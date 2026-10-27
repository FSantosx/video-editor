import 'package:flutter/widgets.dart';

import '../l10n/app_localizations.dart';
import 'result.dart';

extension L10nX on BuildContext {
  AppLocalizations get l10n => AppLocalizations.of(this);
}

extension FailureL10n on Failure {
  String message(AppLocalizations l10n) {
    final base = switch (kind) {
      FailureKind.network => l10n.errorNetwork,
      FailureKind.unauthorized => l10n.errorUnauthorized,
      FailureKind.notFound => l10n.errorNotFound,
      FailureKind.tooLarge => l10n.errorTooLarge,
      FailureKind.invalid => l10n.errorInvalid,
      FailureKind.server => l10n.errorServer,
      FailureKind.unknown => l10n.errorUnknown,
    };
    return detail == null || kind == FailureKind.network ? base : '$base\n$detail';
  }
}

/// 75.4 -> "1:15"
String formatSeconds(double seconds) {
  final total = seconds.round();
  final m = total ~/ 60;
  final s = (total % 60).toString().padLeft(2, '0');
  return '$m:$s';
}
