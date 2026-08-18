# Atlas health-metric instrumentation

DS6-C11 instruments the seven metrics defined by the Atlas master plan's
“Health Metrics” table. The instrument reports repository observations; it is
not a maturity, promotion, publication, runtime-authority, or `stable` gate.
There is deliberately no aggregate PASS and no cross-metric ranking.

## Metric population and current state

| Metric identity           | Current state                               | Complete owner or reason                                                                                                                                                                                              |
| ------------------------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `primitive_adoption`      | `unknown`                                   | 261/261 DS1 readiness rows are read, but neither the ledger nor its schema owns an exhaustive decision-bearing-render to DS4-primitive relation.                                                                      |
| `fail_closed_fidelity`    | `unknown`                                   | The same 261/261 rows are read, but no canonical classifier relates blocker, abstention, out-of-envelope, or stale-cached semantics to rendered states.                                                               |
| `audience_enforcement`    | `unknown`                                   | The current file contains six server-denial proxy tests; it explicitly defers the final audience mapping to DS5 and is neither the complete endpoint denominator nor a test-run receipt.                              |
| `surface_missing_closure` | known zero, 0/27                            | The closed canonical-source validator applies the complete cluster-map checks as a subordinate recomputation. The row is `observed_by_instrument/recomputed`; it is not a cited report or independent reconciliation. |
| `evidence_coverage`       | `incomparable`, 0/0                         | The complete DS2 adoption ledger has 233/233 rows and no `stable` row. A zero denominator has a null ratio and null ranking, never a vacuous pass.                                                                    |
| `machine_twin_parity`     | `missing`                                   | The 261/261 readiness rows include 193 MACHINE-audience rows and five `implemented` rows, but those labels do not create a shipped-surface/twin relation or a parity-test receipt.                                    |
| `honesty_comprehension`   | `protocol_seam_only`; observation `missing` | C12 supplies the two-task instrument and six-metric INT-R3 seam. Research content, observations, and all six thresholds remain `not_established`.                                                                     |

`unknown`, zero, `missing`, and `incomparable` are different typed variants:

- `unknown` means the canonical sources exist but a required metric predicate or
  denominator has not been established;
- zero is an observed numerator of zero over a positive, complete denominator;
- `missing` names an expected relation, artifact, or observation that does not
  exist;
- `incomparable` retains a null ratio and ranking when the denominator is zero
  or scopes cannot be compared.

## Production and persistence path

`apps/runtime-dashboard/scripts/measure_atlas_health.mjs` is the fixed producer.
It accepts no arguments and loads the typed owner. The owner invokes the fixed
`.venv/bin/python -I` canonical-source validator with a minimal environment.
That validator applies the complete DS1 and DS2 Draft 2020-12 schemas,
including format checks, unique arrays, additional-property rejection, local
`$ref` resolution, and the stable-evidence condition before it projects any
count. It also invokes the canonical cluster-map validator as a subordinate
recomputation. Every metric row is `observed_by_instrument`; its separately
bound predicate provenance is either `recomputed` or `not_established`.

The MJS/TypeScript report is explicitly `candidate_only`. It has no
authoritative use, including descriptive measurement. The Python admission
adapter independently reloads and validates the complete owners, recomputes
the exact seven row semantics, and rejects any basis, status, state, count,
source-ref, authority, or interpretation mismatch before CAS storage.

The public persistence operation is closed:

```json
{ "operation": "persist_atlas_health_metrics" }
```

It rejects caller-supplied report bytes, repository roots, producer scripts,
exit codes, bases, and all other fields. The Python adapter resolves Node from
a module-owned absolute allowlist, executes its real path, and gives it a
fixed minimal environment that does not inherit `PATH`, `NODE_OPTIONS`,
`NODE_PATH`, `PYTHON*`, `VITE*`, npm, or pnpm injection. It records the
executable, version, digest, allowed locator, script digest, environment
policy, terminal status, and stdout digest. It stores the exact candidate
stdout as `atlas_health_metric_report` under the instrument producer, then
stores one admitted `atlas_health_metric_snapshot` under the distinct
admission verifier. The adapter reruns the source validator through the same
fixed isolated Python/minimal-environment boundary. The snapshot binds that
validator's identity, implementation digest, Python and `jsonschema` versions,
JSON Schema dialect, executable and stdout digests, and environment policy. It
copies only the recomputed and matched measurements and its sole Core CAS input
is that candidate report with role `measurement_report`. Both artifacts reuse
C07's canonical Core
`ArtifactStore`, internal classification, 365-day CAS retention, and
manual-approval-only deletion convention. They do not use or widen a C07
evidence receipt or evidence kind.

Only the snapshot has `limited_descriptive_admission`; it still denies
maturity, design/policy/runtime authority, promotion, publication, and stable.
The stored capability label is `implemented_but_not_orchestrated`, with
`consumer_missing` and `surface_missing` explicit. C10 owns reconciliation and
the governed reference projection. Until that work lands, persistence does not
grant any stable-bar effect.

## Replay and acceptance

From `apps/runtime-dashboard`:

```bash
cd ../..
uv run --frozen --extra test python -I apps/runtime-dashboard/scripts/validate_atlas_health_sources.py --corruption-probes
cd apps/runtime-dashboard
node scripts/measure_atlas_health.mjs
corepack pnpm exec vitest run src/test/evidence/atlasHealthMetrics.test.ts --maxWorkers=2
```

The isolated-validator command is the **test-extra bootstrap prerequisite** for
C11 acceptance. It deliberately has no `--offline`; its dependency provisioning
is not an offline receipt. The validator's nine corruption probes must pass
before the seven-row report is admitted.

The report records the repository revision, dirty posture, measurement time,
per-owner SHA-256 source refs, and fixed producer identity/version. The
snapshot runs an actual revision comparator over every bound owner, schema,
validator, producer, and admission path. It resolves product-relative paths
through the Git worktree prefix before comparing bytes. It records
`revision_resolvable` only when every current byte equals its blob at the
recorded revision; dirty, modified, or untracked bindings degrade to
`source_hash_bound_only` with the exact non-revision paths (six of 17 checked
paths for the current dirty/untracked ten-path repair candidate: the typed
instrument, MJS producer, source validator, persistence adapter,
`pyproject.toml`, and `uv.lock`). C11 has no historical rerun or cross-snapshot
comparison consumer, so this comparator proves source resolvability only and
does not make the capability orchestrated.

Focused negative controls reject a changed seven-metric identity set, every
status/basis/state/count cross-mutation, collapse among the four state
variants, a cited-report reclassification, incomplete canonical-owner schema
instances, scope ranking, widened input, caller-PATH Node replacement,
`NODE_OPTIONS` preload, broken CAS integrity, broken report-to-snapshot
lineage, and a source binding absent from the recorded revision.
