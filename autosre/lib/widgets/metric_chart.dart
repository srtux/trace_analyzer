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

  @override
  Widget build(BuildContext context) {
    if (widget.series.points.isEmpty) {
      return _buildEmptyState();
    }

    final sortedPoints = List<MetricPoint>.from(widget.series.points)
      ..sort((a, b) => a.timestamp.compareTo(b.timestamp));

    final anomalyCount = sortedPoints.where((p) => p.isAnomaly).length;
    final maxValue = sortedPoints.map((p) => p.value).reduce((a, b) => a > b ? a : b);
    final minValue = sortedPoints.map((p) => p.value).reduce((a, b) => a < b ? a : b);
    final avgValue = sortedPoints.map((p) => p.value).reduce((a, b) => a + b) /
        sortedPoints.length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header
        _buildHeader(anomalyCount),

        const SizedBox(height: 12),

        // Stats row
        _buildStatsRow(minValue, maxValue, avgValue),

        const SizedBox(height: 16),

        // Chart
        Expanded(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(8, 8, 16, 8),
            child: AnimatedBuilder(
              animation: _animation,
              builder: (context, child) {
                return LineChart(
                  LineChartData(
                    gridData: _buildGridData(),
                    titlesData: _buildTitlesData(sortedPoints),
                    borderData: FlBorderData(show: false),
                    lineTouchData: _buildTouchData(sortedPoints),
                    lineBarsData: [
                      _buildLineBarData(sortedPoints),
                    ],
                    minY: minValue * 0.9,
                    maxY: maxValue * 1.1,
                  ),
                  duration: const Duration(milliseconds: 250),
                );
              },
            ),
          ),
        ),

        // Labels footer
        if (widget.series.labels.isNotEmpty) _buildLabelsFooter(),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.show_chart_outlined,
            size: 48,
            color: AppColors.textMuted,
          ),
          const SizedBox(height: 16),
          Text(
            'No metric data available',
            style: TextStyle(
              color: AppColors.textMuted,
              fontSize: 14,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(int anomalyCount) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: AppColors.primaryCyan.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(
              Icons.show_chart,
              size: 16,
              color: AppColors.primaryCyan,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Metric Chart',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                Text(
                  widget.series.metricName,
                  style: TextStyle(
                    fontSize: 11,
                    color: AppColors.textMuted,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          if (anomalyCount > 0)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: AppColors.error.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.error.withValues(alpha: 0.25)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.warning_amber, size: 14, color: AppColors.error),
                  const SizedBox(width: 6),
                  Text(
                    '$anomalyCount anomalies',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: AppColors.error,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildStatsRow(double min, double max, double avg) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          _buildStatItem('Min', min.toStringAsFixed(2), AppColors.info),
          const SizedBox(width: 16),
          _buildStatItem('Max', max.toStringAsFixed(2), AppColors.warning),
          const SizedBox(width: 16),
          _buildStatItem('Avg', avg.toStringAsFixed(2), AppColors.primaryTeal),
        ],
      ),
    );
  }

  Widget _buildStatItem(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w500,
              color: AppColors.textMuted,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: color,
              fontFamily: 'monospace',
            ),
          ),
        ],
      ),
    );
  }

  FlGridData _buildGridData() {
    return FlGridData(
      show: true,
      drawVerticalLine: true,
      horizontalInterval: 1,
      verticalInterval: 1,
      getDrawingHorizontalLine: (value) {
        return FlLine(
          color: AppColors.surfaceBorder,
          strokeWidth: 1,
          dashArray: [5, 5],
        );
      },
      getDrawingVerticalLine: (value) {
        return FlLine(
          color: AppColors.surfaceBorder,
          strokeWidth: 1,
          dashArray: [5, 5],
        );
      },
    );
  }

  FlTitlesData _buildTitlesData(List<MetricPoint> sortedPoints) {
    return FlTitlesData(
      bottomTitles: AxisTitles(
        sideTitles: SideTitles(
          showTitles: true,
          reservedSize: 32,
          interval: (sortedPoints.length / 5).ceil().toDouble(),
          getTitlesWidget: (value, meta) {
            int index = value.toInt();
            if (index >= 0 && index < sortedPoints.length) {
              return Padding(
                padding: const EdgeInsets.only(top: 8.0),
                child: Text(
                  DateFormat('HH:mm').format(sortedPoints[index].timestamp),
                  style: TextStyle(
                    fontSize: 10,
                    color: AppColors.textMuted,
                  ),
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
          reservedSize: 50,
          getTitlesWidget: (value, meta) {
            return Text(
              value.toStringAsFixed(1),
              style: TextStyle(
                fontSize: 10,
                color: AppColors.textMuted,
              ),
            );
          },
        ),
      ),
      topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
      rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
    );
  }

  LineTouchData _buildTouchData(List<MetricPoint> sortedPoints) {
    return LineTouchData(
      enabled: true,
      touchTooltipData: LineTouchTooltipData(
        getTooltipColor: (_) => AppColors.backgroundElevated,
        tooltipBorder: BorderSide(color: AppColors.surfaceBorder),
        tooltipRoundedRadius: 8,
        tooltipPadding: const EdgeInsets.all(12),
        getTooltipItems: (touchedSpots) {
          return touchedSpots.map((spot) {
            final point = sortedPoints[spot.x.toInt()];
            return LineTooltipItem(
              '${DateFormat('HH:mm:ss').format(point.timestamp)}\n${point.value.toStringAsFixed(2)}${point.isAnomaly ? ' (Anomaly)' : ''}',
              TextStyle(
                color: point.isAnomaly ? AppColors.error : AppColors.textPrimary,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            );
          }).toList();
        },
      ),
      handleBuiltInTouches: true,
      touchCallback: (event, response) {
        if (response?.lineBarSpots != null && response!.lineBarSpots!.isNotEmpty) {
          setState(() {
            _touchedIndex = response.lineBarSpots!.first.x.toInt();
          });
        } else {
          setState(() {
            _touchedIndex = null;
          });
        }
      },
    );
  }

  LineChartBarData _buildLineBarData(List<MetricPoint> sortedPoints) {
    return LineChartBarData(
      spots: sortedPoints.asMap().entries.map((e) {
        final animatedValue = e.value.value * _animation.value;
        return FlSpot(e.key.toDouble(), animatedValue);
      }).toList(),
      isCurved: true,
      curveSmoothness: 0.3,
      gradient: LinearGradient(
        colors: [AppColors.primaryTeal, AppColors.primaryCyan],
      ),
      barWidth: 2.5,
      isStrokeCapRound: true,
      belowBarData: BarAreaData(
        show: true,
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            AppColors.primaryTeal.withValues(alpha: 0.2),
            AppColors.primaryCyan.withValues(alpha: 0.05),
          ],
        ),
      ),
      dotData: FlDotData(
        show: true,
        getDotPainter: (spot, percent, barData, index) {
          final point = sortedPoints[index];
          final isTouched = index == _touchedIndex;

          if (point.isAnomaly) {
            return FlDotCirclePainter(
              radius: isTouched ? 8 : 6,
              color: AppColors.error,
              strokeWidth: 2,
              strokeColor: Colors.white,
            );
          }

          if (isTouched) {
            return FlDotCirclePainter(
              radius: 6,
              color: AppColors.primaryTeal,
              strokeWidth: 2,
              strokeColor: Colors.white,
            );
          }

          // Show dots only at intervals
          if (index % (sortedPoints.length ~/ 10 + 1) == 0) {
            return FlDotCirclePainter(
              radius: 3,
              color: AppColors.primaryTeal.withValues(alpha: 0.5),
              strokeWidth: 0,
              strokeColor: Colors.transparent,
            );
          }

          return FlDotCirclePainter(
            radius: 0,
            color: Colors.transparent,
            strokeWidth: 0,
            strokeColor: Colors.transparent,
          );
        },
      ),
    );
  }

  Widget _buildLabelsFooter() {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.surfaceBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Labels',
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: AppColors.textMuted,
            ),
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: widget.series.labels.entries.take(5).map((e) {
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.primaryTeal.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  '${e.key}: ${e.value}',
                  style: TextStyle(
                    fontSize: 10,
                    color: AppColors.textSecondary,
                    fontFamily: 'monospace',
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}
