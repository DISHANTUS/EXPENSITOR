import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/companion/companion_scaffold.dart';

const _phone = '9345296730';
const _email = 'advary2006@gmail.com';

class ContactScreen extends StatelessWidget {
  const ContactScreen({super.key});

  Future<void> _launch(BuildContext context, Uri uri) async {
    final ok = await launchUrl(uri);
    if (!ok && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Couldn’t open that app.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return CompanionScaffold(
      title: 'Contact Us',
      commentary: 'Have a question or an idea? Reach out anytime.',
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.phone),
              title: const Text('Phone'),
              subtitle: const Text(_phone),
              trailing: const Icon(Icons.call),
              onTap: () => _launch(context, Uri(scheme: 'tel', path: _phone)),
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.email_outlined),
              title: const Text('Email'),
              subtitle: const Text(_email),
              trailing: const Icon(Icons.send),
              onTap: () => _launch(context, Uri(scheme: 'mailto', path: _email)),
            ),
          ),
        ],
      ),
    );
  }
}
