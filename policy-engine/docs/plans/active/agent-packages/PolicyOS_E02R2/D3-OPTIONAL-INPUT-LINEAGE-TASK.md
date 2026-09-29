# Proposed engineering task — D3 optional-input lineage and resume currentness

**State:** design reviewed with conditional GO; open P40 class; no production code is implemented by this task artifact. The measured class concerns data identity and replay. It does not authorize promotion, publication, source-time claims, or a new acquisition path. Employment and macro are instances of one input-lineage class. LA-031 remains a separate held import/registry-parity finding.

## Property and reproduced witness

For a D3 run, every normalized source byte or presence fact that can affect an output is part of the persisted run basis. The builder consumes the same run-scoped resolved snapshot whose content and presence records were persisted. A resume reuses a completed run only when the current resolved snapshot matches that historical basis.

The independent controlled probe uses two local D3 roots with the same five declared refs. The real D3 stage completes in both; omitting normalized `employment_service` changes three of ten semantic output hashes and changes `labor_validation_overlap_rows` from 2 to 0, while `BuildRunManifest.inputs` remains equal at five refs. `labor_bias_validated` remains false in both runs. This is a real candidate-computation/input-lineage discrepancy; no production data is involved and no authority consequence is measured.

- Probe output: `/Users/deniskopylov/.codex/scratch/e02-la031-d3-implementation-20260929/optional-probe-v2.json@sha256:b0c89a52af4f965279e72e273f1c5de679b0e5956e946224eb795440a708c9a8`.
- Probe code: `/Users/deniskopylov/.codex/scratch/e02-la031-d3-implementation-20260929/probe_d3_optional.py@sha256:2c4687f204445d1d0483f4691d3579f1561821b2a76780e2e84c7f787349790e`.
- Behavioral review: `/Users/deniskopylov/.codex/scratch/e02-la031-d3-implementation-20260929/OPTIONAL_INPUT_LINEAGE_REVIEW.md@sha256:15b0d29eb438c1ec2fbf72a3d6abf573c704041b7694cbb72fe7dbc35e4d9566`.
- Independent design review: `/Users/deniskopylov/.codex/scratch/e02-la031-d3-implementation-20260929/OPTIONAL_INPUT_LINEAGE_INDEPENDENT_REVIEW.md@sha256:bff3b0b15c69a4ff5d6944d0d937e0bc8847fe3c94c0aeded5a12e3e2c922532`.

## Audited producer-to-consumer path

The production caller is `ukraine-data build --stage d3/full --resume` / `ukraine-data resume d3`, entering `UkraineDataOrchestrator.build_stage` and the registered `build_d3_stage` through `builders/__init__.py`.

1. Existing upstream normalized-data producers write source files and `NormalizedArtifactManifest` / `ArtifactRecord` evidence. This task consumes those outputs through their current owner; it does not add fetch, admission, or storage behavior.
2. `StageConfig.required_sources` in `models.py` currently drives which source records the orchestrator materializes into `BuildRunManifest.inputs`. The present D3 denominator contains five inputs: `household_microdata`, `labor_force_microdata`, `pfu_debt`, `wage_arrears`, and `distress_events`.
3. The registered D3 builder also conditionally reads `employment_service` and `macro_nbu_derzhstat` through the existing normalized-source helpers in `builders/io.py` and calculations in `builders/demography.py`. These bytes are outside the five recorded refs.
4. D3 also checks `land_cadastre` and `logistics_mobility_displacement` presence to choose skipped-source manifest outputs. Those presence facts can change output bytes and must either enter the typed dependency snapshot or be removed from output selection; otherwise declare a bounded residual.
5. `BuildRunManifest` in `manifests.py` persists the selected input records and output records. The current resume fast path in `orchestrator.py` can return on `completed` status plus output-path existence before it resolves the current source snapshot. Therefore merely adding optional records to `required_sources` would not close the class.
6. The Ukraine read API parses `BuildRunManifest` and publishes the bytes in CAS under schema version `1.0`. If the persisted manifest shape changes, this is a real consumer: revise its schema metadata and prove v1 acceptance plus v2 admission. Do not update metadata if the route is not part of the final changed contract; establish this from the consumer census.

The exact owner files and source pins at independent review were:

| Owner surface | Tracked path | Reviewed source SHA-256 |
| --- | --- | --- |
| Stage inputs | `policy-engine/src/polisyos/data_forge/domains/ukraine/models.py` | `236a5610c3644d43a1cee2e50a83be6f4a01cfea015463ae23781f1d73792854` |
| Persisted run manifest | `policy-engine/src/polisyos/data_forge/domains/ukraine/manifests.py` | `a3d9e4ad8b16fb7d4acae5b2613fe1c416509bbb5de597f005033ed2ea703bcf` |
| Build lifecycle and resume | `policy-engine/src/polisyos/data_forge/domains/ukraine/orchestrator.py` | `0fbf635d93f73c84db0c81cc24d94449862c86799f77ddaaaaa73c55e427eeeb` |
| Stage input contract | `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/contracts.py` | `52705ddd2b7a3645d628a31dc633e831fb79b81e884e43645a77fe93b7ca8ad1` |
| Normalized-source read boundary | `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/io.py` | `82c39eca03b9f784ea5cd5282143824113c956b15ed023a186e67378bd345c7c` |
| D3 calculation consumer | `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/demography.py` | `99a21ee2576adc669a32788fe84876fe2bcbea961864595ba75f5fb42b3a42bb` |
| Registry/bridge | `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/__init__.py` | `84b1cbe7e6cf00fa76403e597f0e5e519810030c481f5fca4bdabf30b3c29951` |
| Manifest consumer, if still in contract | `policy-engine/src/polisyos/data_forge/read_api/ukraine.py` | `1d23266e6881fc23c8d9e0cce5786d47a3a1978046ffe62e452d9a561e5abfb2` |
| Current behavioral fixture | `policy-engine/tests/unit/data_forge/domains/ukraine/test_orchestrator.py` | `971486f95ff5139708c11d517d3fa11b2d7a64ed2e1050a4e404760ab818a1d3` |

The upstream manifest is a claim to check, not the byte source of truth. Recompute a content digest from the bytes actually handed to the D3 builder and verify it against the upstream `ArtifactRecord`; if a file changed without a matching manifest refresh, preserve the recomputed digest and a typed manifest-mismatch limitation rather than accepting stale metadata. Do not reopen the path independently after admission: resume comparison and the D3 builder must consume one snapshot.

## Owner-first mechanism

Extend, do not duplicate, the current owner chain:

- Declare D3's exact required, optional, and presence-only inputs in one typed stage-input contract, separate from the list that controls upstream fetch/skip semantics.
- Extend the existing normalized-source read owner in `builders/io.py` to return both the frame used and a typed input record: `source_id`, source stage, actual-byte digest, and one of `present_verified`, `present_manifest_mismatch`, or `absent_optional` with a reason. A present but unverified manifest is not the same as absence. It remains candidate-usable only with a declared limitation; malformed data can fail for its concrete parsing/computation reason.
- Have `UkraineDataOrchestrator` create one run-scoped resolved-input snapshot. Use it both for D3 builder dispatch and for resume equivalence, including optional presence and skipped-source selections. Never issue an upstream acquisition just because an optional source is requested by the D3 contract.
- Persist the complete consumed-input snapshot in a versioned `BuildRunManifest`. Compare it before the resume early return. Legacy v1 runs without a complete basis are stale/rebuildable, not silently current. Preserve exact historical v1 serialization/readback and add v2 admission. If the read API consumes the new form, update its CAS schema metadata and its v1/v2 reader tests.
- Keep source time coverage, measurement validity, jurisdiction, and owner appointment as typed unknowns. This work binds content and presence only. Missing time contract/data is recorded in `OPEN_PREMISES.md`, not converted into a refusal of ordinary candidate computation.

The same class covers `employment_service`, `macro_nbu_derzhstat`, and any sibling D3 input found by the complete census. Under P40, macro is a second instance, not a second repair round. If a sibling read still bypasses the shared snapshot after one mechanism is added, stop patching sites: widen the shared mechanism or name the smallest missing capability and run its falsifier.

## P37/P38 statement

- **P37 predicate:** complete set of current D3 output-affecting source bytes and presence facts. Today it is `not_established`: the persisted `required_sources` set is incomplete relative to builder reads and source-presence-based outputs. After repair, byte identity and presence can be `recomputed` from the shared snapshot; source-time and measurement validity remain `not_established` or require owner-issued evidence.
- **P38 divergence:** required property is “resumed D3 outputs correspond to all current input bytes/presence consumed by the prior D3 run.” Current implementation tests only `completed` plus output paths before source resolution. Divergent example: with the five declared refs unchanged, toggling the optional employment-service file changes three output contents and an overlap metric.

## Write lease proposal

One writer, one candidate, with this exact initial lease:

- `policy-engine/src/polisyos/data_forge/domains/ukraine/models.py`
- `policy-engine/src/polisyos/data_forge/domains/ukraine/manifests.py`
- `policy-engine/src/polisyos/data_forge/domains/ukraine/orchestrator.py`
- `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/contracts.py`
- `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/io.py`
- `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/demography.py`
- `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/__init__.py`, only if the registry must pass the resolved snapshot
- `policy-engine/tests/unit/data_forge/domains/ukraine/test_orchestrator.py`, after its committed LA-031 lease
- Add `policy-engine/src/polisyos/data_forge/read_api/ukraine.py` and `policy-engine/tests/unit/data_forge/read_api/test_ukraine_stage_artifacts.py` only if the read API consumes the versioned manifest

No `cli.py`, generated family, acquisition arm, production-data file, or storage-owner changes are in this lease. Any source beyond the lease requires a reviewed lease amendment before editing. The `test_orchestrator.py` path is currently clear of LA-031's candidate after commit; other writers must not edit it concurrently.

## Acceptance and falsifiers

Selectors below are proposals; they are not present or run yet.

1. **Employment positive/rebuild:** `tests/unit/data_forge/domains/ukraine/test_orchestrator.py::test_d3_optional_source_lineage_is_content_bound_and_resume_rebuilds_when_changed`. Starting from the pinned fixture, mutate employment bytes at the same path, retain/reforge an upstream normalized manifest whose claimed digest is stale, invoke the actual `resume=True` caller, and require a new D3 manifest with the digest recomputed from consumed bytes and the expected output change.
2. **Macro positive/rebuild:** add a sibling selector that changes `macro_nbu_derzhstat` values at the same path, checks the bound input record and macro-derived output/metric change, and proves resume rebuild. This is the same P40 class and must pass through the shared snapshot owner.
3. **Marker-retaining removal:** retain `completed`, output paths, source IDs and presence markers while removing only the resume content/presence equality predicate. A same-path changed source must make the positive selector red. Separately remove the typed absence record while preserving the empty-frame fallback; the absence assertion must turn red.
4. **Candidate preserving control:** with both optional D3 sources absent, the real D3 stage completes with typed `absent_optional` limitations and a real D4 registry execution still emits `d4_governance_request.json` with its existing purpose-limited fields. It must not invent a governance verdict, coverage threshold, or waived signoff. Candidate work proceeds under the limitation.
5. **Other output-affecting presence:** include `land_cadastre` and `logistics_mobility_displacement` presence facts in the same persisted input snapshot if they continue to select D3 skipped-source manifests; otherwise prove the output selection no longer depends on unrecorded presence. Do not declare the source set complete while this is unresolved.
6. **Historical/read surface:** read each committed v1 fixture/manifest and prove byte-exact historical serializer replay. If the read API consumes v2, prove v1 and v2 admission and schema metadata at that consumer. Re-read served CLI outputs through the owner path.
7. **Attribution:** run the full touched test files at the required pinned bases after freeze; classify environmental or inherited reds before carrying them. A metadata-shape-only selector is insufficient.

## Preserving data/contract boundaries

The probe uses controlled local fixture roots only. `production_data` remains read-only and need not be copied for this task. If a real-data check becomes useful, it must use the existing symlink, read-only access, and per-job scratch outside the data tree.

No source-time contract currently defines compatible periods for the five required D3 sources or the optional inputs. That contract is a typed open premise for the data/source owner: this task may identify exact byte content and period labels already present, but it cannot claim temporal validity or cross-source comparability. Lack of that contract does not block implementing content-based currentness or testing the synthetic 2025-12 fixture. Do not convert this uncertainty into a global refusal.

## Pattern pass and closure boundary

Relevant patterns: P07/P08 (replay and time-role separation), P10 (semantic adequacy), P27/P31 (route through the existing source/manifest owners), P29 (behavioral evidence), P35 (enumerate every D3 read and presence selector), P37/P38 (freeze the measured gate predicate and implementation divergence), and P40/P41 (one class-level mechanism and attributed replay). Existing anti-pattern: `required_sources` is used as if it were the complete data dependency set while the builder can read optional bytes and resume can skip without comparison. Target pattern: a typed, source-complete, run-scoped input snapshot consumed by both producer orchestration and resume/builder consumers, with explicit candidate limitations and historical replay.

The task closes only the content-lineage/currentness property for D3 under the evidenced owner route. It does not resolve source-time validity, external institution evidence, acquisition policy, S8/promotion authority, or an unrelated GY/Atlas task. Keep those premises separate and continue independent engineering.
