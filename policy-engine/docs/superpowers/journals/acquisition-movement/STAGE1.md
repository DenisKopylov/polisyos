# Acquisition movement — Stage 1 research and architecture

Commission: `codex/acquisition-movement`, base
`28b8a1a420e746b54fbd0b87f73fad1fc4821ba5`, 2026-09-13.
This document records research findings and a proposed partition. It does not
admit institutional authority, close a register row, or claim production movement.
No production source, test, register, ledger or governed artifact is changed.

## AM-R01 — the commission is not one subject

The proposed partition is **eight acquisition-lifecycle obligations, one numeric
VoI obligation, and one importer-provenance investigation**. The eight are a
dependency chain with different closing acts, not one reduced obligation.
The exact ten first-cell IDs, their denominator and independent reconciliation
are in `probe_stage1.py` and its retained census receipt. The title's “nine plus
two” is not used as a stopping or counting predicate; the enumerated commission
and its explicit ten-row instruction agree.

| Commissioned row | Deciding variable at this base | Present mechanism and missing link | Proposed subject |
| --- | --- | --- | --- |
| `GY-GAP6` | Absent movement-family capability, plus its separate policy/owner selection | DS15 phase/terminal receipts and exact overlay re-entry primitives exist. A native per-row movement producer, admission and Cycle Board consumer remain absent; generic chronology is not that family. | Acquisition lifecycle |
| `ds15-gy-gap6-evidence-register-closure` | GY-owner evidence admission and register closing act | A supplied DS15 receipt does not establish a GY admission. The missing object is an admitted per-row movement-family record, with its own policy/admission/head identities. Register edits are outside this commission. | Acquisition lifecycle |
| `ds15-deterministic-admission-bundle-producer` | Appointment at the local signer slot **and** absent sanctioned production composition | The deterministic producer and invocation mapping exist; the acquisition-purpose signer/verifier slot is typed and empty. The served request/worker chain still lacks its production authority provider. “Signer alone” describes the local producer, not the full served capability. | Acquisition lifecycle |
| `ds15-mandate-intake-has-no-registered-task` | Registration/selection adequacy, not an acquisition-data predicate | The named handoff exists. A ledger absence is bounded by its filename/GY-table selectors; an equivalent active successor is not established by those selectors. Reconcile the allocation before inventing another task. | Acquisition lifecycle, allocation prerequisite |
| `ds15-signed-v2-delegation-mandate-owner-authority` | External delegation/currentness evidence and sanctioned intake capability | Existing PA2 checks consume signed evidence; `AcquisitionAuthorityGatewayProvider` is only a Protocol in production composition. External signing is an integrate boundary; building the empty governed intake does not await the institution. | Acquisition lifecycle |
| `ds15-production-n13b-execution-handshake` | Absent governed authority-provider composition, then end-to-end verification | The concrete tenant/route-bound WDI executor exists. The public request refuses before reserving an attempt because the provider is absent. A direct port test does not discharge the public request → durable worker signal. | Acquisition lifecycle |
| `ds15-numeric-voi-metric-residual-granularity` | Metric/decision basis: content-bound owner/ranking reference and expected value/cost inputs | Ranking-only rows cannot be promoted into numerical VoI by acquisition or epoch signing. The exact metric basis is a different design input from observation admission. | Numeric VoI |
| `education-importer-provenance-neither-inherited-nor-excluded` | Causal attribution of a test failure to the original slice | Same-base red alone does not establish disjoint inputs. Native/transitive/Git input closure must be settled at the original Phase-5 slice base. | Importer provenance |
| `ds15-fresh-positive-production-route` | Absent bridge from live evidence through admitted observation membership and qualified activation to same-case re-entry | WDI execution forces quarantine and delta zero. Existing Data Forge admission, semantic-epoch activation and N6 re-entry primitives supply the integration direction, not a production success. | Acquisition lifecycle |
| `ds15-semantic-epoch-qualification-authority` | Purpose/scope-specific qualification appointment **and** unallocated production composition | The acquisition wrapper explicitly selects unallocated qualification dependencies. Transition signing cannot satisfy the epoch-family qualification selection key or activate observations. | Acquisition lifecycle |

These classifications separate **capability**, **appointment**, **scope**, and
**measurement**. An empty institutional slot never excuses an absent mechanism.
Conversely, a complete refusal does not mean that a production admission path
exists. Detailed primary reads and bounded limitations accompany the three
research reports under `mandate/`, `positive/`, and `outliers/`.

## AM-R02 — GAP6 is a supplier/admitter chain

**Rule before ruling:** whole-obligation reduction requires all three to coincide:
(1) authority slot, including authority purpose and complete selection scope;
(2) the operative refusal mechanism; (3) the missing condition. A shared prefix,
owner name, common helper, or common blocked-by object is insufficient.

The shape here is **supplier → admitter**. It is neither a whole-obligation
reduction nor a pair of parallel obligations sharing only a mechanism. In the
comparison requested by the commission, mechanism-only coincidence,
counterexample-separated siblings, and supplier/admitter chain are different
results; this pair is the chain.

The supplier's evidence is the DS15 acquisition action's persisted phase and
terminal chain. `AcquisitionRouteLoopReceipt` binds tenant, cell, run, route,
action generation, source job, compiled/planner/cost/decision references,
predecessor, owner receipts and re-entry reference. The existing sink checks
read-back before calling re-entry and creates a distinct terminal event.
That proves the scoped runtime action, not admission into GY movement evidence.

The admitter needs a GY-row/gap-specific movement-family record, admitted under
the movement family's owner policy, provenance and relation, with its admitted
chronology head. `GY-GAP6` owes the producer-to-consumer movement binding.
`ds15-gy-gap6-evidence-register-closure` owes the separate GY evidence admission
and its register closing act. Neither act closes the other; supplying the DS15
receipt is necessary input to these acts and is not either act.

**Separating witness:** the actual DS15 phase/terminal sink can persist a receipt
while `CycleBoardProjectionService._compose()` still constructs
`CycleBoardMovementGap()` unconditionally. Its global N13b source is expressly
denied for `per_row_movement`, `row_enumeration` and `exhaustiveness`.
Relabelling that source cannot close per-row movement. A forged or substituted
GY record cannot supply the actual same-case overlay/re-entry evidence either.

Primary anchors: `runtime/quality/acquisition_route_loop.py:115,412,440`;
`runtime/http/services/cycle_board_projection.py:213,643,683`;
`runtime/http/services/cycle_board_sources.py:27` (all under `src/polisyos/`).
The predecessor's explicitly scoped GAP6 specification is
`docs/superpowers/journals/2026-08-30-debt-e-acquisition-n13b.md:1061`.

## AM-R03 — admission objects and the forced answer

The current **live execution artifact is not an observation admission**.
`WorldBankWDIAcquisitionExecutionPort.execute()` reserves and claims a
provision-minted attempt, calls the live executor, then discards the richer typed
result down to four evidence references and constructs:
`disposition="quarantined_no_growth", admitted_observation_delta=0`.
`reenter()` and `resume_reentry()` both call the refusing
`_raise_reentry_not_admitted`. The forcing point is
`src/polisyos/runtime/http/services/acquisition_surface_execution.py:374–446`,
especially the return at line 422. No transition-signer appointment changes it.

The existing admission object chain, derived from its rejecting consumers, is:

| Object | Producer and consumer | What must be established |
| --- | --- | --- |
| `AcquisitionOwnerExecutionResult` | Production WDI port → `AcquisitionActionService.handle_job()` | `world_committed` requires positive admitted delta, overlay admission receipt and post-epoch event. These fields alone are shape checks, not permission to manufacture evidence. |
| `OverlayAdmissionReceipt` and semantic-epoch production/activation receipts | Existing Data Forge overlay/semantic-epoch admission owners → active catalog projection and generation controller | Resolve admitted passport, live evidence, schema/PII/license/provenance and authority; derive actual observation membership; qualify before activation; reopen the exact committed production receipt. |
| `AcquisitionOverlayReentryReceipt` | `GenerationCycleController.reenter_after_active_acquisition_overlay()` → **to-wire** acquisition terminal-reference bridge and future movement-family admission | Same original DesignProblem/run/source cycle, acquisition-required source terminal, exact active overlay and unchanged baseline, demanded variable/passport equality, positive admitted membership, exact activation and epoch-production events, then a newly produced N6 cycle. The current worker consumes the port's re-entry string; it does not yet invoke this owner. |
| Native **per-row movement-family admission** | GY-N13b movement producer → GY-N12 owner qualification/admission → Cycle Board row | This type/producer chain does not exist yet. Existing re-entry receipt is an input, not this missing object. Bind row/gap, admitted DS15 receipt/date, overlay/epoch, exact case/source cycle, re-entry and distinct deeper terminal, plus native policy/admission/head identities. |

The allocation history's `movement_family_producer` entry (ordinal 5) records
`absent/unallocated`, and no later transition in that artifact upgrades it.
`CycleBoardRow.movement_records` is an empty tuple of untyped dictionaries by
default, not an implemented movement admission. Generic
`NativeChronologyAuthorityAdapter`, `QualificationConsumer`,
`PredicateAdmissionPolicyStatement`, `PredicatePolicyAdmissionStatement`, and
`PredicatePolicyAdmissionIndex` are reusable machinery; none grants the movement
family an authority purpose or selection scope by itself.

The non-test caller is already named: HTTP acquisition mutation routes invoke
`AcquisitionActionService.execute()`, which enqueues the control-owned acquisition
job; `handle_job()` consumes the owner result and drives the durable sink.
The read terminus is the acquisition route projection and Cycle Board endpoint.
Before a mechanism is written, this existing corridor must be used and its
sanctioned deployment authority intake must be composed; an injected dev provider
or a new raw executor is not that caller.

The positive owner chain exists as
`admit_acquisition_with_semantic_epoch` → pending overlay admission →
`finalize_admitted_epoch` → `activate_semantic_epoch` →
`ActivatedSemanticEpochAdmissionReceipt`. The production wrapper and its CLI
currently constrain it to the unallocated/refusal branch. Wire those owners;
do not infer admitted delta from downloaded row count or mint a positive literal.
An already activated receipt retains a positive observation count on replay;
`OverlayAdmissionReceipt.replayed` distinguishes that from newly admitted growth.
The positive bridge must consume that distinction. Native acquisition member/query
predicate production and independent verification must also be supplied: signed
policy transport and a populated appointment slot do not establish their truth.
The scoped qualification findings and removal probe are in `positive/`.

## AM-R04 — mandate registration and projection are different predicates

The upstream finding `U15-F06` names `DS15-MANDATE-INTAKE` as a successor handoff;
`OR-N13-04` subsequently measured exact-name absence in a selected active-plan
denominator and explicitly left semantic aliases unresolved. That is not proof
that no task exists anywhere.

The live ledger owner `_plan_inventory()` selects particular plan roots and
derives `DS<number>` identities from filenames. `_parse_gy_tasks()` accepts the
GY task-standing grammar and filters terminal and `not_started` rows. The emitted
measurement receipt itself says that ownership acts and unselected documents are
unresolved. These rules cannot be treated as a universal task-registration index.

Thus the defensible result is **no matching active successor established within
the examined authority boundary**, plus a known projection limitation. It is not
“genuinely unregistered” and not “an existing equivalent task proved registered.”
Those would each require an additional ownership/semantic-equivalence finding.
The detailed alias candidate reads, actual selectors and receipts are in
`mandate/`; the destination is team-architecture/team-runtime to reconcile that
successor, using the existing instrument-honesty row for projection semantics.
Do not open a duplicate task on a ledger zero.

## AM-R05 — proposed execution boundary and specific decision

Adopt the eight-row acquisition lifecycle as one coordinated lane, keeping its
closing acts distinct. Sequence its buildable links as follows:

1. Reconcile the mandate-intake allocation; extend the sanctioned deployment
   intake to compose the existing PA2 gateway, DS20 bound permission evidence,
   external delegation/currentness resolution and deterministic admission producer.
   Leave acquisition-purpose signer and institutional slots typed and empty.
   Refusal must be reachable through the real public request and durable worker.
2. Prove that composition reaches the existing factory-owned WDI port through the
   public action/worker path. Preserve missing authority, scope, attempt and replay
   refusals; do not count fixture worker evidence as production execution.
3. Connect the typed live evidence to the existing passport/admission/qualification/
   activation owners, retaining separate qualification policy/owner slots. Consume
   actual admitted membership and exact epoch receipts, then the existing same-case
   re-entry function. Preserve quarantine for every unmet prerequisite.
4. Build the native movement artifact and its GY admission bridge and per-row
   consumer from the existing receipt owners. An empty movement-policy selection
   fails closed. Retain the global N13b source's denied uses. The architect performs
   the separately evidenced register closing acts; this lane edits no register.

Split numeric VoI to the owner of its metric/decision/value/cost basis and education
to the original Phase-5/importer provenance owner. Neither can be discharged by
the acquisition corridor, and neither blocks building its engineering links.

**Decision requested:** adopt or revise this subject partition and reconcile the
active owner/task for the sanctioned mandate intake. Per the commission's explicit
Stage 1 split rule, no mechanism is implemented for an unratified ten-row group.
The stop is at that architectural partition/allocation act, not at an unappointed
signer, absent production data or the first refused runtime link.

## Pattern pass and review rule

P01/P02/P12: distinguish built local producers from absent production bridges.
P05/P15/P32/P37: qualify purpose/scope and evidence substance; placeholders, refs
and provider declarations cannot confer authority. P07/P08: bind exact case,
epoch, admission time and chronology cutoff. P29/P33: retain semantic refusal and
property-removal probes. P35/P36: complete selected denominators and cited finding
IDs, with aliases/unread inputs left unresolved. P38: ledger absence, constructor
presence and a successful direct port call are different proxies for their actual
properties. P40: deeper findings within the sanctioned-intake absence are one
class, not additional repair rounds. P41: education red is not inherited without
the original-slice replay **and** complete disjoint-input proof.

Acceptance for this Stage 1: every commissioned row is classified against opened
artifacts; GAP6's separate closing acts are explicit; the forcing code and existing
admission owners are located; task-selection uncertainty is preserved; the
non-acquisition subject is routed; research is committed and read back from the
attached branch before any production edit. Reviewers must bucket each escape as
a new class or the same class deeper, and must not treat a static census as runtime
authority.

## Incidental findings and destinations

| Finding | Destination and disposition |
| --- | --- |
| Local admission producer exists but the served authority provider is uncomposed; stale `deterministic_admission_bundle:producer_missing` surface | Acquisition authority-intake work, with producer label corrected only alongside truthful production-composition reporting. No vocabulary-only patch. |
| WDI port and route projection retain the historical fixture badge even when the concrete production class exists | Existing DS15 contract/surface owner; distinguish the legacy label from proof of an actual production instance. No unsolicited schema change. |
| Offline dependency bootstrap lacks cached wheels | team-devx/station evidence; recorded nonreceipts and explicit reused local dependency station. No product conclusion. |
| Raw evidence lacks a general ignore rule at this base | Lane-local journal `.gitignore` protects `raw/`; no repository-wide ignore or register change. |
| OpenAPI environment-derived drift | Existing `openapi-snapshot-pins-environment-derived-digests` owner; snapshot is neither regenerated nor changed here. |
