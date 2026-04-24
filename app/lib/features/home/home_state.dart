import 'package:equatable/equatable.dart';

class HomeState extends Equatable {
  const HomeState({this.rate = 5, this.lastError});
  final int rate;
  final String? lastError;

  HomeState copyWith({int? rate, String? lastError, bool clearError = false}) =>
      HomeState(
        rate: rate ?? this.rate,
        lastError: clearError ? null : (lastError ?? this.lastError),
      );

  @override
  List<Object?> get props => [rate, lastError];
}
