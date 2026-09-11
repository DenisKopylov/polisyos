# Original CI findings: repair decisions and bounded local receipts

Stage 1, 2026-09-11. Slice base `cc74d6581`, attached
`codex/instrument-honesty`. Execution follows the committed/read-back decisions
and follows invocation and dashboard implementation. Root serializes shared
files. This decision does not claim hosted CI success.

## Evidence identity and the unit of work

The triage is C-CI in
`docs/superpowers/specs/2026-09-10-apparatus-station-and-ci.md@cc74d6581`.
Its concrete finding IDs are `CI-F*`, `CI-S*`, `CI-R*`, `CI-B*`, `CI-C*`;
those identities, not the parent debt row's prose, drive this work. All five
original failed-job logs were downloaded again using ordinary read-only `gh`
commands. The complete bytes match the five SHA256 values recorded by C-CI.
They are retained in `docs/superpowers/journals/instruments/root/raw/` as
`run-<id>-failed.log`. Run IDs: Fast 34196405835, Standard 34196405796,
Runtime 34196405891, Fabric 34196405795, Canary 34196405782. Historical commit
is `20082e545ba89cefc2fd913e1723f6ef7c63df39`. No other lane branch is needed.

CI-RESEARCH-01: decoding complete JSON objects in the original Fast log finds
the primary package report's full 243-member findings array. Its owner field is
`check`; grouping by another guessed key would produce a meaningless count.
CI-RESEARCH-02: every final FAILED line in the original Runtime log gives six
test nodes, including both inadequate metrics collaborators. CI-RESEARCH-03:
the Standard log includes interpreter failure for S01/S03 and executable
provenance mismatch for S02. They are distinct classes. CI-RESEARCH-04: seven
publication-aware Docs Contract links fail even though the separate Link Check
succeeds. Raw source files, generated source owners and new command receipts
will decide the current state; these historical facts do not establish it.

Do not add counts from test nodes, package findings, jobs and derived aggregates.
Compare complete identities/classes before drawing a change conclusion. A
traceback or unequal provisioning makes an aggregate comparison inadmissible.
Current targeted replay is bounded local evidence, never a substitute for a
cancelled hosted job. Historical ownership is not_established unless the exact
slice-base replay and a complete disjoint-input proof both establish it.

## Strategy and non-test callers

Reuse current owners first; most findings are failures of existing contracts,
not justification for new subsystems. Repair real producer/consumer defects at
their owning seams, then regenerate only the affected outputs through canonical
commands. For inaccurate instruments, preserve real findings while naming what
their scan did not measure. Do not quiet a scanner through thresholds, expiry
extensions, allowlist additions, skipped files, or new marker conventions.

Existing production paths to compose:

* `execute_live_catalog_acquisition` is called by the acquisition runtime's
  catalog flow. Compose Core's `ArtifactStoreConfig`/`build_artifact_store` and
  existing injectable registry providers, keeping quarantine/admission semantics.
* `ConnectionConfig.redacted` -> `scan_secret_and_pii` -> `PromptSanitizer` is
  consumed by connector logging and connection-configuration custody hashes.
  Preserve scanner-owned redaction vocabulary and immutable Mapping output;
  never replace a redacted credentials mapping with an apparently empty one.
* Runtime container overrides feed application construction, CAS metrics and
  JWT/cell middleware. Test collaborators must satisfy that actual protocol;
  adding production `getattr` fallbacks would hide the failed contract.
* OpenAPI examples/types are emitted by `runtime/http/openapi_contract.py` and
  canonical schema/type generators, then consumed by clients and strict contract
  tests. Fix clocks/fixtures at their owner before regenerating; status and epoch
  semantics are not snapshot conveniences.
* `tools/ci/check_scientist_phase1_gate.py` is already invoked by
  `polisyos-tools ci check-scientist-phase1-gate` and Core Runtime workflow. Its
  current deep-copy predicate searches an exact substring, although its key
  claims absence of live hot-path copies. AST source analysis can measure
  syntactically explicit copy requests, not liveness or execution cost. Preserve
  the copy finding, make that limitation explicit and test whitespace/alias/
  dynamic-argument cases. Never remove defensive nested-copy isolation merely
  to satisfy a source-string check.
* Package/import, directory, docs accuracy, generated tool-reference and broad
  exception owners already have CLI consumers. Extend them only when an actual
  current falsifier identifies a measurement defect. No new path-only executable
  is planned; anything new must first receive a discoverable non-test caller in
  an addendum committed before its source implementation.

## Finding-by-finding decisions

| C-CI IDs | Owner / seam / decision | Deciding falsifier and bounded outcome |
| --- | --- | --- |
| F01 | Workflow policy; retain current valid workflows. | Revalidate each workflow actually changed; no historical green claim about future edits. |
| F02 | `architecture/imports/exceptions.toml` and exception validator. | Full current expired-exception identity set; an expired still-used exception stays rejected. Do not extend dates without architectural validity evidence. |
| F03 | Import boundary owner and current edge graph. | Compare edge identities, distinguish permitted import from increased hidden coupling; no baseline acceptance by count. |
| F04 | Dynamic import discovery/registration owner. | Reconcile full current AST-derived source and registered set; unresolved receiver/module remains explicitly unmeasured. No sampled registration patch. |
| F05 | Cycle graph owner. | Real reachable SCC identities versus scanner representation; no removal of an edge from inventory to erase a cycle. |
| F06 | Shim policy/expiry owner. | Exact expired shim and actual legacy consumer; remove migrated legacy or hand back a dated architect decision, never renew by convenience. |
| F07/F08 | Importable-root classifier. | Tracked Python under architecture/docs is non-product source; ignored raw scratch must not become committed-tree evidence. Real absent policy must remain visible. |
| F09/S05 | Existing vendor directory owner. | Admit the actual vendor role only if its documented wheel custody policy supports it; never erase the dependency. |
| F10/F11 | Non-product-root availability classifier. | Empty clean checkout separately lacking production_data and runs must name absent optional mounts, not assert they were measured. |
| F12 | Common package/root policy and `common/llm_json.py`. | Inspect real canonical ownership and consumers; use an existing home or supported facade, not a catch-all exception. |
| F13 | Single-file-shell policy. | Reconcile all four historical identities to current source; intentional shell requires its real role/test, not a baseline number. |
| F14/F15/F16/F17 | Module-size producer and builder/lifecycle/advisor/OpenAPI owners. | Current subject-to-logical-metric findings, preserving their distinct limits. No raw-line compression, limit increase or unrelated decomposition. Required decomposition/limit adjudications are explicit architecture handback with actual findings. |
| F18 | Deep-import owner. | Exact current edge; new module creep is complete-pending-an-architect-decision. Never run sync. |
| F19/F20/F21/F22 | Changed-source docs/security/runbook contracts. | Actual range and source-impact coverage; a local later range cannot retroactively establish historical documentation. Repair current missing required docs only at their owner. |
| F23 | Auto-discovered tools reference. | Regenerate from CLI registry after new invocation command, `polisyos-tools docs --check --output docs/reference/tools.md`; corrupt copied output must reject. |
| F24/F25/F26 | Hosted ABI/dependency/aggregate workflow states. | Retain skipped/event-conditional/derived semantics. No local pass can repair the absent hosted verdict. |
| S01/S03 | Dashboard Python-child station. | Exact automated-capture/workflow test files and their corruption/source-flip negatives using current local interpreter. Existing base repair is reverified, not assumed from triage. |
| S02 | Evidence producer/consumer executable provenance. | Reconciliation test file rejects a different executable even if schema/content look valid. Do not count S02 as a third missing-package case. |
| S04/R04 | OpenAPI snapshot and generated TS producer. | Current exact hardening node and canonical drift checker; compare same provisioned source, correct owner before regeneration. |
| S06/S07/S09 | Dashboard fixture roles. | Actual two directories versus declared fixture role; the count is a derived aggregate, not a third missing fixture. |
| S08 | Directory documentation denominator. | Complete tracked subtree inventory and actual missing README; preserve floors and distinguish untracked raw content. |
| S10/S11/S12/S13 | Hosted cancelled/skipped jobs. | Explicit unmeasured omission in the local completion report; no full replacement suites are authorized. |
| S14/S15/S16 | Historical smoke/performance/aggregate. | No new repair inferred from successes or dependency failure. |
| R01 | Core artifact-store factory and acquisition executor. | Exact architecture node plus real injected-store acquisition failure/success witnesses; constructor relocation must preserve artifact custody. |
| R02 | Registry provider and acquisition executor. | Exact architecture node plus injected absent/valid source-profile behavior; no inline singleton under a different spelling. |
| R03 | Epoch batch example owner. | Exact strict owner-derived example node; explain stale/review_required through fixed clock/expiry, not expectation weakening. |
| R05/R06 | Runtime test metrics collaborator. | Both named original nodes plus actual counter use/injection identity; align collaborator protocol rather than production fallback. |
| R07/R08 | ADR index generator/publishing policy. | Both links must resolve in published page universe, or become accurate source-only references; actual link checker rejects excluded-target fixture. |
| R09/R10/R11/R12 | Brand source-of-truth publication. | Four distinct links and target publication decision; no broad exclusion. |
| R13 | Research-pipeline documentation publication. | Correct published reference or explicit repository-source link; no inference from local file existence. |
| R14 | Existing mutation runner/CLI. | Preserve current fail-closed unsupported-platform UNRUN and Linux evidence distinction; do not claim native mutant execution from skipped tests. |
| R15 | Phase 1 source-copy scanner. | AST variations preserve findings, unknown dynamic deep argument is named unresolved, absent source is UNRUN; defensive clone behavior stays intact. Liveness/hotness remains explicitly unmeasured even with clean syntax scan. |
| R16/R17/R18/R19/R20 | Hosted typing/phase0/link/performance/review state. | Keep cancelled/success/skipped classes; no broader local testing inferred. |
| B01/B02 | Connector/scanner redaction composition. | Two original exact nodes plus immutable mapping and arbitrary credential-key secret witnesses; original source remains immutable, output retains redaction evidence. |
| B03/B04 | Segments/snapshots exception hygiene. | Classify each actual broad-handler site and preserve storage cleanup/rethrow semantics; no baseline-number refresh. |
| B05/B06 | Historical race/leak/performance successes. | No repair or current verdict inferred. |
| C01 | Canonical setup action/canary orchestration. | Reverify named current orchestration nodes; absence of requested prerequisites is UNRUN before workload. No live-provider invocation. |
| C02 | Credential/event quarantine. | Intentional hosted omission stays named, not a product pass. |

## Shared changes and effects on the other lanes

All edits to pyproject, lockfiles, lefthook, workflows and architecture files go
through root. None is pre-authorized as a blanket baseline refresh. Targeted
architecture role/documentation repairs may alter gate inputs for every lane;
the final frozen receipts must all use that same state. No import exception
expiry, size limit, coverage floor, delta tolerance or deep-import baseline will
be increased by this plan. Dependency provisioning is frozen at the slice lock;
an online cache refill is station repair and does not edit the lock.

Invocation auto-discovery adds a tools-reference row, so the docs owner must
regenerate after its source is final. Coverage script/config changes can alter
executable provenance dependencies; existing producer/consumer negatives decide
whether regenerated evidence is admissible. The unchanged coverage floor is
binding. Runtime/Fabric fixes can alter owner-derived hashes in OpenAPI/schema
surfaces; use the real producer, retain complete before/after class sets, declare
any governed epoch transition relative to `cc74d6581`, and never declare an epoch
merely because a generated file changed. No hosted workflows are dispatched.

## Execution and receipt protocol

First finish independent invocation and coverage source work, review it, and
freeze. Then repair CI items, with red tests immediately preceding source edits.
Existing exact failing tests are admissible red witnesses; no constructor-only
replacement. Root may delegate nonoverlapping Runtime/Fabric and scanner/docs
repairs once the first workstreams finish, keeping at most three concurrent
workstreams and retaining sole ownership of shared files.

Final runner names every test file and node explicitly. Eight initial original
nodes are the six Runtime contract nodes and two Fabric nodes listed in C-CI;
no directory-wide pytest, backend verify or CI parity. Python AST enumerates
definitions including async, TS AST counts calls. Dashboard full coverage is
the sole full-suite exception, with complete output in ignored raw/.

Every gate is the only command in its shell invocation. Capture its actual exit
status, full output, elapsed time and provisioning identity. No `gate; echo $?`.
The completion journal quotes every touched instrument's actual omission
sentence and negative. CLI FAILED means completed rejected measurement;
UNRUN means no complete verdict and findings beside it are partial. Existing
instrument-specific result carriers are preferred over a new CI orchestrator.
Hosted cancelled/skipped scopes are explicitly omitted in that local receipt.

### Root execution refinement: concrete existing owners

CI-F12 composes `common/serialization.py`, the already-public JSON owner.
The complete tracked `.py` census under `src/`, `tests/`, and `tools/` contains
5,670 files with no AST parse failures and finds thirteen non-test importers
of `common.llm_json` plus its behavioral test file (retained census:
`instruments/root/raw/common-json-imports.json`). Move the existing extraction
functions unchanged into serialization, switch every importer, and remove the
unregistered implementation. `runtime.quality.design_generation` and the
Scientist agent, policy-design and validation flows remain its non-test callers.
This library operation must not get a separate CLI: those flows consume its
candidate JSON and retain their own validation/authority boundaries. The
falsifier calls extraction through the canonical owner and rejects invalid
JSON; an AST comparison must preserve the moved function bodies. No shim or
root-file allowance is added.

CI-F07–F11 and S05–S09 compose existing directory contracts. Declare the actual
non-product evidence roles for architecture/docs, the locked wheel-input role
for vendor, and the ignored command-timing role for `.polisyos-tools` (writer:
`tools.lib.timing`). Existing `local_only` + `ignored` contracts distinguish
absent data/run mounts from missing committed source; output names every such
omission. The Python-root denominator becomes explicitly tracked `.py` files,
while filesystem-presence/residue checks keep their distinct scope. Missing Git
or contracts yields UNRUN. Register the two actual dashboard fixture directories
and supply local documentation for the complete measured set of undocumented
high-volume subtrees. These shared changes affect every lane's directory and
package gates, and README additions affect tracked volume; no floor or exception
expiry changes. Documentation presence is explicitly not a substance verdict.

CI-R07–R13 publishes the approved native-value ADR and the reference research
pipeline through the existing MkDocs fragment generator. Atlas's governing
record depends on unpublished plans/decisions; its four published references
become explicitly identified repository-source references, preserving that
publication boundary. The docs instrument must report unavailable YAML/scope as
UNRUN and name prose truth/deployment as unmeasured. Shared MkDocs regeneration
affects all lanes' published page universe; it grants no new policy authority.
The generator also exposes obsolete Ruff overrides. Delete an override only
when its exact source path is absent, and regenerate from its fragment; never
transfer an exemption to a same-named but differently owned file.

Source freeze -> all reviews -> expensive coverage wave once. Any new blocking
review after freeze is batched before rerun. Changes commit at clean boundaries;
branch attachment and branch readback are checked each time. No stash storage,
history rewriting, push, other lane branch, DEBT-REGISTER or LEDGER edits.

## Pattern pass and stopping property

P05/P04/P09: status and failure semantics must not become green by omission.
P29/P32/P33: behavior and negative evidence, including present-but-fake inputs,
not existence of marker words. P35/P36: original complete logs and finding IDs,
never debt narrative as evidence. P37/P38: provisioning and proxy predicates
must disclose their limits. P31/P40: bucket a finding before repair; a second
same-class escape widens the owner mechanism or establishes a bounded residual
with its smallest missing capability and falsifier, not endless local patches.
P41: inherited is not established without exact-base replay and disjointness.

Existing capability chains are production-wired but have verification/protocol/
surface gaps identified above; no new policy authority is built. Developer CLI
and audit receipts are the external surface; policy dashboard/API changes beyond
the named existing paths are `surface_out_of_scope`. Missing hosted execution
remains `verification_missing`. Required architecture approvals are handback
items labelled complete-pending-an-architect-decision, not blocked and not fixed.


## R01 addendum: complete concrete-CAS caller denominator

The first repair replay left the same R01 class outside acquisition execution;
this is not a new class or evidence that the original row closed. The deciding
AST gate scans every Python source below `src/polisyos/runtime/`, including
nested functions and async definitions. The first current output is
`docs/superpowers/journals/instruments/coverage/raw/ci-owner-seams-green-first.log`.
Widen the repair to the complete remaining AST constructor/import set, never
rename `FileSystemCAS` into a scanner-blind alias. Root commits and reads this
addendum before those sibling owners are changed.

The existing production caller set, obtained by AST parent traversal over the
complete runtime `*.py` set, is:

| Runtime owner path (under `src/polisyos/runtime/`) | Existing non-test caller(s) | Preserved backing/options |
| --- | --- | --- |
| `http/services/public_decision_verification_configuration.py` | `build_public_decision_verification_service` | `root / "cas"` |
| `quality/acquisition_epoch_admission.py` | `run_admission` | `request.cas_root` |
| `quality/acquisition_planner.py` | `RealAcquisitionOwnerGateway._capture_skg` | `self._repo_root / ".n7-live-cas"` |
| `quality/adaptation_transition.py` | `AdaptationTransitionRuntime.open` | `root / "cas"`; **tenant_id and cell_id** |
| `quality/confidence_ledger.py` | `ConfidenceLedgerSession.from_repo` | `root / ".polisyos/cas"` |
| `quality/epoch_custody_audit.py` | existing `main` command owner | `arguments.cas_root` |
| `quality/generation_cycle.py` | `GenerationCycleController._begin_source_run` | `root / ".polisyos/runtime/generation_source"` |
| `quality/grounding_calibration.py` | `resolve_grounding_proof_world_input`, `produce_grounding_proof_world_input` | `location` |
| `quality/grounding_risk.py` | `GroundingRunBudget._open` | `owner._root / "cas"` |
| `quality/intervention_substrate.py` | `resolve_law_bound_lever`, `intervention_substrate_behavior_report` (two sites), `_production_composed_world_model_record` | existing `.polisyos/cas` roots and `.tmp/gy-s-composed-wmr-cas` |
| `quality/workspace/foundry_consumption.py` | `verify_staged_foundry_input_state`, `_verify_method_replay` | existing isolated temporary CAS roots |
| `quality/workspace/loop.py` | `WorkspaceLoop._phase2_store` | existing `tempfile.gettempdir() / "polisyos-gy-phase2-cas"` |

`quality/workspace/agent_proposal_bridge.py` has concrete import/annotations but
no constructor; it consumes an injected store. Move all touched consumer
annotations to the public `ArtifactStore` protocol and concrete write-option
imports to their public write contract, while preserving actual read/write/
verify behavior. Do not alter authority, temporary-root selection, artifact
kinds, evidence semantics, tenant ownership, registry policy, or generated
surfaces. The factory is a library dependency with the named callers above,
so it should not become a new `polisyos-tools` command. The existing
`epoch_custody_audit.main` discoverability remains separately bounded; this
repair does not add or advertise a path-only executable.

Compose `polisyos.core.artifacts.backends.config.ArtifactStoreConfig` and
`build_artifact_store`. The existing factory lacks the tenant/cell constructor
options required by adaptation custody. Extend that same factory with optional
`tenant_id`/`cell_id` keyword arguments for its filesystem backend. Reject an
explicit ownership scope on any other backend, because that factory cannot
establish the equivalent custody there; do not silently drop those arguments.
The production caller of this extension is `AdaptationTransitionRuntime.open`.
No new production helper or module is needed. Two consumers additionally
need the filesystem root: adaptation's process lock and foundry's independent
method replay directory. Compose the existing `infer_artifact_store_config`
capability, requiring a filesystem backend and nonempty root before using
`Path(config.root)`. An injected store without that configuration refuses that
filesystem-dependent operation; it must not become a backend-neutral claim.
Preserve the existing lock path and replay directory exactly. Other callers
retain their existing default behavior and all other lanes see the same public factory;
there is no dependency or configuration-file change.

Falsifiers: real factory-created scoped stores must preserve same-owner reopen
and reject a different tenant/cell over identical bytes; unsupported scoped
backend must refuse before constructing a remote store. The new acquisition
store injection additionally gets a different-backing negative: independent
Fabric writes must fail reopen and emit a rejected quarantine terminal, never
`measured_pending_passport`. Keep the two existing R01/R02 AST tests as the
complete structural gate and name focused existing importer behavior nodes in
the final runner. Production CAS type annotations alone do not prove custody;
the factory and acquisition negatives do. No full runtime test suite is allowed.
The import gate still does not resolve arbitrary alias/dataflow constructions,
external plugins, or dynamic factories; a structural pass is not a claim about
those paths. Any new deep-import finding routes to the architect with status
complete-pending-an-architect-decision, and no baseline sync is authorized.

### R04 refinement: replay the complete TypeScript producer

Current replay of both canonical package generators changes no committed bytes.
The strict test's `_render_openapi_typescript` instead runs raw `npx` output and
omits the existing recursive-type normalizer. Its byte comparison measures a
different producer from the one that owns the committed artifact. This is P38,
not evidence that regeneration repaired a stale file. Compose the existing
locked workspace executable and
`packages/runtime-api-client/scripts/normalize-recursive-openapi-types.mjs` in
that test helper. Its callers are the strict shared-types and deterministic
schema tests; it is test infrastructure and must not become another production
CLI. Replace the obsolete generator-string assertions with execution of the
locked tool's version contract; the existing scratch-output test exercises the
real package and dashboard commands. Update the package README's stale standalone
npx instruction to the actual package owner. No generator, schema, lockfile or
policy authority changes are planned. The falsifier is raw unnormalized output:
it must differ from the committed canonical types, while the complete producer
replay must match. Print the byte-comparison scope and omit runtime client
behavior/endpoint execution/hosted CI explicitly. This touches a shared consumer
test and README, so root serializes it; the dashboard coverage floor and globs
are unaffected.

### Frontend full-wave refinement: fixture liveness and a PNG removal probe

The authorized full coverage command on frozen dashboard source at
`a1e93d1f3beb1eee4e0c31411b7ac81d04685aa2` completed with exit 1 after
3,191.52 seconds. Its complete output is
`docs/superpowers/journals/instruments/coverage/raw/full-vitest-coverage.log`.
No coverage directory or summary was produced; the actual ratchet therefore
returns UNRUN 2 in `raw/ratchet-after-failed-full-wave.log`. This is no coverage
ratio measurement, and no earlier report is admitted as this run's result.
The complete failure classes are one PNG removal assertion and six outer
fixture watchdog expirations, including a beforeAll that prevented five census
assertions from running. This is not hosted CI evidence or inherited-red proof.

| Exact failing fixture | Observed duration / outer watchdog | Class and property left unmeasured |
| --- | --- | --- |
| `CycleBoardConsumerCensus.test.ts`: production-census beforeAll | complete hook duration unavailable / 45 s | UNRUN full typed consumer census; five dependent assertions skipped |
| `visualRegressionHarness.test.ts`: screenshot-reference/snapshot one-to-one | 241 ms / 20 s | FAILED removal probe selected a non-PNG companion instead of measured evidence |
| `atlasSurfaceReadinessReconciliation.test.ts`: zero-instance stable arm | 54.735 s / 20 s | UNRUN complete real producer plus sequential admission/refusal comparisons |
| `ds16SuccessorContainment.test.ts`: production mount graph | 22.968 s / 20 s | UNRUN full reachable mount census and malformed-mount negatives |
| `confidenceLedgerRiskSpend.test.ts`: synchronous transport-byte ownership | 21.666 s / 20 s | UNRUN real protected-query admission and defensive-copy assertions |
| `posture.test.ts`: capture before strict validation | 21.194 s / 20 s | UNRUN real loader, captured bytes, and cache/fallback contract |
| `trustPostureTwin.test.ts`: every ordered public claim field/DOM drift | 77.230 s / explicit 60 s | UNRUN full committed-artifact DOM parity and every declared mutation |

The measured mechanism is fixture completion plus its semantic assertions;
these tests contain no elapsed-time performance assertion. The confidence
ledger's step/work bounds and timeout refusal are semantic product contracts
and remain unchanged. Neither the observed fixture times nor a passing replay
establish production latency. The repeated outer-timeout finding is the SAME
class at further callers (P31/P40), so compose one existing watchdog policy
across the bounded actual fixture caller set, rather than adding deadline
literals for the first three witnesses. Do not change global Vitest defaults,
coverage configuration, statement floor, tolerance, product budgets, artifact
populations, DOM mutation populations, or the source census.

Owner composition: extend the existing fixture owner
`src/test/evidence/persistenceProcessResult.ts` with
`evidenceFixtureWatchdog`, returning suite timeout options backed by the existing
`PERSISTENCE_TEST_TIMEOUT_MS` (240 seconds), and printing its measurement scope.
Keep `PERSISTENCE_CHILD_TIMEOUT_MS` (180 seconds), the existing real-child UNRUN
parser, and the selected repository interpreter unchanged. This fixture policy
already states that its measured complete replay budget is a liveness watchdog,
not a latency assertion. It comfortably encloses the completed body durations
above; it does not promise that arbitrarily many sequential children can each
consume their maximum budget. Expiration still means no complete fixture verdict.
No automatically escalating timeout is introduced.

The complete tracked `.ts`/`.tsx` denominator under dashboard `src/` and
`scripts/` contains 1,117 paths: 1,113 source-root paths and four script-root paths.
Tracked and on-disk membership agree. Relative to the earlier source-only census
at the Stage 1 decision, the source member delta is exactly the three new
behavioral test files; the four script paths were outside that earlier root.
This is an explicit member/root comparison, not a finding-count comparison.
AST import/call traversal over that denominator identifies these fixture
consumers for the owner paths implicated here:

- `src/test/evidence/atlasAutomatedEvidenceCapture.test.ts`: canonical capture
  and Core persistence adapter.
- `src/test/evidence/atlasHealthMetrics.test.ts`: real health producer and
  persistence, including its producer beforeAll.
- `src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts`: real stable
  negative-control production and repeated independent admission.
- `src/test/evidence/evidenceProducerExecution.test.ts`: both real producer
  entry points under unavailable-execution conditions.
- `src/features/runs/domain/confidenceLedgerRiskSpend.test.ts`: both strict
  admission and shared protected-query suites.
- `src/features/trust/domain/posture.test.ts`: real artifact admission/loader.
- `src/features/trust/export/trustPostureTwin.test.ts`: full artifact DOM twin;
  replace its witnessed 60-second outer override with the shared policy.
- `src/features/runs/routes/CycleBoardConsumerCensus.test.ts`: full production
  TypeScript program and resolved-symbol census beforeAll.
- `src/features/runs/components/ds16SuccessorContainment.test.ts`: all actual
  `mountGraphCensus` callers and sibling malformed-mount controls.

Compose at suite scope so siblings inherit the same liveness contract. Bind
health/census producer hooks explicitly to that existing budget. Preserve the
CycleBoard's separate 45-second array-assertion budgets, the health DS18
60-second explicit assertion budget, existing explicit persistence budgets,
and the workflow subprocess's already composed 60/65-second child/parent
budgets. The parser-only contract file remains under its short existing limits,
including the real-child 50-ms timeout negative. That file does launch small
real processes; it does not replay the canonical full Atlas producer/admission
fixture. Direct/member calls and imports are resolved in this census, not
arbitrary dynamic aliases, other file types, or every possible downstream
integration suite. Those are named limits, not an exhaustive invocation claim.

The non-test launcher is the existing dashboard package Vitest/coverage command
through `vitest.config.ts`; this helper is test infrastructure used by the named
suites, not a new production capability or path-only CLI. It should not be
registered as a `polisyos-tools` command. Existing production callers of the
exercised owners remain `useConfidenceLedgerRiskSpend`, the confidence ledger
DOM twin, `TrustPosturePage`, the Atlas scripts, and the existing TypeScript
analyzers. No production caller, generated artifact, API, backend admission,
shared dependency/configuration, or other lane's runtime behavior changes.
Root serializes this decision and all subsequent commits.

The watchdog output must say: "Evidence fixture watchdog measures completion
of the named suite's assertions. Not measured: production latency, paths outside
this suite, or hosted CI. A watchdog timeout is UNRUN for the unfinished fixture,
not a completed semantic verdict." The existing real-child timeout negative
must still produce `PersistenceExecutionUnrunError` with `UNRUN` and
`ETIMEDOUT`; unavailable-producer negatives must remain loud. The already-red
full-wave outer timeouts are the negative for unfinished assertions. Focused
replays must preserve complete assertion bodies and exercise the actual owners;
no success may be inferred merely from the new timeout option or printed text.
Production Atlas child sites without a declared child timeout remain a bounded
fixture-liveness research finding, not a silent claim that every production
process is bounded by the test policy.

The visual failure is a NEW class relative to those watchdogs: a P38 probe
removed an out-of-domain member. The complete snapshot directory is 22 PNGs
plus `README.md`; the README was added by this lane's `c86aa6358` documentation
change. `committedSnapshotRefs` correctly measures only PNGs, but `.slice(1)`
removed README and left the measured set unchanged. Select the removed member
from the actual PNG set and retain the orphan-PNG and AST dynamic-name
negatives. Explicitly prove that added README and other non-PNG companions do
not change the measured set. Keep all PNGs and the mandatory README. Print:
"Visual harness measures literal executable screenshot references and committed
PNG names. Not measured: screenshot rendering, pixel equality, or non-PNG
companions." The existing Playwright configuration and visual suite remain the
actual rendering owners; this contract test is their AST/name reconciler, not
an additional CLI.

Acceptance: exact seven failed fixtures (the census via its exact file and all
five named dependent nodes), the owner timeout/unavailable-execution negatives,
and relevant sibling fixtures pass under named targeted invocations; source
review then freezes this delta before one complete coverage replay. The latter
must produce a fresh complete report and the unchanged ratchet must decide its
ratio. Any further timeout is still UNRUN, and any semantic assertion failure
gets its actual class; neither may be erased into an omission. Pattern pass:
P29/P32 substance, P31/P40 class repair, P35 complete denominators, P38 probe
scope, P41 no inherited-red attribution. Residual capability labels are
`verification_missing` where fixture execution did not complete and
`surface_out_of_scope` for production latency/hosted execution in this lane.

### R03 exact-witness refinement: duplicate transport-example registration

The original strict selector is
`tests/unit/runtime/http/test_runtime_api_contract_hardening.py::test_epoch_batch_success_example_is_owner_derived_and_strict`.
The real replay now reaches and reproduces `stale != review_required` in
`root/raw/epoch-original-strict-final.log` (exit 1). The separately passing
wire-format sibling is not the original witness. This corrects a NEW P38
handback-selection error; no historical ownership is inferred.

A complete AST walk of every dictionary in
`src/polisyos/runtime/http/openapi_contract.py` finds one duplicate constant
key: `admit_epoch_validity_batch`. The initial value calls
`_epoch_validity_batch_example()`; a later handwritten value silently replaces
its entire payload with `stale`. The typed producer already emits
`DecisionValidityStatus.REVIEW_REQUIRED` for its declared law-revalidation
scenario. There is no clock or expiry in this producer. Independent source
review confirms this cause; changing clocks or weakening the expectation would
repair the wrong property.

Delete the later handwritten entry and compose the existing typed transport
example owner. Strengthen the exact original test to compare the emitted example
with that owner, preserving its status and strict DTO assertions. A removal
probe must remove the actual registration and make the same exported-example
consumer fail; shape or a surviving success exit cannot substitute for the
missing owner bridge. Existing Ruff F601 is selected and this file does not
exempt it, so the generic duplicate-literal class already has a canonical
checker. Use that existing guard rather than building another source scanner.
Runtime-computed keys and unpacking are outside this constant-key evidence.

Production caller: `create_app` -> `install_runtime_openapi_contract` ->
`_custom_openapi` -> `augment_runtime_openapi` consumes this existing example
map. It is part of the existing registered OpenAPI exporter and contract checker;
no new CLI/module is required. This owner constructs a typed transport sample,
not persisted epoch-admission evidence. Actual batch admission preserves
verifier-admitted target statuses and composes mixed outcomes through the
existing status lattice. Those authority, clock, custody and status-composition
seams remain unchanged; REVIEW_REQUIRED is not imposed on all runtime epochs.

Root serializes canonical OpenAPI regeneration and all commits. The schema's
sample bytes will change for every downstream lane consuming it; clients still
receive the same strict DTO schema and transport types. The change also moves
source-derived provenance bindings; recompute through registered owners, never
edit their hashes by hand. No governed epoch bump is planned: relative to the
slice base `cc74d6581`, this corrects a documentation sample and its source
bindings, not an admitted transition or rule version.

Acceptance is the exact original strict node plus its owner-bridge negative,
Ruff over the two named Python files, canonical schema/client freshness and
corrupt-field checks. Finish review before the next expensive wave. Because
these Python files intersect the complete invocation denominator, its prior
receipt sequence is retained as evidence for its earlier source state and a new
final generation/recomputation/corruption sequence must use fresh output names.
The dashboard's full coverage is held until generated artifacts settle.
Pattern pass: P05/P04 preserve authority/status, P27/P31 remove owner bypass,
P29/P32 exercise the real exported consumer, P33/P38 select the actual witness,
P35 complete constant-key census, P41 historical ownership not established.
The transport sample's persisted-admission surface is explicitly out of scope.
