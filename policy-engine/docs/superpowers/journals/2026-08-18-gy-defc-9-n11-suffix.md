# GY-DEFC-9 N11 Suffix Execution Journal

Date: 2026-08-18

Branch: `codex/gy-defc-9-n11-suffix`

Dedicated worktree: `/Users/deniskopylov/polisyos/.worktrees/gy-defc-9`

Base: `3fde27f0de93229d13839b86475f4ff4c25126a2`

## Objective and authority

`P30` objective: **a cold N11 live-contract validation returns zero issues.** The closed
`owner_bundle_loaded` objective does not name this task and receives no progress receipt here.

The user approved the Foundry-owned governed provenance projection, typed N8 result, N10a governing-
subset consumer, Item 3 non-decisive-by-construction ruling, confidence-only reissue, and cold-last
ordering. This journal records execution; it does not reopen design approval. `[P37:
institutionally_supplied]`

## Entry and environment receipts

- The dedicated linked worktree is attached to `codex/gy-defc-9-n11-suffix`; `HEAD` and `main` both
  resolved to `3fde27f0d…`, and `66d08f287` is an ancestor. The tracked tree was clean. `[P37:
  recomputed]`
- Worktree-local offline provisioning was a tooling non-receipt because locked `jaxlib==0.8.2` and
  then `pandas==2.3.3` wheels were absent from the cache. The complete canonical interpreter is used
  only as a dependency runtime with `PYTHONPATH` forced to this worktree's `src`; `polisyos.__file__`
  resolved to this worktree. The canonical `production_data` directory is linked read-only into the
  ignored worktree path. `[P37: recomputed]`
- N8 `--check-catalog-provenance --output-format json` exited `1` in `16.36` seconds with exactly the
  five registered codes below. `[P37: recomputed]`
- N10a `--check --output-format json` exited `1` in `17.18` wrapper seconds (`6.676628` internal
  seconds) with only `stage_gap_triage_drift:n8_transport_tuple_hardcode`. `[P37: recomputed]`

No mechanism repair round and no cold allowance was consumed by setup or entry reproduction.

## Pre-implementation five-code disposition

The parent ambient admission is equal recorded/live and exactly
`{status: quarantined_unbound, included_in_governed_denominator: false,
fail_closed_action: quarantine}`. `[P37: recomputed]`

| Code | Destination | Complete evidence |
| --- | --- | --- |
| `catalog_ambient_discovery_manifest_mismatch` | `ambient_findings` | Compares only the ambient block's `manifest_id` under the valid non-governing admission. |
| `catalog_ambient_component_manifest_mismatch` | `ambient_findings` | Compares only ambient count/set/addition/overlap observations under that admission. |
| `catalog_ambient_unbound_input_manifest_mismatch` | `ambient_findings` | Compares only the retained ambient `unbound_inputs` observation under that admission. |
| `catalog_predicate_provenance_mismatch` | split per row below | Whole-list equality is forbidden as a disposition. The only live drift is one structurally non-decisive quarantined row. |
| `catalog_provenance_manifest_mismatch` | derived consequence; must stop firing | Raw full-payload IDs differ (`method_catalog_provenance_8b24b2b3…` frozen versus `method_catalog_provenance_e630af38…` live). Raw custody remains protected by `catalog_provenance_content_hash_mismatch`; raw identity drift is not an ambient finding. |

## Complete predicate-provenance row denominator

The complete denominator is `32/32` recorded rows and `32/32` live rows; all `64/64` row values are
mappings, each side has `32/32` unique non-empty predicate names, and the union has 32 names. Exactly
one row differs. A read-only luna reconciliation repeated the census with the same canonical
dependency runtime and worktree source and reproduced the five-code receipt, equal admissions,
denominators, and sole differing row. `[P37: independently_reconciled]`

For an equal row, the destination states where a future row drift must land. Missing, malformed,
duplicated, contradictory, or unknown row admission fails closed into `governing_issues`.

| Predicate | Recorded class | Live class | Decisive/action | Equal | Destination |
| --- | --- | --- | --- | --- | --- |
| `ambient.development_scan_contributed_bytes` | recomputed | recomputed | false/quarantine | yes | `ambient_findings` |
| `ambient.development_scan_import_closure` | recomputed | recomputed | false/quarantine | yes | `ambient_findings` |
| `ambient.development_scan_root_membership` | recomputed | recomputed | false/quarantine | yes | `ambient_findings` |
| `ambient.discovered_component_membership` | not_established | recomputed | false/quarantine | **no** | `ambient_findings` |
| `ambient.duplicate_precedence` | recomputed | recomputed | false/quarantine | yes | `ambient_findings` |
| `ambient.entry_point_distribution_identity` | recomputed | recomputed | false/quarantine | yes | `ambient_findings` |
| `ambient.entry_point_group_enumeration` | recomputed | recomputed | false/quarantine | yes | `ambient_findings` |
| `ambient.entry_point_source_byte_closure` | not_established | not_established | false/quarantine | yes | `ambient_findings` |
| `ambient.source_policy` | recomputed | recomputed | false/quarantine | yes | `ambient_findings` |
| `ambient_discovery_exclusion_policy` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `catalog_registry_denominator_equality` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `catalog_snapshot_content_identity` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `catalog_snapshot_repeatability` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `evaluation_mode_taxonomy_derivation` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `governed.development_scan_contributed_bytes` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `governed.development_scan_import_closure` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `governed.development_scan_root_membership` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `governed.discovered_component_membership` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `governed.duplicate_precedence` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `governed.entry_point_distribution_identity` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `governed.entry_point_group_enumeration` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `governed.entry_point_source_byte_closure` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `governed.source_policy` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `governed_discovery_policy` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `governed_registry_content_binding` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `identification_status_taxonomy_derivation` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `native_contract_family_taxonomy_derivation` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `recorded_live_provenance_equality` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `registry_matches_governed_manifest` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `runtime_backend_package_identity` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `value_capability_owner_reconciliation` | recomputed | recomputed | true/reject | yes | `governing_issues` |
| `value_capability_set_hash_derivation` | recomputed | recomputed | true/reject | yes | `governing_issues` |

The two literal `not_established` values classify predicate evidence, not placement. Both rows are
structurally non-decisive and quarantined under the valid parent admission. No row placement is
`not_established`; the correction's stop condition is not triggered. `[P37: recomputed]`

## Item 3 settled ruling

The historical environment discriminator is `not_established`. Constructing one after the freeze
would bind a fact the frozen record never carried and is therefore a forbidden rebaseline. The full
ambient posture, including import failures and `unbound_inputs`, remains recorded and protected by
the raw custody identity as diagnostic evidence. Ambient posture is no longer a governed replay
prerequisite. `[P37: institutionally_supplied for the ruling; not_established for the historical
discriminator]`

## P39 measured path split

Mechanism: three source paths (`snapshot.py`, N8, N10a), three mirrored test paths
(`test_catalog_snapshot.py`, `test_value_gate.py`, `test_second_domain_pack.py`), and the reissued
confidence artifact. Record companions: this plan, this journal, and standing paragraphs inside
`GY-DEF14`, `GY-DEF16`, and `GY-DEFC-9`. If the Depth-N behavioral witness demonstrates that a fourth
test path is necessary, the measured mechanism set expands and is recorded; no mechanism is split to
fit the prior estimate. `[P37: institutionally_supplied for the counting rule; recomputed for the
initial path census]`

## Repair-round ledger

| Item | Blocking/Important findings | Remaining rounds | Status |
| --- | ---: | ---: | --- |
| Items 1+2 | 0 | 2 | green; source frozen |
| Item 3 | 1 | 1 | green after typed rederive-report correction; source frozen |
| Item 4 | 0 | 2 | not started |
| Item 5 | n/a | single cold allowance unspent | not authorized yet |

## Execution receipts

### Items 1+2 mechanism

- Foundry now derives a governed catalog-provenance projection while leaving the complete raw
  ambient block and raw `provenance_id` untouched. Only an exact valid parent quarantine admission
  and exact predicate-row structure permit non-decision; missing, malformed, duplicated, or
  contradictory declarations raise the named fail-closed catalog error. `[P37: recomputed]`
- N8 now returns `ValueGateValidationResult(governing_issues, ambient_findings)`. Raw custody hash
  failure remains governing; ambient block differences route only under the structural admission;
  predicate differences are placed per row; the raw aggregate
  `catalog_provenance_manifest_mismatch` is emitted nowhere. Validation, full check, and rederive
  compare through the one Foundry projection. The strict N8 reissue authorization is unchanged and
  unused. `[P37: recomputed]`
- N10a now calls `validate_payload_result` and decides its bridge only from
  `governing_issues`. The typed-result tests fail if it falls back to the tuple wrapper. No issue-code
  allowlist and no N10a receipt field was added. `[P37: recomputed]`

### Real environment and Depth-N witness

Two fresh `-S` child environments used the worktree interpreter and isolated site-package trees.
Both copied the same complete `polisyos-foundry-method-example` distribution metadata; one editable
`.pth` target contained the real example module and one target was empty. The complete discovered
component denominator was `390` in the importable posture and `389` in the missing-target posture.
The example resolved only in the first and produced `ModuleNotFoundError` only in the second. The
recorded raw provenance identity was equal across environments; the importable live raw identity
differed from recorded while the missing-target live raw identity equalled it; both live governed
identities equalled the recorded governed identity. `[P37: recomputed]`

Both environments returned zero N8 governing issues, N10a `status:pass` with zero issues, and
Depth-N `status:stable` with zero issues. The importable posture retained exactly four ambient
findings: the three ambient-block codes and the per-row
`catalog_predicate_provenance_mismatch` for `ambient.discovered_component_membership`. An internally
rehashed governed component-count mutation stayed red in N8 and N10a with
`catalog_builtin_discovery_manifest_mismatch`, and Depth-N returned that same named code inside
`n8_owner_validation_failed`. `[P37: recomputed]`

### Tests and live receipts

- The complete two-file Foundry/N8 denominator was `23 + 83 = 106` collected tests; `106/106`
  completed green. The five N10a transport tests completed green as a four-test typed/bridge run plus
  the serialized real-environment test. `[P37: recomputed]`
- N8 `--check-catalog-provenance` and full `--check` exited `0`, each reporting exactly the four
  ambient findings above and zero governing issues. N8 `--rederive-audit` exited `0` in
  `59.352921` internal seconds and emitted those same four ambient findings. N10a full `--check`
  exited `0` with zero issues (`6.497074` internal seconds). `[P37: recomputed]`
- Ruff, bytecode compilation, and `git diff --check` passed over all six changed Python paths.
  `[P37: recomputed]`
- All six frozen N8/N10a artifact files are byte-identical to `HEAD`: N8
  `c3f131ce4f47…`, census `ba20cdb384eb…`, pack `169df14ab4fb…`, smoke
  `688bd3d8c845…`, trace `9b78cad2693a…`, and gaps `361434b07fcd…`. The denominator is every N8
  artifact plus all five N10a artifact files. `[P37: recomputed]`

Architecture guardrails remain red on five deep imports in untouched `runtime/http` files. A clean
full `git archive HEAD` reproduced the exact same deep-import delta and five findings, while the six
named files and their baseline have zero working-tree differences. This is a base-state verification
finding, not an exclusion inferred from directory names; no architecture baseline was changed.
`[P37: independently_reconciled]`

### Independent review and repair round

Two read-only terra/luna reviews inspected the full mechanism. One returned no findings. The other
returned one Important Item 3 finding: `--rederive-audit` used the legacy governing-only tuple and
therefore hid ambient findings. This consumed Item 3 repair round 1. A red test required a typed
rederive result and emitted ambient summary; the correction added `run_rederive_audit_result`, kept
the tuple wrapper for the existing disposition-ledger truthiness consumer, and routed the CLI through
the typed result. Delta review closed the Important finding. Its Minor request for explicit raw and
governed identities was also implemented and re-reviewed; no Blocking, Important, or Minor finding
remains. `[P37: independently_reconciled]`

### Measured mechanism cut

The source/test mechanism is six paths, `1,126` added and `155` removed lines: Foundry owner/test
`128/0 + 117/0`; N8 owner/test `364/127 + 164/25`; N10a consumer/test `7/3 + 346/0`.
The larger test body is the genuine two-environment plus Depth-N process witness, not a split
mechanism. The confidence artifact remains the seventh pending mechanism path. `[P37: recomputed]`

Items 1–3 are source-frozen. Item 4 is now eligible for an exact pre-write declaration; no confidence
writer and no cold N11 run has started. `[P37: recomputed]`
