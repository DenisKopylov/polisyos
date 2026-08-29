# INT-R6 Independent Audit

## Audit Identity And Pinned Evidence

This audit is independent Stage 2 review of the eight-file INT-R6 research package. It assesses research quality only; it does not open a gate, promote a capability, change package standing, or appoint a holder.

Connector observation `git-ref read`, exact ref `refs/heads/research/int-r6-research`, returned package SHA `5e47c868c2c1d4d66fa11fcddcc972dbb55e95d3`. Every repository read used that SHA except the two explicitly historical reads at pre-repair SHA `b612b21272c732d53cfde8569846cfb7a0c73f5a` and governing external-source verification.

The audit ref was created at the package SHA. Before the first content write, connector `compare(base=5e47c868c2c1d4d66fa11fcddcc972dbb55e95d3, head=research/int-r6-independent-audit)` returned `merge_base_commit.sha` equal to the package SHA, `ahead_by=0`, and `behind_by=0`. This is exactly the ancestor predicate required by the commission.

Seven headings-only files were created in seven distinct commits before any substantive audit content.

## Verdict Vector

| dimension | verdict | reason |
|---|---|---|
| delivery containment and final inventory | `GO` | the repair leaves exactly eight package Markdown files under the product root and no root `docs/` tree |
| D4-A1 composition and source/UI separation | `GO` | the package preserves `en` authored UI, `uk` translation, frozen `ru`, and does not use UI locale to confer source authority |
| language-axis architecture | `GO_WITH_REVISIONS` | the separation is useful, but “five orthogonal coordinates” overstates the independence of presentation variants from renditions |
| English-pivot and co-authentic treatment | `GO` | the protocol keeps jurisdiction concepts and co-authentic sets outside a mandatory English authority pivot |
| semantic falsifiers | `GO` | all three malicious targets can retain key and placeholder structure while changing authority semantics |
| proof and certificate argument | `GO_WITH_REVISIONS` | counterexamples are sound falsifiers, but a finite material-context suite cannot prove universal natural-language equivalence |
| repository baseline and evidence custody | `NO_GO` | the delivery repair removed a measured 223-line baseline and its declared 105-line successor does not preserve those measurements |
| W4-K05 conformance | `NO_GO` | two live standing blocks disagree; the main deliverable uses non-registered axes and tokens |
| current capability claims | `NO_GO` | Phase 0 says the system can perform functions while the conforming standing says `absent/unallocated` |
| anchors and citations | `GO_WITH_REVISIONS` | principal institutions resolve, but the `R v Daoust` locator is wrong and several citations are only document-level |
| **aggregate research-quality verdict** | **`GO_WITH_REVISIONS`** | the architecture is worth carrying forward only after all blocking/material defects are corrected in every artifact that carries them |

## Package Standing Under W4-K05

The audit does not move package standing.

The appendix publishes:

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

The main deliverable separately publishes:

```yaml
evidence_standing: supported
decision_standing: proposed
implementation_standing: not_implemented
```

The latter field names and tokens are not members of the vocabularies ratified by W4-K05, and neither block is marked superseded. Therefore the package does not currently publish one internally coherent W4-K05 standing record. The appendix values are individually conforming, but they do not silently erase the live main block.

## Architect Ground-Truth Recomputations G1-G7

| item | supplied | auditor observation and denominator | disposition |
|---|---|---|---|
| G1 delivery repair | 11 commits; root `docs/` zero | connector compare from `dc7bdf79…` to package SHA: `ahead_by=11`, `behind_by=0`; exact root tree had six entries—`.editorconfig`, `.gitattributes`, `.github`, `.gitignore`, `AGENTS.md`, `policy-engine`—with `truncated=false`; package delta had eight Markdown paths, all under `policy-engine/docs/research/policy-operations/` | `agree` |
| G2 final inventory | 8 files, 2,134 lines, 122,903 bytes | complete package set: 8/8 blobs; independently summed blob sizes and line counts match 122,903 bytes and 2,134 lines | `agree` |
| G3 removed content | two files removed/replaced; net −25,850 bytes | pre-repair canonical extras were 8,045 and 18,395 bytes; pre-repair root package was 122,313 bytes; corrected package is 122,903 bytes; arithmetic gives −25,850 bytes | `agree on arithmetic; disagree that succession preserved substance` |
| G4 W4-K05 | three registered axes | full §4.5 read confirms the three fields and the PAO-R4 `GO_WITH_REVISIONS` counterexample; §4.6 confirms prose is not `contract_only` | `agree` |
| G5 two standing blocks | two live sections | exact reads confirm both and no supersession marker | `agree; defect established` |
| G6 catalogue figures | current 2,618/2,618/2,449 and identity figures | exact package-SHA connector reads established three JSON blobs and the current parity mechanism, including `uk` key equality and frozen `ru` count 2,449. The connector could not expose the complete decoded payload to an executable local leaf-walk without leaving the connector boundary. Auditor leaf/identity values are therefore `not_established`; architect values are not silently adopted. Package historical figures cannot serve as current-tree figures. | `not independently verified; package current-baseline claim blocked` |
| G7 D4-A1 | `en` authored, `uk` translated, `ru` frozen | exact D4-A1 read and UI locale contract agree; the package follows D4-A1 rather than the stale backlog row | `agree` |

G6 is an explicit residual, not a borrowed positive. It does not rescue the package: the package itself admits it did not perform the current walk, while its baseline section still foregrounds a superseded equal-denominator snapshot.

## Threat-Model Results T1-T10

| threat | result | evidence |
|---|---|---|
| T1 five-coordinate partition | `partly established` | UI locale, authority set, rendition and semantic namespace remain distinct in both worked cases; presentation variant is a child transformation of a rendition/proposition rather than an independent coordinate of equal type |
| T2 D4-A1 `composes` | `refuted` | MAEP source authority is selected by jurisdiction/authority set, never `ui_locale`; RTL source rendering can be admitted separately from public RTL UI |
| T3 English pivot returns covertly | `refuted` | indexing/glosses may use English only with explicit non-authoritative purpose; jurisdiction IDs survive; the existing `SPOCandidate` English pivot is identified as a repository gap, not endorsed |
| T4 catalogue figures | `established` | the package carries DS0’s equal 2,449 snapshot but does not establish the current unequal denominators; the divergence strengthens its thesis that catalogue symmetry is lifecycle-specific, yet the main baseline does not update to it |
| T5 standing conformance | `established` | two unsuperseded blocks; main block violates W4-K05 vocabulary |
| T6 second-lattice ban | `refuted with implementation condition` | proposed relation/result examples are repeatedly labelled candidates or mapped reasons; runtime already owns namespaced blockers and distinct validity states. A later implementation must map or register rather than copy the examples verbatim |
| T7 binding falsifiers | `refuted` | parity checks paths/placeholders and frozen Russian integrity; each malicious target can preserve that structure, so the red is semantic rather than structural |
| T8 zero-holder operation | `partly established` | the role/appointment/decision model correctly leaves source viewing and draft comparison unblocked; the claim that this is demonstrable today is unearned because no runtime chain implements the refusal |
| T9 thirty findings routes | `established` | denominator: 30 table rows, IDs F-001 through F-030 exactly once. Routes are generic lanes such as “specification”, “architect”, or “future admission”, not accountable existing holders |
| T10 limitations versus absences | `established` | the package carefully labels several measurements unresolved, then uses conceptual records as if the system can already display, check, refuse and admit them |

## Finding Register

| ID | severity | finding | route |
|---|---|---|---|
| IR6-A01 | `blocking` | two live W4-K05 blocks conflict and the main one uses non-member axes/tokens | Stage 3 package amendment; correct every carrying artifact |
| IR6-A02 | `material` | delivery repair removed measured baseline evidence; declared successor does not preserve it | restore or explicitly retract/recompute in package baseline artifacts |
| IR6-A03 | `material` | Phase 0/current-system capability wording exceeds `absent/unallocated` | rewrite as target-model capability or provide full typed chain evidence |
| IR6-A04 | `material` | package has no current catalogue leaf/identity walk and foregrounds a superseded equal-denominator snapshot | independent complete JSON leaf walk at a pinned SHA |
| IR6-A05 | `material` | F-001–F-030 routes do not bind accountable existing owners | architect assigns named owner/holder or records `absent/unallocated` |
| IR6-A06 | `material` | unestablished repository mechanisms are used as settled premises in “works now” and Phase 0 conclusions | separate architecture demonstration from repository fact throughout |
| IR6-A07 | `material` | MAEP turns a sound finite falsification method into an overbroad positive equivalence certificate | narrow certificate claim to bounded tests/purpose or add a defensible completeness oracle |
| IR6-A08 | `minor` | “five orthogonal coordinates” mixes independent selection axes with a dependent presentation transformation | rename to five record dimensions/layers and state dependencies |
| IR6-A09 | `minor` | `R v Daoust` points to the wrong SCC item; several anchors lack paragraph/clause locators | citation correction pass |
| IR6-A10 | `minor` | the 21-line scaffold remains a live sibling without an explicit entrypoint or supersession declaration | package metadata/README-level disposition within an existing artifact |
| IR6-C01 | `commendation` | D4-A1 composition and UI/source separation survive hostile testing | preserve |
| IR6-C02 | `commendation` | three falsifiers genuinely discriminate semantics beyond catalogue parity | preserve |
| IR6-C03 | `commendation` | co-authentic authority and no-mandatory-English-pivot model survives worked examples | preserve |
| IR6-C04 | `commendation` | role, appointment and decision are separated so holder cardinality zero is representable | preserve while removing implementation overclaim |

## Severity Arithmetic

The denominator is the 14 rows in the single register above; IDs are unique.

```text
blocking 1 + material 6 + minor 3 + commendation 4 = total 14
```

## Residual Band

This audit did not validate legal effect in every jurisdiction, translation quality of every quoted example, cryptographic certificate design, real-user comprehension, or full implementation feasibility. The connector could not materialize the three catalogue payloads into the local executable environment, so G6 identity arithmetic remains `not_established` by this auditor. The `df90e10fb` short commit identifier also did not resolve to a full commit through the connector. DS12/DS13 have no directly named slice file in the exact `atlas-slices` directory listing at the package SHA; their seams were audited only through D4-A1, DS11, runtime code and the master-plan references that were reachable.

## Final Connector Observations

Final ref, containment, base ancestry, recursive-tree truncation status, exact `int-r6` path set and package-to-audit delta are appended after the final verification commit. No terminal transcript is asserted anywhere in this audit.
