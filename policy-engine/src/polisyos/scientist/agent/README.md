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
The stable `polisyos.scientist.agent` facade also owns the five workflow protocols (`CriticAgent`, `DataNeedExtractorAgent`, `DrafterAgent`, `FormalizerAgent`, and `PIAgent`) used by Runtime callers. Protocol conformance is structural and does not itself grant execution authority.


- Typed contracts in [`protocols.py`](protocols.py): `ProblemFrame`, `DraftResult`, `CritiqueReport`, `DataNeedSpec`, and `DelegationResult`
- Factories in [`drafter_factory.py`](drafter_factory.py) and [`critic.py`](critic.py): `create_drafter_agent(...)` and `create_critic_agent(...)`
- Role implementations in [`pi.py`](pi.py), [`drafter.py`](drafter.py), [`formalizer.py`](formalizer.py), and [`critic.py`](critic.py)
- Supervisor surface in [`supervisor.py`](supervisor.py): `ScientistSupervisorAgent` plus worker-envelope orchestration
- Reasoning surface in [`reasoning.py`](reasoning.py): `ReasoningPolicyGate`, `TreeOfThoughtPlanner`, `LATSAgentSearch`, and trajectory reports
- Supporting tools in [`rag.py`](rag.py), [`code_verifier.py`](code_verifier.py), [`feasibility_duckdb.py`](feasibility_duckdb.py), and [`failure_index.py`](failure_index.py)

## Vector-memory snapshot compatibility

`VectorMemoryStore` admits metadata as owned built-in JSON objects (finite numbers,
string keys, no arbitrary objects or cycles). The reserved Core 0.2 key
`_type` is refused at every metadata nesting depth before mutation, because the
current artifact writer does not admit the escaping 0.3 grammar. The transfer-history writer serializes
its artifact ID into that JSON before indexing. Query, add, save, and load share a
same-object generation barrier; if native mutation and rollback both fail, reads
and writes refuse until a valid fresh bundle is loaded. This is not a distributed
lock, production-currentness proof, or issuer authorization.

Vector bundle writes default to the legacy unversioned payload for existing
readers. `emit_v2=True` writes an exact native-index profile; `emit_rows=True`
selects version 3, whose exact profiled, bounded JSON metadata and NPZ vector
member carry one row order and matching Core input edge. Flags are mutually
exclusive. New ordinary reads and the candidate-transfer route admit v3 rows,
validate bounded numeric contents and rebuild a fresh index; they do not load
external native graph bytes. `from_portable_artifact` validates the bundle before
constructing any native index. A legacy or native-v2 read requires explicit
`allow_trusted_native=True` **and separately established trusted producer and
ABI**; the flag is a caller declaration, not evidence of trust. Consequently a
new reader does not automatically load the default legacy writer's output.

For the initial v3 engineering profile, JSON is limited to 256 KiB, selected
manifests to 64 KiB, NPZ bytes to 5 MiB, matrix entries to 1,000,000, rows to
25,000, dimensions to 4,096, capacity to 100,000, M to 64 and construction ef
to 1,000. The lower-level native record-size estimate is limited to 64 MiB and
the admission proxy `rows * M * ef` to 16,000,000; these do not bound all native
graph, lock, temporary or process overhead or prove a wall-time cap. These are
resource refusals, not G-law thresholds. Inputs and metadata must remain stable
while admitted. Float32 rounding and rebuilt approximate-neighbor ordering may
differ from the original graph; row identity and metadata remain aligned.

Reader-first migration: keep legacy emission or pause while readers are upgraded,
then enable v3 where bounded rows are retained. Without a verifiable retained row
basis, an untrusted legacy native bundle is refused; policy search continues cold
with a persisted typed limitation. Roll writers back to legacy if needed, retaining
v3-capable readers for artifacts already emitted. Old readers cannot consume v3;
historical read compatibility and old-reader/new-writer behavior require actual
native execution before promotion. Exact CAS bytes and row association do not
authenticate producer provenance, the original world or scientific validity.

## Legal retrieval result compatibility

Direct Python callers of `KnowledgeToolkit.search_legal_facts()` retain its list return. The
registered Scientist `search_legal_facts` tool now returns a strict object envelope with `results`,
`search_mode`, `vector_refusal_code`, and `limitation_code`, so text fallback no longer hides a
vector limitation from the tool consumer. `search_legal_facts_with_status()` receives results and
typed status from the same Legal graph call, so concurrent searches cannot exchange a mutable
latest-status field. Consumers of the registered tool must read facts from `results` and preserve
the status fields; the list-to-object tool response is a compatibility change.
The retrieval benchmark writes the same mode and refusal into each audit row.

`KnowledgeToolkit.assemble_legal_candidate_pack()` now records one strict `LegalRetrievalStatus`
per query and route (`hybrid_facts` reports text/vector, `constraints` reports structured
retrieval or refusal, and `provisions` reports vector admission or refusal). The policy-verified producer carries those records through its
multi-query and bounded recovery merges, so a hybrid text fallback and a direct-vector refusal remain
separately visible in the persisted `LegalCandidatePack`. Historical 1.0 candidate packs still load
with an empty status list, which means `not_recorded`; consumers must not infer vector admission from
that absence. New packs use schema 1.1.

The current policy-verified service builds its graph without the owner-issued Legal runtime
provider: hybrid facts retain text fallback, constraints remain structured, and direct vector-only
provision queries retain typed limitations. Vector-positive retrieval in this Scientist path is out
of scope here; no result is promoted by the presence of these status records or by a candidate result.

## Depends On / Depended On By

- Depends on: [`../../ir/README.md`](../../ir/README.md), [`../../lex/README.md`](../../lex/README.md), [`../../core/llm/README.md`](../../core/llm/README.md), [`../../core/artifacts/README.md`](../../core/artifacts/README.md), and adjacent Scientist LLM/runtime helpers
- Depended on by: policy-design authoring paths, optional critique/reflexion loops, and workflow/search integrations documented in [`../orchestration/workflows/README.md`](../orchestration/workflows/README.md) and [`../methods/search/README.md`](../methods/search/README.md)

## Common Commands

Run from the repository root (`policy-engine/`).

- Historical smoke-test claim for the import check; no qualified receipt
  establishes its source revision or run date, and it was not rerun for this
  review: `uv run python -c "from polisyos.scientist.agent import ProblemFrame, DraftResult; print(ProblemFrame.__name__, DraftResult.__name__)"`
- Conceptual full-slice test run: `uv run pytest tests/unit/scientist/agent -q`

## Test / Verification Commands

The test command below is retained as a historical smoke-test example. No
qualified receipt establishing its source revision or run date was available
for this review; it was not rerun and does not establish current verification.

```bash
uv run pytest tests/unit/scientist/agent/test_drafter_factory.py tests/unit/scientist/agent/test_supervisor.py tests/unit/scientist/agent/test_reasoning.py -q
```

## Reference Docs

- Scientist reference index: [`../../../../docs/reference/scientist/index.md`](../../../../docs/reference/scientist/index.md)
- Agent/search reasoning reference: [`../../../../docs/reference/scientist/agent-search-reasoning.md`](../../../../docs/reference/scientist/agent-search-reasoning.md)
- Phase 3 acceptance notes: [`../../../../docs/reference/scientist/phase3-acceptance.md`](../../../../docs/reference/scientist/phase3-acceptance.md)
- Cross-package navigation: [`../README.md`](../README.md), [`../methods/search/README.md`](../methods/search/README.md), and [`../../../../tests/unit/scientist/README.md`](../../../../tests/unit/scientist/README.md)

## Last Updated

- Last updated: 2026-10-14
