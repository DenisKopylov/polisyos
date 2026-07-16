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
repair, witnessing each missing property: blank/null denominator rows were silently omitted, nested
`observed_at` was incorrectly erased from the hash, the per-attempt call budget allowed values above
one, manifest versions/time were not literal/typed, count maps admitted negatives, and resolution
labels did not require their decisive evidence.

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
