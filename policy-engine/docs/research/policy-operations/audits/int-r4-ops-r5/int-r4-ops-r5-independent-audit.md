# INT-R4 ‖ OPS-R5 — Independent Audit

Audit stage: `stage_2_independent_audit`  
Audited package head: `c3999897b5be2308513846935f1c4fb68157bcb3`  
Pinned package base: `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`  
Audit branch: `research/int-r4-ops-r5-independent-audit`  
Audit posture: hostile, one pass, research-only  
Package files audited: four of four, read in full before the first audit write

## Step 0 — Branch Containment And Audit Boundary

### Containment result

The GitHub branch ref for `research/int-r4-ops-r5-research` resolved to the full package SHA
`c3999897b5be2308513846935f1c4fb68157bcb3`. The audit branch was created by the GitHub branch API
with that exact SHA as its starting object. A fresh branch read immediately after creation returned the
same SHA before any audit artifact was written.

```yaml
package_head: c3999897b5be2308513846935f1c4fb68157bcb3
audit_branch_initial_head: c3999897b5be2308513846935f1c4fb68157bcb3
containment: pass
basis: exact_ref_identity_before_first_write
```

This is stronger than an ancestor relation at Step 0: the two refs were identical. The audit did not
begin from `dc7bdf79a...` and therefore contains every package line it cites.

### Terminal limitation

Ordinary Git transport from the execution environment could not resolve `github.com`. The observed
stderr was:

```text
fatal: unable to access 'https://github.com/DenisKopylov/polisyos.git/': Could not resolve host: github.com
```

No reconstructed value is substituted for the unavailable terminal transcript. Branch creation,
commits and remote readback use the ordinary GitHub branch/contents APIs. This limitation is recorded,
not graded as a package defect.

### Audit evidence boundary

The audit independently read:

1. `int-r4-performative-effect-update-diagnosis.md`, all 604 lines;
2. `ops-r5-monitoring-diagnosis-and-adaptation.md`, all 502 lines;
3. `int-r4/evidence-register.md`, all 111 lines;
4. `ops-r5/evidence-register.md`, all 117 lines;
5. pipeline §2 and §3.2;
6. the INT-R4 and OPS-R5 backlog rows, including absorbed OPS-R7 and OPS-R6;
7. GY Phase 6 O1/O2/O3 riders;
8. the S13 source contract and canonical fixtures;
9. the N8 typed-value carriers, DDM event contracts, monitoring bridge, continuous-governance
   primitives and Fabric time-travel substrate;
10. the five supplied external surveys at the ranges relied on below.

The unrun P35 census remains outside the audit denominator exactly as the package records it.

## Verdict

# `GO_WITH_REVISIONS`

The package is not safe to hand to consolidation or architecture unchanged. It contains nine material
research defects. None is an unrepairable structural defect: all can be repaired within a revised
research package by making the absorbed-task arguments explicit, routing the O1 conflict for an
architect ruling, replacing claimed orthogonality with a constrained state product, and delivering
real fixture packets and independent assertions.

The verdict is not `NO_GO` because the package already fails closed at the capability and gate axes,
keeps its candidate vocabulary unregistered, and names the missing implementation and institutional
chains. The material defects therefore threaten the correctness of the research handoff, not a live
capability that the repository is currently exercising.

The verdict is not `GO` because the package currently:

- treats a literal expansion of GY-O1 as a non-contradictory scope clarification;
- does not discharge several load-bearing OPS-R7 and OPS-R6 questions at standalone-package rigor;
- gives a fixed precedence rule more causal-routing authority than its evidence supports;
- calls a constrained coordinate product orthogonal without declaring forbidden combinations; and
- calls two narrative case inventories fixed corpora although no executable packets or independent
  oracle records are delivered.

## Severity Arithmetic

```text
blocking      0
material      9
minor         2
commendation  7
              --
total        18
```

Arithmetic check:

```text
0 + 9 + 2 + 7 = 18
```

Every finding below has exactly one severity. The severity counts sum to the register total.

## Finding Register

| ID | Severity | Finding | Evidence | Consequence | Recommended revision |
|---|---|---|---|---|---|
| `AUD-F01` | `material` | **Absorbed OPS-R7 is covered but not discharged.** Version identity, interference and delayed harm receive real treatment, but stopping/repeated looks, sequential exchangeability/positivity, carryover, and the choice among version-, mixture- and dynamic-regime estimands are not answered at standalone-task rigor. | Backlog INT-R4 row; INT-R4 §§1.5, 3.4, 8.3; supplied graded-response survey §§versioning and unresolved problems. | A later implementation can carry the named fields while still making an invalid sequential causal comparison. “Mandatory field” is not a validity rule. | Add an OPS-R7 closure matrix. For every absorbed question state the estimand, assumptions, admissible design, failure mode, benchmark and unresolved residue. Give stopping/repeated-look control and endogenous version assignment their own substantive sections and fixtures. |
| `AUD-F02` | `material` | **Absorbed OPS-R6 is a strong outline, not a fully discharged adaptation task.** `refresh/recompute/recalibrate`, `adjust/narrow/partial reissue`, `pause/rollback`, and `redesign/terminate` are grouped into four action-family rows without distinct entry, authority, version, claim and exit semantics. | Backlog OPS-R5 row; OPS-R5 §§1.4, 4.4–4.6, 7–8; OPS-R5 coverage ledger. | A conforming implementation can choose the right family but the wrong operation, destroying the precise distinction OPS-R6 was meant to research. | Add one transition charter per absorbed operation, or a formal equivalence argument for every grouping. Include legal/authority delta, evidence threshold, reversibility, version effect, claim effect, restart and divergent case for each operation. |
| `AUD-F03` | `material` | **`diagnosis_unresolved` has no empirical or consequence-bounded absorption limit.** The package correctly refuses to infer prevalence from 8/24, but it also supplies no risk–coverage curve, all-unresolved baseline, selective-classification bound, or domain holdout proving that the six substantive classes retain discriminating power outside authored cases. | INT-R4 §§3.5, 4.6, 6.1–6.4; S3 on multi-causality, weak inter-rater reliability and nonidentifiable decomposition. | A classifier that routes almost every realistic case to unresolved can pass all non-compensable safety guards while defeating the vocabulary’s operational purpose. | Require domain-stratified holdouts and report class-specific precision/recall, abstention rate, false-resolution rate, unresolved-reason distribution and risk–coverage curves by consequence class. Add an explicit all-unresolved baseline and a maximum tolerated abstention band only after domain evidence exists. |
| `AUD-F04` | `material` | **The 0–6 admission order mixes evidence-admission order with causal precedence.** Observation-first is defensible as a conservative validity gate, but no cross-domain argument proves the global ordering of intervention/version, context/interference and behavior. The package’s contributor field mitigates but does not itself guarantee that a behavior lane executes when observation change is primary. | INT-R4 §§3.3, 4.4–4.5; S3 epidemiology, SRE and Microsoft SRM; S3’s positive-behavior→filtering→apparent-negative example. | Co-occurring policy-induced behavior can be operationally hidden behind `observation_process_change`, particularly when the behavior both changes the latent outcome and changes inclusion/reporting. | Rename the sequence `admission_gate_order`, not causal precedence. Define primary as a routing disposition. Make every supported contributor open its mandatory lane, with a test showing observation-primary plus behavior-contributor cannot suppress mechanism-design review. Justify or remove the relative order of steps 2–4. |
| `AUD-F05` | `material` | **The `expected_variation` update path is a literal contradiction of written GY-O1, not merely a scope clarification.** GY-O1 says only `prediction_error` may update the effect posterior. INT-R4 permits a separately predeclared routine likelihood/calibration update under `expected_variation` and then says the rider is not contradicted. | GY O1 performativity rider; INT-R4 §§4.3, 4.8, 5.1, 10.1; INT evidence register §4. | `predeclared` can become the escape hatch the rider closes: policy-produced but model-compatible observations can repeatedly shrink uncertainty or move a posterior without ever entering `prediction_error`. | Route an explicit first-order contradiction for architect disposition. Until amended, forbid `expected_variation` from changing the causal effect posterior. Any allowed routine path must whitelist the update target, use a sealed pre-deployment schedule, pass the same ancestry/version/interference gates, prohibit adaptive schedule changes, cap cumulative confidence gain and have a fixture where compatible self-produced data tries to ratchet confidence. |
| `AUD-F06` | `material` | **E/X/V/C are useful factors but not operationally orthogonal.** Reachable combinations are constrained: a material `V2 patched_or_reissued` normally invalidates `C0 confirmatory_intact` absent explicit equivalence; `E4 confirmed_unacceptable` plus `X4 terminated` cannot coexist with an intact positive claim; restart and rollback impose further cross-axis constraints. | OPS-R5 §§4.3–4.5, 7.2; supplied graded-response survey §§305–399. | Treating the Cartesian product as unconstrained permits semantically impossible states and ambiguous transition ownership. | Replace “orthogonal” with “factored but constrained.” Deliver a legal-state matrix or invariants over the product, including forbidden tuples, required co-transitions, partial order per axis and the authority required to cross each constraint. Add pairwise and three-way mutation fixtures. |
| `AUD-F07` | `material` | **The 24-case “fixed corpus” is not an artifact-level fixture corpus.** Only class counts, family descriptions, packet fields and acceptance measures are present. No 24 concrete packets, sealed expected records, independent oracle or per-case falsifier is delivered. The five O3 outputs are asserted as one conjunction rather than five independently mutated consumer properties. | INT-R4 §§6.1–6.4, 8.1; package delta contains no fixture files. | Passing is currently definitional: an implementation author can instantiate only the taught examples or hard-code the conjunction. The audit cannot establish that each required O3 output can fail independently. | Deliver 24 immutable packet IDs with inputs and sealed oracle records. Split O3 into five mutations: wrong diagnosis, wrong ancestry, posterior escape, world-writer escape, and reprocessable quarantine. Add an adjacent valid independent-evidence case and remove-property/retain-marker variants for each consumer. |
| `AUD-F08` | `material` | **The 20-scenario response “corpus” has the same non-falsifiability defect.** Family counts, negatives and fault-injection names are not twenty enumerated scenario packets with current state, event sequence, expected transition, forbidden transition and oracle. | OPS-R5 §§6.1–6.3, 8.1; package delta contains no response fixtures. | The proposal cannot demonstrate that all A0–A6 operations, duplicate/late paths, owner absence, restart and partial execution are distinguishable rather than narrated. | Deliver twenty named packets and an evaluator contract. At minimum include paired cases with identical threshold movement but different authority, maturity, waiting harm, reversibility or version consequence so a proxy implementation fails. |
| `AUD-F09` | `material` | **The per-finding capability columns misuse `contract_only` for prose research sketches.** W4-K06 says prose/research contracts do not create `contract_only`; that label presupposes a real admitted type. Both registers nevertheless use phrases such as “`contract_only` as a research sketch/proposal/rule.” | W4-K06; INT rows F07/F15; OPS rows F04/F05/F07/F09–F12/F15. | The top-level `absent/unallocated` is correct, but the row-level stronger token creates an internally inconsistent capability ledger and can be cited later as maturity evidence. | Replace those row values with `absent/unallocated` or `not_established` as the applicable registered label. Put “research contract sketch” in a separate non-capability column. |
| `AUD-F10` | `minor` | **The “one vocabulary or fork” requirement is stronger than the evidence establishes.** The evidence requires consistent source-diagnosis semantics and explicit routing; it does not prove that every task must share one representation, one owner or one terminal set. The package itself correctly retains a separate S13 destination taxonomy. | INT-R4 §§1.1, 4.7; OPS-R5 §§1.1, 9.2; S3 cross-domain vocabularies. | A future domain-specific refinement could be rejected as a “fork” even when it preserves a verified total mapping and does not change update eligibility. | Narrow the invariant to one governed source-diagnosis contract or a versioned, total, tested crosswalk. Allow purpose-specific destination/action taxonomies that cannot widen authority. |
| `AUD-F11` | `minor` | **The evidence registers are not mere lists, but they are under-linked disposition ledgers.** Each row carries six useful fields—ID, finding, research standing, capability standing, gate consequence and route—but no direct evidence IDs, evidence kind, transfer classification or row-specific falsifier. | Both evidence registers §5. | Reviewers must reconstruct support from the top-level prose and broad source ledgers; corrections are expensive and transfer errors are easy to miss. | Add compact `evidence_refs`, `kind/transfer`, and `falsifier_or_resolution` columns, or give every finding a stable backlink into the claim–evidence ledger. |
| `AUD-F12` | `commendation` | **The package correctly overturns the supplied “only truly greenfield” orientation.** It distinguishes an existing S13 attribution/accountability type from the missing evidence-derived joint movement diagnosis. | S13 `DivergenceRecord`, its validators and canonical fixtures; INT-R4 §2.2. | Prevents duplicate taxonomy/platform work and corrects an architect-level baseline error. | Preserve the narrower claim and its exact producer-versus-validator distinction. |
| `AUD-F13` | `commendation` | **The P35 limitation is handled correctly and downstream reasoning does not require the declined repository-wide zero.** Absence is bounded to the required admitted chain and inspected canonical owners. | Both measurement-boundary sections and registers; W4-K01. | Avoids converting indexed search into a denominator while still permitting positive reuse findings and bounded gap analysis. | Preserve `not_established`; a later executing party may add a complete walk without rewriting this audit. |
| `AUD-F14` | `commendation` | **The missing terminal receipt is not fabricated.** The package distinguishes connector-based remote evidence from unavailable CLI output. | Delivery/non-effect record and hand-back. | Preserves evidentiary provenance under tooling failure. | Preserve verbatim stderr and do not reconstruct terminal values. |
| `AUD-F15` | `commendation` | **OPS-F06 uses the rare `refuted` standing correctly.** A universal linear adaptation ladder is contradicted by domains that govern different objects—statistical error, exposure, operating envelope, blast radius and legal duration. | OPS register F06; supplied graded-response survey §§1–3 and §303 onward. | Prevents a false universal sequence from becoming architecture. | Preserve the negative while revising the substitute coordinates as required by AUD-F06. |
| `AUD-F16` | `commendation` | **Both `blocked` findings are correctly assigned and name what can unblock them.** The missing institutional signer is external to research; appointment/preauthorization evidence is the resolution. | INT-F17 and OPS-F14. | Keeps research from manufacturing institutional competence. | Preserve the blocker; later packages must name the actual institution/role for a concrete domain. |
| `AUD-F17` | `commendation` | **The reuse-first repository baseline is precise.** N8 supplies non-scalar value carriers; DDM supplies calibrated signals but not cause; monitoring and continuous governance supply bounded contracts; Fabric supplies append-only storage but not admission; S13 supplies destination attribution but not the joint producer. | Repository source anchors in both §2 baselines. | Avoids a parallel post-deployment platform and assigns missing bridges rather than relabelling fragments as completion. | Preserve owner distinctions and the `absent/unallocated` end-to-end standing. |
| `AUD-F18` | `commendation` | **The package separates protective action from causal learning and source diagnosis from destination accountability.** Unresolved cause may justify preauthorized containment while posterior/world learning remains frozen; SMDV-1 precedes rather than replaces S13. | INT-R4 §§3.3, 4.7–4.8; OPS-R5 §§3.3–4.5. | This is the package’s strongest substantive contribution and avoids both unsafe waiting and detector-to-cause collapse. | Preserve the asymmetry while repairing precedence and vocabulary overreach. |

## Threat-Model Dispositions

### T1 — Thinnest package, widest scope

**Position: material defect established.**

OPS-R7 is not merely cited: versioning, interference and delayed harm receive paragraphs and enter the
artifact sketches. It is still not discharged at standalone rigor. Questions receiving less than a
paragraph or no task-specific answer are:

- how repeated looks and stopping alter posterior/claim admissibility;
- what sequential-exchangeability, positivity or randomization evidence is required when bad outcomes
  cause the next version;
- how carryover is represented beyond retaining exposure history;
- how to choose among a version-specific, mixture-of-versions or dynamic-regime estimand;
- what falsifies version pooling;
- when an unplanned adaptation resets confirmatory status versus merely narrows it.

OPS-R6 is also more than a citation: the package supplies a state machine, action families, transition
charter and restart rule. It remains under-discharged because several actions receive only a shared
row. The questions receiving less than a paragraph are the independent semantics of:

- refresh versus recompute versus recalibrate;
- implementation adjustment versus scope narrowing versus partial reissue;
- pause versus rollback;
- redesign versus termination;
- VOI and legal-clock precedence when they disagree.

### T2 — `diagnosis_unresolved` is one third of the designed corpus

**Position: the realistic proportion is `not_established`; discriminating power is not demonstrated.**

No defensible percentage can be computed from the package or surveys. The correct audit result is not
an invented estimate. The evidence does show that realistic monitoring problems often contain
simultaneous observation, behavior, version and context mechanisms, and sometimes have no independent
channel that identifies their decomposition. Therefore high unresolved use is plausible. The package
has conceptual discrimination, but no empirical selective-classification performance outside its own
designed population. AUD-F03 is material.

### T3 — Admission precedence carries design weight

**Position: observation-first is argued as a safety gate, not as a universal causal winner.**

The order is conservative in the right direction for learning: invalidate the observation relation
before treating its residual as evidence about the world. The package also avoids the strongest form
of the user’s feared rule: behavior can become primary when an independent outcome channel identifies
its latent path, and inseparable paths become unresolved. What is not supported is the full global
0–6 precedence or the assumption that retained contributors automatically receive operational action.
AUD-F04 is material.

### T4 — GY-O1 rider loosening

**Position: this is a contradiction requiring architect disposition.**

The exact rider quantifies over “any posterior update” and permits only `prediction_error`. The package
adds an `expected_variation` route. The route may be scientifically sensible for a separately designed
Bayesian observation schedule, but that makes it a proposed rider amendment, not a clarification. The
current predeclaration condition is insufficient to stop self-produced compatible data from ratcheting
confidence. AUD-F05 is material; the package’s overall verdict remains revision-capable because the
route is not implemented and the gate is already `NO_GO`.

### T5 — Reliance on the unrun census

**Position: no downstream dependence defect found.**

The package does not need a global zero to conclude that the named joint chain is not admitted. A
hidden uninspected implementation would still need a canonical owner, producer, artifact, consumer and
verification path before it could count as an admitted capability. Statements are repeatedly narrowed
to “inspected path,” “no admitted chain,” or `not_established`. AUD-F13 records the commendation.

### T6 — Four coordinates may be refusal to commit

**Position: useful factorization, false orthogonality claim.**

Fixing three values can constrain the fourth. For example, a material reissue (`V2`) ordinarily forces
claim review/downgrade (`C1`/`C2`) unless equivalence is separately proven. A confirmed unacceptable
state with termination cannot retain an intact positive claim without explaining a different claim
object. The package needs a constrained product, not an unconstrained Cartesian space. AUD-F06 is
material.

### T7 — Can the fixtures fail?

**Position: the proposed properties are falsifiable in principle; the delivered fixtures are not yet
fixtures.**

The prose names wrong behaviors and some mutation strategies. It does not deliver the inputs and
oracle needed to run them. For the O3 fixture, each of the five outputs is logically separable, but the
package supplies one conjunction. An implementation can satisfy four and fail one without a named
single-property test. AUD-F07 and AUD-F08 are material.

### T8 — Two evidence registers at roughly six lines per finding

**Position: six-column ledgers, not lists; traceability still underpowered.**

The rows carry standing, capability, consequence and route, so the sibling “standing token only”
defect is not present. Their cost is reconstruction: evidence class, transfer status and direct
falsifier live elsewhere. AUD-F11 is minor.

### T9 — Rare standings

**Position: both are correctly assigned.**

The universal-ladder proposition is genuinely refuted, not merely unproven. The blocked findings name
the missing appointment and the actor class capable of unblocking it. AUD-F15 and AUD-F16 are
commendations.

## Residual Band

The following are registered and intentionally not chased further in this one-pass audit:

- no appointed adjudicator, revision board, signer or override authority;
- joint `capability_standing: absent/unallocated`;
- the complete census remains `not_established` after transport failure;
- the remote receipt remains connector-based rather than a fabricated terminal transcript;
- domain thresholds, rates and horizons that do not transfer;
- deferred problems that name the evidence or decision required to resolve them.

These residuals do not reduce the nine material revisions above.

## Delivery And Non-Effect

This audit writes only the seven Markdown artifacts under
`policy-engine/docs/research/policy-operations/audits/int-r4-ops-r5/`. It does not edit the package,
source, workflows, `AGENTS.md`, the pattern register, staging or transport files. It does not register
SMDV-1, amend GY-O1, appoint an authority, choose production thresholds, implement a classifier,
execute a policy transition, update a posterior or write a world edge.
