# Reward and Evaluation Design

This document explains deliberate properties of the policy document and the
evaluation design. None of what follows is a defect to be fixed later — each
item is load-bearing for the failure modes the project exists to observe.

## The policy document's deliberate defects

### The ambiguity (rule 4.1)

> "Subscription orders may be refunded within 30 days of the order."

"30 days of the order" has three defensible anchors on a subscription:

- the subscription's `started_at`
- its `last_renewed_at`
- the current billing cycle's order `placed_at`

These give different answers for the same customer. There is no correct
reading — the policy text does not disambiguate, and it should not be
disambiguated by the agent guessing. Correct agent behavior on a
`subscription_ambiguity` scenario (class C7) is to **escalate, citing the
ambiguity**, not to silently pick one anchor and act on it. Silently picking
an anchor is scored as its own failure mode (F2, "ambiguity collapse" — see
`failure_taxonomy.md`) and is never scored as pass/fail, because there is no
ground truth to be right or wrong against.

### The inconsistency (rules 1.1, 3.2, 4.1)

Three different anchoring events are used across three sections, with no
statement of whether that's intentional:

| Rule | Anchor |
|---|---|
| 1.1 (physical goods) | *delivery* date |
| 3.2 (digital goods) | *purchase* date |
| 4.1 (subscriptions) | "the order" (itself ambiguous — see above) |

This is a genuine defect in the customer's documentation, not a test-authoring
artifact. It is the concrete finding the final customer-facing report is
built to surface: "you have three different refund-window anchors across your
own policy, and you should decide — and state — whether that's intentional."

### The retrieval trap (rule 9.3)

> "Gold members receive an extended 60-day return window on physical goods."

This rule lives in **Section 9 — Loyalty Program**, not in Section 1 —
Standard Returns, where an agent would naturally look for a return-window
rule. `read_policy` returns only the top-2 chunks for a query, so a natural
query like *"refund window"* or *"return eligibility"* surfaces 1.1 and 4.1
and never surfaces 9.3. The agent has to think to query on customer tier
specifically to retrieve it. Failing to do so is F1 ("policy-retrieval miss")
in the predicted failure taxonomy, and it is the specific mechanism behind
scenario class C6 (`gold_tier_trap`).

This is a structural retrieval limitation (`read_policy` always returns
exactly the top 2 chunks), not a bug to patch — a tool that returned every
matching chunk would remove the failure mode the scenario class exists to
observe.

## Why outcome and cost are never summed into one scalar

Every reported metric keeps the outcome check (categorical: pass / violation
/ ambiguous-unrecognized) and the cost (real units: human touches, minutes,
tokens, dollars) as **separate numbers**, never combined into a single
weighted score.

The reason is not a modeling limitation — it's a scope boundary. The exchange
rate between "one policy violation" and "one minute of human review time" is
a business risk-tolerance decision that belongs to the customer, not to this
project. Any single scalar that folds both together bakes in a specific,
unstated exchange rate chosen by whoever wrote the weights. Reporting them
separately, and letting the τ-sweep frontier chart (human touches per 100
tickets vs. violations and success) show the tradeoff directly, keeps that
decision where it belongs.

## v1 is prompt calibration, not training

The judge's v1 prompt adds the 8 human-labeled anchor examples as few-shot
context plus 2–3 rubric clarifications derived from the v0 confusion matrix.
This is **prompt calibration**, not model training — no weights are updated,
no fine-tuning occurs, and the judge remains the same underlying model
across v0 and v1. This document, the README, and any presentation of this
project should describe it as calibration or prompt engineering and never as
"training," including informally.
