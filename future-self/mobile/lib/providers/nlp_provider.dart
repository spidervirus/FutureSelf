import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';

import '../models/nlp_models.dart';
import '../services/nlp_service.dart';

/// Provider for managing NLP-related state and data
class NlpProvider extends ChangeNotifier {
  final NlpService _nlpService;
  
  // Current analysis results
  EmotionAnalysis? _currentEmotion;
  BiasAnalysis? _currentBias;
  UserAnalytics? _userAnalytics;
  EmotionTrends? _emotionTrends;
  BiasPatterns? _biasPatterns;
  
  // Loading states
  bool _isAnalyzingEmotion = false;
  bool _isAnalyzingBias = false;
  bool _isLoadingAnalytics = false;
  bool _isLoadingTrends = false;
  bool _isLoadingPatterns = false;
  
  // Settings
  bool _emotionAnalysisEnabled = true;
  bool _biasAnalysisEnabled = true;
  bool _realTimeAnalysisEnabled = true;
  String _selectedTimeframe = '7d';
  
  // Cache for recent analyses
  final List<EmotionAnalysis> _recentEmotions = [];
  final List<BiasAnalysis> _recentBiases = [];
  final int _maxCacheSize = 50;
  
  NlpProvider({NlpService? nlpService}) 
      : _nlpService = nlpService ?? NlpService() {
    _loadSettings();
  }
  
  // Getters
  EmotionAnalysis? get currentEmotion => _currentEmotion;
  BiasAnalysis? get currentBias => _currentBias;
  UserAnalytics? get userAnalytics => _userAnalytics;
  EmotionTrends? get emotionTrends => _emotionTrends;
  BiasPatterns? get biasPatterns => _biasPatterns;
  
  bool get isAnalyzingEmotion => _isAnalyzingEmotion;
  bool get isAnalyzingBias => _isAnalyzingBias;
  bool get isLoadingAnalytics => _isLoadingAnalytics;
  bool get isLoadingTrends => _isLoadingTrends;
  bool get isLoadingPatterns => _isLoadingPatterns;
  
  bool get emotionAnalysisEnabled => _emotionAnalysisEnabled;
  bool get biasAnalysisEnabled => _biasAnalysisEnabled;
  bool get realTimeAnalysisEnabled => _realTimeAnalysisEnabled;
  String get selectedTimeframe => _selectedTimeframe;
  
  List<EmotionAnalysis> get recentEmotions => List.unmodifiable(_recentEmotions);
  List<BiasAnalysis> get recentBiases => List.unmodifiable(_recentBiases);
  
  bool get isAnyLoading => _isAnalyzingEmotion || _isAnalyzingBias || 
                          _isLoadingAnalytics || _isLoadingTrends || _isLoadingPatterns;
  
  /// Analyze emotion in a message
  Future<EmotionAnalysis?> analyzeEmotion(String message, String userId) async {
    if (!_emotionAnalysisEnabled || !_nlpService.shouldAnalyzeEmotion(message)) {
      return null;
    }
    
    _isAnalyzingEmotion = true;
    notifyListeners();
    
    try {
      final result = await _nlpService.analyzeEmotion(message, userId);
      if (result != null) {
        _currentEmotion = result;
        _addToEmotionCache(result);
        await _saveRecentEmotions();
      }
      return result;
    } finally {
      _isAnalyzingEmotion = false;
      notifyListeners();
    }
  }
  
  /// Analyze bias in a message
  Future<BiasAnalysis?> analyzeBias(String message, String userId) async {
    if (!_biasAnalysisEnabled || !_nlpService.shouldAnalyzeBias(message)) {
      return null;
    }
    
    _isAnalyzingBias = true;
    notifyListeners();
    
    try {
      final result = await _nlpService.analyzeBias(message, userId);
      if (result != null) {
        _currentBias = result;
        _addToBiasCache(result);
        await _saveRecentBiases();
      }
      return result;
    } finally {
      _isAnalyzingBias = false;
      notifyListeners();
    }
  }
  
  /// Analyze both emotion and bias for a message
  Future<Map<String, dynamic>> analyzeMessage(String message, String userId) async {
    if (_realTimeAnalysisEnabled) {
      final futures = <Future>[];
      
      if (_emotionAnalysisEnabled && _nlpService.shouldAnalyzeEmotion(message)) {
        futures.add(analyzeEmotion(message, userId));
      }
      
      if (_biasAnalysisEnabled && _nlpService.shouldAnalyzeBias(message)) {
        futures.add(analyzeBias(message, userId));
      }
      
      if (futures.isNotEmpty) {
        await Future.wait(futures);
      }
    }
    
    return {
      'emotion': _currentEmotion,
      'bias': _currentBias,
      'success': true,
    };
  }
  
  /// Load user analytics
  Future<void> loadUserAnalytics(String userId, {String? timeframe}) async {
    _isLoadingAnalytics = true;
    notifyListeners();
    
    try {
      final result = await _nlpService.getUserAnalytics(
        userId, 
        timeframe: timeframe ?? _selectedTimeframe,
      );
      _userAnalytics = result;
    } finally {
      _isLoadingAnalytics = false;
      notifyListeners();
    }
  }
  
  /// Load emotion trends
  Future<void> loadEmotionTrends(String userId, {String? timeframe}) async {
    _isLoadingTrends = true;
    notifyListeners();
    
    try {
      final result = await _nlpService.getEmotionTrends(
        userId, 
        timeframe: timeframe ?? _selectedTimeframe,
      );
      _emotionTrends = result;
    } finally {
      _isLoadingTrends = false;
      notifyListeners();
    }
  }
  
  /// Load bias patterns
  Future<void> loadBiasPatterns(String userId, {String? timeframe}) async {
    _isLoadingPatterns = true;
    notifyListeners();
    
    try {
      final result = await _nlpService.getBiasPatterns(
        userId, 
        timeframe: timeframe ?? _selectedTimeframe,
      );
      _biasPatterns = result;
    } finally {
      _isLoadingPatterns = false;
      notifyListeners();
    }
  }
  
  /// Load all user insights
  Future<void> loadUserInsights(String userId, {String? timeframe}) async {
    final selectedTimeframe = timeframe ?? _selectedTimeframe;
    
    await Future.wait([
      loadUserAnalytics(userId, timeframe: selectedTimeframe),
      loadEmotionTrends(userId, timeframe: selectedTimeframe),
      loadBiasPatterns(userId, timeframe: selectedTimeframe),
    ]);
  }
  
  /// Update settings
  Future<void> updateEmotionAnalysisEnabled(bool enabled) async {
    _emotionAnalysisEnabled = enabled;
    await _saveSettings();
    notifyListeners();
  }
  
  Future<void> updateBiasAnalysisEnabled(bool enabled) async {
    _biasAnalysisEnabled = enabled;
    await _saveSettings();
    notifyListeners();
  }
  
  Future<void> updateRealTimeAnalysisEnabled(bool enabled) async {
    _realTimeAnalysisEnabled = enabled;
    await _saveSettings();
    notifyListeners();
  }
  
  Future<void> updateSelectedTimeframe(String timeframe) async {
    _selectedTimeframe = timeframe;
    await _saveSettings();
    notifyListeners();
  }
  
  /// Clear current analysis results
  void clearCurrentResults() {
    _currentEmotion = null;
    _currentBias = null;
    notifyListeners();
  }
  
  /// Clear all cached data
  Future<void> clearAllData() async {
    _currentEmotion = null;
    _currentBias = null;
    _userAnalytics = null;
    _emotionTrends = null;
    _biasPatterns = null;
    _recentEmotions.clear();
    _recentBiases.clear();
    
    await _clearStoredData();
    notifyListeners();
  }
  
  /// Get emotion summary for recent messages
  Map<String, dynamic> getEmotionSummary() {
    if (_recentEmotions.isEmpty) {
      return {'isEmpty': true};
    }
    
    final emotionCounts = <String, int>{};
    double totalConfidence = 0;
    
    for (final emotion in _recentEmotions) {
      emotionCounts[emotion.primaryEmotion] = 
          (emotionCounts[emotion.primaryEmotion] ?? 0) + 1;
      totalConfidence += emotion.confidence;
    }
    
    final mostCommon = emotionCounts.entries
        .reduce((a, b) => a.value > b.value ? a : b);
    
    return {
      'isEmpty': false,
      'totalAnalyses': _recentEmotions.length,
      'mostCommonEmotion': mostCommon.key,
      'mostCommonCount': mostCommon.value,
      'averageConfidence': totalConfidence / _recentEmotions.length,
      'emotionCounts': emotionCounts,
    };
  }
  
  /// Get bias summary for recent messages
  Map<String, dynamic> getBiasSummary() {
    if (_recentBiases.isEmpty) {
      return {'isEmpty': true};
    }
    
    final riskLevelCounts = <String, int>{};
    double totalBiasScore = 0;
    int totalBiasDetections = 0;
    
    for (final bias in _recentBiases) {
      riskLevelCounts[bias.riskLevel] = 
          (riskLevelCounts[bias.riskLevel] ?? 0) + 1;
      totalBiasScore += bias.overallBiasScore;
      totalBiasDetections += bias.detectedBiases.length;
    }
    
    return {
      'isEmpty': false,
      'totalAnalyses': _recentBiases.length,
      'averageBiasScore': totalBiasScore / _recentBiases.length,
      'totalBiasDetections': totalBiasDetections,
      'riskLevelCounts': riskLevelCounts,
    };
  }
  
  // Private methods
  
  void _addToEmotionCache(EmotionAnalysis emotion) {
    _recentEmotions.insert(0, emotion);
    if (_recentEmotions.length > _maxCacheSize) {
      _recentEmotions.removeRange(_maxCacheSize, _recentEmotions.length);
    }
  }
  
  void _addToBiasCache(BiasAnalysis bias) {
    _recentBiases.insert(0, bias);
    if (_recentBiases.length > _maxCacheSize) {
      _recentBiases.removeRange(_maxCacheSize, _recentBiases.length);
    }
  }
  
  Future<void> _loadSettings() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _emotionAnalysisEnabled = prefs.getBool('nlp_emotion_enabled') ?? true;
      _biasAnalysisEnabled = prefs.getBool('nlp_bias_enabled') ?? true;
      _realTimeAnalysisEnabled = prefs.getBool('nlp_realtime_enabled') ?? true;
      _selectedTimeframe = prefs.getString('nlp_timeframe') ?? '7d';
      
      await _loadRecentEmotions();
      await _loadRecentBiases();
    } catch (e) {
      debugPrint('Error loading NLP settings: $e');
    }
  }
  
  Future<void> _saveSettings() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool('nlp_emotion_enabled', _emotionAnalysisEnabled);
      await prefs.setBool('nlp_bias_enabled', _biasAnalysisEnabled);
      await prefs.setBool('nlp_realtime_enabled', _realTimeAnalysisEnabled);
      await prefs.setString('nlp_timeframe', _selectedTimeframe);
    } catch (e) {
      debugPrint('Error saving NLP settings: $e');
    }
  }
  
  Future<void> _loadRecentEmotions() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final emotionsJson = prefs.getStringList('nlp_recent_emotions') ?? [];
      
      _recentEmotions.clear();
      for (final emotionStr in emotionsJson) {
        try {
          final emotionMap = jsonDecode(emotionStr);
          _recentEmotions.add(EmotionAnalysis.fromJson(emotionMap));
        } catch (e) {
          debugPrint('Error parsing stored emotion: $e');
        }
      }
    } catch (e) {
      debugPrint('Error loading recent emotions: $e');
    }
  }
  
  Future<void> _saveRecentEmotions() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final emotionsJson = _recentEmotions
          .map((emotion) => jsonEncode(emotion.toJson()))
          .toList();
      await prefs.setStringList('nlp_recent_emotions', emotionsJson);
    } catch (e) {
      debugPrint('Error saving recent emotions: $e');
    }
  }
  
  Future<void> _loadRecentBiases() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final biasesJson = prefs.getStringList('nlp_recent_biases') ?? [];
      
      _recentBiases.clear();
      for (final biasStr in biasesJson) {
        try {
          final biasMap = jsonDecode(biasStr);
          _recentBiases.add(BiasAnalysis.fromJson(biasMap));
        } catch (e) {
          debugPrint('Error parsing stored bias: $e');
        }
      }
    } catch (e) {
      debugPrint('Error loading recent biases: $e');
    }
  }
  
  Future<void> _saveRecentBiases() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final biasesJson = _recentBiases
          .map((bias) => jsonEncode(bias.toJson()))
          .toList();
      await prefs.setStringList('nlp_recent_biases', biasesJson);
    } catch (e) {
      debugPrint('Error saving recent biases: $e');
    }
  }
  
  Future<void> _clearStoredData() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('nlp_recent_emotions');
      await prefs.remove('nlp_recent_biases');
    } catch (e) {
      debugPrint('Error clearing stored NLP data: $e');
    }
  }
  
}