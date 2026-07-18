# GY-N13b Acquisition Executor Journal

Canonical plan: `docs/superpowers/plans/2026-07-17-gy-n13b-acquisition-executor.md`.

Status: `stopped_by_evidence` on 2026-07-18. This is an execution ledger and stop-law report, not a
GY-N13b closure receipt. No world-growth epoch exists.

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

## Implemented foundations before the stop

Status: `implemented_and_focused_verified`, but not a completed capability claim.

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

## Stop-law result

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
