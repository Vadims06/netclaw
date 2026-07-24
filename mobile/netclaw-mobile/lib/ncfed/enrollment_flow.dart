import 'edge_client.dart';
import 'edge_identity.dart';
import 'enrollment_qr_payload.dart';

/// Result of one enrollment attempt from a scanned QR payload — pulled out
/// of enrollment_screen.dart so the actual decision logic (parse → domain
/// check → dial → friendly error mapping) is unit-testable without needing
/// the `mobile_scanner` widget or a real network/platform channel for the
/// failure paths (T017).
sealed class EnrollmentOutcome {}

class EnrollmentSuccess extends EnrollmentOutcome {
  final EdgeClient client;
  final EnrollmentQrPayload payload;
  EnrollmentSuccess(this.client, this.payload);
}

class EnrollmentFailure extends EnrollmentOutcome {
  final String message;
  EnrollmentFailure(this.message);
}

/// Parses `raw` as an enrollment QR payload and attempts enrollment.
/// Domain-mismatch (research D7) and single-use-token failures are caught
/// and mapped to a friendly message before any state changes — a
/// domain-mismatched payload never reaches `EdgeClient.enroll`'s network
/// call at all (`verifyClawDomainBeforeDial` throws first).
Future<EnrollmentOutcome> attemptEnrollmentFromQr(
  String raw, {
  required String memberId,
  required EdgeIdentity identity,
}) async {
  try {
    final payload = EnrollmentQrPayload.parse(raw);
    final client = await EdgeClient.enroll(payload, memberId: memberId, identity: identity);
    return EnrollmentSuccess(client, payload);
  } on ClawDomainMismatchException catch (e) {
    return EnrollmentFailure('This QR points at the wrong Border.\n${e.toString()}');
  } on EdgeClientException catch (e) {
    final msg = e.message.toLowerCase();
    return EnrollmentFailure(msg.contains('token')
        ? 'This enrollment code has expired or already been used — ask for a new QR code.'
        : 'Could not enroll: ${e.message}');
  } catch (e) {
    return EnrollmentFailure('Could not read that QR code: $e');
  }
}
