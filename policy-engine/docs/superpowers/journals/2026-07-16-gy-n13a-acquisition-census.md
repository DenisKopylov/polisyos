# GY-N13a Acquisition-Layer Reality Census Journal

Canonical plan: `docs/superpowers/plans/2026-07-16-gy-n13a-acquisition-census.md`.

## Task 1 — evidence schema and read-only catalog identity

Status: `complete`

Scope: strict census boundary DTOs, deterministic semantic hashing, a fail-closed read-only DuckDB
catalog identity/full-denominator query, and the initial checker CLI. No fetch, connector, ingestion,
canonical-store, CG, or world owner is imported or executed.

### RED witness

Command:

```text
uv run pytest -q tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py
```

Observed result before implementation: `6 failed`; every test failed on the expected missing owner
module, `ModuleNotFoundError: tools.quality.validation.layer3_gy_n13a_acquisition_census`.

Review then tightened the Task-1 boundary. The added tests produced `11 failed, 6 passed` before the
repair, witnessing each missing property: blank/null denominator rows were silently omitted, the
original top-level-only hash boundary mishandled nested operational time, the per-attempt call budget
allowed values above one, manifest versions/time were not literal/typed, count maps admitted
negatives, and resolution labels did not require their decisive evidence. Task 5 later superseded
that boundary with recursive exclusion of declared operational fields at every nesting level.

### GREEN witness

Focused command:

```text
uv run pytest -q tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py
```

Observed result after the review repairs: `17 passed`.

The checker was then pointed explicitly at the ignored, read-only production snapshot:

```text
uv run python tools/quality/validation/check_layer3_gy_n13a_acquisition_census.py \
  --catalog-path /Users/deniskopylov/polisyos/policy-engine/production_data/\
datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb
```

Observed result: `status=pass`; 124 binding metrics, 12 connector families, 56,846 binding rows,
execution tiers 34,308 `transport_ready` + 7,668 `fetchable` + 14,870 `catalog`, and catalog identity
`sha256:4a1eab1363a948a875d00b0ae3929f47b763ba429c85776709641d6ca7960dd7`.

Ruff command:

```text
uv run --with ruff ruff check \
  tools/quality/validation/layer3_gy_n13a_acquisition_census.py \
  tools/quality/validation/check_layer3_gy_n13a_acquisition_census.py \
  tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py
```

Observed result: `All checks passed!`.

## Task 2 — W1 catalog-to-runtime seam and reverse denominator

Status: `complete`

Scope: binding-linked metric resolution over the full 124-metric denominator, generic cycle-demand
projection from the three frozen upstream owners, and measured binding/local/alignment/executable
support for every projected demand. No runtime owner, catalog row, engine, connector, or production
file was changed.

### RED witness

Command:

```text
uv run pytest -q tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py
```

Observed result after adding W1 witnesses: `9 failed, 16 passed, 1 skipped`. The failures were the
missing binding-linked resolution owner, missing generic demand projection/measurement owner, and
the stricter alignment evidence fields. The production-only witness was intentionally gated by
`POLISYOS_N13A_PRODUCTION_CATALOG`.

The fixture flips prove the decisive predicates: an unrelated-dataset observation/alignment cannot
resolve a metric; moving that evidence onto the bound dataset changes the class; removing the owner
identity alignment changes `resolves_via_alignment` to `unresolved`; a new binding metric grows the
denominator without code changes; and confidence/proxy/penalty mutations reorder and update the
preserved owner candidates.

### GREEN witness

Focused command:

```text
uv run pytest -q tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py
```

Initial pre-review GREEN result (superseded below): `27 passed, 1 skipped`. This included a checker
witness using upstream artifacts outside the repository; their identities fall back to stable
`external://<filename>` locators rather than environment-specific absolute paths.

Independent review then found two load-bearing gaps and both were repaired before commit. First,
metric rows were accepted without proving their dataset/distribution/connector/profile ownership.
All catalog read paths now share one fail-closed relational gate covering the owner dataset, exact
distribution and dataset edge, connector/profile agreement, request dataset ID, legal execution
tier, equality with the owner dataset tier, executable parser support, and exact executable
schema-profile ownership. Fixture mutations prove each edge is decisive—including a catalog-owned
row relabeled `transport_ready`—and the source, resolution, and reverse-demand readers all reject the
same fake executable row. Second, the resolution limitation was derived from the resolution label.
It is now derived from measured catalog key columns through `resolution_scope`; a source flip adds a
distribution/raw-field edge, removes the limitation, and makes that field decisive for resolution.

Post-review focused result: `41 passed, 1 skipped`; Ruff: `All checks passed!`. The opt-in production
witness remains `1 passed`, but its expected denominator and partition are now independently queried
from the live catalog. It contains no snapshot count, unresolved-ID, proxy-count, or family-name
assertions, so a legitimate owner-data growth event changes the measured result without code edits.
With the production witness enabled, the complete focused file is `42 passed`.

Production read-only witness:

```text
POLISYOS_N13A_PRODUCTION_CATALOG=/Users/deniskopylov/polisyos/policy-engine/\
production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb \
uv run pytest -q \
  tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py::\
test_production_metric_resolution_partition_when_catalog_is_declared
```

Observed result: `1 passed`. The recomputed full partition is 95 `resolves_exact` + 20
`resolves_via_alignment` + 9 `unresolved` = 124. The 115 resolved rows include four whose complete
owner-alignment support is proxy-only: `avg_income`, `banking_sector_stability`, `road_quality`, and
`school_quality`. Because `ds_metric_bindings` does not bind a distribution field/raw variable, all
115 resolved rows truthfully have `resolution_scope=dataset_level_identity` and retain
`catalog_binding_field_edge_missing`; exact observation rows do not erase that schema-wide
limitation.

The unresolved denominator is exactly:

```text
access_to_justice, alcohol_consumption, avg_price, conflict_intensity,
export_diversification, inflation_rate, life_expectancy_gap, median_age,
noncommunicable_disease_mortality
```

The W1 checker, run against the same read-only snapshot, measured 19 distinct cycle-demand
variables. Four have executable exact bindings (`education_spending`, `school_quality`,
`tertiary_enrollment`, `years_of_schooling`); 15 are typed `binding_gap`; none are
`connector_gap`. The 15 exact residuals are:

```text
avg_hh_income_uah, avg_household_income, cells.distress_score,
combined_demand_emissions_burden, global.tax_rate, government.balance,
heat_wave_environmental_equity_burden, learning, low_income_renter_energy_costs,
msme_credit_access, msme_survival_rate, particulate_emissions,
residential_peak_demand, teaching, watershed_slope
```

Narrow projection bindings:

- capstone cycle demands: 18 path instances,
  `sha256:55f44ad9dc9fe12f829b086bab64723f7b25ca25487388111bd4a9e8eb68305e`;
- L6 world slots: 3 path instances,
  `sha256:5abae068a10765588e03cb3a961efbbdf01f91756fbf0271c2d0832ed308332e`;
- value-gate targets: 3 path instances,
  `sha256:84486eb5ef6f79b025338f79920e093afe2012fbb1b64a70018118a525ff1617`.

These are path-derived projections over mapping members and array items. No domain name, variable
value, expected count, academic alias, or loose global name overlap is a classifier input.

## Task 3 — W2 capstone route reality

Status: complete.

The route denominator is projected generically from every member of `capstone.domain_runs`. The
narrow projection preserves the owner witness kind, demanded variable set, candidate/gap identity,
N7 gap and recommended strategy, terminal blockers, missing requirement fields, and exact missing
link. It excludes free-form request prose. The current three-route projection is content-bound as:

```text
capstone_acquisition_routes
projected_item_count=3
sha256:c1c2f88469bfb8d6675bf7cd7011ffbae123657cf5533d1143bcbb8c5ba8f53c
```

The owner gate cross-checks the witness route reference, terminal `data_need_spec`, and matching N7
acquisition record. An `owner_data_gap` is row-addressable only when the owner source is
`l1_dcat_variable_availability`, the missing field is exactly one
`canonical_variable_observations:<variable>`, and the availability/producer references bind that
same variable. Missing or conflicting gap IDs, availability evidence, or variable IDs fail closed.

The class precedence is explicit and role-independent:

1. every witness other than `owner_data_gap` is `not_a_data_gap`;
2. a validated `owner_data_gap` with local canonical observations is `local_lift`;
3. otherwise, an exact `fetchable`/`transport_ready` binding is `live_fetchable`;
4. otherwise the row-addressable route is typed `unresolved` rather than forced into a live lane.

The route key, `domain_role`, domain names, and expected reconnaissance class are never classifier
inputs. Persisted labels are validated against the measured supply algebra, so pinning a label does
not survive model validation.

### Production result

Read-only checker command:

```text
uv run python tools/quality/validation/check_layer3_gy_n13a_acquisition_census.py \
  --catalog-path /Users/deniskopylov/polisyos/policy-engine/production_data/\
datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb
```

The recomputed distribution is `not_a_data_gap=3`; there is no current capstone-eligible data-only
demonstration lane.

| Route role | Declared variables | Bindings | Executable | Local observations | Alignments | Class | Exact missing link |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| education | 4 | 147 | 128 | 111 | 2 (2 non-proxy) | `not_a_data_gap` | `method_estimand_binding_mismatch` |
| first_vertical | 4 | 0 | 0 | 0 | 0 | `not_a_data_gap` | `grounding_relation_or_owner_lever:gy_n4.emergency_tax_relief` |
| unseen | 5 | 0 | 0 | 0 | 0 | `not_a_data_gap` | `grounding_relation_or_owner_lever:candidate_fallback_1950390310ca54cb` |

Education's declared variables are `learning`, `teaching`, `tertiary_enrollment`, and
`years_of_schooling`; the binding tier split is 19 catalog + 4 fetchable + 124 transport-ready. The
rows cannot repair an estimand-shaped refusal. The first-vertical and unseen routes are structural
world/grounding-link gaps with `value_world_model_record_unwired` preserved among their blockers.
The actual unseen demand is the five-variable heat-wave electricity/emissions/equity route; stale
water-quality prose does not enter or move the projection.

Adjacent local evidence was measured but deliberately not promoted. The catalog has 1,164,742
`education_outcomes` observations with no owner edge to the education estimand refusal. The frozen
D3 build manifest records `corrected_firm_panels.parquet` at 11,574 rows
(`sha256:f8e987dcb1e724866b8ac431dfc508b6525c6cd411ca57c57b45218e1ea194f4`) and
`calibrated_household_cells.parquet` at 100 rows
(`sha256:a63f3483450f05aea0180f8d3e5eb6899b8734155361060f233a7e2e4a3c59a6`). Neither
has an owner mapping to the first-vertical missing requirement, so both remain unmapped context.

### RED/GREEN and flips

The initial focused route slice failed five tests because the route projection, strict nested
evidence, measurement owner, and class algebra did not yet exist. The GREEN file collects 52 tests:
50 pass and the two declared production witnesses skip unless the read-only catalog is supplied.
The opt-in actual-capstone W2 witness passes.

Decisive mutations cover: persisted class relabeling; witness/spec/planner gap-ID mismatch; missing
availability owner; missing-variable mismatch; local observation deletion; executable-tier decay;
adding both local rows and a transport-ready binding to a structural route; route-key/role rename;
and stale water-quality request prose. The first two supply flips move a synthetic honest
`owner_data_gap` through `local_lift` -> `live_fetchable` -> `unresolved`; adding rows to a structural
route leaves it `not_a_data_gap`.

Focused Ruff lint passes. Formatting was applied only to the three touched Python files.

## Task 4 — W3 owner FetchPlan generation, never execution

Status: implementation and production owner proof complete; consolidated restoring source-flip lane
remains owned by Task 6.

The proof opens the supplied DuckDB with the existing `DatasetCatalogGraph`, resolves a sample whose
membership is derived from resolved executable route demand plus connector-family representatives,
and injects a recording graph into `RetrievalService._resolve_via_catalog`. Every projected field is
cross-checked against the binding returned by that owner call. The sample grows when a new owner
family becomes a primary executable binding; there is no connector-family constant in the selector.

The execution boundary is behavioral. `RetrievalService` receives a typed forbidden executor whose
`preview` and `execute` methods raise `fetch_plan_execution_forbidden` before side effects. The proof
also records zero calls, one catalog resolution per sampled metric, identical before/after catalog
content hashes, and identical empty scratch-tree hashes. The receipt names exactly the two
behaviorally guarded executor edges, `FetchExecutor.execute` and `FetchExecutor.preview`; it does not
claim marker-only enforcement over sibling connector, ingestion, or store APIs. Calling the private
catalog resolver reaches none of those owners by construction, while a malicious service fixture
that invokes either executor entrypoint turns RED before its fallback assertion.

### Production proof

The read-only production catalog generated seven real owner plans. The data-derived metric sample is:

| Metric | Selection reason | Connector | Request dataset | Profile | Tier |
| --- | --- | --- | --- | --- | --- |
| `air_quality_index` | primary connector | `worldbank.wdi` | `EN.ATM.PM25.MC.M3` | `worldbank_wdi` | `transport_ready` |
| `avg_income` | primary connector | `sdmx.source` | `DSD_EARNINGS@RMW` | `oecd_sdmx` | `transport_ready` |
| `cultural_cluster` | primary connector | `wvs.wave7` | `A173` | `wvs_wave7` | `transport_ready` |
| `infant_mortality` | primary connector | `unpd.data` | `22` | `unpd_dataportal` | `transport_ready` |
| `tertiary_enrollment` | education route | `worldbank.wdi` | `GCI.5THPILLAR.XQ` | `worldbank_wdi` | `transport_ready` |
| `wage_growth` | primary connector | `eurostat.data` | `EARN_SES_ANNUAL` | `eurostat_public` | `transport_ready` |
| `years_of_schooling` | education route | `worldbank.wdi` | `UIS.SLE.123.M` | `worldbank_wdi` | `transport_ready` |

All seven plans have `source_lane=catalog`, `persist_payload=false`, real catalog dataset and
distribution IDs, and owner type `polisyos.core.contracts.control.FetchPlan`. The fence receipt is
`preview_calls=0`, `execute_calls=0`, `catalog_resolution_calls=7`; catalog SHA-256 remained
`4a1eab1363a948a875d00b0ae3929f47b763ba429c85776709641d6ca7960dd7`, and both scratch hashes are
the empty-tree SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

### RED/GREEN witness

The initial W3 slice failed four tests on the intentionally missing sample/proof/fence models and
generation owner. After implementation, the complete focused file with the production catalog
declared is `57 passed`. The fixture suite covers real owner output, sample growth from a new family,
plan field validation, forbidden persistence/non-executable-tier claims, and a live execution
attempt stopped by the fence. The production-only proof passes against the actual catalog and actual
three-route W2 projection. Ruff and the consolidated source-flip lane are verified at the workstream
commit/Task-6 boundary respectively.

## Task 5 — W4 stratified connector reality census

Status: complete.

The selector derives its denominator from the 12 distinct validated binding `connector_id` values
and chooses 12 unique distributions per family (144 total). The declared strata are
`execution_tier × fixed quality bucket`; selection round-robins across extant strata and prefers,
within each stratum, an exact schema profile, a recognized open-license identifier, no auth, a
direct HTTP endpoint, parser support, binding confidence, quality, and stable owner IDs. The family
projection binds all population and selected-stratum counts as
`sha256:daad5dce7ae550a6e1f84a034137754125be2b0e46fe2b7f9388c5e2dc97cca5`.

Every family resolves through `fabric.connectors.components.__polisyos_components__`; all 12 have
zero `validate_protocol_compliance` violations. The repaired E7 gate invokes six public
`ConnectorTestHarness` checks for every family (protocol compliance, required attributes, async
core methods, capability-gated methods, unique sessions, and idempotent disconnect), then exercises
all 144 selected carriers through the actual concrete connector using owner-resolved
`ConnectionConfig` and `FetchRequest` objects under `APISimulator(REPLAY)`. A socket-connect fence
proved zero escape attempts and zero actual network calls in the offline lane. An intercepted
`MissingFixtureError` is recorded as positive transport-fence evidence plus a typed missing-fixture
finding; it is never parser conformance or liveness.

| Family | Offline carriers | REPLAY interceptions | Pre-transport findings | Harness failures |
| --- | ---: | ---: | ---: | ---: |
| `ckan.resource` | 12 | 12 | 0 | 0 |
| `eurostat.data` | 12 | 12 | 0 | 0 |
| `opendatasoft.ods` | 12 | 12 | 0 | 0 |
| `rest.json` | 12 | 12 | 0 | 0 |
| `sdmx.source` | 12 | 8 | 4 | 0 |
| `socrata.soda` | 12 | 12 | 0 | 0 |
| `ukons.datasets` | 12 | 12 | 0 | 0 |
| `unesco_uis.data` | 12 | 12 | 0 | 0 |
| `unpd.data` | 12 | 0 | 12 | 0 |
| `who.indicators` | 12 | 12 | 0 | 0 |
| `worldbank.wdi` | 12 | 12 | 0 | 0 |
| `wvs.wave7` | 12 | 12 | 0 | 0 |

The complete offline result is 144 carrier receipts, 128 actual connector interceptions, 16 typed
pre-transport findings, and zero network escapes. SDMX's four findings are OECD carriers whose
declared `1/60` request rate cannot acquire a one-token request from the current burst-size owner;
the other eight SDMX carriers reach REPLAY. All 12 UNPD carriers lack the connector-required
country/location filter. These findings remain nested by `attempt_id`; a family aggregate never
overwrites carrier-specific evidence.

### Fail-closed preflight

All 144 selected rows are journaled outcomes. Only 18 passed every live-call predicate: component
and protocol owner, that carrier's own safe REPLAY interception, exact
distribution/dataset/profile schema edge, matching source profile, no auth, executable tier, direct
HTTP(S), and a recognized open license. Candidate-specific schema/profile/auth/tier/endpoint/license
findings are evaluated before `dry_run_failed`, so a family-level finding cannot erase more precise
catalog evidence. The other 126 rows spent no call:

| Preflight disposition | Count |
| --- | ---: |
| `schema_profile_missing` | 42 |
| `license_unclear` | 42 |
| `endpoint_unusable` | 30 |
| `auth_required` | 12 |
| `live_attempt_authorized` | 18 |

This is deliberately narrower than treating an empty license field, `other-open`, or a catalog
claim such as `True` as permission. `unpd.data` is auth-required in the owner catalog. UK ONS has no
schema profiles. Eurostat/SDMX/WVS selected rows do not expose a direct HTTP distribution carrier.
Those are acquisition-layer findings, not reasons to improvise URLs, repair responses, or shrink
the family denominator.

### Journal-first live result and economics

The explicit live command ran one family at a time. Every authorized request carried one metric,
the exact owner schema profile, source-profile-derived rate interval, a 15-second effective timeout,
64 KiB response/decompression caps through `read_bounded_response_body`, `call_budget=1`, a Range
header, and a census user agent. Transport uses connect/read inactivity timeouts with no total
progress-kill timeout. The append-only JSONL request, periodic progress heartbeats, and raw-response
records were flushed and `fsync`ed before the classifier was called; the frozen self-contained
journal reconstructs that event stream byte-for-byte and binds it as
`sha256:75870c436a7b1621805d0cadb9b024a758e53388a675a261f9a8f842355adeff`. The 18 live attempts
record 18 `attempt_started`, 25 periodic `waiting`, 13 `response_headers`, and 17 body-progress
events; elapsed timing is operational, while the exact event stream remains content-bound.

| Family | Selected | Calls | Wall seconds | Derived outcomes | Aggregate state |
| --- | ---: | ---: | ---: | --- | --- |
| `ckan.resource` | 12 | 6 | 79.403 | 1 response-budget exceeded; 5 transport errors; 6 schema-profile missing | `characterization_failed` |
| `eurostat.data` | 12 | 0 | 0 | 12 endpoint unusable | `no_safe_live_attempt` |
| `opendatasoft.ods` | 12 | 0 | 0 | 6 license unclear; 6 schema-profile missing | `no_safe_live_attempt` |
| `rest.json` | 12 | 0 | 0 | 6 license unclear; 6 schema-profile missing | `no_safe_live_attempt` |
| `sdmx.source` | 12 | 0 | 0 | 6 endpoint unusable; 6 schema-profile missing | `no_safe_live_attempt` |
| `socrata.soda` | 12 | 0 | 0 | 6 license unclear; 6 schema-profile missing | `no_safe_live_attempt` |
| `ukons.datasets` | 12 | 0 | 0 | 12 schema-profile missing | `no_safe_live_attempt` |
| `unesco_uis.data` | 12 | 0 | 0 | 12 license unclear | `no_safe_live_attempt` |
| `unpd.data` | 12 | 0 | 0 | 12 auth required | `no_safe_live_attempt` |
| `who.indicators` | 12 | 0 | 0 | 12 license unclear | `no_safe_live_attempt` |
| `worldbank.wdi` | 12 | 12 | 1.896 | 12 alive, schema unverified | `live_characterized` |
| `wvs.wave7` | 12 | 0 | 0 | 12 endpoint unusable | `no_safe_live_attempt` |

Total paid live economics: 18 calls, 82.503 capture-wall seconds (81.299 summed request-wall
seconds), and 140,685 journaled response
bytes. The CKAN calls produced five 15-second timeout receipts and one response rejected by the
64 KiB owner limit; no endpoint was relabeled alive. All World Bank calls returned bounded 2xx
evidence, but every production schema profile is metadata-only (`sample_row_count=0`), so the
strongest earned state is `alive_schema_unverified`, never `alive_conformant`.

The frozen journal is
`architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json`: 719,062 bytes,
file `sha256:027b3824f77c325ec4550afbf1ea75fb7a4b70c78070d6bb3cb471d73110d3fd`, semantic content
`sha256:e1b38f303965be715f61c70f9dc00f567fe1b5415c1dd11d89c02a19a7228eb9`. Operational timestamps,
elapsed heartbeat timing, and nested wall-time economics are recursively excluded from semantic
identity; exact artifact/event hashes still bind the journal bytes. It contains no canonical-store
admission.

### Behavioral verification

The focused production file is `77 passed`. Decisive tests cover a new data family growing the
denominator, actual connector/harness/simulator receipts, exact-carrier preflight authority, a live
row with no raw response, the exact `dead -> alive` relabel, metadata-only
`alive_conformant` inflation, unearned family aggregate state, periodic heartbeat ordering,
progress-safe inactivity timeouts, and classifier invocation only after raw-response fsync. The
offline checker reloads the frozen journal, re-derives the 144-row sample and all 144 actual
connector dry-run receipts, all preflights, every liveness state, scorecard counts, and D3
tier-decay findings without performing a network call.

## Task 6 — D2 backlog and frozen recurring census

Status: complete.

The frozen census contains the complete 124-row metric-resolution denominator, all 19 reverse
demand variables and 15 typed residuals, all three capstone routes, seven owner-generated FetchPlan
proofs, the 12-family scorecard, and all 15 growth-backlog rows. Its narrow bindings are the catalog
content identity, three upstream demand projections, the three-route capstone projection, the
data-derived connector-family projection, and the frozen live-journal semantic hash. No whole
capstone hash or timestamp is used as a semantic classifier input.

The existing N7 owner `polisyos.runtime.quality.acquisition_planner.plan_evidence_acquisition`
requires authority-bearing claim/requirement gaps plus optional VOI decision rows. The W1 residuals
are raw metric-level gaps and do not carry those semantics, so converting them would invent a
parallel acquisition/VOI contract. Every backlog row therefore records
`voi_owner_fit=metric_residual_granularity_not_supported`,
`authority_boundary=ranking_only_not_voi`, and `voi_owner_integration=routed_to_gy_n13b`. The exact
interim score is existing binding confidence × distinct demand-source count. All 15 current gaps are
true `binding_gap` rows with confidence 0, so all scores are honestly 0; deterministic order uses
route demand, then confidence, then variable ID. It is not presented as VOI.

Top ten interim rows and exact demand sources:

| Rank | Variable | Demand | Exact demand sources |
| ---: | --- | ---: | --- |
| 1 | `avg_hh_income_uah` | 2 | `capstone.domain_runs.first_vertical.design_problem.objectives[0].metric_id`; `capstone.domain_runs.first_vertical.design_problem.outcome_of_interest.metric_id` |
| 2 | `particulate_emissions` | 2 | `capstone.domain_runs.unseen.design_problem.candidate_lever_space.candidate_levers[1].target_slot`; `capstone.domain_runs.unseen.design_problem.objectives[1].metric_id` |
| 3 | `residential_peak_demand` | 2 | `capstone.domain_runs.unseen.design_problem.candidate_lever_space.candidate_levers[0].target_slot`; `capstone.domain_runs.unseen.design_problem.objectives[0].metric_id` |
| 4 | `avg_household_income` | 1 | `capstone.domain_runs.first_vertical.design_problem.outcome_of_interest.target_variable` |
| 5 | `cells.distress_score` | 1 | `intervention_substrate.measured_coverage.world_slot.details[1].target_world_slots[0]` |
| 6 | `combined_demand_emissions_burden` | 1 | `capstone.domain_runs.unseen.design_problem.outcome_of_interest.metric_id` |
| 7 | `global.tax_rate` | 1 | `intervention_substrate.measured_coverage.world_slot.details[2].target_world_slots[0]` |
| 8 | `government.balance` | 1 | `intervention_substrate.measured_coverage.world_slot.details[0].target_world_slots[0]` |
| 9 | `heat_wave_environmental_equity_burden` | 1 | `capstone.domain_runs.unseen.design_problem.outcome_of_interest.target_variable` |
| 10 | `learning` | 1 | `capstone.domain_runs.education.design_problem.candidate_lever_space.candidate_levers[1].target_slot` |

### Artifact lifecycle and recurrence

- census file: 5,599,325 bytes,
  `sha256:63212c8ccdcd80e96f8ae5903a74e4587090cfe096392e00069d30c17ba64791`;
- census semantic content (nested operational time/economics recursively excluded):
  `sha256:62c7e666c58002509c0cd3b65ac1a22630b6b55e7631df676986ab829be5f3c2`;
- live journal semantic binding:
  `sha256:e1b38f303965be715f61c70f9dc00f567fe1b5415c1dd11d89c02a19a7228eb9`;
- builder validator:
  `sha256:704b1b5a10f8357ad6d7d18d19589d7b2da1ac0a504222155d9e94d7e63a77f4`;
- lifecycle checker:
  `sha256:cae954933b6b9ae5fb3210c2f4336852b046a89d722504e743aec7639149d474`.

Two independent `--write` passes over the real catalog and frozen journal produced the identical
census file hash above. `--check` rederived the same manifest and canonical bytes. Explicit
`--capture-live-journal` refuses pre-existing journal/event paths, captures raw evidence first, and
then writes a new dated census; offline `--write`/`--check` never spend a network call. Both outputs
are registered as one `generated_committed` GY lifecycle family, and the generated architecture
inventory was synchronized.

The five nested corrupt-field cases all turned RED: metric binding evidence, route class, FetchPlan
owner edge, decisive tier-decay finding, and backlog order. The restoring behavioral source-flip
suite turned all nine decisive mutations RED: `dead→alive`, a live scorecard row without raw
response, route-label pinning, FetchPlan fence removal, backlog-order reversal, a hardcoded
connector-family denominator, replacing the actual connector fetch with marker-only sleep,
reintroducing a total timeout that can kill progress, and leaving nested run economics in semantic
hashes. Each subprocess verified the exact source SHA after restoration.

The focused file contains 77 tests. All 77 passed with the read-only production catalog declared;
without it, 71 fixture tests passed and the six explicit production witnesses skipped. Ruff passed;
`git diff --check` passed again at the final commit boundary.

### N13b decision input

No frozen capstone route is currently a data-only demonstration lane: education is an estimand
binding refusal, while first-vertical and unseen are structural grounding/world-record gaps. N13b
must not relabel one as local/live merely to demonstrate execution. The seven generated plans prove
the catalog seam is ready but remain `implemented_but_not_orchestrated`; actual acquisition,
overlay admission, epoch effects, and a capstone-eligible owner data gap remain N13b work. The
audit artifact is the N13a surface; Atlas/DS15 UI projection is explicitly outside this lane.

## Task 7 — targeted closeout

Status: `complete`; one pre-existing consumed-artifact residual remains disclosed and unchanged.

### Pattern closeout

The failure/repair register was reopened after implementation. N13a closes P29/P31/P32/P33 for its
own claims by recomputing every class from owner evidence, deriving both denominators from data,
using one journal-first intake/classification boundary, and exercising nine remove-the-property
source flips plus five nested corruptions. It does not claim a runtime acquisition bridge: W3
remains `implemented_but_not_orchestrated`, execution is fenced, and canonical-store/UI surfaces are
respectively forbidden and `surface_out_of_scope`. This avoids P01/P02/P03 inflation while routing
the actual bridge to N13b. The L6/N8/N10 failure described below was reproduced in the clean main
checkout, not excluded by assertion, satisfying the P34 isolation rule.

### Final targeted verification

| Lane | Result | Closeout evidence |
| --- | --- | --- |
| N13a focused file | PASS | 77 tests passed with the production catalog declared |
| N13a `--check` | PASS | committed manifest and canonical bytes rederived offline |
| N13a corrupt-field lane | PASS | all 5 decisive nested corruptions turned RED |
| N13a restoring source flips | PASS | all 9 decisive mutations turned RED; exact source bytes restored |
| Ruff | PASS | builder, checker, and focused test file |
| N4 design-generation contract | PASS | serial `--check` |
| composition artifacts | PASS | serial `--check` |
| N10a second-domain pack | PASS | serial clean-main `--check`; 0.909 s validator wall time |
| L6 intervention substrate | DISCLOSED RED | behavior itself passes with full coverage and zero issues; frozen receipt drift |
| N8 value gate | DISCLOSED RED | propagates the same `cycle_substrate_l6_bundle_content_mismatch` |
| N10 capstone | DISCLOSED RED | one issue: `known_vertical_owner_vocabulary_unavailable` wrapping that same mismatch; 108.835 s |
| 38-validator import/CLI census | PASS | 38/38 in fresh subprocesses; 65.853 s |
| architecture guardrails | PASS | `Architecture guardrail check passed.` |
| `git diff --check` | PASS | no whitespace errors |
| protected/production-data diff | PASS | empty for `production_data`, Atlas worktree, `docs/brand`, `apps`, and Atlas plans |

The L6 residual is narrow and pre-existing. The committed L6 contract already reports live bundle
`sha256:816eff220b460b77e79951afa579407ac439128cda243f1723429b9b52c88356`, while the frozen N10a
pack binds `sha256:7baae8f3404668286ecf94868071117799b1589371cceec7c89a7bb866e3024e`.
Direct L6 recomputation has identical passing coverage counts and no behavioral issues; its only
payload differences are the three legal `provision_ref` values changing from checkout-absolute
DuckDB URIs to repo-relative DuckDB URIs, duplicated under `measured_coverage` and
`behavior_report`. The existing generation-cycle disposition ledger already names this
`gy_s3_intervention_substrate_contract_stale`. Both N8 and N10 were rerun from clean `main`, which
contains none of the N13a commits, and reproduced the mismatch. N13a changes no L6, N8, N10a,
value-gate, capstone, runtime, or production-data byte, so updating those artifacts here would
violate the lane boundary and the user's unchanged-artifact gate.

The branch diff is restricted to the two N13a validation modules, one focused test file, two frozen
N13a artifacts, generated-artifact registration/reference, the active GY plan, and this plan/journal.
The N10 merge remains `7e035a42695add42540c260bf61e6110d0fa3c93`; the scoped N13a commits before
closeout are `585948078`, `1f6f50313`, `08a41cf1f`, `d2430b1d6`, `5d66b6411`, `14434b632`, and
`752e4c10a`. The independent-review repair is `b8d1f445e`.

Independent review found five evidence-backed closure defects. The recurring E7 gate now runs each
selected carrier through its concrete connector and the public harness under zero-network REPLAY,
and live authorization requires both the complete, zero-failure family harness set and the exact
carrier's intercepted/no-escape receipt. E9 now journals periodic progress heartbeats and uses
connect/read inactivity timeouts without a total timeout that can kill a progressing response.
Semantic hashing now recursively excludes declared run economics, while exact artifact/event hashes
still bind their bytes. The W3 execution fence now claims and behaviorally guards only the two actual
`FetchExecutor.execute`/`preview` edges. Independent re-review found no behavioral blocker; the
repaired 77-test focused suite, nine source flips, five corruption cases, byte-stable writer,
offline checker, Ruff, 38-validator census, and architecture guardrails all passed at closeout.
