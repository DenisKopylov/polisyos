# Independent review: composed Mac capture harness

## Result and P40 buckets

The harness has useful fail-closed preflight, output retention, and queue-stop behavior, but I do not recommend running the 19-command product queue yet. The assigned source freeze is not available: the plan leaves `source_scope.final_commit` and `source_scope.final_tree` null, and the candidate worktree is dirty. I ran only the wrapper’s explicitly harmless `--self-test`; no product test, test collection, native fit, or production-data read was run.

| Finding | P40 bucket | Assessment |
|---|---|---|
| Runtime source/tool identity is checked only before the queue. The ignored pytest origin plugin is not hashed or bound to the run at all. | **SAME class, deeper**: source/executable provenance | The runner checks attached HEAD, the full tree, cleanliness, and its scoped file manifest once, then executes all selected commands from the live worktree. It does not repeat those checks inside the loop. It records the wrapper SHA, but not the plugin SHA. If a tracked source/test or the ignored plugin changes after preflight, later commands still carry the old frozen commit/tree in their receipts. Widen the identity mechanism to include all code enforcing capture (wrapper and plugin) and keep each command bound to the source identity it actually runs, or enforce and attest an immutable execution snapshot. Do not add separate one-off hash checks for individual files. |
| Every JUnit skip becomes `UNRUN_REQUIRED_SKIP`. | **NEW class**: skip-reason/status discrimination | This is conservative—no skip can be reported PASS—and each JUnit case retains its ID, message, and text. It nevertheless does not distinguish a required-gate skip from an unavailable optional backend. The selected files include different skip causes such as missing BoTorch, FastAPI, `orjson`, and OpenTelemetry. Emit distinct non-PASS statuses from an explicit per-case/route policy, or label skips unclassified and require review of the retained reasons. |
| The R4 fixture writes six child stdout/stderr files, but their existence and SHA-256 are absent from the command receipt. | **NEW class**: child-output receipt completeness | The preflight checks those names are absent and the fixture writes full streams before its outer assertions. The runner hashes only the parent command stdout/stderr and JUnit. The R4 receipt directory is recoverable from the environment override, but there is no post-run child-file inventory or digest. Record each child path, size, and digest (or an explicit missing-file reason) before classifying the outer test. |

The source-identity finding is the second level of the same property: an initial clean-tree check does not bind worktree bytes throughout a long serial run, and the ignored module-origin plugin itself is outside that check. Treat it as one identity-boundary repair, not a sequence of per-path patches. The skip and child-output findings concern separate result/proof properties.

## Exact candidate and review inputs

Candidate worktree: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`; product root: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`.

At review time, the attached branch was `codex/e02-unified-local-20261009`, HEAD `58ab0ac58c4c3901e518e344fcccef85d22639bb`, tree `227722f77f441e09c1d07112b972d4988e9aa691`. `git status --porcelain=v1 -z --untracked-files=all` returned 801 records (4 tracked modifications and 797 untracked paths), including declared peer work. This is a pre-freeze state; I did not change, stage, or clean any of it.

Current SHA-256 values:

- `LOCAL/raw/composed_mac_capture.py`: `c2fb16b4b0fdb871656ae32302b0afb4e5932e2a5b0a82a33966b203e0a27347`
- `LOCAL/raw/composed_mac_pytest_origin_plugin.py`: `b1920931f4a31ef2561874e0f076f4683e45462123290a26afaab26f862f9298`
- `LOCAL/r4-workload/composed-mac-current-source-replay-plan-20261010.json`: `48512a6a40a43a3d6c4d2723b2cb6ecde34d6725251ab03187ebd69b0b9e430a`
- `integration/composed-mac-current-source-replay-plan-2026-10-10.md`: `46e0dbe10158a8c060930a8af3ca4da6fc9763b9e60b8077052742a7cef787a0`

The plan describes 19 ordered commands: one canonical-module readback and 18 pytest commands, 111 argv test targets across 62 test files, plus 71 source/config/register/criterion paths. All six numerical thread environment variables are explicitly set to `1` for each command; xdist is false, pytest worker count is one, and concurrency is serial. Each pytest command has a separate JUnit/stdout/stderr/metadata path. The configured output root did not exist at inspection time, and none of the planned output or R4 child-stream paths existed. The plan reports no current composed wall-time measurements and intentionally adds no suite timeout.

## Positive properties verified in code

- Freeze preflight requires attached HEAD to match the supplied commit, the commit tree to match the supplied tree, Git cleanliness except the ignored harness/plugin and output root, and byte equality for its declared 71 source inputs, 62 test files, plan JSON, and plan Markdown. The manifest honestly labels itself “scoped direct inputs, not a transitive import closure”; the full commit/tree check also binds tracked conftests and other tracked repository content.
- Every output path is constrained under the dated raw output root. Planned command directories, output files, cache paths, pytest basetemps, and the six known R4 child-stream names are checked for collisions before execution. Output files use exclusive creation; JSON receipts are created without replacement. The only unlink is the harness’s own temporary file after atomic receipt linking.
- The wrapper preserves the planned argv except for adding a unique `--basetemp` after the `pytest` token. It records planned and actual argv, environment overrides, command timing, exit code, sampled RSS, JUnit case records, stdout/stderr/JUnit hashes, and a metadata hash in the append-only event/history records. Output streams are drained separately, written in binary, flushed during capture, and fsynced on process completion.
- JUnit parsing keeps every case’s derived `classname::name`, status, time, skip/failure/error message, and text. Nonzero exits, JUnit errors/failures, skips, empty JUnit, and missing/out-of-root module-origin receipts cannot become PASS. The queue stops on the first non-PASS/non-preflight-pass result and records the remaining selected commands as UNRUN.
- The pytest hook checks every loaded `polisyos.*` and `tools.*` module origin, requires the parent process receipt, and rejects origins outside the product source/tool roots. It writes a unique PID receipt rather than replacing an existing one.

## Lightweight verification performed

Command: `python3 docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed_mac_capture.py --self-test` from the product root.

Result: PASS. It exercised separate stdout/stderr capture, SHA-256 calculation, parsing a synthetic JUnit document with one PASS and one SKIP, the module-origin positive/negative cases, and the PID hook receipt. Receipt: `LOCAL/raw/composed-mac-wrapper-selftest-0b7ba88ee8414f978ece167c74922cdb/selftest-receipt.json`, SHA-256 `4f107b8fa72a26932b6ecc29241cb463d9c3352d74894c6419abcb8ee7d89f78`. Captured stream hashes were stdout `daf039ac66c26bdba48cc7733b0941297423050543b0d4a860b26c417bb48f95` and stderr `b97481fa195870bcd6e13ce3ab645a38c6823faafa29fb5674b2af6d8fb9b8d1`; the hook receipt hash was `b7d4494c72f3c6d78cc2135f5e5ca4621305671de4c7c208402e1bb98973e377`.

This self-test validates capture primitives only; it does not prove pytest collection, real loaded-module origins, or any of the planned product behaviors. The final queue must be reviewed against a newly supplied freeze commit/tree and fresh hashes after source freeze. This review is independent code assessment only; it grants no G acceptance or formal finding closure.
