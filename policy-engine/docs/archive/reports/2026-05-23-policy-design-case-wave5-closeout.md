# Policy Design Case Wave 5 Closeout

Date: 2026-05-23
Wave: Wave 5 - External Surfaces, Evaluation, Calibration, And Memory
Status: closed
Owner: `team-runtime-quality`

## Status

Wave 5 is closed through the I5 external consumer truth manifest:

```text
architecture/policy_design_case/wave5_i5_external_consumer_truth_manifest.json
```

The accepted capability states are recorded in:

```text
architecture/policy_design_case/capability_reality_report.json
```

## Pattern Pass

Relevant patterns: `P03`, `P05`, `P06`, `P07`, `P09`, `P10`, `P11`, `P13`,
`P14`, and `P15`.

Existing anti-pattern found: Wave 5 behavior had runtime, dashboard, fixture,
calibration, memory, and operator-doc evidence, but the capability ratchet did
not yet close W5.A, W5.C, W5.D, W5.E, or I5 as full producer-to-consumer
chains. That left a P01/P03/P10 gap: implemented behavior could remain hidden
from the durable release-readiness surface.

Target correct pattern: external surfaces expose Wave 4 closeout truth,
semantic packs test content-level failure, calibration and memory remain future
influence only, and operator docs route to repo-owned evidence without becoming
runtime authority.

Closed capability labels: W5.A, W5.B, W5.C, W5.D, W5.E, and I5 are recorded as
`implemented` in the capability ratchet. No Wave 5 blocker is deferred.

## Evidence

- Public, reviewer, expert, and machine projection fixtures preserve blockers,
  limitations, omissions, contested records, audit refs, schema refs, and
  projection-only authority.
- Public export, external audit, generated client, and dashboard validators
  consume typed projection surfaces without converting `None`, missing refs,
  blocked claims, omitted fields, or projection gaps into apparent success.
- Semantic evaluation packs include public, hidden, and rotating false-pass
  fixtures for participation prevalence negatives, projection laundering,
  unreachable recourse pointers, tuned-threshold hardcoding, raw-count
  inflation, LLM speculation, and unsupported claims.
- Calibration behavior records sparse-history warnings and feature-flagged
  mature-history gates while preventing historical priors from entering current
  claim evidence slots.
- Balanced memory retrieves success, failure, and opportunity records with
  scope, TTL, revocation, contamination controls, and no evidence-slot
  admission.
- Operator guide and rollout/rollback runbook expose ADR lookup, evidence
  paths, tuned-parameter owners, validation ladders, capability evidence, and
  promotion/hold/rollback procedures from repo-owned paths.

## Validation

The I5 manifest records the Wave 5 command set. The key acceptance commands
are:

```bash
uv run pytest tests/repo_quality/tools/test_policy_design_case_public_export.py -q
uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_w5e_docs_runbooks.py tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
uv run pytest tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py tests/unit/runtime/quality/test_public_export.py tests/unit/runtime/quality/test_external_audit.py tests/repo_quality/tools/test_policy_design_case_w5b_semantic_evaluation_packs.py tests/unit/runtime/quality/test_calibration_ledger.py tests/unit/runtime/quality/test_memory_influence_records.py tests/unit/scientist/orchestration/memory/test_balanced_memory.py tests/unit/scientist/orchestration/memory/test_research_dag_projection.py -q
corepack pnpm --dir apps/runtime-dashboard exec vitest run src/api/validators.test.ts
uv run python tools/quality/validation/check_policy_design_case_capability_ratchet.py --repo-root .
```

## Boundaries

Wave 5 does not claim that historical calibration or memory closes current-run
claims. Both are influence surfaces for future routing, review intensity,
provider or model choice, uncertainty posture, and authority caps. Current
claim closure still requires producer evidence, closeout readers, consumer
contract verification, and semantic tests.

The W5.B fixture pack closes the committed public, hidden, and rotating
false-pass classes for this wave. Broader live-corpus usefulness and rollout
posture remain Wave 6 validation concerns.
