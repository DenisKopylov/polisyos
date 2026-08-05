---
title: "INT-R8 orientation ledger — compression loss and disclosure composition"
research_id: INT-R8
artifact_role: orientation-ledger
status: accepted_narrow_scope
amendment_conformance: pending_independent_verification
research_only: true
repository: DenisKopylov/polisyos
baseline_ref: main
baseline_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
audited_head: 90b372964d29a9e97605a6ef733ef03ffe7938d2
prepared_at: 2026-08-04
amended_after_audit: research/int-r8-independent-audit@f45f338f9d9b0de94edc16efbc334789e70e34e2
may_not_use_for:
  - production_implementation_authorization
  - final_wire_schema_package_database_serialization_or_api_contract
  - canonical_owner_appointment
  - authority_grant
  - capability_claim
  - benchmark_passage
  - legal_compliance_or_institutional_competence_conclusion
  - permission_to_publish_a_governed_result
  - automatic_amendment_of_any_plan_or_system_design_decision
  - signature_algorithm_or_key_policy_selection
  - numeric_disclosure_bound
---

# INT-R8 orientation ledger

## 0. Controlling correction notice

This ledger supersedes the audited orientation ledger where the two conflict. The audited text is
preserved at commit `90b372964d29a9e97605a6ef733ef03ffe7938d2`. The correction executes audit
findings `INT-R8-I-002` and `INT-R8-I-004` and preserves `INT-R8-I-001`, `I-003`, and `I-005`.

Ordinary local Git access was attempted during the amendment and failed because `github.com`
could not be resolved. The published recipe's **operations** were re-run against the pinned
object through the connected exact-ref interface. The literal shell block was not executed in a
local checkout. This is an environment variation, not a claim that the shell ran.

## 1. Count vocabulary

Every numeric census below identifies its unit:

- **line count** — physical newline-delimited source lines;
- **matched-line count** — lines containing at least one exact case-sensitive token;
- **literal-occurrence count** — non-overlapping exact case-sensitive substring occurrences;
- **token-containing-file count** — distinct files containing at least one exact token;
- **invocation-file count** — distinct Python files containing the exact call/definition token
  `build_public_export_bundle(`; and
- **commit/file/addition count** — values returned by exact Git comparison.

Matched lines and literal occurrences are not interchangeable. One line can contain a token more
than once.

## 2. Delivery geometry

Exact comparison of baseline
`02c5b8d23c757c92b9231e6e1e802d5701588908` to audited head
`90b372964d29a9e97605a6ef733ef03ffe7938d2` establishes:

| Quantity | Unit | Value |
|---|---|---:|
| commits ahead | commits | 6 |
| commits behind | commits | 0 |
| added Markdown files | files | 6 |
| modified files | files | 0 |
| deleted files | files | 0 |
| added lines | diff additions | 2,207 |

Audited file line counts are 526, 486, 436, 359, 203, and 197; their arithmetic sum is 2,207.

## 3. Corrected complete-file token census

Complete-file denominator: all 2,103/2,103 lines of
`policy-engine/src/polisyos/runtime/quality/public_export.py` at the pinned baseline.

| Exact token | Matched lines | Literal occurrences | Interpretation |
|---|---:|---:|---|
| `omitted_claim` | 8 | **9** | Omitted-claim discovery and manifestation handling exist. One source line contains the token twice. |
| `projection_faithfulness` | 13 | 13 | S9 faithfulness is integrated. |
| `redaction_reason` | 2 | 2 | Canonical scanner-reason production exists. |
| `omissions_manifested` | 2 | 2 | The fail-closed omission-manifest assertion exists and is called. |
| `lossy` | 0 | 0 | No safe-loss outcome exists in this owner. |
| `blocked_material` | 0 | 0 | No material-omission outcome exists in this owner. |
| `compression` | 0 | 0 | No compression semantic exists in this owner. |
| `retained_limitation` | 0 | 0 | No explicit retained-limitation accounting exists in this owner. |

The audited ledger incorrectly named 8 as the literal-occurrence count for `omitted_claim`.
Python `text.count("omitted_claim")` returns 9. The architectural conclusion is unchanged: omission
handling exists; typed compression loss does not.

## 4. File-size and canonical-audience census

| Claim | Unit | Re-derived result | Pinned evidence |
|---|---|---|---|
| `projection_semantics.py` size | source lines | 3,763 | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:3758-3763` |
| `public_export.py` size | source lines | 2,103 | `policy-engine/src/polisyos/runtime/quality/public_export.py:2098-2103` |
| `publicationPacket.ts` size | source lines | 1,214 | `policy-engine/apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts:1208-1214` |
| Stage-0 ratification size | source lines | 264 | `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:258-264` |
| INT-wave ratification size | source lines | 379 | `policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:373-379` |
| canonical audiences | enum members | 4: PUBLIC, REVIEWER, EXPERT, MACHINE | `projection_semantics.py:648-655` |
| new audience introduced by INT-R8 | audited-file census | 0 in 6/6 audited artifacts | Complete audited-artifact read |

The no-fifth-audience statement is a scope rule for this research, not a claim that a competent
future architecture act can never amend the canonical contract.

## 5. `may_not_use_for` complete-set census

Search universe: every Python file below `policy-engine/src/polisyos` at the pinned commit.
Result unit: **distinct token-containing Python files**, not lines or occurrences.

The complete hit set was partitioned into disjoint path roots:

| Partition | Path rule | Token-containing files |
|---|---|---:|
| runtime | below `policy-engine/src/polisyos/runtime/` | 67 |
| scientist | below `policy-engine/src/polisyos/scientist/` | 12 |
| remainder | below `policy-engine/src/polisyos/`, excluding both roots above | 27 |
| **union** | three disjoint partitions | **106** |

The path sets are disjoint by construction and 67 + 12 + 27 = 106. The denominator is the
complete token-containing hit set, not “all Python files equal 106.” The token may occur multiple
times in a file; no occurrence count is claimed.

This census includes the named examples:

- `policy-engine/src/polisyos/core/contracts/runtime.py`;
- `policy-engine/src/polisyos/core/contracts/rule_evolution.py`; and
- `policy-engine/src/polisyos/evidence/portfolio/conflict_records.py`.

Denied use is therefore live source semantics, not a documentation convention.

## 6. Corrected `build_public_export_bundle` censuses

### 6.1 Production-source symbol-containing set

Search universe: every Python file below `policy-engine/src`.
Unit: distinct files containing the exact symbol text `build_public_export_bundle`.

Exactly 2 files contain the symbol:

1. `policy-engine/src/polisyos/runtime/quality/public_export.py` — definition;
2. `policy-engine/src/polisyos/runtime/quality/__init__.py` — re-export.

The second file is not a caller. No file below
`policy-engine/src/polisyos/runtime/http/` contains a call binding this producer to an HTTP route.

### 6.2 Whole-tree invocation-file set

Search universe: every Python file in the complete repository tree.
Unit: distinct files containing the exact invocation/definition token
`build_public_export_bundle(`.

The complete set contains **5 files**:

1. `policy-engine/src/polisyos/runtime/quality/public_export.py` — definition;
2. `policy-engine/tools/ops_runners/runtime/canary_evidence.py` — tooling caller;
3. `policy-engine/tools/quality/validation/check_layer3_workflow_failure_authority.py` — validation-tool caller;
4. `policy-engine/tests/unit/runtime/quality/test_multi_tenant_shared_cas.py` — test caller;
5. `policy-engine/tests/unit/runtime/quality/test_public_export.py` — test caller.

Therefore there are **4 caller files outside the definition**: two tools and two tests.
`runtime/quality/__init__.py` is in the two-file symbol set but not in the five-file invocation set.

The no-HTTP conclusion survives. The audited orientation's phrase “two callers” does not.

## 7. Named owner/source absence census

Search universe: all files below `policy-engine/src` at the pinned commit. Unit: distinct source
files containing each exact case-sensitive token.

| Token | Source files |
|---|---:|
| `disclosure_budget` | 0 |
| `composition_budget` | 0 |
| `privacy_budget` | 0 |
| `compression_loss` | 0 |
| `CompressionLoss` | 0 |

This establishes absence of these named source owners/contracts. It does not prove that no
differently named component could be adapted after a competent architecture decision.

A whole-repository search for `CompressionLoss` resolves planning/research prose, including:

- `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md`;
- `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`;
- `policy-engine/docs/research/deep-research-value-distillation.md`; and
- `policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md`.

Planning prose is not source capability.

## 8. Re-derived orientation register

| OR ID | Amended disposition |
|---|---|
| OR-001 | Confirmed: `projection_semantics.py` is 3,763 lines. |
| OR-002 | Confirmed: named omission, gap, contest, recourse, deficit, participation, invariant, redaction, and audit helpers exist. |
| OR-003 | Confirmed: four canonical audiences; no fifth is introduced. |
| OR-004 | Confirmed: S9-S14 checks and authority-laundering protections exist. |
| OR-005 | Confirmed: S14 hidden/gold-payload guard exists. |
| OR-006 | Confirmed: `public_export.py` is 2,103 lines. |
| OR-007 | Confirmed with scope: omitted claim IDs and canonical scanner reasons exist; general materiality does not. |
| OR-008 | Confirmed: candidate-firewall and replay-drift gates exist. |
| OR-009 | Corrected: `omitted_claim` is 8 matched lines / 9 literal occurrences; the other seven rows reproduce exactly. |
| OR-010 | Corrected: 2 production-source symbol files; 5 whole-tree invocation files including definition; 4 caller files outside definition; no HTTP binding. |
| OR-011 | Confirmed as exact named-token source absence. |
| OR-012 | Confirmed: `CompressionLoss` appears in plans/research but in zero source files. |
| OR-013 | Confirmed: 106 distinct token-containing Python files, partitioned 67/12/27. |
| OR-014 | Confirmed: 1,214-line frontend packet is consumed by the public viewer. |
| OR-015 | Confirmed: truncation, four-metric cap, and narrow copied semantics have no material-loss receipt. |
| OR-016 | Confirmed: serialized packet is embedded in the deep-link path. |
| OR-017 | Confirmed: Atlas DS12/DS13/DS14 consume INT-R8 as planning/research input. |
| OR-018 | Confirmed: Atlas reconnaissance records no authoritative public-record producer/verifier. |
| OR-019 | Confirmed as plan text, not capability. Amended maturity: GY-PA3 is absent/unallocated, not `producer_missing`. |
| OR-020 | Confirmed by finding ID: `INT-K02`, `K04`, `K05`, `K06`, `K07`, `K08`, and `S0-K07` constrain this result. |

## 9. Existing reuse anchors, stated without a universal limitations field

The base projection emits or derives these concrete carriers:

- `closeout_truth` and closeout limitation/blocker codes;
- `projection_gaps`;
- `omission_manifest`;
- `contested_records`;
- `recourse_pointer`;
- `deficit_register`;
- `participation_requirements`;
- `invariant_summary`;
- `redaction_summary`;
- `audit_refs` and source-authority references;
- `may_not_be_used_for`; and
- `authority_role = projection_only` with empty `authoritative_for`.

Surface-specific S10-S14 enrichment may also carry fields named `limitations` or a named public
limitation. The base projection does not provide one universal top-level limitations collection.
A future receipt may normalize the semantic effect of these carriers; it may not pretend the
storage shape is already unified.

Public export consumes projection semantics, runs existing checks, manifests omitted claim IDs,
and emits scanner-derived reasons. This is the substrate the receipt extends.

## 10. Frontend orientation retained

The packet remains a rendering model, not authority. The pinned source:

- truncates public references to 96 characters and public text to 320;
- limits deterministic metric explanations to the first four metrics;
- copies a narrow projection subset rather than the canonical omission/gap/contest/recourse/
  deficit/audit structures;
- serializes and base64url-encodes the packet into the deep-link path; and
- uses a five-needle private-context heuristic.

These facts establish a detectable receipt gap, not that every current packet is materially
false.

## 11. Reproduction recipe

The recipe prints both matched-line and literal-occurrence columns and distinguishes symbol files
from invocation files. An auditor with an exact checkout can run:

```bash
git checkout --detach 02c5b8d23c757c92b9231e6e1e802d5701588908
wc -l \
  policy-engine/src/polisyos/runtime/quality/projection_semantics.py \
  policy-engine/src/polisyos/runtime/quality/public_export.py \
  policy-engine/apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts \
  policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md \
  policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md

python - <<'PY'
from pathlib import Path

repo = Path('.')
src = repo / 'policy-engine/src'
public_export = src / 'polisyos/runtime/quality/public_export.py'
lines = public_export.read_text(encoding='utf-8').splitlines()
text = public_export.read_text(encoding='utf-8')

tokens = (
    'omitted_claim',
    'projection_faithfulness',
    'redaction_reason',
    'omissions_manifested',
    'lossy',
    'blocked_material',
    'compression',
    'retained_limitation',
)
for token in tokens:
    matched_lines = sum(token in line for line in lines)
    occurrences = text.count(token)
    print(token, 'matched_lines', matched_lines, 'occurrences', occurrences)

python_files = sorted((src / 'polisyos').rglob('*.py'))
hits = {
    path for path in python_files
    if 'may_not_use_for' in path.read_text(encoding='utf-8')
}
runtime = {path for path in hits if (src / 'polisyos/runtime') in path.parents}
scientist = {path for path in hits if (src / 'polisyos/scientist') in path.parents}
remainder = hits - runtime - scientist
assert not (runtime & scientist or runtime & remainder or scientist & remainder)
assert runtime | scientist | remainder == hits
print('may_not_use_for_token_files', len(hits))
print('runtime', len(runtime), 'scientist', len(scientist), 'remainder', len(remainder))

symbol_files = [
    path for path in sorted(src.rglob('*.py'))
    if 'build_public_export_bundle' in path.read_text(encoding='utf-8')
]
print('source_symbol_files', len(symbol_files))
for path in symbol_files:
    print(path)

invocation_files = [
    path for path in sorted(repo.rglob('*.py'))
    if 'build_public_export_bundle(' in path.read_text(encoding='utf-8')
]
print('whole_tree_invocation_files_including_definition', len(invocation_files))
for path in invocation_files:
    print(path)

for token in (
    'disclosure_budget',
    'composition_budget',
    'privacy_budget',
    'compression_loss',
    'CompressionLoss',
):
    token_files = [
        path for path in sorted(src.rglob('*'))
        if path.is_file()
        and token in path.read_text(encoding='utf-8', errors='ignore')
    ]
    print(token, 'source_files', len(token_files))
PY
```

The amendment re-ran these operations through exact-ref reads. They produced the amended values
above, including `omitted_claim: 8 matched lines / 9 literal occurrences` and the five-file
whole-tree invocation set. The local shell execution remains unavailable and is not claimed.

## 12. Orientation conclusion

The corrected delta is:

> PolicyOS has a real canonical projection substrate and a real public-export producer. It has
> no source producer, admitted wired gate, controlled transcript custody, or canonical numerical
> model for compression-loss composition. The present research is a contract-only semantic
> result. The exact bounded reconstruction predicate and scoped prefix discipline survive; the
> former census and caller wording do not.
