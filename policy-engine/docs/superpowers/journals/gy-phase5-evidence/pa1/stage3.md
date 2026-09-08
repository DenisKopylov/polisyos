# PA1-A — stage 3 implementation and falsifiers (2026-09-08)

**Root review disposition:** this first frozen package is a completed worker and
replay mechanism, not full PA1 closeout. Independent finding PA1-R01 in
`independent-temporal-intake.json` shows that evidence signed after the worker's
actual source exists produces a new sidecar through the service owner, but neither
current job reader consumes that new sidecar. This is a NEW temporal bridge class
(P01/P02). The recommendation below was conditional on review and is superseded
until the post-compilation intake/head attachment is implemented and falsified.
The first package is retained in a coherent commit; its correction appends.

Source freeze handed to the root agent for independent review and the one final
integration/guardrail wave. No commit, stash, auxiliary worktree, push, ledger or
debt-register edit was made by this subtask. All work is on the user-authorized
`codex/gy-phase5-execution` worktree. Repository CONTRIBUTING and PDC failure register
were read before design and reopened before this handback.

## PA1-C01 — terminal and actual scope

Recommended GY-PA1 terminal: **executed**, subject to the root's frozen-source review
and required final guards. The old `not_executable` rationale is superseded: the
existing S8 owner now has an unconditional production worker bridge, persisted
source-bound refusal/selection artifacts, and current consumers. No appointment,
canonical all-evidence candidate, empirical ValueGateReceipt or production signed
policy recommendation is claimed. Positive fixture trust remains explicitly a
semantic control, not a canonical denominator.

The exact Done-when is quoted in PA1-R01 (`findings.md`): no authorized schedule
cannot emit even one ranked recommendation; it emits frontier plus typed request;
wrong decision-rights role is blocked; injected equal-weight, historical-prior and
proxy-priority defaults go red. The implemented worker preserves actual generated
N6 front labels and every source candidate identity; it declares dominance
`not_established`. It never promotes an unvalued front to a Pareto archive.

| Full conjunct | Deciding evidence | Result |
| --- | --- | --- |
| No authorized schedule yields zero ranked recommendations | Actual default worker `[missing]`; source-recomputed leaf disposition and outer composition replay | discharged |
| Frontier plus typed persisted request | Worker compares full source front mapping; missing/unresolved sidecar controls require preserved fronts, request and replayable new refusal CAS ref | discharged |
| Authority-lane mismatch blocks for the right reason | Actual default worker `[wrong_role]` reaches `p20_normative_authority_scope_mismatch`, zero rankings and persisted request | discharged; not `p20_value_schedule_resolver_absent` |
| Equal-weight / historical-prior / proxy-priority injection goes red | Three coherent leaf-and-composition mutations; removing leaf replay makes all three unauthorized outputs escape and the tests fail at the `blocked` assertion | discharged |
| Real ranked emitter remains falsifiable | Same actual default worker `[authorized]` consumes independently signed source-bound archive and v2 permission, returns a ranking; expiry and current signature corruption revoke it | discharged for mechanism, no canonical positive design claim |
| P27 owner-first | Existing S8 owner validates leaf source/evidence; existing HTTP compiled DTO owner replays parent membership. No caller-asserted verified flag or second CAS owner | discharged |
| P28 default flipped and receipt | Worker unconditionally calls `resolve_generation_value_choices`; run-emitted `NormativeRunStrangleReceipt` recomputes complete source/disposition node sets; actual worker-call removal fails at omitted sidecar while source run still completes | discharged |
| P29 run/recompute | Sidecar CAS reads, exact source bytes and full source topology are replayed; fabricated coherent statuses and altered receipt membership refuse; four actual property removals are red | discharged |
| §3.5.6 denominator and fake/novel | Complete node/candidate source sets compared; foreign source with unchanged display identities refuses; wrong compiled association, nonexistent sidecar, malformed evidence and projection edits refuse | discharged for source-binding owner |
| §3.5.6 data-only growth | Existing generated candidate leaf data is routed through a graph with two novel leaf names, no source edit; graph-derived and node-derived leaf identities and full projected candidate identities agree | discharged for bridge; synthetic structural control, not canonical policy producer |
| §3.5.6 decisive-property mutation with positive still valid | Composition replay removal keeps initial signed positive green but stale/source-substitution negatives red; signature removal keeps initial signed positive green but damaged signature negative red | discharged |
| Required final integration/guardrails | Root-owned wave after all lane source is frozen; deliberately not run concurrently with other agents' edits | not_established in this subtask handback |

## PA1-C02 — final mechanism and authority ownership

`runtime/http/services/control/generation_cycle.py` owns the additive composition
schema `policyos.normative_generation_composition.v1`. It resolves the actual
compiled CAS object with its existing DTO, derives every real leaf, persists the
exact leaf source bytes, and compares the complete node/source binding at every
composition emission and projection. A matching display name is insufficient.

`runtime/quality/design_axes/value_choice_provenance.py` extends the existing S8
owner with `policyos.normative_generation_disposition.v1`, generation authorization
v2 and admission v2. The signed permission binds compiled CAS ref, exact leaf CAS
ref and node. The signed frontier must also name that leaf source; candidate names
alone cannot establish its source. S8 leaf output explicitly records compiled
membership `not_established`; only the compiled owner establishes parent membership.
Existing standalone v1 authorization/admission and generation DTO epochs remain.
The authorized alternative remains permission for exact selection only, never an
empirical, Pareto, legal or publication claim.

`run_lifecycle.py::_process_control_job` invokes the bridge after real compiled-source
persistence and before completed progress/event publication. Its existing progress
contains the sidecar ref and projection; diagnostics retain the audit ref.
`create_runtime_api_app` passes the typed deployment trust slot through the existing
container to the service. The default slot is empty. Candidate request context
contains only typed evidence refs, never trust. The adapter unwraps only the exact
canonical `GuardedDependencyProxy` and reuses its existing ambient `FileSystemCAS`
object with its ownership checks. An arbitrary `_target` impostor is rejected.
Unsupported stores raise named `p20_normative_signed_store_unavailable`; no fallback
unguarded store is opened. Other backends need their signed-owner adapter.

## PA1-C03 — same-class review findings and widened boundary

The raw `get_latest_job_for_run` snapshot was a second instance of the same
P31/P37/P38 current-emission class, one level deeper. The decision widened once to
`_current_normative_job_record`, used by both outward service job readers. It does
not independently patch two reader bodies. Tests drive both actual readers with a
stored positive, then current expiry and caller-overridden progress.

`stage3-source-census.json` contains the complete 2,630 Python source identity set:
git index and filesystem walks agree, no ambiguous files, and independently parsed
AST and token streams agree for every monitored symbol file set (including exact
`getattr` strings). It identifies the actual caller set: control route job status;
runs route diagnostic and policy projections; production approval scorecard reader;
production approval progress mutation. The latter scorecard helper has a raw-store
fallback, but exposes `quality_scorecard`/`quality`, not the normative projection;
the default worker supplies `quality_scorecard`. Direct store snapshots and CAS
refs remain historical evidence. The present current-normative egress class is the
two service readers, both routed through the shared boundary; no hypothetical
future reader is claimed covered.

The same class also appeared as a lossy refusal fallback: invalid sidecar returned
an empty generic blocked dictionary and an unresolved CAS ref escaped as a read
exception. The red controls are preserved. The widened projection now invokes the
same existing composition producer to persist a fresh refusal from a still-valid
compiled source, preserving real fronts and a typed request. The returned top-level
reason retains the exact prior replay failure, while the new request records a
sidecar-replay limitation. If source resolution itself is unavailable, source status
is explicitly `not_established`; it is not replaced with an empty front.

The independently signed foreign-frontier control revealed another instance of
source binding: the first implementation checked candidate membership but accepted
an archive naming another source. Its red was `authorized` against expected
`blocked`. The source owner now checks the actual frontier source ref. This is a
refusal-path correction inside the not-yet-released generation schema, not an edit
to prior standalone receipt epochs.

## PA1-C04 — red-first and removal record

All current JSON command captures contain exact argv, cwd, PATH/PYTHONPATH, child
return code, monotonic elapsed time and complete stdout/stderr. Each gate is the
only child invocation; there is no shell echo status proxy. Python modules are
invoked with `-m`, and the lane venv precedes PATH for child processes. No directory
suite or full suite was run.

Early logs predate the shared capture runner. `stage3-early-command-records.json`
appends the exact original gate argv/RC and complete logs from the direct tool
invocations. Their wall times and inherited PATH tail were not captured then and
are explicitly `not_established`; they are not invented retrospectively.

- `stage3-worker-red.log`: real worker completes source generation but the new
  assertion fails at omitted normative sidecar. The first green replays the same
  worker plus the existing standalone S8 owner file.
- `stage3-semantic-gates.log`: the source-substitution probe initially failed in
  setup comparing reconstructed model instances. This is a nonreceipt for that
  conjunct; no product refusal was credited. The corrected probe compares complete
  node/candidate identity sets and recursive content hash, then executes both
  actual current-source refusals. Reparse normalization changes leaf CAS bytes
  despite equal display identities; the new-source owner therefore refuses at
  `p20_normative_frontier_source_mismatch`, while old-sidecar consumption refuses at
  `p20_normative_compiled_run_substitution`. The independent wrong-source worker
  control tests exact authorization `generation_binding_mismatch`.
- `stage3-frontier-source-red.json`: genuine signed fixture still reached
  `authorized` with a foreign frontier source; repaired owner refuses specifically.
- `stage3-sidecar-fallback-red.json`: absent sidecar lost leaf dispositions;
  nonexistent CAS escaped as FileNotFoundError. Both are repaired with source-derived
  persisted refusal and exact front preservation.
- `stage3-app-trust-red.json`: actual factory had no configured trust entry; its
  explicit typed keyword now reaches the default container/service in a TestClient
  lifecycle control.
- `stage3-semantic-gates-v2.json`: own implementation NameError in the new fallback
  (type-only import used at runtime) and a fixture invalid execution-profile enum;
  both corrected. No failure is called inherited.
- `stage3-semantic-gates-v3.json`: the corrected substitution reaches a real source
  mismatch earlier than the test's expected authorization mismatch; plus app entry
  red before repair. Neither is hidden by a reduced denominator.
- `stage3-semantic-gates-v4.json`: full bridge control file green.
- `stage3-removal-default_call.json`: process-local AST removes exactly the real
  worker owner call while keeping sidecar markers and completion logic. The run
  completes, then fails at omitted source-bound request; no crash is counted as proof.
- `stage3-removal-composition_replay.json`: copies stored composition instead of
  owner replay. Initial signed positive stays valid; expiry and same-display-name
  source-substitution tests both fail because unauthorized current output is green.
- `stage3-removal-leaf_replay.json`: copies stored leaf instead of recomputation;
  all three coherent silent-default mutations fail because unauthorized rankings escape.
- `stage3-removal-signature.json`: removes only signature validity enforcement;
  initial signed positive stays valid and corrupted current signature stays green,
  making the actual zero-ranking refusal test fail.

The removal processes touch no production source bytes. They use isolated test CAS
roots. Concurrent process startup reported Prometheus fixed-port exporter warnings;
these are explicit station findings (home: P41/verification harness, no product row).
They did not decide any assertion: each red is an actual forbidden ranking or
missing worker output after a completed source run. The final ordinary targeted
run is serialized. Future such probe waves should serialize that shared exporter.

## PA1-C05 — handback, routing and remaining checks

Built/falsified: source-aware S8 admission, shared compiled source projection,
default worker persistence, deployment trust composition, current shared job
projection, source-preserving refusal, run-emitted/recomputed strangle. The exact
falsifiers and all complete command outputs are indexed below.

Belongs elsewhere: the canonical institution-signed rollout assignment and SKG
scientific relation/bridge prerequisite remain GY-N7 / DataForge (root research
findings decide their standing); canonical N8 ValueGateReceipt/valid value_ready
production remains GY-N8 and the first-promotion-candidate row. PA1 grants none of
that authority. Non-filesystem signed CAS support belongs the core artifacts /
runtime persistence adapter boundary (explicit unsupported backend here).
No changes to closed tasks, register or ledger are proposed by this mechanism;
architect may transcribe PA1's superseded orchestration standing from this evidence.

Root retains final guardrail/public-surface companion validation and commits. The
new release fragment declares the additive app keyword/progress surface; it does
not blanket-refresh inventories. Parent-to-leaf source semantics, current trust,
role, time and projection invariants are load-bearing. Remaining source changes
from review require delta falsifiers before any final executed claim.

## Exact current command index

### `stage3-app-trust-red.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_generation_bridge.py::test_app_factory_passes_typed_deployment_trust_to_default_service -q`
- RC: `1`; wall seconds: `30.79528170800768`.
- Complete streams and exact child environment: [stage3-app-trust-red.json](stage3-app-trust-red.json).

### `stage3-final-targeted.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_generation_bridge.py tests/unit/runtime/http/test_control_service_di.py::test_process_nl_job_enters_persisted_tenant_scope --junitxml=docs/superpowers/journals/gy-phase5-evidence/pa1/stage3-final-targeted.xml -q`
- RC: `0`; wall seconds: `64.37934824998956`.
- Complete streams and exact child environment: [stage3-final-targeted.json](stage3-final-targeted.json).

### `stage3-frontier-source-red.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_generation_bridge.py::test_signed_frontier_must_bind_actual_source_not_same_candidate_names -q`
- RC: `1`; wall seconds: `34.726307334029116`.
- Complete streams and exact child environment: [stage3-frontier-source-red.json](stage3-frontier-source-red.json).

### `stage3-removal-composition_replay.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.stage3_probe composition_replay`
- RC: `1`; wall seconds: `48.11002958397148`.
- Complete streams and exact child environment: [stage3-removal-composition_replay.json](stage3-removal-composition_replay.json).

### `stage3-removal-default_call.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.stage3_probe default_call`
- RC: `1`; wall seconds: `47.925161041959655`.
- Complete streams and exact child environment: [stage3-removal-default_call.json](stage3-removal-default_call.json).

### `stage3-removal-leaf_replay.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.stage3_probe leaf_replay`
- RC: `1`; wall seconds: `47.47988204198191`.
- Complete streams and exact child environment: [stage3-removal-leaf_replay.json](stage3-removal-leaf_replay.json).

### `stage3-removal-signature.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.stage3_probe signature`
- RC: `1`; wall seconds: `48.024371917010285`.
- Complete streams and exact child environment: [stage3-removal-signature.json](stage3-removal-signature.json).

### `stage3-ruff-final.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m ruff check src/polisyos/runtime/http/app.py src/polisyos/runtime/http/container.py src/polisyos/runtime/http/services/control/generation_cycle.py src/polisyos/runtime/http/services/control/run_lifecycle.py src/polisyos/runtime/quality/design_axes/value_choice_provenance.py tests/unit/runtime/http/test_control_service_di.py tests/unit/runtime/http/test_normative_generation_bridge.py`
- RC: `0`; wall seconds: `0.04583645798265934`.
- Complete streams and exact child environment: [stage3-ruff-final.json](stage3-ruff-final.json).

### `stage3-semantic-gates-v2.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_generation_bridge.py -q`
- RC: `1`; wall seconds: `33.74686970800394`.
- Complete streams and exact child environment: [stage3-semantic-gates-v2.json](stage3-semantic-gates-v2.json).

### `stage3-semantic-gates-v3.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_generation_bridge.py -q`
- RC: `1`; wall seconds: `38.83979545900365`.
- Complete streams and exact child environment: [stage3-semantic-gates-v3.json](stage3-semantic-gates-v3.json).

### `stage3-semantic-gates-v4.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_generation_bridge.py -q`
- RC: `0`; wall seconds: `36.48701166699175`.
- Complete streams and exact child environment: [stage3-semantic-gates-v4.json](stage3-semantic-gates-v4.json).

### `stage3-sidecar-fallback-red.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_generation_bridge.py::test_missing_or_unresolved_sidecar_preserves_current_source_fronts -q`
- RC: `1`; wall seconds: `34.24474008299876`.
- Complete streams and exact child environment: [stage3-sidecar-fallback-red.json](stage3-sidecar-fallback-red.json).

### `stage3-source-census.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.stage3_census`
- RC: `0`; wall seconds: `18.704401375027373`.
- Complete streams and exact child environment: [stage3-source-census.json](stage3-source-census.json).

### `stage3-targeted-collection.json`

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m pytest tests/unit/runtime/http/test_normative_generation_bridge.py tests/unit/runtime/http/test_control_service_di.py::test_process_nl_job_enters_persisted_tenant_scope --collect-only -q`
- RC: `0`; wall seconds: `25.82654812495457`.
- Complete streams and exact child environment: [stage3-targeted-collection.json](stage3-targeted-collection.json).

### `stage3-test-identity-reconciliation.json` — complete test identity reconciliation

- CWD: `/Users/deniskopylov/polisyos/.worktrees/gy-phase5/policy-engine`
- Command: `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.stage3_collect`
- RC: `0`; wall seconds: `27.96564316697186`.
- Complete streams and exact child environment: [stage3-test-identity-reconciliation.json](stage3-test-identity-reconciliation.json).

The complete collected and executed identities agree: 26/26, with no missing,
unexpected, duplicate or unsuccessful executions. These are the whole new bridge
test file plus all actual default-worker parameterizations. The independent sets
are retained in full; the earlier quiet collect-only file-total output was not
used as an identity proof.

Source is frozen; the shared quality README also contains the concurrently
implemented S3 documentation and should be staged with that ownership understood.


## D3b/D3c appended completion delta — PA1-R01 temporal bridge

The prior initial-package qualification remains in the record. The subsequent
D3b/D3c mechanism closes the measured temporal gap: the actual default worker first
finishes with missing normative evidence; its actual compiled CAS source is signed
only afterward; the new production HTTP intake conditionally appends a current
head; both existing current job readers consume that head through current S8
replay. This uses an explicit signed fixture appointment solely to test the
mechanism. It does not claim a canonical production appointment, complete evidence
candidate, empirical result, or promotion.

The first architectural extension is NEW class PA1-R01 (P01/P02): a standalone
post-source producer persisted a new sidecar without a production intake or head
consumer. The second finding is that same temporal bridge class one level deeper:
the NL worker did not publish a canonical owned core run, so the real owned-run
resolver returned `authorization_binding_run_unresolved`. Under P40 the design was
widened to the complete actual chain, not patched with an authorization bypass:
actual compiled source → canonical core-run publication → owned post-source intake
→ conditional event head → shared current readers. D3b and D3c were recorded by the
root before their production seams were changed.

### Existing owners extended

- `control/generation_cycle.py`: strict submission DTOs and additive
  `policyos.normative_generation_head.v1`, plus the real CAS/epoch head loader.
  Existing S8, generation and composition receipt epochs are unchanged.
- `control/run_lifecycle.py`: existing worker uses canonical `RunContext` to publish
  its actual compiled/initial normative outputs with the persisted job tenant and
  cell. Existing terminal output is replayed and checked instead of overwritten.
  The service derives exact run/compiled/initial-sidecar identity from that immutable
  owner, receives typed external refs, invokes the existing S8 composition producer,
  persists a head, and reads the admitted event back through the shared projection.
- `control_plane_store.py`: the existing `control_job_events` table owns the head
  index through `normative_evidence_admitted`. Compare-and-append runs inside
  SQLite `BEGIN IMMEDIATE` or PostgreSQL's existing transaction context with an
  owning-job `FOR UPDATE` lock. No new table and no progress rewrite.
- `routes/control.py` and the closed `resource_binding.py` resolver map:
  `POST /api/v1/control/runs/{run_id}/normative-evidence` requires the existing
  `EVIDENCE_RESOLVE` permission and verified ownership of that exact run. The strict
  body supplies exact job ID, required nullable prior-head ref, and existing
  `NormativeRunEvidenceRefs`. It supplies no compiled source or deployment trust.
  The added resolver entry changes supported resource vocabulary; it does not
  alter the existing authorization receipt/hash semantics.

Successful receipt returns HTTP 200, a typed refusal HTTP 422, and a stale-head
conflict HTTP 409. Refusal/conflict attempts persist their disposition and immutable
attempt audit event without advancing the admitted head. Wrong-job and malformed
requests fail at the existing bound request boundary. Both GET readers and the
submission response use `_current_normative_job_record`; source/head corruption
cannot resurrect an old worker ranking. If the compiled source remains available,
a broken head produces the same source-preserving refusal producer and typed NDR.

General approval progress updates can copy a current projection. The head's
StrangleReceipt therefore binds its initial disposition to the immutable canonical
core-run output, not to a copied progress field. The retained probe covers this
real sibling-write class and proves that source substitution subsequently blocks.

### Decisive evidence

The corrected final targeted wave is `d3b-final-targeted-v3.json` (actual RC 0,
132.91363483300665 seconds). Its full JUnit is `d3b-final-targeted-v3.xml`; all test
identities are reconciled independently by `d3b_collect.py`. It includes the entire
new intake test file, the actual two-connection SQLite race, complete live-router
versus OpenAPI operation identities, and the new route's permission/identity/handler
controls. This is a targeted blast-radius wave, not a directory suite.

The primary test executes the actual worker before signing. It then enters the
real secured HTTP route and observes an authorized current head at both readers.
A source-substituted authorization signed by the same valid fixture signer returns
`p20_normative_generation_binding_mismatch`, zero ranked recommendations and a
persisted typed NDR. Its prior admitted head remains authorized and unchanged.
The same run proves predecessor conflict, permission absence, foreign-tenant denial,
wrong job rejection and strict source/trust-override rejection. Original job progress
is unchanged by admission, refusal and conflict.

`d3b-source-census.json` walks every `src/**/*.py` file and reconciles the complete
filesystem and git identity sets: 2,630/2,630, no ambiguous files. AST and independent
token identities agree for every temporal owner/call reference. The complete head
schema has nine fields; AST declarations and Pydantic fields agree on the identity
set. Mutation parameters derive from that actual schema, with additional missing-CAS
and artifact-epoch cases. Each admitted-head mutation retains actual candidate
fronts and a typed request while blocking current recommendations. Novel metadata
must really be changed: equal CAS bytes reuse an existing manifest, so the corrected
epoch probe preserves decoded head meaning while using distinct timestamp spelling
to expose a distinct artifact manifest.

The run-emitted `NormativeEvidenceHeadStrangleReceipt` flips the default current-job
projection from worker-only sidecar to the admitted event head and binds both exact
dispositions. The reader recomputes its fields from the immutable core-run output
and admitted sidecar. Removing actual head attachment keeps the signed producer,
append event and all receipt markers but the unchanged post-source positive fails
at missing current head (`d3b-head-attachment-removal.json`, RC 1). Removing canonical
run publication keeps the markers and worker outputs but that same positive fails
at the real owner resolver's HTTP 403 (`d3c-owned-publication-removal.json`, RC 1).
The head-binding removal separately disables the actual source-binding predicate
while preserving its marker/reason strings; the happy path remains valid and the
wrong-job head mutation must fail the unchanged refusal assertion.

### Preserved reds and bounded verification

No earlier red was erased or credited as completion. `d3b-intake-red.json` is a
legacy test-scope UUID setup failure; `-v2` is a harness CAS-owner mismatch;
`-v3` reaches the decisive absent route (404). `d3b-intake-first-green.json` is the
real missing owned-run producer (403), which caused D3c. Subsequent source-head reds
include shared fixture shutdown/creation-time ordering and a temporary schema
attribute implementation error. The first final wave also caught an unsorted
expected authorization operation identity list. The second final wave found that
its metadata-corruption probe had not changed metadata because CAS reused the
existing manifest. Those records remain complete and linked; the corrected third
wave passed every case without weakening a semantic assertion.

Actual concurrent PostgreSQL execution is **not_established**: this station delta
executes SQLite concurrency. The PostgreSQL transaction/row-lock path is implemented
using the existing persistence owner; no PostgreSQL runtime result is claimed.
Canonical OpenAPI/client generation, generated-artifact recomputation and common
architecture guardrails remain the root's serialized closeout work. No generated
writer, register/debt edit, push, stash or commit was performed by this subagent.

Proposed PA1 terminal after the root's frozen delta review and common checks:
`executed` for its refusal/authorization/orchestration contract. The earlier
`not_executable` standing is superseded by the measured buildable mechanism.
Production institutional/scientific appointment and upstream N8/N9 evidence remain
with the named shared N7 fork / first-complete-promotion row; this delta neither
manufactures them nor depends on falsely declaring them present.


### Frozen-review qualification: head arrival must survive mutable progress copying

The 21-case green above is preserved, not the final PA1 completion receipt.
`d3b-head-absence-challenge.json` subsequently measured a real escape (RC 1):
the actual worker's initial disposition was blocked, later signed fixture evidence
was admitted through the owner, its current projection was copied through the real
progress store, and omission by the event owner left an authorized recommendation
and copied head ref. This is the same P31/P37 head-arrival/emission class, one level
deeper. A scalar blocked result is also insufficient when the immutable core source
remains available: source mismatch must preserve that source's frontier and typed
request, not fall back to an unbound progress source.

The independent reviewer also distinguished the initial attachment-removal witness:
it failed first on head-ref presence before reaching the semantic reader assertions.
That record proves reference attachment, not yet the authorization effect. The
source-binding removal is semantic: the happy path passes and a wrong-job head
produces unauthorized ranking at the unchanged refusal assertion. The next approved
batch must move authorization/ranking assertions before reference assertions and
widen the single current-reader source selection to immutable core output for both
head-present and no-head cases. No raw-progress authority fallback may be introduced
to preserve a constructor-only test. Source remained frozen while these findings
were measured and routed to the root.


### D3d — one immutable source selection boundary

Root decision `D3d` was committed before editing. The shared reader now resolves
canonical core outputs before choosing either the no-event default or an admitted
head. Mutable progress supplies neither source nor default authority. Copied head
metadata is cleared before replay; missing head arrival produces a fresh typed
refusal. If progress names another compiled ref, the reader retains the already
resolved canonical compiled source for that refusal, so the original candidate
frontier survives. Only an unresolved immutable owner makes source binding
`not_established`. The submission owner likewise refuses a progress/source mismatch
using the canonical source and existing refusal producer.

The initial standalone job-reader fixture was corrected to publish its actual
source through canonical `RunContext` before asserting job authority. No raw-progress
compatibility path was introduced. The post-source HTTP positive captures both
current readers and asserts authorization and nonempty rankings before checking any
head/receipt marker. The progress-copy test now removes the event owner and checks
both readers' zero ranking, complete original frontier, typed request and cleared
head metadata; the same assertions cover a rebound progress source.

D3d changes no public request/response schema, endpoint, head epoch or S8 receipt
epoch. Generated companion owners remain with the root. Delta results below replace
only the insufficient source-default and attachment assertions; prior evidence and
reds remain retained.
