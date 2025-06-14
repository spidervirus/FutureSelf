import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:record/record.dart';
import 'package:audioplayers/audioplayers.dart';
import 'dart:async';
import 'dart:typed_data';
import 'package:flutter_chat_types/flutter_chat_types.dart' as types;

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
  final AudioPlayer _audioPlayer = AudioPlayer();
  final String backendUrl = 'http://localhost:8000';
  
  String _preferredCommunicationMethod = 'chat';
  bool _isLoadingPreferences = true;
  bool _isLoadingHistory = false; // Declare _isLoadingHistory
  
  Timer? _recordingTimer;
  int _recordingDuration = 0;
  bool _isPlayingAudio = false;
  String? _currentlyPlayingMessageId;

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
    _audioPlayer.dispose();
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

      final url = Uri.parse('$backendUrl/chat');

      try {
        final response = await http.post(
          url,
          headers: <String, String>{
            'Content-Type': 'application/json; charset=UTF-8',
          },
          body: jsonEncode(<String, String>{
            'message': text,
            'user_id': user.id, // Ensure user.id is passed
          }),
        );

        if (response.statusCode == 200) {
          final responseData = jsonDecode(response.body);
          final aiResponseContent = responseData['response'];

          final aiMessage = types.TextMessage(
            author: types.User(id: 'future_self'),
            createdAt: DateTime.now().millisecondsSinceEpoch,
            id: DateTime.now().millisecondsSinceEpoch.toString(),
            text: aiResponseContent,
          );
          setState(() {
            _messages.add(aiMessage);
          });
          _saveMessageToDatabase(aiMessage);

          await _synthesizeSpeech(aiResponseContent, aiMessage.id);
        } else {
          setState(() {
            _messages.add(types.TextMessage(
              author: types.User(id: 'future_self'),
              createdAt: DateTime.now().millisecondsSinceEpoch,
              id: DateTime.now().millisecondsSinceEpoch.toString(),
              text: 'AI Error: ${response.statusCode} - ${response.body}',
            ));
          });
        }
      } catch (e) {
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

  Future<void> _sendAudioForTranscription(Uint8List audioBytes) async {
    final url = Uri.parse('$backendUrl/transcribe');

    try {
      final response = await http.post(
        url,
        headers: {
          'Content-Type': 'application/octet-stream',
        },
        body: audioBytes,
      );

      if (response.statusCode == 200) {
        final responseData = jsonDecode(response.body);
        final transcribedText = responseData['transcribed_text'];

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

        setState(() {
          _messages.add(types.TextMessage(
            author: types.User(id: 'future_self'),
            createdAt: DateTime.now().millisecondsSinceEpoch,
            id: DateTime.now().millisecondsSinceEpoch.toString(),
            text: 'Future Self is thinking...',
          ));
        });
        await _sendMessage(transcribedText);
      } else {
        setState(() {
          final index = _messages.indexWhere((msg) => 
            msg is types.TextMessage && msg.text == '🎤 Processing voice message...');
          if (index != -1) {
            final originalMessage = _messages[index] as types.TextMessage;
            _messages[index] = originalMessage.copyWith(
              text: 'Transcription failed. Error: ${response.body}',
              createdAt: DateTime.now().millisecondsSinceEpoch,
              author: types.User(id: 'future_self'),
            );
          } else {
            _messages.add(types.TextMessage(
              author: types.User(id: 'future_self'),
              createdAt: DateTime.now().millisecondsSinceEpoch,
              id: DateTime.now().millisecondsSinceEpoch.toString(),
              text: 'Transcription failed. Error: ${response.body}',
            ));
          }
        });
      }
    } catch (e) {
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

  // Enhanced synthesis method with playback controls
  Future<void> _synthesizeSpeech(String textToSynthesize, String messageId) async {
    final url = Uri.parse('$backendUrl/synthesize');
    final user = supabase.auth.currentUser;
    
    if (user == null) {
      debugPrint('Error: No authenticated user found for speech synthesis');
      return;
    }
    
    try {
      final response = await http.post(
        url,
        headers: <String, String>{'Content-Type': 'application/json; charset=UTF-8'},
        body: jsonEncode(<String, String>{
          'text': textToSynthesize,
          'user_id': user.id,
        }),
      );
      
      if (response.statusCode == 200) {
        final responseData = jsonDecode(response.body);
        final audioContentBase64 = responseData['audio_content'];
        final audioBytes = base64Decode(audioContentBase64);
        
        if (!mounted) return;
        setState(() {
          _isPlayingAudio = true;
          _currentlyPlayingMessageId = messageId;
        });
        
        await _audioPlayer.play(BytesSource(audioBytes));
        
        // Listen for completion
        _audioPlayer.onPlayerComplete.first.then((_) {
          if (!mounted) return;
          setState(() {
            _isPlayingAudio = false;
            _currentlyPlayingMessageId = null;
          });
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isPlayingAudio = false;
        _currentlyPlayingMessageId = null;
      });
      debugPrint('Error synthesizing speech: $e');
    }
  }

  // Add timestamp formatting method
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
            borderRadius: BorderRadius.only(
              topLeft: const Radius.circular(16.0),
              topRight: const Radius.circular(16.0),
              bottomLeft: Radius.circular(isUserMessage ? 16.0 : 4.0),
              bottomRight: Radius.circular(isUserMessage ? 4.0 : 16.0),
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.1),
                blurRadius: 4.0,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                message.text,
                style: TextStyle(
                  color: textColor,
                  fontSize: 16.0,
                ),
              ),
              const SizedBox(height: 4.0),
              if (!isUserMessage && message.text != 'Future Self is thinking...' && message.text != '🎤 Processing voice message...')
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      icon: Icon(
                        _currentlyPlayingMessageId == message.id && _isPlayingAudio
                            ? Icons.pause_circle
                            : Icons.play_circle,
                        color: textColor.withValues(alpha: 0.7),
                        size: 20.0,
                      ),
                      onPressed: () {
                        if (_currentlyPlayingMessageId == message.id && _isPlayingAudio) {
                          _audioPlayer.pause();
                           setState(() {
                            _isPlayingAudio = false;
                          });
                        } else {
                          _synthesizeSpeech(message.text, message.id);
                        }
                      },
                    ),
                    Text(
                      _formatTimestamp(message.createdAt!),
                      style: TextStyle(
                        color: textColor.withValues(alpha: 0.7),
                        fontSize: 12.0,
                      ),
                    ),
                  ],
                )
              else
                Text(
                  _formatTimestamp(message.createdAt!),
                  style: TextStyle(
                    color: textColor.withValues(alpha: 0.7),
                    fontSize: 12.0,
                  ),
                ),
            ],
          ),
        ),
      );
    }
    return Container();
  }

  Widget _buildInputArea() {
    return Padding(
      padding: const EdgeInsets.all(8.0),
      child: Row(
        children: <Widget>[
          // Show text input only if preferred method is 'chat'
          if (_preferredCommunicationMethod == 'chat') ...[
            Expanded(
              child: TextField(
                controller: _messageController,
                readOnly: _isRecording,
                enabled: !_isRecording,
                maxLines: null,
                textInputAction: TextInputAction.send,
                decoration: InputDecoration(
                  hintText: 'Type your message to Future Self...',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(25.0),
                    borderSide: BorderSide.none,
                  ),
                  filled: true,
                  fillColor: Colors.grey[100],
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 20.0, 
                    vertical: 12.0
                  ),
                  suffixIcon: _messageController.text.isNotEmpty 
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _messageController.clear();
                          setState(() {});
                        },
                      )
                    : null,
                ),
                onChanged: (text) => setState(() {}),
                onSubmitted: (_) => _sendMessage(_messageController.text),
              ),
            ),
            const SizedBox(width: 8.0),
          ],
          
          // Show voice recording button for both modes
          Container(
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: _isRecording ? Colors.red.withValues(alpha: 0.1) : null,
            ),
            child: IconButton(
              iconSize: _isRecording ? 32.0 : 24.0,
              icon: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                child: Icon(
                  _isRecording ? Icons.stop : Icons.mic,
                  color: _isRecording ? Colors.red : Colors.blue,
                ),
              ),
              onPressed: _onRecordButtonPress,
            ),
          ),
          if (_isRecording)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8.0),
              child: Text(
                '${_recordingDuration}s',
                style: const TextStyle(
                  color: Colors.red,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          
          // Show send button only if preferred method is 'chat' and not recording
          if (_preferredCommunicationMethod == 'chat' && !_isRecording)
            IconButton(
              icon: const Icon(Icons.send),
              onPressed: () => _sendMessage(_messageController.text),
            ),
        ],
      ),
    );
  }

  void _onRecordButtonPress() {
    if (_isRecording) {
      _stopRecording();
    } else {
      _startRecording();
    }
  }

  Future<void> _startRecording() async {
    try {
      if (await _recorder.hasPermission()) {
        _audioBytes.clear();
        _recordingDuration = 0;
        
        // Start timer
        _recordingTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
          if (!mounted) {
            timer.cancel();
            return;
          }
          setState(() {
            _recordingDuration++;
          });
        });
        
        // Use PCM16 bits encoder for streaming as it's more widely supported
        final stream = await _recorder.startStream(const RecordConfig(encoder: AudioEncoder.pcm16bits));
    
        _audioStreamSubscription = stream.listen(
          (audioChunk) {
            _audioBytes.addAll(audioChunk);
          },
          onDone: () {
            debugPrint('Recording stream done');
          },
          onError: (e) {
            debugPrint('Recording stream error: $e');
            if (mounted) {
              setState(() {
                _isRecording = false;
                _recordingDuration = 0;
              });
            }
          },
        );
    
        setState(() {
          _isRecording = true;
        });
      } else {
        debugPrint('Recording permission not granted');
      }
    } catch (e) {
      debugPrint('Error starting recording: $e');
      if (mounted) {
        setState(() {
          _isRecording = false;
          _recordingDuration = 0;
        });
      }
    }
  }

  Future<void> _stopRecording() async {
    try {
      await _recorder.stop();
      await _audioStreamSubscription?.cancel();
      _recordingTimer?.cancel();
      
      if (!mounted) return;
      setState(() {
        _isRecording = false;
        _recordingDuration = 0;
      });
    
      if (_audioBytes.isNotEmpty) {
        final audioBytesToSend = Uint8List.fromList(_audioBytes);
        _audioBytes.clear();
    
        setState(() {
          _messages.add(types.TextMessage(
            author: types.User(id: supabase.auth.currentUser?.id ?? 'user'),
            createdAt: DateTime.now().millisecondsSinceEpoch,
            id: DateTime.now().millisecondsSinceEpoch.toString(),
            text: '🎤 Processing voice message...',
          ));
        });
    
        await _sendAudioForTranscription(audioBytesToSend);
      }
    } catch (e) {
      _recordingTimer?.cancel();
      if (!mounted) return;
      setState(() {
        _isRecording = false;
        _recordingDuration = 0;
      });
      debugPrint('Error stopping recording: $e');
    }
  }

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
          // Add a button to toggle communication method
          IconButton(
            icon: Icon(_preferredCommunicationMethod == 'chat' ? Icons.mic : Icons.chat),
            onPressed: () async {
              final newMethod = _preferredCommunicationMethod == 'chat' ? 'voice' : 'chat';
              setState(() {
                _preferredCommunicationMethod = newMethod;
              });
              // Save preference to Supabase
              final user = supabase.auth.currentUser;
              if (user != null) {
                await supabase.from('users').update({'preferred_communication': newMethod}).eq('id', user.id);
              }
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
              child: Text(
                'Menu',
                style: TextStyle(color: Colors.white, fontSize: 24),
              ),
            ),
            ListTile(
              leading: const Icon(Icons.chat_bubble_outline),
              title: const Text('New Chat'),
              onTap: () {
                Navigator.pop(context); // Close drawer
                if (mounted) {
                  setState(() {
                    _messages.clear(); // Clear messages for a new chat
                  });
                }
                _isInitialLoad = false; // Switched to new chat, initial default load no longer relevant
              },
            ),
            ListTile(
              leading: const Icon(Icons.dashboard_outlined),
              title: const Text('Dashboard'),
              onTap: () {
                Navigator.pop(context); // Close drawer
                Navigator.pushReplacementNamed(context, '/home');
              },
            ),
            const Divider(),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
              child: Text(
                'Past Chats',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold),
              ),
            ),
            _isLoadingPastChats
                ? const Center(child: Padding(
                    padding: EdgeInsets.all(16.0),
                    child: CircularProgressIndicator(),
                  ))
                : _pastChatSessions.isEmpty
                    ? const ListTile(
                        title: Text('No past chats found.'),
                      )
                    : ListView.builder(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(), // to disable scrolling within ListView in Drawer
                        itemCount: _pastChatSessions.length,
                        itemBuilder: (context, index) {
                          final chat = _pastChatSessions[index];
                          return ListTile(
                            title: Text(chat['title'] ?? 'Chat Session'),
                            subtitle: Text(chat['subtitle'] ?? 'Tap to view'),
                            onTap: () => _navigateToPastChat(chat),
                          );
                        },
                      ),
          ],
        ),
      ),
      body: Column(
        children: <Widget>[
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
          _buildInputArea(),
        ],
      ),
    );
  }
}