---
title: PAO-R4 independent audit — orientation error ledger
audit_id: PAO-R4
artifact_role: orientation-error-ledger
status: independent-audit
research_only: true
verified_commit: a27c3da9942b03881dbee1005a8a1e44e5ac44b4
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
authoritative_for:
  - independent Pass I census findings for PAO-R4
  - audit-only reconciliation of files, matching lines, and occurrences
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
  - modification of the audited branch
---

# PAO-R4 orientation error ledger

## 1. Method and denominators

The audited head is `a27c3da9942b03881dbee1005a8a1e44e5ac44b4`. Repository-orientation
claims are re-derived from the pinned baseline
`1a7a2d05ebba22fae80e9934329e4b880806588e`.

The audit keeps four denominators distinct:

1. **files** — distinct repository paths below the named root containing at least one match;
2. **matching lines** — physical source lines containing at least one match;
3. **occurrences** — non-overlapping matches, so one line may contribute more than one occurrence;
4. **file-type universe** — all decodable files below `policy-engine/src`, or a narrower declared
   subset such as Python files below `policy-engine/src/polisyos`.

`P35` requires a complete-set walk and an explicit denominator. `P36` requires reliance on the
finding, not adjacent prose. Both are in
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:74-80@1a7a2d05ebba22fae80e9934329e4b880806588e`.

The connected repository search returns the complete distinct-file set for the bounded queries used
below. It does not expose a recursive raw-line stream suitable for independently totaling every
positive `may_not_use_for` line and occurrence. Those two values remain `not_established`; the audit
does not relabel the file count. A complete checkout running the command in §5 would settle them.

## 2. Independent census

### 2.1 Summary

| Query | File universe | Files | Matching lines | Occurrences | Audit verdict |
|---|---|---:|---:|---:|---|
| exact `may_not_use_for` | Python files below `policy-engine/src/polisyos` | **106** | `not_established` | `not_established` | file count agrees; audited ledger did not complete the commissioned line/occurrence pass |
| exact `may_not_use_for` | all files below `policy-engine/src` outside `polisyos` | **0** | **0** | **0** | agrees that the 106 hits exhaust the all-source file set |
| exact `aggregate_only` | all files below `policy-engine/src` | **7** | **10** | **10** | agrees |
| case-insensitive prefix `anonymi` | all files below `policy-engine/src` | **7** | **16** | **22** | **disagrees**: audited ledger reports six because it silently drops a CSV fixture |
| case-insensitive prefix `anonymi` | Python files below `policy-engine/src` | **6** | **15** | **21** | agrees only under this narrower, previously unstated denominator |
| exact `individual_decision` | all files below `policy-engine/src` | **0** | **0** | **0** | agrees |
| exact `export_gate` | all files below `policy-engine/src` | **0** | **0** | **0** | agrees |
| exact `prohibited_use` | all files below `policy-engine/src` | **0** | **0** | **0** | agrees |

### 2.2 `may_not_use_for` partition

The exact-token hit set was partitioned by path predicate:

| Partition | Predicate | Files |
|---|---|---:|
| runtime | `policy-engine/src/polisyos/runtime/**.py` | **67** |
| scientist | `policy-engine/src/polisyos/scientist/**.py` | **12** |
| remainder | all other `policy-engine/src/polisyos/**.py` | **27** |
| **union** | three mutually exclusive predicates | **106** |

The partition is genuinely disjoint by construction: the runtime and scientist prefixes are
distinct; remainder is the set difference; and `67 + 12 + 27 = 106`. No
`may_not_use_for` hit was returned outside `policy-engine/src/polisyos`, and the complete result set
contains Python paths. The file-count claim therefore holds.

The audited orientation ledger is still incomplete against the commission because it writes
`not_established` for positive-token matching lines and occurrences
(`policy-engine/docs/research/policy-operations/pao-r4/orientation-ledger.md:72-96@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`) even though it presents a script intended to
produce those values later (`:151-197`). A specification is not an executed census.

### 2.3 `aggregate_only` reconciliation

The seven complete paths are the same seven named by the audited ledger
(`orientation-ledger.md:122-136@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`). Independent per-file
counts are:

| Path | Matching lines | Occurrences |
|---|---:|---:|
| `polisyos/fabric/evidence/decision_data.py` | 1 | 1 |
| `polisyos/runtime/quality/capability_index.py` | 1 | 1 |
| `polisyos/runtime/quality/semantic_fixtures.py` | 2 | 2 |
| `polisyos/fabric/connectors/contracts/source_contract.py` | 1 | 1 |
| `polisyos/runtime/quality/capability_index_compiler.py` | 2 | 2 |
| `polisyos/runtime/quality/design_axes/substrate_acquisition.py` | 1 | 1 |
| `polisyos/runtime/quality/proving_ground/substrate_grounding_search.py` | 2 | 2 |
| **total** | **10** | **10** |

The audited interpretation is right: these are redaction, rights-envelope, and visibility labels,
not a composition-safe policy-to-person firewall.

### 2.4 `anonymi*` reconciliation and denominator error

The audited ledger lists six Python paths at
`orientation-ledger.md:138-150@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`. The all-file source
walk also finds:

`policy-engine/src/polisyos/data_forge/domains/catalog/fixtures/relevant_topics_domain_files/relevant_topics_block_context_sociocultural.csv`

The CSV contains the prefix in the word `anonymity`. The commission's table said “Files in
`policy-engine/src`”; it did not say “Python files.” Therefore the correct all-file result is seven,
not six.

| Path family | Files | Matching lines | Prefix occurrences |
|---|---:|---:|---:|
| six Python paths named by the research | 6 | 15 | 21 |
| CSV fixture omitted by the research | 1 | 1 | 1 |
| **all-source total** | **7** | **16** | **22** |

This is not a semantic objection to the firewall. It is a `P35` denominator error and must be
corrected before the orientation ledger can be treated as completely reproduced.

### 2.5 Exact zeroes

The three exact-token queries returned no file anywhere below `policy-engine/src`. A zero-file set
necessarily has zero matching lines and zero occurrences. The audited conclusion that the source
cannot name `individual_decision`, `export_gate`, or `prohibited_use` is independently confirmed.
The zero for `prohibited_use` does not imply absence of prohibition semantics; the live vocabulary is
`may_not_use_for`.

## 3. File sizes and named anchors

The remaining orientation figures agree:

| Claim | Result | Verdict |
|---|---:|---|
| `public_export.py` physical lines | 2,103 | agree |
| `projection_semantics.py` physical lines | 3,763 | agree |
| PV ratification physical lines | 439 | agree |
| Stage-0 ratification physical lines | 264 | agree |
| INT-wave ratification physical lines | 379 | agree |
| canonical audiences | 4: PUBLIC, REVIEWER, EXPERT, MACHINE | agree |

The live carrier/enforcement conclusion also holds in bounded form. Authority envelopes declare
`may_not_use_for`; producer paths propagate it; and at least one consumer guard rejects a denied or
non-authoritative purpose. This proves a reusable primitive, not the commissioned firewall.

## 4. Pass-I findings

### `PAO-R4-I-001` — material — all-file `anonymi*` denominator is wrong

**Evidence:** `orientation-ledger.md:72-96,138-150@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`;
pinned CSV path above.

**Finding:** the ledger says its universe is every file below `policy-engine/src`, then reports six
and lists only Python files. The complete all-file set is seven. The six-file result is valid only for
a Python-only denominator that was not the commission's denominator.

### `PAO-R4-I-002` — material — positive-token line and occurrence pass was not executed

**Evidence:** `orientation-ledger.md:30-42,72-96,151-197@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`.

**Finding:** the research correctly refuses to invent line and occurrence totals, but the commission
required re-derivation of every entry with all three units. Supplying a future script is not
completion. The 106-file proposition is established; its line and occurrence totals are not.

### `PAO-R4-I-003` — commendation — the central repository shape is independently reproduced

**Evidence:** complete disjoint path searches and exact-zero searches described above.

**Finding:** 67 runtime + 12 scientist + 27 remainder is a real disjoint partition of 106 Python
files; `aggregate_only` is seven files; and all three missing-vocabulary zeroes hold. The important
orientation conclusion survives: the denial carrier is pervasive, while individual-decision
semantics are absent.

## 5. Complete-checkout command that settles the remaining values

```bash
PIN=1a7a2d05ebba22fae80e9934329e4b880806588e
python3 - "$PIN" <<'PY'
import subprocess, sys
pin = sys.argv[1]
root = "policy-engine/src"
paths = subprocess.check_output(
    ["git", "ls-tree", "-r", "--name-only", pin, "--", root], text=True
).splitlines()

def read(path):
    return subprocess.check_output(["git", "show", f"{pin}:{path}"])

def census(needle, *, fold=False, suffix=None):
    files = lines = occ = 0
    for path in paths:
        if suffix and not path.endswith(suffix):
            continue
        try:
            text = read(path).decode("utf-8")
        except UnicodeDecodeError:
            continue
        scan = text.casefold() if fold else text
        n = needle.casefold() if fold else needle
        hits = [line for line in scan.splitlines() if n in line]
        if hits:
            files += 1
            lines += len(hits)
            occ += scan.count(n)
    return files, lines, occ

for token, fold in [
    ("may_not_use_for", False), ("aggregate_only", False), ("anonymi", True),
    ("individual_decision", False), ("export_gate", False), ("prohibited_use", False),
]:
    print(token, census(token, fold=fold))
PY
```

Until that command or an equivalent complete raw-tree walk is executed, the two positive
`may_not_use_for` totals remain `not_established`; no broader conclusion depends on guessing them.
