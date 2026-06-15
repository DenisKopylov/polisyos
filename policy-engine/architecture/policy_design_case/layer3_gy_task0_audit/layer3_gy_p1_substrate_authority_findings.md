# GY P1 Substrate Authority Findings

Date: 2026-06-14
Scope: CAS integrity/dedup/GC/tamper-evidence, time semantics, secrets/PII, and cost/VOI/budget honesty.
Mode: audit-only; no runtime fixes.

Machine-readable audit: `architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_p1_substrate_authority_audit.json`.

## Method

- Read the failure-pattern register before this pass: relevant risks are P01, P02, P03, P05, P07, P08, P10, P13, P15, and P25.
- Ran a temporary CAS dedup/tamper probe against `FileSystemCAS`.
- Scanned P0 DAG CAS manifests under `tmp/gy_p0_*` for authority linkage.
- Scanned selected DAG bundles, the catalog-fetch connector probe payload, GY audit artifacts, and the red-team fixture directory for secret/PII literals.
- Counted PDC and P0 DAG time fields to separate modeled legal time from runtime/source freshness/replay time.
- Dereferenced the exact G5 S12 `demand-act://...` / `voi://...` refs against committed PDC artifacts and source producers.

## Findings

### 1. CAS byte integrity is real; DAG authority backing is not

`FileSystemCAS` is strong at the byte contract: duplicate canonical JSON writes returned the same `sha256:` ref and one blob/manifest pair; blob tampering failed both `verify` and `get_bytes`; manifest byte-size tampering failed `verify` and `get_bytes`.

Two important limits remain:

- Re-putting the same payload after blob tamper did not heal the blob because the dedup path validates the existing manifest identity, not existing blob bytes.
- `FileSystemCAS` exposes no general GC/sweep/delete API. Fabric world snapshots have separate GC, but core CAS does not.

The authority gap is larger than byte integrity. Runtime-quality reports have `write_runtime_authority_artifact` plus durable diagnostic event reconciliation. Scientist DAG outputs do not: the P0 DAG CAS scan found `178` manifests and `0` `manifest.authority` records across production-worker and depth-2 DAG runs. Workflow report, final state, and `scientist.provenance.run_dag` are ordinary `put_json` outputs.

Implication: GY must not treat DAG bundles as authority roots merely because CAS digest integrity passes.

### 2. Time semantics are split across surfaces

Runtime bitemporality exists, but not on the laundering-risk surfaces. `TemporalService` supports `run_details`, `run_timeline`, `run_lineage`, `run_quantities`, `run_fabric_decision_data`, and `run_compare`; it explicitly marks `run_workflow`, `run_nodes`, and `artifact_content` as unsupported.

The PDC JSON inventory shows legal-time modeling, not a composed admission envelope:

- `legal_as_of`: `87` occurrences, `44` null/empty.
- `effective_from`: `86` occurrences, `74` null/empty.
- `effective_to`: `81` occurrences, `69` null/empty.
- `catalog_watermark`, `source_updated_at`, `source_timestamp`, `fetched_at`, `valid_at`, and `tx_at`: `0` occurrences in committed PDC JSON artifacts scanned.

P0 DAG blobs/manifests mostly carry CAS `created_at`; they do not carry source freshness, legal validity time, or bitemporal replay fields.

Implication: replay/admissibility can drift because catalog watermark, source freshness, effective time, legal time, and runtime as-of/tx time are not one load-bearing envelope.

### 3. Secret/PII protection is preview-bound and opt-in

The selected scan found `5` secret-like match lines across `4` files and `0` PII regex hits. The catalog-fetch connector probe payload under `_build/.tmp/gy-catalog-fetch-audit/catalog_fetch_probe.json` added no secret/PII hits. The important live finding is not the red-team fixture; it is the P0 DAG workflow-report blob containing `error.details.api_token = "Bearer should-not-leak"`.

`ArtifactInspectorService` redacts previews by sensitive kind markers and optional hooks. Raw artifact routes do not use that preview boundary:

- `/api/v1/artifacts/{id}/content` returns raw bytes when the Accept header prefers raw.
- `/api/v1/artifacts/{id}/download` returns raw bytes as attachment.

PII detection exists in Fabric, but `PIIDetectionStage.from_env()` defaults off. The ingestion path applies it when enabled; `FetchExecutor` in retrieval does not apply it before preview/execute metrics.

Implication: a DAG bundle can be byte-valid and API-visible while still containing secret-like data. Raw artifact/public export gates need explicit not-publishable/redaction-required authority, not just preview redaction.

### 4. S12 exists, but G5 pass refs are authorial labels

S12 resource-economics producers are real: `ValueOfInformationAllocation`, `ResourceAllocationPolicy`, `EnvelopeGrowthLedger`, authority envelope checks, and unit tests exist. The committed S12 manifest reports `case_count=13`, `voi_site_count=5`, and `typed_budget_count=5`.

However, the G5 pinned pass uses exact refs that do not dereference to produced S12 objects:

- `demand-act://ua-msme/principal`
- `voi://ua-msme/site-1`

Those refs occur in `layer3_g5_composed_loop_completeness_gate.json` and `layer3_g5_pinned_case_input_bundle.json`. Their source is the hardcoded readiness payload in `src/polisyos/runtime/quality/layer3_proving_ground_conversion.py:1219`.

The runtime run-cost gate is a separate real capability; it does not prove S12 VOI/budget honesty for the G5 handoff.

Implication: G5 S12 should be downgraded from measured/produced pass to `authorial_refs_in_g5_handoff_not_measured_exact_s12_objects` until exact refs dereference to produced resource-economics artifacts.

## Plan Impact

P1 changes the GY improvement plan in four ways:

1. GY-2 cannot be only "govern DAG persistence"; it must govern the authority bridge from DAG CAS outputs to runtime/API/dashboard/public surfaces.
2. GY-1 cannot use catalog freshness/right facets alone; it needs a composed time/source admission envelope before fetch and before public/raw artifact surfaces.
3. Secret/PII admission must sit before raw artifact/public export routes, not only in preview services or optional ingestion.
4. S12 resource pass cannot be accepted by string ref shape. It needs dereferenceable producer artifacts, or the pass must remain candidate/projection-only.

## Verification

```bash
python3 tools/quality/validation/check_layer3_gy_p1_substrate_authority_audit.py --json
uv run pytest -q tests/repo_quality/tools/test_layer3_gy_p1_substrate_authority_audit.py
```
