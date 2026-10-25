# Q2 frozen installed wave

This runner is prepared but has not been executed. It proves the three actual consumer paths from one frozen, committed `policy-engine` tree:

1. source wheel;
2. wheel rebuilt from the source distribution after unpacking;
3. wheel rebuilt from the GCP package archive after unpacking.

The final SHA and tree are not known here. The checked-in generated primary manifest is stale for the current source: it contains 11 resource rows while the current Hatch/runtime-owner inventory contains 12, including the nested OpenAPI resource. Its recorded baseline `077a572ff5880b3f50a85d3e3db6a232d277659a` is historical, not a freeze parameter. After the final source commit, regenerate primary and supplemental manifests from the source audit, preserve all 12 owner-derived resources, and require an exact `check`; never hand-edit generated rows. The caller must pass the final full commit/tree and exact manifest path plus SHA-256. The runner rejects a detached checkout, a mismatched `HEAD`/tree, or any tracked working-tree edits before it allocates run output.

## Exact schema-version admission

The source audit records the selected UV path, version, and binary hash. It requires the explicit `--uv-executable` path to resolve to the same `uv` found on the caller's `PATH`; venv recreation invokes the exact resolved Python executable bound by the selected launcher profile. The selected `pyvenv.cfg` bytes remain hash-bound; the recreated config may use a different `home` path spelling only when both paths resolve to the selected runtime executable's parent directory, which is contained beneath its isolated `base_prefix`, and UV version, Python implementation/version, system-site-packages setting, and project prompt must match exactly. Generated site artifacts still require exact byte and mode equality. This is a local recomputed creator observation (`creator_authenticity: not_established`), not a vendor signature.

The current primary and supplemental source-freeze manifests and the terminal command-evidence sidecar use schema version `1`. Each reader requires the JSON value to be an exact non-boolean integer before proceeding; `true`, `1.0`, `"1"`, `null`, and unsupported integer versions are refused. The source audit applies the same rule when it reads both manifest inputs. This is input validation, not a migration to a newer schema version.

## Source-bound manifest admission

Before a package build, run the source audit against the exact frozen commit. `prepare` recomputes source-selected IDs, resource bytes, and both manifest proposals from that source; it does not build, install, or accept a consumer. If the primary proposal differs from the committed `installed-wave-manifest.json`, review and commit the exact proposed primary bytes, calculate the new source SHA/tree, and repeat `prepare` using the last proposed supplemental file as its explicit input. After the primary manifest matches the proposal for the final source, run `check` against that same source SHA/tree and the newest proposed supplemental file. It must report `source_preflight_exact`, reconcile the source object and actual collection, bind the capsule inputs, and have no runner limitations before the installed wave begins. Use the exact latest proposed supplemental file and SHA for the final `check` and later supplemental run.

```sh
repo=/absolute/path/to/polisyos
source_sha=ACTUAL_FULL_FROZEN_COMMIT_SHA
source_tree=ACTUAL_FULL_FROZEN_TREE_SHA
app_python="$repo/policy-engine/.venv/bin/python"
audit="$repo/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/q2-freeze-input-audit-v2-20261011.py"
uv_executable="$(command -v uv)"
supplemental_manifest=/absolute/path/to/reviewed-versioned-supplemental-manifest.json
supplemental_manifest_sha256=ACTUAL_SUPPLEMENTAL_MANIFEST_SHA256
collection_timeout_seconds=MEASURED_COLLECTION_TIMEOUT_SECONDS
prepare_root="$repo/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/source-freezes/${source_sha}-$(date -u +%Y%m%dT%H%M%SZ)"
python3 "$audit" prepare \
  --repo "$repo" --source-sha "$source_sha" --source-tree "$source_tree" \
  --python "$app_python" --uv-executable "$uv_executable" \
  --collection-timeout-seconds "$collection_timeout_seconds" \
  --output-root "$prepare_root" \
  --supplemental-manifest "$supplemental_manifest" \
  --supplemental-manifest-sha256 "$supplemental_manifest_sha256"
```

After the final `prepare` for a source commit, point `supplemental_manifest` at that run's exact `proposed-supplemental-manifest.json`, hash it, and run `check` into a new absent output directory with the same source SHA/tree. The primary manifest is read from the source commit. If any source or manifest changes after `prepare`, recompute the source SHA/tree and repeat `prepare` before `check`.

Every count-bearing JSON field used to admit this source freeze or a consumer result must be an exact JSON integer (`type(value) is int`), not a boolean, equal-valued float, numeric string, negative value, or a mismatched integer. This applies to selected-node and resource counts, the original baseline denominator, supplemental counts, per-asset byte lengths, captured command/stream byte counts, and consumer receipt counts. The source-audit exact-status predicate and the installed runner independently apply the same rule; a count alias must make the audit stale/limited before any build.

The earlier 8070 readback is historical: its two stale-of-eleven resource rows, eight stale-of-fifteen primary test-module pins, and old supplemental test-source digest do not describe this current source composition. The current Hatch/runtime-owner inventory has 12 resources, including OpenAPI, while the checked-in manifest has 11. Keep the full primary/supplemental selectors and all 12 owner-derived resources. `prepare` must derive current proposals from the canonical test collection, `hatch.toml`, and runtime resource owner; review and apply complete proposals, then run `prepare` again and require an exact `check`. Do not edit counts or resource hashes by hand, and do not treat a matching selector count as source reconciliation.

Before final source freeze, run the source-owned build-tool helper tests in the locked app test environment. The source-audit `prepare`/`check` then binds the helper, external profile, and their tests, computes the current primary selector IDs and six supplemental selector IDs from actual collection, and derives the entire force-include mapping from `hatch.toml` and the canonical runtime resource owner. The retained 15-path/135-ID primary declaration and six-selector supplemental declaration are prior candidate values until that exact current-source check passes.

After committing the Q2 implementation and companion test, run the full focused Q2 unit module from `policy-engine/`. The module resolves the repository root from its own source path, so the command works from this product-root workdir without changing the runner's `--repo` contract. `audit.bind_audit_helper` deliberately compares source bytes to the current commit; do not stub it or use an uncommitted source delta. Give the harness a fresh authorized RAW output root and retain every artifact:

```sh
set -eu
repo=/absolute/path/to/polisyos
product="$repo/policy-engine"
run_parent="$product/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/q2-focused-unit-runs"
mkdir -p "$run_parent"
write_root="$(mktemp -d "$run_parent/q2-focused-unit.XXXXXXXX")"
mkdir "$write_root/tmp" "$write_root/pytest-temp" "$write_root/pytest-cache"
export TMPDIR="$write_root/tmp"
cd "$product"
"$product/.venv/bin/python" -B -m pytest -c "$product/pytest.ini" \
  -o "cache_dir=$write_root/pytest-cache" \
  --basetemp="$write_root/pytest-temp" \
  --benchmark-storage="file://$write_root/benchmarks" \
  --junitxml="$write_root/junit.xml" \
  docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/test_timeout_driver.py
```

When invoked directly as a script, the JSON harness report and all per-case captures stay beneath `TMPDIR`; under pytest, results are retained in JUnit/stdout while the same test-generated case directories, temporary fixtures, cache, and benchmark data stay under `write_root`. This unit replay is not a built-archive or installed-consumer receipt.

The 2026-10-15 run-contract JSON remains a historical, immutable input record. Its command/source digests predate this source delta and cannot authorize a later launch; after the reviewed source patch is applied and frozen, create a new complete run contract from the final source and current worker readback.

```sh
cd "$repo/policy-engine"
"$app_python" -B -m pytest -q tests/repo_quality/tools/test_q2_build_tool_wheel_lock.py
```

The source capsule includes the build-tools helper, its wheel lock, their semantic test, and the architecture-owned profile at `architecture/packaging/q2_build_tools.toml`. The existing `pyproject.toml` `[tool.policyos.q2_build_tools].profile_path` selects that file; its 16 fields bind the exact helper and lock digests plus the CPython 3.14, no-extras, universal-wheel, offline-only policy. `hatch.toml` includes the profile in the sdist. The Q2 runner compares the exact pyproject, profile, helper, and lock Git blobs with their archive bytes before the build-preparation callback can fetch inputs or create a venv.

```sh
supplemental_manifest="$prepare_root/proposed-supplemental-manifest.json"
supplemental_manifest_sha256="$(sha256sum "$supplemental_manifest" | cut -d' ' -f1)"
check_root="$repo/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/source-freeze-checks/${source_sha}-$(date -u +%Y%m%dT%H%M%SZ)"
python3 "$audit" check   --repo "$repo" --source-sha "$source_sha" --source-tree "$source_tree"   --python "$app_python" --uv-executable "$uv_executable" --collection-timeout-seconds "$collection_timeout_seconds"   --output-root "$check_root"   --supplemental-manifest "$supplemental_manifest"   --supplemental-manifest-sha256 "$supplemental_manifest_sha256"
```

## Launch after source freeze

Run on the supported Linux build/consumer worker with its existing locked Python 3.12 DoWhy 0.14 interpreter. Set the absolute interpreter paths to the worker's real environments. The Python 3.14 app environment must already contain pytest and the locked project test/runtime dependencies needed by source-resource inventory; the runner does not install into or mutate it. Hatchling is supplied separately by the source-bound offline build-tools profile.

```sh
repo=/absolute/path/to/polisyos
source_sha=ACTUAL_FULL_FROZEN_COMMIT_SHA
source_tree=ACTUAL_FULL_FROZEN_TREE_SHA
manifest_path="$repo/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/installed-wave-manifest.json"
manifest_sha256="$(sha256sum "$manifest_path" | cut -d' ' -f1)"
cd "$repo"
python3 "$repo/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/timeout_driver.py" \
  --repo "$repo" \
  --source-sha "$source_sha" \
  --source-tree "$source_tree" \
  --manifest "$manifest_path" \
  --manifest-sha256 "$manifest_sha256" \
  --app-python "$repo/policy-engine/.venv/bin/python" \
  --worker-python /absolute/path/to/existing/dowhy-014/.venv/bin/python
```

The two freeze variables must be filled from final-freeze evidence, not inferred from the candidate. If no existing worker interpreter is available, omit `--worker-python` only on Linux: the runner creates one retained environment from the frozen `workers/dowhy-014/uv.lock`, tries `uv sync --locked --offline` first, then retains that failure and makes a locked online fallback. It never skips the worker tests because provisioning failed.


## Separate supplemental consumer run

Run the supplemental installed consumers only after the primary run receipt has status `pass`. Supply the exact primary manifest and supplemental manifest bytes used for the primary freeze and source-audit check. `primary_run` is the exact completed run directory printed by the timed driver.

```sh
primary_run=/absolute/path/from/the-primary-driver-output
supplemental_manifest=/absolute/path/to/the-source-audit-proposed-supplemental-manifest.json
supplemental_manifest_sha256="$(sha256sum "$supplemental_manifest" | cut -d' ' -f1)"
python3 "$repo/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental_run.py" \
  --repo "$repo" --source-sha "$source_sha" --source-tree "$source_tree" \
  --primary-manifest "$manifest_path" --primary-manifest-sha256 "$manifest_sha256" \
  --supplemental-manifest "$supplemental_manifest" \
  --supplemental-manifest-sha256 "$supplemental_manifest_sha256" \
  --primary-run "$primary_run"
```

The supplemental runner confirms that the primary run receipt, both manifest byte hashes, source SHA/tree, and required three profile names all agree before reinstalling each existing wheel and running the supplemental selected collection. It records exact manifest paths/hashes in its own receipt.

## Exact artifact chain and checks

The timed driver verifies the reviewed runner and the exact primary manifest path/hash, then delegates to the primary runner. The runner executes these steps sequentially, with complete stdout/stderr and command records under the new ignored `LOCAL/q2-packaging/raw/runs/<freeze>-<UTC>-pid<PID>/` directory. From the exact `git archive` snapshot it loads the hash-bound `tools/quality/validation/q2_build_tool_wheel_lock.py`, the tracked wheel lock, the exact `pyproject.toml` profile pointer, and the external `architecture/packaging/q2_build_tools.toml` profile. Before any build-tools venv exists, it reconciles all four Git blobs with their archive members, fetches only the five locked PyPI release JSON documents and universal wheels into a new retained quarantine, checks exact final HTTPS URLs, a 1 MiB cumulative bound, release records, METADATA, WHEEL tags, exact RECORD path/hash/size bindings, and the complete CPython 3.14 no-extras dependency closure, then rereads that quarantine. It creates a fresh build-tools venv from the app interpreter's base Python and installs only those verified wheel files with `uv pip install --offline --no-index --only-binary :all: --no-deps --require-hashes`. It verifies the exact installed distribution/version set, package origins, absence of `.pth` files, and the Hatchling entry-point target; the wrapper digest is recorded as a host observation. The app dependency site is never appended to the build-tools venv. Source-resource inventory runs separately with the pre-existing app Python because the canonical owner helper imports application dependencies. The runner then creates the existing isolated Python 3.14 consumer venv and reuses it for the three installs.

```text
git archive <full-frozen-sha> -- policy-engine
uv pip install --offline --no-index --find-links <run>/build-tool-quarantine --only-binary :all: --no-deps --require-hashes --python <run>/build-tools-env/bin/python -r <run>/build-tools-requirements.txt
uv build --offline --no-build-isolation --python <build-tools-python> --wheel --sdist --out-dir <run>/dist-source
uv build --offline --no-build-isolation --python <build-tools-python> --wheel --out-dir <run>/dist-sdist
OUT_DIR=<run>/gcp-archive UPLOAD=0 PYTHON_BIN=<build-tools-python> bash <frozen-product>/ops/cloud/gcp/package_repo.sh
uv build --offline --no-build-isolation --python <build-tools-python> --wheel --out-dir <run>/dist-gcp
uv pip install --offline --reinstall --no-deps --python <one-installed-env-python> <each-wheel-in-sequence>
<one-installed-env-python> -I -m pytest <explicit-Q2-and-installed-consumer-selectors>
```

The `git archive` stream is hashed and extracted directly; it is not retained as a second full source tar. The source distribution and GCP archive are retained, unpacked, and rebuilt independently. Unchanged files in those extracted trees are hard-linked to the single frozen source snapshot; only changed/generated archive members are materialized separately. Each install uses `--reinstall`; every declared `hatch.toml` force-include (11 on this current route) are checked in the source, sdist, GCP archive, all three wheels, and installed site-packages.

`hatch.toml` remains the configuration source of truth. The runner compares its complete force-include mapping with the content-bound manifest, checks the source-sdist includes every such source, verifies the exact three GCP-selected sibling families (`data/dataset_catalog/`, `architecture/production_quality/`, `workers/dowhy-014/`), and refuses undeclared profile target files. If any frozen asset bytes/mapping changed after the candidate baseline, it stops before building and requires reconciling the manifest.

Dependency injection is deliberately isolated: interpreter metadata checks use `-S`; there is no `PYTHONPATH`; both temporary venvs reject `.pth` files, and the build-tools venv is verified before its first normal Python startup. No `sitecustomize.py` or app-site append is installed into the build-tools venv. Python consumers launch with `-I`; pytest uses `--import-mode=importlib` and `--confcutdir <frozen-product>/tests/unit`. The cutoff excludes the root `tests/conftest.py`, which unconditionally inserts the product `src` and `tests` paths, while retaining nested unit conftests needed for fixtures. A pytest plugin writes the complete collected node IDs and verifies after execution that neither the frozen nor live product root entered `sys.path` and every loaded `polisyos` or `tools` module resolves under the installed prefix. A separate isolated installed probe checks all manifest-listed installed asset digests and calls the digest-domain registry loader through the packaged default path.

The consumer invocation also uses pytest `-s`. `run_command` streams pytest's complete process stdout and stderr into separate `consumer-suite.stdout.txt` and `consumer-suite.stderr.txt` files, including output that selected passing tests print from their fresh installed-reader subprocesses. The consumer receipt records both paths, byte counts, and SHA-256 digests. JUnit remains the structural record of selected/executed node IDs and outcome counts; it does not duplicate captured output. Nonzero pytest exits still retain both stream files before the runner reports failure. If a caller supplies a timeout, `run_command` records the command as timed out and retains the partial stream files before raising. The consumer timeout remains unset until its wall time is measured.

## Required consumers and selector set

For each of the three installed wheel profiles, the runner replays the exact 91 original Q2 node IDs from the tracked `wheel-junit.xml.gz` baseline. The baseline gzip SHA-256 is pinned in the manifest; the runner checks the complete original ID set is still collected and actually executed. The original suite is all tests in these five source files:

- `tests/unit/scientist/methods/causal/test_graph_intake_current_content.py`
- `tests/unit/scientist/methods/causal/test_reconcile_causal_graph_node.py`
- `tests/unit/scientist/nodes/builtins/causal/test_reconcile_causal_graph.py`
- `tests/unit/foundry/methods/catalog/causal/test_graph_reconciliation.py`
- `docs/research/e02-cloud-test-plan/implementation-handoffs/F/installed-default-resource-final-20261007/test_installed_catalog_defaults.py`

The run adds 19 explicitly selected installed consumers: six dependency-profile selectors, three canonical bridge/worker selectors, two public API export-identity selectors, one B148 CLI refusal-report consumer, six CAN encoder/profile-boundary consumers (three IR/filesystem, one S3, one GCS, and one TenantScopedCAS), and one installed Ukraine Part A gate consumer. That Ukraine consumer invokes the installed console entrypoint outside a checkout, requires the persisted gate and stage reports to be unavailable and asserts no uv call. The same selected test separately probes source discovery against a marker-shaped fake ancestor and after removing only the C7 marker. At the current source, the five baseline paths contribute 116 selected IDs, and the complete current primary selector set contains 135 IDs. The original 91 Q2 IDs remain required within that set, while the named historical 100-ID subset remains unchanged. The runner reconciles the complete selector set against actual collection and JUnit IDs; the planned count alone is not evidence.

- `tests/unit/foundry/methods/test_dependency_profile.py`: `test_runtime_cutoff_predicate_is_one_sided_and_cutoff_specific`, `test_novel_profile_resolves_from_toml_without_code_change`, `test_cross_object_admission_or_reconciliation_mismatch_is_schema_invalid`, `test_unknown_authority_dto_field_fails_strict_parse`, `test_canonical_store_blob_manifest_or_signature_corruption_fails_before_parse`, and `test_missing_unreadable_or_corrupt_digest_registry_returns_source_not_established`.
- `tests/unit/foundry/methods/catalog/causal/test_installed_worker_profile.py`: `test_public_canonical_helpers_and_pure_report_factory_identity`, `test_real_installed_method_job_factory_and_fresh_reader_with_asset_removal`, and `test_installed_true_gcm_job_and_scientist_source_bound_interval_consumer`. The wrapper's transitive fixture modules are bound explicitly in the manifest and the actual callback source is checked before building.
- `tests/unit/data_forge/domains/ukraine/test_installed_wheel_no_checkout.py`: `test_installed_wheel_without_checkout_reports_gate_unavailable` executes the installed `ukraine-data` console consumer from outside the checkout, checks typed persisted `unavailable` outputs and a zero-call `uv` sentinel, and falsifies marker-shaped ancestor discovery while retaining the explicit-root structural contract.
- tests/unit/data_forge/read_api/test_catalog_graph_builders.py: test_country_normalizer_is_exported_by_catalog_read_api checks that the installed Data Forge read-API facade exports the canonical country normalizer by identity and normalizes DEU to DE.
- tests/repo_quality/architecture/test_public_surface_export_resolution.py: test_catalog_run_profile_is_exported_from_core_contracts_facade checks that polisyos.core.contracts.__all__ exposes CatalogRunProfile and that the exported object is identical to polisyos.core.contracts.control.CatalogRunProfile.
- The worker wrapper resolves `dowhy` to `tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py` for its `dgp` and `admit` helpers, and `gcm` to `tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py` for `test_actual_gcm_job_persisted_fresh_reader_and_scientist_consumer`. The GCM test persists the fitted model, reopens it in a fresh Python 3.14 reader, and runs the Scientist causal-query consumer with a source-bound estimator interval.

The explicit TOML used by the novel-profile test is a test fixture read from the frozen source tree; it is not claimed as a packaged default. The digest-domain TOML, by contrast, is checked as an installed default by its exact package target, byte digest, selected runtime path, and decoder invocation. The profile tests include valid declarations, schema/cross-object rejection, strict unknown-field rejection, CAS corruption controls, and a fail-closed corrupt-registry case. Despite its name, the selected `test_missing_unreadable_or_corrupt_digest_registry_returns_source_not_established` body exercises malformed TOML only; missing and unreadable path cases are not covered by this selected set.

Before the first wheel build, a source-driven AST preflight resolves every selected test node ID to its function body, follows local helper calls, discovers dynamic fixture-module loaders, verifies the manifest's exact kind-to-file binding, and confirms every wrapper callback exists with a compatible call signature in that file. A changed selector, unbound fixture kind, missing file, or missing callback fails before building. The run is green only when actual collection and JUnit each match the complete 135-ID current selector set and preserve the historical 91-plus-nine subset, all selected cases execute with zero skips/failures/errors, each profile has every manifest-listed installed asset byte, GCP selected sibling sets contain no undeclared files, and installed module origins/sys.path checks pass. Any pytest skip is an explicit failure, not an unsupported-profile waiver.

## Scope and scratch

This is one Linux platform, CPython 3.14 application wheel, and the separately locked CPython 3.12 / DoWhy 0.14 worker. It does not claim other Python versions, operating systems, architectures, accelerators, full backend/CI parity, production data, remote services, or EconML. No GPU, full-suite, browser, or production-data tests run. The only selected compute-heavy consumer is the installed GCM/source-bound scientist bridge test in the list above. Unsupported profiles are recorded here as out of scope; a setup failure for the selected profiles is a failed run.

Prior frozen source snapshot evidence measured 555,792,112 source bytes, a 121,945,591-byte sdist, 15,146,001-byte source wheel, and a 15,146,001-byte rebuilt-sdist wheel. With one retained source snapshot, hard-linked extracted payloads, three wheels, one installed app venv, the GCP archive, logs, and metadata, reserve approximately 1.5 GiB scratch when supplying the existing worker environment. This estimate excludes shared uv cache and excludes creating a new worker environment. GCP archive size and platform build overhead were not measured in this preparation turn; the runner records them at execution. It does not delete or overwrite any artifact, and each invocation uses a new run directory.

## Preparation status

The Phase 0 size-repair candidate relocates the 16-field Q2 profile from `pyproject.toml` to `architecture/packaging/q2_build_tools.toml` while retaining the existing pyproject table as an exact path pointer. It updates the helper, semantic tests, Q2 runner, source-audit input capsule, sdist include, and this recipe as one source-bound transport set. The Q2 package wave has not been executed; this candidate has not created a build-tools venv, installed packages, built archives or wheels, or run the helper tests. Static candidate checks do not establish an actual Phase 0 or Q2 CLI pass. The older ignored stdout/stderr retention probe remains historical evidence for the pre-candidate runner at `LOCAL/q2-packaging/raw/capture-retention-probe-20261009-r2/probe-receipt.json`; it does not verify this source candidate.

## Originless native-module collection boundary

The actual post-commit collection report `q2-r122-source-audit-prepare-r1/execution/audit/collect-primary-baseline.collection.json` has 3,837 `module_origins` rows. Exactly 29 have no origin and no search locations: 3 non-exact module subclasses, 5 exact supported data-only modules, 16 exact nondata modules with parent bindings, and 5 exact parentless-native candidates (`_cython_3_1_4`, `_cython_3_1_5`, `_cython_3_1_6`, `_cython_3_2_1`, `_cython_3_2_2`). The report predates native import-execution observations, so it supports denominator and routing research only; independent replay cannot retroactively establish the original producer. A fresh post-commit collection must capture the original same-process object/namespace transition and its selected source scope, then reconcile an independent replay under the bound startup/site profile and complete canonical RECORD ownership inventory.

The scope claim is a recomputed observed native `exec_dynamic` scope containing the target first appearance, bound to live module identity and namespace state, with contained same-thread nested deltas and subsequent state changes checked. The observer keeps nested stacks per thread and records the process-global active-scope interval relation under short bookkeeping locks; it never holds a lock across native execution. If a relevant target appearance or namespace delta overlaps any native scope on another thread, attribution fails closed and reports every competing scope ID, thread, source origin, source hash, and canonical RECORD binding rather than choosing a global deepest scope. Independent replay must reproduce the overlap-free selected-profile event. This does not prove sole instruction-level authorship, callable semantic equivalence, scientific equivalence, or vendor/issuer authenticity. Startup-entry and observer-install module-name sets are captured separately; a target already present at either boundary fails closed. The interval needed to start Python and load standard-library observer prerequisites is not claimed as observed.
