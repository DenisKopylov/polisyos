---
id: OPS-R14-REMEDIATION-LEDGER
artifact_kind: bounded_research_remediation_ledger
status: completed_bounded_remediation
research_standing: accepted_narrow_scope
capability_standing: NO_GO
gate_standing: NO_GO
amendment_branch: research/ops-r14-amendment
amendment_head: 83539ebf0a211728cf3cb8cef4cbffce8429a8bb
verification_branch: research/ops-r14-amendment-verification
verification_head: 0fe8fe6a0e53f23a90b92e06bad2d48543753693
verification_blob: c403d273482fedea1bbae775e87c7810ee5420cf
audit_head: 34c65a04ef178b9a59f70b9fb2012edee17a67cd
repository_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
output_branch: research/ops-r14-remediation
retest_required: true
may_not_use_for:
  - amendment beyond AV-B01, AV-B02, or AV-N01
  - production implementation authorization
  - final wire, schema, package, database, serialization, or API contract
  - canonical owner, vendor, custodian, archive, or service appointment
  - escrow agent appointment
  - authority grant
  - delegation grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - permission to sign
  - automatic amendment of any plan, backlog, or system-design decision
  - automatic amendment of the status lattice
  - proof that any retention period is legally sufficient
  - absorption of OPS-R12 institutional-scale continuity scope
  - re-adjudication of accepted audit findings
---

# OPS-R14 bounded remediation ledger

## 1. Scope and rule

This remediation addresses exactly the three findings in the independent conformance verification at
`research/ops-r14-amendment-verification@0fe8fe6a0e53f23a90b92e06bad2d48543753693`:

1. `AV-B01` — census provenance, dual denominators, and P37 treatment;
2. `AV-B02` — F-14 succession conclusions under P37; and
3. `AV-N01` — completion of the R8 currentness refusal.

No accepted audit finding is reopened. No architecture, runtime capability, status lattice, owner,
wire, vendor, retention period, legal conclusion, or implementation authorization is added. The
failure-patterns register and `AGENTS.md` are not changed.

The three standing fields remain exactly:

- `research_standing: accepted_narrow_scope`
- `capability_standing: NO_GO`
- `gate_standing: NO_GO`

The PAO-R36 F11 seam remains exactly:

`RP-10 + RC-01 + RC-07 + F-04 + F-09 + DE-07`

## 2. Finding dispositions

| Verification finding | Disposition | Bounded remediation | Reason |
| --- | --- | --- | --- |
| `AV-B01` | **`closed_with_variation`** | Retain both all-source and Python-only tuples, the pin, path denominator, fixed-string/binary-exclusion semantics, exact command template, and the architect's reported two identical clean-archive walks. Classify PP-01 as `institutionally_supplied`, not `recomputed`. Treat the three supplied zeroes as reproducible but `not_established` for this package. | The package environment still cannot execute the recursive byte walk. Closure is therefore the correct P37 label and consequence, not a claim of package recomputation. |
| `AV-B02` | **`closed_with_variation`** | Split the single F-14 family into two mutually exclusive worlds: F-14A permits a scoped positive only after exact content-bound instruments and admission receipts are independently reconciled against a non-producing authoritative record; F-14B leaves all declarations and markers intact while falsifying that premise and returns `succession_scope_not_established`. | R9 already required the same admitted-instrument test for unilateral option exercise. The pre-remediation package was internally inconsistent: F-14 emitted positives while PP-36 remained `institutionally_supplied`. The split preserves deterministic verdicts and registered P37. |
| `AV-N01` | **`closed`** | Preserve stable identifiers and transfer limits, continue to decline URL refresh without a fresh retrieval record, and remove or qualify every source-currentness proposition. PP-35 remains the controlling non-positive requirement. | A refusal now refuses both the unsupported link refresh and the unsupported currentness claim; it no longer leaves the latter standing. |

## 3. AV-B01 — census provenance and consequence

### 3.1 Retained reproduction contract

**Pin:** `109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`  
**Path denominator:** `policy-engine/src`  
**Match semantics:** case-sensitive fixed string; binary files excluded  
**Provenance:** architect-supplied report of two clean-archive runs with identical results

Run from `policy-engine/src`. The bracketed include option denotes the Python-only variant:

```text
grep -rIl --binary-files=without-match [--include='.py'] -F <token> . # files
grep -rI --binary-files=without-match [--include='.py'] -F <token> . # matching lines
grep -rIo --binary-files=without-match [--include='*.py'] -F <token> . # occurrences
```

| Token | All-source files / lines / occurrences | Python-only files / lines / occurrences |
| --- | ---: | ---: |
| `legal_hold` | **2 / 7 / 8** | **2 / 7 / 8** |
| `renewal` | **4 / 4 / 4** | **1 / 1 / 1** |
| `expires_at` | **50 / 281 / 364** | **49 / 280 / 363** |
| `ttl_seconds` | **30 / 116 / 148** | **30 / 116 / 148** |
| `expiry` | **28 / 103 / 122** | **27 / 102 / 121** |
| `grace_period` | **0 / 0 / 0** | **0 / 0 / 0** |
| `not_after` | **0 / 0 / 0** | **0 / 0 / 0** |
| `revocation_time` | **0 / 0 / 0** | **0 / 0 / 0** |

The all-source denominator exposes one non-Python member each for `expires_at` and `expiry`. The
single-denominator presentation hid those members.

### 3.2 P37 treatment

PP-01 is now `institutionally_supplied`. The package retains reproducibility information but cannot
use this census as a positive gate predicate. In particular, `grace_period`, `not_after`, and
`revocation_time` are no longer described as true zeroes, settled facts, or established absences.
Their package result is `not_established`.

This treatment does not erase the independent semantic finding that no admitted runtime capability
combines the complete governed-renewal chain. That finding rests on the inspected owner, consumer,
and capability evidence rather than promotion of a supplied lexical zero.

## 4. AV-B02 — F-14 and the falsify-the-declaration proof

### 4.1 Resolution selected

The remediation takes the verification's split-world option while retaining one numbered fixture
family and the seventeen-family denominator.

**F-14A — admitted-instrument world.** Exact instrument bytes and admission receipts are reconciled
against a non-producing authoritative record for authority, scope, timing, notice, conditions, and
effective time. The predicate is `independently_reconciled`. The exact verdict may be
`scoped_succession_partial`: established non-overlap is reported for A and B, the disputed overlap is
`not_established`, and issuer O remains unchanged.

**F-14B — merely supplied or falsified world.** Successor names, scope declarations, instrument refs,
and `admitted=true` markers remain intact, but the exact bytes are absent, contradict the declaration,
or fail reconciliation against the authoritative record. The predicate remains
`institutionally_supplied`. The exact verdict is `succession_scope_not_established`, with no positive
current-custodian conclusion.

This is not a new architecture. It applies the admitted-instrument test that R9 already required. The
package's defect was an internal classification/conclusion mismatch.

### 4.2 Falsify-the-declaration result

The F-14B probe leaves every declaration and marker intact and falsifies the succession premise. The
gate must return `succession_scope_not_established`; a green current-custodian result is forbidden.
The probe therefore goes red on the property rather than passing on the declaration.

## 5. AV-N01 — complete source-currentness sweep

The nine-artifact sweep distinguishes source-currentness assertions from ordinary uses of the word
“current” in authority-time, status, or owner semantics.

| Artifact | Surviving source-currentness claim before remediation | Remediation / adjudication |
| --- | --- | --- |
| Primary report | The external-source synthesis was described without an explicit present-currentness boundary. | The summary now says stable identifiers and historical transfer analysis are retained, while present official status, successor identity, URL resolution, and continued currency remain `not_established` pending PP-35 reconciliation. |
| Amendment ledger | R8 was described as deferred, but the body currentness assertions were left standing. | The disposition now records that URL refresh remains declined and that the bounded remediation removes or qualifies every currentness assertion. |
| Custody objectives | No positive external-source-currentness claim. “Currentness” refers to authority-time ownership and is already non-positive through GY-N12/PP-35 boundaries. | No token change required. |
| Disaster fixtures | F-06 already makes current official status non-positive when the source vanishes. | No unsupported positive source-currentness claim survives; no token change required for AV-N01. |
| External source ledger | Historical review date; “current federal rules”; “current eCFR”; “current U.S. Courts rules page”; “current FAC 2026-01”; current-eCFR-over-historical-numbering adjudication; dated UK call-for-views/current-source statement; and synthesis phrased without a present-currentness disclaimer. | The review date is historical metadata only; each row is phrased as recorded review content; exact current targets and present currency are not reverified; the UK note is a historical review record; the NARA/eCFR adjudication is bounded to that record; the synthesis expressly imports no present-currentness finding. Frontmatter states `source_currentness: not_established`. |
| Long-term replay | RP-09 already separates retained historical capture from present official status. | No unsupported positive source-currentness claim; current official status remains non-positive absent independently authenticated successor evidence. |
| Orientation ledger | No external-source-currentness proposition. | No token change required for AV-N01. |
| Repository integration handoff | “Currentness” names GY-N12's semantic ownership, not the present currency of an external source. | No token change required. |
| Watched dependency / hold semantics | “Currentness” concerns protected-use evaluation and jurisdiction-pack review, with GY-N12 as owner. | No external-source-currentness positive; no token change required. |

Stable identifiers, URLs as historical locators, and transfer/non-transfer limits remain. None is now
represented as proof that an external source is presently official, live, unsuperseded, or current.

## 6. Files changed by this bounded remediation

The remediation modifies only these existing Markdown artifacts and adds this Markdown ledger:

1. `ops-r14-custody-resilience-and-expiring-authority.md`;
2. `ops-r14/amendment-ledger.md`;
3. `ops-r14/disaster-fixtures-and-drill-evidence.md`;
4. `ops-r14/external-primary-source-and-transfer-ledger.md`;
5. `ops-r14/long-term-replay-and-preservation.md`;
6. `ops-r14/orientation-ledger.md`; and
7. `ops-r14/remediation-ledger.md`.

No source, test, workflow, binary, staging, transport, `AGENTS.md`, or failure-patterns-register path
is changed.

## 7. Stop, budget, and retest decision

All three commissioned findings were reached. No repair required work beyond their bounded scope.
Nothing was left unfinished because of budget.

This ledger records remediation dispositions, not a new independent conformance verdict. The package
**should now be independently re-tested** against `AV-B01`, `AV-B02`, `AV-N01`, and registered P37.
The prior `NO_GO` verification verdict is not self-reversed by the subject of that verification.

**Research standing:** `accepted_narrow_scope`.  
**Capability standing:** `NO_GO`.  
**First-public-signature gate standing:** `NO_GO`.
