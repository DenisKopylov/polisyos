# Decision Artifact Quality

Related references: [Decision-grade compiler](decision-grade-compiler.md),
[Claim support semantics](claim-support-semantics.md),
[Citation faithfulness](citation-faithfulness.md), and
[Source quality calibration](source-quality-calibration.md).

Owner: `@scientist-owners`  
Backup owner: `@platform-owners`  
Source of truth:
`src/polisyos/scientist/artifacts/decision_compiler.py`,
`src/polisyos/scientist/validation/decision_artifact_quality.py`,
`tests/unit/scientist/artifacts/test_decision_compiler.py`, and
`tests/unit/scientist/validation/test_decision_artifact_quality.py`.

Phase 5.9 adds the final public decision-artifact compiler and its independent
quality report. The compiler turns final claims and existing quality refs into a
public artifact. The quality report validates that the artifact is complete,
calibrated, citation-preserving, and safe to export.

## Compiler Contract

`compile_public_decision_artifact()` emits
`policyos.scientist.decision_artifact.v1` with:

| Field | Meaning |
| --- | --- |
| `recommendations` | Major and minor final recommendation claims with citation refs, support refs, and decision sections. |
| `supporting_claims` | Non-recommendation final claims that remain visible in the public output. |
| `decision_context` | Grounding, quality scorecard, conflict, approval, and performance status. |
| `performance_warnings` | Scorecard and caller-supplied performance warnings, deduplicated for public display. |
| `assurance_refs` and `refs` | Available Wave 1-5 report refs for downstream aggregation. |
| `public_export_constraints` | Machine-readable statement that public redaction rules were applied. |

Major recommendations must carry the following sections:
`support_summary`, `uncertainty`, `policy_tradeoffs`,
`distributional_impact`, `implementation_feasibility`,
`budget_implication`, `stakeholder_impact`, `implementation_risks`,
`residual_uncertainty`, `monitoring_plan`, and
`withdrawal_reissue_triggers`.

The compiler preserves `citation_refs` for visible claims and recursively drops
known public-forbidden keys such as hidden benchmark answers, credentials,
reviewer-private notes, raw sensitive data, prompts, and raw transcripts.

## Quality Report Contract

`build_decision_artifact_quality_report()` emits
`policyos.scientist.decision_artifact_quality.v1` with a deterministic
`decision_artifact_quality_report_ref`.

The report is offline and deterministic. It uses the compiled artifact plus
available refs from earlier waves; it does not call live LLM judges, external
fetchers, or benchmark services. Wave 6 can join this report ref with other Wave
5 report refs in the final aggregate gate.

The validator fails serious profiles (`research`, `governed`, `production`,
`serious`, and `high_stakes`) when:

| Check | Failure code |
| --- | --- |
| Required major-recommendation sections are missing | `major_recommendation_missing_required_section` |
| Uncertainty language denies residual uncertainty | `uncertainty_language_overconfident` |
| Uncertainty language is present but uncalibrated | `uncertainty_language_not_qualified` |
| Causal, legal, empirical, model, benchmark, or compliance certainty is overstated | `overstated_<dimension>_certainty` |
| Public output contains forbidden private/sensitive data | `public_export_contains_forbidden_data` |
| Public output drops final-claim citations | `citation_refs_dropped` |
| Scorecard, conflict, or approval context is not release-ready | `decision_artifact_*` context failures |

For non-serious profiles, missing sections and approval readiness are warnings;
public-secret leaks, dropped citations, and certainty overstatements remain
failures.

## Public Export Rules

Public exports must preserve citations and omit:

- hidden benchmark answers and hidden-eval material;
- credentials, API keys, bearer tokens, passwords, and secrets;
- reviewer-private notes or private reviewer packets;
- raw sensitive records or raw transcripts;
- system/developer prompts.

Reviewer, expert, and machine packets may use richer internal artifacts, but the
public decision artifact must remain safe to publish without exposing these
fields.

## Validation

```bash
uv run pytest tests/unit/scientist/validation/test_decision_artifact_quality.py tests/unit/scientist/artifacts/test_decision_compiler.py -q
```
