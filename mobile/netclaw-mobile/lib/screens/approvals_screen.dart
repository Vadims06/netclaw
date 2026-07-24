import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';

import '../ncfed/approval_client.dart';
import 'empty_state.dart';

/// Pending approvals with biometric approve/deny (feature 068, US1/T010).
/// `n2n/edge/approval_resolve` is sent ONLY after `LocalAuthentication.
/// authenticate()` succeeds — a failed, cancelled, or unavailable biometric
/// attempt never calls `resolve()` at all (FR-002). This screen is the ONLY
/// place biometric code (`local_auth`) exists in this app — it never
/// imports `EdgeIdentity` or anything Keystore/Secure-Enclave-related
/// (research D7/FR-003).
class ApprovalsScreen extends StatefulWidget {
  final ApprovalClient approvalClient;
  final Future<bool> Function(String reason)? authenticate;

  const ApprovalsScreen({super.key, required this.approvalClient, this.authenticate});

  @override
  State<ApprovalsScreen> createState() => _ApprovalsScreenState();
}

class _ApprovalsScreenState extends State<ApprovalsScreen> {
  List<PendingApproval> _approvals = [];

  @override
  void initState() {
    super.initState();
    _approvals = widget.approvalClient.currentPending;
    widget.approvalClient.pending.listen((list) {
      if (mounted) setState(() => _approvals = list);
    });
  }

  Future<void> _resolve(PendingApproval approval, String action) async {
    final reason = action == 'approve'
        ? 'Confirm approval of ${approval.targetName}'
        : 'Confirm denial of ${approval.targetName}';
    final authenticate = widget.authenticate ??
        (String r) => LocalAuthentication().authenticate(localizedReason: r);
    final authenticated = await authenticate(reason);
    if (!authenticated) return; // failed/cancelled/unavailable -- send nothing (FR-002)
    await widget.approvalClient.resolve(approval.approvalId, action);
  }

  @override
  Widget build(BuildContext context) {
    if (_approvals.isEmpty) {
      return const EmptyState(
        asset: 'assets/illustrations/empty_approvals.png',
        text: 'No pending approvals.',
      );
    }
    return ListView.builder(
      itemCount: _approvals.length,
      itemBuilder: (context, index) {
        final approval = _approvals[index];
        return Card(
          margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${approval.targetType}: ${approval.targetName}',
                    style: const TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                Text('Requested by ${approval.requestingAgent}'
                    '${approval.riskName != null ? " (${approval.riskName})" : ""}'),
                const SizedBox(height: 8),
                Row(
                  children: [
                    ElevatedButton(
                      onPressed: () => _resolve(approval, 'approve'),
                      child: const Text('Approve'),
                    ),
                    const SizedBox(width: 8),
                    OutlinedButton(
                      onPressed: () => _resolve(approval, 'deny'),
                      child: const Text('Deny'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
