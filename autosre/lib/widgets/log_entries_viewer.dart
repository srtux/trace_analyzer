import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/adk_schema.dart';
import '../theme/app_theme.dart';

/// A Datadog-style log entries viewer with expandable JSON payloads.
class LogEntriesViewer extends StatefulWidget {
  final LogEntriesData data;

  const LogEntriesViewer({super.key, required this.data});

  @override
  State<LogEntriesViewer> createState() => _LogEntriesViewerState();
}

class _LogEntriesViewerState extends State<LogEntriesViewer>
    with SingleTickerProviderStateMixin {
  late AnimationController _animController;
  late Animation<double> _animation;
  final Set<String> _expandedIds = {};
  String _searchQuery = '';
  String? _filterSeverity;
  final TextEditingController _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

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
    _scrollController.dispose();
    super.dispose();
  }

  List<LogEntry> get _filteredEntries {
    return widget.data.entries.where((entry) {
      // Filter by severity
      if (_filterSeverity != null && entry.severity != _filterSeverity) {
        return false;
      }
      // Filter by search query
      if (_searchQuery.isNotEmpty) {
        final query = _searchQuery.toLowerCase();
        final payloadStr = entry.payload?.toString().toLowerCase() ?? '';
        final resourceStr = entry.resourceLabels.toString().toLowerCase();
        if (!payloadStr.contains(query) && !resourceStr.contains(query)) {
          return false;
        }
      }
      return true;
    }).toList();
  }

  Map<String, int> get _severityCounts {
    final counts = <String, int>{};
    for (final entry in widget.data.entries) {
      counts[entry.severity] = (counts[entry.severity] ?? 0) + 1;
    }
    return counts;
  }

  Color _getSeverityColor(String severity) {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
      case 'EMERGENCY':
      case 'ALERT':
        return const Color(0xFFFF1744);
      case 'ERROR':
        return AppColors.error;
      case 'WARNING':
        return AppColors.warning;
      case 'INFO':
      case 'NOTICE':
        return AppColors.info;
      case 'DEBUG':
        return AppColors.textMuted;
      default:
        return AppColors.textSecondary;
    }
  }

  IconData _getSeverityIcon(String severity) {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
      case 'EMERGENCY':
      case 'ALERT':
        return Icons.crisis_alert;
      case 'ERROR':
        return Icons.error;
      case 'WARNING':
        return Icons.warning_amber;
      case 'INFO':
      case 'NOTICE':
        return Icons.info_outline;
      case 'DEBUG':
        return Icons.bug_report_outlined;
      default:
        return Icons.circle_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildHeader(),
        const SizedBox(height: 10),
        _buildSearchBar(),
        const SizedBox(height: 8),
        _buildSeverityFilterChips(),
        const SizedBox(height: 8),
        Expanded(
          child: AnimatedBuilder(
            animation: _animation,
            builder: (context, child) {
              final entries = _filteredEntries;
              if (entries.isEmpty) {
                return _buildEmptyState();
              }
              return ListView.builder(
                controller: _scrollController,
                padding: const EdgeInsets.symmetric(horizontal: 12),
                itemCount: entries.length,
                itemBuilder: (context, index) {
                  return _buildLogEntryCard(entries[index], index);
                },
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildHeader() {
    final errorCount = _severityCounts['ERROR'] ?? 0;
    final warningCount = _severityCounts['WARNING'] ?? 0;
    final criticalCount = _severityCounts['CRITICAL'] ?? 0;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  AppColors.primaryBlue.withValues(alpha: 0.2),
                  AppColors.primaryCyan.withValues(alpha: 0.15),
                ],
              ),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.article_outlined, size: 18, color: AppColors.primaryBlue),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      'Log Entries',
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.primaryTeal.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        '${widget.data.entries.length} entries',
                        style: TextStyle(
                          fontSize: 10,
                          color: AppColors.primaryTeal,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                ),
                if (widget.data.filter != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    widget.data.filter!,
                    style: TextStyle(fontSize: 10, color: AppColors.textMuted, fontFamily: 'monospace'),
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ),
          ),
          if (criticalCount > 0) ...[
            _buildStatChip('$criticalCount critical', Icons.crisis_alert, const Color(0xFFFF1744)),
            const SizedBox(width: 6),
          ],
          if (errorCount > 0) ...[
            _buildStatChip('$errorCount errors', Icons.error_outline, AppColors.error),
            const SizedBox(width: 6),
          ],
          if (warningCount > 0)
            _buildStatChip('$warningCount warnings', Icons.warning_amber, AppColors.warning),
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

  Widget _buildSearchBar() {
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
                  hintText: 'Search logs...',
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
    final severities = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'];
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            Text('Filter:', style: TextStyle(fontSize: 10, color: AppColors.textMuted)),
            const SizedBox(width: 8),
            _buildFilterChip('All', null, widget.data.entries.length),
            ...severities.map((s) => Padding(
                  padding: const EdgeInsets.only(left: 6),
                  child: _buildFilterChip(s, s, _severityCounts[s] ?? 0),
                )),
          ],
        ),
      ),
    );
  }

  Widget _buildFilterChip(String label, String? severity, int count) {
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
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                color: isSelected ? color : AppColors.textMuted,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
              ),
            ),
            const SizedBox(width: 4),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
              decoration: BoxDecoration(
                color: (isSelected ? color : AppColors.textMuted).withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(3),
              ),
              child: Text(
                count.toString(),
                style: TextStyle(
                  fontSize: 9,
                  color: isSelected ? color : AppColors.textMuted,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ],
        ),
      ),
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
            child: Icon(Icons.search_off_outlined, size: 40, color: AppColors.textMuted),
          ),
          const SizedBox(height: 16),
          Text(
            _searchQuery.isNotEmpty || _filterSeverity != null
                ? 'No logs match your filters'
                : 'No log entries',
            style: TextStyle(color: AppColors.textMuted, fontSize: 14),
          ),
        ],
      ),
    );
  }

  Widget _buildLogEntryCard(LogEntry entry, int index) {
    final isExpanded = _expandedIds.contains(entry.insertId);
    final severityColor = _getSeverityColor(entry.severity);
    final staggerDelay = index / widget.data.entries.length;
    final animValue = ((_animation.value - staggerDelay * 0.3) / 0.7).clamp(0.0, 1.0);

    return AnimatedOpacity(
      duration: const Duration(milliseconds: 200),
      opacity: animValue,
      child: Container(
        margin: const EdgeInsets.only(bottom: 6),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.02),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: isExpanded ? severityColor.withValues(alpha: 0.3) : AppColors.surfaceBorder,
          ),
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header row (always visible)
            InkWell(
              onTap: () {
                setState(() {
                  if (isExpanded) {
                    _expandedIds.remove(entry.insertId);
                  } else {
                    _expandedIds.add(entry.insertId);
                  }
                });
              },
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Severity indicator
                    Container(
                      width: 4,
                      height: 40,
                      decoration: BoxDecoration(
                        color: severityColor,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                    const SizedBox(width: 10),
                    // Severity icon
                    Container(
                      padding: const EdgeInsets.all(6),
                      decoration: BoxDecoration(
                        color: severityColor.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Icon(_getSeverityIcon(entry.severity), size: 14, color: severityColor),
                    ),
                    const SizedBox(width: 10),
                    // Content
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Timestamp and severity badge
                          Row(
                            children: [
                              Text(
                                _formatTimestamp(entry.timestamp),
                                style: TextStyle(
                                  fontSize: 10,
                                  color: AppColors.textMuted,
                                  fontFamily: 'monospace',
                                ),
                              ),
                              const SizedBox(width: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                                decoration: BoxDecoration(
                                  color: severityColor.withValues(alpha: 0.15),
                                  borderRadius: BorderRadius.circular(3),
                                ),
                                child: Text(
                                  entry.severity,
                                  style: TextStyle(
                                    fontSize: 9,
                                    fontWeight: FontWeight.w600,
                                    color: severityColor,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                                decoration: BoxDecoration(
                                  color: AppColors.primaryTeal.withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(3),
                                ),
                                child: Text(
                                  entry.resourceType,
                                  style: TextStyle(
                                    fontSize: 9,
                                    color: AppColors.primaryTeal,
                                  ),
                                ),
                              ),
                              if (entry.isJsonPayload) ...[
                                const SizedBox(width: 8),
                                Icon(
                                  Icons.data_object,
                                  size: 12,
                                  color: AppColors.primaryCyan,
                                ),
                              ],
                            ],
                          ),
                          const SizedBox(height: 6),
                          // Message preview
                          Text(
                            entry.payloadPreview,
                            style: TextStyle(
                              fontSize: 12,
                              color: AppColors.textPrimary,
                              height: 1.4,
                            ),
                            maxLines: isExpanded ? null : 2,
                            overflow: isExpanded ? null : TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    // Expand icon
                    AnimatedRotation(
                      duration: const Duration(milliseconds: 200),
                      turns: isExpanded ? 0.5 : 0,
                      child: Icon(
                        Icons.keyboard_arrow_down,
                        size: 20,
                        color: AppColors.textMuted,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            // Expanded details
            if (isExpanded) _buildExpandedDetails(entry),
          ],
        ),
      ),
    );
  }

  Widget _buildExpandedDetails(LogEntry entry) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.2),
        border: Border(
          top: BorderSide(color: AppColors.surfaceBorder),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Resource labels
          if (entry.resourceLabels.isNotEmpty) ...[
            _buildDetailSection(
              'Resource Labels',
              Icons.label_outline,
              entry.resourceLabels.entries.map((e) => _buildLabelChip(e.key, e.value)).toList(),
            ),
          ],
          // Trace info
          if (entry.traceId != null || entry.spanId != null) ...[
            _buildDetailSection(
              'Trace Info',
              Icons.account_tree_outlined,
              [
                if (entry.traceId != null) _buildLabelChip('trace_id', entry.traceId!),
                if (entry.spanId != null) _buildLabelChip('span_id', entry.spanId!),
              ],
            ),
          ],
          // HTTP Request
          if (entry.httpRequest != null) ...[
            _buildDetailSection(
              'HTTP Request',
              Icons.http,
              [
                if (entry.httpRequest!['requestMethod'] != null)
                  _buildLabelChip('method', entry.httpRequest!['requestMethod'].toString()),
                if (entry.httpRequest!['status'] != null)
                  _buildLabelChip('status', entry.httpRequest!['status'].toString()),
                if (entry.httpRequest!['latency'] != null)
                  _buildLabelChip('latency', entry.httpRequest!['latency'].toString()),
              ],
            ),
          ],
          // Full JSON payload
          if (entry.isJsonPayload)
            _buildJsonPayloadSection(entry.payload as Map<String, dynamic>),
          // Actions
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                _buildActionButton('Copy Log', Icons.copy, () {
                  _copyToClipboard(context, _formatFullLog(entry));
                }),
                const SizedBox(width: 8),
                if (entry.isJsonPayload)
                  _buildActionButton('Copy JSON', Icons.data_object, () {
                    _copyToClipboard(
                      context,
                      const JsonEncoder.withIndent('  ').convert(entry.payload),
                    );
                  }),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailSection(String title, IconData icon, List<Widget> children) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 12, color: AppColors.textMuted),
              const SizedBox(width: 6),
              Text(
                title,
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textMuted,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Wrap(spacing: 6, runSpacing: 6, children: children),
        ],
      ),
    );
  }

  Widget _buildLabelChip(String key, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.primaryTeal.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: AppColors.primaryTeal.withValues(alpha: 0.15)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '$key:',
            style: TextStyle(
              fontSize: 10,
              color: AppColors.textMuted,
              fontFamily: 'monospace',
            ),
          ),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 10,
                color: AppColors.primaryTeal,
                fontFamily: 'monospace',
                fontWeight: FontWeight.w500,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildJsonPayloadSection(Map<String, dynamic> payload) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.data_object, size: 12, color: AppColors.primaryCyan),
              const SizedBox(width: 6),
              Text(
                'JSON Payload',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textMuted,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.black.withValues(alpha: 0.4),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.surfaceBorder.withValues(alpha: 0.5)),
            ),
            child: SelectableText(
              const JsonEncoder.withIndent('  ').convert(payload),
              style: TextStyle(
                fontSize: 11,
                color: AppColors.textSecondary,
                fontFamily: 'monospace',
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionButton(String label, IconData icon, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: AppColors.primaryTeal.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: AppColors.primaryTeal.withValues(alpha: 0.2)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 12, color: AppColors.primaryTeal),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                color: AppColors.primaryTeal,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _formatTimestamp(DateTime timestamp) {
    final now = DateTime.now();
    final diff = now.difference(timestamp);

    String timeStr;
    if (diff.inDays > 0) {
      timeStr = '${timestamp.month}/${timestamp.day} ${timestamp.hour.toString().padLeft(2, '0')}:${timestamp.minute.toString().padLeft(2, '0')}:${timestamp.second.toString().padLeft(2, '0')}';
    } else {
      timeStr = '${timestamp.hour.toString().padLeft(2, '0')}:${timestamp.minute.toString().padLeft(2, '0')}:${timestamp.second.toString().padLeft(2, '0')}.${timestamp.millisecond.toString().padLeft(3, '0')}';
    }
    return timeStr;
  }

  String _formatFullLog(LogEntry entry) {
    final buffer = StringBuffer();
    buffer.writeln('Timestamp: ${entry.timestamp.toIso8601String()}');
    buffer.writeln('Severity: ${entry.severity}');
    buffer.writeln('Resource: ${entry.resourceType}');
    buffer.writeln('Labels: ${entry.resourceLabels}');
    if (entry.traceId != null) buffer.writeln('Trace ID: ${entry.traceId}');
    if (entry.spanId != null) buffer.writeln('Span ID: ${entry.spanId}');
    buffer.writeln('---');
    if (entry.isJsonPayload) {
      buffer.writeln(const JsonEncoder.withIndent('  ').convert(entry.payload));
    } else {
      buffer.writeln(entry.payload?.toString() ?? '');
    }
    return buffer.toString();
  }

  void _copyToClipboard(BuildContext context, String text) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            Icon(Icons.check_circle, color: AppColors.success, size: 16),
            const SizedBox(width: 8),
            const Text('Copied to clipboard'),
          ],
        ),
        backgroundColor: AppColors.backgroundElevated,
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}
