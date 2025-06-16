import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data'; // Added for Uint8List

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
}