---
task_id: INT-R3
stage: 3
artifact_role: external_source_ledger
status: amendment_complete
authoritative_for:
  - int_r3_external_claim_traceability
may_not_use_for:
  - repository_capability_claim
  - source_domain_rate_transfer
  - operator_population_prevalence
---

# INT-R3 external source ledger

This ledger closes the repository-only traceability defect without promoting the five surveys to
authority. It binds each stage-1 `EXT-*` row to an exact survey input and to stable primary-source or
official-method identifiers.

## Exact survey inputs

The survey files were supplied externally to the stage-1 researcher. They are not committed as
repository capability. Their exact content identity is retained so the same input can be reconciled
later.

| Survey ID | File | Title | Lines | Bytes | SHA-256 |
| --- | --- | --- | ---: | ---: | --- |
| `SURV-01` | `deep-research-report-297.md` | Когда значение — не число: `unknown`, пропуски, интервалы, несравнимость и риск-бюджет | 358 | 74,673 | `9ee76f2bc23ecf118365c0ab0f7f92b4a1e03417ff6f8fa3abe00b071c0ae67e` |
| `SURV-02` | `deep-research-report-298.md` | Время, давление и отсрочка решения | 404 | 72,801 | `cefa71c2261beb11fec0c7808cd280425911cb5b2e5ba19feec0e5affc0b499f` |
| `SURV-03` | `deep-research-report-299.md` | Что останавливает компетентного пользователя | 307 | 61,511 | `82b404d93a10cca0d788cb817bf4944980f92204b822af924c1185e75579142f` |
| `SURV-04` | `deep-research-report-300.md` | Поведенческий benchmark и defensible ground truth | 407 | 78,961 | `39491d6731185cdb16e5cc1ea91a5981cd9e139ca4d6f46791613d77be811475` |
| `SURV-05` | `deep-research-report-301.md` | Screen reader, keyboard-only и низкая numeracy | 188 | 61,762 | `d8eda1e5c6867a52f452e3e5fa77053ef19269101a8bc240c3a3bce9ad3d331c` |

A digest establishes which supplied survey was used; it does not make an unavailable survey readable.
The stable primary anchors below are therefore the repository-resolvable evidence layer.

## Stable primary and official anchors

| Source ID | Stable identifier | Source and relevant result |
| --- | --- | --- |
| `SRC-FDA-LCS` | <https://www.fda.gov/regulatory-information/search-fda-guidance-documents/label-comprehension-studies-nonprescription-drug-products> | FDA, *Label Comprehension Studies for Nonprescription Drug Products*, August 2010; a-priori objectives and objective comprehension/application tasks |
| `SRC-FDA-SS` | <https://www.fda.gov/regulatory-information/search-fda-guidance-documents/self-selection-studies-nonprescription-drug-products> | FDA, *Self-Selection Studies for Nonprescription Drug Products*, April 2013; correct decision criteria set before enrollment |
| `SRC-FDA-LADDER` | <https://www.fda.gov/drugs/types-applications/drug-application-process-nonprescription-drugs> | FDA consumer-study ladder: label comprehension, self-selection, actual use and human factors are distinct evidence claims |
| `SRC-RAND` | <https://www.rand.org/content/dam/rand/pubs/monograph_reports/2011/MR1269.pdf> | Fitch et al., *The RAND/UCLA Appropriateness Method User's Manual*, MR-1269-DG-XII/RE; independent rounds and retained disagreement |
| `SRC-WESTFALL` | <https://doi.org/10.1037/xge0000014> | Westfall, Kenny & Judd (2014), participant × stimulus/scenario sampling and power |
| `SRC-BRIER` | `DOI:10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2` | Brier (1950), proper probability score |
| `SRC-KK` | <https://doi.org/10.1037/a0016755> | Kahneman & Klein (2009), conditions for reliable intuitive expertise |
| `SRC-SZALMA` | <https://doi.org/10.1177/154193120805201944> | Szalma, Hancock & Quinn (2008), 125 sources / 827 effects; pressure speeds response and can reduce accuracy |
| `SRC-WESTBROOK` | <https://doi.org/10.1001/archinternmed.2010.65> | Westbrook et al. (2010), observed interruptions and medication-administration errors |
| `SRC-NANJI` | <https://doi.org/10.1136/amiajnl-2013-001813> | Nanji et al. (2014), 157,483 outpatient alerts; override and appropriateness differ sharply by alert class |
| `SRC-WOGALTER` | <https://doi.org/10.1177/001872088903100202> | Wogalter, Allison & McKenna (1989), compliance cost and social influence |
| `SRC-AKHAWE` | <https://www.usenix.org/conference/usenixsecurity13/technical-sessions/presentation/akhawe> | Akhawe & Felt (2013), large-scale browser warning field study |
| `SRC-SUNSHINE` | <https://www.usenix.org/legacy/event/sec09/tech/full_papers/sunshine.pdf> | Sunshine et al. (2009), SSL-warning understanding and behavior |
| `SRC-EATON` | <https://doi.org/10.1007/11555261_68> | Eaton, Plaisant & Drizd, *Visualizing Missing Data: Graph Interpretation User Study*; missing-as-zero experiment |
| `SRC-WORSTFIRST` | <https://doi.org/10.1287/mnsc.2022.4411> | Lewis, Feiler & Adner (2022), worst-first heuristic in conjunctive-risk intervention choice |
| `SRC-SR-BASE` | <https://doi.org/10.1145/3441852.3471202> | Sharif et al. (2021), screen-reader users’ online-visualization accuracy/time and relation-access barriers |
| `SRC-VOXLENS` | `CHI 2022, ACM DOI:10.1145/3491102.3517431` | Sharif et al., *VoxLens*; interactive summary/query/sonification evaluation |
| `SRC-SR-UNCERTAINTY` | <https://doi.org/10.1145/3597638.3614502> | Sharif, Zhong & Wang (2023), formative nonvisual uncertainty study |
| `SRC-ZONG` | <https://doi.org/10.1111/cgf.14519> | Zong et al. (2022), structure/navigation/description for screen-reader data access |
| `SRC-WCAG` | <https://www.w3.org/TR/WCAG22/> | W3C WCAG 2.2; programmatic relationships, keyboard access and focus order, not a comprehension result |
| `SRC-OECD` | <https://www.oecd.org/en/publications/do-adults-have-the-skills-they-need-to-thrive-in-a-changing-world_b263dc5d-en.html> | OECD Survey of Adult Skills 2023; adult numeracy distribution |
| `SRC-BNT` | <https://doi.org/10.1017/S1930297500001819> | Cokely et al., Berlin Numeracy Test; task-relevant statistical numeracy |
| `SRC-GOOGLE-SRE` | <https://sre.google/workbook/error-budget-policy/> | Google SRE Workbook, example error-budget policy; operational practice, not controlled UI-comprehension evidence |
| `SRC-HANLEY` | <https://pubmed.ncbi.nlm.nih.gov/6827763/> | Hanley & Lippman-Hand (1983), *If nothing goes wrong, is everything all right? Interpreting zero numerators*; zero-event “rule of three” diagnostic |

## `EXT-*` claim map

| EXT ID | Survey window | Stable anchors | Original evidence object | PolicyOS use and non-transfer boundary |
| --- | --- | --- | --- | --- |
| `EXT-01` | `SURV-01:26-114` | `SRC-OECD`, `SRC-BNT` plus the survey’s risk/uncertainty experiments | adult/professional numeracy and risk-display experiments; objective answers or incentivized choices | presentation can affect action; no winning format or effect size transfers to outer sets |
| `EXT-02` | `SURV-01:117-169` | `SRC-EATON` | 30-person missing-data graph experiment, 10 per condition | requires `unknown↔0` and `unknown↔missing` tests; does not estimate explicit epistemic-unknown prevalence |
| `EXT-03` | `SURV-01:5-23,96-114,182-244` | `SRC-EATON`, `SRC-WORSTFIRST` as adjacent anchors | negative review result over explicit unknown, pure set-valued uncertainty and UI incomparability | remains `deferred_open_problem`; adjacent evidence cannot close the direct human question |
| `EXT-04` | `SURV-01:247-295` | `SRC-GOOGLE-SRE` plus consumer-budget studies identified in the survey | consumer mental-accounting/depletion experiments and SRE policy practice | justifies allowance-versus-value contrasts; neither direction nor rate transfers to policy δ |
| `EXT-05` | `SURV-02:53-95` | `SRC-SZALMA`, `SRC-WESTBROOK` | mixed meta-analysis, simulation and observed work | test deadline and interruption conditions; target effect remains a hypothesis |
| `EXT-06` | `SURV-02:23-51` | `SRC-KK` and the survey’s fireground/AEGIS studies | field cognitive-task analysis of experienced operators | informs recognition-compatible design; does not prove causal superiority or PolicyOS validity |
| `EXT-07` | `SURV-02:177-260,262-377` | `SRC-WESTBROOK` plus pathology/speaking-up anchors in the survey | vignette, survey and field deferral/escalation practices | acquire/escalate/defer must be real transitions; downstream response and outcome remain separate |
| `EXT-08` | `SURV-03:25-70` | `SRC-NANJI` | alert exposures with typed override and sampled appropriateness review | supports eligible-opportunity/type denominators; no clinical override rate transfers |
| `EXT-09` | `SURV-03:64-126` | `SRC-WOGALTER`, `SRC-AKHAWE`, `SRC-SUNSHINE` | warning-cost experiment, browser field/lab evidence, hard-stop reviews | compliance cost/history and workaround are testable mechanisms; no universal friction threshold |
| `EXT-10` | `SURV-03:166-233` | `SRC-WORSTFIRST` | probability-judgment and intervention-allocation tasks | hypothesis generator only; deterministic all-must-pass, ordinal minimum and probability product stay distinct |
| `EXT-11` | `SURV-04:5-41` | `SRC-FDA-LCS`, `SRC-FDA-SS`, `SRC-FDA-LADDER` | official regulatory study methodology | confirms evidence-layer separation; labels are not authority UIs |
| `EXT-12` | `SURV-04:43-93` | `SRC-RAND` | structured expert appropriateness procedure | supports set-valued action truth and retained disagreement; does not appoint a panel |
| `EXT-13` | `SURV-04:209-282` | `SRC-BRIER`, `SRC-HANLEY` | scoring-rule/calibration mathematics and rare-event precision | supports Brier plus direct confident-and-wrong cells; governance threshold remains unappointed |
| `EXT-14` | `SURV-05:32-52,70-96` | `SRC-SR-BASE`, `SRC-VOXLENS`, `SRC-SR-UNCERTAINTY`, `SRC-ZONG` | controlled/mixed-method accessible-visualization studies | relation preservation transfers narrowly; direct refusal/δ/epoch action under AT remains open |
| `EXT-15` | `SURV-05:54-68,184-188` | `SRC-WCAG`, `SRC-SR-BASE` | normative standard plus negative behavioral boundary | conformance/reachability cannot close discovery or comprehension |
| `EXT-16` | `SURV-05:98-123` | `SRC-OECD`, `SRC-BNT` | population and professional numeracy instruments | measure and stratify target operators; no population percentage transfers |

## Quantitative discipline

Whenever the package quotes a number, the source ledger or survey window must retain:

```text
population
task/instrument
exposure or trial denominator
outcome definition
study design
source-domain limitation
```

No source-domain rate enters a PolicyOS prior or acceptance threshold. If a stable anchor above cannot
be resolved at verification time, the affected external claim falls to `not_established`; another
source is not silently substituted.
