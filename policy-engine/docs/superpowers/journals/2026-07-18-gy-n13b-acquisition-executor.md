# GY-N13b Acquisition Executor Journal

Canonical plan: `docs/superpowers/plans/2026-07-17-gy-n13b-acquisition-executor.md`.

Status: `closed_typed_deeper_terminal` on 2026-07-19; pending architect review; not merged. The
2026-07-18 stop receipt remains below as historical evidence. No world-growth epoch exists.

## Step 0 — landing and provenance repair

Status: `complete`.

- N13a merge-tree was clean and main received merge commit
  `719d7a35a2221f681a27d69b877c6ea8d58dd6d8`, citing audited census commit `154f2b11b` and semantic
  identity `sha256:62c7e666c58002509c0cd3b65ac1a22630b6b55e7631df676986ab829be5f3c2`.
- The path-relative L6 provision repair and provenance-only L6 → N8 → N10 → N13a ripple landed in
  scoped commits `986a54daa`, `6e71f9fc3`, `8eed73d7d`, `f167adb04`, `46447ae67`, `7c648b045`,
  `687545824`, and `a906ed7c1`. Semantic movement was not observed.
- Final upstream file identities used by this lane: N10
  `sha256:92d6bcc88dc703d45cdcd5e9960974b4c9fb00f879a6295d97c95b81f35e1636`; N13a
  `sha256:5807a9cbb1541b2bd0a12771aed478f19a6672bdfbe313ad868eebee2a4a8d9a`.
- The isolated branch is `codex/gy-n13b-acquisition-executor`. Atlas paths and worktrees were not
  touched; production data remained read-only.

## Implemented foundations before the historical stop

Historical status: `implemented_and_focused_verified`, before the resumption completed the audit
artifact, lifecycle, derivation acceptance, and re-entry contracts.

The branch wires N7 to the real catalog plan owner, consolidates journal-first evidence, implements
strict acquisition authority/passports/quarantine, provides the immutable overlay + shared L1 read
chokepoint, derives last-mile field edges, and implements content-addressed derivation certificates.
These foundations are covered by scoped commits from `ade434ba0` through `ecf9bd449`; the exact
sequence is available from `git log --reverse a906ed7c1..HEAD`.

The exact World Bank carrier authority is content-bound by:

- registry file SHA-256 `be8c231ba429585d92c6f4fbd3044d1911302b15051fd7525cafaab05ab6c98d`;
- two-attempt provision SHA-256 `26b6ea601c1cd9abb5a02c5f159f728575ead28d47892ebdb85142c17c7217ad`;
- attempt-001 harness SHA-256 `ee1d1bef74a22714329ed3fbd362a2e0ceb3cabc73b5c322e969602d4c6e69bf`;
- attempt-002 harness SHA-256 `24b5835c62e1cae4fd776439f7fd7b174d4fa56325ace3aa700fd37937af7ebf`.

The selected edge is N13a backlog rank 8, `government.balance` ← `gov_balance` ← World Bank WDI
`GC.BAL.CASH.CD`, catalog dataset `295e06c73f2cbd166d2c`, distribution
`11d00e4786011c8fc113`, CC-BY-4.0, `transport_ready`, binding confidence 0.87. Percent-of-GDP
`GC.BAL.CASH.GD.ZS` remains an explicit `basis_mismatch` and was never substituted.

## Local-lift full denominator

Status: `terminal_no_admissible_local_binding`.

All 15 N13a `binding_gap` residuals remain in the denominator. None has an owner-admissible local
lift. In particular:

- `calibrated_household_cells.parquet`: 100 rows, 26 cells, 4 periods, SHA-256
  `a63f3483450f05aea0180f8d3e5eb6899b8734155361060f233a7e2e4a3c59a6`. The field
  `household_income_mean` is semantically adjacent to the income residuals, but neither Parquet nor
  its D3 contract proves currency, nominal/real basis, base year, source-snapshot identity, or
  license/ToS authority. Present values and an `income` name do not satisfy the passport.
- `corrected_firm_panels.parquet`: 11,574 rows / 586 agents / 19 periods, SHA-256
  `f8e987dcb1e724866b8ac431dfc508b6525c6cd411ca57c57b45218e1ea194f4`. It contains the derived
  `corrected_exit_bias` construct, not an observed `cells.distress_score`. Only 80 rows / 19 agents
  overlap the firm-fundamentals owner by agent and zero overlap at matching periods. No catalog
  alignment, D5 derivation certificate, construct-validity proof, or rights receipt closes that gap.

No local passport was minted and no local epoch was written.

## Journaled live execution

Status: `terminal_no_admission`.

The recurring owner first rejected reopening a non-empty journal before transport, so no call was
spent. Commit `282a33169` repairs the class: it reopens only a fully canonical, terminal-closed
history; validates request, transport, heartbeats, raw bytes, and terminal links; preserves prior
bytes; and scopes the one-call proof to the exact attempt. Focused journal/transport/live-executor
tests passed before retry.

| Attempt | Request | Calls | Max paid elapsed | Raw bytes | HTTP | Owner-derived terminal |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `...-001` | UKR, 2013 | 1 | 6.945 s | 85 | 200 | `quarantined_live_raw_response_shape_drift` |
| `...-002` | UKR, 2000–2024 | 1 | 15.766 s | 0 | — | `failed_retry_exhausted_error` |

Attempt 001 returned a World Bank envelope declaring zero pages and no data. The raw response was
journaled before classification and persisted in CAS; it was not response-repaired. Attempt 002
tested the honest broader-period lever, emitted waiting heartbeats, and exhausted the owner-derived
15-second timeout before any response bytes arrived. Retries remained one per exact authorized
carrier.

Evidence identities:

- journal: 18 events, 8,779 bytes, SHA-256
  `e4fefafbc107a47bb72419734f5eb3fb2ff971baaaf3192be26ad58e745afbab`;
- raw CAS blob: 85 bytes, content SHA-256
  `244e629ceec4b53324246967388d17b706efe2207744b8148d60ea52dbccd264`;
- raw CAS manifest SHA-256
  `8690c2640658984a6c6e76a9e0cb7c300d1672b42514aa5b5fc4ff48e7db9603`;
- attempt-001 raw event SHA-256
  `3748d96fdefb6a20b075501985bef3da7ba3c3e22cf7ce0ef818f267af8052ab`;
- attempt-001 terminal SHA-256
  `1d489c7bdeba9d38687e9a1edca6a606678b70738e946591ac477a6635379386`;
- attempt-002 terminal SHA-256
  `ee2119e70bbfe5a731e614e316f518db396fa478404157cab017659da1a078ec`.

Both terminals resolve from the full journal denominator. Both have `quarantine=true` and
`response_admitted=false`.

## Historical stop-law result

The two demonstration lanes are exhausted honestly:

- local-lift: 0/15 admissible;
- live-fetch: 2 exact calls, 0 normalized rows, 0 passports, 0 admitted rows;
- overlay: absent; epoch count 0;
- `government.balance` availability before/after: 0 datasets, 0 metric bindings, 0 observations;
- production catalog SHA-256 before/after:
  `4a1eab1363a948a875d00b0ae3929f47b763ba429c85776709641d6ca7960dd7`;
- capstone route classifications: unchanged and still structural; no adjacent rows were laundered.

The binding instruction says that if both lanes die, stop and report. Therefore the derivation
acceptance demonstration, frozen N13b contract, generated-artifact registration, 39-validator
closeout, and merge are deliberately not claimed. Their precise capability state is
`implemented_but_not_demonstrated` plus `artifact_missing`, `lifecycle_registration_missing`, and
`semantic_test_missing` for the world-growth event.

Resumption requires new owner evidence: a content-bound local rights/unit/basis owner for one
demanded residual, or a separately authorized live carrier with honest UKR coverage. Reusing the
empty response, weakening passport gates, promoting quarantine, or retrying without a new exact E7
receipt is forbidden.

## Verification before stop

- two-attempt authority derivation: byte-stable twice and canonical `--check-target-owners` green;
- focused authority/executor suite: 49 passed;
- focused journal/transport/live-executor suite: 59 passed;
- Ruff on touched live/journal/authority files: passed;
- architecture guardrails after the recurring-journal repair: passed;
- N13a census `--check` remained green when its shared owner helpers were exposed;
- baseline content hash after both live calls equals its pre-call hash.

One unrelated pre-existing unit failure remains isolated at base `a906ed7c1`:
`tests/unit/fabric/connectors/sources/test_http_connector_base.py::test_connection_config_redaction_uses_shared_secret_pii_scanner`.
It was not touched or excluded from an otherwise failing target suite.

Evidence-preservation commits:

- `7d6239707` — authorize a second exact live acquisition carrier;
- `282a33169` — reopen terminal-closed acquisition journals;
- `423dcd606` — preserve terminal acquisition evidence.

## Evidence-driven resumption and frozen closure

Status: `closed_typed_deeper_terminal`; frozen implementation `6280e487f`; pending architect
review; not merged.

- `executor_capability_status=implemented`; `surface_status=audit_surface`;
  `demonstration_status=typed_deeper_terminal`.
- World growth remained honest: `status=no_growth`, event count 0, overlay epoch count 0, admitted
  observation count 0, and `government.balance` availability 0 -> 0. The demanding-stage terminal
  is `deeper_terminal_primary_carrier_characterization_failed`.
- The resumption spent 3/6 authorized calls and left three unused. Across all five historical and
  resumption attempts there are five quarantine/terminal outcomes, two raw responses, three
  terminals without response bytes, and zero admitted responses.
- Local lift remains `0/15` with `no_admissible_local_binding`; no rights, unit, or basis authority
  was inferred from adjacent local rows.
- Both N10 residuals are closed:
  `owner_registration_derivation_missing_closed=true` and
  `journal_raw_evidence_persistence_missing_closed=true`; `open_residuals=[]`.
- All three capstone routes remain `not_a_data_gap`; `laundered_route_count=0`.

R1 decoded the already-paid 85-byte body as
`[{"page":0,"pages":0,"per_page":0,"total":0,"sourceid":null,"lastupdated":null},null]`,
therefore exactly `no_data_for_scope`. The body is bound as
`sha256:244e629ceec4b53324246967388d17b706efe2207744b8148d60ea52dbccd264`;
the R1 receipt is
`sha256:a46c3646be7caa696df3fc89096c369eca65e9f73596f7339b00a180f83b58bd`.
The prior elapsed evidence is 6.945391583998571 seconds for the small page and
15.766325374999724 seconds at the owner timeout.

### Resumption call ledger

| Attempt | Class | Max elapsed | Raw bytes | HTTP | Terminal |
| --- | --- | ---: | ---: | ---: | --- |
| `gy-n13b-worldbank-wdi-government-balance-usd-metadata-001` | indicator metadata | 1.0341310840012738 s | 756 | 200 | `quarantined_metadata_characterization_complete` |
| `gy-n13b-worldbank-wdi-government-balance-percent-gdp-metadata-001` | indicator metadata | 14.01588400000037 s | 0 | — | `failed_metadata_retryexhaustederror` |
| `gy-n13b-worldbank-wdi-inflation-index-001` | data fetch | 14.120988167000178 s | 0 | — | `failed_retry_exhausted_error` |

The metadata response proves `GC.BAL.CASH.CD` belongs to World Bank source 11, Africa Development
Indicators, rather than the catalog-declared WDI source profile. The evidence-derived carrier
disposition is `carrier_current_source_profile_mismatch`, and the recurring N13a owner records the
corresponding `transport_ready` tier-decay finding. The primary percent-of-GDP metadata attempt and
the CPI fetch each reached a typed terminal; neither authorized a retry.

### Derived acceptance and re-entry

The contracted real-terms case closed over owner-admissible epoch-0 catalog inputs without claiming
live world growth. It materialized one exact-year CPI derivation and served two distinct consumers;
the first materialization was a cache miss and the second a cache hit.

- recipe:
  `derivation-recipe:sha256:6a2b33103cbd25835d3d502a82c3f9392459b5076769813fc203c49b96a85e99`;
- certificate artifact:
  `sha256:2762950fb0162d50ee54af9947960a85db3b5ff80686f26a99f791726b9f0c0d`;
- derived artifact:
  `sha256:6f8bf2cfc76b89da8500b827c46237fcba4d22fa34fe4b3a569c42156991cb34`;
- consumer methods: `forecasting.univariate.exponential_smoothing@1.0.0` and
  `forecasting.univariate.theta@1.0.0`;
- negative terminals preserved: `basis_mismatch` and `model_output_not_observation`.

The real N7 re-entry trace is
`sha256:5a3aa348588478170d473c65f3504641c0313a16debb03f0382d9b6ecca83a52`.
It recomputes 0 -> 0 availability, zero fetch-plan executions, zero overlay epochs, and the honest
deeper terminal above.

### Frozen contract and lifecycle

- contract semantic identity:
  `sha256:1e2b91fcf8ff2410524d86dd486ffdb7f07e417372f608f16b00135d5aa84235`;
  file SHA-256 `8af3f4b9fd9458c30b7124c409a2a829757b6cf4404123380770daf4f03b3d8a`;
- lifecycle semantic identity:
  `sha256:991b84375cb07b7b58577529f3ee4d13b998631f86c4b7a4bd278e7be19b60b1`;
  file SHA-256 `58ac3aea57a5ff48c9620525fe6a9e01c7cf00adf4a28d0560cdb2c99a802e9e`;
- checker SHA-256 `f93c82cf68823708785703b85698e1b118a09eb5448e87be0bcf1ca68f166720`;
  recomputing owner SHA-256 `b0825cdaafc89a8ecc7cdb76d53bf9526a7076d13260335ca70c0b9866ef658b`;
- raw journal: 44 events, 21,347 bytes,
  `sha256:7dc382b08355301968643b09982940029f4caa2c2b60419268940b5b7a4d4635`;
- lifecycle: 40 registered outputs, 38 content-bound, two writer-managed, zero phantom outputs.

### Closure verification

- canonical N13b `--check`: pass, with byte stability 2/2 and baseline SHA-256 unchanged at
  `4a1eab1363a948a875d00b0ae3929f47b763ba429c85776709641d6ca7960dd7`;
- nested corrupt-field suite: 10/10 RED; restoring behavioral source flips: 15/15 RED with exact
  source SHA restoration;
- focused frozen-contract/overlay/derivation tests: 11 passed; Ruff passed across all 52 Python
  paths changed since `a906ed7c1`;
- serial owner chain: N13a census, N4, N8 (390/390 method denominator), composition, N10a, N10
  capstone, and the generation-cycle disposition ledger all passed;
- validator census: 39/39 contract checkers imported and exposed `--help`, zero failures in
  106.024 seconds. The raw filename glob is 40; the excluded file is the operational live runner
  `check_layer3_gy_acquisition_executor.py`, not a frozen contract validator;
- generated-artifact guardrail sync added only the N13a recurring-carrier output and N13b family;
  architecture guardrails passed;
- the inherited HTTP-redaction failure remains disclosed and unchanged from the clean base; it was
  neither fixed nor excluded from an otherwise failing target suite.

Pattern closeout: P05/P10 keep authority and semantic adequacy fail-closed; P27 prevents a parallel
catalog/overlay owner; P29/P32 require behavioral content-bound proof; P31 closes the guard classes,
not individual carrier strings; and P33/P34 preserve adversarial variation and honest isolation.
