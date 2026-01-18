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

class _ToolLogWidgetState extends State<ToolLogWidget>
    with SingleTickerProviderStateMixin {
  bool _isExpanded = false;
  late AnimationController _animationController;
  late Animation<double> _expandAnimation;
  late Animation<double> _rotateAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 200),
      vsync: this,
    );
    _expandAnimation = CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeOutCubic,
    );
    _rotateAnimation = Tween<double>(begin: 0, end: 0.5).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeOutCubic),
    );

    // Auto-expand if running
    if (widget.log.status == 'running') {
      _isExpanded = true;
      _animationController.value = 1.0;
    }
  }

  @override
  void didUpdateWidget(ToolLogWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Auto-expand when status changes to running
    if (widget.log.status == 'running' && !_isExpanded) {
      _toggleExpand();
    }
    // Auto-collapse when status changes to completed to reduce noise
    if (widget.log.status == 'completed' && _isExpanded && oldWidget.log.status == 'running') {
      _toggleExpand();
    }
  }

  void _toggleExpand() {
    setState(() {
      _isExpanded = !_isExpanded;
      if (_isExpanded) {
        _animationController.forward();
      } else {
        _animationController.reverse();
      }
    });
  }

  void _copyToClipboard(String content, String label) {
    Clipboard.setData(ClipboardData(text: content));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            Icon(Icons.check_circle, color: AppColors.success, size: 18),
            const SizedBox(width: 8),
            Text('$label copied to clipboard'),
          ],
        ),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        backgroundColor: AppColors.backgroundElevated,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
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
      statusColor = AppColors.info;
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

    // Compact collapsed view vs expanded view
    return AnimatedContainer(
      duration: const Duration(milliseconds: 150),
      margin: EdgeInsets.symmetric(vertical: _isExpanded ? 4 : 2),
      decoration: BoxDecoration(
        color: _isExpanded
            ? AppColors.backgroundCard.withValues(alpha: 0.6)
            : AppColors.backgroundCard.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(_isExpanded ? 10 : 8),
        border: Border.all(
          color: isRunning
              ? statusColor.withValues(alpha: 0.4)
              : AppColors.surfaceBorder.withValues(alpha: 0.5),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Compact Header
          Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: _toggleExpand,
              borderRadius: BorderRadius.circular(_isExpanded ? 10 : 8),
              child: Padding(
                padding: EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: _isExpanded ? 10 : 6,
                ),
                child: Row(
                  children: [
                    // Compact status indicator
                    _buildCompactStatusIndicator(isRunning, statusColor, statusIcon),
                    const SizedBox(width: 10),
                    // Tool name and status inline
                    Expanded(
                      child: Row(
                        children: [
                          Text(
                            widget.log.toolName,
                            style: TextStyle(
                              fontFamily: 'monospace',
                              fontWeight: FontWeight.w500,
                              fontSize: 13,
                              color: AppColors.textPrimary,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: statusColor.withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              statusLabel,
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w500,
                                color: statusColor,
                              ),
                            ),
                          ),
                          if (widget.log.timestamp != null) ...[
                            const SizedBox(width: 6),
                            Text(
                              _formatTimestamp(widget.log.timestamp),
                              style: TextStyle(
                                fontSize: 10,
                                color: AppColors.textMuted,
                                fontFamily: 'monospace',
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                    // Expand icon
                    RotationTransition(
                      turns: _rotateAnimation,
                      child: Icon(
                        Icons.keyboard_arrow_down,
                        color: AppColors.textMuted,
                        size: 16,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),

          // Expanded Content
          SizeTransition(
            sizeFactor: _expandAnimation,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  height: 1,
                  color: AppColors.surfaceBorder.withValues(alpha: 0.5),
                ),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(10),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Input section
                      _buildSection(
                        title: 'Input',
                        icon: Icons.input,
                        content: _formatJson(widget.log.args),
                        onCopy: () => _copyToClipboard(
                          _formatJson(widget.log.args),
                          'Input',
                        ),
                      ),
                      // Output section
                      if (completed && widget.log.result != null) ...[
                        const SizedBox(height: 10),
                        _buildSection(
                          title: 'Output',
                          icon: Icons.output,
                          content: widget.log.result!,
                          onCopy: () => _copyToClipboard(
                            widget.log.result!,
                            'Output',
                          ),
                          isSuccess: true,
                        ),
                      ],
                      // Error section
                      if (isError && widget.log.result != null) ...[
                        const SizedBox(height: 10),
                        _buildErrorSection(widget.log.result!),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCompactStatusIndicator(bool isRunning, Color statusColor, IconData statusIcon) {
    return SizedBox(
      width: 18,
      height: 18,
      child: isRunning
          ? CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(statusColor),
            )
          : Icon(statusIcon, color: statusColor, size: 16),
    );
  }

  Widget _buildSection({
    required String title,
    required IconData icon,
    required String content,
    required VoidCallback onCopy,
    bool isSuccess = false,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              icon,
              size: 12,
              color: isSuccess ? AppColors.success : AppColors.textMuted,
            ),
            const SizedBox(width: 6),
            Text(
              title,
              style: TextStyle(
                color: AppColors.textMuted,
                fontSize: 11,
                fontWeight: FontWeight.w500,
              ),
            ),
            const Spacer(),
            Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: onCopy,
                borderRadius: BorderRadius.circular(4),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.copy,
                        size: 11,
                        color: AppColors.textMuted,
                      ),
                      const SizedBox(width: 3),
                      Text(
                        'Copy',
                        style: TextStyle(
                          fontSize: 10,
                          color: AppColors.textMuted,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        _buildCodeBlock(content),
      ],
    );
  }

  Widget _buildErrorSection(String errorMessage) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.error.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: AppColors.error.withValues(alpha: 0.2),
        ),
      ),
      padding: const EdgeInsets.all(8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.warning_amber_rounded,
                size: 12,
                color: AppColors.error,
              ),
              const SizedBox(width: 6),
              Text(
                'Error',
                style: TextStyle(
                  color: AppColors.error,
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const Spacer(),
              Material(
                color: Colors.transparent,
                child: InkWell(
                  onTap: () => _copyToClipboard(errorMessage, 'Error'),
                  borderRadius: BorderRadius.circular(4),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.copy,
                          size: 11,
                          color: AppColors.error.withValues(alpha: 0.7),
                        ),
                        const SizedBox(width: 3),
                        Text(
                          'Copy',
                          style: TextStyle(
                            fontSize: 10,
                            color: AppColors.error.withValues(alpha: 0.7),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Container(
            width: double.infinity,
            constraints: const BoxConstraints(maxHeight: 120),
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.black.withValues(alpha: 0.3),
              borderRadius: BorderRadius.circular(4),
            ),
            child: SingleChildScrollView(
              child: SelectableText(
                errorMessage,
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 11,
                  color: AppColors.error.withValues(alpha: 0.9),
                  height: 1.4,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCodeBlock(String content) {
    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(maxHeight: 160),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(6),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(6),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(8),
          child: SelectableText(
            content,
            style: const TextStyle(
              fontFamily: 'monospace',
              fontSize: 11,
              color: AppColors.textSecondary,
              height: 1.4,
            ),
          ),
        ),
      ),
    );
  }

  String _formatJson(Map<String, dynamic> json) {
    if (json.isEmpty) return '(No arguments)';
    try {
      const encoder = JsonEncoder.withIndent('  ');
      return encoder.convert(json);
    } catch (e) {
      return jsonEncode(json);
    }
  }

  String _formatTimestamp(String? timestamp) {
    if (timestamp == null) return '';
    // Check if it's a long number (likely nanoseconds/microseconds)
    // 13 digits = millis, 16 digits = micros, 19 digits = nanos
    if (RegExp(r'^\d{13,}$').hasMatch(timestamp)) {
      try {
        int ts = int.parse(timestamp);
        // Convert to microseconds for DateTime
        if (timestamp.length > 16) {
          ts = ts ~/ 1000; // Divide by 1000 to get micros if nanos
        } else if (timestamp.length == 13) {
           ts = ts * 1000; // Multiply by 1000 to get micros if millis
        }

        final dt = DateTime.fromMicrosecondsSinceEpoch(ts);
        return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}:${dt.second.toString().padLeft(2, '0')}';
      } catch (e) {
        return timestamp;
      }
    }
    return timestamp;
  }
}
