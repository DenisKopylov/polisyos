# S3 D1d — N9 capture reissue for the governed credal input epoch

The current N9 contract refusal was an unclosed companion of this lane's S3 credal-reference epoch change. The existing canonical writer now admits precisely that governed input transition, emits fresh owner-produced records, and passes its normal current check. This repairs the S3 dependent capture; it does not supply a production promotion candidate or close PR1's remaining production-source work.

## Diagnosis and ownership

The unchanged current owner command returned `promotion_legacy_comparison_semantic_mismatch`, with the underlying reason `current_governing_projection_drift`. [The command record](promotion-comparison-command.json) retains its exact invocation, return code, duration, and complete streams. The process-local observer delegated to the unchanged comparator after recording [the complete actual live and frozen envelopes, ephemeral manifest, and owner projections](promotion-comparison-complete-observation.json).

[Independent recursive and iterative identity reconciliation](promotion-comparison-identity-reconciliation.json) walked every admitted entry and every leaf of both complete owner-produced semantic projections. The complete admitted identity set was:

| Actual admitted identity | Complete governing projection difference |
| --- | --- |
| `contract_lane_anytime_refusal` | `owner_projection.credal_reference.schema_version`: `policyos.runtime.grounding_credal_reference.v1` → `.v2` |
| `production_honest_shadow` | Equal; its credal reference is explicitly null |
| `non_promotable_contract_stamp` | `owner_projection.credal_reference.schema_version`: `policyos.runtime.grounding_credal_reference.v1` → `.v2` |

Absent fields, null, and empty containers are distinct in these walks. The evidence includes every compared identity and difference, not only totals. The bounded source readback found the production N9 owner, then-current validator, and old capture byte-identical to the slice base; the current credal owner had changed. Those explicit source comparisons are not a complete dependency census or an exact slice-base gate replay. An inherited-red attribution under P41 is therefore **not_established**. The measured governing delta belongs directly to S3 D1b's new credal input epoch.

The parent recorded and committed D1d before implementation, in the [execution plan](../../../plans/2026-09-08-gy-phase5-execution.md). The smallest owner-first repair extends `tools/quality/validation/check_layer3_gy_promotion_contract.py`, which already owns controlled canonical-capture reissue. The production promotion evaluator and generic comparison owner remain unchanged. No new acceptance semantics, producer, receipt class, or comparison exemption was introduced.

## Reissue predicate and preserved history

The new `_is_authorized_credal_input_epoch_reissue` requires both complete manifests to equal the actual fresh plan. Comparison rule/schema identities must agree, and the historical inner comparison hash is recomputed even when the older admission helper accepts an identical manifest. Every plan entry is parsed by its existing strict owner projector. Each non-null credal reference must change from exactly `.v1` to exactly `.v2`; a null-reference receipt must remain equal. After normalizing only that schema field in independent projected copies, each complete receipt projection and the complete projected envelope must agree. Any additional governing value, missing or novel identity, changed comparison epoch, or invalid binding refuses reissue. The branch returns the actual live envelope from owner admission and replay.

The preserved fixture `tests/repo_quality/tools/fixtures/layer3_gy_promotion_contract_credal_v1.json` is the prior canonical artifact's verbatim bytes, independently compared against the slice-base Git blob. Its SHA256 is `4825fd7adac74ef35a351d023dbd0069952b602b26b1c124c7795ef696f1a59a`. Historical receipts are read under their own epochs and never restamped.

The canonical writer emitted `architecture/policy_design_case/layer3_gy_promotion_contract.json`, SHA256 `3925c1e9f2474d6c950877f27860c3e8409b57ae2f37f088b40aebb4742b36e9`. [The complete artifact readback](d1d-artifact-readback.json), produced by [this command](d1d-artifact-readback-command.json), independently reconciles recursive and stack walks of all old/current JSON field identities and retains every value difference. The schema/shape identity difference is empty. Every actual admitted receipt remains `promoted=False` and `consumer_promotable=False`; receipt schema remains `n9_promotion.v6`. The nested credal input uses the already governed `.v2`. No N9 obligation or evidence-union epoch is changed by this companion.

## Executed falsifiers and verification

Every linked command record contains the exact argument vector or shell-rendered command, working directory, lane-venv/PYTHONPATH prefix, actual subprocess return code, wall time, and complete stdout/stderr. The recorder executes one gate per invocation; it does not infer success from an `echo`. Package entry points use `-m`, and child processes receive the lane venv first in `PATH`.

| Gate or falsifier | Actual result | Evidence |
| --- | --- | --- |
| Red-first actual canonical writer against the preserved old capture, before repair | RC1, 82.744s; exact governing-projection mismatch | [red](d1d-reissue-red.json) |
| Initial writer/check positive and initial refusal matrix | RC0, 316.852s; earlier test scope, superseded by the expanded matrix | [initial green](d1d-reissue-green.json) |
| Expanded focused writer/refusal matrix and the prior v3→v6 transition control | RC0, 292.919s; behavioral receipt, initially lacking executed identity output | [expanded execution](d1d-reissue-final-tests.json) |
| Remove the new transition predicate while keeping the writer, artifact, and assertions | Expected RC1, 166.212s; the unchanged happy-path test fails with the actual governing mismatch | [transition removal](d1d-transition-removal.json) |
| Replace the complete governing comparison with unconditional admission while keeping markers | Expected RC1, 166.132s; the unchanged extra-governing-value refusal test fails because the owner no longer raises | [comparison removal](d1d-governing-comparison-removal.json) |
| Actual canonical owner `--write --output-format json` | RC0, 83.787s | [write](d1d-canonical-write.json) |
| Actual canonical owner `--check --output-format json` | RC0, 120.637s; status `pass`, issues empty | [check](d1d-canonical-check.json) |
| Actual canonical owner `--corrupt-field-drift-check --output-format json` | Expected RC1, 63.478s; corrupt-field drift detected and typed receipt refusal | [corruption](d1d-canonical-corruption.json) |
| Scoped production/test/diagnostic Ruff | RC0 | [source and tests](d1d-final-ruff-v2.json), [removal harness](d1d-removal-harness-ruff.json), [readback harness](d1d-readback-harness-ruff-v2.json), [command recorder](d1d-command-recorder-ruff.json) |

The corruption mode mutates an in-memory copy; it does not rewrite the canonical artifact. The removal probes patch only the process-local predicate, not files on disk. All normal test writes target isolated output files and confidence-ledger scratch. The negative matrix includes wrong credal epoch, governing change inside a receipt, governing change outside the receipts, changed comparison epoch, invalid outer hash, fake inner comparison hash with a valid outer hash, and absent/null/empty/duplicate/novel/scalar manifests.

The expanded `-q` execution preserved full output but no JUnit identities. It is not evidence of an independently reconciled execution denominator by itself. The parent authorized an exact replay of the same focused nodes with JUnit solely to close that verification limitation. [The exact replay](d1d-identity-execution.json) returned RC0 in 320.487s and emitted [JUnit](d1d-identity-execution.xml). [Independent complete collection-versus-execution reconciliation](d1d-test-identities.json) returned RC0 in 41.947s: the complete targeted Python collection and complete executed JUnit identity sets agree at 15/15; missing, unexpected, ambiguous, duplicate, and nonpassing cases are empty. These identities include every parameter case listed above and the actual writer/check positive. This supersedes the earlier execution-identity limitation without broadening the test scope.

## Pattern and task disposition

[The independent frozen-delta review](../shared/independent-d1d-review.md) found no blocking code issue. P27 is satisfied by extending the existing capture owner. P29 is measured through the real writer/check and removal probes. P37's reissue predicate is `recomputed`, using fresh owner admission and complete projections; the persisted manifest alone is insufficient. P38 is closed by comparing the allowed governing change itself, including values outside admitted receipts. Under P40 this is the required companion to the already identified S3 input-epoch change, not a new promotion-authority repair class.

This packet is verification-only sequence coverage. Its fixtures and owner-produced refusals are never promoted to the canonical production-candidate denominator. The complete-evidence production row, law-correspondence witness, and authority-grade scientific inputs retain their separately measured standings in the lane journals. No incidental new ownerless finding was introduced: this change and its original red belong to **GY-S3 / D1b–D1d**, under governed dependent-epoch replay and P07/P29. Full lane guardrails, final generated API freshness, branch attachment, coherent commits, and branch-blob delivery readback remain with the parent.
