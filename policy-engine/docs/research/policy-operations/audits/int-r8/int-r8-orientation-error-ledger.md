---
title: "INT-R8 — Independent orientation error ledger"
audit_id: INT-R8-INDEPENDENT-AUDIT
verified_commit: 90b372964d29a9e97605a6ef733ef03ffe7938d2
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
authoritative_for:
  - independent Pass I verification of the INT-R8 orientation ledger
  - count reconciliation with explicit matched-line and literal-occurrence semantics
  - exact-ref repository orientation findings INT-R8-I-001 through INT-R8-I-005
may_not_use_for:
  - adoption amendment or ratification of INT-R8
  - production implementation authorization
  - final wire schema package database serialization or API contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - legal sufficiency compliance or institutional competence conclusion
  - permission to publish a governed record
  - automatic amendment of any plan or system-design decision
  - signature algorithm key policy or numeric disclosure-bound selection
research_only: true
---

# INT-R8 independent orientation error ledger

## 1. Method and execution limitation

The audit re-derived the orientation against the immutable objects named above. The output
branch was forked from the audited head; the audited branch was not modified.

Ordinary Git access was attempted and failed because the execution environment could not
resolve `github.com`. The exact-ref GitHub interface was therefore used for file reads, code
searches, compare results and ordinary Markdown commits. The shell block in audited
`int-r8/orientation-ledger.md` §7 could not be executed against a local checkout. Its operations
were nevertheless reproduced individually against the exact baseline:

- end-of-file reads for line counts;
- exact literal inspection for the `public_export.py` token census;
- path-scoped complete code searches for the three disjoint `may_not_use_for` partitions;
- exact source and whole-tree searches for `build_public_export_bundle`; and
- exact source searches for the five claimed absent budget/loss identifiers.

The distinction matters: this audit reports the result of the recipe's operations, but does not
claim that a local shell process ran when network policy made that impossible.

## 2. Branch and delivery geometry

Exact comparison of
`02c5b8d23c757c92b9231e6e1e802d5701588908...90b372964d29a9e97605a6ef733ef03ffe7938d2`
returns:

| Quantity | Re-derived value |
| --- | ---: |
| commits ahead | 6 |
| commits behind | 0 |
| added files | 6 |
| modified files | 0 |
| deleted files | 0 |
| added lines | 2,207 |

The six added-file line counts are 526, 486, 436, 359, 203 and 197; they sum to
2,207. This part of the supplied orientation is exact.

## 3. Count semantics

For every token below, two quantities were re-derived:

- **matched lines** — source lines containing at least one exact case-sensitive token;
- **literal occurrences** — non-overlapping exact case-sensitive substring occurrences, the
  quantity computed by Python `text.count(token)` in the audited recipe.

These quantities differ only for `omitted_claim`, because one source line contains the token
twice:

```python
omitted_claim_ids = set(_iter_omitted_claim_ids(artifacts))
```

### 3.1 `public_export.py` census

Complete-file denominator: 2,103/2,103 lines of
`policy-engine/src/polisyos/runtime/quality/public_export.py` at the pinned baseline.

| Token | Matched lines | Literal occurrences | Audited ledger reports | Verdict |
| --- | ---: | ---: | ---: | --- |
| `omitted_claim` | 8 | **9** | 8, explicitly named as literal occurrences | **False as named.** It is the matched-line count, not the occurrence count. |
| `projection_faithfulness` | 13 | 13 | 13 | Confirmed under both quantities. |
| `redaction_reason` | 2 | 2 | 2 | Confirmed under both quantities. |
| `omissions_manifested` | 2 | 2 | 2 | Confirmed under both quantities. |
| `lossy` | 0 | 0 | 0 | Confirmed. |
| `blocked_material` | 0 | 0 | 0 | Confirmed. |
| `compression` | 0 | 0 | 0 | Confirmed. |
| `retained_limitation` | 0 | 0 | 0 | Confirmed. |

The audited recipe uses `text.count(token)`. On the exact baseline it therefore prints
`omitted_claim 9`, not `omitted_claim 8`. The recipe fails to reproduce the ledger's own
reported occurrence census.

This does not refute the architectural gap. Eight matching lines or nine occurrences both
support the same narrow conclusion: omitted-claim handling exists while the four named
compression/loss terms do not. It does refute the claimed exact census and is a P35 defect.

## 4. Complete `may_not_use_for` census

The audited partition was reproduced with three path-scoped, case-sensitive code searches over
Python files at the pinned baseline:

1. `policy-engine/src/polisyos/runtime/**`: **67 files**;
2. `policy-engine/src/polisyos/scientist/**`: **12 files**;
3. `policy-engine/src/polisyos/**` excluding both roots: **27 files**.

The path sets are disjoint by construction. Their union contains **106 distinct Python files**.
No file was counted twice. The ledger's 67 + 12 + 27 = 106 file count is confirmed.

This is a **file count**, not a line count and not an occurrence count. The token can occur more
than once within a file; INT-R8 did not claim otherwise.

The statement `106/106 Python files returned by the complete exact-token census` is acceptable
only with that denominator: 106 is the number of token-containing Python files, not the total
number of Python files under `policy-engine/src/polisyos`.

## 5. File-size and audience checks

| Audited orientation claim | Re-derived result | Evidence |
| --- | --- | --- |
| `projection_semantics.py` has 3,763 lines | Confirmed | Final export list closes at line 3,763: `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:3758-3763`. |
| `public_export.py` has 2,103 lines | Confirmed | Final export list closes at line 2,103: `policy-engine/src/polisyos/runtime/quality/public_export.py:2098-2103`. |
| `publicationPacket.ts` has 1,214 lines | Confirmed | File closes at line 1,214: `policy-engine/apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts:1208-1214`. |
| Four canonical audiences | Confirmed exactly | Fixture default is PUBLIC, REVIEWER, EXPERT, MACHINE: `projection_semantics.py:648-655`. |
| No fifth audience introduced by INT-R8 | Confirmed over 6/6 audited files | No additional audience member is defined; the research repeatedly consumes the existing four. |

The phrase “no fifth audience is admissible in this research” is a scope prohibition, not a
claim that no future architecture decision can ever amend the canonical contract.

## 6. Projection/public-export substrate checks

Every reuse point claimed in OR-002, OR-004, OR-005, OR-007 and OR-008 exists:

- the base projection emits `projection_gaps`, `omission_manifest`, `contested_records`,
  `recourse_pointer`, `deficit_register`, participation requirements, invariant summary,
  redaction summary, audit/source references and denied uses;
- the projection is asserted `projection_only` and has empty `authoritative_for`;
- the multi-audience fixture uses the four canonical audiences;
- S9-S14 consumer verifiers and laundering checks exist;
- `_s14_contains_hidden_or_gold_payload` participates in the S14 issue path;
- public export invokes S9-S14 checks, omitted-claim manifestation, candidate firewall and
  replay-drift gates; and
- canonical scanner redaction reasons are emitted.

Primary anchors:

- `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:275-575`;
- `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:630-670`;
- `policy-engine/src/polisyos/runtime/quality/public_export.py:430-470`;
- `policy-engine/src/polisyos/runtime/quality/public_export.py:1685-1845`.

The reuse direction is therefore real. Whether the future receipt can use it without creating a
parallel reason/materiality registry is assessed separately in Pass V.

## 7. Budget/loss owner searches

One complete source query over `policy-engine/src`, restricted to Python, for:

- `disclosure_budget`;
- `composition_budget`;
- `privacy_budget`;
- `compression_loss`; and
- `CompressionLoss`

returned **0 source files for every token**. This establishes lexical absence of those named
owners/contracts. It does not prove that no differently named component could ever be adapted.

A whole-repository search for `CompressionLoss` returned four planning/research documents,
including:

- `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md`;
- `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`;
- `policy-engine/docs/research/deep-research-value-distillation.md`; and
- `policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md`.

The ledger's qualification “planning prose exists; source capability does not” is confirmed.

## 8. `build_public_export_bundle` census

### 8.1 Production source token set

Under `policy-engine/src`, exactly **2 files** contain the symbol token:

1. `policy-engine/src/polisyos/runtime/quality/public_export.py` — definition;
2. `policy-engine/src/polisyos/runtime/quality/__init__.py` — re-export.

Neither is an HTTP caller. Complete searches of
`policy-engine/src/polisyos/runtime/http/**` returned no binding.

### 8.2 Whole-tree Python call sites

A complete search for the invocation token `build_public_export_bundle(` in Python files
returned **5 files**:

1. `policy-engine/src/polisyos/runtime/quality/public_export.py` — the function definition;
2. `policy-engine/tools/ops_runners/runtime/canary_evidence.py` — operational caller;
3. `policy-engine/tools/quality/validation/check_layer3_workflow_failure_authority.py` — validation-tool caller;
4. `policy-engine/tests/unit/runtime/quality/test_multi_tenant_shared_cas.py` — test caller;
5. `policy-engine/tests/unit/runtime/quality/test_public_export.py` — test caller with many invocations.

Thus there are **4 caller files outside the definition**: two tooling callers and two test
callers. `runtime/quality/__init__.py` contains the symbol but is not a call site.

The audited ledger's core conclusion—no `runtime/http` binding—is correct. Its prose is
incomplete in calling out “an operations runner” but not the second validation tool, and its §6
phrase “two callers” is inaccurate: the two `src` files are a definition and a re-export, not
callers.

## 9. Re-derived OR-001 through OR-020

| OR ID | Independent disposition |
| --- | --- |
| OR-001 | Confirmed: 3,763 lines. |
| OR-002 | Confirmed: named helpers and projection-only boundary exist. |
| OR-003 | Confirmed: four canonical audiences; no fifth introduced. |
| OR-004 | Confirmed: S9-S14 per-projection checks and laundering checks exist. |
| OR-005 | Confirmed: hidden/gold payload guard exists in S14 path. |
| OR-006 | Confirmed: 2,103 lines. |
| OR-007 | Confirmed, with scope: omitted claim IDs and three canonical scanner reasons exist; they do not classify general semantic materiality. |
| OR-008 | Confirmed: candidate and replay-drift firewalls exist. |
| OR-009 | **Partly false:** seven rows confirmed; `omitted_claim` is 8 lines but 9 occurrences. |
| OR-010 | Confirmed core conclusion; caller description incomplete and §6 “two callers” wording false. |
| OR-011 | Confirmed as exact named-token source absence, not metaphysical owner absence. |
| OR-012 | Confirmed qualification: planning prose exists, source does not. |
| OR-013 | Confirmed: 106 distinct token-containing Python files, 67/12/27 disjoint. |
| OR-014 | Confirmed: 1,214-line packet consumed by public viewer/panel. |
| OR-015 | Confirmed: truncation, first-four metric cap and narrow projection subset have no receipt. |
| OR-016 | Confirmed: packet is encoded into the deep-link path and client-verified. |
| OR-017 | Confirmed: Atlas DS12/DS13/DS14 consume the research as planning input. |
| OR-018 | Confirmed: Atlas reconnaissance says no authoritative public-record producer/verifier exists. |
| OR-019 | Confirmed as plan text, not capability. |
| OR-020 | Confirmed: ratified records impose the cited no-bare-delta, no-hidden-negative and no-unjustified-number constraints. |

## 10. Pass I findings

### INT-R8-I-001 — commendation — delivery geometry, file lengths and audience count are exact

All branch, file, line and canonical-audience facts were independently reproduced.

### INT-R8-I-002 — material — the exact token census confuses matched lines with occurrences

**Evidence:** audited `int-r8/orientation-ledger.md:45-75,83-102,137-197` and pinned
`public_export.py:1730-1840`.

`omitted_claim` occurs nine times on eight lines. The ledger labels 8 as an occurrence count,
and its own `text.count` recipe returns 9. Correct the table, the primary report's repeated
census and the reproduction commentary. Retain both quantities explicitly.

### INT-R8-I-003 — commendation — the 106-file partition is genuinely complete and disjoint

The 67 runtime, 12 scientist and 27 remainder searches cover disjoint path sets and sum to 106.

### INT-R8-I-004 — minor — caller wording is incomplete and uses “caller” for non-callers

The no-HTTP conclusion survives. The orientation should enumerate both tooling callers and call
the two `src` results “token-containing files,” not “two callers.”

### INT-R8-I-005 — commendation — capability absence is narrowly and correctly qualified

The source contains no named budget/loss owner, while GY-PA3 and Atlas references remain plainly
planning/research material. The ledger does not mistake plan text for capability.

## 11. Pass I conclusion

Pass I is **substantively strong but not exact**. One numeric row and the reproduction claim
must be corrected. The error is local and direction-neutral: it does not change the finding
that omission machinery exists and compression-loss machinery does not. Because exact censuses
are used as evidence of method discipline, however, the correction is required before the
orientation can be called fully conformant.