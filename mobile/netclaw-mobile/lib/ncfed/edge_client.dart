import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'edge_identity.dart';
import 'enrollment_qr_payload.dart';

/// Raised for any NCFED-level failure: a JSON-RPC error reply, a request
/// timeout, or the underlying connection failing/closing.
class EdgeClientException implements Exception {
  final String code;
  final String message;
  EdgeClientException(this.code, this.message);

  @override
  String toString() => 'EdgeClientException($code): $message';
}

typedef EdgeMethodHandler = FutureOr<Map<String, dynamic>> Function(Map<String, dynamic> params);

/// Anything that can register a handler for a Border-initiated method —
/// implemented by `EdgeClient`. Lets feed/heartbeat wiring code (and its
/// tests) depend on just this narrow surface instead of the full client
/// and its real WebSocket connection.
abstract class EdgeMethodSource {
  void on(String method, EdgeMethodHandler handler);
}

/// One connection to a NetClaw Border over the NCFED edge (WebSocket)
/// transport (feature 066). Mirrors the Border's own EdgeChannel
/// (mcp-servers/protocol-mcp/bgp/federation/edge.py) dispatch shape — whole
/// JSON-RPC 2.0 messages over `.send()`/the message stream, no byte framing
/// (a WebSocket connection already frames each message).
class EdgeClient implements EdgeMethodSource {
  final WebSocketChannel _channel;
  final EdgeIdentity identity;
  int _nextId = 0;
  final _pending = <String, Completer<Map<String, dynamic>>>{};
  final _handlers = <String, EdgeMethodHandler>{};
  final _connectionWaiters = <Completer>{};
  late final StreamSubscription _sub;
  bool _closed = false;

  /// True once close() has run or the connection has failed/closed — the
  /// reconnect supervisor (T030) uses this to decide whether to re-dial.
  bool get isClosed => _closed;

  /// The Border-computed SHA-256 fingerprint of this device's public key,
  /// returned by the `in2n/enroll` response. The caller (enrollment_screen)
  /// MUST persist this alongside `memberId` — it is required by
  /// `reconnect()`'s `in2n/hello` call, and is authoritative Border-issued
  /// data, not something this client independently re-derives from the
  /// certificate (avoids needing an X.509/DER parser in Dart).
  String? enrollFingerprint;

  EdgeClient._(this._channel, this.identity) {
    _sub = _channel.stream.listen(
      _onMessage,
      onError: (Object error) => _failAll(error),
      onDone: () => _failAll('connection closed'),
    );
  }

  /// Registers a handler for a Border-initiated method (e.g.
  /// n2n/edge/heartbeat, n2n/edge/self_status, n2n/edge/message).
  @override
  void on(String method, EdgeMethodHandler handler) {
    _handlers[method] = handler;
  }

  void _failAll(Object error) {
    if (_closed) return;
    _closed = true; // the connection is no longer usable either way
    final err = EdgeClientException('connection_error', '$error');
    for (final c in _pending.values) {
      if (!c.isCompleted) c.completeError(err);
    }
    for (final c in _connectionWaiters) {
      if (!c.isCompleted) c.completeError(err);
    }
  }

  void _onMessage(dynamic raw) {
    final msg = jsonDecode(raw as String) as Map<String, dynamic>;
    if (msg.containsKey('method')) {
      final method = msg['method'] as String;
      final params = (msg['params'] as Map<String, dynamic>?) ?? <String, dynamic>{};
      final handler = _handlers[method];
      if (handler == null) return; // unknown method — silently dropped, mirrors EdgeChannel
      Future(() async {
        final result = await handler(params);
        final id = msg['id'];
        if (id != null) {
          _channel.sink.add(jsonEncode({'jsonrpc': '2.0', 'id': id, 'result': result}));
        }
      });
    } else if (msg.containsKey('id')) {
      final completer = _pending.remove(msg['id']);
      if (completer == null || completer.isCompleted) return;
      if (msg.containsKey('error')) {
        final err = msg['error'] as Map<String, dynamic>;
        completer.completeError(EdgeClientException('${err['code']}', '${err['message']}'));
      } else {
        completer.complete((msg['result'] as Map<String, dynamic>?) ?? <String, dynamic>{});
      }
    }
  }

  Future<Map<String, dynamic>> call(String method, Map<String, dynamic> params,
      {Duration timeout = const Duration(seconds: 30)}) {
    _nextId += 1;
    final id = 'phone:$_nextId';
    final completer = Completer<Map<String, dynamic>>();
    _pending[id] = completer;
    _channel.sink.add(jsonEncode({'jsonrpc': '2.0', 'id': id, 'method': method, 'params': params}));
    return completer.future.timeout(timeout, onTimeout: () {
      _pending.remove(id);
      throw EdgeClientException('timeout', '$method timed out');
    });
  }

  Future<void> close() async {
    _closed = true;
    await _sub.cancel();
    await _channel.sink.close();
  }

  /// Dials the Border and completes the in2n/enroll handshake (first-time
  /// enrollment). Applies D7's domain check BEFORE dialing —
  /// see verifyClawDomainBeforeDial.
  static Future<EdgeClient> enroll(
    EnrollmentQrPayload payload, {
    required String memberId,
    required EdgeIdentity identity,
    String runtimeKind = 'mobile',
    String? displayName,
  }) async {
    verifyClawDomainBeforeDial(payload);
    final uri = Uri(scheme: 'wss', host: payload.clawDomain, port: payload.borderPort);
    // Standard TLS hostname verification (against the platform's public CA
    // trust store) happens automatically here — a mismatched/untrusted
    // certificate makes this connection fail outright (research D7); no
    // custom certificate inspection code exists anywhere in this client.
    final channel = IOWebSocketChannel.connect(uri);
    final client = EdgeClient._(channel, identity);

    final challenge = Completer<Uint8List>();
    client._connectionWaiters.add(challenge);
    client.on('n2n/edge/challenge', (params) {
      if (!challenge.isCompleted) {
        challenge.complete(hexDecode(params['nonce'] as String));
      }
      return <String, dynamic>{};
    });
    try {
      final nonce = await challenge.future.timeout(const Duration(seconds: 10));
      final certPem = await identity.certificatePem();
      final signature = await identity.sign(nonce);
      final result = await client.call('in2n/enroll', {
        'token': payload.enrollmentToken,
        'member_id': memberId,
        'cert_pem': certPem,
        'signature': hexEncode(signature),
        'runtime_kind': runtimeKind,
        'display_name': ?displayName,
      });
      client.enrollFingerprint = result['enroll_fingerprint'] as String?;
      return client;
    } finally {
      client._connectionWaiters.remove(challenge);
    }
  }

  /// Reconnects to an already-enrolled Border via in2n/hello (pinned-key
  /// proof, no token) — used after a dropped connection (US3). `keyFingerprint`
  /// MUST be the `enrollFingerprint` value `enroll()` returned at enrollment
  /// time and persisted by the caller — the Border, not this client, is the
  /// source of truth for what fingerprint it pinned.
  static Future<EdgeClient> reconnect(
    EnrollmentQrPayload payload, {
    required String memberId,
    required String keyFingerprint,
    required EdgeIdentity identity,
  }) async {
    verifyClawDomainBeforeDial(payload);
    final uri = Uri(scheme: 'wss', host: payload.clawDomain, port: payload.borderPort);
    final channel = IOWebSocketChannel.connect(uri);
    final client = EdgeClient._(channel, identity);

    final challenge = Completer<Uint8List>();
    client._connectionWaiters.add(challenge);
    client.on('n2n/edge/challenge', (params) {
      if (!challenge.isCompleted) {
        challenge.complete(hexDecode(params['nonce'] as String));
      }
      return <String, dynamic>{};
    });
    try {
      final nonce = await challenge.future.timeout(const Duration(seconds: 10));
      final signature = await identity.sign(nonce);
      await client.call('in2n/hello', {
        'member_id': memberId,
        'key_fingerprint': keyFingerprint,
        'signature': hexEncode(signature),
      });
      client.enrollFingerprint = keyFingerprint;
      return client;
    } finally {
      client._connectionWaiters.remove(challenge);
    }
  }
}

Uint8List hexDecode(String hex) {
  final bytes = Uint8List(hex.length ~/ 2);
  for (var i = 0; i < bytes.length; i++) {
    bytes[i] = int.parse(hex.substring(i * 2, i * 2 + 2), radix: 16);
  }
  return bytes;
}

String hexEncode(Uint8List bytes) =>
    bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
