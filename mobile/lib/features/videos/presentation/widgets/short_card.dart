import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/l10n.dart';
import '../../../../core/providers.dart';
import '../../domain/models.dart';
import 'status_label.dart';

class ShortCard extends ConsumerWidget {
  const ShortCard({super.key, required this.videoId, required this.short, required this.onTap});

  final String videoId;
  final Short short;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final repo = ref.watch(videosRepositoryProvider);
    final theme = Theme.of(context);
    final render = short.render;

    return Semantics(
      button: true,
      label: '${short.title}, ${formatSeconds(short.duration)}, ${renderStatusText(l10n, render)}',
      excludeSemantics: true,
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    if (repo != null && render.hasFile)
                      Image.network(
                        repo.thumbUri(videoId, short).toString(),
                        headers: repo.authHeaders,
                        fit: BoxFit.cover,
                        errorBuilder: (_, _, _) => const _Placeholder(),
                      )
                    else
                      const _Placeholder(),
                    if (render.isWorking)
                      ColoredBox(
                        color: Colors.black45,
                        child: Center(
                          child: CircularProgressIndicator(
                            value: render.progress > 0 ? render.progress : null,
                          ),
                        ),
                      ),
                    Positioned(
                      left: 6,
                      top: 6,
                      child: _Badge(text: '${short.score}', icon: Icons.local_fire_department),
                    ),
                    Positioned(
                      right: 6,
                      bottom: 6,
                      child: _Badge(text: formatSeconds(short.duration)),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(short.title,
                        maxLines: 2, overflow: TextOverflow.ellipsis, style: theme.textTheme.titleSmall),
                    const SizedBox(height: 2),
                    Text(
                      renderStatusText(l10n, render),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: render.status == RenderStatus.error ? theme.colorScheme.error : null,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Placeholder extends StatelessWidget {
  const _Placeholder();

  @override
  Widget build(BuildContext context) => ColoredBox(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        child: const Icon(Icons.smart_display_outlined, size: 40),
      );
}

class _Badge extends StatelessWidget {
  const _Badge({required this.text, this.icon});

  final String text;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(6)),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) Icon(icon, size: 14, color: Colors.orangeAccent),
            Text(text, style: const TextStyle(color: Colors.white, fontSize: 12)),
          ],
        ),
      ),
    );
  }
}
