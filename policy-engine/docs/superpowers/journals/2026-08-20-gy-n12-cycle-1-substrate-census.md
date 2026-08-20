# GY-N12 Cycle 1 — Inward Substrate Census

## Receipt and boundary

This census is a read-only measurement of attached branch
`codex/gy-n12-epoch-chronology` at
`1360b1cb592be6a19c162a3ec3ddb5a2e87986c7`. The tree was clean before the
measurement. It covers the complete tracked `policy-engine/src` and
`policy-engine/tests` trees; file counts below are counts of files containing
at least one literal, not occurrence counts.

No PolicyOS runtime result is admitted in this cycle. The admissible baseline
is local Git plus Python 3.14 standard-library inspection of exact HEAD blobs.
The worktree has neither `.venv` nor `production_data`, and the host `uv` is
0.10.6 rather than the 0.9.21 named in the admitted GY-DI1 reconstruction.
The documented `research` extra resolves `torch==2.10.0`, while the frozen N8
runtime identity cannot discriminate that environment. Bootstrapping that
profile would therefore reproduce `GY-DEF22`, not cure it. Runtime imports,
generated-owner scanners, validators, and artifact replays remain
**inadmissible until the GY-DI1 profile is reconstructed exactly**.

The governing time boundary is already ratified: the Custody Time Model has
nine sparse roles, relates them instead of collapsing them to clocks, requires
explicit query coordinates and family-native persistence, and refutes a
universal persisted `OperationalEventEnvelope`. This census therefore looks
for reusable chronology semantics, not a generic event log.

## Complete-denominator method

Two independently written walkers produced every count.

1. The Git walker enumerated every tracked blob below each root with
   `git ls-tree -r -z HEAD`, read exact HEAD bytes through
   `git cat-file --batch`, and tested literal membership in each blob.
2. The filesystem walker independently enumerated the clean worktree below the
   same roots and tested the same byte predicates directly.

Positive controls (`schema_regime` and `case_lifecycle`) were required to be
non-zero. The walkers agreed on every row. Their complete denominators were:

| root | tracked files | Python | Markdown | JSON | YAML | other |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `policy-engine/src` | 2,771 | 2,561 | 164 | 10 | 11 | 25 |
| `policy-engine/tests` | 2,894 | 2,394 | 100 | 381 | 11 | 8 |

The Git walker classified all 2,771 source blobs as text. It classified 2,892
test blobs as text and two `.pkl` blobs as binary; binary blobs were still read
as bytes. The second walker returned the same symbol results over the same
2,771/2,894 path denominators. Thus a zero below means neither complete walker
found a member, not that a search index returned nothing.

The literal census adjudicates the supplied count claims only. It is not used
as a proxy for semantic-owner absence. For that question, a separate reuse
census followed every owner named by the Custody Time Model's binding
subordination table: Fabric/Data Forge validity and stores, core integrity,
evidence/claim/decision admission, Decision Validity, Claim Ledger, Lex, and
family verifiers. That owner-guided pass found important currentness and
lifecycle owners described below; none supplies controlled-release membership,
production recursive-run enumeration, exact row movement, or the common
append-only consistency property.

## Supplied count adjudication

The two spellings in a slash-separated row are one OR predicate. Every supplied
claim is verified; none is refuted at this HEAD.

| symbol predicate | supplied src/tests | measured src/tests | verdict |
| --- | ---: | ---: | --- |
| `schema_regime` | 30 / 28 | 30 / 28 | verified |
| `effective_from` | 30 / 25 | 30 / 25 | verified |
| `branch_mode` | 3 / 4 | 3 / 4 | verified |
| `revalidation_required` | 8 / 8 | 8 / 8 | verified |
| `rule_evolution` | 17 / 12 | 17 / 12 | verified |
| `case_lifecycle` | 12 / 10 | 12 / 10 | verified |
| `OpenWorldRisk` OR `open_world_risk` | 0 / 0 | 0 / 0 | verified zero |
| `epoch_scope_unresolved` | 0 / 0 | 0 / 0 | verified zero |
| `EvidenceValidityEvent` | 0 / 0 | 0 / 0 | verified zero |
| `release_family` OR `release_transcript` OR `disclosure_transcript` OR `controlled_release` | 0 / 0 | 0 / 0 | verified zero |

## Substrate findings

### Bitemporal world facts — `implemented`, not the epoch owner

`fabric/evidence/fact_writer.py` persists facts with source-supplied
`valid_time` and writer-assigned `tx_time`; fact identity binds valid time and
provenance, while transaction time remains the receipt coordinate. The world
query path accepts explicit `as_of_tx_time` and `as_of_valid_time` and resolves
visible facts under both. Snapshot metadata carries both coordinates.

`fabric/world/store/segments.py` also has append-only assertion, correction,
revocation, branch-assertion and scenario-assertion mutations. That is useful
family-native history, but it neither enumerates semantic epochs nor proves a
release or recursive-run transcript complete. `fabric/world/events.py` can
mint generic current timestamps when omitted; using it as the chronology owner
would rebuild the refuted universal envelope and conflate semantic boundaries
with observation/transaction clocks.

State: the bitemporal fact/query capability is **`implemented`**. Its use as an
N12 epoch producer is **`absent/unallocated`**, not `bridge_missing`: no typed
epoch artifact or producer exists to bridge.

### Regime and amendment inputs — `implemented`; epoch derivation —
`absent/unallocated`

`runtime/quality/substrate_registry.py` already lifts every registered L5
entry into a strict `SubstrateSchemaRegime` with regime identity, authority,
effective start/end, boundary buffer and source version. The Ukraine builder's
registry contains v1 and v2 records and a 2022-02 changepoint as data. The L3
legal graph carries amendment rows and `effective_from`/`effective_to`
coordinates.

Those are real source inputs. No owner derives fixed-semantic intervals from
the complete L5-regime plus L3-amendment denominator, resolves a scope at an
explicit coordinate, emits `epoch_scope_unresolved`, maintains heads, or
marks downstream certificates stale. Consequently:

- regime/amendment input contracts and producers: **`implemented`**;
- generic epoch derivation, history, artifact, and owner: **`absent/unallocated`**;
- `OpenWorldRisk`, `EvidenceValidityEvent`, and `epoch_scope_unresolved`:
  **`absent/unallocated`**.

Calling this `bridge_missing` would falsely imply that an epoch producer
exists.

### Canonical currentness owners — reuse, never parallel ownership

`core/contracts/rule_evolution.py` content-binds rule logic, distinguishes
semantic change from identifier-only remapping, preserves original-logic
replay and emits revalidation state. `runtime/quality/rule_replay_engine.py`
recomputes rule outputs. `runtime/quality/case_lifecycle.py` projects
`review_required`, `revalidation_required`, `superseded`, and `withdrawn`
without erasing the historical case.

The semantic owner census also found the paths that a literal-name search would
miss:

- `scientist/validation/decision_validity.py` is the canonical, production-
  orchestrated decision-currentness owner. It persists content-addressed
  evaluations, dependency events, transition history and per-lineage heads;
  decision-packet construction registers it and runtime exposes publish/query
  operations. Its currentness capability is **`implemented`**.
- `scientist/evidence/claims/lifecycle.py` and `claims/audit.py` provide the
  claim-level append-only ledger sidecar and CAS persistence. Initial ledger
  construction is wired into decision-packet enrichment. The later
  governance-to-claim `lifecycle_bridge.py` is a working isolated component
  with persisted output and tests but no production caller, so that bridge is
  **`implemented_but_not_orchestrated`**.
- `core/contracts/rule_evolution.py`, `runtime/quality/rule_replay_engine.py`
  and `runtime/quality/case_lifecycle.py` content-bind logic, preserve original-
  rule replay and project current revalidation/supersession/withdrawal state.

These owners do not prove N12 complete. They change the repair posture from
build-new to **wire/extend/consolidate existing**. The epoch chronology must
emit a verified dependency perturbation into Decision Validity, which continues
to own packet currentness and lineage heads; affected claim transitions must
flow through Claim Ledger/lifecycle bridge. N12 must not create another
certificate-validity ledger or currentness head.

The epoch-to-currentness source producer remains **`producer_missing`** because
`DecisionDependencyEvent` and its deployed consumer already exist but no epoch
owner emits the content-bound event. The exact symbol `EvidenceValidityEvent`
is absent, but that absence is not permission to add a parallel contract: the
canonical event must be extended only if its present fields cannot carry the
required epoch proof. Automatic derivation-recipe recomputation remains
**`absent/unallocated`** because no admitted chain or appointed owner exists for
that function.

### N13b overlay — `implemented_but_not_orchestrated`; semantic stamp and
production bridge incomplete

`data_forge/domains/catalog/knowledge/overlay.py` keeps immutable baseline
epoch 0 separate from an append-only DuckDB overlay. An admitted row binds its
observation, passport, raw-evidence hash/artifact, L5 tier and numeric
`epoch_id`; admission is atomic and read sessions fail closed on malformed
overlay state. `runtime/quality/acquisition_executor.py` verifies the passport
and owner evidence before admission.

Two decisive limits remain:

1. `AdmissionPassport.epoch_id` is caller-supplied and checked only as a
   positive integer. `CatalogAcquisitionOverlay.admit_epoch` checks uniqueness,
   not whether the value is the epoch derived for the row's scope and owner
   time coordinate. The declared stamp is therefore `institutionally_supplied`
   for N12 purposes. Treating positivity as epoch validity would be P37/P38.
   The chronology-coordinate producer is **`producer_missing`**.
2. A complete source-and-test caller census for `build_admission_passport(` and
   `.admit_epoch(` finds definitions and unit tests but no production caller.
   The passport/overlay component is **`implemented_but_not_orchestrated`**;
   its production admission seam is **`bridge_missing`**.

The Rev-16 rider can share one time semantics only if the passport binds a
scope-native observation coordinate, the resolved semantic-epoch identity,
the complete regime/amendment basis and its rule/version proof. An overlay
admission counter cannot itself become semantic time.

### N13b/N7 re-entry half for GY-GAP6 — producer logic exists,
`artifact_missing`; exact composition `absent/unallocated`

`GenerationCycleController` runs N7 re-entry inside the same
`GenerationCycleRecord`. Its `AcquisitionReceipt` requires equal source and
re-entry cycle indexes, binds the same `DesignProblem`, records world growth
and outcomes, and the cycle reruns grounding/terminal logic before emission.
That admitted-acquisition/same-cycle re-entry producer logic exists, but its
returned receipt is not independently persisted or queryable. Its precise
capability label is therefore **`artifact_missing`**.

The N7 receipt does not name N13b overlay row, passport or raw-evidence
identities. Conversely, N13b row provenance does not name a `DesignProblem`,
generation-cycle content identity, re-entry receipt, or deeper terminal. The
exact per-row movement capability is therefore **`absent/unallocated`**: no
typed contract, appointed owner, producer or consumer exists. The adjacent N7
and N13b components do not justify a stronger missing-chain label.
The composition seam owes the exact chain:

`overlay row -> passport/raw evidence -> DesignProblem -> recursive run ->
same-cycle re-entry -> recomputed deeper terminal`.

### Production recursive-run artifact — one run `artifact_missing`; complete
enumeration `absent/unallocated`

`RecursiveGenerationCycleRun` and
`CompiledRecursiveGenerationCycleRun` bind a run and each leaf to exact
`DesignProblem` content, graph content, cycle content and owner-derived
terminal. The single-run contract and producer logic exist, but the production
front door returns an in-memory value and does not persist it. The precise
capability label is **`artifact_missing`**.

The only production caller is the plain-language control service, which
returns the value directly. No production persistence owner, append-only run
membership, chronology, current-head/resolved-terminal projection, consistency
proof, or deletion/post-hoc-narrowing detector exists. GY-GAP5 is therefore
**`absent/unallocated`**, not `bridge_missing`: a complete enumeration producer
has not been allocated.

### Controlled release transcript — `absent/unallocated`

Both complete walkers returned zero source and test files for the four supplied
release/transcript predicates. Existing frozen artifacts and rule registries
can be inputs, but there is no controlled release-family membership,
chronology, head, verifier-disposition or offline-consistency owner. GY-GAP3 is
**`absent/unallocated`**.

## Capability table

| capability | measured state | smallest missing closure |
| --- | --- | --- |
| Fabric bitemporal facts/query | `implemented` | none for its native valid/transaction-time claim |
| L5 regime and L3 amendment inputs | `implemented` | none as source inputs |
| model-revision epoch chronology | `absent/unallocated` | typed artifact + producer + persistence + bridge + consumers + verification/surface |
| Decision Validity packet currentness/lineage | `implemented` | extend as sole currentness consumer of verified epoch perturbations |
| initial Claim Ledger v2 sidecar | `implemented` | keep claim-history ownership here |
| governance-to-claim lifecycle bridge | `implemented_but_not_orchestrated` | wire existing producer into production lifecycle |
| rule replay and current lifecycle projection | `implemented` | epoch-trigger producer and derivation-recipe recompute owner |
| OpenWorldRisk / epoch resolver | `absent/unallocated` | contracts, owner and real producers, not a shim |
| epoch-specific validity trigger into Decision Validity | `producer_missing` | content-bound producer over canonical `DecisionDependencyEvent` |
| derivation-recipe recomputation | `absent/unallocated` | appoint canonical owner and full chain |
| N13b passport/overlay component | `implemented_but_not_orchestrated` | derived epoch coordinate + production bridge |
| N7 same-cycle re-entry receipt | `artifact_missing` | persist/query exact receipt before composition |
| GY-GAP6 per-row movement | `absent/unallocated` | appoint owner; then contract + producer + persistence + bridge + consumer/test |
| single recursive run/content terminal | `artifact_missing` | non-blocking production persistence |
| GY-GAP5 run enumeration | `absent/unallocated` | append-only membership/chronology owner and projection |
| GY-GAP3 release transcript | `absent/unallocated` | family-native transcript producer, verifier and replay surface |

## Pattern pass

Relevant rows are `P01`, `P02`, `P03`, `P04`, `P05`, `P07`, `P08`, `P09`,
`P10`, `P12`, `P13`, `P14`, `P15`, `P27`, `P28`, `P29`, `P31`, `P32`, `P35`,
`P37`, `P38`, `P40`, and `P41`.

Existing anti-patterns found are the caller-supplied positive `epoch_id` proxy
(P37/P38), real N13b and lifecycle-bridge components with no production caller
(P02), and missing histories which would invite parallel owners (P27/P28).
The first draft also committed P38 at the research-method level by treating
literal-name absence as semantic-owner absence. The review repair followed the
Custody Time Model's complete named-owner map and found Decision Validity and
Claim Ledger; the design now subordinates currentness and claim history to
them. The smallest correct pattern to test in Cycle 3 is one chronology
**semantic** owner over family-native records and coordinates, never one
universal event type/log or a second currentness owner.
The acceptance signal is deletion- and narrowing-resistant offline replay,
derived epoch resolution over the complete source denominator, exact per-root
identity, preserved historical authenticity, and an exact movement receipt.

## Cycle 1 conclusion

The proposed unification is plausible but not yet proved. All four consumers
need authenticated membership, ordered predecessor relations, scoped heads,
content binding and append-only consistency. They do not share event payloads,
time roles, openness or correction vocabulary. Cycle 2 must price known
mechanisms; Cycle 3 must determine whether shared proof/verification algebra
with family-native persistence is truly one owner or merely four ledgers behind
a facade.

## Independent review and Cycle 1 rewrite

Reviewers received the P40 bucket rule before reading: every finding had to be
`NEW_CLASS` or `SAME_CLASS_ONE_LEVEL_DEEPER` and target design, record or
research method.

- `C1-ARCH-01` (blocking, same class deeper, research method) found the literal-
  absence/semantic-owner proxy and the unclassified Decision Validity/Claim
  Ledger owners. The owner-guided census and reuse postures above close it.
- `C1-CENSUS-01` (blocking, same class deeper, record) found inflated and
  mutually incompatible capability labels. N7 and a returned recursive run are
  now `artifact_missing`; exact movement is only `absent/unallocated`; the
  epoch perturbation is `producer_missing` only because the canonical deployed
  `DecisionDependencyEvent` consumer has now been established.
- `C1-ARCH-02` (editorial, new class, design) noted that GY-DEF22's canonical
  owner is the Foundry catalog/discovery boundary. The lane still closes it as
  explicitly routed by the task, but only as an owner-preserving dependency;
  N12 does not absorb its authority.
- `C1-BASIS-01` through `C1-BASIS-05` (blocking, same class deeper, design)
  found missing negative classes for generic boundary sources, promotion
  freeze, event-versus-adjudication authority, never-recorded sibling run
  producers and a novel GY-DEF22 profile. The closure-basis rewrite adds each
  class without enumerating domains or event kinds.
