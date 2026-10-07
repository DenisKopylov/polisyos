# Agent (`polisyos.scientist.agent`)

## Purpose

`polisyos.scientist.agent` is the optional policy-authoring layer for
Scientist: PI, drafter, formalizer, critic, supervisor, reflexion, and
supporting RAG/feasibility tools used to create and review policy artifacts
before they enter the main workflow runtime.

## Where to Start

- Package facade and lazy export map: [`__init__.py`](__init__.py)
- Core typed contracts: [`protocols.py`](protocols.py)
- Drafting path: [`drafter_factory.py`](drafter_factory.py), [`drafter.py`](drafter.py), and [`drafter_multipass.py`](drafter_multipass.py)
- Critique and supervision: [`critic.py`](critic.py), [`informed_critic.py`](informed_critic.py), and [`supervisor.py`](supervisor.py)
- Reasoning and worker tools: [`reasoning.py`](reasoning.py) and [`tools/`](tools/)

## Public Entrypoints

- Typed contracts in [`protocols.py`](protocols.py): `ProblemFrame`, `DraftResult`, `CritiqueReport`, `DataNeedSpec`, and `DelegationResult`
- Factories in [`drafter_factory.py`](drafter_factory.py) and [`critic.py`](critic.py): `create_drafter_agent(...)` and `create_critic_agent(...)`
- Role implementations in [`pi.py`](pi.py), [`drafter.py`](drafter.py), [`formalizer.py`](formalizer.py), and [`critic.py`](critic.py)
- Supervisor surface in [`supervisor.py`](supervisor.py): `ScientistSupervisorAgent` plus worker-envelope orchestration
- Reasoning surface in [`reasoning.py`](reasoning.py): `ReasoningPolicyGate`, `TreeOfThoughtPlanner`, `LATSAgentSearch`, and trajectory reports
- Supporting tools in [`rag.py`](rag.py), [`code_verifier.py`](code_verifier.py), [`feasibility_duckdb.py`](feasibility_duckdb.py), and [`failure_index.py`](failure_index.py)

## Depends On / Depended On By

- Depends on: [`../../ir/README.md`](../../ir/README.md), [`../../lex/README.md`](../../lex/README.md), [`../../core/llm/README.md`](../../core/llm/README.md), [`../../core/artifacts/README.md`](../../core/artifacts/README.md), and adjacent Scientist LLM/runtime helpers
- Depended on by: policy-design authoring paths, optional critique/reflexion loops, and workflow/search integrations documented in [`../workflows/README.md`](../workflows/README.md) and [`../search/README.md`](../search/README.md)

## Common Commands

Run from the repository root (`policy-engine/`).

- Smoke-tested import check: `uv run python -c "from polisyos.scientist.agent import ProblemFrame, DraftResult; print(ProblemFrame.__name__, DraftResult.__name__)"`
- Conceptual full-slice test run: `uv run pytest tests/unit/scientist/agent -q`

## Test / Verification Commands

Smoke-tested:

```bash
uv run pytest tests/unit/scientist/agent/test_drafter_factory.py tests/unit/scientist/agent/test_supervisor.py tests/unit/scientist/agent/test_reasoning.py -q
```

## Reference Docs

- Scientist reference index: [`../../../../docs/reference/scientist/index.md`](../../../../docs/reference/scientist/index.md)
- Agent/search reasoning reference: [`../../../../docs/reference/scientist/agent-search-reasoning.md`](../../../../docs/reference/scientist/agent-search-reasoning.md)
- Phase 3 acceptance notes: [`../../../../docs/reference/scientist/phase3-acceptance.md`](../../../../docs/reference/scientist/phase3-acceptance.md)
- Cross-package navigation: [`../README.md`](../README.md), [`../search/README.md`](../search/README.md), and [`../../../../tests/unit/scientist/README.md`](../../../../tests/unit/scientist/README.md)

## Bounded native vector memory

[`VectorMemoryStore`](vector_memory.py) is an internal discovery helper used by
search transfer. It uses optional `hnswlib==0.8.0`; exact history addressability
comes from full CAS `ArtifactRef` values, independently of ANN top-k.
Add/update/load privately prepare a complete native generation and publish one
in-process pointer. Readers capture that pointer once. Native format admission
is pinned to this HNSW ABI; it is not a portable or distributed storage format.

Embedding coordinates admit strict `int`/`float` values (excluding booleans),
convert to finite floats, and identify the rejected coordinate. Before HNSW's
float32 conversion and normalization, nonzero vectors are scaled and normalized
in float64 using a stable cosine-equivalent direction. This prevents large or
tiny finite magnitudes from becoming an overflowed or zero native norm. Native
float32 approximate-neighbor geometry remains the supported profile. Legacy
zero-vector behavior is retained and establishes no scientific similarity.
A refused coordinate leaves the published generation unchanged.

A saved composite CAS ref binds the native index and complete key/metadata map.
The existing CAS verified-snapshot port supplies retained bytes/manifest pairs;
content and envelope binding precede native load. Private loaded native vectors
are checked for finite coordinates before publication. A valid historical CAS
bundle with nonfinite native coordinates is refused; this cannot recover or
distinguish historical nonzero vectors already collapsed to finite zero without
the absent original embedding. Fresh-process tests cover an
exact transfer history beyond 1000 discovery keys and same-ref byte tampering.
They establish a bounded fixture workflow, not source-owner authorization,
production history quality, or multi-host atomicity.

## Last Updated

- Last updated: 2026-10-07
