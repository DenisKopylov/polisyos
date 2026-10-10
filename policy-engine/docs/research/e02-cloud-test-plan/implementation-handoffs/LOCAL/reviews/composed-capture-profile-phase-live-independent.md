# Independent review: live capture profile and phase controls

## Verdict

**Partial, with the requested light behavior checks passing on the reviewed wrapper.** The exact `894300665556ef644ffffb67ab2dc0508ff4e7f8d840bf256bb199c885889087` wrapper reads the actual selected Mac virtual-environment profile, admits the prepared 19-command base plan and 11-command supplement on a fresh output identity, refuses existing selected outputs, refuses same-plan continuation past an unselected prior output, and recomputes the real base/supplement output bindings while prior output exists. Malformed and escaping source paths remain rejected.

**P40 bucket: SAME_CLASS_DEEPER.** The preceding `fd6e137875357c254f4b978392803462f3b1145f2dee88247050dfde44647940` version had a deeper source/output readback call-chain defect: `_manifest_output_bindings()` passed `allow_existing_outputs=` to a `load_and_validate_plan()` function that did not accept it. The preserved old-byte probe reproduced `TypeError`; the reviewed delta removes that unsupported keyword and the exact actual binding call now passes. I found no second class requiring a wider mechanism.

This is not a current source-freeze or full-run receipt. HEAD was `e38eaa9441661a363006a0e9aef7d52cd65fca54`; the selected plan still has no final commit/tree, and root explicitly deferred main `--validate-only` until the source commit. No product test, heavy command, native fit, main `--validate-only`, or full raw-source-manifest scan was run here. Formal G closure is untouched.

## Exact inputs and retained probe

- Wrapper: `LOCAL/raw/composed_mac_capture.py`, SHA-256 `894300665556ef644ffffb67ab2dc0508ff4e7f8d840bf256bb199c885889087`.
- Origin plugin: SHA-256 `b1920931f4a31ef2561874e0f076f4683e45462123290a26afaab26f862f9298`.
- Base plan: `LOCAL/r4-workload/composed-mac-current-source-replay-plan-20261010.json`, SHA-256 `48512a6a40a43a3d6c4d2723b2cb6ecde34d6725251ab03187ebd69b0b9e430a`.
- Supplement: `LOCAL/raw/composed-mac-current-source-replay-plan-20261010/supplemental-light-gap-checks.json`, SHA-256 `67199b1ad751cafd275732abc9d49a1607a2ed237214278267befa694398d1b2`.
- Existing source manifest used only for its actual plan bindings: SHA-256 `0a13130ef3af096901845c0f5deb2185e9a8cc50983a636d03fda149fa5bb835`. It is not treated as a fresh whole-source identity receipt.
- Selected-environment inventory: SHA-256 `d5af118f8b018dc483d3b3caef61dfada97bfc26aeac416a90e8bcadf18fa736`.

The full probe input, stdout, stderr, and exit status are retained under `LOCAL/raw/composed-mac-current-source-20261010/_independent-review-profile-phase-live-20261010/`:

| Capture | SHA-256 | Bytes/result |
|---|---|---:|
| `stdin.txt` | `73a3b41348c2a2ac68923a73c4f144e78d7270b06f70e97b233d9b8bc39878c3` | 9,368 |
| `stdout.json` | `425bf95ba19b9f86542be97292d3d7e1865adfa97ec6dc0db1769d567630e95b` | 22,478 |
| `stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 bytes |
| `status.txt` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` | `0` |

The probe imported only the raw wrapper’s standard-library code. Its `package_versions()` subprocess ran the selected interpreter with `importlib.metadata`, `platform`, and `sys`; it did not import the model packages or execute tests.

## Requirement-to-evidence

| Requirement | Direct check | Result |
|---|---|---|
| Profile is read from the lexical product interpreter and matches its venv | Called `selected_product_python()`, `package_versions()` and `validate_product_python_profile()` using the first actual base-plan command | **PASS:** selected `.venv/bin/python`; Python 3.14.3; `sys.prefix` equals `policy-engine/.venv`; `base_prefix` is the uv CPython 3.14.3 installation; 248 distributions exactly match the prepared 248-entry inventory. Reported versions: pytest 9.0.2, NumPy 2.3.5, Torch 2.10.0, BoTorch 0.16.1, GPyTorch 1.15.1, JAX 0.8.2, Pydantic 2.12.5. |
| Wrong-base substitution is rejected before product execution | Ran metadata-only `package_versions()` on the resolved base interpreter, then tried that resolved path as the selected command entrypoint and as the runtime profile | **PASS:** the direct base interpreter reports only pip 26.0.1 (1 distribution; all seven queried package versions null); `selected_product_python()` rejects its non-venv lexical path, and profile validation rejects its base `sys.prefix`. No product command ran. |
| Actual prepared supplement loads and phase rules are enforced | Loaded the actual 11-command supplement. Its existing I1 output directory was present. Called `checked_paths_for_commands()` with I1 selected and `refuse_unadmitted_unselected_outputs()` with I2 selected | **PASS:** load succeeds; selected I1 root is refused as already present; selecting I2 refuses the prior I1 root as unsupported same-plan resume. This is the explicit no-resume boundary; it is not a claim that the previous output is accepted as a successful receipt. |
| Existing output is tolerated only while recomputing the plan binding | Called `_manifest_output_bindings()` on the actual source manifest, which contains the actual base and supplement plan bindings | **PASS after delta:** two plans and 60 plan-derived output roots recomputed while the supplement I1 output exists. This is the real output-binding path used by raw manifest verification; it does not by itself prove every raw source byte or an end-to-end execution receipt. |
| Invalid/escaping sources remain rejected | Tried a parent-relative Git path, an escaping manifest plan path, an outside-LOCAL/raw supplement capture root, and an outside-product supplement base plan | **PASS:** all four raised `CaptureError` before accepting the invalid path. |
| A fresh full plan is selectable and its output roots are preflightable | Replaced the base plan’s root in memory with a new absent LOCAL/raw descendant; ran canonical validation, `select_commands(... allow_heavy=True)`, `admit_plan_output_root()`, and `checked_paths_for_commands()` | **PASS:** the full 19 IDs select in plan order, the new root is admitted, and all 19 command absence preflights pass. Zero commands executed. The heavy flag only allowed plan selection; it did not release or use the heavy slot. |

The old-byte deciding reproduction is separately retained under `.../_independent-review-profile-phase-20261010/`. On the prior `fd6e137...` target, `verify_raw_source_manifest()` returned `FAIL` at `manifest_output_root_binding_mismatch` with `TypeError: load_and_validate_plan() got an unexpected keyword argument 'allow_existing_outputs'`, despite an otherwise valid plan binding and existing supplement output. That is historical evidence for the same-class defect, not the current result. The current direct binding probe above passed after the `894300...` delta.

## Limits

I did not rerun the full `verify_raw_source_manifest()` after the repair. The product source is still moving and the existing manifest is not a fresh freeze; root also deferred whole-source validation until commit. Therefore current all-file source identity, the author-reported scanner findings, final Git identity, `main --validate-only`, and execution of either queue remain **not established by this review**. The light checks establish wrapper behavior at these selected seams only. The raw source manifest and these checks do not establish scientific/runtime capability or any original criterion closure.
