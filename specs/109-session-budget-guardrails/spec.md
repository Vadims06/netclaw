# Feature Specification: Session Budget Enforcement Guardrails

**Feature Branch**: `109-session-budget-guardrails`
**Created**: 2026-08-14
**Status**: Draft
**Input**: Live operational incident — a 7-question conversational session from a mobile (iPhone/N2N) interface generated 59 assistant turns, 82 tool calls, ~3M input tokens, and $11.13 USD in API costs over 2 hours using claude-sonnet-5 with `thinkingLevel: high`. The existing `netclaw_tokens` library tracks and displays costs (observability-only) but never enforces any ceiling. The alert agent has budget guardrails (hourly caps, concurrency limits, cheap model default) but the main agent — which handles all conversational/N2N/phone sessions — has zero cost controls.

## Problem Statement

The `netclaw_tokens` library (`src/netclaw_tokens/`) provides:
- Token counting per interaction
- Model-aware cost calculation
- Session-level cumulative tracking (SessionLedger)
- GCF serialization for token savings
- Footer display showing costs to the operator

What it does NOT provide:
- **Enforcement** — no mechanism halts or downgrades a session when costs exceed a threshold
- **Per-interface routing** — mobile/N2N sessions inherit the same expensive model as desktop
- **Tool-call depth limits** — an agentic chain can run unlimited tool calls per user message
- **Context growth control** — tool results accumulate in context forever, causing input tokens to balloon quadratically across turns

The alert agent (`agents.list[1]`) demonstrates the correct pattern: it uses `claude-haiku-4-5`, has a restricted tool allowlist, and the alert-receiver enforces hourly/concurrent budget caps via `netclaw_investigation_budget_trips_total`. This feature extends that pattern to ALL agent sessions.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Session cost cap halts runaway spending (Priority: P1)

As a NetClaw operator, I want a configurable per-session cost ceiling so that when cumulative spending in a single session exceeds my threshold (e.g., $2.00), the agent stops tool-calling and informs me it has hit the budget — rather than silently burning $11+ on a casual phone question.

**Why this priority**: This is the exact failure that occurred. A cost cap alone would have limited the damage from $11 to $2 without any other changes.

**Independent Test**: Start a session, configure a $0.50 budget cap, issue a question that would normally trigger expensive multi-tool chains. Verify the agent halts after reaching the cap and returns a budget-exceeded message with the accumulated cost summary.

**Acceptance Scenarios**:

1. **Given** a session with `session_budget_usd: 2.0` configured, **When** cumulative cost (tracked by SessionLedger) exceeds $2.00, **Then** the agent stops making further API calls and returns a message indicating the budget was reached, including the cost breakdown.
2. **Given** a session with no explicit budget configured, **When** costs accumulate, **Then** the system uses a sensible default ceiling (e.g., $5.00) rather than unlimited.
3. **Given** a session that has been budget-halted, **When** the operator explicitly requests continuation (e.g., "continue" or "override budget"), **Then** the budget resets or extends by the configured increment, allowing the session to proceed.
4. **Given** a budget halt occurs mid-tool-chain, **When** the agent stops, **Then** it provides a partial summary of what it accomplished before the halt, not a raw error.

---

### User Story 2 - Tool-call depth limit per user message (Priority: P2)

As a NetClaw operator, I want a configurable maximum number of tool calls per user message so that a single question cannot trigger a 59-turn, 82-tool-call exploration — the agent must summarize its findings and ask for direction after N tool calls instead of running indefinitely.

**Why this priority**: Even with a cost cap, unbounded tool chains waste tokens on low-value exploration. A depth limit forces the agent to be deliberate about which tools it invokes.

**Independent Test**: Configure `max_tool_calls_per_turn: 15`. Issue a question that would normally generate 50+ tool calls. Verify the agent stops after 15 tool calls, summarizes findings so far, and asks whether to continue.

**Acceptance Scenarios**:

1. **Given** `max_tool_calls_per_turn: 15` configured, **When** a user message triggers tool use, **Then** the agent executes at most 15 tool calls before pausing and presenting intermediate results.
2. **Given** the tool-call limit is reached, **When** the agent pauses, **Then** it summarizes what was found so far and asks "Should I continue investigating?" rather than silently stopping.
3. **Given** the operator says "yes, continue", **When** the agent resumes, **Then** the tool-call counter resets for the next batch of N calls.
4. **Given** no explicit tool-call limit is configured, **Then** a sensible default applies (e.g., 20 tool calls per user message).

---

### User Story 3 - Per-interface model routing (Priority: P3)

As a NetClaw operator, I want different model defaults based on the session interface (mobile/N2N vs. desktop/TUI vs. alert) so that casual phone questions use a cheaper model by default while I can still explicitly request an expensive model when needed.

**Why this priority**: Model routing prevents the problem at the source — if mobile sessions default to Haiku ($1/M in, $5/M out) instead of Sonnet 5 ($3/$15), the same 59-turn session would have cost ~$2 instead of $11. But it's P3 because cost caps (P1) and tool limits (P2) provide protection regardless of model choice.

**Independent Test**: Send a message via the OpenAI-compat/N2N interface without an explicit model override. Verify it routes to the configured mobile-default model (e.g., haiku). Then send a message with an explicit "use sonnet" prefix and verify it upgrades.

**Acceptance Scenarios**:

1. **Given** `interface_defaults.mobile.model: "anthropic/claude-haiku-4-5"` configured, **When** a session arrives via the OpenAI-compat gateway (N2N/mobile), **Then** it uses Haiku unless the user explicitly requests a different model.
2. **Given** a mobile session using Haiku, **When** the user says "use sonnet for this" or equivalent escalation command, **Then** the model upgrades for that session only.
3. **Given** a TUI/desktop session, **When** no interface default is configured for that interface, **Then** it falls back to the agent's `model.primary` setting (existing behavior, no regression).
4. **Given** an explicit model override in the message, **Then** it always takes precedence over interface defaults.

---

### User Story 4 - Context growth awareness (Priority: P4)

As a NetClaw operator, I want the session to emit a warning (and optionally auto-summarize) when accumulated context size exceeds a threshold, so I'm aware that continued conversation will be expensive and can choose to start fresh.

**Why this priority**: This is a UX improvement that helps operators make informed decisions. The cost cap (P1) provides hard protection; this provides soft awareness before the cap is hit.

**Independent Test**: Configure `context_warning_tokens: 100000`. Have a multi-turn session that accumulates large tool results. Verify a warning is emitted when context crosses 100K tokens, showing the approximate cost-per-turn going forward.

**Acceptance Scenarios**:

1. **Given** `context_warning_tokens: 100000` configured, **When** cumulative session context exceeds 100K tokens, **Then** the agent emits an inline warning showing current context size and approximate cost-per-additional-turn.
2. **Given** the warning has been shown, **When** context doubles again (200K), **Then** a stronger warning suggests starting a new session or summarizing.
3. **Given** `context_auto_summarize: true` configured, **When** context exceeds the threshold, **Then** old tool results are summarized into a compact form before being re-sent as context.

---

### Edge Cases

- What happens when the cost cap is hit mid-sentence (during streaming)? → The current turn completes, but no further turns are initiated.
- What happens if the Prometheus metrics exporter is down and cost tracking fails? → SessionLedger is in-process (thread-safe Python); it doesn't depend on Prometheus. Enforcement works regardless of metrics export.
- What happens if multiple sessions run concurrently against the same API key? → Each session has its own SessionLedger instance. Budgets are per-session, not global (global daily caps are a future enhancement, not in scope here).
- What happens if the model price changes between config reload and enforcement? → The cost calculator re-reads pricing on each call; enforcement uses real-time cost, not stale values.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SessionLedger MUST expose an `is_over_budget()` method that returns True when `total_cost` exceeds the configured session ceiling.
- **FR-002**: The gateway's turn-dispatch loop MUST check `is_over_budget()` before sending a new request to the model API and halt gracefully if True.
- **FR-003**: A budget halt MUST produce a user-visible message including: accumulated cost, token counts, top tools by cost, and whether continuation is available.
- **FR-004**: SessionLedger MUST expose a `tool_calls_this_turn` counter that resets on each user message and is checked before each tool invocation.
- **FR-005**: Budget configuration MUST be expressible in `openclaw.json` under `agents.defaults` and overridable per-agent in `agents.list[]`.
- **FR-006**: Interface-based model routing MUST be configurable via a new `agents.defaults.interfaceDefaults` map keyed by interface type (e.g., `openai`, `tui`, `n2n`, `discord`).
- **FR-007**: Budget enforcement MUST emit a Prometheus counter (`netclaw_session_budget_trips_total`) with labels `{agent, reason}` where reason is `cost_cap` or `tool_limit`, consistent with the existing `netclaw_investigation_budget_trips_total` pattern.
- **FR-008**: The context warning system MUST calculate approximate tokens from the session message history without requiring an API call (use the existing `count_tokens` estimator).
- **FR-009**: Budget override/continuation MUST require an explicit user action (not automatic) — the agent must not silently resume spending.
- **FR-010**: All budget settings MUST have documented defaults that are safe for a hobbyist/personal deployment (e.g., $5 session cap, 20 tool calls per turn).

### Key Entities

- **BudgetPolicy**: Configuration object holding `session_budget_usd`, `max_tool_calls_per_turn`, `context_warning_tokens`, `context_auto_summarize`. Lives in `openclaw.json`.
- **SessionLedger** (existing): Extended with budget-checking methods and turn-level tool-call tracking.
- **InterfaceDefaults**: Map of interface type → model/thinkingLevel/budgetPolicy overrides.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A session that would previously accumulate >$5 in costs is halted at or below the configured ceiling (±10% tolerance for in-flight completion).
- **SC-002**: No session can execute more than `max_tool_calls_per_turn` tool calls without operator confirmation, default 20.
- **SC-003**: Mobile/N2N sessions default to a model costing ≤$1/M input tokens unless explicitly overridden.
- **SC-004**: The `netclaw_session_budget_trips_total` counter increments on every halt, enabling Prometheus-based alerting on runaway sessions.
- **SC-005**: Zero regression for existing alert-agent behavior — its existing budget enforcement (via alert-receiver) continues unchanged.
- **SC-006**: A repeat of the $11 incident scenario (7 phone questions, agentic tool chains) results in ≤$2 total cost with default settings.

## Assumptions

- The OpenClaw gateway's turn-dispatch loop is the correct enforcement point (it already calls the model API and receives responses).
- SessionLedger is instantiated per-session and persists for the session lifetime (confirmed by code review — it's a class instance, not a global singleton).
- The `openclaw.json` config is the appropriate place for budget settings (it already holds model config, agent definitions, and the tokenOptimization block).
- Prompt caching is already active and will continue to reduce costs for repeated context — budget enforcement accounts for actual cost (post-cache-discount), not theoretical worst-case.
- This feature is library-level (src/netclaw_tokens/) and configuration-level (openclaw.json schema) — it does not require changes to the OpenClaw gateway binary itself (enforcement hooks are called by the gateway's existing plugin/middleware system).
