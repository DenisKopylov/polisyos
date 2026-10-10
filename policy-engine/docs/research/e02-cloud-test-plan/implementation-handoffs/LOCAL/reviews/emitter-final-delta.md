# Independent emitter final-delta review

## Scope and P40 bucket

Reviewed the working-tree bytes of `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/emit_proposals.py`, SHA-256 `c2c79ffd02a25b8d070f92fe2bda5ca242f6058e022416f1cb5ae4228a762d8a`. The candidate branch was attached at HEAD `077a572ff5880b3f50a85d3e3db6a232d277659a`, tree `2895b6c7597215b714275cb4ba83a504724dc89c`; this HEAD does not yet include the reviewed emitter bytes. I did not change source, tests, configuration, or Git state.

**P40: SAME_CLASS_DEEPER.** This is the same criterion-to-decision source-binding class as the earlier occurrence-cardinality escape, at a deeper boundary: decision rows must remain bound to the exact criterion SHA while passing through the real typed-receipt reader. The current mapper preserves a list for each exact `(finding_id, occurrence_pointer, criterion_sha256)`, rejects exact duplicate rows and unmapped covers, and the receipt reader validates each selected row. No new escape appeared in the exercised source-bound path.

## Independent behavior evidence

The current emitter passes `occurrence_sha256` unchanged through `validate_explicit_evaluation()` → `validate_execution_context()` → `validate_typed_slice_receipt()`. The receipt requires the exact finding, pointer, and SHA at `require_handoff_occurrence()`; it then selects the decision list by that same triple and passes the same SHA to `validate_decision_research_rows()`. Each decision source ref is resolved, content-bound, ancestry-checked, JSON-pointer-resolved, and role-checked before the evaluation is returned.

I exercised `validate_explicit_evaluation()` through those actual validators with these outcomes:

| Probe | Result |
| --- | --- |
| Issuer-only `bounded_no_alternative` receipt row with `bounded_no_alternative_basis` source role | Accepted as `OPEN_ACTION` / held; one attempt preserved; no formal-closure result |
| Two different alternatives plus a prototype, all for the same B01 occurrence | Accepted; both option IDs and all three decision rows were retained and validated |
| Foreign criterion SHA (`000…000`) consistently supplied by the evaluation refs while the receipt carries the pinned B01 SHA | Rejected by the typed reader: “does not bind the exact evaluated original criterion occurrence” |
| Prototype row whose embedded source role is changed to `decision_alternative` | Rejected at decision row 2: prototype source role invalid |
| External decision evidence index changed to `actual_consumer` | Rejected by the execution-context role gate before the evaluation returns |

The positive B01 SHA came from the actual pinned `coverage.json` row: `515ee67aec37de92c27b20c9ddd90cc61c95c41608b1daf4eddc88d640c78759`, pointer `coverage.json#/findings/0/criterion_refs/0`. Decision source refs used the real HEAD coverage blob and passed their real Git blob, content SHA, ancestry, and JSON-pointer checks.

**Receipt boundary:** HEAD has no committed `LOCAL/issuer-proof.json` typed-v2 receipt (`git cat-file -e HEAD:<path>` reports it absent). To exercise the reader without writing a source or Git object, the probe supplied synthetic receipt bytes at exactly two object-read calls: `git_bytes("show", "HEAD:<synthetic receipt path>")` and the matching `git_text("rev-parse", "HEAD:<synthetic receipt path>")`. All semantic validators, all other Git reads, source blob checks, and ancestry checks were real and unpatched. The receipt payload was held in memory. Therefore this is a behavioral fixture for the current validator implementation, **not** proof against the actual committed receipt or a frozen candidate source.

Full captured probe output: `LOCAL/raw/emitter-final-delta-fixture-probe.json`, SHA-256 `c036d534daddd1f2bb5e923cc732bca3c9e089d51ff04f0c081b66e139081f9b`. The active ignore rule for this raw path is `policy-engine/.gitignore:151` (`docs/research/**/raw/`).

## Verification caveat

The emitter's embedded self-check still replaces `validate_typed_slice_receipt` with `issuer_only_receipt_probe` around its issuer-only evaluation (lines 5363–5394). Its wrong-hash and wrong-role probes therefore do not independently exercise the real typed-receipt loader. The direct fixture run above does exercise the actual loader, but it is review evidence, not a persistent regression test. No separate test for `validate_typed_slice_receipt` was found under the product tests/tools paths searched.

## Checks and limits

- Exact module import origin was the candidate's `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/emit_proposals.py`; bytecode writing was disabled.
- Python 3.14.3 AST parse: pass.
- `python3 -m ruff check --output-format concise docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/emit_proposals.py`: pass, “All checks passed!”
- `git diff --check -- docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/emit_proposals.py`: pass, no output.
- The generator and self-check were not run; no native/heavy task was run.

**Independent assessment:** The exact-hash and decision-role behavior in the reviewed working-tree code passed the synthetic un-stubbed receipt-path probes. The result remains partial until the emitter source is committed and the same route is rerun against the actual receipt bytes loaded via real `git show` from the source-bound candidate. The self-check stub remains a coverage limitation. This assessment does not adjudicate or close any G finding, and claims no formal closure.
