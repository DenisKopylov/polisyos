# Data Forge relocation repairs — Task 4 journal

## Ledger and pattern pass

- Ledger: 4/8. This is a round-free repair inside the already-spent ledger;
  it creates no new authority-bearing surface and does not loosen an import
  policy, package boundary, exception, or baseline.
- Relevant patterns: P01 (alias-only compatibility), P05/P15 (producer error
  identity leaking across a Lex authority boundary), P06/P27 (compatibility
  shim and duplicate owner drift), P10/P29 (behavioral rather than
  source-marker verification), P35/P36 (complete consumer denominator and
  frozen-row correction), and P37/P38 (the tested boundary is the actual
  read/error behavior, not an import string).
- Correct pattern: Data Forge retains legal corpus write contracts and
  producer errors; Lex owns runtime readers, errors, and read-side versioning
  DTOs. `lex.api.resolve_active_version` adapts the producer result and
  translates `PolicyOSError` semantics. NormPack calls that Lex boundary.
- Capability state: the read boundary has typed Lex contracts, Data Forge
  producer, explicit adapter bridge, NormPack consumer, and negative semantic
  tests. The Foundry-method residual inventory below retains twelve
  `consumer_missing` contracts; no claim is made that they have workflow
  consumers.

## Frozen row 21 amendment

Amended frozen row 21 text: `common.timestamps` owns
`latest_object_by_subject`, `parse_iso_date` — **shared-contract-down**:
Common is the measured lowest legal owner for `latest_object_by_subject`; its
complete consumer set is `data_forge.domains.legal.corpus.versioning`,
`lex.common`, and `lex.normpack.select_sources`. Keep the selector in Common
with no production relocation; DataForge-specific fact selection remains in
the existing corpus module.

The three-consumer census used the complete `src/**/*.py` denominator (2,579
Python files) and found exactly:

1. `polisyos.data_forge.domains.legal.corpus.versioning`
2. `polisyos.lex.common`
3. `polisyos.lex.normpack.select_sources`

## Foundry method-contract residual ledger

| Contract | Consumption state | Residual state |
| --- | --- | --- |
| `d1_multiplex_network` | `selectable_unselected` | `consumer_missing` |
| `d1_trade_network` | `selectable_unselected` | `consumer_missing` |
| `d1_trade_network_causal` | `selectable_unselected` | `consumer_missing` |
| `d1_distress_network` | `selectable_unselected` | `consumer_missing` |
| `d1_distress_network_causal` | `selectable_unselected` | `consumer_missing` |
| `d1_public_service_network` | `selectable_unselected` | `consumer_missing` |
| `d1_public_service_network_causal` | `selectable_unselected` | `consumer_missing` |
| `d2_panel_observational` | `exercised_workflow_consumer` | `none` |
| `d2_dynamic_treatment` | `selectable_unselected` | `consumer_missing` |
| `d2_microsim_survey` | `selectable_unselected` | `consumer_missing` |
| `d2_survival` | `selectable_unselected` | `consumer_missing` |
| `d2_panel_econometric` | `selectable_unselected` | `consumer_missing` |
| `d3_microsim_survey` | `selectable_unselected` | `consumer_missing` |

## Receipts

### Prior supplied receipts

- Task 1: RED collection exit 2 because
  `load_verified_stage_output_bytes` did not exist; GREEN 12 focused tests
  passed and changed-file Ruff passed.
- Task 2: RED eight focused failures; GREEN 43 focused tests passed.
- Task 3: RED persistence, selection, workflow-ordering, lineage, and
  execution-as-validity falsifiers; GREEN 37 focused tests passed. The inherited
  source import census was 48 identities (45/1/2/0), and the inherited Ruff
  identity comparison was three diagnostics in each tree, six observations,
  three normalized identities, symmetric difference zero. The Task-3 release
  gate was exit 1 with 24 additions/54 removals; the package gate was exit 1
  with 152 findings and 42 forbidden statements.

### Task 4 RED

- The first prescribed command initially could not collect because the linked
  worktree environment lacked `pytest` (`No module named pytest`). The same
  `.venv` then had the declared `test` extra provisioned and the command was
  rerun.
- `.venv/bin/python -m pytest tests/unit/data_forge/legal_batch/test_lex_shared_contract_relocation.py tests/unit/lex/mirror_contracts/test_api.py tests/unit/lex/mirror_contracts/test_artifacts.py tests/unit/lex/mirror_contracts/test_errors.py tests/unit/lex/mirror_contracts/test_types.py tests/unit/lex/test_common.py -q`
  produced four expected failures: import-time Data Forge compatibility edge,
  unadapted active-version result identity, untransformed Data Forge error
  identity, and remaining Lex writer DTO surface.
- The companion behavioral mutation run of
  `.venv/bin/python -m pytest tests/unit/lex/mirror_contracts/test_api.py -q`
  produced two expected failures after temporarily removing the NormPack
  Lex-API route and provision-index error translation. Both mutations were
  restored before GREEN verification.

### Task 4 GREEN

- The prescribed focused command passed with 10 tests.
- Focused companion Fabric producer tests plus the prescribed set passed with
  19 tests.
- Changed-file Ruff passed after using the declared `lint` extra.
- The public-surface renderer's expected JSON and Markdown exactly matched the
  surgically updated inventory/reference files.
- The preliminary package replay was exit 1 with 153 findings and 40 forbidden
  statements. That receipt exposed one stale exact coordinate in
  `architecture/imports/dynamic.toml` and two avoidable direct
  `polisyos.core.errors` spellings. After updating the existing dynamic row and
  re-spelling both imports through the already-supported `polisyos.core`
  facade, the final package replay was exit 1 with 150 findings and the same 40
  forbidden statements. The gate remains fail-closed; no composite success is
  claimed.
- Standalone package-boundary census: exit 0, `*.py` denominator 2,579,
  derived forbidden edges 40, reported forbidden edges 40, and both set
  differences empty. The removed compatibility keys were absent:
  `lex.artifacts -> data_forge.kernel.artifacts`, `lex.errors ->
  data_forge.errors`, and `lex.types -> data_forge.domains.legal.contracts`.

### Task 4 final verification boundary

- Focused behavior: exit 0, 19 tests passed. The interpreter resolved
  `polisyos` to this worktree's `src/polisyos/__init__.py`. The measured run was
  `user=4.35s`, `sys=0.80s`; the uptime pair advanced from 13:41/up 3 days 3:54
  to the same minute.
- Changed-file Ruff: exit 0 with no diagnostics (`user=0.03s`, `sys=0.01s`).
- Public-surface derivation: the contract parser found eight generated-artifact
  families and both rendered outputs matched byte-for-byte. A first helper
  invocation that omitted those families was rejected as a harness
  non-receipt; it caused no repository edit.
- Dynamic-import closure signal: the canonical package report has no dynamic
  finding for `src/polisyos/lex/__init__.py`; an independent exact check of the
  AST call at line 197 against `dynamic-42c906379e48` also finds no mismatch.
- Source import predicate: exit 1 with 48 findings, split ARCH001=45,
  ARCH002=1, ARCH004=2, ARCH006=0. The canonical report and the independent AST
  walk agree over 2,579 `*.py` files; the independent ordered-pair sum is also
  45. The measured completed failure was `user=0.58s`, `sys=0.15s`, with an
  uptime pair in the 13:43/up 3 days 3:56 minute.
- Release guardrail predicate: exit 1 pending the authorized explicit baseline
  transaction. The guardrail collector and an independent AST derivation both
  report current=3,604 unique keys, baseline=3,631 unique keys, additions=21,
  removals=48, and no source-file mismatches over the same 2,579-file
  denominator. The completed failure used `user=24.47s`, `sys=5.90s`; uptime
  advanced within 13:44/up 3 days 3:57.
- Package-import predicate: exit 1 with 150 findings and 40 unregistered
  forbidden statements. Its summary and an independent longest-exact-package
  AST walk agree exactly (`reported_minus_derived=[]`,
  `derived_minus_reported=[]`) over 2,579 `*.py` files. The completed failure
  used `user=50.36s`, `sys=3.07s`; uptime advanced from 13:44/up 3 days 3:57 to
  13:45/up 3 days 3:58.
- Task-3-to-Task-4 package reconciliation: strict four-field finding identities
  move 152 -> 150 through two added summary replacements and four removals.
  The substantive removals are the Lex->DataForge import-boundary row and the
  Lex->DataForge package-boundary row; their summary counts change 103 -> 100
  deep edges and 42 -> 40 forbidden edges. The two forbidden statements
  cleared are exactly `lex.artifacts -> data_forge.kernel.artifacts` and
  `lex.types -> data_forge.domains.legal.contracts`; the Lex errors edge was a
  deep/import-boundary finding but not a separately counted package-forbidden
  statement.
