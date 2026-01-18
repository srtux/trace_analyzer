import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

Widget buildGoogleSignInButton({required VoidCallback onMobileSignIn}) {
  return Material(
    color: Colors.transparent,
    child: InkWell(
      onTap: onMobileSignIn,
      borderRadius: BorderRadius.circular(28),
      child: Container(
        constraints: const BoxConstraints(minWidth: 280),
        padding: const EdgeInsets.symmetric(
          horizontal: 24,
          vertical: 16,
        ),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(28),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.2),
              blurRadius: 8,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Image.network(
              'https://upload.wikimedia.org/wikipedia/commons/5/53/Google_%22G%22_Logo.svg',
              height: 24,
              width: 24,
              errorBuilder: (c, o, s) => const Icon(Icons.login, color: Colors.blue),
            ),
            const SizedBox(width: 12),
            Text(
              'Sign in with Google',
              style: GoogleFonts.roboto(
                fontSize: 16,
                fontWeight: FontWeight.w500,
                color: Colors.black87,
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
