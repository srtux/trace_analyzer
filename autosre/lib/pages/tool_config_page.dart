import 'package:flutter/material.dart';
import '../services/tool_config_service.dart';
import '../theme/app_theme.dart';

/// A page for configuring which tools the agent can use.
class ToolConfigPage extends StatefulWidget {
  const ToolConfigPage({super.key});

  @override
  State<ToolConfigPage> createState() => _ToolConfigPageState();
}

class _ToolConfigPageState extends State<ToolConfigPage>
    with SingleTickerProviderStateMixin {
  final ToolConfigService _service = ToolConfigService();
  late TabController _tabController;
  bool _isTestingAll = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(
      length: ToolCategory.values.length,
      vsync: this,
    );
    _service.fetchConfigs();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.backgroundDark,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: const Text('Tool Configuration'),
        actions: [
          // Test All button
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: _isTestingAll
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor:
                          AlwaysStoppedAnimation<Color>(AppColors.primaryTeal),
                    ),
                  )
                : IconButton(
                    icon: const Icon(Icons.play_circle_outline),
                    tooltip: 'Test All Testable Tools',
                    onPressed: _testAllTools,
                  ),
          ),
          // Refresh button
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: () => _service.fetchConfigs(),
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(48),
          child: _buildTabBar(),
        ),
      ),
      body: Column(
        children: [
          _buildSummaryBar(),
          Expanded(
            child: _buildTabContent(),
          ),
        ],
      ),
    );
  }

  Widget _buildTabBar() {
    return TabBar(
      controller: _tabController,
      isScrollable: true,
      indicatorColor: AppColors.primaryTeal,
      labelColor: AppColors.textPrimary,
      unselectedLabelColor: AppColors.textMuted,
      tabAlignment: TabAlignment.start,
      tabs: ToolCategory.values.map((category) {
        return Tab(
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(_getCategoryIcon(category), size: 18),
              const SizedBox(width: 8),
              Text(category.displayName),
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _buildSummaryBar() {
    return ValueListenableBuilder<ToolConfigSummary?>(
      valueListenable: _service.summary,
      builder: (context, summary, _) {
        if (summary == null) {
          return const SizedBox.shrink();
        }

        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: AppColors.backgroundCard,
            border: Border(
              bottom: BorderSide(
                color: AppColors.surfaceBorder,
                width: 1,
              ),
            ),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildSummaryItem(
                'Total',
                summary.total.toString(),
                AppColors.textSecondary,
              ),
              _buildSummaryItem(
                'Enabled',
                summary.enabled.toString(),
                AppColors.success,
              ),
              _buildSummaryItem(
                'Disabled',
                summary.disabled.toString(),
                AppColors.error,
              ),
              _buildSummaryItem(
                'Testable',
                summary.testable.toString(),
                AppColors.info,
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildSummaryItem(String label, String value, Color color) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            color: AppColors.textMuted,
          ),
        ),
      ],
    );
  }

  Widget _buildTabContent() {
    return ValueListenableBuilder<bool>(
      valueListenable: _service.isLoading,
      builder: (context, isLoading, _) {
        if (isLoading) {
          return const Center(
            child: CircularProgressIndicator(
              valueColor: AlwaysStoppedAnimation<Color>(AppColors.primaryTeal),
            ),
          );
        }

        return ValueListenableBuilder<String?>(
          valueListenable: _service.error,
          builder: (context, error, _) {
            if (error != null) {
              return Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.error_outline,
                      size: 48,
                      color: AppColors.error,
                    ),
                    const SizedBox(height: 16),
                    Text(
                      error,
                      style: TextStyle(color: AppColors.textSecondary),
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: () => _service.fetchConfigs(),
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              );
            }

            return TabBarView(
              controller: _tabController,
              children: ToolCategory.values.map((category) {
                return _buildCategoryContent(category);
              }).toList(),
            );
          },
        );
      },
    );
  }

  Widget _buildCategoryContent(ToolCategory category) {
    return ValueListenableBuilder<Map<ToolCategory, List<ToolConfig>>>(
      valueListenable: _service.toolsByCategory,
      builder: (context, toolsByCategory, _) {
        final tools = toolsByCategory[category] ?? [];

        if (tools.isEmpty) {
          return Center(
            child: Text(
              'No tools in this category',
              style: TextStyle(color: AppColors.textMuted),
            ),
          );
        }

        return Column(
          children: [
            _buildCategoryActions(category, tools),
            Expanded(
              child: ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: tools.length,
                itemBuilder: (context, index) {
                  return _buildToolCard(tools[index]);
                },
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildCategoryActions(ToolCategory category, List<ToolConfig> tools) {
    final enabledCount = tools.where((t) => t.enabled).length;
    final testableCount = tools.where((t) => t.testable).length;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
      ),
      child: Row(
        children: [
          Text(
            '${tools.length} tools ($enabledCount enabled, $testableCount testable)',
            style: TextStyle(
              color: AppColors.textSecondary,
              fontSize: 13,
            ),
          ),
          const Spacer(),
          TextButton.icon(
            onPressed: () => _service.enableCategory(category),
            icon: const Icon(Icons.check_circle_outline, size: 18),
            label: const Text('Enable All'),
            style: TextButton.styleFrom(
              foregroundColor: AppColors.success,
            ),
          ),
          const SizedBox(width: 8),
          TextButton.icon(
            onPressed: () => _service.disableCategory(category),
            icon: const Icon(Icons.cancel_outlined, size: 18),
            label: const Text('Disable All'),
            style: TextButton.styleFrom(
              foregroundColor: AppColors.error,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildToolCard(ToolConfig tool) {
    return ValueListenableBuilder<Set<String>>(
      valueListenable: _service.testingTools,
      builder: (context, testingTools, _) {
        final isTesting = testingTools.contains(tool.name);

        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          decoration: GlassDecoration.card(
            borderRadius: 12,
            borderColor: tool.enabled
                ? AppColors.success.withValues(alpha: 0.3)
                : AppColors.surfaceBorder,
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            tool.displayName,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: AppColors.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            tool.name,
                            style: TextStyle(
                              fontSize: 12,
                              color: AppColors.textMuted,
                              fontFamily: 'monospace',
                            ),
                          ),
                        ],
                      ),
                    ),
                    // Test button for testable tools
                    if (tool.testable) ...[
                      isTesting
                          ? const SizedBox(
                              width: 24,
                              height: 24,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor: AlwaysStoppedAnimation<Color>(
                                  AppColors.info,
                                ),
                              ),
                            )
                          : IconButton(
                              icon: const Icon(Icons.play_arrow),
                              tooltip: 'Test Tool',
                              onPressed: () => _testTool(tool.name),
                              style: IconButton.styleFrom(
                                foregroundColor: AppColors.info,
                                backgroundColor:
                                    AppColors.info.withValues(alpha: 0.1),
                              ),
                            ),
                      const SizedBox(width: 8),
                    ],
                    // Enable/Disable switch
                    Switch(
                      value: tool.enabled,
                      onChanged: (value) =>
                          _service.setToolEnabled(tool.name, value),
                      activeColor: AppColors.success,
                      inactiveThumbColor: AppColors.textMuted,
                      inactiveTrackColor:
                          AppColors.textMuted.withValues(alpha: 0.3),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  tool.description,
                  style: TextStyle(
                    fontSize: 13,
                    color: AppColors.textSecondary,
                  ),
                ),
                // Show last test result if available
                if (tool.lastTestResult != null) ...[
                  const SizedBox(height: 12),
                  _buildTestResultBadge(tool.lastTestResult!),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildTestResultBadge(ToolTestResult result) {
    Color color;
    IconData icon;
    String label;

    switch (result.status) {
      case ToolTestStatus.success:
        color = AppColors.success;
        icon = Icons.check_circle;
        label = 'Connected';
      case ToolTestStatus.failed:
        color = AppColors.error;
        icon = Icons.error;
        label = 'Failed';
      case ToolTestStatus.timeout:
        color = AppColors.warning;
        icon = Icons.timer_off;
        label = 'Timeout';
      case ToolTestStatus.notTested:
        color = AppColors.textMuted;
        icon = Icons.help_outline;
        label = 'Not Tested';
      case ToolTestStatus.notTestable:
        color = AppColors.textMuted;
        icon = Icons.block;
        label = 'Not Testable';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: color.withValues(alpha: 0.3),
          width: 1,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 8),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: color,
            ),
          ),
          if (result.latencyMs != null) ...[
            const SizedBox(width: 8),
            Text(
              '${result.latencyMs!.toStringAsFixed(0)}ms',
              style: TextStyle(
                fontSize: 11,
                color: AppColors.textMuted,
              ),
            ),
          ],
          if (result.message.isNotEmpty &&
              result.status != ToolTestStatus.success) ...[
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                result.message,
                style: TextStyle(
                  fontSize: 11,
                  color: AppColors.textMuted,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ],
      ),
    );
  }

  IconData _getCategoryIcon(ToolCategory category) {
    switch (category) {
      case ToolCategory.apiClient:
        return Icons.api;
      case ToolCategory.mcp:
        return Icons.hub;
      case ToolCategory.analysis:
        return Icons.analytics;
      case ToolCategory.orchestration:
        return Icons.account_tree;
      case ToolCategory.discovery:
        return Icons.search;
      case ToolCategory.remediation:
        return Icons.healing;
      case ToolCategory.gke:
        return Icons.cloud;
      case ToolCategory.slo:
        return Icons.speed;
    }
  }

  Future<void> _testTool(String toolName) async {
    final result = await _service.testTool(toolName);
    if (result != null && mounted) {
      final message = result.status == ToolTestStatus.success
          ? 'Tool $toolName is working'
          : 'Tool $toolName test failed: ${result.message}';

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: result.status == ToolTestStatus.success
              ? AppColors.success
              : AppColors.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  Future<void> _testAllTools() async {
    setState(() => _isTestingAll = true);

    try {
      final results = await _service.testAllTools();

      if (mounted) {
        final successCount =
            results.values.where((r) => r.status == ToolTestStatus.success).length;
        final failedCount =
            results.values.where((r) => r.status == ToolTestStatus.failed).length;

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Test completed: $successCount passed, $failedCount failed',
            ),
            backgroundColor:
                failedCount == 0 ? AppColors.success : AppColors.warning,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isTestingAll = false);
      }
    }
  }
}
