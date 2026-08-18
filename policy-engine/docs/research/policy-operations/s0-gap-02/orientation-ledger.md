---
title: S0-GAP-02 — Orientation and pinned-repository evidence ledger
status: research
research_only: true
repository_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
source_tree_equivalent_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
audited_commit: a7c34cc40b649a10b6878228a8a57acc498f279a
audit_commit: 3abbaf8c2808e31fd7d8f9929b696e78dc91b3d4
amendment_branch: research/s0-gap-02-amendment
amendment_status: audit_amended
result_standing: accepted_narrow_scope
authoritative_for:
  - bounded orientation evidence for S0-GAP-02 at the named pins
  - complete census denominator definitions and reconciled counts
  - three-owner concept sample and OPS-R15 prior-art inventory
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner, evaluator, custodian or vendor appointment
  - reviewer panel or evaluator-team appointment
  - authority grant
  - capability claim
  - benchmark passage
  - legal-sufficiency conclusion
  - permission to score OPS-R15
  - claim that OPS-R15 is unblocked
  - automatic amendment of any plan, backlog or system-design decision
---

# Orientation and pinned-repository evidence ledger

## 1. Method and pin discipline

Documentation claims use `main@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`. The architect supplied that `policy-engine/src` is byte-identical to original source pin `1a7a2d05ebba22fae80e9934329e4b880806588e`; source citations retain that full equivalent pin where useful.

The original research environment could not perform ordinary clone/push and correctly claimed no remote state. It also correctly refused to manufacture the inherited census from ranked search, but incorrectly concluded that the connected GitHub interface had no write actions. This amendment uses `create_file`/`update_file`; the delivery-provenance correction does not change the original 9/9 digest evidence.

`P35` applies symmetrically: an index establishes neither a zero nor a positive, and every count states its path and file-type denominator. `P36` requires finding-ID authority. `P37` prevents a gate predicate—such as neutrality, compatibility or machine-checkability—from being supplied merely by declaration. (`policy-engine/docs/reference/policy-design-case-failure-patterns.md`, findings `P35`–`P37`, at `109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`.)

## 2. Governing repository findings

| Finding | Consequence for this architecture |
|---|---|
| `S0-K13` | Evaluate observable custody semantics, not product internal architecture. |
| `S0-K14` | Independent verification may not share admission, reducers, dependency traversal or status projection; same-code rebuild proves consistency only. |
| `S0-K15` | Hidden/adjacent cases and preserved dissent are mandatory. |
| `S0-K16` | Passage is bounded to named artifacts/population/environment/evaluator and carries no authority. |
| `INT-K05` | Benchmark evidence cannot become a second product confidence/authority ledger. |
| `INT-K08` | Negative completion is valid; local non-establishment terminals do not create a fourth outcome-vocabulary element. |
| `PV-K06` | Timeout, unsupported theory, incomplete history or unproved approximation cannot inherit acceptance. |
| `S0-GAP-02` register entry | Four comparative models, eight baseline outputs, six commissioned falsifiers and non-authorization boundary remain binding. |

The brief adds compatible formalism, attacks, handoff, typed questions and transfer ledger. No conflict with the authoritative register was found.

## 3. Complete source census

### 3.1 Denominator

- repository ref: source tree equivalent to `109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`;
- path denominator: tracked content under `policy-engine/src`;
- matching: case-sensitive fixed strings in content, path-name matches excluded;
- binaries: excluded;
- Python-only files: tracked `*.py` under the path;
- all-source files: all tracked non-binary source/text files under the path;
- matching line: one line containing one or more matches;
- occurrence: each non-overlapping fixed-string match.

| Token | Python-only matching files | All-source matching files | All-source matching lines | All-source occurrences |
|---|---:|---:|---:|---:|
| `benchmark` | **183** | **197** | **2,000** | **2,319** |
| `evaluator` | **80** | **85** | **444** | **512** |
| `oracle` | **44** | **44** | **323** | **386** |

The inherited `183 / 80 / 44` were correct Python-only matching-file counts; the original brief omitted that file-type denominator. The researcher’s refusal to repeat them without verification was correct. The complete walk closes audit finding `S0-GAP-02-I-001` without converting token counts into semantic classification.

Reproducer shape:

```bash
PIN=109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
for token in benchmark evaluator oracle; do
  py_files=$(git grep -I -l -F "$token" "$PIN" -- 'policy-engine/src/**/*.py' | wc -l)
  all_files=$(git grep -I -l -F "$token" "$PIN" -- policy-engine/src | wc -l)
  lines=$(git grep -I -n -F "$token" "$PIN" -- policy-engine/src | wc -l)
  occurrences=$(git grep -I -h -F "$token" "$PIN" -- policy-engine/src \
    | awk -v t="$token" '{n+=gsub(t,t)} END{print n+0}')
  printf '%s py_files=%s all_files=%s lines=%s occurrences=%s\n' \
    "$token" "$py_files" "$all_files" "$lines" "$occurrences"
done
```

The amendment records architect-supplied complete-walk results; it does not claim the original research process executed this command.

## 4. Bounded concept sample

Token membership is not semantic ownership. The concept denominator remains exactly the three owners named by the commission: **3 named owners, 3 read, 3 unsuitable as the independent custody verifier**.

| Owner | Evidence | Judgment |
|---|---|---|
| `policy_benchmarking.py` | `policy-engine/src/polisyos/runtime/quality/policy_benchmarking.py:1-70@1a7a2d05ebba22fae80e9934329e4b880806588e` | Product runtime-quality benchmarking/validation; legitimate diagnostic owner, not independent verifier. |
| `grounding_benchmark.py` | `policy-engine/src/polisyos/runtime/quality/grounding_benchmark.py:1-140@1a7a2d05ebba22fae80e9934329e4b880806588e` | Imports product admission/relation/phrasing/hash logic and exposes expected labels/operators/targets; exact positive evidence of the prohibited pattern. |
| `semantic_fixtures.py` | `policy-engine/src/polisyos/runtime/quality/semantic_fixtures.py:1-150@1a7a2d05ebba22fae80e9934329e4b880806588e` | Product semantic fixtures/adjudication/gold records; useful for risk orientation, disqualifying as independent oracle input. |

The production import policy does not construct a separately governed independent evaluator root. (`policy-engine/architecture/imports/policy.toml:1-132@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`.) That does not prove no external evaluator exists.

## 5. OPS-R15 prior art: 8/8 read

The report and all seven audit artifacts were read at the docs pin:

1. `stage0/ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md`;
2. `audits/ops-r15/ops-r15-recommended-revision.md`;
3. `audits/ops-r15/ops-r15-stage0-kernel-and-extension-packs.md`;
4. `audits/ops-r15/ops-r15-independent-audit.md`;
5. `audits/ops-r15/ops-r15-state-contract-and-owner-audit.md`;
6. `audits/ops-r15/ops-r15-metric-and-oracle-audit.md`;
7. `audits/ops-r15/ops-r15-calendar-event-audit-ledger.md`;
8. `audits/ops-r15/ops-r15-test-and-probe-verification.md`.

Prior art already identifies visible expected traces, set-valued outcomes, hidden mutations, a four-package split and a deliberately faulty reducer that passes incremental and clean-build parity while an independent answer differs. S0-GAP-02’s net-new work is the formal provenance boundary, dual blocking channels, specification assurance, oracle custody and self-falsification; it does not score the prior fixtures.

## 6. Orientation conclusions

1. The inherited counts are reconciled with both Python-only and all-source/line/occurrence denominators.
2. The original refusal to invent them remains a `P35` commendation.
3. Census proves vocabulary density, not the semantic absence or presence of an independent oracle.
4. The supportable bounded statement is: **no eligible independent custody oracle was established by the complete OPS-R15 evidence chain and the 3/3 named-owner sample.** “No independent oracle at all” remains unsupported as a universal semantic claim.
5. The 3/3 sample is accurately characterized, especially the product imports and expected-answer fields in `grounding_benchmark.py`.
6. `P27/P28` continue to govern product facts/diagnostics; `S0-K14` is the narrow answer-producing-verification exception; `P37` prevents the exception’s own predicates from being declared rather than constructed.
7. No score, capability, owner appointment or OPS-R15 unblock follows.
