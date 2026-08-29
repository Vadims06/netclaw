# Implementation Plan: Mobile Release Readiness

**Branch**: `119-mobile-release-readiness` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/119-mobile-release-readiness/spec.md`

## Summary

Two independent deliverables. (1) A new install-time convenience: after an operator promotes a
Claw to Border and its edge listener is confirmed live (`scripts/peering-setup.sh`'s existing
daemon-start step), offer to mint and display a mobile enrollment QR/code right there, reusing the
exact existing `netclaw risk edge-check` → `role border` → restart → `token --edge` sequence
already documented in `mobile/netclaw-mobile/MOBILE-ONBOARDING.md` — not a new enrollment
mechanism. A new `netclaw risk enroll-mobile <label>` convenience wrapper collapses that sequence
into one command for existing operators too. (2) Formalizing this session's App Store
release-engineering work (already committed to `main`: privacy policy, support page, AI-disclosure
consent gate, archive script fixes, listing/review-notes drafts) as documented, discoverable spec
deliverables rather than untracked ad hoc files — done via this spec's own `research.md` (R1).

## Technical Context

**Language/Version**: Bash (`scripts/peering-setup.sh`, matching its own existing style), Python
3.10+ (the CLI wrapper lives alongside the existing `netclaw risk` subcommand implementation),
Markdown (`MOBILE-ONBOARDING.md` review/update) — no new language.
**Primary Dependencies**: None new. Reuses the mesh daemon's existing enrollment/token-issuance
mechanism (`netclaw risk edge-check`/`role border`/`token --edge`, `bgp-daemon-v2.py`), the same
`websockets`/`qrcode` dependencies that mechanism already requires.
**Storage**: N/A — no new persisted state. Enrollment continues to live in the existing federation
database (`~/.openclaw/n2n/federation.db`); this feature adds no new table or column.
**Testing**: Bash script logic (dry-run/argument-parsing checks, since a live end-to-end install
against a fresh box needs a real environment this session doesn't have); existing Python test
conventions if the CLI wrapper needs its own coverage.
**Target Platform**: Linux Border host (systemd `--user` units), matching every prior N2N/federation
spec (052-118).
**Project Type**: CLI/installer tooling + documentation — no mobile app changes in this feature
(the mobile app's own enrollment flow, QR scanner, and manual-entry screen are unchanged and are
consumed as-is, per research R2).
**Performance Goals**: N/A — this is an interactive, human-paced install/setup flow, not a
performance-sensitive path.
**Constraints**: MUST NOT introduce a second enrollment mechanism (FR-003); MUST NOT change
behavior for an operator who declines or runs non-interactively (FR-002); MUST NOT require a
restart for enrollments after the first, once a Border is already correctly configured (research R3).
**Scale/Scope**: One new interactive prompt, one new CLI convenience wrapper, one documentation
review pass, one research-only formalization of already-shipped release artifacts. Deliberately
small — this is glue around an already-working enrollment mechanism, not new enrollment plumbing.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Safety-First Operations**: N/A — no device configuration changes; this is Border-side
  installer/CLI tooling.
- **II. Read-Before-Write**: Satisfied — `netclaw risk edge-check` (read/diagnose) always runs
  before any state-changing step (`role border`, `token --edge`), matching the existing documented
  sequence exactly.
- **IV. Immutable Audit Trail**: Satisfied — enrollment already produces GAIT-audited member rows
  via the existing mechanism; this feature adds no new mutation path that bypasses it.
- **V. MCP-Native Integration**: N/A — no new MCP server; this is installer/CLI glue around the
  existing mesh daemon.
- **XI. Full-Stack Artifact Coherence**: Satisfied — this plan's own agent-context update keeps
  `CLAUDE.md` in sync, per the same discipline every prior spec in this series follows.

No violations. Gate passes without complexity justification.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
scripts/
├── netclaw                  # the CLI's actual implementation (symlinked to ~/.local/bin/netclaw);
│                             # risk_edge_check(), risk_edge_token(), risk_role(), risk_members()
│                             # already live here as bash functions under the `risk)` dispatch case
│                             # (line ~999) -- NEW: risk_enroll_mobile() wrapper + `enroll-mobile`
│                             # dispatch case, collapsing edge-check -> role border -> restart ->
│                             # token --edge into one command (User Story 1's "existing users" half)
├── peering-setup.sh          # BGP mesh peering wizard; daemon_start() (line 68) already has its
│                             # own interactive "start it now?"/"restart it now?" prompt (does NOT
│                             # configure N2N_ROLE/Risk -- that's scripts/netclaw's risk_role(),
│                             # a separate action, per research R5's correction) -- NEW: a thin
│                             # "enroll a mobile device now?" prompt right after daemon_start
│                             # succeeds, delegating to `netclaw risk enroll-mobile` for the
│                             # actual logic (User Story 1's "fresh install" half)
└── lib/install-steps.sh      # unchanged -- already installs the mesh daemon's websockets/qrcode
                              # deps (research R1); no new step needed here

mobile/netclaw-mobile/
└── MOBILE-ONBOARDING.md      # reviewed for gaps per FR-005; updated to reference the new
                              # risk_enroll_mobile wrapper as the recommended fast path, keeping
                              # the full manual sequence documented underneath for troubleshooting

specs/119-mobile-release-readiness/
└── research.md               # already captures the App Store rejection history (FR-006) and
                              # references every release-engineering artifact by path (FR-007) --
                              # no separate contracts/data-model needed, this feature adds no API
                              # surface or persisted schema
```

**Structure Decision**: Installer/CLI tooling layout, matching every prior N2N/federation spec.
`scripts/peering-setup.sh` gets the new first-run prompt (it already owns Border/Risk role
configuration and the daemon-start step); `scripts/netclaw` gets the new `risk enroll-mobile`
convenience wrapper (it already owns every other `risk` subcommand); `MOBILE-ONBOARDING.md` gets
reviewed and updated, not replaced. No new top-level directory, no mobile-app changes.

## Complexity Tracking

*No constitution violations — this section is not applicable.*
