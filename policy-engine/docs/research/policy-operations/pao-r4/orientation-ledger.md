---
title: PAO-R4 orientation ledger
research_id: PAO-R4
artifact_role: orientation-ledger
status: research
research_only: true
repository: DenisKopylov/polisyos
baseline_ref: main
baseline_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
result_standing: GO_WITH_REVISIONS
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

## 1. Count vocabulary

This ledger keeps five denominators separate:

- **source-line count** — physical newline-delimited lines in one named file;
- **token-containing-file count** — distinct files containing at least one match;
- **matched-line count** — source lines containing at least one match;
- **literal-occurrence count** — non-overlapping exact substring occurrences; and
- **stem-family file count** — distinct files containing any spelling in a declared token family.

A file count is not a line count and a line count is not an occurrence count. The commission's
source-tree table is a **file-count table**. Where the prior research retained no independent
matched-line or occurrence denominator, this ledger says `not_established` rather than converting a
file count into another unit.

## 2. Pin and binding findings

All repository claims in this package are pinned to
`1a7a2d05ebba22fae80e9934329e4b880806588e`.

| Subject | Pinned finding or source | Orientation effect |
|---|---|---|
| PolicyOS owns the firewall, not the individual act | `policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:123-139@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding **Individual-decision firewall** | The export/use contract is PolicyOS scope; case handling remains external. |
| Anti-roles | `policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:88-91@1a7a2d05ebba22fae80e9934329e4b880806588e` | No case-system workflow, adjudication, notice, payment, sanction, or review design belongs here. |
| No authority by transport/projection | `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:96-112@1a7a2d05ebba22fae80e9934329e4b880806588e`, findings `S0-K05`, `S0-K07`, `S0-K11` | Export and projection cannot create case authority; protected actions need action-specific protection. |
| Denied-use monotonicity | `policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:138-146@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `PV-K04` | Projection may reduce detail but denied uses do not shrink. |
| Basis inseparability | `policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:117-126@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `INT-K02` | A population quantity stripped of its declared basis is a different and false claim. |
| Complete-set discipline | `policy-engine/docs/reference/policy-design-case-failure-patterns.md:71-80@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `P35` | Every set-level fact names its denominator. |
| Warrant discipline | `policy-engine/docs/reference/policy-design-case-failure-patterns.md:71-80@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `P36` | Findings are cited by ID; surrounding prose is not promoted into authority. |

## 3. File-size and boundary-owner census

| Claim | Unit | Result | Pinned evidence |
|---|---|---:|---|
| `public_export.py` | source lines | 2,103 | `policy-engine/src/polisyos/runtime/quality/public_export.py:2098-2103@1a7a2d05ebba22fae80e9934329e4b880806588e` |
| `projection_semantics.py` | source lines | 3,763 | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:3758-3763@1a7a2d05ebba22fae80e9934329e4b880806588e` |
| public-verification ratification | source lines | 439 | `policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:434-439@1a7a2d05ebba22fae80e9934329e4b880806588e` |
| Stage-0 ratification | source lines | 264 | `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:258-264@1a7a2d05ebba22fae80e9934329e4b880806588e` |
| INT-wave ratification | source lines | 379 | `policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:373-379@1a7a2d05ebba22fae80e9934329e4b880806588e` |
| canonical audiences | enum members | 4 | `policy-engine/src/polisyos/core/contracts/policy_design_case_projection.py:12-20@1a7a2d05ebba22fae80e9934329e4b880806588e`: PUBLIC, REVIEWER, EXPERT, MACHINE |

`public_export.py` is a real public-bundle producer with a redacted-projection posture and official
use limits; `projection_semantics.py` emits `projection_only`, an empty `authoritative_for`, and a
carried denied-use list, and validates that projection does not fill authority slots
(`policy-engine/src/polisyos/runtime/quality/public_export.py:45-110@1a7a2d05ebba22fae80e9934329e4b880806588e`;
`policy-engine/src/polisyos/runtime/quality/projection_semantics.py:37-56,522-566@1a7a2d05ebba22fae80e9934329e4b880806588e`).
These are reuse anchors, not an individual-decision firewall capability.

## 4. Complete source-tree vocabulary census

Search universe for every row: all files below `policy-engine/src` at the pin. The first numeric
column reproduces the commissioned **distinct-file** denominator.

| Token or family | Token-containing files | Matched lines | Literal occurrences | Orientation verdict |
|---|---:|---:|---:|---|
| exact `may_not_use_for` | **106 Python files** | `not_established` as a separate denominator | `not_established` as a separate denominator | **Agreement.** Live source mechanism, not a documentation convention. |
| exact `aggregate_only` | **7 files** | `not_established` | `not_established` | **Agreement.** Existing access/export vocabulary, not a firewall rule. |
| stem family `anonymi*` | **6 files** | `not_established` for the stem family | not meaningful without enumerating exact spellings | **Agreement with qualification.** The family includes words such as `anonymization`, `anonymize`, and `anonymized`; it is not one literal token. |
| exact `individual_decision` | **0 files** | **0** | **0** | **Agreement.** The source vocabulary cannot name the commissioned use class. |
| exact `export_gate` | **0 files** | **0** | **0** | **Agreement.** No source owner carries that exact gate concept. |
| exact `prohibited_use` | **0 files** | **0** | **0** | **Agreement.** Existing wording is `may_not_use_for`, not a second prohibition system. |

### 4.1 Disjoint `may_not_use_for` partition

Search universe: every Python file below `policy-engine/src/polisyos`. Result unit: distinct Python
files containing exact `may_not_use_for`.

| Partition | Path rule | Files |
|---|---|---:|
| runtime | below `policy-engine/src/polisyos/runtime/` | 67 |
| scientist | below `policy-engine/src/polisyos/scientist/` | 12 |
| remainder | below `policy-engine/src/polisyos/`, excluding both roots | 27 |
| **union** | three disjoint path partitions | **106** |

The sets are disjoint by path construction and `67 + 12 + 27 = 106`. The denominator is the
complete hit set, not all Python files. This is the `P35`-compliant statement preserved from the
research.

### 4.2 Concrete mechanism anchors

The existing mechanism has all three essential local operations:

1. **declaration** — authority profiles/envelopes carry `may_not_use_for`;
2. **propagation** — compilers and projections copy or union the denied set; and
3. **consumer rejection** — a consumer rejects a purpose present in the denied set or absent from
   `authoritative_for`.

One compact example is the policy-grammar path:
`policy-engine/src/polisyos/core/contracts/runtime.py:250-290@1a7a2d05ebba22fae80e9934329e4b880806588e` declares the field;
`policy-engine/src/polisyos/policy_grammar/_impl/authority.py:15-34@1a7a2d05ebba22fae80e9934329e4b880806588e` unions LLM denials;
and `policy-engine/src/polisyos/policy_grammar/_impl/consumer.py:60-77@1a7a2d05ebba22fae80e9934329e4b880806588e`
rejects denied or non-authoritative purposes.

The missing concept is not “how to carry a denial.” It is the vocabulary and observability needed
to decide whether a policy artifact materially contributed to an individual case action.

## 5. Negative comparator: what the current state shows

At the pin, an operator can see projection-only posture, public-audit limits, and existing authority
use denials. The operator cannot express or test:

- `individual_eligibility_determination`;
- `individual_sanction_or_enforcement`;
- `individual_risk_scoring_or_profiling`;
- material contribution to an individual act;
- completeness of a returning-evidence denominator; or
- reconstruction of an individual determination across compliant queries.

Therefore the commission's falsifier—a statistical population rule used as an individual eligibility
rule—does not encounter a named individual-decision gate in the pinned source. Existing generic
projection/authority denials may block some authority slots, but they do not decide this use class or
produce the required cross-boundary evidence.

## 6. Orientation conclusions

1. Every commissioned file-count figure is reproduced; no supplied figure is refuted.
2. The `106` partition is genuinely disjoint and sums correctly.
3. File, line, and occurrence units remain separate. For positive-token rows where the prior research
   did not preserve a separate matched-line/occurrence census, the result is explicitly
   `not_established`; no file count is relabeled.
4. The live reusable primitive is `may_not_use_for`, including bounded consumer enforcement and
   projection propagation.
5. The firewall vocabulary and complete producer-consumer-returning-evidence chain are absent.
6. `PV-K04`, not a new rule, controls denial monotonicity under projection.
7. The research therefore instantiates the existing mechanism for a new use class and refuses
   unobservable export classes; it does not invent a second prohibition system or claim a capability.
