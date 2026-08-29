# INT-R5 Anchor And Citation Verification

## 1. Method

This verification distinguishes four anchor classes:

1. **content anchor** — exact path, commit and blob identity;
2. **construct anchor** — exact class/function/field/operation identity;
3. **historical receipt** — a closure document or commit message recording a prior measured result;
4. **external-source anchor** — stable identity of a statute, case, standard, report or supplied
   research artifact supporting a claim.

A content anchor proves bytes. A construct anchor proves the referenced implementation exists. A
historical receipt proves what the record says was measured, not that the present tree still has the
same state. An external-source anchor must let a later reader recover the evidence rather than only a
researcher's paraphrase.

The audit verified anchors at package head `02e203de90d51280d569e7f641a158569ae4df39`
and repository baseline `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`.

## 2. Repository Anchors

### 2.1 Package-byte identities

| Package file | Lines | Blob SHA | Result |
|---|---:|---|---|
| `docs/research/policy-operations/int-r5-decision-authority-validity.md` | 833 | `e5cfc1ad996e24fb4b59215894ff78ce8b3ea114` | resolved |
| `docs/research/policy-operations/int-r5/decision-authority-specification.md` | 605 | `8eec97a2ddc4d192584455e1557eb8a378b6bc29` | resolved |
| `docs/research/policy-operations/int-r5/external-evidence-ledger.md` | 448 | `80d0d948c8b346563e9f6a867ba0a7eadf996af5` | resolved |
| `docs/research/policy-operations/int-r5/adversarial-fixtures.md` | 443 | `02efeadec5cf362f95ab8acf3845c525a3658747` | resolved |
| `docs/research/policy-operations/int-r5/repository-baseline.md` | 231 | `fe795bbf7eea0655a84bd4e43d743e04a892a7bd` | resolved |

The five-file package identity is therefore independently recoverable from the audit branch.

### 2.2 Governing-document anchors

The following governing files resolve at the package head and are substantively used:

| Governing artifact | Audit use | Result |
|---|---|---|
| `docs/reference/policy-operations-research-pipeline.md` | stage topology, seven audit artifacts, severity arithmetic, readback | resolved and applied |
| `docs/research/policy-operations-and-real-world-runtime-backlog.md` | INT-R5 task row, mandatory baseline, research quality bar, UDF and operational closure | resolved |
| `docs/system-design-decisions/wave4-decision-evidence-ratification.md` | W4-K01, W4-K02, W4-K05, W4-K06 | resolved |
| `docs/system-design-decisions/policyos-identity-and-custody-boundary.md` | OWN/INTEGRATE/OBSERVE/OUT_OF_SCOPE | resolved by package and audit |
| `docs/research/policy-operations/pao-r4-individual-decision-firewall.md` | individual-use boundary | resolved and crosschecked |

### 2.3 Executable construct anchors

| Package statement | Construct anchor inspected | Result |
|---|---|---|
| PA2 five-predicate operational authority | `runtime/quality/agent_action_authority.py::evaluate_agent_action_authority` and strict delegation models | present; narrow description supported |
| bounded delegation envelope | `runtime/quality/design_axes/mandate_bounded_delegation.py::DelegatedActionEnvelope` | present |
| DS9 raw-source currentness and guarded persistence | `runtime/http/services/human_decisions.py::HumanDecisionService`; `routes/human_decisions.py` | present |
| DS9 reviewer separation | `runtime/http/services/human_decision_contracts.py::ReviewerSeparationCredential` | present |
| DS20 exact permission/resource binding | `runtime/http/authorization.py`, `resource_binding.py`, `permissions.py` | present |
| DS20 step-up | `runtime/http/step_up.py::StepUpClass`; route dependencies | present |
| acquisition route | `runtime/http/routes/control.py::ingest_data` | present, but only DS20 permission and acquisition step-up are wired |
| acquisition effect implementation | `runtime/http/services/control/run_lifecycle.py::ControlPlaneService.run_data_ingestion` | present; directly executes ingestion; no PA2/DS9 call |
| production approval resolver omitted from ten-file closure | `runtime/quality/approval.py` | present, demonstrating denominator incompleteness |
| existing namespaced certificate-stale blocker | `runtime/quality/evaluation_safety.py` blocker construction | present; conflicts with bare provisional refusal code identity |

### 2.4 Historical receipts

The package uses three important historical receipts:

| Receipt | What it supports | Verification result |
|---|---|---|
| GY-PA2 closure commit `82474845a…` | PA2 shipped before INT-R5 | commit resolves and records closure |
| DS9 merge `fd243d1ad…` | DS9 shipped and closed 24/24 | commit resolves and records closure |
| DS20 merge `03ebc1ce8…` | 29 unsafe POST operations and historical 33-value vocabulary | commit resolves; current 34-value state must be read separately |

The package correctly treats the DS20 33 as a historical receipt, not the current vocabulary size.

## 3. External-Evidence Anchors

### 3.1 What the branch preserves

`external-evidence-ledger.md` preserves:

- five survey titles/subjects;
- claim classification such as named legal rule, formal mechanism, control pattern, empirical
  finding, engineering inference or disagreement;
- named regimes, statutes, cases, standards and institutions;
- limitations and jurisdiction qualifiers.

This is good semantic discipline. It prevents a Delaware quorum rule, a UK consultation rule or a
FAR cure mechanism from silently becoming a universal PolicyOS rule.

### 3.2 What the branch does not preserve

The branch does not preserve a stable identity for the five supplied survey artifacts. There is no:

- committed survey copy;
- content hash;
- repository or durable archive reference;
- bibliographic manifest;
- claim-to-survey section/line anchor;
- source retrieval/effective date ledger;
- exact primary-source URL or identifier list for every transferred claim.

The audit could inspect the reports only because they were separately supplied in the audit session:

1. delegation, acting, subdelegation, amount, emergency, revocation and cure;
2. collegial-body validity, forum, quorum, vote and co-signature;
3. COI, recusal, SoD and self-approval;
4. pre-action proof, freshness and mid-operation revocation;
5. cross-agency acceptance and act-effect distinctions.

A reader of the Git branch alone cannot recover those exact inputs. The package therefore has a
semantic transfer ledger but not an independently replayable evidence ledger.

Disposition: `INT-R5-A-005`, **material**.

### 3.3 Minimum source-manifest shape

A revision should add, without importing external vocabulary into the repository contract:

```yaml
survey_id: stable package-local identifier
title: exact title
content_hash: sha256 of admitted survey bytes
source_ref: durable repository/archive reference
inspection_date: date
claim_anchors:
  - package_claim_id
    survey_section_or_line_range
    source_class
    jurisdiction_or_standard
    primary_source_refs
    limitation
```

The source manifest is custody metadata. It is not a legal-compliance conclusion or production
contract.

## 4. Broken Or Misleading Anchors

### 4.1 “Canonical executable denominator”

The package's strongest misleading anchor is not a wrong path. It is the label placed on a selected
set of paths.

The ten named files all exist and were read. But direct import/call inspection reaches omitted owners
for security, identity, authority metadata, reconciliation, event logging, artifact writing,
reservation/idempotency, production approval and the real acquisition effect. Thus the list is a
**selected strict authority slice**, not the complete executable owner closure.

Any anchor that says “absence in these ten files” is valid. An anchor that says “absence in the
complete production authority chain” is not.

Disposition: `INT-R5-A-003`, **material**.

### 4.2 Acquisition “composition”

The package anchors acquisition to the correct route and correctly identifies:

```text
RuntimePermission.EVIDENCE_ACQUIRE
runtime.evidence.acquisition
StepUpClass.ACQUISITION_APPROVAL
```

It then extends that anchor beyond the code by saying PA2 and DS9 are part of the same effect path.
The route and service contain no such edge. This is authority by adjacency: three real mechanisms are
near each other in architecture and are narrated as one landed composition.

Disposition: `INT-R5-A-002`, **material**.

### 4.3 Ordering count

The package and orientation name GY-PA2, DS9 and DS20 together as three violations of one ordering
constraint. The task row uses two different relationships:

```text
must land before GY-PA2 or DS9/DS14 consumers close
feeds DS20 vocabulary and acquisition-approval flow
```

At the pin, the first predicate has two violations: GY-PA2 and DS9. DS14 is unstarted. DS20 is a
missed feed/dependency, not a third closed consumer under the exact sentence.

Disposition: `INT-R5-A-009`, **minor**.

### 4.4 Bare refusal-code anchors

The fixtures cite bare uppercase values as if they were stable construct identities. The
specification simultaneously says final registered vocabulary and namespaces remain downstream.
Those positions are inconsistent once fixtures use the tokens as expected outputs.

`CERTIFICATE_STALE` is especially revealing because the runtime already has a namespaced
`certificate_stale` blocker in another authority family. The package needs a namespace/crosswalk or a
clear non-binding placeholder notation before these become acceptable oracle anchors.

Disposition: `INT-R5-A-006`, **material**.

## 5. Citation Sufficiency

### 5.1 Sufficiently anchored claims

The following are sufficiently anchored for a research package:

- package pin, branch and file set;
- GY-PA2/DS9/DS20 construct descriptions within their narrow scopes;
- permission parity and documentation drift;
- DS9 as a reusable future pre-effect seam;
- capability standing `absent/unallocated`;
- PAO-R4's conceptual non-substitution boundary;
- profile-relative quorum and conflict-detectability conclusions when read with the supplied surveys.

### 5.2 Insufficiently anchored claims

The following require revision:

| Claim | Anchor defect |
|---|---|
| complete repository absence for six attributes | denominator is not complete closure |
| acquisition PA2/DS9/DS20 composition | route/call edge absent |
| every decisive field has a non-requester producer | no construct owner for time/effect/profile selection |
| exact transfer from five surveys | survey bytes/claim anchors absent from branch |
| stable local refusal codes | no namespace/version/crosswalk |
| third identical ordering violation | relationship type changed between backlog and count |

### 5.3 No line-number binding introduced

This audit deliberately cites symbols, sections, commit IDs and blob IDs. It does not make the
validity of a claim depend on a mutable source line number. Line ranges may remain navigation aids,
never construct identity.

## 6. Conclusion

The package's repository anchors are generally real. The hostile failures arise when the package
moves one step beyond them:

- real files become a purported complete closure;
- real adjacent gates become a purported composition;
- real named sources become a purported replayable evidence ledger;
- real local reasons become purported stable vocabulary.

The recommended revision is therefore not “add more citations” in the abstract. It is to bind every
load-bearing claim to the correct **kind** of anchor: complete denominator, real call edge,
independent producer or durable external evidence identity.
