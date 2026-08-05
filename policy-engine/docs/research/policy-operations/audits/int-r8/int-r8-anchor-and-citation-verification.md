---
title: "INT-R8 — Anchor and primary-source verification"
audit_id: INT-R8-INDEPENDENT-AUDIT
verified_commit: 90b372964d29a9e97605a6ef733ef03ffe7938d2
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
authoritative_for:
  - independent Pass II verification of INT-R8 external primary sources and transfer limits
  - exact-ref resolution of load-bearing internal repository anchors
  - findings INT-R8-II-001 through INT-R8-II-004
may_not_use_for:
  - adoption amendment or ratification of INT-R8
  - production implementation authorization
  - final wire schema package database serialization or API contract
  - canonical owner appointment
  - legal sufficiency jurisdictional applicability or institutional competence conclusion
  - permission to publish a governed record
  - authority grant capability claim or benchmark passage
  - automatic amendment of any plan or system-design decision
  - signature algorithm key policy or numeric disclosure-bound selection
research_only: true
---

# INT-R8 anchor and citation verification

## 1. Verification standard

Each external item was checked for four separate propositions:

1. the identifier resolves to a primary or official source;
2. the source says the proposition attributed to it;
3. the proposition is not widened beyond the source's institutional or mathematical scope; and
4. the stated transfer limit prevents the source from becoming a PolicyOS compliance or
   authority claim.

Resolution states are:

- `resolved` — official/primary identifier and proposition verified;
- `resolved_with_version_drift` — proposition verified in the official living source, but the
  exact cited edition is not stably pinned;
- `partially_resolved` — official identifier/title is established, but the exact relied-on text
  was not independently readable from a versioned object;
- `not_established` — evidence did not settle the proposition.

No secondary commentary is used as decisive evidence.

## 2. External primary-source ledger

### 2.1 Public-administration, access, reasons and accessibility sources

| Audited ID | Stable identifier independently checked | Resolution | Proposition check | Transfer-limit check |
| --- | --- | --- | --- | --- |
| US-APA-557 | 5 U.S.C. § 557(c)(3)(A), U.S. House Office of the Law Revision Counsel | `resolved` | The provision requires decisions in its covered formal-adjudication setting to state findings/conclusions and reasons or basis on material issues of fact, law or discretion. | Honest. INT-R8 expressly limits the import to the covered setting and uses it to identify a material-reasons class, not a universal legal duty. |
| US-FOIA-552 | 5 U.S.C. § 552(b), final paragraph | `resolved` | The provision requires reasonably segregable portions after exempt deletion and generally indicates amount/place and exemption, subject to the protected-interest exception. | Honest and unusually important: INT-R8 preserves the exception that an omission indication can itself be harmful. |
| US-PWA-2010 | Pub. L. 111-274, 124 Stat. 2861, GovInfo package `PLAW-111publ274` | `resolved` | The official title and operative purpose concern clear public documents that citizens can understand and use. | Honest. The source supports readability, not semantic deletion or legal sufficiency. |
| AU-ADJR-1977 | Administrative Decisions (Judicial Review) Act 1977 (Cth), Federal Register ID C2004A01697, s 13 | `resolved` | A qualifying requester may obtain findings on material questions of fact, evidence/material and reasons; inadequacy can be corrected, subject to statutory exclusions. | Honest. INT-R8 treats the source as contestability infrastructure and preserves exceptions. |
| AU-FOI-1982 | Freedom of Information Act 1982 (Cth), Federal Register ID C2004A02562 | `resolved` | Current official text includes material findings/reasons and review/complaint information for access decisions, alongside exemptions and review structures. | Honest. The work does not claim direct applicability to PolicyOS. |
| NSW-MHRT-PD-G2 | NSW Mental Health Review Tribunal, Practice Direction General No. 2 — Dissenting Opinions | `partially_resolved` | The official tribunal site and official document locator establish the practice direction and its dissent subject. Searchable official extracts support the three-member/material-matter/signed-and-dated proposition, but the audit interface did not yield a stable versioned full-text object for complete independent reading. | The transfer limit is honest, but the citation should pin a dated/versioned copy before the exact wording is treated as closed evidence. |
| EU-WAD-2016 | Directive (EU) 2016/2102, CELEX 32016L2102, ELI `dir/2016/2102/oj` | `resolved` | The official act concerns accessibility of public-sector websites and mobile applications. | Honest. The work imports release accessibility, not PolicyOS claim semantics or a compliance conclusion. |
| EUIPO-BOA-SUMMARY | EUIPO Boards of Appeal official “Decisions” page | `resolved` | The page states that selected summaries are informational and do not necessarily reproduce exact wording, with links to case decisions and available translations. | Honest. INT-R8 explicitly says the pointer and notice do not cure a materially misleading summary. |

### 2.2 Statistical disclosure-control sources

| Audited ID | Stable identifier independently checked | Resolution | Proposition check | Transfer-limit check |
| --- | --- | --- | --- | --- |
| UK-ONS-SDC | ONS official “Statistical disclosure control” policy page | `resolved` | ONS says all statistical outputs for publication or specific recipients are checked for disclosure risk, controls are applied as required, and an audit trail is retained. It also states that exhaustive factor lists have little value and assessment is case-specific. | Honest. INT-R8 adopts output-event discipline, not an exhaustive theorem for narrative records. |
| UK-ONS-SRS-2023 | ONS SRS “Output Checking Guidance Document,” cited as 12 June 2023 | `resolved_with_version_drift` | The official SRS page still exposes an official guidance download and the official guidance supports risk classes, checker burden and withholding/adjustment. The current live official PDF is a later 2025 edition; the exact 12 June 2023 bytes were not resolved from the cited identifier. | The substantive transfer limit is honest, but the edition/date citation is not reproducible as written. |
| AU-ABS-DATALAB | ABS official DataLab Clearance page | `resolved` | ABS requires clearance before outputs leave DataLab, supporting evidence and application of output rules. | Honest. It supports prospective actual-output review, not a PolicyOS-wide numeric guarantee. |
| AU-ABS-OUTPUT-RULES | ABS official DataLab output rules/examples | `resolved` | The official material applies a rule of 10, requires underlying contributor evidence and guards differencing/secondary suppression. | Honest. The work explicitly refuses to transplant “10” as a universal threshold. |

The ONS policy adds an important qualification that INT-R8 largely preserves: disclosure risk is
reduced to an acceptable institutional level through proportionate procedures; the policy does
not claim exhaustive elimination. That supports INT-R8's refusal to convert SDC practice into a
universal semantic theorem.

### 2.3 Privacy-theoretic and information-leakage sources

| Audited ID | Stable identifier independently checked | Resolution | Proposition check | Transfer-limit check |
| --- | --- | --- | --- | --- |
| NIST-DP-800-226 | NIST SP 800-226 (2025), DOI `10.6028/NIST.SP.800-226` | `resolved` | The final publication defines/evaluates differential-privacy claims around a mechanism, neighboring datasets, parameters and implementation hazards. | Honest. It does not license DP terminology for a curated editorial projection. |
| DP-COMPOSITION-2015 | Kairouz, Oh & Viswanath, PMLR 37:1376–1385; arXiv:1311.0776 | `resolved` | The paper characterizes degradation under adaptive interactions when individual mechanisms already provide differential-privacy levels. | Honest for DP. INT-R8 correctly says the theorem cannot be imported before local DP premises exist. |
| MAX-LEAKAGE-2020 | Issa, Wagner & Kamath, DOI `10.1109/TIT.2019.2962804`; arXiv:1807.07878 | `resolved` | The work defines maximal leakage as multiplicative improvement in guessing a function of a secret after an observation and supplies channel-based properties. | The audited ledger's transfer limit is directionally honest, but its broader composition discussion fails to exploit a key counterpoint: information-leakage quantities can be defined for deterministic channels once the secret/channel model is supplied. That issue is adjudicated in Pass III. |

## 3. Was differential privacy strawmanned?

No. The audited work does not say DP composition is false or irrelevant. It says:

- DP supplies a valid formal composition framework;
- the framework composes mechanisms that already satisfy local DP guarantees;
- current PolicyOS editorial projections have no declared neighboring-record relation, local DP
  guarantee or canonical accountant; and
- therefore epsilon language cannot be imported by analogy.

That is a correct reading of NIST SP 800-226 and the Kairouz–Oh–Viswanath theorem.

The overreach occurs one level higher. The primary report repeatedly presents randomization as
part of the necessary premise set for **a numeric disclosure theorem in general**. DP requires
randomized privacy mechanisms for useful nontrivial releases, but quantitative information-flow
and maximal-leakage frameworks can assign numbers to deterministic channels. Primary literature
also supplies sub-additivity/weak-composition results for maximal-alpha leakage and later work
addresses deterministic release mechanisms. This does not produce a ready PolicyOS budget; it
means the refusal must be framed as “no justified canonical numeric claim under the present
model,” not “no possible numeric framework because the release is deterministic.”

This is finding `INT-R8-III-002`, not a source-fidelity failure in the DP row itself.

## 4. Internal repository-anchor verification

### 4.1 Canonical projection and public-export anchors

| Audited anchor/claim | Resolution | Independent result |
| --- | --- | --- |
| `projection_semantics.py:275-575` emits the claimed base fields and remains projection-only | `resolved` | The projection includes closeout truth, gaps, omission manifest, contested records, recourse, deficit, participation, invariant, redaction, source/audit refs and denied uses; `authoritative_for` is empty and `assert_policy_design_projection_not_authority` is called. |
| `projection_semantics.py:648-655` defines four audiences | `resolved` | PUBLIC, REVIEWER, EXPERT and MACHINE exactly. |
| S9-S14 verifier family and laundering checks | `resolved` | Named verifier functions and per-surface forbidden-use checks exist. |
| `_s14_contains_hidden_or_gold_payload` | `resolved` | Present in the S14 issue path. |
| `public_export.py:430-470` invokes omission manifestation before bundle completion | `resolved` | The call occurs before bundle construction. |
| `public_export.py:1685-1845` contains S9 extraction, omission check, candidate firewall and replay-drift helpers | `resolved` | All named functions exist and have the described fail-closed direction. |
| canonical scanner redaction reasons | `resolved` | Email, keyed-secret and general secret/PII reason categories are emitted. |

### 4.2 Frontend anchors

| Audited anchor/claim | Resolution | Independent result |
| --- | --- | --- |
| `publicationPacket.ts` line count 1,214 | `resolved` | Final brace is line 1,214. |
| `publicRef` truncates to 96 and `publicText` to 320 | `resolved` | Exact source uses `.slice(0, 96)` and `.slice(0, 320)`. |
| deterministic explanations keep four metrics | `resolved` | Exact source uses `metrics.slice(0, 4)`. |
| `buildProjectionSemantics` copies a narrow subset | `resolved` | It carries authority role, closeout truth, display states, evidence class, time, denied uses, policy, provenance kind and surface, but not the canonical omission/gap/contest/recourse/deficit/audit collections. |
| packet is embedded in the deep-link identifier | `resolved` | `signPublicDecisionPacket` stable-serializes packet+signature, base64url-encodes it and places the payload in `/public/decisions/{signedId}`. |
| private-context heuristic checks five needles | `resolved` | Exact five strings are `ssn`, `private reviewer`, `raw restricted`, `confidential value`, `secret`. |

### 4.3 Plan and ratification anchors

| Audited anchor/claim | Resolution | Independent result |
| --- | --- | --- |
| GY-PA3 is a planned producer, not source capability | `resolved` | `GY-engine-subordination.md` names a future compression-loss ledger producer, its intended inputs and red tests; source search is empty. |
| Atlas DS12 gates first public record on INT-R8 | `resolved` | DS12 names INT-R8 with INT-R7, INT-R1 and INT-R9 as pre-publication research inputs. |
| Atlas DS14 consumes the receipt | `resolved` | DS14 calls for rendering the GY-PA3 ledger and cross-projection disclosure discipline. |
| `INT-K02` bare delta rule | `resolved by finding ID` | Ratified statement requires declared obligation set, maintained assumptions and visible relative-basis rider. |
| `INT-K04` numeric composition premises | `resolved by finding ID` | Ratified statement requires fixed exact family, prospective valid local bounds and reproducible custody. |
| `INT-K05` one confidence owner/no second ledger | `resolved by finding ID` | Ratified statement preserves per-problem scopes and forbids a parent risk scope or second ledger. |
| `INT-K06` no-number custody claim | `resolved by finding ID` | Ratified statement permits falsifiable procedural custody without a probability. |
| `INT-K07` adaptive numeric claim | `resolved by finding ID` | Ratified statement requires validity for the history-selected procedure and a pathwise aggregate bound. |
| `INT-K08` negative completion | `resolved by finding ID` | Refusal, void, dispute, no-attempt and exhaustion are completed governed outcomes and may not be hidden by compression. |
| Stage-0 §2 authority/candidate lens | `resolved` | The ratification asks whether strictness binds only protected authority actions or leaks into the candidate band and eats capability. |

No internal citation was found to point to a nonexistent file or to invert the direction of the
source. Several ranges are broad rather than line-sharp; the proposition is still present
inside each cited range.

## 5. Pass II findings

### INT-R8-II-001 — commendation — the source corpus is primary-heavy and transfer-limited

All material source families exist and support the bounded propositions assigned to them. The
work does not convert a statute, tribunal practice or statistical-office rule into a PolicyOS
legal-compliance finding.

### INT-R8-II-002 — minor — the ONS SRS 2023 item is not version-pinned reproducibly

**Evidence:** audited `external-source-and-transfer-ledger.md:79-86` and the official ONS SRS
related-download page.

The proposition survives in official guidance, but the cited “12 June 2023” object is not the
current official download and no content digest/archive identifier is supplied. Pin the exact
edition or cite the living page with an as-of/version statement.

### INT-R8-II-003 — minor — the NSW dissent direction needs a dated/versioned full-text anchor

The title and official tribunal provenance resolve, and available official extracts support the
proposition. The audit could not independently read a stable versioned full text through the
connected interface. Preserve the transfer rule, but do not call the exact wording fully
verified until a dated official copy or digest is bound.

### INT-R8-II-004 — commendation — DP composition is not imported by analogy

The work correctly separates “composition theorem exists” from “this repository satisfies its
premises.” The later over-generalization about all numeric frameworks does not make the DP
source reading a strawman.

## 6. Pass II conclusion

The domain component is a genuine strength. The minimum-retained-set argument is grounded in
material reasons, contestability, dissent, denied-use, deletion indication, accessibility and
actual-output disclosure checking rather than generic summarization literature. Two citation
objects need stronger version custody, and the information-leakage literature creates a
counterexample to one broad composition premise, but the source transfer ledger is otherwise
accurate and restrained.