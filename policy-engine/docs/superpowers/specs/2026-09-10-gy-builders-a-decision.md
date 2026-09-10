# GY-AQ1 decision: candidate non-data acquisition on Fabric evidence owners

Stage 1 decision, 2026-09-10. Source is the lane's immutable merge base
`07c89304d`; this decision was committed before execution at `c628361c5`.
Stage-2 amendments below record the implemented boundary. The task definition is
`docs/plans/active/layer3-slices/GY-engine-subordination.md` §9, GY-AQ1.
The binding claim rule is `W5-K01` in
`docs/system-design-decisions/wave5-evidence-substitution-ratification.md` §4.1.
INT-R2 `AUD-F007`, its amendment §4.2, and routes `W5-R2-Q02`, `W5-S02`,
`W5-R2-Q14` supply the field-level design inputs. The research is not an
institutional appointment or a universal taxonomy.

## Decision and ownership

Build the residual-shape classifier, candidate artifact intake, ceiling evaluator,
persisted decision, and demanding-owner re-entry bridge under
`polisyos.fabric.evidence`. Extend the existing Fabric evidence plane and reuse
`core.artifacts.FileSystemCAS` for exact content storage and the existing
`fabric.data_plane.evidence_journal` append/fsync/read-back primitives for run
evidence. Those primitives already execute successfully in the research probe;
they are not a new storage system.

`runtime.quality.acquisition_planner` remains the sole routing owner. A genuinely
new orchestration bridge in `runtime.quality.non_data_acquisition` composes its
unchanged `plan_evidence_acquisition` and `persist_acquisition_planner_report`
entry points with the Fabric owner. It accepts an existing typed `AcquisitionGap`
from the demanding owner, verifies its claim/gap binding to the non-data demand,
and supplies the persisted canonical route report to the Fabric run. It contains
no type-to-strategy table, no planner subclass, no routing policy, and no default
gap. CG5 remains a router. The new engine does not rank routes or reproduce ADR-0166.
The existing data-acquisition planner/executor path is not replaced or repaired:
it acquires observations, whereas this path requires a non-data object. There is
therefore no replaced predecessor and no fabricated StrangleReceipt. The new
entry is enabled whenever that typed request is used, without a feature flag.
An integration test enters through the canonical planner and reads the persisted
result through the audit consumer.

The broad eight-case intake owner was not allocated in INT-R2's research. This
task allocates the software owner only. Actual relation adjudicators, estimand
owners, external truth/change owners, mandate grantors, normative bodies,
capacity assessors, competent humans and assurance institutions remain external
typed evidence producers. No default principal, appointment or signature is made.

The owner candidates inspected were `acquisition_planner.py`,
`acquisition_executor.py`, `acquisition_route_loop.py`, Fabric's evidence bundle
and evidence journal, and core CAS/signed-evidence adapters. The planner supplies
routing; the executor supplies data-overlay passports; the route loop supplies a
data-acquisition world-commit lifecycle. None may be renamed into an institutional
object producer. The Fabric evidence plane is the lower-layer location that all
these consumers can use without importing Runtime into Fabric.

## Mechanism and seams

The admission plane accepts a content-bound demanding predicate, candidate object,
registered vocabulary content, requested use, and an independently allocated
owner/verifier port. A missing port or non-resolving target refuses; a caller's
boolean, role name, `binding_gap`, evidence label or row count cannot supply it.
The owner resolves actual content before classification and before consumption.
Classification recomputes each positive and nearest-sibling exclusion from the
resolved demanding predicate. A compound demand yields `split_required`; an
unreadable or unknown demand yields `not_established`.

Persisted process facts carry schema/rule version, exact input refs, owner identity,
scope and evaluation time. A successful candidate admission produces
`admitted_reentry_required`, not closure. The demanding owner must rerun against
the admitted candidate and current requested use. Every emitted result carries a
structural candidate-only authority boundary and an empty institutional signer
slot. Process closure, when an independently recomputed candidate predicate
passes, has no approval, publication, truth or mandate consequence.

The implemented `AcquisitionEvaluationContext` is immutable and supplied to both
semantic verification ports and demanding-owner re-entry. It binds request,
claim and gap identities; full demand hash; exact candidate, vocabulary and
optional planner-report refs; every requested-use dimension; and an aware
evaluation time. Audit recomputation rebuilds this context from persisted inputs
and the requested evaluation time. A ceiling-admitted use can still fail the
owner's narrower predicate; an absent context cannot invoke an older context-free
port successfully. Independent review found the initial use/time omission as a
new P02/P10 class; this is the whole-port-context correction, not a default use.

The audit reader reopens the persisted artifact and recomputes the decision; a
caller-constructed or edited result is not authoritative. The evidence/verifier
interface is public at the internal module boundary and accepts independently
allocated implementations. AS1 can own its oracle and expected-output corpus
without importing the runtime decision function. AQ1 does not implement AS1's
63-case battery or claim independent assurance of itself.

## Exact eight ceiling relations

These are the eight formerly deferred semantic dimensions in INT-R2
`AUD-F007` / amendment §4.2, not the eight acquisition-type discriminators.
The software owner of every row is
`polisyos.fabric.evidence.ceiling_relations`; vocabulary definitions are explicit
versioned data resolved through that owner. Arbitrary labels cannot introduce
edges. Content registration establishes a candidate definition, never legal or
institutional standing.

| Dimension | Exact implemented relation | Positive and falsifier |
| --- | --- | --- |
| Population | Requested population's resolved member set is a subset of the ceiling population's member set, both definition/version bound. | Proper subset passes; a same-name different-version population or one extra member refuses. |
| Jurisdiction | Requested jurisdiction/competence is reachable in a resolved directed subordination graph for the exact act, with overlapping incomparable nodes refused. | A registered competent child passes; a sibling or unproved overlap refuses. |
| Purpose / audience | Both requested purpose and requested audience are below their respective ceiling nodes in registered subsumption partial orders. | Narrow purpose and audience pass; widening either alone refuses. |
| Source → target context | Exact source and target identities are connected by a current registered compatibility/transport witness; equality is not a transport default. | Bound compatibility passes; absent witness or changed target refuses. |
| Evidence class | Registered evidence-class-to-claim-class mapping permits the requested claim class; no inference from a class name. | Explicit mapping passes; an unmapped stronger claim refuses. |
| Maintained assumptions | Exact requested assumption identities are covered by the ceiling and each required assumption resolves current at use time. | Complete current coverage passes; a missing, changed, expired or unknown assumption refuses. |
| Maximum claim strength | Requested strength is below the bound strength in a registered acyclic partial order. | Declared lower strength passes; incomparable or unknown strength refuses. |
| Maximum commitment stage | Requested stage is below the bound stage in a registered stage partial order and requested load does not exceed the bound load. | Narrower stage/load passes; larger load or incomparable stage refuses. |

The four directly mechanical dimension families also remain mandatory: exact
claim/action membership with deny precedence; exact subject/object identity;
time interval containment/currentness; exact permitted operations/prohibited uses.
Rule/epoch/downstream-gate identities are exact controls. Unknown fields, absent
definitions, malformed registries, cycles, unknown nodes, ambiguous relationships
and incomplete requested-use denominators fail closed. No unknown becomes the
first enum, an empty set, equal context, the default jurisdiction, or unlimited.

The complete runtime vocabulary is obtained by walking the registered data's
actual dimensions/nodes/edges, not an allow-list of fixture cases. A test adds a
previously unseen valid definition and its relation via data alone and exercises
it through the real owner; the malformed sibling refuses with unchanged code.

## Eight acquisition predicates

The commissioned type denominator is the full union in INT-R2 §4.1, independently
cross-checked against the eight rows of the amendment's classifier table.

| Type | Positive demanding predicate | Nearest sibling falsifier |
| --- | --- | --- |
| `grounding_relation` | Target meaning is fixed; the scoped causal relation warrant is missing. | Unbound target attribute selects estimand; finite-sample precision alone is data. |
| `estimand_binding` | A required regime/population/outcome/horizon/intercurrent-event/contrast attribute is absent or ambiguous. | All target attributes bound and only warrant absent is relation. |
| `owner_writability` | Exact canonical object/field/operation mutation requires missing substantive or technical right. | External lawful competence without canonical mutation is mandate. |
| `legal_mandate` | Exact jurisdiction/actor/act requires a missing competence/delegation link. | Competence present and regime consent missing is normative authorization. |
| `normative_authorization` | Established regime/purpose/version requires a missing determination. | Unestablished issuer/procedure is unknown, not inferred mandate or consent. |
| `implementation_capacity_evidence` | Exact next commitment/load/environment/horizon has missing critical prerequisite evidence. | Legal prohibition or missing causal relation selects its own object. |
| `competent_human_decision` | Case-specific question/role/competence/subject requires missing reconstructable judgment. | Assurance engagement/criteria/independence/level selects audit. |
| `independent_audit` | Exact subject/criteria/scope/period/level requires missing independent assurance work. | External professional judgment without assurance engagement is decision. |

## Refused claim and design falsifiers

**GY-AQ1 continues to refuse the claim that more rows in one data stream establish
a missing non-data object; resolution is driven only by resolved object evidence,
ceiling checks and demanding-owner recomputation, and same-stream volume is not
an input to those transitions (`W5-K01`).** Candidate artifact receipt and even a
candidate predicate passing do not establish institutional authority: every
result retains the typed empty signer and candidate-only authority boundary.

Write the W5-K01 negative first: through the real planner/engine, keep an exact
missing non-data object fixed, increase only rows, and require identical resolution
state and blocked authority. Then prove every type's positive and sibling negative,
all ceiling fields' unknown rejection, and no cross-type substitution.

The design is falsified by any of: a fake object ref admitted; an unknown ceiling
value accepted; a row-count-only resolution movement; one branch collapsing into
its sibling; caller-declared success bypassing owner re-entry; an unsigned object
becoming authority; a candidate receipt being read as approval; a new vocabulary
entry requiring code; or the binding contract remaining green after removing real
owner validation while retaining marker strings.

P37 predicate grades are frozen in receipts: structural demand classification is
`recomputed` with the explicit `candidate_demand_structure_only` scope, while
institutional truth/standing is `not_established` and cannot turn on authority.
Content identity, registry consistency and set/graph/interval relations are
recomputed. Separately allocated ports actually compare resolved candidate
content for the bound context; their identities are recorded, but this is not a
claim that AS1 or institutional independent assurance has been performed.
P38 limitation: correct comparison of candidate
definitions is not proof that an external institution accepts those definitions.
That divergence is enforced by the output boundary, not left as prose.

## Stage 2 write set and checks

Mechanism paths: new `src/polisyos/fabric/evidence/non_data_acquisition.py`, new
`src/polisyos/fabric/evidence/ceiling_relations.py`, and the new composition-only
bridge `src/polisyos/runtime/quality/non_data_acquisition.py`. Authored relation
vocabulary data lives in `src/polisyos/fabric/evidence/ceiling_vocabulary.json`;
candidate specimen builders live in the named tests without a duplicate derived
fixture directory. Tests are the named files
`tests/unit/fabric/test_non_data_acquisition.py` and
`tests/unit/fabric/test_ceiling_relations.py`; existing planner regression tests
will be selected by explicit file/node names after importer discovery. Documentation
companions are this decision, the A journal and the nearest README (root serialized).

Each gate is a separate invocation through `.venv/bin/python -m`, with venv first
in PATH. Retain complete red, green and removal-probe output under
`docs/superpowers/journals/gy-builders/a/`. The targeted behavioral contract covers
§3.5.6's full-denominator, fake-owner, data-only growth and decisive-property mutation.
Read the failure register again before closeout. The default architecture gate is
`not_completed`: its forbidden debt-compiler chain cannot run in this lane.

Stage-1 amendment: an additive method on the existing planner was rejected after
reading its decisive `owner-record` identity in the N11 confidence ledger artifact.
The composition bridge above reuses actual routing and persistence operations
without changing those bound source bytes. This is an ownership decision, not a
subclass invented to evade receipt identity. No governed promotion/calibration
epoch is intentionally moved. Any discovered
receipt-affecting change must be declared as one transition from the immutable
merge base, coordinated with the root before editing; a task-local-start transition
is not valid. No debt-register or ledger edit is authorized.

## Pattern pass and routed residuals

Relevant patterns: P01/P02 (wire artifact→bridge→consumer), P05/P15 (candidate
evidence cannot authorize), P27 (planner and persistence reuse), P29/P32/P33
(execute actual owner and mutate decisive validation), P35 (complete denominators),
P37/P38 (measured predicate versus declared institutional fact). The pre-build
missing labels are `artifact_missing`, `bridge_missing`, `consumer_missing`,
`verification_missing` and `semantic_test_missing` for this allocated mechanism;
institutional producers remain `producer_missing`. Audit output is in scope;
Atlas UI work is `surface_out_of_scope` and routes to DS15/GY-VC1.

`int-r2-ceiling-vocabulary-owners` receives this software ownership and explicit
eight-relation implementation evidence; its register is intentionally unchanged.
The canonical lattice crosswalk remains GY-VC1. The independently owned assurance
battery remains GY-AS1. Institutional domain procedures remain the existing
`w5-institutional-authority-slots` row, never a reason to defer the mechanism.
