import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../ncfed/capture_client.dart';
import '../ncfed/conversation_store.dart';
import '../ncfed/edge_ask_client.dart';
import '../ncfed/voice_transcription.dart';
import 'capture_screen.dart';

/// Chat screen (feature 067, FR-006): request/answer history, in-progress
/// state while a task is pending, and a cancel action per in-progress turn
/// (T007/T012).
class ChatScreen extends StatefulWidget {
  final EdgeAskClient askClient;
  final ConversationStore store;
  final VoiceTranscription voiceTranscription;
  // Bumped by the owner every time a dropped connection successfully
  // redials -- reconciling only once at cold start meant a turn that
  // finished while briefly disconnected stayed stuck on "Working…" until
  // the next full app restart, even though the app was live the whole time.
  final ValueListenable<int>? reconnectTick;

  ChatScreen({
    super.key,
    required this.askClient,
    required this.store,
    VoiceTranscription? voiceTranscription,
    this.reconnectTick,
  }) : voiceTranscription = voiceTranscription ?? VoiceTranscription();

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _controller = TextEditingController();
  bool _loading = true;
  bool _listening = false;
  String? _sendError;

  @override
  void initState() {
    super.initState();
    widget.store.load().then((_) async {
      if (mounted) setState(() => _loading = false);
      await _reconcileStaleTurns();
    });
    widget.askClient.updates.listen((update) async {
      await _applyUpdate(update);
    });
    widget.reconnectTick?.addListener(_reconcileStaleTurns);
  }

  @override
  void dispose() {
    widget.reconnectTick?.removeListener(_reconcileStaleTurns);
    _controller.dispose();
    super.dispose();
  }

  Future<void> _applyUpdate(TaskUpdate update) async {
    final stateName = switch (update.state) {
      TaskState.completed => 'completed',
      TaskState.failed => 'failed',
      TaskState.cancelled => 'cancelled',
      TaskState.working => 'working',
      _ => 'pending',
    };
    await widget.store.updateState(update.taskId, stateName, answerText: update.outputText);
    if (mounted) setState(() {});
  }

  /// A task that finishes while this device is disconnected (or whose
  /// `ask_result` push simply never arrives — e.g. a connection already
  /// going stale by the time the answer was ready) has no other way to
  /// reach the phone; the Border never re-pushes a result spontaneously.
  /// Called once after the store loads: for every turn still `pending`/
  /// `working` locally, ask the Border directly whether it actually
  /// finished already.
  Future<void> _reconcileStaleTurns() async {
    final staleTaskIds = widget.store.turns
        .where((t) => t.state == 'pending' || t.state == 'working')
        .map((t) => t.taskId)
        .toList();
    for (final taskId in staleTaskIds) {
      try {
        final update = await widget.askClient.result(taskId);
        if (update.state != TaskState.pending && update.state != TaskState.unknown) {
          await _applyUpdate(update);
        }
      } catch (_) {
        // Still disconnected, or the Border is unreachable right now --
        // the next reconnect will retry; never blocks the rest of the UI.
      }
    }
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    _controller.clear();
    await _sendRequest(text);
  }

  /// Shared by [_send] and a failed turn's Retry button -- resends the
  /// original `requestText`/`attachment` as a brand-new turn (its own fresh
  /// `taskId`; a `ConversationTurn`'s id is immutable, and re-running the
  /// exact same request is exactly what "retry" means here anyway).
  Future<void> _sendRequest(String text, {Map<String, dynamic>? attachment}) async {
    setState(() => _sendError = null);
    try {
      final taskId = await widget.askClient.ask(text, attachment: attachment);
      List<int>? photoBytes;
      if (attachment != null && attachment['content_type'] == 'image') {
        photoBytes = base64Decode(attachment['content'] as String);
      }
      await widget.store.addPending(taskId, text, photoBytes: photoBytes);
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) setState(() => _sendError = 'Could not send: $e');
    }
  }

  /// Re-submits a failed turn exactly as it was originally sent, including
  /// its photo if it had one (re-read from the locally-saved copy --
  /// nothing else in the app keeps a completed turn's original bytes in
  /// memory). Previously there was no way to recover from a failed send
  /// short of retyping the whole message.
  Future<void> _retry(ConversationTurn turn) async {
    Map<String, dynamic>? attachment;
    if (turn.photoPath != null) {
      final file = File(turn.photoPath!);
      if (await file.exists()) {
        attachment = {
          'content_type': 'image',
          'content': base64Encode(await file.readAsBytes()),
        };
      }
    }
    var text = turn.requestText;
    if (turn.photoPath != null) {
      // requestText was displayed with a "[Photo]"/" [Photo]" suffix added
      // purely for display (see _capturePhoto) -- strip it back off so a
      // retry doesn't literally ask "... [Photo]" as if that were part of
      // the question.
      text = text.replaceAll(RegExp(r'\s?\[Photo\]$'), '');
    }
    await _sendRequest(text, attachment: attachment);
  }

  Future<void> _recordVoice() async {
    setState(() => _sendError = null);
    try {
      final result = await widget.voiceTranscription.recordAndAsk(
        widget.askClient,
        onListeningChange: (listening) {
          if (mounted) setState(() => _listening = listening);
        },
      );
      if (result == null) return; // nothing heard — no request sent
      final (taskId, text) = result;
      await widget.store.addPending(taskId, text);
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) setState(() => _sendError = 'Could not send: $e');
    } finally {
      if (mounted) setState(() => _listening = false);
    }
  }

  Future<void> _capturePhoto() async {
    setState(() => _sendError = null);
    // Whatever's already typed becomes the question that goes with the
    // photo (feature 068, US2) -- same pattern _send() uses for a typed-only
    // request. Previously this was never read at all, so a photo could only
    // ever be sent bare with no way to ask something about it.
    final text = _controller.text.trim();
    List<int>? capturedBytes;
    try {
      // feature 068, US2: a bare capture with no accompanying text is a
      // valid request (FR-005) -- captureAndAsk() sends nothing at all if
      // the operator declines/cancels (CaptureScreen returns null).
      final client = CaptureClient(
        askClient: widget.askClient,
        capture: (type) => CaptureScreen.capture(context, type),
      );
      final taskId = await client.captureAndAsk(
        'camera.capture',
        text: text,
        onCaptured: (result) => capturedBytes = result.bytes,
      );
      if (taskId == null) return;
      _controller.clear();
      await widget.store.addPending(
        taskId,
        text.isEmpty ? '[Photo]' : '$text [Photo]',
        photoBytes: capturedBytes,
      );
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) setState(() => _sendError = 'Could not send: $e');
    }
  }

  Future<void> _cancel(String taskId) async {
    try {
      await widget.askClient.cancel(taskId);
      // The Border pushes n2n/edge/ask_result with state='cancelled' once
      // the worker actually stops — ConversationStore.updateState's
      // terminal-state guard means a completed answer that races the
      // cancel is preserved.
    } catch (e) {
      if (mounted) setState(() => _sendError = 'Could not cancel: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    final turns = List.of(widget.store.turns)
      ..sort((a, b) => a.submittedAt.compareTo(b.submittedAt));
    return Column(
      children: [
        Expanded(
          child: turns.isEmpty
              ? const Center(child: Text('Ask your Border something.'))
              : ListView.builder(
                  itemCount: turns.length,
                  itemBuilder: (context, index) => _TurnTile(
                    turn: turns[index],
                    onCancel: () => _cancel(turns[index].taskId),
                    onRetry: () => _retry(turns[index]),
                  ),
                ),
        ),
        if (_sendError != null)
          Container(
            width: double.infinity,
            color: Colors.red.shade50,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Text(_sendError!, style: TextStyle(color: Colors.red.shade900)),
          ),
        if (_listening)
          Container(
            width: double.infinity,
            color: Colors.blue.shade50,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(
              children: [
                const SizedBox(
                    width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2)),
                const SizedBox(width: 8),
                Text('Listening…', style: TextStyle(color: Colors.blue.shade900)),
              ],
            ),
          ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(8),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    decoration: const InputDecoration(hintText: 'Ask something…'),
                    onSubmitted: (_) => _send(),
                  ),
                ),
                IconButton(icon: const Icon(Icons.camera_alt), onPressed: _capturePhoto),
                IconButton(
                  icon: Icon(_listening ? Icons.mic : Icons.mic_none),
                  color: _listening ? Colors.blue : null,
                  onPressed: _listening ? null : _recordVoice,
                ),
                IconButton(icon: const Icon(Icons.send), onPressed: _send),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _TurnTile extends StatelessWidget {
  final ConversationTurn turn;
  final VoidCallback onCancel;
  final VoidCallback onRetry;

  const _TurnTile({required this.turn, required this.onCancel, required this.onRetry});

  bool get _inProgress => turn.state == 'pending' || turn.state == 'working';

  static String _formatTime(DateTime utc) {
    final t = utc.toLocal();
    final hour = t.hour.toString().padLeft(2, '0');
    final minute = t.minute.toString().padLeft(2, '0');
    return '$hour:$minute';
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(turn.requestText, style: const TextStyle(fontWeight: FontWeight.bold)),
            Text(_formatTime(turn.submittedAt),
                style: Theme.of(context).textTheme.labelSmall?.copyWith(color: Colors.grey)),
            if (turn.photoPath != null) ...[
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Image.file(
                  File(turn.photoPath!),
                  height: 160,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) =>
                      const Text('[Photo unavailable]', style: TextStyle(color: Colors.grey)),
                ),
              ),
            ],
            const SizedBox(height: 8),
            if (_inProgress)
              Row(
                children: [
                  const SizedBox(
                      width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                  const SizedBox(width: 8),
                  const Text('Working…'),
                  const Spacer(),
                  TextButton(onPressed: onCancel, child: const Text('Cancel')),
                ],
              )
            else if (turn.state == 'cancelled')
              const Text('Cancelled', style: TextStyle(color: Colors.grey))
            else if (turn.state == 'failed')
              Row(
                children: [
                  Expanded(
                    child: Text(turn.answerText ?? 'Failed',
                        style: const TextStyle(color: Colors.red)),
                  ),
                  TextButton(onPressed: onRetry, child: const Text('Retry')),
                ],
              )
            else
              Text(turn.answerText ?? ''),
          ],
        ),
      ),
    );
  }
}
