# Architecture export and facade decision — 2026-10-10

## Immediate disposition

A narrow additive fix is ready as a proposed patch at `LOCAL/raw/architecture-companion-export-resolution-proposal.patch` (SHA-256 `47c9fc41cc6a27fd5488d4dffc35311ceb56ca46a0633ef6b7ae9cd8fd33be15`). It adds `CatalogRunProfile` to the existing `polisyos.core.contracts.__all__`, pins the real lazy-facade object identity with a focused test, documents the export, and records the Python API addition in a release fragment. The patch is not applied. It changes no production logic, type values, serialized schema, architecture allowlist, or generated inventory.

This is the routine existing-entrypoint case: `polisyos.core.contracts` is already listed as a supported stable entrypoint. `CatalogRunProfile` is a `Literal` declared in `control.py` and is already present in the facade's `.control` lazy-symbol map, so attribute lookup works; the explicit public `__all__` omits it, so declared/wildcard surface membership is incomplete. The proposed regression test imports through both the supported facade and defining module, then checks membership and object identity. This verifies the export behavior rather than just its source marker.

## Exact source basis

Candidate checkout: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`; HEAD `dc3071e8c700adda56fdc33eba90bdcce33db275`, tree `6469ee340b21a07dc16f3dc0c93473195e630336`. Relevant current byte fingerprints:

- `src/polisyos/core/contracts/__init__.py` `0657d75eb8c5b5568e730b40097a5bb9a59b0e26828eadf1418dbcf2300ccfdd`
- `src/polisyos/core/contracts/control.py` `a2cc9c46829147a9f3b72796987e7aae61b09e2af81556d8e5e08e2778f3959d`
- `src/polisyos/core/contracts/README.md` `1df86638e2521db73ca6c65d8a25004832d29a26a4449d2dacace1a535e0cde5`
- `tests/repo_quality/architecture/test_public_surface_export_resolution.py` `c256fd69a52502adf79d2a3e7f8b02c87fd8f9b843ca87b84b7e0d47786b8c79`
- `architecture/public_surface/contract.toml` `14ae5db4c9f137e2d5b434fd1cdf259151216e7952b50da04218754eef3bdce6`
- `architecture/public_surface/inventory.json` `9e4bdbf3772894f335512c2afd7f27cc03e206475790c0338a74feedabc3b924`
- `docs/reference/public-surface.md` `c6dd74692dbd798b5bd44d21f81e5af71c81edeb220d03f07430785dad00422f`
- `architecture/imports/policy.toml` `f1fd15ac0b8c66126570b51b04da6201f11bd3372ecd0826924bad06ca31637d`

The supported-entrypoint rule is exact: the public-surface contract says any module path not listed is internal by default; `polisyos.core.contracts` is listed. The missing name is already wired in `_MODULE_SYMBOLS[".control"]`; the change only makes it part of the facade's explicit export list.

## Broader architecture result and bounded decision

The complete 475-edge deep-import residual and source-route census were already recorded in `LOCAL/decisions/architecture-companion-defect-triage-20261010.md` (current file SHA-256 `6fb110a42aee41ed85c25b568cc7e7afd3f8fb9c36b32e175b8a00c7bb7a6dac`), with the original full command output retained under `LOCAL/raw/r3-architecture-iteration-20261010/`. That earlier census measured 3,716 current edges versus 3,330 baseline edges (475 additions, 89 removals), spanning 215 source modules/files and 126 target modules; all observed package-root direction pairs were allowed by `architecture/imports/policy.toml`. These figures are cited as that prior pinned census, not newly replayed in this narrow patch-only pass.

P40 classification is **SAME class, one level deeper**: the residual is still public-route/import completeness after existing facade routing, not a new dependency-direction class. The exact route census grouped the 475 additions as 175 exact module-object routes, 121 descendants of those routes, and 179 with only their nearest formal supported FQN. This does not authorize blanket migration or widening the public contract. The existing `core` README describes lazy module facades while `contract.toml` lists exact Core entrypoints. Whether module-object routes such as `polisyos.core.artifacts` and `polisyos.core.canon` are supported independently, or only as attributes reached through `polisyos.core`, is a G/API-owner choice. Preserve the existing contract and import findings pending that choice; do not add a prefix wildcard, sync the deep-import baseline, or claim those 475 rows are closed.

The public-surface inventory currently records 20 packages and 38 entrypoints, all 38 unresolved by the conservative source analyzer. `core.contracts` is unresolved because its `__all__` uses the starred `_CHRONOLOGY_EXPORTS` expression. This is not an empty export set and not a generated-format defect: the current `inventory.json` and reference Markdown byte-match the renderer. The patch leaves those generated files untouched and does not treat one missing name as a parser repair. A safe static `Starred`-tuple/list parser extension remains a separate candidate prototype; it must keep the inventory incomplete when other import-time forms cannot be resolved and must not infer runtime binding solely from a declaration.

G choice still required for broad module-object-route semantics. The smallest discriminator is a source-derived route removal probe: remove a real `__getattr__`/module-object binding while leaving README/contract markers intact; a generic route checker must stop treating the path as routed. Until semantics are selected, the bounded residual is the complete 475-edge set already cited above, with actual per-source route binding unresolved for the 179 formal-only rows. No formal architecture finding or G decision is closed here.

## Verification and limits

This is a proposal artifact only. No product source, test, contract, generated artifact, release fragment, or Git object was modified; the diff itself contains four proposed paths. The behavior assertion is intentionally narrow and deterministic. The patch was not applied and no test/formatter was run against proposed bytes. Current inventory hashes are cited as unchanged source inputs, not as proof of a generated-surface update.

## Current-head source-derived census refresh

I refreshed the census against the current candidate HEAD after the narrow CatalogRunProfile export companion and receipt-only advancement. This supersedes the earlier source-head pointer in this packet for the route count; it does not change the bounded API decision.

- Candidate HEAD/tree: f52809e8210714131f53c7b90bd53a9215c69d69 / ecd5be2042d666dc4668aa995faea30bf119dd5a.
- Product cwd: /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine. Command: env PYTHONPATH=src:. .venv/bin/python docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/architecture-route-prototype-20261010-f52809/route_census.py; exit 0, Python 3.14.3, stderr 0 bytes.
- Captured command record: LOCAL/raw/architecture-route-prototype-20261010-f52809/command.json; stdout SHA-256 c2b65dcca9bf0dd35730027e67f131b342c5dcc71cf85a1a011b1300b35243e1; empty stderr SHA-256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.
- Census script SHA-256 48387aa534ae8d7aa945fc735cdece566d8a4b619f4d68a823fd1f31d1b796f7; complete result LOCAL/raw/architecture-route-prototype-20261010-f52809/deep-import-census.json SHA-256 12a1d04c0d5fa005b7ea1f8733d7984bd553b8fdf89194ae08ec3537f38e1157; complete source manifest LOCAL/raw/architecture-route-prototype-20261010-f52809/source-py-manifest.json SHA-256 c849eccfd8f9f6f95f73a91427c580ab2098de5284c9f6bdf5337d29480a4244.

The denominator is all 2,748 .py files under policy-engine/src/polisyos, excluding __pycache__, using the same iterator as guardrails._iter_py_files(). The imported guardrails module and polisyos package resolved to this candidate product tree. The pinned current input hashes are in the census JSON. It records all 475 added edge keys, all 519 import sites with source path and line, the 215 source modules/files, 126 target modules, and all 34 observed root-to-root directions. All 34 directions are allowed by the current import policy. This is the complete row set, not a sample or a grep-derived count.

The source-derived classifier starts from actual module-object bindings evidenced by literal route declarations plus their implementation: the finite subpackage/surface names and the matching getter, direct import, or explicit branch. It assigns each added edge to an exact module-object route, a descendant beneath the nearest such route, or—only if neither exists—a descendant of the nearest formal supported entrypoint. Current counts are **175 exact module-object routes, 121 descendants, and 179 formal-entrypoint-only edges** (475 total). The census includes the full route list and source path/binding for each match. These counts describe runtime source routes; they do not add prefix wildcards or make the 32 discovered module objects public API.

The selector-loaded distinction is source-bound. Four modules—academic, catalog, legal, and ukraine—are entries in the literal READ_API_SURFACES tuple at src/polisyos/data_forge/read_api/surfaces.py (source SHA-256 91f36c51abc9db63546785d511a8fc757720938ab873d30d14302345a6ef4bd1). src/polisyos/data_forge/read_api/__init__.py has the guarded __getattr__ path that calls load_surface(name); load_surface resolves the declared module through get_surface(name).module and import_module. The source-derived rows bind **14 exact added edge keys / 20 import sites** to those four modules through READ_API_SURFACES → load_surface → __getattr__. Their row-by-row source paths, lines, imported names, and destination module are in the complete census JSON. This is the 14-route increment that the declaration-only count missed. It is evidence of actual selector-backed module routes, not a decision that each destination is independently ratified as an API entrypoint.

The marker-preserving removal probe is behavioral. For polisyos.core.artifacts, the actual route resolves before mutation and imports src/polisyos/core/artifacts/__init__.py. The probe removes only the source __getattr__ function from an AST copy while retaining __all__ and _SUBPACKAGES; the source-derived candidate then disappears and real attribute access returns AttributeError. The complete probe record is module_getattr_marker_preserving_removal_probe in the census JSON. It proves the classifier is tied to a live binding rather than README/__all__ marker presence; it does not ratify the unlisted module FQN.

The safe literal-star prototype reads src/polisyos/core/contracts/__init__.py (SHA-256 263a140bdce75e6e9ce2f6c6b31c3bff43b8c0a91a26fb886f59e6e8e8341e6e). It expands only a starred local name bound to a tuple/list of string literals, and accepts string literals; it performs no eval, import, or callable execution. It yields **643 unique declaration candidates**, with no duplicates, but runtime_binding_count=null, complete_runtime_inventory=false, and current guardrails still report an unresolved export expression and export_count=null. This is a parser prototype, not evidence of 643 runtime bindings or API support. The current inventory must remain unresolved until source-to-runtime binding is separately established.

**P40 bucket: SAME class, one level deeper.** The additional selector-backed paths are a deeper instance of the same public-route/import-completeness class, not a new import-direction class. The complete 475-edge packet and its source locators are now refreshed against the exact current head. Preserve the per-edge distinction and keep broader module-object/FQN support semantics as an explicit G/API choice. Do not close findings by matching markers, widening an entrypoint prefix, or syncing the 475-edge baseline. This review makes no formal architecture-finding or G closure.


### Scope note for the earlier proposal status

The earlier “proposal artifact only / patch not applied” paragraph above is scoped to its then-current snapshot and should not be read as describing this refreshed HEAD. Current HEAD f52809e8210714131f53c7b90bd53a9215c69d69 contains CatalogRunProfile in the core.contracts facade symbol map and __all__ (source file SHA-256 263a140bdce75e6e9ce2f6c6b31c3bff43b8c0a91a26fb886f59e6e8e8341e6e; current lines 202 and 1506). This census records those exact current bytes; the refreshed census did not execute the companion's tests or make a formal API/finding closure.
