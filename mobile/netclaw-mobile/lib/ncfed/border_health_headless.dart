import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:path_provider/path_provider.dart';

import 'device_heartbeat.dart';
import 'edge_client.dart';
import 'headless_connect.dart';

const _channel = MethodChannel('ca.automateyournetwork.netclaw/border_health');

/// TEMPORARY DIAGNOSTIC: appends a timestamped line to a file on disk so it
/// can be pulled and read even when live log streaming (idevicesyslog) is
/// unreliable/unavailable. Best-effort -- swallows its own errors so a
/// diagnostic write can never itself break the real flow.
Future<void> _diag(String msg) async {
  try {
    final dir = await getApplicationDocumentsDirectory();
    final f = File('${dir.path}/bh_diag.log');
    await f.writeAsString(
      '${DateTime.now().toIso8601String()} $msg\n',
      mode: FileMode.append,
      flush: true,
    );
  } catch (_) {}
}

/// Entry point for the headless `FlutterEngine` `BorderHealthIntent.swift`
/// spins up (spec 111, User Story 3). Unlike the other two intents,
/// "Border health" in this system is a periodic passive push, not a
/// request/response query (research.md R4) -- there is no Border-side call
/// to make for the health data itself. Connecting still matters: it is what
/// proves the Border is reachable at all (FR-008's failure path), and it
/// reuses the SAME cold-connect classification (not-enrolled/timeout) as
/// the other two intents for consistency, even though the connected
/// [EdgeClient] is otherwise unused once `connectHeadless()` succeeds.
@pragma('vm:entry-point')
Future<void> borderHealthMain() async {
  await _diag('borderHealthMain entered');
  WidgetsFlutterBinding.ensureInitialized();
  await _diag('WidgetsFlutterBinding ready');
  _channel.setMethodCallHandler((call) async {
    await _diag('submit received: ${call.method}');
    if (call.method != 'submit') return null;
    final dir = await getApplicationDocumentsDirectory();
    await _diag('got documents dir: ${dir.path}');
    final EdgeClient client;
    try {
      client = await connectHeadless(directory: dir);
      await _diag('connectHeadless succeeded');
    } on NotEnrolledError {
      await _diag('connectHeadless: not enrolled');
      throw PlatformException(code: 'not_enrolled');
    } on ConnectTimeoutError {
      await _diag('connectHeadless: timed out');
      throw PlatformException(code: 'timeout');
    }
    await client.close();
    try {
      final result = await runBorderHealth(DeviceHeartbeatStore(dir));
      await _diag('runBorderHealth succeeded: $result');
      return result;
    } on NoHealthDataError {
      await _diag('runBorderHealth: no data');
      throw PlatformException(code: 'no_data');
    } catch (e) {
      await _diag('runBorderHealth failed: $e');
      throw PlatformException(code: 'failed', message: '$e');
    }
  });
  await _diag('method call handler registered');
}

/// No heartbeat has ever been received on this device (spec 111, User Story
/// 3 AS3) -- deliberately distinct from a connect failure: the Border was
/// reachable, there just isn't a cached value yet (e.g. immediately after
/// enrollment).
class NoHealthDataError implements Exception {
  const NoHealthDataError();
  @override
  String toString() => 'NoHealthDataError: no cached heartbeat has ever been received';
}

/// The testable core of [borderHealthMain]: reads the last cached heartbeat
/// (research.md R4) and speaks its summary folded together with a
/// human-readable age, or throws [NoHealthDataError] if none has ever been
/// received (FR-007) -- this is never conflated with a connection failure.
Future<String> runBorderHealth(DeviceHeartbeatStore store) async {
  final status = await store.load();
  if (status == null) {
    throw const NoHealthDataError();
  }
  return 'As of ${_formatAge(status.pushedAt)}: ${status.summary}';
}

String _formatAge(DateTime pushedAt) {
  final age = DateTime.now().toUtc().difference(pushedAt.toUtc());
  if (age.inMinutes < 1) return 'just now';
  if (age.inMinutes == 1) return '1 minute ago';
  if (age.inMinutes < 60) return '${age.inMinutes} minutes ago';
  if (age.inHours == 1) return '1 hour ago';
  if (age.inHours < 24) return '${age.inHours} hours ago';
  final days = age.inDays;
  return days == 1 ? '1 day ago' : '$days days ago';
}
