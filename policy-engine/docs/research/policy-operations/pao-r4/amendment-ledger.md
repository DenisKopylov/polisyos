---
title: PAO-R4 amendment ledger after hostile independent audit
research_id: PAO-R4
artifact_role: amendment-ledger
status: amended_research
research_only: true
repository: DenisKopylov/polisyos
audited_commit: a27c3da9942b03881dbee1005a8a1e44e5ac44b4
audit_commit: 69182c079fb5dc99808d7cd27874d50433efd5a4
pinned_repository_commit: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
result_standing: GO_WITH_REVISIONS
adoption_status: NO_GO_pending_independent_conformance
authoritative_for:
  - factual disposition of every PAO-R4 independent-audit finding
  - exact research-artifact amendment crosswalk
  - bounded declaration of what was preserved, narrowed, or left for conformance
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
  - modification or supersession of the independent audit
---

# PAO-R4 amendment ledger

## 1. Amendment rule

This ledger does not rewrite or supersede the independent audit. It records the author's response to
every finding at audit head `69182c079fb5dc99808d7cd27874d50433efd5a4` and points to the amended
body where the response landed.

Permitted dispositions are:

- **`accepted`** — the finding is adopted as stated or its commendation is preserved;
- **`accepted_with_variation`** — the defect/result is adopted with an explicitly reasoned narrowing
  or different closure instrument; and
- **`declined_with_reason`** — the finding is not adopted, with evidence. No finding is silently
  omitted.

The research standing remains `GO_WITH_REVISIONS`. The independent audit's `NO_GO` for adoption
remains controlling until a separate conformance verification evaluates this amendment. No
capability, owner, authority, or implementation standing is upgraded here.

## 2. Count reconciliation

The audit registered **30 findings**. This ledger contains **30 dispositions**:

| Disposition | Count |
|---|---:|
| `accepted` | 27 |
| `accepted_with_variation` | 3 |
| `declined_with_reason` | 0 |
| **total** | **30** |

The three variations are `PAO-R4-III-001`, `PAO-R4-IV-003`, and `PAO-R4-V-001`. In each case the
amendment preserves the load-bearing concern while narrowing the claim or refusal predicate to the
evidence and the architect's ruling.

## 3. Complete finding disposition register

| Audit finding | Disposition | Exact response | Where it landed |
|---|---|---|---|
| `PAO-R4-I-001` | `accepted` | Corrected `anonymi` to seven all-source files and six Python files; named the omitted CSV fixture and both denominators. | `pao-r4/orientation-ledger.md` §§1, 3.1, 3.4 |
| `PAO-R4-I-002` | `accepted` | Replaced the unexecuted positive-token placeholders with the architect-supplied complete-tree result: 106 Python files, 794 matching lines, 903 occurrences; retained “not separately supplied” only for the all-source positive line/occurrence columns. | `pao-r4/orientation-ledger.md` §§1, 3.1–3.2 |
| `PAO-R4-I-003` | `accepted` | Preserved the confirmed source shape: disjoint 67 runtime + 12 scientist + 27 remainder, seven `aggregate_only` files, and true all-source zeroes for the three absent concepts. | `pao-r4/orientation-ledger.md` §§3.2–3.5, 6 |
| `PAO-R4-II-001` | `accepted` | Replaced global “not weaker” language with the bounded statement “not narrower on the material-reliance / formal-finality trigger,” and expressly excluded comparison across rights, duties, remedies, competence and procedure. | primary report §9; `pao-r4/external-primary-source-and-transfer-ledger.md` §§1, 3, 7 |
| `PAO-R4-II-002` | `accepted` | Pinned the Canadian Directive to instrument `id=32592`, fourth-review version/date 2025-06-24 and its official archive chain; pinned the contemporaneous AIA questionnaire to `canada-ca/aia-eia-js@a10e7f8c...`; replaced current use of M-24-10 with M-25-21 and recorded that M-25-21 rescinds/replaces it. | external-source ledger §§2, 4.1–4.2, 5 |
| `PAO-R4-II-003` | `accepted` | Preserved and strengthened the non-compliance rule in frontmatter, the use rule, every transfer row, and the final limitation. | external-source ledger §§1, 3–8 |
| `PAO-R4-II-004` | `accepted` | Preserved substantive use of each legal/statistical source and retained the source-specific transfer purpose. | external-source ledger §§3–7 |
| `PAO-R4-III-001` | `accepted_with_variation` | Accepted the contract defect but not the audit's claim that the formal empirical tuple admitted normative rules. In the original §3, `Φ(D_B)=θ` was a functional over a population data-generating/causal object; a normative rule was not an object of that tuple. The mismatch was that §§4.2–4.3 nevertheless grouped general rules with empirical estimates and refused executable rules. The amendment defines E/G/X/S, applies non-entailment only to E, permits G as rule-level input under external authority/procedure, and scopes refusal to authority-to-determine rather than executability. | primary report §§3.1–3.3, 4.1–4.4; comparative models §§1, 5–6; falsifiers F-07/F-08 |
| `PAO-R4-III-002` | `accepted` | Added the complete `P37` predicate-provenance table, froze classifications at admission, made last-three predicate classes non-positive, replaced self-reported counterfactual materiality with conservative consultation, and added falsify-the-declaration probes. | primary report §§3.4–3.5; falsifiers F-20/F-21; integration handoff §3.2 |
| `PAO-R4-III-003` | `accepted` | Added `individualizable(a,H)` and deterministic treatment of singleton cells, complete deterministic partitions, differencing families and equivalent pointwise surfaces. | primary report §3.3; falsifiers F-05/F-06 |
| `PAO-R4-III-004` | `accepted` | Preserved empirical non-entailment for non-pointwise class-E claims: population membership does not supply individual facts, reason, procedure or authority. | primary report §3.2; claim-boundary table §11 |
| `PAO-R4-IV-001` | `accepted` | Replaced the three-location heading with four explicit locations: artifact-local, export-context with named `H`, downstream use-context, and outside-boundary/not observable. Each predicate now names its inputs and incomplete result. | primary report §§6.1–6.4; comparative models §4 |
| `PAO-R4-IV-002` | `accepted` | Bounded every positive to a named governed integration boundary and interval; stated that complete in-boundary evidence cannot establish institution-wide non-use; placed audit Scenario S-1 outside the positive claim. | primary report §§1, 3.4–3.5, 6.4, 7.3, 11 |
| `PAO-R4-IV-003` | `accepted_with_variation` | Preserved the audit's correction that voluntary evidence can support narrower observed claims, while keeping the architect-confirmed impossibility exactly strong for complete non-use. Added an explicit claim lattice for incident, lower-bound and sampled-frame claims. | primary report §7.4; comparative models §8; falsifiers F-12/F-13 |
| `PAO-R4-IV-004` | `accepted` | Preserved detection location as the organising principle and refined it rather than replacing it. | primary report §6; comparative models §§3–4 |
| `PAO-R4-IV-005` | `accepted` | Preserved the observational-equivalence proof: no report under compliant non-use and prohibited use followed by silence cannot establish a complete non-use firewall claim. | primary report §7.4; comparative models §8; falsifier F-12 |
| `PAO-R4-V-001` | `accepted_with_variation` | Accepted that the executable-rule refusal was overbroad, applying the architect's narrower diagnosis: non-entailment never justified refusal of normative G. Replaced executability with semantic class and authority effect. Artifact C is allowed as rule-level input; identical-syntax empirical X is refused. | primary report §§3.1–3.3, 4.1–4.4; comparative models §§5–6; falsifiers F-07/F-08 |
| `PAO-R4-V-002` | `accepted` | Preserved candidate-band computation and useful population planning. Added an explicit authority-band paragraph explaining why an executability predicate would forbid PolicyOS's own governed output. | primary report §4.1; falsifier F-19; comparative models §6 |
| `PAO-R4-VI-001` | `accepted` | Bounded the positive to instrumented/reconciled channels; classified cognitive/manual reliance outside instrumentation as outside-boundary and non-observable; retained refusal for actionable classes with material off-ledger paths. | primary report §§3.4, 6.4, 11; falsifier F-18 |
| `PAO-R4-VI-002` | `accepted` | Removed operator counterfactual materiality as the gate predicate. Consultation during a protected action is conservatively treated as use; an independently validated counterfactual may support only a narrower analytical claim. | primary report §§3.4–3.5, 7.2–7.3; falsifier F-21 |
| `PAO-R4-VI-003` | `accepted` | Preserved returning evidence as semantic content, independent denominator reconciliation, content binding, append-only history and `FIREWALL_CLAIM_NOT_ESTABLISHED` on absence. | primary report §§7.1–7.4; integration handoff §3.5 |
| `PAO-R4-VII-001` | `accepted` | Rewrote F-01 as exact silent purpose drift: allowed planning request/export, later resolved eligibility consultation, mandatory consumer-use `BLOCK_PURPOSE`. Request/export gates cannot satisfy the case. Added remove-property/keep-markers probe. | falsifier suite F-01; suite conformance requirement 3 |
| `PAO-R4-VII-002` | `accepted` | Split conditional worlds into separate fixtures and added reference-class shopping, semantic-purpose synonym, counterfactual reliance laundering, and multi-hop relay. Every manifest row has one detector and one expected verdict. | falsifiers F-01–F-26, especially F-03/F-04, F-10/F-11, F-20–F-24 |
| `PAO-R4-VII-003` | `accepted` | Preserved the commissioned join, parameterized/pointwise rule, projection-narrowing and query-reconstruction attacks, now aligned to E/G/X semantics and one-world outcomes. | falsifiers F-03, F-06/F-08, F-09, F-10 |
| `PAO-R4-VIII-001` | `accepted` | Preserved `PV-K04` as an inherited ratified invariant and retained exact denial-union tests; no PAO-R4 re-ratification claim was introduced. | primary report §§2, 4.3, 6.1; comparative models §§2–3; falsifiers F-09/F-16/F-25 |
| `PAO-R4-VIII-002` | `accepted` | Preserved `S0-K05`, `S0-K07`, `S0-K11`, `INT-K02`, the identity ruling and anti-roles. Applied the authority-band lens explicitly and left correction as a PAO-R36 interface obligation. | primary report §§2, 4.1, 12; integration handoff §§1, 5 |
| `PAO-R4-IX-001` | `accepted` | Removed the canonical-owner inference from adjacency. Kept denied-use/projection owners established, stated `public_export.py`'s bounded public role, and reopened the policy-to-case emission chokepoint as an open consolidation decision with alternatives and no appointment. | primary report §10; comparative models §10; integration handoff §§1.1–1.2 |
| `PAO-R4-IX-002` | `accepted` | Preserved prerequisite-safe missing-state usage and the current `absent/unallocated` classification for every PAO-R4-specific component. | primary report §10; orientation ledger §§3.5, 5–6; integration handoff §2 |
| `PAO-R4-X-001` | `accepted` | Added a second durable repository receipt for the amendment payload that names the exact verified payload head, the prior delivery-receipt blob, every amended file blob/line count, and the unavoidable self-reference boundary; final branch state is separately read back after writing. | `pao-r4/amendment-delivery-readback.md`; final completion readback |
| `PAO-R4-X-002` | `accepted` | Preserved wave isolation, the correction restriction-survival interface, complete frontmatter prohibitions, no compliance conclusion, no case-system design, and no capability claim. | primary report §§1–2, 12–13; integration handoff §§5, 7; all amended frontmatter |

## 4. Revision-register crosswalk

| Audit revision | Amendment result | Evidence location |
|---|---|---|
| R1 + R7 | E/G/X/S split; empirical-only non-entailment; authority-scoped refusal; Artifact C versus identical-syntax empirical tree | primary §§3–4; comparative §§5–6; F-07/F-08 |
| R2 | `individualizable(a,H)` and deterministic refusal of Artifacts A/B | primary §3.3; F-05/F-06 |
| R3 | full `P37` table, conservative consultation, declaration-falsification probes | primary §§3.4–3.5; F-20/F-21 |
| R4 | four observation locations and bounded positive claim | primary §§1, 6, 11; comparative §4 |
| R5 | exact silent-purpose-drift F-01 plus remove-property probe | F-01 |
| R6 | 26 one-world cases and A-15–A-18 equivalents | falsifier manifest and F-20–F-24 |
| R8 | supplied complete census with both denominators | orientation §3 |
| R9 | version-pinned Canada sources, current M-25-21, Dawid inference label, narrowed comparison | external-source ledger §§2–7 |
| R10 | open emission-owner decision; no adjacency appointment | primary §10; integration §1.2 |
| R11 | bounded voluntary-evidence claim lattice | primary §7.4; F-12/F-13 |
| R12 | second durable amendment readback | `pao-r4/amendment-delivery-readback.md` |
| R13 | positive/negative claim-boundary table | primary §11 |

## 5. Deliberate non-claims and conformance dependency

This amendment does not:

- claim that the repository implements any amended class, gate, interface, detector or evidence
  chain;
- appoint the policy-to-case emission owner or an external rule/case authority;
- design the case-management workflow, schema, API, database, reason procedure or review system;
- define PAO-R36 correction mechanics, OPS-R14 durability, or S0-GAP-02 evaluation architecture;
- declare legal sufficiency or compliance; or
- convert the amendment into adoption.

Independent conformance must test substance at an exact commit: Artifacts A/B/C, Scenarios S-1/S-2,
the real consumer-gate removal probe, the declaration-falsification probes, exact census/source pins,
and capability/owner non-upgrade. Until that verification, adoption remains `NO_GO`.
