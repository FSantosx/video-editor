import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/l10n.dart';
import '../../../core/providers.dart';
import '../../../core/result.dart';
import '../../../core/widgets/error_view.dart';
import '../domain/models.dart';
import 'widgets/short_card.dart';
import 'widgets/status_label.dart';

class VideoDetailPage extends ConsumerWidget {
  const VideoDetailPage({super.key, required this.videoId});

  final String videoId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final async = ref.watch(videoDetailProvider(videoId));
    final video = async.value;

    return Scaffold(
      appBar: AppBar(
        title: Text(video?.filename ?? l10n.shortsTitle),
        actions: [
          if (video != null && video.status == VideoStatus.ready)
            IconButton(
              tooltip: l10n.reprocess,
              icon: const Icon(Icons.autorenew),
              onPressed: () => reprocessVideo(context, ref, video.id, confirm: true),
            ),
        ],
      ),
      body: switch (async) {
        AsyncValue(value: final v?) => _Body(video: v),
        AsyncValue(:final error?) => ErrorView(
            error: error,
            onRetry: () => ref.invalidate(videoDetailProvider(videoId)),
          ),
        _ => const Center(child: CircularProgressIndicator()),
      },
    );
  }
}

/// Refaz a seleção e os cortes com a versão atual do servidor (sem transcrever de novo).
Future<void> reprocessVideo(BuildContext context, WidgetRef ref, String videoId,
    {bool confirm = false}) async {
  final l10n = context.l10n;
  if (confirm) {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.reprocessTitle),
        content: Text(l10n.reprocessBody),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: Text(l10n.cancel)),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(l10n.reprocess)),
        ],
      ),
    );
    if (ok != true || !context.mounted) return;
  }
  final result = await ref.read(videosRepositoryProvider)!.reanalyze(videoId);
  if (!context.mounted) return;
  if (result case Err(:final failure)) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(failure.message(l10n))));
  }
  ref.invalidate(videoDetailProvider(videoId)); // volta a acompanhar o progresso
}

class _Body extends ConsumerWidget {
  const _Body({required this.video});

  final Video video;

  Future<void> _reanalyze(BuildContext context, WidgetRef ref) =>
      reprocessVideo(context, ref, video.id);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    if (video.status == VideoStatus.error) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('${l10n.statusError}\n${video.error ?? ''}', textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton.tonal(
                onPressed: () => _reanalyze(context, ref),
                child: Text(l10n.retry),
              ),
            ],
          ),
        ),
      );
    }
    if (video.isAnalyzing) {
      return Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            VideoProgress(video: video),
            const SizedBox(height: 16),
            Text(l10n.analyzingHint, textAlign: TextAlign.center),
          ],
        ),
      );
    }
    if (video.shorts.isEmpty) {
      return Center(child: Text(l10n.noShortsFound));
    }
    final grid = RefreshIndicator(
      onRefresh: () => ref.refresh(videoDetailProvider(video.id).future),
      child: GridView.builder(
        padding: const EdgeInsets.all(12),
        gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
          maxCrossAxisExtent: 220,
          childAspectRatio: 9 / 19,
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
        ),
        itemCount: video.shorts.length,
        itemBuilder: (context, i) {
          final short = video.shorts[i];
          return ShortCard(
            videoId: video.id,
            short: short,
            onTap: () => context.push('/videos/${video.id}/shorts/${short.id}'),
          );
        },
      ),
    );
    if (!video.outdated) return grid;
    return Column(
      children: [
        MaterialBanner(
          leading: const Icon(Icons.new_releases_outlined),
          content: Text(l10n.outdatedBanner),
          actions: [
            FilledButton(
              onPressed: () => reprocessVideo(context, ref, video.id, confirm: true),
              child: Text(l10n.reprocess),
            ),
          ],
        ),
        Expanded(child: grid),
      ],
    );
  }
}
