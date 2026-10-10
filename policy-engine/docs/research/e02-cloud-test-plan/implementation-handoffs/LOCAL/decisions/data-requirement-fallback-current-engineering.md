# Data-requirement fallback: current engineering decision

Date: 2026-10-10  
Candidate: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`

## Decision

Keep `POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED` default-off and do not retire its implementation or close its shim yet. It is still callable from current producer/API paths, and its own Phase 7 removal triggers do not have current run evidence. The row is overdue, but a date change alone would not close it.

Treat the flag-gated claim-ledger heuristic and the scenario-family compatibility path as two distinct branches in the same broader legacy-family bridge. Removing `_required_data_families_from_heuristic` alone would leave the `compile_for_scenario` grammar-failure fallback and the production-quality scenario loader’s family projection. Either preserve that latter path as an explicit, tested compatibility-only residual or widen the eventual migration to cover its actual producer, loader, and source-contract consumer chain. Do not report a full strangle from deleting or hiding only the flag branch.

This is an engineering disposition, not a claim that the active environment has the flag enabled or that scenario-family strings independently grant authority. The environment used by a production process was not inspected. No fallback source or lifecycle record was changed in this assessment.

## Two live paths and their consumers

`src/polisyos/data_requirement/compiler.py` @ `68e673a7d190dcfde52af21dbe1ca3ab8ce85190c3690cbf63ec13f56728cd98` defines the flag parser at lines 153–158. It defaults to `false`; only `1`, `true`, `yes`, and `on` enable it. In `compile_for_claim_ledger` at lines 269–304, resolver-derived family rules take precedence. Only when those rules are empty and the flag is enabled does the compiler call `_required_data_families_from_heuristic`; the report labels those specs with `family_derivation="legacy_heuristic_fallback"`. The heuristic inspects facet values, claim text and metadata values, and the scenario id (lines 1078–1154). This default-off branch remains reachable by an explicit process environment value.

The scenario adapter has a separate path. `compile_for_scenario` calls `_compile_from_legacy_scenario_fallback` when Policy Grammar returns no facets (lines 416–447). That method accepts `expected_evidence_contract.admissible_data_source_families`, or defaults to `production_data`, then emits minimal specs tagged with `fallback="legacy_scenario_contract_when_universal_grammar_blocked"` and `missing_capability_label="bridge_missing"` (lines 502–535). This branch does not consult the environment flag.

That branch is exercised by a current tool/runtime composition, not just by a test. `normalize_scenario_evidence_contract` invokes a resolver-free compiler and projects legacy families at `src/polisyos/runtime/quality/scenario_evidence_contract.py:156–195`; `tools/ops_runners/runtime/quality_scenarios.py:200–256` calls it while serving `load_quality_scenario_contract`. Current consumers include:

- `tools/quality/validation/check_production_data_scenario_contracts.py:102` and `tools/quality/testing/local_prod_debug_probe.py:1280`;
- `tools/ops_runners/runtime/local_production_canary.py:2529`;
- `tools/quality/validation/build_policy_design_case_pass2_diagnostics.py:1926`, `build_policy_design_case_wave35a.py:120`, `build_policy_design_case_wave35b.py:403`, and `build_wave5_honest_diagnostics_evidence.py:79`.

The runtime N7 path at `src/polisyos/runtime/quality/generation_cycle.py:6496–6544` gives a typed gap, explicit requirement rows (including an explicit empty tuple), and runtime hints precedence before compiling a scenario. It composes an injected resolver or a governed fixture where available (`:6546–6577`). If compilation reaches a claim ledger with no resolver-derived family rules, the flag can affect its output. The W12.D producer tool has a separate call at `tools/quality/validation/run_universal_outcome_corpus.py:8249–8284`; it supplies the capability-index resolver when the index path is present. `src/polisyos/runtime/quality/workspace/foundry_consumption.py:1081` calls `compile_obligation_basis`, a distinct typed path rather than this heuristic.

The compiler is exported through `polisyos.data_requirement` (`src/polisyos/data_requirement/__init__.py:28–75`), including `DataRequirementCompiler` and `compile_data_requirements_for_scenario`. The wrapper constructs a resolver-free compiler (`compiler.py:547–552`). Current tests separately show the flag disabled, enabled, and disabled for claim-text inference: `tests/unit/data_requirement/test_compiler.py:225–242, 434–478, 481–520`. Those focused tests passed in the existing receipt `LOCAL/decisions/raw/dx0-data-requirement-fallback-tests.log` @ `1645e5c1a2d93528ce8125dd5dd42385a160c52ec625f40a7131a8ea146dd6eb` (3 passed, 2 warnings, 5.12s). They establish local branch behavior, not end-to-end non-authority or Phase 4/7 closure.

### Source census

The current static census walked every Python file under `src`, `tools`, and `tests`: 6,141 `.py` files parsed with zero syntax errors. The AST scan found 87 calls to the named compiler, scenario-loader, and binding APIs; its complete non-test call list is printed below. This is a source/test denominator, not a claim about external installed callers or dynamically resolved callbacks.

```text
src/polisyos/data_requirement/compiler.py:297, 492, 552
src/polisyos/runtime/quality/generation_cycle.py:6528
src/polisyos/runtime/quality/scenario_evidence_contract.py:187
src/polisyos/runtime/http/services/control/production_data.py:179
src/polisyos/runtime/quality/workspace/foundry_consumption.py:1081 (compile_obligation_basis; distinct path)
tools/quality/testing/local_prod_debug_probe.py:1280
tools/quality/validation/build_policy_design_case_pass2_diagnostics.py:1926
tools/quality/validation/build_policy_design_case_wave35a.py:120
tools/quality/validation/run_universal_outcome_corpus.py:8274
tools/quality/validation/build_policy_design_case_wave35b.py:403
tools/quality/validation/build_wave5_honest_diagnostics_evidence.py:79
tools/quality/validation/check_production_data_scenario_contracts.py:102, 127
tools/ops_runners/runtime/quality_scenarios.py:253
tools/ops_runners/runtime/local_production_canary.py:2529
```

The census recipe is reproduced here rather than retaining another derived inventory beside the source:

```python
import ast
from pathlib import Path

roots = [Path("src"), Path("tools"), Path("tests")]
files = [path for root in roots for path in root.rglob("*.py") if path.is_file()]
needles = {
    "DataRequirementCompiler", "compile_for_scenario", "compile_for_claim_ledger",
    "compile_data_requirements_for_scenario", "_required_data_families_from_heuristic",
    "normalize_scenario_evidence_contract", "load_quality_scenario_contract",
    "build_scenario_binding_report", "evaluate_source_family_binding",
    "compile_obligation_basis",
}
hits = []
parse_errors = []
parsed = 0
for path in files:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        parse_errors.append((path, type(exc).__name__))
        continue
    parsed += 1
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else (
            func.attr if isinstance(func, ast.Attribute) else ""
        )
        if name in needles:
            hits.append((path, node.lineno, name))
print(f"roots=src,tools,tests; denominator={len(files)} .py; parsed={parsed}; parse_errors={len(parse_errors)}; call_hits={len(hits)}")
for path, line, name in hits:
    if not str(path).startswith("tests/"):
        print(f"{path}:{line}: {name}")
```

The full product-tree `rg --files -g '*.py'` inventory also includes research evidence copies of old source and 18 syntactically invalid pre/postimage snapshots under `docs/research`; those are not active product callers and are excluded from the source/test caller denominator. A prior local note, `LOCAL/decisions/dx0-jax-order-and-data-requirement-fallback-20261010.md`, said no in-tree caller of the exported normalizer had been found. The AST walk above corrects that: the normalizer is called through the scenario loader and its tool consumers.

## Consumer boundary and remaining semantics question

The compatibility function `evaluate_source_family_binding` explicitly returns `status="compatibility_projection_only"` and `authority_granted=False` for a same-family match (`scenario_evidence_contract.py:330–372`). The `ProductionDataContractIndex` envelope also excludes scenario-family and source-family authority (`production_data_contract_index.py:390–403, 1401–1421`). A family label by itself therefore is not the implemented authority proof.

There is still a consumer-side question that the current source/test set does not settle for Phase 7’s stronger wording. `ProductionDataContractIndex.bind_requirement` filters candidate rows by `source_family == expected_family` before checking required facets, quality facets, limitations, and `source_contract_validation.status == "pass"`; only then does it return `status="satisfied"` and `binding_status="selected"` (`production_data_contract_index.py:441–557`). The code labels the overall result as a source-contract binding and forbids use for scenario-family authority, but the family selector still chooses which candidates reach the check. Phase 7 says scenario-family lookup leaves the authority decision path and only compatibility/audit projections emit family strings. Whether this validated source-contract filter is allowed by that clause is `not_established` by its name or authority-envelope text alone. Before removing the compatibility route, use an adversarial consumer test: same source bytes and valid contract with sibling family labels; then a matching family with missing required facets or failed contract validation. Assert both the selected candidate refs and the exact authority result at the actual checker/consumer boundary.

## Original IDs and retirement gates

The relevant original identifiers and their current occurrence routes are:

| ID / occurrence | Required property | Current evidence |
| --- | --- | --- |
| `data-requirement-family-fallback-from-hardcoded-heuristic` in `architecture/shims.toml:71–85` | Default-off legacy heuristic; remove only after frozen replay, W12.A missing-family zero, and W11.E construct-vocabulary no-regression. | `flag_default="false"`, but `sunset_date="2026-06-30"` is past and the row has no `status="sunset"`. Trigger is not demonstrated. |
| Policy Evidence Capability Graph Phase 4 / I-G4 in `docs/plans/active/POLICYOS_POLICY_EVIDENCE_CAPABILITY_GRAPH_PLAN.md:1462–1487, 1830` | AND gate: resolver-selected or typed-blocked results; rejected alternatives; default false; heuristic only as gated legacy path with sunset metadata; W12.A blocker shift; W11.E construct vocabulary with no baseline regression; candidate firewall, cross-modal refs, mappings, capability reality transition. | Checkboxes remain open. Current unit tests cover only the flag boundary; current canonical W12.A/W11.E outputs are absent. |
| Phase 7 / I-G7 in the same plan at `1783–1815, 1833` | Family lookup leaves authority path; compatibility/audit only; frozen legacy replay emits a typed warning; post-plan replay binds frozen capability/construct/composition refs; DCAT 3 and PROV-O exports; cards; I7-bis and W12.A/W12.D artifacts. | Phase 7 checkboxes remain open; the listed canonical artifacts are absent (below). |
| `scenario-family-authority` and `scenario_family_authority_lookup` in `architecture/shims.toml:88–110` | Preserve legacy family projection as sunset/read-only compatibility while capability-index authority replaces it. | Both are marked `sunset` with 2027-12-31; this is separate from the overdue heuristic row. Runtime code preserves a compatibility projection. |
| W12.A (`wave6_local_validation_ladder_manifest.json`) | Quick local re-execution with a capability-aware producer/consumer signal. | At initial assessment the quick profile invoked W11.E `--self-test`, not the W11.E corpus, and its local production probe had the proxy mismatch below. The source follow-up closes that local child-status mismatch; the quick profile remains distinct from full-corpus W11.E evidence. |
| W11.E / W12.B (`check_compilation_truthfulness.py`; `run_compilation_truthfulness_audit.py`; `wave12b_compilation_truthfulness_audit_manifest.json`) | Full corpus comparison of obligations and construct vocabulary, then rollout floors. Governed-pilot W12.B floors are 50 per case, 60 aggregate, and 50 per domain. | The existing command is available, but W11.E calls the W6/W7 grammar/obligation/claim-decomposition/eight-stage producer chain; it does not call `DataRequirementCompiler`. W11.E/W12.B metrics cannot directly falsify this fallback branch. No current report or pinned pre-Phase-4 baseline report is in the canonical output paths. |
| W12.D and archive diff manifest (`wave12_capability_graph_archive_diff_manifest.json`) | W6/W7/W8 producer path, selected capability binding, replay refs, and export artifacts. | The manifest says `status="implemented"` and lists after-capability-graph artifacts, but the listed W12.A, W12.D corpus-stub, W12.D real-producer, full-index, DCAT, PROV-O, and cards paths are absent in this candidate. The manifest is a declaration, not those run outputs. |
| ADR-0174, “Feature Flag / Advisory Posture,” lines 163–172 | Older Phase 0 note says default `true` and names a default-true test. | Contradicts current compiler and Phase 4 source: default is `false`; that named test is absent. Phase 4/I-G4 is the specific current criterion. The ADR should be reconciled by its owner, not used as evidence that runtime default is true. |

W12.A’s plan-level predicate is specifically `production_data_scenario_contracts_missing` (Phase 4, line 1475; Phase 7, lines 1976–1980). At initial assessment the exact code was present in the plan/archive diff and a repo-quality assertion, while the direct production checker emitted concrete per-family findings for missing manifest, unavailable scenario contract, missing source family, or incomplete source contract. The checker supports `--require-passing` (`:33–160, 215–246`); the current W12.A production-data-static child retains that issue whenever its source-family binding report lists missing families, regardless of separate construct-blocker evidence. A separate construct failure can still determine the overall status.

At initial assessment, the W12.A quick command called `local_prod_debug_probe.py --checks quick,production-data-static,docs-repro` without `--require-passing` (`run_policy_design_case_local_validation_ladder.py:1169–1199`). The probe retained `scenario_binding_findings` and `missing_scenario_source_families` in details, but missing family details did not become an issue (`local_prod_debug_probe.py:1310–1365`). The probe already supported `--require-passing` (`:1798–1814`), while the ladder marked a child `pass` solely from exit code zero (`run_policy_design_case_local_validation_ladder.py:1043–1064`). The follow-up now sets that flag and independently reads each declared JSON child report status.

This was the concrete P38 divergence at initial assessment: the plan property is “no missing scenario-family blocker”; W12.A observed child exit code and construct blockers, while a missing scenario family could remain only in details. A candidate with no matching family but no construct blocker could therefore leave the local probe at `pass` and the ladder child green. Independent review then showed the same class one level deeper: blocker-shaped metadata or a construct-to-capability result could suppress a listed missing source family, and malformed `/summary/status` could fall back to a contradictory root `/status="pass"`. The current candidate retains missing families alongside blocker evidence and admits only the canonical nested string status. Focused tests preserve the blocker and absent-family facts, reject four invalid/missing canonical status shapes, and keep the actual production snapshot `not_established` until the native report is run and read back.

W11.E’s full path is also distinct from its quick smoke. The quick W12.A profile uses `check_compilation_truthfulness.py --self-test` (`run_policy_design_case_local_validation_ladder.py:1202–1234`). The full W11.E function compares corpus annotations with W6/W7 compilation outputs (`check_compilation_truthfulness.py:297–397`), but that chain does not consume the data-family fallback. W12.B’s rollout floor is not the same predicate as “no regression below the pre-Phase-4 baseline”; the latter still needs a pinned baseline report on the same corpus.

## Available fixtures and absent current-production input

The locked offline semantic corpus is `tests/fixtures/universal-corpus` @ `manifest.json` SHA `78b32388a3a28a01548dbc13cac664424b48d1c8e02de9da66a27ea758ccdabb` and README SHA `51732e5fde5a01dc99be9c809de78dc9d89147f7727e3b11840fe50fd53a3e98`. It has 13 case JSON files and 13 producer-stub JSON files. Its README explicitly says those fixtures do not satisfy runtime evidence, legal authority, method validity, participation legitimacy, projection authority, or closeout. `run_universal_outcome_corpus.py --mode corpus_stub` is supported, but the code marks that mode’s boundary as not usable for production-closeout authority. `build_policy_evidence_capability_index.py --mode fixture` creates tiny synthetic local source assets. These are valid offline engineering controls, not a current production-data result.

The existing `tests/_data/data_forge/ukraine_shadow` fixture has 14 JSON files but no root `manifest.json`, which the direct scenario checker requires. The candidate’s `production_data` path is a symlink to `/Users/deniskopylov/polisyos/policy-engine/production_data`; I inspected the link metadata only and did not read that external tree. No approved, content-pinned current-production snapshot was supplied in this task. Therefore the direct current-production minimal check remains blocked on an explicit authorized snapshot path and its manifest/data hashes; the symlink is not a candidate-local reproducibility input.

The candidate canonical W12.A/W11.E/W12.D outputs and capability-index exports checked for this assessment are absent: `_build/.tmp/production-quality/universal_pdc_local_validation_ladder.json`, `universal_pdc_local_quick.json`, `compilation_truthfulness_report.json`, `w12b_compilation_truthfulness_audit.json`, `w12d_universal_outcome_corpus_run.json`, `w12a-after-capability-graph.json`, `w12d-after-capability-graph.json`, `w12d-corpus-stub-after-capability-graph.json`, `w12d-real-producer-after-capability-graph.json`, and the full capability-index DuckDB/DCAT/PROV-O/cards paths. `capability_reality_report.json` @ `9a0a8baf637a886a059729b36902cad56b33443cf05cfa59adb32ccbd1dc20c6` labels the resolver and graph `implemented` with `validation_profile="planning"`; that is a register declaration, not a substitute for the missing run reports.

## Exact next-wave recipe

After source freeze, first pin a permitted production snapshot; record the snapshot root, `manifest.json` hash, and hashes of every data file the checker will read. Do not use the candidate symlink as the implicit root. Use the candidate `.venv`, set `PYTHONPATH=src:.`, and keep the fallback explicitly false. The import preflight must resolve `polisyos` inside this candidate before accepting any report.

Offline controls (these do not assert production authority):

```bash
cd /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine
export PYTHONPATH=src:.
export POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED=false
.venv/bin/python -c 'import pathlib, polisyos; expected=pathlib.Path("src/polisyos/__init__.py").resolve(); actual=pathlib.Path(polisyos.__file__).resolve(); assert actual == expected, (actual, expected); print(actual)'
env -u POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED .venv/bin/python -m pytest --tb=short -rA \
  tests/unit/data_requirement/test_compiler.py::test_missing_resolver_does_not_load_runtime_fixture_when_fallback_is_disabled \
  tests/unit/data_requirement/test_compiler.py::test_legacy_family_heuristic_only_runs_when_phase4_flag_is_enabled \
  tests/unit/data_requirement/test_compiler.py::test_hardcoded_claim_text_fallback_is_not_used_when_phase4_flag_is_disabled
.venv/bin/python tools/quality/validation/build_policy_evidence_capability_index.py \
  --mode fixture --output-dir docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/data-requirement-fallback/capability-index
.venv/bin/python tools/quality/validation/run_universal_outcome_corpus.py \
  --repo-root . --corpus tests/fixtures/universal-corpus \
  --mode corpus_stub --producer-stub-dir tests/fixtures/universal-corpus/producer_stubs \
  --capability-index docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/data-requirement-fallback/capability-index/capability_index_v1.duckdb \
  --graph-output-dir docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/data-requirement-fallback/graphs \
  --hypothesis-ledger-output-dir docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/data-requirement-fallback/ledgers \
  --critic-report-output-dir docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/data-requirement-fallback/critics \
  --output docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/data-requirement-fallback/w12d-corpus-stub.json
```

For current production, set `POLISYOS_PRODUCTION_DATA_ROOT` to the separately approved immutable snapshot and run the actual source-family checker with `--require-passing`:

```bash
export POLISYOS_PRODUCTION_DATA_ROOT=/approved/immutable/snapshot/<snapshot-id>
.venv/bin/python tools/quality/validation/check_production_data_scenario_contracts.py \
  --repo-root . --production-data-root "$POLISYOS_PRODUCTION_DATA_ROOT" \
  --scenario ukraine_msme_wartime_credit_support --require-passing \
  --json-output docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/data-requirement-fallback/production-scenario-check.json
```

Run full W11.E/W12.B over the actual fixture corpus, not W12.A’s synthetic self-test. Preserve the W11.E report and W12.B result separately, then compare W11.E against the pinned pre-Phase-4 baseline using the same corpus hash:

```bash
.venv/bin/python tools/quality/validation/run_compilation_truthfulness_audit.py \
  --repo-root . --corpus tests/fixtures/universal-corpus \
  --raw-report-output docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/data-requirement-fallback/w11e-full.json \
  --output docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/data-requirement-fallback/w12b-full.json \
  --rollout-posture governed-pilot --require-passing
```

Then run W12.A quick with `--require-passing`, explicitly inject the pinned W11.E report through `--compilation-truthfulness-json`, and retain the local-production-debug child output. Provide the configured `POLISYOS_CONTROL_POSTGRES_DSN` through the approved runtime secret mechanism when the selected quick checks use PostgreSQL; do not print it into receipts. The direct scenario checker’s `missing_scenario_source_families` and full `scenario_binding_findings` must be read back, not inferred from exit code.

Phase 7 still needs the named frozen legacy-PDC replay and full post-plan replay against the frozen capability index, construct registry, and composition-rule refs, plus DCAT/PROV-O/cards and I7-bis. Run the existing replay/export/W12.D tests as verification of their consumer paths, but keep corpus-stub results classified as non-production authority.

## Pattern pass and bounded residual

- **P06 / P28:** the fallback flag is default-off but callable and past its shim date; the compatibility scenario branch is separate and unconditional on that flag. The old ADR and I-G0 statement conflict with current code, while Phase 4/I-G4 agrees with it.
- **P35:** the source/test call map above uses a complete `src`/`tools`/`tests` `.py` denominator and names the excluded evidence-snapshot universe. The earlier local note’s smaller count and “no normalizer caller” conclusion are superseded.
- **P37 / P38:** environment enablement is externally supplied and the current process value is `not_established`. The original W12.A zero-family child-status proxy is repaired in the current candidate; the direct checker remains the property-shaped independent control, and actual snapshot coverage remains `not_established` until its report is read.
- **P07 / P05 / P10:** frozen replay and evidence binding remain required; family strings alone do not prove source content or producer authority. Verify the complete selected-reference boundary, not only the family label.
- **P01 / P02:** the capability graph has compiler, artifact, consumers, tests, and audit surfaces, but Phase 4/7 closeout remains `verification_missing` until the actual orchestrated reports and replay/export artifacts are read back. The isolated compiler tests are not the complete capability demonstration.
- **P40:** the grammar-failure scenario projection is the next escape if only the env-gated helper is retired. Widen any future retirement assessment to the whole producer→loader→contract-index chain, or explicitly retain the projection as a bounded compatibility-only surface with the adversarial source-contract falsifier above.

No legacy retirement is justified by “no callers”: the current direct call map disproves that premise. No source lease or semantics change is requested by this decision packet; Phase 4/7 evidence and the snapshot input remain the gating facts.

## W12.A status handoff repair (2026-10-10)

The initial P38 finding above identified two linked gaps: the `production-data-static`
check retained missing family names only in details, and W12.A promoted child exit
code zero to `pass` without reading the child's declared report status. The current
candidate repairs that handoff without changing family derivation or upgrading any
family string into authority:

- `production-data-static` retains a `production_data_scenario_contracts_missing`
  issue with the source-family binding report's missing list. Construct blockers
  and construct-to-capability resolver results remain visible but do not erase
  that source-family absence or establish source availability. A separate
  construct failure can still set the overall status to `fail`.
- W12.A invokes the existing local probe `--require-passing` option. Its executor
  reads the canonical `/summary/status` from every declared JSON output reference
  and records its `present`, `missing`, or `malformed` state, normalized value,
  freshness, and parse error. A root `/status` cannot replace an invalid or absent
  summary status; a stale, malformed, missing, empty, or non-`pass` status cannot
  be promoted by a zero process exit.
- The direct scenario checker is a separate command; `--require-passing` returns
  2 for any non-pass report. It retains the source binding report's missing-family
  list and combines those diagnostics with construct blockers; construct metadata
  does not establish that a physical source family is available.

The controlled negative tests exercise blocker-shaped construct metadata while
retaining missing families at both the local probe and direct checker boundaries,
then separately hold a W12.A child report at `warn` while its simulated process
exits zero. The direct checker test runs the real source-contract index over a
temporary contract fixture before adding blocker metadata, and asserts that both
finding classes survive. Four additional shape controls reject malformed,
missing, or noncanonical nested statuses even when a root `/status="pass"` is
present. The probe reports `warn` and exits 2 under
`--require-passing`; W12.A records the child report's `/summary/status=warn` and
returns a blocked ladder result. This closes the local P38 proxy at that boundary;
it does not establish the actual production snapshot's family coverage or satisfy
the remaining Phase 4/7 replay and export criteria. The canonical
`wave6_local_validation_ladder_manifest.json` is a generated companion and must be
regenerated from `build_ladder_manifest()` after this source change.

The independent source-family checker had the same loss one level deeper. Its
full stdout, XML, and lint receipts are under
`docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/w12a-structured-child-status/`.
report builder selected construct findings instead of source diagnostics and
cleared `missing_scenario_source_families` whenever any construct binding was
present. The follow-up combines construct and source findings and carries the
source index's missing-family list unchanged. The falsifier runs the real
`ProductionDataContractIndex` over the temporary contract fixture, then adds a
blocked construct metadata row to its report; before the fix the checker emitted
an empty missing-family list (`direct-checker-red.log`, SHA-256
`ef7988033582212ee18485668393450d1e4988ebf7937990bb22e2131f68cf92`), while
afterward both finding classes remain (`direct-checker-green.log`, SHA-256
`db096ec41ee24599e75610ea4aab28a7d18b7f68c08bedce2e0982d73a93a19c`). The
final focused W12 producer/consumer pair passed 43 tests with one optional
PostgreSQL integration skipped because its DSN was unset; full output and XML
are retained as `w12-focused-final.log` (SHA-256
`d364090004ececd2e8ef2d34266b000a81400d06a7c5fae4663a4cb30f43c75e`) and
`w12-focused-final.xml` (SHA-256
`420f3607c827367965f34f246bd8f1b29161a9d175c74fbbe2705bf69a5d1166`).
These compatibility reports still do not establish physical source availability
or production snapshot authority.

The focused run was repeated inside the pytest process with an import-path census:
12 selected tests passed and all 1,612 loaded `polisyos` module paths resolved
inside the candidate product tree (`w12-import-census.log`, SHA-256
`96a8c21d4e405965e35b9a0535fb5f313ebac2cb5b6970c49381e7c66ad3a3df`). Ruff
check passed for the five owned Python files (`ruff-final.log`, SHA-256
`82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`), and the
same five pass `ruff format --check` (`format-final.log`, SHA-256
`f114d83b30c5c657ee43a847a45bafccaea255d82673feb87c26d252c61e29c1`). Python
compile, release-fragment TOML parsing, and the two runbook checks also pass;
their full outputs are retained beside these logs. Formatting ran only over the
five leased Python files. The complete initial four-file formatter diff and the
two-file direct-checker delta are retained as `format-diff-pre.txt` (SHA-256
`45b40b18ee08a8130b086f51273929634da7c4688c31867c85b6c499307e9162`) and
`format-diff-direct-checker.txt` (SHA-256
`37019745afa14b0b27e4a3f2ae3712481a2a44b1f92ebbb0b40441bc2c4cd063`).
