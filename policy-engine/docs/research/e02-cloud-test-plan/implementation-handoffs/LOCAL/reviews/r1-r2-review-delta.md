# R1 oracle-companion delta review

Target: `22ca5401692d41f30c37eca060d132c6353dfa87` (tree `041632477ed3081da10ec8244b7be0577f645d51`, parent `4326679438f97c92be08773a33927463b0a67633`). Delta comparison is against the earlier reviewed `672f5514e2733a782b49a56425b67294928de78a`; I inspected those exact commit objects with `git show` and did not switch HEAD or edit product/test source. The candidate worktree is now ten commits ahead with unrelated active edits, so I did not execute tests on its current state.

## Finding resolved: collection dependency

The new `tests/unit/scientist/orchestration/engine/test_producer_model_scope_oracle.py` exists in the exact target, and its blob is `e4116da90128cb85c1736ed470fd08487b6c2f74`, matching the selected prepared-B helper object recorded in the prior receipt. The graph oracle's relative import at line 38 therefore resolves in this tree. The retained collection output lists 20 helper cases and 14 graph-oracle cases. This closes the missing-file collection defect in the pinned source.

## Alias-only witness is now a real identity divergence

The corrected `_AliasSplittingFieldGraph` validator updates `info.data["rows"][0]` in the existing list to `info.data["leaf"].model_copy(deep=True)` (`test_producer_validation_graph_oracle.py:92-99`). `_graph_state` establishes the initial shared-child premise with a real runtime list assignment and asserts `holder.leaf is holder.rows[0]` (`:113-126`). The validator's new child preserves the serialized fields but is a distinct object; it no longer replaces only the temporary `info.data` mapping slot as the prior witness did.

The paired sync/async `alias-only` cases assert refusal, unchanged public value paths and restored identity, and no producer effect artifact, completion callback, or cache publication (`:358-388`). The helper drives the actual sync/async workflow executors, FileSystemCAS effect writes, completion consumer, trace/cache reader, and reopened cache intent. This is behavioral evidence about the public mutation/consumer path, not a marker-only assertion.

## Evidence and scope

The retained collection output (`producer-graph-collection-green.log`) lists `20` and `14`; the full-oracle output (`producer-oracles-green.log`) has 34 progress marks reaching `[100%]`. The receipt records exit 0. However, the retained green output ends after the warning-docs footer and contains no final pytest summary or exit-status line; the two-case alias-repair output has the same omission. Keep the receipt's result labelled as reported by its author until a complete command/exit receipt is retained. Hashes: collection `bec85368a91beadae3dac506fcf9437d8cf8f0f7e2727897209e0b3f77e0d63a`; full output `87afeedc2ce63ef0a9fa27d38edbf64fcc3ea0bd93da25646947ccc2c29715ff`; alias repair `013435c57a0270a91d4d1915b967684087aafc8f5ad8fc3dce136e57d80248ad`.

The isolated matched-removal output shows four sync/async before/after model-validator cases failing `producer_calls == 0` with the observed count becoming `1` (`producer-graph-property-removal.log`, SHA-256 `3fbc03591c4206605722ac7a777c47e18634154d03e7b756614717791a6b5aeb`). This is a genuine behavioral signal for the model-level assignment-validator refusal predicate; it is not a matched removal of the alias-comparison predicate. The alias cases themselves do exercise a real equal-value identity split, and their expected refusal plus restored state makes them discriminating. Do not describe the four-case removal run as an alias-specific removal probe.

No new runtime finding was found in this test-only delta. The prior P40 bounded custom-leaf callback limitation, B61/B148 `verification_missing` statuses, and the original R1 aggregate receipt gap are unchanged by this review. No broad, numerical, or heavy tests were run.
