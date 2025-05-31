import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart'; // Import Supabase

class UserOnboardingScreen extends StatefulWidget {
  const UserOnboardingScreen({super.key});

  @override
  UserOnboardingScreenState createState() => UserOnboardingScreenState(); // Make public
}

class UserOnboardingScreenState extends State<UserOnboardingScreen> { // Make public
  final _nameController = TextEditingController();
  final _futureSelfDescriptionController = TextEditingController();
  final _preferredToneController = TextEditingController();
  final _goal1Controller = TextEditingController();
  final _goal2Controller = TextEditingController();
  final _goal3Controller = TextEditingController();
  
  // New controllers for communication style
  final _chatSampleController = TextEditingController();
  final _commonPhrasesController = TextEditingController();
  final _typicalResponseController = TextEditingController();

  String _preferredCommunication = 'chat'; // Default to chat
  int? _futureSelfAge; // Nullable int for age
  
  // New communication style variables
  String _messageLength = 'medium';
  double _emojiUsage = 3.0; // Scale of 1-5
  String _punctuationStyle = 'standard';
  bool _useSlang = false;

  bool _isLoading = false;

  final List<int> _ageOptions = [2, 5, 20];
  final List<String> _toneOptions = ['gentle', 'loving', 'spiritual', 'motivational', 'calm']; // Example tones
  final List<String> _messageLengthOptions = ['short', 'medium', 'long'];
  final List<String> _punctuationOptions = ['minimal', 'standard', 'expressive'];

  Future<void> _saveOnboardingData() async {
    setState(() {
      _isLoading = true;
    });
    try {
      final user = Supabase.instance.client.auth.currentUser;
      if (user == null) {
        throw Exception('User not authenticated');
      }
  
      // Create goals array (filter out empty goals)
      final topGoals = [
        _goal1Controller.text,
        _goal2Controller.text,
        _goal3Controller.text,
      ].where((goal) => goal.isNotEmpty).toList();
  
      final userData = {
        'id': user.id,
        'name': _nameController.text,
        'preferred_communication': _preferredCommunication,
        'future_self_description': {
          'description': _futureSelfDescriptionController.text
        }, // Convert to JSONB format
        'future_self_age_years': _futureSelfAge ?? 0,
        'top_goals': topGoals, // Now properly formatted as array
        'preferred_tone': _preferredToneController.text,
        // New communication style fields
        'communication_style': {
          'chat_sample': _chatSampleController.text,
          'common_phrases': _commonPhrasesController.text,
          'typical_response': _typicalResponseController.text,
          'message_length': _messageLength,
          'emoji_usage': _emojiUsage,
          'punctuation_style': _punctuationStyle,
          'use_slang': _useSlang,
        },
      };
  
      // Insert data into the 'users' table. Use upsert to handle cases where a user might somehow revisit this screen.
      await Supabase.instance.client
          .from('users')
          .upsert([userData]);
  
      if (!mounted) return; // Check if widget is still mounted
      
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Onboarding data saved successfully!')),
      );
      // Navigate to the Home screen after successful onboarding
      Navigator.of(context).pushReplacementNamed('/home');
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error saving onboarding data: ${error.toString()}')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _futureSelfDescriptionController.dispose();
    _preferredToneController.dispose();
    _goal1Controller.dispose();
    _goal2Controller.dispose();
    _goal3Controller.dispose();
    _chatSampleController.dispose();
    _commonPhrasesController.dispose();
    _typicalResponseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Tell Us About Your Future Self'),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  TextFormField(
                    controller: _nameController,
                    decoration: const InputDecoration(labelText: 'Your Name'),
                  ),
                  const SizedBox(height: 16.0),
                  Text('Preferred Communication Method:', style: Theme.of(context).textTheme.titleMedium),
                  Row(
                    children: [
                      Expanded(
                        child: RadioListTile<String>(
                          title: const Text('Chat'),
                          value: 'chat',
                          groupValue: _preferredCommunication,
                          onChanged: (value) {
                            if (value != null) {
                              setState(() {
                                _preferredCommunication = value;
                              });
                            }
                          },
                        ),
                      ),
                      Expanded(
                        child: RadioListTile<String>(
                          title: const Text('Voice Notes'),
                          value: 'voice_notes',
                          groupValue: _preferredCommunication,
                          onChanged: (value) {
                            if (value != null) {
                              setState(() {
                                _preferredCommunication = value;
                              });
                            }
                          },
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16.0),
                  Text('Ideal Future Self Description:', style: Theme.of(context).textTheme.titleMedium),
                  TextFormField(
                    controller: _futureSelfDescriptionController,
                    decoration: const InputDecoration(labelText: 'Describe your ideal future self across different life areas (career, relationships, health, etc.)'),
                    maxLines: 5,
                  ),
                   const SizedBox(height: 16.0),
                  Text('Age of Future Self (Years from Now):', style: Theme.of(context).textTheme.titleMedium),
                  DropdownButtonFormField<int>(
                    value: _futureSelfAge,
                    hint: const Text('Select age'),
                    items: _ageOptions.map((int age) {
                      return DropdownMenuItem<int>(
                        value: age,
                        child: Text('$age years'),
                      );
                    }).toList(),
                    onChanged: (int? newValue) {
                      setState(() {
                        _futureSelfAge = newValue;
                      });
                    },
                  ),
                  const SizedBox(height: 16.0),
                   Text('Top 3 Goals for the next 40-50 days:', style: Theme.of(context).textTheme.titleMedium),
                  TextFormField(
                    controller: _goal1Controller,
                    decoration: const InputDecoration(labelText: 'Goal 1'),
                  ),
                  const SizedBox(height: 8.0),
                  TextFormField(
                    controller: _goal2Controller,
                    decoration: const InputDecoration(labelText: 'Goal 2'),
                  ),
                  const SizedBox(height: 8.0),
                  TextFormField(
                    controller: _goal3Controller,
                    decoration: const InputDecoration(labelText: 'Goal 3'),
                  ),
                   const SizedBox(height: 16.0),
                   Text('Preferred Communication Tone:', style: Theme.of(context).textTheme.titleMedium),
                   DropdownButtonFormField<String>(
                    value: _preferredToneController.text.isEmpty ? null : _preferredToneController.text,
                    hint: const Text('Select tone'),
                    items: _toneOptions.map((String tone) {
                      return DropdownMenuItem<String>(
                        value: tone,
                        child: Text(tone),
                      );
                    }).toList(),
                    onChanged: (String? newValue) {
                      if (newValue != null) {
                        setState(() {
                          _preferredToneController.text = newValue;
                        });
                      }
                    },
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Please select a tone';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 24.0),
                  
                  // Communication Style Section
                  Text('Communication Style Analysis', 
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: Theme.of(context).primaryColor,
                    )
                  ),
                  const SizedBox(height: 8.0),
                  Text('Help us understand your natural communication style:', 
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Colors.grey[600],
                    )
                  ),
                  const SizedBox(height: 16.0),
                  
                  Text('Quick Chat Sample:', style: Theme.of(context).textTheme.titleMedium),
                  TextFormField(
                    controller: _chatSampleController,
                    decoration: const InputDecoration(
                      labelText: 'Write a quick message about your day or how you\'re feeling',
                      hintText: 'e.g., "Had an amazing day at work! Really excited about the new project 😊"',
                    ),
                    maxLines: 3,
                  ),
                  const SizedBox(height: 16.0),
                  
                  Text('Message Length Preference:', style: Theme.of(context).textTheme.titleMedium),
                  SegmentedButton<String>(
                    segments: _messageLengthOptions.map((option) => ButtonSegment<String>(
                      value: option,
                      label: Text(option.toUpperCase()),
                    )).toList(),
                    selected: {_messageLength},
                    onSelectionChanged: (Set<String> newSelection) {
                      setState(() {
                        _messageLength = newSelection.first;
                      });
                    },
                  ),
                  const SizedBox(height: 16.0),
                  
                  Text('Emoji Usage (1 = Rarely, 5 = Frequently):', style: Theme.of(context).textTheme.titleMedium),
                  Slider(
                    value: _emojiUsage,
                    min: 1.0,
                    max: 5.0,
                    divisions: 4,
                    label: _emojiUsage.round().toString(),
                    onChanged: (double value) {
                      setState(() {
                        _emojiUsage = value;
                      });
                    },
                  ),
                  const SizedBox(height: 16.0),
                  
                  Text('Punctuation Style:', style: Theme.of(context).textTheme.titleMedium),
                  DropdownButtonFormField<String>(
                    value: _punctuationStyle,
                    items: _punctuationOptions.map((String style) {
                      return DropdownMenuItem<String>(
                        value: style,
                        child: Text(style.toUpperCase()),
                      );
                    }).toList(),
                    onChanged: (String? newValue) {
                      if (newValue != null) {
                        setState(() {
                          _punctuationStyle = newValue;
                        });
                      }
                    },
                  ),
                  const SizedBox(height: 16.0),
                  
                  Text('Common Phrases/Slang:', style: Theme.of(context).textTheme.titleMedium),
                  TextFormField(
                    controller: _commonPhrasesController,
                    decoration: const InputDecoration(
                      labelText: 'Words or phrases you use often',
                      hintText: 'e.g., "awesome", "no way", "totally", "for sure"',
                    ),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 16.0),
                  
                  CheckboxListTile(
                    title: const Text('I use casual slang and informal language'),
                    value: _useSlang,
                    onChanged: (bool? value) {
                      setState(() {
                        _useSlang = value ?? false;
                      });
                    },
                  ),
                  const SizedBox(height: 16.0),
                  
                  Text('Typical Response Style:', style: Theme.of(context).textTheme.titleMedium),
                  TextFormField(
                    controller: _typicalResponseController,
                    decoration: const InputDecoration(
                      labelText: 'How would you typically respond to "How was your weekend?"',
                      hintText: 'Write in your natural style...',
                    ),
                    maxLines: 3,
                  ),
                  const SizedBox(height: 24.0),
                  
                  Center(
                    child: ElevatedButton(
                      onPressed: _isLoading || _futureSelfAge == null ? null : _saveOnboardingData,
                      child: _isLoading
                          ? const CircularProgressIndicator(color: Colors.white)
                          : const Text('Save and Continue'),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}