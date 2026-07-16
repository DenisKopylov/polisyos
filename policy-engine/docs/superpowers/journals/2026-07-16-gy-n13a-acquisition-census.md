# GY-N13a Acquisition-Layer Reality Census Journal

Canonical plan: `docs/superpowers/plans/2026-07-16-gy-n13a-acquisition-census.md`.

## Task 1 — evidence schema and read-only catalog identity

Status: `complete`

Scope: strict census boundary DTOs, deterministic semantic hashing, a fail-closed read-only DuckDB
catalog identity/full-denominator query, and the initial checker CLI. No fetch, connector, ingestion,
canonical-store, CG, or world owner is imported or executed.

### RED witness

Command:

```text
uv run pytest -q tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py
```

Observed result before implementation: `6 failed`; every test failed on the expected missing owner
module, `ModuleNotFoundError: tools.quality.validation.layer3_gy_n13a_acquisition_census`.

Review then tightened the Task-1 boundary. The added tests produced `11 failed, 6 passed` before the
repair, witnessing each missing property: blank/null denominator rows were silently omitted, nested
`observed_at` was incorrectly erased from the hash, the per-attempt call budget allowed values above
one, manifest versions/time were not literal/typed, count maps admitted negatives, and resolution
labels did not require their decisive evidence.

### GREEN witness

Focused command:

```text
uv run pytest -q tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py
```

Observed result after the review repairs: `17 passed`.

The checker was then pointed explicitly at the ignored, read-only production snapshot:

```text
uv run python tools/quality/validation/check_layer3_gy_n13a_acquisition_census.py \
  --catalog-path /Users/deniskopylov/polisyos/policy-engine/production_data/\
datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb
```

Observed result: `status=pass`; 124 binding metrics, 12 connector families, 56,846 binding rows,
execution tiers 34,308 `transport_ready` + 7,668 `fetchable` + 14,870 `catalog`, and catalog identity
`sha256:4a1eab1363a948a875d00b0ae3929f47b763ba429c85776709641d6ca7960dd7`.

Ruff command:

```text
uv run --with ruff ruff check \
  tools/quality/validation/layer3_gy_n13a_acquisition_census.py \
  tools/quality/validation/check_layer3_gy_n13a_acquisition_census.py \
  tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py
```

Observed result: `All checks passed!`.
