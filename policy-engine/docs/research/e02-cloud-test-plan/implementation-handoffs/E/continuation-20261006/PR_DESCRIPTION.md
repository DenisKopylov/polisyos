## Summary

Missing dependency information, invalid covariance directions and failed draws could produce misleading calibration or uncertainty results; standalone numeric checks also lacked content-bound producer/consumer readback. This E candidate admits the effective objective and joint law, preserves every draw/replay outcome and denominator, and persists typed reports/evidence through configured CAS consumers. It covers CAL, UQP/UQS, BKT, DDM, DOE, FRC and PCL: 22 bundles, 54 findings and 55 bundle links.

The source is frozen at `58e2d97965c0826c44843a78dcb2f8698d9950a3` (tree `ffd0d56892f8e515838af4c5b160cb9ac6d988ed`) from fresh main `198076863e143dea9f89f02734b13d50dae3eed5`. Later commits contain receipts/documentation only. **Integration HOLD: G code acceptance pending.**

- CAL uses JAX derivatives and NumPy curvature diagnostics, exact objective/cache identity, an actual scalar batch Calibrator caller and CalibrationReport v2 → CAS → welfare readback. Invalid curvature does not become covariance through clipping.
- UQP/UQS share pre-draw joint-law and backend-range admission, singular covariance and complete failed-support outcomes. The narrow bounded IID mean certificate freezes N after an independent pilot; Sobol uses complete independent scrambles and replica estimator errors.
- BKT preserves actual requested replay attempts, source/split/time roles and requested/eligible/observed counts; micro/macro, bootstrap statistic and SciPy inference remain distinct. DDM carries complete report/model/rule/time/invalidation sources through persisted gate consumers.
- DOE uses canonical SALib, complete Morris trajectories and ordered law/scale/seed receipts through the candidate consumer. PCL binds persisted pairs to recomputed reports. FRC admits configured ForecastOwner inputs and produces separate candidate/empirical receipts through one CAS for predictive calibration.

Full handoff: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/README.md` and `final-handoff.json`. The all-54 criterion table, exact local-G recipes, independent negative controls, complete outputs and cleanup candidates are committed alongside them.

## Change Categories

- [x] architecture
- [x] contract / schema
- [x] runtime behavior
- [x] docs

## Compatibility Classification

- [x] breaking

Strict admission now rejects previously accepted invalid/undeclared law, covariance, support, budget and report inputs; inferential/trust results are withheld when their required purpose or source authority is absent. Consumers must supply declared profiles/law and use typed content-bound report readback. B201/B202 remain held for four explicit IR semantic-owner decisions; v1.1 replay is preserved and new uncertainty wire semantics are not silently ratified.

## Labels and Ownership

- [x] Labels: `kind:runtime-behavior`, `kind:architecture`, `kind:contract-schema`, `kind:docs`, `compat:breaking`, `release:fix`.
- [x] Owned areas touched: E calibration, Foundry uncertainty, Scientist backtesting/DOE/simulation consumers, DDM and E02 handoff documentation.
- [ ] A/G/IR integration and semantic owner acceptance remains pending; this is a draft handoff.

## Rollout Ownership

- Migration owner: E mechanism owners; Scientist/Foundry input and orchestration owners for the remaining default consumer bridges.
- Review/integration owner: G. A owns generation-cycle/default gateway/HTTP/S10 served verification. The appointed IR semantic owner owns B201/B202 ratification.

## Category Checklists

- [x] Scoped happy/failure paths, independent analytic/backend oracles, present-but-fake/property-removal controls and old-proxy divergence are recorded.
- [x] Mechanism docs and release fragments describe strict admission and remaining consumer limitations.
- [ ] Architecture acceptance is blocked: 163 reported deep-import creep entries include 35 E-changed-path reports and 12 exact imports introduced since fresh base. E follow-up and G architecture assessment are required; no shared baseline/exception was widened.
- [ ] Generated schema/OpenAPI acceptance is blocked; owning A/G generation paths require follow-up. E did not regenerate shared runtime contracts.

## Validation

- Fresh base contains integration anchor `1ddcd7b3905e52c0d19db091823a64830139fa64`; exact create/resume admission JSONs and accepted prior-slice delta retained.
- `results/import_results.py --check` passed before evidence. Full tracked inventory/criteria/ledger and exact source cells were reconciled.
- One frozen numerical wave: **110 paths, 1125 unique cases = 1123 PASS / 2 FAIL / 0 ERROR / 0 SKIP**, six parallel uncapped processes. Native JAX CPU, SciPy 1.16.3 and SALib 1.5.2 were available; dtype/environment/source identities are retained.
- Both FAILs are current A-owned FRC01 generation-cycle consumer regressions: missing bound calibration time-role record and missing insufficient-history limitation. A must resolve the configured CAS and independently verify full scope/split/pairs/counts/threshold/time/purpose, including fresh served read.
- Ruff and format checks pass for all changed Python files at the frozen source.
- **Architecture, runtime API contract, production invocation, workspace verify and CI parity FAIL.** Static invocation reports eleven regressions but leaves dynamic/callback/DI edges unmeasured. Initial missing Chromium was repaired using the repository browser installer, then workspace/CI preflight was repeated on the same SHA; imports/schema/OpenAPI failures remain. Later fail-fast umbrella steps are **UNRUN**. P41 inherited-red attribution is **not_established**.
- Full stdout/XML and the complete 171 MB static invocation receipt (lossless gzip with raw/compressed hashes) are retained. Every common check records unchanged source/test identity.

## Finding Closure and Remaining Inputs

Ledger statuses remain **49 partial / 4 held / 1 closed**; final verdicts are **49 limited / 4 held / 1 closed**. B194/B197 remain historically held with separate bounded technical verdicts; B201/B202 await IR ratification; B198 remains closed regression. Thirty-three bounded criterion recommendations require owner adjudication and do not automatically change the ledger.

Default served evaluators, source-law authority, native successful K forecasting/seed binding and some persisted default consumer bridges remain unestablished. Exact typed inputs/API sequences and read-only local-G recipes are committed. Production history/source-law data stay local, and synthetic backend fixtures do not establish production evidence. Forecast purpose remains predictive; causal/treatment/policy authority is denied.

## Rollback / Mitigation

Keep this as a draft E topic for G review. Resolve current architecture/generation/A-consumer gates and owner inputs before integration acceptance. No main or integration publication, history rewrite, shared baseline waiver or production-data transfer occurred. Native cloud Trash is unavailable; exact repeatable cleanup candidates are listed and no permanent deletion occurred.

## Release Notes Fragment

- [x] Each implementation slice includes its release fragment under `policy-engine/release-fragments/unreleased/`.
