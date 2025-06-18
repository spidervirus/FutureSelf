#!/usr/bin/env python3
"""
Test script to verify NLP integration works properly
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_emotion_service():
    """Test emotion detection service"""
    try:
        print("Testing Emotion Detection Service...")
        from emotion_detection_service import EmotionDetectionService
        
        emotion_service = EmotionDetectionService()
        
        # Test text emotion analysis
        test_text = "I am feeling really happy and excited about this new project!"
        result = emotion_service.analyze_text_emotion(test_text)
        
        print(f"✅ Text emotion analysis successful:")
        print(f"   Primary emotion: {result['primary_emotion']['emotion']}")
        print(f"   Confidence: {result['primary_emotion']['confidence']}")
        print(f"   Emotional state: {result['emotional_state']}")
        print(f"   Sentiment compound: {result['sentiment']['vader']['compound']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Emotion service test failed: {e}")
        return False

def test_bias_service():
    """Test bias analysis service"""
    try:
        print("\nTesting Bias Analysis Service...")
        from bias_analysis_service import BiasAnalysisService
        
        bias_service = BiasAnalysisService()
        
        # Test bias analysis
        test_text = "This is a neutral and respectful message about technology."
        result = bias_service.analyze_bias_and_toxicity(test_text)
        
        print(f"✅ Bias analysis successful:")
        print(f"   Language: {result['language']}")
        print(f"   Overall Toxicity: {result['toxicity_analysis']['overall_toxicity']}")
        print(f"   Toxicity Level: {result['toxicity_analysis']['toxicity_level']}")
        print(f"   Bias Patterns: {result['bias_patterns']}")
        print(f"   Overall Assessment: {result['overall_assessment']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Bias service test failed: {e}")
        return False

def test_analytics_service():
    """Test analytics service (without database)"""
    try:
        print("\nTesting Analytics Service (structure only)...")
        from analytics_service import AnalyticsService
        
        # We can't test with real database, but we can verify the class loads
        print("✅ Analytics service imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Analytics service test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing NLP Integration Components\n")
    print("=" * 50)
    
    tests = [
        test_emotion_service,
        test_bias_service,
        test_analytics_service
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All NLP integration tests passed!")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)