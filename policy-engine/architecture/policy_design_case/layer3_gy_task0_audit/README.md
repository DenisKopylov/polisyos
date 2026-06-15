# GY Task 0 Audit Artifacts

Date: 2026-06-14
Scope: repo-wide GY engine-subordination research before GY-0.5 planning.
Mode: audit-only; these files are evidence and gap maps, not repair plans.

This folder is the canonical place for GY Task 0 research artifacts. Validators
live under `tools/quality/validation/`, and repo-quality tests live under
`tests/repo_quality/tools/`.

## Start Here

- `layer3_gy_system_audit_gap_map.md` — running gap map and audit order.
- `layer3_gy_capability_coverage_matrix.json` — repo-wide capability × chain-stage grid (audit-order #1) synthesizing all 14 audits.
- `layer3_gy_capability_coverage_matrix_findings.md` — coverage heatmap, the "diagonal" reading, and the global Task 0 review.
- `layer3_gy_p2_semantic_evidence_quality_audit.json` — P2 semantic adequacy pass for catalog search, Scholar/OpenAlex, and KnowledgeToolkit.
- `layer3_gy_p2_semantic_evidence_quality_findings.md` — P2 plan-impact findings.
- `layer3_gy_p1_substrate_authority_audit.json` — P1 substrate authority pass for CAS, time, secrets/PII, and cost/VOI.
- `layer3_gy_p1_substrate_authority_findings.md` — P1 plan-impact findings.
- `layer3_gy_p0_coverage_audit.json` — P0 closure pass for production worker, candidate-positive firewall, blocked DAG inputs, and depth-2 generalization.
- `layer3_gy_p0_coverage_findings.md` — P0 plan-impact findings.
- `layer3_gy_engine_census.json` — pinned-route engine census.
- `layer3_gy_engine_census_findings.md` — census methodology and plan-changing findings.

## Follow-Up Audits

| Area | Machine artifact | Findings |
| --- | --- | --- |
| P2 semantic evidence quality: catalog search / Scholar-OpenAlex / KnowledgeToolkit | `layer3_gy_p2_semantic_evidence_quality_audit.json` | `layer3_gy_p2_semantic_evidence_quality_findings.md` |
| P1 substrate authority: CAS/time/secrets/PII/cost-VOI | `layer3_gy_p1_substrate_authority_audit.json` | `layer3_gy_p1_substrate_authority_findings.md` |
| P0 production worker/firewall/blocked reads/depth-2 coverage | `layer3_gy_p0_coverage_audit.json` | `layer3_gy_p0_coverage_findings.md` |
| Runtime/API/dashboard/public export surfaces | `layer3_gy_runtime_surface_audit.json` | `layer3_gy_runtime_surface_audit_findings.md` |
| Catalog binding to fetch to measurement root | `layer3_gy_catalog_fetch_audit.json` | `layer3_gy_catalog_fetch_audit_findings.md` |
| Connector family truth | `layer3_gy_connector_family_truth_audit.json` | `layer3_gy_connector_family_truth_findings.md` |
| Rights/freshness/source-contract admissibility | `layer3_gy_source_contract_admissibility_audit.json` | `layer3_gy_source_contract_admissibility_findings.md` |
| Data requirement compiler | `layer3_gy_data_requirement_compiler_audit.json` | `layer3_gy_data_requirement_compiler_findings.md` |
| Lex root cause and search frontier semantics | `layer3_gy_lex_frontier_root_cause_audit.json` | `layer3_gy_lex_frontier_root_cause_findings.md` |
| Foundry breadth | `layer3_gy_foundry_breadth_audit.json` | `layer3_gy_foundry_breadth_findings.md` |
| Agent workflow event backing | `layer3_gy_agent_workflow_event_backing_audit.json` | `layer3_gy_agent_workflow_event_backing_findings.md` |
| Governance/generated artifacts/public lifecycle | `layer3_gy_generated_public_lifecycle_audit.json` | `layer3_gy_generated_public_lifecycle_findings.md` |
| Core/IR/evidence/BERL/DDM/calibration/requirements | `layer3_gy_substrate_package_capability_inventory.json` | `layer3_gy_substrate_package_capability_findings.md` |
| Workflow-mode truth (which of the 3 modes the route runs; reuse/merge/build map) | `layer3_gy_workflow_mode_truth_audit.json` | `layer3_gy_workflow_mode_truth_findings.md` |
| Repo-wide capability coverage matrix (synthesis of all audits) | `layer3_gy_capability_coverage_matrix.json` | `layer3_gy_capability_coverage_matrix_findings.md` |

## Validation

Run all GY Task 0 validators:

```bash
python3 tools/quality/validation/check_layer3_gy_engine_census.py --json
python3 tools/quality/validation/check_layer3_gy_runtime_surface_audit.py --json
python3 tools/quality/validation/check_layer3_gy_catalog_fetch_audit.py --json
python3 tools/quality/validation/check_layer3_gy_connector_family_truth_audit.py --json
python3 tools/quality/validation/check_layer3_gy_source_contract_admissibility_audit.py --json
python3 tools/quality/validation/check_layer3_gy_data_requirement_compiler_audit.py --json
python3 tools/quality/validation/check_layer3_gy_lex_frontier_root_cause_audit.py --json
python3 tools/quality/validation/check_layer3_gy_foundry_breadth_audit.py --json
python3 tools/quality/validation/check_layer3_gy_agent_workflow_event_backing_audit.py --json
python3 tools/quality/validation/check_layer3_gy_generated_public_lifecycle_audit.py --json
python3 tools/quality/validation/check_layer3_gy_substrate_package_capability_inventory.py --json
python3 tools/quality/validation/check_layer3_gy_workflow_mode_truth_audit.py --json
python3 tools/quality/validation/check_layer3_gy_p0_coverage_audit.py --json
python3 tools/quality/validation/check_layer3_gy_p1_substrate_authority_audit.py --json
python3 tools/quality/validation/check_layer3_gy_p2_semantic_evidence_quality_audit.py --json
python3 tools/quality/validation/check_layer3_gy_capability_coverage_matrix.py --json
```

Run all matching repo-quality tests:

```bash
uv run pytest -q tests/repo_quality/tools/test_layer3_gy_*.py
```

## Authority Note

These files document what has and has not been proven. Do not treat the folder
itself as a generated/public surface registration, route execution proof, or
authority upgrade. That lifecycle question is explicitly tracked by
`layer3_gy_generated_public_lifecycle_audit.json`.
