---
title: Stage-0 Owner, Contract, and Vocabulary Map
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

# Stage-0 Owner, Contract, and Vocabulary Map

## Owner-category rule

The synthesis uses the following categories and does not collapse them:

| Category | Meaning |
|---|---|
| `ratified_owner` | A ratified decision assigns the function, not necessarily a package |
| `current_implemented_owner` | Code/package owns the implemented contract or transition |
| `partial_owner` | Owns a bounded element of an incomplete chain |
| `integration_neighborhood` | Plausible composition point; not canonical owner proof |
| `projection_owner` | Produces or renders a view; cannot mint source authority |
| `future_consumer` | Expected to consume a contract after later design |
| `research_owner` | Owns inquiry/recommendation only |
| `external_institution_owner` | Performs or authoritatively decides an external function |
| `owner_unresolved` | No accepted semantic owner exists |

`team-architecture`, a future task ID, and H2 are not current runtime owners.

## Conservative owner map

| Concept | Ratified function owner | Current implemented owner | Other role(s) | Conflict or gap | Consolidated posture |
|---|---|---|---|---|---|
| Above-case technical custody identity | PolicyOS (`ratified_owner`) | None | PDC and `core.contracts` are integration neighborhoods; RQ candidate validator; H2 future consumer | Semantic owner/issuer/ABI unresolved | S0-GAP-01; do not assign PDC by implication |
| PDC graph structure | PolicyOS/PDC boundary | `polisyos.pdc` (`current_implemented_owner`) | RQ validates/projections consume | Graph authority is not matter or claim authority | Preserve exact README boundary |
| Matter relations/episodes | PolicyOS owns correct association of its records; competent external bodies own legal succession facts | None | INT-R5 external competence; OPS-R2 applicability dependencies | Relation vocabulary, cardinality, correction, adjudication unresolved | Research-only; no automatic authority inheritance |
| Function-level boundary decision | PolicyOS owns truthful self-boundary | None | PAO-R1/team architecture `research_owner`; PDC/RQ integration neighborhoods | No `OperationalBoundaryDecision` producer/store/verifier | Keep as method/census, not runtime owner |
| Family-native source/evidence contract | Family-dependent | Fabric, Lex/Data Forge, DDM, authorization, audit, lifecycle owners in their scopes | External producer may be competent institution | No generic cross-family owner | Preserve family contracts |
| Transport/provenance receipt | PolicyOS for its receipt | Fabric/provenance/audit patterns (`partial_owner`) | RQ possible verification bridge | Shape differs by family | Compose by reference; no universal super-schema |
| Evidence verification/admission | PolicyOS for use of its claims | RQ/PDC and family verifiers in bounded paths | Source producer is not admission owner | No generic institutional admission chain | Owner selected per consumer/family |
| `AuthorityBoundary` | PolicyOS authority grammar | PDC contract and RQ use (`current_implemented_owner` in current scope) | Claim owners consume | Not proven as every legal/audit/security payload schema | Reuse purpose-scoped grammar by reference; do not force payload shape |
| Claim dependency/reaction | PolicyOS claim owner | Decision-validity/Scientist lifecycle/PDC owners in bounded scopes | OPS-R2 research; H2 future orchestrator | No complete cross-family index/fan-out | Consumer owns materiality and reaction |
| Temporal vocabulary | PolicyOS custody function | Distributed current owners | OPS-R4 `research_owner` | Names/ordering/placement conflict | Defer canonical algebra to OPS-R4 |
| Durable suspension/resume | PolicyOS custody function | Control plane and Scientist own narrower mechanics (`partial_owner`) | OPS-R1/3 research; H2 future consumer/orchestrator | No case-level end-to-end chain or full binding | Require observable equivalent protection only |
| Legal corpus production | PolicyOS sensory path | Data Forge legal (`current_implemented_owner`) | Official external publishers produce source facts | Sole-Lex wording wrong | Data Forge producer → Lex consumer |
| Legal runtime selection/applicability | PolicyOS analytical custody | Lex (`current_implemented_owner`/partial chain) | Jurisdiction packs and competent bodies external | Continuous cross-jurisdiction chain incomplete | Preserve split and jurisdiction limitation |
| Monitoring/KPI evidence | PolicyOS owns claim monitoring/diagnosis; external operators own collection/operation where applicable | DDM, feedback, Scientist (`partial_owner`) | OPS-R5/INT-R4 research | No unified KPI-control capability | Family-native and task-owned |
| Internal authorization | PolicyOS | Runtime HTTP/DS20 path (`current_implemented_owner`) | Audit event records admission | Allow is not handler/external execution | Preserve semantic distinction |
| Core audit package | PolicyOS | `core.audit` (`current_implemented_owner`) | External auditor is separate owner of opinion | Package could be mislabelled independent audit | Package/verifier only |
| Artifact integrity/signature | PolicyOS | core artifacts/signing (`current_implemented_owner`) | INT-R7 research for long-term verification | Integrity-valid can be semantically stale | Preserve bytes; lifecycle owner supplies currentness |
| Public record/correction | PolicyOS for records it publishes | Publication/lifecycle components (`partial_owner`) | PAO-R36/INT-R7/INT-R8 research; Atlas renderer | No complete cross-surface fan-out; redaction defect | Exact contract deferred; stale/current honesty is invariant |
| Atlas projection | PolicyOS publication discipline | Atlas (`projection_owner`) | Upstream publication owner must supply authority | Current readiness panels still mint locally | Renderer only; engineering debt separate |
| Custody capstone governance | Research programme | None | OPS-R15/team architecture `research_owner`; independent oracle custodian unresolved | No runner/oracle/evaluator | S0-GAP-02; no benchmark-pass claim |
| External adjudication/notice/payment/service/procurement/records acts | External institution | None in PolicyOS | Evidence adapter/consumer may exist later | Operator and legal effect need pilot/jurisdiction facts | External execution prohibited; evidence may be integrated |

## Capability-chain census

The state applies to the complete chain:

```text
typed contract
→ producer
→ persisted artifact/event
→ bridge
→ consumer
→ verification
→ surface or explicit exclusion
```

| Capability | Contract | Producer | Persistence | Bridge/consumer | Verification | Surface | Consolidated state |
|---|---|---|---|---|---|---|---|
| PDC graph structure | Typed | PDC compiler | PDC runtime artifact | PDC/RQ | Structural/semantic tests | Governed projections | `implemented` for graph structure only |
| Purpose-scoped authority boundary | Typed | Verifier path | In PDC/records as scoped | PDC/RQ consumers | Meet and verifier-only tests | Projection-bound | `implemented` in current domains |
| PolicyMatter | None | Missing | Missing | Missing | Missing | Missing | `planned_only`; owner unresolved |
| Matter relation/episode graph | Research sketch | Missing | Missing | Missing | Missing | Missing | `planned_only` |
| Operational boundary register | Research table | Research author only | Markdown only | No runtime consumer | Human audit only | Reviewer doc | `documented_only`; non-authoritative |
| Universal institutional evidence envelope | Research sketch | None | None | Duplicates owners | None | None | `premature_contract`; reject |
| Fabric source contract | Typed | Connectors/source onboarding | Contract/artifact records | Fabric/RQ consumers | Validation/replay/lineage tests | Internal or explicit exclusion | `implemented`, data-source oriented |
| Legal corpus/version | Typed family contracts | Data Forge legal | Legal releases/indexes | Lex runtime | Legal tests | Legal/internal surfaces | `implemented` fragments; continuous orchestration incomplete |
| Decision validity | Typed dependency/lifecycle events | Family producers | Decision-scoped store | Scientist validation/lifecycle | Unit tests | Internal/review paths | `implemented_but_not_orchestrated`; tenant qualification defect |
| Claim lifecycle/reissue | Typed | Scientist continuous governance | Append-oriented records | Claim/public consumers | Unit tests | Partial public/reviewer | `implemented` in scoped cases; full fan-out missing |
| DDM incident/monitoring | Typed | DDM/feedback paths | Family artifacts | DDM/Scientist | Unit tests | Reviewer/internal | `partial_owner`; not full OPS-R5 |
| Internal authorization | Typed | Runtime HTTP/policy path | Append audit events | Handler gate | Authorization tests | Reviewer/internal | `implemented`; proves admission only |
| Core audit archive | Typed | Core audit assembler | CAS/archive | Offline verifier | Integrity/signature tests | Public/reviewer package | `implemented`; not independent audit opinion |
| Public signature longevity | Current signing contracts | Signing service | Signed artifacts/key data | Public verifier | Current tests | Public | `partial_owner`; long-term renewal planned |
| Public correction fan-out | Fragmented lifecycle/public contracts | Partial | Partial | Missing complete bridge | Partial tests | Incomplete | `implemented_but_not_orchestrated` / `surface_missing` |
| Durable job/checkpoint mechanics | Typed | Control plane/Scientist | Job/checkpoint stores | Workers | Unit tests | Internal | `implemented` mechanics; custody binding incomplete |
| H2 custody runtime | None | Missing | Missing | Missing | Missing | Missing | `planned_only` / future consumer |
| WorldRelease | Research/backlog sketch | Missing | Missing | Missing | Missing | Missing | `planned_only`; OPS-R8 |
| Independent OPS-R15 benchmark | Prose only | Missing oracle custodian | No machine corpus | No runner/evaluator | Missing | Report only | `documented_only`; blocked |

## Contract disposition map

| Proposed cross-anchor contract | Safe shared semantics | Family-native or separate semantics | Disposition |
|---|---|---|---|
| `PolicyMatter` | Opaque above-case reference need; attachability; non-reinterpretation | Issuance, namespace, cardinality, relations, authority, correction | S0-GAP-01; no schema freeze |
| `PolicyMatterEnvelope` / support envelope | Reference and provenance links only | Support, resolution, authority, lifecycle, public status | Reject common envelope |
| `OperationalBoundaryDecision` | Declared plane, narrow function/relationship, rationale, evidence need, uncertainty | Operator competence, admission contract, reaction, public state | Research method/census only |
| `InstitutionalEvidenceEnvelope` | Subject/scope/provenance/authority obligations as questions | Payload, clocks, verification, admission, correction, reaction | Reject universal persisted form |
| OPS-R15 common event envelope | Opaque fixture ID, family discriminator, scoped input refs, evaluator delivery control | Admission, expected results, actions, oracle labels | Benchmark-only input wrapper |
| `AuthorityBoundary` | Purpose-scoped permitted/prohibited use and weakest-boundary composition | Legal finality, audit opinion, security assurance, record disposition facts | Compose by reference; not universal payload |
| Admission receipt | Identity of input, verifier, purpose/scope, outcome, canonical refs | Family verification details and consumer reaction | Candidate shared pattern; owner/ABI not frozen |
| Consumer reaction | Dependency and canonical lifecycle references | Block/revalidate/reissue/withdraw semantics | Owned by claim/lifecycle consumer |
| Public projection | Attribution, as-of/currentness, evidence/authority qualification | Exact vocabulary, privacy, translation, cache protocol | PAO-R36/INT-R7/INT-R8/Atlas |

## Normalized vocabulary

| Concept | Use this meaning | Do not use it to mean | Canonical owner/status |
|---|---|---|---|
| `subject_reference` | Opaque reference to the thing a claim/evidence item concerns | Lifetime identity contract or authority | Owner unresolved; fixture-local until S0-GAP-01 |
| `case_id` | Identity of a Policy Design Case in its current domain | Lifetime policy/matter identity | Current case/PDC owner |
| `run_id` / `job_id` | Execution/control identity | Case or matter continuity | Runtime/control plane |
| `ArtifactID` | Content identity | Real-world policy identity or current authority | Core artifacts |
| `decision_lineage_key` | Decision-scoped lineage key | Global/tenant-safe matter identity | Decision-validity owner; tenant gap |
| `identity_relation` | Candidate/accepted relation between subject references | Evidence applicability or legal succession by itself | Future semantic owner; competence evidence external |
| `boundary_plane` | Act, evidence emission, receipt/admission, reaction, or projection | One mixed function row | Research method |
| `OWN` | PolicyOS owns the declared custody/epistemic plane | PolicyOS performs every external dependency | Ratified identity decision |
| `INTEGRATE` | External output can alter a PolicyOS claim, so PolicyOS owns the typed interface/admission duty | PolicyOS owns external execution | Ratified identity decision |
| `OBSERVE` | Context/signal without current authority effect | Unverified evidence with implicit effect | Ratified identity decision |
| `OUT_OF_SCOPE` | PolicyOS must not perform the act, or no legitimate custody relation exists | PolicyOS may ignore decisive external evidence | Ratified identity decision |
| `received` | Transport/custody fact | Authentic, competent, admitted, or binding | Transport/provenance owner |
| `authenticated` / `integrity_verified` | Source/channel or bytes checked | Semantically sufficient, legally competent, or admitted | Family verifier |
| `admitted` | Accepted for a declared purpose/claim under a boundary | Universally true or reusable | Canonical admission/claim owner |
| `claim_authority` | Current purpose-scoped authority posture | Evidence lifecycle, workflow, or benchmark result | One authority grammar |
| `lifecycle_posture` | Current/stale/contested/corrected/superseded/etc. within a canonical family | Global cross-product status | Family lifecycle owner |
| `public_posture` | Projection of canonical record/authority/lifecycle facts | New authority state | Publication owner; Atlas renders |
| `capability_state` | Completeness of contract→surface chain | Institutional ownership or evidence status | Repository capability doctrine |
| `benchmark_verdict` | Result for a committed evaluator/fixture/profile version | Runtime status, authority, legal compliance, or readiness | Benchmark governance only |
| `scenario_axiom` | Synthetic authority/institution fact assumed by a fixture | Universal legal ground truth | Oracle package with reviewer provenance |

## Rejected common vocabularies

The following must not become cross-product canonical enums through Stage 0:

- PAO-R0's common `support_status`;
- PAO-R1's `evidence_status`, boundary-decision workflow, `owner_state`, and
  compound implementation abbreviations;
- OPS-R15's case/evidence/public/world state machines, benchmark states, and
  exact public-verification labels;
- one global `status` field;
- a universal sequence from `received` to `binding`;
- `benchmark_passed` as a world-release or authority state.

They may survive as report-local analytical labels only when their standing and
mapping are explicit.

## Temporal role map

| Semantic role | Minimum Stage-0 statement | Current examples | Owner decision |
|---|---|---|---|
| Source occurrence/decision | Preserve when supplied and meaningful | Fabric event/valid time; legal act/event fields | Family native |
| Legal or operational effect | Distinct from publication/receipt when it changes applicability | Lex effective/legal-valid concepts | Family native plus OPS-R4 algebra |
| Observation | State whose observation and by whom; do not assume universal field | Fabric/runtime observation fields | Family native |
| Receipt/custody | PolicyOS can prove when it received/custodied an input | Connector/audit events in parts | Transport/admission owner |
| Admission | Prefer event/receipt reference over mandatory timestamp | RQ/PDC transitions in parts | Canonical verifier/claim owner |
| Transaction/history | Storage-assigned ordering for replay | Bitemporal/append stores in parts | OPS-R4 and storage owners |
| Publication | Public record event, not every evidence item's clock | Publication/lifecycle paths | Publication owner |
| Correction/revocation/supersession | Typed relation/event preserving old history | Lifecycle/decision-validity patterns | Family lifecycle owner |
| Processing/evaluator delivery | Diagnostic/benchmark clock, never content authority | Runtime and test harness | Runtime/evaluator only |

OPS-R4 must decide names, optionality, ordering constraints, late-event
categories, and whether a role is a timestamp, interval, version, or event
reference.

## Audited OPS-R15 predicate allocation

| Audited predicate | Consolidated standing | Dependency | Directly observable now? | Stage-0 use |
|---|---|---|---|---|
| K01 durable suspension | Research constraint | OPS-R1/H2 | Partial mechanics only | Retain outcome; not capability |
| K02 exact wake/look-alike rejection | `ratify_now` semantic predicate | OPS-R1 | No end-to-end path | Mandatory future profile |
| K03 duplicate wake/idempotence | Research constraint | OPS-R1/control plane | Mechanics testable in parts | Profile predicate |
| K04 case/tenant/cell binding | `ratify_now` safety predicate | S0-GAP-01, OPS-R1/3 | Current gap observable | Mandatory future profile |
| K05 fresh action-specific authority | `ratify_now` safety predicate | INT-R5, OPS-R1/3 | Partial | Equivalent protection required |
| K06 wrong tenant/unknown jurisdiction fail closed | `ratify_now` safety predicate | OPS-R11/security | Current negative failure exists | Mandatory; repository fix separate |
| K07 payload identity ≠ authority | `ratify_now` semantic predicate | OPS-R2 | Partial fragments | Mandatory future profile |
| K08 duplicate/permitted-order invariance | Research constraint | OPS-R4/owner semantics | Family-specific | Conditional profile |
| K09 append-only correction | `ratify_now` invariant | PAO-R36/OPS-R4 | Partial | Mandatory future profile |
| K10 cutoff historical replay | `ratify_now` invariant | OPS-R4/version owners | Partial | Mandatory future profile |
| K11 independent declarative rebuild | Additional inquiry prerequisite | S0-GAP-02 | No | Blocks executable benchmark |
| K12 affected-set recall | Research constraint | OPS-R2 + oracle | No closed truth set | Mandatory only after independent truth |
| K13 controlled-surface currentness/attribution | `ratify_now` semantic predicate | PAO-R36/Atlas | Partial/current debt | Mandatory future public profile |
| K14 external-act separation | `ratify_now` invariant | PAO-R1 method | Semantically auditable | Mandatory future profile |
| K15 asymmetric recovery | Extension/profile constraint | OPS-R14/H2 | No production-like harness | Not mandatory Stage-0 kernel passage |
| K16 ID/order/adjacent-case anti-overfit | `ratify_now` benchmark-governance predicate | S0-GAP-02 | No runner | Mandatory before scoring |

The final consensus kernel expresses these as sixteen cross-anchor statements,
not a claim that the audited 16-predicate benchmark is already executable.
