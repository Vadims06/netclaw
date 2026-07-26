import 'package:flutter/material.dart';

import '../ncfed/capability_registration.dart';

/// Per-type capture toggles (feature 068, US3/T019/FR-007a) — disabling a
/// type here means the Border can never even discover it as a possibility,
/// not merely have a request for it refused.
class SettingsScreen extends StatefulWidget {
  final CapabilityRegistration capabilities;

  const SettingsScreen({super.key, required this.capabilities});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  static const _labels = {
    'camera.capture': 'Photo capture',
    'camera.record_video': 'Video capture',
    'audio.record': 'Audio recording',
  };

  String? _error;

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        if (_error != null)
          Container(
            width: double.infinity,
            color: Colors.red.shade50,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Text(_error!, style: TextStyle(color: Colors.red.shade900)),
          ),
        for (final capability in kAllCaptureCapabilities)
          SwitchListTile(
            title: Text(_labels[capability] ?? capability),
            subtitle: const Text('The Border can request this while disconnected too'),
            value: widget.capabilities.enabled.contains(capability),
            onChanged: (value) async {
              setState(() => _error = null);
              try {
                await widget.capabilities.setEnabled(capability, value);
              } catch (e) {
                if (mounted) setState(() => _error = 'Could not update: $e');
              }
              if (mounted) setState(() {});
            },
          ),
      ],
    );
  }
}
