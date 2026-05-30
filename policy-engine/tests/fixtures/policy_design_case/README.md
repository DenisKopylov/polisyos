# Policy Design Case Contract Fixtures

Owner: `team-runtime-quality`
Consumer: `tests/repo_quality/tools/test_policy_design_case_contract_fixtures.py`
Phase: `Policy Design Case Implementation Plan` Phase 1.1

These fixtures freeze minimal contract examples for accepted ADRs 0156-0161.
They are not production schemas yet. They are contract-shaped examples that
later producer, reader, scorecard, readiness, drift, and closeout tests can use
without inferring authority from static inventory alone.

Every fixture wraps its payload in `runtime_authority_envelope`. Passing
fixtures use a runtime event ref, CAS artifact ref, closed same-input closure,
and `producer_authority`. Rejected fixtures intentionally include a
`static_inventory_candidate` and are fail-closed as `not_authoritative`.

| Fixture | ADR | Contract | SDD record family coverage | Expected |
| --- | --- | --- | --- | --- |
| `runtime_assurance_profile_pass` | ADR-0156 | `policy_design_case.runtime_assurance_profile.v1` | `claim_argument_evidence_case.v1` | pass |
| `runtime_assurance_profile_static_inventory_rejected` | ADR-0156 | `policy_design_case.runtime_assurance_profile.v1` | `claim_argument_evidence_case.v1` | rejected |
| `intent_capability_authority_profile_pass` | ADR-0157 | `policy_design_case.intent_capability_authority_profile.v1` | `intent_authoring_and_capture_risk.v1`, `capability_mode_and_fallback_selection.v1` | pass |
| `intent_capability_authority_profile_static_inventory_rejected` | ADR-0157 | `policy_design_case.intent_capability_authority_profile.v1` | `intent_authoring_and_capture_risk.v1`, `capability_mode_and_fallback_selection.v1` | rejected |
| `concept_jurisdiction_spine_pass` | ADR-0158 | `policy_design_case.concept_jurisdiction_spine.v1` | `concept_and_jurisdiction_spine.v1` | pass |
| `concept_jurisdiction_spine_static_inventory_rejected` | ADR-0158 | `policy_design_case.concept_jurisdiction_spine.v1` | `concept_and_jurisdiction_spine.v1` | rejected |
| `jurisdiction_spine_multi_jurisdiction_pass` | ADR-0158 | `policy_design_case.concept_jurisdiction_spine.v1` | `concept_and_jurisdiction_spine.v1` | pass |
| `jurisdiction_spine_unresolved_competence_rejected` | ADR-0158 | `policy_design_case.concept_jurisdiction_spine.v1` | `concept_and_jurisdiction_spine.v1` | rejected |
| `producer_evidence_contracts_pass` | ADR-0159 | `policy_design_case.producer_evidence_contracts.v1` | `legal_authority_and_competence.v1`, `data_source_semantic_lineage.v1`, `scholar_academic_evidence.v1` | pass |
| `producer_evidence_contracts_static_inventory_rejected` | ADR-0159 | `policy_design_case.producer_evidence_contracts.v1` | `legal_authority_and_competence.v1`, `data_source_semantic_lineage.v1`, `scholar_academic_evidence.v1` | rejected |
| `portfolio_synthesis_contract_pass` | ADR-0160 | `policy_design_case.portfolio_synthesis_contract.v1` | `evidence_portfolio_and_synthesis.v1` | pass |
| `portfolio_synthesis_contract_static_inventory_rejected` | ADR-0160 | `policy_design_case.portfolio_synthesis_contract.v1` | `evidence_portfolio_and_synthesis.v1` | rejected |
| `claim_argument_closeout_gate_pass` | ADR-0161 | `policy_design_case.claim_argument_closeout_gate.v1` | `claim_argument_evidence_case.v1` | pass |
| `claim_argument_closeout_gate_static_inventory_rejected` | ADR-0161 | `policy_design_case.claim_argument_closeout_gate.v1` | `claim_argument_evidence_case.v1` | rejected |

Wave 6 adds `walking_skeleton_case_contract_pass`, a full research-profile
`policyos.runtime.policy_design_case.v1` fixture. It proves the vertical ref
path from intent, to stub concept and jurisdiction refs, to one runtime-quality
stub producer evidence record, to one major claim with an accepted
`single_line_evidence_deficit`. The fixture is explicitly non-production:
governed and production profiles must reject that accepted deficit.

The rejected examples cover the Phase 1.1 negative control: a static ADR row,
manifest role, local path, dashboard projection, or narrative citation may
describe what should exist, but it cannot satisfy serious-run Policy Design
Case authority unless a runtime producer emits a compatible envelope.

W1.B adds `semantic_false_passes/`, a production-quality semantic gold-card
pack. Those fixtures intentionally keep `structural_verdict.status=pass` while
the semantic evaluator derives failures for projection laundering,
participation laundering, raw-count inflation, method mismatch, stale evidence,
LLM speculation laundering, and unsupported claims.
