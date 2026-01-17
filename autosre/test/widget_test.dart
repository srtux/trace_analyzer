// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:autosre/app.dart';

void main() {
  testWidgets('App renders correctly', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const SreNexusApp());

    // Verify that our title is present.
    expect(find.text('AutoSRE'), findsOneWidget);

    // Verify input hint is present
    expect(find.text('Ask a question...'), findsOneWidget);

    // Verify send button is present
    expect(find.byIcon(Icons.arrow_upward_rounded), findsOneWidget);

    // Trigger disposal to clean up timers
    await tester.pumpWidget(const SizedBox());
  });
}
