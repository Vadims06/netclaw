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

## Step 9 — Making it actually run live (everything Marketplace setup alone doesn't tell you)

Getting the Marketplace app configured correctly (Steps 1–8) is necessary but not sufficient — this
feature was live-verified end-to-end for the first time on 2026-08-20, and almost every step below
was a real, previously-invisible blocker found only by actually running a real meeting. Do these in
order; skipping one produces a confusing failure several steps later, not an error at the point
you'd expect.

### 9.1 — The real RTMS SDK needs Python 3.13, specifically

`zoom-rtms-mcp`'s `requirements.txt` documents this, but it's easy to skip past: the `rtms` PyPI
package ships **only a cp313 wheel**. If your system Python is anything else (3.10, 3.14, whatever),
build a **dedicated venv on 3.13** for this server specifically:

```bash
python3.13 -m venv mcp-servers/zoom-rtms-mcp/.venv
mcp-servers/zoom-rtms-mcp/.venv/bin/pip install -r mcp-servers/zoom-rtms-mcp/requirements.txt
```

Without this, `rtms_listener.py` degrades to a clearly-logged no-op (everything else in the server
still works — webhook, panel, MCP tools — you just never receive live transcript). The log line to
watch for either way: `Zoom RTMS SDK not installed` (degraded) vs. no such line (SDK loaded).

### 9.2 — The RTMS SDK needs its own client credentials, under different env var names

`Client.join()` needs to sign its own connection request, separately from the OAuth credentials your
Marketplace app already has. It reads `ZM_RTMS_CLIENT`/`ZM_RTMS_SECRET` — **not**
`ZOOM_CLIENT_ID`/`ZOOM_CLIENT_SECRET`, even though the values are the same. Set both:

```bash
ZM_RTMS_CLIENT=<same value as ZOOM_CLIENT_ID>
ZM_RTMS_SECRET=<same value as ZOOM_CLIENT_SECRET>
```

Symptom without this: RTMS actually connects (`Successfully joined` in the log), then immediately
fails with `OSError: Client ID cannot be blank` from inside the SDK's own signature generation —
easy to misread as a Marketplace scope problem; it isn't.

You also need to explicitly set a transcript source language — `enable_transcript(True)` alone
leaves it at `TranscriptLanguage.NONE` and (confirmed live) produces zero transcript callbacks even
with Zoom's own Live Captions visibly on-screen:

```python
transcript_params = rtms.TranscriptParams()
transcript_params.src_language = rtms.TranscriptLanguage.ENGLISH
client.set_transcript_params(transcript_params)
```

### 9.3 — RTMS is a paid, metered feature — separate from your Marketplace app entirely

None of the above produces a single transcript callback unless **RTMS Developer Pack** billing is
active on your Zoom account (Zoom Marketplace → Developer Pricing → "Zoom Developer Pack", not
"Zoom Build Platform" — the latter is for Video SDK/AI Scribe and is a different product despite
similar naming). The free 20-credit trial genuinely covers RTMS on the Developer Pack tier; confirm
by watching for `RTMS started for meeting ...` in the log the moment a real meeting begins — if that
line never appears, billing isn't active yet, not a code problem.

### 9.4 — `getMeetingContext()`/`getUserContext()` may be rejected outright

On at least one real Marketplace app (scopes and config otherwise exactly as documented in Steps
1–8), the panel's own calls to `zoomSdk.getMeetingContext()` and `zoomSdk.getUserContext()` both
failed identically, every time, with:

```
Error: No Permission for this API. [code:80004, reason:app_not_support]
```

This blocks everything downstream — without a `meeting_uuid`, the panel can never tell the server
which meeting it's part of, so every subsequent update (thinking/investigating/answered) broadcasts
into an empty room and the panel just sits on "Listening" forever with no visible error anywhere
except the browser console. **Root cause unresolved as of this writing** — candidates are the app's
build type (General App vs. Zoom's legacy "Zoom Apps" flow), App Review/publication status
(similarly to Collaborate Mode below), or a separate manifest/Build-Flow capability declaration
distinct from the OAuth scopes list. If you hit this: `panel.js` already has a working fallback —
it asks `panel_feed.py` directly which meeting is active (`identify_by_active_meeting` /
`identified` over the same WebSocket), since the server already knows the true `meeting_uuid`
authoritatively from the RTMS webhook, independent of the Zoom SDK entirely. Nothing to configure;
this fallback fires automatically whenever the SDK calls fail.

### 9.5 — Zoom's client enforces its own CSP, separate from this server's response header

A second, unrelated console message you may see: `Zoom App: Content Security Policy Violation...
inline violated the style-src-elem directive`. This is Zoom's **own** client-injected CSP layer,
distinct from the `Content-Security-Policy` header `panel_feed.py` sends — it blocks inline
`<style>` tags outright regardless of what your own header says. Use an external stylesheet
(`panel.css`, same-origin, already the case in this repo) rather than an inline `<style>` block.

### 9.6 — pyATS needs the exact right Python interpreter, and a device name that doesn't collide

The gateway spawns `pyats_mcp_server.py` via whatever interpreter its own config specifies — if that
resolves to a different Python than the one you actually installed `pyats[full]`/`genie` into (very
possible on a machine with both a system Python and pyenv/homebrew Python), you'll see:

```
ModuleNotFoundError: No module named 'genie'
```

Use an **absolute path** to the correct interpreter in the MCP server's `command` field rather than
a bare `python3` — don't rely on `PATH` resolution matching between your shell and whatever spawns
the gateway.

Separately: if your testbed already has devices from another lab (e.g. a CML topology) that happen
to also be named `R1`, an agent asked to "check R1" may try **every** device in the testbed,
wasting real minutes on connection timeouts to unreachable ones before ever reaching the real
device you meant. Keep a small, dedicated testbed (this repo's `testbed/testbed-zoom-demo.yaml`) for
demo/Zoom use, with your real device keyed plainly as the name you'll actually say out loud.

### 9.7 — Give the agent turn time, and tell the operator something's happening

A real investigation — recognize → route to Border → agent turn (often several tool-call round
trips) → answer — takes on the order of **1-3 minutes** even with a lean, uncluttered set of
registered tools. Two things follow from this:

- **Don't end the meeting early.** The most common "it didn't work" report during this feature's own
  bring-up was simply ending the test meeting before the answer had time to compute — the
  investigation completes successfully regardless, but the result has nowhere left to be delivered
  (best-effort push, logged as `Could not push investigate_result ... Connection lost`).
- **Push an immediate acknowledgment.** The Border now pushes "Looking into it — this can take a
  minute or two…" the instant a question is accepted, before the real agent turn even starts, so the
  panel never looks idle/broken while the real work happens.

## Demo script

See `specs/118-zoom-meeting-intelligence/quickstart.md` for the full end-to-end walkthrough, including
the safety-boundary checks (a hypothetical remark must never be treated as authorization; a genuine
change request must still be held for approval).

The trigger phrases (`extractor.py`'s `_INVESTIGATE_MARKERS`) are ambient, not wake-word-gated — no
need to say "NetClaw" specifically. "Can you check R1, is the interface status okay?" works; a purely
narrative remark like "we're having a problem with R1" does not (no present-tense first-person
request phrase), and a technology-free "can you check R1?" alone gets marked ambiguous and never
routes — mention a recognized technology term (router/interface/routing/bgp/etc.) alongside the
device name.
