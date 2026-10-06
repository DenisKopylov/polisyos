# Isolated DoWhy 0.14 computation profile

The application remains Python 3.14. This standalone Linux Python 3.12 profile runs
real DoWhy identification/linear ATE estimation and explicit GCM mechanism fitting.
It imports no PolicyOS module, reads no CAS, writes no artifacts, and asserts no
scientific or governance authority. The enclosing existing Scientist MethodJob
owns scheduling, source resolution, persistence and execution evidence.

Install the complete separate environment with
`uv sync --project workers/dowhy-014 --python 3.12 --frozen`. The committed
`uv.lock` pins every selected distribution and download artifact. The actual
DoWhy 0.14 wheel SHA-256 is
`9c5855d80601e0feb2d0d232c19e7b660db4cd0ea04ace2ebaefcdb3599ab9db`.
Its installed metadata makes EconML an **optional `econml` extra**, rather than
a required dependency. This profile does not select that extra and proves no
EconML capability. The application baseline's DoWhy/EconML Python markers remain
unchanged. The profile lock also contains Windows-only colorama/tzdata; the parent
requires the complete remaining installed Linux distribution inventory.

Configure the server-owned absolute `POLISYOS_DOWHY_WORKER_PYTHON` path to this
environment's Python executable. `_dowhy_worker.worker_execution_context` resolves
the actual typed source through the parent's CAS around the existing `run_job`.
`run_worker` requires the actual complete method input to equal the decoded source
contract, preserving column order, aligned whole rows and the graph. The launch is
one fixed script under Python isolation with a 60-second deadline and 8-MiB JSON
request/response limit. Missing context/profile or a rejected response provides no
backend witness. It does not fall back to a local substitute estimator.

`protocol.py` owns strict `polisyos.dowhy.request.v1` and `.response.v1` JSON.
Bindings cover actual source bytes/ref, complete numeric matrix and columns, common
source-derived row IDs, graph, seed, operation parameters and request hash. Duplicate
fields, nonfinite JSON, unknown operations/fields and binding mismatches are refused.
The parent observes worker source/lock hashes independently. A response is a candidate
computation; neither its labels nor its hashes admit real causal assumptions.

`linear_ate` supports only the explicitly declared DOT graph, identified adjustment
set, binary contrast 0/1, ATE target and `backdoor.linear_regression` at 95%. It invokes
the real `CausalModel`, identifies with `proceed_when_unidentifiable=False`, estimates
with `method_params={"confidence_level": 0.95}`, verifies the actual estimator level,
and asks that estimator explicitly for 95% intervals. Only finite ordered scalar
shapes `(2,)` and `(1,2)` are accepted. Missing intervals retain a non-gate-eligible
point; malformed intervals are refused. No interval is flattened, selected, repaired
or synthesized. Mediation, other estimators/targets/contrasts and effect modifiers
require separate scientific profiles. `legacy-inprocess` remains explicitly named
for existing internal tests and is not this supported backend path.

`gcm_fit` constructs a real DoWhy SCM, explicitly assigns `EmpiricalDistribution`
to roots and linear `AdditiveNoiseModel` to children, then calls actual `gcm.fit`.
It exports fitted coefficients/intercepts and complete observed/root and fitted
residual arrays in common row order. Every requested IID whole-row bootstrap sample
gets a new model, assignments and genuine fit; at most 500 replicates fit within the
same message/deadline bounds. The parent owns SCM serialization, inference semantics
and downstream uncertainty classification. There is no automatic mechanism selection
or polynomial backend claim in this profile.

Run the non-skipping backend tests with `.venv/bin/python -m pytest tests -q -s`.
The linear oracle independently fits Statsmodels OLS with `alpha=.05`, and the
coverage test draws 200 independent correctly specified IID homoscedastic Gaussian
synthetic samples. The GCM oracle checks coefficients, fitted residual rows and
actual installed fit-function execution for the base and each refit. These synthetic
properties establish this bounded implementation; they do not establish graph
correctness, no unmeasured confounding, positivity, Gaussian errors or scientific
authority on admitted real data. The fresh Python 3.14 CAS reader test lives in the
mirrored application test directory.
