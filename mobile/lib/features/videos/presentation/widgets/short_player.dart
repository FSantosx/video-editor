import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

import '../../../../core/l10n.dart';

/// Player 9:16 do short. Recriar com outra [uri] (nova versão) troca o vídeo.
class ShortPlayer extends StatefulWidget {
  const ShortPlayer({super.key, required this.uri, required this.headers});

  final Uri uri;
  final Map<String, String> headers;

  @override
  State<ShortPlayer> createState() => _ShortPlayerState();
}

class _ShortPlayerState extends State<ShortPlayer> {
  late VideoPlayerController _controller;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _init();
  }

  void _init() {
    _error = null;
    _controller = VideoPlayerController.networkUrl(widget.uri, httpHeaders: widget.headers)
      ..setLooping(true);
    _controller.initialize().then((_) {
      if (mounted) setState(() {});
    }).catchError((Object e) {
      if (mounted) setState(() => _error = e);
    });
  }

  @override
  void didUpdateWidget(ShortPlayer old) {
    super.didUpdateWidget(old);
    if (old.uri != widget.uri) {
      _controller.dispose();
      _init();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _toggle() {
    setState(() {
      _controller.value.isPlaying ? _controller.pause() : _controller.play();
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return AspectRatio(
      aspectRatio: 9 / 16,
      child: ColoredBox(
        color: Colors.black,
        child: _error != null
            ? Center(child: Text(l10n.playerError, style: const TextStyle(color: Colors.white)))
            : !_controller.value.isInitialized
                ? const Center(child: CircularProgressIndicator())
                : Semantics(
                    button: true,
                    label: _controller.value.isPlaying ? l10n.pause : l10n.play,
                    child: GestureDetector(
                      onTap: _toggle,
                      child: Stack(
                        alignment: Alignment.center,
                        children: [
                          VideoPlayer(_controller),
                          ValueListenableBuilder(
                            valueListenable: _controller,
                            builder: (context, value, _) => value.isPlaying
                                ? const SizedBox.shrink()
                                : const Icon(Icons.play_circle_fill, size: 72, color: Colors.white70),
                          ),
                          Positioned(
                            left: 0,
                            right: 0,
                            bottom: 0,
                            child: VideoProgressIndicator(_controller, allowScrubbing: true),
                          ),
                        ],
                      ),
                    ),
                  ),
      ),
    );
  }
}
