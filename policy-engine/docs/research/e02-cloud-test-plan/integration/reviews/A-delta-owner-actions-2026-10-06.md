# A owner actions — bounded handoff

**Decision at G `9c989f7877bd25fea38416cbd10d4c8b2511d10e`:** accept only the bounded installed-compiler slice; hold acceptance of the remaining A queue. No finding closure is implied. Basis: A full-queue head `b5e1f973ed9bce3e8dbb53321fb386156ef5d01c` (base `198076863e143dea9f89f02734b13d50dae3eed5`), simulation handoff `b3a07fc23d9300805ce552f25631d6eedab98413`, and compiler replay-4 receipt for `577521c6651bba048d6bdfdc13f36a383c8146c6` / tree `1e8820533c48ec88355f2a2fccba486f279c2a4b`.

## Accepted bounded result

The compiler slice is a bounded GO: replay 4 passed the one installed-wheel selector (1 passed, 0 failed/errors/skips); the fresh wheel-origin probe ran outside the checkout, and the fixture resolver output was persisted and read back. The canonical test path Ruff check passed. G accepted the compiler slice and its 14 companions at `9c989f787`. This demonstrates the named compiler/facade path with `RecordingResolver`; it does not establish production source admission or close LA-045 / REQ-01. Keep the 270 unresolved statically computed targets and dynamic/external boundaries explicit; do not turn the bounded census into a universal-zero claim.

## Remaining work, in owner order

1. **A — rerun the affected simulation set on the post-fixture candidate.** The 106-case wave on `6f9e7b3d117be86e244810b57740fe8faaa12c29` reported SIM 91/91 pass and CYC-02 7/15 pass: 98/106 passed, 8 failed. The CYC-02 failures came from multi-step horizons against a static NCM fixture (including the recursive test without a numerical trajectory). The later `b5e1f97` fixture changes to one step, but this exact 106-case set was not rerun there. Therefore the post-fix result is **UNRUN**, not green and not an inherited product failure. Run the affected set at the exact frozen source, retain JUnit plus full stdout/stderr and environment, and keep the fixture correction only if the runtime property still refuses unsupported static/multi-step execution.

2. **A — finish the two A-owned FRC-01 bridge checks.** E owns the forecast producer; A owns the default-profile bridge/S10 consumer. One old red is a real reason-loss: when calibration is unbound and evidence has no `calibration_status`, `_s10_limitation_refs` returns no typed limitation although the builder says `limit`. Propagate the fail-closed reason (`s10://calibration/fail-closed/insufficient-history`) without upgrading candidate credibility. The other red used naked, unbound evidence as its positive fixture. Replace that fixture with resolved evidence carrying valid prediction/threshold bindings and valid temporal roles; keep invalid/unbound evidence refusing. Then rerun these two FRC-01 tests on the changed exact candidate and preserve the deciding output. Neither red was replayed at A's slice base, so neither is proven inherited.

3. **A + input owner — run the ordinary served POST/GET path only with authentic L6 inputs.** The earlier 19-test attempt had 13 pass and 6 fail, but failed while building the L6 profile: three required files were missing and available files disagreed with the nested manifest. App startup, POST, N5, and GET were never reached. Route acceptance is **UNRUN**. Supply the real read-only L6 profile with its valid manifest, then exercise the route and retain exact input identity and full output. Do not fabricate inputs or weaken the source/manifest gate. The final tracked N9 refusal test still lacks a deciding JUnit.

4. **A — preserve the bounded N5→CAS→fresh-N8 result, then close only the actual residual.** The independent cubic oracle (`x1*x2*x3 + u`) and adversarial controls passed in the 10-case `6f9e` consumer wave. Its `generation_cycle.py` and N8 test blobs match the `b5` blobs, so this is evidence for that bounded typed consumer on unchanged bytes. It is not ordinary HTTP GET, production causal truth, temporal authority, or broad B26 closure. Keep the earlier 9eb consumer-gap note qualified to its older source; do not carry it onto the matching later bytes. B05/N9 still needs a valid signed/currentness positive, not just refusal controls.

5. **A — fix or explicitly bound the numeric-output escape once.** The SIM controller rejects a boolean scalar, but `np.asarray([True, 1.0])` can coerce the original boolean before the dtype check; an array-mean path may then accept it as numeric. This is same-class deeper malformed-value admission (P40), not a reason for per-engine patches. Validate original array elements before coercion and pin mixed-boolean adversarial cases, or retain an explicit bounded limitation. The prior 9eb review saw the static counterexample; it was not an executed test.

6. **A — retain the remaining typed limitations.** B22 time/step binding is `not_established`: registered `dt=1` may return rows labelled `[0,2,4,6]`, and a one-point horizon can mix initial stock with a terminal scalar. Do not invent a `dt == step` law. B19 lacks source/owner/population/time-bound EvidenceStateRef; B20 lacks typed atom dependencies and sequential semantics; B21's uncertainty authority is too broad for a single replication and has no estimand-aware/QMC uncertainty producer; B26 remains bounded to the synthetic N8 consumer, with served bridge absent. Reopen only against the exact owner proposal and discriminator; do not treat limitations as findings closed.

## Declared edge map

Keep the four declared edges exact and reconcile actual consumers before claiming orchestration:

- CYC-01 → FRC-01
- EMP-01 → FRC-02
- CYC-02 → RES-03
- NET-01 → ING-02

For both FRC edges, E owns producer work and A owns its bridge/consumer. The A FRC-01 reason-propagation repair above does not itself complete either edge. Preserve canonical ownership; return cross-owner source changes to the canonical owner.

## Finding and evidence boundary

The A denominator remains 13 bundles, 34 primary finding rows, 34 unique IDs and 35 criterion references. The progress ledger says all 34 are not adjudicated and is an older proposal, not a closure record. Bounded N5/C-member/N8 evidence is useful, but the overall A queue remains **HOLD** pending the exact affected SIM rerun, A-owned FRC repair/check, and served route with valid L6 inputs. Missing raw 9eb deciding output remains unavailable; the reported 6f9 summary (91 SIM + 7 CYC-02 pass, 8 fail) is not raw-byte readback here. No broad A replay, production-data replay, or finding closure is requested by this note.

Sources: `R/1548-A-full-queue.md`; `R/1548-A-simulation.md`; `1548-Acompiler-checks/replay-4/{summary.md,run-result.json,wheel-source-reconciliation.json,compiler-report.json}`; `1548-Acompiler-checks/accepted-test-ruff.json`.

Local `R/1548-*` and `_build` references above are G-only navigation, not cloud dependencies. Read the committed owner receipts at the exact source/transport SHA; absent local bytes remain not_established. This owner-action record adds no product run or formal finding closure.
