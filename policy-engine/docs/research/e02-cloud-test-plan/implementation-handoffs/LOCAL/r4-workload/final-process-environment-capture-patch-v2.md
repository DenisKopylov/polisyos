# Pytest child process capture patch v2

This is an unapplied patch artifact at `LOCAL/raw/composed_mac_pytest_origin_plugin_process_environment_v2.patch`, SHA-256 `4d8047b8270470a58673a1891e55c61623ad1951918c0f87307e2e73d36ec25b`. It targets `LOCAL/raw/composed_mac_pytest_origin_plugin.py` at SHA-256 `b1920931f4a31ef2561874e0f076f4683e45462123290a26afaab26f862f9298`; the target file is unchanged. The v1 patch remains preserved at `LOCAL/raw/composed_mac_pytest_origin_plugin_process_environment.patch`, SHA-256 `3f7bfb90023af612f6c3060f6945c26febbb5f7a5f0acf38c92aef4e6d62fec2`.

## V2 change

At the existing pytest child `pytest_sessionfinish` boundary, the proposed addition records the child PID, Python implementation/version/executable/prefixes, platform, the approved non-secret environment-variable allowlist, and loaded module names. It does not import scientific packages. Existing `build_origin_manifest` behavior and the `polisyos`/`tools` product-root assertion are unchanged.

For an already-loaded external top-level import root, package-name metadata is treated only as a candidate list. The proposal opens each candidate with `importlib.metadata.distribution`, enumerates its installed `files`, resolves each with `locate_file`, and requires exactly one normalized absolute installed path to equal the observed origin. A version is emitted as resolved only with a unique exact file owner, a nonempty distribution version, and a readable hash of the selected origin. When installed RECORD hash or size metadata exists, the selected file is checked against it; unavailable RECORD fields are labeled `not_available`, while malformed metadata or mismatches do not resolve the package version. The content read is limited to the selected loaded-origin file, not a package-wide scan.

The collector includes filesystem-backed non-internal roots even when they are off-site or have no package mapping. Such roots remain explicit unresolved rows and make the aggregate capture `partial` or `not_established`. Namespace or other multiple-origin roots remain unresolved. Source-tree modules are classified separately for binding to the independently frozen source manifest; built-in/frozen and standard-library module names are separately recorded. The claimed external scope is one observed origin per loaded top-level import root, with all loaded submodule names recorded; it does not claim complete per-submodule provenance.

## Strict manifest boundary

The strict manifest must project an external row only when the exact row has resolved origin, unique installed-file ownership, and package-version statuses. It must also require the **whole** `loaded_external_import_capture_status` to be `complete`; selecting only resolved rows from a partial capture cannot establish completeness. Internal source rows must bind to the frozen source/input identity, not a guessed package version. A strict receipt builder must bind its manifest to the exact child sidecar bytes and selected command. That bridge is not implemented by this patch: the current `check_module_origin_receipts()` does not consume these fields, and the strict environment manifest remains unqualified until a reviewed bridge performs those checks.

## P40 and falsifiers

The independent v1 finding is `SAME_CLASS_DEEPER`: joining an import name to `packages_distributions()` and a site root did not establish that the loaded file belonged to the named distribution, and it omitted unmapped off-site roots. V2 widens the same boundary to actual installed-file membership and explicit unresolved-root accounting; it does not add package-specific exceptions.

The following are concrete, unexecuted in-memory falsifiers for review:

1. A loaded `shadowpkg` origin at `/tmp/site/shadowpkg.py`, mapped to `unrelated-dist`, where `distribution.files` resolves only `/tmp/site/unrelated.py`. The candidate name and version are present, but no exact origin-file match exists. V2 must leave ownership/version unresolved and aggregate capture partial. Removing the exact membership condition while keeping the candidate mapping and version must make this falsifier pass incorrectly.
2. A filesystem-backed `orphanpkg` origin outside source, standard-library, and configured site roots with no package mapping. It must still appear as an unresolved external row and prevent aggregate `complete`. Omitting it while retaining all other rows must make the falsifier fail.
3. A loaded origin that is exactly one candidate distribution's installed file, with a nonempty version and matching available RECORD hash/size, should resolve. A mismatched or malformed available RECORD fact must prevent version resolution.

The patch artifact was produced from the exact target bytes. It was not applied; no pytest, product command, test, scientific import, or heavy workload was run for this v2 task. The v1 review and strict validator inputs remain `LOCAL/reviews/composed-plugin-process-environment-independent.md` at SHA-256 `ec087aaeaa47bc89d423efe9998d4e5eeedb711a894f61fcb9d1abaa7294ee42`, and `LOCAL/emit_proposals.py` at SHA-256 `4d5e70c67f62af07cdb7d3313ad3caa2a689172888b44051c13bb07e6dbbacec`.
