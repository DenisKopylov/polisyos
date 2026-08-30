# INT-R4 Amendment — Diagnosis Corpus Gap Record

Audit defect: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:113`.  
Disposition owner: `int-r4/amendment-ledger.md`, `AUD-F07`.  
Disposition: `accepted_with_variation`.

## Decision Not To Instantiate Thin Fixtures

The stage-1 document described a 24-case population, but the repository contains no independently
sourced input records, sealed expected records or appointed/available independent oracle from which a
real artifact-level corpus can be constructed in this amendment. This stage therefore does **not**
create 24 named placeholders and does not call the narrative inventory a fixture corpus.

```yaml
diagnosis_packets_instantiated: 0
placeholder_packets_created: 0
sealed_oracle_records: absent/unallocated
independent_oracle_provenance: not_established
executable_consumer_assertions: absent/unallocated
closure_test_AUD-F07: unmet
```

The honest result is a registered acquisition and verification gap. Creating packet names around
invented values would make the corpus look more mature while preserving the exact non-falsifiability
identified by the audit.

## Required Artifact-Level Corpus Contract

A future 24-case corpus exists only when every case has all of the following:

```text
immutable case_id and content hash
source-case provenance and evidence classification
prediction/effect carrier and canonical content identity
estimand and target construct
intervention artifact, rule and exposure-version history
population, subgroup and spillover frames
measurement definition, instrument, schema and pipeline versions
observation, valid, transaction, decision and follow-up times
maturity, censoring, missingness and zero-inclusion posture
implementation and concurrent-policy evidence
context/interference exposure map
behavioral pathways
independent-channel evidence and ancestry tests
sealed expected primary_routing_disposition
sealed contributing_classes and blocking_contributors
sealed mandatory_contributor_lane_obligations
permitted and forbidden consumer operations
oracle/adjudication provenance and disagreement record
one or more independent mutation assertions
```

A content hash binds both input and oracle. Any correction produces a superseding version; it does not
silently mutate the sealed expected record.

## Population Requirements

The eventual set must still close the declared `3+3+3+3+2+2+8 = 24` denominator, but the count is not
enough. It must contain:

- clean `expected_variation` and clean `prediction_error` controls;
- observation-definition, selection, intensity and series-break cases;
- delivery, eligibility and adaptive-version cases;
- behavioral outcome, behavioral observation and mixed-path cases;
- context, interference and contaminated-control cases;
- delayed, censored, no-channel and zero-inclusion cases;
- uniquely diagnosable cases where `diagnosis_unresolved` is a false abstention;
- genuinely nonidentified cases where any substantive primary is a false resolution;
- remove-property/retain-marker variants for every authority-bearing consumer.

Cases used to derive the vocabulary cannot be the sealed holdout used to validate it.

## Five Independent O3 Mutations

The former conjunction is decomposed into separately failing properties. Each mutation must hold the
other four properties correct while violating exactly one.

### O3-M1 — Wrong diagnosis

Input ancestry is policy-caused observation only, but diagnosis is changed from
`observation_process_change` to another terminal. The diagnosis assertion must fail before any
posterior or writer check.

### O3-M2 — False independent ancestry

Diagnosis remains `observation_process_change`, but a sensor sharing the same selection/reporting path
is marked independent. The ancestry property must fail while diagnosis, posterior refusal, writer
refusal and quarantine permanence remain correct.

### O3-M3 — Posterior escape

Diagnosis and ancestry are correct and quarantine is present, but the effect-posterior consumer moves
mean, interval or confidence. The posterior assertion must fail independently.

### O3-M4 — World-writer escape

Diagnosis, ancestry and posterior freeze are correct, but a world-edge write succeeds through another
consumer or supplied `learning_allowed` marker. The writer assertion must fail independently.

### O3-M5 — Reprocess escape

The original operation is refused, but generic quarantine reprocessing later admits the same evidence
for the same confirmation claim. The permanence assertion must fail independently.

## Adjacent Positive Control

The corpus must include a neighboring case with the same policy and observed movement but a genuinely
independent, valid substantive channel. That channel may survive the O3 negative and proceed to the
remaining gates. A hard-coded rule that quarantines every targeted-policy observation must fail this
positive control.

## Consumer Assertions

At minimum, the evaluator separately asserts:

```text
diagnosis_property
observation_ancestry_property
effect_posterior_refusal_property
world_writer_refusal_property
historical_quarantine_permanence_property
mandatory_contributor_lane_property
```

A single Boolean conjunction is not evidence that each property can fail.

## What Would Close The Finding

1. acquire or construct independently grounded case inputs;
2. seal expected records before implementation tuning;
3. record independent oracle provenance and disagreement;
4. deliver 24 immutable packets plus the five O3 mutations and adjacent positive control;
5. deliver an evaluator at the actual diagnosis, posterior, world-writer and quarantine consumers;
6. run the selective-classification evaluation specified in `amendment-ledger.md` §3;
7. publish the results without replacing unknowns with defaults.

Until those steps occur, the word `corpus` in stage 1 denotes a **future corpus specification**, not a
delivered fixture artifact.
