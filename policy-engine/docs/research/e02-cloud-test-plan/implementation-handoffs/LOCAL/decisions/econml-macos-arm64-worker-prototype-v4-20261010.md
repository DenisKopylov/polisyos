# V4 EconML macOS arm64 worker profile: API-placement repair

**Disposition:** `EXECUTED_CANDIDATE_COMPUTATION_ONLY; NOT_CAUSAL_ACCEPTANCE`. This is an isolated experimental candidate profile, not a product-source change and not evidence of causal calibration, identification, external validity, or production support.

## Deciding source evidence

The root-owned V3 MethodJob attempt is retained at
`LOCAL/raw/batched-blocking-focused-20261010/econml-mac-real-methodjob-cas-fresh-reader-prototype-v3/`.
It ended with `backend_fit_failed` before a successful estimator fit. Its MethodJob
boundary did not preserve the worker exception text, so that receipt alone does
not identify the API mismatch.

A no-fit probe in the already frozen Mac worker environment records the installed
EconML 0.16.0 signatures and actual constructor error at
`LOCAL/raw/econml-worker-profile-prototype-macos-arm64-v4-20261010/verification/installed-econml-api-probe.stdout.txt`.
`LinearDML.__init__` has no `inference` parameter; `LinearDML.fit` has
`inference='auto'`. Passing that keyword to the constructor raises:

```text
TypeError: LinearDML.__init__() got an unexpected keyword argument 'inference'
```

## V4 change and identity

V4 moves the already-selected `inference="auto"` argument from the constructor
to `.fit(...)` in both physical call sites: `worker.py::_fit` and the inline
same-input direct-reference program in `method_job_harness.py::_assert_direct_reference`.
The model family, model_y/model_t, CV folds, treatment encoding, seed, input
rows, 0.95 confidence level, interval method, and returned quantities are
unchanged. The source-level AST audit is retained under `verification/`; Python
compile and Ruff also pass.

Because worker/protocol bytes and bridge identity changed, V4 has its own
server-selected identity:

- Method FQN: `causal.hte.double_ml_worker_prototype@0.2.0`
- Profile ID: `econml-0.16.0-py312-macos-arm64-v4-prototype`
- Worker+protocol SHA-256: `85f4ef138921b012f99a16a611da547e30a135f19a5c27d1fb6b417c010222a8`
- Bridge SHA-256: `3d2aa2c2997117dfeebd5d712017b5a243f733b3ba5acbe4318ea9adecb9c5e8`
- Lock SHA-256 (unchanged): `5016a249a7dbe37ad22a3e0e15ab495b9e63a5a2d7c3f68cbcba04ad09fbfb0d`
- Harness SHA-256: `f59cda52d2178abc0eb3ef7d576ec186356aa0e2366a1cb47960baf94e166a6d`

The harness contains V3-profile/code/harness refusal controls, CAS content/schema
checks, a fresh reader, and a separate same-data/config/seed direct-fit comparison.
The root's independent source review preceded the single V4 MethodJob run recorded
below.

## Actual V4 MethodJob run

The root ran the selected harness once from the product root. The command record
and complete captured outputs remain at
`LOCAL/raw/batched-blocking-focused-20261010/econml-mac-real-methodjob-cas-fresh-reader-prototype-v4/`.
The command exited 0 in 27.455 seconds. Its `command.json` SHA-256 is
`b8bc85c2112a3c67e509c75a6c3abcdbe3670c1f67d7fd781f2b18867cca54c4`; stdout
SHA-256 is `f0db572c7f91dac982d392673fce26646e73bfc731dc90c52530468007062486`
(2,870 bytes), and stderr is empty (SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`). The
complete per-file output index is inside `command.json`; the canonical record
`LOCAL/econml-macos-arm64-worker-prototype.json` binds the source hashes, run,
CAS IDs, manifest hashes, and output hashes without copying the raw capture.

The actual path registered and dispatched the MethodJob through the declared
`numpy` backend, executed `econml.dml.LinearDML` in the isolated CPython 3.12.12,
macOS 27.0.1, arm64 worker, wrote source/adapter/result/evidence CAS artifacts,
and passed a fresh reader over the result with all 400 rows. The source was the
repository's controlled `_synthetic_hte_data(n=400, seed=42)` fixture, bound to
source artifact `sha256:b1d4e29a4dc5a77cb617572f087f497bfb50abae19f900f2b40e70e0f3c3b9dc`.
MethodJob ID is
`job:81d7cc9123fe6824a9f87e376a08471091e8d1662e4448c44769aeb3c32fa1fa`.

The result artifact is
`sha256:436675a2a5440340ee9ef0c058fdfe01c4fb8282e778db880778ba9f9be45303`
(manifest SHA-256 `563735986c2bd020eae495acf8af629f0615a8281824f32d158ccbd3c1fb2d5c`);
the evidence artifact is
`sha256:43cacb0bbf2a68939165b9d537de6d79949846afa7a3642dbede829e2b28d241`
(manifest SHA-256 `897107e96098dcafef2bdd2575e9712484e7635ff148acfcc38a567529906778`).
The source, adapter, and all artifact refs plus their manifest input edges are
listed in the canonical record. A second direct `LinearDML` fit in the worker
environment used the same serialized data, estimator configuration, and seed;
the harness asserted exact equality for ATE, all 400 CATE values, and the ATE
confidence interval.

All ten recorded controls refused as expected. The output intentionally contains
two separate `previous_profile_refused` entries: one tests the V3 profile on the
worker request, and the other tests the V3 profile on the fresh reader. The
remaining controls cover unselected profile, previous code digest, lock and
bridge substitution, malformed response, substituted result, row permutation,
and previous harness digest. The result reports ATE `-0.02827941536086603` and
95% interval `[-0.10944755413574433, 0.052888723414012268]`. The fixture DGP
CATE RMSE `0.05343729401821093` and known sample ATE `0.0014882616631714308`
are diagnostics only, not acceptance thresholds.

## Verification boundary

This run demonstrates the experimental worker execution and MethodJob → local
CAS → fresh-reader bridge for this fixture and selected profile. It does not
establish an accepted causal result, calibration, identification, external
validity, production backend support, or a public policy claim. The profile's
pre-run README and `verification/receipt.json` are retained unchanged as
historical source/provisioning records with their original `FIT_UNRUN` wording;
this post-run note and canonical record supersede only their run-status summary.
No packages were installed for the fit; it used the already provisioned frozen
25-distribution worker profile.
