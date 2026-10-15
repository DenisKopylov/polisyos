# Guidelines For Academic Causal Claim Annotation

## Annotation Purpose

You are annotating the quality and status of causal claims in academic papers for a `policy-oriented causal knowledge graph`, not the "truth of economic laws."

The task context is as follows. `PolisyOS` collects academic papers on policy-relevant topics, extracts candidate causal claims from them, and then decides which claims are reliable enough to publish in the graph as causal edges. At this stage, the `Qwen` model can already find candidate claims, but it tends to conflate three different things:

1. the paper uses causal language;
2. the paper actually identifies a causal effect;
3. the claim is reliable enough to enter a production-grade graph.

The `gold set` is intended to correct this conflation.

Your annotation is not meant to "agree or disagree" with the paper's substantive conclusions. It sets a strict standard for how the system should interpret scientific text. The main questions are: what exactly does the paper claim, how causal is the wording, how well does the research design support the claim, and should the claim enter the graph as a `credible causal edge`?

The system follows a `precision-first` approach. We would rather miss some weak or ambiguous claims than add many false-positive causal relationships to the graph. Therefore, annotate conservatively when uncertain. If a paper reports `association`, `correlation`, a `panel relationship`, or a `regression coefficient` without a convincing `identification design`, do not automatically treat it as a strong causal claim.

## Three Evaluation Levels

It is essential to keep three evaluation levels separate.

1. `paper relevance`:
   whether the paper is relevant to `policy-causal extraction` at all.
2. `claim presence`:
   whether the paper states a claim that can be identified as a distinct assertion.
3. `causal validity`:
   whether the claim is genuinely a `causal assertion` with sufficient evidence, rather than merely an association, mechanism, review conclusion, or normative remark.

Model errors most often occur in the transition from the second level to the third.

The unit of annotation at the `claim-level` is a specific assertion, not the paper as a whole. A paper may contain no usable claims or several claims with different statuses. For example, a paper may contain one main causal claim, one mechanism, and one weak observational side result. These should receive separate annotation outcomes, not one overall paper rating.

## Source Rule

Do not rely on outside knowledge about the paper, author, journal, or topic. Judge only the text supplied in the candidate packet:

- `title`
- `paper_abstract`
- `claim_text`
- `supporting_spans`
- `supporting_text`
- `method_spans`, if present
- `source_basis`
- `design_family_hint`

Insufficient evidence in the packet is not a reason to guess that the paper is probably strong. In that case, lower confidence or `causal_credibility`, or use `insufficient_evidence` / `unclear`.

## Causal Language vs. Causal Evidence

It is especially important to distinguish:

- `paper uses causal language`
- `paper has causally credible evidence`
- `claim should be published to the graph`

These are three different things.

In economics and `policy-literature`, these are not equivalent. Phrases such as `affects`, `impacts`, `drives`, `improves`, and `reduces` also occur frequently in observational papers. Strong causal status usually requires an explicit `design signal`: `RCT`, `IV`, `DiD`, `RDD`, `synthetic control`, or very strong `meta-analysis` evidence. `Panel FE`, `OLS`, `cross-sectional regressions`, and `ML prediction` alone should not be labeled `strong causal evidence`.

## Source Basis

The `source_basis` field is critical and should be interpreted as follows:

- `fulltext`:
  the claim is grounded in the full paper text. This is the preferred mode for a production-grade gold set.
- `abstract_only`:
  the claim is grounded only in the abstract. Such claims are useful for exploratory recall and early annotation rounds, but should almost never enter the production causal graph as `strong publishable edges`.

Be even more conservative when annotating an `abstract-only` packet. Even if the paper looks strong based on its abstract, do not automatically raise the claim to `publish_to_graph = yes` without the full text.

## Supporting Spans

`Supporting spans` are central. We are building a system in which each claim must be grounded in specific textual evidence. A good supporting span matters more than a polished paraphrase of the claim.

If a supporting span:

- does not support the specific `cause -> effect relation` identified in the claim;
- describes background, motivation, or general context rather than a result; or
- discusses only the method, not the finding;

then the claim should be considered weak, insufficiently supported, or `not_causal` / `insufficient_evidence` for the graph.

## Two Expert Annotation Modes

Annotation now takes place in two separate bundles:

1. `fulltext-only bundle`
   - a stronger source for the gold set;
   - supports stricter judgments about `design_family`, `causal_credibility`, and `publish_to_graph`;
   - the primary candidate for a production-grade gold core.

2. `abstract-only bundle`
   - a supplementary set;
   - used to calibrate system behavior when text is limited;
   - decisions should be especially conservative.

When comparing the two bundles:

- if the same type of claim is annotated differently in `fulltext` and `abstract_only`, give priority to `fulltext`.

## Screen Gold

The `paper_relevant_for_policy_causal_extraction` field records a screen-level decision: should the paper proceed to the causal extraction pipeline at all?

Set it to `yes` if the text:

- studies the effect, impact, or consequence of a policy, institutional change, regulation, program, tax, subsidy, spending intervention, or governance reform;
- reports empirical estimates, quasi-experimental evidence, experiments, `meta-analysis`, or explicit causal findings; or
- is useful for building a policy causal graph, even when the result is `null` or `mixed`.

Set it to `no` if the text:

- is purely descriptive and has no policy-evaluation angle;
- is purely theoretical, with no empirical evidence or review/meta synthesis;
- is editorial, commentary, or normative text;
- is a bibliographic stub, redirect, or technical placeholder; or
- falls outside the scope of policy-relevant social science.

Set it to `unclear` if the supplied text does not provide enough evidence to confidently choose `yes` or `no`.

## Claim Gold Fields

Required fields at the claim level:

- `paper_relevant_for_policy_causal_extraction`
- `claim_present`
- `claim_text`
- `claim_type`
- `explicitness`
- `cause_text`
- `effect_text`
- `direction`
- `supporting_spans`
- `source_basis`
- `design_family`
- `causal_credibility`
- `risk_of_bias`
- `support_status`
- `publish_to_graph`

### Claim Type

- `causal_claim`: the paper asserts or explicitly implies that `X causes Y`
- `associative`: the paper reports an association/correlation without enough design support
- `mechanism`: text about how a relationship works, rather than the main causal edge
- `review_summary`: synthesis/review/meta claim
- `unclear`: the type cannot be determined reliably
- `not_applicable`: claim-level annotation does not apply

### Explicitness

- `explicit`: the text directly uses effect/impact/causes/leads to
- `implicit`: causal meaning strongly implied
- `unclear`: textual evidence is insufficient

### Design Family

Allowed values:

- `rct`
- `iv`
- `did`
- `rdd`
- `synthetic_control`
- `panel_fe`
- `ols_cross_sectional`
- `structural_model`
- `review_narrative`
- `review_meta_analysis`
- `time_series_cointegration`
- `quasi_experimental_iv`
- `quasi_experimental_did`
- `quasi_experimental_rdd`
- `quasi_experimental_other`
- `theoretical`
- `unclear`
- `not_applicable`

If the design is not evident from the packet text, use `unclear` rather than inferring it from the paper's reputation.

### Causal Credibility

- `strong`: explicit causal claim backed by strong identification or meta evidence
- `moderate`: plausible causal claim with decent design support but material caveats
- `weak`: likely association or weak design support
- `insufficient`: there is not enough textual support to consider the claim causally credible
- `not_causal`: the claim should not be represented as a causal edge
- `unclear`: the evidence does not allow a decision
- `not_applicable`: the field does not apply

### Risk Of Bias

- `low`
- `moderate`
- `serious`
- `critical`
- `unclear`
- `not_applicable`

### Support Status

- `supported`: the text supports the extracted claim
- `mixed`: the text supports the claim but includes explicit caveats or mixed findings
- `counterevidence`: the paper contains explicit counterevidence
- `insufficient_evidence`: there is not enough text to support the claim
- `not_applicable`: the status does not apply

### Publish To Graph

Set `yes` only when all of the following conditions hold:

- `claim_type = causal_claim` or a justified `review_summary`
- `causal_credibility in {strong, moderate}`
- `support_status in {supported, mixed}`
- `supporting_spans` genuinely support the claim
- `source_basis = fulltext`, except for very rare exceptions such as a `meta-analysis`

By default, set `no` for:

- `abstract_only` claims
- claims without a convincing supporting span
- `panel_fe` / `ols_cross_sectional` claims without stronger identification evidence
- descriptive, normative, or unclear statements

## Practical Priority

The `design_family`, `causal_credibility`, `risk_of_bias`, and `support_status` fields are not academic decoration; they support downstream filtering. They are used to build:

- QC gates
- prompt calibration
- regression tests
- publish rules

Your task is therefore not just to "sort examples," but to give the system sound epistemic discipline: what to treat as a causal claim, what to treat as an association only, and what must not be published as a causal edge at all.

The gold set's ultimate goal is to teach the system to be strict, grounded, and reproducible. After annotation, this set will be used to evaluate `precision`, `calibration`, and `overcall-rate` on `quasi-natural` claims, and to tune adjudication prompts and acceptance criteria.

Use these priorities:

- fewer guesses
- more textual support
- less generosity toward causal claims
- more conservative precision
