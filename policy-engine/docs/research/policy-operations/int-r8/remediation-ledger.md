---
title: "INT-R8 bounded remediation ledger"
research_id: INT-R8
artifact_role: remediation-ledger
status: accepted_narrow_scope
remediation_conformance: pending_independent_delta_verification
research_only: true
repository: DenisKopylov/polisyos
baseline_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
audited_head: 90b372964d29a9e97605a6ef733ef03ffe7938d2
amendment_head: 92b8773fe6da985b9803723d12c07233d6b90876
verification_commit: ead4aca36f94d6014879c9f70b1074800c4ffabf
remediation_branch: research/int-r8-remediation
prepared_at: 2026-08-04
amended_after_audit: research/int-r8-independent-audit@f45f338f9d9b0de94edc16efbc334789e70e34e2
remediated_after_verification: research/int-r8-amendment-verification@ead4aca36f94d6014879c9f70b1074800c4ffabf
authoritative_for:
  - authoring-level disposition of verification findings INT-R8-V-003 through INT-R8-V-006
  - exact fixture and denominator delta from the verified amendment
  - regression evidence for the nineteen audit commendations and nine already-conforming revisions
  - entry point for independent delta-only remediation verification
may_not_use_for:
  - production_implementation_authorization
  - final_wire_schema_package_database_serialization_or_api_contract
  - canonical_owner_appointment
  - authority_grant
  - capability_claim
  - benchmark_passage
  - legal_compliance_or_institutional_competence_conclusion
  - permission_to_publish_a_governed_result
  - opening_the_first_public_record_gate
  - automatic_amendment_of_any_plan_or_system_design_decision
  - signature_algorithm_or_key_policy_selection
  - numeric_disclosure_bound
---

# INT-R8 bounded remediation ledger

## 1. Scope, method, and standing

This remediation answers only verification findings `INT-R8-V-003` through `INT-R8-V-006`.
It adds the missing fixture evidence and splits the one non-atomic row. It does not alter the
research theorem, semantic relations, threat registry, capability map, INT-R7 interface, external
source treatment, or repository orientation.

Ordinary GitHub DNS remained unavailable in the execution environment. Exact-ref reads, branch
creation, Markdown writes, and read-back verification used the connected GitHub interface. No
workflow, encoded upload fragment, staging directory, base64 repository payload, or
self-executing automation was added.

**Standing remains `accepted_narrow_scope`.** The four verification gaps are closed at authoring
level below and remain pending independent delta verification. No numerical disclosure claim is
issued, and the first-public-governed-record gate remains closed.

## 2. Four bounded closures

| Verification finding / revision | Exact change | Controlling evidence | Closure test |
|---|---|---|---|
| `INT-R8-V-003` / R4 | Added `F21-D`, an empty-consistency-set fixture, and `F21-E`, an unsafe sampled-approximation fixture. Both have exact blocked outcomes and typed non-established/model-inconsistent statuses. | `policy-engine/docs/research/policy-operations/int-r8/falsifier-suite-and-integration-handoff.md:145-149` | Neither an empty model nor a sampled search that finds no witness can inherit `lossy_but_safe`. |
| `INT-R8-V-004` / R5 | Added `G05-B`, which admits an unknown external-copy possibility, records `external_history_not_established`, and emits only a `bounded_to_declared_release_family` claim. | `policy-engine/docs/research/policy-operations/int-r8/falsifier-suite-and-integration-handoff.md:179-184` | Unknown external history limits the proposition without being treated as complete and without blocking the bounded controlled-family claim. |
| `INT-R8-V-005` / R7 | Added `G04-B`, a positive two-event condensation fixture retaining both event references, all three bound effect classes, and both required order edges. | `policy-engine/docs/research/policy-operations/int-r8/falsifier-suite-and-integration-handoff.md:177-184` | The result is green only with every declared effect and order edge present; deleting any one invokes the existing materiality or procedural-order block. |
| `INT-R8-V-006` / R9 | Replaced bundled `F09-A` with `F09-A`, `F09-B`, and `F09-C`: rejected-set removal, conflict-row removal, and consensus-label broadening are now separate mutations under immutable family `F09`. | `policy-engine/docs/research/policy-operations/int-r8/falsifier-suite-and-integration-handoff.md:120-122` | Each row changes one fixture field or collection and has one exact expected issue-code set. |

No family ID was added or removed. `F01`-`F30` and `G01`-`G05` remain the controlling family
identities.

## 3. Recomputed denominators

### 3.1 Red fixtures

The verified amendment contained 67 red rows. The remediation changes that denominator by four:

1. replacing one bundled F09 row with three atomic rows adds `3 - 1 = 2`;
2. adding F21-D and F21-E adds `2`; and
3. no other red row is added or removed.

Therefore:

`67 + 2 + 2 = 71` atomic red subfixtures.

The complete family-by-family row count is:

| Families | Row counts |
|---|---|
| F01-F05 | `2 + 3 + 5 + 1 + 4 = 15` |
| F06-F10 | `4 + 2 + 2 + 3 + 2 = 13` |
| F11-F15 | `2 + 1 + 2 + 2 + 1 = 8` |
| F16-F20 | `1 + 4 + 3 + 1 + 3 = 12` |
| F21-F25 | `5 + 2 + 1 + 2 + 3 = 13` |
| F26-F30 | `2 + 2 + 2 + 2 + 2 = 10` |
| **Total** | **`15 + 13 + 8 + 12 + 13 + 10 = 71`** |

The family denominator remains **30/30**.

### 3.2 Green controls

The verified amendment contained five green rows. G04-B and G05-B add two controls without
adding a family:

`5 + 2 = 7` atomic green controls across **5/5** green families.

The family distribution is `G01=1`, `G02=1`, `G03=1`, `G04=2`, `G05=2`; total `7`.

### 3.3 Branch-wide count-site walk

The complete controlling-artifact universe before this ledger was seven Markdown artifacts:
primary report, orientation ledger, external source ledger, formal analysis, semantic contract,
falsifier suite, and amendment ledger. A complete 7/7 exact-ref read found **five affected suite
count statements in two files**:

1. suite red denominator;
2. suite green denominator;
3. suite standing sentence;
4. amendment-ledger R9 row; and
5. amendment-ledger `INT-R8-VI-001` row.

All five now state the derived `30 families / 71 red rows / 5 green families / 7 green rows`
quantities at their appropriate scope. No blind replacement was used.

The unrelated orientation census remains exactly:

`67 runtime + 12 scientist + 27 remainder = 106 distinct token-containing Python files`.

That `67` is a source-file partition and was not changed.

## 4. Complete R9 atomicity sweep

The complete red manifest denominator is **71/71 rows**. Each row was inspected as one mutation
over the fixed baseline.

- F09 now contributes three rows and each changes one collection or scalar.
- The other 68 rows retain the one-mutation interpretation independently confirmed by the prior
  verifier, including the coalition setup in F04 as one declared joint-observation mutation.
- No row contains an alternative issue code, `or`, `and/or`, a bare `Red`, or an unbound
  materiality premise in an expected-value slot.
- Every row has exactly the eight declared columns and an exact `loss_outcome`,
  `evaluation_status`, issue-code set, affected-claim set, and reconstruction status.

**Sweep result: 71/71 red rows satisfy the controlling one-mutation rule.**

## 5. R4 safe-verdict sweep

The complete fixture denominator after remediation is **78/78 rows**: 71 red plus 7 green.

- All 71/71 red rows return `blocked_material_omission`.
- F21-D is the sole empty-consistency-set fixture and returns
  `model_observation_inconsistent`, never safe.
- F21-E is the sole sampled/unproved-approximation fixture and returns
  `not_established_unowned_approximation`, never safe.
- The timeout path remains F21-A and is blocked.
- None of the 7/7 green rows uses an empty set, timeout, unsupported theory, out-of-model channel,
  sampled search, heuristic score, posterior threshold, or unproved approximation as evidence of
  non-reconstruction.
- G05-B is green only for a proposition explicitly limited to the declared release family; it is
  not a universal reconstruction or secrecy pass.

**Sweep result: 0/78 fixture rows permit an unproved approximation to inherit a safe verdict.**

## 6. Regression statement — nine previously conforming revisions

The remediation does not alter the propositions that the verifier found conforming.

| Revision | Preserved evidence |
|---|---|
| R1 | Capability reality remains prerequisite-valid in `int-r8-compression-loss-and-disclosure.md:120-140` and suite `:219-236`; the numerical accountant remains not a missing capability. |
| R2 | Correct line/occurrence and caller reproduction remains in `int-r8/orientation-ledger.md:41-91,134-166,257-342`. |
| R3 | The narrowed theorem and deterministic-QIF path remain in the primary report `:48-90,142-157`, source ledger `:93-149`, and formal analysis `:40-85`. |
| R6 | The open channel registry and F26-F30 remain in the formal analysis `:308-382` and suite `:159-168`. |
| R8 | The single canonical reason relation remains in the semantic contract `:253-292`; F05 remains atomic in suite `:108-111`. |
| R10 | The complete content-side proof interface and issuer-authenticity separation remain in primary `:324-355`, semantic `:429-459`, formal `:425-435`, and suite `:238-249`. |
| R11 | The five-file invocation set, four caller files, and separate re-export classification remain in orientation `:134-166,257-342`. |
| R12 | Living-as-of and narrowed source-custody treatment remains in the external source ledger `:40-91`. |
| R13 | Concrete limitation carriers remain in orientation `:218-241` and semantic `:59-99`. |

## 7. Regression statement — nineteen commendations

All **19/19** audit commendations remain reachable in controlling text.

| Commendation | Preserved strength and evidence |
|---|---|
| `INT-R8-I-001` | Exact file-size and four-audience orientation remains at `int-r8/orientation-ledger.md:56-106`. |
| `INT-R8-I-003` | The disjoint `67/12/27=106` denied-use file census remains at orientation `:108-132`. |
| `INT-R8-I-005` | Named-token source absence remains narrowly qualified at orientation `:168-191`. |
| `INT-R8-II-001` | Primary-source public-administration grounding and transfer limits remain at source ledger `:60-91,150-184` and primary `:158-192`. |
| `INT-R8-II-004` | DP remains non-transferable by analogy while deterministic QIF remains open at source `:93-149` and formal `:40-68`. |
| `INT-R8-III-001` | Refusal of a current canonical number remains at primary `:48-90` and formal `:40-85`. |
| `INT-R8-III-003` | Exact non-uniqueness remains Boolean and number-free at formal `:247-306`; F21-D/E strengthen, rather than weaken, its failure boundary. |
| `INT-R8-III-005` | Actual-prefix induction remains at formal `:247-306`. |
| `INT-R8-IV-001` | Conditional consistency-set and strict-coalition definitions remain at formal `:153-193`. |
| `INT-R8-IV-004` | Existing side-channel breadth and the open registry remain at formal `:308-328`. |
| `INT-R8-V-001` | Bare delta and hidden negative terminals remain categorical at semantic `:383-408`. |
| `INT-R8-V-005` | Receipt reuse-first, projection-only, empty-authority, non-lattice semantics remain at semantic `:40-99`. |
| `INT-R8-VI-002` | F04, F12, F19, F24, F25 and all five green purposes remain at suite `:106-197`; G04-B and G05-B add positive witnesses without replacing them. |
| `INT-R8-VII-001` | `INT-K02`, `INT-K06`, `INT-K08`, `S0-K07`, and `INT-K05` remain applied in the confirmed direction at semantic `:383-408` and primary `:92-118`. |
| `INT-R8-VII-002` | Exact adaptive prefix discipline remains compatible with `INT-K04`/`INT-K07` at formal `:247-306`. |
| `INT-R8-VIII-001` | INT-R8 remains on the content side and selects no proof mechanics at primary `:324-355` and semantic `:429-459`. |
| `INT-R8-IX-002` | Existing projection/public-export capability remains visible at primary `:120-140` and semantic `:59-99`. |
| `INT-R8-X-001` | Effective research/non-use frontmatter remains on every artifact; the two modified files and this ledger additionally carry the exact remediation binding. |
| `INT-R8-X-002` | `accepted_narrow_scope` remains the substantive standing, with independent remediation verification still required and the first-public-record gate closed. |

## 8. Change boundary and verification entry point

Relative to amendment head `92b8773fe6da985b9803723d12c07233d6b90876`, the intended complete
change set is:

1. modified `int-r8/falsifier-suite-and-integration-handoff.md`;
2. modified `int-r8/amendment-ledger.md`; and
3. added `int-r8/remediation-ledger.md`.

All are Markdown. No other research proposition is intentionally changed.

A delta verifier should mechanically check:

1. F21-D and F21-E exact values;
2. G05-B's limiting, non-blocking boundary;
3. G04-B's complete effects and order edges;
4. F09-A/F09-B/F09-C atomicity;
5. `30/71/5/7` at every affected count site;
6. the 71/71 atomicity and 0/78 unsafe-pass sweeps; and
7. the regression tables above.

## 9. Authoring-level closure

The four verified gaps are closed in the controlling authoring artifacts. This statement is not
independent conformance. Until delta verification reads the branch back, the remediation remains
`pending_independent_delta_verification`.

The result continues to authorize no implementation, owner, schema, proof construction,
publication, legal conclusion, benchmark passage, first public record, or numerical disclosure
bound.