---
title: Stage-0 Anchor Consolidation Report
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

# Stage-0 Anchor Consolidation Report

## 1. Scope and standing

This synthesis adjudicates the three Stage-0 anchors and their independent
audits as one research system:

- PAO-R0 — Policy Matter Identity and Episode Graph;
- PAO-R1 — Operational Boundary Census and Evidence-Contract Register;
- OPS-R15 — The PolicyOS Custody-Cycle Capstone Benchmark.

It does not average their verdicts or merge their schemas. It asks which
propositions can coexist under the ratified identity/custody decision without
creating a duplicate owner, parallel authority lattice, universal evidence
envelope, premature clock model, H2 runtime design, Atlas authority source, or
self-certifying benchmark.

This is a documentation-only research synthesis. It changes no production
code, authoritative decision, backlog, audit branch, runtime contract, or
benchmark runner.

## 2. Repository and branch baselines

| Input | Exact commit | Standing |
|---|---|---|
| Historical research `main` | `4813b49f6ce14e8debf3aaea096f0967d38d9768` | Source baseline |
| Pinned current remote `main` | `4813b49f6ce14e8debf3aaea096f0967d38d9768` | Identical; no evolution delta |
| PAO-R0 audit | `258aa740efcfb9e6771bfe52d4fdabc6b74f93a7` | Draft, non-authoritative |
| PAO-R1 audit | `566840c330e867a15313923c87c20b6863cb053f` | Draft, non-authoritative |
| OPS-R15 audit | `42a79a655974b37e28a89d31b5f72ffea83927f4` | Draft, non-authoritative |
| Consolidation branch point | `4813b49f6ce14e8debf3aaea096f0967d38d9768` | Clean branch from current `main` |

Because current and historical `main` are identical:

- no audit finding is stale due to later repository evolution;
- no later change resolves or contradicts an audit finding;
- code/test meaning needs only one checkout, while historical and current
  verdict columns remain explicit;
- draft audit branches remain evidence, not repository authority.

The consolidation read 17 Markdown audit artifacts at their exact commits:
4 PAO-R0, 6 PAO-R1, and 7 OPS-R15 files.

## 3. Source-artifact availability

| Original report | Availability | Content hash | Amendment consequence |
|---|---|---|---|
| PAO-R0 | Not committed; audit says task-context source | Unavailable | Only audit-covered positions can be amended exhaustively; otherwise `source_artifact_required` |
| PAO-R1 | Not committed; audit says conversation/task-context source | Unavailable | Same limitation |
| OPS-R15 | Not committed with audit; audit normalized the supplied attachment | Audit-recorded SHA-256 `0c3baf41df8ae02bd9f9ae88cc9f1a350d7f4e33021a94327c3e578044690d15` | Ledgers cover calendar/metrics/states; persist source before ratification |

The 17 audit files themselves were hashed and are listed in the verification
report. Recommended revisions are not substitutes for original source bytes.

## 4. Executive synthesis

### Combined verdict

**Combined Stage-0 anchor set: `accept_with_material_revisions`.**

What survives is substantially narrower than the three delivered artifacts:

1. PolicyOS needs a stable technical custody reference above one case, but no
   owner, schema, namespace, relation model, or runtime capability is ratified.
2. Boundary analysis must separate external act, evidence emission,
   receipt/admission, claim reaction, and projection. External execution stays
   external; PolicyOS still owns honesty of the claims it signs.
3. Observation, receipt, authentication, workflow state, benchmark passage,
   and display cannot mint authority.
4. Correction appends and historical replay excludes later knowledge; exact
   clocks and relations remain OPS-R4 work.
5. Future custody must prove durable subject-bound suspension, exact wake,
   action-specific re-admission, content-versus-authority invalidation,
   fail-closed scope, and honest public correction without prescribing H2's
   internal state machine.
6. A future capstone must use sealed expected results and an independent
   evaluator. The delivered OPS-R15 is not executable and cannot certify
   anything.

The original PAO-R0 contract, PAO-R1's 213-row adjudication baseline and
universal envelope, and OPS-R15's visible expected trace/twenty gates/state
machines are not accepted Stage-0 anchors.

### Final verdicts

| Object | Verdict | Reason |
|---|---|---|
| PAO-R0 original report | `accept_with_material_revisions` | Functional need confirmed; owner/schema/status/time/migration overclaimed |
| PAO-R0 recommended revision | `accept_narrower_scope` | Safe compatibility packet; still needs source and owner inquiry |
| PAO-R1 original report | `accept_narrower_scope` | Decomposition strong; register/contracts/governance overreach |
| PAO-R1 recommended revision | `accept_narrower_scope` | Sound method/census standing; not a runtime baseline |
| OPS-R15 original report | `blocked_pending_additional_research` | Oracle circular, trace visible, runner absent |
| OPS-R15 recommended revision | `retain_as_non_authoritative_research` | Kernel/profiles useful; executable claim remains blocked |
| Combined Stage-0 anchor set | `accept_with_material_revisions` | Accept only S0-K01–S0-K16 after decision |
| Readiness to dispatch rest of Wave 2 | `accept_with_material_revisions` | Most tasks may proceed after P0 amendments under local assumptions |
| Readiness to begin H2 architecture | `blocked_pending_additional_research` | Subject ABI/owner and custody semantics not resolved |
| Readiness to build executable capstone | `blocked_pending_additional_research` | Independent oracle/evaluator and machine corpus missing |

### Highest-priority findings

1. **P0 — Research standing overclaim.** Each original artifact uses
   research-only caveats while its operative language freezes owners, schemas,
   governance, or benchmark constraints.
2. **P0 — Parallel-owner/lattice risk.** Common support/evidence/boundary/
   custody states duplicate the one authority grammar and family lifecycle
   owners.
3. **P0 — External act/evidence collapse.** PAO-R1 and OPS-R15 can classify an
   external administrative act as INTEGRATE when only evidence crossing is I.
4. **P0 — Owner overclaim.** PDC, runtime quality, team architecture, Atlas,
   future tasks, and H2 are repeatedly assigned semantics they do not own.
5. **P0 — Universal-envelope gravity.** PAO-R0, PAO-R1, and OPS-R15 each
   propose a different common envelope that mixes producer facts, admission,
   reaction, or expected answers.
6. **P0 — Temporal pre-emption.** Nine, ten, and thirteen-clock bundles
   conflict and pre-empt OPS-R4.
7. **P0 — Oracle circularity.** OPS-R15's authors write architecture, visible
   trace, and expected results; same-code rebuild can reproduce the same defect.
8. **P0 — Concrete repository gaps.** Tenant/cell custody binding,
   tenant-qualified lineage storage, unknown-jurisdiction fail-closed behavior,
   public export redaction, and Atlas producer binding are incomplete.

## 5. Audit-of-audits findings

### Method

Every critical/high finding in the three audits was rechecked against the
baseline/current tree. The review distinguished:

- direct code/doc/test evidence;
- architecture inference;
- duplicated root findings;
- a correct defect with an overbroad proposed remedy;
- an unavailable historical/source claim.

The detailed 31-row ledger is in
`stage0-source-test-and-repository-verification.md`.

### Result

| Classification | Count | Meaning |
|---|---:|---|
| `independently_confirmed` | 19 | Direct evidence reproduced or meaning independently re-read |
| `confirmed_but_duplicate` | 7 | Correct but same root issue already counted |
| `confirmed_with_narrower_scope` | 3 | Defect confirmed; remedy/claim narrowed |
| `reasonable_architecture_inference` | 1 | Useful but requires future owner/design decision |
| `requires_team_architecture_decision` | 1 | Repository cannot select the semantic owner |
| `contradicted_by_repository` | 0 | None of the audit's critical/high findings was reversed |
| `not_reproducible` / `insufficient_evidence` | 0 | The R1 Rev-1 *source claim* is non-reproducible; the audit finding about that absence is reproducible |

Shared wording around lattices, envelopes, clocks, owner gravity, and capability
chains is not independent evidence by itself. The synthesis counts the
underlying repository rule once. The OPS-R15 oracle and same-code rebuild
findings are methodologically independent of the PAO audits.

### Audit recommendations not adopted verbatim

- PAO-R0's recommended P27 decision is retained, but its eventual owner is not
  predicted.
- PAO-R1's nine analytical roles are a review vocabulary, not mandatory
  persisted fields.
- OPS-R15's entire 16-predicate audited kernel is not declared executable or
  uniformly mandatory now. It is re-expressed as the consensus statements and
  task-owned profiles.
- A “thin header” is retained as a semantic possibility, not a shared
  production contract.
- Zero-tolerance semantic predicates are accepted only over closed,
  independently labelled populations; no global operational zero is asserted.

## 6. Cross-anchor agreements

### Strongest contributions worth preserving

| Exact audit/report location | Contribution | Why it survives | Limitation | Destination |
|---|---|---|---|---|
| PAO-R0 Executive/§1.4; audit `ID-001` | Identity above one case is necessary for custody | Directly restates ID §6 and is not implemented elsewhere | Name/owner/schema unresolved | S0-K01 |
| PAO-R0 identifier census; recommended revision §1 | Existing IDs must not be silently repurposed | Code gives each ID a narrower role | Explicit future mapping remains possible | S0-K02 |
| PAO-R0 correction analysis; audit `F-11` | Preserve signed/CAS bytes while correcting semantic association | Supported by integrity and append-only patterns | Sidecar sufficiency unproven | S0-K08; PAO-R36 |
| PAO-R1 Executive/§4; audit `H-01` | External act→evidence→admission→reaction→projection | Best cross-anchor protection against administrative scope inflation and responsibility understatement; this is not a relabelling of repository pattern P13 | Analytical planes, not storage schema | S0-K03/S0-K04 |
| PAO-R1 OBSERVE audit | Observation cannot become authority without new admission | Matches verifier/candidate firewall doctrine | Transition contract family-specific | S0-K05 |
| PAO-R1 absence audit | Missing evidence is unknown, not non-occurrence | Strong fail-closed invariant | Reaction remains claim-specific | S0-K12 |
| PAO-R1 audit/package and compensation examples | Package≠independent opinion; workflow compensation≠financial remedy | Exact semantic collision backed by repository names | Public wording implementation missing | Fixtures/projection tests |
| OPS-R15 Executive/§4.18; audit positive findings | Benchmark passage is bounded, not authority | Methodologically necessary and consistent with capability doctrine | No runnable benchmark yet | S0-K16 |
| OPS-R15 authority-only invalidation | Same bytes can lose authority | Directly follows purpose/competence/freshness semantics | Complete dependency index missing | S0-K12/OPS-R2 |
| OPS-R15 replay/rebuild distinction | Historical cutoff and current rebuild answer different questions | Prevents future knowledge leakage | Exact temporal algebra OPS-R4 | S0-K09 |
| OPS-R15 look-alike/ID/order/adjacent cases | Strong anti-overfitting mutations | Tests semantics rather than fixture names | Sealing/evaluator not implemented | S0-K15/S0-GAP-02 |
| OPS-R15 preservation of failed runs/no post-result edits | Sound benchmark governance | Prevents cherry-picking and silent oracle rewrite | Access/commitment protocol missing | S0-K15 |
| OPS-R15 stale-but-cryptographically-valid record | Separates integrity from semantic currentness | Supported by signing/lifecycle separation | Full public fan-out missing | S0-K07/S0-K08 |

### Common factual agreements

- historical and current repository baselines are identical;
- `PolicyMatter`, `OperationalBoundaryDecision`, `WorldRelease`, and H2 have no
  typed production capability;
- PDC `AuthorityBoundary` is real and purpose-scoped;
- PDC graph authority does not establish matter or claim authority;
- Data Forge legal produces offline corpus/version material consumed by Lex;
- core audit owns package/verification, not independent audit opinions;
- authorization allow records admission, not handler or external success;
- Atlas's doctrine is projection-only, while current code/plan debt remains;
- family-native contracts are more mature than any generic institutional
  envelope;
- retention/runbook documentation is not recovery proof.

## 7. Cross-anchor conflicts

| Conflict | Original positions | Resolution |
|---|---|---|
| Matter owner | R0 prefers PDC; R1 repeats PDC/RQ; O15 assumes H2/PDC subject | Owner unresolved; S0-GAP-01 |
| Boundary verdict object | R1 labels external acts I and anti-roles OUT; O15 repeats mixed events | One plane per verdict; external act external, evidence I, reaction O |
| Common envelope | R0 support envelope, R1 institutional envelope, O15 event envelope | Reject production super-schema; benchmark wrapper is input-only |
| Status model | R0 support state, R1 four state families, O15 multiple state machines | Family state owners plus one authority grammar; benchmark predicates |
| Time model | 9 vs 10 vs 13 clocks | Preserve role distinctions; OPS-R4 decides algebra |
| Public owner | R1 calls Atlas projection owner; code/plan can mint locally | Publication owner supplies record; Atlas renderer only |
| H2 design | R1 future orchestrator; O15 exact gates/states/events | Outcome constraints only; internal architecture open |
| Register standing | R1 says Stage-0 adjudication baseline; audit says census | Non-authoritative method/census |
| Benchmark standing | O15 says accepted executable capstone; audit blocks | Research kernel/extensions only; S0-GAP-02 |

## 8. Transitive consistency findings

The amendments must land as one semantic change set:

- removing PDC as canonical matter owner also removes PDC ownership from R1
  register rows and O15 subject assumptions;
- rejecting the universal envelope removes R1 inheritance and prevents O15
  inputs from carrying expected admissions/reactions;
- deferring clocks to OPS-R4 removes all three common timestamp bundles;
- turning R1's register into a method prevents O15 from treating its 213 rows
  as oracle ground truth;
- converting O15 states to predicates prevents a new runtime lattice from
  leaking back into R0/R1;
- blocking the benchmark prevents other tasks from citing it as capability
  proof, while still allowing them to consume adversarial predicates;
- leaving matter identity provisional requires opaque local subject references
  and explicit non-authority assumptions in every dependent research packet;
- correcting the Atlas role requires public-record predicates to inspect
  canonical upstream state and every controlled renderer.

No report can be amended in isolation without reintroducing these conflicts.

## 9. Stage-0 consensus kernel

The standalone kernel contains **16** candidate statements:

- 2 identity invariants;
- 2 boundary invariants;
- 3 authority invariants;
- 2 temporal invariants;
- 3 custody invariants;
- 4 benchmark invariants.

In compact form:

1. identity above a case is needed, but owner/schema are open;
2. existing IDs are not silently lifetime identity and continuity grants no
   evidence authority;
3. classify one boundary plane at a time;
4. external anti-role acts remain external while PolicyOS owns claim reaction;
5. observation/receipt/authentication/workflow/benchmark/display do not mint
   authority;
6. protected authority closes over subject, purpose, tenant, jurisdiction,
   competence, time, and use;
7. publication owners supply authority; Atlas renders;
8. correction appends and old history remains;
9. preserve temporal roles and cutoff replay; OPS-R4 owns the full model;
10. suspension is durable and wake is a scoped candidate;
11. protected actions get equivalent action-specific reproof, not twenty
    universal gates;
12. content equality is not authority validity; missing decisive evidence is
    not a pass;
13. benchmark observables, not runtime internals;
14. sealed expected results and independent semantic evaluator;
15. permutation/adjacent cases, immutable runs, and preserved dissent;
16. passage is bounded and grants no legal, production, or external authority.

The kernel deliberately excludes package ownership, schemas, full event/state
enumerations, numeric thresholds, operator maps, and universal legal claims.

## 10. Required amendments by report

### PAO-R0

- change result to `research_supported_with_open_owner`;
- preserve functional need and non-reinterpretation guard;
- remove PDC/RQ/core-audit owner conclusions;
- remove common support status/envelope and nine-clock requirement;
- mark relations/cardinality/namespace/transfer/migration unresolved;
- say identity continuity never transports evidence authority;
- preserve non-rewrite, not sidecar sufficiency;
- correct tenant, Atlas, Lex/Data Forge, capability, fixture, pattern, and
  citation claims.

### PAO-R1

- change result to `accepted_narrower_scope`;
- replace Stage-0 adjudication baseline with method/candidate census;
- split all mixed act/evidence/admission/reaction/projection rows;
- retain the 213 rows only as non-authoritative census or reduce to audited
  exemplars;
- recast EC-01..21 as research families, not inheriting contracts;
- remove universal envelope, status/owner-state workflows, common clocks,
  mandatory challenge/cadence/freeze rules, and task reclassifications;
- separate evidence condition/admission from consumer reaction;
- correct owner roles, capability states, history, citations, and patterns.

### OPS-R15

- change result to `blocked_pending_oracle_independence`;
- call the 24-month calendar a scenario catalogue;
- separate visible input from sealed expected outputs;
- require independent declarative semantics; same-code rebuild is diagnostic;
- replace state names/twenty gates/common envelope with observable predicates;
- move legal, KPI, public, cryptographic, world, matter, fleet, multilingual,
  and DR scenarios to task-owned profiles/extensions;
- remove arbitrary efficiency/RPO/RTO thresholds;
- treat institutional/legal answers as scenario axioms or contested labels;
- change failure-pattern “Detected” to proposed/untested;
- state that no benchmark runner/pass exists.

Exact replacement wording is in the amendment plan and revision pack.

## 11. Additional-research decisions

Only two new candidate inquiries are justified:

| Gap | Why new | Blocks |
|---|---|---|
| S0-GAP-01 — Minimum Policy Subject Reference and Semantic-Owner Decision | PAO-R0's owner/ABI answer was rejected; no active task owns the minimum cross-family seam | Canonical PolicyMatter ABI and H2/public binding |
| S0-GAP-02 — Independent Custody-Benchmark Oracle and Evaluator Architecture | OPS-R15 lacks independent truth, evaluator, sealing, and challenge governance; amendment alone cannot supply them | Executable/scored OPS-R15 |

All other named gaps map to existing tasks, pilot facts, implementation
validation, or repository defects:

- OPS-R4: clocks/correction/event order;
- OPS-R2: authority dependency/affected sets;
- OPS-R1/3: suspension/resume/migration;
- OPS-R8: WorldRelease;
- OPS-R10/11: legal/jurisdiction operations;
- OPS-R14 + INT-R7: resilience/long-term verification;
- INT-R5: competence/delegation;
- PAO-R36 + INT-R7/8 + Atlas: public correction;
- deferred PAO tasks: partner-specific institutional interfaces.

## 12. Wave-2 readiness

### Overall

- **Ready immediately:** OPS-R4.
- **Ready after Stage-0 amendments/local assumptions:** most INT and active OPS/
  PAO research, including OPS-R1/2/5/8/10/11/14, INT-R1/2/4/5/7/8/9,
  PAO-R4/36.
- **Reframe before relying:** PAO-R0, PAO-R1, OPS-R15.
- **Blocked by named existing dependency:** INT-R6, deferred PAO-R38/R41.
- **Keep deferred until trigger/pilot:** 33 other deferred rows.
- **H2 architecture blocked:** P2 decisions and sufficient active-task outputs.
- **Executable capstone blocked:** S0-GAP-02 plus engineering and domain
  predicates.

The full 67-task table is in the sequencing report. The synthesis does not
reactivate deferred work based only on appearance in a report.

## 13. Repository defects separated from research

| Defect | Classification | Research implication | Separate action |
|---|---|---|---|
| Decision-validity local path hashes unqualified lineage key | Security/tenancy implementation defect | Never assume lineage storage closes subject/tenant scope | Owner fix and collision test |
| Checkpoint/control-job forms omit full tenant/cell/authority binding | Custody implementation blocker | Generic resume is not authority-safe evidence | Control-plane/H2 prerequisite |
| Unknown jurisdiction falls back to UA | Authority/security defect | Keep wrong/unknown-jurisdiction negative predicate | Lex/OPS-R11 engineering fix |
| Public export CAS-ref redaction test fails | Public/privacy defect | Public correctness capability remains incomplete | Runtime-quality/public-export fix |
| Atlas readiness panels compute readiness locally | Projection authority debt | Doctrine is not current completeness | Atlas producer-binding fix |

None is a reason to invent a new research task, and none is fixed in this
branch.

## 14. Final recommendations

### What is safe to ratify now

Ratify only S0-K01–S0-K16 after owner review. They are semantic constraints,
not contracts or capabilities.

### What must be removed or deferred

Remove or demote:

- canonical PDC/RQ/team/H2 matter or register ownership;
- `support_status`, PAO-R1 evidence/boundary/owner lattices, and OPS-R15 runtime
  state machines;
- universal `PolicyMatter`, institutional evidence, and production event
  envelopes;
- mandatory common clock fields;
- mandatory twenty-gate resume;
- fixed WorldRelease vector/state model;
- 213-row adjudication authority;
- visible expected traces and same-code semantic oracle;
- arbitrary reuse/recompute/RPO/RTO thresholds;
- universal external operator/legal-effect mappings.

### What can be shared

Share only:

- opaque reference obligations, not a final reference schema;
- boundary-plane vocabulary;
- purpose/scope/tenant/jurisdiction/competence/provenance questions;
- authority and lifecycle references to canonical owners;
- append/no-rewrite and replay predicates;
- capability-chain labels;
- benchmark predicates and bounded-result vocabulary.

Keep payloads, evidence verification, lifecycle transitions, public correction,
and family clocks family-native until their owners accept composition.

### Smallest coherent next action

`team-architecture` should review and decide the 16-statement consensus kernel,
require amendments to the three source reports, and commission S0-GAP-01 and
S0-GAP-02. It can then dispatch the ready Wave-2 research under the ten local
assumptions without waiting for production contracts.

## 15. Limitations

- Original PAO-R0 and PAO-R1 bytes/hashes were unavailable; exhaustive
  source-level patching requires them.
- OPS-R15's source hash is audit-recorded rather than independently rehashed in
  this consolidation checkout.
- Current and historical baselines are the same; the synthesis cannot evaluate
  future repository evolution.
- Static review and selected tests cannot prove partner competence, legal
  effect, institutional performance, production recovery, or hidden-system
  behavior.
- The available environment does not match the repository's full pinned
  Python/Node/browser toolchain; inherited audit failures and bounded reruns are
  reported, not laundered into semantic conclusions.
- Audit agreement may share the identity decision and capability doctrine as
  premises. The matrix therefore de-duplicates shared roots and preserves
  architecture judgment as judgment.
- S0-GAP identifiers, owner suggestions, task readiness, and replacement text
  remain non-authoritative proposals.
