---
title: "Wave 5 consolidation — open questions and next research"
status: candidate
stage: consolidation
base: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
---

# Wave 5 Open Questions And Next Research

## Reading rule

This is a complete, lossless transcription-and-classification of the response lines' explicit
open-question population: **73 unique questions = 15 + 14 + 12 + 13 + 12 + 7**. The INT-R6 root
protocol repeats six of the seven rows in the terminal response table; those repetitions are one
question each, not six additional questions. This file does not appoint a researcher, convert an
unknown into a contract or duplicate a routed obligation. Each ID is used by the routing map.

The complete file-type denominator is six terminal-response `.md` question sections. This exact row
walk was executed from repository root:

```bash
python3 - <<'PY'
import re, subprocess
specs = [
 ('INT-R2','0afc3779e2894f2793cc40150d6923589bd36ee6','policy-engine/docs/research/policy-operations/int-r2/integration-handoff-and-finding-register.md','## 3. Open questions for consolidation','## 4. Amended complete finding register','numbered'),
 ('INT-R3','32cfebd02354b4d70fbf8beaca168aea6f2e72ee','policy-engine/docs/research/policy-operations/int-r3-authority-ui-comprehension-benchmark.md','## 10. Open Questions For Consolidation','## Operational closure addendum','numbered'),
 ('INT-R4','329edb60f77867f914581d380acfccf5882d607d','policy-engine/docs/research/policy-operations/int-r4-performative-effect-update-diagnosis.md','### 10.1 Questions requiring architect/governance disposition','### 10.2 Classified finding summary','numbered'),
 ('OPS-R5','329edb60f77867f914581d380acfccf5882d607d','policy-engine/docs/research/policy-operations/ops-r5-monitoring-diagnosis-and-adaptation.md','### 10.1 Questions','### 10.2 Classified findings and W4-K05 standing','numbered'),
 ('INT-R5','70f2db6d3a4330664c981721a9305f16bffe369b','policy-engine/docs/research/policy-operations/int-r5-decision-authority-validity.md','### 10.1 Owner and architecture questions','### 10.2 Corrected finding classification','numbered'),
 ('INT-R6','eb9b135089d4a54b648973db02f0312b276ea2ea','policy-engine/docs/research/policy-operations/int-r6/06-findings-standing-and-pattern-pass.md','## Open questions and owner states','## What this research does not decide','table'),
]
total=0
for task,sha,path,start,end,kind in specs:
    body=subprocess.check_output(['git','show',f'{sha}:{path}'],text=True)
    section=body.split(start,1)[1].split(end,1)[0]
    ids=re.findall(r'^\d+\.',section,re.M) if kind=='numbered' else re.findall(r'^\| OQ-\d{2} \|',section,re.M)
    total += len(ids); print(task,len(ids),path)
print('UNIQUE_SOURCE_QUESTIONS',total,'FILES',len(specs))
PY
```

Observed counts were `15, 14, 12, 13, 12, 7 = 73`. INT-R6 uses the terminal seven-row table; its
root protocol's six open bullets duplicate table rows OQ-02–OQ-07 and are not a second population.

## INT-R2 — 15 questions

| ID | Open question retained from response line `0afc3779…` | Next-research shape |
| --- | --- | --- |
| R2-Q01 | Should the narrow common envelope live in `pdc`, with per-type adapters in `runtime/quality`, or should the entire candidate remain outside the waist until one producer path is proven? | owner/canonical-artifact adjudication before schema work |
| R2-Q02 | Which existing team/canonical module owns residual shape and the generic non-data admission/re-entry plane? CG5 cannot own it because CG5 is explicitly a router. | institutional/runtime ownership allocation; no owner today |
| R2-Q03 | Which existing vocabularies can represent relation claim strength, estimand binding strength, legal/normative/write operations, capacity stages and assurance levels? External terms are not registered merely by citation. | complete owner/vocabulary crosswalk with unknowns preserved |
| R2-Q04 | Which domain-specific procedures, if any, can authoritatively classify a relation, and what maximum claim language does each permit? A universal threshold remains open. | institutional role and evidence-floor research |
| R2-Q05 | Is social licence represented only as a continuously evidenced legitimacy condition, routed to another task, or excluded from `normative_authorization` unless a formal regime supplies an issuer? | jurisdiction-specific representation and issuer research; no generic substitute |
| R2-Q06 | Who owns direct prerequisite evidence, assessor independence, commitment-stage rules and longitudinal calibration without turning a checklist into authority? | producer/assurance-owner research, not a local default |
| R2-Q07 | What ordering/dependency graph governs relation + writability, mandate + normative authorization, or capacity + decision + audit combinations? | algebraic composition study with mixed-outcome falsifiers |
| R2-Q08 | The later complete row-level measurement and identity of the one data-shaped member must be imported and independently reconciled before any per-row classification claim. | exact denominator/crosswalk study; no ninth type by implication |
| R2-Q09 | Consolidate with INT-R5/GY-PA2/Atlas DS9 semantics; do not create a second competence certificate. | live-chain topology census and missing-bridge identification |
| R2-Q10 | Extend `core/audit` packaging and runtime assurance owners while keeping the independent provider external. | custody-boundary adjudication by function, one plane at a time |
| R2-Q11 | The exact `gap_acquisition_case_union` row remains `institutionally_supplied` until an immutable branch/ref/path is supplied; it is not a binding consumer or authority source. | producer/artifact/bridge/consumer/verification acceptance study |
| R2-Q12 | Acquisition process states must map to the existing Atlas lattice without creating new readiness/publication authority. | total, authority-nonwidening status/reason crosswalk |
| R2-Q13 | The package appoints no signers/providers. A technically complete integration can remain blocked indefinitely if that layer is not established. | institution-specific availability evidence; absence stays typed |
| R2-Q14 | Eight field relations remain unregistered/unimplemented and fail closed. | field-owner and ceiling-algebra research; fail closed meanwhile |
| R2-Q15 | Stable cases, independent oracle ownership and red-proven mutants remain a later implementation prerequisite. | executable benchmark and independent-oracle research |

## INT-R3 — 14 questions

| ID | Open question retained from response line `32cfebd0…` | Next-research shape |
| --- | --- | --- |
| R3-Q01 | Who supplies the action-admissibility policy, role competence and escalation authority without INT-R3 creating a duplicate authority model? | consumer/claim-use topology study |
| R3-Q02 | Which semantic identifiers must survive locale/translation so the same item key remains valid? | identifier/crosswalk study, bounded to purpose |
| R3-Q03 | How does the benchmark bind to server-offered decision modes and distinguish an attempted override from a committed one? | runtime-event and denominator semantics |
| R3-Q04 | Which DS16/DS17/DS18 successor plans consume the red-first predicates before their surface contracts freeze? | surface-input contract study; projections cannot mint comprehension |
| R3-Q05 | Is DS15/GY-N13b quarantine technically enforced, advisory or both; what event proves use? | owner/capability census and action-boundary adjudication |
| R3-Q06 | Who appoints item adjudicators and the governance loss/acceptance owner? No signer exists. | human-institution allocation; no owner today |
| R3-Q07 | What maximum upper confidence bounds are acceptable for each safety cell and population? Stage 1 does not invent them. | preregistered empirical calibration research |
| R3-Q08 | Which operational audit or outcome can validate simulation without converting PolicyOS into the administrator or employer? | external operational-evidence and anti-role research |
| R3-Q09 | Direct evidence is thin; which AT × uncertainty item families require formative co-design before a powered comparison? | stratified study design with accessible timing |
| R3-Q10 | Distillation must decide whether to extend honest diagnostics, Atlas verification artifacts or another existing owner. This package creates no canonical family. | reuse-first owner census and principal allocation |
| R3-Q11 | Which OPS-R15 capstone event supplies a realistic operator decision point and after-hours escalation failure without making INT-R3 depend on unresolved future work? | event identity and custody-path study |
| R3-Q12 | Predefine the result pattern that triggers architect stop rather than allowing a failed run to be cosmetically reframed. | research-feasibility stop-law design |
| R3-Q13 | Which examples belong in operator training and which remain sealed to preserve benchmark validity? | corpus partition/oracle governance study |
| R3-Q14 | What roles, authority levels, tenure bands and operating environments define the first target population? | population/recruitment/ethics/accessibility research |

## INT-R4 — 12 questions

| ID | Open question retained from response line `329edb60…` | Next-research shape |
| --- | --- | --- |
| R4-Q01 | Does O1's “posterior update” mean only discrepancy-driven repair, or also routine predeclared assimilation under `expected_variation`? | principal architecture adjudication; interim rule stays no mutation |
| R4-Q02 | Should SMDV-1 be registered as a new vocabulary, or encoded as a narrow movement-source axis beside S13's destination attribution? | owner-first placement decision after live-owner census |
| R4-Q03 | What exact mapping between SMDV-1 and S13 is loss-tolerable, and which losses must block? | versioned, authority-nonwidening crosswalk |
| R4-Q04 | What evidence constructs observation-process causal ancestry rather than merely declaring a DAG/provenance path? | producer/evidence contract research |
| R4-Q05 | When mixed outcome and observation paths exist, which domains can identify their separate contributions and which must remain unresolved? | multi-label/causal-route validation study |
| R4-Q06 | What domain/consequence-specific unresolved rate is acceptable before a system remains accountability-only? | sealed holdout and risk–coverage research; no inherited number |
| R4-Q07 | Which treatment-version changes may be pooled, under what predeclared theorem or equivalence evidence? | sequential causal-identification research |
| R4-Q08 | Who owns the independent oracle and who is competent to adjudicate high-stakes diagnosis disagreements? | institutional/assurance allocation; no owner today |
| R4-Q09 | Who is the institutional signer for posterior/world updates, reissue, override or withdrawal? | four-purpose institutional authority research; no package self-signature |
| R4-Q10 | Which independent observation channels are mandatory for people with zero production-channel inclusion probability? | measurement/census design with controls |
| R4-Q11 | How are privacy and minimization preserved when observation ancestry and interference require richer linkage? | data-governance and purpose-limitation research |
| R4-Q12 | Which Atlas projections show unresolved/compound diagnosis without presenting it as a settled cause? | DS17/DS18 surface contract study |

## OPS-R5 — 13 questions

| ID | Open question retained from response line `329edb60…` | Next-research shape |
| --- | --- | --- |
| O5-Q01 | Which H2 artifact owns durable transition state, clocks, idempotency, and recovery? | owner/plan decision; no H2 plan or owner exists |
| O5-Q02 | How do E/X/V/C project into the existing Atlas lattice without adding statuses? | total constrained-product crosswalk |
| O5-Q03 | Which continuous-governance actions are reused directly, and where is an authority delta required? | complete action-owner reuse and authority-delta study |
| O5-Q04 | Which action families may be preauthorized, by whom, for which risk class? | institutional authority and expiry research |
| O5-Q05 | Who is metric steward, transition signer, override signer, and after-hours substitute? | purpose-specific appointment evidence |
| O5-Q06 | What domain-specific waiting/premature-action model selects containment intensity? | decision-analysis research; not a default score |
| O5-Q07 | What maturity/delayed-harm horizons apply per KPI? | time-role and jurisdiction study |
| O5-Q08 | How are subgroup/spillover guardrails composed under multiplicity and unknown groups? | causal/interference research |
| O5-Q09 | Which version changes require partial/full reissue, downgrade, or termination? | epoch/cascade and transition-invariant study |
| O5-Q10 | How is external execution evidence verified when late/contradictory? | typed fail-closed intake contract research |
| O5-Q11 | How is permanent O3 quarantine protected from generic reprocessing? | lifecycle/state-machine research |
| O5-Q12 | Which Atlas/public surfaces communicate unresolved cause, protective action and absent signer? | multi-audience projection design |
| O5-Q13 | What OPS-R15 oracle adjudicates correct response and replay? | existing S0-GAP-02 research input plus missing implementation-owner decision |

## INT-R5 — 12 questions

| ID | Open question retained from response line `70f2db6d…` | Next-research shape |
| --- | --- | --- |
| R5-Q01 | Which existing domain formally owns graph/certificate contracts after allocation? | owner-first runtime placement; no package appointment |
| R5-Q02 | Which owner governs jurisdiction/body/recognition/act-effect profiles without a private legal engine? | institutional plus canonical-profile owner study |
| R5-Q03 | Who independently produces decision time and effect classification in the first consumer? | independent producer/event-source allocation |
| R5-Q04 | Which component owns profile applicability resolution? | legal/institutional adjudication contract |
| R5-Q05 | What exact registered status/reason crosswalk replaces candidate IDs? | versioned non-widening projection study |
| R5-Q06 | Which component evaluates the INT-R5 ∩ PAO-R4 ∩ DS20 conjunction? | live consumer/bridge topology and negative E2E design |
| R5-Q07 | Which protected effect is first: acquisition, DS14 or another operation? | bounded pilot selection after owner availability |
| R5-Q08 | Which pilot institutions supply appointment, meeting and conflict facts? | external institution research; no presumed availability |
| R5-Q09 | Who adjudicates disputed forum, recusal, emergency and cure effect? | four-purpose jurisdiction-specific institutional research |
| R5-Q10 | What transaction/valuation owner supplies amount authority? | rule-versioned amount-authority research |
| R5-Q11 | How are mass root invalidations joined to the custody cascade? | GY-N12 epoch/cascade integration study |
| R5-Q12 | Will full survey bytes be admitted to repository custody, or will the manifest residual remain? | durable source-custody decision |

## INT-R6 — 7 unique questions

| ID | Open question retained from response line `eb9b1350…` | Next-research shape |
| --- | --- | --- |
| R6-Q01 | What is the complete implementation baseline beyond the bounded catalogue path/blob observations? | complete tree/file denominator across message composition, producers, consumers and source-content bridge |
| R6-Q02 | Who owns the mapping of proposed relations, results and reasons to registered vocabularies, or records each field unallocated? | canonical semantic-owner census and total crosswalk |
| R6-Q03 | What Ukrainian high-stakes corpus and behavioral/action ground truth can support MAEP? | new corpus/oracle research; no owner today |
| R6-Q04 | What qualifications and appointments make a holder competent for each purpose once real-user evidence exists? | institutional allocation research |
| R6-Q05 | How is co-authentic divergence reconciled per jurisdiction? | jurisdiction-specific legal process research |
| R6-Q06 | Which named RTL jurisdiction pack establishes source-content admission independently of UI locale? | bounded corpus/participant study |
| R6-Q07 | What certificate form, trust roots, key custody, cryptographic architecture and legal effect bind co-authentic source members? | security architecture research with custody boundary |

## Proposed research sequence

The routing map—not this sequence—is the complete 73-question partition. The questions are not
equally ready; apply these priority criteria without duplicating their IDs into a second register:

1. **Owner and live-chain census:** first resolve canonical placement, existing producers/consumers
   and honest `no owner exists` states. Stop rather than inventing a parallel owner.
2. **Canonical mappings and gate predicates:** next construct total, versioned, authority-nonwidening
   mappings and classify every predicate on which an authority gate would turn.
3. **Institutional evidence:** then identify purpose-specific signers, adjudicators, profiles,
   competence and external evidence contracts; absence remains typed.
4. **Independent empirical assurance:** only then commission corpora, operators, holdouts, sealed
   oracles and consequence-bound thresholds.
5. **Surfaces after producers:** surface work consumes admitted artifacts and limitations; it cannot
   mint the missing result.

Acceptance for any new research task is a bounded claim, complete declared denominator, source
replay or explicit non-receipt, falsifier, non-effect, named downstream consumer, and an honest
capability label. No unresolved question here is an implementation contract.
