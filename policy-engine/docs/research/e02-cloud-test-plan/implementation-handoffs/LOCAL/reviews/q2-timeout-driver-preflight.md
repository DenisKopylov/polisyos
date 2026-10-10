# Independent review: Q2 adaptive timeout driver preflight

## Verdict and exact boundary

**Partial; one medium evidence-integrity finding remains.** The driver refuses to calibrate the next profile from a bad or incomplete predecessor, preserves the runner's normal command flow, and captures real partial stdout/stderr on an actual subprocess timeout. The successful-predecessor checks and the input path/hash checks are supported by fresh evidence below. The timeout artifact path does not bind the partial stream bytes to the failure sidecar, so that sidecar is not yet a content-bound record of a timed-out consumer run.

Reviewed candidate worktree: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`. The driver is ignored local raw input, not product source or an immutable Git commit. Exact hashes at review:

- `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/timeout_driver.py` — `bbbe0a8c39ee2d1974df4c614b2e63c3afab050b5d82a54ad01325175363883e`
- `.../q2-packaging/raw/run.py` — `5d54bce877979e82e3a7f95d451b6f076fcc318037868e329f26908065d80932`
- `.../q2-packaging/installed-wave-manifest.json` — `ab7cf774e1c6805e9b1812472e5b8357af1a6a43d50a994a7488f29442d06eb7`
- `.../q2-packaging/raw/test_timeout_driver.py` — `d38c1f2c01678434357817ac4fa6f0a1377bc0d99e8667bbf25353348ee4426f`
- `.../q2-packaging/timeout-plan.md` — `84ae0c81782d6bbe91932f3665a7373f7b898e8040f88b87ab92475bf8d29d14`
- Existing author test receipt — `.../q2-packaging/raw/timeout_driver_test_receipt.json` @ `717f575b7c89ec39aa3f25ec14be58f8c00027d6b3b10453358e65ec70037f16`

The runner and manifest match the driver's pinned hashes. The runner locates the same manifest as the driver: `raw/run.py` sets the handoff root to the parent of `raw`, matching `timeout_driver.py`'s `driver_path.parent.parent`. The plan invocation keeps all six runner arguments, including the optional output root.

## Requirement-to-evidence results

The driver loads only the exact runner and manifest hashes before import and rechecks them before writing its sidecar. `_run_root_from_log_stem` supports the runner's `logs/` and `consumer-runs/<profile>/` layouts. The wrapper delegates non-`consumer-suite` commands unchanged, requires the three expected consumer profiles in order, and requires direct stream capture. It gives profile one no timeout, then uses `ceil(2 * previous elapsed)` only after the previous profile's complete collection/JUnit/receipt checks pass.

`validate_completed_profile` independently derives the 91 baseline IDs from the frozen product and adds the nine manifest selectors. It requires exact 100-ID equality in both the collected list and JUnit, 100 executed tests with no skips/failures/errors, a successful consumer receipt, verified origin proof, the expected command timeout/stream settings, and retained stdout/stderr whose byte counts and SHA-256 values match the successful consumer receipt. A previous-profile JUnit failure and a wrong set with the same cardinality both prevent the next runner command.

The driver receives the actual runner's `parse_args()` result and calls `run_wave(args)` without rewriting the namespace. I independently exercised that path with the actual pinned parser and a stubbed `run_wave` (no source transport or Git operation): the recorded namespace preserved `/candidate/repo`, both 40-character source IDs, `/scratch/app-venv/bin/python`, `/scratch/dowhy-venv/bin/python`, and `/scratch/q2-runs/frozen` exactly. Runner/manifest path resolution and imports also succeeded through `_load_reviewed_runner` with their exact hashes.

## Finding

**MEDIUM — NEW P40 class: timeout partial streams are retained but not content-bound by the timeout receipt.** On a successful profile, `run.py::verify_consumer_run` adds the stdout/stderr byte counts and SHA-256 values to the consumer receipt. A timed-out command raises in `run_command` before `verify_consumer_run` executes, so those fields are never produced. The driver's exception row records the command/stdout/stderr paths, timing, error, outcome, and predecessor validation, but no stream byte counts or digests; `_write_calibration_sidecar` serializes it without hashing the stream files. The timeout command JSON itself records `argv`, return code, timeout, and `timed_out`, but no stream sizes or digests. The execution plan says the runner retains the complete files and hashes; that is true for a completed consumer receipt, not for this timeout path.

The fresh real timeout probe did retain both 25-byte marker streams, which establishes byte preservation for the tested case. Their hashes were stdout `0a518c22b11f288ee586cce67c77261045be359c25000b60c8d03749ca2308ae` and stderr `d5f8bae2b3816693e6642bf4390397aced1899104faf89ce161619ea9d032cea`. The command record says `timed_out=true`, `timeout_seconds=0.2`, and `returncode=null`, but contains neither hash. The timeout sidecar test only asserts that `stdout_path` appears; the real subprocess test checks for marker substrings, not byte count/digest or a timeout sidecar. Thus the preserved diagnostic bytes cannot be checked against the failure-sidecar record after the run. This does **not** let a failed profile authorize a later timeout; it limits the integrity of the failed-run evidence.

Smallest closure direction: after the runner has closed the stream files on the timeout path, record each stream's exact byte count and SHA-256 in the profile state/timeout sidecar. Extend the real timeout-sidecar test to verify those fields and reject a modified stream. Keep the files at their existing paths; no copying into the JSON sidecar is needed. This is one NEW class in this review; no second same-class escape was found, so P40 requires no ladder repair. No formal G closure is proposed.

## Fresh checks and retained outputs

Command, from the candidate worktree:

```sh
PYTHONDONTWRITEBYTECODE=1 policy-engine/.venv/bin/python \
  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/test_timeout_driver.py
```

Exit 0; all five tests passed, including sequential `None, 4, 5` timeout calibration, prior JUnit failure refusal, wrong 100-ID set refusal, partial-stream delegation, and a real 0.2-second timeout of the pinned runner's `run_command`. Full stdout: `.../q2-packaging/raw/reviewer-timeout-driver-preflight-20261009-r1/stdout.txt` @ `40e98bcd770c0b959a65439c6799e8b067f1130e7a81ad5baae6fdde742c3475`; stderr @ `a0a6aafe9a4690b0bfa23d276cd59f8a8edc6ff6e4e421d0f08b4a43484518f`; exit record @ `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.

The actual timeout artifact from that run is under `.../q2-packaging/raw/timeout-driver-harness/case-1791579601379725000/`: command JSON @ `160919a4eea63fcc627fb437c19c9bbaf6c2a972ee8c087105aaaf62a56e1c7a`, stdout @ `0a518c22b11f288ee586cce67c77261045be359c25000b60c8d03749ca2308ae`, stderr @ `d5f8bae2b3816693e6642bf4390397aced1899104faf89ce161619ea9d032cea`.

Additional independent controls ran in the same product-local Python process: a deliberately wrong pinned runner hash failed before import; appending bytes to a valid predecessor's stderr caused `validate_completed_profile` to refuse it; and the actual pinned argument parser passed all six supplied values unchanged to the stubbed `run_wave`. Full output: `.../q2-packaging/raw/reviewer-timeout-driver-preflight-20261009-r1/independent-controls.stdout.txt` @ `45dcd53d0794327c58493437983237b430e895101bab35155deac4ff2069287d`; stderr @ `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; exit @ `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.

Timing boundary: the driver measures around the full `runner.run_command` call. That excludes build/install/profile setup, but it also includes the runner's post-exit stream-file reads and command-record write. The metric is therefore command-call wall time rather than strictly child-process elapsed time; this is conservative for a timeout bound. No real selected Linux profile was run to quantify that overhead.

## Limits and process note

No selected Q2 package/build/install wave, Linux worker run, source transport, or heavy test was executed. The synthetic harness and real 0.2-second subprocess test are timeout-mechanism evidence only; they do not establish installed-consumer success or a final Q2 runtime receipt. This review is not G acceptance or integration publication.

Process note: I inadvertently ran `git status -sb` during the first inspection command before noticing the task's no-Git instruction. It was read-only and made no change; no Git command was run afterwards. No product source, tests, configuration, or runner inputs were edited.

## Delta review: terminal evidence binding

Reviewed the follow-up at the exact ignored-local input hashes supplied for this delta:

- `q2-packaging/raw/timeout_driver.py` — `915ce7fc1ccf9be9d164656c137e1bbe61255daeb89d49dc3e1cd6bc06a1e63b`
- `q2-packaging/raw/test_timeout_driver.py` — `95ddec022ffabe9758149e2ed1441ca35e2491c1477a7fb1867278da798b4adf`
- `q2-packaging/timeout-plan.md` — `2c71eae82a3216dc8ca159d90603ba5a0e03c6958422993028013901c020b592`
- `q2-packaging/raw/timeout_driver_delta_receipt_20261010.json` — `9206aec924d2626263869988fa6f7d138e8b57e8e328d5cb845afdaadcb01276`
- Reviewed runner and manifest remain at `5d54bce877979e82e3a7f95d451b6f076fcc318037868e329f26908065d80932` and `ab7cf774e1c6805e9b1812472e5b8357af1a6a43d50a994a7488f29442d06eb7`.

The prior NEW-class missing-digest defect is closed for regular terminal files: capture now records command/stdout/stderr paths, byte counts, and hashes on return and exception paths; unavailable files carry a reason; the exact captured files are rehashed before the wrapper returns/re-raises, before sidecar publication, and before a later profile can be calibrated. A changed command record or stream at the same path is refused. The existing manifest/runner pins, profile order, exact-100-ID predecessor checks, and ordinary argument pass-through remain intact in this delta.

**P40: SAME class, one level deeper.** `_capture_file_binding` opens a path with `O_RDONLY | O_NOFOLLOW` and only then applies `fstat`/`S_ISREG`. For a FIFO with no writer, `os.open` blocks before the type check can return `not_regular_file`; the driver therefore cannot record an explicit unavailable reason or finish its timeout sidecar. This is the same terminal-evidence binding/closed-failure class as the preceding missing stream digest, not a separate class. Because this is the second finding in the class, the closure needs to widen the generic file-open mechanism rather than add a FIFO-specific branch: open in a nonblocking way compatible with regular files, then reject every non-regular file after `fstat` (or use an equivalent race-aware mechanism). The falsifier below leaves a FIFO with no writer and requires capture to return an unavailable/non-regular result promptly; no instance-specific denylist is needed.

Independent actual-wrapper falsifier: a synthetic `run_command` wrote an ordinary command record and stderr, returned success, and left the expected consumer stdout path as a FIFO. Calling `install_adaptive_run_command(...).run_command(...)` then blocked while capturing stdout; a parent subprocess timeout stopped it after 0.35 seconds. The command record and stderr existed, but the driver did not return or raise and could not write terminal evidence. Full output: `.../q2-packaging/raw/reviewer-timeout-driver-delta-20261010-r1/wrapper-fifo-control.stdout.txt` @ `b8f69b1f7f1c9e8e5aca2faa5b56ba4aa9095de1b0e100a8c81aeceed88612fa`; stderr @ `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; exit @ `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`. The preserved FIFO is at `.../q2-packaging/raw/reviewer-timeout-driver-delta-20261010-r1/wrapper-fifo-control/consumer-runs/source-wheel/consumer-suite.stdout.txt`.

Fresh focused command:

```sh
PYTHONDONTWRITEBYTECODE=1 policy-engine/.venv/bin/python \
  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/test_timeout_driver.py
```

Exit 0; eight tests passed, covering exact-ID calibration and refusal, real timeout and nonzero child outputs, sidecar bindings, same-path command/stream mutation, and explicit missing-stream refusal. Full stdout: `.../q2-packaging/raw/reviewer-timeout-driver-delta-20261010-r1/harness.stdout.txt` @ `755a2adb7f32f6b666ef7a81bd7faf11bc0825c749fd439090f1230842302633`; stderr @ `df3aafad914809b5de968315dd9b5a676768c39a6465e573bb086b26c9f481ab`; exit @ `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`. Complete report: `.../q2-packaging/raw/timeout-driver-harness/report-1791580385030186000.json` @ `99812da411fff63532ad68e97d996893bee786db553290260348fe181e990815`.

No package wave, build/install, selected Q2 suite, worker provisioning, source transport, Git operation, source edit, or cleanup was performed in this follow-up. This is a delta-only independent review; no G acceptance or closure is claimed.

## Final delta review: generic non-regular terminal evidence capture

Reviewed the new delta by exact local input bytes (still ignored/raw, not an immutable source commit):

- `q2-packaging/raw/timeout_driver.py` — `eaa9c3f2355b05e2f55753da4ba297ca6f137a9ba7f4699e456d4ad872339a0a`
- `q2-packaging/raw/test_timeout_driver.py` — `ec3ecbba552cbe803f6fd51264fd239edc3b91f37b0aae5b4ac50a21df14eb44`
- `q2-packaging/timeout-plan.md` — `1b07143e3ed5165aaf10740c5c57edeedc5cd3f4d0fb726d7121201cfdfc2af3`
- Author's FIFO delta receipt — `q2-packaging/raw/timeout_driver_fifo_delta_receipt_20261010.json` @ `9a7ece0601710a0611762b2bf3fd7d85a47e1394fc7a57a593703f2b51fbd5dc`
- Pinned runner and manifest remain byte-identical at `5d54bce877979e82e3a7f95d451b6f076fcc318037868e329f26908065d80932` and `ab7cf774e1c6805e9b1812472e5b8357af1a6a43d50a994a7488f29442d06eb7`.

**P40 result: SAME class, second finding addressed by widening the generic file-binding mechanism.** The earlier FIFO-without-writer escape showed that the helper blocked before classifying the path. The revised shared `_capture_file_binding` now checks the path without following symlinks, opens nonblocking/no-follow, checks the opened descriptor with `fstat`, compares path/open identity, snapshots the full declared size, and checks descriptor stability and byte count. Both initial capture and subsequent verification use this helper. This is a generic regular-file gate across command/stdout/stderr, not a FIFO-specific exception. I found no same-class residual in the declared non-regular family or same-path content-change controls exercised here.

I independently reran the complete focused harness against those exact bytes:

```sh
PYTHONDONTWRITEBYTECODE=1 policy-engine/.venv/bin/python \
  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/test_timeout_driver.py
```

Exit `0`; 11 tests passed, 0 failures, 0 errors. They include the exact-100-ID and failed-predecessor refusal checks; actual child timeout and nonzero-command stream binding; missing, tampered, and changed-regular controls; FIFO no-writer nonblocking refusal; symlink/directory/socket/device refusal; and wrapper-sidecar failure recording. Complete deciding report `q2-packaging/raw/timeout-driver-harness/report-1791583146847809000.json` @ `e06ec376074413b0dfad26c7af2de73cca44794e49ec2587a12b07b0ea159bd6`. Full command stdout @ `q2-packaging/raw/reviewer-timeout-driver-final-20261010-r1/harness.stdout.txt` SHA-256 `adc233394eef387b9a9d696aa1b89c2325ffbce7f9a2a7cc682c4f6d5184423f`; full test-name output/stderr @ `.../harness.stderr.txt` SHA-256 `fa2329e82a2e6b6c0916100f9c997d5637ddc61eb6c581d33b2313d2a87c3f8b`; exit record @ `.../harness.exit.txt` SHA-256 `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.

I also independently reproduced the actual wrapper boundary with a synthetic successful underlying command that wrote the command record and stderr but left the selected stdout path as a FIFO with no writer. `install_adaptive_run_command(...).run_command(...)` returned control in `0.0004704s`, raised the expected incomplete-evidence `WaveFailure`, and `_write_calibration_sidecar` persisted `status=failed`, verification `failed`, and stdout reason `not_regular_file`. Full result `q2-packaging/raw/reviewer-timeout-driver-final-20261010-r1/independent-wrapper.stdout.txt` @ `0bbf2ad74e8ca9f2246254203f1e9843399e288effd1896f4dc28c8014dea24`; stderr is empty @ `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; exit `0` @ `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`. The independent sidecar is retained at `.../reviewer-timeout-driver-final-20261010-r1/independent-wrapper-case/timeout-calibration.json` @ `1c5be505c9c7ec7f901a0a2bfeefb91f2a509aaebe34b5b75b21f24eb2dc8e6d`.

This establishes the timeout-driver mechanism and its failed-evidence behavior only. No package/build/install wave, selected Q2 suite, worker provisioning, source transport, or Git operation was run. The driver and harness remain raw local inputs; this review makes no immutable-source, installed-consumer, Q2-closeout, or formal G acceptance claim.
