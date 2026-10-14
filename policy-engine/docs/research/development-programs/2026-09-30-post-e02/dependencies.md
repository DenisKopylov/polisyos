# Dependencies, Reuse, and Negative Interactions

[Overview](README.md) · [Scenarios](roadmap.md) · [Structured graph](dependencies.json)

## How to read the graph

A relationship applies to a **specific artifact and increment**; it does not require completing the entire upstream program. If the required input already exists and is fit for purpose, there is no need to launch a new program to create it. Research feedback is not a mutual calendar dependency.

Relationship types:

- **Input:** without the stated result, the selected claim cannot be obtained.
- **Shared asset:** one function may serve two consumers; the resulting savings have not yet been demonstrated.
- **Complement:** two components provide joint value that cannot be assessed correctly in isolation.
- **Feedback:** a new result changes the next research question without transferring authority back.
- **Use condition:** a separate scientific, security, human, or institutional basis applies only to the band that requires it.
- **Competition:** a shared owner, reviewer, memory, quota, or changing contract limits parallel work.
- **Negative interaction:** reuse can propagate an error, expose holdout evidence, or destroy the ability to ask a future question.

## Primary subject-matter relationships

| From → to                            | Type          | Transferred object and exact condition                                                                                                  |
| ------------------------------------ | ------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| E1 → E2                              | Input         | Source/measurement relation, when identification or transport specifically requires it                                                  |
| E2 → E1                              | Feedback      | A discriminating measurement, relation, or source profile for the same target                                                           |
| E1 → M1                              | Input         | Observation frame, units, time, missingness/censoring, and required joint structure                                                     |
| E2 → M1                              | Use condition | Causal interpretation only when an identification/transport premise applies; ordinary prediction need not wait for a causal certificate |
| M1 → P1                              | Input         | The same target and joint evaluation of alternatives; an existing native result may suffice                                             |
| P1 → P2                              | Shared asset  | Stable action identity, resources, and evaluator; completing the full static program is not a prerequisite                              |
| M1 → P2                              | Input         | Transition/signal model and available information set, empirical or explicitly stipulated                                               |
| P3 → P1/P2                           | Input         | Material shared-capacity, calendar, exposure, or response constraints                                                                   |
| P1/P2 → M2                           | Shared asset  | Prior prediction and exact intended/deployed rule; an existing retrospective prediction also qualifies                                  |
| E1/P3 → M2                           | Input         | Observation and delivery evidence that can distinguish causes of a residual                                                             |
| M2 → E2                              | Feedback      | Candidate hypothesis or competing explanations and a useful next experiment                                                             |
| M2/O3 → M1/P1                        | Input         | A separately admitted new world branch that the next cycle actually reads                                                               |
| WP01/WP02 → O3                       | Use condition | An adopted update policy and scientific basis; this does not block all of O1/O2                                                         |
| O1 AND O3 → DS21                     | Input         | Both backend capabilities; O2 is optional                                                                                               |
| N → M1/P1/P2/P3                      | Shared asset  | A target-preserving plan when the numerical workload is genuinely shared                                                                |
| R → E1/E2/N                          | Shared asset  | Better research decisions on unseen tasks; ordinary routing remains the baseline                                                        |
| H → all human consumers              | Feedback      | An observed comprehension failure changes the presentation and workflow, not scientific truth                                           |
| A → E1/E2/M1                         | Input         | Permitted holder output only for an otherwise unavailable input that is actually needed                                                 |
| C → all                              | Shared asset  | Native source/target/assumption versions and exact historical/current-use semantics                                                     |
| Exact E02 output → selected consumer | Input         | Only a specific version-pinned repaired result and its limitations; not a generic green label                                           |

## Complements that cannot be ranked by standalone return

### Measuring and calibrating a shared nuisance

An additional channel may not reduce uncertainty in the target parameter on its own, yet may remove a shared nuisance when combined with another measurement. This is a known finite counterexample to universal greedy selection. Its value arises only when there is a genuine shared nuisance and a compatible noise law. Evaluate the verifiable pair against a strong direct measurement, not any two sources with similar names.

### An action and its evaluation

Good objective vectors without a preserved executable action do not support repeatable selection. A preserved action without a suitable evaluation is also insufficient. The native ParetoRegistry already contains a substantial part of this pair; fund a new bridge only for a specific missing relation.

### The observation process and diagnosis

A new cause classifier may not help until the meaning of a timestamp, a disappeared case, or a registration change is understood. A shared source/process profile may supply much of M2's value. The attribution basis and held-out validation nevertheless remain separate from the mechanics of the log.

### Joint constraints and adaptive continuation

An action that is admissible today may eliminate every admissible continuation. For P2, action identity, available history, and viability are checked together. This does not require static D1 to purchase a general controller in advance.

## Where synergy is established and where it remains assumed

Confirmed source-level relationships include: packet → ClaimLedger owner; publisher → current-owner export and public replay; policy runtime → predictive VOI report → packet; Scientist controller → ParetoRegistry; Calibrator → measurement adapter; transport node → catalog registry. These justify reuse of existing code, but do not establish measured financial savings for a new portfolio.

Synergy for a new increment is earned only after a named shared output and two **valid** consumers with the same meaning are identified. Two future boxes in a diagram establish a hypothesis. When the source family, information regime, lawful use, or scientific target changes, some setup and nearly all validation may need to be repeated.

## Register of unique costs in the first portfolio

These are accounting rules and preliminary work nodes, not an implementation estimate or a new task register.

| Work node                                       | Result                                                                                                                       | Where to count it                                                                                                                          | What to exclude                                                 |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| W00 Completed source/owner reconciliation       | This proposal, source census, and named code boundaries                                                                      | Research already completed; future budgets do not repeat it                                                                                | Another generic corpus audit                                    |
| W01 Exact reading of the selected repaired path | D1 output/consumer and actual residual after E02                                                                             | One bounded discovery node for the selected slice                                                                                          | A separate “preparation” charge in every program                |
| W02 D1 model and exact reference                | All eight sets, constraints, objectives, and value semantics are already specified and analytically checked in this research | No need to redevelop this reference; account separately for future production harness, native reload, and consumer checks only if required | Re-deriving the budget or a general P10 foundation budget       |
| W03 Proven-absent native change                 | A specific action/evaluation/consumer function                                                                               | Only if W01 finds a useful residual                                                                                                        | A new registry, simulator, or already-working carriers          |
| W04 End-to-end D1 check                         | Reload, consumer-removal, material/harmless controls                                                                         | Verification for the selected package                                                                                                      | Charging the same tests again under assurance                   |
| W05 D2 source qualification                     | Exact bounded source, definition, IDs, units/time/rights                                                                     | E1/D2, if inputs are available and the task is selected                                                                                    | A full D0–D5 rebuild or a fictitious live-positive case         |
| W06 D2 source oracle                            | Independent manual source-level calculation                                                                                  | A separate subject-matter check for E1                                                                                                     | Treating the D1 enumerator as the same scientific gold standard |
| W07 Shared artifact/readback                    | Only a missing shared contract or reader                                                                                     | One owner, several specific consumers                                                                                                      | A second CAS, ledger, packet, or universal schema               |
| W08 Full cost trace                             | Actual D/A/B/I/V, compute, waiting, rejected work, and review                                                                | One instrumentation output when compatible                                                                                                 | Double-counting provider billing and the same allocated usage   |
| W09 New migration/compatibility work            | Only affected old/new readers and preserved history                                                                          | I/V for a specific semantic change                                                                                                         | The entire tree of earlier cleanup plans                        |
| W10 Independent O/FA1 boundary                  | Exact stronger use, if needed                                                                                                | A separate conditional decision/operations tranche                                                                                         | Spreading this cost across all candidate questions              |

The total cost of a selected portfolio could combine unique new nodes, integration/requalification, and valid external costs. Their scope and actual effort have not yet been measured, so no numerical total is provided. Do not sum standalone program estimates and mechanically subtract a percentage for “synergy.”

## Negative interactions

1. **A shared source multiplies errors.** Incorrect identity, units, or measurement relation can simultaneously corrupt calibration, policy choice, and retrospective validation. The radius of affected conclusions must be visible.
2. **Shared memory exposes evaluation data.** Learning, challenges, user feedback, and cached summaries can reveal held-out evidence. Separate processes do not guarantee independence.
3. **Early screening is irreversible.** A lost exception, subgroup, or admissible candidate cannot be recovered downstream by increasing the number of simulation draws.
4. **Compression destroys future questions.** Marginals instead of a joint law, one rollout instead of a rule, an aggregate without a document ID, or a selected winner without alternatives all reduce option value.
5. **Currentness checks can become all-refusal.** Overly broad invalidation removes utility; overly narrow invalidation leaves silent staleness. Use material and unrelated controls.
6. **KPI optimization changes what is observed.** A policy may improve reporting rather than an independent outcome; the former holdout then loses its meaning.
7. **An overly general schema raises the cost of the second case.** Many consumers may need migration to support one new statistical target.
8. **A shared verifier creates a shared blind spot.** Reuse the harness when appropriate, but do not transfer another task's gold standard or guarantee.
9. **More alternatives increase human workload.** A broader frontier may worsen decisions without suitable presentation and explicit values.
10. **A new protected authority creates an operational tail.** Retention, rotation, independent deployment, and revocation do not end after the first receipt.

## What can proceed in parallel

Independent source profiles, the analytical finite reference, separate native modules with an already-selected meaning, and independent checks of frozen inputs can proceed in parallel. It is not necessary to wait for E1 as a whole before studying P2 against an honest stipulated model.

The semantic decision for one shared contract, compatible publication/migration, final connection to a changing consumer, and separate principal decisions must be serialized. Coding agents compete for RAM, I/O, and quota, but often compete even more for competent review and shared-owner integration. Their number does not divide normalized effort or calendar time.

Activate the next branch based on an available discriminating basis and the validation queue. Starting every admissible option at once is not the recommended initial portfolio.
