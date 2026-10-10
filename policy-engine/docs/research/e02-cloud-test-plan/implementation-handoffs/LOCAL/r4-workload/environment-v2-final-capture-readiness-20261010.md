# Environment v2 final-capture readiness

Read-only audit against announced `01c9a68f5bc10751f890468e4a2cfac1bcfe384b`. No final-wave command or falsifier was run for this note. The builder and harness are executable now; a fresh, root-bound source manifest and a successful captured command are still required before their outputs can support the planned falsifiers.

## Source readback

| Source | SHA-256 | Relevant boundary |
|---|---|---|
| `LOCAL/raw/env_manifest_adapter.py` | `ba037da67a4ebf036687c5fd4a95ac3d37722358a1c1c7236762f2414126e65c` | `build_observation` / CLI at lines 1192–1521; recomputes source context and exact plan inputs. |
| `LOCAL/raw/environment_v2_falsifiers.py` | `03c471471d694eafa135b9049bc861231861f3a95121d6f58b4bef757dc69fce` | `baseline_evidence`, `bind_output_owner`, and CLI at lines 117–1016. |
| `LOCAL/raw/composed_mac_capture.py` | `f679c64e6d9d8e2f9bf659d06e95b708d28fe5bd12e2164ac78bf7b3afa2a8bc` | Source-manifest verification, `inspect_source_identity`, plan input projection, and PID receipt at lines 992–1110, 1555–1680, 1790–1854, and 2704–2710. |
| `LOCAL/raw/composed_mac_pytest_origin_plugin.py` | `02e43a40767d23f2e042ea8d1d0c4db3585b3697de38db50e79e6e8136175352` | Same-process runtime, platform, allowlisted settings, import-origin capture, and PID-suffixed sidecar at lines 320–583. |
| R3 base plan | `4a825bbc495f13efacadc835c88d86da138fdf6f092d5952659ced2fe016164e` | 19-command base, including `R1_PREPARED_B_CONTOURS`; its source/freeze identities are still placeholders. |
| R3 supplement plan | `121f240ddac113351ee80f2360a620961ab56edc7bba7e3b5041422e48e60d45` | 11-command supplement. |
| R3 tool self-test plan | `a9a88b0a510a92617b83ae34144147940f9a86c17fcf6e527af4b6cb1ec45245` | Source-input manifest path declaration for the R3 wave. |
| external-consumers plan R2 | `b3a9c247a7ae894035b81d334e16233de8c51ac2795567bcd9930b15c4d24c33` | Contains the only prepared `ENVIRONMENT_V2_FALSIFIERS` command and output binding currently read. Its presence in the final source manifest must be verified. |

The current R3 base plan still records `source_scope.final_commit/tree=null`, a not-generated freeze manifest, and `UNRUN` commands. Therefore this audit cannot certify the future nine-plan source manifest or any runtime result. The final source manifest must bind the actual final plan bytes and all nine intended plan bindings; the adapter then matches the executing command to exactly one byte-identical plan. The falsifier harness separately requires exactly one source-manifest-bound `ENVIRONMENT_V2_FALSIFIERS` command. Do not rely on the external R2 plan’s prose saying “shared six-plan manifest”: the final manifest’s actual bindings and count are the evidence.

## Building the R1 observation

The adapter’s supported API is `build_observation(root, *, command_metadata_path, capture_path, stdout_path, stderr_path, junit_path, plugin_path, source_manifest_ref, frozen_input_manifest_ref, handoff_path=None, source_change_census_path=None)`. The equivalent CLI is below. Its evidence paths must be repository-relative, regular non-symlink files. Convert plan paths under the product root by prefixing `policy-engine/` when passing them to this repository-root CLI.

```sh
python3 -B policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/env_manifest_adapter.py \
  --repo-root . \
  --command-metadata policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r3/base/r1_prepared_b_contours/metadata.json \
  --process-capture <repo-relative-PID-suffixed-origin-sidecar> \
  --stdout policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r3/base/r1_prepared_b_contours/stdout.bin \
  --stderr policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r3/base/r1_prepared_b_contours/stderr.bin \
  --junit policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r3/base/r1_prepared_b_contours/junit.xml \
  --plugin-source policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed_mac_pytest_origin_plugin.py \
  --source-input-manifest <repo-relative-final-nine-plan-source-manifest> \
  --frozen-input-manifest policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r3/base/freeze-input-sha256.json \
  --output policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r2/tools/environment-v2-falsifiers/baseline-observation.json
```

Use these paths only if the fresh R1 command metadata and final plan still declare them. Obtain the actual sidecar from the command metadata’s `capture_environment_overrides.POLISYOS_CAPTURE_ORIGIN_FILE` base and its `module_origin_assertion.receipts[]` entry for the captured process PID. The plugin writes `<base stem>-<pid><suffix-or-.json>`; select the unique receipt whose PID, path, and SHA match the actual `process_environment.pid` and file bytes. Do not pass the unsuffixed base path or an older sidecar. The R3 R1 plan currently names `metadata.json`, `stdout.bin`, `stderr.bin`, and `junit.xml` under `base/r1_prepared_b_contours/`; its `freeze_input_manifest.path` is the `base/freeze-input-sha256.json` path above. The R3 self-test plan declares the source manifest at `LOCAL/raw/composed-mac-final-source-inputs-20261010-r3.json`; root must confirm the final manifest is actually generated there and has all nine intended plan bindings before using it.

The adapter recomputes current HEAD/tree and wrapper/plugin bytes through the actual wrapper, checks the source manifest and the exact R1 plan binding, and calls `verify_input_manifest` to reconcile the complete R1 source/test/fixture projection with the frozen input manifest. It also checks that command metadata’s input/source-manifest digests match. A successful serialization readback is:

```sh
python3 -B policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/env_manifest_adapter.py \
  --repo-root . \
  --output policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r2/tools/environment-v2-falsifiers/baseline-observation.json \
  --check
```

`PASS_PARTIAL_OBSERVATION` is an honest and expected possible result. Without a typed v2 handoff, the adapter records backend/profile and strict-v1 projection as unestablished/refused; unresolved external or non-filesystem modules also keep the observation partial. That does not by itself block this harness: `baseline_evidence` explicitly accepts a revalidated partial observation if its current source freeze, exact plan denominator, command-input binding, and PID-sidecar binding resolve. It does not make the profile admitted, prove every imported child’s origin, or close any finding. The plugin’s declared import scope is one observed origin per loaded top-level import root, with loaded child names listed but not a per-child origin/content record; unresolved roots remain partial. This is **P40 SAME_CLASS_DEEPER** within environment provenance, not a new authority class.

## Running the 12 falsifiers

The presently prepared external plan (`composed-mac-tool-external-consumers-plan-20261010-r2.json`) gives this exact command from the repository root, with a fresh baseline and absent `harness/` child:

```sh
python3 policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/environment_v2_falsifiers.py \
  --repo-root . \
  --baseline-observation policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r2/tools/environment-v2-falsifiers/baseline-observation.json \
  --output-parent policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r2/tools/environment-v2-falsifiers/harness
```

Run that argv only if the final nine-plan source manifest binds this exact external plan and exactly one ENV command with those bytes, cwd, baseline path, output parent, and output root. `bind_output_owner` recomputes the source manifest/output-root bindings, reads the external plan, and requires the actual args to equal its planned argv. If root replaces or relocates the plan, derive all args from the new frozen plan; do not widen the output parent to `LOCAL/raw`. The baseline and the new `harness/` child must be strict descendants of the verified command root, and `harness/` must not exist before launch.

The harness executes the 12 controls documented at `LOCAL/crosswalk/environment-v2-falsifiers-readiness.md`: wrong PID path; capture-PID mismatch; plugin digest mismatch; changed sidecar bytes; candidate-tree drift; source-manifest digest drift; command-output inventory drift; false aggregate-complete status with unresolved imports; unattested `_virtualenv` owner/version; `opentelemetry` root without child origins; a required plan-input omission with recomputed hashes; and canonical no-replace versus replacement-enabled Git projections in an isolated fixture. Every control’s streams, mutated inputs, readbacks, and result are retained. Any `UNRUN` control makes the overall run `INCOMPLETE`, not a success. The replacement-object case writes only under its ignored harness output, never refs in the candidate checkout.

One current admission proxy must be respected. Adapter `_validate_command_capture` sets normalized outcome to `PASS` for exit code zero and zero JUnit failures/errors; harness `baseline_evidence` repeats those same checks but does not reject skipped cases or independently require wrapper metadata `status=PASS`, `pytest_result_status=PASS`, `timed_out=false`, and `launch_error=null`. The R1 plan requires every selected case to pass with zero skips. Before treating the harness as an eligible baseline, compare the actual wrapper receipt and complete JUnit testcase outcomes against that requirement; if there is a skip or failed wrapper status, do not interpret harness PASS controls as validating a passing test run. This is **P40 SAME_CLASS_DEEPER** in the command/outcome proxy class (P38), not a reason to infer success from a marker. The harness source remains unchanged in this audit.

No final source freeze, v2 observation, falsifier run, runtime-profile admission, or formal closure is claimed here. Old V5 captures are not inputs to this procedure.
