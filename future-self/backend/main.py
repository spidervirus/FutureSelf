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
async def get_or_create_user_style_profile(user_id: str, supabase_client: Client) -> dict:
    try:
        # Try to fetch existing profile
        profile_response = supabase_client.table("user_style_profiles").select("*").eq("user_id", user_id).execute()
        
        # Also fetch all onboarding data from users table
        user_response = supabase_client.table("users").select("""
            communication_style, name, nationality, birth_country, date_of_birth, current_location,
            future_self_description, preferred_tone, mind_space, future_proud, most_yourself,
            low_moments, spiral_reminder, change_goal, avoid_tendency, feeling_description,
            future_description, future_age, typical_day, accomplishment, words_slang,
            message_preference, messaging_frequency, emoji_usage_preference,
            preferred_communication, communication_tone, message_length, emoji_usage,
            punctuation_style, use_slang, chat_sample, common_phrases
        """).eq("id", user_id).execute()
        # Extract all user data from the response
        user_data = user_response.data[0] if user_response.data else {}
        communication_style = user_data.get("communication_style", {})
        user_name = user_data.get("name", "")
        nationality = user_data.get("nationality", "")
        birth_country = user_data.get("birth_country", "")
        date_of_birth = user_data.get("date_of_birth", "")
        current_location = user_data.get("current_location", "")
        
        # Generate astrology data if birth date and country are available
        astrology_data = {}
        if date_of_birth and birth_country:
            try:
                birth_date = datetime.fromisoformat(date_of_birth.replace('Z', '+00:00')) if isinstance(date_of_birth, str) else date_of_birth
                if isinstance(birth_date, str):
                    birth_date = datetime.strptime(birth_date, '%Y-%m-%d')
                birth_chart = astrology_service.generate_birth_chart(birth_date, birth_country)
                astrology_insights = astrology_service.get_astrological_insights(birth_chart)
                astrology_data = {
                    'birth_chart': birth_chart,
                    'insights': astrology_insights
                }
            except Exception as e:
                print(f"Error generating astrology data for user {user_id}: {e}")
                astrology_data = {'error': str(e)}
        
        # Extract from nested future_self_description JSON
        future_self_description_data = user_data.get("future_self_description", {})
        future_self_description = str(future_self_description_data) if future_self_description_data else ""
        preferred_tone = user_data.get("preferred_tone", "")
        mind_space = future_self_description_data.get("mind_space", "") if isinstance(future_self_description_data, dict) else ""
        future_proud = future_self_description_data.get("future_proud", "") if isinstance(future_self_description_data, dict) else ""
        most_yourself = future_self_description_data.get("most_yourself", "") if isinstance(future_self_description_data, dict) else ""
        low_moments = future_self_description_data.get("low_moments", "") if isinstance(future_self_description_data, dict) else ""
        spiral_reminder = future_self_description_data.get("spiral_reminder", "") if isinstance(future_self_description_data, dict) else ""
        
        # Growth and challenges data from nested JSON
        change_goal = future_self_description_data.get("change_goal", "") if isinstance(future_self_description_data, dict) else ""
        avoid_tendency = future_self_description_data.get("avoid_tendency", "") if isinstance(future_self_description_data, dict) else ""
        feeling_description = future_self_description_data.get("feeling_description", "") if isinstance(future_self_description_data, dict) else ""
        
        # Future vision data from nested JSON
        future_description = future_self_description_data.get("future_description", "") if isinstance(future_self_description_data, dict) else ""
        future_age = str(user_data.get("future_self_age_years", ""))  # Changed from "future_age" to "future_self_age_years"
        typical_day = future_self_description_data.get("typical_day", "") if isinstance(future_self_description_data, dict) else ""
        accomplishment = future_self_description_data.get("accomplishment", "") if isinstance(future_self_description_data, dict) else ""
        
        # Communication style data from nested JSON
        words_slang = communication_style.get("words_slang", "") if isinstance(communication_style, dict) else ""
        message_preference = communication_style.get("message_preference", "") if isinstance(communication_style, dict) else ""
        messaging_frequency = communication_style.get("messaging_frequency", "") if isinstance(communication_style, dict) else ""
        emoji_usage_preference = communication_style.get("emoji_usage_preference", "") if isinstance(communication_style, dict) else ""
        preferred_communication = user_data.get("preferred_communication", "")
        communication_tone = communication_style.get("communication_tone", "") if isinstance(communication_style, dict) else ""
        message_length = communication_style.get("message_length", "") if isinstance(communication_style, dict) else ""
        emoji_usage = communication_style.get("emoji_usage", 0) if isinstance(communication_style, dict) else 0
        punctuation_style = communication_style.get("punctuation_style", "") if isinstance(communication_style, dict) else ""
        use_slang = communication_style.get("use_slang", False) if isinstance(communication_style, dict) else False
        chat_sample = communication_style.get("chat_sample", "") if isinstance(communication_style, dict) else ""
        common_phrases = communication_style.get("common_phrases", "") if isinstance(communication_style, dict) else ""

        if profile_response.data:
            # Merge all onboarding data with existing profile
            profile = profile_response.data[0]
            profile["communication_style"] = communication_style
            profile["user_name"] = user_name
            profile["nationality"] = nationality
            profile["birth_country"] = birth_country
            profile["date_of_birth"] = date_of_birth
            profile["current_location"] = current_location
            profile["astrology_data"] = astrology_data
            
            # Add personal reflection data
            profile["future_self_description"] = future_self_description
            profile["preferred_tone"] = preferred_tone
            profile["mind_space"] = mind_space
            profile["future_proud"] = future_proud
            profile["most_yourself"] = most_yourself
            profile["low_moments"] = low_moments
            profile["spiral_reminder"] = spiral_reminder
            
            # Add growth and challenges data
            profile["change_goal"] = change_goal
            profile["avoid_tendency"] = avoid_tendency
            profile["feeling_description"] = feeling_description
            
            # Add future vision data
            profile["future_description"] = future_description
            profile["future_age"] = future_age
            profile["typical_day"] = typical_day
            profile["accomplishment"] = accomplishment
            
            # Add communication style data
            profile["words_slang"] = words_slang
            profile["message_preference"] = message_preference
            profile["messaging_frequency"] = messaging_frequency
            profile["emoji_usage_preference"] = emoji_usage_preference
            profile["preferred_communication"] = preferred_communication
            profile["communication_tone"] = communication_tone
            profile["message_length"] = message_length
            profile["emoji_usage"] = emoji_usage
            profile["punctuation_style"] = punctuation_style
            profile["use_slang"] = use_slang
            profile["chat_sample"] = chat_sample
            profile["common_phrases"] = common_phrases
            
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
                profile["birth_country"] = birth_country
                profile["date_of_birth"] = date_of_birth
                profile["current_location"] = current_location
                profile["astrology_data"] = astrology_data
                             
                # Add all onboarding data to profile
                profile["future_self_description"] = future_self_description
                profile["preferred_tone"] = preferred_tone
                profile["mind_space"] = mind_space
                profile["future_proud"] = future_proud
                profile["most_yourself"] = most_yourself
                profile["low_moments"] = low_moments
                profile["spiral_reminder"] = spiral_reminder
                profile["change_goal"] = change_goal
                profile["avoid_tendency"] = avoid_tendency
                profile["feeling_description"] = feeling_description
                profile["future_description"] = future_description
                profile["future_age"] = future_age
                profile["typical_day"] = typical_day
                profile["accomplishment"] = accomplishment
                profile["words_slang"] = words_slang
                profile["message_preference"] = message_preference
                profile["messaging_frequency"] = messaging_frequency
                profile["emoji_usage_preference"] = emoji_usage_preference
                profile["preferred_communication"] = preferred_communication
                profile["communication_tone"] = communication_tone
                profile["message_length"] = message_length
                profile["emoji_usage"] = emoji_usage
                profile["punctuation_style"] = punctuation_style
                profile["use_slang"] = use_slang
                profile["chat_sample"] = chat_sample
                profile["common_phrases"] = common_phrases
                
                return profile
            else:
                print(f"Failed to create default profile for user {user_id}")
                # Add all onboarding data to default profile
                default_profile_data["communication_style"] = communication_style
                default_profile_data["user_name"] = user_name
                default_profile_data["nationality"] = nationality
                default_profile_data["birth_country"] = birth_country
                default_profile_data["date_of_birth"] = date_of_birth
                default_profile_data["current_location"] = current_location
                default_profile_data["astrology_data"] = astrology_data
                default_profile_data["future_self_description"] = future_self_description
                default_profile_data["preferred_tone"] = preferred_tone
                default_profile_data["mind_space"] = mind_space
                default_profile_data["future_proud"] = future_proud
                default_profile_data["most_yourself"] = most_yourself
                default_profile_data["low_moments"] = low_moments
                default_profile_data["spiral_reminder"] = spiral_reminder
                default_profile_data["change_goal"] = change_goal
                default_profile_data["avoid_tendency"] = avoid_tendency
                default_profile_data["feeling_description"] = feeling_description
                default_profile_data["future_description"] = future_description
                default_profile_data["future_age"] = future_age
                default_profile_data["typical_day"] = typical_day
                default_profile_data["accomplishment"] = accomplishment
                default_profile_data["words_slang"] = words_slang
                default_profile_data["message_preference"] = message_preference
                default_profile_data["messaging_frequency"] = messaging_frequency
                default_profile_data["emoji_usage_preference"] = emoji_usage_preference
                default_profile_data["preferred_communication"] = preferred_communication
                default_profile_data["communication_tone"] = communication_tone
                default_profile_data["message_length"] = message_length
                default_profile_data["emoji_usage"] = emoji_usage
                default_profile_data["punctuation_style"] = punctuation_style
                default_profile_data["use_slang"] = use_slang
                default_profile_data["chat_sample"] = chat_sample
                default_profile_data["common_phrases"] = common_phrases
                
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

    # 4. Get conversation context for natural flow
    conversation_context = await get_conversation_context(user_id, supabase)
    
    # 5. Generate weather and events context if location is available
    weather_events_context = {}
    current_location = user_profile.get('current_location', '')
    if current_location:
        try:
            weather_service = WeatherEventsService()
            weather_events_context = await weather_service.get_location_context(current_location)
            print(f"Generated weather/events context for {current_location}")
        except Exception as e:
            print(f"Error generating weather/events context: {e}")
            weather_events_context = {}
    
    # 6. Create natural future self prompt with weather/events context
    prompt = create_future_self_prompt(user_message, user_profile, conversation_context, weather_events_context)

    print(f"Generated natural conversation prompt for Ollama:\n{prompt}")

    # 5. Call Ollama (Mistral AI)
    ollama_url = os.environ.get("OLLAMA_API_URL", "http://localhost:11434/api/generate")
    ollama_model = os.environ.get("OLLAMA_MODEL", "mistral:7b")

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
    uvicorn.run(app, host="0.0.0.0", port=8888)