import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:image_picker/image_picker.dart';
import 'dart:io';
import '../models/diary_entry.dart';
import '../services/local_database.dart';

class EntryEditScreen extends StatefulWidget {
  final DiaryEntry? entry; // null for new entry

  const EntryEditScreen({super.key, this.entry});

  @override
  State<EntryEditScreen> createState() => _EntryEditScreenState();
}

class _EntryEditScreenState extends State<EntryEditScreen> {
  final _contentController = TextEditingController();
  final _speech = stt.SpeechToText();

  bool _isListening = false;
  bool _speechAvailable = false;
  bool _isSaving = false;
  File? _selectedImage;

  @override
  void initState() {
    super.initState();
    _initSpeech();

    if (widget.entry != null) {
      _contentController.text = widget.entry!.content;
    }
  }

  Future<void> _initSpeech() async {
    _speechAvailable = await _speech.initialize(
      onStatus: (status) => print('Speech status: $status'),
      onError: (error) => print('Speech error: $error'),
    );
    setState(() {});
  }

  Future<void> _startListening() async {
    if (!_speechAvailable) return;

    setState(() => _isListening = true);

    await _speech.listen(
      onResult: (result) {
        setState(() {
          _contentController.text = result.recognizedWords;
        });
      },
    );
  }

  Future<void> _stopListening() async {
    await _speech.stop();
    setState(() => _isListening = false);
  }

  Future<void> _pickImage() async {
    final picker = ImagePicker();
    final pickedFile = await picker.pickImage(source: ImageSource.gallery);

    if (pickedFile != null) {
      setState(() {
        _selectedImage = File(pickedFile.path);
      });
    }
  }

  Future<void> _saveEntry() async {
    if (_contentController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please write something first')),
      );
      return;
    }

    setState(() => _isSaving = true);

    try {
      final localDb = context.read<LocalDatabase>();

      if (widget.entry != null) {
        // Update existing entry (insertEntry uses REPLACE, so it updates)
        final updatedEntry = widget.entry!.copyWith(
          content: _contentController.text.trim(),
          imagePath: _selectedImage?.path,
          synced: false, // Mark as unsynced since we modified it
          lastModified: DateTime.now(),
        );

        await localDb.insertEntry(updatedEntry);

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Entry updated')),
          );
          Navigator.pop(context, true); // Return true to trigger refresh
        }
      } else {
        // Create new entry
        final entry = DiaryEntry(
          mobileId: DateTime.now().millisecondsSinceEpoch.toString(),
          content: _contentController.text.trim(),
          timestamp: DateTime.now(),
          imagePath: _selectedImage?.path,
          synced: false,
        );

        await localDb.insertEntry(entry);

        if (mounted) {
          Navigator.pop(context, true); // Return true to trigger refresh
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error saving entry: $e')),
        );
      }
    } finally {
      setState(() => _isSaving = false);
    }
  }

  Future<void> _deleteEntry() async {
    if (widget.entry == null) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Entry'),
        content: const Text('Are you sure you want to delete this entry? This cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      try {
        final localDb = context.read<LocalDatabase>();

        // Delete by ID if available (synced entries), otherwise by mobile ID
        if (widget.entry!.id != null) {
          await localDb.deleteEntry(widget.entry!.id!);
        } else if (widget.entry!.mobileId != null) {
          await localDb.deleteEntryByMobileId(widget.entry!.mobileId!);
        }

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Entry deleted')),
          );
          Navigator.pop(context, true); // Return true to trigger refresh
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error deleting entry: $e')),
          );
        }
      }
    }
  }

  @override
  void dispose() {
    _contentController.dispose();
    _speech.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.entry == null ? 'New Entry' : 'Edit Entry'),
        actions: [
          // Delete button (only for existing entries)
          if (widget.entry != null && !_isSaving)
            IconButton(
              icon: const Icon(Icons.delete),
              onPressed: _deleteEntry,
              tooltip: 'Delete',
            ),

          // Save button
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
            IconButton(
              icon: const Icon(Icons.check),
              onPressed: _saveEntry,
              tooltip: 'Save',
            ),
        ],
      ),
      body: Column(
        children: [
          // Image preview
          if (_selectedImage != null)
            Container(
              height: 200,
              width: double.infinity,
              decoration: BoxDecoration(
                image: DecorationImage(
                  image: FileImage(_selectedImage!),
                  fit: BoxFit.cover,
                ),
              ),
              child: Align(
                alignment: Alignment.topRight,
                child: IconButton(
                  icon: const Icon(Icons.close, color: Colors.white),
                  onPressed: () => setState(() => _selectedImage = null),
                ),
              ),
            ),

          // Content editor
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: TextField(
                controller: _contentController,
                decoration: const InputDecoration(
                  hintText: 'What\'s on your mind?',
                  border: InputBorder.none,
                ),
                maxLines: null,
                expands: true,
                autofocus: true,
                textAlignVertical: TextAlignVertical.top,
              ),
            ),
          ),

          // Action bar
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Theme.of(context).cardColor,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.1),
                  blurRadius: 4,
                  offset: const Offset(0, -2),
                ),
              ],
            ),
            child: Row(
              children: [
                // Voice input button
                IconButton(
                  icon: Icon(_isListening ? Icons.mic : Icons.mic_none),
                  onPressed: _isListening ? _stopListening : _startListening,
                  tooltip: _isListening ? 'Stop listening' : 'Voice input',
                  color: _isListening
                      ? Colors.red
                      : (_speechAvailable ? null : Colors.grey),
                ),

                // Camera button
                IconButton(
                  icon: const Icon(Icons.photo_camera),
                  onPressed: _pickImage,
                  tooltip: 'Add image',
                ),

                const Spacer(),

                // Character count
                Text(
                  '${_contentController.text.length} characters',
                  style: TextStyle(
                    color: Colors.grey.shade600,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
