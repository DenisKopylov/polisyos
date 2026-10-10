# DX0 Runtime HTTP mirrors — second ten candidate rows

## Evidence boundary

This is a scoped authoring packet for DX0 routing section 5 rows 11–20, from `case_inspection` through `feedback`. Parent supplied candidate HEAD `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a` and identified the tree as known dirty WIP. I read only the target source modules, their cited routes, the neutral runtime HTTP fixture helper, actual owner modules for misrouted criteria, and the routing note. No production source or tracked fixture was written. Pytest was not run because the root task explicitly reserves it until the combined wave.

The routing note points to the full source/module/test/import-route census at `LOCAL/raw/ratchet-repair-routing-current/complete-mirror-and-import-routes.json` (24,029,998 bytes; SHA-256 `e96e2c9af52deda33693debea0e5e7d14dc917056b35d3f6fc0c8355585b22`) and its Python test-tree path/hash manifest (2,898 files; manifest SHA-256 `7b4013bdb1894da2fb0c8357424cf1503957bc09ef4127126c60a4bbdb070f6a`). I use that existing census for complete-path routing context; assertions below are grounded in the exact target tests/source files and targeted scans.

I accidentally issued one read-only `git status -sb` and `git rev-parse HEAD` while confirming the assigned path; I made no Git mutation and told the parent. I did not call Git again. Exact byte identities for the reviewed inputs and the eight authored test files are retained in [runtime-http-mirrors-2-inputs.json](../raw/dx0-native/runtime-http-mirrors-2-inputs.json) (8,878 bytes, SHA-256 `9b2243710a6465390ee5b986846e3edf9a238cd4369adbc83e51008395a32a36`; it records 41 selected input identities). These hashes bind this local dirty snapshot; they do not claim a final source freeze.

## P40 disposition

**Same class, one level deeper**: this is the runtime owner-mirror coverage class already partitioned in the routing note, not a new defect class. The second slice cannot be treated as ten filename obligations. I added eight tests only where a distinct source-owned discriminator remained. Rows 12 and 15 have no new test because the source has no independent behavior matching the proposed property and existing consumers already exercise the owning contract. Rows 13 and 16 expose routing mismatches: their candidate properties belong to other modules, and the intent/scope behavior already has direct tests at its actual owner. The falsifier is recorded below; after this second slice, widen the owner/property map before opening another batch instead of adding more stem-matching tests.

| Row | Candidate source → cited route | Owner finding and minimal discriminator |
|---|---|---|
| 11 | `case_inspection.py` → `test_case_inspection_api.py` | The service is a transparent delegation to the verified RunPaper producer. The API route already covers unavailable facts, partial/stale replay, missing runs, authorization order, and the frozen union. Added a route-level negative that replays a sibling run’s complete pins against the requested run; it must fail with the case-inspection conflict code. There is no separate service-owned resolver to test. |
| 12 | `case_inspection_contracts.py` → `test_run_paper_api.py` | The module aliases `RunPaperPacket` and `RunPaperReplayQuery`; it defines no second DTO or validation behavior. Existing case-inspection and run-paper routes exercise the strict response and bound identity. **No test added**: an alias/re-export test or another model-construction test would be filler. Reopen only if this owner gains behavior distinct from the RunPaper contract. |
| 13 | `control/admission.py` → `services/test__control_contracts.py` | The source contains optional admission/execution metric forwarders, not intent/scope admission or producer dispatch. Added a field-preservation test for both metric records. The candidate property is misrouted to `control/job_scope_admission.py`; existing tests in `test_control_job_execution_intent.py` cover malformed scope and refusal before a route-owner/effect port. |
| 14 | `control/response_shapes.py` → `test_response_shapes_monetary.py` | Existing owner tests cover unknown/zero and settlement state. Added a high-precision Decimal discriminator: the event projection must retain the exact numeric value as text rather than round through float. |
| 15 | `control/nl_pipeline_testing.py` → `test_nl_pipeline_materialization.py` | This source owns the frozen non-promotable testing stamp and mock-agent factory. Existing tests exercise the stamp’s promotion refusal, production’s non-injection, and actual contract-test lane output. The routing note’s “validated span support” property belongs to `control/nl_pipeline.py`, not this helper. **No test added**: the existing consumer tests already cover the actual source behavior; a duplicate stamp test would not add a discriminator. |
| 16 | `control_worker.py` → `test_control_worker_custody.py` | This worker emits durable diagnostic events and extracts unique handoff refs; it does not own partial-result persistence/retry. Added an actual SQLite-backed dispatch test asserting that both persisted dispatch events retain handoff refs once each and do not adopt tenant/cell values from progress. Partial-attempt transitions belong to `control_plane_store.py`; the candidate row’s retry discriminator must be routed there if the existing attempt/lease tests do not cover that exact failure. |
| 17 | `cycle_board_projection.py` → `test_cycle_board_projection_access_replay.py` | Existing tests cover complete raw/composed replay pins and stage-trace pins. Added the narrower lifecycle binding negative: a sibling run’s signed terminality, or a status string lacking the enum identity, cannot supply the requested row’s lifecycle fact; an exact run/enum pair is the positive control. |
| 18 | `cycle_board_sources.py` → `test_cycle_board_historical_availability.py` | Existing tests cover historical-vs-current limits, absent/ambiguous/malformed rows, and unreadable sources. Added invalid UTF-8 bytes as a distinct read failure and assert the receipt retains the hash of the bytes actually read while status remains `UNRUN`. |
| 19 | `export_replay.py` → `test_confidence_ledger_risk_spend_contracts.py` | Existing tests use projection hashing/address helpers but do not call the shared response binder. Added a successful bind control and a stale-pin negative proving no response headers are partially written before the mismatch is raised. |
| 20 | `feedback.py` → `test_runs_api.py` | Existing API coverage proves feedback artifacts are persisted for the selected run. Added a real-CAS scope check: evaluating one run returns its reports while a sibling run’s packet bytes and projected feedback remain unchanged. |

## P40 falsifier and bounded residual

The second-ten bucket remains the same owner-mirror class, one level deeper. The proposed row list is not itself evidence that every target owns an untested behavior.

- The case-inspection route scan `rg -n 'CaseInspectionService|case_inspection_contracts|CaseInspectionReplayQuery|CaseInspectionResponse' tests/unit/runtime/http` resolves to the existing API and run-paper tests. Reading `case_inspection_contracts.py` confirms it contains only the two aliases, while `case_inspection.py` delegates to RunPaper. The missing capability that would justify another contracts test is an independent case-inspection validator/producer; it is absent at this source.
- The NL stamp/factory scan `rg -n 'NLContractTestingAuthorityStamp|build_nl_contract_testing_agents|production_promotable|contract_testing' tests/unit/runtime/http/test_nl_pipeline_materialization.py` finds direct stamp refusal at line 103 and actual contract-lane output assertions at lines 1591–1616, plus production non-injection at lines 46–100. The property named in the routing note, validated span support, is not implemented in `control/nl_pipeline_testing.py`; route it to `control/nl_pipeline.py` only if a separate uncovered consumer discriminator remains.
- The scope-owner scan `rg -n 'scope|intent|dispatch|admission' src/polisyos/runtime/http/services/control/job_scope_admission.py` finds the actual NL intent binding. Existing `test_control_job_execution_intent.py` covers malformed scope and refusal before owner/effect dispatch; `test_control_job_execution_split.py` covers lease loss before scope processing. The target `admission.py` contains only metric forwarding.
- The retry-owner scan `rg -n 'partial.*attempt|attempt.*partial|recovery_required|only winning attempt|terminal artifact|duplicate.*terminal|retry_selects' tests/unit/runtime/http --glob '*.py'` routes attempt/recovery behavior to `control_plane_store.py` and `test_control_job_core_attempts.py`, not to the worker’s lease/diagnostic loop. The exact partial-persistence retry case remains `not_established` by this read-only pass; the smallest close is a store-owner test that forces a partial attempt and observes terminal/outbox state.

Rows 12 and 15 are bounded no-new-test residuals. For row 12, a distinct case-only validator/producer does not exist because the contract intentionally reuses RunPaper. For row 15, validated-span consumption is owned by the NL pipeline, not this testing-lane helper; the existing consumer integration already exercises the testing lane. Rows 13 and 16 are property-routing corrections, not evidence of defects in these target modules. No import-only, constructor-only, copied-case, or selector-removal test was added.

## Authored paths

1. `tests/unit/runtime/http/services/test_case_inspection.py`
2. `tests/unit/runtime/http/services/control/test_admission.py`
3. `tests/unit/runtime/http/services/control/test_response_shapes.py`
4. `tests/unit/runtime/http/services/test_control_worker.py`
5. `tests/unit/runtime/http/services/test_cycle_board_projection.py`
6. `tests/unit/runtime/http/services/test_cycle_board_sources.py`
7. `tests/unit/runtime/http/services/test_export_replay.py`
8. `tests/unit/runtime/http/services/test_feedback.py`

No file was created for rows 12 or 15 for the reasons above. No existing tests were changed and no concrete test-module imports were added.

## Validation

- Root workspace Ruff on exactly the eight new files: **passed** using `policy-engine/.venv/bin/python -m ruff check --no-cache --config policy-engine/architecture/tooling/ruff/workspace_root.toml …`.
- Python syntax compilation via built-in `compile(..., "exec")` on exactly the eight new files: **passed** (no bytecode files written).
- Pytest: **not run**, per parent instruction; root may run the combined wave after the final source freeze.
- Linux source transport, container/VM work, and heavy test slots were not used.
