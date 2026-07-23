import 'package:flutter_test/flutter_test.dart';

import 'package:netclaw_mobile/main.dart';

void main() {
  testWidgets('App starts on the enrollment screen', (WidgetTester tester) async {
    await tester.pumpWidget(const NetClawMobileApp());
    await tester.pump();

    expect(find.text('Scan Border QR Code'), findsOneWidget);
  });
}
