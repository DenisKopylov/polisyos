# Commit, not station — instruments lane

Binding scope: the four rows in the 2026-09-07 task prompt. Base `a8d323a2f`,
branch `codex/commit-not-station`, worktree `.worktrees/instruments2`. Ordinary
local git only; no push. Neither debt register nor generated ledger is an input;
`check_debt_ledger.py` is excluded in every mode.

## Plan and pattern pass

The property is: a check's verdict depends on the commit, and the check reaches
the behavior it names. Reuse existing generators, composite setup actions and
runtime fixtures. Relevant patterns: P29/P32 (behavior, not markers), P33
(adversarial removal), P35 (complete artifact/finding sets), P38 (a version header
is a proxy for schema compatibility), P41 (measure baseline reds). No new product
capability or DS9 engineering allocation is claimed. Missing verification is
`verification_missing` until the corresponding executable evidence exists.

1. Row 1: compare freshly generated complete ABI model payloads in real git
   worktrees using Python 3.14.0 and 3.14.3, then decide manifest equality policy.
   Exercise both comparison paths and preserve detection of actual payload drift.
2. Row 2: trace every suite invocation and provider; verify the existing error
   propagation with a failing child, then provision at the shared setup boundary.
   Read production before classifying any residual assertion failure.
3. Row 3: compare wheels-only dependency routes with actual vector-search
   behavior. Preserve HNSW availability; compiler installation is not closure.
4. Row 4: reproduce the crash fixture and reservation pair; repair scaffolding
   while preserving assertions unless production proves blocked is the subject.

Parallel ownership: coordinator owns generator, manifest policy, pyproject/lock
and this journal; separate agents own dashboard setup investigation, vector
dependency investigation, and DS9 tests/services. Shared `.venv`, lockfile,
commits and generated schema outputs are serialized. Dashboard JavaScript install
has one owner. Only targeted checks; no directory-wide Python suite.

## Measurements in progress

- Setup verified branch attachment and created the requested branch at the exact
  base. A second, detached worktree at the same base is
  `.worktrees/instruments2-python3143`; no commits are made there.
- Python 3.14.0 is Homebrew macOS arm64; Python 3.14.3 was installed using
  `uv python install 3.14.3` (exit 0).
- `uv sync --offline --extra ml --extra test --extra runtime --extra lint --group ci`
  exited 1 because the locked `jaxlib==0.8.2` wheel was not cached. The online,
  frozen equivalent is being used to provision this local measurement station.
  Its source build of HNSW is explicitly not Row 3 wheels-only evidence.

## Row 1 — schema-manifest-compares-the-generating-interpreter-version

Root **(d) INSTRUMENT**. On base `a8d323a2f`, the complete verdict from
`.venv/bin/python -m tools.quality.diagnostics.gen_schema --check` on macOS arm64,
Homebrew CPython **3.14.0**, Pydantic **2.12.5**, was exit **0**:

```text
ABI schema snapshot check passed (101 models, scan_mode=full)
```

The same command from the detached base worktree on macOS arm64, uv-managed
CPython **3.14.3**, Pydantic **2.12.5**, was exit **1**:

```text
ABI schema snapshot check failed:
- snapshot out of date: /Users/deniskopylov/polisyos/.worktrees/instruments2-python3143/policy-engine/schemas/snapshots/fabric/_manifest.json
- snapshot out of date: /Users/deniskopylov/polisyos/.worktrees/instruments2-python3143/policy-engine/schemas/snapshots/ir/_manifest.json
```

Neither completed run emitted a traceback. The complete finding identity sets are
respectively `{}` and `{fabric/_manifest.json, ir/_manifest.json}`, relative to
`schemas/snapshots/`; neither is inferred from a total. Both stations were
provisioned from frozen `uv.lock`. PATH uv used for these syncs was 0.10.6;
the executors of the schema gates were the two `.venv/bin/python` binaries.
No source dependency was upgraded between these measurements.

Both stations also ran the real generator with fresh output/cache directories:

```text
.venv/bin/python -m tools.quality.diagnostics.gen_schema --output-dir .scratch/commit-not-station-row1/generated3140 --cache-dir .scratch/commit-not-station-row1/cache3140
.venv/bin/python -m tools.quality.diagnostics.gen_schema --output-dir .scratch/commit-not-station-row1/generated3143 --cache-dir .scratch/commit-not-station-row1/cache3143
```

Each exited **0**, with complete output:

```text
Generated ABI schema snapshots for 101 models (103 file updates, scan_mode=full)
```

The denominator is **every generated non-manifest `.json` file** under each fresh
output tree, independently reconciled to **every model entry in both generated
manifests**: **101/101 model paths at each station**, plus **2/2 manifests**.
The comparison parses every payload, recomputes its full canonical hash, verifies
that hash against its manifest entry, and compares both canonical and file-byte
hashes across stations. Complete differing model-path set: **`[]`**.
Both manifests differ only in **`generated_at` and `python_version`**.
The complete path/hash denominator is retained in the local measurement artifact
`policy-engine/.scratch/commit-not-station-row1/generated-payload-comparison.json`.
An independent comparison against all freshly recomputed payload cache entries
from the 3.14.3 `--check` run also agrees; it was the evidence available before
choosing the equality policy. The subsequent written-output comparison confirms it.

Decision: Python/Pydantic version headers remain provenance of the writer, just
like generation time. A common top-level manifest-content projection excludes
these three fields at **both** equality sites. The generator still recomputes and
compares the complete model payloads, full/semantic model hashes, compatibility,
generator version and all other manifest content. A version-induced schema
difference therefore stays red; equality does not imply every future supported
interpreter/Pydantic combination must produce identical schemas. Only 3.14.0 and
3.14.3 with Pydantic 2.12.5 were experimentally compared here.

The new regression cases change each provenance header separately, check a green
verdict and byte-for-byte unchanged manifest on regeneration, then change a real
transitive model field and require both the schema and manifest to be reported.
Both cases failed on the base before the repair. Post-repair targeted gate:
`python -m pytest -q tests/repo_quality/tools/test_schema_station_independence.py
tests/repo_quality/tools/test_diagnostics_phase3.py
tests/repo_quality/tools/test_phase5_tooling.py -k schema` exited **0**.
Mutation and same-commit final station receipts are recorded at closeout below.

## Row 3 — hnswlib-has-no-wheel-for-the-declared-interpreter

Disposition **blocked-and-why**, root **(d) INSTRUMENT**. No dependency changes.
The core wheels-only closure cannot be achieved by moving HNSW alone; proceeding
would change the default vector capability while leaving the requested gate red.

The existing Pillow branch was read: non-default `ci = ["pillow>=12"]` conflicts
with `table-extraction`; it was not modified. Core export with canonical uv
**0.9.21**, CPython **3.14.0**, macOS arm64, from the base dependency files:

```text
/Users/deniskopylov/.local/bin/uv export --frozen --no-dev --no-emit-project --no-hashes --output-file ../.scratch/commit-not-station-row3/core-before-pinned-uv.txt --quiet
```

Exit **0**. From the worktree root, the actual installation probe was:

```text
/Users/deniskopylov/.local/bin/uv --quiet pip install --python /opt/homebrew/bin/python3.14 --only-binary :all: --no-cache --target .scratch/commit-not-station-row3/core-before-pinned-env --requirements .scratch/commit-not-station-row3/core-before-pinned-uv.txt
```

Exit **1**, complete solver verdict (no traceback):

```text
× No solution found when resolving dependencies:
╰─▶ Because hnswlib==0.8.0 has no usable wheels and you require
    hnswlib==0.8.0, we can conclude that your requirements are
    unsatisfiable.

    hint: Wheels are required for `hnswlib` because building from source is
    disabled for all packages (i.e., with `--no-build`)
```

The same command using a scratch requirement copy omitting **only** HNSW
(`core-without-hnsw.txt`, target `core-without-hnsw-pinned-env`) exited **1**:

```text
× No solution found when resolving dependencies:
╰─▶ Because odfpy==1.4.1 has no usable wheels and you require odfpy==1.4.1,
    we can conclude that your requirements are unsatisfiable.

    hint: Wheels are required for `odfpy` because building from source is
    disabled for all packages (i.e., with `--no-build`)
```

P40 bucket: **the same dependency-artifact class one level deeper**. Instead of
further omissions, `census.py` walked the **116 exported requirement identities**,
evaluated markers (**114 selected per platform**), and enumerated every file in
every selected pinned PyPI release for CPython 3.14 macOS arm64 and Linux x86_64
tags. Both complete incompatible identity sets are exactly:

```text
hnswlib==0.8.0
odfpy==1.4.1
regex==2024.11.6
```

Both ambiguous sets are empty. Linux is a wheel-tag census, not a Linux execution
claim. Evidence: worktree-root
`.scratch/commit-not-station-row3/core-wheel-census.json`, with the enumerator and
both requirement exports beside it. `python -m census` exited **0**. Canonical uv
and PATH uv exports selected the same pinned dependencies.

| Route | Result |
| --- | --- |
| Official HNSW upgrade | Complete [PyPI HNSW](https://pypi.org/project/hnswlib/) artifact census: 11 files over 11 releases, all source distributions; latest 0.8.0. No compatible wheel route established. |
| Chroma HNSW substitution | Complete [PyPI Chroma HNSW](https://pypi.org/project/chroma-hnswlib/) census: 277 wheels among 291 files over 13 releases; none cp314/abi3. |
| Another index | No compatible macOS arm64/Linux x86_64 wheel source established in the bounded search; not a universal absence claim. |
| Explicit `vector-search` extra included by `research`/`all` | An available packaging route for HNSW, but core remains blocked by ODF and regex; not applied or claimed verified. |
| Compiler or dropping HNSW | Fails the requested closure; rejected. |

The [ODF release history](https://pypi.org/project/odfpy/) has 15 files, zero
wheels; latest 1.4.1. Regex has newer cp314 wheels, but a lock update alone cannot
resolve ODF. Selecting an alternative ODF distribution or moving additional
ingestion capability out of core is the remaining packaging decision.

Existing capability was demonstrated through production `VectorMemoryStore` and
real `FileSystemCAS`, using an already installed HNSW binary. From row 3 scratch,
`python -m vector_behavior` exited **0**: adds three cosine vectors, queries ordered
neighbors, overwrites a vector and its metadata without increasing item count,
persists to CAS and restores identical results (`north:0`, updated
`east:0.2928932309150696`, `south:2`). CAS artifact:
`sha256:820fa54f5d369bf1c0348def95f4de55431697d6c4a23ade31c8aa7fd72547ee`.
This is existing behavior evidence, **not** a fresh wheel install.

Removal witnesses retained the module/class/backend names:
`python -m vector_behavior --remove-search` exited **1**, `AssertionError: []`;
`--remove-backend` exited **1** at the production constructor with
`ImportError: hnswlib is required for VectorMemoryStore. Install it with: pip install hnswlib`.
The initial scratch report serializer could not encode `ArtifactID`; converting
that report value to `str` preceded the clean run and changed no product assertion.

Proposed incidental rows, not appointments:

- `core-odfpy-has-no-published-wheel`: proposed team-devx with the Fabric ingestion
  owner; preserve ODF ingestion while resolving packaging.
- `core-regex-lock-selects-pre-cp314-release`: proposed team-devx with the tokenizer
  owner; select a compatible release and verify tokenizer behavior.
