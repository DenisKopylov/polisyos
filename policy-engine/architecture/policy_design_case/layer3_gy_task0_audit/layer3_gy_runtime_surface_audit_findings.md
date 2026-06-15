# Layer 3 GY Runtime Surface Audit Findings

Task 0 follow-up slice for `docs/plans/active/layer3-slices/GY-engine-subordination.md`.

Scope: Runtime/API/dashboard/public export surfaces that can turn a failed or candidate scientist workflow into something that looks usable: `/runs`, raw artifact routes, runtime lineage exports, bureaucratic render/export, dashboard run detail, and public viewer.

This is audit-only. No runtime behavior was changed.

## Method

- Used the existing `tests/_helpers/runtime_http.py` fixture instead of inventing a happier fixture.
- The fixture creates a finalized Core run whose workflow report has `status: "fail"` and failed node `run_governance` with `error.code: "governance.blocked"` (`tests/_helpers/runtime_http.py:812`, `tests/_helpers/runtime_http.py:834`).
- The same run is finalized as `status="fail"` while its run manifest carries `execution_profile = "governed"` (`tests/_helpers/runtime_http.py:1004`, `tests/_helpers/runtime_http.py:1007`).
- Ran a FastAPI `TestClient` probe against the temp CAS/core-run root:
  `uv run --extra test --extra runtime python <runtime surface probe>`.
- Probe artifact: `_build/.tmp/gy-runtime-surface-audit/runtime_surface_probe.json`
  with sha256 `783a1a30520fbefc6237bc4bba9ccd3556d5fd0ecec84b20a088c5a036861a6c`.
- Machine-readable audit: `architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_runtime_surface_audit.json`.

## Probe Facts

The indexed run is simultaneously:

- `status = fail`
- `execution_profile = governed`
- `has_workflow_report = true`
- `decision_validity_status = warning`
- `decision_review_required = false`

All 12 probed runtime routes returned 200:

- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/workflow`
- `GET /api/v1/runs/{run_id}/lineage`
- `GET /api/v1/artifacts/{workflow_report_id}`
- `GET /api/v1/artifacts/{workflow_report_id}/content`
- `GET /api/v1/artifacts/{workflow_report_id}/lineage`
- `GET /api/v1/lineage/artifact:{workflow_report_id}`
- `GET /api/v1/lineage/artifact:{workflow_report_id}/export/openlineage`
- `GET /api/v1/lineage/artifact:{workflow_report_id}/export/prov`
- `POST /api/v1/artifacts/{decision_packet_id}/render`
- `GET /api/v1/artifacts/{decision_packet_id}/export?format=html`

## Headline Finding

The system does not hide the workflow failure. `/runs/{id}/workflow` clearly exposes `summary.status = fail`, `fail_count = 1`, and failed node `run_governance`.

The laundering risk is cross-surface: neighboring API, lineage, export, dashboard, and public-viewer consumers do not carry a load-bearing workflow authority ceiling. A failed workflow report can be present, verified, linked, downloaded, rendered, exported, or signed without the consumer receiving an explicit `candidate_only` / `may_not_use_for` / `not_publishable` boundary from the workflow failure.

## Findings

### F1. Run list/details expose presence, not authority

`CoreRunAdapter` extracts `workflow_report_ref` by kind (`src/polisyos/runtime/http/services/adapters/core_run.py:131`). `RunIndexService` converts that into `has_workflow_report` and `workflow_report_ref` (`src/polisyos/runtime/http/services/run_index.py:339`).

The public DTOs expose `status`, `execution_profile`, `has_workflow_report`, `workflow_report_ref`, and decision-validity fields (`src/polisyos/core/contracts/runtime.py:1495`, `src/polisyos/core/contracts/runtime.py:1536`), but not workflow authority status, candidate-only status, root-chain authority, blocked-by node, or may-not-use boundaries.

Gap labels: `surface_missing`, `semantic_test_missing`.
Patterns: `P03`, `P05`, `P15`.

### F2. Workflow route is the strongest backend truth surface but not a reusable gate

`GET /api/v1/runs/{run_id}/workflow` returns `summary.status = fail`, `fail_count = 1`, and failed node error code/message. `DebugService` builds this from workflow report, spec, and timeline (`src/polisyos/runtime/http/services/debug.py:816`, `src/polisyos/runtime/http/services/debug.py:917`).

This is honest execution status, but still not a named authority ceiling consumed by export/public surfaces.

Gap label: `semantic_test_missing`.
Patterns: `P04`, `P05`.

### F3. Raw artifact content is a critical boundary gap

`GET /api/v1/artifacts/{workflow_report_id}/content` returns the raw failed workflow JSON with `status: "fail"`. It also exposes nested error detail `error.details.api_token = "Bearer should-not-leak"` from the current fixture.

The preview path decodes JSON and applies only artifact-kind redaction hooks (`src/polisyos/runtime/http/services/artifact_inspector.py:374`, `src/polisyos/runtime/http/services/artifact_inspector.py:438`). The sanitized workflow route drops error details, but the raw artifact route does not.

This is both a laundering risk and a raw artifact security boundary finding.

Gap labels: `semantic_test_missing`, `verification_missing`.
Patterns: `P05`, `P10`, `P15`.

### F4. Lineage verified/complete is graph integrity, not admissibility

Runtime lineage for the failed workflow report returns `status = verified`, `verification_method = lineage_hash_match`, and `freshness = current`. OpenLineage export returns `eventType = COMPLETE` and `producer = polisyos-runtime-api` (`src/polisyos/runtime/http/services/lineage.py:253`, `src/polisyos/runtime/http/services/lineage.py:264`).

That is valid graph/export semantics, but it is unsafe as a public surface unless paired with workflow authority semantics. A failed workflow report can be exported as verified/complete lineage.

Gap labels: `semantic_test_missing`, `surface_missing`.
Patterns: `P05`, `P07`, `P10`, `P15`.

### F5. Bureaucratic render/export joins packet, not owning workflow authority

Bureaucratic render returns `status = draft`, a visible watermark, packet hash, trust view, and epistemic summary (`src/polisyos/runtime/http/services/bureaucratic_rendering.py:101`). Export reuses that AST and returns HTML with a machine-readable watermark.

The renderer consumes the decision packet payload and template metadata, not the owning workflow failure state. The probed failed run still produced 200 for render and 200 for HTML export.

Gap labels: `bridge_missing`, `consumer_missing`, `semantic_test_missing`.
Patterns: `P05`, `P15`, `P20`.

### F6. Dashboard/public packet has projection caveats, but not workflow-failure gates

The frontend public packet model has explicit projection semantics: `authorityRole: "projection_only"`, `mayNotBeUsedFor`, and projection-only labels fail closed (`apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts:203`, `apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts:1102`).

That is good framing, but it is not the same as consuming failed workflow status. The packet builder does not take `workflow_report_ref`, workflow status, or `decision_review_required` as load-bearing inputs. The public viewer verifies the signed packet payload, not current runtime workflow admissibility.

Gap labels: `bridge_missing`, `consumer_missing`, `semantic_test_missing`.
Patterns: `P05`, `P15`.

### F7. The missing test is cross-surface, not route-local

Existing backend tests prove the routes render and expose fields. Existing frontend tests prove projection caveats and packet verification. What is missing is the adversarial semantic test:

Input condition: failed workflow + governed execution profile + decision packet/evaluator still present.

Expected current characterization: run score, artifact content, verified lineage export, bureaucratic draft/export, and public packet can still render unless a consumer explicitly checks workflow failure.

Target repair acceptance: the same fixture either blocks public/export surfaces or carries machine-readable and visible non-authority/candidate-only caveats derived from workflow failure.

## Surface Matrix

| Surface | Observed | Risk | Gap labels |
| --- | --- | --- | --- |
| `/api/v1/runs` | failed run visible, workflow report only presence flag | high | `surface_missing`, `semantic_test_missing` |
| `/api/v1/runs/{id}` | failed status and workflow ref visible, no authority ceiling | high | `surface_missing`, `semantic_test_missing` |
| `/api/v1/runs/{id}/workflow` | fail status and failed node visible | medium | `semantic_test_missing` |
| `/api/v1/artifacts/{workflow_report}` | CAS integrity metadata, no authority role | high | `surface_missing`, `semantic_test_missing` |
| `/api/v1/artifacts/{workflow_report}/content` | raw failed JSON plus nested token-like detail | critical | `semantic_test_missing`, `verification_missing` |
| `/api/v1/artifacts/{workflow_report}/lineage` | complete/present artifact lineage | high | `semantic_test_missing` |
| `/api/v1/lineage/artifact:{workflow_report}` | verified lineage for failed workflow report | critical | `semantic_test_missing` |
| OpenLineage export | `eventType=COMPLETE` for failed workflow report root | critical | `surface_missing`, `semantic_test_missing` |
| PROV export | derivation graph without workflow authority ceiling | high | `surface_missing`, `semantic_test_missing` |
| Bureaucratic render | draft/watermarked document from packet, no workflow join | critical | `bridge_missing`, `consumer_missing`, `semantic_test_missing` |
| Bureaucratic HTML export | HTML export 200 with watermark, no workflow join | critical | `bridge_missing`, `consumer_missing`, `semantic_test_missing` |
| Dashboard workflow tab | failure visible locally | medium | `consumer_missing`, `semantic_test_missing` |
| Dashboard score/explainability | score/evidence panels not gated by workflow failure | critical | `bridge_missing`, `consumer_missing`, `semantic_test_missing` |
| Public packet builder | projection caveats exist, workflow failure not consumed | critical | `bridge_missing`, `consumer_missing`, `semantic_test_missing` |
| Public viewer | verifies signed packet, not runtime workflow authority | high | `consumer_missing`, `semantic_test_missing` |

## Plan Implications

1. GY-0.5 should re-baseline Runtime/API/dashboard/public export surfaces as a first-class laundering axis, not only engine wiring.
2. GY-1/GY-2 should not claim governance of public/export surfaces until failed workflow authority is carried across run DTOs, artifact surfaces, lineage exports, bureaucratic export, dashboard summary, and public packet signing.
3. Add a characterization test before repair: failed workflow + governed profile + available decision packet must currently show where rendering/export still succeeds.
4. Add a repair acceptance test after design: failed workflow blocks public/export or emits explicit `candidate_only` / `not_publishable` / `may_not_use_for` semantics in both machine-readable metadata and visible UI/export.
5. Add a raw artifact preview negative test for nested secret-like keys in workflow error details.
