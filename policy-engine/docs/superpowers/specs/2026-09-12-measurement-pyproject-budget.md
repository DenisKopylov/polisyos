# Measurement plane Stage1 — pyproject budget (row 5)

**Stage1 research only; root implementation decision pending.** This work is confined to rows 4–5. No source/config changes, pruning, branch/index/commit mutations or push. Root serializes shared Git and any later implementation; at most three workstreams. No row-3 model/helper ownership decision is made here. The two prohibited register/ledger documents were neither opened nor cited; their generator belongs to root.

Source baseline: `307dabcb47bcc0e7659529344d0648cafb840a30` (`307dabcb4`). Session attachment was read back at `/Users/deniskopylov/polisyos/.worktrees/measurement-plane/policy-engine`, branch `codex/measurement-plane`, HEAD `42c09a7a46ac7ec42e39e4cc19a259a10b2c8811`; the delta from baseline is three row-1 documentation files, with no source/config delta. Product-relative source citations below mean `policy-engine/<path>@307dabcb4`. Current Git registrations are explicitly time-bound observations, not facts backdated to that commit.

Raw receipts: `docs/superpowers/journals/measurement-plane/rows45/raw/`; already ignored by `policy-engine/.gitignore:149`. Complete deciding stdout/stderr and failures are retained, not truncated into findings. Raw artifact hashes are in `receipt-index.json`. Exploration failures (wrong guessed tool directories) are retained and superseded by the complete census; they support no absence claim. Every lexical query used case-insensitive matching. AST claims use parsed definitions/calls, not text embedded in logs.

## Decision and measured finding

**MP5-D01 — recommendation, not an implemented fix:** root should relocate only the existing Hatch build configuration at `pyproject.toml@307dabcb4:285–307` into a canonical root `hatch.toml`, translating `[tool.hatch.build…]` to `[build…]` and preserving its values. All 23 physical lines can leave pyproject; the predicted remainder is **307 − 23 = 284**, below the unchanged 300-line ceiling. This is a real configuration-home move. Do not raise the ceiling, add an exception, compress comments/blank lines to satisfy a proxy, or migrate project metadata. Established backend support is described in MP5-F04; repository integration still requires the companion changes and tests below. No config was written or relocated in Stage1.

**MP5-F01 — unchanged gate reproduced.** The actual registered invocation:

```sh
.venv/bin/python -B -m tools.cli validation repository-structure-phase0 gate --gate pyproject_size --json
```

exits **1**, `status=FAILED`, `complete_verdict=true`, `finding_coverage=complete`, with one `pyproject_size_gate` warning, 307/300. Complete output is `pyproject-size-gate.json` (2.266 seconds observed). `tools/quality/validation/repository_structure_phase0.py@307dabcb4::collect_inventory` (252; physical count at 418–419), `gate_pyproject_size` (749) and `main` (1161) establish input → count → finding → CLI outcome; the AST also shows the `GATE_FUNCTIONS` bridge. `architecture/gates/structure_remediation.toml@307dabcb4` finding/defect `section-0-6-pyproject-size` and gate ID `pyproject_size_gate` name **team-devx**, with registry governance under team-architecture. The all-gates consumer is `tests/repo_quality/architecture/test_repository_structure_phase7_closeout.py::test_phase7_structure_gates_run_fail_closed_with_registered_exceptions`; it is a test caller, not a claimed production scheduler. The registered developer CLI and gate registry are the non-test terminus.

The supplied baseline guardrails zero and root ledger 260/no blocking/two shifts are coordination context, not a fresh verification by this workstream. The size gate's reproduced red is a different explicitly selected predicate. No ledger tool was run and no prohibited document was read to justify a finding.

## Complete physical partition and two denominators

**MP5-F02.** Denominator one is exactly `pyproject.toml@307dabcb4`, **all 307 physical lines**, independently counted by `bytes.count(b"\n")` and text `splitlines()`; the file ends in a newline. Every physical line belongs to one section below, including comments and following blank lines. The block sum is 307, not a sampled tail. Receipt: `pyproject-physical-blocks.json`; file SHA-256 `2b6247dc9ca57e33e171ba52dff73544ade16e45fa0f2f8134dbf98ee98a48f5`.

| Section | Lines | Physical count | Consumer / decision |
| --- | --- | ---: | --- |
| `[build-system]` | 1–4 | 4 | PEP 517 frontend → Hatchling; retain |
| `[project]` | 5–51 | 47 | Installed distribution metadata/base deps; retain |
| `[project.optional-dependencies]` | 52–207 | 156 | uv/pip extras graph; retain |
| `[project.scripts]` | 208–215 | 8 | Console entry points and invocation roots; retain |
| `[dependency-groups]` | 216–225 | 10 | uv dev/ci dependency groups; retain |
| `[tool.uv]` | 226–228 | 3 | uv project conflict relation; retain |
| `[tool.uv.sources]` | 229–233 | 5 | uv local odfpy source binding; retain |
| `[project.entry-points."polisyos.fabric_connectors"]` | 234–247 | 14 | Connector entry-point metadata; retain |
| `[project.entry-points."polisyos.scientist_governance_passes"]` | 248–271 | 24 | Governance-pass entry-point metadata; retain |
| `[project.entry-points."polisyos.foundry_methods"]` | 272–274 | 3 | Foundry entry-point metadata; retain |
| `[project.entry-points."polisyos.scientist_nodes"]` | 275–278 | 4 | Declared extension group and comments; retain |
| `[project.entry-points."polisyos.data_forge_domains"]` | 279–280 | 2 | Declared extension group; retain |
| `[project.entry-points."polisyos.lex_normpacks"]` | 281–282 | 2 | Declared extension group; retain |
| `[project.entry-points."polisyos.runtime_middlewares"]` | 283–284 | 2 | Declared extension group; retain |
| `[tool.hatch.build.targets.wheel]` | 285–287 | 3 | Hatch wheel package selection; move |
| `[tool.hatch.build]` | 288–290 | 3 | Hatch output directory; move |
| `[tool.hatch.build.targets.sdist]` | 291–307 | 17 | Hatch sdist include policy; move |

Denominator two is the complete **tracked product-root source/config search population**, independently reconciled by `git ls-files -z` against `git ls-tree -rz --name-only 307dabcb4`: **8,754 identical paths**. It includes `.py/.pyi/.toml/.ini/.cfg/.yaml/.yml/.json/.sh/.mjs/.cjs/.js/.ts/.tsx/.bash` and Dockerfile-named files; excludes documentation/journal trees and the two prohibited basenames. Distribution: 5,869 Python, 5 PYI, 517 TS, 719 TSX, 38 MJS, 9 CJS, 5 JS, 45 SH, 228 TOML, 11 INI, 1 CFG, 84 YAML, 54 YML, 1,168 JSON, 1 Dockerfile.reproducible. Total 8,754. All 5,869 Python ASTs parsed; no read/parse failures. The whole product has 12,872 baseline tracked files and 12,875 at HEAD (the three row-1 docs explain the delta); this is not an all-filesystem or all-language semantic completeness claim.

The case-insensitive lexical query returns 102 source/config reference files. **102 is a candidate-reference count, not 102 runtime consumers**: snapshots, copied schemas, examples, test data and prose literals are distinguished. `pyproject-consumer-search.json` retains every hit; `owner-ast-definitions-calls.json` and `consumer-function-call-closure.json` identify actual definitions/calls. `inspect_rows45.py` is the replay script. Supplementary case-insensitive read of the worktree's repository-level workflow files is retained in `workflow-pyproject-search.json`; those YAML files are outside the product-only 8,754 denominator. Dynamic or external consumers not represented in these source sets remain outside the static proof.

## Exact consumer seams and move breaks

**MP5-F03 — relocating metadata would change the product.** Keep `pyproject.toml` as the canonical metadata file. These are actual consumers, not a claim that every lexical hit reads it:

| Source at `307dabcb4` | Definition / load and dependency |
| --- | --- |
| `tools/lib/imports.py` | `_REPO_SENTINELS` includes pyproject; moving the file changes repository-root discovery. |
| `tools/registry.py`; `tools/cli.py` | `_discover_specs` → `ToolSpec`; `_make_category_group` → `_make_tool_command`; pyproject `[project.scripts]` installs `polisyos-tools = tools.cli:main`. |
| `src/polisyos/runtime/quality/production_invocation.py` | `_read_tree:503` explicitly obtains pyproject from the selected Git tree and consumes script entry points as invocation roots. Removing scripts destroys that evidence seam. |
| `tools/quality/validation/decomposition_preflight.py` | `_entry_point_targets:256` parses `project.entry-points`; `_dynamic_notes:329` consumes its result. |
| `tools/quality/validation/check_extension_examples.py` | `_validate_entry_point_coverage:184` compares declared extension groups; `main:458` runs it via validation. Empty declared groups are not disposable blank configuration. |
| `tools/quality/validation/fabric_best_in_class_inventory.py` | `_build_surfaces:788` calls `_fabric_connector_entrypoints` with pyproject selected by `_paths:341`. |
| `tools/quality/validation/repository_best_in_class_phase0_7_inventory.py`; `repository_last_mile_inventory.py` | `_collect_extension_points:474` → `_load_pyproject:235`; `_collect_entry_point_example_gaps:1005` reads project entry points. |
| `tools/quality/lint/lint_legacy_cutover.py` | `_check_entrypoint_groups:79` reads the declared file to reject legacy groups. |
| `tools/ops_runners/release/check_release_version.py` | `main:35` parses `project.version` at 42–43; package-version ownership must remain there. |
| `src/polisyos/foundry/methods/catalog/dependency_profile.py` | `resolve_dependency_discriminant:741` checks exact pyproject bytes against the owner digest at 762–775, then parses `project`; `resolve_dependency_profile:862` consumes it. A semantically equivalent build-config move still changes the byte digest. |
| `tools/devx/foundry/sync_dependency_profile.py` | `_regenerated_owner_bytes:173`, `_run_diagnose:246`, `_run_regenerate_owner:289` own diagnosis/reissue. Reuse this owner, do not hand-forge accepted hashes. |
| `tools/quality/validation/check_layer3_gy_value_gate_contract.py` | `_resolve_frozen_foundry_dependency_discriminant:945` passes frozen pyproject bytes to the dependency owner; frozen artifacts must retain their historical identity. |
| `src/polisyos/runtime/quality/confidence_ledger.py` | `_deployment_relative_paths_from_closure:4501` includes pyproject and uv.lock in deployment identity; changes legitimately invalidate previous deployment-bound evidence. |
| `tools/ops_runners/runtime/canary_evidence.py`; `replay_canary_bundle.py` | `_dependency_fingerprints:4563` hashes manifests; replay lists pyproject among bundle inputs. Reissue only through their existing ownership rules. |
| `tools/devx/workspace/doctor.py`; `tools/devx/architecture/guardrails.py` | `_check_lockfiles` invokes `uv lock --check`; `_prepare_isolated_probe_environment:1535` invokes frozen sync. They require valid package/build discovery on the actual copied tree. |
| `Dockerfile.reproducible:35,95`; `ops/cloud/gcp/package_repo.sh:27` | Two explicit Docker copies and the deployment archive include list currently carry pyproject but no hatch.toml. Relocation must carry the new config into each build/deploy context. No claim that these historical Python-3.11 Docker recipes are otherwise healthy. |
| `tools/quality/validation/repository_verification_inventory.py` | `_inventory_pytest:725` reads pyproject as one signal, alongside pytest.ini; this does not make pytest config movable again. |

Data carriers (dependency-profile refs in DTOs, frontend clients and schema snapshots), test fixtures and historical inventory JSON are not extra file-reader definitions. Root must follow the existing reissue commands for live digest owners and retain frozen/historical evidence. This Stage1 does not authorize an indiscriminate regeneration of snapshots.

## Canonical tool homes and established relocation

**MP5-F04.** `architecture/tooling/tool_config_split.toml@307dabcb4` (`tool_config_split`, owner `team-devx`) and `tools/devx/workspace/tool_configs.py@307dabcb4::render_files` already own only mypy/Ruff/MkDocs generation. Ruff root stub extends `architecture/tooling/ruff/generated.toml`; mypy root `mypy.ini` is the base and repository commands pass `architecture/tooling/mypy/generated.ini`; MkDocs root inherits `architecture/tooling/mkdocs/generated.yml`. Standalone `pytest.ini`, `basedpyright.toml`, `mutmut.cfg`, and `uv.toml` are already present. None of the 307 physical lines belongs to those moved lint/test configurations. Extending the generator to synthesize package metadata would add an unnecessary second authority.

| Alternative home | Result / move break |
| --- | --- |
| `hatch.toml` | **Selected:** canonical native Hatch build configuration. Move all three related build sections together; no new generator. `build-system` and `project` stay in pyproject. |
| Existing `uv.toml` | Holds `cache-dir` today. `conflicts` and `sources` are project-resolution inputs, not generic cache settings. Their supported project home is pyproject; equivalence in uv.toml is not established. Do not delete or relocate the local odfpy binding or conflict relation to win eight lines. |
| Existing Ruff/mypy/pytest/etc. homes | Already extracted; no remaining block to move. Do not invent a duplicate tool section. |
| `setup.cfg`, `setup.py`, requirements files | Not a semantic drop-in for PEP 621 metadata, extras or entry-point groups; these homes are explicitly denied by `architecture/topology.toml`. |
| Generated pyproject from fragments / dynamic metadata hooks | Adds a producer and stale-artifact bridge, disrupts existing byte-hash and metadata readers; excessive for a 23-line supported build-config move. |

The official [Hatch build configuration](https://hatch.pypa.io/latest/config/build/) documents native `[build.targets…]` in hatch.toml while retaining `[build-system]` in pyproject. At the declared minimum backend version, [Hatchling 1.27.0 ProjectMetadata](https://github.com/pypa/hatch/blob/hatchling-v1.27.0/backend/src/hatchling/metadata/core.py) reads pyproject in `config` (156–165), and loads adjacent hatch.toml into Hatch configuration in `hatch` (215–238). Its builder consumes `metadata.hatch.build_config`; `SdistBuilder.get_default_build_data` force-includes the native config. Complete pinned upstream source is retained as `hatchling-1.27.0-*.txt`. The loaded configuration merges at the top-level Hatch keys, so move the entire `build` tree together to avoid partial override loss. This is a source-established compatibility seam; Hatchling was not importable in this lane's venv and no build/install was run in Stage1.

The [uv settings reference](https://docs.astral.sh/uv/reference/settings/) presents `conflicts` and `sources` as project settings; the [configuration-file reference](https://docs.astral.sh/uv/concepts/configuration-files/) also documents precedence of uv.toml for general settings. Neither justifies blindly transplanting these project tables into generic configuration. Their behavior must stay unchanged here.

## Root implementation package and falsifiers

**MP5-D02 — finite proposed edits, after Stage1 readback.** Mechanism paths are `pyproject.toml` (remove only 285–307), new `hatch.toml` (same three sections using native names), `Dockerfile.reproducible` (both copy lists) and `ops/cloud/gcp/package_repo.sh` (archive include list). Explicitly include `hatch.toml` in the moved sdist include policy for readability even though Hatchling also force-includes its native config. This preserves the original listed source/include policy and adds the newly necessary config file.

Mandatory integration companions: `architecture/topology.toml` and `architecture/policies/directory_health.toml` must admit the new canonical root config; focused packaging tests should mirror under `tests/repo_quality/tools/`; workspace/dependency documentation should identify the new home; root's plan/journal plus live dependency-profile owner outputs and any tests pinning changed constants/hashes must be updated through their owners. These are excluded from a mechanism-path budget under P39; never split one move to satisfy an invented cap. The ceiling constant, gate mode and exception registry remain unchanged. Existing scanner/generator ownership is reused; root adjudicates actual downstream reissue scope before writing governed artifacts.

Acceptance (proposed; not claimed run):

1. Through the real Hatchling backend, compare effective wheel packages, build output directory, sdist inclusion policy, project metadata, dependencies/extras, console scripts and extension groups before/after. Source wheel membership must be identical; sdist must differ only for the necessary new config and its corresponding metadata-file bytes. Rebuild a wheel from the extracted sdist and compare installed metadata/entry points. Real declared package/config paths are the denominator, not one toy file.
2. Run the real registered size gate: 284/300 is the exact expected result if no other pyproject text changes. Pin 300 unchanged. TOML parse success alone is not build equivalence.
3. Negative: omit hatch.toml from a copied build context while preserving pyproject and success markers. The packaging test must detect lost package/output/include behavior or backend failure. Negative: leave the old `tool.hatch` table prefix in hatch.toml; the test must catch fallback/default behavior. Negative: alter `packages` or drop a console/extension entry point; metadata/member comparison must fail.
4. Run existing dependency-profile diagnosis; unchanged old byte digests must be rejected after the move. Reissue live owner declarations with `polisyos-tools foundry sync-dependency-profile` through its actual diagnose/regenerate-owner modes, respecting frozen historical evidence. Retain a corrupt-field drift that must fail; do not merely replace a hash until a checker turns green.
5. Verify copied Docker/deployment archive contexts include the native config; ensure topology/directory-health accept it. Run `workspace tool-configs --check` to demonstrate unrelated generated tool config remains unchanged, plus focused importer/config tests, Ruff and architecture guardrails. Root reserves its full backend/CI parity for the post-review closeout wave.

## The predicate we have versus the one we might want

**MP5-F05 (analysis only).** The implemented predicate is `physical_lines <= 300`, including comments and blank lines. It measures **size, not complexity**. Removing seven comments can make it green without changing configuration meaning; one compact dependency list can be small and expensive to resolve. Conversely a well-separated manifest can be long without being hard to understand. The current gate already discloses those limits, so do not describe a complexity proof or weaken the ceiling in the name of honesty.

A better maintainability analysis would distinguish canonical-home ownership, effective parsed configuration, project/build contract preservation, duplicated settings, dependency-graph fanout and actual resolver/build cost under a fixed environment. Each requires its own measurable denominator and acceptance evidence; no replacement scalar, threshold or additional authority-grade gate is proposed here. The selected Hatch move addresses an established mixed-home seam while preserving the declared size constraint.

## Pattern pass and capability state

P35: all physical lines partitioned; source/config population reconciled twice with file-type denominator; AST calls separated from serialized references. P37: line count is `recomputed`; section classification/config-home choice is reviewed analysis, not self-authorizing evidence; actual relocation equivalence is `not_established` until backend/packaging tests. P38: physical size versus complexity divergence is explicit (MP5-F05), and parse success versus build equivalence has concrete falsifiers. P39: mandatory integration/reissue/test/docs companions stay outside a mechanism cap. P01/P02/P29: real packaging producer, copied artifact, installed consumer and metadata/member negative are required, not a contract-only move.

The existing size instrument is implemented and reproduced. The proposed relocation is `verification_missing` and `semantic_test_missing` until root builds/readbacks it; copied-context propagation would be `bridge_missing` if omitted. A dashboard/API is `surface_out_of_scope`; the package, installed commands and existing developer gates are its surfaces. This document is a recommendation and an analysis receipt, not a delivery/closure claim.

## Stage 2 disposition

Native Hatch config is committed at `eb41d689f`: pyproject is 284 physical lines
under the unchanged 300 ceiling. Docker/GCP packaging contexts carry hatch.toml;
topology permits that canonical config. The real Hatchling 1.27.0 backend produced
identical 3,406 wheel members excluding RECORD across both configurations; among
7,438 native sdist members the permitted delta is hatch.toml and pyproject.toml.
The sdist rebuild preserves the wheel. These counts describe the disclosed
7,457-file build context used in that run, which excludes the two forbidden
governance documents, not the entire repository. Missing/wrong config, package
omission and entrypoint removal fail equivalence. Missing/non-file enumerated
members now fail explicitly, with two red/green probes.

The unchanged size gate passes 284/300 and rejects the 301-line control. The
existing dependency-profile owner writer regenerated its paired declarations;
the current check passes and corrupt-field drift rejects altered bytes. No
complexity predicate was added; the predicate analysis above remains analysis.
Full receipts and diagnostic limitations are in the completion journal.

Mandatory generated companion reissue at `eed7a68e6` also updates the OpenAPI
confidence-ledger-risk-spend example's consulted source-dependency receipt. The
entire delta is within that example; endpoint/DTO contracts are unchanged. This
binding covers the changed source/test input basis, not just pyproject bytes.
The registered freshness gate verifies the real owner-generated output.
