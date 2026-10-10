# Final author-proposal report readiness

**Status:** source-only adapter is ready for root's frozen wave inputs. No final report or candidate outcome was generated here. This is a custom author-proposal report, not the registered v4 evaluator or G adjudication.

The assembler is [`LOCAL/raw/build_final_author_proposal_report.py`](../raw/build_final_author_proposal_report.py). Its current SHA-256 is recorded in the handoff message after static readback. The only verification performed for this update is static Python AST parsing; the assembler was not executed. It does not invoke Git, run the registered v2 validator, or change source data.

## Denominator and preserved state

The assembler checks the exact `(finding ID, coverage JSON pointer, criterion SHA-256)` multiset across the canonical coverage, proposal ledger, and compact preparation draft: 127 bundles, 282 IDs, and 291 occurrences. It also verifies 26 task definitions and 319 task assignments. Repeated IDs remain separate occurrence rows.

The source-author history remains separate: 198 source-author `closed` IDs map to 202 occurrences. Current technical proposal counts remain 194 `limited`, 35 `held`, and 62 `open`. The B198 historical `closed`, Appendix C `closed_bounded`, `closure_now=not_adjudicated`, and source-author `closed` decision are checked and preserved. The report always emits `formal_closure_ids: []`.

## Status and evidence boundaries

Each row keeps its exact criterion pointer/hash, source path/commit/blob/span, original criterion boundary, technical property/proxy boundary, source-qualified author references, task routes, P40 classification, and next check. Task routes remain navigation only.

`actual_execution` is always `UNRUN` with no admitted attempts. The assembler does not call the registered v2 validator and does not create registered v4 evaluations. A v2-shaped handoff packet supplied with `--author-handoff-packet` (the legacy `--external-receipt` spelling is accepted as an alias) can only create a sibling `unadmitted_author_command_attempts` record when its exact occurrence, command, capture, output hashes, and TASKS route structurally match. Those records are explicitly `UNADMITTED_AUTHOR_COMMAND_ATTEMPT_ONLY`; they are not an execution admission, candidate outcome, closure, or G decision.

Route-matched capture results are retained separately in `navigation_only_command_observations`, including the distinction between a consistent command observation and an unestablished one. Command outcomes require complete context and output digests. A timeout is classified as `ERROR` even if JUnit reports passing testcases. PASS requires actual JUnit testcase behavior, a zero process exit, matching wrapper and pytest result statuses, a passed module-origin assertion, and a complete command-output inventory. FAIL and ERROR require a matching real JUnit testcase failure/error plus the corresponding process/wrapper status. A nonzero exit without real JUnit failure/error evidence, malformed or missing context, launch errors, unclassifiable JUnit, and aggregate-only JUnit counts remain unestablished. These status observations still do not change `actual_execution` from `UNRUN`.

Optional `--author-capture` inputs accept `policyos.e02.local_slice_author_capture.v1` only as `UNADMITTED_AUTHOR_EVIDENCE`. Their exact occurrence bindings and source references remain visible, but cannot create admitted attempts, evaluations, or closures. The current local packets are:

- `LOCAL/native-copy-complete-source.json` @ `c197bfe491c970a2761c97dcc62a0f502c3826b24b8cff18d0c315fa11972df1` (no occurrence bindings).
- `LOCAL/v6-owned-lifecycle-readers.json` @ `716951ce874018c445748285a8337d9c642a50dc8ba0cdc64c1ad11b4cb604e7` (one exact occurrence binding).
- `LOCAL/v3-current-owned-source.json` @ `474f4e3d2743b32c418d1156f898e44d754bab11a2b9a8d299e2868add721ac9` (six exact occurrence bindings).

All packet paths are explicit inputs; there is no receipt-directory scan. Author-provided admission text is preserved only as data and never trusted as proof.

## Invocation after freeze

Root supplies the final commit/tree and source-census reference. The output directory must already exist, be absolute and non-symlinked, and be owned by the caller. The output path must be a new file inside it. The assembler does not create directories or overwrite files.

```sh
python3 -B policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/build_final_author_proposal_report.py \
  --freeze-commit <root-supplied-commit> \
  --freeze-tree <root-supplied-tree> \
  --source-census-ref '<root-supplied-path-or-pointer>@<root-supplied-sha256>' \
  --primary-capture <absolute-final-capture-run-or-directory> \
  --supplement-capture <absolute-supplement-capture-run-or-directory> \
  --author-handoff-packet <absolute-v2-shaped-author-packet.json> \
  --author-capture policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/native-copy-complete-source.json \
  --author-capture policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/v6-owned-lifecycle-readers.json \
  --author-capture policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/v3-current-owned-source.json \
  --owned-output-root <absolute-existing-parent-owned-ignored-directory> \
  --output <absolute-new-report.json>
```

Repeat `--supplement-capture`, `--author-handoff-packet`, and `--author-capture` for additional explicit inputs. A handoff packet is optional and never required for the full 291-row report. Task PASS, route PASS, packet status, or source-author history is never upgraded to a candidate occurrence evaluation.

## Limits

The assembler checks report-input consistency and retains source references, but it does not recompute Git ancestry/source census acceptance, validate the registered v2 admission mechanism, or produce a registered v4 evaluation. Per-row `actual_execution.evaluation_state` remains `NOT_ADJUDICATED_BY_ASSEMBLER`; any later adjudication must independently compare admitted occurrence-specific evidence to the full original property, consumer, discriminator, and negative controls. G status remains unadjudicated; source-author history is unchanged.
