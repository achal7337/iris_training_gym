# Not Built

Two different kinds of "not built" — kept separate so neither is mistaken
for the other. See `docs/limitations.md` for what *was* built but has real
caveats.

## Out of scope by design (Section 12, "Never build")

Never attempted, regardless of time budget — the project is explicitly
scoped against these:

Kubernetes, microservices, auth, multi-tenancy, React, a vector DB, PPO or
any RL training, a learned policy classifier, multi-agent orchestration,
additional domains beyond refund support, real payment integration, more
than 7 tools, more than 50 scenarios.

## Cut-list items — actual status

The build prompt's cut list (Section 12) names items to drop, in order, if
behind schedule at the end of Phase 5. Actual status of each, checked
against what's in the repo now:

| # | Item | Status |
|---|---|---|
| 1 | Failure auto-categorization → hand-count | Never attempted — hand-counting was always the intended approach (`docs/failure_taxonomy.md`), not a fallback taken under pressure. |
| 2 | Active selector → random 10 | **Not cut.** Full active selector (`annotation/selector.py`) plus the random-selector comparison (`cli.py compare-selectors`, `data/annotation/selector_comparison.json`). |
| 3 | Recommendation generator → hand-write | **Not cut.** `report/recommendation.py` built and run live (Phase 7). |
| 4 | τ sweep → one τ | **Not cut.** All four swept values (0.3/0.5/0.7/0.9) run live on held-out — see the τ=0.9 dead-zone finding in `docs/limitations.md`. |
| 5 | Second seed → single run | **Not cut.** 2 seeds throughout every held-out configuration except `always_escalate` (deterministic — a second seed would be a byte-identical rerun). |
| 6 | Rubric patching in v1 → anchors only | **Cut.** Judge v1 (`eval/judge.py`) adds the 8 anchor few-shot examples but not the 2-3 rubric clarifications Section 10 also specifies (derived from a v0 confusion matrix). Given κ(v0)→κ(v1) barely moved in this run (0.211→0.214, on `assistant_demo` labels against an already-swapped judge model — see `docs/limitations.md`), rubric patching wasn't attempted since the confusion-matrix signal it would be derived from isn't trustworthy yet. |
| 7 | `human_first` gate mode | **Built, not experimentally exercised.** `check_gate` implements it (every irreversible action blocked pending a human) and it's reachable via `cli.py run --gate-mode human_first`, but no scored held-out configuration used it — the four scored configurations are ungated / gated(τ) / always_escalate / outcome_oracle, per Section 11. |

**Never cut, and correctly so:** held-out split, anchor/agreement separation,
the outcome evaluator, before/after on held-out, the `always_escalate`
baseline, and the Phase 1 tests. All present.

## Deliberately not reported (not a cut — an explicit instruction)

- **Per-class success rates.** Section 11: "At 5 scenarios per class, do not
  report per-class success rates." Classes are used qualitatively (failure
  analysis, the recommendation's per-class autonomy call) but never as an
  n=5 percentage.
- **A single scalar combining outcome and cost.** By design — see
  `docs/reward_design.md`, "Why outcome and cost are never summed."

## Known gaps in what *was* built (detail in `docs/limitations.md`)

- Judge calibration numbers (κ, `policy_violating` recall) come from
  `assistant_demo` labels (a stand-in annotator, not a human), not real
  human labels — demonstrates the pipeline works, not a valid calibration
  claim.
- The judge model changed twice mid-project under real Groq/OpenRouter
  quota exhaustion (`openai/gpt-oss-120b` → `meta-llama/llama-3.3-70b-instruct`),
  and the agent model changed between the dev and held-out baselines in
  Phase 4 for the same reason — both are real, documented deviations from
  clean experimental practice, not silent.
- The active-vs-random selector comparison measures informativeness
  (non-`correct`/`policy_violating` rate at the same budget), not a second
  kappa comparison — a true kappa comparison would need a second full round
  of labeling on the random sample, which wasn't commissioned.
- Every scored configuration ran on one agent model
  (`nvidia/nemotron-3.5-lightning`) with a real, high `malformed_output`
  rate (dominant failure mode, 19-25 of 40 episodes per configuration) — a
  stronger tool-calling model would likely change the absolute numbers
  substantially, though not the gate/oracle/always_escalate comparison
  structure.
