---
title: Comprehensive documentation maintenance at the E02 source snapshot
status: completed
owner: team-docs
created: 2026-10-14
last_verified: 2026-10-14
stability: closed
---

# Documentation maintenance audit

Documentation delivery is complete within the scope below. Global verification
remains partial; the failed and UNRUN gates are not waived by this closeout.

## Scope and authority

This is the second documentation-maintenance slice, authorized on 2026-10-14,
on `codex/docs-refresh-e02-20261014`. Its entry is
`c35222b3dcf103338175cf300c5fe9487e6416f3`; production source is pinned to
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`. Twenty direct lanes performed the
census, source/document audits, tooling repairs and independent reviews.

The system is not functional end to end. Source inspection, declared
contracts, local smoke recipes, generated inventories and documentation
checks establish different bounded properties. This report does not close
E02, certify runtime readiness, run a policy analysis or authorize deployment.
The earlier [documentation-refresh report](2026-10-14-documentation-refresh-e02.md)
records a different publication boundary and verification wave.

## What changed

- Current maps separate existing producers, persisted artifacts, consumers and
  missing bridges across Runtime, Scientist, Foundry, Fabric, Data Forge, Lex,
  IR and frontend surfaces. Candidate, validation, authority and publication
  meanings remain distinct.
- Tutorials explicitly identify draft workflows, synthetic/local smoke scope,
  unexecuted recipes and temporary storage. Unsupported expected results,
  silent synthetic fallback and a dead temporary-store example were removed
  or corrected. Worked examples and procedural/scaffold guidance have distinct
  roles.
- Routing now reaches accepted plans, archive report/spec rules, accessibility
  evidence and the repository-local handbook. Active backlogs and owner-bound
  records stay in place; no age-based archive or duplicate-based deletion was
  performed in this slice.
- Source READMEs correct retired shims, broken links, current canonical owners,
  source-declared counts, expired-but-unresolved governance dates and rubric
  mismatches. Counts name their file/symbol denominator; historical test
  collection is not current execution evidence.
- The user approved the [exact handbook adjustment](../../plans/documentation-publication-adjustment-20261014.md):
  ten primary/verbatim records remain unchanged in Git and leave MkDocs;
  the revised BERL explanation returns to navigation. The existing 493 declared
  pages are preserved. Old deployed URLs/backlinks remain unmeasured; the
  publishing owner must resolve retirement/redirects before merge or dispatch.

## Tool repairs and their limits

| Owner | Result | Remaining boundary |
| --- | --- | --- |
| Docs accuracy | Actual MkDocs inclusion governs page scanning and declared navigation; resolved destinations replace segment proxies; supported reference links and actual-read receipts are checked. | Raw HTML/assets, fragments, root URLs, external liveness, absent allowlisted files and unsupported multiline forms are separately bounded; incomplete deciding input returns UNRUN. |
| Docs lifecycle | Full tracked paths govern removed-directory presence; reference inputs disclose selected reads, opaque bytes, exclusions and ambiguity; canonical table tokenization preserves column roles. | Receipt is reference-scan-only; other lifecycle families are named unmeasured. Historical/archive suppression retains declared-role and unverified-provenance limits. Incomplete scans remain UNRUN with real findings visible. |
| ADR index | Explicit statuses and relation fields replace accepted fallback and narrative supersession; unknown status remains unknown; pipe-bearing titles serialize into one table cell. | Source declarations are not ratification or implementation. Unsupported relation vocabulary and primary source-fidelity discrepancies remain named. |
| Fabric inventory | AST namespace/class resolution excludes functions/protocols, detects aliases/rebinding and derives identity slots; reads are disclosed. | Native imports/slot values/operation are not proved. Equal counts plus a validator do not establish contract-to-connector identity; the family state remains partial. |
| Public-surface renderer | Existing candidate/export-proof scope and compact JSON evidence bindings are visible and safely rendered. | Unproved native exports/counts stay unknown; no resolver or production authority was relaxed. |
| Tools reference renderer | The real CLI emits identical bytes under two checkout roots; the canonical reference includes the three previously absent commands. The footer is product-relative and the expired wrapper prose is qualified. | Command and compatibility metadata do not establish execution, removal, owner sign-off or a closeout receipt. Registry command metadata and dispatch are unchanged. |

Tools were exercised through their real callers with positive, negative,
unreadable, changed-input and marker-preserving removal probes. Complete raw
outputs and execution receipts stay ignored under `_build/docs-maintenance/raw/`;
canonical generated outputs are produced by their existing owners. No CI
workflow, dependency lock, runtime schema or production implementation changed.

## Coverage and verification

The first full wave used `c2346b78ff812f0cabad5a48f456ae46de0fcb1c`.
Its rendered crawl found one missing ownership anchor; the path-aware gate
also exposed stale generated tools entries and a checkout-specific footer.
The batched repair was independently reviewed and frozen at
`1d672b24d2af0a232b6ba95d6bd1f92d40f46e33`, then tested and rebuilt. The other
compiled inputs were reused only after content equality was measured.

The complete c234 Git-tree census is 25,068 tracked paths of all types and
3,319 `.md` paths repository-wide. `policy-engine/docs/` has 14,840 tracked
paths of all types, including 2,814 Markdown; the product has 3,317 Markdown,
503 outside `docs/`. The other two repository Markdown paths are root
`AGENTS.md` and `.github/PULL_REQUEST_TEMPLATE.md`. These path counts remain
unchanged at the publication-content freeze; later closeout companions are
separately measured. They are not semantic-freshness totals.

The 502 supplemental outside-doc assignments comprise 500 product paths and
those two root pages. The three separately allocated product READMEs complete
the 503-path outside-doc set. The 597-row supplemental index at c234 records
495 matching full-file hashes, 73 absent per-path digests and 29 stale or
scope-mismatched digests, with no absent paths. Original methods and pins are
retained; later readbacks are separately indexed. A digest reread, metadata
clarification or work assignment does not become a new semantic review.
Frozen research received structural and selected-record review, not a blanket
endorsement of its scientific claims.

The declared handbook preserves all 493 previous Markdown paths and adds
BERL: 372 nav entries plus 122 `not_in_nav` entries, 494 unique declared
pages. Actual MkDocs inclusion is 530 Markdown files and 14 assets. An
`INCLUDED` flag also admits unlisted pages/assets; its 422-file category is
not a count of nav pages. The ten approved held records remain byte-identical.

### Deciding checks

| Check and freeze | Verdict | Bounded evidence |
| --- | --- | --- |
| Targeted ten-module pytest wave, c234 | 274 passed; 1 failed | Complete progress stream totals 275 outcomes. The failed Phase 3A public-surface snapshot test has the narrow P41 attribution below; the whole wave remains exit 1. |
| Unified CLI tests, 1d672 | 20 passed | Real write/check calls under two checkout roots produce byte-identical references; status corruption is rejected. |
| Python lint/format, 1d672 | Passed | Ruff checked all 14 changed Python files: seven documentation tools/renderers and seven mirrored test modules. |
| Authored Markdown, 1d672 | Passed | Canonical `workspace docs-style` used the complete 321-path changed authored selection. Six owner-generated references use generator drift/build/link checks; configured archive/benchmark/research exclusions remain explicit. |
| Config, ADR and Fabric drift, c234; Fabric recheck after renderer change | Passed | Canonical owners reproduce their outputs. Source inventories and outcomes are captured; no primary ADR or resolver authority was rewritten. |
| Config/ADR/Fabric field corruption, c234; CLI field corruption, 1d672 | Rejected as required | Each real checker returned exit 1 on a changed field with valid surrounding format. Canonical artifacts were restored exactly, or a bound scratch copy was used. |
| Accuracy/freshness, c234 and freshness recheck at 1d672 | Passed | Actual 530-file Markdown selection has zero checker violations; raw HTML/assets/fragments and unsupported forms retain their named checker limits. |
| Strict MkDocs, 1d672 | Passed | Second build completed in 42.77 seconds; first c234 build and its one bad fragment are retained rather than overwritten. |
| Whole source and emitted-site link QA, 1d672 | Passed within declared parser scope | All 544 selected source files: 2,362 references, no unresolved local targets. All 532 HTML and five CSS outputs: 289,149 references, no missing local files, HTML fragments or paths outside the site root. The 715 direct render inputs are content-bound; transitive imports/plugins, JS navigation, one CSS resource fragment and external URL liveness remain unmeasured. |
| Lifecycle child inside actual changed-path gate, 1d672 | UNRUN, exit 2 | Reference-only receipt reports partial selection/read coverage; findings stay visible. |
| Actual changed-path docs-gate, 1d672 | Failed, exit 1 | 351 slice paths discovered from Git; tools reference passes, then lifecycle exit 2 stops remaining children. Independently run checks are not relabeled as gate children. |
| Full architecture guardrails, c234 | UNRUN, exit 2 | Four required generated checks could not install their isolated environment because its copied vendor wheel was absent. Completed findings include one deep-import baseline drift, 406 deep-import-creep entries and two absent declared schema outputs. No full inherited/disjoint claim is established. |

The lifecycle reference denominator is 25,040 product tracked paths: 24,822
selected and 218 selector-excluded. Of the selected paths, 23,878 were scanned
as text and 941 had recognized opaque signatures; three remain ambiguous.
Its 1,159 unresolved findings comprise the 218 exclusions plus those 941
opaque inputs. Ten direct-reference findings remain: nine frozen E02 records
and one intentional negative-test fixture introduced by this slice. The latter
exposes the lexical scan's lack of fixture-role semantics; it is not hidden by
an exemption or assigned to a prior owner. The wrapper adds one command-failure
record separately. Other lifecycle input families and historical/provenance
suppression limits remain explicitly outside this reference receipt.

### Failure attribution and retained evidence

The exact single snapshot-test command was replayed at slice base c352 and
c234 using the same Python, argv and runner environment. Both returned exit 1
with identical complete stdout. All 2,761 selected source Python files and the
actual imported in-repository modules, test, validator and baseline had equal
bytes and zero changed-path overlap. Only this gate is `reproduced/disjoint`;
owner: architecture/public-surface baseline. The snapshot was not refreshed to
silence the failure. Full architecture and lifecycle attribution stays separate.

Complete outputs and actual commands are in ignored raw execution receipts;
these small references bind the retained deciding evidence:

- Census: `final-readonly-reconciliation-c2346b78ff81.json` @
  `ede143eff1328d793479a33f1bf21cde2a99ef8c566173eac3d18996b893c828`;
  scope/readback correction: `final-census-correction-c2346b78ff81.json` @
  `2d98bfcdb055fee85d60c10c12a94791bd21d29850a6069f5b920aed31cacd12`.
- First targeted pytest stdout: `final-targeted-tests.stdout` @
  `89f3b936757437c48fc627064a93cc751e614d858fb95d79b613c365abca1726`.
  P41: `public-surface-p41-c352/summary.json` @
  `5786de3dfb488c857a24854609d1db106824927118e3d091a9c5741768f9c077`;
  exact base/current stdout SHA is
  `7a72d36c9ad6a57e949853e8733c88aa227abac0ad204b1f3255e21c0d482083`.
- Full architecture stdout: `final-architecture.stdout` @
  `7fd1dfafd13ca1dcbe3a17a5c8fd32a65aeaebc0122d3c77e232df614311b7b3`.
  Final changed-path gate stdout: `final-corrected-docs-gate.stdout` @
  `09b1da758fe2ed623268fa27a5fff2713649481ca5354773bb82259ed3d620dc`.
- Second strict-build stderr: `final-corrected-strict-build.stderr` @
  `423ebae230c345a980b8cd891ed9a0f1853b0f1c5057bc2420c6a6f480a73926`.
  First emitted crawl: `final-c2346b7-emitted-crawl.json` @
  `fa5188c3f6ae1c224ec818b64304de95a1f5e03ea0057025a23d787849ebf44e`.

All paths in that list are relative to `_build/docs-maintenance/raw/`.
Passing checks also retain `<label>.execution.json` plus complete stdout/stderr;
no command output is replaced by a hand-authored green status.

The final emitted crawl is `final-1d672b2-emitted-crawl.json` @
`0cf31a6630ccceb55154a8c2a88d7291037cde62089381a451232304eb673507`.
It binds the
second strict-build receipt and all 715 direct input hashes, with no committed
or checkout byte mismatches. Across 593 emitted files, 81,705 local HTML
fragment references were checked; all four Scientist custom TOC IDs are present.
The output path/size/hash inventory stayed stable during the crawl, digest
`4de17bee3502749a18a71e9a1b4f7f8ca1b9bb4fac9839f0227b1df9a80d952f`.
The CSS `url(#throughputFill)` consumer has that ID and stylesheet link, but
browser resolution remains unestablished. External URLs were counted, not
fetched.

This completes the bounded documentation task and records every non-green
signal above. It does not satisfy the failed/UNRUN global gates or authorize
merge/publication. Final report and plan-routing companions stay outside the
715-path render manifest; their input disjointness is checked before delivery.

The final companion set adds only the archived copy of this task's completed
plan: final repository denominators are 25,069 tracked paths and 3,320 Markdown,
including 3,318 product Markdown and 14,841 docs paths of all types / 2,815 docs
Markdown. The complete slice delta is 352 paths: 333 Markdown and 19 authorized
tool/test/config/generated non-Markdown files. Production implementations,
schemas, locks and CI remain unchanged; the 11,249 frozen E02/package paths
and ten held records remain exact. The eight final companion paths intersect
the 715 direct render inputs at zero, and all 715 hashes still match.

After staging the new archive, lifecycle was replayed on 25,041 product paths
(24,823 selected, 218 excluded; 23,879 scanned as text). It again returned
UNRUN with the same 1,159 unresolved, three ambiguous and ten direct-reference
findings. The pre-final-paragraph stdout is `closeout-lifecycle.stdout` @
`5ab86817497c9e0654bf576ee41bd140ce38b902d8a813030994e4f456b5f7d7`;
this replay is a partial verdict, not a green closure gate.

The frozen E02 corpus and agent packages remain read-only. Their structural
and selected-record audits do not certify every research claim or reproduce
the unavailable shared-source occurrence census. No live providers, services,
databases, simulations, browser, deployment or external compliance assessment
were exercised by the documentation audits.
Full backend verification, CI parity and a functional policy E2E scenario
were not run; their results are not inferred from these documentation checks.

## Open owner work

- After E02 reaches a shared source freeze, revalidate these maps and build one
  genuine input-to-public-projection policy scenario with negative authority,
  staleness and invalidation cases. Until then, tutorials retain smoke/draft scope.
- The crosswalk artifact's source hash does not align with its claimed source
  pin; the authored reference discloses `not_established`, while its JSON stays
  unchanged for canonical-owner reconciliation.
- Historical GY source-committed audits and ADR-0045/0064 retain documented
  source-fidelity discrepancies. Their primary bodies are preserved; present
  registration/implementation is not inferred from them.
- Current wrapper/path removal disposition, the lint redirect's unestablished
  lifecycle owner, expired external accessibility/Common dates,
  and the old release-observation disposition require owner reconciliation.
  No renewal, countersign, approval or terminal state was invented.
- Full architecture generated-environment availability, deep-import baseline
  reconciliation and missing declared schema outputs require their canonical
  owners; this documentation branch does not waive those gates or repair
  production contracts. Lifecycle container/fixture semantics need a separately
  scoped instrumentation design rather than a blanket test/research exclusion.
- Backlog routing still omits the Cloud Wave 11 diagnostic queue from its
  production-run index; legal/causal package shorthand can receive a later
  owner-scoped prose pass. Detailed references carry the present source limits.
- Exact-byte archive aliases are retained until their documentary roles,
  consumers and URL consequences support an explicit owner decision.

## Pattern disposition

P01/P02/P03 and P04/P05/P09/P15 govern capability and authority truthfulness.
P07/P08/P36 preserve pins, time roles and primary findings. P29/P31/P32 and
P35/P37/P38 require actual-caller evidence, complete denominators and named
unresolved boundaries. P40 widened namespace-binding checks and bounded the
unproved identity join rather than adding instance patches. P41 attribution
is retained separately from documentation completion: input overlap and changed
tool semantics preclude calling the full lifecycle red inherited/disjoint.
