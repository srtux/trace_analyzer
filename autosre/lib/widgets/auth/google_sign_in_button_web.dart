import 'package:flutter/material.dart';
import 'package:google_sign_in_web/web_only.dart' as web;

Widget buildGoogleSignInButton({required VoidCallback onMobileSignIn}) {
  return Container(
    constraints: const BoxConstraints(maxWidth: 400, maxHeight: 50),
    child: web.renderButton(
      configuration: web.GSIButtonConfiguration(
        type: web.GSIButtonType.standard,
        theme: web.GSIButtonTheme.filledBlue,
        size: web.GSIButtonSize.large,
        text: web.GSIButtonText.signinWith,
        shape: web.GSIButtonShape.pill,
      ),
    ),
  );
}
