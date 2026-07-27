---
title: OPS-R15 — Audited Stage-0 Kernel and Extension Packs
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

# OPS-R15 Stage-0 Kernel and Extension Packs

## Standing

This is the corrected benchmark architecture produced by the independent audit. It is a research specification, not a production contract, legal certification, runtime state model, or RPO/RTO commitment. The historical and current repository baselines are both `4813b49f6ce14e8debf3aaea096f0967d38d9768`. The original capstone is **not executable as supplied** because its oracle artefacts are prose, its expected results are visible with fixture inputs, and most end-to-end bridges do not exist.

**Audit disposition:** `benchmark_kernel_accepted_extensions_deferred`, subordinate to the overall audit result `blocked_pending_oracle_independence`.

## Bounded benchmark claim

A passing implementation may support only this claim:

> For the committed fixture populations, authority assumptions, repository version, evaluator implementation and conformance profile, the system preserved declared PolicyOS custody invariants under the tested event orders and faults.

A pass does not establish legal compliance, production resilience, institutional competence, universal policy quality, complete dependency discovery, or permission to perform an external administrative act.

## Mandatory Stage-0 kernel

The kernel tests semantic predicates. It does not prescribe internal enum names, one event envelope, two graph tables, twenty atomic gates, one workflow engine or one public status lattice.

| ID | Observable predicate | Independent evidence required | Failure condition |
|---|---|---|---|
| K01 | Durable suspension survives worker loss and restart. | Storage inspection plus a fresh evaluator process; no live-worker memory is accepted as state. | Case is lost, implicitly resumed, or cannot be reconstructed from committed records. |
| K02 | Wake matching is exact and look-alike evidence does not wake. | Sealed positive and near-miss events with independently committed scope. | Wrong event wakes, right event is ignored, or wake itself upgrades authority. |
| K03 | Concurrent duplicate wake delivery yields one resume generation and no duplicate irreversible PolicyOS action. | Dedupe key, persisted receipts and side-effect ledger. | Multiple generations/effects or missing event history. |
| K04 | Resume preserves exact case, tenant and security-cell binding. | Independent identifiers in sealed fixtures and storage/public observations. | Binding is dropped, defaulted or widened. |
| K05 | Each protected action receives fresh, action-specific authority and evidence admission. | Independently specified permitted/prohibited uses and freshness predicate. | Generic resume bypasses reproof or one check grants unrelated action. |
| K06 | Wrong-tenant and unknown-jurisdiction inputs fail closed. | Sealed mutation fixtures; no implementation fallback is oracle truth. | Cross-tenant use or silent jurisdiction default. |
| K07 | Payload identity does not preserve authority after revocation, expiry or narrowed permitted use. | Same payload digest under two committed authority contexts. | Stale authority-bearing reuse. |
| K08 | Duplicate and permitted-order variations preserve semantic outcome; prohibited causal reorderings are rejected or held. | Partial-order fixture, permutation seed and effect ledger. | Order-sensitive result without declared causal reason, or duplicate effect. |
| K09 | Correction, revocation, supersession and withdrawal append new custody facts without erasing prior transaction-time history. | Independent event log and cutoff queries. | In-place historical rewrite or old state shown current. |
| K10 | Historical replay uses only information and versions visible at the declared transaction-time cutoff. | Declarative cutoff oracle, version bundle and equivalence policy. | Future knowledge leaks backward or required historical version is absent. |
| K11 | Current rebuild agrees with an implementation-independent declarative evaluator on the observable semantic projection. | Separately owned reference evaluator; no shared reducers, admission code or graph traversal. | Same-code parity is the only proof, or semantic results disagree. |
| K12 | Affected-set recall is measured against independently declared dependencies, including one hidden missing-edge mutation. | Sealed dependency truth and adjudicated ambiguity set. | Load-bearing affected object is omitted. Precision remains diagnostic. |
| K13 | Every controlled public surface represents current/stale/corrected posture consistently and attributes external acts accurately. | Surface inventory, public predicates and independent crawl. | Any controlled surface shows stale as current or claims PolicyOS executed an external act. |
| K14 | External acts, evidence receipt, admission and PolicyOS reaction remain distinct. | Sealed administrative traps and authority-boundary panel assumptions. | Receipt is reported as execution or PolicyOS invokes an external-act adapter. |
| K15 | Asymmetric CAS/control-state recovery never exposes unverifiable state as current and converges through explicit reconciliation. | Injected snapshot cut, integrity scan and public-state observations. | Silent mixed-point recovery, lost committed custody event, or false-current public state. |
| K16 | ID permutation, delivery permutation and an adjacent unseen case do not change outcomes except where declared semantics require it. | Sealed transforms and equivalence relation. | Case/event-ID branching, fixture memorization or structural overfit. |

### Kernel fixture slice

The following 24 original calendar rows are useful raw material after rewriting them into input-only fixtures and sealed expectations:

`CCB24-006`, `CCB24-007`, `CCB24-008`, `CCB24-009`, `CCB24-011`, `CCB24-016`, `CCB24-017`, `CCB24-018`, `CCB24-019`, `CCB24-020`, `CCB24-023`, `CCB24-027`, `CCB24-029`, `CCB24-040`, `CCB24-042`, `CCB24-045`, `CCB24-067`, `CCB24-076`, `CCB24-077`, `CCB24-078`, `CCB24-091`, `CCB24-098`, `CCB24-099`, `CCB24-104`.


They cover suspension/wake, look-alikes, duplicate delivery, authority loss without payload change, temporal correction, public state, tenant/jurisdiction failures, matter-binding challenge, and recovery. Their original expected-action and oracle columns must not be visible to the implementation.

## Fixture and oracle packaging

Use four physically and access-logically distinct packages:

1. **Public schema and invariant package:** schemas, legal fixture disclaimers, allowed observations and scoring rules.
2. **Implementation-visible input package:** actors, input events and payloads only. It contains no expected wake, impact, action, status, prohibited result or oracle reference.
3. **Sealed semantic package:** expected predicates, admissible alternative outcomes, dependency truth, negative controls and ambiguity labels.
4. **Evaluator package:** independent parsers, reference predicates, surface probes and signed run-receipt builder.

Before a run, an oracle custodian publishes content commitments for packages 2–4. Implementers cannot access packages 3–4. The run environment records file hashes, image/repository revisions, configuration, seed and access log. Failed runs and commitments are immutable. A correction creates a new oracle version and never edits a scored run.

The oracle author, custodian, run operator and implementation team must be distinct roles. Jurisdictional and institutional answers are declared scenario axioms or contested sets, never represented as universal legal truth.

## Conformance profiles

| Profile | Mandatory predicates | Main fixtures | Prerequisites | Primary owners |
|---|---|---|---|---|
| Identity and boundary | K04–K07, K14 | wrong tenant/jurisdiction/subject; external administrative trap | consolidated PAO-R0/R1 assumptions or explicit fixture-local axioms | PDC, runtime quality, security; PAO-R0/R1 research |
| Temporal and replay | K08–K11 | duplicate/out-of-order, late correction, cutoff replay | OPS-R4 definitions and historical version availability | artifact/audit owners, OPS-R4 |
| Dependency and recomputation | K07, K11, K12 | authority-only invalidation, missing edge | independently authored dependency oracle | OPS-R2 and family owners |
| Public record | K09, K13, K14 | stale cache, correction, external-act wording | controlled-surface inventory and PAO-R36 predicates | publication/Atlas/core audit |
| Resilience | K01, K03, K15 | worker loss, duplicate wake, asymmetric snapshots | executable fault harness and declared environment | control plane, storage, OPS-R14/H2 |

Kernel passage requires all applicable profile predicates; it is not a weighted average. `unresolved` and `contested` are valid adjudication outcomes but cannot silently become passes.

## Optional extension packs

| Pack | Scope | Why not kernel | Required owner/prerequisite | Promotion condition |
|---|---|---|---|---|
| Legal change | future-effective law, corrigenda, renumbering, unknown jurisdiction | Jurisdictional semantics and continuous Lex path unresolved | OPS-R10/R11, Lex, jurisdiction pack | Independent legal fixture panel and fail-closed plugin behavior |
| Monitoring and learning | KPI warning, subgroup harm, causal diagnosis, adaptation | Thresholds/causal reaction are task-specific | OPS-R5, INT-R4, DDM/Foundry | Frozen estimands, observation provenance and human safety gate |
| Institutional events | appeal, notice, proof of service, remedy and compensation stages | Depends on real authority and PAO-R1 split | PAO-R1/R4 and institution-specific adapters | External act and evidence rows separated; scenario authority facts explicit |
| Public correction | multi-surface correction feed, subscriber fan-out | Current public owner/status vocabulary incomplete | PAO-R36, Atlas/publication | Controlled-surface registry and machine-verifiable correction protocol |
| Cryptographic preservation | rotation, compromise, archived verification, renewal | Long-horizon trust policy not implemented | INT-R7, OPS-R14, core audit/security | Frozen key epochs, revocation history and archive verifier |
| World release | compatible release vectors and atomic current head | Exact vector/state/owner are OPS-R8 questions | OPS-R8, Fabric, GY-N12 | Ratified compatibility relation and independent negative vectors |
| Matter lineage | split, successor and scoped inheritance | PAO-R0 audit rejects frozen production contract | PAO-R0/PDC consolidation | Ratified identity/lineage semantics and tenant namespace |
| Fleet invalidation | 10,000-case fan-out and scheduling | Performance/environment commitment, not semantic kernel | OPS-R2/R12/H2/deployment | Closed dependency population and production-like load harness |
| Disaster recovery | storage, region and provider recovery | RPO/RTO are deployment-specific | OPS-R14/control/storage owners | Declared topology, clocks, fault injection and measured SLO |
| Multilingual projection | certified source/translation parity | Translation authority and equivalence unresolved | INT-R6/Atlas/Lex | Language authority fixture and independently adjudicated parity |

## Corrected metric policy

- Critical semantic predicates are per-event booleans with closed fixture populations. A failing applicable predicate fails the profile.
- Counts named “attempted” exclude deliberate benchmark probes from the implementation numerator but require those probes to be denied and recorded.
- Recall is critical only against independently authored dependency truth; precision, reuse and minimal recomputation are diagnostic until OPS-R2 defines safe denominators.
- RPO/RTO and latency are reported with the environment and both wall-clock and, where useful, virtual-time results. No default number is Stage-0 authority.
- Human-review results report raw labels, agreement, abstentions and adjudication history; no opaque majority score certifies authority.

## Promotion conditions

The kernel becomes executable only when all of the following hold:

- public/input/sealed/evaluator packages are machine-readable and hash-committed;
- an independent reference evaluator exists and shares no semantic reducers with the system under test;
- the fixture population and all denominators are closed before execution;
- PAO-R0/R1-dependent fixtures use consolidated anchors or explicit local assumptions;
- every measured output is observable through artifacts, receipts, effects or controlled surfaces;
- the sealing/access/rotation process is exercised;
- at least one adjacent unseen case and metamorphic family are held back;
- evaluator defects have a challenge, correction and supersession procedure;
- the exact repository, runner and environment revisions are recorded.

## What must not be frozen

Do not freeze the original universal event envelope, thirteen clocks on every event, exact state names, all twenty gates on every resume, two physical dependency graphs, five disjoint impact sets, a nine-component `WorldRelease`, `policy_matter_ref`, institutional operator mappings, public status labels, numerical reuse/recompute/DR thresholds, or any 1–72 hour RTO. These remain research questions or extension-local assumptions.
