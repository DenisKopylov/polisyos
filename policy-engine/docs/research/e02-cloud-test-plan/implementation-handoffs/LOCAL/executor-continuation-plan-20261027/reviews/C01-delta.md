# C01 independent delta review

**Code GO for root composition and native verification.** The sparse repair closes C01-R1 through one unique named-row intake. No new blocking correctness or scope finding was identified in this delta. This is a static source decision; runtime remains **UNRUN / verification_missing**, and this review does not grant G27-01 acceptance or B13 closure.

Reviewed input: `LOCAL/raw/e02-execution-20261027/repairs/C01/manifest.json`, the three exact postimages it names, and `candidate-to-repair.patch`, against cloud candidate tree `ed17cc148eec3a9da75d1f6dc371967667166e17` / slice base `8db01b1076e425b7998b05a658776c991b7bd594`. Canonical HEAD was observed as `a8021d8aee165e6f9618d19c78a6f93104844bea`; canonical product files were not used as repaired postimages. No source, index, refs, runtime state, or native checks were changed or run.

## C01-R1 disposition

**Addressed in source, SAME identity/relevance class.** The property is: derive the selected node metadata and the complete set of relevant same-ID refs from one unambiguous persisted named node; refuse ambiguity or an unestablished relevant binding before exposing a result.

- Repaired `debug.py:376–379` calls `_unique_workflow_report_node`, then derives metadata with `_workflow_node_record(report_node)`. Ref extraction at `:395–398` receives that same raw `report_node`. The former first-ref-row / last-metadata-row split is removed.
- `_unique_workflow_report_node` (`:2659–2687`) traverses the complete node collection before returning. A second matching alias refuses regardless of the refs: A/A, A/B, B/A, malformed, profile omission, or an empty ref collection cannot select competing rows. A node whose alias relevance cannot be established also refuses. A valid distinct alias remains unrelated.
- `_artifact_refs_from_report_node` (`:2690–2715`) traverses the selected row's artifact collection. Every parsable ref is retained. Malformed same-ID refs and malformed refs whose ID relevance cannot be established refuse; a well-established distinct ID remains unrelated.
- The only relevance filter before identity comparison is artifact ID. There is no kind/media/profile filter that could discard a same-ID conflict. `_require_exact_artifact_ref_binding` (`:2718–2730`) still uses the existing `artifact_ref_identity_key` owner to compare ID, kind, media type, and exact profile presence/absence for every same-ID ref. This is not a fourth comparator or an enumerated type list.
- The `_workflow_node_record` extraction preserves the previous metadata projection for ordinary workflow views; the G27 reader now consumes it from its admitted unique row. Selected CAS-profile resolution, integrity, tenant, schema, payload validation, and candidate-only response semantics remain wired after binding checks.

This widens the mechanism to the named-row set that the property actually needs. No actual remaining divergence was found between the bounded G27-01 property and this intake/identity implementation. Hypothetical future fields or a recursive verifier are not blockers under P29/P40.

## Portable HTTP fixture

**Static GO as a declared controlled program fixture, with execution pending.** The delta uses existing repository owners and does not manufacture a production-grounding claim.

`simulation_result_api_env` in the repaired `test_debug_api.py:512` calls the unchanged `tests._helpers.candidate_cycle_source_profile.build_candidate_cycle_catalog_serving_source`. That helper calls `data_forge.read_api.catalog.build_slice0_fixture_catalog_graph`, which delegates to the catalog domain's real graph builder with committed fixture DatasetRecords. It closes the created graph and renames its owner-created database to the selector's required fixed-layout filename; it does not import production bytes or rewrite table contents. Its `CatalogServingSourceSelection` is explicitly candidate-only, selects `preflight_core`, and is resolved/read back against the actual database path.

The fixture passes that selection plus `_build_registry_providers(catalog_run_profile=selection.catalog_run_profile)` into the normal RuntimeContainer. The container reconciles profile and selection, supplies the selected source to the real ControlPlaneService, and the service opens the selected real DatasetCatalogGraph. The registry's fixture source/binding/model/connector descriptors are declared test program inputs used for runtime composition, not an assertion of external evidence authenticity. No DebugService, runtime API context, CAS reader, retrieval service, signature verifier, promotion owner, or grounding/admission result is overridden by this delta. The actual debug run still goes through the app's scoped runtime store, tenant scope, fixture view-owner registration, RunContext persistence, run-index refresh, and HTTP GET.

The unchanged supporting files were checked against the complete candidate tree with `git diff --name-only ed17cc... HEAD -- <five exact support paths>`: `tests/_helpers/candidate_cycle_source_profile.py`, `tests/_helpers/runtime_http.py`, `src/polisyos/runtime/quality/substrate_registry.py`, `src/polisyos/runtime/http/container.py`, and `src/polisyos/runtime/http/app.py`; the result was empty. The reviewed supporting code therefore matches the candidate tree for that stated five-file denominator.

## Defining checks to run under the root resource lease

**These commands were not executed by this reviewer.** Preserve the repository pytest config/plugins, a supported locked native Python environment, the complete source topology, and canonical physical test paths. Use full isolated trees with the repaired HTTP test bytes; do not run a sparse physical test path or reuse an editable installation pointing at another source tree. The direct regression module imports renamed repair helpers and is therefore not a valid unchanged old-source red selector: on old source it would fail import rather than witness the property.

1. **Original G27-01 old red:** complete slice-base source `8db01b1076e425b7998b05a658776c991b7bd594`, with only repaired `test_debug_api.py` overlaid. From its `policy-engine/` directory:

   ```sh
   uv run --frozen --extra runtime --extra test pytest tests/unit/runtime/http/test_debug_api.py::test_simulation_result_http_requires_exact_identity_for_every_same_id_node_ref -q -ra --junitxml=LOCAL/c01-base-http.xml
   ```

   Expected defining sequence, conditional on successful setup: `same_ref_default` and `same_ref_explicit` first establish HTTP 200 with the selected A identity and row0 node metadata; then `node_only_valid_b_default` fails because old code exposes HTTP 200 where the oracle requires 409. A setup/collection failure or an earlier A/A failure is not the intended red.

2. **C01-R1 old red:** complete cloud candidate source `ed17cc148eec3a9da75d1f6dc371967667166e17`, with repaired `test_debug_api.py` overlaid. From its `policy-engine/` directory:

   ```sh
   uv run --frozen --extra runtime --extra test pytest tests/unit/runtime/http/test_debug_api.py::test_simulation_result_http_requires_exact_identity_for_every_same_id_node_ref -q -ra --junitxml=LOCAL/c01-candidate-http.xml
   ```

   Expected first C01-R1 failure, conditional on all earlier checks reaching their intended outcomes: `duplicate_alias_same_ref_default` exposes 200 rather than required 409. The two A/A positive selectors occur before any A/B or duplicate refusal assertion. The HTTP matrix is one looping pytest test, so retain the complete failure output identifying the first failed case rather than attributing one pytest case to every table entry.

3. **Repaired new green:** complete source composed with the exact three repair postimages. From its `policy-engine/` directory:

   ```sh
   uv run --frozen --extra runtime --extra test pytest tests/unit/runtime/http/test_debug_result_profile_identity.py tests/unit/runtime/http/test_debug_api.py::test_simulation_result_http_requires_exact_identity_for_every_same_id_node_ref -q -ra --junitxml=LOCAL/c01-repaired-defining.xml
   ```

   The full repaired `binding_cases` literal was statically enumerated: fourteen case rows times two selector forms, or twenty-eight declared HTTP combinations in this one test (`test_debug_api.py`, Python-file denominator one). The direct suite includes duplicate A/A, A/B and absent-profile rows in both orders, and unestablished-alias refusals. A green run would cover the original seven binding rows and seven added ambiguity rows through both selectors; currently none of these new runtime observations is claimed.

After a defining green, the affected extraction consumer check is the full bounded debug API module plus the direct module on the same repaired source:

```sh
uv run --frozen --extra runtime --extra test pytest tests/unit/runtime/http/test_debug_api.py tests/unit/runtime/http/test_debug_result_profile_identity.py -q -ra --junitxml=LOCAL/c01-repaired-affected.xml
```

Run the agreed property-removal control in isolation while retaining success/ref/error markers, and preserve complete output. Exact-profile removal must make the A/B oracle fail; unique-row refusal removal must make the duplicate A/A oracle fail. These remain required executable evidence, not work performed by this review. Native lint/format and applicable architecture verification must also run on the final composed topology; sparse stdin lint reports are not substituted for that final receipt.

## Integrity, boundaries, and closeout

A read-only SHA-256/length walk covered every manifest entry: all three Python postimages and both patch files match their declared hashes and byte lengths. The final postimage hashes are `fad42cfc4c30f2f91bf7b1e4eff3fa4e0a68a7d6c8347e8047aabf8cecf9df3b` (debug.py), `d97bca6c776ad77e57d3ac9055a90c6df0973d676966ab708c7e79fca4eb38ad` (test_debug_api.py), and `d624fd8205a9be80cc672aae50951c58de78968122ca0ab06be1ce8cc5fa835e` (direct regression). The repair manifest's AST/Ruff results are author-supplied static evidence; this reviewer independently inspected source and digests without rerunning native checks.

The old C01-R1 source HOLD is superseded only for these exact repair bytes by **code GO**. Root product composition and fresh runtime verification are still necessary before acceptance. The cloud HTTP/removal/architecture evidence limitations from the first review are not silently upgraded. The failure/repair register was reopened during this delta review; P29/P31/P32/P37/P38/P40 continue to apply, and no B13 common-basis invalidation bridge is included.
