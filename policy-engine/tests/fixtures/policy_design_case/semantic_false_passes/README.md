# Policy Design Case Semantic False-Pass Fixtures

Owner: `team-runtime-quality`
Consumer: `tests/repo_quality/tools/test_policy_design_case_semantic_fixtures.py`
Phase: `PolicyOS Universal Policy Design Case Implementation Plan` W1.B

These W1.B fixtures are semantic gold cards for P10/P15 failure modes. They
intentionally preserve a passing structural verdict while encoding a
content-level reason the case must still fail. The evaluator derives the
failure code from the `payload`; `expected_failure_code` metadata alone is not
authority.

| Fixture | Failure mode | Primary closure | Expected semantic failure |
| --- | --- | --- | --- |
| `projection_laundering_semantic_fail` | `projection_laundering` | P10, P15, P05 | `semantic_projection_laundering` |
| `participation_laundering_semantic_fail` | `participation_laundering` | P10, P15, P05 | `semantic_participation_laundering` |
| `raw_count_inflation_semantic_fail` | `raw_count_inflation` | P10, P14 | `semantic_raw_count_inflation` |
| `method_mismatch_semantic_fail` | `method_mismatch` | P10 | `semantic_method_mismatch` |
| `stale_evidence_semantic_fail` | `stale_evidence` | P10, P08 | `semantic_stale_evidence` |
| `llm_speculation_semantic_fail` | `llm_speculation` | P10, P15 | `semantic_llm_speculation_laundering` |
| `unsupported_claim_semantic_fail` | `unsupported_claim` | P10 | `semantic_unsupported_claim` |

The pack is deliberately small. A valid fixture must show:

- `structural_pass_claimed=true`;
- a passing `structural_verdict`;
- `expected_status=semantic_fail`;
- at least one semantic probe;
- `E1`, `C30`, and `P10` references;
- a payload that deterministically exhibits the declared semantic failure.
