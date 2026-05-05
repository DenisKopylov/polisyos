# Scientist VOI Scheduler

Related references: [Claim Ledger](claim-ledger.md), [Deep research evidence](deep-research-evidence.md), [Benchmark authority](benchmark-authority.md), [Human oversight](human-oversight.md), [Wave 2 runtime contracts](wave2-runtime-contracts.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/search/voi_models.py`, `src/polisyos/scientist/search/voi_scheduler.py`, `src/polisyos/scientist/search/voi_calibration.py`, `src/polisyos/scientist/evidence/claim_support.py`, `src/polisyos/scientist/human_review/voi_escalation.py`, `tests/unit/scientist/search/test_voi_models.py`, `tests/unit/scientist/search/test_voi_reports.py`, `tests/unit/scientist/search/test_voi_calibration.py`, `tests/unit/scientist/evidence/test_claim_support_voi.py`, `tests/unit/scientist/human_review/test_voi_escalation.py`, and `tools/ci/check_scientist_best_in_class_phase2_3.py`.

The VOI scheduler explains why Scientist spends or does not spend compute. It
can prioritize candidate evaluation, source verification, human escalation,
adversarial challenge and stop-search decisions, but it cannot waive required
evidence or release gates.

## Contracts

| Contract | Module | Role |
| --- | --- | --- |
| `VOIDecisionType` | `search/voi_models.py` | Candidate evaluation, source verification, human escalation, adversarial challenge and stop-search decision families. |
| `VOIDecisionRecord` | `search/voi_models.py` | Per-decision expected value, expected cost, risk reduction, explanation, mandatory gate policy and input refs. |
| `VOIRunReport` | `search/voi_models.py` | Persisted run-level VOI report with decision records, total expected cost, calibration status and optional shadow baseline ref. |
| `build_stop_search_voi_decision` | `search/voi_scheduler.py` | Stop/continue decision helper when marginal expected improvement falls below compute plus safety cost. |
| `build_adversarial_challenge_voi_decision` | `search/voi_scheduler.py` | Challenge-run helper for near-promotion or high-impact candidates. |
| `VOIShadowBaselineComparison` | `search/voi_calibration.py` | Static-vs-VOI cost/safety/regret comparison for shadow rollout. |
| `VOICalibrationReport` | `search/voi_calibration.py` | Default-enable guard for calibrated VOI use. |

## Compute Law

- Spend compute when expected value and expected risk reduction exceed compute
  plus review cost.
- Defer, reject or `stop_search` when expected value is negative.
- Prefer source verification for unsupported, weakly supported, contested or
  counterevidence-heavy claims.
- Escalate to humans when reversal risk and harm justify review, and always
  escalate when human review is required by policy.
- Keep learned/shadow VOI out of default paths until calibration and regret refs
  exist.

## Mandatory Gates

VOI cannot waive:

- benchmark authority evidence;
- hidden holdout or sentinel evidence required for promotion;
- required human review for high-risk/public-sector publication;
- governance publication blocks;
- Claim Ledger evidence, counterevidence and publishability gates;
- Research DAG replay/audit lineage requirements where required by later
  release phases.

If a `VOIDecisionRecord` names `mandatory_gate_overrides`, the only allowed
actions are `defer`, `reject`, `stop_search`, `request_human_review`,
`run_required_gate` or `blocked_by_mandatory_gate`.

## Reports And Persistence

`persist_voi_run_report(...)` stores `VOIRunReport` as
`scientist.voi_run_report` with lineage inputs from decision refs and shadow
baseline refs. Major policy-runtime runs persist a `voi_run_report_ref` sidecar
in `artifacts_index`, and decision packets render it as `voi_report_ref` plus a
compact `voi` summary. Major runs should keep VOI reports in shadow mode first,
then compare them with static scheduling before advisory rollout.

## Human Escalation

`build_human_escalation_voi_decision(...)` emits an auditable
`human_escalation` decision. Human escalation remains overrideable by reviewers,
but required human review cannot be suppressed by negative VOI.

## Calibration And Regret

`compare_voi_to_static_baseline(...)` records:

```text
static_expected_cost
voi_expected_cost
static_safety_score
voi_safety_score
regret
non_worse_safety
cost_targeting_improved
```

`validate_voi_default_enable(...)` fails closed without calibration and regret
refs for learned/shadow VOI.

## Feature Flags

```text
scientist.best_in_class.wave2.phase2_3.voi_reports
scientist.best_in_class.wave2.phase2_3.voi_scheduler_shadow
scientist.best_in_class.wave2.phase2_3.voi_scheduler_default
```

Default rollout is report-only shadow mode.

## Validation

```bash
uv run pytest tests/unit/scientist/search/test_voi_models.py tests/unit/scientist/search/test_voi_reports.py tests/unit/scientist/search/test_voi_calibration.py tests/unit/scientist/evidence/test_claim_support_voi.py tests/unit/scientist/human_review/test_voi_escalation.py -q
uv run python tools/ci/check_scientist_best_in_class_phase2_3.py --repo-root . --output-format json --require-passing
```
