# EconML macOS arm64 MethodJob prototype — V4 API correction

V4 is an isolated experimental candidate profile, not a production backend or a
causal-identification, calibration, external-validity, governance, or publication
claim. A numerical MethodJob fit has **not** been run for V4. The root owns the
single fit attempt after review.

## API correction

The V3 MethodJob reached the worker but returned the generic `backend_fit_failed`
issue before producing a fit. In the frozen EconML 0.16.0 worker environment,
`inspect.signature(LinearDML)` has no `inference` constructor parameter, while
`inspect.signature(LinearDML.fit)` has keyword-only `inference='auto'`. The
retained V4 no-fit probe records the exact `TypeError` from the former call.

V4 preserves the existing `inference="auto"` choice and passes it to
`LinearDML.fit` in both the worker and the same-input direct-reference harness.
No estimator, data, seed, CV, confidence, or output requirements changed. The
worker/protocol code digest and bridge digest are recomputed for this candidate;
the selected lock is unchanged.

## Candidate identity and limits

V4 uses method FQN
`causal.hte.double_ml_worker_prototype@0.2.0` and profile ID
`econml-0.16.0-py312-macos-arm64-v4-prototype`. V3's profile, FQN, source files,
and failure receipt remain intact. Requests bearing the V3 profile are rejected;
selecting V3's old code digest against the V4 worker is rejected by the profile
asset check. The V4 harness also retains CAS content/schema checks, a fresh
reader, same-data/config/seed direct comparison, and negative controls. Those
checks are runnable but remain UNRUN until root authorizes the one fit.

The worker uses the provisioned CPython 3.12.12 / macOS 27.0.1 / arm64 profile
and the existing frozen lock. This is candidate computation only; any downstream
scientific calibration or acceptance criterion remains separately held.

## Root-owned run command

After review, run from the product root with the frozen V4 harness SHA in place
of `<HARNESS_SHA256>` and a fresh local CAS directory. The current harness SHA
is `f59cda52d2178abc0eb3ef7d576ec186356aa0e2366a1cb47960baf94e166a6d`:

```sh
PYTHONPATH=src .venv/bin/python \
  docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/econml-worker-profile-prototype-macos-arm64-v4-20261010/method_job_harness.py \
  /absolute/path/to/local/cas \
  f59cda52d2178abc0eb3ef7d576ec186356aa0e2366a1cb47960baf94e166a6d
```
