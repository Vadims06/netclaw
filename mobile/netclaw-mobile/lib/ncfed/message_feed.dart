import 'dart:convert';
import 'dart:io';

import 'edge_client.dart';

enum MessageContentType { text, voice, image }

/// One message the Border explicitly pushed (US2/FR-008,
/// contracts/edge-enrollment-and-push.md §3). `content` is plain text for
/// `text`, base64-encoded media for `voice`/`image`.
class EdgeMessage {
  final MessageContentType contentType;
  final String content;
  final String designatedBy;
  final DateTime pushedAt;

  const EdgeMessage({
    required this.contentType,
    required this.content,
    required this.designatedBy,
    required this.pushedAt,
  });

  factory EdgeMessage.fromWire(Map<String, dynamic> params) => EdgeMessage(
        contentType: MessageContentType.values.byName(params['content_type'] as String),
        content: params['content'] as String,
        designatedBy: params['designated_by'] as String? ?? 'agent',
        pushedAt: DateTime.tryParse(params['pushed_at'] as String? ?? '') ?? DateTime.now().toUtc(),
      );

  Map<String, dynamic> toJson() => {
        'content_type': contentType.name,
        'content': content,
        'designated_by': designatedBy,
        'pushed_at': pushedAt.toIso8601String(),
      };

  factory EdgeMessage.fromJson(Map<String, dynamic> json) => EdgeMessage(
        contentType: MessageContentType.values.byName(json['content_type'] as String),
        content: json['content'] as String,
        designatedBy: json['designated_by'] as String,
        pushedAt: DateTime.parse(json['pushed_at'] as String),
      );
}

/// Local, on-device store for messages the Border has explicitly pushed —
/// append-only, persisted as JSON Lines so a restart never loses history
/// (T029). Production callers construct this with
/// `await getApplicationDocumentsDirectory()`; tests pass a temp directory
/// directly, so this never touches `path_provider`'s platform channel
/// itself (which has no implementation under `flutter test`).
class MessageFeedStore {
  final Directory directory;
  final List<EdgeMessage> _messages = [];
  bool _loaded = false;

  MessageFeedStore(this.directory);

  List<EdgeMessage> get messages => List.unmodifiable(_messages);

  File _file() => File('${directory.path}/ncfed_message_feed.jsonl');

  Future<void> load() async {
    if (_loaded) return;
    _loaded = true;
    final file = _file();
    if (!await file.exists()) return;
    final lines = await file.readAsLines();
    _messages.clear();
    for (final line in lines) {
      if (line.trim().isEmpty) continue;
      _messages.add(EdgeMessage.fromJson(jsonDecode(line) as Map<String, dynamic>));
    }
  }

  Future<void> append(EdgeMessage message) async {
    await load();
    _messages.add(message);
    await _file().writeAsString(
      '${jsonEncode(message.toJson())}\n',
      mode: FileMode.append,
      flush: true,
    );
  }
}

/// Registers the SINGLE `n2n/edge/message` handler for the whole app —
/// `EdgeClient.on()` only ever keeps the LAST handler registered per
/// method, so this must be the only place that calls `client.on('n2n/edge/
/// message', ...)`. Every Border-initiated push with `content_type`
/// text/voice/image is appended to `store` (066, contracts/
/// edge-enrollment-and-push.md §3); a push with `content_type='approval'`
/// (068, research D5) is instead handed to `onApproval` — never both.
void wireMessageFeed(
  EdgeMethodSource client,
  MessageFeedStore store, {
  void Function(Map<String, dynamic> params)? onApproval,
}) {
  client.on('n2n/edge/message', (params) async {
    if (params['content_type'] == 'approval') {
      onApproval?.call(params);
      return {'received': true};
    }
    await store.append(EdgeMessage.fromWire(params));
    return {'received': true};
  });
}
