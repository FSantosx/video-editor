import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/l10n.dart';
import '../../../core/providers.dart';
import '../../../core/result.dart';
import '../../../core/widgets/error_view.dart';
import '../../videos/data/short_file.dart';
import '../domain/publish_models.dart';
import 'publish_widgets.dart';

/// Tela de postagem de um item da fila (abre também pelo toque no lembrete).
class PublishItemPage extends ConsumerWidget {
  const PublishItemPage({super.key, required this.itemId});

  final String itemId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final queue = ref.watch(publishQueueProvider);
    final item = queue.value?.where((i) => i.id == itemId).firstOrNull;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.postNow)),
      body: switch ((queue, item)) {
        (_, final i?) => _ItemBody(key: ValueKey('${i.id}-${i.status}-${i.slotAt}'), item: i),
        (AsyncValue(:final error?), _) =>
          ErrorView(error: error, onRetry: () => ref.invalidate(publishQueueProvider)),
        (AsyncValue(hasValue: true), null) => Center(child: Text(l10n.errorNotFound)),
        _ => const Center(child: CircularProgressIndicator()),
      },
    );
  }
}

class _ItemBody extends ConsumerStatefulWidget {
  const _ItemBody({super.key, required this.item});

  final PublishItem item;

  @override
  ConsumerState<_ItemBody> createState() => _ItemBodyState();
}

class _ItemBodyState extends ConsumerState<_ItemBody> {
  late final _title = TextEditingController(text: widget.item.title);
  late final _description = TextEditingController(text: widget.item.description);
  double? _downloading;
  bool _busy = false;

  PublishItem get item => widget.item;

  @override
  void dispose() {
    _title.dispose();
    _description.dispose();
    super.dispose();
  }

  void _snack(String text) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

  Future<void> _copy(String text) async {
    await Clipboard.setData(ClipboardData(text: text));
    if (mounted) _snack(context.l10n.copied);
  }

  /// Aplica uma mudança no servidor e recarrega a fila (e os lembretes).
  Future<bool> _apply(Future<Result<Object?>> Function() call) async {
    setState(() => _busy = true);
    final result = await call();
    if (!mounted) return false;
    setState(() => _busy = false);
    if (result case Err(:final failure)) {
      _snack(failure.message(context.l10n));
      return false;
    }
    ref.invalidate(publishQueueProvider);
    return true;
  }

  Future<void> _post() async {
    final l10n = context.l10n;
    final videos = ref.read(videosRepositoryProvider);
    if (videos == null) return;
    await Clipboard.setData(ClipboardData(text: _title.text.trim()));
    setState(() => _downloading = 0);
    final file = await cachedShortFile(videos, item.videoId, item.shortId, item.renderVersion,
        onProgress: (p) => mounted ? setState(() => _downloading = p) : null);
    if (!mounted) return;
    setState(() => _downloading = null);
    switch (file) {
      case Err(:final failure):
        _snack(failure.message(l10n));
        return;
      case Ok(:final value):
        _snack(l10n.postNowHint);
        await SharePlus.instance.share(ShareParams(
          files: [XFile(value.path, mimeType: 'video/mp4')],
          title: _title.text.trim(),
          text: _description.text.trim(),
        ));
    }
    if (!mounted) return;
    final posted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.postedQuestion),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: Text(l10n.notYet)),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(l10n.postedYes)),
        ],
      ),
    );
    if (posted == true) {
      await _apply(() => ref.read(publishRepositoryProvider)!.update(item.id, status: PublishStatus.posted));
    }
  }

  Future<void> _reschedule() async {
    final local = item.slotAt.toLocal();
    final now = DateTime.now();
    final date = await showDatePicker(
      context: context,
      initialDate: local.isBefore(now) ? now : local,
      firstDate: DateTime(now.year, now.month, now.day),
      lastDate: now.add(const Duration(days: 365)),
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(local));
    if (time == null || !mounted) return;
    final when = DateTime(date.year, date.month, date.day, time.hour, time.minute);
    await _apply(() => ref.read(publishRepositoryProvider)!.update(item.id, slotAt: when));
  }

  Future<void> _remove() async {
    final ok = await _apply(() => ref.read(publishRepositoryProvider)!.remove(item.id));
    if (ok && mounted) context.pop();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final theme = Theme.of(context);
    final videos = ref.watch(videosRepositoryProvider);
    final youtube = ref.watch(publishSettingsProvider).value?.youtube;
    final now = DateTime.now().toUtc();
    final editable = item.isPending && !item.missing;
    final changed = _title.text.trim() != item.title || _description.text.trim() != item.description;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (videos != null && !item.missing && item.renderVersion > 0)
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Image.network(
                  videos.thumbUriFor(item.videoId, item.shortId, item.renderVersion).toString(),
                  headers: videos.authHeaders,
                  width: 96,
                  height: 170,
                  fit: BoxFit.cover,
                  errorBuilder: (_, _, _) => const SizedBox(width: 96, height: 170),
                ),
              ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(formatSlot(context, item.slotAt), style: theme.textTheme.titleLarge),
                  const SizedBox(height: 4),
                  Text(publishStatusText(l10n, item, now),
                      style: TextStyle(color: publishStatusColor(theme.colorScheme, item, now))),
                  if (item.error != null) ...[
                    const SizedBox(height: 4),
                    Text(item.error!, style: TextStyle(color: theme.colorScheme.error)),
                  ],
                  if (item.missing) Text(l10n.missingShort),
                  if (item.hook.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(item.hook, style: theme.textTheme.labelLarge),
                  ],
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 20),
        TextField(
          controller: _title,
          enabled: editable,
          maxLength: 100,
          decoration: InputDecoration(
            labelText: l10n.title,
            border: const OutlineInputBorder(),
            suffixIcon: IconButton(
              tooltip: l10n.copyTitle,
              icon: const Icon(Icons.copy),
              onPressed: () => _copy(_title.text.trim()),
            ),
          ),
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: _description,
          enabled: editable,
          minLines: 3,
          maxLines: 8,
          decoration: InputDecoration(
            labelText: l10n.description,
            border: const OutlineInputBorder(),
            suffixIcon: IconButton(
              tooltip: l10n.copyDescription,
              icon: const Icon(Icons.copy),
              onPressed: () => _copy(_description.text.trim()),
            ),
          ),
          onChanged: (_) => setState(() {}),
        ),
        if (editable && changed)
          Align(
            alignment: Alignment.centerRight,
            child: TextButton(
              onPressed: _busy
                  ? null
                  : () => _apply(() => ref.read(publishRepositoryProvider)!.update(item.id,
                      title: _title.text.trim(), description: _description.text.trim())),
              child: Text(l10n.saveChanges),
            ),
          ),
        const SizedBox(height: 16),
        if (editable) ...[
          FilledButton.icon(
            onPressed: _busy || _downloading != null ? null : _post,
            icon: _downloading != null
                ? SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(
                        value: _downloading! > 0 ? _downloading : null, strokeWidth: 2))
                : const Icon(Icons.ios_share),
            label: Text(l10n.postNow),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              OutlinedButton.icon(
                onPressed: _busy
                    ? null
                    : () => _apply(() => ref
                        .read(publishRepositoryProvider)!
                        .update(item.id, status: PublishStatus.posted)),
                icon: const Icon(Icons.check),
                label: Text(l10n.markPosted),
              ),
              OutlinedButton.icon(
                onPressed: _busy ? null : _reschedule,
                icon: const Icon(Icons.schedule),
                label: Text(l10n.reschedule),
              ),
              OutlinedButton.icon(
                onPressed: _busy
                    ? null
                    : () => _apply(() => ref
                        .read(publishRepositoryProvider)!
                        .update(item.id, status: PublishStatus.skipped)),
                icon: const Icon(Icons.skip_next),
                label: Text(l10n.skip),
              ),
            ],
          ),
          if (youtube != null && youtube.connected && !youtube.autoUpload) ...[
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: _busy
                  ? null
                  : () => _apply(() => ref.read(publishRepositoryProvider)!.upload(item.id)),
              icon: const Icon(Icons.cloud_upload_outlined),
              label: Text(l10n.uploadTest),
            ),
            Text(l10n.uploadTestHint, style: theme.textTheme.bodySmall),
          ],
        ],
        if (item.youtubeUrl != null) ...[
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: () => launchUrl(Uri.parse(item.youtubeUrl!), mode: LaunchMode.externalApplication),
            icon: const Icon(Icons.open_in_new),
            label: Text(l10n.openOnYoutube),
          ),
        ],
        const SizedBox(height: 24),
        if (item.status != PublishStatus.uploading)
          TextButton.icon(
            onPressed: _busy ? null : _remove,
            icon: Icon(Icons.delete_outline, color: theme.colorScheme.error),
            label: Text(l10n.removeFromQueue, style: TextStyle(color: theme.colorScheme.error)),
          ),
      ],
    );
  }
}
