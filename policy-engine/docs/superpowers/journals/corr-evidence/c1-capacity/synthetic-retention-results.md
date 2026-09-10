# Synthetic retention diagnostic — executed in its declared finite scope

Both serial profiles completed with RC0 and no cap reached. They used the
same frozen source and v2 declaration
`2026-09-09-synthetic-retention-declaration-v2.json@d24655fbfb56317a4c00ca5323fd8201692e0a32`,
whose content hash is
`sha256:c794e4957d37cb73de88696a8c42ae6cca90246086827055c7b1cc1c8b484dfe`.
The first declaration remains an unexecuted pre-run checkpoint; v2 binds the
whitespace correction made before either profile. No frame or outcome-based
selection changed. The mechanism is
`synthetic_retention.py@d24655fbfb56317a4c00ca5323fd8201692e0a32`; the finite
execution projection also binds the unchanged real campaign, SDK, estimator,
telemetry and analysis owners. Source comparison passed at intake and finish.

| Complete declared frame | 100 | 1000 |
|---|---:|---:|
| Completed typed synthetic works | 100 | 1000 |
| Constructed SDK HTTP attempts | 300 | 3000 |
| Native worker wall seconds | 11.166474 | 91.372820 |
| Raw telemetry samples | 44 | 354 |
| Ambiguous initial checkpoint samples | 4 | 4 |
| Sampled peak summed RSS, bytes | 325386240 | 327319552 |
| Peak fraction of observed physical RAM | 1.893997% | 1.905251% |
| Observed native disk writes, bytes | 33923072 | 366669824 |
| Final logical stored file bytes | 2636684 | 25216691 |
| Final allocated file bytes (`st_blocks`) | 5812224 | 56836096 |

The complete work/attempt identities are reconciled against both database and
filesystem memberships inside each worker. The entire telemetry stream is
independently reconciled through Python and SQLite typed values, with every
ambiguous sample retained. Stored size independently reconciles `pathlib`
and `os.walk/lstat` identity/value sets, including WAL, SHM and lock entries.
Allocated file bytes are not exclusive APFS extents; native write I/O is not
space consumed. The hardware observation is eight logical CPUs and 16 GiB
physical RAM. Worker/descendant metrics exclude the observer process, and
unobserved short-lived descendants retain the native observer's stated limit.

| Active work-progress window | 100 | 1000 |
|---|---:|---:|
| First observed completion count | 1 | 3 |
| First observed RSS, bytes | 324173824 | 325107712 |
| Last observed completion count before full completion | 98 | 998 |
| Last observed RSS, bytes | 325353472 | 327073792 |
| Qualified samples | 34 | 334 |
| RSS OLS, bytes per completion | 14706.014 | 2034.707 |
| RSS OLS, bytes per second | 167138.900 | 23501.561 |
| CPU share of observed logical capacity | 12.412878% | 12.412208% |

This window begins after the first observed durable completion and ends
before the full-frame completion count. Missing count bins were unsampled,
never zero. The analyses separately show the real campaign return window,
including its mandatory replay, and shutdown through process exit. Including
the zero-RSS exit observation produces a negative slope in both runs; that
negative slope is not evidence of steady working memory.

The 1000-input peak exceeds the 100-input peak by 1933312 bytes, while the
work-progress slopes remain positive. This is a finite observation on a
constructed response vocabulary. It does not identify allocator warm-up
versus retained state and does not prove an asymptotic memory bound, provider
week-long behavior, calibration, correctness, or live throughput. The
declared frame-reconciliation SQLite is bounded to 1000 ordinals and runs
before first work completion. Graph finalization has its own native profile.

The deciding run captures are `synthetic-retention-100-profile-run.json` and
`synthetic-retention-1000-profile-run.json`. The compact interpretations are
`synthetic-retention-{100,1000}-interpretation.json`; their original complete
analysis commands remain `synthetic-retention-{100,1000}-analysis-run.json`.
Only the three complete `completion_bins` arrays are omitted from each
interpretation. Every original first/last/terminal bin, slope, count and
limitation is preserved. `synthetic-retention-analysis-compaction.json`
records byte-identical relocation of the full derived analyses with their
hashes. The append-only `synthetic-retention-derived-location-correction.json`
places their current recomputation copies at
`.tmp/corr-c1-capacity/retention-derived/full-analysis-{100,1000}.json`, outside
the measured data roots; it supersedes only the first scratch location in
the compact interpretations. Those derived views are local scratch, not
work storage; the complete raw source trace is retained once. No native run
or source change occurred during compaction. Exact primary native traces
and both emitted summaries are retained in
`synthetic-retention-{100,1000}-primary/`; the archive manifests recompute byte
identity and own synthetic marking. Generated synthetic source/results stay
in scratch; their construction is pinned by the declaration. Mock attempt
clock details are outside the native memory proof.

The five sourcefreeze tests and independent AST/unittest identity census are
recorded in `synthetic-retention-sourcefreeze-{green,census}.json`; Ruff is
`synthetic-retention-sourcefreeze-ruff.json`. The decisive source-finish and
duplicate-observation-body cases first returned red, then passed after the
owner comparisons were added. Removing the real source comparison,
observation identity equality, or work-progress window produces RC1 in
`synthetic-retention-finish-source-removal.json`,
`synthetic-retention-observation-identity-removal.json`, and
`synthetic-retention-warm-window-removal.json`. The declaration/output markers
remain present during those probes.

No incidental mechanism finding remains from this diagnostic. Remaining
provider error origin, unmeasured higher concurrency, live long-duration
memory and changed-retry cost questions stay with C1's already declared
measurement limits. This result grants no canonical GY-PR1 or GY-S3 closure.
