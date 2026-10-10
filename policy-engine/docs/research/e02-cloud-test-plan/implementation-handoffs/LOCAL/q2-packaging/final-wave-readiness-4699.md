# Q2 final installed-wave readiness (candidate 4699)

Status: inspection only. No source build, archive build, install, selected pytest wave, cleanup, or Git mutation was performed. The current worktree is at candidate `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a` / tree `741784521d909f775d50863a29deec63cde300cd`, with broad tracked WIP. These are not final-freeze inputs. The wave must wait for root’s final committed SHA/tree and a clean tracked checkout.

## Frozen execution inputs

Current SHA-256 values:

- `raw/run.py`: `5d54bce877979e82e3a7f95d451b6f076fcc318037868e329f26908065d80932`
- `installed-wave-manifest.json`: `ab7cf774e1c6805e9b1812472e5b8357af1a6a43d50a994a7488f29442d06eb7`
- `installed-wave-recipe.md`: `e496a95d395d860747ba8a457630551040c32a8442be1de12af975fd4d86410e`
- `raw/timeout_driver.py`: `eaa9c3f2355b05e2f55753da4ba297ca6f137a9ba7f4699e456d4ad872339a0a`
- `raw/test_timeout_driver.py`: `ec3ecbba552cbe803f6fd51264fd239edc3b91f37b0aae5b4ac50a21df14eb44`
- `timeout-plan.md`: `1b07143e3ed5165aaf10740c5c57edeedc5cd3f4d0fb726d7121201cfdfc2af3`

The older `raw/installed-runner-static-preflight.json` is stale: it describes source `68b8ac5c32e03309ad888cb3799ad1c574fbdca7`, old runner `97405e…`, old manifest `439583…`, and old recipe `a0fac2…`. Do not cite its green result as current. The current runner itself recomputes the exact original IDs and transitive fixture/callback bindings from the frozen source tree before the first build; the final receipt binds actual runner and manifest hashes.

The current manifest’s candidate asset baseline is still internally consistent with the current `hatch.toml`: 11 unique force-include sources/targets, exact map equality, and all 11 present source byte counts/digests match. The declared asset payload totals 321,740 bytes. This is a pre-freeze observation only; the runner repeats the check against `git archive <final-sha>` and stops before building if any mapping or asset bytes drift.

## Planned serialized invocation and artifact chain

After freeze and independent input review, run exactly one serial invocation on the supported Linux worker, using its existing app CPython 3.14 environment (Hatchling 1.27.0 and locked test dependencies) and existing worker CPython 3.12 / DoWhy 0.14 environment. The runner records the actual `uv --version`; it does not silently substitute the documented version. Pass `--worker-python` to avoid provisioning another worker environment. No `PYTHONPATH` is used.

```sh
repo=/absolute/path/to/polisyos
freeze_sha=ACTUAL_FULL_FINAL_COMMIT_SHA
freeze_tree=ACTUAL_FULL_FINAL_TREE_SHA
app_python=/absolute/path/to/existing-app-3.14/.venv/bin/python
worker_python=/absolute/path/to/existing-dowhy-014-3.12/.venv/bin/python
python3 "$repo/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/timeout_driver.py" \
  --repo "$repo" \
  --source-sha "$freeze_sha" \
  --source-tree "$freeze_tree" \
  --app-python "$app_python" \
  --worker-python "$worker_python" \
  --output-root "/scratch/e02-q2-runs/$freeze_sha"
```

Use `timeout_driver.py`, not direct `run.py`, for the final wave: it pins the exact runner and manifest SHA above, wraps only `consumer-suite` calls, and calibrates timeout for profile 2/3 as `ceil(2 × preceding-profile wall seconds)` only after the preceding receipt reconciles exactly 100 collected IDs to JUnit, all pass with zero skips/errors/failures, installed origins verify, and stdout/stderr hashes reconcile. Profile 1 has no arbitrary timeout. This is per-profile consumer subprocess wall time, not build/install time. The run still calls the same runner CLI and commands.

The runner’s exact sequential chain is:

1. Validate final full commit/tree, attached branch, and no tracked changes; stream/hash/extract `git archive <sha> -- policy-engine` to one frozen source snapshot.
2. From that snapshot, build source wheel + sdist with `uv build --offline --no-build-isolation --python <single build-tools Python 3.14> --wheel --sdist`; byte-check all 11 wheel/sdist assets.
3. Unpack the sdist, rebuild a wheel from that extracted product with the same build tools, and byte-check all 11 assets.
4. Run `OUT_DIR=<run>/gcp-archive UPLOAD=0 PYTHON_BIN=<build-tools Python> bash <frozen-product>/ops/cloud/gcp/package_repo.sh`; check archive asset bytes and exact selected sibling sets, unpack the archive, rebuild its wheel, and byte-check all 11 assets.
5. Create one clean consumer Python 3.14 venv, then serially `uv pip install --offline --reinstall --no-deps --python <consumer-python>` each of the three wheels into that same venv. For each installation, run isolated installed-origin/resource proof and the selected consumers before installing the next wheel.

The installed proof reads all 11 files from the installed `purelib`, compares bytes and SHA-256, imports packaged resource modules and the digest authority module from that prefix, asserts its default digest-registry path is the packaged TOML target, and calls `load_digest_domain_registry` to establish a nonempty registry. The consumer tests then exercise default catalog reads, schema/corruption boundaries, and installed bridge/worker behavior; archive exit alone is not counted as consumer evidence.

The timeout driver retains the run receipt, build/archive outputs, per-command complete stdout/stderr/command JSON, per-profile complete pytest stdout/stderr, collected IDs, JUnit, origin proof, and timeout calibration. Its sidecar binds command record and both streams by path, bytes, and SHA, including terminal failure/timeout. The runner intentionally has no cleanup path. The sdist/GCP extracted payload hard-links unchanged files to the single frozen snapshot; it does not intentionally create extra complete source copies. Recheck shared-volume bytes/inodes and record the present transport footprint before admission; the last capacity plan is historical and the GCP/archive/log/temp upper bound remains unmeasured.

## Selected-property coverage and limits

Each profile must execute exactly 100 nodes: the 91 frozen original Q2 baseline IDs plus nine explicitly selected consumers. The original 91 occur as follows (all unique, exact set reconstructed from the tracked compressed JUnit baseline with SHA `3b04c39f4038726d08759384d6690409f8b33f6b6b12e5afc584453d63510dc9`):

- 38 `tests/unit/scientist/methods/causal/test_graph_intake_current_content.py` cases
- 9 `tests/unit/scientist/methods/causal/test_reconcile_causal_graph_node.py` cases
- 8 `tests/unit/scientist/nodes/builtins/causal/test_reconcile_causal_graph.py` cases
- 24 `tests/unit/foundry/methods/catalog/causal/test_graph_reconciliation.py` cases
- 12 `docs/research/e02-cloud-test-plan/implementation-handoffs/F/installed-default-resource-final-20261007/test_installed_catalog_defaults.py` cases

The nine additions are six exact `test_dependency_profile.py` selectors (one-sided cutoff boundary; novel TOML profile; cross-object schema mismatch; strict unknown DTO field; canonical CAS/manifest/signature corruption; malformed digest registry fail-closed) and three `test_installed_worker_profile.py` selectors (canonical helper/factory identity; real MethodJob + fresh reader + removed worker asset; actual GCM persisted job + Scientist source-bound interval reader). The wrapper’s `dowhy` and `gcm` callback modules are source-bound and the runner verifies their exact callback names/call signatures before builds.

There is a deliberate distinction between packaged-default and fixture profile behavior: `test_novel_profile_resolves_from_toml_without_code_change` reads test TOML from the frozen source tree, not a packaged default. Positive packaged-default evidence for the digest-domain TOML is instead the installed proof’s exact target/hash/default-path/load call. The selected test named `test_missing_unreadable_or_corrupt_digest_registry_returns_source_not_established` only writes malformed TOML; the selected set does not directly establish missing-file or unreadable-file behavior for that registry. Do not describe those two cases as tested.

The 100-node set is a targeted Q2 installed-resource/causal-worker consumer wave, not coverage for every changed source/test in the broad current branch. One concrete current changed behavior outside it is `test_tenant_boundary_metric_records_only_verified_mismatches` in `tests/unit/runtime/http/test_runtime_authorization_access_audit.py` (SHA `62f252eabf490f7d13f11bd9e5c85addf451b246bebbf2d9450451b788a096ff`); neither its path nor selector is in the current manifest. That test imports concrete sibling test modules at module scope, unlike the source-bound fixture wrapper used by this wave, so it cannot safely be added as a raw selector under the runner’s isolated import/origin contract without a separately reviewed installed-consumer wrapper. No selector or source code was changed in this readiness inspection. The final Q2 receipt should not be presented as verifying the newer runtime authorization metric, Scholar/Core DTO/Grant, or broader Ruff-root changes; their focused source checks remain separate evidence.

## Admission state

Not ready to launch yet: current HEAD is a dirty candidate, not the final commit/tree; older static-preflight receipt is stale; root still needs final input freeze/review and current Linux capacity receipt. The reviewed runner/manifest/timeout-driver hashes above match the driver’s pinned runner/manifest constants. No package, install, worker provisioning, selected consumer, or cleanup command was issued in this turn.
