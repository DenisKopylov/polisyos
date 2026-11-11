# LANE-01 N6/P05 consultant directions and priority falsifiers

## Status and provenance

This is an English record of the consultant answers supplied by the user on
2026-11-11 and accepted by the user as implementation directions and priority
decisions to verify. It is a reference decision input, not another execution
plan, institutional appointment, G acceptance, or formal closure. The live plan
and remaining work stay in the root `E02-WORK-PLAN.md` and existing execution
state. Preserve the original 11 packets / 66 requirements / 64 contracts.

The consultant reviewed source `465962a33e87d6a23204115750f9a235e1adac25` without
changing the repository. Their probes used stock Python 3.13.18 and, for one
generated-code probe, beartype 0.22.9. They ran neither project tests nor N5.
Generated-text stability was checked on one simple signature, not actual
PolicyOS methods. Verify the relevant claims on the retained Python 3.14
environment and actual consumers. Do not transfer their timing results as a
measured product profile.

## Earlier diagnosis and implementation advice retained

The first consultation diagnosed an unbounded P40 repair loop: a verifier cannot
reimplement Python's binding, import, decorator and closure semantics. A frame
keyed by module/qualname/code is not the called function object; several method
wrappers share code and differ in captured values. Reading a retained frame at
seal can observe a later mutation instead of the value used by the call. Static
import closure also includes modules the numerical call did not execute, while
process-session tokens prevent cross-process reuse by construction.

Bind interpreter inputs and the actual producer-owned call seam instead. Later
verification can reconcile retained input/result bytes, source blobs and provider
files. It cannot retrospectively establish the actual pre-call object, complete
read-set or correctness of the computation without an independent repeat.

Recommended follow-up instrumentation is `sys.monitoring` with an owned tool ID
and `DISABLE` after a first code observation, replacing blanket `sys.setprofile`
where measured and compatible. An early audit hook records observed changes to
`__code__` and `__defaults__`, including A→B→A. It does not detect all module/class
slot rebinding, closure-cell changes or registry mutations. Calls reached only
through C helpers such as `map` or `sorted(key=...)` expose a frame without the
same producer-held callable-object seam; keep that residual explicit.

The consultant's standalone 2-million-call probe measured 18.3× overhead for
`setprofile` and 1.02× for monitoring with `DISABLE`. Hashing 2,895 first-party
files took 0.10 seconds there; this does not replace the product's 1,281-second
import-edge preflight or establish Python 3.14/N5 performance. Measure the real
profile before making a speed claim. The initial conservative invalidation rule
compares loaded-module bytes, the full first-party path set, providers and
platform; a new source path invalidates that identity until a justified finer
rule exists.

Keep these limits typed and versioned: arbitrary-code read-set completeness,
same-process transient slot/cell/registry substitution, unobserved generated-code
provenance, cross-machine bitwise reproducibility, and interpreter/OS integrity.
The later A/B/C provenance and identity-versus-closure decisions below refine
the initial advice; they do not claim those residuals have disappeared.

## 1. Numerical intent and conditional retention

A value is algorithmic if it changes the sequence of kernel calls (callable,
arguments, seed) or aggregation. A value is operational if it only decides
whether an already planned call may proceed. An operational source may influence
the number only through an explicit algorithmic value materialized in intent
before execution.

- Numerical: horizon, seeds, replications, selected outcomes, baseline/evidence
  state, NCM/variable-map/aggregation plan values, comparator profile, atom
  values, and prepared numerical configuration.
- Operational: `budget_ref`, invocation quota policy, invocation purpose, and
  reservation identities.
- Output labels: `world_model_record_ref` and comparator evidence refs. Keep
  labels separate from any comparator algorithm/profile that changes the math.

Split the current `CandidateN5RequestValues` projection and the effective-basis
facets. Preserve the existing complete field-role denominator: every actual
field has exactly one role; missing or overlapping roles refuse. Do not silently
change persisted v1 basis/hash semantics; provide the new versioned projection
and applicable historical reader.

The effective numerical axis contains Foundry state, selected native NCM,
numerical request values, applied rules, and declared numerical model. Evidence
occurrences, semantic bindings and current permission remain separate axes.

An execution profile includes the actual installed distribution inventory, not
only `uv.lock`. The lock alone cannot distinguish whether an optional beartype
wrapper is installed/activated. Bind loaded provider bytes, declared environment
and backend/numerical policy as appropriate; a caller-supplied profile name is
not admission evidence.

Add a completion predicate over the actual planned physical units and completed
units. A quota-interrupted two-of-three run cannot supply retention of the
planned full aggregate. Preserve existing partial-result display and explicit
algorithmic stopping semantics; do not silently turn a maximum into an invented
fixed schedule. Reuse the physical-plan owner for this denominator.

Do not repurpose `_physical_run_ref`: SIM-03 makes it an identity within one
execution, not a persistent cross-process cache. Cross-process retention has a
separate use-decision record.

Two premise classes govern candidate retention:

1. Identity premises: numerical facets/configuration/seeds, execution profile,
   completion and exact comparable seam binding. If one is unestablished or
   incomparable, only historical observation remains; new use needs N5.
2. Closure premises: completeness of the key/read-set, global/transient
   mutations, opaque seam values and generated code without provenance. With an
   equal established identity key, unknown closure permits only candidate
   retention labelled **equality of the declared numerical basis**, with a fixed
   versioned residual list. It does not enter the protected band.

Priority controls: budget-ref-only change keeps the key; an actual replication
change from 3 to 5 changes it; completing only 2 of 3 refuses aggregate retention;
the same lock with a different installed optional wrapper changes the profile.

## 2. Callable state and generated-code provenance

The new codec has three outcomes, never equality by opaque type name:

- Exact content: supported scalars, bytes, Decimal, Enum, dates, containers of
  exact values, frozen dataclasses and Pydantic models with exact fields.
- Reference: functions as nested graph rows (cycles as positional backrefs),
  and classes/modules whose actual identity matches the recorder's
  `completed_binding`. Compare the recorded row/binding, not an invented FQN
  equivalence.
- Unknown: everything else; unknown is not comparable to itself in another
  process.

Do not route the new content codec through the legacy lossy `_binding_value`
path. The old `@1.0` reader/encoding remains unchanged. An opt-in strict owner
must not execute legacy opaque/cycle fallbacks or reuse a lossy legacy cache.

Encode supported content before every actual call. Pointer fast paths apply
only to values immutable by type. Mutable containers/cells are re-encoded, with
records representing call ranges and their content digests. The producer owns
and invokes the retained callable itself. Capture after execution or at seal
cannot substitute for the pre-call observation.

Executed code has three provenance classes:

- A: code belongs to the tree of a loaded module, using existing
  `_code_belongs_to` membership.
- B: generated code with an observed chain binding compile text/hash to the
  executed code and a generator belonging to A.
- C: unattributed code.

Protected use refuses C executed inside the kernel call. B can be admitted only
with its actual observed chain and a generator in A. Install the early audit
hook before generation. Do not infer the chain from a filename, module-name
string, or adjacent event alone; test ambiguous/reordered compile/exec events.

The beartype probe found hidden kwdefaults containing BeartypeConf and
BeartypeCheckMeta and an address-bearing code filename. B code provenance does
not make those values exact. Candidate work retains that limitation. The
protected execution profile explicitly selects `FOUNDRY_SHAPE_CHECK=0`, retaining
the actual strict contract path; qualify that named profile, rather than changing
global settings or serializing arbitrary beartype internals.

`strict_pure_step` should be exactly representable through its function,
frozen-dataclass/tuple-of-strings and string closure under the supported profile.
Verify this against actual methods, not only the simple consultant probe.

Priority controls: distinct slotted objects never share an exact type-only
identity; in-place default mutation is observed; same-code functions remain
distinct by their captured content; unsupported serializers/getters are not
invoked. Preserve native content fields/bits (including fold/IEEE cases) or
explicitly mark the variant unknown.

## 3. Appointed protected replay

### Appointment and comparison

The protected-use policy owner appoints the verifier through a typed artifact,
not the producer. Bind launcher profile, comparator ref/hash, supported tiers,
allocated capacity, attempt limit, validity interval and scope. Until a real
production issuer exists, appointment is `not_established` /
`verifier_unappointed`. A repeat may still provide a candidate observation of
same-kernel reproducibility. Demonstrate the complete mechanism on a clearly
labelled test trust root.

The repeat is blind: its executor receives only the action/input description,
not the original numerical result. The comparator is fixed before replay, and
the verifier compares two sealed artifacts. Producer self-reconciliation is not
independent verifier provenance.

Comparison profiles:

- STRICT_CPU / LIBRARY_DETERMINISTIC: byte equality of the numerical projection
  on the same platform, with predeclared time/identity exclusions. Mismatch is
  final, not an invitation to retry for green.
- STATISTICAL with the same seeds: the same byte comparison establishes replay
  of the sampling implementation.
- STATISTICAL with different seeds: unsupported without a distinct inference
  profile containing sample size and equivalence boundary.
- NONDETERMINISTIC / BEST_EFFORT_GPU: unsupported in the initial protected
  profile.

This does not establish scientific validity or distributional equivalence from
one close sample (DEC-SIM-03-01 remains binding).

### Budget and cache

Use a separate job/run binding and an existing `BudgetInvocationQuotaPolicy`
instance with diagnostic purpose. No new budget schema/pool is required. The
original retained 7/1 ledger remains byte-for-byte unchanged.

Capacity must cover the complete planned repeat before its first call. Partial
replay consumes actual work and proves no completed comparison. Infrastructure
failure consumes completed work and may retry only within the authorized attempt
limit. Numerical mismatch is not retried. No allocated capacity means no repeat;
candidate computation and history continue.

The verification cache key binds numerical intent, execution profile, full
comparator ref, tier and numerical result-projection hash. Appointment is not
part of this identity key. A cache hit is never permission: current issuer
trust, appointment/deployment scope, expiry and revocation admission are checked
again for each protected use. Preserve historical records.

Priority control: producer copies its result into a supposed replay artifact;
admission refuses absent external appointment and actual appointed-launcher
binding. Freeze comparator/tolerances before execution; do not tune after a red.

### Production institutional boundary

The issuer is the accepting organization's independent control function (model
validation, methodology or control), separate from producer and result-user
teams. This is `integrate` under the ratified custody boundary: PolicyOS owns
the typed intake/admission/fail-closed reaction, not the institutional act.

Three distinct identities/signatures:

1. Independent control issues the appointment and methodological/comparator
   scope. It is not producer, launch operator or result-user team.
2. Deployment trust administrator independently verifies the appointment against
   current trust configuration and the actually deployed component; it is not
   the appointment issuer.
3. Appointed launcher's service identity signs each replay execution record; it
   is not the original producing process.

The organization configures public keys and roles. Do not accept its issuer's
private keys as inputs. Service signing uses the existing designated-service
key/secret mechanism, not an institution-key upload workflow. PolicyOS signs
only what it owns, such as component build provenance. It can supply a candidate
comparator profile; organizational acceptance is a separate signed act.

Represent independence class honestly (same organization/separate function or
external party); the protected-use profile sets its minimum. Hosting producer
and verifier in one organization does not become external independence by label.
Do not use producer appointment, result-user self-appointment, or platform-only
methodological approval as substitutes. External auditor/regulator keys may use
the same role contract; they are not required for every routine deployment.

Reuse shapes/owners from `epoch_deployment.py`, chronology appointment plus
independent-check contracts, and the fail-closed lifecycle. Reuse the form of
`evaluation_safety` appointment, never its safety-attempt purpose or owner.

## 4. P05 reverse view and negative query dependencies

For LANE-01 a rebuildable reverse view plus mandatory per-use revalidation is
sufficient. Durable push is required when a binding supports a standing
published claim that may receive no further use event; that belongs to the
existing epoch/cascade owner, not a new subscription subsystem.

- Query key: interface, port, exact definition/representation/profile and scope;
  hash the query envelope without result rows or derived self-hash. Reports with
  the same key share one rederivation.
- Coarse definition-to-report view: build from existing manifest input roles
  without payload reads. Refine affected candidates by typed query keys.
- A use decision binds selected report ref, envelope hash, checked registry hash
  and compatibility-rule version.
- Bind view freshness to CAS owner generation, registry hash and rule version.
  Verify that the generation actually covers relevant report membership; if
  insufficient, bind/check the metadata inventory as well. An incomplete/stale
  view cannot claim no affected reports; use a complete inventory fallback or
  report the result unestablished.
- Compatibility-rule revision rederives all envelopes; unchanged envelopes stay
  current. Do not confuse a code-dependent verdict with an unversioned marker.

No common Catalog/consumer transaction: Catalog atomically owns its registry
revision; each consumer atomically owns its decision bound to the checked
revision. The final protected-action fence rereads the registry hash (the
existing routing activation fence is the reuse point).

Priority controls: a new compatible row under unchanged selected refs affects
only its query subscribers, without N5; a report published after view construction
is not missed; unrelated aliases do not cause global staling; a standing public
claim requires cascade even when nobody reads it.

## Execution and acceptance boundary

Implement reuse-first through existing N5, effective-basis, Catalog, CAS,
deployment-trust and lifecycle owners. Keep one writer per shared mechanism and
mandatory companions. Review each coherent result independently, then qualify
the actual composed source/profile. Preserve v1 artifacts and historical reading.
Neither this direction nor a demo trust root constitutes production authority,
G acceptance, scientific validity, or completion of LANE-01.

## Source navigation for resumption

All paths are under `policy-engine/src/polisyos/`. Line numbers in the supplied
answers refer to the consultant's historical baseline, not the eventual edited
tree. Use the named owners/functions as the durable anchors:

- `runtime/quality/n5_execution_basis.py`: controlled capture, numerical-call
  seam and historical self-reconciliation; `confidence_ledger.py`: legacy
  normalization and recorder code/module membership.
- `runtime/quality/joint_simulation_horizon.py`: actual selected-step calls,
  replication/physical-plan completion and invocation-local `_physical_run_ref`.
- `runtime/quality/candidate_simulation.py`: request-field role census;
  `candidate_source_basis.py`: effective facets; `acquisition_evaluation.py`:
  `actual_live_implementation` comparison facet.
- `foundry/methods/base.py`: `strict_pure_step`, optional beartype wrapping and
  `_beartype_enabled`; `foundry/methods/catalog/dependency_profile.py`: installed
  provider observations (a filtered closure is not a full installed inventory).
- `runtime/quality/model_input_routing.py` and Catalog
  `data_forge/domains/catalog/knowledge/acquisition_authority.py`: query
  envelopes, manifest roles, current registry and final-use fence.
- `runtime/quality/epoch_deployment.py`, `core/contracts/chronology.py`,
  `runtime/quality/evaluation_safety.py` and
  `runtime/http/services/control/run_lifecycle.py`: existing public-key role,
  appointment/check forms and fail-closed consumers. Reuse their shapes without
  borrowing another authority purpose.
- `tools/authority` under the product root: retained launcher and future blind
  repeat entry point; preserve independent diagnostic capacity and actual
  invocation accounting.
