# Fixture and Seed Data Catalog

Phase 4 catalog for reusable test data, snapshots, and deterministic builders.

Актуально на **3 апреля 2026**.

## 1. Canonical Fixture Families

| Family | Purpose | Canonical path(s) | Notes |
|---|---|---|---|
| Session/runtime fixtures | repo-wide test environment, artifact helpers, observability shims | `tests/conftest.py`, `tests/fixtures/artifacts.py`, `tests/fixtures/observability.py` | loaded automatically for pytest |
| Runtime HTTP environment | fixture-backed FastAPI app and metadata used by backend + dashboard tests | `tests/fixtures/runtime_http.py`, `tests/unit/runtime/http/conftest.py`, `frontend/runtime-dashboard/scripts/serve_fixture_runtime_api.py` | canonical local integration demo dataset |
| Deterministic synthetic builders | generated data when static JSON is too brittle | `tests/fixtures/c7_synthetic_data.py`, `tests/fixtures/causal_scm_fixtures.py`, `tests/fixtures/search_strategies.py` | prefer seeded builders over sprawling static blobs |
| Contract golden records | stable IDs, canonical bytes, ABI-critical fixtures | `tests/contract/golden_records.json`, `tests/contract/conftest.py` | refresh only with explicit contract decision |
| Foundry goldens | cross-method regression expectations | `tests/unit/foundry/golden/*.yaml` | human-reviewed YAML goldens |
| Schema snapshots | generated contract snapshots checked in to gate ABI drift | `schemas/snapshots/**` | refresh via schema generation tooling, never manual edits |
| Frontend contract fixtures | recorded runtime payloads parsed by frontend schemas | `frontend/runtime-dashboard/src/test/contracts/fixtures/*.json` | refresh via `npm run contracts:record` |
| Connector capture fixtures | recorded upstream source payloads and simulator fixtures | `tests/unit/fabric/connectors/sources/fixtures/**`, `polisyos-tools data record-fixtures` | committed only for narrow, reviewable source slices |
| Seed/minimal data bundles | tiny domain examples for lex, transportability, phase0 and benchmark cases | `tests/fixtures/lex/**`, `tests/fixtures/phase0/**`, `tests/fixtures/transportability/**`, `benchmarks/*/fixtures/public_cases.json` | small enough to reason about in code review |

## 2. Policy: Generated Fixtures

- Prefer generated, seeded builders when:
  - shape changes often;
  - semantics matter more than exact serialized bytes;
  - the fixture would otherwise need duplicated variants.
- Every generated fixture entrypoint must accept an explicit seed or derive one deterministically from the test case.
- Builders should emit the minimal fields the test needs, not production-scale payloads.
- If a builder becomes harder to understand than a small static fixture, freeze one reviewed output and reference the builder used to create it.

## 3. Policy: Golden Records

- Goldens represent reviewed compatibility baselines, not convenience fixtures.
- Canonical golden surfaces in this repo:
  - `tests/contract/golden_records.json`
  - `tests/unit/foundry/golden/*.yaml`
  - `schemas/snapshots/**`
- Golden refresh requires:
  - an intentional change reason;
  - matching code change;
  - reviewer acknowledgement that drift is expected.
- “Regenerate because CI failed” is not sufficient justification.

## 4. Policy: Snapshot Refresh

### Backend/schema snapshots

- Check drift:

```bash
cd policy-engine
uv run python tools/quality/diagnostics/gen_schema.py --models ir --check --output-dir schemas/snapshots
uv run python tools/quality/diagnostics/gen_schema.py --models fabric --check --output-dir schemas/snapshots
```

- Refresh intentionally by running the same tooling without `--check`, then review the diff.

### Frontend runtime contract fixtures

```bash
cd policy-engine/frontend/runtime-dashboard
npm run contracts:verify
npm run contracts:record
```

- `contracts:verify` is the safety gate.
- `contracts:record` is allowed only after a reviewed runtime API contract change.

## 5. Policy: Minimal Seed Datasets

- Seed datasets must stay:
  - tiny;
  - deterministic;
  - inspectable in a normal code review;
  - redaction-safe and non-sensitive.
- A seed dataset should describe one concept well, not emulate the entire production warehouse.
- Prefer JSON, YAML, or a very small Parquet fixture when shape fidelity matters.
- If a seed dataset exceeds “review comfortably in one diff,” split it or replace it with a seeded builder.

## 6. Committed Data vs Local Research Data

### Committed test data

- `tests/**`
- `schemas/snapshots/**`
- `benchmarks/*/fixtures/**`
- `frontend/runtime-dashboard/src/test/contracts/fixtures/**`

### Local or large data that must not be committed

- `data/**`
- `production_data/**`
- `.polisyos/**`
- `_build/**`
- `_cache/**`

These paths are already reinforced by root and repo-local `.gitignore` rules.

## 7. Deterministic Data Builders

Use builders instead of static fixtures when any of the following are true:

- the test asserts statistical or structural invariants rather than exact serialized bytes;
- the fixture needs controlled variation across many cases;
- the fixture needs to evolve alongside a model graph or search strategy;
- the static payload would become brittle under harmless schema reshaping.

Minimum expectations for a deterministic builder:

- explicit seed parameter;
- stable defaults;
- documented output contract in the builder docstring;
- narrow helper API so tests do not re-implement builder internals.

## 8. Lightweight Demo Data

The canonical lightweight demo dataset for local smoke and dashboard e2e is the fixture-backed runtime environment built by:

- `tests/fixtures/runtime_http.py`
- `frontend/runtime-dashboard/scripts/serve_fixture_runtime_api.py`

It is the default demo profile for the local integration stack because it is:

- deterministic;
- self-contained;
- cheap to start;
- representative of runtime/control-plane/frontend interaction.
