import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:netclaw_mobile/ncfed/conversation_store.dart';

void main() {
  test('appended turns persist across a simulated app restart (T011)', () async {
    final dir = await Directory.systemTemp.createTemp('ncfed_conv_test_');
    addTearDown(() => dir.delete(recursive: true));

    final storeBeforeRestart = ConversationStore(dir);
    await storeBeforeRestart.addPending('task-1', 'check BGP on core routers');
    await storeBeforeRestart.updateState('task-1', 'completed', answerText: 'All healthy.');
    expect(storeBeforeRestart.turns, hasLength(1));

    final storeAfterRestart = ConversationStore(dir);
    expect(storeAfterRestart.turns, isEmpty); // not loaded yet
    await storeAfterRestart.load();
    expect(storeAfterRestart.turns, hasLength(1));
    expect(storeAfterRestart.turns.single.requestText, 'check BGP on core routers');
    expect(storeAfterRestart.turns.single.answerText, 'All healthy.');
    expect(storeAfterRestart.turns.single.state, 'completed');
  });

  test('a stray late update never flips an already-terminal turn (cancel-after-completion race)',
      () async {
    final dir = await Directory.systemTemp.createTemp('ncfed_conv_test_');
    addTearDown(() => dir.delete(recursive: true));

    final store = ConversationStore(dir);
    await store.addPending('task-2', 'fast request');
    await store.updateState('task-2', 'completed', answerText: 'done already');
    await store.updateState('task-2', 'cancelled'); // arrives late, after completion

    expect(store.turns.single.state, 'completed');
    expect(store.turns.single.answerText, 'done already');
  });

  test('clear() deletes all turns, the persisted file, and every saved photo', () async {
    final dir = await Directory.systemTemp.createTemp('ncfed_conv_test_');
    addTearDown(() => dir.delete(recursive: true));

    final store = ConversationStore(dir);
    await store.addPending('task-3', 'no photo here');
    await store.addPending('task-4', 'has a photo', photoBytes: [1, 2, 3]);
    final photoPath = store.turns.last.photoPath!;
    expect(await File(photoPath).exists(), isTrue);

    await store.clear();

    expect(store.turns, isEmpty);
    expect(await File(photoPath).exists(), isFalse);
    expect(await File('${dir.path}/ncfed_conversation.json').exists(), isFalse);

    // A fresh store over the same directory sees nothing either -- clear()
    // really did remove the persisted file, not just the in-memory list.
    final reloaded = ConversationStore(dir);
    await reloaded.load();
    expect(reloaded.turns, isEmpty);
  });
}
