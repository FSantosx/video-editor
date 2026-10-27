import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/l10n.dart';
import '../../../core/providers.dart';
import '../../../core/result.dart';
import '../../../core/widgets/error_view.dart';
import '../domain/models.dart';
import 'upload_controller.dart';
import 'widgets/status_label.dart';

class VideosListPage extends ConsumerWidget {
  const VideosListPage({super.key});

  Future<void> _pickAndUpload(BuildContext context, WidgetRef ref) async {
    final file = (await FilePicker.pickFiles(type: FileType.video)).singleOrNull;
    if (file?.path == null) return;
    final video = await ref.read(uploadControllerProvider.notifier).upload(file!.path!, file.name);
    if (video != null && context.mounted) context.push('/videos/${video.id}');
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final videos = ref.watch(videosListProvider);
    final upload = ref.watch(uploadControllerProvider);
    final uploading = upload != null && upload.failure == null;

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.appTitle),
        actions: [
          IconButton(
            tooltip: l10n.settingsTitle,
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => context.push('/settings'),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: uploading ? null : () => _pickAndUpload(context, ref),
        icon: const Icon(Icons.video_call_outlined),
        label: Text(l10n.uploadVideo),
      ),
      body: Column(
        children: [
          if (upload != null) _UploadBanner(state: upload),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => ref.refresh(videosListProvider.future),
              child: videos.when(
                data: (list) => list.isEmpty
                    ? _EmptyState(message: l10n.emptyVideos)
                    : ListView.builder(
                        padding: const EdgeInsets.only(bottom: 96),
                        itemCount: list.length,
                        itemBuilder: (context, i) => _VideoTile(video: list[i]),
                      ),
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => ListView(children: [
                  ErrorView(error: e, onRetry: () => ref.invalidate(videosListProvider)),
                ]),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    // ListView para o pull-to-refresh funcionar mesmo vazio
    return ListView(
      padding: const EdgeInsets.all(32),
      children: [
        const SizedBox(height: 80),
        Icon(Icons.movie_filter_outlined, size: 64, color: Theme.of(context).colorScheme.outline),
        const SizedBox(height: 16),
        Text(message, textAlign: TextAlign.center),
      ],
    );
  }
}

class _UploadBanner extends ConsumerWidget {
  const _UploadBanner({required this.state});

  final UploadState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final controller = ref.read(uploadControllerProvider.notifier);
    final failure = state.failure;
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerHigh,
      child: ListTile(
        leading: Icon(failure == null ? Icons.cloud_upload_outlined : Icons.error_outline),
        title: Text(failure == null
            ? l10n.uploading(state.fileName)
            : failure.message(l10n)),
        subtitle: failure == null
            ? Semantics(
                label: l10n.uploadProgress,
                value: '${(state.progress * 100).round()}%',
                child: LinearProgressIndicator(value: state.progress),
              )
            : null,
        trailing: IconButton(
          tooltip: failure == null ? l10n.cancel : l10n.close,
          icon: const Icon(Icons.close),
          onPressed: failure == null ? controller.cancel : controller.dismissError,
        ),
      ),
    );
  }
}

class _VideoTile extends ConsumerWidget {
  const _VideoTile({required this.video});

  final Video video;

  Future<void> _delete(BuildContext context, WidgetRef ref) async {
    final l10n = context.l10n;
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.deleteVideoTitle),
        content: Text(l10n.deleteVideoBody(video.filename)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: Text(l10n.cancel)),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(l10n.delete)),
        ],
      ),
    );
    if (ok != true) return;
    final result = await ref.read(videosRepositoryProvider)!.delete(video.id);
    if (!context.mounted) return;
    if (result case Err(:final failure)) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(failure.message(l10n))));
    }
    ref.invalidate(videosListProvider);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final date = DateFormat.yMd(Localizations.localeOf(context).toString()).add_Hm();
    return ListTile(
      leading: CircleAvatar(
        child: Icon(switch (video.status) {
          VideoStatus.ready => Icons.check,
          VideoStatus.error => Icons.error_outline,
          _ => Icons.hourglass_top,
        }),
      ),
      title: Text(video.filename, maxLines: 1, overflow: TextOverflow.ellipsis),
      subtitle: Text('${date.format(video.createdAt)} · ${videoStatusText(l10n, video)}'),
      onTap: () => context.push('/videos/${video.id}'),
      trailing: IconButton(
        tooltip: l10n.delete,
        icon: const Icon(Icons.delete_outline),
        onPressed: () => _delete(context, ref),
      ),
    );
  }
}
