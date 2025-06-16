// Create a config.dart file
class ApiConfig {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );
  
  static const int timeoutDuration = 30; // seconds
  static const int maxRetries = 3;
}