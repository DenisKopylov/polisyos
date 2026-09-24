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

### Epoch truth and authorized deployment-identity transition

The current Confidence Ledger N12 projection does not establish an epoch:
`N12EpochReferenceProjection.validity` is literally
`epoch_not_implemented` (`confidence_ledger.py:1056-1076, 3688-3718`). It carries
optional epoch/model/rule/schema locators; those fields do not make the epoch
current. R2 currentness is only the owner's deployment-identity result. If a
consumer also needs N12 epoch validity, that independent predicate stays
`not_established` until an epoch owner implements it. Do not turn deployment
identity equality into an epoch claim.

The existing ledger binds its root to `deployment_identity` and rejects a root
whose identity differs (`confidence_ledger.py:1719-1822`). A canonical session
that sees changed code appends `deployment_drift_poison` and treats that poison
as terminal (`:3075-3134, :2012-2040`). There is no authorized identity-reissue
or root-transition API in the owner. R2 must not restamp an old root, receipt,
or trust-posture pin to make it appear current. If the principal and ledger
owner authorize a future identity transition, its proposed contract is
append-only: preserve the old root, receipts, and pins under their old
identity; issue a new owner-bound transition naming predecessor root/receipt
refs, expected and observed identities, authority, premise, time, and falsifier;
then issue a new root/receipt linked to that transition. Old signatures remain
historically replayable and are never rewritten. Until that capability and
authorization exist, changed identity is `stale` or `not_established`, and
current authority stays unavailable. This transition is a named owner
capability gap, not implemented by this map.

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

The v2 specimen was initially missed because the first census stopped at the
package and selected test directories. The full tracked-tree correction is
listed below. Existing `test_generation_source.py`'s
`test_tracked_owner_epochs_remain_exactly_readable` walks an old v1 report and
an N9 v6 promotion fixture, then compares parsed leaf values; its model map has
no v2 GenerationCycleRun and it does not assert byte-exact replay. The N6
owner's `--check` rederives the current generated report and compares canonical
report bytes, but does not prove an isolated historical v2 run replays after
an unrelated edit or without a checkout. Before current N6 regeneration can
replace the tracked specimen, extend `historical_artifacts.py` with
`GENERATION_CYCLE_V2_CONTRACT_BLOB`, set to
`"1bb62940465b1c83d707b87df8f9b59484c28762"`. Use its existing
`historical_owner_bytes` Git `cat-file` helper to retrieve and verify those
immutable whole-contract bytes, parse the historical contract, and extract its
`generation_cycle_run` object. Do not read the current generated JSON path as
the v2 historical fixture. The focused test must run the version-dispatched v2
historical serializer on that exact payload and compare the canonical run bytes
with the captured v2 projection, while the replay/validator receives no
`repo_root`; only test-fixture retrieval uses Git. Show replay still succeeds
without a source checkout and after a source change that makes the owner report
a different current deployment identity. Once the pinned fixture/test source
is in place, regenerate the current N6 contract only through its registered
owner command
`.venv/bin/python -m tools.quality.validation.check_layer3_gy_generation_cycle_contract --write`,
then inspect the entire generated delta. That regenerated current artifact is
not the v2 historical fixture and does not replace its pinned Git object.

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
8. Governed output companions, outside the mechanism count: the N6 owner writes
   `architecture/policy_design_case/layer3_gy_generation_cycle_contract.json@1bb62940465b1c83d707b87df8f9b59484c28762`;
   if its run schema or projection changes, regenerate only through
   `tools.quality.validation.check_layer3_gy_generation_cycle_contract` and
   inspect the entire delta. The N11 owner writes
   `architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json@58a81301ba500bf2ff9c5aaed765a4d9365a17b3`;
   if its owner projection changes, regenerate only through
   `tools/quality/validation/check_layer3_gy_confidence_ledger.py --write`
   with the registered catalog and L5 inputs, then inspect the entire delta.
   Their lifecycle owner and command contracts are pinned by
   `architecture/generated_artifacts.toml@9c0f1dfdac86dd02f16d3b17c5bd28da4e0f9165` and
   `tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py@906bbe22b01704bb1528358b52324767d6e48d1e`.
   R2 does not restamp either artifact merely to clear a gate.

Focused test files:

- `tests/unit/runtime/quality/test_confidence_ledger.py@1537ea3e9984fd9599d4d95b3c9e95c040af6fbf` — owner-issued evidence
  and status transitions;
- `tests/unit/runtime/quality/test_generation_cycle.py@4f851cb207267a13877647ef82a2b73f3a24360a` and
  `tests/unit/remediation/test_cyc_05.py@9a9199993498fa60a72a786fcacc45d469324231` — byte-exact versions, no-checkout
  history, N6 candidate control, census removal probe;
- `tests/unit/runtime/quality/historical_artifacts.py@4a8d4bf763b2295da64e5e418f96fbf7c3ddd3c1` and
  `tests/unit/runtime/quality/test_generation_source.py@dfbffbf32f90920a0b67310e4dd1d94b45e9308c` — pin the v2
  contract Git blob and read it through `historical_owner_bytes`; test exact
  v2 serialization from the extracted historical payload without `repo_root`.
  The existing pinned v1/N9 v6 walk remains separate; extend it for exact v1
  serialization. The current generated N6 contract is regenerated through its
  owner only after the historical blob fixture is pinned.
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

At the candidate-tree checkpoint commit
`b4bcdc2539b25948c58b9e69757109cf33c34641` (tree
`1fc58b7c2feb614ce9ff546ea5c18cd177175778`), the complete tracked
`policy-engine` tree contains 13,336 files, including 2,866 `.json` and 13
`.jsonl`. The exact v1/v2 schema-token search over every tracked file in that
same candidate-tree denominator, including binary files, found 13 token-bearing
files; this is not a count for another base or a later map-writing tree. Only four
structured architecture JSONs contain GenerationCycleRun objects. Recursive
parsing of those JSONs found ten complete run objects: nine v1 and one v2.
The tracked-file denominator is the full output of
`git ls-tree -r --name-only b4bcdc2539b25948c58b9e69757109cf33c34641 -- policy-engine`;
the token-file count is the full output of
`git grep -a -l -e policyos.runtime.generation_cycle_controller.v1 -e policyos.runtime.generation_cycle_controller.v2 b4bcdc2539b25948c58b9e69757109cf33c34641 -- policy-engine`.
The pinned historical owner blob referenced by
`tests/unit/runtime/quality/historical_artifacts.py@4a8d4bf763b2295da64e5e418f96fbf7c3ddd3c1`
adds one more complete v1 run. The structured records are:

| Tracked record | Object path | Run schema | Complete run fields |
|---|---|---|---:|
| `architecture/policy_design_case/layer3_gy_generation_cycle_contract.json@1bb62940465b1c83d707b87df8f9b59484c28762` | `$.generation_cycle_run` | v2 | 18 |
| `architecture/policy_design_case/layer3_gy_composition_certificates.json@dea255d64e83502b093161825d134366f50c98eb` | `$.recursive_runs[0].nodes[3].cycle_run`, `nodes[4].cycle_run` | v1, v1 | 15 each |
| `architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json@efb75eb36d6731d07ce70e49eb9dda83649b52d6` | `$.proof_recordings/{education,first_vertical,unseen}/{authority_source_migration_receipt/historical_recording,}compiled_run/recursive_run/nodes/0/cycle_run` | v1 × 6 | 15 each |
| `architecture/policy_design_case/layer3_gy_second_domain_cycle_entry_trace.json@f6fc534efd909a1ca311fd9665a03d4ec41e8a8e` | `$.generation_cycle_run` | v1 | 15 |
| Git blob `adab90797d1d1562ae252c076883bc5af6d77ce6` (183,254 bytes; parsed by the fixture above) | `$.generation_cycle_run` | v1 | 15 |

The N6 v2 contract is a durable tracked specimen, not merely a schema string.
Its owner builds `generation_cycle_run` from `run.model_dump(mode="json")`
and the nested `strangle_receipt`, then writes a canonical whole-contract
projection. The v2 object is under the schema at line 3307 of the tracked
artifact blob `1bb62940465b1c83d707b87df8f9b59484c28762`; the existing
`historical_owner_bytes` helper can pin and verify that Git blob before the
owner regenerates the current JSON. The exact v2 replay test must read the
historical object from that immutable blob, not from the mutable generated path.
The N6 validator's exact-byte rederive is useful current-output verification,
but it is not the historical replay test described above. After the v2 blob is
pinned, any current-schema output refresh must use the registered N6 owner
command and its full delta must be inspected.

The ignored-record search still found four complete E02 v2 CAS blobs. Three
are paired with passing JUnit runs (J1044: 1 test/0 failures; J1043: 15/0;
J1085: 21/0); J1038 contains a complete payload but its one-test JUnit failed.
Their manifests have matching artifact ID, integrity SHA, and byte size; the
inspection did not independently recompute every blob hash, and the sidecars
are not cryptographic signatures. These raw CAS specimens supplement, rather
than replace, the tracked v2 fixture.

## R2 sibling: historical Wave 5 `repo://` references

The four-base P41 replay found a second instance of the same history/current
state conflation in a separate owner. Treat it as an R2 sibling for the
historical-validity/currentness split, but do not claim the GenerationCycleRun
mechanism itself fixes it. The Wave 5 test is
`test_policy_design_case_capability_ratchet::test_wave5_exit_records_i5_manifest_and_influence_boundaries`;
its test, manifest, and validator blobs are unchanged across all four bases.
The full diagnostic and exact four-base JUnit table are recorded in
`PolicyOS_E02R2/R14_RATCHET_MAP.md@c13460e67ebf13ba36faf077fb38a7c38fce5631`.

| Base | Outcome | JUnit artifact (`path@sha256`) |
|---|---|---|
| E02 execution base `78187878ee188ff6d27442ba1498bd094da9785b` | pass | `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-pre-repair-20260924T161246Z-93931/cells/e02_execution_base/test_policy_design_case_capability_ratchet-1208f704fe80.junit.xml@sha256:24ac90ee7118270b65ce28bad68a9dc884c9e9a13e763732d6af5a522f8ad86b` |
| E02 head `00d946c2b7d052522be092f9c70eb9902f6521c2` | fail | `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-pre-repair-20260924T161246Z-93931/cells/e02_head/test_policy_design_case_capability_ratchet-1208f704fe80.junit.xml@sha256:13d44f90d391fe6cfa7f1d13471767c41e743848d6383085a5662431384e4542` |
| main `5fd3ebcc15637e98bbd4938de5d62ee5004504a8` | pass | `/Users/deniskopylov/.codex/scratch/e02-r2-baselines/p41-pre-repair-20260924T144020Z-80143/cells/main/test_policy_design_case_capability_ratchet-1208f704fe80.junit.xml@sha256:4aebe1a1e5ed2b8672686870c97fca4b56d7899b95c781b4f2c0d66f58eab140` |
| Phase 0 merge `73c656744f051d9f40667da7f8bc91c61d8b4ebf` | fail | `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-pre-repair-20260924T161246Z-93931/cells/phase0_merge/test_policy_design_case_capability_ratchet-1208f704fe80.junit.xml@sha256:ef86ba29e19625866b81baf79d1d82be4c25fa57323788d3b3fefeb55141b2d4` |

The same results and hashes are recoverable from the remap receipt
`/Users/deniskopylov/.codex/scratch/e02-r2-p41-artifact-remap-20260924.json@sha256:4f0e2848ec8f83079cc9b20bcbb29aeee90c51d73f3b8cb2d616dad4b9b907be`;
the relocation inspection counted 113 checkpoint rows, 109 JUnit refs (61
direct, 48 SHA-exact relocated), four safety skips with no JUnit by
construction, and zero unresolved artifacts. The tracked inspection is
`PolicyOS_E02R2/P41_ARTIFACT_RELOCATION.md@f60fe1b2c44dbc5c6164a06d2f3c326ac174406a`.
This supersedes any apparent missing-JUnit limitation caused by their move
from the original scratch paths.

The separate owner predicate is
`tools/quality/validation/check_policy_design_case_capability_ratchet.py@1cd361b73a01e7ed7668d18b92a4491e335d8628:3627-3654`.
`validate_repo_reference` resolves a `repo://` target against the current
checkout, tests `target.exists()`, then optionally checks a text anchor. The
immutable manifest
`architecture/policy_design_case/wave5_i5_external_consumer_truth_manifest.json@fa16e56d90fcfb6b90d8de56cb261ae00f69a95d`
contains 36 references to 30 distinct target paths. Its
`$.artifacts_produced[0].surface_refs[3]` refers to
`repo://packages/runtime-api-client/runtimeApiClient.ts`, whose old raw twin
exists at the execution base and main but is deleted by E02 and absent on the
Phase 0 merge. That one missing target causes the same-key base/main-pass to
E02/Phase0-fail transition. The manifest records no path content digest,
source commit, or as-of identity. Main's file presence therefore passes the
current-path predicate without proving the historical bytes; E02's deletion
fails the predicate despite the unchanged historical manifest and the
canonical `canonicalRuntimeApiClient.ts` export.

P38 divergence: the historical property is replay of the immutable Wave 5
record against its accepted source evidence, with present path availability
assessed separately. The implementation tests today's path existence and
optional anchor, not the source revision/content accepted with the record.
The four-base witness demonstrates both directions of that divergence.
The manifest is registered as immutable source-committed historical evidence;
do not restore the retired raw client or rewrite/restamp the manifest merely
to turn this gate green. A possible class-level route is an owner-issued,
as-of content binding/sidecar plus a distinct current-reference check; whether
the owner can issue that binding is `not_established`. Its separate write/test
set is the historical `repo://` resolver,
`tools/quality/validation/check_policy_design_case_capability_ratchet.py@1cd361b73a01e7ed7668d18b92a4491e335d8628`, and its behavioral witness
`tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py@7c4b73fb339f36b21bcc430c1260f35d76a745d`, plus any owner-issued binding artifact—not the N6 run validator. Preserve the live package route
`packages/runtime-api-client/canonicalRuntimeApiClient.ts@9227640d31e58a3d05572127c5399bf3e4a4bddd` and its owner README
`packages/runtime-api-client/README.md@5772d3ab213e8f44a32ceef0de15f6d63d94bacb` as the control. The manifest's immutable source-committed lifecycle is registered in
`architecture/generated_artifacts.toml@9c0f1dfdac86dd02f16d3b17c5bd28da4e0f9165`; any new binding must go through that record's owner and its delta must be inspected. Recheck the exact four-base attribution before code changes. If the
principal decides the historical reference must mean current path existence,
that changed expectation and its cost need a decision record; no implicit
compatibility exception is authorized here.

Required Wave 5 probes before closure: remove or alter any owner-issued
as-of/content binding while keeping manifest markers and require historical
resolution to fail; preserve the current canonical TypeScript export while
the historical raw twin stays absent and verify ordinary current package use
still resolves. The first cannot yet be run because no as-of bytes or binding
exist. This item remains `not_established`, with owner capability
`producer_missing`, until the principal/owner decision and evidence arrive.

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
