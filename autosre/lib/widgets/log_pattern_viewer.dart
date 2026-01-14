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
    super.dispose();
  }

  List<LogPattern> get _sortedPatterns {
    final sorted = List<LogPattern>.from(widget.patterns);
    sorted.sort((a, b) {
      int comparison;
      switch (_sortBy) {
        case 'count':
          comparison = a.count.compareTo(b.count);
          break;
        case 'severity':
          comparison = _getDominantSeverity(a).compareTo(_getDominantSeverity(b));
          break;
        default:
          comparison = a.template.compareTo(b.template);
      }
      return _sortAsc ? comparison : -comparison;
    });
    return sorted;
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
        return Icons.error_outline;
      case 'WARNING':
        return Icons.warning_amber_outlined;
      case 'INFO':
        return Icons.info_outline;
      case 'DEBUG':
        return Icons.bug_report_outlined;
      default:
        return Icons.circle_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.patterns.isEmpty) {
      return _buildEmptyState();
    }

    final errorCount = widget.patterns
        .where((p) => _getDominantSeverity(p) == 'ERROR')
        .length;
    final warningCount = widget.patterns
        .where((p) => _getDominantSeverity(p) == 'WARNING')
        .length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header
        _buildHeader(errorCount, warningCount),

        const SizedBox(height: 12),

        // Table header
        _buildTableHeader(),

        // Pattern list
        Expanded(
          child: AnimatedBuilder(
            animation: _animation,
            builder: (context, child) {
              return ListView.builder(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: _sortedPatterns.length,
                itemBuilder: (context, index) {
                  return _buildPatternRow(_sortedPatterns[index], index);
                },
              );
            },
          ),
        ),

        // Selected pattern detail
        if (_selectedPattern != null)
          _buildSelectedPatternDetail(_sortedPatterns.firstWhere(
            (p) => p.template == _selectedPattern,
          )),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.article_outlined,
            size: 48,
            color: AppColors.textMuted,
          ),
          const SizedBox(height: 16),
          Text(
            'No significant log patterns found',
            style: TextStyle(
              color: AppColors.textMuted,
              fontSize: 14,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(int errorCount, int warningCount) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: AppColors.primaryBlue.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(
              Icons.article,
              size: 16,
              color: AppColors.primaryBlue,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Log Patterns',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                Text(
                  '${widget.patterns.length} patterns detected',
                  style: TextStyle(
                    fontSize: 11,
                    color: AppColors.textMuted,
                  ),
                ),
              ],
            ),
          ),
          if (errorCount > 0)
            _buildBadge('$errorCount errors', AppColors.error),
          if (warningCount > 0) ...[
            const SizedBox(width: 8),
            _buildBadge('$warningCount warnings', AppColors.warning),
          ],
        ],
      ),
    );
  }

  Widget _buildBadge(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w500,
          color: color,
        ),
      ),
    );
  }

  Widget _buildTableHeader() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(12),
          topRight: Radius.circular(12),
        ),
        border: Border.all(color: AppColors.surfaceBorder),
      ),
      child: Row(
        children: [
          _buildHeaderCell('Count', 'count', 70),
          _buildHeaderCell('Severity', 'severity', 100),
          Expanded(child: _buildHeaderCell('Pattern Template', 'template', null)),
        ],
      ),
    );
  }

  Widget _buildHeaderCell(String label, String sortKey, double? width) {
    final isActive = _sortBy == sortKey;

    Widget content = InkWell(
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
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: isActive ? AppColors.primaryTeal : AppColors.textMuted,
            ),
          ),
          const SizedBox(width: 4),
          Icon(
            isActive
                ? (_sortAsc ? Icons.arrow_upward : Icons.arrow_downward)
                : Icons.unfold_more,
            size: 14,
            color: isActive ? AppColors.primaryTeal : AppColors.textMuted,
          ),
        ],
      ),
    );

    if (width != null) {
      return SizedBox(width: width, child: content);
    }
    return content;
  }

  Widget _buildPatternRow(LogPattern pattern, int index) {
    final severity = _getDominantSeverity(pattern);
    final severityColor = _getSeverityColor(severity);
    final isHovered = _hoveredIndex == index;
    final isSelected = _selectedPattern == pattern.template;

    // Stagger animation
    final staggerDelay = index / widget.patterns.length;
    final animValue = ((_animation.value - staggerDelay * 0.3) / 0.7).clamp(0.0, 1.0);

    return MouseRegion(
      onEnter: (_) => setState(() => _hoveredIndex = index),
      onExit: (_) => setState(() => _hoveredIndex = null),
      child: GestureDetector(
        onTap: () => setState(() {
          _selectedPattern =
              _selectedPattern == pattern.template ? null : pattern.template;
        }),
        child: AnimatedOpacity(
          duration: const Duration(milliseconds: 200),
          opacity: animValue,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            margin: const EdgeInsets.only(bottom: 2),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: isSelected
                  ? AppColors.primaryTeal.withValues(alpha: 0.08)
                  : isHovered
                      ? Colors.white.withValues(alpha: 0.04)
                      : Colors.white.withValues(alpha: 0.02),
              border: Border(
                left: BorderSide(
                  color: isSelected
                      ? AppColors.primaryTeal
                      : Colors.transparent,
                  width: 3,
                ),
                right: BorderSide(color: AppColors.surfaceBorder),
                bottom: BorderSide(color: AppColors.surfaceBorder),
              ),
            ),
            child: Row(
              children: [
                // Count
                SizedBox(
                  width: 70,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.primaryTeal.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      pattern.count.toString(),
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppColors.primaryTeal,
                        fontFamily: 'monospace',
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),

                // Severity
                SizedBox(
                  width: 100,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: severityColor.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: severityColor.withValues(alpha: 0.3),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          _getSeverityIcon(severity),
                          size: 12,
                          color: severityColor,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          severity,
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                            color: severityColor,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

                const SizedBox(width: 16),

                // Pattern template
                Expanded(
                  child: Text(
                    pattern.template,
                    style: TextStyle(
                      fontSize: 12,
                      color: AppColors.textSecondary,
                      fontFamily: 'monospace',
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSelectedPatternDetail(LogPattern pattern) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: GlassDecoration.elevated(borderRadius: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.pattern,
                size: 16,
                color: AppColors.primaryTeal,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Pattern Details',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.close, size: 18),
                onPressed: () => setState(() => _selectedPattern = null),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                color: AppColors.textMuted,
              ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.black.withValues(alpha: 0.3),
              borderRadius: BorderRadius.circular(8),
            ),
            child: SelectableText(
              pattern.template,
              style: TextStyle(
                fontSize: 12,
                color: AppColors.textSecondary,
                fontFamily: 'monospace',
                height: 1.5,
              ),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'Severity Breakdown',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppColors.textMuted,
            ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 12,
            runSpacing: 8,
            children: pattern.severityCounts.entries.map((e) {
              final color = _getSeverityColor(e.key);
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: color.withValues(alpha: 0.3)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      e.key,
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                        color: color,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        e.value.toString(),
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: color,
                          fontFamily: 'monospace',
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}
