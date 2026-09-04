# Loop Contract: 122-astra-live-digital-twin

**Read by**: `/speckit.implement`

**Purpose**: `/speckit.implement` for this feature MUST NOT implement the Astra Live Digital Twin
directly. It MUST generate the autonomous loop harness described here, then stop and report. The loop
— run separately, afterward, by a human deciding to start it — builds the feature.

## Why the implement step generates a loop instead of code

The feature is large, verifiable, and mechanically checkable — a good fit for a Ralph loop. A single
agent session cannot hold it: context fills, quality degrades past roughly 100–150k tokens, and
compaction loses exactly the details that make the twin accurate. The loop sidesteps this by never
letting context grow. Each iteration is a fresh process that reads state from disk, does one task,
commits, and exits. The repository is the memory. `loop/IMPLEMENTATION_PLAN.md`,
`loop/state/memory.md`, and this file are what persist.

Three failure modes get sharper the moment nobody is watching, and each has a countermeasure that is
mandatory here:

| Failure mode | Countermeasure |
|---|---|
| Unattended verification — the model grades its own homework | Maker/checker split. The checker is a separate process with its own fresh context and no access to the maker's reasoning. |
| Comprehension debt — the loop changes more than a human understands | One task per iteration, one commit per iteration, capped diff size, human-readable verdict ledger. |
| Cognitive surrender — accepting output because checking is effort | Every acceptance criterion in `spec.md` maps to named evidence in `loop/state/verdicts.md`. No criterion is ever marked satisfied by assertion. |

## Astra Twin — the identity behind this loop

This loop's maker and checker processes are not Claude. They run as **Astra Twin**, an OpenAI-backed
iN2N mesh member enrolled distinctly from the primary Claude-backed NetClaw agent (spec.md FR-006/
FR-007, research.md R1/R5). `loop/astra_agent.sh` is the concrete `AGENT_CMD` — it wraps `codex exec`
(OpenAI's Codex CLI, already installed on this host) and sources `OPENAI_API_KEY` from `.env`. Astra
Twin's involvement ends at the build: the delivered twin visualization has zero runtime dependency on
any AI provider (FR-011, SC-006) — Astra Twin builds and maintains it, it does not serve it.

## What `/speckit.implement` must generate

```text
loop/
  ralph.sh                 driver: iterate, maker -> gates -> checker, commit, halt
  astra_agent.sh            AGENT_CMD wrapper: codex exec --full-auto, sources OPENAI_API_KEY
  PROMPT.md                 maker prompt — identical every iteration
  CHECK.md                  checker prompt — identical every iteration
  IMPLEMENTATION_PLAN.md    derived from tasks.md; the maker's work queue, ordered by the Pass
                            Schedule in plan.md (Phase A -> B -> C -> D)
  state/
    iterations.md           one line per iteration: task, verdict, commit, duration
    verdicts.md              criterion -> evidence ledger, checker-written only
    debt.md                  things deliberately deferred, with reasons
    memory.md                durable findings across iterations (gotchas, decisions)
  runs/<iteration>/          logs, diffs, screenshots, gate output
```

It must also generate the frozen back-pressure harness from plan.md (`mcp-servers/astra-twin-mcp/`,
`models/twin_schema.py`, `harness/`, `tests/contract/`) before the first iteration runs. A loop with
no back pressure is 30 chances to make things worse.

Then it stops. It does not run `ralph.sh`.

## Iteration protocol

One iteration is: select -> make -> gate -> check -> record -> exit.

1. **Select.** Maker reads `loop/IMPLEMENTATION_PLAN.md` and picks the single highest-priority
   unblocked task, respecting the Pass Schedule's phase order from plan.md. Not two. Failed-gate items
   and checker-rejected items sort above new work.
2. **Make.** Maker implements that one task only. Diff cap applies. Frozen paths are rejected at apply
   time.
3. **Gate.** `ralph.sh` runs the automated back pressure — build, contract tests, console-error check,
   `harness/visual_verify.py` screenshot and non-blank check, element-count assertions. Deterministic,
   no model involved.
4. **Check.** A separate fresh `codex exec` process runs `CHECK.md`. It grades the iteration against
   spec.md's acceptance criteria at the primary source — it reads the artifacts and the gate output,
   never the maker's transcript. It writes `verdicts.md`. It may reject.
5. **Record.** Commit on pass, revert on reject. Append to `iterations.md`. Rejected work returns to
   the plan as a prioritized task with the checker's reason attached.
6. **Exit.** Process terminates. Context is discarded. Next iteration starts clean.

## Stop conditions

`max_iterations = 30` is a budget ceiling, not a target. The loop is a recursive goal, not a
fixed-length for-loop. It exits on whichever comes first:

- **Done** — every blocking acceptance criterion in spec.md has evidence in `verdicts.md` and the
  integrated done-gate (`harness/done_gate.sh`) passes. This is the only success exit.
- **Budget** — 30 iterations consumed. Exits with the work incomplete and says so plainly.
- **Stall** — three consecutive iterations produce no net progress (no commit, or the same task
  rejected three times). The task is written to `debt.md` and the loop halts for human input rather
  than grinding.
- **Breach** — any attempt to write a frozen path, exceed the diff cap repeatedly, or touch a device
  outside the lab testbed. Immediate halt.

## Safety envelope — read this before running

This repository is not an ordinary codebase to point an unattended loop at. It carries live pyATS
credentials, roughly forty MCP servers, and skills that can configure production network devices. A
loop running with permission prompts disabled has every one of those in reach.

Non-negotiable preconditions, enforced by `ralph.sh` at startup:

- Runs in a dedicated git worktree, never the primary checkout.
- `PYATS_TESTBED` points at a CML lab testbed only. Startup aborts if the resolved testbed contains
  any device not in the lab allowlist.
- Production credentials absent from the loop's environment — not merely unused.
- Config-write MCP servers disabled for the duration. The twin is read-only by design (FR-003, spec
  Out of Scope); the loop has no reason to hold write capability.
- Frozen paths checked out read-only and enforced again at patch-apply time.
- Every iteration commits. An unattended run with no commit trail is unreviewable.

## Human checkpoints

Autonomy is the point, but review is the job. The loop pauses for a human at:

- After iteration 0 — baseline scored, harness self-tested against injected regressions (quickstart.md
  Phase B checkpoint). Confirm the gates actually catch things before letting 29 more iterations trust
  them.
- End of each schedule phase (plan.md's Pass Schedule) — read `verdicts.md` and `debt.md`, not the
  code. If a human cannot say what changed, that is comprehension debt and it is the signal to slow
  down.
- Any stall halt.

## Explicit non-goals of the loop

- Drafting the WordPress milestone blog post (constitution Principle XVII) — human-judgment writing,
  kept out of the loop deliberately (plan.md's Constitution Check). Left for the primary agent once
  the loop reports done.
- Anything touching a device outside the lab testbed, under any framing.
- Modifying `models/twin_schema.py`, `mcp-servers/astra-twin-mcp/`, `harness/`, or `tests/contract/`
  once Phase A/B have written them.

## Notes on prior art

This is the Ralph pattern (Geoffrey Huntley, July 2025) with a Spec Kit front end and an explicit
maker/checker split, run under the identity of a distinct, OpenAI-backed iN2N mesh member rather than
the primary Claude-backed agent. The generated harness should stay recognizably simple — a while loop,
a prompt file, and a checker. The value is in the back pressure and the ledger, not in the orchestrator
being clever.
