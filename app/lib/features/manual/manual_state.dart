import 'package:equatable/equatable.dart';

class ManualState extends Equatable {
  const ManualState({this.rate = 5, this.lastError});
  final int rate;
  final String? lastError;

  ManualState copyWith({int? rate, String? lastError, bool clearError = false}) =>
      ManualState(
        rate: rate ?? this.rate,
        lastError: clearError ? null : (lastError ?? this.lastError),
      );

  @override
  List<Object?> get props => [rate, lastError];
}
