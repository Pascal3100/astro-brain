import 'package:equatable/equatable.dart';

enum SplashPhase { contacting, loading, openingStream, success, failure }

class SplashState extends Equatable {
  const SplashState({required this.phase, this.errorMessage});
  const SplashState.initial() : this(phase: SplashPhase.contacting);

  final SplashPhase phase;
  final String? errorMessage;

  SplashState copyWith({SplashPhase? phase, String? errorMessage}) =>
      SplashState(
        phase: phase ?? this.phase,
        errorMessage: errorMessage,
      );

  @override
  List<Object?> get props => [phase, errorMessage];
}
