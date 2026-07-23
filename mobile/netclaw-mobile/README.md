# NetClaw Mobile

Flutter (iOS + Android, one codebase) client app for the NCFED Edge Node profile.
A thin client — no LLM, no local agent reasoning. Connects outbound to a NetClaw
Border Claw, advertises device-native capabilities (camera, biometric approval,
location, etc.), and renders whatever the Border sends back.

Feature 066 (this repo's `specs/066-netclaw-mobile-ncfed-edge/`) covers the protocol
foundation: enrollment and the Border-to-phone push channel. Feature 067
(`specs/067-ncfed-mobile-command-channel/`) adds the reverse direction — asking the
Border something from the phone (text, voice, or a scanned device QR/deep link).
Direction 3 (biometrics/camera/mic capture, `specs/068-ncfed-mobile-biometrics-capture/`)
builds on top of both, in a separate spec.

## Structure

```
lib/
  ncfed/                     # protocol layer -- no UI
    edge_identity.dart        # platform Keystore/Secure Enclave keygen + sign
    enrollment_qr_payload.dart
    edge_client.dart          # WebSocket JSON-RPC client (mirrors edge.py's EdgeChannel)
    enrollment_flow.dart      # QR -> parse -> domain check -> dial -> outcome
    message_feed.dart         # local persisted store for Border-pushed messages (066)
    reconnect_supervisor.dart # generic bounded-retry loop (ports _in2n_member_dialer)
    push_registration.dart    # FCM/APNs token registration
    notification_deep_link.dart
    edge_ask_client.dart      # n2n/edge/ask + task status/result/cancel (067)
    conversation_store.dart   # per-device persisted chat history (067)
    voice_transcription.dart  # on-device speech-to-text -> ask() (067, US4)
    device_deep_link.dart     # netclaw://device/<id> / QR -> ask() (067, US5)
  screens/
    enrollment_screen.dart    # "Scan Border QR Code" (one-time, pre-enrollment)
    feed_screen.dart          # renders pushed messages (066)
    chat_screen.dart          # request/answer history, cancel, voice (067)
    device_scan_screen.dart   # "Scan Device" -- any time, post-enrollment (067, US5)
  main.dart                   # EnrollmentGate -> HomeShell (Chat + Feed tabs)
android/app/src/main/kotlin/.../MainActivity.kt  # AndroidKeyStore EdgeIdentity plugin
ios/Runner/EdgeIdentityPlugin.swift               # Secure Enclave EdgeIdentity plugin
ios/Runner/X509SelfSigned.swift                    # manual self-signed cert builder
```

## Running against a local Border

1. On the Border, set `N2N_CLAW_DOMAIN` and `N2N_EDGE_WS_PORT` in `.env` and restart
   the daemon (`mcp-servers/protocol-mcp/bgp-daemon-v2.py`).
2. Issue a QR: `netclaw risk token --edge [label]`.
3. `flutter pub get`, then `flutter run` (Android) to launch the app and scan it.

```bash
flutter analyze
flutter test
```

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
- **iOS**: building, signing, and running the app — and exercising
  `EdgeIdentityPlugin.swift`'s Secure Enclave key generation — **requires Xcode,
  which only runs on macOS.** That code was written and reviewed without a Mac
  available and is entirely unverified until built there. The Secure Enclave is
  also unavailable on the iOS Simulator — testing needs a real device.
  `Info.plist` declares `NSCameraUsageDescription`, `NSMicrophoneUsageDescription`,
  `NSSpeechRecognitionUsageDescription`, and the `netclaw://` URL scheme — all
  required for the camera/voice/deep-link features to not crash on first use, but
  none of this has been exercised on a real device either.
- Push-notification delivery (FCM/APNs, feature 066 US3) needs real Firebase/Apple
  Developer credentials configured on the Border (`.env.example`'s
  `FCM_SERVICE_ACCOUNT_JSON`/`APNS_*` vars) and a real `Firebase.initializeApp()`
  setup in the app (`google-services.json` / `GoogleService-Info.plist`) — neither
  exists in this repo; wire them in with your own project's credentials.
- Voice transcription (`speech_to_text`, feature 067 US4) and the device deep link
  (`app_links`, feature 067 US5) are wired in and pass their unit tests, but — like
  push notifications — haven't been exercised against a real microphone or a real
  tapped/scanned link on either platform.
