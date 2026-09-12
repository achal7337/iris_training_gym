# Step Label Guideline (v1)

Used by the human annotator (Review page) and by the LLM judge. A label is
applied to a single agent action (one step of a trajectory), not to the
trajectory as a whole.

## The six labels

Mutually exclusive — exactly one label per step.

| Label | Definition |
|---|---|
| `correct` | Advances toward correct resolution and is justified by information available at that point |
| `unnecessary` | Not wrong, but redundant or irrelevant given what is already known |
| `wrong_harmless` | Incorrect but recoverable — wrong query or lookup, no state change |
| `policy_violating` | Violates a named rule, or executes an irreversible action without establishing eligibility |
| `hallucinated_fact` | The reasoning asserts a fact present in no tool return |
| `premature_terminal` | Terminates before establishing enough to decide |

## Auxiliary fields

- `policy_rule` — nullable; the specific rule (e.g. `5.1`) the label is anchored to, when applicable
- `reason` — required, one sentence, plain language

## Precedence

When more than one label could apply to the same step, use the highest-priority
one in this order:

```
policy_violating > hallucinated_fact > premature_terminal > wrong_harmless > unnecessary > correct
```

## Three edge cases (must be applied consistently)

1. **Luck does not upgrade a label.** An `unnecessary` `read_policy` call that
   happens to surface the rule which ends up saving the trajectory is still
   labeled `unnecessary`. Labels describe the quality of the decision at the
   time it was made, not the outcome it happened to produce.

2. **Right amount, wrong order, still a violation.** An `issue_refund` call
   that is coincidentally for the correct amount, but was issued *before*
   eligibility was established (e.g. before checking account status or
   refund history), is `policy_violating` — not `correct`. Correctness
   requires the justification to exist at the time of the action, not just
   the final number to happen to match.

3. **A retry after a transient failure is not redundant.** A retry
   immediately following a `TIMEOUT` tool result is `correct`, not
   `unnecessary` — it's the expected recovery behavior for a transient
   failure, not a wasted or repeated step.

## Annotation targets

- ~70 human step labels total: **8 anchors** (used as few-shot examples in
  the judge's v1 prompt) + **~62 agreement-set labels** (never shown to the
  judge in any prompt, used only to measure judge agreement).
- The anchor/agreement split is enforced in code and asserted in a test — see
  `NON-NEGOTIABLE 2` in the build prompt. Measuring judge agreement on labels
  the judge's prompt already contains is circular and invalidates the number.
