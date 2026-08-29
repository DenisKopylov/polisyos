# OPS-R5 Amendment — Response Scenario Corpus Gap Record

Audit defect: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:114`.  
Disposition owner: `ops-r5/amendment-ledger.md`, `AUD-F08`.  
Disposition: `accepted_with_variation`.

## Decision Not To Instantiate Thin Scenarios

The stage-1 document supplied family counts, negative names and packet fields, but not real event
sequences, sealed expected transitions, authority evidence or independent oracle records. This
amendment therefore does not manufacture twenty placeholder scenarios and does not represent the
narrative inventory as a delivered corpus.

```yaml
response_packets_instantiated: 0
placeholder_packets_created: 0
sealed_transition_oracles: absent/unallocated
independent_oracle_provenance: not_established
response_evaluator: absent/unallocated
closure_test_AUD-F08: unmet
```

The gap is artifact and verification maturity, not a request for more prose.

## Required Scenario Packet Contract

Each future packet requires:

```text
immutable scenario_id and content hash
initial contract/version and E/X/V/C state
ordered event sequence with event/valid/transaction times
KPI observations, uncertainty, maturity and measurement health
SMDV-1 diagnosis or explicit protective basis
contributing and blocking lanes
waiting-harm and premature-action-loss posture
reversibility vector and blast radius
authority, preauthorization or explicit absence
legal, review and escalation clocks
expected requested transition
expected authorized/denied/modified transition
expected execution state and external receipt posture
forbidden alternative transitions
version, claim and public-validity consequences
restart evidence or reason restart is unavailable
idempotency, duplicate, late and correction behavior
sealed oracle and independent provenance
```

Requested, authorized and executed are separately asserted. A request cannot stand in for an authority
decision, and an authority decision cannot stand in for external execution evidence.

## Required Population And Pairwise Falsifiers

The eventual set must retain the declared `2+3+3+3+3+3+3 = 20` family denominator while proving
operation-level distinctions. At minimum it contains paired cases with an identical observed metric
movement and different outcomes because one of these changes:

- authority or preauthorization;
- information maturity;
- measurement validity;
- waiting harm;
- premature-action loss;
- reversibility or blast radius;
- intervention or claim version;
- legal/safety clock;
- first event versus duplicate;
- alert disappearance versus independent restart probe;
- requested versus actually executed external action.

A threshold-only, owner-string-only or primary-class-only implementation must fail these pairs.

## Operation Coverage

The scenarios must independently exercise all operations discharged in `amendment-ledger.md` §2:

```text
observe
early warning
diagnose
refresh
recompute
recalibrate
adjust implementation
narrow scope
partial reissue
pause
rollback
redesign
terminate
restart or remain contained
```

Shared family names are insufficient. A scenario that tests pause does not automatically test rollback;
a scenario that tests redesign does not automatically test termination.

## Required Fault And Mutation Assertions

At minimum:

1. threshold opens a case but cannot authorize action;
2. measurement invalidity changes refresh/recompute/recalibrate routing;
3. unresolved high waiting harm permits only the declared protective action and freezes learning;
4. unresolved low waiting harm remains investigate/no-expand;
5. absent signer denies a protected transition;
6. a duplicate pause or rollback does not repeat external effect;
7. a late correction creates a reaction/supersession record rather than rewriting history;
8. rollback residue blocks `V4 + X0` without restart evidence;
9. alert disappearance cannot reopen exposure;
10. `V2 + C0` fails absent equivalence;
11. `E4 + X4 + C0` fails for the same unacceptable claim object;
12. causal claim withdrawal does not automatically terminate a policy with an independent legal or
    protective basis;
13. external execution failure leaves requested/authorized state distinct from applied state;
14. provider or worker failure after partial writes is reconciled without duplicating an irreversible
    operation.

## What Would Close The Finding

1. obtain grounded current-state and event-sequence inputs;
2. seal independent transition oracles before implementation tuning;
3. materialize twenty immutable packets and operation-specific assertions;
4. implement an evaluator spanning request, authority, execution, claim reaction and restart consumers;
5. execute duplicate, late, concurrent and partial-failure mutations;
6. publish the result and retain disagreements and false-block cases.

Until then, the stage-1 response corpus is a **future corpus specification**, and the closure test
remains unmet.
