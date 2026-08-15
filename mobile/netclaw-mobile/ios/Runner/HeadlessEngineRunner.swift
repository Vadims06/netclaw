import Flutter
import Foundation

/// Errors surfaced to Swift by a headless entrypoint's `submit` reply,
/// classified via `FlutterError.code` so each intent can speak the right
/// distinct failure message (spec 111 FR-008/FR-010).
enum HeadlessIntentError: Error {
    case notEnrolled
    case timedOut
    case noData
    case failed(String)
}

/// Shared plumbing for every headless-engine App Intent (spec 111): a plain
/// `FlutterEngine` per invocation (never `FlutterEngineGroup`, research.md
/// R1), only `EdgeIdentityPlugin` manually registered beyond the
/// auto-generated package plugins (`path_provider`/`flutter_secure_storage`,
/// needed by the shared `headless_connect.dart`/`enrollment_store.dart`
/// helpers) — mirroring `AppDelegate.swift`'s existing `handleBackgroundRefresh`
/// pattern exactly. Deterministic teardown (FR-009/research.md R7) happens
/// simply by the owning `AppIntent` releasing its last strong reference to
/// this object once it's done with it — matching how `AppDelegate.swift`
/// tears its own background-refresh engine down by setting
/// `backgroundRefreshEngine = nil`, since `FlutterEngine` has no separate
/// public "destroy" call.
final class HeadlessEngineRunner {
    private let engine: FlutterEngine
    private let channel: FlutterMethodChannel

    init(entrypoint: String, channelName: String) {
        let engine = FlutterEngine(name: entrypoint)
        engine.run(withEntrypoint: entrypoint)
        GeneratedPluginRegistrant.register(with: engine)
        if let registrar = engine.registrar(forPlugin: "EdgeIdentityPlugin") {
            EdgeIdentityPlugin.register(with: registrar)
        }
        self.engine = engine
        self.channel = FlutterMethodChannel(name: channelName, binaryMessenger: engine.binaryMessenger)
    }

    /// Bridges a single Swift-initiated `invokeMethod("submit", ...)` call to
    /// async/await. Dart's handler either returns the spoken/acknowledgment
    /// string directly, or throws a `PlatformException` whose `code` this
    /// classifies into a [HeadlessIntentError]. A local [timeout] backstops a
    /// Dart side that never replies at all (distinct from `headless_connect.
    /// dart`'s own connect-specific timeout, which surfaces as a
    /// `"timeout"`-coded reply, not a silent hang).
    func submit(_ arguments: Any?, timeout: TimeInterval) async throws -> String {
        try await withCheckedThrowingContinuation { continuation in
            var didResume = false
            let resumeOnce: (Result<String, Error>) -> Void = { outcome in
                guard !didResume else { return }
                didResume = true
                continuation.resume(with: outcome)
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + timeout) {
                resumeOnce(.failure(HeadlessIntentError.timedOut))
            }
            channel.invokeMethod("submit", arguments: arguments) { reply in
                if let error = reply as? FlutterError {
                    switch error.code {
                    case "not_enrolled":
                        resumeOnce(.failure(HeadlessIntentError.notEnrolled))
                    case "timeout":
                        resumeOnce(.failure(HeadlessIntentError.timedOut))
                    case "no_data":
                        resumeOnce(.failure(HeadlessIntentError.noData))
                    default:
                        resumeOnce(.failure(HeadlessIntentError.failed(error.message ?? "unknown error")))
                    }
                } else if let ack = reply as? String {
                    resumeOnce(.success(ack))
                } else {
                    resumeOnce(.failure(HeadlessIntentError.failed("unexpected response")))
                }
            }
        }
    }

    /// `AskBorderIntent`-only: waits for Dart to proactively call `finished`
    /// on this same channel once its bounded post-acknowledgment window
    /// (research.md R8) resolves (the `ask_result` landed and the
    /// notification was posted, or that window's own internal timeout
    /// elapsed) — capped by this method's own [timeout] as a backstop.
    func waitForFinished(timeout: TimeInterval) async {
        await withCheckedContinuation { continuation in
            var didResume = false
            let resumeOnce: () -> Void = {
                guard !didResume else { return }
                didResume = true
                continuation.resume()
            }
            channel.setMethodCallHandler { call, result in
                if call.method == "finished" {
                    resumeOnce()
                    result(nil)
                } else {
                    result(FlutterMethodNotImplemented)
                }
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + timeout) {
                resumeOnce()
            }
        }
    }
}
