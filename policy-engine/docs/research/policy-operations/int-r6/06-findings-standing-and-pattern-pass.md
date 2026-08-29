# INT-R6 findings, standing, open questions, and Pattern Pass

## Consolidated finding register

| ID | finding | evidence basis | classification | route |
|---|---|---|---|---|
| F-001 | D4-A1's UI posture composes with the universal source-content architecture | ratified D4-A1 boundary plus refined-axis analysis | `research_conclusion` | retain D4-A1 unchanged |
| F-002 | the proposed three-axis partition must be refined to separate authority-text set, rendition, semantic namespace, and presentation variant | counterexamples from co-authentic and adaptation regimes | `architecture_decision_candidate` | architect/specification stage |
| F-003 | UI locale must never select legal authority or source-content status | D4-A1 separation and failure analysis | `protocol_requirement` | runtime/specification |
| F-004 | authoritative legal content requires an authority-text-set relation, not a universal `source_language` field | VCLT/EU/Canada/Switzerland comparative evidence | `external_evidence_convergence` | architect/schema specification |
| F-005 | English must not be a mandatory legal semantic pivot | co-authentic regimes and no-equivalent concept risk | `architecture_decision_candidate` | architect ruling/ratification |
| F-006 | English remains admissible for authored UI and explicitly informative bridge uses | D4-A1 plus purpose-bounded rendition model | `bounded_architecture_decision_candidate` | specification |
| F-007 | system-governance IDs and jurisdiction-concept IDs need separate namespaces with versioned mappings | terminology practice and false-universality analysis | `protocol_requirement` | vocabulary/schema specification |
| F-008 | existing registered statuses/refusals must be reused; MAEP cannot create a second lattice | commission constraint and W4-K05 posture | `scope_constraint` | vocabulary review |
| F-009 | catalogue key parity is necessary structural evidence but cannot contribute semantic standing | repo coordinate and proposition-level falsifiers | `bounded_repo_fact` | test/specification |
| F-010 | catalogue identity share is a triage signal, not translation evidence | multiple explanations for identical leaves | `measurement_interpretation` | baseline/audit design |
| F-011 | high-stakes messages must be whole propositions or typed message functions | English/Ukrainian morphology and scope analysis | `protocol_requirement` | i18n specification |
| F-012 | equivalence is decided by action-profile/counterexample preservation | entailment and no-upgrade analysis | `protocol_requirement` | MAEP implementation specification |
| F-013 | `limited`, `may_not_use_for`, `stale`, `superseded`, and `withdrawn` require ID-preserving rendering | three binding falsifiers | `red_first_requirement` | fixture/test specification |
| F-014 | `unknown`, missing, interval, and point values must remain distinct across rendering and projections | numeric/epistemic fixture analysis | `protocol_requirement` | schema/test specification |
| F-015 | translation and plain-language adaptation require separate evidence and decisions | survey 5 and opposite-direction failure analysis | `protocol_requirement` | content workflow specification |
| F-016 | MACHINE twins and Lex projections must consume semantic IDs, structured values, source anchors, and certificate provenance | strict-consumer analysis | `protocol_requirement` | projection contracts |
| F-017 | equivalence certificates must be proposition-, purpose-, version-, and time-bounded | regulated-practice synthesis and invalidation analysis | `protocol_requirement` | certificate specification |
| F-018 | co-authentic divergence must remain representable and invoke a jurisdiction-specific rule | VCLT/EU/Canada evidence | `protocol_requirement` | jurisdiction admission specification |
| F-019 | a required role may have zero holders; this must return a typed refusal naming the role | phased-deployment constraint | `phased_deployment_proof` | authority/role specification |
| F-020 | appointing a holder later changes records, not the language model/schema | role/appointment/decision separation | `phased_deployment_proof` | implementation specification |
| F-021 | jurisdiction N+1 can be admitted by records when authority modes, sources, scripts, concepts, mappings, roles, and evidence are data | refined record model | `phased_deployment_proof` | admission specification |
| F-022 | RTL source-content rendering can be evidenced separately from public RTL UI | D4-A1 capability boundary and bidi evidence | `scope_boundary` | future jurisdiction admission |
| F-023 | a named RTL UI locale remains `not_supported` until D4-A1's evidence trigger is met | ratified D4-A1 | `ratified_repo_fact` | no action in INT-R6 |
| F-024 | Ukraine works now: Ukrainian source authority can coexist with English or Ukrainian UI and informative English rendition | first-deployment worked example | `architecture_demonstration` | specification fixture |
| F-025 | Russian source-content rendering does not reactivate the frozen Russian UI catalogue | D4-A1 separation | `scope_boundary` | runtime/specification |
| F-026 | current `locale_preference` crossing must be tested as a regression hypothesis and eliminated if it selects unsupported UI/runtime behaviour | D4 evidence snapshot; current baseline not reproduced | `reported_repo_risk` | complete baseline and implementation audit |
| F-027 | repository-wide absence claims are not established by connector/code-search misses | measurement discipline | `measurement_limitation` | complete tracked-tree walk |
| F-028 | direct empirical English-to-Ukrainian authority-error rates remain unknown | survey evidence gap | `external_evidence_gap` | empirical corpus/benchmark |
| F-029 | a universal reconciliation algorithm for co-authentic texts is not available and should not be invented | jurisdictional disagreement | `not_applicable_universalisation` | jurisdiction-specific admission |
| F-030 | no finding requires early hand-back for a D4-A1 UI-posture change | complete architecture analysis | `research_conclusion` | proceed to next pipeline stage |

## Decision ledger

### D-01 — language-axis partition

`refined`

### D-02 — D4-A1 composition

`composes`

### D-03 — mandatory English legal pivot

`rejected`

### D-04 — co-authentic authority sets

`required_in_target_architecture`

### D-05 — zero-holder operation

`supported_by_record_model`

### D-06 — architect early-stop trigger

`not_triggered`

These are INT-R6 research conclusions or architecture candidates as classified above. They are not ratified implementation decisions merely because they appear in a decision-shaped ledger.

## W4-K05 standing

The fields are token-only; the following sentences justify the selected members of the three registered vocabularies.

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

`research_standing: accepted_narrow_scope` — the Stage 1 protocol, falsifiers, and architecture are accepted as bounded research input while the package's declared repository-measurement and institutional gaps remain open.

`capability_standing: absent/unallocated` — this Markdown package creates no admitted typed contract, appointed owner, producer, consumer, or verified runtime chain; research prose is an input rather than a capability.

`gate_standing: NO_GO` — no implemented and verified chain or appointed high-stakes holder exists to open the first-public-signature gate.

## Open questions and routed gaps

### OQ-01 — complete repository baseline

The current tree needs a model-visible complete tracked-tree walk with file denominator, exact catalogue paths and counts, definition-to-render coordinates for the five falsifier terms, runtime locale contract/validator coordinates, message-composition inventory, MACHINE/Lex coordinates, and source-content decoupling evidence. Until closed, INT-R6 makes no set-level absence claim.

**Classification:** `measurement_gap`

**Route:** implementation/specification entry condition.

### OQ-02 — registered vocabulary fit

The proposed relationship modes, rendition statuses, mapping relations, certificate outcomes, and refusal examples must be mapped to existing registered vocabularies. Any non-representable concept is a routed vocabulary gap, not a locally invented token.

**Classification:** `governance_gap`

**Route:** vocabulary owner/architect; no register edit in Stage 1.

### OQ-03 — Ukrainian high-stakes glossary and corpus

The architecture needs a real corpus of English-authored PolicyOS authority messages and Ukrainian legal/source-content examples, with semantic frames, defective variants, and operator-action ground truth. Error frequencies are not inferred from other language pairs.

**Classification:** `evidence_gap`

**Route:** specification and empirical benchmark.

### OQ-04 — role qualification and appointment

MAEP names required decision roles but INT-R6 neither appoints holders nor defines final competence thresholds. Real-user deployment should generate the evidence for those decisions.

**Classification:** `institutional_gap_visible_by_design`

**Route:** post-deployment governance decision.

### OQ-05 — jurisdiction-specific co-authentic reconciliation

Each admitted jurisdiction must supply its own authenticity and divergence rule. A generic “shared meaning” implementation would import Canadian doctrine into systems that do not use it.

**Classification:** `jurisdiction_admission_requirement`

**Route:** per-jurisdiction evidence pack.

### OQ-06 — RTL admission evidence

No named RTL jurisdiction/evidence pack is admitted in this pass. The architecture supplies fields and tests only.

**Classification:** `future_admission_gap`

**Route:** D4-A1/source-content capability admission when triggered.

### OQ-07 — certificate cryptographic form

MAEP identifies the objects that must be digested/signed but does not decide signature algorithms, trust roots, key custody, or legal effect.

**Classification:** `out_of_scope_technical_decision`

**Route:** security and trust architecture.

## What this research does not decide

- It does not amend D4-A1 or add a UI locale.
- It does not appoint a language commission, terminology board, sworn translator, adjudicator, or panel.
- It does not declare a translation legally authentic.
- It does not register new status/refusal vocabulary values.
- It does not choose a database/schema implementation.
- It does not create source code, tests, workflows, transport files, or registry edits.
- It does not select one universal interpretation doctrine for co-authentic texts.
- It does not treat English as authority for Ukrainian law.

## Pattern Pass

### Method

Each candidate was checked for recurrence beyond INT-R6, stable problem/solution forces, a clear boundary, known counterexamples, interaction with existing registered vocabularies, ability to operate before institutional appointments, and risk of duplicating an existing pattern. The pass routes candidates only; it does not edit the pattern register.

| candidate | recurring problem | stable invariant | important boundary | pass result | route |
|---|---|---|---|---|---|
| Axis-separated language context | locale repeatedly leaks into source selection, semantics, and rendering | UI, authority text, rendition, semantic ID, and adaptation remain orthogonal | does not itself decide values or UI admissions | `candidate` | architect/pattern review |
| Authority Text Set | one-source translation model cannot represent co-authentic law | authority attaches to one or more versioned text members under a jurisdictional relation | relation and reconciliation remain jurisdiction-specific | `candidate` | architect/pattern review |
| Purpose-bounded semantic rendition certificate | “translated” is used as an unqualified global assurance | certificate binds source, target, purpose, IDs, evidence, versions, and invalidators | does not confer legal authenticity | `candidate` | architect/pattern review |
| Vacant-holder typed refusal | systems assume institutions exist or silently bypass missing decisions | role, appointment, and decision are separate; holder cardinality zero is valid | only governed purposes are blocked | `candidate` | authority/pattern review |
| No-upgrade action-profile gate | fluent wording broadens permission or weakens prohibition | compare allowed/required/forbidden actions in boundary contexts | cannot replace jurisdictional interpretation of ambiguous authentic texts | `candidate` | evidence/pattern review |
| Translation/adaptation double gate | readability and fidelity collapse into one quality score | transformations and certificates are separate | behavioural evidence does not confer authority | `candidate` | content/pattern review |
| Data-only jurisdiction admission | “universal” schemas add a language column per deployment | languages, scripts, authority modes, concepts, roles, and evidence are records | genuinely new semantic categories still require governance, not silent data insertion | `candidate` | architecture/pattern review |
| Catalogue identity-rate threshold | teams seek one number for translation quality | none: identical strings have heterogeneous causes | rate is diagnostic only | `rejected_as_pattern` | retain as audit metric only |
| Universal English canonical legal definition | convenience suggests one pivot | falsified by co-authentic/no-equivalent regimes | D4-A1 UI only | `rejected_as_antipattern` | record in design risks |
| Locale-specific status lattice | local wording appears easier than mapping concepts | violates registered-vocabulary identity | jurisdiction concepts remain separately namespaced | `rejected_as_antipattern` | enforce vocabulary mapping |

### Pattern interactions

The candidates compose as a chain:

```text
Axis-separated language context
  -> Authority Text Set
  -> semantic IDs and mappings
  -> rendition/adaptation transformations
  -> no-upgrade action-profile gate
  -> purpose-bounded certificate
  -> vacant-holder refusal where adjudication is unavailable
```

They must not be registered as overlapping synonyms. Pattern review should decide whether some are facets of one broader “governed semantic rendition” pattern.

### Pattern Pass result

`completed_and_routed`

No pattern-register edit was made.

## Research quality self-check

| check | result |
|---|---|
| D4-A1 read first and treated as binding UI boundary | `pass` |
| designated-source and co-authentic practices kept distinct | `pass` |
| external practice not represented as repository capability | `pass` |
| Ukraine first deployment demonstrated | `pass` |
| zero-holder operation demonstrated | `pass` |
| N+1 without schema change demonstrated at record-model level | `pass` |
| three mandatory falsifiers specified red-first | `pass` |
| negation, exceptions, temporal scope, numeric uncertainty, adaptation fixtures included | `pass` |
| English pivot costs and permitted uses explicit | `pass` |
| RTL boundary and admission evidence explicit | `pass` |
| every substantive finding classified | `pass` |
| operational closure addendum completed | `pass` |
| Pattern Pass completed and recorded | `pass` |
| current-tree complete-walk baseline independently reproduced | `fail` |
| exact final W4-K05 token conformance independently read back | `requires_repository_validation` |

The two non-pass rows are not converted into confidence prose or silently treated as complete. They remain explicit entry conditions for acceptance or the next stage.
