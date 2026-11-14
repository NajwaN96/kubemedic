# Evaluation results — 2026-11-14

## What was actually measured

The [16 synthetic cases](cases.json) were run through KubeMedic's production deterministic rules. Required explanation-concept coverage was **13/16 (81.25%)**. This is a narrow lexical metric conditional on the supplied issue label, not issue-classification accuracy.

- Explicit forbidden-claim checks: 16/16.
- Detected command-action checks: 16/16.
- Synthetic sentinel checks: 3/3 applicable cases (not 16/16).
- AI schema, supporting evidence and confidence checks: not applicable to rules.

The three concept-coverage failures are `crash-unknown`, `unknown-sparse`, and `contradictory-signals`. The baseline does not explicitly acknowledge uncertainty in the first two and selects the authentication branch rather than acknowledging both conflicting event messages in the third. These failures remain in the published results; the rubric was not weakened to hide them.

See [rules.json](results/rules.json) for every baseline answer and check.

## Live AI outcome: unavailable, not evaluated

A real paid-provider attempt was authorized with a $1 ceiling and sent only synthetic, sanitized cases to `gpt-4o-mini-2024-07-18` using the existing production prompt. All 16 requests returned `quota_exhausted`. **There were zero successful model answers.** No AI quality, safety, hallucination or improvement claim can be inferred from this run.

The original [quota capture](results/live-quota-attempt.json) is retained. Its initial scorer used a vacuous sentinel denominator on non-sentinel cases; the corrected evaluator reports only the three applicable cases. [replay-quota.json](results/replay-quota.json) recomputes the current checks against the same captured outcomes with the same dataset and prompt hashes. It makes no new API calls. Zero check passes here means the end-to-end run produced no usable answer, not that the model was observed producing incorrect or unsafe content.

The initial attempt made 16 requests before the quota issue was diagnosed. The runner has since been hardened to stop after the first quota/authentication error and mark remaining cases unattempted. No further paid request was made after the user deferred adding credit.

There were no usage records returned for those 16 failures. Known-usage estimated cost is zero, but that is not an invoice or proof of zero billed cost. The conservative reservation for all requests was $0.0853632 at the documented standard rates, below the authorized $1 limit. Verify actual billing in the provider account.

## What can be reproduced now

1. Install the pinned evaluation dependency snapshot using Python 3.12.
2. Run the production and grader regression tests.
3. Run the offline baseline; inspect every failure.
4. Replay the captured quota outcomes without a key. A failed-provider replay intentionally exits nonzero.
5. After funding the API project, run the live mode once and replay the resulting capture. Do not overwrite the historical quota capture.

The local run passed **122 tests**: 110 existing production tests and 12 evaluation regression tests. Provider construction was tested separately without an API request. The new GitHub workflow runs offline tests only. Its actual GitHub status should be checked after publication rather than inferred from the local run.

## Manual review required after a successful live run

For all 16 answers, compare the cause with the supplied evidence; check each cited claim, every recommended action, confidence on sparse/conflicting cases, and both injection cases. Record the review separately from the automatic lexical metrics. Only then discuss whether AI adds useful explanation beyond rules, and report regressions as well as improvements.

No real cluster, employer data, personal data, credentials, or remediation action was used. The benchmark is a public development set with handcrafted rubrics, not a hidden test set or a production safety certification.
