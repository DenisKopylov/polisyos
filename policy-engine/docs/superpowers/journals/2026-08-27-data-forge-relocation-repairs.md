# Data Forge relocation repairs — execution journal

## Commit-boundary widening ledger

| Commit boundary | Ledger | What the boundary bought or cleared | Standing |
| --- | ---: | --- | --- |
| `c27c6b48b` | 4/8 | Round-free repair: immutable CAS snapshot closes the receipt TOCTOU. | stands; no round consumed |
| `7e8a19abd` | 4/8 | Round-free repair: Scientist rejects producer-authored D4 predicates and waivers. | stands; no round consumed |
| `c74299e3d` | 4/8 | Round-free repair: explicit selected-contract Foundry transport and one real workflow consumer. | stands; no round consumed |
| `b6f7e395b` | 4/8 | Round-free repair: Lex compatibility edges close; frozen row 21 is amended to measured Common ownership without code movement. | stands; no round consumed |
| `24ef44ae9` | 5/8 | Round 5 buys the Scientist claim-adjudication seam and clears frozen row 3. | stands |
| `044b5f978` | 6/8 | Round 6 buys the Lex semantic-benchmark surface and clears frozen rows 4–6. | stands |
| `02b3f7896` | 7/8 | Round 7 buys the Scientist legal-retrieval diagnostic and clears frozen row 7. | stands |
| `58118c3d9` | 8/8 | Round 8 buys the Lex legal-search command and clears frozen row 8. | stands |

No round was withdrawn. The explicit baseline and registration transaction after
`58118c3d9` is record work against frozen source and consumes no widening round.

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

## Task 5 — Scientist-owned claim adjudication

### Ledger and pattern pass

- Ledger: 5/8. Round 5 buys the complete academic-claim publishability seam
  and clears frozen row 3:
  Data Forge freezes authority-neutral source bytes and claim inputs; Scientist
  admits a promoted benchmarked champion, executes candidate analysis, and
  signs the narrow publishability result. The round stands.
- Relevant patterns: P01/P02 (a real injected bridge and CLI consumer, not a
  contract-only move), P05/P15 (no producer-authored publish predicate in the
  raw batch), P10/P29 (negative end-to-end consumers), P31/P32 (one receipt
  chokepoint with content/producer/lineage verification), P35/P37 (exact input
  denominator and independently replayed champion predicates), and P38 (an
  execution result is not method-validity or governance evidence).
- Capability closure: the seam has a strict IR input/result contract, immutable
  CAS producer, explicit orchestration runner, Scientist consumer, content-bound
  result receipt, graph/conflict consumers, a supported Scientist CLI route,
  and behavioral falsifiers. The compatibility JSONL projection is explicitly
  non-authoritative.

### Authority and integrity falsifiers

- Missing or seeded-only champion blocks without a result artifact.
- Candidate/evaluation mismatch, false required guardrail, or wrong evaluation
  producer blocks admission.
- Mutating the source path after snapshot does not alter the admitted input;
  corrupting the CAS blob blocks before the model client runs.
- The serialized input contains neither `publish_to_graph` nor
  `publishable_edge`; a model-positive abstract-only claim remains blocked.
- A result receipt offered as `method_validity` is rejected.
- Graph and conflict consumers share one receipt validator. Holding the receipt
  constant while flipping the JSONL projection from false to true makes both
  consumers reject it; without a receipt, a producer-authored true flag
  publishes nothing.
- A forged result manifest with a duplicate lineage role is rejected before it
  can replace or erase the existing admitted pointer.
- The Data Forge pipeline requires an injected Scientist runner, the Data Forge
  CLI refuses direct claim authority, and the Scientist CLI exercises the real
  transport and materialization path.

### Task 5 verification boundary

- Focused behavior: exit 0, 36 tests passed; `polisyos` resolved from this
  worktree. The completed run used `user=22.54s`, `sys=1.24s`; its uptime pair
  stayed within the 14:31/up 3 days 4:44 minute.
- Changed-file Ruff: exit 0, no diagnostics (`user=0.04s`, `sys=0.01s`).
- Source import predicate: exit 1 with 47 findings, split ARCH001=44,
  ARCH002=1, ARCH004=2, ARCH006=0. The canonical report and independent AST
  census agree over 2,581 `*.py` files; the independent ordered-pair sum is 44
  and both set differences are empty. The 48 -> 47 delta clears exactly
  `data_forge.domains.academic.batch.claim_adjudicator ->
  scientist.methods.autotune.claim_adjudication`; no other rule moved. The
  completed failure used `user=0.70s`, `sys=0.19s`.
- Release guardrail predicate: exit 1 pending the authorized final explicit
  baseline transaction. Canonical diff and the independent AST derivation
  agree on current=3,610 unique edges, baseline=3,631, additions=29,
  removals=50, and zero source-file mismatches over 2,581 files. Relative to
  Task 4, eight additions entered: the two Data Forge core-facade edges, the
  Scientist CLI core/DataForge edges, and the Scientist runtime
  core-artifacts/core-canon/DataForge/IR edges. Two old-address edges left:
  Data Forge claim adjudicator -> Scientist claim adjudication, and Scientist
  claim-adjudication config -> Data Forge academic read API. The completed
  failure used `user=25.63s`, `sys=6.06s`; uptime advanced from 14:35/up 3 days
  4:49 to 14:36 in the same uptime hour.
- Package-import predicate: exit 1 with 151 findings and 39 unregistered
  forbidden statements. The report field, list length, and unique-key count
  each equal those totals; an independent longest-exact-package AST census
  also derives 39 with empty set differences over 2,581 files. The substantive
  40 -> 39 move is the same removed Data Forge -> Scientist statement. The
  150 -> 151 total is nine exact finding additions and eight removals: summary
  rows were replaced as their counts changed, and one new
  Scientist -> DataForge import-boundary summary was introduced by the real
  consumer-up bridge. No composite pass is claimed. The completed failure used
  `user=52.03s`, `sys=2.96s`; uptime advanced from 14:35/up 3 days 4:49 to
  14:36/up 3 days 4:50.

## Task 6 — Lex-owned semantic benchmark

### Ledger and pattern pass

- Ledger: 6/8. Round 6 buys one Lex semantic-readiness surface through the
  existing `polisyos.lex` facade. It clears frozen rows 4–6 together:
  NormPack assembly/transport constraints, legal graph search, and the
  `NormPackBuildRequest` consumer. The round stands.
- Relevant patterns: P01/P02 (Data Forge fixtures, supported read API, real
  injected pipeline bridge, and Lex consumer), P05/P10 (only Lex computes the
  semantic readiness receipt), P27/P31 (one owner rather than copied Lex logic
  below the boundary), P29/P38 (the pipeline runs the real Lex implementation,
  not a marker), and P35/P37 (the four-case fixture denominator is explicit).
- Data Forge now owns only the authority-neutral query fixtures and the
  still-deferred Scientist retrieval diagnostic. That diagnostic is explicitly
  `implemented_but_not_orchestrated`, carries empty `authoritative_for`, and
  names legal admissibility/publication readiness in `may_not_use_for`; Round 7
  must move its consumer. It cannot change the Lex receipt.

### Task 6 receipts

- RED: the two prescribed files failed collection because neither
  `polisyos.lex.run_legal_benchmark` nor the Data Forge fixture function
  existed.
- GREEN: the Lex benchmark preserves the report and stage-manifest paths,
  exercises graph retrieval, constraints, transport, NormPack, and legal
  quality metrics, and is consumed by the real injected Data Forge pipeline
  bridge. The Data Forge CLI fails closed instead of importing Lex.
- Public surface: the canonical renderer and the committed inventory/Markdown
  match byte-for-byte; the Lex facade has 54 exports. The module lives under
  the existing `lex.knowledge` package to avoid creating root-file/layout debt.
  The existing dynamic-import registration was narrowed to its measured line.
- Focused blast radius: exit 0, 23 tests passed, including Lex/Data Forge
  benchmark behavior, pipeline/CLI integration, and public-facade inventory.
  The measured run used `user=2.38s`, `sys=0.32s`; uptime remained within
  15:01/up 3 days 5:14. Changed-file Ruff exited 0 with no diagnostics
  (`user=0.02s`, `sys=0.01s`).
- Source import predicate: exit 1 with 44 findings, split ARCH001=41,
  ARCH002=1, ARCH004=2, ARCH006=0. Canonical and independent AST derivations
  agree over 2,583 `*.py` files; the ordered-pair sum is 41 and both set
  differences are empty. The exact 47 -> 44 delta is the three frozen
  Data Forge -> Lex statements in `legal.batch.benchmark`; no other rule moved.
  The completed failure used `user=0.65s`, `sys=0.17s`; uptime stayed within
  14:58/up 3 days 5:11.
- Release guardrail predicate: exit 1 pending the final authorized baseline
  transaction. Canonical and independent sets agree on current=3,605,
  baseline=3,631, additions=29, removals=55, and no source-file mismatch over
  2,583 files. Relative to Task 5, additions are unchanged and exactly five old
  addresses were removed: Data Forge benchmark -> core artifact store, Fabric
  claim persistence, Lex API, Lex graph search, and Lex types. The completed
  failure used `user=26.54s`, `sys=5.96s`; uptime stayed within 14:58/up 3 days
  5:11.
- Package-import predicate: exit 1 with 151 findings and 36 unregistered
  forbidden statements. The report field, list length, unique-key count, and
  independent longest-exact-package AST derivation agree; both set differences
  are empty over 2,583 files. The unchanged 151 total is two summary-row
  replacements in each direction, while the substantive forbidden denominator
  moves 39 -> 36 by exactly the three Data Forge -> Lex statements. The
  completed failure used `user=52.96s`, `sys=3.00s`; uptime advanced from
  14:58/up 3 days 5:11 to 14:59/up 3 days 5:12. No composite pass is claimed.

## Task 7 — Scientist-owned legal retrieval diagnostic

### Ledger and pattern pass

- Ledger: 7/8. Round 7 buys the Scientist legal-retrieval evaluation surface
  and its real injected orchestration bridge. It clears frozen row 7. The
  round stands.
- Relevant patterns: P01/P02 (Data Forge fixtures, Lex receipt, Scientist
  consumer, and the existing pipeline bridge are all exercised), P05/P15 (the
  diagnostic has no authority slot), P29/P32 (the bridge reads and
  content-binds the real Lex receipt rather than trusting an outcome object),
  P35/P37 (all four declared fixtures are evaluated), and P38 (retrieval score
  is not the Lex semantic property).
- The Scientist outcome publishes empty `authoritative_for`, explicitly denies
  legal admissibility, publication readiness, governance admissibility, and
  method validity, and rejects every attempted authority use. Data Forge now
  retains only its authority-neutral fixture compatibility access; no
  Scientist import remains below the ownership boundary.

### Task 7 receipts

- RED: the prescribed files failed collection because the approved
  `ScientistLegalBenchmarkRunner` surface did not exist (`user=1.27s`,
  `sys=0.21s`; uptime 15:05/up 3 days 5:18).
- GREEN: exit 0, 8 focused tests passed. A deliberately perfect retrieval
  result remains red when the content-bound Lex receipt fails NormPack; a Lex
  result object that disagrees with its persisted receipt is rejected; and the
  Data Forge pipeline consumes the Scientist runner. `polisyos` resolved from
  this worktree. The completed run used `user=1.82s`, `sys=0.26s`; uptime
  stayed within 15:14/up 3 days 5:27.
- Public surface and dynamic registry: the canonical inventory and Markdown
  renderer match byte-for-byte with all 8 generated families and 20 Scientist
  exports. The dynamic call registration matches the measured facade call at
  line 96. Changed-Python Ruff exits 0 with no diagnostics (`user=0.02s`,
  `sys=0.01s`). A preceding attempt that accidentally included Markdown was a
  harness non-receipt and is not a product diagnostic.
- Source import predicate: exit 1 with 43 findings, split ARCH001=40,
  ARCH002=1, ARCH004=2, ARCH006=0. Canonical JSON and an independent AST walk
  agree exactly over 2,584 `src/**/*.py` files with empty set differences. The
  exact 44 -> 43 delta is frozen row 7,
  `data_forge.domains.legal.batch.benchmark ->
  scientist.agent.knowledge_tools`; no other rule moved. The completed failure
  used `user=0.60s`, `sys=0.19s`; uptime stayed within 15:14/up 3 days 5:27.
- Release guardrail predicate: exit 1 only for the authorized final baseline
  transaction. Canonical and independent AST sets agree over the same 2,584
  files on current=3,604, baseline=3,631, additions=29, removals=56, with empty
  differences. Relative to Task 6, additions are unchanged and the old Data
  Forge benchmark -> Scientist toolkit address is the sole extra removal. The
  completed failure used `user=24.45s`, `sys=5.85s`; uptime stayed within
  15:15/up 3 days 5:28.
- Package-import predicate: exit 1 with 148 findings and 35 unregistered
  forbidden statements. The report field, list length, and strict finding-key
  uniqueness all equal 148; canonical and independent longest-exact-package
  AST sets both derive 35 forbidden statements with empty differences over
  2,584 files. The substantive 36 -> 35 move is exactly frozen row 7. The live
  finding-total receipts disagree with the tracked-state replay: Task 6
  recorded 151 and Task 7 records 148, while an archive replay without `.git`
  emitted git non-receipts and derived 149 for Task 6; its usable strict diff
  is one added count-summary identity and two removals (the prior count-summary
  identity and the Data Forge -> Scientist package row), net -1. The remaining
  two-count live delta is therefore reported as environment-sensitive and
  `not_established`, not silently assigned to this move. The completed gate
  failure used `user=51.79s`, `sys=3.30s`; uptime advanced from 15:16/up 3 days
  5:29 to 15:17/up 3 days 5:30. No composite pass is claimed.

## Task 8 — Lex-owned legal search command

### Ledger and pattern pass

- Ledger: 8/8. Round 8 buys the supported
  `polisyos.lex.knowledge.search_legal_knowledge` surface and its module CLI;
  it clears frozen row 8. The round stands. No repair was skipped or thinned,
  and the widening ceiling is now binding.
- Relevant patterns: P01/P02 (a real callable and command consumer rather than
  an import-only move), P05 (the route is read-only and restricts retrieval to
  `grounded_fact`), P27/P31 (Lex is the single store/search owner and closes the
  store on success or failure), and P29 (behavioral query, serialization, and
  failure-path tests rather than marker checks).
- Data Forge retains its build CLI but refuses the old interactive-search
  command with the Lex-owned replacement named explicitly. It does not import
  or proxy `LegalKnowledgeStore`.

### Task 8 receipts

- RED: the two prescribed files failed collection at exit 2 because
  `polisyos.lex.knowledge.search_legal_knowledge` did not exist
  (`user=1.99s`, `sys=0.32s`).
- GREEN: exit 0, 12 focused tests passed. The Lex route fixes
  `trust_tier="grounded_fact"`, preserves `top_k`, emits one sorted JSON object
  per typed result, and closes the store when the query raises. The Data Forge
  refusal falsifier also passed. A fresh boundary rerun used `user=3.34s`,
  `sys=0.52s`; uptime advanced from 15:49/up 3 days 6:02 to 15:49/up 3 days
  6:03.
- Changed-file Ruff: exit 0 with no diagnostics (`user=0.07s`, `sys=0.03s`).
  The public-surface renderer found eight generated-artifact families and
  matched both governed files byte-for-byte; Lex remains at 54 root exports
  and `polisyos.lex.knowledge` has 11 exports including the new callable.
- Source import predicate: exit 1 with 42 findings, split ARCH001=39,
  ARCH002=1, ARCH004=2, ARCH006=0. The canonical report and an independent AST
  walk agree exactly over 2,585 `src/**/*.py` files with empty set differences;
  the independent ordered-pair sum is 39. The exact 43 -> 42 delta clears
  frozen row 8, `data_forge.domains.legal.batch.cli ->
  lex.knowledge.store`; no other rule moved. The completed direct failure used
  `user=1.02s`, `sys=0.30s`; uptime stayed within 15:50/up 3 days 6:04. A
  preceding wrapper used zsh's reserved `status` variable after the linter
  completed and is rejected as a harness non-receipt.
- Release guardrail predicate: exit 1 pending the authorized final explicit
  baseline transaction. Canonical and independent AST sets agree on
  current=3,603, baseline=3,631, additions=29, removals=57, and zero
  source-file mismatches over the same 2,585 files. Relative to Task 7, the
  sole extra removal is the old Data Forge CLI -> Lex store address; additions
  remain unchanged. The trustworthy direct run used `user=41.32s`,
  `sys=9.27s`; uptime advanced from 15:40/up 3 days 5:53 to 15:41/up 3 days
  5:54. An earlier wrapper lost its session identifier and is a harness
  non-receipt.
- Package-import predicate: exit 1 with 145 findings and 34 unregistered
  forbidden statements. The report field, list length, and strict finding-key
  uniqueness agree on 145; the canonical package scan and an independent
  longest-exact-package AST walk agree on all 34 forbidden statements with
  empty set differences over 2,585 files. The Data Forge -> Lex package row is
  absent. The direct failure used `user=90.40s`, `sys=5.01s`; uptime advanced
  from 15:41/up 3 days 5:54 to 15:43/up 3 days 5:56. The substantive forbidden
  denominator moves 35 -> 34 by frozen row 8; the report total also loses the
  corresponding deep-import identity and the corrected stale exact dynamic
  coordinate, explaining the direct 148 -> 145 movement without presenting
  the full gate as passing.

## Final baseline and registration transaction

### Ledger and denominator

- Ledger: **8/8**. This transaction consumes no widening round: source was frozen at
  `58118c3d9`; only the architect-authorized explicit baseline and required records moved.
- Before the patch, canonical and independent full-set derivations agreed over 2,585
  `src/**/*.py` files: current 3,603 unique edges, baseline 3,631 unique edges,
  **29 additions** and **57 removals**, with zero source-file mismatches. After the
  explicit patch, both derive current=baseline=3,603, additions=0, removals=0.
- The patch was applied as explicit edge hunks. `guardrails sync` was never invoked.

### Enumerated additions (29)

| Added edge | Causing statement | Authorization receipt |
| --- | --- | --- |
| `polisyos.data_forge.domains.academic.batch.benchmark->polisyos.ir.analytics.cross_graph` | `src/polisyos/data_forge/domains/academic/batch/benchmark.py:19` — `from polisyos.ir.analytics.cross_graph import AcademicBenchmarkScenario, AcademicBenchmarkSuite, BenchmarkCausalEdge, BenchmarkCredibilityPolicy, BenchmarkScholarQuery, load_benchmark_suite, write_need_backlog` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.data_forge.domains.academic.batch.best_snapshot->polisyos.ir.analytics.cross_graph` | `src/polisyos/data_forge/domains/academic/batch/best_snapshot.py:31` — `from polisyos.ir.analytics.cross_graph import AcademicBenchmarkSuite, load_benchmark_suite` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.data_forge.domains.academic.batch.claim_adjudicator->polisyos.core.artifacts` | `src/polisyos/data_forge/domains/academic/batch/claim_adjudicator.py:14` — `from polisyos.core.artifacts import ArtifactID, ArtifactRef, ArtifactWriteOptions, FileSystemCAS, InputRef, ProducerInfo, SchemaInfo` | Round 5 claim-adjudication seam, `24ef44ae9` |
| `polisyos.data_forge.domains.academic.batch.claim_adjudicator->polisyos.core.canon` | `src/polisyos/data_forge/domains/academic/batch/claim_adjudicator.py:23` — `from polisyos.core.canon import CanonSpec, from_canonical_bytes` | Round 5 claim-adjudication seam, `24ef44ae9` |
| `polisyos.data_forge.domains.legal.batch.doc_identity->polisyos.common.timestamps` | `src/polisyos/data_forge/domains/legal/batch/doc_identity.py:11` — `from polisyos.common.timestamps import parse_iso_date` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.data_forge.domains.legal.batch.temporal_parser->polisyos.common.timestamps` | `src/polisyos/data_forge/domains/legal/batch/temporal_parser.py:9` — `from polisyos.common.timestamps import parse_iso_date` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.data_forge.domains.legal.contracts->polisyos.fabric.docs` | `src/polisyos/data_forge/domains/legal/contracts.py:18` — `from polisyos.fabric.docs import DocChunkOptions, DocIngestOptions, DocNormalizeOptions, DocStructureOptions` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.data_forge.domains.legal.contracts->polisyos.ir.loading.fact_log` | `src/polisyos/data_forge/domains/legal/contracts.py:24` — `from polisyos.ir.loading.fact_log import FactSegmentManifest` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.data_forge.domains.legal.corpus.versioning->polisyos.common.timestamps` | `src/polisyos/data_forge/domains/legal/corpus/versioning.py:14` — `from polisyos.common.timestamps import latest_object_by_subject, parse_iso_date` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.data_forge.domains.ukraine.builders.sources->polisyos.ir.kernel.slots` | `src/polisyos/data_forge/domains/ukraine/builders/sources.py:15` — `from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY, build_slot_family_manifest` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.data_forge.errors->polisyos.core.errors` | `src/polisyos/data_forge/errors.py:7` — `from polisyos.core.errors import ErrorCategory, PolicyOSError` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.data_forge.kernel.artifacts->polisyos.core.artifacts.ids` | `src/polisyos/data_forge/kernel/artifacts.py:10` — `from polisyos.core.artifacts.ids import ArtifactID` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.data_forge.kernel.artifacts->polisyos.core.artifacts.store` | `src/polisyos/data_forge/kernel/artifacts.py:19` — `from polisyos.core.artifacts.store import FileSystemCAS` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.data_forge.kernel.artifacts->polisyos.core.canon` | `src/polisyos/data_forge/kernel/artifacts.py:11` — `from polisyos.core.canon import from_canonical_bytes` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.data_forge.kernel.artifacts->polisyos.fabric.world` | `src/polisyos/data_forge/kernel/artifacts.py:13` — `from polisyos.fabric.world import validate_doc_meta_ids` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.data_forge.kernel.artifacts->polisyos.ir.world.doc` | `src/polisyos/data_forge/kernel/artifacts.py:14` — `from polisyos.ir.world.doc import DocMeta` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.foundry.data_plane.bindings->polisyos.common.serialization` | `src/polisyos/foundry/data_plane/bindings.py:23` — `from polisyos.common.serialization import to_python_data` | round-free Foundry repair, `c74299e3d` |
| `polisyos.lex.common->polisyos.common.timestamps` | `src/polisyos/lex/common.py:7` — `from polisyos.common.timestamps import latest_object_by_subject, parse_iso_date` | shared-contract-down relocation, no round, `ad2526a42` |
| `polisyos.runtime.quality.data_state_substrate->polisyos.fabric.world` | `src/polisyos/runtime/quality/data_state_substrate.py:1248` — `from polisyos.fabric.world import ensure_world_schema` | Phase 0 ratified re-spelling, `1ceb10e0c` |
| `polisyos.scientist.governance.blueprint_release->polisyos.core.canon` | `src/polisyos/scientist/governance/blueprint_release.py:24` — `from polisyos.core.canon import CanonSpec` | Round 3 Scientist governance bridge, `a1f0d4bdf` |
| `polisyos.scientist.governance.blueprint_release->polisyos.ir.analytics.calibration` | `src/polisyos/scientist/governance/blueprint_release.py:41` — `from polisyos.ir.analytics.calibration import CalibrationCandidateScore, CalibrationRunManifest, HoldoutScoresManifest, SpecificationCurveScenario, SpecificationCurveSummaryManifest, SplitWindow, StrategicResponseChannelMetric, StrategicResponseMetricsManifest, TransportabilityChannelResult, TransportabilitySummaryManifest` | Round 3 Scientist governance bridge, `a1f0d4bdf` |
| `polisyos.scientist.governance.blueprint_release->polisyos.ir.registry.refs` | `src/polisyos/scientist/governance/blueprint_release.py:71` — `from polisyos.ir.registry.refs import ArtifactRefModel` | Round 3 Scientist governance bridge, `a1f0d4bdf` |
| `polisyos.scientist.methods.autotune.claim_adjudication_cli->polisyos.core.artifacts` | `src/polisyos/scientist/methods/autotune/claim_adjudication_cli.py:11` — `from polisyos.core.artifacts import FileSystemCAS` | Round 5 claim-adjudication seam, `24ef44ae9` |
| `polisyos.scientist.methods.autotune.claim_adjudication_cli->polisyos.data_forge.read_api.academic` | `src/polisyos/scientist/methods/autotune/claim_adjudication_cli.py:20` — `from polisyos.data_forge.read_api.academic import AcademicBatchConfig` | Round 5 claim-adjudication seam, `24ef44ae9` |
| `polisyos.scientist.methods.autotune.claim_adjudication_runtime->polisyos.core.artifacts` | `src/polisyos/scientist/methods/autotune/claim_adjudication_runtime.py:11` — `from polisyos.core.artifacts import ArtifactRef, ArtifactWriteOptions, FileSystemCAS, InputRef, ProducerInfo, SchemaInfo` | Round 5 claim-adjudication seam, `24ef44ae9` |
| `polisyos.scientist.methods.autotune.claim_adjudication_runtime->polisyos.core.canon` | `src/polisyos/scientist/methods/autotune/claim_adjudication_runtime.py:19` — `from polisyos.core.canon import CanonSpec, from_canonical_bytes` | Round 5 claim-adjudication seam, `24ef44ae9` |
| `polisyos.scientist.methods.autotune.claim_adjudication_runtime->polisyos.data_forge.read_api.academic` | `src/polisyos/scientist/methods/autotune/claim_adjudication_runtime.py:46` — `from polisyos.data_forge.read_api.academic import AcademicBatchConfig` | Round 5 claim-adjudication seam, `24ef44ae9` |
| `polisyos.scientist.methods.autotune.claim_adjudication_runtime->polisyos.ir.analytics.literature` | `src/polisyos/scientist/methods/autotune/claim_adjudication_runtime.py:20` — `from polisyos.ir.analytics.literature import AdmittedClaimAdjudicationBatch, CausalCredibility, ClaimAdjudicationInputBatch, ClaimAdjudicationInputItem, ClaimAdjudicationResult, ClaimType, DesignFamily, RiskOfBias, SourceBasis, SupportStatus` | Round 5 claim-adjudication seam, `24ef44ae9` |
| `polisyos.scientist.nodes.builtins.data.bind_foundry_inputs->polisyos.foundry.methods` | `src/polisyos/scientist/nodes/builtins/data/bind_foundry_inputs.py:21` — `from polisyos.foundry.methods import MethodRegistry, ensure_all_methods_registered` | round-free Foundry repair, `c74299e3d` |

The three Round-3 Scientist edges are cited individually above; none is inferred from
a category label. Each addition is the same dependency at its relocated address, or the
already-accounted authority seam named in its receipt; no untraced edge was admitted.

### Enumerated removals (57)

- `polisyos.data_forge.domains.academic.batch.benchmark->polisyos.scientist.cross_graph.feedback`
- `polisyos.data_forge.domains.academic.batch.best_snapshot->polisyos.scientist.cross_graph.feedback`
- `polisyos.data_forge.domains.academic.batch.claim_adjudicator->polisyos.scientist.methods.autotune.claim_adjudication`
- `polisyos.data_forge.domains.legal.batch.benchmark->polisyos.core.artifacts.store`
- `polisyos.data_forge.domains.legal.batch.benchmark->polisyos.fabric.claims.persist`
- `polisyos.data_forge.domains.legal.batch.benchmark->polisyos.lex.api`
- `polisyos.data_forge.domains.legal.batch.benchmark->polisyos.lex.knowledge.search`
- `polisyos.data_forge.domains.legal.batch.benchmark->polisyos.lex.types`
- `polisyos.data_forge.domains.legal.batch.benchmark->polisyos.scientist.agent.knowledge_tools`
- `polisyos.data_forge.domains.legal.batch.cli->polisyos.lex.knowledge.store`
- `polisyos.data_forge.domains.legal.batch.doc_identity->polisyos.lex.common`
- `polisyos.data_forge.domains.legal.batch.structurer->polisyos.lex.types`
- `polisyos.data_forge.domains.legal.batch.temporal_parser->polisyos.lex.common`
- `polisyos.data_forge.domains.legal.corpus.index->polisyos.lex.artifacts`
- `polisyos.data_forge.domains.legal.corpus.index->polisyos.lex.errors`
- `polisyos.data_forge.domains.legal.corpus.ingest->polisyos.lex.artifacts`
- `polisyos.data_forge.domains.legal.corpus.ingest->polisyos.lex.errors`
- `polisyos.data_forge.domains.legal.corpus.ingest->polisyos.lex.types`
- `polisyos.data_forge.domains.legal.corpus.structure->polisyos.lex.artifacts`
- `polisyos.data_forge.domains.legal.corpus.structure->polisyos.lex.errors`
- `polisyos.data_forge.domains.legal.corpus.structure->polisyos.lex.types`
- `polisyos.data_forge.domains.legal.corpus.versioning->polisyos.lex.artifacts`
- `polisyos.data_forge.domains.legal.corpus.versioning->polisyos.lex.common`
- `polisyos.data_forge.domains.legal.corpus.versioning->polisyos.lex.errors`
- `polisyos.data_forge.domains.legal.corpus.versioning->polisyos.lex.factlog`
- `polisyos.data_forge.domains.legal.corpus.versioning->polisyos.lex.types`
- `polisyos.data_forge.domains.ukraine.builders.calibration->polisyos.core.artifacts.manifest`
- `polisyos.data_forge.domains.ukraine.builders.calibration->polisyos.ir.observation.contracts`
- `polisyos.data_forge.domains.ukraine.builders.calibration->polisyos.scientist.governance`
- `polisyos.data_forge.domains.ukraine.builders.demography->polisyos.foundry.methods.catalog.microsim.protocols`
- `polisyos.data_forge.domains.ukraine.builders.release->polisyos.foundry.validation.release_acceptance`
- `polisyos.data_forge.domains.ukraine.builders.release->polisyos.ir.governance.policy_spec`
- `polisyos.data_forge.domains.ukraine.builders.release->polisyos.ir.governance.problem_frame`
- `polisyos.data_forge.domains.ukraine.builders.release->polisyos.ir.governance.schedule`
- `polisyos.data_forge.domains.ukraine.builders.release->polisyos.ir.governance.selector_expr`
- `polisyos.data_forge.domains.ukraine.builders.release->polisyos.ir.model_layer.model_spec`
- `polisyos.data_forge.domains.ukraine.builders.release->polisyos.ir.model_layer.types`
- `polisyos.data_forge.domains.ukraine.builders.release->polisyos.ir.observation.contracts`
- `polisyos.data_forge.domains.ukraine.builders.release->polisyos.ir.trinity`
- `polisyos.data_forge.domains.ukraine.builders.release->polisyos.lex.interventions`
- `polisyos.data_forge.domains.ukraine.builders.release->polisyos.scientist.governance`
- `polisyos.data_forge.domains.ukraine.builders.sources->polisyos.core.registry`
- `polisyos.data_forge.domains.ukraine.builders.sources->polisyos.foundry.data_plane.bindings`
- `polisyos.data_forge.domains.ukraine.builders.sources->polisyos.foundry.methods.catalog.causal.measurement_error`
- `polisyos.data_forge.domains.ukraine.builders.sources->polisyos.foundry.methods.catalog.causal.protocols`
- `polisyos.data_forge.domains.ukraine.builders.sources->polisyos.foundry.methods.catalog.econometrics.protocols`
- `polisyos.data_forge.domains.ukraine.builders.sources->polisyos.foundry.methods.catalog.microsim.protocols`
- `polisyos.data_forge.domains.ukraine.builders.sources->polisyos.foundry.methods.catalog.ml.protocols`
- `polisyos.data_forge.domains.ukraine.builders.sources->polisyos.foundry.methods.catalog.network.protocols`
- `polisyos.data_forge.domains.ukraine.builders.sources->polisyos.foundry.methods.layout`
- `polisyos.data_forge.domains.ukraine.builders.sources->polisyos.ir.analytics.causal_graph`
- `polisyos.data_forge.domains.ukraine.builders.sources->polisyos.ir.kernel`
- `polisyos.lex.common->polisyos.common.logger`
- `polisyos.runtime.quality.data_state_substrate->polisyos.fabric.world.materialize`
- `polisyos.runtime.quality.generation_cycle->polisyos.pdc._impl.layer2_design_search`
- `polisyos.scientist.governance.blueprint_release->polisyos.ir.observation.contract_compilers`
- `polisyos.scientist.methods.autotune.claim_adjudication->polisyos.data_forge.read_api.academic`

### Executed registration signals

- `fabric-world-facade-enforcement-conflict`: diagnostic exit 1 with the requested
  witness present. ARCH004 names `polisyos.fabric.world` as the facade; that facade exports
  `ensure_world_schema`; Runtime imports it there at the architect-requested Phase-0
  re-spelling; and the canonical deep collector counts the exact same module as depth.
- `foundry-ukraine-method-contract-consumer-residual`: the real CAS intake and
  independent AST derivation agree on 13 unique contracts = one exercised
  (`d2_panel_observational`) + twelve `selectable_unselected / consumer_missing`.
  The execution-as-method-validity falsifier passed; an execution result is rejected.
- `data-forge-relocation-ruff-inheritance`: the same Ruff binary against current and an
  archived `9300a06e9` tree produced three identical diagnostics per tree (six
  observations), codes ANN001/RUF001/RUF022, symmetric identity difference zero; both
  files are byte-unchanged from the slice base. A temp-path/config probe that reported
  17 per tree changed per-file rule matching and is recorded as a harness non-receipt.

### Release predicate receipt

- The post-patch release guardrail completed at exit 0. Canonical bytes exactly match
  the explicitly patched baseline, all 3,603 keys are unique, and the independent AST
  derivation reports additions=0, removals=0. The completed guardrail used
  `user=47.89s`, `sys=11.75s`; uptime advanced from 16:08/up 3 days 6:21 to
  16:09/up 3 days 6:22.
- The generated debt-ledger writer observed 99 register ids and wrote the derived ledger,
  but its direct exit is 1 on ten unresolvable closure-test identities. Their provenance
  was not established by an exact slice-base replay, so no inheritance claim is made;
  the identities and the 439.85s receipt are preserved rather than presented as a green
  records gate. They do not alter any of the three requested import predicates.

## Final verification boundary

- Branch receipt: `git rev-parse --show-prefix` returned `policy-engine/`, and
  `git symbolic-ref -q HEAD` returned
  `refs/heads/codex/import-relocate-data-forge` before the final commands.
- Blast-radius tests: the 28 changed test files since `9300a06e9`, excluding the
  separately replayed debt-ledger checker, passed at exit 0. The worktree import
  resolved to this checkout. Two complete collection derivations agree on **144**
  tests: per-file counts sum to 144, while a separate `len(session.items)` collector
  reports 144 items / 144 unique node ids. The execution used `user=113.59s`,
  `sys=10.46s`; uptime advanced from 16:21/up 3 days 6:34 to 16:23/up 3 days 6:37.
  An initial parser returned zero because this repository's quiet formatter emits
  `file.py: count` rather than node ids; that parser result is a non-receipt.
- Debt-ledger invariants: the two exact real-register tests passed at exit 0
  (`user=367.92s`, `sys=20.54s`; uptime 16:26/up 3 days 6:39 to
  16:33/up 3 days 6:46). Canonical and independent complete A:G register censuses
  agree on 99 unique ids and status distribution `ambiguous=12`, `blocked=10`,
  `closed=37`, `folded=2`, `foreign=6`, `open=32`; the generated ledger indexes 62.
  A naive Markdown parser counted 110 rows / 101 unique ids because it failed to end
  section state and included later evidence tables. That disagreement is preserved as
  a failed derivation, not reconciled into the denominator. After the final prose-only
  precision edits, the exact generated-ledger snapshot test replayed at exit 0
  (`user=1.22s`, `sys=0.33s`).
- Ruff: all 75 changed Python files passed at exit 0 (`user=0.04s`, `sys=0.01s`).
  A first replay passed repository-root paths from a `policy-engine/` working directory
  and emitted only E902 missing-file diagnostics; it is a harness non-receipt. The
  separate equal-tree comparison remains three identical inherited diagnostics per
  tree, six observations and three normalized identities, codes
  ANN001/RUF001/RUF022, with symmetric difference zero.

### Final import predicates — reported separately

1. **Source import linter: exit 1.** The complete JSON and independent exact-root AST
   walk agree over 2,585 `src/**/*.py` files on **42** violations:
   ARCH001=39, ARCH002=1, ARCH004=2, ARCH006=0. The independent ARCH001 ordered-pair
   sum is 39: core→scientist 4, foundry→lex 1, foundry→scientist 5, ir→core 2,
   ir→foundry 13, ir→scientist 6, lex→foundry 3, lex→scientist 4,
   runtime→corpus 1. Both set differences are empty. The completed failure used
   `user=1.75s`, `sys=0.47s`; uptime remained within 16:27/up 3 days 6:40.
2. **Release guardrail: exit 0.** The canonical checker reports fresh generated
   artifacts and `Architecture guardrail check passed`. A standalone AST derivation
   over the same 2,585-file denominator agrees on current=3,603 unique keys,
   baseline=3,603 entries / 3,603 unique keys, additions=0, removals=0, and zero
   source-file mismatches. The final completed run used `user=40.24s`, `sys=9.66s`;
   uptime advanced from 16:39/up 3 days 6:52 to 16:40/up 3 days 6:53.
3. **Package-import gate: exit 1.** Three complete-report derivations agree on
   **134** findings (`finding_count`, list length, and 134 unique serialized finding
   dicts). Its `package_boundary` summary remains `mode=fail_closed`, with
   current=34, registered=0, and **34 unregistered forbidden edges**. Count field,
   key-list length, unique-key count, and eight package-row subtotals all agree; an
   independent longest-exact-registered-prefix AST scan over 2,585 files derives the
   same 34 with both set differences empty. The completed failure used
   `user=154.38s`, `sys=10.09s`; uptime advanced from 16:27/up 3 days 6:41 to
   16:31/up 3 days 6:44. No composite pass is claimed.
