import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gal/gal.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/l10n.dart';
import '../../../core/providers.dart';
import '../../../core/result.dart';
import '../../../core/widgets/error_view.dart';
import '../domain/models.dart';
import '../domain/short_draft.dart';
import 'widgets/short_player.dart';
import 'widgets/status_label.dart';

class ShortEditorPage extends ConsumerWidget {
  const ShortEditorPage({super.key, required this.videoId, required this.shortId});

  final String videoId;
  final int shortId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(videoDetailProvider(videoId));
    final video = async.value;
    final short = video?.shorts.where((s) => s.id == shortId).firstOrNull;

    return Scaffold(
      appBar: AppBar(
        title: Text(short?.title ?? context.l10n.editShort, maxLines: 1, overflow: TextOverflow.ellipsis),
        actions: [if (short != null && short.render.hasFile) _ExportMenu(videoId: videoId, short: short)],
      ),
      body: switch ((video, short, async.error)) {
        (final v?, final s?, _) => _Editor(key: ValueKey(s.render.version), video: v, short: s),
        (_, _, final e?) => ErrorView(error: e, onRetry: () => ref.invalidate(videoDetailProvider(videoId))),
        (_?, null, _) => ErrorView(error: const FailureException(Failure(FailureKind.notFound))),
        _ => const Center(child: CircularProgressIndicator()),
      },
    );
  }
}

/// Recriado (key = versão do render) quando um render novo termina: o rascunho
/// volta a refletir o que está no servidor.
class _Editor extends ConsumerStatefulWidget {
  const _Editor({super.key, required this.video, required this.short});

  final Video video;
  final Short short;

  @override
  ConsumerState<_Editor> createState() => _EditorState();
}

class _EditorState extends ConsumerState<_Editor> {
  late ShortDraft _draft = ShortDraft.fromShort(widget.short);
  late final _title = TextEditingController(text: widget.short.title);
  late final _ctaText = TextEditingController(text: widget.short.ctaText);
  bool _saving = false;

  @override
  void dispose() {
    _title.dispose();
    _ctaText.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final l10n = context.l10n;
    final messenger = ScaffoldMessenger.of(context);
    final patch = _draft.copyWith(title: _title.text, ctaText: _ctaText.text).diff(widget.short);
    if (patch.isEmpty) return;
    setState(() => _saving = true);
    final result = await ref.read(videosRepositoryProvider)!.patchShort(widget.video.id, widget.short.id, patch);
    if (!mounted) return;
    setState(() => _saving = false);
    switch (result) {
      case Ok():
        messenger.showSnackBar(SnackBar(content: Text(l10n.savedRerendering)));
        ref.invalidate(videoDetailProvider(widget.video.id)); // volta a acompanhar o render
      case Err(:final failure):
        messenger.showSnackBar(SnackBar(content: Text(failure.message(l10n))));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final theme = Theme.of(context);
    final short = widget.short;
    final repo = ref.watch(videosRepositoryProvider)!;
    final meta = widget.video.meta;
    final bounds = windowBounds(short, meta?.duration ?? short.windowEnd);
    final hasChanges = !_draft.copyWith(title: _title.text, ctaText: _ctaText.text).diff(short).isEmpty;
    final busy = short.render.isWorking;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 480),
            child: short.render.hasFile
                ? ShortPlayer(uri: repo.videoUri(widget.video.id, short), headers: repo.authHeaders)
                : const AspectRatio(aspectRatio: 9 / 16, child: ColoredBox(color: Colors.black)),
          ),
        ),
        const SizedBox(height: 8),
        if (busy || short.render.status == RenderStatus.error)
          Text(
            short.render.status == RenderStatus.error
                ? '${l10n.renderError}: ${short.render.error ?? ''}'
                : renderStatusText(l10n, short.render),
            textAlign: TextAlign.center,
            style: TextStyle(color: short.render.status == RenderStatus.error ? theme.colorScheme.error : null),
          ),
        if (busy) LinearProgressIndicator(value: short.render.progress > 0 ? short.render.progress : null),
        const SizedBox(height: 16),
        TextField(
          controller: _title,
          maxLength: 120,
          decoration: InputDecoration(labelText: l10n.title, border: const OutlineInputBorder()),
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 8),
        Text(l10n.trimLabel(formatSeconds(_draft.start), formatSeconds(_draft.end)),
            style: theme.textTheme.titleSmall),
        RangeSlider(
          min: bounds.min,
          max: bounds.max,
          values: RangeValues(
            _draft.start.clamp(bounds.min, bounds.max),
            _draft.end.clamp(bounds.min, bounds.max),
          ),
          labels: RangeLabels(formatSeconds(_draft.start), formatSeconds(_draft.end)),
          onChanged: (v) {
            if (v.end - v.start < 5) return; // trecho mínimo
            setState(() => _draft = _draft.copyWith(start: v.start, end: v.end));
          },
        ),
        Text(l10n.trimHint, style: theme.textTheme.bodySmall),
        const SizedBox(height: 8),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(l10n.captions),
          value: _draft.captions,
          onChanged: (v) => setState(() => _draft = _draft.copyWith(captions: v)),
        ),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(l10n.titleOverlay),
          value: _draft.titleOverlay,
          onChanged: (v) => setState(() => _draft = _draft.copyWith(titleOverlay: v)),
        ),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(l10n.cta),
          subtitle: Text(l10n.ctaHint),
          value: _draft.cta,
          onChanged: (v) => setState(() => _draft = _draft.copyWith(cta: v)),
        ),
        if (_draft.cta)
          TextField(
            controller: _ctaText,
            maxLength: 80,
            decoration: InputDecoration(labelText: l10n.ctaText, border: const OutlineInputBorder()),
            onChanged: (_) => setState(() {}),
          ),
        if (meta?.isHorizontal ?? false) ...[
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(l10n.autoReframe),
            subtitle: Text(l10n.autoReframeHint),
            value: _draft.autoReframe,
            onChanged: (v) => setState(() => _draft = _draft.copyWith(autoReframe: v)),
          ),
          if (!_draft.autoReframe)
            Row(
              children: [
                Text(l10n.left),
                Expanded(
                  child: Slider(
                    value: _draft.cropCenter,
                    label: l10n.cropPosition,
                    semanticFormatterCallback: (v) => '${(v * 100).round()}%',
                    onChanged: (v) => setState(() => _draft = _draft.copyWith(cropCenter: v)),
                  ),
                ),
                Text(l10n.right),
              ],
            ),
        ],
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: hasChanges && !_saving ? _save : null,
          icon: _saving
              ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.movie_edit),
          label: Text(l10n.saveAndRender),
        ),
        const SizedBox(height: 24),
        Text(l10n.transcript, style: theme.textTheme.titleSmall),
        const SizedBox(height: 4),
        Text(short.text, style: theme.textTheme.bodySmall),
      ],
    );
  }
}

class _ExportMenu extends ConsumerStatefulWidget {
  const _ExportMenu({required this.videoId, required this.short});

  final String videoId;
  final Short short;

  @override
  ConsumerState<_ExportMenu> createState() => _ExportMenuState();
}

class _ExportMenuState extends ConsumerState<_ExportMenu> {
  double? _progress;

  /// Baixa o MP4 para o cache do app (reaproveita se a mesma versão já foi baixada).
  Future<File?> _download() async {
    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/short_${widget.videoId}_${widget.short.id}_v${widget.short.render.version}.mp4');
    if (await file.exists()) return file;
    setState(() => _progress = 0);
    final result = await ref.read(videosRepositoryProvider)!.download(
          widget.videoId,
          widget.short.id,
          file.path,
          onProgress: (p) => mounted ? setState(() => _progress = p) : null,
        );
    if (mounted) setState(() => _progress = null);
    if (result case Err(:final failure)) {
      if (mounted) _snack(failure.message(context.l10n));
      return null;
    }
    return file;
  }

  void _snack(String text) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

  Future<void> _share() async {
    final file = await _download();
    if (file == null) return;
    await SharePlus.instance.share(ShareParams(files: [XFile(file.path, mimeType: 'video/mp4')], title: widget.short.title));
  }

  Future<void> _saveToGallery() async {
    final l10n = context.l10n;
    if (!await Gal.hasAccess() && !await Gal.requestAccess()) {
      if (mounted) _snack(l10n.galleryPermissionDenied);
      return;
    }
    final file = await _download();
    if (file == null) return;
    try {
      await Gal.putVideo(file.path);
      if (mounted) _snack(l10n.savedToGallery);
    } on GalException catch (e) {
      if (mounted) _snack('${l10n.errorUnknown} (${e.type.message})');
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    if (_progress != null) {
      return Padding(
        padding: const EdgeInsets.all(14),
        child: SizedBox.square(
          dimension: 24,
          child: CircularProgressIndicator(value: _progress! > 0 ? _progress : null, strokeWidth: 3),
        ),
      );
    }
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton(tooltip: l10n.saveToGallery, icon: const Icon(Icons.download), onPressed: _saveToGallery),
        IconButton(tooltip: l10n.share, icon: const Icon(Icons.share), onPressed: _share),
      ],
    );
  }
}
