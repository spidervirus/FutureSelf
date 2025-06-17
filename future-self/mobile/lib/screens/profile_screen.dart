import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:io';
import 'package:flutter/foundation.dart';
// Conditional import for web
// import 'package:web/web.dart' as web; // Removed unused import
// import 'dart:js_interop'; // Removed unused import

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
  File? _selectedImageFile;
  XFile? _selectedXFile; // Restored: Used for web and to hold picked image file info
  String? _webImageUrl; 
  String? _profileImageUrl;
  bool _isLoading = true;
  bool _isSaving = false;
  String? _error;

  Map<String, dynamic>? _userData;
  bool _isUploading = false; // Restored: Used for loading indicator during image upload

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

      final userDataResponse = await Supabase.instance.client
          .from('users')
          .select('*')
          .eq('id', user.id)
          .single();

      setState(() {
        _userData = userDataResponse; // Store fetched user data
        _nameController.text = _userData?['name'] ?? '';
        _emailController.text = user.email ?? '';
        _ageController.text = _userData?['age']?.toString() ?? '';
        _nationalityController.text = _userData?['nationality'] ?? '';
        _locationController.text = _userData?['location'] ?? '';
        _goalsController.text = (_userData?['top_goals'] as List?)?.join('\n') ?? '';
        _thoughtsController.text = _userData?['current_thoughts'] ?? '';
        _feelingsController.text = _userData?['current_feelings'] ?? '';
        _growthController.text = _userData?['growth_areas'] ?? '';
        _visionController.text = _userData?['future_vision'] ?? '';
        _profileImageUrl = _userData?['future_photo_path'];
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
      final XFile? pickedImage = await _picker.pickImage(
        source: source,
        maxWidth: 1024,
        maxHeight: 1024,
        imageQuality: 85,
      );

      if (pickedImage != null) {
        _selectedXFile = pickedImage; // Assign to the field

        if (kIsWeb) {
          // For web, use image.path (which is a blob URL) for immediate display
          if (_selectedXFile != null) { // Use the field for condition and access
            setState(() {
              _webImageUrl = _selectedXFile!.path;
              _selectedImageFile = null; // Clear mobile-specific file
            });
            await _uploadImageWeb(_selectedXFile!); // Pass the field to the upload method
          }
        } else {
          if (_selectedXFile != null) { // Use the field for condition and access
            setState(() {
              _selectedImageFile = File(_selectedXFile!.path);
              _webImageUrl = null; // Clear web-specific URL
            });
            await _uploadImage(); // Uses _selectedImageFile for mobile upload
          }
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

  // Method _uploadImage(File imageFile) from lines 158-190 is REMOVED as it's redundant/conflicting

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

      // Image upload is handled by _pickImageFromSource and its subsequent calls to _uploadImageWeb or _uploadImage.
      // _selectedXFile will be non-null if an image was picked.

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
        // 'future_photo_path' is updated by _uploadImageWeb or _uploadImage methods directly.
      }).eq('id', user.id);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Profile updated successfully!')),
        );
        setState(() {
          // _profileImageUrl is updated by upload methods via _userData
          _selectedImageFile = null; // Clear selection after save
          _selectedXFile = null; // Clear XFile selection
          // _webImageUrl might hold Supabase URL if last action was web upload, or blob url. Clear if not needed after save.
          // For simplicity, let's not clear _webImageUrl here as it might be the Supabase URL.
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
    ImageProvider? imageProvider = _getResolvedBackgroundImageProvider();

    return Stack(
      alignment: Alignment.bottomRight,
      children: [
        CircleAvatar(
          radius: 60,
          backgroundImage: imageProvider,
          child: imageProvider == null && !_isUploading
              ? const Icon(Icons.person, size: 60)
              : null,
        ),
        if (_isUploading)
          const Positioned.fill(
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
            ),
          ),
        if (!_isUploading)
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
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        actions: [
          if (_isSaving || _isUploading)
            const Padding(
              padding: EdgeInsets.all(16.0),
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2, valueColor: AlwaysStoppedAnimation<Color>(Colors.white)),
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
  } // This is the closing brace for ProfileScreenState class

  ImageProvider? _getResolvedBackgroundImageProvider() {
    ImageProvider? resolvedBackgroundImage;
    if (kIsWeb) {
      if (_webImageUrl != null) { // Web has a selected/preview image or uploaded image URL
        resolvedBackgroundImage = NetworkImage(_webImageUrl!);
      }
    } else { // Mobile
      if (_selectedImageFile != null) { // Mobile has a selected image
        resolvedBackgroundImage = FileImage(_selectedImageFile!);
      }
    }
    // If no selected image, use profileImageUrl from Supabase
    if (resolvedBackgroundImage == null && _profileImageUrl != null && _profileImageUrl!.isNotEmpty) {
      resolvedBackgroundImage = NetworkImage(_profileImageUrl!);
    }
    return resolvedBackgroundImage;
  }

  Future<void> _uploadImageWeb(XFile imageFile) async {
    if (!mounted) return;
    setState(() { 
      _isUploading = true;
    });

    try {
      final user = Supabase.instance.client.auth.currentUser;
      if (user == null) throw Exception('User not authenticated');

      final fileName = 'profile_${user.id}_${DateTime.now().millisecondsSinceEpoch}.jpg';
      final bytes = await imageFile.readAsBytes();
      final filePath = 'profile_images/$fileName'; // Ensure consistent path

      await Supabase.instance.client.storage
          .from('user-uploads') // Ensure correct bucket name
          .uploadBinary(filePath, bytes);

      final publicUrl = Supabase.instance.client.storage
          .from('user-uploads') // Ensure correct bucket name
          .getPublicUrl(filePath);

      await Supabase.instance.client
          .from('users')
          .update({'future_photo_path': publicUrl})
          .eq('id', user.id);

      if (mounted) {
        setState(() {
          _userData?['future_photo_path'] = publicUrl;
          _profileImageUrl = publicUrl; 
          _webImageUrl = publicUrl; 
          _selectedImageFile = null; 
          _selectedXFile = null; // Clear XFile after successful web upload
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Profile picture updated!'), backgroundColor: Colors.green),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error uploading image: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) {
        setState(() { 
         _isUploading = false;
        });
      }
    }
  }

  Future<void> _uploadImage() async { 
    if (_selectedImageFile == null) return;
    if (!mounted) return;

    setState(() { 
     _isUploading = true;
    });

    try {
      final user = Supabase.instance.client.auth.currentUser;
      if (user == null) throw Exception('User not authenticated');

      final fileName = 'profile_${user.id}_${DateTime.now().millisecondsSinceEpoch}.jpg';
      final filePath = 'profile_images/$fileName'; // Ensure consistent path

      await Supabase.instance.client.storage
          .from('user-uploads') // Ensure correct bucket name
          .upload(filePath, _selectedImageFile!); 

      final publicUrl = Supabase.instance.client.storage
          .from('user-uploads') // Ensure correct bucket name
          .getPublicUrl(filePath);

      await Supabase.instance.client
          .from('users')
          .update({'future_photo_path': publicUrl})
          .eq('id', user.id);

      if (mounted) {
        setState(() {
          _userData?['future_photo_path'] = publicUrl;
          _profileImageUrl = publicUrl; 
          _selectedImageFile = null; 
          _selectedXFile = null; // Clear XFile after successful mobile upload
          _webImageUrl = null; 
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Profile picture updated!'), backgroundColor: Colors.green),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error uploading image: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) {
        setState(() { 
          _isUploading = false;
        });
      }
    }
  }

} // This is the closing brace for ProfileScreenState class