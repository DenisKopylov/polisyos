# Import policy: candidate adjudication of the 18 edge classes

**Pinned repository state:** `b18937856c6dafe5cb482a7110abb279c5367d85`

**Branch:** `codex/import-policy-18-class-adjudication` (attached)

**Authority status:** research evidence and candidate dispositions only. The package owners and
`team-architecture` have not ratified these rows, and this report does not choose a policy model.

## Result

The complete population is 88 importing statements in 45 source files. Applying the requested
definitions strictly gives this partition:

| Candidate disposition | Statements | Distinct source files | Fully qualified imported bindings | Named owner teams that must participate |
| --- | ---: | ---: | ---: | ---: |
| `respell` | 0 | 0 | 0 | 0 |
| `export` | 0 | 0 | 0 | 0 |
| `relocate` | **76** | **35** | **130** | **9** |
| `ratify` | **6** | **6** | **3** | **5** |
| `ambiguous` | **6** | **5** | **9** | **5** |
| **Total** | **88** | **45 unique** | **142 unique** | **11 unique** |

The file counts by disposition overlap once: `ir/observation/contract_compilers.py` contains both
a `relocate` row and a `ratify` row. The 142 bindings are module-qualified; there are 141 distinct
unqualified imported names because `SearchIteration` names two different objects in two classes.

The zeroes are substantive. Several symbols are re-exported somewhere, but a root-facade spelling
cannot cure a forbidden package direction. Five initially plausible DataForge re-spellings also
failed the strict test: the replacement search and Fabric loader APIs are different objects with
different call, validation, or exception semantics. None is an import-path-only change.

`ratify` below means “the evidence supports asking the owner to ratify this dependency.” It does
not mean that this report has changed or approved policy. The six `ambiguous` rows include the four
unadjudicated rows that the task explicitly reserves for a later ruling.

## Denominators and independent derivations

### Current linter state

Two independent complete-set derivations agree:

1. The plain linter, with no `--allow-type-checking`, scanned all **2,576 Python files** under
   `src/` and reported **88** violations: `ARCH001 78`, `ARCH002 5`, `ARCH004 4`, `ARCH006 1`;
   **84 lapsed cover + 4 unadjudicated = 88**; exit 1; `Allowed exceptions: none`.
2. A standalone AST walk of the same 2,576-file denominator, without importing linter code,
   reconstructed the policy predicates and produced the same 88 exact `(path, line, module)`
   tuples, rule split, population split, and 45-file denominator.

The exception register has **23 entries, all lapsed**: 15 expired on 2026-07-01 and 8 on
2026-07-30. A TOML-object enumeration and an independent anchored text enumeration agree on all
three counts. The 23 records cover 84 current rows. The four unadjudicated rows match no record.

One inherited denominator is corrected rather than silently reconciled: the task described
`data_forge -> lex` as 21 statements across 11 files. The complete AST census and an independent
enumeration of the exact table coordinates both produce **21 statements across 10 files**. The 21
rows are unchanged; the supplied file denominator was high by one.

There is one command-semantics trap worth recording. Adding `--allow-type-checking` makes the
linter *skip* four lapsed `TYPE_CHECKING` references, yielding 80 lapsed + 4 unadjudicated = 84.
The task's 88-row denominator is the plain, no-flag predicate executed by Fast PR. The four skipped
rows are two IR annotation imports and two pandas annotation imports; this report adjudicates them
because the binding workflow does.

### Receipts and CPU ceilings

The fresh parse receipt started at `10:16 up 2 days, 29 mins` and ended at `10:16` with
`real 25.45`, `user 22.33`, `sys 1.98`: **24.31 CPU-seconds**. A later cache-hit receipt started
and ended at `10:49 up 2 days, 1:02`, completed red at exit 1, and used `user 1.79 + sys 0.38 =
2.17 CPU-seconds`. Completed red is the expected receipt; the linter is not supposed to be green.
A final frozen-source receipt started and ended at `11:26 up 2 days, 1:39`, completed red at exit 1
with the same 84+4 output, and used `user 1.85 + sys 0.68 = 2.53 CPU-seconds`.

The release guardrail was replayed independently at the pinned base. The first attempt was a setup
non-receipt: the isolated generator lacked worktree-local Python and pnpm links. After linking the
already-provisioned workspace runtime through temporary ignored symlinks, the replay started at
`10:35 up 2 days, 48 mins`, ended at `10:37 up 2 days, 50 mins`, used
`user 69.77 + sys 19.28 = 89.05 CPU-seconds`, and exited 0 with both generated families fresh and
the architecture guardrail clean. The four validated symlinks were then moved to Trash; no tracked
file changed. The deep-import baseline at this base contains **3,646 list entries and 3,646 unique
edge tuples**; the guardrail independently reconciled current and baseline sets. This supersedes
the 3,648 count at the earlier pre-governance commit.

The distinct `polisyos-tools validation check-package-import-gates --fail-closed` predicate was
replayed again on 2026-08-26 after a hand-over claimed it had turned green on merged `main`. The
fresh run started at `12:01 up 2 days, 2:14`, ended at `12:06 up 2 days, 2:19`, used
`user 162.91 + sys 11.71 = 174.62 CPU-seconds`, and completed at **exit 1 with 143 findings**. It
therefore did not reproduce the claimed `exit 0 / 122.85 CPU-seconds`. Its findings include all 23
expired import exceptions, forbidden-boundary edges, unregistered dynamic imports, and other
structure debt. This completed failure is a receipt, not a release-guardrail failure; the two
measurements disagree and the dedicated package gate must not be described as green at this base.

The CPU ceiling used for this research was 4x the first completed CPU measurement for each command,
not wall time. No run was killed.

### Why “18 classes” is an operational taxonomy

There are **17 literal labels** if all four `ARCH004` rows are called one “Fabric-world” class:
13 internal source-to-target pairs, two external modules, Fabric-world, and PDC private depth. To
reproduce the requested 18-class arithmetic without inventing a package edge, this report splits
Fabric-world by the predicate's two target families: `materialize` and `store`. The row denominator
stays 88 either way.

## Per-class rollup

“Symbols” is the count of distinct imported names inside the class. File counts are class-local;
they sum above the 45-file global denominator because files can participate in more than one class.

| Edge class | Statements | Files | Symbols | `respell` | `export` | `relocate` | `ratify` | `ambiguous` | Required owner set |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `data_forge -> lex` | 21 | 10 | 31 | 0 | 0 | 21 | 0 | 0 | DataForge, Lex, Fabric/Core/IR as lower owners, Architecture |
| `ir -> foundry` | 13 | 6 | 18 | 0 | 0 | 13 | 0 | 0 | IR, Foundry, Scientist consumers, Architecture, PolicyOS |
| `data_forge -> foundry` | 10 | 3 | 12 | 0 | 0 | 10 | 0 | 0 | DataForge, Foundry, IR/Core, Architecture |
| `ir -> scientist` | 6 | 4 | 6 | 0 | 0 | 6 | 0 | 0 | IR, Scientist, Architecture, PolicyOS |
| `data_forge -> scientist` | 6 | 6 | 33 | 0 | 0 | 6 | 0 | 0 | DataForge, Scientist, Lex/IR/Core, Architecture |
| `foundry -> scientist` | 5 | 5 | 7 | 0 | 0 | 5 | 0 | 0 | Foundry, Scientist |
| `lex -> scientist` | 4 | 1 | 8 | 0 | 0 | 4 | 0 | 0 | Lex, Scientist |
| `core -> scientist` | 4 | 2 | 6 | 0 | 0 | 4 | 0 | 0 | Core, Scientist |
| `lex -> foundry` | 3 | 1 | 6 | 0 | 0 | 3 | 0 | 0 | Lex, Foundry |
| `ir -> core` | 2 | 2 | 10 | 0 | 0 | 2 | 0 | 0 | IR, Core, Foundry consumer, Architecture, PolicyOS |
| `foundry -> fabric` | 2 | 2 | 2 | 0 | 0 | 0 | 2 | 0 | Foundry, Fabric, Architecture |
| `runtime -> corpus` | 1 | 1 | 2 | 0 | 0 | 0 | 0 | 1 | Runtime, Architecture; Corpus owner unassigned |
| `foundry -> lex` | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | Foundry, Lex |
| `ir -> pandas` | 4 | 4 | 1 | 0 | 0 | 0 | 4 | 0 | IR, Architecture, PolicyOS |
| `ir -> jax` | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | IR, Foundry, Architecture, PolicyOS |
| `fabric.world.materialize` depth | 2 | 2 | 4 | 0 | 0 | 0 | 0 | 2 | Fabric, Architecture, PolicyOS exception-debt owner |
| `fabric.world.store` depth | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 2 | Fabric/Runtime, Architecture, PolicyOS exception-debt owner |
| `runtime -> pdc._impl` | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 1 | Runtime, PolicyOS Runtime, Architecture |
| **Global unique total** | **88** | **45** | **142 qualified** | **0** | **0** | **76** | **6** | **6** | **11 teams** |

### Measured cost boundary

Owner labels are normalized to repository team IDs. The global 11-team union is
`team-architecture`, `team-core`, `team-data-forge`, `team-fabric`, `team-foundry`, `team-ir`,
`team-lex`, `team-polisyos`, `team-policyos-runtime`, `team-runtime`, and `team-scientist`. The
per-class owner-set union and an independent lookup of source/target package owners plus current
exception-debt owners agree. The `relocate` rows require 9 of those teams; `ratify` requires 5;
`ambiguous` requires 5. These are coordination denominators, not a claim that every team edits
every row. `team-polisyos` enters the ambiguous set as owner of the lapsed Fabric-world cover
(`architecture/imports/exceptions.toml:193-200`); `team-policyos-runtime` is explicit for PDC
(`src/polisyos/pdc/README.md:3`). The Corpus README names no owner. The universal-PDC plan is owned
by `team-policyos-runtime` and introduced the package, but that is not a package-owner appointment;
the ambiguous population therefore has **5 named participating teams plus an unassigned Corpus
owner**, not a guessed sixth team.

For `relocate`, the measurable lower bound is **76 statements, 35 existing source files, 130
qualified bindings, seven implementation-package owners, plus Architecture and the current
exception-debt owner**. Destination modules and tests cannot be counted honestly until those owners
choose between moving a consumer upward and moving a neutral contract downward; this report does
not extrapolate a destination-file estimate.

For `ratify`, there are **two decision units** over 6 statements: narrow pandas use in IR (four)
and Foundry's Fabric product-evidence dependency (two). They involve 6 files, 3 bindings, three
implementation owners, Architecture, and the current register owner. No production source file
needs to move for the direction decision itself, although the Foundry/Fabric case also requires a
supported-surface decision.

For `ambiguous`, there are **three unresolved questions** over 6 statements, 5 files, and 9
bindings: the Fabric-world supported surface (four rows), Runtime's Corpus dependency (one), and
the PDC `SearchIteration` ownership/export question (one). The implementation cost is intentionally
not estimated before those rulings.

## Per-violation evidence

Paths in the tables are relative to `src/polisyos/`. Every path coordinate below was read after
`git rev-parse --show-prefix` returned `policy-engine/`.

### DataForge classes: 37 of 37

The ownership question left open by the options paper is now settled. The DataForge README
(`src/polisyos/data_forge/README.md:23-24,42-45`), legal corpus README
(`src/polisyos/data_forge/domains/legal/corpus/README.md:3-19`), Lex README
(`src/polisyos/lex/README.md:10-13,45-52`), DataForge package contract
(`architecture/packages/data_forge.toml:9-22,49-59`), and ADR-0159
(`docs/adr/0159-production-evidence-producer-contracts.md:19-20,30-43`) agree: offline acquisition,
corpus writing, normalization, and publication belong to DataForge; Lex owns runtime retrieval,
norm binding, and legal evaluation. Commit `7acba2e4e` moved the offline `lex/batch` and
`lex/corpus` implementations into DataForge without moving all contracts. The expired exception
describes those imports as residue of that move, not a permanent dependency.

Consequently `LexIngestOptions`, `LexStructureOptions`, and `LexVersionIndexOptions` are
DataForge writer contracts and their authoritative definitions should move with their producer.
`load_doc_meta_artifact` and `load_json_artifact` are generic mechanics, but the similar Fabric
helpers are not identical re-exports: their names, ID-validation behavior, and exception contracts
differ. Consolidating those mechanics under Fabric is a relocation, not a re-spelling.

#### `data_forge -> lex` (21)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| DF-LX-01 | `data_forge/domains/legal/batch/benchmark.py:19` | `polisyos.lex.api`: `assemble_norm_pack`, `evaluate_transport_constraints` | Runs downstream norm-pack readiness and transport probes. Move the Lex consumer probe out of the offline producer: **`relocate`**. |
| DF-LX-02 | `data_forge/domains/legal/batch/benchmark.py:20` | `polisyos.lex.knowledge.search`: `LegalKnowledgeGraph` | Opens the read-only graph for benchmark searches. Graph retrieval is Lex runtime behavior: **`relocate`**. |
| DF-LX-03 | `data_forge/domains/legal/batch/benchmark.py:21` | `polisyos.lex.types`: `NormPackBuildRequest` | Constructs requests for the downstream norm-pack operation. Move with the consumer probe: **`relocate`**. |
| DF-LX-04 | `data_forge/domains/legal/batch/cli.py:1026` | `polisyos.lex.knowledge.store`: `LegalKnowledgeStore` | `_cmd_search` constructs, queries, and closes the store. The DataForge read API exposes a different ILIKE function, not this class or its search semantics. Move the search command to its runtime owner or redesign the bridge: **`relocate`**. |
| DF-LX-05 | `data_forge/domains/legal/batch/doc_identity.py:11` | `polisyos.lex.common`: `parse_iso_date` | Parses ISO dates before a Ukrainian DMY fallback. This neutral utility belongs below both packages: **`relocate`**. |
| DF-LX-06 | `data_forge/domains/legal/batch/structurer.py:24` | `polisyos.lex.types`: `LexStructureOptions` | Configures the DataForge-owned batch `_build_candidates` writer. Move the authoritative writer contract to DataForge: **`relocate`**. |
| DF-LX-07 | `data_forge/domains/legal/batch/temporal_parser.py:9` | `polisyos.lex.common`: `parse_iso_date` | Parses relative-date anchors. Same neutral date primitive as DF-LX-05: **`relocate`**. |
| DF-LX-08 | `data_forge/domains/legal/corpus/index.py:12` | `polisyos.lex.artifacts`: `load_json_artifact as lex_load_json_artifact` | Loads DataForge-owned indexes. Fabric has a different helper with unconditional error wrapping; consolidate the mechanism and preserve local semantics: **`relocate`**. |
| DF-LX-09 | `data_forge/domains/legal/corpus/index.py:13` | `polisyos.lex.errors`: `LexIndexError` | Defines the error boundary for DataForge index persistence/loading. A producer-owned error should replace it, with Lex translation above: **`relocate`**. |
| DF-LX-10 | `data_forge/domains/legal/corpus/ingest.py:41` | `polisyos.lex.artifacts`: `load_doc_meta_artifact` | Loads `DocMeta` with `validate_ids=True`. Fabric's differently named helper always validates and raises different errors; consolidate below both packages: **`relocate`**. |
| DF-LX-11 | `data_forge/domains/legal/corpus/ingest.py:42` | `polisyos.lex.errors`: `LexError`, `LexIngestError`, `LexValidationError` | Error hierarchy for the DataForge ingest producer. Move producer errors to DataForge: **`relocate`**. |
| DF-LX-12 | `data_forge/domains/legal/corpus/ingest.py:43` | `polisyos.lex.types`: `LegalDocSource`, `LexIngestOptions`, `LexIngestResult`, `WorldEventRefLike` | Public inputs/options/results of corpus ingest. Writer contracts move to DataForge; the neutral event ref moves/reuses a lower contract: **`relocate`**. |
| DF-LX-13 | `data_forge/domains/legal/corpus/structure.py:43` | `polisyos.lex.artifacts`: `load_doc_meta_artifact`, `load_json_artifact` | Loads validated `DocMeta` and normalized JSON for structuring. Fabric alternatives are different objects and error contracts: **`relocate`**. |
| DF-LX-14 | `data_forge/domains/legal/corpus/structure.py:44` | `polisyos.lex.errors`: `LexError`, `LexNotReadyError`, `LexStructureError`, `LexValidationError` | Error hierarchy for the DataForge structuring producer: **`relocate`**. |
| DF-LX-15 | `data_forge/domains/legal/corpus/structure.py:45` | `polisyos.lex.types`: `LexStructureOptions`, `LexStructureResult` | Options/result of the DataForge structuring writer: **`relocate`**. |
| DF-LX-16 | `data_forge/domains/legal/corpus/versioning.py:41` | `polisyos.lex.artifacts`: `load_doc_meta_artifact` | Loads revision metadata with the current default `validate_ids=False`; Fabric always validates. The semantic difference rules out re-spelling: **`relocate`**. |
| DF-LX-17 | `data_forge/domains/legal/corpus/versioning.py:42` | `polisyos.lex.common`: `latest_object_by_subject`, `parse_iso_date` | Selects the latest artifact fact and parses temporal fields. Both are neutral artifact/time utilities: **`relocate`**. |
| DF-LX-18 | `data_forge/domains/legal/corpus/versioning.py:43` | `polisyos.lex.errors`: `LexError`, `LexNotReadyError`, `LexValidationError`, `LexVersioningError` | Version-index build/resolve error hierarchy for the DataForge producer: **`relocate`**. |
| DF-LX-19 | `data_forge/domains/legal/corpus/versioning.py:49` | `polisyos.lex.factlog`: `load_world_facts` | Reads persisted fact segments. The generic data-plane mechanic belongs in Fabric below both packages: **`relocate`**. |
| DF-LX-20 | `data_forge/domains/legal/corpus/versioning.py:50` | `polisyos.lex.types`: `ActiveVersionResult`, `ActiveVersionStrategy`, `LexVersionIndexOptions`, `LexVersionIndexResult` | Version-index writer options/result plus shared resolution types. Writer types move to DataForge and genuinely shared resolution contracts move lower: **`relocate`**. |
| DF-LX-21 | `data_forge/domains/ukraine/builders/release.py:22` | `polisyos.lex.interventions`: `InterventionKnobSpec`, `LexInterventionCompiler`, `LexProvisionDirective`, `TemporalInterventionSequencer` | D5 compiles legal directives and sequences interventions. DataForge should publish source/legal payloads and Lex should compile them: **`relocate`**. |

#### `data_forge -> foundry` (10)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| DF-FD-01 | `data_forge/domains/ukraine/builders/demography.py:5` | `polisyos.foundry.methods.catalog.microsim.protocols`: `SurveyMicroData` | Constructs and serializes a Foundry method contract. Materialize it in a Foundry consumer adapter or move only a neutral DTO lower: **`relocate`**. |
| DF-FD-02 | `data_forge/domains/ukraine/builders/release.py:10` | `polisyos.foundry.validation.release_acceptance`: `ReleaseAcceptanceRunner` | Runs downstream release acceptance and writes its finding. Foundry should validate the published DataForge release: **`relocate`**. |
| DF-FD-03 | `data_forge/domains/ukraine/builders/sources.py:16` | `polisyos.foundry.data_plane.bindings`: `build_input_bindings` | Builds Foundry bindings/state smoke from a snapshot and registry. Move binding construction to the consumer side: **`relocate`**. |
| DF-FD-04 | `data_forge/domains/ukraine/builders/sources.py:17` | `polisyos.foundry.methods.catalog.causal.measurement_error`: `identify_with_proxy` | Executes a downstream causal-method validation over producer artifacts: **`relocate`**. |
| DF-FD-05 | `data_forge/domains/ukraine/builders/sources.py:18` | `polisyos.foundry.methods.catalog.causal.protocols`: `DynamicTreatmentData`, `NetworkCausalData`, `PanelObservationalData` | Constructs and serializes method protocol fixtures. Keep method protocols in Foundry and move construction upward: **`relocate`**. |
| DF-FD-06 | `data_forge/domains/ukraine/builders/sources.py:23` | `polisyos.foundry.methods.catalog.econometrics.protocols`: `PanelData` | Constructs the panel econometric contract via `from_dataframe`: **`relocate`** to the Foundry adapter. |
| DF-FD-07 | `data_forge/domains/ukraine/builders/sources.py:24` | `polisyos.foundry.methods.catalog.microsim.protocols`: `SurveyMicroData` | Builds a preview contract and records its ID. Foundry should create that identity: **`relocate`**. |
| DF-FD-08 | `data_forge/domains/ukraine/builders/sources.py:25` | `polisyos.foundry.methods.catalog.ml.protocols`: `SurvivalData` | Builds/serializes a survival method contract: **`relocate`**. |
| DF-FD-09 | `data_forge/domains/ukraine/builders/sources.py:26` | `polisyos.foundry.methods.catalog.network.protocols`: `MultiplexNetworkData`, `NetworkData` | Builds network method contracts and records their IDs: **`relocate`**. |
| DF-FD-10 | `data_forge/domains/ukraine/builders/sources.py:30` | `polisyos.foundry.methods.layout`: `build_slot_family_manifest` | Projects the IR slot registry through a dynamic Foundry compatibility surface. Own the projection with the registry or run it in Foundry: **`relocate`**. |

#### `data_forge -> scientist` (6)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| DF-SC-01 | `data_forge/domains/academic/batch/benchmark.py:19` | `polisyos.scientist.cross_graph.feedback`: `AcademicBenchmarkScenario`, `AcademicBenchmarkSuite`, `BenchmarkCausalEdge`, `BenchmarkCredibilityPolicy`, `BenchmarkScholarQuery`, `load_benchmark_suite`, `write_need_backlog` | Builds the academic benchmark and also writes Scientist demand feedback. Separate the DataForge benchmark producer from the Scientist consumer bridge: **`relocate`**. |
| DF-SC-02 | `data_forge/domains/academic/batch/best_snapshot.py:31` | `polisyos.scientist.cross_graph.feedback`: `AcademicBenchmarkSuite`, `load_benchmark_suite` | Loads the suite during snapshot re-benchmarking. The producer configuration belongs to DataForge or a neutral contract: **`relocate`**. |
| DF-SC-03 | `data_forge/domains/academic/batch/claim_adjudicator.py:28` | `polisyos.scientist.methods.autotune.claim_adjudication`: `ClaimAdjudicationSearchConfig`, `aggregate_claim_rows`, `load_claim_adjudication_config`, `select_prompt_variant` | Mixes deterministic aggregation with Scientist champion/prompt selection. Inject the admitted config/result through a typed bridge: **`relocate`**. |
| DF-SC-04 | `data_forge/domains/legal/batch/benchmark.py:22` | `polisyos.scientist.agent.knowledge_tools`: `KnowledgeToolkit` | Constructs a downstream toolkit over the Lex graph for search/constraint probes. Move the consumer probe above DataForge: **`relocate`**. |
| DF-SC-05 | `data_forge/domains/ukraine/builders/calibration.py:7` | `polisyos.scientist.governance`: 20 governance runners, manifests, builders, and loaders | Executes the complete downstream D4 governance layer inside a DataForge builder. DataForge emits inputs; Scientist governs them: **`relocate`**. The exact names are `REQUIRED_SIGNOFF_FAMILIES`, `BacktestKind`, `CalibrationGovernanceEvidenceRunner`, `CalibrationRunManifest`, `CalibrationRunRunner`, `CalibrationValidationRunner`, `CalibrationValidationRunnerInput`, `GovernanceAccountabilityInput`, `HoldoutScoresManifest`, `LossBreakdownManifest`, `SpecificationCurveRunner`, `StrategicResponseMetricsManifest`, `StrategicResponseRunner`, `TransportabilityRunner`, `TransportabilitySummaryManifest`, `build_downstream_utility_report`, `build_family_eligibility_registry`, `build_interference_evidence`, `build_required_backtest_bundles`, `load_governance_accountability_artifact`. |
| DF-SC-06 | `data_forge/domains/ukraine/builders/release.py:28` | `polisyos.scientist.governance`: `CalibrationRunManifest`, `HoldoutScoresManifest`, `SpecificationCurveSummaryManifest`, `StrategicResponseMetricsManifest`, `TransportabilitySummaryManifest` | Parses D4 governance artifacts to drive D5 release construction. Consume a stable published result schema rather than Scientist internals: **`relocate`**. |

### IR classes: 26 of 26

The observation/method-protocol ownership question is also settled. IR's primary package contract
(`architecture/packages/ir.toml:47-66`) and the aggregate import contract call IR a schema-first
sink. Foundry's method catalog owns method-family protocol shapes and compilation/execution;
Scientist owns workflow governance and historical-validation plans. The archived DataForge
consolidation ownership record
(`docs/plans/archive/DATA_FORGE_CONSOLIDATION_PLAN_ROOT_LEGACY.md:748-775`) is unusually specific:
keep neutral models/contracts and pure codecs in IR; move
Foundry/Scientist construction, service, conversion, and execution adapters upward. It explicitly
names `ComputeBudget`, strategic bundle construction, `to_source_domain`, and alignment ontology
warnings.

Thus method-specific `DynamicTreatmentData`, `PanelData`, `SurveyMicroData`, `SurvivalData`, network
protocols, and `HistoricalValidationPlan` stay with Foundry/Scientist; the compiler that constructs
them moves out of IR. Neutral persisted manifests remain in IR. This avoids creating duplicate DTOs
(`P27`) while curing the inverted call (`P02`).

#### `ir -> foundry` (13)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| IR-FD-01 | `ir/analytics/strategic.py:2232` | `polisyos.foundry.methods.catalog.causal.strategic`: `strategic_decomposition_summary` | Builds a default failure card from a Foundry solve result. Move result interpretation to the Foundry producer: **`relocate`**. |
| IR-FD-02 | `ir/analytics/strategic.py:2274` | `polisyos.foundry.methods.catalog.causal.strategic`: `build_strategic_response_bundle`, `strategic_decomposition_summary` | Persists decomposition metadata and a response bundle. Move solve-result-to-artifact production upward while retaining IR schemas/persistence: **`relocate`**. |
| IR-FD-03 | `ir/analytics/transportability.py:343` | `polisyos.foundry.methods.catalog.causal.id_engine`: `SourceDomain` | `SourceDomainSpec.to_source_domain()` constructs a Foundry algorithm dataclass. Export a neutral payload from IR and convert in Foundry: **`relocate`**. |
| IR-FD-04 | `ir/observation/causal_execution.py:39` | `polisyos.foundry.methods.catalog.causal.protocols`: `DynamicTreatmentData` | `TYPE_CHECKING` half of the `TemporalDTRTask` field. Keep a neutral IR task payload and bind the concrete method protocol in Foundry: **`relocate`**. |
| IR-FD-05 | `ir/observation/causal_execution.py:51` | `polisyos.foundry.methods.catalog.causal.protocols`: `DynamicTreatmentData` | Runtime/Pydantic half of IR-FD-04. It is a separate importing statement and moves with the same adapter: **`relocate`**. |
| IR-FD-06 | `ir/observation/compiler.py:20` | `polisyos.foundry.calibration.measurement`: `MEASUREMENT_AWARE_TARGET_CONTRACT`, `CalibrationTargetBundle`, `MeasurementAwareTarget` | Constructs calibration targets/bundles in both compile and placebo paths. Move tensor/materialization into Foundry calibration: **`relocate`**. |
| IR-FD-07 | `ir/observation/contract_compilers.py:20` | `polisyos.foundry.methods.catalog.causal.protocols`: `DynamicTreatmentData`, `NetworkCausalData`, `PanelObservationalData`, `ProxyMeasurementData` | Four concrete method-protocol compilers and class-ID reads. Keep neutral compiler inputs/results in IR; move constructors to Foundry: **`relocate`**. |
| IR-FD-08 | `ir/observation/contract_compilers.py:26` | `polisyos.foundry.methods.catalog.econometrics.protocols`: `PanelData` | `PanelEconometricCompiler.compile()` constructs the Foundry protocol: **`relocate`** the compiler adapter. |
| IR-FD-09 | `ir/observation/contract_compilers.py:27` | `polisyos.foundry.methods.catalog.microsim.protocols`: `SurveyMicroData` | Survey compiler constructs the Foundry protocol: **`relocate`**. |
| IR-FD-10 | `ir/observation/contract_compilers.py:28` | `polisyos.foundry.methods.catalog.ml.protocols`: `SurvivalData` | Survival compiler constructs the Foundry protocol: **`relocate`**. |
| IR-FD-11 | `ir/observation/contract_compilers.py:29` | `polisyos.foundry.methods.catalog.network.protocols`: `MultiplexNetworkData`, `NetworkData` | Network compilers construct Foundry protocols and read their IDs: **`relocate`**. |
| IR-FD-12 | `ir/passes/core.py:395` | `polisyos.foundry.methods.catalog.causal.estimand_compiler`: `classify_estimand` | Kernel-lowering fallback invokes a Foundry estimator classifier in an execution-free IR pass. Extract the Foundry compiler boundary: **`relocate`**. |
| IR-FD-13 | `ir/passes/core.py:396` | `polisyos.foundry.methods.catalog.causal.kernel_lowering`: `build_kernel_estimator_spec`, `should_request_kernel_lowering` | Selects/builds a Foundry estimator strategy. Same compiler-boundary extraction: **`relocate`**. |

#### `ir -> scientist` (6)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| IR-SC-01 | `ir/analytics/alignment_certification.py:46` | `polisyos.scientist.cross_graph.compiler`: `build_fragment_alignment_ontology_warnings` | IR invokes a Scientist warning service then degrades failures. Keep certificate/degradation DTOs in IR and inject candidate warnings from Scientist: **`relocate`**. |
| IR-SC-02 | `ir/analytics/alignment_certification.py:49` | `polisyos.scientist.methods.search.latent_governance`: `assess_latent_bridge_governance`, `materialize_latent_bridge_governance` | Executes promotion/readiness governance while persisting IR hypotheses. Scientist supplies the governance snapshot: **`relocate`**. |
| IR-SC-03 | `ir/analytics/strategic.py:28` | `polisyos.scientist.orchestration.kernel.budgets`: `ComputeBudget` | Schema-bearing field/default on `StrategicSCM`. This dependency-free shared contract moves down to IR and Scientist re-exports it: **`relocate`**. |
| IR-SC-04 | `ir/observation/bundles.py:32` | `polisyos.scientist.methods.backtesting.plan`: `HistoricalValidationPlan` | `TYPE_CHECKING` half of `BacktestPlanBundle.plans`. Keep a neutral IR declaration; bind concrete plans in Scientist: **`relocate`**. |
| IR-SC-05 | `ir/observation/bundles.py:41` | `polisyos.scientist.methods.backtesting.plan`: `HistoricalValidationPlan` | Runtime/Pydantic half of IR-SC-04: **`relocate`** with the same adapter. |
| IR-SC-06 | `ir/observation/contract_compilers.py:82` | `polisyos.scientist.methods.backtesting.plan`: `HistoricalValidationPlan`, `PredictionSource` | Defaults a compile spec and constructs historical plans. Move plan construction to Scientist backtesting: **`relocate`**. |

#### `ir -> core` (2)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| IR-CO-01 | `ir/analytics/phase4_dynamics.py:13` | `polisyos.core.contracts.foundry`: `ExecPlanRef`, `IdentifiabilityDiagnosticRef`, `MetricsRef`, `SimulationResult` | `ABMResult` subclasses Core's execution DTO and a builder constructs all four. Keep an IR analytical result; convert to/from Core execution above IR: **`relocate`**. |
| IR-CO-02 | `ir/analytics/simulation_proof_bridge.py:12` | `polisyos.core.observability.truthfulness`: `TruthfulnessReceipt`, `TruthfulnessScope`, `TruthfulnessTier`, `extract_truthfulness_receipt`, `truthfulness_depth`, `validate_truthfulness_receipt` | IR already owns parallel truthfulness types specifically to preserve `common -> ir -> core`. Consolidate the canonical identities/helpers in IR and have Core re-export them: **`relocate`**. |

#### `ir -> pandas` (4)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| IR-PD-01 | `ir/analytics/causal_run_snapshot.py:26` | `pandas as pd` | Runtime `isinstance(..., pd.DataFrame)` precedes deterministic dataset fingerprinting. Pandas is already a base dependency and this is IR reproducibility behavior: candidate **`ratify`**. |
| IR-PD-02 | `ir/data/harmonizer.py:24` | `pandas as pd` | `TYPE_CHECKING` annotations on the deterministic IR harmonizer; no existing structural DataFrame facade exists: candidate **`ratify`** narrowly. |
| IR-PD-03 | `ir/data/versioning.py:33` | `pandas as pd` | `TYPE_CHECKING` annotations for schema/content hash and version codecs owned by IR: candidate **`ratify`** narrowly. |
| IR-PD-04 | `ir/observation/contract_compilers.py:17` | `pandas as pd` | Pure sorted parquet write/read codecs. The ownership record explicitly leaves pure codecs in IR even when protocol constructors move: candidate **`ratify`**. |

Ratifying these four commits IR to a narrow pandas contract for DataFrame recognition, annotations,
and deterministic codecs. It does not authorize estimation or Foundry tensor construction in IR.

#### `ir -> jax` (1)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| IR-JX-01 | `ir/observation/compiler.py:15` | `jax.numpy as jnp` | Builds typed tensors exclusively for the Foundry `CalibrationTargetBundle` imported five lines later. Move tensor materialization with that compiler: **`relocate`**. |

### Remaining classes: 25 of 25

#### `foundry -> scientist` (5)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| FD-SC-01 | `foundry/calibration/calibrator.py:559` | `polisyos.scientist.methods.autotune.calibration`: `apply_calibration_meta_overrides` | `Calibrator.run` applies Scientist autotune policy before fitting. Resolve/inject policy above Foundry or move a neutral operation to `calibration`: **`relocate`**. |
| FD-SC-02 | `foundry/calibration/dp_ci.py:179` | `polisyos.scientist.methods.search.judge_thresholds`: `JudgeThresholdRegistry` | Foundry loads a Scientist registry and resolves CI thresholds. Scientist should inject resolved threshold policy: **`relocate`**. |
| FD-SC-03 | `foundry/methods/catalog/causal/composition_failure_cards.py:20` | `polisyos.scientist.methods.search.failure_cards`: `FailureSeverity`, `TypedFailureCard` | Foundry constructs/deduplicates Scientist blocker cards. Put the neutral card contract below both or project Scientist cards above compute: **`relocate`**. |
| FD-SC-04 | `foundry/methods/catalog/policy/frontier.py:23` | `polisyos.scientist.agent.embedder`: `SentenceTransformerEmbedder`, `TFIDFEmbedder` | A Foundry estimator selects Scientist embedding implementations. Compute implementation/protocol belongs in Foundry or a neutral owner; Scientist may inject selection policy: **`relocate`**. |
| FD-SC-05 | `foundry/validation/release_acceptance.py:33` | `polisyos.scientist.governance.postflight`: `postflight_checks` | Foundry invokes governance postflight and consumes its gate. Orchestration belongs above Foundry; Foundry returns validation receipts: **`relocate`**. |

#### `lex -> scientist` (4)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| LX-SC-01 | `lex/interventions.py:54` | `polisyos.scientist.methods.search.controller`: `SearchIteration`, `SearchResult`, `SearchStatus` | `_run_parameterless_search` manufactures a converged Scientist search result/iteration. Scientist should construct it from Lex inputs: **`relocate`**. |
| LX-SC-02 | `lex/interventions.py:55` | `polisyos.scientist.policy_design.schema`: `PolicyCandidateSchema` | The Lex adapter converts intervention bundles into Scientist candidates. Move the adapter to Scientist: **`relocate`**. |
| LX-SC-03 | `lex/interventions.py:56` | `polisyos.scientist.policy_design.search`: `HierarchicalSearchConfig`, `HierarchicalSearchCoordinator`, `PolicySearchLevel` | Lex parses search config, constructs the coordinator, and plans transitions. Move hierarchical search orchestration to Scientist: **`relocate`**. |
| LX-SC-04 | `lex/interventions.py:1083` | `polisyos.scientist.policy_design.search`: `HierarchicalSearchResult` | Function-local construction of the same downstream result; move with LX-SC-01..03 so the late import is not a bypass: **`relocate`**. |

#### `core -> scientist` (4)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| CO-SC-01 | `core/components/_cli_metric_validation.py:18` | `polisyos.scientist.validation.metrics`: `TestConfig`, `compare_metric_family`, `load_metric_observation_bundle` | Core's CLI handler loads and compares Scientist metric bundles. Move the command implementation to Scientist/top-level tooling: **`relocate`**. |
| CO-SC-02 | `core/components/_cli_scientist.py:284` | `polisyos.scientist.orchestration.llm`: `run_gonka_provider_smoke` | `_cmd_scientist_provider_verify` directly invokes Scientist orchestration. Scientist owns the handler: **`relocate`**. |
| CO-SC-03 | `core/components/_cli_scientist.py:317` | `polisyos.scientist.agent.eval_harness`: `run_starter_eval_harness` | Core directly runs the Scientist evaluation harness. Move the handler upward: **`relocate`**. |
| CO-SC-04 | `core/components/_cli_scientist.py:345` | `polisyos.scientist.agent.reflexion_evaluator`: `evaluate_reflexion_replay_cases` | Core directly runs Scientist replay evaluation. Move the handler upward: **`relocate`**. |

#### `lex -> foundry` (3)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| LX-FD-01 | `lex/interventions.py:17` | `polisyos.foundry.methods.catalog.causal.causal_engine`: `CausalEngine` | Temporal intervention compilation computes causal effects. Foundry/Scientist should execute over a Lex-produced sequence: **`relocate`**. |
| LX-FD-02 | `lex/interventions.py:18` | `polisyos.foundry.methods.catalog.causal.dtr`: `ALearningDTR`, `DoublyRobustDTR`, `OutcomeWeightedLearning`, `QLearningDTR` | `_run_dtr_method` selects and runs Foundry implementations. Move DTR execution to Foundry: **`relocate`**. |
| LX-FD-03 | `lex/interventions.py:24` | `polisyos.foundry.methods.catalog.causal.protocols`: `DynamicTreatmentData` | Lex validates, constructs, and transports a Foundry execution payload. Put a neutral transport contract in IR or keep this behind a higher bridge: **`relocate`**. |

#### `foundry -> fabric` (2)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| FD-FB-01 | `foundry/calibration/fabric_quality.py:10` | `polisyos.fabric.product_integration`: `FabricProductEvidencePath`, `evidence_path_from_fabric_decision_data` | Converts Fabric decision data into canonical evidence paths for calibration context. Boundaries and the Foundry primary contract permit Fabric; the executable matrix and layered contract forbid it. Candidate **`ratify`** the narrow direction to resolve that contradiction; separately decide a supported Fabric surface. |
| FD-FB-02 | `foundry/uncertainty/fabric_quality.py:10` | `polisyos.fabric.product_integration`: `evidence_path_from_fabric_decision_data` | Uses the same canonical Fabric normalization. The same two contracts permit and two contracts forbid this direction: candidate **`ratify`** with FD-FB-01. |

Ratification commits Fabric to the evidence-path DTO/conversion behavior as a stable cross-package
integration surface. It does not justify exposing all of `fabric.product_integration`. The
strongest counterevidence is `architecture/imports/contracts.toml:12-22`: its primary layered
contract makes Foundry and Fabric independent siblings, so ratification would revise a deliberate
layer boundary as well as the executable matrix.

#### `foundry -> lex` (1)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| FD-LX-01 | `foundry/agent_sim/wiring/contracts.py:22` | `polisyos.lex.interventions`: `CompiledLexIntervention` | `InterventionMechanismConfig.from_compiled_intervention` translates a Lex object into Foundry parameters. Put the translation in Lex or Scientist orchestration; keep Foundry's generic `from_params`: **`relocate`**. |

#### Fabric-world depth: four rows, two operational classes

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| FW-ST-01 | `fabric/_adapters/observability.py:581` | `polisyos.fabric.world.store.segments`: `load_world_fact_manifests` | World-health observation loads manifests. `polisyos.fabric.world` exports the symbol, but that facade is absent from the public-surface contract: **`ambiguous`**. Question: is `fabric.world` a supported entrypoint? |
| FW-ST-02 | `runtime/quality/data_state_substrate.py:1249` | `polisyos.fabric.world.store`: `create_world_snapshot` | `_write_fabric_world_snapshot` creates the observed snapshot. No Fabric supported facade exports it: **`ambiguous`** by the task boundary. Question: export the constructor or move snapshot production behind a Fabric bridge? |
| FW-MA-01 | `fabric/data_plane/benchmarks.py:28` | `polisyos.fabric.world.materialize`: `WorldMaterializationPolicy`, `WorldMaterializeStats`, `ensure_world_materialized` | Benchmarks materialization. `fabric.world` exports the stats and function but not the policy type, and is itself unsupported: **`ambiguous`**. Question: support/complete the world facade or move the benchmark behind Fabric root/API? |
| FW-MA-02 | `runtime/quality/data_state_substrate.py:1248` | `polisyos.fabric.world.materialize`: `ensure_world_schema` | Same snapshot writer initializes the schema. `fabric.world` exports it but is unsupported: **`ambiguous`** by the task boundary. |

This is not cosmetic uncertainty. `lint_imports.py:1350-1374` says “Use
`polisyos.fabric.world` facade exports”; `architecture/public_surface/contract.toml:208-216`
supports only `polisyos.fabric` and `polisyos.fabric.api`. The deep-import collector excludes
same-root edges, so it cannot represent FW-ST-01 or FW-MA-01 at all, while it records the two
Runtime rows. Two governance systems therefore disagree across the same four instances.

#### `runtime -> corpus` (1; unadjudicated and reserved)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| RT-CP-01 | `runtime/http/services/governed_projection_validation_worker.py:397` | `polisyos.corpus`: `load_universal_corpus_fixtures`, `load_universal_corpus_manifest` | Lazy import in `_validate_proving_ground`; loads the manifest/fixtures and checks the 13-case denominator. The symbols are Corpus-root exports, so spelling is not the issue. **`ambiguous`** by explicit task boundary. Question: admit a Runtime evaluation-corpus dependency, or consume a persisted/recomputed evaluation artifact? |

#### `runtime -> pdc._impl` (1; unadjudicated and reserved)

| ID | File and line | Exact target and imported symbol(s) | Call-site evidence and candidate disposition |
| --- | --- | --- | --- |
| RT-PD-01 | `runtime/quality/generation_cycle.py:52` | `polisyos.pdc._impl.layer2_design_search`: `SearchIteration` | Field type on `GenerationCycleRecord`, return type, and constructor in `_search_iteration`. PDC exports neighboring search contracts but not this private type. **`ambiguous`** by explicit task boundary. Question: is it a stable cross-workflow contract to export, or should Runtime use a neutral/owned DTO? |

These tables enumerate all 88 statements exactly once. The four reserved unadjudicated rows are
FW-ST-02, FW-MA-02, RT-CP-01, and RT-PD-01; no disposition decision has been smuggled into their
`ambiguous` label.

## Reconciliation of the governance corpus

### The reproducible 21

`architecture/gates/package_import.toml:9-30` contains 21 literal, unique paths. A TOML parser and
an independent line-array parser produced the same ordered set:

1. `architecture/gates/package_import.toml`
2. `architecture/imports/reports.toml`
3. `architecture/imports/contracts.toml`
4. `architecture/imports/policy.toml`
5. `architecture/imports/exceptions.toml`
6. `architecture/baselines/imports/deep_import.json`
7. `architecture/imports/dynamic.toml`
8. `architecture/imports/lazy.toml`
9. `architecture/packages/boundaries.toml`
10. `architecture/packages/layout.toml`
11. `architecture/public_surface/contract.toml`
12. `architecture/public_surface/inventory.json`
13. `architecture/name_registry.toml`
14. `architecture/policies/cross_cutting_concerns.toml`
15. `architecture/shims.toml`
16. `architecture/exceptions/structure_remediation.toml`
17. `architecture/policies/directory_contracts.toml`
18. `architecture/packages/fabric.toml`
19. `architecture/packages/ir.toml`
20. `architecture/packages/scientist.toml`
21. `architecture/module_size_budget.toml`

Authority is dimension-specific and no precedence rule resolves a collision:

- ADR-0004 identifies `policy.toml`, the exception register, and `lint_imports.py` as the binding
  executable policy. That is what makes the 88 rows red today.
- `boundaries.toml:1-8` is marked `draft` but calls itself the canonical per-package dependency
  source of truth.
- 19 package documents say `primary_contract = true` and carry a `[boundaries]` section, but are
  also `draft`/`report_only` and call the aggregate files legacy mirrors. Only Fabric, IR, and
  Scientist are members of the literal 21-source gate corpus;
- `public_surface/contract.toml:1-10` is authoritative for supported FQNs and makes every unlisted
  path internal by default;
- `cross_cutting_concerns.toml` appoints canonical interfaces and concern owners.

A reader can reasonably treat each as authoritative for its advertised property. Therefore the
disagreements below cannot be dismissed as a reader choosing the “wrong” file.

### Matrix versus canonical boundary contract

Normalizing `polisyos.data_forge.read_api` to its top-level root, and treating Runtime's special
`public_facades_only` token separately, a complete comparison finds **21 mismatched root pairs**.
Twelve have live imports: **24 statements across 23 files**. A TOML+AST derivation and an
independent anchored import-line derivation agree per pair.

| Pair | Difference | Executable policy row | Boundary-contract row(s) | Live statements / files |
| --- | --- | --- | --- | ---: |
| `calibration -> core` | policy-only | `policy.toml:81` | `boundaries.toml:266-280` | 0 / 0 |
| `evidence -> ir` | policy-only | `policy.toml:87` | `boundaries.toml:243-251` | 0 / 0 |
| `fabric -> data_requirement` | policy-only | `policy.toml:71` | `boundaries.toml:83-103`; `packages/fabric.toml:52-72` | 1 / 1 |
| `foundry -> calibration` | policy-only | `policy.toml:72-80` | `boundaries.toml:129-149`; `imports/contracts.toml:12-22` | 1 / 1 |
| `foundry -> fabric` | **boundary-only** | `policy.toml:72-80` | `boundaries.toml:129-138` | **2 / 2** |
| `foundry -> method_requirement` | policy-only | `policy.toml:72-80` | `boundaries.toml:129-149` | 2 / 2 |
| `ir -> schemas` | policy-only | `policy.toml:67` | `boundaries.toml:22-40`; `packages/ir.toml:47-66` | 1 / 1 |
| `lex -> batch_common` | policy-only | `policy.toml:114` | `boundaries.toml:106-126` | 0 / 0 |
| `lex -> legal_requirement` | policy-only | `policy.toml:114` | `boundaries.toml:106-126` | 1 / 1 |
| `method_requirement -> ir` | policy-only | `policy.toml:85` | `boundaries.toml:229-233` | 0 / 0 |
| `obligation_graph -> ir` | policy-only | `policy.toml:110` | `boundaries.toml:222-226` | 0 / 0 |
| `obligation_rules -> ir` | policy-only | `policy.toml:68` | `boundaries.toml:215-219` | 0 / 0 |
| `obligation_rules -> runtime` | policy-only, explicitly forbidden in boundary file | `policy.toml:68` | `boundaries.toml:215-219` | 0 / 0 |
| `participation_requirement -> ir` | policy-only | `policy.toml:86` | `boundaries.toml:236-240` | 0 / 0 |
| `scholar -> data_forge` | **boundary-only** (`read_api`) | `policy.toml:113` | `boundaries.toml:152-172` | 0 / 0 |
| `scholar -> scholar_requirement` | policy-only | `policy.toml:113` | `boundaries.toml:152-172` | 5 / 5 |
| `scientist -> calibration` | policy-only | `policy.toml:88-106` | `boundaries.toml:175-195`; `packages/scientist.toml:122-141`; `imports/contracts.toml:12-22` | 1 / 1 |
| `scientist -> evidence` | policy-only | `policy.toml:88-106` | `boundaries.toml:175-195`; `packages/scientist.toml:122-141` | 3 / 3 |
| `scientist -> method_requirement` | policy-only | `policy.toml:88-106` | `boundaries.toml:175-195`; `packages/scientist.toml:122-141` | 1 / 1 |
| `scientist -> participation_requirement` | policy-only | `policy.toml:88-106` | `boundaries.toml:175-195`; `packages/scientist.toml:122-141` | 2 / 2 |
| `scientist -> runtime` | policy-only, explicitly forbidden by both boundary contracts | `policy.toml:102` | `boundaries.toml:191-195`; `packages/scientist.toml:122-141`; `imports/contracts.toml:12-22` | **4 / 4** |

For `scientist -> runtime`, two statements use the supported experimental
`polisyos.runtime.quality` surface and two use unsupported `polisyos.runtime.replay`. The matrix
legalizes both; the aggregate boundary file and the in-corpus Scientist primary contract forbid
both. That is both a direction disagreement and a surface-granularity disagreement.

The in-corpus layered contract supplies a third topology answer. Its “Layered architecture” row
(`architecture/imports/contracts.toml:12-22`) puts pipe-separated packages in independent sibling
positions and calls Runtime above Scientist. ADR-0115 names this file the intended primary boundary
arbiter while also recording that its runner remains report-only
(`docs/adr/0115-layered-architecture-enforcement.md:19-39`). Two consequences are live:

- it rejects **77 of the 78 ARCH001 rows** in this report; Runtime→Corpus is the sole row it cannot
  express because Corpus is absent from its layer list. Mapping every exact AST violation tuple to
  the parsed layer positions and independently summing the 13 class rows give the same 77/1 split.
  It corroborates the candidate `relocate` result for 75 rows and conflicts with the candidate
  `ratify` result for exactly the 2 Foundry→Fabric rows;
- for Foundry→Fabric, it forbids the same 2 statements that the executable matrix forbids, while
  `boundaries.toml` and `packages/foundry.toml` allow them. For Scientist→Runtime, it forbids the
  same 4 statements as both boundary contracts, while the matrix allows them.

Thus Foundry→Fabric is not simply an unmodelled omission: it is a candidate ratification against
one executable and one intended layer contract, supported by two boundary contracts. The call-site
semantics make that candidate defensible, but the architecture documents do not make it unanimous.

The top-root normalization hides one further width mismatch. For IR, Fabric, Foundry, Lex,
Scientist, and Scholar, the matrix permits the whole `data_forge` root while the boundary/import
contracts permit only `data_forge.read_api`. There are **22 live statements in 18 files** across
those six sources; all 22 currently use `read_api`, so no live row violates the narrower property.
The two complete derivations agree, but the executable matrix would admit future non-read-API
imports that the claimed canonical contract forbids.

### Runtime's “public facades only” rule is not what the matrix enforces

`boundaries.toml:197-212` says Runtime may import `public_facades_only`; `policy.toml:109` instead
allows 16 named target roots, and `public_surface/contract.toml:3` makes unlisted paths internal.
A complete Runtime AST walk and an independent anchored line parser agree:

- Runtime has **575 cross-package import statements in 154 files**;
- **83 statements in 55 files** target an exact supported entrypoint;
- **492 statements in 136 files** target an FQN the public contract does not support.

The public contract has 20 package rows covering 18 of the policy's 30 top roots. The 12 absent
roots are `academic`, `batch_common`, `batch_snapshot`, `corpus`, `data_requirement`, `datasets`,
`legal_requirement`, `pdc`, `policy_grammar`, `schemas`, `scholar_requirement`, and `ukraine_data`.
Runtime currently imports four of them: Corpus 1/1, Data Requirement 4/4, PDC 59/54, and Scholar
Requirement 1/1, totaling **65 statements in 56 files**. Across all sources, imports into the 12
absent roots total **74 statements in 65 files**; the other nine are Fabric→Data Requirement (1),
Lex→Legal Requirement (1), IR→Schemas (1), Scholar→Scholar Requirement (5), and Data
Requirement→Policy Grammar (1). Two independent enumerations agree.

This changes the scale of the surface question. The one PDC private row in the 88 is a real depth
violation, but the public contract does not register the PDC root used by the other 58 Runtime
statements either.

### Public canonical interfaces absent from the public-surface contract

The `core.security` finding is one member of a wider class. Seven cross-cutting concern rows marked
public/public-experimental collapse to five distinct canonical interfaces. Only
`polisyos.calibration` is supported by the public-surface contract. Four distinct public canonical
FQNs are absent:

| Canonical interface | Concern rows | Live cross-package statements / files | Exact-interface imports | Public-contract state |
| --- | --- | ---: | ---: | --- |
| `polisyos.core.observability` | `cross_cutting_concerns.toml:53-70,168-183` | **252 / 220** | 67 | absent; Core root only |
| `polisyos.core.security` | `cross_cutting_concerns.toml:73-90` | **47 / 24** | 2 | absent; 45 imports reach 18 submodules |
| `polisyos.common.config` | `cross_cutting_concerns.toml:130-147` | **1 / 1** | 1 | absent; Common root only |
| `polisyos.core.trace` | `cross_cutting_concerns.toml:149-166` and duplicate trace row | **4 / 4** | 1 | absent; Core root only |
| **Union** | — | **304 / 243** | — | four distinct missing FQNs |

AST and anchored import-line derivations agree on those statement/file counts. The generated
inventory mirrors all 20 contract package rows and their entrypoints byte-for-byte, so this is not
stale generation. The root inventory happens to expose `common.config` and `core.observability` as
attributes, but the cross-cutting import rules name submodule FQNs and the contract makes those
unlisted FQNs internal. It exposes neither `core.security` nor `core.trace` at Core root.

`name_registry.toml:966-1034` agrees with `cross_cutting_concerns.toml:53-283` on the seven grouped
canonical homes, but six responsible-owner labels differ: Security (`team-security` versus
`team-core`, 47/24 live), Registry (`team-core` versus `team-architecture`, 23/23), Discovery
(`team-core` versus `team-architecture`, 3/3), Configuration (`team-core` versus
`team-architecture`, 1/1), Tracing (`team-observability` versus `team-core`, 4/4), and Calibration
(`team-scientist` versus `team-architecture`, 2/2). AST and anchored-text counts agree. Because one
field is `canonical_owner` and the other is `owner`, this is recorded as **owner-semantic
ambiguity**, not asserted as a contradiction.

### The literal corpus includes only 3 of 19 primary package boundary contracts

A complete `architecture/packages/*.toml` census finds **19** files declaring
`primary_contract = true`; all 19 also carry a `[boundaries]` section. Only Fabric, IR, and
Scientist appear in the literal 21-source gate corpus, leaving **16 primary boundary contracts
outside it**: BERL, Calibration, Common, Core, DataForge, DDM, Evidence, Foundry Agent-Sim World,
Foundry, Lex, Method Requirement, Obligation Graph, Obligation Rules, Participation Requirement,
Runtime, and Scholar. A TOML-object enumeration and an independent anchored declaration/file-set
enumeration agree on 19 total, 3 included, and 16 omitted.

Foundry is a uniquely direct internal inconsistency: the in-corpus
`architecture/imports/reports.toml:12-18` explicitly names the omitted
`architecture/packages/foundry.toml` as an import-boundary source. That file declares
`primary_contract = true` at lines 1-9 and mirrors the aggregate boundary file by allowing Fabric
and forbidding Scientist, Lex, and Calibration at lines 40-59. Those claims govern nine live
Foundry statements in nine files (2 Fabric, 5 Scientist, 1 Lex, 1 Calibration); two additional
live Foundry→Method Requirement statements are allowed by the matrix but omitted from its
allow-list. This does not change the requested 21-path denominator; it proves that the literal
corpus includes neither the complete declared primary-contract set nor even every source named by
its own reports member.

### Why the package-import gate does not reconcile the documents

`package_import.toml` promises to block “import-contract/public-surface disagreement.” Its
implementation validates source paths and selected `forbidden_dependencies`, and explicitly skips
the `public_facades_only` token. It does not compare the matrix allowsets, supported entrypoints,
or cross-cutting canonical interfaces. The dedicated package gate is red for other reported debt,
but none of the complete allow-set/public-interface disagreements above is its predicate. The
divergent case required by `P38` is therefore still present: hold the reported forbidden markers
and baselines fixed while changing an allow-set/public-surface contradiction, and this checker does
not track the property. Its exit code—red or green—cannot establish semantic agreement among the
21 sources.

## Required-status answer

The repository can establish intent and transitive workflow behavior, but not live GitHub state:

- `.github/repository-rulesets/main.yml:16-20` names only `Fast PR / Gate` and
  `Standard PR / Gate` as directly required. It does **not** name
  `Fast PR / Python quality and unit`.
- `.github/workflows/abi.yml:83-100` gives `quality-and-unit` that display name and runs the plain
  linter. `Fast PR / Gate` at lines 289-308 needs `quality-and-unit` and fails when it fails or is
  cancelled. The linter is therefore **transitively required by the tracked Fast aggregate**.
- `docs/reference/merge-governance.md:10-17,41-54` explicitly says the ruleset file records intent,
  not proof that it is applied or proof of exact live contexts. Without GitHub UI/API evidence,
  whether `main` currently enforces that intended aggregate is **ambiguous**.

Thus the honest answer is: not directly named, transitively required by repository-tracked intent,
and live branch protection not established locally.

## Findings that change the decision frame

1. **The 88 are overwhelmingly ownership inversions, not facade debt.** Seventy-six rows require
   moving a consumer operation upward or a neutral contract downward. A facade-only campaign would
   leave their forbidden directions intact.
2. **The 21-file corpus is reproducible but not complete as an authority corpus.** It includes
   only 3 of 19 declared primary package boundary contracts; Foundry is the omitted member that
   `imports/reports.toml` itself names.
3. **The package-import gate is freshly red and does not establish cross-document agreement.** A
   2026-08-26 replay completed at exit 1 with 143 findings, contradicting the later hand-over's
   exit-0 claim. Independently of that verdict, the implemented predicate does not compare
   `policy.toml` allowsets and skips `public_facades_only`; even a future green result would establish
   only its narrower checks, not agreement on the measured direction and supported-entrypoint
   contradictions (`P38`).
4. **The surface problem is much larger than the four ARCH004 rows.** Runtime has 492 imports to
   unlisted FQNs, and four public canonical interfaces governing 304 cross-package statements are
   absent from the public contract. These are measured facts, not a proposal to broaden anything.
5. **The three commands have distinct predicates and receipts.** At the research base the release
   guardrail receipt is green; the plain import linter is red at 84 lapsed + 4 unadjudicated; and
   the separately replayed package-import validator is red with 143 findings. A composite
   “architecture is green/red” statement would conflate three properties. Each branch or merge
   commit needs the commands reported separately.

The linter also reports the existing 16-node package cycle
(`calibration`, `core`, `data_forge`, `data_requirement`, `fabric`, `fabric.io`, `foundry`, `ir`,
`lex`, `obligation_rules`, `pdc`, `policy_grammar`, `runtime`, `scholar`, `scientist`,
`scientist.agent`) and a god-file list headed by `runtime/quality/__init__.py` at 79 internal
imports. They were observed and not acted on.

## Pattern and capability pass

- **P06 / P27:** the legal source move left authoritative writer contracts under Lex, and IR/Core
  truthfulness types have competing identities. Closure must move/re-export one authority, not
  copy a third DTO.
- **P12 / P02:** DataForge producers and IR schemas directly invoke downstream Foundry/Scientist
  behavior. The intended producer/consumer separation is `implemented_but_not_orchestrated`, with
  several typed handshakes `bridge_missing`.
- **P31:** the 76 relocation rows are instances of a few ownership inversions. Per-site exception
  renewal would preserve the class.
- **P35:** all counts in this report come from complete path/file-type denominators and a second
  independent derivation. The two same-predicate derivations agree. The inherited 11-file claim
  for `data_forge -> lex` versus the measured 10 is preserved as a disagreement; the no-flag 88
  versus flag-enabled 84 is separately identified as a predicate change, not a derivation split.
- **P38:** the package gate promises cross-contract agreement but tests selected declarations and
  baseline deltas. Its current red does not report the measured allow-set/public-interface
  disagreements. `fabric.world` is the concrete semantic case: the linter recommends a facade that
  the public contract calls internal.
- **P41:** the release guardrail was replayed at the task's own base before this report existed. Its
  setup failure was separated from the completed green receipt.

No production import, policy row, exception, baseline, generated inventory, or register entry was
changed. `guardrails sync` was never run.

## Directional signal for the later model decision

The evidence points toward retaining the directional matrix while structurally repairing the 76
ownership inversions, narrowly considering ratification of the six measured legitimate dependencies,
and withholding the six ambiguous rows until their three governance questions are ruled; the
strongest counter-argument is that a matrix cannot remain the sole architecture model while its
claimed canonical mirror differs on 21 pairs and its companion public-surface system cannot express
hundreds of live imports, so keeping it requires an explicit reconciliation mechanism rather than
continuing the present hand-maintained document stack.
