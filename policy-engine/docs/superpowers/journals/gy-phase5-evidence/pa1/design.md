# PA1-R05 — exact default production bridge decision

This proposal replaces PA1-R04's tentative N6 edit location. It is based on the
actual deployed job path. It changes no production file during stage 1/2.

## Decision and exact seam

Use the **existing natural-language run completion owner**,
`src/polisyos/runtime/http/services/control/run_lifecycle.py`, immediately after
`compiled_ref = self._put_json_artifact(...)` at current line 2714 and before the
`progress` mapping at 2726. That path has the actual completed compiled run,
persisted source bytes, deployment CAS, control job identity and diagnostic
projection. It is the production caller currently missing from S8.

Do not modify `GenerationCycleRun`, `RecursiveGenerationCycleRun`, or
`CompiledRecursiveGenerationCycleRun`. Their v1 bytes and hashes remain their own
historical epochs. A **new S8 sidecar** binds the already persisted compiled run
and each actual leaf cycle. Store its reference in existing control-job progress
and diagnostic `artifact_refs`; these are the already live API/audit surfaces.

Proposed service entrypoint (the initial default and later supplied-evidence
reconsideration use the same method):

```python
def resolve_generation_value_choices(
    self,
    *,
    compiled_run_ref: str,
    evidence: NormativeRunEvidenceRefs | None = None,
    evaluated_at: datetime,
) -> NormativeRunDisposition:
    ...
```

`NormativeRunEvidenceRefs` is a strict data-only DTO with current leaf node/ref,
genuine S8 frontier ref and signed authorization ref. It contains no trust,
signer key, selected alternative, weights, pass flag, owner callback or override.
The production worker calls the method unconditionally after source persistence;
optional evidence may be taken from a separately typed context member, but
malformed or mismatched evidence is a typed refusal, not ignored input. Trust is
supplied only as `NormativeAuthorityTrust` to the deployment container/service
constructor and defaults to the existing empty typed slot.

The service result exposes a new sidecar ref plus the owner-replayed public
disposition. Initial execution without authorization yields a request. A later
call with actual signed evidence for that exact existing run can use the same
entrypoint; it must not require generating a new policy to deliver authorization.
The default worker path and this reconsideration path share the producer and
consumer, not two implementations. A REST endpoint is unnecessary for the first
bridge: the existing service and job status/audit surface are sufficient, provided
the test exercises `_process_control_job`, not just this new helper.

## Source binding and owner split

Keep actual compiled-run parsing in
`src/polisyos/runtime/http/services/control/generation_cycle.py`, which already
owns `CompiledRecursiveGenerationCycleRun`; extend this owner with a small
resolver/bridge function called by the service. It must:

1. Read `compiled_run_ref` from the deployment CAS, compare its bytes to the CAS
   digest and expected artifact kind, then call the existing compiled-run DTO
   validator. Never accept an in-memory caller projection instead of this read.
2. Derive the complete leaf set from the parsed recursive run. For each leaf,
   persist the exact already validated `GenerationCycleRun.model_dump(mode="json")`
   bytes as a source artifact, with its existing schema and actual producer
   metadata; this is persistence of the real run, not construction of a new run.
3. Pass the leaf source ref and current compiled source binding to S8. S8 reads
   the leaf CAS back and uses the canonical generation DTO/validator to derive
   every candidate identity and actual `decision/research/quarantine/portfolio`
   membership. The HTTP bridge independently compares the returned complete
   node/source-ref identity set with the original compiled run.
4. On sidecar replay, repeat the compiled and leaf bindings before returning
   any ranking. A current source ref, node, case, candidate, or artifact mutation
   cannot reuse an earlier disposition.

The S8 extension belongs in the existing
`src/polisyos/runtime/quality/design_axes/value_choice_provenance.py` owner. The
new sidecar/result has its **own** kind/schema, for example
`policyos.normative_generation_disposition.v1`; it is not written under the
existing `layer2_s8.value_choice_bundle` v1 kind. Its fields bind source compiled
and leaf refs, node, actual candidate-front projection, authority purpose,
evaluation time, S8 rule epoch, either a typed `NormativeDecisionRequest` or a
reference to the existing verified ranking result, and a derived status.

The shared S8 emission verifier must own all sidecar persistence and projection.
It can dispatch on the new artifact's explicit kind/version, while old S8 bundle
v1 remains readable by its existing parser. It must rederive the complete sidecar
from source/authorization refs instead of trusting its status or copied frontier.

## Both branches, without an artificial permanent refusal

**Absent genuine S8 frontier or authorization:** preserve actual N6 candidate
front labels and candidate identities as an explicitly unvalued candidate front.
Dominance is `not_established`. Emit zero selections and the existing typed
request. Do not fill `ParetoArchive.nondominated_alternative_ids` with N6 candidate
IDs, use proxy scores as priorities, or invent an evaluation/ValueGateReceipt.

**Genuine S8 frontier and authorization supplied:** use the existing
`NormativeValueScheduleOwner.recommend` producer/resolver/emission path. The
production route must be able to select through this branch under a legitimately
configured test trust control; it cannot be implemented as a constant candidate
refusal. The positive control remains fixture evidence, not the canonical
first-promotion population. Selection permission stays
`value_schedule_for_ranking`; it does not promote empirical value, legal
competence, policy optimality, or publication status.

The current authorization v1 does not carry a source-generation binding. A
production bridge must not infer that binding from matching case/candidate names.
Preferred explicit versioned extension: add a `NormativeAuthorizationRecordV2`
with the current leaf `source_run_ref` (and, if needed to disambiguate inclusion,
the compiled source ref/node binding), and versioned source-aware admission.
The existing v1 record stays readable for its original standalone S8 scope, but
is `p20_normative_generation_binding_missing` on this generation-aware route.
The owner verifies the external signature over that complete v2 record, exact
source refs and the already existing genuine Pareto archive. Candidate identities
selected or named by that archive must resolve in the actual source population;
the source binding does not independently certify empirical Pareto truth.

An independently signed typed binding wrapper would also work but adds another
artifact/signature hop without removing any predicate. Prefer the governed v2
record and record the bump explicitly in the execution plan. Do not modify
existing signed v1 bytes or retroactively claim their missing run binding.

## Deployed store compatibility — executed, not assumed

The real factory `build_runtime_api_context` uses
`GuardedDependencyProxy(FileSystemCAS.with_ambient_ownership_enforcement())`.
The current S8 constructor accepts **exactly** `FileSystemCAS`, so passing the
deployment's guarded store directly fails. This was executed with the actual
factory and temporary deployment paths:

```sh
env PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=.:src .venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.measure deployed_store > docs/superpowers/journals/gy-phase5-evidence/pa1/deployed-store.log 2>&1
```

RC0, complete [deployed-store.log](deployed-store.log). The guarded constructor
raises `normative authority requires the concrete CAS and deployment trust`;
its actual underlying ambient `FileSystemCAS` object is accepted unchanged.

The HTTP composition owner may recognize **exactly its canonical**
`GuardedDependencyProxy` and reuse that same ambient target for S8 signature
verification. Do not open a second CAS at the same path, unwrap the ambient
ownership checks, or loosen S8 to arbitrary duck-typed `verify_signature`
callbacks. If a sanctioned wrapper adapter is preferred, it belongs in the
existing resilience/backend composition owner and must preserve the target's
ownership enforcement. The unsupported-backend disposition must be explicit;
this local filesystem measurement does not establish remote signed-store support.

## Surface consumer, configuration and files

- `runtime/http/container.py`: add typed normative deployment trust to
  `RuntimeContainerConfig` or the narrowly validated deployment override, default
  empty; pass it to `ControlPlaneService` in `startup`. Candidate request context
  cannot mutate this object. Validate an overridden service uses the same store
  and configured trust policy rather than accepting a separately populated owner.
- `runtime/http/services/control/run_lifecycle.py`: construct the canonical S8
  bridge using the actual CAS target; add the service method; invoke it by default
  after compiled-run persistence; put sidecar ref and replay-derived disposition
  in job progress and diagnostic artifact refs. Extend `get_job_status` to
  owner-replay an existing sidecar before projecting its current ranking/status,
  so stale permission or a substituted artifact cannot survive as a durable
  green status field. Reconsideration updates progress only after the same replay.
- `runtime/http/services/control/generation_cycle.py`: exact compiled-source
  resolver and leaf bridge using existing DTOs, without modifying their fields.
- `runtime/quality/design_axes/value_choice_provenance.py`: source-bound v2
  authorization/admission, candidate sidecar production/replay and shared S8
  output verification; reuse existing signatures, schedule resolver and request.
- Existing S8 tests plus a mirrored control lifecycle integration test: red first
  against the actual job worker and job-status consumer; fixture trust is plainly
  test configuration. New surface/export/version companions are recorded outside
  mechanism path counts under P39.

The default changes the **job-emission path**, not the completed N6 generation
owner. A sidecar `StrangleReceipt` should be run-emitted and recomputed from the
actual source+call result, with the default state flipped. Its removal test must
delete the actual invocation while leaving marker strings and the positive S8
path valid; missing sidecar/request/projection then fails. Source scans alone
are not a behavioral strangle proof.

## Falsifiers and completion boundary

- Real worker with no schedule: job completes with candidate frontier preserved,
  no ranked choice and a CAS request sidecar exposed by job status.
- Same route, genuine source-bound S8 archive and configured fixture trust:
  existing positive selection survives persistence and consumer replay.
- Wrong rights role, stale authorization, wrong source-run ref, and identical
  candidate names from a different run: blocked with the specific actual owner
  reason; the positive control remains valid.
- Missing/novel leaf or source candidate: all identity-set differences explicit;
  no fixed fixture list or silent `.get` fallback. Data-only candidate growth needs
  no code changes and the source-front identity set remains complete.
- Silent equal-weight/historical-prior/proxy choice injection: persistence and
  the job-status consumer refuse; remove the shared substantive check while
  retaining DTOs, signatures and markers and each negative goes red.
- Remove default bridge call: worker integration test goes red on actual missing
  output, not on a string inventory. Remove sidecar replay: current status
  tampering/staleness test goes red.

This can close PA1's mechanism despite the shared positive SKG scientific gap.
It does not close the separate `first-promotion-candidate-with-complete-evidence`
row: no normative permission can manufacture that missing empirical evidence.
