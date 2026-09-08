# Academic Batch (`polisyos.data_forge.domains.academic.batch`)

`polisyos.data_forge.domains.academic.batch` is the staged pipeline that turns
OpenAlex-selected literature into an academic/SKG graph. It runs in a
fulltext-first mode, keeps extraction deterministic where possible, and writes
publish-ready DuckDB and manifest artifacts.

## Role in System

- **Depends on:** `data_forge.kernel`, `core.canon`, `ir.analytics`, and
  `data_forge.domains.academic.openalex`.
- **Used by:** `data_forge.domains.academic.knowledge` and downstream
  discovery / prior-selection workflows.
- **Boundary function:** separates build-time harvesting/extraction from read-only graph access.

## Key Concepts

- **Staged pipeline** - topic selection, harvest, parse, resolve/extract, merge/dedup, graph load/index, embed, QC, publish.
- **Extraction planning** - `AcademicBatchConfig` keeps the batch inputs and runtime knobs used by the staged pipeline.
- **Fulltext-first resolve** - `resolve_extract.py` streams eligible papers, uses a lazy JSONL index, and keeps dispatch backpressure bounded.
- **Deterministic publish gates** - publish only happens after QC and readiness thresholds are satisfied.
- **Graph materialization** - `graph_builder.py` writes both runtime tables and SKG tables.

## Public API

- configuration: `AcademicBatchConfig`, `ALL_STAGES`, `DEFAULT_RUN_STAGES`
- CLI: `run`, `topic-select`, `resolve-extract`, `graph-load`, `qc`, `publish`, `stats`, `search`, `prior`
- orchestration modules: `pipeline.py`, `resolve_extract.py`, `graph_builder.py`, `publish.py`, `qc.py`

## Current State

- Last updated: 2026-04-03
- Data Forge Phase 8 physically removed the old `polisyos.academic` namespace;
  this package is now the canonical implementation owner.
- `resolve_extract.py` now uses `_LazyJsonlDict` for the precomputed fulltext cache and adds bounded bounce/backpressure handling.
- `claim_adjudicator.py` now routes LLM adjudication through the multi-key pool and uses more explicit design-tier scoring.

## Independent adjudication intake

`claim_adjudication_verifier.py` is the non-producing owner shared by Scientist
admission and DataForge materialization. Deployment supplies evaluator public-key
appointments and the permitted benchmark corpus; the default appointment set is
empty. The verifier authenticates external benchmark and execution receipts,
resolves the complete content-bound observations, recomputes metrics/guardrails and
promotion, replays the current champion, and derives the exact admitted batch. It
contains no receipt signer and does not establish institutional legitimacy.

`claim_adjudication_policy.py` owns the pure arithmetic reused by the evaluator,
registry, runtime and verifier. Arithmetic alone confers no authority. Graph and
conflict consumers obtain `VerifiedClaimAdjudicationRows` through the shared loader;
raw dictionaries cannot replace this capability, whose row reads reverify current
evidence and champion state. Deployment configuration and real independently
signed observations are still required; cryptographic test fixtures are not
production evidence.

The registry retains an explicit genesis or actual predecessor checkpoint before
claim champion transitions, and admits only the canonical claim promotion policy.
The verifier binds incumbent observations to that retained predecessor and
recomputes the comparison. A legacy pointer without a checkpoint is refused;
history is not reconstructed from candidate declarations. The configured verifier,
appointments, CAS and registry directory are deployment-trusted. This mechanism
checks ordinary producer calls inside that boundary, not hostile modification of
deployment configuration, filesystem administration or Python process memory.

The rich article producer reuses the canonical input projection to carry every
adjudication subject field through graph occurrences and conflict rows. This
projection includes all sibling claims in the article when computing contradiction.
Consumers compare the full current subject, conflicting aliases and enclosing work
identity before using a grade; a copied claim ID is insufficient. Legacy partial
transports cannot recover missing source fields from an admitted row and remain
unable to use publication authority. Deterministic candidate extraction continues
without an admitted match. Test integration covers the actual rich serializers,
Scientist intake, persisted receipt, DataForge materialization and both consumers;
it does not appoint a production evaluator or supply production observations.
