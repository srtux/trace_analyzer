import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class ErrorPlaceholder extends StatefulWidget {
  final Object error;
  final StackTrace? stackTrace;

  const ErrorPlaceholder({super.key, required this.error, this.stackTrace});

  @override
  State<ErrorPlaceholder> createState() => _ErrorPlaceholderState();
}

class _ErrorPlaceholderState extends State<ErrorPlaceholder> {
  bool _showDetails = false;

  String _getErrorTitle() {
    final errorType = widget.error.runtimeType.toString();
    if (errorType.contains('DataValidationError')) {
      return 'Data Validation Error';
    } else if (errorType.contains('FormatException')) {
      return 'Data Format Error';
    } else if (errorType.contains('TypeError') || errorType.contains('CastError')) {
      return 'Type Mismatch Error';
    } else if (errorType.contains('NoSuchMethodError')) {
      return 'Missing Field Error';
    }
    return 'Widget Rendering Error';
  }

  String _getErrorSummary() {
    final errorStr = widget.error.toString();
    // Extract key message for common error types
    if (errorStr.contains('Expected:') && errorStr.contains('Received:')) {
      // DataValidationError format
      return errorStr;
    }
    // Truncate very long error messages
    if (errorStr.length > 200) {
      return '${errorStr.substring(0, 200)}...';
    }
    return errorStr;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      margin: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: AppColors.error.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: AppColors.error.withValues(alpha: 0.25),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppColors.error.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(
                  Icons.error_outline,
                  color: AppColors.error,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _getErrorTitle(),
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppColors.error,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Failed to render visualization component',
                      style: TextStyle(
                        fontSize: 11,
                        color: AppColors.textMuted,
                      ),
                    ),
                  ],
                ),
              ),
              if (widget.stackTrace != null)
                IconButton(
                  icon: Icon(
                    _showDetails ? Icons.expand_less : Icons.expand_more,
                    color: AppColors.textMuted,
                    size: 20,
                  ),
                  onPressed: () => setState(() => _showDetails = !_showDetails),
                  tooltip: _showDetails ? 'Hide details' : 'Show details',
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.black.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: SelectableText(
              _getErrorSummary(),
              style: TextStyle(
                fontSize: 11,
                fontFamily: 'monospace',
                color: AppColors.textSecondary,
                height: 1.4,
              ),
            ),
          ),
          if (_showDetails && widget.stackTrace != null) ...[
            const SizedBox(height: 12),
            Text(
              'Stack Trace:',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w600,
                color: AppColors.textMuted,
              ),
            ),
            const SizedBox(height: 6),
            Container(
              width: double.infinity,
              constraints: const BoxConstraints(maxHeight: 150),
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(6),
              ),
              child: SingleChildScrollView(
                child: SelectableText(
                  widget.stackTrace.toString(),
                  style: TextStyle(
                    fontSize: 9,
                    fontFamily: 'monospace',
                    color: AppColors.textMuted,
                    height: 1.3,
                  ),
                ),
              ),
            ),
          ],
          const SizedBox(height: 12),
          Row(
            children: [
              Icon(Icons.lightbulb_outline, size: 14, color: AppColors.warning),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'This may indicate a data format mismatch between the backend and UI.',
                  style: TextStyle(
                    fontSize: 10,
                    color: AppColors.warning,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Shimmer loading placeholder widget
class ShimmerPlaceholder extends StatefulWidget {
  final double? height;
  final double? width;
  final double borderRadius;

  const ShimmerPlaceholder({
    super.key,
    this.height,
    this.width,
    this.borderRadius = 12,
  });

  @override
  State<ShimmerPlaceholder> createState() => _ShimmerPlaceholderState();
}

class _ShimmerPlaceholderState extends State<ShimmerPlaceholder>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat();

    _animation = Tween<double>(begin: -2, end: 2).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _animation,
      builder: (context, child) {
        return Container(
          height: widget.height,
          width: widget.width,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(widget.borderRadius),
            gradient: LinearGradient(
              begin: Alignment(_animation.value, 0),
              end: Alignment(_animation.value + 1, 0),
              colors: [
                Colors.white.withValues(alpha: 0.05),
                Colors.white.withValues(alpha: 0.1),
                Colors.white.withValues(alpha: 0.05),
              ],
            ),
          ),
        );
      },
    );
  }
}

/// Loading state widget for data fetching
class LoadingPlaceholder extends StatelessWidget {
  final String? message;

  const LoadingPlaceholder({super.key, this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(
            width: 40,
            height: 40,
            child: CircularProgressIndicator(
              strokeWidth: 3,
              valueColor: AlwaysStoppedAnimation<Color>(
                AppColors.primaryTeal,
              ),
            ),
          ),
          if (message != null) ...[
            const SizedBox(height: 16),
            Text(
              message!,
              style: TextStyle(
                fontSize: 13,
                color: AppColors.textMuted,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
