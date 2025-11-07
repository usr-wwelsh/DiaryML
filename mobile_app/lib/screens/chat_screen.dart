import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_client.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _messageController = TextEditingController();
  final _scrollController = ScrollController();

  List<Map<String, dynamic>> _messages = [];
  List<dynamic> _sessions = [];
  int? _currentSessionId;
  bool _isLoading = false;
  bool _isSending = false;
  Map<String, dynamic>? _currentModel;
  List<dynamic> _availableModels = [];

  @override
  void initState() {
    super.initState();
    _loadSessions();
    _loadModels();
  }

  Future<void> _loadSessions() async {
    try {
      final apiClient = context.read<ApiClient>();
      final sessions = await apiClient.getChatSessions();

      setState(() {
        _sessions = sessions;
        if (_sessions.isNotEmpty && _currentSessionId == null) {
          _currentSessionId = _sessions.first['id'];
          _loadMessages(_currentSessionId!);
        }
      });
    } catch (e) {
      print('Error loading sessions: $e');
    }
  }

  Future<void> _loadMessages(int sessionId) async {
    setState(() => _isLoading = true);

    try {
      final apiClient = context.read<ApiClient>();
      final messages = await apiClient.getChatMessages(sessionId);

      setState(() {
        _messages = List<Map<String, dynamic>>.from(messages);
        _isLoading = false;
      });

      _scrollToBottom();
    } catch (e) {
      print('Error loading messages: $e');
      setState(() => _isLoading = false);
    }
  }

  Future<void> _loadModels() async {
    try {
      final apiClient = context.read<ApiClient>();
      final result = await apiClient.listModels();

      setState(() {
        _availableModels = result['models'] ?? [];
        _currentModel = result['current_model'];
      });
    } catch (e) {
      print('Error loading models: $e');
    }
  }

  Future<void> _sendMessage() async {
    if (_messageController.text.trim().isEmpty) return;

    final message = _messageController.text.trim();
    _messageController.clear();

    // Add user message to UI immediately
    setState(() {
      _messages.add({
        'role': 'user',
        'content': message,
        'timestamp': DateTime.now().toIso8601String(),
      });
      _isSending = true;
    });

    _scrollToBottom();

    try {
      final apiClient = context.read<ApiClient>();
      final response = await apiClient.sendChatMessage(
        message: message,
        sessionId: _currentSessionId,
      );

      setState(() {
        _currentSessionId = response['session_id'];

        // Add assistant response
        _messages.add({
          'role': 'assistant',
          'content': response['response'],
          'timestamp': DateTime.now().toIso8601String(),
          'model_info': response['model_info'],
          'context_used': response['context_used'],
        });

        _isSending = false;
      });

      _scrollToBottom();

      // Reload sessions to show new session
      if (_sessions.isEmpty) {
        _loadSessions();
      }
    } catch (e) {
      setState(() {
        _messages.add({
          'role': 'error',
          'content': 'Error: ${e.toString()}',
          'timestamp': DateTime.now().toIso8601String(),
        });
        _isSending = false;
      });
    }
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _newSession() async {
    setState(() {
      _currentSessionId = null;
      _messages = [];
    });
  }

  Future<void> _deleteSession({int? sessionId}) async {
    final idToDelete = sessionId ?? _currentSessionId;
    if (idToDelete == null) return;

    try {
      final apiClient = context.read<ApiClient>();
      await apiClient.deleteChatSession(idToDelete);

      // If deleting current session, clear it
      if (idToDelete == _currentSessionId) {
        setState(() {
          _currentSessionId = null;
          _messages = [];
        });
      }

      _loadSessions();

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Chat deleted')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${e.toString()}')),
        );
      }
    }
  }

  Future<void> _showSessionHistory() async {
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => _buildSessionHistory(),
    );
  }

  Widget _buildSessionHistory() {
    return DraggableScrollableSheet(
      initialChildSize: 0.7,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (context, scrollController) {
        return Container(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Chat History',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(context),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              if (_sessions.isEmpty)
                Expanded(
                  child: Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.history,
                          size: 64,
                          color: Colors.grey.shade700,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'No chat history yet',
                          style: TextStyle(
                            color: Colors.grey.shade600,
                            fontSize: 16,
                          ),
                        ),
                      ],
                    ),
                  ),
                )
              else
                Expanded(
                  child: ListView.builder(
                    controller: scrollController,
                    itemCount: _sessions.length,
                    itemBuilder: (context, index) {
                      final session = _sessions[index];
                      final isCurrentSession = session['id'] == _currentSessionId;

                      return Card(
                        color: isCurrentSession
                            ? Theme.of(context).colorScheme.primary.withOpacity(0.2)
                            : null,
                        child: ListTile(
                          leading: Icon(
                            Icons.chat_bubble_outline,
                            color: isCurrentSession ? Theme.of(context).colorScheme.primary : null,
                          ),
                          title: Text(
                            'Chat #${session['id']}',
                            style: TextStyle(
                              fontWeight: isCurrentSession ? FontWeight.bold : FontWeight.normal,
                            ),
                          ),
                          subtitle: Text(
                            _formatSessionDate(session['created_at']),
                            style: const TextStyle(fontSize: 12),
                          ),
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              if (isCurrentSession)
                                const Padding(
                                  padding: EdgeInsets.only(right: 8),
                                  child: Icon(Icons.check_circle, color: Colors.green, size: 20),
                                ),
                              IconButton(
                                icon: const Icon(Icons.delete, size: 20),
                                onPressed: () {
                                  Navigator.pop(context); // Close modal first
                                  _showDeleteConfirmation(session['id']);
                                },
                                tooltip: 'Delete',
                              ),
                            ],
                          ),
                          onTap: () {
                            Navigator.pop(context); // Close modal
                            if (session['id'] != _currentSessionId) {
                              _switchToSession(session['id']);
                            }
                          },
                        ),
                      );
                    },
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  String _formatSessionDate(String? dateStr) {
    if (dateStr == null) return 'Unknown date';

    try {
      final date = DateTime.parse(dateStr);
      final now = DateTime.now();
      final diff = now.difference(date);

      if (diff.inMinutes < 1) {
        return 'Just now';
      } else if (diff.inHours < 1) {
        return '${diff.inMinutes}m ago';
      } else if (diff.inDays < 1) {
        return '${diff.inHours}h ago';
      } else if (diff.inDays < 7) {
        return '${diff.inDays}d ago';
      } else {
        return '${date.month}/${date.day}/${date.year}';
      }
    } catch (e) {
      return dateStr;
    }
  }

  Future<void> _showDeleteConfirmation(int sessionId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Chat'),
        content: const Text('Are you sure you want to delete this chat? This cannot be undone.'),
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

    if (confirmed == true) {
      _deleteSession(sessionId: sessionId);
    }
  }

  Future<void> _switchToSession(int sessionId) async {
    setState(() {
      _currentSessionId = sessionId;
      _messages = [];
    });

    await _loadMessages(sessionId);

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Switched chat session'),
          duration: Duration(seconds: 1),
        ),
      );
    }
  }

  Future<void> _showModelSelector() async {
    await showModalBottomSheet(
      context: context,
      builder: (context) => _buildModelSelector(),
    );
  }

  Widget _buildModelSelector() {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Select AI Model',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 16),

          // Current model
          if (_currentModel != null)
            Card(
              color: Theme.of(context).colorScheme.primary.withOpacity(0.2),
              child: ListTile(
                leading: const Icon(Icons.check_circle, color: Colors.green),
                title: Text(_currentModel!['name'] ?? 'Current Model'),
                subtitle: Text('${_currentModel!['size']}'),
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (_currentModel!['is_thinking'] == true)
                      const Icon(Icons.psychology, size: 16),
                    if (_currentModel!['has_vision'] == true)
                      const Icon(Icons.visibility, size: 16),
                  ],
                ),
              ),
            ),

          const SizedBox(height: 16),

          // Available models
          Text(
            'Available Models',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),

          if (_availableModels.isEmpty)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(16.0),
                child: Text('No models available on server'),
              ),
            )
          else
            SizedBox(
              height: 300,
              child: ListView.builder(
                itemCount: _availableModels.length,
                itemBuilder: (context, index) {
                  final model = _availableModels[index];
                  final isCurrent = _currentModel?['filename'] == model['filename'];

                  return ListTile(
                    leading: isCurrent
                        ? const Icon(Icons.check_circle, color: Colors.green)
                        : const Icon(Icons.circle_outlined),
                    title: Text(model['filename']),
                    subtitle: Text('${model['size_mb']} MB'),
                    onTap: isCurrent
                        ? null
                        : () => _switchModel(model['filename']),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _switchModel(String filename) async {
    Navigator.pop(context); // Close bottom sheet

    try {
      final apiClient = context.read<ApiClient>();

      // Show loading
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Switching model...'), duration: Duration(seconds: 2)),
        );
      }

      final result = await apiClient.switchModel(filename);

      setState(() {
        _currentModel = result['model_info'];
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Switched to ${result['model_info']['name']}')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${e.toString()}')),
        );
      }
    }
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('AI Chat'),
            if (_currentModel != null)
              Text(
                _currentModel!['name'] ?? '',
                style: const TextStyle(fontSize: 11, fontStyle: FontStyle.italic),
              ),
          ],
        ),
        actions: [
          // Session history
          IconButton(
            icon: const Icon(Icons.history),
            onPressed: _showSessionHistory,
            tooltip: 'Chat History',
          ),

          // Model selector
          IconButton(
            icon: const Icon(Icons.model_training),
            onPressed: _showModelSelector,
            tooltip: 'Select Model',
          ),

          // New chat
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: _newSession,
            tooltip: 'New Chat',
          ),

          // Delete current chat
          if (_currentSessionId != null)
            IconButton(
              icon: const Icon(Icons.delete),
              onPressed: _deleteSession,
              tooltip: 'Delete Current Chat',
            ),
        ],
      ),
      body: Column(
        children: [
          // Messages
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _messages.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.chat_bubble_outline,
                              size: 64,
                              color: Colors.grey.shade700,
                            ),
                            const SizedBox(height: 16),
                            Text(
                              'Start a conversation',
                              style: TextStyle(
                                color: Colors.grey.shade600,
                                fontSize: 16,
                              ),
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.all(16),
                        itemCount: _messages.length,
                        itemBuilder: (context, index) {
                          final message = _messages[index];
                          return _buildMessage(message);
                        },
                      ),
          ),

          // Input
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
                Expanded(
                  child: TextField(
                    controller: _messageController,
                    decoration: const InputDecoration(
                      hintText: 'Ask me anything...',
                      border: InputBorder.none,
                    ),
                    maxLines: null,
                    textCapitalization: TextCapitalization.sentences,
                    onSubmitted: (_) => _sendMessage(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: _isSending
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.send),
                  onPressed: _isSending ? null : _sendMessage,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMessage(Map<String, dynamic> message) {
    final isUser = message['role'] == 'user';
    final isError = message['role'] == 'error';

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.75,
        ),
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isUser
              ? Theme.of(context).colorScheme.primary
              : (isError ? Colors.red.withOpacity(0.2) : Theme.of(context).cardColor),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              message['content'],
              style: TextStyle(
                color: isUser ? Colors.white : null,
              ),
            ),

            // Context indicator
            if (message['context_used'] == true) ...[
              const SizedBox(height: 8),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.auto_awesome,
                    size: 12,
                    color: Colors.grey.shade600,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'Used diary context',
                    style: TextStyle(
                      fontSize: 10,
                      color: Colors.grey.shade600,
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
