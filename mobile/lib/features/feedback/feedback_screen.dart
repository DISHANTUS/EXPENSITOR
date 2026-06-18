import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/companion/companion_scaffold.dart';

const _to = 'advary2006@gmail.com';

/// Send feedback. No backend endpoint is needed — it composes an email with the
/// user's message prefilled, the same lightweight approach as Contact Us.
class FeedbackScreen extends StatefulWidget {
  const FeedbackScreen({super.key});

  @override
  State<FeedbackScreen> createState() => _FeedbackScreenState();
}

class _FeedbackScreenState extends State<FeedbackScreen> {
  final _ctrl = TextEditingController();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final body = _ctrl.text.trim();
    if (body.isEmpty) return;
    final uri = Uri(
      scheme: 'mailto',
      path: _to,
      query: 'subject=${Uri.encodeComponent('Advary feedback')}&body=${Uri.encodeComponent(body)}',
    );
    final ok = await launchUrl(uri);
    if (!mounted) return;
    if (ok) {
      _ctrl.clear();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Thanks — opening your email to send.')));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Couldn’t open an email app.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return CompanionScaffold(
      title: 'Feedback',
      commentary: 'Tell me what’s working and what isn’t — it genuinely shapes what I build next.',
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _ctrl,
            minLines: 4,
            maxLines: 8,
            decoration: const InputDecoration(
              labelText: 'Your feedback',
              hintText: 'An idea, a bug, something that confused you…',
              alignLabelWithHint: true,
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(onPressed: _send, icon: const Icon(Icons.send), label: const Text('Send feedback')),
          const SizedBox(height: 8),
          Text('Sends to $_to', style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }
}
