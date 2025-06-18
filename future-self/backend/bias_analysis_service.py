import numpy as np
from detoxify import Detoxify
from transformers import pipeline
import spacy
from textblob import TextBlob
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
import re
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BiasAnalysisService:
    """
    Comprehensive bias and toxicity analysis service.
    Detects various forms of bias, toxicity, and harmful content in text.
    """
    
    def __init__(self):
        self._initialize_models()
        
        # Bias detection patterns
        self.bias_patterns = {
            'gender': [
                r'\b(men|women|male|female|guy|girl|boy|girl)\s+(are|is|always|never|should|shouldn\'t|can\'t|cannot)\b',
                r'\b(he|she|his|her|him)\s+(always|never|should|shouldn\'t|can\'t|cannot)\b'
            ],
            'racial': [
                r'\b(people|person)\s+of\s+(color|race)\s+(are|is|always|never)\b',
                r'\b(black|white|asian|hispanic|latino)\s+(people|person|men|women)\s+(are|is|always|never)\b'
            ],
            'age': [
                r'\b(young|old|elderly|teenager|millennial|boomer)\s+(people|person)\s+(are|is|always|never)\b',
                r'\b(age|years\s+old)\s+.*(too|not|can\'t|cannot)\b'
            ],
            'religious': [
                r'\b(christian|muslim|jewish|hindu|buddhist|atheist)s?\s+(are|is|always|never)\b',
                r'\b(religion|faith|belief)\s+.*(wrong|bad|evil|stupid)\b'
            ],
            'socioeconomic': [
                r'\b(poor|rich|wealthy|homeless)\s+(people|person)\s+(are|is|always|never)\b',
                r'\b(money|wealth|poverty)\s+.*(makes|determines|defines)\b'
            ]
        }
        
        # Toxicity thresholds
        self.toxicity_thresholds = {
            'low': 0.3,
            'medium': 0.6,
            'high': 0.8
        }
        
        # Bias severity levels
        self.bias_severity = {
            'mild': 0.3,
            'moderate': 0.6,
            'severe': 0.8
        }
    
    def _initialize_models(self):
        """Initialize bias detection models"""
        try:
            # Toxicity detection model
            self.detoxify_model = Detoxify('original')
            
            # Hate speech detection
            self.hate_speech_classifier = pipeline(
                "text-classification",
                model="unitary/toxic-bert",
                device=-1  # Use CPU for stability
            )
            
            # spaCy for text analysis
            self.nlp = spacy.load("en_core_web_sm")
            
            logger.info("Bias analysis models initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing bias analysis models: {e}")
            # Fallback to basic analysis if models fail
            self.detoxify_model = None
            self.hate_speech_classifier = None
            self.nlp = None
    
    def analyze_bias_and_toxicity(self, text: str) -> Dict:
        """
        Comprehensive bias and toxicity analysis of text.
        
        Args:
            text (str): Text to analyze
            
        Returns:
            Dict: Comprehensive bias and toxicity analysis results
        """
        try:
            if not text or not text.strip():
                return self._empty_bias_result()
            
            # Detect language
            language = self._detect_language(text)
            
            # Toxicity analysis
            toxicity_results = self._analyze_toxicity(text)
            
            # Bias pattern detection
            bias_patterns = self._detect_bias_patterns(text)
            
            # Hate speech detection
            hate_speech_results = self._analyze_hate_speech(text)
            
            # Linguistic analysis
            linguistic_analysis = self._analyze_linguistic_bias(text)
            
            # Overall assessment
            overall_assessment = self._calculate_overall_assessment(
                toxicity_results, bias_patterns, hate_speech_results
            )
            
            result = {
                'timestamp': datetime.now().isoformat(),
                'input_text': text,
                'language': language,
                'toxicity_analysis': toxicity_results,
                'bias_patterns': bias_patterns,
                'hate_speech_analysis': hate_speech_results,
                'linguistic_analysis': linguistic_analysis,
                'overall_assessment': overall_assessment,
                'recommendations': self._generate_recommendations(overall_assessment)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in bias analysis: {e}")
            return self._empty_bias_result(error=str(e))
    
    def _detect_language(self, text: str) -> str:
        """Detect the language of the text"""
        try:
            return detect(text)
        except LangDetectException:
            return 'unknown'
    
    def _analyze_toxicity(self, text: str) -> Dict:
        """Analyze toxicity using Detoxify model"""
        if not self.detoxify_model:
            return {'error': 'Detoxify model not available'}
        
        try:
            # Get toxicity scores
            scores = self.detoxify_model.predict(text)
            
            # Determine overall toxicity level
            max_score = max(scores.values())
            toxicity_level = self._determine_toxicity_level(max_score)
            
            return {
                'scores': {
                    'toxicity': float(scores.get('toxicity', 0)),
                    'severe_toxicity': float(scores.get('severe_toxicity', 0)),
                    'obscene': float(scores.get('obscene', 0)),
                    'threat': float(scores.get('threat', 0)),
                    'insult': float(scores.get('insult', 0)),
                    'identity_attack': float(scores.get('identity_attack', 0))
                },
                'overall_toxicity': float(max_score),
                'toxicity_level': toxicity_level,
                'is_toxic': max_score > self.toxicity_thresholds['low']
            }
            
        except Exception as e:
            logger.error(f"Error in toxicity analysis: {e}")
            return {'error': str(e)}
    
    def _detect_bias_patterns(self, text: str) -> Dict:
        """Detect bias patterns using regex and linguistic analysis"""
        detected_biases = {}
        
        for bias_type, patterns in self.bias_patterns.items():
            matches = []
            for pattern in patterns:
                found_matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in found_matches:
                    matches.append({
                        'text': match.group(),
                        'start': match.start(),
                        'end': match.end()
                    })
            
            if matches:
                detected_biases[bias_type] = {
                    'detected': True,
                    'matches': matches,
                    'count': len(matches),
                    'severity': self._calculate_bias_severity(len(matches), bias_type)
                }
            else:
                detected_biases[bias_type] = {
                    'detected': False,
                    'matches': [],
                    'count': 0,
                    'severity': 'none'
                }
        
        return {
            'bias_types': detected_biases,
            'total_bias_indicators': sum(bias['count'] for bias in detected_biases.values()),
            'has_bias': any(bias['detected'] for bias in detected_biases.values())
        }
    
    def _analyze_hate_speech(self, text: str) -> Dict:
        """Analyze hate speech using transformer model"""
        if not self.hate_speech_classifier:
            return {'error': 'Hate speech classifier not available'}
        
        try:
            # Classify hate speech
            result = self.hate_speech_classifier(text)
            
            # Extract results
            if isinstance(result, list) and len(result) > 0:
                prediction = result[0]
                is_hate_speech = prediction['label'] == 'TOXIC'
                confidence = prediction['score']
            else:
                is_hate_speech = False
                confidence = 0.0
            
            return {
                'is_hate_speech': is_hate_speech,
                'confidence': float(confidence),
                'classification': 'hate_speech' if is_hate_speech else 'not_hate_speech'
            }
            
        except Exception as e:
            logger.error(f"Error in hate speech analysis: {e}")
            return {'error': str(e)}
    
    def _analyze_linguistic_bias(self, text: str) -> Dict:
        """Analyze linguistic patterns that may indicate bias"""
        if not self.nlp:
            return {'error': 'spaCy model not available'}
        
        try:
            doc = self.nlp(text)
            
            # Analyze sentiment polarity
            blob = TextBlob(text)
            sentiment = blob.sentiment
            
            # Count absolute statements
            absolute_words = ['always', 'never', 'all', 'none', 'every', 'completely', 'totally']
            absolute_count = sum(1 for token in doc if token.text.lower() in absolute_words)
            
            # Count generalizations
            generalization_patterns = ['people are', 'they are', 'everyone is', 'nobody is']
            generalization_count = sum(1 for pattern in generalization_patterns if pattern in text.lower())
            
            # Emotional language intensity
            emotional_words = ['hate', 'love', 'terrible', 'amazing', 'awful', 'perfect']
            emotional_count = sum(1 for token in doc if token.text.lower() in emotional_words)
            
            return {
                'sentiment_polarity': sentiment.polarity,
                'sentiment_subjectivity': sentiment.subjectivity,
                'absolute_statements': absolute_count,
                'generalizations': generalization_count,
                'emotional_language': emotional_count,
                'word_count': len([token for token in doc if not token.is_space]),
                'bias_indicators': {
                    'high_subjectivity': sentiment.subjectivity > 0.7,
                    'extreme_polarity': abs(sentiment.polarity) > 0.8,
                    'excessive_absolutes': absolute_count > 2,
                    'many_generalizations': generalization_count > 1
                }
            }
            
        except Exception as e:
            logger.error(f"Error in linguistic bias analysis: {e}")
            return {'error': str(e)}
    
    def _determine_toxicity_level(self, score: float) -> str:
        """Determine toxicity level based on score"""
        if score >= self.toxicity_thresholds['high']:
            return 'high'
        elif score >= self.toxicity_thresholds['medium']:
            return 'medium'
        elif score >= self.toxicity_thresholds['low']:
            return 'low'
        else:
            return 'none'
    
    def _calculate_bias_severity(self, match_count: int, bias_type: str) -> str:
        """Calculate bias severity based on match count and type"""
        if match_count == 0:
            return 'none'
        elif match_count == 1:
            return 'mild'
        elif match_count <= 3:
            return 'moderate'
        else:
            return 'severe'
    
    def _calculate_overall_assessment(self, toxicity: Dict, bias: Dict, hate_speech: Dict) -> Dict:
        """Calculate overall bias and toxicity assessment"""
        # Calculate risk scores
        toxicity_risk = 0
        if 'overall_toxicity' in toxicity:
            toxicity_risk = toxicity['overall_toxicity']
        
        bias_risk = 0
        if bias['has_bias']:
            bias_count = bias['total_bias_indicators']
            bias_risk = min(bias_count * 0.2, 1.0)  # Scale bias count to 0-1
        
        hate_speech_risk = 0
        if 'confidence' in hate_speech and hate_speech.get('is_hate_speech', False):
            hate_speech_risk = hate_speech['confidence']
        
        # Overall risk calculation
        overall_risk = max(toxicity_risk, bias_risk, hate_speech_risk)
        
        # Determine risk level
        if overall_risk >= 0.8:
            risk_level = 'high'
        elif overall_risk >= 0.5:
            risk_level = 'medium'
        elif overall_risk >= 0.2:
            risk_level = 'low'
        else:
            risk_level = 'minimal'
        
        return {
            'overall_risk_score': float(overall_risk),
            'risk_level': risk_level,
            'component_risks': {
                'toxicity': float(toxicity_risk),
                'bias': float(bias_risk),
                'hate_speech': float(hate_speech_risk)
            },
            'is_problematic': overall_risk > 0.3,
            'requires_review': overall_risk > 0.5
        }
    
    def _generate_recommendations(self, assessment: Dict) -> List[str]:
        """Generate recommendations based on assessment"""
        recommendations = []
        
        risk_level = assessment['risk_level']
        
        if risk_level == 'high':
            recommendations.extend([
                "Content requires immediate review and likely modification",
                "Consider rewriting to remove harmful language",
                "Seek diverse perspectives before publishing"
            ])
        elif risk_level == 'medium':
            recommendations.extend([
                "Content should be reviewed for potential bias",
                "Consider softening absolute statements",
                "Review for inclusive language"
            ])
        elif risk_level == 'low':
            recommendations.extend([
                "Minor adjustments may improve inclusivity",
                "Consider alternative phrasing for sensitive topics"
            ])
        else:
            recommendations.append("Content appears to be free of significant bias or toxicity")
        
        # Specific recommendations based on component risks
        if assessment['component_risks']['toxicity'] > 0.5:
            recommendations.append("Remove or replace toxic language")
        
        if assessment['component_risks']['bias'] > 0.5:
            recommendations.append("Address biased generalizations or stereotypes")
        
        if assessment['component_risks']['hate_speech'] > 0.5:
            recommendations.append("Content may contain hate speech - immediate review required")
        
        return recommendations
    
    def _empty_bias_result(self, error: str = None) -> Dict:
        """Return empty bias analysis result"""
        result = {
            'timestamp': datetime.now().isoformat(),
            'toxicity_analysis': {'overall_toxicity': 0.0, 'toxicity_level': 'none', 'is_toxic': False},
            'bias_patterns': {'has_bias': False, 'total_bias_indicators': 0},
            'hate_speech_analysis': {'is_hate_speech': False, 'confidence': 0.0},
            'overall_assessment': {
                'overall_risk_score': 0.0,
                'risk_level': 'minimal',
                'is_problematic': False,
                'requires_review': False
            },
            'recommendations': ['No analysis performed']
        }
        
        if error:
            result['error'] = error
        
        return result

# Global instance
bias_service = BiasAnalysisService()