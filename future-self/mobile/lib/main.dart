import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'screens/auth/sign_in_screen.dart';
import 'screens/auth/sign_up_screen.dart';
import 'screens/home_screen.dart';
import 'screens/user_onboarding_screen.dart';
import 'screens/chat_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized(); // Ensure widgets are initialized
  await Supabase.initialize(
    url: 'https://hsdxqhfyjbnxuaopwpil.supabase.co',
    anonKey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhzZHhxaGZ5amJueHVhb3B3cGlsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgyNTg1MTAsImV4cCI6MjA2MzgzNDUxMH0.DF6E4HSioBUsO_40dBMiQgnKj_-j_mFHuRA7Zu1GjuM',
  );

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Future-Self',
      theme: ThemeData(
        primarySwatch: Colors.deepPurple,
      ),
      initialRoute: '/', // Start with the root route
      routes: {
        '/': (context) => const AuthGate(), // AuthGate handles initial routing logic
        '/signIn': (context) => const SignInScreen(),
        '/signUp': (context) => const SignUpScreen(),
        '/onboarding': (context) => const UserOnboardingScreen(),
        '/home': (context) => const HomeScreen(),
        '/chat': (context) => const ChatScreen(),
      },
    );
  }
}

class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  @override
  void initState() {
    super.initState();
    Supabase.instance.client.auth.onAuthStateChange.listen((data) async {
      final AuthChangeEvent event = data.event;
      final Session? session = data.session;
      if (event == AuthChangeEvent.signedIn) {
        // Check if user data exists in the 'users' table
        final user = session!.user;
        final userData = await Supabase.instance.client
            .from('users')
            .select('id')
            .eq('id', user.id)
            .maybeSingle();

        if (!mounted) return; // Check if widget is still mounted
        
        if (userData == null) {
          // User is signed in but onboarding not completed
          Navigator.of(context).pushReplacementNamed('/onboarding');
        } else {
          // User is signed in and onboarding completed
          Navigator.of(context).pushReplacementNamed('/home');
        }
      } else if (event == AuthChangeEvent.signedOut) {
        if (!mounted) return; // Check if widget is still mounted
        // Navigate to the sign in screen when signed out
        Navigator.of(context).pushReplacementNamed('/signIn');
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    // Initial check for session and onboarding status
    final session = Supabase.instance.client.auth.currentSession;

    if (session != null) {
      // User is signed in, check onboarding status
      return FutureBuilder<Map<String, dynamic>?>(
        future: Supabase.instance.client
            .from('users')
            .select('id')
            .eq('id', session.user.id)
            .maybeSingle(),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            // Show a loading indicator while checking onboarding status
            return const Scaffold(
              body: Center(child: CircularProgressIndicator()),
            );
          } else if (snapshot.hasData && snapshot.data != null) {
            // User data exists, navigate to home
            return const HomeScreen();
          } else {
            // User data does not exist, navigate to onboarding
            return const UserOnboardingScreen();
          }
        },
      );
    } else {
      // User is not signed in, navigate to sign in
      return const SignInScreen();
    }
  }
}
