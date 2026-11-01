import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/l10n.dart';
import '../../../core/providers.dart';
import '../../../core/widgets/error_view.dart';
import '../domain/publish_models.dart';
import 'publish_widgets.dart';

/// Fila de publicação agrupada por dia.
class AgendaPage extends ConsumerWidget {
  const AgendaPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final queue = ref.watch(publishQueueProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.agendaTitle),
        actions: [
          IconButton(
            tooltip: l10n.publishSettings,
            icon: const Icon(Icons.tune),
            onPressed: () => context.push('/publish/settings'),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(publishQueueProvider.future),
        child: queue.when(
          data: (items) => items.isEmpty
              ? ListView(padding: const EdgeInsets.all(32), children: [
                  const SizedBox(height: 60),
                  Icon(Icons.event_available, size: 64, color: Theme.of(context).colorScheme.outline),
                  const SizedBox(height: 16),
                  Text(l10n.agendaEmpty, textAlign: TextAlign.center),
                ])
              : _AgendaList(items: items),
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(children: [
            ErrorView(error: e, onRetry: () => ref.invalidate(publishQueueProvider)),
          ]),
        ),
      ),
    );
  }
}

class _AgendaList extends ConsumerWidget {
  const _AgendaList({required this.items});

  final List<PublishItem> items;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final locale = Localizations.localeOf(context).toString();
    final groups = groupByDay(items);
    final now = DateTime.now().toUtc();
    final repo = ref.watch(videosRepositoryProvider);
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.only(bottom: 24),
      children: [
        for (final entry in groups.entries) ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
            child: Text(
              DateFormat.MMMMEEEEd(locale).format(entry.key),
              style: theme.textTheme.titleSmall?.copyWith(color: theme.colorScheme.primary),
            ),
          ),
          for (final item in entry.value)
            ListTile(
              leading: SizedBox(
                width: 40,
                child: item.missing || repo == null || item.renderVersion == 0
                    ? const Icon(Icons.smart_display_outlined)
                    : ClipRRect(
                        borderRadius: BorderRadius.circular(6),
                        child: Image.network(
                          repo.thumbUriFor(item.videoId, item.shortId, item.renderVersion).toString(),
                          headers: repo.authHeaders,
                          fit: BoxFit.cover,
                          errorBuilder: (_, _, _) => const Icon(Icons.smart_display_outlined),
                        ),
                      ),
              ),
              title: Text(item.title, maxLines: 2, overflow: TextOverflow.ellipsis),
              subtitle: Text(
                '${DateFormat.Hm(locale).format(item.slotAt.toLocal())} · '
                '${publishStatusText(context.l10n, item, now)}',
                style: TextStyle(color: publishStatusColor(theme.colorScheme, item, now)),
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push('/publish/${item.id}'),
            ),
        ],
      ],
    );
  }
}
