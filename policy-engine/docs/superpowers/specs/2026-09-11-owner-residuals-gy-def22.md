# GY-DEF22 — split-owner decision

Stage 1 decision, before execution or source changes. Lane: `codex/owner-residuals`.
Merge base: `cc74d65813d7bb1259a0f82f6c3cc8b131661a97`.

## Decision: preserve execution; route correctness appointment

**Overall row disposition: routed-to-another-owner — the appointed Foundry
catalog/discovery correctness owner, with the architect owning appointment and
standing.** GY-N12 is the execution lane, not a substitute correctness signer.
Neither another successful test run nor this lane's review can mint the missing
appointment. No completed GY-N12 or GY-DEF22 source is reopened.

The active GY plan, `docs/plans/active/layer3-slices/GY-engine-subordination.md`,
**§8.5 `GY-N12` row**, explicitly resolves the two halves:

| Half | Current owner and standing | This lane's permitted action |
| --- | --- | --- |
| Implementation/execution | GY-N12 / runtime-quality; `executed`, all four clusters merged, diagnostic follow-on delivered | Re-measure the existing bounded diagnostic chain against its exact acceptance nodes; retain failures without changing closed source. |
| Correctness adjudication | Appointed Foundry catalog/discovery owner; receipt **NOT delivered**, typed-empty appointment | Route the exact six-claim packet to this owner through the architect; preserve the empty slot. |

The active row states why the apparent earlier acceptance does not close the
second half: it came from a review subagent, not an appointed authority. The
later source findings **GGA-DEF22-03** and **GGA-DEF22-07** in
`docs/superpowers/journals/2026-09-07-gy-grade-authority.md` corroborate that
standing. GGA-DEF22-07 records the five intended acceptance assertions passing
after owner-pin repair while explicitly leaving appointed acceptance owed.
The earlier proposed-close paragraphs in
`docs/superpowers/journals/2026-09-02-gy-def22-environment-discriminant.md` do not
override the active plan's ruling.

The six bounded claims awaiting appointed Foundry acceptance remain the ones in
GGA-DEF22-03: Foundry owns purpose/profile selection; the identity is dependency
only; closure and first-case ordering are generic; N8 is the sole producer and
consumers share verified bytes; diagnostics never decide admission/closure/
chronology/publication/promotion; and the missing positive authority chain stays
missing. The target packet is the actual resolver/falsifier output, not this
decision document or a fresh subagent verdict.

## Delivered vocabulary and complete census

The shared existing source-derived checker receipt is
`docs/superpowers/journals/residuals/census/raw/invocation-base.json`, SHA-256
`112499cfc606c5e40e7146ec6016f95e10d8160a51c267d6a1573cb817cc0bc0`.
Its complete denominator is **2,654 tracked `src/**/*.py` files**, with 5,670
current versus 5,669 base tracked Python files across `src`, `tools` and `tests`.
The additional file is this lane's exception test; there is no source delta.
The checker returned exit 0 with zero invocation regressions. Root's independent
Git-tree/recursive-filesystem and AST census reconciled the full source set:
36,135 synchronous functions, 879 async functions, 9,935 classes and zero parse
errors. Path-set SHA-256 is
`b91000ce91548fa9c18caf7dcb943b861307d61eb84477bf47dfd330680243d8`.

The row uses delivered vocabulary, not its historical `producer_missing` label:

- `resolve_dependency_discriminant` and `diagnose_dependency_environment` in
  `src/polisyos/foundry/methods/catalog/dependency_profile.py` have actual static
  paths from the Foundry sync command. The checker names `_run_diagnose` and
  N8's `_resolve_frozen_foundry_dependency_discriminant` /
  `_current_dependency_environment_diagnostic` as non-test callers.
- The producer is `build_dependency_discriminant_companion` and
  `write_dependency_discriminant_companion` in
  `tools/quality/validation/check_layer3_gy_value_gate_contract.py`.
  It is under `tools`, so a source-only name search cannot establish its absence.
- N8 `validate_foundry_dependency_discriminant`, N10a
  `check_layer3_gy_second_domain_pack.read_foundry_dependency_discriminant`, and
  chronology `check_layer3_gy_epoch_chronology_contract.read_foundry_dependency_discriminant`
  are separate actual readers. Each reader's function body was read; their
  adjacency or common import is not the asserted bridge.
- `_run_dependency_discriminant_consumers` in
  `tools/quality/validation/execute_gy_n12_artifact_transition.py` reads the exact
  committed companion via `_git_blob(expected_head, path)`, invokes all three
  readers and records their shared content/profile binding. This is the exact
  persisted reader chain, not another uninvoked helper.
- `_value_dependency_diagnostic` in
  `src/polisyos/runtime/http/services/governed_projection_validation_worker.py`
  reads the companion, calls N8's verifier and projects the bounded diagnostic.
  Its framework/callback boundary is a declared limitation of the static
  invocation model, not proof of a missing producer.

The independent row trace follows the actual artifact from its generated-family
registration through writer, committed-blob reader and these exact callers.
`architecture/generated_artifacts.toml`, family
`policy-design-case-layer3-gy-n8-dependency-discriminant`, names `team-foundry` as
owner and approval owner; registers the persisted output
`architecture/policy_design_case/layer3_gy_n8_dependency_discriminant.json`; and
limits its promotion target to machine/audit environment diagnosis. Its stale
output posture is fail. No new checker or symbol-family contract is added.

## Named caller and registration before code

The production caller is the existing N8 validator's `main`, which dispatches
to the companion writer/checker. The independent Foundry diagnostic entry is
`tools/devx/foundry/sync_dependency_profile.py::_run_diagnose`, reached by its
`main`. Both are discoverable through `tools.registry`: the validation and
Foundry category roots enumerate these modules, recognize `main`, and translate
underscores to hyphens. The command addresses are:

- `polisyos-tools validation check-layer3-gy-value-gate-contract`;
- `polisyos-tools foundry sync-dependency-profile`.

The GY-N12 transition command is likewise registered as
`polisyos-tools validation execute-gy-n12-artifact-transition`.
No separate path-only launcher is built by this lane. Registration will be
read back from `TOOL_SPECS_BY_KEY` during Stage 2; the existing command bodies,
not a string occurrence in a registry, supply the call trace.

The companion is strict, content-bound and replayed from owner source freeze,
profile declaration, lock graph and exact N8 bytes. It carries
`decision_role=ambient_non_decisive` and authority only for
`dependency_environment_diagnosis`. `_validate_foundry_dependency_discriminant`
retains `legacy.governing_issues` for both accepted and invalid companions;
diagnostic findings enter the ambient channel. Thus missing or wrong diagnostic
input must produce a typed non-receipt or named diagnostic failure, never a
favorable authority default.

This is a routing verification, not a new all-surface runtime claim. The
five acceptance nodes exercise the N8/N10a/chronology consumers. The existing
HTTP service tests replace the owner subprocess, and therefore cannot establish
live Foundry authority or the missing appointment. Any stronger HTTP request
claim remains with the corresponding Runtime owner and must include an actual
request/worker witness; this lane does not substitute static callback discovery
for that evidence.

## Stage 2 exact verification and removal

Commit this document before executing tests. No source change is proposed.
Use one targeted invocation for these five exact closure-signal nodes, preserving
all stdout/stderr, individual failure reasons, exit code and wall time:

1. `tests/repo_quality/tools/test_execute_gy_n12_artifact_transition.py::test_cb_i01_n8_n10a_and_chronology_share_one_foundry_discriminant`
2. `tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02_research_profile_names_torch_as_first_generic_case`
3. `tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02a_label_and_shape_cannot_mask_two_data_generated_incompatibilities`
4. `tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03_outside_closure_difference_is_diagnostic_irrelevant`
5. `tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03a_novel_admitted_profile_verifies_from_owner_data`

AST enumeration, including `AsyncFunctionDef`, counted 202 test definitions in
the complete dependency-profile test file and 54 in the complete transition test
file; none are async. These are function-definition counts, not parametrized
pytest item counts. Only the five named nodes run from those files.

If a node refuses on stale owner pins before its intended assertion, preserve
that as a current non-receipt and route it to the Foundry dependency-profile
registry owner. Do not regenerate closed owner artifacts, claim the intended
assertions passed, or call the failure inherited without the exact slice-base
P41 demonstration. Historical five-green receipts cannot replace this run.

A separate unchanged-negative probe uses the already-worked **GGA-DEF22-01**
removal design with fresh two-package owner data through the actual Foundry
resolver and diagnoser. It lives only in the gitignored
`docs/superpowers/journals/residuals/gy-def22/raw/test_gy_def22_diagnostic_probe.py`,
node `test_dependency_disagreement_is_named`. It persists the actual resolved
strict discriminant to raw scratch, reads those exact bytes back through
`DependencyProfileDiscriminant.model_validate_json`, supplies a valid observation
with one incorrect in-closure version, and asserts diagnostic `fail` naming the
changed distribution coordinate. The raw artifact is a bounded diagnostic
witness, not an appointed correctness receipt or a new producer implementation.

Run that unchanged node with an isolated pytest plugin that generates three
control phases through an unused fixture parameter: baseline; removal of `_calculate_dependency_distribution_cases` by an
in-memory replacement returning `()`; restoration of the original callable.
The unchanged middle negative must fail for **dependency disagreement was not
detected**, with no collection/import failure. Source bytes, schema, rule and
discriminant content ref remain unchanged. An expected middle failure is still
reported as pytest exit 1; it is not relabelled as an all-green suite. Each phase
and its assertion outcome are retained independently. This avoids repeated
scientific imports while preserving the exact same assertion. No tracked source
or closed test file is modified.

Raw output stays under `docs/superpowers/journals/residuals/gy-def22/raw/` and the
single root completion journal carries the result. No directory-wide test, epoch
transition, production-data write, source repair, register edit or ledger edit
is authorized by this routing decision.

## Independent task routing and pattern pass

The four positive runtime-authority capabilities are a different task, not the
missing appointed signature on this diagnostic close. A full active-document
census read 123 tracked paths, including all 112 allowed Markdown/JSON paths
excluding DEBT-REGISTER and LEDGER. The proposed name `FR-AUTH-01` appears in the
active GY plan's **`GY-FA1` row**: the architect registered that actual task on
2026-09-11 as `not_started`, owned by Foundry + Runtime, explicitly choosing the
main GY plan instead of the proposed standalone filename. This is the concrete
counterexample to a filename/name absence census. **Route those four capabilities
to existing `GY-FA1`; do not invent or re-register FR-AUTH-01.** GY-FA1 does not
satisfy the separate DEF22 appointed-correctness receipt.

P01/P02/P27: retain the real producer and consumers. P05/P15/P37: a diagnostic or
reviewing subagent cannot supply appointed authority. P29/P33: remove the actual
case calculation while the schema/rule/content markers remain. P35/P36: use the
complete source denominator and cite `GY-N12`, `GY-FA1`, GGA-DEF22-03 and
GGA-DEF22-07 rather than adjacent historical proposed-close prose. P38: execution
and institutional appointment are different properties, so code passing cannot
stand in for the second. P40 classification: the alleged missing adjudication
is the **same known authority/appointment class**, not a new implementation
escape; no widening round or new mechanism is justified. Current owner-pin drift,
if reproduced, is a separate freshness/maintenance class routed to the Foundry
profile owner, not a reason to absorb GY-FA1 or reopen GY-N12.

Acceptance here is the split, evidence-bearing **routed-to-another-owner**
verdict: say exactly what the engineering witnesses establish and what they fail
to establish; retain the typed-empty appointed Foundry slot; preserve completed
source; and keep any current pin failure and positive-authority task with their
actual owners. No claimed closure of one half closes the other.
