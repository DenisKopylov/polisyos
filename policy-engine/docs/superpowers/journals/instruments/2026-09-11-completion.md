# Instruments that report their unmeasured boundaries

Local execution journal for `codex/instrument-honesty`, slice base `cc74d6581`.
No push or hosted workflow dispatch. This journal distinguishes a completed
measurement that rejected its subject from a run that produced no complete
verdict. It does not claim hosted CI success or historical ownership of the
coverage deficit.

## Delivery and evidence protocol

The requested branch and worktree names were checked before any other action;
worktree grep printed nothing and the exact branch lookup was empty. The exact
requested worktree was then created, attached to the requested branch. Four
Stage 1 decisions were committed in `81a7fec33766defbd022e9f1e95f5f8269f2207e`
and read back before source implementation:

- `docs/superpowers/specs/2026-09-11-instrument-invocation.md`
- `docs/superpowers/specs/2026-09-11-instrument-dashboard-coverage.md`
- `docs/superpowers/specs/2026-09-11-instrument-pyproject-budget.md`
- `docs/superpowers/specs/2026-09-11-instrument-ci-repairs.md`

Each composes named existing owners and callers, names excluded seams, and
specifies a negative. Refinements for complete CAS custody and canonical type
generation were separately committed/read back before their corresponding
implementation. Root serialized shared architecture/configuration changes.

Raw evidence is deliberately ignored under `instruments/**/raw/`, as added in
the first commit. Complete deciding stdout/stderr and removal probes remain
there. The companion runner names literal test selectors and gate commands.
Raw receipt indexes record exits and distinguish reconstructed replay commands
from historical argv that was not retained. Tracked source is cited by path and
commit; no source dumps or duplicate derived inventories are committed.

Provisioning used a local Python 3.14.3 environment, the frozen lock with
`lint`, `test`, and `runtime` extras, and `corepack pnpm install --frozen-lockfile`.
The initial offline Python attempt lacked cached wheels; online frozen sync
completed. Mutation has its own frozen environment because its extra was absent
from the first targeted station. Those provisioning failures are not product
findings and are not compared to provisioned finding totals.

## Four row verdicts

### Invocation boundaries

Instrument honesty repair complete. The fresh registered census completed with findings (exit 1); recomputation also exits 1 with an identical receipt, and a separate corrupted receipt is UNRUN/2. Nineteen focused tests pass.
The implementation has explicit `unresolved_by_construction` receivers and
unresolved dynamic receiver sites. Direct orphan findings remain separate.
Exit 0 is a bounded static pass; 1 rejects direct regressions; 2 is UNRUN or
receipt drift; 3 means new unresolved registration boundaries without a direct
regression. A route or callback registration cannot erase a removed direct
call path. No runtime invocation or persisted business evidence is inferred.

### Dashboard statement adequacy

The first full Vitest run completed without producing a coverage report (exit 1, 3,191.52 seconds). Six outer fixture watchdogs expired and one PNG-name removal probe removed a non-PNG companion; these are distinct classes. The actual ratchet reports the absent report as UNRUN/2. The reviewed repair decision was committed and read back in `1e7d1cebb` before source edits; a fresh full replay remains required. The binding floor remains
85.57%, tolerance remains zero, and coverage globs remain unchanged. New tests
exercise shortcuts, reproduction navigation, and scenario-capability behavior
through real UI/query boundaries. They are behavioral tests with removal
negatives, not tests that merely execute lines. Historical ownership remains
`not_established`: no complete earlier coverage report establishes attribution.
The export census also found that `GlobalShortcuts`, `ReproduceRunButton`, and `useScenarioCapabilities`
exports do not currently have production consumers; that `bridge_missing`
limitation is separate from whether their source was exercised.

### Original CI per-item repair

Local per-item evidence is reported below; aggregate hosted closure is
`verification_missing`. Original failed-job bytes were read directly and matched
C-CI's recorded log hashes. S02 is executable-provenance mismatch, distinct from
S01/S03 missing Python jsonschema. All six original Runtime failure nodes were
included, including the two metrics-provider failures omitted by the parent row.
No cancelled/skipped job is converted into a local pass.

### Pyproject budget

The physical count is 307 against the unchanged 300-line cap. The September 10
change added two physical lines (comment plus `policy-engine[test]`), moving
305 to 307. The prompt's one-line description was not used as measurement.

The budget is a valid physical-volume instrument, including comments and blank
lines. It is not a valid proxy for dependency correctness, TOML semantic
complexity, or resolver cost. No empty-line compression, floor change, lock edit,
or exception was used to erase the finding. The instrument's honesty repair is
complete; disposition of the excess remains
`complete-pending-an-architect-decision` for the repository-structure owner.
The physical-volume CLI remains FAILED with the finding visible. The negative
constructs unavailable/malformed station input and obtains UNRUN even in
report-only mode; complete over-budget input remains a distinct measured failure.

## Instrument output and negative evidence

The following are the actual output scopes, not documentary waivers.

- Invocation: “Partial coverage: Static direct-call reachability from project
  scripts and non-test __main__ guards, stopping at deferred bodies. Unmeasured:
  HTTP router dispatch; dependency injection/container dispatch; event-bus
  dispatch; registered callback invocation; deferred lambda/coroutine execution
  and generator resumption; reflection and dynamic receiver/factory resolution;
  runtime execution, persisted business receipts, and gate substance.” Router,
  DI, callback, dynamic receiver and deferred-body negatives retain uncertainty
  and cannot hide a direct orphan. CLI negative also proves UNRUN.
- Dashboard coverage: “Not measured: assertion quality, production invocation,
  source-content freshness of this report, suites not executed by its producer,
  code outside the configured coverage globs, backend behavior, or hosted CI.”
  Missing, stale-scope, malformed and inconsistent reports are UNRUN, distinct
  from a complete below-floor FAILED result. UI removal probes fail when the
  actual behavior is removed.
- Package/import gate: “Not measured: runtime import execution, framework
  invocation, semantic correctness, dependency installation, or hosted CI. Root
  Python classification excludes untracked and ignored Python; absent local-only
  roots are not inspected.” Tests prove absent optional mounts are explicitly
  unmeasured, absent required source stays a finding, ignored Python is excluded
  under a named tracked denominator, and missing Git/contracts is UNRUN.
- Directory gate: “Not measured: documentation substance, runtime behavior,
  fixture adequacy, or hosted CI. Tracked-file metrics exclude untracked/ignored
  contents; missing local roots are not inspected. Filesystem-residue checks use
  their separate on-disk scopes.” Missing contract/Git negatives refuse an empty
  successful inventory. Current role/README/fixture repair passes without
  changing documentation floors or expiry dates.
- Docs accuracy: “Not measured: prose truth, runtime behavior, external URL
  availability, unpublished document contents, reference-style links, images,
  asset existence, unresolved extensionless links, .yaml workflows, rendered
  site deployment, or hosted CI.” Missing YAML, malformed nested nav and
  malformed pattern lists are UNRUN. An existing unpublished Markdown target
  fails; unsupported link formats remain present in the negative and are
  explicitly named as omitted on a bounded pass.
- Runtime contract: “Not measured: endpoint execution, authorization behavior,
  client behavior, production deployment, or hosted CI.” Missing comparison
  input/failed generator is UNRUN; previously found drift is retained as partial
  coverage. `--skip-client-drift` explicitly prints client freshness omitted.
- Shared-types comparison: “Measured: schema-type bytes from the locked
  executable and canonical recursive-type normalizer. Not measured: runtime
  client behavior, endpoint execution, or hosted CI.” Removing normalization
  while retaining subprocess success must make the actual byte-comparison test
  fail; raw generator output is not the canonical artifact.
- Scientist Phase 1: “Partial coverage: supplied JUnit pass names and benchmark
  names, plus Python AST bare or unqualified Exception/BaseException handler
  syntax (including tuples) and explicit .model_copy(deep=True) syntax.
  Unmeasured: execution provenance of those reports, benchmark performance,
  runtime receiver types, call reachability/hotness, copy necessity/cost, opaque
  aliases and dynamic arguments, qualified/aliased exception types, and
  allowlisted/excluded source.” Dynamic-copy and qualified-handler negatives
  remain explicitly unresolved/omitted; missing/malformed source is UNRUN.
- Fabric fingerprint: “Partial coverage: normalized literal 'except Exception'
  text in rg-visible files under src/polisyos/fabric (all file types; rg ignore
  rules apply). Unmeasured: tuple/bare/aliased handlers, other exception syntax,
  ignored files, runtime exception safety, rollback correctness, and historical
  change attribution (this command compares count/digest, not baseline member
  identities). Comments/strings may match; this is a text fingerprint, not an
  AST handler census.” Tuple/comment/string and missing-scanner/source negatives
  prove these distinct limits. Storage rollback and error translation have
  separate behavioral tests; the fingerprint cannot establish them.

- Evidence fixture watchdog: “Evidence fixture watchdog measures completion of
  the named suite's assertions. Not measured: production latency, paths outside
  this suite, or hosted CI. A watchdog timeout is UNRUN for the unfinished
  fixture, not a completed semantic verdict.” The first full wave's six outer
  watchdog expirations supplied no complete fixture verdict. The real-child
  timeout negative retains `PersistenceExecutionUnrunError`, `UNRUN` and
  `ETIMEDOUT`; unavailable producer cases refuse fabricated evidence. The shared
  fixture policy does not change product step/work budgets.
- Visual AST/PNG reconciler: “Visual harness measures literal executable
  screenshot references and committed PNG names. Not measured: screenshot
  rendering, pixel equality, or non-PNG companions.” Its actual-PNG removal and
  orphan-PNG negatives reject disagreement; README/text/JSON companions leave
  the measured set unchanged. The first full wave caught this lane's earlier
  removal of README outside the PNG denominator. No pixel-rendering claim is
  inferred from the reconciler.

Pyproject prints: ‘Measured scope: Selected structural predicates over tracked repository inputs. Pyproject physical lines include comments and blank lines.’ It then prints: ‘Not measured: runtime behavior, semantic correctness, or untracked station files, configuration complexity, dependency correctness, resolver cost, or TOML validity.’ The deciding registered CLI output is `root/raw/pyproject-final-cli.log` (exit 1); eleven selected cases passed in `root/raw/pyproject-final-tests.log`.

## Pattern pass and incidental routing

P05/P04/P09 preserve authority and status; P29/P32/P33 require behavioral
negatives; P35/P36 prohibit sampled counts and adjacency-based evidence;
P37/P38 identify declared or wrong measurement predicates; P31/P40 widen one
class rather than patching successive witnesses; P41 keeps ownership unknown
without a slice-base replay and complete disjointness proof.

The docs review bucketed malformed nested scope as the SAME class and closed it
through generic validation. Unsupported lexical formats were one NEW bounded
class, explicitly omitted, with a reproducing negative. The R01 sibling CAS
findings were the SAME class: the complete runtime constructor/import set was
migrated through the existing factory, preserving every root and tenant/cell
option. The test comparison's omitted normalizer was P38 and now composes its
actual producer.

Incidental destinations:

- Core artifact configuration research backlog: inferred filesystem config
  carries root/backend but omits tenant/cell, so general scoped reconstruction
  is not established. New consumers use it only for path location and do not
  reconstruct a scoped store.
- Runtime quality integration backlog: `GlobalShortcuts`, `ReproduceRunButton`, and `useScenarioCapabilities` exports
  without discovered production consumers remain `bridge_missing`; no mounting
  claim was added by this lane.
- Team Fabric GC policy research backlog: `retain_latest=0` currently uses
  `manifests[-0:]`, retaining all entries. Not repaired in this slice.
- Team Fabric error-boundary decision: broad parquet read/write translation
  remains bounded pending the actual engine-error contract. No speculative
  exception union was invented.
- DevX tool-config generator backlog: its generation report can inspect stale
  generated overrides before writing regenerated output and therefore exit 1;
  a subsequent canonical `--check` supplies the actual freshness verdict.
- Repository-structure architect: physical pyproject budget suitability and
  excess disposition; no policy adjustment was made by this lane.
- Architecture import/public-surface owners: exact remaining expired exceptions,
  coupling, dynamic imports, cycles, shims, shells, size violations and new deep
  imports are routed with complete current findings. No `guardrails sync`.
- Grounding-relation instrument research backlog: missing solver yields UNKNOWN candidate results and a refused bind, while the certificate can default its top-level solver status to SAT and omit the unavailable reason. No authority false green was observed; solver provisioning and CAS persistence are distinct predicates.
- Runtime owner-validator/station owners: timeouts and absent canonical inputs
  receive no complete behavior verdict; exact final dispositions follow below.
- Explicit nowhere: failed offline cache attempts, pre-provisioning mutation
  results, temporary test-fixture setup errors and superseded corpus-recovery
  attempts. Retained for provenance, excluded from product verdicts.

No DEBT-REGISTER.md or LEDGER.md was edited or used as evidence about the tree.
No governed epoch bump is claimed merely from a source or generated-byte change.

## Runtime station boundary

The first canonical OpenAPI export ended with `OwnerValidationTimeoutError` for `confidence-ledger-risk-spend` at its existing 184-second owner deadline. It produced no schema rewrite or freshness verdict (`root/raw/openapi-owner-export.log`, exit 1). That exception is not the original epoch status mismatch. The registered contract-checker negative (`root/raw/runtime-registered-unrun-negative.log`, exit 2) explicitly reports UNRUN for an absent comparator. No timeout was increased. Data-only station provisioning is separately hashed; it is not source repair or proof of the unavailable pinned world artifact.

The first full registered invocation census produced no receipt: `KeyError` escaped the scanner (`invocation/raw/production-invocation-final.log`, exit 1). This is an instrument failure with no complete verdict, not a direct-path finding set. The shared conditional traversal repair passes nineteen explicit nodes, including internal exception plus prior-receipt refusal (`invocation/raw/conditional-domain-final-tests.log`, exit 0); fresh full recomputation and the registered corrupted-field negative now complete as recorded below; the failed attempt is retained and excluded from count comparisons.

## Original C-CI item handback

The table denominator is all 70 original C-CI Markdown table IDs in `docs/superpowers/specs/2026-09-10-apparatus-station-and-ci.md@cc74d6581`: Fast, Standard, Runtime, Fabric and Canary, including original successes, skips, cancellations and aggregates. Original failed-job bytes are preserved under `root/raw/run-34196405835-failed.log`, `run-34196405796-failed.log`, `run-34196405891-failed.log`, `run-34196405795-failed.log` and `run-34196405782-failed.log`; their hashes were independently reconciled. Those historical logs establish historical findings, never current source ownership. Receipt paths in this table are relative to this journal directory.

| Original ID | Local disposition | Deciding evidence / remaining measurement | Named destination / boundary |
| --- | --- | --- | --- |
| CI-F01 | Unmeasured current hosted boundary; historical success only | Historical Fast workflow-governance result is preserved; no current hosted success is inferred. | Workflow governance owner; revalidate any actual workflow edit. No repair follows from historical success. |
| CI-F02 | Measured architectural residual; package-r03-final.log exit 1, complete declared measurement | Complete frozen package JSON emits import-exceptions; the complete frozen identity set is retained in package-r03-final.log. | Architect: actual expired exception validity and current uses, under imports/exceptions.toml. complete-pending-an-architect-decision; no date extension. |
| CI-F03 | Measured architectural residual; package-r03-final.log exit 1, complete declared measurement | Complete frozen JSON reports both runtime→quality and quality→runtime unregistered hidden coupling, with preview added_edge_keys in summary.import_boundary.package_level_deltas; complete owner-derived sets are retained in invocation/raw/deep-import-delivery-census.json. Zero forbidden edges does not discharge these. | Architect: reconcile actual complete edge sets with package boundaries; no deep-import baseline acceptance. |
| CI-F04 | Measured architectural residual; package-r03-final.log exit 1, complete declared measurement | Complete frozen JSON retains dynamic-imports findings and the scanner/registered-target summary. This syntax/registration inventory does not execute dynamic receivers. | Architect and dynamic-import registration owner: full identity reconciliation, no sampled registration patch; unresolved runtime targets remain unmeasured. |
| CI-F05 | Measured architectural residual; package-r03-final.log exit 1, complete declared measurement | Frozen JSON contains actual non-lazy SCC member sets and a separate aggregate import-cycle finding. Do not count the aggregate as another SCC. | Architect and Foundry/Scientist graph owners: classify each actual SCC and current source edge; no allow-list refresh to erase it. |
| CI-F06 | Measured architectural residual; package-r03-final.log exit 1, complete declared measurement | Complete frozen JSON retains shim-expiry identities, without changing their expiry policy. | Architect plus named shim owners: migrate/strangle actual consumers or provide an evidence-backed architectural ruling; no convenience renewal. |
| CI-F07 | Repair implemented; package-r03-final.log exit 1, complete declared measurement | Root admitted architecture as the existing non-product evidence Python role. package-scope-green.log exercises tracked roots and unavailable denominators. | Importable-root contract owner; retain evidence files. The frozen package report has no importable-root findings. |
| CI-F08 | Repair implemented; package-r03-final.log exit 1, complete declared measurement | Root admitted docs as the existing non-product evidence Python role. Ignored raw scratch is explicitly outside tracked Python inventory; malformed or unavailable input is UNRUN. | Importable-root contract owner; the frozen package report has no importable-root findings. |
| CI-F09 | Repair implemented; package-r03-final.log exit 1, complete declared measurement and directory-final.log exit 0 (complete declared scope) | Root declared the actual vendor locked-wheel-input role; no wheel dependency was removed. | Architecture/directory and vendoring owners; both exact gates complete and contain no vendor role finding. |
| CI-F10 | Repair implemented; package-r03-final.log exit 1, complete declared measurement | Missing production_data local-only ignored mount is explicitly named unmeasured. Parameterized missing-mount negative separately exercises this root; absent required tracked root still fails. | Importable-root measurement rule; data contents and mounted runtime behavior remain unmeasured. |
| CI-F11 | Repair implemented; package-r03-final.log exit 1, complete declared measurement | Missing runs local-only ignored mount is independently exercised and named unmeasured; this is not inferred from production_data. | Importable-root measurement rule; generated run content remains unmeasured. |
| CI-F12 | Repaired behavioral seam; package-r03-final.log exit 1, complete declared measurement | Existing extraction function bodies moved unchanged from common/llm_json.py to public common/serialization.py; all thirteen non-test importers switched. common-json-consolidation.log, common-json-green.log and common-json-importer-tests.log preserve AST/body and actual extraction/importer evidence. | Common serialization owner; no root-file exception or shim added. The tracked old implementation is absent and the frozen package census has no root-file finding. |
| CI-F13 | Measured architectural residual; package-r03-final.log exit 1, complete declared measurement | Frozen JSON identifies expired single-file-shell policies for src/polisyos/ir/_internal, ir/connectors, ir/schemas and ir/trinity. | Architect and IR owners: decide actual shell role/decomposition and sunset semantics for each; no shell count baseline accepted. |
| CI-F14 | Measured architectural residual; package-r03-final.log exit 1, complete declared measurement | Subject scientist/nodes/builtins/decide/decision_packet/builder.py retains separate module-size findings. Frozen logical measurement 899, budget and report-only limit 885. | Architect plus decision-packet owner: mechanism decomposition or evidenced metric ruling; no line compression or threshold increase. |
| CI-F15 | Measured architectural residual; package-r03-final.log exit 1, complete declared measurement | Subject runtime/http/services/control/run_lifecycle.py: frozen logical measurement 4149, budget and report-only limit 2050. Historical and current counts are not compared as ownership evidence. | Architect plus runtime lifecycle owner: actual mechanism-size decision; no baseline acceptance. |
| CI-F16 | Measured architectural residual; package-r03-final.log exit 1, complete declared measurement | Subject foundry/methods/selection/advisor.py: frozen logical measurement 3914, budget and report-only limit 3114. | Architect plus method-selection owner: actual mechanism-size decision; no baseline acceptance. |
| CI-F17 | Measured architectural residual; package-r03-final.log exit 1, complete declared measurement | Subject runtime/http/openapi_contract.py: frozen logical measurement 4513, budget 2883, distinct report-only limit 2866. Do not conflate the two limits. | Architect plus OpenAPI owner: mechanism-size decision; generated schema bytes do not discharge source-size policy. |
| CI-F18 | Measured architectural residual; package-r03-final.log exit 1, complete declared measurement | Frozen deep-import finding references architecture/baselines/imports/deep_import.json; summary edge arrays are previews. Complete owner-derived base/current identities and deltas live in invocation/raw/deep-import-delivery-census.json, not the report count. | Architect: actual added hidden edges, including any lane-created creep, are complete-pending-an-architect-decision. No guardrails sync and no baseline acceptance. |
| CI-F19 | Unmeasured historical range boundary | Historical scientist_docs impact failure remains supported by the original Fast log. Current tools/doc-publication checks do not replay that original source-impact range. | Scientist/docs source-impact backlog under this original finding ID; exact original range and subject docs required for closure. |
| CI-F20 | Unmeasured historical range boundary | Original foundry_docs gate named its complete touched-source range. No current generated-tools refresh can prove historical subject documentation. | Foundry/docs source-impact backlog under this original finding ID; no retrospective closure or ownership claim. |
| CI-F21 | Unmeasured historical range boundary | Original security/compliance documentation gap is not measured by current publication/link checks. | Security/docs impact owner backlog under this original finding ID; adjudicate actual changed semantics and documentation. |
| CI-F22 | Unmeasured historical range boundary | Original security runbook/rehearsal gap is a separate consumer from security prose and was not replayed locally. | Security/operations runbook owner backlog under this original finding ID; no inferred rehearsal success. |
| CI-F23 | Repair implemented; tools-docs-final-check.log and generated-docs-final.log exit 0 | Registry-owned tools reference regenerated after invocation wrapper discovery. generated-docs-final.log records six explicit generator tests passing; tools-docs-final-check.log exits 0; the sixth selected generator test executes the real CLI against copied-output corruption and rejects it. | DevX CLI documentation owner; exact caller is polisyos-tools docs --check --output docs/reference/tools.md. |
| CI-F24 | Unmeasured hosted boundary: skipped | Historical ABI job never completed. Current bounded schema/client commands do not establish its full hosted verdict. | Hosted ABI workflow owner; future authorized hosted run, not this local lane. |
| CI-F25 | Unmeasured hosted boundary: skipped | Historical dependency review has no completed verdict; push/PR event conditions remain material. | Dependency-review workflow owner; no local or hosted success inferred. |
| CI-F26 | Derived failure, no independent repair | Historical aggregate Gate failed its dependencies. It is not another product defect and this lane does not execute a replacement hosted aggregate. | Explicit nowhere as a standalone defect; preserve dependency-derived failure and individual rows. |
| CI-S01 | FULL_COVERAGE_PENDING | Exact file apps/runtime-dashboard/src/test/evidence/atlasAutomatedEvidenceCapture.test.ts must complete, including real Python-child persistence and corruption behavior. Historical class is missing jsonschema before persistence. | Dashboard evidence/Python provisioning seam. No current verdict until full-coverage output; no fabricated evidence admission. |
| CI-S02 | FULL_COVERAGE_PENDING | Exact file apps/runtime-dashboard/src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts must complete. Its original class is executable-provenance mismatch, distinct from missing jsonschema. | Dashboard evidence provenance owner; selected executable identity and rejection of forged evidence remain the falsifier. |
| CI-S03 | FULL_COVERAGE_PENDING | Exact file apps/runtime-dashboard/src/shared/lib/domain/workflow.test.ts must complete including source-flip negative. Original child error was missing jsonschema. | Dashboard workflow vocabulary/Python provisioning seam; separate observation from automated capture. |
| CI-S04 | Working-checkout byte contracts passed; isolated OpenAPI freshness failed | Final registered runtime contract check passes against this checkout (`root/raw/runtime-contract-r03-final.log`, exit 0). Frozen guardrails rejects the isolated OpenAPI binding bytes; the complete two-station worker comparison identifies ambient build-directory/lookup bindings. Shared-client/dashboard producers and normalizer-removal negative pass separately; no generated TypeScript byte change. | Runtime schema/client and generated-artifact architect: canonical example station decision remains open. Client behavior and hosted frontend contract execution remain unmeasured; a checkout pass is not universal freshness. |
| CI-S05 | Repair implemented; directory-final.log exit 0 (complete declared scope) | Actual vendor role admitted in shared directory policy, independently of package-root policy. | Directory/vendoring owner; final directory finding set decides this subject and its derived coverage. |
| CI-S06 | Repair implemented; directory-final.log exit 0 (complete declared scope) | Exact fixture role admitted for apps/runtime-dashboard/src/features/trust/components/__fixtures__. | Dashboard/architecture fixture-role owner; no threshold widening. |
| CI-S07 | Repair implemented; directory-final.log exit 0 (complete declared scope) | Exact fixture role admitted for apps/runtime-dashboard/src/test/fixtures. | Dashboard/architecture fixture-role owner; separate directory admission from trust fixtures. |
| CI-S08 | Repair implemented; directory-final.log exit 0 (complete declared scope) | Root supplied READMEs for the complete measured undocumented high-volume subtree set. Floors retained. docs-directory-scope-green.log exercises missing contracts/Git and bounded documentation presence. | Directory/docs owners; final tracked denominator decides. Documentation substance and fixture adequacy remain explicitly unmeasured. |
| CI-S09 | Derived aggregate; directory-final.log exit 0 (complete declared scope) | Historical unregistered-fixture count is derived from the two separately admitted directories above, not a third fixture defect. | Explicit nowhere as an independent defect; directory gate must recompute the aggregate from actual roles. |
| CI-S10 | Unmeasured hosted boundary: cancelled | Full Frontend quality job was cancelled. Authorized dashboard coverage is its own bounded deliverable, not a complete replacement of the hosted job. | Frontend quality workflow owner; no hosted closure claim. |
| CI-S11 | Unmeasured hosted boundary: cancelled | Full Runtime HTTP job was cancelled. Only explicitly named local nodes are authorized here. | Runtime HTTP workflow owner; broader job verification remains missing. |
| CI-S12 | Unmeasured hosted boundary: skipped | Integration job produced no complete verdict. | Integration workflow owner; preserve event/dependency conditions. |
| CI-S13 | Unmeasured hosted boundary: skipped | Frontend smoke job produced no complete verdict; separate from component smoke. | Frontend smoke workflow owner. |
| CI-S14 | Unmeasured current boundary; historical success only | Original component smoke succeeded; no repair or current execution inferred. | Explicit nowhere as a newly discovered defect; current hosted verification outside lane. |
| CI-S15 | Unmeasured current boundary; historical success only | Original Performance job succeeded; no current performance verdict inferred. | Explicit nowhere as a newly discovered defect; performance workflow owns future execution. |
| CI-S16 | Derived failure, no independent repair | Original aggregate Gate enforced failed dependencies; no new product class. | Explicit nowhere as a standalone defect; preserve constituent outcomes. |
| CI-R01 | Repaired exact structural node; importer limitations retained | Exact node is tests/unit/runtime/http/test_architecture_boundaries.py::test_runtime_never_imports_concrete_cas_write_implementation (http, not quality). It passed in ci-factory-custody-green.log; that invocation exited 1 only for a new fixture missing media_type. Corrected real factory custody/unsupported-backend negatives passed ci-factory-custody-green-final.log, exit 0. Complete runtime constructor/import set composed through existing Core factory; ci-original-six-station-two-final.log independently passes all six original R01/R02/R05/R06/B01/B02 nodes; its two station importer failures retain separate evidence and do not erase those results. Additional importer limitations are recorded below. | Runtime/Core artifact-store owners; static alias/dynamic-factory execution remains unmeasured. Tenant/cell and backing custody must retain real behavioral witnesses; new deep imports route to architect. |
| CI-R02 | Repaired exact node and injection behavior | Exact http/test_architecture_boundaries.py::test_runtime_control_paths_do_not_resolve_registry_singletons_inline passed in ci-owner-seams-green-first.log and ci-factory-custody-green.log. Injected valid/absent profiles and different-backing quarantine refusal are exercised; ci-owner-boundary-review.log exits 0. | Acquisition runtime/canonical registry owner; no renamed singleton fallback. |
| CI-R03 | Exact original strict node and owner-bridge negative passed | `invocation/raw/epoch-owner-bridge-final.log` exits 0 for the original `test_epoch_batch_success_example_is_owner_derived_and_strict`, preserving `review_required` and comparing the complete exported example with its typed owner. The later duplicate map entry was removed. `epoch-registration-removal.log` exits 0 only after the same consumer rejects the removed registration with its exact missing-example assertion. | Runtime OpenAPI transport-example owner. Persisted epoch admission, runtime mixed-status composition, clock/expiry behavior and hosted CI remain unmeasured by this sample check. |
| CI-R04 | Canonical producer comparison and removal negative passed | Canonical shared/dashboard generators each exited 0 and changed no generated bytes. Strict test previously compared raw npx output without existing recursive-type normalizer. Helper now composes locked workspace executable plus that canonical normalizer; README corrected, version executed rather than shell markers asserted. Three named nodes pass in types-producer-final.log (exit 0); the original R04 selector is separately replayed in `root/raw/types-original-selected-final.log` (exit 0), with its exact completed argv retained in the root receipt index. types-normalizer-removal-probe.log (exit 0) records the intended AssertionError when normalization alone is removed while subprocess success remains. | Runtime shared-client owner; byte agreement explicitly omits runtime client behavior, endpoint execution and hosted CI. |
| CI-R05 | Repaired exact runtime override node | test_api_maturity.py::test_runtime_container_accepts_typed_test_overrides passed in ci-owner-seams-green-first.log; whole invocation exited 1 for separate still-unfixed R01. Metrics collaborator now supplies real counter contract; no production getattr fallback. | Runtime typed test-collaborator owner; preserve application/CAS provider injection behavior. |
| CI-R06 | Repaired exact middleware node | test_api_maturity.py::test_runtime_security_middlewares_receive_injected_metrics_provider passed in the same full receipt; the failure elsewhere is not hidden. Collaborator/injection identity assertions retained. | Runtime middleware/test-collaborator owner; separate consumer from container override. |
| CI-R07 | Repaired declared publication/link scope | docs/adr/by-topic.md link now targets approved ADR admitted through MkDocs. docs-final-registered-cli.log is passed (declared scope only); existing-unpublished-target negative proves local existence is insufficient. | Docs publishing/ADR owner; prose truth and rendered deployment remain unmeasured. |
| CI-R08 | Repaired declared publication/link scope | docs/adr/index.md separate ADR link closes through same target publication. Actual registered docs CLI passes its declared page universe. | Docs publishing/ADR owner; preserve separate link identity. |
| CI-R09 | Repaired source-reference semantics | docs/brand/ATLAS_DESIGN_SYSTEM.md now identifies the unpublished governing source as a repository-source reference; registered docs CLI passes declared scope. | Brand/docs owner; this does not publish the governing plans or measure external URL availability. |
| CI-R10 | Repaired source-reference semantics | docs/brand/ATLAS_V4_ADOPTION.md separate reference corrected to repository-source semantics; registered docs CLI declared-scope pass. | Brand/docs owner; target publication boundary retained. |
| CI-R11 | Repaired source-reference semantics | docs/brand/README.md first original reference corrected independently; registered docs CLI declared-scope pass. | Brand/docs owner; no invented published page. |
| CI-R12 | Repaired source-reference semantics | docs/brand/README.md second original reference corrected independently; registered docs CLI declared-scope pass. | Brand/docs owner; no inference from the other README link. |
| CI-R13 | Repaired declared publication/link scope | docs/reference/index.md target policy-operations-research-pipeline.md admitted as actual reference through MkDocs owner; registered docs CLI declared-scope pass. | Docs reference/pipeline owner; candidate research claims gain no authority from publication. |
| CI-R14 | Controlled protocol replay passed; native mutation unmeasured | Historical obsolete --paths-to-mutate failure was repaired in canonical runner on slice base. Initial mixed replay lacked installed mutmut metadata and supplied no product verdict. The separate frozen mutation environment is provisioned; mutation-provisioned-final.log exits 0 for twelve controlled cases. Native mutant execution on this macOS station remains unmeasured even after controlled protocol tests. | Mutation runner/DevX station owner; controlled corruption protocol proof is distinct from actual supported Linux mutant execution. No native or hosted mutation pass claimed. |
| CI-R15 | Instrument repaired; measured source-policy rejection; runtime hotness unmeasured | Registered scientist CLI exits 1 in ci-scientist-final.log. AST retains actual explicit defensive copies in agent/workers.py, methods/doe/uncertainty.py and validation/policy_verified/service.py. Same frozen source/JUnit/benchmark comparison preserves original uncertainty finding plus multiline siblings. Alias negative yields unresolved callable target; missing/malformed source yields UNRUN. | Scientist/calibration and gate owner: decide defensive-copy necessity/performance policy; no clone removed, allowlist expanded or benchmark/runtime claim inferred. complete-pending-an-architect-decision for policy adequacy. |
| CI-R16 | Unmeasured hosted boundary: cancelled | Typing and Ratchets produced no complete hosted verdict. Named local lint/gates do not replace its broader contract. | Typing/ratchet workflow owners; verification_missing. |
| CI-R17 | Unmeasured current boundary; historical success only | Phase 0 succeeded historically; no new execution or repair inferred. | Explicit nowhere as a newly discovered defect; future workflow execution owns current verdict. |
| CI-R18 | Unmeasured current boundary; historical success only | Historical Link Check succeeded but measured a different scope from publication-aware Docs Contract. | Link-check owner; keep local reachability distinct from publication and deployment. |
| CI-R19 | Unmeasured current boundary; historical success only | Historical Performance Smoke succeeded; no current performance measurement inferred. | Explicit nowhere as a newly discovered defect; performance workflow owner. |
| CI-R20 | Unmeasured hosted boundary: skipped | Release Review Evidence produced no complete review artifact verdict. | Release-review workflow owner; prior dependencies do not manufacture evidence. |
| CI-B01 | Repaired exact scanner/consumer behavior | Exact sources/test_http_connector_base.py::test_connection_config_redaction_uses_shared_secret_pii_scanner passed in ci-owner-seams-green-first.log. Real scanner-owned secret vocabulary/immutable mapping retained; arbitrary credential-key negatives and incomplete scanner shape UNRUN covered. ci-owner-boundary-review.log exits 0. | Fabric/Core scanner and ConnectionConfig owner; unavailable redaction never becomes apparently empty credentials. |
| CI-B02 | Repaired exact credentials-redaction behavior | Exact test_protocol_compliance.py::TestConnectionConfig::test_redacted_hides_credentials passed in same full receipt; distinct secret-mapping consumer assertion retained. No outer-dict-only diagnosis. | Fabric/Core redaction owner; scanner owns redaction vocabulary, original input stays immutable. |
| CI-B03 | Typed semantic repairs passed; measured fingerprint residual | Segments uses ValidationError/TemporalValidationError/OSError at demonstrated owner seams, preserves conservative GC retain, and no longer fabricates zero metrics after index validation refusal. Behavioral negatives pass ci-fabric-green.log. write_world_fact_segment/load_world_facts retain broad engine translation boundaries. Registered fingerprint still rejects in ci-fabric-fingerprint-final.log, exit 1; missing-root negative exits 2 UNRUN. | Fabric storage/error-policy owner plus architect: retained parquet engine translations and full baseline member policy. No numerical/hash baseline update. complete-pending-an-architect-decision. |
| CI-B04 | Canonical rollback repair passed; measured fingerprint residual | Snapshot merge composes existing DuckDBLegacyBackend.transaction BEGIN/COMMIT/ROLLBACK/rethrow owner. Real failure negative proves record/branch head rollback and original error propagation; ci-fabric-green.log passes. Broad fingerprint still red, with historical identity correction described below. | Fabric snapshot/transaction owner plus architect: no rollback weakening and no baseline acceptance. complete-pending-an-architect-decision. |
| CI-B05 | Unmeasured current boundary; historical success only | Repeated race/leak smoke succeeded historically; no broad replay is authorized here. | Explicit nowhere as a newly discovered defect; Fabric race/leak owner retains future verification. |
| CI-B06 | Unmeasured current boundary; historical success only | Fabric performance smoke succeeded historically; no new performance receipt inferred. | Explicit nowhere as a newly discovered defect; Fabric performance owner. |
| CI-C01 | Bounded local orchestration passed; live workload unmeasured | Historical deterministic canary failed importing fastapi before any scorecard. canary-final.log and its JUnit name four explicitly selected setup/orchestration tests, all passed (exit 0). final-runner.md records every selector. No live production workload, scorecard or ci_safe=false canonical-production lane was executed by this subagent. | Canary orchestration/DevX provisioning owner; bundle=none from failed import is not a policy admissibility failure. |
| CI-C02 | Unmeasured hosted boundary: intentionally skipped | Live provider lane was skipped under push/event/credential quarantine. No external provider was invoked as a probe. | Canary event/credential policy; omission retained, not a product pass. |

Fabric history was reconciled by member identity: `invocation/raw/ci-fabric-historical-fingerprint-recovery-corrected.log` reproduces the stored literal fingerprint from tracked Fabric files at `e0c004fb714ecb0584d4d31b61753fcdc012f3b6`; `ci-fabric-member-delta.log` compares the complete members through this slice base and classifies AST ownership. The earlier wrong-root empty recovery is an UNRUN/non-receipt even though its shell exited 0. Most touched store handlers already existed in that baseline; the record does not attribute fingerprint growth to newly added rollback handlers. Seven semantic additions are identified in the complete delta: HTTP scanner translation, quality evidence admission, SDMX validation, non-data admission/result, retrieval custody and load_world_facts. Different hosted provisioning is not compared by count.

## Completed local gate scope

`root/raw/package-r03-final.log` is a complete JSON verdict (exit 1, no traceback), read after the final invocation/Python source freeze and declared data-only station provisioning. Its complete finding-record denominator is 246 records: 21 import-exceptions, 6 import-boundary, 190 dynamic-imports, 3 import-cycle, 13 shim-expiry, 4 single-file-shell-package, 8 module-size-ratchet, and 1 deep-import. The cycle records are two actual SCCs plus their aggregate; the size records are four subjects against two limits each. All finding records remain in that raw report; complete edge identities are retained separately in invocation/raw/deep-import-delivery-census.json because report arrays are previews. The deep-import aggregate names 161 unregistered edges against the existing baseline; that is neither a lane-created count nor a comparison against the historical hosted tree. The complete canonical owner census finds 30 lane-added guardrails edges and 18 removals; the package model additionally finds the acquisition-executor/control-registry-provider edge. All additions remain subject to the architect’s decision. `complete-pending-an-architect-decision`; no guardrails sync. Importable-root findings are empty; with production_data now present, the absent local root explicitly named unmeasured is runs. This measurement does not validate either mount's contents.

`root/raw/directory-final.log` exits 0 with complete declared coverage, no findings and no regressions. It was measured before the later data-only provisioning; no on-disk station comparison or runtime-content claim is made. `root/raw/docs-final-registered-cli.log`, `tools-docs-final-check.log`, `tool-config-check.log` and `generated-docs-final.log` each exit 0. The retained canonical copied-config probe `tool-config-corruption-retained.log` exits 0 after all producer-derived corrupt copies are rejected; it does not execute mypy, Ruff or MkDocs against them. `root/raw/changed-python-ruff.log` passes the complete then-frozen 58 changed existing Python paths, explicitly listed in the runner. The later invocation construction repair receives its own delta verification.

The deep-import comparison uses actual owner functions over the complete 2,654 slice-base and 2,653 current `src/**/*.py` file sets, with successful AST reads and current disk/tracked membership equality. Owner, policy, exception and baseline bytes are identical, and complete provisioning/traceback checks precede the comparison (`invocation/raw/deep-import-delivery-census-v2.log`, exit 0, 30.47 seconds). Guardrails measures top-level package roots: 3,298 unchanged edges, 30 additions and 18 removals reconcile 3,316 base and 3,328 current edges. Every frozen creep diagnostic matches one addition. The additions comprise 13 canonical CAS factory imports, four public CAS provider imports and 13 JSON-extraction relocations. The package owner instead uses the longest declared package and additionally sees `polisyos.runtime.quality.acquisition_executor -> polisyos.runtime.http.services.control_registry_providers`: 3,428 unchanged, 31 added and 18 removed reconcile 3,446 base and 3,459 current edges. Its 161 current outside-baseline members consist of 130 base-present source members and 31 lane additions; this is source membership, not an inherited-red or hosted-ownership claim. The full corpus is `invocation/raw/deep-import-delivery-census.json@sha256:07f972b59af66435397248bf241c850a212e5f028f8540159f93e5de39a3c747`. All additions route to architecture public-surface/import policy with Core CAS, Common serialization and Runtime acquisition owners, as `complete-pending-an-architect-decision`.

The package report retains only the first 100 global edge keys and first 25 per package pair, without naming those arrays as previews. Its predicates and counts use the complete sets before slicing; this is a display omission, not missing source measurement or a false-green verdict. The journal's earlier complete-array claim is corrected at every reference. Destination: architecture reporting backlog for explicit preview labels/full identity projection (`surface_missing` for the latter), with no verdict-policy change. Source: `tools/quality/validation/architecture_report_only_contracts.py@cd47224077c647845e633095b5efdc0f35c15cbe`, `_build_import_boundary_summary`; canonical comparison owner: `tools/devx/architecture/guardrails.py@cd47224077c647845e633095b5efdc0f35c15cbe`, `collect_deep_import_edges`. The initial one-off census stopped before edge measurement on an ordering assertion and is retained as UNRUN/non-receipt; the corrected normalized-set census supplies the evidence.

`coverage/raw/ci-original-six-station-two-final.log` exits 1: R01/R02/R05/R06/B01/B02 pass, while the L6 and phase2 importer nodes fail. The L6 path progressed beyond its first repaired data input and found deeper production-world prerequisites unavailable. The phase2 projection reaches `UnknownNodeError: scientist.node_build_literature_prior@1.0.0`; this is a registry/workflow composition failure already visible under the earlier missing-input exception, not a new ownership attribution. The exact pinned WMR artifact remains unavailable and is not substituted. `coverage/raw/grounding-risk-provisioned-final.log` separately passes the restart/missing-head node in the frozen solvers environment (exit 0); primary-environment solver absence is not used as a CAS finding.

The subsequent registered runtime contract run completed (`root/raw/runtime-contract-final.log`, exit 1, no traceback). The actual owner validator now passed and the complete byte diff is confined to the confidence-ledger projection/dependency/worker receipt binding; artifact content and frozen semantic projection remain unchanged. This is a measured drift, distinct from the prior timeout. The canonical source refresh was subsequently committed in `ce753f17b48fb9c0b00dd2753094a2350416ca38` and read back byte-for-byte; `root/raw/runtime-contract-admitted-artifacts.log` now exits 0. No governed epoch transition is inferred from receipt hashes.

The first full architecture guardrails process completed with exit 1 and no traceback (`root/raw/guardrails-final.log`). Its generator output-probe attributions are not admitted: tracked source/docs repairs continued during that process and its whole-tree before/after check observed those concurrent edits. Those lines do not prove the generators wrote outside scratch. The deciding replay ran under a total tracked-write freeze at `cd47224077c647845e633095b5efdc0f35c15cbe`; `root/raw/guardrails-delivery-frozen.log` exits 1 in 385.00 seconds, without a traceback or tree change. Runtime client, dashboard types and trust-posture generator-observed freshness pass. Deep-import additions remain `complete-pending-an-architect-decision`, without baseline sync. The separate OpenAPI byte mismatch is real and is diagnosed below; a working-checkout pass does not discharge this isolated-station failure.

The exact manifest OpenAPI output probe was replayed in retained isolation with the existing guardrails copy/provision helpers (`root/raw/openapi-isolated-replay.log`, exit 0). The complete recursive JSON comparison differs only in ten confidence-ledger dependency, worker-receipt and replay-binding fields. The isolated schema is retained at `root/raw/runtime_api_v1.isolated.openapi.json@sha256:44c39a02fbda7dd681fd039aaad083030820476e354b1849aab0fb1b0802eb07`; the working-checkout schema is `schemas/runtime_api_v1.openapi.json@1012ee05f03a96bb545e25cde36ac581d3ae0df7`. Both actual example producers were then observed by forwarding their real worker subprocess calls unchanged. Complete worker receipts and distribution inventories are retained in `root/raw/openapi-primary-bindings/` and `openapi-isolated-bindings/`; both example captures equal their corresponding full exports, and neither worker contains a traceback.

`root/raw/openapi-station-binding-comparison.log` (exit 0) compares the complete binding dictionaries before reporting their 6,423/6,420 sizes. The six differing identities are: private-only `libc.dylib=missing`; the `src` directory identity; and working-checkout-only directories `src/_build`, `src/_build/benchmark-results`, `src/_build/benchmark-results/foundry`, and `src/_build/benchmark-results/foundry/selection_history`. Production data does not differ in these consulted receipts. The complete distribution inventories also differ, so this is explicitly a different-station comparison, not a same-provision finding-count regression. Build-residue ownership and the causal effect of each package difference are `not_established`.

Bucket: SAME missing canonical station/input-basis ownership class, one level deeper under P40. The example intentionally preserves the live owner validator's dependency hashes; the isolated generator intentionally excludes `_build`. Their successful local executions can therefore disagree without a schema or policy-semantic change. The smallest missing capability is an admitted canonical station for governed OpenAPI examples, composing the owner-input basis and locked profile. The existing post-execution DependencyTracker and Foundry dependency-profile reducer do not provide that pre-execution Runtime station. The falsifier is the two completed producers with unequal admitted bytes, fully retained above. No dependency hashes were normalized away, no build residue copied into the isolated contract, and no third provisioning ladder was built. Destination: Runtime OpenAPI/generated-artifact architect plus the owner-station research backlog; `complete-pending-an-architect-decision` for canonical-station policy, with isolated freshness still FAILED. The diagnostic itself prints: “Measured: complete forwarded worker binding identities and package distributions at two declared different stations; both captures match their exports. Not measured: counterfactual causation of every package difference, canonical station policy, runtime workload, or hosted CI.”

The production WMR station residual is the SAME missing-data class one level deeper, not successive independent fixes. The root production manifest provides bundle locators/readiness rather than an owner-specific transitive input closure. The actual owner additionally composes data-state, L5/catalog, and academic SKG producers; downstream source refs exist only after loading and cannot prove absent prerequisites. No complete preflight/provision projection is exposed by this caller chain. The smallest missing capability is a canonical owner-input closure/provision manifest, routed to the production WMR station/provisioning research backlog. The retained missing-data replay is its falsifier; six additional file copies would not establish complete provision. No further data tree or provisioning subsystem is built here.

The original source-impact IDs remain historical, but their existing owner was also applied to this lane's complete committed delta. `root/raw/docs-impact-current-plan.log` rejected four current path predicates: Fabric connector docs, security docs, security runbooks and discovery-worker README freshness. A substantive current-slice impact note was added at the existing `docs/reference/documentation-inventory.md` owner, describing scanner failure, custody-preserving factory composition, unchanged JSON extraction semantics and local diagnosis steps. It makes no rehearsal or historical-disposition claim. The retained one-off planner probe emits the complete changed-path set and explicitly lists unrun child gates; it is a bounded path-coverage check, not a new product command or a substitute docs workflow. After the note was committed/read back in 7669325a63eb830e4c7d074b8389cb04c643d036, docs-impact-final-plan.log exits 0 with no current path findings; its child commands remain explicitly UNRUN.

The final invocation report is `invocation/raw/invocation-delivery-final.json`, with a class summary and changed-finding members in `invocation-delivery-final-inspection.log` (exit 0); the complete graph and unresolved sets remain in `invocation-delivery-final.json`. Generation and recomputation both exit 1 with no traceback. Its complete tracked Python denominator is 5,673 current versus 5,669 slice-base files under src/tools/tests, including 2,653 current src files; those are file counts, not function or finding counts. The final source digest is cff112caa45babf2c5bb3987b7d4875cc2434e7dd5d73f4a99a853eb2c35b77f. It retains static_path, uninvoked and unresolved_by_construction classes. Exact direct findings are `polisyos.fabric.world.store.segments.gc_world_segments` and `polisyos.fabric.world.store.snapshots.merge_world_branch`: both changed, neither lost a previously resolved path. A complete AST reference census finds re-export/lazy-export boundaries and actual test calls; `test_callers=[]` for the lazy export is a static-resolution limitation, not proof of absent tests. Both findings route to Fabric storage lifecycle integration and architecture ownership; no production scheduler/bridge is claimed. The thirteen exact new unresolved names remain in the full stdout and receipt, with their callable-escape/decorator/deferred evidence; they are not suppressed or reclassified as proven runtime non-invocation. The earlier `invocation-domain-final*` receipts bind the pre-R03 source and are historical evidence only.

The initial pre-R03 trust-posture candidate was compared with the entire slice-base artifact by claim payload identity rather than array position (`root/raw/trust-semantic-delta.log`, exit 0). All 369 claim payloads agree after excluding claim IDs, source-content digests and coordinate line/column; paths/symbols, authority, status and limitations remain in the comparison. Top-level schema/rule versions, register date and historical slice anchor are unchanged. This is generated binding freshness, not corroboration of register prose or a new custody epoch. `root/raw/openapi-scope-final.log` compares the base and initial pre-R03 OpenAPI candidate: that earlier artifact changed only confidence-ledger bindings. This does not describe the later R03 transport-example correction. The first scope probe used an underscored owner name against the actual hyphenated endpoint and failed its diagnostic assertion; that raw attempt is superseded, never counted as a product finding.

The final invocation receipt verification sequence completed after R03 on unchanged tracked Python, interpreter 3.14.3, complete installed-package fingerprint, lock and pyproject: generation 226.05 s / exit 1, recomputation 192.46 s / exit 1, corrupted-field negative 191.86 s / exit 2. Both complete positive receipts are byte-identical (SHA256 1e8ac97a63c146ad42b3ac94b66d2f6bdc781e51d3f8836c408c6ff2f77bed6a). The negative changes only denominator.source_files from 2,653 to 2,654 on a separate receipt; output says `invocation_receipt_drift`, `complete_verdict:false`, `receipt:null`, with no new receipt and no traceback. Provision equality and absence of tracebacks were checked before comparing complete finding classes and members. Commands, complete comparisons and negative verification are indexed in `invocation/raw/receipt-index.json`; the index's final custody hash is recorded at closeout. No count-only comparison was made. Large complete receipts are ignored raw evidence; output size and repeated full-AST replay cost route to the invocation instrument's performance backlog, not deletion of diagnostic members.

The canonical generated OpenAPI and trust-posture bytes have now been copied byte-for-byte from their retained producer outputs, with no manual JSON rewrite. Their source-versus-slice-base semantic comparisons are recorded above; no schema/rule/epoch transition is introduced. Post-copy registered freshness and corrupt-field checks decide admission, not the successful copy itself.

The pre-R03 post-copy trust-posture validation completed: `root/raw/trust-final-check.log` exits 0 after recompiling actual admitted sources and comparing bytes; `root/raw/trust-final-corrupt-field.log` exits 0 only because the canonical validator rejects the corrupted payload digest. Those earlier generated outputs were `schemas/runtime_api_v1.openapi.json@ce753f17b48fb9c0b00dd2753094a2350416ca38` and `apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json@ce753f17b48fb9c0b00dd2753094a2350416ca38`. Both were read back from the attached branch and equal their retained producer bytes.

Handback review found a NEW P38 selected-witness mismatch for R03: a resolvable sibling test was mistaken for the original strict node. The source table and original runtime log name `test_epoch_batch_success_example_is_owner_derived_and_strict`; complete-file AST and body inspection distinguish its `review_required` assertion from the passed wire-format sibling. All dependent R03/runner descriptions are corrected. The exact original red, subsequent owner-bridge repair, positive and registration-removal negative are recorded below. The earlier sibling receipt remains valid only for its narrower assertions. Destination: witness-selection rule P33/P38; the actual original red, rather than the documentation error, justified the source repair.

The fixture repair is committed and read back in `8ab32c51ffcf9887bc96bcaefe525704b1c16d1b`. Focused replay passes six earlier failure witnesses, including the five census assertions after the formerly unfinished hook, plus the real-child timeout negative (`coverage/raw/fixture-watchdog-focused.log`, exit 0, eleven nodes). The seventh witness, the Atlas stable arm, passes with the actual Atlas producer/admission bodies (`fixture-watchdog-producers.log`, exit 0, four nodes). Those two gates together exercise all seven original witnesses. The first unavailable-case regex matched none; the corrected explicit declaration replay passes all six cases (`fixture-watchdog-unavailable.log`, exit 0). No skipped case is counted as passed. Named TypeScript roots, lint and format checks pass; the review confirms unchanged test callback bodies except the intended actual-PNG probe. The full suite remains the separate statement-adequacy deliverable.

The whole-tree guardrails snapshot and full Vitest execution are serialized. The workflow source-flip witness uses in-memory `source_overrides`, and a complete direct/member TypeScript mutation census finds scratch-owned destinations; arbitrary aliases, embedded subprocesses and dependency side effects remain unmeasured. That bounded census does not justify a universal no-write guarantee, so guardrails runs alone under a total tracked-write freeze.

## Canonical implementation references

These pins identify committed owners, rather than copied source or derived file inventories. Exact test selectors and replay commands are in the companion runner.

- `tools/quality/validation/repository_structure_phase0.py@e9e1ba21844c57b04599d04186f461ea38105b91`
- `src/polisyos/runtime/quality/production_invocation.py@5b5d67b644c72aee8fd08fb8595aef383e2e7d14`
- `tools/quality/validation/check_production_invocation.py@453d21b89878a8c5154f1614b99f24268a8d0475`
- `apps/runtime-dashboard/scripts/check-coverage-ratchet.mjs@42da749db15a5fbe5199d9c9fb174bd044460d3c`
- `apps/runtime-dashboard/vitest.config.ts@42da749db15a5fbe5199d9c9fb174bd044460d3c`
- `apps/runtime-dashboard/src/test/evidence/persistenceProcessResult.ts@8ab32c51ffcf9887bc96bcaefe525704b1c16d1b`
- `apps/runtime-dashboard/src/test/contracts/visualRegressionHarness.test.ts@8ab32c51ffcf9887bc96bcaefe525704b1c16d1b`
- `tools/quality/validation/check_package_import_gates.py@c86aa6358ff681c42f6b7e2a09273f748d58038a`
- `tools/quality/validation/directory_health.py@c86aa6358ff681c42f6b7e2a09273f748d58038a`
- `tools/quality/validation/check_docs_accuracy.py@c86aa6358ff681c42f6b7e2a09273f748d58038a`
- `tools/ops_runners/runtime/check_runtime_api_contract.py@c86aa6358ff681c42f6b7e2a09273f748d58038a`
- `tools/ci/check_scientist_phase1_gate.py@370e715240e6e4ca9b99fad7ede3ce2a50945b92`
- `tools/quality/testing/check_fabric_exception_baseline.py@370e715240e6e4ca9b99fad7ede3ce2a50945b92`
- `src/polisyos/common/serialization.py@c86aa6358ff681c42f6b7e2a09273f748d58038a`
- `src/polisyos/core/artifacts/backends/config.py@f8cc13d514322252ceb892a3f0025aad5bc6bf5a`
- `src/polisyos/runtime/quality/acquisition_executor.py@f8cc13d514322252ceb892a3f0025aad5bc6bf5a`
- `src/polisyos/fabric/connectors/base.py@f8cc13d514322252ceb892a3f0025aad5bc6bf5a`
- `src/polisyos/fabric/world/store/segments.py@370e715240e6e4ca9b99fad7ede3ce2a50945b92`
- `src/polisyos/fabric/world/store/snapshots.py@370e715240e6e4ca9b99fad7ede3ce2a50945b92`
- `docs/reference/documentation-inventory.md@7669325a63eb830e4c7d074b8389cb04c643d036`

R03's original red and corrected positive are now the same exact selector and assertion domain. The canonical typed transport owner was always REVIEW_REQUIRED for this declared revalidation sample; removing the later duplicate restores its registration. The removal probe keeps the producer present, deletes its actual map entry, calls the same strict export test, and requires the specific missing-registration assertion. Existing Ruff F601 guards duplicate literal keys; no new scanner or policy exception was built. The test prints: “Measured: canonical typed epoch transport example registration and wire/status agreement. Not measured: persisted epoch admission, runtime status composition, clock/expiry behavior, or hosted CI.” The wire-format sibling's earlier pass remains a separate narrower receipt.

The final R03 working-checkout export passes the complete JSON scope probe in `root/raw/openapi-r03-scope.log` (exit 0): changes from `cc74d6581` are confined to the epoch-batch transport example and confidence-ledger receipt/dependency bindings. The sample target changes from `stale` to `review_required`, with the typed owner's corresponding refs/lineage/reason. No component schema, endpoint definition, governed epoch or rule version changes. The latter distinction does not erase the real sample-field changes. `root/raw/trust-r03-semantic-delta.log` compares every claim object against the slice-base artifact: all 369 payloads agree after excluding only the claim ID and immediate source-binding digest/line/column; authority, status, limitations and all other nested fields remain compared. Schema/rule versions, register date and historical slice anchor remain identical. The copied bytes, branch readback and station-bounded admission checks are recorded below.

- `src/polisyos/runtime/http/openapi_contract.py@b6e5db7b60b86ba73eeddd62e9a90f02844f825c`
- `tests/unit/runtime/http/test_runtime_api_contract_hardening.py@b6e5db7b60b86ba73eeddd62e9a90f02844f825c`

The final generated artifacts were committed and read back byte-for-byte in `1012ee05f03a96bb545e25cde36ac581d3ae0df7`: `schemas/runtime_api_v1.openapi.json@1012ee05f03a96bb545e25cde36ac581d3ae0df7` and `apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json@1012ee05f03a96bb545e25cde36ac581d3ae0df7`. They exactly equal their retained canonical producer bytes. `root/raw/runtime-contract-r03-final.log`, `trust-r03-final-check.log`, and `trust-r03-corrupt-field.log` all exit 0; the last succeeds because the actual validator rejects its corrupted payload digest. Those receipts supersede the earlier source-state freshness receipts without erasing them. The final package measurement is `root/raw/package-r03-final.log` (completed FAILED/1, no traceback); its complete finding-record classes and identities, supplemented by the full owner-derived edge census rather than a count comparison, support the per-item handback above.
