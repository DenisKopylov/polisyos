# Sharp regression-discontinuity inference

Owner: `polisyos.foundry.methods.catalog.causal.rdd.RegressionDiscontinuity`.
Registered method: `causal.inference.regression_discontinuity@1.0.0`.

The default `bias_correction=False` remains the separate conventional local
polynomial profile. It preserves its weighted-residual homoskedastic covariance
and supports polynomial orders 1 and 2. Omitted bandwidth uses the existing
heuristic IK-like rule; it is not the Imbens–Kalyanaraman selector. The near-cutoff
count-ratio diagnostic is not a validated McCrary density estimator.

An explicit `bias_correction=True` selects the native clean-room CCT robust
bias-corrected profile. It requires finite positive `bandwidth=h` and
`bias_bandwidth=b`; both are fixed symmetrically across the cutoff. No bandwidth
selection is performed. Supported settings are sharp assignment `X >= cutoff`,
`p=polynomial_order` in {1,2}, `q=bias_polynomial_order=p+1`, `kernel` triangular,
uniform or epanechnikov, `vce="hc0"`, `masspoints="off"`,
`bandwidth_selector="fixed"`, and `confidence_level` strictly between 0 and 1.
Omitted q means p+1. Clustering, automatic selectors, other VCEs and mass-point
adjustment are refused. The first profile also requires distinct running-variable
values, enough weighted support in both windows and full-rank local designs.
Fuzzy RD is unavailable because the typed input has no treatment/compliance
vector. Its requested design returns a typed point-free limitation.

For each side, let a denote the intercept weights of the p-order regression at
h, and d the (p+1)-coefficient weights of the q-order regression at b. The
leading-bias coefficient L comes from the p-fit moment of x^(p+1), with the
corresponding h/b scaling. The corrected weights are a−L d. Their square against
the q-fit HC0 residual variance includes both the variance of the estimated bias
and its covariance with the initial estimate. This implements the sharp-RD
specialization of [CCT 2014](https://doi.org/10.3982/ECTA11757), Appendix A.1–A.2,
Theorem A.1(V); it does not relabel a quadratic regression or conventional SE.
Only vector weights and small polynomial Gram matrices are formed.

The report's `point_estimate` is tau_bc, `standard_error` is se.rb, and its
confidence interval uses that robust SE and the requested normal quantile. The
conventional tau.us and its HC0 se.us are retained separately in `method_params`,
along with bias, p/q, h/b, kernel, VCE, cutoff, assignment, level, support counts
and a SHA-256 recomputed from admitted row order/outcome/running-variable/cutoff
bytes. The native producer is `PolicyOS clean-room CCT2014 weights`; no rdrobust
package is imported by product code.

`dev-oracles/rdd-cct/` contains a separate development-only locked rdrobust 2.1.0
reference. Its direct callable compares the actual native method fields and
fixed options on identical generated rows, including curved heteroskedastic DGP
and repeated-sample coverage. It is not a runtime extra or a distributed product
dependency. Its GPL distribution decision remains separate; no GPL source was
read or copied into the implementation.

The scientific claim is a sharp, iid, asymptotic local-polynomial procedure under
continuity, valid bandwidth and no-manipulation assumptions. Known synthetic DGP
coverage validates the declared implementation under that DGP. It does not
establish these assumptions, causal authority or interval coverage on admitted
real data. Registered dispatcher, report/CAS fresh-reader and actual Scientist
consumer checks retain their own source SHA and outcomes; a field/flag or a
successful registration is not their substitute.
