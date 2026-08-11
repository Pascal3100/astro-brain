import 'package:equatable/equatable.dart';

enum SplashPhase { contacting, loading, openingStream, success }

class SplashState extends Equatable {
  const SplashState({required this.phase});
  const SplashState.initial() : this(phase: SplashPhase.contacting);

  final SplashPhase phase;

  SplashState copyWith({SplashPhase? phase}) =>
      SplashState(phase: phase ?? this.phase);

  @override
  List<Object?> get props => [phase];
}
