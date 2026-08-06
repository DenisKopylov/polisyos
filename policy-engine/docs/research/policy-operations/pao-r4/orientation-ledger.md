---
title: PAO-R4 — Orientation ledger
research_id: PAO-R4
artifact_role: orientation-ledger
status: research
research_only: true
repository: DenisKopylov/polisyos
baseline_ref: main
baseline_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
result_standing: GO_WITH_REVISIONS
authoritative_for:
  - research orientation at the pinned repository state
  - complete-set source vocabulary census used by PAO-R4
  - research-only owner and boundary identification
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
---

# PAO-R4 orientation ledger

## 1. Count vocabulary and pin

Every repository statement in this ledger is relative to commit
`1a7a2d05ebba22fae80e9934329e4b880806588e`.

The census units are deliberately distinct:

- **source-line count** — physical newline-delimited lines in one complete file;
- **token-containing-file count** — distinct source files containing at least one matching token;
- **matched-line count** — physical lines containing at least one match;
- **literal-occurrence count** — non-overlapping token occurrences, including multiple matches on one line.

The commission's six vocabulary figures are **token-containing-file counts**. They are not matched-line
or literal-occurrence counts. PAO-R4 does not silently relabel them. Where the research run did not
retain a matched-line or occurrence total, those columns are stated as `not_established`; no number is
inferred from the file count.

This follows failure pattern **`P35`** (complete-set enumeration with the denominator) and **`P36`**
(cite the finding, not adjacent prose) in
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:74-80@1a7a2d05ebba22fae80e9934329e4b880806588e`.

## 2. Orientation figures

### 2.1 File sizes and canonical audiences

| Repository claim | Unit | Reproduced result | Pinned anchor | Disposition |
|---|---|---:|---|---|
| `public_export.py` size | source lines | 2,103 | `policy-engine/src/polisyos/runtime/quality/public_export.py:2098-2103@1a7a2d05ebba22fae80e9934329e4b880806588e` | agrees |
| `projection_semantics.py` size | source lines | 3,763 | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:3758-3763@1a7a2d05ebba22fae80e9934329e4b880806588e` | agrees |
| public-verification ratification size | source lines | 439 | `policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:434-439@1a7a2d05ebba22fae80e9934329e4b880806588e` | agrees |
| Stage-0 ratification size | source lines | 264 | `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:258-264@1a7a2d05ebba22fae80e9934329e4b880806588e` | agrees |
| INT-wave ratification size | source lines | 379 | `policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:373-379@1a7a2d05ebba22fae80e9934329e4b880806588e` | agrees |
| canonical projection audiences | enum members | 4 — `PUBLIC`, `REVIEWER`, `EXPERT`, `MACHINE` | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:648-655@1a7a2d05ebba22fae80e9934329e4b880806588e` | agrees |

The public exporter builds a redacted public projection, performs secret/PII scanning, evaluates
existing authority-surface decisions, and delegates to projection contract checks. Its official-use
limits deny scorecard, approval, runtime-closeout, credential-validation, and tenant-resolution uses,
but contain no individual-decision purpose. See
`policy-engine/src/polisyos/runtime/quality/public_export.py:39-101@1a7a2d05ebba22fae80e9934329e4b880806588e`.

The projection owner already emits `projection_only`, an empty `authoritative_for`, and a
`may_not_be_used_for` collection; `assert_policy_design_projection_not_authority` fails when the
projection mints authority or omits required denied uses. See
`policy-engine/src/polisyos/runtime/quality/projection_semantics.py:46-94@1a7a2d05ebba22fae80e9934329e4b880806588e` and
`:479-523@1a7a2d05ebba22fae80e9934329e4b880806588e`.

### 2.2 Complete source vocabulary census

Search universe: every file under `policy-engine/src` at the pin. For `may_not_use_for`, the universe
was narrowed to Python files under `policy-engine/src/polisyos`, matching the commission's stated
partition. Result unit: distinct token-containing files.

| Token/query | Token-containing files | Matched lines | Literal occurrences | Disposition |
|---|---:|---:|---:|---|
| exact `may_not_use_for` in `policy-engine/src/polisyos/**/*.py` | **106** | `not_established` | `not_established` | agrees; file count only |
| exact `aggregate_only` in `policy-engine/src` | **7** | `not_established` | `not_established` | agrees; file count only |
| case-insensitive prefix `anonymi` in `policy-engine/src` | **6** | `not_established` | `not_established` | agrees; prefix-containing file count only |
| exact `individual_decision` in `policy-engine/src` | **0** | **0** | **0** | agrees |
| exact `export_gate` in `policy-engine/src` | **0** | **0** | **0** | agrees |
| exact `prohibited_use` in `policy-engine/src` | **0** | **0** | **0** | agrees |

For zero-file results, matched lines and literal occurrences are also zero by implication. For
non-zero results, no line or occurrence total is inferred from a file count.

### 2.3 Disjoint `may_not_use_for` partition

The complete 106-file hit set was partitioned by path:

| Partition | Path predicate | Token-containing files |
|---|---|---:|
| runtime | below `policy-engine/src/polisyos/runtime/` | 67 |
| scientist | below `policy-engine/src/polisyos/scientist/` | 12 |
| remainder | below `policy-engine/src/polisyos/`, excluding both roots | 27 |
| **union** | three disjoint predicates | **106** |

The partition is genuinely disjoint: `runtime ∩ scientist = ∅`; the remainder is defined by set
difference; `67 + 12 + 27 = 106`; and the union equals the complete token-containing hit set. The
denominator is **106 token-containing Python files**, not all Python files in the source tree.

The live mechanism includes a typed authority envelope and consumer-side rejection. For example,
`UniversalAuthorityProfile` and `UniversalPolicyGrammarAuthorityEnvelope` carry
`may_not_use_for`, and `assert_authority_slot_eligible` rejects a purpose that is denied or absent
from `authoritative_for`:

- `policy-engine/src/polisyos/core/contracts/runtime.py:278-329@1a7a2d05ebba22fae80e9934329e4b880806588e`;
- `policy-engine/src/polisyos/policy_grammar/_impl/authority.py:17-55@1a7a2d05ebba22fae80e9934329e4b880806588e`;
- `policy-engine/src/polisyos/policy_grammar/_impl/consumer.py:53-67@1a7a2d05ebba22fae80e9934329e4b880806588e`.

The negative conclusion is therefore precise: the repository does not lack a denied-use mechanism;
it lacks a vocabulary and boundary chain for **individual use**.

### 2.4 `aggregate_only` complete hit set

The seven token-containing source files were:

1. `policy-engine/src/polisyos/fabric/evidence/decision_data.py`;
2. `policy-engine/src/polisyos/runtime/quality/capability_index.py`;
3. `policy-engine/src/polisyos/runtime/quality/semantic_fixtures.py`;
4. `policy-engine/src/polisyos/fabric/connectors/contracts/source_contract.py`;
5. `policy-engine/src/polisyos/runtime/quality/capability_index_compiler.py`;
6. `policy-engine/src/polisyos/runtime/quality/design_axes/substrate_acquisition.py`;
7. `policy-engine/src/polisyos/runtime/quality/proving_ground/substrate_grounding_search.py`.

The token is used for field redaction, rights envelopes, or hidden-fixture visibility. It does not
establish a cross-export composition theorem or an individual-use prohibition. `aggregate_only` is
therefore useful form metadata, not the firewall.

### 2.5 `anonymi*` complete hit set

The six prefix-containing source files were:

1. `policy-engine/src/polisyos/core/security/authz.py`;
2. `policy-engine/src/polisyos/scientist/methods/search/transfer_context.py`;
3. `policy-engine/src/polisyos/fabric/catalog/contract.py`;
4. `policy-engine/src/polisyos/runtime/http/authz_middleware.py`;
5. `policy-engine/src/polisyos/scientist/governance/passes/pii_check_pass.py`;
6. `policy-engine/src/polisyos/data_forge/_impl/compliance.py`.

These uses include a data-plane `requires_anonymization` flag, a stable tenant hash helper, a catalog
comment requiring `k>=5`, middleware propagation, redaction advice, and accepted redaction-status
vocabulary. They do not jointly define subject-resolution resistance under auxiliary information or
multi-export composition. The firewall must therefore treat “anonymized” as a proposition requiring
evidence, not as a permission word.

## 3. Reproduction specification

The complete-set script used by the research is reproduced below so the hostile audit can distinguish
files, matched lines, and literal occurrences. It is an executable specification, not an additional
repository artifact.

```bash
PIN=1a7a2d05ebba22fae80e9934329e4b880806588e
ROOT=policy-engine/src

python3 - "$PIN" "$ROOT" <<'PY'
from pathlib import Path
import subprocess
import sys

pin, root = sys.argv[1:]

def paths_at_pin() -> list[str]:
    out = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", pin, "--", root], text=True
    )
    return [p for p in out.splitlines() if p]

def read(path: str) -> str:
    return subprocess.check_output(["git", "show", f"{pin}:{path}"], text=True)

paths = paths_at_pin()
queries = {
    "aggregate_only": lambda text: "aggregate_only" in text,
    "anonymi*": lambda text: "anonymi" in text.casefold(),
    "individual_decision": lambda text: "individual_decision" in text,
    "export_gate": lambda text: "export_gate" in text,
    "prohibited_use": lambda text: "prohibited_use" in text,
}
for name, predicate in queries.items():
    hit_paths, matched_lines, occurrences = [], 0, 0
    needle = "anonymi" if name == "anonymi*" else name
    for path in paths:
        try:
            text = read(path)
        except UnicodeDecodeError:
            continue
        scan = text.casefold() if name == "anonymi*" else text
        if predicate(text):
            hit_paths.append(path)
            matched_lines += sum(needle in line for line in scan.splitlines())
            occurrences += scan.count(needle)
    print(name, "files", len(hit_paths), "lines", matched_lines,
          "occurrences", occurrences)

py = [p for p in paths if p.startswith("policy-engine/src/polisyos/") and p.endswith(".py")]
hits = {p for p in py if "may_not_use_for" in read(p)}
runtime = {p for p in hits if p.startswith("policy-engine/src/polisyos/runtime/")}
scientist = {p for p in hits if p.startswith("policy-engine/src/polisyos/scientist/")}
remainder = hits - runtime - scientist
assert not (runtime & scientist or runtime & remainder or scientist & remainder)
assert runtime | scientist | remainder == hits
print("may_not_use_for", len(hits), len(runtime), len(scientist), len(remainder))
PY
```

## 4. Binding architecture orientation

### 4.1 Identity and anti-role

The identity ruling assigns the individual-decision firewall to PolicyOS while keeping the
individual determination external. It also says that PolicyOS owns the typed evidence contract and
fail-closed absence behavior for integrated functions, not the external function itself:
`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:101-139@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding **Individual-decision firewall**.

### 4.2 Authority-band lens

The Stage-0 lens asks whether a restriction binds only the authority band or leaks into candidate
work. PAO-R4 follows it: population analysis remains allowed; protected individual use is blocked.
See `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:46-88@1a7a2d05ebba22fae80e9934329e4b880806588e` and the binding application note at `:164-176`, findings
**`S0-K05`**, **`S0-K07`**, and **`S0-K11`**.

### 4.3 Projection monotonicity

**`PV-K04`** establishes use-relative conservative parity and says denied uses do not shrink under
projection. PAO-R4 consumes that invariant and does not re-ratify it:
`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:138-146@1a7a2d05ebba22fae80e9934329e4b880806588e`.

### 4.4 Population-claim basis

**`INT-K02`** makes a `delta` inseparable from its declared obligation set, assumptions, and visible
relative-basis rider. PAO-R4 generalizes the same no-basis-stripping rule to every bounded population
claim that crosses toward case systems:
`policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:117-126@1a7a2d05ebba22fae80e9934329e4b880806588e`.

### 4.5 Public consumer

Atlas **DS12** is the named public-boundary consumer and explicitly reuses the 2,103-line public
export producer rather than inventing a duplicate. It is a publication surface, not a case-system
consumer. See
`policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:1420-1535@1a7a2d05ebba22fae80e9934329e4b880806588e`.

## 5. Orientation conclusions

1. **The mechanism exists:** `may_not_use_for` is live in 106 source Python files and has bounded
   consumer enforcement.
2. **The firewall concept does not:** the three exact vocabulary probes return zero source files.
3. **Form metadata is insufficient:** the seven `aggregate_only` and six `anonymi*` files do not
   establish cross-release non-resolution or downstream individual-use detection.
4. **The owner is clear:** extend `public_export.py`, `projection_semantics.py`, and the existing
   authority-envelope/consumer-guard pattern; do not create a parallel prohibition system.
5. **Current capability standing is absent/unallocated:** no accepted individual-decision contract,
   consumer, export gate, or returning-evidence chain exists at the pin.
6. **The research remains isolated:** correction mechanics belong to `PAO-R36`, durability to
   `OPS-R14`, and benchmark-oracle design to `S0-GAP-02`.
