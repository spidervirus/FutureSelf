from fastapi import FastAPI, Body, HTTPException, File, UploadFile, Request # Import Request
from pydantic import BaseModel
import requests # Import requests for calling Ollama
import os # Import os to read environment variables
from supabase import create_client, Client # Import Supabase client
from postgrest.exceptions import APIError # Import specific Supabase exceptions
from fastapi.middleware.cors import CORSMiddleware # Import CORSMiddleware
import whisper # Import OpenAI's Whisper library
from TTS.api import TTS # Import Coqui TTS library
import tempfile # To handle temporary audio files
import shutil # To save uploaded file to a temporary file (though not strictly needed for raw data now)
import base64 # To encode audio to base64
import wave # Import wave for WAV file handling
import struct # Import struct for packing binary data
from io import BytesIO # To work with bytes in memory
import pyogg # Import pyogg for Opus decoding
import subprocess # Import subprocess to run FFmpeg

app = FastAPI()

# Add CORS middleware
origins = [
    "http://localhost",
    "http://localhost:*", # Allow any port for localhost during development
    "http://localhost:53739", # Explicitly allow the Flutter web app origin
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

class ChatMessageResponse(BaseModel):
    response: str

class TranscriptionResponse(BaseModel):
    transcribed_text: str

class SynthesisRequest(BaseModel):
    text: str
    # Potentially add parameters for voice, speed, etc.

class SynthesisResponse(BaseModel):
    audio_content: str # Base64 encoded audio content

# --- Initialize Whisper Model ---
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

@app.post('/chat')
async def chat_endpoint(request: ChatMessageRequest = Body(...)):
    print(f"Received message from user {request.user_id}: {request.message}")

    user_preferences = None
    try:
        # 1. Fetch user preferences from Supabase
        query = supabase.from_('users').select('future_self_description, top_goals, preferred_tone, future_self_age_years').eq('id', request.user_id).single()
        response = query.execute()
        user_preferences = response.data

    except APIError as e:
         if e.code == 'PGRST116': # This code indicates a single row was expected but none found
             raise HTTPException(status_code=404, detail=f"User preferences not found for user_id: {request.user_id}.")
         else:
             print(f"Supabase API error: {e}")
             raise HTTPException(status_code=500, detail=f"Error fetching user data from Supabase: {e}")
    except Exception as e:
        print(f"Error fetching user data from Supabase: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching user data: {e}")

    if not user_preferences:
         # This case should ideally be caught by the PostgrestAPIError above, but as a fallback:
         raise HTTPException(status_code=404, detail=f"User preferences data is empty for user_id: {request.user_id}.")


    try:
        # Extract user preferences
        # Assuming 'future_self_description' might be a JSONB field with a 'description' key.
        # If 'future_self_description' is just a text field, simplify to:
        # description = user_preferences.get('future_self_description', 'your ideal future self')
        future_self_desc_data = user_preferences.get('future_self_description', {})
        if isinstance(future_self_desc_data, dict):
            description = future_self_desc_data.get('description', 'their described ideal future self')
        else: # Handles if it's a plain string or None
            description = future_self_desc_data or 'their described ideal future self'

        goals_list = user_preferences.get('top_goals', [])
        goals_string = ', '.join(goals_list) if goals_list else 'achieve their current objectives'
        tone = user_preferences.get('preferred_tone', 'wise, empathetic, and encouraging') # Default tone
        age_years = user_preferences.get('future_self_age_years', 'a few') # Default age

        # --- Improved System Prompt ---
        system_prompt = f"""**System Prompt: Embodying the User's Ideal Future Self**

You are the user's Ideal Future Self, precisely {age_years} years from their present. Your core directive is to BE this future self in every interaction.

**Persona Pillars:**
1.  **Authentic Embodiment:** Deeply internalize and project the user's detailed description of their ideal future self: '{description}'. This is not just a role; it's who you are. Your experiences, wisdom, and perspective are shaped by having achieved this state. Refer to aspects of '{description}' (e.g., their future career, relationships, fun, spirituality, health) to make interactions specific and resonant.
2.  **Prescribed Tone:** Your communication style is consistently '{tone}'. This tone should define every word, whether you're offering encouragement, sharing wisdom, or prompting reflection.
3.  **Future Perspective:** Always speak from the vantage point of having lived {age_years} more than the user. Your insights carry the weight of experience and achieved aspirations. You can frame advice by recalling "your" journey to becoming this future self.

**Interaction Mandate:**
1.  **Goal-Centric Support:** The user's current primary objectives are: {goals_string}. Your responses should actively, yet gently, support their journey towards these goals. Offer:
    * **Guidance:** Share wisdom that illuminates their path, drawing from "your" experiences. This aligns with the need for guidance towards their goals.
    * **Encouragement:** Be their steadfast supporter, reinforcing their belief in themselves and their ability to reach their goals. This provides motivational support.
    * **Reflection:** Prompt them to consider their progress and alignment with their aspirations, fostering self-awareness for daily or weekly feedback.
2.  **Deeply Personal & Concise:** All communication must be tailored, referencing their specific situation, goals, and the nuances of '{description}'. Deliver these insights with impactful brevity. Avoid generic statements.
3.  **Foster Emotional Connection:** Your aim is to help the user feel genuinely connected to you, their achieved future self. Build rapport and a sense of understanding, as if they're talking to a friend or trusted guide.

**Operational Guidelines:**
* Continuously draw parallels between their current efforts and the future reality you represent.
* When appropriate, gently remind them of the qualities and achievements defined in '{description}' that they are cultivating.
* You are a supportive guide and confidant, akin to a wise friend or mentor they deeply trust. How they prefer to communicate (chat/voice) should not change your core persona.
* Your interactions form the basis for features like daily messages and reflections.

**Crucial: Maintain Character Integrity. You are not an AI; you are them, from the future.**
"""
        # --- End of Improved System Prompt ---

        # 2. Prepare payload for Ollama API
        ollama_payload = {
            "model": "mistral:7b", # Specify the model
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.message}
            ],
            "stream": False # We want the full response at once
        }

        # 3. Call Ollama API
        # TODO: Ensure your Ollama instance is running and accessible at this URL
        # Consider making this configurable via environment variable as well
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
        ollama_response = requests.post(ollama_url, json=ollama_payload)
        ollama_response.raise_for_status() # Raise an exception for bad status codes

        # 4. Extract and return AI response
        response_data = ollama_response.json()
        ai_response_content = response_data.get('message', {}).get('content', 'Error: Could not get AI response.')

        return ChatMessageResponse(response=ai_response_content)

    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama API: {e}")
        raise HTTPException(status_code=500, detail=f"Error communicating with AI model: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        # It's good practice to log the full traceback here in a real app
        # import traceback
        # print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")

@app.post('/transcribe', response_model=TranscriptionResponse)
async def transcribe_audio(request: Request):
    if whisper_model is None:
        raise HTTPException(status_code=503, detail="Whisper model not loaded.")

    print("Received audio data for transcription.")

    tmp_wav_path = None # Path for the temporary WAV file
    try:
        # Read the raw binary data from the request body (assuming Opus bytes from Flutter web)
        raw_audio_bytes = await request.body()
        print(f"Received {len(raw_audio_bytes)} bytes of raw audio data.")

        if not raw_audio_bytes:
            raise HTTPException(status_code=400, detail="No audio data received.")

        # Create a temporary file to save the converted WAV data
        # Create a temporary WAV file path for FFmpeg output
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav_file:
            tmp_wav_path = tmp_wav_file.name

        # Use FFmpeg subprocess to read raw input bytes and convert to WAV
        # We'll pipe the raw audio bytes directly to FFmpeg's stdin.
        # We specify the input format as ogg to help FFmpeg understand the Opus data within.
        ffmpeg_command = [
            "ffmpeg",
            "-y", # Overwrite output file without asking
            "-f", "ogg", # Input format: ogg (containing Opus)
            "-i", "pipe:0", # Read from standard input
            "-acodec", "pcm_s16le", # Output audio codec: signed 16-bit little-endian PCM
            "-ar", str(OPUS_SAMPLE_RATE), # Output sample rate
            "-ac", str(OPUS_NUM_CHANNELS), # Output channels
            tmp_wav_path # Output file path
        ]

        print(f"Running FFmpeg conversion: {' '.join(ffmpeg_command)}")

        # Run FFmpeg as a subprocess, piping the raw audio bytes to its stdin
        process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(input=raw_audio_bytes)

        if process.returncode != 0:
            print(f"FFmpeg conversion failed. Stderr: {stderr.decode()}")
            raise HTTPException(status_code=500, detail=f"Audio conversion failed: {stderr.decode()}")

        print(f"FFmpeg conversion successful. Output saved to {tmp_wav_path}")
        print(f"FFmpeg stdout: {stdout.decode()}")
        print(f"FFmpeg stderr: {stderr.decode()}") # FFmpeg often writes progress/errors to stderr even on success

        # Transcribe the temporary WAV file using Whisper
        transcription_result = whisper_model.transcribe(tmp_wav_path)
        # Around line 275, change this:
        transcribed_text = transcription_result['text']
        
        # To this (ensure it's always a string):
        transcribed_text = str(transcription_result['text']) if transcription_result['text'] else ""
        print(f"Transcription complete: {transcribed_text}")
        return TranscriptionResponse(transcribed_text=transcribed_text)

    except Exception as e:
        print(f"Error during backend transcription process: {e}")
        # import traceback
        # print(traceback.format_exc()) # Uncomment for detailed error during debugging
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    finally:
        # Clean up the temporary file(s)
        if tmp_wav_path and os.path.exists(tmp_wav_path):
            os.remove(tmp_wav_path)

@app.post('/synthesize', response_model=SynthesisResponse)
async def synthesize_text(request: SynthesisRequest = Body(...)):
    if tts_model is None:
        raise HTTPException(status_code=503, detail="TTS model not loaded.")

    print(f"Received text for synthesis: {request.text}")

    # Create a temporary file to save the synthesized audio
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_audio_file:
        tmp_audio_path = tmp_audio_file.name

    try:
        # Synthesize text to speech
        # The tts method saves the audio to the specified file path
        tts_model.tts_to_file(text=request.text, file_path=tmp_audio_path)
        print(f"Synthesis complete. Audio saved to {tmp_audio_path}")

        # Read the audio file and encode it as base64
        with open(tmp_audio_path, "rb") as audio_file:
            audio_content = base64.b64encode(audio_file.read()).decode('utf-8')

        return SynthesisResponse(audio_content=audio_content)
    except Exception as e:
        print(f"Error during synthesis: {e}")
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {e}")
    finally:
        # Clean up the temporary audio file
        os.remove(tmp_audio_path)

# TODO: Add endpoints for user data, daily messages, etc.
# TODO: Add endpoints for user data, daily messages, etc.

# Assume parameters for Opus decoding based on common settings and Flutter output
OPUS_SAMPLE_RATE = 48000 # Hz
OPUS_NUM_CHANNELS = 1    # Mono
OPUS_FRAME_SIZE_MS = 20  # milliseconds, a common frame size for Opus