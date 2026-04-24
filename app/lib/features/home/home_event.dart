import 'package:equatable/equatable.dart';

import '../../services/api_service.dart';

sealed class HomeEvent extends Equatable {
  const HomeEvent();
  @override
  List<Object?> get props => const [];
}

class HomeRateChanged extends HomeEvent {
  const HomeRateChanged(this.rate);
  final int rate;
  @override
  List<Object> get props => [rate];
}

class HomeSlewPressed extends HomeEvent {
  const HomeSlewPressed({required this.axis, required this.direction});
  final Axis axis;
  final Direction direction;
  @override
  List<Object> get props => [axis, direction];
}

class HomeSlewReleased extends HomeEvent {
  const HomeSlewReleased(this.axis);
  final Axis axis;
  @override
  List<Object> get props => [axis];
}

class HomeTrackingToggled extends HomeEvent {
  const HomeTrackingToggled(this.enabled);
  final bool enabled;
  @override
  List<Object> get props => [enabled];
}
