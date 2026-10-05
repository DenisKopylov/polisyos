# Cloud B evidence and acceptance

Cloud B owns the 25 bundles and 60 findings assigned by
`execution-organization/bundle-owners.tsv` and `finding-owners.tsv`.
This directory records bounded runtime evidence and review. It does not change
the shared residual ledger or assert that all findings are closed.

The independent review checkpoint contains these exact executions:

| Property | Frozen implementation | Independent result |
| --- | --- | --- |
| Persisted budget intake and real filesystem/process publication | `53f57da31b6a15397d5dcd9c03d49dc70b8c6daf` | 94 PASS |
| Complete CAS archive publication | `9e8574b7c7afeec474e5a0e77c5142da4004d279` | 41 PASS |
| Checkpoint execution and locked publication/rollback | `d7c9122a60330ce30cee7720c90caf4d8fb07ade` | 28 PASS |
| Async cache publication and fresh consumer replay | `a33898206b4b7421fa06f3444d8d53fb5e1bd174` | 9 PASS |
| Complete connector acquisition deadline and cleanup ownership | `58b04116e25344835f482ef79c16ce87f2d0b771` | 9 PASS |
| Linux process supervisor, descendant reaping and bridge consumers | `ba79d141a3937541b3164db255ceda89883575ec` | 85 PASS, 22 fork warnings |
| Bound scoped CAS admission and exact cache consumers | `34b6c191cc617d89475bdb73c3b50bc0340e4b09` | 67 PASS |
| Queued timed sync-node cancellation before physical start | `4a68d5345ceca69a6148af082f59ae27372865de` | Independent five-case actual file witness: 5 PASS |
| Cold trace/checkpoint recovery and private cache admission | `515054e7427467bf6e72fcfa22cc809c7cfe2c19` | 14 native PASS; independent six-case CAS oracle PASS |

Commands, complete stdout and JUnit outputs are retained in
[coordination-evidence](coordination-evidence/), with hashes in
[evidence-index.json](coordination-evidence/evidence-index.json). The common
interpreter is Python 3.14.2 at
`/workspace/polisyos/policy-engine/.venv/bin/python`; each execution imports its
own checkout with `PYTHONPATH=src:.` from that checkout's `policy-engine` directory.
The bounded tests use isolated temporary filesystem roots, databases or process
fixtures. They do not require the full production dataset.

The exact EXE static invocation diagnostic also completed on
`a33898206b4b7421fa06f3444d8d53fb5e1bd174`: exit 0, no static regressions, partial
coverage, `runtime_invocation_established=false`. Its full stdout and wrapper
are committed; the 170,857,261-byte raw graph remains ignored and untransferred.
The raw hash and exact rerun command are retained. Static reachability does not
establish HTTP, factory, callback or deployed runtime invocation.

The initial architecture measurement on untouched base
`c40d4acae1ce58b597267255026d9356565828fd` returned exit 2 / UNRUN because generator
inputs were unavailable. Its complete log is retained. Later slice gate results
are recorded in their own receipts; none are automatically classified as
inherited failures.

The baseline index resolves all 189 B-routed cells: 180 reported PASS and nine
reported FAILED. All 15 transferred UTF-8 receipt hashes were independently
checked. These counts describe historical source observations. Raw baseline
archives were not transferred, and their reported outcomes do not establish
behavior of a new candidate. Exact cell/source/environment locators are in
[baseline-resolution.json](coordination-evidence/baseline-resolution.json).

G fetches the published slice heads and separate handoffs, reviews the evidence,
and owns the append-only `codex/e02-integration` branch and shared closeout ledger.
The separate B acceptance checkout is for combined B verification. A alone
changes `generation_cycle.py` and `run_lifecycle.py`; C alone changes
`streaming.py`. B supplies contracts, test inputs and negative cases through Git.

Downstream evidence is retained in [downstream](downstream/),
[llm-review](llm-review/), [b52-oracle](b52-oracle/) and
[b52-review](b52-review/). The cold-seed baseline and naive off-loop controls
remain property FAIL witnesses on exact `0f24d18`; the candidate source and
independent acceptance are separate exact `515054e` measurements. A successful
witness process exit does not convert an observed property failure into PASS.

RUN submit/shutdown lock-order fix `b439fe9` and CAS regular output-entry
admission `3b2bcc6` passed separate native and independent runtime checks. Four
occupied user done callbacks still falsify general physical worker availability;
that measured boundary remains held. Fetched G checkpoint
`46748d3d0815b48df1e0d5ed39ffcdff4e251435` adds a real NET-01 late-handle
admission counterexample when a connector suppresses cancellation. The owner
reproduced it on Linux and is widening the common admission boundary before the
final source freeze. No physical cleanup deadline is asserted.

Seven detached historical review/baseline worktrees lack saved precreation
admission: DUR four, adapters two, CAS one. Current identity checkpoints and
complete evidence bytes remain source-bound, while historical admission is
`not_established`; G needs a fresh admitted replay if that protocol criterion is
decisive. See [admission-qualifications](admission-qualifications/), the published
RUN custody companion and CAS workspace qualification.

[Metadata tools](verification-tools/) explicitly join all25 B bundles/all60 B
findings and prepare74 whole native files. [Independent metadata control](metadata-review/)
rejects a missing B37 row even while its declaration remains present. These
checks establish bookkeeping and input binding; final runtime execution and
formal finding closure remain separate. CAS01/03 advertisement warnings are
retained, and no earlier PASS is carried to the final union.
