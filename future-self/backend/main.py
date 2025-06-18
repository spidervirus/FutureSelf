import os
import shutil
import uuid
import asyncio
import re
import base64
from typing import Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Body, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from postgrest.exceptions import APIError
import requests
import whisper
from TTS.api import TTS
import spacy
import subprocess
import sys
import librosa
import numpy as np
from dotenv import load_dotenv
from astrology_service import astrology_service
from weather_events_service import WeatherEventsService
from datetime import datetime
from celery.result import AsyncResult

# --- Load environment variables ---
load_dotenv() # Call it early

# --- Opus Configuration ---
# Parameters for Opus encoding/decoding
OPUS_SAMPLE_RATE = 48000 # Hz (Typical for Opus, though not directly used in current ffmpeg commands for encoding)
OPUS_NUM_CHANNELS = 1    # Mono (Typical for voice, though not directly used)
OPUS_FRAME_SIZE_MS = 20  # Milliseconds, a common frame size for Opus encoding via FFmpeg

# --- Initialize spaCy model --- 
# This should be done once at application startup.
NLP_MODEL_NAME = "en_core_web_sm"
try:
    nlp = spacy.load(NLP_MODEL_NAME)
    print(f"spaCy model '{NLP_MODEL_NAME}' loaded successfully.")
except OSError:
    print(f"spaCy model '{NLP_MODEL_NAME}' not found. Downloading...")
    try:
        subprocess.check_call([sys.executable, "-m", "spacy", "download", NLP_MODEL_NAME])
        nlp = spacy.load(NLP_MODEL_NAME)
        print(f"spaCy model '{NLP_MODEL_NAME}' downloaded and loaded successfully.")
    except Exception as e:
        print(f"Error downloading or loading spaCy model '{NLP_MODEL_NAME}': {e}")
        nlp = None # Handle case where model loading fails

# --- Style Analyzer Functions --- 
# Remove the analyze_text_style function since it's only used for user_style_profiles
# def analyze_text_style(text: str):
#     if not nlp or not text:
#         return {
#             "avg_sentence_length": None,
#             "emoji_frequency": None,
#             "common_emojis": [],
#             "common_slang": [],
#             "formality_score": None,
#         }
#     doc = nlp(text)

#     sentences = list(doc.sents)
#     avg_sentence_length = np.mean([len(sent) for sent in sentences]) if sentences else 0

#     emojis = re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', text)
#     emoji_frequency = len(emojis) / len(doc) if len(doc) > 0 else 0
#     common_emojis = list(set(emojis))

#     # Basic slang detection (example)
#     slang_terms = [token.text.lower() for token in doc if token.text.lower() in ["lol", "brb", "omg", "btw", "imo", "thx", "np"]]

#     # Simple formality score based on POS tags
#     formality_indicators = {
#         "formal": ["NOUN", "ADJ", "ADP", "DET", "CCONJ"],  # More formal parts of speech
#         "informal": ["INTJ", "PART", "PRON"]  # More informal parts of speech
#     }
    
#     pos_counts = {pos: 0 for pos in set(formality_indicators["formal"]) | set(formality_indicators["informal"])}
#     for token in doc:
#         if token.pos_ in pos_counts:
#             pos_counts[token.pos_] += 1
    
#     formal_count = sum(pos_counts[pos] for pos in formality_indicators["formal"])
#     informal_count = sum(pos_counts[pos] for pos in formality_indicators["informal"])
#     total_count = formal_count + informal_count
    
#     formality_score = formal_count / total_count if total_count > 0 else 0.5  # Default to neutral
    
#     return {
#         "avg_sentence_length": round(float(avg_sentence_length), 2) if avg_sentence_length is not None else None,
#         "emoji_frequency": round(float(emoji_frequency), 4) if emoji_frequency is not None else None,
#         "common_emojis": common_emojis[:5],  # Limit to top 5
#         "common_slang": slang_terms[:5],  # Limit to top 5
#         "formality_score": round(float(formality_score), 2) if formality_score is not None else None,
#     }

def analyze_voice_style(audio_file_path: str):
    try:
        y, sr = librosa.load(audio_file_path, sr=None) # Load with original sample rate

        f0, _, _ = librosa.pyin(y, fmin=float(librosa.note_to_hz('C2')), fmax=float(librosa.note_to_hz('C7')))
        avg_pitch = np.nanmean(f0) if f0 is not None and len(f0[~np.isnan(f0)]) > 0 else None

        rms_energy = np.mean(librosa.feature.rms(y=y))
        
        # Placeholder for speaking rate - ideally calculated using word count from STT and duration
        # duration = librosa.get_duration(y=y, sr=sr)
        # speaking_rate = (word_count / duration) * 60 if duration > 0 else None # Words per minute

        return {
            "avg_pitch": round(float(avg_pitch), 2) if avg_pitch is not None else None,
            "voice_energy": round(float(rms_energy), 4) if rms_energy is not None else None,
            # "speaking_rate": round(float(speaking_rate), 2) if speaking_rate is not None else None,
        }
    except Exception as e:
        print(f"Error analyzing voice style from {audio_file_path}: {e}")
        return {
            "avg_pitch": None,
            "voice_energy": None,
            # "speaking_rate": None,
        }

# --- Helper Functions for Natural Conversation --- #

# Get recent conversation context for natural flow
async def get_conversation_context(user_id: str, supabase_client: Client, limit: int = 5) -> list:
    try:
        response = supabase_client.table("chat_messages")\
            .select("content, author_id, created_at")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .limit(limit * 2)\
            .execute()
        
        if response.data:
            # Format as conversation flow
            messages = []
            for msg in reversed(response.data):
                role = "You" if msg["author_id"] != "ai" else "Your future self"
                messages.append(f"{role}: {msg['content']}")
            return messages[-limit:] if len(messages) > limit else messages
        return []
    except Exception as e:
        print(f"Error getting conversation context: {e}")
        return []

# Detect emotional context for natural responses
def detect_emotional_context(message: str) -> str:
    message_lower = message.lower()
    
    # Stress/Anxiety patterns
    if any(word in message_lower for word in ['stressed', 'anxious', 'worried', 'overwhelmed', 'scared', 'panic']):
        return "You sense your current self is feeling overwhelmed. You remember this feeling well."
    
    # Excitement/Joy patterns  
    elif any(word in message_lower for word in ['excited', 'happy', 'amazing', 'great', 'wonderful', 'fantastic']):
        return "You feel your current self's excitement and it brings back memories of your own journey."
    
    # Confusion/Uncertainty patterns
    elif any(word in message_lower for word in ['confused', 'lost', 'stuck', 'don\'t know', 'unsure', 'help']):
        return "You recognize this uncertainty - you've been exactly where they are now."
    
    # Sadness/Disappointment patterns
    elif any(word in message_lower for word in ['sad', 'disappointed', 'failed', 'giving up', 'hopeless']):
        return "You feel your current self's pain and remember when you felt the same way."
    
    # Goal/Ambition patterns
    elif any(word in message_lower for word in ['goal', 'dream', 'want to', 'planning', 'future', 'hope']):
        return "You smile, remembering when you had these same aspirations."
    
    return "You listen with the understanding that comes from having lived through similar experiences."

# Remove AI-speak patterns to make responses more human
def humanize_response(ai_response: str, user_name: str) -> str:
    # Remove AI-speak patterns
    ai_patterns = [
        (r"as an ai", ""),
        (r"i'm here to help", ""),
        (r"i understand that", "I remember"),
        (r"based on your", "knowing you"),
        (r"i recommend", "I think you should"),
        (r"you might want to consider", "maybe try"),
        (r"as an assistant", ""),
        (r"i'm an ai", ""),
    ]
    
    response = ai_response
    for pattern, replacement in ai_patterns:
        response = re.sub(pattern, replacement, response, flags=re.IGNORECASE)
    
    return response.strip()

# Create natural future self prompt with comprehensive onboarding data
def create_future_self_prompt(user_message: str, user_profile: dict, conversation_context: list | None = None, weather_events_context: dict | None = None) -> str:
    if conversation_context is None:
        conversation_context = []
    user_name = user_profile.get("user_name", "")
    name_part = user_name if user_name and user_name.strip() else "your current self"
    
    # Extract onboarding data for persona building
    nationality = user_profile.get("nationality", "")
    current_location = user_profile.get("current_location", "")
    future_self_description = user_profile.get("future_self_description", "")
    preferred_tone = user_profile.get("preferred_tone", "")
    
    # Personal reflection insights
    mind_space = user_profile.get("mind_space", "")
    future_proud = user_profile.get("future_proud", "")
    most_yourself = user_profile.get("most_yourself", "")
    low_moments = user_profile.get("low_moments", "")
    spiral_reminder = user_profile.get("spiral_reminder", "")
    
    # Growth and challenges
    change_goal = user_profile.get("change_goal", "")
    avoid_tendency = user_profile.get("avoid_tendency", "")
    feeling_description = user_profile.get("feeling_description", "")
    
    # Future vision
    future_description = user_profile.get("future_description", "")
    future_age = user_profile.get("future_age", "")
    typical_day = user_profile.get("typical_day", "")
    accomplishment = user_profile.get("accomplishment", "")
    
    # Communication style
    words_slang = user_profile.get("words_slang", "")
    message_preference = user_profile.get("message_preference", "")
    messaging_frequency = user_profile.get("messaging_frequency", "")
    emoji_usage_preference = user_profile.get("emoji_usage_preference", "")
    communication_tone = user_profile.get("communication_tone", "")
    chat_sample = user_profile.get("chat_sample", "")
    common_phrases = user_profile.get("common_phrases", "")
    
    # Build persona context
    persona_context = ""
    if nationality or current_location:
        location_info = f" from {nationality}" if nationality else ""
        location_info += f" living in {current_location}" if current_location else ""
        persona_context += f"You're{location_info}. "
    
    if future_self_description:
        persona_context += f"You described your future self as: {future_self_description}. "
    
    # Core persona establishment with rich context
    base_prompt = f"""
You are {name_part}'s future self, speaking from {future_age if future_age else '5-10'} years ahead. {persona_context}You've lived through exactly what {name_part} is experiencing now. You remember these feelings, these challenges, these dreams - because they were YOUR feelings, challenges, and dreams.

You're not an AI assistant. You're literally {name_part} who has grown, learned, and gained wisdom through experience.
"""
    
    # Add personal insights from onboarding
    if mind_space:
        base_prompt += f"\n\nYou remember when you used to think about: {mind_space}. You've gained perspective on these thoughts."
    
    if change_goal:
        base_prompt += f"\n\nYou remember saying you'd change: {change_goal}. You know the journey of actually making that change."
    
    if avoid_tendency:
        base_prompt += f"\n\nYou remember how you used to avoid: {avoid_tendency}. You've learned to face these things differently."
    
    if spiral_reminder:
        base_prompt += f"\n\nYou remember needing to hear: {spiral_reminder} when you were spiraling. You know exactly when and how to offer this wisdom."
    
    if accomplishment:
        base_prompt += f"\n\nYou've achieved what you once dreamed of: {accomplishment}. You know the path that led there."
    
    if typical_day:
        base_prompt += f"\n\nYour typical day now looks like: {typical_day}. You remember the journey from where you were to where you are."
    
    # Add communication style guidance
    communication_guidance = ""
    if preferred_tone:
        communication_guidance += f"You naturally communicate with a {preferred_tone} tone. "
    
    if message_preference == "long":
        communication_guidance += "You tend to give thoughtful, detailed responses. "
    elif message_preference == "short":
        communication_guidance += "You prefer concise, direct communication. "
    
    if emoji_usage_preference == "love them":
        communication_guidance += "You use emojis naturally in your communication. "
    elif emoji_usage_preference == "never":
        communication_guidance += "You communicate without emojis. "
    
    if words_slang:
        communication_guidance += f"You might use phrases like: {words_slang}. "
    
    if common_phrases:
        communication_guidance += f"You often say things like: {common_phrases}. "
    
    if chat_sample:
        communication_guidance += f"Your communication style is similar to: {chat_sample}. "
    
    # Add astrology insights if available
    astrology_context = ""
    astrology_data = user_profile.get('astrology_data', {})
    if astrology_data and 'insights' in astrology_data:
        insights = astrology_data['insights']
        sun_sign = astrology_data.get('birth_chart', {}).get('sun_sign', '')
        if sun_sign:
            astrology_context += f"\n\nAs a {sun_sign}, you understand the core traits that have shaped your journey: {insights.get('sun_sign_traits', '')} "
        
        if 'moon_sign' in insights:
            astrology_context += f"Your Moon in {insights['moon_sign']} has influenced your emotional growth. "
        
        if 'rising_sign' in insights:
            astrology_context += f"With {insights['rising_sign']} rising, you've learned how your outer personality has evolved. "
    
    base_prompt += astrology_context
    
    # Add weather and events context if available
    weather_events_context_text = ""
    if weather_events_context and weather_events_context != {}:
        current_location = user_profile.get('current_location', '')
        
        # Add current weather context
        if 'weather' in weather_events_context and weather_events_context['weather']:
            weather = weather_events_context['weather']
            weather_events_context_text += f"\n\nRight now in {current_location}, it's {weather['description']} with a temperature of {weather['temperature']}°C. "
            
            # Generate weather advice using the service
            weather_service = WeatherEventsService()
            from weather_events_service import WeatherData
            weather_obj = WeatherData(
                temperature=weather['temperature'],
                feels_like=weather['feels_like'],
                humidity=weather['humidity'],
                description=weather['description'],
                wind_speed=weather['wind_speed'],
                pressure=weather['pressure']
            )
            advice = weather_service.get_weather_advice(weather_obj)
            weather_events_context_text += f"Given the current weather, you might suggest: {advice} "
            
        # Add local events context
        if 'events' in weather_events_context and weather_events_context['events']:
            events = weather_events_context['events'][:3]  # Limit to top 3 events
            if events:
                weather_events_context_text += f"\n\nThere are some interesting events happening in {current_location}: "
                for event in events:
                    weather_events_context_text += f"{event['name']} on {event['date']}. "
                weather_events_context_text += "You might reference these when giving advice about getting out or staying engaged with the community. "
    
    base_prompt += weather_events_context_text
    base_prompt += f"\n\nYour current self just shared: \"{user_message}\"\n\n{detect_emotional_context(user_message)}"
    
    # Add conversation context if available
    if conversation_context:
        context_text = "\n\nRecent conversation:\n" + "\n".join(conversation_context)
        base_prompt += context_text
    
    # Add natural conversation guidance with communication style
    guidance = f"""

{communication_guidance}

As their future self, you naturally embody different aspects depending on what they need:

- When they need direction: Share wisdom from your journey, ask guiding questions
- When they're struggling: Reflect their feelings back with understanding, offer comfort
- When they're excited: Share in their joy, help them channel that energy
- When they're stuck: Gently challenge their perspective, offer new ways of thinking
- When they're planning: Help them think through decisions with your experience
- When discussing daily life: Use current weather and local events to provide contextual, practical advice
- When they need motivation: Suggest weather-appropriate activities or local events that align with their goals

Respond as your future self would - with understanding, wisdom, and authentic care. Sometimes you might:
- Share a memory of when you felt exactly this way
- Ask a question that helps them see things differently  
- Offer gentle guidance from your experience
- Simply validate what they're feeling
- Challenge them lovingly when needed

Be natural. Be authentic. Be the wise, loving version of {name_part} who wants to help. Draw from your shared experiences and the journey you've taken to become who you are now.
"""
    
    return base_prompt + guidance

# --- Helper function to get or create user style profile --- #

app = FastAPI()

# Add CORS middleware
origins = [
    "http://localhost",
    "http://localhost:*",
    "http://localhost:50962",
    "http://127.0.0.1:*",
    "*",  # Allow all origins for development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
        allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], # Allow all common HTTP methods
    allow_headers=["*"], # Allows all headers, including Content-Type
)

# --- Supabase Initialization ---
# Get Supabase credentials from environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_KEY")  # Changed from SUPABASE_SERVICE_KEY to SUPABASE_KEY to match .env.example

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print(f"ERROR: Supabase URL or Service Key not found in environment variables. Please set them in your .env file.")
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY: {SUPABASE_SERVICE_KEY}")
    sys.exit(1)

# Fix for 'proxy' parameter compatibility issue with newer versions of gotrue
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
except TypeError as e:
    if "unexpected keyword argument 'proxy'" in str(e):
        print("Handling gotrue proxy parameter compatibility issue...")
        # Import required modules for the workaround
        from supabase._sync.client import SyncClient
        from gotrue._sync.gotrue_client import SyncGoTrueClient
        from gotrue._sync.gotrue_base_api import SyncGoTrueBaseAPI
        
        # Monkey patch to remove the proxy parameter
        original_init = SyncGoTrueBaseAPI.__init__
        def patched_init(self, *args, **kwargs):
            if 'proxy' in kwargs:
                del kwargs['proxy']
            return original_init(self, *args, **kwargs)
        SyncGoTrueBaseAPI.__init__ = patched_init
        
        # Try again with the patched method
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        print("Successfully connected to Supabase after fixing proxy parameter issue.")
    else:
        print(f"Error connecting to Supabase: {e}")
        sys.exit(1)

# --- Pydantic Models ---
class ChatMessageRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: str | None = None # Added optional conversation_id

class ChatMessageResponse(BaseModel):
    response: str

class TranscriptionResponse(BaseModel):
    transcribed_text: str

class SynthesisRequest(BaseModel):
    text: str
    user_id: str # Added user_id
    # Potentially add parameters for voice, speed, etc.

class SynthesisResponse(BaseModel):
    audio_content: str # Base64 encoded audio content

# --- Initialize OpenAI Whisper Model ---
# You might want to load a smaller model like "base" or "small" depending on your resources
# The first time you run this, the model will be downloaded.
# whisper_model_size = "base"
# # Run on CPU. Replace "cpu" with "cuda" if you have a compatible GPU and PyTorch installed.
# whisper_device = "cpu"
# # Set compute_type to "int8" or "float16" for potentially faster inference on CPU
# whisper_compute_type = "int8"

# # Load the model
# # This can take some time and memory, consider doing this once on startup
# # and potentially using a background task or lazy loading for production
# try:
#     whisper_model = WhisperModel(whisper_model_size, device=whisper_device, compute_type=whisper_compute_type)
#     print("Whisper model loaded successfully.")
# except Exception as e:
#     print(f"Error loading Whisper model: {e}")
#     whisper_model = None # Handle case where model loading fails

# --- Initialize OpenAI Whisper Model ---
# You can choose a model size like 'tiny', 'base', 'small', 'medium', 'large'
# Smaller models are faster but less accurate.
whisper_model_name = "base" # Or 'small', 'medium', etc.

try:
    print(f"Loading OpenAI Whisper model: {whisper_model_name}...")
    whisper_model = whisper.load_model(whisper_model_name)
    print("OpenAI Whisper model loaded successfully.")
except Exception as e:
    print(f"Error loading OpenAI Whisper model '{whisper_model_name}': {e}")
    whisper_model = None # Handle case where model loading fails

# --- Initialize Coqui TTS Model ---
# You need to choose a suitable pre-trained model.
# You can list available models using: TTS().list_models()
# For English, 'tts_models/en/ljspeech/tacotron2-ddc' or 'tts_models/en/vctk/vits' are options.
# 'tts_models/multilingual/multi-dataset/xtts_v2' is a large, powerful multilingual model.
tts_model_name = "tts_models/en/ljspeech/tacotron2-DDC" 
tts_device = "cpu" # Or "cuda" if you have a compatible GPU

try:
    # Ensure the model is downloaded and loaded
    tts_model = TTS(model_name=tts_model_name, progress_bar=False).to(tts_device)
    print(f"Coqui TTS model '{tts_model_name}' loaded successfully.")
except Exception as e:
    print(f"Error loading Coqui TTS model '{tts_model_name}': {e}")
    tts_model = None # Handle case where model loading fails

# --- Initialize NLP Services ---
print("Loading NLP services...")

# Initialize service variables
emotion_service = None
bias_service = None
analytics_service = None

# Try to import and initialize each service separately
try:
    from emotion_detection_service import EmotionDetectionService
    emotion_service = EmotionDetectionService()
    print("Emotion detection service loaded successfully.")
except Exception as e:
    print(f"Error loading emotion detection service: {e}")

try:
    from bias_analysis_service import BiasAnalysisService
    bias_service = BiasAnalysisService()
    print("Bias analysis service loaded successfully.")
except Exception as e:
    print(f"Error loading bias analysis service: {e}")

try:
    from analytics_service import AnalyticsService
    analytics_service = AnalyticsService(supabase)
    print("Analytics service loaded successfully.")
except Exception as e:
    print(f"Error loading analytics service: {e}")

if emotion_service and bias_service and analytics_service:
    print("All NLP services loaded successfully.")
else:
    print("Some NLP services could not be loaded. The application will continue with limited functionality.")


# --- API Endpoints ---
@app.get('/')
async def read_root():
    return {'message': 'Future Self Backend is running!'}

@app.post('/chat', response_model=ChatMessageResponse)
async def chat_endpoint(request: ChatMessageRequest = Body(...)):
    user_id = request.user_id
    user_message = request.message

    # Get user data from users table
    try:
        user_response = supabase.table("users").select("""
            communication_style, name, nationality, birth_country, date_of_birth, current_location,
            future_self_description, preferred_tone, mind_space, future_proud, most_yourself,
            low_moments, spiral_reminder, change_goal, avoid_tendency, feeling_description,
            future_description, future_age, typical_day, accomplishment, words_slang,
            message_preference, messaging_frequency, emoji_usage_preference,
            preferred_communication, communication_tone, message_length, emoji_usage,
            punctuation_style, use_slang, chat_sample, common_phrases
        """).eq("id", user_id).execute()
        user_data = user_response.data[0] if user_response.data else {}
    except Exception as e:
        print(f"Error fetching user data for user {user_id}: {e}")
        user_data = {}

    # 4. Get conversation context for natural flow
    conversation_context = await get_conversation_context(user_id, supabase)
    
    # 5. Generate weather and events context if location is available
    weather_events_context = {}
    current_location = user_data.get('current_location', '')
    if current_location:
        try:
            weather_service = WeatherEventsService()
            weather_events_context = await weather_service.get_location_context(current_location)
            print(f"Generated weather/events context for {current_location}")
        except Exception as e:
            print(f"Error generating weather/events context: {e}")
            weather_events_context = {}
    
    # 6. Create natural future self prompt with weather/events context
    prompt = create_future_self_prompt(user_message, user_data, conversation_context, weather_events_context)

    print(f"Generated natural conversation prompt for Ollama:\n{prompt}")

    # 5. Call Ollama (Mistral AI)
    ollama_url = os.environ.get("OLLAMA_API_URL")
    ollama_model = os.environ.get("OLLAMA_MODEL", "mistral")
    
    if not ollama_url:
        print("ERROR: Ollama API URL not found in environment variables. Please set it in your .env file.")
        return {"error": "Ollama API URL not configured"}

    try:
        # Retry logic for Ollama API calls
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    ollama_url,
                    json={"model": ollama_model, "prompt": prompt, "stream": False},
                    timeout=180  # Increased timeout to 3 minutes for longer generation
                )
                response.raise_for_status() # Raise an exception for HTTP errors
                ai_response_text = response.json().get("response", "").strip()
                break  # Success, exit retry loop
            except requests.exceptions.Timeout as timeout_error:
                print(f"Ollama timeout on attempt {attempt + 1}/{max_retries}: {timeout_error}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise HTTPException(
                        status_code=503, 
                        detail="Ollama service is taking too long to respond. Please try again later or check if Ollama is running properly."
                    )
            except requests.exceptions.ConnectionError as conn_error:
                print(f"Ollama connection error on attempt {attempt + 1}/{max_retries}: {conn_error}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise HTTPException(
                        status_code=503, 
                        detail="Cannot connect to Ollama service. Please ensure Ollama is running on localhost:11434."
                    )
        
        # 6. Humanize the response to remove AI-speak patterns
        user_name = user_profile.get("user_name", "")
        ai_response_text = humanize_response(ai_response_text, user_name)

        # 7. Store the AI's response in chat_messages (optional, but good for history)
        try:
            supabase.table("chat_messages").insert({
                "user_id": user_id,
                "message_id": f"ai_{uuid.uuid4()}",
                "content": ai_response_text,
                "author_id": "ai" # AI as the author
            }).execute()
        except APIError as e:
            print(f"Error saving AI response to Supabase: {e.message}")
        except Exception as e:
            print(f"An unexpected error occurred saving AI response: {e}")

        return ChatMessageResponse(response=ai_response_text)

    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama: {e}")
        raise HTTPException(status_code=503, detail=f"Error communicating with Ollama: {str(e)}")
    except Exception as e:
        print(f"An unexpected error occurred in chat_endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# Import Celery tasks and AsyncResult for task status tracking
from tasks import transcribe_audio as transcribe_audio_task
from celery.result import AsyncResult

# Add new model for task status
class TaskStatusResponse(BaseModel):
    task_id: str
    status: str

# Add new model for transcription task response
class TranscriptionTaskResponse(BaseModel):
    task_id: str

# Import Celery tasks and AsyncResult for task status tracking
from tasks import transcribe_audio as transcribe_audio_task
from celery.result import AsyncResult

# Add new model for task status
class TaskStatusResponse(BaseModel):
    task_id: str
    status: str

# Add new model for transcription task response
class TranscriptionTaskResponse(BaseModel):
    task_id: str

@app.post('/transcribe', response_model=TranscriptionTaskResponse)
async def transcribe_audio_file(request: Request, file: UploadFile = File(...), user_id_query: Optional[str] = Query(None)):
    user_id_header = request.headers.get("X-User-ID")
    user_id = user_id_query or user_id_header

    if not user_id:
        raise HTTPException(status_code=400, detail="User ID must be provided either in query parameters (user_id_query) or headers (X-User-ID).")

    try:
        # Read the file content
        file_content = await file.read()
        
        # Encode the file content as base64
        audio_data_base64 = base64.b64encode(file_content).decode('utf-8')
        
        # Submit the task to Celery
        task = transcribe_audio_task.delay(audio_data_base64, user_id)
        
        print(f"Transcription task submitted with ID: {task.id}")
        
        # Return the task ID to the client
        return TranscriptionTaskResponse(task_id=task.id)

    except Exception as e:
        print(f"An unexpected error occurred in transcribe_audio_file: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get('/transcribe/status/{task_id}', response_model=TaskStatusResponse)
async def get_transcription_status(task_id: str):
    """
    Check the status of a transcription task
    """
    try:
        # Get the task result
        task_result = AsyncResult(task_id)
        
        # Return the task status
        return TaskStatusResponse(task_id=task_id, status=task_result.status)
    
    except Exception as e:
        print(f"Error checking task status: {e}")
        raise HTTPException(status_code=500, detail=f"Error checking task status: {str(e)}")

@app.get('/transcribe/result/{task_id}', response_model=TranscriptionResponse)
async def get_transcription_result(task_id: str):
    """
    Get the result of a completed transcription task
    """
    try:
        # Get the task result
        task_result = AsyncResult(task_id)
        
        # Check if the task is ready
        if not task_result.ready():
            raise HTTPException(status_code=202, detail="Task is still processing")
        
        # Check if the task failed
        if task_result.failed():
            raise HTTPException(status_code=500, detail="Task failed")
        
        # Get the result
        result = task_result.get()
        
        # Return the transcription result
        return TranscriptionResponse(transcribed_text=result.get("transcribed_text", ""))
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting task result: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting task result: {str(e)}")

# Import Celery task for speech synthesis
from tasks import synthesize_speech as synthesize_speech_task

# Add new model for synthesis task response
class SynthesisTaskResponse(BaseModel):
    task_id: str

@app.post('/synthesize', response_model=SynthesisTaskResponse)
async def synthesize_speech(request: SynthesisRequest = Body(...)):
    user_id = request.user_id
    text_to_synthesize = request.text

    try:
        # Submit the task to Celery
        task = synthesize_speech_task.delay(text_to_synthesize, user_id)
        
        print(f"Speech synthesis task submitted with ID: {task.id}")
        
        # Return the task ID to the client
        return SynthesisTaskResponse(task_id=task.id)

    except Exception as e:
        print(f"An unexpected error occurred in synthesize_speech: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get('/synthesize/status/{task_id}', response_model=TaskStatusResponse)
async def get_synthesis_status(task_id: str):
    """
    Check the status of a speech synthesis task
    """
    try:
        # Get the task result
        task_result = AsyncResult(task_id)
        
        # Return the task status
        return TaskStatusResponse(task_id=task_id, status=task_result.status)
    
    except Exception as e:
        print(f"Error checking synthesis task status: {e}")
        raise HTTPException(status_code=500, detail=f"Error checking task status: {str(e)}")

@app.get('/synthesize/result/{task_id}', response_model=SynthesisResponse)
async def get_synthesis_result(task_id: str):
    """
    Get the result of a completed speech synthesis task
    """
    try:
        # Get the task result
        task_result = AsyncResult(task_id)
        
        # Check if the task is ready
        if not task_result.ready():
            raise HTTPException(status_code=202, detail="Task is still processing")
        
        # Check if the task failed
        if task_result.failed():
            raise HTTPException(status_code=500, detail="Task failed")
        
        # Get the result
        result = task_result.get()
        
        # Return the synthesis result
        return SynthesisResponse(audio_content=result.get("audio_content", ""))
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting synthesis task result: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting task result: {str(e)}")

# Add this import at the top with other imports
from fastapi.responses import StreamingResponse
import json

# Add this new model for streaming responses
class ChatStreamRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: str | None = None

# NLP Analysis Models
class EmotionAnalysisRequest(BaseModel):
    text: str
    user_id: str
    audio_file: Optional[str] = None  # Base64 encoded audio for voice emotion analysis

class EmotionAnalysisResponse(BaseModel):
    emotions: dict
    dominant_emotion: str
    confidence: float
    voice_emotions: Optional[dict] = None

class BiasAnalysisRequest(BaseModel):
    text: str
    user_id: str

class BiasAnalysisResponse(BaseModel):
    toxicity_score: float
    bias_patterns: dict
    language: str
    sentiment: dict
    recommendations: list

# Analytics Models
class AnalyticsRequest(BaseModel):
    user_id: str
    days: Optional[int] = 30

class EmotionTrendsResponse(BaseModel):
    trends: dict
    summary: dict
    daily_data: Optional[dict] = None

class BiasTrendsResponse(BaseModel):
    trends: dict
    summary: dict
    daily_data: Optional[dict] = None

class UserInsightsResponse(BaseModel):
    emotion_insights: list
    bias_insights: list
    recommendations: list
    overall_wellbeing_score: int

# Emotion Analysis Endpoint
# Import Celery task for emotion analysis
from tasks import analyze_emotion as analyze_emotion_task

# Add new model for emotion analysis task response
class EmotionAnalysisTaskResponse(BaseModel):
    task_id: str

@app.post('/analyze-emotion', response_model=EmotionAnalysisTaskResponse)
async def analyze_emotion_endpoint(request: EmotionAnalysisRequest = Body(...)):
    if not emotion_service:
        raise HTTPException(status_code=503, detail="Emotion detection service is not available")
    
    try:
        # Submit the task to Celery
        task = analyze_emotion_task.delay(request.text, request.audio_file, request.user_id)
        
        print(f"Emotion analysis task submitted with ID: {task.id}")
        
        # Return the task ID to the client
        return EmotionAnalysisTaskResponse(task_id=task.id)
    
    except Exception as e:
        print(f"An unexpected error occurred in analyze_emotion: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get('/analyze-emotion/status/{task_id}', response_model=TaskStatusResponse)
async def get_emotion_analysis_status(task_id: str):
    """
    Check the status of an emotion analysis task
    """
    try:
        # Get the task result
        task_result = AsyncResult(task_id)
        
        # Return the task status
        return TaskStatusResponse(task_id=task_id, status=task_result.status)
    
    except Exception as e:
        print(f"Error checking emotion analysis task status: {e}")
        raise HTTPException(status_code=500, detail=f"Error checking task status: {str(e)}")

@app.get('/analyze-emotion/result/{task_id}', response_model=EmotionAnalysisResponse)
async def get_emotion_analysis_result(task_id: str):
    """
    Get the result of a completed emotion analysis task
    """
    try:
        # Get the task result
        task_result = AsyncResult(task_id)
        
        # Check if the task is ready
        if not task_result.ready():
            raise HTTPException(status_code=202, detail="Task is still processing")
        
        # Check if the task failed
        if task_result.failed():
            raise HTTPException(status_code=500, detail="Task failed")
        
        # Get the result
        result = task_result.get()
        
        # Return the emotion analysis result
        return EmotionAnalysisResponse(
            emotions=result.get("emotions", {}),
            dominant_emotion=result.get("dominant_emotion", ""),
            confidence=result.get("confidence", 0.0),
            voice_emotions=result.get("voice_emotions")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting emotion analysis task result: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting task result: {str(e)}")

# Import Celery task for bias analysis
from tasks import analyze_bias as analyze_bias_task

# Add new model for bias analysis task response
class BiasAnalysisTaskResponse(BaseModel):
    task_id: str

# Bias Analysis Endpoint
@app.post('/analyze-bias', response_model=BiasAnalysisTaskResponse)
async def analyze_bias_endpoint(request: BiasAnalysisRequest = Body(...)):
    if not bias_service:
        raise HTTPException(status_code=503, detail="Bias analysis service is not available")
    
    try:
        # Submit the task to Celery
        task = analyze_bias_task.delay(request.text, request.user_id)
        
        print(f"Bias analysis task submitted with ID: {task.id}")
        
        # Return the task ID to the client
        return BiasAnalysisTaskResponse(task_id=task.id)
    
    except Exception as e:
        print(f"An unexpected error occurred in analyze_bias: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get('/analyze-bias/status/{task_id}', response_model=TaskStatusResponse)
async def get_bias_analysis_status(task_id: str):
    """
    Check the status of a bias analysis task
    """
    try:
        # Get the task result
        task_result = AsyncResult(task_id)
        
        # Return the task status
        return TaskStatusResponse(task_id=task_id, status=task_result.status)
    
    except Exception as e:
        print(f"Error checking bias analysis task status: {e}")
        raise HTTPException(status_code=500, detail=f"Error checking task status: {str(e)}")

@app.get('/analyze-bias/result/{task_id}', response_model=BiasAnalysisResponse)
async def get_bias_analysis_result(task_id: str):
    """
    Get the result of a completed bias analysis task
    """
    try:
        # Get the task result
        task_result = AsyncResult(task_id)
        
        # Check if the task is ready
        if not task_result.ready():
            raise HTTPException(status_code=202, detail="Task is still processing")
        
        # Check if the task failed
        if task_result.failed():
            raise HTTPException(status_code=500, detail="Task failed")
        
        # Get the result
        result = task_result.get()
        
        # Return the bias analysis result
        return BiasAnalysisResponse(
            toxicity_score=result.get("toxicity_score", 0.0),
            bias_patterns=result.get("bias_patterns", {}),
            language=result.get("language", ""),
            sentiment=result.get("sentiment", {}),
            recommendations=result.get("recommendations", [])
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting bias analysis task result: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting task result: {str(e)}")

# Analytics Endpoints
@app.post('/analytics/emotion-trends', response_model=EmotionTrendsResponse)
async def get_emotion_trends_endpoint(request: AnalyticsRequest = Body(...)):
    if not analytics_service:
        raise HTTPException(status_code=503, detail="Analytics service is not available")
    
    try:
        trends_data = analytics_service.get_emotion_trends(request.user_id, request.days)
        
        if 'error' in trends_data:
            raise HTTPException(status_code=500, detail=trends_data['error'])
        
        return EmotionTrendsResponse(
            trends=trends_data.get('trends', {}),
            summary=trends_data.get('summary', {}),
            daily_data=trends_data.get('daily_data')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting emotion trends: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get emotion trends: {str(e)}")

@app.post('/analytics/bias-trends', response_model=BiasTrendsResponse)
async def get_bias_trends_endpoint(request: AnalyticsRequest = Body(...)):
    if not analytics_service:
        raise HTTPException(status_code=503, detail="Analytics service is not available")
    
    try:
        trends_data = analytics_service.get_bias_trends(request.user_id, request.days)
        
        if 'error' in trends_data:
            raise HTTPException(status_code=500, detail=trends_data['error'])
        
        return BiasTrendsResponse(
            trends=trends_data.get('trends', {}),
            summary=trends_data.get('summary', {}),
            daily_data=trends_data.get('daily_data')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting bias trends: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get bias trends: {str(e)}")

@app.post('/analytics/user-insights', response_model=UserInsightsResponse)
async def get_user_insights_endpoint(request: AnalyticsRequest = Body(...)):
    if not analytics_service:
        raise HTTPException(status_code=503, detail="Analytics service is not available")
    
    try:
        insights_data = analytics_service.get_user_insights(request.user_id, request.days)
        
        if 'error' in insights_data:
            print(f"Analytics service error: {insights_data['error']}")
            # Still return partial data if available
        
        return UserInsightsResponse(
            emotion_insights=insights_data.get('emotion_insights', []),
            bias_insights=insights_data.get('bias_insights', []),
            recommendations=insights_data.get('recommendations', []),
            overall_wellbeing_score=insights_data.get('overall_wellbeing_score', 0)
        )
        
    except Exception as e:
        print(f"Error getting user insights: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get user insights: {str(e)}")

@app.get('/analytics/emotion-chart/{user_id}')
async def get_emotion_chart_endpoint(user_id: str, days: int = 30):
    if not analytics_service:
        raise HTTPException(status_code=503, detail="Analytics service is not available")
    
    try:
        chart_base64 = analytics_service.generate_emotion_chart(user_id, days)
        
        if not chart_base64:
            raise HTTPException(status_code=404, detail="No data available to generate chart")
        
        return {"chart": chart_base64, "format": "png"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating emotion chart: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate emotion chart: {str(e)}")

# NLP Endpoints for compatibility with frontend
@app.post('/nlp/emotion', response_model=EmotionAnalysisTaskResponse)
async def nlp_emotion_endpoint(request: EmotionAnalysisRequest = Body(...)):
    """Compatibility endpoint for /nlp/emotion that redirects to /analyze-emotion"""
    return await analyze_emotion_endpoint(request)

@app.post('/nlp/bias', response_model=BiasAnalysisTaskResponse)
async def nlp_bias_endpoint(request: BiasAnalysisRequest = Body(...)):
    """Compatibility endpoint for /nlp/bias that redirects to /analyze-bias"""
    return await analyze_bias_endpoint(request)

# Add this new endpoint for streaming responses
@app.post('/chat/stream')
async def chat_stream_endpoint(request: ChatStreamRequest = Body(...)):
    user_id = request.user_id
    user_message = request.message

    # Get user data from users table
    try:
        user_response = supabase.table("users").select("""
            communication_style, name, nationality, birth_country, date_of_birth, current_location,
            future_self_description, preferred_tone, mind_space, future_proud, most_yourself,
            low_moments, spiral_reminder, change_goal, avoid_tendency, feeling_description,
            future_description, future_age, typical_day, accomplishment, words_slang,
            message_preference, messaging_frequency, emoji_usage_preference,
            preferred_communication, communication_tone, message_length, emoji_usage,
            punctuation_style, use_slang, chat_sample, common_phrases
        """).eq("id", user_id).execute()
        user_data = user_response.data[0] if user_response.data else {}
    except Exception as e:
        print(f"Error fetching user data for user {user_id}: {e}")
        user_data = {}

    # Get conversation context for natural flow
    conversation_context = await get_conversation_context(user_id, supabase)
    
    # Generate weather and events context if location is available
    weather_events_context = {}
    current_location = user_data.get('current_location', '')
    if current_location:
        try:
            weather_service = WeatherEventsService()
            weather_events_context = await weather_service.get_location_context(current_location)
            print(f"Generated weather/events context for {current_location}")
        except Exception as e:
            print(f"Error generating weather/events context: {e}")
            weather_events_context = {}
    
    # Create natural future self prompt with weather/events context
    prompt = create_future_self_prompt(user_message, user_data, conversation_context, weather_events_context)

    print(f"Generated natural conversation prompt for Ollama:\n{prompt}")

    # Call Ollama (Mistral AI) with streaming enabled
    ollama_url = os.environ.get("OLLAMA_API_URL")
    ollama_model = os.environ.get("OLLAMA_MODEL", "mistral:7b")
    
    if not ollama_url:
        print("ERROR: Ollama API URL not found in environment variables. Please set it in your .env file.")
        return {"error": "Ollama API URL not configured"}

    async def generate_stream():
        # Store the complete response for saving to database later
        complete_response = ""
        
        try:
            # Set up the streaming request to Ollama
            response = requests.post(
                ollama_url,
                json={"model": ollama_model, "prompt": prompt, "stream": True},
                stream=True,  # Enable streaming from requests
                timeout=180  # Increased timeout to 3 minutes for longer generation
            )
            response.raise_for_status()
            
            # Stream each chunk as it arrives
            for line in response.iter_lines():
                if line:
                    # Parse the JSON response from Ollama
                    chunk_data = json.loads(line)
                    if "response" in chunk_data:
                        chunk_text = chunk_data["response"]
                        complete_response += chunk_text
                        # Format for SSE
                        yield f"data: {json.dumps({'text': chunk_text})}\n\n"
            
            # Save the complete response to the database
            try:
                supabase.table("chat_messages").insert({
                    "user_id": user_id,
                    "message_id": f"ai_{uuid.uuid4()}",
                    "content": complete_response,
                    "author_id": "ai" # AI as the author
                }).execute()
            except Exception as e:
                print(f"Error saving AI response to Supabase: {e}")
                
            # Send a completion event
            yield f"data: {json.dumps({'done': True})}\n\n"
            
        except requests.exceptions.RequestException as e:
            print(f"Error calling Ollama: {e}")
            yield f"data: {json.dumps({'error': f'Error communicating with Ollama: {str(e)}'})}\n\n"
        except Exception as e:
            print(f"An unexpected error occurred in chat_stream_endpoint: {e}")
            yield f"data: {json.dumps({'error': f'An unexpected error occurred: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)