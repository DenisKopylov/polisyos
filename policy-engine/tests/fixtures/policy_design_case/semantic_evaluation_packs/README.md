# W5.B Semantic Evaluation Packs

Owner: `team-evaluation`
Consumer: `tests/repo_quality/tools/test_policy_design_case_w5b_semantic_evaluation_packs.py`
Phase: `PolicyOS Universal Policy Design Case Implementation Plan` W5.B

This pack extends the W1.B semantic false-pass gold cards into a split-aware
benchmark. It keeps public/hidden/rotating fixtures separate so structural
passes cannot be overfit to the first public examples.

Pattern pass: P10 is the primary guard because every fixture is structurally
complete but semantically failing. P14 is covered by effective-independence
raw-count collapse. P15 is covered by candidate-to-authority laundering and
participation/speculation boundaries. P05 and P13 appear as supporting guards
for recourse and tuned-threshold cases.

Public fixtures may be documented in detail:

| Public fixture | Failure mode | Expected semantic failure |
| --- | --- | --- |
| `w5b_participation_prevalence_negative_semantic_fail` | `participation_prevalence_negative` | `semantic_participation_prevalence_negative` |
| `w5b_projection_laundering_semantic_fail` | `projection_laundering` | `semantic_projection_laundering` |
| `w5b_raw_count_inflation_semantic_fail` | `raw_count_inflation` | `semantic_raw_count_inflation` |

Hidden and rotating splits are aggregate-only in public documentation. Their
exact fixture ids are internal to the manifest and repo-quality tests; public
exports may disclose only counts, status, failure-mode coverage, and whether a
split is stale or passing.

Acceptance signal:

- manifest cites `E22`, `C30`, `P10`, `P14`, and `P15`;
- each fixture preserves `structural_pass_claimed=true` and a passing
  structural verdict;
- each fixture deterministically emits the declared semantic failure code;
- public, hidden, and rotating split counts are non-zero;
- hidden and rotating fixture details remain aggregate-only;
- required failure modes include participation prevalence negatives,
  projection laundering, unreachable recourse pointers, tuned-threshold
  hardcoding, raw-count inflation, LLM speculation laundering, and unsupported
  claims.
