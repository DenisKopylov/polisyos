---
title: Stage-0 Consolidated Revision Pack
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

# Stage-0 Consolidated Revision Pack

This pack provides replacement frontmatter, executive findings, and a
section-level patch map. It does not overwrite the delivered reports. The
original PAO-R0 and PAO-R1 source artifacts must be supplied before a
byte-accurate patch can be prepared.

## PAO-R0 proposed frontmatter

```yaml
---
title: PAO-R0 — Policy Matter Identity and Episode Graph
status: delivered_requires_amendment
kind: deep-research
research_task: PAO-R0
result_type: research_supported_with_open_owner
repository: https://github.com/DenisKopylov/polisyos
repository_branch: main
repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
independent_audit_commit: 258aa740efcfb9e6771bfe52d4fdabc6b74f93a7
consolidation_required: true
authoritative_for:
  - research evidence that PolicyOS needs technical custody identity above one case
  - compatibility guidance against silently reinterpreting existing identifiers
  - candidate questions for subject-reference and identity-history research
may_not_use_for:
  - canonical PolicyMatter owner
  - final identifier, namespace, schema, cardinality, or relation model
  - evidence applicability or legal continuity
  - production migration authorization
  - common status or temporal contract
  - production capability claim
  - authority grant
research_only: true
---
```

### PAO-R0 replacement executive finding

**Result: `research_supported_with_open_owner`.**

The ratified identity/custody decision and repository architecture support the
need for a stable technical custody reference above a single Policy Design
Case. They do not establish a typed `PolicyMatter` capability, canonical
package owner, issuer, namespace, cardinality, split/merge adjudicator, common
support state, temporal schema, migration, or public resolver.

`PolicyMatter` remains a research hypothesis for an opaque accountability and
justification-custody anchor. The safe compatibility guidance is:

1. do not silently reinterpret case, run, job, decision-lineage, policy,
   portfolio, artifact, legal-instrument, or URL identifiers as lifetime
   identity;
2. do not allow similarity, an LLM, projection, or metadata to mint identity
   authority;
3. preserve signed and content-addressed historical bytes;
4. keep future subject associations correctable and replayable;
5. do not infer evidence applicability, legal succession, or competence from
   identity continuity;
6. preserve compatibility with more than one matter per case until cardinality
   is decided.

PDC is a plausible integration neighborhood, runtime quality a possible
validation bridge, artifacts/audit existing custody primitives, and H2 a future
consumer. None is thereby the canonical semantic owner. That owner and the
minimum subject-reference ABI require S0-GAP-01.

## PAO-R1 proposed frontmatter

```yaml
---
title: PAO-R1 — Operational Boundary Method and Candidate Census
status: delivered_requires_amendment
kind: deep-research
research_task: PAO-R1
result_type: accepted_narrower_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: main
repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
independent_audit_commit: 566840c330e867a15313923c87c20b6863cb053f
consolidation_required: true
authoritative_for:
  - research method for applying the ratified four-way custody test by plane
  - candidate non-authoritative boundary census
  - research questions for family-native evidence interfaces
may_not_use_for:
  - Stage-0 adjudication authority
  - production boundary register
  - universal institutional evidence envelope
  - canonical owner or status assignment
  - legal or institutional operator allocation
  - Wave-2 task reclassification
  - production implementation authorization
  - proof that an external act occurred
research_only: true
---
```

### PAO-R1 replacement executive finding

**Result: `accepted_narrower_scope`.**

The ratified four-way test is a strong boundary-review method only when it
classifies one declared plane at a time:

```text
external institutional act
→ evidence emission
→ PolicyOS receipt/verification/admission
→ scoped claim reaction
→ public projection
```

An external act remains externally owned and PolicyOS execution is prohibited.
If its result can change a PolicyOS claim, the evidence relationship is
INTEGRATE. Purpose-specific admission and the reaction of PolicyOS-owned claims
are OWN. The publication owner produces the governed projection; Atlas renders
it without minting authority. Missing external evidence is not proof of
non-occurrence and the canonical consumer owns claim-specific fail-closed
reaction.

The 213-row Appendix-C register and EC-01..21 catalogue are research hypotheses,
not a frozen adjudication baseline. Keep the census as a non-authoritative
questionnaire or reduce it to audited exemplars. Do not create a universal
institutional envelope, common evidence-status lattice, owner-state lattice,
fixed clock bundle, challenge workflow, quarterly review rule, or backlog
reclassification through PAO-R1.

## OPS-R15 proposed frontmatter

```yaml
---
title: OPS-R15 — PolicyOS Custody-Cycle Semantic Conformance Research
status: delivered_requires_amendment
kind: deep-research
research_task: OPS-R15
result_type: blocked_pending_oracle_independence
benchmark_kernel: retained_as_research_guidance
extension_packs: deferred_to_owners
repository: https://github.com/DenisKopylov/polisyos
repository_branch: main
repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
independent_audit_commit: 42a79a655974b37e28a89d31b5f72ffea83927f4
consolidation_required: true
authoritative_for:
  - candidate observable custody predicates
  - adversarial scenario catalogue
  - benchmark-oracle and anti-overfitting research questions
may_not_use_for:
  - executable benchmark claim
  - production benchmark passage
  - H2 runtime contract or state machine
  - universal event or temporal envelope
  - canonical owner or authority state
  - legal or institutional ground truth
  - production RPO or RTO
  - implementation authorization
research_only: true
---
```

### OPS-R15 replacement executive finding

**Result: `blocked_pending_oracle_independence`.**

The principal custody proposition is strong: a long-lived PolicyOS custody
implementation must preserve durable subject-bound suspension, exact wake
matching, action-specific authority re-admission, content-versus-authority
invalidation, append-only correction, cutoff replay, scoped impact, tenant and
jurisdiction isolation, external-act separation, public currentness, and
recoverable custody state.

The delivered 24-month Markdown calendar is a scenario catalogue, not an
independent executable benchmark. Inputs and expected results are visible
together; event names do not normalize to the declared vocabulary; no
machine-readable corpus, runner, sealed semantic oracle, independent evaluator,
access protocol, or exercised anti-leakage process exists. A clean rebuild may
share the same faulty reducers and dependency graph.

The corrected Stage-0 contribution is a set of implementation-neutral semantic
predicates and task-owned conformance profiles. State names, a universal event
envelope, thirteen clocks, twenty universal gates, two physical graphs, exact
WorldRelease structure, institutional authority outcomes, efficiency
thresholds, and RPO/RTO numbers are not Stage-0 contracts. OPS-R15 remains
blocked until S0-GAP-02 produces an independent oracle/evaluator architecture
and benchmark engineering makes it executable.

## Section-level patch map

| Report | Section family | Action | Replacement source |
|---|---|---|---|
| PAO-R0 | Frontmatter/executive | Replace | This pack |
| PAO-R0 | Repository baseline | Keep facts; add identical current SHA and source availability | Verification report |
| PAO-R0 | Identifier census | Preserve with local-domain qualifications | PAO-R0 audit ledger |
| PAO-R0 | Canonical owner | Delete conclusion; insert open-owner wording | Owner map/S0-GAP-01 |
| PAO-R0 | Entity/envelope/status schema | Remove from accepted result; retain alternatives only | Amendment plan |
| PAO-R0 | Relations/cardinality | Mark unresolved; prohibit applicability inference | Consensus S0-K02/S0-K12 |
| PAO-R0 | Clocks | Remove field bundle | Consensus S0-K09/OPS-R4 |
| PAO-R0 | Migration/correction | Preserve non-rewrite only; defer technique | Consensus S0-K08 |
| PAO-R0 | Capability/test claims | Normalize labels and test status | Verification report |
| PAO-R0 | Owners/citations/patterns | Correct | Owner and source maps |
| PAO-R1 | Frontmatter/executive | Replace | This pack |
| PAO-R1 | Four zones/unit | Split planes; define verdict object | Consensus S0-K03/S0-K04 |
| PAO-R1 | Appendix C | Keep as non-authoritative census or audited exemplars | R1 row audit |
| PAO-R1 | Appendix D | Convert contracts to research families | R1 evidence-contract audit |
| PAO-R1 | Shared envelope/status/owner state | Remove | Owner/vocabulary map |
| PAO-R1 | Absence behavior | Split condition/admission from consumer reaction | Consensus S0-K12 |
| PAO-R1 | OBSERVE | Add explicit new-admission transition | Consensus S0-K05 |
| PAO-R1 | Clocks | Defer names/placement | OPS-R4 |
| PAO-R1 | Governance/deferred tasks | Remove authority/reclassification; current-W2 notes only | Amendment plan |
| PAO-R1 | Citations/patterns/capability labels | Correct | Verification report |
| OPS-R15 | Frontmatter/executive | Replace | This pack |
| OPS-R15 | Calendar | Recast as catalogue; separate input/sealed expected packages | S0-GAP-02 |
| OPS-R15 | Vocabulary/envelope | Benchmark-only input wrapper; no expected outputs | Owner/contract map |
| OPS-R15 | State machines | Convert to predicates | Consensus kernel |
| OPS-R15 | Clocks | Family roles/evaluator clock only; defer production model | OPS-R4 |
| OPS-R15 | Resume gates | Equivalent protection by phase/action | Consensus S0-K11 |
| OPS-R15 | Dependencies | Keep semantic content/authority distinction; defer graph shape | OPS-R2 |
| OPS-R15 | Oracle/rebuild/human review | Replace and block until independent deliverables | S0-GAP-02 |
| OPS-R15 | Metrics | Close denominators; demote efficiency; no arbitrary thresholds | Amendment plan |
| OPS-R15 | RPO/RTO | Move to deployment-specific OPS-R14 profile | OPS-R14 |
| OPS-R15 | Extension scenarios | Allocate to task-owned packs | Sequencing report |
| OPS-R15 | Failure patterns | Change “Detected” to proposed/untested | Verification report |

## Consolidated verdicts

| Object | Verdict |
|---|---|
| PAO-R0 original report | `accept_with_material_revisions` |
| PAO-R0 recommended revision | `accept_narrower_scope` |
| PAO-R1 original report | `accept_narrower_scope` |
| PAO-R1 recommended revision | `accept_narrower_scope` |
| OPS-R15 original report | `blocked_pending_additional_research` |
| OPS-R15 recommended revision | `retain_as_non_authoritative_research` |
| Combined Stage-0 anchor set | `accept_with_material_revisions` |
| Dispatch of remaining Wave 2 | `accept_with_material_revisions` through local assumptions; task-specific exceptions apply |
| H2 architecture | `blocked_pending_additional_research` |
| Executable custody capstone | `blocked_pending_additional_research` |

The combined verdict is not an average. It accepts only the consensus kernel,
not the three original contract bundles.
