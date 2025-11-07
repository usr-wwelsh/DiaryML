import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/diary_entry.dart';

/// API Client for DiaryML Backend
/// Handles all HTTP requests with JWT authentication
///
/// Setup: Replace YOUR_SERVER_IP with your computer's local IP address.
/// Find it by running 'ipconfig' (Windows) or 'ifconfig' (Mac/Linux)
/// Example: http://192.168.1.100:8000/api
class ApiClient {
  static const String defaultBaseUrl = 'http://localhost:8000/api';

  final String baseUrl;
  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  String? _token;
  String? _serverUrl;

  ApiClient({this.baseUrl = defaultBaseUrl}) {
    _serverUrl = baseUrl;
  }

  /// Initialize and load token from storage
  Future<void> initialize() async {
    await _loadToken();
  }

  /// Load JWT token from secure storage
  Future<void> _loadToken() async {
    _token = await _storage.read(key: 'jwt_token');
    _serverUrl = await _storage.read(key: 'server_url') ?? baseUrl;
  }

  /// Save JWT token to secure storage
  Future<void> _saveToken(String token) async {
    _token = token;
    await _storage.write(key: 'jwt_token', value: token);
  }

  /// Save server URL
  Future<void> saveServerUrl(String url) async {
    _serverUrl = url;
    await _storage.write(key: 'server_url', value: url);
  }

  /// Get current server URL
  String get serverUrl => _serverUrl ?? baseUrl;

  /// Clear authentication
  Future<void> logout() async {
    _token = null;
    await _storage.delete(key: 'jwt_token');
  }

  /// Get authorization headers
  Map<String, String> _getHeaders() {
    final headers = {
      'Content-Type': 'application/json',
    };

    if (_token != null) {
      headers['Authorization'] = 'Bearer $_token';
    }

    return headers;
  }

  /// Login and get JWT token
  Future<Map<String, dynamic>> login(String password) async {
    final response = await http.post(
      Uri.parse('$_serverUrl/mobile/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'password': password}),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      await _saveToken(data['access_token']);
      return {'success': true, 'token': data['access_token']};
    } else {
      throw Exception('Login failed: ${response.body}');
    }
  }

  /// Sync entries with server
  Future<Map<String, dynamic>> sync({
    DateTime? lastSync,
    List<DiaryEntry>? pendingEntries,
  }) async {
    final body = {
      'last_sync': lastSync?.toIso8601String(),
      'pending_entries': pendingEntries?.map((e) => e.toJson()).toList() ?? [],
    };

    final response = await http.post(
      Uri.parse('$_serverUrl/mobile/sync'),
      headers: _getHeaders(),
      body: jsonEncode(body),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else if (response.statusCode == 401) {
      throw Exception('Authentication expired - please login again');
    } else {
      throw Exception('Sync failed: ${response.body}');
    }
  }

  /// Get recent entries
  Future<List<DiaryEntry>> getRecentEntries({int limit = 20}) async {
    final response = await http.get(
      Uri.parse('$_serverUrl/mobile/entries/recent?limit=$limit'),
      headers: _getHeaders(),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return (data['entries'] as List)
          .map((e) => DiaryEntry.fromJson(e))
          .toList();
    } else if (response.statusCode == 401) {
      throw Exception('Authentication expired - please login again');
    } else {
      throw Exception('Failed to load entries: ${response.body}');
    }
  }

  /// Get RAG entries from the vector database
  Future<Map<String, dynamic>> getRagEntries({int limit = 50}) async {
    final response = await http.get(
      Uri.parse('$_serverUrl/mobile/rag/entries?limit=$limit'),
      headers: _getHeaders(),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return {
        'entries': (data['entries'] as List)
            .map((e) => DiaryEntry.fromJson(e))
            .toList(),
        'count': data['count'],
        'total_in_rag': data['total_in_rag'],
      };
    } else if (response.statusCode == 401) {
      throw Exception('Authentication expired - please login again');
    } else {
      throw Exception('Failed to load RAG entries: ${response.body}');
    }
  }

  /// Get insights summary
  Future<Map<String, dynamic>> getInsightsSummary({int days = 7}) async {
    final response = await http.get(
      Uri.parse('$_serverUrl/mobile/insights/summary?days=$days'),
      headers: _getHeaders(),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else if (response.statusCode == 401) {
      throw Exception('Authentication expired - please login again');
    } else {
      throw Exception('Failed to load insights: ${response.body}');
    }
  }

  /// Get mood cycles
  Future<Map<String, dynamic>> getMoodCycles({int days = 90}) async {
    final response = await http.get(
      Uri.parse('$_serverUrl/insights/mood-cycles?days=$days'),
      headers: _getHeaders(),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load mood cycles');
    }
  }

  /// Get project momentum
  Future<Map<String, dynamic>> getProjectMomentum({int days = 90}) async {
    final response = await http.get(
      Uri.parse('$_serverUrl/insights/project-momentum?days=$days'),
      headers: _getHeaders(),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load project momentum');
    }
  }

  /// Send chat message
  Future<Map<String, dynamic>> sendChatMessage({
    required String message,
    int? sessionId,
  }) async {
    final body = {
      'message': message,
      if (sessionId != null) 'session_id': sessionId.toString(),
    };

    // Use form-data headers instead of JSON for this endpoint
    final headers = {
      if (_token != null) 'Authorization': 'Bearer $_token',
    };

    final response = await http.post(
      Uri.parse('$_serverUrl/mobile/chat'),
      headers: headers,
      body: body,
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else if (response.statusCode == 401) {
      throw Exception('Authentication expired - please login again');
    } else {
      throw Exception('Chat failed: ${response.body}');
    }
  }

  /// Get chat sessions
  Future<List<dynamic>> getChatSessions() async {
    final response = await http.get(
      Uri.parse('$_serverUrl/mobile/chat/sessions'),
      headers: _getHeaders(),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data['sessions'] ?? [];
    } else {
      throw Exception('Failed to load chat sessions');
    }
  }

  /// Get messages from a chat session
  Future<List<dynamic>> getChatMessages(int sessionId) async {
    final response = await http.get(
      Uri.parse('$_serverUrl/mobile/chat/sessions/$sessionId/messages'),
      headers: _getHeaders(),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data['messages'] ?? [];
    } else {
      throw Exception('Failed to load messages');
    }
  }

  /// Delete chat session
  Future<void> deleteChatSession(int sessionId) async {
    final response = await http.delete(
      Uri.parse('$_serverUrl/mobile/chat/sessions/$sessionId'),
      headers: _getHeaders(),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to delete session');
    }
  }

  /// List available models
  Future<Map<String, dynamic>> listModels() async {
    final response = await http.get(
      Uri.parse('$_serverUrl/mobile/models/list'),
      headers: _getHeaders(),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load models');
    }
  }

  /// Switch model
  Future<Map<String, dynamic>> switchModel(String filename) async {
    final body = {'model_filename': filename};

    // Use form-data headers instead of JSON for this endpoint
    final headers = {
      if (_token != null) 'Authorization': 'Bearer $_token',
    };

    final response = await http.post(
      Uri.parse('$_serverUrl/mobile/models/switch'),
      headers: headers,
      body: body,
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to switch model');
    }
  }

  /// Check if authenticated
  bool get isAuthenticated => _token != null;
}
