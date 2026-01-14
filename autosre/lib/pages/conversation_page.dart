import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:genui/genui.dart';

import '../agent/adk_content_generator.dart';
import '../catalog.dart';
import '../services/project_service.dart';
import '../theme/app_theme.dart';

class ConversationPage extends StatefulWidget {
  const ConversationPage({super.key});

  @override
  State<ConversationPage> createState() => _ConversationPageState();
}

class _ConversationPageState extends State<ConversationPage>
    with TickerProviderStateMixin {
  late final A2uiMessageProcessor _messageProcessor;
  late final GenUiConversation _conversation;
  late final ADKContentGenerator _contentGenerator;
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _focusNode = FocusNode();
  final ProjectService _projectService = ProjectService();

  late AnimationController _backgroundController;
  late AnimationController _typingController;

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

    // Background animation
    _backgroundController = AnimationController(
      duration: const Duration(seconds: 15),
      vsync: this,
    )..repeat(reverse: true);

    // Typing indicator animation
    _typingController = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: this,
    )..repeat();

    final sreCatalog = CatalogRegistry.createSreCatalog();

    _messageProcessor = A2uiMessageProcessor(
      catalogs: [
        sreCatalog,
        CoreCatalogItems.asCatalog(),
      ],
    );

    _contentGenerator = ADKContentGenerator();

    _conversation = GenUiConversation(
      a2uiMessageProcessor: _messageProcessor,
      contentGenerator: _contentGenerator,
      onSurfaceAdded: (update) => _scrollToBottom(),
      onSurfaceUpdated: (update) {},
      onTextResponse: (text) => _scrollToBottom(),
    );

    // Fetch projects on startup
    _projectService.fetchProjects();

    // Update content generator when project selection changes
    _projectService.selectedProject.addListener(_onProjectChanged);
  }

  void _onProjectChanged() {
    _contentGenerator.projectId = _projectService.selectedProjectId;
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
      extendBodyBehindAppBar: true,
      appBar: _buildAppBar(),
      body: Stack(
        children: [
          // Animated gradient background
          _buildAnimatedBackground(),

          // Main content
          SafeArea(
            child: Column(
              children: [
                Expanded(child: _buildMessageList()),
                _buildInputArea(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return PreferredSize(
      preferredSize: const Size.fromHeight(85), // Increased height to prevent overflow
      child: ClipRRect(
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Container(
            decoration: BoxDecoration(
              color: AppColors.backgroundDark.withValues(alpha: 0.8),
              border: Border(
                bottom: BorderSide(
                  color: AppColors.surfaceBorder,
                  width: 1,
                ),
              ),
            ),
            child: SafeArea(
              child: Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                child: Row(
                  children: [
                    // Logo/Icon
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            AppColors.primaryTeal.withValues(alpha: 0.2),
                            AppColors.primaryCyan.withValues(alpha: 0.2),
                          ],
                        ),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: AppColors.primaryTeal.withValues(alpha: 0.3),
                        ),
                      ),
                      child: const Icon(
                        Icons.auto_awesome,
                        color: AppColors.primaryTeal,
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 14),
                    // Title
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        ShaderMask(
                          shaderCallback: (bounds) =>
                              AppColors.primaryGradient.createShader(bounds),
                          child: const Text(
                            'AutoSRE',
                            style: TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ),
                        Text(
                          'AI-Powered SRE Assistant',
                          style: TextStyle(
                            fontSize: 12,
                            color: AppColors.textMuted,
                            fontWeight: FontWeight.w400,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(width: 20),
                    // Project Selector
                    _buildProjectSelector(),
                    const Spacer(),
                    // Status indicator
                    ValueListenableBuilder<bool>(
                      valueListenable: _contentGenerator.isConnected,
                      builder: (context, isConnected, _) {
                        return ValueListenableBuilder<bool>(
                          valueListenable: _contentGenerator.isProcessing,
                          builder: (context, isProcessing, _) {
                            return _buildStatusIndicator(isProcessing, isConnected);
                          },
                        );
                      },
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildStatusIndicator(bool isProcessing, bool isConnected) {
    Color statusColor;
    String statusText;

    if (isProcessing) {
      statusColor = AppColors.primaryTeal;
      statusText = 'Analyzing...';
    } else if (isConnected) {
      statusColor = AppColors.success;
      statusText = 'Connected';
    } else {
      statusColor = AppColors.error;
      statusText = 'Disconnected';
    }

    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: statusColor.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: statusColor.withValues(alpha: 0.3),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (isProcessing)
            SizedBox(
              width: 12,
              height: 12,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor:
                    AlwaysStoppedAnimation<Color>(statusColor),
              ),
            )
          else
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: statusColor,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: statusColor.withValues(alpha: 0.5),
                    blurRadius: 6,
                  ),
                ],
              ),
            ),
          const SizedBox(width: 8),
          Text(
            statusText,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: statusColor,
            ),
          ),
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

  Widget _buildAnimatedBackground() {
    return AnimatedBuilder(
      animation: _backgroundController,
      builder: (context, child) {
        return Container(
          decoration: BoxDecoration(
            gradient: RadialGradient(
              center: Alignment(
                -0.5 + _backgroundController.value * 1.0,
                -0.8 + _backgroundController.value * 0.3,
              ),
              radius: 1.8,
              colors: [
                AppColors.primaryTeal.withValues(alpha: 0.06),
                AppColors.backgroundDark,
              ],
            ),
          ),
          child: Container(
            decoration: BoxDecoration(
              gradient: RadialGradient(
                center: Alignment(
                  0.8 - _backgroundController.value * 0.5,
                  0.6 - _backgroundController.value * 0.4,
                ),
                radius: 1.5,
                colors: [
                  AppColors.primaryBlue.withValues(alpha: 0.04),
                  Colors.transparent,
                ],
              ),
            ),
          ),
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

        return ListView.builder(
          controller: _scrollController,
          padding: const EdgeInsets.fromLTRB(16, 20, 16, 16),
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
        );
      },
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  AppColors.primaryTeal.withValues(alpha: 0.15),
                  AppColors.primaryCyan.withValues(alpha: 0.1),
                ],
              ),
              shape: BoxShape.circle,
              border: Border.all(
                color: AppColors.primaryTeal.withValues(alpha: 0.3),
              ),
            ),
            child: const Icon(
              Icons.auto_awesome_outlined,
              size: 48,
              color: AppColors.primaryTeal,
            ),
          ),
          const SizedBox(height: 24),
          Text(
            'How can I help you today?',
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
          const SizedBox(height: 12),
          Text(
            'Ask me about traces, logs, metrics, or any SRE investigation.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppColors.textMuted,
                ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 40),
          // Quick action suggestions
          Wrap(
            spacing: 12,
            runSpacing: 12,
            alignment: WrapAlignment.center,
            children: [
              _buildSuggestionChip('Analyze recent traces'),
              _buildSuggestionChip('Check error logs'),
              _buildSuggestionChip('View metric anomalies'),
            ],
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
        borderRadius: BorderRadius.circular(20),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.05),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: AppColors.surfaceBorder,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.arrow_outward,
                size: 14,
                color: AppColors.primaryTeal,
              ),
              const SizedBox(width: 8),
              Text(
                text,
                style: TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 13,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTypingIndicator() {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(top: 8, bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: GlassDecoration.aiMessage(),
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
                  margin: EdgeInsets.only(right: index < 2 ? 6 : 0),
                  child: Transform.translate(
                    offset: Offset(0, -bounce * 8),
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: AppColors.primaryTeal.withValues(
                          alpha: 0.5 + bounce,
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
    return ClipRRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                AppColors.backgroundDark.withValues(alpha: 0.75),
                AppColors.backgroundDark.withValues(alpha: 0.95),
              ],
            ),
            border: Border(
              top: BorderSide(
                color: AppColors.surfaceBorder,
                width: 1,
              ),
            ),
          ),
          child: SafeArea(
            top: false,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Selected project indicator
                ValueListenableBuilder<GcpProject?>(
                  valueListenable: _projectService.selectedProject,
                  builder: (context, project, _) {
                    if (project == null) return const SizedBox.shrink();
                    return Container(
                      margin: const EdgeInsets.only(bottom: 10),
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: AppColors.primaryTeal.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: AppColors.primaryTeal.withValues(alpha: 0.2),
                        ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.cloud_done_outlined,
                            size: 14,
                            color: AppColors.primaryTeal,
                          ),
                          const SizedBox(width: 6),
                          Text(
                            'Project: ${project.name}',
                            style: TextStyle(
                              fontSize: 12,
                              color: AppColors.primaryTeal,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
                // Input row
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Expanded(
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 200),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.06),
                          borderRadius: BorderRadius.circular(24),
                          border: Border.all(
                            color: _focusNode.hasFocus
                                ? AppColors.primaryTeal.withValues(alpha: 0.4)
                                : Colors.white.withValues(alpha: 0.1),
                            width: _focusNode.hasFocus ? 1.5 : 1,
                          ),
                          boxShadow: _focusNode.hasFocus
                              ? [
                                  BoxShadow(
                                    color: AppColors.primaryTeal.withValues(alpha: 0.1),
                                    blurRadius: 12,
                                    spreadRadius: -2,
                                  ),
                                ]
                              : null,
                        ),
                        child: TextField(
                          controller: _textController,
                          focusNode: _focusNode,
                          onSubmitted: (_) => _sendMessage(),
                          maxLines: 5,
                          minLines: 1,
                          style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 15,
                            height: 1.4,
                          ),
                          decoration: InputDecoration(
                            hintText: "Ask AutoSRE anything...",
                            hintStyle: TextStyle(
                              color: AppColors.textMuted,
                              fontSize: 15,
                            ),
                            border: InputBorder.none,
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 20,
                              vertical: 14,
                            ),
                            prefixIcon: Padding(
                              padding: const EdgeInsets.only(left: 14, right: 4),
                              child: Icon(
                                Icons.auto_awesome_outlined,
                                color: AppColors.textMuted.withValues(alpha: 0.5),
                                size: 18,
                              ),
                            ),
                            prefixIconConstraints: const BoxConstraints(
                              minWidth: 0,
                              minHeight: 0,
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    ValueListenableBuilder<bool>(
                      valueListenable: _contentGenerator.isProcessing,
                      builder: (context, isProcessing, _) {
                        return _SendButton(
                          isProcessing: isProcessing,
                          onPressed: _sendMessage,
                        );
                      },
                    ),
                  ],
                ),
                // Keyboard hint
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        'Press ',
                        style: TextStyle(
                          fontSize: 11,
                          color: AppColors.textMuted.withValues(alpha: 0.6),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          'Enter',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textMuted.withValues(alpha: 0.8),
                          ),
                        ),
                      ),
                      Text(
                        ' to send, ',
                        style: TextStyle(
                          fontSize: 11,
                          color: AppColors.textMuted.withValues(alpha: 0.6),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          'Shift + Enter',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textMuted.withValues(alpha: 0.8),
                          ),
                        ),
                      ),
                      Text(
                        ' for new line',
                        style: TextStyle(
                          fontSize: 11,
                          color: AppColors.textMuted.withValues(alpha: 0.6),
                        ),
                      ),
                    ],
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
    _projectService.selectedProject.removeListener(_onProjectChanged);
    _backgroundController.dispose();
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
          margin: const EdgeInsets.symmetric(vertical: 6),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
          constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.75,
          ),
          decoration: GlassDecoration.userMessage(),
          child: MarkdownBody(
            data: msg.text,
            styleSheet: MarkdownStyleSheet(
              p: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 15,
                height: 1.5,
              ),
              code: TextStyle(
                backgroundColor: Colors.black.withValues(alpha: 0.2),
                color: AppColors.primaryTeal,
                fontSize: 13,
              ),
            ),
          ),
        ),
      );
    } else if (msg is AiTextMessage) {
      return Align(
        alignment: Alignment.centerLeft,
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 6),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
          constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.85,
          ),
          decoration: GlassDecoration.aiMessage(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    padding: const EdgeInsets.all(4),
                    decoration: BoxDecoration(
                      color: AppColors.primaryTeal.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Icon(
                      Icons.auto_awesome,
                      size: 12,
                      color: AppColors.primaryTeal,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'AutoSRE',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textMuted,
                      letterSpacing: 0.5,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              MarkdownBody(
                data: msg.text,
                styleSheet: MarkdownStyleSheet(
                  p: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 15,
                    height: 1.6,
                  ),
                  h1: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 22,
                    fontWeight: FontWeight.w600,
                  ),
                  h2: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                  ),
                  code: TextStyle(
                    backgroundColor: Colors.black.withValues(alpha: 0.3),
                    color: AppColors.primaryTeal,
                    fontSize: 13,
                    fontFamily: 'monospace',
                  ),
                  codeblockDecoration: BoxDecoration(
                    color: Colors.black.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: AppColors.surfaceBorder,
                    ),
                  ),
                  blockquoteDecoration: BoxDecoration(
                    color: AppColors.primaryTeal.withValues(alpha: 0.1),
                    border: Border(
                      left: BorderSide(
                        color: AppColors.primaryTeal,
                        width: 3,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    } else if (msg is AiUiMessage) {
      return Align(
        alignment: Alignment.centerLeft,
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 8),
          constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.95,
          ),
          decoration: GlassDecoration.card(borderRadius: 16),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
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

/// Animated send button with pulse effect
class _SendButton extends StatefulWidget {
  final bool isProcessing;
  final VoidCallback onPressed;

  const _SendButton({
    required this.isProcessing,
    required this.onPressed,
  });

  @override
  State<_SendButton> createState() => _SendButtonState();
}

class _SendButtonState extends State<_SendButton>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );
    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.08).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void didUpdateWidget(_SendButton oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isProcessing && !oldWidget.isProcessing) {
      _pulseController.repeat(reverse: true);
    } else if (!widget.isProcessing && oldWidget.isProcessing) {
      _pulseController.stop();
      _pulseController.reset();
    }
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _pulseAnimation,
      builder: (context, child) {
        return Transform.scale(
          scale: widget.isProcessing ? _pulseAnimation.value : 1.0,
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: widget.isProcessing ? null : widget.onPressed,
              borderRadius: BorderRadius.circular(18),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  gradient: widget.isProcessing
                      ? LinearGradient(
                          colors: [
                            AppColors.primaryBlue.withValues(alpha: 0.6),
                            AppColors.primaryCyan.withValues(alpha: 0.6),
                          ],
                        )
                      : LinearGradient(
                          colors: [
                            AppColors.primaryTeal,
                            AppColors.primaryCyan,
                          ],
                        ),
                  borderRadius: BorderRadius.circular(18),
                  boxShadow: [
                    BoxShadow(
                      color: (widget.isProcessing
                              ? AppColors.primaryBlue
                              : AppColors.primaryTeal)
                          .withValues(alpha: 0.35),
                      blurRadius: widget.isProcessing ? 16 : 12,
                      offset: const Offset(0, 4),
                      spreadRadius: widget.isProcessing ? 0 : -2,
                    ),
                  ],
                ),
                child: widget.isProcessing
                    ? SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.5,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            Colors.white.withValues(alpha: 0.9),
                          ),
                        ),
                      )
                    : Icon(
                        Icons.arrow_upward_rounded,
                        color: AppColors.backgroundDark,
                        size: 22,
                      ),
              ),
            ),
          ),
        );
      },
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
      _searchFocusNode.requestFocus();
    });
  }

  void _closeDropdown() {
    _animationController.reverse().then((_) {
      _overlayEntry?.remove();
      _overlayEntry = null;
    });
    setState(() {
      _isOpen = false;
      _searchQuery = '';
      _searchController.clear();
    });
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
  void dispose() {
    _animationController.dispose();
    _searchController.dispose();
    _searchFocusNode.dispose();
    _closeDropdown();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return CompositedTransformTarget(
      link: _layerLink,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _toggleDropdown,
          borderRadius: BorderRadius.circular(12),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              gradient: _isOpen
                  ? LinearGradient(
                      colors: [
                        AppColors.primaryTeal.withValues(alpha: 0.2),
                        AppColors.primaryCyan.withValues(alpha: 0.15),
                      ],
                    )
                  : null,
              color: _isOpen
                  ? null
                  : Colors.white.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: _isOpen
                    ? AppColors.primaryTeal.withValues(alpha: 0.5)
                    : AppColors.surfaceBorder,
                width: _isOpen ? 1.5 : 1,
              ),
              boxShadow: _isOpen
                  ? [
                      BoxShadow(
                        color: AppColors.primaryTeal.withValues(alpha: 0.2),
                        blurRadius: 12,
                        spreadRadius: -2,
                      ),
                    ]
                  : null,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  padding: const EdgeInsets.all(4),
                  decoration: BoxDecoration(
                    color: _isOpen
                        ? AppColors.primaryTeal.withValues(alpha: 0.2)
                        : Colors.white.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Icon(
                    Icons.cloud_outlined,
                    size: 14,
                    color: _isOpen ? AppColors.primaryTeal : AppColors.textMuted,
                  ),
                ),
                const SizedBox(width: 10),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 140),
                  child: Text(
                    widget.selectedProject?.name ?? 'Select Project',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color: widget.selectedProject != null
                          ? AppColors.textPrimary
                          : AppColors.textMuted,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 8),
                AnimatedRotation(
                  turns: _isOpen ? 0.5 : 0,
                  duration: const Duration(milliseconds: 200),
                  child: Icon(
                    Icons.keyboard_arrow_down,
                    size: 18,
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
