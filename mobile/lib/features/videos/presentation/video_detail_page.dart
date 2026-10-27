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
      appBar: AppBar(title: Text(video?.filename ?? l10n.shortsTitle)),
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

class _Body extends ConsumerWidget {
  const _Body({required this.video});

  final Video video;

  Future<void> _reanalyze(BuildContext context, WidgetRef ref) async {
    final result = await ref.read(videosRepositoryProvider)!.reanalyze(video.id);
    if (!context.mounted) return;
    if (result case Err(:final failure)) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(failure.message(context.l10n))));
    }
    ref.invalidate(videoDetailProvider(video.id)); // volta a acompanhar o progresso
  }

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
    return RefreshIndicator(
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
  }
}
