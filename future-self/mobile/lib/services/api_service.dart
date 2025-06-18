import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart'; // For logging

import 'package:http/http.dart' as http;
import '../config.dart'; // Corrected import path for config.dart

class ApiService {
  final http.Client _client;
  final String baseUrl;

  ApiService({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        baseUrl = baseUrl ?? ApiConfig.baseUrl;

  Future<T> _retryRequest<T>(
    Future<T> Function() request, {
    int maxRetries = ApiConfig.maxRetries,
  }) async {
    int attempts = 0;
    while (attempts < maxRetries) {
      try {
        return await request();
      } catch (e) {
        attempts++;
        if (attempts == maxRetries) rethrow;
        await Future.delayed(Duration(seconds: attempts));
      }
    }
    throw Exception('All retry attempts failed');
  }

  Future<Map<String, dynamic>> sendMessage(String message, String userId) async {
    return _retryRequest(() async {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/chat'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'message': message, 'user_id': userId}),
          )
          .timeout(const Duration(seconds: ApiConfig.timeoutDuration));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw HttpException('Failed to send message: ${response.statusCode} ${response.body}');
      }
    });
  }

  Future<String> transcribeAudio(Uint8List audioBytes, String userId) async {
    return _retryRequest(() async {
      var request = http.MultipartRequest('POST', Uri.parse('$baseUrl/transcribe?user_id_query=$userId'));
      request.files.add(http.MultipartFile.fromBytes('file', audioBytes, filename: 'audio.wav')); // Assuming WAV format, adjust if needed
      // request.headers['X-User-ID'] = userId; // Alternative way to send user_id

      final streamedResponse = await _client.send(request).timeout(const Duration(seconds: ApiConfig.timeoutDuration));
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        return jsonDecode(response.body)['transcribed_text'];
      } else {
        throw HttpException('Failed to transcribe audio: ${response.statusCode} ${response.body}');
      }
    });
  }

  Future<String> synthesizeSpeech(String text, String userId) async {
    return _retryRequest(() async {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/synthesize'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'text': text, 'user_id': userId}),
          )
          .timeout(const Duration(seconds: ApiConfig.timeoutDuration));

      if (response.statusCode == 200) {
        return jsonDecode(response.body)['audio_content']; // Base64 encoded audio
      } else {
        throw HttpException('Failed to synthesize speech: ${response.statusCode} ${response.body}');
      }
    });
  }

  // Renamed to avoid duplicate function name
  Future<String> sendMessageString(String message, String userId) async {
    final url = Uri.parse('$baseUrl/chat');
    
    try {
      final response = await _retryRequest(() async {
        return await _client.post(
          url,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'message': message,
            'user_id': userId,
          }),
        );
      });

      if (response.statusCode == 200) {
        final responseData = jsonDecode(response.body);
        return responseData['response'];
      } else {
        throw HttpException('Failed to send message: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('Error sending message: $e');
      rethrow;
    }
  }
  
  // New method for streaming messages
  Stream<String> streamMessage(String message, String userId) async* {
    final url = Uri.parse('$baseUrl/chat/stream');
    final request = http.Request('POST', url);
    
    request.headers['Content-Type'] = 'application/json';
    request.body = jsonEncode({
      'message': message,
      'user_id': userId,
    });
    
    try {
      final response = await _client.send(request);
      
      if (response.statusCode == 200) {
        // Process the stream
        await for (final chunk in response.stream.transform(utf8.decoder).transform(const LineSplitter())) {
          if (chunk.startsWith('data: ')) {
            final data = chunk.substring(6); // Remove 'data: ' prefix
            try {
              final jsonData = jsonDecode(data);
              
              // Check if this is the completion message
              if (jsonData.containsKey('done')) {
                break;
              }
              
              // Check if there's an error
              if (jsonData.containsKey('error')) {
                throw HttpException(jsonData['error']);
              }
              
              // Yield the text chunk
              if (jsonData.containsKey('text')) {
                yield jsonData['text'];
              }
            } catch (e) {
              debugPrint('Error parsing SSE data: $e');
              // Skip malformed data
            }
          }
        }
      } else {
        throw HttpException('Failed to stream message: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('Error streaming message: $e');
      rethrow;
    }
  }

  // NLP Services
  
  /// Analyze emotion in a message
  Future<Map<String, dynamic>> analyzeEmotion(String message, String userId) async {
    return _retryRequest(() async {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/nlp/emotion'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'message': message, 'user_id': userId}),
          )
          .timeout(const Duration(seconds: ApiConfig.timeoutDuration));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw HttpException('Failed to analyze emotion: ${response.statusCode} ${response.body}');
      }
    });
  }

  /// Analyze bias in a message
  Future<Map<String, dynamic>> analyzeBias(String message, String userId) async {
    return _retryRequest(() async {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/nlp/bias'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'message': message, 'user_id': userId}),
          )
          .timeout(const Duration(seconds: ApiConfig.timeoutDuration));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw HttpException('Failed to analyze bias: ${response.statusCode} ${response.body}');
      }
    });
  }

  /// Get analytics for a user
  Future<Map<String, dynamic>> getAnalytics(String userId, {String? timeframe}) async {
    return _retryRequest(() async {
      final uri = Uri.parse('$baseUrl/nlp/analytics/$userId');
      final uriWithQuery = timeframe != null 
          ? uri.replace(queryParameters: {'timeframe': timeframe})
          : uri;
      
      final response = await _client
          .get(
            uriWithQuery,
            headers: {'Content-Type': 'application/json'},
          )
          .timeout(const Duration(seconds: ApiConfig.timeoutDuration));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw HttpException('Failed to get analytics: ${response.statusCode} ${response.body}');
      }
    });
  }

  /// Get emotion trends for a user
  Future<Map<String, dynamic>> getEmotionTrends(String userId, {String? timeframe}) async {
    return _retryRequest(() async {
      final uri = Uri.parse('$baseUrl/nlp/emotion-trends/$userId');
      final uriWithQuery = timeframe != null 
          ? uri.replace(queryParameters: {'timeframe': timeframe})
          : uri;
      
      final response = await _client
          .get(
            uriWithQuery,
            headers: {'Content-Type': 'application/json'},
          )
          .timeout(const Duration(seconds: ApiConfig.timeoutDuration));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw HttpException('Failed to get emotion trends: ${response.statusCode} ${response.body}');
      }
    });
  }

  /// Get bias patterns for a user
  Future<Map<String, dynamic>> getBiasPatterns(String userId, {String? timeframe}) async {
    return _retryRequest(() async {
      final uri = Uri.parse('$baseUrl/nlp/bias-patterns/$userId');
      final uriWithQuery = timeframe != null 
          ? uri.replace(queryParameters: {'timeframe': timeframe})
          : uri;
      
      final response = await _client
          .get(
            uriWithQuery,
            headers: {'Content-Type': 'application/json'},
          )
          .timeout(const Duration(seconds: ApiConfig.timeoutDuration));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw HttpException('Failed to get bias patterns: ${response.statusCode} ${response.body}');
      }
    });
  }
}