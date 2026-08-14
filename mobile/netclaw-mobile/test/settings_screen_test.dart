import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:netclaw_mobile/ncfed/capability_registration.dart';
import 'package:netclaw_mobile/ncfed/edge_client.dart';
import 'package:netclaw_mobile/screens/settings_screen.dart';

class _RecordingEdgeRpcSource implements EdgeRpcSource {
  @override
  void on(String method, EdgeMethodHandler handler) {}

  @override
  Future<Map<String, dynamic>> call(String method, Map<String, dynamic> params,
      {Duration timeout = const Duration(seconds: 30)}) async {
    return {'registered': true};
  }
}

void main() {
  Widget wrap(Widget child) => MaterialApp(home: Scaffold(body: child));

  group('Remove this device (105/US2/FR-003-FR-006)', () {
    testWidgets('the control is visible', (tester) async {
      var removed = false;
      await tester.pumpWidget(wrap(SettingsScreen(
        capabilities: CapabilityRegistration(_RecordingEdgeRpcSource()),
        onRemoveDevice: () async => removed = true,
        authenticate: (reason) async => true,
      )));

      expect(find.text('Remove this device'), findsOneWidget);
      expect(removed, isFalse);
    });

    testWidgets(
        'FR-004/FR-005: successful biometric re-authentication clears the enrollment',
        (tester) async {
      var removed = false;
      String? reasonGiven;
      await tester.pumpWidget(wrap(SettingsScreen(
        capabilities: CapabilityRegistration(_RecordingEdgeRpcSource()),
        onRemoveDevice: () async => removed = true,
        authenticate: (reason) async {
          reasonGiven = reason;
          return true;
        },
      )));

      await tester.tap(find.text('Remove this device'));
      await tester.pumpAndSettle();

      expect(removed, isTrue);
      expect(reasonGiven, isNotNull);
    });

    testWidgets('a cancelled/failed biometric attempt leaves the enrollment untouched',
        (tester) async {
      var removed = false;
      await tester.pumpWidget(wrap(SettingsScreen(
        capabilities: CapabilityRegistration(_RecordingEdgeRpcSource()),
        onRemoveDevice: () async => removed = true,
        authenticate: (reason) async => false,
      )));

      await tester.tap(find.text('Remove this device'));
      await tester.pumpAndSettle();

      expect(removed, isFalse);
    });

    testWidgets('an authentication error (e.g. biometric unavailable) also leaves it untouched',
        (tester) async {
      var removed = false;
      await tester.pumpWidget(wrap(SettingsScreen(
        capabilities: CapabilityRegistration(_RecordingEdgeRpcSource()),
        onRemoveDevice: () async => removed = true,
        authenticate: (reason) async => throw Exception('no biometric enrolled'),
      )));

      await tester.tap(find.text('Remove this device'));
      await tester.pumpAndSettle();

      expect(removed, isFalse);
    });

    testWidgets('the action never fires without going through authenticate at all', (tester) async {
      var authenticateCalled = false;
      var removed = false;
      await tester.pumpWidget(wrap(SettingsScreen(
        capabilities: CapabilityRegistration(_RecordingEdgeRpcSource()),
        onRemoveDevice: () async => removed = true,
        authenticate: (reason) async {
          authenticateCalled = true;
          return true;
        },
      )));

      await tester.tap(find.text('Remove this device'));
      await tester.pumpAndSettle();

      expect(authenticateCalled, isTrue);
      expect(removed, isTrue);
    });

    testWidgets(
        'FR-006: removal succeeds with no live Border/EdgeClient connection involved at all',
        (tester) async {
      // onRemoveDevice here has no EdgeClient/network access whatsoever --
      // proving structurally that this path cannot depend on a live
      // connection, since it isn't given one to depend on.
      var removed = false;
      await tester.pumpWidget(wrap(SettingsScreen(
        capabilities: CapabilityRegistration(_RecordingEdgeRpcSource()),
        onRemoveDevice: () async => removed = true,
        authenticate: (reason) async => true,
      )));

      await tester.tap(find.text('Remove this device'));
      await tester.pumpAndSettle();

      expect(removed, isTrue);
    });
  });
}
