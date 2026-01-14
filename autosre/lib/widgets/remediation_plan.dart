import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/adk_schema.dart';
import '../theme/app_theme.dart';

class RemediationPlanWidget extends StatefulWidget {
  final RemediationPlan plan;

  const RemediationPlanWidget({super.key, required this.plan});

  @override
  State<RemediationPlanWidget> createState() => _RemediationPlanWidgetState();
}

class _RemediationPlanWidgetState extends State<RemediationPlanWidget>
    with SingleTickerProviderStateMixin {
  late AnimationController _animController;
  late Animation<double> _animation;
  final Set<int> _completedSteps = {};
  final Set<int> _expandedSteps = {};
  int? _copiedIndex;

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

    // Expand first step by default
    if (widget.plan.steps.isNotEmpty) {
      _expandedSteps.add(0);
    }
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  Color _getRiskColor(String risk) {
    switch (risk.toLowerCase()) {
      case 'high':
        return AppColors.error;
      case 'medium':
        return AppColors.warning;
      case 'low':
        return AppColors.success;
      default:
        return AppColors.primaryTeal;
    }
  }

  IconData _getRiskIcon(String risk) {
    switch (risk.toLowerCase()) {
      case 'high':
        return Icons.warning_rounded;
      case 'medium':
        return Icons.info_rounded;
      case 'low':
        return Icons.check_circle_rounded;
      default:
        return Icons.help_outline;
    }
  }

  void _copyCommand(String command, int index) {
    Clipboard.setData(ClipboardData(text: command));
    setState(() {
      _copiedIndex = index;
    });

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            Icon(Icons.check_circle, color: AppColors.success, size: 18),
            const SizedBox(width: 12),
            const Text('Command copied to clipboard'),
          ],
        ),
        duration: const Duration(seconds: 2),
      ),
    );

    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) {
        setState(() {
          _copiedIndex = null;
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final riskColor = _getRiskColor(widget.plan.risk);
    final progress = _completedSteps.length / widget.plan.steps.length;

    return AnimatedBuilder(
      animation: _animation,
      builder: (context, child) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            _buildHeader(riskColor),

            const SizedBox(height: 16),

            // Progress bar
            if (widget.plan.steps.isNotEmpty)
              _buildProgressBar(progress, riskColor),

            const SizedBox(height: 20),

            // Steps
            Expanded(
              child: ListView.builder(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: widget.plan.steps.length,
                itemBuilder: (context, index) {
                  return _buildStep(widget.plan.steps[index], index, riskColor);
                },
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildHeader(Color riskColor) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Icon
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  riskColor.withValues(alpha: 0.2),
                  riskColor.withValues(alpha: 0.1),
                ],
              ),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: riskColor.withValues(alpha: 0.3),
              ),
            ),
            child: Icon(
              Icons.build_circle,
              size: 24,
              color: riskColor,
            ),
          ),

          const SizedBox(width: 14),

          // Title and subtitle
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Remediation Plan',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  widget.plan.issue,
                  style: TextStyle(
                    fontSize: 13,
                    color: AppColors.textSecondary,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(width: 12),

          // Risk badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: riskColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: riskColor.withValues(alpha: 0.3),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  _getRiskIcon(widget.plan.risk),
                  size: 16,
                  color: riskColor,
                ),
                const SizedBox(width: 6),
                Text(
                  '${widget.plan.risk.toUpperCase()} RISK',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: riskColor,
                    letterSpacing: 0.5,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProgressBar(double progress, Color riskColor) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Progress',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                  color: AppColors.textMuted,
                ),
              ),
              Text(
                '${_completedSteps.length} of ${widget.plan.steps.length} steps',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Stack(
            children: [
              // Background
              Container(
                height: 6,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(3),
                ),
              ),
              // Progress
              AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                height: 6,
                width: (MediaQuery.of(context).size.width - 32) * progress,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      AppColors.primaryTeal,
                      AppColors.primaryCyan,
                    ],
                  ),
                  borderRadius: BorderRadius.circular(3),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.primaryTeal.withValues(alpha: 0.4),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStep(RemediationStep step, int index, Color riskColor) {
    final isCompleted = _completedSteps.contains(index);
    final isExpanded = _expandedSteps.contains(index);
    final isCopied = _copiedIndex == index;

    // Stagger animation
    final staggerDelay = index / widget.plan.steps.length;
    final animValue =
        ((_animation.value - staggerDelay * 0.3) / 0.7).clamp(0.0, 1.0);

    return AnimatedOpacity(
      duration: const Duration(milliseconds: 200),
      opacity: animValue,
      child: AnimatedSlide(
        duration: const Duration(milliseconds: 300),
        offset: Offset(0, (1 - animValue) * 0.1),
        child: Container(
          margin: const EdgeInsets.only(bottom: 12),
          decoration: GlassDecoration.card(
            borderRadius: 14,
            borderColor: isCompleted
                ? AppColors.success.withValues(alpha: 0.3)
                : isExpanded
                    ? AppColors.primaryTeal.withValues(alpha: 0.3)
                    : null,
          ),
          child: Column(
            children: [
              // Step header
              InkWell(
                onTap: () {
                  setState(() {
                    if (_expandedSteps.contains(index)) {
                      _expandedSteps.remove(index);
                    } else {
                      _expandedSteps.add(index);
                    }
                  });
                },
                borderRadius: BorderRadius.circular(14),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      // Step number / checkbox
                      GestureDetector(
                        onTap: () {
                          setState(() {
                            if (isCompleted) {
                              _completedSteps.remove(index);
                            } else {
                              _completedSteps.add(index);
                            }
                          });
                        },
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          width: 32,
                          height: 32,
                          decoration: BoxDecoration(
                            gradient: isCompleted
                                ? LinearGradient(
                                    colors: [
                                      AppColors.success,
                                      AppColors.success.withValues(alpha: 0.8),
                                    ],
                                  )
                                : null,
                            color: isCompleted
                                ? null
                                : AppColors.primaryTeal.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: isCompleted
                                  ? AppColors.success
                                  : AppColors.primaryTeal.withValues(alpha: 0.3),
                            ),
                          ),
                          child: Center(
                            child: isCompleted
                                ? const Icon(
                                    Icons.check,
                                    size: 18,
                                    color: Colors.white,
                                  )
                                : Text(
                                    '${index + 1}',
                                    style: TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w600,
                                      color: AppColors.primaryTeal,
                                    ),
                                  ),
                          ),
                        ),
                      ),

                      const SizedBox(width: 14),

                      // Description
                      Expanded(
                        child: Text(
                          step.description,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                            color: isCompleted
                                ? AppColors.textMuted
                                : AppColors.textPrimary,
                            decoration: isCompleted
                                ? TextDecoration.lineThrough
                                : null,
                          ),
                        ),
                      ),

                      // Expand icon
                      AnimatedRotation(
                        duration: const Duration(milliseconds: 200),
                        turns: isExpanded ? 0.5 : 0,
                        child: Icon(
                          Icons.expand_more,
                          color: AppColors.textMuted,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              // Command (expanded)
              AnimatedCrossFade(
                duration: const Duration(milliseconds: 200),
                firstChild: Container(
                  margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  decoration: BoxDecoration(
                    color: Colors.black.withValues(alpha: 0.4),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: isCopied
                          ? AppColors.success.withValues(alpha: 0.5)
                          : AppColors.surfaceBorder,
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Command header
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 8,
                        ),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.05),
                          borderRadius: const BorderRadius.only(
                            topLeft: Radius.circular(9),
                            topRight: Radius.circular(9),
                          ),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              Icons.terminal,
                              size: 14,
                              color: AppColors.textMuted,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'Command',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w500,
                                color: AppColors.textMuted,
                              ),
                            ),
                            const Spacer(),
                            Material(
                              color: Colors.transparent,
                              child: InkWell(
                                onTap: () => _copyCommand(step.command, index),
                                borderRadius: BorderRadius.circular(6),
                                child: AnimatedContainer(
                                  duration: const Duration(milliseconds: 200),
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 10,
                                    vertical: 4,
                                  ),
                                  decoration: BoxDecoration(
                                    color: isCopied
                                        ? AppColors.success.withValues(alpha: 0.2)
                                        : Colors.white.withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Icon(
                                        isCopied ? Icons.check : Icons.copy,
                                        size: 12,
                                        color: isCopied
                                            ? AppColors.success
                                            : AppColors.textSecondary,
                                      ),
                                      const SizedBox(width: 4),
                                      Text(
                                        isCopied ? 'Copied!' : 'Copy',
                                        style: TextStyle(
                                          fontSize: 11,
                                          color: isCopied
                                              ? AppColors.success
                                              : AppColors.textSecondary,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      // Command text
                      Padding(
                        padding: const EdgeInsets.all(12),
                        child: SelectableText(
                          step.command,
                          style: TextStyle(
                            fontSize: 13,
                            fontFamily: 'monospace',
                            color: AppColors.primaryTeal,
                            height: 1.5,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                secondChild: const SizedBox.shrink(),
                crossFadeState: isExpanded
                    ? CrossFadeState.showFirst
                    : CrossFadeState.showSecond,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
