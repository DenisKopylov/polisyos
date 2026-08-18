---
title: Wave-4 consolidation — architect orientation pack
wave: 4
tasks: [OPS-R14, PAO-R36, PAO-R4, S0-GAP-02]
prepared: 2026-08-16
prepared_by: architect
documentation_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
provenance_of_this_pack: recomputed
scope:
  - complete branch topology and file manifests for all 18 wave-4 refs
  - independently recomputed source census closing the wave's single uniform material gap
  - cross-package divergences requiring one consolidation ruling each
---

# Wave-4 consolidation — architect orientation pack

Every set-level number in this pack was produced by a walk over the whole set, never by reading a
representative file. Where a count is a zero, the harness that produced it was validated with a
positive control (a token that must be non-zero) and a negative control (a token that cannot exist).
Two harness defects were caught and discarded this way before any figure below was retained.

---

## 1. The structural trap — read this before planning any pass

**No single ref contains a complete package.** The wave has **two disjoint lines per task**:

```
research ──► independent-audit                     (line A: the findings)
    └─────► amendment ──► amendment-verification   (line B: the responses)
                 └─────► remediation ──► remediation-verification   (OPS-R14 only)
```

The amendment branch was cut from **research**, not from **audit**. Measured `contains_prev`:

| task | audit contains research | amendment contains audit | verification contains audit |
|---|---|---|---|
| OPS-R14 | YES | **NO** (7 behind) | **NO** |
| PAO-R36 | YES | **NO** (7 behind) | **NO** |
| PAO-R4 | YES | **NO** (7 behind) | **NO** |
| S0-GAP-02 | YES | **NO** (11 behind) | **NO** |

Consequence: reading only the terminal response branch loses **every audit finding document**.
The `audits/<task>/` directory with its seven analysis files exists **only** on line A.

Second consequence: **the two lines collide on paths.** Both write
`policy-operations/<task>/<file>.md`. Line A holds the *audited* (pre-amendment) text that the
findings cite by line number; line B holds the *current* text. Neither supersedes the other for
consolidation purposes — line A is the evidence, line B is the state.

All 18 refs share base `1a7a2d05e`; all are Markdown-only, additions-only, zero deletions,
**zero non-Markdown files**. No branch touches `AGENTS.md`, the failure-patterns register, source,
tests, or workflows. A merge therefore cannot revert `P37`.

---

## 2. Exact refs

| task | research | audit | amendment | amd-verification | remediation | rem-verification |
|---|---|---|---|---|---|---|
| OPS-R14 | `3a694212a` | `34c65a04e` | `83539ebf0` | `0fe8fe6a0` | `62de2c5fe` | `915ed6031` |
| PAO-R36 | `1bccc012b` | `9bbfd37a2` | `926326174` | `47f0680f4` | — | — |
| PAO-R4 | `a27c3da99` | `69182c079` | `0df03f35e` | `93571fd3c` | — | — |
| S0-GAP-02 | `a7c34cc40` | `3abbaf8c2` | `c14e3d435` | `0c7ab71aa` | — | — |

Package size at terminal state (files / added lines):
OPS-R14 **11 / 3,357** · PAO-R36 **10 / 3,251** · PAO-R4 **11 / 2,881** · S0-GAP-02 **12 / 4,201**.

Two artifacts *shrank* between audit-line and response-line versions and the reason should be
confirmed, not assumed: `pao-r36-public-correction-and-durable-notice.md` 684 → 509 and
`pao-r36/ordered-fanout-and-completeness-contract.md` 538 → 480, against
`pao-r36/falsifier-suite.md` 374 → 698.

---

## 3. Verdict state

| task | audit verdict | amendment-verification | blocking | material gaps | terminal |
|---|---|---|---|---|---|
| OPS-R14 | `GO_WITH_REVISIONS` (1 blocker / 28) | **`NO_GO`** | 2 + 1 non-blocking | — | remediation → delta-verification **`NO_GO`** |
| PAO-R36 | `NO_GO` (3 / 39) | `CONFORMS_WITH_GAPS` | **0** | 1 | — |
| PAO-R4 | `NO_GO` (3 / 30) | `CONFORMS_WITH_GAPS` | **0** | 1 | — |
| S0-GAP-02 | `GO_WITH_REVISIONS` (4 / 31) | `CONFORMS_WITH_GAPS` | **0** | 0 stated | — |

Amendment-ledger dispositions: OPS-R14 25 accepted / 4 with-variation · PAO-R36 36 / 4 / 3 rejected /
2 declined / 1 superseded · PAO-R4 29 / 5 · S0-GAP-02 31 / 4.

**The single material gap is the same fact in every package**: the verifier's environment could not
execute a complete exact-ref tree walk (clone/archive egress blocked; the connector exposes file
reads, and under `P35` an index or ranked connector result is not a complete denominator).

---

## 4. The census — recomputed, gap closed

The wave's one uniform material gap is **closed by this pack**. Complete walk executed at
`109ba3f44`, path denominator `policy-engine/src`, case-sensitive fixed string, binary excluded,
both file-type denominators.

**Controls.** Positive: `may_not_use_for` → 106/794/903, `supersede` → 48/215/260 (both non-zero,
both matching independent prior claims). Negative: `zzz_nonexistent_token_qq` → 0/0/0.

| token | all-source f/l/o | Python f/l/o | package claim | result |
|---|---|---|---|---|
| `may_not_use_for` | **106 / 794 / 903** | 106 / 794 / 903 | PAO-R4 106/794/903 | exact |
| `supersede` | **48 / 215 / 260** | 48 / 215 / 260 | PAO-R36 48/215/260 | exact |
| `renewal` | **4 / 4 / 4** | 1 / 1 / 1 | OPS-R14 4/4/4, py 1/1/1 | exact |
| `expires_at` | **50 / 281 / 364** | 49 / 280 / 363 | OPS-R14 same | exact |
| `ttl_seconds` | **30 / 116 / 148** | 30 / 116 / 148 | OPS-R14 same | exact |
| `expiry` | **28 / 103 / 122** | 27 / 102 / 121 | OPS-R14 same | exact |
| `legal_hold` | **2 / 7 / 8** | 2 / 7 / 8 | OPS-R14 2/7/8 | exact; **audit's 2/4/5 is wrong** |
| `grace_period` | **0 / 0 / 0** | 0 / 0 / 0 | OPS-R14 zero | **zero confirmed** |
| `not_after` | **0 / 0 / 0** | 0 / 0 / 0 | OPS-R14 zero | **zero confirmed** |
| `revocation_time` | **0 / 0 / 0** | 0 / 0 / 0 | OPS-R14 zero | **zero confirmed** |
| `individual_decision` | **0 / 0 / 0** | 0 / 0 / 0 | PAO-R4 zero | **zero confirmed** |
| `export_gate` | **0 / 0 / 0** | 0 / 0 / 0 | PAO-R4 zero | **zero confirmed** |
| `prohibited_use` | **0 / 0 / 0** | 0 / 0 / 0 | PAO-R4 zero | **zero confirmed** |

Every figure reproduces exactly, in both denominators, including the deliberate one-unit
all-source/Python differences on `expires_at` and `expiry` and the 4× difference on `renewal` —
those differences are themselves denominator controls and they held.

**The facts were never in doubt. The attribution was.** The distinction consolidation must carry:

| holder | may this party call the census `recomputed`? |
|---|---|
| any wave-4 package | **No** — its environment cannot execute the walk. `institutionally_supplied`; and an `institutionally_supplied` census **cannot settle a zero**. |
| this consolidation | **Yes** — the walk was executed here, with controls, at the pin. |

So the correct instruction is **not** "strip the zeroes everywhere." It is: **name the executing
party and label relative to the holder.** Each census claim carries counts, both denominators, the
pin, the executing party, and a label scoped to the party asserting it. A zero may be relied on at
consolidation level and never by a package standing alone.

---

## 5. Over-claim inventory — exact sites

Swept across the complete terminal state of all four packages, two phrasing families.

**Family 1 — "settled fact / true zero / established absence."**

| package | live sites |
|---|---|
| OPS-R14 | **0 live.** Three matches are the remediation's own record that the phrases were removed. `AV-B01` independently confirmed closed. |
| PAO-R36 | 0 |
| **PAO-R4** | **3 live** — `pao-r4/orientation-ledger.md:149` (§3.5 titled "Settled zeroes": *"settled true zeroes from a complete walk"*), `:199` (*"true all-source zeroes"*), `pao-r4/amendment-delivery-readback.md:120` |
| S0-GAP-02 | 0 |

**Family 2 — "settled because the architect supplied a walk."** A first sweep missed this; it needs
its own pattern.

| package | live sites |
|---|---|
| **PAO-R36** | **2** — `pao-r36/amendment-ledger.md:58` (`PAO-R36-I-005`: *"records settled 0/0/0 values because the architect supplied a complete pinned tree walk"*) and `:107` (R10 row: *"zeroes settled"*) |

Both families are the same defect: a package asserting an absence its own environment cannot
establish. §4 supplies the resolution for both.

**The grading diverged, and one verifier missed what another caught.** PAO-R4's verifier explicitly
wrote that the totals *"including the settled zeroes, remain corroborated and internally reconciled
but **not freshly recomputed here**"* — it knew — yet graded it a material gap, credited the package
with "correctly labels … as architecture-supplied" (not a registered `P37` label), and left the
over-claim and the negative capability conclusion that rests on it standing. OPS-R14's verifier
graded the identical fact **blocking** and forced removal. Same defect, two verifiers, two gradings.

---

## 6. `P37` vocabulary — the one real divergence

Registered five at `109ba3f44`: `recomputed` · `independently_reconciled` · `consumer_asserted` ·
`institutionally_supplied` · `not_established`; last three fail closed.

Measured usage across terminal states (occurrences):

| package | recomputed | indep_rec | cons_asrt | inst_supp | not_estab | machine_observed | inst_accepted |
|---|---:|---:|---:|---:|---:|---:|---:|
| OPS-R14 | 37 | 18 | 6 | 42 | 47 | 0 | 0 |
| PAO-R36 | 47 | 53 | 12 | 12 | 19 | 0 | 0 |
| PAO-R4 | 16 | 19 | 12 | 11 | 69 | 0 | 0 |
| **S0-GAP-02** | 30 | 20 | 3 | 3 | 101 | **11** | **15** |

Three packages use the registered five. S0-GAP-02 uses a six-way vocabulary
(`recomputed · machine_observed · independently_reconciled · attested · institutionally_accepted ·
not_established`). Its own verifier adjudicated this as
`S0-GAP-02-AV-P37-001` — **commendation, not defect** — with a crosswalk, and its decisive argument
is strong and must be engaged rather than dismissed:

> the amended non-positive set `attested · institutionally_accepted · not_established` covers the
> same ground as the registered fail-closed set, **so the refinement does not widen the
> authority-grade positive set.**

The three distinctions it preserves are real: deterministic recomputation vs bounded machine
observation; consumer-specific assertion vs signed attestation from any constrained role; a premise
merely supplied vs one accepted for a named scope after proficiency, dissent and challenge review.

**Architect ruling for consolidation.** Keep the registered **five as labels**; record the three
distinctions as **required sub-annotations** on the registered classes. Reason: in the crosswalk
`machine_observed` is positive-eligible *conditionally* — "subtype of `recomputed`, **or**
`independently_reconciled` when retained by a second non-producing observer," with bare producer
telemetry mapping to `not_established`. A gate must answer "is this predicate positive-eligible?"
With five labels that is a fixed lookup. With six it turns on a declared condition — and a declared
condition governing a gate is exactly the `P37` shape, one level down. Sub-annotation preserves every
distinction the verifier correctly identified while keeping the positive-eligible set condition-free.

---

## 7. Standing shape — measured, and the case that proves the rule

| package | fields | value(s) | files carrying it |
|---|---|---|---|
| **OPS-R14** | **3** — `research_standing` / `capability_standing` / `gate_standing` | `accepted_narrow_scope` / `NO_GO` / `NO_GO` | **11 of 11** |
| PAO-R36 | 1 — `result_standing` | `accepted_narrow_scope` | 8 |
| PAO-R4 | 1 — `result_standing` | **`GO_WITH_REVISIONS`** | 7 |
| S0-GAP-02 | 1 — `result_standing` | `accepted_narrow_scope` | 12 |

OPS-R14 names the third field in prose as **"First-public-signature gate standing."**

**PAO-R4 is the case that settles the ruling.** Its single field carries `GO_WITH_REVISIONS` — an
*audit-verdict* token used as a *standing* value — while the same package holds an unre-executed
census, a retained over-claim, and an `absent/unallocated` capability posture with no owner
appointed. One field cannot express "the architecture is accepted" and "the repo may not act on it"
at once, so it published the positive. That is precisely the two-axis collapse OPS-R14's R1 finding
named. Adopt OPS-R14's three fields as the reference shape and route it to `AGENTS.md`.

---

## 8. OPS-R14 `F-14A` — ruled, carry into consolidation

The remediation split `F-14`. `F-14B` is correct and verified: markers intact, premise falsified,
returns exactly `succession_scope_not_established`. `F-14A` opened a **new positive route**
(`scoped_succession_partial`) gated on an "independently reconciled non-producing authoritative
record," and the delta verification found it **`NOT_CLOSED`**: the detector compares instrument
bytes, receipts and substantive fields but never reconstructs administration, derivation, storage,
key-custody, failure or observation provenance. A successor-controlled record agrees perfectly and
takes the positive.

Its claimed warrant does not exist. Verified against the primary source: in the whole INT-R9 corpus
`non-producing` occurs **0 times**, `admitted_instrument` **0**, `admitted=true` **0**; the 5 uses of
`admitted` are *purpose-scoped* and `int-r9/state-machine-and-artifact-contracts.md:114` explicitly
qualifies admission as **"not authority."** The nearest analogue,
`int-r9/fixture-specifications.md:65` `FP-F18`, demands **"absolute independence from undisclosed
ties"** — stricter than `F-14A`, not its licence.

**Ruling: withdraw `F-14A`.** It is not a missing check but a wrong measurement class — content
agreement can never establish provenance, so no strengthening of the comparison closes it. Do not
commission a "strengthen `F-14A`" round. The two exits converge today: withdrawing, and re-founding
the predicate on a genuinely disjoint custody record, both yield the same operational result,
because such a record is institutional and therefore `institutionally_supplied` → fail-closed.
Register the provenance record as the condition under which the positive may return. Nothing is lost:
`F-14B` is a binding falsifiable procedural result — `INT-K06`, and `INT-K08` makes negative
completion a valid governed outcome.

### The rule this wave produced

> **Every repair that preserves a positive by adding a condition creates a new gate predicate, which
> must itself be classified. There is no fixed point until the condition is constructed at the level
> of the property it names.**

Two independent instances in one wave: `F-14A` (byte agreement offered for provenance independence)
and `machine_observed` (a declared frozen scope offered for observational adequacy). This is the rule
governing how `P37` is *applied*, and it belongs beside `P37`/`P38` in `AGENTS.md`.

---

## 9. What the packages hand up

All four converge, and the shape of the convergence is the wave's headline.

| package | engineering | institutional | further research |
|---|---:|---:|---:|
| S0-GAP-02 | 12 (`ENG-01..12`) | 9 (`INST-Q01..Q09`) | 9 (`RES-01..09`) |
| PAO-R4 | 7 (`ENG-01..07`) | 5 (`INST-01..05`) | 4 (`RES-01..04`) |
| OPS-R14 | 8 | 7 | 6 |
| PAO-R36 | owner-first map + 4 dependency declarations (INT-R6 unresearched · GY-N12 undelivered · INT-R7 delivered · OPS-R14 seam) | | |

PAO-R36 uses a different handoff **format** from the other three — an owner-first integration map
rather than typed `ENG`/`INST`/`RES` tables. That is a fourth shape divergence, alongside the
standing field.

**Not one of these is a blocked research question.** They are engineering wiring and named humans.
S0-GAP-02 states it directly: the wave does not advance the `INST-01`–`INST-05` layer, and a fully
specified system could still lack anyone able to sign. This confirms the standing result — no active
research remains on the first-milestone path — and it is why the architect's ruling holds that the
functional base precedes institutional negotiation.

Every package independently reached `absent/unallocated` for its capability chain, and each was
careful to say why the *weaker* labels (`contract_only`, `bridge_missing`, `producer_missing`,
`verification_missing`) would overstate reality. That label discipline is uniform and correct across
the wave; it is the one thing consolidation should preserve untouched.

---

## 10. Cross-package seam

`F11` closure is the conjunction **`RP-10 + RC-01 + RC-07 + F-04 + F-09 + DE-07`** — `RP-10` alone
does not close it. Present in **9 exact seam summaries across 8 artifacts**, with no surviving
`RP-10`-alone closure statement. Both sides declare the seam semantically complete and the runtime
interface `absent/unallocated`. Do not re-adjudicate it; verify it did not move.

---

## 11. Constraints on the consolidation

- Consolidation **dispositions and routes**; it does not edit package artifacts and does not repair.
  The INT-wave consolidation is the precedent: findings dispositioned, candidates named, routing map.
- It may **not** reopen an accepted finding, re-adjudicate the seam, or promote any capability,
  owner, gate or `OPS-R15` unblock.
- The outcome vocabulary stays at **three**. `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED` is `INT-K08`,
  not a fourth element. The INT-wave act's §8 constitutional trigger stays armed and unactivated.
- Architect adjudications already honored and not to be relitigated: `PAO-R36-I-001` declined
  (48/215/260 correct; the audit's 47/203/246 is index-truncated — **re-confirmed in §4**);
  PAO-R4-III-001 narrowed to the §4.2/§4.3 contract with the firewall binding *authority to
  determine*, never *executability*; S0-GAP-02's `INT-K08` placement.
