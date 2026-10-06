## [0.0.0-q1-review] - 2026-10-06

### Changed
- `scientist-search`: Search spaces refuse finite bounds whose affine span is not representable, and logarithmic endpoints execute exactly within declared bounds. Multi-objective and neural candidates now carry normalized coordinates of the actual typed action. Neural prediction and acquisition values are evaluated at that executed action; the multi-objective converter explicitly marks its scalar prediction unavailable and its existing acquisition value as belonging to the relaxed proposal. The existing training and acquisition algorithms are preserved.
- `scientist-search`: Single-objective GP checkpoints use gp_state_version=3 with the fitted and full-refit raw corpus, ordered observation identities, fitted transforms/model bytes, complete persisted warm-row content, numerical target, refit counters, backend identity and local RNG. Incomplete older GP checkpoints are refused. Warm history requires an explicit configured synthetic target or the numeric_transfer_basis.v1 CAS admission reader; restore repeats admission. Same-basis continuation uses conditioning without a silent MLL refit; due schedules and changed corpus identities refit. Acquisition uses the versioned sobol_ranked_restarts.v1 policy with locally seeded scored restart pools and qEI sampler, changing restart selection while preserving ambient Torch RNG. RL checkpoints now bind a supported linear_decay.v1 schedule and nested strategy state; incomplete old wrapper states are refused. These are technical continuation properties, not source authorization, production deployment or optimization-quality claims.
- `scientist-search`: Multi-objective search admits only complete finite declared objective vectors with matching ordered directions before frontier, hypervolume and GP training. Missing coordinates are no longer imputed as zero. Rejected original rows retain their index, identity and reason in mo_objective_admission.v1 input coverage; suggestions carry that assessment. Training uses canonical executed coordinates. Existing ModelListGP and EHVI algorithms are preserved; the assessment does not establish an independent production source denominator.
- `scientist-search`: Pareto schema 2 artifacts preserve finite front membership when the existing derived hypervolume overflows: the indicator is null with a versioned unavailable assessment, never a fabricated zero. Registry readers accept only supported snapshot schemas 1.0 and 2.0; catalog unions mark hypervolume unassessed instead of copying a single loop's value. Historical finite schema reads remain supported. These technical indicators do not establish an independent source eligibility denominator; the A-owned publisher/export dependency remains explicit and unapplied.

### Fixed
- `scientist-search`: Refuse boolean and unrepresentable scalar fiscal aliases and history measurements before numerical comparison instead of treating them as measured zero or raising an uncaught overflow.
- `scientist-search`: Bind native search points to attainable executed actions and validate strategy state types before replay.

## Compatibility Notes
- Unrepresentable affine spans are refused at construction. Suggestions report executed normalized coordinates; neural predictions use that point, MO scalar predictions remain unavailable.
- Declared primary/null/zero/alias/conflict/sign semantics and existing numeric text remain supported; boolean measurements are unavailable.
- Incomplete older GP/RL checkpoints are refused. GP profile3 and sobol_ranked_restarts.v1 explicitly change continuation/restart behavior.
- Incomplete, nonfinite, duplicate or direction-mismatched declared MO coordinates are excluded with explicit original-input coverage instead of imputed0.
- Supported schema2 indicators can be null only with typed unavailable assessment. Registry snapshot profiles other than1.0/2.0 are refused; historical finite reads remain supported.
- New state artifacts use strategy_state.v2. Structurally valid legacy envelopes remain readable, while malformed versions, booleans used as integers, nonfinite state and incompatible space fingerprints are refused.

## Change Classes
- execution-contract
- execution-contract
- runtime-state-format
- execution-contract
- artifact-schema
- runtime-state-format

## Migration Notes
- Consumers needing relaxed proposals use metadata.relaxed_proposal; check explicit acquisition/prediction basis.
- Provide finite measured scalar values. Existing objective and evaluation invalid-outcome status propagates to the caller; no fabricated scalar substitute is added.
- Create a fresh search for unsupported state/policy/basis/backend fingerprints; configure synthetic target or canonical CAS admission reader. Restore and every tagged numerical training use repeat admission.
- Read objective_admission metadata or last_objective_admission before interpreting an admitted subset as complete input coverage.
- Readers must preserve hypervolume assessments and handle null without substituting0. The A export companion is proposed and unapplied.
- The attainable_projection.v1 space identity changes checkpoint compatibility; start a new search when an older space fingerprint differs.

## Known Limitations
- Bounded duplicate retries do not guarantee a new action in an exhausted finite space; complete MO/neural checkpoint replay is unestablished.
- This technical numeric intake does not define fiscal units or verify institutional economic source truth.
- Conditional technical continuation is not production source authorization, deployment or quality advantage.
- This technical admission does not establish an independent production source denominator, authority or optimization quality.
- Independent A source eligibility/unknown denominator and served assessment propagation remain explicit failing dependencies; no exact higher-dimensional indicator convention is added.
- These changes do not establish deployment invocation, transfer source authority, or optimization quality.
