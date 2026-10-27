# C18 bounded sharp-RDD corrected-profile author receipt

Task token: `e02-c18-20261027-r1`. This is a bounded author result, not independent review, G acceptance, or formal closure. `closure_ids=[]`.

## Admission and source

- Actual cwd: `/workspace/polisyos/policy-engine` (repository root `/workspace/polisyos`).
- Attached branch: `work`; source status was clean at admission.
- Base commit: `8db01b1076e425b7998b05a658776c991b7bd594`.
- Base tree: `1706923ebe943f1a332dca4860cd145ddd366e36`.
- These match the supplied commit/tree; no switch, reset, rebase, or force operation was performed.
- Runtime model/service identity: **not established** by the runtime, so none is inferred.
- No production/private data, database, RAW store, or credentials were used. Tests use synthetic arrays and pytest temporary CAS only.

## Environment and measured budget

Python 3.14.4, NumPy 2.3.5, SciPy 1.16.3, pytest 9.0.2; `rdrobust` is absent and is neither used nor required. Host measurements were 32 GiB total / 28 GiB free disk, 17 GiB total / 16 GiB available RAM, and 3 logical CPUs. NumPy reports OpenBLAS 0.3.30 (maximum 64 threads); deciding runs explicitly set `OPENBLAS_NUM_THREADS=1`. The measured 400-rep pilot took 0.345 s after import (23 s command wall including environment/import startup), so the deciding narrow run retained one numeric thread and a 30 s initial yield budget. Exact environment output is in `outputs/environment.txt`.

An exploratory design-tuning pilot used RNG seed `20261027` and is **not** the deciding coverage run. Before executing the unseen deciding coverage seed, the committed test fixed 400 replications and acceptance `[0.915, 0.985]`, an outward rounding of the three-binomial-standard-error interval about 0.95 (`0.95 ± 3 sqrt(0.95*0.05/400)`). The deciding coverage seed is separately fixed as `2026102701`.

## Bounded design and independent oracle

The fixed design has 400 continuous, unique forcing values: 200 evenly spaced on each of `[-0.995,-0.005]` and `[0.005,0.995]`. The known conditional mean is

`1 + 0.3 x + 1.5 x^2` on the left and `1 + 0.3 x + 2 + 5 x^2` on the right,

so the known jump is 2 and curvature is nonzero and distinct on both sides. Independent normal errors have nonconstant SD `0.15 + 0.25 |x| + 0.10 I[x>=0]`. The bounded profile is sharp design, triangular kernel, `p=1`, `q=2`, fixed `h=0.45`, fixed `b=0.70` (`h/b=9/14`), HC0, mass-points off, 95% two-sided normal intervals, and no bandwidth selector. Point/oracle seed is `20261027`; coverage seed is `2026102701`.

The oracle independently fits the h-window local linear and b-window local quadratic regressions with square-root-weighted `numpy.linalg.lstsq`. For derivative order zero it evaluates

`T(y) = alpha_0(y) - L gamma_2(y)`, where `L = alpha_0((x/h)^2) (h/b)^2`.

It then obtains every element of the corrected linear functional by evaluating `T(e_i)-T(0)` under unit outcome perturbations. With residuals from the independently fitted q polynomial, the one-side HC0 variance is `sum_i [s_i residual_q,i]^2`; left and right variances add for the discontinuity. Thus the expected point, variance contribution, and covariance contribution are not obtained from the product helper. Formula correspondence was checked against Calonico, Cattaneo & Titiunik (2014), Appendix A.1/A.2 and Theorem A.1(V), DOI `10.3982/ECTA11757`; this test covers only the declared p/q/fixed-bandwidth/HC0 specialization.

## Results

The deciding combined run had 43 passed cases and no failures, errors, skips, or filtered fits (JUnit: `tests=43 failures=0 errors=0 skipped=0`). Key outputs:

- **PASS positive/oracle:** oracle and runtime corrected point `2.050513341916`; oracle and runtime robust SE `0.084945874489`. Conventional point `1.952510668425`, establishing a nonzero correction.
- **PASS bridge:** the oracle-checked profile traversed registered dispatcher → persisted filesystem CAS report → fresh typed report reader and retained point, robust SE, profile, and method parameters.
- **PASS coverage:** seed `2026102701`; 380 covered / 400 accepted / 0 failed fits = `0.950000`, inside predeclared `[0.915,0.985]`. This is evidence only for this finite synthetic design and profile, not a universal guarantee or empirical identification claim.
- **PASS executed point removal:** correction was removed while the corrected profile marker remained. Mutant point `1.952510668425` disagreed with independent oracle `2.050513341916`; the discriminator raised as required.
- **PASS executed variance/covariance removal:** corrected variance was replaced with conventional variance while the profile marker remained. Mutant SE `0.068886401533` disagreed with independent oracle `0.084945874489`; the discriminator raised as required.
- **PASS adversarial:** negative/zero h or b, invalid orders, Gaussian kernel, fuzzy-without-treatment design, and automatic selector returned typed non-success; row permutation preserved point/SE but changed row-order binding; a same-shape changed outcome changed input binding. Existing companion cases also cover confidence levels, sparse support/mass points, changed cutoff, and conventional supported modes.
- **SKIP external comparator:** none. `rdrobust` is absent; it was not made mandatory. The independently derived perturbation/WLS oracle is the comparator.
- **UNRUN broad research extras:** intentionally not run because the supplied task documents the unavailable `arch==8.0.0` tunnel failure and directs a narrow supported dependency profile.
- **WARNING lint:** `.venv/bin/python -m ruff ...` was attempted but Ruff is absent from this environment (`No module named ruff`). No dependency lock was loosened.

## Commands and retained material

- `OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q -s tests/unit/foundry/methods/catalog/causal/test_rdd_rbc.py tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_c18_oracle.py --junitxml=.../outputs/combined.junit.xml`
- `.venv/bin/python -m ruff check tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_c18_oracle.py src/polisyos/foundry/methods/catalog/causal/README.md`

Material A retained bytes: `outputs/combined.txt`, `outputs/combined.junit.xml`, `outputs/environment.txt`, and `outputs/ruff.txt`. The earlier focused run is retained as `outputs/oracle.txt` and `outputs/oracle.junit.xml`; it is duplicate diagnostic history, not deciding evidence. SHA-256 values are recorded in `SHA256SUMS`. Material B is the exact command above plus committed test inputs. No category-D nonreproducible deciding output exists.

## Limits and pattern closeout

P14 is addressed by calling this an author result and keeping the independent mathematical oracle distinct from product runtime, not inflating an author run into independent review. P29 is addressed by executable tests that recompute from live runtime and by executed remove-the-property/keep-the-marker mutants for both point correction and corrected covariance. The README now describes the actual bounded support and refuses extrapolation. Historical closures, B198, and separate B211 remain unchanged; no G acceptance or formal B210 closure is asserted.

Post-receipt lint fallback: `uv run --offline --frozen ruff check tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_c18_oracle.py` was also **ERROR/UNRUN** because the locked `psutil==7.2.1` wheel was not cached and offline network use was disabled. `py_compile` and `git diff --check` passed.
