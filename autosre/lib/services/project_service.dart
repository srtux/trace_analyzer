import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

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

  /// Returns display name if available, otherwise project ID.
  String get name => displayName ?? projectId;
}

/// Service for managing GCP project selection and fetching.
class ProjectService {
  static final ProjectService _instance = ProjectService._internal();
  factory ProjectService() => _instance;
  ProjectService._internal();

  final String _projectsUrl = 'http://127.0.0.1:8001/api/tools/projects/list';

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

  /// Fetches the list of available GCP projects from the backend.
  Future<void> fetchProjects() async {
    if (_isLoading.value) return;

    _isLoading.value = true;
    _error.value = null;

    try {
      final response = await http.get(Uri.parse(_projectsUrl));

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

        // Auto-select first project if none selected
        if (_selectedProject.value == null && projects.isNotEmpty) {
          _selectedProject.value = projects.first;
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
    _selectedProject.value = project;
  }

  /// Selects a project directly.
  void selectProjectInstance(GcpProject? project) {
    _selectedProject.value = project;
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
