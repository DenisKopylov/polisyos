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

## Last Updated

- Last updated: 2026-04-17
