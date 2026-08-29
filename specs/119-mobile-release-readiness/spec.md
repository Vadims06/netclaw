# Feature Specification: Mobile Release Readiness

**Feature Branch**: `119-mobile-release-readiness`
**Created**: 2026-08-29
**Status**: Draft
**Input**: User description: "Mobile Release Readiness — formalize NetClaw Mobile's path to a
public App Store release. Two parts: (1) NEW CAPABILITY: during a NetClaw Border's first-time
install, prompt the operator to enroll a mobile device now, reusing the existing enrollment flow.
(2) FORMALIZE EXISTING AD HOC WORK: this session produced real App-Store-release artifacts
(archive script, privacy policy, support page, AI-disclosure consent gate, listing/review-notes
drafts) directly on main without going through the spec-driven process — document that
release-engineering work as proper spec deliverables. Out of scope: Android release readiness."

## Context

NetClaw Mobile went through three rounds of Apple App Review rejection before reaching a
submittable state: inaccurate screenshots (splash-only, not "app in use"), a non-functional
Support URL, a missing explanation for App Review of how to use a self-hosted-Border app, and
finally an AI-data-sharing disclosure/consent gap (Guidelines 5.1.1(i)/5.1.2(i)). Every fix for
these was made directly on `main` in an ad hoc session, without a spec — unlike every other
NetClaw capability, which goes through specify → plan → tasks → implement. This feature closes
that gap two ways: it captures the release-engineering work already done as proper, discoverable
spec deliverables (so a future maintainer can find the whole story in one place instead of
scattered `docs/` files with no context), and it adds one new real capability the release process
exposed as missing — a first-time Border install has no built-in way to enroll a mobile device,
even though enrollment itself already exists and works.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Enroll a mobile device during first-time Border setup (Priority: P1)

An operator runs the NetClaw installer for the first time to stand up a fresh Border. Today,
enrolling a phone or watch afterward is a separate, undocumented step they have to discover on
their own (open the mobile app, find the QR scanner, find where the Border shows an enrollment
code). The operator needs the installer itself to offer enrollment right there, in the same
sitting, so a fresh Border and a fresh phone can be paired without hunting for a second set of
instructions.

**Why this priority**: This is the one genuinely new capability this feature adds, and it directly
removes a real, observed gap — every mobile enrollment in this project's own history so far has
been a manual, ad hoc step figured out after the fact, not something the install process itself
offered.

**Independent Test**: Run the installer against a fresh environment, answer "yes" when prompted to
enroll a mobile device, and confirm a working enrollment QR/code appears without leaving the
installer session or consulting separate documentation.

**Acceptance Scenarios**:

1. **Given** a fresh Border install with no prior enrollment, **When** core setup finishes,
   **Then** the installer asks whether to enroll a mobile device now.
2. **Given** the operator answers yes, **When** the Border/Risk services have finished starting and
   are confirmed up, **Then** the installer triggers enrollment at that point — not earlier, since
   the daemon must actually be running to issue a valid token — and produces a working enrollment
   QR code or manual enrollment code using the Border's existing enrollment mechanism (the same
   one the existing enrollment CLI already uses). No new, separate enrollment pathway is invented.
3. **Given** the operator answers no (or the installer is running non-interactively, e.g. in CI
   with no terminal attached), **When** installation proceeds, **Then** it completes exactly as it
   does today, with no enrollment step and no hang waiting for input.
4. **Given** the operator's Border configuration doesn't yet support mobile enrollment (e.g. the
   edge listener isn't enabled), **When** they answer yes anyway, **Then** the installer explains
   what's missing rather than failing silently or crashing the install.
5. **Given** an operator who already has a Border running from before this feature existed, **When**
   they want to enroll a device without re-running the installer, **Then** the existing manual
   enrollment path still works — reviewed and improved as part of this feature if it has any gaps,
   so existing operators get an equally good experience to a fresh install.
6. **Given** a device successfully enrolls (whether via the new installer prompt or the existing
   manual path), **When** enrollment completes, **Then** the Border's own awareness of its current
   state — its self-model context, memory, heartbeat reporting, and risk/federation posture data —
   reflects the newly enrolled device. If this requires the gateway or daemon to reload/cycle to
   pick up the change, that is acceptable; it must not require a full reinstall or leave the
   Border reporting stale device counts indefinitely.

---

### User Story 2 - Find the complete App Store release story in one place (Priority: P2)

Someone — a future contributor, or the operator themselves months later — wants to understand how
NetClaw Mobile actually reached the App Store: what Apple rejected, why, and what fixed it. Today
that story is scattered across ungrouped files in `docs/` with no narrative connecting them to the
rejections that caused them. They need it captured the same way every other NetClaw capability's
history is captured — as a spec with its own research record.

**Why this priority**: Valuable for the project's own institutional memory and consistency with
how every other feature in this codebase is documented, but it doesn't block anyone from using the
app today the way User Story 1's gap does — hence the lower priority.

**Independent Test**: Open this feature's `research.md` and confirm it lists each App Store review
rejection this project actually received (by guideline number), what caused it, and which existing
file resolves it, with no gaps.

**Acceptance Scenarios**:

1. **Given** this feature's documentation, **When** a reader looks for why the app's Support URL
   points where it does, **Then** they find the specific rejection (Guideline 1.5) that caused it
   and the fix (`docs/support.html`).
2. **Given** this feature's documentation, **When** a reader looks for why the onboarding screen
   has a consent checkbox, **Then** they find the specific rejection (Guidelines 5.1.1(i)/5.1.2(i))
   that caused it and the fix (`onboarding_explainer_screen.dart`, `privacy-policy.html`).
3. **Given** this feature's documentation, **When** a reader looks for the release build/export
   process, **Then** they find `scripts/mobile-release-archive.sh` referenced along with the two
   real problems it was fixed to work around (a stale free/paid Apple team ID guard, and stale App
   Store distribution provisioning profiles).

### Edge Cases

- What happens if the operator's phone isn't nearby / they can't scan a QR during install? The
  enrollment code the installer produces must remain valid long enough to be used later via the
  existing manual-entry path, not expire the instant the installer session ends.
- What happens if the installer is re-run against a Border that already has enrolled devices? It
  must not treat "already has devices enrolled" as "must enroll another one" — asking again is
  harmless, but a "no" answer must not be treated as an error state.
- What happens if a gateway/daemon reload triggered by a fresh enrollment races an in-progress
  conversation on another already-enrolled device? That existing session must not be dropped or
  corrupted by the reload.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Border installer MUST, after core setup completes, ask the operator whether they
  want to enroll a mobile device now.
- **FR-002**: If the operator declines, or the installer runs non-interactively, installation MUST
  complete exactly as it does today — no enrollment step, no hang, no error.
- **FR-003**: If the operator accepts, the installer MUST produce a working enrollment QR code or
  manual enrollment code using the Border's existing enrollment/token-issuance mechanism — this
  feature MUST NOT invent a second, parallel enrollment pathway.
- **FR-004**: If the operator accepts but the Border's current configuration doesn't support mobile
  enrollment yet, the installer MUST explain what's missing rather than failing without
  explanation.
- **FR-005**: The existing manual enrollment path (used today, outside the installer, by operators
  with a Border from before this feature existed) MUST continue to work for enrolling any device
  after the first, or for an operator who declined the installer's prompt — and MUST be reviewed
  and improved as part of this feature if gaps are found, so existing operators aren't left with a
  worse experience than a fresh install.
- **FR-005a**: The installer's enrollment trigger MUST fire only after Border/Risk services are
  confirmed running, not earlier in the install sequence — an enrollment token cannot be validly
  issued before the daemon that issues it is up.
- **FR-005b**: Once a device enrolls (via either path), the Border's own contextual awareness of
  its current state — self-model/SOUL context, memory, heartbeat reporting, and risk/federation
  posture — MUST come to reflect the newly enrolled device, even if this requires a gateway/daemon
  reload cycle to take effect.
- **FR-006**: This feature's documentation MUST record, for each App Store review rejection this
  project actually received, the guideline number, the root cause, and which existing artifact
  resolves it.
- **FR-007**: This feature's documentation MUST reference every release-engineering artifact
  already produced (the archive script and its fixes, `ExportOptions.plist`, the privacy policy,
  the support page, the onboarding consent gate, the listing/review-notes drafts) by file path, so
  none of it remains undiscoverable ad hoc content.

### Key Entities

- **Enrollment prompt**: A first-run installer step, not a new stored entity — it invokes the
  Border's existing enrollment/token-issuance mechanism and displays whatever that mechanism
  already produces (QR payload or manual code).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator running the installer for the first time can reach a working,
  phone-enrolled state without leaving the installer session or reading separate documentation.
- **SC-002**: An operator who declines the prompt experiences installation completing identically
  to today's behavior — zero regression for the "don't want mobile yet" path.
- **SC-002a**: After any successful enrollment, the Border's own reporting of its current state
  (heartbeat, memory, self-model context) reflects the newly enrolled device within one
  gateway/daemon reload cycle — not "never," and not only after a full reinstall.
- **SC-003**: Every App Store review rejection this project received across its actual submission
  history is documented with guideline number, root cause, and fix, discoverable in one place.
- **SC-004**: Every release-engineering file produced during the App Store submission effort is
  referenced by path from this feature's own documentation.

## Assumptions

- The Border's existing enrollment/token-issuance mechanism (already used by the mobile app's
  QR-scan flow) is reused as-is; this feature does not change how enrollment itself works, only
  when an operator is first offered the chance to use it.
- "First-time install" means the installer's normal first-run path (`scripts/install.sh`); this
  feature does not add a way to re-trigger the prompt on an already-configured Border outside of
  re-running the installer.
- Android release readiness is explicitly out of scope — it is gated separately behind recruiting
  12 external test volunteers and has not started.
- This feature's own artifact set (research.md, plan.md, tasks.md) is where the App Store
  rejection history and existing release-engineering files get documented; it does not require
  moving or renaming any of those existing files, only referencing them.
