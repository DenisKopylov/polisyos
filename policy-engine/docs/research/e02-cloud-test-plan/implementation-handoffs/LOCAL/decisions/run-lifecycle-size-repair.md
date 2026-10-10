# Control job lifecycle split receipt

## Outcome

The control-job worker remains a `ControlPlaneService` owned by
`control/run_lifecycle.py`; its canonical class and `_process_control_job` /
`_process_control_job_admitted` method identities are preserved. The worker's
workflow, admission, diagnostics, attempt-publication, and natural-language
admission/execution/publication mechanics now live in seven adjacent internal
facets plus one typed natural-language context carrier. The extraction keeps
scope admission before reads, evaluation-safety admission before protected
execution, and attempt finalization after execution failures.

While finishing the split, I corrected the live extraction defects: the
budget producer binding import now comes from its owning Scientist budget
ledger module; the evaluation-safety intake block is back in the admission
method (and the intent resolver is pure and returns its selected mode); and the
scope facet imports the cast and execution-context key it uses. The in-scope
intent tests now pass exact artifact kinds through their `_load_payload_ref`
wrappers and direct reads. The reported `_NL_REQUEST_SNAPSHOT_SCHEMA`
`NameError` did not reproduce on this tree; the extracted publication helper
contains and uses that module constant.

## Mechanism and companions

The mechanism consists of the preserved service module and seven helpers:

- `src/polisyos/runtime/http/services/control/run_lifecycle.py`
- `src/polisyos/runtime/http/services/control/job_attempt_publication.py`
- `src/polisyos/runtime/http/services/control/job_diagnostics.py`
- `src/polisyos/runtime/http/services/control/job_scope_admission.py`
- `src/polisyos/runtime/http/services/control/job_nl_admission.py`
- `src/polisyos/runtime/http/services/control/job_nl_execution.py`
- `src/polisyos/runtime/http/services/control/job_nl_publication.py`
- `src/polisyos/runtime/http/services/control/job_nl_context.py`

The mandatory characterization/test companions and nearest package README are
outside that mechanism count, consistent with P39:

- `tests/unit/runtime/http/test_control_job_execution_split.py`
- `tests/unit/runtime/http/test_control_job_execution_intent.py`
- `src/polisyos/runtime/http/services/README.md`

No release fragment was needed because this is an internal module split with no
route, DTO, or documented service API change. Existing intermediate `.raw`
helper files were preserved and are not part of the source manifest.

## Size and complexity

The repository's module-size counter counts nonblank, noncomment lines in
`tools/quality/validation/package_import_size_ratchet.py:35`. Current counts:

| Module | Logical lines |
| --- | ---: |
| `run_lifecycle.py` | 3,869 / 4,430 ratchet |
| `job_attempt_publication.py` | 954 / 1,000 facet limit |
| `job_diagnostics.py` | 680 / 1,000 facet limit |
| `job_scope_admission.py` | 900 / 1,000 facet limit |
| `job_nl_admission.py` | 479 / 1,000 facet limit |
| `job_nl_execution.py` | 789 / 1,000 facet limit |
| `job_nl_publication.py` | 137 / 1,000 facet limit |
| `job_nl_context.py` | 58 / 1,000 facet limit |

C901 with maximum complexity 12 passes over all seven helper modules. The
same check over the retained `run_lifecycle.py` still reports six methods above
12: `reconcile_null_ref_reservation` (19), its nested `_restore` (18),
`ControlPlaneService.__init__` (21), `record_production_approval_packet` (15),
`launch_nl_run` (14), and `run_data_ingestion` (17). These methods are outside
the extraction facets and were left untouched. This receipt does not claim an
independent P41 base replay for those findings.

## Verification

The final selected run collected 21 cases across four test files (3 split
characterizations, 14 intent cases including parameterized tamper/refusal
cases, 3 POST controls, and 1 fresh GET). It passed. The controls include the
unknown-scope identity/owner checks, all seven protected-intent tamper cases,
valid candidate and DataTrust worker paths, the three ordinary POST positive /
negative cases, and a fresh authorized GET resolving the persisted candidate
simulation. Full output:

`LOCAL/cas-contracts/raw/run-lifecycle-final-pytest.log`

The exact collected denominator is retained at
`LOCAL/cas-contracts/raw/run-lifecycle-final-collect.log`.

Also passed:

- `PYTHONPATH=src .venv/bin/python -m py_compile` over all eight mechanism modules.
- `ruff check` over all eight modules and both test companions.
- `ruff format --check` over the same ten files.
- `ruff check --select C901 --config lint.mccabe.max-complexity=12` over the seven helper modules.

Complete outputs are in `LOCAL/cas-contracts/raw/run-lifecycle-{ruff-final,format-final,c901-final}.log`; the main-module C901 output, including its nonzero status and six named findings, is in `LOCAL/cas-contracts/raw/run-lifecycle-main-c901.log`.

## Changed-file hashes

SHA-256 values identify the final bytes verified above:

| Path | SHA-256 |
| --- | --- |
| `src/polisyos/runtime/http/services/control/run_lifecycle.py` | `3490e49a0a357edca9fb602632e488a1ef2f4b23fbb639061e537639b070b29a` |
| `src/polisyos/runtime/http/services/control/job_attempt_publication.py` | `1df93d2c7781c74b977be58d2a1f7fef3ea450890762f1483652ba1b3be4fa01` |
| `src/polisyos/runtime/http/services/control/job_diagnostics.py` | `de76808d762989917178213a083f987d6a21bdf018ceec33e34fb91517aa10d5` |
| `src/polisyos/runtime/http/services/control/job_scope_admission.py` | `b0acde9f4a8f6cefabdd1edbdb0cd67f8d2e3272d33e7f5a1316d953bd8a8a97` |
| `src/polisyos/runtime/http/services/control/job_nl_admission.py` | `a082ef37534479d27fb762c2b481926d2cf48ec3a3c959e9051d86fcd799e637` |
| `src/polisyos/runtime/http/services/control/job_nl_execution.py` | `80e0727157df0becf885e57370a893c3011ea5216632170c6c05218b226419c8` |
| `src/polisyos/runtime/http/services/control/job_nl_publication.py` | `ed952750bea47958f5a0ceebc16ba45a2d4bcf030e108e97d5c038ad7be2a574` |
| `src/polisyos/runtime/http/services/control/job_nl_context.py` | `e5f3376f802693fe2cd0bdcf6fc7b917129618ff11f8a726fbb05a48dda22e19` |
| `tests/unit/runtime/http/test_control_job_execution_split.py` | `99a2e068cf67f9cf95a165ad3698f52afeec377f965ad1893c389541fa169456` |
| `tests/unit/runtime/http/test_control_job_execution_intent.py` | `3a590a141170db89343a53672fe56aa6a486f1ab2e9f235b5994353cf11d8c00` |
| `src/polisyos/runtime/http/services/README.md` | `a14d8ee4f078b00dee769600e25bf667f8c160d3360e2cc6bf9ca1df5b002fc3` |
