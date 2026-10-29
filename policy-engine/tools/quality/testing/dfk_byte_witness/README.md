# DFK native-byte witness source admission and run recipe

## Scope and authority boundary

This is a bounded Linux verification child-slice of canonical I2, routed through `LA-006@DFK-01` (original occurrence 230). It verifies one native non-UTF-8 filesystem/Git path through the existing DFK census and public CLI. It does not decide the LA-006 tombstone/import-compatibility criterion, package retirement, external callers, LA closure, LA-005 mixed-root census, LA-026 distribution, installed I2/Q2/DX0, or G acceptance. State remains `verification_missing` until the qualified witness exists; return `G_acceptance=false` and `closure_ids=[]`.

Reuse `tools.quality.validation.schema_fqn_census` and its registered CLI. There is one existing writer: the DFK census owner. Scanner edits are allowed only if the source-qualified baseline demonstrates a product defect; allowed product paths are the existing scanner and `tests/unit/remediation/test_dfk_01.py`. One narrowly scoped lossy-decoder removal control in that test file is allowed because the pinned source lacks it. No new scanner/helper framework, generic string conversion, replacement-character repair, or unrelated files.

## Source identity and pins

The adjacent `pins.json` SHA-256 is `0bde0f6615a68cd284a5d65ce72bff5720ad8034b81b05f7185777f2abbd8fcf`. Its `derivation_cut` is the provenance for the finite 19-path list, not the future task source identity. The coordinator must bind an actual published exact commit/tree and receipt separately. Before any project import, test, dependency setup, or CLI:

1. Read `AGENTS.md`, `policy-engine/CONTRIBUTING.md`, and `policy-engine/docs/reference/policy-design-case-failure-patterns.md`.
2. Verify `git rev-parse HEAD`, `git rev-parse HEAD^{tree}`, symbolic branch/detached state, and `git status --porcelain=v1 --untracked-files=all`; require the dispatch commit/tree and no pre-existing product source/test/config changes. Do not fetch, switch, reset, reclone, clean, or mutate refs/index to force admission. Detached/no-origin is acceptable only at exact IDs.
3. Set `E02C_ROOT` to repo root, `E02C_HARNESS=$E02C_ROOT/policy-engine/tools/quality/testing/tc_sql_mc_witness`, `E02C_OUT` to the new task-owned nonignored output directory, and `E02C_SCRATCH` to fresh private scratch outside source.
4. Confirm the dispatched `E02C_OUT` path does not exist, then create it exactly once with `commands/`, `origins/`, and `observations/`; never overwrite an older task. Keep `E02C_SCRATCH` private and separate from checkout/output. Copy the tracked `dfk_byte_witness/pins.json` byte-for-byte into `$E02C_OUT/pins.json`, verify the SHA-256 equals `0bde0f6615a68cd284a5d65ce72bff5720ad8034b81b05f7185777f2abbd8fcf`, and record the copy/hash command:

```sh
test ! -e "$E02C_OUT" || { printf 'output already exists\n' >&2; exit 1; }
mkdir -p "$E02C_OUT/commands" "$E02C_OUT/origins" "$E02C_OUT/observations"
cp "$E02C_ROOT/policy-engine/tools/quality/testing/dfk_byte_witness/pins.json" "$E02C_OUT/pins.json"
python3 -B -c 'import hashlib,pathlib; p=pathlib.Path("'"$E02C_OUT"'/pins.json"); print(hashlib.sha256(p.read_bytes()).hexdigest())'
```

5. Resolve an absolute `$PY` for an already installed supported CPython 3.14, record its executable path and version, and use that exact executable for source admission, pytest, and the separately source-captured CLI. If the required interpreter is unavailable, stop with environment ERROR/UNRUN; do not download or copy an environment. Run the already tracked generic helper with standard-library Python before product imports; preserve exact argv/cwd, full stdout/stderr, and exit:

```sh
"$PY" -B "$E02C_HARNESS/source_admit.py" \
  --root "$E02C_ROOT" --base "$E02C_COMMIT" --tree "$E02C_TREE" \
  --pins "$E02C_OUT/pins.json" --pins-sha256 0bde0f6615a68cd284a5d65ce72bff5720ad8034b81b05f7185777f2abbd8fcf \
  --out "$E02C_OUT" --scratch "$E02C_SCRATCH"
```

`E02C_COMMIT` and `E02C_TREE` are exact late-bound published identities from the commission, never copied from the pins derivation cut. `source_admit.py` checks `HEAD`, tree, every selected working file against both `git show <base>:<path>` and the supplied SHA/Git blob, relevant tracked changes, untracked Python sources, and writes `source-admission.json` plus the isolated `git-input-index.json`. A mismatch is source-admission ERROR/UNRUN; do not continue. Re-read admitted pins and source/test/config state after the deciding commands.

The manifest has 19 selected file rows derived from the one pinned input file `LOCAL/raw/e02-execution-20261027/next-cloud/I2-linux-byte-current-r2/pins.json` (one JSON file, 19 `files[]` entries). A complete `git show <derivation-commit>:<path>` walk computed each byte count, SHA-256, and Git blob from derivation cut `ef4eff67881069da6a1809acd7dacacf4489f8b0` / `cf5e8fd7f05a39af01a28f7eca601ee6163fcdef`; comparison with the preceding f672 source pin table found 0 changed rows across the same 19 paths. This is a finite selected input set, not every runtime read. For source qualification, also pin the helper bytes and actual commands in the future task material: generic `source_admit.py` SHA `aabe68801ee20cd75e0e2b95f512596a58e0e4ecf2688bdf864c4158e43ec871`; C134 `sitecustomize.py` SHA `c39de7af3f237eba8fdd7b99c1af5bd95aa73d8c8a3c9dab7ec3dfcba16a8beb`; generic full-run observer SHA `f42f8469de8ec9fdbc899333d55b20b756efd27805ac1164ddf9c22c68862e7b`. Requalify those helper paths against the future published Git tree too. Do not substitute C134 `run_case.py` or `cloud_observer.py`; their fixed 139-node contract is unrelated.

## Resource and runtime admission

Before compute, record UTC, host/kernel/architecture, checkout/output/scratch filesystems, Python/pytest/Git/uv versions, `df -Pk`, `/proc/meminfo` available/total, and cgroup v2 memory max/current when present. Keep disk and RAM separate; 32 GB is disk-planning guidance only. Repeat after any allowed dependency setup. Use an already available supported CPython 3.14 and the locked existing test dependency only if missing and normally available within measured resources. No model download, production/private data, environment copy, wheel build, package installation, whole suite, full census, DB, numeric backend, or broad artifact/package run. Missing prerequisite is environment ERROR/UNRUN, never product failure.

Create a new private scratch root and unique empty per-process pycache/temp/cache paths before startup. Record the exact allowlist and presence-only names of inherited `PYTHON*`, `PYTEST*`, `E02C_*`, `POLISYOS_*`, and `GIT_*` controls; use `env -i` for the direct CLI process, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONNOUSERSITE=1`, fresh `PYTHONPYCACHEPREFIX` before startup, and `-B`. Do not disclose secret-bearing inherited values.

## Ordered execution

### 1. Existing positive pytest node

Run only this exact node first, no `-k` or whole-module substitution. Create its cache/temp paths and `observer-positive/` directory fresh and empty before this command; the observer creates one per-PID child directory with exclusive creation:

```sh
cd "$E02C_ROOT/policy-engine"
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$E02C_SCRATCH/pytest-pycache" \
TMPDIR="$E02C_SCRATCH/pytest-tmp" XDG_CACHE_HOME="$E02C_SCRATCH/pytest-xdg" \
POLISYOS_CACHE_HOME="$E02C_SCRATCH/pytest-cache" \
HYPOTHESIS_STORAGE_DIRECTORY="$E02C_SCRATCH/hypothesis" \
E02C_ROOT="$E02C_ROOT" E02C_OUT="$E02C_OUT" E02C_INDEX="$E02C_INDEX" \
E02C_PHASE=pytest-byte-positive E02_OBSERVER_DIR="$E02C_OUT/observer-positive" \
PYTHONPATH="$E02C_HARNESS:$E02C_ROOT/policy-engine/docs/research/e02-cloud-test-plan/full-run:$E02C_ROOT/policy-engine/src:$E02C_ROOT/policy-engine/tests:$E02C_ROOT/policy-engine" \
"$PY" -B -m pytest -p e02_observer -q -ra --tb=short \
  --junitxml="$E02C_OUT/commands/native-byte.junit.xml" \
  tests/unit/remediation/test_dfk_01.py::test_dfk_01_census_reads_native_invalid_byte_git_filename
```

Capture full argv/cwd/env allowlist, stdout/stderr/exit, JUnit, observer collection/phase records, and C134 per-PID code/origin receipts. Verify exactly one collected and executed target, zero skips, and record the child's actual command from the test source. The existing test helper resets child `PYTHONPATH` to product root and `src`; the parent receipt cannot qualify that child (P38). Do not infer child origin from JUnit or a pass.

### 2. Property-removal control

Add the one allowed named test `test_dfk_01_native_invalid_byte_removal_control_detects_lossy_fsdecode` to the existing test module. It must reuse the real temp Git fixture, actual `schema_fqn_census.collect_census`, and independent raw Git-byte oracle. Temporarily replace the actual `os.fsdecode(bytes)` seam with UTF-8 replacement decoding while leaving strings unchanged, and prove the selected/unreadable path diverges from raw Git bytes and cannot claim the exact-byte positive; restore with pytest `monkeypatch`, then rerun the real positive to prove restoration. Keep output markers/fields present during the lossy mutation so the control tests behavior, not form. If the scanner boundary changed, mutate its actual shared decoder seam. Never patch source for the control or treat an unexercisable discriminator as PASS.

The full AST denominator is one Python file (`policy-engine/tests/unit/remediation/test_dfk_01.py`): 26 top-level definitions/45 literal-parameterized cases. After adding one non-parameterized control, recompute full AST counts and actual pytest collected IDs; expected 27 definitions/46 cases, selected set exactly the two byte nodes. Any mismatch is recorded, not assumed. Run exactly both selectors after the control exists (and again after any repair):

```sh
# Use fresh, empty per-run pycache/temp/cache paths and a fresh observer directory.
cd "$E02C_ROOT/policy-engine"
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$E02C_SCRATCH/controls-pycache" \
TMPDIR="$E02C_SCRATCH/controls-tmp" XDG_CACHE_HOME="$E02C_SCRATCH/controls-xdg" \
POLISYOS_CACHE_HOME="$E02C_SCRATCH/controls-cache" \
HYPOTHESIS_STORAGE_DIRECTORY="$E02C_SCRATCH/controls-hypothesis" \
E02C_ROOT="$E02C_ROOT" E02C_OUT="$E02C_OUT" E02C_INDEX="$E02C_INDEX" \
E02C_PHASE=pytest-byte-controls E02_OBSERVER_DIR="$E02C_OUT/observer-controls" \
PYTHONPATH="$E02C_HARNESS:$E02C_ROOT/policy-engine/docs/research/e02-cloud-test-plan/full-run:$E02C_ROOT/policy-engine/src:$E02C_ROOT/policy-engine/tests:$E02C_ROOT/policy-engine" \
"$PY" -B -m pytest -p e02_observer -q -ra --tb=short \
  --junitxml="$E02C_OUT/commands/native-byte-controls.junit.xml" \
  tests/unit/remediation/test_dfk_01.py::test_dfk_01_census_reads_native_invalid_byte_git_filename \
  tests/unit/remediation/test_dfk_01.py::test_dfk_01_native_invalid_byte_removal_control_detects_lossy_fsdecode
```

Preserve full stdout/stderr/exit, JUnit, observer receipts, and both actual collected node IDs. A source edit changes the candidate identity: source-admit the exact candidate commit/tree with a fresh compact pin manifest before claiming source qualification.

If product code changes are required after a qualified failing assertion, preserve initial evidence, use the single DFK writer, check mandatory direct companions from CONTRIBUTING, and bind each candidate commit/tree and fresh pin manifest. Before each commit check `git status -sb`; commit a clean source/test boundary. Rerun only the positive/control plus consumers directly affected by the edited function. No scanner edit is warranted by an environment/setup error.

Historical context: the old I2 Mac run at `320ceeac32ae5dcea44bfcfe884f74ffb6ba0127` had four `OSError 92` fixture-creation errors before CLI/oracle execution; classify that as an environment/filesystem error, not a product result. The old C107 Linux run observed 32 source cases/16 definitions including this byte test but lacked qualified pytest-parent and CLI-child source capture; it is not current-source evidence. Do not rerun its broader pack or old timeout.

### 3. Separately source-captured public CLI

Build a tiny synthetic Git repository under fresh scratch with a harmless tracked README and two small JSON files whose literal pathname bytes are `b"native_\xff.json"` and `b"native_\xfe.json"`. Write byte paths using filesystem bytes; do not use replacement-decoded strings. Give payloads the same harmless existing DFK FQN marker and distinct values. Record raw `git ls-tree -rz --full-tree HEAD`, `git ls-files --stage -z`, raw blob IDs and exact `git cat-file blob` bytes/SHA; prove both names and object IDs differ.

Resolve and record absolute admitted `$PY` and Git executable. For this CLI process create empty fresh per-process pycache, TMPDIR, XDG cache, PolicyOS cache, and empty production-data root before startup; set `POLISYOS_PRODUCTION_DATA_ROOT` to that empty root, create output `origins/`, and retain this PID’s own normal-exit receipt. The C134 capture is available only on supported CPython 3.14; if unavailable or its monitoring slot is occupied, classify this source-origin stage UNRUN rather than dropping capture. Build its environment with `env -i`. Before constructing it, record only inherited control variable names/presence (not values) for `PYTHON*`, `PYTEST*`, `E02C_*`, `POLISYOS_*`, and `GIT_*`; then pass only this explicit allowlist and record exact values: `PATH` (directory containing resolved Git), `HOME` (fresh empty scratch home), `LANG` (recorded installed UTF-8 locale), `PYTHONPATH` (order below), `PYTHONDONTWRITEBYTECODE=1`, `PYTHONNOUSERSITE=1`, fresh `PYTHONPYCACHEPREFIX`, `TMPDIR`, `XDG_CACHE_HOME`, `POLISYOS_CACHE_HOME`, `POLISYOS_PRODUCTION_DATA_ROOT`, `E02C_ROOT`, `E02C_OUT`, `E02C_INDEX`, `E02C_PHASE`, `GIT_CONFIG_NOSYSTEM=1`, and `GIT_CONFIG_GLOBAL=/dev/null`. Invoke Python via its recorded absolute executable; do not add installed/user paths. If no supported UTF-8 locale is installed, record the actual runtime filesystem encoding/error mode without silently substituting a locale. Run from exact cwd `$E02C_ROOT/policy-engine`:

```sh
env -i \
  PATH="$GIT_DIR" HOME="$E02C_SCRATCH/empty-home" LANG="$LANG_UTF8" \
  PYTHONPATH="$E02C_HARNESS:$E02C_ROOT/policy-engine/src:$E02C_ROOT/policy-engine" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  PYTHONPYCACHEPREFIX="$E02C_SCRATCH/direct-pycache" \
  TMPDIR="$E02C_SCRATCH/direct-tmp" XDG_CACHE_HOME="$E02C_SCRATCH/direct-xdg" \
  POLISYOS_CACHE_HOME="$E02C_SCRATCH/direct-cache" \
  POLISYOS_PRODUCTION_DATA_ROOT="$E02C_SCRATCH/empty-production-data" \
  E02C_ROOT="$E02C_ROOT" E02C_OUT="$E02C_OUT" E02C_INDEX="$E02C_INDEX" \
  E02C_PHASE=direct-cli-native-byte GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null \
  "$PY" -B -m tools.cli validation schema-fqn-census \
  --output-format json --repo-root "$SYNTHETIC_GIT_ROOT"
```

Here `PY`, `GIT_DIR`, `LANG_UTF8`, `SYNTHETIC_GIT_ROOT` are the recorded absolute executable/path and validated values; capture the final environment exactly. All per-process directories must be created empty before this process starts.


Capture exact argv/cwd/environment allowlist, inherited-control presence scrub, filesystem encoding/error mode, complete stdout/stderr/exit, and this child's own C134 `sitecustomize` capture. Verify origin receipt executable equals `$PY`; `tools.cli`, `tools.registry`, and `tools.quality.validation.schema_fqn_census` resolve under this checkout; observed project bytes match admitted Git index; no first-party module is installed, foreign, modified, or unresolved. Parse JSON independently and require both exact surrogateescape path spellings in selected/read/match paths; reconcile selected byte digests with committed blobs. Parent pytest capture does not qualify this process.

## Outcomes and delivery

Classify each stage independently: `PASS` requires the exact current published source, native Linux, both path/object identities through the real CLI/scanner, positive and lossy-removal/restoration discrimination, and qualified relevant process/source observations. `PRODUCT_FAILURE` requires a target assertion executed after prerequisites and collection succeeded. `ENVIRONMENT_ERROR` is measured filesystem/runtime/dependency/resource absence. `HARNESS_ERROR` is admission, origin, observer, or collection failure. `UNRUN` means not reached. A semantic result without child source qualification is bounded partial, not full PASS. Do not infer full I2, installed behavior, complete DFK census, LA closure, or G acceptance.

Deliver task-owned nonignored evidence under `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/I2/cloud/e02-linux-byte-current-r2/`: actual deciding stdout/stderr/JUnit, commands/environment, resource measurements, observer/origin receipts, raw Git path/object oracle and outcomes. A/B/C/D artifact classes; target <=512 KiB. Do not deliver environment/source archive, DB/CAS, production data, caches, or unrelated files; do not use upload workarounds. Return actual accessible managed diff/commit only after readback. Report `G_acceptance=false`, `closure_ids=[]`.
