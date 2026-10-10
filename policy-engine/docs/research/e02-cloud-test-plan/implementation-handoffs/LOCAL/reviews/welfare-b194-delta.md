# Independent B194 delta review

Reviewed the shared candidate at `HEAD 68b8ac5c32e03309ad888cb3799ad1c574fbdca7` when the review began. The source hashes below identify the exact reviewed bytes. This is a scoped review of the B194 retry/classification delta, not a whole-candidate approval.

## Decision and P40 bucket

The reopened cycle escape is closed for the reviewed property. P40 classification: **SAME_CLASS_DEEPER**. The earlier classifier treated repeated exception identities as already visited, so a self-cause domain or transient error could be accepted as a complete draw-local signal. The author widened the bounded graph traversal to distinguish active ancestors (a true cycle) from previously visited shared DAG nodes. This resolves the class generically; it does not add per-fixture patches. No further instance repair is warranted for this class. The bounded traversal still fails closed when it reaches its node or edge cap.

The original criterion is B194 in `docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md:4792-4800` (`sha256 9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5`). It identifies the conditional-distribution bias caused by dropping failed inputs, calls for bounded retry of the same transient draw, and requires global access/contract errors not to be counted as noisy draw failures. The implementation keeps that boundary: it does not make arbitrary evaluator exceptions retryable.

## Source result

`propagate_welfare.py` now traverses directed `__cause__`, `__context__`, and `BaseExceptionGroup` links with separate `active` and `visited` sets, a 64-node limit, and a 256-edge limit (`:348-405`). A back-edge makes the scope `unknown`; a shared node reached by two paths does not. Global access/validation/fatal evidence found in the traversed graph keeps global precedence. A truncated graph is also unknown, never domain-limited or retryable.

The draw loop samples once and calls the evaluator with the same `draw_params` on retry. It records the sampled-input digest and each attempt, with two attempts maximum (`:2140-2280`). Only a top-level `PolicyOSError(TRANSIENT)` with a complete acyclic cause graph retries. A top-level `WelfareSampleDomainError` terminates that draw as `sample_domain_inapplicable`, marked `consumer_asserted`; arbitrary and cyclic domain/transient-looking errors fail the node. Permission errors, Pydantic validation errors, and typed fatal/validation PolicyOS errors fail the node even when wrapped. Domain failure leaves missing mass visible, withholds the Monte Carlo interval, and, when any draw succeeds, retains only a successful-draw conditional summary (`:2324-2430`).

The fresh-CAS regression reaches the real node and the existing `_build_welfare_section` consumer. It verifies terminal rows for every requested draw, one transient retry on the same sample digest, exhaustion without another sample, failed sampling without replacement, the default GE condition-number domain, and the persisted partial bundle’s nominal point/conditional-mean warning. The consumer output retains `status=partial`, the nominal input point, no interval, and the warning; the evaluator’s domain predicate remains an assertion rather than an independently verified scientific fact.

## Independent probes and verification

Using the candidate `.venv` with `PYTHONPATH=src:.`, the loaded module path was the candidate checkout’s `src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py`. Direct probes returned:

| Probe | Classification |
| --- | --- |
| Self-caused `WelfareSampleDomainError` | `unknown`, cycle detected |
| Self-caused `PolicyOSError(TRANSIENT)` | `unknown`, cycle detected |
| Two-node cause/context cycle rooted at transient | `unknown`, cycle detected |
| Self-linked `ExceptionGroup` | `unknown`, cycle detected |
| Shared exception reachable through both cause and context | `transient`, complete DAG |
| Cyclic domain error with a visible `PermissionError` | `global`, preserving global precedence |

The focused persisted-CAS selector passed **17 tests in 9.44 seconds**, with two upstream Torch/Python 3.14 deprecation warnings. The full output is `LOCAL/reviews/raw/welfare-b194-independent-focused.log` (`sha256 ea7e42043fe412f164f9c5bf6cce253df3f958bdad1e0be17cca5bab4957fd72`). Direct probe output is `LOCAL/reviews/raw/welfare-b194-cycle-probes.log` (`sha256 3556fd122ac02060c39724655ace09645e25db969fad2ca8e10dbaa01b2a2dc6`). The author’s pre-fix cause-cycle test is retained at `LOCAL/raw/welfare-b194-cause-cycle-red.log` (`sha256 9223cca05e352efb965e68e0c46b8173fc0c70c54ab8c995706e8536cca582bc`); it showed the expected node refusal returning `ok` for the domain-cycle case. The author’s fixed selector also passed 17 tests (`LOCAL/raw/welfare-b194-focused-cycle-final.log`, `sha256 ea7e42043fe412f164f9c5bf6cce253df3f958bdad1e0be17cca5bab4957fd72`).

Ruff check passed independently for the two owned Python paths (`LOCAL/reviews/raw/welfare-b194-ruff-independent.log`, `sha256 82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`). `ruff format --check` reports only formatting differences on added lines in those paths (`LOCAL/reviews/raw/welfare-b194-format-independent.log`, `sha256 ee0d27abe8f37b467134ec27bab0f4655ec494cd376bc21d6f367758cd8a5720`); this is cosmetic, not a semantic blocker.

## Compatibility and boundary

New Monte Carlo payloads use schema `1.2` without a calibration source and `2.2` with one. Delta and limited-report branches remain at `1.0`/`2.0`. A Python-file search over `src/polisyos` and `tests` (5,585 files) found no version-specific in-tree reader for `foundry.welfare_propagation_report`; the nearby strict `PropagationReport` reader in `ir/analytics/uncertainty.py` handles a different artifact kind. The reviewed 17-test run exercises the uncalibrated `1.2` report and generic fresh-CAS decoding. I did not run a calibration fit, so the `2.2` branch is source-checked but not independently executed here. Compatibility of any external or private version-pinned reader for historical `1.1`/`2.1` reports is not established by this repository scan.

The proven chain is the existing internal producer → CAS report/sample/bundle → fresh CAS load → decision-packet Welfare consumer. A standalone public API/dashboard for `WelfarePropagationReport` remains `surface_out_of_scope`. Scientific validation of an evaluator’s declared sample-domain predicate is also outside this change; it is explicitly `consumer_asserted`, so it cannot establish an authority-grade domain boundary.

## Reviewed bytes

| Path | SHA-256 |
| --- | --- |
| `src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py` | `ac3de486fc4714499eab669fb66c77782cda2e4f1318f921b60399ccc79e4d09` |
| `tests/unit/scientist/nodes/builtins/simulate/test_propagate_welfare.py` | `5f2f0f511f71b61bc37a759aaa8b18b3dd71bb91a8e521bd078c357f3dee3e74` |
| `src/polisyos/scientist/nodes/README.md` | `f022a368500464ab37e37784348d702cd6d93c0af521e6510da3e0626ef2969b` |
| `release-fragments/unreleased/2026-10-09-e02-e11-welfare-monte-carlo-truthfulness.toml` | `d7c12cbff3af34dca3625746c4456782a0c806ce16515a3c28d336aaca99f6bd` |
