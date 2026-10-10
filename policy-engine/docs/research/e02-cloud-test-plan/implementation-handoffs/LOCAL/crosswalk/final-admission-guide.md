# Final occurrence admission guide

This guide describes the handoff from the complete original finding set to the final candidate wave. It does not adjudicate any occurrence. The historical report checkpoint inspected when this guide was drafted was `077a572ff5880b3f50a85d3e3db6a232d277659a` (tree `2895b6c7597215b714275cb4ba83a504724dc89c`); that checkpoint is neither the original entry nor the final source freeze, and its zero tracked `policyos.e02.local_slice_handoff.v2` count is historical. Working-tree owner reports are useful review inputs; until committed and read back from Git they are not immutable evidence. The six A–F assessment JSON files describe candidate review pending the final wave, not current-source passes.

The source denominator is the pinned original `coverage.json` at `93d6aa62a8d236667fdf322a5fc17962523b185e`: **282 finding IDs and 291 criterion occurrences**. That is one JSON source file, walked across every `findings[]` row and every `criterion_refs[]` element. Repeated occurrences remain separate by their own pointer and exact source-span SHA-256. The current generated proposal ledger reconciles to that set and presently shows 282 IDs, 291 occurrences, all 291 `UNRUN`, no occurrence dispositions, and `formal_closure_ids: []`. B198’s historical ledger value remains `closed`, while `closure_now` is `not_adjudicated`; those are separate facts and neither is a new candidate result.

## Evidence layers

Keep three artifacts separate:

1. **Original-property crosswalk.** The pinned coverage row and the A–F owner assessments identify the exact original property, source span, historical decision, source-author proposal, current consumer boundary, candidate delta, and next discriminator. This layer selects the test; it does not prove it.
2. **Typed slice handoff v2.** A committed `LOCAL/<slice>.json` binds the selected occurrences, exact slice base, final candidate source, path footprint, selected inputs, backend profile, commands and output references, producer/artifact/bridge/consumer chain, controls, limitations, and occurrence-specific decision choices. Its `formal_closure_ids` must be empty.
3. **Occurrence evaluation v4.** After the source freeze and actual deciding commands, an explicit update keyed by `(occurrence_pointer, sha256)` records the per-occurrence result, evidence indexes, attempts, disposition, P40 classification, and next check. The canonical emitter consumes this update and remains the authority for its source, report, and output validation. A task status, test count, historical closure, or source-author `closed` proposal never fills this layer.

The order matters: source freeze → report-only receipt commit(s) → final command wave and required local read-only closeout → explicit per-occurrence evaluation input → canonical emitter check. Do not put a future receipt commit SHA in the source-freeze packet that precedes it. The evaluation’s candidate SHA/tree names the frozen source commit; its evidence refs name real descendant Git commits that contain the typed handoffs and deciding artifacts.

## Original criterion binding from the A–F reviews

The six assessment files are the complete A–F JSON packet set at `LOCAL/reviews/`; their file-type denominator is six JSON files. Their row counts reproduce the canonical owner partition: A 34 IDs/35 occurrences, B 60/60, C 54/59, D 45/46, E 54/55, F 35/36. This is a partition of the original 282/291 denominator, not an extra set to add to it.

| Owner | Assessment row binding | Property/consumer boundary and next check |
|---|---|---|
| A | `full-id-A-assessment.json#/rows[]`: `finding_id`, `original_criterion_source.occurrence_pointer`, `criterion_span_sha256`. | Read `read_only_candidate_assessment.original_property`, `property_vs_proxy`, `candidate_source_refs`, `minimum_genuine_input`, and `next_runnable_check`. Preserve each A row’s source-owner/history status separately. |
| B | `full-id-B-assessment.json#/occurrences[]`: `finding_id`, `original_criterion.occurrence_pointer`, `original_criterion.sha256`. | The candidate-specific boundary is under `b2_candidate` and its `specific_assessment_pointer`; original text remains the pinned B_r19 source span. Manual and source-author proposals are not candidate evidence or G. |
| C | `full-id-C-assessment.json#/occurrences[]`: `finding_id`, `original_criterion.source_document.coverage_occurrence_pointer`, `sha256_exact_line_span`. | Keep `original_criterion.candidate_property_boundary`, `minimal_next_check`, and `pinned_b2_candidate_assessment` together. C5 recommendations/current-root verdicts remain distinct from the candidate and formal G. |
| D | `full-id-D-assessment.json#/rows[]`: `finding_id`, `pointers_and_hashes.coverage_occurrence_pointer`, `pointers_and_hashes.original_criterion_source.sha256_exact_line_span`. | Preserve `property.original_acceptance_scope_note`; `D45_runtime_property` is a distinct predicate and cannot narrow that original criterion. Bind `property.actual_consumer`, `negative_oracle_or_discriminator`, `minimal_input`, `next_check`, and `G_choice`. |
| E | `full-id-E-assessment.json#/occurrences[]`: `finding_id`, `original_occurrence_pointer`, `original_criterion_source.sha256_exact_source_span`. | Use `candidate_b2cd_assessment.exact_next_check` to select the fresh check. Historical E rows and their old wave selectors do not carry forward as a current-candidate pass. E’s current assessment states all 55 occurrences are UNRUN and G acceptance is zero. |
| F | `full-id-F-assessment.json#/findings[]/original_occurrences[]`: parent `id`, each `coverage_pointer`, and each `source_span.block_sha256`. | Use `property_ref_only` and the exact F per-ID carrier pointers to identify the property; use `candidate_b2_source` only for its explicit source-path scope. Current F semantics remain UNRUN and G is unissued. |

The ignored prototype `LOCAL/raw/crosswalk/final_admission_factory.py` performs a read-only reconciliation of these six row maps with the pinned original coverage and current ledger. It prints the assessment path denominator and JSON file-type denominator, checks multiset equality (so repeated occurrences cannot be collapsed), reports tracked v2 handoffs at a requested Git checkpoint, and emits no candidate outcomes. It intentionally does not write the proposal ledger or a v4 evaluation file.

## Minimum useful typed v2 handoff

The current emitter registers a direct-child receipt path matching `LOCAL/<lowercase-slice-id>.json` and schema `policyos.e02.local_slice_handoff.v2`. One shared receipt may bind several findings and occurrences; do not write 291 duplicate packets. The following is a field map only; its placeholders and empty arrays make it invalid evidence. A committed packet must replace them with actual, source-bound values:

```json
{
  "schema": "policyos.e02.local_slice_handoff.v2",
  "slice_id": "<name matching LOCAL/<name>.json>",
  "slice_base": {"commit": "<full SHA>", "tree": "<tree SHA>"},
  "candidate_source": {"commit": "<root-supplied freeze SHA>", "tree": "<matching tree SHA>"},
  "parents": ["<actual parent SHA>"],
  "source_footprint": [{"path": "<candidate path>", "change": "M", "git_blob": "<blob>", "sha256": "<content SHA>"}],
  "selected_inputs": [],
  "backend_profile": {"backend_id": "<actual backend>", "profile_id": "<actual profile>", "environment_sha256": "<SHA-256 of exact manifest bytes>", "environment_manifest_ref": {"storage": "ignored_local_raw", "path": "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/<slice>/environment.json", "sha256": "<same manifest SHA>", "candidate_source": {"commit": "<frozen source commit>", "tree": "<frozen source tree>"}, "availability": "available_local_readback"}},
  "commands": [{"argv": ["<exact command>", "<arg>"], "cwd": "policy-engine", "status": "PASS", "stdout_ref": {}, "stderr_ref": {}}],
  "chain": {"producer": "<actual producer>", "artifact": "<persisted artifact>", "bridge": "<actual bridge>", "consumer": "<actual consumer>"},
  "controls": [],
  "consumer_surface": {"consumer_id": "<consumer>", "path": "<source path>", "selector": "<exact test/call selector>"},
  "limitations": [],
  "decision_refs": [],
  "proposal_ids": [],
  "proposal_occurrences": [],
  "formal_closure_ids": []
}
```

The smallest useful DevX oracle is one real original occurrence from a final selected slice, one real command with its deciding outputs, the whole relevant producer/artifact/bridge/consumer chain, exact current consumer selector, actual profile/input context, all occurrence-specific controls, and at least one genuine per-occurrence decision choice. Commit the typed receipt and any source-bound choice/output records as an ordinary report-only descendant of the root-supplied source freeze, then read those bytes with `git show <receipt-commit>:<LOCAL/name.json>`. This proves the validator follows a committed Git object. If the root wants an earlier `077a...` schema pilot before final freeze, label it as a temporary oracle only and re-emit/rebind the actual receipt after the final candidate is chosen; the pilot cannot become a final outcome. Do not put a future receipt SHA in its own packet.

`proposal_occurrences` entries have exactly `finding_id`, `occurrence_pointer`, and `criterion_sha256`. Their multiset must equal the complete original occurrence set allocated to that slice. `proposal_ids` must equal the IDs named by those entries; repeated source spans must not be deduplicated by ID or text. Record every affected mechanism and companion in the footprint: implementation, tests, generated/configuration/lock paths, fixtures, and changed consumers. Include unchanged selected paths as `change: "UNCHANGED"` when they are part of the property boundary. The emitter reconciles each footprint row against its recomputed complete-tree census.

The handoff’s `commands` are deciding commands, not a claim that the original criterion passed. Preserve each actual command and `PASS`/`FAIL`/`ERROR`/`SKIP`; an `UNRUN` command needs a reason. A completed command needs both stdout and stderr refs. Do not transform a setup error, skipped backend, or unrun source/input prerequisite into PASS. Each original occurrence still needs its own evaluation state and boundary even when several occurrences share one test run.

For each proposal occurrence, include at least one criterion-specific `decision_ref`; include every distinct alternative and prototype that the evidence supports. A decision row’s `source_ref.covers` names that one exact occurrence pointer and SHA. The allowed kinds are:

- `alternative`: `option_id`, concrete `tradeoff`, and a distinguishing `discriminator`, with source role `decision_alternative`;
- `prototype`: exact `argv` and the actual `PASS`/`FAIL`/`ERROR`/`SKIP`/`UNRUN` status, with source role `prototype_result`;
- `bounded_no_alternative`: explicit reason and falsifier, with source role `bounded_no_alternative_basis`.

The same occurrence may have several distinct options and a prototype. The current verifier rejects an exact duplicate decision, a missing occurrence, an unknown/forged occurrence cover, and a ref whose source was borrowed from a different occurrence. This is the P38 property: validate the actual choice records for every original occurrence, not the count of keys in a mapping. These are research/G choice inputs, never formal closure. `formal_closure_ids` stays `[]`.

## Hashes and local raw outputs

For Git-backed evidence, retain the source as `path@commit` plus `git_blob` and file SHA-256; include the exact JSON pointer where applicable. The v2 output-ref shape for an ignored local raw stdout/stderr is:

```json
{
  "storage": "ignored_local_raw",
  "path": "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/<slice>/<command>/stdout.txt",
  "sha256": "<SHA-256 of exact retained bytes>",
  "candidate_source": {"commit": "<frozen source commit>", "tree": "<frozen source tree>"},
  "availability": "available_local_readback"
}
```

The active ignore rule must be present in the frozen candidate and must ignore that exact path. The current validator rejects missing raw bytes, wrong hashes, path traversal, absolute/backslash paths, symlinks, tracked or indexed raw files, and ignore rules that differ from the candidate. An ignored raw output is a local output reference; it is not an immutable evidence ref and cannot prove a source fact by itself. Keep raw files beside the receipt that cites them and never copy their contents into the report.

The v2 validator directly verifies `stdout_ref` and `stderr_ref`. For deciding JUnit, input, generated-owner, or readback files, give each artifact its own hash-bound source ref in the occurrence evidence/attempt structure and ensure the emitter validates that ref. Do not add an unvalidated `junit_ref` and treat its presence as proof. Retain actual full outputs, elapsed time, and RSS as required by the execution plan; the compact handoff points to them.

## Freeze and per-occurrence evaluation input

The root supplies the final candidate commit/tree after source integration. Resolve the tree from the commit, record its actual parent list and exact branch, and compute the complete source-change census. The v4 `frozen_context` must bind that same candidate and the SHA-256 of the canonical complete census at `/source_boundary/source_freeze/source_change_census`. The candidate is the exact whole-tree checkpoint root freezes, not automatically the earlier implementation commit or the original entry. If reviewed source changes and report notes are committed before the freeze, the later frozen commit includes them; its preceding implementation commit is not relabeled as the freeze. If typed handoffs or outputs are committed after that freeze, those report-only commits are descendants, and the evaluation remains bound to the frozen source commit/tree. Never put a future descendant SHA in an earlier packet. The original entry remains `93d6aa62a8d236667fdf322a5fc17962523b185e`; intermediate checkpoints such as `077a...` are not a substitute for either the original entry or a final candidate freeze.

The v4 file has schema `policyos.e02.occurrence_evaluations.v4` and top-level `schema`, `frozen_context`, `evaluations`. Each explicit evaluation is keyed by exact `(occurrence_pointer, sha256)` and candidate SHA/tree, and includes `state`, `result_summary`, `boundary`, `execution_context`, `evidence_refs`, `attempts`, `next_check`, and `review_escape`. Only add `proposal_disposition`, `limitation`, `falsifier`, `missing_input`, and `new_defining_property_counterexample` when the matching state requires them. Omitted occurrences remain `UNRUN`; do not synthesize 291 rows with placeholder outcomes.

Each `execution_context` must bind the full source-footprint digest, exact configuration/lock evidence or a source-bound scope decision, selected-input state and per-input refs, actual backend/profile, at least one actual consumer surface, the v2 receipt(s), and occurrence-specific decision research. `backend_profile_evidence_index` must point into that same typed receipt at exactly `#/backend_profile`; a nested identity field or a nearby object is not the profile. For available inputs, bind the exact consumed subset and its content hashes. For unavailable inputs, bind each input identity and its source, authority, permission, context, verification, and explicit unavailable reason; use only `UNAVAILABLE_INPUT` or `OPEN_ACTION`. For `not_required`, provide a source-bound `no_input_basis`; for `not_established`, provide `input_scope_not_established` and never mark `VERIFIED`.

Capture `policyos.e02.execution_environment_manifest.v1` as canonical JSON at the cited ignored `LOCAL/raw` path. The exact object has `schema`, `candidate_source`, `backend_id`, `profile_id`, `source_refs`, `runtime`, `platform`, `loaded_import_origins`, `environment_settings`, `command_runs`, `selected_inputs`, and `selected_input_denominator_sha256`. Encode it with sorted keys, compact separators, UTF-8, no duplicate keys or non-finite numbers, and no trailing newline. `backend_profile.environment_sha256` and `environment_manifest_ref.sha256` both equal the SHA-256 of the exact bytes read back from that path; the emitter recomputes it, validates the raw-path ignore/readback boundary, and parses those same bytes.

`source_refs` names exact backend-recipe plus configuration or lockfile paths and SHA-256 values present in the handoff footprint. `runtime` binds implementation, version, and executable; `platform` binds system, release, and machine; each loaded import origin records module, origin, and package version. `environment_settings` is limited to non-secret JSON scalar values. `command_runs` has one index-matched row per handoff command, including `cwd`, exact argv or command, status, and output hashes (or the explicit UNRUN reason). `selected_inputs` is the complete identity-sorted projection of every handoff selected-input row, with unavailable rows carrying a null content hash; the denominator SHA is recomputed over that normalized array. The emitter rejects a changed profile, source ref, selected input, command, or denominator even when the author recomputes the outer manifest hash.

The environment manifest records the execution context; it is not by itself proof that the runtime property passed. The deciding commands and their output artifacts remain separately validated. Bind the actual input manifest and backend profile to every occurrence that depends on them; a task-wide environment label is not a substitute for per-occurrence execution context.

The outcome states are distinct. Every `VERIFIED` evaluation requires occurrence-specific property-positive, actual-consumer, and negative evidence at the real current consumer, regardless of whether a finding-level proposal is closed, limited, held, open, or omitted. `BOUNDED_LIMITATION` requires a named scope, limitation, and executed falsifier. `UNAVAILABLE_INPUT` requires the exact missing input and unavailability evidence. `OPEN_ACTION` requires completed attempts with their real command outcomes and the next runnable action. A candidate `proposal_disposition: "closed"` may be proposed only for VERIFIED occurrences; it still does not close G. A mixed set of occurrence dispositions remains mixed at the finding level. The factory must never map task PASS, author `closed`, old selector PASS, or an exit code alone to a disposition.

For B198, preserve the historical `closed` ledger status and separate `closed_bounded` Appendix C value. Do not make either a formal G closure. If a candidate proposal reopens B198, the emitter requires a new defining-property counterexample bound to each exact occurrence; do not clear or overwrite historical fields.

## Final wave and authority boundary

The execution plan selects one composed required wave after source review and blocking fixes, one required local read-only authentic-input closeout, applicable installed wheel/rebuilt-sdist consumers, and the repository gates. The selected run must be source- and input-frozen. Its handoff must identify the exact current producer → persisted artifact → bridge → real consumer, then retain a distinguishing positive and negative for the original property. For the required local read-only authentic closeout, V1 is `POST → owned context → N5 → CAS → fresh GET`; V6 additionally requires authentic V1 profile, persistence, a later independent failure, CAS/history/debug-served readback, and corrupt-refusal control. Only criterion-specific data is read; retain consumed-subset hashes, permissions, verification, context, and unavailable inputs, without moving a dataset to cloud. The exact source requirements are in the pinned `05-verification-and-release.md#Local read-only authentic inputs`, `06-inputs-and-deferrals.md#A B01–03; B13 authentic served recovery`, `TASKS.json#/tasks/V1`, and `TASKS.json#/tasks/V6`.

For T2 or any other source-backed authority decision, no issuer/currentness/permission is admitted by field presence, an author note, or a test label. If the protected fact lacks a real issuer/verifier/currentness input, report `UNAVAILABLE_INPUT` or `OPEN_ACTION`, or a bounded candidate limitation with a falsifier where that is actually the property. Preserve issuer-only refusal; never turn unavailable authority into an allowed positive. This is consistent with the original identity boundary: PolicyOS owns its own intake and scoped reaction, not the external institution’s signature.

## Pattern pass and acceptance signal

The relevant register patterns are P29 (real outputs, drift-sensitive validator), P32 (resolve/content-bind/verify evidence), P35–P36 (complete denominators and ID-qualified source claims), P37–P38 (freeze and test the gate predicate itself), P39 (include mandatory report/test companions outside mechanism path caps), P40 (classify and widen on the second same-class escape or declare a bounded residual with its falsifier), and P41 (replay from the slice base and prove the changed-path/input denominator). The preflight's `VERIFIED` plus any `PASS` and 64-hex environment label were bucketed `SAME_CLASS_DEEPER`: they are the same common-validator proxy class, closed by requiring cross-field evidence roles and recomputing the exact environment-manifest binding rather than adding per-ID exceptions. The prototype’s decisive property is exact complete source-occurrence reconciliation; a presence/name/prefix check alone is a P38 proxy. Its current result is only a crosswalk preflight, not a source freeze, wave receipt, outcome, or G decision.
