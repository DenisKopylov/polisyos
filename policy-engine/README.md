# Policy Engine (PolisyOS) — Architecture v2.5.0

Policy Engine is an **AI-driven policy operating system** for designing, validating, calibrating, and executing public-policy interventions as reproducible computational experiments.

**Updated:** 2026-02-05  
**Python package version:** see `pyproject.toml` (tracked independently from the architecture version).  
**Repository map:** `architecture.md`

---

## Architecture (at a glance)

```
NL intent
  → Scientist (agents + workflow + governance)
  → IR (Trinity contracts + kernel registries)
  → Fabric (UDF data views + evidence/provenance/quality/trust)
  → Foundry (compile + calibrate + simulate; pure JAX)
  → Runtime (runs/<run_id>/ manifests + audits + artifact refs)
  → Decision artifacts (DecisionPacket / DecisionCard / RunTimeline)
```

Cross-cutting subsystems:
- **Lex**: legal corpus → `NormPack` → legality evaluation (used in governance passes).
- **Scholar**: sources → docs → claims → trust → knowledge bundles (feeds Fabric/IR workflows).
- **Packs (Phase 19)**: built-in components (IR fragments / Foundry methods / Lex evaluators / Scholar extractors).

---

## Module map (current)

`A → B` means “A may depend on B” (Law A). For details, follow the per-module READMEs.

| Module | Responsibility | Depends on | Docs |
| --- | --- | --- | --- |
| `polisyos.common` | config, logging, async tools, migrations, macOS JAX env defaults | — | `src/polisyos/common/README.md` |
| `polisyos.core` | CAS artifacts, canonical JSON, typed contracts, components/registries, run context, observability | common | `src/polisyos/core/README.md` |
| `polisyos.ir` | **pure contracts**: Trinity, kernel registries, `NormPack`/connectors/world types, migrations/loaders | — | `src/polisyos/ir/README.md` |
| `polisyos.fabric` | ingestion + connectors + UDF; evidence/provenance/trust/quality; fact log + materialization; docs/claims | ir, core, common | `src/polisyos/fabric/README.md` |
| `polisyos.foundry` | compile+execute policies in JAX; methods framework; calibration; agent simulation; determinism & NaN guards | ir, core, common | `src/polisyos/foundry/README.md` |
| `polisyos.runtime` | run lifecycle: `RunManifest`, audit trail, budgets, portable artifact refs (`runs/`) | core, common | `src/polisyos/runtime/README.md` |
| `polisyos.lex` | legal docs: corpus, structure/versioning, `NormPack` assembly, legality evaluation | fabric, ir, core, common | `src/polisyos/lex/README.md` |
| `polisyos.scholar` | knowledge enrichment: discovery→acquire→docs→claims→reconcile→trust→bundle | fabric, ir, core, common | `src/polisyos/scholar/README.md` |
| `polisyos.scientist` | orchestration “brain”: agents, workflow engines, governance passes, search/DoE, decision packaging | ir, fabric, foundry, runtime, lex, core, common | `src/polisyos/scientist/README.md` |
| `polisyos.packs` | built-in component packs (Phase 19): IR fragments, Foundry methods, Lex evaluators, Scholar extractors | core, ir, foundry, lex, fabric, common | `src/polisyos/packs/README.md` |

Also:
- **Tests:** `tests/README.md`
- **Developer tools:** `tools/README.md`

---

## Key concepts (what to learn first)

- **Trinity IR** (`ProblemFrame` + `PolicySpec` + `ModelSpec`): separation of *why / what / how* with `TrinityBundle` as canonical bundle format.
- **Kernel registries** (IR): mechanisms, slots, merge rules, units, metrics, constraints, selector_fields, trust, numbers, values, time semantics.
- **UDF (Unified Data Fabric)**: safe “data views” compiled through passes (typecheck, resolution, privacy, lowering, merge) and executed on DuckDB/Kùzu.
- **CAS artifacts** (Core): content-addressed storage (SHA-256) + deterministic canonical JSON; everything important becomes an artifact.
- **Evidence / provenance / trust / quality** (Fabric): evidence bundles, PROV-O lineage graphs, quality indicators + fitness reports, uncertainty bounds / two-pass comparisons.
- **Governance passes** (Scientist): schema/safety/privacy/legal/quality gates before (and after) expensive compute.
- **Runtime runs** (`polisyos.runtime`): portable `runs/<run_id>/` directory with manifest + audit trail + artifact refs (relative paths).

---

## Project laws (invariants)

- **Law A — Import Gate:** dependencies go "down" the stack; cycles are forbidden (enforced by `tools/lint/lint_imports.py`).
- **Law B — Foundry is pure JAX:** no DB/network/file I/O in the execution core (enforced by `tools/lint/lint_foundry.py`).
- **Law C — Contracts are source of truth:** IR + typed inter-module contracts define canonical data; JSON Schemas are generated from them.
- **Law D — Reproducibility:** every run is auditable; artifacts are content-addressed; determinism is tracked (environment fingerprints/manifests).
- **Law E — Evidence & provenance:** data products carry evidence/provenance; fact log can materialize immutable audit trails.
- **Law K — Quality gates:** low-quality or policy-violating inputs are blocked before execution.

---

## Docs index

- Repository structure: `architecture.md`
- Trinity semantics: `docs/contracts/TRINITY.md`
- Merge semantics: `docs/contracts/MERGE_SEMANTICS.md`
- Connector contribution guide: `docs/connectors/CONTRIBUTING.md`

---

## Quickstart (local)

Prereqs: Python `>=3.11`, `uv`.

```bash
cd policy-engine
uv sync --frozen --extra dev
cp env_example.txt .env  # optional local defaults

# Smoke check
uv run python tools/diagnostics/check_setup.py

# Run tests
uv run pytest
```

macOS note: import `jax_bootstrap.py` (which applies safe env defaults from `polisyos.common`) **before** importing `jax` in local scripts.

---

## Running an experiment (example)

Legacy CLI `run_experiment.py` removed. Use the API entrypoint `polisyos.scientist.run_experiment()` with an `ExperimentState`-compatible payload.

Dashboard:

```bash
uv run streamlit run dashboard.py
```

---

## Tests

Tests are organized by architectural layers (contracts/core/fabric/foundry/scientist/runtime) plus integration/performance suites. See `tests/README.md` for the full map.

Common commands:

```bash
uv run pytest                      # all
uv run pytest -m "not integration"  # unit-only
uv run pytest -m integration        # integration-only
uv run pytest tests/contract/ -v
uv run pytest tests/core_phase0/ -v
uv run pytest tests/fabric/ -v
uv run pytest tests/foundry/ -v
uv run pytest tests/scientist/ -v
uv run pytest tests/runtime/ -v
```

Performance regression check:

```bash
uv run pytest tests/performance/ --benchmark-json=results.json
uv run python tools/diagnostics/check_perf_regression.py results.json
```

---

## Tools

See `tools/README.md` for the full catalog. Frequently used:

```bash
uv run python tools/lint/lint_imports.py
uv run python tools/lint/lint_foundry.py
uv run python tools/lint/lint_connectors.py
uv run python tools/diagnostics/gen_schema.py --check
uv run python tools/migrate_to_trinity.py --help
```

---

## Legal norms (NormPacks)

- Example norms live in `data/norms/sample_norms.yaml`.
- Legal evaluation uses pluggable backends; the safe-expression backend validates expressions via an allowlist AST policy (deny-by-default) and enforces resource limits.

---

## Observability & ops

- **Tracing:** OpenTelemetry-based spans via `PolicyOSTracer` + `@traced`.
- **Metrics:** Prometheus-friendly registry.
- **Logs:** structured logs with trace/span correlation.

Start the local observability stack:

```bash
cd policy-engine/ops
docker-compose -f docker-compose.observability.yml up -d
```

---

## Reproducibility & artifacts

- CAS lives under `.polisyos/artifacts/` (by default); artifacts are addressed by SHA-256.
- Runs are stored under `runs/<run_id>/` with a portable `RunManifest` and JSONL audit trail.
- Environment fingerprints/manifests capture execution context and determinism tier.
- Artifact/schema migrations live under `polisyos.common.migrations` and `polisyos.ir.migrations`.
