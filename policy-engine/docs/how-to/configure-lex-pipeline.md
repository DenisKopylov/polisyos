# Configure the Lex Pipeline

Related explanation: [Lex Pipeline](../explanation/lex-pipeline.md). Related reference: [Lex](../reference/lex/index.md).
Test path scope: `tests/unit/lex/**` (discovery scope, not a claim that every module in the tree was executed); [Lex contracts](../contracts/E2_9_LEX_NORMPACK_ASSEMBLY_V1_0.md), [Lex legal evaluation contract](../contracts/E2_10_LEX_LEGAL_EVALUATION_V1_0.md).

Historical source review: snapshot `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
(2026-10-14); reviewed the then-existing Data Forge corpus and contract paths,
`src/polisyos/lex/api.py`, and the runtime control route and service. It predates
the candidate NormPack type owner documented below.
Candidate owner source inspected in the R4 overlay: `src/polisyos/lex/normpack/types.py`
at `sha256:c565bdb422f9ea87b491fb78cdc3959d91fc821b912a7907f436630b17f11517`.
This is a candidate postimage, not a path claimed to exist at the historical
source pin. Commands, HTTP requests, and tests were not run as part of this
documentation review; this does not establish a working runtime or external
configuration.

> This page is for engineers and operators who need to assemble a reliable Lex
> ingestion path rather than call a single helper once.

## Inputs

- a raw legal-document corpus or batch input directories;
- a decision about whether you need a stage-level API path or a control-plane
  batch path;
- configured artifact roots for CAS and provenance/fact logs.

## Outputs

- a reproducible Lex pipeline path for ingest, structure, versioning, and
  NormPack;
- an understanding of which job IDs, artifact IDs, and world events to expect
  at each step;
- a minimal set of operational checks for local triage.

## Commands

```bash
cd policy-engine
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
curl -X POST "http://localhost:8000/api/v1/control/lex/trigger" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cards_path":"data/lex/cards","texts_path":"data/lex/texts","output_dir":".polisyos/lex-out","resume":true,"execution_profile":"research"}'
```

PolicyOS has two supported ways to work with Lex:

- the stage-level Python API for legal corpora and document versions in
  `polisyos.data_forge.domains.legal.corpus`; use `polisyos.lex.api` for the
  policy-facing `NormPack` and legal evaluation;
- the control-plane endpoint `POST /api/v1/control/lex/trigger` for job-based
  batch execution with `pipeline_id` and `job_id`.

## When to use each path

- Use the stage-level API when you need precise artifacts and control over
  `cas`, `fact_log_root`, version selection, and `NormPackBuildRequest`; ingest,
  structure, and the version index belong to the Data Forge corpus facade, while
  `NormPack` assembly belongs to the Lex API.
- Use the control plane when queues, `resume`, job-status polling, and operational
  visibility through `/api/v1/control/jobs/{job_id}` matter.

## 1. Prepare artifact roots

For the stage-level path, define the following in advance:

- a CAS root for artifacts;
- `fact_log_root` for world events and segment manifests;
- a consistent `doc_source_id` strategy so legal document versions can later be
  assembled into a version index.

Minimal local setup:

```python
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS

cas = FileSystemCAS(Path(".polisyos/cas"))
fact_log_root = Path(".polisyos/world")
```

## 2. Ingest and structure legal documents

For the corpus stage path, call `ingest_legal_doc_bytes()` and then
`build_legal_structure()`:

```python
from polisyos.data_forge.domains.legal.contracts import (
    LegalDocSource,
    LexIngestOptions,
    LexStructureOptions,
)
from polisyos.data_forge.domains.legal.corpus import (
    build_legal_structure,
    ingest_legal_doc_bytes,
)

source = LegalDocSource(
    canonical_url="https://zakon.rada.gov.ua/laws/show/example",
    license="official-publication",
    jurisdiction="ua",
    language="uk",
    title="Example Act",
)

ingest_result = ingest_legal_doc_bytes(
    cas=cas,
    fact_log_root=fact_log_root,
    source=source,
    raw_bytes=raw_bytes,
    mime="text/html",
    options=LexIngestOptions(run_normalize=True, run_structure=False, run_chunk=False),
)

structure_result = build_legal_structure(
    cas=cas,
    fact_log_root=fact_log_root,
    doc_meta_artifact_id=ingest_result.doc_meta_artifact_id,
    options=LexStructureOptions(jurisdiction="ua"),
)
```

At this stage, you receive:

- `doc_meta_artifact_id`
- `fragment_ids`
- `provision_index_artifact_id`
- world event refs / segment manifests

## 3. Build the version index

If a document has multiple versions, this is the next required layer for
reproducible legal evaluation:

```python
from polisyos.data_forge.domains.legal.contracts import (
    ActiveVersionStrategy,
    LexVersionIndexOptions,
)
from polisyos.data_forge.domains.legal.corpus import (
    build_version_index,
    resolve_active_version,
)

index_result = build_version_index(
    cas=cas,
    fact_log_root=fact_log_root,
    doc_source_id=ingest_result.doc_source_id,
    options=LexVersionIndexOptions(),
)

active = resolve_active_version(
    cas=cas,
    doc_source_id=ingest_result.doc_source_id,
    as_of_iso="2025-01-01",
    strategy=ActiveVersionStrategy(include_candidates=True),
)
```

This provides a deterministic local selection among the known version-index
records using the supplied `effective_from`/`effective_to` metadata: `as_of`
boundaries are inclusive, and when multiple versions qualify, ties are broken
by `effective_from`, then `published_at`, then `doc_version_id`. This behavior
is defined by
`src/polisyos/data_forge/domains/legal/corpus/versioning.py::resolve_active_version()`
and `src/polisyos/lex/normpack/select_sources.py::select_active_doc_versions()`.
The index does not prove which version was legally in force: it does not verify
the source's provenance with the publisher, corpus completeness, or currentness
at the time of reading. In particular, the current resolver treats a non-empty
but invalid `effective_to` as an open upper bound. This is a known validation
gap, not a finding about the act's effective period. See the [Lex NormPack
reference](../reference/lex/normpack.md#time-identity-and-replay) and [Lex
Pipeline explanation](../explanation/lex-pipeline.md#unresolved-integration).

## 4. Build the `NormPack`

When versioning is ready, move on to the policy-facing artifact:

```python
from polisyos.lex.api import assemble_norm_pack
from polisyos.lex.normpack.types import NormPackBuildRequest

norm_result = assemble_norm_pack(
    cas=cas,
    fact_log_root=fact_log_root,
    request=NormPackBuildRequest(
        jurisdiction="ua",
        as_of="2025-01-01",
        domain="roads",
    ),
)
```

Expected key outputs:

- `norm_pack_artifact_id`
- `norm_pack_world_id`
- selected doc versions
- conflict/trust outputs
- `world_event_id` for `assemble_norm_pack`

## 5. Use the control-plane path for a batch job

For operator-friendly execution, the runtime provides a control endpoint:

```bash
curl -X POST "http://localhost:8000/api/v1/control/lex/trigger" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cards_path": "data/lex/cards",
    "texts_path": "data/lex/texts",
    "output_dir": ".polisyos/lex-out",
    "stages": {
      "parse": true,
      "structure": true,
      "spo": true,
      "graph": true,
      "embed": false
    },
    "resume": true,
    "execution_profile": "research"
  }'
```

After an accepted response, use:

- `pipeline_id`
- `job_id`
- `GET /api/v1/control/jobs/{job_id}`
- `GET /api/v1/control/lex/status/{pipeline_id}`

## 6. Set quality toggles deliberately

Useful practical rules:

- Disable `embed` when you need a quick structural smoke run without the vector
  layer.
- Set `resume=true` only when `output_dir` and previous intermediate artifacts
  are intended to be reused.
- Set `execution_profile` when control-plane behavior must be reproducible
  across dev/research/governed paths.

For the stage-level path, explicitly set:

- `LexIngestOptions.run_normalize`
- `LexIngestOptions.run_structure`
- `LexIngestOptions.run_chunk`
- `LexStructureOptions.jurisdiction`
- `ActiveVersionStrategy.include_candidates`
- `NormPackBuildRequest.budgets`

## 7. Artifacts to expect

When the pipeline is configured correctly, you will usually see four layers of
results:

- corpus artifacts: raw/normalized/structured document payloads;
- versioning artifacts: the version index and active-version explanation;
- policy artifacts: `NormPack` and trust/conflict outputs;
- provenance artifacts: world events and fact segments.

This bundle matters more than a single final JSON: downstream governance and
intervention layers read this evidence bundle.

## 8. Source currentness and reassessment

Treat a discovered upstream publication or amendment, and corrections to source
bytes or metadata (such as effective dates, jurisdiction, or provenance), as a
reason to manually rebuild the affected corpus artifacts, version index, and
`NormPack`, then repeat the claim-level assessment for the required legal
`as_of`. A change to a claim requirement or Lex rule calls for a scoped
reassessment; rebuild source artifacts only when the source inputs or the
extraction/selection basis changed. These are operational prompts, not built-in
freshness triggers: the described path does not poll the publisher, verify its
signature, or itself run a full external-source invalidation/reissue cascade.
Preserve the previous assessment's input references and version/rule basis for
review; local reproducibility does not establish the source's legal currentness.
For time/replay and issuer-verification boundaries, see [Lex
Pipeline](../explanation/lex-pipeline.md#time-and-replay) and [unresolved
integration](../explanation/lex-pipeline.md#unresolved-integration).

## Rollback

- if the batch path used an incorrect `output_dir` or `execution_profile`, stop
  reusing those artifacts and restart the pipeline with the correct parameters;

- if the structure or version index was built from the wrong source payload,
  rebuild it from the correct ingest input rather than on top of the disputed
  result;

- if the issue concerns only documentation/operator guidance, roll back the
  workflow to the last verified stage sequence.

## Troubleshooting

- If the stage-level pipeline produces a "plausible but unclear" result, first
  check `doc_source_id`, `fact_log_root`, and the active-version strategy.

- If a control-plane batch does not produce the expected output artifacts, check
  the `job_id` and status endpoint separately from content-level artifacts.

- If you need a quick structural smoke run, disable `embed` so vector-stage
  latency does not complicate Lex structure/debugging.

## Next steps

- For the operational surface, see [Use Control Plane](use-control-plane.md).
- For the rationale behind the stage design, see the [Lex Pipeline
  explanation](../explanation/lex-pipeline.md).
- For policy-facing contracts, see the [Lex reference](../reference/lex/index.md).
