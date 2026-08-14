# Feature Specification: NetClaw Mobile 1.0.1 Polish Pass (Phase A + C1)

**Feature Branch**: `109-mobile-polish-pass`
**Created**: 2026-08-14
**Status**: Draft
**Input**: User description: "NetClaw Mobile 1.0.1 polish pass, Phase A + C1 of `mobile/netclaw-mobile/NETCLAW-MOBILE-1.0.1-BRIEF.md` (2026-08-14, written against `main` as of spec 108): dark mode support, haptic feedback on key events, copy/share/select/markdown rendering for chat answers and feed messages, Time Sensitive notifications for approvals, a Face ID app-lock toggle, and search/filter across Chat and Feed. Version bump `pubspec.yaml` `1.0.0+1` → `1.0.1+2`. No new Xcode targets, no new capabilities, no Apple Developer portal work — those are Phase B (App Intents, widgets, Live Activities, Watch gestures, complications), each deferred to its own future numbered spec per the brief's own recommended split."

## Context

This spec implements Phase A (A1–A5) and Phase C item C1 of
`mobile/netclaw-mobile/NETCLAW-MOBILE-1.0.1-BRIEF.md` — a handoff brief written
2026-08-14 against `main` as of the commit containing spec 108
(`cloudflare-tunnel-transport`). That brief itself recommends the split used
here: items A1–A5 and C1 are small enough for one spec (this one); items B1–B5
(App Intents/Siri, home-screen and Lock Screen widgets, interactive/in-flight
Live Activities, Apple Watch Double Tap, the `.accessoryCorner` complication)
each require a new Xcode target, a new capability, or Apple Developer portal
work, and each warrants its own numbered spec — explicitly out of scope here.

Every Evidence claim in the brief for these six items was independently
re-verified by reading the current tree (file and line) before this spec was
written; all of it checked out exactly as documented — no interpretation drift
between the brief and the tests below.

This repo's verification standard (established by specs 072/073) applies
unchanged: "passes the Dart suite" is not the same claim as "verified on real
hardware." Every acceptance scenario and success criterion below is provable by
`flutter analyze` + `flutter test` alone — Phase A and C1 were deliberately
scoped by the brief to avoid anything requiring a physical device or an Xcode
build to prove. If a later implementation touches native (Swift/Kotlin)
platform-channel code for these items, that portion is 🔌 **DEVICE** and must be
called out in the README's platform-notes section rather than marked done from
a green Dart build.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The app looks correct in Dark Mode (Priority: P1)

Today the app defines a single light `ColorScheme` and never sets
`darkTheme`/`themeMode`, so it renders in a light theme even when the device is
set to Dark Appearance — and several screens hardcode `Colors.grey` literals
that would look wrong (or fail contrast) if a dark theme were layered on
without fixing them. This story adds a proper dark scheme from the same brand
seed color, follows the system setting, and sweeps every hardcoded color out of
`lib/screens/`.

**Why this priority**: Equal-highest priority in this spec, per the brief's own
"if only three ship" recommendation. This is the single most visible defect a
new user with system-wide Dark Appearance enabled will notice within seconds of
opening the app, and it is cheap: no new dependency, no new target, no portal
work.

**Independent Test**: Switch the device to Dark Appearance, launch the app, and
visually confirm every screen renders with a dark surface and legible text —
verifiable with no Border, no enrollment, and no other story in this spec in
place.

**Acceptance Scenarios**:

1. **Given** the device is set to Dark Appearance, **When** the app launches,
   **Then** every screen renders using a dark `ColorScheme` derived from the
   same brand seed color used in light mode, not the light scheme.
2. **Given** the device is set to Light Appearance, **When** the app launches,
   **Then** behavior is visually unchanged from today.
3. **Given** the device's appearance setting changes while the app is running,
   **When** the change is applied by the OS, **Then** the app's theme updates
   to match without requiring a restart (`themeMode: ThemeMode.system`).
4. **Given** any screen under `lib/screens/`, **When** its source is inspected,
   **Then** it contains no hardcoded `Colors.grey`, `Colors.black`, or
   `Colors.white` literal — each has been replaced with a theme
   `ColorScheme` role (e.g. `onSurfaceVariant`, `error`).
5. **Given** the app's splash screen configuration, **When** the app is
   launched on a device set to Dark Appearance, **Then** the splash uses a dark
   background/image rather than flashing the light-mode splash before the app
   itself renders.

---

### User Story 2 - Chat answers can be selected, copied, shared, and read as formatted text (Priority: P1)

Chat answers are real network-engineering payloads — CLI output, route tables,
config fragments, sometimes over a thousand characters — but today they render
as a single, non-selectable `Text` widget. There is no way to copy a command's
output, share an answer to another app, or see a returned table/code block
rendered as anything other than an unbroken paragraph. This story makes answer
text selectable, copyable (whole answer, or an individual fenced code block),
shareable, and — when the content actually looks like it, not by default —
rendered as formatted markdown with monospaced code.

**Why this priority**: Equal-highest priority in this spec alongside dark mode,
per the brief's own "if only three ship" recommendation, and independently
flagged in the brief as "the single highest-value micro-feature in this entire
document for a network engineer" (the per-code-block copy button). The same
treatment extends to feed message bodies, which carry the same kind of content.

**Independent Test**: Ask a question that returns a long, multi-line answer
(or, for testing, seed a turn with such an answer directly), then confirm text
can be selected, the whole answer copied in one action, and — if the answer
contains a fenced code block or a pipe-table row — that it renders as
formatted markdown with a monospaced code block and its own copy control.

**Acceptance Scenarios**:

1. **Given** a chat turn with a completed answer, **When** the answer is
   displayed, **Then** its text is selectable (not a plain, non-interactive
   `Text` widget).
2. **Given** a displayed answer, **When** the user triggers the copy action
   (long-press or overflow menu), **Then** the full answer text is placed on
   the clipboard and a confirmation is shown.
3. **Given** a displayed turn, **When** the user triggers "copy question +
   answer," **Then** both are copied together as one block, question first.
4. **Given** a displayed answer, **When** the user triggers the share action,
   **Then** the system share sheet opens with the answer text (and the turn's
   photo attached too, if the turn has one).
5. **Given** an answer whose text contains a fenced code block (for example,
   a Markdown-style triple-backtick block) or a Markdown pipe-table row,
   **When** it is displayed, **Then** it is rendered as formatted Markdown —
   any table renders as a table, and any fenced block renders in a monospaced
   font with its own dedicated copy control.
6. **Given** an answer whose text contains none of those markdown signals —
   e.g. raw CLI output containing bare `#`, `*`, `_`, or `|` characters that
   are not part of a fenced block or a table row — **When** it is displayed,
   **Then** it is rendered as plain monospaced preformatted text, not passed
   through a markdown renderer that could mangle those characters.
7. **Given** the same displayed-answer behavior (selectable, copyable,
   shareable, markdown-aware), **When** applied to a feed message body on the
   Feed screen, **Then** it behaves identically to a chat answer.
8. **Given** a turn with an unusually long answer (on the order of thousands
   of characters), **When** it is scrolled past in the chat list, **Then**
   scroll performance is not visibly degraded compared to a short answer.

---

### User Story 3 - Approval requests reach the operator even in a Focus mode (Priority: P2)

Approval push notifications today arrive at the OS's default interruption
level, which means an active Focus mode (Do Not Disturb, Work, Sleep, etc.)
that would normally permit only Time Sensitive notifications will silently
suppress them — exactly the kind of notification an operator most needs to see
promptly, since it is gating a real network change. This story marks approval
notifications specifically as Time Sensitive (iOS) / heads-up (Android),
while leaving lower-urgency feed and chat-answer notifications at their
current, more passive level.

**Why this priority**: A real correctness gap for the app's highest-stakes
notification type, but scoped narrowly (one file) and does not block on
anything else in this spec.

**Independent Test**: With a Focus mode active on the test device configured
to allow only Time Sensitive notifications, trigger an approval push and
confirm it is shown; trigger a feed/chat-answer push under the same Focus mode
and confirm it is not.

**Acceptance Scenarios**:

1. **Given** an approval notification is about to be shown on iOS, **When**
   it is constructed, **Then** it carries a Time Sensitive interruption level.
2. **Given** a feed or chat-answer notification is about to be shown on iOS,
   **When** it is constructed, **Then** it does NOT carry a Time Sensitive
   interruption level — its current, more passive behavior is unchanged.
3. **Given** an approval notification is about to be shown on Android,
   **When** it is constructed, **Then** its notification channel is configured
   for high importance/priority so it produces a heads-up banner.
4. **Given** a device Focus mode is active that would otherwise suppress
   default-priority notifications, **When** an approval notification fires,
   **Then** it is still shown to the operator (subject to the operator's own
   Focus/notification settings, which this feature cannot override).

---

### User Story 4 - An operator can require Face ID to open the app (Priority: P2)

The app already uses biometric authentication to confirm individual approvals,
but nothing today gates opening the app itself — anyone who picks up an
unlocked phone can see live Border data, chat history, and pending approvals
without any additional check. This story adds an opt-in Settings toggle that,
when enabled, requires Face ID (or device passcode, as a fallback) before the
app's content is shown, both on a cold start and after the app has been
backgrounded longer than a short grace period.

**Why this priority**: A meaningful privacy improvement for anyone whose phone
is shared, borrowed, or simply unlocked and left unattended, but opt-in and
additive — it changes nothing for an operator who leaves the toggle off.

**Independent Test**: Enable the toggle, force-quit and relaunch the app, and
confirm a lock screen appears before any app content; background the app for
longer than the grace period and confirm the same; background it briefly and
confirm no re-prompt.

**Acceptance Scenarios**:

1. **Given** the "Require Face ID to open NetClaw" toggle is off (the
   default), **When** the app is launched or resumed, **Then** behavior is
   completely unchanged from today.
2. **Given** the toggle is on, **When** the app is cold-started, **Then** a
   lock screen is shown and no app content (chat history, pending approvals,
   Border data) is visible until authentication succeeds.
3. **Given** the toggle is on and the app is authenticated and in the
   foreground, **When** the app is backgrounded and resumed within the grace
   period (default 60 seconds), **Then** no re-authentication is required.
4. **Given** the same setup, **When** the app is backgrounded and resumed
   after the grace period has elapsed, **Then** the lock screen is shown
   again before content is exposed.
5. **Given** the lock screen is showing, **When** authentication fails or is
   cancelled, **Then** the lock screen remains and no app content is ever
   exposed.
6. **Given** the device has no biometric enrolled, or biometric hardware is
   unavailable/locked out, **When** the operator attempts to unlock, **Then**
   a device-passcode fallback is offered rather than leaving the operator
   permanently locked out.
7. **Given** an approval notification's own inline confirmation flow (which
   already performs its own fresh biometric check independent of this
   feature), **When** the app-lock screen and that flow could both apply,
   **Then** the operator is never prompted for biometrics twice in immediate
   succession for the same action.

---

### User Story 5 - Key events produce haptic feedback (Priority: P3)

The app currently gives no tactile feedback for any event — an approval
arriving, an approval being resolved, a chat answer completing, enrollment
succeeding, or the Border connection being lost. This story adds distinct,
short haptic feedback for each of those events, on both phone and watch.

**Why this priority**: Pure delight/polish with no correctness stakes,
appropriately lowest priority in this spec — but cheap, additive, and
independently shippable.

**Independent Test**: Trigger each event in turn (receive a mock approval,
resolve it, complete a chat answer, enroll a device, force a disconnect) and
confirm exactly one distinct haptic fires per event, with no repeated buzzing
during a bounded reconnect retry loop.

**Acceptance Scenarios**:

1. **Given** any of the six defined events occurs (approval arrives, approval
   resolved successfully, approval resolve failed, chat answer completes,
   enrollment succeeds, Border connection lost), **When** it occurs, **Then**
   exactly one haptic pattern appropriate to that event fires.
2. **Given** the Border connection is lost and the app's bounded reconnect
   loop begins retrying, **When** subsequent retry attempts also fail,
   **Then** no additional haptic fires for those repeated failures — only the
   initial transition to "disconnected" produces one.
3. **Given** the same six events occur on the paired Apple Watch app,
   **When** each occurs, **Then** an equivalent watch-native haptic fires
   (notification/success/failure/click/retry, as applicable).
4. **Given** a user has disabled haptics system-wide on their device,
   **When** any of these events occurs, **Then** the app does not crash or
   misbehave — no UI state may depend on a haptic actually having been felt.

---

### User Story 6 - Chat history and Feed can be searched and filtered (Priority: P3)

Chat conversation history and Feed messages both accumulate over time with no
way to find a specific past exchange or message except manual scrolling. This
story adds a live, case-insensitive text search to both screens, plus filter
chips for a turn's state (pending/working/completed/failed/cancelled) and its
origin (phone/watch).

**Why this priority**: Genuinely useful once history accumulates, but lowest
urgency of the six — Phase C ("quality") in the brief, versus Phase A's
correctness/first-impression items.

**Independent Test**: With a chat history and feed containing several entries,
type a query that matches a subset, confirm the visible list narrows live and
matches are highlighted; clear the query and confirm the full list returns;
apply a state or origin filter chip and confirm it composes correctly with an
active text query.

**Acceptance Scenarios**:

1. **Given** the Chat screen with existing conversation turns, **When** the
   operator types into a new search field, **Then** the visible list narrows
   live to turns whose question or answer text contains the query
   (case-insensitive substring match), with matches highlighted.
2. **Given** the same search field, **When** the operator clears the query,
   **Then** the full, unfiltered list of turns is shown again.
3. **Given** the Feed screen with existing messages, **When** the operator
   types a query, **Then** the same live-filter/highlight behavior applies to
   message bodies.
4. **Given** an active text query on Chat, **When** the operator also selects
   a state filter chip (e.g. "failed") or an origin filter chip (e.g.
   "watch"), **Then** the visible list reflects both the text query AND the
   selected filter(s) together, not either alone.
5. **Given** a filtered view is showing a subset of turns, **When** the
   operator acknowledges or deletes one of the visible (filtered) turns,
   **Then** the correct underlying turn is acknowledged/deleted — never a
   different item selected by its position in the filtered list.
6. **Given** an active search query or filter selection, **When** the app is
   fully closed and relaunched, **Then** the search/filter state has been
   reset — it does not persist across app launches.
7. **Given** a query that matches nothing, **When** it is entered, **Then**
   the list shows an explicit empty/no-results state rather than looking
   identical to "nothing has loaded yet."

### Edge Cases

- What happens to an in-progress markdown-vs-preformatted rendering decision
  (User Story 2) if an answer is still streaming/updating when first
  displayed? The classification (contains a fenced block or pipe-table row,
  or not) should be re-evaluated whenever the answer text changes, not fixed
  permanently from the first partial version of the text.
- What happens if the operator enables Face ID app-lock (User Story 4) on a
  device that has no biometric hardware at all (not just unenrolled)? The
  passcode fallback must still be offered — the toggle must never be able to
  produce a device that cannot be unlocked by its own owner.
- What happens if a Time Sensitive approval notification (User Story 3)
  arrives while the app-lock screen (User Story 4) is showing? The
  notification itself is unaffected by app-lock — app-lock only gates the
  in-app UI, not OS-level notification delivery.
- What happens when the connection-loss haptic (User Story 5) would fire, but
  the app is currently backgrounded? Firing a haptic for a backgrounded app is
  only meaningful if the OS surfaces it at all; this is not expected to work
  reliably in the background and is not a requirement of this story — the
  requirement is specifically about the foregrounded first-transition case.
- What happens to search/filter state (User Story 6) if the underlying list
  updates (a new turn arrives, an existing one changes state) while a query or
  filter is active? The live view should re-apply the current query/filters to
  the updated data, not freeze on a stale snapshot.
- What happens if dark mode (User Story 1) is active and an
  `assets/illustrations/` image intended for a light background is displayed
  (e.g. an empty-state illustration)? It must remain legible/appropriately
  presented rather than visually disappearing against a dark surface.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The app MUST define both a light and a dark `ColorScheme`
  derived from the same brand seed color, and MUST follow the device's system
  appearance setting rather than always rendering in light mode.
- **FR-002**: No screen MUST render text or UI elements using a fixed
  gray/black/white color that ignores the active theme; every such color MUST
  instead be derived from the active theme's color scheme so it adapts
  correctly between light and dark mode.
- **FR-003**: The app's launch splash screen MUST present a dark-appropriate
  background/image when the device is set to Dark Appearance, rather than
  always showing the light-mode splash.
- **FR-004**: Chat answer text and feed message body text MUST be
  user-selectable, not rendered as non-interactive text.
- **FR-005**: The app MUST provide a copy action for a full answer, a
  combined "question + answer" copy action, and a share action (including any
  attached photo) for chat answers.
- **FR-006**: The app MUST render an answer or message body as formatted
  Markdown (including tables and monospaced fenced code blocks, each with its
  own copy control) ONLY when its text contains a fenced code block or a
  Markdown pipe-table row; all other text MUST be rendered as plain,
  monospaced preformatted text rather than passed through a Markdown renderer.
- **FR-007**: Approval push notifications MUST be marked Time Sensitive on
  iOS and configured for high-importance/heads-up delivery on Android; feed
  and chat-answer notifications MUST remain at their current, more passive
  interruption level.
- **FR-008**: Settings MUST offer a toggle to require Face ID (or device
  passcode fallback) before the app's content is shown, persisted across app
  restarts.
- **FR-009**: When that toggle is enabled, the app MUST show a lock screen
  exposing no app content on cold start, and again after being backgrounded
  longer than a configurable grace period (default 60 seconds) — but MUST NOT
  re-prompt for a resume within that grace period.
- **FR-010**: The app-lock flow (FR-008/FR-009) MUST NOT produce a
  double biometric prompt when combined with the existing per-approval
  biometric confirmation flow.
- **FR-011**: The app MUST produce a distinct, single haptic (or watch-native
  equivalent) for each of: approval arrives, approval resolved successfully,
  approval resolve failed, chat answer completes, enrollment succeeds, and
  the Border connection transitioning to lost — and MUST NOT repeat the
  connection-lost haptic on subsequent retry attempts within the same
  disconnected period.
- **FR-012**: The Chat and Feed screens MUST each provide a live,
  case-insensitive text search over their respective content (question/answer
  text for Chat, message body for Feed), with matching text highlighted.
- **FR-013**: The Chat screen MUST provide filter controls for a turn's state
  (pending/working/completed/failed/cancelled) and its origin (phone/watch),
  composable together with an active text search.
- **FR-014**: Search and filter operations (FR-012/FR-013) MUST filter only
  the displayed view, never the underlying stored list — actions taken on a
  filtered item (e.g. acknowledge, delete) MUST apply to the correct
  underlying item regardless of any active filter.
- **FR-015**: Search and filter state MUST NOT persist across app restarts.
- **FR-016**: `pubspec.yaml`'s version MUST be updated from `1.0.0+1` to
  `1.0.1+2` as part of this work.

### Key Entities

- **ColorScheme (light/dark)**: the app's existing single brand-derived color
  scheme, extended to a matched light/dark pair; no new persisted data.
- **ConversationTurn / feed message (existing entities, no schema change)**:
  already hold the question/answer/message text this spec makes selectable,
  copyable, shareable, and searchable; already carry the `origin` field this
  spec surfaces via a filter chip for the first time.
- **App-lock preference (new)**: a single persisted boolean (Face ID app-lock
  enabled/disabled) plus the app's own volatile "last foregrounded at"
  timestamp used to compute the grace period — not a new server-side or
  cross-device concept, purely local device state.
- **Search/filter state (new, transient)**: the current query string and
  selected filter chips for Chat and Feed respectively; explicitly not
  persisted (FR-015).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with system-wide Dark Appearance enabled sees a fully
  dark-themed app on first launch, with no light-background flash and no
  screen requiring a fix afterward.
- **SC-002**: A user can go from "viewing a long chat answer" to "that answer
  pasted into another app" in two taps or fewer (one to open the action, one
  to trigger copy or share).
- **SC-003**: An approval notification is not silently suppressed by a Focus
  mode configured to allow Time Sensitive notifications, in 100% of observed
  cases during testing.
- **SC-004**: An operator can enable the Face ID app-lock toggle and confirm
  it blocks content on a fresh launch without needing any documentation beyond
  the toggle's own label.
- **SC-005**: Every one of the six defined events (User Story 5) produces
  exactly one haptic per occurrence in testing, with zero repeated haptics
  observed across a multi-attempt reconnect retry sequence.
- **SC-006**: An operator can locate a specific past chat exchange or feed
  message, out of a history of at least 50 entries, in under 10 seconds using
  search and/or filters, without scrolling manually.
- **SC-007**: `flutter analyze` reports zero issues and the full `flutter
  test` suite passes with zero regressions and zero skipped tests once all
  six stories are implemented.

## Assumptions

- This spec's scope is exactly Phase A (A1–A5) and Phase C item C1 of
  `NETCLAW-MOBILE-1.0.1-BRIEF.md`. Phase B items (B1–B5: App Intents/Siri,
  home-screen/Lock Screen widgets, interactive and in-flight Live Activities,
  Apple Watch Double Tap, `.accessoryCorner` complication) are explicitly out
  of scope and will each become their own future numbered spec, per the
  brief's own recommendation.
- The two "pre-flight" stale-fact items in the brief (P1: `Runner.entitlements`
  signing status is ambiguous; P2: the existing App Group is watchOS-only) are
  Phase-B prerequisites, not required to be resolved for this spec, since
  nothing in Phase A or C1 touches entitlements, App Groups, or code signing.
- `flutter_markdown` (or an actively maintained equivalent, decided at
  implementation time) is an acceptable new dependency for User Story 2; no
  existing package in `pubspec.yaml` already provides Markdown rendering.
  Likewise `share_plus` is an acceptable new dependency for the share action.
- "Time Sensitive" delivery (User Story 3) is inherently best-effort — the
  operator's own OS-level Focus/notification settings can still suppress any
  notification regardless of interruption level, and this spec cannot
  override that.
- The existing per-approval biometric confirmation flow
  (`approval_confirmation.dart`) is unchanged by this spec; User Story 4 adds
  a separate, app-level gate that must coexist with it without double-prompting
  (FR-010), not replace or modify it.
- Everything in this spec is verifiable via `flutter analyze` + `flutter
  test` alone, consistent with the brief's own scoping of Phase A/C1 to avoid
  native-platform-only behavior; no item here is expected to require a 🔌
  **DEVICE** tag, though any platform-channel code touched during
  implementation (e.g. watch-side haptics) should still be verified on
  hardware before being called done, per specs 072/073's standing precedent.
