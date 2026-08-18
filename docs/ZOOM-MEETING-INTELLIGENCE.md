# NetClaw for Zoom — Meeting Intelligence

Operator setup guide for [spec 118](../specs/118-zoom-meeting-intelligence/spec.md). Written for both
the operator standing this up for the first time and anyone else doing it fresh — every gotcha below
was hit live during this feature's own Marketplace setup session, not theorized in advance.

## What this is

NetClaw gains a new sensory/human-interface surface: Zoom meetings. Built on Realtime Media Streams
(RTMS), **not** a Meeting SDK bot — Zoom reserves Meeting SDK for human participants and directs AI
applications to RTMS instead. `zoom-rtms-mcp` listens to a meeting's transcript/chat/active-speaker/
screen-share signals, recognizes network-investigation questions with a deterministic extractor, and
routes them into NetClaw's existing Border/NCFED investigation path. Results and live status appear
in a NetClaw Zoom App side panel, visible to every participant (including unauthenticated guests via
Guest Mode), with an optional avatar overlay on a consenting participant's own camera feed.

See `specs/118-zoom-meeting-intelligence/` for the full spec/plan/research/data-model/contracts.

## Cost reality check before you start

**RTMS is not free.** It requires Zoom's paid Developer Pack (metered per streaming minute — one
data point found: ~$0.01/meeting-streaming-minute for video-only; audio+transcript likely costs
more). A Basic/free Zoom account never fires the `meeting.rtms_started` webhook even with correct
configuration. Budget for this like any other metered API before deciding on usage patterns.

The Zoom App framework itself (side panel, Collaborate Mode, Guest Mode) does **not** carry this
cost — only RTMS usage is metered.

## Step 1 — Zoom Marketplace app registration

1. Create a **General App, User-managed, Client secret** auth (not Admin-managed — this is for your
   own account's meetings, not org-wide distribution).
2. Note the **Client ID** and **Client Secret** — these become `ZOOM_CLIENT_ID`/`ZOOM_CLIENT_SECRET`.
   Treat both as real secrets: never paste them into a chat session or commit them; if either was
   ever pasted somewhere it could be logged, regenerate it.
3. **OAuth Redirect URL**: needs a real, reachable HTTPS URL — see "Reachability" below before
   filling this in for real. A placeholder is fine to get through the form initially.

## Step 2 — Scopes (the part that's easy to get wrong)

Zoom's scope search is not always in sync with what a given account/app is actually entitled to. The
**confirmed-correct, minimum scope set** for this feature (verified live against a real Marketplace
app):

| Scope | Why |
|---|---|
| `meeting:read:meeting` | Basic meeting metadata (UUID, topic, participants) |
| `meeting:read:meeting_transcript` | Live transcript content via RTMS |
| `meeting:read:meeting_chat` | Live in-meeting chat text via RTMS |
| `rtms:read:rtms_started` | Notified when a meeting's RTMS stream begins |
| `rtms:read:rtms_stopped` | Notified when a meeting's RTMS stream ends |
| `user:read:user` | Identify which participant asked/is viewing |
| `zoomapp:inmeeting` | Run the side panel inside the meeting client |
| `meeting:write:open_app` | Auto-open the panel when listening is enabled |

**Deliberately excluded** (least privilege — this feature never processes raw audio/video/screen
content, only transcript/chat text): `meeting:read:meeting_audio`, `meeting:read:meeting_video`,
`meeting:read:meeting_screenshare`, and every `webinar:*` scope / `zoomapp:inwebinar` (out of scope —
Meetings only, no Webinars).

**The scope name to watch for**: the intuitive-sounding `meeting:rtms:read` is **not a valid scope
name** — Zoom's own validator rejects it. The correct names are the two `rtms:read:rtms_*` scopes
above. If a scope search comes back empty for "rtms", that's a real signal the account/app doesn't
have RTMS backend-enabled yet (Developer Pack, above) — not a search bug.

Each scope needs a "Scope description" (data-usage justification for Zoom's review) — this field is
**not** settable via manifest upload (confirmed: uploading a manifest with a guessed `description` key
per scope neither errored nor populated the field). Fill it in by hand, once, in the Marketplace UI.

## Step 3 — General Features

- **Event Subscription**: enabled, with the RTMS webhook URL (see Reachability) and event types
  `meeting.rtms_started`/`meeting.rtms_stopped`. The **Secret Token** shown here becomes
  `ZOOM_RTMS_WEBHOOK_SECRET` — it verifies Zoom's webhook signature.
- **Plugin SDK**: leave disabled. That's a separate, heavier native-integration feature (deep hooks
  into the Zoom Workplace desktop app) that nothing in this feature needs — everything here runs
  through the ordinary Zoom Apps SDK (in-meeting web panel).
- **"Allow auto-start for RTMS apps"**: this toggle stays grayed out until the two `rtms:read:rtms_*`
  scopes (Step 2) are actually added and saved — it's not a separate account-tier gate, just a
  scope-dependency in the UI. Enable it once available; this is what makes listening start
  automatically when the operator joins/hosts a meeting (FR-001), rather than needing a manual step.

## Step 4 — Surface

- **Home URL**: point at your reachable HTTPS endpoint (see Reachability), path `/panel/`.
- **Product selection**: **Meetings only.** Leave Webinars/Rooms/Phone/Chat/Contact Center/
  Whiteboard/Virtual Agent/Events/Mail/Workflows unchecked.
- **Guest Mode**: enable (including "enable test guest mode") — FR-012, unauthenticated viewers.
- **Collaborate Mode**: enable — requires submitting the app for Zoom's review before it works for
  real participants (not just your own testing). Budget review time into your timeline.
- **In-Client OAuth**: skip — adds a second auth flow this feature doesn't need.
- **Chat Subscription / Chat tabs / App Shortcuts**: skip — Team Chat bot features, unrelated.
- **Mobile**: optional, harmless to enable — widens where the panel is viewable.
- **Zoom Rooms / PWA Client**: skip.
- **Embed** (Meeting SDK / Contact Center SDK / Phone SDK): **leave all off.** Meeting SDK in
  particular is exactly the restricted bot-participant path this whole feature is built to avoid —
  enabling it here would work against the design, not support it.

## Step 5 — Connect (skip entirely)

The "Connect" page (API spec/Base URL/Auth Endpoints, Incoming Webhooks-as-endpoint-table, MCP) is
part of Zoom's AI-Companion/agent-tool-calling framework — it's for exposing *your* API as something
Zoom's own AI can call, the reverse of what this feature does. None of it applies. Don't add any
endpoints here; the real RTMS webhook lives in Step 3's Event Subscription, a different mechanism
entirely despite the similar name.

## Step 6 — Actions and Triggers (skip entirely)

Same family as Connect — Zoom-AI-Companion-facing automation, not used by this feature.

## Step 7 — Customer Form (skip)

Only relevant for published Marketplace apps installed by other orgs. A User-managed app for your own
account has no installer to show a form to.

## Reachability: getting a real HTTPS endpoint

Zoom's "Add app" test and its webhook delivery both require your Redirect/Home/Webhook URLs to
actually resolve over HTTPS with valid TLS and the OWASP security headers
(`Strict-Transport-Security`, `Content-Security-Policy`) present on every response. A bare ngrok
placeholder or an unrelated domain (e.g. your existing marketing site) will fail this — Zoom's "Add
app" flow does a live reachability check and fails with a generic `400` if nothing answers.

Two paths, not mutually exclusive:

1. **Fast, for testing today**: run a minimal local stub server (headers present, handles the
   `endpoint.url_validation` handshake) and tunnel it with `ngrok http <port>` — swap the resulting
   `https://xxxx.ngrok-free.app` URL into every field above. Free-tier ngrok URLs are ephemeral (a new
   one on every restart) — fine for testing, not for production.
2. **Stable, for production**: point a subdomain you own at wherever `zoom-rtms-mcp`'s actual webhook/
   panel server runs (`ZOOM_RTMS_WEBHOOK_PORT`/`ZOOM_PANEL_FEED_PORT`, default 8899/8900). This
   feature's own reference deployment uses a GoDaddy-managed DNS record kept fresh by a systemd
   timer (mirroring the existing `netclaw-ddns` pattern for the NCFED edge domain) — reuse whatever
   dynamic-DNS mechanism you already have for other NetClaw services if you have one, rather than
   inventing a second one. Either way, whatever serves that URL must itself emit the two required
   security headers — `zoom-rtms-mcp`'s webhook/panel servers do this already.

## Step 8 — Environment variables

See `.env.example`'s "NetClaw for Zoom" block for the complete list
(`ZOOM_CLIENT_ID`/`ZOOM_CLIENT_SECRET`/`ZOOM_ACCOUNT_ID`/`ZOOM_RTMS_WEBHOOK_SECRET`/
`N2N_ZOOM_CHANNEL_PORT`/`N2N_ZOOM_CHANNEL_SECRET`/etc.). `N2N_ZOOM_CHANNEL_PORT` and
`N2N_ZOOM_CHANNEL_SECRET` must match between `zoom-rtms-mcp`'s environment and the Border federation
daemon's (`bgp-daemon-v2.py`) environment — they're the two ends of the same loopback-only channel
(`bgp/federation/zoom_channel.py`).

## Known gaps in this environment (be aware, not alarmed)

- **Zoom's official RTMS Python SDK** isn't bundled — install it per Zoom's own distribution
  instructions. Everything else in `zoom-rtms-mcp` (webhook, extractor, panel feed, MCP tools) works
  without it; only the actual live-meeting media connection needs it.
- **Official Zoom Meetings MCP** (historical correlation, User Story 2): exact tool name/credential
  shape is still being confirmed against Zoom's connector setup flow.
- **Layers API "Camera mode"** (the optional camera-overlay avatar, User Story 5) requires Zoom's own
  Controller-mode entitlement and app review — implemented, but gate your rollout on that approval
  landing; the rest of the feature (Stories 1–4) works without it.

## Demo script

See `specs/118-zoom-meeting-intelligence/quickstart.md` for the full end-to-end walkthrough, including
the safety-boundary checks (a hypothetical remark must never be treated as authorization; a genuine
change request must still be held for approval).
