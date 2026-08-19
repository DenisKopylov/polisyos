---
title: INT-R7 — Amendment Conformance Verification
verified_commit: 2d922813ef542f3eebd21d2a189c017b15512803
verified_branch: research/int-r7-amendment
audited_commit: f5671253b51554dde2dd22a6aef2ef827c5bd9dd
audit_commit: 54e8f41d790cb257a616c5bb5f96d996fbe3e9db
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
verification_branch: research/int-r7-amendment-verification
authoritative_for:
  - independent conformance verdict for INT-R7 revision register R1 through R22
  - independent survival check for the twenty audit commendations
  - independent branch, count, frontmatter, suite-manifest, and source-denominator reconciliation
  - findings INT-R7-V-101 through INT-R7-V-108
may_not_use_for:
  - re-audit or substantive re-adjudication of INT-R7
  - re-audit or adoption of INT-R8
  - production implementation authorization
  - final wire, schema, package, database, serialization, or API contract
  - canonical owner, key custodian, trust service, log, witness, archive, institution, team, person, or vendor appointment
  - authority grant or capability claim
  - benchmark, recovery-drill, or falsifier-suite passage claim
  - legal compliance, legal sufficiency, admissibility, or institutional competence conclusion
  - permission to publish a governed record or open the first-public-signature gate
research_only: true
---

# INT-R7 amendment conformance verification

## 1. Executive verdict

**Verdict: `CONFORMS_WITH_GAPS`.**

The amendment contains real changes to every revision family. No revision is wholly absent, and none is closed only by the amendment ledger's assertion that it was executed. However, the independent standing gate is **not met** because ten revisions are only `conforms_with_gap`:

- `R1`, `R3`, `R4`, `R5`, `R6`, `R8`, `R9`, `R10`, `R12`, and `R16`.

Twelve revisions conform:

- `R2`, `R7`, `R11`, `R13`, `R14`, `R15`, `R17`, `R18`, `R19`, `R20`, `R21`, and `R22`.

The gaps have two roots.

First, the primary entry document remains self-contradictory on first read. Its frontmatter records that it was amended, but the executive material and §§4.2, 12.2, 15–20 still present the superseded aggregate, dependency state, capability labels, v1 denominator, NARA transfer and independence wording. The broad controlling amendment appears only in §21 at lines 904–1029, with no entry-point direction telling the reader to read §21 before relying on the earlier propositions. The supporting artifacts generally use the stronger pattern: their amendment sections name the exact superseded sections and state that the earlier text is audited history rather than the amended contract.

Second, suite v2 is materially closer to an executable exact specification but is not internally exact in every place. The validator both permits `short_circuited` and says any value containing `or` is rejected; the B0 baseline gives `BasisBound` a true value while marking it `not_applicable`; and several subfixtures report `IssuerIssuanceAuthentic = established` while setting a predicate that the controlling issuer-completeness formula makes necessary to false.

The audit's substantive standing target remains correct. The first-public-signature gate remains closed. This verification neither opens it nor re-audits the research.

## 2. Scope and method

The narrow question was whether each audit finding was closed by an actual change to the affected proposition, rather than by prose placed near it.

The verification therefore:

1. read the audit's R1–R22 register at `54e8f41d790cb257a616c5bb5f96d996fbe3e9db`;
2. read the audit's complete 42-row finding register at the same audit head;
3. compared the audited head directly with amendment commit `2d922813ef542f3eebd21d2a189c017b15512803`;
4. read all eleven amendment artifacts at the exact verified commit;
5. inspected every cited revision location and every other changed artifact carrying the affected proposition;
6. separately tested supersession reachability, suite exactness, commendation survival, and count reconciliation; and
7. read the written verification artifacts back from the output branch after committing them.

Ordinary GitHub DNS/egress was denied in this environment. A direct `git ls-remote` failed with `Could not resolve host: github.com`. Exact-ref reads, comparisons, branch creation, ordinary Markdown commits and post-write reads therefore used the connected GitHub interface. No workflow, upload fragment, binary, staging directory, base64 payload, or self-executing automation was added.

## 3. Pass A — branch geometry and integrity

The complete comparison from audited head to amendment head establishes:

| Property | Independently reproduced result |
| --- | ---: |
| ahead | 12 commits |
| behind | 0 commits |
| merge base | exactly `f5671253b51554dde2dd22a6aef2ef827c5bd9dd` |
| changed paths | 11/11 |
| modified files | 10 Markdown files |
| added files | 1 Markdown file |
| deleted files | 0 |
| non-Markdown changed files | 0/11 |
| insertions | 1,600 |
| deletions | 0 |

The additions reconcile from the complete per-file set:

`126 + 175 + 117 + 32 + 67 + 571 + 112 + 42 + 105 + 65 + 188 = 1,600`.

No audited artifact was deleted. The audit branch still resolves exactly to `54e8f41d790cb257a616c5bb5f96d996fbe3e9db` with zero commits ahead or behind that commit. The amendment branch resolves exactly to the verified commit. No pull request exists for `research/int-r7-amendment-verification`.

### Frontmatter denominator

Complete frontmatter inspection covered **11/11 artifacts**:

1. `policy-engine/docs/research/policy-operations/int-r7-public-verification-lifecycle.md`;
2. `policy-engine/docs/research/policy-operations/int-r7/orientation-ledger.md`;
3. `policy-engine/docs/research/policy-operations/int-r7/threat-model-and-verification-predicates.md`;
4. `policy-engine/docs/research/policy-operations/int-r7/comparative-models.md`;
5. `policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md`;
6. `policy-engine/docs/research/policy-operations/int-r7/lifecycle-migration-preservation.md`;
7. `policy-engine/docs/research/policy-operations/int-r7/citizen-verification-ux.md`;
8. `policy-engine/docs/research/policy-operations/int-r7/frozen-falsifier-suite.md`;
9. `policy-engine/docs/research/policy-operations/int-r7/repository-integration-and-dependencies.md`;
10. `policy-engine/docs/research/policy-operations/int-r7/external-source-and-transfer-ledger.md`;
11. `policy-engine/docs/research/policy-operations/int-r7/amendment-ledger.md`.

All 11/11 contain:

- `research_only: true`;
- a non-empty `may_not_use_for` block; and
- the exact binding `amended_after_audit: research/int-r7-independent-audit@54e8f41d790cb257a616c5bb5f96d996fbe3e9db`.

**Pass A: conforms.**

## 4. Pass B — revision-by-revision conformance

| Revision | Verdict | Independently inspected evidence | Determination |
| --- | --- | --- | --- |
| `R1` | `conforms_with_gap` | Threat model `:760-949`; profile `:622-728`; lifecycle `:552-672`; UX `:668-784`; suite `:670-1237`; primary `:192-245,904-1029` | The five-way decomposition is real in all required artifacts. The primary report nevertheless presents the superseded aggregate at §4.2 before any directional supersession notice. Its §21 correction is broad and late, so the affected entry proposition remains reachable as governing text. Suite AX-05a also conflicts with the issuer-completeness formula. |
| `R2` | `conforms` | Threat model `:850-872`; profile `:664-674`; lifecycle `:595-612`; UX `:719-733`; suite AX-02 `:1114-1133` | Snapshot authenticity and latest-applicable selection are separated; rollback has an exact non-current outcome and citizen wording. |
| `R3` | `conforms_with_gap` | Repository handoff `:387-407`; threat model `:812-849`; profile `:646-663`; suite `:670-676`; primary `:35-69,904-956` | The INT-R8 comparison is genuinely provisional, retains every original INT-R7 requirement, records partial matches and an offline-closure gap, and leaves projection positives hypothetical. The primary executive still says publication waits for the INT-R8 contract to become available, a superseded factual state encountered before §21. |
| `R4` | `conforms_with_gap` | Repository handoff `:408-410`; threat model `:850-872`; profile `:709-718`; UX `:690-704`; suite `:670-676`; primary `:192-245,904-956` | GY-N12 is consistently planned/undelivered in the amendment sections and positive suite inputs are fixture-only. The primary's earlier current-result algebra omits the admitted-interface condition until §21. |
| `R5` | `conforms_with_gap` | Repository handoff `:356-385`; profile `:718-724`; UX `:776-780`; primary `:120-124,715-729,953-970` | N-01–N-07 and proposed chains are actually reclassified as absent/unallocated, while the real export producer and its `bridge_missing` route survive. The primary still exposes the prohibited downstream labels in §§2.3 and 16.2 before §21. |
| `R6` | `conforms_with_gap` | Suite `:670-1237`; primary `:680-700,964-983` | v2 is a real versioned specification with 23 families and 29 subfixtures, exact scalar slots and evaluation status. Gaps: the primary advertises v1/18 before §21; validator rule 2 literally conflicts with allowed values such as `short_circuited`; and B0 sets `BasisBound=true` with `evaluation_status=not_applicable`. |
| `R7` | `conforms` | Threat model `:793-810`; UX `:700-718`; suite F-04a `:789-804` | F-04 now has `ISSUANCE_TEMPORALLY_UNAUTHORIZED`, visibly preserves valid signature mathematics, and forbids the tamper/signature-invalid terminal. |
| `R8` | `conforms_with_gap` | Threat model `:932-940`; UX `:746-752`; suite F-08a `:852-874`; primary `:192-245,904-939` | F-08 correctly preserves issuer issuance and makes public history/common view non-positive. The primary's earlier aggregate still erases that distinction until §21. |
| `R9` | `conforms_with_gap` | Threat model `:920-930`; suite AX-01–AX-05 `:1098-1195` | All five attacks are present with exact terminals. AX-05a is internally inconsistent: it inherits procedural B0, reports `IssuerIssuanceAuthentic=established`, but sets `ProceduralHistoryBound=false`, although the controlling issuer formula requires that predicate for a procedural claim. |
| `R10` | `conforms_with_gap` | Lifecycle `:570-594`; profile `:709-714`; primary `:840-860,981-992` | A real-path non-authoritative ceremonial phase and bounded first-live phase are specified, and paper/tabletop/mock evidence is rejected. The primary first-signature gate remains the old generic “disconnected recovery drill” until the late §21 clarification. |
| `R11` | `conforms` | Lifecycle `:595-637`; suite AX-02 `:1114-1133` | Authentic-snapshot rollback, compromised-primary operation, independent/cross-custody roots and non-positive currentness are observable requirements without topology or vendor appointment. |
| `R12` | `conforms_with_gap` | Source ledger `:153-225`; lifecycle `:653-657`; primary `:520-552,996-1006` | US-01 is actually made historical-only and US-03 is explicitly jurisdiction-bounded and subject to later supersession. The primary still presents US-01 as a strong current transfer in §12.2 before §21.7. |
| `R13` | `conforms` | Source ledger `:164,213-217`; comparative model `:410-416`; primary `:999-1001` | US-02 is expressly nonbinding, Federal Register submission-specific and transferred only as a bounded delegation/control pattern. |
| `R14` | `conforms` | Orientation ledger `:208-218` | O-18 records the missed same-day fact and states that no substantive design consequence follows. |
| `R15` | `conforms` | Threat model `:873-883`; profile `:675-685`; UX `:734-745`; lifecycle `:659-669`; suite AX-05b `:1176-1195` | Evidence obtainability is separate from signature authenticity and distinguishes public access, records-process access, competent restriction and non-establishment. |
| `R16` | `conforms_with_gap` | Threat model `:760-775`; comparative model `:396-408`; UX `:668-687`; primary `:862-870,924-939` | The amended model consistently says separately reportable, not logically independent. The primary's earlier standing section still states that historical authenticity and current authority “are independent” before §21. |
| `R17` | `conforms` | Source ledger `:153-167,169-225`; comparative model `:410-416` | ETSI-05 is corrected to 2024-01; RFC 9162's quorum transfer is narrowed to an INT-R7 inference; SIG-05 supplies the exact Bundle Format anchor. |
| `R18` | `conforms` | Repository handoff `:412-414`; profile `:726-728`; lifecycle `:669-672`; UX `:782-784`; suite `:1234-1237`; primary `:1027-1029` | Relevant artifacts contain explicit anti-enum/schema/API/wire warnings. No owner, wire format or schema is appointed. |
| `R19` | `conforms` | Profile `:701-708`; lifecycle `:639-651`; UX `:758-764`; suite F-18b `:1074-1095` | The positive lawful-succession path is explicit, predecessor attribution remains original, and successor authority is limited to custody/preservation/status. |
| `R20` | `conforms` | Orientation ledger `:220-258` | Static 14/14 and 5/5 outputs, roots, inclusion rules and rerun recipes are preserved. The local-rerun limitation is honest: ordinary GitHub DNS was also unavailable during this verification. O-02/O-08 remain `not_established`. |
| `R21` | `conforms` | Suite baseline `:706-728`; F-03a `:762-780`; F-13a `:982-997` | Local signature mathematics and configured signature/quorum policy are separately represented. |
| `R22` | `conforms` | Source ledger `:169-225` | All 32 unique source IDs have a checked status/recheck rule and the document requires manual revalidation before consolidation or implementation. |

### Revision verdict reconciliation

| Revision verdict | Count |
| --- | ---: |
| `conforms` | 12 |
| `conforms_with_gap` | 10 |
| `not_executed` | 0 |
| **total** | **22** |

The amendment's self-reported disposition table itself contains **22/22 rows**: 19 `executed`, 3 `executed with variation`, 0 `declined`. The three declared variations are exactly R3, R12 and R20. Each is honestly labelled; none hides complete non-execution.

## 5. Pass C — commendation survival

All **20/20** audit commendations survive. None is weakened or lost.

| Audit commendation | Survival | Verified amended location and determination |
| --- | --- | --- |
| `INT-R7-I-001` | intact | Exact branch geometry reproduced by complete compare; no audited artifact deleted. |
| `INT-R7-I-002` | intact | Primary `:908-917` retains the mutable `signed_at`/identity and timeless-revocation defect exactly. |
| `INT-R7-I-003` | intact/strengthened | Orientation `:231-254` preserves the 5/5 O-09 set; repository handoff `:365-368` preserves the real producer and `bridge_missing` route. |
| `INT-R7-I-004` | intact | Orientation `:256-258` retains O-02/O-08 as `not_established`. |
| `INT-R7-II-001` | intact | Original 30-row corpus remains; source correction/currentness section `:153-225` preserves transfer limits and expands unique IDs to 32. |
| `INT-R7-III-001` | intact | Threat model `:760-919` still rejects “signature equals worldly fact” and exposes separate evidence dimensions. |
| `INT-R7-IV-001` | intact | Comparative artifact `:25-389,392-425` retains the selected construction classes and named elimination properties. |
| `INT-R7-IV-002` | intact | Repository handoff `:387-414` keeps GY-N12 and INT-R8 as consumed dependencies, not duplicate owners. |
| `INT-R7-V-004` | intact/expanded | Suite v2 retains F-05a, F-17a and F-18a and adds lawful F-18b; history, withdrawal and non-substitutive succession remain first-class. |
| `INT-R7-VI-001` | intact/clarified | Lifecycle `:570-594` applies the gate to live authority-bearing issuance, not ceremonial/candidate work. |
| `INT-R7-VI-004` | intact | Lifecycle `:552-568,639-657` still forbids late renewal or custody succession from becoming original issuance. |
| `INT-R7-VII-001` | intact/strengthened | INT-K06 chronology remains issuer-side security semantics; threat model `:920-930` adds withholding of a required negative terminal. |
| `INT-R7-VII-002` | intact | Threat model `:776-809` keeps the declared obligation set and assumptions inside issuer statement completeness. |
| `INT-R7-VII-003` | intact | Threat model `:888-915` preserves withdrawn-but-verifiable as issuance/durability plus current=false, without rewriting history. |
| `INT-R7-VII-004` | intact | Suite `:1221-1233` keeps every v2 passage claim bounded by S0-K16. |
| `INT-R7-VII-005` | intact | Repository handoff `:387-414` creates no second authority, currentness or projection owner. |
| `INT-R7-VIII-001` | intact | Repository handoff `:387-407` preserves the proof/content boundary and labels the comparison provisional. |
| `INT-R7-IX-001` | intact | Complete 11/11 frontmatter census passes; prohibitions are retained and expanded to the amendment ledger. |
| `INT-R7-IX-003` | intact | Primary `:1006-1025` retains `GO_WITH_REVISIONS` and keeps publication closed. Independent retention gate is not yet met because of this verification's gaps. |
| `INT-R7-X-002` | intact | Repository handoff `:365-368` expressly preserves `public_export.py` and only labels the evidenced producer-to-route connection `bridge_missing`. |

### Commendation reconciliation

| Survival verdict | Count |
| --- | ---: |
| intact or strengthened | 20 |
| weakened | 0 |
| lost | 0 |
| **total** | **20** |

## 6. Pass D — new-defect and consistency check

### Five-dimension consistency

The decomposition is stable in threat model §15, profile §18, lifecycle §11 and UX §13. The primary report reachability and three suite vectors are the exceptions recorded in findings `INT-R7-V-102` and `INT-R7-V-104`.

### Suite exactness

The complete v2 manifest contains **23/23 family rows**:

- F-01 through F-18; and
- AX-01 through AX-05.

It contains **29/29 mandatory subfixtures**:

- 23 subfixtures across F-01–F-18; and
- 6 subfixtures across AX-01–AX-05.

No optional subfixture contributes to passage. The denominator block agrees with the manifest. F-04a visibly keeps `SignatureValid=true`; F-08a keeps issuer issuance established and common view non-positive; all five added attack families exist; v1 is left unchanged above and v2 is separately versioned. The static-validator and vector-consistency gaps are recorded rather than treated as suite passage.

### No prohibited design authority introduced

No amended artifact fixes a wire format, schema, enum, API, package, database layout, concrete operator, vendor, trust service, log, witness, archive, institutional owner or legal-sufficiency result. YAML and function-like notation are expressly implementation-neutral.

## 7. Pass E — independent count reconciliation

### Amendment geometry

- 12 commits ahead / 0 behind;
- 11 changed paths / 11 total;
- 10 modified Markdown + 1 added Markdown;
- 1,600 additions / 0 deletions;
- 0 non-Markdown changed paths;
- merge base exactly the audited head.

### Amendment ledger

The complete revision table contains `R1` through `R22` exactly once: **22 rows / 22 total**.

The complete finding-disposition table contains the audit IDs from `INT-R7-I-001` through `INT-R7-X-002`: **42 rows / 42 total**.

### Audit register

The audit's own complete 42-row register independently reconciles to:

| Severity | Rows |
| --- | ---: |
| blocking | 1 |
| material | 15 |
| minor | 6 |
| commendation | 20 |
| **total** | **42** |

The amendment ledger repeats the same 1/15/6/20 split. Its prose and tables agree.

### Sources

The original source table contains **30/30 source IDs**. The amendment adds two new unique IDs, SIG-05 and US-03, and the currentness table contains all resulting IDs: **32 unique source IDs / 32 total**.

### This verification

This report records **8 findings / 8 total**:

| Severity | Rows |
| --- | ---: |
| blocking | 1 |
| material | 2 |
| minor | 1 |
| commendation | 4 |
| **total** | **8** |

## 8. New finding register

| Finding ID | Severity | Pass | Determination and evidence |
| --- | --- | --- | --- |
| `INT-R7-V-101` | commendation | A/E | Branch geometry, 11/11 frontmatter, audit-branch immutability and all self-reported denominators are reproducible from complete sets. |
| `INT-R7-V-102` | blocking | B/F | Primary-report supersession is not adequately reachable from the entry point. Frontmatter `:1-32` says only that an audit amendment exists; executive/deliverable material `:35-83`, aggregate §4.2 `:192-245`, current NARA use `:520-552`, v1/capability material `:680-748`, and gate/independence material `:840-875` are encountered before broad §21 at `:904-1029`. This leaves R1, R3, R4, R5, R6, R8, R10, R12 and R16 incomplete in the controlling entry document. |
| `INT-R7-V-103` | material | D | Suite v2's exact-value validator is not internally executable as written. §9.1 permits `short_circuited`, while §9.2 rejects any value containing `or`; B0 also assigns `BasisBound=true` with `evaluation_status=not_applicable` at `frozen-falsifier-suite.md:706-728`. R6 therefore remains incomplete. |
| `INT-R7-V-104` | material | B/D | Suite vectors contradict the controlling issuer formula. `IssuerStatementComplete` requires audience, jurisdiction and procedural-history bindings at `threat-model-and-verification-predicates.md:776-809`, while F-09a/F-10a report issuer issuance established with the corresponding binding false (`frozen-falsifier-suite.md:875-910`) and AX-05a reports issuer issuance established with `ProceduralHistoryBound=false` (`:1162-1180`). R1 and R9 remain incomplete until the issuer-side predicate and requested-use/release-side predicates are made consistent. |
| `INT-R7-V-105` | minor | B | The amendment ledger's “exact path:line” evidence sometimes identifies a section entry rather than the affected proposition: R12 and R15 cite lifecycle line 552, while the actual NARA and evidence-obtainability propositions are at `:653-669`; R17 cites source line 153 while the corrections are at `:161-167`. The changes exist, but the supplied evidence trail is less exact than claimed. |
| `INT-R7-V-106` | commendation | B | The three variations are honest. R3 is provisional and non-adoptive; R12 is historical-only plus jurisdiction-bounded supplementation; R20 states the failed local-rerun condition and preserves `not_established` instead of fabricating confidence. |
| `INT-R7-V-107` | commendation | C | All twenty commendation-backed strengths survive, including the real public-export producer and its narrowly evidenced `bridge_missing` route. |
| `INT-R7-V-108` | commendation | D/E | Suite family/subfixture counts, source count, revision/finding table counts and severity arithmetic reconcile without prose/table disagreement. |

## 9. Pass F — standing gate

The audit's standing gate required R1–R15 to be executed **and independently verified**.

That gate is **not met**. Nine standing-required revisions are only `conforms_with_gap`:

- R1, R3, R4, R5, R6, R8, R9, R10 and R12.

The correct conformance verdict is therefore `CONFORMS_WITH_GAPS`, not `CONFORMS` and not `NOT_CONFORMING`:

- not `CONFORMS`, because the primary-report reachability defect and suite inconsistencies remain;
- not `NOT_CONFORMING`, because every revision has a real change in the affected proposition family and none is wholly absent.

`GO_WITH_REVISIONS` remains the correct substantive research standing target, but its **post-amendment independent-retention condition has not yet been satisfied**. The first-public-signature gate remains closed.

## 10. Audit disagreement

No audit finding is re-opened or rejected in this verification. The gaps above concern whether the amendment executed the audit's own revision register in a reachable and internally consistent form.
