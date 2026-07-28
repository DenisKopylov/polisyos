---
title: Stage-0 Additional-Research Register
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

# Stage-0 Additional-Research Register

## Decision rule

A new inquiry is proposed only when the question remains unanswered, cannot be
fixed by wording, has no sufficient active/deferred task owner, is not merely
implementation validation or a repository defect, has a bounded falsifier and
deliverable, changes a downstream decision, and does not widen PolicyOS into
administration.

Only **two** candidate inquiries pass that test. The identifiers below are
temporary and must not be inserted into the authoritative backlog without a
separate decision.

## Accepted candidate inquiries

### S0-GAP-01

```yaml
candidate_gap_id: S0-GAP-01
title: Minimum Policy Subject Reference and Semantic-Owner Decision
research_question: >-
  What is the minimum implementation-neutral subject-reference compatibility
  contract, and which existing or new semantic owner is competent to issue and
  govern it, without fixing PolicyMatter cardinality, relation adjudication,
  evidence applicability, or a package layout prematurely?
why_current_stage0_is_insufficient: >-
  The ratified decision establishes the need for identity above a case, but
  PAO-R0 did not establish a canonical owner or safe minimum ABI. PAO-R1 and
  OPS-R15 both need an attachment seam and otherwise invent policy_matter_ref.
why_not_editorial: >-
  Removing the overclaim is editorial; selecting the semantic owner, issuer,
  namespace boundary, compatibility obligations, and multi-subject behavior
  changes future ABI and migration decisions.
why_not_existing_task: >-
  PAO-R0 was the anchor intended to answer this question but its independent
  audit rejected the owner/schema conclusion. OPS-R2, OPS-R4, INT-R5, and
  PAO-R36 own downstream relations, time, competence, and correction, not the
  subject-reference owner/ABI itself.
inputs:
  - ratified identity/custody decision
  - PAO-R0 audit and recommended revision
  - PAO-R1 and OPS-R15 dependency findings
  - package ownership and public-surface policies
  - current PDC, core.contracts, runtime-quality, artifact, audit, and lineage contracts
repository_paths:
  - policy-engine/src/polisyos/pdc
  - policy-engine/src/polisyos/core/contracts
  - policy-engine/src/polisyos/runtime/quality
  - policy-engine/src/polisyos/core/artifacts
  - policy-engine/src/polisyos/core/audit
  - policy-engine/src/polisyos/scientist/validation
  - policy-engine/docs/public-surface-policy.yaml
external_domains:
  - persistent-identifier governance
  - subject-reference ABI design
  - public-record identity and provenance
required_comparative_models:
  - PDC-owned extension
  - core.contracts shared ABI
  - dedicated bounded semantic owner
  - opaque adapter-local reference with later mapping
deliverables:
  - owner decision record with rejected alternatives and P27 analysis
  - minimum opaque subject-reference compatibility profile
  - namespace, tenant, and federation non-assumptions
  - one-to-many and many-to-many cardinality compatibility tests
  - explicit exclusions for legal continuity and evidence applicability
  - migration and correction obligations stated without production schema
falsifiers:
  - the selected owner cannot enforce the compatibility profile across its consumers
  - an alternative valid multi-matter PDC cannot be represented
  - two tenants can collide or an unqualified reference crosses authority scope
  - adoption requires rewriting an existing signed or CAS artifact
  - the reference itself grants evidence applicability or legal continuity
dependencies:
  - Stage-0 consensus kernel
  - package-owner review
candidate_owner: team-architecture research lead with PDC, core.contracts, runtime-quality, security, and audit reviewers
activation_timing: before H2 architecture fixes persistence or public ABIs; not required before unrelated Wave-2 research
blocks:
  - canonical PolicyMatter package or wire contract
  - mandatory policy_matter_ref in cross-family contracts
  - matter-lineage OPS-R15 extension
does_not_authorize:
  - PolicyMatter implementation
  - identity adjudication
  - split or merge decisions
  - legal succession inference
  - migration of existing IDs
expected_disposition: bounded architecture-research decision, then superseded by an accepted owner/ABI decision
```

### S0-GAP-02

```yaml
candidate_gap_id: S0-GAP-02
title: Independent Custody-Benchmark Oracle and Evaluator Architecture
research_question: >-
  How can an implementation-independent, machine-readable and challengeable
  oracle establish acceptable custody semantics while keeping expected results
  sealed, preserving ambiguity and dissent, preventing shared-code circularity,
  and resisting fixture memorization?
why_current_stage0_is_insufficient: >-
  OPS-R15 supplies prose inputs and visible expected traces but no independent
  oracle, reducer, evaluator, sealing protocol, access model, or executable
  corpus. A same-code rebuild can reproduce the same semantic defect.
why_not_editorial: >-
  Relabeling the report as blocked is necessary but does not create independent
  semantic truth, an evaluator, an ambiguity model, or leakage controls.
why_not_existing_task: >-
  OPS-R15 describes the capstone but its audited artifact omits this
  methodology. INT-R9 covers first-promotion selection, not long-cycle oracle
  construction. OPS-R2 and domain tasks provide inputs but do not own
  benchmark governance.
inputs:
  - audited OPS-R15 16-predicate kernel
  - PAO-R0 and PAO-R1 narrowed assumptions
  - failure-pattern register
  - INT-R9 pre-registration requirements
  - domain-owner fixtures and canonical state projections
repository_paths:
  - policy-engine/tests
  - policy-engine/src/polisyos/core/artifacts
  - policy-engine/src/polisyos/core/audit
  - policy-engine/src/polisyos/core/contracts
  - policy-engine/src/polisyos/runtime/quality
  - policy-engine/src/polisyos/scientist/validation
  - policy-engine/src/polisyos/scientist/governance/continuous
external_domains:
  - benchmark validity and leakage
  - differential and metamorphic testing
  - declarative reference semantics
  - inter-reviewer reliability
  - cryptographic commitment and sealed evaluation
required_comparative_models:
  - separately implemented declarative reducer
  - property/predicate evaluator without full reference runtime
  - dual independent evaluators with disagreement adjudication
  - same-code rebuild as diagnostic control
deliverables:
  - machine-readable public schema and input-only fixture corpus
  - sealed semantic expectation format with admissible alternatives
  - independent evaluator interface and code-independence rules
  - clean-rebuild reference semantics and equivalence policy
  - authority-scenario axiom and human-adjudication protocol
  - commitment, custody, access-log, rotation, challenge, and supersession protocol
  - adjacent-case and metamorphic mutation generator specification
  - reproducibility receipt and bounded-claim template
falsifiers:
  - evaluator imports implementation admission, reducers, dependency traversal, or status projection
  - implementation-visible files expose expected actions or labels
  - an ID-renumbered or adjacent unseen case changes outcome without semantic reason
  - a seeded shared reducer fault passes incremental and clean-build checks
  - oracle correction silently changes a prior scored result
  - reviewer conflict, abstention, or disagreement is discarded
dependencies:
  - Stage-0 consensus kernel
  - domain predicates from active Wave-2 tasks
  - accepted local assumptions for subject and boundary fixtures
candidate_owner: independent benchmark-governance lead, separate oracle custodian, and domain reviewers
activation_timing: now for research design; benchmark engineering after relevant domain predicates stabilize
blocks:
  - any claim that OPS-R15 is executable or passed
  - use of OPS-R15 as Group-B capability proof
  - scored hidden-set runs
does_not_authorize:
  - benchmark runner implementation in production packages
  - legal certification
  - production readiness
  - RPO or RTO commitments
  - external institutional authority
expected_disposition: accepted oracle architecture followed by separately governed benchmark engineering
```

## Mandatory 20-item gap review

| # | Question | Decision | Existing owner or route | Stage-0 interim assumption |
|---:|---|---|---|---|
| 1 | PolicyMatter canonical ownership | **Additional inquiry required** | S0-GAP-01 | Functional need only; owner unresolved |
| 2 | Minimum subject-reference compatibility contract | **Additional inquiry required** | S0-GAP-01 | Opaque fixture/local references; no mandatory field |
| 3 | Matter continuity adjudication and competent-authority evidence | **Existing task + pilot evidence** | INT-R5; PAO-R0 amendment; partner authority | Technical relation never proves legal continuity |
| 4 | Multi-matter PDC cardinality | **Additional inquiry required** | S0-GAP-01 | Preserve one-to-many/many-to-many compatibility |
| 5 | Evidence-applicability inheritance after split, merge, or expansion | **Existing task owns it** | OPS-R2 plus family applicability/authority owners | No automatic inheritance |
| 6 | Shared admission header versus family-native contracts | **Amend existing report** | PAO-R1; INT-R2/OPS-R4 later | Family-native contracts; composition by reference; no universal schema |
| 7 | Temporal vocabulary and correction semantics | **Existing task owns it** | OPS-R4 | Preserve role non-collapse and append-only history only |
| 8 | Tenant/cell/authority custody closure | **Repository fix + implementation validation** | Security/control plane; OPS-R1/3/INT-R5 requirements | Protected action fails closed when closure is absent |
| 9 | Jurisdiction fail-closed semantics | **Existing task + repository fix** | OPS-R11/OPS-R10; Lex registry engineering | Unknown jurisdiction cannot authorize protected use |
| 10 | Authority-dependency indexing | **Existing task owns it** | OPS-R2 | Content identity does not imply current authority |
| 11 | Suspension/resume equivalent-protection model | **Existing tasks own it** | OPS-R1, OPS-R3, INT-R5 | Require outcomes, not twenty gates |
| 12 | Independent benchmark oracle design | **Additional inquiry required** | S0-GAP-02 | OPS-R15 remains non-executable |
| 13 | Declarative clean-rebuild reference semantics | **Additional inquiry required** | S0-GAP-02 | Same-code rebuild is diagnostic only |
| 14 | Human authority-adjudication protocol | **Additional inquiry required within benchmark scope** | S0-GAP-02; domain authority reviewers | Synthetic facts are axioms/contested, not legal ground truth |
| 15 | Public correction and cross-surface parity | **Existing tasks own it** | PAO-R36, INT-R7, INT-R8, Atlas | Stale must not render current; exact states deferred |
| 16 | Long-term verification and key/archive renewal | **Existing tasks own it** | INT-R7 and OPS-R14 | No production longevity claim |
| 17 | World-release compatibility | **Existing task owns it** | OPS-R8 | No fixed vector/schema/state machine |
| 18 | Mass invalidation and fleet scheduling | **Existing/deferred tasks + implementation validation** | OPS-R2; OPS-R12 on trigger | Correct affected-set semantics before scale targets |
| 19 | RPO/RTO classification | **Existing task + deployment evidence** | OPS-R14; governed pilot | No Stage-0 number; distinguish semantic/synthetic/production |
| 20 | External institutional partner evidence interfaces | **Pilot evidence required** | Deferred PAO tasks, INT-R5, family adapters | Operator and legal-effect mappings are provisional |

## Rejected candidate inquiries

| Rejected gap | Why it is not a new research task | Correct route |
|---|---|---|
| Universal institutional evidence envelope | The audits provide enough evidence to reject a universal owner/schema; no research is needed to preserve family meaning | Amend PAO-R1 and OPS-R15; INT-R2/OPS-R4 may define narrower interfaces |
| One cross-product status lattice | Directly conflicts with the ratified one-lattice constraint | Remove; map family states to canonical owners |
| Nine/ten/thirteen-clock reconciliation study | Already the explicit remit of OPS-R4 | `defer_to_existing_task` |
| OperationalBoundaryDecision runtime owner | The 213-row artifact is not mature enough to justify a runtime owner | Keep PAO-R1 as research method; reconsider only after real consumers |
| Twenty-gate resume protocol | Mechanism-level prescription already belongs to OPS-R1/3 and H2 architecture | Test equivalent protection, not gate names/count |
| Authority-dependency graph research | Already OPS-R2 | Feed counterexamples to OPS-R2 |
| Public correction state machine | Already PAO-R36/INT-R7/INT-R8/Atlas | Feed predicates, do not duplicate |
| Jurisdiction fallback research | The silent UA fallback is a reproducible repository defect; pack semantics are OPS-R11 | Fix separately; retain negative test |
| Tenant-blind decision-lineage research | The path construction is a repository/security defect; future binding is OPS-R1/3 | Fix/test separately |
| Atlas authority-minting study | Governing doctrine and known code debt already identify the problem | Atlas engineering remediation and semantic tests |
| Long-term verification research | Already INT-R7 with OPS-R14 overlap | Do not create a Stage-0 duplicate |
| WorldRelease research | Already OPS-R8 | Move OPS-R15 material to an extension pack |
| RPO/RTO research | Already OPS-R14 and ultimately deployment-specific | No Stage-0 performance commitment |
| External operator census | Cannot be resolved without an institutional partner and jurisdiction | Activate deferred PAO task on its typed trigger |

## Implementation-validation questions

These require code or deployment evidence later, not new research:

- whether checkpoint/control-job persistence closes tenant, cell, generation,
  and authority scope end to end;
- whether wrong-tenant or wrong-claim evidence reaches a protected consumer;
- whether public correction invalidates every controlled cache/client/surface;
- whether duplicate wakes create duplicate irreversible PolicyOS effects;
- whether asymmetric CAS/control-state recovery can expose false-current state;
- whether release/fan-out scheduling meets scale goals;
- whether a production topology meets any RPO/RTO;
- whether key/archive renewal survives an exercised long-horizon drill;
- whether an executable benchmark runner is reproducible from committed inputs.

## Repository defects, not research gaps

| Defect | Evidence at both baselines | Route |
|---|---|---|
| Decision-validity local state path is tenant-blind | Path hashes raw `decision_lineage_key` | Security/owner issue and tenant-collision test |
| Checkpoint/control-job forms omit full tenant/cell/authority binding | `CheckpointMetadata` and control-job persistence census | Control-plane/H2 prerequisite |
| Unknown jurisdiction silently selects Ukraine | Jurisdiction registry fallback | Lex/OPS-R11 engineering fix |
| Public export does not perform the CAS-reference redaction asserted by its test | Builder path versus failing test recorded by PAO-R0 audit | Public-export code/test fix |
| Atlas readiness panels compute authority-looking readiness locally | Active plan and `publicSectorReadiness.ts` | Atlas producer-binding remediation |

No candidate gap authorizes fixing these defects in this documentation-only
consolidation.
