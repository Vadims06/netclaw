import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

import 'edge_client.dart';

/// Maps the running platform to NCFED's `n2n/edge/register_push` `platform`
/// field — pulled out as a pure function so it's testable without Firebase.
String pushPlatformFor(TargetPlatform platform) =>
    platform == TargetPlatform.iOS ? 'apns' : 'fcm';

/// Registers this device's FCM/APNs push token with the Border
/// (n2n/edge/register_push, US3/T031) so a message pushed while the app is
/// backgrounded/disconnected still reaches the operator via a platform
/// notification. Requires `Firebase.initializeApp()` to have already run
/// with real project configuration (google-services.json /
/// GoogleService-Info.plist) — a deployment-time step with real
/// Firebase/Apple credentials, not something this module does on its own,
/// and not something verifiable in this environment.
class PushRegistration {
  final EdgeClient client;
  StreamSubscription<String>? _refreshSub;

  PushRegistration(this.client);

  Future<void> registerCurrentToken() async {
    final messaging = FirebaseMessaging.instance;
    await messaging.requestPermission();
    final token = await messaging.getToken();
    if (token != null) {
      await _sendToken(token);
    }
    _refreshSub ??= messaging.onTokenRefresh.listen(_sendToken);
  }

  Future<void> _sendToken(String token) async {
    try {
      await client.call('n2n/edge/register_push', {
        'platform': pushPlatformFor(defaultTargetPlatform),
        'token': token,
      });
    } catch (_) {
      // Best-effort — a failed registration just means the push fallback
      // won't work until the next successful attempt (e.g. next reconnect).
    }
  }

  void dispose() => _refreshSub?.cancel();
}
