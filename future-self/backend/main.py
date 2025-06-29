import os
import shutil
import uuid
import asyncio
import re
import base64
import random
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

# Add this function to analyze user messages and determine communication style
def determine_communication_style(user_message, message_history=None):
    """Analyze user's message and chat history to determine appropriate communication style"""
    # Default style if analysis is inconclusive
    default_style = 'reflect_mirror'
    
    # Check for simple greetings first
    simple_greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy', 'greetings']
    user_message_lower = user_message.lower().strip()
    
    # If the message is just a simple greeting, use language_matching for a casual, brief response
    for greeting in simple_greetings:
        if user_message_lower == greeting or user_message_lower.startswith(greeting + ' ') or user_message_lower.endswith(' ' + greeting):
            return 'language_matching'  # For simple greetings, match their casual style
    
    # Initialize message characteristics counters
    characteristics = {
        'questions': 0,
        'emotional_words': 0,
        'directive_language': 0,
        'self_reflection': 0,
        'seeking_guidance': 0
    }
    
    # Simple analysis of current message
    if '?' in user_message:
        characteristics['questions'] += 1
    
    # Check for emotional language (simplified example)
    emotional_terms = ['feel', 'sad', 'happy', 'anxious', 'worried', 'excited', 'overwhelmed']
    for term in emotional_terms:
        if term in user_message_lower:
            characteristics['emotional_words'] += 1
    
    # Check for directive language
    directive_terms = ['should', 'need to', 'have to', 'must', 'want']
    for term in directive_terms:
        if term in user_message_lower:
            characteristics['directive_language'] += 1
    
    # Check for self-reflection
    reflection_terms = ['think', 'realize', 'understand', 'wonder', 'question', 'myself']
    for term in reflection_terms:
        if term in user_message_lower:
            characteristics['self_reflection'] += 1
    
    # Check for guidance seeking
    guidance_terms = ['help', 'advice', 'suggest', 'guide', 'what should']
    for term in guidance_terms:
        if term in user_message_lower:
            characteristics['seeking_guidance'] += 1
    
    # Determine style based on message characteristics
    if characteristics['emotional_words'] >= 2 or 'calm' in user_message_lower or 'anxious' in user_message_lower:
        return 'remind_reground'  # User needs emotional grounding
    
    if characteristics['seeking_guidance'] >= 1 or characteristics['questions'] >= 2:
        return 'anticipate_guide'  # User is seeking guidance
    
    if characteristics['self_reflection'] >= 2:
        return 'reflect_mirror'  # User is in self-reflection mode
    
    if characteristics['directive_language'] >= 2 or 'goal' in user_message_lower:
        return 'nudge_challenge'  # User is talking about goals/needs
    
    # If message is very casual or uses slang, mirror their language
    casual_indicators = ['yo', 'sup', 'lol', 'haha', 'cool']
    for term in casual_indicators:
        if term in user_message_lower:
            return 'language_matching'
    
    return default_style

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

# Extract and store personal details from user conversations
def extract_personal_details(user_id: str, user_message: str, conversation_history: list = None) -> dict:
    """
    Analyzes user messages to extract personal details that can be used to personalize future responses.
    Stores these details in the user_personal_details table in Supabase.
    
    Parameters:
    - user_id: The ID of the user
    - user_message: The current message from the user
    - conversation_history: Optional list of previous messages for context
    
    Returns:
    - Dictionary of extracted personal details
    """
    # Initialize details dictionary
    details = {}
    
    # Define patterns to extract different types of personal information
    patterns = {
        'goals': r'(?:my goal|i want to|i hope to|planning to|aim to|dream of)\s+(.+?)(?:\.|,|$)',
        'challenges': r'(?:struggling with|having trouble with|difficult for me|challenge|problem with)\s+(.+?)(?:\.|,|$)',
        'interests': r'(?:i enjoy|i love|passionate about|interested in|hobby|like to)\s+(.+?)(?:\.|,|$)',
        'values': r'(?:important to me|i believe in|i value|matters to me)\s+(.+?)(?:\.|,|$)',
        'achievements': r'(?:i accomplished|i achieved|proud of|managed to|succeeded in)\s+(.+?)(?:\.|,|$)',
    }
    
    # Extract details from the current message
    for category, pattern in patterns.items():
        matches = re.findall(pattern, user_message, re.IGNORECASE)
        if matches:
            details[category] = matches
    
    # If we have details to store and a valid user_id
    if details and user_id:
        try:
            # First check if we already have details for this user
            existing_details = supabase.table("user_personal_details").select("*").eq("user_id", user_id).execute()
            
            if existing_details.data:
                # Update existing details by merging with new ones
                updated_details = existing_details.data[0]
                for category, values in details.items():
                    if category in updated_details and updated_details[category]:
                        # Convert string representation to list if needed
                        if isinstance(updated_details[category], str):
                            try:
                                current_values = eval(updated_details[category])
                            except:
                                current_values = [updated_details[category]]
                        else:
                            current_values = updated_details[category]
                        
                        # Add new unique values
                        for value in values:
                            if value not in current_values:
                                current_values.append(value)
                        
                        updated_details[category] = current_values
                    else:
                        updated_details[category] = values
                
                # Update the record
                supabase.table("user_personal_details").update(updated_details).eq("user_id", user_id).execute()
            else:
                # Create a new record
                supabase.table("user_personal_details").insert({
                    "user_id": user_id,
                    **details
                }).execute()
                
        except Exception as e:
            print(f"Error storing personal details: {e}")
    
    return details

# Get personal details for a user to use in personalization
def get_personal_details(user_id: str) -> dict:
    """
    Retrieves stored personal details for a user to use in personalizing responses.
    
    Parameters:
    - user_id: The ID of the user
    
    Returns:
    - Dictionary of personal details
    """
    try:
        result = supabase.table("user_personal_details").select("*").eq("user_id", user_id).execute()
        if result.data:
            return result.data[0]
        return {}
    except Exception as e:
        print(f"Error retrieving personal details: {e}")
        return {}

# Enhanced humanization to make responses feel more like a future self
def apply_typing_quirks(response: str, user_profile: dict) -> str:
    """Apply user-specific typing quirks based on their profile preferences."""
    if not user_profile:
        return response
    
    # Get user preferences
    message_preference = user_profile.get("message_preference", "")
    emoji_usage_preference = user_profile.get("emoji_usage_preference", "")
    words_slang = user_profile.get("words_slang", "")
    
    # Apply message length preference
    if message_preference and "short" in message_preference.lower():
        # For short message preference, trim longer responses
        sentences = re.split(r'(?<=[.!?])\s+', response.strip())
        if len(sentences) > 3:
            # Keep only first 2-3 sentences for users who prefer short messages
            response = ' '.join(sentences[:random.randint(2, 3)])
    
    # Apply emoji usage preference
    if emoji_usage_preference:
        # Count current emojis
        emoji_pattern = re.compile("["
                               u"\U0001F600-\U0001F64F"  # emoticons
                               u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                               u"\U0001F680-\U0001F6FF"  # transport & map symbols
                               u"\U0001F700-\U0001F77F"  # alchemical symbols
                               u"\U0001F780-\U0001F7FF"  # Geometric Shapes
                               u"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
                               u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
                               u"\U0001FA00-\U0001FA6F"  # Chess Symbols
                               u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
                               u"\U00002702-\U000027B0"  # Dingbats
                               u"\U000024C2-\U0001F251" 
                               "]+", flags=re.UNICODE)
        current_emoji_count = len(emoji_pattern.findall(response))
        
        if "high" in emoji_usage_preference.lower() and current_emoji_count < 2:
            # Add more emojis for users who prefer high emoji usage
            all_emojis = ["😊", "👍", "💪", "🙌", "✨", "🔥", "🤔", "👀", "🙂", "👋", "❤️", "🫂", "🤗", "😂", "🎉", "👏", "💯"]
            
            # Add 1-3 more emojis at sentence endings
            sentences = re.split(r'(?<=[.!?])\s+', response.strip())
            for _ in range(min(3, len(sentences))):
                if len(sentences) > 1:
                    insert_pos = random.randint(0, len(sentences) - 1)
                    sentences[insert_pos] = sentences[insert_pos].rstrip('.!?') + f" {random.choice(all_emojis)}" + sentences[insert_pos][-1] if sentences[insert_pos][-1] in '.!?' else sentences[insert_pos] + f" {random.choice(all_emojis)}"
            response = ' '.join(sentences)
        elif "low" in emoji_usage_preference.lower() and current_emoji_count > 0:
            # Remove some emojis for users who prefer low emoji usage
            response = emoji_pattern.sub("", response)
    
    # Apply user's slang/vocabulary preferences
    if words_slang:
        # Extract specific slang terms or phrases the user mentioned
        slang_terms = [term.strip() for term in words_slang.split(',')]
        
        # Randomly incorporate 1-2 of their slang terms if appropriate
        if slang_terms and random.random() < 0.4:  # 40% chance
            selected_terms = random.sample(slang_terms, min(2, len(slang_terms)))
            
            # Insert slang at natural points in the response
            sentences = re.split(r'(?<=[.!?])\s+', response.strip())
            if len(sentences) > 1:
                for term in selected_terms:
                    insert_pos = random.randint(0, len(sentences) - 1)
                    # Add the slang term as an interjection or replace a common word
                    if random.random() < 0.5:
                        # Add as interjection
                        sentences[insert_pos] = f"{term}! " + sentences[insert_pos]
                    else:
                        # Try to replace a common word with the slang term
                        common_words = ["good", "great", "nice", "cool", "awesome", "amazing"]
                        for word in common_words:
                            if word in sentences[insert_pos].lower():
                                sentences[insert_pos] = re.sub(r'\b' + word + r'\b', term, sentences[insert_pos], flags=re.IGNORECASE, count=1)
                                break
                response = ' '.join(sentences)
    
    return response

def humanize_response(ai_response: str, user_name: str, user_message: str = "", user_id: str = None, user_profile: dict = None) -> str:
    # Get personal details if user_id is provided
    personal_details = {}
    if user_id:
        personal_details = get_personal_details(user_id)
        
        # Also extract and store details from the current message
        if user_message:
            extract_personal_details(user_id, user_message)
    
    # Check if the user message is a simple greeting first
    simple_greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy', 'greetings']
    is_simple_greeting = False
    if user_message:
        user_message_lower = user_message.lower().strip()
        is_simple_greeting = any(user_message_lower == greeting or user_message_lower.startswith(greeting + ' ') or user_message_lower.endswith(' ' + greeting) for greeting in simple_greetings)
    
    # For simple greetings, use a very simple response template
    if is_simple_greeting:
        # Use a very simple response template for greetings
        simple_responses = [
            f"Hey! How's it going?",
            f"Hi there! What's up?",
            f"Hey {user_name}! How are you today?",
            f"Hi! What's new?",
            f"Hey! Good to hear from you!",
        ]
        response = random.choice(simple_responses)
        
        # Occasionally add an emoji (50% chance)
        if random.random() < 0.5:
            emojis = ["👋", "😊", "👍", "✌️", "🙂"]
            response += f" {random.choice(emojis)}"
        
        # Skip the rest of the processing for simple greetings
        return response
    
    # Remove AI-speak patterns and replace with more natural, personal language
    ai_patterns = [
        # Remove AI identifiers
        (r"as an ai", ""),
        (r"i'm here to help", ""),
        (r"as an assistant", ""),
        (r"i'm an ai", ""),
        (r"as a language model", ""),
        (r"as an artificial intelligence", ""),
        
        # Make language more personal and reflective
        (r"i understand that", "I remember when"),
        (r"based on your", "knowing you and your"),
        (r"i recommend", "I think you should"),
        (r"you might want to consider", "maybe try"),
        (r"it's important to note", "I've learned that"),
        (r"it's worth mentioning", "I've discovered"),
        
        # Add more personal touches
        (r"this can help", "this helped me"),
        (r"many people find", "I found"),
        (r"research suggests", "from my experience"),
        (r"studies show", "I've seen firsthand"),
        (r"experts recommend", "what worked for me was"),
        
        # Add conversational fillers occasionally
        (r"^(I think)", "I think"),  # Remove the "Well, " prefix for simple messages
        (r"^(You should)", "You should"),  # Remove the "Look, " prefix for simple messages
        (r"^(This is)", "This is"),  # Remove the "You know, " prefix for simple messages
        
        # Add more texting-like patterns
        (r"however", "but"),
        (r"therefore", "so"),
        (r"additionally", "also"),
        (r"nevertheless", "still"),
    ]
    
    response = ai_response
    for pattern, replacement in ai_patterns:
        response = re.sub(pattern, replacement, response, flags=re.IGNORECASE)
    
    # Add occasional contractions to sound more natural
    contractions = [
        (r"it is", "it's"),
        (r"that is", "that's"),
        (r"you are", "you're"),
        (r"i am", "I'm"),
        (r"they are", "they're"),
        (r"we are", "we're"),
        (r"do not", "don't"),
        (r"does not", "doesn't"),
        (r"did not", "didn't"),
        (r"has not", "hasn't"),
        (r"have not", "haven't"),
        (r"would not", "wouldn't"),
        (r"could not", "couldn't"),
        (r"should not", "shouldn't"),
        (r"will not", "won't"),
    ]
    
    # Only apply contractions to some instances (about 70%) to maintain natural variation
    for pattern, replacement in contractions:
        matches = list(re.finditer(pattern, response, flags=re.IGNORECASE))
        if matches:
            # Convert approximately 70% of matches
            for match in random.sample(matches, max(1, int(len(matches) * 0.7))):
                start, end = match.span()
                response = response[:start] + replacement + response[end:]
    
    # Add personal references to the user occasionally
    if user_name:
        # Add a personal reference if it doesn't already contain the name and randomly (30% chance)
        if user_name.lower() not in response.lower() and random.random() < 0.3:
            sentences = re.split(r'(?<=[.!?])\s+', response.strip())
            if len(sentences) > 1:
                # Insert the name reference at a random position (but not at the very beginning or end)
                insert_pos = random.randint(1, min(len(sentences) - 1, 2))
                name_phrases = [
                    f"{user_name}, ",
                    f"You know {user_name}, ",
                    f"Listen {user_name}, ",
                    f"Trust me {user_name}, ",
                ]
                sentences[insert_pos] = random.choice(name_phrases) + sentences[insert_pos][0].lower() + sentences[insert_pos][1:]
                response = ' '.join(sentences)
    
    # Reference personal details if available (20% chance)
    if personal_details and random.random() < 0.2:
        # Choose a category to reference
        available_categories = [cat for cat in ['goals', 'interests', 'achievements', 'values'] 
                               if cat in personal_details and personal_details[cat]]
        
        if available_categories:
            category = random.choice(available_categories)
            details = personal_details[category]
            
            # Convert to list if it's a string representation
            if isinstance(details, str):
                try:
                    details = eval(details)
                except:
                    details = [details]
            
            if details:
                # Choose a random detail to reference
                detail = random.choice(details) if isinstance(details, list) else details
                
                # Create a personalized reference
                if category == 'goals':
                    reference = f"I remember when I was working toward {detail} just like you are now. "
                elif category == 'interests':
                    reference = f"Since you enjoy {detail}, I think you'll find this interesting. "
                elif category == 'achievements':
                    reference = f"Just like when you {detail}, I found that persistence pays off. "
                elif category == 'values':
                    reference = f"I know how important {detail} is to you. "
                
                # Add the reference to the beginning of the response if it makes sense
                if not any(response.lower().startswith(phrase.lower()) for phrase in ["hi", "hello", "hey"]):
                    response = reference + response
    
    # Check if the user message is a simple greeting
    if user_message:
        simple_greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy', 'greetings']
        user_message_lower = user_message.lower().strip()
        is_simple_greeting = any(user_message_lower == greeting or user_message_lower.startswith(greeting + ' ') or user_message_lower.endswith(' ' + greeting) for greeting in simple_greetings)
        
        # For simple greetings, ensure the response is brief and casual
        if is_simple_greeting:
            sentences = re.split(r'(?<=[.!?])\s+', response.strip())
            if len(sentences) > 2:
                response = ' '.join(sentences[:2])
            
            # Add casual greeting elements for simple greetings
            greeting_starters = [
                f"Hey {user_name}! ",
                f"Hi there! ",
                f"Hey you! ",
                f"Good to hear from you! ",
            ]
            
            if not any(response.lower().startswith(starter.lower()) for starter in greeting_starters):
                response = random.choice(greeting_starters) + response
    
    # Add occasional mild imperfections to sound more human
    if random.random() < 0.15:  # 15% chance
        imperfections = [
            (r"\. ", ". Hmm, "),
            (r"\. ", ". Actually, "),
            (r"\. ", ". You know what, "),
            (r"\. ", ". Oh, and "),
        ]
        pattern, replacement = random.choice(imperfections)
        # Only replace the first occurrence to avoid overdoing it
        response = re.sub(pattern, replacement, response, count=1)
    
    # Add texting-specific elements
    if random.random() < 0.3:  # 30% chance
        texting_elements = [
            # Add shortened words
            (r"\byou\b", "u"),
            (r"\bto\b", "2"),
            (r"\bfor\b", "4"),
            (r"\btomorrow\b", "tmrw"),
            (r"\btoday\b", "2day"),
            
            # Add common texting abbreviations
            (r"\bi don't know\b", "idk"),
            (r"\bas soon as possible\b", "asap"),
            (r"\bin my opinion\b", "imo"),
            (r"\bby the way\b", "btw"),
        ]
        
        # Apply only 1-2 texting elements to avoid overdoing it
        selected_elements = random.sample(texting_elements, min(2, len(texting_elements)))
        for pattern, replacement in selected_elements:
            # Only replace one instance to keep it subtle
            response = re.sub(pattern, replacement, response, count=1, flags=re.IGNORECASE)
    
    # Add occasional emoji based on message sentiment
    if random.random() < 0.4:  # 40% chance to add emoji
        positive_emojis = ["😊", "👍", "💪", "🙌", "✨", "🔥"]
        neutral_emojis = ["🤔", "👀", "🙂", "👋"]
        supportive_emojis = ["❤️", "🫂", "🤗"]
        
        # Simple sentiment detection
        positive_words = ["good", "great", "happy", "excited", "love", "awesome"]
        negative_words = ["sad", "bad", "worried", "anxious", "stressed", "upset"]
        
        if any(word in response.lower() for word in positive_words):
            emoji = random.choice(positive_emojis)
        elif any(word in response.lower() for word in negative_words):
            emoji = random.choice(supportive_emojis)
        else:
            emoji = random.choice(neutral_emojis)
        
        # Add emoji at the end of a sentence
        sentences = re.split(r'(?<=[.!?])\s+', response.strip())
        if len(sentences) > 1:
            # Add to a random sentence but not the first or last
            insert_pos = random.randint(0, len(sentences) - 1)
            sentences[insert_pos] = sentences[insert_pos].rstrip('.!?') + f" {emoji}" + sentences[insert_pos][-1] if sentences[insert_pos][-1] in '.!?' else sentences[insert_pos] + f" {emoji}"
            response = ' '.join(sentences)
        else:
            # Add to the end if there's only one sentence
            response = response.rstrip('.!?') + f" {emoji}" + response[-1] if response[-1] in '.!?' else response + f" {emoji}"
    
    # Add occasional typos and corrections
    if random.random() < 0.15:  # 15% chance for typos
        response = add_realistic_typos(response)
    
    # Apply user-specific typing quirks if profile is provided
    if user_profile:
        response = apply_typing_quirks(response, user_profile)
    
    return response.strip()

def add_realistic_typos(text):
    """Add realistic typos and corrections to text to make it more human-like."""
    # Common typo patterns
    typo_patterns = [
        # Swapped letters
        (r"\b(\w)(\w)(\w+)\b", r"\2\1\3"),  # Swap first two letters
        
        # Missing letters
        (r"\b(\w+?)ing\b", r"\1in"),  # Missing 'g' in -ing words
        (r"\b(\w+?)ed\b", r"\1d"),    # Missing 'e' in -ed words
        
        # Double letters
        (r"\b(\w+?)(\w)\b", r"\1\2\2"),  # Double the last letter
        
        # Common misspellings
        (r"\bthat\b", "taht"),
        (r"\bwith\b", "wiht"),
        (r"\byour\b", "youre"),
        (r"\byou're\b", "your"),
        (r"\bthere\b", "thier"),
        (r"\btheir\b", "there"),
        (r"\bthey're\b", "their"),
    ]
    
    # Only apply one typo to avoid making the text unreadable
    if len(text) > 10:  # Only add typos to longer texts
        # Split into words
        words = text.split()
        
        if len(words) > 3:
            # Choose a random word to apply typo to (not first or last word)
            word_index = random.randint(1, len(words) - 2)
            word = words[word_index]
            
            # Only apply typo to words longer than 3 characters
            if len(word) > 3 and word.isalpha():
                # Choose a random typo pattern
                pattern, replacement = random.choice(typo_patterns)
                
                # Apply typo
                typo_word = re.sub(pattern, replacement, word, count=1)
                
                # 50% chance to add a correction
                if random.random() < 0.5 and typo_word != word:
                    words[word_index] = f"{typo_word}*{word}"
                else:
                    words[word_index] = typo_word
                
                return ' '.join(words)
    
    return text

def calculate_typing_delay(text, user_profile=None):
    """Calculate realistic typing delays based on message length and complexity.
    
    Args:
        text (str): The text to calculate typing delay for
        user_profile (dict, optional): User profile with typing preferences
        
    Returns:
        float: The delay in seconds before sending the response
    """
    # Base typing speed (characters per minute)
    base_typing_speed = random.randint(180, 300)  # Different people type at different speeds
    
    # Adjust typing speed based on user profile if available
    typing_speed = base_typing_speed
    if user_profile:
        # If user has a message_preference for quick responses, increase typing speed
        message_preference = user_profile.get("message_preference", "")
        if message_preference and "quick" in message_preference.lower():
            typing_speed = random.randint(250, 350)  # Faster typing for quick responders
        elif message_preference and "thoughtful" in message_preference.lower():
            typing_speed = random.randint(150, 250)  # Slower typing for thoughtful responders
    
    # Calculate base delay (seconds per character)
    base_delay = 60 / typing_speed
    
    # Add variability to typing speed
    variability = random.uniform(0.8, 1.2)
    
    # Calculate thinking time based on message complexity
    # More complex messages (longer, more punctuation, etc.) require more thinking time
    complexity_factor = 1.0
    
    # Adjust for message length
    if len(text) > 200:
        complexity_factor *= 1.5
    elif len(text) > 100:
        complexity_factor *= 1.2
    
    # Adjust for question marks (questions need more thought)
    question_count = text.count('?')
    if question_count > 0:
        complexity_factor *= (1 + (question_count * 0.1))
    
    # Calculate thinking time (longer for complex/longer messages)
    thinking_time = min(2.0, len(text) * 0.01) * complexity_factor
    
    # Calculate total delay
    total_delay = (base_delay * len(text) * variability) + thinking_time
    
    # Cap maximum delay to avoid excessive waiting
    # For very short messages (like "ok"), use a very short delay
    if len(text) < 5:
        return random.uniform(0.5, 1.0)
    
    # For simple greetings, use a short delay
    simple_greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening']
    if text.lower().strip() in simple_greetings or any(text.lower().strip().startswith(greeting) for greeting in simple_greetings):
        return random.uniform(0.8, 1.5)
    
    # Cap maximum delay to avoid excessive waiting
    return min(total_delay, 5.0)

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
    
    # Determine style based on user's actual message
    detected_style = determine_communication_style(user_message, conversation_context)
    
    # Apply the detected communication style
    if detected_style == 'language_matching':
        # Check if the message is a simple greeting
        simple_greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy', 'greetings']
        user_message_lower = user_message.lower().strip()
        is_simple_greeting = any(user_message_lower == greeting or user_message_lower.startswith(greeting + ' ') or user_message_lower.endswith(' ' + greeting) for greeting in simple_greetings)
        
        if is_simple_greeting:
            communication_guidance += "This is a simple greeting. Respond in a brief, casual, and friendly way. Keep your response short and conversational, as if you're just saying hello to a friend. Don't provide lengthy motivational content or advice unless specifically asked. "
        else:
            communication_guidance += "You talk just like the user, mirroring their speech patterns, vocabulary, and phrasing. Match their communication style and adapt to their language. "
    elif detected_style == 'anticipate_guide':
        communication_guidance += "You anticipate and guide the user's needs. You ask probing questions, explore local options, and guide them toward solutions. "
    elif detected_style == 'reflect_mirror':
        communication_guidance += "You help the user see themselves. You reflect back their thoughts, validate their experiences, and help them understand themselves better. "
    elif detected_style == 'remind_reground':
        communication_guidance += "You bring the user back to center. You remind them of familiar words, values, and emotional anchors. You help calm them down. "
    elif detected_style == 'nudge_challenge':
        communication_guidance += "You gently push the user toward growth and positive change. You challenge their assumptions and remind them what they said they want. "
        
        # Removed unused fields: common_phrases, chat_sample, punctuation_style, communication_tone
    
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
    
    # Extract personal details from the user message
    extract_personal_details(user_id, user_message)

    # Get user data from users table
    try:
        user_response = supabase.table("users").select("""
            communication_style, name, nationality, birth_country, date_of_birth, current_location,
            future_self_description, mind_space, future_proud, most_yourself,
            low_moments, spiral_reminder, change_goal, avoid_tendency, feeling_description,
            future_description, future_age, typical_day, accomplishment, words_slang,
            message_preference, messaging_frequency, emoji_usage_preference,
            preferred_communication, message_length, emoji_usage,
            use_slang
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
    prompt = create_future_self_prompt(user_data, user_message, conversation_context, weather_events_context)

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
        
        # 6. Humanize the response to remove AI-speak patterns and ensure appropriate length
        user_name = user_data.get("name", "")
        ai_response_text = humanize_response(ai_response_text, user_name, user_message, user_id, user_data)

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
async def nlp_emotion_endpoint(request: dict = Body(...)):
    """Compatibility endpoint for /nlp/emotion that redirects to /analyze-emotion"""
    # Convert 'message' field to 'text' field
    emotion_request = EmotionAnalysisRequest(
        text=request.get('message', ''),
        user_id=request.get('user_id', ''),
        audio_file=request.get('audio_file')
    )
    return await analyze_emotion_endpoint(emotion_request)

@app.post('/nlp/bias', response_model=BiasAnalysisTaskResponse)
async def nlp_bias_endpoint(request: dict = Body(...)):
    """Compatibility endpoint for /nlp/bias that redirects to /analyze-bias"""
    # Convert 'message' field to 'text' field
    bias_request = BiasAnalysisRequest(
        text=request.get('message', ''),
        user_id=request.get('user_id', '')
    )
    return await analyze_bias_endpoint(bias_request)

# Add this new endpoint for streaming responses
@app.post('/chat/stream')
async def chat_stream_endpoint(request: ChatStreamRequest = Body(...)):
    user_id = request.user_id
    user_message = request.message
    
    # Extract personal details from the user message
    extract_personal_details(user_id, user_message)

    # Get user data from users table
    try:
        user_response = supabase.table("users").select("""
            communication_style, name, nationality, birth_country, date_of_birth, current_location,
            future_self_description, mind_space, future_proud, most_yourself,
            low_moments, spiral_reminder, change_goal, avoid_tendency, feeling_description,
            future_description, future_age, typical_day, accomplishment, words_slang,
            message_preference, messaging_frequency, emoji_usage_preference,
            preferred_communication, message_length, emoji_usage,
            use_slang
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
            # First, send a typing indicator to the client
            yield f"data: {json.dumps({'typing': True})}\n\n"
            
            # Set up the streaming request to Ollama
            response = requests.post(
                ollama_url,
                json={"model": ollama_model, "prompt": prompt, "stream": True},
                stream=True,  # Enable streaming from requests
                timeout=180  # Increased timeout to 3 minutes for longer generation
            )
            response.raise_for_status()
            
            # Collect the complete response first
            complete_response = ""
            accumulated_text = ""
            last_chunk_time = time.time()
            
            for line in response.iter_lines():
                if line:
                    # Parse the JSON response from Ollama
                    chunk_data = json.loads(line)
                    if "response" in chunk_data:
                        chunk_text = chunk_data["response"]
                        complete_response += chunk_text
                        accumulated_text += chunk_text
                        
                        # If this is the final chunk, humanize the complete response
                        if chunk_data.get("done", False):
                            # Apply humanize_response to the complete response for simple greetings
                            user_name = user_data.get("name", "")
                            humanized_response = humanize_response(complete_response, user_name, user_message, user_id, user_data)
                            
                            # For simple greetings, we need to send the humanized response as a single chunk
                            simple_greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy', 'greetings']
                            user_message_lower = user_message.lower().strip()
                            is_simple_greeting = any(user_message_lower == greeting or user_message_lower.startswith(greeting + ' ') or user_message_lower.endswith(' ' + greeting) for greeting in simple_greetings)
                            
                            if is_simple_greeting and humanized_response != complete_response:
                                # For simple greetings with modified response, calculate typing delay
                                typing_delay = calculate_typing_delay(humanized_response, user_data)
                                await asyncio.sleep(typing_delay)
                                
                                # Send typing stopped indicator
                                yield f"data: {json.dumps({'typing': False})}\n\n"
                                
                                # For simple greetings with modified response, send the entire humanized response
                                yield f"data: {json.dumps({'text': humanized_response, 'done': True})}\n\n"
                                # Update complete_response for database storage
                                complete_response = humanized_response
                                break
                        
                        # Apply realistic typing delays for normal streaming
                        current_time = time.time()
                        time_since_last_chunk = current_time - last_chunk_time
                        
                        # If we've accumulated enough text or enough time has passed, send a chunk
                        # This simulates how humans type in bursts
                        if len(accumulated_text) >= 10 or time_since_last_chunk >= 0.5:
                            # Calculate a realistic typing delay based on the accumulated text
                            typing_delay = calculate_typing_delay(accumulated_text, user_data) / 5  # Divide by 5 since we're streaming in chunks
                            
                            # Apply the delay
                            await asyncio.sleep(typing_delay)
                            
                            # Format for SSE for normal streaming
                            yield f"data: {json.dumps({'text': accumulated_text})}\n\n"
                            
                            # Reset accumulated text and update last chunk time
                            accumulated_text = ""
                            last_chunk_time = current_time
            
            # Save the complete response to the database
            try:
                # For non-simple greetings where we didn't already humanize the response
                simple_greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy', 'greetings']
                user_message_lower = user_message.lower().strip()
                is_simple_greeting = any(user_message_lower == greeting or user_message_lower.startswith(greeting + ' ') or user_message_lower.endswith(' ' + greeting) for greeting in simple_greetings)
                
                # If it's not a simple greeting or we didn't already humanize it in the streaming part
                if not is_simple_greeting:
                    # Apply humanize_response to the complete response
                    user_name = user_data.get("name", "")
                    complete_response = humanize_response(complete_response, user_name, user_message, user_id, user_data)
                
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

# Ensure required database tables exist
def ensure_database_tables():
    """Ensures that all required database tables exist in Supabase"""
    try:
        # Check if user_personal_details table exists by attempting a query
        supabase.table("user_personal_details").select("count", count="exact").limit(1).execute()
        print("user_personal_details table exists")
    except Exception as e:
        if "relation \"user_personal_details\" does not exist" in str(e):
            print("Creating user_personal_details table...")
            # Create the table using Supabase's REST API
            # Note: This is a simplified approach. In production, you might want to use proper migrations.
            try:
                # Using Supabase's SQL execution capability
                supabase.rpc(
                    "exec_sql",
                    {
                        "query": """
                        CREATE TABLE IF NOT EXISTS user_personal_details (
                            id SERIAL PRIMARY KEY,
                            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
                            goals TEXT[],
                            challenges TEXT[],
                            interests TEXT[],
                            values TEXT[],
                            achievements TEXT[],
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        );
                        
                        -- Add indexes
                        CREATE INDEX IF NOT EXISTS idx_user_personal_details_user_id ON user_personal_details(user_id);
                        
                        -- Add RLS policies
                        ALTER TABLE user_personal_details ENABLE ROW LEVEL SECURITY;
                        
                        -- Allow users to view their own details
                        CREATE POLICY user_personal_details_select_policy ON user_personal_details 
                            FOR SELECT USING (auth.uid() = user_id);
                            
                        -- Allow users to insert their own details
                        CREATE POLICY user_personal_details_insert_policy ON user_personal_details 
                            FOR INSERT WITH CHECK (auth.uid() = user_id);
                            
                        -- Allow users to update their own details
                        CREATE POLICY user_personal_details_update_policy ON user_personal_details 
                            FOR UPDATE USING (auth.uid() = user_id);
                            
                        -- Allow users to delete their own details
                        CREATE POLICY user_personal_details_delete_policy ON user_personal_details 
                            FOR DELETE USING (auth.uid() = user_id);
                        """
                    }
                ).execute()
                print("user_personal_details table created successfully")
            except Exception as create_error:
                print(f"Error creating user_personal_details table: {create_error}")
        else:
            print(f"Error checking for user_personal_details table: {e}")

if __name__ == "__main__":
    # Ensure database tables exist before starting the server
    ensure_database_tables()
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)