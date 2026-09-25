# R7 — governed live acquisition egress

**Property.** A governed World Bank acquisition may issue only the request
authorized and recorded by its request journal. The served executor's
connection acquisition must not make an unrelated health-check GET before the
request observer is installed. Ordinary registry leases retain their active
health checks.

**Repair.** The existing journal owner issues an opaque, one-use lease bound in
an owner-held registry to the exact persisted request, journal bytes, attempt,
connector, and dataset. The pool consumes that binding before serving this
governed acquisition and suppresses its pre-observer active health probe.
The request observer still checks the actual connector, URL, and parameters
before transport. The route remains the live executor → Fabric orchestrator →
ingestion → connector registry → pool → World Bank connector; no second
transport owner is introduced. The independent v3 static review is
`/Users/deniskopylov/.codex/scratch/e02-r2-r7-candidate-20260925/R7_INDEPENDENT_REVIEW_V3_RECHECK.md@sha256:e9c3ab986466ac279baec6e56d830498725d5e6f8e2b34d726d61db2552c0891`.

**Observed behavior.** The JUnit identity is the complete `testcase` set in each
file; counts below include no skips. All receipts use the integration checkout,
the canonical read-only `production_data` link, and intercepted HTTP transport.

| Check | JUnit result | Receipt |
|---|---:|---|
| Base regression, before source repair: unrelated US GDP GET before authorized UKR GET | 1 failed / 1 | `/Users/deniskopylov/.codex/scratch/e02-r2-r7-tdd-20260925/red.junit.xml@sha256:d3c00d5dfc53be584a421f1f76a7cf43622c8903b08b35f9ba116ce4cbb2c1b8` |
| Entire live executor test file after repair | 47 passed / 47 | `/Users/deniskopylov/.codex/scratch/e02-r2-r7-tdd-20260925/live.junit.xml@sha256:8a92eba7b6ec210a74a359611660b9763a3a8fa62f4c973adc1411d13d2ba232` |
| Entire connector-registry and orchestrator files after repair | 92 passed / 92 | `/Users/deniskopylov/.codex/scratch/e02-r2-r7-tdd-20260925/fabric.junit.xml@sha256:03e1320466bd61726c354f26fe74164fcb053e49cfe8f96e6182a437853d767e` |
| Remove governed active-probe suppression, retain journal and request markers | 1 failed, 1 ordinary-control passed / 2 | `/Users/deniskopylov/.codex/scratch/e02-r2-r7-tdd-20260925/active-mutant.junit.xml@sha256:1fafb1233a5f63284b3a5f7b128231e94b9dcbb084b2fc22023aaf39a2cf51f9` |
| Remove exact transport-scope predicate, retain journal markers | 1 failed / 1; out-of-authority transport reached | `/Users/deniskopylov/.codex/scratch/e02-r2-r7-tdd-20260925/scope-mutant.junit.xml@sha256:5c43dc11e4746f51b0ae447d67e466e31b327e3d1c7ce2cfbc753288a898cc86` |
| Restore both properties: served, out-of-authority, and ordinary control | 3 passed / 3 | `/Users/deniskopylov/.codex/scratch/e02-r2-r7-tdd-20260925/restored.junit.xml@sha256:e6b8d6bccbf845c2095de458ac9b3275f8246134061190ca583aad3067e185be` |

`ruff check` across the six changed sources and three touched test files and
`git diff --check` both exited 0. The three edited test files have pre-edit
four-base whole-file records in `BASELINES.md`; fresh post-repair four-base
replay and final gates remain due.

**P37/P38.** The lease gate turns on the owner-held binding, the persisted
journal event and digest, and one-use state (`recomputed` or independently
reconciled); it does not accept fields copied from a caller's token. The earlier
predicate was `validate_on_acquire`, which triggered an active health request
before the observer: a healthy connection was measured, but the acquisition's
egress authority was violated. Mutating the served permit handoff reproduces
that divergence while leaving the authority markers intact.

**Bounded residual.** This repairs the current served `worldbank.wdi` path.
The complete built-in connector census in the review found 20 connectors:
19 are not admitted by this executor and the admitted WDI `connect()` itself
does not make a remote request. A future connector that performs network I/O
inside `connect()` would do so before the pool's health-validation point.
A trusted pre-handle egress boundary is the smallest missing capability for a
generic plugin claim. This remains open under R7; no generic egress closure is
claimed.
