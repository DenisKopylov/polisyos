# Independent review: pytest process-environment capture patch

**P40 bucket: `SAME_CLASS_DEEPER`.** The original gap is that the child-process sidecar does not establish the actual process environment and loaded dependency provenance. This patch adds those fields at the shared pytest-session boundary, but the dependency-name-to-version join still does not prove that the loaded file belongs to the named distribution. This is one deeper provenance/completeness class; it calls for widening the join at that boundary, not another per-package exception.

## Exact inputs and review method

This was a read-only review of the unapplied patch and its exact target bytes. No patch was applied; no pytest, product command, package import, or heavy workload was run.

| Input | SHA-256 |
|---|---|
| `LOCAL/raw/composed_mac_pytest_origin_plugin_process_environment.patch` | `3f7bfb90023af612f6c3060f6945c26febbb5f7a5f0acf38c92aef4e6d62fec2` |
| Target `LOCAL/raw/composed_mac_pytest_origin_plugin.py` | `b1920931f4a31ef2561874e0f076f4683e45462123290a26afaab26f862f9298` |
| Wrapper `LOCAL/raw/composed_mac_capture.py` | `894300665556ef644ffffb67ab2dc0508ff4e7f8d840bf256bb199c885889087` |
| `LOCAL/emit_proposals.py` strict environment validator | `4d5e70c67f62af07cdb7d3313ad3caa2a689172888b44051c13bb07e6dbbacec` |
| Patch note `LOCAL/r4-workload/final-process-environment-capture-patch.md` | `7022e5b6148432550352f9966727df602b977957ad889ee217204ab7f94ac498` |
| Readiness contract `LOCAL/crosswalk/final-wave-environment-capture-readiness.md` | `983a681f6ad5b28bfff06e09f3916695ea435bce665851604906316cab8746fe` |

## Assessment

The runtime, executable, prefix/base-prefix, platform, and twelve allowlisted environment values are read inside the pytest child at `pytest_sessionfinish`. This is the right process boundary for those observations. The patch does not import scientific libraries; it inspects `sys.modules` and uses `importlib.metadata`. The existing `polisyos`/`tools` origin assertion is left unchanged, and the plugin continues to write a PID-specific create-once sidecar.

There is one blocking property gap before any emitted dependency row can be treated as a verified package/version pair. At patch lines 100–105 and 136–148, the collector joins an import root to `packages_distributions()`, checks that its selected origin is somewhere under either configured `purelib` or `platlib`, then marks the version resolved when the metadata mapping names exactly one distribution whose `version()` call succeeds. It never checks that the selected origin is among that distribution’s files or under that distribution’s own installed file set. A loaded `shadowpkg.py` from the site-packages tree can therefore be attributed to a different distribution whose metadata claims `shadowpkg`; the row becomes `origin_status=resolved` and `package_version_status=resolved` although the loaded code is not supplied by that distribution. `packages_distributions()` is a name mapping, not an origin-to-distribution ownership proof.

The related inventory boundary has the same class. A filesystem-backed non-internal import root is silently omitted at lines 102–106 if it is outside the two configured site roots and has no metadata mapping. Since the final status at lines 168–177 considers only emitted rows, that loaded root cannot force `partial`; an otherwise successful capture can report `complete` without establishing that every relevant external root was either resolved or explicitly left unresolved. This matters if a future receipt builder projects rows with resolved status into the strict profile.

The smallest distinguishing source-level falsifier is a loaded root whose `__file__` lies under a configured site root while the sole mapped distribution’s file inventory does not contain that origin: the current predicate reports a resolved origin/version; the truthful outcome is unresolved and aggregate `partial`. A second falsifier is a filesystem-backed external import root outside the site roots with no distribution mapping: it is absent from the emitted list and does not affect `complete`; for a whole external-import inventory claim it must be represented as unresolved or the claim’s scope/status must explicitly exclude it. These are counterexamples to the same provenance/completeness invariant, not separate path-specific findings.

To close that invariant, bind each selected module origin to the candidate distribution’s actual installed file inventory (for example, a normalized `Distribution.files`/`locate_file` match); only then may a sole distribution version be marked resolved. Preserve unmapped or unowned non-internal roots as unresolved evidence, or explicitly narrow the status name and strict-profile contract to the subset being measured. Retain the current fail-closed behavior for namespace/multi-origin and multi-distribution cases. Do not infer ownership solely from import-root text or site-root membership.

## Consumer boundary and limits

The proposed sidecar is useful evidence but does not itself create the strict environment manifest. The current wrapper’s `check_module_origin_receipts()` reads each receipt’s local `assertion`, checks the PID, and hashes the file; it does not inspect `process_environment` or reject a partial dependency-capture status. The strict validator requires a separate exact-shape manifest and nonempty `loaded_import_origins` rows of `{module, origin, package_version}`. The patch note correctly leaves that projection/bridge pending. Therefore the capability remains **bridge missing / verification missing** for the strict profile until the receipt builder validates the child fields, refuses unresolved status, and binds the strict manifest to the exact receipt bytes and selected command.

Independent code assessment only; this review makes no G acceptance or formal closure decision. There is no claim here that the final frozen source, full candidate run, or strict environment profile has been verified.

## V3 delta review

**P40: `SAME_CLASS_DEEPER`.** This is the same loaded-origin ownership/completeness class. V3 responds to the remaining name-map coverage limitation by deriving owners from one generic installed-file inventory, rather than adding package-specific candidates or exceptions. Review scope is the declared unit: one observed origin per loaded top-level import root, with each loaded module name under that root retained. I did not require a second per-submodule closure mechanism.

Exact v3 inputs:

| Input | SHA-256 |
|---|---|
| `LOCAL/raw/composed-plugin-origin-ownership-v3.patch` | `b7ec25da08a2f7fb222b8071048b984cbdeede0f8a68d4327b4395cfa85e6719` |
| Target plugin, unchanged from v2 | `787f22ff049d36d897c58707fd70bc115b9e8e01b707803f42e3797d66f02fa2` |
| `LOCAL/r4-workload/composed-plugin-origin-ownership-v3.md` | `f03b6c879f66b12f63adbe519b73b2ac7cd54fdba1ebb1dd50a1882002df986a` |
| Review file before this append | `6deadc3c2516cbbbba8ad25247791c639a40e9d96398bc23dd0cf0f2e67fba06` |

The v3 source delta removes `packages_distributions()` from ownership decisions. `_installed_distribution_origin_index()` enumerates the installed distributions and their `files`, normalizes each `locate_file()` result, and indexes the actual metadata records by path. A loaded origin gets an owner only when its path has exactly one record across the complete enumerated inventory and that inventory completed without issues. Missing file inventories, failed enumeration/locate calls, duplicate owners, or missing distribution names keep the whole inventory or row unresolved. The inventory counts are dynamic; they are not tied to the author's reported 248-distribution environment.

The module census retains file-backed origins outside the product source and standard-library roots as external rows, whether or not they are under `purelib`/`platlib` or have a package-name mapping. Namespace/mixed-root modules retain their observed path set and cannot become a single-file owner. The `_virtualenv` bootstrap-like path described in the note therefore remains an unresolved row when no installed distribution file owns it; a namespace directory such as `opentelemetry` cannot be collapsed into one owner. Unresolved roots or a partial distribution inventory prevent aggregate `complete`. Built-in/frozen, non-filesystem, source-tree, and standard-library names are represented in their separately named categories.

I traced the proposed falsifiers through the exact changed predicates; they were not executed. A false name mapping cannot create a record at the selected origin path, so owner and package version stay `not_established`. An off-site unmapped file origin is kept in `loaded_external_import_origins` and makes the aggregate non-complete. A unique exact file record with a mismatching available RECORD hash or size gives `record_integrity_status=mismatch`, which prevents a resolved package version. Conversely, an exact owner with a nonempty installed version, readable origin, and matching available RECORD facts reaches the resolved branch. The patch does not import scientific packages or hash package payloads while building the inventory; content reads are limited to selected loaded origins.

I found no remaining blocker in the v3 ownership/census mechanism for the declared top-level-root scope. Where RECORD facts are absent, the sidecar retains `not_available` and the actual origin SHA-256; the resulting claim is installed-file-path ownership plus the installed distribution's version metadata, not signed upstream-wheel authenticity. The strict environment-profile bridge remains pending and must require the complete sidecar/inventory status, not cherry-pick resolved rows from a partial capture. `loaded_source_module_names` still supplies names rather than per-file source-origin bindings; those must be established by the independent frozen-source and existing origin checks. No patch application, test, pytest/product process, Git operation, or G/formal closure action occurred.

## V2 delta review

**P40 remains `SAME_CLASS_DEEPER`.** The v2 patch widens the same process-provenance mechanism at the shared session boundary. The review remains scoped to its declared external-import unit: one observed origin per loaded top-level import root, with all loaded submodule names recorded. It does not require a new per-submodule mechanism or recursively verify a generic census.

Exact v2 inputs:

| Input | SHA-256 |
|---|---|
| `LOCAL/raw/composed_mac_pytest_origin_plugin_process_environment_v2.patch` | `4d8047b8270470a58673a1891e55c61623ad1951918c0f87307e2e73d36ec25b` |
| Target plugin, unchanged | `b1920931f4a31ef2561874e0f076f4683e45462123290a26afaab26f862f9298` |
| `LOCAL/r4-workload/final-process-environment-capture-patch-v2.md` | `4d02b5c82bf4f600e5cbdb41b317142de06b92f6fa4ad9988e3138b684fb30e8` |
| This review before the v2 append | `ec087aaeaa47bc89d423efe9998d4e5eeedb711a894f61fcb9d1abaa7294ee42` |

On source inspection, v2 addresses the v1 blocker for that declared scope. Each loaded root is grouped from the actual module table; source, standard-library, built-in/frozen, and non-filesystem entries are classified separately; every other filesystem-backed root is retained as an external row. A missing distribution mapping or an off-site origin therefore cannot disappear from the external inventory: it has no unique owner/version, and the aggregate status is not complete. The row records all loaded names under that root while explicitly scoping its single origin observation.

Candidate distribution names are now only candidates. For each, the patch enumerates `Distribution.files`, resolves entries through `locate_file`, and requires exactly one normalized path match to the selected loaded origin. It hashes the readable origin bytes and compares any available RECORD hash and size; mismatches or malformed available facts prevent a resolved package version. It also requires a single matching owner, all candidate inventories to be inspected, a nonempty version, and a readable selected origin before setting `package_version_status=resolved`. Ambiguous origins and unmapped roots remain unresolved. No scientific package import was added, and the original `build_origin_manifest()` product-root assertion remains unchanged.

I traced the three author-provided, unexecuted falsifiers through those predicates. A candidate distribution whose inventory contains only a different file yields zero exact matches and no resolved owner/version. An off-site, unmapped file-backed root is retained with no candidates and makes aggregate capture partial. A matching owner with a selected-origin RECORD hash/size mismatch has `record_integrity_status=mismatch` and cannot resolve the package version; matching available facts take the resolved path. This is source-level reasoning only; no probe or test was run.

I found no remaining blocker in the v2 external-root ownership mechanism under its declared one-origin-per-root scope. The process-environment patch remains unapplied, so this is not execution evidence. The strict-manifest bridge is still missing: the wrapper’s current receipt checker does not validate these fields, and the strict assembler must admit only an actually `complete` capture and bind the resulting profile to the exact child sidecar and command. The v2 `loaded_source_module_names` field is a name census, not by itself a source-origin binding; source modules must continue to be grounded through the frozen source manifest and applicable origin checks. No G acceptance or formal closure is implied.
