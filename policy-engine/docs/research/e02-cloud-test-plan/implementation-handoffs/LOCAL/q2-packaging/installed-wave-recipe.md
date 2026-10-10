# Q2 frozen installed wave

This runner is prepared but has not been executed. It proves the three actual consumer paths from one frozen, committed `policy-engine` tree:

1. source wheel;
2. wheel rebuilt from the source distribution after unpacking;
3. wheel rebuilt from the GCP package archive after unpacking.

The final SHA and tree are not known here. The manifest records `077a572ff5880b3f50a85d3e3db6a232d277659a` as the candidate baseline for the 11 asset byte digests; that baseline is not a freeze parameter and need not equal the branch's current `HEAD`. The caller must pass the final full commit and tree values supplied after source freeze. The runner rejects a detached checkout, a mismatched `HEAD`/tree, or any tracked working-tree edits before it allocates run output.

## Launch after source freeze

Run on the supported Linux build/consumer worker with its existing locked Python 3.12 DoWhy 0.14 interpreter. Set the absolute interpreter paths to the worker's real environments. The Python 3.14 app environment must already contain Hatchling 1.27.0, pytest, and the locked project test dependencies; the runner does not install into or mutate it.

```sh
repo=/absolute/path/to/polisyos
source_sha=ACTUAL_FULL_FROZEN_COMMIT_SHA
source_tree=ACTUAL_FULL_FROZEN_TREE_SHA
cd "$repo"
python3 "$repo/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/run.py" \
  --repo "$repo" \
  --source-sha "$source_sha" \
  --source-tree "$source_tree" \
  --app-python "$repo/policy-engine/.venv/bin/python" \
  --worker-python /absolute/path/to/existing/dowhy-014/.venv/bin/python
```

The two freeze variables must be filled from final-freeze evidence, not inferred from the candidate. If no existing worker interpreter is available, omit `--worker-python` only on Linux: the runner creates one retained environment from the frozen `workers/dowhy-014/uv.lock`, tries `uv sync --locked --offline` first, then retains that failure and makes a locked online fallback. It never skips the worker tests because provisioning failed.

## Exact artifact chain and checks

The runner executes these steps sequentially, with complete stdout/stderr and command records under the new ignored `LOCAL/q2-packaging/raw/runs/<freeze>-<UTC>-pid<PID>/` directory. It creates one small build-tools venv from the app Python's base interpreter and reuses it for the three builds. Its `sitecustomize.py` appends the already-provisioned app dependency site via `sys.path.append`; no `.pth` from that editable app site is processed. It creates a second, empty Python 3.14 consumer venv and reuses that for the three installs.

```text
git archive <full-frozen-sha> -- policy-engine
uv build --offline --no-build-isolation --python <build-tools-python> --wheel --sdist --out-dir <run>/dist-source
uv build --offline --no-build-isolation --python <build-tools-python> --wheel --out-dir <run>/dist-sdist
OUT_DIR=<run>/gcp-archive UPLOAD=0 PYTHON_BIN=<build-tools-python> bash <frozen-product>/ops/cloud/gcp/package_repo.sh
uv build --offline --no-build-isolation --python <build-tools-python> --wheel --out-dir <run>/dist-gcp
uv pip install --offline --reinstall --no-deps --python <one-installed-env-python> <each-wheel-in-sequence>
<one-installed-env-python> -I -m pytest <explicit-Q2-and-installed-consumer-selectors>
```

The `git archive` stream is hashed and extracted directly; it is not retained as a second full source tar. The source distribution and GCP archive are retained, unpacked, and rebuilt independently. Unchanged files in those extracted trees are hard-linked to the single frozen source snapshot; only changed/generated archive members are materialized separately. Each install uses `--reinstall`; all 11 declared `hatch.toml` force-includes are checked in the source, sdist, GCP archive, all three wheels, and installed site-packages.

`hatch.toml` remains the configuration source of truth. The runner compares its complete force-include mapping with the reviewed 11-row manifest, checks the source-sdist includes every such source, verifies the exact three GCP-selected sibling families (`data/dataset_catalog/`, `architecture/production_quality/`, `workers/dowhy-014/`), and refuses undeclared profile target files. If any frozen asset bytes/mapping changed after the candidate baseline, it stops before building and requires reconciling the manifest.

Dependency injection is deliberately isolated: interpreter metadata checks use `-S`; there is no `PYTHONPATH`; both temporary venvs reject `.pth` files. Their `sitecustomize.py` files append the pre-existing app dependency site with `sys.path.append` only and never call `site.addsitedir`, so the app venv's editable `.pth` file is not executed. Python consumers launch with `-I`; pytest uses `--import-mode=importlib` and `--confcutdir <frozen-product>/tests/unit`. The cutoff excludes the root `tests/conftest.py`, which unconditionally inserts the product `src` and `tests` paths, while retaining nested unit conftests needed for fixtures. A pytest plugin writes the complete collected node IDs and verifies after execution that neither the frozen nor live product root entered `sys.path` and every loaded `polisyos` or `tools` module resolves under the installed prefix. A separate isolated installed probe checks all 11 installed asset digests and calls the digest-domain registry loader through the packaged default path.

The consumer invocation also uses pytest `-s`. `run_command` streams pytest's complete process stdout and stderr into separate `consumer-suite.stdout.txt` and `consumer-suite.stderr.txt` files, including output that selected passing tests print from their fresh installed-reader subprocesses. The consumer receipt records both paths, byte counts, and SHA-256 digests. JUnit remains the structural record of selected/executed node IDs and outcome counts; it does not duplicate captured output. Nonzero pytest exits still retain both stream files before the runner reports failure. If a caller supplies a timeout, `run_command` records the command as timed out and retains the partial stream files before raising. The consumer timeout remains unset until its wall time is measured.

## Required consumers and selector set

For each of the three installed wheel profiles, the runner replays the exact 91 original Q2 node IDs from the tracked `wheel-junit.xml.gz` baseline. The baseline gzip SHA-256 is pinned in the manifest; the runner checks the complete original ID set is still collected and actually executed. The original suite is all tests in these five source files:

- `tests/unit/scientist/methods/causal/test_graph_intake_current_content.py`
- `tests/unit/scientist/methods/causal/test_reconcile_causal_graph_node.py`
- `tests/unit/scientist/nodes/builtins/causal/test_reconcile_causal_graph.py`
- `tests/unit/foundry/methods/catalog/causal/test_graph_reconciliation.py`
- `docs/research/e02-cloud-test-plan/implementation-handoffs/F/installed-default-resource-final-20261007/test_installed_catalog_defaults.py`

The run adds nine explicitly selected installed consumers. It must collect and execute exactly the 91 frozen Q2 IDs plus these nine unparameterized selectors, for 100 selected node IDs per wheel profile. The runner reconciles this against actual collection and JUnit IDs; the planned count alone is not evidence.

- `tests/unit/foundry/methods/test_dependency_profile.py`: `test_runtime_cutoff_predicate_is_one_sided_and_cutoff_specific`, `test_novel_profile_resolves_from_toml_without_code_change`, `test_cross_object_admission_or_reconciliation_mismatch_is_schema_invalid`, `test_unknown_authority_dto_field_fails_strict_parse`, `test_canonical_store_blob_manifest_or_signature_corruption_fails_before_parse`, and `test_missing_unreadable_or_corrupt_digest_registry_returns_source_not_established`.
- `tests/unit/foundry/methods/catalog/causal/test_installed_worker_profile.py`: `test_public_canonical_helpers_and_pure_report_factory_identity`, `test_real_installed_method_job_factory_and_fresh_reader_with_asset_removal`, and `test_installed_true_gcm_job_and_scientist_source_bound_interval_consumer`. The wrapper's transitive fixture modules are bound explicitly in the manifest and the actual callback source is checked before building.
- The worker wrapper resolves `dowhy` to `tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py` for its `dgp` and `admit` helpers, and `gcm` to `tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py` for `test_actual_gcm_job_persisted_fresh_reader_and_scientist_consumer`. The GCM test persists the fitted model, reopens it in a fresh Python 3.14 reader, and runs the Scientist causal-query consumer with a source-bound estimator interval.

The explicit TOML used by the novel-profile test is a test fixture read from the frozen source tree; it is not claimed as a packaged default. The digest-domain TOML, by contrast, is checked as an installed default by its exact package target, byte digest, selected runtime path, and decoder invocation. The profile tests include valid declarations, schema/cross-object rejection, strict unknown-field rejection, CAS corruption controls, and a fail-closed corrupt-registry case. Despite its name, the selected `test_missing_unreadable_or_corrupt_digest_registry_returns_source_not_established` body exercises malformed TOML only; missing and unreadable path cases are not covered by this selected set.

Before the first wheel build, a source-driven AST preflight resolves every selected test node ID to its function body, follows local helper calls, discovers dynamic fixture-module loaders, verifies the manifest's exact kind-to-file binding, and confirms every wrapper callback exists with a compatible call signature in that file. A changed selector, unbound fixture kind, missing file, or missing callback fails before building. The run is green only when actual collection and JUnit each contain exactly the 91 original IDs plus the nine declared selector IDs, all execute with zero skips/failures/errors, each profile has all 11 expected installed asset bytes, GCP selected sibling sets contain no undeclared files, and installed module origins/sys.path checks pass. Any pytest skip is an explicit failure, not an unsupported-profile waiver.

## Scope and scratch

This is one Linux platform, CPython 3.14 application wheel, and the separately locked CPython 3.12 / DoWhy 0.14 worker. It does not claim other Python versions, operating systems, architectures, accelerators, full backend/CI parity, production data, remote services, or EconML. No GPU, full-suite, browser, or production-data tests run. The only selected compute-heavy consumer is the installed GCM/source-bound scientist bridge test in the list above. Unsupported profiles are recorded here as out of scope; a setup failure for the selected profiles is a failed run.

Prior frozen source snapshot evidence measured 555,792,112 source bytes, a 121,945,591-byte sdist, 15,146,001-byte source wheel, and a 15,146,001-byte rebuilt-sdist wheel. With one retained source snapshot, hard-linked extracted payloads, three wheels, one installed app venv, the GCP archive, logs, and metadata, reserve approximately 1.5 GiB scratch when supplying the existing worker environment. This estimate excludes shared uv cache and excludes creating a new worker environment. GCP archive size and platform build overhead were not measured in this preparation turn; the runner records them at execution. It does not delete or overwrite any artifact, and each invocation uses a new run directory.

## Preparation status

The preparation author wrote this recipe, its manifest, and the ignored runner only. The Q2 package wave has not been executed; no archive, build, package install, worker provisioning, selected Q2 test, or cleanup command has been run. Pre-freeze verification was limited to static syntax/AST binding checks and the ignored synthetic stdout/stderr retention probe (passing, failing, and caller-timeout subprocess cases); its full outputs and hashes are retained at `LOCAL/q2-packaging/raw/capture-retention-probe-20261009-r2/probe-receipt.json`.
