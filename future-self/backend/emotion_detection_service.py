import numpy as np
import librosa
import torch
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
import spacy
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmotionDetectionService:
    """
    Multi-modal emotion detection service that analyzes emotions from text and voice.
    Combines multiple NLP models for comprehensive emotion analysis.
    """
    
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
        
        # Initialize models
        self._initialize_models()
        
        # Emotion mapping for consistency
        self.emotion_mapping = {
            'LABEL_0': 'sadness',
            'LABEL_1': 'joy', 
            'LABEL_2': 'love',
            'LABEL_3': 'anger',
            'LABEL_4': 'fear',
            'LABEL_5': 'surprise'
        }
        
        # Voice emotion features thresholds
        self.voice_thresholds = {
            'energy_high': 0.02,
            'energy_low': 0.005,
            'pitch_high': 200,
            'pitch_low': 100,
            'tempo_fast': 140,
            'tempo_slow': 80
        }
    
    def _initialize_models(self):
        """Initialize all emotion detection models"""
        try:
            # Text emotion classifier (RoBERTa-based)
            self.emotion_classifier = pipeline(
                "text-classification",
                model="j-hartmann/emotion-english-distilroberta-base",
                device=0 if torch.cuda.is_available() else -1
            )
            
            # Sentiment analyzer
            self.vader_analyzer = SentimentIntensityAnalyzer()
            
            # spaCy for text preprocessing
            self.nlp = spacy.load("en_core_web_sm")
            
            logger.info("All emotion detection models initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing models: {e}")
            raise
    
    def analyze_text_emotion(self, text: str) -> Dict:
        """
        Analyze emotions in text using multiple approaches.
        
        Args:
            text (str): Input text to analyze
            
        Returns:
            Dict: Comprehensive emotion analysis results
        """
        try:
            if not text or not text.strip():
                return self._empty_emotion_result()
            
            # Clean and preprocess text
            cleaned_text = self._preprocess_text(text)
            
            # Primary emotion detection
            primary_emotions = self.emotion_classifier(cleaned_text)
            
            # Sentiment analysis
            vader_scores = self.vader_analyzer.polarity_scores(cleaned_text)
            textblob_sentiment = TextBlob(cleaned_text).sentiment
            
            # Extract linguistic features
            linguistic_features = self._extract_linguistic_features(cleaned_text)
            
            # Combine results
            result = {
                'timestamp': datetime.now().isoformat(),
                'input_text': text,
                'primary_emotion': {
                    'emotion': primary_emotions[0]['label'].lower(),
                    'confidence': primary_emotions[0]['score'],
                    'all_emotions': [
                        {'emotion': e['label'].lower(), 'confidence': e['score']} 
                        for e in primary_emotions
                    ]
                },
                'sentiment': {
                    'vader': {
                        'compound': vader_scores['compound'],
                        'positive': vader_scores['pos'],
                        'neutral': vader_scores['neu'],
                        'negative': vader_scores['neg']
                    },
                    'textblob': {
                        'polarity': textblob_sentiment.polarity,
                        'subjectivity': textblob_sentiment.subjectivity
                    }
                },
                'linguistic_features': linguistic_features,
                'emotion_intensity': self._calculate_emotion_intensity(primary_emotions[0], vader_scores),
                'emotional_state': self._determine_emotional_state(primary_emotions[0], vader_scores)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in text emotion analysis: {e}")
            return self._empty_emotion_result(error=str(e))
    
    def analyze_voice_emotion(self, audio_file_path: str) -> Dict:
        """
        Analyze emotions in voice/audio using acoustic features.
        
        Args:
            audio_file_path (str): Path to audio file
            
        Returns:
            Dict: Voice emotion analysis results
        """
        try:
            # Load audio file
            y, sr = librosa.load(audio_file_path, sr=None)
            
            # Extract acoustic features
            features = self._extract_voice_features(y, sr)
            
            # Analyze emotional indicators
            emotion_indicators = self._analyze_voice_emotion_indicators(features)
            
            # Determine voice-based emotion
            voice_emotion = self._classify_voice_emotion(features, emotion_indicators)
            
            result = {
                'timestamp': datetime.now().isoformat(),
                'audio_file': audio_file_path,
                'voice_features': features,
                'emotion_indicators': emotion_indicators,
                'voice_emotion': voice_emotion,
                'confidence': voice_emotion.get('confidence', 0.5)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in voice emotion analysis: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    def analyze_multimodal_emotion(self, text: str = None, audio_file_path: str = None) -> Dict:
        """
        Combine text and voice emotion analysis for comprehensive results.
        
        Args:
            text (str, optional): Text to analyze
            audio_file_path (str, optional): Audio file path
            
        Returns:
            Dict: Combined multimodal emotion analysis
        """
        result = {
            'timestamp': datetime.now().isoformat(),
            'modalities': []
        }
        
        text_result = None
        voice_result = None
        
        # Analyze text if provided
        if text:
            text_result = self.analyze_text_emotion(text)
            result['text_analysis'] = text_result
            result['modalities'].append('text')
        
        # Analyze voice if provided
        if audio_file_path:
            voice_result = self.analyze_voice_emotion(audio_file_path)
            result['voice_analysis'] = voice_result
            result['modalities'].append('voice')
        
        # Combine results if both modalities are available
        if text_result and voice_result and 'error' not in voice_result:
            result['combined_analysis'] = self._combine_emotion_results(text_result, voice_result)
        
        return result
    
    def _preprocess_text(self, text: str) -> str:
        """Clean and preprocess text for analysis"""
        # Basic cleaning
        text = text.strip()
        
        # Use spaCy for more advanced preprocessing if needed
        doc = self.nlp(text)
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        return text
    
    def _extract_linguistic_features(self, text: str) -> Dict:
        """Extract linguistic features from text"""
        doc = self.nlp(text)
        
        return {
            'word_count': len([token for token in doc if not token.is_space]),
            'sentence_count': len(list(doc.sents)),
            'avg_word_length': np.mean([len(token.text) for token in doc if not token.is_punct and not token.is_space]),
            'exclamation_count': text.count('!'),
            'question_count': text.count('?'),
            'capitalized_words': len([token for token in doc if token.text.isupper() and len(token.text) > 1]),
            'emotional_punctuation': text.count('!') + text.count('?') + text.count('...'),
        }
    
    def _extract_voice_features(self, y: np.ndarray, sr: int) -> Dict:
        """Extract acoustic features from audio"""
        # Fundamental frequency (pitch)
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        pitch_values = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            if pitch > 0:
                pitch_values.append(pitch)
        
        # Energy/Intensity
        rms = librosa.feature.rms(y=y)[0]
        
        # Spectral features
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
        
        # Tempo
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        
        # Zero crossing rate
        zcr = librosa.feature.zero_crossing_rate(y)[0]
        
        return {
            'pitch_mean': np.mean(pitch_values) if pitch_values else 0,
            'pitch_std': np.std(pitch_values) if pitch_values else 0,
            'pitch_range': np.max(pitch_values) - np.min(pitch_values) if pitch_values else 0,
            'energy_mean': np.mean(rms),
            'energy_std': np.std(rms),
            'spectral_centroid_mean': np.mean(spectral_centroids),
            'spectral_rolloff_mean': np.mean(spectral_rolloff),
            'tempo': tempo,
            'zcr_mean': np.mean(zcr),
            'duration': len(y) / sr
        }
    
    def _analyze_voice_emotion_indicators(self, features: Dict) -> Dict:
        """Analyze voice features for emotional indicators"""
        indicators = {
            'arousal': 'neutral',  # high/low energy
            'valence': 'neutral',  # positive/negative
            'stress_level': 'normal',
            'speaking_rate': 'normal'
        }
        
        # Arousal (energy level)
        if features['energy_mean'] > self.voice_thresholds['energy_high']:
            indicators['arousal'] = 'high'
        elif features['energy_mean'] < self.voice_thresholds['energy_low']:
            indicators['arousal'] = 'low'
        
        # Speaking rate
        if features['tempo'] > self.voice_thresholds['tempo_fast']:
            indicators['speaking_rate'] = 'fast'
        elif features['tempo'] < self.voice_thresholds['tempo_slow']:
            indicators['speaking_rate'] = 'slow'
        
        # Stress indicators
        if (features['pitch_std'] > 50 and features['energy_std'] > 0.01):
            indicators['stress_level'] = 'high'
        
        return indicators
    
    def _classify_voice_emotion(self, features: Dict, indicators: Dict) -> Dict:
        """Classify emotion based on voice features"""
        # Simple rule-based classification
        # In production, this could be replaced with a trained model
        
        emotion = 'neutral'
        confidence = 0.5
        
        # High arousal emotions
        if indicators['arousal'] == 'high':
            if indicators['speaking_rate'] == 'fast':
                if indicators['stress_level'] == 'high':
                    emotion = 'anger'
                    confidence = 0.7
                else:
                    emotion = 'excitement'
                    confidence = 0.6
            else:
                emotion = 'surprise'
                confidence = 0.6
        
        # Low arousal emotions
        elif indicators['arousal'] == 'low':
            if indicators['speaking_rate'] == 'slow':
                emotion = 'sadness'
                confidence = 0.6
            else:
                emotion = 'calm'
                confidence = 0.5
        
        return {
            'emotion': emotion,
            'confidence': confidence,
            'reasoning': f"Arousal: {indicators['arousal']}, Rate: {indicators['speaking_rate']}, Stress: {indicators['stress_level']}"
        }
    
    def _combine_emotion_results(self, text_result: Dict, voice_result: Dict) -> Dict:
        """Combine text and voice emotion analysis results"""
        # Weight the results (text typically more reliable for emotion classification)
        text_weight = 0.7
        voice_weight = 0.3
        
        text_emotion = text_result['primary_emotion']['emotion']
        text_confidence = text_result['primary_emotion']['confidence']
        
        voice_emotion = voice_result['voice_emotion']['emotion']
        voice_confidence = voice_result['voice_emotion']['confidence']
        
        # Simple combination strategy
        if text_emotion == voice_emotion:
            combined_confidence = (text_confidence * text_weight + voice_confidence * voice_weight)
            final_emotion = text_emotion
        else:
            # Use the more confident prediction
            if text_confidence * text_weight > voice_confidence * voice_weight:
                final_emotion = text_emotion
                combined_confidence = text_confidence * 0.8  # Reduce confidence due to disagreement
            else:
                final_emotion = voice_emotion
                combined_confidence = voice_confidence * 0.8
        
        return {
            'final_emotion': final_emotion,
            'confidence': combined_confidence,
            'agreement': text_emotion == voice_emotion,
            'text_contribution': text_weight,
            'voice_contribution': voice_weight
        }
    
    def _calculate_emotion_intensity(self, primary_emotion: Dict, vader_scores: Dict) -> float:
        """Calculate overall emotion intensity"""
        emotion_confidence = primary_emotion['score']
        sentiment_intensity = abs(vader_scores['compound'])
        
        # Combine confidence and sentiment intensity
        intensity = (emotion_confidence + sentiment_intensity) / 2
        return min(intensity, 1.0)
    
    def _determine_emotional_state(self, primary_emotion: Dict, vader_scores: Dict) -> str:
        """Determine overall emotional state"""
        emotion = primary_emotion['label'].lower()
        compound = vader_scores['compound']
        
        if compound > 0.5:
            return 'very_positive'
        elif compound > 0.1:
            return 'positive'
        elif compound < -0.5:
            return 'very_negative'
        elif compound < -0.1:
            return 'negative'
        else:
            return 'neutral'
    
    def _empty_emotion_result(self, error: str = None) -> Dict:
        """Return empty emotion result structure"""
        result = {
            'timestamp': datetime.now().isoformat(),
            'primary_emotion': {'emotion': 'neutral', 'confidence': 0.0},
            'sentiment': {
                'vader': {'compound': 0.0, 'positive': 0.0, 'neutral': 1.0, 'negative': 0.0},
                'textblob': {'polarity': 0.0, 'subjectivity': 0.0}
            },
            'emotion_intensity': 0.0,
            'emotional_state': 'neutral'
        }
        
        if error:
            result['error'] = error
        
        return result

# Global instance
emotion_service = EmotionDetectionService()