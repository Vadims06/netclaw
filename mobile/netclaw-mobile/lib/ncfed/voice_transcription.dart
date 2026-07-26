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
  final Future<String?> Function({void Function(bool listening)? onListeningChange}) _listenOnce;

  VoiceTranscription({
    Future<String?> Function({void Function(bool listening)? onListeningChange})? listenOnce,
  }) : _listenOnce = listenOnce ?? _defaultListenOnce;

  /// Speech Recognition authorization (`NSSpeechRecognitionUsageDescription`
  /// on iOS) is a SEPARATE OS permission from microphone access — granting
  /// the mic prompt does not imply this one was granted too. If
  /// `initialize()` fails, `speech.lastError` carries the real reason (e.g.
  /// permission denied, no recognizer available) rather than silently doing
  /// nothing, which previously looked identical to "tapped record, nothing
  /// happened" regardless of cause.
  static Future<String?> _defaultListenOnce({void Function(bool listening)? onListeningChange}) async {
    final speech = stt.SpeechToText();
    final initialized = await speech.initialize(
      onStatus: (status) => onListeningChange?.call(status == 'listening'),
    );
    if (!initialized) {
      throw StateError(
          'Speech recognition unavailable: ${speech.lastError?.errorMsg ?? 'permission denied or no recognizer on this device'}');
    }
    final completer = Completer<String?>();
    await speech.listen(
      onResult: (result) {
        if (result.finalResult && !completer.isCompleted) {
          completer.complete(result.recognizedWords.isEmpty ? null : result.recognizedWords);
        }
      },
      // Without an explicit bound, a session with no natural end-of-speech
      // detection (quiet mic, background noise) never resolves `finalResult`
      // at all — the button press then looks identical to doing nothing.
      listenOptions: stt.SpeechListenOptions(
        listenFor: const Duration(seconds: 30),
        pauseFor: const Duration(seconds: 3),
      ),
    );
    try {
      return await completer.future.timeout(const Duration(seconds: 35));
    } on TimeoutException {
      return null; // genuinely heard nothing usable in time — not an error
    } finally {
      await speech.stop();
      onListeningChange?.call(false);
    }
  }

  /// Records, transcribes, and sends the result through the SAME `ask()`
  /// path a typed message uses. Returns the (task_id, transcribed text)
  /// pair — the caller needs the text too, to show a pending conversation
  /// turn exactly like a typed request gets — or `null` if nothing was
  /// heard (never sends an empty request). [onListeningChange] lets the
  /// caller show a "Listening…" indicator instead of silence during the
  /// recording window.
  Future<(String taskId, String text)?> recordAndAsk(
    EdgeAskClient askClient, {
    void Function(bool listening)? onListeningChange,
  }) async {
    final text = await _listenOnce(onListeningChange: onListeningChange);
    if (text == null || text.trim().isEmpty) return null;
    final taskId = await askClient.ask(text);
    return (taskId, text);
  }
}
