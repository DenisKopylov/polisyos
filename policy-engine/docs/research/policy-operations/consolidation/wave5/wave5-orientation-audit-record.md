---
title: "Wave 5 consolidation — orientation audit record"
status: candidate
stage: consolidation
base: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
---

# Wave 5 Orientation Audit Record

## Scope and method

This record compares the consolidation brief with the complete pinned Git population. It is not a
package finding register, does not amend a package, and confers no authority. Package findings remain
in the disposition ledger; the two pipeline findings below remain findings about the research
process.

Every inventory label was resolved at its repository ref
`refs/remotes/origin/research/<inventory-label>` with `git rev-parse`. Every ancestry claim was
tested with `git merge-base --is-ancestor`. Package artifacts were read with
`git show <sha>:<path>`; no research branch was checked out or merged.

The observed 22-ref manifest was:

| Remote branch | Observed SHA |
| --- | --- |
| `research/int-r2-research` | `5e6a7063da770122155af6300647d0cd2e9c17ea` |
| `research/int-r2-independent-audit` | `dbdb1243a277f0864cae9af240ff1d13786d99df` |
| `research/int-r2-amendment` | `0afc3779e2894f2793cc40150d6923589bd36ee6` |
| `research/int-r2-amendment-verification` | `b48cdb131c2a8d4f9b30ce217dfa3efcd65119fa` |
| `research/int-r3-research` | `819a83a88315a90320fdd4b25fcb328b434c77de` |
| `research/int-r3-independent-audit` | `8e9be1e5e737312f92579b57a7f011b9b14d3a46` |
| `research/int-r3-amendment` | `32cfebd02354b4d70fbf8beaca168aea6f2e72ee` |
| `research/int-r3-amendment-verification` | `81635e8878ec99dd6d9e06fc7c53fb6f13ade434` |
| `research/int-r4-ops-r5-research` | `c3999897b5be2308513846935f1c4fb68157bcb3` |
| `research/int-r4-ops-r5-independent-audit` | `ea2eac5575e5b8fb4a5462c068a37bb913076952` |
| `research/int-r4-ops-r5-amendment` | `329edb60f77867f914581d380acfccf5882d607d` |
| `research/int-r4-ops-r5-amendment-verification` | `082ddc26c2f8db55104ccb95518b72d84d94a06b` |
| `research/int-r5-research` | `02e203de90d51280d569e7f641a158569ae4df39` |
| `research/int-r5-independent-audit` | `247f89f016f71ee603ed76ef6dbb6403f7e651a0` |
| `research/int-r5-amendment` | `70f2db6d3a4330664c981721a9305f16bffe369b` |
| `research/int-r5-amendment-verification` | `d9223d12bf7cb4826c6f1f888d84275364c35fe7` |
| `research/int-r6-research` | `5e47c868c2c1d4d66fa11fcddcc972dbb55e95d3` |
| `research/int-r6-independent-audit` | `bae4f8c2b5e5ef340dda73f17bfe852c1d0d3cee` |
| `research/int-r6-amendment` | `8137aa31a4bf5e06c6b1abd4e20458295fd5a506` |
| `research/int-r6-amendment-verification` | `1accee3534befa8ce9bc656a1b35f8eaca7e9b74` |
| `research/int-r6-remediation` | `eb9b135089d4a54b648973db02f0312b276ea2ea` |
| `research/int-r6-delta-verification` | `24b6813d11e87a30e849bf4a799293e682bd7fed` |

## Brief-to-repository comparison

| Coordinate | Brief claim | Measured result | Disposition |
| --- | --- | --- | --- |
| 22 remote heads | The named refs resolve to the supplied SHAs. | **No divergence found.** All 22 exact identities reproduced. | accept orientation fact |
| Common base | Every line descends from `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`, also `origin/main`. | **No divergence found.** The base equals `origin/main`; it is an ancestor of every supplied head. | accept orientation fact |
| Consolidation branch | `research/wave5-consolidation` is cut from `origin/main`. | **No divergence found.** Initial `HEAD` and `origin/main` both resolved to the base and the branch was attached. | accept orientation fact |
| Terminal package verdicts | Five terminal packages are `CONFORMS_WITH_GAPS`. | **No divergence found.** The terminal verifier on each audit line says exactly that. INT-R6's earlier Stage-4 `NO_GO` is superseded for terminal-wave purposes by the bounded delta verification. | accept; preserve history |
| Terminal blocker state | Zero blocking findings remain. | **No terminal divergence.** The original 89-row audit population contains one blocking row, `IR6-A01`; the response and both verification stages close it. “Zero blocking” is therefore terminal state, not original severity arithmetic. | clarify in standing statement |
| INT-R3 topology | Pipeline §2 requires the audit line to contain the research line. | Divergence found: `819a83a…` is not an ancestor of `8e9be1e…`; this is already `INT-R3-AUD-O01`. The later amendment is a two-parent union and terminal containment is restored. | package row closed; pipeline incident retained |
| INT-R4 ‖ OPS-R5 subjects | One package has two subjects and two evidence registers. | **No divergence found.** The audit denominator is one 18-row table, split 10 INT / 8 OPS in the response. | count once as one package |
| Finding totals | The brief deliberately gives no per-package counts. | **No inherited count existed to contradict.** Independent table parsing yields 16, 23, 18, 18 and 14 rows: 89 total. | publish command and both denominators in ledger |
| “Two verifiers published mappings” | Both out-of-vocabulary amendment usages already have verifier-published §3.3 mappings. | **Divergence found.** INT-R2's verifier publishes `13 accepted / 3 accepted_with_variation / 0 declined`. The combined verifier flags `routed_pending_principal`, publishes no mapping and says the author neither accepted nor declined F05. | preserve raw token as `unmapped_invalid`; route author correction; consolidation supplies no disposition |
| GY-N11 existing load | Two DS17 obligations already load GY-N11. | **No divergence found.** The Atlas master plan carries the Bayesian-without-coverage negative and the `over_spend` end-to-end witness. | Wave 5 adds zero GY-N11 obligations; accumulated load stays two |
| H2 custody-runtime plan | A competent H2 implementation plan may already own OPS-R5 state/runtime work. | Divergence from an assumed route, not from explicit brief text: no `docs/plans/active/H2-*` plan exists. The Wave-2 backlog says one must be commissioned. | routes say `no owner exists`; consolidation does not create it |
| Ratified statements | Wave findings may expose a defect in a prior ratified act. | **None found.** The packages refine or instantiate ratified boundaries; no ratified proposition was falsified. | no stop on this coordinate |
| Cross-task facts | Two tasks may contradict on a measured fact. | **None found.** Apparent tensions are scope/semantics questions, most notably GY-O1 versus the INT-R4 proposal, not two incompatible measurements. | route the unresolved policy choice; do not adjudicate it |
| Outcome-vocabulary ordinal | The brief describes the trigger as a fourth outcome-vocabulary entry. | **No substantive divergence.** Binding INT §8 calls it the third **new element**; Wave 4 says the count is three, so that same event is the fourth **total entry**. | use both ordinals explicitly; no trigger in this wave |

## Pipeline finding PIP-W5-01 — §3.3 vocabulary clarity

The operative sentence in
`docs/reference/policy-operations-research-pipeline.md` says:

> `disposition ∈ accepted · accepted_with_variation · declined_with_reason`

The membership symbol and three enumerated values are a closed set. That reading is independently
used by the INT-R2, INT-R5, INT-R6 and combined verifiers. The architect's proposition that the text
does not read as closed is therefore **declined as a semantic interpretation**.

The usability concern is nevertheless established. Two of five amendments used outside tokens:

- INT-R2: `accepted_corrected`, `accepted_residual_registered`, `preserved`;
- INT-R4 ‖ OPS-R5: `routed_pending_principal` on `AUD-F05`.

Thus the measured amendment-package denominator is five and the deviation denominator is two:
`2/5` packages. The edit should make the existing rule explicit: “closed set; exactly these values;
routing state and verification outcome belong in separate fields.” Destination:
`docs/reference/policy-operations-research-pipeline.md`, §3.3, amended paragraph. This is a pipeline
clarification, not a fourth disposition.

## Pipeline finding PIP-W5-02 — disclosure accuracy

The complete task denominator is five. A complete read of the six verifier-stage documents across
those tasks (INT-R6 has Stage 4 and delta verification) found no content-bound conversational
hand-back body: the consolidator's directly assessable denominator is therefore **0/5**, and an
independent wave accuracy/mismatch rate is `not_established`.

The six-`.md` denominator was: `b48cdb13…:audits/int-r2/int-r2-amendment-verification.md`,
`81635e88…:audits/int-r3/int-r3-amendment-verification.md`,
`082ddc26…:audits/int-r4-ops-r5-amendment-verification/int-r4-ops-r5-amendment-conformance-verification.md`,
`d9223d12…:audits/int-r5-amendment-verification/int-r5-amendment-conformance-verification.md`, and
`1accee35…:audits/int-r6-amendment-verification/int-r6-amendment-conformance-verification.md` plus
`24b6813d…:audits/int-r6-delta-verification/int-r6-remediation-delta-verification.md`, all below
`policy-engine/docs/research/policy-operations/`. Each complete blob—not a keyword hit—was read.

| Task | Direct hand-back body in branch | What the verifier reports | Consolidator classification |
| --- | --- | --- | --- |
| INT-R2 | absent | final readback would occur in a later hand-back | `not_established` |
| INT-R3 | absent | only a prospective delivery statement | `not_established` |
| INT-R4 ‖ OPS-R5 | absent | G1–G6 compare architect-supplied values; terminal receipts `not_produced` | `not_established` |
| INT-R5 | absent | three discrepancies: six versus seven paths, `17/1/0` versus `16/2/0`, and wrong reason namespace | verifier-reported `inaccurate`; institutionally supplied here |
| INT-R6 | absent | completion disclosure matched its declared fact set; an earlier episode had mismatches | verifier-reported mixed episodes; institutionally supplied here |

Thus **2/5** tasks have verifier-reported disclosure classifications, but neither underlying message
is content-bound to this reader and the two reports use different episode units. They cannot be pooled
into a rate. The other three remain `not_established`; the architect's additional conversational
examples are likewise not inherited as branch facts. The two independent Stage-4 axes occur at
verifier blobs `d9223d12…` (INT-R5) and `1accee35…` (INT-R6).

Disposition: add `disclosure_accuracy` permanently to pipeline §3.4 and require a content-bound
delivery-disclosure receipt in §5 so future denominators are reproducible. The axis must distinguish
`matches_branch`, `inaccurate`, and `not_established`; branch delivery and disclosure accuracy remain
separate. Destination and declared owner: existing pipeline reference, `team-architecture`.

## Consolidator orientation errors corrected

1. I initially inherited the brief's implication that both affected verifiers supplied vocabulary
   mappings. Exact combined-verifier readback disproved it. The ledger now preserves the invalid token
   and routes author correction instead of normalizing it.
2. I initially used “zero blocking” as shorthand for the wave. The original row census contains one
   blocking row; only the terminal residual population has zero. Both figures are now stated with
   their time coordinate.
3. I considered GY-N11 as a generic destination for post-deployment verification. Reading its Atlas
   load showed two already-assigned negative witnesses. No Wave-5 item is routed there.
4. I treated verifier descriptions as though two underlying hand-back bodies were branch-custodied.
   None is; direct coverage is 0/5, 2/5 are verifier-reported, and no accuracy rate is published.
5. My first row walk stopped at 70 questions. A complete response-section walk found INT-R2 Q14/Q15
   and INT-R6 OQ-01; the deduplicated denominator is 73 and the route map now has 106 rows.
6. I compressed source questions into short labels and dropped load-bearing alternatives and
   anti-role constraints. The question artifact now preserves every source conjunct; the route map
   routes the same content.
7. I treated register/plan custody and downstream lanes as capability ownership, including GY-O1/O3
   and the INT-R6 census verifier. Those routes now preserve `absent/unallocated` or say
   `no owner exists`.

## Stop-rule record

- Several honest destinations are `no owner exists`: the H2 custody runtime, an operator
  comprehension study, institutional signers/adjudicators, and multilingual ground-truth work.
  Creating those owners is larger than creating a document. Consolidation stops at reporting the
  missing owner and the document/appointment that would be required; it does not appoint or build.
- Candidate operational rules that would constrain containment, update, or deployment action are
  excluded from ratification candidates and routed instead.
- No ratified-statement defect and no cross-task contradiction of measured fact was found.
