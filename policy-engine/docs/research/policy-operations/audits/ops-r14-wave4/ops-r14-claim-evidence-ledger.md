---
title: "OPS-R14 Claim-Evidence Ledger"
audit_id: OPS-R14-WAVE4-INDEPENDENT-AUDIT
status: completed
verified_commit: 3a694212aa47c4c2d8a631f8edc4ba8f7e15dce7
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
authoritative_for:
  - independent_mapping_of_ops_r14_claims_to_evidence
  - bounded_support_verdicts_for_consolidation
  - identification_of_overstatement_and_unowned_dependencies
may_not_use_for:
  - production_implementation_authorization
  - production_capability_claim
  - final_wire_schema_package_database_serialization_or_api_contract
  - canonical_owner_vendor_custodian_archive_service_or_escrow_appointment
  - authority_or_delegation_grant
  - legal_sufficiency_or_jurisdictional_conclusion
  - permission_to_publish_sign_or_open_a_gate
  - creation_or_amendment_of_a_status_lattice
  - automatic_amendment_of_any_plan_backlog_or_system_design_decision
  - assessment_or_adoption_of_pao_r36_quality
research_only: true
---

# OPS-R14 claim-evidence ledger

## 1. Verdict vocabulary

- **supported** — the offered evidence establishes the bounded claim as written;
- **supported with qualification** — the direction holds, but a denominator, scope, or inference must
  be stated more narrowly;
- **partially supported** — material parts hold and material parts are not established;
- **not established** — the evidence does not settle the proposition;
- **refuted** — the offered evidence contradicts the proposition.

This ledger audits claims, not implementation feasibility. A sound research requirement is not a
repository capability.

## 2. Load-bearing claim map

| Claim ID | Load-bearing claim | Offered evidence | Audit verdict | Finding / consolidation consequence |
| --- | --- | --- | --- | --- |
| C-01 | PolicyOS cannot presently **claim** custody-grade resilience for its own signed records. | Seven missing operational/institutional elements in the primary report `:31-55`; repository handoff; no qualifying drill. | **Supported.** | `OPS-R14-III-002`. This is an authority-band refusal, not a ban on building or candidate research. |
| C-02 | The task result itself should stand as unqualified `NO_GO`. | Frontmatter and final line in the primary report; the body also supplies a complete selected architecture. | **Partially supported.** | `OPS-R14-III-001` blocking. Split research-result standing from operational capability/gate standing. |
| C-03 | The selected hybrid architecture is preferable to one all-store snapshot, alerts alone, or runbooks alone. | Comparative table in primary `:134-167`; detailed independent-path and restored-predicate analysis in custody objectives. | **Supported.** | Preserve. The eliminating properties are explicit. |
| C-04 | Per-class RPO/RTO values are meaningful because they bind a declared loss model and an evidence predicate. | `custody-class-objectives-and-recovery-closure.md:31-218`, including acknowledgement, loss domains, class table and `RC-01`–`RC-09`. | **Supported.** | `OPS-R14-III-004` commendation. Numbers remain research targets, not capability or legal minima. |
| C-05 | Restoring CAS while control state is absent violates a named invariant and is detectable. | `RC-01`–`RC-03`; F-01; orphan-content negative assertion and independent high-water mark. | **Supported.** | Preserve. It directly answers the commission's asymmetric-store requirement. |
| C-06 | An authentic restored snapshot may still be stale and cannot establish current authority. | `RC-03`, `RC-07`, F-09, INT-R7 anti-rollback input. | **Supported.** | Preserve. Authentication and latest-applicable selection remain separate. |
| C-07 | Expiry is widespread as time/TTL state but absent as a governed renewal event. | Supplied source census; exact low-cardinality search; absence of `WatchedDependencyRecord`, renewal-owner/evidence/query concepts; worker lease is unrelated. | **Supported with qualification.** | Exact high-cardinality matching-line/occurrence totals remain unreproduced in this environment (`OPS-R14-I-002`), but the semantic conclusion is independently supported. |
| C-08 | `renewal` occurs in four all-file source files, but only once in Python, where it means worker-lease renewal. | Orientation ledger and exact file reads. | **Supported.** | `OPS-R14-I-001` and `OPS-R14-I-003`. State both denominators. |
| C-09 | Worker lease renewal is implemented but cannot evidence authority renewal. | `runtime/http/services/control_worker.py:84-174`; explicit guard in repository handoff. | **Supported.** | Preserve the preemptive anti-laundering guard. |
| C-10 | WD-01–WD-12 form a checkable owner-neutral semantic contract rather than a schema. | Each clause names inputs, verifier behavior and verdict; artifact expressly forbids wire/schema selection. | **Supported.** | Preserve. No implementation authority follows. |
| C-11 | WD-12 prevents expiry from being extended by a failed scheduler. | WD-03, WD-12 and F-13. | **Supported.** | Safety side passes. |
| C-12 | The watched-dependency model also ensures expiry surfaces prospectively as a scheduled dependency event rather than first at runtime. | WD-05 watcher notices; WD-12 protected-use fallback. | **Partially supported.** | `OPS-R14-V-001` material. Add a measurable durable due-event delivery/reconciliation proposition; fail-closed use checking alone is not prospective scheduling evidence. |
| C-13 | The eleven commissioned rights partition into six structurally different renewal families. | Families and eleven mappings in watched-dependency artifact `:167-360`. | **Supported.** | `OPS-R14-V-003` commendation. The partition is exhaustive and each family changes who can establish renewal. |
| C-14 | For external/bilateral instruments, local intent cannot complete renewal. | DSA/licence/audit/contract examples; external instrument and counterparty evidence. | **Supported with qualification.** | `OPS-R14-V-002`. Use “local intent alone cannot establish renewal”; a competent unilateral option exercise can be a locally performed act because an existing instrument authorizes it. |
| C-15 | A legal hold is an orthogonal disposal override, not a validity/currentness grant or a rewritten retention class. | LH rules and primary `:300-322`; narrow source implementation and GC tests. | **Supported.** | `OPS-R14-V-004` commendation. Preserve multiple-hold aggregation and separate post-release disposal decision. |
| C-16 | The repository implements a complete legal-hold lifecycle. | Narrow retention enum/tag and snapshot GC path. | **Refuted by the work itself.** | The report correctly labels the complete lifecycle absent/unallocated. |
| C-17 | Long-term replay preserves historical issuance across key, algorithm, format, source and organization change. | RP-01–RP-11; INT-R7 controlling lifecycle; F-05, F-06, F-09–F-12. | **Supported as research semantics.** | `OPS-R14-VII-001`. No repository capability is claimed. |
| C-18 | A present preservation/replay failure never rewrites a historically authentic record. | RP-01, RP-05, RP-10, RP-11; `RC-06`; F-05, F-09, F-11; PV-K02. | **Supported.** | Strong kernel conformance. |
| C-19 | RP-10 closes PAO-R36 F11, “recovery must never un-correct a record.” | RP-10 alone plus RC-01/RC-07/F-04/DE-07 in the wider package. | **Supported at package level, not by RP-10 alone.** | `OPS-R14-VIII-001`. Consolidation should cite the complete closure set. |
| C-20 | OPS-R14 answers all five PAO-R36 interface requests without defining correction semantics. | RC-01/RC-07, RP-10, LH-05, WD-03/08/10, F-04 and DE-07. | **Supported.** | Preserve the seam. PAO-R36 remains unadjudicated. |
| C-21 | All thirteen disaster fixtures are executable semantic specifications. | Each has corpus, attack/failure, exact expected outcome, invariant and detection. | **Supported.** | `OPS-R14-VI-004`. Coverage is not complete; see C-22. |
| C-22 | The fixture suite covers the important asymmetric recovery and succession space completely. | F-01–F-13. | **Not established.** | `OPS-R14-VI-001` and `OPS-R14-VI-002`. Add scoped lawful split succession, common-mode false independence, authenticated-time rollback and parser/canonicalization differential attacks. |
| C-23 | DE-01–DE-10 prevent a paper runbook from satisfying DR closeout. | Frozen scope, actual injection, clean/independent restore, disconnected execution, measurements, predicates, evidence integrity and retest. | **Supported.** | `OPS-R14-VI-005`. Phase A is non-circular because it uses a ceremonial non-authoritative corpus. |
| C-24 | Current acceptance evidence marks recovery posture green from policy/runbook presence and closes a tabletop by reading a runbook. | `platform-acceptance.md:15,23,30`; `platform-acceptance-manual.md:85-95`. | **Supported with qualification.** | `OPS-R14-IV-001`/`IV-002`. It exposes a documentation-versus-exercised-evidence ambiguity; the baseline does not explicitly claim custody-grade DR passage. |
| C-25 | The external source ledger uses current primary sources and honest transfer limits in two jurisdictions. | 20 rows/23 URLs across U.S., UK and standards. | **Mostly supported.** | `OPS-R14-II-003`; repair contract-specific procurement inference and update the ICO guidance link (`II-001`, `II-002`). |
| C-26 | No commercial continuity/IT-DR pattern is imported as a public-record legal conclusion. | NIST/FEMA rows explicitly transfer testing, impact analysis and exercise discipline only. | **Supported.** | Preserve. No legal mandate, vendor, or numerical RPO/RTO is imported. |
| C-27 | Capability labels obey repository prerequisites. | Handoff matrix and explicit non-use of producer/bridge/verification labels. | **Supported except two wording issues.** | `OPS-R14-IX-001`, `IX-002`, `IX-003`. Replace the custom documentation label; qualify GY-N12's contract level. |
| C-28 | The work does not create a second currentness/chronology owner. | GY-N12 interface and repeated ownership disclaimers; `RC-04`, WD-03, RP-07/RP-10. | **Supported.** | `OPS-R14-VII-002`. |
| C-29 | The work remains inside OPS-R14 and does not absorb OPS-R12. | Explicit failure-model exclusion and interface boundary. | **Supported.** | `OPS-R14-X-001`. |
| C-30 | All hard prohibitions hold. | Eight frontmatter blocks; no vendor/custodian appointment, final schema, legal-sufficiency claim, publication permission or capability claim. | **Supported.** | Preserve frontmatter and boundary language. |

## 3. Competence assessment

### Engineering

**Strong.** Mechanisms are named and rules are normally paired with a verifier, input and outcome.
The major engineering gap is prospective event-timeliness evidence: WD-12 safely blocks use after
expiry, but does not by itself prove the watch delivered a governed dependency event before expiry.

### Mathematical / systems

**Very strong.** The work defines durable acknowledgement, explicit failure domains, divergence
invariants, per-class objectives and a clause-by-clause restored predicate. The principal suite gap is
not mathematical vagueness but missing adversarial coverage of common-mode independence and trusted
time.

### Public administration

**Strong with one material qualification.** Delegation, consent, fiscal authority, bilateral
agreement, audit rights and records holds are treated as different institutional propositions. The
source transfer ledger is unusually disciplined. Procurement survival/audit-right statements must be
marked contract-specific rather than statutory universals.
