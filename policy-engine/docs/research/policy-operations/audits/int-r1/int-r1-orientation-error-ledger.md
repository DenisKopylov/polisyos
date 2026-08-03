---
title: INT-R1 — Orientation Error Ledger
status: delivered
kind: independent-audit
research_task: INT-R1
result_type: accepted_narrow_scope
audit_verdict: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-independent-audit
audited_branch: research/int-r1-obligation-coverage
audited_commit: 82e136a8d528cb24e661973ac1a8ea4fb6f1c80f
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-03
authoritative_for:
  - independent verification of the repository facts supplied as orientation to INT-R1
  - identification of supplied-context errors that could affect consolidation
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - legal compliance conclusion
  - benchmark passage
  - merger or release approval
research_only: true
---

# INT-R1 — Orientation Error Ledger

## 1. Method and result

Each supplied orientation claim was rechecked against the exact baseline
`d152565dcc11cea457dacd61fadc6e15dc3ecc86`. Historical comparisons used
`4813b49f6ce14e8debf3aaea096f0967d38d9768`; audited-work claims used
`82e136a8d528cb24e661973ac1a8ea4fb6f1c80f`. The audit did not treat the
researcher's correction as evidence for itself.

**Result:** one supplied fact was false and was correctly caught by the researcher: the
obligation enum has 15 members, not 14. No second material orientation error was found. Two
claims require wording discipline: “dominated by refusals” is a qualitative summary of profile
kinds rather than a status computed by the registry, and “0 of 13” describes the pinned
proving-ground/corpus state rather than proving that no unrelated experimental execution ever
occurred.

## 2. Claim-by-claim ledger

| ID | Supplied orientation claim | Independent evidence at pinned baseline | Verdict | Effect on audited research |
| --- | --- | --- | --- | --- |
| OR-01 | `main` moved 121 commits from `4813b49f6` to `d152565dc`. | Git comparison reports `ahead_by=121`, `behind_by=0`, with merge base `4813b49f6ce14e8debf3aaea096f0967d38d9768`. | **verified** | The researcher correctly refused to reuse the old Stage-0 baseline. |
| OR-02 | `PromotionObligationClass` has 14 members. | `policy-engine/src/polisyos/pdc/_impl/gy_waist.py:218-235` contains 15 values: `syntax`, `type`, `slot`, `param`, `coupling`, `effect`, `identification`, `calibration`, `measurement`, `data`, `implementation`, `equilibrium`, `normative`, `eval_safety`, and `value`. `VALUE = "value"` is the omitted member. | **false — caught by researcher** | The report's 15-member correction is correct and load-bearing. Any benchmark or denominator statement using 14 is invalid. |
| OR-03 | The enum's docstring calls it a “Universal N9 obligation-class denominator.” | Exact text at `policy-engine/src/polisyos/pdc/_impl/gy_waist.py:218-220`. | **verified** | Supports the denominator analysis, but the adjective “universal” is not evidence of worldly completeness. |
| OR-04 | `confidence_ledger.py` is approximately 4,782 lines. | The final executable statement occupies lines 4780-4782; a fetch beginning at 4791 is empty. | **verified exactly at 4,782 lines** | Non-substantive orientation detail; no effect on the result. |
| OR-05 | `CONDITIONAL_VALIDITY_CLAUSE` says the δ claim is conditional on obligation completeness and validator soundness. | `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:37-45` contains the formula and the explicit conditionality sentence. | **verified** | Core premise of INT-R1. |
| OR-06 | `_MAINTAINED_ASSUMPTIONS = ("obligation_completeness", "validator_soundness")` and the assumptions are typed/carried into records. | Constant at `confidence_ledger.py:47-50`; record classes and receipt/root structures carry the assumptions in `:500-1010`; durable emissions include them at `:2463-2488`. | **verified** | The repository labels the gap honestly but does not discharge it. |
| OR-07 | The ledger enforces a total partition over the enum with no duplicates and weights summing to exactly 1. | `confidence_ledger.py:337-369` compares configured classes with `set(PromotionObligationClass)`, rejects duplicate/omitted membership with `obligation_partition_not_total`, and rejects a non-unit sum with `obligation_pool_weights_do_not_sum_to_one`. | **verified** | Proves internal allocation totality relative to the enum, not completeness of the external obligation universe. |
| OR-08 | The split is content-bound as `obligation_split_hash`. | Root/receipt construction and durable output bind the split and related policy material at `confidence_ledger.py:500-1010`, `:2463-2488`. | **verified** | Prevents silent risk-allocation drift; does not discover missing obligations. |
| OR-09 | The live registry has two `basel_square_v1` schedules and five proof profiles: two `ineligible_v1`, one `owner_theorem_unavailable_v1`, one `deterministic_owner_v1`, and one `closed_constant_unit_e_process_v1`. | `policy-engine/architecture/production_quality/confidence_ledger.toml:1-52` contains two Basel-square schedules; `:53-89` contains the five profile kinds in exactly that distribution. | **verified** | Confirms that only one current profile is a real e-process. |
| OR-10 | The live registry is “dominated by refusals.” | Four of five proof profiles are ineligible, unavailable-owner, or deterministic rather than a statistical e-process. The TOML does not itself compute a field named `dominated_by_refusals`. | **verified as a qualitative summary, not a registry status** | Consolidation should quote the profile-kind counts, not promote the phrase into a typed capability label. |
| OR-11 | The proving ground stands at 0 of 13 with `useful_design_rate = 0`. | `policy-engine/docs/plans/active/layer3-slices/G5-first-proving-ground-conversion.md:430-500` records a current W12.D run with 13 typed blockers, zero runtime useful-design cases, and zero grounded conversions. `policy-engine/architecture/policy_design_case/layer3_g5_readiness_manifest.json` records `g5_grounded_conversion_count=0`, `g5_useful_design_credit_count=0`, `g5_governed_promotion_input_count=0`, `g5_conversion_outcome="unchanged_blocker"`, and `g5_envelope_expansion_rate=0.0`. | **verified for the pinned proving-ground/corpus state** | There is no empirical miss-rate basis available from successful governed promotions. The claim should not be generalized beyond the evidenced corpus snapshot without a separate history census. |
| OR-12 | The registry/corpus history cannot calibrate an empirical base rate of missed obligations. | The current profile distribution is not a sequence of real obligation-discovery outcomes, and the pinned proving-ground state contains no positive governed conversion/useful-design observation. | **verified** | Any numeric probability of the unknown remainder would be authored rather than empirically estimated. |
| OR-13 | RACE-HOG-PODS §12.2 defines a 15-family obligation union and tracks `ObligationCompletenessRisk_t(x, scope)`. | `policy-engine/docs/reference/policy-design-search-RACE-HOG-PODS-v3.2-spec.md:774-798` includes the 15 families, including `O_value`, and the named risk. | **verified** | Also independently confirms that the supplied 14-member count was wrong. |
| OR-14 | RACE-HOG-PODS Theorem 1 assumption A4 is validator soundness relative to the declared obligation language. | `policy-design-search-RACE-HOG-PODS-v3.2-spec.md:1635-1654` states A4 exactly in that form and conditions the false-promotion result on maintained assumptions. | **verified** | The external target spec formalizes, but does not close, the semantic adequacy dependency. |
| OR-15 | The PolicyOS adoption record says the target spec formalizes the hardest open problem without closing it and that the theorem's teeth are empirical. | `policy-engine/docs/system-design-decisions/policy-design-search-target-spec.md:155-177`. | **verified** | The INT-R1 report must not claim that merely restating A4 as a premise discharges it. |
| OR-16 | P29 contains a stopping point for generic traversal over the actual source of truth. | `policy-engine/docs/reference/policy-design-case-failure-patterns.md:70-75` states the generic actual-object/source rule and rejects another meta-level absent a present gap or non-generic enumeration. | **verified** | It closes the mechanical traversal regress for owned sources, not the external-world source-selection problem. |
| OR-17 | The ratified kernel includes no-authority-by-observation/projection, band-sensitive fail-closed scope, evidence-validity, and bounded-passage constraints. | `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:43-116`, `:164-212`. | **verified** | These constraints correctly bind the coverage sketch. |
| OR-18 | The Atlas plan contains a waiting DS17 placeholder for the INT-R1 conditional chip, and DS18 owns perturbation rendering. | The long revision line at `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:7` records the INT-R1/DS17 and perturbation dependencies; the surface constitution separately denies projection authority at `policyos-atlas-surface-constitution-and-frontend-vision.md:130-260`. | **verified** | Atlas is a consumer; it cannot construct the coverage decision. |
| OR-19 | The GY plan, Atlas plan, and Wave-2 backlog frontmatter do not parse as YAML because long unquoted `revised:` values contain `: `. | `GY-engine-subordination.md:7` contains several unquoted colon-space sequences; `POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:7` does likewise; `policy-operations-and-real-world-runtime-backlog.md:7` includes unquoted `Counts: ...`. YAML plain scalars cannot contain an unquoted colon followed by space. | **verified** | The researcher correctly read those lines as prose and did not modify them. |
| OR-20 | The research branch shape is six commits, six new Markdown files, 4,242 insertions, no code/test/existing-document modifications. | Baseline-to-audited-commit comparison reports exactly six added `.md` files and no modified/deleted files; additions total 4,242. | **verified** | Scope discipline passed. |

## 3. Error disposition

### INT-R1-I-001 — supplied denominator count was wrong

- **Severity:** material
- **Disposition:** corrected by the audited deliverable; preserve the correction.
- **Evidence:** `gy_waist.py:218-235`; RACE-HOG-PODS §12.2 independently lists the value family.
- **Audit consequence:** all downstream references must use 15. This was an orientation error,
  not a repository change from 14 to 15.

### INT-R1-I-002 — no uncaught material supplied-context error found

- **Severity:** commendation
- **Disposition:** verified.
- **Evidence:** OR-01 and OR-03 through OR-20.
- **Audit consequence:** the researcher did not silently inherit another false load-bearing
  premise from the supplied orientation.

### INT-R1-I-003 — proving-ground statement needs scope wording

- **Severity:** minor
- **Disposition:** clarify during consolidation.
- **Evidence:** G5 plan and readiness manifest establish the pinned corpus/proving-ground state,
  not an exhaustive historical query over every experimental invocation.
- **Required wording:** “At the pinned proving-ground/corpus snapshot: zero grounded conversions
  and zero useful-design credit across the 13-case W12.D state.”

## 4. Consolidation instruction

The orientation baseline is usable after one correction: **15**, never 14. Preserve the exact
profile counts and the scoped proving-ground evidence. Do not turn qualitative phrases such as
“dominated by refusals” into status labels, and do not treat the absence of positive corpus
observations as an estimated probability of omission.