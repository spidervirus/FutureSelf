import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:io';
import 'package:flutter/foundation.dart';
// Conditional import for web
import 'package:web/web.dart' as web;
import 'dart:js_interop';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  ProfileScreenState createState() => ProfileScreenState();
}

class ProfileScreenState extends State<ProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _ageController = TextEditingController();
  final _nationalityController = TextEditingController();
  final _locationController = TextEditingController();
  final _goalsController = TextEditingController();
  final _thoughtsController = TextEditingController();
  final _feelingsController = TextEditingController();
  final _growthController = TextEditingController();
  final _visionController = TextEditingController();
  
  final ImagePicker _picker = ImagePicker();
  File? _selectedImage;
  XFile? _selectedXFile; // For web compatibility
  String? _webImageUrl; // For displaying web images
  String? _profileImageUrl;
  bool _isLoading = true;
  bool _isSaving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadUserProfile();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _ageController.dispose();
    _nationalityController.dispose();
    _locationController.dispose();
    _goalsController.dispose();
    _thoughtsController.dispose();
    _feelingsController.dispose();
    _growthController.dispose();
    _visionController.dispose();
    super.dispose();
  }

  Future<void> _loadUserProfile() async {
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
          .select('*')
          .eq('id', user.id)
          .single();

      setState(() {
        _nameController.text = userData['name'] ?? '';
        _emailController.text = user.email ?? '';
        _ageController.text = userData['age']?.toString() ?? '';
        _nationalityController.text = userData['nationality'] ?? '';
        _locationController.text = userData['location'] ?? '';
        _goalsController.text = (userData['top_goals'] as List?)?.join('\n') ?? '';
        _thoughtsController.text = userData['current_thoughts'] ?? '';
        _feelingsController.text = userData['current_feelings'] ?? '';
        _growthController.text = userData['growth_areas'] ?? '';
        _visionController.text = userData['future_vision'] ?? '';
        _profileImageUrl = userData['future_photo_path'];
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Failed to load profile: ${e.toString()}';
        _isLoading = false;
      });
    }
  }

  Future<void> _showImageSourceDialog() async {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('Select Image Source'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                leading: const Icon(Icons.camera_alt),
                title: const Text('Camera'),
                onTap: () {
                  Navigator.of(context).pop();
                  _pickImageFromSource(ImageSource.camera);
                },
              ),
              ListTile(
                leading: const Icon(Icons.photo_library),
                title: const Text('Gallery'),
                onTap: () {
                  Navigator.of(context).pop();
                  _pickImageFromSource(ImageSource.gallery);
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
      final XFile? pickedFile = await _picker.pickImage(
        source: source,
        maxWidth: 800,
        maxHeight: 800,
        imageQuality: 85,
      );

      if (pickedFile != null) {
        if (kIsWeb) {
          // For web, create a blob URL for immediate display
          final bytes = await pickedFile.readAsBytes();
          final blob = web.Blob([bytes.toJS].toJS);
          final url = web.URL.createObjectURL(blob);
          
          setState(() {
            _selectedImage = File(pickedFile.path); // Placeholder
            _selectedXFile = pickedFile;
            _webImageUrl = url;
          });
        } else {
          setState(() {
            _selectedImage = File(pickedFile.path);
          });
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error picking image: ${e.toString()}')),
        );
      }
    }
  }

  Future<String?> _uploadImage(File imageFile) async {
    try {
      final user = Supabase.instance.client.auth.currentUser;
      if (user == null) return null;

      final fileName = 'profile_${user.id}_${DateTime.now().millisecondsSinceEpoch}.jpg';
      final filePath = 'profile_images/$fileName';

      if (kIsWeb && _selectedXFile != null) {
        // For web, use uploadBinary with bytes
        final bytes = await _selectedXFile!.readAsBytes();
        await Supabase.instance.client.storage
            .from('user-uploads')
            .uploadBinary(filePath, bytes);
      } else {
        // For mobile, use regular upload
        await Supabase.instance.client.storage
            .from('user-uploads')
            .upload(filePath, imageFile);
      }

      final publicUrl = Supabase.instance.client.storage
          .from('user-uploads')
          .getPublicUrl(filePath);

      return publicUrl;
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error uploading image: ${e.toString()}')),
        );
      }
      return null;
    }
  }

  Future<void> _saveProfile() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isSaving = true;
    });

    try {
      final user = Supabase.instance.client.auth.currentUser;
      if (user == null) {
        throw Exception('User not authenticated');
      }

      String? imageUrl = _profileImageUrl;
      if (_selectedImage != null) {
        imageUrl = await _uploadImage(_selectedImage!);
      }

      final goals = _goalsController.text
          .split('\n')
          .where((goal) => goal.trim().isNotEmpty)
          .toList();

      await Supabase.instance.client.from('users').update({
        'name': _nameController.text,
        'age': int.tryParse(_ageController.text),
        'nationality': _nationalityController.text,
        'location': _locationController.text,
        'top_goals': goals,
        'current_thoughts': _thoughtsController.text,
        'current_feelings': _feelingsController.text,
        'growth_areas': _growthController.text,
        'future_vision': _visionController.text,
        if (imageUrl != null) 'future_photo_path': imageUrl,
      }).eq('id', user.id);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Profile updated successfully!')),
        );
        setState(() {
          _profileImageUrl = imageUrl;
          _selectedImage = null;
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error saving profile: ${e.toString()}')),
        );
      }
    } finally {
      setState(() {
        _isSaving = false;
      });
    }
  }

  Widget _buildProfileImage() {
    return Center(
      child: Stack(
        children: [
          CircleAvatar(
            radius: 60,
            backgroundColor: Colors.grey[300],
            backgroundImage: _selectedImage != null
                ? (kIsWeb && _webImageUrl != null
                    ? NetworkImage(_webImageUrl!)
                    : FileImage(_selectedImage!))
                : _profileImageUrl != null
                    ? NetworkImage(_profileImageUrl!)
                    : null,
            child: (_selectedImage == null && _profileImageUrl == null)
                ? const Icon(Icons.person, size: 60, color: Colors.grey)
                : null,
          ),
          Positioned(
            bottom: 0,
            right: 0,
            child: CircleAvatar(
              radius: 18,
              backgroundColor: Theme.of(context).primaryColor,
              child: IconButton(
                icon: const Icon(Icons.camera_alt, size: 18, color: Colors.white),
                onPressed: _showImageSourceDialog,
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
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
              onPressed: _saveProfile,
              child: const Text('Save', style: TextStyle(color: Colors.white)),
            ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('Error: $_error'))
              : Form(
                  key: _formKey,
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildProfileImage(),
                        const SizedBox(height: 24),
                        TextFormField(
                          controller: _nameController,
                          decoration: const InputDecoration(
                            labelText: 'Name',
                            border: OutlineInputBorder(),
                          ),
                          validator: (value) {
                            if (value == null || value.isEmpty) {
                              return 'Please enter your name';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _emailController,
                          decoration: const InputDecoration(
                            labelText: 'Email',
                            border: OutlineInputBorder(),
                          ),
                          enabled: false,
                        ),
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _ageController,
                          decoration: const InputDecoration(
                            labelText: 'Age',
                            border: OutlineInputBorder(),
                          ),
                          keyboardType: TextInputType.number,
                        ),
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _nationalityController,
                          decoration: const InputDecoration(
                            labelText: 'Nationality',
                            border: OutlineInputBorder(),
                          ),
                        ),
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _locationController,
                          decoration: const InputDecoration(
                            labelText: 'Location',
                            border: OutlineInputBorder(),
                          ),
                        ),
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _goalsController,
                          decoration: const InputDecoration(
                            labelText: 'Top Goals (one per line)',
                            border: OutlineInputBorder(),
                            alignLabelWithHint: true,
                          ),
                          maxLines: 4,
                        ),
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _thoughtsController,
                          decoration: const InputDecoration(
                            labelText: 'Current Thoughts',
                            border: OutlineInputBorder(),
                            alignLabelWithHint: true,
                          ),
                          maxLines: 3,
                        ),
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _feelingsController,
                          decoration: const InputDecoration(
                            labelText: 'Current Feelings',
                            border: OutlineInputBorder(),
                            alignLabelWithHint: true,
                          ),
                          maxLines: 3,
                        ),
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _growthController,
                          decoration: const InputDecoration(
                            labelText: 'Growth Areas',
                            border: OutlineInputBorder(),
                            alignLabelWithHint: true,
                          ),
                          maxLines: 3,
                        ),
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _visionController,
                          decoration: const InputDecoration(
                            labelText: 'Future Vision',
                            border: OutlineInputBorder(),
                            alignLabelWithHint: true,
                          ),
                          maxLines: 4,
                        ),
                        const SizedBox(height: 24),
                      ],
                    ),
                  ),
                ),
    );
  }
}