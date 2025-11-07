import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:timeago/timeago.dart' as timeago;
import '../models/diary_entry.dart';
import '../services/api_client.dart';
import '../services/sync_service.dart';
import 'entry_edit_screen.dart';

class DiaryEntriesScreen extends StatefulWidget {
  const DiaryEntriesScreen({super.key});

  @override
  State<DiaryEntriesScreen> createState() => _DiaryEntriesScreenState();
}

class _DiaryEntriesScreenState extends State<DiaryEntriesScreen> {
  List<DiaryEntry> _entries = [];
  bool _isLoading = true;
  SyncStatus? _syncStatus;

  @override
  void initState() {
    super.initState();
    _loadEntries();
    _performSync();
  }

  Future<void> _loadEntries() async {
    setState(() => _isLoading = true);

    try {
      // Load all entries from server (desktop + mobile)
      final apiClient = context.read<ApiClient>();
      final entries = await apiClient.getRecentEntries(limit: 100);

      setState(() {
        _entries = entries;
        _isLoading = false;
      });
    } catch (e) {
      print('Error loading entries: $e');
      setState(() => _isLoading = false);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Could not load entries from server: $e'),
            backgroundColor: Colors.orange,
          ),
        );
      }
    }
  }

  Future<void> _performSync() async {
    final syncService = context.read<SyncService>();
    final result = await syncService.syncWithRetry();

    if (result.success) {
      await _loadEntries();
    }

    setState(() {
      _syncStatus = syncService.getSyncStatus();
    });
  }

  Future<void> _handleManualSync() async {
    final syncService = context.read<SyncService>();

    setState(() {
      _syncStatus = syncService.getSyncStatus();
    });

    final result = await syncService.syncWithRetry();

    if (result.success) {
      await _loadEntries();

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Synced: ${result.uploadedCount} uploaded, ${result.downloadedCount} downloaded',
            ),
            backgroundColor: Colors.green,
          ),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(result.message),
            backgroundColor: result.offlineMode ? Colors.orange : Colors.red,
          ),
        );
      }
    }

    setState(() {
      _syncStatus = syncService.getSyncStatus();
    });
  }

  void _navigateToNewEntry() async {
    final result = await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => const EntryEditScreen(),
      ),
    );

    if (result == true) {
      _loadEntries();
      _handleManualSync();
    }
  }

  void _navigateToEntry(DiaryEntry entry) async {
    final result = await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => EntryEditScreen(entry: entry),
      ),
    );

    if (result == true) {
      _loadEntries();
      _handleManualSync();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Diary Entries'),
        actions: [
          // Sync button
          IconButton(
            icon: _syncStatus?.isSyncing == true
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.sync),
            onPressed: _syncStatus?.isSyncing == true ? null : _handleManualSync,
            tooltip: _syncStatus?.statusText ?? 'Sync',
          ),
        ],
      ),
      body: _buildBody(),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _navigateToNewEntry,
        icon: const Icon(Icons.add),
        label: const Text('New Entry'),
        backgroundColor: Theme.of(context).colorScheme.primary,
      ),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_entries.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.auto_stories_outlined,
              size: 80,
              color: Colors.grey.shade700,
            ),
            const SizedBox(height: 16),
            Text(
              'No entries yet',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    color: Colors.grey.shade700,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              'Tap the button below to start journaling',
              style: TextStyle(color: Colors.grey.shade600),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () async {
        await _loadEntries();
        await _handleManualSync();
      },
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _entries.length,
        itemBuilder: (context, index) {
          final entry = _entries[index];
          return _buildEntryCard(entry);
        },
      ),
    );
  }

  Widget _buildEntryCard(DiaryEntry entry) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: InkWell(
        onTap: () => _navigateToEntry(entry),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header row
              Row(
                children: [
                  // Mood emoji
                  Text(
                    entry.moodEmoji,
                    style: const TextStyle(fontSize: 32),
                  ),

                  const SizedBox(width: 12),

                  // Date and time
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _formatDate(entry.timestamp),
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        Text(
                          timeago.format(entry.timestamp),
                          style: TextStyle(
                            color: Colors.grey.shade600,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Sync status
                  if (!entry.synced)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.orange.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.cloud_upload,
                            size: 14,
                            color: Colors.orange.shade300,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            'Pending',
                            style: TextStyle(
                              color: Colors.orange.shade300,
                              fontSize: 11,
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              ),

              const SizedBox(height: 12),

              // Full content
              Text(
                entry.content,
                style: Theme.of(context).textTheme.bodyMedium,
              ),

              // Moods bar (if available)
              if (entry.moods.isNotEmpty) ...[
                const SizedBox(height: 12),
                _buildMoodsBar(entry.moods),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMoodsBar(Map<String, double> moods) {
    final sortedMoods = moods.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    final topMoods = sortedMoods.take(3);

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: topMoods.map((mood) {
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: _getMoodColor(mood.key).withOpacity(0.2),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: _getMoodColor(mood.key).withOpacity(0.5),
            ),
          ),
          child: Text(
            '${mood.key} ${(mood.value * 100).toInt()}%',
            style: TextStyle(
              color: _getMoodColor(mood.key),
              fontSize: 11,
              fontWeight: FontWeight.w500,
            ),
          ),
        );
      }).toList(),
    );
  }

  Color _getMoodColor(String mood) {
    const moodColors = {
      'joy': Colors.yellow,
      'love': Colors.pink,
      'sadness': Colors.blue,
      'anger': Colors.red,
      'fear': Colors.purple,
      'surprise': Colors.orange,
    };

    return moodColors[mood] ?? Colors.grey;
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));
    final entryDate = DateTime(date.year, date.month, date.day);

    if (entryDate == today) {
      return 'Today, ${_formatTime(date)}';
    } else if (entryDate == yesterday) {
      return 'Yesterday, ${_formatTime(date)}';
    } else {
      return '${date.month}/${date.day}/${date.year} ${_formatTime(date)}';
    }
  }

  String _formatTime(DateTime date) {
    final hour = date.hour > 12 ? date.hour - 12 : (date.hour == 0 ? 12 : date.hour);
    final period = date.hour >= 12 ? 'PM' : 'AM';
    final minute = date.minute.toString().padLeft(2, '0');
    return '$hour:$minute $period';
  }
}
