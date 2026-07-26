# NetClaw Mobile

Flutter (iOS + Android, one codebase) client app for the NCFED Edge Node profile.
A thin client — no LLM, no local agent reasoning. Connects outbound to a NetClaw
Border Claw, advertises device-native capabilities (camera, biometric approval,
location, etc.), and renders whatever the Border sends back.

Feature 066 (this repo's `specs/066-netclaw-mobile-ncfed-edge/`) covers the protocol
foundation: enrollment and the Border-to-phone push channel. Feature 067
(`specs/067-ncfed-mobile-command-channel/`) adds the reverse direction — asking the
Border something from the phone (text, voice, or a scanned device QR/deep link).
Feature 068 (`specs/068-ncfed-mobile-biometrics-capture/`) adds two more slices on
top of both: Border-triggered approvals resolved on the phone with device
biometrics (Face ID/fingerprint), and camera/mic capture in either direction
(attach a photo to your own request, or let the Border request one from you).

## Structure

```
lib/
  ncfed/                     # protocol layer -- no UI
    edge_identity.dart        # platform Keystore/Secure Enclave keygen + sign
    enrollment_qr_payload.dart
    edge_client.dart          # WebSocket JSON-RPC client (mirrors edge.py's EdgeChannel)
    enrollment_flow.dart      # QR -> parse -> domain check -> dial -> outcome
    message_feed.dart         # local persisted store for Border-pushed messages (066)
    enrollment_store.dart     # persisted enrollment, so a restart redials instead of re-enrolling
    reconnect_supervisor.dart # bounded-retry loop; drives the app's auto-redial
    heartbeat.dart            # answers the Border's n2n/edge/heartbeat + self_status probes
    push_registration.dart    # FCM/APNs token registration
    notification_deep_link.dart # notification tap -> jump to that message in the feed
    edge_ask_client.dart      # n2n/edge/ask + task status/result/cancel (067)
    conversation_store.dart   # per-device persisted chat history (067)
    voice_transcription.dart  # on-device speech-to-text -> ask() (067, US4)
    device_deep_link.dart     # netclaw://device/<id> / QR -> ask() (067, US5)
    approval_client.dart      # tracks pushed approvals + approval_resolve (068, US1)
    capability_registration.dart # advertises/toggles capture capabilities (068, US3)
    capture_client.dart       # phone-initiated attach + Border-requested capture handler (068, US2/US3)
  screens/
    enrollment_screen.dart    # "Scan Border QR Code" + "Can't scan? Enter manually"
    manual_enrollment_screen.dart # domain/port/token typed by hand (no camera needed)
    empty_state.dart          # shared illustrated empty state
    feed_screen.dart          # renders pushed messages (066)
    chat_screen.dart          # request/answer history, cancel, voice, camera (067/068)
    device_scan_screen.dart   # "Scan Device" -- any time, post-enrollment (067, US5)
    approvals_screen.dart     # pending approvals, Face ID/fingerprint gate (068, US1)
    settings_screen.dart      # per-capture-type enable/disable toggles (068, US3)
    capture_screen.dart       # live camera preview + shutter (068, US2/US3)
  main.dart                   # EnrollmentGate -> HomeShell (Chat/Feed/Approvals/Settings tabs)
android/app/src/main/kotlin/.../MainActivity.kt  # FlutterFragmentActivity (local_auth needs a FragmentActivity host) + AndroidKeyStore EdgeIdentity plugin
ios/Runner/EdgeIdentityPlugin.swift               # Secure Enclave EdgeIdentity plugin
ios/Runner/X509SelfSigned.swift                    # manual self-signed cert builder
```

## Running against a local Border

1. On the Border, set `N2N_CLAW_DOMAIN` and `N2N_EDGE_WS_PORT` in `.env` and restart
   the daemon (`mcp-servers/protocol-mcp/bgp-daemon-v2.py`).
2. Issue a QR: `netclaw risk token --edge [label]`.
3. `flutter pub get`, then `flutter run` (Android) to launch the app and scan it.
   No usable camera (emulator, Simulator)? Tap **"Can't scan? Enter manually"** on
   the enrollment screen and type the domain, port, and token instead — it
   synthesizes exactly the payload a scan would produce.

Once enrolled, the app persists the enrollment (`enrollment_store.dart`) and
redials automatically on restart or a dropped connection, so steps 2–3 are
one-time. A Border that revokes the device returns `-32023`, which drops the app
back to the enrollment screen rather than retrying forever.

```bash
flutter analyze
flutter test
```

## Building a release

`flutter build appbundle` reads signing material from `android/key.properties`:

```properties
storeFile=/absolute/path/to/upload-keystore.jks
storePassword=…
keyAlias=upload
keyPassword=…
```

That file and any `*.jks`/`*.keystore` are gitignored and must never be
committed. **If it's absent the build still succeeds but signs with the debug
key** (Gradle prints a warning) — such an artifact cannot be uploaded to Play.
The release build type has R8 minification and resource shrinking enabled; keep
rules live in `android/app/proguard-rules.pro`.

## Docs

| Doc | What it covers |
|---|---|
| [`MOBILE-ONBOARDING.md`](MOBILE-ONBOARDING.md) | **How to securely enroll a phone against your own Border** — operator side (token/QR) and phone side, plus the security model. Start here. |
| [`TESTER-INSTRUCTIONS.md`](TESTER-INSTRUCTIONS.md) | Copy-paste handout for sending a build to someone else to test. |
| [`PLAY-STORE-ROADMAP.md`](PLAY-STORE-ROADMAP.md) | Google Play publication path, sequenced against this repo's build config. |
| [`APP-STORE-ROADMAP.md`](APP-STORE-ROADMAP.md) | Apple App Store publication path, sequenced against this repo's build config. |
| [`MAC-IOS-HANDOFF.md`](MAC-IOS-HANDOFF.md) | The original iOS handoff brief. Superseded as the source of truth by `specs/071-ios-mobile-port/` — read that spec's tasks.md for current status. |
| [`ASSETS.md`](ASSETS.md) | Icon/splash regeneration and brand rationale. |

The app ships with no hostnames or credentials — it is a generic NCFED edge
client, bound to whichever Border enrolls it. Any reference to
`netclaw.automateyournetwork.ca` in this repo is the maintainer's own test
Border, not a dependency.

## Platform-specific notes

- **Android**: builds and runs on any Linux/Mac/Windows machine with the Android
  SDK — no macOS required. Verified for real in this repo's own dev environment:
  a debug APK was built (`flutter build apk --debug`), installed and launched on
  an Android emulator (API 34, x86_64, KVM-accelerated), the real
  `mobile_scanner`/`CameraX` camera-permission dialog and a live emulated camera
  preview both rendered correctly inside `EnrollmentScreen`, and a full enrollment
  + `n2n/edge/ask` handshake completed against a real (throwaway, non-production)
  Border daemon over `wss://`. `MainActivity.kt`'s `EdgeIdentityPlugin`
  (AndroidKeyStore-backed) links and runs without crashing; its actual key
  generation/signing behavior has not been separately exercised end-to-end (no QR
  containing a real payload was presented to the emulator's synthetic camera feed).
  Feature 068 was verified the same way: a fresh debug APK (now linking `local_auth`
  and `camera` on top of everything above, and with `MainActivity` changed to
  `FlutterFragmentActivity`) built, installed, and launched cleanly on the same
  emulator — `logcat` showed no Dart/Flutter exception and the activity reached
  `topResumedActivity`, confirming the new native plugins don't crash on startup.
  Biometric approval and a real photo capture were NOT exercised here — this
  emulator has no provisioned fingerprint/Face-unlock enrollment and its virtual
  camera only produces a synthetic test pattern, not a real capture; both need
  either a real device or a properly provisioned emulator, done in a later pass.
  **A full production round trip has since been verified** (2026-07-25): a question
  asked from the emulated phone against the operator's real Border fanned out to
  the `cml` and `pyats` risk members and returned a 1583-byte answer to the handset
  in 2m13s, with GAIT audit records for each delegation. Enrollment, the edge WS
  transport, delegation/routing, and result delivery are all proven end to end.
- **iOS** (status as of spec `071-ios-mobile-port`, 2026-07-26 — see that spec's
  `tasks.md` for the authoritative, evolving record): **the app now builds,
  installs, and launches cleanly on the iOS Simulator.** Xcode 26.6 and Flutter
  3.44.8 were installed on the operator's Mac, and the first-ever
  `flutter build ios --debug --simulator` attempt surfaced (and fixed) two real
  blockers that no amount of code review could have found without an actual
  compiler run — see `specs/071-ios-mobile-port/research.md` D8 for full detail:
  1. `firebase-core`/`firebase-messaging`'s Swift Package Manager products
     require iOS 15.0 minimum; `IPHONEOS_DEPLOYMENT_TARGET` was still the
     Flutter template's `13.0`. Bumped to `15.0` in
     `ios/Runner.xcodeproj/project.pbxproj` (all 3 occurrences) — a
     build-config change only, no app behavior affected.
  2. `EdgeIdentityPlugin.swift` and `X509SelfSigned.swift` — both written
     without Xcode access — had genuinely **never been added to the Xcode
     project at all** (zero `PBXFileReference`/`PBXBuildFile`/Sources-phase
     entries). The build failed with `Cannot find 'EdgeIdentityPlugin' in
     scope`, confirming this file had truly never compiled. Fixed by adding
     both files to the `Runner` target via the `xcodeproj` Ruby gem
     (equivalent to dragging them into Xcode and checking "Add to target").
  After both fixes: `flutter build ios --debug --simulator` succeeds
  (`✓ Built build/ios/iphonesimulator/Runner.app`), and `xcrun simctl
  install`/`launch` confirm the app runs without crashing — the Dart VM
  service starts, and it correctly lands on the "Scan Border QR Code"
  enrollment screen (`EnrollmentGate` routing works) with a real system
  camera-permission dialog showing the exact `NSCameraUsageDescription` text
  from `Info.plist`. This is strong evidence `EdgeIdentityPlugin.register(with:)`
  runs at launch without crashing.
  - **Still unverified — needs a real device**: Secure Enclave key
    generation/signing, Face ID, and a real camera feed are all unavailable on
    the Simulator regardless of tooling. This needs a signing team selected in
    Xcode (requires the operator's own Apple ID — an interactive step no agent
    can do) and a physically connected iPhone. Neither was available as of this
    pass.
  - **Still unverified — needs interactive tapping**: the "Can't scan? Enter
    manually" fallback screen was reached in principle (the enrollment screen
    rendered correctly) but never actually tapped through and submitted — no
    CLI-only UI-automation tool was available/attempted for that.
  - `AppDelegate.swift` uses the stock `FlutterAppDelegate` with no
    `FlutterFragmentActivity`-style change, and the app launched successfully
    with it — consistent with the expectation that iOS's `local_auth` needs no
    such change, though the actual Face ID prompt itself is still unconfirmed
    (needs a real device).
  Remaining work: `specs/071-ios-mobile-port/tasks.md` Phase 1 (T004/T005,
  both requiring the operator's hands) through the rest of the task list.
- Push-notification delivery (FCM/APNs, feature 066 US3) needs real Firebase/Apple
  Developer credentials configured on the Border (`.env.example`'s
  `FCM_SERVICE_ACCOUNT_JSON`/`APNS_*` vars) and a real `Firebase.initializeApp()`
  setup in the app (`google-services.json` / `GoogleService-Info.plist`) — neither
  exists in this repo; wire them in with your own project's credentials. Note that
  `main.dart`'s `_tryRegisterPush()` swallows the resulting failure to a
  `debugPrint`, so **push silently does nothing rather than erroring** until those
  credentials exist. Notification-tap deep-linking is wired on the same success
  path: it jumps to the Feed tab and highlights the referenced message.
- Voice transcription (`speech_to_text`, feature 067 US4) and the device deep link
  (`app_links`, feature 067 US5) are wired in and pass their unit tests, but — like
  push notifications — haven't been exercised against a real microphone or a real
  tapped/scanned link on either platform.
- Feature 068's `local_auth`/`camera` packages need no manual `AndroidManifest.xml`
  permission entries — both merge their own required permissions (`CAMERA`,
  `RECORD_AUDIO`, `USE_BIOMETRIC`) in automatically via Gradle manifest merging.
  `INTERNET` is the exception and **is** declared explicitly in
  `android/app/src/main/AndroidManifest.xml`: it previously reached release builds
  only as a merge side-effect of `firebase_messaging`, so dropping that dependency
  would have silently broken networking in release with no compile-time error. On
  iOS, `local_auth`'s Face ID needs `NSFaceIDUsageDescription` (Touch ID/Android's
  BiometricPrompt need no key at all) — added to `Info.plist` alongside the
  existing camera/microphone keys, which now also cover the `camera` package's
  photo/video capture use (not exercised on iOS, same Xcode/Mac caveat as above).
