import 'package:equatable/equatable.dart';

enum SplashPhase { contacting, loading, openingStream, success, failure }

class SplashState extends Equatable {
  const SplashState({
    required this.phase,
    this.errorMessage,
    this.failedPhase,
  });
  const SplashState.initial() : this(phase: SplashPhase.contacting);

  final SplashPhase phase;
  final String? errorMessage;

  /// Phase où l'échec s'est produit (null hors phase `failure`). Permet à l'UI
  /// de distinguer les étapes réellement franchies de celle qui a échoué et de
  /// celles jamais atteintes — sans ça, `failure` (dernier index de l'enum)
  /// ferait paraître toutes les étapes « faites ».
  final SplashPhase? failedPhase;

  SplashState copyWith({
    SplashPhase? phase,
    String? errorMessage,
    SplashPhase? failedPhase,
  }) =>
      SplashState(
        phase: phase ?? this.phase,
        errorMessage: errorMessage,
        failedPhase: failedPhase,
      );

  @override
  List<Object?> get props => [phase, errorMessage, failedPhase];
}
