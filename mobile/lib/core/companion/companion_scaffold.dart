import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../analytics/analytics.dart';
import '../cache/offline_cache.dart';
import '../intervention/intervention_controller.dart';
import '../nav/app_drawer.dart';
import '../settings/settings_repository.dart';
import '../theme/app_theme.dart';
import '../theme/aurora_background.dart';
import '../theme/glass.dart';
import '../theme/theme_voice.dart';
import '../voice/voice_memory.dart';
import '../voice/voice_plan.dart';
import '../voice/voice_service.dart';
import 'companion_mood.dart';
import 'companion_orb.dart';
import 'companion_orb_button.dart';
import 'mood_models.dart';
import 'mood_repository.dart';
import 'reaction.dart';
import 'reaction_queue.dart';
import 'widgets/celebration_overlay.dart';
import 'widgets/reaction_card.dart';
import 'widgets/voice_sheet.dart';

/// Auto-handle a milestone/achievement reaction once: speak it in the celebration
/// voice (if enabled) and record achievements as timeline candidates. Normal acks
/// never auto-play (tap-to-hear).
Future<void> _handleReaction(WidgetRef ref, CompanionReaction r,
    {required bool speakCelebrations, required bool tappedOnly}) async {
  if (r.importance == ReactionImportance.normal) return;
  final mem = ref.read(voiceMemoryProvider);
  if (await mem.alreadySpoken('rx:${r.signature}')) return;
  await mem.markSpoken('rx:${r.signature}');
  if (speakCelebrations && !tappedOnly) {
    await ref.read(voiceControllerProvider.notifier).speakPlan(r.voicePlan);
  }
  if (r.importance == ReactionImportance.achievement && (r.timelineLabel ?? '').isNotEmpty) {
    await ref.read(moodRepositoryProvider).recordTimelineCandidate(r.timelineLabel!);
  }
}

/// Auto-speak the greeting on Home — only high-priority plans auto-play; routine
/// greetings need the opt-in; same signature is suppressed for ~10 min (5b).
Future<void> _maybeAutoSpeakGreeting(WidgetRef ref, VoicePlan plan, Map prefs) async {
  if (plan.isEmpty || (prefs['voice_when_tapped_only'] ?? false)) return;
  final openOptIn = prefs['speak_greeting_on_open'] ?? false;
  if (!plan.autoPlay && !openOptIn) return;          // never auto-blast routine greetings
  final mem = ref.read(voiceMemoryProvider);
  if (await mem.spokenRecently(plan.signature)) return;
  await mem.markSpokenAt(plan.signature);
  await ref.read(voiceControllerProvider.notifier).speakPlan(plan);
}

/// Whether the companion panel is collapsed. App-wide so the choice persists as
/// the user moves between screens (the companion stays available, just compact).
final companionCollapsedProvider = StateProvider<bool>((_) => false);

/// A short-lived "Advary just replied" pulse, set by the Chat screen when a new
/// AI text turn arrives (no real TTS voice involved) and cleared automatically
/// after ~1.2s. `orbState` below ORs this in alongside the real speaking check,
/// so a text reply reads as "Advary is speaking" instead of "text appeared" —
/// the actual voice/TTS speaking state is untouched.
final chatReplyPulseProvider = StateProvider<bool>((_) => false);

/// The frame every authenticated screen uses: Drawer (☰) + mic (🎤) + an
/// always-available AI companion. The face is a live, rotating mood (4c-A) that
/// falls back to the static [mood] while loading/offline.
class CompanionScaffold extends ConsumerWidget {
  const CompanionScaffold({
    super.key,
    required this.title,
    required this.child,
    this.commentary,
    this.mood = CompanionMood.neutral,
    this.actions = const [],
    this.showGreeting = false,
    this.extraLines = const [],
  });

  final String title;
  final Widget child;
  final String? commentary;
  final CompanionMood mood;
  final List<Widget> actions;
  /// Only Home shows the daily companion greeting + live rotating mood. Every
  /// other screen uses its own page `commentary` (budget, currency, date, …).
  final bool showGreeting;
  /// Extra contextual lines shown inside the SAME companion bubble (Home's
  /// thought: goal status, who owes you, next milestone). Keeps Home to ONE orb.
  final List<String> extraLines;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final collapsed = ref.watch(companionCollapsedProvider);
    // Daily greeting + live mood are Home-only; other pages keep their own commentary.
    final live = showGreeting ? ref.watch(companionMoodProvider).valueOrNull : null;
    final voiceState = ref.watch(voiceControllerProvider);
    final speaking = voiceState == VoiceState.speaking || ref.watch(chatReplyPulseProvider);

    // Reactions are GLOBAL — they show over the greeting/commentary on any page.
    final reactions = ref.watch(reactionQueueProvider);
    final reaction = reactions.isEmpty ? null : reactions.first;
    final prefs = ref.watch(userSettingsProvider).valueOrNull?.notificationPreferences ?? const {};
    ref.listen(reactionQueueProvider, (_, next) {
      if (next.isNotEmpty) {
        _handleReaction(ref, next.first,
            speakCelebrations: prefs['speak_celebrations'] ?? true,
            tappedOnly: prefs['voice_when_tapped_only'] ?? false);
      }
    });
    // Tiny analytics: count each intervention the orb raises, once per session.
    ref.listen(topInterventionProvider, (_, next) {
      if (next != null && shownInterventions.add(next.id)) {
        ref.read(analyticsProvider).track('intervention_shown', {'trigger': next.trigger.name});
      }
    });

    // Home: drain intelligence-driven reactions into the queue + auto-speak the
    // greeting (high-priority only; routine needs opt-in; deduped ~10 min).
    if (showGreeting) {
      ref.listen(companionMoodProvider, (_, next) {
        final m = next.valueOrNull;
        if (m == null) return;
        for (final r in m.pendingReactions) {
          ref.read(reactionQueueProvider.notifier).push(r);
        }
        final plan = m.greeting?.voice;
        if (plan != null) _maybeAutoSpeakGreeting(ref, plan, prefs);
      });
    }

    // Drive the orb from voice + reaction + mood.
    final orbState = speaking
        ? OrbState.speaking
        : (reaction != null && reaction.importance != ReactionImportance.normal)
            ? OrbState.celebrating
            : (mood == CompanionMood.concerned) ? OrbState.concerned : OrbState.idle;

    return PopScope(
      // Home is the root: the system back gesture exits there. Every other screen
      // intercepts back and returns to Home instead of closing the app.
      canPop: showGreeting,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) context.go('/home');
      },
      child: AuroraBackground(
        child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: Text(title),
          actions: [
            // A one-tap way back to Advary's room from anywhere (Home itself shows
            // the greeting, so it doesn't need the shortcut). The orb = Home.
            if (!showGreeting)
              IconButton(
                tooltip: 'Home',
                icon: const CompanionOrb(state: OrbState.idle, size: 26),
                onPressed: () => context.go('/home'),
              ),
            ...actions,
            IconButton(
              tooltip: 'Talk to me',
              icon: const Icon(Icons.mic_none_outlined),
              onPressed: () => showVoiceSheet(context, ref),
            ),
          ],
        ),
        drawer: const AppDrawer(),
        body: Stack(
          children: [
            Column(
          children: [
            const _OfflineBanner(),
            if (!collapsed)
              _CompanionPanel(
                commentary: commentary,
                extraLines: extraLines,
                mood: mood,
                orbState: orbState,
                live: live,
                speaking: speaking,
                reaction: reaction,
                onDismissReaction: reaction == null
                    ? null
                    : () => ref.read(reactionQueueProvider.notifier).dismiss(reaction),
                onTapReaction: (reaction?.tapRoute == null)
                    ? null
                    : () {
                        ref.read(reactionQueueProvider.notifier).dismiss(reaction!);
                        context.go(reaction.tapRoute!);
                      },
                onCollapse: () => ref.read(companionCollapsedProvider.notifier).state = true,
              ),
            Expanded(child: child),
          ],
            ),
            const Positioned(top: 0, left: 0, right: 0, child: CelebrationOverlay()),
          ],
        ),
        floatingActionButton: collapsed
            ? FloatingActionButton(
                tooltip: 'Show advisor',
                backgroundColor: Colors.transparent,
                elevation: 0,
                onPressed: () => ref.read(companionCollapsedProvider.notifier).state = false,
                child: CompanionOrb(state: orbState, size: 44),
              )
            : null,
      ),
      ),
    );
  }
}

/// A slim, dismissable-by-nature (it just disappears once connectivity is
/// back) banner: shown whenever any [OfflineCache]-backed screen is
/// currently displaying its last-cached data instead of a live fetch.
class _OfflineBanner extends ConsumerWidget {
  const _OfflineBanner();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cache = ref.watch(offlineCacheProvider);
    return ValueListenableBuilder<bool>(
      valueListenable: cache.isOffline,
      builder: (context, offline, _) {
        if (!offline) return const SizedBox.shrink();
        final p = AppColors.active;
        return Container(
          width: double.infinity,
          color: p.muted,
          padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 14),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.cloud_off_outlined, size: 14, color: p.on),
              const SizedBox(width: 6),
              Text('Offline — showing saved data',
                  style: TextStyle(color: p.on, fontSize: 12, fontWeight: FontWeight.w600)),
            ],
          ),
        );
      },
    );
  }
}

class _CompanionPanel extends StatelessWidget {
  const _CompanionPanel({
    required this.commentary,
    required this.extraLines,
    required this.mood,
    required this.orbState,
    required this.live,
    required this.speaking,
    required this.reaction,
    required this.onDismissReaction,
    required this.onTapReaction,
    required this.onCollapse,
  });
  final String? commentary;
  final List<String> extraLines;
  final CompanionMood mood;
  final OrbState orbState;
  final MoodState? live;
  final bool speaking;
  final CompanionReaction? reaction;
  final VoidCallback? onDismissReaction;
  final VoidCallback? onTapReaction;
  final VoidCallback onCollapse;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final accent = mood.color(cs);
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
      child: GlassCard(
        padding: const EdgeInsets.fromLTRB(8, 8, 6, 10),
        radius: 24,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            // The orb is alive: tap → a fun fact, double-tap → encouragement,
            // long-press → "how I'm feeling".
            CompanionOrbButton(orbState: orbState, size: 48, live: live, encouragements: extraLines),
            const SizedBox(width: 6),
            Expanded(
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 350),
                child: reaction != null
                    ? ReactionCard(reaction!, key: ValueKey('rx:${reaction!.signature}'),
                        onDismiss: onDismissReaction ?? () {}, onTap: onTapReaction)
                    : _GreetingBubble(live: live, commentary: commentary, extraLines: extraLines, accent: accent),
              ),
            ),
            IconButton(
              tooltip: 'Collapse',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.keyboard_arrow_up),
              onPressed: onCollapse,
            ),
          ],
        ),
      ),
    );
  }
}

/// The greeting bubble: cross-fades when a background-narrated version arrives
/// (version-based, not polling), and shows "why did I say this?" on tap.
class _GreetingBubble extends ConsumerStatefulWidget {
  const _GreetingBubble({required this.live, required this.commentary, required this.accent, this.extraLines = const []});
  final MoodState? live;
  final String? commentary;
  final Color accent;
  final List<String> extraLines;

  @override
  ConsumerState<_GreetingBubble> createState() => _GreetingBubbleState();
}

class _GreetingBubbleState extends ConsumerState<_GreetingBubble> {
  String? _lastText;       // tracks the current greeting version
  int _refreshes = 0;      // bounded retries while narration is pending

  void _maybeScheduleRefresh() {
    final g = widget.live?.greeting;
    if (g == null) return;
    if (g.displayText != _lastText) {               // a new greeting version arrived
      _lastText = g.displayText;
      _refreshes = 0;
    }
    // Poll a few times while the richer narration is still being generated, then
    // stop (it fades in via AnimatedSwitcher once narration_source == ollama).
    if (g.pendingNarration && g.narrationSource != 'ollama' && _refreshes < 3) {
      _refreshes++;
      Future.delayed(const Duration(seconds: 5), () {
        if (mounted) ref.invalidate(companionMoodProvider);
      });
    }
  }

  @override
  void initState() {
    super.initState();
    _maybeScheduleRefresh();
  }

  @override
  void didUpdateWidget(_GreetingBubble old) {
    super.didUpdateWidget(old);
    _maybeScheduleRefresh();
  }

  void _showGreetingReasons() {
    final g = widget.live?.greeting;
    if (g == null || g.reasons.isEmpty) return;
    showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Why did I say this?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [for (final r in g.reasons) Text(r.detail.isEmpty ? '• ${r.label}' : '• ${r.label}: ${r.detail}')],
        ),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('OK'))],
      ),
    );
  }

  /// Tap the bubble to hear it: the greeting's paced VoicePlan when present,
  /// else the plain page commentary (5c moved "read aloud" here from the mic).
  void _readAloud() {
    final voice = ref.read(voiceControllerProvider.notifier);
    final plan = widget.live?.greeting?.voice;
    if (plan != null && !plan.isEmpty) {
      voice.togglePlan(plan);
    } else {
      final text = (widget.live?.greeting?.spokenText ?? widget.commentary ?? '').trim();
      if (text.isNotEmpty) voice.toggle(text);
    }
  }

  /// Surface phrasing per the active theme's personality — never touches a
  /// number, date, or name, only line prefixes/final punctuation (see
  /// `theme_voice.dart`). Applied right at render time so every text source
  /// (Ollama-narrated, deterministic salutation+lines, or the plain
  /// fallback) gets it, without changing what the engines actually computed.
  String _voice(String text) => themeVoice(text, AppColors.active.personality);

  Widget _body(Greeting? g) {
    final tt = Theme.of(context).textTheme;
    if (g != null && g.narrationSource == 'ollama' && g.displayText.isNotEmpty) {
      return Text(_voice(g.displayText), key: ValueKey('o:${g.displayText}'), style: tt.bodyMedium);
    }
    if (g != null && g.salutation.isNotEmpty) {
      return Column(
        key: ValueKey('d:${g.displayText}'),
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(_voice(g.salutation), style: tt.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
          for (final line in g.lines)
            Padding(padding: const EdgeInsets.only(top: 2), child: Text(_voice(line), style: tt.bodyMedium)),
        ],
      );
    }
    return Text(_voice(widget.commentary ?? 'I’m here whenever you need me.'), key: const ValueKey('fallback'),
        style: tt.bodyMedium);
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final g = widget.live?.greeting;
    final hasReasons = g != null && g.reasons.isNotEmpty;
    return GestureDetector(
      onTap: _readAloud,                                   // tap → hear it (5c)
      onLongPress: hasReasons ? _showGreetingReasons : null,  // long-press → "why did I say this?"
      child: Container(
        padding: const EdgeInsets.fromLTRB(4, 6, 8, 6),
        decoration: g?.specialDay != null
            ? BoxDecoration(color: cs.tertiaryContainer.withValues(alpha: 0.4), borderRadius: BorderRadius.circular(14))
            : null,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 450),
              transitionBuilder: (child, anim) => FadeTransition(opacity: anim, child: child),
              child: _body(g),
            ),
            // Home's contextual thought — goal status, who owes you, next milestone —
            // lives in this SAME bubble so there's only one companion on screen.
            for (final line in widget.extraLines)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(line,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant, height: 1.3)),
              ),
            // Greeting sign-off with the companion's name (6c), Home greeting only.
            if (g != null && (widget.live?.companionName ?? '').isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Align(
                  alignment: Alignment.centerRight,
                  child: Text('— ${widget.live!.companionName}',
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                          color: Theme.of(context).colorScheme.primary, fontStyle: FontStyle.italic)),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Cycles through the mood rotation (~2s each) with a gentle cross-fade. Falls
/// back to a single static glyph when there's nothing to rotate.
class RotatingFace extends StatefulWidget {
  const RotatingFace({super.key, required this.faces, required this.fallback, required this.fontSize});
  final List<MoodFace> faces;
  final String fallback;
  final double fontSize;

  @override
  State<RotatingFace> createState() => _RotatingFaceState();
}

class _RotatingFaceState extends State<RotatingFace> {
  Timer? _timer;
  int _i = 0;

  @override
  void initState() {
    super.initState();
    _restart();
  }

  @override
  void didUpdateWidget(RotatingFace old) {
    super.didUpdateWidget(old);
    if (old.faces.map((f) => f.id).join() != widget.faces.map((f) => f.id).join()) {
      _i = 0;
      _restart();
    }
  }

  void _restart() {
    _timer?.cancel();
    if (widget.faces.length > 1) {
      _timer = Timer.periodic(const Duration(seconds: 2), (_) {
        if (mounted) setState(() => _i = (_i + 1) % widget.faces.length);
      });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final emoji = widget.faces.isNotEmpty ? widget.faces[_i % widget.faces.length].emoji : widget.fallback;
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 400),
      transitionBuilder: (child, anim) => FadeTransition(opacity: anim, child: child),
      child: Text(emoji, key: ValueKey(emoji), style: TextStyle(fontSize: widget.fontSize)),
    );
  }
}
