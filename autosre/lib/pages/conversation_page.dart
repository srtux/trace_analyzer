import 'dart:async';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:genui/genui.dart';

import '../agent/adk_content_generator.dart';
import '../catalog.dart';
import '../services/project_service.dart';
import '../services/session_service.dart';
import '../theme/app_theme.dart';
import '../widgets/session_panel.dart';
import 'tool_config_page.dart';

class ConversationPage extends StatefulWidget {
  const ConversationPage({super.key});

  static const double kMaxContentWidth = 1000.0;

  @override
  State<ConversationPage> createState() => _ConversationPageState();
}

class _ConversationPageState extends State<ConversationPage>
    with TickerProviderStateMixin {
  late A2uiMessageProcessor _messageProcessor;
  late GenUiConversation _conversation;
  late ADKContentGenerator _contentGenerator;
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _focusNode = FocusNode();
  final ProjectService _projectService = ProjectService();
  final SessionService _sessionService = SessionService();

  late AnimationController _typingController;

  bool _showSessionPanel = true;
  StreamSubscription<String>? _sessionSubscription;

  @override
  void initState() {
    super.initState();

    // Handle Enter key behavior (Enter to send, Shift+Enter for newline)
    _focusNode.onKeyEvent = (node, event) {
      if (event is KeyDownEvent && event.logicalKey == LogicalKeyboardKey.enter) {
        if (HardwareKeyboard.instance.isShiftPressed) {
          return KeyEventResult.ignored;
        }
        _sendMessage();
        return KeyEventResult.handled;
      }
      return KeyEventResult.ignored;
    };

    // Typing indicator animation
    _typingController = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: this,
    )..repeat();

    _initializeConversation();

    // Listen to session updates from the content generator
    _sessionSubscription = _contentGenerator.sessionStream.listen((sessionId) {
      _sessionService.setCurrentSession(sessionId);
      // Refresh sessions list after a message is sent
      _sessionService.fetchSessions();
    });

    // Fetch projects and sessions on startup
    _projectService.fetchProjects();
    _sessionService.fetchSessions();

    // Update content generator when project selection changes
    _projectService.selectedProject.addListener(_onProjectChanged);
  }

  void _initializeConversation() {
    final sreCatalog = CatalogRegistry.createSreCatalog();

    _messageProcessor = A2uiMessageProcessor(
      catalogs: [
        sreCatalog,
        CoreCatalogItems.asCatalog(),
      ],
    );

    _contentGenerator = ADKContentGenerator();
    _contentGenerator.projectId = _projectService.selectedProjectId;

    _conversation = GenUiConversation(
      a2uiMessageProcessor: _messageProcessor,
      contentGenerator: _contentGenerator,
      onSurfaceAdded: (update) => _scrollToBottom(),
      onSurfaceUpdated: (update) {},
      onTextResponse: (text) => _scrollToBottom(),
    );
  }

  void _onProjectChanged() {
    _contentGenerator.projectId = _projectService.selectedProjectId;
  }

  void _startNewSession() {
    // Clear session in content generator (new messages will start a new backend session)
    _contentGenerator.clearSession();
    // Clear current session in service
    _sessionService.startNewSession();
    // Show confirmation
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('Starting new investigation'),
        backgroundColor: AppColors.primaryTeal,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  Future<void> _loadSession(String sessionId) async {
    // Load session from backend
    final session = await _sessionService.getSession(sessionId);
    if (session == null) return;

    // Set session ID in content generator - backend will use session history for context
    _contentGenerator.sessionId = sessionId;
    _sessionService.setCurrentSession(sessionId);

    // Show a message indicating the session is loaded
    // The backend will maintain the conversation context
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Loaded session: ${session.displayTitle}'),
        backgroundColor: AppColors.primaryTeal,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 400),
          curve: Curves.easeOutCubic,
        );
      }
    });
  }

  void _sendMessage() {
    if (_textController.text.trim().isEmpty) return;
    final text = _textController.text;
    _textController.clear();
    _focusNode.requestFocus();

    _conversation.sendRequest(UserMessage.text(text));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.backgroundDark,
      appBar: _buildAppBar(),
      body: Column(
        children: [
          // Main content with session panel
          Expanded(
            child: Row(
              children: [
                // Session panel (collapsible)
                if (_showSessionPanel)
                  ValueListenableBuilder<String?>(
                    valueListenable: _sessionService.currentSessionId,
                    builder: (context, currentSessionId, _) {
                      return SessionPanel(
                        sessionService: _sessionService,
                        onNewSession: _startNewSession,
                        onSessionSelected: _loadSession,
                        currentSessionId: currentSessionId,
                      );
                    },
                  ),
                // Main conversation area
                Expanded(
                  child: Column(
                    children: [
                      Expanded(child: _buildMessageList()),
                      _buildInputArea(),
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

  PreferredSizeWidget _buildAppBar() {
    return PreferredSize(
      preferredSize: const Size.fromHeight(56),
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.backgroundCard,
          border: Border(
            bottom: BorderSide(
              color: AppColors.surfaceBorder.withValues(alpha: 0.5),
              width: 1,
            ),
          ),
        ),
        child: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final isCompact = constraints.maxWidth < 600;
              final isMobile = constraints.maxWidth < 400;

              return Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1600),
                  child: Padding(
                    padding: EdgeInsets.symmetric(
                      horizontal: isCompact ? 12 : 24,
                      vertical: 8,
                    ),
                    child: Row(
                      children: [
                        // Logo/Icon - clickable to return to home
                        _buildLogoButton(isMobile: isMobile),
                        SizedBox(width: isMobile ? 8 : 12),
                        // Title
                        Text(
                          'AutoSRE',
                          style: TextStyle(
                            fontSize: isMobile ? 15 : 17,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textPrimary,
                            letterSpacing: 0.3,
                          ),
                        ),
                        const Spacer(),
                        // History Toggle
                        _buildSessionToggle(compact: isMobile),
                        SizedBox(width: isCompact ? 8 : 12),
                        // Project Selector - constrained width on mobile
                        Flexible(
                          child: ConstrainedBox(
                            constraints: BoxConstraints(
                              maxWidth: isMobile ? 110 : (isCompact ? 160 : 200),
                            ),
                            child: _buildProjectSelector(),
                          ),
                        ),
                        SizedBox(width: isCompact ? 8 : 12),
                        // Status indicator
                        ValueListenableBuilder<bool>(
                          valueListenable: _contentGenerator.isConnected,
                          builder: (context, isConnected, _) {
                            return ValueListenableBuilder<bool>(
                              valueListenable: _contentGenerator.isProcessing,
                              builder: (context, isProcessing, _) {
                                return _buildStatusIndicator(
                                  isProcessing,
                                  isConnected,
                                  compact: isMobile,
                                );
                              },
                            );
                          },
                        ),
                        const SizedBox(width: 8),
                        // Tool Configuration button
                        _buildToolConfigButton(compact: isMobile),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildLogoButton({bool isMobile = false}) {
    return Tooltip(
      message: 'New Session',
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _startNewSession,
          borderRadius: BorderRadius.circular(8),
          child: Container(
            padding: EdgeInsets.all(isMobile ? 6 : 8),
            decoration: BoxDecoration(
              color: AppColors.primaryTeal.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              Icons.terminal,
              color: AppColors.primaryTeal,
              size: isMobile ? 18 : 20,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildNewSessionButton({bool compact = false}) {
    return Tooltip(
      message: 'Start New Session',
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _startNewSession,
          borderRadius: BorderRadius.circular(6),
          child: Container(
            padding: EdgeInsets.symmetric(
              horizontal: compact ? 8 : 10,
              vertical: compact ? 4 : 6,
            ),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(6),
              border: Border.all(
                color: AppColors.surfaceBorder.withValues(alpha: 0.5),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.add,
                  size: compact ? 14 : 16,
                  color: AppColors.textSecondary,
                ),
                if (!compact) ...[
                  const SizedBox(width: 4),
                  Text(
                    'New',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSessionToggle({bool compact = false}) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () {
          setState(() {
            _showSessionPanel = !_showSessionPanel;
          });
        },
        borderRadius: BorderRadius.circular(10),
        child: Container(
          padding: EdgeInsets.all(compact ? 6 : 8),
          decoration: BoxDecoration(
            color: _showSessionPanel
                ? AppColors.primaryTeal.withValues(alpha: 0.15)
                : Colors.white.withValues(alpha: 0.05),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: _showSessionPanel
                  ? AppColors.primaryTeal.withValues(alpha: 0.3)
                  : Colors.white.withValues(alpha: 0.1),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                _showSessionPanel
                    ? Icons.menu_open
                    : Icons.history,
                color: _showSessionPanel
                    ? AppColors.primaryTeal
                    : AppColors.textMuted,
                size: compact ? 16 : 18,
              ),
              if (!compact) ...[
                const SizedBox(width: 8),
                Text(
                  'History',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                    color: _showSessionPanel
                        ? AppColors.primaryTeal
                        : AppColors.textMuted,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildToolConfigButton({bool compact = false}) {
    return Tooltip(
      message: 'Tool Configuration',
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () {
            Navigator.of(context).push(
              MaterialPageRoute(
                builder: (context) => const ToolConfigPage(),
              ),
            );
          },
          borderRadius: BorderRadius.circular(6),
          child: Container(
            padding: EdgeInsets.all(compact ? 6 : 8),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(6),
              border: Border.all(
                color: AppColors.surfaceBorder.withValues(alpha: 0.5),
              ),
            ),
            child: Icon(
              Icons.settings_outlined,
              size: compact ? 16 : 18,
              color: AppColors.textMuted,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildStatusIndicator(bool isProcessing, bool isConnected, {bool compact = false}) {
    Color statusColor;
    String statusText;

    if (isConnected) {
      statusColor = AppColors.success;
      statusText = 'Connected';
    } else {
      statusColor = AppColors.error;
      statusText = 'Offline';
    }

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 6 : 8,
        vertical: compact ? 3 : 4,
      ),
      decoration: BoxDecoration(
        color: statusColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (isProcessing)
            SizedBox(
              width: 10,
              height: 10,
              child: CircularProgressIndicator(
                strokeWidth: 1.5,
                valueColor: AlwaysStoppedAnimation<Color>(statusColor),
              ),
            )
          else
            Container(
              width: 6,
              height: 6,
              decoration: BoxDecoration(
                color: statusColor,
                shape: BoxShape.circle,
              ),
            ),
          if (!compact) ...[
            const SizedBox(width: 6),
            Text(
              statusText,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w500,
                color: statusColor,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildProjectSelector() {
    return ValueListenableBuilder<bool>(
      valueListenable: _projectService.isLoading,
      builder: (context, isLoading, _) {
        return ValueListenableBuilder<List<GcpProject>>(
          valueListenable: _projectService.projects,
          builder: (context, projects, _) {
            return ValueListenableBuilder<GcpProject?>(
              valueListenable: _projectService.selectedProject,
              builder: (context, selectedProject, _) {
                return _ProjectSelectorDropdown(
                  projects: projects,
                  selectedProject: selectedProject,
                  isLoading: isLoading,
                  onProjectSelected: (project) {
                    _projectService.selectProjectInstance(project);
                  },
                  onRefresh: () {
                    _projectService.fetchProjects();
                  },
                );
              },
            );
          },
        );
      },
    );
  }

  Widget _buildMessageList() {
    return ValueListenableBuilder<List<ChatMessage>>(
      valueListenable: _conversation.conversation,
      builder: (context, messages, _) {
        if (messages.isEmpty) {
          return _buildEmptyState();
        }

        return Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: ConversationPage.kMaxContentWidth),
            child: ListView.builder(
              controller: _scrollController,
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
          itemCount: messages.length + 1, // +1 for typing indicator
          itemBuilder: (context, index) {
            if (index == messages.length) {
              // Typing indicator at the end
              return ValueListenableBuilder<bool>(
                valueListenable: _contentGenerator.isProcessing,
                builder: (context, isProcessing, _) {
                  if (!isProcessing) return const SizedBox.shrink();
                  return _buildTypingIndicator();
                },
              );
            }
            final msg = messages[index];
            return _MessageItem(
              message: msg,
              host: _conversation.host,
              animation: _typingController,
            );
          },
        ),
      ),
    );
      },
    );
  }

  Widget _buildEmptyState() {
    return SingleChildScrollView(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Simple icon
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.primaryTeal.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  Icons.terminal,
                  size: 32,
                  color: AppColors.primaryTeal,
                ),
              ),
              const SizedBox(height: 20),
              Text(
                'SRE Assistant',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
              ),
              const SizedBox(height: 8),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 380),
                child: Text(
                  'Analyze traces, investigate logs, monitor metrics, and debug production issues.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppColors.textMuted,
                        height: 1.4,
                      ),
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: 32),
              // Compact category sections
              Wrap(
                spacing: 16,
                runSpacing: 16,
                alignment: WrapAlignment.center,
                children: [
                  _buildSuggestionSection(
                    'Traces',
                    Icons.timeline_outlined,
                    [
                      'Analyze recent traces',
                      'Find slow requests',
                      'Identify bottlenecks',
                    ],
                  ),
                  _buildSuggestionSection(
                    'Logs',
                    Icons.article_outlined,
                    [
                      'Check error logs',
                      'Find error patterns',
                      'Investigate exceptions',
                    ],
                  ),
                  _buildSuggestionSection(
                    'Metrics',
                    Icons.show_chart_outlined,
                    [
                      'View anomalies',
                      'Check SLO status',
                      'Golden signals',
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSuggestionSection(String title, IconData icon, List<String> suggestions) {
    return Container(
      width: 220,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.backgroundCard.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: AppColors.surfaceBorder.withValues(alpha: 0.5),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                icon,
                size: 14,
                color: AppColors.textMuted,
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textSecondary,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: suggestions.map((s) => _buildSuggestionChip(s)).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildSuggestionChip(String text) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () {
          _textController.text = text;
          _sendMessage();
        },
        borderRadius: BorderRadius.circular(6),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.04),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(
              color: AppColors.surfaceBorder.withValues(alpha: 0.3),
            ),
          ),
          child: Text(
            text,
            style: TextStyle(
              color: AppColors.textSecondary,
              fontSize: 12,
            ),
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ),
    );
  }

  Widget _buildTypingIndicator() {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(top: 4, bottom: 4),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: AppColors.backgroundCard.withValues(alpha: 0.6),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(3, (index) {
            return AnimatedBuilder(
              animation: _typingController,
              builder: (context, child) {
                final delay = index * 0.2;
                final animValue =
                    ((_typingController.value + delay) % 1.0 * 2.0)
                        .clamp(0.0, 1.0);
                final bounce = (animValue < 0.5
                        ? animValue * 2
                        : 2 - animValue * 2) *
                    0.4;

                return Container(
                  margin: EdgeInsets.only(right: index < 2 ? 4 : 0),
                  child: Transform.translate(
                    offset: Offset(0, -bounce * 4),
                    child: Container(
                      width: 6,
                      height: 6,
                      decoration: BoxDecoration(
                        color: AppColors.textMuted.withValues(
                          alpha: 0.4 + bounce,
                        ),
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
                );
              },
            );
          }),
        ),
      ),
    );
  }

  Widget _buildInputArea() {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 16),
      decoration: BoxDecoration(
        color: AppColors.backgroundCard,
        border: Border(
          top: BorderSide(
            color: AppColors.surfaceBorder.withValues(alpha: 0.5),
            width: 1,
          ),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: ConversationPage.kMaxContentWidth),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Input row
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Expanded(
                      child: Container(
                        decoration: BoxDecoration(
                          color: AppColors.backgroundDark,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color: AppColors.surfaceBorder.withValues(alpha: 0.5),
                            width: 1,
                          ),
                        ),
                        child: TextField(
                          controller: _textController,
                          focusNode: _focusNode,
                          onSubmitted: (_) => _sendMessage(),
                          maxLines: 4,
                          minLines: 1,
                          style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 14,
                            height: 1.4,
                          ),
                          decoration: InputDecoration(
                            hintText: "Ask a question...",
                            hintStyle: TextStyle(
                              color: AppColors.textMuted,
                              fontSize: 14,
                            ),
                            border: InputBorder.none,
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 14,
                              vertical: 12,
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    ValueListenableBuilder<bool>(
                      valueListenable: _contentGenerator.isProcessing,
                      builder: (context, isProcessing, _) {
                        return _SendButton(
                          isProcessing: isProcessing,
                          onPressed: _sendMessage,
                          onCancel: _contentGenerator.cancelRequest,
                        );
                      },
                    ),
                  ],
                ),
                // Compact keyboard hint
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(
                    'Enter to send • Shift+Enter for new line',
                    style: TextStyle(
                      fontSize: 10,
                      color: AppColors.textMuted.withValues(alpha: 0.5),
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

  @override
  void dispose() {
    _sessionSubscription?.cancel();
    _projectService.selectedProject.removeListener(_onProjectChanged);
    _typingController.dispose();
    _conversation.dispose();
    _focusNode.dispose();
    super.dispose();
  }
}

/// Animated message item widget
class _MessageItem extends StatefulWidget {
  final ChatMessage message;
  final GenUiHost host;
  final AnimationController animation;

  const _MessageItem({
    required this.message,
    required this.host,
    required this.animation,
  });

  @override
  State<_MessageItem> createState() => _MessageItemState();
}

class _MessageItemState extends State<_MessageItem>
    with SingleTickerProviderStateMixin {
  late AnimationController _entryController;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;

  @override
  void initState() {
    super.initState();
    _entryController = AnimationController(
      duration: const Duration(milliseconds: 400),
      vsync: this,
    );

    _fadeAnimation = CurvedAnimation(
      parent: _entryController,
      curve: Curves.easeOut,
    );

    _slideAnimation = Tween<Offset>(
      begin: const Offset(0, 0.15),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _entryController,
      curve: Curves.easeOutCubic,
    ));

    _entryController.forward();
  }

  @override
  void dispose() {
    _entryController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _fadeAnimation,
      child: SlideTransition(
        position: _slideAnimation,
        child: _buildMessageContent(),
      ),
    );
  }

  Widget _buildMessageContent() {
    final msg = widget.message;

    if (msg is UserMessage) {
      return Align(
        alignment: Alignment.centerRight,
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 4),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          constraints: const BoxConstraints(
            maxWidth: 800,
          ),
          decoration: BoxDecoration(
            color: AppColors.primaryTeal.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(10),
          ),
          child: MarkdownBody(
            data: msg.text,
            styleSheet: MarkdownStyleSheet(
              p: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 14,
                height: 1.4,
              ),
              code: TextStyle(
                backgroundColor: Colors.black.withValues(alpha: 0.2),
                color: AppColors.primaryTeal,
                fontSize: 12,
                fontFamily: 'monospace',
              ),
            ),
          ),
        ),
      );
    } else if (msg is AiTextMessage) {
      return Align(
        alignment: Alignment.centerLeft,
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 4),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          constraints: const BoxConstraints(
            maxWidth: 800,
          ),
          decoration: BoxDecoration(
            color: AppColors.backgroundCard.withValues(alpha: 0.6),
            borderRadius: BorderRadius.circular(10),
          ),
          child: MarkdownBody(
            data: msg.text,
            styleSheet: MarkdownStyleSheet(
              p: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 14,
                height: 1.5,
              ),
              h1: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
              h2: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
              code: TextStyle(
                backgroundColor: Colors.black.withValues(alpha: 0.3),
                color: AppColors.primaryTeal,
                fontSize: 12,
                fontFamily: 'monospace',
              ),
              codeblockDecoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(6),
              ),
              blockquoteDecoration: BoxDecoration(
                color: AppColors.primaryTeal.withValues(alpha: 0.08),
                border: Border(
                  left: BorderSide(
                    color: AppColors.primaryTeal.withValues(alpha: 0.5),
                    width: 2,
                  ),
                ),
              ),
            ),
          ),
        ),
      );
    } else if (msg is AiUiMessage) {
      return Align(
        alignment: Alignment.centerLeft,
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 4),
          constraints: const BoxConstraints(
            maxWidth: 950,
          ),
          decoration: BoxDecoration(
            color: AppColors.backgroundCard.withValues(alpha: 0.4),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: AppColors.surfaceBorder.withValues(alpha: 0.3),
            ),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: GenUiSurface(
              host: widget.host,
              surfaceId: msg.surfaceId,
            ),
          ),
        ),
      );
    }
    return const SizedBox.shrink();
  }
}

/// Compact send/stop button
class _SendButton extends StatelessWidget {
  final bool isProcessing;
  final VoidCallback onPressed;
  final VoidCallback onCancel;

  const _SendButton({
    required this.isProcessing,
    required this.onPressed,
    required this.onCancel,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: isProcessing ? 'Stop' : 'Send',
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: isProcessing ? onCancel : onPressed,
          borderRadius: BorderRadius.circular(8),
          child: Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: isProcessing
                  ? AppColors.error
                  : AppColors.primaryTeal,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              isProcessing ? Icons.stop_rounded : Icons.arrow_upward_rounded,
              color: isProcessing ? Colors.white : AppColors.backgroundDark,
              size: 20,
            ),
          ),
        ),
      ),
    );
  }
}

/// Modern searchable project selector with combobox functionality
class _ProjectSelectorDropdown extends StatefulWidget {
  final List<GcpProject> projects;
  final GcpProject? selectedProject;
  final bool isLoading;
  final ValueChanged<GcpProject?> onProjectSelected;
  final VoidCallback onRefresh;

  const _ProjectSelectorDropdown({
    required this.projects,
    required this.selectedProject,
    required this.isLoading,
    required this.onProjectSelected,
    required this.onRefresh,
  });

  @override
  State<_ProjectSelectorDropdown> createState() => _ProjectSelectorDropdownState();
}

class _ProjectSelectorDropdownState extends State<_ProjectSelectorDropdown>
    with SingleTickerProviderStateMixin {
  final LayerLink _layerLink = LayerLink();
  final TextEditingController _searchController = TextEditingController();
  final FocusNode _searchFocusNode = FocusNode();
  OverlayEntry? _overlayEntry;
  bool _isOpen = false;
  String _searchQuery = '';
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 200),
      vsync: this,
    );
    _fadeAnimation = CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeOut,
    );
    _scaleAnimation = Tween<double>(begin: 0.95, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeOutCubic),
    );
  }

  @override
  void dispose() {
    _animationController.dispose();
    _searchController.dispose();
    _searchFocusNode.dispose();
    _overlayEntry?.remove();
    _overlayEntry = null;
    super.dispose();
  }

  List<GcpProject> get _filteredProjects {
    if (_searchQuery.isEmpty) return widget.projects;
    final query = _searchQuery.toLowerCase();
    return widget.projects.where((p) {
      return p.projectId.toLowerCase().contains(query) ||
          (p.displayName?.toLowerCase().contains(query) ?? false);
    }).toList();
  }

  void _toggleDropdown() {
    if (_isOpen) {
      _closeDropdown();
    } else {
      _openDropdown();
    }
  }

  void _openDropdown() {
    _overlayEntry = _createOverlayEntry();
    Overlay.of(context).insert(_overlayEntry!);
    _animationController.forward();
    setState(() {
      _isOpen = true;
    });
    // Focus the search field after a short delay
    Future.delayed(const Duration(milliseconds: 100), () {
      if (mounted) {
        _searchFocusNode.requestFocus();
      }
    });
  }

  void _closeDropdown() {
    _animationController.reverse().then((_) {
      if (mounted) {
        _overlayEntry?.remove();
        _overlayEntry = null;
      }
    });
    if (mounted) {
      setState(() {
        _isOpen = false;
        _searchQuery = '';
        _searchController.clear();
      });
    }
  }

  void _selectCustomProject(String projectId) {
    if (projectId.trim().isEmpty) return;
    final customProject = GcpProject(projectId: projectId.trim());
    widget.onProjectSelected(customProject);
    _closeDropdown();
  }

  OverlayEntry _createOverlayEntry() {
    final renderBox = context.findRenderObject() as RenderBox;
    final size = renderBox.size;
    final offset = renderBox.localToGlobal(Offset.zero);

    return OverlayEntry(
      builder: (context) => GestureDetector(
        behavior: HitTestBehavior.translucent,
        onTap: _closeDropdown,
        child: Material(
          color: Colors.transparent,
          child: Stack(
            children: [
              Positioned(
                left: offset.dx,
                top: offset.dy + size.height + 8,
                width: 320,
                child: GestureDetector(
                  onTap: () {}, // Prevent tap from closing
                  child: FadeTransition(
                    opacity: _fadeAnimation,
                    child: ScaleTransition(
                      scale: _scaleAnimation,
                      alignment: Alignment.topLeft,
                      child: _buildDropdownContent(),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDropdownContent() {
    return StatefulBuilder(
      builder: (context, setDropdownState) {
        return Container(
          constraints: const BoxConstraints(maxHeight: 400),
          decoration: BoxDecoration(
            color: AppColors.backgroundCard,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: AppColors.primaryTeal.withValues(alpha: 0.3),
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.4),
                blurRadius: 24,
                offset: const Offset(0, 12),
              ),
              BoxShadow(
                color: AppColors.primaryTeal.withValues(alpha: 0.1),
                blurRadius: 40,
                spreadRadius: -10,
              ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Search input
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.03),
                    border: Border(
                      bottom: BorderSide(
                        color: AppColors.surfaceBorder,
                      ),
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.05),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color: Colors.white.withValues(alpha: 0.1),
                          ),
                        ),
                        child: TextField(
                          controller: _searchController,
                          focusNode: _searchFocusNode,
                          style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 14,
                          ),
                          decoration: InputDecoration(
                            hintText: 'Search or enter project ID...',
                            hintStyle: TextStyle(
                              color: AppColors.textMuted,
                              fontSize: 14,
                            ),
                            prefixIcon: Icon(
                              Icons.search,
                              size: 18,
                              color: AppColors.textMuted,
                            ),
                            suffixIcon: _searchController.text.isNotEmpty
                                ? IconButton(
                                    icon: Icon(
                                      Icons.clear,
                                      size: 16,
                                      color: AppColors.textMuted,
                                    ),
                                    onPressed: () {
                                      _searchController.clear();
                                      setDropdownState(() {
                                        _searchQuery = '';
                                      });
                                    },
                                  )
                                : null,
                            border: InputBorder.none,
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 12,
                            ),
                          ),
                          onChanged: (value) {
                            setDropdownState(() {
                              _searchQuery = value;
                            });
                          },
                          onSubmitted: (value) {
                            if (_filteredProjects.isEmpty && value.isNotEmpty) {
                              _selectCustomProject(value);
                            } else if (_filteredProjects.length == 1) {
                              widget.onProjectSelected(_filteredProjects.first);
                              _closeDropdown();
                            }
                          },
                        ),
                      ),
                      // Quick tip
                      Padding(
                        padding: const EdgeInsets.only(top: 8, left: 4),
                        child: Row(
                          children: [
                            Icon(
                              Icons.lightbulb_outline,
                              size: 12,
                              color: AppColors.textMuted,
                            ),
                            const SizedBox(width: 6),
                            Text(
                              'Type to search or enter a custom project ID',
                              style: TextStyle(
                                fontSize: 11,
                                color: AppColors.textMuted,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                // Header with refresh button
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.02),
                  ),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(4),
                        decoration: BoxDecoration(
                          color: AppColors.primaryTeal.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Icon(
                          Icons.cloud_outlined,
                          size: 14,
                          color: AppColors.primaryTeal,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        'GCP Projects',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textMuted,
                          letterSpacing: 0.5,
                        ),
                      ),
                      const Spacer(),
                      Text(
                        '${_filteredProjects.length} projects',
                        style: TextStyle(
                          fontSize: 11,
                          color: AppColors.textMuted,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Material(
                        color: Colors.transparent,
                        child: InkWell(
                          onTap: widget.onRefresh,
                          borderRadius: BorderRadius.circular(6),
                          child: Padding(
                            padding: const EdgeInsets.all(6),
                            child: widget.isLoading
                                ? SizedBox(
                                    width: 14,
                                    height: 14,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      valueColor: AlwaysStoppedAnimation<Color>(
                                        AppColors.primaryTeal,
                                      ),
                                    ),
                                  )
                                : Icon(
                                    Icons.refresh,
                                    size: 14,
                                    color: AppColors.textMuted,
                                  ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                // Custom project option when search doesn't match
                if (_searchQuery.isNotEmpty && _filteredProjects.isEmpty)
                  _buildUseCustomProjectOption(_searchQuery, setDropdownState),
                // Project list
                if (_filteredProjects.isEmpty && _searchQuery.isEmpty && !widget.isLoading)
                  Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      children: [
                        Icon(
                          Icons.cloud_off_outlined,
                          size: 32,
                          color: AppColors.textMuted,
                        ),
                        const SizedBox(height: 12),
                        Text(
                          'No projects available',
                          style: TextStyle(
                            fontSize: 13,
                            color: AppColors.textMuted,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Type a project ID above to use it',
                          style: TextStyle(
                            fontSize: 12,
                            color: AppColors.textMuted,
                          ),
                        ),
                      ],
                    ),
                  )
                else if (_filteredProjects.isNotEmpty)
                  Flexible(
                    child: ListView.builder(
                      shrinkWrap: true,
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      itemCount: _filteredProjects.length,
                      itemBuilder: (context, index) {
                        final project = _filteredProjects[index];
                        final isSelected = widget.selectedProject?.projectId == project.projectId;

                        return _buildProjectItem(project, isSelected);
                      },
                    ),
                  ),
                // Use custom project when there's a search with some results
                if (_searchQuery.isNotEmpty && _filteredProjects.isNotEmpty)
                  _buildUseCustomProjectOption(_searchQuery, setDropdownState),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildUseCustomProjectOption(String projectId, StateSetter setDropdownState) {
    // Don't show if exact match exists
    final exactMatch = widget.projects.any((p) => p.projectId == projectId);
    if (exactMatch) return const SizedBox.shrink();

    return Container(
      margin: const EdgeInsets.fromLTRB(8, 4, 8, 8),
      decoration: BoxDecoration(
        color: AppColors.primaryTeal.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: AppColors.primaryTeal.withValues(alpha: 0.3),
        ),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => _selectCustomProject(projectId),
          borderRadius: BorderRadius.circular(10),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: AppColors.primaryTeal.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Icon(
                    Icons.add,
                    size: 14,
                    color: AppColors.primaryTeal,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Use "$projectId"',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w500,
                          color: AppColors.primaryTeal,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                      Text(
                        'Press Enter or click to use this project ID',
                        style: TextStyle(
                          fontSize: 11,
                          color: AppColors.textMuted,
                        ),
                      ),
                    ],
                  ),
                ),
                Icon(
                  Icons.keyboard_return,
                  size: 14,
                  color: AppColors.primaryTeal,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildProjectItem(GcpProject project, bool isSelected) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () {
            widget.onProjectSelected(project);
            _closeDropdown();
          },
          borderRadius: BorderRadius.circular(10),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            padding: const EdgeInsets.symmetric(
              horizontal: 12,
              vertical: 10,
            ),
            decoration: BoxDecoration(
              color: isSelected
                  ? AppColors.primaryTeal.withValues(alpha: 0.15)
                  : Colors.transparent,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: isSelected
                    ? AppColors.primaryTeal.withValues(alpha: 0.3)
                    : Colors.transparent,
              ),
            ),
            child: Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    gradient: isSelected
                        ? LinearGradient(
                            colors: [
                              AppColors.primaryTeal.withValues(alpha: 0.3),
                              AppColors.primaryCyan.withValues(alpha: 0.2),
                            ],
                          )
                        : null,
                    color: isSelected
                        ? null
                        : Colors.white.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    isSelected ? Icons.folder : Icons.folder_outlined,
                    size: 16,
                    color: isSelected
                        ? AppColors.primaryTeal
                        : AppColors.textMuted,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        project.name,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: isSelected
                              ? FontWeight.w600
                              : FontWeight.w500,
                          color: isSelected
                              ? AppColors.primaryTeal
                              : AppColors.textPrimary,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                      if (project.displayName != null &&
                          project.displayName != project.projectId)
                        Text(
                          project.projectId,
                          style: TextStyle(
                            fontSize: 11,
                            color: AppColors.textMuted,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                    ],
                  ),
                ),
                if (isSelected)
                  Container(
                    padding: const EdgeInsets.all(2),
                    decoration: BoxDecoration(
                      color: AppColors.primaryTeal,
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      Icons.check,
                      size: 12,
                      color: AppColors.backgroundDark,
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }



  @override
  Widget build(BuildContext context) {
    return CompositedTransformTarget(
      link: _layerLink,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _toggleDropdown,
          borderRadius: BorderRadius.circular(6),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
            decoration: BoxDecoration(
              color: _isOpen
                  ? AppColors.primaryTeal.withValues(alpha: 0.1)
                  : Colors.white.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(6),
              border: Border.all(
                color: _isOpen
                    ? AppColors.primaryTeal.withValues(alpha: 0.3)
                    : AppColors.surfaceBorder.withValues(alpha: 0.5),
              ),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.folder_outlined,
                  size: 14,
                  color: _isOpen ? AppColors.primaryTeal : AppColors.textMuted,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    widget.selectedProject?.name ?? 'Project',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: widget.selectedProject != null
                          ? AppColors.textPrimary
                          : AppColors.textMuted,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 2),
                AnimatedRotation(
                  turns: _isOpen ? 0.5 : 0,
                  duration: const Duration(milliseconds: 150),
                  child: Icon(
                    Icons.keyboard_arrow_down,
                    size: 16,
                    color: _isOpen ? AppColors.primaryTeal : AppColors.textMuted,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
