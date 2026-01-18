import 'package:flutter/material.dart';
import 'package:genui/genui.dart';
import 'package:json_schema_builder/json_schema_builder.dart';

import 'models/adk_schema.dart';
import 'theme/app_theme.dart';
import 'widgets/error_placeholder.dart';
import 'widgets/log_entries_viewer.dart';
import 'widgets/log_pattern_viewer.dart';
import 'widgets/metric_chart.dart';
import 'widgets/remediation_plan.dart';
import 'widgets/tool_log.dart';
import 'widgets/trace_waterfall.dart';
// Canvas widgets
import 'widgets/canvas/agent_activity_canvas.dart';
import 'widgets/canvas/service_topology_canvas.dart';
import 'widgets/canvas/incident_timeline_canvas.dart';
import 'widgets/canvas/metrics_dashboard_canvas.dart';
import 'widgets/canvas/ai_reasoning_canvas.dart';

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
        CatalogItem(
          name: "x-sre-log-entries-viewer",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = context.data as Map<String, dynamic>;
              final logData = LogEntriesData.fromJson(Map<String, dynamic>.from(data));
              return _buildWidgetContainer(
                child: LogEntriesViewer(data: logData),
                height: 500,
              );
            } catch (e) {
              return ErrorPlaceholder(error: e);
            }
          },
        ),
        CatalogItem(
          name: "x-sre-tool-log",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = context.data as Map<String, dynamic>;
              final log = ToolLog.fromJson(Map<String, dynamic>.from(data));
              return ToolLogWidget(log: log);
            } catch (e) {
              return ErrorPlaceholder(error: e);
            }
          },
        ),
        // Canvas Widgets
        CatalogItem(
          name: "x-sre-agent-activity",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = context.data as Map<String, dynamic>;
              final activityData = AgentActivityData.fromJson(Map<String, dynamic>.from(data));
              return _buildWidgetContainer(
                child: AgentActivityCanvas(data: activityData),
                height: 450,
              );
            } catch (e) {
              return ErrorPlaceholder(error: e);
            }
          },
        ),
        CatalogItem(
          name: "x-sre-service-topology",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = context.data as Map<String, dynamic>;
              final topologyData = ServiceTopologyData.fromJson(Map<String, dynamic>.from(data));
              return _buildWidgetContainer(
                child: ServiceTopologyCanvas(data: topologyData),
                height: 500,
              );
            } catch (e) {
              return ErrorPlaceholder(error: e);
            }
          },
        ),
        CatalogItem(
          name: "x-sre-incident-timeline",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = context.data as Map<String, dynamic>;
              final timelineData = IncidentTimelineData.fromJson(Map<String, dynamic>.from(data));
              return _buildWidgetContainer(
                child: IncidentTimelineCanvas(data: timelineData),
                height: 420,
              );
            } catch (e) {
              return ErrorPlaceholder(error: e);
            }
          },
        ),
        CatalogItem(
          name: "x-sre-metrics-dashboard",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = context.data as Map<String, dynamic>;
              final dashboardData = MetricsDashboardData.fromJson(Map<String, dynamic>.from(data));
              return _buildWidgetContainer(
                child: MetricsDashboardCanvas(data: dashboardData),
                height: 400,
              );
            } catch (e) {
              return ErrorPlaceholder(error: e);
            }
          },
        ),
        CatalogItem(
          name: "x-sre-ai-reasoning",
          dataSchema: S.object(),
          widgetBuilder: (context) {
            try {
              final data = context.data as Map<String, dynamic>;
              final reasoningData = AIReasoningData.fromJson(Map<String, dynamic>.from(data));
              return _buildWidgetContainer(
                child: AIReasoningCanvas(data: reasoningData),
                height: 480,
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
