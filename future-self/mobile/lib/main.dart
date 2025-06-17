import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
// import 'package:flutter_dotenv/flutter_dotenv.dart'; // Removed unused import
import 'config.dart'; // Import the config file
import 'screens/auth/sign_in_screen.dart';
import 'screens/auth/sign_up_screen.dart';
import 'screens/home_screen.dart';
import 'screens/user_onboarding_screen.dart';
import 'screens/chat_screen.dart';
import 'screens/past_chats_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/settings_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized(); // Ensure widgets are initialized
  await ApiConfig.initializeSupabase(); // Use the method from config.dart

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
        fontFamily: 'NotoSans',
        textTheme: const TextTheme().apply(
          fontFamilyFallback: ['NotoSans', 'NotoColorEmoji', 'NotoSansSymbols'],
        ),
      ),
      initialRoute: '/', // Start with the root route
      routes: {
        '/': (context) => const AuthGate(), // AuthGate handles initial routing logic
        '/signIn': (context) => const SignInScreen(),
        '/signUp': (context) => const SignUpScreen(),
        '/onboarding': (context) => const UserOnboardingScreen(),
        '/home': (context) => const HomeScreen(),
        '/chat': (context) => const ChatScreen(),
        '/pastChats': (context) => const PastChatsScreen(),
        '/profile': (context) => const ProfileScreen(),
        '/settings': (context) => const SettingsScreen(),
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
