import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/auth_controller.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _registerMode = false;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final notifier = ref.read(authControllerProvider.notifier);
    final email = _email.text.trim();
    final password = _password.text;
    if (_registerMode) {
      await notifier.register(email, password);
    } else {
      await notifier.login(email, password);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(authControllerProvider);
    final busy = state.busy;

    return Scaffold(
      appBar: AppBar(title: Text(_registerMode ? 'Create account' : 'Welcome back')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Form(
            key: _formKey,
            child: ListView(
              children: [
                const SizedBox(height: 8),
                TextFormField(
                  controller: _email,
                  enabled: !busy,
                  keyboardType: TextInputType.emailAddress,
                  decoration: const InputDecoration(labelText: 'Email'),
                  validator: (v) => (v == null || !v.contains('@')) ? 'Enter a valid email' : null,
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _password,
                  enabled: !busy,
                  obscureText: true,
                  decoration: const InputDecoration(labelText: 'Password'),
                  validator: (v) => (v == null || v.length < 8) ? 'At least 8 characters' : null,
                ),
                if (state.error != null) ...[
                  const SizedBox(height: 16),
                  Text(state.error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                ],
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: busy ? null : _submit,
                  child: busy
                      ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : Text(_registerMode ? 'Create account' : 'Log in'),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: busy ? null : () => setState(() => _registerMode = !_registerMode),
                  child: Text(_registerMode ? 'I already have an account' : "Create an account"),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
