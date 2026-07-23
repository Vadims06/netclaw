import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

import 'ncfed/approval_client.dart';
import 'ncfed/capability_registration.dart';
import 'ncfed/capture_client.dart';
import 'ncfed/conversation_store.dart';
import 'ncfed/device_deep_link.dart';
import 'ncfed/edge_ask_client.dart';
import 'ncfed/edge_client.dart';
import 'ncfed/edge_identity.dart';
import 'ncfed/message_feed.dart';
import 'screens/approvals_screen.dart';
import 'screens/capture_screen.dart';
import 'screens/chat_screen.dart';
import 'screens/device_scan_screen.dart';
import 'screens/enrollment_screen.dart';
import 'screens/feed_screen.dart';
import 'screens/settings_screen.dart';

void main() {
  runApp(const NetClawMobileApp());
}

class NetClawMobileApp extends StatelessWidget {
  const NetClawMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'NetClaw Mobile',
      theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple)),
      home: const EnrollmentGate(),
    );
  }
}

/// Shows the enrollment flow first; once enrolled, hands the connected
/// EdgeClient to the main app shell (Chat + Feed tabs).
class EnrollmentGate extends StatefulWidget {
  const EnrollmentGate({super.key});

  @override
  State<EnrollmentGate> createState() => _EnrollmentGateState();
}

class _EnrollmentGateState extends State<EnrollmentGate> {
  static const _identity = EdgeIdentity();

  @override
  Widget build(BuildContext context) {
    return EnrollmentScreen(
      memberId: 'risk/${DateTime.now().millisecondsSinceEpoch}', // operator picks a real id in a future task
      identity: _identity,
      onEnrolled: (client, payload) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => HomeShell(client: client)),
        );
      },
    );
  }
}

/// Chat + Feed tabs, once enrolled and connected (feature 066/067).
class HomeShell extends StatefulWidget {
  final EdgeClient client;

  const HomeShell({super.key, required this.client});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _tab = 0;
  MessageFeedStore? _feedStore;
  EdgeAskClient? _askClient;
  ConversationStore? _conversationStore;
  ApprovalClient? _approvalClient;
  CapabilityRegistration? _capabilities;
  DeviceDeepLinkListener? _deepLinkListener;

  @override
  void initState() {
    super.initState();
    getApplicationDocumentsDirectory().then((dir) async {
      final feedStore = MessageFeedStore(dir);
      final askClient = EdgeAskClient(widget.client);
      final conversationStore = ConversationStore(dir);
      final approvalClient = ApprovalClient(widget.client);
      final capabilities = CapabilityRegistration(widget.client);
      wireMessageFeed(widget.client, feedStore, onApproval: approvalClient.receiveApproval);
      CaptureClient(
        askClient: askClient,
        capture: (type) => CaptureScreen.capture(context, type),
      ).wire(widget.client);
      await capabilities.register();
      setState(() {
        _feedStore = feedStore;
        _askClient = askClient;
        _conversationStore = conversationStore;
        _approvalClient = approvalClient;
        _capabilities = capabilities;
      });
      // T022: a cold-start-from-link and a foreground-tap both land on
      // ChatScreen with the auto-submitted request visible.
      _deepLinkListener = DeviceDeepLinkListener(
        handler: DeviceDeepLinkHandler(askClient),
        onSubmitted: (taskId, text) async {
          await conversationStore.addPending(taskId, text);
          if (mounted) setState(() => _tab = 0);
        },
      );
      _deepLinkListener!.start();
    });
  }

  @override
  void dispose() {
    _askClient?.dispose();
    _approvalClient?.dispose();
    super.dispose();
  }

  Future<void> _scanDevice() async {
    if (_askClient == null || _conversationStore == null) return;
    await Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => DeviceScanScreen(
        handler: DeviceDeepLinkHandler(_askClient!),
        onSubmitted: (taskId) {
          Navigator.of(context).pop();
        },
      ),
    ));
  }

  static const _titles = ['Chat', 'Feed', 'Approvals', 'Settings'];

  @override
  Widget build(BuildContext context) {
    if (_feedStore == null ||
        _askClient == null ||
        _conversationStore == null ||
        _approvalClient == null ||
        _capabilities == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final pages = [
      ChatScreen(askClient: _askClient!, store: _conversationStore!),
      FeedScreen(store: _feedStore!),
      ApprovalsScreen(approvalClient: _approvalClient!),
      SettingsScreen(capabilities: _capabilities!),
    ];
    return Scaffold(
      appBar: AppBar(
        title: Text(_titles[_tab]),
        actions: [
          IconButton(icon: const Icon(Icons.qr_code_scanner), onPressed: _scanDevice),
        ],
      ),
      body: pages[_tab],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.chat), label: 'Chat'),
          NavigationDestination(icon: Icon(Icons.notifications), label: 'Feed'),
          NavigationDestination(icon: Icon(Icons.verified_user), label: 'Approvals'),
          NavigationDestination(icon: Icon(Icons.settings), label: 'Settings'),
        ],
      ),
    );
  }
}
