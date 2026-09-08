# PA1-D3f — emitted OpenAPI transport example

The normative-evidence POST now has a lazily supplied, strict DTO-validated
`positive_fixture_only_transport` example through the existing OpenAPI example-set
owner. Its entire response value is copied from the actual default worker → later
fixture-signature → owned HTTP intake positive. Every captured ref, time, status,
null, collection, limitation and nested value remains unchanged. The example's
description explicitly disclaims production authority and a canonical denominator;
the response body has no invented qualification field and no fabricated receipt.

The changed production owner is
`src/polisyos/runtime/http/openapi_contract.py`: one captured literal, a lazy helper,
one operation registration, and the existing example-set augmentation accepting a
callable just as the singleton example map already does. The helper validates
`NormativeEvidenceSubmissionResponse` with `model_validate_json(..., strict=True)`
and returns the original capture values rather than a normalized model dump. No
runtime evidence admission reads the documentation sample. No schema epoch changed.

The mandatory mirrored companion is
`tests/unit/runtime/http/test_runtime_api_contract_hardening.py`. Its focused tests
load the complete tracked `schemas/runtime_api_v1.openapi.json`, remove only this
operation's preexisting transport examples, and run the real augmentation plus the
whole contract validator. The complete owner-derived get/post identity set is
independently reconciled against a separate JSON traversal in the probe output.
The happy path then compares the complete emitted value against the preserved
capture and strictly validates it as the actual response DTO.

## Evidence that decides this delta

All command records below retain exact argv, cwd, PATH, PYTHONPATH, actual return
code, wall time, complete stdout and complete stderr. Their cwd is the lane's
`policy-engine`; venv PATH is first. Python package entrypoints run with `-m`.

| Record | RC | Wall seconds | Deciding observation |
| --- | ---: | ---: | --- |
| [Actual HTTP capture](openapi-response-capture-command.json) | 0 | 99.909 | Existing worker → later-signed HTTP positive passes; process-local observer returns the unchanged response. |
| [Red before repair](openapi-example-red.json) | 1 | 60.727 | Full validator returns exactly `POST /api/v1/control/runs/{run_id}/normative-evidence: missing 2xx success response example`, before transport marker assertions. |
| [First focused green](openapi-example-green.json) | 0 | 41.703 | Actual augmentation, full contract validation, complete capture equality, strict DTO validation and removal companion pass. |
| [Registration removal](openapi-registration-removal.json) | 1 | 77.001 | Process-local removal of only the operation registration makes the same positive fail at the exact missing-success-example assertion. Payload, helper, documentation markers and disk source remain. |
| [Final focused green](openapi-example-final-green.json) | 0 | 65.208 | Fresh process on the final formatted source validates the captured response and both focused tests; complete operation identity sets agree. |
| [Final full scoped Ruff](openapi-example-ruff-final-v2.json) | 1 | 0.122 | Only F601 for the unchanged, unrelated epoch-validity duplicate remains. It is neither ignored nor removed from this gate. |

The exact wire bytes are retained in
[openapi-response-capture.json](openapi-response-capture.json), with observer
provenance in [openapi-response-capture-metadata.json](openapi-response-capture-metadata.json).
Their SHA-256 is
`becbcde583102a388069266d50e0dbee946b7c642223a958f8234652b8e4ed65`.
The complete capture is fixture transport evidence only. Its referenced source,
signers, deployment trust and candidate are not a production authority allocation,
institutional act or canonical policy denominator.

## Preserved incidental finding, outside PA1

`F601 / overwritten epoch-validity example` belongs to **DS18 C03 and DS15 C03**.
The [read-only audit](openapi-epoch-duplicate-audit.json) retains both complete
defining expressions, the entire earlier helper, every direct helper call, and
the exact Git history commands and outputs.

- Commit `716078d53026a33acea14b8100ff03311ad7a1c9`
  (`feat(ds18): generate executable epoch clients`) introduced the earlier
  `"admit_epoch_validity_batch": _epoch_validity_batch_example()` entry. The helper
  eagerly constructs ArtifactRef and typed epoch DTO objects and dumps them to
  JSON during module initialization. Its direct call set contains those
  constructors, `str`, and `model_dump`; it is not an evidence persistence path.
- Commit `4d02940e5bf7c8d3fa59d27676729e5a6b062156`
  (`feat(api): publish acquisition route ABI`) introduced the later literal for
  that same key. Python evaluates the earlier helper, then the later literal
  becomes the effective map value. The later example has batch ID
  `epoch-validity-batch-001`; the earlier helper emits `epoch-batch-openapi-sample`.
  These are different example values, not redundant text copies.
- DS18's execution journal C03, beginning at
  `docs/superpowers/journals/2026-08-27-ds18-epoch-staleness-chrome.md:392`, owns the
  strict owner-derived epoch example; DS15's active slice C03 owns the generated
  ABI transaction. The source remains untouched under the user's prohibition
  against repairs to executed tasks, as directed by the root coordinator.

Ruff therefore remains **RC1**. This report makes no inherited/disjoint P41 claim:
the gate includes the OpenAPI owner changed by PA1. The finding does not establish
a gap in PA1's refusal or evidence-intake mechanism. The responsible owners must
decide how to reconcile their competing example definitions; this lane has not
silently selected one or changed the epoch API example.

## Nonreceipts and retained intermediate records

The earlier [mixed-source import attempt](openapi-mixed-source-import-nonreceipt.json)
returned RC1 before validation: the long-lived process had loaded the old core
facade and then encountered the new consumer import while another authorized
writer was adding the facade export. The coordinator subsequently supplied the
fresh-process green facade evidence. Final D3f parsing now succeeds in the fresh
green above. The failed record remains; it is not a current product finding.

The inline-installation and formatting records preserve the value conversion:
[initial installation](openapi-example-owner-write.json),
[Python literal rendering](openapi-example-literal-format.json),
[first wrap attempt](openapi-example-literal-wrap.json), and
[successful bounded wrap](openapi-example-literal-wrap-v2.json). The first wrap
attempt failed in the formatting harness before writing source; the corrected
formatter started from a single literal representation and proved complete
decoded equality before replacing only the added literal span. The first attempted
Ruff-v2 invocation used an invalid cwd and did not start a process; its corrected
invocation has the real record. Earlier Ruff results are retained as
`openapi-example-ruff.json`, `openapi-example-ruff-v2.json`,
`openapi-example-ruff-v3.json`, `openapi-example-ruff-v4.json`, and
`openapi-example-ruff-final.json`; no failure record was overwritten.

The historical capture observer, value-install/render/wrap witnesses, semantic
probe, and duplicate audit are retained under `pa1/openapi*.py`. Their local
research-only Ruff annotations cover deliberate assertions/output/observation and
fixed subprocess orchestration; no project Ruff policy or production exemption
was added.

Production and test files are frozen after final readback. The coordinator owns
canonical OpenAPI/client/dashboard generation, final common verification, commits
and the lane's terminal status. This delta ran no canonical generator, broad
suite, composed WMR builder, debt/ledger tool, or Git mutation.
