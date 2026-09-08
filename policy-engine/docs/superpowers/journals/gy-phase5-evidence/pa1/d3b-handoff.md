# PA1 D3b/D3c/D3d frozen delta handoff

Source and tests are frozen for independent delta review. This is the post-source
intake delta after initial PA1 commit `f412d424a`; the root owns local commits,
canonical OpenAPI/client/dashboard companions, and common final guardrails.

## Mechanism paths

- `src/polisyos/runtime/http/services/control/generation_cycle.py`
- `src/polisyos/runtime/http/services/control/run_lifecycle.py`
- `src/polisyos/runtime/http/services/control_plane_store.py`
- `src/polisyos/runtime/http/routes/control.py`
- `src/polisyos/runtime/http/resource_binding.py`

## Mandatory companions

- `tests/unit/runtime/http/test_normative_evidence_intake.py`
- `tests/unit/runtime/http/test_normative_generation_bridge.py`
- `tests/unit/runtime/http/test_control_plane_store.py`
- `tests/unit/runtime/http/test_runtime_api_authz.py`
- `src/polisyos/runtime/http/README.md`
- `release-fragments/unreleased/2026-09-08-gy-pa1-normative-evidence-intake.toml`
- `docs/superpowers/journals/gy-phase5-evidence/pa1/stage3.md`

The evidence/command scripts and records are the `d3b*`, `d3c*`, `d3d*` members
of this directory, plus the append to `stage3.md`. Root-authored review/decision
records remain with root ownership. No S3 quality/foundry file, ledger/debt file,
GitHub capability, commit, push, stash or generated writer was touched here.

## Verification boundary

- `d3b-final-targeted-v3.json`: complete preceding targeted wave, 21 actual test
  identities independently reconciled in `d3b-test-identities.json`; all green.
- `d3d-shared-source-delta.json`: changed-boundary four-node delta green after
  immutable default/source widening and real core-publication fixture correction.
- `d3b-head-absence-challenge.json`: actual escape before D3d, retained red.
- `d3d-semantic-head-attachment-removal.json`: corrected falsifier reads both real
  current consumers and asserts authorization/rankings before metadata.
- `d3b-head-binding-removal.json`: historical bound-source mutation kept happy
  path green and made wrong-job negative red; predicate unchanged by D3d.
- `d3c-owned-publication-removal.json`: actual HTTP owned-run resolver rejects
  unpublished worker source, with typed 403 reason.
- `d3b-ruff-final-v2.json` and `d3d-ruff-final.json`: scoped Ruff green.
- `d3b-source-census.json` / `d3d-source-census.json`: complete source git/filesystem,
  AST/token, and head-schema/Pydantic identity reconciliation.

No live PostgreSQL transaction was executed. SQLite concurrency is measured using
two independent store instances; PostgreSQL row-lock transaction code uses the
existing owner but its runtime verification is `not_established` here.

Current API schema did not change in D3d. Canonical generated owners are
`tools.ops_runners.runtime.export_runtime_openapi`,
`tools.ops_runners.runtime.generate_runtime_client` (or its pnpm owner wrapper),
and `tools.ops_runners.runtime.check_runtime_api_contract`. Invoke Python modules
with `-m` and lane venv first PATH. Root already coordinates these writers.

## Complete command record index

### `d3b-final-targeted-v2.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_evidence_intake.py tests/unit/runtime/http/test_control_plane_store.py::test_normative_head_compare_and_append_has_one_sqlite_winner tests/unit/runtime/http/test_runtime_api_authz.py::test_mutating_routes_have_exactly_one_action_permission_dependency tests/unit/runtime/http/test_runtime_api_authz.py::test_openapi_mutating_denominator_matches_live_router tests/unit/runtime/http/test_runtime_api_authz.py::test_each_mutating_operation_projects_action_permission_extension 'tests/unit/runtime/http/test_runtime_api_authz.py::test_mutating_operation_without_permission_is_denied_403[submit-normative-evidence]' 'tests/unit/runtime/http/test_runtime_api_authz.py::test_mutating_operation_without_identity_is_denied_401[submit-normative-evidence]' 'tests/unit/runtime/http/test_runtime_api_authz.py::test_mutating_operation_authorized_request_reaches_handler[submit-normative-evidence]' -q --junitxml=.tmp/gyphase5-pa1-d3b-targeted.xml`
- Actual RC: `1`; wall seconds: `71.54820462502539`.
- Complete stdout/stderr and child environment: [d3b-final-targeted-v2.json](d3b-final-targeted-v2.json).

### `d3b-final-targeted-v3.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_evidence_intake.py tests/unit/runtime/http/test_control_plane_store.py::test_normative_head_compare_and_append_has_one_sqlite_winner tests/unit/runtime/http/test_runtime_api_authz.py::test_mutating_routes_have_exactly_one_action_permission_dependency tests/unit/runtime/http/test_runtime_api_authz.py::test_openapi_mutating_denominator_matches_live_router tests/unit/runtime/http/test_runtime_api_authz.py::test_each_mutating_operation_projects_action_permission_extension 'tests/unit/runtime/http/test_runtime_api_authz.py::test_mutating_operation_without_permission_is_denied_403[submit-normative-evidence]' 'tests/unit/runtime/http/test_runtime_api_authz.py::test_mutating_operation_without_identity_is_denied_401[submit-normative-evidence]' 'tests/unit/runtime/http/test_runtime_api_authz.py::test_mutating_operation_authorized_request_reaches_handler[submit-normative-evidence]' -q --junitxml=.tmp/gyphase5-pa1-d3b-targeted.xml`
- Actual RC: `0`; wall seconds: `132.91363483300665`.
- Complete stdout/stderr and child environment: [d3b-final-targeted-v3.json](d3b-final-targeted-v3.json).

### `d3b-final-targeted.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_evidence_intake.py tests/unit/runtime/http/test_control_plane_store.py::test_normative_head_compare_and_append_has_one_sqlite_winner tests/unit/runtime/http/test_runtime_api_authz.py::test_mutating_routes_have_exactly_one_action_permission_dependency tests/unit/runtime/http/test_runtime_api_authz.py::test_openapi_mutating_denominator_matches_live_router tests/unit/runtime/http/test_runtime_api_authz.py::test_each_mutating_operation_projects_action_permission_extension 'tests/unit/runtime/http/test_runtime_api_authz.py::test_mutating_operation_without_permission_is_denied_403[submit-normative-evidence]' 'tests/unit/runtime/http/test_runtime_api_authz.py::test_mutating_operation_without_identity_is_denied_401[submit-normative-evidence]' 'tests/unit/runtime/http/test_runtime_api_authz.py::test_mutating_operation_authorized_request_reaches_handler[submit-normative-evidence]' -q --junitxml=.tmp/gyphase5-pa1-d3b-targeted.xml`
- Actual RC: `1`; wall seconds: `68.59847654099576`.
- Complete stdout/stderr and child environment: [d3b-final-targeted.json](d3b-final-targeted.json).

### `d3b-head-absence-challenge.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.d3b_head_absence`
- Actual RC: `1`; wall seconds: `94.16000058397185`.
- Complete stdout/stderr and child environment: [d3b-head-absence-challenge.json](d3b-head-absence-challenge.json).

### `d3b-head-attachment-removal.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.d3b_probe head_attachment`
- Actual RC: `1`; wall seconds: `40.95574783399934`.
- Complete stdout/stderr and child environment: [d3b-head-attachment-removal.json](d3b-head-attachment-removal.json).

### `d3b-head-binding-removal.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.d3b_probe head_binding`
- Actual RC: `1`; wall seconds: `102.35859358304879`.
- Complete stdout/stderr and child environment: [d3b-head-binding-removal.json](d3b-head-binding-removal.json).

### `d3b-intake-first-green.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_evidence_intake.py::test_post_source_signature_advances_both_current_job_readers -q`
- Actual RC: `1`; wall seconds: `33.76308229198912`.
- Complete stdout/stderr and child environment: [d3b-intake-first-green.json](d3b-intake-first-green.json).

### `d3b-intake-red-v2.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_evidence_intake.py::test_post_source_signature_advances_both_current_job_readers -q`
- Actual RC: `1`; wall seconds: `34.57497074996354`.
- Complete stdout/stderr and child environment: [d3b-intake-red-v2.json](d3b-intake-red-v2.json).

### `d3b-intake-red-v3.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_evidence_intake.py::test_post_source_signature_advances_both_current_job_readers -q`
- Actual RC: `1`; wall seconds: `34.12447245896328`.
- Complete stdout/stderr and child environment: [d3b-intake-red-v3.json](d3b-intake-red-v3.json).

### `d3b-intake-red.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_evidence_intake.py::test_post_source_signature_advances_both_current_job_readers -q`
- Actual RC: `1`; wall seconds: `37.75508054200327`.
- Complete stdout/stderr and child environment: [d3b-intake-red.json](d3b-intake-red.json).

### `d3b-ruff-final-v2.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m ruff check src/polisyos/runtime/http/services/control/generation_cycle.py src/polisyos/runtime/http/services/control/run_lifecycle.py src/polisyos/runtime/http/services/control_plane_store.py src/polisyos/runtime/http/routes/control.py src/polisyos/runtime/http/resource_binding.py tests/unit/runtime/http/test_normative_evidence_intake.py tests/unit/runtime/http/test_control_plane_store.py tests/unit/runtime/http/test_runtime_api_authz.py`
- Actual RC: `0`; wall seconds: `0.05996104096993804`.
- Complete stdout/stderr and child environment: [d3b-ruff-final-v2.json](d3b-ruff-final-v2.json).

### `d3b-ruff-final.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m ruff check src/polisyos/runtime/http/services/control/generation_cycle.py src/polisyos/runtime/http/services/control/run_lifecycle.py src/polisyos/runtime/http/services/control_plane_store.py src/polisyos/runtime/http/routes/control.py src/polisyos/runtime/http/resource_binding.py tests/unit/runtime/http/test_normative_evidence_intake.py tests/unit/runtime/http/test_control_plane_store.py tests/unit/runtime/http/test_runtime_api_authz.py`
- Actual RC: `1`; wall seconds: `0.04282208398217335`.
- Complete stdout/stderr and child environment: [d3b-ruff-final.json](d3b-ruff-final.json).

### `d3b-ruff-initial.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m ruff check src/polisyos/runtime/http/services/control/generation_cycle.py src/polisyos/runtime/http/services/control/run_lifecycle.py src/polisyos/runtime/http/services/control_plane_store.py src/polisyos/runtime/http/routes/control.py src/polisyos/runtime/http/resource_binding.py tests/unit/runtime/http/test_normative_evidence_intake.py tests/unit/runtime/http/test_control_plane_store.py`
- Actual RC: `1`; wall seconds: `0.04900783294579014`.
- Complete stdout/stderr and child environment: [d3b-ruff-initial.json](d3b-ruff-initial.json).

### `d3b-source-census.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.d3b_census`
- Actual RC: `0`; wall seconds: `91.87675329099875`.
- Complete stdout/stderr and child environment: [d3b-source-census.json](d3b-source-census.json).

### `d3b-source-head-gates-v2.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_evidence_intake.py -q`
- Actual RC: `1`; wall seconds: `38.21298075001687`.
- Complete stdout/stderr and child environment: [d3b-source-head-gates-v2.json](d3b-source-head-gates-v2.json).

### `d3b-source-head-gates-v3.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_evidence_intake.py -q`
- Actual RC: `0`; wall seconds: `41.221868166991044`.
- Complete stdout/stderr and child environment: [d3b-source-head-gates-v3.json](d3b-source-head-gates-v3.json).

### `d3b-source-head-gates.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_evidence_intake.py -q`
- Actual RC: `1`; wall seconds: `34.52616291702725`.
- Complete stdout/stderr and child environment: [d3b-source-head-gates.json](d3b-source-head-gates.json).

### `d3b-store-cas.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_control_plane_store.py::test_normative_head_compare_and_append_has_one_sqlite_winner -q`
- Actual RC: `0`; wall seconds: `26.314331541012507`.
- Complete stdout/stderr and child environment: [d3b-store-cas.json](d3b-store-cas.json).

### `d3b-test-identities.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.d3b_collect`
- Actual RC: `0`; wall seconds: `78.47893366700737`.
- Complete stdout/stderr and child environment: [d3b-test-identities.json](d3b-test-identities.json).

### `d3c-owned-publication-removal.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.d3b_probe owned_run_publication`
- Actual RC: `1`; wall seconds: `64.50765395798953`.
- Complete stdout/stderr and child environment: [d3c-owned-publication-removal.json](d3c-owned-publication-removal.json).

### `d3c-owned-run-intake.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_evidence_intake.py::test_post_source_signature_advances_both_current_job_readers -q`
- Actual RC: `0`; wall seconds: `34.400347457965836`.
- Complete stdout/stderr and child environment: [d3c-owned-run-intake.json](d3c-owned-run-intake.json).

### `d3d-ruff-final.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m ruff check src/polisyos/runtime/http/services/control/run_lifecycle.py tests/unit/runtime/http/test_normative_generation_bridge.py tests/unit/runtime/http/test_normative_evidence_intake.py`
- Actual RC: `0`; wall seconds: `0.11348324996652082`.
- Complete stdout/stderr and child environment: [d3d-ruff-final.json](d3d-ruff-final.json).

### `d3d-ruff.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m ruff check src/polisyos/runtime/http/services/control/run_lifecycle.py tests/unit/runtime/http/test_normative_generation_bridge.py tests/unit/runtime/http/test_normative_evidence_intake.py`
- Actual RC: `1`; wall seconds: `0.11163183394819498`.
- Complete stdout/stderr and child environment: [d3d-ruff.json](d3d-ruff.json).

### `d3d-semantic-head-attachment-removal.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.d3b_probe head_attachment`
- Actual RC: `1`; wall seconds: `117.34918674995424`.
- Complete stdout/stderr and child environment: [d3d-semantic-head-attachment-removal.json](d3d-semantic-head-attachment-removal.json).

### `d3d-shared-source-delta.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_evidence_intake.py::test_post_source_signature_advances_both_current_job_readers tests/unit/runtime/http/test_normative_evidence_intake.py::test_current_head_survives_shared_progress_copy_and_refuses_owned_source_rebind tests/unit/runtime/http/test_normative_generation_bridge.py::test_every_current_job_reader_replays_persisted_authority -q`
- Actual RC: `0`; wall seconds: `119.40018916700501`.
- Complete stdout/stderr and child environment: [d3d-shared-source-delta.json](d3d-shared-source-delta.json).

### `d3d-source-census.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Exact command: `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.d3b_census`
- Actual RC: `0`; wall seconds: `124.80559941701358`.
- Complete stdout/stderr and child environment: [d3d-source-census.json](d3d-source-census.json).

