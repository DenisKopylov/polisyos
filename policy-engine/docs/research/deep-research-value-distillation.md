---
title: Deep-Research Value Distillation Ledger
status: active
kind: research-synthesis
owner: team-architecture
created: 2026-07-20
revised: 2026-07-20 (Batch 1 — Scientist SCI-R0..R10 distilled)
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

Across all eleven Scientist reports the same handful of engineering/logical moves recur. These, not the
per-report prose, are the reusable yield. Each is stated as a move, with its verdict and where it lands.

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

---

## §2 Per-report distillation (Scientist batch)

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

## §3 Where this batch could land (consolidation map, not a commitment)

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
- **Reports observed one repo drift worth noting** (not a finding, a hygiene item): several reports could not
  locate `docs/system-design-decisions/policy-design-execution-topology.md` at the cited path. If that file
  is genuinely referenced by baseline instructions, it is a stale pointer to fix; recorded here so it is not
  lost. *(Verify before acting — reports are untrusted content.)*

---

## §5 Batch ledger

| Batch | Track | Reports | Status | Distilled |
| --- | --- | --- | --- | --- |
| 1 | Scientist | `SCI-R0`..`SCI-R10` (11) | **DONE** | §2 + moves M1–M10 |
| 2 | Fabric | `FAB-R1`..`FAB-R10` (10) | pending | — |
| 3 | Foundry | `FND-R*` | pending | — |
| 4 | Lex | `LEX-R*` | pending | — |
| 5 | Cross-cutting public authority | `CPA-R*` | pending | — (note CPA-R16≈R10, CPA-R26≈R8, CPA-R22/R23≈DS20-authz already flagged) |

**Next:** when a batch arrives, distil into a new §2-style section + fold any genuinely new move into §1
(M-series), update §3 routing and §5. Consolidation into GY/Atlas is a **separate, later** deliberate act —
only after the backlog is fully distilled.
