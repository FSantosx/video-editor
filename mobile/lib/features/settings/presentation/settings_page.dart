import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/l10n.dart';
import '../../../core/providers.dart';
import '../domain/app_settings.dart';

class SettingsPage extends ConsumerStatefulWidget {
  const SettingsPage({super.key});

  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  final _formKey = GlobalKey<FormState>();
  final _url = TextEditingController();
  final _apiKey = TextEditingController();
  bool _obscure = true;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    final current = ref.read(settingsProvider).value;
    _url.text = current?.serverUrl ?? '';
    _apiKey.text = current?.apiKey ?? '';
  }

  @override
  void dispose() {
    _url.dispose();
    _apiKey.dispose();
    super.dispose();
  }

  AppSettings get _draft => AppSettings(
        serverUrl: AppSettings.normalizeUrl(_url.text),
        apiKey: _apiKey.text.trim(),
      );

  /// Valida URL e chave chamando /videos (que exige a chave), não só /health.
  Future<bool> _testConnection() async {
    final l10n = context.l10n;
    final messenger = ScaffoldMessenger.of(context);
    final draft = _draft;
    try {
      await Dio(BaseOptions(
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 15),
        headers: {if (draft.apiKey.isNotEmpty) 'X-API-Key': draft.apiKey},
      )).get<void>('${draft.serverUrl}/videos');
      messenger.showSnackBar(SnackBar(content: Text(l10n.connectionOk)));
      return true;
    } on DioException catch (e) {
      final msg = e.response?.statusCode == 401 ? l10n.errorUnauthorized : l10n.errorNetwork;
      messenger.showSnackBar(SnackBar(content: Text(msg)));
      return false;
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _busy = true);
    final ok = await _testConnection();
    if (ok) {
      await ref.read(settingsProvider.notifier).save(_draft);
      if (mounted) context.go('/');
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.settingsTitle)),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(l10n.settingsIntro, style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(height: 16),
            TextFormField(
              controller: _url,
              keyboardType: TextInputType.url,
              autocorrect: false,
              decoration: InputDecoration(
                labelText: l10n.serverUrl,
                hintText: 'https://meu-app.up.railway.app',
                border: const OutlineInputBorder(),
              ),
              validator: (v) => AppSettings.isValidUrl(v ?? '') ? null : l10n.invalidUrl,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _apiKey,
              obscureText: _obscure,
              autocorrect: false,
              decoration: InputDecoration(
                labelText: l10n.apiKey,
                border: const OutlineInputBorder(),
                suffixIcon: IconButton(
                  tooltip: _obscure ? l10n.showKey : l10n.hideKey,
                  icon: Icon(_obscure ? Icons.visibility : Icons.visibility_off),
                  onPressed: () => setState(() => _obscure = !_obscure),
                ),
              ),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: _busy ? null : _save,
              icon: _busy
                  ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.check),
              label: Text(l10n.saveAndConnect),
            ),
          ],
        ),
      ),
    );
  }
}
