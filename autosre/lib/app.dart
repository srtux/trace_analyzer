import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'pages/conversation_page.dart';
import 'pages/login_page.dart';
import 'services/auth_service.dart';
import 'theme/app_theme.dart';

class SreNexusApp extends StatelessWidget {
  const SreNexusApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthService()..init()),
      ],
      child: MaterialApp(
        title: 'AutoSRE',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.darkTheme,
        home: const AuthWrapper(),
      ),
    );
  }
}

class AuthWrapper extends StatelessWidget {
  const AuthWrapper({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<AuthService>(
      builder: (context, auth, _) {
        if (auth.isLoading) {
          return const Scaffold(
            backgroundColor: AppColors.backgroundDark,
            body: Center(
              child: CircularProgressIndicator(
                color: AppColors.primaryTeal,
              ),
            ),
          );
        }

        if (!auth.isAuthenticated) {
          return const LoginPage();
        }

        return const ConversationPage();
      },
    );
  }
}
