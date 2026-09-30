# E02-R2 write leases

## R13/B12 snapshot typed-view custody expansion (2026-09-30)

Root alone writes the canonical branch. After the first guarded-store probe
found a foreign-tenant sidecar read and a lost manifest-view selector, the
R13/B12 snapshot write set expands to
`policy-engine/src/polisyos/foundry/execute/_internal/snapshots/__init__.py`
and `policy-engine/tests/unit/foundry/runtime/test_executor_snapshots.py`.
The scratch candidate writer and independent reviewer have read-only access
to the canonical tree and may prepare patches outside it. No other writer
holds these two files. The design is pinned in
`/Users/deniskopylov/.codex/scratch/e02-r13-snapshot-tenant-custody-design-v2-20260930.md@sha256:58615a63d385579bc1eaf87cd470de5cd0ebeea7f0643f9ace40dbe05ca3c5d6`.

The single property is that an owner-written snapshot uses the runtime-supplied
tenant store and retains its exact typed CAS view through the state-blob write,
lineage, wrapper, and readback. The first `has(ArtifactID)` patch is not an
accepted fix: it can read a foreign default manifest and loses the selector.
Use the CAS's `put_bytes` typed-view admission; do not inspect raw paths or
construct a second store. Retain the old default manifest byte-exactly and
prove foreign access is denied. A marker-retaining selector-removal probe must
turn red, while a current typed view and a historical default view both remain
readable by their owners. This is the second P40 finding of the same class,
so widen the mechanism, then bound any remaining residual by its falsifier.
No governed receipt, epoch, generated family, plan or debt register is leased.

## R13/B12 controlled WMR state consumption by N5 (2026-09-30)

Root may write the following source and test files in the clean attached `codex/e02-r2`
integration worktree after independent design review:
`policy-engine/src/polisyos/runtime/quality/generation_cycle.py`,
`policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py`,
`policy-engine/tests/unit/runtime/quality/test_generation_cycle.py`, and
`policy-engine/tests/unit/runtime/quality/test_joint_simulation_horizon.py`, and
`policy-engine/tests/unit/remediation/test_cyc_02.py`.
No other writer holds these paths; R2's temporal lease on the first file was
released at `977943ed9`. The reviewed design target is
`/Users/deniskopylov/.codex/scratch/e02-r13-candidate-n5-lease-design-20260930/R13_N5_CANDIDATE_LEASE_DESIGN.md@sha256:e6eeaca2d66ab36de409e4072ceb0663f147391b6fa98bc5a8bc35047d390fc6`.

The property is numerical consumption of the WMR-bound Foundry StateSnapshot
through the injected tenant store by the existing ProgramGraph N5 runner.
The remediation test is in this lease because the v1 EvalSafety helper now
requires the injected store to verify a persisted N5 result before naming its
schema. Its synthetic no-store call failed on 2026-09-30 while the two
independent N5 controls passed; the test must supply its existing real store.
The same file may pin the v2 stripped-blocker refusal. This amends only the
test surface; no authority producer or historical receipt is reissued.
Require a WMR-listed graph, load and compare the controlled candidate plan,
override caller-provided state/store runtime fields, and persist a versioned,
typed content-bound consumption record. Plan provenance and horizon time
alignment remain `not_established`; N8 may only carry candidate-grade value.
All N5 request ingress (factory, explicit request and hint-built request) must
pass through the same WMR-bound resolver. Check the selected graph and plan
manifest profiles and the plan-to-graph binding before execution. N8 derives
both limitations from the persisted consumption record and returns them
explicitly; review every consumer of `_SIMULATION_AUTHORITY_LIMITATIONS` so
the wider allowlist cannot turn either unknown into authority.
V1 N5 result bytes require frozen historical replay, not reserialization with
new fields. A marker-retaining removal of only the state handoff must turn
the two-state positive red; the ordinary NCM candidate is a preserving
control. No served graph producer/selector, WDI unit/time/SKG admission,
S8/N9/publication claim, Foundry implementation, generated family, plan or
register is leased. If actual guarded-store use proves a Foundry runtime
defect, stop and review an expanded owner write set before touching it.
All behavior, removal and four-base P41 cells are `UNRUN` below the 8 GiB
free-disk floor. The unedited recursive N5 writer and N8/importer test files
remain in the post-integration replay denominator.

## B111 required evaluation status at every registry intake (2026-09-30)

The B111 candidate `edb05ed7de7ae9de441e76a2c9009e6d24233dec` is frozen
for independent review, not integrated. Its public `ParetoRegistry.update`
and `ParetoRegistryEntry` currently default an omitted evaluation status to
`valid`. A direct caller can thereby enter a declared-basis frontier or
transfer surface with a finite vector but without an established producer
status. This is the same B111 downstream admission class under P40; the
criterion is a recomputed finite vector **and** an explicitly supplied typed
producer status, never a default-`valid` declaration.

The same B111 writer may append one follow-up candidate commit. In addition
to its existing leased paths below, the exact expanded write set is:
`policy-engine/src/polisyos/scientist/methods/search/registry_contracts.py`,
`policy-engine/tests/unit/scientist/search/test_voi_scheduler.py`, and
`policy-engine/tests/unit/scientist/policy_design/test_phase_b_output.py`.
The source contract, concrete update API, and entry DTO must require the
status; existing direct test fixtures may supply `valid` only when they are
deliberately constructing a fully assessed input. Historical v1/v2.0 wire
fixtures remain field-absent and decode as `unassessed`. Schema 2.1 is needed
to persist per-entry producer status/error across registry replay and transfer;
the older per-view assessment does not retain a finite-but-invalid row's
source status. This adds no status enum. No other writer owns these three paths
during this amendment. The current candidate is unchanged until this lease
is recorded. Behavior, four-base P41 and marker-retaining removal remain
`UNRUN` below the 8 GiB free-disk floor; static review does not close B111.

## R2 temporal S8 source handoff to R13 candidate N5 (2026-09-30)

The R2 temporal S8 candidate at `a2143a4e1c2fe436a9d357dab5f7966cbc693ad1`
was integrated as `658833ffd` with byte-identical versions of all nine
leased source, test, release and migration paths. Its worktree is clean and
has no active writer. At the present `codex/e02-r2` head, the shared
`policy-engine/src/polisyos/runtime/quality/generation_cycle.py` Git blob is
`9dfbd19939922c50989382ed871fdfd1d715c9f5`, identical to that candidate.
The R2 temporal S8 exclusive lease on this quality file is therefore
**released**. This releases file ownership, not R2's source-free currentness,
issuer, positive S8, four-base P41 or historical-reader residuals. The newer
root-owned R2 outer-v1 lease below covers the HTTP composition owner and its
history/normative tests, not this quality file.

The separately reviewed R13/B12 controlled ProgramGraph state-consumption
slice may receive a **candidate-only** write lease on this quality file after
its complete source/test write set and reused attached worktree are recorded
and independently reviewed. No R13 production graph/plan selector or served
authority lease is granted here; `R13_N5_STATE_CONSUMPTION_TASK.md` and
`OPEN_PREMISES.md#OP-R13-N5-GRAPH-OWNER` state the missing producer and scope.
Do not edit this file under a stale R2 lease or infer that the R13 candidate
closes B12. This handoff was a read-only blob and worktree-status check; it
ran no behavior or removal test.

## R1 controlled N4 source identity in served candidate N5 (2026-09-30)

One direct R1 writer may edit only
`policy-engine/tests/unit/runtime/http/test_control_service_di.py` in the
canonical `codex/e02-r2` worktree after root confirms this lease. This
supersedes the wider two-test-file R1 served-source lease below for this
controlled slice; `test_normative_generation_bridge.py` is not included.
Root owns commits and integration. B111's Scientist paths and R13's N5
runtime paths do not overlap; no second writer edits this test concurrently.

Use the existing typed N4 port and GenerationSourceRepository on the served
controlled-profile fixture. Capture the candidate actually passed to N5,
reopen the same-run GenerationSourceHandoff, resolve it for the exact problem
and cycle, and require a nonempty equal expected/retained identity set plus
candidate ID and atom-content-hash equality. Keep the fixture's synthetic
candidate lineage and profile `not_established`; this does not prove N5
resolves source custody, production profile admission, real data/time, S8,
N9, or publication. A marker-retaining source-link removal must make the
persisted-custody assertion red, while ordinary no-owner candidate work and
direct explicit-N4-without-context refusal remain. Current exact-head
four-base P41 and removal runs are `UNRUN` below the 8 GiB disk floor. The
writer may perform static checks, but no resource-bearing test until the
floor and RAM reserve are satisfied. Independent review precedes commit.

Design: `/Users/deniskopylov/.codex/scratch/e02-r1-controlled-owner-bridge-audit-20260930/R1_CONTROLLED_OWNER_BRIDGE_AUDIT.md@sha256:4d8735c6e7de6725a5a627210a88c194e64c3f05aa54729ffa0aaa4d94259541`.

## B111 registry-to-result assessment propagation (queued 2026-09-29; `e17d550bb`)

### Independent-review expansion (2026-09-30)

The first candidate at `d11775516` is **NO-GO** under independent review
`/Users/deniskopylov/.codex/scratch/e02-r2-b111-candidate-20260928/B111-independent-review-final.md@sha256:1ee4143adc6741b3e9ea3c2651d65e014d3196a749ff98ed3a65e2b5f583ee56`.
For this same candidate writer, this dated expansion supersedes the narrower
"finite ranking" and "downstream finite-admission" write-set sentences below;
those sections remain historical records of the prior slices. The exact
current source lease under `policy-engine/src/polisyos/scientist/` is:
`policy_design/objectives.py`, `policy_design/search.py`,
`policy_design/output.py`, `methods/search/controller.py`,
`methods/search/run_state.py`, `methods/search/contracts.py`,
`methods/search/pareto_registry.py`,
`methods/search/strategies/adapter.py`,
`methods/search/strategies/multi_objective.py`, and
`nodes/builtins/planning/run_hierarchical_policy_search.py`. The exact
current mirrored test lease is:
`policy-engine/tests/unit/scientist/search/test_contracts.py`,
`policy-engine/tests/unit/scientist/search/test_phase_b_policy_runtime.py`,
`policy-engine/tests/unit/scientist/search/test_pareto_transfer.py`,
`policy-engine/tests/unit/scientist/search/strategies/test_adapter.py`,
`policy-engine/tests/unit/scientist/search/strategies/test_multi_objective.py`,
`policy-engine/tests/unit/scientist/policy_design/test_phase_b_policy_design.py`,
`policy-engine/tests/unit/scientist/policy_design/test_phase_b_hierarchical_search.py`,
and `policy-engine/tests/unit/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py`.
No second B111 writer shares the candidate worktree. The same P40 class is
typed-but-unadmitted evaluation crossing best/acceptance/frontier/report
boundaries. Fix the shared assessment and route both SearchController paths,
the configured-objective producer, direct registry intake, hierarchy report,
and registry-free legacy front through it. Preserve the distinct P04 rule:
only genuinely absent typed data may use the legacy scalar path; present
invalid/unassessed data may not. Strict JSON must retain non-finite invalid
observations through a typed owner codec, without bare NaN/Infinity tokens or
historical restamping. Review the expanded candidate independently before
root cherry-picks any commit. The 8 GiB disk floor currently leaves tests and
four-base P41 `UNRUN`; static checks may proceed. Mixed finite/unassessed
input must still select a finite assessed candidate with typed partial
coverage; all-invalid input emits no champion or global frontier. A
registry-free legacy list has no coverage status and remains candidate-only
until an owner-backed assessed projection replaces it.

After the R14 candidate below is reviewed and integrated or rejected, one
direct B111 writer may reuse its clean existing candidate worktree. Root alone
integrates the reviewed B111 candidate. The exclusive permanent source write
set is `scientist/methods/search/pareto_registry.py`, `run_state.py`,
`controller.py`, `contracts.py`, `scientist/policy_design/search.py`,
`scientist/policy_design/output.py`, and
`scientist/nodes/builtins/planning/run_hierarchical_policy_search.py` under
`policy-engine/src/polisyos/`. The mirrored tests named in the independent
review are leased to this writer; any new source/test path requires a written
lease amendment before editing. R2 owns its separate S8/generation files;
R13 remains sequenced on any overlapping source. Do not change the objective
basis owner, instantiate another ParetoRegistry, or edit the debt register or
plans.

Use the existing `ParetoRegistrySnapshot.view_assessments` as the single basis
truth. Test first: an omitted required-axis row must remain typed unassessed
through the registry, run state, SearchResult, hierarchy, and both persisted
reports, while complete finite and candidate-only controls keep working.
Change both hashed report schemas to v2 only with explicit byte-exact v1
historical serializers/loaders; never reissue or restamp old artifacts. The
registry-less hierarchy producer must retain candidate work without emitting
an unproved global frontier. Remove assessment propagation or per-row
disposition while keeping schema/status markers: the persisted/served witness
must turn red. Freeze source for each run and independently review each clean
candidate boundary. Before permanent edits, attempt the specified four-base
whole-file replay; preserve resource-limited cells as typed UNRUN under Denis's
prior ruling, then run focused and touched-file current-head tests. Keep one
resource-bearing test process at a time in this worktree, at least 8 GiB free
disk and 25% free RAM. Do not run concurrently with another heavy native job.

Design correction and test set:
`/Users/deniskopylov/.codex/scratch/e02-b111-current-design-6f6e-20260929/B111_CLASS_PROPAGATION_REVIEW.md@sha256:b37e3bcf8a260af27d6efe8d32d518bfa4a87faf9d6ee65830a5aae32761b9fa`.

## R14 existing-owner facade imports (narrowed 2026-09-29; `913bf82db`)

One direct R14 candidate writer may reuse a clean existing candidate worktree
after verifying that its branch is attached and bringing it forward by an
append-only merge. The exclusive source write set is exactly
`policy-engine/src/polisyos/fabric/connectors/cache/_store_core.py`,
`policy-engine/src/polisyos/fabric/ingestion/ingestion_providers.py`, and
`policy-engine/src/polisyos/fabric/storage/tenant_cas.py`. Route the three
tenant-context imports through the already supported `polisyos.core.security`
facade. Do not change the owner exports, architecture contract, tests,
generated families, or register in this slice. The earlier four-file lease
incorrectly assumed `polisyos.ir.api` exported `SLOT_ID_PATTERN`; that module
is an export manifest and the import raises `ImportError`. The actual stable
facade is `polisyos.ir.kernel`, which is not currently in the supported
entrypoint contract. `design_problem.py` is released from this lease; its
single deep-import finding remains open pending an IR public-entrypoint
decision. No runtime workaround or silent contract edit is allowed.
The R13 ingestion source lease is sequenced after
this import-only candidate is reviewed and integrated or rejected; no other
writer edits these three files meanwhile. Root alone integrates a reviewed
candidate. Record the exact pre-edit and post-edit import edges, run the
existing focused behavior controls, and require the architecture classifier
to detect a temporary marker-retaining deep-import reintroduction before
restoring the candidate byte-exactly. A classifier result is bounded to these
three edges; the remaining guardrail findings retain their own provenance.
Keep the source frozen during each run, use one process group for the focused
tests, and preserve at least 8 GiB free disk and 25% free RAM.

## R7 current-source active-probe removal replay (2026-09-29; `0cf4afa19`)

One direct R7 probe writer uses the clean attached, reused candidate worktree
`/Users/deniskopylov/.codex/worktrees/e02-r7-r8-probes/polisyos` at
`25f01088d`. Its `acquisition_executor.py` and two selected test blobs are
byte-identical to canonical `codex/e02-r2@0cf4afa19`; no branch update is
needed. It may temporarily edit only
`policy-engine/src/polisyos/runtime/quality/acquisition_executor.py` with the
one-line `live_acquire_permit=permit` to `None` marker-retaining removal patch
from the earlier R7 probe. First run the governed intercepted-transport test,
the foreign-country refusal, and ordinary active-health control at exact
unmodified source; then apply the mutation, require the governed request to
show the extra USA egress while the ordinary control remains green, and
reverse it byte-exactly. Store JUnit/log/patch hashes in scratch and verify
clean attachment and original blobs. This is a current-source proof lease, not
a permanent runtime change, a real network request, or all-transport closure.
Freeze the candidate tree during each run, use one test process at a time,
keep 8 GiB disk and 25% RAM free, and do not touch canonical source or other
writers' files. Root alone integrates any future code candidate.

Earlier probe: `/Users/deniskopylov/.codex/scratch/e02-r7-fixture-current-20260927/R7_R8_CURRENT_MUTANT_RECEIPT.md@sha256:e38d626dd42c780d37d84607ce0cb51b7f2ddbb3e25387571fbd42f17c80ff84`;
the exact same one-line patch applies cleanly to the current source blob
`399fc8d459ebb71169ded1da375e59c9dc24ecea`.

## B109 exact same-group Pareto witness (2026-09-29; `4fd29d6e0`)

One direct B109 writer reuses the clean attached worktree
`/Users/deniskopylov/.codex/worktrees/e02-r7-r8-probes/polisyos` on
`codex/e02-r2-r13-selected-row-candidate`, fast-forwards from the current
`codex/e02-r2` branch append-only, and edits only
`policy-engine/tests/unit/scientist/methods/autotune/test_pareto.py`.
The production comparator is not a permanent write target: its current weak
comparison already has the intended property. Use the exact same-first-group
3D pair, both permutations, duplicate and incomparable controls, and an
independent minimize-direction control which asserts the lower raw cost wins.
After a clean passing current test, temporarily change only the comparator's
`<=` to `<` in the isolated candidate worktree, retain markers, require the
new discriminator red with controls green, then reverse the patch byte-exactly.
Record source/test blobs and JUnit hashes. Run one light test process at a time;
freeze the candidate tree during each run. Do not touch canonical source, any
generated family, or `production_data`; root alone integrates a reviewed
candidate. Preserve at least 8 GiB free disk and 25% free RAM.

Design: `/Users/deniskopylov/.codex/scratch/e02-nb109-pareto-design-20260929/NB109_PARETO_TEST_FIRST_PLAN.md@sha256:40d03bf0f8fb2d2a9804a27fdd8b9c1d648ecbe697cbd0e10fbf050e66f1b6b7`;
independent review: `/Users/deniskopylov/.codex/scratch/e02-nb109-pareto-design-review-20260929.md@sha256:95d62e375fce364b5ebf3dc4fe83830e553a25a5853640e0e179ead1f8ed07ec`.

## R6 foreign-context N5 removal probe (2026-09-29; `58df9a932`)

The R5 writer and five-selector R9 reader have finished in the clean reused
`/Users/deniskopylov/.codex/worktrees/e02-r2-r1-sim-gateway/polisyos` worktree.
One R6 probe writer may fast-forward its branch `codex/e02-r2-r1-sim-gateway`
to the current integration head, then temporarily edit only
`policy-engine/src/polisyos/runtime/quality/generation_cycle.py`.
No permanent source or test edit is leased. The mutation must disable only the
atomless `candidate_unbound` resolver call inside `_context_world_model_record`,
keeping the identity markers and other gates intact. Before mutation, record
the exact source blob and run the foreign-context negative plus the
same-context control. Under mutation, the negative must turn red and the
control must stay green. Restore the source byte-exactly with a reversed patch,
verify a clean attached branch, and keep all JUnit/raw outputs in scratch.
Do not use the canonical integration worktree for the mutation. Use one capped
pytest process at a time; preserve 8 GiB free disk and at least 25% free RAM.
This is a proof lease, not authority to rewrite R6 or adjacent R13 behavior.
Design: `/Users/deniskopylov/.codex/scratch/e02-r6-property-audit-20260929/R6_REMOVAL_PROBE_PLAN.md@sha256:d82cc91e3500e10fd321b38e982f15f4817d9ab5dc931ce6c7424632234222f3`.

## R1 served N4 source-owner witness lease (2026-09-29; `21752fa16`)

One R1 writer reuses the clean worktree
`/Users/deniskopylov/.codex/worktrees/e02-r7-r8-probes/polisyos`, branch
`codex/e02-r2-r13-selected-row-candidate`, after an append-only fast-forward
from `codex/e02-r2`. Its exclusive permanent write set is
`policy-engine/tests/unit/runtime/http/test_control_service_di.py` and
`policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py`.
This supersedes the earlier immutable-front/current-egress candidate lease
below. That uncommitted diagnostic patch was frozen at
`/Users/deniskopylov/.codex/scratch/e02-r1-current-fronts-v2-5a57a6665/r1-v2-premise-review.patch@sha256:79aea6ca0041902d6971bf4799491fa89e6bdcd9645e7da9e0e036c28f072707`,
then reversed byte-exactly before the worktree fast-forward. Root alone
integrates a reviewed candidate; no runtime source edit is leased here.

Replace the controlled fixture's `SimpleNamespace` N4 bypass with the real
`N4GenerationPort` and a deterministic local response against the exact served
problem, owner-replayed context, and selected WMR. Require a nonempty typed
`DesignGenerationOrganRun`, source-store replay with positive equal
expected/retained identity sets, and an N5 `joint_simulated` candidate result.
The positive retains the existing profile-admission `not_established`, no N9
promotion, no S8 authority, and no publication controls. Test first: the
source-positive assertion must fail on the old fixture. A marker-retaining
source-persistence failure must make the receipt drift/refuse while its
expected identity denominator remains positive; N9 refusal alone is not the
probe because the profile is already limited. If canonical N4 cannot ground
an atom against this exact fixture, record the typed owner/data premise and
stop this slice without fabricating an atom or copying another fixture's ref.
Run one resource-bearing test process at a time, keep 8 GiB free and at least
25% RAM available, and freeze its worktree source during every run.
Design:
`/Users/deniskopylov/.codex/scratch/e02-r1-positive-owner-path-20260929/R1_N4_POSITIVE_OWNER_PATH_DESIGN.md@sha256:3356bde502577023f08111cfc6aa2b7f414b0c7793c9d7207428f5f675bbb120`;
independent conditional GO:
`/Users/deniskopylov/.codex/scratch/e02-r1-positive-owner-path-review-20260929.md@sha256:11513ef851f9e9fda5ffa4544d4326aa646687a43c8742ada9ccce944f864938`.

## R5 protected-mode denominator test lease (2026-09-29; `cd9e935e5`)

The current R1 owner-fixture design does not use
`policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py`.
Release that file from the older R1 owner-station lease for one R5 writer in
the clean, reused `codex/e02-r2-r1-sim-gateway` worktree. After an append-only
fast-forward to this branch, the writer's permanent write set is exactly that
one test file. Root alone integrates a reviewed candidate. The production
owner `runtime/quality/recursive_generation_cycle.py` may be changed only as
a temporary marker-retaining removal probe, with its initial blob recorded
and restored exactly before any candidate commit. No other agent writes this
worktree during that probe.

The test extends the existing pre-N4 EvalSafety denominator selector across
`sandbox_pilot`, `field_pilot`, and `deployment`: missing, extra, and wrong-key
leaf contexts must refuse before N4. Preserve the exact-current protected
control and context-free candidate/simulation controls. Do not claim a
DataTrust producer or revised-basis EvalSafety refresh. A denominator-guard
removal must turn the semantic test red while leaving its marker text present.
The exact current four-base whole-file comparison precedes the edit if the
resource guard permits it; otherwise retain each typed `UNRUN` and proceed
under Denis's 2026-09-27 ruling, then run the focused and whole current-file
checks after the candidate. Keep at least 8 GiB free and 20–30% memory free;
one test process at a time. Design audit:
`/Users/deniskopylov/.codex/scratch/e02-r5-next-engineering-audit-20260929/R5_NEXT_ENGINEERING_AUDIT.md@sha256:8cbb4318dcb7105c735df0986768a2da512a38b7619ce70d1deb12a2edcf4e47`.

## R1 immutable-front/current-egress candidate lease (2026-09-29)

One R1 writer may reuse the clean worktree at
`/Users/deniskopylov/.codex/worktrees/e02-r7-r8-probes/polisyos` on branch
`codex/e02-r2-r13-selected-row-candidate`, first merging the latest
`codex/e02-r2` append-only and verifying attachment, cleanliness and target
blobs. Its exclusive write set is exactly:
`policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py`,
`policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py`,
`policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`,
and `policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py`.
Root alone applies a reviewed candidate to the integration branch. B26's
numerical paths and the R1 Control test are outside this lease.

The property is replayable, byte-identical v1 S8 leaf and outer composition
under changing N6 currentness, with unvalued candidate fronts visible only
for the sole history-valid source issue
`generation_cycle_source_preservation_not_established(reason=receipt_missing)`
plus typed currentness `not_established` / census `UNRUN` and
missing/unresolved sidecar. Fresh
currentness belongs in a distinct typed egress projection with `projected_at`,
never in either persisted v1 payload. Keep legacy v1 bytes and static reason
codes; reuse the N6 historical validator and Confidence Ledger currentness
owner. Apply the current projection on the initial `_process_control_job`
response as well as status/latest reads. Composition is all-or-none for
fronts. A terminal-blocked N6 run, stale or FAIL currentness, extra source
issue, or invalid history exposes no fronts or ranking; no recommend,
authority, N9, S8 approval or publication is inferred.

Design: `/Users/deniskopylov/.codex/scratch/e02-r1-current-fronts-20260929/R1_CURRENT_FRONTS_DESIGN_V2.md@sha256:72d85b2e36f67f19b8f2614584f19f0a23442e031bae2aad3e29ec207bd77385`.
Independent design GO with conditions:
`/Users/deniskopylov/.codex/scratch/e02-r1-current-fronts-review-20260929.md@sha256:99c3b18c0e8bc1101c0f9a8482be9ed73a4ae3e0b9ac043ed9bd16709261b50b`.
Test-first sequence: `/Users/deniskopylov/.codex/scratch/e02-r1-current-fronts-20260929/R1_CURRENT_FRONTS_TEST_FIRST_SEQUENCE.md@sha256:1d37ff357cdc68d7d4e9cbad0a3e9ca1aafa7454c67ed99b533c999b4267778d`.
Obtain exact pre-edit red, history/currentness temporal controls, source-front
mutation, marker-retaining egress-condition removal and a normal candidate
control. Freeze source during tests, then independent delta review before
integration. The historical N6 issuer and real DataState time contract are
separate OPEN_PREMISES blockers, not reasons to refuse candidate work.
Measure one process at a time until RAM and disk peaks are known; maintain
at least 8 GiB free disk and 20–30% free RAM. Do not edit another path,
generated family or governed receipt without a new lease.

## R1 ordinary candidate world-build removal probe (2026-09-29)

Root alone edits `policy-engine/tests/unit/runtime/http/test_control_service_di.py`
on `codex/e02-r2` to guard the existing plain-request candidate test against
an eager production WMR build. The test patches the canonical WMR owner to
raise if ordinary no-context candidate routing reaches it, while preserving
the existing typed candidate result and separate owner-admitted N5 positive.
This is a bounded route-level removal probe, not proof of the WMR builder's
independent compute budget or S8 authority. The R1 v2 sidecar candidate owns
different files; B26 owns its separate three-file numerical slice. Freeze the
canonical source/test tree during the focused run and keep the 8 GiB disk floor.

## Active bounded R2 historical S8 lease (2026-09-29; canonical `86bdf0e5b`)

One direct R2 candidate writer owns only a scratch patch to
`policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py`
and `policy-engine/tests/unit/runtime/quality/test_s8_blocked_generation_owner.py`.
Root alone applies a reviewed patch to `codex/e02-r2`. The slice may project an
exactly replayed historical N6-v1 source as a typed blocked/no-ranking S8
disposition with both missing deployment identity and unestablished v1 source
custody declared. It cannot claim currentness transitions, a current source,
verified S8 evidence, or served R1 closure. Test first; capture a marker-
retaining removal probe and a candidate-band preserving control. The current
direct-owner whole-file baseline is 1/3 with two source-preservation setup
failures; the historical three bases lack that test file. Preserve the
historical `MISSING` and current 1 PASS/2 FAIL as measured. The post-edit
whole-file/P41 replay remains `UNRUN` until a new receipt exists.
No other candidate edits these two paths until review and root handoff. R1
retains its Control store/HTTP files; R13 retains its Data Forge/N6 files.
Source is frozen during each test run; the 8 GiB disk floor and 20–30% free
memory reserve still apply.

## B88 served record-ref replay slice (2026-09-29; canonical `607872175`)

Root alone writes the canonical B88 slice while R1 and R13 remain isolated in
their candidate worktrees. Complete direct caller census and test design:
`/Users/deniskopylov/.codex/scratch/e02-b88-record-replay-design-607872175-20260929/B88_RECORD_REPLAY_WITNESS_DESIGN.md@sha256:b238b3b03abed1a2d1fe204fbdbf0f2a91b4cab81c1ec1bef39910db9e3ef6b2`.
The exact writable set is `policy-engine/src/polisyos/fabric/data_plane/modes.py`,
`policy-engine/tests/unit/fabric/data_plane/test_modes.py`, and
`policy-engine/tests/unit/runtime/http/test_b88_served_replay.py`, plus this
lease, `policy-engine/release-fragments/unreleased/2026-09-29-e02-r2-b88-record-ref.toml`,
and later reviewed package reports. No `run_lifecycle.py` edit is leased;
the R1 candidate retains it. The served test-first red proves that the normal
record issuer returns bare hex while the replay reader requires a canonical
`sha256:` ArtifactID. Repair the producer's public ref to the canonical ID,
without rewriting retained sessions or trusting a mode label. Preserve the
missing/corrupt-fixture no-egress negatives and ordinary-ingestion control;
verify complete touched test files and a marker-retaining fallback removal
probe. Do not infer publisher source time or all-transport egress coverage.
Keep the 8 GiB disk floor and source frozen during every test run.

## Active owner corrections at `20b110f7b` (2026-09-29)

Root committed the bounded R2 historical `ArtifactID` scalar-wire repair at
`6eac18ccc`; its temporary `generation_cycle.py` and history-test lease is
released. The R1 and R13 candidates may merge the current canonical branch
append-only before their next tests. The R2 repair does not claim a served R1
N6/N5 positive or current authority.

The R1 candidate writer retains the three-file lease listed below and may
also edit `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py`
and its mirrored `policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py`
for one owner-level historical completed-candidate replay operation. This
extension is limited to the same R1 class: fail-closed invalid-intent
sanitation, positive served N6/N5 readback, and a foreign-tenant negative
through the runtime-supplied guarded/ambient-owned store. It must reuse the
N6/N5 validation and artifact owners, not duplicate their rules in the HTTP
reader. The current a037 candidate remains review NO-GO until a complete
positive, marker-retaining removal red, preserving candidate control, and
independent delta review. Do not edit the R13 `generation_cycle.py` owner.

The R13 selected-row writer retains the correction lease below and its saved
WIP recovery patch. Qualified DesignProblem outcome grammar, the frozen N6
history predicate, provider schema, and generated families have the bounded
lease below. The shared canonical-variable contract premise is recorded
separately in `OPEN_PREMISES.md` and does not block the exact WDI candidate
route. Root alone writes canonical files and package documents. Keep at least
8 GiB disk and 20–30% RAM free.

## R13 exact WDI qualified-outcome lease (2026-09-29)

After independent design review
`/Users/deniskopylov/.codex/scratch/e02-r13-qualified-outcome-v3-review-20260929/QUALIFIED_OUTCOME_V3_REVIEW.md@sha256:2f1113ddbf4a622d60d26f67beeb9937b6d1f40799000c341828478db8139cdf`,
the one R13 selected-row candidate writer may additionally edit these exact
paths on its attached candidate branch:
`policy-engine/src/polisyos/runtime/quality/design_problem.py`,
`policy-engine/src/polisyos/runtime/quality/_generation_cycle_history_schema.py`,
`policy-engine/tests/unit/runtime/quality/test_design_problem.py`,
`policy-engine/tests/unit/runtime/quality/test_generation_cycle_history.py`,
`policy-engine/tests/unit/runtime/http/test_nl_pipeline_materialization.py`,
and the already-leased served WDI test
`policy-engine/tests/integration/core_runtime/test_acquisition_world_growth_chain.py`.
Its existing `generation_cycle.py` source lease covers only a necessary
version-aware historical typed-edge adaptation and N8 source-time propagation;
do not rewrite frozen v1/v2/v3 graphs or the R2 scalar RootModel repair.

The v1 default and byte history remain intact; v2 retains qualified
`target_slot` but strict unqualified outcome; v3 admits the exact qualified
outcome, while standalone `OutcomeOfInterest` remains strict in runtime and
JSON Schema. Keep v2 projection decoding. Test runtime/schema parity and a
marker-retaining version-gate removal, replay every pinned historical N6
record, and exercise a served WDI row whose `government.balance` identity is
set before problem hashes and reaches N8 by exact admitted row content.
Syntactically valid but unbound variables remain typed data gaps; source update
time remains `not_established`. The candidate may regenerate only the
DesignProblem contract and changed registered OpenAPI/client dependents through
their owner commands, inspecting every delta before committing. A nonempty
public schema/client delta needs a release fragment; no governed receipt, epoch,
or trust pin may be restamped. The generated-artifact family is serialized:
the R1 writer must not run its owner in parallel. Freeze candidate source/tests
and obtain independent full-delta review before root integrates it.

## Sequential R2 historical N6 projector lease (2026-09-29)

The R13 candidate writer has frozen `generation_cycle.py` at SHA-256
`f974c1144b92fcf496cbb6947ea086ffc07b0d33ed862086ad9aca8dc905383f`
and released that source path temporarily; no R13 test process is running.
Root alone may edit the canonical branch's
`policy-engine/src/polisyos/runtime/quality/generation_cycle.py` and mirrored
`policy-engine/tests/unit/runtime/quality/test_generation_cycle_history.py`
for R2's historical `ArtifactID` RootModel scalar-wire replay defect. The
property is byte-exact persisted N6 history replay, including a non-null N5
result reference, without a live checkout or authority/currentness upgrade.
Root must run a failing behavioral test first, then a preserving historical
control and a marker-retaining removal probe. The R13 writer keeps its current
WIP in its separate candidate worktree but does not edit `generation_cycle.py`
until root commits this R2 slice and the candidate merges canonical append-only.
The two branches' tests must never edit either tree during an in-flight run.

This lease is a temporary sequencing override to the R13 source lease below.
R1 continues on its frozen candidate branch; its N6/N5 positive path is not
claimed until the corrected history owner and guarded CAS replay are tested.

## Current R13 correction lease at `36bc65858` (2026-09-29)

Root remains the sole writer of `codex/e02-r2`. Independent review found the
frozen R13 candidate `04fe512bc` NO-GO for its selected-row-to-N8 claim: the
read-only Data Forge route is owner-bound, but the served WDI test does not
prove that its selected row enters N8, and the source-update/currentness
limitation disappears after the gateway. The same R13 writer retains the clean
attached `codex/e02-r2-r13-selected-row-candidate` worktree for the correction.
Its exact additional write set is
`policy-engine/tests/unit/runtime/quality/test_value_gate.py` and
`policy-engine/tests/integration/core_runtime/test_acquisition_world_growth_chain.py`;
the original seven-file R13 source/test write set below stays leased. No
Foundry selection-owner file, generated family, plan, register, or other test
is leased. Request a new lease before changing one.

The correction keeps hashed `ValueDataProfile` v1 and the Foundry v4 selection
receipt unchanged: the latter binds observed owner rows and the effective
query, and makes no source-update/currentness claim. WDI observation-year
coordinates may still support candidate panel shape. The existing N8
production result must carry `source_update_time_not_established` as a typed
additional authority blocker, without hiding its treatment-assignment blocker
or claiming current N8 authority. The served test must bind the exact admitted
WDI row's value/content to the N8 profile/result through the existing runtime
store and a real catalog owner; a marker-retaining removal of either row
consumption or status propagation must turn red, while ordinary candidate
selection remains allowed. If the selected route starts making a currentness
claim, the Foundry receipt owner needs a separately versioned context/receipt
transition with historical replay; a new unbound runtime hint is not accepted.

The R1 candidate writer exclusively owns the three files in the next section;
R13 does not edit them. Keep at least 8 GiB free disk and 20–30% free RAM.

## Active leases after integration `686ecfcfa` (2026-09-29)

Root alone writes the attached `codex/e02-r2` branch. The R2 S8 history-owner
candidate was reviewed, integrated at `686ecfcfa`, and its source/test lease
is released. The independent R7/R8 exact-source removal-probe worktree is
restored and clean; those source leases are released. The prior dated lease
entries below describe their historical snapshots, not current ownership.

| Work | Exact writable surface | Current owner and boundary |
|---|---|---|
| R1 candidate-intent gate | Reused `codex/e02-r2-r1-candidate` worktree; `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`, `policy-engine/src/polisyos/runtime/http/services/control_plane_store.py`, and `policy-engine/tests/unit/runtime/http/test_control_service_di.py` | One direct candidate writer. The third file is leased only for an owner read of the exact `job_completed` outbox fact: the completed simulate-only reader must rebind its candidate compiled ref and stage statuses from immutable completion evidence, not mutable progress or strict N6 currentness. Preserve the existing store fence and event semantics. Root integrates only after a forged-progress negative, valid completion control, and independent full-delta review. No other writer may edit these candidate files concurrently. |
| R13 selected-row-to-N8 candidate | Reused `codex/e02-r2-r13-selected-row-candidate` worktree; `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/overlay.py`, `policy-engine/src/polisyos/data_forge/read_api/catalog.py`, `policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py`, `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`, and mirrored `test_overlay.py`, `test_acquisition_executor.py`, `test_acquisition_overlay_visibility.py`, `test_generation_cycle.py` | One direct candidate writer. Selected active rows may reach the existing N8 value owner only after full Data Forge admission readback through the runtime-supplied tenant store. The served WDI control and marker-retaining row-removal probe precede independent review. This lease makes no DataState/S1→WMR→N5, source-time, S8, or authority claim. |
| R4 governed-check same-subject basis witness | `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py` on canonical; root only | Independently reviewed V2 test patch is admitted for one focused test and marker-retaining owner-guard removal probe. N9 production owner/checker source remains read-only. Do not claim governed N6 currentness or N9 callback was reached by the typed `UNRUN` gate. |
| R4 guard-removal probe | Reused clean detached `e02-r7-r8-probes` checkout at `6ad734ffc`; temporary copies of the reviewed R4 test and `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py` only | One probe writer may disable the full-scope equality guard while preserving the mismatch marker, run the stale/matching controls, then restore both source blobs exactly. No mutant commit or canonical source edit. |
| R2 S8 byte-history removal probe | Reused detached `e02-r7-r8-probes` checkout fast-forwarded to `ce286a67f`; temporary mutation of `policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py` only | One probe writer may bypass the raw-byte equality guard while retaining its marker, run the direct owner byte-variant negative and canonical positive, then restore the source blob exactly. No mutant commit or canonical source edit; full served S8/currentness remain separate. |
| R9 typed views and R13 selected-row-to-N5 | Read-only source census and scratch design memo | The R13-to-N8 slice above is the only active R13 writer; selected-row-to-N5 remains a separate typed residual. No code lease or authorization to duplicate the world-growth owner. |
| P41 fixed-base replay | Pinned historical worktrees and scratch JUnit/receipts | One broker, at most four profiled light groups; no source edit in a tree under test. Integration-head cells wait for the next source freeze. |
| Premises and reports | Scratch-only patch against the current package documents | One docs preparer, then an independent reviewer; root alone applies and commits on the canonical branch. `OPEN_PREMISES.md` is the separate durable source for missing data, contracts, owner appointments and decisions. |

Keep at least 8 GiB free disk and roughly 20–30% free RAM, with no new swap
pressure; run heavy native jobs alone. A file crossing a listed write set
requires a new lease entry before editing. Root verifies `git status -sb`
before every commit. No historical base, governed receipt, epoch, plan, or
register is restamped to make a gate green.

## Active handoff (2026-09-29; canonical `c0cb70b88`)

Root alone writes `codex/e02-r2`. The R13 selected-row candidate was reviewed,
integrated at `c0cb70b88`, and its source/test lease is released. Its four
touched test files pass 64/64 on that exact head; the integrated JUnit is
`/Users/deniskopylov/.codex/scratch/e02-r13-integrated-c0cb70b88-20260929.xml@sha256:a03f77a26a4b8a1dfb46056d7943203300052e55ce7a90435114cbd1b03ac3c6`.
R13 remains partial because selected admitted values are not yet shown in the
problem-bound WMR consumed by served N5.

The R2 history writer now exclusively leases the clean, attached reusable
`codex/e02-r2-r1-candidate` worktree at `fd9375ae4` for these four paths:
`policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py`,
`policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py`,
`policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py`,
and `policy-engine/tests/unit/runtime/quality/test_generation_cycle_history.py`.
The independently reviewed narrow seam validates exact persisted N6 history
before model normalization and keeps currentness separate; broad model
extraction is not admitted. The writer must freeze a test-first candidate for
independent review before root integrates it. No other writer may edit those
four files meanwhile.

R1's controlled-profile witness writer owns only a scratch patch to
`policy-engine/tests/unit/runtime/http/test_control_service_di.py`. R14's
runtime-contract checker/test patch was reviewed and integrated at
`6ad734ffc`; that two-file source lease is released. Its four-base touched-file
replay found the test path Git-missing at execution/E02, Main 3/3 passing and
integration 5/5 passing; all three shared Main selectors remain pass→pass.
The complete manifest is
`policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260929T003439Z-60001/results.json@sha256:d0a7b3125a036aa5abc2c1cebe0af0f942c703369e04d55cf70e2cd464e68c8b`.
R7/R8 marker-retaining probes now exclusively use the managed detached
`e02-r7-r8-probes` worktree at `6ad734ffc`, with sequential mutation and exact
source restoration; no mutant is committed. Neither candidate writer may edit
canonical files. Read-only P41 planning and the separate
`OPEN_PREMISES.md` blocker addenda hold no source lease. The complete R1
control-service four-cell reconciliation is pinned in
`policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-single-base-control-service-20260929T000807Z-47844/reconciliation.json@sha256:c2cddee57b8d4d6c73a368a94f8d3bc09a1c980699bdf69016d0f66fb7fac782`;
its five Main-to-integration pass→fail identities require repair or a
principal-level disposition. Source trees remain frozen while their tests run.
Keep at least 8 GiB free disk, approximately 20–30% free RAM, and at most
four to five light test groups; heavy native jobs run alone.

## R13 selected-row active-read integrity sublease (2026-09-29; canonical head `7dd9616dce28ab0892a9e76148f001db8ed7245a`)

The first R13 Slice A design was not admitted: a selected-row projection used only by tests has no production consumer. Independent bounded review instead permits strengthening the existing Data Forge active-admission read, already called by `AcquisitionWorldGrowthBridge.resume` before served re-entry. The production property is that a selected active row's current value and decisive coordinates still match the source-derived admission content even if its ID, member keys, counts and receipt markers are unchanged. This slice must remain explicitly partial: it does not put the selected value into the problem-bound WMR or N5, does not qualify source-time semantics, and grants no S8/promotion/publication authority. Design and review: `/Users/deniskopylov/.codex/scratch/e02-r13-selected-overlay-n5-design-20260929.md@sha256:5cd9f2151f0231edcfcb1a07955513bd3aa74b582ce2622dd675c75fe6387673`; `/Users/deniskopylov/.codex/scratch/e02-r13-design-review-20260929/R13_SLICE_A_REVIEW.md@sha256:bfa9b09d9d1cd0f47bf27989ea68c30f032a0f210dcf164d0e0e38ba8c4cc182`.

One candidate writer reuses the clean, branch-attached `codex/e02-r2-r1-candidate` worktree. The **exact source write set** is `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/overlay.py`, `policy-engine/src/polisyos/runtime/quality/acquisition_executor.py`, `policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py`, and `policy-engine/src/polisyos/runtime/quality/acquisition_epoch_admission.py`. The **exact test write set** is `policy-engine/tests/unit/data_forge/domains/catalog/knowledge/test_overlay.py`, `policy-engine/tests/unit/runtime/quality/test_acquisition_activation_readback.py`, `policy-engine/tests/unit/runtime/quality/test_semantic_epoch_native_qualification.py`, and `policy-engine/tests/integration/core_runtime/test_acquisition_world_growth_chain.py`. A change outside this set requires a revised lease before writing. Do not edit `generation_cycle.py`, DataState, any generated artifact family, the register, plans or E02 records. Root remains the sole writer of `codex/e02-r2`; another agent independently reviews the frozen candidate before integration.

The reader must bind the exact passport to the admitted receipt and runtime-supplied guarded store; rederive observations in source order, recompute the existing admission digest, and compare every decisive native row field without changing admission/write path or schema. Pass the existing authority through all three production resolver callers. Test first: a temporary overlay row-value mutation with receipt/member markers retained must refuse active read and served resume, while an unchanged epoch and an unrelated ordinary candidate route remain accepted within their existing limits. The original source must be restored byte-for-byte after a marker-retaining removal probe, before final tests and commit. P37/P38/P40 require naming the residual selected-row-to-N5 divergence, not claiming world-growth closure.

Pre-edit canonical whole-file baselines at `73815191cc86ec4266689b1ac6bbe1bb49819bea`: overlay 40/40 `/Users/deniskopylov/.codex/scratch/e02-r13-selected-overlay-pre-20260929/overlay-738-pre.junit.xml@sha256:99af271f0f9b6e6fc4b99a92fd97b368d7da9ec527e605bc850593999942b38d`; served world-growth 9/9 `/Users/deniskopylov/.codex/scratch/e02-r13-selected-overlay-pre-20260929/world-growth-738-pre.junit.xml@sha256:9d2bac83f39e02b0ddc1b7dd918ed3a41151d0441916261c1f09380b8fca80eb`; activation/native pair 8/8 `/Users/deniskopylov/.codex/scratch/e02-r13-selected-overlay-pre-20260929/activation-native-738-pre.junit.xml@sha256:d7db82b1451bb046b04ca8b023de79d5e828911bfa645c9d72e14aad71193854`. Historical four-base attribution remains UNRUN for this exact test set.

Resource admission remains at most four light test groups with at least 20–30% free RAM and 8 GiB free disk. Read-only production data is linked, never copied or written. Do not edit any tree under test during a run; commit only after branch attachment is checked. The root will retain the independent review, value-mutation removal receipt, and integrated whole-file/JUnit results.

## R9 exact-view tenant-custody sublease (2026-09-29; canonical code head `68caebd84a5102a92eb93453c5a1bf0ca9ea2455`)

The second R9 finding is the same cache-admission class one level deeper (P40): an exact `ArtifactRef` can return tenant A's cached bytes to tenant B even when the durable owner rejects B. The read-only production-caller and scratch-probe receipt is `/Users/deniskopylov/.codex/scratch/e02-r9-cache-code-20260929/R9_TENANT_EXACT_CACHE_AUDIT.md@sha256:b1775551a0c74443bffcf37a0f9b3fcf4beb8490509c454a92497cb8fbc4cd64`. This widens the property to durable-owner admission before every write-through cache hit. A local exact-profile marker is not authorization.

The single R9 candidate writer reuses clean, branch-attached `codex/e02-r9-cache` at `ad8462d62eb720baa4e449e470a22df7761a656f`. The **exact write set** is `policy-engine/tests/unit/core/artifacts/backends/test_caching_store.py` for the initial red and `policy-engine/src/polisyos/core/artifacts/backends/caching_store.py` for the class-wide fix. No other source, test, generated family, governed receipt, plan, register, or canonical file is leased. Root remains the only writer of `codex/e02-r2`; an independent reviewer reads the frozen candidate commit before integration. The test uses the actual `guard_runtime_cas` proxy with an ambient-enforced durable FileSystemCAS, an unscoped local cache, tenant-B denial, and an authorized tenant-A exact-view hit without a remote blob fetch. The marker-retaining removal probe deletes only the pre-local owner admission and must turn the tenant-B test red. Cloud S3/GCS tenant and signed-evidence authority remain typed residuals under OP-R9-CACHE-CUSTODY.

Resource admission remains at most four light test groups with at least 20–30% available RAM and 8 GiB free disk; no worktree under test is edited during a run. Reuse the existing candidate environment; no data copy or Trash emptying.

## Current-state addendum (2026-09-29; pinned integration HEAD `5f433df89f45f3bf29dd2a5d715985790e421db6`)

This snapshot supersedes only the older active-lease snapshot below; all prior sections remain dated history. Root is the sole canonical writer of `codex/e02-r2`, including package documents, `WRITE_LEASES.md`, ledger, baselines and reports. Root's OP-R13 blocker/falsifier addendum is integrated at `359756edc`. R1 owner-bound context code is integrated at `77bfcdb36` and `eb1733750`, but R1 remains partial. Real DataState source-time qualification, trust/profile admission, and an S8 authority producer remain unestablished. No fixture, test lease or candidate authorizes S8.

### R1 helper/importer migration and P41 state

The complete recursive test-source census is `/Users/deniskopylov/.codex/scratch/e02-r1-normative-helper-write-set-20260929.md@sha256:4710f6edf00b7fc62c45c4affb47cde3935e5e072c1dad2fe028ed66431beedf`; the exact four-file migration set is:

- `policy-engine/tests/unit/runtime/http/test_control_service_di.py`
- `policy-engine/tests/unit/runtime/http/test_normative_evidence_intake.py`
- `policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py`
- `policy-engine/tests/integration/runtime_quality/test_evaluation_safety_promotion_bridge.py`

The broker's 16-cell P41 receipt is `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260928T213314Z-92507/results.json@sha256:da21734cb758da1dc5d97be2431b3e3411277d899733251efa59c2510511a2b9`. It is incomplete: 16 total cells comprise 5 recorded PASS, 8 scheduler-paused `UNRUN`, one E02-head worker `PermissionError` `UNRUN`, and 2 Git-verified `MISSING`. The exact per-file statuses in that receipt are:

| Whole test file | Execution `78187878e` | E02 `00d946c2b` | Main `5fd3ebcc1` | Integration recorded at `bed508646` |
|---|---|---|---|---|
| `test_control_service_di.py` | `UNRUN` (paused) | `UNRUN` (paused) | PASS | `UNRUN` (paused) |
| `test_normative_evidence_intake.py` | PASS | `UNRUN` (`PermissionError` in broker worker; no test verdict) | PASS | `UNRUN` (paused) |
| `test_normative_generation_bridge.py` | `UNRUN` (paused) | `UNRUN` (paused) | PASS | `UNRUN` (paused) |
| `test_evaluation_safety_promotion_bridge.py` | `MISSING` in Git | `MISSING` in Git | PASS | `UNRUN` (paused) |

The four integration cells are recorded at `bed508646`, not at current HEAD `5f433df89`; the latter adds the builder-facade source change. Do not relabel or claim the old cells as a four-base replay at current HEAD. The broker released its frozen canonical tree after the incomplete wave. Root admits the single R1 migration writer to proceed under Denis's later direction to continue code work with informative resource-bounded tests. Denis's explicit two-cell `UNRUN` ruling concerned R2; this R1 admission is the orchestrator's narrow decision. It assigns no red/green ownership to an `UNRUN`, does not turn it into `PASS`, and does not waive post-repair whole-file four-base verification.

R11's supplemental served-path test is integrated at `be857b3c9ceb048b9a0fb491ad3ef475620557f3`. Preserve its `promotion_runtime=runtime` fixture input and `source_custody_limitation is None` assertion in `test_control_service_di.py`; its focused 1/1 witness does not replace that file's incomplete P41 cells. The earlier R11 lease also named `test_evaluation_safety_promotion_bridge.py`. No concurrent R11 writer remains: one R1 writer owns the four-file migration sequentially and must preserve the landed R11 control. R11 review: `/Users/deniskopylov/.codex/scratch/e02-r13-r11-stop-control-test-patch-20260929/INDEPENDENT_REVIEW.md@sha256:7e6a89ca1ecdd57581130dcc637b593aa50500552bafce2e7c10162c73d201e8`.

After R1 hands off all four files, the R13 source-store graft witness remains a separate later sublease: `policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py::test_compiled_owner_rejects_leaf_graft_even_when_s8_leaf_is_valid`. It shares a file with the R1 importer migration, so R1 completes first; then R13 runs under a sequential lease. The graft witness does not establish S8 authority.

### Integrated and candidate statuses

- **R14:** integrated at `ec604e9a9b4d7731304bcacd792585a423cc2b55`. Bounded independent review authorized integration and the commit records 30 focused checks; full touched-file P41 remains pending. Review: `/Users/deniskopylov/.codex/scratch/e02-r14-trust-check-patch-20260928/R14_INDEPENDENT_REVIEW_EB.md@sha256:756706c78398a4eb875d12946c5224aca2d47a12e4383fcd09e18907f14685fb`.
- **R13 builder facade:** integrated at `5f433df89f45f3bf29dd2a5d715985790e421db6` after independent GO for the bounded correction. The Core-root import has the structural removal probe and 23/23 preserving test; see `/Users/deniskopylov/.codex/scratch/e02-r13-builder-facade-20260929/INDEPENDENT_REVIEW_05ecd78f.md@sha256:9cf1eab971b62edc29d82c3e4cdcb44c2802248e8a76703cbc3dccccefa02d9f` and `REVISION_RECEIPT.md@sha256:e09118cab8753feef6bba546f073c75378b32be08a0ab74edda1d33260e0b77d`. This bounds the newly introduced direct Core import edge only; pre-existing builder import edges, full architecture guardrails, broader storage custody and R13/P31 remain open.
- **P41:** the cited four-file broker wave is released but incomplete as tabulated above. Any later test run must freeze its exact inputs for the run; no source edit may touch a tree under test.

### Serialized overlap map and resource cap

| Lane | Exact write set / state | Sequencing |
|---|---|---|
| Root integration/docs | Canonical `codex/e02-r2`, including all package documents and ledger | Root only. Candidates/reviewers do not edit canonical files. |
| R1 migration | The four importer test files listed above | One writer sequentially across the four paths; preserve R11 control assertions; keep every unresolved P41 cell `UNRUN`. |
| R13 graft witness | `test_normative_generation_bridge.py`, exact selector above | Starts only after R1's four-file handoff; never concurrent with R1 on the shared file. |
| R14 | Six source/test files integrated at `ec604e9a9` | No new write lease; its full P41 replay is still pending. |
| R13 builder facade | `builder.py` integrated at `5f433df89` | No separate candidate writer remains; broader pre-existing import edges and custody remain outside this bounded change. |
| P41 broker | Prior 16-cell run released; future receipts in broker scratch | Re-freeze exact source/test inputs for each new run and preserve tree immutability while it runs. |

Resource admission: cap at five light resource-bearing process groups, default four; use a fifth only while at least 20% RAM remains free, targeting 30%. Keep at least 8 GiB free disk. Heavy native suites, full architecture guardrails, wheel builds, and exclusive DuckDB/port/store jobs run alone. Reuse existing environments and the read-only `production_data` link. This is a ceiling, not a claim about current utilization. Only Denis empties Trash.

## Active conditional bridges (2026-09-28; lease updated at `9bd9e8556`)

- At clean canonical `be4713328`, the five queued R1/R13 test files have a bounded pre-edit P41 admission record: 5 files × 4 bases = 20 cells, 9 absent in the corresponding Git trees and 11 present but `UNRUN`. Five older JUnits are historical evidence but 0/11 present cells meet the current reuse verifier. No red is assigned to a candidate from this admission. The exact table, environment key, and disk reason are `/Users/deniskopylov/.codex/scratch/e02-p41-r1-r13-unrun-20260928/ADMISSION.md@sha256:a1981fe4e90849bc1035754dcfe851497039163e6ef7032a928f7549cc3f0701`. The isolated source leases below may proceed under Denis's recorded `UNRUN` contingency; no test is in flight in the canonical tree.

- Root is the only writer of `codex/e02-r2`. The earlier R13/P31 six-path custody repair is integrated at `d103d234c`; its lease is released. Source/test changes below are in separate existing candidate worktrees. Scratch-only reviewers and package-document drafters do not edit either candidate or canonical source.
- R1 controlled candidate bridge: clean `codex/e02-r2-r1-sim-gateway` at `64583b314` is reviewed NO-GO because its served positive stops at missing worker scope and its context route enters the N6 coordinator. The candidate writer owns only `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`, `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py`, `policy-engine/src/polisyos/runtime/quality/cycle_substrate.py`, `policy-engine/tests/unit/runtime/http/test_control_service_di.py`, `policy-engine/tests/unit/runtime/http/test_cycle_substrate_job_execution_binding.py`, and `policy-engine/tests/unit/runtime/quality/test_cycle_substrate.py`. The quality owner source and its mirrored test are the two added paths for the purpose-limited, lease-bound `VerifiedNLJobScope` witness and negative controls; no writer owns `quality/generation_cycle.py` or the acquisition bridge under R1. The served route must be described as candidate-only N6 coordination with actual N4→N5 behavior and observed N9 non-certification, not as an N5-only mechanism. No full user `AccessScope` may be reconstructed from payload markers. The fixture proves routing and custody mechanics only; real DataState source-time, real profile admission and S8 authority remain separate premises. No production provider is appointed by the fixture. A changed write set must be recorded here before another file is edited.
- R1 new mirrored test-file pre-edit census: `test_cycle_substrate.py` is PRESENT at all 4 required bases, with Git blobs `e951dfdf7652ff930bfa381c890862e81f561d5c` at execution base/E02 head/Main and `5d4d75969f95757bf696758df00ef3064087c50b` at integration `9bd9e8556`. These four cells are provisionally `UNRUN` for this lease; a past JUnit is not admitted without exact input/environment reconciliation. The existing `test_control_service_di.py` focused eight-cell wave leaves its E02-head and integration whole-file cells `UNRUN` after the swap resource guard. This is a bounded pre-edit admission under Denis's UNRUN contingency, not a pass→fail classification or R1 closure. The broker will attach a strict-reuse receipt before integration.
- R13/P31 epoch evidence store: clean `codex/e02-r2-r1-candidate` owns only `policy-engine/src/polisyos/runtime/quality/epoch_deployment.py`, `policy-engine/src/polisyos/runtime/quality/chronology_proof.py`, `policy-engine/src/polisyos/core/artifacts/__init__.py`, `policy-engine/tests/unit/runtime/quality/test_epoch_deployment.py`, `policy-engine/tests/unit/runtime/quality/test_semantic_epoch_native_qualification.py`, `policy-engine/tests/unit/runtime/quality/test_chronology_proof.py`, `policy-engine/tests/unit/core/artifacts/test_artifact_store_protocol.py`, and `policy-engine/tests/integration/core_runtime/test_acquisition_world_growth_chain.py`. The first candidate commit `672ad1447` is reviewed NO-GO for the broad P31 property: chronology's policy evidence still uses the raw deployment store. The same runtime-aware owner accessor must feed both production chronology store factories, with a marker-preserving denial of the policy-plane admission blob and a positive scoped read. The Core artifacts facade should expose the already-owned factory/config instead of adding a second Runtime deep import. Root reserves `policy-engine/architecture/public_surface/contract.toml` and its generated public-surface/inventory family for a separate reviewed owner transition; the candidate does not edit them. A guarded store alone does not prove tenant ownership: a tenant custody witness must exercise ambient ownership enforcement and a real tenant scope. This bounded repair does not appoint the native epoch issuer or close production world growth. Review: `/Users/deniskopylov/.codex/scratch/e02-r13-acq01-design-20260928/R13-P31-epoch-store-candidate-review-672ad1447.md@sha256:a113136d012b43666e5f645bd588f50cf7dd334a558e21f60f4b488cd054de6d`.
- These two source leases are file-disjoint. The integration branch, generated-artifact families, governed epochs/receipts, and package documents remain serialized by root. Before integration each candidate needs a property-removal red, a preserving control, whole changed-file replay, and independent review. Run no canonical checkout edit during an in-flight canonical test. Keep at least 8 GiB free disk and 30% free RAM; reuse existing environments and never empty Trash.

## Prior integration coordination (2026-09-28; superseded lease snapshot)

The active R1/R13 write sets are only those under **Active conditional bridges** above. The assignments in this section and every older section below are retained as historical coordination, not concurrent leases.

- Root is the sole writer of `codex/e02-r2`. The DDM lazy-facade contract and its owner-rendered inventory/public-surface projection are integrated; no DDM writer lease remains.
- R13/P31 source/test candidate is frozen on `codex/e02-r2-r1-candidate` for independent review. Its six-path aggregate write set is `core/artifacts/{ownership.py,store.py}`, `scientist/orchestration/workflows/builder.py`, and their three mirrored test files. Root alone applies a reviewed patch; no candidate or reviewer edits canonical. R13 remains open after this bounded custody slice.
- R1 simulated NL candidate is frozen on `codex/e02-r2-r1-sim-gateway` for independent review. Its write set is `runtime/http/services/control/nl_pipeline.py`, `scientist/orchestration/llm/simulated_gateway.py`, and `tests/unit/scientist/orchestration/llm/test_factory.py`. It does not touch the R13 owner files. The explicit N4 context/S8 authority case is outside that candidate and remains open.
- Package ledger, baselines, reports, and decision drafts are root-only canonical writes. Four-base P41 runs freeze the canonical checkout for their entire lifetime; scratch read-only analysis and isolated candidate tests may continue. Limit active test work to measured resource groups, keep at least 8 GiB free and 20–30% RAM free, use the read-only production-data symlink, and never empty Trash.

## R13/P31 owner-level custody slice (2026-09-28; canonical HEAD `e55012e22`)

- Root alone writes `codex/e02-r2`. The clean isolated `codex/e02-r2-r1-candidate` worktree at `/Users/deniskopylov/.codex/worktrees/e02-r2-r1-candidate/polisyos` has the exclusive R13/P31 candidate lease for `policy-engine/src/polisyos/core/artifacts/ownership.py`, `policy-engine/src/polisyos/core/artifacts/store.py`, `policy-engine/src/polisyos/scientist/orchestration/workflows/builder.py`, `policy-engine/tests/unit/core/artifacts/test_artifact_id_serialization_contract.py`, `policy-engine/tests/unit/core/artifacts/test_ownership_history.py`, and `policy-engine/tests/unit/scientist/orchestration/workflows/test_builder_pinning.py`. No other source, test, governed artifact, generated family, plan, register, or package document is leased. The earlier default-store lease is complete at `e55012e22`; this is its owner-level follow-up.
- Property: an ambient-owned filesystem CAS denies unscoped access or mutation of any ID with an artifact-owner, exact-view, or blob-reader claim in the signed v1/v2 ownership index. A unique unclaimed ID still supports ordinary unscoped candidate work. A raw filesystem CAS supplied at the Scientist workflow boundary enters the existing ambient owner, without rebuilding the root or changing canonical content IDs. An already strict `for_tenant()` store and an already guarded runtime store retain their stronger contract and identity. Do not change the global `FileSystemCAS` constructor default in this slice. Its direct raw consumers remain a named bounded residual, with a falsifier, rather than a custody closure claim.
- Test first: tenant A writes through default and supplied raw workflow stores; tenant B and foreign cell cannot read; unscoped known claimed IDs cannot read bytes/metadata, return `has`, enumerate, receive raw paths, supply lineage inputs, attach views, or import them. Keep a property-preserving unclaimed candidate control. Marker-retaining removal probes must turn the scoped raw-owner attachment and no-scope aggregate-claim checks red. A signed v1/v2 query must preserve index and signature bytes exactly; explicit admission alone may migrate history. Cover target ID and manifest inputs on import, or record the smallest uncovered capability and its falsifier under P40.
- Pre-edit four-base whole-file P41: `test_artifact_id_serialization_contract.py` is 5/5 at each base (`raw/p41-custom-20260928T161911Z-78098/results.json@sha256:0ef343ba46b1ba279a8cf262357aaef42f5398eb4abd2c3852f4cc492b101547`); `test_builder_pinning.py` is 15/15 at execution/E02/Main and 17/17 at canonical `e55012e22` (`raw/p41-custom-20260928T162938Z-81584/results.json@sha256:c643790d90628cddb43fbb3190d644f04e0342b57e38f34d99cb967c1e5dffd2`); `test_ownership_history.py` is verified absent on the three older bases and 3/3 at `e55012e22` (`raw/p41-custom-20260928T164030Z-86453/results.json@sha256:d62f6a797cd17a71800e4552c938d1ad28252ce5cf3fe250e4e9defa6991b3d5`). Four additional Scientist workflow files have a 16-cell pre-edit matrix (`raw/p41-custom-20260928T163157Z-83283/results.json@sha256:09c4c28380c4a4878b0f3738204f5579a26b7f5024b6aea95210c479fdb8f8be`): three executable files pass at execution/Main/current with two E02-head reds; the tracing file is all-skipped `UNRUN` at all four bases. Do not call the tracing skip a passing witness.
- Candidate writer commits only after branch-attachment check, runs bounded tests and Ruff, and hands off a frozen diff plus removal/positive receipts for independent review before root integration. Root replays whole touched test files and the served tenant-custody/checkpoint preservation witnesses after integration. Preserve at least 8 GiB free disk and 20–30% free RAM; never empty Trash.

## Current snapshot (2026-09-28; canonical HEAD `764e122e2`)

- Root remains the only writer of `codex/e02-r2`. The isolated R13/P31 default-workflow-store writer may reuse clean `codex/e02-r2-r1-candidate` at `/Users/deniskopylov/.codex/worktrees/e02-r2-r1-candidate/polisyos`. Its exclusive write set is `policy-engine/src/polisyos/scientist/orchestration/workflows/builder.py` and `policy-engine/tests/unit/scientist/orchestration/workflows/test_builder_pinning.py`; no other source, test, generated family, governed artifact, plan, register, or package document is leased. Root alone integrates a reviewed candidate.
- Property: a workflow-created default FileSystemCAS enforces the existing ambient tenant/cell ownership under `tenant_scope`, while unscoped candidate computation and supplied-store identity remain intact. Route through the existing artifact-store owner; do not rebuild a store from a root or change a supplied tenant-bound/guarded store. The property-removal probe must keep marker strings but make a foreign-tenant read succeed and the test red. Independent review must classify any escape using P40 before integration. This slice does not close generic namespaced storage or all of R13.
- Pre-edit whole-file P41 for `test_builder_pinning.py` exists at all four bases with identical test blob and 15/15 passing in each; no common pass→fail. Its manifest is `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260928T160220Z-64918/results.json@sha256:8d7013cc317f790a412e0924b633a85e48fb4991ffe7b35eaa04abd034f4a7b0`; resource verdict passed with approximately 611 MiB peak group RSS and 74% free RAM. Preserve the 8 GiB disk floor and 20–30% free RAM; never empty Trash.

## Prior snapshot (2026-09-28; code/test HEAD `8b7b532dd`; docs HEAD `90eb7e4f8`)

- B198/CAL-06 is integrated at `8b7b532dd`; its candidate source/test and public-surface owner-generation lease is released, with no active B198 writer. Owner sync: `/Users/deniskopylov/.codex/scratch/E02R2_B198_504b9e749/public-surface-owner-sync.log@sha256:3a1c841e27e002f813b631ad3847f17a39a1b8e4dab8a007892ea06d0c5d83c8`.
- Whole-file P41 for `test_propagate_welfare.py` is 4/4: execution 7/7, E02 7/7, Main 7/7, integration 8/8; no common pass→fail. The new identity is `CASE_SET_CHANGED` at the historical bases. Manifest `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260928T153723Z-58057/results.json@sha256:b9cf91ec5fe04714faeea84146d4c807d7ba9fc6e995836e1c9fddea8a97b5b7`.
- Focused suite 30/30; typed-scale removal red, eligibility removal red, restored control 1/1 green. Receipt `/Users/deniskopylov/.codex/scratch/e02-b198-removal-probes-20260928/B198_MARKER_RETAINING_PROBES.md@sha256:1f37c4372c1fc3e59fa2030bd2fa5845375221dd31877a49d252677863bfe45b`. B198 is closed bounded; GE-entry ref/replay, GE matrix admission, and CREDIBLE source-law residuals have no active lease.
- TypeScript gate passed 5 workspace typecheck scripts across 5 workspaces, invoking 7 TypeScript configurations, exit 0: `/Users/deniskopylov/.codex/scratch/e02-b198-tsc-20260928/typecheck-90eb.log@sha256:f71ce568ad9d8538e6c204fa3bf8644c7b0050949518bc1ec51a4b92bc554054`. Root remains sole canonical branch/document writer. Preserve 8 GiB disk and 20–30% RAM reserve; no one empties Trash.

## Prior current snapshot (2026-09-28; code/test HEAD `e0c6623ed`)

- Root is the sole writer of `codex/e02-r2`. R11's isolated candidate lease is released: the independent reachability review found that the default served producer refuses a blocked N6 before a genuine N9 receipt can be persisted; its no-write verdict does not close R11. Receipt: `/Users/deniskopylov/.codex/scratch/e02-r11-served-reachability-20260928/R11_SERVED_REACHABILITY_RECEIPT.md@sha256:a8e50228fd5b58931a56313cb5225ec45c5afa564cd35c60059437cf22219332`.
- The next isolated B198/CAL-06 writer may reuse clean branch `codex/e02-r2-r1-candidate` at `/Users/deniskopylov/.codex/worktrees/e02-r2-r1-candidate/polisyos`. Its exclusive source/test write set is `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py`, `policy-engine/src/polisyos/foundry/uncertainty/__init__.py`, `policy-engine/src/polisyos/foundry/uncertainty/README.md`, `policy-engine/architecture/packages/foundry.toml`, and `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_propagate_welfare.py`. The last two non-test additions are allowed only if the public uncertainty facade needs explicit supported-entrypoint registration; the shared `covariance.extract_std` owner is read-only unless this map is amended. The writer must test-first prove that a typed Normal `std` survives changes only to display level through the welfare consumer, preserve the legacy no-carrier path and non-gating status, and make a marker-retaining removal probe red. A second owner, generated-family edit, governed artifact or epoch is not leased. Root regenerates any affected governed mirror through its owner after reviewed integration and inspects every delta. Independent review precedes root integration.
- Pre-edit welfare whole-file P41 is four present cells, all 7/7 pass with zero case deltas; source/test file blob is identical at all four bases. The one-worker run had peak group RSS 554,912 KiB, no swap growth and at least 72% free memory. Receipt: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260928T142500Z-41302/results.json@sha256:cb94aa5020cf0219de44c2fe22874463743fde6288ad4196c17529e6a0778665`.
- Root owns package documentation and P41. No checkout is edited during a run in that checkout. Maintain at least 8 GiB free disk and 20–30% free RAM; move only verified disposable outputs to Trash, and do not empty it.

## Current snapshot (2026-09-28; code/test HEAD `267636d55`)

- Root remains the sole writer of `codex/e02-r2`. The R1 candidate lease below is released. Its reviewed, test-only delta landed at `267636d55`; the canonical complete recursive file is 27/29, with the two static-denominator reds also observed on Main. The renamed HTTP selector proves only that an explicit N4 without owner context refuses before N4. The original Appendix-A direct/HTTP parity selector is retired pending the selected real N4→N5→S8 owner bridge; no positive owner chain or R1 closure is claimed. Integrated JUnit: `/Users/deniskopylov/.codex/scratch/e02-r1-r13-http-intent-20260928/integrated-recursive-c090.xml@sha256:6848a66c612ef1edbb3fd0952ded252004bc5f97de9efdf8419a9828ea35ebe6`.
- R11 candidate writer lease: the isolated `/Users/deniskopylov/.codex/worktrees/e02-r2-r1-candidate/polisyos` may now edit only `policy-engine/tests/integration/runtime_quality/test_evaluation_safety_promotion_bridge.py` for a served blocked-N6→N9 refusal witness and ordinary-stop preserving control. `generation_cycle.py` is read-only unless a bypass is independently shown and this lease is amended. The writer must use a real same-candidate persisted N9 receipt and keep the authority chain typed; no governed epoch, receipt family, generated artifact, plan, register, or canonical source/test file is leased. The writer hands off a patch and full deciding/removal receipts for independent review before root integration.
- Root owns package documentation and the current-head P41 broker. Candidate and canonical test jobs use separate scratch; no tree is edited during a run in that tree. Keep at least 8 GiB disk free and 20–30% RAM spare. No one empties Trash.

## Prior snapshot (2026-09-28; code/test HEAD `44a7441eb`)

- R1 candidate writer lease (2026-09-28): the isolated, branch-attached `/Users/deniskopylov/.codex/worktrees/e02-r2-r1-candidate/polisyos` starts at documentation commit `9a92e5d89` with code/test bytes from `44a7441eb`. Only `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py` and `policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py` are leased for the simulation-only explicit-N4 over-refusal class. The writer must preserve protected-intent refusal, demonstrate candidate/blocked pre-N9 behavior, run a marker-retaining removal probe and a property-preserving control, and hand off a patch/receipt for independent review. No canonical source/test or generated family is leased; an additional write path requires this map to be updated before editing. The full positive N4→N5→S8 owner bridge remains separate and cannot be asserted from a test-double context.
- Root remains the sole writer of `codex/e02-r2`. The R13 tenant-custody fixture landed at `10315b7b2`; its two-file lease is released. The earlier 12/12 run used `8a09e7f5f` source plus staged test bytes; an exact committed-`44a7441eb` clean-worktree replay now passes the same two complete tenant/WDI files 12/12 (`/Users/deniskopylov/.codex/scratch/e02-r12-n7-integration-20260928/full-clean/tenant-wdi-44a.junit.xml@sha256:23544251f1a80d57f642227d184226281bd97e0b0fc607cecc4b1e0c95d32813`). This does not establish authenticated tenant-ID issuance or B12's dependent-calculation change.
- R12/R13 N7 re-entry landed at `44a7441eb` after independent GO. It changes only `generation_cycle.py` and its mirrored test, and its source/test write lease is released. The integrated three-selector N7/R6 group passed 3/3; the marker-retaining N5-callback removal probe failed as intended, and the restored candidate passed 3/3. The clean exact-head whole generation-cycle file now passes 153/153. Against `10315b7b2`, all 153 identities are common: two N7 cases and one N9 case changed fail→pass, with zero pass→nonpass; the N9 transition is not attributed to R12 because ignored ledger state differs. Comparison: `/Users/deniskopylov/.codex/scratch/e02-44a-cycle-p41-20260928/GENERATION_CYCLE_44A_P41_RECEIPT.md@sha256:597827a3203bc6e52855aa83f4a50dd64ba1f607bf85b8423b402ea186c2fb40`. The local route remains `contract_testing` and cannot issue CGF, N9, or S8 authority from unknown grounding. The changed Appendix-A expectation has a principal decision draft in `DECISION_RECORDS.md`.
- R13-G's complete 2,696-file AST census found no served caller for the root-CAS composed-WMR helper; N5 already uses `PromotionRuntime.store`. The R13-G residual document is corrected and committed at `d06f56981`. The missing served WMR/context bridge and owner-issued NCM remain named blockers; no marker-only helper patch is leased.
- R7/R8 marker-retaining exact-source removal probes are complete in isolated scratch overlays; canonical source/test files were never mutated. The exact-`44a7441eb` live-executor file passes 49/49. The N9 red in the stateful canonical worktree is a stale local ledger-scope hypothesis: its selector passed 1/1 both at `d06f56981` in a clean worktree and at exact `44a7441eb` after moving only that clean worktree's generated ledger to Trash. Four-base P41 and authorized reissue remain separate. Documentation and ledger reconciliation are the only current write work; no source/test file is leased to another writer.
- Generated families, governed epochs/receipts, plans, register and E02 records have no writer. At most four to five measured light processes may run while RAM has at least 20–30% free and disk at least 8 GiB. Completed scratch may move to Trash after verification; no one empties Trash.

## Prior snapshot (2026-09-28; code/test HEAD `6a31548ea`)

- Root is the sole writer of `codex/e02-r2`. R13 N6 source-store custody landed at `065929f51`; the world-growth bridge store-identity fence landed at `6a31548ea`. Those source leases are released. R13 remains open on the served tenant-custody positive path, composed WMR/NCM owner, and full P41 replay.
- The R3 historical test-contract correction landed at `17ba0b7eb` after independent review and a same-head selector/full-file replay. Its `test_generation_source.py` lease is released; the 25-case full file still has parent-present reds, recorded separately.
- The next isolated R13 served-tenant fixture writer owns only `policy-engine/tests/integration/core_runtime/test_acquisition_tenant_custody.py` and `policy-engine/tests/integration/core_runtime/test_acquisition_world_growth_chain.py` in the existing clean-probe checkout. The writer must bind the same valid UUID tenant to the scope and WDI route, retain foreign-tenant refusal, and hand off a test-only patch and red/green receipt. No product UUID guard is leased for change.
- R14's shared route-basis fixture correction landed at `a1875e4c9` with 17/17 and independent review; that lease is released. The R13 tenant-fixture candidate owns only `test_acquisition_tenant_custody.py` and `test_acquisition_world_growth_chain.py` in clean-probe and is frozen for review. R13 ledger/report work is scratch-only. The branch's generated families, plans and debt register have no writer.
- The next R13-G composed-WMR candidate uses the clean isolated `e02-r1-worker-context-20260928/worktree` at `42ac6b4c9`. Its bounded source write set is `intervention_substrate.py`, `credal_reference.py`, `design_generation.py`, `data_state_substrate.py`, `world_model_record.py`, and `runtime/http/services/control/nl_pipeline.py`, plus their mirrored unit/integration tests. It must census callers before editing, wire the existing WMR owner to the exact runtime store and durable scope-bound workspace, preserve candidate N4 under absent NCM, and leave NCM production/admission explicitly missing. It may not edit `generation_cycle.py`, `acquisition_world_growth.py`, either tenant-fixture test, generated families, or any plan/register. If an additional caller requires a source edit, the writer must stop and request a lease update; no second owner or root-built CAS fallback may be added. Candidate files remain isolated until independent review, a removal probe, and root integration.
- Compute admission is at most four to five light test groups, with 20–30% RAM free and 8 GiB disk free. Reuse existing `.venv` and worktrees; `production_data` is read-only and is never copied. Move only verified disposable files to Trash, and do not empty it. No checkout is edited while tests run there.

## Current snapshot addendum (2026-09-28; code/test HEAD `4060a4cc7a2cb455348b162471f848cb02758eda`)

- R13 Fabric storage-custody slice committed at `93affc59bcbeb3c21e015596b05ae6b8787d8e8e`; independent review is bounded GO. Served tenant/session/cache custody and streaming snapshot witnesses are recorded in the Fabric receipt and the B12/B88 ledger additions. B12 remains partial on admitted world-growth effect, producer/journal admission, and four-base P41; B88 remains partial on production identity issuance, exact persisted replay lineage, broader callers, and four-base P41.
- R13 training output-store owner slice committed at `ac3796b6b`; the complete three-file comparison is 23/23 base and 24/24 patched, zero common pass→nonpass, one new owner-store pass. Its bounded receipt and independent GO review are cited in `FINAL_REPORT.md`; it has no established separate finding-level mapping and changes no ledger status.
- R2 pre-N9 deployment-identity recheck committed at `4fae74c22`; six selected tests pass, the marker-retaining removal probe turns both new cases red, and the non-refusal control passes. B30 remains partial; packaged issuer/reissue, source-free positive currentness, and touched-file four-base P41 remain `UNRUN`.
- At code/test HEAD `4060a4cc7`, the workspace TypeScript typecheck passed all five packages (exit 0): `/Users/deniskopylov/.codex/scratch/e02-r2-tsc-4060-20260928/typecheck.log@sha256:f71ce568ad9d8538e6c204fa3bf8644c7b0050949518bc1ec51a4b92bc554054`. Architecture guardrails remain `UNRUN`.
- Root remains the sole canonical writer of `codex/e02-r2`. Active isolated write sequence: the R13 N6 source-store candidate owns `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` and `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py`; the R1 N3 agent owns `policy-engine/src/polisyos/runtime/quality/data_state_substrate.py`, `policy-engine/src/polisyos/runtime/quality/world_model_record.py`, and its N3 test. The R1 served-provider candidate follows the N3 handoff and owns `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`, `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py`, and its HTTP test. LA-018 and LA-053 work remains disjoint and scratch-only. Candidate writes do not enter the canonical tree before review and root integration.
- Completed R13 Fabric/training and R2 pre-N9 integration code/test leases are released. The active scratch leases listed above remain in force; root remains the sole canonical branch writer. This documentation addendum has not run product tests and does not upgrade a finding or class. Full Appendix-A/B/touched-file four-base replay and R13 world-growth/source-run residuals remain incomplete. The following dated snapshots are historical coordination records.

## Prior current snapshot (2026-09-28; code/test HEAD `a59107f3885895324792d47f0d639e136603bd8a`; superseded by current snapshot)

- B88 is integrated at `dfaa31c7a78d9e1f1afcc849d03f3e294981ea27` with a bounded 19/19 two-file served replay witness; it remains partial pending R13 tenant custody, replay lineage, and four-base P41.
- R2 is integrated at `a59107f3885895324792d47f0d639e136603bd8a`: the selected final-target group passed 18/18 and the final source-free wheel semantic-mutation replay passed 1/1. B30/R2 remains partial; the GY-N6 gate is typed `UNRUN` / exit 2, and packaged deployment identity issuer/reissue plus four-base P41 remain unresolved. Receipts are recorded in `BASELINES.md` and the B30 ledger row.
- R13 source changes remain in scratch/review. The 8 GiB free-disk floor remains active; recheck available space with `df -k` before resource-bearing work. Pinned coordination and lease snapshots below refer to earlier heads and are historical.

## Historical source-lease snapshot (2026-09-28; branch HEAD `15c5c40a1`; superseded by current snapshot)

- Root alone writes `codex/e02-r2`; the branch was clean at this snapshot. Scratch candidate authors must not edit the integration tree. The 8 GiB free-disk floor supersedes the historical 10 GiB thresholds below. At this snapshot only 8,443,340 KiB were free, so resource-bearing tests and wheel builds wait for measured margin; source stays frozen during every run. The user may clear Trash after checking it; agents may only move verified disposable items there via terminal `mv`.
- **B88 served replay:** frozen candidate writes `src/polisyos/fabric/connectors/testing/simulator.py` and a new `tests/unit/runtime/http/test_b88_served_replay.py`. No other writer owns these paths. Root will rerun the exact final test plus the complete `tests/unit/fabric/data_plane/test_modes.py` before a B88 commit. This is a bounded served witness; tenant custody remains R13.
- **R2 packaged history V5:** frozen candidate writes `src/polisyos/foundry/methods/catalog/dependency_authority.py`, `hatch.toml`, and `tests/unit/runtime/quality/test_generation_cycle_history.py`. No other active candidate owns them. Root will build the real wheel offline and replay the focused source-free tests before a commit. This does not claim full R2 closure.
- **R13 served ingestion custody:** one scratch writer owns the proposed `fabric/data_plane/modes.py`, `fabric/data_plane/orchestrator.py`, `fabric/ingestion/ingestion_providers.py`, `fabric/ingestion/ingestion.py`, and `runtime/http/services/control/run_lifecycle.py` slice plus its focused mode/served tests. It must freeze and independently review a patch before root applies it. This lease includes connector-cache SQLite tenancy, cursor sidecars, ownership-error projection, and record-mode no-egress failure; no second writer may edit `run_lifecycle.py` until it is handed off.
- **R1 candidate/authority bridge:** read-only design may proceed now. Any new R1 patch that touches `run_lifecycle.py` waits for the R13 handoff; any disjoint `runtime/quality/generation_cycle.py`, `recursive_generation_cycle.py`, or mirrored tests need an exact write-set amendment before a scratch writer starts. Existing positive N4→N5→S8 is not established, so candidate-band work may not assert S8 authority.
- Governed artifact generators, epochs/receipts, the integration branch, and exclusive native handles remain serialized. B88 and R2 candidate patches have disjoint source/test paths, but their resource-bearing verification runs sequentially while disk margin is narrow. Four-base P41 cells still marked `UNRUN` remain `UNRUN`; the user authorized proceeding with repair while preserving that status.

## Historical coordination snapshot (2026-09-28, integration HEAD `0c2910581018642e9f27077d625e9309f5ad84ec`)

- Root is the sole writer of `codex/e02-r2`. The branch was clean at this HEAD. Commits `bac6996df` and `3cc111aa9` landed bounded B73 and STA-01 repairs; `0c2910581` recorded B73 evidence in the 282-row ledger. B73 and STA-01 remain partial; the latter has a confirmed direct `AsyncWorkflowExecutor` timeout-configuration residual. STA-01's exact JUnit and falsifier receipts are in `STA_01_REPAIR.md`; B73's are in `FINAL_REPORT.md` and the current ledger.
- R1's five complete touched test files have a frozen prepatch current-head comparison at `bac6996df`: 356 cases, 325 pass, 20 fail, 11 error. The receipt is `/Users/deniskopylov/.codex/scratch/e02-r1-current-bac-prepatch-20260928/R1_FIVE_FILE_BAC_BASELINE.md@sha256:aea8c52c37c93eeb4e25183bdbbc68428f4257e63f33b4289e104702fd3cacfb`. V2 N4 outcome was blocked on contextless `pass/evaluated` admission; V3 owner-bound outcome and a separate served bridge are in isolated scratch work. Do not edit or test the canonical R1 files until the frozen candidate is reviewed and admitted.
- B111's Pareto owner candidate is isolated in `/Users/deniskopylov/.codex/scratch/e02-r2-b111-candidate-20260928/tree`. V1 was independently blocked on inferred-basis `complete` and v1-history frontier ranking; V2 is in progress. Its write set is Pareto promoter/registry/VOI/objectives and three mirrored test files, disjoint from R1. Its tracked-history census found no committed serialized v1 Pareto payload in 13,422 tracked blobs; deployed histories are not thereby disproved.
- R13's exact active-observation projection is a reviewed bounded candidate at `fba62c46d` in its separate clean worktree, not integrated. It has no served WMR/context consumer. The current world-growth bridge lacks an established canonical-variable-to-policy-slot mapping and a matching snapshot-bound SKG prior. Do not turn the projection into a full R13 closure or fabricate the missing causal relation; the candidate worktree and its receipts remain retained.
- Canonical source is frozen during a root-owned test wave. Last measured free disk was about 8.25 GiB against the 8 GiB floor; reuse the shared `.venv`, the read-only `production_data` symlink, and existing scratch trees. No new full worktree or large wave starts without a fresh disk/RAM check. Up to four or five light process groups are permitted when memory stays 20–30% free; native/exclusive resources and generated families remain serialized. Terminal `mv` may retire only verified-safe completed files to `~/.Trash`; only Denis may empty Trash.

## Prior coordination snapshot (2026-09-28, integration HEAD `782652222cece9899adea0a171c08166544901b9`)

- Canonical integration branch `codex/e02-r2` is clean at committed HEAD `782652222cece9899adea0a171c08166544901b9`. R2 production changes landed at `a877f8abc918ff46f6db2a3f0ae64fb4d07fe856`; the follow-on `782652222` commit changes only the R13 re-entry test double. Root remains the sole branch writer. The R2 whole-file wave is complete at a877; the RES-02 782 wave comprises complete `test_res_02.py` (6/6), complete `test_distributed_tier.py` (8/8), and one CAS stop/reopen selector (1/1), 15/15 total. A separate B73 expected-red probe reproduces persisted state containing `right=2` while `completed_nodes=["left"]`; B73 remains partial pending repair/control. The prior R2 prototype scratch workspace is retired to macOS Trash per root; no active R2 prototype lease remains. Keep candidate writers in scratch and do not edit the canonical tree during any root-owned run.
- Integrated and released leases include WDI/tenant custody (`6a508368`), R13 entry fence (`84ac676f`), RES-02 finding tests (`add75e473`), R4 checker/generation-cycle block (`355225dd`), and R11 V3 test-only block (`1544073dd`). Bounded exact receipts are pinned in `FINAL_REPORT.md`; none is a four-base replay or class closure.
- R11 V3 whole-file result at 154 collected 148 tests: 139 pass / 9 fail / 0 errors or skips, exit 1. Compared with 355, 144 identities are common and there are zero pass→fail outcomes; positive owner-issued N9 remains `UNRUN`. This is historical to 154; R2's later exact comparison is recorded in `FINAL_REPORT.md`.
- R2 commit `a877f8abc` distinguishes a census failure from unavailable identity. At that head, `test_generation_cycle.py` was 145/149 with four reds; compared with 154, 148 identities had zero pass→fail, five fail→pass, four fail→fail, plus one new passing removal/control case. `test_generation_cycle_history.py` was 26/26. R2 remains partial: packaged N6 issuer, positive N9 and touched-file four-base replay are `UNRUN`. R13 test-double correction `782652222` passed its focused selector 1/1; no whole-file rerun is claimed. Receipts are in `FINAL_REPORT.md`.
- R1 default-world, served-context and generic time-scope candidates remain BLOCKed and unapplied. The current served unknown-scope path exits before the suspected fixed-UA API fallback; API production reachability remains under investigation. R9 serializer proposals remain scratch-only after independent P07 BLOCKs. R12 planner strangle passed at 154, but its N7 synthetic-receipt/real-grounding residual folds into R13 canonical world growth; no runtime patch is claimed.
- The add75 ledger/N source-audit snapshot plus subsequent bounded tests remains incomplete P41 evidence. R4 `--check --output-format json` at 355 returns typed `UNRUN`/exit 2, historical replay passes, N9 callbacks/sessions are zero, and candidate/receipt denominators are null. Full four-base/touched-file replay and architecture guardrails remain `UNRUN`.
- The earlier coordination snapshot of about 16 GiB free disk and 56% free RAM is historical and superseded. A fresh `df -k` measurement at clean code HEAD `782652222` on 2026-09-27 22:01 UTC reported 9,235,008 KiB free (about 8.81 GiB), only about 0.81 GiB above the 8 GiB floor. Recheck disk and RAM before any heavy replay; admit up to four or five resource-bearing process groups only if a fresh measurement supports the requested headroom. Serialize exclusive native resources, governed artifacts/epochs, fixed ports and the canonical integration branch. Reuse the shared `.venv` and read-only `production_data` symlink. Never edit a source tree while its tests are in flight.

## Historical coordination and evidence snapshot (2026-09-27)

- Root integration is the sole writer of `codex/e02-r2`. The last observed branch pointer during this revision is `768ef3ca1400663f3667baa0069481019ad14878`; that pointer is context only, not the source of every status below. The report/lease patch base is the unchanged pair of document blobs at `5b215d430` (`FINAL_REPORT.md@sha256:73151733f621981234eb4f8fe5d5be081d2cf5b2fefa1143bb5c8f7a138a6728`, `WRITE_LEASES.md@sha256:9d470ae44c3589aa9668baddb4d68cfe46a9d70a5d9fdfaa91f7edc7744d0e71`).
- Evidence pins are intentionally independent: code through `6c7168566d51b22a4de8c0895c18291b3c697ca4`; `BASELINES.md` at `cfcf5ff1caff41c91efdc10f50c59eddaf7f424b` (`sha256:47faae4a26c59d111d9d5fa921c9cc627a0e82ae206b76c4cdd94d80a881a9c2`); ledger and triage at `da3b395f356b4581f1920fb520973ab5117a974d`; `CROSSWALK.md` at `5b215d4302525d927e42d2d289fafc7d72c46d52`; R5 decision addendum at `0fcc58c3c0ceb92723a8b33650b55e19d3b22ed6`. The `6f5b6f613` baseline addendum and any later changes are outside the pinned baseline/report snapshot; `9c989fbe8` is likewise beyond the report code cutoff. Do not describe this document as latest branch status.
- The source tree is frozen during tests. The resource note used for this coordination snapshot recorded about 10.21 GiB free against the 10 GiB hard reserve; serialize test jobs until a fresh measurement confirms more disk and memory headroom. Preserve the root's integration lease, read-only production-data symlink, and existing test receipts.
- R1 commit `5ea4b1a18` has the 27/27 guarded current-job witness, but the 2,696-file source census found no production composition caller for the context owner; the served positive chain remains unestablished. Census `/Users/deniskopylov/.codex/scratch/e02-r2-r1-owner-caller-census-6c716856.md@sha256:18091997f95d5822ac60e242e7cee3aade2e685e92e975ff91323a60b5a27bed`.
- R2 frozen-history replay is committed at `b363204ba` with 22/22; source-free currentness and the authorized package issuer remain `UNRUN`. The new standalone-reader follow-up exists only in a tiny scratch tree and owns `runtime/quality/generation_cycle.py` plus the new reader owner. Sequence it before any future R11 edit to that shared module; no shared lease is currently held for it.
- R5 commit `f7d66883f` has corrected integrated 28/28 evidence. Denis's non-simulation fail-closed direction is recorded in the R5 addendum; positive DataTrust and per-active-basis work remain open. Whole-file `test_modes.py` is 15/15 but not a four-base replay.
- R11 frozen v6 candidate `/Users/deniskopylov/.codex/scratch/e02-r11-owner-admission-20260927/R11_BLOCKED_N6_CANDIDATE_v6.patch@sha256:d5f27d3046eba8064bb383c762d5a45b6ddf8932c59a6a82dc2b8b1675f286d4` released its `generation_cycle.py` lease. Its blocked→N9 property replay is `UNRUN`: the test produced and replayed an owner receipt with different `repo_root` inputs, so it failed before exercising the predicate. Frozen result `/Users/deniskopylov/.codex/scratch/e02-r11-owner-admission-20260927/R11_V6_FROZEN_RESULT_AND_NEXT_STEP.md@sha256:16b818baa00c8c78da8e61806c3667e89444621e1fd2ab84d08f38a81f567246`; root diagnosis `/Users/deniskopylov/.codex/scratch/e02-r11-owner-admission-20260927/R11_V6_OWNER_REPLAY_ROOT_DIAGNOSIS.md@sha256:a9a4fc9707fe9f8b6896a2a2e2f53483a32a3a8e75ae4b999f468b01a0eab6d8`. Keep it separate from the earlier committed bounded 7/7 guard and 2/2 persisted-source witness; do not count it as a new pass/fail.
- The R13-L5 hash candidate named in the earlier dispatch landed at `9c989fbe8` after the report code cutoff, changing `core/contracts/epoch.py`, `substrate_registry.py`, and `test_substrate_registry.py` with a recorded 2/2 witness. Its scratch write lease is released; its effect on the earlier native diagnostic and ledger row remains to be reconciled. Remaining scratch-only candidate write sets are serialized by owner: R9 claim-root work owns `head_index.py` and its test; R9 public-record work owns two governance files and their tests; R14 WS-2D owns the release-ledger file and test. These candidates are not integrated or independently verified by this lease note.
- The pinned ledger at `da3b395f` is 282 rows: 2 closed / 268 partial / 11 held / 1 open. The pinned P triage is 84 engineering / 16 principal decisions / 18 typed blockers. The separate 5b crosswalk has 291 memberships, 77 GY scopes, 22 Atlas scopes and 74 live A/B rows; 35 edges across 28 findings cover 36 membership-target cells, leaving 50,307 membership-target and 48,751 distinct-pair opportunities without admitted edges. Exact file hashes are in `FINAL_REPORT.md`.
- Commit `6c7168566` bounds B72 Ray outcome-status transport: 79 pass / 1 Temporal skip over 80 postpatch outcomes, versus 65 pass / one Ray failure / one Temporal skip over 67 prepatch outcomes; 67 common identities have no pass-to-fail. B72 is partial in the pinned ledger, Temporal remains skipped, and B73 atomicity remains open. The cfcf baseline pin is not the later `6f5b6f613` version.
- The earlier lease sections below are retained as historical records. Their “active” labels and present-tense language describe the snapshot at their named commit, not the current write allocation. Shared-branch edits remain serialized under the root's lease; candidates and reviews stay in scratch until explicitly admitted. No one edits the tree while its tests are in flight.

## Historical lease snapshots (not active)

### Lease snapshot at `43d4f4783` (2026-09-27)

- The root integrator alone writes `codex/e02-r2`. Its committed HEAD is
  `43d4f4783`; a 16-path R5 v6 candidate is dirty in the shared tree. No
  agent may write or test this tree while the root integrates a reviewed class.
  R5's v10 work and test source are isolated in
  `/Users/deniskopylov/.codex/scratch/e02-r5-owner-candidate-20260926/tree`.
  The 14/14 v9 wave is provisional; v10 has a 5/5 focused green after two
  property-red owner-scope probes. It still needs a frozen delta, independent
  review, B88 preservation check, integration replay, and a class commit.
- R11's sole writer uses branch `codex/e02-r11-owner-admission-candidate` in
  `/Users/deniskopylov/.codex/scratch/e02-r11-owner-admission-20260927/polisyos`.
  Its lease is the typed blocked-N6 admission predicate, persisted EvalSafety
  reader and public projection/tests. The R1-dependent served fixture fails
  before R11's property; the candidate must keep its independent persisted
  owner witness. R11 follows R5 on shared generation/consumer files.
- B72/B73's sole writer uses branch
  `codex/e02-r2-b72-distributed-status-candidate` in
  `/Users/deniskopylov/.codex/scratch/e02-b72-distributed-status-20260927/polisyos`.
  Its lease is the existing distributed `NodeOutcome`/codec, Temporal and Ray
  merge/checkpoint/report consumers and mirrored tests. It does not edit R5,
  R11 or R13 sources. An independent reviewer checks skipped/failing native
  results and status-blind old cache/checkpoint admission.
- R13 revised-basis WDI's sole writer uses branch
  `codex/e02-r2-r13-basis-candidate` in
  `/Users/deniskopylov/.codex/scratch/e02-r13-wdi-basis-20260927/polisyos`.
  Its lease is `runtime/http/services/acquisition_surface_execution.py` and
  the actual WDI/native-growth integration test. It must select jurisdiction
  and year from verified revised basis B, retain subject S, and refuse an
  unauthorized B before egress. This is separate from R13-G's absent NCM
  producer and R9 selected-view residual. No test launches below 11 GiB free.
- R1's reviewed `b396d1...` patch is only a current-job identity prerequisite
  with 27/27 and a removal-red receipt. The later `21a050...` import variant
  is NO-GO on Python 3.14. Neither proves the principal's selected positive
  N4→N5→S8 path; an owner-issued, scope-grounded profile and production caller
  are still missing. R1 integration follows R5 in the shared store/context
  files. R2's v3 history-only scratch slice has 22/22 current-tree replay,
  while source-free currentness and authorized deployment census remain UNRUN;
  a superseded synthetic development fixture from Git history is not a
  standing authority claim and does not justify a blanket compatibility
  migration. R2 follows R5 on `generation_cycle.py`.
- H14 and N18 ledger writers work in scratch only. Their combined 282-row
  JSON/Markdown candidate must correct B219's stale test path and receive an
  independent evidence review before integration. The principal's latest
  direction is to avoid broad old/external compatibility work without a live
  E02 or custody purpose. `WRITE_LEASES.md` is this coordination record; plans,
  the debt register and excluded E02 records stay untouched.
- P41 has a complete E02-head CYC-05 whole-file cell (21/21), and the same
  workspace-loop test-source blob has 17 pass/1 inherited fail on the E02
  execution base, E02 head and main. The final integration-head cell and full
  21-file Appendix A/B matrix remain UNRUN. Source tests and generated families
  are frozen during their own runs. At most four or five measured light process
  groups may run if memory remains 20–30% free and disk stays at least 10 GiB;
  heavy native jobs are exclusive. Current disk is about 10.9 GiB, so new
  test waves pause below an 11 GiB launch margin. Production data remains a
  read-only symlink; no one copies it or empties macOS Trash.

### Lease snapshot after `1ed0df830` (2026-09-26)

- The root integrator alone writes `codex/e02-r2`. The DFK H14 owner-decision
  ledger correction is committed; P118 triage must be rebuilt on this head
  before its overlapping JSON/Markdown/CROSSWALK files can be integrated.
- The combined R2 v4 currentness patch is **NO-GO for integration** while its
  N6 owner issuer is absent and its census rule disagrees with the provisional
  owner. It would make positive N9/S8 witnesses refuse. The history author is
  extracting a history-only v1–v3 replay slice that leaves the live v3
  producer, currentness and S8 unchanged. The separate fixture-entry guard
  remains scratch-only and cannot itself claim source-route or package PASS.
- R1's first versioned-slot patch is held: its global default-v2 change can
  reinterpret unversioned persisted DesignProblems. The revised grammar must
  keep generic default v1, make the current NL compiler explicitly emit v2,
  and regenerate its schema only through the declared owner. R5 takes the
  overlapping `run_lifecycle.py` and `generation_cycle.py` lease before R1's
  served context bridge. R5 must retain a positive N5 computation path for
  `simulate_only` while stopping before S8 value choice or publication.
- R11 public-OWR test v3 is **NO-GO**: forcing `stop` over a
  `search_ceiling_repair_required` terminal failed before projection. Its
  writer is replacing that setup with two owner-produced runs. CYC-03/B28's
  first corrected test bundle needs exact patch-to-JUnit reconciliation.
  R13's source-occurrence resolver patch is scratch-only, owns
  `generation_source.py` and its mirrored test, and must not change hashed
  handoff schemas or the overlapping `generation_cycle.py` lease.
- Strict Appendix A/B current cells remain 42 completed JUnit / 20 absent /
  22 present UNRUN (21 files × 4 bases). Shared tests and shared edits are
  serialized. Scratch tests may use a second light process group while free
  RAM stays at least 20–30% and disk above 10 GiB. No generated families,
  governed epochs, receipts or production data are restamped or copied.

### Lease snapshot after `95f082bfd` (2026-09-26)

- The root integrator alone writes `codex/e02-r2`. The R2 package-issuer
  decision draft is committed; no owner or epoch reissue is authorized.
- R2's first owner candidate is **NO-GO for class-wide PASS**. An unlisted
  served sibling can call `run_fixture` yet be excluded from its fixed-root
  import closure. The independent review is
  `/Users/deniskopylov/.codex/scratch/e02-r2-owner-attestation-final-20260926/INDEPENDENT_REVIEW.md@sha256:252ff01a35c1da460c13b459aa589574fe42a408a5eb80ea106d6a93e2d7f085`.
  A widened all-source candidate catches unlisted direct/alias siblings but
  still returns PASS for an opaque computed `getattr` route outside the fixed
  closure. This is the second finding of the same P38/P40 class: no more
  per-route scanner patches; seek a structural owner guard or declare a
  bounded residual. Package-only currentness remains `UNRUN` without an
  appointed issuer.
- The R2 history/currentness patch must be independently admissible while the
  owner remains `UNRUN`: its GY checker owner import is being made lazy, and a
  frozen v1–v3 `CandidateLever.target_slot` constraint is being added. R1 owns
  only `design_problem.py` and mirrored tests until that history lease lands;
  qualified-slot grammar cannot silently widen historical v3 validation.
- R5 owns the isolated five-band HTTP/quality dispatch candidate. Its earlier
  v3 remains **NO-GO**; no R5 source is in the integration tree. The R1 served
  context bridge follows R5 in overlapping HTTP lifecycle files. R11's public
  OWR audit found the existing blocked-run validator boundary and prepared a
  test-only scratch candidate; do not add a duplicate runtime gate without a
  failing property witness.
- The strict current Appendix A/B denominator remains 21 files × 4 bases:
  42 completed JUnit cells, 20 verified absent paths, 22 present `UNRUN`.
  Small test groups may run concurrently in separate frozen trees while disk
  stays above 10 GiB and free RAM above 20–30%; no tree is edited during its
  own run. The full matrix, generated families, guarded epochs, and native
  jobs remain queued for source freeze and adequate disk. Only Denis empties
  macOS Trash.

### Lease snapshot at `ce54d6f16` (2026-09-26)

- The root integrator is the sole writer to `codex/e02-r2`; the branch is clean.
  The R11 S8 bounded repair and H ledger refinements are committed. The strict
  current four-base P41 denominator is 21 files × 4 = 84 cells: 42 completed
  JUnit cells, 20 missing paths and 22 present `UNRUN`, as reconciled in
  `BASELINES.md`. Selected green tests do not fill whole-file cells.
- R5 v3 is **NO-GO** after independent review: DataTrust labels still route to
  EvalSafety, malformed jobs remain pending before worker refusal, and sealed
  route authorization is not bound to the durable job. Its writer owns a new
  five-band dispatch candidate only in scratch; it must preserve candidate and
  simulate-only work, represent missing DataTrust bridge as typed limitation,
  and prove served permission consumption. Do not apply v3 to the branch.
- R1's full scratch worktree owns the job-scoped context producer and served
  N4→N5 seam. Its write set includes the existing HTTP composition/lifecycle,
  a narrow context owner, `design_problem.py` for exact qualified slot syntax,
  and mirrored tests. It follows R5 in the shared `run_lifecycle.py` lease.
  Owner-admitted population/time profile and current S8 value authority are not
  present on the production path; a test fixture cannot grant general S8 authority.
- R2 has frozen scratch owner-only and historical-schema candidates. The owner
  census has a bounded source-tree removal probe; its exact patch is under
  review. Package-only N6 authority remains `UNRUN`: no appointed build/deploy
  issuer or installed attestation binds the route census to canonical loaded
  code and lock. Integrate only a compatible, reviewed combined delta, preserve
  v1–v3 historical bytes, and keep the package limitation explicit.
- Disk is near 11 GiB free, just above the mandatory 10 GiB reserve. Do not
  create a new worktree/environment or start an unbounded test. Reuse the
  existing venv and read-only production-data symlink. Four or five measured
  light process groups may run only with 20–30% RAM free and sufficient disk;
  heavy native tests and the architecture guardrail require a larger margin.
  No tree is edited while a test reads it. Only the user empties macOS Trash.

### Lease snapshot at `341985355` (2026-09-26)

- The root integrator is the only writer to `codex/e02-r2`; the branch was clean
  after the reviewed R11 S8 commit. R11's bounded S8 guard passed its direct
  N6→CAS→S8 owner test 2/2 and a marker-retaining removal probe. It does not
  close the served R1 path or all R11 consumers. The earlier HTTP fixture edits
  that failed at R1 setup were preserved as a scratch patch and removed from
  the integration tree before this commit.
- R5's widened protected-intent gate owns only its isolated scratch candidate;
  its independent review and removal receipt precede any integration edit to
  `runtime/http/services/control/run_lifecycle.py` or recursive runtime tests.
  R1's owner-backed N4→N5 candidate is in a separate full scratch worktree and
  follows R5 on overlapping HTTP lifecycle files. Its writer must carry an
  owner-admitted profile and the runtime-supplied tenant store; absence remains
  a typed candidate limitation, not an S8 authority claim.
- R2 has two scratch-only writers: deployment-identity route attestation and
  v4 historical schema/currentness. They share an explicit owner API and are
  sequenced before one combined independent review and integration into
  `runtime/quality/generation_cycle.py`. The old three-file NO-GO prototype was
  reversed and preserved in scratch. The R2 route-removal and unresolved-call
  probes are required before admission; an UNRUN census cannot grant authority.
- H/N ledger patches are scratch-only until the integrator validates each exact
  row change, 282-row denominator and Markdown JSON digest. The R14 P41 broker
  is read-only; it may inventory receipts but not classify an unrun cell green.
- At most four or five measured light test groups may run while retaining
  20–30% free RAM and 10 GiB free disk. Heavy native jobs and the full
  architecture guardrail are exclusive. The R11 test wave is complete; R5's
  removal probe runs only in its scratch tree. No tree is edited during a test
  against that tree. Production data stays a read-only symlink, no branch is
  pushed or merged into main, and only the user empties macOS Trash.

### Historical lease snapshot at `02b7f5e3c` (2026-09-26; superseded by a877f8abc)

- At this dated snapshot, the root integrator was the only writer to `codex/e02-r2`. Three uncommitted R2 prototype files were owned by root: `generation_cycle.py`, `recursive_generation_cycle.py`, and `test_generation_cycle.py`; the candidate was then marked **NO-GO** pending a canonical deployment identity/N6 route attestation. This is historical coordination, not an active lease. R2's bounded reviewed repair later committed at `a877f8abc`; root reports the prototype scratch workspace was retired to macOS Trash, with branch history preserved. The old patch remains a historical artifact at `/Users/deniskopylov/.codex/scratch/e02-r2-currentness-prototype-20260926/NO_GO_PROTOTYPE.patch@sha256:09a74c989dc53868d2bfcf6cbb19bdab0f2be868322c94a0eeb2deb6755447b5`.
- R2 confidence-ledger attestation and v4 history/schema authors work only in
  scratch against the committed head. They share the R2 interface but do not
  edit the integration tree. The root integrates one reviewed combined delta,
  verifies historical replay and the served authority/candidate split, then
  commits the class. A separate independent reviewer examines that combined
  delta before integration.
- R14 guardrail interruption has a four-file scratch patch touching only
  `tools/cli.py`, `tools/devx/architecture/guardrails.py`, and their mirrored
  repository-quality tests. Its second review found a same-class run-cursor
  escape; the author is widening that one mechanism. Admit it only after a
  delta review and marker-retaining removal probes. The full guardrail is
  deferred until source is frozen and disk remains at least 13 GiB free.
- R11 S8 blocked-run work owns only `value_choice_provenance.py` and its
  normative consumer test in scratch, behind R2's schema handoff. B88's replay
  mode candidate owns `run_lifecycle.py` before the R5 durable-intent candidate;
  R5 stays read-only on that shared source until B88 is integrated. These
  candidates do not write the integration tree or each other's scratch files.
- Limit measured test process groups to four or five light jobs while retaining
  20–30% RAM and 10 GiB free disk. Heavy native jobs and the full guardrail are
  exclusive. Production data remains a read-only symlink; never copy or write it.
  No source tree is edited during its test run. No branch is pushed or merged to
  main, and only the user empties macOS Trash.

### Handoff snapshot after `0c80c296c` (2026-09-26; supersedes older snapshots below)

- The root integrator remains the sole writer of `codex/e02-r2`; the branch is
  clean at this handoff. R13-G is committed as a **bounded residual**, not a
  positive NCM capability. Its 2,905-path/2,695-Python census found no
  production NCM writer or selected-view WMR reference. The missing owner,
  versioned reference, scope-bound cache and served witness are recorded in
  `R13_G_RESIDUAL.md`. The isolated candidate's citation was corrected and
  independently reviewed before integration. R13 as a whole remains open.
- R13-F owns only the synthetic `contract_testing` ACQ-01 route-store helper in
  `generation_cycle.py` and its `test_acq_01.py` fixture. Its candidate is
  scratch-only and must pass review, a wrong-store negative, a candidate control,
  and a marker-retaining removal probe before integration. R1's served unknown
  scope patch is likewise scratch-only; principal option A still requires a
  positive owner-bound N4→N5→S8 witness. No other agent writes shared source.
- R2 history-owner work is scratch-only and overlaps `generation_cycle.py`;
  integrate only after the R13-F lease and independent review. H/N work stays
  in scratch until exact evidence and citation review. The strict 21-file
  four-base baseline and touched-file replay remain incomplete.
- Admit at most four to five measured light test groups, preserving 20–30% free
  RAM and at least 10 GiB disk. Heavy native jobs are exclusive. Never edit a
  tree during its tests, copy or write `production_data`, restamp governed
  artifacts, or empty macOS Trash.

### Handoff snapshot after `5619eae65` (2026-09-26; supersedes older snapshots below)

- The root integrator remains the sole writer of `codex/e02-r2`; it is clean at
  this handoff. R13-D is committed at `ea422219b` with exact N5/N8 runtime-store
  continuity, nine focused passes, removal-red probes, and zero pass→fail in
  its two whole-file slice-base comparisons. Persistent acquisition/parent
  reds reproduce at the slice base, but strict P41 ownership is
  `not_established`, not inherited. R13-D does not close R13.
- The R2 confidence-ledger **leaf** identity boundary is committed at
  `5619eae65`: integrated 8/8, Ruff PASS, installed identity absence typed
  `UNRUN`. It does not establish ordinary source-free package import or N6
  history replay. The scratch eager-initializer attempt is NO-GO under P40;
  the dedicated history-owner candidate now owns only its own scratch files.
- R13-G has the isolated writer branch `codex/e02-r13-g-candidate` at
  `/Users/deniskopylov/.codex/worktrees/e02-r13-g-candidate/polisyos`, starting
  from `ea422219b`. It is the sole writer there. Its write set is the existing
  composed-WMR producer/reader and named HTTP runtime-store handoff; no NCM
  producer is appointed, so it must not synthesize one or claim a positive
  served NCM result. It must finish independent review and focused tests before
  any application to the integration branch. This candidate tree shares the
  read-only production-data symlink and existing `.venv` by symlink.
- R1's selector/profile bridge is scratch-only. The principal chose the real
  owner-bound N4→N5→S8 path for the old normative fixtures. A bounded
  candidate-only change may be reviewed separately but does not discharge
  that choice. Its source lease must follow R13-G's WMR/store handoff because
  both touch `intervention_substrate.py` and HTTP composition. R2 history-owner
  work also overlaps `generation_cycle.py` and waits for a clean integration
  lease; no scratch agent writes the shared tree.
- H14 and N18 record reconciliation runs in scratch without heavy tests.
  The shared branch has no H/N ledger edit admitted yet. The full 21-file
  four-base matrix, all touched-file replay, R2 packaged history, R1 positive
  S8, and R13 WMR/NCM custody remain explicit open gates.
- Resource admission: at most four to five measured test groups, at least
  20–30% RAM free and 10 GiB free disk. Current available disk was about
  12.4 GiB after the R13-G worktree; new worktrees/environments require a
  fresh `df` check. Reuse `.venv`, never copy or write `production_data`, and
  never edit a tree under test. Trash may receive retired worktrees, but only
  the user empties it.

### Handoff snapshot after `d76fbf022` (2026-09-26; supersedes older snapshots below)

- The root integrator is the sole writer of `codex/e02-r2`. R13-E is committed at
  `d782e7ea1`: the supplied Foundry store and selected CAS view pass the integrated
  PLG-03 file (6/6). Runtime store injection still has no production caller in that
  plugin. The shared tree was clean when this handoff was written.
- **Next shared source lease: R13-D**, then R13-F/G, then R2 consumer work that
  also edits `runtime/quality/generation_cycle.py`. R13-D owns that file,
  `recursive_generation_cycle.py`, `test_cyc_02.py`, and `test_acq_01.py` in an
  isolated scratch candidate. Its first patch is not admitted as-is: moving the
  NCM reader to the runtime store while the composed-WMR owner still writes to a
  root store would split producer and reader. The author is preparing a bounded
  N5/N8 revision; independent delta review must precede integration. R13-F's
  contract-only route store and R2's currentness consumer wait for that lease.
- R1's target-scope profile is a scratch-only candidate. Its existing write set is
  `data_state_substrate.py`, `world_model_record.py`, HTTP control generation/lifecycle,
  and their tests. It lacks a production job producer/consumer bridge and a served
  N4→N5 witness; protected S8 still requires an appointed scope issuer and current
  evidence. Independent review is NO-GO for completed R1; the profile DTO also
  advertises arbitrary scope while its WMR builder remains fixed to UA. Do not
  integrate it as a completed R1 capability. The R2 cold-start
  package-identity candidate remains scratch-only and cannot grant authority from
  a synthetic manifest or an UNRUN N6 census.
- **P41 test-origin correction:** the first supplementary R13-C four-base wave
  used a relative test path from `/Users/deniskopylov/polisyos` (the 78187878e
  execution checkout) while importing source from each target checkout. Its
  execution-base cell used matching inputs; its E02/main/current cells do not
  establish those bases' test outcomes. The corrected harness uses an absolute
  target test path and checks every collected item's path and Git blob. The broker
  runs historical trees separately; current-head tests wait for the next source
  freeze. Preserve the invalid receipts with their `UNRUN` attribution. The
  corrected three-base history and 364-module R14 denominator are committed in
  `BASELINES.md` at `d76fbf022`; neither is a current-head green replay.
- B72 and B111 candidates are reviewed or under review in isolated scratch and
  wait behind the R classes. Keep no more than four or five measured test process
  groups, at least 20–30% RAM free and 10 GiB disk free. Never edit a tree during
  its test, copy or write `production_data`, reissue governed artifacts without an
  authorized transition, or empty macOS Trash.

### Handoff snapshot at `ff07e89fa` (supersedes older snapshots below)

- The root integrator is the sole writer of `codex/e02-r2`. R1's narrow served
  N4 terminal repair is committed at `679f096e3`; its reviewed decision-draft
  correction is `b14af08ca`. The 282-row ledger reconciliation is `ff07e89fa`.
  These commits do not close the pending principal choices or the remaining
  four-base `UNRUN` cells.
- The shared `runtime/quality/generation_cycle.py` lease belongs to **R2 history**.
  Its uncommitted prototype is frozen at SHA-256
  `a7cc9cf9be1aced16a5a58071abaf9ea0eb4c733968ea1547f0916c56fc542ea`;
  its untracked history test is frozen at SHA-256
  `8cd5afb970c33e2bc177376169976178a8fac0087b2dde1615acfaa51faaf36c`.
  A scratch candidate is being built from the complete historical typed graph;
  no one else edits these shared files. The separate R2 deployment-identity
  candidate also touches `generation_cycle.py`, `confidence_ledger.py`, and
  `promotion_sequence.py`; it waits for history handoff, compatibility review,
  and test-first admission. Do not apply its earlier six-file patch unchanged.
- R13's supplied-store/world-growth candidate and R11's VOI-status candidate
  remain scratch-only. Their `generation_cycle.py` edits follow R2 in that order.
  R11's EIG-per-USD threshold was rejected in independent review because its
  units are not established. H/N agents own read-only probes and scratch patches,
  not the integration tree. The reviewed ledger documentation patch has already
  landed; further ledger edits require new SHA-link reconciliation.
- Test jobs may use four to five measured process groups while preserving at
  least 20–30% RAM headroom and 10 GiB free disk; native/high-RSS jobs remain
  exclusive. No shared tree edits while a test reads it. Reuse the existing
  offline `.venv` and the read-only `production_data` symlink. No governed
  artifact reissue, branch publication, or Trash emptying is authorized here.

### Handoff snapshot at `0ee329300` (supersedes every older snapshot below)

- The sole integration writer owns `codex/e02-r2`. R1/R5 is merged at
  `8b748e334`; the R1 reader/profile integration correction is committed at
  `d4c5ae777`. Its selected-view removal probe is red and the scoped served
  control is green. R1/R5 remain bounded: the current whole-file
  `test_control_service_di.py` has 32 passes and six failures. Five of 30
  node IDs shared with the E02 execution base and main passed there and fail
  here; the sixth failing node was added later. R1 class design is active.
  The passed
  `test_generation_source.py` cases have zero new main-pass-to-head-fail among
  17 shared node IDs; its inherited failures remain recorded separately.
- R1 follow-up design is read-only/scratch. It owns the HTTP candidate/context
  boundary and may propose tests, but no agent writes the integration tree.
  R2-History v8 is scratch-only and next in the shared
  `runtime/quality/generation_cycle.py` and EvalSafety lease. R13 supplied-store
  handoff remains scratch-only; its `generation_cycle.py` changes follow R2.
  R11 remains a principal decision draft on blocked/N9 semantics. Apply one
  reviewed class delta at a time; do not edit any tree under an active test.
- The four-base `BASELINES.md` addendum at `0ee329300` distinguishes the original
  Phase 0 column from later current heads. It does not claim current-head
  21-file completion. The full changed-test union is a path-presence census,
  not a test result; the later R1 whole-file receipts must be appended after
  their casewise reconciliation.
- One measured R1 full-file job has approached 5.52 GiB RSS, so native and
  unmeasured jobs remain exclusive. Lightweight measured logic tests may run
  in parallel only while preserving 20–30% RAM headroom. Keep at least 10 GiB
  available disk. Reuse the existing `.venv` and the read-only production-data
  symlink; never copy production data or restamp governed artifacts.

### Handoff snapshot at `62d9456d4` (supersedes earlier snapshots below)

- The sole integration writer owns `codex/e02-r2`. R7's journal-owned live permit
  scope is committed at `349c6e3e7`; R9's honest CAS view and v1 ownership-history
  candidate was independently reviewed and merged at `62d9456d4`. On that
  merge head the scoped CAS suite passed 69/69 and five exact Appendix A/B CAS
  selectors passed. R9 remains bounded partial for 252 selector-loss-possible
  calls in 85 source files; these are a census, not 252 proven failures.
- R1/R5 owns only its isolated candidate branch `codex/e02-r1-r5-candidate` at
  `8b618f85f`. Its scoped and unknown-scope served N4 selectors pass, as do the
  focused mode matrix and exact R5 selector. It is **not admitted for merge**
  until marker-retaining R1 and R5 removal probes are decisive and independent
  delta review completes. The support-file whole-file comparison is running
  in that isolated tree. Do not write its files from the integration tree.
- R2 remains a scratch v7 design/test-first task, with no source writer lease.
  R13 remains a reviewed store/world-growth plan with no source writer lease.
  R11 is held for a principal decision on blocked/N9 semantics. R7's postcommit
  review is GO for its bounded scope; its current-head whole-file P41 and the
  architecture guardrail rerun remain open.
- The baseline broker owns test admission. A measured R1 served run uses about
  5.2 GiB RSS, and the E02 whole-file control test reached 5.1 GiB. Treat these
  and other unmeasured native jobs as exclusive memory groups. A prior overlap
  briefly left about 13% physical RAM free; subsequent heavy runs are serialized.
  Keep at least 30% physical RAM free and 10 GiB available disk. No tree is
  edited during a run against that tree. The current strict Appendix A/B
  baseline still has `UNRUN` cells; do not infer a green four-base gate.

## Current code admission after the principal's 2026-09-25 direction

The principal directed the lane to move to code with minimal, informative
resource-bounded tests. The frozen v10 normative replay was stopped with SIGINT,
quiesced, and reconciled before the first R10 source edit. Its execution base and
main passed 22/22 each; E02 head and Phase 0 remain present `UNRUN`, so
`BASELINES_DONE` is **not** recorded. The 84-cell denominator remains 62 complete,
20 verified missing, 2 present `UNRUN`; the 74 named cases remain 42 pass→fail,
12 same, 20 `UNRUN`. This explicit principal direction supersedes the initial
pre-first-repair freeze described immediately below. Begin with R10 and R2, keep
the existing one-writer file leases, and retain the two old-head cells as
`not_established` while completing exact whole-file checks on the repaired head.
The prior result cannot be recast as a timeout or a negative product verdict.

The terminal runner receipt is
`/Users/deniskopylov/.codex/scratch/p41-normative-fullfile-v10-20260925T1250Z/results.json@sha256:20f6f490eceb791ac5fedcfeae9db5bdeecb567f802fb1fc89dcffe292273f58`;
the independent strict-map reconciliation is
`/Users/deniskopylov/.codex/scratch/p41-v10-unrun-reconciliation-20260925-cancel.json@sha256:f47014d025e55e09287f735fa3e91c5ee85d266f90cf3c34048a76c95e0b569e`.
R10's first code commit is `6e159767230188b881e3a2ed70ddd0b031e854df` and its
test-first, removal, control, and full consumer JUnit receipts are in
`R10_REPAIR.md`. The exact R2-History v10 candidate is **NO-GO**: it routed a
fresh recursive producer through history-only validation and left the repeated
S8 source scans in place. Review:
`/Users/deniskopylov/.codex/scratch/e02-r2-r2-history-sublease-v10-independent-review-20260925.md@sha256:8b5834c75b2063920b5420b8a47fc3674893cada19f92c92a5f63c80bd533e38`.

### Handoff snapshot at `021658cd8` (supersedes the prior handoff snapshot)

Snapshot: `codex/e02-r2` is clean at `021658cd87380727f367b0b60a7946ff9668567c`. The integrated bounded repairs are R3 (`79fac987e`), R4 (`efb0f1664`, checker follow-up `c0d290e0a`), R6 (`a8533c688`), R7 (`9426d868a`), R8 (`6baa2e21d`), R10 (`6e1597672`), and the bounded R12/R13 route fence (`da41f2e8c`). These commits close only the recorded properties and scopes; the finding ledger remains the status authority. Commits `314d77c72` and `021658cd8` after the B73 run are documentation-only, so its source/test inputs are unchanged.

The strict pre-repair P41 gate is still **not complete**: 62/84 cells complete, 20 verified missing, 2 present `UNRUN`; the 74 named Appendix A/B cases remain 42 pass→fail, 12 same, and 20 `UNRUN`. `BASELINES_DONE` is not recorded. B73's later three-file replay inspected 12 cells: 10 present cells passed and two cells were missing, so its aggregate verdict remains `UNRUN`, not a clean four-base comparison. Receipts and limitations are in `BASELINES.md` (current blob SHA-256 `f7173e4eac0dc4c0f4263516d4c6e1dcb3f04ca09b014ecec2bc65d26ca59b80`) and its cited raw result `p41-custom-20260925T190717Z-95272/results.json@sha256:2c6aa1351c9ed5bf4530e52a3d6b757534864e9bba2a4253c5e55f641c3e4b49`.

| Current owner | Frozen state and next handoff |
|---|---|
| Root integrator | Sole writer of `codex/e02-r2`; this tree is clean at the snapshot above. Apply only reviewed, ordered candidates and commit each clean boundary. Preserve the existing serialized source order and file leases below. |
| R1/R5 candidate | Clean isolated branch `codex/e02-r1-r5-candidate`: R5 correction `8b6ecd0f7`, then served R1 proposal `bada26f81`. Focused candidate JUnits are green: R5 2/2 and protected-mode 1/1; R1 served proposal v2 1/1 (`/Users/deniskopylov/.codex/scratch/e02-r1-r5-candidate/r5-focused-junit.xml@sha256:117111a988dfd38778f332f821cf40ffc1b114785540ffc427c174f5211a1e58`, `r5-protected-mode-junit.xml@sha256:dc369d919e6db7bb85a1cbe4f883ff551d24fdc145873a3972a365196627af51`, `r1-served-candidate-proposal-v2-junit.xml@sha256:69de1d2df20c6ec4b9d32b30a1c29dcdb2425bbb92b84af3835c84ad1bad2302`). Their paired test-first reds are retained in the same scratch directory. These focused results do not replace exact post-commit independent review or whole-file four-base P41 replay; neither is recorded for this final candidate head. R1/R5 remain unintegrated, and the principal's D-R1/D-R5 decisions remain pending. Keep the typed absent-versus-invalid owner distinction, candidate/authority boundary, and named DataTrust/acquisition residuals in review. |
| R9 candidate | The last clean bounded storage/cache result is `725790db1` with its frozen 60-case suite green (`R9-final-cache-namespace-green-v2.junit.xml@sha256:0008dcbc7959e4a1708183432c8fb3039b4be441789d9a26d715fac11407317e`; addendum `R9_CACHE_SLICE_FINAL.md@sha256:e4556067ce393b9f2f74e431386096a4d61040fa35c0126173f91eea31dd4909`). The candidate then advanced to `849882bc7`; its worktree is now dirty in `caching_store.py`, `store.py`, and `test_caching_store.py` after new cache/selector falsifiers. That later diff is not frozen, reviewed, or covered by the prior 60-case receipt; do not present 60/60 as the current candidate result or integrate it yet. The wider semantic-consumer identity/history residual and R9 principal decision remain open. |
| R13 supplied-store candidate | Clean isolated `codex/e02-r2-r13-store-candidate` at `dd2e9476b`. The writer-reported six-case caller JUnit passed, and the separate R13 receiver-removal probe is retained; independent review is **conditional NO-GO for the full store-owner slice**. It found the R9 typed-view selector dropped in retrieval custody and that the served default N7 gateway does not receive `PromotionRuntime.store`; planner/training/N7 root-store siblings and ACQ-01's second world-growth route remain residuals. These are not R13 closure: sequence through the existing R9/lease handoffs and require the selector-preserving and served same-store witness before accepting the bounded candidate. Review: `/Users/deniskopylov/.codex/scratch/e02-r2-r13-store-candidate-review-dd2e9476-20260925.md@sha256:2e316d49f8dd17e6ed90a8f796077a97edbe3426900ffe8626ee98fc0d114607`; reported caller JUnit: `/Users/deniskopylov/.codex/scratch/e02-r13-store-owner-candidate-20260925T171603Z/reviewed/raw/r13-caller-green-final-diff.xml@sha256:ddc8e82333db4ebbccb20b82d56658da1de0c9763208f764fb0c6f05e68e8401`. The integrated `da41f2e8c` route fence remains a bounded negative only. |
| R11 feasibility | Status remains **not established**; no R11 mechanism or test patch is committed. Patched and unpatched exact-repeat probes both stop at the existing `actual_n4_source` setup before the proposed assertions; the patch was reversed. No owner-emitted exact-repeat candidate, changed-semantics control, persisted-terminal consumer census, or marker-retaining removal probe is established. Missing OR-Tools is only a possible cause, not proven. Keep the positive owner identity and consumer mapping as the next evidence gate; do not infer repair from the inherited setup red. `R11_FEASIBILITY.md@sha256:ca66d88cbf45f84c5d5668247b00e9b6a4802b472275309e6341ab4ee20bb9c1` records the receipts and limits. |
| B72 / N finding coordinator | B72 remains **open**. Commit `021658cd8` corrects its residual owner to the Temporal/Ray worker-result bridge and distributed tier/checkpoint merge: local async already checks `status == ok`, while the remote path loses status and reconstructs success from state-only bytes. The exact durable width-one/width-two resume, skip/fail, independent-success witness is `UNRUN`; sequence any shared merge/checkpoint edit with B73. Source trace: `/Users/deniskopylov/.codex/scratch/e02-r2-b73-b72-admission-20260925/B72-DECISION-PROBE-DRAFT.md@sha256:bf2e0ab8f6dea7ff59cea8eaa5460b1308c19ceece3a32b6b757b4e9e34f0299`. For CYC-03, the current read-only review keeps B09/B27 partial/open and B28 a bounded closure candidate only; the ledger remains partial pending a current-head behavioral replay. Served WDI re-entry does not establish a newly admitted WMR basis. Review: `/Users/deniskopylov/.codex/scratch/e02-r2-cyc03-b09-b27-b28-test-first-20260925/REVIEW.md@sha256:f3ce46be0d03ebad9664b93de086d2aee3858a32add8bf291da4fbfb187fbc9a`; the 11/11 N matrix is `/Users/deniskopylov/.codex/scratch/e02-r2-n-unrecorded-behavior-matrix-20260925/N_FINDING_MATRIX.md@sha256:5eb00c69dec055eb764a34c57bc07a4bc7d975695a84b7f288e4d800ca350cb3`. No status upgrade follows from review alone. |
| Baseline broker | Keep exact per-file/base outcomes, verified missing cells, and `UNRUN` distinct. B73's 10 present passes do not cure its two missing cells or close the 84-cell strict gate. Admit resource-bearing jobs within the measured cap: at most four to five concurrent groups, at least 30% free RAM and 10 GiB disk; serialize native/exclusive resources. Never edit a source tree while its test run is active. |

## Initial pre-repair freeze (superseded by the current code admission above)

This is the coordination map for candidate writers. By default, the `codex/e02-r2` integration worktree stays frozen for source/test edits until the baseline broker closes the strict pre-first-repair gate and records `BASELINES_DONE`. The historical strict matrix is 21 unique Appendix A/B test files × 4 bases = 84 cells; its fourth base is Phase 0, with 62 completed, 20 verified `MISSING`, and 2 present/`UNRUN` (the normative-generation bridge at E02 head and Phase 0). That historical matrix is not a current-integration-head replay. The 74 exact cases reconcile separately to A=15 `PASS_TO_FAIL`, 2 `SAME`, 20 `UNRUN`; B=27 `PASS_TO_FAIL`, 10 `SAME`, 0 `UNRUN` (42/12/20 total). The expanded 100-path/400-cell inventory is historical/additional admission context, not a global first-repair gate. Control API's historical four-base result does not complete the strict gate or TCS semantic probes. The broker alone owns `BASELINE_HARNESS.py`, `BASELINES.md`, raw replay metadata and admissions. **Scoped resource continuation:** Denis's later lane-level instruction permits active TCS-01 engineering to proceed after the broker runs every affordable pre-edit cell and records each resource-limited/not-admitted cell as `UNRUN` with exact base and input identity, command/admission decision, guard/stop reason and retained receipt. This is an explicit continuation for TCS-01; it does not record `BASELINES_DONE`, resolve either strict present `UNRUN`, assign red ownership, or waive TCS post-fix replay. Other writers remain under the default gate unless separately admitted. The strict map is `/Users/deniskopylov/.codex/scratch/e02-r2-p41-closeout-admission-map-20260925-v3.json@sha256:d00e0d7cd566cfb0d23d2f79182472a08b98de945610131be212f96504dc70e5`; runbook `/Users/deniskopylov/.codex/scratch/e02-r2-p41-closeout-runbook-20260925-v3.md@sha256:6e178194b40b3e860a3a1c837f7c865a98e92633e56f58b31207ffc85f38b33a`. Never run simultaneous writers on `runtime/quality/generation_cycle.py`.

The frozen normative v8 replay completed all four fresh collections (22 cases each) but does not close the strict gate. E02-head's one-case JUnit reports a pass for `test_signed_frontier_must_bind_actual_source_not_same_candidate_names`, while the enclosing P41 pilot is `UNRUN` because 270,880,768 bytes of disk loss remained unattributed (2,445,312 bytes beyond the unchanged 256 MiB tolerance); the Phase 0 pilot and both whole-file cells were not launched. This is a diagnostic discrepancy, not an admitted case outcome: preserve the 62/20/2 strict-cell census and 74-case counts above, and do not record `BASELINES_DONE`. The independent disk audit (`/Users/deniskopylov/.codex/scratch/e02-r2-v8-disk-attribution-independent-audit-20260925.md@sha256:2644a58e1eeb8fd64725f00b38b6df1d6a83f8be059ddea21183805942d328d6`) keeps the v8 receipt immutable and recommends that a future versioned runner preserve direct disk-capacity admission/floor checks while recording unexplained shared-volume drift as `not_established` diagnostic state; all other guards and source/checkout checks stay fixed. No later runner or reclassification receipt exists in this note. Receipt `/Users/deniskopylov/.codex/scratch/p41-normative-fullfile-20260925T105323Z-98879/results.json@sha256:8778ccad6ae23f82b659a3b24463a061b6377eeb241d597cf506c9df2c4f6101` and details are in `BASELINES.md` under “Normative bridge guarded replay v8”.

A focused R10 pre-edit replay of `policy-engine/tests/integration/core_runtime/test_acquisition_admission_bundle.py` completed 4/4 present cells at 6/6 passed, with no missing or `UNRUN` cells. Its file blob and `pytest.ini` blob match across the four bases; normalized pytest flags match and imports resolve from each pinned checkout. Receipt: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260925T114032Z-24622/results.json@sha256:0a71316d05bf865ec8704210168bb5a9890baaac7bc359998f1c3fa99fa31639`; full IDs and source/import/resource evidence are in `BASELINES.md` under “R10 admission-bundle focused pre-edit replay”. This class-specific baseline does not close or reduce the 21×4 Appendix A/B strict gate or alter the 74 named-case outcomes; source/test writers remain frozen until the normative cells are resolved and `BASELINES_DONE` is recorded.

## Compute admission after the interruption

**Current user override (2026-09-29).** For ordinary light jobs, the later explicit resource ruling supersedes the older 10 GiB disk floor and the 35%/30% free-memory targets in this section: keep at least **8 GiB free disk**, admit no more than **five light test process groups** with about **500% aggregate CPU** as the working ceiling, and retain roughly **25% free memory at admission / 20% while running**. Heavy native or numerical work remains exclusive. The single-group normative launcher retains its separately measured host-idle, process-sample, swap and **12 GiB early-abort** guards until that launcher is reviewed and changed. Observe actual pressure and stop admitting new jobs before the applicable floor; do not edit a tree while its tests run. Only fully verified, unneeded files may be moved with `mv` to named macOS Trash folders; never delete directly or empty Trash. The earlier limits below are historical for ordinary light admission; their normative-launcher checks still bind that pilot.

Run one process for an unprofiled or heavy job. For measured jobs, admit at most four same-blob groups, with admission CPU capped at 500% and active-run CPU capped at 600%; each group must stay at or below 8 GiB resident memory. The single-group normative-bridge pilot is a measured exception: its prior two-thread run reached 587.6% and stopped at a 525% cap before JUnit, so its bounded launcher may tolerate a short process-group sample up to 625% while separately requiring host CPU idle of at least 15% (with only a bounded transient-sample allowance), no other pytest group, and the same memory, swap and disk guards. This exception does not admit parallel native jobs or change the general 600% limit. Keep at least 35% free-RAM reserve at admission and enforce a 30% hard reserve while jobs run. Swap growth must stay at or below 256 MiB, and free disk must remain at least 10 GiB; the normative launcher aborts earlier at 12 GiB. When a guard turns red, stop admission and checkpoint running work or record interrupted/unadmitted work as typed `UNRUN`; do not fall back to singleton `Popen` execution. Native or exclusive-resource jobs run alone.

## Initial ownership

| Work set | Owner |
|---|---|
| Integration branch/worktree `codex/e02-r2`, generated families, governed artifacts, authorized reissue planning | root integrator |
| `BASELINE_HARNESS.py`, `BASELINES.md`, baseline raw metadata and test admission | baseline broker |
| `RESIDUAL_LEDGER.md`, `residual_ledger.json`, `finding_record_probe.json`, `CROSSWALK.md`, `REGISTER_PROPOSALS.md`, `WRITE_LEASES.md` | ledger writer, candidate branch only |
| `DECISION_RECORDS.md` | decision writer |
| E02 records, DEBT-REGISTER/LEDGER, plans, runtime/test code | their owners; read-only to this writer |

TCS-01 has a 14-file task-specific whole-file P41 denominator (56 file/base statuses), admitted by the broker after the R-class lane and per-class changed-input census: the original nine paths are `policy-engine/tests/unit/runtime/http/test_control_api.py`, `test_runtime_rego_authorization_parity.py`, `test_runtime_api_authz.py`, `test_runtime_api_observability.py`, `test_workspace_loop_transition.py`, `test_runtime_api_write_path_hardening.py`, `policy-engine/tests/unit/runtime/http/services/test_lex_pipeline.py`, `policy-engine/tests/unit/runtime/http/test_runs_api.py`, and `test_core_only_runs_api.py`; class-wide P40 adds `policy-engine/tests/unit/runtime/http/test_runtime_authorization_access_audit.py`, `test_acquisition_control_worker.py`, and `policy-engine/tests/integration/core_runtime/test_acquisition_authority_served.py`; the candidate test write set also includes `policy-engine/tests/unit/runtime/http/test_control_plane_store.py` and `test_normative_evidence_intake.py`. The four bases are execution `78187878e`, E02 head `00d946c2b`, main `5fd3ebcc1`, and integration HEAD `7d628fd8f6233a5cc7110c52a14141c0f226f519`. `1b48cee95dd17534527532e3b4f7930d9d479ee0` is an earlier ancestor. `5b64d38c3` was HEAD when v2 was reviewed; live HEAD pinned for v3 is `7d628fd8f6233a5cc7110c52a14141c0f226f519`. The 1b48-to-7d628 path delta contains only `OPEN_PREMISES.md` and `BASELINES.md`, with no `src` or `tests` paths. Do not relabel receipts across commits or treat path equivalence as a test run. Following the R-class handoffs, freeze the exact TCS pre-edit integration HEAD and recheck test/source input closure; any changed closure needs a new affordable replay or a resource-justified `UNRUN`. At the 7d628 snapshot, all 14 integration-head cells are `UNRUN` absent exact-head receipts. Historical four-cell controls for `test_control_api.py` (63/63 each; `raw/p41-custom-20260925T050338Z-88064/results.json@sha256:2259b569c1a5d97ff224f24cad7f9d2d141d21d1791471c6d80e031f47fe83d5`), `test_runtime_api_write_path_hardening.py` (7/7 each; `raw/p41-custom-20260925T055347Z-34201/results.json@sha256:5be1e7bfb85f60082c98761ad303214909cb7f8ad03ab84c1bbb4fce21788187`), and `test_control_plane_store.py` (28/28 at execution/E02, 29/29 at main/Phase 0; `raw/p41-custom-20260925T052235Z-96088/results.json@sha256:4dd5fab17b4b524621a2def4020a9ccc6630161dca8c9c7cb51c023b63d7f9ca`) use Phase 0 `73c656744` as fourth base and do not fill current-head cells. `test_normative_evidence_intake.py` has a partial older four-slot receipt pinned to integration `bed508646`: two 14/14 passes, one E02 worker-exception `UNRUN`, and one scheduler-paused `UNRUN` (`raw/p41-custom-20260928T213314Z-92507/results.json@sha256:da21734cb758da1dc5d97be2431b3e3411277d899733251efa59c2510511a2b9`); those outcomes remain attached to their recorded bases. The broker's “other seven” original entries are seven path-level replay sets, not seven cells; enumerate actual remaining cells per file. The three P40 paths have historical per-base rows but no exact 7d628 cell; `test_acquisition_authority_served.py` is `MISSING` at execution/E02, PASS at main, and FAIL at Phase 0, not a current integration result. TCS semantic and removal/preserving witnesses remain `UNRUN`.

The historical strict Appendix A/B matrix is 21 files × four bases = 84 cells; it uses Phase 0 `73c656744` as the fourth base and records 62 completed, 20 verified `MISSING`, and 2 present `UNRUN`. This is not a current-integration-head replay; `BASELINES_DONE` remains false while either present cell is unresolved. Denis's later lane-level resource direction permits the active repair to continue after every affordable pre-edit cell is run and each resource-limited/not-admitted cell is recorded `UNRUN` with exact base and test/source identity, command or admission decision, resource guard/stop reason, and retained receipt. This permits engineering continuation; it does not turn `UNRUN` into PASS/FAIL, assign red ownership, or claim `BASELINES_DONE`. Run the affordable subset before edits, keep all runs source-frozen, and preserve per-cell status. After TCS implementation, whole-file four-base replay of each changed test path remains required for closure; if a post-fix cell is still resource-limited, keep it `UNRUN` and TCS open/partial until safely reverified. Apply this explicit lane-level continuation instead of the older absolute “all cells before code” wording; it is not a general permission to skip affordable baselines.

## Candidate write sets after baseline freeze

The historical strict Appendix A/B matrix remains 21 unique files × four bases = 84 file/base cells; it uses Phase 0 `73c656744` as its fourth base and records 62 completed, 20 verified `MISSING`, and 2 present/`UNRUN` normative-generation bridge cells. It is not a current-integration-head replay. `BASELINES_DONE` is not recorded unless those present cells are resolved. Denis's later lane-level resource direction authorizes the active repair to continue after the broker runs every affordable pre-edit cell and records any present resource-limited/not-admitted result as `UNRUN` with exact source/base identity, command or admission decision, guard/stop reason, and retained receipt. This is a code-work continuation, not completion of the strict gate; `UNRUN` stays unowned, Git-verified path absence remains `MISSING`, and no class closes until its required post-fix replay is complete. TCS-01 applies this rule to its 14×4 task-specific denominator below. The expanded 100-path/400-cell inventory (32 initial paths plus 68 add-ons) is not a blanket first-repair requirement. It remains useful historical admission context, while each later class gets a fresh four-base replay for its frozen source/input closure. The broker alone owns baseline artifacts and outcomes; read-only diagnosis may proceed. Candidate writers follow the default gate unless the principal's explicit resource-bounded continuation applies. Compute admission follows the guarded policy above. R12 may inspect the independent acquisition fixture/bootstrap checker during diagnosis, but any R12 edit to `generation_cycle.py` remains serialized after R13, R6 and R11.

| Sequence | Class | Exclusive write set | Handoff / constraint |
|---|---|---|---|
| 15 | TCS-01 | One writer's exact class-wide set: `runtime/http/dependencies.py`, `runtime/http/routes/control.py`, `runtime/http/routes/acquisitions.py`, `runtime/http/routes/runs.py`, `runtime/http/services/acquisition_action_service.py`, `runtime/http/services/control/run_lifecycle.py`, `runtime/http/services/control/lex_pipeline.py`, `runtime/http/services/control_plane_store.py`, `runtime/http/production_approval_binding.py`, `runtime/http/resource_binding.py`; tests `test_runtime_authorization_access_audit.py`, `test_acquisition_control_worker.py`, `test_acquisition_authority_served.py`, `test_control_plane_store.py`, `test_normative_evidence_intake.py`, plus broker-admitted TCS importer/consumer paths | Post-R-class `ControlPlaneStore` owner lease for direct job/Lex status, run-detail projections, approval scorecard/packet inputs, normative-evidence job selection, and the acquisition route's tenant-only scope/idempotency edge. `acquisitions.py::_scope` is the same TCS-01 P40 class one level deeper, not a new class. Put one reusable verified-tenant + registry-routed-cell helper in existing `dependencies.py`; the helper and every consumer/store change have the same writer/lease, with no side owner or per-route helper. Use one immutable owner tuple and exact scoped selectors; keep historical NULL-owner rows inaccessible to in-scope consumers. Preserve the independent completed-job verifier at `runtime/http/services/control/evaluation_safety.py` unchanged and excluded. Keep the verified cell router/registry read-only. The task-specific denominator is 14 whole files × four bases = 56 statuses, with integration HEAD `7d628fd8f6233a5cc7110c52a14141c0f226f519` as the present snapshot; the v2 review HEAD `5b64d38c3` and earlier ancestor `1b48cee95` are historical identities. Receipts remain pinned to the commit actually tested. The prior full historical control receipts use Phase 0 `73c656744` as their fourth base, and the partial normative-evidence receipt pins `bed508646`; none fills the 7d628 cell. All 14 current integration cells are `UNRUN` absent exact-head receipts. The broker's other seven original entries are path-level replay sets, not seven missing cells. After R-class handoffs, freeze the exact TCS pre-edit HEAD and reconcile source closure. Under Denis's later lane-level direction, run every affordable pre-edit cell and retain each present constrained/unadmitted cell as `UNRUN` with per-cell base/input/command/admission/guard receipt; TCS code may then proceed without falsely recording `BASELINES_DONE`. Post-fix four-base whole-file replay for every changed test path is still required for closure, with any resource-limited cell left `UNRUN` and TCS open. TCS follows the R-class `ControlPlaneStore` handoffs (R8 → R1/R5); source overlap requires serialization, not preemption of R work. |
| 1 | R8 | `runtime/http/services/control_plane_store.py`, including `update_manifest_ref` and `advance_acquisition_action_head`; `runtime/http/services/acquisition_action_service.py` / `runtime/quality/acquisition_route_authority_sink.py` only as caller tracing requires; `tests/unit/runtime/http/test_acquisition_control_worker.py` | Take the shared-store lease before R1/R5. The R8/R1-R5 source map identified a direct `control_plane_store.py` collision; sequencing R8 first keeps the bounded stale-generation fence change independent of R1's broader candidate/context work, after which R1/R5 rebase onto R8's committed head. One writer owns the guarded control-store invariant across known worker-owned writes. Reviewed v2 design `/Users/deniskopylov/.codex/scratch/e02-r2-r8-expanded-p40-handoff-v2-20260925.md@sha256:018aa2c7271e7d2338e2401be514475c02ca55f7e1360e753fc45eb8e871ba1d` and review `/Users/deniskopylov/.codex/scratch/e02-r2-r8-expanded-p40-handoff-v2-review-20260925.md@sha256:827869bd95dfdce8290f2fc9f7d90c106c00f4890c08ae56477b5de1ff3425e3` give `GO` for design, not behavior. Replace the per-store fence carrier with ContextVar across the existing `GuardedDependencyProxy` context-copy boundary and recompute persisted `running + owner + attempt + unexpired lease` at each protected mutation. `update_manifest_ref` is a pre-terminal escape; `advance_acquisition_action_head` is a second same-class escape requiring lease check, predecessor comparison, conditional insert and readback in one transaction, with fresh expiry at append and lease-loss distinct from predecessor conflict. Preserve rollback for nested `upsert_progress`/event/outbox writes; no blanket `upsert_progress` fence or running-only rule. The frozen 100 includes the worker test's two direct-service cases at each base, not a production-worker witness. Add the actual guarded `ControlWorker`: pause A, take over with B, then resume stale A through action-head and terminal mutations; stale work must be refused without changing B. Keep current-owner, pre-enqueue `requested` head, and post-completion readback controls. The marker-retaining ContextVar-removal probe must turn stale assertion red. `test_control_plane_store.py` and `test_acquisition_route_authority_sink.py` are outside the frozen 100; broker-admit each whole file at all four bases before editing. `test_dur_02.py` raw-store evidence is insufficient. Every behavior/removal probe remains `UNRUN`.
| 2 | R1 + R5 | `runtime/http/services/control/generation_cycle.py`, `runtime/http/services/control_plane_store.py`, `runtime/quality/recursive_generation_cycle.py`, `runtime/quality/generation_cycle.py`, `runtime/quality/evaluation_modes.py`, and recursive epoch-gate tests | One candidate writer owns the listed runtime paths and shared tests; review candidate/authority bands together. After R8 hands off the shared store, R1/R5 own `control_plane_store.py` for `create_job` and projection behavior, rebasing on R8's committed head. Use existing hash-verified compiled-run/context references and the owner resolver; ordinary candidate work may carry a typed unknown. Decision-draft review `/Users/deniskopylov/.codex/scratch/e02-r2-decision-drafts-independent-review-20260925.md@sha256:fc7103792e6525d032101dba8208336f223d3f21c5e87118f5407bc66b21af4c` is conditional NO-GO until R5 routes `retrospective`/`measurement_audit` through existing DataTrust and limits EvalSafety to `sandbox_pilot`/`field_pilot`/`deployment`; no principal ruling or behavior result is inferred. N4 owner context is `not_established`: `_build_cycle_substrate_context_from_owner` uses a separate `.tmp/gy-s-composed-wmr-cas`, so runtime tenant-store custody and caller provenance are not proven. N7 post-growth owner context is also `not_established`; S8 authority stays blocked until a canonical post-growth witness is supplied. No GenerationCycleRun schema change belongs to this lease. This is the first shared `generation_cycle.py` source lease; finish before R2-History, then R13, then R6/R11/R12 runtime edits and R2-Currentness/Route. The R1 context owner must resolve/refresh `CycleSubstrateContext` for each exact active basis before R13's served cycle-index>0 witness: N4/N5 use that same basis-bound context, and any N8 EvalSafety context is explicitly bound to it. Root-only context cannot be reused for revised basis `B`; unavailable scope remains a typed candidate-band unknown.
| 2 | R7 | connector registry/executor and acquisition validation/transport | Independent source lease; one writer owns the connected registry/executor path. No parallel health-probe or network edits. |
| 4 | R3 | `runtime/quality/promotion_sequence.py` | Historical fixture and serializer changes are this lease. R2's pre-N9 identity capture/compare also needs this file, so R3 must hand it off before any R2 edit there; keep R2's compare as a separate reviewed delta. R4 may reuse `_VerificationN9PromotionPort` only after R3 completes, with its own reviewed delta. |
| 5 | R10 | core artifact signature/integrity public boundary | First shared CAS owner change; normalize IDs at boundary and reconcile all 28 direct call expressions (16 source across 12 files, plus 12 tests). |
| 6 | R9 | core artifact store plus every backend/profile manifest | Follows R10 in the shared artifact-owner lane; all backend/view identities are exclusive. |
| 7a | R2-History | `runtime/quality/generation_cycle.py`, plus `runtime/quality/recursive_generation_cycle.py` only if historical replay needs a caller change, and broker-admitted historical serializer tests | After R1/R5 and before R13, this narrow lease changes only versioned v1/v2 historical projections and source-free historical replay. It does not compute current deployment identity, route census, pre-N9 currentness, or authority. Enumerate the tracked denominator: 9 N6-v1 occurrences across 6 run IDs (including duplicate historical/current representations), 1 N6-v2, 7 recursive-v1 objects/seven parent hashes, and 6 compiled-v1 objects/six hashes. Preserve occurrence paths while deduplicating identical payloads; authenticate raw/canonical bytes and parent hashes. v2 byte parity remains UNRUN without an authenticated original. Any `promotion_sequence.py` touch waits for R3 handoff. Keep `tests/unit/remediation/test_cyc_05.py` in the brokered whole-file set; other history test files need explicit four-base admission before edits. Hand the shared generation-cycle path to R13. |
| 8 | R13 | `runtime/quality/generation_cycle.py`, `acquisition_planner.py`, `acquisition_route_loop.py`, `generation_source.py`, `acquisition_world_growth.py`, `acquisition_movement.py`, Foundry training adapter, `intervention_substrate.py`, `data_state_substrate.py`, `world_model_record.py`, `cycle_substrate.py`, `confidence_ledger.py` / `promotion_sequence.py` for the supplied-store N9 sublease, and `fabric/data_plane/modes.py` / CursorStore caller where the root-store census overlaps; broker-admitted tests | After R1 per-basis context refresh and R2-History; acquisition/world-growth caller and tenant custody are reviewed together. Static census: 2,693/2,693 `src/**/*.py` parsed, zero errors; 26 direct `FileSystemCAS` + 33 root-config `build_artifact_store` calls = 59. E02’s five new direct constructors are a subset, not a complete denominator. Include `.n7-live-cas`, root-forwarded wrappers, production caller and tenant custody through re-entry; B79’s `run_batch_incremental` also builds from `cas_root` before `CursorStore`, but cursor lookup still does not prove request propagation. Dynamic paths remain `not_established`. For a selected source cycle, resolve persisted `run_id + cycle_index + candidate id + atom hash` and exact `GenerationSourceHandoff.problem`; recompute the full problem hash and reconcile it to the selected cycle basis and the immediately preceding revision's `revised_problem`. Keep the root `design_problem_ref` as route/movement subject; carry source/re-entry basis separately, and separately prove world-growth epoch admission. `GenerationSourceRepository.resolve()` currently does not select `cycle_index`, so no source-basis lineage is established from its current lookup. The v2 source/basis audit `/Users/deniskopylov/.codex/scratch/e02-r2-subject-basis-reentry-20260925-v2.md@sha256:8d74d9cb624e8e96d4c75a7ee4323034934a18b366029f85677ee90dab06c12c` and independent review `/Users/deniskopylov/.codex/scratch/e02-r2-subject-basis-reentry-v2-independent-review-20260925.md@sha256:ec361a1378a6fcb7d5bf2cd6e2bc0d690ccbf1b63c8016673bd570e53fdb00f0` confirm exact-occurrence design and that the active-overlay W1 context provider is a missing capability; design is conditional GO, implementation/behavior remain UNRUN. The bounded follow-up is `R13-W1_ACTIVE_OVERLAY_CONTEXT_TASK.md`. Add `policy-engine/tests/unit/runtime/quality/test_acquisition_route_loop.py` to the broker's pre-edit four-base queue; it is absent from frozen 100. The served positive, wrong-basis/wrong-occurrence negatives, marker-retaining source-basis and overlay-to-W1 removal probes, and same-subject/same-basis candidate control remain `UNRUN`. W1 extends the existing Data Forge→data-state→WorldModel→CycleSubstrateContext chain and uses the runtime-supplied guarded store after R1 per-basis refresh. The separate `ConfidenceLedgerSession.from_repo()` root-CAS call is the same R13/P31 store-custody class, behind R3/R2-History and before R4; do not edit it under the acquisition W1 sublease. Static receipt: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/policyos-r13-root-store-census.json@sha256:38c3ddd50feceb7fef253bac54569315007a5cc9289d536721c9dd2ff3beb7bf`. |
| 9 | R6 | `runtime/quality/generation_cycle.py` / joint N5 input context | Root serializes after R13; the context-identity map `/Users/deniskopylov/.codex/scratch/e02-r2-r6-context-identity-map-20260925.md@sha256:6022815efb9ded6b1137a242015b0209c4cad979bcb3ee22a41a46af214a56f7` locates the E02-only foreign-context fallback at the existing JointSimulationPort owner. Use the existing negative and same-context preserving control; the map is source/dataflow diagnosis, and all behavior/removal probes remain `UNRUN`. Hand off before R11/R12 runtime edits and final R2 route census. |
| 10 | R11 | `runtime/quality/generation_cycle.py` / VOI decision consumers | Root serializes after R6; enumerate board, promotion, projection, and recursive consumers. Positive-N9 blocked-run promotion remains an identified consumer gap; do not claim `blocked` fully handled until every consumer preserves the disposition and a real blocked run cannot promote. Principal decision remains pending. |
| 11a | R12 diagnosis | independent acquisition fixture/bootstrap checker only; no shared mechanism write | May inspect during diagnosis. The R4/R12 dataflow audit `/Users/deniskopylov/.codex/scratch/e02-r2-r4-r12-n6-dataflow-20260925.md@sha256:2a0e8e05455838a20f99efa006926ee8d335558109a5adb7a4a92960ba4a6ca9` classifies the fake N7 atom as a fixture and the bootstrap checker as a P38 proxy candidate; neither proves a served canonical re-entry. The real local WMR route is already R13. If runtime repair changes `generation_cycle.py`, hand off to sequence 11b; R2-Currentness/Route must census after it. |
| 11b | R12 runtime repair | acquisition contract plus `runtime/quality/generation_cycle.py` | Root serializes after R13, R6, and R11; diagnose then fold into R13 or R2 if evidence shows the same class. A runtime edit that changes N6 entry/admission precedes R2-Currentness/Route. The dataflow audit above is diagnosis only; all semantic probes remain `UNRUN`. |
| 12 | R4 | governed GY-N6 checker and `runtime/quality/generation_cycle.py`; if `_VerificationN9PromotionPort` is touched, `runtime/quality/promotion_sequence.py` | Measure the checker crash before repair. The R4/R12 dataflow audit `/Users/deniskopylov/.codex/scratch/e02-r2-r4-r12-n6-dataflow-20260925.md@sha256:2a0e8e05455838a20f99efa006926ee8d335558109a5adb7a4a92960ba4a6ca9` traces a stale initial verifier session against the final basis. Independent exact-design review `/Users/deniskopylov/.codex/scratch/e02-r2-r4-n6-exact-design-review-20260925.md@sha256:53db00b7d88a969c57c8cc2062768e32b1639eeb0961079ad94b9944044a27a5` returned NO-GO: completed scope mismatch is FAIL/1, prepredicate unavailability is UNRUN/2, and valid scope is PASS/0; the design also lacked JSON/text input disclosure and claimed three suites UNRUN despite completed BASELINES. The corrected handoff addendum `/Users/deniskopylov/.codex/scratch/e02-r2-r4-n6-implementation-handoff-addendum-20260925.md@sha256:8f731a5d0211942f1f58bc7014ab04a677f34a30b203c28d66ebcdfdec49ce5d` supersedes that design NO-GO on the verdict distinction and is design-ready subject to implementation review and P41; it requires no governed output mutation on red and no restamp. Preserve N9 equality and three-valued verdicts (exit 0/1/2). R4 follows R3 for any shared promotion-sequence port and precedes R2-Currentness/Route edits to the same GY-N6 checker. Its source diagnosis is not a behavioral result. |
| 13 | R2-Currentness/Route | `runtime/quality/generation_cycle.py`, `runtime/quality/recursive_generation_cycle.py`, `runtime/quality/confidence_ledger.py`, `runtime/http/services/control/generation_cycle.py`, `runtime/quality/public_export.py`, `runtime/quality/design_axes/value_choice_provenance.py`, `tools/quality/validation/check_layer3_gy_generation_cycle_contract.py`, `tools/quality/validation/check_layer3_gy_second_domain_pack.py`, plus broker-admitted consumer tests including `tests/unit/remediation/test_cyc_05.py` and `tests/unit/runtime/quality/test_second_domain_pack.py`; serialized pre-N9 compare sublease on `runtime/quality/promotion_sequence.py` | This is the final shared-N6 route/currentness/schema/census lease, after R1/R5, R2-History, R13, R6/R11, any R12 runtime edit, R4, and R3’s explicit `promotion_sequence.py` handoff. Bind complete served-route/source census to canonical deployment identity, compare before N9, preserve historical-valid/currentness as distinct typed states, and wire authority consumers. The checker has three `validate_generation_cycle_run` call sites (N10a trace, single-terminal closure, smoke replay); explicitly classify their historical-vs-currentness semantics. The off-100 test `policy-engine/tests/unit/runtime/quality/test_second_domain_pack.py` must enter the broker’s pre-edit four-base queue. Include/recompute generated JSON only if the owner produces a real delta, through the checker after source freeze. The package carrier remains `not_established / bridge_missing`; do not substitute checkout paths or caller digests. Keep `runtime/http/services/control/run_lifecycle.py`, `runtime/quality/evaluation_safety.py`, and `runtime/quality/acquisition_route_loop.py` conditional only; add them to the write set only if the consumer audit establishes a direct R2 dependency. Source-free currentness, candidate preservation, marker-retaining route removal, controls and final P41 replay remain `UNRUN`. |


R2 narrowed-history P41 expansion: before editing `confidence_ledger.py` or `promotion_sequence.py`, add these ten missing whole-file importer/consumer paths to the broker's four-base queue: `policy-engine/tests/repo_quality/tools/test_governed_owner_history_independence.py`, `policy-engine/tests/repo_quality/tools/test_layer3_gy_confidence_ledger_contract.py`, `policy-engine/tests/unit/runtime/quality/test_obligation_coverage.py`, `test_confidence_ledger_surface.py`, `test_promotion_scope_guards.py`, `test_depth_n_universality.py`, `test_second_domain_pack.py`, `policy-engine/tests/unit/runtime/http/test_confidence_ledger_risk_spend_api.py`, `test_confidence_ledger_risk_spend_projection.py`, and `test_confidence_ledger_risk_spend_contracts.py`. Review: `/Users/deniskopylov/.codex/scratch/e02-r2-narrow-history-handoff-independent-review-20260925.md@sha256:83141f52564ec9b256d9e1a08afa0cfb90189f45b403c3a983228726ec8fcadb`; it is `NO-GO` to begin code until the denominator and source-free witness are settled, while the architecture is otherwise accepted. These are importer-path findings, not test outcomes; `MISSING` at a pinned ref is not a pass. The `test_second_domain_pack.py` consumer also remains an explicit R2 final-currentness checker. `test_hatch_packaging.py` must not run under the no-delete constraint; choose a no-delete installed-package witness in an admitted file or admit a safe whole-file path. No R2 edit is admitted before the full Appendix A/B replay and `BASELINES_DONE`.
| 14 | R14 | tooling/release-manifest and core-runtime closeout ledger | Distinct tooling lease; its separate 344-path R14 denominator must not be conflated with the 100-file pre-repair replay. Four same-source cases currently identified (one W5 historic repo ref, three WS-2D release-ledger raw-client refs); attribution and test-file replay pending. |
| 14b | R14 runtime-contract merge candidates | `tools/ops_runners/runtime/check_runtime_api_contract.py` and `tests/repo_quality/tools/test_runtime_contract_measurement.py` | Do not edit either file until the broker completes the queued P41 custom replay for the main-only test path and records its four-base/overlay disposition. Phase 0 review `/Users/deniskopylov/.codex/scratch/e02-r2-phase0-merge-review-20260924.md@sha256:98b4cf8351d5e321812aace2a2d626b62e942c1109f31e3caf547f509b4f891e` predicts two setup failures from monkeypatches of retired `_check_runtime_client_drift`; this remains a replay candidate, not a confirmed regression. The formal subtask `/Users/deniskopylov/.codex/scratch/e02-r2-r14-runtime-client-unrun-subtask-20260924.md@sha256:844e67d675be12188ee15cf98628ce7de74f5e9165b659395972d1f204faa9a0` identifies a separate P38 candidate: nonzero generator exit may be reported as measured `FAIL`/exit 1 although byte inspection did not complete and should be `UNRUN`/exit 2. Keep this source/test pair exclusive after replay; require a marker-retaining nonzero-generator probe that must return `UNRUN`, a valid measured-drift control that returns `FAIL`, and four-base evidence before classifying. Both leads remain provisional and `UNRUN`. |
| 16 | H/N/P | Finding-specific owners after R classes | Census each write set against this map; one writer per intersecting path. N OPT/SIM test sources wait for the 68-file planned add-on replay. LA-046 has its own serialized source lease below because it intersects `generation_cycle.py`. |
| 17 | LA-046 | `data_requirement/compiler.py`, `runtime/quality/generation_cycle.py`, `tests/unit/data_requirement/test_compiler.py`, `tests/unit/runtime/quality/test_generation_cycle.py` | One writer owns the original compiler/profile semantics and the r08 N7 handoff. Wait until the baseline is frozen and all earlier `generation_cycle.py` leases (R1/R5, R2-History, R13, R6, R11, R12-runtime, R4, R2-Currentness/Route) are complete. Any test file absent from the frozen 100-file set needs a separate four-base replay before editing. LA-046 is not assigned to R12 or R13 merely from shared N7 vocabulary or a shared file. |

## Source dependency order

- The reconciled order follows R13’s independent review `/Users/deniskopylov/.codex/scratch/e02-r2-r13-class-design-review-20260925.md@sha256:11b75dc598e4652e3038e0a80a22bcf4bf1f465a8f1b787fc714ce4964b93690` and R2’s independent review `/Users/deniskopylov/.codex/scratch/e02-r2-r2-history-design-review-20260925.md@sha256:5eb1de2a6654a7757d4f7a0f4cc613c672658c2f143639957e6c55a1d82159a2`. R13’s “R2 final” means R2-Currentness/Route; R2-History is the explicitly bounded earlier serializer-only sublease. Required shared N6 order: resolve the strict 21-file/84-cell pre-first-repair gate before any source edit; R1/R5; optional R2-History; R13; R6; R11; R12 runtime changes; R4; then R2-Currentness/Route. R3 owns `promotion_sequence.py` independently and hands it off before R2’s pre-N9 compare sublease. If R9 has an admitted shared `acquisition_movement.py` change, finish R9 before R13; otherwise R9’s artifact-store lane does not constrain R13.

- Shared ControlPlaneStore order: R8 → R1/R5 → TCS-01. R8 takes the bounded stale-generation fence lease first; R1/R5 rebase after R8’s handoff. TCS-01 is a proposed new class scheduled after the full R-class lane; its same-file overlap with this sequence requires serialization but establishes no dependency to preempt R work. Each owner completes and hands off the shared file; no concurrent edits. R8 covers `update_manifest_ref` and worker-phase `advance_acquisition_action_head` at their persisted mutation boundary; `upsert_progress` is not an independently admitted escape.

- R2-History may change only historical v1/v2 projection/replay behavior and its broker-admitted witnesses. It must not claim route completeness or current deployment authority. R2-Currentness/Route waits for all route-changing owners and the governed N6 checker repair; it owns currentness/census integration and its consumers. Keep the R3 serializer/fixture lease distinct from R2’s pre-N9 compare delta.
- Independent source lanes after the baseline freeze: R3 owns the first `promotion_sequence.py` lease and hands off the pre-N9 compare sub-lease to R2-Currentness/Route; R7 owns its connector registry/executor path. On the shared `control_plane_store.py`, R8 precedes R1/R5; TCS-01 follows the full R-class lane. Each candidate rebases after the preceding explicit handoff. R10 owns the public signature boundary before R9 changes store/profile behavior.
- R14’s 344-path denominator is a separate same-source audit, not an expansion of the 100-file pre-repair baseline denominator.
- The R14 runtime-contract test/checker pair in row 14b waits for the broker’s queued custom P41 replay of `tests/repo_quality/tools/test_runtime_contract_measurement.py`; its predicted stale monkeypatch and P38 verdict concern are candidates only until the replay and behavioral removal/preserving controls complete.

## Serialization rules

- R8 owns the first R-class ControlPlaneStore lease; R1/R5 follow R8 and rebase on its committed head. TCS-01 follows the R-class lane; the shared file is never edited concurrently.

- Only the candidate holding the current lease may edit `generation_cycle.py`. Required order is R1/R5 → R2-History → R13 → R6 → R11 → R12-runtime → R4 → R2-Currentness/Route; root may change later order only after recording dependency evidence and reassigning the lease. R12 diagnosis outside that file does not hold its lease. R3 must hand off `promotion_sequence.py` before R2-Currentness/Route’s distinct pre-N9 compare sub-lease; R4 follows R3 if it touches that file. These follow-on deltas do not reopen R3's serializers or fixtures.
- R1 and R5 share one candidate writer; the `generation_cycle.py` handoff completes before R2-History begins. R2-History may not include current route/currentness changes. Neither N4 nor N7 owner-bound context may be claimed from a separate temporary CAS or prior handoff refs alone.
- R10 precedes R9 in the shared artifact owner lane. `control_plane_store.py` follows R8 → R1/R5 → TCS-01 with explicit handoffs and no concurrent lease. If review shows a dependency reversal, stop and revise the lease before further edits.
- R8's reviewed source scope is the existing `ControlPlaneStore` fence plus `update_manifest_ref` and `advance_acquisition_action_head`; do not introduce a separate `upsert_progress` fence or a blanket running-only check. The production worker witness belongs in the already admitted `test_acquisition_control_worker.py`; any edit to unadmitted store/sink tests requires fresh four-base admission. Preserve the post-completion workspace proof and transaction rollback semantics.
- Governed epochs and receipts are serialized by the root integrator. Reissue occurs only through an authorized transition; no restamping is permitted.
- H/N/P repair edits begin only after both baseline waves and R-class write sets settle. Any later-added test file needs its own broker-admitted four-base pre-edit replay before source/test edits. Any collision becomes an explicit sequential lease.
- LA-046's `compiler.py` + `generation_cycle.py` pair is a single serialized finding lease after R1/R5, R2-History, R13, R6, R11, R12-runtime, R4 and R2-Currentness/Route. Its property is requirement content/profile through the real N7 handoff; it does not inherit the R12 re-entry-identity or R13 world-growth/store-custody property. Replaying any newly admitted test must go through the baseline broker.
- The baseline broker controls test process admission and exclusive native resources. The historical strict pre-first-repair Appendix A/B denominator is 21 unique test files × 4 bases = 84 file/base cells, with Phase 0 as the fourth base: 62 completed, 20 verified `MISSING`, and 2 present/`UNRUN` normative-generation bridge cells. It is not the current-integration-head replay. `BASELINES_DONE` remains false until those present cells resolve. Denis's later lane-level instruction allows resource-bounded code continuation after affordable pre-edit cells run and remaining constrained cells receive exact `UNRUN` receipts; it neither changes this count nor treats `UNRUN` as a verdict. The 74 named Appendix A/B case outcomes remain separately A=15 `PASS_TO_FAIL`, 2 `SAME`, 20 `UNRUN`; B=27 `PASS_TO_FAIL`, 10 `SAME`, 0 `UNRUN`. The 100-path / 400-cell inventory (32 initial + 68 add-ons) is an expanded historical queue, not the global first-repair gate. Its old 342 present / 58 missing counts are not current gate evidence. The broker controls any added class-specific replay; active-lane source/test edits may use only the explicit principal-approved resource continuation, and post-fix evidence remains necessary before class closure.

## New reviewed P41 constraints and design boundaries (2026-09-25)

- R1/R5 per-basis review `/Users/deniskopylov/.codex/scratch/e02-r2-r1-r5-per-basis-context-owner-review-20260925.md@sha256:6109b4ac7885123ffa0c3922d9ad2d1d9fb1240e8c89bc0155ee1eb0ee18ef7b` conditionally accepts candidate dispatch only; protected revised-basis authority needs the actual EvalSafety issuer and active-overlay W1 provider. Add `tests/unit/runtime/quality/test_acquisition_route_loop.py` and `test_control_api.py` to the pre-edit queue; add `test_value_gate.py` only if N8 provenance changes. Its source/context census additionally names `test_acquisition_route_authority_sink.py`, `test_proving_ground_legal_mandate_search.py`, and v6 status readers. These and all behavior remain `UNRUN`; exact four-base presence is for the broker to record.
- R12/R13 N7 design v2 `/Users/deniskopylov/.codex/scratch/e02-r2-r12-r13-n7-dataflow-design-v2-20260925.md@sha256:423792e2be7410cca94ff3877366b3bc67d7a850c8f2103319a7fc8fafc100fe` with delta review `/Users/deniskopylov/.codex/scratch/e02-r2-r12-r13-n7-dataflow-design-v2-review-20260925.md@sha256:ceacc5fc6e5e0d007a977b658001d82d6a510a2547d2d20978b9b27228e5fec8` is `GO` for bounded design only. It names 64 whole-file P41 candidates; changed-input disjointness and all tests remain `UNRUN`. The post-overlay N4 context producer and served DS15 positive remain missing. R12/R13 earlier standalone-plan NO-GO remains superseded only for the reviewed bounded v2 scope.
- B194's independent review adds `tests/unit/scientist/nodes/test_decision_packet_node_v3.py` to the P41 set, and `tests/unit/scientist/nodes/builtins/decide/test__decision_packet_contracts.py` if its contract changes. The full B194 file list is in `B194_HELD_TASK.md`; it is a task queue, not a run receipt.
- P41 data-state adapter v2 review `/Users/deniskopylov/.codex/scratch/e02-r2-p41-adapter-v2-independent-review-20260925.md@sha256:4cc4f330c44440a9f325e87745e7e865d64bafe36d8c7a49d0b131200f02e13b` is `NO-GO`: symlinked `tests/conftest.py` resolves the pinned checkout, risking marker/cache/write/import leakage; 11.22 GiB available leaves only 1.22 GiB above the 10 GiB hard floor and no peak bound. Four data-state cells remain `UNRUN`; no adapter run is admitted.
- B109's P27 task has a six-file / 24-cell focused denominator, with `test_pareto.py` already measured at 8/25/8/25 and five whole files absent from the 100-path matrix. `B109_P27_TASK.md` lists them; broker admission and served behavior are `UNRUN`.

## Live write leases after `dcaddbfd0` (2026-09-29)

This current handoff supersedes older task-status rows above only for the named files. The root remains the sole writer of `codex/e02-r2`; separate candidate worktrees may run read-only checks concurrently within the current 8 GiB disk floor and five-light-group CPU limit. No source tree is edited during its own test run.

| Writer / branch | Exclusive current files | Handoff |
|---|---|---|
| R1 owner-station writer, `codex/e02-r2-r1-sim-gateway` after its clean merge of `dcaddbfd0` | `tests/unit/runtime/http/test_control_service_di.py`, `tests/unit/runtime/http/test_normative_generation_bridge.py`, `tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py`, `tests/integration/runtime_quality/test_evaluation_safety_promotion_bridge.py`; indispensable R1 Control/context owner files only after the writer records their exact additions to this lease | Restore the controlled N4→N5 source/context witness and candidate-only preserving control. The older R2-history row's mention of `test_normative_generation_bridge.py` is deferred until this R1 writer commits and hands off. No served S8 positive is inferred while OP-R1-TIME and OP-R1-S8 are open. |
| R2 historical-v1 test writer, `codex/e02-r2-r13-selected-row-candidate` | `tests/unit/runtime/quality/test_generation_cycle_history.py` only | Correct the stale source-free S8-v1 expectation; source/schema and `test_normative_generation_bridge.py` are excluded. A wheel-build tooling failure is `UNRUN`, not a product red. R2 currentness/source work waits for the R1 handoff. |
| R13 active-overlay fixture patch, root integration worktree after independent review | `tests/unit/runtime/quality/test_acquisition_overlay_visibility.py` only | Pass the fixture's exact passport store at three active-projection consumers, then run focused positives and the selected-row mutation negative. Do not change passport verification or the runtime store owner. |

The same-head full-file and four-base outcomes for these fresh edits remain `UNRUN` until measured. Historical JUnits retain their original source/test identity; no current lease silently upgrades an earlier receipt.

## Live N8 owner-transition lease after `68c40400b` (2026-09-29)

The R2 historical-v1 test and R13 active-overlay fixture rows above are complete at `246263467` and `c19944773`, respectively; their file leases are released. The R1 owner-station writer retains the four test paths in the preceding table. Root remains the only writer to `codex/e02-r2`.

One N8 owner-transition writer on the reused `codex/e02-r2-r13-selected-row-candidate` branch exclusively owns `policy-engine/architecture/production_quality/method_catalog_dependency_profiles.toml`, `policy-engine/architecture/production_quality/method_catalog_dependency_authority.toml`, `policy-engine/architecture/policy_design_case/layer3_gy_n8_dependency_discriminant.json`, `policy-engine/architecture/generated_artifacts.toml`, and `policy-engine/docs/reference/generated-artifacts.md`. It must first merge the latest canonical branch append-only, then use the registered owners. Commit the two profile/authority files as one clean boundary and derive the new source freeze from that commit; commit the three companion/registration/rendered files as the next boundary. No other candidate edits those five paths until independent review and root integration.

This lease is limited to the existing N8 purpose and the exact dependency bytes already declared by `e66388e34`. `team-foundry` remains the registered approval owner of the generated companion. No trust pin, epoch, receipt, broad sync, register row, or plan file is leased. The 30 N8 tests must reach their assertions before they can be counted as semantic witnesses; a passing owner check alone establishes only replay of the refreshed inputs. The unresolved owner approval is recorded in `OPEN_PREMISES.md` and does not suspend other engineering.

## R2 typed-currentness consumer lease after R1 integration `8b206b254` (2026-09-29)

The R1 candidate-intent source/test lease is released after independent GO, commit `bd6963dc6`, and integration `8b206b254`. One R2 writer may reuse the now-clean `codex/e02-r2-r1-sim-gateway` worktree/branch after merging current `codex/e02-r2` append-only. Its exclusive write set is `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`, `policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py`, `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py`, `policy-engine/tests/unit/runtime/quality/test_s8_blocked_generation_owner.py`, `policy-engine/tests/unit/runtime/quality/test_generation_cycle_history.py`, and `policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py`. Ask root to amend this lease before any additional file, generated family, or shared R1 test edit.

The property is byte-exact historical N6 replay plus a separately typed currentness observation at S8 admission and current projection. Only history/intrinsic/source-custody-valid runs with currentness `UNRUN` or stale may produce a persisted blocked, no-ranking S8 result; mixed `FAIL`, missing custody and terminal-blocked cases keep their refusal. Any new hashed S8 field needs a schema bump and v1 historical serializer. The existing Confidence Ledger and N6 census remain the owners; no packaged issuer, trust pin, epoch or receipt is leased. Positive packaged authority remains an OPEN_PREMISES item. The candidate needs a marker-retaining currentness-removal probe, current signed-owner preserving control, source-free historical replay, and a served consumer witness or explicit `UNRUN` for the missing source. Review every source/test delta before integration. The N8 five-file lease above remains disjoint.

## R1 EvalSafety terminal-source diagnostic lease (2026-09-29)

The prior R1 owner-station candidate has been integrated at `8b206b254`; its four-test-file lease above is released. The N8 candidate was integrated at `b2e0cb633` and its five-file lease is released. One R1 diagnostic writer may reuse the clean `codex/e02-r2-r13-selected-row-candidate` worktree after merging current `codex/e02-r2` append-only. Its exclusive initial write set is `policy-engine/tests/integration/runtime_quality/test_evaluation_safety_promotion_bridge.py` only. It first proves a positive strict Core terminal-source readback, then records the exact inner cause if the existing byte-tamper selector still stops before the CAS read. Production changes require an exact additional lease after that cause is measured. It must preserve the byte-tamper removal probe and the unmutated source control. This test path is disjoint from the active six-file R2 currentness lease. No heavy integration test may start while free disk is below the 8 GiB floor plus its measured peak scratch requirement.

## B26 / SIM-03 numerical-basis owner lease (2026-09-29)

The R2 modern-S8 six-file candidate lease is released after its setup red at the synthetic N4 gate; the candidate branch is clean at `d183032e8`. `OPEN_PREMISES.md` records the reviewed bounded source-custody fixture stop at `843a46b9b`. No modern S8 currentness behavior was exercised or closed. The canonical source/test tree is unchanged from the B26 independent-review head `c07065da9` through `843a46b9b`, so its seven direct-importer files remain the pre-edit P41 set; the writer must recheck the exact slice-base census after merging the latest canonical branch.

One B26 writer may reuse the clean `codex/e02-r2-r1-sim-gateway` candidate worktree after merging `codex/e02-r2` append-only. Its exclusive initial write set is `policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py`, `policy-engine/tests/unit/remediation/test_sim_03.py`, and `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py`. No `generation_cycle.py`, generated family, store owner or other R-class file is leased. This lease implements the reviewed B26 v2 plan at `/Users/deniskopylov/.codex/scratch/e02-r2-b26-sim03-closure-plan-20260929-v2.md@sha256:44cf54f0e761483287955cb44e3aa1664b7e6f623d006b9e071be4d705a1f1a8` with independent GO `/Users/deniskopylov/.codex/scratch/e02-b26-independent-review-20260929/REVIEW.md@sha256:5e79dd94f56c980dee237b32adeb41dc204b378690b5b428117f4e49d6488806` and its delta review. The implementation must distinguish incomplete numerical basis from engine-selection failure, use exact requested atoms/outcomes/horizon points, and exercise the real `GenerationCycleController` route with default N5/N8 ports and runtime-supplied store. Four-plus atom cancellation stays bounded `unsupported`; no new schema or authority is implied. Test first, preserve additive/non-additive controls, and run the marker-retaining removal probe. Numerical/native tests have one exclusive process slot with `JAX_PLATFORMS=cpu`, measured peak disk/RAM, and at least 8 GiB free disk. Freeze the candidate before review and integration.

## R1 owner-context test-fixture correction lease (2026-09-29)

The complete current-head `test_control_service_di.py` run at `0716402ea` has 41 cases, 40 PASS and one R1-gate failure in `test_direct_recursive_http_and_replay_share_one_owner_context_ref`; `BASELINES.md` pins the JUnit. The test asks for a protected epoch-subject replay while passing an explicit N4 producer without an owner-bound context. Under Denis's conditional owner-bound ruling, a test of that protected path must supply the actual typed context through the existing owner/resolver and runtime store. An ordinary no-owner candidate control must continue with its typed limitation; the test fixture must not mint S8 or promotion authority.

One R1 candidate writer may reuse the clean branch-attached `codex/e02-r2-r13-selected-row-candidate` worktree at `/Users/deniskopylov/.codex/worktrees/e02-r7-r8-probes/polisyos`, first merging current `codex/e02-r2` append-only. Its **only initial editable path** is `policy-engine/tests/unit/runtime/http/test_control_service_di.py`. Restore the failing test's legitimate owner context without changing a production gate, using the existing context producer/resolver and retaining exact problem/run/store bindings. First confirm the red; then run the protected positive, foreign/missing-context negative and no-owner candidate preserving control. If production code or any additional test path proves necessary, stop editing and request an exact lease amendment. No same-file concurrent writer exists; B26's three-file lease is disjoint. The candidate needs independent delta review before integration, and a source-corrected selector is not R1 class closure or four-base P41 closure.

**Superseded at the 2026-09-29 current-head reconciliation.** Commit
`fba37baf1` already changed that exact selector into a protected no-context
refusal; commit `7a2fd5f45` added the ordinary candidate control. The complete
Control file passed 41/41 at both `8ca88499f` and `7a2fd5f45`; the latter
has a marker-retaining eager-WMR removal probe. `OPEN_PREMISES.md` records the
protected refusal and the separate served candidate N4→N5 witness. Thus the
one-file fixture lease above is **released**, and nobody should restore its
old protected-positive expectation. Its historic 40/41 result at `0716402ea`
remains a valid earlier observation, not a current red. The served
persist→resolve and protected source/S8 authority witnesses plus final-blob
four-base P41 remain open under R1; they require a fresh exact lease. The
candidate branch's append-only merge `44e35ecd9` is clean and has the same
tree as canonical `acc4de867`; it made no R1 test edit.

## B111 assessment-index integrity lease (2026-09-29)

Root alone owns `policy-engine/src/polisyos/scientist/methods/autotune/pareto.py` and `policy-engine/tests/unit/scientist/methods/autotune/test_pareto.py` for the reviewed two-file slice. The B109 test-only change and its 31/31 whole-file result at `0cf4afa19` are the pre-edit current evidence; the post-B109 four-base replay remains `UNRUN` under the resource continuation. No other writer may edit these files until root commits and releases this lease. The exact write set excludes registry, output report, generated families, objective basis, and governed artifacts.

The property is internal, sequence-local assessment consistency: each omission index is unique and within declared `input_count`, and the validated omission sequence cannot be mutated afterward. Test malformed and reconstructed DTOs first, then preserve duplicate candidate refs at distinct indices and the finite subfront under a separate invalid input. A marker-retaining removal of the index predicate must turn the negative red; a preserving control must stay green. Review this slice independently before any B111 status change. The wider registry-to-report omission propagation, source-bound objective basis, served owner/provider, and complete four-base replay remain residuals, so B111 stays `partial`.

## R11 final-action reconciliation after N7 re-entry (2026-09-29)

The complete source/consumer census is `/Users/deniskopylov/.codex/scratch/e02-r11-consumer-census-20260929/R11_BLOCKED_CONSUMER_CENSUS.md@sha256:9592138b4a7d8a9014005b82b8e276a1a3881055de53156f8c42b1e0899475b9`. Denis ruled that any `blocked` N6 action is terminal for N9. The existing owner checks the first VOI action before N7, but N7 re-entry recomputes it after that check; a final `blocked` action can leave the run marked `completed` before the N9 branch. Independent source review gives a conditional GO for one owner-level reconciliation and one touched test file; its formal memo remains pending. This is the same R11 class at the final action boundary (P40), not a new instance exception.

One R11 candidate writer may reuse the clean branch-attached `codex/e02-r2-r1-sim-gateway` worktree at `/Users/deniskopylov/.codex/worktrees/e02-r2-r1-sim-gateway/polisyos`, first merging current `codex/e02-r2` append-only. Its **exclusive source/test write set** is `policy-engine/src/polisyos/runtime/quality/generation_cycle.py` and `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py`. The owner helper must reconcile the final in-memory cycle/action after any N7 re-entry and before N9; no Scientist scheduler vocabulary, separate N7 gate, generated family, receipt or epoch is leased. Test first with the real N7 re-entry fixture: second decision `blocked` yields coherent blocked run/recursive front and no N9 certification; ordinary re-entered `stop` remains completed candidate computation. A marker-retaining removal of the final reconciliation must turn the targeted test red. Do not claim a promotion-spy call unless source custody and typed currentness actually permit reaching that spy; the existing `test_nonblocked_scheduler_stop_still_reaches_n9_owner` proves zero calls under unavailable census. Retain current base-passing controls, run bounded current tests, and record the touched whole-file four-base replay as `UNRUN` until measured. Freeze for independent patch review before root integration.

This R11 source lease precedes and excludes the R2 temporal-history/currentness slice's `generation_cycle.py` edit. R2's exact lease and source pin must be refreshed after R11 integration; no simultaneous writer may edit that shared file. The candidate worktree already has the read-only production-data symlink and local venv. One test process at a time for this candidate; preserve at least 8 GiB free disk.

## R11 handoff and R2 temporal S8 lease after `c0d5a0570` (2026-09-29)

The R11 two-file source/test lease above is released. Its reviewed patch is integrated at `c0d5a0570`; five focused current-head tests pass and the marker-retaining final-call removal probe is red. The independent bounded GO is `/Users/deniskopylov/.codex/scratch/e02-r11-post-n7-implementation-20260929/R11_POST_N7_V2_REVIEW.md@sha256:aa9c95d69b0cfdd8c3d140342dc202e7522c8bcd7f639816a16e9a2afaca0d1a`. The earlier lease's post-N7 `stop` phrase is now bounded: the real fixture legitimately produces `escalate`; a typed grounded-abstention `stop` is a helper-level preserving control, while an owner-produced end-to-end N7 `stop` remains `UNRUN` and belongs in `OPEN_PREMISES.md`. R11 and the touched whole-file four-base replay are not closed.

One R2 temporal replay candidate writer may reuse the R11 candidate worktree only after it is clean and branch-attached and its canonical merge includes `c0d5a0570` without a conflict. Root alone integrates reviewed changes into `codex/e02-r2`. The **exclusive source write set** is `policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py`, `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`, `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py`, and `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`. The **exclusive test write set** is `policy-engine/tests/unit/runtime/quality/test_s8_blocked_generation_owner.py`, `policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py`, and, only if the validator interface changes, `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py`. Mandatory companions are one new `release-fragments/unreleased/2026-09-29-e02-r2-s8-disposition-v2.toml` and `docs/how-to/normative-generation-disposition-v2-migration.md`. Any additional source/test/generated path needs an amended lease before editing.

Input Git blobs at the `c0d5a0570` handoff: value-choice owner `f42f5b2b4be92fe723c488985c9861ef3da17aa6`; N6 owner `16b3d057ddbe2d92a0077fa883dca6b209e316f2`; HTTP composition `471a80e2db0d93cec5a4c19d5970c1ddb9182e63`; served lifecycle `44408ec780524453e39650070031f0c8a6875bc4`; S8 owner test `ce414fa065efdb3051242fd255bb23482f56a2d6`; normative bridge test `34951136ed03ab5d1424a2b7eb60dc1e66b67cd3`; N6 owner test `e3f06169b67fa07373a645f9cbed92dc03115a58`. Refresh these only after a recorded intervening canonical source/test change, never silently.

The independently reviewed design is `/Users/deniskopylov/.codex/scratch/e02-r2-temporal-replay-design-20260929/R2_TEMPORAL_REPLAY_DESIGN.md@sha256:ebf761dfc55084530e6bd54dfc2e63c553ce14b9ed069cf3ec838367db5340f0` with bounded GO `/Users/deniskopylov/.codex/scratch/e02-r2-temporal-replay-design-20260929/INDEPENDENT_REVIEW.md@sha256:7a802858d170a7d7aeab5b2581c1fff7cf4262830ea5dbfddba23bfe8d7dd94c`. Freeze v1 bytes, put the complete single owner currentness observation only in a versioned internal v2 envelope, replay historical bytes without live currentness, and project current authority through a fresh observation. Legacy v1 admission currentness remains unknown and cannot be upgraded by later PASS. Test first with fixed N6/disposition bytes and changed live observation; marker-retaining removal of the history/current split and removal of the no-upgrade check must each turn red. Preserve an ordinary candidate path and the served job readers. Do not claim a positive S8 issuer, census or publication. One focused test process for this candidate; preserve the 8 GiB disk floor and 20–30% free RAM.

The older R2 typed-currentness lease after `8b206b254` and the later six-file modern-S8 lease are superseded by this temporal-history lease; their candidate was stopped at the synthetic N4 setup red and neither owns a current file. The B26/SIM-03 three-file candidate lease above was integrated and released at `cd9e935e5` after independent review; no B26 writer remains. Its `test_generation_cycle.py` path is therefore available to R2 only under the conditional test scope and exact `e3f06169b67fa07373a645f9cbed92dc03115a58` input pin stated here. Until root confirms that the one-observation N6 inspection actually needs a changed N6 owner test, the R2 writer uses the two unconditional test paths; any extra test scope must be recorded before editing.

## LA-031 D3 registered-output witness lease (2026-09-29)

Root owns exactly `policy-engine/tests/unit/data_forge/domains/ukraine/test_orchestrator.py` for this bounded H-class witness. No production module, generated family, receipt, epoch, or other test file is leased. Its pre-edit Git blob is `767a9b479c5495742db1107a143caede1d47d4b2` at all four pinned refs; the controlled whole-file replay at integration `447ccdb98204c9ad46c57eba0710844eba7e5921` passed 3/3 on each of 78187878e, 00d946c2b, 5fd3ebcc1 and integration, with zero shared pass-to-fail (`raw/p41-custom-20260929T154927Z-47620/results.json@sha256:f1f11cceca85a19f04d89206a37d7650fb01211efd8eb7a9b15cfa0dfc1df627`). The earlier three-cell scratch receipt is supplementary, not a substitute for that four-cell result.

The reviewed test design is `/Users/deniskopylov/.codex/scratch/e02-la031-d3-design-20260929/LA031_D3_BEHAVIORAL_DESIGN.md@sha256:17a812d594305ab9907b7650cb38a59fe959b75c7460bd918441261542c42de6` with conditional GO `/Users/deniskopylov/.codex/scratch/e02-la031-d3-independent-review-20260929/LA031_D3_DESIGN_REVIEW.md@sha256:dc35035a0f5f754ef6db6d56822d13ea0f38166e270cc2848368a785fd986c52`. Exercise the real D3 registry through `UkraineDataOrchestrator.build_stage` on an explicit-period controlled fixture, compare selected outputs/content/findings/warnings/writes with the pre-split execution base, and keep a D4 purpose-limited candidate-work control. Mutate one D3 output value with a recomputed self-consistent artifact digest while retaining registry/output markers; the semantic oracle must turn red. The optional D3 input-inventory concern is a separate P40 class in `OPEN_PREMISES.md`; a D3 import/output witness neither closes that concern nor all of LA-031.

The LA-031 D3 test lease is released at `fcaa325a3967c5751b1d6e0493590c0c4c5f2b3b`. Its independently reviewed bounded witness and exact-source removal probe are recorded in `/Users/deniskopylov/.codex/scratch/e02-la031-d3-implementation-20260929/LA031_D3_WITNESS_V2_REVIEW.md@sha256:7105f4c0e96c65be57688f4561ae93af65fbff8702d78c90eeae5dfa3fffbc78`; the post-edit four-base whole-file replay is `raw/p41-custom-20260929T161900Z-53537/results.json@sha256:a9047ffad9989c8d0037489deac339616d572c5a8547af021d746b41d3c35c4a` (three historical cells 3/3, current 5/5, zero shared pass-to-fail). The preceding hypothesis about optional D3 inputs has now been reproduced separately: `OPEN_PREMISES.md` and the register proposal must cite `optional-probe-v2.json@sha256:b0c89a52af4f965279e72e273f1c5de679b0e5956e946224eb795440a708c9a8`. It does not change the LA-031 held status.

## B153 CAS fixed-lock witness lease (2026-09-29)

Root owns only `policy-engine/tests/unit/remediation/test_cas_01.py` for the B153 bounded witness. The production `policy-engine/src/polisyos/core/artifacts/store.py` remains under R13/P31 ownership and must not be edited in this slice. At clean integration `e31b13bd3`, the strict four-base whole-file replay `raw/p41-custom-20260929T155325Z-48474/results.json@sha256:67d63a94fc404f38d4b0f594db5c0675ca2f20f78219fdf1f824de1d5b0d68f4` found the file missing at Execution and Main, E02 head 5/5 passing, integration 16/16 passing. The intervening LA-031 commit changes only the Ukraine orchestrator test, so the B153 test and store input blobs are unchanged. The reviewed owner-first design is `/Users/deniskopylov/.codex/scratch/e02-b153-immediate-candidate-20260929/B153_IMMEDIATE_CLOSURE_REVIEW.md@sha256:951583d6638bcf4d06a90556b6ba5ab408ff53a7808cf973c0b03826d1f32752`.

The writer must enumerate 3,000 deterministic ArtifactIDs and returned lock identities, preserve same-ID live waiter exclusion, and read back distinct payload-derived IDs that collide on one stripe without aliasing bytes or manifests. In isolated scratch, marker-retaining removal of bounded residency and of same-key fencing must turn the exact witness red. A benign collision is a property-preserving control. No generated artifact or epoch is in the write set. Keep the 8 GiB disk floor and run no more than two light test process groups while R2/B111 writers are active. Review before integration, then repeat the four-base whole-file replay. B153 closure remains unclaimed until those receipts exist.

**B153 exception-waiter follow-on (2026-09-29).** The first bounded lock
witness is integrated and its complete current file passed 17/17 at the
recorded `4be6d38e6` evidence cut. Root retains the same exclusive one-file
test lease; the production CAS owner and all other files remain read-only.
Add `test_exception_releases_same_id_lock_for_scoped_view_waiter` as the exact
remaining source-card discriminator. Seed a default manifest, hold the first
distinct-view writer inside the real same-ID CAS lock at a controlled I/O
failure, observe the second distinct-view writer at its actual lock acquire
attempt, then release the first to raise. Require the second to complete and
read back its exact bytes and typed manifest; the failed first view must not
be presented as persisted. A repeated same-profile put is the preserving
control. A marker-retaining removal of the lock or of exception release must
turn this test red. The four-base cells for the new selector are `UNRUN` until
disk is above the 8 GiB floor; the existing 17/17 result is not a current-head
or post-edit claim. Freeze the test and source during any run, then obtain
independent review before treating B153 as closed. The detailed gap and
receipts are in `BASELINES.md` under `B153 bounded progress`.

## B73 fresh-store checkpoint witness lease (2026-09-29)

Root owns only `policy-engine/tests/integration/scientist/test_checkpoint_resume.py` for this RES-02/B73 witness. The `AsyncWorkflowExecutor` and checkpoint owners are read-only here. The strict pre-edit four-base whole-file replay at clean `4be6d38e6` is `raw/p41-custom-20260929T163814Z-57383/results.json@sha256:5ff7925882ee9f6cc7dedf16bba29f0441a3c65346857cc758984bed6508d782`: Execution, E02 and Main each pass their seven cases; integration passes nine, including two current-only cases, with no common pass-to-fail. The exact target is `test_parallel_tier_checkpoint_survives_stop_without_reapplying_any_peer`.

The first same-process fresh-store variant was independently rejected as redundant: the old test already read the disk and checked the complete frontier. After the simulated stop, spawn a fresh child process that constructs its own `FileSystemCAS` from the root path, reads the persisted merged peer state and completion frontier, and resumes from that head. Require zero peer reapplications in the child and one final-node execution. A marker-retaining mutation of `_handle_tier_checkpoint` must persist merged state with only one completed peer and make the child observer red; source files stay frozen during tests. This proves the built-in CAS producer and local process-boundary reader/consumer. Remote workers, externally exactly-once effects, arbitrary hooks and B72's outcome transport remain residuals. Review the final one-file patch independently before commit, then rerun all four whole-file cells. Keep the 8 GiB disk floor and at least 25% free RAM.

## B111 persisted-artifact v1→v3 documentation supersession (2026-09-29)

This dated amendment supersedes only the initial B111 lease's v2 schema
target. The implementation at `fdd65e889` changes the ordinary persisted
`PolicyFrontierReport` and `RejectedAlternativesSummary` path directly from
v1 to v3. V1 remains byte-exact historical replay; schema v2 for these two
DTO kinds was an unintegrated draft and is unsupported/rejected. Do not
document a v2 writer, reader, serializer, or replay path for these two kinds;
`ParetoRegistrySnapshot` is a separate artifact with a v2.0 writer.

The docs rebase uses candidate commits `5b2e45ffb` and `23edf1ab5` as
material and may update only these B111-owned surfaces: this file,
`policy-engine/release-fragments/unreleased/2026-09-29-e02-r2-b111-frontier-v3.toml`,
`policy-engine/ops/migrations/ir/README.md`,
`policy-engine/docs/runbooks/migration-release-promotion.md`,
`policy-engine/src/polisyos/scientist/policy_design/README.md`,
`policy-engine/src/polisyos/scientist/methods/search/README.md`, and
`policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/OPEN_PREMISES.md`.
Root alone integrates. Do not edit source/tests, migration-class or promotion-gate
contracts, generated families, DEBT-REGISTER, LEDGER, or GY/Atlas plans.

The v3 DTO validator compares caller-supplied source-feasible identities with
the registry projection, checks duplicate/overlap with the caller-supplied
unknown set, and requires the projection assessment status to be
`denominator_limited` when the sets differ or the unknown set is nonempty;
it does not authenticate unknown identities. The ordinary
`PolicyArtifactBuilder._build_frontier_report` path does not receive an
independent source population or unknown-eligibility input: it copies
`projection.eligible_candidate_hashes` into `source_feasible_candidate_hashes`
and leaves `eligibility_unknown_candidate_hashes` at its empty default. The
resulting equality is self-derived, not a served observation of the source
population; it cannot detect a candidate omitted before registry projection.
Do not claim a served source/registry reconciliation or external completeness.
A missing registry remains basis-limited and unranked. The external candidate
universe and deployed artifact/reader inventory remain not established.

No-rewrite compatibility evidence has not been accepted by the current
`ir_migration_review` owner contract, so promotion stays held. B111 also retains
separate numerical/selector engineering residuals and the source-bound
objective-basis/served-registry residual; it remains `partial`.

**Pattern pass.** The stale v2 wording is one P40 class; correct every owned
B111 surface together. P04/P07 preserve basis-vs-denominator status and v1-only
history. P10/P37/P38 state the property/code divergence: the property is
coverage of the external source universe; the DTO validates supplied values,
while the ordinary builder supplies the registry set as its own source set and
no unknown set. An eligible upstream candidate omitted before that projection
is the divergent case. P01/P02 keep owner approval and operational rollout
evidence open. Missing capability labels are `producer_missing` and
`bridge_missing` for an independent source/eligibility input, `surface_missing`
for external candidate and deployment/reader inventories,
`verification_missing` for no-rewrite gate acceptance, and
`semantic_test_missing` for the producer-input omission falsifier. Acceptance
is v1/v3-only language, no served-observation or global-completeness claim,
explicit held promotion, and separate source-population, deployment, and owner
contract premises. B111 remains `partial`.

## B111 finite ranking and no-fallback champion lease (2026-09-29)

The earlier broad registry-to-result B111 lease is complete at its reviewed
v3 boundary. This amendment gives one direct B111 writer the next, disjoint
numerical slice. No other writer may edit its five paths until root reviews
and integrates or rejects the candidate. The exclusive source write set is
`policy-engine/src/polisyos/scientist/policy_design/objectives.py`,
`policy-engine/src/polisyos/scientist/policy_design/search.py`, and
`policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py`.
The exclusive test write set is
`policy-engine/tests/unit/scientist/policy_design/test_phase_b_hierarchical_search.py`
and
`policy-engine/tests/unit/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py`.
These five paths are released from any older B111 lease only for this ordered
slice; a wider registry or report edit needs another explicit lease.

Reuse the existing clean `codex/e02-r2-b111-candidate` worktree at
`/Users/deniskopylov/.codex/scratch/e02-r2-b111-candidate-20260928/tree`.
First merge current `codex/e02-r2` into its attached candidate branch
append-only; stop if that merge has conflicts. Its `.venv` and
`production_data` are symlinks; neither may be copied. Verify `git status -sb`
before each commit. Root alone integrates the reviewed candidate. Do not edit
generated families, epochs, receipts, debt register, GY/Atlas plans, or
`PolicyOS_E02R2/` records from the candidate.

**Property.** Recompute finite validity at the shared ranking intake for all
decision coordinates and derived rank expressions, including welfare plus
employment. An evaluated invalid row is typed unassessed with its identity and
reason; it cannot win via NaN, infinity, a zero sentinel, or input order. A
mixed set ranks only finite rows and carries a candidate-band limitation. If
evaluated rows exist but all are invalid, emit a typed no-champion result and
persist no champion ID, Trinity ref, or frontier artifact. Zero evaluated rows
is distinct and may retain its existing fallback behavior. Preserve finite
permutation controls. Use the existing node status vocabulary; do not imply
authority or make an unsupported global Pareto claim.

Write behavioral tests first. A marker-retaining removal of the finite
assessment must turn the real selector test red with positive infinity and
NaN before/after a finite row. A property-preserving finite input permutation
must stay green. The first class finding is raw non-finite selection; the
derived welfare-plus-employment overflow is the same class one level deeper
(P40), so the shared intake must cover both. For P37/P38, the desired property
is finite-only champion election; raw tuple ordering is the current proxy,
and positive infinity winning or NaN order-dependence is the divergent case.
The production source of non-finite vectors and N9 promotion path remain
`not_established`; do not claim served or authority-grade closure.

The separate finite-coordinate hypervolume overflow requires a typed
indicator through persisted registry/report readers and a deployed-version
inventory. It is a bounded no-code residual in this slice; do not encode
unavailable as zero, clamp, or infinity. The objective basis and independent
source-population bridge remain open premises. B111 stays `partial`.

The design record is
`/Users/deniskopylov/.codex/scratch/e02-b111-docs-rebase-20260929/B111_NUMERICAL_CLASS_DESIGN.md@sha256:45f1249f29608a0b7928f15fb24e3262a35906a591df6316097338d5289b8386`.
The pre-edit two-file whole-file P41 replay is eight requested cells across
Execution, E02 head, Main, and integration. All eight are `UNRUN` while disk
free is below Denis's 8 GiB floor; this is not an inherited-red claim. The
separately recorded three-file B111 cohort is 12/12 cells, not this two-file
set or the full Appendix A/B denominator of 21 files and 74 selectors. No
heavy tests or fresh environment may start below the floor. Static lint and
compile are allowed if free space remains stable. Freeze source before any
test, run only the smallest informative checks once admitted, and obtain an
independent patch review before root integration.

## R2 outer v1 composition replay lease (2026-09-30)

Root holds exactly these three paths for the next ordered R2 history slice:
`policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py`,
`policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py`, and
`policy-engine/tests/unit/runtime/quality/test_generation_cycle_history.py`.
The earlier R1 fixture lease was released at `32e036dc69`; the R13-W1 writer
stopped with a clean separate candidate at `3c355bd0f` and owns none of these
paths. No other candidate may edit them until root releases this lease. The
source and two test blobs at clean pre-edit `acc4e7584` are respectively
`a435a317c4050551ac9dd9f34a1ee41e75f64fce`,
`4471c1a4a6c65d34606c017f36b1d55191d1528d`, and
`f94ce5e006e93887dba28bb79ac1d2c6fcb5b4f4`.

**Property and limit.** The existing outer `NormativeRunDisposition.v1`
producer and historical reader must share one frozen v1 wire projection. The
reader resolves raw CAS bytes and checks the ref hash, kind, schema name and
version, internal v1 literal, typed payload, and exact v1 bytes before the
existing leaf-membership/composition checks. Currentness remains a separate
typed observation; historical replay grants no current S8/N9 authority. P38's
divergent case is a decodable whitespace/key-order JSON variant with a valid
new CAS ref and unchanged markers, or wrong outer manifest schema. P40 keeps
this within R2's historical-replay class; P07 semantic rule-version replay
remains a bounded residual. The reviewed design is
`/Users/deniskopylov/.codex/scratch/e02r2-r2-next-slice-design-20260929.md@sha256:b1dacb9affe9426fca5af6a9ed96fd0e3fe2348c6191f9719147e3b29fb7d42c`
and the independent bounded GO is
`/Users/deniskopylov/.codex/scratch/e02r2-r2-next-slice-design-review-20260930.md@sha256:bcc2e1962ba2889f0d1453e0a4c28dd24ac1097990bf13682a798036b01f044b`.

**Pre-edit P41 admission.** The two whole test files at four refs are eight
slots. Git verifies three `MISSING` history-file slots (Execution, E02, Main)
and five present slots (four bridge-file slots plus current history). All five
present tests are `UNRUN` for this slice while disk is below Denis's 8 GiB
floor; they are not inherited reds. Write the noncanonical and wrong-schema
tests first, then owner code. A marker-retaining byte-guard removal must turn
the noncanonical test red, while canonical v1 history replays without a live
currentness call and fresh unknown-currentness projection stays blocked. The
installed-wheel owner replay needs a valid compiled/leaf/outer fixture; a
direct owner call in that child is not a served ControlPlaneService proof.
Record any unavailable installed served witness as `UNRUN`. Do not edit N6,
S8 leaf, RunLifecycle, generated families, epochs, plans or register. Static
checks may run; no pytest/build below the disk floor.

## B111 downstream finite-admission amendment (2026-09-30)

The first five-file B111 candidate at `915c04497a1404cf5024efccadb06a38303ca5d0`
is a clean, attached branch, but its independent review is **NO-GO**:
`/Users/deniskopylov/.codex/scratch/e02-r2-b111-candidate-20260928/B111-independent-review.md@sha256:5c431d4186c7ad540ab303eefd51ca3f0e029fd1bd4f7d07a6cd3bcc88de997d`.
This amendment keeps its five existing leased paths and gives the same writer
exclusive access to three additional source owners:
`policy-engine/src/polisyos/scientist/methods/search/strategies/adapter.py`,
`policy-engine/src/polisyos/scientist/methods/search/strategies/multi_objective.py`,
and `policy-engine/src/polisyos/scientist/methods/search/pareto_registry.py`;
and four mirrored test paths:
`policy-engine/tests/unit/scientist/search/strategies/test_adapter.py`,
`policy-engine/tests/unit/scientist/search/strategies/test_multi_objective.py`,
`policy-engine/tests/unit/scientist/search/test_phase_b_policy_runtime.py`, and
`policy-engine/tests/unit/scientist/search/test_pareto_transfer.py`.
These seven added paths have candidate-HEAD blobs, in the order just listed:
`fa68d647f511abd5851224ca66b00678ce4eda11`,
`75b53531047e43e31dd4d12e6991ee03f6da7a79`,
`ba4244c0c904224a0fa73cb8d4d10feb4e8acf37`,
`01f309e3242a156c9b65df3fbb4efe29c026cf6c`,
`e3e47990c5279e2378ab3aeb784854a08181b694`,
`72714f78c14adcff1f5ec83f570eb188cccfd1bf`, and
`43f738fab66ab5ee6b48cd013fea2f13a5b26fb6`.
The writer merges current `codex/e02-r2` append-only before editing and stops
on conflicts. No other writer may touch these twelve paths during this lease.

**P40 bucket and acceptance.** Non-finite raw values entering champion choice,
strategy training, or either registry intake are the same downstream-bypass
class; repair the shared admission/consumption mechanism, not one caller.
Present-but-malformed stage-B evaluation collapsing to the zero-evaluation
fallback is a separate P04 status-lattice class. Reuse `SearchIteration`'s
existing `missing`, `valid`, `invalid`, `unassessed` vocabulary and retain
identity/reason; only truly absent evaluations may take the zero-evaluated
fallback. The missing `rank_assessment` test fixture is a test-interface
regression: supply a typed assessment, not a permissive runtime default.
Exercise both production `ParetoRegistry.update` callers through its shared
owner intake. A finite rank key with another non-finite raw objective channel
must stay unassessed; an all-invalid set must produce no champion, frontier,
or training row. Keep finite mixed and zero-evaluation controls. Avoid a new
schema or status enum where the existing owner fields carry the distinction.
The six touched whole test files at four refs are 24 P41 slots, **UNRUN** while
free disk is below the 8 GiB floor; no inherited-red inference is authorized.
Use only static checks until the floor is restored, then run focused witnesses
and marker-retaining removal probes before a new independent code review.
