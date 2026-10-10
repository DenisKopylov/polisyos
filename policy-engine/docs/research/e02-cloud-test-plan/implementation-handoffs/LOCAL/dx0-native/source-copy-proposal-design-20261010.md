# Native freshness source-copy proposal patch
#
# Reviewable source delta; intentionally not applied and not run. This is a proposal
# for the full input-basis class, not an apply-ready partial hunk. Do not consume the
# old Git-only copy selector as evidence.

## architecture/generated_artifacts.toml

Add typed selectors to each of the four current default native families. `source_of_truth`
remains descriptive; it is never treated as the selector. `probe_input_roots` is a complete
filesystem subtree selector for ignored/untracked inputs. `probe_required_paths` names exact
cross-root inputs whose absence or unsafe resolution makes that family `UNRUN` before copy.
All tracked paths and Git-visible untracked paths remain in the source snapshot as today.

```toml
# runtime-openapi-snapshot
probe_input_roots = ["src", "tools"]
probe_required_paths = [
  "pyproject.toml",
  "uv.lock",
  "architecture/generated_artifacts.toml",
]

# runtime-api-client
probe_input_roots = ["packages/runtime-api-client"]
probe_required_paths = [
  "schemas/runtime_api_v1.openapi.json",
  "package.json",
  "pnpm-workspace.yaml",
  "pnpm-lock.yaml",
]

# runtime-dashboard-api-types
probe_input_roots = ["apps/runtime-dashboard"]
probe_required_paths = [
  "schemas/runtime_api_v1.openapi.json",
  "package.json",
  "pnpm-workspace.yaml",
  "pnpm-lock.yaml",
]

# trust-claim-posture-register
probe_input_roots = ["src", "tools", "architecture"]
probe_required_paths = [
  "docs/system-design-decisions/policyos-identity-and-custody-boundary.md",
  "docs/compliance/A11Y_AUDIT_2026Q2.md",
  "docs/plans/active/DEBT-REGISTER.md",
  "docs/plans/active/atlas-slices/receipts/ds11-page-a11y-base/environment-after.json",
  "docs/plans/active/atlas-slices/receipts/ds11-page-a11y-base/environment-before.json",
  "docs/plans/active/atlas-slices/receipts/ds11-page-a11y-base/receipt.json",
  "docs/plans/active/atlas-slices/receipts/ds11-page-a11y-base/run-1/.last-run.json",
  "docs/plans/active/atlas-slices/receipts/ds11-page-a11y-base/run-1/results.json",
]
```

The trust-family roots include all filesystem `src/` Python/resource inputs and the complete
`tools/` and `architecture/` configuration roots. Its exact `probe_required_paths` include the
tracked 961,811-byte debt register and all five receipt files; those names are not optional
because the generic tracked walker happens to return them. The frontend family roots include
the full package source/config trees; `node_modules` remains only a typed existing dependency
link, tied to the frozen `pnpm-lock.yaml` and successful `corepack pnpm install --frozen-lockfile`
receipt. The Python root config and `uv.lock` remain selected source inputs. Include any
additional actual family root discovered by canonical owner readers before declaring the row
ready; do not edit or normalize unrelated family rows.

## tools/devx/architecture/guardrails.py

Extend `GeneratedArtifactFamily` and `_parse_generated_artifacts()` with `probe_input_roots`
and `probe_required_paths`, validating every value with `_ensure_relative()`. Defaults of empty
tuples preserve synthetic/legacy callers, but a family selected for native freshness must have
an explicit basis or its result is `UNRUN`.

Change `_copy_isolated_probe_source(repo_root, destination)` to accept the selected family
tuple and construct one union admission:

```python
tracked = iter_repository_files(repo_root)  # preserve absent entries; fail if any is missing
visible = _snapshot_git_visible_worktree(repo_root)  # same tracked + nonignored-untracked view
family_roots = filesystem_walk(each family.probe_input_roots, follow_symlinks=False)
required = union(each family.probe_required_paths)
trust_reads = actual trust compiler read receipt, when trust family is selected
```

For trust reads, call `compile_claim_posture_register()` under `measure_file_reads()` and retain
`snapshot(complete_verdict=False)`: its positive file reads add exact required inputs and SHA-256
identities, while `unresolved_by_construction` keeps imports/subprocesses distinct from explicit
reads. Reconcile every successful compiler-read path against the selected source set. Do not
turn a declaration, read receipt, or `source_of_truth` string into a completeness verdict. The
full filesystem `src/` family root is still required because imported Python modules and the
trust token walker include ignored/untracked source. Keep the collector's imports/subprocess
limitation in the native row.

For every selected path, retain provenance (`tracked`, `visible_untracked`, `family_root_filesystem`,
`compiler_read`, or `required_family_input`), resolved relative path, content SHA-256, size, mode,
and link target. A missing tracked input, missing required input, unreadable source, unsupported
special file in a family root, external/broken symlink, or escaping ancestor is a structured copy
error mapped by the existing caller to an environment `UNRUN` for every family that depends on
that copy. Do not `continue` past an unsafe untracked symlink. Validate every lexical ancestor
with `lstat` before reading it. Internal symlinks are accepted only if the resolved target is
within the product root and is also selected. Copy bytes and verify their hashes after copy.

Admit ignored/untracked descendants under the typed family roots without force-adding them to
Git and without filtering by file extension. In particular, the `src/` walk must use the same
filesystem closure as `derive_token_sources()`, not `iter_repository_files()` alone. The family
roots are the only additional ignored-input selectors; there is no blanket `LOCAL`, `raw`,
`docs`, or `production_data` copy. `.polisyos` and local data roots use their existing state/data
owner contracts. Python environments require the structural `pyvenv.cfg` plus interpreter
witness; HF caches require the `blobs/refs/snapshots` structure. A same-name directory without
the structure remains a source. A tracked or required path underneath a typed local-state
exclusion fails closed. A FIFO/device/socket inside a family root is an admission failure, not
an omitted file. The existing three `node_modules` dependency roots are explicit typed links,
not basename-wide skips.

Before `uv venv` or `uv sync`, build the child environment from an allowlist and resolve
`POLISYOS_GOVERNED_ARTIFACT_ROOT` against the original product root. If it is unset, remove the
inherited variable so the code's `__file__` fallback resolves within the copy. If it resolves
inside the product and is selected, rewrite it to the same relative path under the copy. If it
is external, excluded, absent, or unselected, return `UNRUN` before provisioning. Apply the same
rule to any current path-valued host setting consumed by a family. The trust output-probe caller
already builds a small explicit environment; keep it free of host values and use the same root
mapping helper if a caller elects to pass a governed root.

Keep disk preflight, now over the full selected source/config/resource bytes before creating the
destination. Preserve the existing output workspace/cache boundaries and node links. The
selection receipt must hash per-file content; a digest of only path, mode and size is not a
content identity.

## tests/repo_quality/tools/test_architecture_phase3.py

Replace the force-added raw-file control with an ignored-untracked source control. A real child
must open/read an ignored `src/...py`, an ignored config/resource beneath a family root, the debt
register, and every receipt member; emit content derived from those reads; and change output when
one copied property source is edited. Keep the existing tracked-source-removal control and add
missing-required-path controls proving copy/admission returns `UNRUN` before child execution.

Add independent controls for:

- ignored Python source inside `src/` is discovered and its child read is present;
- every compiler-read path is under the admitted product root and present in the copy; a missing
  debt-register member or DS11 JSON member is not replaced with an empty/default read;
- a family-root external-parent symlink, unsafe untracked symlink, internal symlink with an
  unselected target, and a FIFO in a selected root each fail closed;
- structurally valid Python/HF caches are excluded with typed provenance, while same-name
  non-cache source remains; a FIFO outside selected roots does not become a copied source;
- unset governed-root environment is scrubbed, a contained selected root is remapped into the
  clone, and outside/excluded/unselected roots produce `UNRUN` before any `uv` call;
- package-manager links remain only at the three registered roots and the package lock/install
  control remains bound;
- the child reads copied content, not source markers: remove the property while retaining
  metadata markers and prove the output/failure changes (`P29`).

Keep assertions on complete selected sets and source hashes; do not report guessed file counts or
claim a complete OS-level read audit. The focused tests are a proposal and were not run.

## Mandatory companions and root decision

The source change requires the generated-artifact manifest parser/schema, canonical generated
reference, and selector/copy behavior tests to stay synchronized. Run canonical rendering only
after source review; this proposal does not modify generated output or expiry/owner data.

The current `measure_file_reads()` collector says it does not observe imports or arbitrary
subprocess reads. The preferred current-family repair uses typed full roots plus the real trust
compiler receipt and refuses all known path-valued external settings. If the gate must prove that
arbitrary child code cannot read any absolute path outside the source copy, the smallest extra
capability is a supported OS-level sandbox with only the cloned source, explicit package
(dependency) roots, interpreter, and output/cache mounts. There is no such sandbox in this current
mechanism; without it, keep unknown external reads `UNRUN`. This is a bounded G choice, not an
expiry or authority waiver.
