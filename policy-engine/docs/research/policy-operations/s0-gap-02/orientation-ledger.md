---
title: S0-GAP-02 — Orientation and pinned-repository evidence ledger
status: research
research_only: true
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
result_standing: accepted_narrow_scope
authoritative_for:
  - bounded orientation evidence gathered for S0-GAP-02 at the named repository pin
  - census denominator definitions and access limitations
  - prior-art reading inventory
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

# S0-GAP-02 orientation and evidence ledger

## 1. Scope and method

This is the required Pass-I orientation audit. It was completed before the architecture was selected. Repository observations are bounded to commit `1a7a2d05ebba22fae80e9934329e4b880806588e` (`PIN`). The connected GitHub interface confirmed that this commit exists and that `main` was identical to it at the time of the read. Ordinary `git clone` and archive egress were unavailable because the execution environment could not resolve `github.com`; the connected interface permitted exact-ref reads but exposed no write action. The delivery therefore distinguishes three evidence grades:

| Grade | Meaning |
|---|---|
| `exact_ref_read` | The named file and line range were read through the connected GitHub interface at `PIN`. |
| `connected_search` | A GitHub code-search result was obtained at `PIN`; this is file-oriented, case-insensitive in practice, may include path matches, and does not expose raw occurrence totals. |
| `not_established` | The requested complete-tree fact could not be reproduced with the available interface. It is not inferred from a sample. |

This is an application of **P35**, not an exception to it: a set-level claim requires a complete enumeration and its denominator; a connected search capped or altered by query semantics is not silently promoted to a complete census. **P36** is also applied: ratified propositions are cited by finding ID rather than by neighboring prose. (`policy-engine/docs/reference/policy-design-case-failure-patterns.md:71-80@1a7a2d05ebba22fae80e9934329e4b880806588e`, findings `P27`, `P28`, `P35`, `P36`.)

## 2. Commission and governing findings

| Evidence item | Pinned finding and line | Orientation consequence |
|---|---|---|
| Commission | `S0-K14`, `S0-K15`, and the ratification action commissioning `S0-GAP-02` (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:143-202@1a7a2d05ebba22fae80e9934329e4b880806588e`) | The task is a pending ratified obligation, not a new proposal. It blocks scoring claims, not continued capstone design. |
| Observable-semantics boundary | `S0-K13` (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:96-112@1a7a2d05ebba22fae80e9934329e4b880806588e`) | An evaluator judges observable custody semantics, not internal architecture. |
| Verification independence | `S0-K14` (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:143-154@1a7a2d05ebba22fae80e9934329e4b880806588e`) | A same-code rebuild may establish consistency only; it cannot establish independent correctness. |
| Memorization and dissent | `S0-K15` (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:155-176@1a7a2d05ebba22fae80e9934329e4b880806588e`) | Hidden/adjacent cases and preserved disagreement are mandatory design properties. |
| Bounded passage | `S0-K16` (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:96-112@1a7a2d05ebba22fae80e9934329e4b880806588e`) | A pass carries no authority and is bounded to a named implementation, revision, environment, population, and evaluator. |
| One owner, no second ledger | `INT-K05` (`policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:157-170@1a7a2d05ebba22fae80e9934329e4b880806588e`) | Evaluator records must not become a second product confidence or authority ledger. |
| No safe inheritance from approximation | `PV-K06` (`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:164-182@1a7a2d05ebba22fae80e9934329e4b880806588e`) | An unsupported, timed-out, empty, or unproved approximation cannot inherit an acceptable benchmark verdict. |
| Authoritative task detail | `S0-GAP-02` register entry (`policy-engine/docs/research/policy-operations/consolidation/stage0/stage0-additional-research-register.md:123-199@1a7a2d05ebba22fae80e9934329e4b880806588e`) | The four comparative models, eight baseline deliverables, six falsifiers, dependencies, and non-authorization effect are binding. |

### Brief-to-register precedence check

No substantive contradiction was found. The register remains authoritative for the commission’s baseline scope and gate. The present brief adds non-conflicting specificity: formal independence, three additional attacks, integration-label prerequisite evidence, typed open questions, external transfer ledger, and a result-standing vocabulary. The brief does not narrow the register’s required four-model comparison or its eight baseline outputs. Delivery of this research does not itself satisfy the register’s implementation and acceptance dependency. (`policy-engine/docs/research/policy-operations/consolidation/stage0/stage0-additional-research-register.md:123-199@1a7a2d05ebba22fae80e9934329e4b880806588e`, entry `S0-GAP-02`.)

## 3. Orientation census: files, lines, and occurrences are different denominators

The commission supplied six figures described as “Files in `policy-engine/src`.” A hostile audit can reproduce a complete checkout census; this run could not because ordinary repository egress was blocked and the connected interface does not return a recursive tree or raw occurrence stream. Accordingly, this ledger does **not** relabel connected-search results as a complete source walk.

| Token | Commissioned file count | Connected exact-ref observation | Distinct matching files | Matching source lines | Raw token occurrences | Orientation verdict |
|---|---:|---|---:|---:|---:|---|
| `benchmark` | 183 | Search is dense and exceeds a single result page; grouped searches show heavy concentration in `runtime`, `scientist`, `foundry`, and `data_forge`. Search behavior also matched path segments such as `benchmarks/`. | `not_established` independently | `not_established` | `not_established` | **Figure not independently reproduced.** The qualitative warning—extensive benchmark machinery—is supported, but the exact denominator must be rerun from a complete checkout. |
| `evaluator` | 80 | Connected search exceeded its result cap and is case/path sensitive in ways that prevent an exact lowercase file census. | `not_established` independently | `not_established` | `not_established` | **Figure not independently reproduced.** Dense evaluator vocabulary is established; exact count is not. |
| `oracle` | 44 | Connected search returned 50 case-insensitive distinct-file results, demonstrating that its semantics differ from the brief’s lowercase census. | `not_established` independently | `not_established` | `not_established` | **Disagreement in query semantics, not a repository contradiction.** The exact lowercase complete-tree result remains `not_established`. |
| `metamorphic` | 3 | Three files were returned: `runtime/quality/metamorphic_controls.py`, `runtime/quality/diagnostic_slos.py`, and `runtime/quality/closeout_reader.py`. | 3 by connected search | `not_established` | `not_established` | **Agreement at file-search denominator.** |
| `fixture_corpus` | 1 | One file was returned: `runtime/quality/semantic_binding.py`. | 1 by connected search | `not_established` | `not_established` | **Agreement at file-search denominator.** |
| `sealed_expect` | 0 | No result was returned under `policy-engine/src`. | 0 by connected search | 0 by connected search | 0 by connected search | **Agreement within connected-search limits.** Absence outside tracked source, generated artifacts, or external services is not claimed. |

### Reproducible complete-checkout command

The following is an executable census specification, not a claim that it ran here. It defines all three denominators and prevents a path-name match from masquerading as a content match:

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

The command is case-sensitive and fixed-string. A separate case-insensitive census, if wanted, must be named as such rather than compared to these figures.

## 4. Concept census versus vocabulary census

The figures are an orientation signal, not a semantic classification. The complete denominator of files containing the words was unavailable, so no claim is made that all 183/80/44 files were concept-reviewed. The bounded concept sample was the three benchmark owners expressly named by the commission: denominator **3 named owners, 3 read in full or in owner-relevant ranges, 3 unsuitable as an independent custody verifier**.

| Named owner | Pinned evidence | What it is | Independence consequence |
|---|---|---|---|
| `policy_benchmarking.py` | `policy-engine/src/polisyos/runtime/quality/policy_benchmarking.py:1-70@1a7a2d05ebba22fae80e9934329e4b880806588e` | A production runtime-quality benchmarking/validation owner with implementation-facing pass criteria and metrics. | It may remain a product diagnostic owner. Extending it into the S0-K14 verifier would put evaluator semantics inside the implementation tree. |
| `grounding_benchmark.py` | `policy-engine/src/polisyos/runtime/quality/grounding_benchmark.py:1-140@1a7a2d05ebba22fae80e9934329e4b880806588e` | A benchmark that imports production admission, relation, phrasing-defense, and hash code and carries implementation-visible expected fields such as obligation labels and expected operators. | It is positive evidence of the exact shared-code/visible-answer pattern S0-GAP-02 must prohibit, not a candidate oracle. |
| `semantic_fixtures.py` | `policy-engine/src/polisyos/runtime/quality/semantic_fixtures.py:1-150@1a7a2d05ebba22fae80e9934329e4b880806588e` | Production fixture and adjudication machinery with visible semantic signals and gold-card results. | It can inform anti-leakage risks, but neither its labels nor its adjudication code may be imported by an independent evaluator. |

The repository import policy enumerates production package roots and permits wide runtime dependencies; it contains no separately governed independent evaluator root at the pin. (`policy-engine/architecture/imports/policy.toml:1-132@1a7a2d05ebba22fae80e9934329e4b880806588e`.) This does not prove that no external evaluator exists; it proves only that the inspected in-repository import policy does not construct the required separation.

## 5. OPS-R15 prior-art inventory

The input report and all seven audit artifacts were read at `PIN`:

1. `policy-engine/docs/research/policy-operations/stage0/ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md:1-2@1a7a2d05ebba22fae80e9934329e4b880806588e`
2. `policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-recommended-revision.md:1-2@1a7a2d05ebba22fae80e9934329e4b880806588e`
3. `policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-stage0-kernel-and-extension-packs.md:1-2@1a7a2d05ebba22fae80e9934329e4b880806588e`
4. `policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-independent-audit.md:1-2@1a7a2d05ebba22fae80e9934329e4b880806588e`
5. `policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-state-contract-and-owner-audit.md:1-2@1a7a2d05ebba22fae80e9934329e4b880806588e`
6. `policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-metric-and-oracle-audit.md:1-2@1a7a2d05ebba22fae80e9934329e4b880806588e`
7. `policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-calendar-event-audit-ledger.md:1-2@1a7a2d05ebba22fae80e9934329e4b880806588e`
8. `policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-test-and-probe-verification.md:1-2@1a7a2d05ebba22fae80e9934329e4b880806588e`

The prior art already proposes a four-package benchmark architecture, hidden mutations, set-valued expectations, and a bounded receipt, while reserving same-code rebuild for diagnosis. (`policy-engine/docs/research/policy-operations/stage0/ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md:326-470@1a7a2d05ebba22fae80e9934329e4b880806588e`, especially `CK-11`.) Its executable probe demonstrates the discriminating risk: a deliberately faulty reducer produced the same wrong value incrementally and on rebuild, while an independent result differed; the same audit records visible expected answers and no executable independent oracle. (`policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-test-and-probe-verification.md:80-160@1a7a2d05ebba22fae80e9934329e4b880806588e`.) S0-GAP-02 therefore extends the prior art by constructing enforceable provenance separation and a challenge/custody protocol; it does not repeat the benchmark narrative or score its fixtures.

## 6. Orientation conclusions

1. **The dangerous configuration is established qualitatively, not by an invented count:** extensive in-tree benchmark/evaluator/oracle vocabulary coexists with no connected-search hit for `sealed_expect` and with three named owners that are production-coupled or answer-visible.
2. **The exact 183/80/44 figures remain `not_established` in this run.** A complete-checkout command is supplied so a later auditor can reproduce file, line, and occurrence denominators without search-interface ambiguity.
3. **P27/P28 do not win by default.** Their canonical-owner discipline applies to ordinary production capability ownership, while `S0-K14` expressly requires the verification semantics to live outside the implementation’s semantic provenance. (`policy-engine/docs/reference/policy-design-case-failure-patterns.md:71-80@1a7a2d05ebba22fae80e9934329e4b880806588e`, findings `P27`, `P28`; `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:143-154@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `S0-K14`.)
4. **No score, unblock, or capability claim follows.** The evidence establishes the need and boundary for an architecture only.
