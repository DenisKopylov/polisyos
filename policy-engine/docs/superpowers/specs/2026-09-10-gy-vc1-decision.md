# GY-VC1 — One admitted vocabulary crosswalk with preserved authority boundaries

Decision date: 2026-09-10. Lane merge base: `992aa493f`.
Implementation owner: `team-architecture`, in `codex/gy-lattice-and-custody`.
Stage: design accepted for execution by the commissioning prompt; source work starts only after
this decision is committed and read back from the attached branch.

## Decision and bounded claim

Build one versioned reference crosswalk and one recomputing checker. Runtime movement diagnosis
has one admitted namespace, `SMDV-1@1`, and one `MovementClass` owner. E/X/V/C are typed coordinates
beside an existing producer's lifecycle value. A vocabulary translation never establishes an
institutional fact, causal diagnosis, admissibility, legal equivalence, or authority to execute.

Crosswalk entries retain their source identity, source owner, source version, semantic purpose,
target owner, information required to survive projection, loss classification, and exact refusal
condition. A tolerable loss means only that an explicitly named non-decisive representation detail
may be omitted. A blocking loss raises a typed refusal; it is not coerced to a nearby status. Unknown
namespace, unknown member, absent mapping, unknown target-owner status, stripped reason namespace,
and source-owner drift are blocking. There is no permissive default member.

The output is `docs/reference/canonical-vocabulary-crosswalk.v1.json`, accompanied by a short
human-readable reference. This is a candidate vocabulary/conservation reference, not an authority
appointment or a replacement Atlas grammar. Its version is local to this new artifact. No existing
governed epoch or authority artifact is reissued from the lane merge base.

## Evidence read and ownership composition

Binding sources below refer to the tracked files at `992aa493f`; a path reference is not a claim that
all prose in the source carries the standing of the named finding.

| Source and finding | What this decision consumes | Owner preserved |
| --- | --- | --- |
| `docs/plans/active/layer3-slices/GY-engine-subordination.md@992aa493f`, GY-VC1 | Task and Done conjunction | Architecture crosswalk only |
| `docs/research/policy-operations/int-r4-performative-effect-update-diagnosis.md@992aa493f`, INT-F07/INT-F08, §§4.3–4.8 | Bounded movement-source diagnosis; precedence and contributors; S13 non-collapse | INT-R4 source diagnosis, then existing S13 destination attribution |
| `docs/research/policy-operations/ops-r5-monitoring-diagnosis-and-adaptation.md@992aa493f`, OPS-F04/FM-OPS-17, §§4.3–4.5 | E/X/V/C coordinates and refusal of cause forks | OPS response semantics; no second physical-cause ontology |
| `docs/research/policy-operations/ops-r5/amendment-state-invariants.md@992aa493f`, AUD-F06/FCT-01–FCT-04 | Product is constrained, not freely orthogonal | GY-CR2 implements state/history predicates |
| `src/polisyos/runtime/quality/adaptation_transition.py@992aa493f` | Delivered request/decision/restart/snapshot contracts and `pending`/`failed_safe` snapshot status | GY-CR1 durable custody; no edit to this closed task |
| `docs/research/policy-operations/int-r2-gap-acquisition-cases.md@992aa493f`, INT-R2 audit AUD-F007 and §§7.1/10 | Proposed acquisition process states and missing vocabulary ownership | Original demanding gate owns closure/admissibility |
| `src/polisyos/fabric/evidence/non_data_acquisition.py@992aa493f` | Delivered `AcquisitionType`, `GapShapeAssessment`, `NonDataReceipt` local process outcomes | GY-AQ1 classifier/verifier/re-entry ports |
| `src/polisyos/fabric/evidence/ceiling_relations.py@992aa493f` and `ceiling_vocabulary.json@992aa493f` | Eight software relations, registered candidate definitions and fail-closed algebra | Fabric compares definitions; institutions supply semantics |
| `docs/research/policy-operations/int-r5/decision-authority-specification.md@992aa493f`, §14; parent INT-R5-F17 | Candidate local results and namespaced/versioned reasons; stale sibling is not alias | Existing family owners and DS4; no legal graph producer created |
| `docs/research/policy-operations/int-r6/05-red-first-fixtures-and-phased-deployment.md@992aa493f`, FX-001–FX-003; parent F-013 | `limited`, `may_not_use_for`, `stale`, `superseded`, `withdrawn` have distinct semantics | Registered system statuses/restrictions precede display strings |
| `src/polisyos/lex/knowledge/multilingual_assurance.py@992aa493f` | Delivered `AssurancePacket`, `CandidateAssuranceResult`, `AssuranceReceipt`, `RTLSourcePack`, `CandidateSourceContent` | GY-ML1 finite candidate comparison, typed-empty holders |
| `src/polisyos/runtime/quality/status_deficits.py@992aa493f` and Atlas DS4 | Source-local statuses survive; reader axes are compositions, not a new universal status union | Existing backend owner → typed DTO → generated client |

The current Atlas owner law does **not** authorize creating a central Python `AtlasStatus` enum.
The checked owner-specific target used by this lane is the existing CR1 snapshot status field.
The checker derives that exact field's Literal members; it does not treat a sampled lifecycle enum
or a list of lifecycle *events* as the global system-status denominator. Other family semantic IDs
remain scoped identities, carried losslessly or refused. Frontend rendering integration remains
DS12's consumer responsibility.

## Declared source vocabularies and extraction boundaries

The checker must independently read the complete named source section/type, then compare its set
with every reference row. No source is defined by a search-result window. A missing section, parse
failure, empty extraction, duplicated member, or unreadable source is ambiguous and fails the gate.

| Vocabulary | Complete declared source boundary | Runtime/reference treatment |
| --- | --- | --- |
| `SMDV-1@1` | INT-R4 §4.3 seven primary-class table rows | Canonical `MovementClass` enum; contributors remain typed separately |
| `ops.epistemic@1` | OPS-R5 §4.3 complete `Epistemic` coordinate | `EpistemicFactor`, codes E0–E4, meanings retained |
| `ops.exposure@1` | Same complete `Exposure` coordinate | `ExposureFactor`, X0–X4 |
| `ops.intervention@1` | Same complete `Intervention` coordinate | `InterventionFactor`, V0–V4 |
| `ops.claim@1` | Same complete `Claim` coordinate | `ClaimFactor`, C0–C3 |
| `fabric.ceiling-dimension@1` | Every `CeilingDimension` member, reconciled against every JSON relation key | Preserve field identity and the corresponding relation/owner |
| `int-r2.process@candidate-1` | INT-R2 §7.1 entire process-state block, including material-trigger terminal | Preserve process state; absent delivered producer path is explicit |
| `fabric.acquisition-process@1` | Every Literal member of `NonDataReceipt.resolution_state` | Preserve delivered process result, never read `reentry_closed` as publication |
| `int-r6.semantic@candidate-1` | FX-001 status ID, FX-002 restriction ID, FX-003 complete source-ID block | Preserve all five distinct identifiers and prohibition/remedy dimensions |
| `int-r5.result@0.1.0-candidate` | §4.8 full local-result union | Preserve candidate result; no claimed pre-action validity becomes authority |
| `int-r5.lifecycle@0.1.0-candidate` | Parent §8.4 full lifecycle block | Opaque family-native process state, explicit current-status projection |
| `int-r5.cure@0.1.0-candidate` | Parent §4.11 complete cure-result block | Preserve legal-effective-time/profile/historical-immutability distinctions |
| `int-r5.reason@0.1.0-candidate` | Every exact qualified reason in the parent INT-R5 document and every `.md` file directly in its `int-r5/` package | Preserve complete namespaced/versioned identity, never alias by slug |

INT-R5 exact reasons across the complete declared document package constitute the finite candidate
source vocabulary for this version, not every future legally relevant reason. This includes the
adversarial-fixture reasons beyond specification §14’s examples. Adding a qualified token anywhere
in that source set requires a crosswalk update; a namespace placeholder is not a registered member. INT-R6 relation
labels described in prose (authentic text, draft, translation, etc.) are **not** final semantic IDs.
Their missing registered owner/term requirement remains explicit; this lane does not invent legal
source statuses from prose. The reference records this boundary instead of silently omitting it.

Source sets are cross-checked by independently implemented section extraction versus the emitted
reference's grouped term sets and runtime enum/Literal introspection where an executable owner
exists. Counts must sum to the reference's own declared row total. The checker lists set differences,
not merely booleans; no unreadable source can become an empty set.

## Mapping semantics and loss policy

1. Movement classes are retained as movement-source identities. `prediction_error` is only eligible
   for a separately governed proposal and grants no posterior write. `diagnosis_unresolved` retains
   the discriminator/next-evidence requirement and freezes learning. A blocking contributor remains
   blocking even with a `prediction_error` primary. S13 destination labels are *not* aliases:
   observation is not necessarily evidence error, version change is not necessarily failure,
   behavioral response is not necessarily adversarial, and context can implicate several components.
2. Coordinate codes retain axis identity and their meaning. Dropping display wording while keeping
   the exact versioned code is tolerable. Dropping claim identity, version, affected population,
   evidence basis, or a required co-transition is blocking. VC1 does not implement CR2's tuple rules.
3. Ceiling dimensions preserve their software relation. The crosswalk cannot make matching unknown
   tokens registered, substitute a scope ceiling for a legal operation, or flatten incomparable
   partial-order nodes to an ordinal. Such loss is blocking.
4. Acquisition states are process facts. `reentry_closed` means the demanding candidate predicate
   reran successfully; it never means approved/publishable. Proposed research states without a
   delivered equivalent remain explicitly producer-missing and refuse an asserted executable alias.
5. INT-R6 keeps the five semantic IDs separate. In particular, stale needs reacquisition/revalidation,
   superseded needs a successor, and withdrawn excludes current use. A common display string may
   not erase those remedy differences. `may_not_use_for` is a restriction, not a soft recommendation.
6. INT-R5 preserves namespace/version and candidate status. Its certificate-stale reason remains a
   semantic sibling of `polisyos.eval_safety.certificate_stale@1.0.0`, not an alias. The conditions and
   issuer scopes differ. Missing-holder/not-established/refused cannot project positive; local
   positive text alone cannot mint an appointed producer or current protected-effect admission.
7. Existing lifecycle status passes through from the owning producer. Only values derived from the
   named target-owner field are accepted. The crosswalk produces a refusal on an impossible mapping;
   it never adds an eighth response action or a new Atlas lifecycle label.

Each row declares tolerable losses and blocking losses explicitly. Projection exercises these rules:
unknown losses fail closed, intersecting a blocking loss refuses, and no requested omission silently
vanishes. Retaining source metadata is necessary for a tolerable coarse presentation.

## The five ceiling-vocabulary debts: explicit rulings

The eight fields and five vocabularies are different denominators. The shipped relation registry
settles where software comparison occurs, not what the domain terms mean.

| Vocabulary from `int-r2-ceiling-vocabulary-owners` | Ruling | Reason, retained limitation and owner supply |
| --- | --- | --- |
| Relation claim strength | Conditional correspondence to `maximum_claim_strength`; Fabric `CeilingVocabulary.strength_order` owns comparison | Both bound maximum support language. This is not equality with source evidence class or numeric confidence. A domain relation owner must provide versioned nodes, order edges, provenance, scope and independently verified justification for each permitted implication. Until supplied, unknown terms fail closed. |
| Capacity stages | Conditional correspondence to `maximum_commitment_stage`; Fabric `CeilingVocabulary.stage_order` plus load owns comparison | Both bound commitment that the observed capacity can support. Order is domain-specific; stage labels are not a universal maturity score, and the existing numeric load check stays separate. A competent capacity evidence owner must supply stage definitions/order, load semantics, scope/time, and independently verified capacity basis. |
| Estimand binding strength | No canonical registered vocabulary or appointed semantic owner established by this lane; `absent/unallocated` for authority-grade terms | An owner must supply versioned estimand identity (population, contrast, outcome, horizon, intercurrent events, regime), a defensible partial order or explicit incomparability, equivalence/transport evidence, provenance, expiry, and negative use cases. It cannot alias generic claim strength: a precise claim can bind the wrong estimand. |
| Legal/normative/write operations | No combined canonical vocabulary or appointed semantic owner; decompose before registration | Existing `CeilingScope.operation`/permitted/prohibited tokens enforce exact candidate identity only. Legal mandate, authorized value choice and state-write capability are distinct planes. Their respective competent owners must supply namespaced operation IDs, resource/subject/scope/time, delegation/mandate/value authority and current verifier evidence, plus explicit cross-plane conjunctions. A single `allowed` would launder one authority into another. |
| Assurance levels | No canonical registered vocabulary or appointed semantic owner established; `absent/unallocated` for authority-grade terms | An independent assurance owner must supply engagement/subject/criteria/period, versioned level definitions and a defensible order (or no order), scope/exclusions, admissible issuer/independence basis, and negative cases. AUP is not assurance; confidence, evidence class and generic claim strength cannot substitute for the engagement meaning. |

This is the explicitly authorized “state precisely what an owner would have to supply” outcome for
the latter three. It does not claim the debt row's full closure. Institutional appointments remain
typed-empty. Closed AQ1 implementation is not modified and not re-labeled incomplete merely because
it deliberately consumes supplied candidate definitions.

## Predicted institutional family reconciliation

The family list in `w5-institutional-authority-slots` predicted spellings before mechanisms existed.
Reconcile concepts against delivered artifacts and behavior before counting names.

| Predicted family member(s) | Delivered owner/vocabulary | Relationship and remaining limitation |
| --- | --- | --- |
| AdaptationTransitionRequest / AdaptationDecisionRecord / RestartEvidenceRecord / KPIControlStateSnapshot | Same names in `runtime/quality/adaptation_transition.py` | Exact delivered contracts; signer/substitute remain None; failed-safe custody does not execute policy |
| GapAcquisitionCase | `GapShapeAssessment`, `AcquisitionType`, `NonDataRequest`, `CandidateObject` in `fabric/evidence/non_data_acquisition.py` | Decomposed equivalent candidate data flow; no invented alias class |
| NonDataAcquisition | `NonDataAcquisitionRuntime` and `NonDataReceipt` | Concept delivered under more precise names; a prefix match is not an exact symbol |
| human_comprehension_established | `ComprehensionResult.human_comprehension_established` | Delivered property returns Literal[False] |
| OperatorComprehension | `ComprehensionCorpus`, `TrialEvent`, `ComprehensionResult`, `InstrumentReceipt` in `runtime/quality/operator_comprehension.py` | Finite synthetic instrument, not evidence of real human comprehension |
| MAEP / MultilingualAuthority / AuthorityEquivalence | `AssurancePacket`, `CandidateAssuranceResult`, `AssuranceReceipt` in Lex multilingual assurance | Bounded candidate frame/action comparison and persisted receipt; it deliberately cannot establish legal equivalence or authentic-text authority |
| CoAuthentic | `RTLSourcePack`, `CandidateSourceContent`, and explicit absent source-legal-authority/adjudication slots | No exact co-authentic reconciliation producer is claimed. RTL source content is not co-authentic authority; the missing institutional relation is preserved, not renamed closed |

**Measurement correction:** two independent whole-set walks at the lane base agree on 6,136 tracked
`.py` paths below `policy-engine/`; restricting to `src/` plus `tests/` yields 5,207, and restricting to
`src/` yields 2,647. The inherited 5,640 count does not describe either of those declared denominators.
A full exact-word source scan, independently checked by `git grep -w -F` at the base, finds 5 of the
12 predicted names. `NonDataAcquisitionRuntime` does not make the exact token `NonDataAcquisition`
present. These are findings about the old instrument, never a capability score. Unreadable members
were checked explicitly and none were found. Deciding census output will be retained with the lane
receipt and the complete sets can be recomputed from the pinned source.

The VC1 plan bullet independently tokenized and regex-enumerated contains 12 unique route IDs while
its narrative says thirteen. Do not fabricate a thirteenth route or rewrite the closed consolidation.
The reference preserves the actual twelve listed routes and records the mismatch for architect
handback to the GY plan/routing-map owner.

## Production callers and deferred surfaces

| Mechanism | Non-test caller in this lane | Deferred boundary |
| --- | --- | --- |
| Canonical movement admission and factor vocabulary | GY-CR2 `src/polisyos/runtime/quality/constrained_response.py` calls `require_canonical_movement` when admitting its movement context and imports the four factor enums | GY-O1/O3 are `not_started` in §8.5 and own later live monitoring/learning integration. GY-AS3 separately owns a real posterior-consumer assertion. Neither future task is implemented by this crosswalk. |
| Loss/refusal crosswalk projection | The canonical vocabulary checker invokes the actual projector over every row and every declared loss; CR2 may consume its scope-preserving projection as its own admission requires | DS12 is the named Atlas rendered consumer: frontend is outside this lane; `surface_out_of_scope` for new dashboard UI. The machine-readable reference and checker are the immediate audit surface. |
| Candidate vocabulary registry anti-fork invariant | `require_canonical_movement` and the checker validate the complete registry at admission | No automatic semantic detector for arbitrary prose or dead unrelated enums is claimed. See boundary below. |
| Ceiling semantic-owner requirements and predicted-family reconciliation | Reference/checker used as architecture admission/review tooling | Institutions supply missing terms/evidence; no missing institution is appointed by code. |

A registry-only proof would be too weak. The checker also checks the actual CR2 accepted movement
field uses the canonical type and executes namespace/member mutations through the real admission
function. Changing the registry or CR2 field to accept another vocabulary must fail. Introduction
means **admission to this commissioned production movement channel**, not a theorem about whether
any arbitrarily named string anywhere in a repository is secretly a cause ontology. An unused
independent enum cannot be inferred to carry movement semantics from spelling alone. Within the
admitted channel, a second namespace is refused regardless of name or how similar its terms are.

## Red-first implementation and verification

Owned source/reference/checker/test paths:

- `src/polisyos/runtime/quality/vocabulary_crosswalk.py`.
- `docs/reference/canonical-vocabulary-crosswalk.v1.json`.
- `docs/reference/canonical-vocabulary-crosswalk.md`.
- `tools/quality/validation/check_canonical_vocabulary_crosswalk.py`.
- `tests/unit/runtime/quality/test_vocabulary_crosswalk.py`.
- `tests/repo_quality/tools/test_canonical_vocabulary_crosswalk.py`.

Root serializes README, package initializers, commits, the five GY standing rows and the completion
journal. No DEBT-REGISTER/LEDGER mutation; no closed task repairs; no guardrail baseline sync.

1. Write focused tests first: missing source term, extra source term, unknown namespace, blocking
   loss, unknown loss, status addition, stripped namespace/version, coarse negative collapse,
   second arbitrarily named movement registry, same-name changed vocabulary, and CR2 field drift.
   Run each named test file and retain the actual missing-mechanism red output.
2. Implement canonical enums and strict scoped projection/admission. Existing owner fields stay
   source-of-truth inputs. Factor enums contain codes, not replacement lifecycle statuses.
3. Emit the reference; implement an independent bounded source-section extractor and compare every
   vocabulary against the artifact and executable owner. Include explicit owner requirements and
   family-reconciliation outcomes, not inferred legal aliases.
4. Execute each declared loss against the actual projector. Each blocking loss must raise its own
   refusal; each allowed display-only loss must retain source identity. Corrupt a reference member
   and remove the anti-fork property while keeping marker strings, proving the checker turns red.
5. Integrate with CR2's real packet intake. Freeze source before root runs deciding targeted gates.
   Use `.venv/bin/python -m ruff` on each named touched Python path; root runs architecture guardrails
   as a standalone command and reports freshness crashes as unrun checks.

| Done conjunct | Binding falsifier | Required acceptance signal |
| --- | --- | --- |
| Total over declared source vocabularies | Add a source member or delete one crosswalk row without changing the other; blank/unreadable extraction | Checker fails with exact source/member difference; independent set reconciliation agrees on denominator |
| No target status added | Add a new target label, or replace target-owner field membership with a hand-authored permissive list | Live owner Literal membership check and projection reject; original owner schema remains unchanged from lane base |
| Blocking loss refuses | Request deletion of blocker, source identity, reason namespace/version, negative remedy distinction, or any row-declared blocking dimension | Actual projector raises, produces no nearest label, and adjacent allowed display loss preserves identity |
| FM-OPS-17 fork unreachable in admitted channel | Introduce second registry entry with arbitrary name, same terms under another namespace, altered same-ID terms, or change CR2 movement type to a sibling vocabulary | Complete registry check and real CR2 admission refuse; property-removal probe turns battery red |
| Ceiling debts adjudicated honestly | Attempt to treat relation field as estimand strength or assurance grade; supply unknown authority operation | Reference names separate owner requirements; no external terms silently registered or promoted |
| Family vocabulary reconciliation | Substitute expected name presence for delivered behavior, or alias RTL source support as co-authentic authority | Reference preserves delivered candidate mechanisms and explicit absent authority, without changing appointment status |

## Pattern pass and residual routing

P04/P05: retain owner-native lifecycle and authority; no coarse positive default. P27/P30: domain-named
owner composes delivered CR1/AQ1/ML1; no slice-prefixed parallel engine. P29/P32/P37/P38: compare live
source sets and run the projection property, not marker presence or an authorial “complete” boolean.
P35/P36: enumerate declared sets, keep path/type denominators, cite specific findings. P13/P39:
reference rows carry only necessary semantics and owner pointers; receipts retain command evidence,
not embedded tracked source copies. P40: a later escaped spelling in the same admitted channel is
one class deeper, not a new countable victory; widen the choke point once or state a bounded residual.

Initial capability gaps: crosswalk `artifact_missing`/`verification_missing`; machine projection
`consumer_missing` until CR2 is wired; new UI `surface_out_of_scope` to DS12; institutional vocabulary
terms and holders `absent/unallocated`. Accepting this design does not change those labels to built.

Route the three remaining semantic-vocabulary owner obligations to architect row
`int-r2-ceiling-vocabulary-owners`; route corrected predicted-family measurement and non-equivalence
to `w5-institutional-authority-slots`; route the 12-versus-13 source-route mismatch to the GY plan and
wave-5 routing-map owner; route GY-O1/O3 import integration to the named GY-AS3 consumer work. The
checker can establish candidate semantic conservation. A claim of domain truth, legal equivalence,
operator comprehension, an institutional appointment, or universal cause exhaustiveness remains
refused because the corresponding independently admitted producer evidence does not exist here.
