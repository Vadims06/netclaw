import 'package:flutter_test/flutter_test.dart';
import 'package:netclaw_mobile/ncfed/edge_ask_client.dart';
import 'package:netclaw_mobile/ncfed/edge_client.dart';
import 'package:netclaw_mobile/ncfed/voice_transcription.dart';

/// Records every `call()` NCFED method + params — lets the test assert the
/// exact request shape a voice input produces, without a real microphone/STT
/// platform channel (T020: this is not a speech-recognition-accuracy test).
class _RecordingEdgeRpcSource implements EdgeRpcSource {
  final List<(String method, Map<String, dynamic> params)> calls = [];

  @override
  void on(String method, EdgeMethodHandler handler) {}

  @override
  Future<Map<String, dynamic>> call(String method, Map<String, dynamic> params,
      {Duration timeout = const Duration(seconds: 30)}) async {
    calls.add((method, params));
    return {'task_id': 'task-voice-1'};
  }
}

void main() {
  test('a transcribed voice input produces the exact same request shape a typed one would',
      () async {
    final source = _RecordingEdgeRpcSource();
    final askClient = EdgeAskClient(source);
    final voice = VoiceTranscription(
      listenOnce: ({onListeningChange}) async => 'check every core router for BGP problems',
    );

    final result = await voice.recordAndAsk(askClient);

    expect(result, isNotNull);
    final (taskId, text) = result!;
    expect(taskId, 'task-voice-1');
    expect(text, 'check every core router for BGP problems');
    expect(source.calls, hasLength(1));
    expect(source.calls.single.$1, 'n2n/edge/ask');
    // The exact request shape a typed message produces via
    // EdgeAskClient.ask() -- {"text": ...}, nothing voice-specific.
    expect(source.calls.single.$2, {'text': 'check every core router for BGP problems'});
  });

  test('nothing heard never sends an empty (or any) request', () async {
    final source = _RecordingEdgeRpcSource();
    final askClient = EdgeAskClient(source);
    final voice = VoiceTranscription(listenOnce: ({onListeningChange}) async => null);

    final result = await voice.recordAndAsk(askClient);

    expect(result, isNull);
    expect(source.calls, isEmpty);
  });

  test('whitespace-only transcription is treated as nothing heard', () async {
    final source = _RecordingEdgeRpcSource();
    final askClient = EdgeAskClient(source);
    final voice = VoiceTranscription(listenOnce: ({onListeningChange}) async => '   ');

    final result = await voice.recordAndAsk(askClient);

    expect(result, isNull);
    expect(source.calls, isEmpty);
  });
}
