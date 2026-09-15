# Trajectory Gym

**Can this AI agent safely automate our customer-support refund workflow, and
where does it still need a human?**

A small, self-contained evaluation harness for that question: a simulated
refund-support environment (7 tools, a seeded world of customers/orders,
deliberate policy defects), an LLM agent, an LLM judge calibrated against
real (if imperfect, see below) human-style labels, a pre-execution safety
gate, and a τ-sweep experiment comparing gated vs. ungated vs. a degenerate
`always_escalate` baseline vs. a zero-annotation rule-engine oracle.

Built to a phase-gated spec (`prompt.md`) with six non-negotiables that
survive any time pressure: a frozen held-out split, anchor/agreement
separation for judge calibration, a deterministic rule-based outcome
evaluator (never an LLM), full agent isolation from ground truth, outcome
and cost reported separately (never summed into one score), and
deterministic replay (fixed seed + fixed "today").

## Quick start

```bash
pip install -e ".[dev]"
make test    # 154 tests, mock provider, zero network, zero cost
make demo    # ~40s, no API key needed; see "The demo" below
make app     # Streamlit: Run / Trajectory / Review / Report pages
```

Nothing above needs an API key. Every LLM role in `config/models.yaml`
defaults to `provider: mock`; `make demo` and the committed
`data/llm_cache.sqlite3` replay real, previously-recorded responses instead.

To run against a real provider, copy `.env.example` to `.env`, fill in a key,
and point the relevant role(s) in `config/models.yaml` at a real provider
(see the comments in that file for the model history and why each swap
happened), or just run `make demo ARGS=--live`, which sends one genuine
network call to prove the pipeline can talk to a real provider, then
finishes the rest of the demo from cache.

## The demo

`cli.py demo` (Section 14 of `prompt.md`) actually executes the agent loop,
the gate, and the judge; it is not a script printing pre-written numbers.
By default every LLM call replays from the committed cache, so it needs no
API key, no network, and finishes in well under a minute (rehearsed three
times: 37s / 45s / 49s, against a 3:15 budget). It:

1. Runs all 20 held-out scenarios ungated, showing the real pass rate and
   policy violations.
2. Reports real judge-calibration numbers from a completed grading pass.
3. Re-runs the same 20 scenarios with the gate on: violations drop,
   contrasted against the `always_escalate` baseline's zero-violations,
   zero-autonomy degeneracy.
4. Opens one real gate block found live in that run and prints the judge's
   actual reasoning.
5. Generates the customer recommendation live, LLM-filled from the real
   scoreboard.

## Key results (held-out, live models, 2 seeds; see `docs/limitations.md`)

| Configuration | Violations | Human touches | Task success |
|---|---|---|---|
| Ungated | 5 | 2 | 0.194 |
| Gated (τ=0.5) | **0** | 3 | 0.194 |
| Outcome-oracle (rule engine, zero LLM cost) | **0** | 3 | 0.278 |
| `always_escalate` | 0 | 20/20 | 0.333 (degenerate, 0% autonomy) |

Gating eliminates every observed held-out violation at the cost of one
extra human touch per 40 tickets. The τ sweep (0.3/0.5/0.7/0.9) surfaced a
real, reproducible finding: this judge's confidence output is quantized to
exactly 0.90, so τ=0.9 is a dead zone where the gate blocks nothing. Full
numbers, the τ-sweep table, hand-counted failure modes (including a
verbatim judge arithmetic error), and an honest accounting of what's
confounded in this run (judge model swapped mid-project, `assistant_demo`
labels standing in for human ones, a dominant agent-model formatting-failure
rate) are all in `docs/limitations.md`.

## Repository layout

```
config/            models.yaml (role -> provider/model), env.yaml, gate.yaml
src/trajectory_gym/
  llm/             complete(messages, role); providers; sqlite response cache
  models/          Pydantic schemas: Scenario, Trajectory, StepLabel, ...
  data/            world generation, 10 scenario classes, rule engine
                    (THE outcome evaluator), ticket prose writer, split
  env/             DB schema/seed/reset, the 7 tools, the episode step loop
  agent/           the LLM agent, and the always_escalate baseline
  eval/            outcome scoring, judge (v0/v1), calibration, gate, metrics
  annotation/      label taxonomy, active selector, label store
  report/          the recommendation generator
  cli.py           generate | run | select | calibrate | compare-selectors |
                    grade | demo
app/streamlit_app.py   Run / Trajectory / Review / Report pages
data/policy/       the refund policy (with deliberate, documented defects)
data/runs/         trajectory/outcome logs, mostly gitignored; the 7
                    directories backing the numbers above are committed
docs/              reward_design, failure_taxonomy, limitations, not_built
tests/             offline, mock-only, zero cost
```

## Documentation map

- **`prompt.md`**: the full build spec this project was built against.
- **`docs/reward_design.md`**: the policy document's deliberate defects
  (an ambiguity, a cross-section inconsistency, a retrieval trap) and why
  outcome and cost are never combined into one score.
- **`docs/failure_taxonomy.md`**: the predicted failure modes, written
  before the first run, with an honest after-the-fact accounting.
- **`docs/limitations.md`**: a running, dated log of every real limitation
  hit while building this: model swaps under quota pressure, AI-assistant
  labels standing in for human ones, the τ=0.9 dead zone, and more.
- **`docs/not_built.md`**: what's explicitly out of scope, what was cut
  vs. not cut from the spec's cut list, and what's deliberately not
  reported (e.g. no per-class success rates at n=5).
