import 'dart:async';

import 'edge_client.dart';

enum TaskState { pending, working, completed, failed, cancelled, unknown }

TaskState _parseTaskState(String? s) {
  switch (s) {
    case 'completed':
      return TaskState.completed;
    case 'failed':
      return TaskState.failed;
    case 'cancelled':
      return TaskState.cancelled;
    case 'working':
      return TaskState.working;
    case 'submitted':
      return TaskState.pending;
    default:
      return TaskState.unknown;
  }
}

class TaskUpdate {
  final String taskId;
  final TaskState state;
  final String? outputText;
  final int? tokensUsed;

  const TaskUpdate({
    required this.taskId,
    required this.state,
    this.outputText,
    this.tokensUsed,
  });

  factory TaskUpdate.fromAskResult(Map<String, dynamic> params) => TaskUpdate(
        taskId: params['task_id'] as String,
        state: _parseTaskState(params['state'] as String?),
        outputText: params['output_text'] as String?,
        tokensUsed: params['tokens_used'] as int?,
      );
}

/// Phone-to-Border command channel (feature 067). Wraps `EdgeClient`'s
/// call()/on() to expose the n2n/edge/ask / ask_result / tasks/status /
/// tasks/cancel wire surface
/// (contracts/edge-ask-command-channel.md).
class EdgeAskClient {
  final EdgeRpcSource client;
  final _updates = StreamController<TaskUpdate>.broadcast();

  EdgeAskClient(this.client) {
    client.on('n2n/edge/ask_result', (params) {
      _updates.add(TaskUpdate.fromAskResult(params));
      return <String, dynamic>{};
    });
  }

  /// Fires once per task whenever the Border pushes a finished answer
  /// (best-effort — a disconnected phone should also poll `status()` on
  /// reconnect for a task it submitted but never heard back on).
  Stream<TaskUpdate> get updates => _updates.stream;

  /// `attachment` (feature 068, US2, research D3): an optional
  /// `{content_type, content}` capture riding the SAME request — `text` may
  /// be empty when the capture stands alone (FR-005).
  Future<String> ask(String text, {Map<String, dynamic>? attachment}) async {
    final result = await client.call('n2n/edge/ask', {
      'text': text,
      'attachment': ?attachment,
    });
    return result['task_id'] as String;
  }

  Future<bool> cancel(String taskId) async {
    final result = await client.call('n2n/tasks/cancel', {'task_id': taskId});
    return result['cancelled'] as bool? ?? false;
  }

  Future<TaskUpdate> status(String taskId) async {
    final result = await client.call('n2n/tasks/status', {'task_id': taskId});
    return TaskUpdate(taskId: taskId, state: _parseTaskState(result['state'] as String?));
  }

  void dispose() {
    _updates.close();
  }
}
