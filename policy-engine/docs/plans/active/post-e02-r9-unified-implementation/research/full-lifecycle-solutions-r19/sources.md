# R19: первичные источники и пределы переноса

Технический или научный источник обосновывает конкретный приём; он не назначает PolicyOS authority, не доказывает работоспособность выбранного deployment и не делает библиотеку обязательной зависимостью. Версия, применимость и assumptions повторно проверяются при реализации. Ни один benchmark не становится универсальным порогом.

## S01-R01

[PROV-DM: The PROV Data Model](https://www.w3.org/TR/2013/REC-prov-dm-20130430/) · [S01](../../solutions/lifecycle-r19/S01.md)

**version_date.** W3C Recommendation, 30 April 2013

**standing.** Первичный доменно-нейтральный стандарт W3C для provenance.

**supports.** Q01,Q03,Q04: entities, activities, agents, time, derivation and extensible relations/collections support preserving signal and parent-basis lineage without collapsing history.

**limits.** Provenance assertions do not prove truth, issuer competence, legal continuity, evidence applicability, permission or commissioning authority; PROV does not choose PolicyOS owner/schema/cardinality.

## S01-R02

[PROV-O: The PROV Ontology](https://www.w3.org/TR/2013/REC-prov-o-20130430/) · [S01](../../solutions/lifecycle-r19/S01.md)

**version_date.** W3C Recommendation, 30 April 2013; latest page checked 2026-10-23

**standing.** Первичная спецификация W3C для interchange provenance; допускает application/domain specialization.

**supports.** Q01,Q03,Q04: reuse and locally specialize lineage rather than create a universal registry.

**limits.** Specialization does not give an edge mandate, identity or evidence semantics; RDF/OWL adoption is not required.

## S01-R03

[A Theory for Record Linkage](https://doi.org/10.1080/01621459.1969.10501049) · [S01](../../solutions/lifecycle-r19/S01.md)

**version_date.** Ivan P. Fellegi and Alan B. Sunter, JASA 64(328), 1969, pp. 1183–1210; online 10 April 2012

**standing.** Первичная peer-reviewed статья JASA о статистическом связывании записей.

**supports.** Q03: for stated features/error levels, linkage distinguishes link, non-link and possible-link/insufficient evidence; useful precedent for non-automatic duplicate triage.

**limits.** Its model does not determine political/legal identity, continuity, sponsor authority or claim applicability; features and error costs must be profile-specific.

## S02-R01

[SKOS Simple Knowledge Organization System Reference](https://www.w3.org/TR/skos-reference/) · [S02](../../solutions/lifecycle-r19/S02.md)

**standing.** W3C Recommendation, 2009-08-18

**supports.** closeMatch deliberately non-transitive; exactMatch transitive for broad retrieval interchangeability.

**limits.** SKOS is a retrieval vocabulary, not policy construct/population/effect equivalence.

## S02-R02

[A Theory for Record Linkage — Fellegi & Sunter](https://doi.org/10.1080/01621459.1969.10501049) · [S02](../../solutions/lifecycle-r19/S02.md)

**standing.** JASA 64(328), 1969, pp.1183–1210

**supports.** Match, non-match and insufficient-evidence decisions under stipulated error levels.

**limits.** Record-pair error theory does not establish target population, legal identity or estimand validity.

## S02-R03

[Evaluating bias due to data linkage error in electronic healthcare records — Harron et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC4015706/) · [S02](../../solutions/lifecycle-r19/S02.md)

**standing.** BMC Medical Research Methodology 14:36, 2014-03-05

**supports.** Differential linkage error, low match rate and identifier error changed infection estimates; propagate link uncertainty to outcome.

**limits.** Specific pediatric health setting; assumes match probabilities accurate; no universal method/threshold.

## S02-R04

[U.S. Census Bureau 2020 Relationship Files](https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.2020.html) · [S02](../../solutions/lifecycle-r19/S02.md)

**standing.** Official geography relationships over time and among geography types

**supports.** Relationship files help compare boundaries; 2020 files omit population/housing counts, so IDs/geometric relations alone give no variable weights.

**limits.** U.S. census geographies only; relations are not weights for arbitrary outcomes/effects.

## S02-R05

[Using Big Data to Emulate a Target Trial — Hernán & Robins](https://doi.org/10.1093/aje/kwv254) · [S02](../../solutions/lifecycle-r19/S02.md)

**standing.** AJE 183(8), published 2016-03-18

**supports.** Causal comparison must specify target trial/strategies and align time zero, treatment and follow-up.

**limits.** Comparative-effectiveness framework; does not prove exchangeability/positivity or define all calendars.

## S02-R06

[Theory and pragmatics of the tz code and data](https://www.iana.org/time-zones/theory) · [S02](../../solutions/lifecycle-r19/S02.md)

**standing.** IANA community-maintained tz documentation, checked 2026-10-23

**supports.** Civil rules change politically; historical locality/precision is limited; tz is not authoritative.

**limits.** Zone conversion only; not fiscal periods, legal dates or exposure definitions.

## S02-R07

[Distributed Snapshots — Chandy & Lamport](https://doi.org/10.1145/214451.214456) · [S02](../../solutions/lifecycle-r19/S02.md)

**standing.** ACM TOCS 3(1), 1985, pp.63–75

**supports.** A coherent distributed snapshot relies on relations among process/channel events, not maximum timestamp.

**limits.** Distributed-process model; does not establish consistency of independent datasets or estimands.

## S02-R08

[Ecological Regression with Partial Identification — Jiang et al.](https://doi.org/10.1017/pan.2019.19) · [S02](../../solutions/lifecycle-r19/S02.md)

**standing.** Political Analysis 28(1), 2020; online 2019-08-02

**supports.** For a specified 2x2 ecological inference class, real aggregate margins can support bounds rather than unjustified point estimates.

**limits.** Specific ecological model/estimand; not general subgroup causal bounds.

## S02-R09

[Accuracy of areal interpolation methods for count data — Do et al.](https://doi.org/10.1016/j.spasta.2015.07.005) · [S02](../../solutions/lifecycle-r19/S02.md)

**standing.** Spatial Statistics 14, 2015, pp.412–438

**supports.** Finite-distance accuracy depends on target size and auxiliary-variable relation; no considered method always dominates.

**limits.** Studied count-data methods only; demographic weights do not allocate other outcomes.

## S02-R10

[Measurement Invariance, Factor Analysis and Factorial Invariance — Meredith](https://doi.org/10.1007/BF02294825) · [S02](../../solutions/lifecycle-r19/S02.md)

**standing.** Psychometrika 58(4), 1993, pp.525–543

**supports.** Comparisons of latent constructs require stronger invariance conditions than similar item labels.

**limits.** Factor-model framework, not a universal policy-construct test.

## S03-R01

[PRISMA-S: an extension to PRISMA for Reporting Literature Searches (Rethlefsen et al., 2021)](https://doi.org/10.1186/s13643-020-01542-z) · [S03](../../solutions/lifecycle-r19/S03.md)

**standing.** Peer-reviewed reporting extension; 16 checklist items.

**supports.** Captures databases/platforms, methods, exact strategies, limits, update dates, review, counts and deduplication.

**limits.** Reproducibility is not evidence of representativeness, source completeness or external absence; systematic-review scope.

## S03-R02

[PRESS Peer Review of Electronic Search Strategies: 2015 Guideline Statement (McGowan et al., published 2016)](https://doi.org/10.1016/j.jclinepi.2016.01.021) · [S03](../../solutions/lifecycle-r19/S03.md)

**standing.** Evidence-based guideline from review, expert survey and consensus.

**supports.** Specialist reviews question translation, Boolean logic, headings, text words, syntax and limits/filters before execution.

**limits.** Checks the search string, not source coverage, seed representativeness, execution, access rights or claim support.

## S03-R03

[A practical guide to evaluating sensitivity of literature search strings using relative recall (Lagisz et al., 2025)](https://doi.org/10.1017/rsm.2024.6) · [S03](../../solutions/lifecycle-r19/S03.md)

**standing.** Peer-reviewed method paper with worked database examples; RSM 16(1).

**supports.** Compare query hits with preselected known-relevant items actually indexed by each source; use misses to refine search or expose coverage gaps.

**limits.** Benchmark representativeness and absolute recall are unknown; small or circular seeds are biased/imprecise.

## S03-R04

[Cochrane Handbook, Chapter 4: Searching for and selecting studies (v6.5.1; updated March 2025)](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04) · [S03](../../solutions/lifecycle-r19/S03.md)

**standing.** Official Cochrane Information Retrieval Methods Group handbook.

**supports.** Covers source choice, sensitivity/precision, limits, search review/stopping, and reports versus underlying studies.

**limits.** Intervention-review context; no fixed source set guarantees coverage for other fields, languages, rights or institutional records.

## S03-R05

[Cochrane Handbook, Chapter 5: Collecting data (chapter last updated October 2019)](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-05) · [S03](../../solutions/lifecycle-r19/S03.md)

**standing.** Official Cochrane methods handbook chapter (v6.5 cited 2024).

**supports.** The study, not each report, is the unit of interest; link multiple reports while retaining their distinct information.

**limits.** Bibliographic linkage does not determine covariance or claim-specific statistical independence.

## S03-R06

[Modeling dependent effect sizes with three-level meta-analyses (Cheung, 2014)](https://doi.org/10.1037/a0032968) · [S03](../../solutions/lifecycle-r19/S03.md)

**standing.** Peer-reviewed methods paper with two empirical illustrations.

**supports.** Models effect sizes nested in known studies/clusters rather than treating every report or outcome as independent.

**limits.** Hierarchy/covariance assumptions must match evidence; it cannot find unknown cohort membership.

## S03-R07

[Robust variance estimation in meta-regression with dependent effect sizes (Hedges, Tipton & Johnson, 2010; erratum DOI 10.1002/jrsm.17)](https://doi.org/10.1002/jrsm.5) · [S03](../../solutions/lifecycle-r19/S03.md)

**standing.** Peer-reviewed statistical method and simulation.

**supports.** Can model correlated estimates within known clusters without specifying exact within-cluster covariance; simulation suggested 20-40 clusters in their settings.

**limits.** Requires identified clusters and adequate sample assumptions; not a way to discover unknown overlap or certify any cluster count.

## S03-R08

[A general framework for meta-analyzing dependent studies with overlapping subjects in association mapping (2016)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4986332/) · [S03](../../solutions/lifecycle-r19/S03.md)

**standing.** Peer-reviewed original method with GWAS examples.

**supports.** Shared controls/participants can create dependence and spurious results; overlap-adjusted covariance can use evidenced overlap.

**limits.** GWAS-specific; does not solve unknown lineage or generalize as an identity-resolution system.

## S03-R09

[U.S. Census Bureau Statistical Quality Standard D3: Producing Measures and Indicators of Nonsampling Error (revised 2021)](https://www.census.gov/about/policies/quality/standards/standardd3.html) · [S03](../../solutions/lifecycle-r19/S03.md)

**standing.** Official standard for Census Bureau products.

**supports.** Separates coverage, nonresponse, processing and measurement error; calls for indicators, studies, testing and documentation.

**limits.** Agency-specific thresholds/obligations are not universal; indicators alone do not prove unbiasedness or transport.

## S03-R10

[Nonresponse Rates and Nonresponse Bias in Household Surveys (Groves, 2006)](https://doi.org/10.1093/poq/nfl033) · [S03](../../solutions/lifecycle-r19/S03.md)

**standing.** Peer-reviewed methodological synthesis of empirical evidence and assessment designs.

**supports.** Overall response rate alone does not predict bias for a particular estimate; bias varies by statistic and participation-variable relation.

**limits.** Focuses on U.S./Western European household, mostly one-time surveys; no design resolves unobserved nonresponse.

## S03-R11

[Testing Measurement Invariance in Longitudinal Data with Ordered-Categorical Measures (Liu et al., 2017; online 2016)](https://doi.org/10.1037/met0000075) · [S03](../../solutions/lifecycle-r19/S03.md)

**standing.** Peer-reviewed methods/tutorial paper with empirical example and sensitivity procedure.

**supports.** Tests whether repeated measures retain construct/metric across waves, including categorical indicators and practical invariance violations.

**limits.** Does not establish frame representativeness, causal transport or unmeasured population drift; relies on model assumptions.

## S03-R12

[Estimation of Mode Effects in the Health and Retirement Study Using Measurement Models (Cernat, Couper & Ofstedal, 2016)](https://doi.org/10.1093/jssam/smw021) · [S03](../../solutions/lifecycle-r19/S03.md)

**standing.** Peer-reviewed quasi-experimental study with randomized mode assignment/reversal.

**supports.** Found systematic mode differences on two panel measures; bridge/measurement models can separate mode from change.

**limits.** Study- and instrument-specific; does not imply every mode change shifts every measure.

## S04-R01

[Vienna Convention on the Law of Treaties, 1969, UNTS 1155 p.331](https://treaties.un.org/doc/Publication/UNTS/Volume%201155/volume-1155-I-18232-English.pdf) · [S04](../../solutions/lifecycle-r19/S04.md)

**standing.** Official UN treaty text; Article 1 covers treaties between States.

**supports.** Arts.30-34 scope successive treaties/parties/third States; Arts.31-33 interpretation and authentic languages.

**limits.** Not a universal domestic-law hierarchy or direct-effect rule; establish parties, scope and applicable law.

## S04-R02

[UN Treaty Collection: VCLT status at 2026-10-23](https://treaties.un.org/pages/ViewDetailsIII.aspx?chapter=23&mtdsg_no=XXIII-1&src=IND) · [S04](../../solutions/lifecycle-r19/S04.md)

**standing.** Official UN Secretary-General depositary status page, current at the stated date.

**supports.** Party status and deposited reservations/declarations/objections need treaty-, party- and time-specific evidence.

**limits.** Covers UN-SG depositary treaties; status does not decide interpretation, domestic effect or addressee scope.

## S04-R03

[Statute of the International Court of Justice, 1945, Arts.38-41](https://www.icj-cij.org/statute) · [S04](../../solutions/lifecycle-r19/S04.md)

**standing.** Constitutive statute governing the Court's jurisdiction and function.

**supports.** Art.38 is the Court's source taxonomy; Art.41 shows provisional relief is a competent court act in a specific case.

**limits.** Not a universal source ranking or precedent rule; no actual judgment/order is asserted here.

## S04-R04

[ILC Draft Conclusions on Identification of Customary International Law, 2018, with commentaries](https://legal.un.org/ilc/texts/instruments/english/commentaries/1_13_2018.pdf) · [S04](../../solutions/lifecycle-r19/S04.md)

**standing.** Adopted by ILC on second reading and commended for attention by the UN General Assembly; non-treaty guidance.

**supports.** Custom requires practice plus acceptance as law; particular custom may be limited to a group; resolutions alone do not create custom.

**limits.** Methodological guidance, not a finding that any specific custom exists; requires case-specific evidence and review.

## S04-R05

[ILC Study Group Conclusions on Fragmentation of International Law, 2006](https://legal.un.org/ilc/texts/instruments/english/draft_articles/1_9_2006.pdf) · [S04](../../solutions/lifecycle-r19/S04.md)

**standing.** Collective ILC Study Group conclusions noted by the Commission and UNGA; non-treaty study.

**supports.** Special-regime conflicts and tools such as lex specialis require contextual analysis; institutional competence is left to institutions.

**limits.** Concerns international law, not a resolver for every domestic/international conflict or universal hierarchy.

## S04-R06

[ILC Draft Conclusions on Subsequent Agreements and Practice in Treaty Interpretation, 2018](https://legal.un.org/ilc/texts/instruments/english/commentaries/1_11_2018.pdf) · [S04](../../solutions/lifecycle-r19/S04.md)

**standing.** Adopted by ILC on second reading and commended for attention; non-treaty guidance on treaty interpretation.

**supports.** Subsequent agreement/practice interacts with other interpretive means and is not automatically conclusive.

**limits.** Does not give general force to every agency guide, expert view or soft-law text.

## S04-R07

[TFEU Article 267, OJ C 326, 26.10.2012](https://eur-lex.europa.eu/eli/treaty/tfeu_2012/art_267/oj/eng) · [S04](../../solutions/lifecycle-r19/S04.md)

**standing.** EU treaty rule on preliminary references by courts of Member States.

**supports.** Referral scope and duties depend on a defined regional institutional procedure.

**limits.** Regional example; referral alone does not establish suspension of the underlying act or case.

## S04-R08

[Aarhus Convention, 1998, official UNECE text](https://unece.org/environment-policy/public-participation/aarhus-convention/text) · [S04](../../solutions/lifecycle-r19/S04.md)

**standing.** Official treaty text, UNTS 2161 p.447; applicability depends on parties and covered environmental procedure.

**supports.** Arts.6-9 specify different participation/access procedures for bounded decision classes.

**limits.** Not a universal consultation template, representation rule or mandate outside its scope.

## S05-R01

[Arrow, A Difficulty in the Concept of Social Welfare, JPE 58(4), 1950](https://www.journals.uchicago.edu/doi/10.1086/256963) · [S05](../../solutions/lifecycle-r19/S05.md)

**standing.** Peer-reviewed original theorem.

**supports.** No hidden universal aggregator follows from general conflicting preferences.

**limits.** Depends on specified axioms/domain; does not invalidate a scoped mandate.

**questions.** - R18-D05-Q01

## S05-R02

[OECD Guidelines for Citizen Participation Processes, 2022](https://www.oecd.org/en/publications/oecd-guidelines-for-citizen-participation-processes_f765caf6-en.html) · [S05](../../solutions/lifecycle-r19/S05.md)

**standing.** Official guidance.

**supports.** Plan outcome, inclusion, transparency, privacy, resources and feedback.

**limits.** Not law, mandate, representation proof or neutrality test.

**questions.** - R18-D05-Q02

- R18-D05-Q03

## S05-R03

[TCPS 2 (2022), ch. 9, Indigenous peoples of Canada](https://ethics.gc.ca/eng/tcps2-eptc2_2022_chapter9-chapitre9.html?wbdisable=true) · [S05](../../solutions/lifecycle-r19/S05.md)

**standing.** Official Canadian research policy.

**supports.** Shows source-specific community rules beside individual permission.

**limits.** Narrow scope; no universal precedence.

## S05-R04

[Carroll et al., CARE Principles for Indigenous Data Governance, DSJ 19:43, 2020](https://datascience.codata.org/en/articles/dsj-2020-043) · [S05](../../solutions/lifecycle-r19/S05.md)

**standing.** Primary publication.

**supports.** Supports collective benefit/control/responsibility/ethics for Indigenous data.

**limits.** Not generic permission or weight.

## S05-R05

[OECD, Managing Conflict of Interest in the Public Service, 2003](https://www.oecd.org/content/dam/oecd/en/publications/reports/2004/01/managing-conflict-of-interest-in-the-public-service_g1gh3c56/9789264104938-en.pdf) · [S05](../../solutions/lifecycle-r19/S05.md)

**standing.** Official guidance/country review.

**supports.** Examples: updated disclosure, recusal, restriction, reassignment and independent review.

**limits.** Public-service scope; not universal COI code.

## S05-R06

[Sigelman, Question-Order Effects on Presidential Popularity, POQ 45(2), 1981](https://academic.oup.com/poq/article-abstract/45/2/199/1927128) · [S05](../../solutions/lifecycle-r19/S05.md)

**standing.** Primary survey experiment.

**supports.** Question order changed opinionation, not response direction.

**limits.** One survey; not proof of manipulation or neutral order.

**questions.** - R18-D05-Q03

## S05-R07

[Kane, Validating the Interpretations and Uses of Test Scores, JEM 50(1), 2013](https://onlinelibrary.wiley.com/doi/abs/10.1111/JEDM.12000) · [S05](../../solutions/lifecycle-r19/S05.md)

**standing.** Primary methodology paper.

**supports.** Validate the specific interpretation/use and its inferences/consequences.

**limits.** Test-score method; analogy does not authorize need/rubric.

**questions.** - R18-D21-Q01

## S06-R01

[Collier, Understanding Process Tracing, PS: Political Science & Politics 44(4), 2011](https://doi.org/10.1017/S1049096511001429) · [S06](../../solutions/lifecycle-r19/S06.md)

**standing.** Первичная методическая статья.

**supports.** Диагностические наблюдения и последовательность внутри случая могут поддержать локальное причинное объяснение.

**limits.** Не даёт среднего эффекта или переноса на иные случаи без отдельного warrant.

## S06-R02

[Verma & Pearl, Equivalence and Synthesis of Causal Models, UCLA TR R-150, 1991; revision of UAI 1990](https://ftp.cs.ucla.edu/tech-report/1991-reports/910020.pdf) · [S06](../../solutions/lifecycle-r19/S06.md)

**standing.** Первичная статья авторов, UCLA.

**supports.** Графы могут быть эквивалентны при доступных наблюдениях; различимы только относительно данных/экспериментов.

**limits.** Не гарантирует, что сохранённый model set включает истину.

## S06-R03

[Pearl, Causal Diagrams for Empirical Research, Biometrika 82(4), 1995](https://doi.org/10.1093/biomet/82.4.669) · [S06](../../solutions/lifecycle-r19/S06.md)

**standing.** Первичная методическая статья.

**supports.** При данных graph assumptions определить идентифицируемость и нужные дополнительные данные/эксперименты.

**limits.** Не доказывает правильность или полноту assumptions/graph.

## S06-R04

[Manski, Nonparametric Bounds on Treatment Effects, AER 80(2), 1990, 319–323](https://ipcid.org/evaluation/outros_temas/Manski%20-%20Nonparametric%20Bounds.pdf) · [S06](../../solutions/lifecycle-r19/S06.md)

**standing.** Копия первичной статьи.

**supports.** Частичная идентификация даёт границы вместо ложной точечной оценки.

**limits.** Bounds могут быть широкими; статья не решает проблему selective reporting.

## S06-R05

[Bareinboim & Pearl, Causal Inference and the Data-Fusion Problem, PNAS 113(27), 2016](https://doi.org/10.1073/pnas.1510507113) · [S06](../../solutions/lifecycle-r19/S06.md)

**standing.** Первичная методическая статья.

**supports.** Для source/target и режимов нужны явные selection/transport assumptions.

**limits.** Формализм сам не подтверждает сопоставимость источника и целевой популяции.

## S06-R06

[King et al., Enhancing the Validity and Cross-Cultural Comparability of Measurement, APSR 98(2), 2004](https://doi.org/10.1017/S000305540400108X) · [S06](../../solutions/lifecycle-r19/S06.md)

**standing.** Первичная методическая статья.

**supports.** Anchoring vignettes могут выявлять различия порогов самооценки между группами.

**limits.** Требует vignette equivalence и response consistency; не валидирует любой новый режим.

## S06-R07

[Chan et al., Empirical Evidence for Selective Reporting of Outcomes, JAMA 291(20), 2004](https://doi.org/10.1001/jama.291.20.2457) · [S06](../../solutions/lifecycle-r19/S06.md)

**standing.** Первичное сравнение протоколов и публикаций.

**supports.** В исследованной когорте обнаружено выборочное/неполное reporting внутри опубликованных испытаний.

**limits.** Частоту смещения нельзя переносить автоматически на иные области.

## S06-R08

[Turner et al., Selective Publication of Antidepressant Trials, NEJM 358, 2008](https://doi.org/10.1056/NEJMsa065779) · [S06](../../solutions/lifecycle-r19/S06.md)

**standing.** Первичный разбор зарегистрированных и опубликованных испытаний.

**supports.** Учет неопубликованных испытаний изменил apparent efficacy в изученной области.

**limits.** Конкретные препараты и реестры, не универсальная correction.

## S06-R09

[Cochrane Handbook v6.5, Chapter 13: Missing Evidence, updated 2024](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-13) · [S06](../../solutions/lifecycle-r19/S06.md)

**standing.** Официальное руководство.

**supports.** ROB-ME, inception cohorts, протоколы и result matrix дают путь оценки missing results.

**limits.** Оценка не восстанавливает неизвестный исход; методики ограничены для qualitative/non-standard synthesis.

## S06-R10

[Gneiting & Raftery, Strictly Proper Scoring Rules, JASA 102(477), 2007](https://doi.org/10.1198/016214506000001437) · [S06](../../solutions/lifecycle-r19/S06.md)

**standing.** Первичная методическая статья.

**supports.** Proper scores/coverage позволяют оценивать probabilistic forecasts по наблюдаемым исходам.

**limits.** Forecast calibration не устанавливает причинность, transport или authority.

## S07-R01

[Survey of Multifidelity Methods in Uncertainty Propagation, Inference, and Optimization — Peherstorfer et al., SIAM Review 60(3), 2018](https://epubs.siam.org/doi/10.1137/16M1082469) · [S07](../../solutions/lifecycle-r19/S07.md)

**standing.** Peer-reviewed survey.

**supports.** Taxonomy: cheap fidelity guides calls; target guarantees still need target accuracy.

**limits.** Not causal-model adequacy or policy-threshold evidence.

**questions.** - R18-D07-Q01

## S07-R02

[Multi-Fidelity Bayesian Optimization with Unreliable Information Sources — Mikkola et al., AISTATS/PMLR 206, 2023](https://proceedings.mlr.press/v206/mikkola23a.html) · [S07](../../solutions/lifecycle-r19/S07.md)

**standing.** Primary peer-reviewed paper.

**supports.** GP multi-fidelity BO regret bound vs vanilla BO with unreliable sources; guides expensive calls.

**limits.** Regret is not a candidate hard-floor certificate or model probability.

**questions.** - R18-D07-Q01

## S07-R03

[Certified Multi-Fidelity Zeroth-Order Optimization — de Montbrun, Gerchinovitz, 2023](https://arxiv.org/abs/2308.00978) · [S07](../../solutions/lifecycle-r19/S07.md)

**standing.** Primary theoretical preprint.

**supports.** Data-driven optimization-error bound under Lipschitz objective and noise assumptions.

**limits.** One objective; not model-set or normative validity.

**questions.** - R18-D07-Q01

## S07-R04

[Practical error bounds for a non-intrusive bi-fidelity approach to parametric/stochastic model reduction — Hampton et al., JCP 368, 2018](https://doi.org/10.1016/j.jcp.2018.04.015) · [S07](../../solutions/lifecycle-r19/S07.md)

**standing.** Primary peer-reviewed paper.

**supports.** Profile-specific low/high-fidelity bounds for parametric/stochastic model reduction.

**limits.** Assumptions do not transfer to other causal structures or targets.

**questions.** - R18-D07-Q01

## S07-R05

[NIST Digital Library of Mathematical Functions §3.1(ii), Interval Arithmetic](https://dlmf.nist.gov/3.1.ii) · [S07](../../solutions/lifecycle-r19/S07.md)

**standing.** Official NIST reference.

**supports.** Directed rounding gives inclusion bounds for rounding error.

**limits.** Does not bound surrogate, sampling or identification error.

**questions.** - R18-D07-Q01

- R18-D07-Q02

## S07-R06

[Shapley Effects for Global Sensitivity Analysis: Theory and Computation — Song, Nelson, Staum, SIAM/ASA JUQ 4(1), 2016](https://epubs.siam.org/doi/10.1137/15M1048070) · [S07](../../solutions/lifecycle-r19/S07.md)

**standing.** Primary peer-reviewed paper.

**supports.** Shapley effects allocate variance across inputs and account for interactions.

**limits.** Chosen distribution and subset evaluations; not a revision cause.

**questions.** - R18-D07-Q02

## S07-R07

[The Many Shapley Values for Model Explanation — Sundararajan, Najmi, ICML/PMLR 119, 2020](https://proceedings.mlr.press/v119/sundararajan20b.html) · [S07](../../solutions/lifecycle-r19/S07.md)

**standing.** Primary peer-reviewed method paper.

**supports.** Baseline, distribution and context change Shapley values; axioms do not select a game.

**limits.** ML attribution, not a policy-revision explainer.

**questions.** - R18-D07-Q02

## S07-R08

[The Counterfactual-Shapley Value: Attributing Change in System Metrics — Sharma, Li, Jiao, 2022](https://arxiv.org/abs/2208.08399) · [S07](../../solutions/lifecycle-r19/S07.md)

**standing.** Primary workshop/preprint, not a standard.

**supports.** SCM counterfactuals allocate one observed system-metric change.

**limits.** Requires useful structural equations; software revision is not a world intervention.

**questions.** - R18-D07-Q02

## S07-R09

[NIST/SEMATECH e-Handbook §7.4.7.3, Bonferroni's method](https://itl.nist.gov/div898/handbook/prc/section4/prc473.htm) · [S07](../../solutions/lifecycle-r19/S07.md)

**standing.** Official statistical reference.

**supports.** Finite-family union bound gives simultaneous coverage ≥1−sum of miss rates, without dependence assumptions.

**limits.** Needs valid marginals; not a fix for peeking, postselection or omitted cells.

**questions.** - R18-D07-Q01

## S07-R10

[Time-uniform, nonparametric, nonasymptotic confidence sequences — Howard et al., Annals of Statistics 49(2), 2021](https://doi.org/10.1214/20-AOS1991) · [S07](../../solutions/lifecycle-r19/S07.md)

**standing.** Primary peer-reviewed paper.

**supports.** Confidence sequences provide time-uniform coverage under stated conditions.

**limits.** Time-uniform alone is not joint branch/constraint or selection coverage.

**questions.** - R18-D07-Q01

## S08-R01

[Mouret & Clune, Illuminating search spaces by mapping elites (2015)](https://arxiv.org/abs/1504.04909) · [S08](../../solutions/lifecycle-r19/S08.md)

**standing.** Primary research paper introducing MAP-Elites.

**supports.** A quality-diversity archive preserves strong candidates across an explicitly selected behavior-descriptor space.

**limits.** Coverage depends on the chosen descriptors and discretization; this does not establish complete or policy-relevant axes.

**used_for.** - R18-D08-Q01

- R18-D08-Q02

- R18-D08-Q05

## S08-R02

[Lehman & Stanley, Abandoning Objectives: Evolution Through the Search for Novelty Alone (2011)](https://doi.org/10.1162/EVCO_a_00025) · [S08](../../solutions/lifecycle-r19/S08.md)

**standing.** Primary peer-reviewed research paper.

**supports.** Novelty search can find useful paths when an explicit objective misdirects bounded computational search.

**limits.** Novelty is representation-dependent and can produce irrelevant candidates; it is not a policy-quality or authority measure.

**used_for.** - R18-D08-Q02

- R18-D08-Q05

## S08-R03

[Kent, Branke, Gaier & Mouret, A Discretization-free Metric for Assessing Quality Diversity Algorithms (GECCO 2022 QD stream)](https://www.research.autodesk.com/publications/a-discretization-free-metric-for-assessing-quality-diversity-algorithms/) · [S08](../../solutions/lifecycle-r19/S08.md)

**standing.** Primary conference research, author research record.

**supports.** Coverage and QD-score can miss a decision maker's interest in particular continuous descriptor values.

**limits.** Assumes target descriptors and tolerances are known; cannot discover missing policy axes or authorize who chooses a target.

**used_for.** - R18-D08-Q02

## S08-R04

[Astudillo & Frazier, Multi-attribute Bayesian optimization with interactive preference learning (2020)](https://proceedings.mlr.press/v108/astudillo20a.html) · [S08](../../solutions/lifecycle-r19/S08.md)

**standing.** Primary peer-reviewed PMLR paper.

**supports.** Interactive preference learning can retain options while eliciting decision-maker input instead of assuming an initial point utility.

**limits.** A specified decision maker in technical black-box optimization; it does not resolve collective preferences or mandate.

## S08-R05

[Ungredda & Branke, When to elicit preferences in multi-objective Bayesian optimization (GECCO '23 Companion, 2023)](https://doi.org/10.1145/3583133.3596342) · [S08](../../solutions/lifecycle-r19/S08.md)

**standing.** Primary peer-reviewed conference paper.

**supports.** Under an explicit total budget, the method chooses between another evaluation and a preference query, including which pair to show.

**limits.** Assumes a single decision maker's utility and returns one preferred solution; use only where that owner's authority is real.

## S08-R06

[Grunert da Fonseca, Fonseca & Hall, Inferential Performance Assessment of Stochastic Optimisers and the Attainment Function (EMO 2001)](https://doi.org/10.1007/3-540-44719-9_15) · [S08](../../solutions/lifecycle-r19/S08.md)

**standing.** Primary research paper on stochastic multi-objective optimizer comparison.

**supports.** Independent repetitions and attainment functions characterize variation in whole Pareto outcome sets.

**limits.** Numeric objective-space variation is not semantic coverage, causal validity, policy-case independence or social preference.

## S08-R07

[Samson, Wirth & Rickard, The value of information from multiple sources of uncertainty in decision analysis (1989)](https://doi.org/10.1016/0377-2217(89)90163-X) · [S08](../../solutions/lifecycle-r19/S08.md)

**standing.** Primary theory/methodology paper.

**supports.** Values of information are generally non-additive across sources because decision value is nonlinear.

**limits.** Applies to a specified decision model; does not create common units for compute, money, human attention, rights and public outcomes.

## S08-R08

[Martí, García, Berlanga & Molina, A stopping criterion for multi-objective optimization evolutionary algorithms (2016)](https://doi.org/10.1016/j.ins.2016.07.025) · [S08](../../solutions/lifecycle-r19/S08.md)

**standing.** Primary peer-reviewed optimizer stopping research.

**supports.** A numerical method can stop its own run using tested progress evidence.

**limits.** Method convergence/stagnation does not prove space exhaustion, policy admissibility or absence of a useful mechanism.

## S08-R09

[NIST/SEMATECH e-Handbook §5.2.1.2, One-Factor-at-a-Time Designs](https://www.itl.nist.gov/div898/handbook/pri/section2/pri212.htm) · [S08](../../solutions/lifecycle-r19/S08.md)

**standing.** Official statistical-methods handbook.

**supports.** OFAT tests main effects, not interactions; one factor’s effect may depend on another.

**limits.** Pair screens cover only tested settings, not higher-order interactions or policy robustness.

**used_for.** - R18-D08-Q05

## S09-R01

[ICH Harmonised Guideline: Guideline for Good Clinical Practice, E6(R3), Step 4 Final version](https://database.ich.org/sites/default/files/ICH_E6%28R3%29_Step4_FinalGuideline_2025_0106.pdf) · [S09](../../solutions/lifecycle-r19/S09.md)

**standing.** ICH Step 4 adopted 2025-01-06; local adoption varies.

**supports.** Separates sponsor/site/investigator/IRB/regulator duties and protocol-specific approvals, amendments, deviations, termination.

**limits.** Clinical human trials; not general research law or reuse rights.

## S09-R02

[ICH E9(R1): Addendum on Estimands and Sensitivity Analysis in Clinical Trials](https://database.ich.org/sites/default/files/E9-R1_Step4_Guideline_2019_1203.pdf) · [S09](../../solutions/lifecycle-r19/S09.md)

**standing.** ICH Step 4 adopted 2019-11-20.

**supports.** Aligns estimand/design/conduct/analysis; specifies intercurrent-event strategy and sensitivity analysis.

**limits.** Clinical methods; no universal deviation threshold.

## S09-R03

[Adaptive Design Clinical Trials for Drugs and Biologics: Guidance for Industry, December 2019](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/adaptive-design-clinical-trials-drugs-and-biologics-guidance-industry) · [S09](../../solutions/lifecycle-r19/S09.md)

**standing.** FDA Final Level 1, Dec 2019; nonbinding.

**supports.** Prespecifies adaptation and trial-specific method/operating-characteristic checks.

**limits.** Drug/biologic trials; not universal procedure.

## S09-R04

[Protocol Registration Data Element Definitions for Interventional and Observational Studies](https://clinicaltrials.gov/policy/protocol-definitions) · [S09](../../solutions/lifecycle-r19/S09.md)

**standing.** Official definitions; no page version/date stated.

**supports.** Fields cover IDs, status, design, outcomes, responsible party, documents/history.

**limits.** Registry assertion does not verify conduct, effect or global coverage.

## S09-R05

[WHO Trial Registration Data Set, version 1.3.1](https://www.who.int/tools/clinical-trials-registry-platform/network/who-data-set) · [S09](../../solutions/lifecycle-r19/S09.md)

**standing.** WHO official minimum TRDS v1.3.1.

**supports.** 24 fields include IDs, protocol/version, outcomes/results, IPD-sharing.

**limits.** Minimum set proves neither rights nor completeness/independence.

## S09-R06

[Lakens, Equivalence Tests: A Practical Primer for t Tests, Correlations, and Meta-Analyses](https://journals.sagepub.com/doi/10.1177/1948550617697177) · [S09](../../solutions/lifecycle-r19/S09.md)

**standing.** Peer-reviewed, first online 2017-05-05.

**supports.** Nonsignificance is not absence; fitting TOST needs prespecified smallest-effect bounds.

**limits.** No universal margin; method must fit.

## S09-R07

[Heath et al., Simulating Study Data to Support Expected Value of Sample Information Calculations](https://journals.sagepub.com/doi/10.1177/0272989X211026292) · [S09](../../solutions/lifecycle-r19/S09.md)

**standing.** Peer-reviewed tutorial, online 2021; journal 2022.

**supports.** EVSI compares current best utility with expectation after simulated study data; model relevant missingness/deviations.

**limits.** Needs decision/uncertainty/target/horizon/data law; expectation is not guarantee.

## S09-R08

[Bhattacharjya, Eidsvik, and Mukerji, The Value of Information in Portfolio Problems with Dependent Projects](https://pubsonline.informs.org/doi/10.1287/deca.2013.0277) · [S09](../../solutions/lifecycle-r19/S09.md)

**standing.** Peer-reviewed Decision Analysis, online 2013-12-02.

**supports.** Dependence changes portfolio value; use joint/conditional rather than summed standalone values.

**limits.** Stylized Gaussian example, not scheduler.

## S09-R09

[Chan et al., Empirical Evidence for Selective Reporting of Outcomes in Randomized Trials](https://pubmed.ncbi.nlm.nih.gov/15161896/) · [S09](../../solutions/lifecycle-r19/S09.md)

**standing.** Original JAMA cohort study, 2004.

**supports.** Protocol/publication comparison found incomplete/discrepant outcomes.

**limits.** One clinical cohort; discrepancy alone does not establish bias.

## S09-R10

[WHO ICTRP: Reporting on Findings / Public Disclosure of Clinical Trial Results](https://www.who.int/tools/clinical-trials-registry-platform/reporting-on-findings) · [S09](../../solutions/lifecycle-r19/S09.md)

**standing.** Official WHO results guidance, updated 2025.

**supports.** Registry results/negative-result reporting affect evidence-base completeness.

**limits.** Clinical trials; no case-specific rights or global completeness.

## S10-R01

[Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing (Benjamini & Hochberg, 1995)](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x) · [S10](../../solutions/lifecycle-r19/S10.md)

**standing.** Первичная методологическая статья, JRSS B 57(1), 289–300 (1995).

**supports.** FDR контролирует ожидаемую долю ложных отклонений среди отвергнутых гипотез при assumptions выбранной процедуры; это не мощность и не false-negative bound.

**limits.** Не валидирует текущий OnlineFDRController; нужны принятый алгоритм, valid p/e-values, полная ordered test family и условия зависимости.

**question_ids.** - R18-D10-Q01

## S10-R02

[Inference and Missing Data (Rubin, 1976)](https://doi.org/10.1093/biomet/63.3.581) · [S10](../../solutions/lifecycle-r19/S10.md)

**standing.** Первичная методологическая статья, Biometrika 63(3), 581–592 (1976).

**supports.** Игнорировать missing-data process допустимо только при заданных Rubin условиях; вывод может быть условен на фактически observed pattern.

**limits.** Не определяет MAR/MNAR конкретного канала и не дает универсальной коррекции; при неигнорируемом пропуске нужны обоснованные sensitivity/bounds либо limitation.

**question_ids.** - R18-D10-Q01

- R18-D10-Q02

## S10-R03

[Failing Loudly: An Empirical Study of Methods for Detecting Dataset Shift (Rabanser, Günnemann & Lipton, NeurIPS 2019)](https://proceedings.neurips.cc/paper/2019/hash/846c260d715e5b854ffad5f70a516c88-Abstract.html) · [S10](../../solutions/lifecycle-r19/S10.md)

**standing.** Первичная эмпирическая работа, NeurIPS 2019.

**supports.** Сравнение shift detectors показывает зависимость обнаружения/вреда от вида и размера сдвига и метода.

**limits.** Тестированы отдельные датасеты/perturbations; результат не покрывает произвольный policy-induced shift или скрытый outcome.

**question_ids.** - R18-D10-Q01

## S10-R04

[Transportability of Causal and Statistical Relations: A Formal Approach (Pearl & Bareinboim, AAAI 2011)](https://ojs.aaai.org/index.php/AAAI/article/view/7861) · [S10](../../solutions/lifecycle-r19/S10.md)

**standing.** Первичная формальная работа, AAAI 25(1), 247–254 (2011).

**supports.** Selection diagrams и transport formulas задают проверяемый путь переноса из source в target при явной структуре различий и доступных измерениях.

**limits.** Требуются защищаемые causal/selection assumptions и target data; не переносит локальный null автоматически.

**question_ids.** - R18-D10-Q02

## S10-R05

[Beyond Power Calculations: Assessing Type S (Sign) and Type M (Magnitude) Errors (Gelman & Carlin, 2014)](https://doi.org/10.1177/1745691614551642) · [S10](../../solutions/lifecycle-r19/S10.md)

**standing.** Первичная методологическая статья, Perspectives on Psychological Science 9(6), 641–651 (2014).

**supports.** Type S/M и design calculations показывают зависимость интерпретации sign/magnitude от plausible effects, uncertainty и размера исследования.

**limits.** Расчеты условны на выбранную модель и внешние effect-size предположения; не задают универсальный порог мощности или отрицательного знания.

**question_ids.** - R18-D10-Q02

## S10-R06

[Causal inference by using invariant prediction: identification and confidence intervals (Peters, Bühlmann & Meinshausen, 2016)](https://doi.org/10.1111/rssb.12167) · [S10](../../solutions/lifecycle-r19/S10.md)

**standing.** Первичная методологическая статья, JRSS B 78(5), 947–1012 (2016).

**supports.** Invariance across конкретные environments/interventions может поддержать причинную идентификацию при assumptions метода.

**limits.** Нужны подходящие среды, данные и предпосылки идентификации; наблюдаемое сходство само не является универсальным transport certificate.

**question_ids.** - R18-D10-Q02

## S10-R07

[Continuous Inspection Schemes (Page, 1954)](https://doi.org/10.1093/biomet/41.1-2.100) · [S10](../../solutions/lifecycle-r19/S10.md)

**standing.** Первичная методологическая статья, Biometrika 41(1–2), 100–115 (1954).

**supports.** Sequential inspection/change detection имеет смысл для заданного процесса и класса изменений; профиль должен назвать предполагаемое изменение и detection behavior.

**limits.** Не универсальный detector для неуказанного размера shift, произвольной зависимости или смены канала; пример метода, не default PolicyOS.

**question_ids.** - R18-D10-Q01

## S11-R01

[Models — Gemini API](https://ai.google.dev/gemini-api/docs/models) · [S11](../../solutions/lifecycle-r19/S11.md)

**standing.** Google official docs, updated 2026-10-22.

**supports.** latest alias hot-swaps each release; breaking changes get two weeks notice.

**limits.** Provider-specific; notice does not prove served version per request.

## S11-R02

[Model IDs and versioning — Claude Platform Docs](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions) · [S11](../../solutions/lifecycle-r19/S11.md)

**standing.** Anthropic official docs, checked 2026-10-23.

**supports.** Older short aliases resolve dated snapshots; 4.6+ IDs pin weights/config, while serving router/safety/sampling may still shift behavior.

**limits.** Provider account, not request-level independent telemetry.

## S11-R03

[API Overview — Backwards compatibility](https://developers.openai.com/api/reference/overview) · [S11](../../solutions/lifecycle-r19/S11.md)

**standing.** OpenAI official docs, checked 2026-10-23.

**supports.** Behavior may change between snapshots; recommends pinning and app-specific evals.

**limits.** No universal cadence or adequacy guarantee.

## S11-R04

[How is ChatGPT's behavior changing over time?](https://arxiv.org/abs/2307.09009) · [S11](../../solutions/lifecycle-r19/S11.md)

**standing.** Chen, Zaharia, Zou; primary empirical study, v3 (2023-10-31).

**supports.** March/June GPT API behavior changed in different directions across reasoning, refusals, multi-hop and code.

**limits.** Early API and selected tasks; no PolicyOS threshold.

## S11-R05

[Did the Model Change? Efficiently Assessing Machine Learning API Shifts](https://arxiv.org/abs/2107.14203) · [S11](../../solutions/lifecycle-r19/S11.md)

**standing.** Chen, Cai, Zaharia, Zou; primary empirical paper (2021-07-29).

**supports.** API-shift assessment under fixed inputs; adaptive sampling reduces queries in classification setting.

**limits.** Not agentic free-text or multilingual evidence.

## S12-R01

[To Trust or to Think: Cognitive Forcing Functions Can Reduce Overreliance on AI in AI-Assisted Decision-Making](https://doi.org/10.1145/3449287) · [S12](../../solutions/lifecycle-r19/S12.md)

**standing.** PACM HCI (CSCW), 2021; controlled N=199 study.

**supports.** Wrong AI advice was followed less under cognitive-forcing conditions than simple explanations; effects and burden varied by participant.

**limits.** Simulated decision task, not institutional-policy workflow; no universal interaction or threshold.

## S12-R02

[Does Automation Bias Decision-Making?](https://doi.org/10.1006/ijhc.1999.0252) · [S12](../../solutions/lifecycle-r19/S12.md)

**standing.** Peer-reviewed IJHCS, 1999; simulated-flight experiment.

**supports.** Faulty aids produced omission and commission errors; correctness-conditioned outcomes matter more than agreement.

**limits.** Historical flight simulation does not estimate PolicyOS or frontline error rates.

## S12-R03

[Conflict-free Replicated Data Types](https://perso.lip6.fr/Marc.Shapiro/papers/2011/CRDTs_SSS-2011.pdf) · [S12](../../solutions/lifecycle-r19/S12.md)

**standing.** Peer-reviewed SSS 2011 distributed-systems paper.

**supports.** Formal conditions allow offline replica convergence for selected CRDT types.

**limits.** Converged bytes do not establish semantic compatibility or policy admissibility.

## S12-R04

[Revisiting the Conflict-Resolving Problem from a Semantic Perspective](https://doi.org/10.1145/3691620.3694993) · [S12](../../solutions/lifecycle-r19/S12.md)

**standing.** Peer-reviewed ASE 2024 software-merge study.

**supports.** Targeted behavior tests expose conflicts missed by text/structure-only merging.

**limits.** Software has executable behavior/oracles; policy meaning needs native owners.

## S12-R05

[Web Content Accessibility Guidelines (WCAG) 2.2](https://www.w3.org/TR/WCAG22/) · [S12](../../solutions/lifecycle-r19/S12.md)

**standing.** W3C Recommendation, 12 December 2024.

**supports.** Use scoped, testable accessibility criteria on actual selected pages and modes.

**limits.** WCAG does not address every user need or prove policy comprehension/semantic parity.

## S12-R06

[Making Content Usable for People with Cognitive and Learning Disabilities](https://www.w3.org/TR/coga-usable/) · [S12](../../solutions/lifecycle-r19/S12.md)

**standing.** W3C Working Group Note, 29 April 2021; supplemental, non-normative.

**supports.** User testing and cognitive accessibility consider context, structure, language and usability.

**limits.** Not a conformance result or comprehension score; declare the audience/task.

## S12-R07

[RFC 9110: HTTP Semantics, §15.5.5 404 Not Found](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.5) · [S12](../../solutions/lifecycle-r19/S12.md)

**standing.** IETF Standards Track, June 2022.

**supports.** RFC 9110 permits 404 when the server will not disclose a forbidden resource exists.

**limits.** HTTP does not define evidence states or rule out side channels on other surfaces.

## S13-R01

[Records Management Guidance for Federal Employees, U.S. National Archives](https://www.archives.gov/records-mgmt/transition/records-management-guidance-federal-employees) · [S13](../../solutions/lifecycle-r19/S13.md)

**standing.** Официально; updated 2024-06-10, reviewed 2025-05-06.

**supports.** Записи остаются в федеральном агентстве и передаются преемнику через exit briefing/records officer; конкретный пример человеческого handoff. Q01,Q04.

**limits.** Только США; не устанавливает полномочия конкретного преемника, его ресурсы или смысловую fidelity копии.

## S13-R02

[Frequently Asked Questions about GRS 5.1, Common Office Records, U.S. National Archives](https://www.archives.gov/records-mgmt/grs/faqs-for-grs-5-1) · [S13](../../solutions/lifecycle-r19/S13.md)

**standing.** Официальное разъяснение NARA, updated 2024-04.

**supports.** Копия, используемая при деловой работе, сама может быть record; наличие другого официального экземпляра не делает все производные эквивалентными. Q03.

**limits.** Только федеральная records-retention практика; не доказывает статус данной копии и не делает PolicyOS её хранителем.

## S13-R03

[Magenta Book: Central Government guidance on evaluation, HM Treasury / Evaluation Task Force](https://www.gov.uk/government/publications/the-magenta-book/magenta-book-central-government-guidance-on-evaluation-html) · [S13](../../solutions/lifecycle-r19/S13.md)

**standing.** Официальное UK guidance, HTML updated 2026-05-15.

**supports.** §1.8 разделяет process/delivery и impact/causal attribution; §4.2 различает staff/resources inputs, processes, outputs и outcomes; §5.2-5.3 требует учитывать роли и ресурсы оценки. Q01,Q04.

**limits.** Методическое руководство UK, не evidence о выбранной организации и не каузальный вывод без соответствующего design.

## S13-R04

[Understanding CDER’s Postmarket Safety Surveillance Programs and Public Data, U.S. FDA](https://www.fda.gov/drugs/cder-conversations/understanding-cders-postmarket-safety-surveillance-programs-and-public-data) · [S13](../../solutions/lifecycle-r19/S13.md)

**standing.** Официальная страница; точная дата не указана в полученном результате.

**supports.** Adverse-event report не означает причинность; review может устранять дубли, применять case definitions и проверять поля. Q05.

**limits.** Фармаконадзорный пример; клинические методы, полномочия и пороги не переносятся на другие домены.

## S13-R05

[Data Mining at the Center for Biologics Evaluation and Research, U.S. FDA](https://www.fda.gov/science-research/data-mining/data-mining-center-biologics-evaluation-and-research) · [S13](../../solutions/lifecycle-r19/S13.md)

**standing.** Официальная страница; дата публикации не установлена.

**supports.** Disproportionality mining генерирует гипотезы: сигнал не доказывает causal effect, отсутствие сигнала не доказывает отсутствие вреда. Q05.

**limits.** Специализированная фармаконадзорная методика, не универсальный порог или harm taxonomy.

## S14-R01

[SLSA v1.2 Verifying Artifacts](https://slsa.dev/spec/v1.2/verifying-artifacts) · [S14](../../solutions/lifecycle-r19/S14.md)

**standing.** Official SLSA v1.2, Approved.

**supports.** Consumer verifies subject, trusted builder/signer, build type and parameters.

**limits.** Trusted-builder compromise and semantic correctness remain outside provenance.

## S14-R02

[SLSA v1.2 Build Track Basics](https://slsa.dev/spec/v1.2/build-track-basics) · [S14](../../solutions/lifecycle-r19/S14.md)

**standing.** Official SLSA v1.2, Approved.

**supports.** L3 isolates builds and protects signing secrets.

**limits.** Platform remains trusted; no data/evaluator/conclusion truth.

## S14-R03

[in-toto: Providing Farm-to-Table Guarantees for Bits and Bytes](https://www.usenix.org/system/files/sec19-torres-arias.pdf) · [S14](../../solutions/lifecycle-r19/S14.md)

**standing.** Primary USENIX Security 2019 paper.

**supports.** Signed links bind declared steps, functionaries and material transitions.

**limits.** One common root cannot provide independent semantic truth.

## S14-R05

[Membership Inference Attacks against Machine Learning Models](https://arxiv.org/abs/1610.05820) · [S14](../../solutions/lifecycle-r19/S14.md)

**standing.** Shokri et al., IEEE S&P 2017.

**supports.** Black-box model behavior can reveal training membership.

**limits.** Empirical result depends on model, data and access.

## S14-R06

[Extracting Training Data from Large Language Models](https://www.usenix.org/conference/usenixsecurity21/presentation/carlini-extracting) · [S14](../../solutions/lifecycle-r19/S14.md)

**standing.** Carlini et al., USENIX Security 2021.

**supports.** Queries can extract memorized training strings from some LLMs.

**limits.** Selected model/data attacks; no universal risk rate.

## S14-R07

[Revealing Information while Preserving Privacy](https://doi.org/10.1145/773153.773173) · [S14](../../solutions/lifecycle-r19/S14.md)

**standing.** Dinur & Nissim, PODS 2003.

**supports.** Repeated perturbed aggregates can reconstruct records under stated assumptions.

**limits.** No universal threshold for arbitrary outputs.

## S14-R08

[The Composition Theorem for Differential Privacy](https://proceedings.mlr.press/v37/kairouz15.html) · [S14](../../solutions/lifecycle-r19/S14.md)

**standing.** Kairouz et al., ICML/PMLR 2015.

**supports.** Adaptive DP releases compose; one accountant covers the selected set.

**limits.** Valid only for realized DP, specified unit and complete denominator.

## S14-R09

[Regulation (EU) 2016/679, Articles 7, 17 and 19](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng/) · [S14](../../solutions/lifecycle-r19/S14.md)

**standing.** Official EUR-Lex GDPR text.

**supports.** GDPR requires demonstrable consent where relied on; withdrawal is prospective; erasure has exceptions.

**limits.** Applicability, basis and retention depend on jurisdiction and facts.

## S14-R10

[Machine Unlearning](https://doi.org/10.1109/SP40001.2021.00019) · [S14](../../solutions/lifecycle-r19/S14.md)

**standing.** Bourtoule et al., IEEE S&P 2021.

**supports.** SISA limits training influence/retraining cost in tested settings.

**limits.** No universal full-unlearning proof.

## S14-R11

[NIST AI 600-1 Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) · [S14](../../solutions/lifecycle-r19/S14.md)

**standing.** Official voluntary NIST profile, 2024-07-26.

**supports.** Recommends postdeployment monitoring, incident response and foreseeable-misuse review.

**limits.** Does not adjudicate individual adopter facts.

## S14-R12

[NIST SP 800-61 Rev. 3 Incident Response](https://csrc.nist.gov/pubs/sp/800/61/r3/final) · [S14](../../solutions/lifecycle-r19/S14.md)

**standing.** Official NIST final, 2025-04-03.

**supports.** Organizes incident preparation, analysis, response and recovery.

**limits.** Does not prove PolicyOS dependency coverage complete.

## S15-R01

[RFC 8126: Guidelines for Writing an IANA Considerations Section in RFCs](https://www.rfc-editor.org/rfc/rfc8126.html) · [S15](../../solutions/lifecycle-r19/S15.md)

**standing.** IETF BCP 26, June 2017.

**supports.** Documented criteria, named change controller, expert review and appeal for assigned registry decisions; provisional status can record without endorsing use.

**limits.** Protocol-code registration only; supports owner-local process, not a universal semantic classifier or PolicyOS authority.

## S15-R02

[SKOS Simple Knowledge Organization System Reference](https://www.w3.org/TR/skos-reference/) · [S15](../../solutions/lifecycle-r19/S15.md)

**standing.** W3C Recommendation, 18 August 2009.

**supports.** Distinguishes exact/close/broader/narrower/related mappings; closeMatch is non-transitive to limit compounded errors.

**limits.** Vocabulary relations do not prove truth, fit, authority or admissibility; exactMatch has stronger transitive effects and requires evidence.

## S15-R03

[FHIR R5 ConceptMap (FHIR v5.0.0)](https://hl7.org/fhir/conceptmap.html) · [S15](../../solutions/lifecycle-r19/S15.md)

**standing.** Published HL7 R5 v5.0.0; Trial Use, maturity 3.

**supports.** Mappings are directional and business-context-specific; allows conditions, ambiguity, multiple targets and no match.

**limits.** Medical terminology model, not general authority; receiver still verifies mapping owner, version, scope and requiredness.

## S15-R04

[Verifiable Credentials Data Model v2.0](https://www.w3.org/TR/vc-data-model-2.0/) · [S15](../../solutions/lifecycle-r19/S15.md)

**standing.** W3C Recommendation, 15 May 2025.

**supports.** Issuer authenticity is distinct from verifier trust; verifier decides which issuers to trust and for what purpose.

**limits.** Credential exchange does not establish subject-matter competence; signature alone is not mandate.

## S16-R01

[Dominant Resource Fairness (Ghodsi et al., NSDI 2011)](https://www.usenix.org/conference/nsdi11/dominant-resource-fairness-fair-allocation-multiple-resource-types) · [S16](../../solutions/lifecycle-r19/S16.md)

**standing.** Первичная рецензированная работа; реализована и измерена в Mesos.

**supports.** DRF generalizes max-min fairness to dominant shares across multiple resource dimensions; candidate for residual bulk allocation.

**limits.** Does not choose duty urgency/custody priority or guarantee deadlines under overload, discrete resources or non-preemptive work.

## S16-R02

[Large-scale cluster management at Google with Borg (EuroSys 2015)](https://research.google/pubs/large-scale-cluster-management-at-google-with-borg/) · [S16](../../solutions/lifecycle-r19/S16.md)

**standing.** Первичная системная работа с production-кластером.

**supports.** Borg combines admission, isolation, recovery and measured scheduling at cluster scale.

**limits.** One infrastructure’s operational experience does not set PolicyOS caps, weights or priority semantics.

## S16-R03

[Leases: An Efficient Fault-Tolerant Mechanism for Distributed File Cache Consistency (Gray & Cheriton, SOSP 1989)](https://doi.org/10.1145/74850.74870) · [S16](../../solutions/lifecycle-r19/S16.md)

**standing.** Первичная исследовательская работа SOSP.

**supports.** Lease correctness explicitly depends on physical clocks, bounded skew and message delay.

**limits.** File-cache model; expiry does not kill workers or fence provider effects.

## S16-R04

[The Chubby Lock Service for Loosely-Coupled Distributed Systems (OSDI 2006)](https://research.google/pubs/the-chubby-lock-service-for-loosely-coupled-distributed-systems/) · [S16](../../solutions/lifecycle-r19/S16.md)

**standing.** Первичная системная работа OSDI.

**supports.** Sequencer includes generation; protected receiver validates it to reject stale operations.

**limits.** Fencing works only at participating sinks; Chubby is not proposed as dependency.

## S16-R05

[Time, Clocks, and the Ordering of Events in a Distributed System (Lamport, CACM 1978)](https://lamport.azurewebsites.net/pubs/time-clocks.pdf) · [S16](../../solutions/lifecycle-r19/S16.md)

**standing.** Первичная теоретическая работа; авторская копия.

**supports.** Happened-before is partial; logical clocks encode causality, physical deadlines require clock assumptions.

**limits.** Logical clocks do not measure TTL or elapsed time.

## S16-R06

[Spanner: Google’s Globally-Distributed Database (OSDI 2012)](https://research.google/pubs/spanner-googles-globally-distributed-database-2/) · [S16](../../solutions/lifecycle-r19/S16.md)

**standing.** Первичная системная работа OSDI.

**supports.** Strict time consistency may use a dedicated API that exposes bounded uncertainty.

**limits.** TrueTime is not implied by ordinary SQL or UTC; no such profile is established here.

## S17-R01

[The Update Framework Specification v1.0.37](https://theupdateframework.github.io/specification/v1.0.37/index.html) · [S17](../../solutions/lifecycle-r19/S17.md)

**standing.** Официальная первичная спецификация; обновлена 2026-10-08.

**supports.** Root N+1/threshold continuity, persistent generation, anti-rollback, expiry/freeze.

**limits.** Update protocol only; not runtime identity, compatibility or authority; no required dependency.

## S17-R02

[SLSA v1.2 Build Provenance](https://slsa.dev/spec/v1.2/build-provenance) · [S17](../../solutions/lifecycle-r19/S17.md)

**standing.** Первичная approved provenance spec.

**supports.** Artifact subject ↔ builder/build type, inputs/dependencies, time.

**limits.** Depends on trusted builder and complete inputs; not loaded runtime or result correctness.

## S17-R03

[SLSA v1.2 Verifying Artifacts](https://slsa.dev/spec/v1.2/verifying-artifacts) · [S17](../../solutions/lifecycle-r19/S17.md)

**standing.** Официальная approved consumer verification spec.

**supports.** Signature, subject digest, trusted builder, source/build expectations; consumer verification matters.

**limits.** Consumer sets expectations; recursive deps optional/best-effort; no runtime/semantic proof.

## S17-R04

[Kubernetes Version Skew Policy](https://kubernetes.io/releases/version-skew-policy/) · [S17](../../solutions/lifecycle-r19/S17.md)

**standing.** Official component policy; current page 1.37, checked 2026-10-23.

**supports.** Directional component-specific skew; tools may narrow the window.

**limits.** Kubernetes example; its numeric skew does not transfer to PolicyOS.

## S17-R05

[NIST SP 800-218 SSDF v1.1](https://csrc.nist.gov/pubs/sp/800/218/final) · [S17](../../solutions/lifecycle-r19/S17.md)

**standing.** Final NIST recommendation, 2022-02.

**supports.** Secure software/vulnerability lifecycle and supplier communications.

**limits.** Does not set PolicyOS emergency authority, deadlines, exceptions or compatibility.

## S17-R06

[OpenAI API Deprecations](https://developers.openai.com/api/docs/deprecations) · [S17](../../solutions/lifecycle-r19/S17.md)

**standing.** Primary single-vendor docs; dynamic page checked 2026-10-23.

**supports.** Example model ID/shutdown notice; API records may expose shutdown_date.

**limits.** One vendor only; public/null feed misses account notices and does not prove actual called model.

## S18-R01

[RFC 7282, On Consensus and Humming in the IETF](https://www.rfc-editor.org/rfc/rfc7282.html) · [S18](../../solutions/lifecycle-r19/S18.md)

**standing.** Informational RFC, 2014-06

**supports.** Record and resolve objections; consensus is not a vote.

**limits.** Does not name a PolicyOS ratifier or precedence.

## S18-R02

[NIST SP 800-53 Rev. 5, CM-3 Configuration Change Control](https://csrc.nist.gov/Pubs/sp/800/53/r5/upd1/Final) · [S18](../../solutions/lifecycle-r19/S18.md)

**standing.** NIST SP 800-53 Rev.5, CM-3

**supports.** Configuration changes need impact review, explicit disposition and retained record.

**limits.** No SDD hierarchy; cite Rev. 5, not latest release.

## S18-R03

[NIST RMF Authorize Step FAQs](https://csrc.nist.gov/CSRC/media/Projects/risk-management/documents/06-Authorize%20Step/NIST%20RMF%20Authorize%20Step-FAQs.pdf) · [S18](../../solutions/lifecycle-r19/S18.md)

**standing.** Official NIST RMF FAQ, 2021-03-11

**supports.** Within RMF, the appointed Authorizing Official owns risk acceptance.

**limits.** Does not identify PolicyOS principal or succession.

## S18-R04

[The Update Framework Specification v1.0.37](https://theupdateframework.github.io/specification/v1.0.37/index.html) · [S18](../../solutions/lifecycle-r19/S18.md)

**standing.** TUF v1.0.37; modified 2026-10-08

**supports.** Version/threshold continuity supports technical root rotation.

**limits.** Key protocol does not prove human authority.

## S18-R05

[W3C PROV-O](https://www.w3.org/TR/prov-o/) · [S18](../../solutions/lifecycle-r19/S18.md)

**standing.** W3C Recommendation, 2013-04-30

**supports.** Entity/activity/agent provenance relations support cross-reference.

**limits.** Lineage does not prove truth, admissibility or authority.

## S19-R01

[GAO-20-195G, Cost Estimating and Assessment Guide, March 2020](https://www.gao.gov/assets/710/706933.pdf) · [S19](../../solutions/lifecycle-r19/S19.md)

**standing.** Official GAO guide.

**supports.** LCCE covers concept through disposal, past/current/future costs, omissions, assumptions and uncertainty; supports whole-life vector rather than invocation price.

**limits.** Does not set PolicyOS prices, allocation policy, social value or admissibility.

## S19-R02

[FinOps Framework: Allocation capability (official page; accessed 2026-10-23)](https://framework.finops.org/framework/capabilities/allocation/) · [S19](../../solutions/lifecycle-r19/S19.md)

**standing.** Industry cloud-finance framework; page undated.

**supports.** Direct/shared cloud costs use an explicit org-selected strategy; shared costs can remain central/unallocated.

**limits.** Accounting convention does not prove causal benefit, custody ownership, or cross-tenant reuse rights.

## S19-R03

[NIST SP 800-53A Rev. 5, January 2022](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53Ar5.pdf) · [S19](../../solutions/lifecycle-r19/S19.md)

**standing.** Official federal security/privacy assessment guidance.

**supports.** Risk may tailor assessment extent, rigor and intensity to sufficient assurance.

**limits.** Analogy only; no PolicyOS assurance floor or permission to weaken its claim predicate.

## S19-R04

[NIST SP 800-53B, October 2020](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53B.pdf) · [S19](../../solutions/lifecycle-r19/S19.md)

**standing.** Official federal security/privacy baselines.

**supports.** Risk-based tailoring considers cost/schedule/performance while retaining justified constraints.

**limits.** Specific federal context; does not define PolicyOS admissibility.

## S19-R05

[Green Software Foundation, SCI Specification v1.1.0, October 2024](https://sci.greensoftware.foundation/) · [S19](../../solutions/lifecycle-r19/S19.md)

**standing.** Published specification; site identifies ISO/IEC 21031:2024.

**supports.** SCI=(E×I+M)/R separates energy, sourced intensity, embodied emissions and common unit; boundary includes provisioned/reserved energy and support infrastructure. Modeled data is labeled when measurement is unavailable.

**limits.** Software footprint is not policy impact/value; cloud energy and embodied allocation may be modeled and uncertain.

## S19-R06

[GHG Protocol Scope 2 update: current status, 2026-10-16](https://ghgprotocol.org/blog/scope-2-market-based-method-update-2025-2026-public-consultation-current-status) · [S19](../../solutions/lifecycle-r19/S19.md)

**standing.** Official status update, not final standard.

**supports.** Revision was still under consideration at publication; cite current factor/method/version, not a pending draft as settled.

**limits.** Does not select a factor or boundary for a deployment.

## S20-R01

[Mark W. Maier, Architecting a portfolio of systems, Systems Engineering 22(4), 2019](https://doi.org/10.1002/sys.21486) · [S20](../../solutions/lifecycle-r19/S20.md)

**standing.** Peer-reviewed systems-engineering paper

**supports.** Portfolio systems need explicit operational relations; grouping alone is not integration.

**limits.** Aerospace framing; no policy authority or causal estimator.

**questions.** - R18-D20-Q01

- R18-D20-Q02

## S20-R02

[Rogge & Reichardt, Policy mixes for sustainability transitions: An extended concept and framework for analysis, Research Policy 45(8), 2016](https://doi.org/10.1016/j.respol.2016.04.004) · [S20](../../solutions/lifecycle-r19/S20.md)

**standing.** Peer-reviewed framework

**supports.** Policy mixes differ by goals/instruments/processes, governance level, geography and time.

**limits.** Conceptual framework; not causal identification or competence test.

**questions.** - R18-D20-Q01

- R18-D20-Q03

- R18-D20-Q06

## S20-R03

[Hudgens & Halloran, Toward Causal Inference With Interference, JASA 103(482), 2008](https://doi.org/10.1198/016214508000000292) · [S20](../../solutions/lifecycle-r19/S20.md)

**standing.** Peer-reviewed causal methods

**supports.** Interference estimands depend on exposure mappings and their assumptions.

**limits.** No universal map of policy interactions.

**questions.** - R18-D20-Q02

- R18-D20-Q03

- R18-D20-Q04

## S20-R04

[Elinor Ostrom, Polycentric systems for coping with collective action and global environmental change, Global Environmental Change 20(4), 2010](https://doi.org/10.1016/j.gloenvcha.2010.07.004) · [S20](../../solutions/lifecycle-r19/S20.md)

**standing.** Peer-reviewed governance research

**supports.** Autonomous decision centers can coexist with nested externalities; scale follows the problem.

**limits.** Governance theory does not prove powers or causal effects.

**questions.** - R18-D20-Q01

- R18-D20-Q03

## S20-R05

[Robert E. Lucas, Econometric Policy Evaluation: A Critique, Carnegie-Rochester Conference Series on Public Policy 1, 1976](https://doi.org/10.1016/S0167-2231(76)80003-6) · [S20](../../solutions/lifecycle-r19/S20.md)

**standing.** Foundational policy-evaluation paper

**supports.** Policy can change expectations, behavior and the data-generating process.

**limits.** Does not prove a response in a particular matter.

**questions.** - R18-D20-Q04

- R18-D20-Q05

## S20-R06

[Buldyrev et al., Catastrophic cascade of failures in interdependent networks, Nature 464, 2010](https://doi.org/10.1038/nature08932) · [S20](../../solutions/lifecycle-r19/S20.md)

**standing.** Peer-reviewed network model

**supports.** Interdependent networks can exhibit nonlinear cascade failure.

**limits.** Idealized assumptions; not a crisis detector or incident evidence.

**questions.** - R18-D20-Q02

- R18-D20-Q05

## S20-R07

[Arrow & Fisher, Environmental Preservation, Uncertainty, and Irreversibility, QJE 88(2), 1974](https://doi.org/10.2307/1883074) · [S20](../../solutions/lifecycle-r19/S20.md)

**standing.** Peer-reviewed decision theory

**supports.** Uncertainty plus irreversibility can give option value to preserving choice.

**limits.** Conditional on payoffs/probabilities; no universal discount or delay rule.

**questions.** - R18-D20-Q06

## S20-R08

[Haasnoot et al., Dynamic adaptive policy pathways: A method for crafting robust decisions for a deeply uncertain world, Global Environmental Change 23(2), 2013](https://doi.org/10.1016/j.gloenvcha.2012.12.006) · [S20](../../solutions/lifecycle-r19/S20.md)

**standing.** Peer-reviewed decision-support method

**supports.** Signposts and switching paths can represent sequential adaptation.

**limits.** A pathway does not prove signal quality, authority or resources.

**questions.** - R18-D20-Q05

- R18-D20-Q06

## Дополнительное исследование интегратора

### ROOT-R01

[W3C PROV-O Recommendation](https://www.w3.org/TR/prov-o/)

**Применение.** Reuse qualified derivation, revision and specialization relations; keep case identity, evidence lineage and institutional authorization distinct.

**Предел.** PROV records asserted provenance; does not establish scientific truth, legal effect or permission. PROV invalidation must not be substituted for scoped claim-currentness.

### ROOT-R02

[W3C Data Quality Vocabulary](https://www.w3.org/TR/vocab-dqv/)

**Применение.** Attach quality measurement to its concrete metric, resource and provenance; publish plural contextual assessments rather than universal quality grades.

**Предел.** Working Group Note, not an admissibility calculus or external quality oracle. No requirement to add RDF store.

### ROOT-R03

[NIST AI RMF 1.0 Appendix C](https://airc.nist.gov/airmf-resources/airmf/appendices/app-c-ai-risk-management-and-human-ai-interaction/)

**Применение.** Preserve contextual meaning and differentiated human responsibilities; assess actual human-system use, not only model accuracy.

**Предел.** Guidance does not certify local comprehension, delegate a mandate or determine value tradeoffs.

### ROOT-R04

[SLSA v1.2 provenance](https://slsa.dev/spec/v1.2/provenance)

**Применение.** Source/build provenance binds production history; owner admission still verifies expected identity and operation.

**Предел.** Build/source authenticity does not prove method validity, a benign source, or actual loaded runtime state.

### ROOT-R05

[Hidden Technical Debt in Machine Learning Systems](https://papers.neurips.cc/paper/5656-hidden-technical-debt-in-machine-learning-systems.pdf)

**Применение.** Make dependent consumers, feedback loops and changing data assumptions explicit; avoid proliferating independent lifecycle managers.

**Предел.** Architecture risk analysis, not proof of a PolicyOS defect or prescription of a new component.

### ROOT-R06

[OHDSI Book chapter 15: Data Quality](https://ohdsi.github.io/TheBookOfOhdsi/DataQuality.html)

**Применение.** Separate internal verification of data constraints from external validation and temporal plausibility.

**Предел.** Health-data pattern; does not supply universal thresholds or establish target-estimand support.
