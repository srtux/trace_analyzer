import 'dart:math' as math;
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/adk_schema.dart';
import '../theme/app_theme.dart';

class MetricCorrelationChart extends StatefulWidget {
  final MetricSeries series;

  const MetricCorrelationChart({super.key, required this.series});

  @override
  State<MetricCorrelationChart> createState() => _MetricCorrelationChartState();
}

class _MetricCorrelationChartState extends State<MetricCorrelationChart>
    with SingleTickerProviderStateMixin {
  late AnimationController _animController;
  late Animation<double> _animation;
  int? _touchedIndex;
  bool _showTrendLine = true;
  bool _showThreshold = true;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      duration: const Duration(milliseconds: 1000),
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

  // Calculate moving average for trend line
  List<double> _calculateMovingAverage(List<MetricPoint> points, int windowSize) {
    if (points.length < windowSize) return points.map((p) => p.value).toList();

    List<double> result = [];
    for (int i = 0; i < points.length; i++) {
      int start = math.max(0, i - windowSize ~/ 2);
      int end = math.min(points.length, i + windowSize ~/ 2 + 1);
      double sum = 0;
      for (int j = start; j < end; j++) {
        sum += points[j].value;
      }
      result.add(sum / (end - start));
    }
    return result;
  }

  // Find anomaly regions (consecutive anomaly points)
  List<_AnomalyRegion> _findAnomalyRegions(List<MetricPoint> points) {
    List<_AnomalyRegion> regions = [];
    int? startIndex;

    for (int i = 0; i < points.length; i++) {
      if (points[i].isAnomaly) {
        startIndex ??= i;
      } else if (startIndex != null) {
        regions.add(_AnomalyRegion(startIndex, i - 1));
        startIndex = null;
      }
    }
    if (startIndex != null) {
      regions.add(_AnomalyRegion(startIndex, points.length - 1));
    }
    return regions;
  }

  // Calculate percentiles
  double _calculatePercentile(List<double> sortedValues, double percentile) {
    if (sortedValues.isEmpty) return 0;
    int index = ((percentile / 100) * (sortedValues.length - 1)).round();
    return sortedValues[index];
  }

  // Format large numbers
  String _formatValue(double value) {
    if (value.abs() >= 1000000) {
      return '${(value / 1000000).toStringAsFixed(1)}M';
    } else if (value.abs() >= 1000) {
      return '${(value / 1000).toStringAsFixed(1)}K';
    } else if (value.abs() < 0.01 && value != 0) {
      return value.toStringAsExponential(1);
    }
    return value.toStringAsFixed(value.abs() < 10 ? 2 : 1);
  }

  @override
  Widget build(BuildContext context) {
    if (widget.series.points.isEmpty) {
      return _buildEmptyState();
    }

    final sortedPoints = List<MetricPoint>.from(widget.series.points)
      ..sort((a, b) => a.timestamp.compareTo(b.timestamp));

    final values = sortedPoints.map((p) => p.value).toList();
    final sortedValues = List<double>.from(values)..sort();

    final anomalyCount = sortedPoints.where((p) => p.isAnomaly).length;
    final maxValue = sortedValues.last;
    final minValue = sortedValues.first;
    final avgValue = values.reduce((a, b) => a + b) / values.length;
    final p95Value = _calculatePercentile(sortedValues, 95);
    final p50Value = _calculatePercentile(sortedValues, 50);

    final movingAvg = _calculateMovingAverage(sortedPoints, 5);
    final anomalyRegions = _findAnomalyRegions(sortedPoints);

    // Determine trend
    final firstHalfAvg = values.sublist(0, values.length ~/ 2).reduce((a, b) => a + b) / (values.length ~/ 2);
    final secondHalfAvg = values.sublist(values.length ~/ 2).reduce((a, b) => a + b) / (values.length - values.length ~/ 2);
    final trendPercent = ((secondHalfAvg - firstHalfAvg) / firstHalfAvg * 100);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildHeader(anomalyCount, trendPercent),
        const SizedBox(height: 10),
        _buildStatsRow(minValue, maxValue, avgValue, p95Value),
        const SizedBox(height: 8),
        _buildToggleRow(),
        const SizedBox(height: 8),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(4, 8, 12, 8),
            child: AnimatedBuilder(
              animation: _animation,
              builder: (context, child) {
                return LineChart(
                  LineChartData(
                    gridData: _buildGridData(),
                    titlesData: _buildTitlesData(sortedPoints),
                    borderData: FlBorderData(show: false),
                    lineTouchData: _buildTouchData(sortedPoints),
                    extraLinesData: _buildExtraLines(avgValue, p95Value),
                    rangeAnnotations: _buildAnomalyAnnotations(anomalyRegions, sortedPoints.length, minValue, maxValue),
                    lineBarsData: [
                      _buildMainLineData(sortedPoints),
                      if (_showTrendLine) _buildTrendLineData(sortedPoints, movingAvg),
                    ],
                    minY: minValue - (maxValue - minValue) * 0.1,
                    maxY: maxValue + (maxValue - minValue) * 0.1,
                  ),
                  duration: const Duration(milliseconds: 250),
                );
              },
            ),
          ),
        ),
        _buildSparklineOverview(sortedPoints, anomalyRegions),
        if (widget.series.labels.isNotEmpty) _buildLabelsFooter(),
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
            child: Icon(Icons.show_chart_outlined, size: 40, color: AppColors.textMuted),
          ),
          const SizedBox(height: 16),
          Text('No metric data available', style: TextStyle(color: AppColors.textMuted, fontSize: 14)),
        ],
      ),
    );
  }

  Widget _buildHeader(int anomalyCount, double trendPercent) {
    final trendColor = trendPercent > 5 ? AppColors.error : trendPercent < -5 ? AppColors.success : AppColors.textMuted;
    final trendIcon = trendPercent > 5 ? Icons.trending_up : trendPercent < -5 ? Icons.trending_down : Icons.trending_flat;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [AppColors.primaryCyan.withValues(alpha: 0.2), AppColors.primaryBlue.withValues(alpha: 0.15)],
              ),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.insights, size: 18, color: AppColors.primaryCyan),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Metric Analysis', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
                const SizedBox(height: 2),
                Text(
                  widget.series.metricName,
                  style: TextStyle(fontSize: 10, color: AppColors.textMuted, fontFamily: 'monospace'),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          // Trend indicator
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: trendColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(6),
              border: Border.all(color: trendColor.withValues(alpha: 0.25)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(trendIcon, size: 12, color: trendColor),
                const SizedBox(width: 4),
                Text(
                  '${trendPercent >= 0 ? '+' : ''}${trendPercent.toStringAsFixed(1)}%',
                  style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: trendColor),
                ),
              ],
            ),
          ),
          if (anomalyCount > 0) ...[
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.error.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: AppColors.error.withValues(alpha: 0.25)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.warning_amber, size: 12, color: AppColors.error),
                  const SizedBox(width: 4),
                  Text('$anomalyCount anomalies', style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w500, color: AppColors.error)),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStatsRow(double min, double max, double avg, double p95) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          _buildStatCard('Min', _formatValue(min), AppColors.info, Icons.arrow_downward),
          const SizedBox(width: 8),
          _buildStatCard('Max', _formatValue(max), AppColors.warning, Icons.arrow_upward),
          const SizedBox(width: 8),
          _buildStatCard('Avg', _formatValue(avg), AppColors.primaryTeal, Icons.remove),
          const SizedBox(width: 8),
          _buildStatCard('P95', _formatValue(p95), AppColors.primaryCyan, Icons.show_chart),
        ],
      ),
    );
  }

  Widget _buildStatCard(String label, String value, Color color, IconData icon) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withValues(alpha: 0.15)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 10, color: color),
                const SizedBox(width: 4),
                Text(label, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w500, color: AppColors.textMuted)),
              ],
            ),
            const SizedBox(height: 2),
            Text(value, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: color, fontFamily: 'monospace')),
          ],
        ),
      ),
    );
  }

  Widget _buildToggleRow() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          _buildToggle('Trend Line', _showTrendLine, (v) => setState(() => _showTrendLine = v), AppColors.warning),
          const SizedBox(width: 12),
          _buildToggle('Threshold', _showThreshold, (v) => setState(() => _showThreshold = v), AppColors.primaryCyan),
        ],
      ),
    );
  }

  Widget _buildToggle(String label, bool value, Function(bool) onChanged, Color color) {
    return GestureDetector(
      onTap: () => onChanged(!value),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: value ? color.withValues(alpha: 0.15) : Colors.white.withValues(alpha: 0.05),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: value ? color.withValues(alpha: 0.3) : AppColors.surfaceBorder),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(value ? Icons.check_box : Icons.check_box_outline_blank, size: 14, color: value ? color : AppColors.textMuted),
            const SizedBox(width: 6),
            Text(label, style: TextStyle(fontSize: 11, color: value ? color : AppColors.textMuted, fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }

  FlGridData _buildGridData() {
    return FlGridData(
      show: true,
      drawVerticalLine: false,
      horizontalInterval: null,
      getDrawingHorizontalLine: (value) {
        return FlLine(color: AppColors.surfaceBorder, strokeWidth: 0.5, dashArray: [4, 4]);
      },
    );
  }

  FlTitlesData _buildTitlesData(List<MetricPoint> sortedPoints) {
    final interval = (sortedPoints.length / 5).ceil();

    return FlTitlesData(
      bottomTitles: AxisTitles(
        sideTitles: SideTitles(
          showTitles: true,
          reservedSize: 28,
          interval: interval.toDouble(),
          getTitlesWidget: (value, meta) {
            int index = value.toInt();
            if (index >= 0 && index < sortedPoints.length && index % interval == 0) {
              return Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  DateFormat('HH:mm').format(sortedPoints[index].timestamp),
                  style: TextStyle(fontSize: 9, color: AppColors.textMuted),
                ),
              );
            }
            return const Text('');
          },
        ),
      ),
      leftTitles: AxisTitles(
        sideTitles: SideTitles(
          showTitles: true,
          reservedSize: 45,
          getTitlesWidget: (value, meta) {
            return Padding(
              padding: const EdgeInsets.only(right: 4),
              child: Text(
                _formatValue(value),
                style: TextStyle(fontSize: 9, color: AppColors.textMuted),
                textAlign: TextAlign.right,
              ),
            );
          },
        ),
      ),
      topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
      rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
    );
  }

  ExtraLinesData _buildExtraLines(double avg, double p95) {
    if (!_showThreshold) return ExtraLinesData();

    return ExtraLinesData(
      horizontalLines: [
        HorizontalLine(
          y: avg,
          color: AppColors.primaryTeal.withValues(alpha: 0.5),
          strokeWidth: 1,
          dashArray: [8, 4],
          label: HorizontalLineLabel(
            show: true,
            alignment: Alignment.topRight,
            style: TextStyle(fontSize: 9, color: AppColors.primaryTeal, fontWeight: FontWeight.w500),
            labelResolver: (line) => 'avg: ${_formatValue(avg)}',
          ),
        ),
        HorizontalLine(
          y: p95,
          color: AppColors.warning.withValues(alpha: 0.5),
          strokeWidth: 1,
          dashArray: [8, 4],
          label: HorizontalLineLabel(
            show: true,
            alignment: Alignment.topRight,
            style: TextStyle(fontSize: 9, color: AppColors.warning, fontWeight: FontWeight.w500),
            labelResolver: (line) => 'P95: ${_formatValue(p95)}',
          ),
        ),
      ],
    );
  }

  RangeAnnotations _buildAnomalyAnnotations(List<_AnomalyRegion> regions, int totalPoints, double minY, double maxY) {
    return RangeAnnotations(
      verticalRangeAnnotations: regions.map((region) {
        return VerticalRangeAnnotation(
          x1: region.startIndex.toDouble(),
          x2: (region.endIndex + 1).toDouble(),
          color: AppColors.error.withValues(alpha: 0.08),
        );
      }).toList(),
    );
  }

  LineTouchData _buildTouchData(List<MetricPoint> sortedPoints) {
    return LineTouchData(
      enabled: true,
      touchTooltipData: LineTouchTooltipData(
        getTooltipColor: (_) => AppColors.backgroundElevated,
        tooltipBorder: BorderSide(color: AppColors.surfaceBorder),
        tooltipBorderRadius: BorderRadius.circular(8),
        tooltipPadding: const EdgeInsets.all(12),
        getTooltipItems: (touchedSpots) {
          return touchedSpots.map((spot) {
            final index = spot.x.toInt();
            if (index < 0 || index >= sortedPoints.length) return null;
            final point = sortedPoints[index];
            return LineTooltipItem(
              '${DateFormat('MMM d, HH:mm:ss').format(point.timestamp)}\n${_formatValue(point.value)}${point.isAnomaly ? ' (Anomaly)' : ''}',
              TextStyle(
                color: point.isAnomaly ? AppColors.error : AppColors.textPrimary,
                fontSize: 11,
                fontWeight: FontWeight.w500,
              ),
            );
          }).toList();
        },
      ),
      handleBuiltInTouches: true,
      touchCallback: (event, response) {
        if (response?.lineBarSpots != null && response!.lineBarSpots!.isNotEmpty) {
          setState(() => _touchedIndex = response.lineBarSpots!.first.x.toInt());
        } else {
          setState(() => _touchedIndex = null);
        }
      },
    );
  }

  LineChartBarData _buildMainLineData(List<MetricPoint> sortedPoints) {
    return LineChartBarData(
      spots: sortedPoints.asMap().entries.map((e) {
        final animatedValue = e.value.value * _animation.value;
        return FlSpot(e.key.toDouble(), animatedValue);
      }).toList(),
      isCurved: true,
      curveSmoothness: 0.2,
      gradient: const LinearGradient(colors: [AppColors.primaryTeal, AppColors.primaryCyan]),
      barWidth: 2,
      isStrokeCapRound: true,
      belowBarData: BarAreaData(
        show: true,
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [AppColors.primaryTeal.withValues(alpha: 0.15), AppColors.primaryCyan.withValues(alpha: 0.02)],
        ),
      ),
      dotData: FlDotData(
        show: true,
        getDotPainter: (spot, percent, barData, index) {
          if (index >= sortedPoints.length) return FlDotCirclePainter(radius: 0, color: Colors.transparent, strokeWidth: 0, strokeColor: Colors.transparent);

          final point = sortedPoints[index];
          final isTouched = index == _touchedIndex;

          if (point.isAnomaly) {
            return FlDotCirclePainter(
              radius: isTouched ? 7 : 5,
              color: AppColors.error,
              strokeWidth: 2,
              strokeColor: Colors.white,
            );
          }

          if (isTouched) {
            return FlDotCirclePainter(radius: 5, color: AppColors.primaryTeal, strokeWidth: 2, strokeColor: Colors.white);
          }

          return FlDotCirclePainter(radius: 0, color: Colors.transparent, strokeWidth: 0, strokeColor: Colors.transparent);
        },
      ),
    );
  }

  LineChartBarData _buildTrendLineData(List<MetricPoint> sortedPoints, List<double> movingAvg) {
    return LineChartBarData(
      spots: movingAvg.asMap().entries.map((e) {
        final animatedValue = e.value * _animation.value;
        return FlSpot(e.key.toDouble(), animatedValue);
      }).toList(),
      isCurved: true,
      curveSmoothness: 0.3,
      color: AppColors.warning.withValues(alpha: 0.7),
      barWidth: 1.5,
      isStrokeCapRound: true,
      dotData: const FlDotData(show: false),
      dashArray: [6, 3],
    );
  }

  Widget _buildSparklineOverview(List<MetricPoint> points, List<_AnomalyRegion> anomalyRegions) {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 8),
      height: 32,
      child: CustomPaint(
        painter: _SparklinePainter(
          points: points,
          anomalyRegions: anomalyRegions,
          animation: _animation.value,
        ),
        child: Container(),
      ),
    );
  }

  Widget _buildLabelsFooter() {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.surfaceBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Resource Labels', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w600, color: AppColors.textMuted)),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: widget.series.labels.entries.take(6).map((e) {
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                decoration: BoxDecoration(
                  color: AppColors.primaryTeal.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text('${e.key}: ${e.value}', style: TextStyle(fontSize: 9, color: AppColors.textSecondary, fontFamily: 'monospace')),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}

class _AnomalyRegion {
  final int startIndex;
  final int endIndex;
  _AnomalyRegion(this.startIndex, this.endIndex);
}

class _SparklinePainter extends CustomPainter {
  final List<MetricPoint> points;
  final List<_AnomalyRegion> anomalyRegions;
  final double animation;

  _SparklinePainter({required this.points, required this.anomalyRegions, required this.animation});

  @override
  void paint(Canvas canvas, Size size) {
    if (points.isEmpty) return;

    final values = points.map((p) => p.value).toList();
    final minVal = values.reduce(math.min);
    final maxVal = values.reduce(math.max);
    final range = maxVal - minVal;

    // Draw background
    final bgPaint = Paint()..color = Colors.white.withValues(alpha: 0.03);
    canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromLTWH(0, 0, size.width, size.height), const Radius.circular(4)), bgPaint);

    // Draw anomaly regions
    for (final region in anomalyRegions) {
      final x1 = (region.startIndex / (points.length - 1)) * size.width;
      final x2 = ((region.endIndex + 1) / (points.length - 1)) * size.width;
      final regionPaint = Paint()..color = AppColors.error.withValues(alpha: 0.15);
      canvas.drawRect(Rect.fromLTRB(x1, 0, x2, size.height), regionPaint);
    }

    // Draw sparkline
    final linePath = Path();
    for (int i = 0; i < points.length; i++) {
      final x = (i / (points.length - 1)) * size.width;
      final normalizedY = range > 0 ? (points[i].value - minVal) / range : 0.5;
      final y = size.height - (normalizedY * size.height * 0.8 + size.height * 0.1) * animation;

      if (i == 0) {
        linePath.moveTo(x, y);
      } else {
        linePath.lineTo(x, y);
      }
    }

    final linePaint = Paint()
      ..color = AppColors.primaryTeal
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    canvas.drawPath(linePath, linePaint);

    // Draw anomaly dots
    final dotPaint = Paint()..color = AppColors.error;
    for (int i = 0; i < points.length; i++) {
      if (points[i].isAnomaly) {
        final x = (i / (points.length - 1)) * size.width;
        final normalizedY = range > 0 ? (points[i].value - minVal) / range : 0.5;
        final y = size.height - (normalizedY * size.height * 0.8 + size.height * 0.1) * animation;
        canvas.drawCircle(Offset(x, y), 3, dotPaint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _SparklinePainter oldDelegate) {
    return oldDelegate.animation != animation;
  }
}
