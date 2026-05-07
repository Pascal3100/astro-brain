import 'package:equatable/equatable.dart';

import '../../../models/about.dart';

const _sentinel = Object();

class AboutState extends Equatable {
  const AboutState({
    this.info,
    this.isLoading = false,
    this.errorMessage,
  });

  /// Réponse backend — `null` tant que pas encore chargé.
  final AboutInfo? info;

  /// `true` pendant le `GET /about`.
  final bool isLoading;

  /// Message d'erreur réseau — `null` quand tout va bien.
  final String? errorMessage;

  AboutState copyWith({
    Object? info = _sentinel,
    bool? isLoading,
    Object? errorMessage = _sentinel,
  }) => AboutState(
        info: identical(info, _sentinel) ? this.info : info as AboutInfo?,
        isLoading: isLoading ?? this.isLoading,
        errorMessage: identical(errorMessage, _sentinel)
            ? this.errorMessage
            : errorMessage as String?,
      );

  @override
  List<Object?> get props => [info, isLoading, errorMessage];
}
