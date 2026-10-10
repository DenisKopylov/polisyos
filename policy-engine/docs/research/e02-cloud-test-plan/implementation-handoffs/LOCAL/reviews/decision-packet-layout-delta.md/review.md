# Decision-packet layout delta review

## Finding

The decision-packet extraction is review-ready within this component scope. I found no semantic blocker in the reviewed refactor: public names and canonical identities are preserved, and packet validation, publication gates, persistence order, and epoch issuance still compose through the production node. This is a component review, not final freeze or G acceptance.

Review base was `68b8ac5c32e03309ad888cb3799ad1c574fbdca7` (tree `7966c18c0557e8f43fd09e03f3c4eda9f987e458`). The checkout is shared and has unrelated WIP. The reviewed decision-packet source, tests, complexity row, and node README match the hashes recorded in [`raw/review-fingerprints.sha256`](raw/review-fingerprints.sha256); the later formatter pass did not alter their AST or bytes. I made no source or test edits.

## Scope and behavior

The change extracts decision-packet sections and orchestration helpers into five section owners plus `decision_packet_support.py`. The AST census found 74 prior definitions and 96 current definitions, no missing prior definitions, and 22 extracted helpers. The seven changed definitions are the node, `execute`, and orchestration/section helpers whose bodies now delegate to the extracted owners. The detailed census is in [`raw/ast-owner-delta.log`](raw/ast-owner-delta.log).

The production sequence remains invocation capture → payload build → decision-validity preparation → publication gates → packet CAS persistence → epoch-owner finalization. A real blocked-gate probe returned `phase5_validation_failed`, wrote no decision-packet ref, and registered no issuance. The owner probe output is in [`raw/epoch-owner-blocked-gate-probe.log`](raw/epoch-owner-blocked-gate-probe.log). Successful epoch issuance, exact packet basis/history reconciliation, selected-view preservation, and restart survival are covered by the focused tests.

The dynamic API census is unchanged at 296 names (0 added, 0 removed); `runtime.__all__` still matches. The `BuildDecisionPacketNode`, its `execute` method, and `_build_policy_summary` retain their expected canonical FQNs, and the legacy shim resolves to the same class object. See [`raw/api-and-owner-identity.log`](raw/api-and-owner-identity.log).

The schema literals remain the same (`3.4` packet and `3.2` run record); no status or authority rule changed. The obsolete decision-packet complexity exception was removed. The section modules are within the configured C901 limit of 12 and below the prior 926-line maximum for the builder: builder 886, enrichment 760, validation 645, basis 686, causal 348, outcome 802, strategic 415, uncertainty 216, and support 296 nonblank/noncomment lines. Exact measurements are in [`raw/module-sizes.log`](raw/module-sizes.log).

## Verification

- Focused contract and epoch issuance tests: **68 passed**, 2 upstream Torch/Python 3.14 deprecation warnings. Full output: [`raw/focused-pytest.log`](raw/focused-pytest.log).
- Ruff for the full decision-packet package and support module: pass. Formatting check: 13 files already formatted. Outputs: [`raw/ruff-check-full-package.log`](raw/ruff-check-full-package.log) and [`raw/ruff-format-full-package.log`](raw/ruff-format-full-package.log).
- Explicit C901 limit 12: pass. [`raw/ruff-c901-12-full-package.log`](raw/ruff-c901-12-full-package.log).
- Diagnostic with Ruff's default C901 threshold of 10 reports three functions (12, 11, 11). The repository's configured cap is 12, so this is not a component failure; it is recorded for transparency in [`raw/ruff-c901-default-10.log`](raw/ruff-c901-default-10.log).

## Remaining scope

Three broader repository-quality tests remain red and are not accepted or closed by this component review: the module-size gate measures unchanged `check_package_import_gates.py` at 1,627 against 1,580; the module-size deadline is `2026-10-01`, earlier than the review date `2026-10-09`; and the exception-expiry gate finds an expired `propagate_welfare.py` entry dated `2026-08-15`. The test output is [`raw/complexity-budget-tests.log`](raw/complexity-budget-tests.log); unchanged base controls are recorded in [`raw/preexisting-complexity-controls.log`](raw/preexisting-complexity-controls.log). These broader closeout items and the remaining native suite are separate pending scope. No global readiness or G decision follows from this review.

Pattern pass: P06/P13/P29/P32/P33/P34/P38/P40/P41. The prior complexity issue is the same module-size/complexity class, addressed by widening the extraction across the complete section set. The remove-the-property-keep-markers controls exercised real validity and owner issuance behavior; they did not depend on field names alone. No second component escape was found. The broader red gates above remain explicit and unresolved.

All raw command outputs and source fingerprints are under [`raw/`](raw/); source, test, docs, and output hashes are indexed in [`raw/review-fingerprints.sha256`](raw/review-fingerprints.sha256).
