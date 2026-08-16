---
title: "OPS-R14 Amendment Independent Conformance Verification"
verification_id: OPS-R14-AMENDMENT-VERIFICATION
status: completed_with_blocking_findings
verdict: NO_GO
blocking_findings: 2
non_blocking_findings: 1
verified_amendment_branch: research/ops-r14-amendment
verified_amendment_head: 83539ebf0a211728cf3cb8cef4cbffce8429a8bb
independent_audit_branch: research/ops-r14-independent-audit
independent_audit_head: 34c65a04ef178b9a59f70b9fb2012edee17a67cd
audited_research_head: 3a694212aa47c4c2d8a631f8edc4ba8f7e15dce7
repository_documentation_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
output_branch: research/ops-r14-amendment-verification
authoritative_for:
  - independent_conformance_verdict_for_ops_r14_amendment
  - amendment_orientation_reproduction
  - audit_revision_conformance_check
  - p37_and_falsifier_conformance_check
may_not_use_for:
  - amendment_repair
  - production_implementation_authorization
  - production_capability_claim
  - permission_to_publish_sign_or_open_a_gate
  - final_wire_schema_package_database_serialization_or_api_contract
  - canonical_owner_vendor_custodian_archive_service_or_escrow_appointment
  - authority_or_delegation_grant
  - legal_sufficiency_or_jurisdictional_conclusion
  - assessment_or_adoption_of_pao_r36_quality
research_only: true
---

# OPS-R14 amendment independent conformance verification

## 0. Verdict

**`NO_GO`.**

The amendment is materially stronger than the audited package and passes most of the independent
audit's required revisions. It does **not** fully conform to the audit and the ratified predicate-
provenance kernel it claims to satisfy.

- **Blocking findings: 2.**
- **Non-blocking findings: 1.**

The blocking findings are:

1. the amendment declares the audit's R7 census closed without carrying the audit-required retained
   complete-walk evidence or supplying both file-type censuses for every literal; and
2. F-14 returns positive scoped current-custodian conclusions from organizational-succession scope,
   even though the package itself classifies that decisive predicate as `institutionally_supplied`.
   That contradicts registered P37.

The non-blocking finding is that R8's refusal is incomplete: stable identifiers and transfer limits
are preserved, but explicit source-currentness assertions remain standing despite the amendment's
statement that it had no fresh retrieval record.

This verification does not repair the amendment.

## 1. Verified objects and independence boundary

### 1.1 Exact objects

| Object | Exact identity |
| --- | --- |
| Amendment | `research/ops-r14-amendment@83539ebf0a211728cf3cb8cef4cbffce8429a8bb` |
| Independent audit | `research/ops-r14-independent-audit@34c65a04ef178b9a59f70b9fb2012edee17a67cd` |
| Amendment merge base / audited research head | `3a694212aa47c4c2d8a631f8edc4ba8f7e15dce7` |
| Registered P37 documentation pin | `109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` |
| Pre-registration source baseline | `1a7a2d05ebba22fae80e9934329e4b880806588e` |

The amendment's merge base was established by exact commit comparison; it was not inferred from the
amendment ledger. The amendment is **9 commits ahead and 0 behind**
`3a694212aa47c4c2d8a631f8edc4ba8f7e15dce7`, and that commit is the comparison merge base.

The comparison from `1a7a2d05e...` to `109ba3f44...` changes only `AGENTS.md` and
`policy-engine/docs/reference/policy-design-case-failure-patterns.md`. No path below
`policy-engine/src` changes, so the pinned source census is comparable across those two commits.

### 1.2 Method and limitation

Exact refs, commit comparisons, named-file reads, Git object identities, and connector-backed branch
writes were used. The available interface did not expose a materializable recursive archive or raw
checkout. Therefore this verification does not convert indexed candidates, amendment prose, or an
architect's declaration into a complete byte-walk result.

That limitation affects the high-cardinality and zero source-token rows described in section 2.3. It
does not affect the exact branch geometry, changed-file set, final line counts, frontmatter fields,
low-cardinality `legal_hold` and `renewal` censuses, complete nine-artifact prose review, P37 register
review, seam enumeration, or delivered-file read-back.

## 2. Orientation audit

### 2.1 Branch geometry and path boundary

The base-to-amendment comparison contains exactly **9 changed files**, all Markdown under the OPS-R14
research package. It contains no source, tests, CI, workflow, audit-branch, sibling-task, binary,
staging, or transport path.

### 2.2 Exact changed-file set and final line counts

| Path | Lines | Amendment blob |
| --- | ---: | --- |
| `policy-engine/docs/research/policy-operations/ops-r14-custody-resilience-and-expiring-authority.md` | **488** | `349faba008284c4c6ecdf6d346be8148f263ef41` |
| `policy-engine/docs/research/policy-operations/ops-r14/amendment-ledger.md` | **119** | `65f84b2e7882654fb07450fd222f03552b7aac0e` |
| `policy-engine/docs/research/policy-operations/ops-r14/custody-class-objectives-and-recovery-closure.md` | **287** | `aa873ac91c2c48d19910ca0543497b6a54137dab` |
| `policy-engine/docs/research/policy-operations/ops-r14/disaster-fixtures-and-drill-evidence.md` | **457** | `83e560ccc30edf78cad53c7043a031290e500af2` |
| `policy-engine/docs/research/policy-operations/ops-r14/external-primary-source-and-transfer-ledger.md` | **154** | `57adf2a20975e34167a0246d9d7ecf37c886d6b5` |
| `policy-engine/docs/research/policy-operations/ops-r14/long-term-replay-and-preservation.md` | **305** | `b174965f3b252b7ec2c3ab47ae9c2de74b36c900` |
| `policy-engine/docs/research/policy-operations/ops-r14/orientation-ledger.md` | **172** | `c34848023054e2f23063753f3632065cfcfe3d6c` |
| `policy-engine/docs/research/policy-operations/ops-r14/repository-integration-handoff.md` | **194** | `0adbb8a4709beea65b37d292329e2ae36dce9300` |
| `policy-engine/docs/research/policy-operations/ops-r14/watched-dependency-and-legal-hold-semantics.md` | **516** | `8e902f852486abfd95a7150ca8bba5a66989204d` |
| **Total** | **2,692** | |

The reported file count, commit distance, changed-path boundary, per-path line counts, and total are
reproduced.

### 2.3 Source census reproduction

**Path denominator tested:** `policy-engine/src` at `109ba3f44...`.  
**Literal semantics:** exact, case-sensitive, non-overlapping occurrences; a matching line is counted
once even when it contains multiple occurrences.

| Literal and file-type denominator | Amendment claim | Independent result | Conformance |
| --- | ---: | --- | --- |
| `legal_hold`, all source | `2 / 7 / 8` | **Reproduced: `2 / 7 / 8`.** | Pass. |
| `renewal`, all source | `4 / 4 / 4` | **Reproduced: `4 / 4 / 4`.** | Pass. |
| `renewal`, Python only | `1 / 1 / 1` | **Reproduced: `1 / 1 / 1`.** | Pass. |
| `expires_at`, Python only | `49 / 280 / 363` | File count was strongly corroborated by the audit; lines and occurrences were not independently byte-walked here. | Not established by this verification. |
| `ttl_seconds`, Python only | `30 / 116 / 148` | Audit evidence strongly corroborated the file claim; the complete files/lines/occurrences tuple was not independently byte-walked here. | Not established by this verification. |
| `expiry`, Python only | `27 / 102 / 121` | Audit evidence strongly corroborated the file claim; the complete files/lines/occurrences tuple was not independently byte-walked here. | Not established by this verification. |
| `grace_period`, all source | `0 / 0 / 0` | No contradictory indexed candidate was identified, but a complete byte-walk zero was not independently executed here. | Not established by this verification. |
| `not_after`, all source | `0 / 0 / 0` | Same limitation. | Not established by this verification. |
| `revocation_time`, all source | `0 / 0 / 0` | Same limitation. | Not established by this verification. |

#### `legal_hold` adjudication

The independent audit's `2 files / 4 matching lines / 5 occurrences` result is wrong. The complete
low-cardinality read gives:

- `fabric/security/retention.py`: 3 matching lines and 4 occurrences; the classification condition
  contains the literal twice on one line; and
- `fabric/world/store/snapshots.py`: 4 matching lines and 4 occurrences, in the retained-tag constant,
  enforcement call, default retained-tag tuple, and enforcement-function name.

The correct total is **2 files / 7 matching lines / 8 occurrences**. The amendment is right on this
point and the audit's candidate set was incomplete.

#### `renewal` adjudication

The complete low-cardinality set is:

- one Python occurrence in the `ControlWorker` processing-lease docstring; and
- three CSV fixture-description occurrences concerning urban or strategic renewal.

That gives all-source `4 / 4 / 4` and Python-only `1 / 1 / 1`. The Python occurrence is not an
authority-renewal primitive.

### 2.4 Blocking finding AV-B01 — R7 is claimed closed without the audit's closure evidence

The independent audit's R7 required, for **each of the eight literals**:

1. both all-file and Python-only results;
2. matching files, matching lines, occurrences, and the exact path list;
3. a retained script/output identity tied to the pin; and
4. a matching second independent run.

The amendment instead publishes nine selected rows: only `renewal` has both file-type denominators;
the other seven literals have one selected denominator. The package contains no exact path lists, no
script/output digest, and no second-run receipt. Its changed-file set contains only the nine Markdown
artifacts above, and none names an external retained census object that supplies the missing evidence.

The amendment ledger nevertheless says “R7 is closed” by architect-supplied data. That substitutes the
amendment's framing for the audit's execution evidence. Under the commission's anti-ratchet rule, the
high-cardinality and zero tuples cannot be promoted from claims to independently established facts.
This is blocking for this conformance verification.

## 3. Independent-audit revision conformance

| Revision | Result | Independent adjudication |
| --- | --- | --- |
| R1 — separate research/capability/gate standing | **Pass** | All nine artifacts use the exact three fields and preserve negative operational conclusions. |
| R2 — narrow/register acceptance evidence defect | **Pass** | `OPS-R14-ACCEPTANCE-001` appears in the primary, orientation, and drill artifacts with the required taxonomy and closure signal. |
| R3 — prospective delivery reconciliation | **Pass** | WD-05A separates `delivery_reconciled`/`delivery_gap` from WD-12 use-time refusal; F-13 exercises both. |
| R4 — four added adversarial fixtures | **Pass on requested fixture shape; fails P37 at F-14** | F-14–F-17 are present with one detector, one verdict, and one forbidden outcome. F-14's positive result conflicts with registered P37; see AV-B02. |
| R5 — canonical capability labels / GY-N12 layering | **Pass** | Runbooks are factual inputs, aggregate capability is `absent/unallocated`, and GY-N12 is project semantic/plan `contract_only` with runtime absent/unallocated. |
| R6 — instrument-specific procurement inference | **Pass** | FAR 4.805 and Procurement Act s.98 are limited to durable records/chronology; options, audit, exit, records, and survival effects require the admitted instrument/rule. |
| R7 — complete retained source census | **Fail** | AV-B01. |
| R8 — exact external anchors/currentness evidence | **Declined, but refusal incomplete** | Stable identifiers and transfer limits survive; currentness assertions also survive without the fresh retrieval record. See AV-N01. |
| R9 — local intent qualification | **Pass** | The package says local intent **alone** cannot establish renewal and bounds unilateral option exercise to admitted authority/scope/notice/timing/conditions. |
| R10 — real-path anti-substitution | **Pass** | DE-04/DE-05 require component/profile digests; permissive substitution with markers intact must return `real_path_identity_mismatch`. |
| R11 — full PAO-R36 F11 conjunction | **Pass** | Every F11 closure summary names the full six-part conjunction; no `RP-10`-alone closure survives. |

The preserved audit commendations were also checked across the package: six renewal families and all
eleven mappings remain; legal hold remains an orthogonal disposal override; PV-K02 discipline remains;
capability-label prerequisites remain conservative; GY-N12 remains the sole currentness owner; and no
implementation, publication, signing, legal-sufficiency, vendor, custodian, wire, or OPS-R12
absorption authority is introduced.

## 4. Three-axis standing

All nine artifacts carry exactly:

- `research_standing: accepted_narrow_scope`
- `capability_standing: NO_GO`
- `gate_standing: NO_GO`

The exact field names and values are uniform. The primary report explicitly explains that the prior
one-field scale forced a capability refusal to be written as a research-result refusal. Supporting
artifacts independently state that research acceptance does not establish runtime capability or open
the first-public-signature gate.

No artifact was found deriving research acceptance from capability, capability from research
acceptance, or gate standing from either other axis. This requirement conforms.

## 5. R8 refusal and currentness

### 5.1 What is preserved correctly

The external ledger retains stable instrument identifiers and disciplined transfer limits, including
statutory section identifiers, CFR/FAR identifiers, NIST and RFC DOIs, the FOIA Code ISBN, ISO/OAIS and
PREMIS version identities, and explicit “what transfers / what does not transfer / recheck trigger”
columns. The procurement correction is bounded to instrument-specific predicates.

### 5.2 Non-blocking finding AV-N01 — the refusal is incomplete

The amendment ledger says no fresh external retrieval record was supplied and correctly refuses to
replace URLs as though current targets had been reverified. However the amended package still leaves
currentness assertions standing, including:

- `source_review_date: 2026-08-06` and the prose review date;
- “current federal rules” for 36 C.F.R. Part 1226;
- “current U.S. Courts rules page” for Rule 37(e);
- “current FAC 2026-01 effective 2026-03-13” for FAR 4.805;
- the current-eCFR-over-historical-numbering adjudication; and
- the dated UK continuity call-for-views/current-source note.

This verification does not decide whether those propositions were factually true on their stated
date. It finds that the package's claimed R8 refusal is not complete: it declines fresh retrieval while
retaining currentness propositions that P37 classifies as requiring independent reconciliation
(`PP-35`). Stable identifiers and transfer limits pass; currentness provenance does not.

This is non-blocking because it does not promote runtime capability or change the transfer result, but
it is a real conformance gap and must not be reported as a complete R8 refusal.

## 6. R11 seam enumeration

The exact required closure is:

`RP-10 + RC-01 + RC-07 + F-04 + F-09 + DE-07`

Every place that claims to summarize or close PAO-R36 F11 uses the full conjunction:

1. primary report §4.4;
2. orientation ledger §3 seam row;
3. custody/recovery artifact RC-07;
4. long-term replay artifact RP-10;
5. disaster/drill artifact DE-07;
6. repository-integration matrix PAO-R36 row;
7. repository-integration §4.3; and
8. amendment-ledger disposition `OPS-R14-VIII-001`.

The watched-dependency and legal-hold artifacts contain ordinary PAO-R36 ownership/interface
statements, but do not claim that F11 closes through `RP-10` alone. No blocking R11 survivor was found.

## 7. P37 conformance

### 7.1 Registered vocabulary

At `109ba3f44...`, P37 registers exactly five labels:

1. `recomputed`
2. `independently_reconciled`
3. `consumer_asserted`
4. `institutionally_supplied`
5. `not_established`

It also requires labels to be frozen at admission and forbids a positive gate when a decisive
predicate is in the last three classes.

### 7.2 The 48-predicate register

The primary report contains one contiguous table from `PP-01` through `PP-48`, with no missing or
duplicate ID and no sixth label. Its class counts are:

| Classification | Predicates |
| --- | ---: |
| `recomputed` | **15** |
| `independently_reconciled` | **12** |
| `consumer_asserted` | **2** |
| `institutionally_supplied` | **17** |
| `not_established` | **2** |
| **Total** | **48** |

A complete read of the nine artifacts found the explicit load-bearing gate families represented in
that table: source census, content/control closure, event-prefix completeness, custody independence,
time, class assignment, authority/renewal/grace, due-event delivery, affected-set completeness,
hold/release/disposal, signing/trust/compromise, parser/canonicalizer identity and equivalence, public
head/fan-out, external-source currentness, succession, RPO/RTO, drill corpus/injection/disconnection,
real-path identity, review authority, acceptance evidence, public duty, instrument-specific rights,
escrow, and aggregate capability. No explicit sixth class or unclassified named gate was found.

The register is therefore a complete enumerated package register rather than a visible sample. Its
application is not fully conformant because of F-14.

### 7.3 Falsify-the-declaration probes

- **F-13:** “alert sent” remains intact while the independent history contains no due/expiry event.
  The exact result is `delivery_gap`, and protected use is blocked.
- **F-15:** two `independent=true` declarations remain intact while non-producing provenance shows one
  compromised substrate/root. The exact result is `custody_independence_not_established`, and
  restoration is false.

Both probes genuinely go red when the declared premise is falsified. They test the property, not the
marker.

### 7.4 Blocking finding AV-B02 — F-14 contradicts PP-36 and P37

`PP-36` classifies **organizational succession scope** as `institutionally_supplied`. Registered P37
says a decisive predicate in that class may not yield a positive gate.

F-14's exact verdict nevertheless says:

- successor A **is current custodian** for X-only; and
- successor B **is current custodian** for Y-only;

while only the overlap is `not_established`. The detector compares admitted instruments, effective
times, query scope, and issuer identity, but the package names no recomputing or independently
reconciling canonical owner that changes the decisive succession-scope predicate out of
`institutionally_supplied`. The package's general statement that institutional facts may later be
admitted does not create a sixth P37 exception; P37 freezes the label at admission.

F-14 is correctly non-global and preserves valid non-overlap as an architectural aim, but its positive
custodian conclusions do not conform to the registered gate rule the package claims to apply. This is
a ratified-kernel conflict and is blocking.

## 8. F-14 through F-17 structural verification

| Fixture | One detector | Exact verdict | One forbidden outcome | Structural result |
| --- | --- | --- | --- | --- |
| F-14 lawful partial succession | Scope-bound comparison of both instruments/effective times plus invariant issuer identity | `scoped_succession_partial` | No global pass over the overlap and no global failure erasing established non-overlap | Shape passes; P37 application fails under AV-B02. |
| F-15 common-mode false independence | Reconstruct non-producing administration/storage/key/observation provenance and collapse shared roots | `custody_independence_not_established` | Do not count declarations as two or return green restoration | Pass. |
| F-16 authenticated-time rollback | Compare local clock, trusted-time chain, checkpoint sequence, effective time, and action time | `authority_time_not_established` | Do not accept because rolled-back local time reports pre-expiry | Pass. |
| F-17 parser/canonicalization differential | Compare implementation digests, canonical signing input, protected-query outputs, and migration linkage | `historical_semantic_interpretation_not_established` | Do not select a parser because it is newer or reports syntactic success | Pass. |

No fixture offers alternate conditional verdicts or split execution worlds. F-14 has one deliberately
scoped mixed verdict, not competing branches.

The remove-the-property/keep-the-markers probe was checked on two load-bearing cases:

1. **F-15:** actual independence is removed while both `independent=true` markers remain; the detector
   still returns red.
2. **F-17:** historical semantic equivalence is removed while both parsers retain syntactic-success
   markers; the detector still returns red.

The separate R10 substitution probe also leaves marker strings/declarations intact while replacing a
real intended component and must return `real_path_identity_mismatch`.

## 9. Ratified-kernel cross-check

| Kernel / owner | Result |
| --- | --- |
| S0-K08 append-only correction | Pass: correction, renewal, replay failure, hold, and remediation append without rewriting history. |
| S0-K09 Custody Time Model | Pass: effective, processing, query, compromise, expiry, and authenticated-time roles remain distinct. |
| S0-K10 durable suspension / wake only a candidate | Pass: WD-08/WD-12 and F-03 preserve the rule. |
| PV-K01 separate reportable verification dimensions | Pass: RC-06 and replay semantics do not collapse authenticity, public history, durable verifiability, interpretation, and current authority. |
| PV-K02 present failure does not erase historical act | Pass across compromise, source loss, rollback, verifier absence, succession conflict, differential interpretation, and hold. |
| INT-K05 / GY-N12 sole currentness owner | Pass: OPS-R14 consumes the owner and creates no second runtime chronology/currentness owner. |
| INT-R7 real-path and disconnected pre-live evidence | Pass at research-specification level: DE-04/DE-05 preserve non-circular real-path, digest, network-denial, and anti-substitution requirements. No runtime passage is claimed. |
| PAO-R36 F11 seam | Pass: complete six-part conjunction everywhere closure is claimed. |
| P37 declared-gate predicate rule | **Fail:** F-14 yields positive scoped custodian conclusions from `PP-36 = institutionally_supplied`. |

## 10. Finding register

### AV-B01 — blocking — R7 closure is not audit-conformant

The package does not retain or identify the audit-required complete census evidence, omits the second
file-type census for seven literals, and supplies no matching second run. High-cardinality and zero
claims remain unverified here. The amendment's “R7 closed” statement is not accepted as evidence.

### AV-B02 — blocking — F-14 violates registered P37

The package classifies organizational succession scope as `institutionally_supplied` and then emits
positive current-custodian conclusions from it. The last-three-class positive-gate prohibition is
violated.

### AV-N01 — non-blocking — R8 refusal leaves currentness claims standing

Stable identifiers and transfer limits are preserved, but dated and explicit “current” source claims
remain without the fresh retrieval record that the amendment says was unavailable.

## 11. Reach, budget, and stop statement

All commissioned areas were reached: branch orientation, changed-file/line census, low-cardinality
source adjudication, three-axis standing, R8, R11, P37 vocabulary/register/probes, F-14–F-17, ratified
kernel cross-check, classification, and connector-backed delivery.

The exact byte-walk tuples for `expires_at`, `ttl_seconds`, `expiry`, `grace_period`, `not_after`, and
`revocation_time` were **not** independently reproduced. That is stated as AV-B01 rather than silently
reported clean. No inference from the amendment's summary or from an index was used to close those
rows.

## 12. Final decision

**Verdict: `NO_GO`.**

The amended research package may retain its separately reported
`research_standing: accepted_narrow_scope`; this conformance verification does not challenge the
substantive bounded architecture as a whole. It finds that the amendment package, as delivered, does
not conform completely to the independent audit and registered P37 kernel it claims to satisfy.

The amendment's own operational fields remain correctly negative:

- `capability_standing: NO_GO`
- `gate_standing: NO_GO`
