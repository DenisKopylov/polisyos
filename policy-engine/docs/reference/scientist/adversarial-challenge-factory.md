# Scientist Adversarial Challenge Factory

Related references: [Scientist](index.md), [Benchmark authority](benchmark-authority.md), [Reflexive memory](reflexive-memory.md), [VOI scheduler](voi-scheduler.md), [Wave 2 runtime contracts](wave2-runtime-contracts.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/evals/challenge_factory.py`, `src/polisyos/scientist/evals/sentinels.py`, `src/polisyos/scientist/evals/red_team.py`, `src/polisyos/scientist/evals/rotation.py`, `src/polisyos/scientist/evals/challenge_packs.py`, `src/polisyos/scientist/evals/authority.py`, `tests/unit/scientist/evals/test_challenge_factory.py`, `tests/unit/scientist/evals/test_sentinels.py`, `tests/unit/scientist/evals/test_red_team.py`, `tests/unit/scientist/evals/test_rotation.py`, and `tools/ci/check_scientist_best_in_class_phase2_5.py`.

Phase 2.5 turns observed failures and near misses into controlled challenge
candidate packs. It is a shadow/read-only factory by default: generation is not
benchmark admission, and generated cases are not hidden evals until review and
Benchmark authority registration agree.

## Runtime Contract

| Surface | Contract |
| --- | --- |
| Challenge generation | `GeneratedChallenge`, `ChallengeSeed` and `ChallengeFactoryReport` capture candidate challenge class, source failure refs, near-miss or policy-domain risk seeds, prompt/case ref, expected failure mode, leakage risk, reviewer refs and lineage key. |
| Challenge mutation | `mutate_generated_challenge(...)` creates a new `review_required` child challenge, preserves parent lineage metadata and resets reviewer refs so every mutation is reviewed independently. |
| Review-before-hidden | `ChallengeStatus.APPROVED_FOR_HIDDEN` requires `reviewer_refs` and blocks high leakage risk. `register_challenge_pack_with_benchmark_registry(...)` accepts reviewed public/private packs but rejects hidden registration unless every challenge is reviewed for hidden admission. |
| Sentinel admission | `SentinelChallengeCase` records canary, invariant, decoy and regression sentinel metadata; hidden sentinel admission requires reviewer refs and cannot be high leakage. |
| Red-team registry | `default_red_team_scenario_registry()` covers every required challenge class with risk tags for citation, staleness, causal, fairness, legal, strategic-response, budget and human-oversight review. |
| Rotation lifecycle | `ChallengePackLineage` tracks pack id, source challenge ids, source failure refs, parent packs, revision, expiry and lineage key. `validate_fresh_rotating_challenge_evidence(...)` blocks near-frontier promotion when no fresh rotating challenge evidence exists. |
| Authority integration | `BenchmarkAuthorityVerdict.challenge_pack_lineage` exposes lineage summaries from `BenchmarkRegistry` metadata. Public exports include lineage summaries but not hidden answers. |

## Challenge Classes

Phase 2.5 recognizes these required classes:

- `source_contradiction`
- `stale_source`
- `forged_citation`
- `missing_transportability_assumption`
- `hidden_confounding_proxy_assumption_trap`
- `fairness_threshold_reversal`
- `legal_exception`
- `policy_gaming_strategic_response`
- `budget_infeasibility`
- `ambiguous_human_review_instruction`

`challenge_class_for_failure_card(...)` maps existing `TypedFailureCard`
signals into this taxonomy. `ChallengeSeed` covers near-miss and
policy-domain risk generation when the input is not a failure card. Unknown failures default to
`source_contradiction` so the case remains reviewable instead of silently
disappearing.

## Review-Before-Hidden

review-before-hidden is mandatory:

- generated challenges start as `review_required`;
- public, private, rotating, sentinel or adversarial benchmark registration
  requires reviewer refs;
- private benchmark registration accepts `approved_for_private` or stronger;
- hidden benchmark registration requires `approved_for_hidden`;
- high-leakage generated challenges cannot be admitted as hidden;
- generated-but-unreviewed cases remain outside hidden eval packs and reusable
  memory.

This preserves the Phase 1.5 rule that `BenchmarkRegistry` and
`BenchmarkAuthority` are the promotion authority. The factory proposes cases;
it does not self-certify scientific validity.

## Leakage Rules

Public exports use `export_public_challenge_factory_report(...)` and scan the
full report payload for hidden artifact ids, hidden suite ids and canary tokens
before returning a compact ref-free summary. A challenge containing a hidden
answer or canary is rejected from public export.

Failure cards with private data cannot generate public challenge content.
Private or hidden candidate material can remain internal, but it must not enter
public docs, public reports or reusable memory.

## Benchmark Authority Lineage

Approved packs register lineage metadata under
`metadata.challenge_pack_lineage` in `BenchmarkRegistry`. The lineage summary
contains source challenge ids, source failure ref ids, challenge classes,
reviewer ref ids and a stable lineage key.

Near-frontier promotion can request fresh rotating challenge evidence through
`PromotionEvidenceRequest(near_frontier=True)` or
`require_fresh_rotating_challenge=True`. The authority then blocks if no fresh
rotating lineage exists, or if the rotating lineage is expired or retired.

## Feature Flags

| Flag | Default posture |
| --- | --- |
| `scientist.best_in_class.wave2.phase2_5.challenge_factory` | shadow |
| `scientist.best_in_class.wave2.phase2_5.require_fresh_rotating_challenge` | off except explicit near-frontier checks |

## Rollout

1. Generate candidate reports in shadow mode from failure cards.
2. Promote reviewed public/private packs first.
3. Register approved packs with `BenchmarkRegistry`.
4. Require fresh rotating challenge evidence only for near-frontier promotion.
5. Keep generated-but-unreviewed cases out of reusable memory.

## Validation

```bash
uv run pytest tests/unit/scientist/evals/test_challenge_factory.py tests/unit/scientist/evals/test_sentinels.py tests/unit/scientist/evals/test_red_team.py tests/unit/scientist/evals/test_rotation.py -q
uv run python tools/ci/check_scientist_best_in_class_phase2_5.py --repo-root . --output-format json --require-passing
```
