# N6 cycle history in run details

Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/routes/runs.py`, `src/polisyos/core/contracts/runtime.py`, `schemas/runtime_api_v1.openapi.json`

`GET /api/v1/runs/{run_id}` exposes the exact N6 cycle records carried by the selected persisted `runtime.compiled_recursive_generation_cycle` artifact under `run.generic_cycle_simulation.n6_cycle_history`. Each row is keyed by recursive `node_ref` and `cycle_index` and carries the selected design problem and candidate refs, the N6 run terminal status, `terminal_kind`, `refinement_decision`, `search_iteration_status`, the grounding and value-port statuses, and the VOI next action. The top-level compiled `source_ref` and `source_content_hash` bind all rows to the artifact the reader resolved.

The served fields copy producer values. `grounded_abstention` remains distinct from `grounded_partial_admissible`; `abstain` and `stop` remain distinct refinement decisions; `abstained` and `stopped` remain distinct search-iteration statuses. No result is inferred from a label, mapped into a new status, or promoted to authority. The existing `recursive_cycle_checkpoint` separately reports incomplete traversal, failed branches, the budget stop, and pending frontier. An N6 history status of `resolved` means the executed cycle rows in the selected compiled artifact were read and projected; it does not claim that recursive traversal completed.

When the compiled artifact is valid but carries no N6 cycle rows, the response uses `n6_cycle_history_status: "not_established"`, an empty history, and `n6_cycle_history_limitation_code: "n6_cycle_history_not_emitted"`. If the compiled source itself cannot be resolved or verified, the existing artifact-level refusal remains in force. Neither status establishes currentness, external custody, causal validity, or publication permission.

The projection schema advances to v3 for N6 history. Strict generated clients must be regenerated before consuming the added fields. The v2 credal-source-attempt projection remains supported; a response carrying both v2's credal fields and N6 history uses v4.
