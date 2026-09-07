# Toolchain inputs — 2026-09-07

## Disposition

| Row | Classification | Stop condition |
| --- | --- | --- |
| `basedpyright-runner-rewrites-a-frozen-baseline-as-a-side-effect` | **blocked-and-why** | The measured repair must reach existing launchers in forbidden `tools/devx/**`; the maintained workflow template is also outside the allowlist. |
| `pillow-is-built-from-source-on-every-ci-run` | **blocked-and-why** | Pillow isolation works in a scratch candidate, but the required wheels-only dependency-set install still fails on base dependencies. Removing/replacing HNSW changes active capabilities and requires an architect decision and forbidden source edits. The candidate also rejects an existing all-extras cloud-runner install mode whose migration is outside the allowlist. |

An instrument must not mutate the inputs it measures. The interpreter the project declares must be able to install its dependency set from wheels. Neither closure signal is claimed here. The delivered change is this journal; production runners, baselines, dependency declarations, lockfile, actions, and workflows remain unchanged. Candidate repairs below are proposals, not installed behavior.

## Station, scope, and evidence custody

- Local worktree: `/Users/deniskopylov/polisyos/.worktrees/toolchain`.
- Attached branch: `codex/toolchain-inputs`, created by the requested `git worktree add` from `938ddc32a5e243267a8fcd578364ff7c8505df9e`.
- Station: macOS 26.6.2, arm64; dependency experiments use CPython **3.14.0**, `/opt/homebrew/bin/python3.14` (resolved executable `/opt/homebrew/opt/python@3.14/bin/python3.14`).
- Resolver: canonical **uv 0.9.21**, invoked through `uvx --from uv==0.9.21 uv`. Host uv is 0.10.6; it was only the launcher for the pinned resolver. Successful no-compiler probes invoke the resolved 0.9.21 executable directly.
- Linux measurements use `--python-platform x86_64-manylinux_2_28` on this Mac. They are actual target installs, **not native Linux execution or a CI run**.
- All dependency installs enforce `--no-build` or `--only-binary :all:` and use `--no-cache`. Project-set probes use `--no-install-project`: they test third-party dependencies, excluding the repository's editable build. A failure already in that dependency set refutes full-install closure; a successful subset would not prove it.
- Every gate was a sole command in its invocation; stdout/stderr are retained in full, and exit codes come from the process/tool receipt. No appended `echo` was used to infer status. No directory-wide pytest or broad verification suite was run.
- The debt documents were excluded before content reads; their presence/content was not used as a gate. `check_debt_ledger.py` was never run. No GitHub plugin, push, rebase, stash, or other lane's edits were used.

Evidence roots, relative to this worktree:

| Alias | Local retained evidence |
| --- | --- |
| `B` | `policy-engine/_build/toolchain-row1/` — checker logs, byte comparisons, complete worktree/launcher censuses, installed-source excerpts, fixture, `row1-report.md`. |
| `D` | `policy-engine/_build/toolchain-inputs/` — original/candidate manifests and locks, full install output, PyPI metadata, `command-receipts.json`, `input-provenance.json`, `station.json`. |
| `I` | `policy-engine/_build/toolchain-inputs/isolation/` — isolated candidate, exact argv/environment/exit/time receipts, exports, installed wheel metadata, semantic lock comparison. |
| `U` | `_build/toolchain-inputs/marker-usage/` — complete SHA-bound tracked-file census, AST imports, CI selections, call-chain and API evidence. This root is repository-local, not product-local. |

These are ignored local evidence, retained for this local handback; they are not committed artifacts and will not travel with a fresh clone. The journal records the results and replay commands. `D/input-provenance.json` verifies that both original experiment inputs, `pyproject.toml` and `uv.lock`, are byte-identical to the pinned base and the unchanged working files.

## Pattern pass

Read `docs/reference/policy-design-case-failure-patterns.md` before investigation and again before closeout. Relevant findings: P27 (a disconnected quality wrapper would bypass the owner), P29/P33 (exercise actual analysis and hostile variants), P31/P40 (include sibling launchers; classify further missing-wheel packages as the same dependency-install class), P35 (complete denominators), P37/P38 (measure the property), P41 (pin the input provenance).

The predicates admitted here are `recomputed`: baseline byte comparisons, complete file inventories, selected dependency exports, and actual subprocess/install results. Production closure is `not_established`. The decisive divergent cases are concrete: the old checker returns zero while changing its baseline; Pillow alone installs successfully while the complete dependency set fails. Neither exit zero nor a successful package subset substitutes for the requested property. The immutability repair remains `bridge_missing` and `semantic_test_missing`; Marker conversion also has a measured API mismatch and lacks a successful semantic conversion receipt. No new product capability is claimed.

## Row 1 — measured mutation, forbidden repair boundary

### Ordering-risk census

`B/sibling-baseline-census.json` walks **all 31 worktrees under `.worktrees/`** (30 siblings plus this toolchain worktree), recursively comparing every file under each `policy-engine/architecture/baselines/` with its own HEAD blob. Denominator: **1,023 file instances**, 33 per worktree, every file type (JSON, Markdown, TOML, TXT). Result at the early census: **zero changed, added, or deleted baseline instances**. The directory's additional `.DS_Store` entry is not a worktree. No sibling was edited.

### Root cause and witnesses

Installed basedpyright **1.39.0** matches the version in the pinned lock. Its baseline writer defaults to `auto` outside CI and `lock` inside CI. Ordinary `auto` checking prunes resolved/missing diagnostics and writes the configured baseline, even without `--writebaseline`.

The real `core_runtime_basedpyright.main()` was run against an isolated scratch project by redirecting its `PRODUCT_ROOT`; no production baseline was used as a disposable fixture. The configured baseline changed from SHA-256 `83228f47f5d9c597786fd3f25a4cbd58763245e86d9bd5a4c2504a848d1b91fe` to `f0ccaae1154b4bd0625cd134cb35e0ff1d31c194bbf9031d9ad7d1802824a29e` at exit **0**. A second, unrelated sentinel baseline stayed unchanged.

The executable was supplied read-only by `/Users/deniskopylov/polisyos/policy-engine/.venv/bin/`; that environment was not installed into or rebound. The initial Python-3.14 analysis fixture also reproduced mutation, but exited **3** because installed typeshed emitted a separate `string/templatelib.pyi` diagnostic. Controlled subsequent fixture probes analyzed Python **3.13**, with the same locked basedpyright. This is a bounded mechanism witness, not project-Python-3.14 typing acceptance.

| Actual fixture probe | Exit | Byte property and retained receipt |
| --- | --- | --- |
| Existing runner, ordinary check | 0 | Configured baseline changed; `B/03-existing-runner-check-py313.log` and paired byte-diff JSON. |
| Native `--baselinemode=discard`, twice | 0 / 0 | Both files in the complete two-file fixture baseline set were byte-identical before the first run and after the second; no intermediate byte snapshot was retained. `B/04-discard-first.log`, `05-discard-second.log`, `05-discard-two-runs-byte-comparison.json`. |
| Discard mode plus a new unbaselined assignment error | 1 | Error rejected; both fixture baselines unchanged; `B/07-discard-new-error.log` and paired JSON. |
| Explicit `--writebaseline` | 0 | Only the configured baseline changed; `B/08-explicit-update.log` and paired JSON. |
| `--baselinefile baseline-copy.json` | 0 | Failed remedy: configured `baselineFile` wins; original changed while copy stayed unchanged; `B/06-baselinefile-copy.log` and paired JSON. |
| TOML `baselineMode = "discard"` | 3 | Failed remedy: unsupported setting, and baseline still changed; `B/09-config-baselineMode.log` and paired JSON. |

### Connected repair to hand back

`B/tracked-launch-census.json` enumerates 10,581 tracked paths: 10,522 UTF-8 text files across all text file types, 57 binary files, and the two debt-document exclusions before reading. All direct maintained launch sites found in that complete denominator are:

| Path | Exact proposed change |
| --- | --- |
| `policy-engine/tools/devx/workspace/core_runtime_basedpyright.py:113` | Add `"--baselinemode=discard"` to the basedpyright argument vector in `_run_scope`. |
| `policy-engine/tools/devx/workspace/python_base_basedpyright.py:45` | Add the same argument to the `uv_run` basedpyright command. |
| `policy-engine/tools/devx/workspace/runtime_surface.py:70` | Add the same argument to the runtime-source basedpyright command. |
| `policy-engine/ops/ci/templates/workflows/arch.yml:46` | Change `run: uv run basedpyright --project basedpyright.toml` to `run: uv run basedpyright --project basedpyright.toml --baselinemode=discard`. This is a workflow template, not an active `.github/workflows` job. |

The active `.github/workflows/core-runtime-release-gate.yml` delegates to the core-runtime launcher, so that active workflow needs no edit for this repair. The initially missed runtime-surface sibling was classified **same class deeper**, and the proposal expanded to the complete launcher denominator. An allowed `tools/quality` implementation without these consumers would leave the defect active; none was added. A pyproject console-script shadow or rewriting the baseline would likewise fail the requested property.

After the owning lane accepts the boundary change, add targeted real-entrypoint tests for resolved baseline entries, new diagnostics, sentinel files, and explicit update. Then commit the repair and run the production checker twice from a clean attached tree, checking the full `git status` and all baseline bytes after each run. **Those production closure runs remain unperformed.**

Commands from `policy-engine/`, for that future authorized repair:

```bash
uv run --extra lint python -m tools.devx.workspace.core_runtime_basedpyright
```

Native non-writing analysis over the configured scope:

```bash
uv run --extra lint basedpyright --project basedpyright.toml --baselinemode=discard
```

Explicit baseline maintenance, only when requested:

```bash
uv run --extra lint basedpyright --project basedpyright.toml --writebaseline
```

Remaining owner: `team-devx` with runtime/quality. The forbidden launcher boundary, rather than the existence of a local prototype, determines this row's blocked disposition.

## Row 2 — three routes measured, complete install still blocked

### Actual repository use and CI selection

`U/summary.json`, `inventory.json`, `parser_imports.json`, `matches.json`, and `ci-census.json` enumerate the complete tracked set, excluding debt documents before reads. Python denominator: **5,761 `.py` files** across the repository, comprising 2,621 under `policy-engine/src`, 2,507 under `policy-engine/tests`, 434 under `policy-engine/tools`, and 199 elsewhere; all parsed without an AST error.

There is one static Marker import, in `academic/batch/table_extractor.py`. The intended chain is `doc_normalize` PDF input → `extract_tables_from_pdf` → structured `doc_tables_path` / ready-queue artifacts with `structure_source=marker_pdf` → `_resolve_extract_api` structured-table consumption. Missing Marker returns an empty table list; text/TEI alternatives remain, but do not establish equivalent structured OCR/table output. The `table_extraction_enabled=False` and backend configuration declarations do not guard that call path.

The locked wheel `marker_pdf-1.10.2-py3-none-any.whl` (SHA-256 `f631737dd46d3927142b4b14c7b488962c5af278dc2c3ae7dc5b03a47f5909fb`) also reveals a concrete adapter mismatch: the repository calls `PdfConverter(str(path)); converter()`, whereas its constructor expects an artifact dictionary and `__call__` requires a filepath. Extracted original method bodies reject those calls with `TypeError`; heavy import/base/render dependencies were stubbed for this falsifier. `U/marker-api-receipt.json` explicitly records that limitation: **this was not a full Marker install or PDF-conversion test**. The mismatch belongs in a source-owner proposal; it is not authority to silently remove the intended capability.

`table-extraction = ["marker-pdf>=0.3.0"]` is **already optional**. `all` and `research` do not include it. Complete active-CI denominator: **12 `.yml`/`.yaml` workflow files, 52 jobs, 299 steps**, plus all **3 action YAML files**. None requests table-extraction directly or transitively. The **28 calls** to the Python composite resolve as follows (counts sum to that call denominator):

| Selection | Calls / 28 |
| --- | ---: |
| Profile minimal → lint test | 2 |
| Profile docs → lint docs | 2 |
| Profile runtime → lint test runtime | 11 |
| Extras all | 1 |
| Extras docs | 1 |
| Extras lint test | 1 |
| Extras lint test runtime analytics ml | 1 |
| Extras lint test runtime docs causal-discovery | 1 |
| Extras test mutation runtime | 1 |
| Extras test runtime analytics ml | 2 |
| Extras test runtime causal-discovery | 1 |
| Extras test runtime causal-discovery sandbox | 2 |
| Extras test runtime causal-discovery security | 2 |

Direct canary/substrate `uv run` paths also do not select table-extraction. The release-wheel `pip install` path selects runtime-http. The separate ABI declaration-checker environment only installs its checker dependencies. Full step bodies and graph expansion are retained in `U/ci-census.json` and `workflow_installs.json`.

Moving Marker into an ordinary extra again would therefore stop CI syncing **nothing**: it is already omitted from installation. The problem is its cap in the universal lock resolution, which still constrains shared Pillow (and other transitive packages). [uv's resolution documentation](https://docs.astral.sh/uv/concepts/resolution/#conflicting-dependencies) describes the joint resolution and explicit extra/group conflicts; the experiment below verifies behavior with the project's pinned resolver.

### Three-route comparison

| Route | Measured result | Decision / remaining boundary |
| --- | --- | --- |
| Move the cap, including upgrading Marker | Actual `marker-pdf>=0.3.0` plus `pillow>=11`, wheels-only, exits **1**: resolver enumerates available stable candidates and rejects their Pillow cap. Explicit latest stable 2.0.0 also exits **1** on `<11`. Overriding Pillow to `>=12` for locked Marker 1.10.2 still exits **1**, now because its `regex>=2024.4.28,<2025` range has no usable wheel. Full outputs: `D/marker-cap-range.log`, `marker-upgrade.log`, `marker-override.log`. | No offered stable version solves it. An override/fork would need compatibility validation across Marker, Surya and the existing mismatched source adapter. No constraint was falsified in the production manifest. |
| Remove/replace the imposing dependency | Scratch removal preserves the extra name but empties it, then `uv lock --upgrade-package pillow` succeeds. Complete package-record comparison: **416 original → 401 candidate**; 15 package names removed, Pillow 10.4.0 replaced by 12.3.0. `D/remove-marker-diff.json` enumerates every changed identity. Actual frozen dev/test wheels-only sync still exits **2** on HNSW. | Removal withdraws the intended structured table producer; text/PDF siblings are not a proven equivalent replacement. A replacement needs adapter work under forbidden `src/**` and an architect's capability decision. Not implemented. |
| Truly isolate the existing extra from the default dependency group | Scratch adds Pillow `>=12` to dependency-group `dev` and declares that group incompatible with extra `table-extraction`. Lock succeeds. Default/dev/test exports select Pillow **12.3.0**; actual wheels-only Pillow installs succeed on macOS arm64 and Linux x86_64 target. Full dependency-set sync still exits **2** on HNSW. | Least invasive **Pillow-specific proposal**, preserving the optional Marker branch. It does not satisfy the user's complete dependency-set closure, so it was not installed or described as repaired-with-a-limit. |

The isolated candidate has **417 package records versus 416 originally**, with the same 416 names: it adds a Pillow 12.3.0 branch and retains 10.4.0 for table extraction. Of the original 416 package identities, **50 records** also have field changes, including dependency marker expansion and wheel inventories. This is not a claim that the whole lock diff changes only a Pillow version. `I/lock-semantic-diff.json` contains the complete comparison.

Exact scratch isolation proposal (`I/pyproject.diff`), not a production edit:

```diff
 [dependency-groups]
 dev = [
   "libcst>=1.5.0",
+  "pillow>=12",
 ]
+
+[tool.uv]
+conflicts = [[{extra = "table-extraction"}, {group = "dev"}]]
```

Default bare sync and dev/test selection retain the default group. Bare `--no-default-groups` also exports Pillow 12.3.0 in the measured candidate lock. Selecting table-extraction with `--no-default-groups` exports Pillow 10.4.0; table-extraction with default groups rejects the declared conflict at exit **2**. Extra `dev` is distinct from group `dev`: table-extraction plus dev/test extras is exportable with default groups disabled. Actual table-extraction/no-default-groups wheels-only sync still stops on HNSW at exit **2**. These selection exports establish which branch would install; they do not establish successful whole-environment installation.

Independent review identified a concrete existing consumer of the conflicting combination: `policy-engine/tools/ops_runners/experiments/run_msme_final_v3_cloud_rerun.py:113` emits `uv sync --all-extras --dev`. A fresh pinned-uv export of the candidate with `--frozen --all-extras --dev --no-hashes --no-emit-project` returned **2**, rejecting table-extraction plus group dev. Root also ran the actual install attempt from `I`: `uvx --from uv==0.9.21 uv sync --frozen --all-extras --dev --no-install-project --no-build --no-cache --python /opt/homebrew/bin/python3.14`; it returned **2** with the same conflict, retained in `I/sync-cloud-all-extras.log`. This is **same class deeper** (isolation's install-mode migration), not a new repair round. That maintained caller would need migration in forbidden `tools/ops_runners/**`; merely documenting the new command would not wire it. The isolation proposal preserves an explicit Marker branch but is not backward-compatible with this existing installation mode. The caller and the full-set install blockers remain declared limits; no further candidate mechanism was added.

### Install receipts and the wider blocker

All root command argument vectors, shell-quoted replay commands, actual exits and full-output SHA-256 values are in `D/command-receipts.json`. Isolation gate JSON files include argv, cwd, timestamps, duration and exit.

| Actual attempt | Exit | Receipt / meaning |
| --- | --- | --- |
| Original frozen dev/test dependency set, CPython 3.14, macOS | 2 | `D/original-sync.log`: HNSW 0.8.0 has no binary distribution. |
| Same original frozen set, Linux x86_64 target | 2 | `D/original-sync-linux.log`: same HNSW rejection. |
| Locked Pillow 10.4.0 alone, macOS / Linux target | 1 / 1 | `D/pillow-locked.log`, `pillow-locked-linux.log`: no usable wheel. |
| Removed-Marker candidate frozen set | 2 | `D/remove-marker-sync.log`: HNSW still blocks. |
| Isolated-extra candidate frozen set | 2 | `I/sync-ci-wheels.log`: HNSW still blocks. |
| Pillow 12.3.0 alone with compiler discovery removed, macOS / Linux target | 0 / 0 | `I/pillow-macos-no-compiler-install.log`, `pillow-linux-no-compiler-install.log`. Fresh targets, `PATH`, `CC`, `CXX`, `CFLAGS`, `CPPFLAGS`, `LDFLAGS`, `PKG_CONFIG_PATH` empty; absolute interpreter/resolver; `--only-binary :all: --no-cache`. |
| Locked HNSW 0.8.0 alone, Linux target | 1 | `D/hnswlib-linux.log`: no usable wheel. |
| Locked odfpy 1.4.1 alone, Linux target | 1 | `D/odfpy-linux.log`: no usable wheel. Pure-Python source packaging is still outside a wheels-only acceptance rule. |

Successful Pillow install readback reports `cp314-cp314-macosx_11_0_arm64` and `cp314-cp314-manylinux_2_27_x86_64` / `cp314-cp314-manylinux_2_28_x86_64` wheel tags. This proves no local Pillow compilation in those attempts, not full Marker compatibility or successful CI setup.

Representative replay of the **complete default contributor dependency attempt**, from worktree root (one command):

```bash
uvx --from uv==0.9.21 uv sync --project policy-engine/_build/toolchain-inputs/original --python /opt/homebrew/bin/python3.14 --frozen --extra dev --extra test --no-install-project --no-build --no-cache
```

HNSW is a base dependency. In the complete 5,761-file tracked-Python denominator above, 11 files mention hnswlib; `U/hnsw-census.json` enumerates 10 static import sites in 8 source modules plus the dynamic availability probe. Active producers build academic/catalog/legal/OpenAI-shard indexes. Knowledge-store vector consumers and `VectorMemoryStore` need those indexes; missing HNSW raises rather than transparently substituting equivalent retrieval. Moving it out of base requires source/install migration and a capability decision. That is the blocking boundary, not permission to silently delete the requirement.

`D/lock-wheel-inventory.json` additionally enumerates every package record in the pinned lock: 416 total, 415 registry records, of which 9 have no wheel entries (autograd-gamma, hnswlib, odfpy, osqp, pillow, regex, rpy2-rinterface, ruptures, stochtree). This is a **lock-record inventory**, not nine independently demonstrated CI failures or a claim that each package's entire upstream history lacks wheels. The install receipts above establish the failures actually exercised. Further packages of this class belong to the same wider dependency-install limitation; no source-build exception was used to manufacture a green result.

### Follow-up scope and exact workflow handback

`team-devx` needs an architect-backed decision for the non-wheel base capabilities before claiming the stated full-install closure. The measured isolation candidate is the preferred starting proposal if preserving Marker as an opt-in branch; it remains local scratch pending that decision. Replacing the Marker adapter, dropping HNSW, or pretending its fallback is equivalent is outside this diff.

No workflow change is needed merely to stop selecting table-extraction: active CI already does not select it. When a future complete wheels-only repair is verified, remove the entire step named `Install source-build system headers` from these exact workflow jobs:

- `.github/workflows/honest-diagnostics-substrate.yml`, job `fast-pr`.
- `.github/workflows/policyos-canary-matrix.yml`, job `deterministic-canary-matrix`.
- `.github/workflows/policyos-canary-matrix.yml`, job `live-provider-canary`.

Each removal includes its comments, `if`, `run`, `set -euo pipefail`, `sudo apt-get update -qq`, and `sudo apt-get install -y -qq libjpeg-dev zlib1g-dev`. Remove the same complete named step from `.github/actions/setup-policy-engine-python/action.yml` once validated. This is the full header-step set in the 12 workflow YAML + 3 action YAML denominator, not a sample. **No removal was made now**, because the production lock still needs the existing workaround.

## Delivery boundary

Only this required journal is a tracked change. The installed-mechanism states of both rows remain blocked as classified above. Local scratch retains the full measurements; production closure probes and code changes remain with the stated owners. Commit locally, read the journal back from the attached branch, verify the final path set and clean status, and stop before push.

Independent read-only review reconciled the journal against both rows' retained evidence. Corrections preserve the workflow template's existing `--project` argument, qualify the fixture's endpoint-only byte comparison, and include the existing cloud install-mode conflict. `git diff --cached --check` passed. A normal local commit attempt exited **1** because the checkout-local Lefthook dispatcher requires an absent dashboard `node_modules/.bin/lefthook` (`D/commit-attempt.log`). No dashboard installation or hook repair was attempted in the parallel lane's tree. For this journal-only handback, retry the commit with a command-local `-c core.hooksPath=/dev/null`; repository hook configuration remains unchanged. The frontend hook suite has no passing receipt here.
