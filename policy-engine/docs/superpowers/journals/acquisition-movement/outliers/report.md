# Stage 1: numeric VOI and education provenance

Research only, at `28b8a1a420e746b54fbd0b87f73fad1fc4821ba5` on
`codex/acquisition-movement`. No source, test, configuration, register, or ledger
repair is proposed as already authorized by this report. The two rows require
different deciding variables and should leave the common movement implementation
denominator.

## O1 — Numeric VOI is an input/valuation prerequisite, not hidden projection

The exact register row is `ds15-numeric-voi-metric-residual-granularity`,
`docs/plans/active/DEBT-REGISTER.md:566`. Its `blocked` verdict waits for a
content-bound decision/ranking artifact and expected-value and expected-cost inputs.
Its owner cell is `producer_missing`, rather than an appointed team. The cited
Task E finding is the subsection of that exact ID at
`docs/superpowers/journals/2026-08-30-debt-e-acquisition-n13b.md:1147`; the
original complete input census is at `:932`.

**Counterexample tested:** a real metric-level decision and its primitive inputs
already exist, but a consumer simply fails to project them. Case-insensitive
owner/call and expected-value/cost/VOI searches located existing numerical owners;
therefore a repository-wide claim that there is no numeric VOI producer would be
false. The deciding distinction is whether those owners have the selected metric
residual's substantive inputs and authority.

The current owner expresses the distinction directly:

- `tools/quality/validation/layer3_gy_n13a_acquisition_census.py:1428` defines
  `GrowthBacklogRow` with literal `ranking_only_not_voi` and
  `metric_residual_granularity_not_supported` (`:1439–1442`).
- `derive_growth_backlog` at `:3281` derives only confidence times route demand;
  its input is `ReverseDemandResidual`, not an acquisition decision. The source
  explicitly names the missing claim/requirement contract and optional VOI report
  at `:3286`. Changing binding confidence can change the interim rank while the
  VOI refusal stays true. This is the intended different quantity, not a cached
  numeric result the frontend could reveal.
- `src/polisyos/runtime/quality/acquisition_planner.py:1653` accepts typed
  `AcquisitionGap`s and an optional `voi_report`; `_ranked_voi_by_gap` at `:4346`
  expects a decision identity, a strategy and a gap binding, plus expected value
  and cost. `plan_requirement_gap_acquisition` at `:1700` is the existing bridge.
- Numerical machinery exists: `_plan_one_required_distribution` at `:1781`
  computes a research score from authority gain times decision value (`:1813`),
  then constructs a VOI report (`:1843`). The fallback bases are `0.48` and `0.62`
  at `:3246` and `:3271`, and the generic fallback cost is declared at `:3190`.
  These supplied/default quantities do not establish a metric's empirical value
  of information, population, horizon, measure, or authorized decision basis.
- The stricter current cost owner `produce_acquisition_cost_basis_record` at
  `:2993` returns `None` when the exact schedule has no row (`:3018`). A complete
  AST/JSON comparison of the one shipped schedule and one canonical census finds
  **two schedule rows versus fifteen backlog rows, with an empty exact and
  case-insensitive key intersection**. `cost_schedule_comparison.py` reproduces
  the comparison; `raw/cost-schedule-probe-output.txt` retains its full output.
  It is source evidence, explicitly not a runtime execution receipt.
- The surface at
  `src/polisyos/runtime/http/services/acquisition_surface_projection.py:66`
  forwards those owner fields. Its production consumer is
  `governed_projections._project_acquisition_growth` at
  `src/polisyos/runtime/http/services/governed_projections.py:2336`; the
  governed-projection route is at
  `src/polisyos/runtime/http/routes/governed_projections.py:213`. The projection's
  allowed scope is acquisition audit history/gap shape, and it explicitly denies
  current action authority and execution (`governed_projections.py:1061`).

The other source callers found by the complete AST walk do not alter that
distinction: the producer pipeline consumes compiled requirement specs and a
supplied `voi_report` (`src/polisyos/runtime/quality/producer_pipeline.py:2214`);
the substrate-acquisition owner labels its values as fixture acquisition and
supplies `0.91`/`0.15`
(`src/polisyos/runtime/quality/design_axes/substrate_acquisition.py:461`). These
are concrete counterexamples to broad numeric-producer absence, but are not
content-bound valuation inputs for the selected census residuals.

**Disposition:** split into a metric-to-decision valuation prerequisite lane,
upstream of acquisition movement. Keep the row's per-residual `producer_missing`
and absent persisted input artifacts explicit. The generic planner and generic
Scientist `VOIDecisionRecord`/`VOIRunReport`
(`src/polisyos/scientist/methods/search/voi_models.py:37`, `:81`) are reusable
components, not proof of an admitted metric valuation chain. No `surface_missing`
finding is established. A positive metric valuation requires the decision
subject/granularity and substantive owner-backed value/cost inputs. Typed empty
input slots, provenance and reachable refusal remain buildable without an
appointment; a metric-specific calculation must not substitute default research
numbers for the unanswered decision.

**Buildable chain, with the metric-specific choice kept explicit:** retain each residual's upstream demand
identity → derive the actual claim/requirement gap → bind the value/cost and owner
decision through the existing VOI report → call the existing requirement-gap
planner → persist its report → consume its action/limitation through the existing
surface. The existing owner command is
`python -m tools.quality.validation.check_layer3_gy_n13a_acquisition_census --check`;
the worker registration is at
`src/polisyos/runtime/http/services/governed_projection_validation_worker.py:80`.
This report does not claim that hypothetical metric bridge is wired.

## O2 — Education waits on provenance measurement, independently of acquisition

The exact row is
`education-importer-provenance-neither-inherited-nor-excluded`,
`docs/plans/active/DEBT-REGISTER.md:518`. It appoints the existing education
cycle-substrate / GY-S0 capture owner. The decisive Phase-5 finding is
`docs/superpowers/journals/2026-09-08-gy-phase5-completion.md:352`, with its
non-exclusion statement at `:371–379`.

**Counterexample tested:** the same error code at a convenient later base is
mistaken for proof that the Phase-5 lane inherited the failure. The original
slice base is **`3d572c146f9d021cb6daad64ebb7b093121ed124`**, not this acquisition
lane's `28b8a1a42` and not a later Phase-5 cluster entry. The retained
`gy-phase5-evidence/s3/education-pair-slice-base.json` contains the exact base,
named branch, inner pytest command, RC1 and both failing node identities.
`baseline_pair.py:24` asserts that immutable base before invoking the command.

The failure occurs before either lever assertion: the tests' real helper at
`tests/unit/runtime/quality/test_intervention_substrate.py:473` loads the frozen
pack and calls its current-owner projection (`:495`). The production gate at
`tools/quality/validation/check_layer3_gy_second_domain_pack.py:5441` rederives
the current S0 registry and compares the complete registry payload at `:5491`.
The observed refusal is `cycle_substrate_registry_owner_rederive_mismatch`.
The same gate is consumed by non-test `validate_bundle_payloads` (`:707`) and
the frozen cycle-trace path (`_build_cycle_trace`, `:2803`), with runnable
terminus `python -m tools.quality.validation.check_layer3_gy_second_domain_pack --check`.

The retained source-closure probe itself settles why the row cannot close:
`gy-phase5-evidence/s3/registry_owner_gate.py:33` reports
`input_closure_status=not_established`. Its empty observed Python-call intersection
does **not** enumerate native DuckDB, Rust validation, subprocess Git, or all
transitive definition inputs. These named unresolved boundaries remain undecided.
The retained `education-registry-identity-delta.json` compares the full frozen and
current registry identity sets and shows the L5 epoch source identity change; it
is evidence of the mismatch, not a replacement for a complete P41 intersection.

**Disposition:** separate GY-S0/education provenance lane; missing capability is
`verification_missing` for the historical input-denominator attribution. No new
acquisition producer, external appointment, or signer can close this row. It
must remain neither inherited nor excluded until the correct exact-base replay
and a complete relevant input intersection are established. The current-gate
failure's historical owner is **not_established**, while the owner of the next
measurement is already named by the row.

**Architect decision:** explicitly place that bounded provenance measurement
with the named education capture owner, outside acquisition movement. Its next
work is to reconstruct the Phase-5 slice's actual deciding source/data/Git/native
inputs at both pinned runs, reconcile the complete set independently, then
attribute the failure. The result can be an inherited failure, a slice-owned
change, or a named undecided boundary; repeat RC1 alone is not the decision.

## Measurement boundaries and incidental destinations

`census.py` walked all **5,704 tracked `.py` files** under `src/`, `tools/`, and `tests/`,
reconciles that set with a separate `git ls-tree` walk, retains every successful
read/content identity and parse/read failure, and enumerates direct/attribute
calls including imported aliases. It also parses the complete canonical
N13a JSON row set and independently reconciles it with the reverse-residual IDs.
Both set differences were empty; no selected file was unreadable or failed AST
parsing. In the complete one-JSON / fifteen-backlog-row denominator, all fifteen
retain the typed VOI refusal and zero interim score; decision/ranking keys and
expected-value/cost keys occur zero times, including case-insensitive forms.
Those key zeros are bounded structural facts, interpreted only with the producer
and caller source reads above; they are not proof that all possible valuation
artifacts everywhere are absent.
Its `raw/census.json` is the receipt, not a repository-wide semantic absence
certificate. Dynamic dispatch, non-Python producers, external stores, unselected
authority documents, and unsupported/unreadable inputs remain named undecided
boundaries.

Current attempts at the exact education pair and three existing numeric semantic
tests were bounded using earlier station expectations. Current concurrency made
those bounds invalid: the education harness stopped at 150.08 seconds and the
numeric harness at 120 seconds before any test result. They are **UNRUN_TIMEOUT**,
not passing tests, product failures, or inherited failures. Receipts:
`raw/education-current.json`, `raw/numeric-semantic-tests-nonreceipt.json`.
Destination: this lane's harness only; no product debt row. Earlier navigation
attempts with oversized one-line JSON output or a nonexistent guessed service
file are likewise non-evidence, never absence verdicts. The full retained
education receipt identities and commands are bound in
`raw/retained-education-receipt-readback.json` without copying the historical dumps.

Pattern pass before closeout: P01/P02 prohibit graduating reusable numeric
components into a metric chain; P03 confirms the existing typed refusal is
actually surfaced; P05/P32/P37 prohibit treating supplied/default numbers as
authority; P35/P38 prohibit deciding input absence from missing names or a
truncated result; P07/P08 keep historical and current epoch semantics distinct;
P34/P41 prohibit inherited attribution from an incomplete denominator. No repair
round, register transition, or blanket capability closure is claimed.
