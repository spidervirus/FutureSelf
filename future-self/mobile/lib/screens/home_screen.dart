import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  HomeScreenState createState() => HomeScreenState(); // Make public
}

class HomeScreenState extends State<HomeScreen> { // Make public
  String? _userName;
  String? _dailyMessage;
  List<String>? _reflectionQuestions;
  List<String>? _userGoals;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchUserDataAndDailyMessage();
  }

  Future<void> _fetchUserDataAndDailyMessage() async {
    try {
      final user = Supabase.instance.client.auth.currentUser;
      if (user == null) {
        // Should not happen if AuthGate works correctly
        setState(() {
          _error = 'User not authenticated.';
          _isLoading = false;
        });
        return;
      }

      // Fetch user data (including name and goals)
      final userData = await Supabase.instance.client
          .from('users')
          .select('name, top_goals')
          .eq('id', user.id)
          .single();

      _userName = userData['name'] as String;
      _userGoals = (userData['top_goals'] as List?)?.map((item) => item as String).toList();

      // Fetch the latest daily message (including reflection questions)
      final dailyMessageData = await Supabase.instance.client
          .from('daily_messages')
          .select('message_content, reflection_questions')
          .eq('user_id', user.id)
          .order('message_date', ascending: false)
          .limit(1)
          .maybeSingle();

      _dailyMessage = dailyMessageData?['message_content'] as String?;
      _reflectionQuestions = (dailyMessageData?['reflection_questions'] as List?)?.map((item) => item as String).toList();

    } catch (e) {
      _error = 'Failed to fetch data: ${e.toString()}';
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _signOut() async {
    try {
      await Supabase.instance.client.auth.signOut();
    } catch (error) {
      if (!mounted) return; // Check if widget is still mounted
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error signing out: ${error.toString()}')),
      );
    }
    // Navigation is handled by AuthGate listening to auth state changes
  }

  void _navigateToChat() {
    Navigator.pushNamed(context, '/chat', arguments: {'newChat': true});
  }

  void _navigateToReflection() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Navigate to Reflection Interface (Not Implemented)')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      drawer: Drawer(
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            DrawerHeader(
              decoration: BoxDecoration(
                color: Theme.of(context).primaryColor,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const CircleAvatar(
                    radius: 30,
                    backgroundColor: Colors.white,
                    child: Icon(Icons.person, size: 30, color: Colors.deepPurple),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    _userName ?? 'User',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const Text(
                    'Future Self App',
                    style: TextStyle(
                      color: Colors.white70,
                      fontSize: 14,
                    ),
                  ),
                ],
              ),
            ),
            ListTile(
              leading: const Icon(Icons.home),
              title: const Text('Home'),
              onTap: () => Navigator.pop(context),
            ),
            ListTile(
              leading: const Icon(Icons.chat),
              title: const Text('New Chat'),
              onTap: () {
                Navigator.pop(context);
                _navigateToChat();
              },
            ),
            ListTile(
              leading: const Icon(Icons.history),
              title: const Text('Past Chats'),
              onTap: () {
                Navigator.pop(context);
                Navigator.pushNamed(context, '/pastChats');
              },
            ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.person),
              title: const Text('Profile'),
              onTap: () {
                Navigator.pop(context);
                Navigator.pushNamed(context, '/profile');
              },
            ),
            ListTile(
              leading: const Icon(Icons.settings),
              title: const Text('Settings'),
              onTap: () {
                Navigator.pop(context);
                Navigator.pushNamed(context, '/settings');
              },
            ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.logout),
              title: const Text('Sign Out'),
              onTap: () {
                Navigator.pop(context);
                _signOut();
              },
            ),
          ],
        ),
      ),
      appBar: AppBar(
        title: const Text('Future Self Home'),
        actions: [
          IconButton(
            icon: const Icon(Icons.person),
            onPressed: () => Navigator.pushNamed(context, '/profile'),
            tooltip: 'Profile',
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.pushNamed(context, '/settings'),
            tooltip: 'Settings',
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: _signOut,
            tooltip: 'Sign Out',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('Error: $_error'))
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        'Welcome, ${_userName ?? 'User'}!',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 24.0),
                      Text(
                        'Message from your Future Self:',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 8.0),
                      _dailyMessage != null
                          ? Text(
                              _dailyMessage!,
                              style: Theme.of(context).textTheme.bodyMedium,
                            )
                          : const Text(
                              'No daily message available yet.',
                              style: TextStyle(fontStyle: FontStyle.italic),
                            ),
                      if (_reflectionQuestions != null && _reflectionQuestions!.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 16.0),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Reflection Questions:',
                                style: Theme.of(context).textTheme.titleLarge,
                              ),
                              const SizedBox(height: 8.0),
                              ListView.builder(
                                shrinkWrap: true,
                                physics: const NeverScrollableScrollPhysics(),
                                itemCount: _reflectionQuestions!.length,
                                itemBuilder: (context, index) {
                                  return Padding(
                                    padding: const EdgeInsets.only(bottom: 4.0),
                                    child: Text(
                                      '${index + 1}. ${_reflectionQuestions![index]}',
                                      style: Theme.of(context).textTheme.bodyMedium,
                                    ),
                                  );
                                },
                              ),
                            ],
                          ),
                        ),
                      if (_userGoals != null && _userGoals!.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 24.0),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Your Top Goals:',
                                style: Theme.of(context).textTheme.titleLarge,
                              ),
                              const SizedBox(height: 8.0),
                              ListView.builder(
                                shrinkWrap: true,
                                physics: const NeverScrollableScrollPhysics(),
                                itemCount: _userGoals!.length,
                                itemBuilder: (context, index) {
                                  return Padding(
                                    padding: const EdgeInsets.only(bottom: 4.0),
                                    child: Text(
                                      '\u2022 ${_userGoals![index]}',
                                      style: Theme.of(context).textTheme.bodyMedium,
                                    ),
                                  );
                                },
                              ),
                            ],
                          ),
                        ),
                      const SizedBox(height: 24.0),
                      Center(
                        child: Column(
                          children: [
                            ElevatedButton(
                              onPressed: _navigateToChat,
                              child: const Text('Chat with Future Self'),
                            ),
                            const SizedBox(height: 16.0),
                            ElevatedButton(
                              onPressed: _navigateToReflection,
                              child: const Text('Write a Reflection'),
                            ),
                          ],
                        ),
                      )
                    ],
                  ),
                ),
    );
  }
}