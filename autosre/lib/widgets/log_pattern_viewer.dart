import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../models/adk_schema.dart';
import '../theme/app_theme.dart';

class LogPatternViewer extends StatefulWidget {
  final List<LogPattern> patterns;

  const LogPatternViewer({super.key, required this.patterns});

  @override
  State<LogPatternViewer> createState() => _LogPatternViewerState();
}

class _LogPatternViewerState extends State<LogPatternViewer>
    with SingleTickerProviderStateMixin {
  late AnimationController _animController;
  late Animation<double> _animation;
  String _sortBy = 'count';
  bool _sortAsc = false;
  int? _hoveredIndex;
  String? _selectedPattern;
  String _searchQuery = '';
  final TextEditingController _searchController = TextEditingController();
  String? _filterSeverity;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      duration: const Duration(milliseconds: 600),
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
    _searchController.dispose();
    super.dispose();
  }

  List<LogPattern> get _filteredAndSortedPatterns {
    var filtered = widget.patterns.where((p) {
      // Filter by search query
      if (_searchQuery.isNotEmpty &&
          !p.template.toLowerCase().contains(_searchQuery.toLowerCase())) {
        return false;
      }
      // Filter by severity
      if (_filterSeverity != null && _getDominantSeverity(p) != _filterSeverity) {
        return false;
      }
      return true;
    }).toList();

    filtered.sort((a, b) {
      int comparison;
      switch (_sortBy) {
        case 'count':
          comparison = a.count.compareTo(b.count);
          break;
        case 'severity':
          comparison = _getSeverityPriority(_getDominantSeverity(a))
              .compareTo(_getSeverityPriority(_getDominantSeverity(b)));
          break;
        default:
          comparison = a.template.compareTo(b.template);
      }
      return _sortAsc ? comparison : -comparison;
    });
    return filtered;
  }

  int _getSeverityPriority(String severity) {
    switch (severity.toUpperCase()) {
      case 'ERROR':
        return 4;
      case 'WARNING':
        return 3;
      case 'INFO':
        return 2;
      case 'DEBUG':
        return 1;
      default:
        return 0;
    }
  }

  String _getDominantSeverity(LogPattern pattern) {
    String dominantSeverity = 'INFO';
    int max = 0;
    pattern.severityCounts.forEach((k, v) {
      if (v > max) {
        max = v;
        dominantSeverity = k;
      }
    });
    return dominantSeverity;
  }

  Color _getSeverityColor(String severity) {
    switch (severity.toUpperCase()) {
      case 'ERROR':
        return AppColors.error;
      case 'WARNING':
        return AppColors.warning;
      case 'INFO':
        return AppColors.info;
      case 'DEBUG':
        return AppColors.textMuted;
      default:
        return AppColors.textSecondary;
    }
  }

  IconData _getSeverityIcon(String severity) {
    switch (severity.toUpperCase()) {
      case 'ERROR':
        return Icons.error;
      case 'WARNING':
        return Icons.warning_amber;
      case 'INFO':
        return Icons.info;
      case 'DEBUG':
        return Icons.bug_report;
      default:
        return Icons.circle;
    }
  }

  // Generate simulated frequency distribution for sparkline
  List<double> _generateFrequencyDistribution(int count) {
    final random = math.Random(count);
    List<double> distribution = [];
    for (int i = 0; i < 12; i++) {
      // Simulate a distribution that peaks somewhere
      double base = count / 12.0;
      double variance = base * (random.nextDouble() * 0.6 + 0.7);
      distribution.add(variance);
    }
    return distribution;
  }

  // Calculate trend indicator based on frequency distribution
  String _getTrend(List<double> distribution) {
    if (distribution.length < 4) return 'stable';
    double firstHalf = distribution.sublist(0, distribution.length ~/ 2).reduce((a, b) => a + b);
    double secondHalf = distribution.sublist(distribution.length ~/ 2).reduce((a, b) => a + b);
    double changePercent = ((secondHalf - firstHalf) / firstHalf) * 100;
    if (changePercent > 15) return 'up';
    if (changePercent < -15) return 'down';
    return 'stable';
  }

  @override
  Widget build(BuildContext context) {
    if (widget.patterns.isEmpty) {
      return _buildEmptyState();
    }

    final totalLogs = widget.patterns.map((p) => p.count).reduce((a, b) => a + b);
    final errorCount = widget.patterns
        .where((p) => _getDominantSeverity(p) == 'ERROR')
        .length;
    final warningCount = widget.patterns
        .where((p) => _getDominantSeverity(p) == 'WARNING')
        .length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildHeader(totalLogs, errorCount, warningCount),
        const SizedBox(height: 10),
        _buildSearchAndFilter(),
        const SizedBox(height: 8),
        _buildSeverityFilterChips(),
        const SizedBox(height: 8),
        _buildTableHeader(),
        Expanded(
          child: AnimatedBuilder(
            animation: _animation,
            builder: (context, child) {
              final patterns = _filteredAndSortedPatterns;
              if (patterns.isEmpty) {
                return Center(
                  child: Text(
                    'No patterns match your filters',
                    style: TextStyle(color: AppColors.textMuted, fontSize: 13),
                  ),
                );
              }
              return ListView.builder(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: patterns.length,
                itemBuilder: (context, index) {
                  return _buildPatternRow(patterns[index], index, patterns.length);
                },
              );
            },
          ),
        ),
        if (_selectedPattern != null)
          _buildSelectedPatternDetail(_filteredAndSortedPatterns.firstWhere(
            (p) => p.template == _selectedPattern,
            orElse: () => widget.patterns.first,
          )),
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
            child: Icon(Icons.article_outlined, size: 40, color: AppColors.textMuted),
          ),
          const SizedBox(height: 16),
          Text('No log patterns detected', style: TextStyle(color: AppColors.textMuted, fontSize: 14)),
        ],
      ),
    );
  }

  Widget _buildHeader(int totalLogs, int errorCount, int warningCount) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [AppColors.primaryBlue.withValues(alpha: 0.2), AppColors.primaryCyan.withValues(alpha: 0.15)],
              ),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.analytics, size: 18, color: AppColors.primaryBlue),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('Log Pattern Analysis', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.primaryTeal.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text('${widget.patterns.length} patterns', style: TextStyle(fontSize: 10, color: AppColors.primaryTeal, fontWeight: FontWeight.w500)),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text('$totalLogs total log entries analyzed', style: TextStyle(fontSize: 10, color: AppColors.textMuted)),
              ],
            ),
          ),
          if (errorCount > 0) _buildStatChip('$errorCount errors', Icons.error_outline, AppColors.error),
          if (warningCount > 0) ...[
            const SizedBox(width: 6),
            _buildStatChip('$warningCount warnings', Icons.warning_amber, AppColors.warning),
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

  Widget _buildSearchAndFilter() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Container(
        height: 40,
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.05),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppColors.surfaceBorder),
        ),
        child: Row(
          children: [
            const SizedBox(width: 12),
            Icon(Icons.search, size: 18, color: AppColors.textMuted),
            const SizedBox(width: 8),
            Expanded(
              child: TextField(
                controller: _searchController,
                onChanged: (value) => setState(() => _searchQuery = value),
                style: TextStyle(fontSize: 13, color: AppColors.textPrimary),
                decoration: InputDecoration(
                  hintText: 'Search patterns...',
                  hintStyle: TextStyle(color: AppColors.textMuted, fontSize: 13),
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.zero,
                  isDense: true,
                ),
              ),
            ),
            if (_searchQuery.isNotEmpty)
              IconButton(
                icon: Icon(Icons.close, size: 16, color: AppColors.textMuted),
                onPressed: () {
                  _searchController.clear();
                  setState(() => _searchQuery = '');
                },
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
              ),
            const SizedBox(width: 12),
          ],
        ),
      ),
    );
  }

  Widget _buildSeverityFilterChips() {
    final severities = ['ERROR', 'WARNING', 'INFO', 'DEBUG'];
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          Text('Filter:', style: TextStyle(fontSize: 10, color: AppColors.textMuted)),
          const SizedBox(width: 8),
          _buildFilterChip('All', null),
          ...severities.map((s) => Padding(
                padding: const EdgeInsets.only(left: 6),
                child: _buildFilterChip(s, s),
              )),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String label, String? severity) {
    final isSelected = _filterSeverity == severity;
    final color = severity != null ? _getSeverityColor(severity) : AppColors.primaryTeal;

    return GestureDetector(
      onTap: () => setState(() => _filterSeverity = severity),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: isSelected ? color.withValues(alpha: 0.2) : Colors.transparent,
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: isSelected ? color : AppColors.surfaceBorder),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 10,
            color: isSelected ? color : AppColors.textMuted,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
          ),
        ),
      ),
    );
  }

  Widget _buildTableHeader() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(10),
          topRight: Radius.circular(10),
        ),
        border: Border.all(color: AppColors.surfaceBorder),
      ),
      child: Row(
        children: [
          _buildHeaderCell('Trend', null, 50),
          _buildHeaderCell('Count', 'count', 60),
          _buildHeaderCell('Severity', 'severity', 80),
          const SizedBox(width: 8),
          Expanded(child: _buildHeaderCell('Pattern', 'template', null)),
          SizedBox(width: 80, child: Text('Frequency', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: AppColors.textMuted))),
        ],
      ),
    );
  }

  Widget _buildHeaderCell(String label, String? sortKey, double? width) {
    final isActive = sortKey != null && _sortBy == sortKey;

    Widget content = sortKey != null
        ? InkWell(
            onTap: () {
              setState(() {
                if (_sortBy == sortKey) {
                  _sortAsc = !_sortAsc;
                } else {
                  _sortBy = sortKey;
                  _sortAsc = false;
                }
              });
            },
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(label, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: isActive ? AppColors.primaryTeal : AppColors.textMuted)),
                const SizedBox(width: 2),
                Icon(
                  isActive ? (_sortAsc ? Icons.arrow_upward : Icons.arrow_downward) : Icons.unfold_more,
                  size: 12,
                  color: isActive ? AppColors.primaryTeal : AppColors.textMuted,
                ),
              ],
            ),
          )
        : Text(label, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: AppColors.textMuted));

    if (width != null) {
      return SizedBox(width: width, child: content);
    }
    return content;
  }

  Widget _buildPatternRow(LogPattern pattern, int index, int total) {
    final severity = _getDominantSeverity(pattern);
    final severityColor = _getSeverityColor(severity);
    final isHovered = _hoveredIndex == index;
    final isSelected = _selectedPattern == pattern.template;
    final distribution = _generateFrequencyDistribution(pattern.count);
    final trend = _getTrend(distribution);

    final staggerDelay = index / total;
    final animValue = ((_animation.value - staggerDelay * 0.3) / 0.7).clamp(0.0, 1.0);

    return MouseRegion(
      onEnter: (_) => setState(() => _hoveredIndex = index),
      onExit: (_) => setState(() => _hoveredIndex = null),
      child: GestureDetector(
        onTap: () => setState(() {
          _selectedPattern = _selectedPattern == pattern.template ? null : pattern.template;
        }),
        child: AnimatedOpacity(
          duration: const Duration(milliseconds: 200),
          opacity: animValue,
          child: Container(
            margin: const EdgeInsets.only(bottom: 1),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: isSelected
                  ? severityColor.withValues(alpha: 0.1)
                  : isHovered
                      ? Colors.white.withValues(alpha: 0.04)
                      : Colors.white.withValues(alpha: 0.015),
              border: Border(
                left: BorderSide(color: isSelected ? severityColor : Colors.transparent, width: 3),
                right: BorderSide(color: AppColors.surfaceBorder),
                bottom: BorderSide(color: AppColors.surfaceBorder),
              ),
            ),
            child: Row(
              children: [
                // Trend indicator
                SizedBox(
                  width: 50,
                  child: _buildTrendIndicator(trend),
                ),

                // Count
                SizedBox(
                  width: 60,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: AppColors.primaryTeal.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      _formatCount(pattern.count),
                      style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.primaryTeal, fontFamily: 'monospace'),
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),

                // Severity badge
                SizedBox(
                  width: 80,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                    decoration: BoxDecoration(
                      color: severityColor.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: severityColor.withValues(alpha: 0.3)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(_getSeverityIcon(severity), size: 10, color: severityColor),
                        const SizedBox(width: 3),
                        Text(severity, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w600, color: severityColor)),
                      ],
                    ),
                  ),
                ),

                const SizedBox(width: 8),

                // Pattern template with syntax highlighting
                Expanded(
                  child: _buildHighlightedTemplate(pattern.template),
                ),

                // Mini sparkline
                SizedBox(
                  width: 80,
                  height: 24,
                  child: CustomPaint(
                    painter: _FrequencySparklinePainter(
                      values: distribution,
                      color: severityColor,
                      animation: animValue,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTrendIndicator(String trend) {
    Color color;
    IconData icon;
    String label;

    switch (trend) {
      case 'up':
        color = AppColors.error;
        icon = Icons.trending_up;
        label = 'Up';
        break;
      case 'down':
        color = AppColors.success;
        icon = Icons.trending_down;
        label = 'Down';
        break;
      default:
        color = AppColors.textMuted;
        icon = Icons.trending_flat;
        label = 'Stable';
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: color),
        const SizedBox(width: 2),
        Text(label, style: TextStyle(fontSize: 9, color: color, fontWeight: FontWeight.w500)),
      ],
    );
  }

  String _formatCount(int count) {
    if (count >= 1000000) return '${(count / 1000000).toStringAsFixed(1)}M';
    if (count >= 1000) return '${(count / 1000).toStringAsFixed(1)}K';
    return count.toString();
  }

  Widget _buildHighlightedTemplate(String template) {
    // Parse template and highlight placeholders like <*>, {var}, etc.
    final regex = RegExp(r'(<\*>|\{[^}]+\}|\[[^\]]+\]|%[a-zA-Z]+)');
    final matches = regex.allMatches(template);

    if (matches.isEmpty) {
      return Text(
        template,
        style: TextStyle(fontSize: 11, color: AppColors.textSecondary, fontFamily: 'monospace'),
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      );
    }

    List<InlineSpan> spans = [];
    int lastEnd = 0;

    for (final match in matches) {
      if (match.start > lastEnd) {
        spans.add(TextSpan(
          text: template.substring(lastEnd, match.start),
          style: TextStyle(fontSize: 11, color: AppColors.textSecondary, fontFamily: 'monospace'),
        ));
      }
      spans.add(TextSpan(
        text: match.group(0),
        style: TextStyle(fontSize: 11, color: AppColors.primaryCyan, fontFamily: 'monospace', fontWeight: FontWeight.w500),
      ));
      lastEnd = match.end;
    }

    if (lastEnd < template.length) {
      spans.add(TextSpan(
        text: template.substring(lastEnd),
        style: TextStyle(fontSize: 11, color: AppColors.textSecondary, fontFamily: 'monospace'),
      ));
    }

    return RichText(
      text: TextSpan(children: spans),
      maxLines: 2,
      overflow: TextOverflow.ellipsis,
    );
  }

  Widget _buildSelectedPatternDetail(LogPattern pattern) {
    final severity = _getDominantSeverity(pattern);
    final severityColor = _getSeverityColor(severity);
    final distribution = _generateFrequencyDistribution(pattern.count);

    return Container(
      margin: const EdgeInsets.all(12),
      padding: const EdgeInsets.all(14),
      decoration: GlassDecoration.elevated(
        borderRadius: 12,
        withGlow: severity == 'ERROR',
        glowColor: severityColor,
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
                  color: severityColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Icon(_getSeverityIcon(severity), size: 16, color: severityColor),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Pattern Details', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
                    Text('${pattern.count} occurrences', style: TextStyle(fontSize: 10, color: AppColors.textMuted)),
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.close, size: 16),
                onPressed: () => setState(() => _selectedPattern = null),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                color: AppColors.textMuted,
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Template with full highlighting
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.black.withValues(alpha: 0.3),
              borderRadius: BorderRadius.circular(8),
            ),
            child: SelectableText.rich(
              TextSpan(
                children: _buildHighlightedSpans(pattern.template),
              ),
            ),
          ),

          const SizedBox(height: 12),

          // Frequency distribution chart
          Text('Frequency Distribution', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: AppColors.textMuted)),
          const SizedBox(height: 6),
          SizedBox(
            height: 40,
            child: CustomPaint(
              painter: _FrequencyBarPainter(values: distribution, color: severityColor),
              child: Container(),
            ),
          ),

          const SizedBox(height: 12),

          // Severity breakdown
          Text('Severity Breakdown', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: AppColors.textMuted)),
          const SizedBox(height: 6),
          _buildSeverityBreakdownBar(pattern),
        ],
      ),
    );
  }

  List<TextSpan> _buildHighlightedSpans(String template) {
    final regex = RegExp(r'(<\*>|\{[^}]+\}|\[[^\]]+\]|%[a-zA-Z]+)');
    final matches = regex.allMatches(template);
    List<TextSpan> spans = [];
    int lastEnd = 0;

    for (final match in matches) {
      if (match.start > lastEnd) {
        spans.add(TextSpan(
          text: template.substring(lastEnd, match.start),
          style: TextStyle(fontSize: 12, color: AppColors.textSecondary, fontFamily: 'monospace', height: 1.5),
        ));
      }
      spans.add(TextSpan(
        text: match.group(0),
        style: TextStyle(fontSize: 12, color: AppColors.primaryCyan, fontFamily: 'monospace', fontWeight: FontWeight.w600, backgroundColor: AppColors.primaryCyan.withValues(alpha: 0.1), height: 1.5),
      ));
      lastEnd = match.end;
    }

    if (lastEnd < template.length) {
      spans.add(TextSpan(
        text: template.substring(lastEnd),
        style: TextStyle(fontSize: 12, color: AppColors.textSecondary, fontFamily: 'monospace', height: 1.5),
      ));
    }

    return spans;
  }

  Widget _buildSeverityBreakdownBar(LogPattern pattern) {
    final total = pattern.severityCounts.values.fold(0, (a, b) => a + b);
    if (total == 0) return const SizedBox.shrink();

    return Column(
      children: [
        // Stacked bar
        Container(
          height: 8,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(4),
          ),
          clipBehavior: Clip.antiAlias,
          child: Row(
            children: pattern.severityCounts.entries.map((e) {
              final percent = e.value / total;
              return Expanded(
                flex: (percent * 100).round(),
                child: Container(color: _getSeverityColor(e.key)),
              );
            }).toList(),
          ),
        ),
        const SizedBox(height: 8),
        // Legend
        Wrap(
          spacing: 12,
          runSpacing: 6,
          children: pattern.severityCounts.entries.map((e) {
            final color = _getSeverityColor(e.key);
            final percent = (e.value / total * 100).toStringAsFixed(1);
            return Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(width: 8, height: 8, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
                const SizedBox(width: 4),
                Text('${e.key}: ${e.value} ($percent%)', style: TextStyle(fontSize: 10, color: AppColors.textSecondary)),
              ],
            );
          }).toList(),
        ),
      ],
    );
  }
}

class _FrequencySparklinePainter extends CustomPainter {
  final List<double> values;
  final Color color;
  final double animation;

  _FrequencySparklinePainter({required this.values, required this.color, required this.animation});

  @override
  void paint(Canvas canvas, Size size) {
    if (values.isEmpty) return;

    final maxVal = values.reduce(math.max);
    if (maxVal == 0) return;

    final barWidth = size.width / values.length - 1;
    final paint = Paint()..color = color.withValues(alpha: 0.6);

    for (int i = 0; i < values.length; i++) {
      final normalizedHeight = (values[i] / maxVal) * size.height * animation;
      final rect = Rect.fromLTWH(
        i * (barWidth + 1),
        size.height - normalizedHeight,
        barWidth,
        normalizedHeight,
      );
      canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(1)), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _FrequencySparklinePainter oldDelegate) {
    return oldDelegate.animation != animation;
  }
}

class _FrequencyBarPainter extends CustomPainter {
  final List<double> values;
  final Color color;

  _FrequencyBarPainter({required this.values, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    if (values.isEmpty) return;

    final maxVal = values.reduce(math.max);
    if (maxVal == 0) return;

    final barWidth = size.width / values.length - 2;

    for (int i = 0; i < values.length; i++) {
      final normalizedHeight = (values[i] / maxVal) * size.height;
      final rect = Rect.fromLTWH(
        i * (barWidth + 2),
        size.height - normalizedHeight,
        barWidth,
        normalizedHeight,
      );

      final gradient = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [color, color.withValues(alpha: 0.5)],
      );

      final paint = Paint()..shader = gradient.createShader(rect);
      canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(2)), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
