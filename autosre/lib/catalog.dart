import 'package:flutter/material.dart';
import 'package:genui/genui.dart';
import 'package:json_schema_builder/json_schema_builder.dart';

import 'models/adk_schema.dart';
import 'theme/app_theme.dart';
import 'widgets/error_placeholder.dart';
import 'widgets/log_pattern_viewer.dart';
import 'widgets/metric_chart.dart';
import 'widgets/remediation_plan.dart';
import 'widgets/tool_log.dart';
import 'widgets/trace_waterfall.dart';

/// Custom error class for data validation failures
class DataValidationError implements Exception {
  final String component;
  final String expectedType;
  final String actualType;
  final String? details;

  DataValidationError({
    required this.component,
    required this.expectedType,
    required this.actualType,
    this.details,
  });

  @override
  String toString() {
    var msg = 'DataValidationError for $component:\n'
        'Expected: $expectedType\n'
        'Received: $actualType';
    if (details != null) {
      msg += '\nDetails: $details';
    }
    return msg;
  }
}

/// Registry for all SRE-specific UI components.
class CatalogRegistry {
  /// Safely cast data to Map<String, dynamic> with validation
  static Map<String, dynamic> _asMap(dynamic data, String componentName) {
    if (data == null) {
      throw DataValidationError(
        component: componentName,
        expectedType: 'Map<String, dynamic>',
        actualType: 'null',
        details: 'Received null data from backend',
      );
    }
    if (data is Map<String, dynamic>) {
      return data;
    }
    if (data is Map) {
      return Map<String, dynamic>.from(data);
    }
    throw DataValidationError(
      component: componentName,
      expectedType: 'Map<String, dynamic>',
      actualType: data.runtimeType.toString(),
      details: 'Data preview: ${data.toString().substring(0, data.toString().length > 100 ? 100 : data.toString().length)}...',
    );
  }

  /// Safely cast data to List<dynamic> with validation
  static List<dynamic> _asList(dynamic data, String componentName) {
    if (data == null) {
      throw DataValidationError(
        component: componentName,
        expectedType: 'List<dynamic>',
        actualType: 'null',
        details: 'Received null data from backend',
      );
    }
    if (data is List<dynamic>) {
      return data;
    }
    throw DataValidationError(
      component: componentName,
      expectedType: 'List<dynamic>',
      actualType: data.runtimeType.toString(),
      details: 'Data preview: ${data.toString().substring(0, data.toString().length > 100 ? 100 : data.toString().length)}...',
    );
  }

  static Catalog createSreCatalog() {
    return Catalog(
      [
        CatalogItem(
          name: "x-sre-trace-waterfall",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = _asMap(context.data, 'x-sre-trace-waterfall');
              final trace = Trace.fromJson(data);
              return _buildWidgetContainer(
                child: TraceWaterfall(trace: trace),
                height: 380,
              );
            } catch (e, stackTrace) {
              return ErrorPlaceholder(error: e, stackTrace: stackTrace);
            }
          },
        ),
        CatalogItem(
          name: "x-sre-metric-chart",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = _asMap(context.data, 'x-sre-metric-chart');
              final series = MetricSeries.fromJson(data);
              return _buildWidgetContainer(
                child: MetricCorrelationChart(series: series),
                height: 380,
              );
            } catch (e, stackTrace) {
              return ErrorPlaceholder(error: e, stackTrace: stackTrace);
            }
          },
        ),
        CatalogItem(
          name: "x-sre-remediation-plan",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = _asMap(context.data, 'x-sre-remediation-plan');
              final plan = RemediationPlan.fromJson(data);
              return _buildWidgetContainer(
                child: RemediationPlanWidget(plan: plan),
                height: null, // Auto height based on content
                minHeight: 200,
              );
            } catch (e, stackTrace) {
              return ErrorPlaceholder(error: e, stackTrace: stackTrace);
            }
          },
        ),
        CatalogItem(
          name: "x-sre-log-pattern-viewer",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = _asList(context.data, 'x-sre-log-pattern-viewer');
              final patterns = data
                  .map((item) => LogPattern.fromJson(_asMap(item, 'LogPattern item')))
                  .toList();
              return _buildWidgetContainer(
                child: LogPatternViewer(patterns: patterns),
                height: 450,
              );
            } catch (e, stackTrace) {
              return ErrorPlaceholder(error: e, stackTrace: stackTrace);
            }
          },
        ),
        CatalogItem(
          name: "x-sre-tool-log",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = _asMap(context.data, 'x-sre-tool-log');
              final log = ToolLog.fromJson(data);
              return ToolLogWidget(log: log);
            } catch (e, stackTrace) {
              return ErrorPlaceholder(error: e, stackTrace: stackTrace);
            }
          },
        ),
      ],
      catalogId: "sre-catalog",
    );
  }

  /// Builds a styled container for widgets with consistent theming
  static Widget _buildWidgetContainer({
    required Widget child,
    double? height,
    double? minHeight,
  }) {
    return Container(
      height: height,
      constraints: minHeight != null
          ? BoxConstraints(minHeight: minHeight)
          : null,
      decoration: BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: AppColors.surfaceBorder,
          width: 1,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.2),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: child,
    );
  }
}
