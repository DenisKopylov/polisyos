# Independent HTTP terminal-proof review

## Decision

The terminal admission mechanism correctly verifies the active handler’s job, worker, attempt, cleared lease, and latest matching `job_completed` / `job_failed` event before appending the diagnostic. The real guarded Lex completion path also passes and preserves the creation-time tenant/cell scope.

The broader property “the persisted diagnostic content itself names the proven control-job attempt” is **not established**. A test-only fresh SQLite control-store falsifier completed attempt 1, supplied `event_payload={"attempt": 100}`, and received `status="persisted"`; fresh readback retained `payload_inline.attempt == 100`. The proof gates the append, but it does not bind that optional payload field to the proof. The review is therefore not a closure claim for exact diagnostic-content attribution. Root has been informed and owns the next source delta; this reviewer made no product edits.

## Current source and test snapshot

Product root: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`.

| Path | SHA-256 |
| --- | --- |
| `src/polisyos/runtime/http/services/control_plane_store.py` | `9220fdb97006813f692f56e59ccf4ff0675253e30c44eb80f2f465b928eca033` |
| `src/polisyos/runtime/http/services/control/job_diagnostics.py` | `deee0a2103f7f16745bc3028842d4666e21337aacb81ec79b05edf5cb5234a15` |
| `src/polisyos/runtime/http/resilience.py` | `aa060253ec9474db1446b7b048730be2284300a1378b87d9cd3dc9969d3b34a0` |
| `src/polisyos/runtime/quality/event_log.py` | `dd477cbcc88ab5a464976285d72736c82a5ff9180681a44827f01b76fead3b28` |
| `src/polisyos/runtime/http/services/control/run_lifecycle.py` | `4f941cd8b069020cc3d70bd4ac61f129d881c68d77e673278cea7d00265b5fd3` |
| `tests/unit/runtime/http/test_control_job_execution_intent.py` | `91c12576ad94b04f3c5cfce6d5fdc52ba89c6458ff85504b49c8758a5fcd27b3` |
| `tests/unit/runtime/http/test_control_plane_store.py` | `3c50de6b9efa3a0b75b2dc7ee9eb6d7bf06456bc2eaf46019897a6d68879cf30` |
| `tests/unit/runtime/http/test_control_service_di.py` | `a350618bae4942c3e2184ad6b801b0180f7ac05a84495072649dbc2c3b90faed` |
| `tests/unit/runtime/http/test_served_unknown_target_scope.py` | `a7a295e4448c975f1c25818e19c4f54a105c32bd02d67cd7eb1322263e51f7ff` |

## Source trace

- `ControlPlaneStore.create_job` writes a `job_created` event and `control.job.created` outbox record in its store transaction (`control_plane_store.py:2703–2774`). A real worker resolves its `ControlJobExecutionAdmission` from the active execution fence and these records (`:1538–1640`): it reconciles event/outbox content, binds stable creation fields to the current row, checks actor subject against `submitted_by`, and returns the typed creation scope. A typed scope is not reconstructed from mutable progress or ambient request state.
- `ControlJobDiagnosticsMixin._emit_runtime_diagnostic_event` classifies the supplied typed scope and withholds authority-bearing payload/refs if scope is unestablished (`job_diagnostics.py:86–166`). The admission phase checks the durable creation event and outbox inside `run_guarded_dependency_operation` (`:219–270`). The running path resolves the current fenced job and requires `state == "running"` (`:327–339`).
- For terminal jobs, the method enters `append_terminal_event` on the control-store guarded worker and opens one `_job_transaction` with the appropriate terminal proof purpose. Inside that transaction it checks the created-event/outbox scope against the handler scope, obtains the exact current completed/failed record, and checks job ID and attempt before appending (`job_diagnostics.py:271–325`).
- `current_execution_completed_job_record` and `current_execution_failed_job_record` require the bound execution fence, inspect the persisted terminal row, reject any remaining lease owner/expiry or attempt mismatch, and read the latest matching event type by descending event ID. The event must carry the exact state, worker, and strict integer attempt (`control_plane_store.py:3373–3445`). `complete_job` / `fail_job` clear the lease and write the terminal event/outbox from the active fence inside the job transaction (`:3640–3810`).
- The event log is constructed over the same guarded control-store object (`run_lifecycle.py:1504–1520`). Its diagnostic append uses nested store operations, which run inline on the already active guard worker; `_job_transaction` reuses the worker’s thread-local SQL resource (`control_plane_store.py:5153–5190`; `resilience.py:261–345`). The service-level completion test demonstrates this path completes without a nested control-store deadlock.

## Independent controls

All runs used the candidate `.venv` Python 3.14 interpreter, `PYTHONPATH=src:.`, and numerical thread counts set to one.

1. Full current callback-domain replay:

   ```text
   OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python -m pytest -q --tb=short tests/unit/runtime/http/test_control_job_execution_intent.py tests/unit/runtime/http/test_served_unknown_target_scope.py
   ```

   Result: exit 0, 39 parametrized cases passed. The real `test_lex_worker_keeps_completion_diagnostic_under_admitted_scope` dispatches a job through the service, reads back the completed event, and checks tenant, cell, established status, and `source=job_admission`; the completed/failed terminal handler test rejects a foreign scope, foreign job ID, and replaced attempt. The complete output is `LOCAL/reviews/raw/http-terminal-callback-domain-replay.log`, SHA-256 `e9df60e18e1e617a79394ebc6a4e90048877377ea9c1a115d764dc804b9a698a`.

2. Store proof and corruption controls, plus the diagnostic request-scope callback:

   ```text
   OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python -m pytest -q --tb=short \
     tests/unit/runtime/http/test_control_plane_store.py::test_failed_terminal_record_resolves_exact_worker_attempt \
     tests/unit/runtime/http/test_control_plane_store.py::test_failed_terminal_record_refuses_foreign_or_replaced_attempt \
     tests/unit/runtime/http/test_control_plane_store.py::test_completed_proof_publication_preserves_progress_and_journals_exact_attempt \
     tests/unit/runtime/http/test_control_plane_store.py::test_completed_proof_publication_refuses_foreign_or_replaced_attempt \
     tests/unit/runtime/http/test_control_plane_store.py::test_control_job_execution_admission_rejects_malformed_scope_and_row_mismatch \
     tests/unit/runtime/http/test_control_plane_store.py::test_control_job_execution_admission_requires_exactly_one_creation_event \
     tests/unit/runtime/http/test_control_service_di.py::test_diagnostic_events_bind_authenticated_scope_and_declare_unknown_attribution
   ```

   Result: exit 0, 35 parametrized cases passed. This includes guarded and unguarded terminal record positives; foreign owner, wrong event attempt, row attempt mutation, replaced worker, and missing event refusals; completed-proof progress and publication checks; malformed creation-scope/row mismatch; and missing/duplicate creation-event controls. Complete output is `LOCAL/reviews/raw/http-terminal-store-controls.log`, SHA-256 `17a21aa500a96381e0301489b366678c1d305590a89297e257fbb553baab7069`.

3. The author’s retained `failed-terminal-proof-final.log` has SHA-256 `845e3a7994d028060bd1a5a759b52e85b43423530a5a204d926f2fdd4c1d1ba2` and contains 71 dots at 100% plus two Python 3.14 `torch.jit.script` deprecation warnings. It has no pytest command or explicit count summary, so it is supporting author output only; the independent commands above state their selectors and counts.

4. A fresh terminal-emitter malformed-source control changed the durable `job_created` scope envelope to `actor_authenticated=false` after the handler admitted the original source, then completed the row and invoked the terminal diagnostic. Readback: `emission_status=not_persisted`, `persisted_events=0`, exit 0. This confirms the terminal path reparses and rejects a malformed creation source rather than relying only on the earlier admission result. Complete output is `LOCAL/reviews/raw/http-terminal-malformed-created-event-control.log`, SHA-256 `f534f56cb38030d2c4670f374f8007048a503ffdf1e182f62d970063715f585c`.

## Content-attribution falsifier (P38)

A test-only script built a fresh service in `TemporaryDirectory`, created a typed scoped job, leased it to `proof-worker`, obtained admission from the durable creation event/outbox, completed it under `job_execution_fence`, then invoked `_emit_runtime_diagnostic_event` with a mismatched caller payload attempt. No product source or test was modified. Output: `active_attempt=1`, `emission_status=persisted`, `persisted_attempt=100`, `probe_exit=0`; complete output is `LOCAL/reviews/raw/http-terminal-payload-attempt-falsifier-replay.log`, SHA-256 `4c274684df8a8b2db19e436cd56e2d0e4544686c27fac3640d8eddb33f7b1a11`.

Property: a persisted diagnostic that declares a control-job attempt names the attempt proven by the terminal transaction. Current code checks the row and latest terminal event against the active fence, but copies `event_payload` through unchanged. The divergent case is a valid attempt-1 terminal transition carrying caller `attempt=100`; it remains persisted. The optional payload key is not a typed control-store proof field, and real producers may use a domain-specific `attempt` value. Any source delta should inspect every caller and add a canonical, separate source-control attempt identity rather than overwrite domain payload semantics. This review does not make that edit.

## P37 / P40 disposition

P40 classification: **SAME_CLASS_DEEPER**. Generalizing the proof from completed-only to the completed/failed terminal union is the correct class-level mechanism. The additional escape is one level deeper in proof-to-emission attribution: verified current attempt gates the append, but the emitted content does not identify that verified attempt separately from arbitrary caller payload. Since this is the second same-class finding, stop the local repair ladder and use the class-level canonical control-job attempt in emitted content; inspect all actual payload callers before choosing the separate field. No external protected fact was established by these SQLite fixtures or this review.

For P37, the status/attempt/lease/event comparisons are **recomputed** from the active fence and current durable rows. Scope equality across the creation event, outbox, and handler scope is also **recomputed**; both persisted records share one store producer, so their match is not independent institutional attestation. The optional `event_payload.attempt` is **not_established** as the control-job attempt because the terminal proof never compares it with the fence.

Scope limits: independent tests exercised the SQLite guarded-store path, not a live production store or PostgreSQL deployment. No production currentness, external identity-provider attestation, or production database state is inferred from these results.

## Final execution-binding delta review

The final delta closes the earlier proof-to-emission attempt-attribution escape on the reviewed SQLite path. The prior `attempt=100` result remains a valid historical falsifier against the earlier source snapshot above; the same divergent input is now refused by the updated implementation, and the accepted positive cases carry a separately named `control_job_execution_binding` derived from the durable source event.

### Reviewed snapshot

| Path | SHA-256 |
| --- | --- |
| `src/polisyos/runtime/http/services/control/job_diagnostics.py` | `3405e7e722e3958d8bd625e9103e82649202f25a2e6a18e7ef14705438ad5cc9` |
| `src/polisyos/runtime/http/services/control_plane_store.py` | `b703f021ca4d87aa7b643eba1f02b37257d258a579e1313db0d9b3962c427f58` |
| `tests/unit/runtime/http/test_control_job_execution_intent.py` | `5ce8748748e562a64de9064844737002802cb40268dbb32344a025280de6a8be` |
| `tests/unit/runtime/http/test_control_plane_store.py` | `73859ef94fe4dd31782f70e7a9cf09b0949d9c59008c2df63a5b5a6ac8f89a8a` |
| `src/polisyos/runtime/http/services/README.md` | `54f87df014e7390b2b5c9556e1638384a0e132367561519462e7915207eb7f9c` |
| Author focused receipt `LOCAL/raw/v4-v7-current-boundary/execution-binding-final-focus.log` | `418c39209515492102d9c114885beccee24cc7ee1637e88357170ba07b4d0cbc` |

The README describes the binding as an internal service contract: admission uses the persisted `job_created` record and no worker attempt; running and terminal diagnostics bind the persisted lifecycle source, its row time and raw-payload digest, and stored artifact references. It also keeps evaluation-step attempts nested. The independent review did not rely on the author’s test receipt for its verdict.

### Implementation and caller trace

`_ControlJobExecutionBinding` is a strict, frozen, extra-forbid internal model. It carries the proof phase, control job/run, source event state and identity, source-row timestamp, SHA-256 of the exact stored JSON text, worker/attempt when one exists, and job-record artifact refs. `_control_job_bound_diagnostic_payload` builds this object from the store’s lifecycle proof; callers cannot supply the reserved binding key. A supplied top-level `attempt` is accepted only as a strict integer equal to the proof attempt. Admission has no worker attempt, so an `attempt` there is refused. If omitted, the canonical attempt remains in `control_worker_attempt` in the binding. Nested domain/evaluation attempts are not interpreted by this check.

The store parses lifecycle event rows while preserving the raw payload string for hashing, requires a positive exact event ID and the expected job/event type, parses a timezone-aware row timestamp, and returns the parsed payload with that identity. Running proof checks the current execution fence against the job row and newest `job_running` source. Completed/failed proof checks the fenced attempt, cleared lease, current terminal row, and newest matching terminal event. The diagnostic producer obtains the proof and appends within the corresponding guarded job transaction. The admission path also checks the unique creation source and matching outbox in its guarded transaction. The route-level Lex test confirms these paths through real service dispatch and fresh diagnostic-store readback.

An AST census of `src/polisyos/**/*.py` (2,748 Python source files) found 18 diagnostic emitter call sites and exactly one statically supplied top-level `event_payload.attempt`: `job_diagnostics.py:929`, the running producer’s current `job.attempt`. The natural-language evaluation step attempts are nested domain rows, not top-level diagnostic event payloads. The generic `AccessScope` path refuses a top-level attempt without a control-job proof. This supports keeping the existing field semantics while adding the canonical binding.

### Independent delta controls

Command, from the candidate `policy-engine/` root:

```text
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python -m pytest -q --tb=short \
  tests/unit/runtime/http/test_control_job_execution_intent.py::test_lex_worker_keeps_completion_diagnostic_under_admitted_scope \
  tests/unit/runtime/http/test_control_job_execution_intent.py::test_terminal_handler_diagnostic_rejects_foreign_and_replaced_attempt \
  tests/unit/runtime/http/test_control_plane_store.py::test_failed_terminal_record_resolves_exact_worker_attempt \
  tests/unit/runtime/http/test_control_plane_store.py::test_running_lifecycle_proof_resolves_exact_source_event \
  tests/unit/runtime/http/test_control_plane_store.py::test_running_lifecycle_proof_refuses_missing_or_foreign_source_event \
  tests/unit/runtime/http/test_control_plane_store.py::test_failed_terminal_record_refuses_foreign_or_replaced_attempt
```

Result: exit 0, 22 selected cases passed. Complete independent output: `LOCAL/reviews/raw/http-terminal-binding-delta-controls.log`, SHA-256 `f64fc772726632a59257fb02063d18ca02e8e34f10ff43ac2b6aa19546aa5a62`.

The Lex service-path test verifies admission’s exact creation-event ID/time/raw-payload digest and stored refs, then reads back running and completed diagnostics with the matching worker attempt and lifecycle phase. The completed/failed emitter test repeats the old mismatch (`attempt=100`) and also rejects bool/string/`None`, a caller-forged binding, foreign scope/job, malformed terminal source, and a replaced attempt. It accepts both an omitted attempt and the matching attempt, then confirms exactly those two records are present and both carry the canonical binding. The store tests verify exact source-row ID/time/payload digest for running proofs and reject missing/wrong attempt, foreign worker, malformed payload, and missing running event; guarded and unguarded failed-terminal record selection and foreign/replaced-source cases also pass.

An additional isolated service-path probe emitted both completed and failed diagnostics, then selected the raw terminal event row directly from SQLite and independently computed SHA-256 over its stored `payload_json` bytes. For both terminal states, the emitted binding exactly matched the raw row’s event ID, normalized `created_at`, and independently computed digest, as well as the active worker and attempt. Output: `LOCAL/reviews/raw/http-terminal-binding-terminal-digest-probe.log`, SHA-256 `fc05bcfd49758edc0d280ac068757406e979a0a7236093daeacaffad017182f5`.

The first invocation of that auxiliary probe used `PYTHONPATH=src:.` and exited 1 before product execution because the helper imports `_helpers` as a top-level module. This was a tooling nonreceipt, not a product failure; rerunning the same probe with `PYTHONPATH=src:.:tests` passed and produced the receipt above.

### Updated finding and scope

P40 remains **SAME_CLASS_DEEPER**. The second-level proof-to-emission attribution defect is now closed by one shared producer rule: each job-scoped diagnostic contains a strict canonical binding derived from its lifecycle source, and any caller-supplied top-level attempt must agree. The former `attempt=100` counterexample is explicitly negative in the final terminal test, while omission and a matching attempt are positive controls. No new escape in this class was observed in the bounded replay.

For P37, the control-worker attempt is recomputed from the active fence and reconciled job/source rows; source event ID, row time, and raw-payload digest are recomputed from the persisted row; artifact refs come from the transaction’s job record. These are facts reconciled within the same SQLite store, not independent institutional attestations. The source event’s `created_at` identifies its stored row time; the diagnostic event’s `event_time` remains the emission time. This does not establish freshness of the referenced artifacts or a live production-store/currentness claim. Verification remains scoped to the selected SQLite guarded-store/service tests; PostgreSQL and production deployments were not exercised in this delta review.
