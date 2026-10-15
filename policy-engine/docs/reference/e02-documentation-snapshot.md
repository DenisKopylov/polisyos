# E02 documentation snapshot

Owner: E02 integration (G) for cross-owner acceptance; A–F own their individual source slices.

Source of truth: exact finding-to-criterion bindings, owner handoffs, deciding receipts, and G
integration checkpoints cited below. This page is a dated reading map, not an acceptance record.

**Reviewed against:** documentation and receipts at
`c35222b3dcf103338175cf300c5fe9487e6416f3` on `codex/docs-refresh-e02-20261014` (2026-10-14).
The latest author candidate named by the E02 handoff is a different source:
`4e37301ee205bfc3a913993a5da81bbf292be3ef`, tree
`bc56dde4f4ac5611d65266bbc9cb09bc80bc5348`, based on
`28b73cb9c78f6f65f2baa1e1561b2f6b57039aa3`.

The repository evidence-navigation census walked every regular file, of every suffix and
extensionless type, under `docs/research/`, `docs/superpowers/`, and both E02 agent-package
directories at the reviewed tree: 13,996 paths and 471,200,979 bytes. All paths were tracked; the
walk found no ignored or untracked paths in those roots. The scoped counts are: research 11,409
paths / 270,873,940 bytes; the E02 plan subtree 11,010 / 256,887,714; superpowers 2,348 /
181,581,585; the combined E02 package 185 / 11,516,567; and the distinct E02-R2 package 54 /
7,228,887. These are inventory counts, not evidence-status counts. The ignored local receipt
`policy-engine/_build/docs-maintenance/raw/research-e02-audit.json` contains the per-path hashes,
complete file-type histogram, lexical-scan counts, and read limits; it is not published and contains
no source bytes.

The read boundary matters: all 13,996 files were streamed and SHA-256 hashed; 13,052 UTF-8 files
were fully decoded, 936 binary/container files and 8 non-UTF-8 files were hashed only. Decoding and
the recorded full-text lexical scan do not amount to line-by-line semantic review of every archived
record. The owner records below were read as source-qualified evidence. No test or functional E2E
was run for this documentation snapshot.

As of this snapshot, E02 has a pinned Source41 author candidate and bounded owner results, but the
shared source/input/backend freeze is explicitly false, the handoff records no new formal closure
IDs, and the candidate is not the separate published G checkpoint. The original cloud matrix, the
numbered integration checkpoint, and Source41 therefore remain distinct evidence cuts.

## Source drift in handbook maps

A separate read-only source comparison on 2026-10-14 used commit
`4dffb9f537db40bac255ea6a15f81e70a1eca080`. It compared the complete
backticked path/glob declarations of six selected handbook maps with their
inspected pins, using `check_docs_source_bindings`. Five declared sets differ:

| Selected page | Changed existing paths | Added paths |
| --- | ---: | ---: |
| Architecture | 50 | 2 |
| End-to-end data flow | 2 | 0 |
| Runtime request lifecycle | 3 | 0 |
| Data Forge current data paths | 2 | 0 |
| Frontend surface map | 21 | 1 |
| Scientist current workflows | 0 | 0 |

No selected set had removals or mode changes. Sets overlap, so these counts
must not be summed as distinct repository changes. The Scientist result covers
its 194 declared paths only; it does not establish complete claim coverage,
current body-cited tests, unchanged dependencies or executed behavior. The
other results require review, not an automatic verdict that their prose is
false. Their historical source pins remain intact.

The comparison read Git objects without switching checkout, fetching objects,
importing E02 code or changing its branch. It does not inspect uncommitted E02
work, establish a shared freeze, accept an integration checkpoint or close a
finding. After the canonical owner freezes integration, review each changed
owner and its dependent claims before updating a pin. Tutorials remain
scheduled for that later completed-E02 work; this pass did not change them.
The documentation-maintenance closeout retains the actual comparison receipt.

## Evidence cuts

### Historical transferred campaign

Start with results and limitations (`policy-engine/docs/research/e02-cloud-test-plan/results/README.md@sha256:2f91e5a04610ef877dce4ed9121a045aefac01540662a85c12c340a5ed32b8e7`), its
source inventory (`policy-engine/docs/research/e02-cloud-test-plan/results/sources.json@sha256:a08b728541bf0c424e985969760131e553873c3be91aa9b4d6e96a50e9556edb`), and the
campaign assessment (`policy-engine/docs/research/e02-cloud-test-plan/results/ASSESSMENT.md@sha256:81d235335f4b5bb8ffd2055ff2d349baec2a80e9711db4722f1bcdbadb7488c2`).
The owner map pins `69780761ae091d8fcc6ab8778c7f5f7227eeef0b` as the original planning source;
the results table preserves the different historical source cuts used by individual reports.

The result README describes transferred UTF-8 reports and states that raw VM archives were not part
of the transfer. It also says receipt validity, full stdout/stderr/longrepr, and source-input
custody were not independently checked. Treat these as source-reported historical results, not
current-candidate replay or finding closure.

### Checkpoint 13 — historical G record

Checkpoint 13 (`policy-engine/docs/research/e02-cloud-test-plan/integration/checkpoint-13.json@sha256:5e9b5c2cdc2f9a427807766f58eedec0979050084f2c70e1ef7d1c7c1585290a`) is dated
2026-10-07. The integration README (`policy-engine/docs/research/e02-cloud-test-plan/integration/README.md@sha256:9cb5cfb8d5b238126a759dce39a63ca0c9340db64be2359256fc83a7d558666c`)
identifies it as current for that record. It pins source `ff277db7798fc312654704fa51c52e00f53f10f4`, tree
`618e17b5da96a623d5e57f30d265e245a2b277eb`. It records no accepted slices or finding closures.
Its narrow direct search-service check is 2/2; the composed runner and independent-process case
are UNRUN. Broad replay remained UNRUN pending a shared freeze and independent reviews. This
checkpoint predates Source41 and is not a current-source census or a new G acceptance of Source41.

### Composed current-source replay plan

The 2026-10-10 plan (`policy-engine/docs/research/e02-cloud-test-plan/integration/composed-mac-current-source-replay-plan-2026-10-10.md@sha256:46e0dbe10158a8c060930a8af3ca4da6fc9763b9e60b8077052742a7cef787a0`) consolidates
named local routes for a later final freeze. The document says **plan only**: no pytest,
collection, native fit, production-data read, or source edit occurred for that handoff. Its
`f1cc10a…` source is only a planning anchor; the exact final freeze identity is deliberately blank.
It is not a test receipt.

### Source41 author candidate

The candidate handoff (`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/source41-implementation-candidate-handoff-r1604-20261014.json@sha256:34b5488bebee945f316e222209f4ebb9399cdeb04daf136ce2e7ed10378b4e75`) pins candidate
`4e37301…` / tree `bc56dde…`, parent `28b73cb…`, branch
`codex/e02-unified-local-20261009`, and a clean tracked-worktree readback. Its
`G_accepted_checkpoint` is `93d6aa62a8d236667fdf322a5fc17962523b185e` / tree
`c3a38aecbab5af06c8aed1ae27d535c7e2dc8eca`, explicitly a separate published G source.

The handoff sets `global_source_input_backend_freeze` to `false` and has an empty
`formal_closure_ids` list. Some Source41 receipts name dirty or per-command source snapshots. A
receipt’s `source_stable` applies to its own command inputs; it does not make all receipts share a
freeze. The cited source readback and full-occurrence report are marked as retained on G’s host and
are not tracked in this checkout.

The older E02 package README (`policy-engine/docs/research/e02-cloud-test-plan/README.md@sha256:7032d97b39f15d45c8f4d7b8f514f143ce1e6bc41e9038719d89495bdbb16793`) still says the A–G prompts
have not been launched. That sentence predates the transferred results and integration receipts;
use the source-qualified records above for execution status. The Source41 handoff also says its
full-occurrence report is a historical/navigation report that needs a final successor report after
the actual freeze.

## Source41 results: bounded evidence, not closure

The candidate handoff indexes these committed owner summaries and records their receipt hashes.
Counts below describe the exact selected test runs named by each receipt.

- OpenAPI strict-wire (`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/source41-openapi-strict-wire-native-result-r1529-20261014.json@sha256:a0a75000bbb53d425c4ad1d49fb54e68539d6dab2e7da1fa0731f7bafffd969d`): five selected
  exporter/wire tests passed. This is not a CAN compatibility/generated/browser receipt, nor
  production calibration or persisted-calibration producer proof.
- Foundry access-scope (`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/source41-access-scope-foundry-native-result-r1533-20261014.json@sha256:e5de590f3c8e79ef341bbdca58c61ec9cc6daf2e8edff7fea0a85ea36760e07f`): 75/79 selected
  cases passed; four failed. Three new basis-reference negatives failed on a raw absent-field
  `KeyError` before the intended receiver, so they do not prove the negative property. One actual
  benchmark-to-Search positive also failed on an empty `tenant_hash` scope supplied by the benchmark
  producer; the receipt does not classify it as inherited. It is limited to its selected tier and
  adds no finding closure IDs.
- C12/V3 actual-boundary record (`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/source41-c12-v3-actual-boundary-results-r1558-20261014.json@sha256:f231f1ffe2da52c4216da104b93bdcf18bf7cba5d0789520d338fe37b078f784`): it preserves
  per-command dirty-source records and marks a shared freeze **not established**. The C12 facade
  test-double refusal repair still needed a rerun; the V3 served attempt stalled before acquisition
  POST. This is diagnostic evidence, not product PASS.
- Frontend and Vitest (`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/source41-frontend-typecheck-and-vitest-result-r1569-20261014.json@sha256:464b77367ccfa19f765169bdd061c5fb4257cc76fc8ef34b10e1d41f1a610e32`): typecheck exited
  0 and four Vitest files recorded 192 passes. The run receipt says its source was uncommitted; it
  did not exercise a real browser or production serving instance, and is not a rerun on the pinned
  candidate.
- Reviewed backend companions (`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/source41-reviewed-companion-native-result-r1567-20261014.json@sha256:0efa3e13d16e140039250ad1023bb1b2ff1eb4d8175076dc5aad1b373964f936`): 104 passed / 5
  failed among 109 selected cases. The five ArtifactInspector CAN failures remain under
  product-versus-fixture diagnosis; this is not the full E02 closure.
- Media-aware CAN replay (`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/source41-can-media-aware-native-result-r1599-20261014.json@sha256:c033e4a1b61c6262aaaa6799182dfbca0ec677974ffc2d0ab43f577c72d56767`): the extended
  selected run recorded 103 passed / 7 failed across 110 selected cases. The receipt says five
  initial blockers were repaired but the extended module found seven further failures. It assigns no
  P41 inherited classification and no closure IDs.
- V3 selected-catalog discriminator (`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/source41-v3-selected-catalog-discriminator-r1595-20261014.json@sha256:f0dd446e7db186933d32386bdd212c6704ee02fc3513499ee454f370d00cf87a`): a call-bounded
  diagnostic found that serving context selects a fixture catalog while the K-ref Data Forge
  iterator uses the root/default catalog. It stopped before ordinary acquisition POST or
  same-candidate reissue, applied no patch, and is not product PASS. The handoff lists a general
  bridge repair as underway.

The reviewed-companion and media-aware CAN receipts are distinct runs, not additive coverage. The
candidate handoff is the owner’s synthesis; neither a bounded pass nor the clean candidate readback
changes its empty formal-closure set.

At the reviewed tree, the full set of eight direct `.json` files matching `source41-*.json` under
`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/` consists of one
candidate handoff and seven result/diagnostic receipts. A full parse found `closure_ids: []` in all
eight. This source-file result does not create G acceptance or a finding-status transition.

## Current unresolved source mechanisms

The candidate handoff’s `next_source_mechanisms` field is the author-side residual map, not a
finding-status ledger:

- `CAN`: shared semantic intake and owner/profile/control fixtures after independent R1598 review.
- `B31`: canonical active-owner intake is described as virtually implemented; exact
  owner-projection-to-profile row-set repair R4 remains required.
- `C12`: owned runtime and same-query status are described as virtually implemented; the complete
  live model-state invariant R4 remains required.
- `N4`: carry the selected catalog source/profile through full K-ref and persisted replay, and
  distinguish real V3 from a narrow projection.
- `Q2`: derive complete runtime-role profiles independently, then audit source and exercise the
  three installed profiles.

Resolve each finding before assigning a capability label. Follow
`policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json@sha256:97860dc18c7b92124971aa8032fc229be3367723ea2ec45e6cda4a777e544e01#/findings[id=<ID>].criterion_refs`
to its original criterion/card, then use
`policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv@sha256:b5b36f75d54d4c94bb20c37e1a76827dd1028da1c15942cc5dae331907811722`
and
`policy-engine/docs/research/e02-cloud-test-plan/execution-organization/bundle-owners.tsv@sha256:f587df5256ebef909b4060a588c2f947f31b173adf8d44b32e7f4eea5abd1f75`
for the primary owner and bundle dependencies.
`policy-engine/docs/research/e02-cloud-test-plan/results/routes.tsv@sha256:30755ddca05267c4aeec56154c1c9282ee985c3414b76991aecb99d0ecf59da2`
is navigation only. Compare each owner’s immutable handoff base,
candidate tree, changed paths, deciding outputs, and limitations. Do not infer `closed`,
`implemented`, `verified`, or `inherited` from a candidate label, task-level pass, source-reported
matrix row, or receipt exit code.

The initial results README points to
`PolicyOS_E02R2/residual_ledger.json@69780761ae091d8fcc6ab8778c7f5f7227eeef0b` as historical
criterion context. E02-R2 has a separate stop handoff,
`policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/HANDOFF_EVIDENCE.json@sha256:bd899edf80bbb5df215ef5564318d97a347308a0be7d83409aae1d96dee076b4`,
which records branch `codex/e02-r2`, source `0213101b6d124e6f855b1aff7c442bb0912a61c2`, and
`stopped_at_principal_request; assignment_definition_of_done_not_met`. That separate source and
assignment do not establish the current E02 Source41 integration decision.

## Recensus before another integration decision

The next shared status must come from one exact final source freeze. The Source41 owner handoff
leaves that freeze unset and lists these verification items:

- Run canonical ABI/public-surface/generator checks and corrupt-field controls on the final source.
- Recheck ordinary POST → N5 → CAS → fresh GET, meaningful N4 children, and the current reissue
  chain on that source.
- After source freeze and independent reviews, compose the Prepared-B baseline and contours with
  the remaining S1/refinement/law criteria.
- Run the required native SOTA rows/children and Linux LA-029 plus the exact installed/rebuilt wheel
  consumers.
- Reconcile authentic read-only production pairing/currentness and issue a successor report for
  the 282 finding IDs / 291 occurrences, bound to the same freeze.

These are owner-listed remaining checks, not commands run by this documentation snapshot. Before a
closure or inherited-red statement, bind each result to the exact candidate SHA/tree,
source/config/fixture/test inputs, command, and environment. Preserve complete deciding outputs and
keep UNRUN/SKIP separate from PASS. For P41, replay the exact command at the slice base before the
author’s changes and prove disjointness against the complete input denominator.

## Repository corpus, evidence roles, and archival exclusions

Keep three roles separate. Assignments, criteria/cards, prompts, bundle and owner maps, and the
publication rules are documentation inputs. Transferred reports, owner handoffs, per-command
receipts, and G checkpoints are documentary evidence for their own pinned sources, commands,
inputs, and limitations. The Source41 handoff is the latest owner-authored candidate proposal in
this snapshot; it does not certify its bounded checks or transfer authority to the separate G
checkpoint. The `PolicyOS_E02R2` package is a separate assignment and source cut; its handoff records
`stopped_at_principal_request; assignment_definition_of_done_not_met`. Its ledger does not update
Source41.

The complete repository census included 11,010 E02 research-subtree files across all file types,
including 9,810 implementation-handoff paths, 1,034 integration paths, 27 results paths, 18
closure-decision paths, and the documentation inputs and indexes. The complete
`docs/superpowers/` census included
2,251 journal paths, 39 plan Markdown files, 47 specification Markdown files, 6 research paths, and
4 timing-evidence paths. The large historical record is part of the repository inventory; its
presence does not make each file active or authoritative. An exact-SHA scan found repeated bytes,
including 1,422 empty files. Exact duplication identifies review candidates but does not establish
obsolete knowledge, and this lane removed or relocated nothing.

The initial publication record
(`policy-engine/docs/research/e02-cloud-test-plan/PUBLICATION.md@sha256:aa4113e8b783d4e30a819d688506c79c930dc1060f8e41294a0dbeb67822ada8`)
is the source for its original inclusion and exclusion decisions, not a fresh inventory of every
later handoff. It records that earlier research commits stayed on a local source branch and were
not imported. It also excludes superseded `jobs.json`/`jobs-current.json`, pilot files and Fxx prompt
copies, old planner and verification exports, temporary audit dumps, duplicate reports, VM raw
archives, full production data, and large source-audit intermediates. Those are historical
publication boundaries; this census does not establish whether corresponding bytes still exist on
the author's host.

The Source41 raw source readback and full-occurrence JSON cited by the handoff are separately marked
local-on-G and are not tracked here. Their hashes are locators, not bytes available for independent
recensus here. Later integration decisions require a new exact source freeze and recensus; this
inventory does not recover the missing raw outputs or reissue their bindings.

Pattern pass: `P35` requires complete source denominators; `P36` keeps claims bound to the finding or
owner record that establishes them; `P37`/`P38` keep gate predicates and measured properties
distinct; `P41` requires the slice base and full disjointness proof for inherited red. The correct
closeout pattern is a source-frozen owner slice with a consumed producer-to-consumer witness and
exact deciding output. Capability labels remain criterion-specific; this snapshot does not assign
a single completion state to the E02 corpus.

## Reading and binding path

For a specific finding, start with the original assignment in
the full-run map (`policy-engine/docs/research/e02-cloud-test-plan/full-run/README.md@sha256:43918f513e868803c4b6a87875819617be3ebd88507051cc35cc084a5991eafa`), then read the
bundle catalog (`policy-engine/docs/research/e02-cloud-test-plan/bundle-catalog.md@sha256:d63c6183839d00d026a6376ddf2133059cf762b1f023c3f415e58ac9182ad6a1`) and
owner organization (`policy-engine/docs/research/e02-cloud-test-plan/execution-organization/README.md@sha256:ab45ac1dc98969df9149e56e7afd19843c777854a7bff4bacb4bcc2e37f1933e`). Resolve the
exact criterion through
`policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json@sha256:97860dc18c7b92124971aa8032fc229be3367723ea2ec45e6cda4a777e544e01#/findings[id=<ID>].criterion_refs`
to its source card; use
`policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv@sha256:b5b36f75d54d4c94bb20c37e1a76827dd1028da1c15942cc5dae331907811722`
for the primary finding owner and
`policy-engine/docs/research/e02-cloud-test-plan/execution-organization/bundle-owners.tsv@sha256:f587df5256ebef909b4060a588c2f947f31b173adf8d44b32e7f4eea5abd1f75`
for shared mechanism/dependency owners.

The A–F closure decisions (`policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/README.md@sha256:d23afa2c31cada1a42be2c3e66ecdaa7b57cb436a7a133f288c36edd361f5fbe`) describe
the chosen methods and consumer checks; the Git handoff protocol (`policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/HANDOFF.md@sha256:8519f95eb0ff2ec2c64caa4497eb58b957fe7cd47a0a6955bad98a2c20795d3b`)
states what an owner must bind to an immutable slice. The integration record (`policy-engine/docs/research/e02-cloud-test-plan/integration/README.md@sha256:9cb5cfb8d5b238126a759dce39a63ca0c9340db64be2359256fc83a7d558666c`)
and its checkpoint JSONs record what G accepted at each source. The Source41 handoff is later author
evidence; it does not replace any of these bindings or G decisions.
