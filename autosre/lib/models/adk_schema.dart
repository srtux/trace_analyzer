
class SpanInfo {
  final String spanId;
  final String traceId;
  final String name;
  final DateTime startTime;
  final DateTime endTime;
  final Map<String, dynamic> attributes;
  final String status; // 'OK', 'ERROR'
  final String? parentSpanId;

  SpanInfo({
    required this.spanId,
    required this.traceId,
    required this.name,
    required this.startTime,
    required this.endTime,
    required this.attributes,
    required this.status,
    this.parentSpanId,
  });

  Duration get duration => endTime.difference(startTime);

  factory SpanInfo.fromJson(Map<String, dynamic> json) {
    return SpanInfo(
      spanId: json['span_id'],
      traceId: json['trace_id'],
      name: json['name'],
      startTime: DateTime.parse(json['start_time']),
      endTime: DateTime.parse(json['end_time']),
      attributes: Map<String, dynamic>.from(json['attributes'] ?? {}),
      status: json['status'] ?? 'OK',
      parentSpanId: json['parent_span_id'],
    );
  }
}

class Trace {
  final String traceId;
  final List<SpanInfo> spans;

  Trace({required this.traceId, required this.spans});

  factory Trace.fromJson(Map<String, dynamic> json) {
    var list = json['spans'] as List;
    List<SpanInfo> spansList = list.map((i) => SpanInfo.fromJson(i)).toList();
    return Trace(traceId: json['trace_id'], spans: spansList);
  }
}

class MetricPoint {
  final DateTime timestamp;
  final double value;
  final bool isAnomaly;

  MetricPoint({required this.timestamp, required this.value, this.isAnomaly = false});

  factory MetricPoint.fromJson(Map<String, dynamic> json) {
    return MetricPoint(
      timestamp: DateTime.parse(json['timestamp']),
      value: (json['value'] as num).toDouble(),
      isAnomaly: json['is_anomaly'] ?? false,
    );
  }
}

class MetricSeries {
    final String metricName;
    final List<MetricPoint> points;
    final Map<String, dynamic> labels;

    MetricSeries({required this.metricName, required this.points, required this.labels});

    factory MetricSeries.fromJson(Map<String, dynamic> json) {
         var list = json['points'] as List;
         List<MetricPoint> pointsList = list.map((i) => MetricPoint.fromJson(i)).toList();
         return MetricSeries(
             metricName: json['metric_name'],
             points: pointsList,
             labels: Map<String, dynamic>.from(json['labels'] ?? {}),
         );
    }
}

class LogPattern {
    final String template;
    final int count;
    final Map<String, int> severityCounts;

    LogPattern({required this.template, required this.count, required this.severityCounts});

    factory LogPattern.fromJson(Map<String, dynamic> json) {
        return LogPattern(
            template: json['template'],
            count: json['count'],
            severityCounts: Map<String, int>.from(json['severity_counts'] ?? {}),
        );
    }
}

class RemediationStep {
    final String command;
    final String description;

    RemediationStep({required this.command, required this.description});

    factory RemediationStep.fromJson(Map<String, dynamic> json) {
        return RemediationStep(
            command: json['command'],
            description: json['description'],
        );
    }
}

class RemediationPlan {
    final String issue;
    final String risk; // 'low', 'medium', 'high'
    final List<RemediationStep> steps;

    RemediationPlan({required this.issue, required this.risk, required this.steps});

    factory RemediationPlan.fromJson(Map<String, dynamic> json) {
        var list = json['steps'] as List;
        List<RemediationStep> stepsList = list.map((i) => RemediationStep.fromJson(i)).toList();
        return RemediationPlan(
            issue: json['issue'],
            risk: json['risk'],
            steps: stepsList,
        );
    }
}

class ToolLog {
    final String toolName;
    final Map<String, dynamic> args;
    final String status; // 'running', 'completed', 'error'
    final String? result;
    final String? timestamp;

    ToolLog({
        required this.toolName,
        required this.args,
        required this.status,
        this.result,
        this.timestamp,
    });

    factory ToolLog.fromJson(Map<String, dynamic> json) {
        return ToolLog(
            toolName: json['tool_name'],
            args: Map<String, dynamic>.from(json['args'] ?? {}),
            status: json['status'] ?? 'unknown',
            result: json['result']?.toString(), // Handle both string and complex object results by stringifying for now
            timestamp: json['timestamp'],
        );
    }
}
