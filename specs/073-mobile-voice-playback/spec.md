# Feature Specification: On-Device Voice Playback of Messages (Android + iOS)

**Feature Branch**: `073-mobile-voice-playback`
**Created**: 2026-07-29
**Status**: Draft
**Input**: User description: "working VOICE PLAYBACK to messages on android — where on the device it uses local TTS and plays back the message"

## Context: what exists today

NetClaw Mobile can already **listen** but cannot **speak**. Verified against the tree at time of writing:

- `pubspec.yaml` declares `speech_to_text: ^7.4.0` and **no** text-to-speech or audio-playback package (`flutter_tts`, `just_audio`, `audioplayers` all absent).
- An exhaustive sweep of `lib/`, `test/`, `android/`, `ios/` for `flutter_tts|FlutterTts|TextToSpeech|speak(|AudioPlayer` returns **zero** hits.
- `lib/ncfed/voice_transcription.dart` (feature 067, extended by in-flight work on `main`) is input-only: microphone → text → `edge_ask_client`.

So the voice loop is currently half-open: the operator can speak a request, but the answer is text-only and must be read on screen.

There is also a pre-existing dead end this feature must consciously decide about: `MessageContentType.voice` already exists in `lib/ncfed/message_feed.dart:6`, and `lib/screens/feed_screen.dart:131-135` renders such a message as an inert `Chip(label: Text('Voice message'))`. The Border can therefore push base64 audio that the app can display but **physically cannot play**. See "Out of Scope" — this is adjacent but not the same capability.

### Two speakable surfaces

| Surface | Source of text | Screen | Feature |
|---|---|---|---|
| Agent answer to a request | `ConversationTurn.answerText` (`lib/ncfed/conversation_store.dart:9`) | `chat_screen.dart` | 067 |
| Border-pushed message | `EdgeMessage.content` where `contentType == text` (`message_feed.dart:11-22`) | `feed_screen.dart` | 066 |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Hear an answer without looking at the phone (Priority: P1)

An operator with their hands and eyes occupied — up a ladder in a data centre, arms inside a rack, driving to a site, holding a console cable — asks NetClaw a question by voice and needs the answer **spoken back**. Today they must stop, find the phone, and read it, which defeats the purpose of having asked by voice.

**Why this priority**: This closes the voice loop that features 067/068 opened. Voice input without voice output is a half-feature: the hands-free scenario that justified speech-to-text is still not achievable. Everything else in this spec is an enhancement on top of this one capability.

**Independent Test**: Submit a request (typed or spoken) in Chat, wait for the answer to arrive, tap the speak control on that turn, and confirm the answer is audible with the screen not being read. Delivers the complete hands-free ask→hear cycle on its own.

**Acceptance Scenarios**:

1. **Given** a completed turn with a non-empty `answerText`, **When** the operator activates the speak control on that turn, **Then** the answer text is spoken aloud through the device's current audio route.
2. **Given** an answer is being spoken, **When** the operator activates the same control again, **Then** playback stops immediately and does not resume from where it left off.
3. **Given** a turn in `pending`/`working` state with no answer yet, **When** the operator looks at that turn, **Then** no speak control is offered (there is nothing to speak).
4. **Given** a turn whose state is `failed` or `cancelled`, **When** the operator looks at that turn, **Then** no speak control is offered.
5. **Given** the device has no usable TTS voice installed, **When** the operator activates the speak control, **Then** they are told why nothing was spoken and what to install — never a silent no-op.

---

### User Story 2 - Answers spoken automatically as they arrive (Priority: P2)

For genuinely hands-free operation the operator should not have to tap anything: having asked by voice, the answer should simply be read out when it lands. Because an agent turn can take a while, the operator may have put the phone in a pocket by then.

**Why this priority**: This is what makes the feature usable in the field rather than merely present. It is separated from US1 because auto-speaking is a behaviour change with real annoyance potential (speaking aloud in a meeting), so it must be operator-controlled and is therefore independently shippable behind a setting.

**Independent Test**: Enable the auto-speak setting, submit a request, put the phone down, and confirm the answer is spoken on arrival with no interaction. Disable the setting and confirm silence.

**Acceptance Scenarios**:

1. **Given** auto-speak is enabled, **When** a turn transitions to `completed` with a non-empty answer, **Then** that answer is spoken without any operator interaction.
2. **Given** auto-speak is disabled (the default), **When** an answer arrives, **Then** nothing is spoken and the US1 manual control remains available.
3. **Given** auto-speak is enabled and an answer is already being spoken, **When** a second answer arrives, **Then** the answers are spoken one after another without overlapping or being dropped.
4. **Given** auto-speak is enabled, **When** the operator opens a historical turn from a previous session, **Then** old answers are not re-spoken on load.

---

### User Story 3 - Hear a Border-pushed message (Priority: P3)

The Border pushes messages the operator did not ask for — alerts, notifications, a heads-up designated by another agent. These land in the Feed and are equally worth hearing when the operator cannot look.

**Why this priority**: Valuable but strictly additive; the Feed is a review surface rather than an interactive loop, and US1/US2 deliver the core value without it.

**Independent Test**: With a text message in the Feed, activate the speak control on that message and confirm it is audible.

**Acceptance Scenarios**:

1. **Given** a Feed message with `contentType == text`, **When** the operator activates its speak control, **Then** its content is spoken.
2. **Given** a Feed message with `contentType == image`, **When** the operator views it, **Then** no speak control is offered.

---

### Edge Cases

- **Microphone interlock (critical).** What happens if playback starts while the recogniser is listening? Spoken output would be captured as input, transcribing NetClaw's own answer back into the next request. `chat_screen.dart` already tracks `_listening` and `voice_transcription.dart` exposes `cancel()`/`finishNow()`, so the state needed for an interlock exists — the spec requires one (FR-006).
- **Domain text is hostile to naive TTS.** Answers routinely contain IP addresses, prefix lengths, MAC addresses, interface names (`GigabitEthernet0/0/1`), AS numbers, and pasted CLI/table output. A synthesiser reading `10.0.0.1/24` as "ten point zero point zero point one slash twenty-four" is tolerable; one reading a 40-line routing table verbatim is useless and cannot be interrupted fast enough to matter. See FR-008/FR-009.
- **Interruptions.** Incoming call, another app taking audio focus, alarm, navigation prompt.
- **Lifecycle.** App backgrounded, screen locked, or the screen disposed mid-utterance. `chat_screen.dart:58-67` already releases the mic on dispose; playback needs the equivalent.
- **Audio routing.** Bluetooth headset, wired headphones, car audio, speakerphone, silent/vibrate mode. Does silent mode suppress playback the operator explicitly requested?
- **Very long answers.** Is there a ceiling, a summary, or is the whole thing read?
- **Empty/whitespace-only answer text.**
- **Rapid repeated activation** of the speak control.
- **Language mismatch** between the answer text and the installed voice.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The app MUST synthesise speech using the **device's local/on-device TTS capability**, not a network or cloud synthesis service.
- **FR-002**: The app MUST support voice playback on **both Android and iOS**. The Flutter codebase is shared and feature 071 has already ported it to iOS, so an Android-only capability would be an immediate parity regression.
- **FR-003**: Operators MUST be able to trigger playback of a completed answer's text on demand from the Chat screen.
- **FR-004**: Operators MUST be able to stop in-progress playback at any time.
- **FR-005**: The app MUST NOT offer a playback control where there is no speakable text (turns without an answer; non-text Feed content).
- **FR-006**: The app MUST NOT play synthesised audio while the microphone is open for speech recognition, so that output is never captured as input.
- **FR-007**: The app MUST stop playback when the owning screen is disposed and when the app leaves the foreground [NEEDS CLARIFICATION: should playback continue in the background — arguably desirable for the "phone in pocket" case in US2 — or stop? Background audio has real platform cost: an iOS background audio mode entitlement and an Android foreground service, both of which affect app review and battery].
- **FR-008**: The app MUST make network-operations text intelligible when spoken, rather than passing raw text to the synthesiser unmodified [NEEDS CLARIFICATION: how far should normalisation go? Options range from none, to punctuation/pacing hints for dotted-quad and interface names, to skipping fenced code and tabular blocks entirely. This materially changes scope and needs a decision before planning].
- **FR-009**: The app MUST handle answers whose bulk is machine output rather than prose [NEEDS CLARIFICATION: read in full, truncate at a ceiling, or speak a spoken-form summary? A spoken summary would require Border-side support — the phone has only the final answer text — which would widen this feature beyond the mobile client].
- **FR-010**: The app MUST report to the operator when playback cannot proceed (no voice/engine available, permission or platform failure) rather than failing silently. This follows the precedent set for the microphone, where a silent failure was explicitly called out as the worst outcome (`voice_transcription.dart`: *"tapped the mic and nothing whatsoever happened. Always say why."*).
- **FR-011**: Auto-speak (US2) MUST be operator-controllable and MUST default to **off**, so no existing installation starts speaking aloud after an update.
- **FR-012**: When multiple items are queued for playback, the app MUST speak them sequentially without overlap or loss.
- **FR-013**: The app MUST yield the audio session to higher-priority audio (calls, alarms) and MUST NOT resume silently in a way that surprises the operator [NEEDS CLARIFICATION: on regaining focus — resume, restart the utterance, or stay stopped?].
- **FR-014**: Playback state MUST be visible in the UI, so the operator can tell what is speaking and that a control did something.

### Privacy Requirements

- **FR-015**: Synthesis MUST NOT transmit message text off the device. This is a **continuation of an existing commitment, not a new one**: `voice_transcription.dart` sets on-device recognition specifically because *"Spoken requests here carry hostnames, interface IDs and IP addresses, so the claim has to hold."* **Answers carry the same class of data and generally more of it** — sending them to a cloud voice would silently reopen the exact hole the input path was hardened against.
- **FR-016**: Where the platform can silently fall back to a network voice, the app MUST prefer a local voice and MUST surface the situation rather than degrading quietly. The input path documents this precise hazard — a plugin that "constructs the ordinary recogniser anyway. Silent, and nothing in its API reports which one was chosen" — and the same trap must be assumed to exist on the synthesis side until proven otherwise. **Planning must verify what on-device guarantee each platform actually offers; do not assume parity with the STT path's `EXTRA_PREFER_OFFLINE` enforcement.**
- **FR-017**: The app MUST NOT persist synthesised audio to disk.

### Key Entities

- **Speakable item**: a unit of text offered for playback, derived from either a `ConversationTurn.answerText` or a text `EdgeMessage.content`. Carries the text, a stable identity (so the UI can show *which* item is speaking), and its origin surface.
- **Playback session**: the app's single logical speaking channel — at most one utterance audible at a time, with a queue behind it and a well-defined interaction with the microphone.
- **Voice playback preference**: operator-set, persisted, per-installation; at minimum the US2 auto-speak toggle. [NEEDS CLARIFICATION: also rate/pitch/voice selection, or is a single toggle sufficient for v1?]

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can complete an entire ask→hear cycle — submit a request by voice and understand the answer — without reading the screen.
- **SC-002**: Playback begins within a short, consistent delay of activation, fast enough that the control feels responsive rather than ambiguous.
- **SC-003**: Playback stops promptly when the operator asks it to, on the first activation.
- **SC-004**: No message text leaves the device for synthesis, verifiable by observing that playback works with all network interfaces disabled.
- **SC-005**: Synthesised audio is never transcribed back into a subsequent request (zero self-capture across repeated voice ask→hear→ask cycles).
- **SC-006**: Answers containing IP addresses and interface names are intelligible to an operator hearing them for the first time, without needing the screen to disambiguate.
- **SC-007**: Behaviour is equivalent on Android and iOS for every acceptance scenario above.
- **SC-008**: An installation that does not enable auto-speak behaves exactly as it did before this feature.

## Out of Scope

- **Playback of `MessageContentType.voice` audio.** The dead `Chip` at `feed_screen.dart:131-135` is a real gap, but playing Border-supplied base64 audio is *media playback*, not local synthesis — a different dependency and a different set of questions. Recorded here so it is not lost; it deserves its own spec. [NEEDS CLARIFICATION: confirm the operator agrees this stays separate — it is arguably the more obvious reading of "voice playback of messages", and the two could reasonably ship together.]
- **Voice playback on the Apple Watch.** Feature 072's `WatchRelay` already exposes `watch/feed` and `watch/history`, so the watch has the text and this is a natural follow-on, but the watch is a separate target with its own audio session and constraints.
- **Server/Border-side synthesis**, including the existing Twilio voice path (feature 043). This feature is strictly on-device.
- **Wake-word or fully conversational hands-free operation.**
- **Changes to speech-to-text.** The in-flight `voice_transcription.dart` work on `main` is a separate concern; this feature consumes the existing input path unchanged.

## Assumptions

- Operators run OS versions with a usable built-in TTS engine and at least one installed local voice. Absence is handled per FR-010 rather than by bundling a voice.
- English is the only language that must be supported for v1.
- The existing `ConversationStore` and `MessageFeedStore` are the sources of speakable text; no new Border-side protocol work is required — **unless FR-009 resolves toward Border-generated spoken summaries**, which would change that and should be settled during clarification.
- The Border's answer text is unchanged by this feature; any speech-oriented normalisation happens on the phone.
- No new push, enrollment, or federation behaviour is involved.

## Dependencies

- A Flutter TTS capability wrapping Android `TextToSpeech` and iOS `AVSpeechSynthesizer`. No such package is currently in `pubspec.yaml`; selecting one (and confirming its on-device guarantees per FR-016) is a Phase 0 research task.
- Existing: `ConversationStore`/`ConversationTurn` (067), `MessageFeedStore`/`EdgeMessage` (066), `VoiceTranscription` (067, for the FR-006 interlock), `chat_screen.dart`, `feed_screen.dart`, `settings_screen.dart` (for FR-011).

## Open Questions for Clarification

1. **Background playback** (FR-007) — is the "phone in pocket" case in US2 required? It is the difference between an in-app convenience and a platform-entitlement change.
2. **Normalisation depth** (FR-008) and **long machine output** (FR-009) — the largest scope lever in this spec.
3. **Scope of `voice` message playback** — genuinely separate feature, or expected in the same delivery?
4. **Settings surface** (FR-011) — bare auto-speak toggle, or rate/voice controls too?
5. **Silent/vibrate mode** — does an explicitly requested playback override it?
