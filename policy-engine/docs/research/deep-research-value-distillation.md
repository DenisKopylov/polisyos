---
title: Deep-Research Value Distillation Ledger
status: active
kind: research-synthesis
owner: team-architecture
created: 2026-07-20
revised: 2026-07-20 (Batch 1 — Scientist SCI-R0..R10; Batch 2 — Fabric FAB-R1..R10; Batch 3 — Foundry P6.01..P6.17; Batch 4 — Foundry Phase 7 P7.01..P7.14; Batch 5 — Foundry Phase 8 P8.01..P8.14; Batch 6 — Foundry Phase 9 P9.01..P9.14; Batch 7 — Foundry Phase 10 P10.01..P10.16; Batch 8 — Foundry Phase 11 P11.01..P11.15; Batch 9 — Cross-cutting Public Authority CPA-R1..R17; Batch 10 — Cross-cutting Public Authority CPA-R18..R28 distilled)
source: docs/research/remaining-deep-research-backlog.md
relationship: candidate_for_consolidation into docs/plans/active/layer3-slices/GY-engine-subordination.md and docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
authoritative_for: [research_finding_triage, consolidation_candidate_registry, move_adoption_gating]
may_not_use_for: [capability_claim, authority_grant, task_execution_contract]
note: "§6 is the per-move gate that authorizes a *specific* move to become a mandatory input to a *named* plan task (plan_adopted). A move NOT carrying plan_adopted in §6.2 remains under may_not_use_for. The raw §2 reports are never capability claims."
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
Batch 3 (Foundry Phase 6); **M18–M20** by Batch 4 (Foundry Phase 7); **M21–M24** by Batch 5 (Foundry Phase
8); **M25–M26** by Batch 6 (Foundry Phase 9); **M27–M28** by Batch 7 (Foundry Phase 10); **M29–M30** by Batch 8
(Foundry Phase 11); **M31–M35** by Batch 9 and **M36–M40** by Batch 10 (both Cross-cutting Public Authority) — but
all are cross-cutting and later batches may reinforce any of them.

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

**M21 — Anchored-support certificate: grounding to a source is provable correspondence to a *versioned,
fragment-addressed* official source, and correctness is a conjunction where any single mismatch blocks.**
The text/legal sibling of the causal grounding firewall (CGF) — "provable correspondence to a typed atom,
not nearest-name" applied to citations/norms. From P8.01 (regulatory citation proof = extracted value ∧
canonical official URI / ELI / Akoma-Ntoso *fragment* ∧ exact support span ∧ scope algebra
{legal_scope / jurisdiction / date / population / exception} ∧ same-input closure — "right value, wrong
article / wrong version / hidden exception" is a **hard FAIL**, its "Strict Attributed Extraction Accuracy"),
P8.04 (calibrate the citation *edge* at sentence/claim granularity, reuse the deterministic label family, and
treat retrieval coverage as its **own** calibrated claim — absence of a retrieved source is *not* proven
absence of support), P8.05 (statutory reasoning needs a legal-reasoning certificate binding norm-selection +
temporal competence + amendment lineage + argument/warrant/rebuttal — context ≠ authority; an LLM legal
summary stays candidate until Lex validates). Embedding / LLM / lexical similarity **prioritizes** candidates
but never **binds**. *Verdict: ADOPT-CANDIDATE.* Reuses the Scientist `citation_faithfulness` seed and the
`assurance_case.py` SACM/CAE/GSN graph; sibling of [[M18]] (the checker authorizes only its own narrow claim)
and [[SCI-R2]] (atom + scope match, not lexical overlap); routes to the CGF grounding plane. *Batch-6
extension (P9.02 TEE):* the same discipline governs cryptographic attestation chains — a signed quote/token
is verifier **input**, not proof; sufficiency needs Evidence + Endorsements + Reference Values + Appraisal
Policy + claim-specific binding + **freshness/nonce**, and grounds only a narrow claim class (genuine
platform, approved launch state), never runtime confidentiality or side-channel immunity. Freshness/staleness
is a load-bearing validity axis, not metadata: a one-shot attestation grounds only a launch-bounded claim.

**M22 — Triage-before-estimate + orthogonal conjunctive gates: classify the regime with an explicit typed
classifier *before* choosing the estimator, and split admission into orthogonal gates keyed to distinct
failure classes that must *all* pass and can *never* substitute for one another.** The dominant architectural
move of the applied-frontier batch. From P8.08 (geoprivacy = a Disclosure-Risk Gate ⊥ an Aggregation-Validity
Gate — a privacy pass is **not** a semantic pass, and vice versa), P8.07 (multimodal fusion = a
support-certification gate *then* fused estimation as a separate claim class — never fuse before support is
certified), P8.14 (DTR under partial observability = a four-route classifier {observed-Markov / belief-state /
proxy-identifiable / nonidentifiable}, each with a *different* authority ceiling — unsafe code silently
retrofits hidden state into a no-hidden-confounding method), P8.10 (OPE triage = a point-ID branch vs
partial-ID branches {no-overlap / hidden-confounding / proximal / worst-case} chosen by *identification
conditions*, not by whether the estimator runs), P8.12 (adaptive RCT = design-replay → backend-selection →
authority-boundary, the backend a rule keyed to the adaptation type), P8.11 (fairness = a typed profile
selecting one of several *incompatible* semantics). *Verdict: ADOPT-CANDIDATE.* The generalization of [[M5]]
(gate-first feasibility) and [[M17]] (validity is a function of the decision structure) into a multi-gate
router; routes to the runtime/quality admission ring and the Foundry-subordination method-selection layer.

**M23 — Set-valued / abstention honesty under non-identification; identification is an axis orthogonal to
finite-sample uncertainty.** When a quantity is only partially identified, out-of-support, or nonidentifiable,
the authoritative output is a bound / identified-set / ambiguity-set / abstention — **never** a point-with-CI
dressed as the answer; and the identified-set width is **not** sampling uncertainty (Imbens–Manski
separation). From P8.10 (partial-ID OPE returns an identification *envelope*; the midpoint or clipped-DR point
is the core overclaim; decide by baseline-relative dominance — lower bound vs threshold, not midpoint), P8.06
(a remote-sensing proxy needs an explicit *area of applicability*; outside predictor support → abstain /
downgrade, CV error does not transfer), P8.14 (nonidentifiable DTR → ambiguity set / pessimistic
safe-improvement window / acquisition plan, never a single best policy), P8.07 (unresolved support / linkage →
outer-bound envelope; uncertainty must **widen** when probabilistic linkage or areal transfer is added, never
shrink), P8.02 (an underidentified topic model is exploratory-only, not a measurement), P8.03 (an uncorrected
surrogate label is screening-only). *Verdict: ADOPT-CANDIDATE.* Strong tie to the GY search target-spec
direction (lifted state must be set-valued; marginal-interval fallback + unknown/incomparable) and to [[M16]]
(the canonical object is the set/law; the scalar is derived); sharpens [[M15]] with the
identification-vs-uncertainty non-substitution.

**M24 — No-cancellation / worst-case-over-process metrics: a claim about a *process* or a *tail* may not rest
on an average that lets a good period offset a harmful one.** For safety-through-time, fairness-through-time,
catastrophic rare events, or disclosure across a release graph, require positive-part / step-wise / anytime /
tail (chance / CVaR) metrics; an expectation-only or cancellation-friendly cumulative metric is
diagnostic-only and `may_not_use_for` the process/tail claim. From P8.13 (safe-RL needs a typed **quartet** —
final-policy feasibility + strong *no-cancellation* cumulative violation \(V^+_K\) + step-wise/anytime +
tail-risk; the "cancellation trap" — violate early, compensate later, pass a weak average — and the
rare-catastrophe tail are the mandatory falsifiers), P8.11 (fairness temporal-scope {stagewise / rolling /
cumulative / hindsight} are *different* claims; feasibility must be detected, not assumed), P8.09 (a change
boundary chosen as a function of the outcome is a kill rule — no target-dependent split), P8.08 (disclosure
risk is over the whole release *graph* incl. non-nested differencing, not one table). *Verdict:
ADOPT-CANDIDATE.* The temporal/tail sibling of [[M16]] (distribution, not mean) and [[M12]] (the reassuring
average carries the burden of proof); resonates with the DS19 / GY-N11 baseline-relative gating discipline.

**M25 — Vintage / as-of is a first-class modeling input, and the honest unit of temporal update is an
append-only delta over a sealed baseline — recency is not strength.** Two coupled disciplines. (a) The
*as-of* cutoff is a load-bearing input, never metadata: P9.05 makes ragged-edge nowcasting a *vintage-aware
missingness* problem at the highest frequency (the vintage object — cutoff, release calendar, publication
lag, missingness mask — is typed input; forward-fill and vertical realignment are semantic leaks that inject
artifact-driven dynamics); P9.02 makes attestation freshness load-bearing; P9.04 makes data-vintage a
reproducibility field. (b) An update is an *append-only delta transaction* over an immutable baseline, with
its own separated claims: P9.09 (living-review update = surveillance-diff ≠ inclusion/protocol-diff ≠
certainty-diff ≠ claim-impact-diff ≠ replay ≠ admissibility; the baseline is never overwritten; **a new
source is not stronger evidence**, and source-count-up ≠ confidence-up; dedupe preprint↔journal↔news to hold
the independence count; retrospective protocol narrowing after an inconvenient result is a block). *Verdict:
ADOPT-CANDIDATE.* The constructive form of the temporal axis in [[M11]] and the epistemic sharpening of
SCI-R8 / GY-N12 lifecycle (`reissue`/`supersede`/`withdraw`) — the update mechanic, not just the status;
directly informs GY-N12 epochs and the Atlas temporal-cursor discipline.

**M26 — Impossibility-scoped claims: when a property provably cannot hold universally or symmetrically, the
certificate must name the exact side / domain / regime where it holds AND carry the *provable* negative
region — a boolean or symmetric statement is unsafe by construction.** Distinct from [[M23]] (which is about
partial *identification* of a quantity): here a *property* is proven not to hold in general, so the honest
artifact is theorem-scoped with a mandatory negative scope. From P9.11 (deferred-acceptance strategy-proofness
is proposer-side + classical-domain only — `exact` there, `asymptotic`/`approximate`/`blocked` elsewhere,
with mandatory `may_not_use_for` {receiver-side truthfulness, couples, constraints, welfare, fairness, legal
admissibility, participant comprehension}; a boolean `is_strategy_proof` is unsafe by construction — Roth
asymmetry) and P9.12 (two-sided matching cannot promise bilateral truthfulness — pick the strategic principal,
state honesty for that side, declare the negative scope for the other). *Verdict: ADOPT-CANDIDATE.* Makes the
[[M1]] `may_not_use_for` field load-bearing and *provable*, not merely cautious; the market-design sibling of
[[M23]]'s abstention honesty.

**M27 — Representation-conditioned descriptor: a learned geometric / topological / embedding / intensity
summary is authoritative only relative to its *declared representation* (metric, filtration, embedding,
aggregation, observation model), which is itself load-bearing; geometric fidelity never becomes substantive /
causal / policy authority; the observation process that shaped the descriptor must be *modeled*, not assumed
away; and opaque latent dimensions may not be semantically relabeled without separate evidence.** The
signature of the ML-shape cluster. From P10.09 (persistent homology describes the shape of the *chosen*
complex/filtration, not "the shape of policy" — a stable H1 loop can be a missingness/masking donut, not an
institutional gap), P10.10 (geometry-good ≠ causally-faithful — unsupervised disentanglement is impossible
without inductive bias, latent axes are not causes, forbid relabeling `latent_2` → "social capital"), P10.08
(basis / FPCA / signature coefficients are engineering sidecars, never a publication surface; and *path ≠
functional* — one trajectory yields many normative functionals), P10.11 (an administrative graph's topology
is entangled with the registration / linkage / observation mechanism — "model *how the network became
observable*"; observability ≠ need), P10.06 (don't collapse (time, space, mark) into tabular features; the
conditional-intensity semantics is load-bearing; MAUP / discretization leakage; a post-event mark used as a
pre-event covariate is leakage). *Verdict: ADOPT-CANDIDATE.* The observation-process-firewall half generalizes
[[M19]]'s leakage discipline to derived descriptors; the no-substance-from-geometry half sharpens [[M17]] for
representation learning. The repo already ships the fail-closed template — `embedding_fidelity.py`'s
red/yellow/green + `ALLOW_AS_NUISANCE_ONLY` / `ALLOW_AS_ADJUSTMENT` actions and `latent_bridge_synthesis`'s
`opaque_label_required` — so this is extend-existing, not build-new.

**M28 — Certify the run by a checkable *a-posteriori* bound in decision-relevant units, never by a convergence
/ success flag.** The authoritative numerical/statistical claim is a computed, verifiable bound for *this* run
— expressed in the unit the decision uses and keyed to the method regime — not "it converged," "iterations
stopped," "the fit succeeded," "the solver returned a point," or a static default. From P10.16 (a Bellman
residual maps to a *policy-loss* bound that is regime-dependent — exact-PI needs none, VFI-extract needs
2γ/(1−γ)², approximate-PI needs the (1−γ)² form and only a *stabilized-policy proof* sharpens it to (1−γ);
"values barely changed" is not an admissibility claim, and late-iteration errors dominate so keep the trace),
P10.01 (a solver certificate is objective lower/upper bounds — "the solver returned a point" is not exactness;
abstain when unbounded/uncertified), P10.03 (an exact primal witness + residuals + replay outranks an
ε-witness outranks an empirical low-regret learning trace, which is support-only), P10.13 (an exact
hypergeometric / anytime-valid e-process bound is the proof layer; Monte-Carlo power and historical calibration
are calibration-*only*, never the authoritative bound), P10.02 (εN must be an evidence-backed computed bound,
not a static 0.05). *Verdict: ADOPT-CANDIDATE.* The numerical/statistical sibling of [[M12]] (the reassuring
verdict is the one that must be earned) and [[M18]] (the checker authorizes only its own narrow claim); the
"decision-relevant unit" clause ties to [[M17]].

**M29 — Compose multiple decision sub-results through their *native operators*, never by scalar sum; each
sub-result's authority stays bounded to its own claim (one never covers another's); the composition record
only certifies composability + weakest-link status; guard the two hazards — double-counting (one effect
entering two layers) and the convenient-sum that erases a veto (subgroup / fairness / feasibility / incentive-
compatibility).** From P11.05 (worst fiscal scenario = a *nested* protocol EVT → DRO → GE-feedback → risk-
functional; order matters — the exogenous-shock tail and the endogenous-amplification tail are different
claims, so re-tailing GE output double-counts; a worst-case is authority-bearing only with tail-cert ∧
ambiguity-cert ∧ equilibrium-cert), P11.12 (sequential value = six typed sub-results {intertemporal-welfare /
option-delta-vs-*named-irreversible-baseline* / allocation-feasibility / fairness-frontier / dynamic-IC /
composition-record}, "not summed symmetrically" — real-option value is a *delta relative to a named baseline*,
not a second copy of continuation welfare; integer-allocation and IC enter as *feasibility filters*, not
welfare add-ons; fairness stays a *frontier* until reviewed value-choice authority appears), P11.10 (combine
forecasts at the CDF/distribution level, never by averaging medians+bounds component-wise → quantile crossing;
a linear pool of calibrated forecasts is *not* calibrated — mandatory post-combination recalibration), P11.09
(Bayesian-diagnostics and safe-BO share one surface but two non-interchangeable lanes — retrospective-fit ⊥
prospective-search), P11.02 (whistleblower governance = five control loops {intake / source-protection /
anti-retaliation / investigation / disclosure}, each with its own boundary — never one "we have a channel"
claim). *Verdict: ADOPT-CANDIDATE.* Sharpens [[M16]] (law-not-scalar) and [[M11]] (don't average axes) to the
multi-result decision-composition setting; overall status is the weakest-link (weakest-boundary composition).

**M30 — Unify heterogeneous producers at a *thin shared admission port* with a discriminated-union of
family-native payloads — never force a shared theorem family, shared scalar, or merged domain semantics
("common port, not common theorem").** The consumer gate checks only the shared required fields (same-input
closure, typed uncertainty semantics, a family-native certificate ref, an explicit authority boundary); the
domain-specific payload stays local to its family. **This is the constructive resolution to the certificate-
proliferation risk (§4):** the ~60+ candidate artifacts across Phases 8–11 should collapse to *one* shared-waist
envelope + per-family payloads — not ~60 parallel authority families, and not one merged mega-scalar. From
P11.13 ("общий порт — да, общий theorem family — нет" — a trajectory-enclosure cert and a motif-count cert are
admitted by ONE rule but keep distinct payloads, discriminated by `certificate_domain`), P11.15 (cross-toolchain
replication = canonical estimator-spec + input-snapshot + *language-native lowerers* + result-canonicalization +
one parity certificate; "same formula ≠ same estimand" because design-matrix / missingness / vcov / df semantics
differ across R/Stata/Python, so the *lowered* spec is the unit of replication, not the surface script — a sharp
[[M27]] instance), P11.09 (one authority surface, two lanes), P11.05 / P11.12 (one composition record over
family-native sub-certs). *Verdict: ADOPT-CANDIDATE.* Extends [[M1]]/[[M2]] (envelope + additive sidecar) into a
shared-port-with-union architecture; reuses the repo's `CrossBackendEquivalenceCertificate` seed.

**M31 — Heterogeneous-authority axis separation: public-authority admissibility is NOT one governance score.**
The whole CPA corpus (R1–R17) converges on one law: *legal authority / democratic legitimacy / organizational
authority / operational capacity / public transparency / contestability / technical evidence* are **non-fungible
evidentiary lanes**, each with its own resolution routes and its own status. The aggregate composes by
**weakest-boundary + hard-gates** (minimum-over-load-bearing), never by average or weighted sum, and **a passing
lane cannot buy a failing one** — strong technical evidence never mints a legal mandate; a fast, cheap service
never mints legitimacy; a human-review trace in the wrong role never mints value authority. Grounds: Bovens
(accountability = actor↔forum; legal accountability is the most unambiguous lane because it rests on specifically
assigned duties), Koppell ("multiple accountabilities disorder" — the dimensions cannot share one scale),
NIST/OECD/OMB M-25-21/UK ATRS (roles, oversight, traceability, appeals as *separate* operational duties). **The
repo already owns the composition primitive:** `capability_authority.py` uses "minimum across load-bearing
factors" with `admissible|limited|contested|blocked` + `authoritative_for`/`may_not_use_for`. *Verdict:
ADOPT-CANDIDATE.* This is the CPA signature; it reinforces [[M29]] (native-operator composition, no scalar-sum)
and [[M5]] (gate = constraint, not reward), and **pairs with [[M30]]**: the ~17 CPA records should be
discriminated-union payloads over one admission port, composed by this 7-axis weakest-boundary rule — not 17
authority families and not one merged governance number.

**M32 — Delivery-capacity envelope: technical validity is necessary, never sufficient; execution capacity is a
separate blocking axis, and state capacity is a *ceiling*.** From R6/R7/R8: a design is `deliverable` only if the
executing institution can staff, monitor, explain, contest and *stop* it. Two sharp sub-laws: **(a) model
adequacy ≠ delivery adequacy** — a calibrated model behind an unstaffed appeal queue, missing logs, or no override
path is `blocked`, not `deliverable`; **(b) local success does not extrapolate — the "pocket-of-efficiency trap":**
a regional pilot may be `limited` while nationwide rollout stays `blocked`, because state capacity caps the *whole
delivery chain* (coordination, frontline discipline, long-run monitoring), not a per-site KPI. Capacity evidence
(skills / staffing-continuity / institutional-memory / maintenance-burden) must come from **observable sources**
(rosters, training records, incident/postmortem stores, backlog & response telemetry, CHAOSS contributor-absence-
factor) — never from a prose runbook. *Verdict: ADOPT-CANDIDATE.* Extends [[M5]] (hard gate) and the capacity-as-
constraint discipline; the four capacity record-classes are family-native payloads for [[M30]]/[[M31]].

**M33 — Authorization-to-aggregate: social weights are a recorded *permission to aggregate*, not ground truth.**
From R3: objectives, social weights, distributional priorities and acceptable trade-offs are stored as a typed
normative-authorization artifact recording *who* authorized *which aggregation* under *what mandate / scope /
dissent / TTL* — **not** as a model parameter or loss weight. Absent a valid schedule the system may emit only a
Pareto frontier + scenario cards + a typed `NormativeDecisionRequest`; it must **never silently scalarize**. The
value schedule is "permission to aggregate this way," not "the truth about fairness." Banned laundering paths:
silent equal-weight default, historical-prior-as-social-weight, proxy-as-priority, fairness-metric-library-default.
Grounds: UK Green Book / OMB Circular A-4 (distributional weighting is a *disclosed choice*, applied consistently,
never a hidden default), HM Treasury MCDA (record disagreement → sensitivity, never average it away), Kleinberg-
Mullainathan-Raghavan (no universal fair scalarization exists). *Verdict: ADOPT-CANDIDATE.* The constructive
counterpart to "the system is never the principal"; reinforces [[M16]] (the canonical object is the full
partial-order / red-line / floor structure, never the collapsed scalar) and [[M31]] (its own axis).

**M34 — Contestability is proven, not gestured; explanation efficacy is *measured*, not assumed from fluency.**
From R5/R16: a public-facing recommendation is publishable only behind a typed contestability packet — same-input
explanation, a *competent independent* reviewer with real authority to change the outcome, and withdraw/reissue
mechanics; an "Appeal here" link bound to no case, or a rubber-stamp review, fails closed. And an explanation earns
governed use only when it is shown to raise **objective** understanding (simulatability / limit-recognition /
error-detection) *and* challenge quality at **non-increasing false confidence** — perceived clarity, trust, or
adoption are not release criteria. Two named failure modes: **recourse laundering** (telling a person how to change
*themselves* to flip the output instead of how to challenge the decision's *validity* — burden-shift, not
contestation) and **false-confidence inflation** (illusion of explanatory depth; deceptive explanations can
out-persuade honest ones). **Repo already owns the primitives:** `human_review.py` scores reviewer independence /
separation-of-duty / rubber-stamp risk; `graded_outcomes.py` requires a verified recourse pointer for high-stakes
publish. *Verdict: ADOPT-CANDIDATE.* Extends [[M10]] (structured transparency, not explanation) with a *behavioral
falsification test*; reinforces [[M7]] (control-artifact vs measurement-artifact) and [[M8]] (false-pass fixtures).

**M35 — Graded external-supplier admission: escrow + independent audit access + pinned reproducibility replace
both blind trust and impossible full-disclosure.** From R10/R11: third-party AI/data-supplier artifacts never
enter authority *directly*. Three admission tiers — **archive** (`candidate_only`) → **serious-PDC authority-path**
(six sub-dossiers: supplier-chain / data-provenance / TEVV / logging / incident / independent-review) →
**claim-closing** (needs authority-side independent verification + [[M3]] independence accounting). For proprietary
models/data the neutral contract is a **three-contour regime**: confidential *evidence escrow* + *independent audit
access* + *graded reproducibility* (same-input → metric → portability replay tiers), version/hash/time-bound and
release-triggered — the AI-Act Art.78 "confidential access ≠ zero access" pattern, and the EDPB rule that
*dataset-not-published ≠ model-safe* (extractability/memorization is its own axis). Two anti-patterns fail closed:
**vendor-run eval treated as independent evidence**, and **"no incident found in AIID/OECD-AIM" read as "no
incidents"** (those corpora are media-based, incomplete, and self-declared non-authoritative — research/challenge
inputs only, never closure). *Verdict: ADOPT-CANDIDATE.* Reinforces [[M3]] (vendor + literature sharing lineage is
*one* line, not two), [[M18]] (proposer≠verifier), [[M21]] (anchored-support certificate over a versioned source).

**M36 — Typed post-publication perturbation cascade: incidents, appeals, corrections, retractions, legal changes
and discovered bias are *distinct event classes*, not one "reopen" — each with a least-expansive default scope,
downgrade-only pre-adjudication authority, a bounded lifecycle action, and NO silent mutation of a closed case.**
Unifies R18/R19/R21/R26. A perturbation is authoritative only for `review_required` / `contested` / annotation
*until adjudicated*; only after adjudication may it become authoritative for `invalidate` / `reissue` / `supersede`
/ `withdraw`. The scope rule is *least-expansive-but-safety-preserving*: a single upheld appeal invalidates the
*instance*, not the class; a renumbered rule with an unchanged logic-hash is `annotation_only`, not supersession; a
media/AIID entry is a *candidate trigger* requiring corroboration, never self-acting withdrawal. **Supersede ≠
withdraw:** a law change supersedes a claim that was lawful-and-replay-valid at closure (old case stays immutably
replayable under its closure-time rules), and only *withdraws* when continued public reliance is itself unsafe or
unremediable. Source-status invalidity (retraction / correction / expression-of-concern / living-review-supersession
/ fabricated-citation / withdrawn-source) propagates as a replayable `EvidenceValidityEvent` through
source→evidence-line→claim→publication — no authority survives silently after its support is lost. **Repo already
owns most of this:** `case_lifecycle.py` enumerates the lifecycle states + `REVISION_ACTION_ORDER`;
`core.contracts.rule_evolution` emits a revalidation blocker on a semantic (not cosmetic) rule change;
`obligation_rules` has `PUBLIC_CONTESTATION` + public-revalidation effects; `scientist/governance/continuous` has
`incident.py`/`invalidation.py`/`reissue.py`/`lifecycle_bridge.py`. *Verdict: ADOPT-CANDIDATE ([[M25]] recompute-
not-pin over time + [[M31]] per-axis + one-lattice).* Reinforces [[SCI-R8]] decision-lifecycle typing.

**M37 — Capability is not permission: an agent's external action (search / tool_call / draft / data_request /
external_interaction) needs a *pre-action*, mandate-bounded, least-privilege, replay-linked authority packet — not a
post-hoc log.** From R22/R24. `autonomous_action_allowed = verified_identity ∩ explicit_permission ∩
mandate-bounded delegation ∩ operation-in-envelope ∩ live accountability binding`; out-of-envelope stakes/
reversibility/data-sensitivity route to a typed `HumanDecisionRequest` and a five-rights-valid `HumanDecisionRecord`
(a click by the wrong role/after TTL/without disconfirming evidence is not approval — P26 responsibility laundering).
**Authority is not monotone:** "can search" never grants "can data_request / write / publish"; `draft` is not
globally low-risk (type it by audience/externality). The security precondition (R24): treat the agent as an
*untrusted transducer* whose inputs, tools, and long-term memory are all attack surfaces (indirect prompt injection,
tool poisoning, memory poisoning) requiring governed admission — memory records masquerading as policy/incident
facts must pass the same candidate→authority gate as any external document; multi-agent handoff is first-class
attack surface. *Verdict: ADOPT-CANDIDATE ([[M18]] proposer≠verifier + [[M31]] + [[M5]] gate-not-reward).* The D3
delegation layer (`DelegationContract`/`HumanDecisionRequest`/`HumanDecisionRecord`) is still `contract_only` /
`producer_missing` — this is the pre-action gate it needs.

**M38 — Orchestration and handoff transparency *preserve* authority: log each choice as an authority delta, and
transfer bounded artifacts + a responsibility chain, never authority wholesale.** From R23/R25. Every load-bearing
orchestration choice (evidence-selection / tool-choice / framing / compression) leaves a typed trace carrying the
candidate universe + rejected set + decision-policy ref + an **explicit authority effect** — `authoritative_for = ∅`
by default (the repo's `search_ledger` already does exactly this). Because *framing-narrowing* and *lossy
compression* are themselves authority moves: compression that cannot preserve retained-limitations, denied-uses and
omitted-counterevidence must **fail closed**, not silently emit a clean-looking public summary ("compression
laundering", "framing laundering", "selection laundering" — a low-`k_eff` selected set masquerading as broad
consensus, [[M3]]). Cross-agency handoff (R25) is a *two-step bounded acceptance*: the receiver `meet()`s the
offered `AuthorityBoundary` against its own permitted purposes (intersection of allowed uses, union of deny-lists;
empty ⇒ blocked), inherits *no* responsibility by default, gets a typed *context capsule* (not a summary blob), and
an `llm_candidate` summary can cross departments only as `candidate_only` routing hint — never as decision authority.
Auditability-by-construction: time-correlated who-emitted/who-accepted/what-denied records, verifiable offline.
*Verdict: ADOPT-CANDIDATE.* Extends [[M10]] (structured transparency) with an authority-delta discipline; reuses
the repo's `AuthorityBoundary.meet()`, `ClusterHandoffRecord`, `AuthorityDerivationTrace`. **Gap:** G6 emits
prompt/tool/search/orchestration/replay ledgers but *no* compression-specific ledger yet.

**M39 — A proxy standing for a policy construct requires a construct-validity *case*, not a fit statistic —
technical validity is necessary, never sufficient, and measurability never authorizes the construct.** From R27
(source of the "streetlight bias" antidote). Before a metric / text-variable / remote-sensing signal / administrative
field may *substitute* for a construct (need, vulnerability, fraud-risk, legitimacy, public value, trust), it needs
content + substantive/process + structural + external (convergent/discriminant/predictive) + generalizability +
consequential evidence (Messick / Jacobs-Wallach), PLUS a **modality-specific independence floor**: administrative →
source-process audit (incentives, coding rules, missingness, schema drift, QAAD); text → confounder + semantic
validation beyond gold labels (ValiText — a classifier "measuring ideology" that actually learned incumbency fails
discriminant validity); remote-sensing → an *independent* reference sample with reported CIs (CEOS LPV — a train/test
split is not independence; correlated reference can make the worse map look better). **Aggregation-level jumps
(school-history proxy → individual grade, Ofqual 2020), non-independent validation, and single-number fit all fail
closed.** **Repo already owns the seam:** `runtime/quality/construct_registry.py` carries
`construct_validity_requirements` / `proxy_validation_rules` / `required_time_roles` / per-posture
`authority_requirements` (research/governed_pilot/production). *Verdict: ADOPT-CANDIDATE ([[M27]] representation-
conditioned + [[M17]] validity-by-decision-structure + [[M31]]).* `implemented_but_not_orchestrated` +
`verification_missing`.

**M40 — External governance regimes compile to *plane-separated obligation atoms over source anchors*, never to
authority — one atom = one governance plane, binding-force is a typed field, and only producer-owned fulfillment
artifacts (not the cited regime) close a gate.** From R28. A `RegimeClauseAnchor` is authoritative only for source
identity/traceability; an `ObligationAtom` carries *exactly one* of the seven planes ([[M31]]) plus a typed
`binding_kind` — voluntary framework (NIST RMF, "not a checklist"), binding law (EU AI Act), management memo (OMB
M-25-21), transparency duty (UK ATRS), governance framework (OECD), incident-learning (OECD-AIM/AIID, `monitor_only`
never approval). **Governance-prose-laundering guard:** a published ATRS record, a NIST profile, a "no AIID match",
or an LLM legal summary can be a traceability anchor / public projection / rebuttal input — *never* a filled
authority slot. An LLM-extracted "obligation" enters only as `ObligationRuleCandidate` behind a `RuleGovernanceDecision`
(the repo already blocks `LLM_CANDIDATE` from the blocking frontier). No universal cross-jurisdiction legal
conclusion — jurisdiction-neutral contract + one example mapping per regime. *Verdict: ADOPT-CANDIDATE ([[M31]]
planes + [[M30]] shared port + [[M1]] envelope).* Extends the [[M30]]×[[M31]] consolidation architecture to the
*ingestion* of external regimes; open question = the `lex` (legal artifacts) vs `obligation_rules` (mixed-bindingness)
boundary.

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

## §2·E Per-report distillation — Batch 5 (Foundry Phase 8, P8.01–P8.14)

Phase 8 is Foundry's **applied-frontier** tier: text/legal extraction (P8.01–05), spatial/multimodal
(P8.06–08), and causal-decision under weak identification (P8.09–14). Two signatures dominate. First, **every
one** self-caps at `accepted_narrow_scope` + `bridge_missing` — none claims an implemented capability, and
each repeatedly names an *existing repo seed* (`scientist/validation/citation_faithfulness.py`,
`runtime/quality/assurance_case.py`'s SACM/GSN graph, `ir.analytics.partial_identification`,
`ir.analytics.invariance`, `ir.analytics.alignment_certification`, `foundry.methods.catalog.spatial`,
`foundry.agent_sim.world`) — so the work is overwhelmingly **wire / extend**, not build-new. Second, the batch
is where the *set-valued* and *multi-gate* disciplines ([[M21]]–[[M24]]) crystallize. Because Foundry is a
Layer-3 subordinated engine, most of this routes to the future Foundry-subordination lane and the runtime/
quality admission ring; a few (P8.05 legal, P8.09 causal-change, P8.10/12/13/14 causal-decision) touch live GY
grounding/causal work. **Caution:** the batch proposes ~14 new candidate certificate types — a proliferation
risk called out in §4.

**P8.01 — Regulatory citation correctness = a typed anchored-support certificate, not a citation string (199).**
Value ∧ canonical official URI (ELI / Akoma-Ntoso fragment) ∧ exact support span ∧ scope algebra ∧ same-input
closure; "right value, wrong article / stale version / hidden exception" is a hard FAIL ("Strict Attributed
Extraction Accuracy"). Reuse the deterministic Scientist `citation_faithfulness` labels + goldens.
*Verdict: ADOPT-CANDIDATE ([[M21]]).* `bridge_missing` — the Scientist seed exists but no Foundry→PDC
claim-evidence admission bridge. Routes to Scientist/CGF + runtime/quality.

**P8.02 — A topic model is "identified for policy corpora" only with a declared identification basis +
permutation-invariant stability + document-level semantic validity + an authority boundary (200).** anchor/
separable vs anchor-free-second-order vs supervised-transfer; unsupervised topics are exploratory-only unless a
taxonomy/human bridge upgrades them; boilerplate coherence ≠ policy concepts; `K` lives in the uncertainty
envelope, never a hidden constant. *Verdict: ADOPT the identification-basis discipline ([[M23]] exploratory-vs-
measurement).* `producer_missing` / `implemented_but_not_orchestrated` — reuse the `foundry.calibration`
identifiability-certificate pattern, not an absent topic-model owner. Routes to Foundry-subordination /
Scientist measurement plane.

**P8.03 — Text-derived variables enter a causal pipeline only as a certified measurement model, never as
self-standing authority (201).** Six simultaneous obligations: ex-ante construct statement; temporality +
leakage firewall (no post-treatment / treatment-predictive / prompt signal); frozen coder + separate
discovery/estimation split (discover the coding function ≠ estimate the effect on the same sample);
gold-standard correction (DSL / prediction-powered inference — 80–90% surrogate accuracy is **not** a causal
certificate); measurement invariance/drift; prompt-artifact robustness. *Verdict: ADOPT-CANDIDATE — reinforces
[[M19]] (leakage/split discipline), [[M17]] (validity by decision structure), and [[M23]] (uncorrected
surrogate → screening-only).* `bridge_missing`. Routes to Foundry validation + runtime/quality; Scientist
consumer.

**P8.04 — Calibrated RAG citations = a two-level protocol (edge support/scope/contradiction within retrieved
context ⊥ claim-level emission-vs-abstention), never one "confidence" (202).** Unit = atomic claim / sentence
edge ([[M20]]); reuse the repo label family; calibrate `p_nonblocking` and `p_full_support` separately, and
`retrieval_coverage` as its **own** calibrated claim; a retrieval miss is *not* proven absence of support
(anti search-laundering, our P25); selective abstention is the default for public/legal claims. *Verdict:
ADOPT-CANDIDATE ([[M21]] + [[M23]]).* `bridge_missing`. Routes to runtime/quality + scientist/validation +
Atlas DS9/DS12.

**P8.05 — Statutory reasoning needs a legal-reasoning certificate (norm-binding + temporal competence +
amendment lineage + argument/warrant/rebuttal), NOT a generic proof-carrying-analytics record (203).** The repo
already separates the GL legal-mandate family from G3 proof-carrying analytics; `assurance_case.py`'s SACM/CAE/
GSN claim→argument→warrant→rebuttal→counter_evidence→deficit graph is the ready consumer (this **confirms the
R8 memory note** that SACM/GSN/CAE already live in `assurance_case.py`); context ≠ authority; an LLM legal
summary stays candidate until Lex validates. *Verdict: ADOPT-CANDIDATE ([[M21]]).* `bridge_missing` — Lex +
runtime/quality seeds exist, no unifying certificate. Routes to the Lex lane + runtime/quality assurance_case
+ GY grounding.

**P8.06 — A remote-sensing proxy is "bias-corrected enough" only for a declared claim × strata × decision-mode,
gated by independent validation + calibrated uncertainty + an explicit area-of-applicability + decision-
preservation + mode-separation (205).** "high correlation + low average bias" is the refused simple formula;
outside predictor support → abstain (CV error does not transfer); test decision-flip / under-allocation *per
stratum*, not aggregate fit; monitoring < allocation < eligibility in barrier height. *Verdict: ADOPT-CANDIDATE
([[M23]] AOA + [[M17]] decision-preservation).* Reuses `foundry.calibration` measurement-aware weighting +
calibration diagnostics. Routes to Fabric quality + IR analytics + runtime/quality.

**P8.07 — Multimodal common-unit fusion = a support-certified, uncertainty-carrying, disagreement-preserving
authority record; certify support BEFORE any fused value (206).** Two stages: support certification (same unit
+ geography support + time support) *then* fused estimation as a separate claim; a **disagreement ledger** lives
*beside* the fused estimate (conflict is authority-bearing, never dissolved — [[M14]]); uncertainty must
**widen** with probabilistic linkage / areal transfer, never shrink ([[M23]]). Reuse existing IR seeds:
`alignment_certification` (`VariableAlignmentCertificate`), `latent_bridge_synthesis`,
`administrative_missingness`, `uncertainty.CompositionProvenance`, `evidence_bundle`; STAC / PROV-O / GSGF
external anchors. *Verdict: ADOPT-CANDIDATE ([[M22]] two-gate + [[M23]]).* `bridge_missing` — seeds exist, no
orchestrated bridge. Routes to `runtime/quality/ir_analytics_bridge.py`.

**P8.08 — Geoprivacy at the aggregation level = a DUAL admission (Disclosure-Risk Gate ⊥ Aggregation-Validity
Gate); a privacy pass is not a semantic pass (209).** Evaluate the whole release **graph** (non-nested
differencing, overlapping polygons, query-builder surfaces), not one table; suppression-only fails on
non-nested geographies; MAUP / ecological-fallacy flips are a *separate* validity failure even after DP. Reuse
`foundry.methods.catalog.spatial.MAUPSensitivityProfileEstimator` + `DependenceStructure` + IR
`DPRobustnessCertificate`. *Verdict: ADOPT-CANDIDATE ([[M22]] orthogonal gates + [[M24]] release-graph-wide).*
`bridge_missing`. Routes to Fabric/spatial + runtime/quality; the direct instance of failure-pattern **P19
aggregation-laundering**.

**P8.09 — Change detection carries causal semantics only as a typed environment-contrast + shift-classification
certificate, never as proof of effect (207).** Three steps: environment proposal → semantic typing {selection-
only / structural / mixed-or-latent / ambiguous / uninformative} → controlled admission; **kill rule**: a
boundary chosen as a function of the outcome invalidates causal semantics ([[M24]] no target-dependent split);
mixed-or-latent → route to latent-aware discovery, not contraction (honest-indeterminate, [[M14]]).
*Verdict: ADOPT the attachment discipline — but REINFORCES-EXISTING strongly:* `ir.analytics.invariance`
(`RegimeShiftIdentificationCertificate`) + Foundry causal catalog (`invariance_tests` / `pcmci_discovery` /
`dynamic_graph_dscm` / `local_independence_id`) **already implement this** — `implemented_but_not_orchestrated`
+ `bridge_missing`, so *wire, don't build*. Routes to runtime/quality + the GY causal engine.

**P8.10 — OPE under partial identification returns an identification ENVELOPE, not a scalar; a point estimate
only in the point-ID branch (208).** Triage by identification conditions {overlap / hidden-confounding /
proximal / worst-case}; the identified-set width ≠ a sampling CI (Imbens–Manski); decide by baseline-relative
dominance (lower bound vs threshold, not midpoint). *Verdict: ADOPT-CANDIDATE ([[M22]] triage + [[M23]] set-
valued) — REINFORCES-EXISTING:* `ir.analytics.partial_identification` already ships Manski / IV / MTR / MIV /
MTS / intersection-bounds / Imbens–Manski / Rosenbaum, and `foundry…causal_rl.OffPolicyEvaluator` is the
point-ID seed — wire the two branches. `bridge_missing`. Routes to Foundry causal + runtime/quality + GY
causal engine.

**P8.11 — Fairness in contextual bandits = a typed fairness profile selecting one of several incompatible
semantics, not a "fair" flag (210).** {merit / service-floor / exposure-parity / outcome-equity / α-fair},
with comparison-scope + temporal-scope + constraint-hardness + evidence-basis as load-bearing fields; the
narrow default is a *constrained bandit with pessimistic fairness accounting*, with merit / exact-parity as
opt-in governed profiles; the biased-proxy reward, hidden infeasibility, and fairness-specific adversarial
attack are the counterexamples. *Verdict: ADOPT the typed-profile discipline ([[M22]] regime-classifier +
[[M24]] temporal-scope).* `bridge_missing` — causal-fairness IR + `policy_learning` seeds exist. Routes to
Foundry causal + runtime/quality.

**P8.12 — Adaptive RCTs preserve valid post-experiment inference only via a logged adaptation ledger + an
inference family matched to the adaptation type + an explicit authority boundary (211).** Three gates: design-
replay → backend-selection (adaptive-weighted AIPW / batched BOLS / confidence-sequence for optional stopping /
selective-randomization for adaptive target-selection / last-batch-only fallback) → authority boundary; a
fixed-horizon CI after peeking is invalid; the selection event must be conditioned-on or firewalled ([[M19]]).
Reuse `foundry…causal` `conformal_ci` + `causal_rl` + `ir.analytics.dynamic_regime`/`interference` seeds.
*Verdict: ADOPT-CANDIDATE ([[M22]] backend-triage + [[M19]]).* `bridge_missing`. Routes to runtime/quality + GY
causal.

**P8.13 — Safe-RL requires a typed QUARTET of violation bounds; a weak average is not a safety certificate
(212).** final-policy feasibility + strong *no-cancellation* cumulative \(V^+_K\) + step-wise/anytime +
tail-risk (chance / CVaR); the cancellation trap (violate early, "compensate" later, pass a weak average) and
the rare-catastrophe tail are mandatory falsifiers; expectation-only `may_not_use_for` process/tail claims.
Reuse `foundry.agent_sim` PPO primitives + `constraints_engine` + `agent_sim.world` synthetic latent worlds.
**Actionable:** `FOUNDRY_REMEDIATION_PLAN` flags `agent_sim/rl.py` PPO advantage-normalization mixing active
and inactive agents — a safety-relevant defect that blocks promoting the RL seed until repaired (verify in
code; the report is untrusted). *Verdict: ADOPT-CANDIDATE ([[M24]] no-cancellation).*
`implemented_but_not_orchestrated` + `bridge_missing`. Routes to Foundry-subordination + GY causal.

**P8.14 — DTR under partial observability = a four-route authority gate {observed-Markov / belief-state /
proxy-identifiable / nonidentifiable-ambiguous}, each with a different authority ceiling (213).** Never
silently retrofit hidden state into a no-hidden-confounding DTR/OPE (exactly what `dtr.py` / `causal_rl.py`
assume via `sequential_ignorability` / `no_hidden_confounders`); OPE under partial observability can be
arbitrarily biased; nonidentifiable → ambiguity set / pessimistic window / acquisition plan, not a best regime;
the proxy route needs bridge-solvability diagnostics. The frontier method `causal.proximal.proximal_bridge@1.0.0`
**exists but is not orchestrated into the DTR path** (an engineering blocker, not an open research problem).
Reuse `agent_sim.world` for the partially-observed fixtures. *Verdict: ADOPT-CANDIDATE ([[M22]] route-
classifier + [[M23]] ambiguity-set).* `bridge_missing` + `semantic_test_missing`. Routes to runtime/quality +
GY causal.

---

## §2·F Per-report distillation — Batch 6 (Foundry Phase 9, P9.01–P9.14)

Phase 9 is Foundry's **applied estimation / mechanism-design frontier**: energy/carbon accounting (P9.01),
confidential computing (P9.02), macro-econometric identification (P9.03–06), evidence synthesis (P9.07–10),
market/mechanism design (P9.11–14). Two signatures. First, Phase 9 mostly **reinforces** the existing moves —
almost every report lands on [[M22]] (triage / identify-first) + [[M23]] (set-valued under non-identification)
+ [[M15]] (claim-type separation), and every one self-caps at `accepted_narrow_scope` + `bridge_missing` over
a *named existing repo seed* (so the work is wire/extend, not build-new). Second, it adds two genuinely new
moves — [[M25]] (vintage/as-of + append-only delta) and [[M26]] (impossibility-scoped claims). Same
caution as Phase 8: ~14 more candidate certificate types (see §4).

**P9.01 — Energy/carbon is a multi-resource estimation-cost ENVELOPE on one declared functional unit, never a
"carbon number" (214).** Separate typed fields for physical energy, location-based vs market-based operational
carbon, embodied carbon, marginal (decision-use-only) carbon, and a monetary shadow price (derivative-only,
own provenance); missing embodied = **null not zero**; heuristic/TDP fallback ≠ measured (fail-closed status).
Reuse `foundry.methods.selection.cost_model.CostEstimate` (already first-class w/ `resource_vector`),
`runtime/quality/cost_gate.py` + ADR-0164, `foundry.welfare.social_weight_provenance` (fact-vs-value split).
*Verdict: ADOPT-CANDIDATE ([[M16]] vector-not-scalar + [[M11]] axis non-collapse).* `bridge_missing`. Routes
to GY value engine + Atlas DS16 + Foundry-subordination. (SCI / GHG-Protocol dual-reporting external; OMB
M-25-15 currency note reaffirmed — don't cite 2023 A-4.)

**P9.02 — TEE evidence sufficient for a confidential-computing claim = the full RATS appraisal chain, never a
signed quote alone (215).** Evidence + Endorsements + Reference Values + Appraisal Policy + Attestation Result
+ claim-specific binding + freshness/nonce; the signed quote is verifier *input*, not proof; sufficient only
for narrow claims (genuine platform, approved launch state, TCB-in-policy, secret-release-to-instance), **not**
runtime confidentiality / side-channel immunity / legal compliance; a one-shot attestation → launch-bounded
downgrade; multiple verifier tokens from one quote lineage = one evidence line ([[M3]]). Reuse
`ir.analytics.alignment_certification`, `pdc.AuthorityBoundary`; the bridge belongs in `runtime/quality`.
*Verdict: ADOPT-CANDIDATE (extends [[M21]] to attestation chains + freshness).* `bridge_missing` /
`surface_missing`. Routes to runtime/quality + a future confidential-compute lane.

**P9.05 — Mixed-frequency nowcasting treats the ragged edge as vintage-aware missingness at the highest
frequency, never dataset "balancing" (216).** Route by structure ([[M22]]): DFM state-space default for large
panels / MF-VAR for small systems / Factor-MIDAS fallback; forward-fill and vertical realignment are semantic
leaks; output = backcast/nowcast/forecast + news-decomposition + vintage id, and revision-from-new-data must
be separable from revision-from-re-estimation. Reuse `foundry.methods.catalog.econometrics` (ARIMA/VAR seeds);
`TimeSeriesData` cannot express ragged edge → needs a new vintage contract, else **fail-closed, never silently
coerce** into a dense array. *Verdict: ADOPT-CANDIDATE ([[M22]] + [[M25]]).* `bridge_missing`. Routes to
Foundry-subordination + GY value engine.

**P9.06 — Structural model averaging weights by identification strength via gate → reliability → utility,
never raw posterior / inverse-variance weights (217).** Admissibility class {identified_admissible /
identified_limited / set_identified_or_ambiguous / non_identified_blocked} first; then a *calibrated* per-family
reliability factor (an F-stat of 12 and a Hessian min-eigenvalue of 1e-4 are **not** raw-comparable — map each
family's diagnostics to a common scale first); then a utility/stacking score. Never point-average across
authority classes; set-identified → ambiguity envelope, not a point weight; weak-IV + a naive prior yields a
misleadingly sharp posterior that steals weight. Reuse `foundry.calibration.identifiability`,
`foundry.uncertainty.aggregator`, `econometrics.iv` weak-IV, `consensus.py`. *Verdict: ADOPT-CANDIDATE
([[M22]] + [[M23]]; stacking over naive BMA in the M-open world).* Routes to GY value engine + Foundry-subordination.

**P9.03 — HANK identification evidence = a six-layer joint micro–macro packet; aggregate fit ≠ identification
(218).** Structural mapping + steady-state micro evidence (wealth/liquidity distribution, MPC — the
liquid-vs-total-wealth trap) + dynamic aggregate + distributional dynamics + formal rank/curvature/profile
diagnostics + honest uncertainty; a calibrated-by-convenience steady-state block must be flagged
`calibrated_not_estimated`, never projected as identified; without micro evidence the household block caps at
`partially_identified`. **Actionable — independently confirms a prior finding:** the measurement-aware loss
adapter already drops `identification_mode` (`del targets, identification_mode`) — the same P6.13 defect,
now re-confirmed from a second angle. Reuse `IdentificationMode` / `IdentifiabilityStatus` +
`causal_statistical_validity_report` template. *Verdict: ADOPT-CANDIDATE ([[M22]] + [[M23]] + [[M17]]).*
`bridge_missing`.

**P9.04 — DSGE robust priors + structural breaks reported as six authority-separated claims; priors are
load-bearing, breaks are first-class (219).** A robust prior = a *class/set* + local & global sensitivity +
"a conclusion is robust only if sign/order survives the admitted prior set" — not one baseline hyperparameter
vector; the break family is declared {none / fixed / unknown-date / regime-switching / SV / TVP} + where it
enters + a predictive-density comparison; an unmodeled break is a limitation, never a silent default; heuristic
Hessian ≠ certified posterior. Reuse `ir.analytics.calibration.literature_priors` + the
`runtime.quality.calibration_ledger` historical-prior firewall (its named test
`test_historical_prior_refs_fail_claim_registry_evidence_slots` is the ready model to emulate). *Verdict:
ADOPT-CANDIDATE ([[M16]] class-not-vector + [[M12]]).* `bridge_missing`; Bayesian calibration is
repo-self-labelled research-gated (no production posterior sampler).

**P9.07 — Bayesian NMA includes transportability as a separate target-population standardization layer + a
transportability certificate, never "another prior" (220).** ML-NMR (multilevel network meta-regression) as
the narrow default: model effect modifiers at the individual level, integrate the AgD likelihood over covariate
distributions, standardize to the decision target population; keep marginal vs conditional estimands distinct
on non-collapsible scales; weak overlap / missing effect modifier / unanchored network → bounds/sensitivity/block,
not bolder averaging. Reuse `ir.analytics.transportability` (SelectionDiagram / TransportabilityStatus /
TransportabilityResult) — the contract carrier already exists. *Verdict: ADOPT-CANDIDATE ([[M22]] + [[M23]]).*
`bridge_missing`.

**P9.08 — Publication bias is corrected by a bias-adjusted effect ENSEMBLE; calibrated power is a
diagnostic/calibration layer, not a standalone corrector (221).** Two separated bundles: power-calibrated
diagnostics (z-curve 2.0 EDR/ERR/ODR + excess-significance TESS/PSST) answer *is there selection and how deep*;
an effect-correction ensemble (selection models + PET-PEESE + RoBMA model-averaging + p-uniform* sensitivity)
does the correction; low replication ≠ publication bias; small-k → all diagnostics unstable. Reuse
`econometrics.selection.HeckmanSelectionEstimator` (selection-mechanics seed, but at sample not publication
level), `ir.analytics.literature` (RoB / EvidenceStrength / LiteratureEdgePrior), calibration_diagnostics →
TruthfulnessReceipt. *Verdict: ADOPT-CANDIDATE (calibrated-power `authoritative_for` diagnostics,
`may_not_use_for` standalone correction; [[M15]] + [[M12]]).* `bridge_missing`.

**P9.09 — A living-review update is safe only as an append-only evidence-delta transaction with six separated
claims; a new source is not stronger evidence (222).** surveillance ≠ inclusion/protocol ≠ claim-impact ≠
certainty ≠ reproducibility ≠ admissibility; the baseline is immutable, each update emits a delta
(protocol-diff / source-diff / certainty-diff / replay refs / validity action); dedupe preprint↔journal↔news
to hold the independence count; retrospective protocol narrowing after an inconvenient result = block.
**Strong reuse:** the Scientist deep-research stack (append-only claim ledger, research-DAG replay/invalidation,
continuous-governance statuses valid/monitoring/stale/review_required/reissued/withdrawn). *Verdict:
ADOPT-CANDIDATE ([[M25]] append-only delta; recency ≠ strength).* `implemented_but_not_orchestrated` +
`bridge_missing`. Routes to Scientist governance + GY-N12.

**P9.10 — Meta-transportability across K sites = identify-first (multi-source selection diagram / mZ-ID) then
site-admissible DR estimation then EIF-combination; NOT meta-analysis over sites (223).** An effect can be
non-transportable from every single site yet identified from a *combination* (the "pairwise trap" — a
site-by-site intersection wrongly returns `unsupported`); precision (inverse-EIF-variance) weighting is
admissible **only after** identification + estimand alignment (else "precision laundering" lets the narrowest
variance beat the correct causal model); positivity holes → bounds/sensitivity; unexplained site heterogeneity
→ downgrade, not just a wider CI. Reuse `causal.fusion.data_fusion@1.0.0` (`multi_study_fusion` mZ-ID,
`optimal_data_combination` EIF-variance weighting) + `MultiSourceSelectionDiagram` — the seeds are implemented.
*Verdict: ADOPT-CANDIDATE ([[M22]] + [[M23]]).* `implemented_but_not_orchestrated` + `bridge_missing`.

**P9.12 — Two-sided matching elicits a typed acceptability-first preference surface, not "full true preferences
of both sides", and declares its strategic principal (224).** Four layers {acceptability / coarse ordinal
tiers / targeted pairwise refinement / outside-option}; support incomplete/incomparable preferences (forcing a
full strict order is a bad default); declared preferences ≠ inferred latent preferences (inferred =
estimation-only with its own calibration + uncertainty). By the Roth impossibility there is no bilateral
truthfulness — pick the proposer side and state the negative scope. Reuse `mechanism.runtime.labor_market@1.0.0`,
`ir.analytics.mechanism_design`, `ir.analytics.strategic`. *Verdict: ADOPT-CANDIDATE ([[M26]]
impossibility-scoped + [[M22]]).* `bridge_missing`.

**P9.13 — Public-sector combinatorial-auction welfare loss is a decomposed interval, never a scalar; the zero
component must be earned (225).** λ_upper ≤ λ_opt + λ_expr + λ_strat + λ_unc, each with a *different* admissible
source; λ_opt (a solver certificate) is cheap; **λ_strat = unbounded by default** unless a truthfulness bridge
is proven; λ_expr = unknown unless the bid-language restriction is auditable; "mip_gap ≈ 0" is NOT a
welfare-loss bound; the normative welfare-functional choice stays a separate value-choice record. Reuse
`foundry.welfare` frontier emitter (`assert_welfare_publication_not_scalar_only`) + `social_weight_provenance`
(LLM-origin fail-closed) — both already enforce the fact-vs-value split. *Verdict: ADOPT-CANDIDATE ([[M16]] +
[[M12]] — the reassuring λ=0 carries the burden of proof).* `bridge_missing`.

**P9.14 — Platform regulation = a bounded composite mechanism-design contract, not one welfare-maximizing
planner (226).** Typed actors {regulator / platform / business-users / end-users / auditor}, a typed incentive
map (never one representative-agent objective), three observable rings (authoritative / derived / research-only
latent), levers restricted to what is auditable + enforceable (DSA/DMA-shaped), and an equilibrium *ladder*
{Stackelberg leader / finite-game / mean-field / blocked} with exactness certificates gating `exact` vs
`strategic_bounds`. Reuse `ir.analytics.mechanism_design` + `ir.analytics.strategic` (fallback modes) +
`policy.agent_sim.mean_field_equilibrium@1.0.0`. *Verdict: ADOPT-CANDIDATE ([[M22]] regime ladder; [[M17]]
validity by governance structure).* `bridge_missing` + `semantic_test_missing`.

**P9.11 — Deferred acceptance exposes strategy-proofness as a side-scoped, domain-conditional theorem
certificate with a provable negative region — never a boolean `is_strategy_proof` (228).** Proposer-side +
classical domain only earns `exact`; large-market → `asymptotic` (SP-L); finite misreport search →
`approximate_calibrated`; couples / distributional constraints / report-dependent tie-breaking → block;
mandatory `may_not_use_for` {receiver-side truthfulness, welfare, fairness, legal admissibility, participant
comprehension}. Reuse `core.observability.truthfulness.TruthfulnessReceipt` (exact / asymptotic /
approximate_calibrated / unverified) as the coarse downgrade signal + the `causal.strategic` authority pattern.
*Verdict: ADOPT-CANDIDATE ([[M26]] impossibility-scoped; Roth/Dubins–Freedman asymmetry).* `producer_missing`
(no DA owner in the repo).

---

## §2·G Per-report distillation — Batch 7 (Foundry Phase 10, P10.01–P10.16)

Phase 10 — the largest batch (16) — is Foundry's **advanced numerical/statistical-methods frontier**:
optimization theory (P10.01, P10.16), stochastics (P10.02, P10.04, P10.06, P10.15), survival/event history
(P10.05, P10.07, P10.08), topological/geometric ML (P10.09–11), and applied policy detection (P10.03, P10.12,
P10.13, P10.14). It overwhelmingly **reinforces** the regime-triage discipline ([[M22]]/[[M17]]) and set-valued
honesty ([[M23]]), and adds two new moves: [[M27]] (representation-conditioned descriptors — the ML-shape
cluster) and [[M28]] (a-posteriori bound in decision units, not a convergence flag). Same certificate-
proliferation caution as Phases 8–9 (see §4).

**P10.01 — Multilevel policy optimization is a regime-classified admissibility decision, not "solve exactly
by default" (227).** Exact only for certified classes (LP/MILP-moderate, bilevel-linear via KKT/duality,
multilevel-MILP branch-and-cut); relaxation only with certified tightness or a reported gap; decomposition
only with separability + valid bounds/cuts; bilevel reduction only *level-by-level* with an equivalence proof;
robust bounding as the safe fallback for strategic/nonunique lower levels; abstention otherwise. Reuse
`foundry…optimization` (`OptimizationAmbiguityCertificate`, `AmbiguityCertificate` w/ price_of_ambiguity) —
`BilevelOptimizationEstimator@1.1.0` **already** returns leader-objective bounds and honestly abstains.
*Verdict: ADOPT-CANDIDATE ([[M22]] + [[M23]] + [[M28]]).* `implemented_but_not_orchestrated` + `bridge_missing`.

**P10.02 — Mean-field convergence needs a *split* finite-N correction stack, not one "safety factor" (229).**
Four separate corrections keyed to the claim: εN-Nash bound (∼C/√N) for incentive/admissibility, √N
fluctuation envelope for measure/trajectory, no-common-noise concentration for tails (common noise →
`conditional_only`), optional 1/N weak-bias only for smooth aggregates; nonunique/phase-selection → block, not
"add a 1/√N band." Reuse `policy.agent_sim.mean_field_equilibrium@1.0.0` + IR `EPSILON_NASH` — but εN is a
static 0.05 today, not an evidence-backed bound ([[M28]]). *Verdict: ADOPT-CANDIDATE ([[M22]] + [[M23]]).*
`implemented_but_not_orchestrated`.

**P10.07 — Deep survival models expose a *separate* interval artifact typed by what is bounded, not a lower/
upper field on `SurvivalResult` (230).** Three claim families {horizon-risk / event-time-set / survival-curve-
band}, each with its own coverage semantics; "calibrated" = empirical predictive coverage under a *named
censoring regime* (conformal), NOT a Hessian/Laplace parameter envelope; pointwise ≠ simultaneous bands (a
whole-curve claim from stitched pointwise intervals is a kill rule); D-calibration pass ≠ interval authority.
Reuse `ml/protocols.PredictionIntervalResult` for scalar horizon-risk only. *Verdict: ADOPT-CANDIDATE ([[M22]]
+ [[M27]] observation-regime as load-bearing).* `bridge_missing`.

**P10.03 — Coupled mechanisms / correlated equilibria = separate certification layers, not one "certified"
enum (231).** semantics (CE for finite complete-info / BCE for type-mediated / coupled-envelope for shared-
constraint) ⊥ existence ⊥ witness ⊥ multiplicity ⊥ ambiguity ⊥ calibration ⊥ policy-disposition; existence ≠
"solver didn't fail" ([[M12]]); multiplicity is load-bearing (uniqueness must be *proved*, else welfare
interval); a regret-matching/learning trace is empirical support, never an exact witness ([[M28]] hierarchy).
Reuse four recognizable repo patterns: `IncentiveCompatibilityCertificate`, `NegativeCertificate`,
`ProofComposabilityCertificate` (reusable/revalidate/rederive), `simulation_proof_bridge` (IDENTIFIED/BOUNDED/
SCENARIO/BLOCKED). *Verdict: ADOPT-CANDIDATE ([[M22]] + [[M28]]).* `bridge_missing`.

**P10.04 — Hawkes/self-exciting processes carry policy events as a measurement-rooted, marked, multivariate
point-process, with narrow descriptive authority — never causal (232).** Raw event log (exact times + marks +
jurisdiction/actor + exogenous-baseline + batching/dedup) is canonical; the binned panel is a *derived view*;
`authoritative_for` intensity/excitation/clustering/short-horizon-risk, `may_not_use_for` causal-self-excitation
/ welfare / publication. The killer counterexample is reporting-lag/calendar-batch → false contagion — the
observation process must be modeled ([[M27]]). Reuse IR `TemporalDiscoveryMethod.HAWKES` +
`EventProcessObservationalData` + `LocalIndependenceWeightingCertificate`. *Verdict: ADOPT-CANDIDATE ([[M27]]).*
`bridge_missing`.

**P10.05 — Competing risks / recurrent events = an estimand→estimator rulebook, not one "event-history
estimator" (233).** competing risks → Aalen–Johansen CIF (treating a competing event as censoring
over-estimates incidence) + cause-specific Cox; Fine–Gray opt-in prediction-only (summing multiple Fine–Gray
CIFs can exceed 1); recurrent → mean-cumulative-function, then AG (pooled intensity) / PWP (order matters) /
WLW (marginal only); recurrent+terminal → while-alive burden, joint-frailty research-only; informative
censoring must not be silently assumed independent. Reuse `ml.survival` (Cox seed; no CIF/MCF fields yet).
*Verdict: ADOPT-CANDIDATE ([[M22]] + [[M17]]).* `bridge_missing`.

**P10.06 — Marked spatio-temporal events = a bounded-window event-law via conditional intensity, family-routed
by question (234).** (t, s, m) tuples with a marked conditional intensity, never tabular features; route by
question — Hawkes/ETAS (contagion) / LGCP (latent background) / local-independence (intervention) — and don't
mix their claim semantics; observation-process failures (reporting lag, MAUP/discretization, post-event marks)
are the adversaries. Strong reuse: IR `dynamic_regime` (SUPPORTED/DEGRADED/BLOCKED_RESEARCH) +
`local_independence` (process_family: marked_point_process) already own the semantics; the `spatial` catalog
(Moran's I / kriging / IDW) has no STPP producer. *Verdict: ADOPT-CANDIDATE ([[M27]] + [[M22]]).* `bridge_missing`.

**P10.08 — Longitudinal policy outcomes = a typed trajectory bundle with an explicit *named functional*, never
a scalar / basis blob / bare curve (235).** path ≠ functional (same trajectory → integral / crossing-time /
time-above-threshold / welfare-path); basis/FPCA/signature coefficients are engineering sidecars, not a
publication surface; whole-curve claims need *simultaneous* bands; informative visit processes must downgrade
or block. Strong reuse: IR `EffectTrajectoryBundle` + `RoughPathInterventionCertificate` + `TemporalTargetFunctional`
are shape-parallel — extend, don't reinvent. *Verdict: ADOPT-CANDIDATE ([[M27]] + [[M16]]).*
`implemented_but_not_orchestrated` + `bridge_missing`.

**P10.09 — Persistent homology describes the shape of the *chosen representation*, not "the shape of policy"
(236).** A typed, representation-conditioned, multiscale structural descriptor: `authoritative_for` structural
patterns / anomaly-disparity candidates under a *declared* embedding+metric+filtration; `may_not_use_for`
causal / welfare / legal / publication claims; the "false donut" (an H1 loop that is really administrative
missingness / masking) is the mandatory counterexample; long bars ≠ signal without a confidence/noise-
separation layer. Reuse `DependenceStructure` + `ir_analytics_bridge`; GUDHI/Ripser/persim are permissive,
giotto-tda is AGPL. *Verdict: ADOPT-CANDIDATE ([[M27]]).* `producer_missing`.

**P10.10 — Manifold learning is "causally faithful enough" only as causal-supporting, never causal-defining
(237).** Requires a declared identifiability basis beyond unsupervised geometry (auxiliary vars / environments /
interventions — Locatello impossibility, nonlinear-ICA identifiability), a causal falsification pack (invariance,
counterfactual/effect-drift, recoverability, residual-dependence), an explicit uncertainty envelope, and a
narrow ceiling (`nuisance_only` / `adjustment_candidate`); geometry-good ≠ causal-good, and auto-relabeling
opaque latent axes is a blocker. Strong reuse: `ir.representation_learning` (research_gate_required,
decision_support_allowed=False), `network/embedding_fidelity`, `latent_bridge_synthesis` (opaque_label_required).
*Verdict: ADOPT-CANDIDATE ([[M27]]).* `bridge_missing`.

**P10.11 — Geometric deep learning on administrative graphs is a candidate estimation layer only, gated by the
observation mechanism (238).** Lift to a *typed* administrative graph (node/edge type, time validity,
provenance, structural-missing + confirmed-absence masks, linkage quality) and run `administrative_missingness`
/ `network.missingness` *before* the learner; the killer case is observability ≠ need (a better-digitized
municipality looks higher-risk); default to R-GCN/HGT (not vanilla GCN, which fails under institutional
heterophily), require graph-specific + subgroup/local calibration, and forbid eligibility/sanction/publication
use. Reuse `ml.graph.graph_conv@1.0.0` (baseline-only) + the missingness + embedding-fidelity seeds. *Verdict:
ADOPT-CANDIDATE ([[M27]] + [[M17]]).* `implemented_but_not_orchestrated`.

**P10.12 — Benefit-abuse detection balances causal fairness *lexicographically*, not via one aggregated score
(239).** A four-loop protocol: causal-fairness decomposition (TV = DE + IE + SE; distinguish prohibited-direct /
spurious-surveillance / legitimately-mediated paths) → an *explicit welfare ledger* (no hidden social-weight
laundering) → performative/strategic response (a gate, not an appendix — chilling/non-take-up) → slice-aware
calibration/uncertainty; blocked causal harms and uncovered uncertainty come *first*, then a frontier, then a
separate governance admissibility decision. Reuse `causal.fairness@1.0.0` (SFM + Ctf-DE/IE/SE + partial-ID
bounds), `sufficient_statistics_welfare` (social_weight_ref), `social_weight_provenance` (LLM fail-closed),
`causal.strategic`. *Verdict: ADOPT-CANDIDATE (reinforces [[M7]]/[[M13]] fact-vs-value + [[M23]]).* `bridge_missing`.

**P10.13 — Adaptive audit sampling exposes detection *bounds* — a miss/detection curve — not one confidence
score (240).** Two mutually-invertible authority curves (miss-prob upper / detection-prob lower) for a declared
tolerable rate, plus `minimum_detectable_rate`, under a *logged* without-replacement sampling policy; only exact
hypergeometric/sequential or anytime-valid e-process/confidence-sequence bounds are the proof layer (Monte-Carlo
power & historical calibration are calibration-only — [[M28]]); deterministic risk-targeting with zero inclusion
probability → subpopulation-only or blocked, never a population guarantee; peeking without anytime validity is a
kill rule. Reuse `ir.analytics.uncertainty` (deterministic_bounds) + `RobustSetCalibrationReport` +
`method_quality`. *Verdict: ADOPT-CANDIDATE ([[M28]] + [[M23]]).* `implemented_but_not_orchestrated`.

**P10.14 — Anomaly detection under drift updates as a *staged, fail-closed* authority chain — never a silent
auto-retrain on a drift score (241).** drift evidence → calibration evidence → uncertainty → replay/same-input
closure → admissibility; a *new drift score is not license to update* (recency ≠ authority — [[M25]]); typed
update actions {threshold-recalibrate / reference-window-refresh / dynamic-normal-update / retire-abstain} keyed
to whether score-ordering vs the notion-of-normal changed; a data-quality breach must precede and block, not be
absorbed as "new normal." Strong reuse: `polisyos.ddm` (`adapt_shift_event` fail-closed requires calibration_id
+ empirical-FP evidence; CBPE estimator requires calibrated probs; `evaluate_data_quality`) + recalibration.
*Verdict: ADOPT-CANDIDATE ([[M25]] + [[M22]]).* `bridge_missing`.

**P10.15 — Multivariate policy tail risk = a typed joint-exceedance object in outcome-metric space, never a
scalar risk score or univariate metadata (242).** A multivariate-GP / peaks-over-threshold law over a *declared
adverse region* of the policy-outcome vector, with an explicit extremal-dependence class (asymptotic dependence
vs independence vs hidden regular variation — a Gaussian-copula center hides crisis co-exceedances); default
estimator = Heffernan–Tawn conditional extremes (transfers to high dimension), graphical extremes for sparse
metric graphs; CoVaR/ES are downstream summaries, not the core object; early scalarization erases subgroup
vetoes. **Actionable seed note:** `foundry.uncertainty.monte_carlo` writes only *univariate* `tail_risk`
metadata (cvar_05 / quantile_01 / quantile_99) with an arithmetic-only test — don't mistake it for authority.
*Verdict: ADOPT-CANDIDATE ([[M16]] law-not-scalar + [[M22]]).* `bridge_missing` / `producer_missing`.

**P10.16 — Policy-function iteration needs a *regime-keyed* error certificate in policy-loss units, not one VFI
stop rule (243).** exact Howard PI → `not_applicable_exact_pfi` (evaluation is a fixed-point solve, no VFI bound
needed); VFI-extract-greedy → a Bellman-residual → policy-loss bound 2γ/(1−γ)²; approximate-PI → (ε_imp + 2γδ_eval)/
(1−γ)², sharpened to /(1−γ) *only* under a stabilized-policy proof; "it converged" / "values barely changed" is
not an admissibility claim, tie-breaking + finite precision are load-bearing, and late-iteration errors dominate.
**Actionable precision note:** the existing `optimization.dynamic.dynamic_programming@1.0.0` is *finite-horizon
staged DP*, NOT stationary discounted PI — the discounted (1−γ) bounds must not be applied to it mechanically.
*Verdict: ADOPT-CANDIDATE ([[M28]] + [[M17]]).* `implemented_but_not_orchestrated`.

---

## §2·H Per-report distillation — Batch 8 (Foundry Phase 11, P11.01–P11.15)

Phase 11 is Foundry's **composition / dispatch / cross-tool-reproducibility** tier, with several governance/
infra topics (whistleblower, judge-stack, R/Stata/Python replication). It heavily reinforces regime-triage
([[M22]]/[[M17]]) and set-valued honesty ([[M23]]), re-applies effective-independence ([[M3]]) to LLM-judge
panels, and adds two new moves: [[M29]] (compose by native operator, never scalar-sum; guard double-count &
veto-erasure) and [[M30]] (shared admission port + family-native payloads — the *constructive resolution* to the
certificate-proliferation risk).

**P11.01 — Geostatistical extremes are a regime-gated extremal-dependence workflow, not "spatial interpolation
of rare values" (244).** Estimate marginal tails and extremal *dependence class* separately; gate maxima →
max-stable / exceedances → generalized-Pareto-process / high-dim or ambiguous → conditional-extremes; a Gaussian-
process kriging surface (the tempting `gaussian_process_kriging` cousin) localizes extremes and gives NO joint
tail dependence — the dangerous false-neighbor; ambiguous class → research_only/block. Reuse
`foundry.methods.catalog.spatial` + `DependenceStructure` + `UncertaintyEnvelope`. *Verdict: ADOPT-CANDIDATE
([[M27]] + [[M22]]).* `producer_missing`.

**P11.02 — Whistleblower-safe infrastructure = five separate control loops, not "we have a channel" (245).**
{protected-intake / source-protection / anti-retaliation / independent-investigation / disclosure}, each with its
own owner + typed artifact + `authoritative_for`/`may_not_use_for` + fail-closed kill rules; the "anonymous
channel that only accepts identifiable corporate accounts" is the killer counterexample → `blocked` even if every
ticket field is green. Reuse runtime/quality governance modules (`consultation` judgement-not-data, `compliance`
PII fail-closed, `authority` no projection/fixture authority). *Verdict: ADOPT-CANDIDATE ([[M29]] role-separated
composition).* `bridge_missing` / `surface_missing`.

**P11.03 — Copula tail dependence supports policy scenarios only as a scenario-coupling primitive, never a policy
claim (246).** Same rank-dependence ≠ same tail dependence (Gaussian gives none, t gives symmetric joint extremes;
Gumbel=upper, Clayton=lower); tail-asymmetry and regime/time semantics are load-bearing fields; thin-tail sample
or family disagreement → research_only/block, not pseudo-precise λ-values. Reuse
`foundry.methods.catalog.dependence` + `econometrics.route_cross_sectional_dependence`. *Verdict: ADOPT-CANDIDATE
([[M22]] + [[M27]]).* `bridge_missing`.

**P11.04 — Scenario generation "proves coverage" only via five separated claims over a *declared denominator*
(247).** envelope-declaration (world family + factor schema + boundaries) → structural coverage (combinatorial
`t`-way + LHS for continuous — NOT run-count) → distributional calibration (`coverage_lcb` + empirical source) →
tail/boundary-challenge → balanced success+failure memory; raw-count inflation and space-filling-over-the-wrong-
semantic-model are the counterexamples; overall = weakest boundary, downgrades to `SCENARIO`/`BLOCKED`. Reuse
`foundry.agent_sim.world` (phase-0 seed worlds) + `RobustSetCalibrationReport` + `simulation_proof_bridge`.
*Verdict: ADOPT-CANDIDATE ([[M29]] + [[M28]]; balanced-memory reinforces the GY-P11 successes-not-just-failures
law).* `bridge_missing`.

**P11.05 — Worst fiscal scenarios compose as a NESTED protocol EVT → DRO → GE-feedback → risk-functional, each
with its own certificate (248).** Order matters: the exogenous-shock tail (EVT) and endogenous-amplification tail
(GE) are different claims — re-tailing GE output double-counts; a worst-case is authority-bearing only with
tail-cert ∧ ambiguity-cert ∧ equilibrium-cert; a "bad but locally-unstable" equilibrium must not be published as
inevitable; a GE fixed-point without *fiscal budget closure* is not fiscal admissibility. Reuse compile/execute
feedback (convergence/multiplicity certs) + policy frontier. *Verdict: ADOPT-CANDIDATE ([[M29]] the canonical
double-count guard).* `bridge_missing` + `producer_missing` (EVT/DRO).

**P11.06 — A dynamic game is "identified" only after a six-layer decomposition, never from a calibration fit
(249).** {game class / information structure / equilibrium concept / claimed primitives / exclusion-independence-
heterogeneity assumptions / point-set-selection-dependent-or-not}; multiplicity → identify only equilibrium-
*invariant* objects (selection_dependent/set_identified); persistent latent heterogeneity mimicking strategic
dynamics → blocked_evidence; incomplete-info without exclusion restrictions → at most set_identified. Do NOT fold
this into the symbolic causal-ID stack — it's structural econometrics. Reuse `ir.analytics.strategic` (static
seeds) + `foundry.calibration.identifiability`. *Verdict: ADOPT-CANDIDATE ([[M22]] + [[M23]]).* `bridge_missing`.

**P11.07 — Uncertainty in a VFI chain propagates as a chain of separate claims, not one CI (250).** primitive-
uncertainty → Bellman/solver certificate → policy-selection stability → occupancy/value → welfare → admissibility;
a Bellman residual gives a *solver-truncation* outer bound only (not primitive/calibration/admissibility);
approximate VFI needs separate truncation + approximation + discretization bounds; a narrow *value* band with a
small *action-gap* is NOT a stable policy — emit a `policy_gap_certificate` (`selection_contested`);
distributional-*control* is unstable (only policy-evaluation contracts), non-rectangular ambiguity ≠ robust-Bellman
support. Reuse `foundry.agent_sim.vfi.OfflineVFI` + `ir.analytics.uncertainty` (heuristics can't be gate-eligible).
*Verdict: ADOPT-CANDIDATE ([[M28]] + [[M23]] + [[M29]]).* `implemented_but_not_orchestrated` + `bridge_missing`.

**P11.08 — Discrete-continuous choice needs a task-specific estimator, not pure discrete-choice + an ad-hoc
two-part model (251).** Route by structure: MDCEV full-information ML as the frequentist default (Bayesian
research-gated — no production posterior sampler); escalate to flexible-MDCEV if participation/quantity margins
decouple, to MDCP/KT if cross-alternative covariance matters; a two-part model is `heuristic_baseline` only (no
welfare/substitution); outside-good & budget semantics and measurement truncation are load-bearing. Reuse
`econometrics.discrete_choice` (MNL/mixed-logit/BLP seeds). *Verdict: ADOPT-CANDIDATE ([[M22]] + [[M17]]).*
`producer_missing`.

**P11.09 — Bayesian diagnostics and safe BO share ONE authority surface but two non-interchangeable lanes (252).**
`retrospective_fit_authority` (PPC / PSIS-LOO / SBC / stacking — no single scalar; policy-sensitive multimodality
→ refuse single policy) ⊥ `prospective_search_authority` (GP-UCB regret + SafeOpt safe-seed + (ε,δ)-stopping —
misspecification turns sublinear regret linear, so it needs sentinels); never one "Bayesian trust score", never
active-search on fit diagnostics alone, never a regret-cert as model-adequacy. Reuse calibration diagnostics +
bayesian `pmd_hmc` + SearchExitContract; NO `bayesian_optimization`/`safeopt` producer. *Verdict: ADOPT-CANDIDATE
([[M29]] two-lane + [[M30]] shared surface).* retrospective = `implemented_but_not_orchestrated`; BO =
`producer_missing`; `bridge_missing`.

**P11.10 — Coherent forecast authority = five separate claims; combine at the distribution level, never
component-wise (253).** estimate / coherence-certificate / calibration / uncertainty / admissibility; ordinal →
RPS on cumulative CDF (not numericalized RMSE — cardinal laundering), continuous → pinball/WIS/CRPS with the score
family declared *ex ante*; no-arbitrage invariants (monotone CDF, non-crossing quantiles, nested intervals); **a
linear pool of calibrated forecasts is NOT calibrated (Ranjan–Gneiting) → mandatory post-combination
recalibration**; interval bundles need *conditional* coverage (Christoffersen), not just hit-rate; historical
calibration is influence, not current-run evidence. Reuse `ForecastingUncertaintyBundle` (monotone fan-chart seed)
+ `CausalModelEnsemble` + `calibration_ledger`. *Verdict: ADOPT-CANDIDATE ([[M29]] + [[M15]]).* `bridge_missing`
/ `producer_missing`.

**P11.11 — The econometric dispatcher is not one "LP or VAR" flag; MHT, top-coded wealth, and group deflators are
separate layers, never hidden knobs (254).** Fix the estimand first (LP/VAR share it, differ on bias-variance);
default LP-first-for-authority / VAR-as-benchmark; run confirmatory MHT via Romano–Wolf stepdown (not per-horizon
t-tests); treat top-coded wealth as a tail-coverage problem (Pareto/rich-list/bounds — raw top-codes = input
provenance only); publish a group-deflator sensitivity view whenever cross-group *real* comparisons are claimed.
Reuse `econometrics.timeseries` (ARIMA/VAR) + `foundry.calibration.fabric_quality`. *Verdict: ADOPT-CANDIDATE
([[M22]] + [[M29]] separate-layer composition).* VAR = `implemented_but_not_orchestrated`; LP/MHT/top-code/deflator
= `producer_missing`.

**P11.12 — Sequential public-decision value composes six typed sub-results by native operators, never a scalar
(255).** {intertemporal-welfare-envelope / continuation-option-delta-vs-*named-irreversible-baseline* /
allocation-feasibility-certificate / facility-fairness-frontier / dynamic-IC-certificate / composition-record};
option value added to continuation welfare that already optimizes it = double-count; a static IC cert for a
sequential mechanism checks the wrong strategy space → `abstain_dynamic_ic_mismatched`; fairness stays a frontier
absent reviewed social-weight provenance. Reuse `MethodComposer` + `frontier_emitter` + `social_weight_provenance`
+ `ir.mechanism_design`. *Verdict: ADOPT-CANDIDATE ([[M29]] the canonical statement).*
`implemented_but_not_orchestrated` + `bridge_missing`.

**P11.13 — Validated trajectory enclosures and motif-count uncertainty need SEPARATE family-native certificates,
admitted by ONE shared rule (256).** ODE → deterministic outer enclosure (Taylor-model remainder); SDE →
pathwise-or-coverage enclosure with adaptedness/filtration/no-future-leakage (a deterministic-looking interval on
SDE output is not a validated enclosure); motif-count → design-conditional interval (subgraph-sampling model is
load-bearing — an interval under one design is invalid under another). "Common port, not common theorem" — the
shared consumer checks same-input closure + typed uncertainty + family-native cert + authority boundary, the
payloads stay local. Reuse `RoughPathInterventionCertificate` + `proof_composability` (REUSABLE/REVALIDATE/
REDERIVE); network catalog has no motif owner. *Verdict: ADOPT-CANDIDATE ([[M30]] the canonical statement +
[[M27]]).* trajectory = `implemented_but_not_orchestrated`; motif = `bridge_missing`.

**P11.14 — A six-judge stack is meta-evaluated as a selective measurement instrument, not "six independent votes"
(257).** Two levels — seat diagnostics (prompt-stability / order-invariance / gold-agreement / calibration) and
stack diagnostics (chance-corrected agreement, Brier, risk-coverage w/ abstention, robustness, and
**`effective_independent_judge_count`** — nominal 6 without it is unsafe, [[M3]]); reliability ≠ validity (high
test-retest can coexist with strong position bias); on human-disagreement slices, calibration to majority vote is
wrong — score contested-item recognition + abstention. **Reuse the near-perfect template**
`foundry.validation.causal_validity` (`causal_statistical_validity_report`: offline benchmark contract, known-
answer/placebo/negative-control/missingness/uncertainty-calibration) + `agent_sim.world`. *Verdict: ADOPT-CANDIDATE
([[M3]] + [[M8]]).* `implemented_but_not_orchestrated` (bridge/consumer/surface/semantic-test missing).

**P11.15 — Foundry cross-toolchain replication = canonical estimator-spec + input-snapshot + language-native
lowerers + result-canonicalization + a parity certificate, never shared script text or coefficient-table identity
(258).** "Same formula ≠ same estimand": R `model.matrix`/`na.action`, statsmodels Patsy/`missing='none'`→NaN,
Stata factor-vars/`e(sample)`, and `sandwich` HC0–HC5 vs statsmodels `cov_type` vs Stata `vce()` differ on
design-matrix, missingness *mask*, and vcov/df — so parity must cover the *lowered* spec, the sample-mask hash,
and the vcov/df, not just coefficients; a lowerer that can't represent a slot exactly must fail-closed. **Strong
reuse:** `foundry.methods.equivalence.CrossBackendEquivalenceCertificate` (field-tolerance, strict/relaxed, signed,
`canonicalize_method_result`) is the seed — extend NumPy/JAX → R/Stata/Python; `ecosystem_bridges` is Python-only
today. *Verdict: ADOPT-CANDIDATE ([[M30]] + [[M27]] lowering-is-load-bearing).* `bridge_missing` +
`implemented_but_not_orchestrated`.

---

## §2·I Per-report distillation — Batch 9 (Cross-cutting Public Authority, CPA-R1–R17)

The CPA tier is **not** an engine tier; it is the public-authority admissibility layer. All 17 reports share one
template and one meta-conclusion — the seven-axis non-collapse ([[M31]]) — applied to a different question each.
Almost every report self-labels `implemented_but_not_orchestrated` + `surface_missing`: the repo already owns the
primitives (`AuthorityBoundary`, `capability_authority`, `participation_requirement`, `evidence.PolicyConflictRecord`,
`graded_outcomes`, `human_review`, `institutional_provenance`, `core.audit`) but has **no single cross-cutting
public-authority producer/surface**. So this batch is overwhelmingly *reuse-first wiring guidance*, not new
capability — and its ~17 proposed records are the sharpest test yet of the [[M30]] shared-port discipline.

**CPA-R1 — Mandate-admissibility precheck: three core prongs (goal-mandate ∧ intervention-authority ∧
decision-forum), fail-closed (259).** A typed `mandate_admissibility_record` that answers *only* "does this design
objective have a valid authority envelope for further design" — not "is the goal true." Any core prong ≠ `pass`
⇒ `blocked`; core pass + transparency/contestability deficit ⇒ at most `limited`. Reuses S6/S7/S8 posture inputs
(`mandate_record_ref`, `delegation_contract_ref`, `decision_rights_matrix_ref`) already present. *Verdict:
ADOPT-CANDIDATE ([[M31]] + [[M1]]).* `implemented_but_not_orchestrated` + `verification_missing`.

**CPA-R2 — Affected-community participation is `sufficient_narrow_scope`, never mandate-creating (260).**
Participation can *support* a bounded value choice inside an already-authorized decision space; it never *creates*
the space, never overrides a rights floor, never averages away a multi-principal conflict. Claim-matched: a
non-representative consultation supports "consulted subgroup raised concern Y," not "the affected population
prefers X." Repo `participation_requirement` already downgrades thin consultation and blocks LLM-summary-as-
participation. *Verdict: REINFORCES-EXISTING ([[M31]] + [[M12]] burden-of-proof).* `implemented_but_not_orchestrated`.

**CPA-R3 — `NormativeAuthorizationRecord`: weights are a recorded permission to aggregate, not ground truth (261).**
The keystone value-authority report and the source of [[M33]]. Absent an authorized schedule ⇒ `pareto_only` +
`NormativeDecisionRequest`; authority-lane mismatch (legal competence but wrong decision-rights role) ⇒ `blocked`,
not "downgraded to okay." Bans silent equal-weight / historical-prior / proxy-as-priority / library-default
scalarization. *Verdict: ADOPT-CANDIDATE ([[M33]] + [[M31]] + [[M16]]).* `producer_missing` (adjacent primitives
present).

**CPA-R4 — Multi-principal conflict = typed incompatibility records per axis, never a scalar settlement (262).**
Each principal gets one-or-more *authority seats* on the 7 axes; conflict materializes on logical-incompatibility
∨ rights/procedure-bar ∨ unauthorized-value-aggregation. Resolution routes are axis-specific (legal ⇒
hierarchy/scope-narrowing/phasing; legitimacy ⇒ governance-decision only). **Reuse-first, do not rebuild:**
`polisyos.evidence` already owns `PolicyConflictRecord` / `build_conflict_portfolio_index` /
`persistent_contested_state`, authoritative *only for conflict materialization*, never support-strength. *Verdict:
REINFORCES-EXISTING ([[M29]] + [[M30]] + [[M31]]).* `implemented_but_not_orchestrated` + `semantic_test_missing`.

**CPA-R5 — `ContestabilityReleasePacket`: prove contestability before publishing, don't gesture at it (263).**
Source of [[M34]]'s packet half. Publishable only if same-input explanation ∧ real recourse to a competent
reviewer with authority to change ∧ withdraw/reissue ∧ provenance/replay. Repo `graded_outcomes.py` already
requires a verified recourse pointer + `decision_owner_ref` for `publish_with_limitation`; `human_review.py`
already scores rubber-stamp risk. *Verdict: ADOPT-CANDIDATE ([[M34]] + [[M10]]).* `implemented_but_not_orchestrated`.

**CPA-R6 — Deliverability envelope: `deliverable | limited | blocked`, hard gates + minimum-of-load-bearing (264).**
Source of [[M32]]. Legal/organizational/operational/transparency/contestability must all meet the posture floor;
state capacity is a *ceiling* capping rollout scope even when local capacity looks fine. Repo `capability_authority.py`
already implements "minimum across load-bearing factors" — the exact composition primitive. *Verdict:
ADOPT-CANDIDATE ([[M32]] + [[M31]]).* `implemented_but_not_orchestrated`.

**CPA-R7 — Operational feasibility = a stage-by-stage failure ledger × 7 axes, never a feasibility score (265).**
Model per delivery stage (intake → scope → recommend → approve → execute → notify → appeal → monitor/suspend/replay);
"feasible" requires no unmodeled severe failure on any axis at any material stage. Fallback must be capacity-tested,
not described. *Verdict: ADOPT-CANDIDATE ([[M32]] + [[M31]] + [[M20]] verdict-granularity).* `implemented_but_not_orchestrated`
+ `verification_missing`.

**CPA-R8 — Capacity evidence = four observable record-classes, not caveats-in-a-memo (266).** Skills-Readiness /
Staffing-Continuity / Institutional-Memory / Maintenance-Burden, each emitted from *observable telemetry* (rosters,
training/incident stores, CHAOSS contributor-absence-factor, change-request-closure-ratio, toil ratio) — a
narrative-only input fails closed (`capacity_narrative_only_rejected`). **Caution (see §4):** raw git/HR telemetry
raises privacy/data-ethics issues — needs a governed aggregation/minimization layer, not raw reads. *Verdict:
ADOPT-CANDIDATE ([[M32]] + [[M8]]).* `producer_missing` + `verification_missing` + `surface_missing`.

**CPA-R9 — Ex-post public value = 5-domain card bundle; ROI computed *last* and *withheld* when unproven (267).**
No composite `public_value_score` (a direct Goodhart pressure). Separate cards for public-value / service-quality /
cost / trust / ROI; ROI needs baseline ∧ attribution-class ∧ non-monetized ledger ∧ no unresolved
rights/incident state, else `withheld_as_misleading`. Cost ledger must include *user-burden* + incident-adjustment
or the ROI is systematically false. *Verdict: ADOPT-CANDIDATE ([[M16]] full-bundle-not-scalar + [[M24]]
no-cancellation + [[M31]]).* `implemented_but_not_orchestrated`.

**CPA-R10 — Third-party evidence: three admission tiers + six sub-dossiers + independence accounting (268).**
Source of [[M35]]'s tiering half. Vendor artifacts enter as `candidate_only`, reach authority-path only via a
producer-owned adapter (content-bind + same-input closure + purpose boundary), and close a *major* claim only with
authority-side independent verification. Vendor-run eval ≠ independent; "no AIID match" ≠ "no incident." Reuse
existing `producer_evidence_contracts` family, don't invent a vendor engine. *Verdict: ADOPT-CANDIDATE ([[M35]] +
[[M3]] + [[M21]]).* `implemented_but_not_orchestrated` + `verification_missing` + `surface_missing`.

**CPA-R11 — Proprietary models/data: escrow + independent audit access + graded reproducibility (269).** Source of
[[M35]]'s three-contour half. Escrow is trigger-based (insolvency/breach/incident/regulator/contested-decision),
version/hash/time-bound, updated on every material change (silent drift = breach). Reproducibility is *tiered*
(same-input → metric → portability), never "full retraining replication." AI-Act Art.78 confidential-access
pattern. *Verdict: ADOPT-CANDIDATE ([[M35]] + [[M28]] a-posteriori-checkable + [[M13]] sealed-original).*
`implemented_but_not_orchestrated` (+ `producer/bridge/surface_missing`).

**CPA-R12 — License/IP/data-use/contract gating is an action×audience matrix, composed to the weakest boundary
(270).** Not one label per artifact: the same asset may allow internal inference but bar external fine-tune, allow
summary publication but bar payload. Labels ("open-source", "public") are *not* gate inputs — resolve the actual
clauses (**provenance-over-label**). Mixed bundles compose to the weakest permitted boundary; model-reuse
decomposes (inference / fine-tune / distill / weight-redistribution). EDPB: dataset-not-shared ≠ model-safe.
*Verdict: REINFORCES-EXISTING ([[M21]] + [[M1]] weakest-boundary + [[M31]]).* `contract_only` + `consumer_missing`
+ `semantic_test_missing`.

**CPA-R13 — External-dependency contingency/exit/decommission = a 7-band evidence bundle, fail-closed (271).**
Trigger classes: failure/outage, terms-or-model change, noncompliance-suspension. **Silent model swap** (schema
unchanged, weights/moderation/pricing changed) and **semantic data drift under unchanged schema** are the headline
adversaries — shape-validation greens while the decision basis moved. Exit needs data-return/delete evidence +
sub-processor visibility + continuity-of-appeal, not just a cutover. *Verdict: ADOPT-CANDIDATE ([[M32]] + [[M9]]
external-dependency typing + [[M31]]).* `producer_missing` + `semantic_test_missing` + `surface_missing`.

**CPA-R14 — Public transparency record is a projection-only derived artifact, never a public dump of the case
(272).** Audience-scoped; every field is a public-safe summary, an explicit redaction stub (with reason code), or a
blocker — never a silent drop and never a raw `cas://`/internal ref. Private evidence stays in PDC/audit; the
public record must not mint authority. Two-tier ATRS mapping. *Verdict: REINFORCES-EXISTING ([[M10]] + [[M31]]).*
`implemented_but_not_orchestrated` + `surface_missing`.

**CPA-R15 — Per-audience disclosure/redaction contract: PUBLIC/REVIEWER/EXPERT/MACHINE dispositions per fact ×
axis (273).** `AudienceDisclosureDecisionRecord` with `public_summary | reviewer_detail | expert_detail |
machine_structured | ref_only | access_controlled | redacted | blocked`. **MACHINE projection must preserve
reconstructable source/authority/audit refs** — a machine packet without refs launders prose into authority. A
redaction may hide a sensitive detail but never the *existence* of contestability. *Verdict: REINFORCES-EXISTING
([[M10]] + [[M31]]).* `implemented_but_not_orchestrated` + `semantic_test_missing`.

**CPA-R16 — Test whether public explanations improve *understanding + contestability* at non-increasing false
confidence — not perceived clarity (274).** Source of [[M34]]'s efficacy half; ties to [[SCI-R10]] structured
transparency. Four-arm design (control / reason / reason+limits / +challenge affordance); three DVs (understanding
via simulatability+error-detection / contest quality / false-confidence calibration gap). **Recourse laundering**
and **illusion of explanatory depth** are the named traps; deceptive explanations can out-persuade honest ones.
*Verdict: ADOPT-CANDIDATE ([[M34]] + [[M8]] behavioral-fixtures + [[M7]]).* `verification_missing` +
`semantic_test_missing` + `surface_missing`.

**CPA-R17 — Update/notice semantics: `record_lifecycle_state` is a downgrade-only *local dimension*, never a
parallel status world (275).** `current | stale | superseded | corrected | restricted | retired` composes with —
and only ever *lowers* — the publication state; superseded versions stay replay/audit-valid but not current-valid;
**no silent edit of a published public record** (breaks replay + contestability). `as_of` + `review_due_at`;
restriction distinguishes partial-redaction / full-tombstone / no-acknowledgement (NCND). Reuse `obligation_rules`
`PublicRevalidationEffect` vocabulary. *Verdict: REINFORCES-EXISTING ([[M25]] vintage/as-of + one-lattice
(Atlas DS4) + [[M31]]).* `implemented_but_not_orchestrated` + `surface_missing` + `semantic_test_missing`.

---

## §2·J Per-report distillation — Batch 10 (Cross-cutting Public Authority, CPA-R18–R28)

The second CPA half moves from *admissibility* (R1–R17) to the **operational lifecycle**: how perturbations reopen a
case ([[M36]]), how agents are authorized and disciplined ([[M37]]/[[M38]]), how proxies earn the right to stand for
a construct ([[M39]]), and how external regimes enter without laundering prose into authority ([[M40]]). As before,
nearly every report is reuse-first — and several point at *already-built* repo scaffolding (`case_lifecycle`,
`rule_evolution`, `construct_registry`, `scientist/governance/continuous`), which strengthens the [[M30]]×[[M31]]
"reuse the owner, don't mint a family" verdict.

**CPA-R18 — Incident registration = four operational classes + a seniority axis, not "we have a channel" (276).**
`hazard` (plausible harm w/ causal path) / `near_miss` (harmful chain stopped by a gate/rollback/fail-safe — a
blocked LLM-authority-laundering *is* a near-miss, not "doesn't count") / `incident` (realised harm) / `public_harm`
(external public-effect tag). OECD incident∥hazard; a candidate-only hallucination that never reached closeout is an
ordinary defect, not an incident (anti-alert-fatigue). OECD-7 mandatory fields + repo `same_input_envelope`.
*Verdict: ADOPT-CANDIDATE (feeds [[M36]] + [[M31]]).* `producer_missing`.

**CPA-R19 — Reopen/limit after appeal ≠ challenge ≠ correction ≠ reviewer-escalation: four event classes, four
default scopes (277).** Citizen appeal → narrow person-slice reopen; institutional challenge (regulator/court/DPA) →
default *revalidation demand* across sibling cases; correction request → data-accuracy narrow path (typo = annotate;
inaccurate-personal-data/provenance = restrict-then-reopen); reviewer escalation → hardest pre-publication gate.
Contestation never *mutates* a closed case — it emits a typed `PdcContestationIntake` + `PdcReopenScopeDecision`.
**Repo reuse:** `obligation_rules` `PUBLIC_CONTESTATION` + revalidation effects; `scientist/governance/continuous`
`incident/invalidation/reissue/lifecycle_bridge`. *Verdict: ADOPT-CANDIDATE ([[M36]] + [[M34]]).*
`implemented_but_not_orchestrated` + `semantic_test_missing`.

**CPA-R20 — Harm-response: compensation & public apology need a SEPARATE authority; they are not derivable from the
AI-incident fact (278).** `HarmResponseCaseV1` proves *readiness* per axis: correction / notification / individual
recourse may be ready while `compensation_blocked` (no compensation authority) and `public_apology_blocked` (no named
approver / unverified facts). Asymmetric states are first-class (`correction_complete + notification_complete +
compensation_not_authorized`). Ombudsman remedy practice (explanation/apology/remedial-action/compensation), not
governance theatre. *Verdict: REINFORCES-EXISTING ([[M31]] non-fungibility + [[M33]] authorization-required +
[[M34]]).* `artifact_missing` + `bridge_missing`.

**CPA-R21 — Cascade rulebook: 5 triggers × 7 axes → 5 lifecycle actions, fail-closed (279).** `incident | appeal |
retraction | legal_change | discovered_bias` → per-axis deltas → `annotation_only | invalidate | reissue | supersede
| withdraw`. Sharp discriminators: one upheld appeal ≠ systemic defect; renumbered rule w/ same logic-hash =
annotate not supersede; a single bias-metric anomaly ≠ withdraw (needs replication + protected-group harm). Two typed
records (`ClaimLifecycleTriggerRecord` + `ClaimLifecycleDecisionRecord`); pre-adjudication authoritative only for
intake/queueing. **Reuse `rule_evolution` supersede semantics.** *Verdict: ADOPT-CANDIDATE ([[M36]] keystone +
[[M31]]).* `implemented_but_not_orchestrated`.

**CPA-R22 — Pre-action `AgentActionAuthorityPacket`: capability ∩ permission ∩ mandate-bounded delegation ∩
envelope ∩ live accountability, checked *before* the action (280).** Source of [[M37]]. Five action classes;
`draft` is not globally low-risk (type by audience/externality); authority is non-monotone (search ↛ data_request).
Out-of-envelope ⇒ `HumanDecisionRequest` → five-rights `HumanDecisionRecord`; a click by the wrong role fails (P26).
Reuse `OperationContract`/`OperationInvocationRecord`/`AuthorityBoundary`/candidate-firewall. *Verdict:
ADOPT-CANDIDATE ([[M37]]).* `contract_only` + `producer_missing` + `bridge_missing` (D3 delegation layer).

**CPA-R23 — Log orchestration as an authority delta, not a rationale (281).** Source of [[M38]]'s selection half.
Evidence-selection / tool-choice / framing / compression each get candidate-universe + rejected-set + decision-policy
+ explicit authority effect (`authoritative_for = ∅`, mirroring `search_ledger`). Named traps: selection laundering
(low-`k_eff` set → false "consensus"), framing laundering (silent envelope-narrowing changes governance burden),
compression laundering (public prose drops retained-limitations). **Gap:** G6 has prompt/tool/search/orchestration/
replay ledgers but *no compression ledger*. *Verdict: ADOPT-CANDIDATE ([[M38]] + [[M3]] + [[M10]]).*
`implemented_but_not_orchestrated` + `semantic_test_missing`.

**CPA-R24 — Composite, lifecycle-bound, authority-aware agent threat model — not STRIDE/LINDDUN alone (282).** The
agent is simultaneously an untrusted interpreter of untrusted content, a privileged workflow actor, a PII handler,
and a non-authoritative evidence transformer. Six abuse classes (control/evidence-integrity/state-memory/privilege/
privacy/public-process) × workflow stages; **long-term memory is an untrusted surface** (memory-poisoning records
masquerading as policy/incident facts need governed admission); multi-agent coordination is first-class attack
surface. `agent_threat_case.v1` with 7 governance axes. *Verdict: ADOPT-CANDIDATE (security half of [[M37]] +
[[M31]]).* `verification_missing` + `semantic_test_missing` + `surface_missing`.

**CPA-R25 — Cross-agency handoff = two-step bounded acceptance; transfer artifacts + responsibility chain, never
authority wholesale (283).** Source of [[M38]]'s handoff half. `AuthorityBoundary.meet()` (∩ allowed uses, ∪
deny-lists; empty ⇒ blocked); no-responsibility-transfer-by-default; a *context capsule* (typed refs + as-of + legal
snapshot), not a summary blob; an `llm_candidate` summary crosses only as `candidate_only`. Auditability-by-
construction (time-correlated emit/accept/deny). Reuse `ClusterHandoffRecord`/`AuthorityDerivationTrace`. *Verdict:
ADOPT-CANDIDATE ([[M38]] + [[M35]]).* `implemented_but_not_orchestrated` + `surface_missing`.

**CPA-R26 — Retraction/correction propagation = a replayable `EvidenceValidityEvent`, not a narrative note (284).**
Taxonomy: metadata-correction / content-correction / expression-of-concern / retraction-recall / living-review-
superseded / citation-fabricated-or-unresolvable / source-withdrawn-unverified (**do NOT invent a `partial_retraction`
source type** — model partial loss at the claim/evidence relation). Propagates source→evidence-line→claim→publication;
"retraction laundering through a living review" and "fabricated citation w/ plausible metadata" are the headline
adversaries. Reuse `evidence_spine`→`claim_registry`→`case_lifecycle`; distinct from `rule_evolution` (sources, not
rules). *Verdict: ADOPT-CANDIDATE ([[M36]] source-status facet + [[M21]] anchored-support).*
`implemented_but_not_orchestrated` + `verification_missing`.

**CPA-R27 — Proxy-for-construct needs a construct-validity case, not a fit statistic (285).** Source of [[M39]].
Seven bundles (concept-contract + 6 Messick lenses) + a modality-specific independence floor (admin source-audit /
text confounder+semantic / EO independent-reference) + legal/legitimacy/capacity/transparency/contestability bundles.
Ofqual-2020 aggregation trap; ValiText ideology→incumbency confounder; CEOS non-independent-reference. **Repo owns
the seam:** `runtime/quality/construct_registry.py` (`construct_validity_requirements`, `proxy_validation_rules`,
per-posture `authority_requirements`). *Verdict: ADOPT-CANDIDATE ([[M39]]).* `implemented_but_not_orchestrated` +
`verification_missing` + `semantic_test_missing`.

**CPA-R28 — Minimal obligation grammar: one atom = one governance plane, over a source anchor, never direct authority
(286).** Source of [[M40]]. `RegimeClauseAnchor` (source identity/traceability) + `ObligationAtom` (exactly one of 7
planes + typed `binding_kind` + applicability + fulfillment-contract + temporal-semantics + authority-boundary).
Governance-prose-laundering guard: ATRS record / NIST profile / "no AIID match" / LLM legal summary are anchors,
projections, or rebuttal inputs — never filled authority slots. Extend `obligation_rules` with a dialect; don't
build a compliance brain. *Verdict: ADOPT-CANDIDATE ([[M40]] + [[M30]]×[[M31]]).* `implemented_but_not_orchestrated`
+ `surface_missing`.

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

*— Foundry Phase 8 batch —*

- **GY grounding firewall / CGF plane + a future Lex lane** (highest-value Phase-8 tie-in) ← **P8.01** / **P8.04**
  (anchored-support certificate at claim/span granularity, reusing the Scientist `citation_faithfulness` seed) and
  **P8.05** (legal-reasoning certificate over `assurance_case.py`'s SACM/GSN graph — this **confirms the R8 memory
  note** that SACM/GSN/CAE already live there). [[M21]] is the text/legal sibling of the CGF discipline; these are
  the design briefs for a Lex-authority + runtime/quality admission bridge.
- **GY causal engine (the N4/N-cycle causal organs) + runtime/quality admission** ← **P8.09** (change→causal
  attachment — **already implemented** in `ir.analytics.invariance` + the Foundry causal catalog; wire, don't build),
  **P8.10** (partial-ID OPE envelope — `ir.analytics.partial_identification` already ships the bounds machinery),
  **P8.12** (adaptive-RCT inference gates), **P8.14** (DTR partial-observability route classifier; the
  `proximal_bridge` frontier method exists but is unorchestrated). [[M22]] + [[M23]] as the triage-before-estimate
  discipline for every weak-identification method.
- **GY value / uncertainty engine (set-valued state)** ← **P8.10** / **P8.14** / **P8.06** / **P8.07** — all four
  land on [[M23]] (bound / ambiguity-set / abstention, never a laundered point), which is exactly the GY search
  target-spec's "lifted state must be set-valued; marginal-interval fallback + unknown/incomparable."
- **The future Foundry-subordination lane (ports/adapters/registry/conformance + D3.8)** ← the engine-internal
  disciplines not touching live GY work: **P8.02** (topic-model identification), **P8.03** (text-measure
  admissibility), **P8.11** (fairness-profile bandits), **P8.13** (safe-RL violation quartet). Carry as conformance-
  battery / promotion-gate candidates.
- **Fabric + spatial + runtime/quality** ← **P8.06** (RS-proxy admissibility with an area-of-applicability),
  **P8.07** (multimodal fusion support-certification + disagreement ledger), **P8.08** (dual disclosure-vs-validity
  gate — the direct instance of failure-pattern **P19**). Reuse `foundry.methods.catalog.spatial` +
  `ir.DPRobustnessCertificate` + the `ir.analytics` alignment/missingness/uncertainty seeds.
- **Atlas (DS9 / DS12 / DS16 / DS17)** ← **P8.04** (calibrated-citation edge/claim surface + selective abstention →
  DS9/DS12), **P8.07** (disagreement ledger as an authority-bearing surface state), **P8.10** / **P8.14** (bounds /
  ambiguity-set rendered as a *set*, not a fake point — [[M23]] made visual via [[M16]]/[[M10]]).
- **One actionable repo-defect finding worth a GY/Foundry ticket** (not routing): **P8.13** — `agent_sim/rl.py` PPO
  advantage normalization mixes active and inactive agents (already flagged in `FOUNDRY_REMEDIATION_PLAN`), a
  safety-relevant bug that must close before the RL seed is promoted. Verify in code before acting — reports are
  untrusted content.

*— Foundry Phase 9 batch —*

- **GY value / uncertainty engine (set-valued state)** ← **P9.06** (identification-gated model averaging →
  ambiguity envelope), **P9.10** (partial-ID meta-transport → bounds), **P9.01** (multi-resource cost envelope —
  [[M16]]). All reinforce [[M22]]/[[M23]] on the value plane and the GY "lifted state must be set-valued" direction.
- **GY causal engine + runtime/quality admission** ← **P9.07** / **P9.10** (transportability —
  `ir.analytics.transportability` + `causal.fusion.data_fusion` are **already implemented**; wire, don't build),
  **P9.03** (HANK identification packet), the identify-first-estimate-second discipline for every weak-ID method.
- **Scientist governance / GY-N12** ← **P9.09** (append-only living-review delta over the existing Scientist
  claim-ledger + continuous-governance statuses — [[M25]]), **P9.08** (publication-bias diagnostic-vs-correction
  split for the evidence-synthesis plane).
- **The future Foundry-subordination lane (conformance battery / D3.8)** ← **P9.05** (vintage-aware nowcasting),
  **P9.02** (TEE appraisal chain → a confidential-compute conformance item), **P9.04** (DSGE reporting),
  **P9.11/P9.12/P9.13/P9.14** (mechanism-design certificates with side/impossibility scoping — [[M26]]).
- **Atlas (DS9 / DS16 / DS17)** ← **P9.01** (energy/carbon envelope surface — distribution/basis, not a number),
  **P9.13** (welfare-loss decomposition surface — never scalar-only), **P9.11/P9.12** (side-scoped /
  negative-scope claim rendering — [[M26]] made visible on the glass).
- **Two actionable repo findings (verify in code — reports are untrusted):** **P9.03** independently
  **re-confirms the P6.13 defect** — the measurement-aware loss adapter drops `identification_mode`
  (`del targets, identification_mode`); and **P9.04** names `runtime.quality.calibration_ledger`'s
  `test_historical_prior_refs_fail_claim_registry_evidence_slots` as the ready model for a historical-influence
  firewall.

*— Foundry Phase 10 batch —*

- **The future Foundry-subordination lane (conformance battery / D3.8)** is the primary home for Phase 10 — most
  reports are engine-internal method disciplines: **P10.01** (multilevel-solve regime router), **P10.02**
  (finite-N correction stack), **P10.05** (competing-risks/recurrent estimand→estimator rulebook), **P10.15**
  (multivariate EVT tail object), **P10.16** (regime-keyed policy-iteration certificate). Carry as
  conformance-battery / promotion-gate criteria ([[M22]] regime-triage + [[M28]] a-posteriori bounds).
- **GY causal engine + runtime/quality admission** ← **P10.03** (coupled-mechanism / correlated-equilibrium
  certification layers — reuses four recognizable repo patterns), **P10.06** (marked STPP — `dynamic_regime` +
  `local_independence` already own the semantics; wire, don't build), **P10.12** (causal-fairness lexicographic
  admission over `causal.fairness@1.0.0`), **P10.10** (manifold causal-faithfulness — extends
  `latent_bridge_synthesis`).
- **GY value / uncertainty engine (set-valued state)** ← **P10.01** (robust-bound/abstain as first-class solve
  modes), **P10.15** (joint-exceedance tail law, not a scalar), **P10.02** (εN/fluctuation set-valued) — all
  reinforce [[M23]] and the "lifted state must be set-valued" direction.
- **Scientist governance / GY-N12** ← **P10.14** (drift-conditioned anomaly update = staged fail-closed chain
  over `polisyos.ddm`; recency ≠ authority — [[M25]]), **P10.13** (adaptive-audit detection bounds for the
  evidence plane).
- **Atlas (DS9 / DS16 / DS17)** ← **P10.07** / **P10.08** (survival-band / longitudinal-functional surfaces —
  *simultaneous* vs pointwise bands, path ≠ functional), **P10.09** / **P10.10** / **P10.11** (representation-
  conditioned descriptors on the glass — show the declared metric/filtration/observation regime, never geometry-
  as-substance — [[M27]]), **P10.15** (tail as a joint object, not a scalar risk score).
- **Two actionable precision notes (verify in code — reports are untrusted):** **P10.15** — `foundry.uncertainty.
  monte_carlo` writes only *univariate* `tail_risk` metadata (cvar_05 / quantile_01 / quantile_99) with an
  arithmetic-only test; do not mistake it for a multivariate tail-risk authority. **P10.16** —
  `optimization.dynamic.dynamic_programming@1.0.0` is *finite-horizon staged DP*, not stationary discounted PI, so
  the discounted (1−γ) error bounds must not be applied to it mechanically (it needs a separate finite-horizon
  backward-error contract).

*— Foundry Phase 11 batch —*

- **The consolidation architecture itself** ([[M30]], the constructive answer to the §4 certificate-proliferation
  caveat): **P11.13** ("common port, not common theorem"), **P11.09** (one authority surface, two lanes), **P11.15**
  (one parity port, language-native lowerers), **P11.05** / **P11.12** (one composition record over family-native
  sub-certs). When the deliberate consolidation act happens, this is the pattern — a shared waist envelope +
  discriminated-union payloads, reusing `CrossBackendEquivalenceCertificate`.
- **The future Foundry-subordination lane (conformance battery / D3.8)** ← the engine-internal method disciplines:
  **P11.01** (spatial EVT), **P11.03** (copula tail-dependence), **P11.06** (dynamic-game ID), **P11.07** (VFI
  uncertainty chain), **P11.08** (DCC/MDCEV), **P11.10** (coherent forecast authority), **P11.11** (LP-vs-VAR
  dispatch + MHT + top-code + deflator), **P11.13** (trajectory/motif certs), **P11.15** (cross-toolchain parity).
- **GY value / uncertainty engine (set-valued state) + causal engine** ← **P11.05** (nested EVT→DRO→GE composition
  — [[M29]]), **P11.12** (sequential-value composition), **P11.06** (dynamic-game set/selection identification),
  **P11.09** (safe-BO search-authority lane for the GY search controller). All reinforce [[M23]]/[[M29]].
- **Scientist governance / GY hidden-eval + promotion gate (D3.8)** ← **P11.14** (six-judge meta-eval as a selective
  instrument with `effective_independent_judge_count` — [[M3]]; reuses the `causal_statistical_validity_report`
  template), **P11.04** (scenario-coverage proof over a declared denominator — the GY balanced-memory /
  successes-not-just-failures law), **P11.02** (whistleblower governance's role-separated control loops).
- **Atlas (DS9 / DS12 / DS16 / DS17)** ← **P11.10** (ordinal/quantile/interval forecast surfaces — *simultaneous* vs
  pointwise, no-crossing on the glass), **P11.02** (source-protection / disclosure surfaces — projection-only,
  recourse-reachable), **P11.14** (show the judge-stack envelope + collapse reasons + abstention, never a bare
  verdict).
- **Actionable (verify in code — reports are untrusted):** `tests/_golden/foundry/signature_baseline.json`
  `method_count: 0` is re-confirmed a *third* time (P11.14, P11.15) — an empty method-inventory golden, consistent
  with the standing note.

*— Cross-cutting Public Authority batch —*

- **The consolidation architecture for the whole public-authority layer = [[M31]] × [[M30]].** The ~17 CPA records
  should NOT become 17 owners and NOT become one governance number. They should be **discriminated-union payloads
  over one admission port** ([[M30]]), **composed by the 7-axis weakest-boundary rule** ([[M31]]). Most already
  have a home: reuse `evidence.PolicyConflictRecord` (R4), `participation_requirement` (R2/R3 participation lane),
  `capability_authority` "minimum-of-load-bearing" (R6/R7 composition), `runtime.quality` `producer_evidence_contracts`
  (R10/R11 supplier evidence), `graded_outcomes`/`human_review` (R5/R16 contestability), `institutional_provenance`
  (R6/R8 feasibility), `core.audit` (R11/R14 offline bundles). The one genuinely `producer_missing` new family is
  the value-authorization record (R3, [[M33]]).
- **Atlas DS12 (public publication gate) + DS14 (public transparency surface)** ← **CPA-R5** (contestability packet
  before publish), **CPA-R14** (projection-only transparency record, redaction-with-reason, never mint authority),
  **CPA-R15** (per-audience disclosure matrix; MACHINE must keep reconstructable refs), **CPA-R16** (measure
  explanation efficacy, not clarity — ties to [[SCI-R10]] and the existing DS12↔CPA-R16 cross-link), **CPA-R17**
  (lifecycle-state is downgrade-only, no silent edit). All are projection-only [[M10]]/[[M31]] surfaces.
- **Atlas DS9 (human decision integrity)** ← **CPA-R3** (value-authorization = `principal` role, not `ai_first`,
  not `delegated_autonomous`), **CPA-R5** (competent reviewer with change-authority; rubber-stamp fails) — both sit
  directly on the DS20 review-effectiveness telemetry already merged.
- **Atlas DS4 (status grammar)** ← the CPA lattices must be filtered through DS4's one-lattice / recompute-not-pin
  discipline. **CPA-R17 supplies the rule:** a lifecycle/authority dimension may only *lower* the composed status,
  never open a parallel status world — the antidote to status-enum-proliferation from 7 axes × 17 records.
- **GY-N11 (δ-budget) / N12 (epochs)** ← **CPA-R1/R6** hard-gate-then-minimum composition is the same shape as
  N11's obligation-class δ-split; **CPA-R17** stale/superseded/corrected semantics = N12's epoch/stale-certificate
  handling, and **CPA-R13** contingency triggers = external-dependency epoch boundaries.
- **Layer-2 D3 (multi-principal normative firewall)** ← **CPA-R4** typed incompatibility-per-axis + reuse of
  `evidence.PolicyConflictRecord`; **CPA-R3** authorization-to-aggregate. These are the D3 firewall's evidence shapes.
- **Observations (not actionable code bugs — this tier is design-research):** (1) every CPA report independently
  lands `implemented_but_not_orchestrated` + `surface_missing` — a *consistent* signal that the public-authority
  primitives exist but the cross-cutting producer/surface does not; treat as a real orchestration gap, not 17
  separate ones. (2) The target-architecture doc's own admission that *"measurability & subject granularity are
  orphan"* and *"state capacity, mandate/legitimacy, feasibility are orphan"* on the axes (cited by CPA-R9) is a
  registered gap worth a pointer. (3) **CPA-R8's CHAOSS/git-telemetry-as-capacity-evidence needs a governed
  minimization layer** before any raw read (privacy/data-ethics) — see §4.

*— Cross-cutting Public Authority batch 2 —*

- **GY-N12 (epochs / stale certificates) + Layer-2 lifecycle** ← **CPA-R21** (5-trigger × 5-action cascade =
  [[M36]]) and **CPA-R26** (source-status `EvidenceValidityEvent` propagation) are the same recompute-not-pin law
  N12 needs. **Reuse-first, do not rebuild:** `case_lifecycle.py` (states + `REVISION_ACTION_ORDER`),
  `core.contracts.rule_evolution` (semantic-change revalidation blocker), and `scientist/governance/continuous`
  (`incident`/`invalidation`/`reissue`/`lifecycle_bridge`) already materialize much of the cascade — CPA-R19/R21/R26
  should wire these, not add a parallel owner.
- **Atlas DS9 (human decision integrity) + DS20 server-authz** ← **CPA-R22** (pre-action `AgentActionAuthorityPacket`
  = [[M37]]) and **CPA-R23** (orchestration-choice authority-delta log = [[M38]]). The memory's prior note
  "CPA-R22/R23 ≈ DS20-authz" is confirmed: these are the agent-action authorization + audit that DS20's server floor
  and the G6 bounded-agent ledgers already partially carry. **CPA-R23 flags a real gap:** G6 has prompt/tool/search/
  orchestration/replay ledgers but *no compression ledger* — the compression-laundering surface is unbuilt.
- **GY bounded LLM agent + proving-ground safety** ← **CPA-R24** (composite agent threat model: untrusted transducer,
  memory-poisoning, multi-agent handoff as attack surface) and **CPA-R25** (cross-agency handoff = `meet()` +
  responsibility-chain, [[M38]]). These are the security envelope for any promoted B-side agent (the D3.8 gate).
- **Layer-2 D3 delegation layer** ← **CPA-R22** names the pre-action gate the still-`contract_only`
  `DelegationContract`/`HumanDecisionRequest`/`HumanDecisionRecord` triad needs (the D3 layer the memory tracks as
  producer-missing). This is the single highest-value wiring target in the batch.
- **GY-S substrate / construct grounding + CGF** ← **CPA-R27** proxy-for-construct validity ([[M39]]) has a live repo
  seam: `runtime/quality/construct_registry.py` already carries `construct_validity_requirements` /
  `proxy_validation_rules` / per-posture `authority_requirements`. This is the "measurability ≠ construct" gate the
  target-arch doc admits is orphan.
- **External-regime ingestion (Lex ↔ obligation_rules) + §3.5.11 CGF** ← **CPA-R28** plane-separated obligation
  grammar ([[M40]]). Open consolidation question it raises: the boundary between `lex` (true legal artifacts) and
  an `obligation_rules` dialect (mixed-bindingness regimes: OMB/NIST/ATRS/OECD) — keep `binding_kind` typed, don't
  dilute the Lex legal contour.
- **Actionable / observational (verify — reports are untrusted):** no hard code bugs this batch (design-research
  tier). Two standing gaps re-confirmed: the **D3 delegation layer is still `contract_only`/`producer_missing`**
  (CPA-R22), and **no compression ledger exists on the G6 bounded-agent surface** (CPA-R23). One reuse win worth
  recording: `case_lifecycle.py` already enumerates the full lifecycle-state set + `REVISION_ACTION_ORDER` that
  CPA-R21/R26 assume (verify before building anything new).

---

## §4 What NOT to adopt / honest caveats

- **Do not import the reports' status lattices wholesale.** Each proposes its own — collectively they are a
  status-enum-proliferation risk (our own anti-pattern). Adopt the *shape* (typed, fail-closed,
  research_only floor, recomputed states) and reconcile against the single Atlas status lattice.
- **Do not treat any report as a capability.** Every report across all five batches honestly self-caps at
  `research_only` / `accepted_narrow_scope` / `implemented_but_not_orchestrated` / `bridge_missing` /
  `semantic_test_missing`. SCI-R7's predictive-challenge claim is explicitly `blocked` — keep it blocked.
- **Do not present δ-style guarantees as unconditional.** R1/R4's admissibility and VOI bounds are
  conditional on obligation-completeness + validator-soundness — the same P29 regress that GY-N11 carries.
  Any consolidation must carry the conditionality clause (and, per [[M1]], red-test its deletion).
- **`authoritative_for`/`may_not_use_for` must be recomputed, not trusted by presence** (§3.5.10 / substrate
  gate-2). A label is not a control; the checker must catch the forbidden *consumption*.
- **Do not regress Fabric's already-honest self-labels.** Several Fabric primitives already carry the correct
  conservative label in code (`graph_temporal_scope="partial"` / `research_track="R3"`; generic-streaming default
  `at_least_once_with_dedupe`; row-level quarantine). The reports *validate* these; consolidation must keep them,
  not "upgrade" them without the proof artifact ([[M12]]) each label demands.
- **The status-lattice proliferation risk is now severe** ([[M6]] caveat, escalated again): across Foundry Phases 6–11
  the reports propose ~89 bespoke status lattices (defect-impact effects, reduction-certificate tiers, calibration-
  decision-relevance states, sequential-Bayes coverage classes, proof-carrying-certificate lattices, reproducibility
  tiers, DP-composition states, federated-correctness classes, judge-holdout states, identification-status lattices,
  observability-regime routes, fairness-profile states, safe-RL violation classes, energy-carbon estimate statuses,
  TEE claim classes, nowcast/HANK/DSGE identification lattices, transportability statuses, matching/auction/DA
  certificate statuses, multilevel-solve postures, equilibrium existence/witness/multiplicity lattices, survival-
  interval admission states, topology/manifold/graph descriptor statuses, audit-detection & drift-update lattices,
  policy-iteration certificate regimes, spatial-EVT/copula/scenario-coverage lattices, dynamic-game identification
  statuses, VFI/DCC/forecast-authority lattices, judge-stack meta-eval states, cross-toolchain parity verdicts, …).
  Adopt the *shape* (typed, fail-closed, `research_only` floor, states recomputed not pinned) but every one must be
  reconciled against the single Atlas status lattice / DS4 discipline before it lands. Do not import ~89 parallel
  lattices. **The CPA batch adds a second dimension of the same risk:** 7 authority axes × 17 records, each report
  proposing per-axis statuses. The resolution is supplied *inside* the batch by **CPA-R17 / [[M31]]**: an
  authority/lifecycle dimension may only ever *lower* the single composed status (weakest-boundary), never open a
  parallel status world — so the 7 axes are composition inputs to one lattice, not seven lattices.
- **Candidate-certificate proliferation is now the single largest consolidation risk** (Phases 8–10): the three
  batches together propose **~44 new local candidate artifacts** (Phase 10 alone adds ~16: `multilevel_admissibility_
  assessment`, `mean_field_finite_n_correction`, `SurvivalIntervalBundle`, `CoupledMechanismEquilibriumCase`, the
  Hawkes triad, `EventHistoryEstimateV1`, `MarkedSpatioTemporalEventProcessResult`, `LongitudinalOutcomeFunctionalBundle`,
  `TopologyShapeReport`, `CausalManifoldFaithfulnessCertificate`, `AdministrativeGraphEstimateCandidateV0`,
  `BenefitAbuseFairnessBalanceBundleV1`, `AuditDetectionBoundReport`, `FoundryAnomalyDriftUpdateAssessment`,
  `FoundryMultivariateTailRiskArtifactV1`, `PolicyIterationErrorCertificateV1`). The earlier ~28 were Phase 8's ~14
  (`regulatory_citation_proof`,
  `topic_model_identification_record`, `text_measure_certificate`, `rag_citation_calibration_receipt`,
  `legal_reasoning_certificate`, `remote_sensing_proxy_admissibility_report`, `common_unit_fusion_authority_record`,
  `causal_change_semantics_attachment`, `ope_identification_envelope`, `geospatial_aggregation_risk_record`,
  `fair_contextual_bandit_report`, `adaptive_rct_inference_bundle`, `safe_rl_violation_certificate`,
  `partial_observability_assessment`) plus Phase 9's ~14+ (`energy_carbon_estimate` envelope, the four `tee.*` records,
  `MixedFrequencyNowcastCandidate`, `StructuralModelAveragingAuthorityRecord`, `hank_identification_evidence`,
  `dsge_reporting_bundle`, `transport_bayesian_nma_report`, `publication_bias_calibrated_power`, the `LivingReviewDelta`
  triad, the five `MetaTransport*` records, `TwoSidedPreferenceProfile`, `FoundryAuctionWelfareLossEnvelope`,
  `BoundedPlatformRegulationContract`, the DA strategy-proofness certificate). Do **not** canonize these as ~44 parallel
  authority families. Any consolidation must factor a **shared waist** (authority_boundary + provenance +
  same_input_closure + status + calibration/uncertainty refs — the [[M1]]/[[M11]]/[[M15]] envelope) and let only the
  domain-specific payload differ; otherwise the backlog reintroduces the very fragmentation the narrow waist exists to
  prevent. Every report *itself* flags its artifact as `candidate_for_consolidation` — honor that. **The constructive
  resolution now has a name: [[M30]]** (surfaced by Phase 11 — P11.13 "common port, not common theorem"; P11.15's
  parity-port; P11.09's one-surface-two-lanes) — collapse the ~60+ candidate certificates (Phases 8–11) to *one*
  shared admission port with a discriminated-union of family-native payloads, reusing the repo's
  `CrossBackendEquivalenceCertificate` seed. That is the pattern the deliberate consolidation act should adopt.
  **Batch 9 raises the count to ~77** (adds ~17 CPA records: `mandate_admissibility_record`,
  `affected_community_participation_judgement`, `NormativeAuthorizationRecord`, `MultiPrincipalConflictBundle`,
  `ContestabilityReleasePacket`, `PolicyDeliveryCapacityAssessment`, `delivery_feasibility_failure_battery`,
  `operational_capacity_evidence`, `ExPostValueMeasurementRecord`, `third_party_supplier_evidence_packet`,
  `VendorEvidenceEscrowRecord`, `DownstreamUseRestrictionRecord`, `ExternalDependencyContinuityEvidenceBundle`,
  `public_algorithmic_transparency_record`, `AudienceDisclosureDecisionRecord`, `PublicExplanationEvaluationRecord`,
  `TransparencyRecordLifecycleEvent`). For the CPA layer the resolution is **[[M30]] × [[M31]] jointly**: the shared
  port + family-native payloads ([[M30]]), *composed by* the 7-axis weakest-boundary rule ([[M31]]). Most CPA
  records also have an existing owner (reuse `evidence.PolicyConflictRecord`, `participation_requirement`,
  `capability_authority`, `runtime.quality.producer_evidence_contracts`, `graded_outcomes`/`human_review`,
  `institutional_provenance`, `core.audit`) — only the value-authorization record ([[M33]]) is genuinely new.
  **Batch 10 raises the count to ~90** (adds ~13 CPA lifecycle/agent records: `PolicyIncidentRecordV1`,
  `PdcContestationIntake` + `PdcReopenScopeDecision`, `HarmResponseCaseV1`, `ClaimLifecycleTriggerRecord` +
  `ClaimLifecycleDecisionRecord`, `AgentActionAuthorityPacket`, `OrchestrationChoiceAuditV1`, `agent_threat_case.v1`,
  `CrossAgencyAgentHandoffRecordV1`, `EvidenceValidityEvent`, `ConstructValidityReceipt`, `RegimeClauseAnchor` +
  `ObligationAtom`). But Batch 10 *strengthens* the resolution rather than worsening it: **most of these reports name
  an existing owner to reuse** — `case_lifecycle` + `rule_evolution` + `scientist/governance/continuous` (R19/R21/R26
  cascade), `construct_registry` (R27), `obligation_rules` dialect (R28), `OperationContract`/`AuthorityBoundary.meet`
  (R22/R25). The consolidation act should treat the ~90 records as [[M30]]×[[M31]] payloads over ~6–8 existing owners,
  not ~90 families. **The two genuinely-missing producers to note:** the D3 delegation gate (R22, `contract_only`) and
  the value-authorization record (R3, [[M33]]).
- **CPA-R8 CHAOSS/repo-telemetry caveat.** Using raw git/HR telemetry (contributor-absence-factor, change-request-
  closure-ratio, response latency, roster data) as operational-capacity evidence ([[M32]]) is attractive but raises
  privacy / data-ethics concerns that CHAOSS itself flags. Any adoption must route through a **governed aggregation
  / minimization layer**, never a raw read of git or HR stores — treat this as a hard precondition, not a later
  refinement.
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
- **Repo-drift pointers — with one earlier caveat now CORRECTED by Phase 9** (hygiene items, not findings). *Correction:*
  many earlier reports (Scientist / Fabric / Foundry P6–P8) could not locate
  `docs/system-design-decisions/policy-design-execution-topology.md` and I recorded it as a likely stale pointer — but
  **Phase 9 contradicts that**: several reports (P9.09, P9.12, P9.13, P9.14) list that exact path as *successfully
  inspected*, while only a couple (P9.05, P9.06) still couldn't reach it. The honest read now flips: the file **most
  likely exists and is fine**, and the earlier "universally missing" pattern was a per-report web-fetch limitation
  (several reports explicitly cited "GitHub without sign-in" limits), not a real repo gap. Do **not** action a
  "fix the stale pointer" chore on this basis — verify the path exists first (it probably does). The other two
  recurring pointers still stand: `tests/_golden/foundry/signature_baseline.json` reports `method_count: 0` (an empty
  method-inventory golden, flagged by P7.01/P7.11/P7.12), and `agent_sim/rl.py` PPO advantage normalization mixes
  active/inactive agents (a safety-relevant defect tracked in `FOUNDRY_REMEDIATION_PLAN`, whose `identification_mode`
  sibling P9.03 re-confirms). Phase 10 is consistent with the correction (P10.13/P10.16 list the topology doc as
  inspected; P10.06 could not reach it) — treat it as a per-report fetch artifact, not a repo gap. *(Verify before
  acting — reports are untrusted content.)*

---

## §5 Batch ledger

| Batch | Track | Reports | Status | Distilled |
| --- | --- | --- | --- | --- |
| 1 | Scientist | `SCI-R0`..`SCI-R10` (11) | **DONE** | §2·A + moves M1–M10 |
| 2 | Fabric | `FAB-R1`..`FAB-R10` (10) | **DONE** | §2·B + moves M11–M14 |
| 3 | Foundry (Phase 6) | `P6.01`..`P6.17` (17) | **DONE** | §2·C + moves M15–M17 |
| 4 | Foundry (Phase 7) | `P7.01`..`P7.14` (14) | **DONE** | §2·D + moves M18–M20 |
| 5 | Foundry (Phase 8) | `P8.01`..`P8.14` (14) | **DONE** | §2·E + moves M21–M24 |
| 6 | Foundry (Phase 9) | `P9.01`..`P9.14` (14) | **DONE** | §2·F + moves M25–M26 |
| 7 | Foundry (Phase 10) | `P10.01`..`P10.16` (16) | **DONE** | §2·G + moves M27–M28 |
| 8 | Foundry (Phase 11) | `P11.01`..`P11.15` (15) | **DONE** | §2·H + moves M29–M30 |
| 9 | Cross-cutting public authority (I) | `CPA-R1`..`CPA-R17` (17) | **DONE** | §2·I + moves M31–M35 (CPA-R16≈`SCI-R10`) |
| 10 | Cross-cutting public authority (II) | `CPA-R18`..`CPA-R28` (11) | **DONE** | §2·J + moves M36–M40 (CPA-R22/R23≈DS20-authz; R26≈`SCI-R8`) |
| 11 | Lex | `LEX-R*` | pending | — (sole remaining track) |

**Next:** only the **Lex (`LEX-R*`)** track remains. When it arrives, distil into a new §2-style section + fold any
genuinely new move into §1 (M-series), update §3 routing and §5. Consolidation into GY/Atlas is a **separate,
later** deliberate act — only after the backlog is fully distilled. Running totals: **139 reports** across 10
batches, **40 cross-cutting moves**, ~90 candidate records flagged for [[M30]]×[[M31]] consolidation (over ~6–8
existing owners, not ~90 families).

---

## §6 Assurance & adoption layer — all 40 moves

**Purpose.** §1–§5 answered *"what was valuable in the research?"* This section answers the harder question that
gates plan edits: *"which moves are re-verified enough to become a **mandatory input to a named plan task**?"* This
is the deliberate crossing of the frontmatter `may_not_use_for: task_execution_contract` boundary — but only for a
move that earns `plan_adopted` **here**, per-move, not for the raw reports (which stay untrusted content, [[M2]]).

**Method.** Three disciplines, applied to *all* 40 moves: (a) a **tier** (how much re-verification before it may
gate a task); (b) a **red-test / falsifier** — the single check that, if it *passes*, means the move was violated
(this is what a fixture must encode, [[M8]]); (c) **[[M3]] turned on the report corpus itself** (§6.4) — the CPA
consensus is inflated by shared NIST/OECD/OMB/ATRS/EU-AI-Act anchors, so a move backed by "12 reports agree" is
*not* 12-independent; we weight distinct primary anchors, not report count.

**Standing constraint (from the owner).** Every plan edit derived here (§6.5) is sequenced **after** the in-flight
**GY-N11** task (main plan) and **after** the in-flight **DS4** task (frontend plan). Nothing in §6 touches N11 or
DS4 themselves; N11/DS4 are treated as immovable predecessors.

### §6.1 Tiering & status schema

| Tier | Meaning | Gate before it may become a task input |
| --- | --- | --- |
| **T1** | Adopt-as-reinforcement. `REINFORCES-EXISTING` and/or a real repo primitive was cited. | One-line confirm against the named primitive; no new research. |
| **T2** | Adopt-with-verification. `ADOPT-CANDIDATE`, novel, touches an active/imminent lane. | Needs a false-pass/false-block fixture ([[M8]]) **and** an owner before it gates a task. |
| **T3** | Hold-as-candidate. Deferred, not-yet-needed, or conditional on an open research question. | Do not adopt; revisit when its dependency closes. |

Status codes (per move, §6.2): `RV` research_validated (≥1 independent primary anchor + internal coherence) · `RepoV`
repo_verified (a real named primitive cited — still re-check in code before it gates) · `FX` fixture_needed · `PROD✗`
producer_missing · `GAP` named-gap (surface unbuilt) · `COND(P29)` conditional on obligation-completeness (§6.3).
`plan_adopted` is **not** set until Phase 2 lands the edit.

### §6.2 Master adoption table (grouped by principle-family)

*My synthesis: the 40 moves collapse into 8 families. "Plan consumer" tags marked **(research)** route to the
proposed INT-R integration backlog, not to the two plans.*

**F1 · Envelope & authority-boundary**

| M | Tier | Red-test (turns it red) | Plan consumer | Status |
| --- | --- | --- | --- | --- |
| M1 | T1 | remove the envelope → consumer still grants authority | DS4 (envelope = first-class field); every GY producer | RepoV (`runtime.quality.authority`) |
| M2 | T1 | a research finding rewrites a spine artifact | process discipline (this doc) | RepoV |
| M9 | T1 | a producer blocks waiting on a parallel track instead of typing the assumption | GY-N7/N13 | RV |
| M21 | T2 | a nearest-name match passes as a bind | GY-N4 / CGF §3.5.11 | RV · FX |
| M30 | T1-design | ~90 records → ~90 authority families **or** one mega-scalar | the consolidation act (design, not research) | RV · OWN=consolidation |
| M31 | T2 | a passing lane compensates a failing lane; **or** 7 axes become 7 lattices (must compose to ONE — DS4 dep.) | DS4 composition rule; every CPA producer | RepoV (`capability_authority` min-of-load-bearing) |
| M40 | T2 | an ATRS record / NIST profile / "no AIID match" fills an authority slot | external-regime ingestion (lex↔obligation_rules) | RV · open-Q(lex boundary) |

**F2 · Claim-type / axis separation**

| M | Tier | Red-test | Plan consumer | Status |
| --- | --- | --- | --- | --- |
| M11 | T1 | two axes collapse into one score | Fabric passport; GY-N13b | RepoV (Fabric self-labels) |
| M15 | T1 | an estimate is read as a certificate | GY value/causal; Foundry outputs | RV |
| M16 | T1-design | a scalar ranking hides the Pareto / partial-order | DS16–18 set-valued surfaces; GY value | RV |
| M20 | T1 | aggregation hides a subgroup flip | GY value/causal; DS attribution | RV |
| M22 | T1 | a wrong-regime method runs with no triage gate | Foundry dispatch; GY causal | RV |
| M27 | T2 | a relabeled opaque latent dim treated as substance; a metric/embedding swap silently changes the "finding" | GY substrate; **INT-R6** (language-as-representation) **(research)** | RV |
| M29 | T1 | a veto is averaged away | GY value engine (nested composition) | RV |

**F3 · Effective-independence / no-inflation**

| M | Tier | Red-test | Plan consumer | Status |
| --- | --- | --- | --- | --- |
| M3 | T1 | N lineage-sharing sources counted as N independent supports | GY-N9 promotion; Foundry judge-stack; **§6.4 (this pass)** | RV |
| M12 | T1 | an "absolved/safe" claim passes by default | Fabric detect; GY | RV |
| M14 | T1 | a single lane's "clear" passes as detection | Fabric detect; **INT-R8** **(research)** | RV |
| M19 | T1 | free tuning with no accountable ledger | GY search controller; N11 δ-budget (selection *spends*) | RV |

**F4 · Proof-over-presence / verifier discipline**

| M | Tier | Red-test | Plan consumer | Status |
| --- | --- | --- | --- | --- |
| M7 | T1 | a measurement/diagnostic artifact is used as a control/authority artifact (or vice-versa) | GY honest-diagnostics; **INT-R3** control-vs-measurement at the UI **(research)** | RV |
| M8 | T1 | a structural-only test greens while the property is deleted | every producer's verification; **INT-R3/R9** **(research)** | RV |
| M18 | T1 | the generator self-certifies | GY bounded agent | RV |
| M28 | T1 | a convergence flag stands in for a decision-unit bound | Foundry method certs; GY | RV |
| M34 | T2 | an "Appeal here" link bound to nothing passes; an explanation that raises confidence but not understanding passes | DS9/DS12; **INT-R3** **(research)** | RepoV (`graded_outcomes`,`human_review`) |
| M35 | T2 | a vendor-run eval counts as independent; "no AIID match" = "no incidents" | CPA supplier evidence; **INT-R7** **(research)** | RV |
| M39 | T2 | single-number fit / non-independent validation / aggregation-jump passes | GY substrate | RepoV (`construct_registry.py`) |

**F5 · Sealing / projection / contamination**

| M | Tier | Red-test | Plan consumer | Status |
| --- | --- | --- | --- | --- |
| M4 | T1 | a derivative leaks back into the sealed raw | GY contamination containment; CGF | RV |
| M10 | T1 | a projection mints authority, or a MACHINE projection drops reconstructable refs | DS12–15; **INT-R8** **(research)** | RV |
| M13 | T1 | a redaction is reconstructable from diffs/hashes/ordering | DS12–14; **INT-R8** **(research)** | RV |
| M38 | T2 | compression drops retained-limitations and greens; framing-narrowing changes governance burden silently | **compression ledger (NEW task)**; DS12–14 | **GAP** (no compression ledger exists) |

**F6 · Regime-triage / validity-by-structure**

| M | Tier | Red-test | Plan consumer | Status |
| --- | --- | --- | --- | --- |
| M5 | T1 | a mandatory gate encoded as a buyable-back penalty term | GY-N11 obligation-class gates, N9 | RV · COND(P29) |
| M17 | T1 | a convenient method used outside its decision structure | Foundry dispatch; GY | RV |
| M23 | T2 | non-identification collapsed to a wide interval instead of a set/abstention; `unknown` treated as zero | DS16–18; GY value (ValueOuterSet); **INT-R1** **(research)** | RV · COND(P29) |
| M24 | T1 | a tail/process claim rests on a cancelling average | GY value; ex-post value (CPA-R9) | RV |
| M26 | T1 | a universal claim where impossibility is provable | GY; DS `incomparable` surface | RV |

**F7 · Time / lifecycle / recompute-not-pin**

| M | Tier | Red-test | Plan consumer | Status |
| --- | --- | --- | --- | --- |
| M6 | T1-design | a status pinned/trusted-by-presence instead of recomputed; a parallel lattice appears | DS4 (one-lattice, recompute-not-pin) | RepoV (DS4 direction) |
| M25 | T1 | a newer source outranks by recency alone; a silent edit replaces a versioned record | GY-N12 epochs; DS18 staleness | RV |
| M36 | T2 | a single upheld appeal invalidates the class; a closed case is silently mutated instead of superseded | GY-N12; DS13/DS18 (reuse `case_lifecycle`+`rule_evolution`+`scientist/governance/continuous`) | RepoV (`case_lifecycle` seam) |

**F8 · Capacity / permission / delivery**

| M | Tier | Red-test | Plan consumer | Status |
| --- | --- | --- | --- | --- |
| M32 | T2 | a calibrated model with an unstaffed appeal queue passes as deliverable; a local pilot extrapolates to national | CPA delivery gates | RV · caveat(CHAOSS-privacy) |
| M33 | T2 | silent equal-weight / historical-prior / proxy-as-priority scalarization | **NormativeAuthorizationRecord producer (NEW task)**; DS16–18 | **PROD✗** |
| M37 | T2 | a click by the wrong role / after TTL passes; search-authority grants data-request/write | **D3 delegation gate (NEW task)**; DS9/DS20; **INT-R5** | **PROD✗** / `contract_only` |

### §6.3 Load-bearing conditionals, missing producers, named gaps, actionable defects

- **The P29 conditional — the one thing that must never be presented unconditionally.** M5/M19/M23/M31 *feed* the
  δ-bound N11 computes, but that bound is **conditional on obligation-completeness**, which is formalized-not-solved
  (P29 regress). Any plan task or public surface that consumes these moves must carry the explicit rider "risk ≤ δ
  *relative to the declared obligation set*." This is precisely the dependency the proposed **INT-R1** closes; until
  it does, `COND(P29)` moves may gate *mechanism* tasks but not *public-claim* surfaces (DS12). This is the single
  most important adoption constraint in the whole ledger.
- **Three genuinely-missing producers (→ NEW tasks, §6.5).** (1) **M33** `NormativeAuthorizationRecord` — the value
  authorization producer; adjacent primitives exist, the producer does not. (2) **M37** the **D3 delegation gate** —
  `DelegationContract`/`HumanDecisionRequest`/`HumanDecisionRecord` are still `contract_only`/`producer_missing`.
  (3) **M38** the **compression ledger** — G6 emits prompt/tool/search/orchestration/replay ledgers but *no*
  compression ledger, so the compression-laundering surface is unbuilt.
- **Everything else is reuse, not build.** The ~90 candidate records collapse to [[M30]]×[[M31]] payloads over ~6–8
  existing owners; status-lattice consolidation is DS4 design work; M36's cascade reuses `case_lifecycle` +
  `rule_evolution` + `scientist/governance/continuous`; M39 reuses `construct_registry.py`. None of these is a
  research task.
- **Three actionable repo defects (verify-in-code first — reports are untrusted).** These are *tickets*, not
  move-adoptions, and per the standing constraint they queue **after** N11/DS4: (1) `tests/_golden/foundry/signature_baseline.json`
  `method_count: 0` (empty method-inventory golden, confirmed 3×). (2) **safety-relevant:** `agent_sim/rl.py` PPO
  advantage-normalization mixes active/inactive agents (`FOUNDRY_REMEDIATION_PLAN`) — flag for an out-of-band check
  even though its ticket queues after N11. (3) `del targets, identification_mode` in a Foundry adapter (P6.13/P9.03)
  — silently drops `identification_mode`. **Verify each exists before filing.**

### §6.4 Report-corpus lineage map — [[M3]] applied to the reports themselves

The honest deflation: the CPA half (R1–R28) reaches near-identical conclusions in part because the reports draw on a
**small shared anchor set** — NIST AI RMF, OECD AI Principles/AIM, OMB M-25-21/M-25-22, UK ATRS, EU AI Act. So
"many CPA reports converge on the 7-axis rule" is high-`k_eff`-illusion: the *distinct primary anchors* number far
fewer than the reports. Adoption weighting that follows:

- **High independent grounding (weight the move strongly):** the *engine* moves (M11–M29 from Scientist/Fabric/Foundry)
  rest on genuinely diverse method literatures + real repo primitives — low shared-lineage risk. M31/M34/M39 also
  have *independent repo anchors* (`capability_authority`, `graded_outcomes`/`human_review`, `construct_registry`),
  which is stronger than external-anchor consensus.
- **Shared-anchor consensus (adopt the *shape*, not the "N reports agree" strength):** M32/M35/M36/M37/M40 and the
  seven-axis framing lean heavily on the shared NIST/OECD/OMB/ATRS/EU set. Their *structure* is sound and repo-aligned,
  but a plan task must cite them as "a jurisdiction-neutral contract + one example mapping," never as settled
  cross-jurisdiction law (the reports say this themselves).
- **Practical rule for Phase 2:** when a task-addition cites a CPA move, cite the **repo primitive it reuses** as the
  authority and the external regime as the *example mapping* — never the report count. This keeps [[M3]] honored at
  the plan level.

### §6.5 Derived plan-edit manifest (Phase-2 bridge — all edits post-N11 / post-DS4)

*Proposed mapping of adoption-ready moves to concrete plan edits. Exact insertion anchors (task IDs, section numbers)
are pinned in Phase 2 by reading the two plan files; nothing here is applied yet, and every item is sequenced strictly
after the named predecessor.*

**Main plan — `docs/plans/active/layer3-slices/GY-engine-subordination.md` (all after GY-N11):**

| Edit | Type | Moves folded | Intent |
| --- | --- | --- | --- |
| **NormativeAuthorizationRecord producer** | NEW task | M33 (·M16·M29·M31) | value-schedule = recorded permission to aggregate; `pareto_only` + `NormativeDecisionRequest` absent authorization |
| **D3 delegation gate producer** | NEW task | M37 (·M18·M5) | pre-action mandate-bounded authority packet; agent = untrusted transducer |
| **Augment GY-N12 (epochs/stale)** | augment | M36·M25 (+CPA-R21/R26 `EvidenceValidityEvent`) | typed post-publication cascade; no silent mutation of closed cases; reuse `case_lifecycle`/`rule_evolution`/`continuous` |
| **Augment N9 / post-N11 δ-hardening** | augment | M5·M19·M3 · **COND(P29)** | gate-first (mandatory gate ≠ buyable penalty); selection *spends* budget; k_eff on promotion — with the explicit P29 rider |
| **Grounding/CGF §3.5.11** | augment | M21·M4 | anchored-support (versioned source + span + scope-algebra), not nearest-name |

**Frontend plan — `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` (all after DS4):**

| Edit | Type | Moves folded | Intent |
| --- | --- | --- | --- |
| **Augment DS16–18 (set-valued/risk-spend/staleness)** | augment | M23·M16·M24·M26 | set-valued/abstention surfaces; full-structure-not-scalar; `incomparable` as no-admissible-ranking |
| **Augment the DS4-successor status surfaces** | augment | M31·M6·M29 | weakest-boundary composition into ONE lattice; recompute-not-pin; no veto-erasure |
| **Augment DS9/DS12 (human decision / publication gate)** | augment | M34·M10·M35 | contestability proven not gestured; four-projection transparency; MACHINE keeps reconstructable refs |
| **Compression ledger** | NEW task | M38·M13·M14 | close the named G6 gap; `CompressionLossReceipt`; composition budget across repeated disclosures |
| **Augment DS18 staleness chrome** | augment | M25·M36 | vintage/as-of first-class; supersede-not-silent-edit |

**Not in this manifest (kept separate on purpose):** the INT-R integration/epistemic-closure research wave
(obligation-completeness, generalized acquisition, operator-comprehension, performative post-deployment learning,
etc.) is a *new research backlog*, not a plan edit — it belongs in `remaining-integration-and-epistemic-closure-backlog.md`,
downstream of this pass. The three actionable defects (§6.3) are *tickets*, also post-N11/DS4.
