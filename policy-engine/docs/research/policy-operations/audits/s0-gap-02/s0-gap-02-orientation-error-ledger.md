---
title: S0-GAP-02 — Orientation error ledger
status: independent_audit
audit_task: S0-GAP-02
verified_commit: a7c34cc40b649a10b6878228a8a57acc498f279a
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
authoritative_for:
  - Pass-I orientation findings at the verified and pinned commits
  - bounded repository-count reconciliation and stated audit limitations
  - verification of the three named benchmark owners and OPS-R15 prior-art inventory
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner, evaluator, custodian, reviewer panel or vendor appointment
  - authority grant
  - capability claim
  - benchmark passage
  - permission to score OPS-R15
  - claim that OPS-R15 is unblocked
  - legal-sufficiency conclusion
  - automatic amendment of any plan, backlog or system-design decision
research_only: true
---

# S0-GAP-02 orientation error ledger

## 1. Scope and denominator discipline

This ledger audits the orientation in the nine content artifacts delivered at
`research/s0-gap-02-independent-benchmark-oracle@a7c34cc40b649a10b6878228a8a57acc498f279a`
against the complete tracked tree at
`main@1a7a2d05ebba22fae80e9934329e4b880806588e`.

The requested census has three different denominators and they are not interchangeable:

1. **matching files** — distinct tracked non-binary files under `policy-engine/src` containing the
   exact lowercase fixed string;
2. **matching lines** — source lines under the same complete tracked set that contain at least one
   exact lowercase fixed-string match;
3. **occurrences** — all non-overlapping exact lowercase fixed-string occurrences on those lines.

Path-name matches are excluded. Case-insensitive matches are excluded. Ranked code-search result
counts are excluded. Those distinctions are the direct application of `P35` and agree with the
research orientation ledger at `s0-gap-02/orientation-ledger.md:51-78`.

## 2. Reproduction command

The research supplied the following complete-checkout command. It is the correct reproducer:

```bash
PIN=1a7a2d05ebba22fae80e9934329e4b880806588e
for token in benchmark evaluator oracle metamorphic fixture_corpus sealed_expect; do
  files=$(git grep -I -l -F "$token" "$PIN" -- policy-engine/src | wc -l)
  lines=$(git grep -I -n -F "$token" "$PIN" -- policy-engine/src | wc -l)
  occurrences=$(git grep -I -h -F "$token" "$PIN" -- policy-engine/src \
    | awk -v t="$token" '{n+=gsub(t,t)} END{print n+0}')
  printf '%s files=%s lines=%s occurrences=%s\n' \
    "$token" "$files" "$lines" "$occurrences"
done
```

Ordinary `git clone`, `git archive`, and raw GitHub download remained unavailable in this audit
environment. The connected GitHub interface exposed exact-ref file reads, code search, comparisons,
and Git-data writes, but no recursive tree/content read. I used two independent checks rather than
silently treating ranked search as a complete walk:

- an unreferenced Git-data commit deleting `policy-engine/src` from the pinned tree, compared against
  the pin, established a complete tracked-file view until the GitHub compare API's documented file
  cap was reached; no ref was moved;
- exact-ref code search established bounded file sets for the small tokens and showed the large
  searches were capped/ranked, not complete line or occurrence walks.

The literal `git grep` command therefore **was not executed**. Matching-line and occurrence totals are
not independently established here. Under the task's own rule, that is a finding against this audit,
not permission to copy the inherited numbers.

## 3. Count reconciliation

| Token | Brief: files | Auditor: files | Auditor: matching lines | Auditor: occurrences | Exact audit disposition |
|---|---:|---:|---:|---:|---|
| `benchmark` | 183 | `not_established` | `not_established` | `not_established` | Global connected search reached its 100-file cap. The inherited `183` is neither confirmed nor contradicted. |
| `evaluator` | 80 | `not_established` | `not_established` | `not_established` | Global search was ranked/capped and cannot satisfy the fixed-string denominator. The inherited `80` is neither confirmed nor contradicted. |
| `oracle` | 44 | `not_established` | `not_established` | `not_established` | Connected search semantics included case/path ambiguity; the inherited lowercase `44` is neither confirmed nor contradicted. |
| `metamorphic` | 3 | 3 by exact-ref file search | `not_established` | `not_established` | The three returned files were `runtime/quality/metamorphic_controls.py`, `runtime/quality/diagnostic_slos.py`, and `runtime/quality/closeout_reader.py`. File-count agreement only. |
| `fixture_corpus` | 1 | 1 by exact-ref file search | `not_established` | `not_established` | The returned file was `runtime/quality/semantic_binding.py`. File-count agreement only. |
| `sealed_expect` | 0 | 0 by exact-ref file search | 0 by that search denominator | 0 by that search denominator | No result was returned. This is strong bounded agreement, but the complete-checkout command remains the controlling reproducer. |

**Prose reconciliation:** zero of the three high-risk figures (`183`, `80`, `44`) is claimed as
independently reproduced. Two of the three small positive file counts agree at the connected
file-search denominator, and `sealed_expect` returned no file. The table and this paragraph state the
same result.

### Finding `S0-GAP-02-I-001` — `material`

**Audit census remains incomplete.** The auditor did not reproduce matching-line and occurrence
counts over the complete source set. Evidence: this ledger §2-§3; research reproducer at
`s0-gap-02/orientation-ledger.md:51-78`. What settles it: run the quoted command in a complete checkout
of the pinned commit and attach stdout plus the script digest. Until then no exact 183/80/44 claim is
available from this audit.

### Finding `S0-GAP-02-I-002` — `commendation`

**The researcher correctly refused to manufacture the census.** The orientation ledger labels the
three large counts `not_established`, separates path/content and case semantics, names the bounded
search denominator, and supplies the exact reproducer
(`s0-gap-02/orientation-ledger.md:35-78,114-119`). That is `P35` discipline, not evasion.

## 4. Qualitative conclusion after count uncertainty

The exact token census was evidentiary orientation, not the proof of `S0-K14` non-independence. The
qualitative warning survives in a narrower form:

> The pinned repository contains multiple substantial in-tree benchmark/evaluation owners. The
> three specifically identified runtime-quality owners are not eligible as the independent
> custody verifier, and the audited OPS-R15 chain establishes no executable independent oracle.

The stronger sentence “there is no independent oracle anywhere in the whole source tree” is not
proved by the bounded sample or the incomplete token census.

### Finding `S0-GAP-02-I-005` — `material`

**Whole-tree absence language exceeds the evidence.** The main report says the configuration has “no
independent oracle at all” and the handoff says no implementation-independent chain was established
(`s0-gap-02-independent-benchmark-oracle.md:91-106`;
`s0-gap-02/integration-handoff-and-open-questions.md:27-31`). The second formulation is supportable as
an evidentiary verdict; the first is a universal repository claim. Required narrowing: say that no
eligible independent custody oracle was established by the complete OPS-R15 prior-art chain and the
three-owner sample, unless the complete census and a semantic owner walk are attached.

## 5. Three named benchmark owners — 3/3 read

| Owner | Evidence at the pin | Audit judgment |
|---|---|---|
| `policy-engine/src/polisyos/runtime/quality/policy_benchmarking.py` | Lines 1-70 define product closeout benchmarking records, required product metrics, accepted status labels, and product-facing validation. | Legitimate product diagnostic/closeout owner. It is inside the implementation tree and cannot become the `S0-K14` verifier. |
| `policy-engine/src/polisyos/runtime/quality/grounding_benchmark.py` | Lines 1-45 import `gy_content_hash`, `CredalReference`, `GroundingAdmissionEngine`, `GroundingBindGate`, `GroundingPhrasingDefenseEngine`, and grounding relation engines. Lines 78-101 carry `obligation_labels`, `expected_atom_id`, `expected_operator`, `expected_target`, and `decisive_mechanism_expected`. | Exact positive example of product-code circularity plus answer-visible fixtures. It cannot verify custody independently. |
| `policy-engine/src/polisyos/runtime/quality/semantic_fixtures.py` | Lines 1-150 define product semantic gold cards, adjudication labels, public/hidden/rotating splits, and evaluator-facing expected failure metadata inside runtime quality. | Useful product semantic-testing owner; not an independent oracle package and not a clean-room verifier. |

### Finding `S0-GAP-02-I-003` — `commendation`

**The 3/3 concept sample is accurately characterized.** In particular,
`grounding_benchmark.py` both executes product admission/relation/phrasing logic and exposes expected
semantic fields. The research uses it as an example of what `S0-K14` forbids, and that use is correct
(`s0-gap-02/orientation-ledger.md:89-105`;
`s0-gap-02-independent-benchmark-oracle.md:91-103`).

## 6. OPS-R15 prior-art inventory — 8/8 read

The report and all seven audit artifacts named by the commission were read:

1. `stage0/ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md`;
2. `audits/ops-r15/ops-r15-independent-audit.md`;
3. `audits/ops-r15/ops-r15-recommended-revision.md`;
4. `audits/ops-r15/ops-r15-stage0-kernel-and-extension-packs.md`;
5. `audits/ops-r15/ops-r15-state-contract-and-owner-audit.md`;
6. `audits/ops-r15/ops-r15-metric-and-oracle-audit.md`;
7. `audits/ops-r15/ops-r15-calendar-event-audit-ledger.md`;
8. `audits/ops-r15/ops-r15-test-and-probe-verification.md`.

The inventory confirms prior art rather than a blank slate: visible expected traces, 117 prose rows,
36 metrics, seven prose oracle families, a seeded same-code reducer fault, set-valued outcome needs,
and a four-package separation proposal all predate S0-GAP-02. S0-GAP-02's net-new work is the formal
provenance boundary, dual-channel conjunction, custody protocol, and self-falsification rule.

### Finding `S0-GAP-02-I-004` — `commendation`

**The prior-art inventory is complete and not repeated as invention.** The research read 8/8 and
correctly identifies the seeded same-code-fault probe as prior art
(`s0-gap-02/orientation-ledger.md:107-113`;
`ops-r15-test-and-probe-verification.md`, “Temporary probe results”).

## 7. Pass-I conclusion

- The researcher's refusal to claim 183/80/44 is correct.
- This audit did not close the full line/occurrence census and records that failure as
  `S0-GAP-02-I-001`.
- The named-owner argument is strong and independently verified.
- The whole-tree absence claim must remain bounded to “not established by the inspected evidence.”
- The architecture's need does not depend on the exact token counts: ratified `S0-K14`, the 3/3 owner
  sample, and the complete OPS-R15 audit chain independently establish the circularity problem.
