# Citation Faithfulness

Related references: [Claim support semantics](claim-support-semantics.md), [Source quality calibration](source-quality-calibration.md), [Benchmark authority](benchmark-authority.md).

Owner: `@scientist-owners`  
Source of truth: `src/polisyos/scientist/validation/citation_faithfulness.py` and `tests/unit/scientist/validation/test_citation_faithfulness.py`.

Citation faithfulness is an offline deterministic quality gate for cited public
factual and legal claims. It intentionally avoids live LLM judging in CI and
uses only persisted claim refs, evidence snippets, structured support ids, and
scope metadata.

## Labels

Each cited ref is labeled as one of:

| Label | Meaning |
| --- | --- |
| `supports` | The evidence explicitly supports the claim and has no structured scope mismatch. |
| `partially_supports` | The source supports the claim only if an exception or caveat is preserved. |
| `scope_limited` | Legal scope, jurisdiction, date, or population metadata does not match the claim. |
| `contradicts` | The source explicitly or lexically contradicts the claim. |
| `irrelevant` | The source has insufficient overlap and no structured support link. |
| `fabricated` | The cited ref is not present in the evidence set. |
| `unverifiable` | The source is missing, blocked, unfetched, or has no usable snippet/support metadata. |

For public factual/legal claims, every non-`supports` label is blocking.
Missing citation refs are also blocking and set the per-claim status to `fail`.

## Runtime Contract

`build_policy_context_citation_faithfulness_report(...)` converts runtime Lex
norms and Fabric selected sources into the evidence shape consumed by
`build_citation_faithfulness_report(...)`. Serious runtime NL profiles persist
the resulting `policyos.scientist.citation_faithfulness.v1` artifact and fold
non-pass issues into the final policy grounding matrix.

## Residual Risk

The checker reports `live_llm_judging_enabled = false`, deterministic residual
risk, and false-pass limits. Passing the checker means refs are structurally
faithful to the available offline evidence; it does not prove full semantic
entailment or replace human/legal review for high-stakes publication.

## Verification

```bash
uv run pytest tests/unit/scientist/validation/test_citation_faithfulness.py -q
```
