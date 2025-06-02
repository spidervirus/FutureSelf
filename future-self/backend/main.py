from fastapi import FastAPI, Body, HTTPException, File, UploadFile, Request, Query # Import Request and Query
from pydantic import BaseModel
import requests # Import requests for calling Ollama
import os # Import os to read environment variables
from supabase import create_client, Client # Import Supabase client
from postgrest.exceptions import APIError # Import specific Supabase exceptions
from fastapi.middleware.cors import CORSMiddleware # Import CORSMiddleware
import whisper # Import OpenAI's Whisper library
from TTS.api import TTS # Import Coqui TTS library
import shutil # To save uploaded file to a temporary file
import base64 # To encode audio to base64
import asyncio # Import asyncio for async subprocess
import uuid # Import uuid for unique file names
from typing import Optional # Import Optional for type hints
import re
import numpy as np
import spacy
import librosa
from dotenv import load_dotenv # Ensure this is imported if not already

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
        spacy.cli.download(NLP_MODEL_NAME)
        nlp = spacy.load(NLP_MODEL_NAME)
        print(f"spaCy model '{NLP_MODEL_NAME}' downloaded and loaded successfully.")
    except Exception as e:
        print(f"Error downloading or loading spaCy model '{NLP_MODEL_NAME}': {e}")
        nlp = None # Handle case where model loading fails

# --- Style Analyzer Functions --- 
def analyze_text_style(text: str):
    if not nlp or not text:
        return {
            "avg_sentence_length": None,
            "emoji_frequency": None,
            "common_emojis": [],
            "common_slang": [],
            "formality_score": None,
        }
    doc = nlp(text)

    sentences = list(doc.sents)
    avg_sentence_length = np.mean([len(sent) for sent in sentences]) if sentences else 0

    emojis = re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', text)
    emoji_frequency = len(emojis) / len(doc) if len(doc) > 0 else 0
    common_emojis = list(set(emojis))

    # Basic slang detection (example)
    slang_terms = [token.text.lower() for token in doc if token.text.lower() in ["lol", "brb", "omg", "btw", "imo", "thx", "np"]]

    num_contractions = len([token for token in doc if "'" in token.text and token.pos_ not in ['PUNCT', 'SYM']])
    # Heuristic: more contractions might mean less formal. Normalize by number of tokens.
    # This is a very rough heuristic.
    formality_score = 1.0 - (num_contractions / len(doc)) if len(doc) > 0 else 0.5 

    return {
        "avg_sentence_length": round(float(avg_sentence_length), 2) if avg_sentence_length is not None else None,
        "emoji_frequency": round(float(emoji_frequency), 3) if emoji_frequency is not None else None,
        "common_emojis": common_emojis[:5],
        "common_slang": list(set(slang_terms))[:5],
        "formality_score": round(float(formality_score), 2) if formality_score is not None else None,
    }

def analyze_voice_style(audio_file_path: str):
    try:
        y, sr = librosa.load(audio_file_path, sr=None) # Load with original sample rate

        f0, _, _ = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
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

# --- Helper function to get or create user style profile --- #
async def get_or_create_user_style_profile(user_id: str, supabase_client: Client) -> dict:
    try:
        # Try to fetch existing profile
        profile_response = supabase_client.table("user_style_profiles").select("*").eq("user_id", user_id).execute()
        
        # Also fetch communication style and personal info from users table
        user_response = supabase_client.table("users").select("communication_style, name, nationality, date_of_birth, current_location").eq("id", user_id).execute()
        communication_style = user_response.data[0].get("communication_style", {}) if user_response.data else {}
        user_name = user_response.data[0].get("name", "") if user_response.data else ""
        nationality = user_response.data[0].get("nationality", "") if user_response.data else ""
        date_of_birth = user_response.data[0].get("date_of_birth", "") if user_response.data else ""
        current_location = user_response.data[0].get("current_location", "") if user_response.data else ""

        if profile_response.data:
            # Merge communication style data and user name with existing profile
            profile = profile_response.data[0]
            profile["communication_style"] = communication_style
            profile["user_name"] = user_name
            profile["nationality"] = nationality
            profile["date_of_birth"] = date_of_birth
            profile["current_location"] = current_location
            return profile
        # Check if no data was returned (profile not found)
        else:
            print(f"No style profile found for user {user_id}, creating default.")
            
            # Proceed to create a default profile if not found
            default_profile_data = {
                "user_id": user_id,
                "avg_sentence_length": None,
                "emoji_frequency": None,
                "formality_score": None,
                "avg_pitch": None,
                "voice_energy": None,
            }
            inserted_response = supabase_client.table("user_style_profiles").insert(default_profile_data).execute()
            
            if inserted_response.data:
                profile = inserted_response.data[0]
                profile["communication_style"] = communication_style
                profile["user_name"] = user_name
                profile["nationality"] = nationality
                profile["date_of_birth"] = date_of_birth
                profile["current_location"] = current_location
                return profile
            else:
                print(f"Failed to create default profile for user {user_id}")
                default_profile_data["communication_style"] = communication_style
                default_profile_data["user_name"] = user_name
                default_profile_data["nationality"] = nationality
                default_profile_data["date_of_birth"] = date_of_birth
                default_profile_data["current_location"] = current_location
                return default_profile_data # Return defaults if creation fails
        # This else block is no longer needed since we handle the no-data case above
        # Keeping it for defensive programming but simplified
        # else:
        #     print(f"Unexpected case: no data and no error for user {user_id}")
        #     return default_profile_data

    except Exception as e:
        print(f"Error in get_or_create_user_style_profile for user {user_id}: {e}")
        # Return a default structure on error to prevent crashes downstream
        return {
            "user_id": user_id, "avg_sentence_length": None, "emoji_frequency": None, 
            "common_emojis": [], "common_slang": [], "formality_score": None, 
            "avg_pitch": None, "voice_energy": None, "communication_style": {}, "user_name": ""
        }

app = FastAPI()

# Add CORS middleware
origins = [
    "http://localhost",
    "http://localhost:*",
    "http://localhost:54625",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["OPTIONS", "POST"], # Explicitly allow OPTIONS and POST
    allow_headers=["*"], # Allows all headers, including Content-Type
)

# --- Supabase Initialization ---
# TODO: Replace with your actual Supabase URL and Service Key
# It's highly recommended to use environment variables for these!
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://hsdxqhfyjbnxuaopwpil.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhzZHhxaGZ5amJueHVhb3B3cGlsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0ODI1ODUxMCwiZXhwIjoyMDYzODM0NTEwfQ.g-gMw6340j7hL-U_LA95q7OFsGh0Lb_PxkQuZ6U5eXk")

if SUPABASE_URL == "https://hsdxqhfyjbnxuaopwpil.supabase.co" or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" in SUPABASE_SERVICE_KEY:
    print("WARNING: Supabase URL or Service Key using hardcoded values. Consider using environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

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

# --- API Endpoints ---
@app.get('/')
async def read_root():
    return {'message': 'Future Self Backend is running!'}

@app.post('/chat', response_model=ChatMessageResponse)
async def chat_endpoint(request: ChatMessageRequest = Body(...)):
    user_id = request.user_id
    user_message = request.message

    # 1. Analyze user's text style
    text_style_features = analyze_text_style(user_message)

    # 2. Get or create user's style profile
    user_profile = await get_or_create_user_style_profile(user_id, supabase)

    # 3. Update style profile with new text features (consider averaging or a more sophisticated update)
    # For simplicity, we'll update with the latest analysis. You might want to average over time.
    update_data = {
        "avg_sentence_length": text_style_features.get("avg_sentence_length") if text_style_features.get("avg_sentence_length") is not None else user_profile.get("avg_sentence_length"),
        "emoji_frequency": text_style_features.get("emoji_frequency") if text_style_features.get("emoji_frequency") is not None else user_profile.get("emoji_frequency"),
        "common_emojis": text_style_features.get("common_emojis") if text_style_features.get("common_emojis") else user_profile.get("common_emojis", []),
        "common_slang": text_style_features.get("common_slang") if text_style_features.get("common_slang") else user_profile.get("common_slang", []),
        "formality_score": text_style_features.get("formality_score") if text_style_features.get("formality_score") is not None else user_profile.get("formality_score"),
    }

    try:
        supabase.table("user_style_profiles").update(update_data).eq("user_id", user_id).execute()
        print(f"Successfully updated style profile for user {user_id}")
    except APIError as e:
        print(f"Error updating style profile for user {user_id}: {e.message}")
        # Continue even if profile update fails, but log it
    except Exception as e:
        print(f"An unexpected error occurred updating style profile for user {user_id}: {e}")

    # Refresh profile after update to ensure we use the latest for the prompt
    user_profile = await get_or_create_user_style_profile(user_id, supabase) # Re-fetch or merge update_data into user_profile

    # 4. Construct the prompt for Ollama, incorporating style
    # Base prompt - can be further refined
    # Extract communication style data from onboarding
    communication_style = user_profile.get("communication_style", {})
    user_name = user_profile.get("user_name", "")
    
    prompt_template = (
        "You are an AI assistant embodying the user's 'Future Self'. "
        "Your goal is to communicate in a way that reflects the user's current communication style, "
        "blended with aspirational qualities. Analyze the user's message and the provided style profile "
        "to guide your response. Be supportive, insightful, and slightly aspirational.\n\n"
        "User Information:\n"
        "- Name: {user_name}\n"
        "- Nationality: {nationality}\n"
        "- Date of Birth: {date_of_birth}\n"
        "- Current Location: {current_location}\n\n"
        "User's Current Style Profile:\n"
        "- Average Sentence Length: {avg_sentence_length}\n"
        "- Emoji Frequency: {emoji_frequency} (0=none, 1=high)\n"
        "- Common Emojis: {common_emojis}\n"
        "- Common Slang/Informal: {common_slang}\n"
        "- Formality Score: {formality_score} (0=very informal, 1=very formal)\n"
        "- Average Pitch (from voice, if available): {avg_pitch}\n"
        "- Voice Energy (from voice, if available): {voice_energy}\n\n"
        "Communication Style from Onboarding:\n"
        "- Message Length Preference: {message_length}\n"
        "- Emoji Usage Level: {emoji_usage}/5\n"
        "- Punctuation Style: {punctuation_style}\n"
        "- Uses Casual Slang: {use_slang}\n"
        "- Common Phrases: {common_phrases}\n"
        "- Chat Sample: {chat_sample}\n"
        "- Typical Response Style: {typical_response}\n\n"
        "Aspirational Qualities to gently weave in: Clarity, confidence, wisdom, positivity.\n\n"
        "User's message: '{user_message}'\n\n"
        "Future Self AI, respond to the user{name_instruction}, subtly mimicking their style while embodying their future self:")

    # Fill the prompt template with style data
    # Use defaults if some profile attributes are None
    # Determine name instruction based on whether user name is available
    name_instruction = f" (address them by name: {user_name})" if user_name and user_name.strip() else ""
    
    prompt = prompt_template.format(
        user_name=user_name if user_name and user_name.strip() else "Not provided",
        nationality=user_profile.get("nationality", "Not provided") if user_profile.get("nationality") and user_profile.get("nationality").strip() else "Not provided",
        date_of_birth=user_profile.get("date_of_birth", "Not provided") if user_profile.get("date_of_birth") else "Not provided",
        current_location=user_profile.get("current_location", "Not provided") if user_profile.get("current_location") and user_profile.get("current_location").strip() else "Not provided",
        name_instruction=name_instruction,
        avg_sentence_length=user_profile.get("avg_sentence_length", "N/A"),
        emoji_frequency=user_profile.get("emoji_frequency", "N/A"),
        common_emojis=', '.join(user_profile.get("common_emojis", [])) if user_profile.get("common_emojis") else "N/A",
        common_slang=', '.join(user_profile.get("common_slang", [])) if user_profile.get("common_slang") else "N/A",
        formality_score=user_profile.get("formality_score", "N/A"),
        avg_pitch=user_profile.get("avg_pitch", "N/A"), # Will be N/A for text-only interactions
        voice_energy=user_profile.get("voice_energy", "N/A"), # Will be N/A for text-only interactions
        # Communication style from onboarding
        message_length=communication_style.get("message_length", "N/A"),
        emoji_usage=communication_style.get("emoji_usage", "N/A"),
        punctuation_style=communication_style.get("punctuation_style", "N/A"),
        use_slang=communication_style.get("use_slang", "N/A"),
        common_phrases=communication_style.get("common_phrases", "N/A"),
        chat_sample=communication_style.get("chat_sample", "N/A"),
        typical_response=communication_style.get("typical_response", "N/A"),
        user_message=user_message
    )

    print(f"Generated prompt for Ollama:\n{prompt}")

    # 5. Call Ollama (Mistral AI)
    ollama_url = os.environ.get("OLLAMA_API_URL", "http://localhost:11434/api/generate")
    ollama_model = os.environ.get("OLLAMA_MODEL", "mistral:7b")

    try:
        response = requests.post(
            ollama_url,
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=60 # Increased timeout for potentially longer generation
        )
        response.raise_for_status() # Raise an exception for HTTP errors
        ai_response_text = response.json().get("response", "").strip()

        # 6. Store the AI's response in chat_messages (optional, but good for history)
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

@app.post('/transcribe', response_model=TranscriptionResponse)
async def transcribe_audio_file(request: Request, file: UploadFile = File(...), user_id_query: Optional[str] = Query(None)):
    user_id_header = request.headers.get("X-User-ID")
    user_id = user_id_query or user_id_header

    if not user_id:
        raise HTTPException(status_code=400, detail="User ID must be provided either in query parameters (user_id_query) or headers (X-User-ID).")

    tmp_opus_path: Optional[str] = None
    tmp_wav_path: Optional[str] = None

    try:
        # Save uploaded Opus file temporarily
        tmp_opus_path = f"temp_{uuid.uuid4()}.opus"
        with open(tmp_opus_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Convert Opus to WAV using FFmpeg
        tmp_wav_path = f"temp_{uuid.uuid4()}.wav"
        ffmpeg_process = await asyncio.create_subprocess_exec(
            'ffmpeg', '-i', tmp_opus_path, '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', tmp_wav_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await ffmpeg_process.communicate()

        if ffmpeg_process.returncode != 0:
            error_detail = stderr.decode() if stderr else "Unknown FFmpeg error"
            print(f"FFmpeg error: {error_detail}")
            raise HTTPException(status_code=500, detail=f"Audio conversion failed: {error_detail}")

        if not whisper_model:
            raise HTTPException(status_code=500, detail="Whisper model is not loaded.")
        
        # Transcribe using OpenAI Whisper
        transcription_result = whisper_model.transcribe(tmp_wav_path, beam_size=5)
        
        transcribed_text: str = ""
        detected_language: str = ""

        if isinstance(transcription_result, dict):
            raw_text_data = transcription_result.get("text")
            raw_lang_data = transcription_result.get("language")

            if isinstance(raw_text_data, str):
                transcribed_text = raw_text_data.strip()
            elif isinstance(raw_text_data, list):
                # If 'text' is a list (e.g., list of segment texts), join them.
                segment_texts = [str(s).strip() for s in raw_text_data if isinstance(s, (str, int, float))]
                transcribed_text = " ".join(filter(None, segment_texts))
                if not transcribed_text and raw_text_data:
                    print(f"Transcription result 'text' was a list, but could not extract valid string data: {raw_text_data}")
            elif raw_text_data is not None:
                # If text is present but not str or list, try to convert to string
                transcribed_text = str(raw_text_data).strip()
                print(f"Transcription result 'text' was of unexpected type {type(raw_text_data)}, converted to string.")
            else: # raw_text_data is None
                print("Transcription result 'text' is missing or None.")
                # transcribed_text remains empty string

            if isinstance(raw_lang_data, str):
                detected_language = raw_lang_data.strip()
            elif raw_lang_data is not None:
                detected_language = str(raw_lang_data).strip()
                print(f"Transcription result 'language' was of unexpected type {type(raw_lang_data)}, converted to string.")
            else: # raw_lang_data is None
                detected_language = "unknown" # Fallback language
                print("Transcription result 'language' is missing or None.")

        else:
            # Handle completely unexpected transcription_result format
            print(f"Unexpected transcription result format (not a dict): {transcription_result}")
            raise HTTPException(status_code=500, detail="Transcription failed due to unexpected result format.")
        
        print(f"Transcription successful. Language: {detected_language}")
        print(f"Transcribed text: {transcribed_text}")

        # Analyze voice style
        voice_style_features = analyze_voice_style(tmp_wav_path)
        print(f"Voice style analysis: {voice_style_features}")

        # Get or create user's style profile
        user_profile = await get_or_create_user_style_profile(user_id, supabase)

        # Update style profile with new voice features
        voice_update_data = {
            "avg_pitch": voice_style_features.get("avg_pitch") if voice_style_features.get("avg_pitch") is not None else user_profile.get("avg_pitch"),
            "voice_energy": voice_style_features.get("voice_energy") if voice_style_features.get("voice_energy") is not None else user_profile.get("voice_energy"),
        }

        try:
            supabase.table("user_style_profiles").update(voice_update_data).eq("user_id", user_id).execute()
            print(f"Successfully updated voice style profile for user {user_id}")
        except APIError as e:
            print(f"Error updating voice style profile for user {user_id}: {e.message}")
        except Exception as e:
            print(f"An unexpected error occurred updating voice style profile for user {user_id}: {e}")

        return TranscriptionResponse(transcribed_text=transcribed_text)

    except HTTPException:
        raise # Re-raise HTTP exceptions
    except Exception as e:
        print(f"An unexpected error occurred in transcribe_audio_file: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        # Clean up temporary files
        if tmp_opus_path and os.path.exists(tmp_opus_path):
            os.remove(tmp_opus_path)
        if tmp_wav_path and os.path.exists(tmp_wav_path):
            os.remove(tmp_wav_path)

@app.post('/synthesize', response_model=SynthesisResponse)
async def synthesize_speech(request: SynthesisRequest = Body(...)):
    user_id = request.user_id
    text_to_synthesize = request.text

    # Get user's style profile for potential TTS customization
    user_profile = await get_or_create_user_style_profile(user_id, supabase)
    
    # Log how we could use style features for TTS (current Coqui model limitations)
    avg_pitch = user_profile.get("avg_pitch")
    voice_energy = user_profile.get("voice_energy")
    print(f"User {user_id} style profile - Avg Pitch: {avg_pitch}, Voice Energy: {voice_energy}")
    print("Note: Current TTS model doesn't support dynamic pitch/energy adjustment. Consider voice cloning for future versions.")

    if not tts_model:
        raise HTTPException(status_code=500, detail="TTS model is not loaded.")

    tmp_wav_path: Optional[str] = None
    tmp_opus_path: Optional[str] = None

    try:
        # Generate a unique filename for the temporary WAV file
        tmp_wav_path = f"temp_{uuid.uuid4()}.wav"
        
        # Synthesize text to WAV file
        tts_model.tts_to_file(text=text_to_synthesize, file_path=tmp_wav_path)
        print(f"TTS synthesis completed. WAV file saved to: {tmp_wav_path}")

        # Convert WAV to Opus using FFmpeg
        tmp_opus_path = tmp_wav_path.replace(".wav", ".opus")
        ffmpeg_process = await asyncio.create_subprocess_exec(
            'ffmpeg', '-i', tmp_wav_path, '-c:a', 'libopus', '-b:a', '64k', tmp_opus_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await ffmpeg_process.communicate()

        if ffmpeg_process.returncode != 0:
            error_detail = stderr.decode() if stderr else "Unknown FFmpeg error"
            print(f"FFmpeg error during WAV to Opus conversion: {error_detail}")
            raise HTTPException(status_code=500, detail=f"Audio conversion to Opus failed: {error_detail}")

        # Read the Opus file and encode it to base64
        with open(tmp_opus_path, "rb") as opus_file:
            opus_audio_data = opus_file.read()
            base64_audio = base64.b64encode(opus_audio_data).decode('utf-8')

        print(f"Opus conversion completed. File size: {len(opus_audio_data)} bytes")
        return SynthesisResponse(audio_content=base64_audio)

    except HTTPException:
        raise # Re-raise HTTP exceptions
    except Exception as e:
        print(f"An unexpected error occurred in synthesize_speech: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        # Clean up temporary files
        if tmp_wav_path and os.path.exists(tmp_wav_path):
            os.remove(tmp_wav_path)
        if tmp_opus_path and os.path.exists(tmp_opus_path):
            os.remove(tmp_opus_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)