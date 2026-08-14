# Tasks: Session Budget Enforcement Guardrails

**Input**: Design documents from `/specs/109-session-budget-guardrails/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md
**Tests**: Included — unit tests for enforcement logic, integration test for halt behavior.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 [P] Add `NETCLAW_SESSION_BUDGET_USD` to `.env.example` with default `5.0` and inline comment explaining its purpose
- [ ] T002 [P] Document the budget enforcement feature in `docs/` or `README.md` — operator-facing explanation of what happens when a cap is hit

---

## Phase 2: Foundational (Blocking Prerequisites)

- [ ] T003 Create `src/netclaw_tokens/budget_policy.py` with `BudgetPolicy` dataclass (fields per data-model.md §1) and `load_budget_policy(config: dict, interface_type: str | None = None) -> BudgetPolicy` function that resolves agent-level → interface-level → env-var overrides in correct precedence
- [ ] T004 [P] In `src/netclaw_tokens/__init__.py`, add `BudgetPolicy` to exports and `__all__`, add lazy import for `load_budget_policy`
- [ ] T005 [P] Unit test `tests/test_budget_policy.py`: verify default construction, config override loading, env-var precedence, interface-specific override resolution

**Checkpoint**: BudgetPolicy dataclass + loader exist and are tested. No enforcement yet.

---

## Phase 3: User Story 1 — Session cost cap halts runaway spending (Priority: P1) 🎯 MVP

**Goal**: When cumulative session cost exceeds the configured ceiling, the agent halts and reports.

**Independent Test**: Instantiate SessionLedger with a $0.50 budget, record costs totaling $0.60, verify `is_over_budget()` returns True and `get_halt_message()` returns a formatted summary.

- [ ] T006 [US1] Extend `SessionLedger.__init__()` to accept an optional `budget: BudgetPolicy` parameter (defaults to `BudgetPolicy()` if not provided — zero regression for existing callers that don't pass it)
- [ ] T007 [US1] Add `is_over_budget() -> bool` method to SessionLedger — returns `self.total_cost >= self.budget.session_budget_usd`
- [ ] T008 [US1] Add `budget_halted: bool = False` and `halt_reason: Optional[str] = None` fields to SessionLedger
- [ ] T009 [US1] Add `check_budget() -> tuple[bool, str | None]` method that sets `budget_halted` and `halt_reason` if over budget, returns `(should_halt, reason)` — this is the method the gateway calls before each API request
- [ ] T010 [US1] Add `get_halt_message() -> str` method that formats a user-facing budget-exceeded message including: total cost, token counts, top 5 tools by cost, and continuation instructions
- [ ] T011 [US1] Add `override_budget()` method that extends `budget.session_budget_usd` by `budget.override_increment_usd` and clears `budget_halted`/`halt_reason`
- [ ] T012 [P] [US1] Unit test `tests/test_session_budget.py`: test `is_over_budget()` returns False below cap and True at/above cap; test `check_budget()` sets halt state; test `override_budget()` clears halt and extends ceiling; test `get_halt_message()` produces non-empty formatted string

**Checkpoint**: SessionLedger enforces cost caps. Gateway integration is the caller's responsibility (the library provides the check, the gateway acts on it).

---

## Phase 4: User Story 2 — Tool-call depth limit (Priority: P2)

**Goal**: Limit tool calls per user message to prevent unbounded agentic exploration.

**Independent Test**: Configure `max_tool_calls_per_turn: 5`, call `record_tool_call()` 6 times, verify `is_over_tool_limit()` returns True on the 6th call.

- [ ] T013 [US2] Add `tool_calls_this_turn: int = 0` field to SessionLedger
- [ ] T014 [US2] Add `new_turn()` method that resets `tool_calls_this_turn` to 0 (called by gateway on each user message)
- [ ] T015 [US2] Add `record_tool_call()` method that increments `tool_calls_this_turn`
- [ ] T016 [US2] Add `is_over_tool_limit() -> bool` method — returns `self.tool_calls_this_turn >= self.budget.max_tool_calls_per_turn`
- [ ] T017 [US2] Extend `check_budget()` to also check tool-call limit (returns `(True, "tool_limit")` if exceeded)
- [ ] T018 [P] [US2] Unit test: verify `new_turn()` resets counter; verify limit triggers at configured threshold; verify `check_budget()` catches both cost and tool-limit independently

**Checkpoint**: Both cost cap and tool-call limit are enforced via the same `check_budget()` interface.

---

## Phase 5: User Story 3 — Per-interface model routing (Priority: P3)

**Goal**: Different interfaces (mobile, desktop, discord) get different default models.

**Independent Test**: Call `load_budget_policy(config, interface_type="openai")` with an interfaceDefaults config that sets Haiku for openai. Verify the returned policy reflects the mobile model setting.

- [ ] T019 [US3] Extend `BudgetPolicy` with optional `model: str | None = None` and `thinking_level: str | None = None` fields (these are routing hints, not enforcement — the gateway reads them at session init)
- [ ] T020 [US3] In `budget_policy.py`, extend `load_budget_policy()` to resolve `interfaceDefaults.<type>.model` and `interfaceDefaults.<type>.thinkingLevel` into the returned BudgetPolicy
- [ ] T021 [US3] Add a top-level `resolve_session_config(config: dict, session_key: str) -> BudgetPolicy` function that parses the session key to determine interface type and calls `load_budget_policy()` with it
- [ ] T022 [P] [US3] Unit test: verify interface detection from session key patterns; verify model routing for openai/n2n/tui/discord; verify fallback to defaults when no interface-specific config exists

**Checkpoint**: Library provides a one-call function (`resolve_session_config`) that returns the full budget policy + model routing for any session.

---

## Phase 6: User Story 4 — Context growth awareness (Priority: P4)

**Goal**: Warn operators when context size makes continued conversation expensive.

- [ ] T023 [US4] Add `should_warn_context(context_tokens: int) -> bool` method to SessionLedger — returns True when `context_tokens >= budget.context_warning_tokens`
- [ ] T024 [US4] Add `get_context_warning(context_tokens: int, model: str) -> str` method that formats a warning including current context size, approximate cost-per-turn at current model pricing, and suggestion to start fresh
- [ ] T025 [P] [US4] Unit test: verify warning triggers at threshold, not below; verify message includes cost estimate

**Checkpoint**: Context warnings available. Auto-summarize (context_auto_summarize) is documented as a future enhancement hook but not implemented in this PR (marked in spec as P4).

---

## Phase 7: Polish & Integration

- [ ] T026 [P] Add `BudgetPolicy` and all new SessionLedger methods to the module docstring in `__init__.py`
- [ ] T027 [P] Update `requirements.txt` in `src/netclaw_tokens/` if any new dependencies are needed (likely none — this is pure Python)
- [ ] T028 Add example `openclaw.json` budget configuration to `config/` or document in existing config file comments
- [ ] T029 [P] Add Prometheus metric documentation: `netclaw_session_budget_trips_total` counter spec (labels: agent, reason, interface) — document in a metrics section of the feature docs, matching the existing `netclaw_investigation_budget_trips_total` pattern

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: No dependencies (BudgetPolicy is standalone)
- **US1 (Phase 3)**: Depends on Phase 2 (needs BudgetPolicy)
- **US2 (Phase 4)**: Depends on Phase 2 (needs BudgetPolicy), can parallel with Phase 3
- **US3 (Phase 5)**: Depends on Phase 2 (extends BudgetPolicy)
- **US4 (Phase 6)**: Depends on Phase 3 (uses SessionLedger extensions)
- **Polish (Phase 7)**: Depends on all above

### MVP Delivery

Phase 1 + Phase 2 + Phase 3 = functional cost cap enforcement.
This alone would have prevented the $11 incident.

### Parallel Opportunities

- T001 and T002 can run in parallel (different files)
- T004 and T005 can run in parallel with T003 (different files)
- Phase 3 and Phase 4 can run in parallel (different methods, no shared state)
- All test tasks marked [P] can run alongside their implementation tasks
