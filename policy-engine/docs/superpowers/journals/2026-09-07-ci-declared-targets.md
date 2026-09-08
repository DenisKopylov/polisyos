# CI declared targets — local handback, 2026-09-07

## Intake history — superseded by continuation below

Stopped at intake before the first repair: its binding closure signal is unavailable
in the required source. The user requires reading each row's closure signal before
starting the row and requires processing the rows in order. Supplying that missing
signal requires the architect's transcription or a direct clarification from the
user; this lane cannot invent it or edit `DEBT-REGISTER.md`.

Worktree: `/Users/deniskopylov/polisyos/.worktrees/ci-targets`.
Branch: `codex/ci-declared-targets`.
Slice base: local `main` at `edc104849a9830dd5249390aa5380bd49836490c`.
Created using the exact ordinary-git worktree command from the task. Initial
`git status -sb` reported the attached branch with no changes; before writing this
journal, `git diff --exit-code main HEAD` exited 0 with no output.

The only intended tracked change is this explicitly requested journal. No workflow,
manifest, dependency, source, test, baseline, debt register, or ledger repair was
made. No other lane's worktree or branch was changed. No stash, rebase, push,
GitHub plugin, or GitHub integration was used.

## Plan and pattern pass

1. Establish the isolated base and obtain the binding closure signal for the first
   row. **Blocked on the signal**, as measured below.
2. If that prerequisite is supplied, enumerate the complete workflow target set,
   independently reconcile the denominator, and adjudicate every missing path from
   test content and history before rewriting references. This step has not started.
3. Proceed in the user's listed order, verifying each closure signal and stopping
   at an architect, file, or dependency boundary. This step has not started.
4. Preserve the measured state and hand back locally. This journal is the mandatory
   record, explicitly authorized separately from the mechanism-file allowlist.

Relevant patterns: `P35` (complete denominators), `P36` (a binding finding is not an
adjacent description), `P37`/`P38` (do not substitute a row's name or colour for its
closure property), `P41` (do not attribute a red without its base/input proof).
The failure/repair register was opened during intake and its relevant rows read
again before closeout. Existing issue found: the requested first finding cannot be
resolved in the mandated register at the mandated base. Target pattern: bind repair
and verification to an available closure signal. Its current state is
`not_established`; no product capability state is inferred from this planning gap.
Acceptance for resuming: the architect/user supplies the missing binding signals
and identifies how they apply to this pinned base. No owner is appointed here.

## Measurement stations and artifact set

All measurements here are **local runs**. There is **no CI run available because
this lane does not push**. No row is claimed closed, and no CI job is claimed green.

The artifact denominator is the **one complete Markdown file**
`policy-engine/docs/plans/active/DEBT-REGISTER.md` at the slice base, tested against
**all eight requested debt IDs**. It is readable UTF-8: 599,548 bytes and 1,276 lines
for that one file, SHA-256
`3a28c095b727a8c7c528e3417917ffdb5c0d8b4cccd170e8f6469880625e4472`.

- Station A: Python read the complete worktree file, enumerated every line, matched
  exact IDs in Markdown table first cells outside fences, and separately scanned
  every line for literal occurrences. Result over the eight-ID denominator:
  **one present, seven absent**. The worktree register was byte-equal to
  `git show main:policy-engine/docs/plans/active/DEBT-REGISTER.md`.
- Station B: `git grep -n -F` with each of the eight IDs supplied as a separate `-e`
  walked the complete committed register at the pinned slice base. Result over the
  same eight-ID denominator: **one present, seven absent**. Only the S3 row appeared,
  at line 370. Exit 0 meant a text match, not that any debt was repaired.
- An independent read-only agent separately checked the complete register bytes
  and their equality with local `main`, with the same presence result.

These measurements establish source availability only. The task's historical
`45-of-118` target figures and seven Python overrides have **not been remeasured**.
There is no completed per-path adjudication, no coverage deletion, and no claim
that the workflow target set currently has either historical denominator.

## Current per-row disposition (continuation; supersedes intake)

All receipts are local. No CI run is available because this lane does not push.
The historical intake above remains preserved; these are the current dispositions.

| Requested row | Disposition | Measurement, change, verification, and remainder |
| --- | --- | --- |
| `workflow-test-targets-45-of-118-missing` | **repaired-with-a-limit** | All 45 individually adjudicated below; 44 moved, one renamed, none absent. Rewrote references and added a refusal gate for literal Python test files. Focused run reaches tests: 501 passed, two skipped out of 503 XML cases. Gate deliberately does not expand globs, directory selectors, or computed shell expressions. |
| `generated-artifact-s3-check-target-missing` | **repaired** | Repointed the manifest to the historically renamed substrate-acquisition test. All declared files exist; the exact check now runs and reports a lineage assertion failure, recorded separately. Closure asks that the command run, not that its assertions turn green. |
| `ci-jobs-pin-python-3-11-against-declared-3-14` | **repaired-with-a-limit** | Removed all seven unsupported overrides and added a refusal gate derived from requires-python. Local 3.14 job probes and their causes are recorded below; full runner/CI parity is not established. |
| `typing-ratchets-invokes-a-package-module-as-a-file` | **repaired-with-a-limit** | Changed both package runners to `python -m`. Mypy, basedpyright and ratchet checks execute; local findings are recorded separately. Basedpyright used a bounded file scope, mypy fail-fast; the complete CI typing job is not claimed green. |
| `ripgrep-is-assumed-by-ci-and-provisioned-nowhere` | **repaired-with-a-limit** | Explicit Ubuntu ripgrep setup in both consumer jobs. All five execution consumers fail and name rg with it absent from PATH. Local missing-binary behavior verified; an Ubuntu image/setup run is unavailable. |
| `abi-detector-fails-open-when-its-scan-command-fails` | **repaired** | Actual extracted step with rg absent: base exits 0 and reports changed=false; fixed step exits 127 and emits a named scan error, without skip output. Match/no-match/scan-error are separate outcomes. |
| `abi-detector-watches-prefixes-not-the-import-closure` | **repaired-with-a-limit** | Snapshot validation and ABI comparison are unconditional; the old prefix scan only reports context. Real outside-prefix imported-model witness: old detector skips, new complete check runs and exits 1. Baseline control passes. No CI execution or CI runtime-budget receipt is available. |
| `pillow-is-built-from-source-on-every-ci-run` | **blocked-and-why** | A fresh Python 3.14 wheel-only install of locked Pillow 10.4.0 fails with no usable wheel. marker-pdf is already optional; the shared lock still selects Pillow 10.4.0 for ML consumers. A dependency-policy decision and uv.lock refresh exceed this lane. No dependency edit. |

The S3 row's exact closure signal, finding
`generated-artifact-s3-check-target-missing`:

> the family's `check_command` resolves to files that exist and the command runs, or the family is retired with a reason

The row identifies family `policy-design-case-layer2-s3-governed-capability-rows`
in `architecture/generated_artifacts.toml`. Its presence does not authorize skipping
the required first row.

## Verification and limits

- Every gate invocation was a standalone command; none appended `echo` or another
  command that could mask its exit status.
- `actionlint` was invoked with no workflow filenames from the repository root,
  requesting discovery. Local result: **exit 127**,
  `zsh:1: command not found: actionlint`. This is a tooling non-receipt, not a lint
  pass or a repository finding. The checker never enumerated workflows.
- No pytest run was appropriate to a journal-only intake stop; no directory-wide
  pytest, backend suite, or CI-parity run was performed.
- No product red is classified as inherited. The source-availability finding was
  measured directly on the slice base before any write and cross-checked against
  the committed blob. No zero-intersection claim is used to excuse an unrun gate.
- The task sentence remains the intended mechanism: “a declared target must name
  something that exists, and a job must provision what it invokes.” Supplying a
  missing register closure signal is an intake repair, not a CI repair under that
  sentence. This journal does not stretch the mechanism to claim otherwise.

## Proposed architect follow-up — declined by user

Proposed row: `ci-declared-targets-task-register-source-mismatch`.
Proposed owner: `team-architecture` (a proposal, not an appointment).
Disposition: **declined** in the continuation; a task-text defect, not repository debt.
The missing rows were committed at `ba95b6c8a`; this proposal has no register home.
Finding: the eight-row task names seven IDs absent from its mandated register at
its mandated local-main base, including its required first row. The one present ID
is the S3 finding identified above. This blocks reading binding closure signals
before repairs, as explicitly required by the task.
Proposed closure: supply the missing binding row definitions, or explicitly amend
the task to supply their authoritative closure signals directly, with an identified
base. Architect transcribes; this lane edits neither register nor ledger.

The missing local `actionlint` binary is recorded as an environment provisioning
non-receipt, not proposed as a new CI debt: it establishes nothing about runner
provisioning. No lost-coverage proposals are manufactured without adjudicating
coverage.

## Reproduction of source availability

Run this single command from the worktree root. It walks the full file and derives
the comparison count independently from git's fixed-string scan of the full base
blob; read the emitted presence set rather than interpreting exit 0 as closure.

```bash
python3 - <<'PY'
from pathlib import Path
import hashlib
import subprocess

base = "edc104849a9830dd5249390aa5380bd49836490c"
path = "policy-engine/docs/plans/active/DEBT-REGISTER.md"
ids = [
    "workflow-test-targets-45-of-118-missing",
    "generated-artifact-s3-check-target-missing",
    "ci-jobs-pin-python-3-11-against-declared-3-14",
    "typing-ratchets-invokes-a-package-module-as-a-file",
    "ripgrep-is-assumed-by-ci-and-provisioned-nowhere",
    "abi-detector-fails-open-when-its-scan-command-fails",
    "abi-detector-watches-prefixes-not-the-import-closure",
    "pillow-is-built-from-source-on-every-ci-run",
]
data = Path(path).read_bytes()
lines = data.decode("utf-8").splitlines()
present_a = {debt_id for debt_id in ids if any(debt_id in line for line in lines)}
command = ["git", "grep", "-n", "-F"]
for debt_id in ids:
    command.extend(["-e", debt_id])
command.extend([base, "--", path])
result = subprocess.run(command, capture_output=True, text=True, check=False)
if result.returncode not in (0, 1):
    raise RuntimeError(result.stderr)
present_b = {debt_id for debt_id in ids if debt_id in result.stdout}
base_data = subprocess.check_output(["git", "show", f"{base}:{path}"])
assert data == base_data, "Register differs from measured base; remeasure."
assert present_a == present_b, "Independent presence stations disagree."
print("Denominator: all", len(ids), "requested IDs over one complete Markdown register")
print("File bytes:", len(data), "lines:", len(lines))
print("SHA256:", hashlib.sha256(data).hexdigest())
for debt_id in ids:
    print(debt_id, "present" if debt_id in present_a else "absent")
print("Present:", len(present_a), "absent:", len(ids) - len(present_a))
PY
```

## Continuation from local main d2f2dffe4

The user supplied the missing rows and authorized an ordinary merge. `git merge main`
completed cleanly, retaining the intake commit. This continuation's code base is
`d2f2dffe47757898a016cad7671a2cec39035e45`; the merge also carries the architect's
ledger/tool changes as base history, not this lane's repairs. No ledger contents
were read and no debt-ledger instrument was run.

The corrected ordering rule is in force: record an individually blocked row and
continue to the next available one; systemic unavailability still stops the lane.
The intake table above is historical until replaced with final continuation
dispositions below.

Plan: adjudicate the complete first-row target set from current tests and local
history, rewrite verified destinations, and wire an existence gate in the existing
Fast PR workflow-governance job. The existing workflow-policy checker checks
action/governance conventions but does not check test-file existence; its canonical
implementation is in the forbidden tools lane. A small supplemental checker under
`.github/scripts/` fits the authorized CI surface and requires only the standard
library. Gate acceptance is a real invocation refusing a nonexistent target, plus
a complete clean target census; test outcomes remain separately reported. Proceed
through subsequent rows in listed order with per-row binding acceptance.

Shared write surfaces: root owns workflows, manifests and this journal. Delegated
readers own no tracked files. Test/history censuses run independently; environment
provisioning and checks that share the local venv are serialized. Relevant patterns
remain P29/P35/P37/P38/P41; the gate recomputes existence and does not infer coverage
from existence. No product capability is added.

Pre-change local census: all **19 files under `.github/`** contain **118 unique
literal Python test-file references**, of which **45 are absent** relative to
`policy-engine/`. Independent git-tracked shell-token census agrees on 118/45 and
records the separate existing glob selector. The first station walked the full
filesystem; the second used `git ls-files` and tokenization. The test source corpus
for content adjudication is all **2,502 tracked `.py` files under
`policy-engine/tests/`**, not filenames sampled for similarity.

Local actionlint baseline: `command -v shellcheck` resolved
`/opt/homebrew/bin/shellcheck`;
`pre-commit run actionlint --all-files --config policy-engine/.pre-commit-config.yaml`
printed `Passed`, exit 0. This supersedes the direct-PATH non-receipt as the current
lint baseline; it is not CI evidence.

### Row 1 — individual target adjudication

All 45 originally absent literal paths are adjudicated: **44 moved, one renamed,
zero absent, zero ambiguous** (denominator: all 45 missing members of the 118-path
pre-change `.github/` literal Python-test set). Each historical test-function name
was checked against its current file after the independent history/content review.
No reference was deleted, and no test file was written. No lost-coverage proposal
is required by this disposition.

`7acba2e4e` often rewrote workflows to a nonexistent `unit/` intermediate while
moving the real source elsewhere. The predecessor column records the actual
pre-move source, not that invalid intermediate. `fcafac435` then reorganized
Scientist subpackages. C7 retains all six historical tests, including the lifelines
skip conditions; API retains all fifteen historical methods and adds evaluation-
safety assertions. The API-absence sentence in the registered finding is refuted
by this history/content measurement; the architect can correct the register.

| Original absent reference | Disposition | Workflow destination | Historical predecessor and move | Current retained test witness |
| --- | --- | --- | --- | --- |
| `tests/tools/test_fabric_schema_governance.py` | moved | `tests/repo_quality/tools/test_fabric_schema_governance.py` | `fcafac435` R100; `tests/tools/test_fabric_schema_governance.py` | `test_breaking_change_requires_approved_major_bump_metadata` |
| `tests/unit/common/test_serialization_properties.py` | moved | `tests/property/common/test_serialization_properties.py` | `7acba2e4e` R099; `tests/common/test_serialization_properties.py` | `test_fast_json_loads_rejects_malformed_bytes` |
| `tests/unit/runtime/http/test_access_invariants_properties.py` | moved | `tests/property/runtime/http/test_access_invariants_properties.py` | `7acba2e4e` R099; `tests/runtime/http/test_access_invariants_properties.py` | `test_enforce_artifact_tenant_access_respects_tenant_invariants` |
| `tests/unit/scientist/autotune/test_calibration_autotune.py` | moved | `tests/unit/scientist/methods/autotune/test_calibration_autotune.py` | `fcafac435` R097; `tests/unit/scientist/autotune/test_calibration_autotune.py` | `test_apply_to_config_uses_branch_local_nested_model_clones` |
| `tests/unit/scientist/autotune/test_execution_plan_autotune.py` | moved | `tests/unit/scientist/methods/autotune/test_execution_plan_autotune.py` | `fcafac435` R098; `tests/unit/scientist/autotune/test_execution_plan_autotune.py` | `test_backend_for_method_does_not_swallow_assertion` |
| `tests/unit/scientist/autotune/test_registry_and_runner.py` | moved | `tests/unit/scientist/methods/autotune/test_registry_and_runner.py` | `fcafac435` R095; `tests/unit/scientist/autotune/test_registry_and_runner.py` | `test_autotune_persistence_helpers_accept_protocol_backed_store` |
| `tests/unit/scientist/backtesting/test_bootstrap.py` | moved | `tests/unit/scientist/methods/backtesting/test_bootstrap.py` | `fcafac435` R097; `tests/unit/scientist/backtesting/test_bootstrap.py` | `test_empty_values` |
| `tests/unit/scientist/backtesting/test_distributional.py` | moved | `tests/unit/scientist/methods/backtesting/test_distributional.py` | `fcafac435` R092; `tests/unit/scientist/backtesting/test_distributional.py` | `test_autocorrelated_data` |
| `tests/unit/scientist/backtesting/test_ipw.py` | moved | `tests/unit/scientist/methods/backtesting/test_ipw.py` | `fcafac435` R097; `tests/unit/scientist/backtesting/test_ipw.py` | `test_basic_ate` |
| `tests/unit/scientist/backtesting/test_masking.py` | moved | `tests/unit/scientist/methods/backtesting/test_masking.py` | `fcafac435` R088; `tests/unit/scientist/backtesting/test_masking.py` | `test_masking_raises_when_intervention_step_exceeds_metric_horizon` |
| `tests/unit/scientist/compute/test_advanced_methods_c7.py` | renamed | `tests/unit/scientist/methods/test_advanced.py` | `fcafac435` R097; `tests/unit/scientist/compute/test_advanced_methods_c7.py` | `test_bilevel_c7_bundle_roundtrip_with_new_params` |
| `tests/unit/scientist/engine/locks/test_dynamodb_lock.py` | moved | `tests/unit/scientist/orchestration/engine/locks/test_dynamodb_lock.py` | `fcafac435` R096; `tests/unit/scientist/engine/locks/test_dynamodb_lock.py` | `test_acquire_contention_raises` |
| `tests/unit/scientist/engine/locks/test_fcntl_lock.py` | moved | `tests/unit/scientist/orchestration/engine/locks/test_fcntl_lock.py` | `fcafac435` R078; `tests/unit/scientist/engine/locks/test_fcntl_lock.py` | `test_acquire_and_release` |
| `tests/unit/scientist/engine/locks/test_lock_metrics.py` | moved | `tests/unit/scientist/orchestration/engine/locks/test_lock_metrics.py` | `fcafac435` R094; `tests/unit/scientist/engine/locks/test_lock_metrics.py` | `test_measure_acquire_does_not_swallow_assertion_errors` |
| `tests/unit/scientist/engine/locks/test_redis_lock.py` | moved | `tests/unit/scientist/orchestration/engine/locks/test_redis_lock.py` | `fcafac435` R092; `tests/unit/scientist/engine/locks/test_redis_lock.py` | `test_acquire_failure_raises` |
| `tests/unit/scientist/engine/runner/test_activity_worker.py` | moved | `tests/unit/scientist/orchestration/engine/runner/test_activity_worker.py` | `fcafac435` R091; `tests/unit/scientist/engine/runner/test_activity_worker.py` | `test_build_worker_context_bootstraps_registry_bundle_when_missing` |
| `tests/unit/scientist/engine/runner/test_worker_pool.py` | moved | `tests/unit/scientist/orchestration/engine/runner/test_worker_pool.py` | `fcafac435` R087; `tests/unit/scientist/engine/runner/test_worker_pool.py` | `test_capacity_defaults` |
| `tests/unit/scientist/engine/test_async_executor.py` | moved | `tests/unit/scientist/orchestration/engine/test_async_executor.py` | `fcafac435` R094; `tests/unit/scientist/engine/test_async_executor.py` | `test_async_executor_persists_via_async_artifact_store_adapter` |
| `tests/unit/scientist/engine/test_budget_middleware.py` | moved | `tests/unit/scientist/orchestration/engine/test_budget_middleware.py` | `fcafac435` R097; `tests/unit/scientist/engine/test_budget_middleware.py` | `test_alert_at_80` |
| `tests/unit/scientist/engine/test_fan_out_async.py` | moved | `tests/unit/scientist/orchestration/engine/test_fan_out_async.py` | `fcafac435` R097; `tests/unit/scientist/engine/test_fan_out_async.py` | `test_async_bind_failure_emits_degraded_event` |
| `tests/unit/scientist/engine/test_metrics_slo.py` | moved | `tests/unit/scientist/orchestration/engine/test_metrics_slo.py` | `fcafac435` R091; `tests/unit/scientist/engine/test_metrics_slo.py` | `test_accepts_injected_metrics_registry` |
| `tests/unit/scientist/engine/test_operational_monitoring.py` | moved | `tests/unit/scientist/orchestration/engine/test_operational_monitoring.py` | `fcafac435` R093; `tests/unit/scientist/engine/test_operational_monitoring.py` | `test_classify_metric_alert_maps_fairness_and_calibration` |
| `tests/unit/scientist/engine/test_retry.py` | moved | `tests/unit/scientist/orchestration/engine/test_retry.py` | `fcafac435` R093; `tests/unit/scientist/engine/test_retry.py` | `test_backoff_base_bounds` |
| `tests/unit/scientist/integration/test_workflow_reliability_scenarios.py` | moved | `tests/integration/scientist/test_workflow_reliability_scenarios.py` | `7acba2e4e` R096; `tests/scientist/integration/test_workflow_reliability_scenarios.py` | `test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes` |
| `tests/unit/scientist/llm/test_budget_enforcer.py` | moved | `tests/unit/scientist/orchestration/llm/test_budget_enforcer.py` | `fcafac435` R095; `tests/unit/scientist/llm/test_budget_enforcer.py` | `test_accepts_injected_metrics_and_operational_monitor` |
| `tests/unit/scientist/llm/test_factory.py` | moved | `tests/unit/scientist/orchestration/llm/test_factory.py` | `fcafac435` R093; `tests/unit/scientist/llm/test_factory.py` | `test_create_traced_gateway_client_accepts_injected_observability` |
| `tests/unit/scientist/llm/test_gateway_client_retry.py` | moved | `tests/unit/scientist/orchestration/llm/test_gateway_client_retry.py` | `fcafac435` R098; `tests/unit/scientist/llm/test_gateway_client_retry.py` | `test_400_not_retryable` |
| `tests/unit/scientist/test_api.py` | moved | `tests/unit/scientist/facade/test_api.py` | `7acba2e4e` R099; `tests/scientist/test_api.py` | `test_auto_generates_run_id` |
| `tests/unit/scientist/test_checkpoint.py` | moved | `tests/unit/scientist/orchestration/engine/test_checkpoint.py` | `7acba2e4e` R099; `tests/scientist/test_checkpoint.py` | `test_checkpoint_head_invalid_json_raises_typed_error` |
| `tests/unit/scientist/test_code_verifier.py` | moved | `tests/unit/scientist/agent/test_code_verifier.py` | `7acba2e4e` R098; `tests/scientist/test_code_verifier.py` | `test_apply_resource_limits_import_assertion_is_not_swallowed` |
| `tests/unit/scientist/test_cross_graph_evidence.py` | moved | `tests/unit/scientist/cross_graph/test_cross_graph_evidence.py` | `7acba2e4e` R099; `tests/scientist/test_cross_graph_evidence.py` | `test_academic_gatherer_does_not_use_edge_prior_for_parameter_needs` |
| `tests/unit/scientist/test_decision_validity_service.py` | moved | `tests/unit/scientist/validation/test_decision_validity_service.py` | `7acba2e4e` R099; `tests/scientist/test_decision_validity_service.py` | `test_decision_validity_service_accepts_protocol_store_proxy` |
| `tests/unit/scientist/test_error_semantics.py` | moved | `tests/unit/scientist/orchestration/engine/test_error_semantics.py` | `7acba2e4e` R096; `tests/scientist/test_error_semantics.py` | `test_emit_degraded_path_accepts_stdlib_logger` |
| `tests/unit/scientist/test_fabric_bridge.py` | moved | `tests/unit/scientist/adapters/test_fabric_bridge.py` | `7acba2e4e` R099; `tests/scientist/test_fabric_bridge.py` | `test_default_fabric_port_enforces_execution_tier_from_injected_catalog_store` |
| `tests/unit/scientist/test_idempotency.py` | moved | `tests/unit/scientist/orchestration/engine/test_idempotency.py` | `7acba2e4e` R100; `tests/scientist/test_idempotency.py` | `test_compute_idempotency_key_available_for_all_builtin_nodes` |
| `tests/unit/scientist/test_informed_critic.py` | moved | `tests/unit/scientist/agent/test_informed_critic.py` | `7acba2e4e` R100; `tests/scientist/test_informed_critic.py` | `test_informed_critic_accepts_injected_observability` |
| `tests/unit/scientist/test_knowledge_base.py` | moved | `tests/unit/scientist/agent/test_knowledge_base.py` | `7acba2e4e` R100; `tests/scientist/test_knowledge_base.py` | `test_knowledge_base_accepts_injected_metrics` |
| `tests/unit/scientist/test_llm_cycle_preflight.py` | moved | `tests/unit/scientist/orchestration/llm/test_llm_cycle_preflight.py` | `7acba2e4e` R099; `tests/scientist/test_llm_cycle_preflight.py` | `test_evaluator_supports_all_verdict_paths` |
| `tests/unit/scientist/test_norm_loader.py` | moved | `tests/unit/scientist/agent/test_norm_loader.py` | `7acba2e4e` R099; `tests/scientist/test_norm_loader.py` | `test_cas_norm_loader_assertion_is_not_swallowed` |
| `tests/unit/scientist/test_rag_index.py` | moved | `tests/unit/scientist/agent/test_rag_index.py` | `7acba2e4e` R099; `tests/scientist/test_rag_index.py` | `test_build_or_load_rag_index_load_assertion_is_not_swallowed` |
| `tests/unit/scientist/test_reliability_operational_evidence.py` | moved | `tests/unit/scientist/orchestration/engine/test_reliability_operational_evidence.py` | `7acba2e4e` R099; `tests/scientist/test_reliability_operational_evidence.py` | `test_bounded_retention_operational_signal` |
| `tests/unit/scientist/test_reliability_scorecard.py` | moved | `tests/unit/scientist/governance/test_reliability_scorecard.py` | `7acba2e4e` R098; `tests/scientist/test_reliability_scorecard.py` | `test_scientist_reliability_scorecard_from_evidence_maps_required_cases` |
| `tests/unit/scientist/test_remediation_status.py` | moved | `tests/unit/scientist/facade/test_remediation_status.py` | `7acba2e4e` R098; `tests/scientist/test_remediation_status.py` | `test_scientist_remediation_status_report_covers_all_workstreams` |
| `tests/unit/scientist/test_replay_backend.py` | moved | `tests/unit/scientist/replay/test_replay_backend.py` | `7acba2e4e` R098; `tests/scientist/test_replay_backend.py` | `test_list_dead_letters_filters_by_run_and_alias` |
| `tests/unit/scientist/workflows/test_builder_pinning.py` | moved | `tests/unit/scientist/orchestration/workflows/test_builder_pinning.py` | `fcafac435` R095; `tests/unit/scientist/workflows/test_builder_pinning.py` | `test_artifact_ref_or_none_assertion_is_not_swallowed` |

### Continuation verification stations — rows 1 through 6

The local interpreter is Python 3.14.0. `uv sync --frozen --extra lint --extra test
--extra runtime --extra ml` provisioned the worktree environment successfully after
an offline attempt correctly refused an uncached wheel. A separate ignored job
probe environment uses the union of lint/test/runtime/ml/docs/mutation/
causal-discovery/sandbox/security extras. Its sync completed. This union is a local
execution aid, not proof of each job's exact dependency profile. No lockfile changed.

Row 1 station: `python3 .github/scripts/check_declared_test_targets.py --repo-root .`
walks every non-cache declaration file and normalizes root/product-prefixed literal
Python test paths. At the current patch: 23 declaration files, 118 unique literal
Python file targets, zero missing out of 118. The independent git-index/token
census and final reconciliation are recorded in the closeout below. Baseline
refusal was 45 missing out of the same 118 targets (exit 1). Negative fixtures:
missing literal and `./tests/` target both exit 1; invalid UTF-8 exits 2 (undecidable),
existing target exits 0. The gate refuses symlink directories rather than silently
not walking them. A directory/glob/expression is outside this literal-file gate's
claimed denominator; the existing `test_honest_diagnostics*.py` glob is not counted
as a missing literal file.

Exact focused execution, from `policy-engine`, was:
`uv run --no-sync pytest -q @_build/.tmp/ci-declared-targets/rewritten-targets.txt
--junitxml=_build/.tmp/ci-declared-targets/rewritten-targets.xml`.
The argfile contains precisely the 45 adjudicated destinations, not a directory.
Exit 0; XML duration 1132.197 seconds. The XML accounts for 503 cases: 501 passed,
one DynamoDB module-level skip for absent boto3, and one alerting-rule fixture skip.
Only 44 of the 45 targeted modules executed passing cases in this run. The SLO
skip is a misplaced relative lookup under tests/ops, not absence of the real
policy-engine/ops rule; see the proposed fixture-root debt.
These are retained coverage with local limitations, not absent test files.

Row 2 station: complete TOML family record and all three explicit pytest paths,
plus historical content comparison (`584bd7b72`) of the renamed test and its producer.
The family now invokes:
`uv run pytest tests/unit/core/contracts/test_capability_resolution.py
 tests/unit/runtime/quality/test_capability_resolver.py
 tests/unit/runtime/quality/test_design_axes_substrate_acquisition.py -q`.
Executed this command with `UV_NO_SYNC=1` after provisioning; exit 1. The failure is
`test_s3_substrate_consumes_g1_grounded_binding_through_existing_resolver_port`:
`CapabilityBindingResult.lineage_refs` is empty at the assertion. This proves the
manifest now reaches the intended test. It does not prove a functioning substrate
capability, and no source/test repair or family retirement is made.

Row 3 station: `.github/scripts/check_python_versions.py` parses all YAML under
`.github`, reads the project `requires-python`, follows the local setup action's
default and `.python-version`, and checks static matrix/include versions. Unsupported
or undecidable values fail closed. It reads the declared range rather than embedding
3.14 as the allowed range. Workflow governance provisions its Python interpreter
and PyYAML/packaging dependencies explicitly. The original checker run rejected
all seven bad overrides; removing them makes the declaration check pass. Fixtures
cover unsupported literals, matrix/include members, local defaults, version files,
unresolved expressions, malformed values and YAML merge aliases. Job execution
receipts remain a separate station; see the per-job table below.

Row 4 station: AST-read all file-invoked Python targets in `.github` YAML for
relative imports. The two affected existing package runners are
`tools.devx.workspace.core_runtime_mypy` and
`tools.devx.workspace.core_runtime_basedpyright`. The old mypy file invocation was
replayed locally and raises `ImportError: attempted relative import with no known
parent package` (exit 1). Module invocation with `--fail-fast` reaches real mypy:
`src/polisyos/common/timestamps.py` requires missing pandas stubs (exit 1).
Module-based basedpyright with explicit `src/polisyos/common/logger.py` reaches
basedpyright (exit 0), but its configured automatic baseline update rewrote the
baseline. That zero is **not** a full typing pass. The unrequested diff was saved as
ignored scratch evidence and only that tool-generated change was replaced with the
original HEAD bytes. No baseline change is delivered. The actual ratchet command
`uv run --no-sync python tools/quality/validation/check_ci_ratchets.py` exits 1
with suppression/cache findings and stale allowlist entries. Its implementation
returns 1 for findings; this is not report-only output masquerading as a pass.

Rows 5/6 station: independent filesystem and git-index-plus-untracked enumeration
of every non-cache file under `.github` and `policy-engine/tools` agreed on the
549-file denominator and the same seven rg-token lines in four files. The execution
consumer denominator is five: ABI scan, Python Fabric baseline scan, and each of
three Fabric ban scans, across two CI jobs. The local action installs ripgrep via
apt and checks `rg --version` before those consumers. Fabric ban scans now use
`require_no_matches.sh`: a match exits 1, no match exits 0, scan error preserves a
nonzero error, and missing rg names the binary and exits 127. Its action/helper
paths are included in Fabric workflow triggers.

All five consumers were run with `PATH=/usr/bin:/bin` (rg absent): ABI and each
Fabric ban step exit 127; Python baseline consumer exits 1 with FileNotFoundError
naming rg. This is a local job-step simulation on macOS, **not** a clean Ubuntu
image or CI run. With real rg, a nonexistent scan input exits 2, forbidden text
exits 1, and an established no-match scan exits 0. The actual ABI baseline step
extracted from `d2f2dffe4` reports changed=false and exits 0 under missing rg; the
fixed step exits 127 without writing changed=false. No echo command masks status.
The prefix scan is retained as diagnostic context only in row 7; its result no
longer controls snapshot validation. Its errors still fail the job.

An adjacent declared-target defect was found while executing Fabric's Python scan:
its default repository root resolves to `policy-engine/tools`, so the original
workflow command tries to scan `tools/src/polisyos/fabric` and exits 2. Passing
`--repo-root .` from the workflow corrects the invocation within this lane. It now
reaches an actual broad-exception baseline drift (exit 1), not a directory error.
No tool or baseline was changed.

All reds here are **observed, provenance not established**. This journal does not
call any red inherited: the exact source checks have not been replayed from the
original slice base `edc104849a9830dd5249390aa5380bd49836490c` with a complete,
zero-intersection input proof. The continuation base is `d2f2dffe4`; it must not be
substituted for that older slice base to excuse our own changes. Runtime failures
are not repaired by changing workflow colour. Their proposed owners below are
proposals for the architect, not appointments.

### Row 8 — dependency boundary and stop

Binding finding `pillow-is-built-from-source-on-every-ci-run` was read before this
row. The complete parsed project and lockfile were inspected for Pillow dependency
edges, not a sampled setup job. `table-extraction` already contains optional
`marker-pdf>=0.3.0`; `uv.lock` selects marker-pdf 1.10.2 and Pillow 10.4.0. Other
locked incoming Pillow edges include matplotlib and sentence-transformers, so
omitting the already optional table-extraction extra does not remove Pillow from
the ML environment. The actual earlier environment sync built Pillow 10.4.0.
No count of all available package releases or published platform wheels is claimed.

Local negative receipt in a fresh 3.14 environment and separate empty cache:
`uv pip install --python _build/.tmp/ci-declared-targets/wheel-probe-env/bin/python
--cache-dir _build/.tmp/ci-declared-targets/wheel-probe-cache
--only-binary=:all: pillow==10.4.0`.
Exit 1: “pillow==10.4.0 has no usable wheels”; source builds explicitly disabled.
This single required-member failure falsifies a wheel-only installation of the
currently locked dependency set. It is not a wheel census or an Ubuntu-image run.

Stop boundary: choosing to remove/replace/constrain the table-extraction dependency
has wider product consequences, and changing the locked selection requires
`policy-engine/uv.lock`, outside the allowed files. The setup action uses
`uv sync --frozen`; changing only pyproject would not deliver an honestly locked
wheel-only environment. No override, cap bump, dependency removal, lockfile change,
or extra system-header workaround is made. Proposed next decision belongs to the
architect with `team-devx` and the table-extraction capability owner. That is a
proposed consultation, not an owner appointment. Already-running row verification
is completed before handback; no new debt row is started beyond the owned set.

### Incidental findings for architect transcription

These are proposed rows/owners, not register edits or owner appointments. None of
the following reds is labelled inherited without the required slice-base replay
and complete disjoint-input proof. Each needs its own investigation/closure scope.

| Proposed row | Proposed owner | Finding and proposed closure |
| --- | --- | --- |
| `s3-grounded-capability-binding-loses-lineage` | `team-architecture` with runtime-quality owner | Manifest's intended test now executes and fails its nonempty lineage_refs assertion. Diagnose the real resolver/producer and make the semantic test pass without weakening it. |
| `typing-runtime-missing-pandas-stubs` | `team-devx` | Package invocation reaches mypy, which rejects the untyped pandas import in common/timestamps.py. Establish the intended typing dependency/profile or typed boundary and rerun the typing check. |
| `typing-local-check-rewrites-shared-baseline` | `team-devx` | Bounded basedpyright invocation reported an automatic baseline rewrite and exit 0. Separate baseline maintenance from a read-only verification invocation, and prove verification cannot silently ratchet its evidence. No baseline edit delivered here. |
| `core-runtime-ratchet-findings-after-invocation-repair` | `team-core-runtime` with `team-devx` | Actual check_ci_ratchets.py returns 1 with unallowlisted suppressions/cache findings and stale allowlist entries; e.g. runtime/quality/grounding_bind.py `_replay_cache`. Adjudicate the emitted findings against their owning sources rather than treating invocation repair as a typing pass. Full local log: `_build/.tmp/ci-declared-targets/ratchets.log`. |
| `fabric-baseline-command-defaults-to-tools-root` | `team-devx` with `team-fabric` | Observed wrong effective scan root and exit 2. **Workflow invocation repaired in this patch** with explicit --repo-root .; tool-default semantics remain with its owner. The intended scan must reach Fabric source. |
| `fabric-broad-exception-baseline-drift` | `team-fabric` | Correctly rooted baseline scan reaches source and exits 1 on a count/digest mismatch. Review current matches and their semantics; no baseline refresh is authorized here. |
| `scientist-slo-alerting-test-skips-after-relocation` | `team-scientist` with observability owner | The moved metrics/SLO test resolves parents[4] under tests/ops and skips, while the real policy-engine/ops alert rule exists. Repair the fixture-root lookup and exercise the alert-rule assertion; it must not pass by skipping. |
| `docs-contract-links-target-excluded-pages` | `team-docs` with `team-devx` | Python 3.14 docs accuracy command reaches its checks and exits 1, reporting links to excluded ADR-048, ATLAS_SOURCE_OF_TRUTH and policy-operations-research-pipeline pages. Reconcile link/publication contracts; no docs repair in this lane. |
| `mutation-subset-uses-removed-mutmut-cli-options` | `team-devx` with `team-core-runtime` | Locked mutmut rejects --paths-to-mutate (exit 2) before mutation execution. Port the subset selection/runner to the installed CLI and prove the same intended source/test scope; not repaired incidentally here. |
| `scientist-phase1-live-deep-copy-hot-path` | `team-scientist` | Full local Phase 1 evidence gate exits 1 after passing tests/benchmarks; no_live_model_copy_deep_true_hot_paths is false, naming methods/doe/uncertainty.py:985. Adjudicate and repair the live copy path or its governed evidence separately. |

The row-1 register sentence asserting the Scientist API coverage is absent needs
architect correction: its predecessor/move and retained test evidence are in the
45-path table. That is a factual correction to an existing finding, not a new
lost-coverage row. All 45 references were retained by exact substitution.

### Final independent reconciliation and review

The independent final target station used both filesystem parsing and a separate
`rg` extraction across all 23 final `.github` declaration files: 118 unique literal
Python test targets, 181 occurrences, zero absent. Baseline all 19 declaration
files also contain 181 occurrences. Comparing the complete per-file reference
multisets proves the only changes are the exact 45-path substitution: no reference
was silently removed or added. The 45-entry mapping independently totals 44 moved
and one renamed, agreeing with the durable table above. XML suite totals reconcile
to its 503 testcase nodes: 501 passing outcomes, one actual testcase skip and one
synthetic module-collection skip, zero failures/errors. Logs are not used to equate
quiet pytest dots with executed modules.

The independent version station walks all 17 final YAML files and reconciles the
32 checked candidates: 28 local Policy setup call sites, two setup-python call
sites, one local action default and the canonical version file. All resolve to
3.14. Both stations agree on zero invalid/undecidable candidates out of those 32.
No dynamic external workflow-input or arbitrary shell interpreter override is
claimed covered. Unknown static expressions are refused, not silently allowed.

Independent source review found no blocking defect in exact path substitutions,
S3 target selection, provisioning order, scan failure handling, or unconditional
ABI step wiring. Negative target fixtures still reject a missing normalized path
(exit 1) and unreadable declaration (exit 2); negative version fixtures reject
matrix/include/version-file/unresolved values (exit 1). The final ABI diagnostic
step with missing rg still exits 127; with an unchanged actual git comparison it
reports changed=false as context and does not control validation.

Standalone local closeout checks:
- `pre-commit run actionlint --all-files --config policy-engine/.pre-commit-config.yaml`
  from repo root: Passed, exit 0, shellcheck present at /opt/homebrew/bin/shellcheck.
- `.venv/bin/python -m ruff check ../.github/scripts`: exit 0, All checks passed.
- `shellcheck .github/scripts/require_no_matches.sh`: exit 0.
- `python3 policy-engine/tools/ci/check_workflow_policy.py --repo-root . --summary
  policy-engine/_build/.tmp/ci-declared-targets/workflow-policy-summary.md`: exit 0;
  read back the emitted summary rather than treating silence as its verdict.
- `git diff --check`: exit 0.

No directory-wide pytest, debt-ledger checker, CI-parity/full-backend suite, GitHub
integration, push, rebase or stash was used. The debt register and ledger were not
edited; the ledger was not read during continuation. Tracked test/source/tool and
baseline files remain unchanged by this lane. The scratch copy used for the ABI
falsifier is isolated and never changes the source worktree's model.

### Row 7 — real imported-model falsifier

The actual dependency is `TransportabilityResult.p_star_values` in
`src/polisyos/ir/analytics/transportability.py`, importing `PStarZResult` via
`data_forge.read_api.catalog`; the class is defined in
`src/polisyos/data_forge/domains/catalog/knowledge/types.py`. The latter is outside
all four previously watched source prefixes. `CausalEffectReport` also consumes
that transportability result transitively. This is a real existing dependency,
not an invented marker or a probe placed inside a watched directory.

The workflow now runs setup, full snapshot correctness check, generation, baseline
extraction and semantic comparison without `abi_scope` conditions. The old scan
remains a direct-path diagnostic in the step summary; its no-match output cannot
skip validation, and its errors still fail. A new unconditional invocation of the
existing `gen_schema.py --check` recomputes the full schema payload. No import
closure engine or hand-maintained replacement scope is introduced.

Local isolated witness repository:
`policy-engine/_build/.tmp/ci-declared-targets/abi-import-witness`, prepared from
source ref `c32d1e2d6ce389793b8341c3e906934344f993ca` (the continuation merge).
The scoped archive excludes the ledger. Dependency wheels come from the already
provisioned local environment, while PYTHONPATH resolves the scratch source tree.
The real worktree's source/test/tool/snapshot files are unchanged.

- Scratch control commit `65426daa0e17fefcce5100cc5b7e6feb80b5aced`: exact
  `uv run --extra ml python tools/quality/diagnostics/gen_schema.py --check`, with
  UV_NO_SYNC=1 and the isolated source path, exits 0. It reports full scanning of
  all 101 selected ABI models; independent registry/manifest enumeration agrees
  on that 101-model denominator. Wall time 202.29 seconds.
- Scratch witness commit `16bc24ee613783ac1f8b021d102c92d1188987e7`: the sole changed
  path is the outside-prefix `data_forge/domains/catalog/knowledge/types.py`.
  Change `PStarZResult.canonical_variable` from str to int, retaining snapshots.
- Run the **actual old detector step** on that commit pair: exit 0,
  `changed=false`. The old job would skip.
- Run the **same complete check command** at the witness: exit 1, wall time
  95.24 seconds. It specifically identifies stale `causal_effect_report.schema.json`,
  `transportability_result.schema.json`, and `ir/_manifest.json`. The complete log
  was read; the red is actual recomputation, not a marker or prefix assertion.
  Default workflow failure semantics make this mandatory step fail the job.

This is local green-control/red-witness evidence, not CI. The measured full check
fits the job's 20-minute budget locally, but dependency setup plus generation and
semantic diff have not been timed on an Ubuntu CI runner; row 7 remains
repaired-with-a-limit on that runtime receipt. No claim is made that the separate
ABI comparator proves every nested-definition/version-bump policy. This repair
ensures a stale imported schema cannot bypass the declared snapshot check.

### Python 3.14 post-change job states

Denominator: the seven jobs whose explicit 3.11 override was removed, independently
matched between the baseline YAML call-site inventory and the seven edited lines.
All executions below use the isolated 3.14 union environment described above;
`uv run --no-sync` preserves it. The executable command body was extracted from
each job; setup mkdir was performed separately so each invocation contains only
its gate. Benchmark output was directed to ignored scratch. This is local command
execution, not an assertion that all seven GitHub jobs ran or that their individual
runner/profile setup is proved. Remaining steps after a failed mandatory step are
not needed to explain the corresponding job's red.

| Job | Local post-change state and cause |
| --- | --- |
| `runtime-contracts` | **Red**, exit 1: 873 passed, nine failed, one skipped out of 883 JUnit records. Four failures are missing-Prettier tooling non-receipts; remaining assertions concern runtime boundaries, epoch status and metrics injection. Complete individual findings follow. The soak-smoke step is not run after this mandatory failure. |
| `docs-contract` | **Red**, exit 1 at check_docs_accuracy.py: links point to excluded/unpublished ADR, brand and reference pages. MkDocs is not run after this mandatory failure. |
| `mutation-subset` | **Red**, exit 2 before mutation: installed mutmut rejects --paths-to-mutate. No source mutations occurred. |
| `performance-smoke` | **Pass for its benchmark-only command**, exit 0 over the three explicit performance test files; JSON contains benchmark evidence. Non-benchmark tests are intentionally skipped by --benchmark-only. Concurrent local CPU load means these timings are not a CI latency budget receipt. |
| `scientist-phase0-gate` | **Pass**, test command exit 0, 161 passing cases out of 161 JUnit records, no skips/errors/failures. Subsequent --require-passing evidence gate exits 0 and emits passes_all=true with every required category true. |
| `scientist-phase1-gate` | **Red at the final evidence gate**, exit 1. Its targeted tests first pass (198 out of 198 JUnit records), and its benchmark command exits 0. The final report emits passes_all=false and no_live_model_copy_deep_true_hot_paths=false, identifying methods/doe/uncertainty.py:985. This is a real ratchet outcome after execution. |
| `long-soak` | **Pass**, exit 0. All five scenario reports say pass, each with its full default 192 iterations; JSON failures is empty. Independent enumeration of all five JSON reports agrees with all five stdout PASS receipts. |

The Phase 0/1 test counts come from both testsuite attributes and independent
enumeration of every testcase node and outcome. Full logs and machine outputs
remain in `_build/.tmp/ci-declared-targets/`, `_build/.tmp/test-reports/`, and
`_build/.tmp/reports/`. No assertion red above is called inherited. Proposed
follow-ups are recorded with provenance not_established rather than assigned away.

Closeout pattern pass reread findings P29/P35/P37/P38/P40/P41. Target existence,
version range and schema truth are recomputed; their artifact-set denominators are
independently_reconciled. Actual CI provisioning/execution is not_established and
therefore not promoted to a CI pass. Literal target parsing has a declared boundary;
coverage adequacy remains the content/history and runtime evidence, not existence.
The old ABI prefix/no-match proxy is demonstrated divergent by the real imported
model mutation and no longer decides whether the correctness check runs.

### Runtime-contract receipt and final handback

The exact targeted runtime-contract command completed with exit 1. Its JUnit
suite attributes and independently enumerated testcase outcomes agree on the
complete 883-record denominator: 873 passing outcomes, nine failures, one skip,
zero collection errors. XML-reported duration is 785.144 seconds. The complete
failure set is recorded here, not sampled. All test paths below are beneath
`policy-engine/tests/unit/runtime/http/`.

| Test file and test | Local finding | Proposed row / proposed owner |
| --- | --- | --- |
| `test_architecture_boundaries.py::test_runtime_never_imports_concrete_cas_write_implementation` | Runtime-quality code imports/constructs concrete CAS types where the check requires write protocols. Full finding list remains in JUnit/log. | `runtime-quality-concrete-cas-boundary` / `team-core-runtime` with runtime-quality owner |
| `test_architecture_boundaries.py::test_runtime_control_paths_do_not_resolve_registry_singletons_inline` | acquisition_executor.py resolves SourceProfileRegistry.get_instance inline. | `runtime-quality-inline-source-profile-singleton` / `team-core-runtime` |
| `test_runtime_api_contract_hardening.py::test_epoch_batch_success_example_is_owner_derived_and_strict` | Example target status is stale; assertion expects review_required. Adjudicate authority/status semantics rather than changing the expected string to green the test. | `runtime-epoch-batch-example-status-mismatch` / `team-core-runtime` with custody owner |
| `test_runtime_api_contract_hardening.py::test_generated_runtime_client_includes_capability_search_wrapper` | Node cannot import prettier; generated-client property was not tested. | `runtime-contract-job-client-toolchain-provisioning` / `team-devx` |
| `test_runtime_api_contract_hardening.py::test_committed_runtime_client_matches_package_generation_pipeline` | Same missing prettier tooling non-receipt. | Same proposed toolchain row / `team-devx` |
| `test_runtime_api_contract_hardening.py::test_client_package_entrypoints_generate_only_in_scratch` | Same missing prettier tooling non-receipt through corepack pnpm. | Same proposed toolchain row / `team-devx` |
| `test_runtime_api_contract_hardening.py::test_schema_and_clients_regenerate_byte_identically_twice` | Same missing prettier tooling non-receipt. | Same proposed toolchain row / `team-devx` |
| `test_api_maturity.py::test_runtime_container_accepts_typed_test_overrides` | _MetricsStub lacks artifact_operations_total when the artifact store consumes it. | `runtime-metrics-injection-contract-mismatch` / `team-core-runtime` |
| `test_api_maturity.py::test_runtime_security_middlewares_receive_injected_metrics_provider` | Same metrics-provider attribute mismatch. | Same proposed metrics row / `team-core-runtime` |

The skip is the already proposed moved SLO fixture-root defect. This run did not
provision workspace node_modules with `corepack pnpm install --frozen-lockfile`;
therefore the four client-generation failures are **tooling non-receipts**, not
product drift findings. Their properties are not_established. The workflow's
runtime-contract job also warrants a separate toolchain-provisioning audit before
those properties can receive CI evidence. This lane stops at the Pillow dependency
decision rather than starting an additional client-toolchain repair. No TypeScript
scanner's missing-dependency output is promoted to a product finding.

Late diagnostic-only finding (recorded after source freeze, no mechanism edit):
`abi-direct-path-summary-workflow-escape`, proposed owner `team-devx`. The retained
informational regex over-escapes the workflow self-path; running its actual
shell-decoded pattern against `.github/workflows/abi.yml` yields no match (exit 1).
It cannot skip the now-unconditional checks. Correcting that summary is outside the
closed guard property, so it is recorded as a bounded diagnostic residual rather
than restarting repairs. No inherited label is asserted for it.

Implementation commit: `b34fc2ea2cffdce30957c0d342dbf1589c5892db`.
It follows merge `c32d1e2d6ce389793b8341c3e906934344f993ca`, preserving intake commit
`4926ce1c4` and merging the requested local main. Branch attachment was verified
before committing; every delivered file was then read from
`codex/ci-declared-targets` and compared byte-for-byte with the verified worktree.
The complete changed-path set relative to `d2f2dffe4` is within `.github/**`, the
generated-artifact manifest, and this explicitly mandated journal. No forbidden
source/test/tool/baseline/register/ledger path is delivered. Commit hooks reported
no local Lefthook config; the explicit standalone checks above are the receipts,
not an implied hook verification.

Final stop: all eight owned rows are dispositioned in the current table, and Pillow
requires the architect/dependency boundary. This final receipt is a new journal-only
commit, preserving append-only history. All started verification processes have
finished. **No push was performed; no CI run is available.** Handback ends at the
push boundary with local execution limits and proposed owners explicitly recorded.
