import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/sync_service.dart';
import '../services/api_client.dart';
import 'entry_edit_screen.dart';
import 'insights_screen.dart';
import 'chat_screen.dart';
import 'login_screen.dart';
import 'diary_entries_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _isLoading = true;
  SyncStatus? _syncStatus;
  Map<String, dynamic>? _insights;
  int _entryCount = 0;

  @override
  void initState() {
    super.initState();
    _loadDashboardData();
    _performInitialSync();
  }

  Future<void> _loadDashboardData() async {
    setState(() => _isLoading = true);

    try {
      final apiClient = context.read<ApiClient>();

      // Load insights summary
      final insights = await apiClient.getInsightsSummary(days: 7);

      // Load entry count
      final entries = await apiClient.getRecentEntries(limit: 100);

      setState(() {
        _insights = insights;
        _entryCount = entries.length;
        _isLoading = false;
      });
    } catch (e) {
      print('Error loading dashboard: $e');
      setState(() => _isLoading = false);
    }
  }

  Future<void> _performInitialSync() async {
    final syncService = context.read<SyncService>();

    // Perform sync in background
    final result = await syncService.syncWithRetry();

    if (result.success) {
      // Reload dashboard data after sync
      await _loadDashboardData();
    }

    // Update sync status
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
      await _loadDashboardData();

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
      _loadDashboardData();
      _handleManualSync();
    }
  }

  void _navigateToDiaryEntries() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => const DiaryEntriesScreen(),
      ),
    ).then((_) => _loadDashboardData());
  }

  void _navigateToInsights() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => const InsightsScreen(),
      ),
    );
  }

  void _navigateToChat() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => const ChatScreen(),
      ),
    );
  }

  Future<void> _handleLogout() async {
    // Show confirmation dialog
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Logout'),
        content: const Text('Are you sure you want to logout? You will need to login again to sync with the server.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Logout'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      try {
        // Logout from API client
        final apiClient = context.read<ApiClient>();
        await apiClient.logout();

        // Navigate back to login screen and clear navigation stack
        if (mounted) {
          Navigator.pushAndRemoveUntil(
            context,
            MaterialPageRoute(builder: (_) => const LoginScreen()),
            (route) => false, // Remove all previous routes
          );
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Logout error: $e'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('DiaryML'),
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

          // Chat button
          IconButton(
            icon: const Icon(Icons.chat),
            onPressed: _navigateToChat,
            tooltip: 'Chat with AI',
          ),

          // Insights button
          IconButton(
            icon: const Icon(Icons.insights),
            onPressed: _navigateToInsights,
            tooltip: 'Insights',
          ),

          // Logout button
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: _handleLogout,
            tooltip: 'Logout',
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

    return RefreshIndicator(
      onRefresh: () async {
        await _loadDashboardData();
        await _handleManualSync();
      },
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Welcome header
            Text(
              'Welcome to DiaryML',
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              'Your private AI-powered journal',
              style: TextStyle(
                color: Colors.grey.shade600,
                fontSize: 16,
              ),
            ),
            const SizedBox(height: 24),

            // Stats card
            _buildStatsCard(),
            const SizedBox(height: 16),

            // Quick actions
            Text(
              'Quick Actions',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 12),

            // Navigation cards
            _buildNavigationCard(
              title: 'Diary Entries',
              subtitle: '$_entryCount entries',
              icon: Icons.book,
              color: Colors.blue,
              onTap: _navigateToDiaryEntries,
            ),
            const SizedBox(height: 12),

            _buildNavigationCard(
              title: 'Chat with AI',
              subtitle: 'Get insights and reflections',
              icon: Icons.chat_bubble,
              color: Colors.purple,
              onTap: _navigateToChat,
            ),
            const SizedBox(height: 12),

            _buildNavigationCard(
              title: 'Insights & Analytics',
              subtitle: 'Discover patterns and trends',
              icon: Icons.insights,
              color: Colors.orange,
              onTap: _navigateToInsights,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatsCard() {
    final mood = _insights?['top_emotion'] ?? 'neutral';
    final streak = _insights?['streak'] ?? 0;
    final projects = _insights?['top_projects'] as List? ?? [];

    final List<Widget> statsWidgets = [
      Text(
        'Your Week at a Glance',
        style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.bold,
            ),
      ),
      const SizedBox(height: 16),
      Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.yellow.withOpacity(0.2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.mood, color: Colors.orange),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Current Mood'),
              Text(
                mood.toUpperCase(),
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                ),
              ),
            ],
          ),
        ],
      ),
      const SizedBox(height: 16),
      Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.green.withOpacity(0.2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.local_fire_department, color: Colors.orange),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Writing Streak'),
              Text(
                '$streak days',
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                ),
              ),
            ],
          ),
        ],
      ),
    ];

    if (projects.isNotEmpty) {
      statsWidgets.add(const SizedBox(height: 16));
      statsWidgets.add(
        Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.blue.withOpacity(0.2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.work, color: Colors.blue),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Active Projects'),
                  Text(
                    projects.take(2).join(', '),
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: statsWidgets,
        ),
      ),
    );
  }

  Widget _buildNavigationCard({
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
  }) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: color, size: 28),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                    Text(
                      subtitle,
                      style: TextStyle(
                        color: Colors.grey.shade600,
                        fontSize: 14,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.arrow_forward_ios, size: 16, color: Colors.grey.shade400),
            ],
          ),
        ),
      ),
    );
  }
}
