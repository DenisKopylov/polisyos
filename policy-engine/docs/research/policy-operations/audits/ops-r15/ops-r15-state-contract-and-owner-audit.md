---
title: OPS-R15 state contract and owner audit
status: draft_audit
kind: research-audit
research_task: OPS-R15
source_report_status: delivered
source_report_result_type: accepted_narrow_scope
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
pao_r0_audit_commit: 258aa740efcfb9e6771bfe52d4fdabc6b74f93a7
pao_r1_audit_commit: 566840c330e867a15313923c87c20b6863cb053f
audit_date: 2026-07-27
audit_branch: research/ops-r15-independent-audit
authoritative_for:
  - repository audit findings at recorded commits
  - benchmark-validity and executability findings
  - recommended corrections to OPS-R15
may_not_use_for:
  - production capability claim
  - legal compliance certification
  - final runtime contract
  - production RPO or RTO commitment
  - authority grant
  - implementation authorization
  - proof that an external institution performed an act
  - proof of disaster-recovery capability
research_only: true
---

# OPS-R15 State, Contract, Gate, and Owner Audit


## Overall finding

OPS-R15 correctly says its discriminators and state machines are research-level. It then gives them enough fields, transitions, owners and cross-task authority that they would function as a future H2 architecture if frozen. The safe benchmark form is observable predicates plus mappings to accepted owners. The report may require semantic protection; it may not require identical internal state names, one envelope, two graphs, five impact sets, fifteen enums or twenty atomic gates.

## State-machine audit

| State | Semantic kind | Claimed/correct owner | Public meaning | Disposition |
|---|---|---|---|---|
| `designing` (case) | workflow phase | GY/PDC workflow | No public authority | map to existing workflow predicate; do not freeze |
| `acquisition_required` (case) | terminal/refusal posture | PDC/RQ | Honest refusal with path | preserve semantic predicate |
| `suspended` (case) | custody workflow | future H2 | Waiting; worker released | predicate only; owner missing |
| `wake_pending` (case) | custody workflow | future H2 | Possible trigger; not resumed | predicate only; exact state deferred |
| `resume_review` (case) | custody workflow | future H2 + PDC/RQ | No authority action yet | predicate only; exact state deferred |
| `resumed` (case) | execution workflow | future H2/worker | No inherent public meaning | replace with permission receipt predicate |
| `revalidating` (case) | claim lifecycle | Decision-Validity/PDC | May be stale | map to existing owner |
| `human_review` (case) | review workflow | human-review owners | No automatic upgrade | conditional predicate; role/mandate required |
| `confirmed` (case) | claim support/authority projection | PDC/RQ | Current only within boundary | map; do not duplicate authority status |
| `limited` (case) | authority/public projection | PDC/publication | Current with visible limitations | map to boundary + projection |
| `blocked` (case) | authority/action result | PDC/RQ | Not permitted for blocked use | map; avoid universal case state |
| `reissued` (case) | record lifecycle | continuous governance/publication | New scoped current record | existing partial owner |
| `superseded` (case) | record lifecycle | continuous governance/publication | Replaced, historical | existing partial owner |
| `withdrawn` (case) | record lifecycle | continuous governance/publication | Reliance prohibited | existing partial owner |
| `historical_only` (case) | projection/retention | core audit/publication | History, never current authority | predicate; avoid evidence-state reuse |
| `received` (evidence) | receipt | family adapter/store | No authority | preserve predicate |
| `authenticated` (evidence) | source/integrity verification | family verifier | Identity/integrity only | split crypto/source checks |
| `verified` (evidence) | ambiguous verification | family verifier | Must say what was verified | replace with typed verification results |
| `admitted` (evidence) | purpose-specific admission | runtime quality/PDC | May affect named claim/use | preserve predicate with boundary |
| `quarantined` (evidence) | intake workflow | adapter/security | No claim effect | local state, not common authority |
| `rejected` (evidence) | intake/admission result | adapter/RQ | No claim effect | local result; preserve reason |
| `stale` (evidence) | freshness result | consumer/Decision-Validity | No current use for affected purpose | map to existing lifecycle |
| `disputed` (evidence) | evidence conflict | consumer/human forum | Weakest boundary | set-valued, not automatic transition |
| `corrected` (evidence) | evidence lineage | external producer + admission owner | Old object retained | model as successor event/link |
| `revoked` (evidence) | authority/evidence event | competent revoker + admission owner | Prior use revalidated | model as event/link |
| `superseded` (evidence) | evidence lineage | producer/admission owner | Old evidence historical | model as event/link |
| `historical_only` (evidence) | retention projection | core audit/family owner | Not current | predicate; avoid parallel enum |
| `draft` (public) | publication workflow | publication owner | Not public | owner mapping required |
| `published_current` (public) | public predicate | publication/PDC | Current within stated boundary | replace with currentness predicate |
| `limited` (public) | public predicate | publication/PDC | Visible limits | do not duplicate PDC limited state |
| `correction_pending` (public) | publication workflow | PAO-R36/publication | Pending correction visible if material | task-specific mapping |
| `corrected` (public) | record lineage | PAO-R36/publication | Successor/correction linked | append-only predicate |
| `superseded` (public) | record lineage | publication | Replaced | append-only predicate |
| `withdrawn` (public) | record lifecycle | publication | Reliance prohibited | map to canonical record lifecycle |
| `verification_degraded` (public) | verification projection | core audit/security/publication | Integrity/current verifier limited | keep separate from semantic currentness |
| `archived` (public) | retention/projection | core audit/archive | Historical access | profile-specific |
| `candidate` (world) | release workflow | OPS-R8/Fabric | No authority | extension only |
| `shadow` (world) | release workflow | OPS-R8/Fabric | No current authority | extension only |
| `benchmark_passed` (world) | evaluation result | independent evaluator | Pass is not authority | remove from runtime release lattice |
| `governed` (world) | release authority | unresolved OPS-R8 owner | Eligible only after governance | premature owner/state |
| `superseded` (world) | release lineage | OPS-R8 owner | Historical vector | extension only |
| `archived` (world) | retention | core/Fabric | Historical | extension only |


The appeal/incident “state machine” is not a state machine and is the strongest of the five models: it is a cross-owner causal sequence. Preserve it after changing “external process is INTEGRATE” to “external act is not PolicyOS performance; its typed evidence interface is INTEGRATE.”

### Predicate conversion

| Report state family | Mandatory observable predicates | Internal representation freedom |
|---|---|---|
| Case custody | no live worker required while suspended; exact wake binding; no authority action before applicable gates; append-only resume receipt | Jobs, workflow states and queues may use any names. |
| Evidence | source/integrity/competence/scope checks are distinguishable; admission is purpose-scoped; correction/revocation are append-only | Family owners keep local status/results. |
| Public | currentness, limitations, as-of time and successor/correction links are truthful across controlled surfaces | Publication owner chooses canonical state model. |
| World release | unverified component mixtures cannot be current; historical vectors remain replayable | OPS-R8 decides whether a WorldRelease object/state machine exists. |

## Common event-envelope field audit

| Field | Legitimate fixture role | Proper owner | Risk / disposition |
|---|---|---|---|
| `fixture_event_id` | Test identity | benchmark governance | Keep test-only; never branch semantically on value. |
| `event_type` | Input discriminator | family schema + benchmark mapping | Keep after resolving 87/62 mismatch; not one production enum. |
| `producer_ref` | Evidence producer | source/family adapter | Keep; distinguish from operator. |
| `operator_ref` | External actor owning underlying act | institutional scenario/PAO-R1 | Keep as scenario fact, often provisional. |
| `boundary_class` | Fixture expectation/input constraint | ratified boundary + PAO-R1 | Do not encode expected verdict in visible input for classification tests; split act/interface. |
| `policy_matter_ref` | Optional fixture alias | PAO-R0 | Optional opaque assumption only. |
| `case_refs` | Scoped subjects | PDC/family consumer | Keep with tenant/cell binding. |
| `tenant_ref` | Security boundary | core security | Mandatory fail-closed where applicable. |
| `jurisdiction_refs` | Scope input | Lex/institutional profile | Keep; unknown must not silently fall back. |
| `event_time` | Source occurrence fact | source/family | Optional by family; provenance required. |
| `legal_effective_time` | Legal applicability fact | Lex/legal source | Legal profile only. |
| `valid_time` | Modeled assertion interval | family/model owner | Optional; OPS-R4 definition pending. |
| `publication_time` | Source publication fact | publisher/source | Optional by family. |
| `observation_time` | Ambiguous source or PolicyOS observation | source/adapter | Split source-observed from PolicyOS-observed if both matter. |
| `receipt_time` | Transport arrival | adapter/store | Storage/adapter owned. |
| `admission_time` | Purpose-specific admission | RQ/PDC | Consumer/admission receipt, not external event payload. |
| `processing_time` | Runtime diagnostic | runtime/H2 | Exclude from semantic identity; test-only diagnostic. |
| `transaction_time` | Durable record time | storage | Must be assigned by store, never trusted from fixture producer. |
| `correction_time` | Derived from correction event | family/store | Prefer `correction_of` event/link, not universal mutable slot. |
| `revocation_time` | Derived from revocation event | competent producer/store | Prefer `revokes` event/link. |
| `review_due_time` | Obligation/scheduler datum | OPS-R1/H2 | Not universal event time. |
| `expiry_time` | Dependency datum | rights/authority owner | Family-specific; may trigger watcher. |
| `dedupe_key` | Semantic idempotency identity | adapter/H2 | Keep; derivation/version must be specified. |
| `correction_of` | Append-only relation | family lineage | Keep where defined; unresolved target quarantines. |
| `revokes` | Append-only relation | authority/evidence lineage | Keep where competent and scoped. |
| `schema_version` | Payload compatibility | family schema owner | Keep; distinguish fixture wrapper vs payload version. |
| `rule_version` | Admission/reaction replay | admission/consumer owner | Keep as reference, not producer assertion. |
| `payload_ref` | Content address | CAS/family | Keep with tenant ownership. |
| `provenance_ref` | Source/activity/receipt chain | family/core audit | Keep; provenance does not prove competence. |
| `authority_boundary` | Purpose/denied-use result | PDC/RQ admission | Consumer/admission result, not raw external event fact. |
| `permitted_downstream_actions` | Expected/derived consumer behavior | action authorization/consumer | Remove from visible input; put policy inputs or sealed oracle, never let event grant action. |
| `prohibited_uses` | Boundary constraint | PDC/RQ/family contract | May be input evidence terms, but final denied uses are admission-owned. |

**Disposition:** retain a minimal test wrapper; compose family-native payloads, receipts and reactions. Reject it as a universal production event contract.

## Typed wake-condition audit

| Wake | Minimum binding supplied by report | Current owner/state | Audit verdict | Required correction |
|---|---|---|---|---|
| `data_watermark_reached` | Required dataset/partition, event-time watermark, source/version; look-alike: More rows from another source | Fabric; `implemented temporal seed; exact wake contract missing` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |
| `required_artifact_admitted` | Exact obligation ID, accepted artifact class, content binding; look-alike: Similar report or keyword match | RQ/PDC; `partial admission owner; H2 bridge missing` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |
| `legal_release_governed` | Governed legal-release vector, jurisdiction, effective scope; look-alike: Unofficial or shadow legal hit | Lex/OPS-R10/R11; `implemented_but_not_orchestrated` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |
| `human_decision_received` | Correct person/forum, role, mandate, TTL, active choice; look-alike: Email approval or wrong-role click | human-review/INT-R5; `contract_only/partial` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |
| `review_window_closed` | Declared window and late-event policy; look-alike: Processing delay alone | future H2 scheduler; `producer_missing` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |
| `scheduled_review_due` | Case/matter review obligation; look-alike: Generic cron without case binding | future H2 scheduler; `producer_missing` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |
| `incident_received` | Scoped incident evidence and status; look-alike: Media mention only | DDM + external adapter; `partial; institutional bridge missing` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |
| `appeal_outcome_admitted` | Competent body, claim/case scope, finality; look-alike: Appeal filed or narrative summary | contestability + RQ; `partial; external producer missing` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |
| `rule_changed` | Rule version, semantic diff, affected obligations; look-alike: File timestamp change | rule/validator governance; `partial; impact bridge missing` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |
| `validator_changed` | Validator version and compatibility/defect record; look-alike: New package version alone | rule/validator governance; `partial; impact bridge missing` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |
| `delegation_expiring` | Delegation ref, expiry, affected actions; look-alike: Generic personnel change | dependency watcher/H2; `planned_only` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |
| `license_expiring` | License/right ref, scope, affected uses; look-alike: Vendor newsletter | dependency watcher/H2; `planned_only` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |
| `public_record_correction_required` | Specific record/claim and correction basis; look-alike: Unverified complaint | PAO-R36/publication; `planned/partial` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |
| `source_recovered` | Source identity, health, gap census; look-alike: One successful HTTP response | Fabric/source monitor; `partial; gap census orchestration missing` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |
| `jurisdiction_pack_governed` | Pack identity, benchmark, authority and no-fallback proof; look-alike: Adding a code string | Lex/OPS-R10/R11; `implemented_but_not_orchestrated` | semantic property sound; exact enum premature | Require an immutable typed input and one dedupe-bound wake-evaluation receipt; allow owner-specific event names. |


The fifteen names are neither present as one runtime vocabulary nor required for a valid implementation. The invariant “wake permits evaluation, never automatic authority-bearing resume” is safe Stage 0.

## Twenty resume-gate audit

| # / gate | Report evidence / failure | Correct phase | Current owner | Universal? / atomicity | Verdict and correction |
|---|---|---|---|---|---|
| 1 / State integrity | CAS hashes, checkpoint/index consistency, suspension record<br>Failure: Block; recovery workflow | `unconditional core` | core artifacts/checkpoint/H2 | yes; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Integrity predicate for any stateful resume. |
| 2 / Policy-matter identity | Matter/case association and lineage state<br>Failure: Block or human identity review | `conditional/provisional` | PAO-R0 + PDC | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Matter closure only when the action depends on a matter; exact identity unresolved. |
| 3 / Case identity | Exact case and open obligation binding<br>Failure: Reject wrong case | `unconditional core` | PDC/H2 | yes; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Exact subject/case binding. |
| 4 / Tenant identity | Tenant/cell closure across state, event and evidence<br>Failure: Security block | `unconditional security` | core security/H2 | yes; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Tenant/cell closure is fail-closed. |
| 5 / Principal authentication | Current authenticated principal/service<br>Failure: Deny | `action-specific` | runtime authorization | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Required for active action; not necessarily passive historical reconstruction. |
| 6 / Action authorization | Exact resume/revalidate permission<br>Failure: Deny and audit | `action-specific` | runtime authorization | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Exact permission before the action, not a generic resume status. |
| 7 / Delegation/mandate | Current subject-matter/time/jurisdiction authority<br>Failure: Suspend or human review | `conditional authority` | INT-R5/PDC/Lex | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Only for actions needing mandate/delegation. |
| 8 / Permissions/step-up | Fresh purpose-bound high-stakes approval where required<br>Failure: Deny; no cached approval | `conditional high-stakes` | runtime authorization/DS20 | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Step-up where policy requires it; not universal. |
| 9 / Workflow compatibility | Workflow fingerprint or approved migration mode<br>Failure: Original environment, migrate/compare, or refuse | `unconditional when executing workflow` | Scientist checkpoint/OPS-R3 | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Equivalent migration/refusal protection is acceptable. |
| 10 / Schema compatibility | State/evidence schema compatibility<br>Failure: Migration dossier or block | `unconditional when decoding state` | schema owners/OPS-R3 | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Compatibility or explicit migration/refusal. |
| 11 / Rule compatibility | Closure-time and current rule versions, semantic diff<br>Failure: Replay old/new compare or revalidation | `conditional authority/current action` | rule owners/OPS-R3 | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Historical replay uses old rules; current action may require diff/revalidation. |
| 12 / Validator compatibility | Validator version, governance and known-defect state<br>Failure: Block until independently valid | `conditional authority/current action` | validator governance | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Known-defect and compatibility checks before reliance. |
| 13 / World-release compatibility | Governed compatible release vector<br>Failure: Reject latest-of-each mix | `conditional recompute/promotion` | OPS-R8/Fabric | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Not required for purely historical reads; exact WorldRelease unfinished. |
| 14 / Obligation status | Exact open/closed/unknown obligations and coverage envelope<br>Failure: Keep acquisition/open-world block | `conditional claim action` | PDC/INT-R1 | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Open obligations constrain relevant claims. |
| 15 / Dependency impact | Artifact and authority impact sets<br>Failure: No resume until impact closure | `asynchronous/conditional` | OPS-R2/H2 | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Complete impact before affected authority action/public current, not necessarily before safe diagnostic resume. |
| 16 / Evidence freshness | TTL, expiry, revocation and current source status<br>Failure: Mark stale; reacquire/revalidate | `conditional claim action` | source/admission/Decision-Validity | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Only evidence relied on for the action. |
| 17 / Budget/cost envelope | Spent/remaining compute, acquisition and human attention<br>Failure: Limit, replan or human decision | `action-specific/advisory` | resource economics/human principal | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Cost envelope may limit work; not semantic authority for every resume. |
| 18 / Certified operating envelope | Domain, stakes, actors, methods and modes remain in-envelope<br>Failure: Limit/abstain/human review | `action-specific` | PDC/RQ | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Required where method/output has a certified envelope. |
| 19 / Public-record implications | Current public records, correction/freeze requirements<br>Failure: Public freeze or correction before current display | `post-resume/pre-publication` | PAO-R36/publication | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Freeze/correct before current display; not a universal pre-resume gate. |
| 20 / Human-review requirements | Required independent/competent human decision exists<br>Failure: Remain suspended or blocked | `conditional action-specific` | human-review owner | conditional; One monolithic transaction is not required; the protected action must see one coherent decision snapshot. | Required only for decisions allocated to competent human review. |


### Corrected gate model

1. **Core pre-evaluation:** state integrity and exact case/tenant/cell binding.
2. **Conditional pre-action:** authentication, authorization, mandate/delegation, step-up, rule/validator/release compatibility, obligation and freshness for the exact action.
3. **Action-specific:** budget, certified envelope and human review.
4. **Before signing/publication/current display:** public implications, authority boundary, correction/freeze.
5. **Asynchronous but blocking affected use:** dependency fan-out may proceed after safe diagnostic resume; affected authority actions remain frozen until complete.

The evaluator checks equivalent protection and receipts. It does not require a single 20-gate function.

## CaseResumeReceipt audit

The sketch mixes legitimate audit facts with proposed runtime architecture:

- safe common receipt facts: receipt ID, exact case/tenant/cell, wake refs and dedupe key, generation, coherent gate outcomes, rule versions, input/evidence refs, resulting permission boundary;
- conditional/owner-specific facts: matter ref, budgets, public posture and human-review sets;
- premature OPS-R2 design: two dependency graphs and five named impact sets;
- unsafe authority implication: a receipt can prove checks and allowed PolicyOS action only; it cannot certify external facts, fairness or final legal authority.

Keep the receipt as a research schema split into: immutable input snapshot, gate decisions, protected action/result and audit provenance. Let OPS-R1/3/H2/PDC define final contracts.

## Dependency graphs and impact sets

The payload/authority distinction is semantic and should survive. The representation as two canonical graphs is not proven. Existing artifact lineage, AuthorityBoundary, Decision-Validity dependencies, source contracts and publication relations may compose into owner-specific indexes.

The five proposed sets can overlap:

- one claim may need recompute, authority revalidation, human review and public notice;
- `historical_only_set` is a resulting lifecycle predicate, not merely an impact traversal output;
- completeness cannot be inferred from the implementation's own reverse graph.

Benchmark fixtures must provide independently declared affected sets and allow the implementation to produce equivalent partitions.

## WorldRelease audit

The negative invariant—never promote an unverified latest-of-each combination—is strong. The exact nine-component vector, `candidate → shadow → benchmark_passed → governed → superseded → archived` lifecycle, atomic head and owner are OPS-R8/GY-N12/Fabric research. `benchmark_passed` is especially unsafe as a runtime release state because a benchmark result is not authority.

Disposition: optional world-release profile. Preserve compatibility, atomic-currentness, historical-vector and no-partial-fan-out predicates; defer schema/state/owner.

## Canonical owner and P27 audit

| Concept | Documented owner | Actual implementation owner | Missing role/conflict | Disposition |
|---|---|---|---|---|
| Purpose-scoped authority | PDC/RQ | PDC `AuthorityBoundary`, runtime-quality consumers | Longitudinal admission/reaction bridge | Extend; do not duplicate. |
| Computational checkpoint | Scientist | Scientist orchestration | Tenant/cell/authority custody metadata | Do not treat as custody resume. |
| Control scheduling | Runtime HTTP control | Control store/worker | Matter/case security closure and custody semantics | Reuse infrastructure only. |
| Source contracts/temporal | Fabric | Fabric + runtime temporal | Institutional family semantics/H2 bridge | Compose. |
| Legal source/change | Lex/Data Forge | Legal batch/Lex fragments | Continuous governed release/jurisdiction fail-closed | OPS-R10/R11 profile. |
| Claim invalidation/reissue | Decision-Validity/continuous governance | Core contracts + Scientist | Matter/fleet/public orchestration | Extend. |
| Public correction | PAO-R36/publication/Atlas | Distributed partial implementation | Canonical public state/feed owner | Predicate only pending owner. |
| Audit/signature | Core audit/security | Core audit/signing | Long-term public verification profile | Extend via INT-R7. |
| World release | OPS-R8/Fabric/GY-N12 | No production owner | Schema/head/compatibility governance | Defer. |
| Matter | PAO-R0/PDC candidate | No production owner | Identity/namespace/lineage consumers | Defer. |
| Operational boundary | PAO-R1/team architecture research | No production owner | Register/envelope rejected as freeze | Use ratified predicates only. |
| Custody orchestration | future H2 | No implementation | All end-to-end bridges | Future consumer; not external-act owner. |
| Benchmark governance | independent evaluator + architecture review | No operational owner | Oracle author, custodian, run evaluator separation | Establish before execution. |

`team-architecture` is a research/governance reviewer, not a runtime schema, admission, state or projection owner.

## Cross-task allocation

| OPS-R15 element | Classification | Primary destination |
|---|---|---|
| Semantic custody predicates | legitimate benchmark requirement | OPS-R15 kernel |
| Exact event enum/envelope | premature contract | OPS-R4 + family owners |
| Suspension/wake/resume states | cross-task interface constraint only | OPS-R1/3/future H2 |
| Dependency graph/set names | premature state/data model | OPS-R2 |
| Thirteen clocks | premature contract | OPS-R4 |
| KPI ladder | optional fixture | OPS-R5/INT-R4/DDM |
| WorldRelease vector/state | optional fixture/premature owner | OPS-R8/GY-N12/Fabric |
| Legal/jurisdiction results | scenario axioms | OPS-R10/R11/Lex |
| Long-term key/archive | optional fixture | INT-R7/OPS-R14/core audit |
| Matter split/inheritance | unsafe to freeze | PAO-R0 |
| Administrative stages | strong extension after split | PAO-R1/PAO-R4/PAO-R36 |
| Public labels | predicate, not state machine | PAO-R36/Atlas/publication |
| RPO/RTO | premature performance commitment | deployment/OPS-R14 |
