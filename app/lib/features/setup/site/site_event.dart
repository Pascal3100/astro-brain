import 'package:equatable/equatable.dart';

abstract class SiteEvent extends Equatable {
  const SiteEvent();
  @override
  List<Object?> get props => const [];
}

/// Chargement initial : lit le site persisté côté Pi.
class SiteLoaded extends SiteEvent {
  const SiteLoaded();
}

/// L'utilisateur demande d'écrire le site depuis le GPS du téléphone.
class SiteFromPhoneRequested extends SiteEvent {
  const SiteFromPhoneRequested();
}
