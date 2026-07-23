import 'edge_client.dart';

/// The three capture capability names the Border understands (mirrors
/// `RiskManager.CAPTURE_CAPABILITY_NAMES` in `risk.py` exactly).
const List<String> kAllCaptureCapabilities = [
  'camera.capture',
  'camera.record_video',
  'audio.record',
];

/// Sends `n2n/edge/register_capabilities` at connect time and whenever the
/// operator changes a Settings toggle (feature 068, US3/T019) — a disabled
/// type is simply never included, making it invisible to the Border's
/// routing entirely (FR-007a), not merely refused.
class CapabilityRegistration {
  final EdgeRpcSource client;
  final Set<String> _enabled;

  CapabilityRegistration(this.client, {Set<String>? initiallyEnabled})
      : _enabled = initiallyEnabled ?? {...kAllCaptureCapabilities};

  Set<String> get enabled => Set.unmodifiable(_enabled);

  Future<void> register() async {
    await client.call('n2n/edge/register_capabilities', {
      'capabilities': _enabled.toList(),
    });
  }

  Future<void> setEnabled(String capability, bool isEnabled) async {
    if (isEnabled) {
      _enabled.add(capability);
    } else {
      _enabled.remove(capability);
    }
    await register();
  }
}
