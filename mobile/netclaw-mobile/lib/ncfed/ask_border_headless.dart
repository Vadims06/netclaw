import 'dart:async';

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:path_provider/path_provider.dart';

import 'conversation_store.dart';
import 'edge_ask_client.dart';
import 'edge_client.dart';
import 'headless_connect.dart';
import 'local_notifications.dart';

const _channel = MethodChannel('ca.automateyournetwork.netclaw/ask_border');

/// How long [runAskBorder] keeps listening for a fast-arriving `ask_result`
/// after the acknowledgment has already been reported, hoping to post the
/// real-answer notification before this headless process is reclaimed
/// (spec 111 FR-004, research.md R8). A slower answer is left `pending` —
/// `lib/ncfed/turn_reconciler.dart`'s `reconcileStaleTurns` finishes it on a
/// later reconnect, exactly as it already does for any other stranded ask.
const askBorderPostAckWindow = Duration(seconds: 20);

/// Entry point for the headless `FlutterEngine` `AskBorderIntent.swift`
/// spins up (spec 111, research.md R1). Mirrors `background_refresh.dart`'s
/// shape: no widget tree, reconnects via the same persisted enrollment a
/// cold foreground launch would, and reports back over [_channel] — except
/// here the channel carries a real request (the question) inbound, not just
/// a completion signal outbound.
@pragma('vm:entry-point')
Future<void> askBorderMain() async {
  WidgetsFlutterBinding.ensureInitialized();
  _channel.setMethodCallHandler((call) async {
    if (call.method != 'submit') return null;
    final question = (call.arguments as Map)['question'] as String;
    final dir = await getApplicationDocumentsDirectory();

    final EdgeClient client;
    try {
      client = await connectHeadless(directory: dir);
    } on NotEnrolledError {
      throw PlatformException(code: 'not_enrolled');
    } on ConnectTimeoutError {
      throw PlatformException(code: 'timeout');
    }

    final store = ConversationStore(dir);
    await store.load();
    try {
      return await runAskBorder(
        question,
        rpc: client,
        store: store,
        close: client.close,
        notify: ({required identifier, required preview, required badgeCount}) async {
          final notifications = LocalNotifications();
          await notifications.initialize(onResponse: (_) {});
          await notifications.postChatNotification(
              identifier: identifier, preview: preview, badgeCount: badgeCount);
        },
        onFinished: () => _channel.invokeMethod<void>('finished'),
      );
    } catch (e) {
      await client.close();
      throw PlatformException(code: 'failed', message: '$e');
    }
  });
}

/// The testable core of [askBorderMain]: given an already-connected [rpc],
/// submits [question], persists it into [store] as a pending turn with
/// `origin: 'siri'` (FR-005/FR-011), and returns the acknowledgment string
/// as soon as a `task_id` comes back (FR-003) — WITHOUT waiting for the real
/// answer. The bounded post-acknowledgment wait for `ask_result` (FR-004,
/// research.md R8) runs afterward, unawaited by the returned future, and
/// calls [onFinished] exactly once when it concludes (landed or timed out)
/// so the caller knows it is safe to tear down the headless engine.
Future<String> runAskBorder(
  String question, {
  required EdgeRpcSource rpc,
  required ConversationStore store,
  required Future<void> Function() close,
  required Future<void> Function({
    required String identifier,
    required String preview,
    required int badgeCount,
  }) notify,
  required void Function() onFinished,
  Duration postAckWindow = askBorderPostAckWindow,
}) async {
  final askClient = EdgeAskClient(rpc);
  final String taskId;
  try {
    taskId = await askClient.ask(question);
  } catch (e) {
    onFinished();
    rethrow;
  }
  await store.addPending(taskId, question, origin: 'siri');

  unawaited(_awaitResultAndNotify(
    askClient: askClient,
    store: store,
    taskId: taskId,
    close: close,
    notify: notify,
    window: postAckWindow,
    onFinished: onFinished,
  ));

  return "Sent to NetClaw. I'll let you know when it answers.";
}

Future<void> _awaitResultAndNotify({
  required EdgeAskClient askClient,
  required ConversationStore store,
  required String taskId,
  required Future<void> Function() close,
  required Future<void> Function({
    required String identifier,
    required String preview,
    required int badgeCount,
  }) notify,
  required Duration window,
  required void Function() onFinished,
}) async {
  try {
    final update = await askClient.updates
        .firstWhere((u) => u.taskId == taskId)
        .timeout(window);
    if (update.state != TaskState.completed &&
        update.state != TaskState.failed &&
        update.state != TaskState.cancelled) {
      return; // still working when the stream closed early — leave it pending
    }
    final answer = update.outputText ?? '';
    await store.updateState(
      taskId,
      switch (update.state) {
        TaskState.completed => 'completed',
        TaskState.failed => 'failed',
        TaskState.cancelled => 'cancelled',
        _ => 'working',
      },
      answerText: answer,
    );
    await notify(
      identifier: taskId,
      preview: answer.isEmpty ? 'NetClaw answered your question.' : answer,
      badgeCount: store.unreadCount,
    );
  } on TimeoutException {
    // Left 'pending' -- reconcileStaleTurns finishes this later (research.md R8).
  } finally {
    await close();
    onFinished();
  }
}
