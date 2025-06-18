import 'package:flutter/material.dart';
import '../models/nlp_models.dart';
import 'api_service.dart';

/// Service for handling NLP-related operations
class NlpService {
  final ApiService _apiService;
  
  NlpService({ApiService? apiService}) 
      : _apiService = apiService ?? ApiService();

  /// Analyze emotion in a message and return typed result
  Future<EmotionAnalysis?> analyzeEmotion(String message, String userId) async {
    try {
      final response = await _apiService.analyzeEmotion(message, userId);
      return EmotionAnalysis.fromJson(response);
    } catch (e) {
      debugPrint('Error analyzing emotion: $e');
      return null;
    }
  }

  /// Analyze bias in a message and return typed result
  Future<BiasAnalysis?> analyzeBias(String message, String userId) async {
    try {
      final response = await _apiService.analyzeBias(message, userId);
      return BiasAnalysis.fromJson(response);
    } catch (e) {
      debugPrint('Error analyzing bias: $e');
      return null;
    }
  }

  /// Get user analytics with optional timeframe
  Future<UserAnalytics?> getUserAnalytics(String userId, {String? timeframe}) async {
    try {
      final response = await _apiService.getAnalytics(userId, timeframe: timeframe);
      return UserAnalytics.fromJson(response);
    } catch (e) {
      debugPrint('Error getting user analytics: $e');
      return null;
    }
  }

  /// Get emotion trends for a user
  Future<EmotionTrends?> getEmotionTrends(String userId, {String? timeframe}) async {
    try {
      final response = await _apiService.getEmotionTrends(userId, timeframe: timeframe);
      return EmotionTrends.fromJson(response);
    } catch (e) {
      debugPrint('Error getting emotion trends: $e');
      return null;
    }
  }

  /// Get bias patterns for a user
  Future<BiasPatterns?> getBiasPatterns(String userId, {String? timeframe}) async {
    try {
      final response = await _apiService.getBiasPatterns(userId, timeframe: timeframe);
      return BiasPatterns.fromJson(response);
    } catch (e) {
      debugPrint('Error getting bias patterns: $e');
      return null;
    }
  }

  // Utility methods for UI formatting
  static String getEmotionEmoji(String emotion) {
    switch (emotion.toLowerCase()) {
      case 'joy':
      case 'happy':
      case 'happiness':
        return '😊';
      case 'sadness':
      case 'sad':
        return '😢';
      case 'anger':
      case 'angry':
        return '😠';
      case 'fear':
      case 'afraid':
        return '😨';
      case 'surprise':
      case 'surprised':
        return '😲';
      case 'disgust':
      case 'disgusted':
        return '🤢';
      case 'neutral':
        return '😐';
      case 'love':
        return '❤️';
      case 'excitement':
      case 'excited':
        return '🤩';
      case 'anxiety':
      case 'anxious':
        return '😰';
      case 'confusion':
      case 'confused':
        return '😕';
      case 'frustration':
      case 'frustrated':
        return '😤';
      default:
        return '🤔';
    }
  }
  
  static String getEmotionColor(String emotion) {
    switch (emotion.toLowerCase()) {
      case 'joy':
      case 'happy':
      case 'happiness':
        return 'FFD700';
      case 'sadness':
      case 'sad':
        return '4169E1';
      case 'anger':
      case 'angry':
        return 'DC143C';
      case 'fear':
      case 'afraid':
        return '800080';
      case 'surprise':
      case 'surprised':
        return 'FF8C00';
      case 'disgust':
      case 'disgusted':
        return '228B22';
      case 'neutral':
        return '808080';
      case 'love':
        return 'FF1493';
      case 'excitement':
      case 'excited':
        return 'FF6347';
      case 'anxiety':
      case 'anxious':
        return '9370DB';
      case 'confusion':
      case 'confused':
        return 'D2691E';
      case 'frustration':
      case 'frustrated':
        return 'B22222';
      default:
        return '696969';
    }
  }
  
  static String formatEmotionScore(double score) {
    return '${(score * 100).toStringAsFixed(1)}%';
  }
  
  static String formatBiasScore(double score) {
    return '${(score * 100).toStringAsFixed(1)}%';
  }
  
  static String getBiasLevelDescription(double score) {
    if (score < 0.3) {
      return 'Low bias detected';
    } else if (score < 0.6) {
      return 'Moderate bias detected';
    } else {
      return 'High bias detected';
    }
  }
  
  static Color getBiasLevelColor(double score) {
    if (score < 0.3) {
      return const Color(0xFF4CAF50); // Green
    } else if (score < 0.6) {
      return const Color(0xFFFF9800); // Orange
    } else {
      return const Color(0xFFF44336); // Red
    }
  }

  static String getBiasSeverityColor(String riskLevel) {
    switch (riskLevel.toLowerCase()) {
      case 'low':
        return '#32CD32'; // Lime Green
      case 'medium':
        return '#FFD700'; // Gold
      case 'high':
        return '#FF6347'; // Tomato
      case 'critical':
        return '#DC143C'; // Crimson
      default:
        return '#808080'; // Gray
    }
  }

  /// Analyze both emotion and bias for a message
  Future<Map<String, dynamic>> analyzeMessage(String message, String userId) async {
    final results = <String, dynamic>{};
    
    try {
      // Run both analyses concurrently
      final futures = await Future.wait([
        analyzeEmotion(message, userId),
        analyzeBias(message, userId),
      ]);
      
      results['emotion'] = futures[0];
      results['bias'] = futures[1];
      results['success'] = true;
    } catch (e) {
      debugPrint('Error analyzing message: $e');
      results['success'] = false;
      results['error'] = e.toString();
    }
    
    return results;
  }

  /// Get comprehensive user insights
  Future<Map<String, dynamic>> getUserInsights(String userId, {String? timeframe}) async {
    final insights = <String, dynamic>{};
    
    try {
      // Run all analytics concurrently
      final futures = await Future.wait([
        getUserAnalytics(userId, timeframe: timeframe),
        getEmotionTrends(userId, timeframe: timeframe),
        getBiasPatterns(userId, timeframe: timeframe),
      ]);
      
      insights['analytics'] = futures[0];
      insights['emotionTrends'] = futures[1];
      insights['biasPatterns'] = futures[2];
      insights['success'] = true;
    } catch (e) {
      debugPrint('Error getting user insights: $e');
      insights['success'] = false;
      insights['error'] = e.toString();
    }
    
    return insights;
  }

  /// Check if emotion analysis should be performed based on message content
  bool shouldAnalyzeEmotion(String message) {
    // Skip analysis for very short messages or commands
    if (message.trim().length < 10) return false;
    
    // Skip analysis for messages that look like commands
    final commandPatterns = ['/help', '/start', '/stop', '/clear'];
    final lowerMessage = message.toLowerCase().trim();
    
    for (final pattern in commandPatterns) {
      if (lowerMessage.startsWith(pattern)) return false;
    }
    
    return true;
  }

  /// Check if bias analysis should be performed based on message content
  bool shouldAnalyzeBias(String message) {
    // Similar logic to emotion analysis but might have different criteria
    if (message.trim().length < 15) return false;
    
    // Skip for simple greetings or very basic responses
    final simplePatterns = ['hi', 'hello', 'thanks', 'thank you', 'ok', 'okay', 'yes', 'no'];
    final lowerMessage = message.toLowerCase().trim();
    
    if (simplePatterns.contains(lowerMessage)) return false;
    
    return true;
  }


}