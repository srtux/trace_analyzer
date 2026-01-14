import 'package:flutter/material.dart';
import 'package:genui/genui.dart';
import 'package:json_schema_builder/json_schema_builder.dart';

import 'models/adk_schema.dart';
import 'theme/app_theme.dart';
import 'widgets/error_placeholder.dart';
import 'widgets/log_pattern_viewer.dart';
import 'widgets/metric_chart.dart';
import 'widgets/remediation_plan.dart';
import 'widgets/trace_waterfall.dart';

/// Registry for all SRE-specific UI components.
class CatalogRegistry {
  static Catalog createSreCatalog() {
    return Catalog(
      [
        CatalogItem(
          name: "x-sre-trace-waterfall",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = context.data as Map<String, dynamic>;
              final trace = Trace.fromJson(Map<String, dynamic>.from(data));
              return _buildWidgetContainer(
                child: TraceWaterfall(trace: trace),
                height: 380,
              );
            } catch (e) {
              return ErrorPlaceholder(error: e);
            }
          },
        ),
        CatalogItem(
          name: "x-sre-metric-chart",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = context.data as Map<String, dynamic>;
              final series = MetricSeries.fromJson(Map<String, dynamic>.from(data));
              return _buildWidgetContainer(
                child: MetricCorrelationChart(series: series),
                height: 380,
              );
            } catch (e) {
              return ErrorPlaceholder(error: e);
            }
          },
        ),
        CatalogItem(
          name: "x-sre-remediation-plan",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = context.data as Map<String, dynamic>;
              final plan = RemediationPlan.fromJson(Map<String, dynamic>.from(data));
              return _buildWidgetContainer(
                child: RemediationPlanWidget(plan: plan),
                height: null, // Auto height based on content
                minHeight: 200,
              );
            } catch (e) {
              return ErrorPlaceholder(error: e);
            }
          },
        ),
        CatalogItem(
          name: "x-sre-log-pattern-viewer",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = context.data as List<dynamic>;
              final patterns = data
                  .map((item) => LogPattern.fromJson(Map<String, dynamic>.from(item)))
                  .toList();
              return _buildWidgetContainer(
                child: LogPatternViewer(patterns: patterns),
                height: 450,
              );
            } catch (e) {
              return ErrorPlaceholder(error: e);
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
