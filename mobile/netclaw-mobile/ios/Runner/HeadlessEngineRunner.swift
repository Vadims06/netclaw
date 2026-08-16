import Flutter
import Foundation
import flutter_secure_storage_darwin
import flutter_local_notifications

/// TEMPORARY DIAGNOSTIC: writes a timestamped line to a file on disk since
/// NSLog/os_log output has proven unreliable to observe via idevicesyslog
/// on this device/build. Best-effort; never throws.
func diagLog(_ msg: String) {
    NSLog("[hl-diag] %@", msg)
    guard let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first else { return }
    let url = docs.appendingPathComponent("bh_diag_native.log")
    let line = "\(Date().ISO8601Format()) \(msg)\n"
    if let data = line.data(using: .utf8) {
        if FileManager.default.fileExists(atPath: url.path), let handle = try? FileHandle(forWritingTo: url) {
            handle.seekToEndOfFile()
            handle.write(data)
            try? handle.close()
        } else {
            try? data.write(to: url)
        }
    }
}

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
/// `FlutterEngine` creation/run MUST happen on the main thread. AppIntents'
/// `perform()` does not guarantee it runs on the main actor, so without this
/// annotation, engine startup could race against (and deadlock with)
/// whatever executor AppIntents chose -- observed on-device as a hang deep
/// inside AppIntents'/Swift Concurrency's own machinery, never reaching this
/// class's own code at all. Marking the class `@MainActor` makes every call
/// site hop onto the main actor via an implicit `await`, guaranteeing engine
/// work always happens on the thread Flutter requires.
@MainActor
final class HeadlessEngineRunner {
    /// A raw second `FlutterEngine` created independently of the app's main
    /// engine is unsupported when that main engine may still be alive in the
    /// same process (exactly App Intents' `openAppWhenRun = false` scenario —
    /// confirmed on-device: the app process gets thawed/resumed, not
    /// launched fresh). `FlutterEngineGroup` is Flutter's documented
    /// mechanism for creating additional engines safely in that situation.
    /// Shared/lazy so repeated intent invocations reuse the same group
    /// rather than re-paying Dart VM setup each time.
    private static let engineGroup = FlutterEngineGroup(name: "netclaw-headless-intents", project: nil)

    private let engine: FlutterEngine
    private let channel: FlutterMethodChannel

    init(entrypoint: String, libraryURI: String, channelName: String) {
        diagLog("creating FlutterEngine for \(entrypoint) via FlutterEngineGroup (lib: \(libraryURI))")
        let engine = Self.engineGroup.makeEngine(withEntrypoint: entrypoint, libraryURI: libraryURI)
        diagLog("engineGroup.makeEngine(withEntrypoint: \(entrypoint)) returned")
        // Deliberately NOT calling GeneratedPluginRegistrant.register(with:) here.
        // That registers every plugin in the app -- including Firebase Core/
        // Messaging -- into this second, throwaway engine while the main
        // engine's own Firebase instance is still alive in the same process.
        // Firebase's SDKs hold internal locks around app-lifecycle
        // notifications (UIApplicationDidEnterBackgroundNotification) and are
        // documented as unsafe to configure/register twice per process; doing
        // so here deadlocked the main thread during a background transition
        // and iOS's scene-update watchdog (0x8BADF00D) killed the app after
        // 10s. Only register what these headless entrypoints actually touch.
        // path_provider needs no explicit registration here -- it isn't in
        // GeneratedPluginRegistrant.m either (confirmed), and the main
        // engine's own getApplicationDocumentsDirectory() calls work fine
        // without it, so its Swift implementation self-registers or needs
        // no native plugin class at all in this Flutter version.
        if let registrar = engine.registrar(forPlugin: "FlutterSecureStorageDarwinPlugin") {
            FlutterSecureStorageDarwinPlugin.register(with: registrar)
        }
        if let registrar = engine.registrar(forPlugin: "FlutterLocalNotificationsPlugin") {
            FlutterLocalNotificationsPlugin.register(with: registrar)
        }
        diagLog("minimal plugin set registered")
        if let registrar = engine.registrar(forPlugin: "EdgeIdentityPlugin") {
            EdgeIdentityPlugin.register(with: registrar)
            diagLog("EdgeIdentityPlugin registered")
        } else {
            diagLog("EdgeIdentityPlugin registrar was nil")
        }
        self.engine = engine
        self.channel = FlutterMethodChannel(name: channelName, binaryMessenger: engine.binaryMessenger)
        diagLog("method channel created: \(channelName)")
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
            diagLog("invoking submit with timeout \(timeout)s")
            DispatchQueue.main.asyncAfter(deadline: .now() + timeout) {
                diagLog("local Swift timeout fired after \(timeout)s")
                resumeOnce(.failure(HeadlessIntentError.timedOut))
            }
            channel.invokeMethod("submit", arguments: arguments) { reply in
                diagLog("submit reply received: \(String(describing: reply))")
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
