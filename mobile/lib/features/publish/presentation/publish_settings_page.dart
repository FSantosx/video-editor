import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/l10n.dart';
import '../../../core/providers.dart';
import '../../../core/result.dart';
import '../../../core/widgets/error_view.dart';
import '../domain/publish_models.dart';

/// Horários de postagem e conexão com o canal do YouTube.
class PublishSettingsPage extends ConsumerWidget {
  const PublishSettingsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final settings = ref.watch(publishSettingsProvider);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.publishSettings)),
      body: settings.when(
        data: (s) => RefreshIndicator(
          onRefresh: () => ref.refresh(publishSettingsProvider.future),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [_SlotsSection(settings: s), const Divider(height: 32), _YoutubeSection(status: s.youtube)],
          ),
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorView(error: e, onRetry: () => ref.invalidate(publishSettingsProvider)),
      ),
    );
  }
}

class _SlotsSection extends ConsumerWidget {
  const _SlotsSection({required this.settings});

  final PublishSettings settings;

  Future<void> _save(BuildContext context, WidgetRef ref, List<String> slots) async {
    final result = await ref.read(publishRepositoryProvider)!.saveSlots(slots);
    if (!context.mounted) return;
    if (result case Err(:final failure)) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(failure.message(context.l10n))));
    }
    ref.invalidate(publishSettingsProvider);
  }

  Future<void> _add(BuildContext context, WidgetRef ref) async {
    final time = await showTimePicker(context: context, initialTime: const TimeOfDay(hour: 15, minute: 0));
    if (time == null || !context.mounted) return;
    final value = '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}';
    await _save(context, ref, {...settings.slots, value}.toList());
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(l10n.slotsTitle, style: theme.textTheme.titleMedium),
        Text(l10n.slotsHint(settings.tz), style: theme.textTheme.bodySmall),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final slot in settings.slots)
              InputChip(
                label: Text(slot),
                onDeleted: settings.slots.length > 1
                    ? () => _save(context, ref, [...settings.slots]..remove(slot))
                    : null,
              ),
            ActionChip(
              avatar: const Icon(Icons.add, size: 18),
              label: Text(l10n.addSlot),
              onPressed: () => _add(context, ref),
            ),
          ],
        ),
      ],
    );
  }
}

class _YoutubeSection extends ConsumerWidget {
  const _YoutubeSection({required this.status});

  final YoutubeStatus status;

  Future<void> _connect(BuildContext context, WidgetRef ref) async {
    final result = await ref.read(publishRepositoryProvider)!.youtubeConnectUrl();
    if (!context.mounted) return;
    switch (result) {
      case Ok(:final value):
        await launchUrl(value, mode: LaunchMode.externalApplication);
      case Err(:final failure):
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(failure.message(context.l10n))));
    }
  }

  Future<void> _disconnect(WidgetRef ref) async {
    await ref.read(publishRepositoryProvider)!.youtubeDisconnect();
    ref.invalidate(publishSettingsProvider);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(l10n.youtubeSection, style: theme.textTheme.titleMedium),
        const SizedBox(height: 8),
        if (!status.configured)
          Text(l10n.youtubeNotConfigured)
        else if (!status.connected) ...[
          FilledButton.icon(
            onPressed: () => _connect(context, ref),
            icon: const Icon(Icons.link),
            label: Text(l10n.youtubeConnect),
          ),
          const SizedBox(height: 4),
          Text(l10n.youtubeConnectHint, style: theme.textTheme.bodySmall),
        ] else ...[
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.check_circle, color: Colors.green),
            title: Text(l10n.youtubeConnected(status.channelTitle ?? '?')),
            trailing: TextButton(onPressed: () => _disconnect(ref), child: Text(l10n.youtubeDisconnect)),
          ),
          Text(status.autoUpload ? l10n.youtubeAuto : l10n.youtubeAuditPending),
        ],
      ],
    );
  }
}
