# Runtime Policy Design Case Graph

- Owner: team-policyos-runtime
- Purpose: compile the runtime-owned `RuntimePolicyDesignCase` graph from claim registry, semantic binding, producer pipeline, closeout, contested, deficit, and projection-bound refs.
- Authority boundary: the graph is authoritative only for `pdc_graph_structure`; it may not be used for projection authority or claim authority.
- Local verification: `uv run pytest tests/unit/pdc tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py tests/repo_quality/tools/test_compiled_pdc_graph_smoke.py -q`
