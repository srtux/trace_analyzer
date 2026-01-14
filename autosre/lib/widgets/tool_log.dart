import 'dart:convert';
import 'package:flutter/material.dart';
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

  @override
  Widget build(BuildContext context) {
    final isRunning = widget.log.status == 'running';
    final isError = widget.log.status == 'error';
    final completed = widget.log.status == 'completed';

    Color statusColor;
    IconData statusIcon;

    if (isRunning) {
      statusColor = AppColors.primaryBlue;
      statusIcon = Icons.sync;
    } else if (isError) {
      statusColor = AppColors.error;
      statusIcon = Icons.error_outline;
    } else {
      statusColor = AppColors.success;
      statusIcon = Icons.check_circle_outline;
    }

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
                    child: Text(
                      'Tool: ${widget.log.toolName}',
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontWeight: FontWeight.w600,
                        fontSize: 13,
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ),
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
          if (_isExpanded || isRunning) // Auto-show args if running or expanded
            Container(
              width: double.infinity,
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Divider(height: 1, color: AppColors.surfaceBorder),
                  const SizedBox(height: 12),
                  const Text(
                    'Input:',
                    style: TextStyle(
                      color: AppColors.textMuted,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 4),
                  _buildCodeBlock(jsonEncode(widget.log.args)),
                  if (completed && widget.log.result != null) ...[
                    const SizedBox(height: 12),
                    const Text(
                      'Output:',
                      style: TextStyle(
                        color: AppColors.textMuted,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    _buildCodeBlock(widget.log.result!),
                  ],
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildCodeBlock(String content) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        content,
        style: const TextStyle(
          fontFamily: 'monospace',
          fontSize: 12,
          color: AppColors.textSecondary,
        ),
      ),
    );
  }
}
