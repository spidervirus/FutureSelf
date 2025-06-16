import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
// Conditional import for web
import 'package:web/web.dart' as web;
import 'dart:js_interop';
import 'package:country_picker/country_picker.dart';
import 'package:date_picker_plus/date_picker_plus.dart';
import 'package:speech_to_text/speech_to_text.dart';

import 'dart:async';


class UserOnboardingScreen extends StatefulWidget {
  const UserOnboardingScreen({super.key});

  @override
  UserOnboardingScreenState createState() => UserOnboardingScreenState();
}

class UserOnboardingScreenState extends State<UserOnboardingScreen>
    with TickerProviderStateMixin {
  final PageController _pageController = PageController();
  int _currentStep = 0;
  final int _totalSteps = 5;
  
  late AnimationController _progressAnimationController;
  late Animation<double> _progressAnimation;
  late AnimationController _fadeAnimationController;
  late Animation<double> _fadeAnimation;
  
  final _formKey = GlobalKey<FormState>();
  final _step1FormKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  String? _selectedNationality;
  String? _selectedBirthCountry;
  String? _selectedLocation;

  
  // Controllers for second section - personal reflection
  final _mindSpaceController = TextEditingController();
  final _futureProudController = TextEditingController();
  final _mostYourselfController = TextEditingController();
  final _lowMomentsController = TextEditingController();
  final _spiralReminderController = TextEditingController();
  final _proudOfSelfController = TextEditingController();
  final _dreamController = TextEditingController();
  
  // Controllers for third section - personal challenges and growth
  final _changeController = TextEditingController();
  final _avoidController = TextEditingController();
  final _feelingController = TextEditingController();
  
  // Controllers for fourth section - future self vision
  final _futureDescriptionController = TextEditingController();
  final _futureAgeController = TextEditingController();
  final _typicalDayController = TextEditingController();
  final _accomplishmentController = TextEditingController();
  String? _futurePhotoPath;
    // Controllers for fifth section - communication style
  final _wordsSlangController = TextEditingController();
  String _messagePreference = 'long'; // 'long' or 'short'
  String _messagingFrequency = 'daily'; // 'daily', 'weekly', 'minimal'
  String _emojiUsagePreference = 'love them'; // 'love them', 'use a little', 'never'
  
  // Communication style controllers
  
  DateTime? _selectedDate;
  String? _profileImagePath;
  
  final String _preferredCommunication = 'chat';
  
  // Image picker instance
  final ImagePicker _picker = ImagePicker();
  File? _selectedImage;

  String? _webImageUrl; // For displaying web images
  
  // Communication style fields
  final String _messageLength = 'medium';
  final double _emojiUsage = 3.0;
  final String _punctuationStyle = 'standard';
  final bool _useSlang = false;
  
  bool _isLoading = false;
  final bool _hasUnsavedChanges = false;
  
  // Progress saving key - used for saving progress to SharedPreferences
  static const String _progressKey = 'onboarding_progress';
  
  // Speech-to-text related variables
  final SpeechToText _speechToText = SpeechToText();
  bool _speechEnabled = false;
  String _currentListeningController = '';
  bool _isListening = false;
  String _lastWords = '';
  Timer? _speechTimer;
  
  @override
  void initState() {
    super.initState();
    
    // Initialize animation controllers
    _progressAnimationController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
    
    _progressAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _progressAnimationController,
      curve: Curves.easeInOut,
    ));
    
    _fadeAnimationController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 200),
    );
    
    _fadeAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _fadeAnimationController,
      curve: Curves.easeIn,
    ));
    
    // Start with fade in animation
    _fadeAnimationController.forward();
    
    // Initialize speech-to-text
    _initSpeech();
  }
  
  void _initSpeech() async {
    _speechEnabled = await _speechToText.initialize(
      onStatus: (val) => debugPrint('onStatus: $val'),
      onError: (val) => debugPrint('onError: $val'),
    );
    setState(() {});
  }
  
  // Enhanced navigation methods with validation and progress saving
  Future<void> _nextStep() async {
    if (_validateCurrentStep()) {
      await _saveProgress();
      
      if (_currentStep < _totalSteps - 1) {
        setState(() {
          _currentStep++;
        });
        
        // Animate progress
        _progressAnimationController.forward();
        
        // Animate page transition with fade
        _fadeAnimationController.reset();
        await _pageController.nextPage(
          duration: const Duration(milliseconds: 400),
          curve: Curves.easeInOutCubic,
        );
        _fadeAnimationController.forward();
      }
    } else {
      _showValidationError();
    }
  }
  
  Future<void> _previousStep() async {
    if (_currentStep > 0) {
      await _saveProgress();
      
      setState(() {
        _currentStep--;
      });
      
      // Animate page transition with fade
      _fadeAnimationController.reset();
      await _pageController.previousPage(
        duration: const Duration(milliseconds: 400),
        curve: Curves.easeInOutCubic,
      );
      _fadeAnimationController.forward();
    }
  }
  
  bool _validateCurrentStep() {
    switch (_currentStep) {
      case 0: // Basic Information
        return _nameController.text.trim().isNotEmpty &&
               _selectedNationality != null &&
               _selectedBirthCountry != null &&
               _selectedDate != null &&
               _selectedLocation != null;
      case 1: // Personal Reflection
        return _mindSpaceController.text.trim().isNotEmpty &&
               _futureProudController.text.trim().isNotEmpty &&
               _mostYourselfController.text.trim().isNotEmpty &&
               _lowMomentsController.text.trim().isNotEmpty &&
               _spiralReminderController.text.trim().isNotEmpty &&
               _proudOfSelfController.text.trim().isNotEmpty &&
               _dreamController.text.trim().isNotEmpty;
      case 2: // Growth and Challenges
        return _changeController.text.trim().isNotEmpty &&
               _avoidController.text.trim().isNotEmpty &&
               _feelingController.text.trim().isNotEmpty;
      case 3: // Future Vision
        return _futureDescriptionController.text.trim().isNotEmpty &&
               _futureAgeController.text.trim().isNotEmpty &&
               _typicalDayController.text.trim().isNotEmpty &&
               _accomplishmentController.text.trim().isNotEmpty;
      case 4: // Communication Style
        return _wordsSlangController.text.trim().isNotEmpty &&
               _messagePreference.isNotEmpty &&
               _messagingFrequency.isNotEmpty &&
               _emojiUsagePreference.isNotEmpty;
      default:
        return true;
    }
  }
  
  void _showValidationError() {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.warning_amber_rounded, color: Colors.white),
            const SizedBox(width: 8),
            const Expanded(
              child: Text(
                'Please fill in all required fields before continuing.',
                style: TextStyle(fontWeight: FontWeight.w500),
              ),
            ),
          ],
        ),
        backgroundColor: Colors.orange.shade600,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        margin: const EdgeInsets.all(16),
        duration: const Duration(seconds: 3),
      ),
    );
  }
  
  Future<void> _showExitConfirmation() async {
    if (_hasUnsavedChanges) {
      final shouldExit = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Unsaved Changes'),
          content: const Text(
            'You have unsaved progress. Are you sure you want to exit? Your progress will be saved automatically.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('Exit'),
            ),
          ],
        ),
      );
      
      if (shouldExit == true) {
        await _saveProgress();
        if (mounted) Navigator.of(context).pop();
      }
    } else {
      Navigator.of(context).pop();
    }
  }

  Future<void> _saveOnboardingData() async {
    // Validate step 1 form if we're on step 0
    if (_currentStep == 0 && (_step1FormKey.currentState == null || !_step1FormKey.currentState!.validate())) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please fill in all required fields correctly.')),
        );
      }
      return;
    }

    // Validate all required fields before saving
    if (_nameController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter your name')),
      );
      return;
    }
    
    if (_selectedNationality?.isEmpty ?? true) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select your nationality')),
      );
      return;
    }
    
    if (_selectedBirthCountry?.isEmpty ?? true) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select your birth country')),
      );
      return;
    }
    
    if (_selectedLocation?.isEmpty ?? true) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select your location')),
      );
      return;
    }
    
    if (_selectedDate == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select your date of birth')),
      );
      return;
    }
    
    if (_futureAgeController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter your future age')),
      );
      return;
    }
    
    // Validate that at least one goal is provided for top_goals array
    final goals = [_changeController.text, _accomplishmentController.text].where((goal) => goal.trim().isNotEmpty).toList();
    if (goals.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please provide at least one goal')),
      );
      return;
    }

    setState(() {
      _isLoading = true;
    });

    try {
      final user = Supabase.instance.client.auth.currentUser;
      if (user == null) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('User not authenticated. Please log in again.'),
              backgroundColor: Colors.red,
            ),
          );
        }
        return;
      }
      
      // Log the data being saved for debugging
      debugPrint('Saving onboarding data for user: ${user.id}');
      debugPrint('Name: ${_nameController.text}');
      debugPrint('Nationality: $_selectedNationality');
      debugPrint('Location: $_selectedLocation');
      
      final dataToSave = {
        'id': user.id,
        'name': _nameController.text,
        'nationality': _selectedNationality!,
        'birth_country': _selectedBirthCountry!,
        'date_of_birth': _selectedDate!.toIso8601String(),
        'current_location': _selectedLocation!,
        'profile_image_path': _profileImagePath,
        'preferred_communication': _preferredCommunication,
        'future_self_description': {
          'mind_space': _mindSpaceController.text,
          'future_proud': _futureProudController.text,
          'most_yourself': _mostYourselfController.text,
          'low_moments': _lowMomentsController.text,
          'spiral_reminder': _spiralReminderController.text,
          'proud_of_self': _proudOfSelfController.text,
          'dream': _dreamController.text,
          'change_goal': _changeController.text,
          'avoid_tendency': _avoidController.text,
          'feeling_description': _feelingController.text,
          'future_description': _futureDescriptionController.text,
          'typical_day': _typicalDayController.text,
          'accomplishment': _accomplishmentController.text,
          'future_photo_path': _futurePhotoPath,
        },
        'future_self_age_years': int.tryParse(_futureAgeController.text) ?? 0,
        'top_goals': goals,
        'communication_style': {
          'words_slang': _wordsSlangController.text,
          'message_preference': _messagePreference,
          'messaging_frequency': _messagingFrequency,
          'emoji_usage_preference': _emojiUsagePreference,
          'message_length': _messageLength,
          'emoji_usage': _emojiUsage,
          'punctuation_style': _punctuationStyle,
          'use_slang': _useSlang,
        },
      };
      
      debugPrint('Data to save: $dataToSave');
      
      await Supabase.instance.client.from('users').upsert(dataToSave);
        
      // Clear saved progress after successful completion
      await _clearProgress();

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Profile saved successfully!')),
        );
        Navigator.of(context).pushReplacementNamed('/home');
      }
    } catch (e) {
      // Log the error for debugging
      debugPrint('Error saving onboarding data: $e');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error saving profile: ${e.toString()}'),
            backgroundColor: Colors.red,
            duration: const Duration(seconds: 5),
          ),
        );
      }
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
    _pageController.dispose();
    _nameController.dispose();

    _mindSpaceController.dispose();
    _futureProudController.dispose();
    _mostYourselfController.dispose();
    _lowMomentsController.dispose();
    _spiralReminderController.dispose();
    _proudOfSelfController.dispose();
    _dreamController.dispose();
    _changeController.dispose();
    _avoidController.dispose();
    _feelingController.dispose();
    _futureDescriptionController.dispose();
    _futureAgeController.dispose();
    _typicalDayController.dispose();
    _accomplishmentController.dispose();
    _wordsSlangController.dispose();
    _progressAnimationController.dispose();
    _fadeAnimationController.dispose();
    _speechTimer?.cancel();
    super.dispose();
  }

  // Speech-to-text methods
  void _startListening(String controllerName, TextEditingController controller) async {
    if (!_speechEnabled) return;
    
    await _speechToText.listen(
      onResult: (val) {
        setState(() {
          _lastWords = val.recognizedWords;
          if (val.finalResult) {
            // Append to existing text if there's any
            String currentText = controller.text;
            if (currentText.isNotEmpty && !currentText.endsWith(' ')) {
              currentText += ' ';
            }
            controller.text = currentText + val.recognizedWords;
            _isListening = false;
            _currentListeningController = '';
          }
        });
      },
      listenFor: const Duration(seconds: 30),
      pauseFor: const Duration(seconds: 3),
      listenOptions: SpeechListenOptions(
        partialResults: true,
        cancelOnError: true,
        listenMode: ListenMode.confirmation,
      ),
      localeId: 'en_US',
      onSoundLevelChange: (level) {},
    );
    
    setState(() {
      _isListening = true;
      _currentListeningController = controllerName;
    });
  }
  
  void _stopListening() async {
    await _speechToText.stop();
    setState(() {
      _isListening = false;
      _currentListeningController = '';
    });
  }
  
  Widget _buildVoiceButton(String controllerName, TextEditingController controller) {
    bool isCurrentlyListening = _isListening && _currentListeningController == controllerName;
    
    return Container(
      margin: const EdgeInsets.only(left: 8),
      child: IconButton(
        onPressed: _speechEnabled
            ? () {
                if (isCurrentlyListening) {
                  _stopListening();
                } else {
                  _startListening(controllerName, controller);
                }
              }
            : null,
        icon: Icon(
          isCurrentlyListening ? Icons.mic : Icons.mic_none,
          color: isCurrentlyListening ? Colors.red : Colors.blue,
        ),
        tooltip: isCurrentlyListening ? 'Stop recording' : 'Start voice input',
      ),
    );
  }
  
  Widget _buildTextFieldWithVoice({
    required TextEditingController controller,
    required String controllerName,
    required String hintText,
    required String? Function(String?) validator,
    int maxLines = 3,
    TextInputType? keyboardType,
  }) {
    bool isCurrentlyListening = _isListening && _currentListeningController == controllerName;
    
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: TextFormField(
                controller: controller,
                maxLines: maxLines,
                keyboardType: keyboardType,
                decoration: InputDecoration(
                  hintText: hintText,
                  border: const OutlineInputBorder(),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  suffixIcon: _buildVoiceButton(controllerName, controller),
                ),
                validator: validator,
              ),
            ),
          ],
        ),
        if (isCurrentlyListening)
          Container(
            margin: const EdgeInsets.only(top: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.red.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.red.withValues(alpha: 0.3)),
            ),
            child: Row(
              children: [
                const Icon(Icons.mic, color: Colors.red, size: 16),
                const SizedBox(width: 8),
                const Text(
                  'Listening...',
                  style: TextStyle(color: Colors.red, fontWeight: FontWeight.w500),
                ),
                const Spacer(),
                if (_lastWords.isNotEmpty)
                  Expanded(
                    flex: 2,
                    child: Text(
                      _lastWords,
                      style: const TextStyle(fontSize: 12, color: Colors.grey),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
            ),
          ),
      ],
    );
  }

  // Image picker methods
  Future<void> _showImageSourceDialog() async {
    return showDialog<void>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('Select Image Source'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                leading: const Icon(Icons.photo_library),
                title: const Text('Gallery'),
                onTap: () {
                  Navigator.of(context).pop();
                  _pickImageFromSource(ImageSource.gallery);
                },
              ),
              ListTile(
                leading: const Icon(Icons.camera_alt),
                title: const Text('Camera'),
                onTap: () {
                  Navigator.of(context).pop();
                  _pickImageFromSource(ImageSource.camera);
                },
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _pickImageFromSource(ImageSource source) async {
    try {
      final XFile? image = await _picker.pickImage(
        source: source,
        maxWidth: 1024,
        maxHeight: 1024,
        imageQuality: 85,
      );
      
      if (image != null) {
        if (kIsWeb) {
           // For web, create a blob URL for immediate display
           final bytes = await image.readAsBytes();
           final blob = web.Blob([bytes.toJS].toJS);
           final url = web.URL.createObjectURL(blob);
           
           setState(() {
             _selectedImage = File(image.path); // Placeholder

             _webImageUrl = url;
           });
           // Upload image to Supabase storage using XFile for web
           await _uploadImageWeb(image);
         } else {
           setState(() {
             _selectedImage = File(image.path);
           });
           // Upload image to Supabase storage
           await _uploadImage();
         }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error picking image: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _uploadImageWeb(XFile? imageFile) async {
    if (imageFile == null) {
      debugPrint("imageFile is null in _uploadImageWeb. Returning.");
      return;
    }
    
    if (!mounted) {
        debugPrint("_uploadImageWeb called on unmounted widget. Returning.");
        return;
    }

    setState(() { 
      _isLoading = true; 
    });

    try {
      final user = Supabase.instance.client.auth.currentUser;
      if (user == null) {
        debugPrint("User is null in _uploadImageWeb.");
        throw Exception('User not authenticated'); 
      }
      
      if (user.id.isEmpty) {
          debugPrint("User ID is empty in _uploadImageWeb.");
          throw Exception('User ID is empty.');
      }
      final fileName = 'future_self_${user.id}_${DateTime.now().millisecondsSinceEpoch}.jpg';
      
      Uint8List bytes;
      try {
        bytes = await imageFile.readAsBytes();
        if (bytes.isEmpty) {
            debugPrint("imageFile.readAsBytes() returned empty bytes.");
            throw Exception('Image data is empty.');
        }
      } catch (e) {
        debugPrint("Error reading bytes from imageFile in _uploadImageWeb: $e");
        throw Exception('Failed to read image data. Original error: $e');
      }
      
      await Supabase.instance.client.storage
          .from('user-photos')
          .uploadBinary(fileName, bytes);
      
      final publicUrl = Supabase.instance.client.storage
          .from('user-photos')
          .getPublicUrl(fileName);
      
      if (!mounted) {
          debugPrint("_uploadImageWeb unmounted before setting futurePhotoPath. Returning.");
          return; 
      }
      setState(() { 
        _futurePhotoPath = publicUrl;
      });
      
      if (mounted) { 
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Photo uploaded successfully!'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      debugPrint("Error in _uploadImageWeb's main try-catch: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error uploading photo: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      } else {
        debugPrint("_uploadImageWeb unmounted, cannot setState for isLoading in finally.");
      }
    }
  }

  Future<void> _uploadImage() async {
    if (_selectedImage == null) return;
    
    try {
      setState(() {
        _isLoading = true;
      });
      
      final user = Supabase.instance.client.auth.currentUser;
      if (user == null) {
        throw Exception('User not authenticated');
      }
      
      // Generate unique filename
      final fileName = 'future_self_${user.id}_${DateTime.now().millisecondsSinceEpoch}.jpg';
      
      // Upload to Supabase storage
      await Supabase.instance.client.storage
          .from('user-photos')
          .upload(fileName, _selectedImage!);
      
      // Get public URL
      final publicUrl = Supabase.instance.client.storage
          .from('user-photos')
          .getPublicUrl(fileName);
      
      setState(() {
        _futurePhotoPath = publicUrl;
        _isLoading = false;
      });
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Photo uploaded successfully!'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error uploading image: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  // Progress saving and clearing methods
  Future<void> _saveProgress() async {
    final prefs = await SharedPreferences.getInstance();
    final progressData = {
      'currentStep': _currentStep,
      'name': _nameController.text,
      'nationality': _selectedNationality,
      'location': _selectedLocation,

      'mindSpace': _mindSpaceController.text,
      'futureProud': _futureProudController.text,
      'mostYourself': _mostYourselfController.text,
      'lowMoments': _lowMomentsController.text,
      'spiralReminder': _spiralReminderController.text,
      'change': _changeController.text,
      'avoid': _avoidController.text,
      'feeling': _feelingController.text,
      'futureDescription': _futureDescriptionController.text,
      'futureAge': _futureAgeController.text,
      'typicalDay': _typicalDayController.text,
      'accomplishment': _accomplishmentController.text,
      'wordsSlang': _wordsSlangController.text,
      'useSlang': _useSlang,
    };
    await prefs.setString(_progressKey, json.encode(progressData));
  }

  Future<void> _clearProgress() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_progressKey);
  }

  @override
  Widget build(BuildContext context) {
    return PopScope<bool>(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) async {
        if (!didPop) {
          await _showExitConfirmation();
        }
      },
      child: Scaffold(
        backgroundColor: Colors.grey[50],
        appBar: AppBar(
          title: Row(
            children: [
              const Text('Tell me about yourself'),
              if (_hasUnsavedChanges) ...[
                const SizedBox(width: 8),
                Container(
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    color: Colors.orange,
                    shape: BoxShape.circle,
                  ),
                ),
              ],
            ],
          ),
          backgroundColor: Colors.white,
          elevation: 0,
          foregroundColor: Colors.black87,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: _showExitConfirmation,
          ),
        ),
        body: Column(
          children: [
            // Enhanced progress indicator with animation
            Container(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Step ${_currentStep + 1} of $_totalSteps',
                        style: const TextStyle(
                          fontSize: 14,
                          color: Colors.grey,
                        ),
                      ),
                      Row(
                        children: [
                          if (_hasUnsavedChanges)
                            Container(
                              margin: const EdgeInsets.only(right: 8),
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: Colors.orange.shade100,
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Text(
                                'Unsaved',
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w500,
                                  color: Colors.orange.shade700,
                                ),
                              ),
                            ),
                          Text(
                            '${((_currentStep + 1) / _totalSteps * 100).round()}%',
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                              color: Colors.blue,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  AnimatedBuilder(
                    animation: _progressAnimation,
                    builder: (context, child) {
                      return LinearProgressIndicator(
                        value: (_currentStep + 1) / _totalSteps * _progressAnimation.value,
                        backgroundColor: Colors.grey[300],
                        valueColor: const AlwaysStoppedAnimation<Color>(Colors.blue),
                        minHeight: 6,
                      );
                    },
                  ),
                ],
              ),
            ),
            // Enhanced PageView with fade animation
            Expanded(
              child: AnimatedBuilder(
                animation: _fadeAnimation,
                builder: (context, child) {
                  return FadeTransition(
                    opacity: _fadeAnimation,
                    child: Form(
                      key: _formKey,
                      child: PageView(
                        controller: _pageController,
                        physics: const NeverScrollableScrollPhysics(), // Disable swipe to enforce validation
                        onPageChanged: (index) {
                          setState(() {
                            _currentStep = index;
                          });
                          _progressAnimationController.forward();
                        },
                        children: [
                          _buildStep1(),
                          _buildStep2(),
                          _buildStep3(),
                          _buildStep4(),
                          _buildStep5(),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
          // Navigation buttons
          Container(
            padding: const EdgeInsets.all(20),
            child: Row(
              children: [
                if (_currentStep > 0)
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _isLoading ? null : _previousStep,
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Text(
                        'Back',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                      ),
                    ),
                  ),
                if (_currentStep > 0) const SizedBox(width: 16),
                Expanded(
                  child: AnimatedBuilder(
                    animation: _fadeAnimation,
                    builder: (context, child) {
                      return FadeTransition(
                        opacity: _fadeAnimation,
                        child: ElevatedButton(
                          onPressed: _isLoading ? null : () {
                            if (_currentStep < _totalSteps - 1) {
                              _nextStep();
                            } else {
                              if (_validateCurrentStep()) {
                                _saveOnboardingData();
                              } else {
                                _showValidationError();
                              }
                            }
                          },
                          style: ElevatedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(vertical: 16),
                            backgroundColor: Colors.blue,
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                            elevation: 2,
                          ),
                          child: _isLoading
                              ? const SizedBox(
                                  height: 20,
                                  width: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                  ),
                                )
                              : Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Text(
                                      _currentStep < _totalSteps - 1 ? 'Continue' : 'Complete',
                                      style: const TextStyle(
                                        fontSize: 16,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    Icon(
                                      _currentStep < _totalSteps - 1
                                          ? Icons.arrow_forward_rounded
                                          : Icons.check_rounded,
                                      size: 20,
                                    ),
                                  ],
                                ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    ));

  }

  Widget _buildStep1() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Form(
        key: _step1FormKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Let me meet you 👋',
              style: TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.bold,
                color: Colors.black87,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Tell me a bit about yourself so I can get to know you better.',
              style: TextStyle(
                fontSize: 16,
                color: Colors.grey,
              ),
            ),
            const SizedBox(height: 32),
            _buildQuestionCard(
              icon: Icons.person,
              question: 'What should I call you?',
              child: TextFormField(
                controller: _nameController,
                decoration: const InputDecoration(
                  hintText: 'Your preferred name...',
                  border: OutlineInputBorder(),
                  contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return 'Please tell me your name';
                  }
                  return null;
                },
              ),
            ),
            _buildQuestionCard(
              icon: Icons.public,
              question: 'What\'s your cultural background?',
              child: InkWell(
                onTap: () {
                  showCountryPicker(
                    context: context,
                    showPhoneCode: false,
                    onSelect: (Country country) {
                      setState(() {
                        _selectedNationality = country.name;
                      });
                    },
                    countryListTheme: CountryListThemeData(
                      borderRadius: BorderRadius.circular(8),
                      inputDecoration: InputDecoration(
                        labelText: 'Search',
                        hintText: 'Start typing to search',
                        prefixIcon: const Icon(Icons.search),
                        border: OutlineInputBorder(
                          borderSide: BorderSide(
                            color: Colors.grey.withValues(alpha: 0.2),
                          ),
                        ),
                      ),
                    ),
                  );
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    border: Border.all(color: Colors.grey),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        _selectedNationality ?? 'Select your nationality...',
                        style: TextStyle(
                          color: _selectedNationality != null ? Colors.black : Colors.grey[600],
                        ),
                      ),
                      const Icon(Icons.arrow_drop_down, color: Colors.grey),
                    ],
                  ),
                ),
              ),
            ),
            _buildQuestionCard(
              icon: Icons.location_city,
              question: 'Which country were you born in?',
              child: InkWell(
                onTap: () {
                  showCountryPicker(
                    context: context,
                    showPhoneCode: false,
                    onSelect: (Country country) {
                      setState(() {
                        _selectedBirthCountry = country.name;
                      });
                    },
                    countryListTheme: CountryListThemeData(
                      borderRadius: BorderRadius.circular(8),
                      inputDecoration: InputDecoration(
                        labelText: 'Search',
                        hintText: 'Start typing to search',
                        prefixIcon: const Icon(Icons.search),
                        border: OutlineInputBorder(
                          borderSide: BorderSide(
                            color: Colors.grey.withValues(alpha: 0.2),
                          ),
                        ),
                      ),
                    ),
                  );
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    border: Border.all(color: Colors.grey),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        _selectedBirthCountry ?? 'Select your birth country...',
                        style: TextStyle(
                          color: _selectedBirthCountry != null ? Colors.black : Colors.grey[600],
                        ),
                      ),
                      const Icon(Icons.arrow_drop_down, color: Colors.grey),
                    ],
                  ),
                ),
              ),
            ),
            _buildQuestionCard(
              icon: Icons.cake,
              question: 'When\'s your birthday?',
              child: InkWell(
                onTap: () async {
                  final DateTime? picked = await showDatePickerDialog(
                    context: context,
                    initialDate: _selectedDate ?? DateTime(2000),
                    minDate: DateTime(1900),
                    maxDate: DateTime.now(),
                    width: 300,
                    height: 300,
                    currentDate: DateTime.now(),
                    selectedDate: _selectedDate ?? DateTime(2000),
                    currentDateDecoration: const BoxDecoration(),
                    currentDateTextStyle: const TextStyle(),
                    daysOfTheWeekTextStyle: const TextStyle(),
                    disabledCellsDecoration: const BoxDecoration(),
                    disabledCellsTextStyle: const TextStyle(),
                    enabledCellsDecoration: const BoxDecoration(),
                    enabledCellsTextStyle: const TextStyle(),
                    initialPickerType: PickerType.days,
                    selectedCellDecoration: BoxDecoration(
                      color: Theme.of(context).primaryColor,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    selectedCellTextStyle: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
                    leadingDateTextStyle: const TextStyle(),
                    slidersColor: Theme.of(context).primaryColor,
                    slidersSize: 20,
                    splashColor: Theme.of(context).primaryColor.withValues(alpha: 0.1),
                    splashRadius: 40,
                    centerLeadingDate: true,
                  );
                  if (picked != null && picked != _selectedDate) {
                    setState(() {
                      _selectedDate = picked;
                    });
                  }
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    border: Border.all(color: Colors.grey),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        _selectedDate != null
                            ? DateFormat('MMMM d, yyyy').format(_selectedDate!)
                            : 'Select your birthday...',
                        style: TextStyle(
                          color: _selectedDate != null ? Colors.black : Colors.grey[600],
                        ),
                      ),
                      const Icon(Icons.calendar_today, color: Colors.grey),
                    ],
                  ),
                ),
              ),
            ),
            _buildQuestionCard(
              icon: Icons.location_on,
              question: 'Where do you currently live?',
              child: InkWell(
                onTap: () {
                  showCountryPicker(
                    context: context,
                    showPhoneCode: false,
                    onSelect: (Country country) {
                      setState(() {
                        _selectedLocation = country.name;
                      });
                    },
                    countryListTheme: CountryListThemeData(
                      borderRadius: BorderRadius.circular(8),
                      inputDecoration: InputDecoration(
                        labelText: 'Search',
                        hintText: 'Start typing to search',
                        prefixIcon: const Icon(Icons.search),
                        border: OutlineInputBorder(
                          borderSide: BorderSide(
                            color: Colors.grey.withValues(alpha: 0.2),
                          ),
                        ),
                      ),
                    ),
                  );
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    border: Border.all(color: Colors.grey),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        _selectedLocation ?? 'Select your current location...',
                        style: TextStyle(
                          color: _selectedLocation != null ? Colors.black : Colors.grey[600],
                        ),
                      ),
                      const Icon(Icons.arrow_drop_down, color: Colors.grey),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildQuestionCard({
    required IconData icon,
    required String question,
    required Widget child,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 24),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.grey.withValues(alpha: 0.1),
            spreadRadius: 1,
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: Colors.blue, size: 24),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  question,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: Colors.black87,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          child,
        ],
      ),
    );
  }

  Widget _buildStep2() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Tell me more about you 💭',
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.bold,
              color: Colors.black87,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'These questions help me understand your inner world and how to support you better.',
            style: TextStyle(
              fontSize: 16,
              color: Colors.grey,
            ),
          ),
          const SizedBox(height: 32),
          _buildQuestionCard(
            icon: Icons.psychology,
            question: 'What\'s been taking up space in your mind lately?',
            child: _buildTextFieldWithVoice(
              controller: _mindSpaceController,
              controllerName: 'mindSpace',
              hintText: 'Share what\'s been on your mind recently...',
              maxLines: 3,
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please share what\'s been on your mind';
                }
                return null;
              },
            ),
          ),
          _buildQuestionCard(
            icon: Icons.star,
            question: 'What would future-you be proud of you for doing today — even just a small thing?',
            child: _buildTextFieldWithVoice(
              controller: _futureProudController,
              controllerName: 'futureProud',
              hintText: 'Think about what would make your future self proud...',
              maxLines: 3,
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please share what would make your future self proud';
                }
                return null;
              },
            ),
          ),
          _buildQuestionCard(
            icon: Icons.favorite,
            question: 'When do you usually feel most like yourself?',
            child: _buildTextFieldWithVoice(
              controller: _mostYourselfController,
              controllerName: 'mostYourself',
              hintText: 'Describe when you feel most authentic and true to yourself...',
              maxLines: 3,
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please share when you feel most like yourself';
                }
                return null;
              },
            ),
          ),
          _buildQuestionCard(
            icon: Icons.support,
            question: 'When you feel low, what do you usually turn to — a person, a habit, or something else?',
            child: _buildTextFieldWithVoice(
              controller: _lowMomentsController,
              controllerName: 'lowMoments',
              hintText: 'Share what helps you during difficult times...',
              maxLines: 3,
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please share what helps you during low moments';
                }
                return null;
              },
            ),
          ),
          _buildQuestionCard(
            icon: Icons.lightbulb,
            question: 'What\'s one thing you wish someone would just remind you when you\'re spiraling?',
            child: _buildTextFieldWithVoice(
              controller: _spiralReminderController,
              controllerName: 'spiralReminder',
              hintText: 'What reminder would help ground you during overwhelming moments...',
              maxLines: 3,
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please share what reminder would help you';
                }
                return null;
              },
            ),
          ),
          _buildQuestionCard(
            icon: Icons.celebration,
            question: 'What are you most proud about yourself?',
            child: _buildTextFieldWithVoice(
              controller: _proudOfSelfController,
              controllerName: 'proudOfSelf',
              hintText: 'Share something about yourself that makes you proud...',
              maxLines: 3,
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please share what you\'re proud of about yourself';
                }
                return null;
              },
            ),
          ),
          _buildQuestionCard(
            icon: Icons.auto_awesome,
            question: 'What is your dream?',
            child: _buildTextFieldWithVoice(
              controller: _dreamController,
              controllerName: 'dream',
              hintText: 'Describe your biggest dream or aspiration...',
              maxLines: 3,
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please share your dream';
                }
                return null;
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStep3() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Let\'s explore your growth 🌱',
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.bold,
              color: Colors.black87,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Understanding your challenges and aspirations helps me support your personal development.',
            style: TextStyle(
              fontSize: 16,
              color: Colors.grey,
            ),
          ),
          const SizedBox(height: 32),
          _buildQuestionCard(
            icon: Icons.refresh,
            question: 'What\'s one thing you keep saying you\'ll change... but haven\'t yet?',
            child: _buildTextFieldWithVoice(
              controller: _changeController,
              controllerName: 'change',
              hintText: 'Share something you\'ve been meaning to change about yourself...',
              maxLines: 3,
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please share something you want to change';
                }
                return null;
              },
            ),
          ),
          _buildQuestionCard(
            icon: Icons.visibility_off,
            question: 'What do you tend to avoid, even though you know you should face it?',
            child: _buildTextFieldWithVoice(
              controller: _avoidController,
              controllerName: 'avoid',
              hintText: 'Describe something you tend to avoid or put off...',
              maxLines: 3,
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please share what you tend to avoid';
                }
                return null;
              },
            ),
          ),
          _buildQuestionCard(
            icon: Icons.emoji_emotions,
            question: 'What feeling do you want to experience more this year?',
            child: _buildTextFieldWithVoice(
              controller: _feelingController,
              controllerName: 'feeling',
              hintText: 'Think about an emotion or feeling you\'d like to cultivate...',
              maxLines: 3,
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please share what feeling you want to experience more';
                }
                return null;
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStep4() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Tell me about your future self 🚀',
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.bold,
              color: Colors.black87,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Help me understand your vision for your future self so I can guide you toward that destination.',
            style: TextStyle(
              fontSize: 16,
              color: Colors.grey,
            ),
          ),
          const SizedBox(height: 32),
          _buildQuestionCard(
            icon: Icons.person_outline,
            question: 'In 3–5 words, how would you describe your Future self?',
            child: _buildTextFieldWithVoice(
              controller: _futureDescriptionController,
              controllerName: 'futureDescription',
              hintText: 'e.g., Confident, creative, fulfilled, peaceful...',
              maxLines: 1,
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please describe your future self';
                }
                return null;
              },
            ),
          ),
          _buildQuestionCard(
            icon: Icons.cake_outlined,
            question: 'How old is your Future self?',
            child: _buildTextFieldWithVoice(
              controller: _futureAgeController,
              controllerName: 'futureAge',
              hintText: 'Enter age (e.g., 35, 50, 65)...',
              maxLines: 1,
              keyboardType: TextInputType.number,
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please enter your future age';
                }
                final age = int.tryParse(value);
                if (age == null || age < 18 || age > 120) {
                  return 'Please enter a valid age between 18 and 120';
                }
                return null;
              },
            ),
          ),
          _buildQuestionCard(
            icon: Icons.schedule,
            question: 'Walk me through a typical day in your desired future life.',
            child: _buildTextFieldWithVoice(
              controller: _typicalDayController,
              controllerName: 'typicalDay',
              hintText: 'Describe your ideal daily routine, activities, and experiences...',
              maxLines: 4,
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please describe your typical future day';
                }
                return null;
              },
            ),
          ),
          _buildQuestionCard(
            icon: Icons.emoji_events,
            question: 'One day, you want to wake up and think: "I actually did it. I ______."',
            child: _buildTextFieldWithVoice(
              controller: _accomplishmentController,
              controllerName: 'accomplishment',
              hintText: 'Complete the sentence with your biggest aspiration...',
              maxLines: 3,
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please share your biggest accomplishment goal';
                }
                return null;
              },
            ),
          ),
          _buildQuestionCard(
            icon: Icons.photo_camera,
            question: 'Upload a photo if you\'d like me to imagine your Future Self.',
            child: Column(
              children: [
                if (_futurePhotoPath != null || _selectedImage != null)
                  Container(
                    height: 200,
                    width: double.infinity,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.grey[300]!),
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: _selectedImage != null
                          ? (kIsWeb && _webImageUrl != null
                              ? Image.network(
                                  _webImageUrl!,
                                  fit: BoxFit.cover,
                                  errorBuilder: (context, error, stackTrace) {
                                    return const Center(
                                      child: Icon(Icons.error, color: Colors.grey),
                                    );
                                  },
                                )
                              : Image.file(
                                  _selectedImage!,
                                  fit: BoxFit.cover,
                                ))
                          : Image.network(
                              _futurePhotoPath!,
                              fit: BoxFit.cover,
                              errorBuilder: (context, error, stackTrace) {
                                return const Center(
                                  child: Icon(Icons.error, color: Colors.grey),
                                );
                              },
                            ),
                    ),
                  )
                else
                  Container(
                    height: 120,
                    width: double.infinity,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.grey[300]!, style: BorderStyle.solid),
                      color: Colors.grey[50],
                    ),
                    child: const Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.photo_camera, size: 40, color: Colors.grey),
                        SizedBox(height: 8),
                        Text(
                          'Optional: Add a photo to help visualize your future self',
                          style: TextStyle(color: Colors.grey, fontSize: 14),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _isLoading ? null : _showImageSourceDialog,
                        icon: _isLoading 
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.upload),
                        label: Text(
                          _isLoading 
                              ? 'Uploading...' 
                              : (_futurePhotoPath != null || _selectedImage != null) 
                                  ? 'Change Photo' 
                                  : 'Upload Photo'
                        ),
                      ),
                    ),
                    if (_futurePhotoPath != null || _selectedImage != null) ...[
                      const SizedBox(width: 8),
                      OutlinedButton.icon(
                        onPressed: _isLoading ? null : () {
                          setState(() {
                            _futurePhotoPath = null;
                            _selectedImage = null;
                
                            _webImageUrl = null;
                          });
                        },
                        icon: const Icon(Icons.delete_outline, color: Colors.red),
                        label: const Text('Remove', style: TextStyle(color: Colors.red)),
                        style: OutlinedButton.styleFrom(
                          side: const BorderSide(color: Colors.red),
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStep5() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'How do you like to communicate? 💬',
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.bold,
              color: Colors.black87,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Help me understand your communication style so I can match your preferences.',
            style: TextStyle(
              fontSize: 16,
              color: Colors.grey,
            ),
          ),
          const SizedBox(height: 32),
          
          _buildQuestionCard(
            icon: Icons.chat_bubble_outline,
            question: 'What are some words or slang you use all the time?',
            child: _buildTextFieldWithVoice(
              controller: _wordsSlangController,
              controllerName: 'wordsSlang',
              hintText: 'e.g., "awesome", "no cap", "bet", "vibes"...',
              maxLines: 3,
              validator: (value) {
                if (value == null || value.trim().isEmpty) {
                  return 'Please share some words or phrases you use';
                }
                return null;
              },
            ),
          ),
          
          _buildQuestionCard(
            icon: Icons.message_outlined,
            question: 'Do you prefer long messages, or short and straight to the point?',
            child: Column(
              children: [
                RadioListTile<String>(
                  title: const Text('Long messages - I like details and context'),
                  value: 'long',
                  groupValue: _messagePreference,
                  onChanged: (value) {
                    setState(() {
                      _messagePreference = value!;
                    });
                  },
                ),
                RadioListTile<String>(
                  title: const Text('Short and straight to the point'),
                  value: 'short',
                  groupValue: _messagePreference,
                  onChanged: (value) {
                    setState(() {
                      _messagePreference = value!;
                    });
                  },
                ),
              ],
            ),
          ),
          
          _buildQuestionCard(
            icon: Icons.schedule_outlined,
            question: 'How often do you like to be messaged?',
            child: Column(
              children: [
                RadioListTile<String>(
                  title: const Text('Daily - I like regular check-ins'),
                  value: 'daily',
                  groupValue: _messagingFrequency,
                  onChanged: (value) {
                    setState(() {
                      _messagingFrequency = value!;
                    });
                  },
                ),
                RadioListTile<String>(
                  title: const Text('Weekly - A few times per week is good'),
                  value: 'weekly',
                  groupValue: _messagingFrequency,
                  onChanged: (value) {
                    setState(() {
                      _messagingFrequency = value!;
                    });
                  },
                ),
                RadioListTile<String>(
                  title: const Text('Only when needed - Minimal contact'),
                  value: 'minimal',
                  groupValue: _messagingFrequency,
                  onChanged: (value) {
                    setState(() {
                      _messagingFrequency = value!;
                    });
                  },
                ),
              ],
            ),
          ),
          
          _buildQuestionCard(
            icon: Icons.emoji_emotions_outlined,
            question: 'Emojis: love them, use a little, or never?',
            child: Column(
              children: [
                RadioListTile<String>(
                  title: const Text('😍 Love them - Use emojis frequently'),
                  value: 'love them',
                  groupValue: _emojiUsagePreference,
                  onChanged: (value) {
                    setState(() {
                      _emojiUsagePreference = value!;
                    });
                  },
                ),
                RadioListTile<String>(
                  title: const Text('🙂 Use a little - Occasional emojis are fine'),
                  value: 'use a little',
                  groupValue: _emojiUsagePreference,
                  onChanged: (value) {
                    setState(() {
                      _emojiUsagePreference = value!;
                    });
                  },
                ),
                RadioListTile<String>(
                  title: const Text('Never - Prefer text without emojis'),
                  value: 'never',
                  groupValue: _emojiUsagePreference,
                  onChanged: (value) {
                    setState(() {
                      _emojiUsagePreference = value!;
                    });
                  },
                ),
              ],
            ),
          ),
          

        ],
      ),
    );
  }
}