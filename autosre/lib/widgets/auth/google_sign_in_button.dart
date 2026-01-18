import 'package:flutter/material.dart';

import 'google_sign_in_button_stub.dart'
    if (dart.library.js_interop) 'google_sign_in_button_web.dart'
    if (dart.library.io) 'google_sign_in_button_mobile.dart';

class GoogleSignInButton extends StatelessWidget {
  final VoidCallback onMobileSignIn;

  const GoogleSignInButton({super.key, required this.onMobileSignIn});

  @override
  Widget build(BuildContext context) {
    return buildGoogleSignInButton(onMobileSignIn: onMobileSignIn);
  }
}
