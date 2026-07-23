import 'dart:convert';

import 'package:flutter/material.dart';

import '../ncfed/message_feed.dart';

/// Renders messages the Border has explicitly pushed (US2/T026), in
/// chronological order. `voice` playback is out of scope here (shown as a
/// placeholder chip) — a dedicated audio player is a follow-up, not part of
/// this feature's minimum feed rendering requirement.
class FeedScreen extends StatefulWidget {
  final MessageFeedStore store;

  const FeedScreen({super.key, required this.store});

  @override
  State<FeedScreen> createState() => _FeedScreenState();
}

class _FeedScreenState extends State<FeedScreen> {
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    widget.store.load().then((_) {
      if (mounted) setState(() => _loading = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    final messages = List.of(widget.store.messages)
      ..sort((a, b) => a.pushedAt.compareTo(b.pushedAt));
    if (messages.isEmpty) {
      return const Center(child: Text('No messages from the Border yet.'));
    }
    return ListView.builder(
      itemCount: messages.length,
      itemBuilder: (context, index) => _MessageTile(message: messages[index]),
    );
  }
}

class _MessageTile extends StatelessWidget {
  final EdgeMessage message;

  const _MessageTile({required this.message});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${message.designatedBy} · ${message.pushedAt.toLocal()}',
              style: Theme.of(context).textTheme.labelSmall,
            ),
            const SizedBox(height: 8),
            _content(context),
          ],
        ),
      ),
    );
  }

  Widget _content(BuildContext context) {
    switch (message.contentType) {
      case MessageContentType.text:
        return Text(message.content);
      case MessageContentType.image:
        try {
          return Image.memory(base64Decode(message.content));
        } catch (_) {
          return const Text('[image could not be decoded]');
        }
      case MessageContentType.voice:
        return const Chip(
          avatar: Icon(Icons.mic, size: 18),
          label: Text('Voice message'),
        );
    }
  }
}
