# Final-wave process environment capture readiness

Read-only audit of the prepared composed-Mac 19-command base plan and 11-command supplement. The current source anchor reported by root (`00954ff`) is still awaiting final freeze; no final-wave command or test was run for this note.

## Evidence reviewed

- Current capture wrapper: `LOCAL/raw/composed_mac_capture.py` SHA-256 `894300665556ef644ffffb67ab2dc0508ff4e7f8d840bf256bb199c885889087`.
- Current pytest origin plugin: `LOCAL/raw/composed_mac_pytest_origin_plugin.py` SHA-256 `b1920931f4a31ef2561874e0f076f4683e45462123290a26afaab26f862f9298`.
- Strict handoff/environment validator: `LOCAL/emit_proposals.py` SHA-256 `4d5e70c67f62af07cdb7d3313ad3caa2a689172888b44051c13bb07e6dbbacec`; relevant functions are `normalized_environment_inputs`, `validate_environment_manifest_bytes`, and `validate_backend_environment_manifest`.
- Base plan SHA-256 `48512a6a40a43a3d6c4d2723b2cb6ecde34d6725251ab03187ebd69b0b9e430a`; supplement SHA-256 `67199b1ad751cafd275732abc9d49a1607a2ed237214278267befa694398d1b2`.

The initial 13e invocation is historical and partial: `LOCAL/raw/composed-mac-root-execution-13e411da-20261010/base-light.command.json` (SHA-256 `73e6d16e91f72d96fda65d0272116afe81dfd7fb219e00133a9ebe9ef0209b51`) completed `SOURCE_MODULE_READBACK=PREFLIGHT_PASS`, then `R1_PREPARED_B_CONTOURS=EXIT_NONZERO` and stopped with the remaining selected routes `UNRUN`. Root later ran independent `--only`/selected-range resumes against the same 19-command base plan; the complete retained command history is `LOCAL/raw/composed-mac-current-source-20261010/runner-history.jsonl` (SHA-256 `fac658ac4561a23f7c9c7a3881b947a15b0cf31d3066f3f34e8624d9fc7b8821`), with per-command metadata and JUnit files under that directory and invocation argv/streams under `LOCAL/raw/composed-mac-root-execution-13e411da-20261010/`. Across that complete inventory, 13 commands executed (source readback plus 12 pytest commands), with 12 JUnit files: 785 passed, 8 failed, 0 errors, and 0 skipped; six of the 19 planned commands remained `UNRUN`. These are multiple runs, not one uninterrupted invocation. They used the older wrapper `6f40ef9f…`, which supported selected resumes; the current wrapper `89430066…` does not. The initial R1 metadata is 2.9 MB (`2161935ae21826fde1625401dedba1f28aaa02204571d4e77a3aec4f520fb936`); it records Python 3.14.3 but no prefix, base prefix, distribution count, or non-null versions for the seven named packages. The retained runs are not receipts for the current wrapper or final source.

## What the current capture proves

`composed_mac_capture.py` records planned and actual argv, cwd, planned/capture environment overrides, launch-map environment values, timestamps, elapsed time, exit status, stdout/stderr/JUnit hashes, output inventory, and before/after source and wrapper/plugin hashes. It also runs `package_versions()` against the selected product `.venv` before commands; that separate probe reports interpreter details and installed distributions. `platform.platform()` is recorded by the wrapper process. These are useful source/command bindings, but the package inventory is not the pytest process’s loaded package/version set, the platform field is not the strict manifest’s process-bound `{system, release, machine}`, and the launch-map environment dump is not an allowlisted readback from inside pytest.

The plugin’s `build_origin_manifest()` records loaded `polisyos.*` and `tools.*` module origins and a product-root assertion. In the retained 13e R1 command, its sidecar reported 1,545 such modules and passed the origin assertion. The plugin does not record the child’s runtime/platform, environment settings, or a `package_version` per loaded origin. Its current output therefore cannot fill those strict manifest fields. The source-module preflight imports ten chosen local modules and prints their paths, but it is also a separate preflight command, not a substitute for process-bound capture from the selected test command.

| Strict manifest field | Existing evidence | Final-wave gap |
|---|---|---|
| `candidate_source` | Wrapper checks and records exact commit/tree. | 13e is stale; bind the final frozen commit and full tree. |
| `backend_id`, `profile_id` | Plans select the product `.venv`; current profile probe checks its interpreter target. | No captured strict backend/profile identity; name the actual selected profile after freeze. |
| `source_refs` | Frozen source-input manifest contains path/hash rows. | Add role-tagged refs for the actual recipe and config/lockfile, matched to the handoff footprint. |
| `runtime` | Pre-run `.venv` probe reads Python version, executable, prefix/base prefix, and installed distributions. | It is separate from each pytest process; old 13e output lacks prefix and package versions. |
| `platform` | Wrapper records `platform.platform()`. | It is wrapper-side text, not process-bound `{system, release, machine}`. |
| `loaded_import_origins` | Pytest sidecar checks local `polisyos`/`tools` origins. | No loaded third-party origins with their distribution versions. |
| `environment_settings` | Wrapper records planned overrides and a broad redacted launch map. | No allowlisted child-process readback; do not reuse the inherited-environment dump as the strict settings map. |
| `command_runs` | Completed command metadata binds actual argv, cwd, status, stdout/stderr/JUnit hashes. | 13e covers only the preflight and one failed R1 command; final commands need fresh records. |
| `selected_inputs`, `selected_input_denominator_sha256` | Old source/frozen-input manifests enumerate source paths and plan fixtures. | Rebuild at final freeze; strict validation hashes the submitted list but does not prove its completeness. |

## Smallest capture delta before the freeze

If authorized, keep the capture addition confined to the existing plugin receipt, preserving its root assertion and PID-specific, create-once output. Add process-observed fields to that receipt:

- `runtime`: Python implementation/version and `sys.executable` from the pytest process.
- `platform`: `platform.system()`, `platform.release()`, and `platform.machine()` from that process.
- `environment_settings`: only named non-secret runtime controls read from the child’s `os.environ` (the six thread caps, `PYTHONPATH`, `PYTHONDONTWRITEBYTECODE`, `PYTEST_PLUGINS`, `PYTEST_ADDOPTS`, `POLISYOS_RUN_NATIVE_GP_HEAVY`, and `POLISYOS_RUN_NATIVE_METHODJOB_WORK`); represent unset allowlisted keys explicitly as `null`. Do not copy the complete inherited environment into the strict manifest.
- `loaded_import_origins`: the observed import origin and corresponding distribution version for loaded third-party packages, retaining the existing `polisyos`/`tools` source-origin checks. For in-tree modules, bind the value to the frozen source tree rather than inventing a released package version.

The plugin sidecar already lands in the command output directory, whose inventory hashes it. The root receipt builder can combine that exact sidecar with the wrapper’s actual command metadata and final frozen input manifest; the plugin alone does not create the complete strict environment manifest. If one handoff spans commands with different runtime flags, do not collapse conflicting values into one profile: split by actual profile/command or extend the manifest contract to bind settings per command.

## Strict-manifest binding and input denominator

The strict v1 validator requires the exact manifest fields, exact candidate commit/tree, runtime and platform structures, unique loaded-origin rows with nonempty origin/version strings, scalar non-secret settings, and `source_refs` whose hashes match `source_footprint` (including a backend recipe and a config or lockfile). It reconciles one `command_runs` row to every handoff command, including argv, cwd, status and stdout/stderr hashes. `validate_backend_environment_manifest()` reads and hashes the canonical ignored `LOCAL/raw` manifest bytes.

`selected_inputs` is the weak point in completeness: the validator checks unique identities, `available`/`unavailable`, hash shape, equality between the handoff and environment manifest, and a canonical digest of that list. It does not require a nonempty list or derive the list from the frozen source/fixture manifest. An empty or shortened list copied consistently to both sides can satisfy those specific checks. Do not claim completeness from the self-hash; bind the selected list to the final source/fixture manifest (or add a source-manifest reference and recomputation to a future schema version) before using it as an authority-grade predicate.

For the final run, regenerate the existing wrapper manifests after the final source freeze, using both exact plans through the existing source-manifest API. The prior 13e source-input manifest had 1,306 LOCAL source/config rows and bound both plans; its file SHA `d85ba837…` and 13e tree are historical and must not be reused. The prior frozen input manifest had 135 selected paths and two plan-declared fixtures; it is also not the final denominator. The plan-defined K3 history JSON has an exact value SHA in the old manifest, while the R4 roster explicitly says its materialized child-CAS input digest is not established until the bytes/ref are captured. Rebind those declarations at the final freeze; leave that materialized digest unavailable until there is an actual artifact hash.

Count source-defined fixture recipes and values as selected inputs only when the frozen plan/source manifest names them. The K3 JSON literal and R4 roster parameters are controlled inputs defined before the run; the R4 CAS materialization is a separate produced artifact until it is actually written and read by a consumer. Likewise stdout, stderr, JUnit, command metadata, origin sidecars, temporary CAS blobs, and R4 child streams are produced outputs, not selected inputs. If a later command consumes a prior command’s output, bind that exact artifact as an input to the receiving command rather than predicting it in the initial denominator. Use `path@sha` references and retain the actual full output streams; do not copy source text or add a production-data census.

No code, validator, wrapper, plugin, plan, or command output was changed by this audit. No pytest, source freeze, production payload read, or Git command was run.
