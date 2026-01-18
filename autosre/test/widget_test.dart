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
    // Set a fixed size to ensure desktop layout and visibility of elements
    tester.view.physicalSize = const Size(1280, 720);
    tester.view.devicePixelRatio = 1.0;

    // Build our app and trigger a frame.
    await tester.pumpWidget(const SreNexusApp());
    await tester.pumpAndSettle();

    // Verify Login Page is shown
    expect(find.text('Welcome to AutoSRE'), findsOneWidget);

    // Verify logo icon
    expect(find.byIcon(Icons.smart_toy), findsOneWidget);

    // Verify Sign In button
    expect(find.text('Sign in with Google'), findsOneWidget);

    // Clear size override
    addTearDown(tester.view.resetPhysicalSize);
  });
}
