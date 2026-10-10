# Output-binding-only admission proposal, v2

Status: patch-only proposal; unapplied. The v1 artifact is preserved unchanged.

## Added selected-plan boundary

The v1 manifest admission separated output-root derivation from product-Python execution, but a selected plan with `execution_mode.capture_cli_execution_compatible: false` and `.venv` argv could still pass the path-based Python check. In the ordinary `run_one` path, that leaves a route that is expressly non-executable able to reach capture as a selected plan. V2 adds a fail-closed selected-plan check in both CLI branches that load a primary plan: manifest preparation and execution/`--validate-only`. In the execution branch it runs immediately after plan validation and before output-root creation or lock acquisition; the preparation branch checks before it writes the model-assets or source-input manifest.

The selection predicate refuses (a) the exact output-binding-only status, (b) any command typed `external_output_binding`, or (c) any present `execution_mode` that is malformed or does not explicitly set `capture_cli_execution_compatible` to the boolean `True`. Thus a forged product-Python argv cannot turn a non-executable DTO into a runnable selected plan. Additional plans remain a separate path: a fully typed output-binding-only plan may contribute roots only when explicitly named in `additional_plan_paths`; every such command's roots must be absent and symlink-free. It is never run from this admission path, whether its argv names product Python or an external tool.

## Preserved and widened manifest behavior

The v1 patch's generic typed DTO recognizer, additional-only admission, output-root absence/overlap/symlink controls, and union of every candidate plan's declared local source paths are retained. The primary manifest plan still must pass the existing `_plan_uses_only_product_python` check, and existing execution-time Python/profile/source identity checks remain unchanged. Unknown or malformed non-executable declarations fail closed instead of falling through to interpreter-path admission.

P38 remains the underlying class: execution compatibility had been used as a proxy for output-root describability, and the reverse direction also needed an explicit gate. P40 is the same class one level deeper; v2 widens the shared plan-kind boundary for both binding and selection rather than adding per-plan exceptions.

## Bound plan set

The six candidate plan files and SHA-256 values are preserved from v1:

| Role | Product-relative path | SHA-256 |
| --- | --- | --- |
| Primary | `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/composed-mac-final-replay-plan-20261010-r2.json` | `eae051fdf3a5bfcade7c08bb0c90a090e36b7bc4d8debab9bc9c8fd6820ade36` |
| Additional | `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/composed-mac-final-supplement-plan-20261010-r2.json` | `d5edbb3027daefbbc25bc7e38952c7aa97d0af821af43195ef6fd69f2386e237` |
| Additional | `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/composed-mac-current-source-replay-plan-20261010.json` | `48512a6a40a43a3d6c4d2723b2cb6ecde34d6725251ab03187ebd69b0b9e430a` |
| Additional | `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-current-source-replay-plan-20261010/supplemental-light-gap-checks.json` | `67199b1ad751cafd275732abc9d49a1607a2ed237214278267befa694398d1b2` |
| Additional | `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/composed-mac-tool-selftest-plan-20261010-r2.json` | `7cee5538169a888bf8b6c4c3e8ef31c6a2a6a8a7618559c5310f11714260c957` |
| Additional, output-binding-only | `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/composed-mac-tool-external-consumers-plan-20261010-r2.json` | `df9ce854ac25ec01dff6c7ca0d1d2e52e0caf3c8a7ac5236dba2dca3b4f2e747` |

## V2 artifact and verification limits

Source preimage: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed_mac_capture.py` SHA-256 `8d4c418a7966915d45e5a4821e548fe6b80cce1cdf8fb81f7380e12b439f9454`. V2 is a complete source-derived unified diff from that exact preimage; its patch SHA-256 is `0025294599ba1a9f9b560b49adeb50d9a7760aa625eb9343bac8c1f8e36799b9`. The proposed text passed `ast.parse`. No product source was edited, patch applied, runtime/test executed, or Git command run.

Focused acceptance controls for the root owner: selected external plan is refused even with a forged `.venv/bin/python` argv; both normal and `--validate-only` paths refuse before output-root/lock creation; manifest preparation refuses such a plan before writing asset/source manifests; an exact external DTO is admitted only as an explicit additional binding plan and is never selected/executed; malformed/missing mode markers and altered command types refuse; existing/symlinked/overlapping roots refuse; full declared local-source inputs from each additional plan enter the source denominator. These controls remain unexecuted and the capability remains `verification_missing` pending root apply and checks.

V1 patch preserved at `LOCAL/raw/composed-mac-output-binding-admission-v1.patch` @ SHA-256 `290429cd54b6c1b2e78fdc2fa424e0577fe04b354d6482d5c824ef517ac64b0a`. The plan-role receipt remains `LOCAL/r4-workload/final-plan-last-source-companions.md` @ SHA-256 `10151cf9bf7ac5d95958509e0f11a3d332edd708da80725c2725497b43fcbe21`; the independent companion and external-route reviews are cited in the v1 note.
