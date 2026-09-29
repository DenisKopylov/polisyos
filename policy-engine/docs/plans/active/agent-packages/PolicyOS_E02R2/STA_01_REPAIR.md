# STA-01 — workflow report timeout admission

## Bounded property

The synchronous and asynchronous workflow executors now encode the actual timeout threshold as a binary64 hexadecimal string. Both current `scientist.workflow_report` CAS writers admit only producer statuses `ok` and `fail` and validate every error-details payload against the strict canonical profile before writing. `WorkflowReport` and `NodeError` remain permissive when reading historical payloads; no persisted historical bytes were rewritten.

The production `LocalWorkflowRunner` delegates to the asynchronous executor without passing its optional semaphore or workflow timeout settings. A direct caller can still set `semaphore_timeout_s=-1.0`; that invalid threshold becomes the valid JSON string `-0x1.0000000000000p+0` in a persisted report. The direct-config falsifier and valid control are recorded in `/Users/deniskopylov/.codex/scratch/e02-sta-report-timeout-candidate/direct-config-falsifier.log@sha256:29b0252e5757d1becad041460d3e0c5f5e435eacbb8e3fc69f50ac164addfb01` (script `@sha256:d68e3728f45b4f1c8b0d50e1182787d5254d640878f6e05bec62cefabd47bef1`). This is a bounded residual owned by the `AsyncWorkflowExecutor` configuration boundary and `NodeError.for_timeout`; the next step is finite, nonnegative input validation with an explicit decision about zero as immediate timeout. Do not treat this slice as full STA-01 closure.

## Evidence and limits

The independent review gave **GO only for this bounded served-path repair**: `/Users/deniskopylov/.codex/scratch/e02-sta-report-timeout-candidate/independent-review-V2-bac6996.md@sha256:cb5aca5f7b573c7f3d97dabf7d13a8f9370bb0b99f236f719910c89a4a433a31`. The frozen implementation patch is `/Users/deniskopylov/.codex/scratch/e02-sta-report-timeout-candidate/frozen-v2-combined.patch@sha256:d13621ffd84976cf4a98c35e78b31e7f7ae9bd276d5e848e4864de2dade4d91f`; only two formatting lines in its new test file changed after application. The writer's marker-retaining status-removal probe has two expected failures (`status-red.junit.xml@sha256:e8bf9b662c2c10d109fc47eedfcc50e4506dd4edadfabd768c22060db5fb1ca4`). The earlier float-details removal witness is `red.junit.xml@sha256:e0155a358129e8e4a40b34ed9570e0ab7030eb2ec3c42b15ff1ac2fcce429c2c`.

At the integrated head, complete test files ran with the existing `.venv`, Git, the read-only `production_data` symlink, `JAX_PLATFORMS=cpu`, per-job scratch, and explicit alarms. No tree edit overlapped a run:

| Scope | JUnit result | Receipt |
|---|---:|---|
| New report-custody file | 14/14 pass, exit 0 | `/Users/deniskopylov/.codex/scratch/e02-sta-integrated-bac6996-20260928/focused/test.junit.xml@sha256:953e070eb20573a1d7e395cc450c25fb515adff1fc54fea7a4dec3b312f4ed46` |
| B73 whole-file controls (`test_res_02.py`, `test_checkpoint_resume.py`) | 17/17 pass, exit 0 | `/Users/deniskopylov/.codex/scratch/e02-sta-integrated-bac6996-20260928/b73-control/test.junit.xml@sha256:e30cd84d005aeab426417f82dbbfa114830e96443c768d8382a87d2a9b521d61` |
| Five executor/checkpoint/distributed importer files | 72/72 pass, exit 0 | `/Users/deniskopylov/.codex/scratch/e02-sta-integrated-bac6996-20260928/importers/test.junit.xml@sha256:c418604ab5bbb888920e03b64684b20d469730c5b70104c2a6625819b2a00e2c` |

Targeted `ruff check` and `git diff --check` passed. The new test file passes `ruff format --check`; the formatter also requests broad changes to four existing source files at the unmodified parent `bac6996`, so they were not reformatted for this repair. A byte-exact census of all previously persisted `WorkflowReport` fixtures and the complete four-base replay are **UNRUN**. Current tests establish replay of a historical float-bearing `NodeOutcome` and permissive parsing of a historical `not_established` report, not byte-exact replay of every historical report.

P37: current result status is derived from failed-node evidence, and newly written error details are validated at the common CAS write boundary. P38: canonical serialization alone does not prove a timeout threshold was valid; the negative direct-config example above is the divergence. This is the same STA report-admission class, not a fresh round of per-call-site patches.
