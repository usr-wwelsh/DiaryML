/// Diary Entry Model
/// Represents a single journal entry with mood data
class DiaryEntry {
  final int? id; // null for unsync'd entries
  final String? mobileId; // Temporary ID before sync
  final String content;
  final DateTime timestamp;
  final Map<String, double> moods;
  final String? imagePath;
  final bool synced;
  final DateTime? lastModified;

  DiaryEntry({
    this.id,
    this.mobileId,
    required this.content,
    required this.timestamp,
    this.moods = const {},
    this.imagePath,
    this.synced = false,
    this.lastModified,
  });

  /// Create from JSON (API response)
  factory DiaryEntry.fromJson(Map<String, dynamic> json) {
    return DiaryEntry(
      id: json['id'],
      mobileId: json['mobile_id'],
      content: json['content'],
      timestamp: DateTime.parse(json['timestamp']),
      moods: json['moods'] != null
          ? Map<String, double>.from(json['moods'])
          : {},
      imagePath: json['image_path'],
      synced: json['synced'] ?? true,
      lastModified: json['last_modified'] != null
          ? DateTime.parse(json['last_modified'])
          : null,
    );
  }

  /// Convert to JSON (for API)
  Map<String, dynamic> toJson() {
    return {
      if (id != null) 'id': id,
      if (mobileId != null) 'mobile_id': mobileId,
      'content': content,
      'timestamp': timestamp.toIso8601String(),
      'moods': moods,
      if (imagePath != null) 'image_path': imagePath,
      'synced': synced,
      if (lastModified != null) 'last_modified': lastModified!.toIso8601String(),
    };
  }

  /// Create from SQLite
  factory DiaryEntry.fromMap(Map<String, dynamic> map) {
    return DiaryEntry(
      id: map['id'],
      mobileId: map['mobile_id'],
      content: map['content'],
      timestamp: DateTime.parse(map['timestamp']),
      moods: map['moods'] != null && map['moods'].isNotEmpty
          ? Map<String, double>.from({}) // Parse JSON string if needed
          : {},
      imagePath: map['image_path'],
      synced: map['synced'] == 1,
      lastModified: map['last_modified'] != null
          ? DateTime.parse(map['last_modified'])
          : null,
    );
  }

  /// Convert to SQLite map
  Map<String, dynamic> toMap() {
    return {
      if (id != null) 'id': id,
      if (mobileId != null) 'mobile_id': mobileId,
      'content': content,
      'timestamp': timestamp.toIso8601String(),
      'moods': moods.toString(), // Store as string
      if (imagePath != null) 'image_path': imagePath,
      'synced': synced ? 1 : 0,
      if (lastModified != null) 'last_modified': lastModified!.toIso8601String(),
    };
  }

  /// Copy with modifications
  DiaryEntry copyWith({
    int? id,
    String? mobileId,
    String? content,
    DateTime? timestamp,
    Map<String, double>? moods,
    String? imagePath,
    bool? synced,
    DateTime? lastModified,
  }) {
    return DiaryEntry(
      id: id ?? this.id,
      mobileId: mobileId ?? this.mobileId,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      moods: moods ?? this.moods,
      imagePath: imagePath ?? this.imagePath,
      synced: synced ?? this.synced,
      lastModified: lastModified ?? this.lastModified,
    );
  }

  /// Get dominant mood
  String get dominantMood {
    if (moods.isEmpty) return 'neutral';
    return moods.entries
        .reduce((a, b) => a.value > b.value ? a : b)
        .key;
  }

  /// Get mood emoji
  String get moodEmoji {
    final mood = dominantMood;
    const moodEmojis = {
      'joy': '😊',
      'love': '❤️',
      'sadness': '😢',
      'anger': '😠',
      'fear': '😰',
      'surprise': '😲',
      'neutral': '😐',
    };
    return moodEmojis[mood] ?? '😐';
  }
}
