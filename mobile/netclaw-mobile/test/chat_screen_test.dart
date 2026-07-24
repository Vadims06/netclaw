import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:netclaw_mobile/ncfed/conversation_store.dart';
import 'package:netclaw_mobile/ncfed/edge_ask_client.dart';
import 'package:netclaw_mobile/ncfed/edge_client.dart';
import 'package:netclaw_mobile/screens/chat_screen.dart';

/// Minimal stand-in for the wire connection `EdgeAskClient` needs — avoids
/// constructing a real `EdgeClient` (which requires an actual
/// WebSocketChannel) just to test the widget in isolation.
class _FakeEdgeRpcSource implements EdgeRpcSource {
  final Map<String, EdgeMethodHandler> handlers = {};

  @override
  void on(String method, EdgeMethodHandler handler) {
    handlers[method] = handler;
  }

  @override
  Future<Map<String, dynamic>> call(String method, Map<String, dynamic> params,
      {Duration timeout = const Duration(seconds: 30)}) async {
    return {'task_id': 'task-1'};
  }
}

/// Builds a ChatScreen wired to a store pre-seeded with one turn in `state`.
/// Real dart:io (Directory/ConversationStore) is used, so setup runs inside
/// `runAsync()` — testWidgets() runs in a fake-async zone where a plain
/// await never lets real File I/O complete.
Future<Widget> _buildChatScreen(WidgetTester tester, String state, {String? answerText}) async {
  late Directory dir;
  late ConversationStore store;
  await tester.runAsync(() async {
    dir = await Directory.systemTemp.createTemp('ncfed_chat_test_');
    store = ConversationStore(dir);
    await store.addPending('task-1', 'check BGP');
    if (state != 'pending') {
      await store.updateState('task-1', state, answerText: answerText);
    }
  });
  addTearDown(() => dir.delete(recursive: true));
  return MaterialApp(
    home: Scaffold(body: ChatScreen(askClient: EdgeAskClient(_FakeEdgeRpcSource()), store: store)),
  );
}

void main() {
  testWidgets('an in-progress turn shows a distinct state from a completed one (T015)',
      (tester) async {
    await tester.pumpWidget(await _buildChatScreen(tester, 'pending'));
    await tester.pump();

    expect(find.text('Working…'), findsOneWidget);
    expect(find.text('Cancel'), findsOneWidget);
    expect(find.text('All healthy.'), findsNothing);
  });

  testWidgets('a completed turn shows its answer, not the in-progress state', (tester) async {
    await tester.pumpWidget(
        await _buildChatScreen(tester, 'completed', answerText: 'All healthy.'));
    await tester.pump();

    expect(find.text('Working…'), findsNothing);
    expect(find.text('Cancel'), findsNothing);
    expect(find.text('All healthy.'), findsOneWidget);
  });

  testWidgets('cancelling updates the turn to cancelled, not failed', (tester) async {
    await tester.pumpWidget(await _buildChatScreen(tester, 'cancelled'));
    await tester.pump();

    expect(find.text('Cancelled'), findsOneWidget);
    expect(find.text('Working…'), findsNothing);
    expect(find.textContaining('Failed'), findsNothing);
  });
}
