import 'package:equatable/equatable.dart';

abstract class AboutEvent extends Equatable {
  const AboutEvent();
  @override
  List<Object?> get props => const [];
}

/// Chargement initial : `GET /about`.
class AboutLoaded extends AboutEvent {
  const AboutLoaded();
}

/// Bouton « RAFRAÎCHIR » : re-fetch `GET /about`.
class AboutRefreshRequested extends AboutEvent {
  const AboutRefreshRequested();
}
