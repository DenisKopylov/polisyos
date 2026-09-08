# Task S — PostgreSQL reservation proof and GY-DEF22 plan journal

Date: 2026-09-02
Branch: `codex/debt-s-pgproof-and-def22`
Entry base: `071cf3c5feab54e57f21f1f931984f4319852536`

This is the append-only execution record for the two strictly serialized Task S parts. Part A was
closed and committed before any Part B research began. `docs/plans/active/` is transcription-only
and was not edited. The read-only `production_data` link was neither consulted nor changed.

## Part A — `ds9-postgres-reservation-proof`

### Verification contract

The sole product question was whether the existing named real-PostgreSQL proof observes exactly
one winner under concurrent human-decision reservation. Repository implementation was explicitly
out of scope: the 2026-08-31 audit had already established that the harness is complete and that
the historical `DS9-PG-PROOF-NONRECEIPT` results were honest fail-closed provisioning failures.

The machine identity and invocation were read from `_REPRO_COMMAND` in
`tests/unit/runtime/http/test_runtime_postgres_linearizability.py`; the selected identity was:

```text
tests/unit/runtime/http/test_runtime_postgres_linearizability.py::test_human_decision_concurrent_reservation_has_one_postgres_winner
```

Pass required all of the following from one real PostgreSQL endpoint: selection count greater than
zero, zero skips, test exit `0`, and the test's independent invariant
`sorted(result.acquired for result in results) == [False, True]`. Any zero-winner or multi-winner
result was a stop-level product finding.

### Provisioning receipt

1. Initial `/usr/local/bin/docker info` reached the client and failed to reach the daemon, confirming
   the requested stopped starting state. Docker Desktop was started with `open -a Docker`; the first
   successful daemon receipt reported zero containers.
2. Dependencies were provisioned with the invocation's own extras:

   ```bash
   uv sync --frozen --extra test --extra runtime --extra multi-tenant
   ```

   Exit: `0`.
3. A disposable `postgres:16` container ran at the non-default host endpoint
   `127.0.0.1:55439`, database/user `polisyos_proof`. The pulled image digest was
   `sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94`.
   `pg_isready` reported `accepting connections`. A direct privilege probe created and dropped
   schema `debt_s_privilege_probe`; it printed `schema_create_drop=PASS`.

### Measured proof and frozen timeout

The cold proof was run with both strict environment variables, the exact three extras from
`_REPRO_COMMAND`, and only the registered selector:

```bash
POLISYOS_DS9_REQUIRE_PG=1 \
POLISYOS_TEST_PG_DSN='postgresql://polisyos_proof:<ephemeral-password>@127.0.0.1:55439/polisyos_proof' \
/usr/bin/time -p uv run --extra test --extra runtime --extra multi-tenant pytest -q -rs \
  tests/unit/runtime/http/test_runtime_postgres_linearizability.py::test_human_decision_concurrent_reservation_has_one_postgres_winner
```

Terminal receipt: exit `0`, one passing test marker, `real 77.82`, `user 36.59`, `sys 2.72`.
The required timeout therefore freezes at:

```text
max(60s, 2 × 77.82s) = 155.64s
```

The same child invocation was then run under a `subprocess.run(..., timeout=155.64)` ceiling with
verbose collection output. Its terminal receipt was:

```text
collecting ... collected 1 item
tests/unit/runtime/http/test_runtime_postgres_linearizability.py::test_human_decision_concurrent_reservation_has_one_postgres_winner PASSED [100%]
============================== 1 passed in 0.27s ===============================
frozen_timeout_seconds=155.64 child_exit=0
```

Thus `selected = 1 > 0`, `passed = 1`, and `skipped = 0`. Passing the test establishes exactly one
winner because the executed oracle requires the two acquired flags to be `[False, True]` after
sorting and requires the loser to carry `DS9-OVERLAPPING-REISSUE`.

### Teardown and pattern pass

The named container was stopped; because it was created with `--rm`, the subsequent
`docker ps -a --format ...` result was empty. `docker desktop stop` returned
`Stopping Docker Desktop`, and the final status probe reported that Docker Desktop was not running;
the backend/UI process census was empty. No container or Docker daemon was left running.

- `P29`: closure comes from the real concurrency path on real PostgreSQL, not from an authored
  packet or marker check.
- `P34`: no skip, failure, retry, or exclusion was relabelled green.
- `P41`: no red was inherited or excluded; both proof executions terminated green on the entry
  base with no source change.

No source, test, configuration, generated artifact, active plan, or production-data path changed in
Part A.

### Architect transcription prose — `ds9-postgres-reservation-proof`

> **TASK S 2026-09-02 — `blocked` -> `closed`; provisioning-only closure.** The repository harness was already complete. A disposable real `postgres:16` endpoint with create/drop-schema privilege was provisioned at non-default port `55439`, `POLISYOS_DS9_REQUIRE_PG=1` forced fail-closed behavior, and the row's own machine-checked identity selected exactly one test with zero skips. The concurrent reservation proof passed and its executed oracle observed exactly one winner (`[False, True]`) plus the typed losing result `DS9-OVERLAPPING-REISSUE`. Cold measured wall time was `77.82s`; the timeout is frozen at `max(60s, 2 × 77.82s) = 155.64s`, under which the replay again reported `collected 1 item`, `1 passed`, `0 skipped`, exit `0`. The six historical `DS9-PG-PROOF-NONRECEIPT` errors remain correctly classified as the strict harness refusing an absent DSN, never as a product defect. The disposable container was removed and Docker Desktop returned to stopped state.

## Part B — `GY-DEF22` research and ratification plan

### Scope and dependency receipt

Part B began only after the Part A commit was attached and the worktree was clean. Its scope was
research plus a detailed implementation plan; no GY source, test, owner registry, generated
artifact, active plan, runtime package, or production-data path was edited.

The declared research environment was provisioned with:

```bash
uv sync --frozen --extra test --extra runtime --extra research
```

Exit: `0`. The resolved installed metadata reports `torch==2.10.0`. This reproduces the historical
GY-DI1 posture at the dependency level without reading the read-only `production_data` link.

### Authoritative basis read

The following owner and acceptance sources were read before design:

- `docs/superpowers/specs/2026-08-20-gy-n12-epoch-chronology-closure-basis.md`, section I;
- `docs/plans/active/layer3-slices/GY-engine-subordination.md`, GY-DEF22 and its GY-DEF14
  two-close ruling;
- `docs/superpowers/plans/2026-08-20-gy-n12-epoch-chronology-implementation.md`, Cluster 1;
- `docs/reference/policy-design-case-failure-patterns.md`, especially P01/P02/P03/P05/P07/P10,
  P13/P27/P29/P32/P33/P37/P38/P41;
- the Foundry profile/evidence/authority modules and all three supplied N8/N10a/chronology tool
  seams; and
- the complete tracked literal-reference set for the N8 artifact at entry base
  `071cf3c5feab54e57f21f1f931984f4319852536`.

The plan quotes CB-I01, CB-I02, CB-I02A, CB-I03, and CB-I03A exactly rather than restating them.

### Measured current state

The tree contains more candidate machinery than the one-line register entry suggests, but the
registered capability state remains correct.

Commit `f2c202997` added the Foundry-owned strict profile/evidence/authority types, the three owner
TOMLs, the generic root/extras/marker lock-graph walk, environment-receipt reconciliation, the
preflight-only sync tool, and candidate-level tests. Merge `911657027` explicitly retained the
production refusal because the competent runtime-subtree cutoff and owner receipt store were not
established.

The landed pieces are not a GY-DEF22 capability chain:

- no persisted dependency discriminant is shared by N8, N10a, and chronology;
- N8 has no producer for such an artifact;
- N10a preserves the exact owner non-receipt but has no discriminant to report;
- chronology's candidate transition blocks before it can admit the candidate environment receipt;
- no end-to-end CB-I01–CB-I03A semantic suite exists under those acceptance identities; and
- no machine/audit surface exposes the absent discriminant or its authority limitation.

Existing tests for a novel profile, an in-closure substitution, a research-shaped mismatch, and an
out-of-closure difference are useful partial witnesses. They do not prove the producer -> artifact
-> N10a/chronology -> surface chain. The exact state is therefore still:

```text
producer_missing + artifact_missing + semantic_test_missing + surface_missing
```

The production authority remains more specifically blocked by four owner capabilities recorded as
`absent/unallocated`: `owner_enforced_runtime_subtree_cutoff`,
`owner_resolved_resolution_receipt_store`, `platform_toolchain_admission`, and
`production_data_trust_policy`.

One additional owner-data drift was measured. The profile registry's declared pyproject domain
digest is
`sha256:57498f29ef1e6b6bf8f7edf3fbe03573686b64d2c0d72077eac9edc3b3223efb`, while
the entry tree recomputes the current `pyproject.toml` as
`sha256:803cbfb79c7727807db1c98d07413e8ef2f1b2a08929bd99bc2f8e638ee5142d`.
The declared `uv.lock` digest still matches at
`sha256:d3ca8737e0ce78b1deade715174576cb5449b443d96180e7029d9999d0584572`.
The plan requires owner-tool regeneration and rebinding of the stale row; it does not teach a test
to accept the old digest.

The committed N8 v2 artifact is also still the legacy positive-shaped packet, whereas the current
public N8 builder produces only a typed `producer_missing` non-receipt. The plan does not use an
environment diagnostic to bless either shape or silently cross the blocked transition.

### Chosen close and target chain

The plan chooses GY-DEF14's legitimate second close: explicitly declare the ambient environment
block non-decisive by construction.

The decisive alternative would require promoting candidate observations through the four absent
Foundry authority capabilities. That would either launder a recomputed scan into authority (P37) or
build a new sovereign subsystem. Neither is the smallest honest GY-DEF22 repair.

The plan instead separates two results:

1. a generic dependency-environment diagnostic, which may pass or fail and names its first
   root/profile/distribution case; and
2. the existing N8/N10a/chronology governing result, which is invariant to the diagnostic.

For CB-I02 and CB-I02A, the diagnostic verification fails. That failure cannot decide N8 admission,
N10a stage-gap closure, chronology acceptance, publication, or promotion. The historical research
environment therefore becomes self-describing on the first run without becoming a new gate.

The one planned shared artifact is:

```text
architecture/policy_design_case/layer3_gy_n8_dependency_discriminant.json
```

Foundry catalog/discovery owns its strict schema and derivation; N8 produces it. It binds the exact
N8 artifact bytes and source freeze, the owner-resolved purpose/profile declaration, root, extras,
used markers, tracked pyproject/lock refs, complete selected distribution rows, distribution set,
rule version, and an explicit `ambient_non_decisive` authority boundary. It contains no machine
path, host identity, package allowlist, backend ignore, or production-data ref.

The discriminant is computed by factoring a dependency-only reducer out of the existing Foundry
lock-graph walk. The current authority path then composes production-manifest evidence after that
reducer exactly as before. A new digest domain prevents the dependency-only preimage from being
mislabelled as the existing production-manifest-bearing dependency closure.

N8, N10a, chronology replay, and the governed `value-gate` machine projection all verify the same
artifact content ref. The red-first suite maps one exact test to each of CB-I01, CB-I02, CB-I02A,
CB-I03, and CB-I03A, then adds P29/P33/P38 falsifiers.

The complete plan is:

```text
docs/superpowers/plans/2026-09-02-gy-def22-environment-discriminant.md
```

### Blast radius, collision, and data ruling

The authoritative entry-base literal census for
`architecture/policy_design_case/layer3_gy_value_gate_contract.json`, excluding planning/history
docs, returned 12 tracked paths: four committed JSON artifacts, two Runtime HTTP service files,
three tests, and three quality validators. The plan records all 12 paths and the exact `git grep`
command.

The planned mechanism is confined to the Foundry catalog owner, N8/N10a/chronology tools, transition
readback, generated-artifact registry, and Runtime HTTP governed projection, with targeted tests and
registered generated outputs. No required path is under `src/polisyos/runtime/quality/`; the GY-PR1a
collision stop is not triggered. A later finding that the governing result can only be made
invariant by changing that package is an explicit implementation stop.

No Part B command consulted `production_data`, and the plan's dependency-only acceptance path does
not require it. The link remains read-only and unchanged.

### Foundry adjudication ask

Foundry review is the final implementation step, not a substitute for implementation. The reviewer
would be asked to accept the exact source commit and evidence packet establishing:

1. Foundry retains purpose -> profile ownership and callers cannot select an identity;
2. the new preimage is dependency-only, machine-independent, and derived from complete owner data;
3. closure and first-case ordering are generic over registry/lock data;
4. N8 alone produces the registered companion and all three consumers verify the same bytes;
5. diagnostic status is structurally barred from every authority use; and
6. the positive environment-authority chain remains `producer_missing` with all four absent owner
   capabilities named.

Only an accepted review reference bound to the final source commit, artifact, semantic tests, and
authority boundary is a Foundry adjudication receipt.

### Pattern pass

- `P01/P02`: the plan closes the complete producer/artifact/bridge/consumer chain rather than
  counting the existing contract as capability.
- `P03`: the companion is registered and projected through the governed machine/audit surface.
- `P05/P15`: candidate environment evidence cannot become policy authority.
- `P07`: schema/rule/source-freeze and exact N8 byte bindings make replay explicit.
- `P10/P38`: the diagnostic names the true generic coordinate, while the gate no longer turns on
  that ambient proxy.
- `P13/P27`: the smallest close reuses the Foundry reducer and the existing ambient/governing split;
  no N10a-, chronology-, or Runtime-local profile list is created.
- `P29/P33`: property-removal and name/profile-variation falsifiers are mandatory.
- `P32/P37`: shaped records and repeat scans remain candidate evidence; the positive authority
  non-receipt is preserved.

Part B intentionally ran no implementation tests: the task stops at a committed plan. Document
verification and the final bound checker are recorded after the Part B commit boundary.

### Architect transcription prose — `GY-DEF22`

> **TASK S 2026-09-02 — research complete; implementation not started; standing remains `open` / `producer_missing` with `artifact_missing + semantic_test_missing + surface_missing`.** Entry-base readback found a substantial Cluster-1 candidate reducer already landed at the Foundry catalog/discovery boundary: strict profile/evidence contracts, generic root/extras/marker lock-graph resolution, environment-receipt reconciliation, and an honest production preflight refusal. It did not find the missing GY-DEF22 chain: no persisted discriminant produced by N8, no one-ref N10a/chronology bridge, no exact CB-I01–CB-I03A end-to-end suite, and no machine/audit surface. The registered profile row is also stale against the current tracked `pyproject.toml` (`sha256:57498f…` declared versus `sha256:803cbfb…` recomputed); `uv.lock` still matches. The ratification plan chooses GY-DEF14's explicit **ambient-non-decisive** close. Foundry will derive a dependency-only profile/root/distribution discriminant from owner purpose, source freeze, root/extras, used markers, and the complete selected lock closure; N8 will persist one content-bound companion at `architecture/policy_design_case/layer3_gy_n8_dependency_discriminant.json`; N10a, chronology replay, and the governed `value-gate` machine projection will verify those same bytes. The documented `research` environment (`torch==2.10.0`) and two data-generated in-closure substitutions must fail the generic diagnostic with the decisive coordinate first; an outside-closure difference and a novel admitted profile must verify without a package rule, machine pin, or code edit. Diagnostic status is structurally forbidden from deciding N8 admission, N10a closure, chronology acceptance, publication, or promotion. The separate authority-grade environment chain remains `producer_missing`: `owner_enforced_runtime_subtree_cutoff`, `owner_resolved_resolution_receipt_store`, `platform_toolchain_admission`, and `production_data_trust_policy` remain `absent/unallocated`. No `src/polisyos/runtime/quality/`, active-plan, or production-data path is in the planned mechanism. Foundry adjudication of the final owner/producer/artifact/consumer/test/surface packet is the last closure step, not the implementation itself. Plan: `docs/superpowers/plans/2026-09-02-gy-def22-environment-discriminant.md`.
