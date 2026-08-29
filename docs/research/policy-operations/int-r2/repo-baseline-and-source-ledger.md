---
title: INT-R2 — Repository Baseline And Source Ledger
status: research_only
research_task: INT-R2
repository_commit: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
authoritative_for:
  - pinned-source coordinates used by the INT-R2 stage-1 argument
  - holder-relative classification of repository and commissioned measurements
may_not_use_for:
  - capability claim
  - owner appointment
  - institutional authority
  - production admission
  - runtime contract
---

# INT-R2 — Repository Baseline And Source Ledger

## 1. Inspection pin and measurement discipline

The repository inspection is pinned to
`dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`. The delivery branch was created from that
commit and is not rebased onto later `main`.

This ledger distinguishes three evidence positions:

- **`recomputed`** — the present researcher read the pinned owner artifact or source and derived the
  proposition from the object that owns it;
- **`institutionally_supplied`** — the commission supplied the proposition, but the executing walk or
  later slice is not present at the pinned tree and therefore was not rerun here;
- **`not_established`** — neither an owned computation nor an independently reconciled second source
  establishes the proposition for this holder.

These are the registered P37 predicate-provenance labels, not a new standing vocabulary. An
`institutionally_supplied` census may preserve a positive count with attribution, but it does not
settle a zero. Set-level facts below name their denominator and the party that executed or supplied
the measurement.

## 2. Governing anchors

| Anchor | Coordinates | What it governs here |
| --- | --- | --- |
| Research pipeline | `policy-engine/docs/reference/policy-operations-research-pipeline.md:18-78,84-92,176-218` | Stage 1 produces evidence only; branch topology; ten-section delivery; P35–P38; ordinary Markdown delivery and branch readback. |
| Wave-2 backlog | `policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md`, sections `Mandatory Repo Baseline Study`, `Research Quality Bar`, `Unified Deliverable Form`, `Operational closure addendum`, `Pattern Pass` | Required baseline fields, quality bar, Group-A state-machine/artifact/fixture addendum, and three-axis standing. |
| W4-K05/W4-K06 | `policy-engine/docs/system-design-decisions/wave4-decision-evidence-ratification.md`, `W4-K05` and `W4-K06` | Separate research, capability and gate axes; substantive prose remains `absent/unallocated`. |
| Identity boundary | `policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:55-112` | PolicyOS owns typed evidence contracts and fail-closed effects; it integrates or observes external institutional acts and does not become the institution that performs them. |
| Failure register | `policy-engine/docs/reference/policy-design-case-failure-patterns.md:1-146,145-240` | Capability-reality labels, authority boundaries, owner-first placement, resolve-bind-verify, complete denominators and gate-predicate classification. |

## 3. Current repository primitives and limits

| Finding | Pinned coordinate | Existing primitive | Exact limit | Classification |
| --- | --- | --- | --- | --- |
| `INT-R2-F01` | `policy-engine/src/polisyos/pdc/_impl/gy_waist.py:218-255` | Coarse promotion-obligation and refusal vocabularies, including `single_obligation_fail`, `joint_obligation_inconsistency`, `proof_timeout`, `scope_insufficient`, and `unknown`. | These identify a failed gate posture; they do not identify the object whose acquisition could close it. | `confirmed` |
| `INT-R2-F02` | `policy-engine/src/polisyos/runtime/http/services/authority_values.py:1-150` | A real discriminated `refused | supplied` value union and refusal codes `no_runtime_composition_rule`, `no_runtime_estimator`, `analysis_not_runtime_resident`, `no_runtime_producer`, `owned_by_another_surface`. | Only `owned_by_another_surface` necessarily names a route. The other codes are honest first-class refusals but may be bare with respect to acquisition. | `confirmed` |
| `INT-R2-F03` | `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py:1-220,220-360` | Typed gaps, eligible strategies, authority levels, mandatory-gate state and planner dispositions. | Planner records are routing/governance inputs and explicitly do not satisfy domain evidence slots. Its grounding bridge still enters through `data_requirement`/`routing_only` shapes. | `confirmed` |
| `INT-R2-F04` | `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/acquisition_authority.py:1-380` | Owner re-resolution for source, licence, L5 trust, transport, local-rights declarations and live receipts. | The registry may add last-mile data edges but cannot mint upstream authority. The model is source/observation-specific, not a generic authority-acquisition protocol. | `confirmed` |
| `INT-R2-F05` | `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/overlay.py:1-90,260-620` | Content-bound acquisition passports, quarantine, immutable baseline epoch, separate overlay and provenance classes. | Admission culminates in observation rows and overlay epochs. Relation, estimand, mandate, decision and audit objects have no corresponding overlay admission path. | `confirmed` |
| `INT-R2-F06` | `policy-engine/tools/quality/validation/layer3_gy_n13b_reentry.py:1-210` | Re-entry recomputes an actual before/after availability delta and distinguishes closure from two `deeper_terminal_*` dispositions. | Closure is defined by dataset/binding/observation growth. The deeper-terminal vocabulary is useful but its proof predicates are data-carrier and catalog specific. | `accepted_narrow_scope` |
| `INT-R2-F07` | `policy-engine/src/polisyos/runtime/quality/grounding_admission.py:1-360` | CG3 hard obligations include mechanism witness, estimand, admissibility, data trust and ambiguity; an `AcquisitionNeed` can route a blocker. | The certificate does not become authoritative from its own fields and re-resolves owners. No generic non-data producer or institutional signer is appointed. | `confirmed` |
| `INT-R2-F08` | `policy-engine/src/polisyos/runtime/quality/grounding_active_controller.py:1-300` | CG5 reads typed gate outputs, selects `cheap_verify`, `elicit_human`, `acquire_data`, `adversarial_validate` or `abstain`, and routes a result back through gates. | Its module contract says it never closes obligations, injects evidence, writes gate dispositions or marks resolution. It is a control-plane router, not the missing acquisition plane. | `confirmed` |
| `INT-R2-F09` | `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2410-2495` | N13b honestly records no conversion of the 15 residuals and routes three capstone non-data gaps to a future knowledge/grounding acquisition plane. | The route is legitimate as an explicit residual, but no canonical owner/producer/artifact chain for that plane exists. Stage 1 may specify a candidate contract; it may not appoint the owner. | `confirmed` |
| `INT-R2-F10` | `policy-engine/architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json` | A committed census with a 15-row ranked `growth_backlog`, every row carrying `gap_kind: binding_gap`, plus three capstone route-evidence rows. | `binding_gap` states that a binding is absent. It does not establish whether the missing object is a data row, causal relation, estimand, write right, mandate, authorization, capacity proof, decision or audit. | `confirmed` |
| `INT-R2-F11` | `authoritative_for` / `may_not_use_for` uses across runtime projections; acquisition passports; P37 labels in the failure register | Purpose-scoped authority fragments are already present. | No one generic owner computes a checkable ceiling over action, subject, population, jurisdiction, purpose, time, evidence strength and permitted downstream use for all eight requested case types. | `confirmed` |
| `INT-R2-F12` | backlog standing caveat and identity boundary | The repository explicitly distinguishes PolicyOS custody from external institutional acts. | No appointed legal grantor, ethics body, register authority, competent decision-maker pool or independent assurance provider is created by this repository research package. | `confirmed` |

## 4. Worked data-acquisition path

The one end-to-end worked example has this shape:

1. a demanding stage emits a typed requirement gap;
2. the planner selects only strategies eligible for that gap and records a disposition;
3. a source owner or connector supplies a response and journal/CAS provenance;
4. acquisition authority is re-resolved from baseline owners, licence, rights and trust evidence;
5. an admission passport either admits, degrades or quarantines the candidate observations;
6. admitted observations enter a separate epoch overlay without mutating epoch zero;
7. the demanding stage re-enters and recomputes its availability before/after delta;
8. only a real owner-visible growth delta closes the data gap; otherwise a more specific refusal is
   recorded.

That chain is the exemplar to generalise at the level of **discipline** — typed demand, eligible
producer, content-bound proof, admission, bounded authority, owner-gated re-entry and replayable
terminal — not at the level of **storage shape**. Requiring every non-data case to end in an observation
row or overlay epoch would be the adversarial category error.

## 5. Residual measurements and holder standing

| Proposition | Measure and denominator | Executing/supplying party | Holder-relative P37 label | Consequence |
| --- | --- | --- | --- | --- |
| The N13a growth backlog contains 15 residual rows and all 15 say `binding_gap`. | Ranked JSON rows 1–15 in the single committed census artifact; the artifact also declares an expected selection count of 15. | Pinned repository artifact, read by the present researcher through the GitHub connector. | `recomputed` for the declared artifact denominator. | The 15-row denominator is usable; the shared label is not a shape classifier. |
| There are three capstone route-evidence rows and each is `not_a_data_gap`. | The complete route-evidence collection in the same committed census; cross-checked against `GY-engine-subordination.md:2451-2453`. | Pinned repository artifact and plan. | `recomputed`. | These three must not enter the ordinary same-stream data acquisition path. |
| Exactly one of the 15 was later established as data-shaped and 14 remained `shape: not_established`. | Later 15-row re-derivation described in the commission; the later slice is not part of the pinned branch used here. | Commissioning authority / later slice, not this researcher. | `institutionally_supplied`. | Preserve the positive partition with attribution; do not infer a type for any of the 14. |
| Zero of the 15 was structurally classified in that later re-derivation. | Claimed zero over the same 15-row denominator. | Commissioning authority / later slice. | `institutionally_supplied`, therefore the zero is **not settled for this holder** under W4-K01/P35. | Use `not_established`, not a proved `zero_structural`, until the complete later walk is available and rerun. |

The exact three capstone demands are:

- `education`: `method_estimand_binding_mismatch` — candidate `estimand_binding`;
- `first_vertical`: `grounding_relation_or_owner_lever:gy_n4.emergency_tax_relief` — unresolved
  disjunction between `grounding_relation` and `owner_writability`;
- `unseen`: `grounding_relation_or_owner_lever:candidate_fallback_1950390310ca54cb` — the same
  unresolved disjunction.

The two `grounding_relation_or_owner_lever` strings must not become a hybrid ninth discriminator.
They are evidence that classification may yield two ordered cases: establish the relation first, then
establish that the canonical owner can register or write the lever.

## 6. Current capability labels

| Slice | Current label | Missing prerequisite |
| --- | --- | --- |
| Existing observation acquisition and N13b re-entry exemplar | existing bounded implementation, not general authority | It closes only owner-visible data availability under the data passport/overlay model. |
| `GapAcquisitionCase` union | `absent/unallocated` | No admitted canonical contract, appointed owner, producer or consumer chain. |
| Residual shape classifier | `absent/unallocated` | No owner-computed discriminator that can prove data-shaped versus one or more non-data acquisition objects. |
| Generic authority ceiling evaluator | `absent/unallocated` | No complete registered vocabulary or consumer-side evaluator covering all requested dimensions and case types. |
| Institutional producers/signers | `absent/unallocated` | Accountable external actors and commitments are not appointed by repository code or research. |
| Multi-type non-data re-entry | `absent/unallocated` | No bridge from admitted non-data artifacts back to each demanding canonical gate. |
| Semantic/adversarial fixture pack | `semantic_test_missing` | No test yet proves row inflation cannot close relation, estimand or mandate gaps. |

The aggregate INT-R2 capability standing is therefore `absent/unallocated`. A research contract is an
input to later consolidation and ratification, not a capability chain.

## 7. Commissioned external-practice inputs

The five surveys were supplied to this stage as Markdown. Their line measures below are the complete
Files-parser denominators for the supplied files, not counts inferred from search snippets.

| Source | Denominator | Decision-relevant contribution | Preserved limitation |
| --- | ---: | --- | --- |
| **“Виды незнания: какие пробелы закрываются данными, а какие — нет”** | 625 file lines | Distinguishes sampling/imprecision from target definition, non-identifiability, directness/support and authority; provides reason-triggered re-entry and deepened-refusal analogues. | No universal cross-disciplinary taxonomy or model-free `is_structural_gap()` exists. Structurality is relative to target, evidence regime, model class and assumptions. |
| **“Как приобретаются причинная связь и estimand, когда больше строк данных не решает проблему”** | 434 file lines | Separates relation acquisition from estimand binding; supplies causal-dossier, five-attribute estimand, identification and transportability requirements. | No universally calibrated causal-edge threshold exists; expert causal structures lack a mature prospective calibration record. |
| **“Приобретение полномочия: юридический мандат, нормативная авторизация и право записи”** | 493 file lines | Separates legal competence, normative sanction and substantive write authority; supplies issuer-chain, ceiling and terminal distinctions. | Jurisdiction examples are not universal law; social licence usually lacks a canonical issuer and cannot safely become a permission token. |
| **“Компетентное человеческое решение и независимое заверение”** | 665 file lines | Supplies reconstructability, case-specific competence, relational independence, assurance-level and unavailability-versus-adverse-result distinctions. | Standing and process increase warrant for how a conclusion was made; neither proves the conclusion true. Formal independence safeguards do not prove substantive independence. |
| **“Доказательство реализуемости политики”** | 400 file lines | Treats capacity as evidence about a specific delivery system and next bounded commitment; supplies stage-specific sufficiency, evidence bundle, decay and horizon-terminal semantics. | No mature universal calibrated probability or interval-scale measure of policy deliverability exists. Framework/checklist completion is not direct capacity evidence. |

All five sources are classified `surveyed_external_practice`. They show that mechanisms are possible
and expose their costs and limits. They are not repository capability, registered project vocabulary,
owner appointment or authority.

## 8. External findings classified

| Finding | Proposition retained by INT-R2 | Classification | Non-effect |
| --- | --- | --- | --- |
| `INT-R2-F13` | “More data” is meaningful only after naming the target and proving that the proposed evidence channel can change the blocked predicate. | `confirmed` across the supplied surveys; adopted as the same-stream invariance test. | Does not prove that any particular residual is structural. |
| `INT-R2-F14` | Relation acquisition and estimand binding acquire different objects and confer different ceilings. | `confirmed`; union branches must remain distinct. | Does not claim either is identified or estimated. |
| `INT-R2-F15` | No universal scientifically calibrated rule converts arbitrary evidence streams into an `established` causal relation. | `deferred_open_problem`; preserve evidence classes and scope instead of inventing a scalar threshold. | Does not forbid domain-specific adjudication rules. |
| `INT-R2-F16` | A bound estimand licenses “the question is defined”; identification and estimator alignment are separate proofs. | `confirmed`. | Does not license causal validity or transportability. |
| `INT-R2-F17` | Legal mandate, normative authorization and owner writability are three non-substitutable authority objects. | `confirmed`; retain three branches. | Does not imply that every action requires all three. The demanding gate declares which apply. |
| `INT-R2-F18` | Cryptographic verification proves provenance/integrity of an authority claim, not issuer competence or substantive truth. | `confirmed`; admission requires issuer-chain resolution. | Does not reduce the value of signatures for binding identity/version/time. |
| `INT-R2-F19` | Social licence commonly has no single issuer, canonical grant threshold or expiry. | `accepted_narrow_scope`; represent only when a governing regime defines an admissible producer and proof, otherwise leave `not_established`. | Does not claim legitimacy concerns are irrelevant. |
| `INT-R2-F20` | Competent decision requires standing, role, domain competence, task scope, actual work and a reconstructable record. | `confirmed`. | A licence or signature alone cannot close the case. |
| `INT-R2-F21` | Independence is a relationship over reviewer, subject, funding, appointment, prior work and threats; it is not a permanent person attribute. | `confirmed`; independent audit remains separate from competent decision. | An internal review retains value but cannot silently satisfy an independent-assurance requirement. |
| `INT-R2-F22` | Audit unavailability and an adverse audit conclusion are different terminal meanings. | `confirmed`. | `provider_unavailable` makes no claim about the audited subject. |
| `INT-R2-F23` | Implementation-capacity evidence is stage-, scale-, environment-, dependency- and time-specific; its ceiling is the next bounded commitment supported by direct evidence. | `accepted_narrow_scope`. | A pilot, maturity score or readiness checklist cannot authorise automatic full rollout. |
| `INT-R2-F24` | A genuine capacity terminal requires no credible build/maturation, narrower staged scope or alternative channel within the decision horizon. | `accepted_narrow_scope`; proposed candidate doctrine, not an established universal standard. | A current Red/not-ready rating is not automatically terminal. |
