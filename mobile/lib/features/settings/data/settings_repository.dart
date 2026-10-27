import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../domain/app_settings.dart';

/// URL em SharedPreferences; API key no armazenamento seguro (Keystore no Android).
class SettingsRepository {
  SettingsRepository({FlutterSecureStorage? secure}) : _secure = secure ?? const FlutterSecureStorage();

  static const _urlKey = 'server_url';
  static const _apiKeyKey = 'api_key';

  final FlutterSecureStorage _secure;

  Future<AppSettings> load() async {
    final prefs = await SharedPreferences.getInstance();
    return AppSettings(
      serverUrl: prefs.getString(_urlKey) ?? '',
      apiKey: await _secure.read(key: _apiKeyKey) ?? '',
    );
  }

  Future<void> save(AppSettings settings) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_urlKey, settings.serverUrl);
    await _secure.write(key: _apiKeyKey, value: settings.apiKey);
  }
}
