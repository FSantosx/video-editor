class AppSettings {
  const AppSettings({required this.serverUrl, required this.apiKey});

  final String serverUrl;
  final String apiKey;

  bool get isConfigured => serverUrl.isNotEmpty;

  /// Aceita "meuapp.up.railway.app" ou com barra no fim e devolve uma URL utilizável.
  static String normalizeUrl(String input) {
    var url = input.trim();
    if (url.isEmpty) return url;
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = 'https://$url';
    }
    while (url.endsWith('/')) {
      url = url.substring(0, url.length - 1);
    }
    return url;
  }

  static bool isValidUrl(String input) {
    final uri = Uri.tryParse(normalizeUrl(input));
    return uri != null && uri.hasScheme && uri.host.isNotEmpty;
  }
}
