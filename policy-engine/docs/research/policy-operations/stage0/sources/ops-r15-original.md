---
title: OPS-R15 — The PolicyOS Custody-Cycle Capstone Benchmark
status: delivered
kind: deep-research
research_task: OPS-R15
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: main
repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
inspection_date: 2026-07-26
authoritative_for:
  - research-level custody-capstone scenario
  - provisional event and actor vocabulary
  - benchmark metrics and falsifiers
  - expected longitudinal custody trace
  - fixture requirements for Group-B research
may_not_use_for:
  - capability claim
  - authority grant
  - final runtime contract
  - production readiness claim
  - legal compliance certification
  - proof of disaster-recovery capability
  - permission to execute administrative functions
research_only: true
---

# OPS-R15 — The PolicyOS Custody-Cycle Capstone Benchmark

## Executive Finding

**Result: `accepted_narrow_scope`.** A bounded, frozen, adversarial **24-month** custody-cycle capstone is supportable now as a Stage-0 research benchmark. It is supportable because the repository already contains mature fragments for durable job storage, leases and outbox delivery, CAS-backed checkpoints, workflow fingerprints, event-time watermarks, bitemporal reads, decision-validity events, claim-local reissue, legal amendment extraction, public-signature verification, audit packaging, and retention/recovery procedures. It is not yet an implemented custody runtime because those fragments are not orchestrated around a stable policy-matter identity, a boundary-aware wake protocol, a distinct authority-dependency graph, governed world releases, and one longitudinal semantic oracle. fileciteturn17file0 fileciteturn18file0 fileciteturn22file0 fileciteturn29file0 fileciteturn32file0 fileciteturn34file0 fileciteturn37file0

The capstone can prove only a **bounded composition claim**:

> For the frozen scenario, declared event families, actor and authority assumptions, benchmark versions, fault profiles, and accepted ambiguity classes, the tested implementation maintained the current and historical meaning of PolicyOS-owned justifications while correctly consuming external events as evidence and refraining from administrative execution.

It cannot prove universal legal compliance, correctness in every jurisdiction, production RPO/RTO, the truth of real-world causal claims, institutional adoption readiness, or the absence of unknown event classes. A passing run is evidence about one declared operating envelope, not an authority grant.

### Principal custody invariant

For every benchmark event `e`, every current PolicyOS claim `c`, every published record `p`, and every historical cutoff `t`:

1. **Current binding:** `c` is traceable to the correct `policy_matter_ref`, case, tenant, jurisdiction, admitted evidence, governed world-release vector, rule/schema/validator versions, authority boundary, and human authority where required.
2. **No silent history change:** records and claims published before `e` remain byte- and meaning-preserving historical objects; corrections, reissues, supersessions, and withdrawals are append-only deltas.
3. **External-act separation:** administrative, legal, payment, appeal, notice, procurement, and delivery acts retain their external operator; PolicyOS may admit evidence and react to its own claims, but may not represent itself as the actor.
4. **Incremental correctness:** the incremental current state is semantically equivalent to a clean rebuild over the frozen current source corpus, while historical replay reproduces only what was knowable and admissible at the cutoff.
5. **Weakest-boundary preservation:** no event, model, surface, restoration, or human action may strengthen authority beyond the weakest valid support path.

### Main benchmark kill criteria

The run is killed by any nonzero value of:

```text
lost_case_state
stale_public_shown_as_current
unauthorized_authority_upgrades
silent_historical_rewrites
missed_affected_cases
duplicate_irreversible_actions
out_of_boundary_actions_attempted
external_execution_overclaims
jurisdiction_fallback_violations
invalid_artifact_reuse
```

A high reuse or minimal-recompute score cannot offset any of these failures. The repository’s own capability rule similarly rejects contract-only, bridge-less, surface-less, or structurally green but semantically false claims. fileciteturn51file0

### Largest unresolved dependency

The largest unresolved oracle is not computational. It is the **competence and authority oracle** for matter identity, institutional succession, legal effect, appeal finality, remedy status, and jurisdictional applicability. The benchmark therefore uses:

- local `policy_matter_ref` and operational-boundary assumptions marked `candidate_for_consolidation`;
- independently adjudicated authority packets;
- accepted `unresolved` and `contested` outcomes;
- a prohibition against scoring an unresolved case as an automatic pass.

The benchmark specification supplied for this report is the uploaded OPS-R15 research brief. fileciteturn81file0

---

# 1. Task And Project Fit

## 1.1 Source task

| Field | Value |
|---|---|
| Backlog | Custody & Operations — Parallel Deep Research Backlog |
| Wave | Wave 2, Revision 2 |
| Task | OPS-R15 |
| Group | Group B — The Custody Runtime |
| Priority | Stage-0 bootstrap anchor |
| Owner | `team-architecture` |
| Governing decision | `docs/system-design-decisions/policyos-identity-and-custody-boundary.md` |
| Intended later path | `docs/research/policy-operations/ops-r15-custody-cycle-capstone-benchmark.md` |
| Repository modification | None |

The source backlog explicitly makes `PAO-R0`, `PAO-R1`, and `OPS-R15` the three Stage-0 anchors. It requires the capstone to be designed first so it shapes the other custody contracts, and routes the mechanical core into a future H2 Custody Runtime rather than appending it to GY or Atlas. fileciteturn53file0 fileciteturn54file0 fileciteturn55file0

## 1.2 Exact research question

> What frozen 18–24 month simulated policy calendar, event vocabulary, authority-boundary model, expected reaction trace, fault-injection suite, and success criteria are required to prove that PolicyOS can maintain honest custody of a signed policy justification across suspension, world change, legal change, data revision, institutional transition, monitoring signals, incidents, appeals, public correction, partial reissue, supersession, resilience failure, and historical replay—without attempting to execute administrative functions outside its boundary?

## 1.3 Why benchmark-first is mandatory

Designing the capstone after implementation would permit the implementation to define its own test universe. The predictable failures would be:

- short pause/resume masquerading as months-long custody;
- schemas validated without semantic authority;
- “minimal recompute” asserted without a clean-rebuild oracle;
- receipt order substituted for event and effective time;
- state restore substituted for identity and authority reproof;
- administrative operations hidden behind generic workflow verbs;
- runbooks counted as resilience evidence;
- excluded or rewritten failing fixtures;
- a single successful demonstration selected after the result is known.

Pre-registration is therefore part of the benchmark, not documentation garnish. The 2026 UK Magenta Book states that evaluation objectives, design, data collection and analysis should be recorded before outcome data are collected or analysed, and that later amendments should be documented rather than silently substituted. citeturn587027view8

## 1.4 False production claims prevented

The benchmark is designed to reject the claim:

> “PolicyOS maintains lifetime custody of policy justification,” when it can only finish short-lived runs, cannot wake a suspended case correctly, cannot detect authority loss without payload change, misses affected claims, rewrites historical meaning, shows stale records as current, or performs/claims administrative acts outside its boundary.

## 1.5 Four-way boundary verdict

**OPS-R15 itself is OWN, narrowly.** Without a precommitted falsifier of lifetime custody, a PolicyOS claim that its signatures remain honest over time is not supportable. PolicyOS owns the benchmark of its own custody promise; it does not own the external acts represented in the benchmark.

The governing decision states that PolicyOS owns everything it signs for while the signature publicly stands, consumes other institutions’ outputs as typed evidence, and is not an administrator, case-management system, court, notification channel, or payment system. fileciteturn13file0

## 1.6 Relationship to PAO-R0 and PAO-R1

This capstone consumes two provisional Stage-0 anchors:

- `policy_matter_ref` and split/successor semantics from PAO-R0, treated here as an `external_dependency_assumption` rather than a final identity contract;
- function-level OWN/INTEGRATE/OBSERVE/OUT constraints from PAO-R1, treated as `candidate_for_consolidation` rather than legal or institutional delegation.

The benchmark does not redefine either anchor. It tests whether a future runtime can use them without losing state, overclaiming external execution, or rewriting history.

---

# 2. Current Repo Baseline

## 2.1 Inspection record

| Item | Finding |
|---|---|
| Repository | `https://github.com/DenisKopylov/polisyos` |
| Branch | `main` |
| Commit | `4813b49f6ce14e8debf3aaea096f0967d38d9768` |
| Inspection date | 2026-07-26 |
| Branch completeness | The commit-pinned branch appeared internally coherent for the requested source, plan, contract, test, and runbook surfaces. A local uncommitted working tree was not available. |
| Search method | Commit-pinned GitHub repository search and direct file retrieval. A local clone/`rg` pass was attempted but unavailable because the execution environment could not resolve GitHub. Negative absence findings therefore remain connector-search findings, not formal exhaustive proofs. |
| Important path movement | The old Lex batch runtime was retired; the current canonical offline legal pipeline is under `src/polisyos/data_forge/domains/legal/batch`. |
| Honest diagnostics | Both `honest-diagnostics-substrate.md` and its separate decision log exist. The former was not absent or merely renamed. |
| Modification | No repository files were changed. |

The inspected commit ratifies the identity/custody boundary and reshapes Wave 2 around the H2 custodial core. fileciteturn12file0

## 2.2 Paths inspected

The baseline covered:

- `AGENTS.md` and `policy-engine/CONTRIBUTING.md`;
- the identity/custody decision;
- universal vision, target architecture, operating model, honest diagnostics, and causal-OS north star;
- the failure-pattern register;
- Wave-1 backlog and distillation;
- Wave-2 backlog;
- GY and Atlas plans;
- durable control-plane contracts and store;
- Scientist checkpoint/resume and workflow fingerprints;
- Fabric cursors, watermarks and bitemporal HTTP views;
- Decision-Validity;
- Scientist continuous-governance lifecycle and reissue;
- Lex/Data Forge legal batch and jurisdiction plugins;
- DDM and monitoring contracts;
- core audit and signing tests;
- retention/recovery policies and runbooks;
- PolicyPortfolio ADR;
- representative unit, semantic, replay, authorization, lifecycle and public-projection tests.

## 2.3 Verification of the ten provisional baseline claims

| Claim | Verdict | Repository evidence |
|---|---|---|
| Control plane mainly models `pending / running / completed / failed` | **Confirmed.** | The public control contract declares exactly those four states. Durable stores add leases/outbox mechanics but not a long-lived custody lifecycle. fileciteturn17file0 fileciteturn18file0 |
| Scientist resume protects a computational workflow, not a policy custody process | **Confirmed.** | Checkpoint/resume is DAG-, cache-, lock-, schema- and workflow-fingerprint-aware. It is not a matter-aware custody state machine. fileciteturn22file0 fileciteturn24file0 fileciteturn25file0 |
| State restore does not automatically re-prove identity, tenant, authorization, delegation, permissions, freshness and authority | **Confirmed.** | Resume performs integrity, compatibility and reconstruction checks, but the listed authority gates are not one mandatory resume boundary. fileciteturn26file0 |
| Fabric contains temporal and ingestion primitives | **Confirmed.** | Watermarks, signed/validated cursors and bitemporal valid/transaction reads exist. fileciteturn29file0 fileciteturn30file0 fileciteturn32file0 |
| Decision-Validity, W9 and W10 are strong fragments but not one custody cycle | **Confirmed.** | Decision events and append-only claim transitions exist, but no matter-aware longitudinal orchestrator connects the whole cycle. fileciteturn34file0 fileciteturn37file0 fileciteturn38file0 |
| Retention/recovery runbooks are not demonstrated DR capability | **Confirmed.** | The policy defines required drills and explicitly treats failed restore drills as defects; documentation alone is not proof. fileciteturn52file0 |
| Jurisdiction registry is limited and has unsafe fallback | **Confirmed.** | Only `EU` and `UA` are registered; unknown/empty codes resolve to the Ukrainian plugin. fileciteturn44file0 |
| PolicyPortfolio models candidate portfolios rather than deployed stock | **Confirmed.** | ADR-0022 defines combinations of `PolicySpec` for search/optimization with interaction matrices and constraints. fileciteturn58file0 |
| Lex operations lack full living-law continuity | **Narrowly confirmed.** | Staged parsing, temporal resolution and amendment detection exist, but the weekly governed release, complete reference/corrigendum/consolidation resolution and matter-aware fan-out remain a research target. fileciteturn46file0 fileciteturn47file0 |
| No existing end-to-end 18–24 month capstone is present | **High-confidence negative finding.** | Repository search returned only the Wave-2 specification and GY planning references, not an implemented longitudinal capstone. fileciteturn63file0 |

## 2.4 Existing status and event vocabulary

### Control-plane states

```text
pending | running | completed | failed
```

These are useful worker/job states but cannot represent suspension, wake review, revalidation, public correction, supersession or historical-only custody.

### Decision-validity states and triggers

Decision-Validity already includes `active`, `warning`, `stale`, `review_required`, `superseded`, `reissued`, `withdrawn`, `revoked`, and human-review states, with triggers for legal, data, source, model, metric, historical-semantic and post-deployment changes. fileciteturn34file0

### W9 claim lifecycle

The continuous-governance bridge maps admitted monitor events into claim-local `stale`, `blocked`, `invalidated`, `superseded`, `review_required`, `reissued`, and `withdrawn` transitions. It blocks unscoped or unknown claim references and preserves the old ledger. fileciteturn37file0

### Diagnostic events

The runtime diagnostic envelope already carries stable event identity, source/type/time, producer/version, run/job/tenant/cell, state before/after, artifact references, payload and dedupe semantics. fileciteturn33file0

These vocabularies should be **consumed and composed**, not copied into a second capstone-specific status lattice.

## 2.5 Existing reusable primitives

| Primitive | Current owner | Benchmark role | Reality label |
|---|---|---|---|
| Durable job rows, leases, outbox | Runtime control plane | Worker-loss, duplicate delivery and handoff substrate | `implemented` for jobs; `bridge_missing` for custody |
| CAS artifacts and manifests | Core artifacts | Immutable state/evidence and clean rebuild inputs | `implemented` |
| Checkpoint/resume, workflow fingerprint | Scientist | Computational resume and compatibility fixture | `implemented_but_not_orchestrated` |
| Watermarks and cursors | Fabric/core contracts | Event-time and late-event fixture substrate | `implemented_but_not_orchestrated` |
| Bitemporal views | Runtime/Fabric | Valid-time vs transaction-time replay oracle | `implemented_but_not_orchestrated` |
| Decision-Validity | Core/runtime/scientist | Dependency event and current-status fragments | `implemented_but_not_orchestrated` |
| Claim lifecycle and partial reissue | Scientist continuous governance | Append-only scoped correction/reissue | `implemented_but_not_orchestrated` |
| Legal batch and amendment detector | Data Forge/Lex | Legal-event source fixtures | `implemented_but_not_orchestrated` |
| Jurisdiction plugins | Data Forge/Lex | Unknown-jurisdiction negative fixture | `implemented`, unsafe fallback |
| KPI/monitoring DTOs | Core/DDM | Decision-linked monitoring seed | `contract_only` to `partial_internal_owner` for OPS-R5 semantics |
| AuthorityBoundary | PDC | One authority grammar for all events | `implemented` |
| Core audit archive | Core audit | Offline verification and recovery evidence | `implemented` |
| Artifact signing/revocation | Core artifacts | Key rotation, compromise and revoked-key fixtures | `implemented` for narrow cryptographic scope |
| Retention/recovery policy | Platform owners | Fault expectations and drill requirements | `verification_missing` for full custody DR |
| Atlas projections | Atlas/runtime | Cross-surface public-state oracle | `surface_missing` for H2 custody |
| GY-N12 epochs/OpenWorldRisk | GY plan | Future semantic-epoch input | `producer_missing` at inspected commit |
| PolicyMatter identity | PDC lineage candidate | Scenario anchor | `contract_only` research assumption |
| Boundary register | Team architecture/PDC candidate | Administrative action constraints | `contract_only` research assumption |
| H2 custody orchestrator | Future H2 owner | Long-lived process under test | `producer_missing` / `bridge_missing` |

The repository’s narrow-waist doctrine requires all engine and external outputs to enter through runtime quality and typed PDC contracts, with the authority backbone leading the generative layer. fileciteturn72file0

## 2.6 Existing tests and failure-injection seeds

Reusable seeds include:

- lease/outbox retry and idempotency tests;
- CAS integrity and missing-artifact errors;
- checkpoint workflow-fingerprint mismatch and cache reconstruction;
- cursor signature, query-binding and expiry checks;
- bitemporal `valid_at`/`tx_at` tests;
- Decision-Validity law/source/data/metric events;
- W9 unknown-claim and missing-scope blockers;
- partial reissue preserving unaffected claims;
- legal amendment detection and temporal parsing;
- revoked, untrusted, tampered and identity-mismatched signatures; fileciteturn61file0
- audit archive integrity and offline verification;
- documented artifact corruption, replay/restore and key-rotation runbooks. fileciteturn70file0 fileciteturn70file3

What is missing is a single frozen fixture that composes those behaviors over two years and judges the resulting **authority and public-history trace**.

## 2.7 Research blockers versus engineering blockers

### Research blockers

1. Final PAO-R0 matter identity and split/successor semantics are not yet canonical.
2. Final PAO-R1 boundary decisions and real institutional operators remain provisional.
3. Jurisdiction-specific competence, legal effect, appeal finality and proof-of-service rules cannot be universally hardcoded.
4. Some expected outcomes require human adjudication and admit genuine disagreement.
5. RPO/RTO values are workload- and deployment-dependent; this benchmark can freeze candidate targets, not production promises.
6. No synthetic corpus can prove external validity across all policy domains and institutions.

### Engineering blockers

1. No durable `suspended` case process separate from a live job.
2. No mandatory matter/tenant/authority reproof at wake.
3. No unified artifact-versus-authority dependency impact engine.
4. No governed `WorldRelease` producer/head.
5. No full living-law release and matter-aware fan-out.
6. No boundary-aware external institutional evidence port across all event families.
7. No matter-aware Atlas custody projection.
8. No fleet-scale backpressure/public-freeze scheduler.
9. No complete public verification lifecycle through rotation, compromise and archival renewal.
10. No capstone runner or sealed fixture governance.

## 2.8 Smallest reuse-first benchmark path

The benchmark should be built conceptually from existing owners in this order:

```text
CAS + control-plane rows + checkpoints
→ Fabric event-time/bitemporal fixtures
→ Decision-Validity and W9 lifecycle reactions
→ Lex legal-event fixtures
→ DDM/KPI fixtures
→ core audit/signature/recovery oracles
→ PDC AuthorityBoundary + PAO-R0/PAO-R1 assumptions
→ future H2 orchestration under test
→ Atlas projection oracle
```

No new legal engine, status lattice, audit subsystem, event store, payment function, notification system, or administrative case-management system is justified.

---
# 3. External Research Baseline

The benchmark composes several mature pattern families. None is sufficient alone because none carries PolicyOS’s authority semantics.

## 3.1 Durable workflow history

Temporal’s official documentation describes workflows that resume after crashes, network failure or infrastructure loss even after long delays. This establishes the engineering plausibility of separating a durable logical process from a transient worker. It does **not** establish that the resumed process still has the right identity, tenant, delegation, permission, current evidence or public authority. citeturn152469view0

**PolicyOS authority delta:** every replay/resume must stop at an authority re-admission boundary. Deterministic workflow history is necessary but not sufficient.

## 3.2 Event time, watermarks and late data

Apache Beam explicitly distinguishes element/event timestamps, watermarks, late data, event-time triggers, processing-time triggers and allowed lateness. This is the correct technical pattern for out-of-order and late institutional evidence. It does not decide whether a late legal or administrative event should annotate, reopen, recompute, revalidate or remain historical only. citeturn152469view1

**PolicyOS authority delta:** late-event handling is keyed to legal/evidentiary materiality and the claim dependency graph, not only a windowing policy.

## 3.3 Incremental computation and clean-build equivalence

“Build Systems à la Carte” provides a formal vocabulary for dependency discovery, invalidation, caching and build-system behavior. It supports using a clean rebuild as an independent oracle for incremental recomputation. It does not model authority loss when bytes remain unchanged. citeturn152469view2

**PolicyOS authority delta:** maintain two graphs—artifact derivation and authority permission—and compare both current semantic output and current permitted use.

## 3.4 Contingency planning and exercises

NIST SP 800-34 treats contingency planning as a lifecycle that includes business-impact analysis, preventive controls, recovery strategies, plans, testing/training/exercises and maintenance. This supports the capstone’s rule that a runbook is not evidence of recovery. citeturn587027view0

Chaos Engineering similarly starts from a measurable steady-state hypothesis, injects realistic disruptive events and tries to falsify the hypothesis while controlling blast radius. citeturn890889search5

**PolicyOS authority delta:** the steady state is not merely service availability. It is custody correctness: no lost state, stale public record, authority upgrade, boundary violation or replay drift.

## 3.5 Preservation metadata and historical representations

PREMIS provides a preservation-oriented object/event/agent/rights model. Memento provides datetime negotiation and TimeMaps for retrieving prior representations of a resource. Together they support the benchmark’s requirement to preserve historical public states rather than mutate current URLs in place. citeturn152469view4 citeturn587027view4

**PolicyOS authority delta:** archived bytes must remain linked to the authority boundary, evidence state and public meaning that existed at the historical cutoff.

## 3.6 Long-term cryptographic evidence and transparency

RFC 4998 defines evidence records for long-term proof of data existence and anticipates renewal as algorithms weaken or keys are compromised. RFC 9162 shows how append-only Merkle logs and consistency proofs can expose equivocation. These patterns support archival verification, key rotation, compromise recovery and append-only correction history. citeturn587027view5 citeturn587027view6

**PolicyOS authority delta:** cryptographic validity does not imply semantic currency. A valid signature may point to a stale, corrected or superseded justification.

## 3.7 Legal-document identity and versions

ELI and Akoma Ntoso provide legal-document identifiers, metadata and document/version structures. They help represent acts, amendments, expressions and manifestations but do not determine whether a legal change affects a specific PolicyMatter or claim. citeturn152469view8 citeturn152469view9

**PolicyOS authority delta:** resolve competence, territorial scope, effective time, claim applicability and impact fan-out before legal evidence changes authority.

## 3.8 Public-sector evaluation and anti-overfitting

The Magenta Book’s pre-registration guidance is directly applicable: freeze objectives, questions, design, collection and analysis before outcome data are seen; record amendments rather than overwrite the plan. NIST’s ARIA program and statistical-evaluation work emphasize context-sensitive, repeatable, robust and uncertainty-aware assessment rather than a single headline score. NIST’s metamorphic-testing work supports testing properties when no simple oracle exists. citeturn587027view8 citeturn152469view11 citeturn152469view12 citeturn152469view13

**PolicyOS authority delta:** the benchmark must include semantic, authority, public-record and recovery oracles; a successful demo or aggregate score cannot override a critical falsifier.

## 3.9 Public-sector governance and accountable roles

NIST AI RMF requires continuing governance, ongoing monitoring, clear roles, incident processes and contingency handling for third-party dependencies. The UK Algorithmic Transparency Recording Standard expects an operationally accountable senior responsible owner rather than an unnamed technical system. citeturn587027view11 citeturn587027view12

The EU AI Act likewise distinguishes providers, deployers, oversight persons and competent authorities; the benchmark uses this separation only as a comparative governance pattern, not as a jurisdiction-neutral legal rule. citeturn152469view15

**PolicyOS authority delta:** every event names the real operator and evidence producer; PolicyOS’s role is restricted to admission, claim reaction and its own public records.

## 3.10 Limits of the external patterns

| Pattern family | Establishes | Does not establish |
|---|---|---|
| Durable workflows | Crash/retry/replay durability | Current identity, authority or evidence validity |
| Streaming/event-time | Late/out-of-order processing semantics | Legal or epistemic materiality |
| Incremental build systems | Dependency invalidation and clean-build comparison | Authority dependencies or public correction |
| Chaos/contingency testing | Controlled failure experiments | Policy-claim or institutional authority oracle |
| PREMIS/Memento | Preservation events and historical representations | Current claim admissibility |
| ERS/CT | Long-term integrity and append-only transparency | Semantic currency or legal correctness |
| ELI/Akoma Ntoso | Legal-document identity/version structures | PolicyMatter identity and claim applicability |
| Evaluation guidance | Precommitment, uncertainty and robustness | Production readiness or institutional mandate |
| AI governance frameworks | Roles, monitoring, accountability, incident duties | PolicyOS-specific contract placement |

The capstone’s original contribution is the **authority-aware composition** of these patterns.

---

# 4. Result

## 4.1 Benchmark posture and scenario assumptions

### 4.1.1 Frozen benchmark identity

```yaml
scenario_id: policyos.custody_capstone.msme_energy_resilience.v1
scenario_version: 1.0.0
calendar_start: 2027-01-05
calendar_end: 2028-12-20
repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
policy_matter_ref: pm:ccb24:msme-energy-resilience
policy_matter_status: external_dependency_assumption
case_ref: pdc-ccb24-001
tenant_ref: tenant-ccb24-alpha
primary_jurisdiction_ref: UA-MUNI-ALPHA
parent_jurisdiction_ref: UA
comparison_jurisdiction_ref: EU
unknown_jurisdiction_fixture: ZZ-01
boundary_register_status: candidate_for_consolidation
```

### 4.1.2 Synthetic policy matter

The principal matter is a synthetic **Municipal MSME Energy-Resilience Pilot**. It targets micro and small enterprises supplying essential local goods and services during energy disruption. The design combines:

- a limited credit guarantee;
- co-financed energy audits and efficiency upgrades;
- a voucher for backup-power leasing;
- implementation-capacity and vendor-availability constraints;
- subgroup guardrails for displaced, women-owned and very small firms;
- a policy-to-individual-decision firewall: PolicyOS may define policy-level eligibility principles but may not determine any applicant’s entitlement.

The matter is synthetic, but its structure is realistic enough to generate legal, fiscal, data, capacity, delivery, monitoring, appeal and public-record dependencies.

### 4.1.3 Initial design record

| Dimension | Frozen scenario content |
|---|---|
| Public problem | Energy disruption threatens continuity of essential local MSMEs and employment. |
| Target population | Registered micro/small firms in critical local supply chains, with subgroup reporting but no PolicyOS individual scoring. |
| Options | Voucher-only; guarantee-plus-voucher; staged pilot with reversible expansion. |
| Causal chain | Financing and audit access → retrofit/backup capacity → uptime → output/employment, with debt, safety and distributional risks. |
| Evidence | Administrative business panel, outage data, credit-market evidence, legal sources, supplier capacity evidence, literature and expert elicitation. |
| Constructs | Energy vulnerability, liquidity constraint, business continuity, implementation capacity, distributional burden. |
| KPI contracts | Result, implementation, guardrail, leading, diagnostic, context and measurement-health families. |
| Obligations | Legal authority, fiscal exposure, data rights, construct validity, causal identification, subgroup safety, supplier capacity, contestability, public verification. |
| Known unknowns | Municipal competence, contingent-liability authority, delegation, supplier capacity, subgroup measurement, transport from prior studies. |
| Decisive gap | A competent, time-bounded municipal delegation authorizing the pilot’s guarantee exposure and relevant data use. This is a mandate/delegation gap, not a request for more rows. |

The initial case must terminate at `acquisition_required`. Adding more relevant data cannot close the mandate gap.

### 4.1.4 Initial expected result

On 2027-01-18:

- the case is durably suspended;
- live worker leases and locks are released;
- the exact open obligation and acceptable evidence class remain visible;
- spent/remaining budgets and review deadlines are preserved;
- the public posture is `limited — acquisition required`, not `failed`, `completed`, or “almost approved”;
- similar political or administrative material cannot satisfy the obligation.

### 4.1.5 Quiet periods

The calendar deliberately contains low-activity intervals—especially late January to early March 2027 and selected later review windows. During quiet periods, only scheduled expiry, census and review checks run. This tests that custody is not simulated as a continuously active worker.

## 4.2 Actor registry

| Actor | Institution/system | Lifecycle | Boundary | Allowed benchmark actions | Prohibited PolicyOS claim |
|---|---|---|---|---|---|
| `actor.policyos.pdc` | PDC authority waist | Epistemic | OWN | Hold typed claims, boundaries and case/matter refs | Raw engine output is authority |
| `actor.policyos.runtime_quality` | Runtime quality admission ring | Epistemic | OWN | Authenticate, resolve, bind, downgrade, quarantine and admit | It performed the external event |
| `actor.policyos.h2_candidate` | Future H2 custody orchestrator | Epistemic/custody | OWN, candidate | Suspend, wake, gate, impact, revalidate, schedule recompute | It administers citizens, notices, appeals or payments |
| `actor.policyos.fabric` | Fabric/data plane | Epistemic/data | OWN producer for PolicyOS data artifacts; INTEGRATE external data | Watermarks, snapshots, quarantine, release candidates | External data collection was performed by PolicyOS when it was not |
| `actor.policyos.lex` | Lex/Data Forge legal sensing | Epistemic/legal evidence | OWN sensing; INTEGRATE sovereign acts | Authenticate and structure legal evidence, build legal release | PolicyOS enacted/adjudicated the law |
| `actor.policyos.ddm` | DDM/monitoring | Epistemic | OWN diagnosis contract; INTEGRATE observations | Detect/route signals and produce typed monitoring evidence | Threshold crossing changed policy |
| `actor.policyos.audit` | Core audit/signing | Public record/custody | OWN | Package, sign, verify and preserve PolicyOS evidence | Cryptographic validity proves current semantic validity |
| `actor.policyos.atlas` | Atlas projections | Public records | OWN projection discipline | Render current, stale, corrected and historical state | Surface state mints authority |
| `actor.human.principal` | Mandated human decision maker | Institutional/epistemic | INTEGRATE identity/mandate; OWN PolicyOS decision record | Approve/limit/reject/revise within mandate | A click without role, evidence or TTL is valid approval |
| `actor.external.council` | Municipal council | Institutional/legal | INTEGRATE | Issue mandate/delegation and legal acts | PolicyOS issued the mandate |
| `actor.external.program_agency` | Municipal programme agency | Implementation/administrative | INTEGRATE | Configure and operate pilot, issue implementation evidence | PolicyOS operated the programme |
| `actor.external.gazette` | Official legal publisher | Legal/public record | INTEGRATE | Publish acts, amendments, corrigenda, repeal | Retrieval alone proves applicability |
| `actor.external.data_provider` | Administrative/statistical provider | Implementation/evidence | INTEGRATE | Publish measurements and revisions | No report means no event |
| `actor.external.service_operator` | Delivery/provider network | Implementation | INTEGRATE | Deliver audits/vouchers and report performance | PolicyOS delivered service |
| `actor.external.notice_system` | Administrative notice channel | Administrative | INTEGRATE | Send notice and emit proof-of-service | “Sent” alone equals legally effective service |
| `actor.external.appeal_body` | Competent appeal body | Administrative/legal | INTEGRATE | Adjudicate and publish outcome | PolicyOS adjudicated the appeal |
| `actor.external.payment_authority` | Treasury/payment operator | Administrative/finance | INTEGRATE | Authorize, initiate, settle and reconcile compensation | PolicyOS paid compensation |
| `actor.external.procurement_authority` | Procurement/contracting body | Implementation/finance | INTEGRATE | Select vendor and execute contract | PolicyOS selected or contracted vendor |
| `actor.external.records_authority` | Records/publication authority | Public records | INTEGRATE | Issue hold/disclosure/retention decisions | PolicyOS owns institution-wide records management |
| `actor.external.identity_provider` | Institutional identity source | Institutional/security | INTEGRATE | Assert identity and representation at assurance level | Identity assertion grants unrelated authority |
| `actor.external.cloud_provider` | Hosting/infrastructure provider | Infrastructure | INTEGRATE | Supply infrastructure and incident/recovery evidence | Provider status equals PolicyOS custody success |
| `actor.malicious.producer` | Untrusted/compromised source | Any | OUT until verified | Submit candidate evidence only | Submitted evidence is admitted authority |

## 4.3 Event vocabulary

The following are **research-level discriminators**, not production enums.

### 4.3.1 External world events

```text
DataRevisionPublished
SourceRecordCorrected
SourceAuthorityRevoked
MetricSchemaChanged
MetricDefinitionChanged
ConstructDefinitionChanged
CalibrationExpired
LegalNormPublished
LegalNormEffective
LegalNormCorrected
LegalNormAmended
LegalNormRepealed
LegalRenumbered
InstitutionReorganized
ResponsibleBodyChanged
DelegationExpired
ActingAppointmentIssued
ReviewerCertificationExpired
WorkflowVersionChanged
ValidatorVersionChanged
ValidatorDefectDiscovered
JurisdictionPackPublished
SourceUnavailable
DataSharingAgreementExpiring
ModelLicenseExpiring
SigningKeyRotated
SigningKeyCompromised
KPIEarlyWarningIssued
SubgroupHarmReported
ImplementationFailureReported
MeasurementFailureReported
BehavioralResponseDetected
BaselinePolicyChanged
IncidentReported
AppealOutcomeIssued
CorrectionRequestIssued
PolicyMatterSplitAsserted
```

### 4.3.2 Evidence receipt and admission events

```text
ExternalEvidenceReceived
ExternalEvidenceAuthenticated
ExternalEvidenceQuarantined
ExternalEvidenceRejected
ExternalEvidenceAdmitted
ExternalEvidenceCorrected
ExternalEvidenceRevoked
ExternalEvidenceDisputed
ExternalEvidenceMarkedStale
```

### 4.3.3 PolicyOS custody events

```text
CaseSuspended
WakeConditionSatisfied
CaseWakeRequested
ResumeGateFailed
CaseResumed
ArtifactMarkedStale
AuthorityBoundaryDowngraded
DependencyImpactComputed
RevalidationRequired
RecomputeStarted
RecomputeCompleted
HumanReviewRequired
PolicyClaimConfirmed
PolicyClaimRevalidated
PolicyClaimLimited
PolicyClaimBlocked
PolicyClaimReissued
PolicyClaimSuperseded
PolicyClaimWithdrawn
PublicRecordCorrectionPending
PublicRecordCorrected
HistoricalReplayCompleted
```

### 4.3.4 External administrative events

```text
NoticeServed
AppealAdjudicated
CompensationRecommended
CompensationAuthorized
CompensationPaymentInitiated
CompensationPaid
CompensationReconciled
CaseClosedByAgency
VendorSelected
ServiceDelivered
```

These may be represented only with an external producer and INTEGRATE boundary. The benchmark fails if PolicyOS emits them as its own institutional acts.

### 4.3.5 Infrastructure and resilience events

```text
WorkerTerminated
DuplicateWorkerDetected
ControlDatabaseUnavailable
CASObjectMissing
CASRestored
ControlDatabaseRestored
DuplicateControlEventDetected
WorldHeadAdvanced
FanoutIncomplete
BackupRestored
ReplayVerificationFailed
RecoveryEventRejected
CleanRebuildUnavailable
MassInvalidationTriggered
```

## 4.4 Common event envelope

Every event fixture carries:

```yaml
fixture_event_id: stable benchmark identifier
event_type: discriminated event type
producer_ref: actual evidence producer
operator_ref: real-world actor that owns the underlying act
boundary_class: own | integrate | observe | out_of_scope
policy_matter_ref: stable/provisional matter reference
case_refs: scoped cases
tenant_ref: explicit tenant
jurisdiction_refs: explicit jurisdictions
event_time: when the underlying event occurred
legal_effective_time: when legal effect begins, if applicable
valid_time: modeled world interval
publication_time: when the source published it
observation_time: when PolicyOS or its source observed it
receipt_time: when the message/artifact arrived
admission_time: when it passed PolicyOS gates
processing_time: when the runtime processed it
transaction_time: when PolicyOS persisted the representation
correction_time: optional
revocation_time: optional
review_due_time: optional
expiry_time: optional
dedupe_key: semantic idempotency identity
correction_of: optional prior event
revokes: optional prior evidence/authority
schema_version: source and envelope schemas
rule_version: admission and reaction rules
payload_ref: content-addressed fixture
provenance_ref: producer/activity/receipt chain
authority_boundary: authoritative_for / may_not_use_for
permitted_downstream_actions: typed actions
prohibited_uses: typed denied uses
```

Processing time is excluded from content identity unless a declared claim is specifically about processing latency. Receipt order never establishes event-time truth.

## 4.5 Multi-clock temporal model

| Clock | Meaning | Benchmark use |
|---|---|---|
| `event_time` | Underlying occurrence | Orders factual sequence where known |
| `legal_effective_time` | Start/end of legal effect | Determines legal applicability, not publication date |
| `valid_time` | Interval for which an assertion is modeled true | Current/historical world query |
| `publication_time` | Source made record public | Source chronology and notice |
| `observation_time` | PolicyOS/source first observed event | Detection latency |
| `receipt_time` | Transport arrival | Duplicate/out-of-order tests |
| `admission_time` | Passed identity, provenance, competence, scope and quality gates | Earliest authority-bearing use |
| `processing_time` | Runtime handled message | Operational performance only |
| `transaction_time` | Persisted in PolicyOS history | As-known/as-recorded replay |
| `correction_time` | Correcting assertion admitted | Current corrected view |
| `revocation_time` | Authority/evidence revoked | Authority-loss trigger |
| `review_due_time` | Scheduled human/system review | Wake condition |
| `expiry_time` | Right, license, delegation, calibration or certificate expiry | Pre-expiry watch and post-expiry block |

### Late-event outcomes

```text
ignore_for_closed_window
annotate_only
recompute_if_material
mandatory_revalidation
open_new_epoch
human_adjudication
historical_only
```

These are reaction categories, not authority statuses. The selected outcome is derived from event class, materiality, claim dependency, public state, legal effect and applicable rule version.

### Temporal falsifiers

The benchmark fails if:

- processing time enters a semantic content hash without an explicit claim;
- a legal publication date is treated as its effective date;
- a retroactive revision mutates the historical state instead of adding a current interpretation;
- receipt order becomes event order;
- a closed window is reopened without a typed policy;
- an out-of-order correction is applied to an unidentified original event;
- late evidence changes a public record without correction/supersession history.


## 4.5A Five unsynchronized lifecycles

| Lifecycle | Principal state in the scenario | External inputs | PolicyOS-owned consequence | Example divergence |
|---|---|---|---|---|
| Epistemic | supported / limited / stale / contested / revalidated | Data, law, evaluation, incident and appeal evidence | Admission, impact, revalidation and claim/public state | Claim becomes stale before the programme agency changes operations |
| Administrative | notice, appeal, remedy and individual case states | Proof of service, appeal outcome, compensation stages | Evidence ingestion and correction of PolicyOS records | Notice is sent but epistemic state does not change until valid proof matters to a claim |
| Implementation | budget, configuration, supplier capacity, delivery and rollback | Programme/service/operator evidence | Feasibility diagnosis, limitation and learning inputs | Delivery failure occurs while legal authority remains unchanged |
| Institutional | mandate, delegation, responsible body, acting appointment, certification | Competent authority records | Re-proof of who may decide or sign | Institution changes while policy-matter identity continues |
| Public records | draft, current, limited, corrected, superseded, withdrawn, archived | PolicyOS publication events and external records decisions | Own correction, verification and historical linkage | Old record remains historically valid but is not current |

No single `policy_status` is allowed to collapse these lifecycles. A benchmark step may advance one, leave another unchanged and downgrade a third.

## 4.6 Research-level state machines

The benchmark keeps lifecycle state machines separate. These candidates must feed the one PolicyOS authority grammar; they are not new canonical enums.

### 4.6.1 Case custody state machine

```text
designing
  ├─ grounded terminal ────────────────→ limited / blocked / publishable
  └─ decisive open obligation ────────→ acquisition_required
acquisition_required
  └─ durable custody record committed → suspended
suspended
  ├─ no typed wake condition ─────────→ suspended
  └─ typed wake condition ────────────→ wake_pending
wake_pending
  ├─ resume gate fails ───────────────→ suspended | blocked | human_review
  └─ all mandatory gates pass ────────→ resumed
resumed → revalidating
revalidating
  ├─ material conflict/authority choice→ human_review
  ├─ support remains valid ───────────→ confirmed | limited
  ├─ scoped change ───────────────────→ reissued
  ├─ replacement current record ──────→ superseded
  └─ continued reliance unsafe ───────→ withdrawn
confirmed / limited / blocked / reissued / superseded / withdrawn
  └─ later admitted perturbation ─────→ wake_pending | revalidating
historical_only
  └─ never reactivated as current without a new authority-bearing transition
```

| State | Owner | Clock/expiry | Public meaning |
|---|---|---|---|
| `designing` | GY/PDC workflow | Execution and budget clocks | No public authority |
| `acquisition_required` | PDC/RQ | Obligation TTL/review due | Honest refusal with path |
| `suspended` | Future H2 | Wake deadlines, expiry watchers | Waiting; worker released |
| `wake_pending` | Future H2 | Dedupe and wake lease | A possible trigger arrived; not resumed |
| `resume_review` | H2 + PDC/RQ | Gate-specific TTL | Identity/authority/compatibility reproof |
| `resumed` | H2/worker | Worker lease | Execution permitted within refreshed envelope |
| `revalidating` | Decision-Validity/PDC | Event materiality deadline | Prior public claim may be stale |
| `human_review` | Mandated human forum | Decision due/availability | No automated authority upgrade |
| `limited` | PDC/publication | Recheck/expiry | Current with visible limitations |
| `blocked` | PDC/publication | Until evidence/authority changes | Not current for blocked use |
| `reissued` | PDC/publication | New record lifecycle | New current scoped record; old retained |
| `superseded` | PDC/publication | Historical retention | Previously valid; replaced |
| `withdrawn` | PDC/publication | Historical retention | Continued reliance prohibited |
| `historical_only` | Core audit/archive | Preservation profile | Verifiable history, never current authority |

A worker crash may change execution state without changing custody state. A case can remain `suspended` for months with zero live worker.

### 4.6.2 Evidence state machine

```text
received
  ├─ identity/integrity failure ─→ rejected
  ├─ incomplete/unsafe ─────────→ quarantined
  └─ authenticated ─────────────→ authenticated
authenticated
  ├─ competence/scope conflict ─→ disputed | rejected
  └─ verification succeeds ─────→ verified
verified
  └─ purpose-specific admission → admitted
admitted
  ├─ freshness/expiry ──────────→ stale
  ├─ counterevidence ───────────→ disputed
  ├─ correction ────────────────→ corrected
  ├─ revocation ────────────────→ revoked
  └─ replacement ───────────────→ superseded
corrected / revoked / superseded / rejected
  └─ retained as historical_only
```

`authenticated` is not `admitted`; `verified` is not globally authoritative; `admitted` is always purpose-scoped.

### 4.6.3 Public-record state machine

```text
draft → published_current
published_current
  ├─ support weakens ─────────────→ limited
  ├─ correction identified ───────→ correction_pending
  ├─ successor record published ──→ superseded
  ├─ continued reliance unsafe ───→ withdrawn
  └─ verification material problem→ verification_degraded
correction_pending → corrected
corrected / superseded / withdrawn / verification_degraded → archived historical view
```

A record may be cryptographically valid and simultaneously `limited`, `superseded`, `withdrawn`, or `verification_degraded`.

### 4.6.4 World-release state machine

```text
candidate → shadow → benchmark_passed → governed → superseded → archived
```

A component version is never “governed” merely because it is individually newest. Governed status belongs to the verified vector.

### 4.6.5 Appeal and incident evidence flow

```text
external institution performs process
→ external outcome/report issued
→ evidence received/authenticated/verified/admitted
→ PolicyOS computes affected claims and public records
→ PolicyOS annotates, limits, revalidates, corrects, reissues, supersedes or withdraws
```

The external process and the PolicyOS reaction remain different lifecycles and different actors.

## 4.7 Typed wake conditions

| Wake condition | Trigger source | Minimum binding | Non-sufficient look-alike |
|---|---|---|---|
| `data_watermark_reached` | Fabric | Required dataset/partition, event-time watermark, source/version | More rows from another source |
| `required_artifact_admitted` | RQ/PDC | Exact obligation ID, accepted artifact class, content binding | Similar report or keyword match |
| `legal_release_governed` | Lex | Governed legal-release vector, jurisdiction, effective scope | Unofficial or shadow legal hit |
| `human_decision_received` | Human-decision producer | Correct person/forum, role, mandate, TTL, active choice | Email approval or wrong-role click |
| `review_window_closed` | Custody scheduler | Declared window and late-event policy | Processing delay alone |
| `scheduled_review_due` | Custody scheduler | Case/matter review obligation | Generic cron without case binding |
| `incident_received` | DDM/external adapter | Scoped incident evidence and status | Media mention only |
| `appeal_outcome_admitted` | Contestability adapter | Competent body, claim/case scope, finality | Appeal filed or narrative summary |
| `rule_changed` | Rule registry | Rule version, semantic diff, affected obligations | File timestamp change |
| `validator_changed` | Validator governance | Validator version and compatibility/defect record | New package version alone |
| `delegation_expiring` | Authority watcher | Delegation ref, expiry, affected actions | Generic personnel change |
| `license_expiring` | Dependency watcher | License/right ref, scope, affected uses | Vendor newsletter |
| `public_record_correction_required` | Publication owner | Specific record/claim and correction basis | Unverified complaint |
| `source_recovered` | Source platform | Source identity, health, gap census | One successful HTTP response |
| `jurisdiction_pack_governed` | Lex/jurisdiction owner | Pack identity, benchmark, authority and no-fallback proof | Adding a code string |

A typed wake condition creates permission to **evaluate resume**, never permission to resume automatically.

## 4.8 Resume gates and receipt

The benchmark requires the following gates on every resume generation:

| # | Gate | Required evidence | Failure reaction |
|---:|---|---|---|
| 1 | State integrity | CAS hashes, checkpoint/index consistency, suspension record | Block; recovery workflow |
| 2 | Policy-matter identity | Matter/case association and lineage state | Block or human identity review |
| 3 | Case identity | Exact case and open obligation binding | Reject wrong case |
| 4 | Tenant identity | Tenant/cell closure across state, event and evidence | Security block |
| 5 | Principal authentication | Current authenticated principal/service | Deny |
| 6 | Action authorization | Exact resume/revalidate permission | Deny and audit |
| 7 | Delegation/mandate | Current subject-matter/time/jurisdiction authority | Suspend or human review |
| 8 | Permissions/step-up | Fresh purpose-bound high-stakes approval where required | Deny; no cached approval |
| 9 | Workflow compatibility | Workflow fingerprint or approved migration mode | Original environment, migrate/compare, or refuse |
| 10 | Schema compatibility | State/evidence schema compatibility | Migration dossier or block |
| 11 | Rule compatibility | Closure-time and current rule versions, semantic diff | Replay old/new compare or revalidation |
| 12 | Validator compatibility | Validator version, governance and known-defect state | Block until independently valid |
| 13 | World-release compatibility | Governed compatible release vector | Reject latest-of-each mix |
| 14 | Obligation status | Exact open/closed/unknown obligations and coverage envelope | Keep acquisition/open-world block |
| 15 | Dependency impact | Artifact and authority impact sets | No resume until impact closure |
| 16 | Evidence freshness | TTL, expiry, revocation and current source status | Mark stale; reacquire/revalidate |
| 17 | Budget/cost envelope | Spent/remaining compute, acquisition and human attention | Limit, replan or human decision |
| 18 | Certified operating envelope | Domain, stakes, actors, methods and modes remain in-envelope | Limit/abstain/human review |
| 19 | Public-record implications | Current public records, correction/freeze requirements | Public freeze or correction before current display |
| 20 | Human-review requirements | Required independent/competent human decision exists | Remain suspended or blocked |

### Candidate `CaseResumeReceipt`

```yaml
resume_receipt_id: stable id
policy_matter_ref: reference
case_ref: reference
wake_event_refs: [...]
wake_dedupe_key: string
pre_suspension_state_ref: CAS ref
suspension_record_ref: CAS ref
resume_generation: integer
gate_results:
  - gate_id
  - status: pass | fail | review_required
  - evidence_refs
  - rule_version
  - reason
reused_artifact_refs: [...]
stale_artifact_refs: [...]
authority_lost_refs: [...]
invalidated_refs: [...]
payload_recompute_set: [...]
authority_revalidation_set: [...]
public_notice_set: [...]
human_review_set: [...]
historical_only_set: [...]
remaining_obligations: [...]
boundary_downgrades: [...]
pre_post_semantic_diff_ref: reference
public_posture_before: string
public_posture_after: string
authority_boundary:
  authoritative_for: [resume_gate_result]
  may_not_use_for: [external_administrative_execution, final_policy_approval]
```

The receipt is authoritative only for what PolicyOS checked and did, not for the truth or fairness of an external institutional process.

## 4.9 Artifact and authority dependency graphs

### Artifact dependency graph

Nodes and edges represent:

- source snapshots and legal versions;
- constructs and schemas;
- calibration/model/rule/validator versions;
- transformations and derived data;
- claims, decisions, public projections and signatures;
- `derived_from`, `consumed_by`, `produced_by` and technical invalidation.

### Authority dependency graph

Nodes and edges represent:

- evidence permitted for a particular claim/use;
- legal norm and competent body supporting a legal conclusion;
- mandate/delegation authorizing a human or system action;
- calibration and certified envelope permitting a model output;
- data right/license permitting reuse or publication;
- validator result setting an authority ceiling;
- public signature depending on claim, evidence, world release and key state.

### Required impact output

```yaml
payload_recompute_set: artifacts whose semantic payload may change
authority_revalidation_set: unchanged or changed artifacts whose permitted use must be rechecked
public_notice_set: PolicyOS-controlled records/surfaces requiring freeze, correction, reissue or withdrawal
human_review_set: contested, high-stakes or value/authority decisions requiring competent review
historical_only_set: old artifacts retained but prohibited as current authority
```

### Change-pruning rule

Content recomputation may stop when a canonical semantic comparison proves the downstream value unchanged. Authority traversal may stop only when the **support, competence, right, freshness, validator and permitted-use relation** are also unchanged.

Examples:

- source text unchanged, but source authority revoked → no payload recompute; mandatory authority revalidation;
- cosmetic legal renumbering with stable resolved provision logic → annotation only;
- recalculated derived table has identical semantic rows → stop payload fan-out, but retain revalidation receipt;
- license expires → bytes remain; current publication/reuse authority may disappear.

## 4.10 Coordinated world releases

A governed world release is a verified vector:

```yaml
legal_release: version
source_data_release: version
knowledge_release: version
construct_registry: version
calibration_release: version
intervention_definitions: version
rulebook: version
validator_set: version
jurisdiction_pack_set: version
valid_time: interval
transaction_time: timestamp
compatibility_matrix_ref: reference
known_gaps: [...]
authority_boundary: ...
```

The capstone includes an unsafe vector assembled from:

```text
new law + old dataset + new calibration + old construct mapping + old validator
```

Every component is individually real; the vector was never verified together. It must remain `candidate` or `shadow`, never become the governed head.

Required tests:

- shadow differential benchmarks;
- atomic governed-head swap;
- old release tags retained;
- rollback without historical rewrite;
- partial fan-out detected before the new head appears current on all surfaces;
- current incremental state equals clean rebuild under the governed vector.

## 4.11 Living-law operations

The legal subscenario covers:

1. immutable source intake and content hash;
2. source/document identity and official publisher;
3. adoption, publication and effective times;
4. new act, amendment, corrigendum, repeal, consolidation, duplicate and metadata-only change;
5. amendment-target and reference resolution;
6. transitional provisions and retroactivity;
7. competent body, territory, binding force and authority type;
8. shadow branch and differential benchmark;
9. governed legal release;
10. affected case/claim/obligation/public-record fan-out.

### Expected legal reactions

| Change | Expected reaction |
|---|---|
| Cosmetic renumbering, resolved logic unchanged | `annotate_only`; no full recompute |
| Amendment without applicability change | Record/version update; no authority change |
| New applicable exception | Mandatory affected-scope revalidation |
| Future-only change | Schedule wake before effective time; historical cases remain replay-valid |
| Repeal of current authority | Freeze affected current promotion; revalidate/reissue/withdraw |
| New delegation or competent body | Competence recomputation |
| Unknown jurisdiction | Block; never fall back silently |
| International/EU source with no domestic applicability proof | Context only, not binding domestic authority |

## 4.12 KPI, monitoring and learning protocol

### KPI families

```text
result
implementation
guardrail
leading
diagnostic
context
measurement_health
```

These are non-fungible. No weighted sum can let a good result KPI cancel subgroup harm or measurement failure.

### Diagnosis before adaptation

| Injected signal | Required diagnosis |
|---|---|
| Threshold crossed | Verify definition, source, timing, seasonality, revision, implementation state and causal attribution |
| Data revised | Recompute measurement/history; do not label theory refuted automatically |
| KPI definition changed | New semantic series/epoch; no splice without declared bridge |
| Implementation failure | Delivery/capacity diagnosis, not causal-model rejection by default |
| Measurement failure | Freeze inference; repair measurement |
| Subgroup harm under acceptable average | Distributional review and potential scope narrowing |
| Causality unidentifiable | Freeze automatic adaptation; produce bounds/uncertainty/acquisition path |
| Behavioral response changes data | Performativity/endogeneity safety review |
| Another policy changes baseline | Interference/context-model update |
| Delayed/censored harm | Preserve incomplete outcome status; no early confirmation |

### Candidate adaptation ladder

```text
observe
→ early_warning
→ diagnose
→ refresh
→ recompute
→ recalibrate
→ adjust_implementation recommendation
→ narrow_scope
→ partial_reissue
→ redesign
→ pause recommendation
→ rollback recommendation
→ terminate recommendation
```

PolicyOS may produce recommendations and custody reactions. External programme authorities execute implementation adjustment, pause, rollback or termination.

## 4.13 Public records and signatures

The public-record subscenario includes:

- a signed initial limited record;
- PUBLIC, REVIEWER and MACHINE projections from one substrate;
- a compression-loss receipt;
- multilingual variants;
- key rotation and later key compromise;
- correction, API supersession, controlled cache invalidation, subscriber notification, correction feed and archive linkage;
- historical verification under old key material and algorithm/key-renewal evidence;
- a cryptographically valid but semantically stale record;
- a public-verification state that may be `current_verified`, `historically_verified`, `verification_degraded`, `superseded`, or `withdrawn` without collapsing those meanings.

The cross-view disclosure budget must also test whether repeated PUBLIC/REVIEWER/MACHINE views, diffs, hashes, ordering or timing reconstruct a fact denied to an audience. A record is not publishable merely because its signature verifies. The signature proves integrity and signer binding within its cryptographic profile; current semantic authority remains a separate oracle.

## 4.14 Administrative boundary traps

### Appeal

- External appeal body adjudicates.
- PolicyOS receives and admits the outcome.
- PolicyOS computes affected claims and corrects/reissues/supersedes/withdraws its own records.
- Any `AppealAdjudicated` event emitted with PolicyOS as operator is a boundary failure.

### Notice

- External notice system sends a message.
- `message_sent` does not prove legally effective service.
- PolicyOS may consume separately authenticated proof-of-service evidence.
- PolicyOS never becomes the notification channel.

### Compensation

The benchmark keeps five stages distinct:

```text
compensation_recommended
compensation_authorized
compensation_payment_initiated
compensation_paid
compensation_reconciled
```

The first may be a PolicyOS recommendation. The remaining stages are external institutional acts whose evidence may affect PolicyOS claims.

### Individual decisions

A case-management system attempts to consume a policy-level artifact for individual eligibility/risk/sanction. The export must be blocked by the policy-to-individual-decision firewall; aggregate returned implementation evidence remains admissible through a separate interface.

### Procurement and delivery

PolicyOS may assess options and admit supplier/delivery evidence. It may not select a vendor, sign a contract, schedule staff, deliver the service, or manage citizen cases.

## 4.15 Expected longitudinal custody trace

The principal expected trace is:

1. **Design:** PDC compiles the synthetic design and identifies a decisive mandate/delegation obligation.
2. **Honest terminal:** the case reaches `acquisition_required`; no positive recommendation is promoted.
3. **Suspension:** immutable suspension record committed; worker and locks released; public posture shows waiting with an explicit path.
4. **Rejected look-alikes:** partial and similar artifacts are received but do not satisfy the obligation.
5. **Decisive evidence:** competent delegation is authenticated and admitted; a typed wake is raised.
6. **First resume failure:** reviewer certification has expired; resume is blocked despite the correct delegation.
7. **Successful resume:** certification and all 20 gates pass; valid artifacts are reused, stale artifacts are marked, minimal recomputation occurs, and a human issues a limited pilot decision.
8. **First publication:** a limited, signed, multi-audience record is published with explicit denied uses and preservation profile.
9. **World drift:** source correction, retraction, retroactive data revision, schema and construct changes, calibration expiry and workflow/validator changes produce scoped recomputation, revalidation or migration review.
10. **Living law:** a norm is published before it is effective, later becomes effective, receives a corrigendum and amendment, then is repealed. Cosmetic renumbering remains annotation-only.
11. **Institutional change:** responsible body changes; delegation and reviewer certification expire; acting appointment and successor delegation are independently evaluated.
12. **Monitoring:** an early warning does not auto-change policy; subgroup harm and implementation/measurement failures trigger diagnosis and human review.
13. **Performative context:** behavior and another policy change the observed baseline; no self-confirming posterior update is allowed.
14. **Appeal/correction:** external appeal outcome is admitted; PolicyOS corrects and partially reissues its own records; third-party caches are outside direct control but controlled surfaces and correction feeds update.
15. **Administrative traps:** proof-of-service, compensation stages, individual-decision use, procurement and delivery remain externally owned.
16. **Authority loss:** DSA/license/validator/delegation/key changes can invalidate authority while payload stays unchanged.
17. **Resilience:** worker, database, CAS, webhook, duplicate, out-of-order, partial fan-out and recovery faults are injected; state is reconciled under RPO/RTO targets.
18. **Mass invalidation:** 10,000 synthetic cases become stale; backpressure/dedupe/public-freeze semantics preserve correctness.
19. **Matter split/successor:** new child/successor matter receives no unrestricted authority inheritance.
20. **Final resolution:** after repeal and validator-obligation discovery, unaffected claims are partially reissued, the previous public record is superseded, unsupported legal/applicability claims are withdrawn, and every prior state remains replayable.

## 4.16 Candidate resilience classes and RPO/RTO targets

These are benchmark targets, not production commitments.

| Custody class | Candidate RPO | Candidate RTO | Public posture during breach |
|---|---:|---:|---|
| Shadow/candidate | Last committed event; ≤24 h | 48 h | Internal unavailable/degraded |
| Governed but unpublished | Zero committed custody events | 24 h | Blocked from publication |
| Published current | Zero committed events and signed history | 4 h for authoritative status; 24 h full replay | Stale/verification-degraded banner immediately |
| Active incident/appeal | Zero accepted event/outcome records | 1 h routing; 8 h full service | Public/current claim frozen if affected |
| Legal release/head | Zero governed head changes | 4 h rollback/reconcile | Previous governed head remains current |
| Public verification log | Zero signed entries/consistency proofs | 4 h | Verification degraded, never false verified |
| Cold historical archive | No loss of retained record/evidence chain | 72 h restore exercise | Historical verification unavailable/degraded, current state unaffected if independently held |

## 4.17 Ground-truth and oracle design

### Frozen semantic oracle

An independently adjudicated calendar maps each fixture to:

- expected evidence state;
- wake/no-wake;
- artifact and authority impact sets;
- required human review;
- expected current claim and public state;
- prohibited PolicyOS actions.

### Clean rebuild oracle

At declared checkpoints, rebuild current matter/case state from the frozen source corpus, governed world-release vector, current rules and admitted evidence. Compare:

- claim semantic hashes;
- authority boundaries and denied uses;
- public-record state;
- affected-case sets;
- matter/episode associations.

### Historical replay oracle

Replay only artifacts and rules available/admitted by cutoffs:

```text
2027-01-18  suspension state
2027-07-02  first public record
2028-01-05  post-legal-effective governed release
2028-04-02  post-appeal correction
2028-09-15  post-compromise/recovery state
2028-12-20  final current and historical views
```

Later evidence must not leak backward.

### Authority oracle

A sealed panel labels:

- competent actor/forum;
- authority scope and TTL;
- permitted and prohibited use;
- whether evidence is binding, advisory, reported, disputed or unresolved;
- whether identity/succession or legal effect requires human adjudication.

### Public-record oracle

For every controlled surface and time slice, the oracle specifies:

- current/limited/stale/correction-pending/corrected/superseded/withdrawn/archived/verification-degraded;
- exact material limitations and denied uses that must remain visible;
- linked correction and historical records.

### Human-review oracle

Three independent reviewers receive a sealed packet. Material disagreements are not averaged into a scalar truth. They produce:

- consensus where possible;
- documented dissent;
- `contested` or `unresolved` where competence or interpretation remains genuinely open;
- an authority ceiling and escalation rule.

### Fault-recovery oracle

Each injected fault has an expected:

- detectable symptom;
- custody state;
- allowed/prohibited action set;
- RPO/RTO class;
- reconciliation set;
- public posture;
- final current and historical state.

## 4.18 What the benchmark proves and cannot prove

### A pass supports

- the declared events were processed with correct identities, clocks and provenance;
- suspension did not occupy a worker and state was not lost;
- wake/resume gates were not bypassed;
- incremental output matched clean rebuild for the scenario;
- historical replay matched the cutoff oracle;
- public corrections and signature states were coherent across controlled surfaces;
- external institutional acts were consumed as evidence without execution overclaim;
- specified faults recovered within candidate targets.

### A pass does not support

- universal lifetime custody;
- legal compliance outside the mapped example;
- production availability or fleet-scale performance;
- correctness of real policy effects;
- complete open-world obligation discovery;
- fairness, legitimacy or institutional acceptance beyond the benchmark packet;
- authority to execute any administrative act;
- readiness to publish real public records.

---
# 5. Counterexamples And Failure Modes

| Counterexample | Unsafe implementation behavior | Expected benchmark failure |
|---|---|---|
| Resume without reauthorization | Restores checkpoint and immediately executes using old user/role/delegation | `unauthorized_authority_upgrades > 0`; resume-gate fixture red |
| Similar artifact closes obligation | Press release or generic legal memo satisfies the exact municipal delegation gap | False wake; obligation-closure oracle mismatch |
| Late event silently changes publication | Retroactive data revision overwrites the original public record | `silent_historical_rewrites > 0`; historical replay mismatch |
| Payload unchanged, authority lost | Retracted source/license expiry leaves byte-identical artifact current | `authority_loss_detection_rate < 1`; stale public failure |
| Latest-of-each release | Unverified component versions become current because each is newest | World-release compatibility kill |
| Threshold-driven adaptation | KPI crossing directly invokes a policy change or posterior update | Adaptation-without-diagnosis boundary failure |
| Administrative overreach | H2 sends a notice, adjudicates an appeal, pays compensation or selects a vendor | `out_of_boundary_actions_attempted > 0` |
| Duplicate irreversible action | Duplicate event or wake creates two reissues, corrections or external commands | `duplicate_irreversible_actions > 0` |
| Silent historical rewrite | Migration or correction mutates old CAS/public history | Replay parity and immutable-hash failure |
| Stale public record | One PolicyOS surface still shows current after canonical supersession | `stale_public_shown_as_current > 0` |
| Unknown jurisdiction fallback | `ZZ-01` receives Ukrainian rules/authority | `jurisdiction_fallback_violation_rate > 0` |
| Runbook treated as DR proof | Documents exist, but restore/fault drill is not executed | DR evidence missing; run cannot pass |
| Event-ID overfitting | Code branches on `EVT-xxx` rather than semantic fields | Hidden renumber/permutation fixture fails |
| Case-specific code | MSME-specific special branch passes while adjacent unseen case fails | `no_case_specific_code` governance check fails |
| Observation becomes authority | Dashboard or media report changes claim state without admission | `unauthorized_authority_upgrades > 0` |
| Cryptographic-validity laundering | Signature verifies, so semantically stale record is shown as current | Public-record oracle failure |
| False evidence independence | Corrected/reissued copies count as independent corroboration | P14 mutation fixture; evidence-strength mismatch |
| Matter split inherits all authority | Successor/child matter receives parent evidence without scope review | Matter-lineage/authority oracle failure |
| State restore changes tenant | Recovered state is attached to another tenant or cell | Security and replay kill |
| Human rubber stamp | After-hours or expired reviewer approval is accepted without evidence exposure | Human-review integrity kill |
| Validator self-attestation | New validator claims its own soundness and closes an obligation | Independent-validator and P32 failure |
| Incomplete fan-out | World head changes before all affected claims/public records are reconciled | `missed_affected_cases > 0` or public-head freeze failure |
| High reuse hides stale reuse | Reuse score is high because invalid artifacts were reused | `invalid_artifact_reuse > 0`; headline efficiency ignored |
| Fast revalidation skips checks | Low latency achieved by bypassing matter, delegation or freshness gates | Authority gate kill despite good timing |

The benchmark’s role is to make these failures observable at the level of **meaning and authority**, not only process status.

---

# 6. Benchmark Or Fixture Proposal

## 6.1 Fixture strata

The benchmark should contain three separately governed sets:

| Fixture set | Visibility | Purpose |
|---|---|---|
| Public core | Fully published scenario shell, event families, metric definitions, critical falsifiers and a representative subset of events | Reproducibility and implementation guidance without revealing all variants |
| Sealed semantic set | Hidden timestamps, reordered delivery, altered IDs, plausible look-alikes, authority conflicts, matter split variants and fault combinations | Prevent event-ID and exact-payload overfitting |
| Adjacent unseen case | A structurally different policy matter, such as a school-building energy retrofit programme, sharing the same custody grammar but different actors/evidence | Tests generalization and no-case-specific-code |

The main calendar below contains the public semantic skeleton. A later implementation should create at least two hidden variations per major event class.

## 6.2 Mutation tests

Required mutations include:

- remove the decisive delegation artifact while keeping a similarly titled document;
- preserve all marker fields but break content binding;
- change tenant or jurisdiction only;
- revoke source authority without changing bytes;
- replace a qualified proof of service with “message sent”;
- change `limited` to `confirmed` in one translation;
- drop a material limitation from the public summary;
- combine PUBLIC/REVIEWER/MACHINE diffs, hashes, ordering or timing to reconstruct a forbidden fact;
- replace a same-input evidence artifact with a wrong-run or fixture-only artifact while retaining matching field names;
- rotate event IDs and delivery order;
- duplicate a correction, wake and compensation report;
- remove one affected-case dependency edge;
- replace a governed world vector with latest-of-each versions;
- corrupt a CAS object while leaving its manifest reference;
- mark a runbook present while removing drill evidence;
- allow the validator under test to self-attest its soundness;
- remove the discovered obligation while retaining the δ marker strings.

The verifier itself must fail when the protected property is removed while marker strings remain, following repository failure pattern P29. fileciteturn51file0

## 6.3 Metamorphic properties

1. Renaming the policy does not erase custody history.
2. Permuting delivery order does not change event-time truth.
3. Duplicating an event does not duplicate an irreversible action.
4. Removing decisive authority evidence downgrades or blocks the result.
5. Adding irrelevant evidence does not close an obligation gap.
6. A similar artifact does not satisfy the exact original obligation.
7. Payload-preserving source revocation triggers authority revalidation.
8. Cosmetic legal renumbering does not trigger full recomputation.
9. A new applicable legal exception triggers revalidation.
10. A retroactive revision changes the current interpretation but not historical replay.
11. A KPI threshold crossing without diagnosis cannot change policy automatically.
12. A translation cannot upgrade `limited` to `confirmed`.
13. A summary dropping a material limitation fails.
14. A revoked key cannot make a record appear currently verified.
15. An unknown jurisdiction never inherits another jurisdiction silently.
16. Restored state cannot bypass identity, tenant, delegation or permission gates.
17. Incremental and clean-rebuild current claims are semantically equivalent.
18. Historical replay differs from current state when later evidence exists but matches what was knowable then.
19. Administrative evidence receipt never implies PolicyOS performed the action.
20. A matter split does not copy unrestricted authority to descendants.
21. A correction supersedes rather than overwrites.
22. An unverified latest-of-each world release fails.
23. Changing event IDs does not change behavior.
24. Replacing the primary case with the adjacent unseen case preserves the generic custody properties.
25. Reducing the scenario to only successful events must not satisfy the balanced-learning requirement.

## 6.4 Human-review packet

A sealed review packet contains:

- matter and case identity evidence;
- event chronology by all clocks;
- competing legal and institutional interpretations;
- authority/delegation records and expiry state;
- claims and public records affected;
- artifact and authority dependency graphs;
- counterevidence and unresolved obligations;
- expected consequences of false pass, false block and delayed action;
- permitted decisions and denied uses;
- proposed current/public state;
- reviewer mandate, independence, conflict disclosures and signature.

Reviewers must not see the implementation’s proposed answer before recording their own. Material disagreement yields `contested`/`unresolved`, not majority-as-ground-truth by default.

## 6.5 Metric rules

Every metric is computed against a frozen denominator. Denominators may not be changed after a run; excluded events require a predeclared rule or a new benchmark version.

Unless a row states otherwise, the time window is the complete 2027-01-05–2028-12-20 scenario; scope is the registered matter, case, synthetic 10,000-case fan-out, controlled PolicyOS surfaces and declared faults; exclusions are only those committed in the scenario manifest before the first run.

Reaction deadlines used by `time_from_world_event_to_correct_revalidation` are predeclared by class: immediate/≤1 virtual hour after admission for key compromise, forged evidence, tenant/jurisdiction violations and current-public authority loss; at or before legal effective/expiry time for known future changes; ≤1 virtual business day for high-material appeal, incident, subgroup-harm and source-revocation events; and ≤7 virtual days for normal non-public corrections.

### Critical and diagnostic metrics

| Metric | Numerator / denominator | Unit and authoritative source | Pass | Warning | Kill | Limitation |
|---|---|---|---:|---:|---:|---|
| `lost_case_state` | Required suspension/recovery state fields missing or semantically changed / required state fields | Count; suspension and recovery oracles | 0 | — | >0 | Does not measure unmodeled state |
| `stale_public_shown_as_current` | Controlled surface-time observations labeled current when oracle says stale/limited/superseded/withdrawn / controlled observations | Count/rate; public-record oracle | 0 | — | >0 | Third-party caches are measured separately from controlled surfaces |
| `unauthorized_authority_upgrades` | Stronger authority transitions lacking admitted competent evidence and gate receipt / all authority transitions | Count/rate; authority oracle | 0 | — | >0 | Cannot prove absence of unknown upgrade paths outside instrumented surfaces |
| `silent_historical_rewrites` | Historical cutoff states or artifact meanings altered without append-only successor / replay cutoffs | Count; replay oracle | 0 | — | >0 | Requires frozen historical hashes and semantic comparison |
| `missed_affected_cases` | Oracle-affected cases absent from actual impact set / oracle-affected cases | Count/rate; dependency oracle | 0 / 1.00 recall | — | any miss | Synthetic fleet denominator only |
| `duplicate_irreversible_actions` | More than one committed action for one semantic idempotency key / irreversible keys | Count; action and audit receipts | 0 | — | >0 | Duplicate requests may occur; duplicate committed effects may not |
| `out_of_boundary_actions_attempted` | Non-probe PolicyOS attempts to perform prohibited external acts / all PolicyOS actions | Count; PAO-R1 boundary oracle | 0 | — | >0 | Deliberately injected negative probes are scored separately by prevention |
| `boundary_probe_prevention_rate` | Declared administrative-boundary probes prevented with no external side effect / declared probes | Share; BoundaryViolationReceipt set | 1.00 | — | <1.00 | Complements the zero-attempt mainline metric; probes must be explicitly declared |
| `external_execution_overclaim_rate` | PolicyOS records/projections claiming it performed an external act / external-act projections | Rate; public and audit oracle | 0 | — | >0 | Requires semantic copy review, not keyword-only lint |
| `jurisdiction_fallback_violation_rate` | Unknown/unsupported jurisdiction submissions mapped to another jurisdiction / unsupported submissions | Rate; jurisdiction oracle | 0 | — | >0 | Zero tolerance in governed/production posture |
| `invalid_artifact_reuse` | Stale, revoked, wrong-tenant, wrong-world or authority-invalid artifacts reused / reused artifacts | Count/rate; reuse oracle | 0 | — | >0 | Byte identity alone is not validity |
| `reused_artifact_share` | Oracle-valid eligible artifacts reused / all oracle-valid reusable artifacts | Share; resume and clean-build oracle | ≥0.75 | 0.50–0.75 | No standalone kill | Efficiency metric; cannot offset correctness failures |
| `minimal_recompute_share` | Unaffected eligible artifacts not recomputed / unaffected eligible artifacts | Share; clean-build dependency oracle | ≥0.90 | 0.75–0.90 | No standalone kill | Must be read with recompute recall |
| `recompute_recall` | Oracle-required recompute artifacts actually recomputed / required recompute artifacts | Share; clean-build oracle | 1.00 | — | <1.00 | Authority-only revalidations are excluded from payload denominator |
| `recompute_precision` | Actual recomputations in oracle-required set / all actual recomputations | Share; clean-build oracle | ≥0.95 | 0.80–0.95 | <0.50 | Diagnostic efficiency, not authority |
| `clean_rebuild_equivalence` | Current claims with equal semantic payload, boundary and public state / current claims | Share; clean rebuild | 1.00 | — | <1.00 | Accepted tolerance only for non-semantic ordering/serialization fields |
| `time_from_world_event_to_correct_revalidation` | Admission-to-correct-state duration minus class deadline | Virtual hours/days; event and reaction logs | No positive lateness | Any positive noncritical lateness | Critical/safety deadline missed | Benchmark time, not production SLO evidence |
| `consumed_evidence_binding_correctness` | Consumed evidence bound to correct producer, scope, matter/case, tenant, jurisdiction and claim / consumed evidence | Share; evidence/authority oracle | 1.00 | — | <1.00 | Does not prove external evidence itself true beyond oracle assumptions |
| `historical_replay_success_rate` | Cutoffs exactly matching expected historical state / tested cutoffs | Share; replay oracle | 1.00 | — | <1.00 | Semantic equivalence, not byte identity for derived projections |
| `disaster_recovery_success_rate` | Fault scenarios meeting state, RPO/RTO, public and reconciliation oracle / applicable fault scenarios | Share; fault oracle | 1.00 critical; ≥0.95 overall | 0.90–0.95 | Any critical failure | Synthetic environment cannot prove production capacity |
| `false_wake_rate` | Wake requests with no oracle-satisfying typed condition / wake attempts | Rate; wake oracle | 0 | — | >0 | Includes similar-artifact false wakes |
| `missed_wake_rate` | Required wake conditions not producing request by deadline / required wakes | Rate; wake oracle | 0 | — | >0 | Event producer outage is separately modeled |
| `duplicate_wake_rate` | More than one committed resume generation for one wake key / wake keys | Rate; resume receipts | 0 | — | >0 | Multiple contenders are allowed; only one generation may commit |
| `authority_loss_detection_rate` | Oracle authority-loss events detected and routed correctly / authority-loss events | Share; authority oracle | 1.00 | — | <1.00 | Includes payload-preserving revocation/expiry |
| `late_event_policy_correctness` | Late/out-of-order events assigned the expected typed reaction / late events | Share; temporal oracle | 1.00 | — | <1.00 | Some outcomes may be panel-adjudicated |
| `public_correction_fanout_completeness` | Controlled correction targets updated/linked / oracle controlled targets | Share; PAO-R36/public oracle | 1.00 | — | <1.00 | Third-party caches require durable notice, not guaranteed deletion |
| `cross_surface_status_consistency` | Surface snapshots consistent with canonical projection at same as-of / snapshots | Share; public oracle | 1.00 | — | <1.00 | Audience redaction may differ; status meaning may not |
| `translation_authority_parity` | Semantic units preserving status, limitation, denied use, time and uncertainty / translated units | Share; multilingual oracle | 1.00 | — | <1.00 material | Minor non-authority wording differences may be accepted |
| `human_review_escalation_correctness` | Mandatory escalations raised and prohibited automatic decisions prevented / mandatory cases | Share; human oracle | 1.00 mandatory recall | False-positive rate >0.10 | Any mandatory miss | Human disagreement is preserved, not forced into one label |
| `unresolved_obligation_detection_rate` | Oracle unresolved obligations detected / unresolved obligations | Share; obligation oracle | 1.00 | — | <1.00 | Open-world remainder remains declared |
| `validator_fault_detection_rate` | Injected validator faults detected and authority blocked/downgraded / injected faults | Share; mutation oracle | 1.00 | — | <1.00 | Does not prove no unknown validator defect |
| `no_case_specific_code` | Generic source inspection and adjacent-case parity | Binary; code/probe review | Pass | — | Fail | Later implementation check |
| `no_event_id_branching` | Behavior invariant under ID renumber/permutation | Binary; sealed metamorphic set | Pass | — | Fail | Does not forbid legitimate semantic type dispatch |
| `no_post_result_threshold_edit` | Hash-committed metric profile unchanged after first result | Binary; governance log | Pass | — | Fail | Changes require new version |
| `no_hidden_fixture_leak` | Sealed fixture access/audit shows no implementer disclosure | Binary; access log | Pass | — | Fail | Organizational control, not mathematical proof |
| `no_selective_event_exclusion` | Processed denominator equals registered denominator except predeclared exclusions | Binary; manifest/run receipt | Pass | — | Fail | Corrected fixture requires superseding benchmark version |

### Metric composition rule

The capstone verdict is:

```text
PASS only if every zero-tolerance metric passes
AND every required oracle passes
AND no governance/overfitting kill is present
AND all noncritical warning metrics are disclosed.
```

There is no weighted average. A good efficiency score cannot buy a failed authority or boundary gate.

## 6.6 Pass, warning and kill posture

| Outcome | Meaning |
|---|---|
| `pass_bounded` | All critical invariants and oracles pass for the declared benchmark envelope |
| `pass_with_warnings` | All critical invariants pass, but one or more noncritical efficiency/latency targets warn |
| `blocked_semantic` | Structure runs, but a semantic/authority/public-record oracle fails |
| `blocked_boundary` | Administrative overreach or external-execution overclaim occurs |
| `blocked_replay` | Historical or clean-build parity fails |
| `blocked_resilience` | Critical fault does not meet state/RPO/RTO/public oracle |
| `invalid_benchmark_run` | Fixture leakage, event exclusion, post-result threshold edit, missing denominator or case-specific code invalidates the evaluation |

These are benchmark verdict labels, not PolicyOS runtime authority statuses.


## 6.7 Real operator workflow

| Role | Primary responsibility | Separation requirement |
|---|---|---|
| Benchmark designer | Defines public scenario shell, invariants and metric profile before implementation results | May not approve own expected authority judgments alone |
| Fixture curator | Produces public/sealed event fixtures and mutation variants | Sealed set inaccessible to implementation team |
| Repository-baseline researcher | Pins commit, inventories existing owners and capability reality | Must report missing/partial owners without creating new canonical truth |
| Authority adjudicator | Determines expected `authoritative_for`, denied uses, competence and escalation | Independent from event producer and implementation team |
| Legal reviewer | Reviews legal-event identity, effective time, jurisdiction and competence | Does not adjudicate real law; validates synthetic mapping and uncertainty |
| Public-record reviewer | Freezes expected publication/correction/supersession/withdrawal states | Independent of Atlas implementation |
| Human-decision reviewer | Defines valid role, evidence exposure, active choice and dissent expectations | Cannot be the simulated decision maker in the same packet |
| Fault-injection operator | Executes declared faults, records blast radius and recovery evidence | Cannot edit oracles during the run |
| Independent evaluator | Computes metrics and compares against sealed oracles | Read-only access to implementation outputs |
| Result approver | Accepts bounded benchmark verdict and limitations | Cannot convert pass into production authority |
| Dispute resolver | Adjudicates benchmark expectation challenges and orders a superseding version | Preserves old expectations and run results |

### Automated steps

- schema and hash validation;
- fixture denominator checks;
- event delivery permutations and duplicates;
- clean rebuild and replay execution;
- metric calculation;
- controlled-surface crawling;
- authority-boundary diffing;
- fault injection and recovery-time capture;
- event-ID and case-identity mutation tests.

### Human-adjudicated steps

- matter split/successor ambiguity;
- conflicting competent sources;
- high-stakes delegation/acting appointment questions;
- whether a legal change is material to the claim;
- accepted semantic tolerances;
- public-language materiality;
- contested or unresolved outcomes.

### After-hours and unavailable authority

If a required human authority is unavailable:

- the case remains `suspended`, `blocked` or `review_required`;
- no cached or inferred approval substitutes;
- a deadline/availability event is recorded;
- public posture reflects the unresolved state;
- emergency authority is accepted only when separately declared, current and scope-valid.

### Conflict-of-interest controls

- implementers do not curate sealed expected traces;
- external-event producers do not verify their own competence evidence;
- reviewers disclose role and conflict state;
- material dissent is preserved;
- no majority vote may erase a known authority defect.

### Failed-run preservation

Every failed or invalid run retains:

- scenario and metric versions;
- implementation version;
- exact processed/excluded denominator;
- event and fault receipts;
- evaluator output;
- reason for invalidity or failure;
- any subsequent benchmark supersession link.

## 6.8 Benchmark governance and anti-overfitting

### Pre-registration and sealing

Before any implementation is evaluated, publish or hash-commit:

- scenario manifest;
- public event taxonomy;
- metric formulas and thresholds;
- critical kill rules;
- public fixture set;
- sealed fixture root hash;
- adjacent unseen case commitment;
- adjudicator and conflict rules;
- accepted tolerance policy.

### Change governance

A benchmark change requires:

1. a `BenchmarkChangeProposal` stating the defect and affected oracles;
2. independent review;
3. a new semantic version;
4. preservation of the old manifest, run results and expected traces;
5. a statement whether prior results remain comparable, require replay, or are retired.

Expected outcomes are never edited in place after a run.

### Anti-overfitting controls

```text
no_case_specific_code
no_event_id_branching
no_post_result_threshold_edit
no_hidden_fixture_leak
no_selective_event_exclusion
```

Additional controls:

- at least one hidden delivery-order permutation;
- at least one hidden look-alike artifact per decisive obligation;
- one hidden wrong-tenant and wrong-jurisdiction variant;
- one adjacent unseen policy case;
- source-flip and authority-revocation mutations;
- validator-defect mutation where marker fields remain intact;
- result review against all metrics, never one headline metric.

### Benchmark retirement

A benchmark version is retired only when its assumptions, event families or oracles no longer match the target custody envelope. Retirement creates a signed successor notice and preserves the retired manifest, sealed commitment, run results and comparability statement; it never deletes or edits prior expected traces.

### External-validity boundary

The benchmark covers one synthetic municipal economic-resilience matter, one parent jurisdiction, one municipal pack, one comparison jurisdiction and one unknown-jurisdiction negative. It does not justify extrapolation to criminal justice, immigration, healthcare eligibility, national security, taxation, or any other domain without new fixtures and authority review.

---

# 7. Artifact Contract Sketch

All sketches are `research_only` and `candidate_for_consolidation`. They must extend existing PDC, runtime-quality, Fabric, Lex, DDM, audit and Atlas owners rather than create a second authority system.

## 7.1 Common research envelope

Every artifact below includes:

```yaml
schema_version: versioned research schema
rule_version_refs: [...]
scenario_version: version
tenant_ref: explicit tenant
jurisdiction_refs: [...]
policy_matter_ref: reference or external_dependency_assumption
case_refs: [...]
time_context:
  event_time: optional
  valid_time: optional
  legal_effective_time: optional
  observation_time: optional
  admission_time: optional
  processing_time: optional
  transaction_time: required
provenance:
  producer_ref: reference
  activity_ref: reference
  source_refs: [...]
  content_hashes: [...]
  runtime_event_refs: [...]
authority_boundary:
  authoritative_for: [...]
  may_not_use_for: [...]
uncertainty_and_limits: [...]
```

Missing tenant, jurisdiction, provenance, version or purpose-scoped authority fails closed for governed use.

## 7.2 `CapstoneScenarioManifest`

```yaml
CapstoneScenarioManifest:
  scenario_id: string
  scenario_version: semver
  repository_commit: git SHA
  calendar_start: date
  calendar_end: date
  policy_matter_ref: reference
  policy_matter_ref_status: external_dependency_assumption | admitted
  case_refs: [...]
  tenant_refs: [...]
  jurisdiction_refs: [...]
  actor_registry_ref: reference
  boundary_register_ref: reference
  initial_world_release_ref: reference
  world_release_fixture_refs: [...]
  initial_claim_refs: [...]
  initial_obligation_refs: [...]
  event_fixture_refs: [...]
  public_fixture_root: digest
  sealed_fixture_commitment: digest
  adjacent_case_commitment: digest
  ground_truth_ref: sealed reference
  metric_profile_ref: reference
  fault_profile_ref: reference
  oracle_profile_ref: reference
  exclusion_policy_ref: reference
  authoritative_for:
    - benchmark_denominator
    - scenario_version_binding
  may_not_use_for:
    - production_readiness
    - legal_compliance
    - administrative_execution
```

Fail closed if fixture roots, metric profile or oracle version do not resolve.

## 7.3 `CapstoneEventFixture`

```yaml
CapstoneEventFixture:
  fixture_event_id: string
  event_type: discriminator
  producer_ref: reference
  operator_ref: reference
  boundary_class: own | integrate | observe | out_of_scope
  policy_matter_ref: reference
  case_refs: [...]
  tenant_ref: string
  jurisdiction_refs: [...]
  event_time: timestamp
  legal_effective_time: timestamp_or_interval | null
  valid_time: interval | null
  publication_time: timestamp | null
  observation_time: timestamp
  receipt_time: timestamp
  admission_time: timestamp | null
  processing_time: timestamp | null
  transaction_time: timestamp
  correction_time: timestamp | null
  revocation_time: timestamp | null
  expiry_time: timestamp | null
  dedupe_key: string
  correction_of: reference | null
  revokes: reference | null
  source_schema_version: string
  admission_rule_version: string
  payload_ref: CAS/reference
  provenance_ref: reference
  authority_boundary: AuthorityBoundary
  expected_wake:
    required: bool
    condition_type: string | null
    deadline: timestamp | null
  expected_impact:
    payload_recompute_refs: [...]
    authority_revalidation_refs: [...]
    public_notice_refs: [...]
    human_review_refs: [...]
    historical_only_refs: [...]
  expected_policyos_actions: [...]
  prohibited_policyos_actions: [...]
  expected_public_posture: string
  oracle_ref: reference
```

Fail closed if an INTEGRATE fixture lacks an external operator/producer or if an OUT action is expected from PolicyOS.

## 7.4 `ExpectedCustodyTrace`

```yaml
ExpectedCustodyTrace:
  trace_id: string
  scenario_version: string
  fixture_event_ref: reference
  expected_state_before_ref: reference
  evidence_receipt_expectation:
    state: received | authenticated | quarantined | verified | admitted |
           disputed | corrected | revoked | stale | rejected | historical_only
    evidence_refs: [...]
  admission_expectation:
    disposition: admit | reject | quarantine | contest | no_authority_effect
    reason_codes: [...]
  dependency_impact_expectation:
    payload_recompute_set: [...]
    authority_revalidation_set: [...]
    public_notice_set: [...]
    human_review_set: [...]
    historical_only_set: [...]
  wake_expectation:
    requested: bool
    dedupe_key: string | null
  resume_gate_expectations:
    - gate_id
    - expected_status
    - expected_reason
  reused_artifact_refs: [...]
  stale_or_invalidated_refs: [...]
  recomputation_expectation: [...]
  human_review_expectation: {...}
  expected_authority_change: {...}
  expected_public_record_change: {...}
  expected_state_after_ref: reference
  historical_state_preservation_refs: [...]
  accepted_ambiguity: {...}
  authoritative_for:
    - sealed_semantic_oracle
  may_not_use_for:
    - production_runtime_state
```

## 7.5 `CapstoneRunReceipt`

```yaml
CapstoneRunReceipt:
  run_id: string
  scenario_version: string
  implementation_version: string
  repository_commit: git SHA
  world_release_vector: {...}
  started_at: timestamp
  completed_at: timestamp
  registered_event_count: integer
  processed_event_refs: [...]
  rejected_event_refs: [...]
  excluded_event_refs: [...]
  exclusion_policy_ref: reference
  wake_attempts: [...]
  resume_gate_failures: [...]
  revalidation_results: [...]
  public_correction_refs: [...]
  boundary_violation_refs: [...]
  metric_results: [...]
  clean_rebuild_comparison_ref: reference
  historical_replay_comparison_refs: [...]
  fault_recovery_result_refs: [...]
  human_review_result_refs: [...]
  governance_check_results: [...]
  final_verdict: pass_bounded | pass_with_warnings | blocked_* | invalid_benchmark_run
  known_limitations: [...]
  authoritative_for:
    - benchmark_run_result
  may_not_use_for:
    - capability_claim
    - production_readiness
    - authority_grant
```

The registered denominator must equal processed plus predeclared exclusions; selective omission invalidates the run.

## 7.6 `BoundaryViolationReceipt`

```yaml
BoundaryViolationReceipt:
  violation_id: string
  scenario_version: string
  attempted_action: string
  triggering_event_ref: reference
  actor_ref: reference
  violated_boundary_decision_ref: reference
  prevention_mechanism_ref: reference
  prevented: bool
  external_side_effect_occurred: bool
  affected_claim_refs: [...]
  affected_public_record_refs: [...]
  required_correction: [...]
  audit_refs: [...]
  authority_boundary:
    authoritative_for: [boundary_violation_detection]
    may_not_use_for: [proof_external_institution_acted]
```

A mainline non-probe attempted action is a kill even if blocked; a declared negative-control probe is successful only when prevented with no external side effect.

## 7.7 `ReplayParityReceipt`

```yaml
ReplayParityReceipt:
  receipt_id: string
  scenario_version: string
  replay_cutoff: timestamp
  replay_mode: historical_as_known | current_clean_rebuild | migration_compare
  source_corpus_refs: [...]
  world_release_ref: reference
  rule_version_refs: [...]
  schema_version_refs: [...]
  validator_version_refs: [...]
  expected_state_ref: reference
  actual_state_ref: reference
  semantic_differences: [...]
  authority_differences: [...]
  public_record_differences: [...]
  identity_differences: [...]
  accepted_tolerances: [...]
  status: pass | fail | review_required
  authority_boundary:
    authoritative_for: [replay_parity_for_declared_cutoff]
    may_not_use_for: [universal_reproducibility]
```

## 7.8 Canonical-owner map

| Concept | Existing owner | Owner state | Benchmark role | Proposed disposition |
|---|---|---|---|---|
| Policy matter identity | PAO-R0 / PDC lineage candidate | Provisional | Scenario anchor and split/successor scope | Consume; do not redefine |
| Boundary decisions | PAO-R1 / PDC authority owner | Provisional | Administrative action constraints | Consume |
| Suspension/resume | Control plane + Scientist; future H2 | Partial | Mechanism under test | Extend in future H2 |
| Artifact dependency | Core artifacts / IR lineage | Partial | Recompute oracle | Extend existing |
| Authority dependency | PDC/runtime quality/decision validity | Partial/missing bridge | Authority impact oracle | Candidate consolidation |
| Event-time semantics | Fabric/core temporal | Partial | Calendar and late-event semantics | Consolidate, do not duplicate |
| World release | Fabric/GY-N12 candidate | Partial/absent producer | Compatible world oracle | Extend existing owners |
| Legal release | Lex/Data Forge | Partial | Legal event and release fixtures | Extend Lex |
| KPI contracts | DDM/core feedback | Partial | Monitoring events and diagnosis | Extend DDM/OPS-R5 |
| Audit events | Core audit/runtime diagnostic events | Existing/partial | Evidence trail and portable verification | Extend existing |
| Public projection | Atlas/runtime API | Planned/partial | Display oracle only | Must not mint authority |
| Public correction | PAO-R36/publication owner | Provisional | Correction fan-out | Consume |
| Public verification | Core signing/audit + INT-R7 | Partial | Key/archival fixtures | Consolidate with INT-R7 |
| Resilience | Runbooks/platform + future H2 | Partial | Fault and recovery oracle | Test; do not create duplicate platform |
| Benchmark governance | Team architecture/research owner | Missing runtime owner by design | Pre-registration and sealed oracle | Research artifact; candidate consolidation |

No new canonical owner is established by this report.

---
# 8. Later Integration Handoff

This section identifies evidence-chain responsibilities only. It is not an implementation plan.

| Benchmark component | Producer | Persisted artifact/event | Bridge | Consumer | Verification | Surface | Likely home |
|---|---|---|---|---|---|---|---|
| Scenario manifest and metric profile | Benchmark governance owner | Versioned manifest and hash commitments | Benchmark runner | Independent evaluator | Schema, denominator and signature checks | Reviewer/MACHINE | Research/quality tooling |
| Policy matter/case anchor | PDC identity owner | Matter/case association | H2/PDC | All custody records | Identity/tenant/jurisdiction and lineage checks | Atlas matter/case header | PDC |
| Suspension record | Future H2 over control plane | CAS suspension record + durable state row | H2 control worker | Wake scheduler/resume gate | Worker-release, integrity and state-preservation tests | DS15/DS18-style projection | Future H2 |
| External evidence fixture | External/family producer | Source artifact plus evidence receipt | Runtime quality adapter | PDC/Decision-Validity/H2 | Resolve, content-bind, competence, scope, time, provenance | Evidence detail | RQ + family owner |
| Wake request | H2 watcher | Dedupe-keyed wake event | Control-plane outbox | Resume-gate evaluator | False/missed/duplicate-wake fixtures | Custody timeline | Future H2 |
| Resume receipt | PDC/RQ/H2 | CAS receipt + audit event | Control plane | Worker and publication consumers | Twenty-gate semantic tests | Reviewer/MACHINE | Future H2 + PDC |
| Artifact impact | Artifact graph owner | `payload_recompute_set` | H2 incremental engine | Recompute scheduler | Clean-build recall/precision | DS16 impact view | Core/IR + H2 |
| Authority impact | PDC/RQ/Decision-Validity | `authority_revalidation_set` and notices | H2 | Claim/publication lifecycle | Payload-unchanged authority-loss fixtures | DS18/DS13 | PDC/RQ/H2 |
| World release | Fabric/GY-N12 owner | Governed vector/head event | H2 | Case resume, rebuild and replay | Compatibility, atomic-head and rollback tests | Epoch/release chrome | Fabric/GY-N12 |
| Legal release | Lex/Data Forge | Legal delta/release and impact event | RQ/H2 | Claims, obligations and public records | Legal differential fixtures and no-fallback tests | Legal/epoch view | Lex |
| KPI observation | External producer/DDM | Observation artifact | RQ/DDM | Diagnosis and learning gate | Definition/vintage/lineage and causal-safety tests | Monitoring view | DDM/OPS-R5 |
| Public correction | PDC/publication owner | Correction, supersession and notice artifacts | Runtime API/cache/feed | Atlas and subscribers | Cross-surface, translation and archive parity | PUBLIC/REVIEWER/MACHINE | PAO-R36/Atlas |
| Signature/key event | Security/core audit | Key/trust/revocation/evidence record | Public verifier | Public record and archive | Tamper, revoked-key, rotation and renewal fixtures | Public verification | Core audit + INT-R7 |
| Fault and recovery receipt | Fault operator/platform/H2 | Fault event, recovery and reconciliation artifacts | Benchmark evaluator | Fault oracle | RPO/RTO/state/public parity | Reviewer/MACHINE | Platform + H2 |
| Final run receipt | Independent evaluator | Signed benchmark report | Governance review | Result approver | Recompute metrics from raw receipts | Reviewer/public research summary | Research/quality tooling |

### Routing rule

- GY supplies design, world and promotion artifacts and consumes revalidation outcomes.
- Atlas projects custody truth.
- Fabric supplies temporal/data-release primitives.
- Lex supplies legal evidence and legal releases.
- DDM supplies monitoring/incident evidence and diagnosis inputs.
- Core audit supplies portable custody evidence.
- The long-lived mechanical process belongs in a future H2 Custody Runtime, not inside GY or Atlas.

## 8.1 Parallel-task fixture and metric map

| Task | Capstone fixture/event | Primary metric(s) | Failure prevented | Local assumption before task closes |
|---|---|---|---|---|
| PAO-R0 | Matter anchor; split/successor; wrong association correction | lost state, historical rewrite, authority inheritance | Case-as-lifetime identity and false lineage | `policy_matter_ref` is provisional and non-authoritative |
| PAO-R1 | Appeal/notice/payment/procurement/delivery traps | boundary actions, execution overclaim | PolicyOS becoming administrator | Provisional function-level boundary oracle |
| INT-R1 | Late discovery of decisive obligation; validator omission | unresolved obligation, validator fault | Conditional δ presented as complete | Open-world remainder and validator governance are local candidates |
| INT-R2 | Initial non-data delegation gap and similar-artifact negative | false wake, obligation correctness | “More data” closes mandate gap | Gap discriminator is research candidate |
| INT-R3 | Human/operator packet under time pressure and degraded public state | human escalation, comprehension sub-study | Operator misreads unknown/stale/limited | Behavioral instrument external to runtime verdict |
| INT-R4 | Behavioral response, interference and baseline-policy change | no unsafe posterior update | Self-confirming learning | No world-model writeback before safety gate |
| INT-R5 | Delegation expiry, acting appointment, reviewer certification and after-hours absence | unauthorized upgrades, human escalation | Wrong-role/expired approval | Authority graph fields are local candidate |
| INT-R6 | Translation upgrades `limited` to `confirmed` | translation parity | Multilingual authority inflation | Canonical semantic IDs assumed |
| INT-R7 | Rotation, compromise, revocation and archival verification | public/current verification and DR | Signature lifecycle collapse | Existing Ed25519/revocation is narrow seed only |
| INT-R8 | Summary drops material limitation; cross-view reconstruction mutation | public/cross-surface parity | Lossy summary looks safe | Compression-loss receipt candidate |
| INT-R9 | Preregistered scenario, sealed variants, adjacent unseen case | governance binary checks | Cherry-picking and case-specific code | First positive result not guaranteed |
| OPS-R1 | Months-long suspension, typed wake and 20 resume gates | lost state, false/missed/duplicate wake | Generic resume bypass | Candidate suspension/receipt fields |
| OPS-R2 | Authority loss without payload change; mass fan-out | affected-case recall, clean-build parity | Hidden authority dependencies | Separate graphs are local candidate |
| OPS-R3 | Workflow/validator version change and replay old/new compare | replay parity | Dormant case resumes under incompatible logic | Four migration modes are candidates |
| OPS-R4 | Late, retroactive, duplicate and correction-before-original events | late-event correctness, duplicate actions | Processing-time/receipt-order truth | Multi-clock envelope candidate |
| OPS-R5 | KPI definition/schema change, early warning, subgroup harm | no auto-adaptation, binding correctness | Threshold-driven policy changes | KPI type/response table candidate |
| OPS-R8 | Latest-of-each vector, partial head fan-out and rollback | clean-build/current parity | Incompatible world head | WorldRelease vector candidate |
| OPS-R9 | Retroactive revision and derived refresh | recompute precision/recall | Stampede and historical rewrite | Derived recipe semantics from GY |
| OPS-R10 | New act, effective date, corrigendum, exception, repeal, renumbering | legal impact correctness | Living-law miss or indiscriminate fan-out | Current legal batch is partial |
| OPS-R11 | Municipal pack and `ZZ-01` | no jurisdiction fallback | Silent Ukraine fallback | Pack schema candidate |
| OPS-R14 | Worker/DB/CAS/key/credential/license/mass-stale faults | DR success, authority loss | Runbook-as-proof and surprise expiry | Candidate RPO/RTO by custody class |
| PAO-R4 | Individual case system consumes policy artifact | boundary actions | Policy-level output becomes individual decision | Prohibited-use matrix candidate |
| PAO-R36 | Appeal/correction, caches, translations and feeds | correction fan-out, cross-surface consistency | Silent edit or stale public surface | Controlled-surface denominator candidate |

---

# 9. Promotion And Kill Rules

## 9.1 `research_only`

Current status. Required while:

- PAO-R0/PAO-R1 anchors are provisional;
- no runner executes the complete fixture set;
- no sealed authority/public/fault oracle exists;
- no matter-aware H2 custody process exists;
- jurisdiction and institutional mappings are synthetic;
- RPO/RTO targets are unvalidated.

## 9.2 `prototype_allowed`

A prototype is allowed when:

1. it uses synthetic/non-authoritative fixtures;
2. no public production record or external administrative action is possible;
3. external acts are represented only by fixture evidence;
4. every event carries tenant, jurisdiction, provenance, clocks, versions and AuthorityBoundary;
5. the public and sealed denominators are hash-committed;
6. the implementation has no event-ID or case-specific branches;
7. failed runs and corrections are preserved.

## 9.3 `governed_allowed`

A governed pilot of the benchmark requires:

- independently reviewed PAO-R0/PAO-R1 anchors;
- real typed producers/bridges for every tested PolicyOS-owned path;
- sealed semantic, authority, public and fault oracles;
- clean rebuild and historical replay execution;
- twenty resume gates enforced at one chokepoint;
- cross-tenant and unknown-jurisdiction negatives;
- no missing provenance or fail-closed behavior;
- controlled Atlas surfaces derived from canonical state;
- full critical metric pass.

This permits a governed **benchmark run**, not a real policy publication.

## 9.4 `production_candidate`

Production candidacy for the custody mechanism would additionally require:

- representative real institutional integrations and legal review;
- production-scale performance and 10,000-case fan-out evidence;
- real deployment restore drills against declared RPO/RTO;
- key/algorithm/archive renewal practice;
- public correction and notification agreements;
- independent security, privacy, records and accessibility reviews;
- multiple policy domains and jurisdictions;
- no critical failure across repeated runs and hidden variants.

A capstone pass remains necessary but not sufficient.

## 9.5 Mandatory block/kill rules

Block promotion if any of the following occurs:

1. matter or boundary anchor missing or silently inferred from names;
2. `case_id` treated as lifetime identity;
3. external evidence admitted without resolve + content-bind + verifier provenance;
4. any mandatory resume gate bypassed;
5. no clean-rebuild parity;
6. historical replay mismatch;
7. stale/superseded/withdrawn record shown current;
8. unauthorized authority upgrade;
9. affected case missed;
10. duplicate irreversible action;
11. administrative action attempted by PolicyOS;
12. external execution overclaimed;
13. INTEGRATE event lacks fail-closed absence behavior;
14. missing producer, tenant, jurisdiction, schema, rule or temporal provenance;
15. unknown jurisdiction falls back silently;
16. invalid artifact reused;
17. public correction fan-out incomplete on a controlled surface;
18. translation materially changes authority semantics;
19. runbook substituted for recovery drill;
20. benchmark thresholds or expected outcomes changed after observing results;
21. selective event exclusion, sealed-fixture leak or event-ID branching;
22. new canonical owner created without P27 evidence;
23. unresolved identity/authority scored as automatic success;
24. δ or completeness claim survives removal of a decisive obligation.

## 9.6 `out_of_scope`

The capstone may not authorize or test PolicyOS as the operator of:

- citizen applications or administrative cases;
- individual eligibility, entitlement, risk scoring or sanctions;
- appeal or court adjudication;
- legally effective notice delivery;
- payments, settlement or compensation execution;
- vendor selection, contracting or procurement execution;
- staff scheduling or service delivery;
- institution-wide records administration;
- sovereign identity provision.

It may test evidence ingestion and PolicyOS-owned claim/public-record reactions to those external acts.

---

# 10. Open Questions For Consolidation

## 10.1 Identity and boundary anchors

1. What is the final wire identity and namespace of `policy_matter_ref`?
2. Can one case attach to several matters at claim/option scope?
3. Which matter split/successor decisions require external competent authority?
4. Where does the final boundary-register version bind to a case and event?
5. Does a mainline blocked administrative attempt count as `attempted` even when prevented, or should the metric distinguish implementation-generated and benchmark-injected probes? This report recommends the distinction used in §6.5.

## 10.2 State and event ownership

6. Which package owns the durable suspension record without widening PDC?
7. Is the wake scheduler part of the control plane or a distinct H2 service?
8. Which existing event envelope should be extended for multi-clock institutional events?
9. How are bitemporal event corrections and event-sourcing history reconciled?
10. Who owns the authority-dependency index and its fleet-scale reverse lookup?

## 10.3 Oracle questions

11. What semantic equivalence function compares incremental and clean rebuild outputs?
12. Which fields are legitimate non-semantic differences?
13. How is adjudicator disagreement scored without majority laundering?
14. What constitutes acceptable ambiguity versus evaluator indecision?
15. How are real legal and institutional competence oracles obtained for pilots?
16. How is third-party cache correction measured when PolicyOS cannot force deletion?

## 10.4 Temporal and release questions

17. Which late-event policies are structurally fixed and which are governed configuration?
18. When does a retroactive event open a new epoch versus only revalidate?
19. How does a governed world head become atomic across stores and surfaces?
20. How is partial fan-out represented while the old head remains public current?
21. What are the final version compatibility rules for dormant cases?

## 10.5 Resilience and preservation questions

22. Which custody classes require zero RPO in the eventual production design?
23. How are audit/public-verification logs reconstructed if CAS and control DB restore at different points?
24. What is the minimum 10–30 year public verification profile before the first real signature?
25. How are cryptographic renewals linked without changing original signed meaning?
26. Who holds recovery authority after hours, and what emergency scope is legitimate?
27. Which 10,000-case fan-out behavior can be tested synthetically without building the deferred fleet scheduler?

## 10.6 Institutional pilot facts

28. Which systems emit appeal outcomes, proof of service, payment settlement and records decisions?
29. What signatures, identifiers and correction channels do those systems expose?
30. Which events are legally effective, advisory, alleged or merely reported?
31. Who is the real after-hours authority for correction and withdrawal?
32. Which public/subscriber notice obligations exist for a specific institution?

## 10.7 Recommended consolidation owner

`team-architecture` should consolidate the Stage-0 vocabulary with:

- the PDC canonical owner;
- future H2 Custody Runtime owner;
- Fabric temporal/release owner;
- Lex legal owner;
- DDM/monitoring owner;
- core audit/security owner;
- Atlas/publication owner;
- PAO-R0, PAO-R1, INT-R1, INT-R5, INT-R7, PAO-R4 and PAO-R36 research owners.

Review should occur before dispatching the remaining Group-B research and whenever a bootstrap anchor is superseded.

---

# Appendix A. Repository Evidence Register

| Repository evidence | Current behavior | Benchmark relevance | Confidence | Missing bridge |
|---|---|---|---|---|
| `core/contracts/control.py` | Four job states: pending/running/completed/failed. | Proves job state is not custody state. fileciteturn17file0 | High | Suspension/wake/revalidation lifecycle |
| Control-plane store | Durable jobs, leases and outbox. | Worker loss, duplicate delivery and recovery seeds. fileciteturn18file0 | High | Matter-aware custody and wake |
| Scientist checkpoint/resume | CAS state, fingerprint, cache and lock compatibility. | Computational resume fixture. fileciteturn22file0 | High | Mandatory authority reproof |
| Fabric watermark | Event-time watermark state. | Late/out-of-order substrate. fileciteturn29file0 | High | Authority-aware late policy |
| Signed cursor | Query-bound/expiring cursor. | Replay and pagination integrity. fileciteturn30file0 | High | Custody event cursor integration |
| Bitemporal service | Valid-at and transaction-at reads. | Historical/current oracle seed. fileciteturn32file0 | High | End-to-end case/public replay |
| Diagnostic event envelope | Producer, tenant, time, state and dedupe fields. | Common event-envelope seed. fileciteturn33file0 | High | Institutional clocks and authority boundary |
| Decision-Validity | Dependency events and status transitions. | Law/data/source/model/metric reaction. fileciteturn34file0 | High | Matter-aware impact orchestration |
| W9 lifecycle bridge | Scoped append-only stale/block/reissue/withdraw transitions. | Claim reaction oracle. fileciteturn37file0 | High | Fleet/matter bridge |
| Case lifecycle | Revision action ordering and public consequences. | State vocabulary seed. fileciteturn38file0 | High | Durable custody state machine |
| Jurisdiction plugins | EU and UA only; unknown falls back to UA. | Mandatory no-fallback kill fixture. fileciteturn44file0 | High | Generic JurisdictionPack |
| Legal batch README | Canonical offline legal pipeline and staged operations. | Living-law fixture source. fileciteturn46file0 | High | Governed weekly release/fanout |
| Amendment detector | Typed legal-change extraction. | Amendment/corrigendum/repeal seed. fileciteturn47file0 | High | Full reference/identity continuity |
| Failure patterns | Capability, authority, replay, time and owner anti-patterns. | Benchmark kill-rule source. fileciteturn51file0 | High | Capstone semantic battery |
| Retention and recovery | Classes, must-retain artifacts and restore drills. | RPO/RTO and runbook-not-proof rule. fileciteturn52file0 | High | Executed custody DR evidence |
| Wave-2 backlog | Explicit Stage-0 capstone and H2 routing. | Task authority and scope. fileciteturn55file0 | High | Benchmark artifact itself |
| PolicyPortfolio ADR | Candidate combinations/search under constraints. | Negative: not deployed stock or custody identity. fileciteturn58file0 | High | Deployed stock interaction future task |
| Core audit | Portable deterministic offline-verifiable archive. | Audit/recovery oracle. fileciteturn60file0 | High | Matter/custody bundle profile |
| Signing tests | Tamper, untrusted, revoked and identity mismatch behavior. | Key and signature fixtures. fileciteturn61file0 | High | Long-term public verification |
| Honest diagnostics | Authority graph, same-input closure and projection-not-authority. | Evidence-chain invariants. fileciteturn71file0 | High | Longitudinal composition |
| Universal vision | B-on-A, narrow waist, one lattice and immutable closed cases. | Architecture constraints. fileciteturn72file0 | High | H2 orchestration |
| GY-N12 plan | Epoch/stale certificate/OpenWorldRisk specified, not closed at inspected commit. | Future world/epoch input. fileciteturn68file1 | Medium-high | Producer and bridge |
| Existing capstone search | Only task/planning references found. | Negative finding: no end-to-end capstone. fileciteturn63file0 | Medium-high | Runner, fixtures and oracles |

# Appendix B. External Source Register

Access date for all sources: **2026-07-26**.

| Source | Type / standing (primary or secondary) | Claim supported | Limitation and PolicyOS delta |
|---|---|---|---|
| Temporal documentation | Primary official product documentation; canonical implementation pattern | Long-lived workflows can resume after crashes and long delays. citeturn152469view0 | Does not re-prove identity or authority; PolicyOS adds resume gates. |
| Apache Beam Programming Guide | Primary official ASF documentation | Event time, watermarks, triggers and late data are distinct. citeturn152469view1 | Does not decide legal/claim materiality; PolicyOS adds typed reaction policy. |
| Build Systems à la Carte | Primary peer-reviewed/formal research | Dependency/incremental behavior can be compared with clean builds. citeturn152469view2 | No authority graph; PolicyOS adds permitted-use dependencies. |
| NIST SP 800-34 | Primary official guidance | Recovery planning includes testing, exercises and maintenance. citeturn587027view0 | Plan existence is not drill success; candidate RPO/RTO are benchmark-only. |
| Principles of Chaos Engineering | Secondary/canonical engineering-practice statement | Controlled real-world failure variables should try to falsify steady-state behavior. citeturn890889search5 | Software steady state is insufficient; PolicyOS defines custody steady state. |
| PREMIS v3 | Primary official preservation standard | Preservation objects/events/agents/rights support custody evidence. citeturn152469view4 | Does not determine current policy authority. |
| RFC 7089 Memento | Primary technical standard (informational) | Historical resource representations can be addressed by datetime and TimeMaps. citeturn587027view4 | Web representation history is not full claim replay. |
| RFC 4998 ERS | Primary standards-track specification | Long-term evidence records support proof of data existence and renewal. citeturn587027view5 | Does not preserve semantic currency by itself. |
| RFC 9162 CT | Primary standards-track specification | Append-only logs and consistency proofs expose equivocation. citeturn587027view6 | Logging does not prevent bad authority; PolicyOS still validates claims. |
| ELI | Primary official interoperability framework | Persistent legal identifiers and metadata support legal version references. citeturn152469view8 | Does not prove domestic applicability or claim impact. |
| Akoma Ntoso | Primary formal standard | Legal works/expressions and structured provisions support amendment/reference fixtures. citeturn152469view9 | Document structure is not policy-matter or competence authority. |
| UK Magenta Book 2026 | Primary official guidance | Pre-registration limits post-hoc selection and requires documented amendments. citeturn587027view8 | Evaluation governance does not confer production authority. |
| NIST ARIA | Primary official evaluation programme | Contextual, repeatable AI risk/impact evaluation is needed. citeturn152469view11 | Not a PolicyOS custody benchmark; provides evaluation posture. |
| NIST statistical evaluation work | Primary official technical publication | Benchmark conclusions need statistical validity and uncertainty. citeturn152469view12 | Synthetic critical invariants remain logical zero-tolerance checks. |
| NIST metamorphic testing | Primary official technical publication | Metamorphic properties support testing when simple gold outputs are insufficient. citeturn152469view13 | Relations must be authority-aware and independently reviewed. |
| NIST AI RMF Core | Primary official voluntary framework | Ongoing governance, monitoring, incidents, roles and third-party contingencies are lifecycle duties. citeturn587027view11 | Does not allocate PolicyOS-specific institutional authority. |
| UK Algorithmic Transparency Recording Standard | Primary official guidance | An operationally accountable SRO and operating team must be identifiable. citeturn587027view12 | Transparency record is not proof of operation or correctness. |
| EU AI Act | Primary legislation | Provider/deployer/oversight/authority roles remain distinct. citeturn152469view15 | Jurisdiction-specific; used only as comparative role separation. |

# Appendix C. Frozen 24-Month Calendar

The calendar is deliberately non-linear. Each row carries the required clocks in compact form: `E` event time, `Eff` legal/semantic effective time, `Pub` publication time, `Obs` observation time, `Adm` admission time, `Proc` processing time and `Tx` transaction time. Unlisted clock values are null or inherited from the fixture envelope.


## 2027-01

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-001 | 2027-01-05 | E/Pub/Obs/Adm 2027-01-05 | ScenarioManifestSealed — benchmark governance (OWN) | Whole scenario; signed manifest, metric and sealed-root commitments | No | Governance baseline | Freeze denominator and thresholds | Post-result edit | Research-only, preregistered | Manifest/hash oracle |
| CCB24-002 | 2027-01-06 | E 01-06; Adm 01-06 | MatterCaseAnchored — PDC identity owner (OWN) | pm:ccb24 matter; pdc-ccb24-001; tenant alpha | No | Identity closure | Bind case without claiming final PAO-R0 contract | Treat case_id as lifetime identity | Internal only | Identity oracle |
| CCB24-003 | 2027-01-08 | E 01-08; Adm 01-08 | InitialWorldReleaseCandidate — Fabric/Lex/RQ (OWN) | Initial legal/data/construct/calibration/rule/validator vector | No | World candidate | Keep shadow pending compatibility | Call latest components governed | No public authority | World-release oracle |
| CCB24-004 | 2027-01-12 | E/Obs/Adm 01-12 | DesignCaseCompiled — GY/PDC (OWN) | MSME resilience design, options, claims, KPI and obligations | No | Case graph | Persist candidate design and provenance | Publish candidate as authority | Reviewer candidate | PDC semantic oracle |
| CCB24-005 | 2027-01-15 | E 01-15; Adm 01-15 | DecisiveMandateGapDetected — RQ/PDC (OWN) | Municipal guarantee and data-use delegation obligation | No | Authority gap | Classify as non-data acquisition gap | Close with additional rows | Acquisition required | Obligation oracle |
| CCB24-006 | 2027-01-17 | E/Tx 01-17 | AcquisitionRequired — PDC (OWN) | Exact obligation, accepted artifact class, VOI/cost path | No | Case terminal | Emit honest terminal, not failure/completion | Promote recommendation | Limited; path visible | Terminal oracle |
| CCB24-007 | 2027-01-18 | E/Tx 01-18 | CaseSuspended — future H2 candidate (OWN) | State, budgets, obligations, deadlines, wake conditions | Scheduled only | Custody state | Commit suspension; release worker/locks | Keep live worker or mark completed | Waiting/acquisition required | Suspension oracle |

## 2027-02

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-008 | 2027-02-10 | E 02-08; Pub 02-09; Obs 02-10; Adm — | PartialEvidenceReceived — municipal secretariat (INTEGRATE) | Draft minutes without final competence/effective date | No | Evidence quarantine | Authenticate then quarantine as incomplete | Wake or close obligation | Unchanged waiting state | Evidence oracle |

## 2027-03

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-009 | 2027-03-05 | E/Pub 03-04; Obs 03-05; Adm — | SimilarArtifactReceived — political press office (INTEGRATE) | Press release describing same programme | No | No authority effect | Reject as non-satisfying look-alike | Treat title similarity as mandate | Unchanged waiting state | Look-alike oracle |

## 2027-04

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-010 | 2027-04-01 | E/Obs 04-01; Tx 04-01 | SourceUnavailable — official source monitor (INTEGRATE) | Municipal registry endpoint | No unless required deadline | Source health | Mark unknown/stale; schedule census | Infer no delegation exists | Waiting; source warning | Availability oracle |
| CCB24-011 | 2027-04-03 | E/Proc 04-03 | WorkerTerminatedDuringSuspension — platform (OWN fault) | No live worker should own suspended case | No | Worker/custody separation | Demonstrate no case-state change | Lose suspension state | Unchanged | Fault oracle |

## 2027-05

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-012 | 2027-05-01 | E 05-01; Exp 2028-06-01 | DataSharingAgreementExpiryApproaching — rights owner (INTEGRATE) | Data-use right supporting monitoring/publication | Yes: expiry watcher | Authority dependency | Schedule renewal evidence and affected-use query | Ignore until runtime error | Current; expiry watch internal/reviewer | Expiry oracle |
| CCB24-013 | 2027-05-05 | E 05-05; Exp 2028-06-05 | ModelLicenseExpiryApproaching — vendor/contract owner (INTEGRATE) | Model reuse/publication rights | Yes: expiry watcher | Authority dependency | Schedule renewal/substitution review | Assume perpetual right | Current; expiry watch | Expiry oracle |
| CCB24-014 | 2027-05-10 | E 05-10; Exp 2027-06-10 | ReviewerCertificationExpiryApproaching — certifier (INTEGRATE) | Reviewer authority required at resume | Yes: expiry watcher | Human authority | Require current certification at gate | Cache old certification indefinitely | Waiting; review dependency visible | Authority oracle |

## 2027-06

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-015 | 2027-06-01 | E 06-01; Pub 06-03; Eff 06-15; Obs 06-07 | DelegationAdopted — municipal council (INTEGRATE) | Exact subject matter, amount, pilot term and data-use authority | Not before admission/effect | Potential obligation closure | Receive and verify legal source | Claim PolicyOS issued delegation | Waiting until effective/admitted | Legal/authority oracle |
| CCB24-016 | 2027-06-17 | E 06-01; Eff 06-15; Obs 06-07; Adm 06-17 | DecisiveDelegationEvidenceAdmitted — Lex/RQ (OWN admission) | Obligation ID bound to authenticated act and competence | Yes: required_artifact_admitted | Authority revalidation and wake | Admit purpose-scoped evidence; emit one wake key | Grant unrelated permissions | Wake pending; not resumed | Admission oracle |
| CCB24-017 | 2027-06-17 | Receipt/Proc 06-17 | TwoWorkersWakeRace — control plane fault (OWN) | Same wake dedupe key and suspension generation | Yes, two contenders | Duplicate-wake control | One resume generation commits; other loses lease | Two resumes or reissues | Wake pending | Concurrency oracle |
| CCB24-018 | 2027-06-17 | Proc/Tx 06-17 | ResumeGateFailedCertificationExpired — H2/PDC (OWN) | Gate 20 human review authority | No successful resume | Human review blocker | Remain suspended; record failed gate | Resume because decisive artifact exists | Waiting; certification blocker | Resume-gate oracle |
| CCB24-019 | 2027-06-20 | E 06-19; Adm 06-19; Proc 06-20 | CertificationRenewedAndCaseResumed — certifier + H2 | Correct certification plus all twenty gates | Yes | Selective impact | Commit CaseResumeReceipt; reuse valid artifacts | Reuse stale/wrong-world artifacts | Revalidating, no public claim yet | Resume oracle |
| CCB24-020 | 2027-06-21 | Proc/Tx 06-20–06-21 | DependencyImpactAndMinimalRecompute — H2/core (OWN) | Artifact and authority graph over current case | No new wake | Payload+authority sets | Reuse valid evidence; recompute only affected branches | Stop authority traversal at unchanged bytes | Revalidating | Clean-build oracle |
| CCB24-021 | 2027-06-25 | E/Adm/Tx 06-25 | HumanDecisionLimitedPilot — mandated principal (INTEGRATE decision; OWN record) | Pilot-only scope; dissent and denied uses preserved | No | Authority decision | Record active informed choice and limited authority | Treat click as broad approval | Limited pilot eligible | Human oracle |
| CCB24-022 | 2027-06-28 | E/Tx 06-28 | WorldReleaseGoverned — release owner (OWN) | Compatible initial version vector | No | Governed head | Atomic head swap; retain shadow/predecessor | Use unverified components | Limited; current world visible | World oracle |

## 2027-07

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-023 | 2027-07-02 | E/Pub/Adm 07-02 | InitialPublicRecordPublished — publication/signing owners (OWN) | PUBLIC/REVIEWER/MACHINE views, compression receipt, signature | No | Public record | Publish limited record with denied individual use | Present as universal or final | published_current: limited | Public/signature oracle |
| CCB24-024 | 2027-07-15 | E/Pub/Obs 07-15; Adm 07-15 | NoticeMessageSent — external notice system (INTEGRATE) | Administrative notice send status only | No | External administrative status | Record reported send; keep service-dependent claim unresolved | Claim legally effective service | External status: sent/unproven | Boundary oracle |
| CCB24-025 | 2027-07-20 | E 07-18; Pub 07-19; Obs/Adm 07-20 | ProofOfServiceIssued — qualified/competent service (INTEGRATE) | Exact notice, recipient class, delivery evidence | If claim depended on proof | Authority revalidation only | Admit narrow proof; update relevant implementation evidence | Claim PolicyOS served notice | Service verified by external producer | Proof-of-service oracle |

## 2027-08

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-026 | 2027-08-05 | E 07-31; Pub 08-03; Obs/Adm 08-05 | ImplementationEvidenceIssued — programme agency (INTEGRATE) | Pilot configuration, capacity and delivery denominator | Yes if material | Feasibility/monitoring | Admit scoped evidence; do not infer individual outcomes | Claim PolicyOS delivered service | Current with reported implementation evidence | Implementation oracle |
| CCB24-027 | 2027-08-15 | E 07-10; Pub 08-12; Obs 08-15; Adm 08-16 | SourceRecordCorrected — data provider (INTEGRATE) | Baseline energy-use records corrected | Yes if consumed | Payload recompute + public review | Append correction, compute affected rows/claims | Overwrite old source snapshot | Current review pending; old snapshot historical | Correction oracle |
| CCB24-028 | 2027-08-20 | Valid from 2027-03-01; Pub 08-18; Adm 08-20 | RetroactiveDataRevisionAndRefresh — data provider/Fabric | Revision changes March–July derived baseline | Yes | Derived recompute, current vs historical split | Recompute material partitions; preserve prior decision replay | Backfill old public meaning silently | Current limited if material; historical unchanged | Bitemporal/clean-build oracle |

## 2027-09

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-029 | 2027-09-01 | E/Pub/Obs 09-01; Adm 09-02 | SourceAuthorityRevoked — source owner (INTEGRATE) | Survey remains byte-identical but no longer authoritative | Yes | Authority revalidation, no required payload recompute | Mark support revoked; downgrade affected claims | Keep current because bytes unchanged | Limited/stale on affected claims | Authority-loss oracle |
| CCB24-030 | 2027-09-20 | E 09-18; Pub 09-19; Adm 09-20 | MetricSchemaChanged — data provider (INTEGRATE) | KPI source fields/units change | Yes | New semantic series/refresh | Open measurement epoch; validate bridge | Splice as same series silently | Monitoring degraded pending bridge | Schema oracle |
| CCB24-031 | 2027-09-22 | E/Pub/Adm 09-22 | ConstructDefinitionChanged — construct owner (OWN governed change) | Energy-vulnerability construct scope changes | Yes | Claim/measurement revalidation | Version construct; identify affected claims | Treat label-only metadata | Limited pending revalidation | Construct oracle |
| CCB24-032 | 2027-09-30 | Exp/E/Obs 09-30; Tx 09-30 | CalibrationExpired — calibration owner (OWN) | Model/KPI calibration validity window ends | Yes | Authority revalidation | Block calibrated-use claims until refreshed | Continue because model payload same | Stale/limited | Calibration oracle |

## 2027-10

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-033 | 2027-10-05 | E/Pub/Obs 10-05 | WorkflowVersionChanged — Scientist owner (OWN) | Dormant/resumed workflow fingerprint changes | At next execution | Migration review | Select original/migrate/compare/refuse mode | Resume under new logic silently | Current state unchanged; execution blocked pending mode | Migration oracle |
| CCB24-034 | 2027-10-06 | E/Pub/Obs 10-06 | ValidatorVersionChanged — validator owner (OWN) | Rule/validator version changes | Yes if affected | Validator compatibility | Run semantic diff and independent validation | Assume newer is safer | Review required | Validator oracle |
| CCB24-035 | 2027-10-10 | Proc/Tx 10-10 | ReplayOldAndNewCompare — H2/PDC (OWN) | Old and new workflow/rule/validator results | No | Migration parity | Persist comparison and authority downgrade if divergent | Rewrite old closure meaning | Current review; historical pinned | Migration/replay oracle |
| CCB24-036 | 2027-10-15 | Pub/Obs 10-15; Adm 10-15 | TranslationAuthorityDiverged — publication QA (OWN finding) | One locale renders limited as confirmed | Yes: correction required | Public notice/correction | Block divergent locale and issue parity correction | Leave other surfaces current | Correction pending on affected locale | Multilingual oracle |
| CCB24-037 | 2027-10-20 | Pub/Tx 10-20 | TranslationCorrected — publication owner (OWN) | All semantic IDs/status/denied uses restored | No | Public correction linkage | Publish correction and archive prior translation | Silent in-place edit | Corrected; prior locale historical | Translation/public oracle |

## 2027-11

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-038 | 2027-11-01 | Adopt 10-20; Pub 11-01; Eff 2028-01-01; Obs 11-02; Adm 11-04 | LegalNormPublished — official gazette (INTEGRATE) | New pilot-governance norm, future effective | Scheduled before effect | Legal dependency | Create shadow legal release and future wake | Apply as current immediately | Current under old law; future change disclosed | Legal-time oracle |
| CCB24-039 | 2027-11-15 | E 11-10; Pub 11-15; Adm 11-16 | LegalNormCorrigendum — official gazette (INTEGRATE) | Corrects cross-reference before effective date | Yes for release rebuild | Legal payload/reference | Correct shadow branch and rebenchmark | Ignore because not effective yet | Current old law; future release corrected | Legal oracle |
| CCB24-040 | 2027-11-20 | E/Pub/Adm 11-20 | CosmeticLegalRenumbering — gazette/Lex (INTEGRATE) | Provision number changes, logic hash stable | No full wake | Annotation only | Update aliases/references; no mass recompute | Invalidate all cases | Current unchanged; annotation available | Legal-diff oracle |

## 2027-12

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-041 | 2027-12-01 | E/Pub/Obs 12-01 | JurisdictionPackUpdateCandidate — Lex pack owner (OWN) | UA pack update and municipal schema candidate | No governed use | Shadow release | Benchmark in shadow | Make candidate current | Current unchanged | Jurisdiction-pack oracle |
| CCB24-042 | 2027-12-10 | E/Pub/Adm 12-10 | NewMunicipalPackGoverned — Lex pack owner (OWN) | UA-MUNI-ALPHA publishers, hierarchy, clocks and competence | Yes if needed | World-release compatibility | Admit pack and create compatible release candidate | Treat pack as proof of every local authority | Current after governed world head only | Pack oracle |
| CCB24-043 | 2027-12-15 | E/Obs/Proc 12-15 | UnknownJurisdictionSubmitted ZZ-01 — external request | Unsupported jurisdiction | No | Jurisdiction block | Return unsupported/blocked and acquisition path | Fallback to UA plugin | Blocked for ZZ-01; existing matter unchanged | No-fallback oracle |
| CCB24-044 | 2027-12-20 | E/Obs 12-20 | SourceEndpointUnavailable — official source (INTEGRATE) | Legal/data source becomes unreachable | Maybe source-recovery watcher | Freshness and availability | Mark source unknown/stale according to TTL | Assume no new amendment | Current with source-health warning/limits | Availability oracle |
| CCB24-045 | 2027-12-31 | Cutoff 12-31; Proc/Tx 12-31 | YearEndHistoricalReplay — core audit/H2 (OWN) | Cutoffs through first public record | No | Replay proof | Reproduce as-known states | Leak later events backward | Historical views available | Replay oracle |

## 2028-01

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-046 | 2028-01-01 | E/Eff 01-01; Obs/Adm 01-01 | LegalNormEffective — official gazette/Lex (INTEGRATE) | Current legal basis and affected claims | Yes | Authority revalidation/world release | Freeze old-law current authority until governed release | Apply unverified latest vector | Revalidation required | Legal-effective oracle |
| CCB24-047 | 2028-01-02 | Proc/Tx 01-02 | LatestOfEachWorldVectorRejected — release gate (OWN) | New law + old data + new calibration + old construct + old validator | No successful resume | Compatibility block | Keep prior governed head | Promote each newest component | Prior world remains current | World oracle |
| CCB24-048 | 2028-01-05 | E/Tx 01-05 | CompatibleWorldReleaseGoverned — release owner (OWN) | Verified legal/data/construct/calibration/rule/validator vector | Yes | Atomic head + affected scope | Swap head and retain predecessor | Delete predecessor tags | Current under new governed world | Release oracle |
| CCB24-049 | 2028-01-10 | E/Proc 01-10 | WorldHeadAdvancedFanoutIncomplete — fault injection (OWN) | Head store advanced; impact queue partially failed | Yes | Public freeze + reconciliation | Prevent new head from appearing fully current; reconcile | Show mixed current states | Verification/current status degraded | Fanout oracle |
| CCB24-050 | 2028-01-12 | Proc/Tx 01-12 | FanoutReconciled — H2/release owner (OWN) | All affected cases/claims/public records processed | No | Close fanout gap | Unfreeze canonical current projection | Ignore missed case | Current under new world | Impact oracle |
| CCB24-051 | 2028-01-20 | E 01-18; Pub 01-19; Adm 01-20 | KPIEarlyWarningIssued — external data/DDM (INTEGRATE) | Leading KPI crosses threshold | Yes: diagnosis | Monitoring/human review candidate | Diagnose definition, data, implementation and causality | Auto-change policy | Current; early warning visible, no adaptation | KPI oracle |
| CCB24-052 | 2028-01-25 | E/Pub/Adm 01-25 | KPIDefinitionRevised — metric owner (INTEGRATE) | Denominator/aggregation definition changes | Yes | New semantic series/epoch | Separate old/new series and refresh contracts | Continue one series silently | Measurement definition changed | Metric-semantic oracle |

## 2028-02

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-053 | 2028-02-01 | E/Tx 02-01 | SigningKeyRotated — security/core audit (OWN) | New signing key; old trust material retained | No | Verification lifecycle | Use new key for new records; historical old signatures verify | Re-sign old records in place | Current verified; historical verified | Key oracle |
| CCB24-054 | 2028-02-10 | E 02-08; Pub 02-10; Adm 02-11 | InstitutionReorganized — competent authority (INTEGRATE) | Programme agency replaced by successor body | Yes | Competence and responsibility review | Observe/ingest succession; revalidate affected authority | Accept old agency indefinitely | Review required; operator changed | Institutional oracle |
| CCB24-055 | 2028-02-15 | Exp/E/Obs 02-15 | DelegationExpired — authority watcher (INTEGRATE) | Old delegation no longer authorizes review/reissue | Yes | Authority loss; public freeze if affected | Block authority-bearing actions and request successor evidence | Continue with cached delegation | Limited/blocked for affected actions | Delegation oracle |
| CCB24-056 | 2028-02-16 | E/Proc 02-16 23:30 | HumanAuthorityUnavailableAfterHours — governance condition | Required competent reviewer unavailable | No successful decision | Human escalation pending | Remain suspended/review_required | Self-approve or use wrong role | Review pending | Human oracle |
| CCB24-057 | 2028-02-19 | E 02-17; Eff 02-17; Pub 02-18; Adm 02-19 | ActingAppointmentAndSuccessorDelegation — appointing body (INTEGRATE) | Acting official, narrow scope and TTL | Yes | Competence revalidation | Admit scope-limited authority; resume allowed only inside it | Treat acting role as unlimited | Limited; authority restored for named actions | Authority oracle |

## 2028-03

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-058 | 2028-03-01 | E 02-25; Pub 02-28; Adm 03-01 | SubgroupHarmDetected — evaluator/DDM (INTEGRATE) | Guardrail harm despite acceptable average result KPI | Yes | Distributional review/public notice | Freeze expansion; human review/narrow-scope analysis | Average away harm | Contested/limited; harm disclosed | Distributional oracle |
| CCB24-059 | 2028-03-05 | E 03-02; Pub 03-04; Adm 03-05 | ImplementationFailureReported — programme agency (INTEGRATE) | Supplier capacity and delivery backlog | Yes | Implementation diagnosis | Separate delivery failure from causal theory failure | Refute causal model automatically | Limited; implementation warning | Diagnosis oracle |
| CCB24-060 | 2028-03-08 | E 03-06; Pub 03-07; Adm 03-08 | MeasurementFailureReported — data provider (INTEGRATE) | Subgroup field missingness/collection change | Yes | Measurement-health block | Freeze affected inference and repair measurement | Treat missing as zero/no harm | Measurement degraded | Measurement oracle |
| CCB24-061 | 2028-03-10 | E 03-01; Obs/Adm 03-10 | BehavioralResponseDetected — DDM/analysis (OWN candidate from external data) | Applicants change reporting after policy launch | Yes | Performativity/identification review | Keep as exploratory candidate; no posterior confirmation | Accept endogenous shift as success | Learning blocked/limited | Causal-safety oracle |
| CCB24-062 | 2028-03-15 | E 03-01; Pub 03-12; Adm 03-15 | BaselinePolicyChanged — another public authority (INTEGRATE) | National energy subsidy changes counterfactual baseline | Yes | Interference/context update | Re-estimate or limit attribution | Ignore other policy | Outcome attribution contested | Interference oracle |
| CCB24-063 | 2028-03-20 | E 03-18; Pub 03-19; Adm 03-20 | IncidentNearMissReported — service operator (INTEGRATE) | Safety near miss in backup-power delivery | Yes | Incident/human/public review | Admit as reported; corroborate; apply downgrade-only pre-adjudication | Declare confirmed root cause or no issue | Incident under review | Incident oracle |
| CCB24-064 | 2028-03-25 | E 03-22; Pub 03-25; Adm — | AppealOutcomeIssued — external appeal body (INTEGRATE) | Appeal changes authoritative factual/eligibility interpretation | Not until admitted | Potential claim/public correction | Receive and verify competence/finality/scope | Claim PolicyOS adjudicated | Current pending admission | Appeal oracle |
| CCB24-064A | 2028-03-26 | E/Pub/Obs 03-26; Adm — | ConflictingAuthoritativeSourcesReceived — appeal body and programme agency (INTEGRATE) | Same policy-level fact has contradictory competent-source assertions | Yes after admission review | Contested authority and human adjudication | Preserve both assertions, resolve competence/finality/scope or remain contested | Average them, choose latest receipt, or silently discard one | Contested/review required | Authority-panel oracle |
| CCB24-065 | 2028-03-27 | E 03-22; Obs 03-25; Adm 03-27 | AppealEvidenceAdmittedAndReissueRequired — RQ/PDC | Specific policy-level claims and public explanation affected | Yes | Authority revalidation/public correction/human review | Compute least-expansive impact and require partial reissue | Execute remedy or alter individual case | Correction pending; contested scope | Appeal/impact oracle |

## 2028-04

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-066 | 2028-04-01 | E/Obs/Tx 04-01 | CorrectionRequestIssued — affected stakeholder (INTEGRATE candidate) | Public record alleges wrong limitation/appeal explanation | Yes if corroborated | Contestability review | Bind request, evidence and recourse pointer; do not assume truth | Silently ignore or auto-adjudicate | Correction review visible | Contestability oracle |
| CCB24-067 | 2028-04-02 | Pub/Tx 04-02 | PublicRecordCorrectedFanout — PolicyOS publication owner (OWN) | Canonical record, API, controlled caches, subscribers, feed, archive, translations; third-party cached copy already exists | No | Public correction | Publish correction/supersession links, controlled cache invalidation and durable third-party notice; do not promise deletion outside control | Edit old record silently or claim every third-party cache was erased | Corrected; prior record historical; external cache notice outstanding | Public-correction oracle |
| CCB24-068 | 2028-04-05 | E/Tx 04-05 | CompensationRecommended — PolicyOS/human recommendation (OWN narrow) | Recommendation based on harm review; no payment status | No | Advisory claim only | Record recommendation and denied-use boundary | Show paid/authorized | Recommendation only | Boundary oracle |
| CCB24-069 | 2028-04-08 | E/Pub/Obs/Adm 04-08 | CompensationAuthorized — external remedy authority (INTEGRATE) | Affected class, amount ceiling, authorization ref | If public claim depends | Authority/status update | Record externally authorized, not paid | Claim PolicyOS authorized or completed payment | Authorized, not paid | Remedy oracle |
| CCB24-070 | 2028-04-10 | E/Pub/Obs/Adm 04-10 | CompensationPaymentInitiated — payment operator (INTEGRATE) | Payment batch initiated | No | External status | Record initiated only | Collapse to paid | Initiated | Payment-stage oracle |
| CCB24-071 | 2028-04-15 | E/Pub/Obs/Adm 04-15 | CompensationPaid — payment operator (INTEGRATE) | Settlement evidence for scoped batch | If claim depends | External execution evidence | Admit paid state with external attribution | Claim PolicyOS paid | Paid by external authority | Payment oracle |
| CCB24-072 | 2028-04-20 | E/Pub/Obs/Adm 04-20 | CompensationReconciled — finance authority (INTEGRATE) | Reconciliation confirms final scoped amounts | No | Closure evidence | Record reconciled status; retain prior stages | Rewrite authorization/initiation history | Reconciled externally | Reconciliation oracle |
| CCB24-073 | 2028-04-22 | E/Proc 04-22 | IndividualDecisionUseAttempt — external case system (OUT action) | Policy-level model offered as individual eligibility rule | No | Boundary firewall | Deny export/use; emit BoundaryViolationReceipt | Score or determine individual eligibility | Policy-level artifact remains non-individual | PAO-R4 oracle |
| CCB24-074 | 2028-04-23 | E/Proc 04-23 | VendorSelectionAttempt — procurement integration (OUT action) | Request asks PolicyOS to select winning vendor | No | Boundary firewall | Return advisory analysis only or refuse; no selection | Select/sign contract | External procurement only | PAO-R1 oracle |
| CCB24-075 | 2028-04-24 | E 04-18; Pub 04-23; Adm 04-24 | ServiceDeliveryEvidenceReceived — service operator (INTEGRATE) | Delivery counts and backlog evidence | Yes if material | Implementation revalidation | Admit scoped report; do not claim delivery actor | Show PolicyOS delivered service | Reported/verified external delivery | Delivery oracle |

## 2028-05

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-076 | 2028-05-01 | E 2028-02-28; Pub 04-25; Obs/Adm 05-01 | LateEventAfterClosedWindow — data provider (INTEGRATE) | Material February implementation revision arrives late | Yes | Typed late-event policy | Select recompute_if_material or mandatory_revalidation; preserve old cutoff | Ignore or silently rewrite | Current review; historical unchanged | Late-event oracle |
| CCB24-077 | 2028-05-02 | Same underlying E; duplicate receipt 05-02 | DuplicateEvent — transport retry (INTEGRATE) | Same semantic dedupe key as event 76 | No new wake/action | Dedupe | Record duplicate receipt; no second irreversible action | Create second reissue/correction | Unchanged | Idempotency oracle |
| CCB24-078 | 2028-05-03 | Correction event 05-03; original expected later | CorrectionBeforeOriginal — out-of-order transport | Unknown original event ID at receipt | No | Quarantine/order resolution | Hold correction pending original/corroboration | Apply to arbitrary nearest event | Unchanged; evidence quarantined | Out-of-order oracle |
| CCB24-079 | 2028-05-10 | E 04-30; webhook lost; census Obs 05-10; Adm 05-11 | LostWebhookFoundByCensus — source census (INTEGRATE) | Missed source correction/incident event | Yes | Missed-wake and impact | Ingest with original clocks; evaluate lateness/materiality | Use census time as event time | Current may revalidate; history preserved | Census oracle |
| CCB24-080 | 2028-05-15 | E/Obs 05-15 | SourceRecovered — source monitor (INTEGRATE) | Official source returns with continuity evidence | Yes if stale dependency | Freshness/reconciliation | Reconcile gap interval and missed records before current use | Assume uninterrupted source | Source recovered pending reconciliation | Recovery oracle |

## 2028-06

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-081 | 2028-06-01 | Exp/E/Obs 06-01 | DataSharingAgreementExpired — rights owner (INTEGRATE) | Current monitoring/reuse right ends | Yes | Authority loss/public-use review | Block affected collection/reuse/publication; retain historical evidence per rights | Continue because data bytes exist | Limited/blocked for affected use | Rights oracle |
| CCB24-082 | 2028-06-05 | Exp/E/Obs 06-05 | ModelLicenseExpired — license owner (INTEGRATE) | Model execution/publication right ends | Yes | Authority dependency | Stop prohibited current use; invoke substitution/renewal path | Continue model execution | Limited/blocked | License oracle |
| CCB24-083 | 2028-06-10 | Exp/E/Obs 06-10 | ReviewerCertificationExpired — certifier (INTEGRATE) | Reviewer loses current qualification | Yes if review due | Human authority | Prevent approval/reissue until valid reviewer | Accept existing session/role | Review blocked | Certification oracle |
| CCB24-084 | 2028-06-15 | E/Pub/Obs 06-15 | ValidatorDefectDiscovered — independent challenger (OWN governance evidence) | Validator false-passed a class of missing obligations | Yes | Authority revalidation/mass impact | Mark validator unsound; freeze affected authority | Let validator self-clear | Current records potentially stale | Validator oracle |
| CCB24-085 | 2028-06-16 | E/Obs/Adm 06-16 | PreviouslyUnresolvedObligationDiscovered — challenger (INTEGRATE/OWN admission) | Decisive supplier-safety obligation absent at closure | Yes | Open-world coverage and human review | Add obligation via append-only delta; identify affected cases | Hide because case was closed | Revalidation required | Obligation oracle |
| CCB24-086 | 2028-06-17 | Proc/Tx 06-17 | ValidatorOmittedDecisiveObligation — governance finding (OWN) | Old δ/coverage claim no longer supportable | Yes | Authority loss; public notice | Invalidate conditional completeness claim; recompute/review | Keep risk≤δ headline | Stale/limited; correction pending | P29 mutation oracle |
| CCB24-087 | 2028-06-20 | E/Proc 06-20 | MassInvalidation10k — synthetic fleet fault | 10,000 cases depend on validator/obligation | Yes, deduped/prioritized | Backpressure, public freeze scopes | Enqueue complete affected set with dedupe and priority | Drop cases or issue duplicate actions | Affected public records frozen/stale | Fleet impact oracle |
| CCB24-088 | 2028-06-21 | Proc/Tx 06-21 | BackpressureAndPublicFreezeApplied — H2 candidate (OWN) | Fleet queue and controlled public surfaces | No | Safe degraded mode | Preserve correctness, expose backlog and affected scope | Show unprocessed cases current | Stale/freeze scope visible | Mass-fanout oracle |

## 2028-07

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-089 | 2028-07-01 | E/Eff/Pub 07-01; Adm 07-02 | PolicyMatterSplitOrSuccessorAsserted — competent authority (INTEGRATE) | National successor and municipal residual branch | Yes | Identity/scope/human review | Create candidate child/successor refs; preserve parent history | Collapse or copy all authority | Identity contested/review required | PAO-R0 oracle |
| CCB24-090 | 2028-07-03 | Proc/Tx 07-03 | ChildAuthorityInheritanceBlocked — PDC/RQ (OWN) | Evidence/claims scoped to parent population/mechanism | No | Scope review | Require explicit evidence transport and authority per child | Inherit all parent evidence automatically | Children limited/blocked pending review | Lineage/authority oracle |
| CCB24-091 | 2028-07-15 | Signature from 2027-07-02 still verifies; Obs 07-15 | CryptographicallyValidButSemanticallyStale — public verifier/PDC | Old public record after appeal, obligation and split changes | Yes: public correction check | Public/authority state | Show historically verified but not current | Show green Current Verified | Superseded/stale, historically verified | Signature-semantic oracle |

## 2028-08

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-092 | 2028-08-01 | E 07-25; Pub 08-01; Eff 08-15; Adm 08-02 | LegalAmendmentChangesException — official gazette (INTEGRATE) | New exclusion affects subgroup eligibility principles | Yes | Mandatory affected-scope revalidation | Build shadow legal release; review policy-level rule | Treat as cosmetic | Correction/reissue may be required | Legal exception oracle |
| CCB24-093 | 2028-08-15 | E 08-10; Pub 08-15; Eff 2028-10-01; Adm 08-16 | LegalRepealPublished — official gazette (INTEGRATE) | Current enabling basis scheduled to end | Scheduled before effect | Future authority loss/public planning | Schedule mandatory revalidation and public notice before effect | Withdraw history immediately or ignore future repeal | Current until effective with future warning | Legal-time oracle |

## 2028-09

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-094 | 2028-09-01 | E/Obs 09-01 08:00 | SigningKeyCompromised — security (OWN incident) | Current signing key compromise | Yes | Verification/public freeze/incident | Revoke key, stop signing, expose degraded current verification | Continue signing or erase old records | Verification degraded; current issuance stopped | Key-compromise oracle |
| CCB24-094A | 2028-09-01 | E/Tx 09-01 08:05 | PublicVerificationKeyRevoked — security/trust owner (OWN) | Revocation entry, affected current signatures and archival verification path | Yes | Verification-state and public-record review | Publish revocation, switch current verifier state, preserve historical evidence path | Continue to show current verified or make history unverifiable without disclosure | Current verification degraded; historical verification separately evaluated | Key-revocation oracle |
| CCB24-095 | 2028-09-02 | E/Proc 09-02 | ForgedPacketAndRevokedKeyFixture — malicious producer | Forged current packet under compromised/revoked key | No authority wake | Reject/quarantine/security incident | Reject packet; retain forensic evidence | Display verified or admit claim | No current authority | Cryptographic oracle |
| CCB24-096 | 2028-09-10 | E/Proc 09-10 | WorkerTerminatedDuringRecompute — platform fault (OWN) | In-flight recomputation after mass/legal changes | Retry by durable state | Execution recovery | Retry idempotently from committed boundary | Lose or double-commit results | Current remains frozen until completion | Worker fault oracle |
| CCB24-097 | 2028-09-11 | E/Obs 09-11 | ControlDatabaseUnavailable — platform fault (OWN) | Custody control store unavailable, CAS intact | No unsafe action | Degraded custody | Stop writes/wakes; serve bounded historical/read-only state | Execute from stale local memory | Current status degraded/frozen | DR oracle |
| CCB24-098 | 2028-09-12 | Restore 09-12 | CASRestoredControlDBNot — recovery fault | CAS is present but control history unavailable | No | Partial recovery | Do not infer current head or resume cases | Treat CAS alone as complete custody | Verification/history available; current custody unavailable | Recovery oracle |
| CCB24-099 | 2028-09-13 | Restore 09-13 | ControlDBRestoredCASIncomplete — recovery fault | Control rows reference missing CAS objects | No | Integrity block | Detect missing objects; quarantine affected state | Mark jobs complete from rows alone | Affected records unavailable/degraded | Recovery oracle |
| CCB24-100 | 2028-09-14 | E/Proc 09-14 | MalformedRecoveryEvent — fault operator | Wrong tenant/hash/schema recovery signal | No | Reject + audit | Reject event and preserve partial recovery state | Apply recovery blindly | Unchanged degraded state | Recovery-event oracle |
| CCB24-101 | 2028-09-15 | Restore/Adm/Tx 09-15 | BackupRestoredAndReconciled — platform/H2 (OWN) | Control DB, CAS, outbox, heads and audit chain | Required reconciliation wake | Recovery impact | Reconcile dedupe, heads, fan-out and public state within RPO/RTO | Resume before reconciliation | Current only after reconciliation | Fault-recovery oracle |
| CCB24-102 | 2028-09-16 | Cutoff replay Proc 09-16 | HistoricalReplayMismatchDetected — evaluator (OWN) | One historical projection differs from oracle | No current promotion | Benchmark block | Mark run blocked; diagnose without editing oracle/history | Accept approximate replay silently | Research run blocked; public custody unchanged | Replay oracle |
| CCB24-103 | 2028-09-20 | Proc deadline 09-20 | CleanRebuildUnavailableWithinTarget — fault/scale | Current clean rebuild misses candidate RTO | No | Resilience warning/block by class | Keep current state frozen/degraded; continue rebuild | Declare incremental result correct without oracle | Verification degraded | Clean-build oracle |
| CCB24-104 | 2028-09-25 | Proc/Tx 09-25 | CleanRebuildCompleted — evaluator/core | Rebuild from frozen current corpus/world/rules | No | Parity comparison | Compare semantic, authority and public states | Compare only payload bytes | Current may unfreeze if parity passes | Clean-build oracle |

## 2028-10

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-105 | 2028-10-01 | Eff/E/Obs/Adm 10-01 | LegalRepealEffective — official gazette/Lex (INTEGRATE) | Enabling authority ends | Yes | Freeze current legal/applicability claims | Mandatory revalidation; prepare reissue/supersession/withdrawal | Continue old authority or rewrite history | Current record stale/withdrawal pending | Legal oracle |
| CCB24-106 | 2028-10-02 | Proc/Tx 10-02 | FinalHumanReviewRequired — PDC/H2 (OWN) | Choose scoped reissue/supersession/withdrawal under current evidence | No automatic final | Human decision | Present full packet, dissent, consequences and denied uses | Auto-select best-looking action | Review pending | Human oracle |
| CCB24-107 | 2028-10-05 | E/Adm/Pub/Tx 10-05 | FinalPartialReissueSupersessionWithdrawal — human/PDC/publication | Unaffected empirical claims reissued; old record superseded; legal claim withdrawn | No | Final current/public transition | Publish append-only lineage and preserve every prior state | Mutate old record or over-withdraw unaffected claims | New limited record current; old superseded/withdrawn by scope | Final semantic/public oracle |
| CCB24-108 | 2028-10-06 | Pub/Tx 10-06 | HistoricalArchiveAndVerificationLinked — core audit (OWN) | Old signatures, keys, records, reasons and replay materials | No | Historical-only preservation | Provide archive/time links and verification status | Delete superseded evidence | Historical records verifiable | Archive oracle |

## 2028-11

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-109 | 2028-11-01 | E/Obs 11-01 | WrongMatterAssociationCorrectionRequest — stakeholder/records review | One public record attached to parent instead of child/successor | Yes | Identity/authority/public review | Open matter-association adjudication; freeze aggregation if material | Move record silently | Correction pending | Identity oracle |
| CCB24-110 | 2028-11-10 | E/Adm/Pub/Tx 11-10 | MatterProjectionCorrected — PDC/publication (OWN) | Current association corrected; original remains historical | No | Public correction/impact | Supersede association and recheck dependent claims | Rewrite old signed packet | Corrected current view; original historical | PAO-R0/public oracle |

## 2028-12

| Event ID | Process/observation date | Clock summary | Event, producer and boundary | Matter/case scope and evidence | Expected wake | Expected impact | Expected PolicyOS action | Prohibited action | Expected public posture | Oracle |
|---|---|---|---|---|---|---|---|---|---|---|
| CCB24-111 | 2028-12-01 | Cutoffs 2027-01-18/07-02/2028-01-05/04-02/09-15/12-01 | FinalMultiCutoffReplay — core audit/H2 | All declared historical/current cutoffs | No | Replay evidence | Reproduce each as-known state and current corrected view | Use current facts in old replay | Historical and current views coexist | Replay oracle |
| CCB24-112 | 2028-12-05 | Fault drill 12-05 | FinalDisasterRecoveryDrill — fault operator/platform | Published/current, incident, legal release and verification-log classes | No | DR evidence | Execute restore/reconcile and record RPO/RTO/public posture | Submit runbook as evidence | Benchmark result pending | Fault oracle |
| CCB24-113 | 2028-12-10 | Proc/Tx 12-10 | CapstoneRunReceiptIssued — independent evaluator | Full registered event/fault/metric denominator | No | Evaluation record | Compute all metrics from raw receipts | Hand-author pass report | Research verdict pending | Metric oracle |
| CCB24-114 | 2028-12-15 | E/Tx 12-15 | IndependentReviewAndDisputeResolution — panel | Semantic, authority, public, fault and governance results | No | Adjudication | Preserve dissent and unresolved items | Average away authority defect | Bounded result with limits | Human-review oracle |
| CCB24-115 | 2028-12-20 | E/Pub/Tx 12-20 | FinalBoundedBenchmarkVerdict — result approver | Scenario v1.0.0 only | No | Research conclusion | Issue pass/blocked/invalid verdict with limitations | Claim production readiness or legal compliance | Research-only result | Governance oracle |

# Appendix D. Actor And Boundary Registry

This appendix is the compact machine-oriented projection of §4.2. It is provisional and consumes PAO-R1 assumptions.

| Actor ID | Real institution/system | Lifecycle | Authority basis | Boundary class | Allowed actions in the capstone | Prohibited PolicyOS claims |
|---|---|---|---|---|---|---|
| `policyos.pdc` | PDC narrow waist | Epistemic | PolicyOS internal contract authority | OWN | Bind claims, cases, matter refs, boundaries and decisions | Raw external/engine output is authoritative |
| `policyos.runtime_quality` | Admission/grounding ring | Epistemic | Internal admission rules and verifier provenance | OWN | Resolve, bind, verify, downgrade, quarantine and admit | It performed the external act |
| `policyos.h2_candidate` | Future custody process | Custody | Ratified custody promise; future governed contract | OWN candidate | Suspend, watch, wake, gate, impact, revalidate and schedule | It administers cases, notices, appeals, payments, procurement or delivery |
| `policyos.fabric` | Data plane | Epistemic/data | Source contracts and runtime evidence rules | OWN/INTEGRATE split | Persist snapshots, watermarks, quarantine and releases | It collected external data unless it actually did |
| `policyos.lex` | Legal sensing | Epistemic/legal | Legal-source and competence adapters | OWN sensing / INTEGRATE acts | Authenticate, version and evaluate legal evidence | It enacted, repealed or adjudicated law |
| `policyos.ddm` | Monitoring/incident diagnostics | Epistemic | Monitoring and diagnostic contracts | OWN diagnosis / INTEGRATE observations | Detect and route typed signals | It changed real policy automatically |
| `policyos.audit` | Audit/signing/verification | Public/custody | Core audit and cryptographic contracts | OWN | Package, sign, verify, preserve and expose evidence | Signature proves current semantic authority |
| `policyos.atlas` | Public/reviewer surfaces | Public records | Projection contracts only | OWN projection | Render canonical current/historical status | A UI state is evidence or authority |
| `human.principal` | Mandated reviewer/board | Institutional | Valid identity, mandate, role, TTL, evidence exposure | INTEGRATE authority / OWN decision record | Approve, limit, reject or revise within scope | A bare click or wrong-role approval is valid |
| `external.council` | Municipal council | Institutional/legal | Jurisdiction-specific public authority | INTEGRATE | Issue mandate, delegation and local act | PolicyOS issued or guaranteed legal effect |
| `external.gazette` | Official publisher | Legal/public | Official publication mandate | INTEGRATE | Publish act, amendment, corrigendum, repeal | Publication alone proves claim applicability |
| `external.program_agency` | Programme administrator | Administrative/implementation | Statute/mandate/appropriation | INTEGRATE | Configure and operate programme; emit evidence | PolicyOS operated citizen cases or delivery |
| `external.data_provider` | Statistical/admin source | Evidence | Source mandate and data agreement | INTEGRATE | Publish data, schema and revisions | Missing report proves no event |
| `external.notice_system` | Notice/trust service | Administrative | Applicable notice/service law | INTEGRATE | Send notice and produce proof-of-service | PolicyOS served notice; “sent” equals service |
| `external.appeal_body` | Appeal forum | Administrative/legal | Statute/mandate and case jurisdiction | INTEGRATE | Adjudicate and issue outcome | PolicyOS decided appeal merits |
| `external.payment_authority` | Treasury/payment operator | Finance/administrative | Fiscal and payment authority | INTEGRATE | Authorize, initiate, settle, reconcile | PolicyOS paid compensation |
| `external.procurement_authority` | Contracting body | Implementation/finance | Procurement mandate | INTEGRATE | Select vendor, award and manage contract | PolicyOS selected or contracted vendor |
| `external.service_operator` | Delivery network | Implementation | Service contract/mandate | INTEGRATE | Deliver service and report execution | PolicyOS delivered service |
| `external.records_authority` | Records/privacy/legal office | Public records | Records schedule, law, hold/disclosure authority | INTEGRATE | Retain, disclose, hold or transfer institutional records | PolicyOS owns whole-institution records management |
| `external.identity_provider` | Sovereign/institutional IdP | Institutional/security | Trust framework and assurance profile | INTEGRATE | Assert identity/representation | Identity proves mandate or eligibility |
| `external.cloud_provider` | Infrastructure provider | Infrastructure | Service contract | INTEGRATE | Operate infrastructure and emit incident/recovery evidence | Provider uptime proves PolicyOS custody correctness |
| `malicious.producer` | Untrusted/compromised source | Any | None until independently verified | OUT_OF_SCOPE for authority | Submit candidate material that may be quarantined | Submission, signature shape or confidence grants authority |

After-hours absence never transfers an external institution’s authority to PolicyOS. The safe response is suspension, limitation, block or escalation.

# Appendix E. Event-Type Dictionary

| Event family | Real producer/owner | Boundary | May wake? | Permitted PolicyOS reaction | Prohibited use |
|---|---|---|---|---|---|
| Legal publication/effect/correction/repeal | Official gazette and competent legal body | INTEGRATE | Yes, depending on effective scope | Build shadow/governed legal release; revalidate affected claims | Claim PolicyOS enacted/adjudicated law |
| Data revision/schema/source correction | External data producer; Fabric admission | INTEGRATE | Yes if consumed/material | Correct, refresh, recompute and preserve historical vintage | Treat receipt date as event date or overwrite prior state |
| Construct/rule/validator/calibration change | Governed internal owner or independent challenger | OWN/INTEGRATE by source | Yes | Open epoch, revalidate, migrate, block or limit | Assume newer version is automatically stronger |
| Institution/delegation/appointment/certification | Competent institutional authority | INTEGRATE | Yes | Re-prove competence and action scope | Transfer authority from title/name similarity |
| KPI/monitoring/incident | External source + DDM/RQ | INTEGRATE observation; OWN diagnosis | Yes | Diagnose, limit, review, acquire evidence | Threshold auto-changes policy or confirms causality |
| Appeal/correction/remedy | Appeal/remedy body | INTEGRATE | Yes after admission | Revalidate/correct/reissue/supersede/withdraw own claims | Adjudicate appeal or execute remedy |
| Notice/proof of service | External notice/trust service | INTEGRATE | Only if a PolicyOS claim depends on it | Admit narrow delivery evidence or remain limited | “Sent” equals legally served; PolicyOS is channel |
| Compensation/payment | Remedy and payment authorities | INTEGRATE | Only if a PolicyOS claim depends on stage | Preserve recommended/authorized/initiated/paid/reconciled distinctions | Collapse stages or claim PolicyOS paid |
| Matter split/successor | Competent authority + PDC identity adjudication | INTEGRATE/OWN split | Yes | Preserve parent history; review child evidence/authority | Copy unrestricted parent authority |
| Public correction/signature/key | PolicyOS publication/security owner; external trust inputs as needed | OWN | Yes | Correct, supersede, withdraw, rotate/revoke, archive | Edit history or equate crypto validity with current semantic validity |
| Source/license/right expiry | Rights/contract issuer; custody watcher | INTEGRATE/OWN watcher | Yes | Pre-expiry review, block affected use after expiry | Continue because bytes or credentials still work |
| Worker/store/CAS/fan-out/recovery | Platform/H2 | OWN for PolicyOS custody | Yes where recovery/reconciliation required | Enter degraded state, restore, reconcile, prove RPO/RTO | Execute from partial/stale state or count runbook as proof |
| Administrative case/procurement/delivery action request | External operational system | OUT_OF_SCOPE execution | No legitimate execution wake | Refuse or return bounded analysis/evidence interface | Perform the institutional act |

Every event is admitted for a declared purpose. No event type carries global authority.

# Appendix F. Fault-Injection Matrix

Candidate RPO/RTO values are inherited from §4.16 and remain research targets.

| Fault | Injection point | Expected detection | Expected custody response | Candidate RPO / RTO | Public effect | Recovery oracle |
|---|---|---|---|---|---|---|
| Killed worker during execution | After recompute starts, before commit | Lease expiry/heartbeat and incomplete generation | Retry idempotently from last committed boundary | 0 committed events / 1 h | Current record remains frozen | One committed result; no lost/duplicate state |
| Killed worker during suspension | No worker should be active | Worker census | No case-state change | 0 / N/A | Unchanged waiting state | Suspension state hash identical |
| Duplicate worker | Same wake key claimed twice | Lease/CAS/dedupe conflict | One resume generation commits | 0 / 1 h | No duplicate public transition | One receipt/action per key |
| Corrupted snapshot | CAS blob or checkpoint hash | Integrity verification | Quarantine; recover from retained good object | 0 / 4 h | Affected record unavailable/degraded | Hash-valid restored snapshot and audit trail |
| Missing CAS object | Control record points to absent content | Dereference/integrity census | Block resume/public current; recover or mark historical gap | 0 / 24 h | Degraded/unavailable, never current verified | All refs resolve or affected state explicitly blocked |
| Stale control database | Restore DB behind CAS/head | Version/head reconciliation | Do not process new wakes until reconciled | 0 / 4 h | Previous known public head or frozen state | No lost event; current head equals oracle |
| Control DB unavailable | Runtime access | Health check/write failure | Read-only bounded service; stop writes/wakes | 0 / 4 h | Current status degraded/frozen | Restored DB plus outbox/dedupe reconciliation |
| CAS restored, DB absent | Partial restore | Cross-store census | No inference of current process state | 0 / 8 h | Historical artifacts may verify; current custody unavailable | DB restored and references reconciled |
| DB restored, CAS incomplete | Partial restore | Missing-object scan | Block affected rows and publication | 0 / 24 h | Explicit degraded/unavailable state | Required objects restored or honest permanent gap |
| Malformed evidence | Admission port | Schema/content-bind/provenance validation | Reject/quarantine; no wake | 0 / immediate | No public change | Rejection receipt; no authority transition |
| Forged signature | Public/evidence verifier | Signature/trust/identity check | Reject and open security incident | 0 / immediate | Never verified | Forged packet excluded; forensic record retained |
| Revoked key | Verification path | Trust/revocation lookup | Stop current verification/signing; show historical/degraded status | 0 / 4 h | Verification degraded, not falsely current | Correct status across all surfaces; archival proof retained |
| Source outage | Lex/Fabric connector | Source monitor/TTL | Unknown/stale; schedule census/recovery | 0 admitted events / source-class target | Visible source-health limitation if material | Gap interval reconciled before current reuse |
| Official source disappears | Legal/evidence source | Census and failed authentication | Preserve prior source; block new-current claims needing freshness | 0 / 24 h triage | Legal/source freshness warning or freeze | Archived source verifies; no invented update |
| Lost webhook | Ingestion transport | Periodic census | Ingest with original clocks; apply late policy | 0 / census interval | Possible revalidation/correction | Missed-wake rate remains zero after census deadline |
| Duplicate event | Ingestion/outbox | Dedupe key and semantic identity | Record duplicate receipt; no second effect | 0 / immediate | None | One irreversible action |
| Out-of-order correction | Transport | `correction_of` unresolved | Quarantine until original or adjudication | 0 / 24 h triage | None until resolved | Correct relation and clocks preserved |
| Wrong tenant | Event/evidence/resume state | Tenant closure gate | Security block; no cross-tenant read/write | 0 / immediate | None | No affected state outside source tenant |
| Wrong jurisdiction | Admission/release | Jurisdiction/pack gate | Block or context-only; never fallback | 0 / immediate | Unsupported jurisdiction shown honestly | Fallback violation rate zero |
| Expired delegation | Resume/human action | Authority watcher/gate | Suspend/block action; request current evidence | 0 / immediate | Limited/review required | No authority-bearing action under expired delegation |
| Expired license/right | Execution/publication | Dependency watcher | Stop prohibited use; substitution/renewal path | 0 / immediate | Limited/withdrawn use as required | No use after expiry; history retained |
| Incompatible workflow | Dormant resume | Fingerprint/compatibility gate | Original environment, migrate/compare or refuse | 0 / 24 h review | Current public state unchanged/frozen | Migration parity or explicit refusal |
| Incompatible/unsound validator | Promotion/revalidation | Governance/version/defect event | Freeze affected authority; independent repair | 0 / immediate | Stale/correction pending | Validator fault detected; missed obligation surfaced |
| Incomplete world fan-out | After head swap | Queue/head/surface census | Freeze new public head; reconcile all affected cases | 0 / 4 h critical | Mixed current state prohibited | Impact recall 1.0; surfaces consistent |
| Partial release | Component released without vector | Compatibility matrix | Keep candidate/shadow | 0 / immediate | Old governed release remains current | No latest-of-each current state |
| Mass invalidation | Authority event affects 10,000 cases | Reverse-dependency query | Dedupe, prioritize, backpressure and public-freeze scopes | 0 / class-specific | Affected scope visibly stale/frozen | No missed cases or duplicate actions |
| Public-cache persistence | Controlled cache/subscriber not updated | Surface crawler/fan-out ledger | Retry controlled invalidation and durable correction feed | 0 / 4 h controlled surfaces | Corrected status or explicit stale banner | Controlled completeness 1.0; third-party notice recorded |
| Failed translation update | Locale projection | Semantic-ID parity checker | Block locale; issue correction | 0 / immediate | Locale unavailable/correction pending | No authority-semantic divergence |
| Missing human reviewer | Required review | Availability/decision due clock | Remain suspended or blocked | 0 / until authorized reviewer | Review pending | No automatic or wrong-role decision |
| Audit right expiry | Supplier dependency | Expiry watcher | Downgrade supplier evidence; freeze affected use | 0 / immediate | Limitation disclosed if material | No current claim relying on expired audit right |
| Credential expiry | Connector/provider | Expiry watcher/auth failure | Scheduled renewal; fail closed at expiry | 0 / immediate | Source unavailable/stale | No sudden silent fallback or fabricated evidence |
| Partial recovery | Any subset of CAS/DB/heads/audit | Cross-store reconciliation | Serve only provable bounded state | 0 / custody-class target | Degraded, never falsely current | Final reconciled graph matches oracle |
| Historical replay mismatch | Replay evaluator | Semantic/authority/public diff | Block benchmark and affected migration/release | N/A / immediate block | No change to real public state from failed test | Exact or accepted-tolerance parity after repair/new version |
| DR runbook without drill | Governance closeout | Missing execution receipt | Mark `verification_missing`; benchmark cannot pass | N/A | No production/DR claim | Executed drill evidence required |


# Appendix G. Oracle Checkpoints And Expected Current States

| Cutoff | Historically knowable state | Current-at-cutoff public state | Later facts forbidden from replay |
|---|---|---|---|
| 2027-01-18 | Design exists; decisive delegation obligation unresolved; case suspended | `acquisition_required`, waiting with path | Later delegation, public record, legal changes, appeal, harm |
| 2027-07-02 | Delegation admitted, certification renewed, limited human decision, initial governed world | Initial signed record `published_current: limited` | Source correction/retraction, new norm, KPI harm, appeal |
| 2027-12-31 | Data/source/construct/calibration/workflow changes known; future norm published; municipal pack governed | Limited/current with disclosed stale/review items under old effective law | 2028 legal effect, harm, appeal, split, repeal |
| 2028-01-05 | New norm effective and compatible world release governed | Revalidated/limited under new world | Later institution change, subgroup harm, appeal, repeal |
| 2028-04-02 | Appeal admitted; correction and partial reissue path known | Corrected/contested/limited record; prior record historical | Later validator defect, mass invalidation, split, key compromise |
| 2028-09-15 | Obligation/validator defects, mass invalidation, split, amendment, key compromise and recovery known | Current issuance/verification degraded or frozen until reconciliation | Repeal effective and final resolution |
| 2028-10-06 | Repeal effective; final partial reissue/supersession/withdrawal published | New limited record current; prior record superseded/withdrawn by scope | Later matter-association correction |
| 2028-12-20 | All corrections and matter association adjudications included | Final bounded current view plus complete historical chain | None within scenario |

For each cutoff, the replay oracle compares claim meaning, evidence state, authority boundary, public posture, matter/case attachment, world release, rule/validator versions and visible limitations.

# Appendix H. Failure-Pattern Pass

| Pattern | Scenario witness | Unsafe behavior | Expected signal/metric | Coverage posture |
|---|---|---|---|---|
| P01 contract-only capability | Suspension/world release/public correction sketches | Declare custody implemented because schemas exist | Missing producer/bridge/consumer/run receipt | **Detected**; report remains research-only |
| P02 mature fragments without bridge | Control plane + Scientist + Decision-Validity + W9 coexist | Each component passes alone, no longitudinal reaction | Capstone trace or affected-case parity fails | **Central benchmark target** |
| P03 internal state no surface | Stale/withdrawn state not shown in one Atlas surface | Operator/public sees old current status | `stale_public_shown_as_current`, cross-surface consistency | **Detected** |
| P04 status proliferation | Separate case/evidence/public/world states | New local status acts as second authority lattice | Composition/public oracle mismatch | **Reduced** by explicit non-authority state machines |
| P05/P15 authority dilution and LLM laundering | Similar artifact, dashboard, narrative appeal, generated summary | Candidate/projection satisfies authority | Unauthorized upgrade, false wake, overclaim | **Detected** |
| P07 replay gap | Migration, correction, replay cutoffs | Old case replayed under current rules/facts | Historical replay mismatch | **Detected** |
| P08 time-role conflation | Published-before-effective norm; retro revision; late event | Receipt/publication/effective time collapsed | Late-policy/legal oracle failure | **Detected** |
| P09 warning lifecycle gap | DSA/license/delegation/certification expiry | Surprise runtime failure or ignored warning | Authority-loss detection and expiry fixtures | **Detected** |
| P10 structural-only validation | Schemas present but wrong scope/authority | Green shape, false semantic result | Clean-build/authority/public oracle red | **Detected** |
| P11 failure-only memory | Scenario includes confirmations, valid reuse and successful recovery as well as faults | Learning stores only anomalies | Balanced fixture/adjacent-case review | **Reduced**, not fully solved |
| P12 producer handshake gap | External event emitted without exact claim/matter/clock binding | Meaning resolved after emission | Evidence-binding correctness <1 | **Detected** |
| P13 institutional scope inflation | Notice, appeal, payment, vendor and individual-decision traps | H2 becomes ERP/administrator | Boundary-action/overclaim kill | **Detected; identity decision is firewall** |
| P14 evidence inflation | Corrected/reissued source copies | Count duplicates as corroboration | Mutation/authority oracle mismatch | **Detected** |
| P19 aggregation laundering | Good average with subgroup harm | Average hides affected subgroup | Distributional/public oracle failure | **Detected** |
| P21 capacity laundering | Implementation plan but missing supplier capacity | Design called deliverable | Implementation-capacity evidence gap | **Detected** |
| P24 strategic/performance response | Applicants change reporting; other policy changes baseline | Endogenous shift confirms model | Learning safety fixture | **Detected** |
| P26 responsibility laundering | Expired reviewer/wrong-role/after-hours | Human click launders authority | Human escalation and upgrade kill | **Detected** |
| P27 duplicate owner | New capstone event/status/audit subsystem | Parallel canonical contract family | Owner-map review blocks | **Reduced**; consolidation still needed |
| P28 unstrangled legacy | New H2 path leaves generic resume as default | Old bypass remains callable | Hidden generic-resume probe | **Required future fixture** |
| P29 authorial proof/conditional δ | Validator omitted decisive obligation but markers remain | Hand-authored proof stays green | Validator fault and unresolved obligation metrics | **Detected** |
| P31 instance patching | Only named routes/events guarded | Sibling administrative action bypasses boundary | Hidden action/event variants | **Detected** |
| P32 trust-by-form | Present signed ref, wrong scope/tenant/jurisdiction | Shape/signature grants authority | Resolve-bind-verify fixtures | **Detected** |
| P33 teaching to the test | Code branches on exact event IDs/payloads | Public fixtures pass, variants fail | ID permutation, look-alike and adjacent case | **Detected** |
| P34 uncompleted exclusion | Failed fault declared environment issue without isolation | Denominator shrinks post hoc | No selective exclusion governance check | **Detected** |

The benchmark cannot resolve the open-world completeness problem or jurisdiction-specific legal truth. It can detect implementations that falsely behave as though those questions were closed.

# Appendix I. Stage-0 Custody-Capstone Anchor Packet

This packet is intended for parallel research consumption without importing the entire report.

## I.1 Benchmark identity

```yaml
task: OPS-R15
result: accepted_narrow_scope
calendar: 2027-01-05 to 2028-12-20
scenario: synthetic municipal MSME energy-resilience pilot
policy_matter_ref: external_dependency_assumption
boundary_register: candidate_for_consolidation
implementation_authority: none
```

## I.2 Custody invariant

```text
Current PolicyOS claims must be bound to the correct matter, case, tenant,
jurisdiction, admitted evidence, governed world release, rule/schema/validator
versions and authority boundary.

Past records are never rewritten; current changes are append-only deltas.

External institutional acts remain external; PolicyOS owns only admission,
claim reaction and its own public records.

Incremental current state must equal a clean rebuild, while historical replay
must reproduce what was knowable and admissible at the cutoff.
```

## I.3 Required event envelope

```text
stable id + dedupe key
producer + real operator + boundary class
matter/case + tenant + jurisdiction
multiple clocks
schema/rule/validator/world versions
provenance + content binding
AuthorityBoundary
correction/revocation relation
permitted actions + prohibited uses
```

## I.4 Required wake/resume discipline

A wake condition only opens resume evaluation. Resume requires all twenty gates from §4.8. A generic `resume()` path is a kill.

## I.5 Required impact sets

```text
payload_recompute_set
authority_revalidation_set
public_notice_set
human_review_set
historical_only_set
```

## I.6 Zero-tolerance metrics

```text
lost_case_state = 0
stale_public_shown_as_current = 0
unauthorized_authority_upgrades = 0
silent_historical_rewrites = 0
missed_affected_cases = 0
duplicate_irreversible_actions = 0
out_of_boundary_actions_attempted = 0
external_execution_overclaims = 0
jurisdiction_fallback_violations = 0
invalid_artifact_reuse = 0
```

## I.7 Mandatory oracles

```text
frozen semantic trace
clean rebuild
historical replay
authority and permitted-use panel
public-record state
human-review packet
fault recovery/RPO-RTO
```

## I.8 Non-negotiable administrative traps

PolicyOS must not adjudicate appeals, issue legally effective notices, execute compensation/payments, decide individual cases, select vendors, sign contracts, schedule staff, deliver services or manage citizen cases.

## I.9 Benchmark governance

```text
preregister
hash-commit sealed fixtures
preserve failed runs
version corrections append-only
no case-specific code
no event-ID branching
no post-result threshold edits
no fixture leakage
no selective exclusions
```

## I.10 Handoff

The mechanical core routes to future H2; PDC/RQ own authority gates; Fabric owns temporal/data release primitives; Lex owns legal releases; DDM owns KPI/incident contracts; core audit owns portable custody evidence; Atlas projects only.

# Appendix J. Direct Answers And Final Research Posture

1. **Is a bounded 18–24 month capstone supportable?** Yes, as a 24-month research benchmark with declared limits and synthetic authority oracles.
2. **What does it prove?** Correct behavior for the frozen scenario, events, faults, actors, oracles and versions.
3. **What does it not prove?** Universal lifetime custody, legal compliance, production RPO/RTO, causal truth, institutional acceptance or authority to administer.
4. **What is the principal invariant?** Current binding + append-only history + external-act separation + incremental/clean parity + weakest authority.
5. **Why is suspension different from a job pause?** It releases workers/locks while retaining case obligations, budgets, deadlines, wake conditions, public posture and identity over months.
6. **What wakes a case?** A typed condition bound to an exact obligation, matter/case, producer, clocks and evidence class.
7. **Why is wake not resume?** Resume requires twenty independent integrity, identity, tenant, authority, compatibility, freshness, impact, budget, envelope, public and human gates.
8. **How are late and retroactive events handled?** Through explicit clocks and typed policies; current interpretation may change, historical replay may not.
9. **How is minimal recomputation proved?** Against a clean-rebuild dependency oracle with separate precision and recall.
10. **How is authority loss without payload change tested?** Source revocation, license/DSA/calibration/delegation/validator/key events enter the authority graph independently of bytes.
11. **How are world releases tested?** Only compatible verified vectors can become governed heads; latest-of-each is a kill fixture.
12. **How are legal changes differentiated?** New act, publication, effect, corrigendum, amendment, exception, repeal and cosmetic renumbering have separate expected reactions.
13. **How are KPIs treated?** As decision-linked, non-fungible contracts requiring diagnosis before any adaptation recommendation.
14. **How are public records corrected?** By append-only correction, reissue, supersession or withdrawal with cross-surface and archive linkage.
15. **How are signatures treated?** Integrity evidence only; semantic currency and public status are separate.
16. **How is disaster recovery proved?** By executed fault/restore/reconciliation receipts under candidate custody-class RPO/RTO, never by a runbook alone.
17. **How are administrative boundaries enforced?** Every event names real operator and boundary; prohibited external acts create a kill or negative-control receipt.
18. **What is the mainline final result?** Reissue unaffected empirical claims, supersede the prior public record, withdraw unsupported legal/applicability scope, preserve all history, and keep successor/child authority limited pending new evidence.
19. **What remains unresolved?** Final matter identity, boundary register, jurisdiction-specific competence/effect, semantic equivalence tolerances and production recovery targets.
20. **What may later be prototyped?** Synthetic runner, event fixtures, wake/resume gate harness, clean-build/replay comparisons, public-state crawler and fault injector.
21. **What must be blocked?** Any silent rewrite, authority upgrade, missed affected case, duplicate irreversible action, stale public state, invalid reuse, unknown-jurisdiction fallback, administrative action or benchmark overfitting.

## Final posture

The strongest defensible conclusion is:

> PolicyOS’s lifetime-custody claim should be evaluated by a precommitted longitudinal benchmark, not a successful short run. The benchmark must force one policy matter through honest acquisition failure, durable suspension, typed wake, full authority reproof, selective reuse, minimal recomputation, legal and data change, institutional succession, KPI and harm signals, appeal and public correction, key and infrastructure failure, matter split, partial reissue, supersession, withdrawal and historical replay. Correctness is conjunctive: current state, authority, public meaning, historical truth, recovery and administrative boundaries must all hold. A pass is bounded evidence about the tested custody envelope and never a capability claim, legal certification, production-readiness finding or permission to execute administration.

