/// Data models for ADK agent responses with proper validation.
/// These models parse data sent from the backend via A2UI protocol.

/// Exception thrown when required fields are missing or invalid
class SchemaValidationError implements Exception {
  final String model;
  final String field;
  final String message;

  SchemaValidationError({
    required this.model,
    required this.field,
    required this.message,
  });

  @override
  String toString() =>
      'SchemaValidationError in $model: $field - $message';
}

/// Helper class for safe field access
class _FieldValidator {
  final Map<String, dynamic> json;
  final String modelName;

  _FieldValidator(this.json, this.modelName);

  /// Get required string field
  String requireString(String field) {
    final value = json[field];
    if (value == null) {
      throw SchemaValidationError(
        model: modelName,
        field: field,
        message: 'Required field is missing',
      );
    }
    if (value is! String) {
      throw SchemaValidationError(
        model: modelName,
        field: field,
        message: 'Expected String, got ${value.runtimeType}',
      );
    }
    return value;
  }

  /// Get optional string field
  String? optionalString(String field) {
    final value = json[field];
    if (value == null) return null;
    return value.toString();
  }

  /// Get required int field
  int requireInt(String field) {
    final value = json[field];
    if (value == null) {
      throw SchemaValidationError(
        model: modelName,
        field: field,
        message: 'Required field is missing',
      );
    }
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value is String) {
      final parsed = int.tryParse(value);
      if (parsed != null) return parsed;
    }
    throw SchemaValidationError(
      model: modelName,
      field: field,
      message: 'Expected int, got ${value.runtimeType}',
    );
  }

  /// Get required double field
  double requireDouble(String field) {
    final value = json[field];
    if (value == null) {
      throw SchemaValidationError(
        model: modelName,
        field: field,
        message: 'Required field is missing',
      );
    }
    if (value is double) return value;
    if (value is num) return value.toDouble();
    if (value is String) {
      final parsed = double.tryParse(value);
      if (parsed != null) return parsed;
    }
    throw SchemaValidationError(
      model: modelName,
      field: field,
      message: 'Expected double, got ${value.runtimeType}',
    );
  }

  /// Get optional double with default
  double optionalDouble(String field, double defaultValue) {
    final value = json[field];
    if (value == null) return defaultValue;
    if (value is double) return value;
    if (value is num) return value.toDouble();
    if (value is String) {
      final parsed = double.tryParse(value);
      if (parsed != null) return parsed;
    }
    return defaultValue;
  }

  /// Get required bool field
  bool requireBool(String field) {
    final value = json[field];
    if (value == null) {
      throw SchemaValidationError(
        model: modelName,
        field: field,
        message: 'Required field is missing',
      );
    }
    if (value is bool) return value;
    if (value is String) {
      return value.toLowerCase() == 'true';
    }
    return value == 1 || value == '1';
  }

  /// Get optional bool with default
  bool optionalBool(String field, bool defaultValue) {
    final value = json[field];
    if (value == null) return defaultValue;
    if (value is bool) return value;
    if (value is String) {
      return value.toLowerCase() == 'true';
    }
    return value == 1 || value == '1';
  }

  /// Get required DateTime from ISO string
  DateTime requireDateTime(String field) {
    final value = json[field];
    if (value == null) {
      throw SchemaValidationError(
        model: modelName,
        field: field,
        message: 'Required field is missing',
      );
    }
    if (value is DateTime) return value;
    if (value is String) {
      try {
        return DateTime.parse(value);
      } catch (e) {
        throw SchemaValidationError(
          model: modelName,
          field: field,
          message: 'Invalid datetime format: $value',
        );
      }
    }
    throw SchemaValidationError(
      model: modelName,
      field: field,
      message: 'Expected DateTime or ISO string, got ${value.runtimeType}',
    );
  }

  /// Get required list field
  List<dynamic> requireList(String field) {
    final value = json[field];
    if (value == null) {
      throw SchemaValidationError(
        model: modelName,
        field: field,
        message: 'Required field is missing',
      );
    }
    if (value is! List) {
      throw SchemaValidationError(
        model: modelName,
        field: field,
        message: 'Expected List, got ${value.runtimeType}',
      );
    }
    return value;
  }

  /// Get optional list with default
  List<dynamic> optionalList(String field) {
    final value = json[field];
    if (value == null) return [];
    if (value is List) return value;
    return [];
  }

  /// Get optional map with default
  Map<String, dynamic> optionalMap(String field) {
    final value = json[field];
    if (value == null) return {};
    if (value is Map<String, dynamic>) return value;
    if (value is Map) return Map<String, dynamic>.from(value);
    return {};
  }

  /// Get optional Map<String, int> with default
  Map<String, int> optionalMapStringInt(String field) {
    final value = json[field];
    if (value == null) return {};
    if (value is Map) {
      return value.map((k, v) => MapEntry(k.toString(), v is int ? v : (v is num ? v.toInt() : 0)));
    }
    return {};
  }
}

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
    final v = _FieldValidator(json, 'SpanInfo');
    return SpanInfo(
      spanId: v.requireString('span_id'),
      traceId: v.requireString('trace_id'),
      name: v.requireString('name'),
      startTime: v.requireDateTime('start_time'),
      endTime: v.requireDateTime('end_time'),
      attributes: v.optionalMap('attributes'),
      status: v.optionalString('status') ?? 'OK',
      parentSpanId: v.optionalString('parent_span_id'),
    );
  }
}

class Trace {
  final String traceId;
  final List<SpanInfo> spans;

  Trace({required this.traceId, required this.spans});

  factory Trace.fromJson(Map<String, dynamic> json) {
    final v = _FieldValidator(json, 'Trace');
    final traceId = v.requireString('trace_id');
    final spansList = v.requireList('spans');

    final spans = spansList.map((item) {
      if (item is! Map) {
        throw SchemaValidationError(
          model: 'Trace',
          field: 'spans',
          message: 'Each span must be a Map, got ${item.runtimeType}',
        );
      }
      return SpanInfo.fromJson(Map<String, dynamic>.from(item));
    }).toList();

    return Trace(traceId: traceId, spans: spans);
  }
}

class MetricPoint {
  final DateTime timestamp;
  final double value;
  final bool isAnomaly;

  MetricPoint({required this.timestamp, required this.value, this.isAnomaly = false});

  factory MetricPoint.fromJson(Map<String, dynamic> json) {
    final v = _FieldValidator(json, 'MetricPoint');
    return MetricPoint(
      timestamp: v.requireDateTime('timestamp'),
      value: v.requireDouble('value'),
      isAnomaly: v.optionalBool('is_anomaly', false),
    );
  }
}

class MetricSeries {
  final String metricName;
  final List<MetricPoint> points;
  final Map<String, dynamic> labels;

  MetricSeries({required this.metricName, required this.points, required this.labels});

  factory MetricSeries.fromJson(Map<String, dynamic> json) {
    final v = _FieldValidator(json, 'MetricSeries');
    final pointsList = v.optionalList('points');

    final points = pointsList.map((item) {
      if (item is! Map) {
        throw SchemaValidationError(
          model: 'MetricSeries',
          field: 'points',
          message: 'Each point must be a Map, got ${item.runtimeType}',
        );
      }
      return MetricPoint.fromJson(Map<String, dynamic>.from(item));
    }).toList();

    return MetricSeries(
      metricName: v.optionalString('metric_name') ?? 'Unknown Metric',
      points: points,
      labels: v.optionalMap('labels'),
    );
  }
}

class LogPattern {
  final String template;
  final int count;
  final Map<String, int> severityCounts;
  /// Optional: actual frequency data points for sparkline
  final List<int>? frequencyData;

  LogPattern({
    required this.template,
    required this.count,
    required this.severityCounts,
    this.frequencyData,
  });

  factory LogPattern.fromJson(Map<String, dynamic> json) {
    final v = _FieldValidator(json, 'LogPattern');

    // Parse frequency data if available
    List<int>? freqData;
    final freqRaw = json['frequency_data'];
    if (freqRaw != null && freqRaw is List) {
      freqData = freqRaw.map((e) => e is int ? e : (e is num ? e.toInt() : 0)).toList();
    }

    return LogPattern(
      template: v.requireString('template'),
      count: v.requireInt('count'),
      severityCounts: v.optionalMapStringInt('severity_counts'),
      frequencyData: freqData,
    );
  }
}

class RemediationStep {
  final String command;
  final String description;

  RemediationStep({required this.command, required this.description});

  factory RemediationStep.fromJson(Map<String, dynamic> json) {
    final v = _FieldValidator(json, 'RemediationStep');
    return RemediationStep(
      command: v.optionalString('command') ?? '',
      description: v.requireString('description'),
    );
  }
}

class RemediationPlan {
  final String issue;
  final String risk; // 'low', 'medium', 'high'
  final List<RemediationStep> steps;

  RemediationPlan({required this.issue, required this.risk, required this.steps});

  factory RemediationPlan.fromJson(Map<String, dynamic> json) {
    final v = _FieldValidator(json, 'RemediationPlan');
    final stepsList = v.optionalList('steps');

    final steps = stepsList.map((item) {
      if (item is! Map) {
        throw SchemaValidationError(
          model: 'RemediationPlan',
          field: 'steps',
          message: 'Each step must be a Map, got ${item.runtimeType}',
        );
      }
      return RemediationStep.fromJson(Map<String, dynamic>.from(item));
    }).toList();

    return RemediationPlan(
      issue: v.optionalString('issue') ?? 'Unknown Issue',
      risk: v.optionalString('risk') ?? 'medium',
      steps: steps,
    );
  }
}

class ToolLog {
  final String toolName;
  final Map<String, dynamic> args;
  final String status; // 'running', 'completed', 'error'
  final dynamic result; // Keep as dynamic to preserve structure
  final String? timestamp;

  ToolLog({
    required this.toolName,
    required this.args,
    required this.status,
    this.result,
    this.timestamp,
  });

  factory ToolLog.fromJson(Map<String, dynamic> json) {
    final v = _FieldValidator(json, 'ToolLog');
    return ToolLog(
      toolName: v.requireString('tool_name'),
      args: v.optionalMap('args'),
      status: v.optionalString('status') ?? 'unknown',
      result: json['result'], // Keep original structure
      timestamp: v.optionalString('timestamp'),
    );
  }
}
