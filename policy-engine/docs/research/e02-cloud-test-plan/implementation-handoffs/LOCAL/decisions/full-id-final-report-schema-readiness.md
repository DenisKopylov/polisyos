# Full-ID final report schema readiness

**Status:** read-only input/schema audit. No emitter, tests, Git commands, or native wave were run. This note does not set an outcome, freeze a candidate, or make a G decision.

## Current artifacts and occurrence identity

The canonical input source is `closure-decisions/coverage.json` (SHA-256 `97860dc18c7b92124971aa8032fc229be3367723ea2ec45e6cda4a777e544e01`). Its full parsed denominator is 127 bundles, 282 findings, and 291 criterion occurrences. The key is the exact pair `(coverage JSON pointer, criterion-span SHA-256)`; occurrences with identical text/hash remain distinct when their pointers differ. The current proposal output [finding-proposals.json](../finding-proposals.json) is schema `policyos.e02.finding_proposals.v4` (SHA-256 `1bd47384a114951b89305ec48892593ae061933d9d0b2fa884e63a47b3b97908`): it preserves all 282/291 rows, reports `provisional_author_review_pending_final_source_freeze`, and has all candidate rows `UNRUN`. Its `formal_closure_ids` is `[]`. The file’s own checkpoint is provisional navigation context, not a final source identity.

The registered final input, `LOCAL/crosswalk/occurrence-evaluations.json`, is absent. The existing ignored `LOCAL/raw/full-id-closeout-preparation/full-id-current-draft.json` (SHA-256 `b04812ae40f423c6c5105a9ffa781a0c8830d05c14ad9f5cdfabb2d5fad3f894`) has schema `policyos.e02.full_id_current_draft.v1`, status `PREPARATION_ONLY_NOT_IMPORTABLE`, and 291 locator/evaluation rows marked `UNRUN`. It explicitly says there is no final source/config/input/backend/profile freeze or final-wave evidence. It is not a v4 input: it uses a different top-level shape, carries extra per-row preparation/formal-closure fields, and has no frozen source/evidence suitable for evaluation. Do not copy its `UNRUN` rows into the v4 importer or infer a current outcome from them.

B198 history remains separate from current outcome: its prior ledger value is `closed`, Appendix C is `closed_bounded`, and `closure_now` is `not_adjudicated`; its candidate row remains `UNRUN`. Preserve those historical fields. A candidate proposal that reopens B198 must include the exact-occurrence `new_defining_property_counterexample`. Formal G closure remains `[]` throughout this proposal process.

## Emitter contract

The current emitter is `LOCAL/emit_proposals.py` (SHA-256 `4d5e70c67f62af07cdb7d3313ad3caa2a689172888b44051c13bb07e6dbbacec`). The controlling code is `validate_evaluation_input_artifact`, `validate_explicit_evaluation`, `validate_execution_context`, `validate_environment_manifest_bytes`, and `apply_evaluations`.

The registered v4 input has exactly `schema`, `frozen_context`, and `evaluations`. `frozen_context` has exactly root-supplied candidate `{commit, tree}`, the fixed `/source_boundary/source_freeze/source_change_census` reference, and the canonical SHA-256 of the complete census. Each explicit row has a unique exact `(occurrence_pointer, sha256)` key and the same candidate identity. Required fields are `state`, `result_summary`, typed nonempty `boundary`, `execution_context`, `evidence_refs`, `attempts`, `next_check`, and `review_escape`; only the declared conditional fields may be added. The input deliberately permits a subset of rows: an omitted occurrence stays `UNRUN` in the full output. There is no `UNRUN` evaluation-row state in v4, so do not synthesize placeholder evaluation rows to reach 291.

Every explicit row needs occurrence-bound immutable evidence. Its execution context binds the complete source-footprint digest; configuration/lock refs or a source-bound configuration scope; selected-input state and matching evidence or scope; a backend profile; a current consumer surface; a typed slice receipt; and decision research. Evidence refs bind the same exact pointer/hash and candidate. `VERIFIED` always needs `property_positive`, `actual_consumer`, and `negative` roles. `BOUNDED_LIMITATION` needs a named limitation and an executed falsifier. `UNAVAILABLE_INPUT` needs the identified missing input and unavailability evidence. `OPEN_ACTION` needs completed, source-bound attempts with actual `PASS`/`FAIL`/`ERROR`/`SKIP` status and a runnable next check. The current output also retains per-occurrence boundary and next-check fields for rows left `UNRUN`; those remain unassessed, not positive evidence.

The slice receipt is `policyos.e02.local_slice_handoff.v2` and binds a slice base, frozen candidate, actual ordered parents, complete affected footprint, inputs, commands and output refs, producer/artifact/bridge/consumer chain, controls, limitations, decision refs, and exact covered occurrence triples. Receipt and evidence refs are validated against Git objects and candidate ancestry by the emitter. `formal_closure_ids` must remain empty. A task status, author proposal, historical status, or passing command cannot replace the occurrence-specific consumer evidence.

## Environment boundary and partial captures

The v2 receipt’s `backend_profile` and v1 environment manifest are strict. The profile requires backend/profile IDs, an exact manifest hash, and an ignored-raw manifest ref. `policyos.e02.execution_environment_manifest.v1` has a closed field set; it requires complete nonempty runtime/platform values, nonempty loaded-import-origin rows with nonempty origin and package-version strings, source refs for both a backend recipe and configuration/lock, a command row for every handoff command, and selected-input rows matching the handoff list and its digest. It cross-binds command argv/cwd/status/output hashes and selected inputs; the manifest bytes are canonicalized and rehashed.

That v1 shape cannot truthfully encode an unresolved import owner/version or a partially observed process environment: replacing an unknown with a placeholder string would pass shape checks while misrepresenting the capture. It also checks that the manifest’s selected-input list equals the handoff list and its self-digest, but does not independently derive completeness of that list from a frozen source/fixture manifest. The task-specific `environment-manifest-v2-decision.md` (SHA-256 `1bbda8c9b59a76dbe99c9c2f2511eed376d1950951d5f99e99be96a76ce66d90`) already records this same-class P37/P38 limitation and the alternatives.

The immediate safe disposition is to keep profile-dependent occurrences `UNRUN`/`OPEN_ACTION` when no complete v1 manifest exists; an unavailable scientific/data input can use the existing input-state path only when the required real runtime profile and receipt are still valid. If partial runtime observations must be a first-class admitted context, the minimal G choice is: retain v1 as complete-only and authorize a discriminated v2 observation plus a handoff v3 tagged choice between a complete v1 profile and partial observation. The v2 route may carry evidence/limitations but cannot itself make a profile-dependent occurrence `VERIFIED`. Do not stringify unresolved values or loosen v1. The v2 proposal must also bind selected inputs to the frozen source/fixture manifest rather than only to a mutually matching self-declared list.

## Author inputs, independence, and P40

The A–F assessment packets and source-author proposals are source/property locators and author input. The v4 evidence reference carries a role and immutable source/candidate/occurrence binding, but the schema has no reviewer identity or source-intersection field that certifies independence. Therefore, an independent review can be retained as a separate source-bound artifact, but it must report the reviewer and overlap in source files, selectors, profile, and inputs. Shared evidence is not independent corroboration merely because it appears in multiple owner packets or has a second reviewer label.

P40 classification: this is the existing `SAME_CLASS_DEEPER` environment/evidence-completeness class, not a new class. The structural close is one generic admission mechanism that verifies the complete set and its provenance; do not add per-occurrence exceptions. The distinguishing falsifier is a retained process capture whose module has no resolved distribution owner, paired with a v1 manifest that labels its package version `unresolved` while keeping all markers and hashes valid; that fake completion must not be mistaken for a complete observed profile. Separately, a shortened selected-input list with a recomputed self-digest must be rejected when compared with the frozen source/fixture manifest.

## Final run gate

No final evaluation input, complete final source census, or admitted final environment is present in the inspected artifacts. After root supplies the frozen candidate and the v2 receipts/evidence are committed as report-only descendants, the writer command from the repository root is:

```sh
python3 -B policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/emit_proposals.py \
  --frozen-commit <root-supplied-40-hex-commit> \
  --frozen-tree <root-supplied-40-hex-tree> \
  --evaluations policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/crosswalk/occurrence-evaluations.json
```

Then read back `LOCAL/finding-proposals.json` and `LOCAL/crosswalk/receipt.json`, and run the emitter’s read-only check from the same repository root:

```sh
python3 -B policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/emit_proposals.py --check
```

Reconcile the complete original pointer/hash multiset, keep omitted rows `UNRUN`, preserve B198 history, and confirm `formal_closure_ids: []`. These are required final-run inputs, not results established by this audit.
