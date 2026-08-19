---
title: PAO-R4 independent audit — claim/evidence ledger
audit_id: PAO-R4
artifact_role: claim-evidence-ledger
status: independent-audit
research_only: true
verified_commit: a27c3da9942b03881dbee1005a8a1e44e5ac44b4
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
authoritative_for:
  - independent mapping of PAO-R4 load-bearing claims to evidence and audit verdicts
  - audit traceability across Pass I through Pass X
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
  - modification of the audited branch
---

# PAO-R4 claim/evidence ledger

## 1. Verdict vocabulary

- **supported** — evidence establishes the claim within its stated boundary;
- **supported with narrowing** — the core holds but wording exceeds evidence;
- **not established** — evidence is incomplete or the proposition depends on an unresolved premise;
- **refuted** — a concrete counterexample or source conflict defeats the claim as written;
- **process-only** — factual delivery evidence, excluded from research standing.

## 2. Repository and orientation claims

| ID | Load-bearing claim | Audited evidence | Verdict | Finding |
|---|---|---|---|---|
| `CE-01` | `may_not_use_for` occurs in 106 Python files partitioned 67 runtime + 12 scientist + 27 remainder | Complete distinct-file searches under `policy-engine/src/polisyos`; disjoint path predicates | **supported** for file count | `PAO-R4-I-003` |
| `CE-02` | The orientation pass supplied files, matching lines and occurrences for every token | `orientation-ledger.md:72-96,151-197@a27c3da9942b03881dbee1005a8a1e44e5ac44b4` leaves positive `may_not_use_for` units `not_established` | **refuted** | `PAO-R4-I-002` |
| `CE-03` | `aggregate_only` appears in seven source files | Complete all-file search; 10 matching lines/10 occurrences | **supported** | `PAO-R4-I-003` |
| `CE-04` | `anonymi*` appears in six files under all `policy-engine/src` | Six Python paths plus one CSV fixture containing `anonymity` | **refuted; all-file count is seven** | `PAO-R4-I-001` |
| `CE-05` | `individual_decision`, `export_gate`, `prohibited_use` each appear in zero source files | Complete exact-token searches below `policy-engine/src` | **supported** | `PAO-R4-I-003` |
| `CE-06` | Existing code declares, propagates and sometimes consumer-enforces denied uses | Core authority-envelope fields, policy-grammar propagation and consumer guard at the pin | **supported in bounded owners** | `PAO-R4-I-003` |
| `CE-07` | The repository already has an individual-decision firewall | Exact zeroes plus absent consumer/return chain | **not claimed by research; correctly absent** | `PAO-R4-IX-002` |

## 3. Formal and semantic claims

| ID | Load-bearing claim | Audited evidence/attack | Verdict | Finding |
|---|---|---|---|---|
| `CE-08` | A population claim is adequately defined by `P=(R_B,B,Φ,θ,L)` | `pao-r4-individual-decision-firewall.md:82-115@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`; object audit finds `D_B`, `Φ`, `θ`, completeness of `B/L`, and class non-degeneracy under-defined | **not established as a decidable type** | `PAO-R4-III-001`, `III-002` |
| `CE-09` | `P ∧ C_B(x)=1 ⊭ I_x` holds for the claim class as stated | Singleton-rate, deterministic-partition and normative-universal-rule counterexamples | **refuted as universal; supported for non-degenerate empirical summaries** | `PAO-R4-III-001`, `III-003`, `III-004` |
| `CE-10` | Arithmetic applicability is not semantic/administrative authority | Empirical group probability/association lacks case facts, rule/procedure and authority | **supported** | `PAO-R4-III-004` |
| `CE-11` | The counterfactual material-contribution test makes individual use observable | Returning interface relies on reported “would action change”; complete logs do not validate the counterfactual | **not established** | `PAO-R4-III-002`, `VI-002` |
| `CE-12` | The useful reverse case—individual determination disguised as population output—is closed by the formal definition | Singleton, pointwise partition and adaptive query constructions satisfy population form | **refuted for formal definition; partly addressed by later gates** | `PAO-R4-III-003` |

## 4. Handoff and refusal claims

| ID | Load-bearing claim | Audited evidence/attack | Verdict | Finding |
|---|---|---|---|---|
| `CE-13` | Default-deny conjunction is a checkable research contract | Class, resolution, executability, basis, monotonicity, purpose, history and evidence predicates are enumerated | **supported as architecture outline; inputs not fully decidable** | `PAO-R4-III-002` |
| `CE-14` | “Anonymized” is model-relative, not an independent permission class | Auxiliary information and composition can resolve purported aggregates | **supported** | `PAO-R4-IV-004`, `V-002` |
| `CE-15` | Every person-resolvable/pointwise artifact whose use cannot be observed must be refused | Observationally equivalent compliant/violating worlds and off-ledger examples | **supported within governed-crossing scope** | `PAO-R4-IV-005`, `V-002` |
| `CE-16` | Every executable general rule is inherently unsafe to cross | Normative universal rule counterexample; report's own `Q` is a competent rule/procedure | **refuted as class-wide claim** | `PAO-R4-III-001`, `V-001` |
| `CE-17` | The refusal list forbids computation/candidate work | F-12 permits population planning; text limits refusal to case-system crossing | **refuted; research preserves candidate band** | `PAO-R4-V-002` |
| `CE-18` | Prohibited-use matrix covers materially adverse and beneficial individual action classes | 13 action/evidence/reason/review/finality purposes, with material-contribution trigger | **supported as broad research taxonomy, subject to rule distinction and semantic synonym closure** | `PAO-R4-VII-002` |

## 5. Detection and returning-evidence claims

| ID | Load-bearing claim | Audited evidence/attack | Verdict | Finding |
|---|---|---|---|---|
| `CE-19` | Violations partition into export-time, use-time-only and not-detectable classes | Primary report §§6.1–6.3; examples cover all three observation locations | **supported as organizing framework** | `PAO-R4-IV-004` |
| `CE-20` | Everything placed in export-time class is detectable from the artifact at export | Resolution, uniqueness, executability, material omission and composition require auxiliary models/history | **refuted as artifact-local claim; supported only as model-relative export-context check** | `PAO-R4-IV-001` |
| `CE-21` | The three classes are exhaustive for the unqualified institutional claim | Reference-class shopping, purpose synonyms, cognitive use and relay attacks | **not established** | `PAO-R4-IV-002`, `VII-002` |
| `CE-22` | Voluntary reporting cannot support a complete firewall claim | No-report observation identical under compliant non-use and prohibited use plus silence | **supported** | `PAO-R4-IV-005` |
| `CE-23` | Voluntary reporting supports only a terms-of-use/documented restriction | Voluntary reports can still establish observed incidents, lower bounds or sampled evidence | **overstated; supported with narrowing** | `PAO-R4-IV-003` |
| `CE-24` | Returning-evidence semantics are first-class and absence is fail-closed | Issue/use evidence, denominators, content binding, independent reconciliation and `FIREWALL_CLAIM_NOT_ESTABLISHED` | **supported** | `PAO-R4-VI-003` |
| `CE-25` | Full compliance with that interface establishes no prohibited individual use | Cognitive off-boundary use and incorrect counterfactual reliance record | **refuted for institution-wide claim; supported only for recorded governed events** | `PAO-R4-VI-001`, `VI-002` |

## 6. Falsifier claims

| ID | Load-bearing claim | Audited evidence/attack | Verdict | Finding |
|---|---|---|---|---|
| `CE-26` | F-01 implements the commission's silent eligibility-use falsifier | F-01 declares prohibited purpose before export and accepts “at least one” gate; no allowed-request/later-use drift | **refuted** | `PAO-R4-VII-001` |
| `CE-27` | Every suite case has one exact expected outcome | F-01, F-02, F-05 and F-07 contain conditional worlds/disjunctive gates | **refuted** | `PAO-R4-VII-002` |
| `CE-28` | Required aggregate-join, parameterized-rule, projection-narrowing and query-sequence cases are present | F-02 through F-05 | **supported** | `PAO-R4-VII-003` |
| `CE-29` | Suite closes the general property rather than named witnesses only | Missing reference-class-shopping, semantic-purpose, reliance-truth and relay attacks | **not established** | `PAO-R4-VII-002` |

## 7. Legal, kernel, ownership and standing claims

| ID | Load-bearing claim | Audited evidence | Verdict | Finding |
|---|---|---|---|---|
| `CE-30` | Every external source supports the proposition attributed to it | Primary-source verification | **supported substantively** | `PAO-R4-II-004` |
| `CE-31` | External ledger uses stable/current identifiers | Mutable Canadian pages unversioned; M-24-10 rescinded and replaced by M-25-21 | **refuted in part** | `PAO-R4-II-002` |
| `CE-32` | PAO-R4 is “not weaker” than the cited regimes | Broader reliance trigger, but omitted rights/remedies/procedures prevent global dominance comparison | **not established** | `PAO-R4-II-001` |
| `CE-33` | Citing regimes is not a compliance claim | Every row and final limitation explicitly refuses compliance transfer | **supported** | `PAO-R4-II-003` |
| `CE-34` | `PV-K04` supplies, and PAO-R4 consumes, denial monotonicity | Primary report and F-04 | **supported** | `PAO-R4-VIII-001` |
| `CE-35` | `S0-K05`, `S0-K07`, `S0-K11`, `INT-K02`, identity ruling and anti-roles are respected | Internal anchor and scope audit | **supported** | `PAO-R4-VIII-002`, `X-002` |
| `CE-36` | Existing `public_export.py` is the canonical owner of policy-to-case export | Pinned file proves public redacted bundle producer, not all case-system handoffs | **not established** | `PAO-R4-IX-001` |
| `CE-37` | Capability labels are prerequisite-safe and current chain is absent/unallocated | Full label table and no claimed endpoints | **supported** | `PAO-R4-IX-002` |
| `CE-38` | Work is isolated from OPS-R14, PAO-R36 and S0-GAP-02 | Only correction restriction-survival interface; no sibling mechanics | **supported** | `PAO-R4-X-002` |
| `CE-39` | `GO_WITH_REVISIONS` is warranted now | Three blocking defects affect the formal boundary, decidability and commissioned falsifier | **refuted for current adoption; audit recommends NO_GO pending required revisions** | `PAO-R4-III-001`, `III-002`, `VII-001` |

## 8. Delivery-accountability claims—excluded from standing

| ID | Claim | Verdict |
|---|---|---|
| `CE-D1` | The failed first delivery never advanced the remote branch | **process-only, supported** by branch history and incident ledger |
| `CE-D2` | Incident ledger retracts both false completion assertions and later read-only-plugin assertion | **process-only, supported** |
| `CE-D3` | Readback receipt establishes seven-file payload at `4120dc...` | **process-only, supported** |
| `CE-D4` | Committed receipt itself contains a self-contained final-head verification | **process-only, not established**; it explicitly delegates final-head check to later completion record (`PAO-R4-X-001`) |

## 9. Ledger conclusion

The package's durable strengths are `CE-06`, `CE-10`, `CE-14`, `CE-15`, `CE-19`, `CE-22`,
`CE-24`, `CE-28`, `CE-30`, `CE-33`–`CE-35`, `CE-37`, and `CE-38`. The current standing is blocked
by `CE-08`/`CE-09`/`CE-11` and `CE-26`: the object classes are not separated, trusted declarations
carry undecided completeness, material contribution is not observable, and the core silent-use probe
does not test silent use.
