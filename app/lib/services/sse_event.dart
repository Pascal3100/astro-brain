import 'package:equatable/equatable.dart';

class SseEvent extends Equatable {
  const SseEvent({required this.event, required this.data});
  final String event;
  final String data;

  @override
  List<Object> get props => [event, data];
}
