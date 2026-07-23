# NetClaw Mobile

Flutter (iOS + Android, one codebase) client app for the NCFED Edge Node profile.
A thin client — no LLM, no local agent reasoning. Connects outbound to a NetClaw
Border Claw, advertises device-native capabilities (camera, biometric approval,
location, etc.), and renders whatever the Border sends back.

Feature 066 (this repo's `specs/066-netclaw-mobile-ncfed-edge/`) covers the protocol
foundation: enrollment and the Border-to-phone push channel. Direction 2 (phone asks
the Border something, `specs/067-ncfed-mobile-command-channel/`) and Direction 3
(biometrics/camera/mic capture, `specs/068-ncfed-mobile-biometrics-capture/`) build on
top of this, in separate specs.

## Structure

```
lib/
  ncfed/                    # protocol layer -- no UI
    edge_identity.dart       # platform Keystore/Secure Enclave keygen + sign
    enrollment_qr_payload.dart
    edge_client.dart         # WebSocket JSON-RPC client (mirrors edge.py's EdgeChannel)
    enrollment_flow.dart     # QR -> parse -> domain check -> dial -> outcome
    message_feed.dart        # local persisted store for Border-pushed messages
    reconnect_supervisor.dart # generic bounded-retry loop (ports _in2n_member_dialer)
    push_registration.dart   # FCM/APNs token registration
    notification_deep_link.dart
  screens/
    enrollment_screen.dart   # "Scan Border QR Code"
    feed_screen.dart         # renders pushed messages
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

- **Android**: builds and runs on any machine with the Android SDK — no macOS
  required. `MainActivity.kt`'s `EdgeIdentityPlugin` (AndroidKeyStore-backed) has
  been reviewed but not exercised on a real device/emulator as of this commit.
- **iOS**: building, signing, and running the app — and exercising
  `EdgeIdentityPlugin.swift`'s Secure Enclave key generation — **requires Xcode,
  which only runs on macOS.** That code was written and reviewed without a Mac
  available and is entirely unverified until built there. The Secure Enclave is
  also unavailable on the iOS Simulator — testing needs a real device.
- Push-notification delivery (FCM/APNs, feature 066 US3) needs real Firebase/Apple
  Developer credentials configured on the Border (`.env.example`'s
  `FCM_SERVICE_ACCOUNT_JSON`/`APNS_*` vars) and a real `Firebase.initializeApp()`
  setup in the app (`google-services.json` / `GoogleService-Info.plist`) — neither
  exists in this repo; wire them in with your own project's credentials.
