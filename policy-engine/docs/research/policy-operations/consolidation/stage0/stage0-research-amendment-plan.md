---
title: Stage-0 Research Amendment Plan
status: draft_consolidation
kind: research-synthesis
research_scope:
  - PAO-R0
  - PAO-R1
  - OPS-R15
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
pao_r0_audit_commit: 258aa740efcfb9e6771bfe52d4fdabc6b74f93a7
pao_r1_audit_commit: 566840c330e867a15313923c87c20b6863cb053f
ops_r15_audit_commit: 42a79a655974b37e28a89d31b5f72ffea83927f4
consolidation_date: 2026-07-28
consolidation_branch: research/stage0-anchor-consolidation
authoritative_for:
  - cross-audit synthesis at recorded commits
  - proposed Stage-0 research amendments
  - candidate additional-research sequencing
may_not_use_for:
  - production capability claim
  - final code contract
  - canonical owner assignment
  - authority grant
  - legal compliance conclusion
  - implementation authorization
  - production benchmark passage
  - production RPO or RTO commitment
  - automatic amendment of authoritative backlogs or decisions
research_only: true
---

# Stage-0 Research Amendment Plan

## Source limitation

The original PAO-R0 and PAO-R1 reports were not committed on the baseline or
audit branches and no byte-identical source was available during
consolidation. The amendments below are exhaustive only for positions quoted or
covered by their audit ledgers/recommended revisions. Any uncaptured
section-level rewrite is `source_artifact_required`.

The OPS-R15 audit records a 2,672-line source with SHA-256
`0c3baf41df8ae02bd9f9ae88cc9f1a350d7f4e33021a94327c3e578044690d15`;
that original was not committed with the audit. Its event/metric/state ledgers
are sufficient for the listed amendments, but the source must be persisted
before ratification.

## PAO-R0 amendment plan

**Recommended final research verdict:** `research_supported_with_open_owner`
(equivalent in this synthesis framework to `accept_with_material_revisions`).

The report establishes the functional need and compatibility guard, but not a
canonical owner, contract, state model, temporal model, relation adjudicator,
or migration authorization.

| Exact section or covered location | Current conclusion | Audit defect | Replacement conclusion | Exact required action | Dependency | Urgency | Rewrite or supplement |
|---|---|---|---|---|---|---|---|
| Frontmatter/result | `accepted_narrow_scope`; research anchor may freeze design | Standing conflicts with immediate-binding language | `research_supported_with_open_owner`; compatibility guidance only | Replace result/standing and add source SHA once available | Stage-0 decision | P0 | Rewrite |
| Executive finding | Stable identity need plus near-complete candidate contract | Functional need and contract/owner claims conflated | Need above a case is ratified; `PolicyMatter` is candidate name; all production shape unresolved | Replace executive finding with wording below | S0-GAP-01 | P0 | Rewrite |
| Authority/compatibility freeze | “Immediately binding” or equivalent | Research artifact grants itself authority | New work should avoid irreversible ID assumptions pending accepted decision | Replace binding verbs; identify acceptance principal | team-architecture | P0 | Rewrite |
| Canonical owner §§2.8/7.7 | PDC presumptive owner; no new top-level owner justified | PDC README limits authority to graph structure | PDC is an integration neighborhood; owner unresolved | Delete owner conclusion and comparative winner | S0-GAP-01 | P0 | Rewrite |
| Runtime-quality owner | RQ admission/ID producer | No matter producer or adapter exists | RQ patterns may be reused after owner/producer acceptance | Downgrade to candidate bridge | S0-GAP-01 | P0 | Rewrite |
| Core audit owner | Core audit owns matter-custody events | Package verifier does not own event semantics | Core audit may package canonical events produced elsewhere | Correct owner role | Package README | P0 | Rewrite |
| Identity definition | `PolicyMatter` entity/envelope fields | Premature schema | Opaque accountability/custody hypothesis only | Move all fields to non-binding alternatives or remove | S0-GAP-01 | P1 | Rewrite |
| Support/status model | Shared `support_status` and resolution/lifecycle states | Parallel lattice and duplicate owners | Keep identity relation, evidence support, authority, resolution, and lifecycle separate | Delete common enum; map each concept | one-lattice rule | P0 | Rewrite |
| Matter relations | split/merge/successor/continuity rules presented as settled | Competence, direction, correction, and evidence inheritance unresolved | Relations are research questions; no authority/applicability inheritance | Add explicit uncertainty and external-evidence requirement | INT-R5, OPS-R2 | P1 | Rewrite |
| Cardinality | One matter/case model implied | Multi-matter PDC not evaluated | Preserve one-to-many and many-to-many compatibility | Add falsifier; remove cardinality assumption | S0-GAP-01 | P2 | Supplement |
| Common envelope | Identity/support envelope | Duplicates authority, provenance, lifecycle owners | Compose references to family/canonical contracts | Remove production-envelope proposal | P27 | P0 | Rewrite |
| Clocks | Nine mandatory timestamps | Pre-empts OPS-R4; current names conflict | Preserve only source/effect, custody/transaction, and correction/replay role distinctions when material | Remove field list; route algebra to OPS-R4 | OPS-R4 | P0 | Rewrite |
| Namespace/tenant | Immutable `origin_tenant_id`, transfer/federation assumptions | Not ratified; CAS content IDs can be shared while ownership remains tenant-scoped | Tenant scope is mandatory for authority use; namespace/transfer remain open | Remove immutable field claim; record decision-lineage tenant defect separately | S0-GAP-01/security | P0 | Rewrite |
| Migration | Existing IDs can be mapped under proposed plan | No owner/ABI or production migration proof | Do not reinterpret IDs; migration design deferred | Remove implementation authorization and claimed readiness | S0-GAP-01 | P1 | Rewrite |
| Sidecar correction | Sidecar association is sufficient | No matter-aware correction/public fan-out exists | Preserve signed bytes; sidecar is one unproven candidate | Replace sufficiency claim | PAO-R36/INT-R7 | P0 | Rewrite |
| Public/Atlas claims | Projection-only described as actual complete state | Active plan/code record authority-minting debt; redaction test failure | Projection-only is doctrine; current surfaces remain incomplete | Add capability and defect qualifications | Atlas/PAO-R36 | P0 | Rewrite |
| Lex owner | Lex owns legal source/version production | Offline producer is Data Forge legal | Data Forge producer → Lex runtime selector/evaluator | Correct every owner table/chain | Package policy | P0 | Rewrite |
| Capability labels | Types/test literals called implemented contracts/fixtures | No complete matter chain; named fixtures absent | Use chain labels and exact test-function names | Replace `contract_only` with missing-chain states; relabel fixtures | Repository capability doctrine | P0 | Rewrite |
| Failure patterns | Shifted P07/P08/P12/P13/P15/P26/P29/P32/P33 | Wrong remediation routing | Use exact register titles/IDs | Correct every occurrence | Failure register | P0 | Rewrite |
| External citations | DOI/ARK label mismatch; secondary bitemporal source | Citation/source standing defect | Use official DOI/ARK and primary temporal sources | Replace links/display text and bound claims | Source verification | P0 | Rewrite |

### PAO-R0 critical/high replacement wording

#### Executive finding

> The repository and ratified identity decision establish a functional need for
> stable PolicyOS custody identity above one Policy Design Case. No typed
> `PolicyMatter` contract or end-to-end capability exists. `PolicyMatter`
> remains a research hypothesis for an opaque accountability reference. This
> report does not assign its package owner, issuer, namespace, cardinality,
> relation adjudication, status model, temporal schema, migration, or public
> resolver. The safe compatibility guidance is to avoid silently reusing
> existing IDs, preserve signed/CAS history, keep future associations
> correctable, and never infer evidence applicability or legal continuity from
> identity continuity.

#### Owner statement

> PDC lineage is a plausible integration neighborhood, not an established
> canonical owner. `core.contracts`, runtime quality, core artifacts, core
> audit, and future H2 each own or may consume narrower concerns. A separate
> owner/ABI decision with P27 review is required before a contract is frozen.

#### Temporal statement

> PAO-R0 requires historical non-rewrite and the ability to distinguish
> source/effect, custody/transaction, and correction/replay roles when
> material. It does not define common clock fields. OPS-R4 owns the canonical
> temporal vocabulary and correction algebra.

#### Status statement

> Identity relation, relation-resolution outcome, evidence support, claim
> authority, and record lifecycle are distinct concepts owned by their
> canonical domains. PAO-R0 introduces no common `support_status`.

#### Correction statement

> Existing signed and CAS bytes must not be rewritten. A separately linked
> correction or association record is a candidate technique, not proof of a
> complete semantic or public-correction chain.

## PAO-R1 amendment plan

**Recommended final research verdict:** `accepted_narrower_scope`.

The decomposition method and a small anti-role/authority packet survive. The
213-row census remains non-authoritative research; the 21 `EC-*` entries remain
family questionnaires, not contracts.

| Exact section or covered location | Current conclusion | Audit defect | Replacement conclusion | Exact required action | Dependency | Urgency | Rewrite or supplement |
|---|---|---|---|---|---|---|---|
| Frontmatter/result | `accepted_narrow_scope`; Stage-0 baseline | Full register not safe baseline | `accepted_narrower_scope`; method/guidance only | Replace result and authoritative-for claims | Stage-0 decision | P0 | Rewrite |
| Executive/four zones | External functions often listed INTEGRATE | External act confused with evidence interface | External act remains externally owned/PolicyOS execution prohibited; evidence relation I; admission/reaction O | Replace zone table and examples | ID §5 | P0 | Rewrite |
| Unit of analysis | One row combines function, claim, operator, evidence, reaction | Denormalized row still contains several verdict planes and can explode | Use linked analytical objects/planes; no required storage row | Replace formula and schema implication | Stage-0 kernel | P0 | Rewrite |
| Appendix C | 213 rows as adjudication register | 100 require split, 12 merge, 127 unresolved/pilot dependent | Retain as non-authoritative census/questionnaire or reduce to exemplars | Remove “full baseline” standing; attach audit dispositions | Partner/pilot facts | P0 | Supplement then rewrite |
| Owner fields | “At least four,” then operator/state/producer/adapter/consumer/reaction/projection/team | Roles, owners, and completeness mixed | Use nine analytical roles only where proven; capability state separate | Replace `owner_state` and compound aliases | Owner map | P0 | Rewrite |
| Canonical owner map | PDC/RQ/team/future tasks named as owners | Owner unproven; tasks are not runtime owners | Use implemented package owner, integration neighborhood, future consumer, external operator, unresolved | Replace every map entry | S0-GAP-01/family owners | P0 | Rewrite |
| Evidence catalogue D | EC-01..21 presented as candidate contracts inheriting envelope | Taxonomy duplicates family owners and mixes stages | Recast as research question families; compose existing contracts | Rename catalogue and remove inheritance | INT-R2/OPS-R4 | P0 | Rewrite |
| Institutional envelope §7.3 | Universal fields, states, downstream actions | P13/P27; external fact+admission+reaction mixed | No universal production envelope; separate fact, receipt, admission, reaction, projection | Delete schema; keep composition diagram | Family owners | P0 | Rewrite |
| Status systems §§4.7–4.9/7 | Evidence/boundary/owner/implementation states | Parallel lattices without transition owner | Report-local audit labels only; map or defer | Delete runtime implication/status transitions | one-lattice | P0 | Rewrite |
| Clocks/direct answer 13 | Ten required; five per I row | Pre-empts OPS-R4 | Require semantic role non-collapse only | Delete clock bundle | OPS-R4 | P0 | Rewrite |
| Absence grammar | Generic contract selects block/recompute/withdraw | Consumer materiality and legal duties vary | Source/receipt records condition; canonical consumer selects reaction | Split evidence disposition from reaction | OPS-R2/family owners | P0 | Rewrite |
| OBSERVE | Observation may be promoted | Promotion transition underdefined | Acquisition/review trigger has no authority; new purpose-bound admitted artifact required | Add explicit firewall | Admission owners | P0 | Rewrite |
| Stage-0 governance | Quarterly review, challenge receipt, mass freeze, kill rules | Unratified governance/workflow | Recommendations only; owner acceptance required | Remove mandatory cadence/receipt/freeze | team-architecture/OPS-R2 | P0 | Rewrite |
| Policy matter | Optional dependency but standard field | Silently pre-decides PAO-R0 | Opaque optional subject ref in research only | Remove `policy_matter_ref` from common requirements | S0-GAP-01 | P0 | Rewrite |
| Deferred Appendix E | Reclassifies tasks; includes active OPS-R14/PAO-R36; cites unavailable Rev-1 | Status/history not reproducible | Current-W2 observations only; proposed changes separate | Remove reclassification authority and historical claim | W2 owner | P0 | Rewrite |
| Capability states | Undefined abbreviations and future tasks as owners | Inconsistent repository vocabulary | Use exact chain labels per family | Replace entire state legend | Capability doctrine | P0 | Rewrite |
| Failure patterns/fixtures | Multiple wrong IDs; `M31` as pattern; BND fixtures implied | Wrong IDs and no executable corpus | Correct IDs; say proposed fixtures | Rewrite Appendix F status | Failure register/OPS-R15 | P0 | Rewrite |
| External sources | W3 working draft, GAO label/press release, OECD press release | Noncanonical/misleading sources | Use final W3C PROV-O, GAO Green Book, OECD report; narrow jurisdiction claims | Replace citations | Source verification | P0 | Rewrite |

### PAO-R1 critical/high replacement wording

#### Executive finding

> The ratified four-way test is supportable when applied to one declared plane
> at a time. For an external act that affects a PolicyOS claim, the act remains
> externally owned and PolicyOS execution is prohibited; the evidence
> relationship is INTEGRATE; purpose-specific admission and the scoped reaction
> of PolicyOS-owned claims are OWN; the publication owner supplies the governed
> projection and Atlas only renders it. The 213-row census and 21 evidence
> families are non-authoritative research hypotheses, not a frozen Stage-0
> register or contract catalogue.

#### Register standing

> Appendix C is a boundary-review questionnaire and candidate census. A row
> cannot constrain architecture until its planes are split, external operator
> and competence are evidenced for the relevant jurisdiction/time, canonical
> internal owners accept their roles, and claim-specific absence behavior is
> supplied.

#### Evidence architecture

> Do not create a universal `InstitutionalEvidenceEnvelope`. Compose a
> family-native external fact with existing transport/provenance and authority
> references, a separately owned admission receipt, a consumer-owned reaction,
> and a publication-owned projection.

#### Absence behavior

> Missing, late, stale, contradictory, revoked, or unavailable evidence is not
> evidence of non-occurrence. The evidence/source layer records the condition
> and admission disposition; the canonical claim consumer owns materiality and
> the least-expansive safe reaction.

#### Governance standing

> Review cadence, challenge workflow, mass-impact freeze, owner assignment, and
> task disposition are proposals for acceptance by their competent owners.
> PAO-R1 does not ratify them.

## OPS-R15 amendment plan

**Recommended final research verdict:** `blocked_pending_oracle_independence`;
retain the semantic conformance kernel and extension architecture as
non-authoritative research.

| Exact section or covered location | Current conclusion | Audit defect | Replacement conclusion | Exact required action | Dependency | Urgency | Rewrite or supplement |
|---|---|---|---|---|---|---|---|
| Frontmatter/result | `accepted_narrow_scope` | Benchmark not executable/independent | `blocked_pending_oracle_independence` | Replace result and capability wording | S0-GAP-02 | P0 | Rewrite |
| Executive finding | 24-month capstone is Stage-0 benchmark | Prose calendar, visible answers, no runner/oracle | Calendar is scenario catalogue; kernel is research guidance | Replace finding with wording below | Stage-0 kernel | P0 | Rewrite |
| Bounded claim | Passage proves custody composition broadly | External validity too wide | Pass is revision/environment/fixture/evaluator bounded | Add exact bounded claim | Benchmark governance | P0 | Rewrite |
| Calendar | 117 rows form frozen executable trace | 87 calendar-only names, zero executable rows, expectations visible | Input-only fixtures plus sealed expectations; extension split | Remove visible expected columns from implementation package | S0-GAP-02/domain tasks | P0 | Rewrite |
| Event vocabulary | 92 types cover calendar | 117 one-off names; 62 unused declared types | Test-family discriminators with explicit schema mapping | Normalize only when engineering corpus exists | S0-GAP-02 | P1 | Rewrite |
| Event envelope | Common production-style wrapper includes expected actions/oracle | Leakage and duplicate owner; mixed stages | Benchmark-only input wrapper; receipt/admission/reaction are outputs | Remove expected/prohibited/oracle fields from visible input | PAO-R1 method | P0 | Rewrite |
| Multi-clock model | Thirteen fields common | Pre-empts OPS-R4 and lacks universal meaning | Family clocks plus evaluator delivery/storage refs; OPS-R4 owns production algebra | Remove common requirement | OPS-R4 | P0 | Rewrite |
| State machines | Exact case/evidence/public/world states | Parallel runtime design | Observable semantic predicates; internal representation free | Replace state equality with predicates | Family owners | P0 | Rewrite |
| Typed wakes | Exact enum/state transition | Semantic property good, contract premature | Exact subject/scope match; wake is candidate, no authority | Preserve predicate; defer enum | OPS-R1 | P1 | Rewrite |
| Twenty resume gates | All gates on every resume | Conditional/action/public checks mixed; DoS risk | Core, conditional, action-specific, pre-publication, asynchronous protections | Replace universal gate list | OPS-R1/3/INT-R5 | P0 | Rewrite |
| Dependency graphs/impact sets | Two physical graphs/five sets | Semantic distinction valid, physical/exhaustive design premature | Content and authority dependencies distinct; representation/overlap open | Convert to predicates and profile outputs | OPS-R2 | P1 | Rewrite |
| WorldRelease | Exact vector/states/head swap | OPS-R8 pre-emption | Optional extension assumptions only | Move whole scenario to OPS-R8 pack | OPS-R8 | P0 | Rewrite |
| Matter split/successor | Expected oracle truth | PAO-R0 owner/relation unresolved | Optional fixture axioms after consolidation | Move to matter-lineage extension | S0-GAP-01 | P0 | Rewrite |
| External/human scenarios | Synthetic authority outcomes treated as truth | Jurisdiction/competence/reviewer protocol missing | Scenario axioms, contested ranges, raw reviewer labels | Add scope/provenance/disagreement | INT-R5/S0-GAP-02/pilot | P0 | Rewrite |
| Semantic oracle | Same report authors trace | Circular | Versioned sealed predicates, independent authorship/custody | Remove executable claim until delivered | S0-GAP-02 | P0 | Rewrite |
| Clean rebuild | Parity is semantic oracle | Same reducers/deps reproduce defect | Same-code parity diagnostic; independent declarative evaluator required | Rewrite oracle hierarchy | S0-GAP-02 | P0 | Rewrite |
| Hidden fixtures | Conceptual sealing | No access, commitment, rotation, leakage model | Four-package model with commitments/access logs/immutable runs | Add governance protocol; keep blocked until exercised | S0-GAP-02 | P0 | Rewrite |
| Metrics | Zero sentinels plus ratios/thresholds | Open denominators, unobservable terms, Goodhart risk | Closed per-event predicates; recall only against independent truth; efficiency diagnostic | Redefine formulas; remove arbitrary cutoffs | OPS-R2/S0-GAP-02 | P0 | Rewrite |
| RPO/RTO | Zero RPO and 1–72h targets | No topology/wall-clock basis | Classify semantic/synthetic/deployment SLOs; numbers illustrative only | Move to OPS-R14 extension | OPS-R14/pilot | P0 | Rewrite |
| Failure-pattern Appendix | “Detected” | No OPS-R15 runner | “Represented by proposed fixture; untested” | Correct every status/ID | Failure register | P0 | Rewrite |
| Contract sketches | Candidate H2/event/state contracts | Hidden architecture prescription | Research-only examples or remove; no canonical owner | Move to task-owned extensions | Group-B tasks | P1 | Rewrite |
| Stage-0 anchor | Complete capstone constrains Group B | Oracle and dependencies blocked | Consensus kernel constrains research semantically only | Replace packet with S0-K01–K16 references | Stage-0 decision | P0 | Rewrite |

### OPS-R15 critical/high replacement wording

#### Executive finding

> PolicyOS custody is benchmarkable as observable semantic predicates, but the
> delivered 24-month Markdown calendar is not an independent executable
> benchmark. Inputs and expected results are co-located, event vocabulary does
> not normalize the calendar, no machine-readable corpus or runner exists, the
> semantic and authority oracles are self-authored, and clean rebuild need not
> be implementation-independent. The scenario catalogue and corrected
> conformance profiles are retained as research; benchmark execution is blocked
> pending an independent oracle/evaluator architecture.

#### Bounded pass claim

> A pass may state only that the named implementation and repository revision,
> in the recorded environment, satisfied the committed predicates for the
> closed fixture population, declared scenario axioms, and evaluator version.
> It does not establish legal compliance, institutional competence, production
> resilience, production readiness, or authority to perform an external act.

#### Clean-rebuild statement

> A full rebuild using implementation reducers, admission code, dependency
> traversal, or status projection is a consistency check. Semantic correctness
> requires an independently owned declarative evaluator with an explicit
> equivalence relation and no shared semantic implementation.

#### Resume statement

> The benchmark requires equivalent action-specific protection: durable
> reconstruction, exact subject/tenant/jurisdiction binding, integrity,
> authorization, fresh evidence/authority, compatibility, and applicable human
> conditions before the protected action. It does not require all twenty named
> checks at one universal resume boundary.

#### Metrics/RPO-RTO statement

> Critical semantic predicates use closed populations and independently
> established expected results. Reuse, precision, minimal recomputation,
> escalation, latency, and recovery time are diagnostic until their
> denominators, environment, and evidence basis are fixed. Stage 0 sets no
> production RPO or RTO.

## Transitive patch obligations

| If this change is accepted | PAO-R0 consequence | PAO-R1 consequence | OPS-R15 consequence |
|---|---|---|---|
| PolicyMatter owner remains unresolved | Remove PDC owner | Remove PDC/matter fields from owner/register grammar | Use fixture-local subject; matter pack deferred |
| Universal envelope rejected | Remove support envelope | Remove institutional envelope/inheritance | Keep input-only test wrapper |
| Status machines rejected | Separate identity/support/authority/lifecycle | Remove evidence/boundary/owner lattices | Convert states to predicates |
| Clocks assigned to OPS-R4 | Remove nine-field requirement | Remove ten/five-field requirement | Remove thirteen-field envelope |
| Boundary census becomes method | Use only external-evidence distinction | Census non-authoritative | Oracle cannot import 213 rows |
| Oracle blocked | Fixtures remain proposed | BND fixtures remain examples | No executable/pass claim |
| Atlas is renderer only | Correct public-owner map | Correct projection owner role | Crawl canonical projections; do not use UI as oracle source |
| Public correction incomplete | Sidecar not sufficient | Public states unresolved | Public profile conditional on PAO-R36 |
| Tenant/jurisdiction defects separated | Do not encode defects as identity theory | Keep scope invariant | Negative fixtures remain; capability claim removed |

## Amendment acceptance gate

The three original reports should not be marked completed Stage-0 anchors until:

1. their source bytes and hashes are persisted;
2. the replacement executive findings and standing are accepted;
3. every cross-anchor owner, envelope, status, and clock overclaim is removed;
4. repository defects are linked as separate engineering work rather than
   research conclusions;
5. the consensus kernel is accepted or amended by `team-architecture`;
6. OPS-R15 explicitly remains non-executable pending S0-GAP-02.
