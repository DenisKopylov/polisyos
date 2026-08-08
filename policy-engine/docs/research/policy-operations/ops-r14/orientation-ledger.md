---
id: OPS-R14-ORIENTATION
artifact_kind: research_orientation_ledger
status: research_only
research_standing: accepted_narrow_scope
capability_standing: NO_GO
gate_standing: NO_GO
repository: DenisKopylov/polisyos
repository_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
audited_head: 3a694212aa47c4c2d8a631f8edc4ba8f7e15dce7
audit_head: 34c65a04ef178b9a59f70b9fb2012edee17a67cd
inspection_date: 2026-08-06
amendment_date: 2026-08-08
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

The bounded orientation result is accepted. The repository capability and the first-public-signature
gate remain `NO_GO`: this amendment supplies no institutional commitment, runtime chain, or executed
disconnected drill.

## 1. Inspection boundary and count method

Documentation anchors in this amended package are pinned to
`109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`. The architect established that
`policy-engine/src` at that pin is byte-identical to the original research pin
`1a7a2d05ebba22fae80e9934329e4b880806588e`, so source censuses remain directly comparable.

The complete literal census below was supplied by the architect from a complete tree walk using
case-sensitive fixed-string `git grep` over the pinned ref. Its **path denominator** is
`policy-engine/src`; binary files are excluded. Each row states its **file-type denominator**. These
figures are not connector or search-index results. This applies the symmetric P35 index rider at
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:76-80,139-167`: an index
establishes neither a zero nor a positive count.

Count vocabulary:

- **files**: distinct files with at least one exact literal;
- **matching lines**: physical lines with one or more exact literals;
- **occurrences**: all non-overlapping exact appearances, including multiple appearances on one line;
- **all source**: every non-binary file under the path denominator;
- **Python only**: `*.py` files under the path denominator.

Authority claims cite their controlling finding IDs rather than adjacent prose, applying P36.
Load-bearing gate predicates are classified under P37 in the primary report.

## 2. Complete source census

**Pinned ref:** `109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`  
**Path denominator:** `policy-engine/src`  
**Search:** case-sensitive fixed strings; binary files excluded

| Token | File-type denominator | Files | Matching lines | Occurrences | Verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `legal_hold` | all source | **2** | **7** | **8** | Established by complete walk. |
| `renewal` | all source | **4** | **4** | **4** | Established by complete walk. |
| `renewal` | Python only | **1** | **1** | **1** | Established by complete walk. |
| `expires_at` | Python only | **49** | **280** | **363** | Established by complete walk. |
| `ttl_seconds` | Python only | **30** | **116** | **148** | Established by complete walk. |
| `expiry` | Python only | **27** | **102** | **121** | Established by complete walk. |
| `grace_period` | all source | **0** | **0** | **0** | True zero at the pin. |
| `not_after` | all source | **0** | **0** | **0** | True zero at the pin. |
| `revocation_time` | all source | **0** | **0** | **0** | True zero at the pin. |

### 2.1 Reconciliation with the commission and independent audit

- The commission's `renewal = 1` is correct only for the unstated Python-only denominator. The
  all-source result is `4 / 4 / 4`.
- The independent audit reproduced both `renewal` denominators and the file counts for `expires_at`,
  `ttl_seconds`, and `expiry`.
- The audit's `legal_hold = 2 files / 4 matching lines / 5 occurrences` is wrong. The correct complete-
  walk result is **2 / 7 / 8**. Its file count is right; its indexed candidate set was not a complete
  line or occurrence denominator.
- The three zeroes are established facts, not `not_established` findings.

### 2.2 Semantic consequence

The conclusion is strengthened. Expiry and TTL are represented in many Python files, while exact
source literals for `grace_period`, `not_after`, and `revocation_time` are absent across all source
files. More importantly, repository inspection establishes no admitted capability chain that combines:

- an accountable renewal role and succession/escalation path;
- process-derived lead time;
- sufficient renewal evidence from a competent source;
- affirmative grace authority;
- a protected-use failure consequence;
- a reproducible affected-case query; and
- a public effect and durable fan-out requirement.

The only Python `renewal` occurrence describes renewal of a worker processing lease
(`policy-engine/src/polisyos/runtime/http/services/control_worker.py:84-85,128-174`). It is not an
authority-renewal primitive. The preemptive guard against reusing it as such remains binding.

## 3. Orientation results beyond the census

| Claim | Amended result | Evidence and boundary |
| --- | --- | --- |
| The five directly in-scope runbooks exist and are substantive. | **Established.** They contain commands, checks, recovery steps, and evidence destinations. | `replay-or-restore.md:1-128`; `retained-artifact-recovery.md:1-180`; `artifact-corruption-recovery.md:1-119`; `key-rotation.md:1-113`; `fabric-quarantine-dlq-and-data-plane-recovery.md:1-178`, all at the documentation pin. |
| `legal_hold` is a complete hold lifecycle. | **Refuted.** The two files implement narrow snapshot classification and GC protection only. | `fabric/security/retention.py:32-38,92-134`; `fabric/world/store/snapshots.py:654-689`; semantic tests at `tests/unit/fabric/test_world_time_travel.py:340-400`. |
| S0-K08, S0-K09, and S0-K10 bind the work. | **Established by finding ID.** Correction appends, the Custody Time Model applies, suspension is durable, and wake is only a candidate. | `stage0-custody-kernel-ratification.md:94-110`. |
| PV-K01 and PV-K02 bind recovery and replay. | **Established by finding ID.** Durable verifiability is separate, and present evidentiary failure never erases a historical act. | `int-r7-r8-public-verification-and-disclosure-ratification.md:91-123`. |
| GY-N12 owns currentness and epoch chronology. | **Established at the project semantic/plan contract layer; runtime capability absent/undelivered.** | `GY-engine-subordination.md:2053-2120`. OPS-R14 does not create a runtime type, schema, or second owner. |
| INT-R7 controls the public-proof preservation minimum. | **Established and consumed, not redefined.** Phase A uses a ceremonial pre-live corpus and real intended paths; Phase B cannot retroactively authorize the first record. | `int-r7-public-verification-lifecycle.md:990-1020`; `int-r7/lifecycle-migration-preservation.md:558-650`. |
| OPS-R14 and PAO-R36 have one declared seam. | **Established.** OPS-R14 owns durability/recovery/expiry/hold/drill mechanics; PAO-R36 owns correction meaning and fan-out semantics. | Backlog `:500-505,512-532`; the complete F11 closure is `RP-10 + RC-01 + RC-07 + F-04 + F-09 + DE-07`. |
| Institutional-scale continuity belongs to OPS-R12. | **Established scope boundary.** | Backlog `:130-151,500-505`. This package assumes at least one competent continuing institution or lawful successor. |

The earlier indexed count of all runbooks is not repeated as a complete directory fact because no
complete path denominator was supplied for that separate docs census. The five in-scope named files
are established individually.

## 4. Runbooks versus exercised recovery evidence

### OPS-R14-ACCEPTANCE-001 — documentation/tabletop versus exercised-recovery taxonomy

At the documentation pin, `platform-acceptance.md` records:

- line 15: `Runbook presence` — automated — `pass`;
- line 23: `Retention and restore posture` — automated — `pass`, because retention policy and recovery
  runbooks cover the posture; and
- line 30: `Incident / runbook tabletop` — manual — `pass`.

`platform-acceptance-manual.md:85-95` records review of the alert-to-runbook path and validation of
compose syntax. These rows do **not** say that a custody-grade restore ran, that RPO/RTO was measured,
or that `DurablyVerifiableAt(t_v)` passed. The original research phrasing was therefore too strong.

The repository finding is the taxonomy gap: the acceptance surface does not distinctly report

1. document/procedure present;
2. tabletop completed;
3. restore path exercised; and
4. custody-grade drill predicates passed.

**Closure signal:** the finding closes only when the acceptance evidence either:

- carries a separate exercised-recovery row that remains non-green until a real restore is run; or
- links a retained DE-01–DE-10 package containing frozen scope, actual failure injection, clean and
  independent restore, measured loss and elapsed recovery, clause-by-clause restored results,
  disconnected-path evidence, and append-only remediation/retest.

The five runbooks remain necessary, substantive inputs. They are not themselves exercise evidence.

## 5. Orientation conclusion

1. The complete census is now established with explicit path and file-type denominators.
2. `renewal` is **4 / 4 / 4** over all source and **1 / 1 / 1** over Python; the Python occurrence is
   worker-lease renewal only.
3. `legal_hold` is **2 / 7 / 8**, correcting both the original ledger and the independent audit's line
   and occurrence counts.
4. `expires_at`, `ttl_seconds`, and `expiry` reproduce the original file counts and now have established
   line and occurrence totals.
5. `grace_period`, `not_after`, and `revocation_time` are true zeroes at the pin.
6. The semantic absence of a complete governed renewal capability remains the operative finding.
7. The acceptance defect is a documentation/tabletop-versus-exercised-recovery taxonomy defect, not a
   claim that the baseline expressly accepted a paper runbook as custody-grade DR closeout.
8. None of these corrections supplies a runtime capability, institutional commitment, or drill. The
   capability and first-public-signature gate standings remain `NO_GO`.
