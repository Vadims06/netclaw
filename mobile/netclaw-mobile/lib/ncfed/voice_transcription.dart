import 'dart:async';

import 'package:speech_to_text/speech_to_text.dart' as stt;

import 'edge_ask_client.dart';

/// On-device speech-to-text for voice requests (feature 067, US4, research
/// D7): transcribes before sending, so the wire protocol never differs
/// between a typed and a spoken request — the Border always just sees
/// `{"text": ...}` via `n2n/edge/ask` (contract's client-side-shortcuts
/// section). `listenOnce` is injectable so tests can exercise
/// `recordAndAsk`'s request-shape guarantee without a real microphone/STT
/// platform channel.
class VoiceTranscription {
  final Future<String?> Function() _listenOnce;

  VoiceTranscription({Future<String?> Function()? listenOnce})
      : _listenOnce = listenOnce ?? _defaultListenOnce;

  static Future<String?> _defaultListenOnce() async {
    final speech = stt.SpeechToText();
    if (!await speech.initialize()) return null;
    final completer = Completer<String?>();
    await speech.listen(onResult: (result) {
      if (result.finalResult && !completer.isCompleted) {
        completer.complete(result.recognizedWords.isEmpty ? null : result.recognizedWords);
      }
    });
    final text = await completer.future;
    await speech.stop();
    return text;
  }

  /// Records, transcribes, and sends the result through the SAME `ask()`
  /// path a typed message uses. Returns the (task_id, transcribed text)
  /// pair — the caller needs the text too, to show a pending conversation
  /// turn exactly like a typed request gets — or `null` if nothing was
  /// heard (never sends an empty request).
  Future<(String taskId, String text)?> recordAndAsk(EdgeAskClient askClient) async {
    final text = await _listenOnce();
    if (text == null || text.trim().isEmpty) return null;
    final taskId = await askClient.ask(text);
    return (taskId, text);
  }
}
