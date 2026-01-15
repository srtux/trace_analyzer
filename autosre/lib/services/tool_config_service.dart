import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

/// Categories of tools based on their functionality.
enum ToolCategory {
  apiClient('api_client', 'API Client', 'Direct GCP API clients'),
  mcp('mcp', 'MCP', 'Model Context Protocol tools'),
  analysis('analysis', 'Analysis', 'Analysis and processing tools'),
  orchestration('orchestration', 'Orchestration', 'Orchestration tools'),
  discovery('discovery', 'Discovery', 'Discovery tools'),
  remediation('remediation', 'Remediation', 'Remediation tools'),
  gke('gke', 'GKE', 'GKE/Kubernetes tools'),
  slo('slo', 'SLO', 'SLO/SLI tools');

  const ToolCategory(this.value, this.displayName, this.description);

  final String value;
  final String displayName;
  final String description;

  static ToolCategory? fromValue(String value) {
    for (final category in ToolCategory.values) {
      if (category.value == value) {
        return category;
      }
    }
    return null;
  }
}

/// Status of tool connectivity test.
enum ToolTestStatus {
  success('success'),
  failed('failed'),
  timeout('timeout'),
  notTested('not_tested'),
  notTestable('not_testable');

  const ToolTestStatus(this.value);

  final String value;

  static ToolTestStatus fromValue(String value) {
    for (final status in ToolTestStatus.values) {
      if (status.value == value) {
        return status;
      }
    }
    return ToolTestStatus.notTested;
  }
}

/// Result of a tool connectivity test.
class ToolTestResult {
  final ToolTestStatus status;
  final String message;
  final double? latencyMs;
  final String? timestamp;
  final Map<String, dynamic> details;

  const ToolTestResult({
    required this.status,
    required this.message,
    this.latencyMs,
    this.timestamp,
    this.details = const {},
  });

  factory ToolTestResult.fromJson(Map<String, dynamic> json) {
    return ToolTestResult(
      status: ToolTestStatus.fromValue(json['status'] as String? ?? 'not_tested'),
      message: json['message'] as String? ?? '',
      latencyMs: (json['latency_ms'] as num?)?.toDouble(),
      timestamp: json['timestamp'] as String?,
      details: json['details'] as Map<String, dynamic>? ?? {},
    );
  }
}

/// Configuration for a single tool.
class ToolConfig {
  final String name;
  final String displayName;
  final String description;
  final ToolCategory category;
  final bool enabled;
  final bool testable;
  final ToolTestResult? lastTestResult;

  const ToolConfig({
    required this.name,
    required this.displayName,
    required this.description,
    required this.category,
    required this.enabled,
    required this.testable,
    this.lastTestResult,
  });

  factory ToolConfig.fromJson(Map<String, dynamic> json) {
    ToolTestResult? lastTest;
    if (json['last_test_result'] != null) {
      lastTest = ToolTestResult.fromJson(
        json['last_test_result'] as Map<String, dynamic>,
      );
    }

    return ToolConfig(
      name: json['name'] as String,
      displayName: json['display_name'] as String,
      description: json['description'] as String,
      category: ToolCategory.fromValue(json['category'] as String) ?? ToolCategory.analysis,
      enabled: json['enabled'] as bool? ?? true,
      testable: json['testable'] as bool? ?? false,
      lastTestResult: lastTest,
    );
  }

  ToolConfig copyWith({
    String? name,
    String? displayName,
    String? description,
    ToolCategory? category,
    bool? enabled,
    bool? testable,
    ToolTestResult? lastTestResult,
  }) {
    return ToolConfig(
      name: name ?? this.name,
      displayName: displayName ?? this.displayName,
      description: description ?? this.description,
      category: category ?? this.category,
      enabled: enabled ?? this.enabled,
      testable: testable ?? this.testable,
      lastTestResult: lastTestResult ?? this.lastTestResult,
    );
  }
}

/// Summary statistics for tool configuration.
class ToolConfigSummary {
  final int total;
  final int enabled;
  final int disabled;
  final int testable;

  const ToolConfigSummary({
    required this.total,
    required this.enabled,
    required this.disabled,
    required this.testable,
  });

  factory ToolConfigSummary.fromJson(Map<String, dynamic> json) {
    return ToolConfigSummary(
      total: json['total'] as int? ?? 0,
      enabled: json['enabled'] as int? ?? 0,
      disabled: json['disabled'] as int? ?? 0,
      testable: json['testable'] as int? ?? 0,
    );
  }
}

/// Service for managing tool configuration.
class ToolConfigService {
  static final ToolConfigService _instance = ToolConfigService._internal();
  factory ToolConfigService() => _instance;
  ToolConfigService._internal();

  /// Returns the API base URL based on the runtime environment.
  String get _baseUrl {
    if (kDebugMode) {
      return 'http://127.0.0.1:8001';
    }
    return '';
  }

  final ValueNotifier<Map<ToolCategory, List<ToolConfig>>> _toolsByCategory =
      ValueNotifier({});
  final ValueNotifier<ToolConfigSummary?> _summary = ValueNotifier(null);
  final ValueNotifier<bool> _isLoading = ValueNotifier(false);
  final ValueNotifier<String?> _error = ValueNotifier(null);
  final ValueNotifier<Set<String>> _testingTools = ValueNotifier({});

  /// Tools grouped by category.
  ValueListenable<Map<ToolCategory, List<ToolConfig>>> get toolsByCategory =>
      _toolsByCategory;

  /// Configuration summary.
  ValueListenable<ToolConfigSummary?> get summary => _summary;

  /// Whether data is currently being loaded.
  ValueListenable<bool> get isLoading => _isLoading;

  /// Error message if fetch failed.
  ValueListenable<String?> get error => _error;

  /// Set of tool names currently being tested.
  ValueListenable<Set<String>> get testingTools => _testingTools;

  /// Fetches all tool configurations from the backend.
  Future<void> fetchConfigs() async {
    if (_isLoading.value) return;

    _isLoading.value = true;
    _error.value = null;

    try {
      final response = await http.get(
        Uri.parse('$_baseUrl/api/tools/config'),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final toolsMap = data['tools'] as Map<String, dynamic>? ?? {};
        final summaryData = data['summary'] as Map<String, dynamic>?;

        // Parse tools grouped by category
        final Map<ToolCategory, List<ToolConfig>> grouped = {};
        for (final entry in toolsMap.entries) {
          final category = ToolCategory.fromValue(entry.key);
          if (category != null) {
            final tools = (entry.value as List<dynamic>)
                .map((t) => ToolConfig.fromJson(t as Map<String, dynamic>))
                .toList();
            grouped[category] = tools;
          }
        }

        _toolsByCategory.value = grouped;

        if (summaryData != null) {
          _summary.value = ToolConfigSummary.fromJson(summaryData);
        }
      } else {
        _error.value = 'Failed to fetch tool configs: ${response.statusCode}';
      }
    } catch (e) {
      _error.value = 'Error fetching tool configs: $e';
      debugPrint('ToolConfigService error: $e');
    } finally {
      _isLoading.value = false;
    }
  }

  /// Updates the enabled status of a tool.
  Future<bool> setToolEnabled(String toolName, bool enabled) async {
    try {
      final response = await http.put(
        Uri.parse('$_baseUrl/api/tools/config/$toolName'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'enabled': enabled}),
      );

      if (response.statusCode == 200) {
        // Update local state
        final updatedMap = Map<ToolCategory, List<ToolConfig>>.from(
          _toolsByCategory.value,
        );

        for (final category in updatedMap.keys) {
          final tools = updatedMap[category]!;
          final index = tools.indexWhere((t) => t.name == toolName);
          if (index != -1) {
            final updatedTools = List<ToolConfig>.from(tools);
            updatedTools[index] = tools[index].copyWith(enabled: enabled);
            updatedMap[category] = updatedTools;
            break;
          }
        }

        _toolsByCategory.value = updatedMap;

        // Update summary
        if (_summary.value != null) {
          final currentSummary = _summary.value!;
          _summary.value = ToolConfigSummary(
            total: currentSummary.total,
            enabled: enabled
                ? currentSummary.enabled + 1
                : currentSummary.enabled - 1,
            disabled: enabled
                ? currentSummary.disabled - 1
                : currentSummary.disabled + 1,
            testable: currentSummary.testable,
          );
        }

        return true;
      } else {
        _error.value = 'Failed to update tool: ${response.statusCode}';
        return false;
      }
    } catch (e) {
      _error.value = 'Error updating tool: $e';
      debugPrint('ToolConfigService error: $e');
      return false;
    }
  }

  /// Tests a specific tool's connectivity.
  Future<ToolTestResult?> testTool(String toolName) async {
    // Mark tool as being tested
    _testingTools.value = {..._testingTools.value, toolName};

    try {
      final response = await http.post(
        Uri.parse('$_baseUrl/api/tools/test/$toolName'),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;

        if (data['testable'] == false) {
          return ToolTestResult(
            status: ToolTestStatus.notTestable,
            message: data['message'] as String? ?? 'Tool is not testable',
          );
        }

        final resultData = data['result'] as Map<String, dynamic>?;
        if (resultData != null) {
          final result = ToolTestResult.fromJson(resultData);

          // Update local state with test result
          _updateToolTestResult(toolName, result);

          return result;
        }
      }

      return ToolTestResult(
        status: ToolTestStatus.failed,
        message: 'Failed to test tool: ${response.statusCode}',
      );
    } catch (e) {
      debugPrint('ToolConfigService test error: $e');
      return ToolTestResult(
        status: ToolTestStatus.failed,
        message: 'Error testing tool: $e',
      );
    } finally {
      // Remove tool from testing set
      final updated = Set<String>.from(_testingTools.value);
      updated.remove(toolName);
      _testingTools.value = updated;
    }
  }

  /// Tests all testable tools.
  Future<Map<String, ToolTestResult>> testAllTools({
    ToolCategory? category,
  }) async {
    try {
      final uri = category != null
          ? Uri.parse('$_baseUrl/api/tools/test-all?category=${category.value}')
          : Uri.parse('$_baseUrl/api/tools/test-all');

      final response = await http.post(uri);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final results = data['results'] as Map<String, dynamic>? ?? {};

        final Map<String, ToolTestResult> parsedResults = {};
        for (final entry in results.entries) {
          final resultData = entry.value as Map<String, dynamic>;
          parsedResults[entry.key] = ToolTestResult.fromJson(resultData);
        }

        // Update local state with all test results
        for (final entry in parsedResults.entries) {
          _updateToolTestResult(entry.key, entry.value);
        }

        return parsedResults;
      }

      return {};
    } catch (e) {
      debugPrint('ToolConfigService test all error: $e');
      return {};
    }
  }

  /// Updates the local state with a tool's test result.
  void _updateToolTestResult(String toolName, ToolTestResult result) {
    final updatedMap = Map<ToolCategory, List<ToolConfig>>.from(
      _toolsByCategory.value,
    );

    for (final category in updatedMap.keys) {
      final tools = updatedMap[category]!;
      final index = tools.indexWhere((t) => t.name == toolName);
      if (index != -1) {
        final updatedTools = List<ToolConfig>.from(tools);
        updatedTools[index] = tools[index].copyWith(lastTestResult: result);
        updatedMap[category] = updatedTools;
        break;
      }
    }

    _toolsByCategory.value = updatedMap;
  }

  /// Bulk update tool configurations.
  Future<bool> bulkUpdateTools(Map<String, bool> updates) async {
    try {
      final response = await http.post(
        Uri.parse('$_baseUrl/api/tools/config/bulk'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(updates),
      );

      if (response.statusCode == 200) {
        // Refresh configs to get updated state
        await fetchConfigs();
        return true;
      }

      return false;
    } catch (e) {
      debugPrint('ToolConfigService bulk update error: $e');
      return false;
    }
  }

  /// Enable all tools in a category.
  Future<bool> enableCategory(ToolCategory category) async {
    final tools = _toolsByCategory.value[category] ?? [];
    final updates = <String, bool>{};
    for (final tool in tools) {
      updates[tool.name] = true;
    }
    return bulkUpdateTools(updates);
  }

  /// Disable all tools in a category.
  Future<bool> disableCategory(ToolCategory category) async {
    final tools = _toolsByCategory.value[category] ?? [];
    final updates = <String, bool>{};
    for (final tool in tools) {
      updates[tool.name] = false;
    }
    return bulkUpdateTools(updates);
  }

  void dispose() {
    _toolsByCategory.dispose();
    _summary.dispose();
    _isLoading.dispose();
    _error.dispose();
    _testingTools.dispose();
  }
}
