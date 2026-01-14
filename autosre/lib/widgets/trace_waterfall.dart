import 'package:flutter/material.dart';
import '../models/adk_schema.dart';
import '../theme/app_theme.dart';

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
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.trace.spans.isEmpty) {
      return _buildEmptyState();
    }

    final sortedSpans = List<SpanInfo>.from(widget.trace.spans)
      ..sort((a, b) => a.startTime.compareTo(b.startTime));

    final startTime = sortedSpans.first.startTime;
    final totalDuration =
        sortedSpans.last.endTime.difference(startTime).inMicroseconds;

    final errorCount = sortedSpans.where((s) => s.status == 'ERROR').length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header
        _buildHeader(totalDuration, sortedSpans.length, errorCount),

        const SizedBox(height: 12),

        // Legend
        _buildLegend(),

        const SizedBox(height: 16),

        // Waterfall chart
        Expanded(
          child: AnimatedBuilder(
            animation: _animation,
            builder: (context, child) {
              return SingleChildScrollView(
                child: Column(
                  children: List.generate(sortedSpans.length, (index) {
                    final span = sortedSpans[index];
                    return _buildSpanRow(
                      span,
                      index,
                      startTime,
                      totalDuration,
                      sortedSpans.length,
                    );
                  }),
                ),
              );
            },
          ),
        ),

        // Selected span details
        if (_selectedSpan != null) _buildSpanDetails(_selectedSpan!),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.timeline_outlined,
            size: 48,
            color: AppColors.textMuted,
          ),
          const SizedBox(height: 16),
          Text(
            'No spans in trace',
            style: TextStyle(
              color: AppColors.textMuted,
              fontSize: 14,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(int totalDuration, int spanCount, int errorCount) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          // Trace ID
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(6),
                      decoration: BoxDecoration(
                        color: AppColors.primaryTeal.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.timeline,
                        size: 16,
                        color: AppColors.primaryTeal,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Text(
                      'Trace Waterfall',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  widget.trace.traceId,
                  style: TextStyle(
                    fontSize: 11,
                    fontFamily: 'monospace',
                    color: AppColors.textMuted,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),

          // Stats badges
          _buildStatBadge(
            '${(totalDuration / 1000).toStringAsFixed(1)} ms',
            Icons.timer_outlined,
            AppColors.primaryCyan,
          ),
          const SizedBox(width: 8),
          _buildStatBadge(
            '$spanCount spans',
            Icons.layers_outlined,
            AppColors.primaryTeal,
          ),
          if (errorCount > 0) ...[
            const SizedBox(width: 8),
            _buildStatBadge(
              '$errorCount errors',
              Icons.error_outline,
              AppColors.error,
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStatBadge(String text, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Text(
            text,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLegend() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          _buildLegendItem('OK', AppColors.primaryTeal),
          const SizedBox(width: 16),
          _buildLegendItem('ERROR', AppColors.error),
        ],
      ),
    );
  }

  Widget _buildLegendItem(String label, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [color, color.withValues(alpha: 0.7)],
            ),
            borderRadius: BorderRadius.circular(3),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: TextStyle(
            fontSize: 11,
            color: AppColors.textMuted,
          ),
        ),
      ],
    );
  }

  Widget _buildSpanRow(
    SpanInfo span,
    int index,
    DateTime traceStart,
    int totalDuration,
    int totalSpans,
  ) {
    final offsetMicros = span.startTime.difference(traceStart).inMicroseconds;
    final durationMicros = span.duration.inMicroseconds;

    double startPercent = offsetMicros / totalDuration;
    double widthPercent = durationMicros / totalDuration;

    // Ensure minimum visibility
    if (widthPercent < 0.02) widthPercent = 0.02;

    final isHovered = _hoveredIndex == index;
    final isSelected = _selectedSpan?.spanId == span.spanId;
    final isError = span.status == 'ERROR';

    // Stagger animation
    final staggerDelay = index / totalSpans;
    final animValue =
        ((_animation.value - staggerDelay) / (1 - staggerDelay)).clamp(0.0, 1.0);

    return MouseRegion(
      onEnter: (_) => setState(() => _hoveredIndex = index),
      onExit: (_) => setState(() => _hoveredIndex = null),
      child: GestureDetector(
        onTap: () => setState(() {
          _selectedSpan = _selectedSpan?.spanId == span.spanId ? null : span;
        }),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
          padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
          decoration: BoxDecoration(
            color: isSelected
                ? AppColors.primaryTeal.withValues(alpha: 0.1)
                : isHovered
                    ? Colors.white.withValues(alpha: 0.05)
                    : index % 2 == 0
                        ? Colors.white.withValues(alpha: 0.02)
                        : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
            border: isSelected
                ? Border.all(color: AppColors.primaryTeal.withValues(alpha: 0.3))
                : null,
          ),
          child: Row(
            children: [
              // Span name
              SizedBox(
                width: 180,
                child: Row(
                  children: [
                    Icon(
                      isError ? Icons.error_outline : Icons.check_circle_outline,
                      size: 14,
                      color: isError ? AppColors.error : AppColors.success,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        span.name,
                        style: TextStyle(
                          fontSize: 12,
                          color: AppColors.textSecondary,
                          fontWeight: isSelected ? FontWeight.w500 : null,
                        ),
                        overflow: TextOverflow.ellipsis,
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
                          height: 24,
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.03),
                            borderRadius: BorderRadius.circular(4),
                          ),
                        ),

                        // Span bar
                        Positioned(
                          left: barOffset,
                          child: Tooltip(
                            message:
                                '${span.name}\n${span.duration.inMilliseconds} ms\nStatus: ${span.status}',
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 150),
                              height: 24,
                              width: barWidth.clamp(4.0, constraints.maxWidth - barOffset),
                              decoration: BoxDecoration(
                                gradient: LinearGradient(
                                  colors: isError
                                      ? [AppColors.error, AppColors.error.withValues(alpha: 0.7)]
                                      : [AppColors.primaryTeal, AppColors.primaryCyan],
                                ),
                                borderRadius: BorderRadius.circular(4),
                                boxShadow: isHovered || isSelected
                                    ? [
                                        BoxShadow(
                                          color: (isError
                                                  ? AppColors.error
                                                  : AppColors.primaryTeal)
                                              .withValues(alpha: 0.4),
                                          blurRadius: 8,
                                          offset: const Offset(0, 2),
                                        ),
                                      ]
                                    : null,
                              ),
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
                width: 70,
                child: Text(
                  '${span.duration.inMilliseconds} ms',
                  style: TextStyle(
                    fontSize: 11,
                    fontFamily: 'monospace',
                    color: isError ? AppColors.error : AppColors.textMuted,
                    fontWeight: FontWeight.w500,
                  ),
                  textAlign: TextAlign.right,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSpanDetails(SpanInfo span) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: GlassDecoration.elevated(
        borderRadius: 12,
        withGlow: span.status == 'ERROR',
        glowColor: span.status == 'ERROR' ? AppColors.error : AppColors.primaryTeal,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                span.status == 'ERROR' ? Icons.error : Icons.check_circle,
                size: 18,
                color: span.status == 'ERROR' ? AppColors.error : AppColors.success,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  span.name,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.close, size: 18),
                onPressed: () => setState(() => _selectedSpan = null),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                color: AppColors.textMuted,
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 16,
            runSpacing: 8,
            children: [
              _buildDetailItem('Span ID', span.spanId),
              _buildDetailItem('Duration', '${span.duration.inMilliseconds} ms'),
              _buildDetailItem('Status', span.status),
              if (span.parentSpanId != null)
                _buildDetailItem('Parent', span.parentSpanId!),
            ],
          ),
          if (span.attributes.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 12),
            Text(
              'Attributes',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: AppColors.textMuted,
              ),
            ),
            const SizedBox(height: 8),
            ...span.attributes.entries.take(5).map((e) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    children: [
                      Text(
                        '${e.key}: ',
                        style: TextStyle(
                          fontSize: 11,
                          color: AppColors.textMuted,
                        ),
                      ),
                      Expanded(
                        child: Text(
                          '${e.value}',
                          style: TextStyle(
                            fontSize: 11,
                            color: AppColors.textSecondary,
                            fontFamily: 'monospace',
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                )),
          ],
        ],
      ),
    );
  }

  Widget _buildDetailItem(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 10,
            color: AppColors.textMuted,
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: TextStyle(
            fontSize: 12,
            color: AppColors.textSecondary,
            fontFamily: label == 'Span ID' || label == 'Parent' ? 'monospace' : null,
          ),
        ),
      ],
    );
  }
}
