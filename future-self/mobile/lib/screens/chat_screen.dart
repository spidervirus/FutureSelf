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
  
  // Add this variable to store user's preferred communication method
  String _preferredCommunicationMethod = 'chat'; // Default to chat
  bool _isLoadingPreferences = true;
  
  // Add these variables for enhanced functionality
  Timer? _recordingTimer;
  int _recordingDuration = 0;
  bool _isPlayingAudio = false;
  String? _currentlyPlayingMessageId;

  @override
  void initState() {
    super.initState();
    _loadUserPreferences();
    _loadMessageHistory();
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
  Future<void> _loadMessageHistory() async {
    try {
      final user = supabase.auth.currentUser;
      if (user != null) {
        final response = await supabase
            .from('chat_messages')
            .select()
            .eq('user_id', user.id)
            .order('created_at', ascending: false)
            .limit(50);
        
        if (!mounted) return;
        final loadedMessages = response.map<types.Message>((data) {
          return types.TextMessage(
            author: types.User(id: data['author_id']),
            createdAt: DateTime.parse(data['created_at']).millisecondsSinceEpoch,
            id: data['message_id'],
            text: data['content'],
          );
        }).toList();
        
        setState(() {
          _messages.insertAll(0, loadedMessages.reversed);
        });
      }
    } catch (e) {
      print('Error loading message history: $e');
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
      print('Error saving message to database: $e');
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
    
    try {
      final response = await http.post(
        url,
        headers: <String, String>{'Content-Type': 'application/json; charset=UTF-8'},
        body: jsonEncode(<String, String>{'text': textToSynthesize}),
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
      print('Error synthesizing speech: $e');
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
                color: Colors.black.withOpacity(0.1),
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
                        color: textColor.withOpacity(0.7),
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
                        color: textColor.withOpacity(0.7),
                        fontSize: 12.0,
                      ),
                    ),
                  ],
                )
              else
                Text(
                  _formatTimestamp(message.createdAt!),
                  style: TextStyle(
                    color: textColor.withOpacity(0.7),
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
              color: _isRecording ? Colors.red.withOpacity(0.1) : null,
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
            print('Recording stream done');
          },
          onError: (e) {
            print('Recording stream error: $e');
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
        print('Recording permission not granted');
      }
    } catch (e) {
      print('Error starting recording: $e');
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
      print('Error stopping recording: $e');
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