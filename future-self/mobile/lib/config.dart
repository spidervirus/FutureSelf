// Create a config.dart file
import 'package:supabase_flutter/supabase_flutter.dart';

class ApiConfig {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://69.62.83.177:8888',
  );
  
  static const int timeoutDuration = 30; // seconds
  static const int maxRetries = 3;

  static Future<void> initializeSupabase() async {
    await Supabase.initialize(
      url: 'https://hsdxqhfyjbnxuaopwpil.supabase.co',
      anonKey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhzZHhxaGZ5amJueHVhb3B3cGlsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgyNTg1MTAsImV4cCI6MjA2MzgzNDUxMH0.DF6E4HSioBUsO_40dBMiQgnKj_-j_mFHuRA7Zu1GjuM',
    );
  }
}