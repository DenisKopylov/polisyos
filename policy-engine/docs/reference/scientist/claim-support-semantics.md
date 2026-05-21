# Scientist Claim Support Semantics

Related references: [Claim Ledger](claim-ledger.md), [Benchmark authority](benchmark-authority.md), [Decision-grade compiler](decision-grade-compiler.md), [Continuous governance](continuous-governance.md).

Owner: `@scientist-owners`  
Backup owner: `@platform-owners`  
Source of truth: `src/polisyos/scientist/validation/claim_support.py` and `tests/unit/scientist/validation/test_claim_support.py`.

Phase 3.2 defines the semantic support layer used between structural grounding
and publication governance. Structural grounding answers whether a claim points
to selected Fabric, Foundry, and Lex refs. Claim support semantics answer what
kind of evidence predicate is required for the claim's meaning.

## Contract

Claim support has three separate outputs:

| Output | Meaning |
| --- | --- |
| `support_strength` | Evidence fit for the claim family: `unsupported`, `weak`, `supported`, or `strong`. |
| `publishability` | Release state from the Claim Ledger vocabulary: `internal_only`, `review_required`, `publishable`, or `blocked`. |
| `lifecycle_transition` | Append-only claim lifecycle action implied by support and counterevidence. |

Support strength never implies publication by itself. A claim can be
semantically supported but remain `internal_only` because the target readiness
level is only `research_artifact`, or it can be supported but
`review_required`/`blocked` because counterevidence is unresolved.

## Claim Family Rules

| Claim family | Required support predicates | Final grounding matrix mapping |
| --- | --- | --- |
| `factual` | `data_ref`, `source_attribution` | `empirical`; `claim_family_missing_required_grounding`, `data_claim_refs_not_selected` |
| `legal` | `norm_ref`, `legal_scope` | `normative`; `normative_claim_missing_applicable_norm`, `normative_claim_refs_not_applicable` |
| `causal` | `data_ref`, `method_ref`, `identification_strategy` | `causal`; `claim_family_missing_required_grounding`, `data_claim_refs_not_selected`, `method_claim_refs_not_selected` |
| `numerical` | `method_ref`, `method_output_ref`, `numeric_value` | `numerical`; `numeric_claim_unreadable`, `numeric_claim_missing_method_output`, `numeric_claim_mismatch`, `method_claim_refs_not_selected` |
| `forecast` | `method_ref`, `uncertainty_ref`, `forecast_horizon` | `forecast`; `claim_family_missing_required_grounding`, `method_claim_refs_not_selected` |
| `distributional` | `method_ref`, `subgroup_ref` | `distributional`; `claim_family_missing_required_grounding`, `method_claim_refs_not_selected` |
| `welfare` | `method_ref`, `welfare_metric` | `causal`; `claim_family_missing_required_grounding`, `method_claim_refs_not_selected` |
| `implementation` | `implementation_plan_ref`, `feasibility_ref` | `implementation`; `major_claim_missing_grounding_rationale`, `minor_claim_missing_grounding_rationale` |

Aliases are accepted for compatibility with existing final-policy artifacts:
`empirical` becomes `factual`, `normative` becomes `legal`, and `operational`
becomes `implementation`.

## Counterevidence

Counterevidence is explicit and action-bearing. Every counterevidence record
should include `counterevidence_id`, `action`, and `reason`.

| Action | Effect |
| --- | --- |
| `block` | Sets `publishability = blocked` and lifecycle transition `block_publication`. |
| `warn` | Keeps publication possible but emits a warning issue for operator/reviewer display. |
| `lower_readiness` | Caps readiness at `readiness_floor` or lowers it one step when no floor is supplied. |
| `require_review` | Sets `publishability = review_required` and lifecycle transition `require_review`. |

Blocking counterevidence dominates review, readiness-lowering, and warning
counterevidence. Review dominates readiness-lowering for publication state, but
the lowered readiness remains visible in the assessment.

## Grounding Matrix Relationship

The claim support layer does not replace the final policy grounding matrix. It
maps each claim family to the matrix family and issue codes that structural
grounding must still enforce:

1. Claim support checks semantic predicates required by family.
2. The policy grounding matrix verifies that referenced data, method, and norm
   ids are selected/applicable and that numerical values match Foundry outputs.
3. Claim Ledger readiness combines support, counterevidence, reviewer state, and
   publication audience.

This keeps Phase 3.2 deterministic: semantic support can fail or require review
without weakening the fail-closed structural grounding checks.

In serious runtime NL profiles (`research`, `governed`, and `production`), the
policy grounding matrix enables claim-support semantics for final policy claims.
Major claims with missing semantic predicates are escalated to fail-closed
grounding issues, while the raw claim-support assessment is retained on the
normalized claim for reviewer/debugging use.

## Validation

```bash
uv run pytest tests/unit/scientist/validation/test_claim_support.py -q
```
