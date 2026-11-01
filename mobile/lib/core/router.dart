import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/publish/presentation/agenda_page.dart';
import '../features/publish/presentation/publish_item_page.dart';
import '../features/publish/presentation/publish_settings_page.dart';
import '../features/settings/presentation/settings_page.dart';
import '../features/videos/presentation/short_editor_page.dart';
import '../features/videos/presentation/video_detail_page.dart';
import '../features/videos/presentation/videos_list_page.dart';
import 'providers.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    // Sem servidor configurado, qualquer rota cai nas configurações
    redirect: (context, state) {
      final settings = ref.read(settingsProvider).value;
      final configured = settings?.isConfigured ?? false;
      return !configured && state.matchedLocation != '/settings' ? '/settings' : null;
    },
    routes: [
      GoRoute(path: '/', builder: (_, _) => const VideosListPage()),
      GoRoute(path: '/settings', builder: (_, _) => const SettingsPage()),
      GoRoute(
        path: '/publish',
        builder: (_, _) => const AgendaPage(),
        routes: [
          GoRoute(path: 'settings', builder: (_, _) => const PublishSettingsPage()),
          GoRoute(
            path: ':itemId',
            builder: (_, state) => PublishItemPage(itemId: state.pathParameters['itemId']!),
          ),
        ],
      ),
      GoRoute(
        path: '/videos/:id',
        builder: (_, state) => VideoDetailPage(videoId: state.pathParameters['id']!),
        routes: [
          GoRoute(
            path: 'shorts/:sid',
            builder: (_, state) => ShortEditorPage(
              videoId: state.pathParameters['id']!,
              shortId: int.parse(state.pathParameters['sid']!),
            ),
          ),
        ],
      ),
    ],
  );
});
