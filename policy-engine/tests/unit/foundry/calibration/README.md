# Foundry Calibration Unit Tests

- Owner: team-foundry
- Purpose: unit tests for Foundry calibration algorithms, score normalization, and calibration artifact contracts.
- Allowed contents: deterministic calibration tests, small fixtures, golden expectations, and calibration-specific helper modules.
- Local verification: `uv run pytest tests/unit/foundry/calibration -q`
- Maintenance: update tests with calibration contract changes; stale golden data requires owner approval and a refresh note.

## Ordered-row and selected-input discriminators

`test_ordered_batch_calibration.py` runs the real Calibrator on noncumulative
100/300-income rows, checks configured epsilon/priority and weighted metrics,
exact stochastic scalar-row/key/permutation behavior, eager/JIT invalid-domain
status, original/effective priority/weight representation, typed source-dtype preservation,
integer-weight refusal,
optional sentinel-state refusal, parameter-dependent off-target invalid output,
and a real JIT-gradient/Hessian analytic quadratic. Cache identity tests are
additional controls, not derivative proof.

`test_pure_executor_semantics.py` retains the scalar schedule/dependency controls
and adds a typed partial age mask consumed by real IncomeTax across active and
inactive steps, plus complete supported structural admission variants and real
built-in/no-selector positives. The inactive witness observes numerical selector
reads separately from the actual state/key effects, with explicit effect barriers
before callback assertions. `test_hessian.py` keeps raw
negative/flat spectrum and fallback-cause evidence distinct from repaired output.

The real compile → execute → calibrate → selected full input → basis1.2 → report2.1
→ fresh consumer tests are in
`tests/unit/scientist/nodes/builtins/simulate/test_propagate_welfare.py`. They cover
coherent changed key/weight/basis digests, selected config/row metadata and edges,
row wrapper step, stale report input selection, actual model/loss/metric replay,
backend/PRNG-profile-unavailable limitations, actual absent selected views versus
malformed present bases, missing report basis, generic curvature withholding,
and an unrelated external mean/quantile/welfare-weight law. The same real selected
producer fixture reaches `CalibrationMetaEvaluator`; unselected/new altered metrics
are not scored. Its legacy scalar positive and a new limited-profile test are in
`tests/unit/scientist/methods/autotune/test_calibration_autotune.py`.

`test_identifiability_response_basis.py` retains genuine scalar response positives
and sends a real new batch report through the fresh response source and actual
`PropagateUncertaintyNode` refusal route, asserting no output artifact/index/CAS
write after admission. The genuine scalar node fixture also refuses an identical
report payload under a selected schema9.9 manifest. Public-writer refusal observes
both actual CAS publication methods instead of comparing payload-ID sets. Legacy report wire and unknown-version controls live in
`test_calibrator.py`. None of these source tests is a runtime receipt until run.

Float64 underflow/negative-zero witnesses run only in a pre-enabled measured x64
process; x64-off is an explicit skip for those witnesses, never PASS. A separate
zero-individual-weight positive and typed NumPy64 preservation/refusal case cover
the actual default profile. No test changes global x64. PRNG counterfactuals use
real restoring JAX context managers and include a key-sensitive stochastic oracle.


`test_selected_source_intake.py` is a generic matrix over the actual Core JSON
producer and freshly reopened selected bytes: absent refs/edges/profiles/views/blob,
access denial and non-default-view capability limits stay unavailable; duplicate
or conflicting selectors and present schema/content/integrity contradictions stay
mismatches. Only disposable test CAS data is damaged for the missing/corrupt blob
controls. The real same-report welfare/autotune matrix adds a profileless readable
basis, missing and duplicate basis edges, and conflicting selected input. The scalar
response node receives profileless and duplicate selected basis views too, retaining
its actual scalar positive and schema9.9 refusal. These are proposed runtime checks;
static parsing is not execution evidence.


The R5 matrix adds actual producer NPZ plus typed JSON through fresh welfare,
Core strict numeric-string rejection and JSON tuple adaptation, actual welfare and
response missing-report view/blob/absent-ref classification before evaluators,
and selected no-canon legacy basis display versus unavailable qualification.
Schema-derived numeric-only mutants cover the bounded actual contract set; genuine
string unions/Any and no-eligible/unsupported schema views are named exclusions or
SKIPs. Registry cases derive consumed members from Core's actual content contract.
Both same-report consumer results are collected before the first status assertion.
All are source test definitions until run; no generic strict-Python list/tuple test
substitutes for Core's JSON adaptation.


R6 adds a real scalar2.0 config falsifier to the existing native response fixture.
Its existing response positive is reused; one small real fitted-override execute
supplies welfare's source contract, without a second optimizer/Hessian. A coherent
config/basis/report selected reissue preserves report bytes while changing an int
config field to a numeric string. Both public-node observations precede the joint
mismatch assertion. The raw-channel control proves that a coercing DTO decoder is
not an alternative to the required-model API. Schema and typed-helper probes alone
do not substitute for this consumer test. Every runtime/removal remains UNRUN here.

R7 broadens that same raw-result property across media. The existing real producer
NPZ/welfare fixture collects valid bytes and exact selected metadata, then direct
and nested domain DTO and foreign-metadata results at the public raw reader. Its
named joint assertion is the deciding NPZ removal target; setup/other red is invalid.
Core native date/Decimal/bytes values retain their existing codec; changed raw values
are refused. No extra optimizer fixture or independent replay is introduced for
these NPZ cases. All runtime/removal outcomes remain UNRUN in the source packet.
