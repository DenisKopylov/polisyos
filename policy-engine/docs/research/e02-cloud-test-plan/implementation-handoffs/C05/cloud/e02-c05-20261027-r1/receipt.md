# C05 cloud receipt — e02-c05-20261027-r1

## Identity and environment

- Admitted base: commit `8db01b1076e425b7998b05a658776c991b7bd594`, tree `1706923ebe943f1a332dca4860cd145ddd366e36`, branch `work`.
- Environment: `/workspace/polisyos`; 32 GiB disk total / 28 GiB initially free; 17 GiB RAM total / 13 GiB initially free; 3 CPUs; Python 3.14.4; uv 0.7.22.
- Author-06 inputs verified: product patch `4a85a63957c6f0750e57214ca060a9a3772aa795292595381c702ec8368ed75f`; test patch `a172b044428e06bf2f6fc2b948a870f00df9134819e9462394d71c48b34fb93f`.

## Candidate and authority boundary

The app owns one configured private prompt cache. Core's opaque settlement owner is now tied to that exact cache lifetime, while each request retains its own caching/tracing wrapper and settlement hooks. This preserves a prior physical producer origin across later wrappers without copying or re-attesting it and prevents one request from overwriting another request's hooks. The container derives shared cache capacity and TTL from `GatewayLLMConfig`, rather than using a divergent default.

P37 classification: actor authentication, tenant/cell and live execution scope are independently reconciled from `ControlJobExecutionScope`; CAS bytes, digest, manifest profile and artifact identity are recomputed; current owner epoch/decision is institutionally supplied by the configured reuse owner and is fail-closed when absent; request metadata is never authority. P38 divergence guarded: a syntactically valid submitted snapshot ref can point at missing/corrupt bytes or a changed manifest profile, in which case no reuse context is constructed and the provider path is used.

## Results

- PASS: focused durable settlement and cross-wrapper cache-owner test (2 passed).
- PASS: Python compilation of touched runtime/Core/LLM packages.
- PASS: fixture companion source hashes remain the commissioned preimages.
- ERROR: `uv sync --frozen --extra runtime --extra ml` could not download locked `joblib==1.5.3` because the network tunnel was unavailable. The already-present supported `.venv` was used for bounded tests.
- UNRUN: the fourteen-case real-producer fixture replay, full integration POST witness, removal controls, Ruff and architecture guardrails. The integration witness was started with a 240-second bound but deliberately terminated before completion after high CPU use and no test output; it is not represented as a result. Run the commands below on the committed candidate.

## Exact bounded continuation

```bash
cd policy-engine
.venv/bin/python -m pytest -q tests/integration/runtime/http/test_nl_pipeline_cache_reuse_authorization.py::test_control_plane_reuses_only_current_owner_authorized_snapshot
.venv/bin/python -m pytest -q tests/unit/runtime/http/test_nl_pipeline_cost_projection.py::test_simulated_nl_producer_costs_settle_and_capture_four_origins tests/unit/runtime/quality/test_generation_cycle.py::test_b10_second_grounded_candidate_is_evaluated_with_first_blocker_preserved tests/unit/runtime/quality/test_generation_cycle.py::test_owner_program_graph_n5_consumes_distinct_wmr_states_and_n8_keeps_limits tests/unit/runtime/quality/test_generation_cycle.py::test_owner_program_graph_n5_consumes_selected_wmr_view_and_rejects_sibling tests/unit/runtime/quality/test_generation_cycle.py::test_owner_program_graph_n5_consumes_selected_state_blob_view tests/unit/runtime/quality/test_generation_cycle.py::test_owner_program_graph_n5_rejects_state_ref_selector_removal_with_markers tests/unit/runtime/quality/test_generation_cycle.py::test_owner_program_graph_n5_state_handoff_removal_probe_keeps_markers_red tests/unit/runtime/quality/test_generation_cycle.py::test_n8_types_unknown_or_malformed_content_bound_persisted_blockers tests/unit/runtime/quality/test_generation_cycle.py::test_owner_program_graph_n5_refuses_profileless_selected_json_semantic_inputs tests/unit/runtime/quality/test_generation_cycle.py::test_owner_program_graph_n5_requires_core_json_reader_before_store_reads
.venv/bin/python -m ruff check src/polisyos/core/llm/cache_settlement.py src/polisyos/runtime/http/container.py src/polisyos/runtime/http/services/control/nl_pipeline.py src/polisyos/runtime/http/services/control/run_lifecycle.py src/polisyos/scientist/orchestration/llm/factory.py src/polisyos/scientist/orchestration/llm/prompt_cache.py tests/unit/core/llm/test_traced_client_settlement.py tests/integration/runtime/http/test_nl_pipeline_cache_reuse_authorization.py
uv run polisyos-tools architecture guardrails check
```

Capability state is `verification_missing`: authored source and a focused lifetime witness exist, but the ordinary POST/readback, adversarial matrix, removal controls and producer fixture diagnosis remain pending. Independent review and G acceptance are pending; `closure_ids` is empty.
