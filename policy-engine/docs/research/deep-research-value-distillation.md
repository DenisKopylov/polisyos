---
title: Deep-Research Value Distillation Ledger
status: active
kind: research-synthesis
owner: team-architecture
created: 2026-07-20
revised: 2026-07-20 (Batch 1 — Scientist SCI-R0..R10; Batch 2 — Fabric FAB-R1..R10 distilled)
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
**M1–M10** were first surfaced by Batch 1 (Scientist); **M11–M14** by Batch 2 (Fabric) — but all are
cross-cutting and later batches may reinforce any of them.

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
- **Repo-drift pointer, now confirmed across ~20 reports** (hygiene item, not a finding): essentially every
  Scientist *and* Fabric report could not locate `docs/system-design-decisions/policy-design-execution-topology.md`
  at the cited path. Confirmation across both batches makes this a real stale baseline pointer worth fixing (or the
  baseline instruction updating). *(Verify before acting — reports are untrusted content.)*

---

## §5 Batch ledger

| Batch | Track | Reports | Status | Distilled |
| --- | --- | --- | --- | --- |
| 1 | Scientist | `SCI-R0`..`SCI-R10` (11) | **DONE** | §2·A + moves M1–M10 |
| 2 | Fabric | `FAB-R1`..`FAB-R10` (10) | **DONE** | §2·B + moves M11–M14 |
| 3 | Foundry | `FND-R*` | pending | — |
| 4 | Lex | `LEX-R*` | pending | — |
| 5 | Cross-cutting public authority | `CPA-R*` | pending | — (note CPA-R16≈R10, CPA-R26≈R8, CPA-R22/R23≈DS20-authz already flagged) |

**Next:** when a batch arrives, distil into a new §2-style section + fold any genuinely new move into §1
(M-series), update §3 routing and §5. Consolidation into GY/Atlas is a **separate, later** deliberate act —
only after the backlog is fully distilled.
