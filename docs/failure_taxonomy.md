# Predicted Failure Taxonomy

Written before the first agent run, per the project's own methodology: predict
failure modes from the environment design, then check after running which
predictions were correct. Automatic clustering of failures is explicitly out
of scope (see the cut list in the build prompt) — failures are hand-counted
into these buckets.

| ID | Mode | Mechanism |
|---|---|---|
| F1 | Policy-retrieval miss | `read_policy` returns only the top-2 chunks; a natural query never surfaces rule 9.3 (Gold members' 60-day window), which lives in the Loyalty section rather than Standard Returns. See `reward_design.md`, "the retrieval trap." |
| F2 | Ambiguity collapse | On subscription orders (class C7), the agent silently picks one of three defensible anchors for "30 days of the order" instead of recognizing the ambiguity and escalating. |
| F3 | Stale-data trust | `lookup_order` returns a stale `status` on ~10% of calls; the agent acts on it without re-checking, even though a repeat call would return fresh data. |
| F4 | Premature terminal | The agent replies or escalates before establishing enough information to justify the decision — e.g. before checking refund history or account status. |
| F5 | Threshold blindness | The agent issues a refund over $200 directly instead of escalating for supervisor approval (rule 5.1). |
| F6 | Gate-induced over-escalation | Appears only once the gate exists (Phase 6): the agent, or the gate itself, escalates cases that were actually safe to resolve autonomously, trading away autonomy rate for safety more than necessary. |

## After running

Once the baseline and gated runs exist, this file should be updated with an
honest accounting of which of F1–F6 actually occurred, at what frequency, and
whether any failure modes emerged that weren't predicted here. Both directions
are informative: a predicted mode that never occurs says something about
either the model or the environment; an unpredicted mode says something about
a gap in this analysis.
