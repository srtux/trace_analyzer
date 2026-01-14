import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/adk_schema.dart';
import '../theme/app_theme.dart';

class ToolLogWidget extends StatefulWidget {
  final ToolLog log;

  const ToolLogWidget({super.key, required this.log});

  @override
  State<ToolLogWidget> createState() => _ToolLogWidgetState();
}

class _ToolLogWidgetState extends State<ToolLogWidget> {
  bool _isExpanded = false;

  /// Pretty-print JSON with proper indentation
  String _formatJson(dynamic data) {
    if (data == null) return 'null';

    try {
      // If it's already a string, try to parse it as JSON first
      if (data is String) {
        try {
          final parsed = json.decode(data);
          return const JsonEncoder.withIndent('  ').convert(parsed);
        } catch (_) {
          // Not valid JSON, return as-is but truncate if too long
          if (data.length > 2000) {
            return '${data.substring(0, 2000)}\n... (truncated ${data.length - 2000} chars)';
          }
          return data;
        }
      }

      // Convert maps/lists to pretty JSON
      if (data is Map || data is List) {
        final formatted = const JsonEncoder.withIndent('  ').convert(data);
        if (formatted.length > 3000) {
          return '${formatted.substring(0, 3000)}\n... (truncated ${formatted.length - 3000} chars)';
        }
        return formatted;
      }

      // Fallback: just stringify
      final str = data.toString();
      if (str.length > 2000) {
        return '${str.substring(0, 2000)}\n... (truncated ${str.length - 2000} chars)';
      }
      return str;
    } catch (e) {
      return 'Error formatting: $e';
    }
  }

  /// Build a syntax-highlighted JSON display
  Widget _buildHighlightedJson(String jsonStr) {
    // Simple syntax highlighting for JSON
    final List<TextSpan> spans = [];
    final regex = RegExp(
      r'("(?:[^"\\]|\\.)*")\s*:?|(\d+\.?\d*)|(\btrue\b|\bfalse\b|\bnull\b)|([{}\[\],:])',
      multiLine: true,
    );

    int lastEnd = 0;
    for (final match in regex.allMatches(jsonStr)) {
      // Add any text before this match
      if (match.start > lastEnd) {
        spans.add(TextSpan(
          text: jsonStr.substring(lastEnd, match.start),
          style: TextStyle(color: AppColors.textSecondary, fontFamily: 'monospace', fontSize: 11),
        ));
      }

      final matchStr = match.group(0) ?? '';
      Color color;

      if (match.group(1) != null) {
        // String - check if it's a key (followed by :) or value
        if (matchStr.endsWith(':')) {
          color = AppColors.primaryCyan; // Key color
        } else {
          color = AppColors.success; // String value color
        }
      } else if (match.group(2) != null) {
        color = AppColors.warning; // Number color
      } else if (match.group(3) != null) {
        color = AppColors.primaryBlue; // Boolean/null color
      } else {
        color = AppColors.textMuted; // Punctuation color
      }

      spans.add(TextSpan(
        text: matchStr,
        style: TextStyle(color: color, fontFamily: 'monospace', fontSize: 11),
      ));

      lastEnd = match.end;
    }

    // Add remaining text
    if (lastEnd < jsonStr.length) {
      spans.add(TextSpan(
        text: jsonStr.substring(lastEnd),
        style: TextStyle(color: AppColors.textSecondary, fontFamily: 'monospace', fontSize: 11),
      ));
    }

    return SelectableText.rich(
      TextSpan(children: spans),
      style: const TextStyle(height: 1.4),
    );
  }

  void _copyToClipboard(String text, String label) {
    Clipboard.setData(ClipboardData(text: text));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.check, color: Colors.white, size: 16),
              const SizedBox(width: 8),
              Text('Copied $label to clipboard'),
            ],
          ),
          backgroundColor: AppColors.success.withValues(alpha: 0.9),
          duration: const Duration(seconds: 2),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final isRunning = widget.log.status == 'running';
    final isError = widget.log.status == 'error';
    final completed = widget.log.status == 'completed';

    Color statusColor;
    IconData statusIcon;
    String statusLabel;

    if (isRunning) {
      statusColor = AppColors.primaryBlue;
      statusIcon = Icons.sync;
      statusLabel = 'Running';
    } else if (isError) {
      statusColor = AppColors.error;
      statusIcon = Icons.error_outline;
      statusLabel = 'Error';
    } else {
      statusColor = AppColors.success;
      statusIcon = Icons.check_circle_outline;
      statusLabel = 'Completed';
    }

    final formattedArgs = _formatJson(widget.log.args);
    final formattedResult = widget.log.result != null ? _formatJson(widget.log.result) : null;

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: statusColor.withValues(alpha: 0.3),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          InkWell(
            onTap: () {
              setState(() {
                _isExpanded = !_isExpanded;
              });
            },
            borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  if (isRunning)
                    SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(statusColor),
                      ),
                    )
                  else
                    Icon(statusIcon, color: statusColor, size: 18),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.log.toolName,
                          style: const TextStyle(
                            fontFamily: 'monospace',
                            fontWeight: FontWeight.w600,
                            fontSize: 13,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          statusLabel,
                          style: TextStyle(
                            fontSize: 10,
                            color: statusColor,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: statusColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: statusColor.withValues(alpha: 0.2)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.build_outlined, size: 10, color: statusColor),
                        const SizedBox(width: 4),
                        Text('Tool', style: TextStyle(fontSize: 9, color: statusColor, fontWeight: FontWeight.w500)),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Icon(
                    _isExpanded ? Icons.expand_less : Icons.expand_more,
                    color: AppColors.textMuted,
                    size: 20,
                  ),
                ],
              ),
            ),
          ),

          // Expanded Content
          if (_isExpanded || isRunning)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Divider(height: 1, color: AppColors.surfaceBorder),
                  const SizedBox(height: 12),

                  // Input section
                  Row(
                    children: [
                      Icon(Icons.input, size: 12, color: AppColors.primaryCyan),
                      const SizedBox(width: 6),
                      const Text(
                        'Input Arguments',
                        style: TextStyle(
                          color: AppColors.textMuted,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const Spacer(),
                      InkWell(
                        onTap: () => _copyToClipboard(formattedArgs, 'input'),
                        borderRadius: BorderRadius.circular(4),
                        child: Padding(
                          padding: const EdgeInsets.all(4),
                          child: Icon(Icons.copy, size: 14, color: AppColors.textMuted),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  _buildCodeBlock(formattedArgs),

                  if (completed && formattedResult != null) ...[
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Icon(Icons.output, size: 12, color: AppColors.success),
                        const SizedBox(width: 6),
                        const Text(
                          'Output Result',
                          style: TextStyle(
                            color: AppColors.textMuted,
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const Spacer(),
                        InkWell(
                          onTap: () => _copyToClipboard(formattedResult, 'output'),
                          borderRadius: BorderRadius.circular(4),
                          child: Padding(
                            padding: const EdgeInsets.all(4),
                            child: Icon(Icons.copy, size: 14, color: AppColors.textMuted),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    _buildCodeBlock(formattedResult, maxHeight: 300),
                  ],

                  if (isError && widget.log.result != null) ...[
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Icon(Icons.error_outline, size: 12, color: AppColors.error),
                        const SizedBox(width: 6),
                        const Text(
                          'Error Details',
                          style: TextStyle(
                            color: AppColors.error,
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    _buildCodeBlock(formattedResult!, isError: true),
                  ],
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildCodeBlock(String content, {double? maxHeight, bool isError = false}) {
    return Container(
      width: double.infinity,
      constraints: maxHeight != null ? BoxConstraints(maxHeight: maxHeight) : null,
      decoration: BoxDecoration(
        color: isError
            ? AppColors.error.withValues(alpha: 0.1)
            : Colors.black.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(8),
        border: isError ? Border.all(color: AppColors.error.withValues(alpha: 0.3)) : null,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(12),
          child: _buildHighlightedJson(content),
        ),
      ),
    );
  }
}
