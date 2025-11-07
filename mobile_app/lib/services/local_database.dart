import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';
import '../models/diary_entry.dart';

/// Local SQLite Database for Offline Storage
/// Stores entries locally and tracks sync status
class LocalDatabase {
  static Database? _database;
  static final LocalDatabase instance = LocalDatabase._init();

  LocalDatabase._init();

  Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _initDB('diaryml.db');
    return _database!;
  }

  Future<Database> _initDB(String filePath) async {
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, filePath);

    return await openDatabase(
      path,
      version: 1,
      onCreate: _createDB,
    );
  }

  Future<void> _createDB(Database db, int version) async {
    await db.execute('''
      CREATE TABLE entries (
        id INTEGER PRIMARY KEY,
        mobile_id TEXT UNIQUE,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        moods TEXT,
        image_path TEXT,
        synced INTEGER NOT NULL DEFAULT 0,
        last_modified TEXT
      )
    ''');

    await db.execute('''
      CREATE TABLE sync_metadata (
        key TEXT PRIMARY KEY,
        value TEXT
      )
    ''');

    await db.execute('''
      CREATE INDEX idx_timestamp ON entries(timestamp DESC)
    ''');

    await db.execute('''
      CREATE INDEX idx_synced ON entries(synced)
    ''');
  }

  /// Insert or update entry
  Future<int> insertEntry(DiaryEntry entry) async {
    final db = await database;

    // If entry has no ID, generate mobile_id
    final entryToInsert = entry.copyWith(
      mobileId: entry.mobileId ?? DateTime.now().millisecondsSinceEpoch.toString(),
      lastModified: DateTime.now(),
    );

    return await db.insert(
      'entries',
      entryToInsert.toMap(),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Get all entries (sorted by timestamp)
  Future<List<DiaryEntry>> getAllEntries() async {
    final db = await database;
    final result = await db.query(
      'entries',
      orderBy: 'timestamp DESC',
    );

    return result.map((map) => DiaryEntry.fromMap(map)).toList();
  }

  /// Get unsynced entries
  Future<List<DiaryEntry>> getUnsyncedEntries() async {
    final db = await database;
    final result = await db.query(
      'entries',
      where: 'synced = ?',
      whereArgs: [0],
    );

    return result.map((map) => DiaryEntry.fromMap(map)).toList();
  }

  /// Mark entry as synced
  Future<void> markAsSynced(String mobileId, int serverId) async {
    final db = await database;
    await db.update(
      'entries',
      {'synced': 1, 'id': serverId},
      where: 'mobile_id = ?',
      whereArgs: [mobileId],
    );
  }

  /// Get last sync timestamp
  Future<DateTime?> getLastSyncTime() async {
    final db = await database;
    final result = await db.query(
      'sync_metadata',
      where: 'key = ?',
      whereArgs: ['last_sync'],
    );

    if (result.isEmpty) return null;
    return DateTime.parse(result.first['value'] as String);
  }

  /// Update last sync timestamp
  Future<void> updateLastSyncTime(DateTime time) async {
    final db = await database;
    await db.insert(
      'sync_metadata',
      {'key': 'last_sync', 'value': time.toIso8601String()},
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Delete entry by server ID
  Future<void> deleteEntry(int id) async {
    final db = await database;
    await db.delete(
      'entries',
      where: 'id = ?',
      whereArgs: [id],
    );
  }

  /// Delete entry by mobile ID
  Future<void> deleteEntryByMobileId(String mobileId) async {
    final db = await database;
    await db.delete(
      'entries',
      where: 'mobile_id = ?',
      whereArgs: [mobileId],
    );
  }

  /// Get entry count
  Future<int> getEntryCount() async {
    final db = await database;
    final result = await db.rawQuery('SELECT COUNT(*) as count FROM entries');
    return Sqflite.firstIntValue(result) ?? 0;
  }

  /// Get entries for date range
  Future<List<DiaryEntry>> getEntriesInRange(DateTime start, DateTime end) async {
    final db = await database;
    final result = await db.query(
      'entries',
      where: 'timestamp BETWEEN ? AND ?',
      whereArgs: [start.toIso8601String(), end.toIso8601String()],
      orderBy: 'timestamp DESC',
    );

    return result.map((map) => DiaryEntry.fromMap(map)).toList();
  }

  /// Search entries by content
  Future<List<DiaryEntry>> searchEntries(String query) async {
    final db = await database;
    final result = await db.query(
      'entries',
      where: 'content LIKE ?',
      whereArgs: ['%$query%'],
      orderBy: 'timestamp DESC',
    );

    return result.map((map) => DiaryEntry.fromMap(map)).toList();
  }

  /// Clear all data (for logout)
  Future<void> clearAllData() async {
    final db = await database;
    await db.delete('entries');
    await db.delete('sync_metadata');
  }

  /// Close database
  Future<void> close() async {
    final db = await _database;
    if (db != null) {
      await db.close();
      _database = null;
    }
  }
}
