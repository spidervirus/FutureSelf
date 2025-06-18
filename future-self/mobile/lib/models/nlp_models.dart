// NLP Models for FutureSelf App

/// Emotion analysis result
class EmotionAnalysis {
  final String primaryEmotion;
  final double confidence;
  final Map<String, double> emotionScores;
  final List<String> detectedEmotions;
  final String? sentiment;
  final double? sentimentScore;
  final DateTime timestamp;

  EmotionAnalysis({
    required this.primaryEmotion,
    required this.confidence,
    required this.emotionScores,
    required this.detectedEmotions,
    this.sentiment,
    this.sentimentScore,
    required this.timestamp,
  });

  factory EmotionAnalysis.fromJson(Map<String, dynamic> json) {
    return EmotionAnalysis(
      primaryEmotion: json['primary_emotion'] ?? '',
      confidence: (json['confidence'] ?? 0.0).toDouble(),
      emotionScores: Map<String, double>.from(
        (json['emotion_scores'] ?? {}).map(
          (key, value) => MapEntry(key, (value ?? 0.0).toDouble()),
        ),
      ),
      detectedEmotions: List<String>.from(json['detected_emotions'] ?? []),
      sentiment: json['sentiment'],
      sentimentScore: json['sentiment_score']?.toDouble(),
      timestamp: DateTime.parse(json['timestamp'] ?? DateTime.now().toIso8601String()),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'primary_emotion': primaryEmotion,
      'confidence': confidence,
      'emotion_scores': emotionScores,
      'detected_emotions': detectedEmotions,
      'sentiment': sentiment,
      'sentiment_score': sentimentScore,
      'timestamp': timestamp.toIso8601String(),
    };
  }
}

/// Bias analysis result
class BiasAnalysis {
  final List<BiasDetection> detectedBiases;
  final double overallBiasScore;
  final String riskLevel;
  final List<String> suggestions;
  final DateTime timestamp;

  BiasAnalysis({
    required this.detectedBiases,
    required this.overallBiasScore,
    required this.riskLevel,
    required this.suggestions,
    required this.timestamp,
  });

  factory BiasAnalysis.fromJson(Map<String, dynamic> json) {
    return BiasAnalysis(
      detectedBiases: (json['detected_biases'] as List? ?? [])
          .map((bias) => BiasDetection.fromJson(bias))
          .toList(),
      overallBiasScore: (json['overall_bias_score'] ?? 0.0).toDouble(),
      riskLevel: json['risk_level'] ?? 'low',
      suggestions: List<String>.from(json['suggestions'] ?? []),
      timestamp: DateTime.parse(json['timestamp'] ?? DateTime.now().toIso8601String()),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'detected_biases': detectedBiases.map((bias) => bias.toJson()).toList(),
      'overall_bias_score': overallBiasScore,
      'risk_level': riskLevel,
      'suggestions': suggestions,
      'timestamp': timestamp.toIso8601String(),
    };
  }
}

/// Individual bias detection
class BiasDetection {
  final String type;
  final double confidence;
  final String description;
  final String? context;

  BiasDetection({
    required this.type,
    required this.confidence,
    required this.description,
    this.context,
  });

  factory BiasDetection.fromJson(Map<String, dynamic> json) {
    return BiasDetection(
      type: json['type'] ?? '',
      confidence: (json['confidence'] ?? 0.0).toDouble(),
      description: json['description'] ?? '',
      context: json['context'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'type': type,
      'confidence': confidence,
      'description': description,
      'context': context,
    };
  }
}

/// User analytics data
class UserAnalytics {
  final String userId;
  final String timeframe;
  final int totalMessages;
  final Map<String, int> emotionCounts;
  final Map<String, int> biasCounts;
  final double averageEmotionScore;
  final double averageBiasScore;
  final List<String> topEmotions;
  final List<String> topBiases;
  final Map<String, dynamic> trends;
  final DateTime generatedAt;

  UserAnalytics({
    required this.userId,
    required this.timeframe,
    required this.totalMessages,
    required this.emotionCounts,
    required this.biasCounts,
    required this.averageEmotionScore,
    required this.averageBiasScore,
    required this.topEmotions,
    required this.topBiases,
    required this.trends,
    required this.generatedAt,
  });

  factory UserAnalytics.fromJson(Map<String, dynamic> json) {
    return UserAnalytics(
      userId: json['user_id'] ?? '',
      timeframe: json['timeframe'] ?? '',
      totalMessages: json['total_messages'] ?? 0,
      emotionCounts: Map<String, int>.from(json['emotion_counts'] ?? {}),
      biasCounts: Map<String, int>.from(json['bias_counts'] ?? {}),
      averageEmotionScore: (json['average_emotion_score'] ?? 0.0).toDouble(),
      averageBiasScore: (json['average_bias_score'] ?? 0.0).toDouble(),
      topEmotions: List<String>.from(json['top_emotions'] ?? []),
      topBiases: List<String>.from(json['top_biases'] ?? []),
      trends: Map<String, dynamic>.from(json['trends'] ?? {}),
      generatedAt: DateTime.parse(json['generated_at'] ?? DateTime.now().toIso8601String()),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'user_id': userId,
      'timeframe': timeframe,
      'total_messages': totalMessages,
      'emotion_counts': emotionCounts,
      'bias_counts': biasCounts,
      'average_emotion_score': averageEmotionScore,
      'average_bias_score': averageBiasScore,
      'top_emotions': topEmotions,
      'top_biases': topBiases,
      'trends': trends,
      'generated_at': generatedAt.toIso8601String(),
    };
  }
}

/// Emotion trend data point
class EmotionTrendPoint {
  final DateTime date;
  final String emotion;
  final double score;
  final int count;

  EmotionTrendPoint({
    required this.date,
    required this.emotion,
    required this.score,
    required this.count,
  });

  factory EmotionTrendPoint.fromJson(Map<String, dynamic> json) {
    return EmotionTrendPoint(
      date: DateTime.parse(json['date']),
      emotion: json['emotion'] ?? '',
      score: (json['score'] ?? 0.0).toDouble(),
      count: json['count'] ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'date': date.toIso8601String(),
      'emotion': emotion,
      'score': score,
      'count': count,
    };
  }
}

/// Emotion trends collection
class EmotionTrends {
  final String userId;
  final String timeframe;
  final List<EmotionTrendPoint> trends;
  final Map<String, double> averageScores;
  final DateTime generatedAt;

  EmotionTrends({
    required this.userId,
    required this.timeframe,
    required this.trends,
    required this.averageScores,
    required this.generatedAt,
  });

  factory EmotionTrends.fromJson(Map<String, dynamic> json) {
    return EmotionTrends(
      userId: json['user_id'] ?? '',
      timeframe: json['timeframe'] ?? '',
      trends: (json['trends'] as List? ?? [])
          .map((trend) => EmotionTrendPoint.fromJson(trend))
          .toList(),
      averageScores: Map<String, double>.from(
        (json['average_scores'] ?? {}).map(
          (key, value) => MapEntry(key, (value ?? 0.0).toDouble()),
        ),
      ),
      generatedAt: DateTime.parse(json['generated_at'] ?? DateTime.now().toIso8601String()),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'user_id': userId,
      'timeframe': timeframe,
      'trends': trends.map((trend) => trend.toJson()).toList(),
      'average_scores': averageScores,
      'generated_at': generatedAt.toIso8601String(),
    };
  }
}

/// Bias pattern data
class BiasPattern {
  final String type;
  final int frequency;
  final double averageConfidence;
  final List<String> contexts;
  final String trend; // 'increasing', 'decreasing', 'stable'

  BiasPattern({
    required this.type,
    required this.frequency,
    required this.averageConfidence,
    required this.contexts,
    required this.trend,
  });

  factory BiasPattern.fromJson(Map<String, dynamic> json) {
    return BiasPattern(
      type: json['type'] ?? '',
      frequency: json['frequency'] ?? 0,
      averageConfidence: (json['average_confidence'] ?? 0.0).toDouble(),
      contexts: List<String>.from(json['contexts'] ?? []),
      trend: json['trend'] ?? 'stable',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'type': type,
      'frequency': frequency,
      'average_confidence': averageConfidence,
      'contexts': contexts,
      'trend': trend,
    };
  }
}

/// Bias patterns collection
class BiasPatterns {
  final String userId;
  final String timeframe;
  final List<BiasPattern> patterns;
  final double overallTrend;
  final List<String> recommendations;
  final DateTime generatedAt;

  BiasPatterns({
    required this.userId,
    required this.timeframe,
    required this.patterns,
    required this.overallTrend,
    required this.recommendations,
    required this.generatedAt,
  });

  factory BiasPatterns.fromJson(Map<String, dynamic> json) {
    return BiasPatterns(
      userId: json['user_id'] ?? '',
      timeframe: json['timeframe'] ?? '',
      patterns: (json['patterns'] as List? ?? [])
          .map((pattern) => BiasPattern.fromJson(pattern))
          .toList(),
      overallTrend: (json['overall_trend'] ?? 0.0).toDouble(),
      recommendations: List<String>.from(json['recommendations'] ?? []),
      generatedAt: DateTime.parse(json['generated_at'] ?? DateTime.now().toIso8601String()),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'user_id': userId,
      'timeframe': timeframe,
      'patterns': patterns.map((pattern) => pattern.toJson()).toList(),
      'overall_trend': overallTrend,
      'recommendations': recommendations,
      'generated_at': generatedAt.toIso8601String(),
    };
  }
}