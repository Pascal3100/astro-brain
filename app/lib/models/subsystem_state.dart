import 'package:equatable/equatable.dart';

/// Un sous-système porté par le backend : [state] (enum typé côté appelant),
/// [details] libres, [since] horodatage du dernier changement, [message]
/// optionnel pour erreurs ou infos humaines.
class SubsystemState<T> extends Equatable {
  const SubsystemState({
    required this.state,
    required this.details,
    required this.since,
    this.message,
  });

  final T state;
  final Map<String, dynamic> details;
  final DateTime since;
  final String? message;

  factory SubsystemState.fromJson(
    Map<String, dynamic> json,
    T Function(String) stateParser,
  ) {
    return SubsystemState<T>(
      state: stateParser(json['state'] as String),
      details: Map<String, dynamic>.from(
          (json['details'] as Map?) ?? const <String, dynamic>{}),
      since: DateTime.parse(json['since'] as String),
      message: json['message'] as String?,
    );
  }

  @override
  List<Object?> get props => [state, details, since, message];
}
