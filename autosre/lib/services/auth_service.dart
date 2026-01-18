import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart' as gsi;
import 'package:googleapis_auth/auth_io.dart';
import 'package:http/http.dart' as http;

/// Service to handle authentication with Google Sign-In
class AuthService extends ChangeNotifier {
  static final AuthService _instance = AuthService._internal();

  factory AuthService() {
    return _instance;
  }

  AuthService._internal();

  final gsi.GoogleSignIn _googleSignIn = gsi.GoogleSignIn.instance;
  final List<String> _scopes = [
    'email',
    'https://www.googleapis.com/auth/cloud-platform',
  ];

  gsi.GoogleSignInAccount? _currentUser;
  String? _idToken;
  String? _accessToken;
  bool _isLoading = true;

  gsi.GoogleSignInAccount? get currentUser => _currentUser;
  bool get isAuthenticated => _currentUser != null;
  bool get isLoading => _isLoading;
  String? get idToken => _idToken;
  String? get accessToken => _accessToken;

  /// Initialize auth state
  Future<void> init() async {
    // Listen to auth events
    _googleSignIn.authenticationEvents.listen((event) async {
      if (event is gsi.GoogleSignInAuthenticationEventSignIn) {
        _currentUser = event.user;
        await _refreshTokens();
      } else if (event is gsi.GoogleSignInAuthenticationEventSignOut) {
        _currentUser = null;
        _idToken = null;
        _accessToken = null;
      }
      notifyListeners();
    });

    try {
      // Initialize configuration (REQUIRED for Web to setup Client ID)
      await _googleSignIn.initialize();

      // Attempt silent sign-in
      // Note: On web, attemptLightweightAuthentication might fail or not be appropriate immediately
      // if not configured, but we wrap it.
      await _googleSignIn.attemptLightweightAuthentication();
    } catch (e) {
      // Ignore cancellation errors during silent sign-in
      if (e.toString().contains('canceled')) {
        debugPrint('Silent sign-in canceled (normal behavior if not logged in)');
      } else {
        debugPrint('Error initializing auth: $e');
      }
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Sign in with Google
  Future<void> signIn() async {
    try {
      await _googleSignIn.authenticate(scopeHint: _scopes);
    } catch (e) {
      debugPrint('Error signing in: $e');
      rethrow;
    }
  }

  /// Sign out
  Future<void> signOut() async {
    await _googleSignIn.signOut();
    // State clearing handled by event listener
    notifyListeners();
  }

  /// Refresh auth tokens
  Future<void> _refreshTokens() async {
    if (_currentUser == null) return;
    try {
      final auth = _currentUser!.authentication;
      _idToken = auth.idToken;
      // We need to request proper scopes if not granted?
      // For now assume basic token is enough or we use authorizeScopes if needed.
      // But getAuthenticatedClient handles access token.

      // Note: accessToken from authentication might be null if scopes weren't authorized securely?
      // In v7, we might need to use authorizationClient or something for scopes.
      // But let's see if authentication returns it.

      // Actually, authentication property on account (idToken) is for Identification.
      // For API access (scopes), we need Authorization.

    } catch (e) {
      debugPrint('Error refreshing tokens: $e');
    }
  }

  /// Get authenticated HTTP client
  Future<http.Client> getAuthenticatedClient() async {
    if (_currentUser == null) {
      throw Exception('User not authenticated');
    }

    // In v7, we should check if we have authorization for scopes.
    // We can use the authorizationClient from the user.
    final authClient = _currentUser!.authorizationClient;
    final headers = await authClient.authorizationHeaders(_scopes);

    if (headers == null) {
       // Need to authorize
       try {
         await authClient.authorizeScopes(_scopes);
         // Try getting headers again
         final headers2 = await authClient.authorizationHeaders(_scopes);
         if (headers2 == null) throw Exception('Failed to authorize scopes');

           // Extract token from header 'Authorization': 'Bearer <token>'
         final authHeader = headers2['Authorization']!;
         final token = authHeader.split(' ').last;

         return authenticatedClient(
          http.Client(),
          AccessCredentials(
            AccessToken(
              'Bearer',
              token,
              DateTime.now().add(const Duration(hours: 1)).toUtc(),
            ),
            null, // refreshToken
            _scopes,
          ),
        );
       } catch (e) {
         throw Exception('Authorization failed: $e');
       }
    }

     // Use existing token
     final authHeader = headers['Authorization']!;
     final token = authHeader.split(' ').last;

    return authenticatedClient(
      http.Client(),
      AccessCredentials(
        AccessToken(
          'Bearer',
          token,
          DateTime.now().add(const Duration(hours: 1)).toUtc(),
        ),
        null, // refreshToken
        _scopes,
      ),
    );
  }
}
