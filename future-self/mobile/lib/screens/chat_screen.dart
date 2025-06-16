import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:record/record.dart';
import 'dart:async';
import 'dart:typed_data';
import 'package:flutter_chat_types/flutter_chat_types.dart' as types;

import '../services/api_service.dart';
import '../services/api_exception.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  ChatScreenState createState() => ChatScreenState();
}

class ChatScreenState extends State<ChatScreen> {
  final TextEditingController _messageController = TextEditingController();
  final List<types.Message> _messages = [];
  final supabase = Supabase.instance.client;
  bool _isRecording = false;
  final _recorder = AudioRecorder();
  StreamSubscription<Uint8List>? _audioStreamSubscription;
  final List<int> _audioBytes = [];
  final ApiService _apiService = ApiService();
  
  String _preferredCommunicationMethod = 'chat';
  bool _isLoadingPreferences = true;
  bool _isLoadingHistory = false; // Declare _isLoadingHistory
  
  Timer? _recordingTimer;
  int _recordingDuration = 0;

  List<Map<String, dynamic>> _pastChatSessions = [];
  bool _isLoadingPastChats = true;
  bool _isInitialLoad = true; // Flag to manage initial message loading

  @override
  void initState() {
    super.initState();
    _loadUserPreferences();
    _fetchPastChatSessions();
   }

  Future<void> _fetchPastChatSessions() async {
    if (!mounted) return;
    setState(() {
      _isLoadingPastChats = true;
    });
    try {
      final user = supabase.auth.currentUser;
      if (user != null) {
        final response = await supabase
            .from('chat_messages')
            .select('content, created_at, author_id')
            .eq('user_id', user.id)
            .order('created_at', ascending: true); // Changed to true

        if (mounted) {
          final Map<String, Map<String, dynamic>> groupedChats = {};
          for (var msgData in response) {
            final messageContent = msgData['content'] as String;
            final createdAt = DateTime.parse(msgData['created_at']);
            final dateStr = createdAt.toLocal().toString().substring(0, 10);
            final authorId = msgData['author_id'] as String;

            // If it's a user message and we haven't recorded a title for this day yet
            if (authorId == user.id && !groupedChats.containsKey(dateStr)) {
              groupedChats[dateStr] = {
                'id': msgData['created_at'], // Timestamp of the first user message of the day
                'title': messageContent.length > 30 ? '${messageContent.substring(0, 27)}...' : messageContent,
                'subtitle': 'Chat from $dateStr',
                'data': msgData 
              };
            }
          }
          if (mounted) {
            setState(() {
              _pastChatSessions = groupedChats.values.toList();
              // Sort by the 'id' (timestamp of the title message) descending to show newest sessions first
              _pastChatSessions.sort((a, b) => (b['id'] as String).compareTo(a['id'] as String));
              _isLoadingPastChats = false;
            });
          }
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoadingPastChats = false;
        });
        // Optionally show a snackbar or log error
        debugPrint('Error fetching past chat sessions for drawer: $e');
      }
    }
  }

  void _navigateToPastChat(Map<String, dynamic> chatData) {
    debugPrint('Navigate to past chat: ${chatData['title']}');
    Navigator.pop(context); // Close the drawer
    final String fullTimestamp = chatData['id'] as String;
    final String chatDate = fullTimestamp.substring(0, 10);

    if (mounted) {
      setState(() {
        _messages.clear(); // Clear current messages before loading a past chat
      });
    }
    _loadMessageHistory(specificChatDate: chatDate);
    _isInitialLoad = false; // We've explicitly loaded a chat, so initial default load is no longer relevant
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final arguments = ModalRoute.of(context)?.settings.arguments as Map?;

    if (arguments?['newChat'] == true) {
      // Explicitly starting a new chat - clear messages and don't load history
      if (mounted) {
        setState(() {
          _messages.clear();
        });
      }
      _isInitialLoad = false; // A new chat means initial load (of history) is not needed
    } else if (_isInitialLoad && arguments == null) {
      // Only load history on initial load if no arguments are passed
      // This prevents loading history when refreshing or navigating without explicit newChat
      _loadMessageHistory();
      _isInitialLoad = false;
    } else {
      // For any other case (refresh, navigation without arguments), start fresh
      if (mounted && _messages.isEmpty) {
        setState(() {
          _messages.clear(); // Ensure we start with a clean slate
        });
      }
      _isInitialLoad = false;
    }
  }

  // Add this method to fetch user preferences
  Future<void> _loadUserPreferences() async {
    try {
      final user = supabase.auth.currentUser;
      if (user != null) {
        // Add a small delay to ensure the session is fully established
        await Future.delayed(const Duration(milliseconds: 100));
        
        final response = await supabase
            .from('users')
            .select('preferred_communication')
            .eq('id', user.id)
            .single();
        
        if (mounted) {
          setState(() {
            _preferredCommunicationMethod = response['preferred_communication'] ?? 'chat';
            _isLoadingPreferences = false;
          });
        }
      } else {
        // User not authenticated, redirect to sign in
        if (mounted) {
          Navigator.of(context).pushReplacementNamed('/signIn');
        }
      }
    } catch (e) {
      // If there's an error, default to chat mode
      if (mounted) {
        setState(() {
          _preferredCommunicationMethod = 'chat';
          _isLoadingPreferences = false;
        });
      }
    }
  }

  // Add method to load message history
  Future<void> _loadMessageHistory({String? specificChatDate}) async {
    if (_isLoadingHistory) return;
    if (mounted) {
      setState(() {
        _isLoadingHistory = true;
        _messages.clear(); // Clear messages when loading starts
      });
    }

    // Clear messages only if we are loading a new set (either general history or a specific chat)
    // This was moved from _navigateToPastChat to here to ensure it happens before any load.
    // if (mounted) { // This block is now redundant due to the change above
    //   setState(() {
    //     // Consider adding a loading indicator for messages if it's a long operation
    //   });
    // }
    try {
      final user = supabase.auth.currentUser;
      if (user != null) {
        // Basic implementation: if specificChatDate is provided, you'd query based on that.
        // This part needs to be fleshed out based on how chat sessions are identified and stored.
        // For example, if 'id' in _pastChatSessions corresponds to a 'session_id' or a 'created_at' timestamp
        // that can be used to filter messages.
        //
        // For now, if specificChatDate is NOT null, we assume we want to load messages for that chat.
        // If it IS null, we load the general history.
        // This is a placeholder for more specific logic.

        var query = supabase // Use 'var' or the specific builder type
            .from('chat_messages')
            .select()
            .eq('user_id', user.id);

        if (specificChatDate != null) {
          // Assumes specificChatDate is in 'YYYY-MM-DD' format
          final DateTime startDate = DateTime.parse(specificChatDate);
          final DateTime endDate = startDate.add(const Duration(days: 1));
          query = query
              .gte('created_at', startDate.toIso8601String())
              .lt('created_at', endDate.toIso8601String());
        }

        // The 'order' method returns a PostgrestTransformBuilder, so we can chain 'limit' after it.
        final response = await query
            .order('created_at', ascending: false)
            .limit(specificChatDate == null ? 50 : 100); // Load more if it's a specific chat
        
        if (!mounted) return;

        final loadedMessages = response.map<types.Message>((data) {
          return types.TextMessage(
            author: types.User(id: data['author_id']),
            createdAt: DateTime.parse(data['created_at']).millisecondsSinceEpoch,
            id: data['message_id'],
            text: data['content'],
          );
        }).toList();
        
        if (mounted) {
          setState(() {
            // _messages.clear(); // Already cleared when _isLoadingHistory was set to true
            _messages.insertAll(0, loadedMessages.reversed);
          });
        }
      }
    } catch (e) {
      debugPrint('Error loading message history: $e');
      if (mounted) {
        // Optionally, set an error state or show a snackbar
      }
    } finally {
      if (mounted) {
        setState(() {
          _isLoadingHistory = false;
        });
      }
    }
  }

  // Add method to save messages to Supabase
  Future<void> _saveMessageToDatabase(types.Message message) async {
    try {
      final user = supabase.auth.currentUser;
      if (user != null && message is types.TextMessage) {
        await supabase.from('chat_messages').insert({
          'user_id': user.id,
          'message_id': message.id,
          'content': message.text,
          'author_id': message.author.id,
          'created_at': DateTime.fromMillisecondsSinceEpoch(message.createdAt!).toIso8601String(),
        });
      }
    } catch (e) {
      debugPrint('Error saving message to database: $e');
    }
  }

  @override
  void dispose() {
    _messageController.dispose();
    _recorder.dispose();
    _audioStreamSubscription?.cancel();
    _recordingTimer?.cancel();
    super.dispose();
  }

  Future<void> _sendMessage(String text) async {
    final user = supabase.auth.currentUser;
    if (user == null) {
      setState(() {
        _messages.add(types.TextMessage(
          author: types.User(id: 'system'),
          createdAt: DateTime.now().millisecondsSinceEpoch,
          id: DateTime.now().millisecondsSinceEpoch.toString(),
          text: 'Error: User not authenticated.',
        ));
      });
      return;
    }

    if (text.isNotEmpty) {
      final userMessage = types.TextMessage(
        author: types.User(id: user.id),
        createdAt: DateTime.now().millisecondsSinceEpoch,
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        text: text,
      );
      setState(() {
        _messages.add(userMessage);
      });
      _saveMessageToDatabase(userMessage);
      _messageController.clear();

      try {
        // Create a placeholder message for the AI response that will be updated incrementally
        final aiMessageId = DateTime.now().millisecondsSinceEpoch.toString();
        final aiPlaceholderMessage = types.TextMessage(
          author: types.User(id: 'future_self'),
          createdAt: DateTime.now().millisecondsSinceEpoch,
          id: aiMessageId,
          text: '', // Start with empty text that will be filled incrementally
        );
        
        if (mounted) {
          setState(() {
            _messages.add(aiPlaceholderMessage);
          });
        }
        
        // Use the streaming API
        String completeResponse = '';
        await for (final chunk in _apiService.streamMessage(text, user.id)) {
          completeResponse += chunk;
          if (mounted) {
            setState(() {
              // Find the placeholder message and update its text
              final index = _messages.indexWhere((msg) => msg.id == aiMessageId);
              if (index != -1) {
                final currentMessage = _messages[index] as types.TextMessage;
                _messages[index] = currentMessage.copyWith(
                  text: completeResponse,
                );
              }
            });
          }
        }
        
        // Save the complete message to the database
        final finalAiMessage = types.TextMessage(
          author: types.User(id: 'future_self'),
          createdAt: DateTime.now().millisecondsSinceEpoch,
          id: aiMessageId,
          text: completeResponse,
        );
        _saveMessageToDatabase(finalAiMessage);

      } on ApiException catch (e) {
        if (mounted) {
          setState(() {
            _messages.add(types.TextMessage(
              author: types.User(id: 'future_self'),
              createdAt: DateTime.now().millisecondsSinceEpoch,
              id: DateTime.now().millisecondsSinceEpoch.toString(),
              text: 'AI Error: ${e.message}',
            ));
          });
        }
      } catch (e) {
        if (mounted) {
          setState(() {
            _messages.add(types.TextMessage(
              author: types.User(id: 'system'),
              createdAt: DateTime.now().millisecondsSinceEpoch,
              id: DateTime.now().millisecondsSinceEpoch.toString(),
              text: 'Error sending message: ${e.toString()}',
            ));
          });
        }
      }
    }
  }

  Future<void> _sendAudioForTranscription(Uint8List audioBytes) async {
    final user = supabase.auth.currentUser;
    if (user == null) {
      // Handle user not authenticated case if necessary, e.g., show a message
      debugPrint("User not authenticated for transcription");
      if (mounted) {
        setState(() {
          // Remove placeholder if it exists
          _messages.removeWhere((msg) => 
            msg is types.TextMessage && msg.text == '🎤 Processing voice message...');
          // Add error message
          _messages.add(types.TextMessage(
            author: types.User(id: 'system'),
            createdAt: DateTime.now().millisecondsSinceEpoch,
            id: DateTime.now().millisecondsSinceEpoch.toString(),
            text: 'Error: User not authenticated for transcription.',
          ));
        });
      }
      return;
    }
    try {
      final transcribedText = await _apiService.transcribeAudio(audioBytes, user.id);

      if (mounted) {
        setState(() {
          final index = _messages.indexWhere((msg) => 
            msg is types.TextMessage && msg.text == '🎤 Processing voice message...');
          if (index != -1) {
            final originalMessage = _messages[index] as types.TextMessage;
            _messages[index] = originalMessage.copyWith(
              text: transcribedText,
              createdAt: DateTime.now().millisecondsSinceEpoch,
              author: types.User(id: supabase.auth.currentUser?.id ?? 'user'),
            );
          } else {
            _messages.add(types.TextMessage(
              author: types.User(id: supabase.auth.currentUser?.id ?? 'user'),
              createdAt: DateTime.now().millisecondsSinceEpoch,
              id: DateTime.now().millisecondsSinceEpoch.toString(),
              text: transcribedText,
            ));
          }
        });
      }

      if (mounted) {
        setState(() {
          _messages.add(types.TextMessage(
            author: types.User(id: 'future_self'),
            createdAt: DateTime.now().millisecondsSinceEpoch,
            id: DateTime.now().millisecondsSinceEpoch.toString(),
            text: 'Future Self is thinking...',
          ));
        });
      }
      await _sendMessage(transcribedText);
    } on ApiException catch (e) {
      if (mounted) {
        setState(() {
          final index = _messages.indexWhere((msg) => 
            msg is types.TextMessage && msg.text == '🎤 Processing voice message...');
          if (index != -1) {
            final originalMessage = _messages[index] as types.TextMessage;
            _messages[index] = originalMessage.copyWith(
              text: 'Transcription failed. Error: ${e.message}',
              createdAt: DateTime.now().millisecondsSinceEpoch,
              author: types.User(id: 'future_self'),
            );
          } else {
            _messages.add(types.TextMessage(
              author: types.User(id: 'future_self'),
              createdAt: DateTime.now().millisecondsSinceEpoch,
              id: DateTime.now().millisecondsSinceEpoch.toString(),
              text: 'Transcription failed. Error: ${e.message}',
            ));
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          final placeholderIndex = _messages.indexWhere((msg) => 
            msg is types.TextMessage && msg.text == '🎤 Processing voice message...');
          if (placeholderIndex != -1) {
            final originalMessage = _messages[placeholderIndex] as types.TextMessage;
            _messages[placeholderIndex] = originalMessage.copyWith(
              text: 'Transcription error: ${e.toString()}',
              createdAt: DateTime.now().millisecondsSinceEpoch,
              author: types.User(id: 'system'),
            );
          } else {
            _messages.add(types.TextMessage(
              author: types.User(id: 'system'),
              createdAt: DateTime.now().millisecondsSinceEpoch,
              id: DateTime.now().millisecondsSinceEpoch.toString(),
              text: 'Transcription error: ${e.toString()}',
            ));
          }
        });
      }
    }
  }

  // Audio playback functionality has been removed


  @override
  Widget build(BuildContext context) {
    if (_isLoadingPreferences) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Chat with Future Self'),
        actions: [
          IconButton(
            icon: Icon(_preferredCommunicationMethod == 'voice' ? Icons.mic : Icons.chat_bubble_outline),
            onPressed: () {
              setState(() {
                _preferredCommunicationMethod = _preferredCommunicationMethod == 'voice' ? 'chat' : 'voice';
                // You might want to save this preference to Supabase as well
                final user = supabase.auth.currentUser;
                if (user != null) {
                  supabase.from('users').update({'preferred_communication': _preferredCommunicationMethod}).eq('id', user.id);
                }
              });
            },
          ),
          IconButton(
            icon: const Icon(Icons.history),
            onPressed: () {
              // This can be used to toggle a view or navigate to a history screen
              // For now, let's just refresh the current chat history as an example
              _loadMessageHistory();
            },
          ),
        ],
      ),
      drawer: Drawer(
        child: ListView(
          padding: EdgeInsets.zero,
          children: <Widget>[
            const DrawerHeader(
              decoration: BoxDecoration(
                color: Colors.blue,
              ),
              child: Text('Past Chats', style: TextStyle(color: Colors.white, fontSize: 24)),
            ),
            if (_isLoadingPastChats)
              const Center(child: CircularProgressIndicator())
            else if (_pastChatSessions.isEmpty)
              const ListTile(title: Text('No past chats found'))
            else
              ..._pastChatSessions.map((chat) => ListTile(
                    title: Text(chat['title'] ?? 'Chat'),
                    subtitle: Text(chat['subtitle'] ?? 'Tap to view'),
                    onTap: () => _navigateToPastChat(chat),
                  )),
            ListTile(
              leading: const Icon(Icons.add_circle_outline),
              title: const Text('Start New Chat'),
              onTap: () {
                Navigator.pop(context); // Close drawer
                if (mounted) {
                  setState(() {
                    _messages.clear();
                    _isInitialLoad = false; // Mark that we are starting fresh
                  });
                }
              },
            ),
          ],
        ),
      ),
      body: Column(
        children: <Widget>[
          if (_isLoadingHistory) // Show loading indicator for message history
            const Padding(
              padding: EdgeInsets.all(8.0),
              child: Center(child: CircularProgressIndicator()),
            ),
          Expanded(
            child: ListView.builder(
              reverse: true,
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final message = _messages[_messages.length - 1 - index];
                return _buildMessageBubble(message);
              },
            ),
          ),
          if (_isRecording)
            Padding(
              padding: const EdgeInsets.all(8.0),
              child: Text('Recording: ${_recordingDuration}s', style: const TextStyle(color: Colors.red)),
            ),
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Row(
              children: <Widget>[
                if (_preferredCommunicationMethod == 'chat' || _isRecording)
                  Expanded(
                    child: TextField(
                      controller: _messageController,
                      decoration: InputDecoration(
                        hintText: _isRecording ? 'Recording...' : 'Type a message',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(25.0),
                        ),
                        filled: true,
                        fillColor: Colors.grey[200],
                        contentPadding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 10.0),
                      ),
                      enabled: !_isRecording, // Disable text field when recording
                      onSubmitted: _isRecording ? null : (text) => _sendMessage(text),
                    ),
                  ),
                if (_preferredCommunicationMethod == 'chat' && !_isRecording)
                  IconButton(
                    icon: const Icon(Icons.send),
                    onPressed: () => _sendMessage(_messageController.text),
                  ),
                if (_preferredCommunicationMethod == 'voice')
                  IconButton(
                    icon: Icon(_isRecording ? Icons.stop : Icons.mic),
                    onPressed: _isRecording ? _stopRecording : _startRecording,
                    iconSize: 30.0,
                    color: _isRecording ? Colors.red : Theme.of(context).primaryColor,
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
  
  // Helper method to format timestamp for message bubbles
  String _formatTimestamp(int timestamp) {
    final dateTime = DateTime.fromMillisecondsSinceEpoch(timestamp);
    final now = DateTime.now();
    final difference = now.difference(dateTime);
    
    if (difference.inMinutes < 1) {
      return 'Just now';
    } else if (difference.inHours < 1) {
      return '${difference.inMinutes}m ago';
    } else if (difference.inDays < 1) {
      return '${difference.inHours}h ago';
    } else {
      return '${dateTime.day}/${dateTime.month}';
    }
  }

  // Helper method to build message bubbles
  Widget _buildMessageBubble(types.Message message) {
    final isUserMessage = message.author.id == supabase.auth.currentUser?.id;
    final alignment = isUserMessage ? Alignment.centerRight : Alignment.centerLeft;
    final color = isUserMessage ? Colors.blue[600] : Colors.grey[300];
    final textColor = isUserMessage ? Colors.white : Colors.black87;

    if (message is types.TextMessage) {
      return Align(
        alignment: alignment,
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 4.0, horizontal: 8.0),
          padding: const EdgeInsets.all(12.0),
          constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.75,
          ),
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(12.0),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                message.text,
                style: TextStyle(color: textColor, fontSize: 16.0),
              ),
              const SizedBox(height: 4.0),
              Text(
                _formatTimestamp(message.createdAt!),
                style: TextStyle(color: textColor.withAlpha((0.7 * 255).round()), fontSize: 10.0),
              ),
              // Removed audio playback buttons
            ],
          ),
        ),
      );
    }
    return const SizedBox.shrink();
  }

  Future<void> _startRecording() async {
    try {
      if (await _recorder.hasPermission()) {
        _audioBytes.clear();
        _recordingDuration = 0;
        _recordingTimer?.cancel();
        _recordingTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
          if (mounted) {
            setState(() {
              _recordingDuration++;
            });
          }
        });

        final stream = await _recorder.startStream(const RecordConfig(encoder: AudioEncoder.pcm16bits));
        _audioStreamSubscription = stream.listen((data) {
          _audioBytes.addAll(data);
        });

        if (mounted) {
          setState(() {
            _isRecording = true;
            _recordingDuration = 0;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isRecording = false;
          _recordingDuration = 0;
        });
      }
      debugPrint('Error starting recording: $e');
    }
  }

  Future<void> _stopRecording() async {
    try {
      await _recorder.stop();
      await _audioStreamSubscription?.cancel();
      _recordingTimer?.cancel();
      if (mounted) {
        setState(() {
          _isRecording = false;
          _recordingDuration = 0;
        });
      }
      if (_audioBytes.isNotEmpty) {
        final user = supabase.auth.currentUser;
        if (user != null) {
          // Add a placeholder message for the voice input
          final placeholderMessage = types.TextMessage(
            author: types.User(id: user.id),
            createdAt: DateTime.now().millisecondsSinceEpoch,
            id: DateTime.now().millisecondsSinceEpoch.toString(),
            text: '🎤 Processing voice message...',
          );
          if (mounted) {
            setState(() {
              _messages.add(placeholderMessage);
            });
          }
          await _sendAudioForTranscription(Uint8List.fromList(_audioBytes));
        }
      }
      _audioBytes.clear();
    } catch (e) {
      _recordingTimer?.cancel();
      if (mounted) {
        setState(() {
          _isRecording = false;
          _recordingDuration = 0;
        });
      }
      debugPrint('Error stopping recording: $e');
    }
  }
}