# External sharp-RD numerical oracle

This isolated development profile pins rdrobust 2.1.0 and all resolved transitive
artifacts in its own uv.lock. The selected universal wheel SHA-256 is
8179f8f75445876297317a9805b81cbbf2e1e39bf804a460a8c23d0d7fa33263.
Development/oracle use is authorized by the E02 F continuation task. The package
is never a PolicyOS runtime dependency; its GPL product distribution decision
remains with the product/license owner. No upstream implementation source is
read or copied. Native code independently implements the published CCT 2014
sharp-RD formulas (Appendix A.1/A.2, Theorem A.1(V)).

Create a separate environment and run the selected non-skipping numerical gate
with the actual product interpreter and a distinct output path:

```sh
UV_PROJECT_ENVIRONMENT=/absolute/scratch/rdd-oracle uv sync --frozen \
  --project dev-oracles/rdd-cct --python 3.14
/absolute/scratch/rdd-oracle/bin/python dev-oracles/rdd-cct/compare.py \
  --product-python /absolute/product/.venv/bin/python \
  --replicates 2000 --output /absolute/scratch/rdd-comparison.json
```

The real reference import/fit is mandatory, never importorskip. The product child
uses candidate `src:.`, invokes the actual canonical method on its native NumPy
backend and checks settings and row bytes. The coordinator independently invokes
rdrobust on identical rows/options. It compares tau.us/tau.bc, se.us/se.rb and
the Robust CI row for 36 order/kernel/h:b/level variants plus 2,000 independent
null and 2,000 nonzero-effect DGP draws. Both targets use the predeclared fixed
HC0 profile. Each empirical coverage must lie in [.925,.975] and its two-sided
99% Clopper–Pearson binomial interval must contain .95. These Monte Carlo bounds
describe sampling uncertainty of measured synthetic coverage; they do not
validate a real-data design.

`--removal` deletes correction and variance adaptation inside the actual product
child while retaining successful status, profile/parameter fields and markers.
Its same direct numerical oracle and both repeated-coverage targets must FAIL.
Complete product and independent
reference numeric outputs, environments, streams, command/source identity and
exits are retained next to the deciding summary. No thread/process/CPU quota is
set by this profile. The shared PolicyOS environment is read-only.
