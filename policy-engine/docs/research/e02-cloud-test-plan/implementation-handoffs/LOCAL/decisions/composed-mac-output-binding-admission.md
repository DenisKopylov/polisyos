# Output-binding-only plan admission proposal

Status: patch-only proposal; unapplied. No runtime command or test was run.

## P38 property and divergence

The manifest builder must bind every declared command output root so source scans can exclude only plan-owned outputs. It currently uses `_plan_uses_only_product_python` as the admission test for every plan in `plan_output_bindings`. That predicate answers whether a command starts through the selected product Python interpreter; it does not answer whether a separately owned route has a valid, non-executable output-root declaration. The six-plan freeze includes a real external-consumer plan whose canonical DTO intentionally marks it non-executable, so the proxy rejects a valid root-binding input before the manifest can include its output roots.

## Proposed structural boundary

The diff adds one generic classifier for the declared output-binding-only DTO shape: exact plan-only status, `capture_cli_execution_compatible is False`, `no_execution_performed is True`, nonempty purpose/reason, and a nonempty command list where every command has `command_type == "external_output_binding"`. This admits arbitrary command counts within that typed class; it does not enumerate the seven current command IDs.

The classifier is accepted only for a plan path explicitly listed by the caller in `additional_plan_paths`. An implicit `_source_plan_paths` reference, malformed/unknown marker set, or non-Python primary plan still fails. Each admitted external command must have all derived roots absent and symlink-free at preparation time; the existing overlap check remains authoritative across the full binding set. Every candidate plan now contributes its full `declared_local_source_paths` set to the source scan, including source inputs, selected tests, fixture paths, referenced plans, and the plan file itself.

The selected primary-plan `_plan_uses_only_product_python` check remains unchanged, as do execution-time product-Python/profile/source checks. The new class contributes only pinned output roots and declared source inputs; it is not executable, a run receipt, a source-freeze exception, or authority to bypass the external route's owner-specific adapter.

## Current six-plan input set

The final source-companion receipt calls for one primary and four additional plans; this external route is the sixth binding. These hashes were read back from the candidate tree at proposal time:

| Role | Product-relative path | SHA-256 |
| --- | --- | --- |
| Primary | `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/composed-mac-final-replay-plan-20261010-r2.json` | `eae051fdf3a5bfcade7c08bb0c90a090e36b7bc4d8debab9bc9c8fd6820ade36` |
| Additional | `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/composed-mac-final-supplement-plan-20261010-r2.json` | `d5edbb3027daefbbc25bc7e38952c7aa97d0af821af43195ef6fd69f2386e237` |
| Additional | `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/composed-mac-current-source-replay-plan-20261010.json` | `48512a6a40a43a3d6c4d2723b2cb6ecde34d6725251ab03187ebd69b0b9e430a` |
| Additional | `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-current-source-replay-plan-20261010/supplemental-light-gap-checks.json` | `67199b1ad751cafd275732abc9d49a1607a2ed237214278267befa694398d1b2` |
| Additional | `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/composed-mac-tool-selftest-plan-20261010-r2.json` | `7cee5538169a888bf8b6c4c3e8ef31c6a2a6a8a7618559c5310f11714260c957` |
| Additional, output-binding-only | `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/composed-mac-tool-external-consumers-plan-20261010-r2.json` | `df9ce854ac25ec01dff6c7ca0d1d2e52e0caf3c8a7ac5236dba2dca3b4f2e747` |

The source-companion receipt identifies the first five roles. The final row is the external-consumer route whose `execution_mode.capture_cli_execution_compatible` is false and whose seven commands are typed `external_output_binding`.

## Patch and limits

Source preimage: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed_mac_capture.py` SHA-256 `8d4c418a7966915d45e5a4821e548fe6b80cce1cdf8fb81f7380e12b439f9454`. Proposed in-memory text passed `ast.parse`; no source file was edited, no patch was applied, no runtime/test was run, and no Git operation was performed.

The root owner should apply/review the diff and run focused controls for: accepted explicitly additional external DTO with all six plans; refusal when the external plan is primary or only implicitly referenced; refusal when any required marker or a command type is missing/altered; refusal for existing/symlinked roots and overlapping roots; and proof that each additional plan's declared local source inputs join the complete source denominator. These are unexecuted acceptance checks, not claimed results.

Pattern pass: P38 proxy admission; P40 same-class deeper plan-kind route, closed by one typed output-binding-only class rather than per-plan exceptions. Capability status remains `verification_missing` until applied and exercised; this patch is not a test receipt or a new execution capability.

Evidence sources and artifact identity:

- Patch artifact SHA-256: `290429cd54b6c1b2e78fdc2fa424e0577fe04b354d6482d5c824ef517ac64b0a`.
- The primary-plus-four-additional plan roles are from `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/final-plan-last-source-companions.md` @ SHA-256 `10151cf9bf7ac5d95958509e0f11a3d332edd708da80725c2725497b43fcbe21`.
- Independent companion review: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/reviews/final-plan-last-source-companions-independent-20261010.md` @ SHA-256 `e94aca5818297029e111a1e86ca4763d94e167e7e98c3a49211340e46addd602`.
- External route scope review: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/reviews/c12-real-http-output-scope-independent-20261010.md` @ SHA-256 `7ee5a636764a3f9dd2971ad0c1ef85525ea811fadf5c3c3da577f1b0497d7f1b`.
