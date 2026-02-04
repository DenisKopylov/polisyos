# E2.6 (Phase 13) — Fabric Claims v1.0: deterministic `extract -> normalize -> cite`

**Repo snapshot date**: 2026-02-03  
**Scope**:
- new package: `policy-engine/src/polisyos/fabric/claims/*`
- new tests: `policy-engine/tests/fabric/test_claims_pipeline_phase13.py`

## 0) Goal

Phase 13 adds a deterministic, offline claims pipeline that:

1. Reads `DocMeta` by `doc_meta_artifact_id`.
2. Extracts claim candidates from `fabric.doc.chunks`.
3. Builds IR `Claim` objects (`source_kind=doc`) with stable minimal citations.
4. Persists claims and claim-set artifacts in CAS.
5. Emits world facts only through `polisyos.fabric.world.store.*`.
6. Audits extraction/normalization as `WorldEvent`.

## 1) Public API

Exposed from `polisyos.fabric.claims`:

```python
def extract_claims_from_doc(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    doc_meta_artifact_id: str,
    extractor_id: str,
    options: ClaimExtractOptions | None = None,
    segment_name: str | None = None,
) -> ClaimExtractResult: ...

def normalize_claims(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    claim_set_artifact_id: str,
    options: ClaimNormalizeOptions | None = None,
    segment_name: str | None = None,
) -> ClaimNormalizeResult: ...
```

## 2) Determinism + ID invariants

- `claim_id` is computed with `claim_id_from_payload(...)` and validated via `validate_claim_id(...)`.
- Doc claims always carry citations.
- Citation payload is intentionally minimal to avoid `claim_id` drift:
  - `doc.doc_id`, `doc.doc_version_id`, `fragment_id`
  - no locator/text hash/evidence/props extras.
- Claim-set payload ordering is stable:
  - `claims` sorted by `claim_id`
  - `derived_from` sorted by `(input_claim_id, output_claim_id)`
  - warnings sorted by `(code, msg)`.

## 3) Artifacts and events

- Claim objects: kind `fabric.world.claim` (existing world contract).
- Claim sets: kind `fabric.claims.claim_set`, schema `fabric.claims.claim_set@1.0`.
- Optional evidence bundles use `fabric.evidence_bundle` with stage-specific schema names:
  - `fabric.evidence.claim_extract_v1`
  - `fabric.evidence.claim_normalize_v1`
- Events:
  - `EventKind.EXTRACT_CLAIMS`
  - `EventKind.NORMALIZE_CLAIMS` (added in this phase)

## 4) Materialization expectations

After `materialize_world_duckdb_from_fact_log(...)`:

- `world.claims` contains extracted/normalized claims.
- `world.claim_citations` is populated from `claim.cites` edges.
- `world.world_edges` includes `claim.cites` and optional `prov.was_derived_from`.
- `world.world_events` includes extraction and normalization events.
