/// Resultado de operações de I/O: erro vira valor, nunca exceção solta na UI.
sealed class Result<T> {
  const Result();
}

final class Ok<T> extends Result<T> {
  const Ok(this.value);
  final T value;
}

final class Err<T> extends Result<T> {
  const Err(this.failure);
  final Failure failure;
}

enum FailureKind { network, unauthorized, notFound, tooLarge, invalid, server, unknown }

class Failure {
  const Failure(this.kind, [this.detail]);
  final FailureKind kind;

  /// Mensagem vinda do servidor (ex.: "end precisa ser maior que start").
  final String? detail;

  @override
  String toString() => 'Failure($kind, $detail)';
}
