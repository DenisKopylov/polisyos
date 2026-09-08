# CORR capability lane — decisions and execution

Lane: `/Users/deniskopylov/polisyos/.worktrees/gy-corr`, attached
`codex/corr-capability`, base `9619f6d2d892d7994ae3f29d3230362c41862f2d`.
No auxiliary worktree is allocated. Ordinary local commits only; no push, GitHub
plugin, history rewrite, storage stash, full re-extraction or directory test run.

## Binding inputs and interpretation

The architect's `delta-ground-composition-and-stratum-budget` decision in
`docs/plans/active/DEBT-REGISTER.md@9619f6d2d` is accepted, not re-derived. The
run planning ceiling is 0.05, with 0.04 for relation admissions and a shared 0.01
construction reserve. The per-admission relation ceiling is 0.01. These are
configured budget parameters, not measured correctness bounds. Candidate
exploration is free; exhausted runs retain candidate custody under INT-K06.

The calibration stratum is operator family × target type × domain × input-only
difficulty tier. Model, prompt, birth cohort and reference version belong to
certificate epoch scope. Begin with one dated, pre-declared stratum. No bound is
published by this lane: no accepted-binding calibration has been established.

`adversarial-refusal-sensitivity-is-publishable-today` permits a separately named
refusal-sensitivity result. Every occurrence of that result carries:
**A high refusal rate on constructed mismatches is not evidence that accepted
bindings are correct.** Pre-declared mismatches are its denominator; matched
controls do not enter that denominator. Neither correctness nor the configured
grounding/relation ceilings may be inferred from it.

Rules 7–8 in `docs/reference/data-capability-requirements.md@9619f6d2d` govern
missing inputs: build the mechanism on independently addressed, explicitly
synthetic artifacts. `synthetic: true` travels in each constructed artifact and
its derived outputs. A mechanical recognition/test admission is a separate plane
from governed authority, which must refuse the synthetic chain. Missing data is
recorded in the existing requirements document, not converted into a code stop.

## A — CG2 refusal, frame and admitted-binding accounting

Extend `runtime/quality/grounding_bind.py`, the current CG2 owner. Its existing
per-certificate ledger is not a run ledger; the bounded baseline executes both
refused and matched controls to measure that distinction. A concept-owned
`grounding_calibration.py` may own frame/suite declaration and execution, calling
existing CG1/CG2 and L6/WMR owners rather than parsing their artifacts again.

A1 freezes a dated, content-bound suite before its first official execution.
Original intervention inputs trace to the real L6/WMR owner. Deliberate mismatch
derivatives and any reference scaffolding are marked synthetic. A benchmark
fixture cannot replace the real vocabulary denominator. All declared cases get
a terminal result, including ambiguity. Input corruption, changed declaration,
execution before declaration, fake/novel input and removal of actual refusal
must reject; matched controls still reach the mechanical supported path.

A2 enumerates the complete current input frame before CG0 outcomes are consulted.
Missing fields stay ambiguous; source-cluster components derive from shared
support provenance, not invented independent row IDs. Difficulty uses only input
properties. Outcome permutation must not change it; model/prompt/cohort/reference
changes stale certificate scope without changing stratum. Data-only input growth
must appear through the same owner without a code branch. Persist the controlling
frame once, not duplicate sorted/expanded audit views of it.

A3 adds a CG2-owned durable run admission ledger in `grounding_risk.py`, consumed
by the existing binder, which retains the sole authority decision. C owns forwarding its single
run-scoped handle through N4/controller/reentry. Reuse Core CAS and existing
Fabric file-lock/atomic-write primitives; do not copy N11's purpose-specific
ledger or alter its closed rules. Scope is a canonical run namespace. Under one
cross-process lock, resolve/rederive admission history, perform the pre-emptive
cap check, and persist a bound, chained admission event. Candidate attempts are
not spend events; certificate replay is idempotent. Missing cache heads cannot
reset spend; corrupt/unreadable established state cannot initialize new authority.
Independent owners of the same run must share the cap.

Newly minted CG2 records move to an explicit v2 carrying synthetic provenance,
run admission and candidate-custody semantics. Preserve v1 parsing and its exact
historical hash projection; do not silently claim old certificates were run
budgeted. Missing budget context or exhaustion preserves the candidate with
`run_continues=true`, INT-K06 custody and `correctness_bound=None`. The governing
resolver, not a caller boolean, decides whether an admission is eligible.
The residual construction reserve receives no invented component split.

The synthetic mechanical test namespace exercises the same admission transition
with genuine owner checks but cannot grant production authority. Its falsifiers
are many attempts/few admissions, duplicate replay, four admissions followed by
candidate custody, independent-owner races, restart, and crash between immutable
event and head update. Removing admission-only charging or the pre-emptive cap
must fail while the supported control remains valid. Publish the distinction
between this mechanism proof and absent empirical calibration.

The existing `check_grounding_bind_contract.py` still requires cold-start
attempts to exceed their budget. A3 replaces that default, so its existing
validator advances the current report from `grounding_bind_contract.v1` to v2.
Preserve the complete original relation and mutation denominators; replace the
old spend assertion with the new admission-only property and add its removal
probes. Historical v1 certificates retain their own reader/serialization and
the previous report is cited at its git revision. This is the required governed
replacement companion for A3, not a reopening of the closed CG2 task. A second
CG2 validator cannot be used to avoid the affected owner's red result.

## B — subject-aware legal recognition

Foundry owns the new semantic comparison: use a concept-named
`foundry/validation/legal_correspondence.py` for strict subject-spine source
parsing, Core ArtifactStore resolution and comparison. The existing runtime
`intervention_substrate.py` stays the L6/L3 bridge and sole existing bundle parser;
it delegates typed source references to Foundry. Unit constraints are not a
legal-subject owner. An existing content-bound owner-authority manifest may
carry the independent source descriptor; no parallel artifact store is added.

The synthetic spine is produced from separately frozen lever-membership and
norm-membership inputs, without accepting the proposed law→lever mapping. Persist
it before evaluating proposals. Different producer strings are not independent
authority: source ancestry overlap rejects circularity, and actual legal truth
remains unestablished. Synthetic annotations of real identifiers are explicitly
synthetic controls, never claimed institutional legal identities.

Source provenance requires an explicit boolean synthetic marker, without a
false default. The synthetic producer requires marked inputs; the generic reader
can substitute independently addressed real source bytes under the same schema.
A typed source-authority reference remains unverified here. Flipping the marker
or supplying an unsupported authority reference cannot grant governed authority.

Recognition has passed/rejected/ambiguous outcomes relative to the addressed
source. Governed authority remains blocked for synthetic input. Missing subject
returns ambiguous **before** units/threshold evaluation, with numeric evaluation
explicitly not run. Always retain law/knob association so uncertainty cannot erase
the blocking dependency. Correct and transposed pairs must respectively pass and
reject recognition; a missing-subject/bad-unit control proves subject precedence.
Fake refs, altered source bytes, circular producers, transposition and data-only
new members exercise the same real owner. Removal of subject validation makes
the unchanged transposition gate red while the supported pair remains valid.

The law-resolution lift moves to v3, with explicit v1/v2 historical readers and
original hash projections. Bundle/knob/route epochs remain v2. S3's current report
moves to v3. Preserve the existing incomplete credal dependency and association;
do not bump its schema merely for a changed input hash. Any actual rule/schema
change discovered there is recorded before editing. Recompute required generated
companions through their actual owners rather than restamping historical claims.

The S3 strangle packet itself advances from
`intervention_substrate_strangle.v1` to v2: its current default transitions now
include early subject recognition, and complete Python source identities are
reconciled in memory while the receipt retains their count, independently
derived hashes and difference. Prior v1 packets keep their historical bytes;
the packet's new shape is not emitted under the old epoch.

## C — bounded re-extraction, then preservation wiring

C1 extends the existing Academic rich `PolicyArticleExtractor` and current claim
transport/reassembly owners. A concept-owned `batch/abstract_reextraction.py`
orchestrates a declared subset and stage cost accounting; it does not introduce
another extraction parser. The closed canonical-class alias repair is verified
and reused. Preserve the difference between a missing source class and an
explicit unknown at the new intake boundary, before normalization loses it.
Never infer that class from an adjudicated design.

Input is the held read-only Academic database; output is a new lane-local store.
Never point destructive graph rebuilding at the held substrate. Persist current
candidate evidence class/status, separate extraction confidence/design, input
provenance, model/prompt/rule/schema pins, source basis and downgrade warnings.
Exercise existing ingest, exact, family and contested consumers. Contested
non-emission is not a zero-confidence row. Synthetic outputs remain synthetic
and candidate through governed N7/CG2 consumption.

Freeze the no-call subset manifest before provider execution. Its selection uses
the complete nonblank held-abstract frame, input-length terciles and stable salted
identity ordering; no outcome-based replacement. The bounded pilot uses the
declared six inputs, concurrency one, at most eighteen phase calls, one transport
attempt per call and a 120-second per-call ceiling. Preserve every submitted
identity's terminal outcome. Existing OpenAI-compatible transport may use the
already configured provider credentials/endpoint without copying secrets. No
fulltext acquisition and no full pass occur.

Record actual screening/extraction/self-verification calls, attempted and billed
tokens when available, elapsed time, failures and provider cost when supplied.
Missing cost is not zero. Estimate the full pass from declared stratum weights
and conditional phase frequencies, explicitly as a small-pilot estimate with
uncertainty. Synthetic timing cannot masquerade as measured provider time.
Self-verification is not independent entailment authority. A credential failure
does not stop construction, and is reported as a measurement limitation rather
than a fabricated full-pass price.

The C1 provenance measurement requires extending the existing raw-claim ingress
in `graph_builder.py` and the existing quality metadata in `edge_synthesize.py`.
Carry each source's explicit synthetic marker into raw rows and exact/family/
contested edge provenance. C also owns the conditional L2 exact-edge provenance
handoff in `credal_reference.py`; the family edge already retains quality signals.
Historical absence stays absent, preserving its original hash. The decisive
consumer test uses the real production CG2 owner against marked source support;
unadjudicated non-emission alone is not evidence of synthetic refusal. This
extends the existing owners and does not reopen the closed class-alias repair.

The subsequent complete L2 consumer inspection found sibling variable, claim,
and contested views. This is the same provenance-loss class, so C replaces the
proposed helper-level fix with one `_iter_l2_edges` source boundary: an actual
synthetic raw claim marks every L2 output from that snapshot synthetic. This is
a declared conservative snapshot scope, including mixed-source snapshots; a
mixed-source falsifier pins it. Per-edge metadata is also retained, but cannot
silently narrow that source limitation. A historical snapshot with no synthetic
column retains absence and its existing bytes. No further instance patches are
used for this class.

C2 retains `ShadowGeneratedCandidate.atom` and its actual parsed proposal, keyed
by `(design_problem_ref, candidate_id, atom.content_hash)`, plus the enclosing
`DesignGenerationOrganRun.trinity_bundle`. C owns `generation_cycle.py` and
forwarding-only changes in `design_generation.py`; A owns the CG2 implementation.
Use the same verified cycle substrate/WMR and existing N9 context-provider seam.
Never reconstruct a writer input from CandidateSummary or catalog defaults.
Persist/replay source identity through reentry; duplicate, mismatched and missing
bindings fail closed. Removing the handoff must break actual N9 source consumption.
If C1 yields no real forwardable reference, complete this wiring on declared
controls and prove the real missing-input negative, naming the exact missing input.

C2 advances the N6 run artifact from `policyos.runtime.generation_cycle_controller.v1` to v2 when its
source-handoff references and run-emitted preservation strangle are added.
Preserve historical v1 serialization without injecting the new fields. Retain
actual organ objects during a run and persist their typed payloads through the
existing Core CAS. The run carries the immutable source-handoff artifact ref;
reentry resolves that exact ref and reconciles the full problem/candidate/atom
identity, instead of consulting a new mutable run-index service. Missing or
corrupt source payloads remain typed absence. The existing N9 context provider
consumes those retained owners only after its protected admission boundary.
A's admission ledger remains the sole mutable run-budget owner. N6 does not
reconstruct a parsed atom, Trinity bundle, certificate or WMR from a summary.

## Execution ownership and verification

- A owns grounding/calibration source, its mirrored tests and audit surface.
- B owns Foundry subject recognition, runtime intervention bridge, necessary
  credal handoff, S3 report and mirrored tests.
- C owns Academic subset pipeline and N4/N6/N9 source forwarding and tests. It
  integrates A's run-budget API in its files after the agreed interface exists.
- Root owns this plan, completion journal, shared requirement/register proposals,
  public facades/inventory and final integration. Each worker owns its own journal.

Serialize shared owner scratch/DuckDB writers and generated artifacts. Held
databases are read-only; each workstream uses separate scratch/output roots.
Serialize every commit with all writers, including evidence capture completion.
Declare/commit suites and provider subsets before running them. Write each
behavioral falsifier first, observe its substantive failure, then implement.

Run exact affected test files/nodes and importer tests, recomputing owner checks
and corrupt-field/removal probes, Ruff and architecture guardrails. Preserve
normal pytest import mode and put the lane venv first in PATH. No directory/full
test suite. Freeze source, complete reviews, then run the integration wave once;
later changes reprice only their actual affected checks.

Retain complete deciding gate/probe outputs once. Cite tracked inputs as
`path@sha`; retain two pins plus a delta instead of copied comparison sides.
Do not store derivable field/key/identity views alongside source data. A controlling
pre-declared suite/frame is a functional artifact, not an extra audit copy.
The existing capture harness is reused; no parallel command recorder is built.

Pattern pass: P01/P02 require actual production bridges and downstream consumption;
P05/P15/P32 synthetic/candidate inputs cannot grant authority; P07/P08 preserve
historical epochs and pre-outcome timing; P14/P35 reconcile complete sources and
independent clusters; P27/P28 keep single owners and default-flip StrangleReceipts;
P29/P37/P38 test the deciding property; P40 buckets repeated-class findings before
another repair; P41 never calls a red inherited without exact base/disjointness.
Missing capability labels and final acceptance belong in each workstream journal.

Handback: `2026-09-08-corr-a.md`, `2026-09-08-corr-b.md`,
`2026-09-08-corr-c.md`, and `2026-09-08-corr-completion.md`. Report C1's full-pass
cost estimate on its own line. Keep built/falsified work separate from incidental
findings routed to named rows/rules/explicit nowhere. Do not edit DEBT/LEDGER or
run their checker. Data requirements are appended to their existing owner doc.

## Source checkpoint and cost-scope correction

The A/C1 foundation is committed at `2ad1e8b47b5ba2bccc6cbba96fb206112c6fbd06`
and read back from the attached branch without mismatched blobs. This is a source
checkpoint, not a final workstream claim. The controller epoch above is the actual
existing `generation_cycle_controller` schema, correcting the earlier shorthand.

C1's unchanged primary declaration covers the whole held-abstract frame. Its
relationship to the historical raw-claim source works is measured separately
before provider outcomes. Append a dated secondary cost target over the raw-origin
works with available abstracts, using their weights in the existing input-length
terciles; retain unavailable source works explicitly. Do not replace any selected
pilot input. A secondary forecast applies observed phase costs from the same
pilot only under a stated exchangeability assumption within those tiers. It is
a conditional decision estimate, not an empirical representativeness or precision
claim. Neither forecast is the price of reacquiring fulltext.

C2's marked direct source-provider/EFFECT-writer control and actual protected
N9 refusal are distinct witnesses. The existing positive epoch test helper
authors an appointment receipt and cannot satisfy this lane's synthetic marking
constraint for its strict protected DTOs. It is therefore not used to manufacture
a protected positive admission. Source retention proceeds; positive protected
integration remains `not_established` until actual owner input exists.

The existing N6 report advances from
`policyos.policy_design_case.layer3_gy.generation_cycle_contract.v1` to v2 with
the controller run's preservation fields. The separate existing
`policyos.layer3.gy.n6.generation_cycle.v1` refinement rule is unchanged. The
new preservation strangle names its own source-custody schema/rule; it does not
repurpose refinement evidence. Measure the existing comparison owner's actual
red before admitting a narrowly governed report reissue, and preserve historical
report bytes rather than restamping their identity.

## Required new-input consumer and reentry companions

CORR-A owns the compatibility migration when new CG2 v2 synthetic provenance
reaches the existing CG3 consumer. Its closed novelty/obligation/registry
algorithms are not reopened. The existing single CG3 decision producer must
recompute complete reference ancestry together with the input certificate marker,
retain candidate/shadow computation, and refuse production authority. Fresh
`policyos.runtime.grounding_admission_certificate.v1` and its
`policyos.runtime.grounding_admission.cg3.v1` validator advance to v2; the
existing `policyos.policy_design_case.grounding_admission_contract.v1` report
also advances to v2. Historical v1 serialization/hash omits new source-limitation
fields. The complete original relation/control/mutation sets remain measured;
canonical-input withholding and marked structural controls stay separate. The
pre-existing v1 declaration behavior is routed to closed GY-CG3 history, without
retrospective receipt repair. The falsifier keeps synthetic source ancestry but
removes its authority limitation: the fresh governed consumer must go red while
ordinary candidate and shadow computation still works. This is one complete
consumer migration for the new input, not a per-caller workaround.

C2's existing acquisition-overlay reentry returns its own receipt, so newly
retained sources must survive that return as well as GenerationCycleRun. Advance
`policyos.runtime.acquisition_overlay_reentry.v1` to v2 with immutable source refs
and the distinct preservation strangle. Preserve historical v1 hash/serialization.
Reentry continues to consume its original immutable run source and A's same run
budget; it does not create an independent source index or reset the allowance.

## C2 import ownership correction during integration

The first implementation eagerly imported the complete source capsule from N6,
thereby loading N4/Trinity/CGF schemas even for unrelated N6/N9 imports. A's
CG3 probe subsequently timed out during imports and then exited with signal 11
while Pydantic gathered a schema. That is an execution failure, not evidence of
the proposed CG3 authority defect; attribution remains unestablished until replay.
Keep the lightweight source-preservation receipt beside N6's existing run and
strangle DTOs. Load the source repository only when custody is used, retaining
full validation at that boundary. This restores N4's existing lazy ownership
without changing any artifact payload or epoch. The falsifier is the exact
previously failing CG3 invocation followed by actual source-custody execution;
moving a failure from import to first use would not satisfy it.

## C2 evidence-bridge provenance companion

The existing N9 evidence bridge v2 stores source references but cannot carry a
synthetic provenance field in its own body. CORR's newly emitted marked-source
bridges therefore require a governed v3 bridge epoch. Root owns this narrow
`promotion_sequence.py` companion and the new CG2 contract-scope compatibility
predicate; C owns its actual-source controls and controller wiring. The evidence
union is unchanged. N9 receipt v6 and owner projection v3 remain unchanged, with
the existing `producer_root_refs` carrying the new bridge epoch. Historical v1/v2
bridge bodies remain readable under their own epochs and are never restamped.

Derive the bridge's marker from resolved source content and bound candidate
provenance, then independently recompute it on resolution. Synthetic source
content cannot yield an authority-grade established resolution. Preserve the
underlying producer's mechanical outcome as evidence, with the authority
limitation distinct. The red-first controls require a real marked source to emit
a marked bridge, reject a concealed marker after complete rehashing, and retain
the historical bridge's exact body. A source-ref string alone is insufficient.

The existing N9 report input helper also changes a real CG2 result into a claimed
bind by editing safe candidates, obligations and revalidation before rehashing.
That is a static P29/P37 finding in the current report input companion, not a
reason to reopen N9's closed obligation algorithms. Root will measure whether
the returned certificate equals the actual producer output before any repair.
The current CORR proof must consume an unchanged, explicitly marked owner result;
all existing report control identities and historical readers remain required.

## Typed source transport, measured before its correction

The real EFFECT writer rejects the first capsule roundtrip because an original
Decimal intervention parameter became a string in Trinity's `Any` field. JSON
equality would hide that material change and is not an acceptable test. CORR-C
uses the existing Core canonical typed encoder/decoder at the sole capsule
boundary, hashes that complete typed payload excluding only its own hash, and
retains full CAS byte binding. The source capsule is an unreleased v1 artifact;
no historical receipt is rewritten. The falsifier preserves exact original
Trinity/atom/parsed-candidate values through persistence, then invokes the real
writer; changing a numeric value to a same-looking string must remain detectable.

The complete current historical N6 comparison found exactly four absent-to-null
additions: acquisition cost basis hash/record in each retained cycle. Preserve
the original supplied-field tree when serializing a historical v1 run or reentry,
using its existing typed models; current v2 emits its full contract. This is
historical byte preservation for CORR's new envelope, not a repair of the older
cost-basis algorithms. Keep the complete historical owner-record denominator and
exact N9 roundtrips in the acceptance test.

CG3's existing registry patch and admission ledger are independently emitted
content-addressed artifacts as well as children of the certificate. The same
synthetic-carriage migration covers that complete emitted set: each receives
its recomputed marker and advances its existing schema from v1 to v2, with exact
historical v1 serialization and hash behavior. Their shadow-only algorithms and
authority ceilings are unchanged. A owns the complete emission census and these
DTO companions; B's current CG3 report consumes them through the existing owner.
An enclosing marker alone does not mark an independently returned child artifact.

## N9 source-artifact emission boundary

The bridge audit found the same synthetic-carriage class one level deeper (P40):
the existing effective-independence and EFFECT writer records are independently
persisted CAS artifacts. Their nested input provenance does not supply each
artifact's own marker. Widen the existing N9 source-record mechanism to these
owned emissions, rather than repair individual caller declarations. Both source
record schemas advance from v1 to v2; exact v1 bodies remain readable and cannot
be restamped. Derive the marker from the complete actual writer inputs and bound
candidate, share that derivation with bridge admission, and recompute it when
resolving. Keep the independent producer result distinct from authority.

The measurement source is consumed from its existing DataForge owner, not
produced by this bridge. CORR must not invent one to fill C2's missing input.
The source-boundary falsifier asserts an own marker on each actual synthetic
source artifact before bridge admission, then conceals a declaration while
retaining the original ancestry. This belongs to CORR-C's new synthetic input
compatibility; it does not reopen any closed evidence calculus.
