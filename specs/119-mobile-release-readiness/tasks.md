# Tasks: Mobile Release Readiness

**Input**: Design documents from `/specs/119-mobile-release-readiness/`
**Prerequisites**: plan.md, spec.md, research.md

**Tests**: Bash script logic gets targeted syntax/argument-parsing checks; a full live install
against a fresh Border cannot be automated in this environment (needs a real host) — flagged
explicitly below as a live-verification task, matching this repo's convention (e.g. spec 117's
Phase 5) of marking what a session without the target hardware/environment cannot complete.

**Organization**: Tasks are grouped by user story (US1: install-time enrollment + existing-user
convenience wrapper; US2: formalize release-engineering artifacts) per spec.md's priorities.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Installer/CLI tooling layout: `scripts/peering-setup.sh`, `scripts/netclaw`,
`mobile/netclaw-mobile/MOBILE-ONBOARDING.md` — no new top-level directory.

---

## Phase 1: Setup

- [X] T001 Confirm `scripts/peering-setup.sh` and `scripts/netclaw` both pass `bash -n` (syntax
      check) before any change, as a baseline.

---

## Phase 2: Foundational

**Purpose**: N/A for this feature. US1's two halves (installer prompt, CLI wrapper) touch
different files with no shared new infrastructure; US2 is research-only (already done in
research.md). This phase is intentionally empty.

---

## Phase 3: User Story 1 - Enroll a mobile device during first-time Border setup (Priority: P1) 🎯 MVP

**Goal**: An operator answering "yes" to a new prompt, immediately after their Border/Risk role is
configured and the daemon is confirmed running, gets a working mobile enrollment QR/code without
leaving that session — and an existing operator gets the same sequence collapsed into one command.

**Independent Test**: Run `scripts/peering-setup.sh` interactively against a Border being promoted
for the first time; answer yes; confirm a QR/manual code appears. Separately, run
`netclaw risk enroll-mobile <label>` against an already-configured Border and confirm it produces
the same result as the documented five-command fast path.

### Implementation for User Story 1

- [X] T002 [US1] In `scripts/peering-setup.sh`, after `daemon_start` succeeds (either branch —
      fresh start or restart), add an interactive prompt gated on the same TTY check the file's
      other prompts implicitly rely on: "Would you like to enroll a mobile device now? (y/n)"
      (default "n", using the file's existing `ask_yn` helper).
- [X] T003 [US1] If yes, delegate entirely to the new wrapper — `"$NETCLAW_DIR/scripts/netclaw"
      risk enroll-mobile` — rather than reimplementing edge-check/promote/token logic in this
      file too (research R5's corrected design keeps that logic in exactly one place).
- [X] T004 [US1] If no (or non-interactive), skip this step entirely with no prompt, no hang, and
      no change to today's behavior (FR-002).
- [X] T005 [US1] (superseded by T002-T004's delegation design — retained as a placeholder ID so
      later task references in this file don't need renumbering.)
- [X] T006 [P] [US1] In `scripts/netclaw`, add a `risk_enroll_mobile()` function and wire it into
      the `risk)` dispatch case as `enroll-mobile` (alongside the existing `status`/`members`/
      `health`/`add` cases at line ~999): it runs `risk_edge_check`; if the result is `not_border`
      or `stack_disabled`, it now offers *inline* to promote (prompting for a Risk name if
      `N2N_RISK_NAME` isn't already set, then calling the existing `risk_role()` logic followed by
      `daemon_start`) rather than just printing a hint and giving up — this inline promotion is
      the one genuinely new piece of logic this feature adds (FR-003/FR-004/FR-005); it then
      re-runs `edge-check` and, once green, prompts for a device label and calls the existing
      `risk_edge_token` — reusing token issuance exactly, never reimplementing it.
- [X] T007 [US1] Update the `netclaw` script's own top-of-file usage comment (where
      `netclaw risk token --edge <device-label>` is already documented) to list the new
      `netclaw risk enroll-mobile <device-label>` one-command alternative.
- [X] T008 [US1] Review `mobile/netclaw-mobile/MOBILE-ONBOARDING.md`'s "Fast path" section (FR-005)
      and add the new `risk enroll-mobile` wrapper as the recommended entry point, keeping the
      full five-command manual sequence documented immediately below it for troubleshooting when
      the wrapper reports a problem — do not remove or shorten the existing troubleshooting table.

### Tests for User Story 1

- [X] T009 [P] [US1] `bash -n scripts/peering-setup.sh` and `bash -n scripts/netclaw` both pass
      after the above changes (syntax-valid).
- [X] T010 [P] [US1] Manually trace both new interactive paths (T002-T005 and T006) against
      `edge-check` reporting green and reporting a specific failure, confirming the explanatory
      message (not a crash) appears in the failure case — this is a logic walkthrough, not an
      automated test, since neither script has an existing automated test harness to extend.

**Checkpoint**: The installer's fresh-Border path and the existing-operator convenience wrapper
both exist and are internally consistent with each other and with the documented manual sequence.
Full live confirmation is User Story 1's own live-verification item below (T011-T013).

### Live verification for User Story 1

**⚠️ Requires a real Border host — this environment has no fresh box to install against.**

- [ ] T011 [US1] On a real host, run `scripts/peering-setup.sh` through a fresh Border promotion
      and confirm the new prompt appears at the right point, produces a working QR, and that
      answering "no" changes nothing about today's flow.
- [ ] T012 [US1] On a real, already-configured Border, run `netclaw risk enroll-mobile <label>`
      and confirm it produces an equivalent result to the documented five-command fast path.
- [ ] T013 [US1] Confirm FR-005b in practice: enroll a second device on an already-running,
      already-Border-configured host and confirm no restart was needed (research R3) — the
      already-live daemon accepts the new member without a cycle.

---

## Phase 4: User Story 2 - Find the complete App Store release story in one place (Priority: P2)

**Goal**: Someone looking for why the app's Support URL, privacy consent gate, or archive script
look the way they do finds the answer in this spec's own `research.md`, not scattered undocumented
files.

**Independent Test**: Open `research.md` and confirm each rejection (guideline number, cause, fix)
and each release-engineering artifact is present.

### Implementation for User Story 2

- [X] T014 [US2] Document the full App Store review rejection history (three rounds: 2.3.3/1.5/2.1
      combined, 2.1(a)/2.1 combined, 5.1.1(i)/5.1.2(i)) with guideline number, root cause, and
      resolving artifact — done in `research.md` R1.
- [X] T015 [US2] Reference every release-engineering artifact produced this session by file path
      (`scripts/mobile-release-archive.sh`, `ExportOptions.plist`, `privacy-policy.html`,
      `support.html`, the onboarding consent gate, the three listing/review-notes drafts) — done
      in `research.md` R1.
- [X] T016 [US2] Commit the one artifact that had been written but never actually committed
      (`docs/APP-REVIEW-REPLY-5.1-DRAFT.md`) so FR-007's "every artifact referenced" claim is true
      of the actual git history, not just the working tree — done.

**Checkpoint**: User Story 2 is fully satisfied by `research.md` as written; no further
implementation needed for this story.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T017 Re-run `bash -n` on both changed scripts together after all of Phase 3's changes to
      confirm nothing regressed.
- [X] T018 Update `mobile/netclaw-mobile/MOBILE-ONBOARDING.md`'s own cross-references if the new
      wrapper changes which command is "the" recommended fast path anywhere else in that file.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Empty — nothing blocks either story.
- **User Story 1 (Phase 3)**: Depends on Setup only. T002-T005 (installer) and T006-T008 (CLI
  wrapper + docs) can proceed in parallel — disjoint files.
- **User Story 2 (Phase 4)**: Already complete via `research.md` — no code dependency on Phase 3.
- **Polish (Phase 5)**: Depends on Phase 3's changes existing.

### Parallel Opportunities

- T002-T005 (`peering-setup.sh`) and T006-T008 (`scripts/netclaw` + docs) in parallel.
- T009/T010 (tests) in parallel with each other once T002-T008 land.

---

## Implementation Strategy

### What this session can complete

Everything in Phase 1, Phase 3's Implementation + Tests (T002-T010), and all of Phase 4 (already
done via `research.md`) — no live host or mobile device needed for any of it, since it's pure
script/documentation editing plus a logic walkthrough.

### What needs a live host (handed to the user)

Phase 3's Live Verification (T011-T013) — actually running the installer against a fresh Border
and confirming the prompt, the wrapper, and the no-restart-needed claim hold on real
infrastructure. Per this repo's own convention, this is the point at which the feature is
considered *implemented* but not yet *live-verified*.
