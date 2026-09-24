# R2 deployment identity, historical replay, and N6 strangle map

Status: read-only design map for R2. This document records the producer,
owner, artifact, consumer, and verifier seams to use after the four-base
baseline and source-write lease. It is not implementation evidence.

The source inspection used `codex/e02-r2` at
`b4bcdc2539b25948c58b9e69757109cf33c34641`. The E02 artifact check used the
`codex/safe-workspace` tree at `00d946c2b7d052522be092f9c70eb9902f6521c2`.
No tests, native jobs, or source edits were run for this map.

## Property and split validity result

Keep the property that production N6 is the recursive generation-cycle
controller and does not route through `WorkspaceLoop.run_fixture`. Change its
proof from re-hashing every source file at run creation and every run read to
a source/deploy-time census bound to the confidence-ledger owner's canonical
deployment identity.

Keep historical validity separate from present authority. A serialized run is
historically valid when its own versioned projection, canonical bytes, and
content bindings replay. Currentness is a separate typed result:

| Historical replay | Currentness | Meaning |
|---|---|---|
| valid | current | Historical bytes replay and the owner confirms the same deployed identity and census |
| valid | stale | Historical bytes replay, but owner evidence identifies a changed deployment |
| valid | not_established | Historical bytes replay, but no current owner evidence is available |
| invalid | any | The artifact cannot be relied on, including as history |

`stale` and `not_established` cap authority; they do not erase historical
validity and do not refuse candidate-band computation. A caller-supplied
identity string, field shape, marker, or frozen DTO is not owner evidence.
N6 deployment identity also does not prove cycle-substrate context, WMR
custody, tenant custody, acquisition passport admission, or epoch admission;
those remain their own owner-resolved facts.

## Exact N9 pre-capture and admission order

The outer `GenerationCycleRun` is created after promotion. Therefore adding a
field only at run construction cannot protect N9. Use this ordering:

1. At the start of `GenerationCycleController.run`, ask the Confidence Ledger
   owner for an immutable, owner-issued capture of the currently admitted
   deployment identity and the release/deploy census binding. Do not take a
   hash or identity string supplied by the HTTP caller. If the owner cannot
   issue the capture, retain typed `not_established`; continue candidate work.
2. Keep that capture in the controller's private run context and pass the same
   object to the canonical N9 port. A caller-created projection cannot replace
   it.
3. N6 generates, grounds, simulates, and prepares the existing completed
   generation. The existing owner path creates the exact pre-N9 admitted
   candidate batch in `generation_cycle.py` and
   `epoch_validity_cascade.py`; do not weaken that batch.
4. The N9 port resolves the admitted batch and epoch evidence as it does now.
   Before invoking N9, it opens the exact `ConfidenceLedgerSession` and asks
   the owner for that session's admitted identity evidence. Compare this
   evidence with the N6 capture. Only an exact, owner-confirmed current match
   reaches N9. Missing evidence is candidate-limited; mismatch is stale and
   authority is refused.
5. After N9 returns, construct and persist the `GenerationCycleRun` with the
   v3 owner-evidence reference/projection and the source/deploy census
   reference. Persist the captured evidence, never a consumer-computed
   `current` label. Consumers resolve and recompute currentness through the
   owner again.
6. Every recursive, S8, public, and authority-bearing consumer runs the same
   currentness assessment before it emits authority. Historical deserialization
   and replay do not require a checkout or currentness assessment.

The current N9 order explains the seam: `GenerationCycleController.__init__`
constructs the N9 port (`generation_cycle.py:3499-3513`); the N6 promotion
path seals the existing batch (`generation_cycle.py:4020-4122`); the canonical
port resolves the batch and then opens the ledger session
(`promotion_sequence.py:3021-3081`); the outer run is only constructed later
(`generation_cycle.py:3799-3819`).

## Canonical identity owner and packaged boundary

The Confidence Ledger is the sole existing deployment-identity owner. Its
canonical baseline includes:

- `pyproject.toml` and `uv.lock`;
- all source paths derived from the authority import closure;
- the Python runtime/ABI manifest;
- the import-time authority closure and loaded-code manifest, checked against
  the actually loaded modules and code objects.

The owner implementation is `confidence_ledger.py`:

- `_deployment_baseline`: lines 4434-4452;
- exact path set (`pyproject.toml`, `uv.lock`, closure files): lines 4501-4509;
- `_deployment_identity_from_baseline`: lines 4382-4392;
- `_loaded_code_manifest`: lines 5282-5365;
- `_admit_loaded_runtime`: lines 4417-4431;
- `ConfidenceLedgerSession.from_repo`: lines 1211-1249.

The identity exists privately as `ConfidenceLedgerSession._deployment_identity`
and is included in ledger root/receipt records. The session exposes no public
deployment-identity evidence property: its public properties at lines
1285-1318 are `risk_scope`, `registry`, `is_authority_session`, and
`authority_provenance`. R2 must add a public owner-issued evidence/currentness
projection; consumers must not call the private helpers or reproduce their
hash.

The packaged-runtime boundary is real. `from_repo` requires the supplied root
to equal `_loaded_policy_engine_root()` (`confidence_ledger.py:1211-1224,
4370-4373`), and present deployment capture needs the root's lock/project and
closure files. There is no source-checkout-free shipped-manifest producer or
admission path. Historical v1/v2 replay remains available. For a package with
no checkout, currentness is `not_established` and protected N9/public authority
is refused, while ordinary candidate N6 proceeds. The missing package path is
`producer_missing` for owner-issued shipped identity evidence; do not claim
positive packaged authority until that producer is supplied by the owner.

## Versioned run serializer seam

In the inspected tree, `GENERATION_CYCLE_SCHEMA_VERSION` is
`policyos.runtime.generation_cycle_controller.v2`; `GenerationCycleRun`
accepts v1/v2 (`generation_cycle.py:155,1360-1384`). Its serializer has a
special historical projection for v1 only (`:1407-1417`), using
`_historical_supplied_field_tree` and dropping later source-custody fields.
`validate_generation_cycle_run` currently ties general validation to a live
`repo_root` (`:5873-5912`), conflating replay and currentness.

Adding the owner binding requires current schema v3 and version-dispatched
historical serializers:

- v1: preserve the existing supplied-field projection byte-for-byte;
- v2: freeze the actual historical v2 projection, excluding v3 owner/census
  fields and any later nested defaults;
- v3: serialize the current owner-evidence reference/projection and census
  binding.

For v1/v2, exact serialization must be compared with historical canonical
bytes, not just `model_validate` success. For v3, the embedded/ref'd evidence
must resolve through Confidence Ledger. Currentness belongs to a fresh owner
projection; a historical payload never self-declares itself current.

## R2 source/deploy census and P38

`StrangleReceipt` in `generation_cycle.py:1235-1270` expressly limits its
positive claim to a direct AST census of `src/polisyos` and declares build,
deployment, alias, and dynamic-call gaps. `_collect_strangle_source_census`
walks the full source denominator and hashes files (`:9330-9428`), but the
decisive predicate is narrower than the property:

- at `:9377-9380`, only calls whose AST callee is a plain name or attribute
  ending in `run_fixture` are recorded;
- `_call_name` at `:9437-9445` misses aliases such as
  `fixture = loop.run_fixture; fixture(...)` and dynamic dispatch;
- `_is_allowed_fixture_caller` at `:9445+` exempts every line in
  `runtime/quality/workspace/loop.py`, not just the intended fixture-only
  callsites. A production caller added to that file would stay green.

Those are P38 divergent cases. The full measured denominator at this audit
revision is 2,693 Python files under `policy-engine/src/polisyos`. The new
source/deploy gate should consume the full shipped source/build manifest,
derive the full set rather than sample it, bind its output to the canonical
identity evidence, and make unresolved alias/dynamic routes `not_established`.
Do not rescan all 2,693 files at every N6 run or persisted-run read. Run the
census as a tooling/release gate; N6 and its consumers resolve the owner-issued
result. The source/deploy gate needs a real served N6 witness as well as the
static census so it proves the production route, not just markers.

P37 labels:

- loaded deployment identity and same-session N9 comparison: `recomputed` by
  Confidence Ledger owner; caller-supplied or unresolved identity:
  `consumer_asserted` / `not_established`, never positive;
- deployment census membership and callers: `recomputed` from the full
  controlled source/deployment artifact; unresolved dispatch:
  `not_established`;
- historical validity: recomputed from versioned serializer and content bytes,
  independent of current source tree.

## Production caller and consumer map

Source census covered 2,693 production Python files. Exact
`validate_generation_cycle_run` calls are four sites in three files (plus the
definition):

| Path | Role |
|---|---|
| `runtime/quality/recursive_generation_cycle.py:907-928` | Validates each served recursive leaf before enclosing it |
| `runtime/quality/design_axes/value_choice_provenance.py:1048-1060` | Reloads and validates a persisted N6 run |
| `runtime/quality/public_export.py:149-160,216-226` | Gates public OWR and pre-N9 limitation projections |

`GenerationCycleRun.verify_strangle_receipt` at
`generation_cycle.py:1402-1405` is the only runtime delegation to
`StrangleReceipt.verify_current`; that consumer currently re-hashes the
complete source slice.

The compiled recursive-run reader census found three
`CompiledRecursiveGenerationCycleRun.model_validate` owners:

| Path | Role |
|---|---|
| `runtime/http/services/control/generation_cycle.py:280-323,413-446` | Persists/replays per-leaf normative source and recalculates S8 authority on egress |
| `runtime/http/services/control/evaluation_safety.py:651-670` | Reads served compiled source for promotion-safety evaluation |
| `runtime/quality/acquisition_route_loop.py:276-310` | Reads N6 leaves/cycles to close acquisition routing |

`runtime/http/services/control/run_lifecycle.py:3333-3354` persists the
compiled run, invokes the S8 projection, and projects leaf N9 refusal reasons.
The R2 owner currentness choke point must be used at all authority-bearing
consumers; acquisition routing remains candidate work and must carry an
unknown currentness limitation rather than being globally refused.

## Source/test write set after lease

Mechanism files:

1. `runtime/quality/confidence_ledger.py@c3775ce0a96966fcbc46fa243e5cc03f3a80c84b`:
   public owner-issued capture,
   validation, and current/stale/not-established projection; support packaged
   evidence only once a real owner-issued manifest producer exists.
2. `runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`:
   v3 run binding, v1/v2/v3 historical
   serializer dispatch, separated replay/currentness, and use of the
   precomputed source/deploy census.
3. `runtime/quality/promotion_sequence.py@dc8beab981b714e80e54bef22ba83bc66ab3ffd4`:
   compare the run-start owner capture
   with the exact ledger session before N9.
4. `runtime/quality/recursive_generation_cycle.py@ddff9abd228378166bce8437862ebe487ae00149`:
   validate historical bytes
   independently, preserve candidate N6 on unknown currentness, block authority
   unless current.
5. `runtime/http/services/control/generation_cycle.py@055cca6c9424deac61fa61543143a2a2d2310b1a`,
   `runtime/quality/public_export.py@4abfb2f28b32c422ecee45966b5fdd4218489b8d`, and
   `runtime/quality/design_axes/value_choice_provenance.py@83ec53fefe0cc036480bb3d164ebcb44225a6ed9`:
   route S8, public,
   and replay consumers through the owner projection.
6. `runtime/http/services/control/run_lifecycle.py@a3827ed1677df17f09827d479db7510ffdb70e6e`,
   `runtime/http/services/control/evaluation_safety.py@5e4aee53788d5b1b1fa3464f16090714934b1f93`, and
   `runtime/quality/acquisition_route_loop.py@8d2aecd29b71bfc43af45d4d8ff89f2683916d1a`:
   touch only where the complete
   caller review finds an authority decision taking currentness from a loaded
   compiled tree.
7. Use the existing GY generation-cycle tooling owner for the source/deploy
   census (`tools/quality/validation/check_layer3_gy_generation_cycle_contract.py`)
   or a narrowly owned companion. Do not add another runtime identity owner.

Focused test files:

- `tests/unit/runtime/quality/test_confidence_ledger.py@1537ea3e9984fd9599d4d95b3c9e95c040af6fbf` — owner-issued evidence
  and status transitions;
- `tests/unit/runtime/quality/test_generation_cycle.py@4f851cb207267a13877647ef82a2b73f3a24360a` and
  `tests/unit/remediation/test_cyc_05.py@9a9199993498fa60a72a786fcacc45d469324231` — byte-exact versions, no-checkout
  history, N6 candidate control, census removal probe;
- `tests/unit/runtime/quality/test_generation_source.py@dfbffbf32f90920a0b67310e4dd1d94b45e9308c` — historical v1/v2
  payload replay;
- `tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py@b675681a801cb9a66ec3ca80faf636fd91bc92d9`
  — recursive candidate versus N9 authority;
- `tests/unit/runtime/http/test_normative_generation_bridge.py@ef8ec18a438afe790a0b03f35f90b9e90d6288d4` — S8 production path;
- `tests/unit/runtime/quality/test_public_export.py@7fceafd3360cdf912136fcb171f07e8f6fd83fa5` and
  `tests/unit/runtime/http/test_public_export.py@6561502ffd1432605283c8cfc1f06baf44b9c33d` — current public projections;
- `tests/unit/runtime/http/test_control_service_di.py@4c100bb6d2c17cac8e3e61bee34519c338c075ec` — served NL front door;
- `tests/unit/runtime/quality/test_acquisition_route_loop.py@6bf0cffd0807dcd1fb51ff2541bd2e684ed41c8a` — candidate
  acquisition reader;
- `tests/integration/runtime_quality/test_evaluation_safety_promotion_bridge.py@ee88e300df544e58f886feafef7c193ab573e060`
  — served promotion-safety reader;
- `tests/repo_quality/tools/test_layer3_gy_generation_cycle_contract.py@6ff8b4691de6250900154aac5e64f3ac7898c605` —
  source/deploy gate’s behavioral mutation witness.

This is a proposed write set, not a claim that every listed consumer must
change. Reconfirm changed-file intersection against the broker's four-base
baseline before edits and record exact touched-file outcomes.

## Required behavioral probes

**Removal probe:** keep the existing receipt/schema markers, but mutate a
production N6 entry path so it reaches `WorkspaceLoop.run_fixture` through an
alias, or add a production call in the currently blanket-exempt
`workspace/loop.py`. The deployment gate and served N6 witness must turn red;
unknown dispatch is not a positive census.

**Historical preserving control:** take a valid serialized v1/v2 run, remove
the checkout or make an unrelated source edit, and prove the exact historical
serializer still reproduces the old canonical bytes. If the edited bytes alter
the current canonical deployment identity, only the separate currentness
result becomes stale; historical validity remains true.

**Candidate preserving control:** remove owner currentness evidence while
leaving candidate computation enabled. Direct/served N6 still produces the
candidate run and carries `not_established`; N9 and current public authority
remain unavailable. This enforces S0-K06’s candidate/authority split.

## V2 oracle search result

The E02 tree is on `codex/safe-workspace` at `00d946c2b7d052522be092f9c70eb9902f6521c2`.
Its owner code confirms the artifact is a run payload, not merely a schema
string: `runtime/http/services/control/generation_cycle.py@055cca6c9424deac61fa61543143a2a2d2310b1a:294-305`
sets `payload = node.cycle_run.model_dump(mode="json")` and stores it under
the normative-generation-source artifact kind at the current run schema
version. E02’s `generation_cycle.py@a17e52cff360f554478dd44844ea3ef27c62c043:154,1359`
declares v2 as the current `GenerationCycleRun` schema.

The complete ignored-record root contains 63,994 files. Its full extension
census is: 30,912 `.json`, 21,393 `.blob`, 2,387 `.txt`, 2,330 `.lock`, 1,055
`.xml`, 868 `.duckdb`, 818 `.jsonl`, 783 `.md`, 692 `.py`, 607 extensionless,
324 `.npz`, 252 `.sample`, 186 `.hnsw`, 183 `.parquet`, 179 `.log`, 142
dotfiles, 140 `.TAG`, 139 `.gz`, 136 `.pyc`, 135 `.csv`, 76 `.sig`, 76
`.sqlite3`, 47 `.toml`, 36 `.npy`, 33 `.yaml`, 32 `.pid`, 9 `.bin`, 7
`.prom`, 6 `.yml`, 4 `.ini`, 4 `.png`, and one each `.cypher`, `.exit`, and
`.ts`.
Text search for the exact v2 schema
returned 27 files: 13 `.blob`, 7 `.json`, 1 `.log`, 3 `.txt`, and 3 `.xml`.
Four manifests declare kind `runtime_quality.normative_generation_source`,
schema version `policyos.runtime.generation_cycle_controller.v2`, and a
content-addressed artifact ID with matching manifest integrity SHA and byte
size. Their paired blobs contain the complete N6 run field family (`run_id`,
`design_problem_ref`, `terminal_denominator`, `cycles`, `fronts`,
`candidate_summaries`, `value_port`, `promotion_port`, and `strangle_receipt`),
not only the version string:

| E02 test output | Content-addressed run blob | Manifest byte size | JUnit |
|---|---|---:|---|
| `I1-ROLLING-WORK-CYCLE-20260922-CYC-05-B29/outputs/E02-J1044-N-CYC05-b15-postmerge-smoke/basetemp/test_http_job_progress_exposes0/.polisyos/artifacts/sha256/d5/f2/d5f2026f928d1b5cfe9be80245450b7364a63c8fd8cd309ff1d37e603747e71f.blob@sha256:d5f2026f928d1b5cfe9be80245450b7364a63c8fd8cd309ff1d37e603747e71f` | `29,484` | 1 test, 0 failures; `test_http_job_progress_exposes_requested_and_effective_recursive_limits` |
| `I1-ROLLING-WORK-CYCLE-20260922-CYC-05-B29/outputs/E02-J1043-N-CYC05-b15-limits-candidate/basetemp/test_http_job_progress_exposes0/.polisyos/artifacts/sha256/5d/a3/5da31d44fe6c520263a97b41c0593a4d7f588fadfc5dea9c35cf10c410c2ef32.blob@sha256:5da31d44fe6c520263a97b41c0593a4d7f588fadfc5dea9c35cf10c410c2ef32` | `29,060` | 15 tests, 0 failures |
| `I1-ROLLING-WORK-CYCLE-20260922-CYC-05-FULL-R1/outputs/E02-J1085-N-CYC05-full-remediation/basetemp/test_http_job_progress_exposes0/.polisyos/artifacts/sha256/47/32/4732d41718178359512dd1fd31d8dcd8bd999e5fa08c4e09ebcae07b9b9d5d0b.blob@sha256:4732d41718178359512dd1fd31d8dcd8bd999e5fa08c4e09ebcae07b9b9d5d0b` | `29,060` | 21 tests, 0 failures |

A fourth complete payload is at
`I1-ROLLING-WORK-CYCLE-20260922-CYC-05-B29/outputs/E02-J1038-N-CYC05-b15-owner-context-test-only/basetemp/test_http_job_progress_exposes0/.polisyos/artifacts/sha256/b3/67/b3675af191636acaac5d65d4a2728d527e8b8cff36e238d1feb60346477e59bb.blob@sha256:b3675af191636acaac5d65d4a2728d527e8b8cff36e238d1feb60346477e59bb`, but its associated one-test JUnit has one failure, so it is not the primary passing oracle.

Tracked E02 package denominator: 185 files (21 JSON, 160 Markdown, 2 Python,
1 ZIP, 1 extensionless, 1 `.gitignore`); no exact v2 token in its text files.
Tracked current R2 package plus `tests/**/*.json`/`*.jsonl` denominator: 577
files (411 JSON, 160 Markdown, 3 Python, 1 ZIP, 1 extensionless, 1
`.gitignore`); no exact v2 token in searchable JSON/package files. The single
ZIP in each tracked set was not inspected internally; ripgrep does not read
archive contents by default. Binary/non-text records are included in path
counts but are not asserted to have been text-searched.

Conclusion: a complete, E02-produced v2 run byte oracle exists locally in the
ignored CAS and can support an exact historical serializer comparison. The
sidecars are content-addressed integrity metadata, not cryptographic signatures;
this search did not independently recompute every blob hash. The v2 oracle is
not checked into the repository, so a durable CI regression needs a reviewed,
safe tracked fixture or a reproducible verifier that can access the cited raw
artifact. Do not report “no v2 oracle exists”; the correct status is “local
oracle found, tracked durable oracle still absent.”

## Sequencing and design references

Wait for R1 before changing the HTTP, recursive, S8, or shared N6 DTO seam; R1
must carry missing cycle context as a typed candidate limitation. R2's missing
current deployment evidence has the same candidate-band behavior. Wait for R13
before persisting through an N6 artifact-store seam; use runtime-supplied,
tenant-bound storage and do not rebuild a CAS from a root path. Keep identity
evidence independent from R1's cycle context and R13's overlay/passport/epoch
custody.

Relevant direction: GY-N6 and its fixture strangle (`GY-engine-subordination.md
§3.5.6, §8.5, GY-N6`); identity/time custody (`policyos-identity-and-custody-boundary.md`);
candidate versus authority band (Stage0 K06); and failure/repair patterns P07,
P08, P29, P31, P32, P37, and P38. The source map implements no GY/Atlas plan
task and edits no debt/register document.
