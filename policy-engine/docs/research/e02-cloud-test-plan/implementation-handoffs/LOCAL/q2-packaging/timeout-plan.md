# Q2 profile timeout and capacity plan

Status: preparation only. No package wave, build, selected Q2 test, source transport, worker command, or Git command was run for this note. The source freeze is still pending; the parent supplied candidate prefix `9e02a9f49...` as context, not as an execution identity. A separately hashed timeout driver is prepared and its lightweight synthetic harness passed; the driver still requires independent review before it becomes a wave input.

The reviewed local Q2 inputs inspected here are:

| Input | SHA-256 |
| --- | --- |
| `raw/run.py` | `5d54bce877979e82e3a7f95d451b6f076fcc318037868e329f26908065d80932` |
| `installed-wave-manifest.json` | `ab7cf774e1c6805e9b1812472e5b8357af1a6a43d50a994a7488f29442d06eb7` |
| `installed-wave-recipe.md` | `e496a95d395d860747ba8a457630551040c32a8442be1de12af975fd4d86410e` |
| `raw/timeout_driver.py` (prepared; independent review pending) | `eaa9c3f2355b05e2f55753da4ba297ca6f137a9ba7f4699e456d4ad872339a0a` |

## Timeout mechanism

The runner already has the low-level hook needed to retain a timed-out command: `run_command(..., stream_output=True, timeout_seconds=...)` streams both child descriptors to separate files, writes a command receipt, and raises only after retaining partial output. The pytest invocation uses `stream_output=True`. However, `run_wave` currently passes no timeout to any consumer profile, and the CLI has no timeout option. Its profiles execute in this order in one invocation: `source-wheel`, `rebuilt-sdist-wheel`, `rebuilt-gcp-archive-wheel`. All three wheels are built before the consumer loop.

Use the prepared small, separately hashed driver only after independent review and final freeze, leaving the reviewed runner and manifest unchanged. Before import, it hashes and checks both exact reviewed inputs; it then imports the runner as a module, wraps its existing `run_command` function in memory, and calls the existing `parse_args()` and `run_wave()`. The normal runner command-line arguments stay unchanged. The driver intercepts only calls whose log stem is `consumer-suite`; every build, install, and preflight command goes through the original `run_command` behavior.

For every terminal `consumer-suite` command outcome, including successful exit, nonzero return, exception, and timeout, the driver captures the existing command-record path, byte count, and SHA-256 together with the stdout/stderr paths, byte counts, and SHA-256. It checks path type before opening, uses nonblocking/no-follow flags, verifies a regular-file descriptor before reading, hashes only the captured size, and detects metadata drift. Symlinks, FIFOs, sockets, directories, and devices are explicit unavailable `not_regular_file` evidence; a missing file has `file_missing`. Unavailable evidence cannot authorize a later timeout. The sidecar binds all terminal outcomes; its reader re-hashes the exact files and rejects changed command records or streams. An incomplete capture still writes a failed sidecar with the unavailable reason.

The driver applies this sequential policy:

1. Run the first actual Linux consumer profile with `timeout_seconds=None`. Measure only the `consumer-suite` subprocess wall time with a monotonic clock; do not include packaging, installation, or environment setup in the consumer duration.
2. Before timing out the second profile, read the run receipt written by the runner for `source-wheel`. Derive the complete expected ID set from the frozen original baseline plus the nine selectors in the manifest, then require exact equality in both the runner's collected-node-ID JSON and JUnit. Also require exactly 100 executed cases, return code zero, zero skips/failures/errors, verified installed-origin proof, and retained stdout/stderr whose byte counts and SHA-256 values match the runner receipt. If any check fails, the runner stops before the next profile and no timeout is calibrated from a bad measurement.
3. Set the second profile's timeout to `ceil(2 × T1)` seconds, where `T1` is the measured first-profile wall time. Retain its exact start/end duration and the derived value.
4. Before the third profile, require the `rebuilt-sdist-wheel` receipt to pass the same exact collection/JUnit set, execution, origin, and full-stream reconciliation. Set the third profile's timeout to `ceil(2 × T2)` seconds, using the measured second-profile time.
5. Record the driver hash, source/runner/manifest identities, each profile's measured seconds and timeout, previous-profile validation, outcome, and existing receipt/log paths in `timeout-calibration.json` under the unique run directory. Do not copy stdout/stderr into the sidecar; the runner already retains the complete files and hashes. The driver rechecks its own hash and both pinned input hashes before writing this sidecar.

The first profile has no arbitrary timeout. A timeout on either later profile is derived only from the immediately preceding successfully completed and independently reconciled 100-test profile. The frozen source, runner, manifest, and build inputs remain constant throughout the wave; the existing installed consumer environment is intentionally reinstalled sequentially by the runner. The driver is an execution input and must receive independent review with this exact hash before the heavy slot. It is not part of the product source or archived package. A future runner-native option would require a reviewed runner delta and a new runner hash; no such change is proposed here.

After freeze and review, the invocation changes only its executable from the reviewed runner to the separately hashed driver, while preserving the existing six arguments:

```sh
python3 "$repo/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/timeout_driver.py" \
  --repo /workspace/polisyos \
  --source-sha "$freeze_sha" \
  --source-tree "$freeze_tree" \
  --app-python /scratch/root-venv/bin/python \
  --worker-python /scratch/dowhy-venv/bin/python \
  --output-root "/scratch/e02-q2-runs/$freeze_sha"
```

The driver must run from its prepared location beside `raw/run.py`, resolve and hash that exact reviewed runner and the sibling manifest before import, pass through all six existing arguments (including optional `--output-root`) unchanged, and never mutate them. Keep the Q2 handoff directory layout intact in the worker checkout: the driver locates `run.py` beside itself and the manifest in the parent handoff directory. The separate sidecar binds its own hash and calibration observations to the run directory. The run receipt continues to bind the runner and manifest hashes. The current `run_command` timeout path already preserves partial stdout/stderr on later-profile timeout; the real subprocess-timeout evidence and verification results are retained in `raw/timeout_driver_delta_receipt_20261010.json`.

## Shared-volume capacity

The latest retained Linux capacity receipt reports a 7.8-GiB Colima data volume with 4.2 GiB used and 3.3 GiB available by `df` (3.2 GiB by `findmnt` rounding), plus 432,557 free inodes. `/scratch` and Docker's `/var/lib/docker` share that volume. The VM root's 18 GiB free is separate and cannot be added to the data-volume budget. These are prior measurements; recheck immediately before any admitted heavy run.

The three-profile runner reuses one existing app environment and the supplied existing DoWhy worker, creates one build-tools environment and one consumer environment, and installs each wheel into that same consumer environment. It retains one run directory and all three built wheels, the source distribution, GCP archive, logs, reports, and per-profile pytest temp directories. The sdist and GCP extracted trees hard-link payload files back to the one frozen source snapshot when bytes and modes match; they do not intentionally make a second full payload copy. The GCP archive is built from `src`, `tools`, `schemas`, `ops`, and the 11 force-includes, then retained while its extracted tree and rebuilt wheel are produced.

Prior measured artifact sizes are 555,792,112 bytes for the source snapshot, 121,945,591 bytes for the source distribution, and 15,146,001 bytes for each of the source and rebuilt-sdist wheels. The current scratch estimate is about 1.5 GiB with the existing worker supplied, but it is not a cap: the GCP archive size, rebuilt-GCP wheel size, build-environment footprint, future pytest log/temp growth, and the copied bare repository pack are not measured. The attached checkout is described as roughly 530 MiB and is also not included in that run-scratch estimate.

Using the rounded values only, the 1.5-GiB run estimate plus the roughly 0.52-GiB checkout leaves about 1.18 GiB against the conservative 3.2-GiB `findmnt` availability, before the bare pack and any estimate overrun. That remainder is a sensitivity calculation, not proof of fit: the estimate already includes an unmeasured GCP archive and is not an upper bound. The bare pack's size is unknown. The runner retains artifacts instead of deleting earlier profiles, so the retained-artifact floor grows cumulatively through completion. Hard-linking limits extracted-tree duplication but does not bound the compressed archive, wheel/build outputs, new environment files, pytest logs, or inodes; a temporary `.q2-writing` member can also raise an intermediate peak. No defensible numeric peak can be asserted from the current receipts.

Before admission, remeasure the actual shared-volume free bytes and inodes after the one bare pack and attached checkout exist, and record their exact `du -sb` sizes. The runner does not emit run-directory storage high-water values. A separate read-only monitor must capture `/scratch` free bytes/inodes at admission and during the wave, plus the run directory's bytes at observed stage boundaries; that reports observed peak, not a pre-build upper bound for the unknown GCP archive. Pass the existing worker interpreter so no second worker environment is created. Keep the runner's single output root, one build-tools environment, and one sequential installed environment; do not create per-profile venvs or source copies. If the free-space budget cannot cover the measured transport footprint plus the retained-run estimate with an explicit reserve approved by root, hold the heavy slot and resolve capacity through an authorized storage change; do not infer fit from the host root or claim OOM from the memory snapshot.

The cgroup snapshot is not an OOM finding: its memory cap was 2,306,867,200 bytes, current usage 2,221,060,096 bytes, `memory.events` OOM counters were zero, and most reported use was file cache. This does not establish peak memory during package builds or GCM tests; refresh it before the heavy slot and report observed pressure separately from data-volume capacity.

## Preparation verification

The separately hashed harness `raw/test_timeout_driver.py` (SHA-256 `ec3ecbba552cbe803f6fd51264fd239edc3b91f37b0aae5b4ac50a21df14eb44`) ran eleven cases successfully. In addition to exact-set timeout calibration, sidecar evidence binding, actual timeout/nonzero children, same-path tamper rejection, and explicit missing-stream reasons, it checks a FIFO with no writer in a bounded subprocess, exercises the real wrapper's FIFO failure sidecar, rejects symlink/directory/socket/device file types uniformly, and verifies a changed regular-file control fails. The wrapper FIFO probe completed in 0.0018s and wrote a failed sidecar identifying `not_regular_file`; no fixture cleanup was performed. The command receipt retains complete harness stdout/stderr, and the test report indexes actual child paths/hashes. The FIFO delta receipt is `raw/timeout_driver_fifo_delta_receipt_20261010.json` (SHA-256 `9a7ece0601710a0611762b2bf3fd7d85a47e1394fc7a57a593703f2b51fbd5dc`).

This preparation did not execute the selected Q2 suite or any package build/install. The timeout driver and this execution plan are ready for independent composition review; input freeze and the serialized Linux wave remain pending. The synthetic harness is not evidence that the installed package consumers pass.
