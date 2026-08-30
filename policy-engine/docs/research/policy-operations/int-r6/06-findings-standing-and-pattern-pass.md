# INT-R6 findings, standing, open questions, and Pattern Pass

## Consolidated finding register

Owner vocabulary in this table is deliberately strict:

- **`existing: <identity>`** cites an owner already named by a governing repository record;
- **`unallocated`** states that no accountable MAEP owner has been appointed or discovered for the
  proposed cross-cutting object;
- a work lane, document type, or generic “specification” route is not presented as an owner.

Stage 3 appoints nobody. The 30-row denominator below is complete and each row has one owner state.

| ID | finding | classification | accountable owner state | evidence-bound next action |
|---|---|---|---|---|
| F-001 | D4-A1 UI posture composes with the source-content architecture | `research_conclusion` | `existing: team-design product owner for D4-A1` | retain D4-A1 unchanged |
| F-002 | the partition requires five dimensions plus explicit parent/dependency edges | `architecture_decision_candidate` | `unallocated` | later architecture ruling may adopt/reject the record model |
| F-003 | UI locale must never select legal authority or source-content status | `protocol_requirement` | `unallocated` for MAEP seam; `existing: @frontend-owners` only for D4 UI mechanics | allocate a cross-boundary owner before implementation |
| F-004 | authoritative legal content needs an authority-text-set relation, not universal `source_language` | `external_evidence_convergence` | `unallocated` | jurisdiction admission/authority owner required later |
| F-005 | English must not be a mandatory legal semantic pivot | `architecture_decision_candidate` | `unallocated` | preserve as architecture constraint pending ratification |
| F-006 | English remains admissible for authored UI and explicitly informative uses | `bounded_architecture_decision_candidate` | `existing: team-design` for UI authorship; `unallocated` for source rendition | keep purpose/provenance limits explicit |
| F-007 | system and jurisdiction concepts need separate namespaces and mappings | `protocol_requirement` | `unallocated` | allocate concept/mapping owner before registry work |
| F-008 | existing statuses/refusals must be reused; MAEP cannot create a second lattice | `scope_constraint` | `unallocated` for cross-owner mapping; existing namespaced owners remain authoritative | complete owner-by-owner vocabulary mapping |
| F-009 | catalogue key parity is structural evidence only | `bounded_repo_fact` | `existing: @frontend-owners` for catalogue mechanics | retain parity; prohibit semantic-standing inference |
| F-010 | catalogue identity share is a triage signal, not translation evidence | `measurement_interpretation` | `unallocated`; no accountable interpretation owner appointed | retain current and historical denominators separately; allocate before operational use |
| F-011 | high-stakes messages require whole propositions or typed message functions | `protocol_requirement` | `unallocated` | allocate message-contract owner before implementation |
| F-012 | action-profile counterexamples can refute a candidate over a declared population | `protocol_requirement` | `unallocated` | implement only with complete population, exclusions, and residual |
| F-013 | `limited`, `may_not_use_for`, `stale`, `superseded`, `withdrawn` need ID-preserving rendering | `red_first_requirement` | `unallocated` for cross-family fixture ownership; existing status owners remain separate | map each fixture to exact namespace/version |
| F-014 | `unknown`, missing, interval, and point remain distinct | `protocol_requirement` | `unallocated` | allocate structured-value/projection owner before implementation |
| F-015 | translation and plain-language adaptation require separate evidence/results | `protocol_requirement` | `unallocated` | allocate distinct transformation/review ownership later |
| F-016 | MACHINE and Lex projections must consume IDs, structured values, anchors, population, residual, provenance | `protocol_requirement` | `unallocated` for cross-consumer contract | bind each existing consumer owner during specification |
| F-017 | certificates are proposition-, purpose-, version-, time-, and tested-population-bounded | `protocol_requirement` | `unallocated` | allocate certificate authority/custody owner before implementation |
| F-018 | co-authentic divergence remains representable and invokes a jurisdiction-specific rule | `protocol_requirement` | `unallocated` | each future admission names its competent external/internal owner |
| F-019 | zero eligible holders are representable as a purpose-scoped refusal | `phased_deployment_proof` | `unallocated`; no holder appointed | reuse an existing refusal owner or leave vocabulary gap explicit |
| F-020 | a later appointment changes institutional records, not the core language model | `phased_deployment_proof` | `unallocated`; Stage 3 cannot appoint | require competent appointment authority in a later stage |
| F-021 | N+1 is data-only only inside the admitted relation/vocabulary/evidence envelope | `phased_deployment_proof` | `unallocated` | route novel semantic categories to governance/schema review |
| F-022 | RTL source-content admission is separate from public RTL UI | `scope_boundary` | `unallocated` for source-content admission | require named jurisdiction evidence; do not claim UI support |
| F-023 | named RTL UI remains `not_supported` until D4-A1 trigger is met | `ratified_repo_fact` | `existing: team-design` with `@frontend-owners` mechanics | no action in INT-R6 |
| F-024 | Ukraine is an architecture fixture, not a present capability claim | `architecture_demonstration` | `unallocated` | later implementation must attach real producer/consumer evidence |
| F-025 | Russian source-content rendition cannot reactivate frozen Russian UI | `scope_boundary` | `existing: team-design` for D4 UI boundary; source-content owner `unallocated` | preserve separate capability records |
| F-026 | current `locale_preference` serialization is a seam; downstream authority effect is not established | `bounded_repo_risk` | `unallocated` for cross-boundary remediation; existing `@frontend-owners`/`@runtime-owners` own their current components | complete producer-to-consumer audit before changing behaviour |
| F-027 | code-search misses do not establish repository-wide absence | `measurement_limitation` | `unallocated`; no accountable evidence-discipline owner appointed | require complete tree/file denominator for future zeros |
| F-028 | direct English→Ukrainian authority-error rates remain unknown | `external_evidence_gap` | `unallocated` | allocate corpus/benchmark owner before empirical claim |
| F-029 | no universal co-authentic reconciliation algorithm is available | `not_applicable_universalisation` | `unallocated` globally; each jurisdiction must name its competent owner | preserve jurisdiction-specific rule/holder |
| F-030 | no finding requires a D4-A1 UI-posture early stop | `research_conclusion` | `unallocated` for next pipeline stage; no capability owner implied | proceed only under standing and audit/amendment evidence |

Owner-state census, complete 30-row denominator:

```text
rows with explicit unallocated state 27
rows with existing-owner identity only 3
rows naming an artifact as owner 0
rows naming a generic work lane as owner 0
total 30
```

The 27-row category includes mixed rows that also name bounded existing component owners; the three
owner-only rows are F-001, F-009, and F-023.

## Decision ledger

| decision | result | boundary |
|---|---|---|
| D-01 — language partition | `refined` | five dimensions; dependent presentation variant |
| D-02 — D4-A1 composition | `composes` | no UI-posture amendment |
| D-03 — mandatory English legal pivot | `rejected` | English still allowed for UI/indexing/informative uses |
| D-04 — co-authentic authority sets | `required_in_target_architecture` | jurisdiction-specific relation/rule |
| D-05 — zero-holder operation | `representable_by_record_model` | no present producer or appointment claimed |
| D-06 — architect early-stop trigger | `not_triggered` | research conclusion only |
| D-07 — positive equivalence proof | `bounded_to_declared_population` | finite passing suite leaves explicit residual |
| D-08 — data-only N+1 | `bounded_by_admitted_envelope` | novel category remains governance/schema gap |

These are research conclusions or architecture candidates, not ratified implementation decisions.

## W4-K05 standing — single package authority

This is the package's only W4-K05 tuple. The scaffold and substantive main report link here and
publish no parallel axes.

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

`research_standing: accepted_narrow_scope` — the architecture, falsifiers, bounded protocol, and
amended repository evidence are accepted as research input while empirical, institutional,
owner-allocation, and implementation gaps remain.

`capability_standing: absent/unallocated` — Markdown creates no admitted typed contract, owner,
producer, consumer, appointment, or verified runtime chain.

`gate_standing: NO_GO` — no implemented verified chain or appointed high-stakes holder exists to open
the first-public-signature gate.

An audit verdict is not a standing value. Stage 3 does not move these axes.

## Open questions and owner states

| ID | gap | owner state | closure evidence |
|---|---|---|---|
| OQ-01 | complete implementation baseline beyond the bounded catalogue path/blob observations | `unallocated` | complete tree/file denominators for message composition, certificate producers/consumers, and source-content bridge |
| OQ-02 | mapping proposed relations/results/reasons to registered vocabularies | `unallocated` | owner-by-owner mapping; no local token invention |
| OQ-03 | Ukrainian high-stakes corpus and behavioural ground truth | `unallocated` | versioned corpus, protocol, denominator, reviewer agreement, action ground truth |
| OQ-04 | role qualification and appointment | `unallocated`; zero appointments | competent appointment record in a later stage |
| OQ-05 | jurisdiction-specific co-authentic reconciliation | `unallocated` globally | per-jurisdiction rule and competent holder/evidence |
| OQ-06 | RTL source-content admission | `unallocated` | named jurisdiction pack; D4-A1 UI remains unchanged |
| OQ-07 | cryptographic certificate form/trust roots/key custody/legal effect | `unallocated` | separate security/trust architecture decision |

## What this research does not decide

- It does not amend D4-A1 or add a UI locale.
- It does not appoint an owner, translator, commission, terminology board, adjudicator, or panel.
- It does not declare a translation legally authentic or universally equivalent.
- It does not register relation, result, status, or refusal tokens.
- It does not choose or implement a database/schema/runtime design.
- It does not create source code, tests, workflows, transport files, or registry edits.
- It does not select one universal interpretation doctrine for co-authentic texts.
- It does not treat English as authority for Ukrainian law.
- It does not infer an unblocked function merely from a modeled purpose-scoped refusal.

## Pattern Pass

### Method

Each candidate was checked for recurrence, stable forces, boundary, counterexamples, vocabulary
interaction, zero-holder representation, and duplicate-pattern risk. The pass routes candidates only;
it does not edit the pattern register or allocate a pattern owner.

| candidate | stable invariant | boundary | result | owner state |
|---|---|---|---|---|
| Language-dimension separation | UI, authority set, rendition, semantic ID, dependent variant remain distinct | does not decide values/UI admissions | `candidate` | `unallocated` |
| Authority Text Set | authority attaches to versioned members under jurisdictional relation | relation/reconciliation jurisdiction-specific | `candidate` | `unallocated` |
| Population-bounded semantic rendition certificate | certificate binds source, target, purpose, IDs, versions, population, exclusions, residual | no legal authenticity/universal proof | `candidate` | `unallocated` |
| Vacant-holder typed refusal | role, appointment, decision separated; zero appointments valid | only governed purpose blocked; other functions separately established | `candidate` | `unallocated` |
| No-upgrade action-profile gate | source action profile cannot strengthen/soften/collapse | finite context suite only refutes/passes bounded population | `candidate` | `unallocated` |
| Translation/adaptation double gate | transformations/results separate | behavioural evidence does not confer authority | `candidate` | `unallocated` |
| Bounded record-based jurisdiction admission | language/script/source/concept/evidence are records | novel semantic category needs governance | `candidate` | `unallocated` |
| Catalogue identity-rate threshold | no stable semantic invariant | diagnostic only | `rejected_as_pattern` | n/a |
| Universal English canonical legal definition | falsified by co-authentic/no-equivalent regimes | D4-A1 UI only | `rejected_as_antipattern` | n/a |
| Locale-specific status lattice | duplicates registered identity | local legal concepts remain separately namespaced | `rejected_as_antipattern` | n/a |

### Pattern interactions and result

```text
Language-dimension separation
  -> Authority Text Set
  -> semantic IDs and mappings
  -> rendition and dependent adaptation transformations
  -> no-upgrade action-profile gate
  -> population-bounded certificate
  -> vacant-holder refusal where adjudication is unavailable
```

Candidates must not be registered as overlapping synonyms. Pattern review may determine that several
are facets of one governed-semantic-rendition pattern.

Pattern Pass result: `completed_and_routed`; no pattern-register edit was made.

## Research quality self-check

| check | amended result |
|---|---|
| D4-A1 treated as binding UI boundary | `pass` |
| designated-source and co-authentic practices distinct | `pass` |
| external practice not represented as repository capability | `pass` |
| Ukraine example typed as architecture fixture | `pass` |
| zero-holder state represented without appointment/capability claim | `pass` |
| N+1 claim bounded by admitted envelope | `pass` |
| three falsifiers remain red-first and parity-compatible | `pass` |
| finite suite not presented as unrestricted proof | `pass` |
| English pivot costs/permitted uses explicit | `pass` |
| RTL boundary/evidence trigger explicit | `pass` |
| 30/30 findings have an existing-owner identity or explicit unallocated state; no artifact owner | `pass` |
| catalogue path/blob denominator is connector-established; leaf/identity figures are `institutionally_supplied` and settle no zero | `pass` |
| historical DS0 census remains historical | `pass` |
| single conforming W4-K05 tuple | `pass` |
| capability/gate standings unchanged | `pass` |
| broader implementation and institutional residuals explicit | `pass` |
