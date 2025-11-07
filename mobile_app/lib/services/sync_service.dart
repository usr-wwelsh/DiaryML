import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import '../models/diary_entry.dart';
import 'api_client.dart';
import 'local_database.dart';

/// Sync Service - Error-Resistant Bidirectional Sync
/// Handles offline queue, conflict resolution, and retry logic
class SyncService {
  final ApiClient apiClient;
  final LocalDatabase localDb;

  bool _isSyncing = false;
  DateTime? _lastSuccessfulSync;
  List<String> _syncErrors = [];

  SyncService({
    required this.apiClient,
    required this.localDb,
  });

  /// Perform full bidirectional sync
  /// Returns success status and any errors
  Future<SyncResult> sync() async {
    if (_isSyncing) {
      return SyncResult(
        success: false,
        message: 'Sync already in progress',
      );
    }

    _isSyncing = true;
    _syncErrors = [];

    try {
      // Check connectivity
      final connectivityResult = await Connectivity().checkConnectivity();
      if (connectivityResult == ConnectivityResult.none) {
        return SyncResult(
          success: false,
          message: 'No internet connection',
          offlineMode: true,
        );
      }

      // Get unsynced entries
      final unsyncedEntries = await localDb.getUnsyncedEntries();

      // Get last sync time
      final lastSync = await localDb.getLastSyncTime();

      print('Syncing ${unsyncedEntries.length} unsynced entries...');

      // Perform sync
      final syncResponse = await apiClient.sync(
        lastSync: lastSync,
        pendingEntries: unsyncedEntries,
      );

      // Process uploaded entries (mark as synced)
      final newEntries = syncResponse['new_entries'] as List? ?? [];
      for (final entry in newEntries) {
        if (entry['synced'] == true) {
          final mobileId = entry['mobile_id'] as String?;
          final serverId = entry['server_id'] as int?;

          if (mobileId != null && serverId != null) {
            await localDb.markAsSynced(mobileId, serverId);
            print('Marked entry $mobileId as synced with server ID $serverId');
          }
        }
      }

      // Process downloaded entries (insert/update)
      final updatedEntries = syncResponse['updated_entries'] as List? ?? [];
      for (final entryJson in updatedEntries) {
        try {
          final entry = DiaryEntry.fromJson(entryJson);
          await localDb.insertEntry(entry.copyWith(synced: true));
          print('Downloaded entry ${entry.id}');
        } catch (e) {
          _syncErrors.add('Failed to import entry: $e');
          print('Error importing entry: $e');
        }
      }

      // Process conflicts
      final conflicts = syncResponse['sync_conflicts'] as List? ?? [];
      for (final conflict in conflicts) {
        _syncErrors.add('Conflict: ${conflict['error']}');
        print('Sync conflict: ${conflict['mobile_id']} - ${conflict['error']}');
      }

      // Update last sync timestamp
      final serverTimestamp = syncResponse['server_timestamp'];
      if (serverTimestamp != null) {
        final syncTime = DateTime.parse(serverTimestamp);
        await localDb.updateLastSyncTime(syncTime);
        _lastSuccessfulSync = syncTime;
      }

      return SyncResult(
        success: true,
        message: 'Sync completed successfully',
        uploadedCount: newEntries.length,
        downloadedCount: updatedEntries.length,
        conflictCount: conflicts.length,
      );
    } catch (e) {
      print('Sync error: $e');
      _syncErrors.add(e.toString());

      return SyncResult(
        success: false,
        message: 'Sync failed: ${e.toString()}',
        errors: _syncErrors,
      );
    } finally {
      _isSyncing = false;
    }
  }

  /// Background sync with retry logic
  /// Automatically retries up to 3 times with exponential backoff
  Future<SyncResult> syncWithRetry({int maxRetries = 3}) async {
    for (int attempt = 1; attempt <= maxRetries; attempt++) {
      print('Sync attempt $attempt of $maxRetries');

      final result = await sync();

      if (result.success) {
        return result;
      }

      // Don't retry if offline
      if (result.offlineMode) {
        return result;
      }

      // Exponential backoff: 2s, 4s, 8s
      if (attempt < maxRetries) {
        final waitSeconds = 2 * attempt;
        print('Retrying in $waitSeconds seconds...');
        await Future.delayed(Duration(seconds: waitSeconds));
      }
    }

    return SyncResult(
      success: false,
      message: 'Sync failed after $maxRetries attempts',
      errors: _syncErrors,
    );
  }

  /// Quick sync check - upload only if pending entries exist
  Future<bool> hasUnsyncedData() async {
    final unsynced = await localDb.getUnsyncedEntries();
    return unsynced.isNotEmpty;
  }

  /// Get sync status info
  SyncStatus getSyncStatus() {
    return SyncStatus(
      isSyncing: _isSyncing,
      lastSync: _lastSuccessfulSync,
      errors: _syncErrors,
    );
  }

  /// Schedule periodic background sync
  /// Returns timer that can be cancelled
  Timer schedulePeriodicSync({Duration interval = const Duration(minutes: 15)}) {
    return Timer.periodic(interval, (_) async {
      if (!_isSyncing && await hasUnsyncedData()) {
        print('Performing scheduled background sync...');
        await syncWithRetry();
      }
    });
  }
}

/// Sync result object
class SyncResult {
  final bool success;
  final String message;
  final int uploadedCount;
  final int downloadedCount;
  final int conflictCount;
  final bool offlineMode;
  final List<String> errors;

  SyncResult({
    required this.success,
    required this.message,
    this.uploadedCount = 0,
    this.downloadedCount = 0,
    this.conflictCount = 0,
    this.offlineMode = false,
    this.errors = const [],
  });

  @override
  String toString() {
    return 'SyncResult(success: $success, uploaded: $uploadedCount, '
        'downloaded: $downloadedCount, conflicts: $conflictCount)';
  }
}

/// Current sync status
class SyncStatus {
  final bool isSyncing;
  final DateTime? lastSync;
  final List<String> errors;

  SyncStatus({
    required this.isSyncing,
    this.lastSync,
    this.errors = const [],
  });

  String get statusText {
    if (isSyncing) return 'Syncing...';
    if (lastSync == null) return 'Never synced';

    final now = DateTime.now();
    final diff = now.difference(lastSync!);

    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}
