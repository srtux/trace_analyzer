import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'auth_service.dart';

/// Model representing a GCP project.
class GcpProject {
  final String projectId;
  final String? displayName;
  final String? projectNumber;

  const GcpProject({
    required this.projectId,
    this.displayName,
    this.projectNumber,
  });

  factory GcpProject.fromJson(Map<String, dynamic> json) {
    return GcpProject(
      projectId: json['project_id'] as String,
      displayName: json['display_name'] as String?,
      projectNumber: json['project_number'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'project_id': projectId,
    if (displayName != null) 'display_name': displayName,
    if (projectNumber != null) 'project_number': projectNumber,
  };

  /// Returns display name if available, otherwise project ID.
  String get name => displayName ?? projectId;
}

/// Service for managing GCP project selection and fetching.
class ProjectService {
  static final ProjectService _instance = ProjectService._internal();
  factory ProjectService() => _instance;
  ProjectService._internal();

  /// HTTP request timeout duration.
  static const Duration _requestTimeout = Duration(seconds: 30);

  /// Returns the base API URL based on the runtime environment.
  String get _baseUrl {
    if (kDebugMode) {
      return 'http://127.0.0.1:8001';
    }
    return '';
  }

  /// Returns the projects API URL based on the runtime environment.
  String get _projectsUrl => '$_baseUrl/api/tools/projects/list';

  /// Returns the preferences API URL.
  String get _preferencesUrl => '$_baseUrl/api/preferences/project';

  final ValueNotifier<List<GcpProject>> _projects = ValueNotifier([]);
  final ValueNotifier<GcpProject?> _selectedProject = ValueNotifier(null);
  final ValueNotifier<bool> _isLoading = ValueNotifier(false);
  final ValueNotifier<String?> _error = ValueNotifier(null);

  /// List of available projects.
  ValueListenable<List<GcpProject>> get projects => _projects;

  /// Currently selected project.
  ValueListenable<GcpProject?> get selectedProject => _selectedProject;

  /// Whether projects are currently being loaded.
  ValueListenable<bool> get isLoading => _isLoading;

  /// Error message if project fetch failed.
  ValueListenable<String?> get error => _error;

  /// The selected project ID, or null if none selected.
  String? get selectedProjectId => _selectedProject.value?.projectId;

  /// Loads the previously selected project from backend storage.
  Future<void> loadSavedProject() async {
    try {
      final client = await AuthService().getAuthenticatedClient();
      final response = await client.get(
        Uri.parse(_preferencesUrl),
      ).timeout(_requestTimeout);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final savedProjectId = data['project_id'] as String?;

        if (savedProjectId != null && savedProjectId.isNotEmpty) {
          // Find in projects list or create new
          final project = _projects.value.firstWhere(
            (p) => p.projectId == savedProjectId,
            orElse: () => GcpProject(projectId: savedProjectId),
          );
          _selectedProject.value = project;
          debugPrint('Loaded saved project: $savedProjectId');
        }
      }
    } catch (e) {
      debugPrint('Error loading saved project: $e');
    }
  }

  /// Saves the selected project to backend storage.
  Future<void> _saveSelectedProject(String projectId) async {
    try {
      final client = await AuthService().getAuthenticatedClient();
      await client.post(
        Uri.parse(_preferencesUrl),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'project_id': projectId}),
      ).timeout(_requestTimeout);
      debugPrint('Saved project selection: $projectId');
    } catch (e) {
      debugPrint('Error saving project selection: $e');
    }
  }

  /// Fetches the list of available GCP projects from the backend.
  Future<void> fetchProjects() async {
    if (_isLoading.value) return;

    _isLoading.value = true;
    _error.value = null;

    try {
      final client = await AuthService().getAuthenticatedClient();
      final response = await client.get(Uri.parse(_projectsUrl)).timeout(_requestTimeout);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        // Handle different response formats
        List<dynamic> projectList;
        if (data is List) {
          projectList = data;
        } else if (data is Map && data['projects'] != null) {
          projectList = data['projects'] as List;
        } else {
          projectList = [];
        }

        final projects = projectList
            .map((p) => GcpProject.fromJson(p as Map<String, dynamic>))
            .toList();

        _projects.value = projects;

        // Load saved project preference first
        await loadSavedProject();

        // Auto-select first project if still none selected
        if (_selectedProject.value == null && projects.isNotEmpty) {
          selectProjectInstance(projects.first);
        }
      } else {
        _error.value = 'Failed to fetch projects: ${response.statusCode}';
      }
    } catch (e) {
      _error.value = 'Error fetching projects: $e';
      debugPrint('ProjectService error: $e');
    } finally {
      _isLoading.value = false;
    }
  }

  /// Selects a project by its ID.
  void selectProject(String projectId) {
    final project = _projects.value.firstWhere(
      (p) => p.projectId == projectId,
      orElse: () => GcpProject(projectId: projectId),
    );
    selectProjectInstance(project);
  }

  /// Selects a project directly.
  void selectProjectInstance(GcpProject? project) {
    _selectedProject.value = project;
    // Persist selection
    if (project != null) {
      _saveSelectedProject(project.projectId);
    }
  }

  /// Clears the current selection.
  void clearSelection() {
    _selectedProject.value = null;
  }

  void dispose() {
    _projects.dispose();
    _selectedProject.dispose();
    _isLoading.dispose();
    _error.dispose();
  }
}
