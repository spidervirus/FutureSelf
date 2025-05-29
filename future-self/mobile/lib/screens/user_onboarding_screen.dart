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

  String _preferredCommunication = 'chat'; // Default to chat
  int? _futureSelfAge; // Nullable int for age

  bool _isLoading = false;

  final List<int> _ageOptions = [2, 5, 20];
  final List<String> _toneOptions = ['gentle', 'loving', 'spiritual', 'motivational', 'calm']; // Example tones

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