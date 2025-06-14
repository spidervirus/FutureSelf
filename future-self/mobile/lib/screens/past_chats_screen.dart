import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
// Removed unused import: import 'package:flutter_chat_types/flutter_chat_types.dart' as types;

class PastChatsScreen extends StatefulWidget {
  const PastChatsScreen({super.key});

  @override
  State<PastChatsScreen> createState() => _PastChatsScreenState();
}

class _PastChatsScreenState extends State<PastChatsScreen> {
  final supabase = Supabase.instance.client;
  List<Map<String, dynamic>> _chatSessions = []; // Or List<types.Message> if showing individual messages
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchPastChats();
  }

  Future<void> _fetchPastChats() async {
    setState(() {
      _isLoading = true;
    });
    try {
      final user = supabase.auth.currentUser;
      if (user != null) {
        final response = await supabase
            .from('chat_messages')
            .select('content, created_at, author_id')
            .eq('user_id', user.id)
            .order('created_at', ascending: false);

        if (mounted) {
          final Map<String, Map<String, dynamic>> groupedChats = {};
          for (var msgData in response) {
            final messageContent = msgData['content'] as String;
            final createdAt = DateTime.parse(msgData['created_at']);
            final dateStr = createdAt.toLocal().toString().substring(0, 10); // Group by YYYY-MM-DD

            // For simplicity, we'll use the first user message of a day as the title.
            // More sophisticated grouping would require session IDs or conversation markers.
            if (!groupedChats.containsKey(dateStr) && msgData['author_id'] == user.id) {
              groupedChats[dateStr] = {
                'id': msgData['created_at'], // Use timestamp of the first message as ID for the group
                'title': messageContent.length > 40 ? '${messageContent.substring(0, 37)}...' : messageContent,
                'subtitle': 'Chat from $dateStr',
                'data': msgData // Store the first message data
              };
            } else if (groupedChats.containsKey(dateStr) && msgData['author_id'] == user.id) {
              // If we already have an entry for this date, but it was an AI message first,
              // and now we found a user message, prefer the user message as title.
              // This is a simple heuristic.
              if (groupedChats[dateStr]!['data']['author_id'] != user.id) {
                 groupedChats[dateStr]!['title'] = messageContent.length > 40 ? '${messageContent.substring(0, 37)}...' : messageContent;
                 groupedChats[dateStr]!['data'] = msgData; // Update to user's message data
              }
            }
            // If no user message is found for a day, that day won't be listed as a separate chat session.
            // You could add logic here to handle days with only AI responses if needed.
          }

          setState(() {
            _chatSessions = groupedChats.values.toList();
            // Sort by date again, as map iteration order is not guaranteed for all Dart versions/platforms
            _chatSessions.sort((a, b) => (b['id'] as String).compareTo(a['id'] as String));
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error fetching past chats: $e')),
        );
      }
    }
  }

  void _navigateToChat(Map<String, dynamic> chatData) {
    // Navigate back to ChatScreen, passing data to load this specific chat
    // This part needs to be implemented based on how ChatScreen can load specific chats
    // For example, by passing a message ID, a date range, or a session ID if you have one.
    // Navigator.pushReplacementNamed(context, '/chat', arguments: {'chatId': chatData['id']});
    debugPrint('Navigate to chat: ${chatData['title']}');
     Navigator.pop(context); // Go back to chat screen for now
     // Potentially, you'd want to pass arguments to ChatScreen to load this specific chat
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Past Chats'),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _chatSessions.isEmpty
              ? const Center(child: Text('No past chats found.'))
              : ListView.builder(
                  itemCount: _chatSessions.length,
                  itemBuilder: (context, index) {
                    final chat = _chatSessions[index];
                    return ListTile(
                      title: Text(chat['title'] ?? 'Chat Session'),
                      subtitle: Text(chat['subtitle'] ?? 'Tap to view'),
                      onTap: () => _navigateToChat(chat),
                    );
                  },
                ),
    );
  }
}