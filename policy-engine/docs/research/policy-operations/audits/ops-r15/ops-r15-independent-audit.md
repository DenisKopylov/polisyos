---
title: Independent audit of OPS-R15 custody capstone
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

# Independent Benchmark-Validity, Executability, and Adversarial Audit of OPS-R15


## 1. Audit scope and standing

This audit treats the supplied 2,672-line Markdown artifact (SHA-256 `0c3baf41df8ae02bd9f9ae88cc9f1a350d7f4e33021a94327c3e578044690d15`) as an object under adversarial review. It does not implement H2, ratify a runtime contract, certify legal compliance, or prove production recovery. Repository facts are pinned to the commits in frontmatter; methodological judgments are this audit's research findings.

The audit used six lenses: repository truth, benchmark validity, oracle independence, executability, anti-overfitting strength, and Stage-0 proportionality. It normalized the report mechanically, inspected code/tests/history, ran selected tests and temporary probes, checked both Stage-0 audit branches, and checked cited primary sources. Every one of the 117 frozen-calendar rows is dispositioned in the companion ledger; every one of the 36 metrics and each of the seven named oracle families is audited separately.

## 2. Historical and current baselines

| Baseline | Resolution | Consequence |
|---|---|---|
| Historical A | `4813b49f6ce14e8debf3aaea096f0967d38d9768` | Exact report baseline. |
| Pinned current B | `4813b49f6ce14e8debf3aaea096f0967d38d9768` | `origin/main` at audit start. The audit branch was created from this exact commit. |
| Delta | Identical SHAs | No claim can be “historically true but stale now” in this audit. Historical and current verdicts are identical unless an external fact changed. |

The commit is `docs: ratify PolicyOS identity and custody boundary; reshape Wave-2 research; audit both plans`. `git log`, `git show`, and path inspection were therefore performed at one immutable tree. The report's inspection date postdates the commit, but that does not alter the tree.

## 3. Relationship to PAO-R0 and PAO-R1 audits

The unmerged audits are non-authoritative inputs:

- [PAO-R0 independent audit](https://github.com/DenisKopylov/polisyos/blob/258aa740efcfb9e6771bfe52d4fdabc6b74f93a7/policy-engine/docs/research/policy-operations/audits/pao-r0/pao-r0-independent-audit.md), commit `258aa740efcfb9e6771bfe52d4fdabc6b74f93a7`, [draft PR #1](https://github.com/DenisKopylov/polisyos/pull/1): confirms the need for a durable matter concept but does **not** establish the final PDC owner, status grammar, namespace/federation semantics, clocks, or production `PolicyMatter` contract.
- [PAO-R1 independent audit](https://github.com/DenisKopylov/polisyos/blob/566840c330e867a15313923c87c20b6863cb053f/policy-engine/docs/research/policy-operations/audits/pao-r1/pao-r1-independent-audit.md), commit `566840c330e867a15313923c87c20b6863cb053f`, [draft PR #2](https://github.com/DenisKopylov/polisyos/pull/2): preserves the external-act/evidence/admission/reaction/projection split and anti-roles, but rejects the full boundary register, universal institutional envelope, parallel states, exact clocks, and several owner assignments as a Stage-0 freeze.

| OPS-R15 dependency | Classification | Audit consequence |
|---|---|---|
| Stable, opaque matter-capable references | `supported_by_pao_r0_audit` | Safe as optional opaque fixture aliases only. |
| Matter split, successor and inheritance rules | `requires_cross_anchor_consolidation` | Calendar events 089, 090, 109 and 110 are extension fixtures, not ground truth. |
| Event-to-matter binding and PDC ownership | `unsafe_to_freeze` | No production `PolicyMatter` owner/consumer exists. |
| Administrative anti-roles | `stable_ratified_invariant` | Safe kernel predicate. |
| External act vs evidence interface | `supported_by_pao_r1_audit` | Use two rows/layers; 16 calendar rows currently collapse them. |
| Full four-way register and common evidence envelope | `contradicted_by_stage0_audit` | Not a benchmark oracle. |
| Claim-reaction and public-correction duty | `stable_ratified_invariant` with task-specific details pending | Safe predicate; exact public states remain PAO-R36/Atlas work. |
| Tenant/jurisdiction closure | `stable_ratified_invariant` | Safe fail-closed predicate; current primitives are incomplete. |

OPS-R15 must be evaluated against ratified invariants plus both audits' narrowed recommendations. The original PAO reports may remain alternative synthetic assumptions, but they cannot silently define oracle truth.

## 4. Executive verdict

**Overall result: `blocked_pending_oracle_independence`.**

OPS-R15 contains a strong custody invariant and a useful adversarial scenario catalogue, but the supplied artifact is not yet an independent executable benchmark. Its visible Markdown co-locates inputs and expected results, defines 117 one-off calendar event names that do not resolve to its 92-type event vocabulary, supplies no machine-readable oracle artifacts or runner, gives no independent authorship or commitment protocol, and does not exclude a same-code “clean rebuild.” Passing such a realization could certify agreement with the report's future architecture rather than custody correctness.

The smallest 16-predicate Stage-0 kernel is accepted as **safe research guidance**, not as a passed or runnable benchmark. The 24-month scenario, state names, 13-clock envelope, twenty universal gates, exact WorldRelease model, numerical efficiency and RPO/RTO thresholds, institutional authority outcomes, and most domain extensions are deferred.

| Lens | Verdict |
|---|---|
| A — repository truth | `confirmed_with_material_revisions`: local primitives exist; end-to-end custody, matter, boundary register, WorldRelease and H2 do not. |
| B — benchmark validity | `accepted_narrower_scope`: fixed-scenario conformance can support a bounded claim after oracle separation; one municipal case has no broad external validity. |
| C — oracle independence | `blocked`: seven oracle families are prose authored with the architecture; no independent executable artifact or clean-room reference exists. |
| D — executability | `blocked`: all 117 calendar rows are underspecified as executable fixtures and 87 event names are outside the declared vocabulary. |
| E — anti-overfitting | `conceptually strong, operationally incomplete`: ID permutation, adjacent cases and sealed sets are sound ideas, but sealing/access/rotation are undefined and expected outputs are visible. |
| F — Stage-0 proportionality | `kernel accepted, extensions deferred`: semantic predicates are safe; schemas, states, clocks, gates, owners, SLOs and institutional results are not. |

### Required component verdicts

| Component | Verdict |
|---|---|
| 1. Bounded composition claim | `confirmed_with_qualification` |
| 2. Principal custody invariant | `confirmed` |
| 3. 24-month scenario | `fixture_only`; useful extension catalogue |
| 4. Event vocabulary | `partially_refuted`; 87/62 mismatch |
| 5. Common event envelope | `premature_runtime_contract`; retain test wrapper only |
| 6. Multi-clock model | `accepted_as_roles`; 13-field freeze rejected |
| 7. Lifecycle state machines | `convert_to_predicates` |
| 8. Typed wake conditions | `confirmed_as_property`; exact enum deferred |
| 9. Twenty resume gates | `partially_refuted`; phase/condition partition required |
| 10. Artifact/authority dependency separation | `confirmed_with_qualification` |
| 11. World-release semantics | `extension_deferred` |
| 12. Legal-change subscenario | `extension_accepted_as_fixture`, owner/contract pending |
| 13. KPI and learning subscenario | `extension_deferred` |
| 14. Public-record/signature subscenario | `profile_accepted_with_qualification` |
| 15. Administrative traps | `strong; preserve with act/interface split` |
| 16. RPO/RTO targets | `unsupported illustrative numbers` |
| 17. Semantic oracle | `oracle_not_independent` |
| 18. Clean-rebuild oracle | `oracle_circular unless independent reducer is supplied` |
| 19. Historical-replay oracle | `partially_supported; unexecutable` |
| 20. Authority oracle | `scenario_axiom / external_validation_required` |
| 21. Human-review oracle | `under-specified` |
| 22. Fault oracle | `synthetic target only` |
| 23. Metric suite | `mixed`; correctness metrics salvageable, thresholds mostly unjustified |
| 24. Hidden fixtures / anti-overfitting | `conceptually strong, governance missing` |
| 25. Contract sketches | `research_only; not safe to freeze` |
| 26. Stage-0 anchor packet | `replace with 16-predicate kernel` |
| 27. Readiness to constrain Group-B | `not ready beyond kernel invariants` |

## 5. Highest-severity findings

1. **Critical — self-authored oracle/circular certification.** The same report specifies the future state machines, event trace, expected wakes, impact sets, public states and “oracle” labels. No separately authored or committed semantic oracle exists. Expected results are visible in the calendar and in proposed envelope fields.
2. **Critical — clean rebuild is not independent.** The report never requires a different reducer, dependency source, admission path or validator. The temporary probe demonstrated that a deliberately faulty reducer returns the same wrong value incrementally and in a full rebuild. Equality is consistency, not correctness.
3. **Critical — custody resume can lose security context if current fragments are composed naively.** `CheckpointMetadata` contains no tenant, cell or authority boundary. `control_jobs` persists neither tenant nor cell, while diagnostics may default to `tenant-unknown`/`cell-unknown`. These are not proofs of an exploitable production path; they are decisive evidence that generic resume is not yet authority-safe.
4. **Critical — current jurisdiction lookup fails the proposed no-fallback invariant.** Unknown or absent codes select `UkrainianJurisdiction`. The benchmark correctly wants a kill fixture, but incorrectly presents the reusable baseline as if the gate exists.
5. **Critical — external acts and evidence interfaces remain mixed.** Sixteen calendar rows label legislation, notice dispatch, institutional reorganization, appeal outcomes, compensation/payment stages or repeal as `INTEGRATE`. The safe unit is external act (not PolicyOS performance) plus separate evidence receipt/admission/reaction.
6. **High — the calendar is not a schema.** There are 117 unique calendar names, 92 declared event types, 87 calendar-only names and 62 unused declared types. The report has no mapping, so an implementation cannot know which payload contract or reducer applies.
7. **High — twenty universal gates are an architecture chokepoint.** Public-record implications and budget are not pre-resume requirements for every historical or low-risk operation; several checks are conditional, action-specific, pre-signing/pre-publication, or asynchronous.
8. **High — parallel state and envelope gravity.** Case, evidence, public, world, benchmark and verification labels have no canonical owner mappings and duplicate or pre-empt OPS-R1/R4/R8, PAO-R36 and PAO-R1.
9. **High — arbitrary performance thresholds.** Reuse `.75`, minimal recompute `.90`, precision `.95`, DR `.95`, reviewer false positive `.10`, and the RPO/RTO values have no repository, pilot or source-derived basis.
10. **High — “Detected” misstates proposed coverage.** Appendix H has correctly selected failure-pattern concepts, but no OPS-R15 runner has executed them. The status must be “represented by proposed fixture; untested.”

## 6. Strongest Contributions Worth Preserving

| Report location | Contribution | Evidence/methodological support | Limitation | Disposition / destination |
|---|---|---|---|---|
| Executive finding / §4.18 | A bounded composition claim is not universal proof or production authority. | Repository capability doctrine; NIST distinguishes fixed-benchmark from generalized performance. | Current report still overextends one case. | Preserve unchanged in kernel standing. |
| §4.7 | A wake only authorizes evaluation; resume must re-prove authority. | Ratified custody decision; current checkpoint lacks authority closure. | Exact wake enums are premature. | Preserve predicate K02/K04/K05; OPS-R1/3 owns contracts. |
| §4.9 | Payload validity and authority validity are distinct. | `AuthorityBoundary`, source revocation/expiry, Decision-Validity. | Two canonical graphs are not yet proven necessary. | Preserve semantic predicate K07; OPS-R2 decides representation. |
| §4.17 | Historical replay differs from current rebuild. | Bitemporal service, checkpoints, retention guidance. | Visibility sets and equivalence function are absent. | Preserve K09–K11 after sealed cutoffs. |
| §4.14 / calendar 073–075 | External administrative actions must not be performed or overclaimed. | Ratified anti-roles; PAO-R1 audit. | Act/interface labels need splitting. | Preserve K14 and institutional extension pack. |
| Calendar 008–009 | Incomplete and look-alike evidence must not close an exact obligation. | P32 resolve-bind-verify and P33 variant principle. | Independent obligation oracle required. | Preserve in 24-fixture kernel. |
| Calendar 017/077/078 | Race, duplicate and out-of-order controls target committed effects, not requests. | Control leases/outbox; distributed-systems method. | No current custody receipts. | Preserve K03/K08. |
| Calendar 029/091/094A | Cryptographic validity does not establish current semantic authority. | Core signing/audit plus authority boundary. | Long-term profile remains INT-R7 work. | Preserve K07/K13; cryptographic extension. |
| §6.1 | Critical failures cannot be averaged away by a weighted score. | Authority and safety properties are conjunctive. | Requires closed denominators and independent labels. | Preserve unchanged. |
| §7 | ID permutation, delivery-order permutation, adjacent unseen cases and no post-result edits. | P29/P33; NIST metamorphic testing; Magenta Book preregistration. | Sealing/rotation/access model missing. | Preserve with operational governance. |
| §8 | Preserve failed runs, dissent, contested and unresolved outcomes. | Auditability and non-majority laundering. | Human-review protocol incomplete. | Preserve in benchmark governance. |
| Appendix F | Runbook existence is not recovery proof. | Retention/recovery decision and NIST SP 800-34. | Synthetic exercise is not production DR. | Preserve in resilience profile. |

## 7. Benchmark-validity verdict

The report currently mixes at least six evaluation products: semantic conformance, architecture conformance, incremental-computation efficiency, resilience exercise, institutional/legal scenario simulation, and human adjudication. A pass has a coherent interpretation only if scoped to “this implementation satisfied independently specified predicates for this frozen input population.” It cannot establish generalized lifetime custody, legal correctness, production availability, or fitness across jurisdictions.

The corrected architecture therefore has one mandatory semantic kernel, several conformance profiles and optional domain packs. Correctness metrics are conjunctive. Efficiency and timing diagnostics cannot compensate for a semantic failure.

## 8. Oracle-independence verdict

Seven named oracle families exist in prose: frozen semantic, clean rebuild, historical replay, authority, public record, human review and fault recovery. The calendar uses 98 distinct oracle-label strings without a registry mapping them to those families. None is shipped as a separately committed machine artifact.

- **Semantic:** expected trace is authored beside the runtime proposal; circular until independently adjudicated and sealed.
- **Clean rebuild:** same-code full rebuild may reproduce the same dependency/validator/admission defect. It is a consistency oracle only unless an independent reducer is used.
- **Replay:** useful cutoffs exist, but visible artifacts/rules/versions and semantic equivalence are not sealed.
- **Authority:** competent actor, legal effect, finality and matter identity are scenario axioms, contested labels or jurisdiction-specific judgments—not universal benchmark truth.
- **Public:** terms are benchmark-authored and ownership is distributed; PAO-R36/Atlas mappings are unresolved.
- **Human:** three reviewers without assignment, blinding, training, conflicts, agreement statistic, adjudication and drift policy are not reproducible.
- **Fault:** virtual/synthetic recovery can establish semantic behavior in the test environment, not production capacity or SLO compliance.

## 9. Executability verdict

No runner, machine-readable calendar, schemas, sealed expected outputs, reference evaluator, fixture-root commitment, or generated run receipt accompanies the report. All 117 rows are therefore `underspecified`, not executable today. This is not an objection to Markdown as research; it is an objection to calling the Markdown a capstone benchmark.

Mechanical normalization found:

| Item | Exact count |
|---|---:|
| Lines / headings / Markdown tables | 2,672 / 192 / 54 |
| Calendar events / unique IDs | 117 / 117 |
| Numeric ID range | 001–115, plus 064A and 094A; no gaps/duplicates |
| Calendar event names / unique | 117 / 117 |
| Declared vocabulary types / unique | 92 / 92 |
| Calendar names not declared | 87 |
| Declared types absent from calendar | 62 |
| Actors | 22 |
| Wake conditions | 15 |
| Resume gates | 20 |
| Metrics | 36 |
| Fault classes | 34 |
| Replay checkpoint rows | 8 |
| Calendar oracle labels | 98 |

## 10. Stage-0 proportionality verdict

Safe to freeze: the custody promise; durable suspension independent of a live worker; exact typed wake binding; mandatory re-admission before authority-bearing action; tenant/jurisdiction fail-closed behavior; payload-versus-authority invalidation; append-only correction; historical/current separation; dedupe/out-of-order safety; no external execution; and controlled-surface stale/current honesty.

Not safe: exact event/state enum names, a universal 13-clock envelope, a production PolicyMatter schema, WorldRelease lifecycle, two canonical dependency graphs, five exhaustive impact sets, all-twenty-gates-on-every-resume, public status vocabulary, numerical efficiency/SLO targets, institutional authority outcomes, or H2 owner assignment.

## 11. Repository capability audit

| Primitive | Historical/current evidence | Actual chain state | What it proves / does not prove |
|---|---|---|---|
| Control jobs, events, leases, outbox | [policy-engine/src/polisyos/runtime/http/services/control_plane_store.py](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/runtime/http/services/control_plane_store.py) | `implemented` for local control | Durable scheduling fragments; not matter-aware custody. |
| Checkpoint/fingerprint/resume | [policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py) | `implemented` computationally | Schema/fingerprint/cache replay; no tenant/cell/authority reproof. |
| Tenant CAS | [policy-engine/src/polisyos/core/artifacts/store.py](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/artifacts/store.py) | `implemented` narrow | Artifact ownership checks; does not close job/checkpoint identity. |
| Watermark/cursor/bitemporal | [policy-engine/src/polisyos/fabric/data_plane/watermark.py](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/fabric/data_plane/watermark.py); runtime temporal | `implemented_but_not_orchestrated` | Event-time and valid/transaction reads; no universal 13-clock contract. |
| AuthorityBoundary | [policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py) | `implemented` narrow | Purpose-scoped weakest-boundary composition; not a custody dependency graph. |
| SourceContract | [policy-engine/src/polisyos/fabric/connectors/contracts/source_contract.py](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/fabric/connectors/contracts/source_contract.py) | `implemented` data-focused | Strong source contract; not a universal institutional event. |
| Decision-Validity | [policy-engine/src/polisyos/core/contracts/decision_validity.py](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/contracts/decision_validity.py) | `implemented_but_not_orchestrated` | Typed dependency invalidation; no matter fleet fan-out. |
| Continuous lifecycle/reissue | [policy-engine/src/polisyos/scientist/governance/continuous/lifecycle_bridge.py](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/scientist/governance/continuous/lifecycle_bridge.py); reissue module | `implemented_but_not_orchestrated` | Scoped append-only reaction; no 24-month orchestrator. |
| Lex legal pipeline | [policy-engine/src/polisyos/data_forge/domains/legal/batch](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/data_forge/domains/legal/batch) | `implemented_but_not_orchestrated` | Amendment/reference primitives; unknown jurisdiction fallback is unsafe for governed use. |
| DDM/KPI | `src/polisyos/ddm`, feedback contracts | `partial_internal_owner` | Local detection/monitoring; no full OPS-R5 protocol. |
| Core audit/signing | [policy-engine/src/polisyos/core/audit](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/audit) | `implemented` narrow | Portable verification/tamper tests; not semantic currency or long-term public profile. |
| Public projection | Atlas plan/runtime APIs | `planned/partial`, many `surface_missing` | Projection doctrine; no OPS-R15 canonical public state. |
| PolicyMatter | decision/backlog only | `planned_only` | Need is ratified; contract/owner/consumers unresolved. |
| OperationalBoundaryDecision | backlog only | `planned_only` | Research task; no canonical register. |
| WorldRelease | backlog/decision language | `planned_only` | Negative compatibility principle; no producer/head. |
| H2 custody runtime | future task | `producer_missing` | No end-to-end custody runtime. |

## 12. Calendar consistency audit

No hard impossible date order was proven by the compact calendar. Future-effective legislation and the deliberately out-of-order correction are plausible. That finding is weaker than executability: clock roles are abbreviated, most receipt/transaction/admission values are omitted or “inherited,” and the owner of transaction time is not stated.

All event rows require at least qualification because implementation-visible rows contain their own expected wake, impact, action, prohibited action, public result and oracle. Disposition counts are: qualify `44`, split `30`, defer `43`, preserve `0`, merge `0`, remove `0`. The companion ledger records each row and the reason.

## 13. Metric and threshold audit

The suite has 36 unique names and no duplicates. Strong correctness candidates include lost state, stale current display, unauthorized upgrade, historical rewrite, missed affected cases, duplicate committed irreversible effects, out-of-boundary external action, wrong-jurisdiction fallback, invalid artifact reuse, wake correctness, authority-loss detection and selective exclusion. Each needs a frozen population, explicit instrumentation and independent oracle.

Efficiency and performance values—reuse, minimal recompute, precision, DR aggregate success, human false positives and time deadlines—are unsupported. They invite Goodhart pressure toward unsafe pruning and cannot be Stage-0 kills. The metric companion file supplies a formula, denominator, gaming strategy and correction for every metric.

## 14. State-machine audit

The case/evidence/public/world state diagrams are useful semantic explanations but unsafe canonical enums. Existing owners already have job, Decision-Validity, lifecycle, source, audit and publication states. Require observable predicates such as “no authority-bearing action occurred before current evidence admission” or “old public bytes remain retrievable with a successor link,” then allow each accepted owner to map those predicates to local state.

## 15. Resume-gate audit

The report's twenty checks contain valuable material but are phase-confused. The corrected model is:

- unconditional integrity/binding checks: state integrity, exact case/subject, tenant/cell, compatible executable representation;
- conditional authority checks: principal, action authorization, delegation, step-up, rules, validator, governed release, obligation and freshness;
- action-specific checks: budget, certified envelope and human review;
- pre-signing/pre-publication checks: public-record implications and publication authority;
- asynchronous diagnostics: complete dependency impact can continue after safe resume if no affected authority action is permitted.

The benchmark should require equivalent protection, not identical gate count or atomic implementation.

## 16. Event-envelope audit

As a **test-only fixture wrapper**, a common envelope can normalize identifiers, event type, source, subject scope, tenant/jurisdiction, a minimal recorded-at time, provenance reference and payload reference. It must not become a universal production `ExternalEvent`.

Remove `expected_wake`, `expected_impact`, `expected_policyos_actions`, public answer and `oracle_ref` from implementation-visible input. Move them to a sealed oracle. Keep family clocks/payload semantics with Fabric, Lex, DDM, authorization, audit and publication owners. Consumer-calculated `permitted_downstream_actions` and claim reaction do not belong in an external producer record.

## 17. Dependency and clean-rebuild audit

Artifact validity and authority validity are a necessary semantic distinction. The report has not shown that two new canonical graph products are necessary or sufficient; identity, public, human and institutional dependencies may be projections or edges owned elsewhere. The five impact sets may overlap and are not exhaustive.

Minimal recomputation must never be optimized against an oracle derived from the same graph implementation. A correct reference path needs independently declared dependencies or a different reducer. Semantic equality must define authority boundaries, public posture and accepted nondeterministic fields—not only payload bytes.

## 18. Temporal audit

Existing repository semantics primarily establish valid-at, transaction-at, event-time/watermark and component-specific occurrence/recording times. OPS-R15 proposes thirteen common clocks. Many are family-specific, derivable or event references:

- storage owns transaction/recorded time;
- source owns event/observation/publication/effective facts where meaningful;
- PolicyOS admission owns admission time;
- correction/revocation should generally be linked events, not mutable timestamp slots;
- review due/expiry are obligation/dependency fields, not universal event clocks.

OPS-R4 must settle definitions, optionality, order and replay. Stage 0 should freeze only the predicate that distinct time roles must not be conflated.

## 19. Resilience and RPO/RTO audit

The 34 fault rows are valuable as a taxonomy. Separate semantic recovery, storage recovery, workflow retry, public reconciliation, key recovery, source outage and third-party outage. Virtual-time tests may prove semantic deadlines; single-node integration tests may prove local recovery behavior; production-like exercises are required for capacity/SLO evidence.

Zero RPO and 1/4/8/24/48/72-hour values are unsupported illustrative exercise parameters. The 10,000-case fan-out is a scale fixture, not proof that the deferred scheduler or production infrastructure meets a target. Asymmetric CAS/control-DB restore is strong and should remain in the resilience profile.

## 20. Anti-overfitting audit

Public core, sealed semantic variants, ID and order permutation, wrong-scope variants, adjacent cases, no event-ID branching, preregistration and preserved failed runs are sound. Current controls remain conceptual:

- no role/access matrix or storage location for sealed artifacts;
- no public cryptographic commitment format;
- no audit-log owner or leak response;
- no run budget before hidden cases become learned;
- no rotation/retirement frequency;
- only two hidden variants per class are suggested;
- Git history leakage is not addressed.

Until that model exists, all 117 visible rows carry high overfitting risk because expected outcomes are disclosed.

## 21. Cross-task premature-specification audit

| Concept | Proper owner/task | OPS-R15 standing |
|---|---|---|
| Matter identity/split/successor | PAO-R0 | Fixture alias/provisional extension only. |
| Operational boundary register/envelope | PAO-R1 | Use ratified anti-roles and audited split, not full report schema. |
| Wake/suspension/resume | OPS-R1/3/future H2 | Benchmark predicates only. |
| Dependency impact | OPS-R2 | Recall predicate; graph schema deferred. |
| Time roles | OPS-R4 | Non-conflation predicate; exact clocks deferred. |
| KPI/learning | OPS-R5/INT-R4/DDM | Optional profile. |
| WorldRelease | OPS-R8/GY-N12/Fabric | Compatibility negative; state/vector deferred. |
| Legal change/jurisdiction | OPS-R10/11/Lex | Optional profile and scenario axioms. |
| Recovery/preservation | OPS-R14/INT-R7/core audit | Synthetic profile; no production SLO. |
| Public correction | PAO-R36/Atlas/publication | Append-only/current-honesty predicate; exact labels deferred. |
| Individual decisions | PAO-R4 | Negative boundary probe only. |
| Benchmark governance | OPS-R15 evaluator | Manifest, independent oracle, sealed access and result versioning. |

## 22. External-source audit

Primary/official sources were checked on 2026-07-27:

- [Temporal documentation](https://docs.temporal.io/) supports durable replay after failures, not PolicyOS authority correctness.
- [Apache Beam Programming Guide](https://beam.apache.org/documentation/programming-guide/) supports event/processing time, watermarks, triggers and late data, not legal materiality.
- [Build Systems à la Carte](https://www.microsoft.com/en-us/research/publication/build-systems-a-la-carte/) supports executable comparison of incremental build designs; it does not make a same-code rebuild independent.
- [NIST SP 800-34 Rev. 1](https://csrc.nist.gov/pubs/sp/800/34/r1/upd1/final) supports contingency planning/testing, not these RPO/RTO numbers.
- [Principles of Chaos Engineering](https://principlesofchaos.org/) favors measured output and realistic controlled faults, but explicitly prefers production experiments; a synthetic run is not production evidence.
- [PREMIS 3](https://www.loc.gov/standards/premis/v3/index.html), [RFC 7089](https://www.rfc-editor.org/info/rfc7089/), [RFC 4998](https://www.rfc-editor.org/rfc/rfc4998.html) and [RFC 9162](https://www.rfc-editor.org/rfc/rfc9162.html) support preservation/version/log-integrity mechanisms, not current semantic authority.
- [ELI](https://op.europa.eu/en/web/eu-vocabularies/eli) and [Akoma Ntoso 1.0](https://docs.oasis-open.org/legaldocml/akn-core/v1.0/akn-core-v1.0-part1-vocabulary.html) support legal identifiers/metadata/structure, not jurisdictional competence.
- [Magenta Book 2026](https://www.gov.uk/government/publications/the-magenta-book/magenta-book-central-government-guidance-on-evaluation-html) accurately supports proportionate preregistration and documented amendments.
- [NIST ARIA](https://www.nist.gov/publications/assessing-risks-and-impacts-ai-aria-pilot-evaluation-report), [NIST statistical benchmark work](https://www.nist.gov/publications/expanding-ai-evaluation-toolbox-statistical-models), [NIST metamorphic testing](https://www.nist.gov/publications/metamorphic-testing-cybersecurity), and [AI RMF 1.0](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10) support contextual evaluation, uncertainty and oracle-relations; none validates OPS-R15 architecture.
- [UK ATRS](https://www.gov.uk/government/publications/guidance-for-organisations-using-the-algorithmic-transparency-recording-standard/algorithmic-transparency-recording-standard-guidance-for-public-sector-bodies) and the [EU AI Act](https://eur-lex.europa.eu/eli/reg/2024/1689/oj?locale=en) support bounded institutional roles in their jurisdictions, not universal PolicyOS allocations.

The report's external-source summaries are generally accurate and appropriately caveated. Their defect is inferential: general engineering/evaluation patterns are sometimes used to make detailed report-authored contracts appear settled.

## 23. Failure-pattern audit

Historical and current failure-pattern registers are identical. Every cited ID resolves to the intended concept; the substantive defect is coverage standing, not mostly ID selection.

| Reference | Historical/current concept | ID correct? | Actual coverage | Required correction |
|---|---|---|---|---|
| P01 | Contract-only capability | Yes | Report demonstrates the risk; no runner | “Represented; not detected.” |
| P02 | Mature fragments without bridge | Yes | Central repository condition | Preserve as benchmark target. |
| P03 | Rich internal state, poor external surface | Yes | Proposed public fixtures | Untested. |
| P04 | Status proliferation | Yes | Report itself creates lattice risk | Change “reduced” to “material unresolved risk.” |
| P05/P15 | Authority dilution / LLM laundering | Yes | Proposed negative controls | Untested. |
| P07/P08 | Replay / time-role gaps | Yes | Proposed cutoffs and late events | Untested end to end. |
| P09 | Warning lifecycle | Yes | Expiry scenarios | Untested. |
| P10 | Structural-only validation | Yes | Relevant; same-code oracle may repeat it | Add independent reducer. |
| P11/P12 | Balanced memory / producer handshake | Yes | Weakly covered | Keep diagnostic, not kill. |
| P13 | Contract gravity/proportional governance | Yes | Twenty gates trigger P13 themselves | Partition gates. |
| P14/P19/P21/P24/P26 | Independence, aggregation, capacity, strategic response, human integrity | Yes | Domain extensions | Defer to profiles. |
| P27/P28 | Canonical-owner bypass / unstrangled legacy | Yes | Owner risks real; generic-resume probe future | Untested. |
| P29 | Authorial proof | Yes | Central oracle defect | Report itself currently fails this pattern. |
| P31/P32/P33/P34 | Chokepoint, resolve-bind-verify, teaching-to-test, exclusion isolation | Yes | Strong proposed probes | Operational artifacts absent; say “proposed.” |

## 24. Recommended final posture

Replace `accepted_narrow_scope` with:

> **`blocked_pending_oracle_independence`** for the complete OPS-R15 artifact. The principal custody invariant and a 16-predicate Stage-0 kernel are accepted as research guidance. No benchmark pass is possible until implementation-visible inputs, sealed expected outputs, independent reference semantics, denominator commitments, evaluator governance and executable artifacts exist. Domain scenarios and numerical targets are extension packs, not shared Stage-0 law.

## 25. Required corrections

1. Publish a machine-readable fixture manifest and schema; resolve all 87/62 event-vocabulary mismatches.
2. Split implementation-visible inputs from sealed expected outputs and remove answer-bearing envelope fields.
3. Commission an independently authored semantic oracle and declarative/clean-room reference reducer.
4. Define per-cutoff visibility, versions and semantic equivalence for historical replay.
5. Treat authority/legal/matter outcomes as synthetic axioms or contested labels, not universal truth.
6. Split sixteen external-act rows from evidence receipt/admission/reaction.
7. Replace state names with observable predicates and canonical-owner mappings.
8. Replace twenty universal gates with phased/conditional equivalent-protection requirements.
9. Demote arbitrary efficiency and RPO/RTO thresholds to diagnostics/illustrative exercise parameters.
10. Define hidden-fixture access, commitment, run budget, leakage response, rotation and retirement.
11. Change every Appendix-H “Detected” to “represented by a proposed fixture; unexecuted.”
12. Freeze only the 16-predicate kernel and route every extension to its task owner.

## 26. Commands and results

Detailed commands are in `ops-r15-test-and-probe-verification.md`. Key results:

- prescribed bootstrap could not start in the base environment; the available environment used Python 3.12.13 and Node 24.14.0 while repository diagnostics require Python 3.14 and Node 22.x;
- targeted control-store tests: 16 passed;
- checkpoint/GC: 40 passed, 1 environment-sensitive failure under Python 3.12;
- Fabric cursor/watermark/temporal group: 34 passed;
- legal jurisdiction/temporal group: 15 passed;
- a governed-projection cache test failed in the unsupported toolchain/filesystem environment and prevents a blanket green projection claim;
- Decision-Validity contract/service, lifecycle bridge, partial reissue, CAS integrity, signing and external audit targeted tests passed as recorded;
- a tenant-CAS test and authorization tests had failures under the unsupported environment and are not classified as verified repository defects;
- static probes confirmed missing custody security fields, unsafe jurisdiction fallback, correct AuthorityBoundary meet behavior, and same-code rebuild circularity.

## 27. Limitations

- Current and historical repository baselines are identical, so no evolution comparison exists.
- The supplied OPS-R15 artifact is not committed; audit locations refer to its headings and event IDs rather than repository permalinks.
- No production partner, jurisdiction authority, institutional system, sealed fixture store, H2 runtime, benchmark runner or production-like recovery environment was available.
- The unsupported local toolchain prevents a full-suite conclusion. Passing subsets prove only the named local contracts.
- Static inspection cannot prove absence of every hidden action path or external event; absence claims are bounded to `src`, `tests`, architecture/docs/manifests and the exact `rg`/Git searches recorded.

## Claim-to-evidence ledger

The following ledger covers all non-row repository, ownership, capability, benchmark, oracle, metric, temporal, resilience and governance claim families. Calendar claims and metric claims are exhaustively expanded in their companion ledgers.

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Methodological verdict | Confidence | Severity | Dependency | Observability | Capability state | Risk | Required correction |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CLM-001 | Executive finding | Repository has an implemented custody runtime substrate sufficient to support this capstone. | repo/capability | `control_plane_store.py`; checkpoint module at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | `control_plane_store.py`; checkpoint module at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | partially_supported | partially_supported | partial/circular | high | high | H2 | partial | implemented_but_not_orchestrated | overclaim | Say that fragments exist; no custody runtime or end-to-end chain exists. |
| CLM-002 | §2.4 | Durable job storage, leases and outbox exist. | repo fact | `runtime/http/services/control_plane_store.py` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | `runtime/http/services/control_plane_store.py` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | confirmed | confirmed | valid narrow fact | high | info | control plane | full | implemented | none | Preserve narrowly. |
| CLM-003 | §2.4 | Checkpoint/resume carries enough state for authority-safe custody resume. | capability | `scientist/orchestration/engine/checkpoint.py:135` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | `scientist/orchestration/engine/checkpoint.py:135` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted | contradicted | invalid | high | critical | OPS-R3/H2 | full | implemented computationally | underclaim/security | Checkpoint metadata lacks tenant, cell and authority boundary; require equivalent protection before authority-bearing resume. |
| CLM-004 | §2.4 | Control jobs are tenant/cell closed. | capability | `control_plane_store.py:2294`; `run_lifecycle.py:437` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | `control_plane_store.py:2294`; `run_lifecycle.py:437` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted | contradicted | invalid | high | critical | H2/security | full | partial | tenant leakage | Do not reuse control job identity as custody identity; persist and verify tenant/cell closure. |
| CLM-005 | §2.4 | Unknown jurisdiction is fail-closed. | capability | `data_forge/.../jurisdictions/__init__.py:13` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | `data_forge/.../jurisdictions/__init__.py:13` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted | contradicted | valid proposed kill | high | critical | OPS-R11 | full | implemented unsafe fallback | authority leakage | Keep the fixture; record current default-to-UA behavior as a known failing probe. |
| CLM-006 | §2.4 | AuthorityBoundary exists and composes by weakest boundary. | repo fact | `pdc/_impl/layer2_readiness.py:62-116` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | `pdc/_impl/layer2_readiness.py:62-116` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | confirmed | confirmed | valid | high | info | PDC | full | implemented | none | Preserve; it is not a complete custody graph. |
| CLM-007 | §2.4 | Fabric provides event-time watermarks and bitemporal primitives. | repo fact | `fabric/data_plane/watermark.py`; `runtime/http/services/temporal.py` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | `fabric/data_plane/watermark.py`; `runtime/http/services/temporal.py` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | confirmed_with_qualification | confirmed_with_qualification | valid local fact | high | low | Fabric/OPS-R4 | full | implemented_but_not_orchestrated | overclaim | State that local temporal primitives do not settle the common 13-clock model. |
| CLM-008 | §2.4 | Decision-Validity and lifecycle/reissue implement scoped reactions. | repo fact | `core/contracts/decision_validity.py`; `scientist/governance/continuous` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | `core/contracts/decision_validity.py`; `scientist/governance/continuous` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | confirmed_with_qualification | confirmed_with_qualification | valid local fact | high | low | OPS-R2/PAO-R36 | full | implemented_but_not_orchestrated | overclaim | Preserve local capability; do not claim matter-wide fan-out. |
| CLM-009 | §2.4 | PolicyMatter is a current production identity. | capability | decision/backlog only; no source symbol at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | decision/backlog only; no source symbol at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | planned_not_implemented | planned_not_implemented | invalid as fixture identity truth | high | high | PAO-R0 | partial | planned_only | premature design | Treat matter refs as optional opaque fixture aliases pending consolidation. |
| CLM-010 | §2.4 | OperationalBoundaryDecision exists. | capability | backlog only; no source symbol at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | backlog only; no source symbol at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | planned_not_implemented | planned_not_implemented | invalid as production input | high | high | PAO-R1 | partial | planned_only | premature design | Use ratified anti-role predicates, not the unaudited register schema. |
| CLM-011 | §2.4/§4.10 | WorldRelease exists as a governed production vector. | capability | backlog/decision references only at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | backlog/decision references only at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | planned_not_implemented | planned_not_implemented | partial scenario assumption | high | high | OPS-R8/GY-N12 | none | planned_only | premature contract | Move WorldRelease lifecycle and exact vector shape to an extension profile. |
| CLM-012 | §4.1 | One 24-month municipal case can support a bounded composition claim. | benchmark claim | synthetic report fixture at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | synthetic report fixture at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | fixture_only | fixture_only | partial | medium | high | benchmark governance | partial | fixture_only | external validity | Limit inference to fixed-scenario conformance; add independent adjacent families. |
| CLM-013 | §4.3 | The declared event vocabulary is complete for the calendar. | benchmark claim | mechanical normalization at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | mechanical normalization at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted | contradicted | unexecutable | high | high | benchmark governance | full | fixture_only | schema mismatch | Resolve 87 calendar-only names and 62 unused declared types through a versioned mapping. |
| CLM-014 | §4.4 | The common event envelope is a safe production contract. | architecture proposal | multiple existing family contracts at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | multiple existing family contracts at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | unsupported | unsupported | premature_runtime_contract | high | high | OPS-R4/PAO-R1 | partial | research_only | duplicate owner | Keep a test-fixture wrapper; exclude consumer expectations and family-owned clocks from producer input. |
| CLM-015 | §4.4 | Expected wake, impact and actions may travel with implementation-visible fixtures. | benchmark design | calendar/envelope at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | calendar/envelope at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted | contradicted | scenario_overfit_risk | high | critical | benchmark governance | full | fixture_only | oracle leakage | Move every expected result and oracle label to separately committed sealed artifacts. |
| CLM-016 | §4.5 | Thirteen clocks are universally required. | architecture proposal | existing valid_at/tx_at and family clocks at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | existing valid_at/tx_at and family clocks at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | unsupported | unsupported | premature_runtime_contract | high | high | OPS-R4 | partial | research_only | clock proliferation | Require roles/predicates; let OPS-R4 define family-specific clocks and ownership. |
| CLM-017 | §4.6 | Exact case/evidence/public/world state names are benchmark law. | benchmark design | local enums differ; no mapping at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | local enums differ; no mapping at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | unsupported | unsupported | premature_runtime_contract | high | high | OPS-R1/R8/PAO-R36 | partial | research_only | parallel lattice | Replace state names with externally observable predicates and owner-specific mappings. |
| CLM-018 | §4.7 | Wake authorizes resume. | benchmark invariant | report explicitly rejects this at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | report explicitly rejects this at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | confirmed | confirmed | valid | high | info | OPS-R1/H2 | full | research invariant | none | Preserve: wake authorizes evaluation only. |
| CLM-019 | §4.7 | Fifteen exact wake enum values are canonical. | architecture proposal | no matching runtime contract at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | no matching runtime contract at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | unsupported | unsupported | premature_runtime_contract | high | high | OPS-R1 | none | planned_only | duplicate grammar | Test typed binding and false-wake properties without requiring these enum names. |
| CLM-020 | §4.8 | All twenty gates must pass on every resume. | benchmark claim | no runtime gate composition; mixed phases at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | no runtime gate composition; mixed phases at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted | contradicted | unexecutable/overbroad | high | critical | OPS-R3/H2 | partial | planned_only | DoS/chokepoint | Partition core, conditional, action-specific, pre-publication and asynchronous checks. |
| CLM-021 | §4.9 | Artifact and authority invalidation are semantically distinct. | benchmark invariant | AuthorityBoundary + Decision-Validity support distinction at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | AuthorityBoundary + Decision-Validity support distinction at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | confirmed_with_qualification | confirmed_with_qualification | valid | high | info | OPS-R2 | partial | partial_internal_owner | none | Preserve distinction; do not require two canonical graph products. |
| CLM-022 | §4.9 | Five impact sets are disjoint and exhaustive. | architecture proposal | no repository representation at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | no repository representation at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | unsupported | unsupported | premature_runtime_contract | medium | high | OPS-R2 | none | planned_only | premature design | Treat them as possibly overlapping oracle labels pending OPS-R2. |
| CLM-023 | §4.10 | Latest-of-each component selection must not establish a governed world. | benchmark invariant | identity decision/backlog at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | identity decision/backlog at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | confirmed_with_qualification | confirmed_with_qualification | valid negative | high | medium | OPS-R8 | partial | planned_only | none | Preserve as extension predicate, not proof that WorldRelease exists. |
| CLM-024 | §4.11 | Legal publication/effect/repeal clocks must remain distinct. | benchmark invariant | Lex temporal code and failure P08 at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | Lex temporal code and failure P08 at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | confirmed_with_qualification | confirmed_with_qualification | valid | high | info | OPS-R10/R11 | partial | implemented_but_not_orchestrated | none | Preserve in legal-change profile. |
| CLM-025 | §4.12 | KPI threshold crossing may directly alter policy. | benchmark invariant | report prohibits auto-adaptation at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | report prohibits auto-adaptation at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | confirmed | confirmed | valid negative | high | info | OPS-R5/INT-R4 | full | research invariant | none | Preserve negative control. |
| CLM-026 | §4.13 | A signature proving integrity also proves current semantic authority. | benchmark invariant | core signing/audit plus PDC boundary at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | core signing/audit plus PDC boundary at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | confirmed as false claim | confirmed as false claim | valid negative | high | info | INT-R7 | full | implemented fragments | none | Preserve stale-but-cryptographically-valid fixture. |
| CLM-027 | §4.14 | External acts can be labeled INTEGRATE without splitting the evidence interface. | boundary claim | PAO-R1 audit at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | PAO-R1 audit at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted_by_stage0_audit | contradicted_by_stage0_audit | invalid | high | critical | PAO-R1 | full | research_only | scope inflation | Use Model C: external act outside PolicyOS performance; evidence receipt/admission separately integrated/owned. |
| CLM-028 | §4.16 | Zero RPO and 1/4/8/24/48/72-hour RTOs are Stage-0 thresholds. | performance target | no executable environment or empirical basis at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | no executable environment or empirical basis at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | unsupported | unsupported | threshold_unjustified | high | high | OPS-R14/deployment | none | illustrative | performance overclaim | Label as illustrative exercise parameters; production SLOs require deployment evidence. |
| CLM-029 | §4.17 | Frozen semantic oracle is independently adjudicated. | oracle claim | no separate artifact, authorship, commitment or challenge procedure at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | no separate artifact, authorship, commitment or challenge procedure at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | unsupported | unsupported | oracle_not_independent | medium | critical | benchmark governance | none | documented_only | circularity | Create independently authored, machine-readable, precommitted oracle artifacts. |
| CLM-030 | §4.17 | Clean rebuild is an independent semantic oracle. | oracle claim | same-code path not excluded at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | same-code path not excluded at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | unsupported | unsupported | oracle_circular | high | critical | benchmark governance | none | documented_only | shared bug | Require a declarative reducer or independently implemented reference; same-code rebuild is only consistency evidence. |
| CLM-031 | §4.17 | Historical replay is independently specified. | oracle claim | cutoffs stated; version visibility/equivalence function absent at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | cutoffs stated; version visibility/equivalence function absent at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | partially_supported | partially_supported | partial/unexecutable | high | high | OPS-R3/R4 | partial | documented_only | oracle ambiguity | Seal per-cutoff visible inputs, rules and equivalence functions. |
| CLM-032 | §4.17 | Authority panel labels are universal ground truth. | oracle claim | synthetic jurisdiction/institution at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | synthetic jurisdiction/institution at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | unsupported | unsupported | external_validation_required | medium | critical | PAO-R0/PAO-R1/external | none | scenario axiom | authority overclaim | Call them contested scenario axioms; use jurisdiction-specific competent review for pilots. |
| CLM-033 | §4.17 | Three reviewers suffice for reproducible human truth. | oracle claim | no sampling, blinding, training, agreement or adjudication protocol at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | no sampling, blinding, training, agreement or adjudication protocol at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | unsupported | unsupported | oracle_not_independent | high | high | benchmark governance | none | documented_only | reviewer bias | Specify assignment, conflicts, blinding, agreement, dissent, adjudication and drift. |
| CLM-034 | §4.17 | Public state labels are canonical. | oracle claim | PAO-R36/Atlas plans incomplete; local owners distributed at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | PAO-R36/Atlas plans incomplete; local owners distributed at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | unsupported | unsupported | cross_task_dependency_unresolved | high | high | PAO-R36/Atlas | partial | planned_only | parallel lattice | Use semantic public predicates and map them to accepted publication contracts. |
| CLM-035 | §6 | Zero-tolerance correctness metrics are meaningful with closed denominators. | metric claim | metric definitions at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | metric definitions at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | confirmed_with_qualification | confirmed_with_qualification | valid if sealed | high | medium | benchmark governance | partial | fixture_only | open denominator | Preserve only after denominator, instrumentation and independent oracle are frozen. |
| CLM-036 | §6 | Reuse ≥.75, minimal recompute ≥.90, precision ≥.95, DR ≥.95 and reviewer FP ≤.10 are evidence-based. | threshold claim | no repository/external derivation at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | no repository/external derivation at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | unsupported | unsupported | threshold_unjustified | medium | high | benchmark governance | full | illustrative | Goodhart | Demote to diagnostics or calibrate on preregistered pilot data. |
| CLM-037 | §7 | Hidden fixture controls are operational. | governance claim | no access/sealing/rotation/leak process at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | no access/sealing/rotation/leak process at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | documented_not_implemented | documented_not_implemented | partial/conceptual | high | high | benchmark governance | none | planned_only | leakage | Define roles, cryptographic commitment, access logs, run limits, rotation and incident response. |
| CLM-038 | §7 | ID permutation and adjacent unseen cases reduce teaching-to-test. | method claim | P33 and metamorphic-testing literature at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | P33 and metamorphic-testing literature at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | confirmed_with_qualification | confirmed_with_qualification | valid | high | info | benchmark governance | partial | fixture_only | none | Preserve; use more than two variants and rotate. |
| CLM-039 | §8 | Passing the synthetic scenario supports production DR. | production claim | report disclaims this elsewhere at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | report disclaims this elsewhere at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted internally | contradicted internally | invalid | high | critical | deployment | none | fixture_only | external validity | Retain explicit disclaimer; never use pass as production recovery proof. |
| CLM-040 | Appendix C | All calendar events belong to one executable event vocabulary. | benchmark claim | 87/62 name mismatch at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | 87/62 name mismatch at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted | contradicted | unexecutable | high | high | benchmark governance | full | fixture_only | schema mismatch | Publish a normalized input schema and migration mapping. |
| CLM-041 | Appendix C | Each expected impact follows from a declared dependency edge. | benchmark claim | no machine dependency graph/oracle artifact at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | no machine dependency graph/oracle artifact at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | unsupported | unsupported | unexecutable | high | high | OPS-R2 | none | fixture_only | circularity | Seal dependency facts separately and expose only event inputs. |
| CLM-042 | Appendix H | Failure patterns are detected by the report. | test claim | proposed fixtures only at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | proposed fixtures only at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted | contradicted | invalid standing | high | high | all | full | fixture_only | capability overclaim | Replace “Detected” with “represented by proposed fixture; not executed.” |
| CLM-043 | Appendix I | The complete anchor packet may constrain Group-B research now. | governance claim | unresolved PAO/OPS contracts and oracles at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | unresolved PAO/OPS contracts and oracles at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | unsupported | unsupported | premature | high | critical | Group B | none | research_only | authority overclaim | Freeze only the 16-predicate kernel; defer names, schemas, clocks, targets and owners. |
| CLM-044 | Cross-anchor | policy_matter_ref and split/successor semantics are settled. | dependency | PAO-R0 audit commit at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | PAO-R0 audit commit at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted_by_stage0_audit | contradicted_by_stage0_audit | invalid | high | high | PAO-R0 | none | planned_only | premature identity | Use optional opaque aliases and mark split cases as provisional. |
| CLM-045 | Cross-anchor | External act versus evidence interface is consistently modeled. | dependency | PAO-R1 audit commit at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | PAO-R1 audit commit at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted_by_stage0_audit | contradicted_by_stage0_audit | invalid | high | critical | PAO-R1 | full | research_only | scope inflation | Split 16 named calendar events before reuse. |
| CLM-046 | Repository baseline | Current main differs from historical research commit. | repo fact | `git rev-parse origin/main` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | `git rev-parse origin/main` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted | contradicted | valid finding | high | info | repository | full | n/a | none | Both baselines resolve to the same SHA; no stale-now class can arise. |
| CLM-047 | Capability chain | A class/test/doc constitutes complete custody capability. | method claim | AGENTS.md capability doctrine at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | AGENTS.md capability doctrine at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted | contradicted | invalid | high | high | repository | full | partial | P01 | Require producer → artifact → bridge → consumer → verification → surface. |
| CLM-048 | Overall result | OPS-R15 is executable at the supplied report artifact. | benchmark claim | Markdown only; no machine calendar/oracle/runner at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | Markdown only; no machine calendar/oracle/runner at `4813b49f6ce14e8debf3aaea096f0967d38d9768` (identical tree) | contradicted | contradicted | unexecutable | high | critical | benchmark governance | full | documented_only | non-reproducibility | Block whole-capstone acceptance pending independent oracle and executable artifacts. |
