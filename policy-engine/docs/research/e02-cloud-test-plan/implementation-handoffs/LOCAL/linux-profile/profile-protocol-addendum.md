# Python profile protocol addendum

Captured 2026-10-10 against the mutable candidate. This resolves the macOS `ruptures` check failure as a profile-selection problem for the current witnesses; it does not claim the source is frozen or that any tests passed. Everything below was read-only. No package was removed, installed, or imported from `ruptures`; no environment or source was changed.

## Cause and supported profile boundaries

The host `policy-engine/.venv` uses Python 3.14.3 and contains 249 distributions. Its exact `uv pip check` result is:

```text
Checked 249 packages
Found 1 incompatibility
The package `ruptures` requires Python >=3.9, <3.14, but `3.14.3` is installed
```

Installed metadata confirms `ruptures==1.1.10`, `Requires-Python=<3.14,>=3.9`. The root project requires `>=3.14,<3.15`, while its `analytics` optional extra alone declares `ruptures>=1.1.10` (alongside SciPy, Statsmodels, linearmodels, pandas, and arch). This makes the currently selected `analytics` distribution set inconsistent with Python 3.14. It does not make the root base, runtime HTTP, or test profile depend on `ruptures`.

The existing host `.venv` is a broad environment, not a clean rendering of the browser profile. A read-only `uv sync --locked --offline --dry-run` for the browser selection proposed 101 removals from it, including `ruptures`; the prior known Linux root profile selection proposed 91 removals. Neither plan was executed. Do not sync either profile into the existing host `.venv`: that would prune packages another task or user may rely on.

The selected browser/API profile is the root base plus `runtime-http`, `test`, and the `dev` dependency group. The base already pins the JAX CPU stack. `runtime-http` supplies FastAPI, Uvicorn, HTTPX, and PyJWT; `test` supplies pytest and the fixture test dependencies; `dev` is explicit so the environment matches `uv run`'s test-group behavior. None selects `analytics` or `ruptures`. The browser config itself calls `uv run --extra runtime-http --extra test`.

The existing Linux root environment is the appropriate profile for the Linux C7/LA-029 and Python 3.14 reader consumers: Python 3.14.0, `uv` 0.9.21, root `runtime + ml + dev` lock recipe, 161 packages, passing `uv pip check`, `lifelines==0.30.3`, and no `ruptures`. `test_c7_synthetic_full_pipeline.py` declares `lifelines` as its optional presence requirement. Its C7 advanced suite runs factor embeddings, clustering, bilevel, Heckman, survival, Sobol, and specification-curve adapters; it does not select the time-series change-point method. The only two `ruptures` imports in the inspected catalog module are function-local: `_detect_group_breaks` catches `ModuleNotFoundError` and has its own fallback; `ChangePointDetection.pure_step` imports `ruptures` directly, but it is outside this C7 composition. LA-029 has not been run here, so this is a source/profile assessment, not a test receipt.

The DoWhy worker remains its own existing Python 3.12.12 / DoWhy 0.14 environment: 52 packages, passing `uv pip check`, no `ruptures`, and `statsmodels==0.15.0` through DoWhy's dependency graph. It is the worker for B212/F, not a Python 3.12 substitute for the root PolicyOS application: the root project declares Python `>=3.14,<3.15`, and the worker project contains only DoWhy and pytest. B212/F and DFK do not justify installing the root `analytics` extra.

Thus the environmental finding buckets as: **the current core browser / LA-029 / B212-F profiles do not require `ruptures`; the root `analytics` extra is independently incompatible with the root's declared Python range.** Leave the latter bounded and unclaimed. Do not ignore `Requires-Python`, alter the analytics extra/guard, install an unpinned package, or route the root app through the standalone worker. Tests that invoke `ChangePointDetection.pure_step` need a separately supported root analytics runtime decision; that profile is not established by this investigation.

## One clean host browser environment, if root releases provisioning

The existing Linux root environment is already suitable for Linux witnesses but cannot serve the host browser's fixed API listener. The host `.venv` must remain intact. The one proposed host profile is a separate environment under the user's existing cache, built against the exact final source tree without copying that tree:

```sh
set -euo pipefail
frozen_policy_engine=/absolute/path/root-supplies-at-freeze/policy-engine
freeze_sha=ROOT_SUPPLIED_FULL_COMMIT_SHA
browser_venv="$HOME/.cache/polisyos/e02-browser-core-${freeze_sha}"

UV_CACHE_DIR="$HOME/.cache/uv" \
UV_PROJECT_ENVIRONMENT="$browser_venv" \
/opt/homebrew/bin/uv sync --project "$frozen_policy_engine" \
  --python 3.14.3 --locked --offline \
  --extra runtime-http --extra test --group dev --no-install-project

/opt/homebrew/bin/uv pip check --python "$browser_venv/bin/python"
"$browser_venv/bin/python" -c \
  'import sys, importlib.metadata as m; print(sys.version); print("fastapi="+m.version("fastapi"), "pytest="+m.version("pytest"))'
```

If the offline install reports a missing locked artifact, retry the same recipe against the same new path with only `--offline` removed. Keep `--locked`; that fallback fetches versions and hashes from the committed lock. `--no-install-project` avoids a source build; the fixture server inserts the source roots itself. During Playwright execution set `UV_PROJECT_ENVIRONMENT="$browser_venv" UV_NO_SYNC=1 UV_FROZEN=1` so the web-server child uses this exact environment without reconciling it. Retain the current fixture guards and port preflight from [`final-wave-readiness.md`](final-wave-readiness.md). This is one host venv for the existing source checkout, not another source tree or a replacement for the Linux root/worker profiles.

The dry-run resolved the locked browser dependency graph offline and, with an absent target path, reported “Would download 141 packages” / “Would install 148 packages”; it did not create the target. This proves lock/profile resolution only. A dry-run does not establish that all 141 download artifacts are already in the 498 MiB host uv cache. A real offline sync, after root releases provisioning, is the safe cache test; if it fails for an uncached locked wheel, use the locked network fallback above. The current host `.venv` is 2.0 GiB; the already-installed Linux root superset occupies about 1.1 GiB per the prior profile receipt. The exact Mac browser-profile footprint is **not measured**. Host free space was 19 GiB at the earlier snapshot, with a separately assigned host budget; remeasure before any install. The Linux worker data disk is a distinct 8 GiB allocation with 3.0 GiB free and is not the place to build this host venv.

Current tool versions differ by host: the Mac Homebrew `uv` measured `0.10.6`; Linux `uv` remains `0.9.21`. The locked Mac dry-run succeeded with 0.10.6 and `--locked`; no uv downgrade or package install was performed. Preserve 0.9.21 for the existing Linux recipe. Recheck the final source `pyproject.toml` and `uv.lock` hashes before installing the proposed host profile; current candidate hashes are in the raw receipt and are not a final freeze binding.

## Receipt

Full bounded command inputs and stdout/stderr/exit captures are in [`raw/profile-protocol-audit/`](raw/profile-protocol-audit/), including the host metadata check, Linux environment inventory, both no-write sync plans, and the fresh-target offline dry-run. `SHA256SUMS` verifies the receipts. The no-write fresh-target probe confirmed `/tmp/e02-browser-core-dryrun-20261010` remained absent. Two exploratory `uv export`/`uv tree` probes used unsupported flags and returned usage errors; they caused no mutations and are not used for these conclusions. The supported `uv sync --dry-run` probes are the profile-selection evidence.
