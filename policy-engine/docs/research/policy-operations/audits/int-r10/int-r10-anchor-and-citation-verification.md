---
title: INT-R10 — Anchor and Citation Verification
status: delivered
kind: independent-audit
research_task: INT-R10
audited_branch: research/int-r10-family-wise-risk-composition
audited_commit: 317fc9c36e710ac75634096c4d14a714b8bff504
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
overall_verdict: NO_GO
research_only: true
authoritative_for:
  - independent verification of INT-R10 repository path-line anchors
  - exhaustive enumeration of frontmatter/revision-line anchors across all three audited files
  - primary-source verification of the external transfer ledger
  - exact disposition of weighted-union, Holm, Sidak, group-sequential, anytime-valid, e-value, and selective-inference transfers
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, or database contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - permission to promote a PolicyOS design
  - replacement statistical theorem
  - assertion that a cited method applies outside its stated assumptions
---

# INT-R10 — Anchor and Citation Verification

## 1. Scope and method

Pass F checked every distinct repository `path:line` range used by the three audited files against
baseline `978e6b958...`. Repeated anchors were searched across the complete blobs rather than
sampled from visible excerpts. Pass D resolved each external citation to its primary paper or
publisher record and compared the paper's stated object and assumptions with INT-R10's transfer
verdict.

Two anchor classes failed:

1. one frontmatter/revision-line anchor was repeated **32 times** instead of citing the substantive
   `GY-GAP2` block; and
2. `confidence_ledger.py:1301-1364` was repeatedly asked to prove durable burn-before-invocation,
   although the append and transition to `execute_check()` occur after line 1364.

The external literature review was substantially stronger. Its main transfer judgments are
correct. The one recurring precision issue is that “Sidak” covers different product claims under
different structures: exact product control under independent tests, and the 1967 Gaussian
rectangle inequality under multivariate-normal structure.

---

## 2. Repository-anchor verification table

| Anchor used by INT-R10 | Claim tested | Audit result | Better substantive range where needed |
| --- | --- | --- | --- |
| `promotion_sequence.py:356-375` | one admissible N11 scope per N9 binding; `design-problem:<id>` | exact | unchanged |
| `confidence_ledger.py:1-52` | exact rational path, conditionality, good-event union without independence | exact | unchanged |
| `confidence_ledger.py:156-184` | stable owner scope for one non-resettable budget; content-derived scope ID | exact | unchanged |
| `confidence_ledger.py:250-390` | policy delta, schedule mass bound, total obligation partition, exact pool sum | exact for those validations | `405-419` additionally shows pool-to-class expansion when that fact is used |
| `confidence_ledger.py:518-557` | root binds one scope, registry/schedule, `budget_delta`, assumptions | exact | unchanged |
| `confidence_ledger.py:723-752` | one-scope receipt/current-head projection fields | adequate | unchanged |
| `confidence_ledger.py:1175-1298` | preflight binding and zero-spend refusal | adequate | unchanged |
| `confidence_ledger.py:1301-1364` | local ordinal, schedule index, spend and prior-spend computation | exact | unchanged for those claims |
| `confidence_ledger.py:1301-1364` | append `started` and burn before owner invocation | **range ends too early** | `1301-1382`, or narrowly `1356-1382` |
| `confidence_ledger.py:3740-3855` | ineligible/unavailable/non-anytime preflight refusal | adequate | unchanged |
| `confidence_ledger.py:3890-4025` | exact receipt recomputation and Basel schedule | exact | unchanged |
| `confidence_ledger.py:3998-4025` | exact `_schedule_alpha()` formula | exact | unchanged |
| `confidence_ledger.toml:1-18` | delta `1/100`; mass-one and half-mass schedules | exact | unchanged |
| `confidence_ledger.toml:53-121` | five proof profiles and unavailable owner-verified procedures | exact at proof-profile level | add `122-166` when claiming the complete thirteen-instrument census |
| `GY-engine-subordination.md:1-10` | substantive GY-GAP2 owner, consequence, warning, and closure signal | technically names the gap in revision metadata; **not reproducible as a substantive anchor** | `2439-2463` |
| `int-r9-first-promotion-evaluation-protocol.md:590-650` | three-slot chronology and general repair permission | substantive and adequate | unchanged |
| `audits/int-r9/int-r9-recommended-revision.md:30-105` | R1's eight requirements and mandatory falsifier | substantive and exact | unchanged |
| `int-r1-obligation-coverage-and-open-world-completeness.md:1-90` | relative completeness and conditional risk language | broad, but contains the exact theorem and clause at lines 35–79 | prefer `35-79`; no finding because the cited range does include the evidence |
| `stage0-custody-kernel-ratification.md:45-112` | authority/candidate lens and K05/K16 ratification | substantive and adequate | unchanged |
| `stage0-custody-kernel-ratification.md:160-190` | fail-closed binds authority band, not candidate computation | exact | unchanged |
| `universal-policy-design-system-vision-and-organizing-rules.md:390-398` | 13 blockers, zero useful-design rate, unbuilt D3.8 | exact | unchanged |
| `AGENTS.md:17-27` | P29 behavioral property-removal rule | substantive and exact | unchanged |
| `AGENTS.md:37-55` | P27/P28 pattern register and unresolved-research warning | substantive and adequate | unchanged |

### 2.1 Repeated range `1301-1364`

The range correctly includes:

- current-scope state loading;
- next local ordinal;
- schedule index;
- exact local reservation;
- local prior-spend sum; and
- local overspend rejection.

It ends while the `started` model is still being assembled. The source writes
`proof_detail = "risk burned before owner execution"`, appends the `started` event, and only then
enters `execute_check()` after line 1364. Eight uses across the three deliverables rely on that
ordering rather than merely local arithmetic:

- primary report §2.2 capability table;
- primary report §5 failure 11;
- primary report §7.4;
- primary report's owner-baseline description;
- fixture §1;
- fixture §3.4;
- fixture §9 invariant 3; and
- source ledger §2.

Each is a minor range defect. Their repetition is material because pre-execution enforcement is a
premise of Theorem A.

---

## 3. Full frontmatter/revision-line anchor set

The exact weak anchor is:

```text
policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10
```

Lines 1–10 are frontmatter. The long `revised:` metadata line happens to mention GY-GAP2, making
the citation technically defensible but operationally poor. The reader does not land on the
registered gap, owner, warning that N11 is not wrong, or closure signal. The substantive block is
at `:2439-2463`.

### 3.1 Primary report — 17 citations

`int-r10-family-wise-risk-composition.md` uses the weak range at:

1. Executive Finding — missing cross-scope composition;
2. §1.5 — current standing;
3. §2.2 — baseline census row;
4. §2.3 — mandatory falsifier, item 4;
5. §2.6 — cross-scope declaration/cap capability;
6. §2.6 — live family projection capability;
7. §3.3 — absence of a verified dependence contract;
8. §4.4 — current three-scope corollary;
9. §4.10 — pinned-baseline public language;
10. §4.11 — mandatory falsifier standing;
11. §6.2 — positive fixture's expected baseline refusal;
12. §6.3 — negative control's missing family binding;
13. §8.1 — owner handoff;
14. §8.2 — current INT-R9 claim handoff;
15. §9.1 — research-promotion condition;
16. §9.4 — GY-GAP2 closure evidence; and
17. §10 question 15 — stronger-than-union structure.

### 3.2 Fixture and artifact sketch — 5 citations

`int-r10/fixture-and-artifact-sketch.md` uses the weak range at:

1. §1 — pinned missing capability;
2. §1 — expected baseline `family_composition_unavailable` refusal;
3. §7.2 — positive future-control baseline refusal;
4. §7.3 — mandatory negative control; and
5. §10 — pinned-baseline expected result.

### 3.3 Source and transfer ledger — 10 citations

`int-r10/source-and-transfer-ledger.md` uses the weak range at:

1. §2 — pinned repository predicates;
2. S01 Holm non-transfer;
3. S05 online-FWER non-transfer;
4. S13 Sidak non-transfer;
5. §4.1 — current weighted-union conclusion;
6. §5 exact family membership/order standing;
7. §5 prospective local-cap standing;
8. §5 exact/pathwise aggregate-cap standing;
9. §5 live-source-verifier standing; and
10. §6 final carried conclusion.

### 3.4 Exhaustiveness result

The complete set is **32 citations across all three files**. No other cited range was found to rely
only on document frontmatter or a revision-history line. `INT-R1:1-90` was examined separately:
although it begins at frontmatter, it includes the substantive relative-coverage theorem and exact
conditional probability statement, so it is broad rather than empty.

---

## 4. Pass D — external primary-source verification

### 4.1 Weighted union / Bonferroni

**Source check:** direct probability inequality; Tian and Ramdas additionally treat predictable
online FWER allocations.

**Transfer verdict:** correct. If each local authority-error event has a valid cap under the same
maintained assumptions, the union inequality needs no common null, exchangeability, or
independence. The error in INT-R10 is not this transfer; it is the later claim that root delta is the
sharpest local information exposed by the pinned owner.

### 4.2 Holm

**Primary source:** Sture Holm, “A Simple Sequentially Rejective Multiple Test Procedure,”
*Scandinavian Journal of Statistics* 6(2), 65–70 (1979), stable DOI/JSTOR identifier
`10.2307/4615733`.

**Source result:** a step-down procedure controls the probability of at least one false rejection
for any configuration of true hypotheses using valid p-values; it does not need favorable
independence.

**INT-R10 verdict:** correct. PolicyOS has no canonical family of valid p-values or step-down
procedure, so Holm is a future option, not a live theorem.

### 4.3 Online FWER

**Primary source:** Jinjin Tian and Aaditya Ramdas, “Online Control of the Familywise Error Rate,”
*Statistical Methods in Medical Research* 30(4), 976–993 (2021), DOI
`10.1177/0962280220983381`, arXiv `1910.04900`.

**Source result:** online Bonferroni-style control extends to an a-priori unbounded sequence;
stronger adaptive procedures in the paper rely on independent or locally dependent p-values.

**INT-R10 verdict:** correct. Predictable nonnegative allocations transfer as an accounting
principle. The paper does not supply valid PolicyOS p-values or an adaptive repair theorem.

### 4.4 Pocock, O'Brien–Fleming, and Lan–DeMets

**Primary sources:**

- Pocock (1977), DOI `10.1093/biomet/64.2.191`;
- O'Brien and Fleming (1979), DOI `10.2307/2530245`, PubMed `497341`;
- Lan and DeMets (1983), DOI `10.1093/biomet/70.3.659`.

**Source results:** repeated analyses are parts of one overall trial procedure. Pocock's model is
one accumulating two-treatment comparison; O'Brien–Fleming fixes a maximum number of analyses and
accumulating chi-square statistic; Lan–DeMets spends type-I error as a function of information time
and past/current decision times.

**INT-R10 verdict:** correct and reasoned, not asserted. Pre-allocation, total accounting, and early
stopping transfer. Their clinical critical values and information-time boundaries do not become a
cross-problem theorem for heterogeneous design problems.

### 4.5 Confidence sequences and e-processes

**Primary sources:** Howard et al. (2020, 2021), DOIs `10.1214/18-PS321` and
`10.1214/20-AOS1991`; Ramdas, Grünwald, Vovk, and Shafer (2023), DOI
`10.1214/23-STS894`.

**Source results:** time-uniform validity is relative to a specified process and filtration;
predictability and supermartingale/e-process conditions support optional stopping or continuation.

**INT-R10 verdict:** correct. An anytime-valid process does not automatically validate selection
among repaired implementations after observing earlier family outcomes.

### 4.6 E-value multiplication and merging

**Primary sources:**

- Vovk and Wang, “E-values: Calibration, Combination, and Applications,” DOI
  `10.1214/20-AOS2020`, arXiv `1912.06116`;
- “Merging Sequential E-values via Martingales,” arXiv `2007.06382`; and
- “True and False Discoveries with Independent and Sequential E-values,” arXiv `2003.00593`.

**Exact conditions:**

- arithmetic averaging merges e-values for the **same null** under arbitrary dependence;
- products/martingale mergers are valid for independent e-values or sequential e-values satisfying
  the required conditional expectation/martingale conditions; and
- multiple-testing gains require a family procedure and the paper's independent or sequential
  validity structure.

**INT-R10 verdict:** “not automatic” is correct, not an under-claim. The repository could in
principle satisfy the conditions only after it had owner-verified e-values bound to the correct
null/error polarity, a declared filtration or verified independence relation, and a canonical
merger whose target is strong control of any false authority promotion. The pinned registry has
none of those cross-scope objects and marks the relevant owner theorem unavailable.

### 4.7 Sidak/product correction

**Primary source:** Zbyněk Sidak, “Rectangular Confidence Regions for the Means of Multivariate
Normal Distributions,” *JASA* 62(318), 626–633 (1967), DOI
`10.1080/01621459.1967.10482935` / JSTOR `2283989`.

**Source result:** for multivariate-normal coordinates, a rectangle constructed for independence is
conservative under the dependence covered by Sidak's normal rectangle inequality.

**Precision required:** the familiar product threshold
`1 - (1-alpha)^(1/m)` is exact for independent component tests. The cited 1967 result supports a
broader conservative Gaussian rectangle statement, not an arbitrary positive-dependence rule and
not arbitrary heterogeneous authority events.

**INT-R10 verdict:** the non-transfer conclusion is correct. Its shorthand “Sidak/product requires
joint structure” should explicitly distinguish independence from multivariate-normal rectangle
structure.

### 4.8 Selective inference

**Primary source:** Fithian, Sun, and Taylor, “Optimal Inference After Model Selection,” arXiv
`1410.2597`.

**Source result:** valid post-selection inference must account for the selection event and the model
under which conditional inference is performed.

**INT-R10 verdict:** correct. It constrains what a first-passing result means; it does not by itself
supply the PolicyOS family risk owner or a population-generalization theorem.

### 4.9 Empirical calibration

The external ledger does not import a historical base rate. The repository evidence at
`universal-policy-design-system-vision-and-organizing-rules.md:390-398` shows no positive governed
design and an unbuilt D3.8 gate. The “unavailable” verdict is correct.

---

## 5. Findings

### INT-R10-F-001 — GY-GAP2 is cited through frontmatter 32 times

- **Severity:** `material`
- **Disposition:** replace every `GY-engine-subordination.md:1-10` citation with the substantive
  `:2439-2463` range, or with a narrower subrange for the exact claim.
- **Why material:** requirement 8 demands live reproducibility. The most important missing-owner
  fact repeatedly routes a verifier to metadata rather than evidence.

### INT-R10-F-002 — Pre-execution burn citations end before the durable append

- **Severity:** `material`
- **Disposition:** retain `:1301-1364` for local ordinal/spend calculations; use `:1356-1382` or a
  containing range when asserting the `started` append precedes owner execution.
- **Why material:** pre-execution enforcement is a theorem premise, not incidental implementation
  detail.

### INT-R10-F-003 — Other repository anchors are substantively adequate

- **Severity:** `commendation`
- **Disposition:** preserve the accurate N9 scope, registry, refusal, schedule, INT-R1, custody
  kernel, and proving-ground anchors after correcting the two repeated classes above.

### INT-R10-D-001 — The external transfer ledger is substantially correct

- **Severity:** `commendation`
- **Disposition:** preserve weighted-union, Holm, group-sequential, anytime-valid, e-value,
  selective-inference, and no-empirical-calibration dispositions.

### INT-R10-D-002 — Sidak conditions need a precise split

- **Severity:** `minor`
- **Disposition:** state exact product control under independence separately from the conservative
  multivariate-normal rectangle inequality. Do not summarize either as generic “positive
  dependence.”

### INT-R10-D-003 — “E-values are not automatic” is the correct repository verdict

- **Severity:** `commendation`
- **Disposition:** preserve. A future e-value route must prove target alignment, conditional
  e-validity or independence, filtration, and a repository-owned merger.

---

## 6. Citation verdict

No cited primary source was nonexistent or materially misattributed. The literature review does not
cause the `NO_GO`. The decisive failure is internal: INT-R10 correctly imports conservative event
composition, then discards the pinned owner's exact schedule structure when claiming its
`3 * delta` bound is sharp.