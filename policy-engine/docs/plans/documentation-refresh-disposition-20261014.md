# Documentation plan disposition — 2026-10-14

This is a dated review of plan locations and selected closeout records. The
membership census is pinned to `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`;
the reference scan used the current `codex/docs-refresh-e02-20261014` working
tree. The first archive/pointer batch is recorded below. E02 remains active.

## Census and denominator

The plan-tree set was enumerated with
`git ls-tree -r --name-only bafca83bff9ff49eef1466bc491a8420b5cd1dbb -- policy-engine/docs/plans`.
It contains 403 paths: `active/` 363 (300 Markdown, 47 JSON, 1 DOCX, 3 PNG,
3 Python, 3 WebM, 4 ZIP, 2 without extensions); `accepted/` 10 (9 Markdown,
1 without extension); `archive/` 28 Markdown; and 2 root Markdown files.

All 300 Markdown files under `active/` were read for front matter. The
script-derived status buckets are: 218 without front matter, 43 `active`,
4 `completed`, 4 `superseded`, and 31 with other explicit status strings
(including `active-draft`, `execution_closed`, `complete-on-branch`,
`implementation_complete_no_merge_baseline_red`, and `awaiting_owner_approval_no_implementation`).
Those strings are not one normalized lifecycle. The 9 accepted Markdown files
have 3 `accepted`, 1 `active`, 1 `report`, and 4 without front matter. The 28
archive Markdown files have 3 `archived`, 2 `superseded`, 2 `accepted`, 1
`active`, and 20 without front matter. Directory placement or a raw status
string does not settle the semantic state of a bounded item.

All four active-path `completed` labels are addressed below: Data Forge and G5
are bounded-closeout candidates; G2 and production quality remain held on
current red evidence. All four `superseded` labels are accounted for: Design
and Frontend already have pointer stubs, Atlas marketing still carries useful
DS11–DS13 material, and Repository Last-Mile has live consumer references.
The other 292 active Markdown files have `active`, other workflow, or no
front-matter status and remain in place; this census does not infer their
closure.

The complete accepted set is:

- [Repository SOTA plan](accepted/REPOSITORY_SOTA_PLAN.md) and its Phase 0–5
  files: [Phase 0](accepted/REPOSITORY_SOTA_PHASE_0_CONTRACTS.md),
  [Phase 1](accepted/REPOSITORY_SOTA_PHASE_1_DATA_FORGE_FOUNDATION.md),
  [Phase 2](accepted/REPOSITORY_SOTA_PHASE_2_DOMAIN_MIGRATION.md),
  [Phase 3](accepted/REPOSITORY_SOTA_PHASE_3_TOPOLOGY_CLEANUP.md),
  [Phase 4](accepted/REPOSITORY_SOTA_PHASE_4_GENERATED_FRONTEND_DATA_OPS.md),
  and [Phase 5 closeout](accepted/REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md);
- [Repository structure remediation plan](accepted/REPOSITORY_STRUCTURE_REMEDIATION_PLAN.md)
  and [closeout](accepted/REPOSITORY_STRUCTURE_REMEDIATION_CLOSEOUT.md).

All nine accepted files had inbound references in the full working-tree scan.
The Repository SOTA phases are referenced by repository quality tests and
closeout tooling, so this review proposes no move from `accepted/`. The pinned archive set consists of 28 Markdown paths. The delivered batch
below adds three byte-preserved historical copies; it does not rewrite the
pinned originals.

The inbound scan walked 22,693 text-like files out of 25,056 current
tracked/non-ignored paths. Its suffix denominator was: Markdown 3,307; JSON
7,225; TXT 2,334; CSV 15; TSV 6; JSONL 15 (12,902 prose/data files); Python
7,575; Pyi 5; TS 532; TSX 724; JS 4; CJS 9; MJS 43 (8,892 source files); SH
48; TOML 429; YAML 85; YML 73; JSONC 1; CFG 1; INI 11; TF 1 (649
configuration/build files); MDC 1; HTML 3; XML 199; SQL 6; Rego 23; SVG 18
(250 markup/other files). This scan treats matching content as a lead for
classification, not proof that a reference is live.

`docs/superpowers/plans/` held 39 Markdown paths at the pinned tree (README and
38 plans). Every one of the 38 plans had at least one literal inbound filename
or stem hit in the same full working-tree scan; no unreferenced plan was
identified for this disposition. Another lane is separately reviewing that
collection.

## Move proposals

The first three rows were delivered as byte-identical archive copies with
compatibility pointers on 2026-10-14. DS15 remains a conditional proposal.
Completion of a bounded slice is separate from current runtime readiness.

| Current path → proposed archive path | Classification and primary evidence | Inbound references and move shape |
| --- | --- | --- |
| [`active/DOCUMENTATION_SOTA_PLAN.md`](active/DOCUMENTATION_SOTA_PLAN.md) → `archive/DOCUMENTATION_SOTA_PLAN.md` | Candidate bounded historical plan. The [documentation inventory's Historical D6 Status Snapshot](../reference/documentation-inventory.md#historical-d6-status-snapshot), dated 2026-04-17, records the D1–D6 documentation closeout as complete on the published surface and the dedicated docs/contract/import/state-read gates as passing. The same inventory's 2026-10-14 preamble explicitly says these D0–D6 rows are historical and were not revalidated by its census. The plan's `status: active` is therefore not promoted to current documentation readiness. The current bounded successor is [DOCUMENTATION_REFRESH_20261014.md](active/DOCUMENTATION_REFRESH_20261014.md). | 32 literal-name hit files in the 22,693-file scan. Live docs and MkDocs config mentions remain resolvable through an old-path pointer. `test_repository_sota_phase3_topology_cleanup.py` checks only that the old path exists; `tools/registry.py` mentions it in generated documentation-impact text, not as a plan parser or runtime input. Four path/content receipts are historical and commit-qualified: `sources.json` records the source snapshot head `2122b1fd904a5a378416e9ac7370bbd4191dfda2` and SHA-256; two C10 manifests bind source blobs at commits `03a7c5d5…` and `e6854a70…`; the `source_disposition.json` entry is scoped to the same historical snapshot. Preserve these files unchanged. Proposed old-path stub uses the existing redirect contract fields `owner`, `target_path`, `reason`, `created_date`, `sunset_date`, and `removal_gate`; a 90-day sunset from 2026-10-14 is 2027-01-12. Keep the archived original byte-identical so the pinned bytes remain available. |
| [`active/DATA_FORGE_CUTOVER_READINESS.md`](active/DATA_FORGE_CUTOVER_READINESS.md) → `archive/DATA_FORGE_CUTOVER_READINESS.md` | Candidate bounded cutover completion. The plan names `team-data-forge`, status `completed`, and a dated [Owner Sign-Off](archive/DATA_FORGE_CUTOVER_READINESS.md#owner-sign-off): the accepted Lex artifact root was sufficient for the Phase 0 Legal cutover. The sign-off explicitly retains the reference-resolution and temporal-current-safety benchmark failures. The [Data Forge master plan](active/DATA_FORGE_CONSOLIDATION_PLAN.md) records Phase 0 complete while Phase 8 remains in shim-sunset mode. This is not a claim that all Data Forge readiness gates pass. | 11 hit files (4 Markdown, 7 JSON), including the active master-plan link and historical reports/journal. JSON source inventories and manifests are frozen provenance, not runtime consumers. No code, configuration, validator, or runtime dependency on the plan path was found in the scan. A pointer at the current path preserves the master-plan link; leave receipts unchanged. |
| [`active/layer3-slices/G5-first-proving-ground-conversion.md`](active/layer3-slices/G5-first-proving-ground-conversion.md) → `archive/G5-first-proving-ground-conversion.md` | Candidate bounded implementation closeout. Front matter records `completed`, `2026-06-10`, and `stability: closed`. Current `layer3_g5_readiness_manifest.json` and conformance report pass; the W12D consumer gate passes with `conversion_classification=unchanged_blocker` and `decision_grade=unsupported`. The bounded G5 plumbing is complete; a positive conversion is not established. Dependency-health failures and active G6/G7/GX follow-on plans remain outside this slice's completion claim. | 13 hit files (6 Markdown, 7 JSON), including current G6/G7/GX owner documents and static source/epoch receipts. No code, configuration, validator, or runtime dependency on the plan path was found. Preserve an old-path pointer for the active successor links; leave receipts unchanged. |
| [`active/atlas-slices/DS15-acquisition-routes.md`](active/atlas-slices/DS15-acquisition-routes.md) → `archive/DS15-acquisition-routes.md` | Candidate bounded surface closure. Its dated [C06 closure](active/atlas-slices/DS15-acquisition-routes.md) records the final 42/42 mechanism readback and says the bounded surface is closed. It separately leaves `fresh_positive_production_route` `absent/unallocated`; no positive production-growth claim follows. | 15 hit files, including current E02R2 docs and immutable source receipts. `CROSSWALK.md` pins the original Git blob `ccc4a7bd…`; `R13_G_RESIDUAL.md` binds `DS15-acquisition-routes.md@sha256:5402b3e4…`. Do not edit either E02 source binding or JSON receipt. A pointer can preserve ordinary path links, while the byte-identical archived original preserves the content digest/blob. Keep the move conditional on confirming the hash-only R13 receipt resolves to that archived original; if it expects current bytes at the old path, do not stub the source. No code/config/runtime dependency on this plan path surfaced. |

For an active-path pointer, preserve the original plan's historical status in
the archived copy; the pointer's `superseded` status describes that old path,
not global completion. Link the pointer to the archive copy, disposition record,
and any current successor. Do not edit E02 or hashed-source bindings as part of
these moves.

## Held or unresolved

| Plan | Evidence and current reading | Disposition |
| --- | --- | --- |
| [`active/layer3-slices/G2-causal-forecast-search-engine.md`](active/layer3-slices/G2-causal-forecast-search-engine.md) | Its 2026-06-08 Completion Audit describes bounded ForecastSupport and explicit authority denials, with a then-passing readiness signal. The current [`layer3_g2_readiness_manifest.json`](../../architecture/policy_design_case/layer3_g2_readiness_manifest.json) is `fail`, with G2 conformance `fail` and eight current issue codes. Successor G3/G4/G5/GL/GX plans remain active, but no current owner reconciliation was found that separates a historical regression from an open G2 obligation. | Keep visible pending owner reconciliation. Historical completion is not current runtime readiness; the current failure is not erased by the earlier pass. |
| [`active/POLICYOS_BEST_IN_CLASS_PRODUCTION_QUALITY_REMEDIATION_PLAN.md`](active/POLICYOS_BEST_IN_CLASS_PRODUCTION_QUALITY_REMEDIATION_PLAN.md) | Front matter says `completed`, while the [production-quality acceptance report](../archive/reports/POLICYOS_PRODUCTION_QUALITY_BEST_IN_CLASS_ACCEPTANCE.md) records `passes_all: false`, `passes_required: false`, and `status: fail` (17 passed, 7 failed). | Hold. The contradictory production-quality result is unresolved. |
| [`active/REPOSITORY_BEST_IN_CLASS_LAST_MILE_REMEDIATION_PLAN.md`](active/REPOSITORY_BEST_IN_CLASS_LAST_MILE_REMEDIATION_PLAN.md) | Superseded status coexists with live references from code/config, including the repository last-mile inventory tool and architecture/pre-commit budgets. | Hold the path until those consumers have an owner-approved replacement; a documentation pointer alone cannot preserve their content semantics. |
| Existing [Design](active/DESIGN_BEST_IN_CLASS_PLAN.md) and [Frontend](active/FRONTEND_SOTA_PLAN.md) pointer stubs | Both already use `archived_copy` and `disposition_record` and carry no execution authority. | Keep their existing lifecycle anchors. |
| [`active/POLICYOS_ATLAS_PRODUCT_MARKETING_CLIENT_SURFACES_MASTER_PLAN.md`](active/POLICYOS_ATLAS_PRODUCT_MARKETING_CLIENT_SURFACES_MASTER_PLAN.md) | Front matter says `superseded`, while the plan still contains useful DS11–DS13 owner material. | Keep the material routed until its bounded owner content has a current home; do not archive from the status label alone. |

The nine accepted Repository SOTA and structure plans also remain in place:
repository quality tests and closeout tooling bind their paths, including the
Phase 0–5 set and structure Phase 7 closeout. This review makes no accepted-plan
moves.

## Pattern and gate-property notes

- `P35`: counts above come from complete scripted path walks; denominators and
  file-type groups are stated. No count was inferred from a search result.
- `P36`: primary evidence is cited by path and section or artifact. Where a
  source has no finding ID, none is invented; a missing ID alone does not block
  an otherwise explicit bounded closure.
- `P37`: Data Forge's cutover sufficiency is `institutionally_supplied` by its
  owner sign-off; G5 conformance and consumer verdicts are `institutionally_supplied` to this
  review through retained artifacts, not rerun gates. DS15's recorded closeout
  is likewise `institutionally_supplied`, while its
  positive production route is `not_established`; G2's retained readiness artifact reports failure; the gate was not rerun
  here (`institutionally_supplied` relative to this review). The historical Documentation D6 snapshot is an
  `institutionally_supplied` record about its 2026-04-17 scope, not a current
  gate predicate.
- `P38`: the property for G5's `pass` is slice conformance; using it as positive
  conversion readiness would disagree with the same consumer artifact's
  `unchanged_blocker`/`unsupported` output. For Data Forge, `completed` means
  owner-approved Phase 0 cutover sufficiency, not that the two named benchmark
  readiness metrics passed. DS15 explicitly separates bounded closure from
  unallocated production growth. G2 and production quality have unresolved
  current red evidence and remain held.

This task is documentation navigation and disposition, not a claim of a new
runtime capability. The target pattern is bounded owner closure with an honest
residual, a history-preserving archive copy, and a routed active owner when
needed; no code or governed JSON binding is changed here.

## Delivered batch and next review

Documentation SOTA, Data Forge Phase 0 and G5 were archived with old-path
pointers. Root reread their destination bytes against the pinned source and
retained all E02 receipts. DS15 remains conditional on its hash-only reader
semantics; the original plan stays in place. Do not move G2 or the production-quality
plan until their current reds have an owner disposition. The parent task's
separate superpowers-plan census may add candidates, but this review found no
unreferenced plan in that set.

## Reference and verification limits

The inbound scan establishes literal filename/stem references within the named
text-like denominator. It does not prove absence of dynamic path readers or
runtime consumers that construct paths without those tokens. Stored gate
verdicts were inspected; this review did not rerun G2/G5/DS15 or Data Forge
runtime verification. Archive/pointer delivery is a documentation operation,
not an authority-grade runtime gate. The three historical-source copies were
read back byte-for-byte before delivery; source code and E02 receipt bindings
were not changed.
