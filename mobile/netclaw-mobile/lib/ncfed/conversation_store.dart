import 'dart:convert';
import 'dart:io';

/// One request/answer turn in the phone's conversation with its Border
/// (feature 067, FR-006/FR-007).
class ConversationTurn {
  final String taskId;
  final String requestText;
  String? answerText;
  String state; // 'pending' | 'working' | 'completed' | 'failed' | 'cancelled'
  final DateTime submittedAt;
  // Absolute path to a locally-saved copy of a photo this turn sent, if any
  // -- purely for showing what was sent in the UI; never re-read to build
  // the wire request (that already went out as base64 at send time).
  final String? photoPath;

  ConversationTurn({
    required this.taskId,
    required this.requestText,
    this.answerText,
    this.state = 'pending',
    required this.submittedAt,
    this.photoPath,
  });

  Map<String, dynamic> toJson() => {
        'task_id': taskId,
        'request_text': requestText,
        'answer_text': answerText,
        'state': state,
        'submitted_at': submittedAt.toIso8601String(),
        'photo_path': photoPath,
      };

  factory ConversationTurn.fromJson(Map<String, dynamic> json) => ConversationTurn(
        taskId: json['task_id'] as String,
        requestText: json['request_text'] as String,
        answerText: json['answer_text'] as String?,
        state: json['state'] as String,
        submittedAt: DateTime.parse(json['submitted_at'] as String),
        photoPath: json['photo_path'] as String?,
      );
}

/// Per-device persisted conversation history (FR-007: independent per
/// enrolled edge node, no cross-device sync — trivially true since this is
/// already per-installation; survives app restart/reboot, SC-004). Mirrors
/// 066's `MessageFeedStore` JSON-Lines pattern exactly, but turns are
/// mutable (a pending turn gets its answer filled in later), so this store
/// rewrites the whole file on each save rather than appending.
class ConversationStore {
  final Directory directory;
  final List<ConversationTurn> _turns = [];
  bool _loaded = false;

  ConversationStore(this.directory);

  List<ConversationTurn> get turns => List.unmodifiable(_turns);

  File _file() => File('${directory.path}/ncfed_conversation.json');

  Future<void> load() async {
    if (_loaded) return;
    _loaded = true;
    final file = _file();
    if (!await file.exists()) return;
    final raw = await file.readAsString();
    if (raw.trim().isEmpty) return;
    final list = jsonDecode(raw) as List<dynamic>;
    _turns
      ..clear()
      ..addAll(list.map((e) => ConversationTurn.fromJson(e as Map<String, dynamic>)));
  }

  Future<void> _save() async {
    await _file().writeAsString(jsonEncode(_turns.map((t) => t.toJson()).toList()));
  }

  Future<void> addPending(String taskId, String requestText, {List<int>? photoBytes}) async {
    await load();
    String? photoPath;
    if (photoBytes != null) {
      final file = File('${directory.path}/photo_$taskId.jpg');
      await file.writeAsBytes(photoBytes);
      photoPath = file.path;
    }
    _turns.add(ConversationTurn(
      taskId: taskId,
      requestText: requestText,
      submittedAt: DateTime.now().toUtc(),
      photoPath: photoPath,
    ));
    await _save();
  }

  Future<void> updateState(String taskId, String state, {String? answerText}) async {
    await load();
    for (final t in _turns) {
      if (t.taskId == taskId) {
        // Never let a stray late update flip an already-terminal turn (the
        // cancel-after-completion race from spec.md's edge cases).
        if (_isTerminal(t.state)) return;
        t.state = state;
        if (answerText != null) t.answerText = answerText;
        break;
      }
    }
    await _save();
  }

  static bool _isTerminal(String state) =>
      state == 'completed' || state == 'failed' || state == 'cancelled';

  /// Clears all history, including every saved photo file -- without this,
  /// there was no way to manage a conversation that only ever grows, and
  /// `photo_*.jpg` files would accumulate on disk forever with nothing ever
  /// deleting them.
  Future<void> clear() async {
    await load();
    for (final turn in _turns) {
      final path = turn.photoPath;
      if (path == null) continue;
      final file = File(path);
      if (await file.exists()) await file.delete();
    }
    _turns.clear();
    final file = _file();
    if (await file.exists()) await file.delete();
  }
}
