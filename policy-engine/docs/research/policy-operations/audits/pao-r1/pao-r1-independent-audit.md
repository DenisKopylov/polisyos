---
title: PAO-R1 Independent Repository Audit
status: draft_audit
kind: research-audit
research_task: PAO-R1
source_report_status: delivered
source_report_result_type: accepted_narrow_scope
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
pao_r0_audit_commit: 258aa740efcfb9e6771bfe52d4fdabc6b74f93a7
audit_date: 2026-07-26
audit_branch: research/pao-r1-independent-audit
authoritative_for:
  - repository audit findings at the recorded commits
  - recommended corrections to the PAO-R1 research artifact
may_not_use_for:
  - production capability claim
  - legal or institutional authority allocation
  - final code contract
  - production implementation authorization
  - automatic boundary adjudication
  - direct modification of authoritative plans
  - proof that an external institution performed a function
research_only: true
---

# PAO-R1 Independent Repository Audit

## 1. Audit scope and standing

This is an adversarial audit of the supplied, uncommitted research report, not an
endorsement or implementation. It tests repository facts, ownership, capability
state, internal consistency, external citations, and the authority claimed for
the proposed register. No production code, canonical contract, active plan, or
runtime status is changed.

The report was normalized as follows:

| Corpus | Count | Integrity result |
| --- | ---: | --- |
| Appendix-C register rows | **213** | IDs unique; 28 PD, 18 LG, 24 AP, 22 IM, 23 ML, 21 PR, 19 IR, 20 ORG, 19 FIN, 19 SEC |
| Supplied verdicts | **86 O / 114 I / 6 V / 7 X** | All rows have a verdict; many `I` rows conflate act and interface |
| Evidence contracts | **21** | `EC-01`–`EC-21`, contiguous and unique |
| Deferred-review entries | **38** | 36 deferred tasks plus active `OPS-R14` and active `PAO-R36` riders |
| Benchmark fixtures | **40** | `BND-001`–`BND-040`, contiguous and unique |
| Stage-0 rules | **10** | G.1–G.10 |
| Claim codes | **17** | C1–C17; research shorthand, not repository claim IDs |
| Absence codes | **9** | A1–A9; shorthand, not implemented status/reaction contracts |

Undefined or malformed vocabulary includes lifecycle codes `E`, `A`, `I`, `PR`
and `FIN`; owner/capability abbreviations `IBO`, `CO`, `PM`, `SM`, and `BM`; and
the use of `M31` as though it were a failure-pattern ID. The row ledger records
every supplied row and its disposition.

## 2. Historical and current baselines

| Baseline | Ref | Resolution |
| --- | --- | --- |
| A — historical | `4813b49f6ce14e8debf3aaea096f0967d38d9768` | Reproduced exactly |
| B — pinned current `main` | `4813b49f6ce14e8debf3aaea096f0967d38d9768` | Resolved before work; branch created from this SHA |

The two baselines are the same commit. There are therefore **no
historically-correct-now-stale repository claims** in this audit. A contrary
current/historical result would be methodologically impossible at these refs.
The baseline commit introduced both the identity decision and the Wave-2
backlog. Its parent has neither file. Current-state conclusions remain pinned
even if `main` advances later.

The report's claim that `honest-diagnostics-substrate.md` was missing or renamed
is false: both that file and
`honest-diagnostics-substrate-decision-log.md` exist at the inspected commit.
The Wave-2 statement that full Rev-1 specifications are in Git history is also
not reproducible: the backlog has exactly one reachable commit and is absent
from its parent.

### Commit-pinned evidence index

The row and claim ledgers use these evidence keys. Because A and B are identical,
each link supports both baseline columns.

| Key | Evidence |
| --- | --- |
| ID | [Ratified identity and four-way test, lines 88–139](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md#L88-L139) and [one-lattice/replay effects, lines 174–190](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md#L174-L190) |
| W2 | [Wave-2 OPS-R4, OPS-R14, PAO-R1 and PAO-R36](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md#L428-L460) |
| PDC | [`AuthorityBoundary` and `meet`](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py#L62-L114) |
| RQ | [`EvidenceAuthorityEnvelope`](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/runtime/quality/authority.py#L471-L605) |
| FAB | [Fabric `SourceContract`](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/fabric/connectors/contracts/source_contract.py#L382-L470) |
| REC | [ADR-0170 boundary and fail-closed outcome ingestion](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/adr/0170-contestability-and-recourse-boundaries.md#L51-L91) |
| DV | [Decision-validity status/events/clocks](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/contracts/decision_validity.py#L21-L208) |
| LIFE | [Scoped, append-only lifecycle bridge](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/scientist/governance/continuous/lifecycle_bridge.py#L102-L399) |
| AUD | [Portable audit assembler/verification package](https://github.com/DenisKopylov/polisyos/tree/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/audit) |
| EXT-AUD | [External-audit projection cannot mint authority](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/runtime/quality/external_audit.py#L260-L285) |
| AUTH | [Authorization receipt is admission, not handler success](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/runtime/http/access_audit.py#L85-L100) |
| PROV | [Entity/activity/agent/edge provenance model](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/contracts/provenance.py#L63-L174) |
| TIME | [`TemporalRef(valid_at, tx_at)`](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/contracts/runtime.py#L595-L626) |
| ATLAS | [Atlas records two surfaces that minted unproduced authority](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md#L1070-L1085) |
| RET | [Retention classes and immutable audit-package duties](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/reference/operations/retention-and-recovery.md#L13-L74) |
| FP | [Failure-pattern register](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/reference/policy-design-case-failure-patterns.md) |
| DIST | [M30 thin port and M31 separate authority axes](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/research/deep-research-value-distillation.md#L404-L435) |

## 3. Relationship to the PAO-R0 audit

The unmerged branch `research/pao-r0-independent-audit` exists at
`258aa740efcfb9e6771bfe52d4fdabc6b74f93a7`. It is a non-authoritative
cross-audit input. Its overall verdict is
`confirmed_with_material_revisions`.

| PAO-R1 dependency | Cross-audit classification | Consequence |
| --- | --- | --- |
| `policy_matter_ref` as mandatory/common subject | `requires_pao_r0_consolidation` | PAO-R0 audit found the PDC owner and namespace model unratified; keep optional research reference outside a common envelope |
| “Future PDC identity owner” | `contradicted_by_pao_r0_audit` | Replace with “canonical owner unresolved; PDC is one candidate neighborhood” |
| Multiple clocks | `consistent_with_pao_r0_audit` | Both reports pre-empt OPS-R4 |
| Shared envelope and local statuses | `consistent_with_pao_r0_audit` | Both create P27/parallel-lattice risk |
| Atlas projection-only doctrine | `consistent_with_pao_r0_audit` | Doctrine is ratified, implementation debt remains |
| Anti-role and claim-reaction principle | `independent_of_pao_r0` | Directly grounded in the identity decision |

There is no contradiction between the two audits. There is a material
contradiction between PAO-R1's PDC/matter assumptions and the qualified PAO-R0
owner finding.

## 4. Executive verdict

**Overall verdict: `accepted_narrower_scope`.**

The report's strongest contribution is the act/evidence/admission/reaction/
projection decomposition. It correctly prevents both administrative scope
inflation and epistemic responsibility evasion. The complete 213-row register,
21-contract catalogue, governance states, common envelope, clock set, and
deferred-task reclassifications are **not** safe as a shared Stage-0
adjudication baseline.

The safe anchor is smaller:

1. PolicyOS must not perform the ratified anti-roles.
2. A claim-relevant external act remains externally owned; its evidence
   interface is INTEGRATE; verification/admission and scoped reaction to
   PolicyOS claims are OWN.
3. Observation cannot alter authority without a separately admitted artifact.
4. Projection cannot mint authority or imply execution.
5. Missing claim-critical evidence cannot become a pass.
6. Existing owners and the single authority lattice must be reused.

| Component | Verdict |
| --- | --- |
| Four-way operationalization method | `confirmed_with_qualification` |
| Function-decomposition rule | `confirmed_with_material_revisions` |
| Ownership model | `partially_supported` |
| Institutional evidence envelope | `duplicate_owner_risk`; split/reject as universal contract |
| Absence-behavior grammar | Useful research checklist; `premature_contract` |
| Register state model | `parallel_lattice_risk` |
| Full Appendix-C register | `accepted_narrower_scope`; all external-act rows need plane separation |
| Appendix-D catalogue | Research taxonomy only; not 21 new contracts |
| Deferred activation review | `authority_overclaim`; advisory crosswalk only |
| Fixture proposal | Strong, unimplemented, pattern corrections required |
| Stage-0 packet | G.1/G.2 core preserved; remaining rules qualified or deferred |
| Ready to constrain all Wave-2 tasks | `contradicted` as authority claim |

## 5. Highest-severity findings

| ID | Severity | Finding | Evidence | Required correction |
| --- | --- | --- | --- | --- |
| H-01 | Critical | External acts are repeatedly labelled `INTEGRATE` in the same row as evidence receipt. This can be read as PolicyOS ownership of adjudication, payment, notice, service, procurement, records, or audit execution. | ID explicitly says “interface ours; function is not”; REC separates appeal administration from ingestion. | Use linked plane records. External act = externally owned and PolicyOS execution prohibited; evidence crossing = I; admission/reaction = O. |
| H-02 | Critical | The report disclaims a second lattice but proposes evidence, boundary-decision, owner, and implementation state systems without mappings or transition owners. | ID requires no new statuses; DV, lifecycle, PDC, Atlas and source contracts already own different state grammars. | Keep research labels outside runtime; map each proposed state to its canonical owner or mark unresolved. |
| H-03 | High | `InstitutionalEvidenceEnvelope` duplicates RQ authority, Fabric source, provenance, audit, lifecycle, decision-validity and family-native contracts, while mixing external fact, admission result, consumer reaction and public impact. | RQ, FAB, PROV, DV, LIFE, AUD. | Do not freeze it. Compose family payload + existing provenance/authority refs + separate admission receipt + consumer-owned reaction. |
| H-04 | High | The report freezes ten timestamps and requires five on every INTEGRATE row, pre-empting active OPS-R4. | W2 assigns the multi-clock model and `OperationalEventEnvelope` to OPS-R4; existing clocks conflict. | Freeze only the non-collapse requirement; let OPS-R4 name and place clocks. |
| H-05 | High | The Stage-0 baseline, quarterly review, mass-impact freeze, challenge receipt, and task reclassifications are unratified governance/workflow decisions. | Source frontmatter forbids authority grants; W2 describes research artifacts, not ratification. | Recast as proposed guidance requiring architecture/canonical-owner acceptance. |
| H-06 | High | PDC is treated as the future matter/register owner and runtime quality as the generic institutional admission owner without owner proof. | PDC's boundary is purpose-scoped; RQ has an overlapping envelope; PAO-R0 audit rejected presumed PDC ownership. | Mark owner unresolved and conduct P27 consolidation across actual owners. |
| H-07 | High | The report says the baseline supplies “most necessary owners,” but many are contract-only, partial, un-orchestrated, or future tasks. | REC explicitly limits contestability capability; LIFE is scoped to case claims; Atlas plan records missing producer binding. | Use capability-chain labels per family; never infer completeness from a type or plan. |
| H-08 | High | The Appendix-C owner/capability vocabulary contains undefined states and future research tasks as owners. | No source symbols for `owner_state`, `real_operator`, `claim_reaction_owner`; `PAO-R36`, `INT-R7`, `H2` are tasks/future, not current runtime owners. | Normalize roles separately from capability state; name implemented package owners only. |
| H-09 | High | Numerous failure-pattern citations are semantically wrong; `M31` is not a failure pattern. | FP and DIST. | Correct every fixture mapping before reuse. |
| H-10 | High | The claimed Rev-1 historical source is unavailable in Git, preventing reproducibility of deferred reclassifications. | `git log --all --follow` shows only baseline commit; parent lacks backlog. | Mark prior disposition comparison `not_reproducible`. |

## 6. Strongest Contributions Worth Preserving

| Report location | Contribution | Repository support | Limitation | Disposition / consumer |
| --- | --- | --- | --- | --- |
| Executive Finding; §4.2 | Separate external act, evidence emission, admission, reaction, and projection. | ID lines 103–118; REC lines 53–84; AUTH lines 93–99. | The register later collapses them back into one row. | Preserve with linked-object normalization; consume in OPS-R15. |
| §1.4 and counterexamples | Distinguish authorization, execution, settlement, reconciliation, notice dispatch, service, and legal effect. | AUTH proves allow ≠ success; identity anti-roles support the distinction. | External event semantics are jurisdiction/pilot facts. | Preserve with qualification; consume in PAO-R6/R20 and partner adapters. |
| §4.3 step 8 | Missing external evidence is unknown, never proof of non-occurrence. | ID's fail-closed contract and source/lifecycle gates. | Reaction depends on claim materiality and consumer. | Preserve as invariant; OPS-R4/R15. |
| §4.3 steps 4/6 | Separate real operator, evidence producer, adapter, reaction, and projection roles. | PROV has distinct agent/activity/entity concepts; repository wrappers otherwise obscure these roles. | Exact field set is not ratified; “owner” is overused. | Preserve as research model with corrected role names. |
| §4.7 and fixtures | Observation needs a new admitted artifact before authority changes. | Identity OBSERVE semantics; DDM distinguishes risk signals from action. | No generic transition contract exists. | Preserve; INT-R4/OPS-R5 semantic tests. |
| §5 | Audit package is not an independent audit opinion. | AUD and EXT-AUD. | External audit institution/mandate remain pilot facts. | Preserve unchanged; INT-R7/audit integration. |
| §2.6 and BND-025 | Detects technical `compensation.py` name collision. | The file implements saga rollback, not financial remedy. | Needs UI vocabulary lint, not a new contract. | Preserve unchanged; Atlas/public wording tests. |
| §6.2–6.5 | Metamorphic and fault-injection tests target scope inflation and responsibility understatement. | Existing verifier-only, projection-only, lifecycle, and contestability tests are reusable seeds. | No BND fixture exists; pattern IDs need correction. | Preserve with corrections; OPS-R15 benchmark. |
| §4.11 | Rejects a universal family-erasing `ExternalEvent`. | DIST M30 keeps family-native payloads. | Proposed common envelope recreates part of that risk. | Preserve the rejection; remove the universal envelope. |
| Appendix G.10 | `out_of_boundary_actions_attempted = 0`. | W2 OPS-R15 and ratified anti-roles. | Metric instrumentation is not implemented. | Preserve as proposed capstone sentinel. |

## 7. What the report gets right

The following repository claims are confirmed:

- the ratified four-way test and anti-roles exist;
- PDC has a purpose-scoped `AuthorityBoundary` whose `meet` intersects permitted
  uses, unions prohibited uses, and takes weaker evidence/decision axes;
- non-verifier Ring-2 writes are rejected by existing PDC tests;
- Fabric has a rich, data-oriented `SourceContract`;
- ADR-0170 separates PolicyOS contestability/outcome ingestion from external
  appeal administration;
- decision-validity and continuous-governance code support scoped append-only
  reactions and partial reissue;
- core audit produces portable verification packages, not auditor opinions;
- authorization allow records admission rather than handler success;
- Atlas is constitutionally projection-only;
- no implemented `OperationalBoundaryDecision`, `policy_matter_ref`,
  `InstitutionalEvidenceEnvelope`, generic proof-of-service contract, or BND
  fixture exists;
- no inspected production subsystem executes payments, legally effective
  notification, citizen service delivery, procurement, or case administration.

The last item is a bounded negative finding, not universal proof of absence.
Queries covered case-insensitive naming variants across `src`, `tests`, `docs`,
`schemas`, `architecture`, and `apps`; generated baselines and documentation
were included. Blind spots are runtime-only partner deployments, secrets,
unreachable branches, external services, and dependencies not present in the
checkout.

## 8. What is overstated

- `AuthorityBoundary` is not proven canonical for every institutional evidence
  family. The repository contains multiple purpose-specific authority envelopes.
- Lex does not alone own legal corpus production: Data Forge owns offline
  corpus/write/version builds; Lex is a runtime reader/evaluator.
- DDM has local drift/readiness/incident semantics, not a generic external
  institutional-incident admission service.
- runtime quality has a rich admission envelope but is not proved the owner of
  all legal, audit, records, payment, service, identity, and remedy admissions.
- Atlas is not the sole public-projection owner. Runtime API contracts,
  publication services, PDC projections, core audit, generated clients, and
  Atlas share the surface chain.
- “implemented” is too strong for lifetime validity fan-out, generic competence
  verification, public correction, partner adapters, and H2 orchestration.
- Named external operators are generic role hypotheses. Their competent legal
  identity cannot be established from the repository.

## 9. What is contradicted

- `honest-diagnostics-substrate.md` is present.
- no reachable Rev-1 backlog exists in Git history.
- “PDC future identity owner” is not established and conflicts with the PAO-R0
  audit.
- “no second status lattice” conflicts with four newly proposed state systems.
- “common envelope can be frozen now” conflicts with active OPS-R4 and existing
  distributed canonical owners.
- an `INTEGRATE` act row is not sufficient to express the identity decision's
  “function not ours” boundary.
- future task labels and `team-architecture` are not runtime producers or
  schema owners.

## 10. What is stale

No repository statement can be stale between the two baselines because the SHAs
are identical. External pages have moved or stronger final sources exist: the
W3C working draft, GAO press release, and OECD press release should be replaced.

## 11. Internal contradiction audit

| Contradiction | Consequence | Correction |
| --- | --- | --- |
| “At least four ownership fields” vs nine later owner/role fields | Roles, owners and capability states are mixed | Use the corrected role model in §16 |
| External execution is both `I` and an OUT anti-role | Can imply execution ownership | Plane-separate act and evidence |
| Family-native payloads vs one broad envelope | Recreates universal-event gravity | Common references only; family-native payload |
| No second lattice vs four candidate state systems | Parallel authority/workflow grammar | Keep research states non-runtime; map or defer |
| `research_only` vs “Stage-0 baseline”, “freeze now”, quarterly review | Unratified authority grant | Recast as proposed guidance |
| PolicyMatter is an external assumption but appears in every envelope | Premature subject constraint | Optional adapter-level reference after PAO-R0 |
| No universal `ExternalEvent` vs universal institutional envelope | Semantic contradiction | Split envelope, receipt, reaction |
| Claim reaction stored in external evidence | External producer appears to prescribe PolicyOS behavior | Consumer-owned impact/reaction record |
| Mass-impact freeze assumes OPS-R2 graph | Pre-empts active research | Requirement only; mechanism deferred |
| Owner state mixes institutional ownership and implementation completeness | Misleading capability conclusions | Separate `external_act_role` from capability chain |

The full contradiction ledger is in
`pao-r1-contradiction-and-consistency-ledger.md`.

## 12. Four-way-test interpretation

The report reads the high-level test substantially correctly but applies it to
an unstable unit. The identity decision itself says an external *function* can
be `INTEGRATE` while its interface is ours and the function is not. That word is
a relationship verdict, not ownership.

The safe interpretation is Model C:

| Plane | Ownership/verdict |
| --- | --- |
| External institutional act | External owner; PolicyOS execution prohibited (`X` as an execution boundary) |
| External evidence emission | External producer; evidence relationship `I` |
| Receipt, verification and claim-specific admission | PolicyOS `O`, through an existing canonical owner |
| Claim impact/reaction | PolicyOS `O`, scoped by dependency and materiality |
| Public projection | PolicyOS-owned rendering discipline; projection-only |

This does not replace the ratified four-way terms. It prevents `INTEGRATE` from
being misread as institutional ownership.

## 13. External act versus evidence-interface analysis

Every supplied `I` row is treated in the row ledger as requiring plane
separation unless it already describes only an evidence crossing. The most
dangerous mixed rows are court/appeal adjudication, legislation, legal hold,
notice/service, remedy execution, delivery, procurement, programme monitoring,
incident investigation/classification, audit/oversight, payments, records
decisions, identity issuance, hosting, and credential renewal.

Rows that already name evidence—proof of service, KPI observation, external
incident intake, admitted vendor evidence, settlement report—still require the
external production act to be separated from PolicyOS admission and reaction.

## 14. OWN/INTEGRATE/OBSERVE/OUT consistency

- **OWN:** strong for PolicyOS grounding, admission, signing, staleness,
  revalidation, correction, replay, internal authorization and bounded
  analytical functions. “Legal sensing,” “capacity assessment,” “monitoring,”
  “incident detection,” and “public verification” must be split into internal
  analysis versus external authoritative inputs.
- **INTEGRATE:** directionally correct for 114 rows, but structurally unsafe
  when a row names the act rather than the evidence relationship.
- **OBSERVE:** six rows are plausible candidate/risk signals, but the repository
  has no generic observation-to-admission transition. `ORG-04` becomes
  INTEGRATE when competence changes, as the identity decision itself suggests.
- **OUT:** the seven explicit anti-role rows are sound. OUT forbids PolicyOS
  performance; it does not forbid a separate, typed evidence link or
  claim-specific block.

## 15. Function-granularity analysis

The proposed product
`function × claim × operator × evidence × reaction` is useful as an
adjudication question but poor as a stored row. One act can affect multiple
claims; one artifact can support several functions; one operator can hold
several roles; jurisdiction and time can change the answer. Denormalizing every
combination creates combinatorial explosion and duplicate rows.

Use linked objects:

1. function/act definition;
2. jurisdiction-scoped operator/competence assertion;
3. family-native evidence contract;
4. claim-dependency binding;
5. admission receipt;
6. consumer reaction;
7. projection policy.

## 16. Ownership-model audit

Corrected model:

| Field | Meaning | Owner or role? |
| --- | --- | --- |
| `external_act_operator` | Institution legally/operationally performing the act | External role, jurisdiction-scoped |
| `evidence_issuer` | Actor/system asserting the evidence | Producer role; may differ from operator |
| `source_contract_owner` | Owner of transport/schema/source rules | Internal canonical schema owner |
| `admission_verifier` | PolicyOS component/person deciding purpose-specific admissibility | Internal runtime role |
| `claim_dependency_owner` | Canonical owner of affected claim linkage | Internal domain owner |
| `reaction_executor` | PolicyOS component that limits/revalidates/corrects its claim | Internal runtime role |
| `publication_owner` | Owner of published record/API | Internal canonical owner |
| `projection_renderer` | Atlas/client consuming authoritative projection | Consumer, not authority owner |
| `institutional_review_forum` | Body reviewing the external act | External role, not always present |

`owner_state` should be removed. Capability completeness belongs in the
repository capability lattice; legal/operator uncertainty belongs in a separate
`operator_grounding` assessment.

## 17. Canonical-owner and P27 audit

| Area | Actual signal | Audit result |
| --- | --- | --- |
| PDC | Purpose-scoped waist and case graph | Reuse for PDC-owned claim authority; not proved owner of the global register or PolicyMatter |
| Runtime quality | Rich evidence authority envelope and gates | Candidate admission component; universal owner not established |
| Fabric | Data source contract/provenance | Reuse for data sources; do not force legal/remedy payloads into dataset semantics |
| Lex + Data Forge | Runtime legal evaluation + offline corpus production | Split owner; report understates Data Forge |
| DDM | Drift/readiness/local incident signals | Producer of specific signals, not generic institutional adjudication |
| Decision validity / continuous governance | Claim reaction and lifecycle | Strong reaction owner, incomplete fleet orchestration |
| Core audit | Portable package and verification | Owns package integrity, not independent audit conclusion |
| Runtime HTTP | Internal action authorization | Owns admission to handler execution, not successful/external execution |
| Atlas | Renderer/consumer | Projection-only; not sole publication owner |
| H2 | Future orchestration concept | No current owner/capability |
| `team-architecture` | Research/governance review | Not a runtime schema producer |

## 18. AuthorityBoundary reuse audit

The exact `AuthorityBoundary.meet` claim is confirmed for the PDC type. The
universal-canonical claim is not. The repository has several family-specific
authority envelopes and status owners. Legal finality, audit independence,
security assurance, records authority, payment finality, and public correction
cannot be inferred from `authoritative_for`/`may_not_use_for` alone.

Recommendation: reference the existing canonical authority boundary at the
claim/admission point; do not embed a new copy in every external payload or
declare the PDC class the sole grammar before P27 consolidation.

## 19. Evidence-envelope audit

The proposed envelope should be rejected as a frozen cross-family contract. It:

- duplicates RQ producer/tenant/run/lineage/integrity fields;
- duplicates Fabric schema/security/quality/replay/retention fields;
- duplicates PROV entity/activity/agent edges;
- duplicates family clocks and lifecycle links;
- stores verification/admission outcomes beside source facts;
- lets external evidence prescribe `required_reaction`;
- embeds affected claims/public records and provisional `policy_matter_ref`;
- defines a generic evidence-status machine;
- pre-empts OPS-R4.

The corrected architecture is documented in
`pao-r1-evidence-contract-audit.md`: family-native payload, existing references,
a separate admission receipt, consumer impact/reaction, and projection.

## 20. Status-lattice audit

| Proposed list | Classification |
| --- | --- |
| Evidence states | Mix of transport, integrity, admission, dispute, temporal and lifecycle states; material parallel-lattice risk |
| Boundary-decision states | New governance workflow without ratified transition owner |
| Owner states | Mixes legal ownership and capability completeness |
| Implementation states | Useful audit labels, but incomplete compared with repository capability vocabulary |

`verified` is especially unsafe: integrity, source identity, competence, legal
effect, semantic adequacy, and claim-specific admission are independent checks.
No generic state should collapse them.

## 21. Absence-behavior audit

The invariant “missing is not non-occurrence” is strong. The generic reaction
grammar is not safe to freeze. `block`, `freeze_publication`, `recompute`,
`reissue`, and `withdraw` depend on materiality, claim type, audience,
jurisdiction and the canonical consumer. Absence conditions belong with source
and admission records; final reaction belongs with the claim-dependency owner.

The A1–A9 codes are too coarse for claim-specific fail-closed proof. Most
INTEGRATE rows name a code or prose reaction but do not identify an implemented
bridge, dependency key, verifier or negative test. They are
`semantic_test_missing`, not implemented fail-closed routes.

The universal rule “absent hold status → no deletion” is not supportable.
Retention is governed by applicable schedules and known holds; an absent feed
may require uncertainty/escalation, but indefinite preservation can itself
violate law, minimization or retention policy.

## 22. Temporal-semantics audit

| Clock | Existing signal | Standing |
| --- | --- | --- |
| `valid_at`, `tx_at` | Core and Fabric temporal refs | Existing but not proven universal |
| occurred/recorded | Decision-validity events | Existing event-specific pair |
| published/effective | Lex and publication records | Family-specific |
| observed | Multiple runtime/data records | Existing but inconsistent naming |
| receipt | Sparse family-specific use | Not canonical |
| admission | One census match; no cross-family owner | Absent as common clock |
| correction/revocation | Usually events/relations, sometimes timestamps | Prefer event refs where possible |

OPS-R4 explicitly owns the shared vocabulary and late-event policy. PAO-R1 may
require preservation of distinct relevant roles but must not require ten fields
or decide their payload placement.

## 23. Claim-at-risk taxonomy audit

C1–C17 are useful reviewer shorthand, not canonical claim families. They
overlap (`C2`, `C5`, `C6`, `C9`), mix capabilities with claims (`C10`, `C17`),
and do not map to PDC claim IDs, authority axes, or decision-validity dependency
keys. Keep them in research fixtures only. A production register should bind
actual claim/dependency references owned by PDC or the relevant domain owner.

## 24. Public-projection audit

Current surfaces cannot uniformly distinguish all of `externally performed`,
`reported`, `received`, `authenticated`, `verified`, `admitted`, `binding`,
`provisional`, `disputed`, `stale`, `corrected`, `revoked`, `executed`,
`settled`, and `superseded`. Generated and runtime APIs expose several local
status fields, not the proposed cross-family semantics.

Atlas's constitutional rule is sound, but the active plan records two components
that synthesized authority the runtime never produced. Public wording proposed
by PAO-R1 is therefore a semantic-test target, not an implemented capability.
Publication ownership is distributed; Atlas is a renderer, not the owner of
every public record.

## 25. Tenant, jurisdiction, competence, and security audit

Tenant identifiers are common in RQ, Fabric, runtime HTTP and audit code.
Jurisdiction is common in Lex and policy contracts. Their presence does not
prove cross-tenant federation, external competence, or safe cross-jurisdiction
admission. The generic envelope provides no trust-federation protocol and no
proof that a signed but wrong-subject/wrong-jurisdiction event is rejected
across every family.

The register's named operators are therefore `provisional` or
`owner_unresolved` until a jurisdiction and institutional system are known.
Existing authorization tests protect internal actions; they do not authenticate
external sovereign acts.

## 26. Deferred activation audit

The 38-entry appendix is useful as a research crosswalk but cannot reclassify
the backlog. “Trigger sufficient” opens research only. The historical Rev-1
comparison is unavailable.

| Entry | Backlog standing at both baselines | Audit disposition |
| --- | --- | --- |
| OPS-R12 | deferred | Preserve trigger as advisory; queue economics/operator facts required |
| OPS-R13 | deferred | Preserve; interaction evidence interface remains research |
| PAO-R2 | deferred | Preserve as pilot-dependent |
| PAO-R3 | deferred | Qualify: accessibility ownership and external journey need separate rows |
| PAO-R5 | deferred | Preserve; OPS-R4 owns clocks |
| PAO-R6 | deferred | Preserve; jurisdictional service proof required |
| PAO-R7 | deferred | Preserve; remedy authority unresolved |
| PAO-R8 | deferred | Preserve; identity provider facts required |
| PAO-R9 | deferred | Preserve act/interface split; ADR-0170 is the local owner seed |
| PAO-R10 | deferred | Preserve institution/own-record split |
| PAO-R11 | deferred | Remove “prefreeze hooks” as an implementation constraint |
| PAO-R12 | deferred | Preserve; controller/law facts required |
| PAO-R13 | deferred | Preserve; no universal no-delete rule |
| PAO-R14 | deferred | Preserve fidelity concept; enactment remains external |
| PAO-R15 | deferred | Preserve as pilot-dependent |
| PAO-R16 | deferred | Preserve V→I distinction as research hypothesis |
| PAO-R17 | deferred | Preserve V; corroboration transition unresolved |
| PAO-R18 | deferred | Preserve |
| PAO-R19 | deferred | Preserve |
| PAO-R20 | deferred | Preserve event-stage separation |
| PAO-R21 | deferred | Preserve |
| PAO-R22 | deferred | Preserve; eligibility denominator may implicate PAO-R4 |
| PAO-R23 | deferred | Split is a sound recommendation, not a reclassification |
| PAO-R27 | deferred | Preserve |
| PAO-R29 | deferred | Preserve; reliance terms are pilot facts |
| PAO-R30 | deferred | “Merge at activation” exceeds PAO-R1; propose to backlog owner |
| PAO-R31 | deferred, backlog says OBSERVE | Proposed V/I split is plausible but is a reclassification requiring acceptance |
| PAO-R32 | deferred | Split is useful; do not freeze EC-19 |
| PAO-R33 | deferred | Preserve V; admission path unresolved |
| PAO-R34 | deferred | “OWN sealed receipt” is premature; security/records owner review needed |
| PAO-R35 | deferred | Report correctly notes trigger insufficiency, but cannot rewrite trigger |
| PAO-R37 | deferred | Preserve with pilot and human-authority qualification |
| PAO-R38 | deferred residual | Preserve minimum/extended split; consolidate with INT-R7/OPS-R14 |
| PAO-R39 | deferred | Preserve |
| PAO-R40 | deferred, backlog says OWN-adjacent | Report's V/O split and trigger refinement require backlog acceptance |
| PAO-R41 | deferred | Preserve |
| OPS-R14 overlap | **active** | Not a deferred row; move to overlap note |
| PAO-R36 rider | **active narrow core** | Not a deferred row; third-party rider remains deferred only |

## 27. Stage-0 authority audit

| Rule | Standing |
| --- | --- |
| G.1 identity | Direct restatement of ratified invariant |
| G.2 four-way test | Direct restatement, with act/interface clarification |
| G.3 mandatory five-plane decomposition | Safe temporary research guidance; not a schema |
| G.4 ownership fields | Proposed model requiring acceptance; field set corrected in §16 |
| G.5 INTEGRATE minimum | Mixed: provenance/scope/absence are ratified; exact clocks/status/reaction fields are premature |
| G.6 OBSERVE minimum | Safe guidance; transition contract unresolved |
| G.7 OUT minimum | Safe guidance if “display status” has an admitted projection contract |
| G.8 anti-roles | Ratified invariant, except “records-management platform” should be limited to general/institution-wide operation |
| G.9 core ownership | Mostly ratified; legal sensing, learning and public verification require qualified subfunction splits |
| G.10 capstone rule | Task-specific proposed sentinel, not current capability |

Quarterly review, mass-impact freezes, challenge receipts, and immutable boundary
rows are proposals requiring human-principal, architecture and canonical-owner
acceptance. The research artifact cannot make them binding.

## 28. External-source quality audit

Targeted network verification found the high-level role-separation claims
generally directionally supported. The sources do not establish a universal
PolicyOS allocation or schema.

| Source | Result | Correction |
| --- | --- | --- |
| Bovens | DOI/title and actor–forum framing supported | Keep; do not infer technical fields |
| Koppell | DOI/title and distinct accountability dimensions supported | Keep; not an authority allocator |
| W3C PROV | Concepts supported, but cited URL is a 2012 Last Call Working Draft | Replace with final [W3C Recommendation](https://www.w3.org/TR/prov-o/) |
| EU AI Act | Official regulation supports differentiated roles within EU scope | State jurisdiction/use-case limits; do not universalize |
| NIST AI RMF | Official voluntary framework supports organizational governance | Keep “not legal allocation” qualification |
| GovS 005 | Official current standard assigns end-to-end service ownership | UK organizational example only |
| UK ATRS | Official guidance supports operational SRO and publishing roles | Transparency record is not execution evidence |
| eIDAS | Official law supports qualified trust/delivery distinctions | Use the canonical consolidated EUR-Lex version; legal sufficiency is jurisdiction-specific |
| ISSAI 100 | Final standard separates auditor, responsible party and users | Strong support for package/opinion distinction |
| NARA / ICO / GDPR | Support schedule/controller duties in their jurisdictions | Do not derive universal “no deletion when hold feed absent” |
| GAO Green Book | Underlying 2025 standard supports management responsibility | Replace corrupted display title and press release with [the 2025 standard PDF](https://www.gao.gov/assets/890/882014.pdf) |
| European Ombudsman | Official treaty/statute supports bounded independent mandate | EU-specific |
| OECD procurement | Official full report supports institutional procurement governance | Does not define PolicyOS contract |
| OECD public-sector AI | Report cites a press release, not the underlying study | Replace with [Governing with Artificial Intelligence](https://www.oecd.org/en/publications/governing-with-artificial-intelligence_795de142-en/full-report.html) |

## 29. Benchmark and fixture audit

No `BND-*` fixture exists at either baseline. The 40 scenarios are proposals.
The strongest are BND-001, 003–006, 009, 014, 017–020, 025, 031, 035–040.
They directly test the act/evidence boundary, observation firewall, duplicate
event handling and historical supersession. Several pattern mappings are wrong;
the detailed mapping is in the test-and-fixture file.

The proposed corpus size of 160 and zero sentinels are research benchmark
choices, not repository facts. Existing tests prove narrower properties:
Ring-2 verifier-only writes, source-contract validation, legal
competence/applicability, append-only reissue, authorization-receipt semantics,
projection-only authority, audit-package verification, and incident signal
typing. None proves that all 213 institutional rows are correctly classified.

## 30. Recommended final PAO-R1 posture

Retitle the result as an **operational-boundary research method and candidate
questionnaire**, not a frozen adjudication register. Preserve the six invariant
rules in §4 and the highest-value fixtures. Treat the 213 rows as hypotheses
requiring:

- plane separation;
- actual canonical-owner mapping;
- jurisdiction/pilot operator evidence;
- OPS-R4 temporal consolidation;
- PAO-R0 subject consolidation;
- dependency-specific absence behavior;
- negative semantic tests.

## 31. Required changes before Stage-0 freeze

1. Replace every mixed external-act `I` row with linked act/evidence/admission/
   reaction/projection records.
2. Remove the universal institutional envelope; publish only a research field
   comparison and corrected composition architecture.
3. Remove or map all proposed statuses to existing canonical owners.
4. Replace undefined owner/capability/lifecycle codes.
5. Remove future tasks and `team-architecture` as runtime owners.
6. Mark every external operator provisional until jurisdiction/pilot evidence.
7. Downgrade C1–C17 and A1–A9 to fixture shorthand.
8. Defer clock names and placement to OPS-R4.
9. Make `policy_matter_ref` optional and dependency-qualified pending PAO-R0.
10. Correct all failure-pattern IDs and remove `M31` from the pattern column.
11. Separate active OPS-R14/PAO-R36 overlap notes from the deferred registry.
12. Remove “binding,” “freeze now,” mandatory quarterly review and automatic
    mass-freeze language absent ratification.
13. Correct the baseline/history and external-link defects.
14. Run the BND corpus only after the register is normalized and independently
    adjudicated.

## 32. Open questions for consolidation

- PAO-R0: subject identity and canonical owner.
- OPS-R4: clock vocabulary, late events, correction/revocation references.
- OPS-R5: observation, KPI diagnosis and safe adaptation boundary.
- OPS-R10: Lex/Data Forge legal release and applicability ownership.
- INT-R5: competence, delegation, quorum, recusal and pre-action authority.
- INT-R7: public verification, key lifecycle and archival proof.
- PAO-R36: public correction, caches, subscriber notices and external
  misinformation.
- OPS-R15: executable sentinel instrumentation and partner-event capstone.
- Architecture/canonical owners: whether any global boundary register should
  exist at runtime, or remain a versioned research/governance artifact.
- Institutional partners: operator identity, legal competence, evidence
  authentication, finality, retention and dispute forum.

## 33. Commands and verification results

The exact command ledger is in
`pao-r1-test-and-fixture-verification.md`. Summary:

- prescribed system-Python bootstrap and doctor failed because `click` is
  unavailable;
- a dependency-bearing audit environment ran bootstrap, which failed because
  it attempted an incompatible `pip --user` install;
- doctor ran and reported eight environmental/repository issues: wrong Node and
  uv versions, missing Chromium, lock/schema/OpenAPI/frontend checks blocked;
- **108 targeted tests passed** across PDC, Fabric, Lex, DDM, core audit,
  authorization audit, contestability/ownership and partial reissue;
- two Fabric fail-closed repo-quality tests failed because generated source
  platform documentation is stale at the baseline;
- runtime-quality, HTTP and full lifecycle collections were blocked by missing
  `jaxlib==0.8.2` for CPython 3.14;
- all static searches and history probes ran at the pinned SHA.

## 34. Audit limitations

- The report was supplied in conversation, not as a repository file; its
  normalization is captured in these artifacts but cannot be commit-pinned.
- Historical and current repository baselines are identical, so evolution
  cannot explain any disagreement.
- Static inspection cannot prove partner identity, competence, legal effect,
  institutional performance, production routing, hidden deployment
  configuration, or cross-institution agreements.
- Some runtime suites could not collect because the required `jaxlib` wheel was
  unavailable; no pass is claimed for them.
- Network review was targeted, not a full legal opinion. EU, UK, US and OECD
  sources are examples within their scope, not universal law.
- Negative searches covered the checked-out repository and generated
  baselines, not inaccessible services or untracked partner code. Confidence is
  high for symbol absence at the two SHAs and medium for operational absence.
