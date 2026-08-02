---
title: OPS-R4 — Temporal Semantics for Policy Custody
status: delivered
kind: deep-research
research_task: OPS-R4
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/ops-r4-temporal-custody-semantics
repository_base_branch: research/stage0-anchor-amendments
repository_base_commit: 290725446b8c073eb577f421ae2056986fbfcafb
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
inspection_date: 2026-07-29
authoritative_for:
  - research-level temporal role and relation model for PolicyOS custody
  - candidate late, duplicate, retroactive, correction, and replay semantics
  - bounded handoff to later Wave-2 research
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - universal event envelope
  - legal-effective-date adjudication
  - administrative deadline operation
  - authority grant
  - capability claim
  - production H2 architecture
  - executable OPS-R15 benchmark claim
research_only: true
---

# OPS-R4 — Temporal Semantics for Policy Custody

| Boundary | Verdict at task start |
|---|---|
| **OWN** | PolicyOS owns the temporal honesty of claims, admission actions, custody actions, lifecycle actions, and public records that PolicyOS itself signs or emits. That ownership includes explicit historical cutoffs, append-only transaction history, reproducible reconstruction, currentness/staleness, scoped revalidation, and the time attribution of PolicyOS-owned actions. |
| **INTEGRATE** | PolicyOS integrates typed, provenance-bearing assertions produced by competent external owners: occurrence, observation, publication, adoption, entry into force, repeal, retroactive effect, finality, service, delivery, payment, audit, tolling, grace-period, and deadline assertions. PolicyOS owns admission for a declared purpose and the reaction of its own claims; it does not own the external clock or legal effect. |
| **OBSERVE** | Unadmitted timestamps, polling times, news, monitoring signals, inferred dates, missing-webhook suspicions, and incomplete source progress may trigger acquisition or review. They cannot establish effect, admission, authority, currentness, or a protected downstream action. |
| **OUT_OF_SCOPE** | PolicyOS is not an administrative deadline operator, notice or service operator, court/finality adjudicator, payment scheduler, institution-wide records calendar, universal legal-time engine, or authoritative source of external operational time. |

## Executive Finding

**Result: `accepted_narrow_scope`.** PolicyOS needs a small temporal authority-delta, but it does **not** need a universal persisted event envelope or a fixed bundle of clocks.

Established temporal systems answer bounded questions well:

- bitemporal databases answer *which version was valid and which version was transaction-visible at a cutoff*;
- stream processors answer *how far a computation believes an input stream has progressed and what it will do with late elements*;
- CDC/log systems answer *how source changes were ordered and delivered under a particular log contract*;
- event-sourced workflows answer *how a recorded workflow execution can be reconstructed deterministically*;
- legal-informatics models answer *how legal documents, expressions, lifecycle events, force, efficacy, and applicability can be represented*;
- archival models answer *how immutable objects, preservation events, agents, outcomes, and revisions can be retained*.

None of those patterns, alone or in combination, proves that a PolicyOS claim was justified at a historical cutoff. They do not establish which evidence PolicyOS had received, which evidence it had admitted for the relevant purpose, whether the producer remained competent, whether a late fact was materially dependency-bearing, whether a public claim had already been issued, or which claim owner was authorized to react. Those are custody and authority questions.

The minimum coherent result is therefore:

1. **Nine primitive temporal roles**, used as a thin semantic profile rather than a mandatory field bundle: source occurrence, source effect/validity, observation/measurement, source publication/version, PolicyOS receipt, transaction visibility, verification, purpose-scoped admission, and PolicyOS claim/publication/lifecycle action.
2. **Relations rather than clocks** for correction, revocation, supersession, derivation, authority withdrawal, version validity, and unresolved correction-before-original.
3. **Explicit query coordinates** rather than an overloaded `as_of`: valid/effect coordinate, transaction/knowledge cutoff, purpose-scoped admission cutoff, publication-history coordinate, and exact replay context where required.
4. **Family-native persistence with adapters**. Fabric keeps data fact valid/transaction time and immutable mutation links; Lex and legal Data Forge keep legal publication/effect/version assertions; Scientist and Decision Validity keep claim dependency, lifecycle, reissue, and workflow history; audit keeps integrity; Atlas projects but never owns temporal truth.[^r-legal-resolver][^r-audit][^r-adr-time]
5. **A late-event assessment that recommends a minimum reaction category but never mints the final claim reaction**. The canonical claim consumer remains owner.
6. **Append-only correction history**. Current understanding of the past may change, but what PolicyOS had received, admitted, decided, or published at an earlier cutoff is never silently rewritten.

The recommended interoperability approach is **family-native events with a thin shared temporal role profile and shared relation/query semantics**. The original `OperationalEventEnvelope` is refuted as a universal persisted contract. A thin identity/mutation header remains only a research candidate for boundaries where repeated adapters prove a real need.

The current runtime `TimeSourceEnvelopeAudit` is neither an authoritative semantic owner nor a safe universal envelope.[^r-runtime-audit][^r-runtime-audit-fixture][^r-runtime-audit-validator] It is a local diagnostic composition with an accidental fifteen-role bundle and an authority-laundering defect because it can emit `mismatch_disposition="admitted"`. No code change is authorized here, but later planning should narrow and rename it, treat it as a projection only, remove admission semantics from its authority surface, and map sparse family-native roles without defaulting missing or naive time to semantic truth.

## 1. Task and Project Fit

### Research question

What do established bitemporal, event-time, CDC, event-sourcing, durable-workflow, legal-temporal, and archival patterns still lack when the object being reconstructed, corrected, admitted, invalidated, replayed, or published is a PolicyOS authority-bearing claim whose justification must remain honest across time?

The answer is not another clock taxonomy. It is a boundary-preserving algebra that separates:

- what happened, was observed, was published, or became effective in an external domain;
- when PolicyOS received an immutable representation of that assertion;
- when a named verifier checked it;
- when an authorized consumer admitted it for a declared purpose and scope;
- what was transaction-visible in repository history;
- what decision context and versions a PolicyOS claim actually used;
- what PolicyOS published or signed;
- how later information changes current standing without changing the historical record.

### Boundary verdict

The four-way verdict at the beginning of this report is controlling. In operational terms:

- **OWN** is limited to PolicyOS-authored custody, admission, evaluation, lifecycle, replay, and publication facts.
- **INTEGRATE** accepts competent external temporal assertions without re-adjudicating the external institution's clock.
- **OBSERVE** may initiate acquisition or human review but has no authority effect.
- **OUT_OF_SCOPE** prevents OPS-R4 from becoming a legal-calendar engine, service operator, payment operator, or universal records platform.

### False production claims prevented

This result is designed to prevent at least the following false claims:

| False claim | Why it is false | Required prevention |
|---|---|---|
| “The watermark passed, so no earlier-effective correction can arrive.” | A watermark is progress under a source/runtime contract, not a theorem about future legal or semantic corrections. | Preserve source-contract scope and allow late retroactive mutation. |
| “The record existed by time T, so PolicyOS knew and admitted it by T.” | Transaction visibility, receipt, verification, and admission are different predicates. | Separate `visible_by`, `known_by`, and `admitted_by`. |
| “The current database view of valid time T is what PolicyOS said at T.” | Current reconstruction may use later corrections and later admissions. | Distinguish current reconstruction, historical knowledge, and historical publication. |
| “Matching bytes or timestamps mean the same legal act.” | Distinct publications may contain identical text and retain distinct legal identity. | Preserve source identity, publication lineage, and competence. |
| “A retry-safe message means a protected external effect happened once.” | Delivery deduplication does not cover arbitrary irreversible side effects. | Use effect-scoped idempotency/at-most-once protection and audit every attempt. |
| “A cryptographically valid artifact is current.” | Integrity and semantic currentness are independent. | Join integrity to lifecycle/currentness without changing historical bytes. |
| “A missing timestamp can default to now.” | `now` is processing time, not source occurrence/effect/receipt/admission. | Unknown remains unknown; authority-dependent use fails closed. |
| “UTC normalization preserves the source meaning.” | A civil date, unknown offset, ambiguous local time, or jurisdictional date may not denote one instant. | Preserve precision, zone, calendar, and uncertainty. |
| “A source-required action is the PolicyOS reaction.” | A producer cannot prescribe the canonical consumer's claim lifecycle. | Treat source action fields as assertions/advice; claim owner decides. |
| “A UI cursor defines temporal truth.” | Projection state cannot become an authority owner. | Atlas and other surfaces consume explicit query semantics only. |

### Standing

This is an authority-delta adaptation study. It is research-only and implementation-neutral. It may be used to constrain later Wave-2 research, but it does not authorize code, schemas, generated APIs, production architecture, legal-effect adjudication, or an executable OPS-R15 benchmark.

The amended Stage-0 inputs are treated as research baselines, not production contracts. Their controlling direction is consistent: preserve source/effect, custody/admission, transaction/history, correction/replay, and family ownership; do not reactivate the frozen nine-, ten-, or thirteen-clock proposals.[^r-stage0-r0][^r-stage0-r1][^r-stage0-r15][^r-stage0-consensus]

## 2. Current Repository Baseline

### Repository and branch baselines

| Baseline | Resolution |
|---|---|
| Historical Stage-0 repository baseline | `main` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` |
| Amended Stage-0 base branch | `research/stage0-anchor-amendments` |
| Recorded amendment head | `290725446b8c073eb577f421ae2056986fbfcafb` |
| Remote amendment head resolved on 2026-07-29 | `290725446b8c073eb577f421ae2056986fbfcafb` |
| Comparison | Exact match; zero commits ahead or behind; no later amendment-branch changes to inspect |
| OPS-R4 branch base | The exact resolved amendment head above |
| Required result path | `policy-engine/docs/research/policy-operations/ops-r4-temporal-semantics-for-policy-custody.md` |
| PR #5 standing | Open draft input; not assumed merged or ratified |

The required Stage-0 files were read in full, including the amended PAO-R0, PAO-R1, OPS-R15, conformance report, disposition ledger, consolidation report, consensus kernel, owner/vocabulary map, Wave-2 readiness report, and additional-research register. The frozen originals were used only as historical evidence of proposals that Stage-0 subsequently narrowed or rejected.

Repository instructions, custody decisions, backlog and distillation documents, failure patterns, Fabric references, retention/recovery references, active Atlas/Fabric plans, implementation owners, tests, and relevant commit history were inspected before external research. The repository-wide term search covered every required token: `valid_at`, `valid_time`, `tx_at`, `tx_time`, `occurred_at`, `recorded_at`, `observed_at`, `published_at`, `updated_at`, `ingested_at`, `admitted_at`, `effective_time`, `legal_valid_time`, `as_of_time`, `replay_time`, `scheduled_for`, `deadline`, `expiry`, `expires_at`, `watermark`, `cursor`, `dedupe_key`, `corrects`, `revokes`, `supersedes`, `retroactive`, `late`, and `out_of_order`.

The search result is semantically important: repeated names do not imply shared meaning. For example, `updated_at` appears in source records, caches, projections, queues, security credentials, and materializations; `cursor` appears in source progress and UI navigation; `watermark` appears in Fabric processing and visual document branding; `expiry` appears in cache TTLs, authority credentials, retention, evidence freshness, and lifecycle policy. The census therefore records producer, trust, shape, persistence, replay effect, and authority effect rather than inferring semantics from spelling.

### Temporal-role census

**Census scope.** The table records 94 material fields, functions, or mechanisms across 11 owner families: (1) core runtime/query contracts; (2) runtime temporal audit and Atlas-facing projections; (3) Fabric facts, world history, snapshots, and materialization; (4) Fabric source progress and delivery guarantees; (5) Decision Validity and control-plane lifecycle; (6) Scientist claim lifecycle; (7) Scientist workflow, checkpoint, and replay; (8) Lex and legal Data Forge temporal evidence; (9) Data Forge snapshots and artifact transactions; (10) core audit and source-truth records; and (11) obligation, identity/security, retention, and public-record projections. “Persisted” means persisted by the inspected implementation or its declared storage path, not merely serializable. The `Capability state` column also records the evidence level: `implemented / persisted / tested` means both storage behavior and semantic tests were found; `implemented / persisted` means storage was found but no test proving the stated meaning was located; `implemented` means code exists while persistence or semantic-test coverage remains unresolved; and `partial`, `contract-only`, `projection-only`, or `research-only` state the narrower capability directly. “Authority effect” reports current behavior, not a normative endorsement.

#### Core runtime query and scope contracts

| ID / Symbol/path | Current owner | Domain | Producer | Time role | Trust standing | Shape | Current authority effect | Replay role | Correction behavior | Capability state | Conflict/duplication | Recommended disposition |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C001 `core/contracts/runtime.py::TemporalRef.valid_at` | core contracts | cross-domain query | caller/adapter | requested valid/effect coordinate | external/caller asserted | instant | family-specific; may constrain facts | selects valid-time view | new query, not mutation | implemented | overlaps `as_of`, `legal_as_of` | reuse; require role label at boundary |
| C002 `TemporalRef.tx_at` | core contracts | repository visibility | caller/adapter | transaction cutoff | caller asserted, store interpreted | instant/cutoff | no authority alone | selects versions visible by cutoff | immutable query coordinate | implemented | runtime sometimes aliases trace time | reuse; forbid fallback to valid time or now |
| C003 `TemporalScope.valid_at` | core contracts/runtime | query scope | route/client | valid-time coordinate | caller asserted | instant/cutoff | family-specific | current or historical valid view | new scope | implemented | UI calls it universal `as_of` | clarify: not knowledge/publication by itself |
| C004 `TemporalScope.tx_at` | core contracts/runtime | query scope | route/client | transaction-visibility coordinate | caller asserted | instant/cutoff | none alone | historical repository view | new scope | implemented | sometimes omitted or copied from valid time | reuse; authority paths require explicitness |
| C005 `TemporalScope.snapshot_id` | Fabric/runtime | data/world version | snapshot owner | immutable world snapshot selector | system-recorded | version reference | family-specific | binds replay to snapshot | replacement by new ref | implemented | can be mistaken for global decision context | reuse as one context component only |
| C006 `TemporalScope.branch/scenario` | Fabric/runtime | counterfactual/workspace | branch/scenario owner | non-historical overlay coordinate | system-recorded/asserted | relation/version | no real-world authority by default | reproduces branch projection | append/new head | implemented | UI temporal mode can conflate history/counterfactual | retain family-native; label counterfactual |
| C007 runtime `?as_of` / UI time cursor | runtime/Atlas | projection/query | user/UI | generic point-in-time request | user asserted | instant | must be none until mapped | routes to owner query | no correction | implemented/partial | ADR-044 treats one cursor as universal | adapt: coordinate chooser, never truth owner |
| C008 runtime temporal range/projection points | runtime services | diagnostic/projection | runtime trace/world adapters | sampled display time | system-recorded/derived | instant series | unclear in some routes | display/reconstruction aid | recompute projection | partial | some points use one timestamp for valid and tx | narrow; prohibit custody inference |

#### Runtime `TimeSourceEnvelopeAudit` and adjacent validation

| ID / Symbol/path | Current owner | Domain | Producer | Time role | Trust standing | Shape | Current authority effect | Replay role | Correction behavior | Capability state | Conflict/duplication | Recommended disposition |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C009 `TimeSourceEnvelopeAudit.as_of_time` | runtime quality | diagnostic composition | builder | generic comparison cutoff | derived from scope | instant | participates in admit/block diagnostic | comparison anchor | regenerate audit | implemented | duplicates valid/evaluation/publication meanings | projection-only; rename role explicitly |
| C010 `.catalog_watermark` | runtime quality from Fabric/catalog | data progress | catalog adapter | source/catalog progress | system-recorded or derived | instant | currently gates disposition | replay diagnostic | new audit | implemented | may be fetched/source-update fallback | keep source-contract qualified; no finality claim |
| C011 `.effective_time` | runtime quality | mixed source/domain | builder | asserted/derived source effect | source asserted or substituted | instant | currently gates disposition | comparison input | new audit | implemented | one field spans law/data/workflow | sparse family mapping; never universal required |
| C012 `.ingested_at` | runtime quality | operational receipt | builder | pipeline ingestion | system-recorded/substituted | instant | currently bundled with authority decision | diagnostic only | append/new audit | implemented locally | almost no canonical repository owner | remove from semantic bundle; map to receipt only when proved |
| C013 `.legal_valid_time` | runtime quality | legal | builder | legal validity coordinate | derived/substituted | instant | blocks outside replay/as-of | diagnostic | new audit | implemented | competes with Lex legal windows | defer to Lex assertion; no runtime adjudication |
| C014 `.replay_time` | runtime quality | replay | builder | generic replay cutoff | derived from tx scope | instant | currently gates disposition | intended replay anchor | new audit | implemented | conflates transaction cutoff and exact context | replace with explicit replay context mapping |
| C015 `.transaction_time` | runtime quality | repository history | builder | record visibility | system/derived | instant | currently in fixed bundle | historical ordering | append audit | implemented | may equal trace completion | map only from canonical store transaction time |
| C016 `.source_observed_at` | runtime quality | source observation | builder | observation time | source asserted/substituted | instant | currently compared | diagnostic | new audit | implemented | observation often interval/date | allow interval/precision; no fixed instant requirement |
| C017 `.source_published_at` | runtime quality | source publication | builder | publication time | source asserted/substituted | instant | currently compared | publication diagnostic | new audit | implemented | absent for many data/workflow families | family-native optional role |
| C018 `.source_updated_at` | runtime quality | source revision | builder | source revision/update | source asserted | instant | currently compared | revision diagnostic | new audit | implemented | update is not correction/effect | map as version assertion, not mutation relation |
| C019 `.retention_or_expiry` | runtime quality | retention/currentness | builder | overloaded retention or expiry | system/derived | instant | can block replay | replay availability | append policy/event | implemented | collapses retention, freshness, authority expiry | split by owner; no shared field |
| C020 `.run_started_at/.run_finished_at` | runtime workflow | processing | runtime events | execution timing | system-recorded | interval endpoints | none semantically | operational replay/diagnostic | append events | implemented | can contaminate semantic identity | keep outside content identity |
| C021 `.node_started_at/.node_finished_at` | runtime workflow | processing | runtime events | node processing timing | system-recorded | interval endpoints | none semantically | diagnostic | append events | implemented | same | retain operational only |
| C022 `.mismatch_disposition` | runtime quality | diagnostic/admission | builder | output reaction | derived | enum/relation | **can emit `admitted`** | no safe replay meaning | regenerate | implemented | launders diagnostic into authority | narrow immediately in planning; no admission vocabulary |
| C023 `build_time_source_envelope_audit()` | runtime quality | diagnostic composition | runtime service | composes fifteen roles | mixed | projection | accidental authority owner | diagnostic replay | regenerated | implemented | accidental universal envelope/P13 gravity | retain code unchanged now; future narrow+rename+projection-only |
| C024 `check_layer3_time_source_authority.py` | quality validation | fixture validation | validation tool | validates fixed role bundle | derived/test | rule set | treats bundle as admission gate | benchmark-like | rerun | implemented | freezes rejected clock list; naive/year normalization | treat as local historical proof; do not generalize |

#### Fabric facts, world store, snapshots, and immutable mutations

| ID / Symbol/path | Current owner | Domain | Producer | Time role | Trust standing | Shape | Current authority effect | Replay role | Correction behavior | Capability state | Conflict/duplication | Recommended disposition |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C025 `ir/loading/fact_log.py::Fact.valid_time` | Fabric/IR fact log | data fact | fact producer | domain validity/observation coordinate | source asserted/normalized | instant | family-specific | valid-time selection | new fact/mutation | implemented | generic name spans observations and effects | reuse; require predicate/family semantics |
| C026 `Fact.tx_time` | Fabric/IR fact log | data history | fact writer/store | transaction visibility | system-recorded | instant | none alone | cutoff reconstruction | append-only | implemented | may be confused with receipt | reuse as store visibility only |
| C027 `build_fact_id(...valid_time...)` | Fabric evidence | semantic identity | fact writer | constitutive valid-time input | governed producer | identity component | can distinguish semantic facts | deterministic replay | new ID for changed semantic time | implemented | risk if valid_time is substituted from processing | reuse with provenance and precision rules |
| C028 Fact ID exclusion of `tx_time` | Fabric evidence | identity invariant | fact writer | prevents processing/recording contamination | system design | negative rule | preserves semantic equality | stable replay | append later tx version | implemented/testable | other artifacts include `created_at` in hashes | preserve and extend metamorphic test |
| C029 DuckDB `facts.valid_time` | Fabric world store | data validity | materializer | stored valid coordinate | source/family asserted | instant | family-specific | `as_of_valid` filter | append replacement/mutation | implemented | point time only in current table | reuse; intervals need family adaptation |
| C030 DuckDB `facts.tx_time` | Fabric world store | transaction history | store/materializer | stored visibility coordinate | system-recorded | instant | none alone | `as_of_tx` filter | append | implemented | no global cross-store total order | reuse; expose store identity/order scope |
| C031 `world/query.py::as_of_valid` | Fabric world query | data query | consumer | valid cutoff | caller asserted | cutoff | family-specific | historical/current valid view | no mutation | implemented/tested | often called `as_of` externally | reuse; label valid/effect coordinate |
| C032 `world/query.py::as_of_tx` | Fabric world query | data query | consumer | transaction cutoff | caller asserted | cutoff | none alone | historical knowledge substrate | no mutation | implemented/tested | not identical to PolicyOS knowledge/admission | reuse; compose with custody predicates |
| C033 latest-tx-per-predicate projection | Fabric world query | current view | query engine | transaction-visible winner | derived | ordering/projection | family-specific current fact | current reconstruction | recompute projection | implemented | “latest” may ignore authority/lifecycle | retain Fabric-local; claim owner filters standing |
| C034 `world/store/snapshots.py::created_at` | Fabric world store | snapshot history | store | snapshot creation/recording | system-recorded | instant | none alone | identifies snapshot availability | append | implemented | not source valid time | reuse operationally only |
| C035 snapshot `valid_at` | Fabric world store | snapshot coordinate | snapshot creator | captured valid coordinate | caller/system | cutoff | family-specific | binds world reconstruction | immutable snapshot | implemented/tested | can be absent/derived | reuse; record explicit coordinate for replay |
| C036 snapshot `tx_at` | Fabric world store | snapshot coordinate | snapshot creator | captured transaction cutoff | store/caller | cutoff | none alone | exact visible state | immutable snapshot | implemented/tested | may not capture custody/admission | reuse as one replay dimension |
| C037 branch head/update history | Fabric world store | scenario/branch | branch owner | overlay version order | system-recorded | version/relation | no external authority | replay scenario lineage | append new head | implemented/tested | can look like historical correction | keep distinct from real-world mutation |
| C038 segment `mutation_kind=correction` / `corrects_fact_ref` | Fabric world store | data correction | authorized fact producer | correction relation | source/producer asserted | relation | family-specific | preserves old/new views | append immutable relation | implemented | not public claim correction | reuse for Fabric facts; adapter to custody relation |
| C039 segment `mutation_kind=revocation` / `revokes_fact_ref` | Fabric world store | data revocation | authorized fact producer | revocation relation | source/producer asserted | relation | family-specific | excludes/relabels current projection | append immutable relation | implemented | revocation may mean source or authority withdrawal | qualify relation type and owner |
| C040 `inserted_at` / projection `updated_at` / document `retrieved_at` | Fabric world/materialization | operational storage | materializer/retriever | load, projection refresh, retrieval | system-recorded | instants | none by default | diagnostics/rebuild | append or replace projection | implemented | overloaded `updated_at` | keep outside authority unless object is that event |

#### Fabric progress, watermarks, windows, cursors, and delivery guarantees

| ID / Symbol/path | Current owner | Domain | Producer | Time role | Trust standing | Shape | Current authority effect | Replay role | Correction behavior | Capability state | Conflict/duplication | Recommended disposition |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C041 `WatermarkType.TIMESTAMP` | Fabric data plane | ingestion progress | connector/source contract | time-like progress marker | source/system | watermark | none beyond contract | resume/window progress | advance monotonically | implemented | mistaken for semantic completeness | reuse with explicit contract and confidence |
| C042 `WatermarkType.ETAG` | Fabric data plane | source version progress | connector | opaque source version | external | token | none | resume/change detection | replace/advance | implemented | not time | retain; never compare as temporal instant |
| C043 `WatermarkType.REVISION` | Fabric data plane | source version progress | connector | revision coordinate | external | token/order | none | resume/version selection | advance | implemented | revision order may not equal effect order | retain source-local semantics |
| C044 `WatermarkType.OFFSET` | Fabric data plane | log progress | connector/log | offset coordinate | source/system | ordinal | none | resume/delivery order | advance | implemented | partition-local, not global time | retain scope/partition identity |
| C045 `WatermarkType.SCHEMA` | Fabric data plane | schema progress | connector | schema-version coordinate | external/system | version | none | reproducibility | replace | implemented | not event-time | retain as version role |
| C046 timestamp watermark `source_updated_at` | Fabric data plane | source progress | connector payload | source update marker | source asserted | instant | none | progress estimate | advance | implemented | update not occurrence/effect/correction | label source revision only |
| C047 timestamp fallback `fetched_at` | Fabric data plane | acquisition | connector | retrieval/processing fallback | system-recorded | instant | none | resume estimate | advance | implemented | can impersonate event time | prohibit semantic-completeness inference |
| C048 cursor/checkpoint `created_at/updated_at/committed_at` | core/Fabric cursor store | resumption | cursor store | state management times | system-recorded | instants | none | operational resume | append/update cursor state | implemented/tested | “committed” not legal/admission commit | keep operational |
| C049 `dedupe_key` and delivery guarantee | Fabric processing | message delivery | producer/runtime | delivery identity | producer/system | identity token | protects pipeline effect only | stable retry | suppress duplicate delivery | implemented/tested | not real-world act identity | retain scoped; record dedupe basis/expiry |
| C050 `out_of_order_policy` / late-window handling | Fabric processing | stream processing | source contract/runtime | delivery-order reaction | configured | enum/window | none on claims | window/replay behavior | quarantine/drop/reorder | implemented/tested | can be mistaken for custody reaction | keep Fabric-local; emit assessment evidence only |

#### Decision Validity, claim lifecycle, and custody reactions

| ID / Symbol/path | Current owner | Domain | Producer | Time role | Trust standing | Shape | Current authority effect | Replay role | Correction behavior | Capability state | Conflict/duplication | Recommended disposition |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C051 `DecisionValidityEnvelope.built_at` | core contracts / Scientist | authority-support packet | packet builder | envelope construction time | system-recorded | instant | none by itself | identifies packet version availability | append/new envelope | implemented/persisted | can be mistaken for evidence or decision time | retain operational/provenance role only |
| C052 `DecisionValidityEvaluation.evaluated_at` | Scientist decision validity | authority evaluation | evaluator | custody evaluation time | system-recorded | instant | accompanies validity status | reconstructs when a verdict existed | append/new evaluation | implemented/persisted | not source effect, admission, or publication | reuse as PolicyOS evaluation action time |
| C053 `DecisionDependencyEvent.occurred_at` | core control-plane contract | dependency event | source adapter/monitor | asserted occurrence of trigger | mixed source/system | instant | may initiate a lifecycle reaction | orders source-trigger narrative | append | implemented/persisted | default `now` can become false source occurrence | require explicit trust/role; no authority default-to-now |
| C054 `DecisionDependencyEvent.recorded_at` | control plane | transaction/audit | event log | PolicyOS event recording time | system-recorded | instant | none alone | historical visibility of trigger | append | implemented/persisted | often close to `occurred_at` but semantically distinct | reuse as custody transaction coordinate |
| C055 `DecisionDependencyEvent.event_id` / `dedupe_key` | control plane | delivery/idempotency | event producer | event/delivery identity | producer/system | identity token | protects duplicate processing only | stable retry/audit | reject duplicate key within scope | implemented/tested | cannot prove same real-world act or correction | retain scoped; bind namespace, producer, effect scope |
| C056 `DecisionValidityTransition.occurred_at`, previous/current status | Scientist/control plane | custody lifecycle | canonical decision consumer | PolicyOS transition occurrence | system-recorded | instant + relation | changes current claim standing | reconstructs past standing | append transition | implemented/persisted | no separate recorded time in transition DTO | extend owner locally if transaction visibility cannot be recovered from store |
| C057 `DecisionLifecycleJob.scheduled_for` / `completed_at` | Scientist/control plane | workflow scheduling | lifecycle service | planned and completed follow-up | system-owned | deadline/instant | no legal effect; may govern custody work | reproduces pending/completed work | update job plus audit events | implemented | resembles external deadline | retain as PolicyOS-owned workflow duty only |
| C058 `DecisionValidityStatus` (`active`, `stale`, `review_required`, `superseded`, `reissued`, `withdrawn`, `revoked`, etc.) | Scientist decision validity | claim currentness | evaluator/claim owner | lifecycle standing, not time | derived authority decision | state relation | directly controls current standing | standing at cutoff requires event history | append transitions; do not overwrite history | implemented | risks becoming parallel Stage-0 lattice | reuse family-native statuses; map only to shared predicates |
| C059 `supersedes_decision_ref` / `superseded_by_ref` / `recommended_action` | Scientist decision validity | correction/reissue | evaluator | mutation lineage and advisory reaction | derived | relation + advisory text | relation can affect currentness; action is non-canonical | links versions in replay | append new evaluation/reissue | implemented/partial | `recommended_action` can prescribe another owner | preserve refs; treat action as advisory to canonical claim consumer |
| C060 dependency refs, watched triggers, trigger records | core/Scientist | dependency validity | packet builder/monitor | dependency and trigger relation | mixed | relation/set | family-specific inputs to authority | affected-set and cutoff reconstruction | append new versions/events | implemented | no explicit dependency validity interval in base DTO | extend OPS-R2 owner with interval/standing evidence, not OPS-R4 store |
| C061 `ClaimLifecycleEvent.occurred_at` | Scientist Claim Ledger v2 | claim lifecycle | claim owner | occurrence of PolicyOS lifecycle action | system-recorded or caller supplied | instant | changes claim publishability/standing through action | reconstructs claim history | append immutable event | implemented/tested | one timestamp carries both action occurrence and ledger order | retain; add transaction visibility through store rather than reinterpret field |
| C062 `AppendOnlyClaimLedger` sorting and `append_lifecycle_event()` monotonic `occurred_at` gate | Scientist Claim Ledger v2 | append-only history | ledger | local monotone workflow ordering | system rule | total order constraint | prevents reordering/deletion | deterministic local replay | rejects earlier occurrence after later event | implemented/tested | cannot represent genuinely late external occurrence or correction-before-original | preserve local rule; adapter records external source time separately from ledger transaction order |
| C063 lifecycle actions and `previous_claim_ref` / `next_claim_ref` / superseding claim metadata | Scientist Claim Ledger v2 | correction/currentness | claim owner | immutable lifecycle mutation relations | system/authorized human | relations | controls publishability and currentness | preserves earlier bytes and lineage | append `marked_stale`, `invalidated`, `superseded`, `reissued`, `withdrawn`, etc. | implemented/tested | no universal correction semantics across legal/data/public families | reuse as canonical claim-family reaction; map to shared mutation predicates |
| C064 incident `detected_at`, monitor `observed_at`, reissue/continuous-governance timestamps | Scientist continuous governance | monitoring and reaction | detectors/monitors/reissue service | detection, observation, reissue processing | system-recorded/derived | instants | trigger evidence, not source effect or admission | explains why/when a reaction began | append incident/reissue artifacts | implemented/partial | names overlap source observation and claim occurrence | owner-qualify; no source-time substitution |

#### Scientist checkpoints, durable workflow history, and replay

| ID / Symbol/path | Current owner | Domain | Producer | Time role | Trust standing | Shape | Current authority effect | Replay role | Correction behavior | Capability state | Conflict/duplication | Recommended disposition |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C065 `CheckpointMetadata.created_at` / head-history `updated_at` | Scientist orchestration | workflow persistence | checkpoint writer | checkpoint recording/update time | system-recorded | instant | none on claim truth | locates recoverable state | append artifact; move head | implemented/persisted | can be mistaken for decision cutoff | keep operational; exact replay also needs evidence/admission cutoffs |
| C066 `sequence_number`, completed node alias/id/list, FSM phase | Scientist orchestration | workflow history | engine | causal workflow order | system-recorded | ordinal/state | no authority alone | deterministic resume ordering | append checkpoint chain | implemented/tested | sequence is not world/source time | reuse as workflow-native partial order |
| C067 `workflow_id` / `workflow_fingerprint` | Scientist orchestration | executable history | workflow owner | executable version identity | system-derived | identity/version | bounds replay validity | rejects incompatible resume | new workflow/version | implemented/tested | content-equivalent workflows may differ operationally | retain; include in exact replay receipt, not temporal truth |
| C068 `snapshot_mode`, `base_checkpoint_ref`, `chain_depth`, state delta | Scientist orchestration | durable state | checkpoint writer | state-version lineage | system-recorded | version/relation | none alone | reconstructs state before continuation | append full/incremental checkpoint | implemented/tested | not Fabric world snapshot or evidence snapshot | retain family-native and distinguish namespaces |
| C069 `CheckpointResumeRequest.resume_strategy`, workflow/registry compatibility gates | Scientist orchestration | resume | operator/runtime | requested resume/replay mode | system/operator asserted | policy + refs | can authorize workflow continuation only | guards exact/bounded replay | fail closed on mismatch/corruption | implemented/tested | “allow_replay” does not establish historical evidence parity | reuse; OPS-R1 must add custody cutoff and wake evidence |
| C070 replay backend/verification timestamps and duration metrics | Scientist replay | execution diagnostics | replay engine | replay processing time | system-recorded | instant/duration | none semantically | performance and audit | append verification | implemented/partial | can contaminate output hashes if included | exclude from semantic result identity unless the claim concerns execution timing |
| C071 cache entry refs, research DAG ref, registry bundle ref, artifact versions | Scientist orchestration | replay context | engine/artifact owners | exact context/version coordinates | system-recorded | reference set | authority only through resolved owners | necessary but not sufficient for exact replay | immutable refs/new versions | implemented/partial | no unified receipt joins evidence, admission, world, rules, workflow | candidate `TemporalReplayReceipt` projection; no new store |

#### Lex and legal Data Forge temporal evidence

| ID / Symbol/path | Current owner | Domain | Producer | Time role | Trust standing | Shape | Current authority effect | Replay role | Correction behavior | Capability state | Conflict/duplication | Recommended disposition |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C072 Lex legal evaluation `legal_as_of` / claim evaluation instant | Lex | legal applicability | caller/claim evaluator | legal applicability coordinate | caller asserted, Lex interpreted | instant/date cutoff | family-specific and authority material | selects applicable legal claims/rules | new evaluation | implemented/tested | runtime calls similar field `legal_valid_time` | Lex remains owner; adapters expose role without adjudicating |
| C073 legal `effective_from` / `effective_to` | Lex/Data Forge legal corpus | legal effect | competent source assertion/extractor | legal effect interval | external asserted, provenance-backed | interval, often civil dates | authority material when competence supports it | reconstructs applicability | append new source/version/assertion | implemented/partial | inclusive date semantics may differ by jurisdiction | retain source precision and interpretation rule; no UTC-midnight invention |
| C074 competence windows and split-claim evaluation | Lex legal authority | legal competence | competence evidence/authority adapter | producer competence interval | external asserted/derived by Lex | interval | directly bounds legal authority | validates competence at claim time | new competence record/revocation | implemented/tested | payload can remain identical after competence expiry | reuse; claim consumer revalidates authority independently of content hash |
| C075 `published_at` in legal document metadata/version entries | Data Forge legal corpus / Lex | legal publication | official publisher/source metadata | publication date/time | external asserted | civil date/instant | may be prerequisite but not equivalent to effect | source-known/published-by queries | append version | implemented/partial | fallback sorting can use publication when effect absent | retain distinct from adoption, receipt, effect, transaction |
| C076 adoption, promulgation, entry-into-force, repeal, consolidation, future-effect and retroactivity evidence | Lex/legal source family | legal lifecycle | competent external authority | family-native legal temporal acts | external asserted | dates, intervals, relations | potentially authority material | legal historical/current reconstruction | append new act/version/relation | partial/dispersed | not all represented by one field | OPS-R10/11 define family contract; OPS-R4 supplies shared roles/relations only |
| C077 legal temporal resolution status, confidence, quality issues, unresolved/overlap flags | Data Forge legal temporal resolver | legal evidence quality | extractor/resolver | epistemic standing of temporal assertion | derived with source provenance | state + bounds | limits authority; must not mint effect | explains uncertainty at cutoff | append revised resolution | implemented/partial | confidence scalar can hide disputed alternatives | retain alternatives, precision, basis and competent-human requirement |
| C078 legal version index (`doc_version_id`, version entries, current source pointer) | Data Forge legal corpus / Lex | source revision | corpus builder | source/version order | system-recorded from source artifacts | version/relation | family-specific | reproducible source selection | append version/index and pointer | implemented | revision order may differ from effect/publication order | reuse version identity; query valid-under-version explicitly |
| C079 rule/norm-pack/source version references and selection policy | Lex | legal executable context | NormPack assembler | `valid under version` relation | system-recorded/derived | version relation | authority material through Lex | exact replay before/after legal changes | append new pack/version | implemented | a latest pointer is not historical selection evidence | pin refs and selection policy in replay context |
| C080 date-only/month-only/local-calendar/timezone metadata | legal source family | legal precision | external source | bounded precision and interpretation | source asserted | uncertain interval/precision descriptor | may limit authority | preserves exact historical assertion | append clarified assertion | partial | parsers often coerce ISO dates | preserve lexical value, calendar/zone and interpreted interval; fail closed when material |
| C081 legal correction, repeal, revocation, supersession and consolidation relations | Lex/Data Forge legal | legal mutation | competent source/curator | source-family mutation relation | external asserted | relation | authority material but not self-executing for PolicyOS claims | preserves source history/current legal view | append relation/version; never rewrite bytes | partial | “revokes” overlaps Fabric fact and custody withdrawal | namespace relation and competent authority; claim reaction remains consumer-owned |
| C082 retrieval/fetch/source-update times for legal artifacts | Data Forge connectors | acquisition | connector | receipt/retrieval/revision polling | system-recorded or source asserted | instants | none by default | proves when PolicyOS could access bytes | append acquisition log/artifact | implemented/dispersed | may be substituted for publication or effect | map only to receipt/source revision when provenance proves role |

#### Data Forge snapshots, logical transactions, and artifact time

| ID / Symbol/path | Current owner | Domain | Producer | Time role | Trust standing | Shape | Current authority effect | Replay role | Correction behavior | Capability state | Conflict/duplication | Recommended disposition |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C083 snapshot commit `committed_at` | Data Forge snapshot kernel | data transaction | snapshot commit service | snapshot transaction/commit time | system-recorded | instant | none alone | orders snapshot visibility | append commit | implemented/persisted | “commit” can be confused with legal/admission commitment | retain store-local meaning |
| C084 snapshot transaction `logical_ts` | Data Forge snapshot kernel | transaction ordering | transaction manager | logical order coordinate | system-derived | ordinal/logical instant | none alone | deterministic time travel | monotonically advance | implemented | not wall clock, valid time, or source order | reuse with store identity and documented ordering scope |
| C085 snapshot IDs, parent/base refs, transaction state and time-travel selector | Data Forge snapshot kernel | data versioning | snapshot service | immutable version lineage | system-recorded | version/relation | family-specific input | exact dataset-state reconstruction | append new snapshot | implemented/tested | overlaps Fabric world snapshot namespace | retain separate owner; adapters map version role only |
| C086 artifact `created_at`, freshness/retention/expiry metadata | artifact/Data Forge owners | artifact custody | artifact writer/policy | recording, freshness or retention duties | system-recorded/derived | instants/deadlines | only owner-specific | availability/currentness at cutoff | append policy/event/new artifact | implemented/dispersed | same label spans TTL, evidence freshness and authority expiry | require explicit role and owner; never infer from generic `expires_at` |
| C087 source acquisition, observation period, release/version and publication metadata in domain artifacts | Data Forge domains | data evidence | source adapter/domain pack | family-native source temporal evidence | external + system | interval/date/version/instant | family-specific after admission | supports valid/source-published/received views | append revised artifact/version | implemented/partial | field conventions vary by domain | preserve family-native schema; expose sparse temporal-role adapter |

#### Audit, source truth, projections, and deadlines

| ID / Symbol/path | Current owner | Domain | Producer | Time role | Trust standing | Shape | Current authority effect | Replay role | Correction behavior | Capability state | Conflict/duplication | Recommended disposition |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C088 core audit event timestamps / verification time | core audit | integrity/audit | audit writer/verifier | record creation and later integrity verification | system-recorded | instants | proves integrity, not semantic currentness | verifies retained bytes/history | append audit/verification events | implemented | “verified” can be misread as evidence admitted/current | retain; explicitly separate integrity, verification and authority |
| C089 source-truth `recorded_at` and source assertions | core source-truth contracts | provenance | source adapter/custody recorder | PolicyOS recording of source assertion | system-recorded plus external content | instant + assertion | no authority until purpose-specific admission | historical knowledge substrate | append assertion/version | implemented/partial | name may suggest objective truth | treat as source assertion custody, not truth adjudication |
| C090 Atlas/runtime cursor, labels, temporal chips and projected `as_of` values | Atlas/runtime | UI/public projection | projection services/UI | display/query coordinate | derived/user asserted | instant/label | none; must not mint truth | reproduces view parameters only | regenerate projection | implemented | ADR-044 universal cursor can collapse query meanings | keep projection-only; require query-kind and owner provenance |
| C091 `BoundedLivenessConfig.deadline_s` and retry ceilings | runtime quality | workflow liveness | governed runtime config | maximum producer wait duration | system-owned configuration | duration | controls escalation, not claim truth/legal deadline | reproduces operational wait policy | version config | implemented/governed | generic “deadline” wording | retain runtime-native; outside custody temporal algebra except provenance |
| C092 obligation graph `deadline_at`, `observed_at`, `temporal_window`, owner/escalation binding | obligation graph | PolicyOS obligation workflow | rule/candidate/ledger owner | owner-scoped duty due time and observation | mixed governed/source/system | deadline + instant + scope | can require owner action, not adjudicate external law | reconstructs obligation frontier | append ledger/rule version | implemented | could absorb external filing/appeal clocks | retain only with owner/source refs; external deadline remains assertion |
| C093 credential, delegation, licence, mandate, reviewer or producer competence expiry | security/identity/Lex/custody owner | authority validity | competent authority/system policy | authority-validity interval/expiry | external/governed | interval/deadline | directly authority material | re-evaluates authority at cutoff | append expiry/revocation/renewal | implemented/dispersed | bytes/content unchanged while authority changes | shared predicate `authority_valid_during`; family owner supplies evidence |
| C094 public artifact signature/integrity timestamp, publication/currentness/archive standing | public record / PAO-R36 / Atlas projection | public accountability | publisher/archive/claim owner | publication event, signature, currentness and archival retention | system-recorded/derived | instant + lifecycle relations | publication/currentness is authority material; signature only integrity | reconstructs what was actually public | append correction/withdrawal/supersession; retain original | partial/dispersed | UI may show valid signature as current | later public owner must expose integrity and currentness separately |

### Existing capability chains

The repository already contains most of the mechanical primitives needed for a custody temporal semantics. The missing work is not a second temporal platform; it is disciplined composition and authority narrowing.[^r-fabric-time][^r-decision-validity][^r-claim-lifecycle][^r-checkpoint][^r-lex]

| Capability chain | Existing owner and primitives | What it can already establish | Missing authority-delta |
|---|---|---|---|
| Data fact history | Fabric fact log, world store, `valid_time`, `tx_time`, snapshots, branches, immutable correction/revocation links | Which Fabric fact/version was valid and transaction-visible under a named world-store query; how a corrected or revoked fact relates to retained predecessors | It does not prove PolicyOS receipt, purpose-specific admission, producer competence, claim dependency, publication standing, or exact decision context |
| Source progress | Fabric watermark, cursor store, source contracts, delivery dedupe, out-of-order policy | Connector progress, resume position, delivery handling, and scoped duplicate suppression | It does not establish domain completeness, no future retroactive correction, or the claim reaction to late material evidence |
| Decision currentness | Decision Validity envelope/evaluation/event/transition/job contracts | Dependency-triggered status changes, scheduled monitoring, dedupe, supersession/reissue links, and current validity standing | It lacks a shared distinction between source occurrence, receipt, transaction visibility, and historical admission; reaction labels must remain claim-owner decisions |
| Claim history | Scientist append-only Claim Ledger v2 | Immutable lifecycle events, non-silent downgrade, supersession/reissue/withdrawal, retained predecessor refs | Its local `occurred_at` monotonicity cannot represent genuinely late external occurrence without an adapter; no cross-family current reconstruction query |
| Durable workflow | Scientist checkpoints, workflow fingerprints, snapshot chains, resume compatibility checks, replay verification | Recoverable execution state and deterministic compatibility with a workflow/version context | A checkpoint is not an evidence/admission/publication cutoff; exact policy replay needs a composite receipt of all authority-bearing inputs |
| Legal temporality | Lex authority evaluation, effective windows, competence windows, NormPack/source versions; legal Data Forge publication/version resolver | Family-native legal applicability, source/version history, competence at time, and uncertainty/issues in extracted temporal evidence | Runtime must not replace Lex with a generic `legal_valid_time`; external legal effect remains an integrated assertion and may require competent adjudication |
| Data snapshots | Data Forge immutable snapshots, logical transaction time, commit history and time-travel | Reproducible dataset state under its own transaction/version model | Dataset snapshot availability is not evidence admission or a complete PolicyOS knowledge state |
| Integrity and provenance | CAS/artifact refs, core audit, source-truth records, signatures and verification | Byte identity, retained artifacts, source attribution, and integrity verification | Integrity does not establish semantic currentness, authority validity, admission, or public standing |
| Projection | Runtime temporal services and Atlas temporal cursor/chips | User-selected query coordinate and rendered projection | A projection cannot own temporal truth, infer a missing coordinate, or collapse valid, transaction, knowledge, admission and publication queries |

The strongest existing reuse path is therefore:

> Fabric and Data Forge preserve data/version history; Lex preserves legal temporal meaning; Scientist and Decision Validity preserve claim/workflow lifecycle; audit preserves integrity; OPS-R4 supplies only cross-family role names, predicates, query forms, and falsifiers.

### Current conflicts and gaps

The census identifies twelve material conflicts.

1. **Overloaded `as_of`.** The UI and runtime often expose one cursor where custody queries require at least a valid/effect coordinate and a transaction/custody cutoff, sometimes plus admission and publication coordinates.
2. **Valid/transaction collapse.** Some runtime projections assign one trace timestamp to both valid and transaction time. That is a display convenience, not an authority-safe reconstruction.
3. **Processing-time substitution.** Several models use `default_factory=now`, and the runtime audit normalizes missing/naive values. A system-generated current time cannot become source occurrence, legal effect, observation, receipt, or admission by default.
4. **Accidental universal bundle.** `TimeSourceEnvelopeAudit` assembles fifteen roles regardless of family, even though many roles are inapplicable or represented as intervals/versions/relations elsewhere.
5. **Diagnostic admission.** The audit's `mismatch_disposition="admitted"` makes a local consistency check appear to grant evidence authority.
6. **Watermark overclaim.** Fabric timestamp watermarks may derive from `source_updated_at` or fall back to `fetched_at`; other watermark types are opaque versions or offsets. None is generic proof of event-time or legal completeness.
7. **Occurrence/transaction ordering collision.** Claim Ledger v2 appends by `occurred_at`, making a late earlier-occurring event invalid even when its transaction visibility should be later and auditable.[^r-claim-lifecycle]
8. **Content/authority collision.** Fact identity appropriately excludes transaction time, but other artifact hashes or equality checks can include creation fields or ignore competence expiry. Stable bytes do not imply stable authority.
9. **Mutation vocabulary collision.** `corrects`, `revokes`, `supersedes`, `withdrawn`, and `invalidated` occur in data, legal, workflow, claim, public-record and authority contexts. The relation name alone does not identify the owner or effect.
10. **Deadline collision.** Runtime wait ceilings, obligation-owner due dates, evidence freshness, credential expiry, and external legal deadlines all use deadline/expiry language but require different owners and computation rules.
11. **Integrity/currentness collision.** Audit/signature verification can pass after a claim becomes stale or authority expires; controlled surfaces need an explicit currentness join.
12. **Projection gravity.** ADR-044 and Atlas make one time cursor a platform primitive. This is useful interaction design but unsafe as a semantic owner unless every query declares which coordinate it is controlling.

### Reuse-first conclusion

| Order | Disposition |
|---|---|
| **Wire existing** | Use Fabric valid/transaction queries and immutable mutation refs; Decision Validity dependency events and transitions; Claim Ledger lifecycle actions; Lex legal windows/versions/competence; Scientist checkpoint fingerprints; audit integrity evidence. |
| **Extend existing** | Add owner-local receipt/admission/transaction distinctions where absent; allow source temporal assertions to retain precision/uncertainty; add exact replay context references; add transaction visibility to lifecycle histories that currently rely only on occurrence order. |
| **Consolidate existing** | Define shared query names and relation predicates; qualify overloaded fields by owner/role; map currentness separately from integrity; align late-event assessments without centralizing claim reactions. |
| **Build new only if proven** | A sparse `TemporalRoleProfile`, `TemporalMutationRelation`, or `TemporalReplayReceipt` projection may be justified after repeated adapter evidence. No new temporal store, universal envelope, legal calendar, or lifecycle lattice is justified. |

## 3. External Research Baseline

### Formal temporal models

#### Interval relations

Allen's interval algebra supplies thirteen mutually exclusive qualitative relations between intervals—before/after, meets/met-by, overlaps/overlapped-by, starts/started-by, during/contains, finishes/finished-by, and equals—and a composition calculus.[^x-allen] It is a **formal algebra**, useful for observations, legal effect, competence, suspension, applicability and disputed ranges. It does not supply provenance, transaction visibility, evidence admission, authority, or public correction.

OPS-R4 uses only the needed interval predicates and preserves uncertainty. It does not require every family to store Allen relation labels; the relations may be derived from interval endpoints when endpoints are sufficiently known.

#### Bitemporal database models and SQL

Classic temporal-database work distinguishes valid time from transaction time; that distinction is the correct database base for separating current reconstruction of past reality from what a store recorded at a historical cutoff.[^x-bitemporal] ISO/IEC 19075-2 standardizes SQL support for application-time, system-versioned, and bitemporal tables.[^x-sql-temporal] This is a **database model**, not an authority model.

A bitemporal row can establish, under a specified database and transaction ordering, that a version was considered valid for interval `V` and visible for transaction interval `X`. It cannot establish that PolicyOS had custody of all underlying evidence, that a named consumer admitted the row for a purpose, that the producer was competent, or that a public claim was issued.

#### Provenance and revision

W3C PROV-O distinguishes entities, activities and agents and provides generation, invalidation, derivation, specialization and revision relations.[^x-prov] It is a **provenance model**. `prov:wasRevisionOf` and invalidation are useful semantic anchors for immutable correction lineage, but PROV-O intentionally does not prescribe PolicyOS admission, claim currentness, legal effect, or replay query coordinates.

#### Timestamp syntax and uncertain offsets

ISO 8601 standardizes representations for dates, times and intervals, while RFC 3339 provides a narrower Internet timestamp profile with explicit offsets and warns that local time plus offset is needed for unambiguous interoperable instants.[^x-iso8601][^x-rfc3339] RFC 9557 updates timestamp handling and distinguishes an unknown local offset (`-00:00`) from a known UTC offset.[^x-rfc9557] These are **serialization standards**. They do not justify converting a civil date, month, local legal date, unknown offset or disputed date into a false exact instant.

The Library of Congress Extended Date/Time Format extends ISO-style dates with uncertain, approximate, unspecified and interval forms.[^x-edtf] It is a **date-expression model** useful for preserving epistemic precision; it is not an authority calculus.

### Stream and event-time patterns

Apache Beam separates event time from processing time, uses watermarks as estimates of event-time completeness, and provides triggers and allowed-lateness behavior for revising window results.[^x-beam] Apache Flink likewise uses watermarks to indicate progress in event time, combines multiple inputs conservatively, and classifies elements behind a watermark as late under the operator's configured strategy.[^x-flink] These are **stream-processing patterns**.

Their key lesson is not “copy event time and watermark into every PolicyOS record.” It is:

- progress is scoped to a source/operator contract;
- completeness is estimated or contract-relative;
- late data requires an explicit policy;
- processing time is operational;
- output revision remains an application decision.

A stream watermark cannot prove that a legislature, court, data publisher, auditor, or citizen will never later issue an earlier-effective correction. Nor can a trigger decide whether a PolicyOS public claim should be suspended, annotated, reissued, or withdrawn.

### CDC, logs, and durable workflow history

Debezium's PostgreSQL connector exposes source-record timestamps separately from connector processing timestamps and carries log sequence/transaction metadata that can support source-local ordering.[^x-debezium] PostgreSQL logical decoding emits committed changes in commit order and omits aborted transactions.[^x-postgres-logical] These are **CDC/log implementation patterns**. They establish ordering and delivery facts only within the log/source contract; an offset or LSN is not legal effect, observation time, admission or a global clock.

Kafka idempotent and transactional processing protects duplicate writes and read-process-write pipelines within defined broker/session boundaries; official documentation also limits what those guarantees cover.[^x-kafka-producer][^x-kafka-streams] This is an **implementation pattern**. A dedupe key cannot prove that two records describe the same external act, and broker exactly-once does not make an arbitrary payment, notice, publication or other irreversible external effect exactly once.

Temporal's workflow model stores append-only event history and reconstructs workflow state by deterministic replay; workflow versioning and idempotent activity design are needed when code changes or external effects occur.[^x-temporal] This is a **durable-workflow/event-sourcing pattern**. Exact workflow replay still does not prove that the replay used the same source versions, admitted evidence, legal authority, world snapshot or publication context unless those references were recorded.

### Legal and archival temporal models

Akoma Ntoso represents legal documents and temporal metadata, including document/expression versions and lifecycle events; its force/efficacy concepts distinguish legal states that ordinary event timestamps collapse.[^x-akn] The European Legislation Identifier ontology provides identifiers and metadata for legal resources and their versions/relationships.[^x-eli] LegalRuleML explicitly separates temporal dimensions such as validity, efficacy and applicability from the substantive deadlines contained in legal provisions.[^x-legalruleml] These are **legal-informatics models**.

They support the conclusion that adoption, publication, entry into force, efficacy/applicability, repeal, consolidation and retroactivity are family-native legal concepts. PolicyOS should integrate competent assertions and Lex interpretations; OPS-R4 must not adjudicate legal effect from receipt or publication alone.

PREMIS models preservation objects, events, agents and rights and retains event outcomes and relationships needed for trustworthy archives.[^x-premis] NARA/Federal Register guidance treats published records as permanent and uses later correction or withdrawal documents rather than silently changing the original publication.[^x-nara-faq][^x-nara-correct] These are **archival/public-record models**. They strongly support immutable historical bytes and append-only correction lineage, but they do not decide claim authority.

Legal certainty doctrine also treats retroactivity as exceptional and legally constrained; a later act may alter current legal understanding of an earlier period without changing what was published or knowable before the later act.[^x-retroactivity] This is a **legal principle**, not a database update rule.

### Limits of imported patterns

| Imported pattern | Classification | Mechanically establishes | Does **not** establish for PolicyOS |
|---|---|---|---|
| Allen interval algebra | theorem/formal algebra | qualitative interval relations and composition | provenance, authority, admission, transaction visibility |
| SQL valid/system time | database model | valid and transaction-visible versions in one database | receipt, purpose-scoped admission, competence, publication history |
| PROV-O | provenance model | derivation, generation, invalidation, revision, agents/activities | legal effect, current claim standing, canonical reaction |
| RFC 3339/9557, EDTF | syntax/date-expression model | interoperable instant syntax and preserved uncertainty/precision | truth of asserted time or jurisdictional interpretation |
| Beam/Flink | stream-processing pattern | event/processing-time behavior, progress estimates, lateness policy | final source completeness, legal finality, authority reaction |
| Debezium/PostgreSQL log | CDC/log implementation | source transaction/log order and delivery metadata | global order, source-domain effect, admission |
| Kafka idempotency/transactions | implementation pattern | scoped duplicate protection and atomic broker writes | uniqueness of external acts or arbitrary irreversible effects |
| Temporal workflow history | durable-workflow pattern | deterministic replay of recorded workflow decisions | evidence parity, legal-authority parity, public-history parity |
| Akoma Ntoso/ELI/LegalRuleML | legal-informatics model | legal resource/version/lifecycle/effect/applicability vocabulary | competent adjudication in a jurisdiction or PolicyOS claim reaction |
| PREMIS/NARA correction | archival/public-record model | immutable objects, preservation events, append-only correction/publication practice | semantic currentness or authority without lifecycle owner |

**External baseline verdict:** imported models provide component algebras and implementation disciplines. The PolicyOS authority-delta is the explicit composition of source assertion, custody receipt, transaction visibility, verification, purpose-specific admission, claim dependency, claim/publication action, and immutable later mutation—under distributed ownership.

## 4. Temporal Authority-Delta

### Why ordinary bitemporal/event-time systems are insufficient

Consider a legal amendment published on day 20 with declared effect from day 1. A conventional bitemporal store can represent:

- valid/effect interval beginning day 1;
- transaction visibility beginning day 20 or later;
- a later version that corrects an earlier record.

That is necessary, but not sufficient. A PolicyOS authority-bearing claim also needs answers to the following:

1. Did PolicyOS receive the authoritative bytes on day 20, day 22, or only during a later reconciliation?
2. Was the source identity and competence verified?
3. Was the amendment admitted for the purpose, jurisdiction, population, decision and evidence policy of the claim?
4. Which claims actually depended on the superseded legal proposition?
5. Had PolicyOS already published a signed output before receipt or admission?
6. Does the later act require annotation, recomputation, suspension, revalidation, reissue, withdrawal, or human adjudication?
7. Can the exact earlier decision be replayed using only the evidence and versions visible and admitted at its historical cutoff?

Event-time and watermark systems add progress and late-data machinery, but they do not answer those custody questions. Durable workflow histories replay recorded control flow, but they do not supply missing evidence/admission/version coordinates. Archival systems retain old bytes, but they do not determine claim materiality. Legal models represent effect and applicability, but they do not grant PolicyOS admission.

### Source time versus custody time

OPS-R4 distinguishes two planes without making them two platforms.

**Source-domain plane** contains assertions about the external object:

- occurrence/act;
- effect or validity interval;
- observation/measurement interval;
- publication or source revision/version;
- family-native adoption, finality, repeal, consolidation, delivery, payment, notice or deadline facts.

These are produced by external or family-native owners. Their trust standing, precision and competence must travel with them.

**PolicyOS custody plane** contains PolicyOS-owned actions and repository facts:

- receipt of immutable bytes/assertion;
- transaction visibility in a named store/log;
- verification action and outcome;
- purpose/scope-specific admission or rejection;
- evaluation/decision action;
- lifecycle/currentness action;
- public publication/signature/correction action.

A source assertion can be received but unverified; verified but not admitted; admitted for one purpose but not another; transaction-visible but unavailable to an earlier workflow snapshot; effective in the source domain before PolicyOS received it; or received before its future effect begins. No one timestamp safely represents those states.

### Admission and authority time

Admission is not a property of evidence bytes and not a synonym for ingestion. It is an immutable PolicyOS-owned action with at least:

- admitted object/version reference;
- purpose and scope;
- authorized admitting principal or policy;
- transaction visibility;
- provenance and verification basis;
- limitations/uncertainty;
- optional validity/currentness conditions;
- relation to later revocation, supersession or revalidation.

`admitted_by(T, purpose, scope)` means that an admission action satisfying those predicates is transaction-visible at cutoff `T` and has not been revoked or superseded **at that same cutoff**. A later revocation changes current admission standing but does not make the historical admission action disappear.

Authority is conjunctive. A simplified research predicate is:

\[
Authority(c, q) = Ownership(c) \land Admission(E_c, q) \land DependencyValid(c,q) \land Competence(P_c,q) \land CurrentStanding(c,q) \land QueryHonest(q)
\]

where `q` contains explicit temporal coordinates and context. No adapter or timestamp can make a false conjunct true.

### Public and historical time

For a public claim, at least three histories coexist:

1. **Repository history:** what records and actions were transaction-visible at each cutoff.
2. **Claim/publication history:** what PolicyOS actually signed or published, when, under which context and standing.
3. **Current reconstruction:** what PolicyOS now concludes about an earlier source-valid time after later corrections, admissions or legal changes.

A later correction may change (3), may trigger a new publication in (2), and adds records to (1). It must not rewrite the earlier publication or transaction-visible history. A stale public artifact may remain cryptographically valid and historically authentic while being prohibited from a “current” surface.

## 5. Temporal Role Model

### Primitive roles

A **temporal role** describes what a temporal value means, who can assert it, and how it participates in custody. It is not a requirement that every object carry a field for every role. A role may be represented by an instant, civil date, interval, version relation, transaction sequence, provenance assertion, lifecycle event, or query cutoff.

The minimum shared vocabulary has nine primitive roles.

| Role | Definition | Universal or family-specific | Standing | Shape | May affect authority? | May be absent? | Correction behavior | Replay behavior |
|---|---|---|---|---|---|---|---|---|
| **R1 Source occurrence / act** | When an external event or act happened, was performed, decided, delivered, served, paid, adjudicated, or otherwise occurred in its source domain | Shared role; meaning and admissible evidence are family-native | Source asserted; sometimes externally observed | Instant, civil date, interval, partial order, unknown | Yes when occurrence is materially relevant; never by itself | Yes; some facts are states/versions rather than events | New assertion or relation corrects the prior assertion; old receipt/history remains | Historical replay uses only occurrence assertions visible/admitted at its cutoff |
| **R2 Source effect / validity** | When the source-domain proposition, norm, authority, licence, state, entitlement, or fact is applicable/effective/valid | Shared role; semantics are strongly family-native | External asserted and interpreted by competent family owner | Open/closed interval, date range, uncertain interval, version-conditioned interval | Often directly material | Yes when not applicable or unknown | Append revised effect assertion or legal/data version; never replace transaction history | Current reconstruction may use later revisions; historical replay may not |
| **R3 Observation / measurement** | Period or point about which a measurement, inspection, survey, audit, sensor reading, estimate, or observation speaks | Shared role; data-family meaning | Source asserted/observed | Instant, interval, reference period, cohort/window | Yes through evidentiary relevance/freshness | Yes for non-observational records | Append corrected measurement/version or relation | Replay pins the observation assertion and source version used |
| **R4 Source publication / revision / version availability** | When and in what source version an assertion or document was publicly or institutionally issued, revised, consolidated, or made available | Shared role; lifecycle details are family-native | External asserted plus source/version identity | Instant/civil date, version, revision relation | Sometimes; publication may be a legal prerequisite but is not effect by default | Yes for unpublished/internal sources | Append new source version/relation; preserve prior publication | Supports `published_by` and source-version historical views |
| **R5 PolicyOS receipt** | When PolicyOS first obtained an immutable representation or authenticated notification under a named custody channel | PolicyOS-wide custody role for received evidence | System-recorded; channel-qualified | Instant plus receipt/custody record | Enables “known by” but grants no admission | Yes for derived/internal objects | Append later receipt, reconciliation or duplicate delivery; do not backdate | Historical knowledge excludes material not received/visible by cutoff |
| **R6 Transaction visibility** | When a record/version/action became visible in a named repository, ledger or store under that store's ordering model | Universal for persisted PolicyOS records, store-scoped | System-recorded | Transaction interval, commit instant, logical sequence, offset | Indirectly; bounds what can be claimed historically | No for a persisted authority-bearing action; may be unavailable for external-only assertions | Append new version/event; no overwrite | Fundamental cutoff for repository and custody reconstruction |
| **R7 Verification** | When an identified verifier checked integrity, identity, provenance, competence, consistency or another declared predicate, with outcome and method | PolicyOS custody role; verification type is family-specific | System-recorded or accountable human action | Instant + activity/outcome relation | Yes as a required predicate; never equivalent to admission | Yes when unverified evidence is retained as observed/unadmitted | Append new verification or invalidation; preserve earlier outcome | Replay uses only verification actions visible by cutoff |
| **R8 Purpose-scoped admission** | Immutable authorized action admitting a specific object/version for a named purpose, scope, decision context and limitations | Universal for authority-bearing use; policy is consumer-owned | PolicyOS-owned accountable action | Event + scope/version relations; optional validity conditions | Directly | Yes; unadmitted evidence may remain in custody | Append admit/reject/revoke/supersede/revalidate action; never mutate prior action | Historical admitted-evidence view is evaluated at a transaction cutoff and purpose/scope |
| **R9 PolicyOS claim/publication/lifecycle action** | When PolicyOS evaluated, signed, published, marked stale, suspended, corrected, superseded, reissued, withdrew, archived or otherwise acted on its own claim/record | PolicyOS-wide role; vocabulary remains canonical-owner native | System-recorded/accountable human | Event, state transition, publication relation | Directly | No for an action that is claimed to have occurred | Append lifecycle/publication event and retained relation | Reconstructs actual historical standing/publication separately from recomputation |

These roles are irreducible because collapsing any adjacent pair creates a concrete authority error:

- effect into occurrence misstates future-effective or retroactive rules;
- observation into publication misstates the period measured;
- publication into receipt pretends PolicyOS had timely custody;
- receipt into transaction visibility ignores persistence and store order;
- visibility into verification or admission launders stored bytes into authority;
- admission into decision/publication erases the canonical consumer's responsibility;
- processing time into any source/custody role fabricates semantic facts.

### Derived roles and predicates

The following should normally be derived from primitive records, relations and query coordinates rather than persisted as universal timestamps.

| Derived concept | Research definition | Persistence guidance |
|---|---|---|
| `known_by(object, X)` | A custody representation was received and transaction-visible by cutoff `X`, with resolvable provenance; it need not be verified, admitted, authoritative or current | Persist receipt and transaction facts; derive predicate |
| `verified_by(object, X, predicate)` | A successful verification activity for the named predicate was visible by `X` and not invalidated at `X` | Persist verification events/outcomes; derive standing |
| `admitted_by(object, purpose, scope, X)` | A matching admission action was visible by `X` and remained in force at `X` | Persist owner-native admission lifecycle; derive predicate |
| `current_at(claim, X)` | Canonical claim owner considered the claim current under its lifecycle and dependencies at cutoff `X` | Persist lifecycle actions/dependency evidence; derive currentness |
| `late(relative_to)` | Receipt/transaction visibility occurred after a declared window, cutoff, expected order or source-contract progress coordinate | Do not persist one global enum; persist assessment basis and relation |
| `retroactive` | An assertion/version visible or published later claims effect over an earlier source-valid interval | Derive from effect and publication/receipt/transaction relations; retain competent assertion |
| `stale` | Evidence or claim exceeded an owner-defined freshness/currentness condition without necessarily being false | Persist lifecycle/currentness action, not a generic expiry clock |
| `expired` | A named authority, evidence licence, admission condition, freshness policy or retention entitlement ceased under its owner | Persist owner-specific expiry assertion/action; never one universal field |
| `review_due` / `correction_due` | PolicyOS-owned custody duty reaches its due coordinate | Persist owner-specific obligation/job; do not compute external legal deadlines |
| `replay_cutoff` | The set of transaction, admission, publication, world, rule and workflow version coordinates needed by a declared replay mode | Persist exact references in a replay receipt where warranted; not a single time |
| `processing_time` | Worker/runtime wall-clock timing of acquisition, queueing, execution, retry or projection | Operational telemetry; excluded from semantic authority unless the claim is about that timing |

### Family-native roles

The shared profile does not replace family-native meanings. Examples include:

- **Fabric/data:** observation/reference period, release vintage, source revision, fact valid interval, world-store transaction interval, source offset and watermark confidence.
- **Legal:** adoption, signature, promulgation, publication, entry into force, efficacy, applicability, repeal, annulment, consolidation, finality, retroactivity and competence windows.
- **Workflow:** scheduled wake, wake occurrence, wake receipt, checkpoint sequence, retry attempt, lock lease, suspension interval and resume cutoff.
- **Authority:** delegation issue/expiry, licence or mandate interval, reviewer competence, admission validity conditions, decision evaluation and revalidation due.
- **Public record:** publication, signature, correction notice, withdrawal, supersession, archive transfer and public-currentness.

Those roles should be exposed through adapters only when a consumer needs cross-family comparison. An adapter maps evidence; it does not reinterpret a family-native date or grant authority.

### Uncertainty and precision

A temporal value used for authority must preserve at least the information needed to avoid false precision:

\[
\tau = \langle lexical,\ calendar,\ zone,\ precision,\ bounds,\ closure,\ basis,\ confidence,\ dispute\_set \rangle
\]

Not every implementation needs that exact structure. The semantic requirements are:

1. **Lexical preservation.** Retain the source form where legally or epistemically material, such as `2026-07`, “effective on publication”, or a local civil date.
2. **Calendar and jurisdiction.** Record the calendar and interpretation rule when not safely Gregorian/UTC.
3. **Offset honesty.** Known UTC, known numeric offset, named zone, unknown offset, and no zone are distinct.
4. **Precision monotonicity.** A day cannot be promoted to a second; a month denotes a range unless the source defines another convention.
5. **Open/closed endpoints.** Applicability at a boundary may be material; do not silently assume inclusive or half-open semantics.
6. **Uncertain bounds.** Represent earliest/latest possible start/end or an explicit unknown; do not substitute processing time.
7. **Conflicting assertions.** Retain competing source assertions and provenance. A derived merged interval may be offered as an analytical view but cannot erase the conflict.
8. **Clock quality.** Device-clock trust, clock skew and backdating indicators are provenance/quality evidence, not automatic corrections.
9. **Authority monotonicity.** Reducing temporal precision or timezone certainty cannot increase authority. Where the distinction is material, the action fails closed or requires competent adjudication.
10. **Future-dated records.** Separate a future-effective source assertion from an implausible or untrusted future device timestamp.

## 6. Temporal Relation and Query Algebra

### Instants and intervals

Let:

- `T` be a partially ordered set of temporal coordinates. A total order is available only where a source/store contract supplies one.
- `I` be intervals over `T` with explicit start/end closure and possibly uncertain bounds.
- `V(o)` be the source effect/validity interval asserted for object `o`.
- `O(o)` be an observation/measurement interval.
- `P(o)` be source publication/version availability evidence.
- `R(o)` be one or more PolicyOS receipt events.
- `X_s(o)` be transaction visibility in store or ledger `s`.
- `G(o,k)` be verification of predicate `k`.
- `A(o,p,s)` be an admission action for purpose `p` and scope `s`.
- `C(c)` be PolicyOS claim/publication/lifecycle actions for claim `c`.

A conceptual temporal assertion is:

\[
a = \langle id,\ subject,\ role,\ value,\ owner,\ provenance,\ precision,\ transaction\_visibility \rangle.
\]

This is an algebraic description, not a required persisted envelope. Family contracts may encode the same information as fields, versions, event records, provenance graphs or query parameters.

For intervals, OPS-R4 adopts the useful Allen-style predicates `before`, `meets`, `overlaps`, `starts`, `during`, `finishes`, `equals` and their inverses. Additional custody predicates are kept separate.

Examples:

- `effective_during(o, t) := t ∈ V(o)` under the family owner's boundary interpretation;
- `observed_over(o, i) := O(o) = i` or has a declared Allen relation to `i`;
- `disputed_effect(o) :=` two or more competent assertions about `V(o)` are not mutually consistent and no authorized resolution is visible at the query cutoff.

### Valid and transaction visibility

For a bitemporal record `r` in store `s`:

\[
Visible_s(r; v,x) := v ∈ V(r) \land x ∈ X_s(r).
\]

If the record has a point valid coordinate rather than an interval, the store's documented point-selection rule applies. `Visible` establishes database visibility, not custody admission.

Store transaction orders are scoped. If two stores do not share a certified transaction sequence, their commit timestamps provide at most an asserted/observed wall-clock order subject to skew. Cross-store historical queries must either:

- use a recorded release/snapshot that joins the stores;
- use per-store cutoffs in an exact replay context; or
- state that the reconstruction is approximate/non-atomic.

### Custody predicates

For cutoff `x` in the relevant custody store:

\[
Known(o,x) := \exists r \in R(o): X(r) \le x \land ProvenanceResolvable(r,x).
\]

`Known` means “PolicyOS had a recorded custody representation available under the declared repository cutoff.” It does not mean true, verified, admitted, competent or considered by a specific run.

\[
Verified(o,k,x) := \exists g \in G(o,k): X(g) \le x \land outcome(g)=pass \land \neg Invalidated(g,x).
\]

\[
Admitted(o,p,s,x) := \exists a \in A(o,p,s): X(a) \le x \land outcome(a)=admit \land \neg RevokedOrSuperseded(a,x).
\]

For a claim `c` and decision context `d`:

\[
Used(c,o,d) := DependencyDeclared(c,o,d) \land ContextPins(d,o).
\]

This prevents “all records known by PolicyOS” from being conflated with “records actually used by the decision.”

### Correction, revocation, supersession, and derivation

Mutation relations are typed, directional and immutable:

- `corrects(n,o,aspect,basis)` means new record `n` asserts that a specified aspect of old record `o` was erroneous or incomplete. It does not necessarily terminate all uses of `o`.
- `revokes(n,o,scope,basis)` means an authorized act withdraws standing/effect for `o` in the declared scope. It does not erase prior existence or necessarily negate historical effect.
- `supersedes(n,o,scope,basis)` means `n` becomes the preferred/current successor for the declared scope while preserving `o` as a historical version.
- `derived_from(n,o,method,version)` records derivation without implying correction or authority.
- `valid_under(o,v)` binds an assertion or result to a source/rule/workflow/version context.
- `authority_withdraws(n,principal_or_act,scope)` changes authority standing even when evidence bytes remain identical.

Relations are not transitive by default. For example, if `B corrects A` and `C corrects B`, a consumer may select `C` as current for a specific aspect, but it must not infer that `C` revokes every historical use of `A`.

A relation may be **unresolved** when its target has not yet arrived. `pending_relation(n,target_id,type)` is a valid custody state. The relation becomes resolved by append when the target arrives; the transaction history remains `n` first, target later.

### Retroactivity

For an assertion `o` with effect start `v_start`, source publication `p`, PolicyOS receipt `r`, or transaction visibility `x`:

\[
Retroactive_{publication}(o) := p > v_{start}
\]

\[
Retroactive_{custody}(o) := x > v_{start}.
\]

These predicates describe temporal relations; they do not decide whether the source is legally entitled to retroactive effect or what PolicyOS must do. A competent legal assertion may be admitted as `declared_retroactive`; a disputed act remains a set of competing assertions plus a competent-human requirement.

### Expiry and deadlines

`expires_at` is never sufficient without an owner-qualified predicate:

- `evidence_freshness_expires(e,purpose,t)`;
- `admission_condition_expires(a,t)`;
- `authority_expires(principal,scope,t)`;
- `credential_expires(credential,t)`;
- `retention_eligibility_ends(object,t)`;
- `review_due(claim,t)`;
- `external_deadline_asserted(matter,t,basis,competent_owner,uncertainty)`.

Only the first six may be PolicyOS-owned depending on the canonical owner. The last is integrated evidence and may not be independently recomputed by OPS-R4.

### Query semantics

No unqualified query named “as of T” is authority-safe. The minimum query forms are:

| Query form | Required coordinates/context | What it may claim | What it may not claim |
|---|---|---|---|
| **Current view** `current(owner, context, now)` | Current valid/effect coordinate or owner-defined current rule; latest transaction cutoff; current admission/dependency/currentness policies | What the canonical owner currently presents as current | What PolicyOS historically knew or published |
| **Valid-time historical view** `valid_view(v; tx=current)` | Source-valid/effect coordinate `v`; current transaction cutoff | Current reconstruction of the source/world at historical valid time `v` | Historical PolicyOS knowledge or actual past publication |
| **Transaction-time historical view** `tx_view(x)` | Named store/ledger and transaction cutoff `x` | Which records/actions were visible in that store by `x` | Their source effect, admission, truth or use by a decision |
| **Historical PolicyOS-knowledge view** `knowledge_view(x, custody_scope)` | Receipt and transaction cutoff; custody channels/stores | What custody representations PolicyOS had recorded by `x` | That they were verified, admitted, authoritative or used |
| **Historical admitted-evidence view** `admission_view(purpose, scope, x)` | Purpose, scope, admitting owner/policy version, transaction cutoff | Which object versions were admitted and not revoked/superseded at `x` | That every admitted object was used or the resulting claim was valid |
| **Historical publication view** `publication_view(surface, x_or_publication_id)` | Public-record owner/surface, publication records, transaction/publication cutoff | What PolicyOS actually signed/published and its then-recorded standing | A recomputed answer using later evidence |
| **Current reconstruction of past valid time** `reconstruct(v, tx=current, policies=current_or_declared)` | Historical valid/effect coordinate plus current or explicitly versioned interpretation/admission policy | What PolicyOS currently concludes about past `v` | What PolicyOS knew, admitted or said then |
| **Exact replay of past decision context** `replay(decision_ref, receipt)` | Historical transaction cutoffs per store; admitted evidence versions; world/data snapshots; legal/NormPack versions; workflow fingerprint; model/tool/config versions; authority/delegation context; randomness/external-call receipts where material | Whether the recorded decision can be reproduced under the recorded context and what that context contained | Current correctness, current authority, or equivalence to a current reconstruction unless separately established |

Three frequently confused questions therefore have distinct answers:

- **“What would PolicyOS currently say about the world at historical time T?”** — `reconstruct(valid=T, tx=current)`.
- **“What did PolicyOS know/admit at historical cutoff T?”** — `knowledge_view(tx=T)` and `admission_view(..., tx=T)`.
- **“What did PolicyOS actually say using only the context available then?”** — historical publication record and/or exact replay receipt at the decision's historical cutoffs.

The first may change after a retroactive correction. The second and third are append-only historical facts.

## 7. Late, Duplicate, Out-of-Order, and Retroactive Events

### Lateness assessment

Lateness is not an intrinsic global enum. An object is late **relative to** a declared expectation: a source progress contract, transaction cutoff, evaluation window, scheduled wake, public publication, legal-effect start, or dependency epoch.

A `LateEventAssessment` is advisory evidence produced by the temporal adapter/consumer boundary. It must include, conceptually:

- source family and canonical source owner;
- asserted temporal role/value/precision;
- receipt and transaction visibility;
- relation to the relevant cutoff/window/watermark;
- whether it corrects, revokes, supersedes, withdraws, or merely arrives late;
- dependency and authority materiality;
- affected claims/publications known at the assessment cutoff;
- current public standing;
- window closed/open status;
- reversibility of any protected effect;
- competent-human requirement;
- recommended minimum reaction category and limitations.

#### Decision procedure

1. **Admit no authority from arrival alone.** Record receipt/transaction history and provenance.
2. **Resolve identity class.** Distinguish duplicate delivery, duplicate source record, repeated assertion of one act, distinct equivalent act, correction, revocation, supersession, retry, or duplicate protected effect.
3. **Resolve temporal relation.** Compare source occurrence/effect/publication to receipt, transaction cutoff, relevant window and source-contract progress. Preserve uncertainty.
4. **Resolve mutation standing.** Determine whether a competent relation is asserted and whether its target is present, missing, disputed or outside the source family's competence.
5. **Trace declared dependencies.** Ask canonical claim consumers whether the object/version or proposition is materially dependency-bearing. Temporal infrastructure does not invent the affected set.
6. **Check authority dependency.** A competence expiry, revocation, legal invalidation or admission withdrawal is material even if payload/content is unchanged.
7. **Check public standing and irreversibility.** A published or operationalized claim requires stronger minimum handling than an unpublished reversible computation.
8. **Check cutoff/window status.** Preserve closed historical computation; decide current reaction separately.
9. **Escalate uncertainty.** If effective time, competence, identity, jurisdiction or deadline is materially disputed, require the competent human/owner and fail closed for authority-dependent action.
10. **Recommend a minimum reaction.** The canonical claim consumer chooses and records the actual lifecycle action.

#### Reaction categories

| Category | Minimum semantic reaction | Appropriate when | Prohibited inference |
|---|---|---|---|
| **L0 Retain only** | Append custody/delivery history; no claim change | Non-material duplicate delivery, irrelevant observation, or evidence outside declared dependency/scope | Do not discard the record or claim it was timely |
| **L1 Annotate** | Add provenance/limitation/current-context annotation | Non-material late information that improves transparency but does not alter claim support/authority | Annotation cannot substitute for recomputation when dependency is material |
| **L2 Update current context** | Update current source/world/legal context without changing the historical claim/publication | Late fact changes current understanding but the earlier claim was honest and is no longer a controlled current output, or dependency is immaterial | Do not rewrite the historical result |
| **L3 Recompute materially dependent current claim** | Re-run the owning computation using current admitted context; preserve old result | Material evidence affects a reversible, still-current or open evaluation and authority remains valid | Recompute does not erase or retroactively replace the old publication |
| **L4 Suspend/freeze and require revalidation** | Prevent controlled current use; open owner revalidation | Authority/competence/admission may have failed, material public harm is possible, or effect/time is uncertain | Temporal adapter cannot decide the final validity state |
| **L5 Open a new epoch and reissue/supersede/withdraw** | Preserve old epoch; create new decision/publication lineage with explicit relation | Material correction after publication, changed legal/authority regime, changed purpose/scope, or non-equivalent context means the old decision cannot simply be recomputed in place | Do not mutate old claim bytes or pretend the new epoch existed earlier |
| **L6 Competent-human adjudication** | Freeze authority-dependent action within affected scope and route to the competent owner | Disputed legal effect, identity, finality, tolling, jurisdictional date meaning, correction authority, or irreversible public harm | No automated default from receipt time, watermark or source `required_action` |

#### Input-to-minimum-reaction table

| Mutation / dependency / standing | Unpublished and reversible | Published/current but reversible | Irreversible or material public effect | Time/competence disputed |
|---|---|---|---|---|
| Duplicate delivery; same scoped event identity; no new source assertion | L0, idempotent effect | L0, audit both attempts | L0 plus protected-effect idempotency evidence | L6 only if identity itself disputed |
| Late but immaterial new evidence | L0 or L1 | L1 or L2 | L1 plus owner review if harm-sensitive | L6 where materiality cannot be resolved |
| Material late evidence; no authority change | L3 if window/current claim remains open; otherwise L2 | L3 and preserve publication | L4 then owner decides L3/L5/remedy | L6 |
| Competent correction/supersession of depended-on input | L3 | L4 then L3 or L5 | L4/L5 and public correction/remedy owner | L6 if relation/effect disputed |
| Revocation/authority expiry/admission withdrawal | L4 | L4, freeze current surface | L4/L5; affected-set/remedy process | L6 where competence/finality disputed |
| Retroactive source effect discovered after decision | L3 for current context; preserve old replay | L4 then L5 if public standing changes | L4/L5 plus remedy escalation | L6 for legal effect/adjudication |
| Future-effective publication | L2/preparation; no premature invalidation | L2, schedule owner revalidation if required | Owner-specific preparation controls | L6 if effective date disputed |
| Closed historical computation with no controlled current use | L0/L2; retain exact history | L2 unless publication still presented as current | Owner review based on harm | L6 as needed |

**Final reaction ownership:** the canonical claim/publication consumer—Decision Validity, Scientist Claim Ledger, legal decision owner, public-record owner, or another established owner—records the actual reaction. Fabric, temporal adapters, Atlas and source payloads may only supply evidence and advisory assessment.

### Watermark semantics

A Fabric watermark proves only what its named type, source contract, partition/scope, extraction policy and confidence define.[^r-watermark][^r-processing]

- A timestamp watermark may prove that the connector has processed or observed records up to a source update/retrieval coordinate under the current run.
- An offset watermark may prove a consumed source-log position within a partition/log contract.
- An ETag or revision watermark may prove the last observed opaque source version.
- A schema watermark may prove the schema version processed.
- A cursor may prove the resume position committed by the cursor store.

It does **not** prove:

- that all real-world events effective before that coordinate exist in the source;
- that no publisher will issue an earlier-effective correction;
- that legal effect or institutional finality is settled;
- that PolicyOS received every out-of-band notice/webhook;
- that the source record was verified or admitted;
- that every downstream claim was recomputed;
- that a timestamp fallback from `fetched_at` is event time;
- that progress in one partition/source is a global order;
- that an advanced watermark makes a public claim current.

A completeness claim requires a separate source contract stating the relevant guarantee, scope, correction behavior, reconciliation process and residual uncertainty. Even then, the claim is contractual/empirical, not metaphysical finality.

### Deduplication

OPS-R4 distinguishes six identity questions.

| Identity question | Candidate evidence | What it can prove | What it cannot prove |
|---|---|---|---|
| Duplicate message delivery | producer namespace + event/message ID + channel + idempotency scope | Same delivery identity under the producer contract | Same external act, same content semantics, or competent correction |
| Duplicate source record | stable source record/version ID and source contract | Same source object/version was sent twice | Whether two source records denote one real-world act |
| Repeated assertion of the same external act | competent act identifier, issuer, jurisdiction, publication lineage | Same asserted act under source semantics | That text equality or timestamps alone establish identity |
| Distinct but semantically equivalent acts | distinct competent publication/act IDs, even with equal content hash | Legal/institutional identity remains distinct | Content hash must not collapse them |
| Retry of a PolicyOS action | action/effect idempotency key scoped to canonical consumer and target | One protected PolicyOS effect or equivalent result | Exactly-once arbitrary external effect without an effect-specific protocol |
| Duplicate irreversible effect | target-system receipt/effect ID, transactional outbox/ledger, reconciliation evidence | At-most-once or equivalent protected effect under that protocol | That message dedupe alone prevented double payment/notice/publication |

Deduplication identity must include the namespace and effect scope. Content equality, identical timestamps, and a shared event ID are never universally sufficient. Corrections and superseding acts must remain new immutable records even when payloads are similar.

### Retroactivity

The following cases require different handling.

1. **Legal act published now, effective earlier.** Record publication/receipt/transaction now and asserted effect interval earlier. Historical knowledge/publication remains unchanged; current legal reconstruction may change; dependent current claims are assessed and possibly revalidated. Legal entitlement to retroactivity remains a Lex/competent-owner question.
2. **Dataset revision for an earlier observation period.** Preserve original release/version and observation interval; append revised version/correction relation. Current analyses may recompute; exact past replay pins the old release.
3. **Correction arrives before original.** Persist the correction and unresolved target relation at its actual receipt/transaction time. Apply bounded buffering/reconciliation according to source contract, but never discard. When the original arrives, append it and resolve the relation without reordering history.
4. **Authority revocation discovered after decision.** Content stays stable; authority standing changes at the competent revocation/effect interval and at the later PolicyOS receipt cutoff. Affected current claims enter scoped revalidation; historical claim context remains reproducible.
5. **Future-effective rule published in advance.** Record publication and future effect separately. Do not invalidate current claims early unless a family owner establishes preparation/transition duties; schedule revalidation if PolicyOS owns that duty.
6. **Disputed effective date.** Preserve competing assertions and precision; fail closed for materially authority-dependent action; route to competent adjudication.
7. **Date/month/interval rather than instant.** Preserve the range and boundary semantics. Do not use UTC midnight or end-of-month as semantic truth without an explicit interpretation basis.

The invariant is:

> Retroactivity may change current understanding of the past and what PolicyOS must do now; it never changes what PolicyOS had received, admitted, known, decided or published at an earlier historical cutoff.

### Deadline boundary

PolicyOS owns only deadlines that arise from its own custody and authority duties, for example:

- evidence freshness expiry under an evidence policy;
- scheduled claim/authority revalidation;
- reviewer or correction due dates for a PolicyOS-owned record;
- delegation, licence, credential or mandate expiry when PolicyOS is the authoritative custodian of that grant;
- retention verification or archival transfer checkpoints;
- suspension review and wake/resume due times.

PolicyOS may integrate competent assertions about external filing windows, service/notice periods, appeal deadlines, tolling, statutory grace periods, payment/procurement dates, court finality and institutional calendars. It may use those assertions as claim inputs and fail closed when uncertainty is material. OPS-R4 does not authorize an independent holiday/tolling/legal-calendar engine or operational administration of those deadlines.

## 8. Minimal Interoperability Decision

### Alternatives considered

| Alternative | Semantic loss | Owner gravity / P13 risk | Migration cost | P27 owner-preemption risk | Authority laundering risk | Replay adequacy | Legal/institutional compatibility | Benchmarkability | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| **A. One universal persisted `OperationalEventEnvelope`** | High: forces occurrence, effect, publication, observation, receipt, admission and processing into one shape; intervals/versions/relations become fake timestamps | Very high; creates a new central temporal platform | Very high across Fabric, Lex, Scientist, Data Forge, audit and public records | Very high; pre-empts canonical family owners without evidence | Very high; mere presence in envelope appears authoritative | Superficially convenient but semantically unreliable | Poor; legal and institutional meanings do not fit one bundle | Easy syntactically, misleading semantically | **Refuted** |
| **B. Thin shared persisted identity/mutation header on every event** | Medium: identity namespace, relation target and transaction ref may help, but mandatory headers still misfit non-event/version/interval records | Medium-high; header tends to grow into envelope | Medium-high | Medium | Medium if header is interpreted as admission/currentness | Useful for delivery and lineage, insufficient for exact replay | Mixed; legal acts need richer identity/competence/version data | Good for transport fixtures | **Research candidate only at proven boundaries; not universal** |
| **C. Family-native events/contracts with shared temporal roles, relations and query semantics** | Low: preserves native legal/data/workflow/public meaning | Low if profile remains semantic and adapters cannot mint authority | Low-to-medium, incremental adapters | Low; owners persist/react | Low when admission and reaction remain canonical-owner actions | High when exact replay receipt pins family versions/cutoffs | High | High through common predicates and fixture mappings | **Recommended** |
| **D. No shared persisted contract; only ad hoc adapters and benchmark mappings** | Low locally but high cross-family ambiguity | Low central gravity | Low initially, recurring adapter cost | Low | Medium through inconsistent translations | Variable and difficult to audit | High locally | Weak; fixtures cannot name stable predicates | **Insufficient alone** |

### Recommended architecture

**Explicit verdict:** only a **thin shared temporal role profile plus shared relation/query semantics** is justified. Persisted events and fields remain family-native, connected by adapters. No shared persisted temporal envelope is justified.

The interoperability layer contains:

1. the nine sparse role names and their authority/trust definitions;
2. interval and uncertainty semantics;
3. store-scoped transaction visibility;
4. custody predicates (`known_by`, `verified_by`, `admitted_by`, `used_by`, `published_by`);
5. typed immutable mutation relations;
6. explicit query kinds and replay coordinates;
7. late-event assessment inputs and minimum reaction categories;
8. benchmark predicates and metamorphic falsifiers.

It does **not** contain:

- a required clock list;
- a universal event ID scheme;
- a global transaction order;
- a central admission service;
- a canonical claim lifecycle;
- a legal effect engine;
- an administrative deadline service;
- an Atlas-owned truth model;
- a production H2 wire contract.

### Disposition of `OperationalEventEnvelope`

The original backlog proposal does not survive as a universal artifact. Its useful intent—preserve event identity, source/custody distinction, duplicate/correction lineage, and late-event evidence—is satisfied more safely by family-native records plus shared predicates.

A future thin header may be prototyped only if repository evidence shows repeated transport-boundary duplication. It may contain, at most, owner-qualified event/record identity, producer namespace, immutable target relation(s), and transaction/audit reference. It must not require every temporal role, contain a universal `required_action`, decide admission, or become the source of legal effect/currentness.

### Disposition of `TimeSourceEnvelopeAudit`

The current object is classified as follows:

| Question | Verdict |
|---|---|
| Local audit projection? | **Yes.** It composes runtime, catalog and source values for one Layer-3 quality check. |
| Reusable diagnostic composition? | **Only after narrowing.** Sparse role mappings and explicit source contracts could make the consistency checks reusable. |
| Accidental universal envelope? | **Yes in current shape.** It requires a fixed fifteen-role bundle and normalizes values across unrelated domains. |
| Authoritative semantic owner? | **No.** Runtime quality cannot own legal effect, source observation, admission, retention, replay or claim reaction. |
| Candidate requiring narrowing? | **Yes.** |

Required future-planning disposition, without code change in this task:

1. treat it as a **projection only**;
2. narrow and preferably rename it to a consistency-audit name such as `TimeSourceConsistencyAuditProjection`;
3. remove `admitted` from `mismatch_disposition`; use diagnostic outcomes such as `consistent`, `inconsistent`, `insufficient_evidence`, `blocked_for_owner_review`;
4. accept sparse family-native roles rather than demanding all fields;
5. delegate legal effect/competence to Lex and source progress to Fabric contracts;
6. never derive missing source time from processing time or a generic year/default;
7. never equate watermark freshness with semantic completeness;
8. map `replay_time` to an explicit replay query/receipt rather than one timestamp;
9. ensure tests falsify valid/transaction collapse, false precision and authority laundering.

Until that narrowing is accepted by the relevant owners, the current audit is local evidence about one proving-ground composition and must not be cited as the PolicyOS temporal contract.

## 9. Fixtures and Falsifiers

### Required edge fixtures

The fixtures are implementation-neutral specifications. “Executable now” means existing repository primitives are sufficient to express and test the core invariant without authorizing a production contract. “Partial” means some primitives exist but the cross-family authority assertion or adapter is missing. “Proposed” means the fixture belongs in later OPS-R15/S0-GAP-02 work.

| Fixture | Input events and temporal roles | Ordering | Expected invariants | Prohibited result | Relevant repository primitive | Later owner | Executability |
|---|---|---|---|---|---|---|---|
| **T-01 — Duplicate amendment** | `E1`: amendment notification, source event ID `A-17`, publication/effect assertion, receipt `r1`, tx `x1`; `E2`: same producer namespace/event ID and payload, receipt `r2`, tx `x2` | `x1 < x2`; source identity equal | One source assertion or one deduplicated delivery identity; one protected PolicyOS trigger/effect; both delivery attempts and receipts auditable; no change to source publication/effect | Two lifecycle invalidations, reissues, notices or other irreversible effects | Fabric `dedupe_key`; DecisionDependencyEvent `event_id`/`dedupe_key`; audit log | source adapter + canonical claim consumer | **Executable now for scoped delivery dedupe; partial for protected external effect** |
| **T-02 — Semantically equivalent but distinct amendment** | `E1` and `E2`: distinct official publication/act IDs, equal normalized text/content hash, possibly same effect interval | Any publication/receipt order | Two legal identities and publication histories remain distinct; content similarity may support semantic comparison only; each competence/provenance evaluated separately | Collapse to one act because bytes/hash/timestamp match | Lex/Data Forge document/version IDs; source provenance; fact-ID/content-hash rules | OPS-R10/11 + Lex | **Proposed cross-family fixture; components exist** |
| **T-03 — Correction before original** | `C`: competent correction refers to source record `O`, arrives/records at `x1`; `O`: delayed original arrives at `x2`; source occurrence/effect may place `O` earlier | `x1 < x2`, while source relation says `C corrects O` | Persist `C` with unresolved target; retain receipt/transaction order; bounded buffer/reconciliation may wait but cannot discard; append `O` at `x2`; resolve relation by append; current view follows family policy | Reorder transaction history, overwrite `C`, silently drop either object, or treat processing order as source order | Fabric immutable mutation refs; source-truth custody; claim-ledger gap identified by C062 | source-family owner + adapter | **Partial; Fabric relation exists, unresolved cross-family relation fixture proposed** |
| **T-04 — Retroactive legal effect** | Legal act published `p=day20`, received/visible `x≥day20`, competent assertion `effective_from=day1`; claim/publication existed at day10 | effect start `<` historical claim cutoff `<` publication/receipt | Knowledge/admission/publication at day10 unchanged; current legal reconstruction for valid day10 may change; affected current claims assessed; old publication retained; legal retroactivity competence not inferred by runtime | Backdate receipt/admission, rewrite day10 claim, or equate publication with effect | Lex effective/competence windows; Fabric valid/tx view; Decision Validity/Claim Ledger | OPS-R10/11 + claim owner + public record owner | **Partial/proposed integration fixture** |
| **T-05 — Late data after a closed window** | Material observation for reference interval `V` arrives after evaluation/publication cutoff `x_pub`; receipt/tx later; declared dependency on relevant metric | observation interval before window close; receipt after close/publication | Historical result remains reproducible; late evidence is retained; dependency/materiality determines L2/L3/L4/L5; current recomputation produces a new result/ref; old public record unchanged | Silent mutation of closed aggregate/publication or global “drop all late data” | Fabric late/out-of-order policy; snapshots; Decision Validity; Claim Ledger | data claim owner + PAO-R36 | **Partial; stream mechanics executable, custody reaction proposed** |
| **T-06 — Processing-clock contamination** | Same semantic source assertion/version processed by workers `W1` and `W2` at different worker start/end/receipt-retry times, with same constitutive source temporal assertion and admission context | Processing times differ; semantic inputs equal | Semantic fact/artifact identity and authority result equal; operational audit differs; transaction records may differ only as declared | Hash, legal identity, claim content or authority changes solely because worker time changed | `build_fact_id` excludes `tx_time`; workflow fingerprints; audit timestamps | Fabric/artifact owners + OPS-R15 | **Executable now for Fabric identity; broader metamorphic fixture proposed** |
| **T-07 — Watermark false completeness** | Timestamp watermark advances beyond day20 under source contract; later competent correction arrives with effect day5 and receipt day25 | watermark advance before correction receipt; effect earlier | Watermark remains evidence of prior progress only; correction is accepted as late/retroactive; current context and dependent claims assessed; source completeness claim records limitation | Reject correction as impossible, rewrite its effect to receipt time, or assert no earlier-effective facts exist | Fabric watermark types/fallback; processing guarantee; late assessment | Fabric source-contract owner + claim owner | **Partial; watermark mechanics executable, authority falsifier proposed** |
| **T-08 — Duplicate irreversible action** | Two workers consume same admitted temporal trigger and attempt one protected effect (e.g., publish correction or send controlled instruction) with same effect-scoped idempotency key | Attempts concurrent or reordered | At most one protected effect, or two attempts converge to an equivalent idempotent state; both attempts and final effect receipt auditable; claim reaction recorded once | Duplicate publication/payment/notice merely because each worker had a valid message | Decision/event dedupe; control worker idempotency; audit; transactional effect protocol where available | canonical effect owner | **Partial; internal idempotency testable, arbitrary external effect requires owner protocol** |
| **T-09 — Wrong timezone or date precision** | Source supplies local civil date `2026-10-25` with no offset/zone; another adapter proposes UTC midnight; materially different jurisdictional interpretation possible | Same lexical source; alternative normalizations | Preserve lexical date, precision and unknown zone; derive an interval/alternatives only with explicit basis; lower certainty cannot increase authority; material action fails closed | Assert exact UTC instant, choose DST offset silently, or admit stronger authority after losing zone information | legal/Data Forge parser and quality issues; temporal profile uncertainty | source family + Lex/competent human | **Proposed; parser-level components exist** |
| **T-10 — Future-effective publication** | Binding source publishes version `v2` now (`p0`, `r0`, `x0`) with effect start `v_future`; current version `v1` remains effective | publication/receipt before effect start | Record future applicability and version; current claims remain under `v1`; owner may schedule preparation/revalidation; at effect boundary, current reconstruction changes; replay before/after remains version-correct | Prematurely invalidate current claims merely because `v2` was received, or ignore known future effect | Lex effective windows/version selection; lifecycle jobs | OPS-R10/11 + claim owner | **Partial/executable in legal-window components; end-to-end fixture proposed** |
| **T-11 — Revoked authority with unchanged payload** | Evidence bytes/hash unchanged; producer competence/mandate expires or is revoked at `t_exp`; claim remains otherwise identical | content version before and after `t_exp`; authority interval ends | Integrity/content equality passes; current authority predicate fails after expiry; materially dependent claims enter scoped revalidation; historical pre-expiry use remains reproducible | Preserve current authority because content hash is unchanged, or mutate historical signature | Lex competence windows; security expiry; Decision Validity; audit | OPS-R2 + authority/claim owner | **Partial; competence tests exist, cross-claim fixture proposed** |
| **T-12 — Lost webhook found by census** | Source event effective at `v1` was not delivered; reconciliation/census discovers it at receipt/tx `x2`; source publication/record proves earlier existence | source effect/publication earlier; PolicyOS receipt later | Record late discovery and reconciliation method; do not pretend timely receipt; evaluate material dependencies/current public standing; preserve earlier knowledge view as lacking event | Backdate receipt/transaction, erase monitoring gap, or treat source timestamp as proof PolicyOS knew | source cursor/watermark, reconciliation records, source-truth, Decision Validity | Fabric/source adapter + claim owner | **Proposed integration fixture** |
| **T-13 — Public record cryptographically valid but stale** | Signed artifact and signature verify; later lifecycle/dependency event marks claim stale/superseded/revoked; archive retains original | publication/signature before later lifecycle action | Integrity and historical authenticity remain true; `current` predicate false; controlled surfaces hide/de-emphasize it as current and link successor/correction; archive remains accessible | Treat valid signature as current authority, delete historical artifact, or rewrite signed bytes | core audit/signature; Claim Ledger/Decision Validity; Atlas projection | PAO-R36 / INT-R7 / INT-R8 / Atlas | **Partial; integrity and lifecycle components exist, public-currentness join proposed** |
| **T-14 — External deadline with tolling uncertainty** | Competent source asserts filing/appeal deadline `D`; another competent assertion raises tolling/holiday/service uncertainty; PolicyOS claim depends materially on timeliness | assertions visible at different cutoffs; no authorized resolution yet | Retain both assertions/provenance/precision; classify deadline as integrated disputed evidence; fail closed or require competent human for dependent authority; PolicyOS does not run its own legal calendar | Compute one date from receipt/default holiday rules, claim finality, or operate the filing/service process | Lex legal evidence/quality issues; obligation graph source refs; human review | external competent authority + OPS-R10/11 consumer | **Proposed; no universal deadline engine authorized** |

### Metamorphic properties

| ID | Transformation | Required invariant | Falsifying observation | Likely execution owner |
|---|---|---|---|---|
| **M-01 Processing-time invariance** | Change worker start/end, retry and processing timestamps only | Semantic content identity, source-valid meaning and authority result remain equal | Claim/hash/authority changes | Fabric/artifact owners; OPS-R15 mapping |
| **M-02 Delivery-order invariance** | Permute delivery order within a source contract's declared equivalence class | Current semantic result and protected effect remain equivalent; transaction history records actual order | Result changes without a mutation/ordering dependency | source adapter/Fabric |
| **M-03 Duplicate-delivery invariance** | Duplicate the same scoped delivery | One protected effect/equivalent result; all attempts auditable | Duplicate lifecycle/public/irreversible action | canonical consumer |
| **M-04 Transaction-cutoff sensitivity** | Change only transaction cutoff `x` | What was visible/known/admitted may change; source valid/effect assertion does not | Source effect is rewritten to cutoff | Fabric/custody query owner |
| **M-05 Valid-coordinate sensitivity** | Change only valid/effect coordinate `v` | Applicability/current reconstruction may change; transaction history does not | Commit/receipt history changes | Fabric/Lex query owner |
| **M-06 Precision monotonicity** | Replace exact instant with lower-precision civil date/month | Authority cannot increase; possible interval widens or action blocks | Stronger authority or narrower interval appears without basis | temporal adapter/Lex |
| **M-07 Timezone-certainty monotonicity** | Remove known zone/offset or replace with unknown offset | Authority cannot increase; ambiguity retained | System silently chooses UTC/local offset and proceeds more strongly | parser/consumer |
| **M-08 Append-only correction** | Add a later correction/revocation/supersession | Earlier transaction/knowledge/publication view remains reproducible | Earlier view disappears or bytes mutate | Fabric/claim/public record owner |
| **M-09 Content/authority separation** | Keep content identical while competence expires/revokes | Integrity/equality stays true; current authority may fail | Authority remains solely due to identical hash | Lex/security/Decision Validity |
| **M-10 Watermark non-finality** | Advance watermark, then add an earlier-effective competent correction | Correction remains representable and assessed | Correction rejected as impossible | Fabric/source contract |
| **M-11 Projection non-authority** | Change a UI time label/cursor formatting without changing query coordinates | Temporal truth and authority unchanged | UI label changes canonical result | Atlas/runtime |
| **M-12 Producer-action non-prescription** | Change source payload `required_action` while source facts remain the same | Canonical PolicyOS claim reaction remains consumer-owned and may be unchanged | Source field directly mutates claim lifecycle | source adapter/canonical consumer |
| **M-13 Reconstruction/replay separation** | Compare `reconstruct(valid=T, tx=current)` with exact replay at historical cutoff `T` after a later correction | Results may differ and must be labeled; neither overwrites the other | Queries are treated as aliases or differences hidden | runtime/Fabric/Scientist/public owner |
| **M-14 Unknown-time non-substitution** | Remove a material source temporal assertion | Result becomes unknown/limited/blocked; processing time is not substituted | `now`, ingestion or worker time appears as source truth | every adapter; OPS-R15 falsifier |

### Executability classification

- **Executable with existing local primitives:** core parts of T-01, T-06; the bitemporal and lifecycle sub-properties of M-01, M-03, M-04, M-05 and M-08.
- **Partially executable with adapter/owner gaps:** T-04, T-05, T-07, T-08, T-10, T-11, T-13 and most cross-family metamorphic mappings.
- **Proposed research/benchmark fixtures:** T-02, T-03 cross-family unresolved relation, T-09, T-12, T-14 and full end-to-end authority assertions.

No fixture in this report is claimed as an executable OPS-R15 benchmark. OPS-R15/S0-GAP-02 must map each property to canonical owners, setup artifacts, observations and fail predicates before promotion.

## 10. Candidate Contract Sketches

All sketches in this section are **research-only semantic sketches**. They are not production schemas, mandatory DTOs, or implementation authorization. Their purpose is to show the narrowest possible artifact if later owner evidence proves one is needed.

### Retained sketches

#### A. `TemporalRoleProfile`

A sparse projection that maps family-native values to the nine OPS-R4 roles without requiring missing or inapplicable fields.

```text
TemporalRoleProfile
  profile_version
  subject_ref
  family
  owner_ref
  assertions[]:
    role
    value_ref_or_value
    shape
    trust_standing
    provenance_ref
    precision_and_uncertainty_ref
  limitations[]
```

- **Canonical owner:** unresolved shared semantic vocabulary; each profile instance remains owned by the family adapter/producer. A core package may later own only the vocabulary/version, not the underlying facts.
- **Persisted or projected:** projected by default. A canonical family owner may persist its native assertions; no requirement to persist the profile itself.
- **Family-specific extensions:** legal effect type, observation period semantics, source offset/version, workflow sequence, public-record standing.
- **Authority boundary:** the profile cannot verify, admit, adjudicate legal effect, compute currentness, or prescribe a claim reaction.
- **Required provenance:** every asserted/derived role maps to a source/native field or relation, producer, method and transaction-visible record.
- **Uncertainty:** must preserve source lexical form, precision, zone/calendar and disputed alternatives where material.
- **Versioning:** additive vocabulary versions; a profile declares the mapping version and source-contract version.
- **Non-use rules:** no mandatory role list; no default `now`; no role inferred solely from field name; no adapter-minted authority; no content identity based on projection timestamp.
- **Why existing owners are insufficient alone:** they preserve native meaning well, but cross-family consumers currently lack stable names for asking whether a value is effect, observation, receipt, transaction visibility or admission.

#### B. `TemporalMutationRelation`

A shared semantic relation vocabulary mapped to family-native immutable links.

```text
TemporalMutationRelation
  relation_id
  relation_type: corrects | revokes | supersedes | withdraws_authority | clarifies
  subject_ref
  target_ref_or_unresolved_target_identity
  aspect_or_scope
  asserted_by
  basis_ref
  source_effect_assertion_ref?
  transaction_visibility_ref
  uncertainty_or_dispute_ref?
```

- **Canonical owner:** each mutation is owned by the source/claim/public-record family authorized to assert it; shared vocabulary owner unresolved.
- **Persisted or projected:** persisted family-native relation when canonical; adapter projection elsewhere. No central mutation store.
- **Family-specific extensions:** legal competence/finality, data field/observation aspect, claim publishability, public correction notice, authority scope.
- **Authority boundary:** existence of a relation does not select the final current record or mutate a dependent claim. The canonical consumer evaluates competence, scope and dependency.
- **Required provenance:** issuer/actor, target identity, basis, transaction visibility, relation authority and unresolved status.
- **Uncertainty:** target may be unresolved; scope/effect may be disputed; competing relations remain visible.
- **Versioning:** relation vocabulary version plus family contract version.
- **Non-use rules:** no silent replacement; no transitivity by default; no content-equality shortcut; no relation from an untrusted adapter treated as competent.
- **Why existing owners are insufficient alone:** Fabric, Lex, Decision Validity and Claim Ledger already persist useful relations, but names and effects differ. A common predicate is needed for query/fixture interoperability, not centralized lifecycle ownership.

#### C. `TemporalReplayReceipt`

A decision-owned immutable projection declaring the exact temporal/version context used for a replay claim.

```text
TemporalReplayReceipt
  receipt_version
  decision_or_publication_ref
  replay_kind: exact_historical | current_reconstruction | diagnostic
  custody_transaction_cutoffs[]
  admitted_evidence_refs[]
  admission_policy_and_action_refs[]
  world_and_data_snapshot_refs[]
  legal_source_normpack_and_rule_refs[]
  workflow_fingerprint_and_checkpoint_refs[]
  authority_delegation_and_licence_refs[]
  model_tool_config_and_randomness_refs[]
  external_call_receipts_or_declared_gaps[]
  limitations[]
```

- **Canonical owner:** the decision/replay/publication owner, not OPS-R4 and not Fabric.
- **Persisted or projected:** persisted only when the owner makes an exact replay/reproducibility claim; otherwise projected diagnostic evidence.
- **Family-specific extensions:** solver seeds, legal pack selection, source reconciliation release, human-review record, public signature/publication reference.
- **Authority boundary:** proves context pinning and replay outcome only. It does not prove current correctness, current authority, legal validity, or completeness of unrecorded external systems.
- **Required provenance:** all refs resolvable to immutable artifacts/actions and their transaction histories; declared gaps are first-class.
- **Uncertainty:** missing external receipts or approximate cross-store cutoffs must be stated and lower the replay claim.
- **Versioning:** explicit receipt schema/vocabulary version; every referenced contract/version remains pinned.
- **Non-use rules:** one `replay_time` is insufficient; no wall-clock rerun time in semantic identity; no claim of exactness with unresolved mutable references.
- **Why existing owners are insufficient alone:** Fabric snapshots and Scientist checkpoints each capture only part of the authority-bearing context. A decision-owned receipt is needed to compose them without creating a new store.

#### D. `LateEventAssessment`

An advisory projection of the Section 7 decision procedure.

```text
LateEventAssessment
  assessment_version
  source_record_ref
  family_and_owner
  temporal_relation_to_cutoff_or_window
  mutation_standing
  dependency_materiality_evidence
  authority_materiality_evidence
  public_standing
  reversibility
  human_competence_requirement
  recommended_minimum_reaction
  limitations
```

- **Canonical owner:** assessment producer/adapter; final claim reaction owner remains the canonical claim consumer.
- **Persisted or projected:** projected by default; persist only as audit evidence when it influences a governed decision.
- **Family-specific extensions:** source-contract lateness, legal competence, data window closure, public-harm class.
- **Authority boundary:** never emits `admitted`, `valid`, `withdrawn`, `required_action`, or another final lifecycle result.
- **Required provenance:** cutoff/window definition, source contract, dependency evidence, public standing and assessor identity/version.
- **Uncertainty:** unresolved identity/effect/competence must be explicit and can force L6.
- **Versioning:** assessment algorithm/version and family adapter version.
- **Non-use rules:** no global late enum; no `recompute all`; no automatic claim mutation; no watermark finality.
- **Why existing owners are insufficient alone:** Fabric can classify delivery order and claim owners can react, but the evidence joining temporal relation, material dependency, authority and public standing is currently not represented as one bounded advisory view.

### Sketches not retained

- **`TemporalAssertion` as a universal persisted object:** not retained. It would recreate the envelope through a generic assertion table and compete with family-native records.
- **A new universal `TemporalScope`:** not retained. Existing runtime/Fabric scope primitives should be clarified and adapted rather than replaced.
- **A mandatory thin event header for every record:** not retained. It remains a conditional pilot candidate only where repeated boundary adapters prove value.
- **A global `OperationalEventEnvelope`:** refuted.

### Repository reuse map

| Semantic responsibility | Reuse-first action | Existing owner | Current primitive | Missing authority-delta | Candidate extension/projection | Consumer | Verification |
|---|---|---|---|---|---|---|---|
| Source data validity/observation | wire existing, extend precision | Fabric/Data Forge domain owner | fact `valid_time`, observation/release metadata, immutable snapshots | interval/precision/source-role ambiguity | family adapter to sparse `TemporalRoleProfile` | Foundry/Scientist/Decision Validity | valid-vs-tx query tests; M-04/M-05/M-06 |
| Transaction visibility | wire existing, consolidate query semantics | Fabric, Data Forge, event/claim stores | `tx_time`, logical transaction time, append-only logs | store scope and cross-store cutoff parity | store-qualified cutoffs in query/replay receipt | runtime/replay/public reconstruction | cutoff slicing; cross-store limitation tests |
| Source progress and receipt | wire existing, extend custody evidence | Fabric connectors/cursor/source-truth | watermark/cursor, fetch/retrieval records | progress vs receipt vs completeness not explicit | source-contract-qualified receipt/progress adapter | acquisition, knowledge view | T-07/T-12; no fallback-to-event-time test |
| Legal publication/effect/version | wire existing | Lex and legal Data Forge | effective/competence windows, publication/version records, NormPack refs | cross-family role mapping and disputed precision | OPS-R10/11 family adapter/profile | legal evaluation/claim owner | T-04/T-09/T-10/T-14; Lex property tests |
| Verification/integrity | wire existing, clarify outcome semantics | core audit/security and family verifier | artifact hashes, signatures, audit/verification events | verified vs admitted/current conflation | typed verification predicate mapping | admission/currentness/public surfaces | T-13; integrity-currentness separation |
| Purpose-scoped admission | extend canonical owners; do not centralize | evidence/claim/decision owners | existing gates, refs and lifecycle evidence; no universal action | explicit purpose/scope/action/cutoff/revocation semantics | owner-local admission lifecycle mapped to `admitted_by` | canonical claim consumer | historical admission-view fixtures; actor/authority tests |
| Claim dependency/currentness | wire existing, extend cutoff parity | Decision Validity and Claim Ledger | dependency refs/events, evaluations, transitions, lifecycle actions | dependency validity intervals, receipt/admission cutoff join | OPS-R2/claim-owner extensions; shared predicates only | runtime/public/appeal/remedy owners | T-05/T-11/T-13; M-08/M-09 |
| Correction/revocation/supersession | consolidate relation vocabulary | Fabric, Lex, Claim Ledger, public owner | immutable relation refs and lifecycle events | owner/scope/competence/unresolved-target mapping | `TemporalMutationRelation` vocabulary/adapters | current view, affected set, public correction | T-02/T-03/T-04; append-only checks |
| Late/out-of-order assessment | extend existing evidence flow | Fabric processing + canonical consumers | source out-of-order policy, dedupe, dependency events | materiality/authority/public-standing join | advisory `LateEventAssessment` | claim/public owner | Section 7 table; T-05/T-07/T-12 |
| Exact replay | consolidate refs, build only receipt projection | Scientist checkpoints, Fabric/Data Forge snapshots, Lex/NormPack, artifact store | workflow fingerprints, checkpoint chains, version refs | composite decision-owned context and declared gaps | `TemporalReplayReceipt` | Scientist/runtime/audit/public verification | T-04/T-05; M-13; replay parity tests |
| Public publication/currentness/archive | extend later public owner; Atlas projects | Claim Ledger/Decision Validity, core audit, Atlas/public artifacts | publication/signature, lifecycle status, projections | currentness join and append-only public correction | PAO-R36/INT-R7/INT-R8 public record semantics | controlled/public surfaces | T-13; publication-view reconstruction |
| Custody deadlines/review due | qualify and reuse owner-native duties | Decision jobs, obligation graph, authority/security, retention | `scheduled_for`, `deadline_at`, expiry, retention checkpoints | distinction from external legal/administrative deadlines | owner-qualified predicates/profile | OPS-R1/2/public/review owners | T-14; no external-calendar inference |

## 11. Later Integration Handoff

### OPS-R1

OPS-R1 may assume the following temporal requirements for suspension and resumption:

- represent a suspension as an owner-native interval or lifecycle relation, with PolicyOS transaction visibility separate from any source event;
- distinguish **wake occurrence** asserted by the source from **wake receipt** and repository recording;
- treat scheduled wake/review due as a PolicyOS-owned custody duty only when the owner is PolicyOS;
- deduplicate wake delivery under a scoped idempotency identity while retaining all attempts;
- assess late wake materiality rather than rejecting solely because a cursor/watermark advanced;
- define a resume cutoff as a composite of custody transaction/admission, dependency/world/version and workflow/checkpoint context;
- preserve the pre-suspension historical view and every resume attempt.

OPS-R4 does not define OPS-R1's complete suspension state machine, wake authorization, lock protocol, resume eligibility, or state payload.

### OPS-R2

OPS-R2 receives:

- dependency validity/currentness may be intervals or lifecycle predicates, not one expiry timestamp;
- authority/delegation/competence expiry can invalidate a dependency while content remains unchanged;
- late invalidation has distinct source effect, PolicyOS receipt and transaction visibility;
- affected-set reconstruction must be evaluated at explicit transaction/admission cutoffs and under dependency versions;
- current affected set and historical affected set are different queries;
- cutoff parity across graph/index/store projections must be testable;
- mutation relations identify candidates but do not automatically propagate final claim reactions.

OPS-R4 does not define OPS-R2's physical graph, index, storage, traversal or propagation algorithm.

### OPS-R3

OPS-R3 receives:

- old and new environment/version meanings require explicit validity/compatibility intervals or version relations;
- migration observation, execution and transaction visibility are distinct;
- historical replay before migration pins the old environment/workflow/rule/schema versions;
- replay after migration must state whether it is exact, emulated or current reconstruction;
- migrations append mappings and compatibility evidence; they do not rewrite old artifact meaning;
- processing time and migration wall-clock do not enter semantic content identity unless governed content refers to them.

OPS-R4 does not define migration mechanics, compatibility policy or environment package schema.

### OPS-R8

OPS-R8 receives temporal compatibility requirements for coordinated world releases:

- a release must identify per-owner version/snapshot and transaction cutoffs rather than assume a global clock;
- valid/effect coverage and uncertainty must be explicit for included facts/legal sources;
- admission/currentness must be supplied by canonical owners, not inferred from release inclusion;
- a release may provide an atomic or declared non-atomic cross-store visibility boundary;
- late corrections create later releases/relations without rewriting prior release history;
- historical replay pins the release and underlying versions.

OPS-R4 does not define a `WorldRelease` schema, state machine, publication process or release authority.

### OPS-R10 and OPS-R11

OPS-R10/11 receive the legal-family role requirements:

- distinguish adoption/signature, promulgation/publication, entry into force, efficacy/applicability, repeal/annulment, consolidation, finality and retroactivity;
- preserve civil-date precision, jurisdiction, calendar, timezone/offset uncertainty and boundary interpretation;
- model legal source/document/expression/rule versions and `valid_under_version` relations;
- separate competent legal effect assertions from PolicyOS receipt, verification and admission;
- represent future-effective and earlier-effective-later-published acts;
- expose disputed effective intervals and competent-human requirements;
- keep external filing, service, appeal, tolling and legal-calendar computation outside OPS-R4 ownership.

OPS-R4 does not decide legal competence, legal effect, conflict-of-laws, finality or jurisdictional deadline computation.

### PAO-R36, INT-R7, INT-R8, and Atlas

These tasks/surfaces receive:

- public publication history is append-only and distinct from current reconstruction;
- a correction, withdrawal or supersession is a new public/lifecycle record linked to the retained original;
- cryptographic integrity and semantic currentness are separate predicates;
- controlled surfaces must not present a stale/superseded/withdrawn record as current merely because its signature verifies;
- archive views may expose historical records with explicit standing and successor/correction links;
- Atlas is a projection consumer: its cursor must declare query kind and coordinates and cannot own temporal truth;
- public signatures/content identity exclude UI display time and ordinary processing time.

OPS-R4 does not define their complete public-state vocabulary, archival access policy, signature profile, correction UX or remedial workflow.

### OPS-R15 and S0-GAP-02

OPS-R15/S0-GAP-02 receive:

- the nine role definitions and trust/authority limitations;
- interval, transaction visibility and custody predicates;
- the eight query forms and their non-claims;
- reaction categories L0–L6 as advisory outcomes;
- fixtures T-01–T-14 and metamorphic properties M-01–M-14;
- explicit owner/adapter mappings and executability classifications;
- falsifiers for processing-time contamination, false precision, watermark finality, duplicate effects, history rewrite and projection authority.

They must produce executable setup, observation and failure predicates owned by the relevant packages. This report is not itself the benchmark oracle.

## 12. Promotion and Kill Rules

### Promotion states

| State | Meaning | Minimum evidence |
|---|---|---|
| **`research_only`** | Conceptual result may guide research but cannot authorize production contracts | This report, source citations, repository census and explicit limitations |
| **`accepted_narrow_scope`** | The temporal role/relation/query semantics are accepted as a bounded research handoff; universal envelope is rejected | Stage-0 compatibility, owner map, external baseline, fixtures/falsifiers, no owner pre-emption |
| **`prototype_allowed`** | One named owner may prototype a sparse adapter/projection in a bounded pilot | P13/P27 review; owner acceptance; no new store/lattice; exact pilot sources; fixture subset; rollback and non-use rules |
| **`governed_allowed`** | A production owner may rely on a temporal contract for a declared capability | Canonical design decision; versioned owner contract; executable OPS-R15 evidence; cross-owner parity; security/privacy/retention review; migration and rollback; operational monitoring; public-currentness safeguards where relevant |
| **`blocked`** | Evidence or ownership is insufficient, or a prohibited collapse is present | Precise blocker and owner required; no authority claim |
| **`refuted`** | The proposed semantic/contract approach is contradicted by evidence or necessarily creates unsafe ownership/collapse | Falsifying fixture, owner conflict, impossibility or demonstrated lower-risk alternative |

This report is `accepted_narrow_scope`. Prototype and governed promotion remain blocked pending canonical owner decisions and executable evidence.

### Mandatory block/kill rules

Promotion is **blocked** if any of the following is true:

1. one universal envelope is required without evidence that family-native contracts and adapters cannot satisfy the use case;
2. processing, ingestion, retry, worker-start, trace or wall-clock time becomes source occurrence/effect/observation/receipt/admission by default;
3. a historical correction overwrites, reorders or hides prior transaction history or public bytes;
4. current reconstruction and historical replay are represented by the same unqualified query;
5. external legal effect is inferred from PolicyOS receipt, ingestion, publication or watermark time;
6. a missing/unknown material time defaults to `now` for authority use;
7. a watermark, cursor or source update timestamp is treated as proof of final semantic completeness;
8. duplicate delivery can create duplicate protected PolicyOS effects;
9. timezone loss, precision loss or calendar uncertainty can increase authority;
10. an adapter, source payload or Atlas projection can admit evidence or mint a canonical claim reaction;
11. Atlas or another UI/projection becomes the owner of temporal truth;
12. the proposal pre-empts Fabric, Lex, Scientist, Decision Validity, Data Forge, audit, public-record or another canonical owner without P27 evidence and a ratified owner decision;
13. `corrects`, `revokes` or `supersedes` is applied without issuer/owner, target, scope/aspect, basis, transaction visibility and competence standing;
14. content equality is treated as proof of legal/institutional identity or continuing authority;
15. one transaction timestamp is claimed to atomically order independent stores without a coordinated release/sequence;
16. a replay claim omits mutable external/version references or silently substitutes current versions;
17. external legal/administrative deadlines are independently computed or operated without jurisdictional pilot, competent authority and explicit ownership;
18. `TimeSourceEnvelopeAudit` or a successor can emit `admitted`, adjudicate legal validity, require inapplicable fields or normalize unknown time into semantic truth;
19. a claim/public artifact can remain on a controlled “current” surface solely because integrity verification succeeds;
20. a source's `required_action` or equivalent field prescribes the canonical PolicyOS claim lifecycle.

### Refutation conditions for this model

The model itself would be refuted or require revision if governed evidence demonstrates any of the following:

- two or more of the nine primitive roles can always be collapsed across all material families without producing a false fixture result;
- purpose-scoped admission can be derived safely from transaction visibility/verification alone under all governed uses;
- one universal persisted envelope preserves family-native legal/data/workflow/public semantics, does not create owner gravity, and passes all fixtures with lower complexity than adapters;
- current reconstruction and historical replay are provably equivalent under all allowed correction/retroactivity scenarios;
- a source contract can legitimately guarantee permanent absence of earlier-effective correction for the relevant family, making the watermark non-finality rule overbroad;
- immutable append-only mutation relations cannot reconstruct a required current or historical view and a safer alternative is proven;
- cross-store exact replay can be established without per-store/version/release cutoffs;
- uncertainty-preserving temporal values are shown to make authority outcomes less honest than a different governed representation.

## 13. Open Questions for Consolidation

These questions do not block the `accepted_narrow_scope` result, but they block production promotion where relevant.

1. **Custody receipt owner.** Which existing package is canonical for a first-class PolicyOS receipt action across source families: source-truth, Fabric acquisition, core audit, or a family owner?
2. **Admission action owner.** Which current claim/evidence owners already have sufficient immutable purpose/scope admission evidence, and where is an explicit owner-local action still missing?
3. **Store-scoped transaction cutoffs.** Which stores expose trustworthy logical sequences versus wall-clock timestamps, and when is an OPS-R8 coordinated release required for cross-store parity?
4. **Public currentness owner.** Which PAO-R36/INT task owns the authoritative join between publication, lifecycle standing, integrity and controlled-surface eligibility?
5. **Legal precision profile.** What minimum lexical/calendar/zone/precision fields are needed for the first OPS-R10/11 jurisdictions without inventing a universal legal date type?
6. **Unresolved mutation targets.** What bounded buffering, reconciliation and escalation policy should each source family use for correction-before-original?
7. **Source completeness contracts.** Which sources can offer contractual completeness, correction-window or reconciliation guarantees, and how should residual uncertainty be benchmarked?
8. **Authority expiry affected sets.** How will OPS-R2 reconstruct claims depending on a producer/delegation whose competence interval later changes?
9. **Replay exactness levels.** Which external calls, human decisions, randomness, model binaries and environment versions are mandatory for `exact_historical` versus `diagnostic` replay?
10. **Retention versus replay.** When lawful retention deletion prevents exact replay, what limitation/public disclosure must replace a false reproducibility claim?
11. **Deadline pilots.** Which PolicyOS-owned review/correction duties need a governed deadline contract, and which external deadline assertions need jurisdiction-specific legal pilots?
12. **Thin header evidence.** Do repeated boundary adapters reveal a stable, genuinely cross-family identity/mutation subset, or would even a thin header create P13/P27 gravity?
13. **Admission revocation time.** Should owner-local admission lifecycle expose both action occurrence and transaction visibility explicitly, or is store history sufficient?
14. **Clock/skew evidence.** Which high-risk source families need signed time, trusted timestamping or clock-quality evidence rather than ordinary source timestamps?
15. **Benchmark authority.** Which OPS-R15 fixtures can be executable immediately without asserting capabilities that current owners do not provide?

## 14. Direct Answers

### What temporal distinctions are irreducible for PolicyOS custody?

Nine roles are irreducible: source occurrence/act; source effect/validity; observation/measurement; source publication/revision/version availability; PolicyOS receipt; repository transaction visibility; verification; purpose-scoped admission; and PolicyOS claim/publication/lifecycle action. Processing time is operational and must remain separate.

### Which distinctions require persisted fields?

No universal field bundle is required. Persist the facts needed by the owning family: constitutive source temporal assertions and their precision/provenance; PolicyOS receipt; transaction visibility/sequence; verification and admission actions when authority depends on them; immutable claim/publication lifecycle actions; and exact version/cutoff references when an exact replay claim is made. Existing family-native fields and event records should be reused.

### Which are better represented as relations, intervals, versions, or query cutoffs?

Effect, observation, competence and suspension are usually intervals. Publication/revision and executable context are often versions. Correction, revocation, supersession, derivation, authority withdrawal and unresolved correction-before-original are relations. Historical knowledge, admission, publication and replay are query cutoffs/context receipts, not object timestamps. Lateness and retroactivity are derived relations between those coordinates.

### Is a universal temporal event envelope justified?

No. It is refuted as a universal persisted contract because it collapses family-native meaning, creates central owner gravity, invites authority laundering and imposes inapplicable fields. A thin identity/mutation header may be piloted only at a proven boundary, never universally.

### What is the minimum cross-family temporal interoperability layer?

A sparse nine-role vocabulary; uncertainty/interval semantics; store-scoped transaction visibility; typed immutable mutation relations; explicit `known_by`, `verified_by`, `admitted_by`, `used_by` and `published_by` predicates; named query forms; a late-event assessment procedure; and shared fixtures/falsifiers. Persistence remains family-native with adapters.

### What does “known by PolicyOS at time T” mean?

A provenance-resolvable custody representation had been received and was transaction-visible in the declared PolicyOS custody scope by cutoff `T`. It does not mean verified, admitted, true, authoritative, used by a decision or current.

### What does “admitted by PolicyOS at time T” mean?

An authorized, purpose- and scope-specific admission action for a particular object/version was transaction-visible by `T` and had not been revoked or superseded at that same cutoff. Admission for one purpose or scope does not imply admission for another.

### How does historical replay differ from current reconstruction of a past valid time?

Historical replay pins the evidence, admission actions, transaction cutoffs, world/data snapshots, legal/rule versions, workflow fingerprint, authority context and other material versions actually available to the historical decision. Current reconstruction asks what PolicyOS now concludes about past valid time using later transaction history and explicitly current or versioned policies. They may legitimately differ; neither overwrites the other.

### What exactly does a Fabric watermark prove?

It proves progress under a named Fabric source/connector contract and watermark type. Depending on type, it may establish a processed timestamp estimate, opaque ETag/revision, source/log offset, schema version or committed cursor position within its declared scope.

### What does it not prove?

It does not prove real-world or legal completeness, absence of future earlier-effective corrections, timely receipt of out-of-band events, verification, admission, claim recomputation, global cross-source order, finality, or current public authority. A `fetched_at` fallback is not event time.

### When must late evidence cause recomputation?

When it is admitted, materially dependency-bearing for a current or open reversible claim, changes the claim's evidentiary result, and no stronger authority/public-standing rule requires suspension or a new epoch. The canonical claim owner performs and records the recomputation.

### When is annotation sufficient?

When the late fact is immaterial to claim support and authority, only adds provenance or limitation context, or changes current background context while the historical claim is no longer represented as current and no public-harm duty requires stronger action. Annotation is not sufficient for a material dependency.

### When is mandatory revalidation required?

When producer competence, authority/delegation, admission, legal validity, material dependency, temporal identity or current public standing may have failed; when a material correction/revocation affects a controlled current claim; or when time/zone/precision uncertainty is material to authority.

### When must a new epoch be opened?

When a material correction or regime/version/authority change after publication makes in-place recomputation misleading; when purpose/scope or legal environment is non-equivalent; when a public claim must be reissued, superseded or withdrawn; or when historical context must remain closed while a new decision context begins.

### Who owns the final claim reaction?

The canonical claim/publication consumer: for example Decision Validity, Scientist Claim Ledger, the legal decision owner, or the later public-record owner. Fabric, temporal adapters, source payloads, diagnostics and Atlas may supply evidence or recommendations but cannot mint the final reaction.

### How should correction-before-original be handled?

Persist the correction immediately with its actual receipt/transaction history and an unresolved target relation. Apply a bounded source-family buffer/reconciliation policy without discarding it. When the original arrives, append it and resolve the relation; never reorder or overwrite the earlier custody history.

### How should retroactive legal effect be represented?

As separate competent assertions/relations: publication/source version and PolicyOS receipt/transaction occur later; the asserted legal effect interval begins earlier. Preserve legal precision, jurisdiction and competence. Current legal reconstruction and affected current claims may change, but historical knowledge, admission and publications do not. Disputed retroactivity requires competent adjudication.

### Which timestamps may enter content identity?

Only temporal values constitutive of the governed semantic object may enter identity: for example a source act/publication/version identity, observation/reference period, effective interval, or declared decision cutoff when the artifact's content is expressly “the result under cutoff/version X.” Precision, zone and interpretation basis must be part of that semantic value where material.

### Which operational timestamps must stay outside semantic identity?

Ingestion/fetch, receipt retry, queue time, worker start/end, node/run start/end, processing time, replay execution time, projection refresh, trace time, audit verification time and transaction recording time must stay outside semantic content identity unless the governed claim is specifically about that operational event. They remain in provenance/audit.

### What temporal semantics belong to OPS-R1, OPS-R2, OPS-R3, and OPS-R8?

OPS-R1 receives suspension intervals, wake occurrence versus receipt, owner-owned review/wake due times, duplicate/late wake semantics and composite resume cutoffs. OPS-R2 receives dependency/authority validity intervals, late invalidation, affected-set reconstruction and cutoff parity. OPS-R3 receives old/new environment validity/version relations, migration observation/transaction history and before/after replay semantics. OPS-R8 receives coordinated release cutoffs, valid/effect coverage, owner-supplied admission/currentness, cross-store atomicity declarations and append-only later releases. OPS-R4 does not define their physical protocols or schemas.

### What deadline semantics does PolicyOS own?

PolicyOS owns custody duties it creates or is authoritative for: evidence freshness expiry, scheduled revalidation/review, public correction due, authority/delegation/licence/credential expiry when PolicyOS is the grant custodian, suspension review/wake due, and retention/archive verification checkpoints.

### Which external deadlines remain INTEGRATE or OUT_OF_SCOPE?

Filing and appeal periods, service/notice deadlines, tolling, statutory grace periods, court finality, payment/procurement deadlines, and institutional calendars remain competent external assertions under **INTEGRATE**. Operating those processes, independently adjudicating the date, or building a universal holiday/tolling/legal-calendar engine is **OUT_OF_SCOPE**.

### What should happen to the existing `TimeSourceEnvelopeAudit`?

Keep production code unchanged in this research task, but treat the object as a local projection only. Later planning should narrow and rename it, accept sparse family-native role mappings, remove `admitted` from its disposition vocabulary, delegate legal/source meanings to their owners, prohibit default-time substitution, and replace one `replay_time` with explicit replay context. It is not the PolicyOS temporal owner.

### What would falsify the proposed temporal model?

Evidence that the nine roles can safely be collapsed across all material families; that visibility or verification alone always implies admission; that a universal envelope passes all fixtures with less risk and no owner pre-emption; that current reconstruction and historical replay can never differ; that append-only relations cannot support required views; or that uncertainty preservation systematically produces less honest authority results than a proven alternative.

### What is safe for later H2 planning to assume?

H2 may assume only that PolicyOS needs explicit source-versus-custody distinctions, append-only transaction history, family-native temporal ownership, sparse shared role/relation/query semantics, separate current reconstruction and historical replay, non-final watermarks, effect-scoped idempotency, uncertainty monotonicity, and canonical-consumer ownership of claim reactions. H2 may not assume a universal envelope, final field list, central temporal store, legal calendar, global transaction clock, fixed lateness enum, or production-ready contract from this report.

[^r-stage0-r0]: PolicyOS, “PAO-R0 — Policy Matter Identity and Episode Graph,” amended Stage-0 research input, pinned at [`2907254`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/docs/research/policy-operations/stage0/pao-r0-policy-matter-identity-and-episode-graph.md) (accessed 2026-07-29).
[^r-stage0-r1]: PolicyOS, “PAO-R1 — Operational Boundary, Method, and Evidence Interface Census,” amended Stage-0 research input, pinned at [`2907254`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/docs/research/policy-operations/stage0/pao-r1-operational-boundary-method-and-evidence-interface-census.md) (accessed 2026-07-29).
[^r-stage0-r15]: PolicyOS, “OPS-R15 — Custody Capstone Semantic Kernel and Benchmark Architecture,” amended Stage-0 research input, pinned at [`2907254`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/docs/research/policy-operations/stage0/ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md) (accessed 2026-07-29).
[^r-stage0-consensus]: PolicyOS, “Stage-0 Consensus Kernel,” pinned at [`2907254`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/docs/research/policy-operations/consolidation/stage0/stage0-consensus-kernel.md) (accessed 2026-07-29).
[^r-fabric-time]: PolicyOS, “Fabric Time Travel,” and the corresponding valid/transaction-time implementation, pinned at [`2907254`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/docs/reference/fabric/time-travel.md) (accessed 2026-07-29).
[^r-decision-validity]: PolicyOS, [`core/contracts/decision_validity.py`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/src/polisyos/core/contracts/decision_validity.py), pinned at `2907254` (accessed 2026-07-29).
[^r-claim-lifecycle]: PolicyOS, [`scientist/evidence/claims/lifecycle.py`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/src/polisyos/scientist/evidence/claims/lifecycle.py), pinned at `2907254` (accessed 2026-07-29).
[^r-checkpoint]: PolicyOS, [`scientist/orchestration/engine/checkpoint.py`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py), pinned at `2907254` (accessed 2026-07-29).
[^r-lex]: PolicyOS, [`lex/normpack/legal_authority.py`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/src/polisyos/lex/normpack/legal_authority.py), pinned at `2907254` (accessed 2026-07-29).
[^r-runtime-audit]: PolicyOS, [`runtime/http/services/temporal.py`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/src/polisyos/runtime/http/services/temporal.py), including `TimeSourceEnvelopeAudit` and `build_time_source_envelope_audit()`, pinned at `2907254` (accessed 2026-07-29).
[^r-runtime-audit-fixture]: PolicyOS, [`layer3_gy_time_source_envelope_audit.json`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/architecture/policy_design_case/layer3_gy_time_source_envelope_audit.json), pinned at `2907254` (accessed 2026-07-29).
[^r-runtime-audit-validator]: PolicyOS, [`check_layer3_time_source_authority.py`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/tools/quality/validation/check_layer3_time_source_authority.py), pinned at `2907254` (accessed 2026-07-29).
[^r-watermark]: PolicyOS, [`fabric/data_plane/watermark.py`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/src/polisyos/fabric/data_plane/watermark.py), pinned at `2907254` (accessed 2026-07-29).
[^r-processing]: PolicyOS, [`fabric/quality/processing_guarantees.py`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/src/polisyos/fabric/quality/processing_guarantees.py), pinned at `2907254` (accessed 2026-07-29).
[^r-legal-resolver]: PolicyOS, [`data_forge/domains/legal/batch/temporal_resolver.py`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/src/polisyos/data_forge/domains/legal/batch/temporal_resolver.py), pinned at `2907254` (accessed 2026-07-29).
[^r-audit]: PolicyOS, [`core/audit/README.md`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/src/polisyos/core/audit/README.md), pinned at `2907254` (accessed 2026-07-29).
[^r-adr-time]: PolicyOS, [`ADR-044: Time as a UI Primitive`](https://github.com/DenisKopylov/polisyos/blob/290725446b8c073eb577f421ae2056986fbfcafb/policy-engine/docs/adr/ADR-044-time-as-primitive.md), pinned at `2907254` (accessed 2026-07-29).
[^x-allen]: James F. Allen, “Maintaining Knowledge about Temporal Intervals,” *Communications of the ACM* 26(11), 1983, [OSTI record and DOI](https://www.osti.gov/biblio/5140950) (accessed 2026-07-29).
[^x-bitemporal]: Kristian Torp, Christian S. Jensen, and Richard T. Snodgrass, “Effective Timestamping in Databases,” *VLDB Journal* 8(3–4), 2000, [bibliographic record](https://www.sigmod.org/publications/dblp/db/journals/vldb/TorpJS00.html) (accessed 2026-07-29).
[^x-sql-temporal]: ISO/IEC 19075-2:2021, “Guidance for the use of database language SQL — Part 2: Time-related information,” covering application-time, system-versioned, and bitemporal tables, [official ISO record](https://www.iso.org/standard/78933.html) (accessed 2026-07-29).
[^x-prov]: W3C, “PROV-O: The PROV Ontology,” W3C Recommendation, [official specification](https://www.w3.org/TR/prov-o/) (accessed 2026-07-29).
[^x-iso8601]: ISO 8601-1:2019, “Date and time — Representations for information interchange — Part 1: Basic rules,” [official ISO record](https://www.iso.org/standard/70907.html) (accessed 2026-07-29).
[^x-rfc3339]: IETF, RFC 3339, “Date and Time on the Internet: Timestamps,” [RFC Editor](https://www.rfc-editor.org/info/rfc3339/) (accessed 2026-07-29).
[^x-rfc9557]: IETF, RFC 9557, “Date and Time on the Internet: Timestamps with Additional Information,” [RFC Editor](https://www.rfc-editor.org/info/rfc9557/) (accessed 2026-07-29).
[^x-edtf]: Library of Congress, “Extended Date/Time Format (EDTF) Specification,” [official specification](https://www.loc.gov/standards/datetime/) (accessed 2026-07-29).
[^x-beam]: Apache Beam, “Beam Programming Guide,” sections on event time, processing time, watermarks, triggers and late data, [official documentation](https://beam.apache.org/documentation/programming-guide/) (accessed 2026-07-29).
[^x-flink]: Apache Flink, “Windows — Allowed Lateness,” [official Flink 1.19 documentation](https://nightlies.apache.org/flink/flink-docs-release-1.19/docs/dev/datastream/operators/windows/) (accessed 2026-07-29).
[^x-debezium]: Debezium, “Debezium Connector for PostgreSQL,” including source timestamps, connector processing timestamps, offsets, LSNs and transaction metadata, [official documentation](https://debezium.io/documentation/reference/stable/connectors/postgresql.html) (accessed 2026-07-29).
[^x-postgres-logical]: PostgreSQL, “Logical Decoding Output Plugins,” including commit-order decoding and exclusion of rolled-back transactions, [official documentation](https://www.postgresql.org/docs/current/logicaldecoding-output-plugin.html) (accessed 2026-07-29).
[^x-kafka-producer]: Apache Kafka, “Producer Configs,” `enable.idempotence` and transactional producer scope, [official documentation](https://kafka.apache.org/41/configuration/producer-configs/) (accessed 2026-07-29).
[^x-kafka-streams]: Apache Kafka, “Kafka Streams Core Concepts,” exactly-once processing scope for Kafka input offsets, state stores and Kafka output, [official documentation](https://kafka.apache.org/11/streams/core-concepts/) (accessed 2026-07-29).
[^x-temporal]: Temporal, “Architecture,” describing append-only workflow history, deterministic replay, and idempotent or non-retryable activities, [official project repository](https://github.com/temporalio/temporal/blob/main/docs/architecture/README.md) (accessed 2026-07-29).
[^x-akn]: OASIS, “Akoma Ntoso Version 1.0, Part 2: Specifications,” including FRBR versions, events, force and efficacy metadata, [official specification](https://docs.oasis-open.org/legaldocml/akn-core/v1.0/cos01/part2-specs/akn-core-v1.0-cos01-part2-specs.html) (accessed 2026-07-29).
[^x-eli]: Publications Office of the European Union, “ELI Ontology,” version 1.5, [official EU Vocabularies record](https://op.europa.eu/en/web/eu-vocabularies/model/-/resource/dataset/eli) (accessed 2026-07-29).
[^x-legalruleml]: OASIS, “LegalRuleML Core Specification Version 1.0,” §4.3.5 distinguishing entry into force, efficacy, applicability and provision-content deadlines, [official specification](https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/legalruleml-core-spec-v1.0.html) (accessed 2026-07-29).
[^x-premis]: Library of Congress, “PREMIS Data Dictionary for Preservation Metadata, Version 3.0,” [official resource](https://www.loc.gov/standards/premis/v3/index.html) (accessed 2026-07-29).
[^x-nara-faq]: U.S. National Archives, Office of the Federal Register, “Federal Register Frequently Asked Questions,” including the permanent public record standing of published documents, [official guidance](https://www.archives.gov/federal-register/faqs) (accessed 2026-07-29).
[^x-nara-correct]: U.S. National Archives, Office of the Federal Register, “Document Drafting Handbook — Corrections,” [official guidance](https://www.archives.gov/federal-register/write/ddh/correct) (accessed 2026-07-29).
[^x-retroactivity]: Court of Justice of the European Union, Advocate General's Opinion in Case C-162/09, discussion of legal certainty and retroactive effect, [EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:62009CC0162) (accessed 2026-07-29).
