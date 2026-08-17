---
id: OPS-R14-ORIENTATION
artifact_kind: research_orientation_ledger
status: research_only
standing: NO_GO
repository: DenisKopylov/polisyos
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
inspection_date: 2026-08-06
may_not_use_for:
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
  - design of PAO-R36 correction, notice, subscriber fan-out, or correction-feed semantics
---

# OPS-R14 orientation ledger

## 1. Inspection boundary and method

All repository readings in this ledger are pinned to commit
`1a7a2d05ebba22fae80e9934329e4b880806588e`. Ordinary HTTPS cloning was attempted first and failed in
this execution environment because outbound DNS and direct HTTPS access to GitHub were unavailable.
The connected GitHub exact-ref interface was therefore used, as permitted by the commission. No CI
workflow, upload fragment, staging directory, self-executing automation, or repository workaround was
created. This follows the delivery rule at `AGENTS.md:27`.

The connected interface can fetch named files at an exact ref and can search its exact-ref code index.
It cannot enumerate a recursive Git tree, expose a raw repository archive, or guarantee byte-exact
lexical search semantics. Its search also stems some terms. Consequently:

- named-file existence, contents, and exact line claims are established by `fetch_file` at the pin;
- low-cardinality literal counts are established only where every candidate file was fetched and the
  literal was counted directly;
- high-cardinality set claims are not treated as complete-tree censuses merely because code search
  returned a finite result set;
- a code-search candidate count is recorded as a diagnostic, not silently promoted to a lexical file,
  matching-line, or occurrence count.

This distinction applies the repository's `P35` rule: a set-level claim needs a complete denominator,
not a sampled or truncated search (`policy-engine/docs/reference/policy-design-case-failure-patterns.md:78`).
Authority claims below cite the controlling finding ID rather than adjacent prose, applying `P36`
(`policy-engine/docs/reference/policy-design-case-failure-patterns.md:79`).

### 1.1 Count vocabulary

- **files**: distinct files containing at least one exact, case-sensitive literal token;
- **matching lines**: physical source lines containing at least one such token;
- **occurrences**: non-overlapping literal-token appearances, including multiple appearances on one
  line;
- **indexed candidate files**: files returned by the connector search; this is not a synonym for any of
  the three lexical counts above.

## 2. Orientation results

| Supplied claim | Independent result | Verdict | Evidence and limitation |
| --- | --- | --- | --- |
| The pin is on `main`. | Commit metadata identifies the exact object and the exact-ref repository reads succeeded. A local ancestry test could not run because cloning was blocked. | **Partly established.** The commit exists and is readable; branch ancestry is not independently established in this environment. | Exact-ref commit read. The limitation is recorded rather than inferred away. |
| `AGENTS.md:27` contains the delivery rule. | The rule requires branch read-back and forbids CI workflows, base64 fragments, staging directories, and self-executing automation as blocked-egress workarounds. | **Agrees.** | `AGENTS.md:25-28`. |
| There are 27 runbooks in `policy-engine/docs/runbooks/`. | Exact-ref indexed search returned 27 Markdown candidates. `index.md` routes 24 procedures. The five named in-scope files all exist and were read in full. Recursive tree enumeration is unavailable. | **Corroborated, not P35-established as a complete directory count.** | `policy-engine/docs/runbooks/index.md:1-76`; five named files below. |
| The five directly in-scope runbooks exist. | All five exist and contain operational steps, commands, checks, and evidence locations. | **Agrees.** | `policy-engine/docs/runbooks/replay-or-restore.md:1-128`; `policy-engine/docs/runbooks/retained-artifact-recovery.md:1-180`; `policy-engine/docs/runbooks/artifact-corruption-recovery.md:1-119`; `policy-engine/docs/runbooks/key-rotation.md:1-113`; `policy-engine/docs/runbooks/fabric-quarantine-dlq-and-data-plane-recovery.md:1-178`. |
| `expires_at` occurs in 49 source files. | Exact-ref quoted search returned **50 indexed candidate files**. Because the connector cannot perform a recursive byte walk and search semantics are not guaranteed lexical, exact files, matching lines, and occurrences are not established. | **Not established; no correction claimed.** | Diagnostic only: 50 indexed candidates under `policy-engine/src`. |
| `ttl_seconds` occurs in 30 source files. | Search returned **33 indexed candidate files** under the same limitation. | **Not established; no correction claimed.** | Diagnostic only: 33 indexed candidates. |
| `expiry` occurs in 27 source files. | Search returned **32 indexed candidate files** under the same limitation. | **Not established; no correction claimed.** | Diagnostic only: 32 indexed candidates. |
| `legal_hold` occurs in 2 source files. | Exact lowercase literal: **2 files, 4 matching lines, 5 occurrences**. | **Agrees on files; adds line and occurrence counts.** | `policy-engine/src/polisyos/fabric/security/retention.py:37,103,108`; `policy-engine/src/polisyos/fabric/world/store/snapshots.py:666`. The line at `policy-engine/src/polisyos/fabric/security/retention.py:108` contains two occurrences. |
| `renewal` occurs in 1 source file. | Exact lowercase literal: **4 files, 4 matching lines, 4 occurrences**. Only one is Python code, and that occurrence describes worker lease renewal rather than renewal of authority. | **Supplied whole-tree claim is false as written.** | `policy-engine/src/polisyos/runtime/http/services/control_worker.py:85`; `policy-engine/src/polisyos/data_forge/domains/catalog/fixtures/relevant_topics_domain_files/relevant_topics_block_policy_core.csv:34`; `policy-engine/src/polisyos/data_forge/domains/catalog/fixtures/relevant_topics_domain_files/relevant_topics_domain_urban_housing_transport.csv:42`; `policy-engine/src/polisyos/data_forge/domains/catalog/fixtures/relevant_topics_domain_files/relevant_topics_domain_economy_finance_business.csv:58`. |
| `grace_period` occurs in 0 source files. | Exact-ref search returned zero indexed candidates, but complete lexical zero cannot be established without a tree walk. | **Not established; no contradictory candidate found.** | Exact-ref indexed search only. |
| `not_after` occurs in 0 source files. | Same result and limitation. | **Not established; no contradictory candidate found.** | Exact-ref indexed search only. |
| `revocation_time` occurs in 0 source files. | Same result and limitation. | **Not established; no contradictory candidate found.** | Exact-ref indexed search only. |
| The eleven right classes have no renewal owner in source. | No exact-ref source candidate was found for `WatchedDependencyRecord`, `renewal_owner`, `renewal_evidence`, or `affected_case_query`. The sole Python `renewal` hit is a worker lease docstring. A universal absence claim is still not P35-established. | **Strongly corroborated, formally not established as a complete-tree absence.** | `policy-engine/src/polisyos/runtime/http/services/control_worker.py:75-174`; exact-ref negative searches with the limitation above. |
| `legal_hold` is implemented only in `retention.py` and `snapshots.py`. | Those two files contain the lowercase literal. They implement a snapshot retention class, tag/boolean classification, deletion-impact description, and GC protection for selected snapshots. | **Agrees, with a narrower semantic reading.** | `policy-engine/src/polisyos/fabric/security/retention.py:32-38,92-134`; `policy-engine/src/polisyos/fabric/world/store/snapshots.py:654-689`. |
| `renewal` in `control_worker.py` is relevant to expiring authority. | It describes renewing a worker lease heartbeat. It does not name a right, renewal owner, lead time, renewal evidence, grace authority, affected-case query, or public consequence. | **Refuted as an expiring-authority primitive.** | `policy-engine/src/polisyos/runtime/http/services/control_worker.py:84-85,128-174`. |
| There are zero recorded recovery drills. | The in-scope runbooks contain checklists and evidence destinations but no drill event with a frozen corpus, injected failure, measured loss, measured elapsed recovery, restored predicate, or disconnected execution. Acceptance records mark posture green from document presence and a tabletop reading. No complete-tree proof of absolute zero is available. | **The falsifier fires against the inspected acceptance chain; universal zero is not P35-established.** | `policy-engine/docs/archive/reports/platform-acceptance.md:15,23,30`; `policy-engine/docs/archive/reports/platform-acceptance-manual.md:85-95`; five runbooks above. |
| The three ratification acts contain 264, 379, and 439 lines. | Requests beginning at lines 264, 379, and 439 respectively returned their terminal lines and no later content. | **Agrees exactly.** | `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:264`; `policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:379`; `policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:439`. |
| S0-K08, S0-K09, and S0-K10 bind this task. | S0-K08 requires append-only correction; S0-K09 adopts the Custody Time Model; S0-K10 makes suspension durable and wake only a candidate. | **Agrees by finding IDs.** | `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:94-110`. |
| PV-K01, PV-K02, and PV-K07 bind this task. | PV-K01 separates durable verifiability; PV-K02 prevents present evidence failure from erasing historical authenticity; PV-K07 requires reproducible release chronology and is not issuable because its owner is missing. | **Agrees by finding IDs.** | `policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:91-123,182-205`. |
| GY-N12 owns epoch/currentness and is undelivered. | Its normative task body assigns epochs, stale certificates, append-only reissue, and release-family chronology to one planned owner and forbids a parallel time/currentness model. No implementation capability is established. | **Agrees; capability label `contract_only`.** | `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2053-2120`. |
| INT-R7 is delivered and controls minimum public-proof preservation. | Its terminal amendment requires real production-intended paths, a ceremonial pre-live corpus, and disconnected restore; a paper runbook or mocked Boolean does not pass. | **Agrees; consumed, not redefined.** | `policy-engine/docs/research/policy-operations/int-r7-public-verification-lifecycle.md:990-1020`; `policy-engine/docs/research/policy-operations/int-r7/lifecycle-migration-preservation.md:558-650`. |
| OPS-R14 and PAO-R36 share one declared seam. | The backlog assigns durability/recovery/expiry mechanics to OPS-R14 and correction, notice, supersession, cache/subscriber fan-out, and correction feeds to PAO-R36. | **Agrees.** | `policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:500-505,512-532`. |
| Institutional-scale continuity belongs to deferred OPS-R12. | The disposition ledger keeps OPS-R12 deferred; OPS-R14 is explicitly re-scoped to PolicyOS's own signed records and expiring authority. | **Agrees as a scope boundary.** | `policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:130-151,500-505`. |

## 3. What the two low-cardinality literals actually do

### 3.1 `legal_hold`

`SnapshotRetentionClass.LEGAL_HOLD` is a classification value
(`policy-engine/src/polisyos/fabric/security/retention.py:32-38`).
`classify_snapshot_retention()` maps a Boolean or selected tags to that class
(`policy-engine/src/polisyos/fabric/security/retention.py:92-105`). `gc_world_snapshots()` protects snapshots classified as audit-tagged or
legal-hold and snapshots carrying retained tags (`policy-engine/src/polisyos/fabric/world/store/snapshots.py:654-689`).
The deletion-impact object records replay/time-travel impact before deletion
(`policy-engine/src/polisyos/fabric/security/retention.py:108-134`).

This is a useful implemented fragment. It does **not** establish a general legal-hold lifecycle. No
inspected path establishes hold issuance authority, scope over independently failing stores, notice
to downstream custodians, release authority, multiple-hold aggregation, race-free post-release
disposal, correction/supersession interaction, public effect, or drill evidence. Those broader
semantics are `absent/unallocated`, not `bridge_missing`: both endpoints of a bridge are not yet
established.

### 3.2 `renewal`

The Python occurrence is in the `ControlWorker` docstring: the worker performs polling, leasing,
heartbeats, and lease renewal (`policy-engine/src/polisyos/runtime/http/services/control_worker.py:84-85`).
The implementation renews a job-processing lease (`policy-engine/src/polisyos/runtime/http/services/control_worker.py:128-174`). It does not renew a
public-law delegation, agreement, licence, certification, consent, budget authority, contract, or
jurisdiction review. The remaining three occurrences are fixture text about urban or strategic
renewal. The orientation therefore confirms the semantic hole even while correcting the supplied
whole-source-tree file count.

## 4. Runbooks versus drill evidence

The five runbooks are not dismissed. They contain concrete operational mechanisms:

- replay versus restore selection, digest checks, and rollback cautions;
- retained-artifact lookup and recovery tests;
- corruption isolation and fixity checking;
- key-rotation and emergency revocation procedures;
- quarantine, DLQ, checkpoint, deduplication, and replay controls.

Those are necessary inputs to a drill. They are not themselves evidence that recovery objectives
were met. The inspected acceptance report marks runbook presence and retention/restore posture green
from policy and document existence (`policy-engine/docs/archive/reports/platform-acceptance.md:15,23,30`).
Its manual tabletop closes an incident item by reading a runbook rather than executing a restore
(`policy-engine/docs/archive/reports/platform-acceptance-manual.md:85-95`). This is the commission's
second falsifier: the chain accepts documentary preparedness where `PV-K01` needs demonstrated
durable verifiability.

## 5. Orientation conclusion

Pass I changes one inherited fact and narrows several others:

1. `renewal` is **4 files / 4 matching lines / 4 occurrences**, not one file, when the stated
   denominator is all of `policy-engine/src`.
2. Only the one Python occurrence is operational, and it is worker-lease renewal, not authority
   renewal.
3. The `legal_hold` count is exactly **2 files / 4 matching lines / 5 occurrences**, but its meaning is
   snapshot GC protection rather than a cross-store hold lifecycle.
4. The three high-cardinality token counts and three zeroes cannot be independently promoted to
   complete-tree lexical facts under this connector. They remain `not established`, with indexed
   candidate diagnostics recorded.
5. The five in-scope runbooks are substantive procedures, but the inspected evidence chain has no
   qualifying executed, measured, disconnected recovery drill.

These limits are part of the research result. They are not repaired by confident extrapolation.
