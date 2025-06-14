import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  SettingsScreenState createState() => SettingsScreenState();
}

class SettingsScreenState extends State<SettingsScreen> {
  bool _isLoading = true;
  bool _isSaving = false;
  String? _error;
  
  // Communication preferences
  bool _emailNotifications = true;
  bool _pushNotifications = true;
  bool _dailyReminders = true;
  bool _weeklyReflections = true;
  String _preferredTime = '09:00';
  String _communicationStyle = 'supportive';
  
  // App preferences
  bool _darkMode = false;
  String _language = 'English';
  bool _analyticsEnabled = true;

  final List<String> _communicationStyles = [
    'supportive',
    'challenging',
    'motivational',
    'gentle',
    'direct'
  ];

  final List<String> _languages = [
    'English',
    'Spanish',
    'French',
    'German',
    'Italian'
  ];

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    try {
      final user = Supabase.instance.client.auth.currentUser;
      if (user == null) {
        setState(() {
          _error = 'User not authenticated.';
          _isLoading = false;
        });
        return;
      }

      final userData = await Supabase.instance.client
          .from('users')
          .select('communication_preferences, app_preferences')
          .eq('id', user.id)
          .single();

      final commPrefs = userData['communication_preferences'] as Map<String, dynamic>? ?? {};
      final appPrefs = userData['app_preferences'] as Map<String, dynamic>? ?? {};

      setState(() {
        _emailNotifications = commPrefs['email_notifications'] ?? true;
        _pushNotifications = commPrefs['push_notifications'] ?? true;
        _dailyReminders = commPrefs['daily_reminders'] ?? true;
        _weeklyReflections = commPrefs['weekly_reflections'] ?? true;
        _preferredTime = commPrefs['preferred_time'] ?? '09:00';
        _communicationStyle = commPrefs['communication_style'] ?? 'supportive';
        
        _darkMode = appPrefs['dark_mode'] ?? false;
        _language = appPrefs['language'] ?? 'English';
        _analyticsEnabled = appPrefs['analytics_enabled'] ?? true;
        
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Failed to load settings: ${e.toString()}';
        _isLoading = false;
      });
    }
  }

  Future<void> _saveSettings() async {
    setState(() {
      _isSaving = true;
    });

    try {
      final user = Supabase.instance.client.auth.currentUser;
      if (user == null) {
        throw Exception('User not authenticated');
      }

      final communicationPreferences = {
        'email_notifications': _emailNotifications,
        'push_notifications': _pushNotifications,
        'daily_reminders': _dailyReminders,
        'weekly_reflections': _weeklyReflections,
        'preferred_time': _preferredTime,
        'communication_style': _communicationStyle,
      };

      final appPreferences = {
        'dark_mode': _darkMode,
        'language': _language,
        'analytics_enabled': _analyticsEnabled,
      };

      await Supabase.instance.client.from('users').update({
        'communication_preferences': communicationPreferences,
        'app_preferences': appPreferences,
      }).eq('id', user.id);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Settings saved successfully!')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error saving settings: ${e.toString()}')),
        );
      }
    } finally {
      setState(() {
        _isSaving = false;
      });
    }
  }

  Future<void> _selectTime() async {
    final TimeOfDay? picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(
        hour: int.parse(_preferredTime.split(':')[0]),
        minute: int.parse(_preferredTime.split(':')[1]),
      ),
    );
    
    if (picked != null) {
      setState(() {
        _preferredTime = '${picked.hour.toString().padLeft(2, '0')}:${picked.minute.toString().padLeft(2, '0')}';
      });
    }
  }

  Future<void> _signOut() async {
    try {
      await Supabase.instance.client.auth.signOut();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error signing out: ${error.toString()}')),
        );
      }
    }
  }

  Future<void> _showDeleteAccountDialog() async {
    return showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('Delete Account'),
          content: const Text(
            'Are you sure you want to delete your account? This action cannot be undone and all your data will be permanently lost.',
          ),
          actions: <Widget>[
            TextButton(
              child: const Text('Cancel'),
              onPressed: () {
                Navigator.of(context).pop();
              },
            ),
            TextButton(
              child: const Text('Delete', style: TextStyle(color: Colors.red)),
              onPressed: () {
                Navigator.of(context).pop();
                _deleteAccount();
              },
            ),
          ],
        );
      },
    );
  }

  Future<void> _deleteAccount() async {
    try {
      final user = Supabase.instance.client.auth.currentUser;
      if (user == null) return;

      // Delete user data from the users table
      await Supabase.instance.client
          .from('users')
          .delete()
          .eq('id', user.id);

      // Sign out the user
      await Supabase.instance.client.auth.signOut();

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Account deleted successfully')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error deleting account: ${e.toString()}')),
        );
      }
    }
  }

  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 8),
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleMedium?.copyWith(
          color: Theme.of(context).primaryColor,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildSwitchTile({
    required String title,
    String? subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return SwitchListTile(
      title: Text(title),
      subtitle: subtitle != null ? Text(subtitle) : null,
      value: value,
      onChanged: onChanged,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        actions: [
          if (_isSaving)
            const Padding(
              padding: EdgeInsets.all(16.0),
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            )
          else
            TextButton(
              onPressed: _saveSettings,
              child: const Text('Save', style: TextStyle(color: Colors.white)),
            ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('Error: $_error'))
              : ListView(
                  children: [
                    _buildSectionHeader('Communication Preferences'),
                    _buildSwitchTile(
                      title: 'Email Notifications',
                      subtitle: 'Receive notifications via email',
                      value: _emailNotifications,
                      onChanged: (value) => setState(() => _emailNotifications = value),
                    ),
                    _buildSwitchTile(
                      title: 'Push Notifications',
                      subtitle: 'Receive push notifications on your device',
                      value: _pushNotifications,
                      onChanged: (value) => setState(() => _pushNotifications = value),
                    ),
                    _buildSwitchTile(
                      title: 'Daily Reminders',
                      subtitle: 'Get daily reminders to check in',
                      value: _dailyReminders,
                      onChanged: (value) => setState(() => _dailyReminders = value),
                    ),
                    _buildSwitchTile(
                      title: 'Weekly Reflections',
                      subtitle: 'Receive weekly reflection prompts',
                      value: _weeklyReflections,
                      onChanged: (value) => setState(() => _weeklyReflections = value),
                    ),
                    ListTile(
                      title: const Text('Preferred Notification Time'),
                      subtitle: Text(_preferredTime),
                      trailing: const Icon(Icons.access_time),
                      onTap: _selectTime,
                    ),
                    ListTile(
                      title: const Text('Communication Style'),
                      subtitle: Text(_communicationStyle.toUpperCase()),
                      trailing: const Icon(Icons.arrow_forward_ios),
                      onTap: () {
                        showDialog(
                          context: context,
                          builder: (context) => AlertDialog(
                            title: const Text('Select Communication Style'),
                            content: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: _communicationStyles.map((style) {
                                return RadioListTile<String>(
                                  title: Text(style.toUpperCase()),
                                  value: style,
                                  groupValue: _communicationStyle,
                                  onChanged: (value) {
                                    setState(() => _communicationStyle = value!);
                                    Navigator.pop(context);
                                  },
                                );
                              }).toList(),
                            ),
                          ),
                        );
                      },
                    ),
                    _buildSectionHeader('App Preferences'),
                    _buildSwitchTile(
                      title: 'Dark Mode',
                      subtitle: 'Use dark theme',
                      value: _darkMode,
                      onChanged: (value) => setState(() => _darkMode = value),
                    ),
                    ListTile(
                      title: const Text('Language'),
                      subtitle: Text(_language),
                      trailing: const Icon(Icons.arrow_forward_ios),
                      onTap: () {
                        showDialog(
                          context: context,
                          builder: (context) => AlertDialog(
                            title: const Text('Select Language'),
                            content: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: _languages.map((language) {
                                return RadioListTile<String>(
                                  title: Text(language),
                                  value: language,
                                  groupValue: _language,
                                  onChanged: (value) {
                                    setState(() => _language = value!);
                                    Navigator.pop(context);
                                  },
                                );
                              }).toList(),
                            ),
                          ),
                        );
                      },
                    ),
                    _buildSwitchTile(
                      title: 'Analytics',
                      subtitle: 'Help improve the app by sharing usage data',
                      value: _analyticsEnabled,
                      onChanged: (value) => setState(() => _analyticsEnabled = value),
                    ),
                    _buildSectionHeader('Account'),
                    ListTile(
                      title: const Text('Sign Out'),
                      leading: const Icon(Icons.logout),
                      onTap: _signOut,
                    ),
                    ListTile(
                      title: const Text('Delete Account'),
                      leading: const Icon(Icons.delete_forever, color: Colors.red),
                      onTap: _showDeleteAccountDialog,
                    ),
                    const SizedBox(height: 24),
                  ],
                ),
    );
  }
}