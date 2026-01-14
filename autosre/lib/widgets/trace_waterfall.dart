import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../models/adk_schema.dart';
import '../theme/app_theme.dart';

/// A node in the span tree hierarchy
class _SpanNode {
  final SpanInfo span;
  final List<_SpanNode> children;
  final int depth;
  bool isExpanded;
  bool isOnCriticalPath;

  _SpanNode({
    required this.span,
    this.children = const [],
    this.depth = 0,
    this.isExpanded = true,
    this.isOnCriticalPath = false,
  });
}

class TraceWaterfall extends StatefulWidget {
  final Trace trace;

  const TraceWaterfall({super.key, required this.trace});

  @override
  State<TraceWaterfall> createState() => _TraceWaterfallState();
}

class _TraceWaterfallState extends State<TraceWaterfall>
    with SingleTickerProviderStateMixin {
  late AnimationController _animController;
  late Animation<double> _animation;
  int? _hoveredIndex;
  SpanInfo? _selectedSpan;
  late List<_SpanNode> _flattenedNodes;
  late Set<String> _criticalPathSpanIds;
  late DateTime _traceStart;
  late int _totalDuration;
  final Map<String, Color> _serviceColors = {};
  final ScrollController _scrollController = ScrollController();

  // Color palette for services
  static const List<Color> _colorPalette = [
    Color(0xFF00D9B5), // Teal
    Color(0xFF00B4D8), // Cyan
    Color(0xFF7B68EE), // Purple
    Color(0xFFFF6B9D), // Pink
    Color(0xFFFFAB00), // Amber
    Color(0xFF00E676), // Green
    Color(0xFF40C4FF), // Light Blue
    Color(0xFFFF7043), // Deep Orange
  ];

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    _animation = CurvedAnimation(
      parent: _animController,
      curve: Curves.easeOutCubic,
    );
    _animController.forward();
    _buildSpanTree();
  }

  void _buildSpanTree() {
    if (widget.trace.spans.isEmpty) {
      _flattenedNodes = [];
      _criticalPathSpanIds = {};
      return;
    }

    // Sort spans by start time
    final sortedSpans = List<SpanInfo>.from(widget.trace.spans)
      ..sort((a, b) => a.startTime.compareTo(b.startTime));

    _traceStart = sortedSpans.first.startTime;
    final traceEnd = sortedSpans.map((s) => s.endTime).reduce(
        (a, b) => a.isAfter(b) ? a : b);
    _totalDuration = traceEnd.difference(_traceStart).inMicroseconds;

    // Build parent-child map
    final Map<String?, List<SpanInfo>> childrenMap = {};
    for (final span in sortedSpans) {
      childrenMap.putIfAbsent(span.parentSpanId, () => []).add(span);
    }

    // Find root spans (no parent or parent not in trace)
    final allSpanIds = sortedSpans.map((s) => s.spanId).toSet();
    final rootSpans = sortedSpans.where(
        (s) => s.parentSpanId == null || !allSpanIds.contains(s.parentSpanId));

    // Build tree recursively
    _SpanNode buildNode(SpanInfo span, int depth) {
      final children = (childrenMap[span.spanId] ?? [])
          .map((child) => buildNode(child, depth + 1))
          .toList();
      return _SpanNode(span: span, children: children, depth: depth);
    }

    final rootNodes = rootSpans.map((s) => buildNode(s, 0)).toList();

    // Find critical path (longest execution path)
    _criticalPathSpanIds = _findCriticalPath(rootNodes);

    // Mark critical path nodes
    void markCriticalPath(_SpanNode node) {
      node.isOnCriticalPath = _criticalPathSpanIds.contains(node.span.spanId);
      for (final child in node.children) {
        markCriticalPath(child);
      }
    }
    for (final root in rootNodes) {
      markCriticalPath(root);
    }

    // Flatten tree for display
    _flattenedNodes = [];
    void flatten(_SpanNode node) {
      _flattenedNodes.add(node);
      if (node.isExpanded) {
        for (final child in node.children) {
          flatten(child);
        }
      }
    }
    for (final root in rootNodes) {
      flatten(root);
    }

    // Assign colors to services
    _assignServiceColors();
  }

  Set<String> _findCriticalPath(List<_SpanNode> roots) {
    // Critical path is the longest chain of spans by cumulative duration
    Set<String> criticalPath = {};
    int maxDuration = 0;

    void findPath(_SpanNode node, Set<String> currentPath, int currentDuration) {
      currentPath.add(node.span.spanId);
      final newDuration = currentDuration + node.span.duration.inMicroseconds;

      if (node.children.isEmpty) {
        if (newDuration > maxDuration) {
          maxDuration = newDuration;
          criticalPath = Set.from(currentPath);
        }
      } else {
        for (final child in node.children) {
          findPath(child, Set.from(currentPath), newDuration);
        }
      }
    }

    for (final root in roots) {
      findPath(root, {}, 0);
    }

    return criticalPath;
  }

  void _assignServiceColors() {
    int colorIndex = 0;
    for (final node in _flattenedNodes) {
      final service = _extractServiceName(node.span.name);
      if (!_serviceColors.containsKey(service)) {
        _serviceColors[service] = _colorPalette[colorIndex % _colorPalette.length];
        colorIndex++;
      }
    }
  }

  String _extractServiceName(String spanName) {
    // Extract service name from span name patterns like:
    // "service:method", "service/path", "service.method"
    final colonIndex = spanName.indexOf(':');
    final slashIndex = spanName.indexOf('/');
    final dotIndex = spanName.indexOf('.');

    int splitIndex = spanName.length;
    if (colonIndex > 0) splitIndex = math.min(splitIndex, colonIndex);
    if (slashIndex > 0) splitIndex = math.min(splitIndex, slashIndex);
    if (dotIndex > 0) splitIndex = math.min(splitIndex, dotIndex);

    return spanName.substring(0, splitIndex);
  }

  void _toggleNode(_SpanNode node) {
    setState(() {
      node.isExpanded = !node.isExpanded;
      _rebuildFlatList();
    });
  }

  void _rebuildFlatList() {
    // Re-flatten based on current expansion state
    final oldNodes = _flattenedNodes.where((n) => n.depth == 0).toList();
    _flattenedNodes = [];
    void flatten(_SpanNode node) {
      _flattenedNodes.add(node);
      if (node.isExpanded) {
        for (final child in node.children) {
          flatten(child);
        }
      }
    }
    for (final root in oldNodes) {
      flatten(root);
    }
  }

  @override
  void dispose() {
    _animController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.trace.spans.isEmpty) {
      return _buildEmptyState();
    }

    final errorCount = widget.trace.spans.where((s) => s.status == 'ERROR').length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildHeader(errorCount),
        const SizedBox(height: 8),
        _buildServiceLegend(),
        const SizedBox(height: 8),
        _buildTimeRuler(),
        Expanded(
          child: AnimatedBuilder(
            animation: _animation,
            builder: (context, child) {
              return ListView.builder(
                controller: _scrollController,
                padding: const EdgeInsets.only(bottom: 16),
                itemCount: _flattenedNodes.length,
                itemBuilder: (context, index) {
                  return _buildSpanRow(_flattenedNodes[index], index);
                },
              );
            },
          ),
        ),
        if (_selectedSpan != null) _buildSpanDetails(_selectedSpan!),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.textMuted.withValues(alpha: 0.1),
              shape: BoxShape.circle,
            ),
            child: Icon(Icons.timeline_outlined, size: 40, color: AppColors.textMuted),
          ),
          const SizedBox(height: 16),
          Text('No spans in trace', style: TextStyle(color: AppColors.textMuted, fontSize: 14)),
        ],
      ),
    );
  }

  Widget _buildHeader(int errorCount) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [AppColors.primaryTeal.withValues(alpha: 0.2), AppColors.primaryCyan.withValues(alpha: 0.15)],
              ),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.account_tree, size: 18, color: AppColors.primaryTeal),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('Trace Waterfall', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.primaryTeal.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text('${_flattenedNodes.length} spans', style: TextStyle(fontSize: 10, color: AppColors.primaryTeal, fontWeight: FontWeight.w500)),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Icon(Icons.fingerprint, size: 10, color: AppColors.textMuted),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        widget.trace.traceId,
                        style: TextStyle(fontSize: 10, fontFamily: 'monospace', color: AppColors.textMuted),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          _buildStatChip('${(_totalDuration / 1000).toStringAsFixed(1)}ms', Icons.timer_outlined, AppColors.primaryCyan),
          if (errorCount > 0) ...[
            const SizedBox(width: 8),
            _buildStatChip('$errorCount errors', Icons.error_outline, AppColors.error),
          ],
          if (_criticalPathSpanIds.isNotEmpty) ...[
            const SizedBox(width: 8),
            _buildStatChip('Critical path', Icons.trending_up, AppColors.warning),
          ],
        ],
      ),
    );
  }

  Widget _buildStatChip(String text, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: color),
          const SizedBox(width: 4),
          Text(text, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w500, color: color)),
        ],
      ),
    );
  }

  Widget _buildServiceLegend() {
    return Container(
      height: 28,
      margin: const EdgeInsets.symmetric(horizontal: 16),
      child: ListView(
        scrollDirection: Axis.horizontal,
        children: _serviceColors.entries.map((e) {
          return Container(
            margin: const EdgeInsets.only(right: 12),
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: e.value.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: e.value.withValues(alpha: 0.3)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(width: 8, height: 8, decoration: BoxDecoration(color: e.value, borderRadius: BorderRadius.circular(2))),
                const SizedBox(width: 6),
                Text(e.key, style: TextStyle(fontSize: 10, color: e.value, fontWeight: FontWeight.w500)),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildTimeRuler() {
    const int tickCount = 6;
    final tickInterval = _totalDuration / (tickCount - 1);

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.only(left: 200, right: 70),
      child: SizedBox(
        height: 24,
        child: CustomPaint(
          painter: _TimeRulerPainter(
            tickCount: tickCount,
            totalDuration: _totalDuration,
            tickInterval: tickInterval,
          ),
          child: Container(),
        ),
      ),
    );
  }

  Widget _buildSpanRow(_SpanNode node, int index) {
    final span = node.span;
    final offsetMicros = span.startTime.difference(_traceStart).inMicroseconds;
    final durationMicros = span.duration.inMicroseconds;

    double startPercent = offsetMicros / _totalDuration;
    double widthPercent = durationMicros / _totalDuration;
    if (widthPercent < 0.015) widthPercent = 0.015;

    final isHovered = _hoveredIndex == index;
    final isSelected = _selectedSpan?.spanId == span.spanId;
    final isError = span.status == 'ERROR';
    final service = _extractServiceName(span.name);
    final serviceColor = _serviceColors[service] ?? AppColors.primaryTeal;

    final staggerDelay = index / _flattenedNodes.length;
    final animValue = ((_animation.value - staggerDelay * 0.5) / 0.5).clamp(0.0, 1.0);

    return MouseRegion(
      onEnter: (_) => setState(() => _hoveredIndex = index),
      onExit: (_) => setState(() => _hoveredIndex = null),
      child: GestureDetector(
        onTap: () => setState(() {
          _selectedSpan = _selectedSpan?.spanId == span.spanId ? null : span;
        }),
        child: AnimatedOpacity(
          duration: const Duration(milliseconds: 150),
          opacity: animValue,
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 1),
            decoration: BoxDecoration(
              color: isSelected
                  ? serviceColor.withValues(alpha: 0.12)
                  : isHovered
                      ? Colors.white.withValues(alpha: 0.04)
                      : node.isOnCriticalPath
                          ? AppColors.warning.withValues(alpha: 0.05)
                          : Colors.transparent,
              borderRadius: BorderRadius.circular(6),
              border: isSelected ? Border.all(color: serviceColor.withValues(alpha: 0.3)) : null,
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 8),
              child: Row(
                children: [
                  // Indentation + expand button
                  SizedBox(
                    width: 24.0 * node.depth + 24,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        if (node.children.isNotEmpty)
                          GestureDetector(
                            onTap: () => _toggleNode(node),
                            child: AnimatedRotation(
                              duration: const Duration(milliseconds: 200),
                              turns: node.isExpanded ? 0.25 : 0,
                              child: Icon(Icons.chevron_right, size: 16, color: AppColors.textMuted),
                            ),
                          )
                        else
                          const SizedBox(width: 16),
                      ],
                    ),
                  ),

                  // Span name with service color indicator
                  SizedBox(
                    width: 160,
                    child: Row(
                      children: [
                        // Critical path indicator
                        if (node.isOnCriticalPath)
                          Container(
                            width: 3,
                            height: 16,
                            margin: const EdgeInsets.only(right: 6),
                            decoration: BoxDecoration(
                              color: AppColors.warning,
                              borderRadius: BorderRadius.circular(2),
                            ),
                          ),
                        // Status icon
                        Icon(
                          isError ? Icons.cancel : Icons.check_circle,
                          size: 12,
                          color: isError ? AppColors.error : serviceColor,
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Tooltip(
                            message: span.name,
                            child: Text(
                              span.name,
                              style: TextStyle(
                                fontSize: 11,
                                color: isError ? AppColors.error : AppColors.textSecondary,
                                fontWeight: isSelected || node.isOnCriticalPath ? FontWeight.w500 : null,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Timeline bar
                  Expanded(
                    child: LayoutBuilder(
                      builder: (context, constraints) {
                        final barWidth = constraints.maxWidth * widthPercent * animValue;
                        final barOffset = constraints.maxWidth * startPercent;

                        return Stack(
                          children: [
                            // Background track
                            Container(
                              height: 20,
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.02),
                                borderRadius: BorderRadius.circular(3),
                              ),
                            ),
                            // Span bar
                            Positioned(
                              left: barOffset,
                              child: Tooltip(
                                message: '${span.name}\nDuration: ${span.duration.inMilliseconds}ms\nStatus: ${span.status}',
                                child: AnimatedContainer(
                                  duration: const Duration(milliseconds: 150),
                                  height: 20,
                                  width: barWidth.clamp(6.0, constraints.maxWidth - barOffset),
                                  decoration: BoxDecoration(
                                    gradient: LinearGradient(
                                      colors: isError
                                          ? [AppColors.error, AppColors.error.withValues(alpha: 0.7)]
                                          : node.isOnCriticalPath
                                              ? [AppColors.warning, AppColors.warning.withValues(alpha: 0.8)]
                                              : [serviceColor, serviceColor.withValues(alpha: 0.7)],
                                    ),
                                    borderRadius: BorderRadius.circular(3),
                                    boxShadow: (isHovered || isSelected)
                                        ? [BoxShadow(color: (isError ? AppColors.error : serviceColor).withValues(alpha: 0.4), blurRadius: 8)]
                                        : null,
                                  ),
                                  child: barWidth > 40
                                      ? Center(
                                          child: Text(
                                            '${span.duration.inMilliseconds}ms',
                                            style: TextStyle(fontSize: 9, color: Colors.white.withValues(alpha: 0.9), fontWeight: FontWeight.w500),
                                          ),
                                        )
                                      : null,
                                ),
                              ),
                            ),
                          ],
                        );
                      },
                    ),
                  ),

                  // Duration
                  SizedBox(
                    width: 60,
                    child: Text(
                      '${span.duration.inMilliseconds}ms',
                      style: TextStyle(
                        fontSize: 10,
                        fontFamily: 'monospace',
                        color: isError ? AppColors.error : node.isOnCriticalPath ? AppColors.warning : AppColors.textMuted,
                        fontWeight: FontWeight.w500,
                      ),
                      textAlign: TextAlign.right,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSpanDetails(SpanInfo span) {
    final service = _extractServiceName(span.name);
    final serviceColor = _serviceColors[service] ?? AppColors.primaryTeal;
    final isOnCriticalPath = _criticalPathSpanIds.contains(span.spanId);

    return Container(
      margin: const EdgeInsets.all(12),
      padding: const EdgeInsets.all(14),
      decoration: GlassDecoration.elevated(
        borderRadius: 12,
        withGlow: span.status == 'ERROR',
        glowColor: span.status == 'ERROR' ? AppColors.error : serviceColor,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: serviceColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Icon(
                  span.status == 'ERROR' ? Icons.error : Icons.check_circle,
                  size: 16,
                  color: span.status == 'ERROR' ? AppColors.error : serviceColor,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(span.name, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
                    Text(service, style: TextStyle(fontSize: 10, color: serviceColor)),
                  ],
                ),
              ),
              if (isOnCriticalPath)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.warning.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.trending_up, size: 12, color: AppColors.warning),
                      const SizedBox(width: 4),
                      Text('Critical Path', style: TextStyle(fontSize: 10, color: AppColors.warning, fontWeight: FontWeight.w500)),
                    ],
                  ),
                ),
              const SizedBox(width: 8),
              IconButton(
                icon: const Icon(Icons.close, size: 16),
                onPressed: () => setState(() => _selectedSpan = null),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                color: AppColors.textMuted,
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 6,
            children: [
              _buildDetailChip('Span ID', span.spanId.substring(0, math.min(8, span.spanId.length)), serviceColor),
              _buildDetailChip('Duration', '${span.duration.inMilliseconds}ms', AppColors.primaryCyan),
              _buildDetailChip('Status', span.status, span.status == 'ERROR' ? AppColors.error : AppColors.success),
              if (span.parentSpanId != null) _buildDetailChip('Parent', span.parentSpanId!.substring(0, math.min(8, span.parentSpanId!.length)), AppColors.textMuted),
            ],
          ),
          if (span.attributes.isNotEmpty) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Attributes', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: AppColors.textMuted)),
                  const SizedBox(height: 6),
                  ...span.attributes.entries.take(6).map((e) => Padding(
                        padding: const EdgeInsets.only(bottom: 3),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            SizedBox(
                              width: 100,
                              child: Text('${e.key}:', style: TextStyle(fontSize: 10, color: AppColors.textMuted)),
                            ),
                            Expanded(
                              child: Text('${e.value}', style: TextStyle(fontSize: 10, color: AppColors.textSecondary, fontFamily: 'monospace'), overflow: TextOverflow.ellipsis),
                            ),
                          ],
                        ),
                      )),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildDetailChip(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('$label: ', style: TextStyle(fontSize: 10, color: AppColors.textMuted)),
          Text(value, style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.w500, fontFamily: 'monospace')),
        ],
      ),
    );
  }
}

/// Custom painter for the time ruler
class _TimeRulerPainter extends CustomPainter {
  final int tickCount;
  final int totalDuration;
  final double tickInterval;

  _TimeRulerPainter({
    required this.tickCount,
    required this.totalDuration,
    required this.tickInterval,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppColors.surfaceBorder
      ..strokeWidth = 1;

    // Draw baseline
    canvas.drawLine(Offset(0, size.height - 1), Offset(size.width, size.height - 1), paint);

    // Draw ticks and labels
    final textPainter = TextPainter(textDirection: TextDirection.ltr);
    for (int i = 0; i < tickCount; i++) {
      final x = (i / (tickCount - 1)) * size.width;
      final timeMs = (tickInterval * i) / 1000;

      // Tick mark
      canvas.drawLine(Offset(x, size.height - 6), Offset(x, size.height), paint);

      // Label
      textPainter.text = TextSpan(
        text: '${timeMs.toStringAsFixed(0)}ms',
        style: TextStyle(fontSize: 9, color: AppColors.textMuted),
      );
      textPainter.layout();
      final labelX = x - textPainter.width / 2;
      textPainter.paint(canvas, Offset(labelX.clamp(0, size.width - textPainter.width), 0));
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
