# Independent review: EconML macOS arm64 MethodJob harness V4

## Verdict

**GO for the one root-owned V4 candidate retry after the serialized heavy slot
is available.** V4 repairs a concrete EconML 0.16.0 API mismatch in both the
worker and the same-input direct-reference path. I found the requested API
placement, candidate identity, and stale-V3 refusal changes coherent. The
MethodJob fit, direct comparison, CAS readback, and negative controls remain
**UNRUN** by this reviewer. This review does not establish calibration, causal
identification, external validity, or production support.

## Frozen inputs

The assigned checkout was `HEAD=7e9d0912e014252260c217396ba50465392ab69a`,
tree `e6c8f72be8f4e2279bbac46e0715643484ca6760`. The shared worktree had
unrelated concurrent edits; I did not modify source, tests, or Git state.

V4 candidate inputs read back:

| Input | SHA-256 |
| --- | --- |
| `LOCAL/raw/econml-worker-profile-prototype-macos-arm64-v4-20261010/method_job_harness.py` | `f59cda52d2178abc0eb3ef7d576ec186356aa0e2366a1cb47960baf94e166a6d` |
| `worker.py` | `39828653fe092413f140203a93854864b2c61fceca62fd54a6c5c478d7cc8855` |
| `protocol.py` | `8fac20b4d13dfeb4e53b9b1d5d8a58ffb2da060d22693bb61da0570fa1ddedc2` |
| `bridge.py` | `3d2aa2c2997117dfeebd5d712017b5a243f733b3ba5acbe4318ea9adecb9c5e8` |
| `uv.lock` | `5016a249a7dbe37ad22a3e0e15ab495b9e63a5a2d7c3f68cbcba04ad09fbfb0d` |
| `verification/receipt.json` | `00f313eceb956b665ba9abfca4fc15a14916a9e039605d40ca5d9a9385f38936` |
| `verification/installed-econml-api-probe.stdout.txt` | `da6ddc531e251d46d1d1498d844145a89bc455458683df6722a6df7c5073ec8f` |
| `verification/callsite-audit.stdout.txt` | `ffda3015d2b3b2e8cae787f15cdddc79f7617db49f850159ff29316d38663060` |
| `LOCAL/decisions/econml-macos-arm64-worker-prototype-v4-20261010.md` | `57fbb2025d7153fd3a2a7cbb3bb18b8165ebbce1ba1a3d59d8810e4b383abce8` |

The lock, profile Python version, and project configuration are unchanged from
the prior candidate. Product-path fingerprints for `dml.py`, `_common.py`,
`numpy_runner.py`, `scientist/compute/runner.py`, `core/artifacts/store.py`,
`causal/protocols.py`, and the selected HTE fixture were read back:
`dml.py` `5bc3d414227c426f2ab1df973196ffe6891905a70782d14a36cb3110f56f4885`,
`_common.py` `afe8b61f2d8bd9ff8b6c357ff8c42133603f2a1bc2b437e3546d681a5a1490ab`,
`numpy_runner.py` `a36c55d2996b178e2671fbd433e56f9e5d5cde327989907ad49f6fc59297c505`,
`scientist/compute/runner.py` `09549945f709bbd98701ddccaa4e88a3240a731c4e77c87c01f51343adb8a41d`,
`core/artifacts/store.py` `c224d3c2ff9ffda97f9c7e3fcf5c3adb25167df48d55ed547afc5e1d0e2e7d3e`,
`causal/protocols.py` `250497e0024481a5bdc4e0b941fb31e57eaeb841702164490874f3978a3134c1`,
and the HTE fixture `0abb23a8e056aa7d77601647c2834945bfce7b97c67d3d9bd3b31dd2d19f6127`.
They do not intersect the V4 candidate changes.

## API correction and behavioral boundary

The retained no-fit probe ran against the selected EconML 0.16.0 environment
(CPython 3.12.12, macOS 27.0.1, arm64). Its captured signature shows that
`LinearDML.__init__` has no `inference` parameter, while `LinearDML.fit` accepts
keyword-only `inference='auto'`. It also records the exact constructor
`TypeError`. This explains the preceding V3 MethodJob's `backend_fit_failed`
without treating that generic issue as a successful computation.

The V4 worker now constructs `LinearDML` with the same model choices, CV,
treatment setting, and seed, then calls `fit(..., inference="auto")`. The
separate direct-reference program makes the same change and still consumes the
captured request's Y/T/X/W arrays, configuration, and seed. The expected CATE,
ATE interval, and exact same-implementation output comparison are unchanged.
No scientific setting was added or retuned.

V4 binds the changed worker/protocol/bridge bytes to a new identity:

- Method FQN: `causal.hte.double_ml_worker_prototype@0.2.0`
- Profile ID: `econml-0.16.0-py312-macos-arm64-v4-prototype`
- Worker + protocol SHA-256: `85f4ef138921b012f99a16a611da547e30a135f19a5c27d1fb6b417c010222a8`
- Bridge SHA-256: `3d2aa2c2997117dfeebd5d712017b5a243f733b3ba5acbe4318ea9adecb9c5e8`
- Harness SHA-256: `f59cda52d2178abc0eb3ef7d576ec186356aa0e2366a1cb47960baf94e166a6d`

The stale controls target the concrete prior profile/FQN, prior worker+protocol
digest, prior fresh-reader profile, and prior harness digest. Their refusal
assertions are in the harness but have not run. The reader's profile mismatch
and harness mismatch checks are explicit runtime errors, so the controls do
not depend on Python `assert` being enabled.

The retained verification receipt records a source AST audit of both
`LinearDML` call sites, Ruff, and `py_compile` as successful. These are
author-run static checks, not independent execution evidence. The receipt
correctly leaves the V4 numerical fit unrun.

## Limits and P40 bucket

The direct-reference run is a same-library, same-input consistency check; it
cannot validate scientific accuracy or calibration. The isolated prototype
does not register a production method, grant authority, or expose a public
surface. A successful retry should remain labeled
`candidate_computation_only`; calibration and any substantive acceptance
criterion remain separately unestablished.

**P40: NEW_CLASS — third-party API call-boundary compatibility.** This differs
from V3's lexical-versus-resolved interpreter-path issue. The installed API
probe establishes the actual constructor/fit mismatch, and V4 moves the
unchanged option at both executable call sites while versioning the candidate
identity. No further instance-specific repair is indicated by this delta.

Relevant patterns are P07/P12 (reproducible worker handshake), P10/P14
(scientific adequacy and evidence independence), and P04/P05/P15 (honest
candidate status and authority). Capability remains
`candidate_computation_only`; production registration and public surfaces are
`surface_out_of_scope`. No G acceptance or formal closure follows.

## Review actions

Read-only actions: recomputed the listed V4 hashes, compared the V3→V4
candidate diff, read the installed no-fit API probe, inspected worker/reference
call arguments, profile/FQN bindings, and stale-identity controls, and checked
the cited product source hashes. No test, fit, estimator, install, source
write, or Git mutation was performed. Root's single V4 MethodJob retry remains
the required runtime check and should use a fresh CAS root with full output and
artifact references retained.
