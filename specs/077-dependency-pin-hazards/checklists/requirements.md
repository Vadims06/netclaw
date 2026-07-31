# Specification Quality Checklist: Dependency-Pin Hazards

**Purpose**: Validate specification completeness before planning
**Created**: 2026-07-31
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — every figure was measured, not inferred
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

**Status: PASS — ready for `/speckit.plan`.**

## Validation Notes

### Every figure was audited, and one was wrong first time

| Claim | How measured |
|---|---|
| `mcp 2.0.0` removed the module | Downloaded the wheel; zero `mcp/server/fastmcp/` files, no `fastmcp` in `Requires-Dist` |
| 7 servers exposed | Cross-referenced unbounded pins against actual `mcp.server.fastmcp` imports |
| 188 pip installs (143 bare `pip3`, 46 bare `pip`, 2 venv-scoped) | Counted in `install-steps.sh` |
| 2 `ensurepip`-dependent venv creations | Grep across `scripts/` |

**A correction is recorded in the spec.** The first audit treated exact `==` pins as unbounded, so it
named the wrong servers — `f5-mcp-server` (`mcp==1.4.1`) and `meraki-magic-mcp-community`
(`fastmcp==2.2.10`) are safe. The total is coincidentally still 7; the membership is not. Recorded
because a spec whose figures shift silently is worse than one that shows its corrections.

### Why this is P1/P1 rather than P1/P2

US2 (enforcement) is equal priority to US1 (repair), not lower. Three hazards survived because nothing
checked for them, and the repair alone would leave the next `mcp 3.0` to be discovered the same way.
This mirrors spec 075, where the enforcement story was co-equal with the cleanup.

### Deliberate scope limits, stated rather than implied

- **Declared pins only.** Transitive breakage needs a lockfile strategy this repository does not have.
- **Pinning `<2` is the default repair**, not migration to standalone `fastmcp`. Migration is legitimate
  where a server wants the new API but is a much larger per-server change, and forcing it would turn a
  hygiene fix into seven rewrites.
- **Not every unbounded pin is a defect.** The spec distinguishes API-significant dependencies — whose
  submodules are imported — from those used via stable top-level APIs. Demanding upper bounds everywhere
  would produce noise and train people to suppress the check.

### One thing worth watching in planning

`n2n-mcp` is exposed via `fastmcp>=0.1.0` — the *standalone* package, a different hazard from the other
six, and it backs the federation. It is the highest-risk single repair here and should not be batched
carelessly with the six `mcp>=` fixes.

## Notes

- Ready for `/speckit.plan`. Phase 0 should settle: pin-versus-migrate per server, how to classify
  API-significant dependencies without hand-maintaining a list, and whether resolution checking can be
  fast enough to run pre-push.
