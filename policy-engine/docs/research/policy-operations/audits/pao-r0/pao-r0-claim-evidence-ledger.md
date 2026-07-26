---
title: PAO-R0 — Claim-to-Evidence Ledger
status: draft_audit
kind: research-audit
research_task: PAO-R0
source_report_status: delivered
source_report_result_type: accepted_narrow_scope
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
audit_date: 2026-07-26
audit_branch: research/pao-r0-independent-audit
authoritative_for:
  - repository audit findings at the recorded commits
  - recommended research corrections
may_not_use_for:
  - production capability claim
  - final code contract
  - authority grant
  - production migration authorization
  - automatic identity adjudication
  - direct modification of authoritative plans
research_only: true
---

# PAO-R0 — Claim-to-Evidence Ledger

## Ledger method

This ledger atomizes repository facts, absence claims, owner claims, architecture inferences,
implementation states, migration claims, test/fixture claims, normative proposals, and
external-source claims from the supplied PAO-R0 report.

Baseline A and Baseline B are identical. Every current evidence link is nevertheless repeated
as a commit-pinned permalink, and every row has separate historical/current verdicts.

Evidence cells identify an exact path and symbol/section. “Static only” in the runtime column
means the repository fact is verifiable without executing the unavailable capability; it
does not lower the static confidence.

### Verdict summary

The final count is computed from the atomic rows below and must be kept synchronized if rows
change.

| Category | Count |
| --- | ---: |
| Claims audited | 131 |
| Confirmed | 55 |
| Confirmed/partially supported with qualification | 46 |
| Contradicted/unsupported/owner or contract risk | 26 |
| External or runtime verification still required | 4 |

For this roll-up, `confirmed_with_qualification`, `partially_supported`,
`planned_not_implemented`, and `fixture_only` are counted as qualified;
`contradicted`, `unsupported`, `owner_not_established`, `premature_contract`, and
`absence_not_proven` are counted in the defect/risk bucket. Atomic verdicts remain visible in
the rows and are not collapsed in the evidence record.

## Repository baseline and audit method

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BASE-001 | §2.1 inspection record | The inspected branch/SHA is `main` at `4813b49f…`. | Repo fact | [Pinned commit](https://github.com/DenisKopylov/polisyos/commit/4813b49f6ce14e8debf3aaea096f0967d38d9768) | Current `main` resolved to the same pinned commit | confirmed | confirmed | High | Informational | Git/repository | N/A | — | Keep and record full SHA. | Git remote and connector comparison. |
| BASE-002 | Mandatory two-baseline implication | Current `main` may differ from the report SHA. | Current-state claim | Historical pinned commit | GitHub comparison returned identical, ahead/behind 0 | confirmed | confirmed | High | Informational | Git/repository | N/A | — | State explicitly that there is no stale/current delta. | Remote verified at audit start. |
| BASE-003 | §2.1 | The inspected commit ratified the identity boundary and reshaped Wave 2. | Git-history claim | [Commit 4813b49f](https://github.com/DenisKopylov/polisyos/commit/4813b49f6ce14e8debf3aaea096f0967d38d9768) | Same commit | confirmed | confirmed | High | Informational | team-architecture/Git history | documented_only | — | Keep. | `git log`, `git show`, `git -S`. |
| BASE-004 | §2.1 | Most requested paths live below `policy-engine/`. | Repo-layout claim | Repository tree; all cited source/docs/tests are below `policy-engine/` | Same tree | confirmed | confirmed | High | Low | Repository | N/A | — | Keep. | Static. |
| BASE-005 | §2.1 | Requested `honest-diagnostics-substrate.md` was represented by the renamed decision-log file. | Repo-path claim | [The requested file exists][honest-diagnostics]; [decision log is a separate append-only log][honest-log] | Same links | contradicted | contradicted | High | Medium | team-architecture docs | documented_only | stale/incorrect path claim | Replace with “both source decision and separate decision log exist; inspect both.” | Static. |
| BASE-006 | §2.1; supplied-report standing | The PAO-R0 report had not been committed. | Absence claim | No PAO-R0 research artifact path/ledger entry; [completion ledger remains pending][wave2-ledger] | Same | confirmed | confirmed | High | Low | Research backlog owner | planned_only | — | State that the audited report came from task context and was absent from the tree. | Full tracked-tree search. |
| BASE-007 | §2.2 | Governing repo files and package READMEs exist at the cited paths. | Repo-path/method claim | Root `AGENTS.md`; `policy-engine/CONTRIBUTING.md`; package READMEs; no nested AGENTS below policy-engine | Same tree | confirmed | confirmed | High | Informational | Repository/package owners | documented_only | — | Keep exact paths and note only root AGENTS applies. | Static. |
| BASE-008 | §2.2 | Repository doctrine requires a complete capability chain before “implemented.” | Repo fact | [Failure register capability definition][capability-chain] | Same link | confirmed | confirmed | High | Medium | team-architecture/runtime quality | documented invariant | — | Keep and apply consistently to matter claims. | Static. |

## Identity inventory

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ID-001 | Executive; §1.4; §4.14 | A stable identity above a case is necessary/OWN. | Repo fact | [`policyos-identity…md` §6][identity-decision] | Same SHA: [§6][identity-decision] | confirmed | confirmed | High | Informational | team-architecture for boundary | documented_only | — | Keep as the ratified functional boundary, not a capability claim. | Static only. |
| ID-002 | §2.4 | `PolicyMatter` has no implementation occurrence. | Absence claim | [`rg` result; decision/backlog only][wave2-pao] | Same SHA: [PAO-R0 row][wave2-pao] | confirmed | confirmed | High | Medium | Missing | planned_only | — | Say “appears only in two governing/research docs; no typed implementation.” | Full tracked-tree search; external systems blind. |
| ID-003 | §2.4 | `policy_matter`, `matter_id`, and `matter_ref` are absent. | Absence claim | Tracked-tree census; [PDC model has none][pdc-model] | Same tree/model: [link][pdc-model] | confirmed | confirmed | High | Medium | Missing | planned_only | — | Retain with exact search scope/exclusions. | No deployed DB inspected. |
| ID-004 | §2.4; §4.12 | `case_id` is case identity, not lifetime matter identity. | Repo fact / inference | [Ratified identity is above a case][identity-decision]; [case DTOs][governed-projections] | Same links | confirmed_with_qualification | confirmed_with_qualification | High | Medium | PDC/runtime-quality case owners | implemented | — | Keep; avoid claiming every `case_id` producer has identical semantics. | Static plus case tests. |
| ID-005 | §2.4 | `run_id` is execution identity. | Repo fact | [PDC model `run_id`][pdc-model]; [generated run routes][api-client] | Same links | confirmed | confirmed | High | Medium | runtime/control plane | implemented | — | Keep. | Static; selected PDC tests passed. |
| ID-006 | §2.4 | `job_id` is operational scope, not policy identity. | Repo fact | [PDC optional `job_id`][pdc-model] | Same link | confirmed | confirmed | High | Low | runtime/control plane | implemented | — | Keep. | Static. |
| ID-007 | §2.4 | PDC `graph_id` is graph/version context. | Repo fact | [`RuntimePolicyDesignCase`][pdc-model]; [`graph_id = runtime-pdc-graph:{run_id}`][pdc-compile] | Same links | confirmed | confirmed | High | Medium | PDC | implemented | — | State that the current PDC graph ID is run-derived. | PDC compiler tests passed. |
| ID-008 | §2.3.3; §2.4 | `ArtifactID` identifies bytes, not a real-world policy. | Repo fact / semantic inference | [`ArtifactID` SHA-256 ABI][artifact-id]; [manifest][artifact-manifest] | Same links | confirmed | confirmed | High | Medium | core.artifacts | implemented | — | Keep. | Signing tests passed. |
| ID-009 | §2.3.6; §2.4 | `decision_lineage_key` is one decision lineage and not proved tenant/global/matter identity. | Repo fact | [Decision-validity contract][decision-contract]; [state-store key path][decision-store] | Same links | confirmed | confirmed | High | High | core.contracts + Scientist validation | implemented | underclaim | Add that raw local persistence is tenant-blind. | Path-collision probe confirmed. |
| ID-010 | §2.4 | `policy_id` is overloaded and owner-local. | Absence/semantic census | 201-file tracked-tree census; [PolicyPortfolio ADR/code][portfolio-adr] | Same tree | confirmed_with_qualification | confirmed_with_qualification | High | Medium | Multiple/conflicting | implemented in local domains | overclaim risk | Keep “overloaded”; do not impose one global rule without per-symbol inventory. | Static census; not every occurrence dynamically traced. |
| ID-011 | §2.3.11; §2.4 | `portfolio_id`/PolicyPortfolio is candidate analysis, not deployed identity. | Repo fact | [ADR-0022][portfolio-adr]; [`PolicyPortfolio`][portfolio-code] | Same links | confirmed | confirmed | High | Medium | IR loading | implemented | — | Keep. | Portfolio tests passed. |
| ID-012 | §2.4 | `release_id` and `epoch_id` are version/epistemic scope, not matter. | Repo fact / inference | Tracked-tree census; [Wave-2 release/epoch context][wave2-ops] | Same | confirmed_with_qualification | confirmed_with_qualification | Medium | Low | Fabric/GY/domain owners | implemented in parts | incomplete search | Keep as per-owner meanings; avoid one universal semantic claim. | Static only. |
| ID-013 | §2.4; §4.3 | `tenant_id` is essential and an origin tenant belongs in the immutable identity kernel. | Repo fact + design recommendation | [CAS ownership separates tenant claims][artifact-ownership]; [shared-CAS test][tenant-test] | Same links | partially_supported | partially_supported | High | High | security/CAS; semantic owner missing | implemented security / missing matter | premature_contract | Preserve tenant scope; move immutable origin tenant to open questions. | No federation/transfer runtime. |
| ID-014 | §2.4; §4.3 | Jurisdiction is context, not the ID. | Architecture inference | [Capability scope includes jurisdiction][capability-scope]; [Lex source][lex-types] | Same links | confirmed_with_qualification | confirmed_with_qualification | High | Medium | Lex/capability/applicability owners | implemented in parts | — | Keep distinction; do not freeze one matter jurisdiction field. | Static. |
| ID-015 | §2.4 | No relevant higher-order `subject` concept exists. | Absence claim implied by inventory | [`NormApplicability`/generic subject models][applicability]; tracked `subject_id`/`subject_reference` census | Same | contradicted | contradicted | High | Medium | Multiple | implemented generic subjects | underclaim | Add generic subject primitives, then explain why none has lifetime matter semantics. | Static. |
| ID-016 | Executive; §4.3 | No descriptive tuple can universally determine identity. | Architecture/external inference | No repository implementation proves a theorem; [PAO-R0 remains research-only][wave2-pao] | Same | external_verification_required | external_verification_required | Medium | Medium | External/legal + future owner | research_only | unresolved research question | Present as research hypothesis supported by counterexamples, not repository fact. | Jurisdictional research required. |

## PDC ownership

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PDC-001 | §2.3.1; §2.8; §7.7 | PDC is the closest/presumptive canonical owner of matter identity. | Ownership claim | [PDC README limits authority to graph structure][pdc-readme]; [Wave-2 later target says PDC lineage][wave2-pao] | Same links | owner_not_established | owner_not_established | High | High | Missing/conflicting candidate signals | planned_only | owner overclaim | Say PDC is a candidate integration neighborhood; require P27 owner ratification. | Static. |
| PDC-002 | §2.3.1 | PDC is a typed authority waist above claims/cases. | Architecture inference | [Wave-2 calls PDC narrow waist][wave2-waist]; [PDC README][pdc-readme] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Medium | PDC + shared ABI | implemented for current contracts | overclaim | Limit to current PDC graph/Layer-2 contracts; do not extend to matter by implication. | Selected tests passed. |
| PDC-003 | §2.3.1 | Current PDC graph is tied to `run_id`, optional `job_id`, and `tenant_id`. | Repo fact | [`RuntimePolicyDesignCase` fields][pdc-model] | Same | confirmed | confirmed | High | Informational | PDC | implemented | — | Keep. | PDC tests passed. |
| PDC-004 | §2.3.1; PMF-24 | PDC projection is projection-only. | Repo fact | [PDC authority envelope/model][pdc-model]; [projection test family][projection-tests] | Same | confirmed | confirmed | High | Medium | PDC/runtime quality projection | implemented | — | Keep for the PDC projection path only. | 37 projection tests passed. |
| PDC-005 | §2.6 | PDC anti-LLM laundering tests exist. | Test claim | [Compiler test file][pdc-tests] | Same | confirmed | confirmed | High | Medium | PDC | implemented | — | Cite exact function, not a generic fixture. | Test passed. |
| PDC-006 | §2.3.2; §2.6 | Typed PDC record families block a status-only pass. | Repo/test claim | [Record registry tests][record-tests] | Same | confirmed | confirmed | High | Medium | runtime quality | implemented | — | Keep; state it proves record completeness, not matter identity. | Tests passed in targeted batch. |
| PDC-007 | §2.8 | Extending PDC is the smallest safe integration path. | Architecture recommendation | [Reuse-first/P27 register][failure-register]; [PDC later target][wave2-pao] | Same | partially_supported | partially_supported | Medium | High | Unresolved | planned_only | unresolved research question | Present as candidate A in owner comparison, not accepted path. | Requires architecture review. |
| PDC-008 | §7.7 | “No new top-level canonical owner is justified.” | Ownership conclusion | [PDC is not listed as a public package][public-surface]; [core.contracts owns shared ABI][contracts-readme] | Same | unsupported | unsupported | High | High | Missing | planned_only | owner_not_established | Remove; reuse-first does not predetermine the winner. | Static. |

## Runtime-quality ownership

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RQ-001 | §2.5; §2.8; §7.7 | Runtime quality should be the matter admission ring. | Ownership/design claim | [Runtime-quality README says adapter/validation but cannot create producer authority][rq-readme]; [Wave-2 waist][wave2-waist] | Same | owner_not_established | owner_not_established | High | High | runtime quality is candidate bridge | bridge_missing | owner overclaim | Say “candidate validator/adapter after producer and owner ratification.” | No matter bridge exists. |
| RQ-002 | §2.8 | Runtime quality is the current PDC backbone owner. | Repo/ownership claim | [README scope][rq-readme]; [PDC owner is team-policyos-runtime][pdc-readme] | Same | confirmed_with_qualification | confirmed_with_qualification | Medium | Medium | PDC + runtime quality | implemented for existing PDC | ambiguous terminology | Replace “backbone owner” with exact responsibilities. | Static/tested subsets. |
| RQ-003 | §2.8 | Runtime quality can admit, validate, downgrade, or block external identity evidence. | Capability claim | [Capability authority does this for current capability evidence][capability-authority]; no matter adapter | Same | planned_not_implemented | planned_not_implemented | High | High | Candidate runtime-quality bridge | bridge_missing | overclaim | “Could reuse existing validation patterns; no matter intake exists.” | Matter runtime impossible. |
| RQ-004 | §2.5 | Future governed PDC/runtime-quality producer will mint matter IDs. | Design recommendation | No producer symbol; [PAO-R0 research-only][wave2-pao] | Same | unsupported | unsupported | High | High | Missing | producer_missing | premature_contract | Do not name producer until owner/issuance policy is ratified. | Impossible today. |
| RQ-005 | §7.7 | Identity-resolution receipt belongs to runtime quality/PDC. | Ownership claim | No receipt or owner record; [shared ABI boundary][contracts-readme] | Same | owner_not_established | owner_not_established | High | Medium | Missing/conflicting | planned_only | duplicate-owner risk | Keep artifact as research candidate and owner question. | Static. |
| RQ-006 | §2.3.1 | Runtime quality does not itself launder raw engines/LLMs into authority. | Repo fact | [README lines 7–10][rq-readme]; [capability authority fields][capability-authority] | Same | confirmed | confirmed | High | Medium | runtime quality | implemented | — | Keep. | Projection/record tests passed. |

## CAS and audit

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAS-001 | §2.3.3 | `ArtifactID` is stable `sha256:` content address. | Repo fact | [`ArtifactID`][artifact-id] | Same | confirmed | confirmed | High | Informational | core.artifacts | implemented | — | Keep. | Signing/store tests passed. |
| CAS-002 | §2.3.3 | Artifact manifests are immutable and preserve producer/input/tenant/authority/integrity metadata. | Repo fact | [`ArtifactManifest`][artifact-manifest] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Medium | core.artifacts | implemented | overclaim | Enumerate actual manifest fields; avoid implying all proposed matter fields exist. | Static plus signing tests. |
| CAS-003 | §2.3.3 | Content identity is not real-world matter identity. | Architecture inference | [Artifact ID and signature binding][artifact-id] | Same | confirmed | confirmed | High | Medium | core.artifacts vs future semantic owner | implemented content / missing matter | — | Keep. | Static. |
| CAS-004 | §2.3.4 | IR artifact lineage has artifact/task nodes and technical relations only. | Repo fact | [`ArtifactLineageGraph`][artifact-lineage] | Same | confirmed | confirmed | High | Medium | IR artifacts | implemented | — | Keep. | Static/test patterns. |
| CAS-005 | §2.3.9 | Core audit assembles deterministic portable archives and verifies integrity/signatures/provenance offline. | Repo fact | [core audit README][audit-readme]; [audit tests][audit-tests] | Same | confirmed | confirmed | High | Informational | core.audit | implemented | — | Keep. | Selected audit test passed. |
| CAS-006 | §2.3.9; §7.7 | Core audit is an appropriate owner for matter-custody audit events. | Ownership claim | [README owns packaging/verification only][audit-readme] | Same | contradicted | contradicted | High | High | Semantic owner missing; core audit is package verifier | implemented verifier / missing events | wrong owner | Say core audit may package future canonical events; it does not own their semantics. | Static. |
| CAS-007 | §4.11 | A record can remain integrity-valid while a matter association becomes semantically wrong. | Architecture inference | [Signature binds bytes + manifest hash][signing]; no semantic verifier | Same | confirmed_with_qualification | confirmed_with_qualification | High | High | core.artifacts integrity + future semantic owner | implemented integrity / verification_missing semantics | overclaim | State this is possible only if correction semantics are external to signed payload; exact packet shape matters. | Signing tests passed; semantic path absent. |
| CAS-008 | §4.12; §5.5 | A sidecar association/correction is sufficient without changing signed bytes. | Design recommendation | [Signature statement][signing]; [PAO-R36 planned correction chain][wave2-pao36] | Same | unsupported | unsupported | High | High | PAO-R36/INT-R7/future owner | planned_only | premature_contract | “Sidecar is a candidate non-rewrite technique; sufficiency is unproven.” | Public correction runtime absent. |
| CAS-009 | §4.9; PMF-23 | ID equality must never cross tenants. | Normative proposal | [CAS deliberately shares content IDs across tenants][artifact-ownership]; [test][tenant-test] | Same | contradicted | contradicted | High | High | core.artifacts/security | implemented | too broad | Scope the rule to semantic matter references/external IDs; content IDs intentionally compare equal. | Cross-tenant CAS test passed. |
| CAS-010 | §2.3.5; §2.8 | Existing public/audit export plumbing is safe/reusable. | Capability claim | [Public redaction test][public-redaction-test] | Same | contradicted | contradicted | High | High | runtime quality/public export | implemented_but_failing | overclaim | Record redaction defect; do not call the public surface ready. | Test failed reproducibly. |

## Decision validity

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DV-001 | §2.3.6 | Decision validity tracks law/data/source/model/metric/context/evidence changes. | Repo fact | [Decision-validity contract][decision-contract] | Same | confirmed | confirmed | High | Informational | core.contracts + Scientist | implemented | — | Keep. | Selected tests passed. |
| DV-002 | §2.3.6; §2.6 | A law change can move a decision to human review. | Test claim | [`test_decision_validity_service_records_events…`][decision-tests] | Same | confirmed | confirmed | High | Medium | Scientist validation | implemented | — | Cite exact function. | Passed. |
| DV-003 | §2.3.6; §2.6 | Legacy packets receive sticky lifecycle triggers. | Test claim | [`test_decision_validity_service_applies_sticky_triggers…`][decision-tests] | Same | confirmed | confirmed | High | Medium | Scientist validation | implemented | — | Keep at decision scope. | Passed. |
| DV-004 | §2.3.6 | `decision_lineage_key` is not proved tenant/jurisdiction/global unique. | Repo/absence claim | [Contract lacks fields][decision-contract]; [store hashes raw key][decision-store] | Same | confirmed | confirmed | High | High | Scientist validation + security gap | implemented_but_not_tenant_scoped | underclaim | Add shared-store collision risk and required qualification. | Dynamic path probe confirmed. |
| DV-005 | §4.11 | Repository already distinguishes payload validity from authority validity. | Capability claim | [Decision dependencies/reasons][decision-contract]; [OPS-R2 assigns two output sets][wave2-ops] | Same | partially_supported | partially_supported | High | High | OPS-R2 future; current decision-validity owner | implemented fragments / planned generic split | overclaim | Say fragments support the concept; canonical two-set fan-out is planned, not implemented. | No matter runtime. |
| DV-006 | §4.11 | Transportability is a validity dependency. | Repo fact | [DecisionValidityDependencyKind][decision-contract] | Same | confirmed | confirmed | High | Medium | decision-validity + transportability owner | implemented | — | Keep; do not confuse dependency presence with transport certificate. | Static/tested service. |
| DV-007 | §2.5; §7.7 | Decision validity can simply add a matter reference. | Design recommendation | No matter field; [shared ABI owner][contracts-readme] | Same | premature_contract | premature_contract | High | High | Unresolved/shared ABI | consumer_missing | duplicate-owner risk | Require scope/cardinality/owner design before extension. | Impossible today. |
| DV-008 | §6.5 | `lineage_fixture_001` is a reusable decision-validity fixture. | Fixture claim | [Literal inside test][decision-tests] | Same | fixture_only | fixture_only | High | High | Test-local | fixture_only | fixture overclaim | Call it a literal scenario value and cite the test function. | Test passed, reuse shape not frozen. |

## Lifecycle and reissue

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LC-001 | §2.3.7 | Continuous governance maps detector events into append-only claim lifecycle transitions. | Repo fact | [`lifecycle_bridge.py`][lifecycle-bridge]; [tests][lifecycle-tests] | Same | confirmed | confirmed | High | Informational | Scientist continuous governance | implemented | — | Keep at claim scope. | Tests passed. |
| LC-002 | §2.3.7 | Unscoped events block and do not mutate lifecycle. | Test claim | [`test_unscoped_detector_event…`][lifecycle-tests] | Same | confirmed | confirmed | High | Medium | Scientist continuous governance | implemented | — | Keep. | Passed. |
| LC-003 | §2.3.7 | Partial reissue preserves unaffected claims/records. | Test claim | [`test_partial_scope_builder…`][reissue-tests] | Same | confirmed | confirmed | High | Medium | Scientist continuous governance | implemented | — | Keep at claim/packet scope. | Passed. |
| LC-004 | §2.3.7 | Public revision state is projection-only. | Repo/test claim | [Reissue/lifecycle tests][reissue-tests] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Medium | Scientist/public projection | implemented for this path | overclaim | Limit to this lifecycle projection, not all Atlas/public code. | Passed selected tests. |
| LC-005 | §2.3.7 | This is the strongest repository precedent for matter corrections. | Architecture inference | [Lifecycle and reissue code/tests][lifecycle-bridge] | Same | confirmed_with_qualification | confirmed_with_qualification | Medium | Medium | Scientist precedent; matter owner missing | implemented narrower capability | overclaim | Say “strong append-only/scoping precedent,” not reusable matter capability. | No matter semantics. |
| LC-006 | §2.5; §7.7 | Existing lifecycle bridge is a matter-aware correction/fan-out bridge. | Capability claim implied by integration | No matter refs; [PAO-R36 planned][wave2-pao36] | Same | unsupported | unsupported | High | High | Missing/PAO-R36 future | bridge_missing | capability overclaim | Mark matter correction bridge missing. | Impossible today. |

## Lex

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LEX-001 | §2.3.8 | Repository separates legal source identity from versions. | Repo fact | [`LegalDocSource`][lex-types]; [version index][legal-versioning] | Same | confirmed | confirmed | High | Informational | Data Forge legal + Lex | implemented | — | Keep with split owner. | Lex tests passed. |
| LEX-002 | §2.3.8 | Active version selection uses effective/as-of semantics and warns on missing/overlap. | Repo/test fact | [`build_version_index`/`resolve_active_version`][legal-versioning]; [tests][lex-tests] | Same | confirmed | confirmed | High | Medium | Data Forge producer; Lex runtime facade | implemented | — | Keep. | Selected tests passed. |
| LEX-003 | §2.3.8; §7.7 | Lex owns legal-document source identity/version production. | Ownership claim | [Public-surface contract assigns offline preprocessing to Data Forge][public-surface]; [Lex README/runtime facade][lex-readme] | Same | contradicted | contradicted | High | High | Data Forge producer + Lex consumer | implemented | wrong owner | State exact producer/consumer split. | Static + tests. |
| LEX-004 | §2.3.8 | Legal-document identity cannot be promoted into policy identity. | Architecture inference | [Legal source/version types][lex-types]; [matter function above case][identity-decision] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Medium | Separate owners | implemented doc / missing matter | — | Keep as semantic distinction, not a tested theorem. | No matter runtime. |
| LEX-005 | §4.7; PMF-12 | Instruments and matters are necessarily many-to-many. | Design recommendation | No matter link exists; legal docs allow multiple structures but do not prove policy cardinality | Same | external_verification_required | external_verification_required | Medium | High | External/legal + future matter owner | research_only | premature_contract | Keep many-to-many as a required representational possibility, not universal factual cardinality. | Jurisdictional/examples required. |
| LEX-006 | §2.6 | Lex version-selection fixtures are under Lex tests. | Fixture/path claim | [Exact tests are `tests/unit/fabric/test_lex_corpus.py`][lex-tests] | Same | partially_supported | partially_supported | High | Medium | Test topology: Fabric file, Data Forge/Lex code | fixture_only | inaccurate path/owner | Cite exact path and symbols. | Tests passed. |

## DDM

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DDM-001 | §2.3.10 | DDM canonically owns drift, degradation, readiness, incidents, and shift evidence. | Ownership/repo claim | [DDM README][ddm-readme] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Informational | DDM/Scientist | implemented | — | Keep the package's exact declared scope; avoid claiming all incident sources repository-wide. | Selected DDM tests passed. |
| DDM-002 | §2.3.10 | DDM does not establish which matter an incident belongs to. | Absence/semantic claim | [DDM contracts/README contain no matter ref][ddm-readme]; tracked census | Same | confirmed | confirmed | High | Medium | DDM event owner; matter association missing | producer implemented / association missing | — | Keep. | Static. |
| DDM-003 | §2.8; §7.7 | DDM events can affect a matter after a typed association. | Design recommendation | No association bridge; [OPS-R2 future dependency fan-out][wave2-ops] | Same | planned_not_implemented | planned_not_implemented | High | Medium | DDM producer + future matter bridge | bridge_missing | architecture inference | State as later integration hypothesis. | No matter runtime. |

## PolicyPortfolio

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PP-001 | §2.3.11 | ADR-0022 defines PolicyPortfolio as candidate PolicySpec references/interactions. | Repo fact | [ADR-0022][portfolio-adr]; [`PolicyPortfolio`][portfolio-code] | Same | confirmed | confirmed | High | Informational | IR loading | implemented | — | Keep. | Portfolio tests passed. |
| PP-002 | §2.3.11; PMF-25 | PolicyPortfolio is not a deployed policy stock or lifetime identity. | Semantic inference | [ADR/code purpose][portfolio-adr] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Medium | IR loading | implemented | — | Keep as current contract semantics. | Static/tests. |
| PP-003 | §2.6 | PolicyPortfolio tests are reusable negative identity fixtures. | Fixture claim | [Tests validate portfolio behavior][portfolio-tests] | Same | fixture_only | fixture_only | High | High | IR test owner | fixture_only | fixture overclaim | Say tests are conceptual negative evidence; add a future explicit anti-identity fixture if needed. | Tests passed but do not assert identity. |
| PP-004 | §4.13; §9.5 | PolicyPortfolio must never become matter registry unless a ratified ADR changes it. | Normative proposal | [Accepted ADR-0022][portfolio-adr]; [P27][failure-register] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Medium | IR/architecture | implemented current semantics | — | Classify current separation as established; future redesign still requires normal ADR/P27 process. | Static. |

## Atlas and projection

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AT-001 | §2.3.1; §4.6.3; PMF-24 | Atlas/projections may not mint identity or authority. | Repo invariant | [Identity decision: no new statuses][identity-status]; [Atlas plan doctrine/debt][atlas-debt] | Same | confirmed | confirmed | High | Critical if violated | Runtime producer + Atlas consumer | documented invariant | — | Keep as governing doctrine. | Selected backend projection tests passed. |
| AT-002 | §2.8; §7.7 | Atlas is currently projection-only. | Implementation-state claim | [Atlas plan admits two minting surfaces][atlas-debt]; [local `approvalReady` code][atlas-code] | Same | contradicted | contradicted | High | High | Atlas/UI with runtime producer debt | implemented_but_noncompliant | overclaim | Say “projection-only is the required boundary; known current violations remain.” | Frontend runtime not executed. |
| AT-003 | §2.5 | Matter projection surface is missing. | Absence claim | No matter term in API/dashboard; [generated run routes][api-client] | Same | confirmed | confirmed | High | Medium | Runtime HTTP/Atlas future consumer | surface_missing | — | Keep. | Static tracked-tree search. |
| AT-004 | §2.8; §7.7 | H2 custody runtime is a consumer, not identity owner. | Ownership/design claim | [H2 is a horizon in identity decision][identity-horizons]; no package/owner | Same | owner_not_established | owner_not_established | High | High | Future plan only | planned_only | premature owner rule | Keep as preferred architecture hypothesis, not freeze. | No runtime. |
| AT-005 | §2.5; §8 | Public correction fan-out is separate and missing. | Repo/planning claim | [PAO-R36 row][wave2-pao36] | Same | confirmed | confirmed | High | High | PAO-R36 future; Atlas/API consumers | planned_only | — | Keep and use it to qualify sidecar sufficiency. | No implemented chain. |
| AT-006 | §2.3.5 | Runtime lineage is a reusable projection/export surface with tenant, valid/tx, audit semantics. | Capability claim | [Lineage service/routes][runtime-lineage]; [TemporalScope][temporal-scope] | Same | partially_supported | partially_supported | Medium | Medium | Runtime HTTP + core temporal | implemented artifact/run surface | overclaim | Split claims: service exports lineage; route layer supplies access/time; matter surface absent. | HTTP tests blocked by missing `jaxlib`. |

## Migration

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MIG-001 | §4.12 | Existing IDs retain their historical meanings and must not be redefined as matter IDs. | Normative recommendation | [Identity above case][identity-decision]; [signature/CAS semantics][signing] | Same | confirmed_with_qualification | confirmed_with_qualification | High | High | Existing identifier owners | compatibility advice | — | Keep as safe Stage-0 advice. | Static. |
| MIG-002 | §4.12 | Signed legacy artifacts retain original bytes. | Repo invariant | [Signature binds blob/manifest hashes][signing]; [CAS ID][artifact-id] | Same | confirmed | confirmed | High | Critical | core.artifacts | implemented | — | Keep. | Signing tests passed. |
| MIG-003 | §4.12 | Additive case-to-matter sidecar associations are the migration method. | Design recommendation | No matter artifact; [PAO-R0 research-only][wave2-pao] | Same | premature_contract | premature_contract | High | High | Missing | artifact_missing | unresolved research question | Say “candidate non-rewrite method,” not migration rule. | No runtime. |
| MIG-004 | §4.12 | Dual-read projections can show corrected current and historical views. | Design recommendation | [TemporalScope exists][temporal-scope]; no matter association reader | Same | planned_not_implemented | planned_not_implemented | High | High | Future owner + temporal/runtime HTTP | consumer_missing | capability overclaim | Keep as required future property, not current capability. | Matter replay impossible. |
| MIG-005 | §4.12; PMF-19 | Existing public URLs remain resolvable with correction/supersession. | Capability/normative claim | [Retention policy has finite classes][retention]; [run routes][api-client] | Same | unsupported | unsupported | High | High | PAO-R36/OPS-R14/INT-R7 | surface_missing | authority overclaim | Replace permanence with open retention/resolver requirement. | No public resolver runtime. |
| MIG-006 | §4.3; §4.9 | Matter identity can preserve immutable origin tenant and transfer current custody. | Design recommendation | [CAS ownership model][artifact-ownership]; no transfer/federation contract | Same | unsupported | unsupported | High | High | Security/external/future owner | planned_only | premature_contract | Move origin/custody-transfer model to open research. | No federation. |
| MIG-007 | §4.5; §4.9 | Every split child and merged result gets a new ID; parents remain resolvable. | Normative proposal | No matter schema/test; [PAO-R0 row only][wave2-pao] | Same | premature_contract | premature_contract | High | High | External/legal + product/architecture | research_only | unresolved research question | Classify as repository-consistent recommendation, jurisdiction/product dependent. | External and benchmark verification required. |
| MIG-008 | §4.12; PMF-10 | One case to many matters must remain structurally possible. | Normative proposal | [PDC has no subject field and forbids extras][pdc-model] | Same | premature_contract | premature_contract | High | High | Future matter/PDC owner | contract_missing | internally unresolved | Preserve as an open cardinality question; do not bind schemas. | PDC field probe confirmed absence. |

## Fixtures and tests

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FIX-001 | §6.5 | The PDC graph fixture is “built from `run-24`.” | Fixture claim | [`run-24` is a literal in compiler test][pdc-tests] | Same | fixture_only | fixture_only | High | High | PDC test-local | fixture_only | fixture overclaim | “A compiler unit-test scenario uses literal `run-24`; no named fixture exists.” | Test passed. |
| FIX-002 | §2.6 | PDC projection tests are reusable. | Fixture/test claim | [Projection test family][projection-tests] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Medium | runtime quality/PDC tests | implemented test pattern | overclaim | Reuse properties/builders, not as matter fixtures. | 37 passed. |
| FIX-003 | §2.6 | PDC anti-LLM-laundering tests exist. | Test claim | [Compiler and projection anti-laundering tests][pdc-tests] | Same | confirmed | confirmed | High | Medium | PDC/runtime quality | implemented | — | Cite exact symbols. | Passed. |
| FIX-004 | §2.6 | Record-family completeness tests reject status-only pass. | Test claim | [Record registry tests][record-tests] | Same | confirmed | confirmed | High | Medium | runtime quality | implemented | — | Keep narrow property. | Passed in batch. |
| FIX-005 | §2.6 | Tenant/CAS governance fixtures are reusable. | Fixture/test claim | [Shared-CAS test][tenant-test] | Same | confirmed_with_qualification | confirmed_with_qualification | High | High | core.artifacts/runtime quality tests | implemented access test | overclaim | Reuse access-control pattern; content IDs intentionally equal and public redaction is red. | Access test passed; redaction failed. |
| FIX-006 | §2.6 | Recall/retraction fixture exists. | Test claim | [`test_scorecard_blocks_recall_retraction…`][recall-test] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Medium | runtime quality | implemented test | inaccurate “fixture” label | Call it an exact test function. | Passed in batch. |
| FIX-007 | §2.6; §6.5 | `lineage_fixture_001` is reusable and proves law-change review. | Fixture/test claim | [Literal and exact test][decision-tests] | Same | fixture_only | fixture_only | High | High | Scientist test-local | fixture_only | fixture overclaim | Separate: test property confirmed; named fixture claim rejected. | Test passed. |
| FIX-008 | §2.6 | Legacy-packet fixture proves sticky trigger migration behavior. | Test claim | [Legacy packet test][decision-tests] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Medium | Scientist validation | implemented test pattern | overclaim | Limit to decision-validity legacy packet; no matter migration. | Passed. |
| FIX-009 | §2.6 | Partial-reissue fixture preserves unaffected scope. | Test claim | [Partial reissue tests][reissue-tests] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Medium | Scientist continuous governance | implemented test pattern | overclaim | Keep claim/packet scope qualification. | Passed. |
| FIX-010 | §2.6 | Lifecycle bridge fixtures prove append-only bridge behavior. | Test claim | [Lifecycle bridge tests][lifecycle-tests] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Medium | Scientist continuous governance | implemented test pattern | overclaim | Keep exact symbols; no matter bridge. | Passed. |
| FIX-011 | §2.6 | Lex version-selection fixtures exist and are reusable. | Test claim | [Fabric Lex corpus tests][lex-tests] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Medium | Data Forge/Lex test topology | implemented test pattern | inaccurate path | Cite actual path; legal-document scope only. | Selected tests passed. |
| FIX-012 | §2.6 | Runtime lineage `valid_at`/`tx_at` tests verify reusable matter plumbing. | Test/capability claim | [Lineage test source][lineage-tests]; [TemporalScope][temporal-scope] | Same | external_verification_required | external_verification_required | Medium | Medium | runtime HTTP | implemented artifact/run tests, unexecuted here | runtime blocker | Say tests exist; audit could not execute; no matter semantics. | Blocked by missing `jaxlib`. |
| FIX-013 | §2.6 | Audit export/offline verification fixtures are reusable. | Test claim | [Audit tests][audit-tests] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Medium | core.audit | implemented | overclaim | Reuse packaging/integrity patterns only. | Selected round trip passed. |
| FIX-014 | §2.6 | PolicyPortfolio tests are negative non-identity fixtures. | Fixture claim | [Portfolio tests][portfolio-tests] | Same | fixture_only | fixture_only | High | High | IR tests | fixture_only | fixture overclaim | State they test portfolio composition; future explicit anti-identity fixture is missing. | Tests passed but not identity property. |

## Capability-state claims

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAP-001 | §2.5 | Typed matter contract is `contract_only`. | Capability claim | [Only decision/backlog mention it][wave2-pao]; no type/schema | Same | contradicted | contradicted | High | High | Missing | planned_only / documented_only | capability mislabel | Replace `contract_only` with `planned_only`/`documented_only`. | Static. |
| CAP-002 | §2.3.1 | PDC graph capability is implemented. | Capability claim | [Compiler/model/persistence][pdc-compile]; [tests][pdc-tests] | Same | confirmed | confirmed | High | Informational | PDC | implemented | — | Keep graph-structure scope. | 4 tests passed. |
| CAP-003 | §2.3.4 | Technical artifact lineage is implemented. | Capability claim | [IR lineage graph][artifact-lineage] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Informational | IR artifacts | implemented | — | Keep; no matter relations. | Static/test patterns. |
| CAP-004 | §2.3.8 | Legal-document identity/version evidence is implemented. | Capability claim | [Data Forge versioning + Lex facade][legal-versioning] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Informational | Data Forge + Lex | implemented | wrong owner in report | Correct producer/consumer ownership. | Selected tests passed. |
| CAP-005 | §2.3.6; §2.5 | Decision validity is implemented but case/decision scoped. | Capability claim | [Contract/service/tests][decision-contract] | Same | confirmed_with_qualification | confirmed_with_qualification | High | Medium | core.contracts + Scientist | implemented, decision scoped | — | Keep; disclose tenant key and fan-out gaps. | Tests passed. |
| CAP-006 | §2.3.7; §2.5 | Claim lifecycle/reissue is implemented but matter bridge missing. | Capability claim | [Lifecycle/reissue][lifecycle-bridge] | Same | confirmed | confirmed | High | Medium | Scientist continuous governance | implemented narrower / bridge_missing | — | Keep exact scope. | Tests passed. |
| CAP-007 | §2.3.9; §2.5 | Portable audit verification is implemented for artifacts/runs. | Capability claim | [Audit README/tests][audit-readme] | Same | confirmed | confirmed | High | Informational | core.audit | implemented | — | Keep; matter semantics absent. | Selected test passed. |
| CAP-008 | §2.5 | Matter surface is missing. | Capability claim | [API client is run-oriented and no matter term exists][api-client] | Same | confirmed | confirmed | High | Medium | Runtime HTTP/Atlas future | surface_missing | — | Keep. | Static; HTTP suite blocked. |
| CAP-009 | §2.7; §4.11 | Matter-aware authority fan-out/public correction exists as reusable fragments. | Capability inference | [OPS-R2 and PAO-R36 are planned research][wave2-ops] | Same | planned_not_implemented | planned_not_implemented | High | High | Future OPS-R2/PAO-R36 | bridge_missing / consumer_missing | overclaim | Say narrower fragments exist; complete chain is absent. | No runtime. |
| CAP-010 | Executive; §2.5 | Overall matter capability is contract-only plus missing bridge/tests/surface, surrounded by orchestratable fragments. | Capability summary | All chain evidence above | Same | contradicted | contradicted | High | High | Missing | planned_only + producer/artifact/bridge/consumer/verification/surface missing | incomplete chain | Use the corrected seven-element missing chain; do not imply an existing contract or orchestration. | Static plus targeted tests. |

## Absence claims

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ABS-001 | §2.4 | No `PolicyMatter` runtime/source/schema/API implementation. | Absence claim | Full tracked-tree census; [only docs row][wave2-pao] | Same | confirmed | confirmed | High | High | Missing | planned_only | — | Include exact terms, paths, exclusions, SHAs, and blind spots. | No external DB/service. |
| ABS-002 | §2.7 | No canonical matter schema or identifier registry. | Absence claim | No matter symbols/migrations; [public surface has no PDC/matter package][public-surface] | Same | confirmed | confirmed | High | High | Missing | contract_missing | — | Keep. | Static. |
| ABS-003 | §2.7 | No case-to-matter typed association or split/merge cardinality. | Absence claim | [Strict PDC model has no subject/matter fields][pdc-model] | Same | confirmed | confirmed | High | High | Missing | artifact_missing | — | Keep with PDC/non-PDC search scope. | PDC field probe. |
| ABS-004 | §2.7 | No matter-aware invalidation/fan-out. | Absence claim | [OPS-R2 is future research][wave2-ops]; no matter refs | Same | confirmed | confirmed | High | High | Missing/future OPS-R2 | bridge_missing | — | Keep. | Static. |
| ABS-005 | §2.7 | No correction path for cryptographically valid wrong-matter record. | Absence claim | [Signature code has integrity only][signing]; [PAO-R36 planned][wave2-pao36] | Same | confirmed | confirmed | High | High | Future owner + PAO-R36/INT-R7 | consumer_missing / surface_missing | — | Keep; separate integrity verification from semantic correction. | No runtime path. |
| ABS-006 | §2.7 | No matter-aware cross-tenant isolation tests. | Absence claim | [Shared CAS tests are artifact/runtime refs only][tenant-test]; no matter term | Same | confirmed | confirmed | High | High | Security/future matter owner | semantic_test_missing | — | Keep; do not misstate existing CAS isolation as absent. | Static. |
| ABS-007 | §2.1 limitation | Connector search provides high-confidence absence despite failed local clone. | Method claim | This audit completed a full clone and exhaustive `rg`/Git search; original report did not | Same | absence_not_proven | absence_not_proven | High | High | Research methodology | N/A | incomplete search | Replace original negative-method statement with this audit's exact census; acknowledge ignored/external blind spots. | Full tracked-tree search now available. |

## External-source claims

| Claim ID | Report location | Exact claim | Claim class | Historical evidence | Current evidence | Historical verdict | Current verdict | Confidence | Severity | Canonical owner | Capability label | Problem type | Required correction | Runtime verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EXT-001 | §3.1 | No single pattern exists for lifetime public-policy identity. | External-source/absence claim | [Enumerated source corpus in report]; no exhaustive universe | Same | external_verification_required | external_verification_required | Medium | Medium | External research | research_only | absolute negative | “No single pattern was identified in the enumerated review corpus.” | Broader systematic review required. |
| EXT-002 | §3.2 | W3C PROV models entities/activities/agents/provenance but leaves domain identity external. | External-source claim | [Official W3C PROV-DM](https://www.w3.org/TR/prov-dm/) | Same source | confirmed_with_qualification | confirmed_with_qualification | High | Low | W3C/external | documented standard | — | Keep bounded wording. | External primary source checked. |
| EXT-003 | §3.2 | Akoma Ntoso/ELI support legal-document identity/version semantics, not policy identity. | External-source claim | [OASIS Akoma Ntoso](https://docs.oasis-open.org/legaldocml/akn-core/v1.0/akn-core-v1.0-part1-vocabulary.html); [ELI](https://op.europa.eu/en/web/eu-vocabularies/eli) | Same | confirmed_with_qualification | confirmed_with_qualification | High | Low | OASIS/EU/external | documented standard | — | Keep as bounded distinction. | Primary sources checked. |
| EXT-004 | §3.2 | DataCite provides typed version/continuation/part relations whose meaning depends on stewardship. | External-source claim | [DataCite relation types](https://support.datacite.org/docs/connecting-to-works) | Same | confirmed | confirmed | High | Low | DataCite/external | documented standard | — | Keep. | Official source checked. |
| EXT-005 | §3.2; §4.9 | ARK supports opaque/persistent/non-reassigned identifier guidance. | External-source claim | [ARK overview](https://arks.org/about/ark-overview/) | Same | confirmed_with_qualification | confirmed_with_qualification | High | Low | ARK Alliance/external | documented guidance | overclaim | Use as design analogy; governance, not syntax, supplies persistence. | Official source checked. |
| EXT-006 | Appendix B | “DOI Foundation guidance” is linked to ARK features. | Citation-quality claim | Supplied title/URL mismatch; [DOI Handbook](https://www.doi.org/doi-handbook/) | Same | contradicted | contradicted | High | Medium | External citation owner | N/A | wrong URL/title | Link official DOI source or relabel the row as ARK. | External link checked. |
| EXT-007 | §3.2 | Fellegi–Sunter/Sadinle support uncertain or possible linkage. | External-source claim | [Fellegi–Sunter DOI](https://doi.org/10.1080/01621459.1969.10501049); [Sadinle DOI](https://doi.org/10.1080/01621459.2016.1148612) | Same | confirmed_with_qualification | confirmed_with_qualification | High | Low | External research | documented method | — | Keep; statistical linkage grants no legal authority. | Primary/publisher records checked. |
| EXT-008 | §3.2; Appendix B | ResearchGate bitemporal link is acceptable primary research citation. | Citation-quality claim | Supplied ResearchGate page; [primary IEEE record](https://ieeexplore.ieee.org/document/344056) | Same | contradicted | contradicted | High | Medium | External citation owner | N/A | secondary/incorrect source choice | Cite underlying primary publication or author report. | Source quality checked. |
| EXT-009 | §3.2 | GLEIF event model supports name changes, mergers, demergers, acquisitions, status/effective dates. | External-source claim | [GLEIF Legal Entity Events](https://www.gleif.org/en/lei-data/gleif-golden-copy/download-the-golden-copy#/lei-data/lei-mapping/download-lei-relationship-data) and official policy materials | Same | confirmed_with_qualification | confirmed_with_qualification | Medium | Low | GLEIF/external | documented model | citation precision | Cite official event-policy/model page, not only L1 ontology landing page. | Targeted check only. |
| EXT-010 | §3.2 | Federal Program Inventory is official registry evidence with granularity/alignment limits. | External-source claim | [Federal Program Inventory](https://fpi.omb.gov/about/fpi) | Same | confirmed_with_qualification | confirmed_with_qualification | High | Low | OMB/external | documented registry | — | Keep bounded wording. | Official source checked. |
| EXT-011 | §3.2 | Memento preserves historical representations, not policy identity. | External-source claim | [RFC 7089](https://www.rfc-editor.org/rfc/rfc7089.html) | Same | confirmed | confirmed | High | Low | IETF/external | documented standard | — | Keep. | Primary standard checked. |

## Failure-pattern correction sub-ledger

The report's failure-pattern table is important enough to restate atomically. These rows
refine F-05 and do not increase the 123-claim summary count; they are corrections to the
claims already represented in owner/status/temporal/fixture rows.

| Report usage | Actual register entry | Historical correctness | Current correctness | Required correction |
| --- | --- | --- | --- | --- |
| P01 — contract-only capability | P01 — Contract-only capability | Correct concept, but matter state is not `contract_only` because no typed contract exists. | Same | Use P01 for the future risk; label current state `planned_only`. |
| P02 — fragments without bridge | P02 — Component sophistication with thin orchestration | Substantively close. | Same | Use exact title. |
| P03 — internal state without surface | P03 — Internal richness with poor external surface | Substantively close. | Same | Use exact title. |
| P05/P15 — prose or projection becomes authority | P05 is authority dilution; P15 is LLM speculation laundering | Conflated. | Same | Use P05 for projection/diagnostic authority and P15 only for LLM-generated identity claims. |
| P07/P08 — wrong run or closure | P07 is schema versioning without rule evolution; P08 is time semantics fragmentation | Wrong. | Same | Use P07 for rule-version replay and P08 for clock-role collapse; run/matter confusion needs direct identifier tests. |
| P10 — structural completeness ≠ semantic adequacy | P10 — Structural-only validation | Correct. | Same | Keep exact title. |
| P12 — meaning resolved after emission | P12 — Producer fragmentation | Wrong/shifted. | Same | Use for cross-producer subject/scope handshake; silent reassignment needs correction/replay rules. |
| P13 — governance scope inflation | P13 — Contract gravity well | Partly related but wrong title/meaning. | Same | Use for disproportionate universal envelope/gate cost. |
| P14 — evidence inflation | P14 — Raw evidence count inflation | Substantively close. | Same | Link identity continuity to evidence-independence/transport review. |
| P26 — wrong fallback | P26 — Responsibility-integrity laundering | Wrong. | Same | Use P26 for human adjudicator mandate/information; fail-closed fallback is not P26. |
| P27 — duplicate canonical owner | P27 — Parallel re-implementation / canonical-owner bypass | Correct. | Same | Keep and apply it to the report's own PDC owner claim. |
| P29 — projection/canonical drift | P29 — Authorial proof / self-attested artifact | Wrong. | Same | Use P29 for the authored benchmark/fixture proving itself. |
| P32 — temporal context missing | P32 — Trust-by-form | Wrong. | Same | Use P32 for generic metadata/ref/shape admitted without resolve-bind-verify. |
| P33 — untyped artifact admission | P33 — Witness-as-spec / teaching-to-the-test | Wrong. | Same | Use P33 for overfitting to named fixtures; untyped admission is P32/P05/P10. |
| Omitted P04 | P04 — Status enum proliferation | Material omission. | Same | Apply to `support_status`, identity outcomes, and Atlas mapping. |

## Evidence permalink definitions

[identity-decision]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md#L123-L139
[identity-status]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md#L180-L189
[identity-horizons]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md#L151-L160
[wave2-pao]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md#L450-L458
[wave2-ledger]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md#L537-L546
[wave2-waist]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md#L83-L97
[wave2-ops]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md#L423-L430
[wave2-pao36]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md#L455-L460
[pdc-readme]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/pdc/README.md#L1-L6
[pdc-model]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/pdc/_impl/compiler.py#L231-L276
[pdc-compile]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/pdc/_impl/compiler.py#L302-L386
[pdc-tests]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/tests/unit/pdc/test_runtime_policy_design_case_compiler.py#L22-L260
[projection-tests]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py#L465-L682
[record-tests]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/tests/unit/runtime/quality/test_policy_design_case_record_registry.py#L50-L120
[rq-readme]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/runtime/quality/README.md#L1-L26
[contracts-readme]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/contracts/README.md#L1-L25
[governed-projections]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/runtime/http/services/governed_projections.py#L304-L330
[artifact-id]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/artifacts/ids.py#L13-L31
[artifact-manifest]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/artifacts/manifest.py#L212-L255
[artifact-ownership]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/artifacts/ownership.py#L54-L105
[artifact-lineage]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/ir/artifacts/lineage.py#L1-L120
[signing]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/artifacts/signing.py#L67-L78
[audit-readme]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/audit/README.md#L1-L35
[audit-tests]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/tests/unit/core/phase0/test_audit_export_verify.py#L61-L166
[tenant-test]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/tests/unit/runtime/quality/test_multi_tenant_shared_cas.py#L43-L138
[public-redaction-test]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/tests/unit/runtime/quality/test_multi_tenant_shared_cas.py#L140-L178
[recall-test]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/tests/unit/runtime/quality/test_tenant_cas_approval_governance.py#L155-L180
[decision-contract]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/contracts/decision_validity.py#L1-L180
[decision-store]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/scientist/validation/decision_validity.py#L94-L148
[decision-tests]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/tests/unit/scientist/validation/test_decision_validity_service.py#L52-L215
[lifecycle-bridge]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/scientist/governance/continuous/lifecycle_bridge.py#L1-L220
[lifecycle-tests]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py#L62-L215
[reissue-tests]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/tests/unit/scientist/governance/continuous/test_reissue_partial_scope.py#L36-L145
[lex-types]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/lex/types.py#L1-L90
[lex-readme]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/lex/README.md#L1-L80
[legal-versioning]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/data_forge/domains/legal/corpus/versioning.py#L123-L220
[lex-tests]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/tests/unit/fabric/test_lex_corpus.py#L131-L220
[ddm-readme]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/ddm/README.md#L1-L100
[portfolio-adr]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/adr/0022-policy-portfolio-ir-extension.md#L1-L45
[portfolio-code]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/ir/loading/portfolio.py#L160-L225
[portfolio-tests]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/tests/unit/ir/test_policy_portfolio.py#L1-L130
[public-surface]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/architecture/public_surface/contract.toml#L130-L180
[atlas-debt]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md#L1072-L1088
[atlas-code]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts#L917-L1028
[runtime-lineage]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/runtime/http/services/lineage.py#L1-L220
[lineage-tests]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/tests/unit/runtime/http/test_lineage_api.py#L1-L240
[api-client]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/packages/runtime-api-client/canonicalRuntimeApiClient.ts#L1320-L1400
[temporal-scope]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/core/contracts/runtime.py#L595-L617
[capability-scope]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/runtime/quality/capability_index.py#L34-L65
[capability-authority]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/runtime/quality/capability_authority.py#L23-L60
[applicability]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/ir/analytics/applicability.py#L60-L120
[failure-register]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/reference/policy-design-case-failure-patterns.md#L42-L78
[capability-chain]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/reference/policy-design-case-failure-patterns.md#L16-L21
[retention]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/reference/operations/retention-and-recovery.md#L1-L140
[honest-diagnostics]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/system-design-decisions/honest-diagnostics-substrate.md#L1-L40
[honest-log]: https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/system-design-decisions/honest-diagnostics-substrate-decision-log.md#L1-L25
