import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:netclaw_mobile/ncfed/ask_border_headless.dart';
import 'package:netclaw_mobile/ncfed/conversation_store.dart';
import 'package:netclaw_mobile/ncfed/edge_client.dart';

class _FakeRpc implements EdgeRpcSource {
  final String taskId;
  EdgeMethodHandler? askResultHandler;
  final List<String> methodsCalled = [];

  _FakeRpc(this.taskId);

  @override
  void on(String method, EdgeMethodHandler handler) {
    if (method == 'n2n/edge/ask_result') askResultHandler = handler;
  }

  @override
  Future<Map<String, dynamic>> call(String method, Map<String, dynamic> params,
      {Duration timeout = const Duration(seconds: 30)}) async {
    methodsCalled.add(method);
    if (method == 'n2n/edge/ask') return {'task_id': taskId};
    return {};
  }

  Future<void> deliverAskResult(Map<String, dynamic> params) async {
    await askResultHandler!(params);
  }
}

class _RecordedNotification {
  final String identifier;
  final String preview;
  final int badgeCount;
  _RecordedNotification(this.identifier, this.preview, this.badgeCount);
}

void main() {
  late Directory dir;
  late ConversationStore store;
  late _FakeRpc rpc;
  final notifications = <_RecordedNotification>[];
  var finishedCalls = 0;
  var closeCalls = 0;

  setUp(() async {
    dir = await Directory.systemTemp.createTemp('ask_border_headless_test');
    store = ConversationStore(dir);
    rpc = _FakeRpc('task-1');
    notifications.clear();
    finishedCalls = 0;
    closeCalls = 0;
  });

  tearDown(() async {
    if (await dir.exists()) await dir.delete(recursive: true);
  });

  Future<String> run(String question, {Duration postAckWindow = const Duration(seconds: 20)}) {
    return runAskBorder(
      question,
      rpc: rpc,
      store: store,
      close: () async => closeCalls++,
      notify: ({required identifier, required preview, required badgeCount}) async {
        notifications.add(_RecordedNotification(identifier, preview, badgeCount));
      },
      onFinished: () => finishedCalls++,
      postAckWindow: postAckWindow,
    );
  }

  test('reports the acknowledgment before any ask_result has arrived (FR-003)', () async {
    final ack = await run('is BGP up on the core switch');

    expect(ack, contains('Sent to NetClaw'));
    expect(rpc.methodsCalled, ['n2n/edge/ask']);
    expect(notifications, isEmpty, reason: 'must not wait for the real answer');
  });

  test('persists the turn as pending with origin siri before returning the ack (FR-005/FR-011)',
      () async {
    await run('is BGP up on the core switch');

    final turn = store.turns.single;
    expect(turn.taskId, 'task-1');
    expect(turn.requestText, 'is BGP up on the core switch');
    expect(turn.state, 'pending');
    expect(turn.origin, 'siri');
  });

  test('once ask_result arrives within the window, finalizes the turn and notifies (FR-004)',
      () async {
    await run('is BGP up on the core switch');
    await rpc.deliverAskResult(
        {'task_id': 'task-1', 'state': 'completed', 'output_text': 'Yes, BGP is up.'});
    await Future<void>.delayed(const Duration(milliseconds: 100));

    expect(store.turns.single.state, 'completed');
    expect(store.turns.single.answerText, 'Yes, BGP is up.');
    expect(notifications, hasLength(1));
    expect(notifications.single.identifier, 'task-1');
    expect(notifications.single.preview, 'Yes, BGP is up.');
    expect(finishedCalls, 1);
    expect(closeCalls, 1);
  });

  test('a failed task is also finalized and notified, not left pending', () async {
    await run('is BGP up on the core switch');
    await rpc.deliverAskResult({'task_id': 'task-1', 'state': 'failed', 'error': 'timed out'});
    await Future<void>.delayed(const Duration(milliseconds: 100));

    expect(store.turns.single.state, 'failed');
    expect(notifications, hasLength(1));
  });

  test('if the window elapses first, the turn stays pending for later reconciliation (R8)',
      () async {
    await run('is BGP up on the core switch', postAckWindow: const Duration(milliseconds: 5));
    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(store.turns.single.state, 'pending');
    expect(notifications, isEmpty);
    expect(finishedCalls, 1, reason: 'onFinished must fire even on timeout, to allow teardown');
    expect(closeCalls, 1);
  });

  test('onFinished fires exactly once even when the result arrives instead of timing out',
      () async {
    await run('is BGP up on the core switch');
    await rpc.deliverAskResult(
        {'task_id': 'task-1', 'state': 'completed', 'output_text': 'ok'});
    await Future<void>.delayed(const Duration(milliseconds: 100));

    expect(finishedCalls, 1);
  });
}
