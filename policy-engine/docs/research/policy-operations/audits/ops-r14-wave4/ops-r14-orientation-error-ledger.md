---
title: "OPS-R14 Orientation Error Ledger"
audit_id: OPS-R14-WAVE4-INDEPENDENT-AUDIT
status: completed_with_recorded_access_limit
verified_commit: 3a694212aa47c4c2d8a631f8edc4ba8f7e15dce7
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
authoritative_for:
  - independent_orientation_audit_of_ops_r14
  - count_denominator_reconciliation
  - repository_baseline_agreements_and_errors
may_not_use_for:
  - production_implementation_authorization
  - production_capability_claim
  - final_wire_schema_package_database_serialization_or_api_contract
  - canonical_owner_vendor_custodian_archive_service_or_escrow_appointment
  - authority_or_delegation_grant
  - legal_sufficiency_or_jurisdictional_conclusion
  - permission_to_publish_sign_or_open_a_gate
  - creation_or_amendment_of_a_status_lattice
  - automatic_amendment_of_any_plan_backlog_or_system_design_decision
  - assessment_or_adoption_of_pao_r36_quality
research_only: true
---

# OPS-R14 orientation error ledger

## 1. Exact scope and method

This ledger audits the eight OPS-R14 Markdown artifacts at
`3a694212aa47c4c2d8a631f8edc4ba8f7e15dce7` against
`main@1a7a2d05ebba22fae80e9934329e4b880806588e`.

The connected GitHub interface was used for exact-ref reads and writes. It can search its code index,
fetch named files, compare commits, and read branches. It does **not** expose a recursive Git-tree read
or repository archive. Ordinary clone, raw download, `curl`, and `gh` all failed because this
execution environment could not resolve GitHub hosts. I therefore distinguish:

- **byte-walk census**: a script reads every file in the denominator and counts exact literal matches;
- **indexed candidate census**: exact-ref search returns candidate paths, followed by named-file reads;
- **semantic absence search**: several independent names and owner/consumer concepts return no source
  candidate.

`P35` permits no substitution of the second or third for the first. Where the byte-walk could not be
completed, the count is marked `not_established` rather than guessed. The required revision register
states the command/output that would settle it.

### Count vocabulary

- **files**: distinct files with at least one exact, case-sensitive literal;
- **matching lines**: physical lines with one or more exact literals;
- **occurrences**: all non-overlapping literal appearances, including two on one line;
- **denominator A**: all file types under `policy-engine/src`;
- **denominator B**: Python files under `policy-engine/src/**/*.py`.

## 2. Count reconciliation

| Literal | Commission claim | Independent result | Verdict |
| --- | ---: | --- | --- |
| `expires_at` | 49 files | Exact-ref search produced 50 candidates; direct inspection proved at least one search false positive (`runtime/http/openapi_contract.py`) and corroborated the 49-file Python denominator. A byte-walk total for matching lines and occurrences was not obtainable through the connector. | **49 files corroborated; matching lines and occurrences `not_established`.** |
| `ttl_seconds` | 30 files | Exact-ref search produced 33 candidates. Direct reads showed search normalization/substring false positives, including uppercase-only settings material. No complete byte-walk was available. | **30-file claim plausible and strongly corroborated, but files/lines/occurrences remain `not_established` at P35 byte-walk standard.** |
| `expiry` | 27 files | Exact-ref search produced 32 candidates because search normalization also returns related forms and import/export files. No complete byte-walk was available. | **27-file claim plausible and strongly corroborated, but files/lines/occurrences remain `not_established` at P35 byte-walk standard.** |
| `legal_hold` | 2 files | **2 files / 4 matching lines / 5 occurrences**, denominator A. | **Agrees.** |
| `renewal` | 1 file | Denominator A: **4 files / 4 matching lines / 4 occurrences**. Denominator B: **1 file / 1 matching line / 1 occurrence**. | **Both figures are right under different denominators; the commission omitted its Python-only denominator.** |
| `grace_period` | 0 files | Exact-ref indexed search returned zero source candidates. | **0 indexed files; byte-walk lines/occurrences `not_established`.** |
| `not_after` | 0 files | Exact-ref indexed search returned zero source candidates. | **0 indexed files; byte-walk lines/occurrences `not_established`.** |
| `revocation_time` | 0 files | Exact-ref indexed search returned zero source candidates. | **0 indexed files; byte-walk lines/occurrences `not_established`.** |

### 2.1 Exact low-cardinality anchors

`legal_hold` appears only in:

1. `policy-engine/src/polisyos/fabric/security/retention.py:37,103,108` — four occurrences
   because line 108 contains the literal twice; and
2. `policy-engine/src/polisyos/fabric/world/store/snapshots.py:666` — one occurrence.

The behavior is narrow: a snapshot retention class, classification from a flag/tag, and protection
from snapshot garbage collection. The tests prove encryption metadata is required for the held
snapshot and that the snapshot survives GC. They do not prove a general hold lifecycle across all
stores.

`renewal` appears in:

1. `policy-engine/src/polisyos/runtime/http/services/control_worker.py:85` — worker **lease** renewal;
2. three data-catalog CSV fixture descriptions concerning urban or strategic renewal.

Only item 1 is operational code. It renews a processing lease, not a delegation, agreement, licence,
certificate, consent, budget, contract, audit right, or review authority.

## 3. Does the semantic expiry finding survive?

**Yes. Strongly.** The proposition is not the exact number 49, 30, or 27. It is that the repository
has many time-point/TTL constructs but no governed renewal event with all of:

- a renewal owner **role** and succession/escalation path;
- lead time derived from the real renewal process;
- sufficient renewal evidence and competent evidence source;
- affirmative grace authority rather than a retry window;
- failure consequence for the protected action;
- reproducible affected-case query; and
- public effect.

Independent exact-ref searches found no admitted runtime source candidate for
`WatchedDependencyRecord`, `renewal_owner`, `renewal_evidence`, or `affected_case_query`. The only
Python `renewal` literal is unrelated worker-lease documentation. The semantic conclusion therefore
does not depend on the unresolved high-cardinality line/occurrence totals.

## 4. Orientation agreements and errors

| ID | Supplied/audited statement | Audit result | Evidence |
| --- | --- | --- | --- |
| O-01 | Audited branch is 8 commits ahead, with 8 added Markdown files, 2,536 insertions and no deletion/modification. | **Agrees exactly.** | GitHub exact-ref comparison `1a7a2d0...3a694212`. |
| O-02 | All eight artifacts carry `may_not_use_for`. | **Agrees.** | Complete eight-file read at the audited head. |
| O-03 | Five named recovery runbooks exist and are substantive. | **Agrees.** They contain actual commands, triage, recovery and evidence steps. | `docs/runbooks/replay-or-restore.md`; `retained-artifact-recovery.md`; `artifact-corruption-recovery.md`; `key-rotation.md`; `fabric-quarantine-dlq-and-data-plane-recovery.md`. |
| O-04 | Runbook presence is not a qualifying drill. | **Agrees.** | OPS-R14 `DE-01`–`DE-10`; INT-R7 controlling drill amendment. |
| O-05 | `legal_hold` is exactly two source files. | **Agrees and reproduces lines/occurrences.** | Anchors in §2.1. |
| O-06 | `renewal=4` on all file types corrects the commission. | **Agrees, with denominator qualification.** | Anchors in §2.1. |
| O-07 | GY-N12 owns currentness/epochs/reissue and is not implemented. | **Agrees by finding/task identity.** | `docs/plans/active/layer3-slices/GY-engine-subordination.md:2053-2120`. |
| O-08 | INT-R7 is delivered and requires a pre-live disconnected ceremonial drill. | **Agrees.** | `int-r7/lifecycle-migration-preservation.md:558-606`. |
| O-09 | OPS-R14/PAO-R36 seam is declared. | **Agrees.** | backlog `:512-532`; both branch artifacts. |
| O-10 | Institutional-scale continuity remains OPS-R12. | **Agrees.** | backlog `:130-151,500-505`. |

## 5. Findings from Pass I

### OPS-R14-I-001 — minor — denominator ambiguity in the commission

The commission's `renewal=1` is correct only for Python source. The delivered orientation correctly
counts all file types, but should state both denominators at first use. The discrepancy does not alter
the semantic result.

### OPS-R14-I-002 — minor — high-cardinality lines/occurrences remain unresolved

OPS-R14 correctly refused to fabricate high-cardinality lexical totals. This independent audit could
corroborate file sets but could not complete the byte walk because neither a recursive tree/archive
nor ordinary network checkout was available. The audit therefore does not claim exact matching-line
or occurrence totals for `expires_at`, `ttl_seconds`, or `expiry`.

### OPS-R14-I-003 — commendation — semantic correction and preemptive worker-lease guard

The work both corrects the all-file `renewal` denominator and explicitly prevents the only operational
hit from being laundered into proof that expiring authority is governed. That guard is correct and
should survive consolidation.

## 6. Required settlement evidence

A later re-verification should run, at the pin, a script equivalent to:

```text
for each literal in the eight-token set:
  walk every regular file under policy-engine/src
  count distinct matching files
  count physical matching lines
  count non-overlapping exact lowercase occurrences
  report both all-file and Python-only denominators
```

The retained output must include the exact file list and SHA-256 of the script and pin. A connector
candidate count or a truncated grep is not enough.
