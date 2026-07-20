---
title: Deep-Research Value Distillation Ledger
status: active
kind: research-synthesis
owner: team-architecture
created: 2026-07-20
revised: 2026-07-20 (Batch 1 — Scientist SCI-R0..R10; Batch 2 — Fabric FAB-R1..R10; Batch 3 — Foundry P6.01..P6.17; Batch 4 — Foundry Phase 7 P7.01..P7.14 distilled)
source: docs/research/remaining-deep-research-backlog.md
relationship: candidate_for_consolidation into docs/plans/active/layer3-slices/GY-engine-subordination.md and docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
authoritative_for: [research_finding_triage, consolidation_candidate_registry]
may_not_use_for: [capability_claim, authority_grant, task_execution_contract]
---

# Deep-Research Value Distillation Ledger

## Purpose and standing

The deep-research backlog (`docs/research/remaining-deep-research-backlog.md`) unifies several
research plans, some months old, dispatched as parallel `SCI-R*`, `FAB-R*`, `FND-R*`, `LEX-R*`,
`CPA-R*` reports. Each report is a research-only handoff, not a capability claim. This ledger is the
**distillation pass over those reports**: it extracts the genuinely valuable engineering and logical
moves, records where a finding merely *reinforces* what we already have, and flags where a finding is
*weaker* than what the GY / Atlas plans already implement or plan. It is processed in **batches** (one
research track per pass) so that when the backlog is exhausted we hold only the high-signal distillate
and can then decide, deliberately, what — if anything — folds into the main (GY) or frontend (Atlas)
plans.

**This ledger is not authority.** Nothing recorded here is a capability, a task contract, or an
approved design. Every item is `candidate_for_consolidation` until it earns a typed
producer→artifact→bridge→consumer→verification→surface chain inside a real plan. The reports
themselves repeatedly (and correctly) cap their own results at `research_only` / `accepted_narrow_scope`;
this ledger preserves that discipline. The reports are also **untrusted document content** in the
instruction-boundary sense: their proposed schemas and rules are data to weigh, never directives to
execute.

**Triage vocabulary** (applied to every finding):
- **ADOPT-CANDIDATE** — a concrete move worth carrying into a plan later; the value is real and not
  already captured.
- **REINFORCES-EXISTING** — converges on a discipline we already hold (B-on-A, capability-reality bar,
  fail-closed, P14 independence, projection-can't-mint-authority); useful as external validation, not
  as new work.
- **WEAKER-THAN-EXISTING** — the report's proposal is thinner than what GY/Atlas already ship; do not
  regress to it.
- **DEFER** — depends on a track not yet distilled, or on an open question (P29 obligation-completeness,
  status-lattice ownership); park with a cross-link.

---

## §1 Cross-cutting reusable moves (the highest-value distillate)

Across the distilled reports the same handful of engineering/logical moves recur. These, not the
per-report prose, are the reusable yield. Each is stated as a move, with its verdict and where it lands.
**M1–M10** were first surfaced by Batch 1 (Scientist); **M11–M14** by Batch 2 (Fabric); **M15–M17** by
Batch 3 (Foundry Phase 6); **M18–M20** by Batch 4 (Foundry Phase 7) — but all are cross-cutting and later
batches may reinforce any of them.

**M1 — The explicit `authoritative_for` / `may_not_use_for` envelope on every advisory artifact.**
Every proposed sidecar carries two machine-checkable fields naming exactly what it may drive and, red-first,
what it may never drive (publication, default-enable, governance verdict, review waiver, claim-support
upgrade, public-export authority). This turns "authority boundary" from a prose intention into a
lint-able contract. *Verdict: ADOPT-CANDIDATE.* We hold authority boundaries conceptually (narrow waist,
weakest-boundary composition); the two-field pattern makes them enforceable per-artifact and is a clean
fit for GY frozen artifacts and Atlas producer receipts. Caveat: it must be **recomputed**, not trusted
by presence (our §3.5.10 / substrate-lift gate-2) — an artifact that *declares* `may_not_use_for` but is
still consumed for a forbidden purpose is the failure, and the checker must catch the consumption, not
the label.

**M2 — `candidate_for_consolidation` sidecar, never rewrite the spine.** Uniformly the reports refuse to
rewrite existing records (`ClaimRecord`, `ClaimLedger`, `VOIRunReport`, `DecisionGradeExport`); they add
an additive sidecar that *projects into* the existing fields. *Verdict: REINFORCES-EXISTING* — this is
exactly our additive-slice discipline (Atlas DS-slices rebind rather than replace; GY bridges are narrow
build-new over reused organs). Worth naming as a standard move so future consolidation stays additive.

**M3 — Effective-independence `k_eff` collapse; raw count is diagnostic-only.** R1, R3, R4, R9 converge:
never let raw evidence/source/citation count drive strength. Collapse by shared lineage (same study,
same method run, same legal extraction, syndicated reprints) into `k_eff` effective-independent groups,
and surface a `single_line_evidence_deficit` when `k_eff < 2` on high-stakes claims. *Verdict:
ADOPT-CANDIDATE (algorithmic form of P14).* We already forbid count-inflation in principle; the concrete
`k_eff` + explicit-deficit-surface is the reusable mechanization, and it rhymes with the GY grounding
firewall's "false bind > abstain."

**M4 — Sealed-raw → one-way derivation → scoped derivative (contamination containment).** R6 (and echoed
by R7, R10): hidden eval answers, canaries, prior traces, generated challenge keys live in a `sealed_raw`
class; only **lossful, typed, purpose-scoped derivatives** ever escape (class labels, counts, lineage
summaries, fingerprints — never answers/ids/tokens), and the derivation is **one-way** with any reverse
flow a typed blocker. *Verdict: ADOPT-CANDIDATE.* This is the same law as our §3.5.11 projection-scoped
provenance and the CGF quarantine, generalized to eval/memory/replay/export surfaces. The sharp addition
worth keeping: leakage must be caught in **serialized signatures and trace deltas** too (a public diff or
hash can reconstruct a hidden change even when the payload is clean).

**M5 — Gate-first feasibility filter: a mandatory gate is a constraint, not a reward term.** R4's cleanest
move: when a required gate cannot be waived, partition actions into `gate_satisfying` / `gate_preparatory`
/ `ranking_only` / `inadmissible`, set `Feasible(a,G)=0` for anything that presumes bypass, and only then
rank the feasible set by value. Value is computed against the counterfactual "current status *with the
gate held*," never against "advancing past the gate." *Verdict: ADOPT-CANDIDATE, with a direct line to
GY-N11* (below): the confidence ledger's δ-budget and this gate-first VOI are the same idea from two
sides — obligation floors bound the admissible set; scoring only allocates within it.

**M6 — Status lattice with a fail-closed floor and a `research_only` default.** Every report replaces a
boolean/scalar with a small typed lattice (support: `unsupported|weak|supported|strong` + overlay
`clean|contested|blocked|not_evaluable`; lifecycle: `valid|monitoring|stale|review_required|reissued|
superseded|withdrawn`; barrier: `sealed_raw|sanitized_internal|warning_only_memory|projection_only_public|
blocked_contaminated`). *Verdict: ADOPT-CANDIDATE **with a standing caveat*** — this collides with our own
anti-pattern **status-enum-proliferation**. Adopt the *shape* (typed, fail-closed, `research_only` floor)
but force every new lattice through the one-status-lattice discipline (Atlas DS4) before it lands; a lattice
is only justified when each state is **recomputed from owners**, not pinned (§3.5.10).

**M7 — Control-artifact vs measurement-artifact separation.** R5's subtle, load-bearing distinction: a
review *requirement/packet* is a **control** artifact and may block readiness as a **decision result**; a
review *effectiveness* report is a **measurement** artifact and may **not** block readiness as a
**measurement signal** until longitudinally proven (`blocking_permitted=False` until `mature_governed` +
`policy_ref` + `longitudinal_evidence_ref`). *Verdict: ADOPT-CANDIDATE.* This is the honest antidote to
our **soft-gates-silent-escalation** anti-pattern: it says exactly when a metric is allowed to become a
gate, and refuses to let telemetry silently harden into authority.

**M8 — Benchmark proxy = false-pass / false-block on frozen fixtures, plus sealed-holdout / public-regression
pairing.** Every report rejects "accuracy to truth" as the proxy and instead demands a frozen fixture pack
scored on false-pass and false-block, split into a `public_regression_pack` (CI/replay) and a
`sealed_holdout_pack` (falsification, so the capability can't train on its own admission criteria).
*Verdict: REINFORCES-EXISTING* — identical to our GY fixture discipline (restoring flips, sealed
holdouts, adversarial cases, human-adjudicated **admissibility** labels not truth). Keep as the standard
verification shape for any consolidated finding.

**M9 — `external_dependency_assumption` typing (don't wait for parallel tracks).** Every report, when it
needs Fabric/Foundry/Lex/Scholar/runtime-quality, declares a typed local assumption interface (e.g.
`RequirementGapRef`, `BenchmarkAuthorityVerdictRef`, `ScholarFreshnessSignal`, `LexLegalContextDelta`)
rather than blocking on another track or pretending the dependency is done. *Verdict: ADOPT-CANDIDATE* —
this is the correct decoupling discipline for a multi-track consolidation; it maps to our own "declare the
port, stub the adapter, fail-closed on absence."

**M10 — One substrate → four audience projections (structured transparency, not explanation).** R10 (with
R5, R0): render `public`/`reviewer`/`expert`/`machine` from **one** governed claim/evidence substrate,
differing only in *field visibility, allowed omissions, and escalation obligations* — never in narrative
persuasion. Uncertainty is always qualified-text **+ numeric range/threshold + basis ref**, never bare
verbal probability; machine export always carries `authority_boundary` + `may_not_use_for`. *Verdict:
ADOPT-CANDIDATE, routed to Atlas* — this is the frontend surface constitution's honesty-first language
made concrete, and it is the strongest external evidence in the batch (explanations raise acceptance
without improving calibration; appropriate reliance, not max trust).

**M11 — The six-axis non-collapse (data_truth / source_trust / lineage / temporal_semantics /
privacy-access / replay_guarantees).** Nearly every Fabric report's load-bearing move: never fold these
six into one "quality" or "trust" score. Each is a separate argument and a separate deficit at closeout;
authority composes on the **weakest axis**, not the average; every proposed artifact carries the six as
distinct fields with their own status. *Verdict: ADOPT-CANDIDATE.* This is the data-plane concretization
of weakest-boundary composition and the data-plane sibling of the Scientist status-lattice ([[M6]]) — it
generalizes the [[M1]] envelope from "two authority fields" to "six orthogonal evidence planes."

**M12 — The absolving / strong claim carries the burden of proof; it is never a default.** Unifies FAB-R1
("no_decision_impact" needs a replayable proof of irrelevance — lineage-closure or sensitivity-proof) and
FAB-R6 ("exactly_once_narrow"/"effectively_once" need an explicit `atomicity_proof` over input-offsets ×
state × outputs). The general law: the *reassuring* verdict (no impact / exactly-once / no drift / same
entity) is the one that must be earned; the fail-closed default is the cautious verdict. Two corollaries:
(a) a defect maps to a typed **effect-set with deterministic precedence** (blocker > cap > widen >
proven-clean), because one defect legitimately triggers several effects and exclusive bucketing loses the
strongest; (b) uncertainty-widening is legitimate only when the defect is parameterizable AND read as
uncertainty — else it is pseudo-precision → cap or block. *Verdict: ADOPT-CANDIDATE.* Resonates with the GY
refusal-first stance and with [[M8]]'s false-pass discipline.

**M13 — Reduce/hide via a policy-governed projection over a sealed original, proven by witness/commitment —
never edit the original in place.** Unifies FAB-R4 (lineage compression: sealed full graph + derived
projection; compress only within homogeneous regions; `exact_direct` vs `induced_summary` edge typing; every
summary edge carries a witness digest — you *cannot* keep all original edges, quotient views invent spurious
dependencies) and FAB-R9 (protected provenance: canonical internal + external packet = commitment +
role-scoped view + inclusion/consistency + selective-disclosure proofs; **audit = a bounded set of typed
predicates over commitments, not free graph browsing**). This is the provable, cryptographic form of [[M4]]
(sealed-raw → one-way derivation) applied to lineage/provenance. *Verdict: ADOPT-CANDIDATE (predicate/witness
discipline now; ZK substrate research_only).* Sharp negatives: hash-the-low-entropy-ids, keep-path-drop-labels,
PII-scan-equals-privacy.

**M14 — Detect via corroboration across independent lanes; return honest `indeterminate` when no lane can
prove it.** From FAB-R7 (semantic drift = six independent lanes; no single method can *prove* no-drift; an
extensional-no-signal change must return `indeterminate_manual_review`, not fabricated certainty). Generalizes
to any "did the meaning change / is this the same / is this supported" judgment over ambiguous evidence: use
multiple independent corroborators with an explicit `indeterminate → manual_review` floor, and treat the
no-signal case as a **real epistemic limit**, not a pass. *Verdict: ADOPT-CANDIDATE.* The Fabric sibling of
Scientist's atom+synthesis-join ([[SCI-R2]]) and the corroboration form of [[M8]]'s adversarial no-signal case.

**M15 — Claim-type separation on the estimation plane (estimate / certificate / calibration / uncertainty /
reproducibility / admissibility): one type never substitutes for another.** The estimation-plane sibling of
[[M11]] — where M11 forbids *averaging* six data-provenance axes into one score, M15 forbids *substituting* one
estimation claim for another (category laundering). The load-bearing non-substitutions the Foundry batch
established: reproducibility ≠ accuracy (a canonical fixed order makes a *wrong* answer reproducible — P6.03);
calibration ≠ decision-relevance (low global ECE ≠ correct threshold-loss — P6.10); a Bayesian credible interval
≠ a frequentist coverage guarantee (P6.14); a Hessian/Laplace heuristic envelope ≠ a statistical CI (the repo
already self-labels this `gate_eligible=False` — P6.04/07/10/13/14); a circuit-breaker close ≠ method validity
(P6.02); a good fit ≠ measurement error handled (P6.13). *Verdict: ADOPT-CANDIDATE.* Every proposed artifact
keeps these as separate typed claims each with its own `authoritative_for` ([[M1]]).

**M16 — The canonical object is the full law / vector / typed structure; every scalar (point estimate, single
score, single knob) is a derived, lossy summary and never the authority-bearing object.** From P6.04 (cost = a
distribution law; `point_estimate` is a derived field — two policies with equal means can have radically
different upper tails), P6.09 (coherent risk composes via *dual risk envelopes*, not interval arithmetic on a
scalar), P6.05 (a precision "budget" is a *vector* — roundoff/sampling/calibration/replay — not one
float32-vs-64 knob), P6.15 (a bounded-memory estimator discloses estimand + error-type + memory as separate
fields, never one "confidence" number). *Verdict: ADOPT-CANDIDATE.* The numeric sibling of [[M10]] — it directly
informs the GY value engine and Atlas DS16 value/uncertainty grammar (show the law + tail + basis, not a bare
number).

**M17 — Method validity is a function of the decision/loss/deployment structure it serves; the convenient
default is valid only in a narrow, must-be-proven regime.** The sharpest Foundry logical signature — the
convenient question is always the wrong one. P6.07: "is the model differentiable?" is the wrong test —
delta-method is admissible only for smooth + local + moment-only loss with non-heuristic inputs, else Monte
Carlo. P6.10: global ECE is the wrong object — calibration is decision-relevant only when identifiable *for the
decision class* (threshold→local-near-τ; subgroup→multicalibration) on observable scope with a CI below the
utility margin. P6.13: a weight-discount is the wrong tool for systematic bias — measurement error must enter as
an *observation model* matched to the error structure. P6.12: a size-only index override is the wrong join —
alignment is a four-stage claim-separated process matched to the index & missingness structure. P6.17: random
K-fold is the wrong split — validity means respecting decision-time filtration & deployment cadence. *Verdict:
ADOPT-CANDIDATE.* Corollary (P6.11): the naming itself can launder authority — forbid ontological overclaim words
("hidden" minimum, "exactly-once", "coverage guarantee") and require the conditioned/observed phrasing;
"false-hidden rate must be zero" is its semantic-test form.

**M18 — Proposer ≠ verifier: the generator proposes bounded candidates; a small trusted checker disposes;
the proposal is candidate-only and never emits its own certificate.** The signature move of the LLM-scaffolded
Phase-7 reports (P7.11 theorem drafting, P7.12 estimator synthesis, P7.13 literature synthesis, P7.14
hallucination detection) — the operational form of B-on-A applied to LLM tooling. The LLM may draft a
statement/sketch/tactic/query, fill bounded slots, or propose a mutation; it may NEVER emit a proof-certificate,
truthfulness tier, uncertainty interval, or admissibility label. Verification is delegated to a *small
deterministic trusted checker* (a proof-assistant kernel that "does nothing but check proof terms" — P7.11; a
deterministic compiler + CEGIS counterexample loop — P7.12; a span-level entailment / citation-faithfulness
verifier — P7.13/P7.14), and the checker's acceptance authorizes only its own narrow claim (kernel: proof-valid-
for-*this*-statement; NOT statement-faithful; NOT admissible). Two enforcement rules: the proposal space is a
pre-approved typed grammar (SyGuS/Sketch — no arbitrary code), and the loop closes on typed counterexamples with
every failed candidate preserved (CEGIS), never free-form self-improvement. *Verdict: ADOPT-CANDIDATE.* Directly
informs the GY generation cycle — N10's compiler-conformance fix (constraining the provider to the full
owner-derived tool-schema for 18/18 conformance) is exactly this move's bounded-grammar enforcement.

**M19 — The selection / search / tuning process is itself a budgeted, accountable operation — never free
preprocessing.** Adaptive selection contaminates the final claim unless it is logged as a first-class design
object with disjoint data roles. Unifies P7.04 (DP budget composes over *every data-dependent touch* of the
protected unit — tuning, model-selection, validation, calibration — not over "document stages"; "free
preprocessing" that reads private data is the canonical error), P7.12 (disjoint `search`/`critic`/`calibration`/
`sealed` data roles — Cawley–Talbot selection bias reappears the instant search and inference share data), P7.08
(hidden holdouts must *rotate*, and an item that leaks into public exemplars must be *retired*), and generalizes
P6.08 (hidden adaptivity, not adaptivity, is the enemy). Also: blocking/partitioning is a hidden-bias source that
must be evidenced separately from the comparison step (P7.06, P7.09). *Verdict: ADOPT-CANDIDATE.* The GY sibling:
this is why the hidden-eval discipline retires contaminated fixtures and why N10 held a sealed holdout distinct
from the training slice.

**M20 — Stratify / decompose / attribute at the granularity that changes the verdict, not at the convenient
unit.** The coarse unit (aggregate score / whole-answer / doc-level citation / suite id) systematically hides the
semantically critical failure. From P7.09 (stratify benchmarks by *regime cell* — the conditions that change
identifiability / inference-type / failure-mode — not by dataset/theme/method, and report aggregate + per-regime +
claim-conditioned), P7.14 (score by *atomic claim + reasoning-link*, not whole-answer binary — a correct answer
can carry a hallucinated rationale), P7.13 (attribute provenance at *claim→span*, not doc-level — a doc-level
citation never proves the span supports the claim), P7.02 (bind the guarantee to the *exact estimand*, not a
generic "estimate"). *Verdict: ADOPT-CANDIDATE.* The Foundry-plane sibling of Scientist's atom+synthesis-join
([[SCI-R2]]) and the evaluation-granularity counterpart of [[M17]].

---

## §2·A Per-report distillation — Batch 1 (Scientist)

Each entry names the load-bearing move (not the whole report), the verdict, and where it maps. Reports
are frozen at `research_only`; nothing below is a capability.

**SCI-R0 — Research-track admission gate (report 148).** The meta-frame: a research track must emit a
`research-only promotion packet` (hypothesis+scope, benchmark proxy, falsification pack, statistical
report, contamination posture, explicit readiness cap, and the *named downstream consumer* it will later
adapt into) **before** it can touch readiness / default-enable / governance / review / export. *Verdict:
ADOPT-CANDIDATE as the governing gate for this whole ledger* — it is literally the rule this distillation
enforces on itself, and it maps to the GY promotion-gate discipline (D3.8) and the readiness ladder. The
"name the existing consumer you will adapt into" requirement is the sharpest reusable clause. Cross-link:
[[M1]], [[M8]].

**SCI-R1 — Typed bipolar admissibility, not a support scalar (report 149).** Support is a **typed bipolar
relation**: two positive subtypes (`supports_evidentially`, `is_prerequisite_for_acceptance`) and
`attacks`; a claim is admissible when it has a covering support core over family-required predicates
**and** no undefeated applicable attack — not when it "scored higher." Output is status-bearing (semantic
result + dialectical overlay + publishability/readiness cap), never a boolean. *Verdict: ADOPT-CANDIDATE
for the bipolar/predicate-coverage structure; the report's own "strong support" rule is local and
WEAKER-THAN-EXISTING relative to our grounding depth.* Maps to CGF (provable correspondence, not
nearest-name) and claim-support semantics. Cross-link: [[M3]], [[M6]].

**SCI-R2 — Atom-level support with typed synthesis-joins (report 158).** Paraphrase/synthesis support is
proven, not matched: atomize the claim (FActScore-style: subject/predicate/object/scope/time/jurisdiction/
population/exceptions + relation-atoms for synthesis), normalize each source into evidence units, judge
each atom by domain NLI entailment **+ scope match** (not lexical overlap), and give every cross-source
join its own verdict — `supported_join | assumption_join | scope_broken_join | contradicted_join`, where
any `assumption_join` caps the result at `partially_supports`/`review_required`. *Verdict: ADOPT-CANDIDATE
— the join-typing is the smart move*; it is the exact discipline that stops "Frankenstein synthesis" (atoms
individually supported, bridge unproven). Strong resonance with CGF and with the GY refusal-first stance.
Cross-link: [[M3]], [[SCI-R1]].

**SCI-R3 — Source quality as veto+cap+route, never a composite score (report 150).** Authority, recency,
primary-source status, duplicates, conflict each enter as a **monotone** modifier — `source_class`/`source_role`
prior on admissibility, claim-family-specific freshness TTL (not a blanket interval), duplicate →
independence-zero, material conflict → review, blocking conflict → block — composed **lexicographically and
fail-closed** so no combination of good signals raises authority above the weakest boundary; the composite
score is triage-only. *Verdict: REINFORCES-EXISTING (weakest-boundary composition) + ADOPT-CANDIDATE for the
claim-family TTL matrix and duplicate→independence-zero rule.* Cross-link: [[M3]], [[M6]].

**SCI-R4 — Constrained, gate-first VOI (report 151).** Detailed above as [[M5]]. The reusable formula:
`CCVOI(a|G,B) = Feasible(a,G) × (gate-yield + false-pass-reduction + false-block-reduction + support-delta +
reviewer-burden-reduction + decision-uncertainty-reduction)` evaluated against a **typed** budget vector
(compute/reviewer-time/legal-access/urgency stay typed, never collapsed to one exchange rate). *Verdict:
ADOPT-CANDIDATE, routed to GY-N11* — the δ-budget ledger and this share a spine. The kill-rule is worth
keeping verbatim: positive VOI may never waive a hidden holdout, rotating challenge, or human review.
Cross-link: [[GY-N11]], [[M7]].

**SCI-R5 — Human review: risk-triggered, mandate-scoped, packetized, measured (report 152).** Two reusable
moves: (a) the trigger taxonomy — `authority-transition` / `rights-and-public-risk` / `authority-deficit` /
`responsibility-integrity` — with mandatory review **only** on a trigger, else sampling-audit (avoids
proportional-governance drift, our P13); (b) the reviewer sees a **decision packet for challenge** (top
evidence *and* strongest disconfirming evidence, blocked claims, unresolved assumptions, uncertainty/
calibration/freshness, `reviewer_mandate_scope`), and effectiveness is measured in three layers
(per-decision adequacy → behavioral telemetry → longitudinal outcome calibration) under the [[M7]]
control-vs-measurement rule. *Verdict: ADOPT-CANDIDATE, routed to Atlas DS9* — and note the live hook: **DS20
already landed review-effectiveness telemetry on the append-only access audit for DS9**, so R5 is the
design brief that hook was built for. The rubber-stamp / explanation-laundering / missing-observation
counterexamples are ready-made DS9 negatives. Cross-link: [[Atlas-DS9]], [[M10]].

**SCI-R6 — Contamination containment as one-way derivation (report 153).** Detailed above as [[M4]]. The
reusable status lattice (`sealed_raw → sanitized_internal → warning_only_memory / projection_only_public`,
with `blocked_contaminated` as the fail-closed sink) and the `sealed_contamination_pack` fixture family
(memory-leak, challenge-export, replay-leak, claim-export, search-time-contamination) are the yield.
*Verdict: ADOPT-CANDIDATE, routed to §3.5.11 / CGF.* The external anchor is strong (Carlini memorization,
search-time contamination inflating deep-research scores). Cross-link: [[GY-3.5.11]], [[SCI-R7]].

**SCI-R7 — Predictive challenge validity needs time-split replay (report 157).** The honest split:
generated challenges can be **valid** (typed seed, expected failure mode, reviewed admission, mutation-
preserving) and **non-leaky** (provenance/split-safe, redacted export) today, but **predictive of real
failures is unproven and must stay `blocked`** until a sealed time-split backtest (generator sees `T0`,
`T1` hidden real failures) shows out-of-sample lift over a keyword/random baseline. Non-leakiness is
**provenance-first**; statistical contamination-audit is a secondary guard (it is unreliable under
distribution shift). *Verdict: ADOPT-CANDIDATE for the methodology; the predictive claim itself is
WEAKER-THAN-EXISTING to admit — keep it blocked.* This is the correct antidote to "synthetic hardness =
real robustness." Cross-link: [[M8]], [[SCI-R6]].

**SCI-R8 — Decision-lifecycle rulebook: reissue vs supersede vs withdraw (report 154).** The reusable
test: "same decision, re-issued after new checks" = `reissue`; "a different decision now governs (law/scope/
population/basis changed)" = `supersede`; "cannot be relied on at all" = `withdraw`; and — critically —
**not every context change is a withdrawal** (refresh/amend < supersede < withdraw). Six-status lifecycle
over `valid`, history-preserving (append-only, never silent overwrite), with incidents as the hardest
trigger and drift handled by thresholded response, not auto-reissue. *Verdict: ADOPT-CANDIDATE, routed to
GY-N12* — this is the same machinery as N12's model-revision epochs + stale-certificate revalidation, seen
from the decision-artifact side; the `reissue/supersede/withdraw` typing is a clean addition to N12's
revision-trigger vocabulary. Cross-link: [[GY-N12]], [[M6]].

**SCI-R9 — Fan-out epistemics: novelty gain over duplicate/conflict/citation-failure mass (report 155).**
Fan-out helps only when it raises **unique supported evidence-needs** faster than it raises duplicate mass,
unresolved-conflict mass, and citation-failure risk; else skip it or run shadow-only. Reusable defaults:
trigger-based (not always-on), **max 3 branches**, `scout → merge → synthesize`, novelty-based merge
(late-fusion/MMR/effective-independence), and correlated-error awareness (a model monoculture with a shared
frontier yields pseudo-diversification). *Verdict: ADOPT-CANDIDATE as an operational rule; REINFORCES-
EXISTING on the independence/count discipline ([[M3]]).* Directly relevant to any multi-agent Scientist
loop and to CPA-R23 (agent-choice ledger). Cross-link: [[M3]].

**SCI-R10 — Trust-calibration exports without overclaiming (report 156).** Detailed above as [[M10]]. The
strongest external result in the batch: explanation-first exports raise acceptance without improving
calibration and can worsen error detection via overload; the fix is structured transparency (blocker
visibility, qualified+numeric+basis uncertainty, `may_not_use_for` on machine export), four projections
from one substrate. *Verdict: ADOPT-CANDIDATE, routed to Atlas (DS12 public gate, DS9, surface
constitution).* This is the most directly frontend-relevant finding in the batch and lines up with
CPA-R16 (public-explanation comprehension). Cross-link: [[Atlas-DS12]], [[M7]].

---

## §2·B Per-report distillation — Batch 2 (Fabric)

The Fabric reports are markedly more **repo-grounded** than the Scientist ones — they cite real primitives
(`ProcessingGuaranteeContract`, `SchemaEvolution.compare()`, `FabricLineageTracker`, `RecordSession`/
`ReplayStore`) and several report that the code **already honestly self-labels** its limitation
(`graph_temporal_scope="partial"` + `research_track="R3"`; generic streaming default `at_least_once_with_dedupe`;
row-level quarantine). Consequence: most Fabric findings are *REINFORCES-EXISTING at the discipline level* with
the yield being the **specific taxonomy / fixture pack**, not a new law. The exception is the six-axis move,
which is load-bearing and new ([[M11]]).

**FAB-R1 — Defect→impact is a typed effect-SET with deterministic precedence, not a bucket (report 159).**
A single data-quality defect can simultaneously widen uncertainty and cap readiness; `hard_blocker` dominates
all; and `no_decision_impact` is a **proven negative** (replayable proof of irrelevance via lineage-closure or
sensitivity-proof), never a default from a low defect count. Precedence: `hard_blocker > readiness_cap >
uncertainty_widening > no_decision_impact_proven`. Widening is legitimate **only** when the defect is
parameterizable (interval/scenario/bias-model) AND the consumer reads it as uncertainty — else it is
pseudo-precision and must be a cap or block (MNAR missingness that can flip sign/ranking is the canonical
"looks widenable, isn't" case). *Verdict: ADOPT-CANDIDATE ([[M12]]).* Maps to our uncertainty-envelope +
readiness caps; the passport admit/quarantine logic in the GY acquisition executor is an instance.

**FAB-R2 — Institutional prestige is a capped, logged weak prior; source-trust ≠ claim-truth; reliability ≠
credibility (report 160).** Source trust = a calibrated, purpose-bounded, multi-dimensional profile of the
source's *production process* (identity / provenance / process / historical-calibration / independence /
timeliness / transparency — all observable), with `institutional_context` as an eighth, explicitly capped prior
that may break a tie but never flip a blocker to pass or raise a claim-support tier. External anchors: DORA
("judge on merits, not the journal") and the intelligence-analysis rule that *source reliability* and
*information credibility* must stay separable (allow "reliable source / non-credible claim"). *Verdict:
REINFORCES-EXISTING (weakest-boundary) + ADOPT-CANDIDATE for the reliability/credibility diagonal and the
capped-prestige rule.* Reinforces [[M3]] (pseudo-independence collapse). Cross-link: [[M11]].

**FAB-R3 — Bitemporal traversal must be snapshot-reducible over ONE effective graph cut (report 161).** Pick
`branch`+`snapshot`, fix one `(valid_at, tx_at)`, reconstruct the effective graph cut, THEN traverse — never
prove a path by unioning edges each visible at a *different* tx-cut. Point-cut default (interval answers explode
complexity → a separate operator); deterministic temporal-first winner selection (latest tx within cut, tie-break
`(tx_time, fact_id)`), never trust-weighted; journey/time-respecting paths are a different query kind
(out-of-scope). *Verdict: ADOPT-CANDIDATE — the sharpest anti-P08 (time-role-mixing) move in the batch.* The repo
already self-labels this `partial`/`research_track="R3"`, which is exactly the honest posture to keep. Cross-link:
[[M11]], [[GY-N12]].

**FAB-R4 — Lineage compression = policy-governed projection over a sealed full graph (report 162).** You literally
*cannot* "compress and keep all audit-critical edges" if edge means original edge — quotient views preserve paths
but not exact edges and can invent spurious dependencies. So: sealed full graph internal; projection graph derived;
compress only within **homogeneous regions** (no crossing authority/privacy/trust/temporal/replay boundary);
topology-preserving redaction (hide attributes, keep participation via surrogate nodes); **exact-vs-induced edge
typing** (`exact_direct | exact_control_or_usage | induced_summary`, cf. OpenLineage DIRECT/INDIRECT); every summary
edge carries a **witness digest**. *Verdict: ADOPT-CANDIDATE ([[M13]]).* The lineage-specific instance of [[M4]].

**FAB-R5 — ER calibration = typed, time- and policy-conditioned relation risk, not a timeless "same-entity" score
(report 164).** First type the relation (`same_entity_same_time` / `administrative_predecessor_successor` /
`alias_or_rename` / `broader_narrower` / `conflicted`); only within a fixed relation semantics may you calibrate.
Calibrate **per slice** (entity-kind × relation × source-family × identifier-regime × language × temporal-overlap ×
code-system-version × change-regime); no calibration data for a slice → review-only, never "guess by analogy".
Separate risk budgets (`false_merge_rate` / `missed_true_link_rate` / `cluster_consistency_risk`), not one
threshold; decision lattice `auto_merge / review_required / auto_reject / blocked_by_drift`. Killer counterexample:
UN M49 codes (former/current Germany 280/276, Ethiopia, Sudan) — name+code similarity yields 0.97 but the correct
verdict is `predecessor_successor`, not `same_entity`. Sharp eval trick: synthetic **impossible links**
("never-match decoys") to estimate false-discovery rate. *Verdict: ADOPT-CANDIDATE.* Maps to [[GY-N12]] (identity
across regime change) and reinforces [[M3]]. Cross-link: [[M11]].

**FAB-R6 — Honest processing-guarantee taxonomy; the strong label needs an atomicity proof; today no default path
qualifies (report 163).** `batch_atomic` (artifact/manifest boundary only), `at_least_once`,
`at_least_once_with_dedupe` (generic-streaming default), `effectively_once` (future hardened adapter: needs
idempotency + replay-retention + convergence), `exactly_once_narrow` (needs a full `atomicity_proof` over input
offsets × state × outputs), `replay_only`. External anchor: Flink/Dataflow/Kafka all draw the same line —
engine-internal exactly-once ≠ end-to-end exactly-once (side effects outside the commit boundary can double),
and accuracy ≠ completeness (late data is dropped). The guarantee binds to a **(source, sink, path) tuple**, and
no-proof ⇒ no-label. *Verdict: REINFORCES-EXISTING (honest-diagnostics fail-closed labeling) + ADOPT-CANDIDATE for
the taxonomy and the accuracy≠completeness distinction ([[M12]]).* Cross-link: [[GY-N13b]].

**FAB-R7 — Semantic schema drift = six-lane corroboration with an honest `indeterminate` (report 171).** No single
method can *prove* no-drift; an **extensional-no-signal** change (same column, same values, but denominator /
code-system / derivation-formula / normative-meaning swapped) is undetectable from data alone and MUST return
`indeterminate_manual_review`, never fabricated certainty. Six lanes: declared-semantics, observed-semantics
(profile + concept-drift detectors like ADWIN), learned-semantics (Sherlock/Sato — corroborator only, never
authority), lineage-definition (transform/AST/metric-hash + source substitution — catches formula change under
unchanged shape), reference-vocabulary (UCUM/QUDT units, official code lists, SHACL/OWL — catches USD→EUR, FIPS→ISO,
per-100k→per-1k), and honest-indeterminate. Killer case: `unemployment_rate` keeps name/type/range but the
denominator silently shifts labor-force→working-age. *Verdict: ADOPT-CANDIDATE ([[M14]]).* The Fabric sibling of
Scientist [[SCI-R2]] (atom + synthesis-join). Cross-link: [[GY-N12]], [[FAB-R5]].

**FAB-R8 — Adversarial ingestion robustness = a two-layer fixture stack that constrains/caps/blocks, never raises
value trust (report 165).** Cross-family **core pack** (parser/encoding hostility, value poisoning, metadata
deception, source-identity spoofing via homoglyph/punycode/IDN, endpoint hostility incl. HTTP-200-with-error-body
and pagination loops, and review/export hazards like CSV formula-injection **on the ingest/quarantine side too**)
+ **source-family packs** (CKAN/Socrata/Opendatasoft, SDMX, SPARQL — each has distinct metadata/temporal/endpoint
attack surfaces). Admission principle: a fixture pass never raises value trust; parser hazard → block/quarantine,
metadata deception → trust/readiness cap + mandatory review, replay non-closure → cannot promote to a higher-trust
label even if the payload looks correct. The "operator-safe paradox" (safe for JSON ingest, unsafe once a
quarantine/review payload is serialized to formula-injectable CSV) is the sharp counterexample. *Verdict:
ADOPT-CANDIDATE.* Maps [[M8]] (sealed holdout / false-pass). Cross-link: [[GY-N13b]], [[M11]].

**FAB-R9 — Auditable provenance without leakage = a bounded set of typed audit PREDICATES over commitments, not
free graph browsing (report 166).** Full interactive inspection + zero leakage is a bad goal (preserve too much
detail → the underlying query/source is reconstructable). So: canonical provenance internal (tenant-private CAS) +
a `ProtectedProvenancePacket` external = commitment root + role-scoped sanitized view + inclusion/consistency proofs
+ selective-disclosure proofs + policy reasons + replay-binding. Default-deny raw `connector_id`/`dataset_id`/
`query_id`/SQL; default-allow only a fixed predicate set ("lineage traces to an allowed source-class", "packet
N→N+1 append-only-consistent", "same-input replay matches committed snapshot", "hidden edge exists and is correctly
typed", "disclosed value satisfies committed range/set/equality"). Crypto substrate: CT-style append-only logs
(tamper-evidence, **not** secrecy) + BBS/BBS+ selective disclosure + optional ZK. Sharp negatives: "hash the
low-entropy ids" (dictionary attack), "keep path structure, drop labels" (structural inference of hidden edges),
"PII scan = privacy solved" (detection ≠ non-disclosure policy). *Verdict: ADOPT-CANDIDATE for the audit-predicate
grammar ([[M13]]); the ZK substrate stays research_only.* Cross-link: [[Atlas-DS12]], [[M4]].

**FAB-R10 — Policy-world replay = a six-slot minimal CLOSURE, not one magic artifact (report 172).** Slots: (1)
source-admission contract, (2) family-specific capture state (the only family-varying slot: HTTP =
RecordSession/response artifacts + watermark; file = CAS ref + object version/etag + listing; SQL = query spec +
source position; **CDC = offset + schema history + dedupe policy**; official-corpus = SnapshotProvenanceManifest),
(3) **complete** source evidence closure (ALL sources — today's `DataSnapshot` takes `evidence_bundle.sources[0]`,
unsafe for multi-source worlds), (4) lineage/provenance closure, (5) world-state replay anchor (segments or
retained snapshot/branch), (6) closeout envelope binding all six axes without collapsing to a score. Missing any
slot ⇒ debug replay, not serious replay (fail-closed). External anchors: Debezium schema-history is *mandatory* for
CDC replay; an Iceberg snapshot is metadata-pointer + manifest-list + manifests, not just a version id. *Verdict:
ADOPT-CANDIDATE, routed to GY-N13b* — the acquisition executor already does record/replay + CAS + journal-first raw
evidence; R10 formalizes the slots it must not drop (esp. multi-source evidence closure and, for any future CDC
lane, schema history). Cross-link: [[GY-N13b]], [[M11]].

---

## §2·C Per-report distillation — Batch 3 (Foundry, P6.01–P6.17)

The Foundry batch is the largest and most numeric (estimation / uncertainty / calibration / reproducibility). It
is even *more* repo-grounded than Fabric — it cites real primitives (`MethodAdvisorResult`, `ProcessingGuaranteeContract`
det-tiers, `UncertaintyEnvelope`/`DistributionCarrier`, `RobustSetCalibrationReport`, `IdentifiabilityDiagnosticResult`,
DDM `CalibrationExpiration`) and repeatedly leans on a discipline the repo *already practices*: heuristic
Hessian/Laplace envelopes are self-labelled `interval_semantics=HEURISTIC_RANGE`, `is_heuristic_ci=True`,
`gate_eligible=False`. Consequence: most Foundry findings are *REINFORCES-EXISTING at the discipline level* (they
strongly reinforce [[M5]], [[M6]], [[M12]]) with the yield being the specific taxonomy / decision-rule / fixture,
plus the three new logical moves [[M15]]/[[M16]]/[[M17]]. Foundry is a Layer-3 subordinated engine, so most of
this routes to the future **Foundry-subordination lane** as conformance-battery / promotion-gate criteria, not
now-work — except the value/uncertainty and calibration findings that touch live GY value and N11/N12 work.

**P6.01 — Human method-override = a typed deviation record over an IMMUTABLE advisor result; "override changes
selection, never evidence" (167).** The reviewer's choice materializes a `MethodAdvisorOverrideRecord` + a computed
`authority_delta`; the override may never raise the truthfulness tier, replace the regret certificate / consensus,
clear a runtime downgrade, or auto-admit publishability — authority for the chosen method comes only from its own
receipts. *Verdict: ADOPT-CANDIDATE, routed to Atlas DS9.* (Honest caveat the report itself flags: no fresh HCI
scan — its external grounding is standards-only; the core move stands on repo invariants.) Cross-link: [[Atlas-DS9]], [[M1]].

**P6.02 — Circuit-breaker recovery = deterministic epoch-based, not "timeout passed" (173).** Persisted `trip_epoch`,
time-gated-but-not-time-sufficient half-open, a *single idempotency-safe* probe (mutating replay needs an idempotency
key or synthetic read-only probe, else block), purpose-limited close criteria read from *typed outputs* (not HTTP-200);
`authoritative_for = runtime_recovery_admission` only. *Verdict: REINFORCES [[M12]] + ADOPT the "close ≠ method
validity" separation ([[M15]]).* Routes to the reproducibility/runtime plane.

**P6.03 — Non-associative distributed reduction must declare a strategy or fail closed (168).** `reproducible_accumulator`
(binned/ExBLAS-style) | `canonical_tree` (pinned leaf-order/partition/tree/route) | `statistical_envelope` — "same
seed" is NOT determinism, and reproducibility ≠ accuracy (a fixed order makes a *wrong* sum reproducible). The
`[1e20, -1e20, 1]` triple is the clean falsifier. *Verdict: REINFORCES [[M12]]+[[M15]]; ADOPT the three-strategy
taxonomy.* Routes to GY replay/E-gate reproducibility discipline.

**P6.04 — Cost = a distribution law; the point estimate is a derived summary (169).** Two policies with equal
expected cost can have radically different upper tails → decision needs `P(cost>cap)`/`CVaR95`, not the mean;
positive-skew families (`GAMMA`/`LOGNORMAL`) are missing from the enum; dependence must be *stored* (don't sum
independent marginals). *Verdict: ADOPT-CANDIDATE ([[M16]]), routed to the GY value engine + Atlas DS16.* Currency
note: the report correctly flags OMB M-25-15 (Feb 2025) rescinded the 2023 Circular A-4 and restored the 2003
edition — don't cite 2023 A-4 as current.

**P6.05 — Error-bound-FIRST, not budget-first; the precision budget is a vector (170).** Fix the tolerable error
bound + replay semantics, then pick the cheapest *certified-feasible* precision config (roundoff/sampling/calibration/replay
as separate channels); fail-closed (`INFEASIBLE_TARGET_PAIR`) if none — test-case-only tuning is never gate-eligible.
*Verdict: REINFORCES [[M5]] (gate/feasibility-first) + [[M16]] (vector not scalar).* DEFER caveat: the term "precision
budget" is undefined in-repo; the report chose the nearest numeric interpretation — keep research-only until the
term is pinned.

**P6.06 — Robust plan selection: budget-admissibility FIRST, then robust-lower-bound welfare among admissible (174).**
Regret and rank-stability are *secondary diagnostics*, never the primary selector; return a contested-frontier /
abstain when the leaders are within the uncertainty margin or `price_of_ambiguity`. Set-robust when evidence is
bounds-only; moment-DRO when mean/covariance exist. *Verdict: REINFORCES [[M5]]; ADOPT the ordering.* Routes to the
GY value engine.

**P6.07 — Delta-method vs Monte Carlo is a function of the loss, not the model (176).** "Is the model differentiable?"
is the wrong test; delta is admissible only for smooth + local + moment-only loss with *statistical* (non-heuristic)
inputs; MC is the default for threshold/tail/asymmetric/nondifferentiable loss; a heuristic-calibration input must
NOT be routed through delta for admissibility. *Verdict: ADOPT-CANDIDATE ([[M17]]).* Flags a real repo bug: the
auto-dispatcher routes on `distribution_family==NORMAL` and ignores `is_heuristic_ci` — a genuine finding worth a GY/Foundry ticket.

**P6.08 — Importance sampling / adaptive allocation: hidden adaptivity is the enemy, not adaptivity (177).** Log the
allocation as a *design object* (propensities, proposal density, stopping rule, target-selection event); SNIS/PSIS
are *diagnostics*, not unbiased authority (Pareto-k̂ ≥ 0.7 downgrade, ≥ 1 block; positivity/ESS kill rules); measure
gain by coverage + decision-error, not interval width; post-hoc target selection after adaptive collection needs a
selective-inference correction. *Verdict: ADOPT-CANDIDATE, routed to GY-N11* — this is exactly N11's world
(adaptive querying of the gate under a risk budget). Cross-link: [[GY-N11]].

**P6.09 — Coherent risk composes via DUAL risk envelopes, not interval aggregation (175).** Conservative = convex-hull
union (`max_i ρ_i`); authorized weighted = Minkowski (`Σ λ_i ρ_i`); intersection only with proven independence.
Static single-stage AVaR/spectral only; multi-stage needs *nested + rectangular* ambiguity; shared-lineage kills
precision-weighted narrowing; no dual envelope ⇒ `outer_bound_only`. *Verdict: ADOPT-CANDIDATE ([[M16]]); reinforces
[[M3]] (independence).* Routes to the GY value engine.

**P6.10 — Calibration is decision-relevant only when identifiable *for the decision class* (178).** Global ECE ≠
decision-relevant; threshold action → local calibration near τ; subgroup routing → multicalibration; needs observable
scope, a CI below the utility margin, and nontrivial resolution; selective-labels ⇒ `observable_case_only`. *Verdict:
ADOPT-CANDIDATE ([[M17]]).* Routes to the CGF/calibration plane + Atlas DS16/DS17; ties to the L5 calibration registries.

**P6.11 — Reject the word "hidden" for multi-start minima (179).** Describe `distinct_observed_minimum` (solver +
budget + equivalence-rule conditioned, with a local-optimality certificate) + a run-level `coverage_status` deficit;
"not found" is a coverage fact, never an ontological object. *Verdict: ADOPT the [[M17]] vocabulary corollary;
false-hidden rate must be zero.* Routes to Foundry-subordination.

**P6.12 — Target alignment is a four-stage, claim-separated, fail-closed process (180).** semantic-alignment →
index-alignment (`exact`/`inner-overlap`/rule-governed reindex — never size-only override) → missingness
(support + mask + quality, not silent `fillna`) → imputation/linkage (a *separate* producer carrying uncertainty).
The same-length-shifted-index case is the clean falsifier. *Verdict: ADOPT-CANDIDATE ([[M17]]).* Routes to the
calibration/data plane; reinforces [[FAB-R5]] (linkage uncertainty must propagate).

**P6.13 — Measurement error enters calibration as an observation MODEL, not a weight-discount (181).** Match the
model to the error structure (additive/multiplicative/censored/misclassification/errors-in-variables/dark-uncertainty);
the current `compute_effective_weight()` discount is the *fallback for weak evidence only*; both-axes or systematic
bias needs an explicit bias/EIV channel. *Verdict: ADOPT-CANDIDATE ([[M17]]).* Flags a repo gap: the default adapter
drops `identification_mode` and ignores `measurement_bias_flag`. Routes to the calibration plane.

**P6.14 — Sequential Bayesian updating needs FOUR separate coverage guarantees (182).** posterior-coherence /
computational-correctness (SBC + R-hat/ESS) / predictive-coverage (conformal / adaptive-conformal) / anytime-valid
(confidence-sequences / e-values); a credible interval is NOT automatically a coverage guarantee, and exact
distribution-free conditional coverage is impossible. *Verdict: ADOPT-CANDIDATE ([[M15]]), STRONG tie to GY-N11* —
N11 already draws anytime-valid instruments (e-values / confidence sequences); P6.14's four-class split and
"credible-interval ≠ coverage" refine N11's instrument taxonomy directly. Cross-link: [[GY-N11]].

**P6.15 — Bounded-memory estimators publish two artifacts: estimate + a typed disclosure (183).** The disclosure
carries estimand-semantics / approximation-semantics (rank vs value error; formal vs empirical vs heuristic) /
memory-semantics (hard cap + degradation mode) / assumptions / uncertainty-admissibility / runtime-events; "exact"
must fail-closed under bounded memory; rank-error must never be reported as value-error. *Verdict: ADOPT-CANDIDATE
([[M15]]+[[M16]]).* Routes to Foundry-subordination.

**P6.16 — Online calibration monitoring = a two-loop, sequentially-valid, authority-bounded early-warning (185).**
evidence-admission (label-maturity + provenance fail-closed) → robust estimation (equal-mass/smoothed ECE +
subgroup/horizon slices) → change-detection (CUSUM/EWMA) → sequential-evidence (e-values, conservative alpha); a
warning is *posture*, never current-run claim evidence; lattice `advisory → persistent → mandatory_review →
readiness_capped → scoped_block`. *Verdict: ADOPT-CANDIDATE, routed to GY-N12 (drift = an epoch/revision trigger) +
Atlas surface honesty (designed warning/stale states).* Ties to the L5 `schema_regime` substrate. Cross-link: [[GY-N12]].

**P6.17 — Valid streaming/rolling CV = respect decision-time filtration & deployment semantics (184).** delayed-prequential
(online) / rolling-origin (batch retrain) / purged-embargoed (overlapping labels); random K-fold is a *narrow
autoregressive exception*, never a default; a global preprocessing fit is a leak that no chronological ordering
repairs; authoritative only for out-of-sample predictive performance under the declared deployment. *Verdict:
ADOPT-CANDIDATE ([[M17]]).* Routes to the calibration/validation plane.

---

## §2·D Per-report distillation — Batch 4 (Foundry Phase 7, P7.01–P7.14)

Phase 7 is Foundry's frontier tier. It splits into two clusters: **(a) advanced numerics / privacy / federation**
(P7.03–P7.07) — mostly `bridge_missing` / `research_only`, capabilities the repo does *not* have and may not need
soon → they route to the future privacy / Fabric- / Foundry-subordination lanes as deferred discipline; and **(b)
LLM-scaffolded tooling + benchmark governance** (P7.01, P7.08–P7.14) — the B-on-A generation discipline, the
source of [[M18]], and the cluster that touches live GY generation-cycle work. Same repo-grounding + honest
self-labelling as Phase 6. One recurring actionable finding across P7.01/P7.11/P7.12: `tests/_golden/foundry/
signature_baseline.json` reports `method_count: 0` — an empty golden that can't anchor a real method inventory.

**P7.01 — Lower a probabilistic program as a method-family + evidence bridge, NOT a new PPL (186).** Reuse
compile/execute + method ABI + `UncertaintyEnvelope`; separate representation-semantics from inference-semantics;
posterior draws are an evidence sidecar while policy-facing intervals go through the envelope; a multimodal
posterior must never be compressed to a clean single CI. *Verdict: ADOPT the reuse-first lowering ([[M15]]).*
Routes to Foundry-subordination; ties to the GY N4 model-compilation path.

**P7.02 — A proof-carrying estimate certificate = estimate + guarantee-class + witness + envelope + replay +
boundary, each a separate claim (192).** The guarantee class must be explicit (exact / sharp-bound / finite-sample-
marginal / time-uniform / asymptotic / heuristic); narrow default = count only exact / bounded / finite-sample /
time-uniform as proof-carrying, asymptotic-only stays research/prototype. PCC analogy: a predefined checkable
policy + a machine-checkable witness + an independent validator (not "trust the producer"). *Verdict:
ADOPT-CANDIDATE ([[M15]]+[[M12]]).* Routes to the GY value/certificate plane (the IR proof-carrying certificates
already in the substrate). Strong.

**P7.03 — Cross-hardware bitwise reproducibility is REFUTED as a default; a tiered contract replaces it (187).**
`bitwise` (same fingerprint) / `numeric-tolerance` (same arch) / `cross-arch-tolerance` / `distributional`
(stochastic) / `no-claim-without-measured-canaries`; "same seed" ≠ determinism (non-associative FP + parallel
reductions); the repo already self-labels `seed_prior` with `validation_status="unknown"`. *Verdict: ADOPT the
tier lattice ([[M12]]); one claim to REFUSE outright: "reproducible on any hardware."* Routes to GY replay /
E-gate reproducibility (the byte-stable-×2 discipline).

**P7.04 — DP budget composes over every data-dependent touch of the protected unit, not over "document stages"
(188).** Start from the protected unit (user-level default) + contribution bounds, not ε; account tuning /
model-selection / validation / calibration; sequential composition is the default, parallel only with *certified*
disjointness; keep the native accountant space (RDP/PLD) internal and convert to (ε,δ) only at release; use an
odometer/filter for adaptive pipelines. *Verdict: ADOPT-CANDIDATE ([[M19]]); DEFER (bridge_missing — a capability
the repo lacks).* Routes to a future privacy lane.

**P7.05 — Synthetic microdata are "utility-preserving enough" only for a declared workload, across three
independent axes (189).** fidelity + analytic-replicability + decision-stability-on-real-holdout, plus a separate
privacy/generalization pass; there is no universal scalar "good enough" threshold; synthetic data alone never
raise a major policy claim above governed *supporting* evidence. *Verdict: ADOPT the workload-declared 3-axis
protocol ([[M17]]); DEFER (research_only).* Killer case: a rare-subgroup / threshold decision flip that aggregate
fidelity hides.

**P7.06 — Privacy-preserving record linkage = a typed candidate-evidence pipeline, not an identity-truth engine
(190).** Separate PII from payload; declare the threat model; keep quality-evidence and privacy/disclosure-risk as
*separate* artifacts; Fellegi–Sunter's third class (clerical review / ambiguous zone) must survive; the method
family is part of the artifact, not a hidden implementation detail (no single method wins on privacy *and* quality
*and* scale). *Verdict: ADOPT the separation discipline ([[M15]]); DEFER (bridge_missing).* Ties to [[FAB-R5]]
(entity resolution / linkage uncertainty must propagate).

**P7.07 — Federated correctness = a bundle of separate proofs, not one "it's federated" flag (191).** Only two
admissible classes: *lossless* (sufficient-statistics / additive-estimating-equation parity with the centralized
estimator) or *asymptotically-justified* (explicit theorem + N/K regime + site-level assumptions + empirical
coverage). FedAvg-style deep FL without inference theory stays `research_only`. Secure aggregation ≠ correctness;
DP noise must enter the uncertainty envelope. *Verdict: ADOPT-CANDIDATE ([[M15]]); DEFER.*

**P7.08 — Hidden holdouts for a judge stack = three independent loops, never one static test (193).**
`shadow_calibration` (update judge weights / bias / drift) + `sealed_promotion` (release gate, separate runner) +
`reserve_rotation` (untouched until contamination/drift/refresh). Never raw majority vote — calibrate to human gold
(Dawid–Skene / Bridge), abstain/escalate on high disagreement or collapsed judge-independence; retire any item
that leaks into public exemplars. *Verdict: ADOPT-CANDIDATE ([[M19]] rotation + [[M8]]).* Routes to the GY
hidden-eval / contamination discipline (N10 sealed holdouts). (The report couldn't find "six-judge stack" in the
repo — treat as an independent research prompt, `research_only`.)

**P7.09 — Stratify benchmarks by REGIME, not by dataset / theme / method (204).** Six regime axes (assignment &
identification / transport & shift / interaction & response / temporal-decision / support & overlap /
measurement-quality); report in three cuts (aggregate / per-regime-cell / claim-conditioned); use a sparse
anchor/stress/edge lattice, not the full Cartesian product; a benchmark is authoritative only for
*benchmark-adequacy*, never for method admissibility. *Verdict: ADOPT-CANDIDATE ([[M20]]).* Routes to GY
universality / U-gate testing and the promotion gate.

**P7.10 — Method promotion requires a six-family adversarial/pathological stress dossier, fail-closed (194).**
authority-chain / identification-&-data-validity / calibration-under-shift / adversarial-brittleness (non-robust
features) / runtime-numeric-reproducibility / decision-&-welfare-stability. Only `pass` / `pass_narrow_scope` /
`fail_closed` are acceptable outcomes — a *fail-open* blocks promotion. *Verdict: ADOPT-CANDIDATE ([[M17]]+[[M8]]).*
Routes to the GY promotion gate (D3.8) as a conformance battery.

**P7.11 — LLM theorem drafting: kernel-verified ≠ statement-faithful ≠ policy-admissible (195).** The LLM proposes
(draft / sketch / tactic); a *small trusted proof-assistant kernel* disposes; statement-faithfulness (does the
formal statement match the source intent?) is a SEPARATE, review-dependent claim that kernel acceptance never
establishes; `axiom`/`sorry`/unapproved oracles without rechecking = blocked. *Verdict: ADOPT-CANDIDATE ([[M18]]).*
Routes to the GY B-on-A generation discipline; strong tie to N10 (structured-output conformance).

**P7.12 — LLM-scaffolded estimator synthesis is safe only as bounded candidate-generation over a predeclared
grammar (196).** SyGuS/Sketch grammar (pre-approved operators, no arbitrary code / imports / network); CEGIS
counterexample-guided rejection with every failed candidate preserved; disjoint data roles (search / critic /
calibration / sealed); the LLM is proposer, never verifier; a partially-identified task → set-valued or blocked,
never a laundered point estimate. *Verdict: ADOPT-CANDIDATE ([[M18]]+[[M19]]).* Routes to the GY generation cycle —
bounded-grammar generation is exactly N10's tool-schema constraint.

**P7.13 — Literature-synthesis provenance must be preserved at four levels, never collapsed into "citations"
(197).** search-provenance (PRISMA-S/PRESS: queries / cutoffs / dedup / exclusions / incompleteness) +
document-and-span provenance (claim→span→version→source, not doc-level) + claim-support provenance (`used_in_
generation` vs `attached_post_hoc` — correctness ≠ faithfulness) + study-lineage (collapse dependent lines by
`study_family_id` — anti-P14), with the certainty layer (GRADE) kept separate. *Verdict: ADOPT-CANDIDATE
([[M20]]+[[M3]]).* Routes to the Scientist plane / CGF; reinforces [[SCI-R2]].

**P7.14 — Policy-text hallucination detection = evidence-grounded, claim-decomposed, reasoning-integrity separate
from support and admissibility (198).** Decompose the answer into atomic policy/reasoning claims; check span-level
support (not doc-level); check the reasoning path (a correct answer can carry a hallucinated rationale; premise
injection; citation doping; a missed exception in a long document); calibrated abstention; self-confidence is not
authority. Status keeps `support` and `reasoning_integrity` as separate lattices, both distinct from admissibility.
*Verdict: ADOPT-CANDIDATE ([[M20]]+[[M18]]).* Routes to Scientist/CGF and Atlas DS surfaces (designed
grounding/abstention states); reinforces [[SCI-R2]].

---

## §3 Where these findings could land (consolidation map, not a commitment)

These are candidate routings to weigh once all batches are distilled — **not** approved plan edits.

- **GY-N11 (confidence ledger / δ-budget)** ← **SCI-R4** gate-first constrained-VOI framing (mandatory gate =
  feasibility constraint, not reward term) and **SCI-R0** admission-packet gate. The strongest single
  cross-link in the batch: N11's obligation-class δ-split and R4's `Feasible(a,G)` partition are the same
  law. If N11 adopts the `gate_satisfying/preparatory/ranking_only/inadmissible` partition as the shape of
  its "which certificates may spend," it gains a ready vocabulary. *Both remain conditional on P29
  obligation-completeness — do not present either as unconditional.*
- **GY-N12 (epochs + stale certificates)** ← **SCI-R8** decision-lifecycle `reissue/supersede/withdraw` typing
  and the "not every context change is a withdrawal" discriminator; **SCI-R6** sealed-raw derivation for
  epoch-boundary evidence.
- **§3.5.11 / CGF grounding firewall** ← **SCI-R6** one-way derivation law (extend leakage checks to serialized
  signatures/trace deltas); **SCI-R2 / SCI-R1** atom-level + typed-bipolar admissibility as the "provable
  correspondence, not nearest-name" discipline on the claim-support side.
- **Atlas DS9 (human decision integrity)** ← **SCI-R5** trigger taxonomy, decision-packet-for-challenge shape,
  three-layer effectiveness measurement under control-vs-measurement separation. **Live tie-in:** DS20's
  merged review-effectiveness telemetry hooks on the access audit are the instrument R5 specifies.
- **Atlas DS12 (public publication gate) + surface constitution** ← **SCI-R10** structured-transparency /
  four-projection / uncertainty-as-numeric-plus-basis discipline; connects to cross-cutting CPA-R16.
- **Atlas DS4 (status grammar)** ← the status-lattice *tension*: [[M6]] must be filtered through DS4's
  one-lattice, recompute-not-pin discipline so the batch's many proposed lattices don't reintroduce
  status-enum-proliferation.

*— Fabric batch —*

- **GY-N13b acquisition executor** (highest-value Fabric tie-in) ← **FAB-R10** six-slot replay closure
  (the executor already does record/replay + CAS + journal-first raw evidence; R10 names the slots it must
  not drop — complete multi-source evidence closure, and schema-history for any future CDC lane); **FAB-R8**
  adversarial public-data ingestion fixtures (it fetches WDI — spoofing / metadata-deception / replay-nonclosure
  are exactly its robustness surface); **FAB-R1** defect→impact precedence (formalizes the passport
  admit/quarantine); **FAB-R6** processing-guarantee honesty for the acquisition journal's at-least-once terminals.
- **GY grounding firewall / §3.5.11** ← **FAB-R4 + FAB-R9** ([[M13]]): sealed-original projection + witness /
  commitment is the cryptographic form of projection-scoped provenance; the audit-predicate grammar is how a
  future protected surface stays fail-closed.
- **GY-N12 (epochs + stale certificates)** ← **FAB-R5** (code-system version + predecessor/successor as an
  identity/epoch boundary) and **FAB-R7** (semantic drift = a revision/epoch trigger; code-system rebase).
- **The future Fabric-subordination lane** (per the Layer-2 post-S14 direction: foundry/fabric/scientist via
  ports/adapters/registry/conformance) is the natural home for the Fabric-internal disciplines that don't touch
  live GY work today — **FAB-R2** (source-trust profile), **FAB-R3** (snapshot-reducible traversal), **FAB-R6**
  (guarantee taxonomy), **FAB-R7** (drift corroboration). Carry them as conformance-battery candidates, not
  now-work.
- **Atlas (DS9 / DS12 / surface constitution)** ← **FAB-R9** (protected provenance = what a public/reviewer
  surface may disclose — the DS12 gate); **FAB-R2** (Trust View shows source-class/tier, never institutional
  prestige); **FAB-R1** (defect-impact reviewer packet → DS9).

*— Foundry batch —*

- **GY-N11 (confidence ledger / δ-budget)** ← **P6.14** (anytime-valid coverage = confidence-sequences/e-values,
  which N11 already draws; the four-guarantee-class split and "credible-interval ≠ coverage guarantee" refine N11's
  instrument taxonomy) and **P6.08** (adaptive querying of the gate must log allocation as a design object; SNIS/PSIS
  are diagnostics not authority; ESS/Pareto-k̂ kill rules) — the strongest Foundry tie to live work.
- **GY value / uncertainty engine** (GY-N8 value-outer-set, GY-N-V ValueOuterSet, the marginal-interval fallback) ←
  **P6.04** (cost = distribution law, tail metrics), **P6.09** (dual risk envelopes; nested+rectangular for multi-stage),
  **P6.06** (admissibility-first then robust-lower-bound welfare), **P6.07** (delta-vs-MC by loss structure). [[M16]] +
  [[M5]] applied to the value plane.
- **GY-N12 (epochs + stale certificates)** ← **P6.16** (online calibration drift = an epoch/revision trigger; ties to
  the L5 `schema_regime` changepoint) and **P6.17** (deployment-cadence / decision-time filtration as temporal semantics).
- **CGF / calibration-grounding plane** ← **P6.10** (calibration decision-relevance for the decision class),
  **P6.13** (measurement-error observation model), **P6.12** (four-stage target alignment) — these bind to the L5
  calibration registries (`trust_tiers`/`identification_mode`/`schema_regime`) already in the production substrate.
- **The future Foundry-subordination lane** (per the Layer-2 post-S14 direction: foundry/fabric/scientist via
  ports/adapters/registry/conformance + promotion gate D3.8) is the home for the Foundry-internal disciplines that
  don't touch live GY work — **P6.02** (breaker recovery), **P6.03** (deterministic reduction), **P6.05** (precision
  frontier), **P6.11** (multi-start minima), **P6.15** (bounded-memory disclosure). Carry as conformance-battery /
  promotion-gate candidates.
- **Atlas (DS9 / DS16 / DS17)** ← **P6.01** (typed override deviation record → DS9 human decision integrity);
  **P6.04/P6.09/P6.16** (distribution + tail + advisory/warning posture → DS16 value/uncertainty grammar and DS17
  confidence-ledger surface — [[M16]] made visual via [[M10]]).
- **Two concrete repo-bug findings worth GY/Foundry tickets** (not routing, but actionable): **P6.07** — the uncertainty
  auto-dispatcher routes on `distribution_family==NORMAL` and ignores `is_heuristic_ci`, so a heuristic envelope can be
  delta-propagated into an admissibility claim; **P6.13** — the default measurement adapter drops `identification_mode`
  and ignores `measurement_bias_flag`. Both are genuine (verify in code before acting — reports are untrusted).

*— Foundry Phase 7 batch —*

- **GY generation cycle (N4/N10 and the B-on-A discipline)** ← **P7.11** (proposer≠verifier, small trusted checker),
  **P7.12** (bounded grammar + CEGIS + disjoint data roles), **P7.01** (probabilistic-program lowering). [[M18]]/[[M19]]
  are the strongest Phase-7 tie to live work: N10 already practices bounded-grammar generation (the tool-schema
  conformance fix) and sealed-holdout separation — these reports name the discipline it was reaching for.
- **GY hidden-eval / promotion gate (D3.8) / U-gate universality** ← **P7.08** (three-loop rotating holdouts +
  contamination retirement), **P7.10** (six-family adversarial stress dossier), **P7.09** (regime-stratified benchmark).
  [[M8]]+[[M19]]+[[M20]] as the conformance-battery discipline for promoting any engine method.
- **GY value / certificate plane** ← **P7.02** (proof-carrying estimate certificate = the estimate/guarantee/witness/
  envelope/replay/boundary bundle) and **P7.03** (tiered reproducibility contract → the byte-stable-×2 / E-gate replay
  discipline).
- **Scientist plane / CGF grounding** ← **P7.13** (four-level provenance ledger, study-lineage collapse) and **P7.14**
  (claim-decomposed, span-level, reasoning-integrity-separate hallucination detection) — both reinforce [[SCI-R2]]
  (atom + synthesis-join support) and the grounding firewall.
- **Deferred (capabilities the repo lacks — future privacy / Fabric- / Foundry-subordination lanes)** ← **P7.04** (DP
  budget), **P7.05** (synthetic microdata), **P7.06** (privacy-preserving record linkage), **P7.07** (federated
  correctness). Carry the discipline; do not treat as now-work. P7.06 consolidates with [[FAB-R5]].
- **Atlas (DS9 / DS16 / DS17)** ← **P7.02** (certificate surface), **P7.14** (grounding/abstention states on the glass),
  **P7.01** (uncertainty as distribution not point — [[M16]]).

---

## §4 What NOT to adopt / honest caveats

- **Do not import the reports' status lattices wholesale.** Each proposes its own — collectively they are a
  status-enum-proliferation risk (our own anti-pattern). Adopt the *shape* (typed, fail-closed,
  research_only floor, recomputed states) and reconcile against the single Atlas status lattice.
- **Do not treat any report as a capability.** All eleven honestly self-cap at `research_only` /
  `implemented_but_not_orchestrated` / `semantic_test_missing`. SCI-R7's predictive-challenge claim is
  explicitly `blocked` — keep it blocked.
- **Do not present δ-style guarantees as unconditional.** R1/R4's admissibility and VOI bounds are
  conditional on obligation-completeness + validator-soundness — the same P29 regress that GY-N11 carries.
  Any consolidation must carry the conditionality clause (and, per [[M1]], red-test its deletion).
- **`authoritative_for`/`may_not_use_for` must be recomputed, not trusted by presence** (§3.5.10 / substrate
  gate-2). A label is not a control; the checker must catch the forbidden *consumption*.
- **Do not regress Fabric's already-honest self-labels.** Several Fabric primitives already carry the correct
  conservative label in code (`graph_temporal_scope="partial"` / `research_track="R3"`; generic-streaming default
  `at_least_once_with_dedupe`; row-level quarantine). The reports *validate* these; consolidation must keep them,
  not "upgrade" them without the proof artifact ([[M12]]) each label demands.
- **The status-lattice proliferation risk is now severe** ([[M6]] caveat, escalated again): across Foundry Phase 6 + 7
  the reports propose ~30 bespoke status lattices (defect-impact effects, reduction-certificate tiers, calibration-
  decision-relevance states, sequential-Bayes coverage classes, proof-carrying-certificate lattices, reproducibility
  tiers, DP-composition states, federated-correctness classes, judge-holdout states, …). Adopt the *shape* (typed,
  fail-closed, `research_only` floor, states recomputed not pinned) but every one must be reconciled against the single
  Atlas status lattice / DS4 discipline before it lands. Do not import ~30 parallel lattices.
- **A claim to refuse outright** (P7.03): "the computation is reproducible on any hardware." Bitwise cross-hardware
  reproducibility is refuted as a default; only the tiered contract ([[M12]]) is honest. If any consolidated artifact or
  surface asserts blanket hardware reproducibility, that is the overclaim to block.
- **Do not treat Phase-7 privacy/federation reports as capabilities** (P7.04/05/06/07): all are `bridge_missing` /
  `research_only` and describe capabilities the repo does not have. Capture the discipline; never present them as
  implemented. P7.08 additionally self-declares that "six-judge stack" isn't a repo object — an independent prompt.
- **Reports are uneven in grounding — weight the move, not the prose.** Several Foundry reports openly self-limit:
  P6.01 skipped a fresh HCI scan (standards-only external base), P6.05 flags that "precision budget" is an undefined
  in-repo term and it chose an interpretation. The *engineering/logical move* in each is still usable; the *external
  certainty* is not. Treat interpretation-dependent findings as DEFER until the term/scope is pinned.
- **Do not cite stale external anchors as current.** P6.04 correctly notes OMB M-25-15 (Feb 2025) rescinded the 2023
  Circular A-4 and restored the 2003 edition; any consolidation must not carry the 2023 A-4 as live guidance.
- **Repo-drift pointers, confirmed across all ~52 reports (four batches)** (hygiene items, not findings): essentially
  every Scientist, Fabric and Foundry report could not locate
  `docs/system-design-decisions/policy-design-execution-topology.md` at the cited path — a real stale baseline pointer
  worth fixing (or the baseline instruction updating). Phase 7 adds a second recurring one:
  `tests/_golden/foundry/signature_baseline.json` reports `method_count: 0` (an empty method-inventory golden), flagged
  by P7.01/P7.11/P7.12. *(Verify before acting — reports are untrusted content.)*

---

## §5 Batch ledger

| Batch | Track | Reports | Status | Distilled |
| --- | --- | --- | --- | --- |
| 1 | Scientist | `SCI-R0`..`SCI-R10` (11) | **DONE** | §2·A + moves M1–M10 |
| 2 | Fabric | `FAB-R1`..`FAB-R10` (10) | **DONE** | §2·B + moves M11–M14 |
| 3 | Foundry (Phase 6) | `P6.01`..`P6.17` (17) | **DONE** | §2·C + moves M15–M17 |
| 4 | Foundry (Phase 7) | `P7.01`..`P7.14` (14) | **DONE** | §2·D + moves M18–M20 |
| 5 | Lex | `LEX-R*` | pending | — |
| 6 | Cross-cutting public authority | `CPA-R*` | pending | — (note CPA-R16≈SCI-R10, CPA-R26≈SCI-R8, CPA-R22/R23≈DS20-authz already flagged) |

**Next:** when a batch arrives, distil into a new §2-style section + fold any genuinely new move into §1
(M-series), update §3 routing and §5. Consolidation into GY/Atlas is a **separate, later** deliberate act —
only after the backlog is fully distilled.
