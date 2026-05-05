# MSME PolicyOS Final Experiment Suite 2026-05-01 (v2 Defense-Grade Redesign)

Status: redesign frozen before final thesis defense run
Prepared on: 2026-04-30 (v1), 2026-04-30 (v2 redesign after first run review)
Target thesis topic: public policy for supporting small and medium-sized
enterprises during martial law in Ukraine
Primary system: PolicyOS Policy Engine
Working run name: `msme_final_fresg_evaluation_v2_20260501`

This document is the reproducible technical protocol for the final defense
experiments. The earlier `msme_final_fresg_evaluation_20260501_20260430-092000`
run is treated as the pilot of this protocol: it confirmed end-to-end pipeline
execution, GCS sync, Foundry/Fabric integration, schema-lite validation and
audit-chain emission, but it surfaced six defense-grade weaknesses that the v2
redesign addresses:

1. The semi-synthetic causal benchmark used a single clean DGP, so AIPW, TMLE
   and IPW agreed to four decimal places. That convergence under-tests an
   identification-aware gauntlet — methods must be allowed to disagree where
   identification is harder.
2. The 200 `bootstrap_replicates` parameter was carried in the config but never
   actually executed, so no estimate had a confidence interval.
3. The eight ablation variants produced almost identical top-30 rankings for
   six of the eight variants — only `no_governance` and `mean_only_ranking`
   actually shifted ranks. The thesis claim that evidence layers are binding
   needs ablations whose removal triggers structural drop-out, not additive
   penalties.
4. The fairness audit returned uniform results across 20 policies because the
   synthetic applicant generator did not vary by family or include any
   deliberately biased policy. The audit was therefore testing the pipeline,
   not policy fairness.
5. The robust ranking reported a single winner (`det_policy_102`) without
   confidence intervals; the gap to rank 2 was 0.034 in a metric whose
   variability was unmeasured.
6. Causal discovery, vertical-slice depth on a single Ukrainian program
   («Власна справа»), and several opt-in frontier methods listed in the
   limitations were not exercised at all.

The v2 protocol below removes all six weaknesses while staying inside a
4-6 hour budget on the same 12 vCPU profile. The protocol still does not claim
a final real-world causal effect of any Ukrainian MSME support program unless
applicant-level treatment and outcome microdata are available and the
identification checks pass. It claims that the system catches problems that
single-method approaches miss, and produces typed verdicts with
uncertainty quantification.

## 1. Thesis Alignment

### 1.1 Research Problem

The thesis argues that Ukrainian MSME support policy during martial law has a
capability gap: programs exist, but the institutional system does not yet
consistently produce formalized, reproducible, causal, scalable and governable
evidence. In the thesis this gap is represented by the FRESG diagnostic frame:

| FRESG dimension | Meaning in the thesis | What the final suite must test |
| --- | --- | --- |
| F - Formalization | Policy goals, eligibility, treatment, outcomes and assumptions are machine-readable and internally coherent. | Can PolicyOS convert MSME programs into typed policy artifacts and detect ambiguity? |
| R - Reproducibility | An independent reviewer can reconstruct the data, method and decision path. | Does the run produce manifests, hashes, inputs, method configs and replay plans? |
| E - Evidence base | Claims are linked to statistical data, legal sources, academic priors and causal diagnostics. | Does the system retrieve, score and qualify evidence instead of reporting unsupported claims? |
| S - Scalability / transferability | Policy evidence remains useful across regions, sectors, time and conflict contexts. | Does the suite stress-test policies over many uncertainty worlds and transportability contexts? |
| G - Governance | Policy analysis is contestable, auditable, fairness-aware and human-reviewable. | Does the suite produce governance, fairness, recourse and claim-boundary artifacts? |

### 1.2 Original H1-H6 and Final Experiment Mapping

The thesis initially described six experiments. The v2 protocol keeps the
hypothesis structure but expands each module so that the gauntlet is harder,
the ranking is uncertainty-aware, and three new modules (E9 vertical slice,
E10 sensitivity surface, E11 frontier-method opt-in) close the limitations
that the pilot run left open.

| Thesis hypothesis | Original intent | v2 suite modules |
| --- | --- | --- |
| H1 - formalization and auto-identification | Formalize MSME programs and infer estimands / data requirements. | E1, E2, E9 (vertical slice) |
| H2 - full causal stack | Run identification-aware causal estimators, bounds, sensitivity, discovery. | E3 (multi-DGP gauntlet + bootstrap), E3b (discovery ensemble), E10 (sensitivity surface), E11 (frontier opt-in) |
| H3 - transportability | Evaluate transfer of external evidence to wartime Ukraine. | E4 (with bootstrap CIs on transport scores) |
| H4 - runtime mechanisms, welfare and robustness | Compare policy variants under budget, welfare and uncertainty constraints. | E5 (multi-method ranking + bootstrap CIs), E6 (3 macro scenarios + region heatmap) |
| H5 - fairness, recourse and conflict sensitivity | Test fairness, contestability and human-gate behavior. | E7 (with 3 deliberately biased policies + bootstrap CIs) |
| H6 - adaptivity and chained audit | Show replayable audit and behavior under policy/norm changes. | E8 (binding-semantics ablations + adaptivity) |

### 1.3 Final Suite Claim

If the v2 suite succeeds, the defensible thesis claim is:

> PolicyOS catches problems that single-method approaches miss. It
> operationalizes the FRESG requirements for MSME policy analysis by producing
> formalized policy artifacts with explicit issue registers, linked
> legal/data/evidence inputs with bootstrap-quantified uncertainty,
> identification-aware causal diagnostics that disagree where identification is
> harder, multi-method robust scenario rankings whose top candidates are
> statistically tied, governance checks that flag deliberately biased policies,
> and replayable audit trails in a single reproducible cloud workflow that fits
> a 4-6 hour budget on a 12 vCPU machine.

The suite must not claim:

- that the top-ranked policy is objectively optimal for Ukraine;
- that observed scenario effects are real causal estimates without real
  applicant-level data;
- that all methods in the Foundry catalog were executed (the suite executes a
  defensible subset and one frontier opt-in method);
- that deferred Lex amendment enrichment has no effect (the v2 suite still
  records evidence posture rather than legal claims);
- that LLM-generated policy language is a substitute for public authority,
  legal review or democratic decision-making.

### 1.4 v2 Redesign Summary

| Pilot weakness | v2 fix | New artifact |
| --- | --- | --- |
| Single clean DGP, methods agreed to 4 decimals | 6 DGPs (clean, weak_overlap, nonlinear, heterogeneous, hidden_confounder, positivity_violation) × 8 methods × 200 bootstrap | `causal_method_dgp_grid.csv` with bias / RMSE / coverage / status |
| `bootstrap_replicates=200` carried but unused | Genuine bootstrap on causal estimates, transport scores, robust scores, disparate impact bounds | `*_ci.csv` files for each |
| 6 of 8 ablations were additive shifts | Binding-semantics ablation: `no_lex` drops policies with `legal_compatibility < 0.5`; `no_fabric` drops policies with no metric coverage | `ablation_binding_dropouts.csv` |
| Uniform fairness audit | 3 deliberately biased policies (`bias_geo_kyiv_only`, `bias_credit_history_3y`, `bias_male_only`) injected; audit must catch them | `fairness_violation_detection.csv` with TP/FP rates |
| Single ranking method, no CIs | TOPSIS, robust TOPSIS, regret-min, AHP, ELECTRE-III with bootstrap CIs | `multi_method_rank_stability.csv`, `robust_score_cis.csv` |
| No causal discovery, no vertical depth, no frontier methods | E3b discovery ensemble; E9 vertical slice on «Власна справа»; E11 BayesianBART opt-in | new module outputs in stages 13-15 |

## 2. Methodological Anchors

The final suite follows six external methodological principles.

| Anchor | Relevance for this experiment |
| --- | --- |
| HM Treasury Magenta Book | Evaluation should combine process, impact and value-for-money questions and start from a Theory of Change. The suite therefore includes process/formalization, causal/impact diagnostics and budget/welfare ranking. |
| OECD evidence governance | Technical evidence is necessary but not sufficient; ethics, values, context and political constraints must be visible. The suite therefore includes governance, fairness, contestability and claim boundaries. |
| Robust Decision Making / MORDM | Policies under deep uncertainty should be stress-tested across many plausible worlds, not optimized for one forecast. The suite therefore includes many-world robust ranking and vulnerability analysis. |
| STRESS simulation reporting | Simulation studies should report model, software, inputs, assumptions, random seeds and reproducibility conditions. The suite therefore writes runtime manifests, input hashes, stage configs and replay commands. |
| ABM verification, validation and accreditation | Agent-based policy models should distinguish verification, validation, calibration and credibility. The suite labels graph-aware simulation as scenario/proxy simulation unless external validation data are available. |
| E-value / sensitivity reporting | Observational causal claims must show robustness to unmeasured confounding. The suite reports sensitivity and does not rely on p-values or point estimates alone. |

Reference URLs:

- HM Treasury Magenta Book: <https://www.gov.uk/government/publications/the-magenta-book/magenta-book-central-government-guidance-on-evaluation-html>
- OECD evidence governance: <https://www.oecd.org/en/publications/mobilising-evidence-for-good-governance_3f6f736b-en/full-report/component-5.html>
- Robust Decision Making overview: <https://link.springer.com/chapter/10.1007/978-3-030-05252-2_2>
- STRESS guidelines: <https://www.equator-network.org/reporting-guidelines/strengthening-the-reporting-of-empirical-simulation-studies-introducing-the-stress-guidelines/>
- ABM credibility and VV&A: <https://jasss.soc.surrey.ac.uk/27/4/4.html>
- E-value sensitivity analysis: <https://content.sph.harvard.edu/wwwhsph/sites/603/2017/08/EValue_Preprint.pdf>

## 3. Experiment Identity and Output Layout

### 3.1 Identifiers

```text
experiment_family = msme_policyos_final
experiment_id     = msme_final_fresg_evaluation_v2_20260501
run_id            = msme_final_fresg_evaluation_v2_20260501_<YYYYMMDD-HHMMSS>
pilot_run_id      = msme_final_fresg_evaluation_20260501_20260430-092000
```

The v2 run id must be distinct from the pilot run id so that artifacts do not
overwrite each other in the GCS prefix and so that ablation comparison between
v1 (additive) and v2 (binding) ablations remains possible.

The run script must create the exact `run_id` at launch and write it into every
stage artifact. A result is not considered thesis-grade if stage artifacts lack
the run id.

### 3.2 Cloud Output Prefix

Primary cloud prefix:

```text
gs://lex-1-494208-data/experiments/msme_final_fresg_evaluation_v2_20260501/<run_id>/
```

Required top-level structure (v2 adds stages 13-16):

```text
<run_id>/
  00_preflight/
  01_capability_inventory/
  02_input_freeze/
  03_policy_formalization/
  04_evidence_retrieval/
  05_causal_benchmark/                 # E3 multi-DGP gauntlet + bootstrap
  05b_causal_discovery/                # NEW: E3b discovery ensemble
  06_transportability/                 # with bootstrap CIs
  07_robust_policy_tournament/         # multi-method + bootstrap CIs
  08_agent_network_simulation/         # 3 macro scenarios + region heatmap
  09_fairness_recourse_governance/     # with 3 bias-injected policies
  10_ablation_reproducibility/         # binding-semantics ablations
  11_adaptivity_audit/
  12_final_dossier/
  13_vertical_slice_vlasna_sprava/     # NEW: E9 deep dive
  14_sensitivity_surface/              # NEW: E10 E-value / Rosenbaum
  15_frontier_optin/                   # NEW: E11 BayesianBART
  _logs/
  _manifests/
  _replay/
```

### 3.3 Local / VM Workdir

Preferred VM workdir:

```text
/mnt/experiments/msme_final_fresg_evaluation_20260501/<run_id>/
```

The run should not write large temporary data into the repository directory.
The repository is code. The workdir is state.

## 4. Compute Profile

### 4.1 Current Safe Profile

The v2 run is sized for the same VM as the pilot. The pilot ran in ~12 minutes
because most stages were vectorized scoring and `bootstrap_replicates=200` was
unused. The v2 budget is 4-6 hours (≈12-30× pilot), driven by genuine
bootstrap, multi-DGP gauntlet, multi-method ranking, 3 macro scenarios, and
the BayesianBART opt-in demo.

| Resource | Target |
| --- | ---: |
| Machine family | `n2-custom-12-98304` or equivalent |
| vCPU | 12 |
| RAM | 96 GB |
| Disk | 240 GB pd-ssd or larger |
| Threads | 12 |
| Expected runtime | 4-6 hours |

This profile is enough for the v2 suite if causal methods run on bounded
subsamples (12k rows for direct foundry, 5k for heavy methods), bootstrap is
parallelized over 12 cores, and the BART opt-in caps thinning at 1000 draws.

### 4.2 Stretch Profile

If quota is increased, the preferred stretch profile is:

| Resource | Target |
| --- | ---: |
| Machine family | `n2-standard-32`, `c3-standard-22`, or closest available |
| vCPU | 22-32 |
| RAM | 88-128 GB |
| Disk | 300-400 GB pd-ssd |
| Threads | all physical vCPU, with per-stage caps |
| Expected runtime | 1.5-3 hours |

The experiment must not require the stretch profile. It is only a speedup path.

### 4.3 Environment Variables

The run must record the effective values of these variables without printing
secret values:

```text
PYTHONPATH
OMP_NUM_THREADS
OPENBLAS_NUM_THREADS
MKL_NUM_THREADS
NUMEXPR_NUM_THREADS
XLA_FLAGS
GONKA_API_KEY_* availability only, never values
```

Recommended CPU settings for the 12-vCPU profile:

```text
OMP_NUM_THREADS=12
OPENBLAS_NUM_THREADS=12
MKL_NUM_THREADS=12
NUMEXPR_NUM_THREADS=12
XLA_FLAGS=--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=12
```

## 5. Input Data Freeze

Every final run must begin by freezing an input manifest. The manifest must
store file paths, sizes, sha256 hashes where feasible, row counts, schema
summaries and freshness notes.

### 5.1 Required Inputs

| Input family | Required path or resolver | Role |
| --- | --- | --- |
| PolicyOS code | `/mnt/experiments/polisyos/policy-engine` on VM and local repository path | Executable system under test |
| Production datasets | `policy-engine/production_data/dataset_catalog.duckdb` | Fabric/Datasets evidence retrieval |
| Dataset embeddings/index | `policy-engine/production_data/ds_dataset_embeddings.npz`, `ds_dataset_index.hnsw` | Semantic retrieval support, optional if DuckDB retrieval is enough |
| Dataset records | `policy-engine/production_data/all_records.jsonl` | Source-level evidence inventory |
| Academic runtime | `policy-engine/production_data/policyos_academic_runtime_slim_20260411T112032Z/` | Academic/Scholar evidence priors and transport scores |
| Ukraine agent baseline | `policy-engine/production_data/ukraine_agent_simulation_baseline_20260410/` | Graph-aware agent simulation and calibration priors |
| Heavy graph addon | `trade_graph_sparse.npz`, `budget_graph_sparse.npz`, `public_service_graph_sparse.npz`, `procurement_graph_sparse.npz`, `distress_graph_sparse.npz` | Network spillovers, shock propagation and graph priors |
| Lex final artifacts | resolved from current GCS final Lex publish bundle | Legal corpus, provisions, domains, SPO, document metadata and legal evidence snippets |
| Previous pilot artifacts | `gs://lex-1-494208-data/experiments/msme_deadline_20260430/msme_grand_tournament_v2/` | Pilot comparison and regression guard, not final evidence |

### 5.2 Known Data Volumes at Design Time

These counts are design-time checks from the prepared environment. The final
run must recompute them and write the observed values.

| Data source | Observed count |
| --- | ---: |
| Fabric `ds_datasets` | 137,176 |
| Fabric `ds_observations` | 3,708,006 |
| Fabric `ds_metric_bindings` | 56,846 |
| Fabric `ds_schema_profiles` | 176,249 |
| Fabric `ds_distributions` | 605,408 |
| Fabric `ds_variable_alignments` | 20,326 |
| Foundry method catalog | 389 methods in pilot environment |
| Causal methods in catalog | about 151 in pilot environment |

### 5.3 Data Quality Caveat

The production dataset bundle is analytically useful but not perfect. Existing
readiness files show strong benchmark readiness and transport/foundry fitness,
while source preflight and some QC checks may be non-passing because of
partial/deferred external manifests. This must be represented in evidence
weights and in the claim boundary.

Required artifact:

```text
02_input_freeze/data_quality_and_readiness.md
```

It must distinguish:

- available evidence;
- incomplete evidence;
- stale evidence;
- synthetic/proxy evidence;
- blocked claims.

## 6. Policy Universe

### 6.1 Program Families

The final suite should cover at least these MSME support families:

| Family id | Program family | Examples / thesis relevance |
| --- | --- | --- |
| `microgrant_restart` | Microgrants and restart grants | `Власна справа`, єРобота |
| `credit_guarantee` | Subsidized credit and guarantees | `Доступні кредити 5-7-9%`, guarantees |
| `tax_relief` | Tax and administrative relief | Wartime tax changes and reporting simplification |
| `digital_export` | Digital/export support | Дія.Бізнес, export promotion |
| `procurement_anchor` | Demand support through procurement | Public procurement, defense-adjacent demand |
| `relocation_frontline` | Relocation/restart support | Frontline and deoccupied region resilience |
| `veteran_idp` | Veteran/IDP entrepreneurship | Veteran grants, IDP support |
| `innovation_defense` | Innovation and dual-use support | Brave1, high-risk innovation |
| `industrial_parks` | Place-based production support | Industrial parks and recovery infrastructure |
| `donor_blended` | Donor and blended finance | USAID, MIGA/SURE-like risk guarantees |

### 6.2 Policy Design Count

Recommended final profile:

```text
policy_count = 192
minimum_policy_count = 128
stretch_policy_count = 256
```

Each policy candidate must have:

- `policy_id`;
- `family_id`;
- short label;
- problem statement;
- target group;
- intervention mechanism;
- eligibility logic;
- budget envelope or cost proxy;
- expected outcomes;
- legal constraints;
- evidence requirements;
- governance risks;
- simulation knobs.

### 6.3 LLM and Deterministic Generation

The final suite may use LLM policy design, but it must not depend on it.

Rules:

- LLM batches can enrich policy language and generate variants.
- Deterministic templates must cover all policy families.
- If LLM calls fail, the run continues with deterministic candidates.
- Every policy row must include `generation_mode`: `llm`, `llm_repaired`,
  `deterministic_template`, or `hybrid`.
- LLM outputs must pass schema-lite validation before entering the tournament.

## 7. Final Experiment Modules

## E1. FRESG Baseline to PolicyOS Capability Lift

### Objective

Test whether PolicyOS turns weakly formalized program descriptions into typed,
auditable policy artifacts and exposes remaining ambiguity.

### Inputs

- thesis program list and FRESG baseline scores;
- Lex-derived legal evidence;
- Fabric/Datasets variable and metric bindings;
- Trinity / IR schema contracts;
- policy candidates from the design factory.

### Method

For each program family:

1. Build a baseline FRESG row using thesis diagnostic criteria.
2. Create a PolicyOS formalization row:
   `ProblemFrame`, `PolicySpec`, `ModelSpec`, `RequiredDataSpec`,
   evidence refs and governance requirements.
3. Score capability lift on F, R, E, S and G.
4. Record unresolved issues:
   ambiguous eligibility, missing outcome definition, missing legal ref,
   weak data binding, missing causal identification, missing governance pass.

### Outputs

```text
03_policy_formalization/fresg_baseline.csv
03_policy_formalization/fresg_policyos_lift.csv
03_policy_formalization/formalization_issues.jsonl
03_policy_formalization/trinity_like_policy_artifacts.jsonl
03_policy_formalization/e1_formalization_summary.md
```

### Acceptance

- At least 10 program families scored.
- Every score has a reason, not only a number.
- Missing evidence is represented as an issue, not silently filled.

### Thesis Use

This module supports the claim that PolicyOS operationalizes the FRESG
diagnostic system.

## E2. Legal, Data and Academic Evidence Retrieval

### Objective

Test whether the system can assemble a multi-source evidence matrix for MSME
policy claims.

### Inputs

- Lex legal artifacts from processed NPA corpus;
- Fabric `dataset_catalog.duckdb`;
- Academic runtime bundle;
- policy candidates and policy families.

### Method

For each policy family and candidate:

1. Retrieve legal snippets and candidate normative references.
2. Retrieve relevant datasets by metric, source, geography and textual match.
3. Retrieve academic evidence priors and transport scores where available.
4. Score evidence by:
   availability, relevance, trust tier, source quality, recency,
   transportability support and Foundry fitness.
5. Generate claim-level evidence rows.

### Parameters

```text
fabric_dataset_limit = 8000
metric_binding_limit = 12000
academic_evidence_limit = 3000
lex_snippet_limit_per_family = 50
```

### Outputs

```text
04_evidence_retrieval/legal_evidence_matrix.jsonl
04_evidence_retrieval/fabric_evidence_matrix.jsonl
04_evidence_retrieval/academic_evidence_matrix.jsonl
04_evidence_retrieval/claim_evidence_map.jsonl
04_evidence_retrieval/missing_evidence_register.csv
04_evidence_retrieval/e2_evidence_summary.md
```

### Acceptance

- Evidence retrieval covers all policy families.
- Each policy candidate has at least one evidence posture:
  `supported`, `proxy_supported`, `weak_support`, `missing`, or `blocked`.
- The summary separates legal support, statistical support and academic priors.

### Thesis Use

This module supports the claim that PolicyOS integrates legal, statistical and
academic sources rather than relying on narrative policy justification.

## E3. Identification-Aware Causal Gauntlet (v2: multi-DGP + bootstrap)

### Objective

Test whether PolicyOS can run a causal stack, **disagree where identification
is harder**, and avoid overclaiming when identification is weak. The pilot
run had all three doubly-robust estimators agreeing to four decimals because
the DGP was too clean. v2 forces estimator disagreement by running 6 DGPs
with progressively harder identification.

### Inputs

- 6 semi-synthetic MSME applicant/panel data sets with known treatment
  effects and known identification status (one DGP per identification
  challenge);
- Fabric-derived covariate priors;
- policy family treatment definitions;
- Foundry causal estimators and diagnostics.

### DGP Suite

Each DGP shares schema (treatment T, outcome Y, covariates X, region R,
sector S, time t) but varies the identification challenge.

| DGP id | Identification challenge | Expected method behavior |
| --- | --- | --- |
| `clean` | Linear confounding, full overlap, no missingness | All DR methods agree; baseline |
| `weak_overlap` | Propensity scores in `[0.02, 0.98]` for 30% of sample | IPW divergence; matching shrinks sample; AIPW/TMLE more stable |
| `nonlinear_confounding` | Confounding nonlinear in X (interactions + splines) | Linear adjustment biased; ML-nuisance DML / AIPW with flexible nuisance closer to truth |
| `heterogeneous_effects` | True CATE varies 5× across sectors | ATE estimators biased toward sample-mix; CATE methods (causal forest, BART) recover heterogeneity |
| `hidden_confounder` | One latent confounder unmeasured | All point estimates biased; bounds (Manski, Lee) include truth; E-value < 1.5 |
| `positivity_violation` | Treatment deterministic for one stratum | Methods must return `not_identified` for that stratum, partial estimate elsewhere |

### Method Stack

For each DGP, run:

- treatment effects: AIPW, TMLE, IPW, propensity matching;
- ML-nuisance DML with three nuisance learners (Random Forest, gradient
  boosting, Lasso) cross-fitted in 5 folds;
- heterogeneous effects: causal forest (GRF), R-learner, X-learner;
- modern DiD ensemble for the time-varying DGPs: Callaway-Sant'Anna,
  Sun-Abraham, de Chaisemartin-D'Haultfœuille;
- synthetic control + augmented SCM where panel structure permits;
- bounds: Manski, Lee;
- diagnostics: overlap (NTV), balance, positivity, missingness;
- sensitivity: E-value and Rosenbaum bounds (full surface produced in E10).

### Bootstrap Protocol

Genuine bootstrap, not config-only:

- 200 cluster-bootstrap replicates per (DGP × estimator) combination;
- parallelized across 12 cores;
- emit point estimate, 95% CI, coverage of known truth, bias, RMSE per cell;
- record `successful_replicates` and `failed_replicates` separately so that
  failure rate is visible.

### Parameters

```text
causal_panel_rows = 750000
direct_foundry_subsample_rows = 12000
heavy_method_subsample_rows = 5000
bootstrap_replicates = 200
crossfit_folds = 5
random_seeds = 32
dgp_count = 6
heavy_methods_per_dgp = 8
bootstrap_parallelism = 12
```

### Outputs

```text
05_causal_benchmark/causal_panel_manifest.json
05_causal_benchmark/dgp_specifications.json
05_causal_benchmark/causal_method_runs.jsonl
05_causal_benchmark/causal_method_dgp_grid.csv         # 6 DGPs × 8 methods
05_causal_benchmark/causal_consensus_table.json
05_causal_benchmark/estimator_bias_rmse_coverage.csv   # with bootstrap CIs
05_causal_benchmark/bounds_tornado.csv
05_causal_benchmark/method_disagreement_matrix.csv     # NEW: pairwise disagreement
05_causal_benchmark/identification_verdicts.jsonl
05_causal_benchmark/bootstrap_diagnostics.csv          # NEW: replicate counts
05_causal_benchmark/e3_causal_gauntlet_summary.md
```

### Acceptance

- All 6 DGPs complete or produce typed failure status.
- For each DGP, at least 5 causal or bounds methods produce results or typed
  failure reasons with `successful_replicates >= 150` of 200.
- `method_disagreement_matrix.csv` shows non-zero disagreement on at least
  3 of 6 DGPs (otherwise the gauntlet is too easy and must be re-tuned).
- For `positivity_violation` DGP, at least one method returns
  `not_identified` for the affected stratum.
- For `hidden_confounder` DGP, bounds include known truth.
- For `nonlinear_confounding` DGP, ML-nuisance DML is closer to truth than
  linear AIPW.
- No effect estimate is reported without 95% CI.

### Thesis Use

This module supports the claim that PolicyOS is identification-aware and
that its gauntlet **catches** identification failures rather than masking
them with method agreement.

## E3b. Causal Discovery Ensemble

### Objective

Demonstrate that causal discovery returns an ensemble of DAG candidates with
edge-level reliability, not a single proven structure. The pilot had no
discovery output; v2 closes this gap.

### Inputs

- Same covariate panels as E3 (one DGP per discovery target plus a
  Fabric-derived real-covariate panel without outcomes);
- prior expert DAG (constructed deterministically from the program family
  causal map, used for face validity).

### Method

Run 5 discovery algorithms on each panel:

- PC (constraint-based);
- FCI (latent-variable allowing);
- GES (score-based);
- DAGMA (continuous optimization);
- PCMCI (time-series, on event-study DGP).

For each run, emit the DAG, the edge-level confidence (bootstrap or
algorithm-native), and the agreement with the prior expert DAG (precision,
recall, F1).

### Parameters

```text
discovery_algorithms = pc, fci, ges, dagma, pcmci
discovery_bootstrap_resamples = 100
discovery_panel_rows = 50000
discovery_max_runtime_per_algo_seconds = 300
```

### Outputs

```text
05b_causal_discovery/discovery_inputs.json
05b_causal_discovery/dag_per_algorithm/<algo_id>.json
05b_causal_discovery/consensus_dag.json
05b_causal_discovery/edge_reliability_matrix.csv
05b_causal_discovery/discovery_disagreement_table.csv
05b_causal_discovery/expert_prior_comparison.csv
05b_causal_discovery/e3b_discovery_summary.md
```

### Acceptance

- All 5 algorithms either complete or return typed timeout/failure.
- `consensus_dag.json` lists every edge with reliability score in `[0,1]`
  and `appears_in_n_of_5` count.
- `expert_prior_comparison.csv` reports F1 per algorithm vs prior DAG.
- The summary states explicitly that consensus DAG is not a proven structure.

### Thesis Use

Closes the discovery gap in the causal stack and demonstrates that the
system represents structural uncertainty as ensemble disagreement, not as a
single causal map.

## E4. Transportability and Context Shift

### Objective

Test whether external MSME evidence can be qualified before being applied to
wartime Ukraine.

### Inputs

- Academic evidence and transport scores;
- Fabric macro/regional context variables;
- Ukrainian war-context proxies;
- policy family definitions.

### Method

For each policy family:

1. Define source context: UK/EU/international evidence.
2. Define target context: wartime Ukraine.
3. Compare support factors:
   conflict exposure, displacement, credit constraints, fiscal capacity,
   administrative capacity, sector mix, regional exposure and fraud risk.
4. Compute or approximate transportability verdict:
   `admissible`, `admissible_with_bounds`, `proxy_only`,
   `insufficient_support`, `blocked`.
5. Record transport bounds or missing support factors.

### Parameters

```text
transport_contexts = 8
support_factors_per_context = 12
academic_candidates_per_family = 200
transport_bootstrap_resamples = 200
```

### Outputs

```text
06_transportability/source_target_contexts.jsonl
06_transportability/support_factor_matrix.csv
06_transportability/transportability_verdicts.jsonl
06_transportability/transport_bounds.csv
06_transportability/transport_score_cis.csv         # NEW: bootstrap CIs
06_transportability/missing_support_factors.md
06_transportability/e4_transportability_summary.md
```

### Acceptance

- Every policy family has a transportability verdict with bootstrap-based
  95% CI on the transport score (200 resamples over the support-factor
  vector).
- External evidence is never treated as directly transferable by default.
- Missing wartime context factors are explicit.
- Verdict thresholds are crossed only if both the point estimate and the
  CI lower bound are on the same side of the threshold (otherwise the
  verdict is downgraded one tier).

### Thesis Use

This module supports the thesis argument that transportability is a required
capability for evidence-informed policy during martial law and that
transport verdicts are uncertainty-aware, not point-only.

## E5. Many-World Robust Policy Tournament (v2: multi-method + bootstrap CIs)

### Objective

Test which policy designs remain useful under deep uncertainty, **using five
ranking methods and bootstrap-based confidence intervals** so that the
defensible output is a robust shortlist of statistically tied candidates,
not a single point-estimate winner. The pilot reported `det_policy_102` as
the top policy with a 0.034 gap to rank 2; the v2 protocol must show whether
that gap is statistically significant.

### Inputs

- policy candidates;
- evidence scores from E2;
- causal diagnostics from E3;
- transportability verdicts from E4 (with CIs);
- uncertainty-world generator;
- MCDA / welfare methods.

### Uncertainty Worlds

Each world samples:

- conflict intensity;
- regional displacement;
- energy disruption;
- export corridor disruption;
- domestic demand shock;
- credit crunch;
- fiscal scarcity;
- fraud pressure;
- administrative capacity;
- sector recovery speed;
- procurement demand shock;
- inflation / cost pressure.

### Method

For each candidate and world:

1. Project outcomes:
   survival, employment, fiscal cost, fraud risk, fairness, coverage,
   conflict sensitivity and implementation burden.
2. Apply evidence penalties:
   missing data, weak transportability, weak identification, weak legal
   support.
3. Rank policies under five ranking methods:
   - TOPSIS;
   - robust TOPSIS (worst-decile aware);
   - regret-minimization (Savage minimax regret);
   - AHP weighted (analyst priors);
   - ELECTRE-III (outranking with discordance threshold).
4. Bootstrap each ranking by resampling 100 random subsets of 100 worlds
   from the 160 generated worlds, 100 times → 100 bootstrap rankings per
   method per policy → 95% CI on robust score and on rank position.
5. Produce robust shortlist defined by overlapping CIs at 95%, not by
   single-method point ranking.
6. Produce vulnerability scenarios (worst-case worlds for each
   shortlisted policy).

### Parameters

```text
policy_count = 192
uncertainty_worlds = 160
scenario_seeds = 64
ranking_methods = topsis, robust_topsis, regret_min, ahp_weighted, electre_iii
ranking_bootstrap_resamples = 100
ranking_bootstrap_world_subsample = 100
pareto_objectives = survival, employment, fairness, budget_pressure, fraud_risk, evidence_strength
```

### Outputs

```text
07_robust_policy_tournament/world_design_matrix.parquet
07_robust_policy_tournament/policy_world_outcomes.parquet
07_robust_policy_tournament/robust_rankings.csv             # all 5 methods
07_robust_policy_tournament/multi_method_rank_stability.csv # NEW: 5 methods × top-30
07_robust_policy_tournament/robust_score_cis.csv            # NEW: bootstrap CIs
07_robust_policy_tournament/rank_position_cis.csv           # NEW: rank CIs
07_robust_policy_tournament/statistically_tied_shortlist.csv # NEW: CI overlap groups
07_robust_policy_tournament/pareto_frontier.csv
07_robust_policy_tournament/vulnerability_scenarios.csv
07_robust_policy_tournament/top_policy_dossiers.json
07_robust_policy_tournament/e5_robust_tournament_summary.md
```

### Acceptance

- At least 128 policy candidates and 100 worlds complete (target 192 × 160).
- Five ranking methods executed; pairwise top-10 agreement reported.
- Each top-30 policy has robust-score 95% CI and rank-position CI.
- `statistically_tied_shortlist.csv` lists policies whose CIs overlap at
  95% with the top-ranked policy.
- Single point-estimate winner is **not** the headline output; the headline
  is a tied shortlist.

### Thesis Use

This is the main decision-support result. It demonstrates robust policy
design under wartime uncertainty with explicit uncertainty quantification
and ranking-method robustness.

## E6. Graph-Aware Agent and Network Simulation (v2: 3 macro scenarios + region heatmap)

### Objective

Test how candidate policies behave under region-sector network structure and
shock propagation, **across three macro scenarios** so that policy ranking
becomes scenario-conditional. The pilot ran one scenario only; v2 adds an
intensified-conflict and a partial-recovery scenario so that policies that
win only in baseline can be flagged.

### Inputs

- `ukraine_agent_simulation_baseline_20260410`;
- runtime bundle agent registry;
- calibration bundle;
- heavy graph addon:
  trade, budget, procurement, public service and distress graphs;
- shortlist from E5 (statistically tied shortlist preferred).

### Macro Scenarios

| Scenario id | Conflict intensity | Displacement | Energy disruption | Fiscal capacity | Demand shock |
| --- | ---: | ---: | ---: | ---: | ---: |
| `baseline_2026` | 1.0× | 1.0× | 1.0× | 1.0× | 1.0× |
| `intensified_conflict` | 1.5× | 1.3× | 1.4× | 0.85× | -10% |
| `partial_recovery` | 0.7× | 0.8× | 0.7× | 1.2× | +20% |

### Method

For the shortlist policies and selected baseline policies:

1. Load graph priors and runtime/calibration metadata.
2. For each macro scenario, simulate heterogeneous agents over time.
3. Track outcomes by:
   region (oblast level), sector, firm size, conflict exposure, IDP/veteran
   priority and frontline/deoccupied status.
4. Estimate spillover and vulnerability patterns by graph layer.
5. Produce region × policy heatmap of survival and employment for each
   scenario.
6. Identify scenario-fragile policies (winners in baseline but not in
   intensified_conflict).
7. Record credibility:
   `proxy_simulation`, `calibrated_proxy`, or `validated` if validation data
   are available.

### Parameters

```text
agent_count = 220000
simulation_months = 30
simulation_seeds = 64
shortlist_size = 32
graph_layers = trade, procurement, budget, public_service, distress
macro_scenarios = baseline_2026, intensified_conflict, partial_recovery
```

### Outputs

```text
08_agent_network_simulation/simulation_input_manifest.json
08_agent_network_simulation/policy_simulation_scores.jsonl
08_agent_network_simulation/scenario_policy_outcomes.csv         # NEW: 3 scenarios × shortlist
08_agent_network_simulation/region_sector_heatmap_baseline.csv
08_agent_network_simulation/region_sector_heatmap_intensified.csv # NEW
08_agent_network_simulation/region_sector_heatmap_recovery.csv   # NEW
08_agent_network_simulation/scenario_fragility_table.csv         # NEW
08_agent_network_simulation/spillover_summary.csv
08_agent_network_simulation/graph_layer_contribution.csv
08_agent_network_simulation/simulation_credibility_statement.md
08_agent_network_simulation/e6_agent_network_summary.md
```

### Acceptance

- At least 24 shortlist policies simulated under all 3 scenarios.
- Every result row includes credibility status (`proxy_simulation` by
  default).
- Simulation claims are not presented as real forecasts.
- `scenario_fragility_table.csv` lists policies whose rank moves by ≥ 3
  positions between scenarios.
- Three region × policy heatmaps emitted, one per scenario.

### Thesis Use

This module shows that PolicyOS can reason about heterogeneous MSME response,
network spillovers, and scenario-conditional ranking, while staying honest
about simulation credibility.

## E7. Fairness, Recourse and Conflict-Sensitive Governance (v2: bias injection + bootstrap)

### Objective

Test whether PolicyOS **distinguishes fair from deliberately biased
policies**, produces contestability artifacts and escalates risky cases to
human review. The pilot returned uniform fairness scores across 20 policies
because no policy had injected bias; v2 adds 3 deliberately biased policy
templates and the audit must detect and flag them with a higher-severity
governance verdict.

### Inputs

- synthetic applicant profiles (with family-aware distributions, not uniform);
- 23 policies: 20 standard shortlist policies + 3 deliberately biased
  injection policies;
- conflict exposure and regional tags;
- fairness and recourse method outputs;
- legal and governance constraints.

### Bias Injection Templates

| Bias policy id | Bias mechanism | Expected detection | Expected verdict |
| --- | --- | --- | --- |
| `bias_geo_kyiv_only` | Eligibility excludes Donetsk, Luhansk, Kherson, Zaporizhzhia, Kharkiv | `conflict_region_approval_ratio` collapses (< 0.3) | `reject_until_review` with `bias_reason=geographic_exclusion` |
| `bias_credit_history_3y` | Requires 3 years of credit history (proxy filter that excludes IDPs and post-2022 founders) | IDP approval ratio < 0.4; cohort effect against post-2022 firms | `reject_until_review` with `bias_reason=indirect_temporal_filter` |
| `bias_male_only` | Beneficiary type filter that proxies for gender | gender approval ratio < 0.5 | `reject_until_review` with `bias_reason=protected_attribute_proxy` |

### Method

1. Generate applicant profiles with:
   gender, region, sector, firm size, veteran/IDP status, conflict exposure,
   credit access and data completeness, with **family-aware distributions**
   so that microgrant_restart, credit_guarantee and tax_relief draw from
   different applicant pools.
2. Simulate eligibility / prioritization decisions for all 23 policies.
3. Evaluate:
   disparate impact, group access, counterfactual sensitivity, recourse
   feasibility, conflict-sensitive coverage and human-gate triggers.
4. Bootstrap disparate impact bounds (200 resamples) to produce 95% CI on
   approval ratios per group.
5. Produce contestability packet for each policy with `bias_reason` field
   when triggered.
6. Compute true-positive rate (3 bias policies caught), false-positive rate
   (standard policies wrongly flagged at the strictest threshold) and
   confusion matrix.

### Parameters

```text
applicant_profiles = 200000
applicant_distribution_per_family = stratified
protected_or_sensitive_dimensions = gender, region, veteran_status, idp_status, conflict_exposure
bias_injection_policy_count = 3
recourse_examples = 100
human_gate_thresholds = strict and deadline_safe
fairness_bootstrap_resamples = 200
```

### Outputs

```text
09_fairness_recourse_governance/fairness_audit.csv
09_fairness_recourse_governance/disparate_impact_bounds.csv
09_fairness_recourse_governance/disparate_impact_cis.csv          # NEW: bootstrap CIs
09_fairness_recourse_governance/fairness_violation_detection.csv  # NEW: TP/FP per bias type
09_fairness_recourse_governance/bias_injection_specs.json         # NEW: 3 templates
09_fairness_recourse_governance/recourse_atlas.jsonl
09_fairness_recourse_governance/contestability_packets.jsonl      # with bias_reason
09_fairness_recourse_governance/human_gate_cases.jsonl
09_fairness_recourse_governance/governance_verdicts.jsonl
09_fairness_recourse_governance/e7_fairness_governance_summary.md
```

### Acceptance

- All 3 bias-injected policies flagged with `reject_until_review` and a
  specific `bias_reason` matching the injected mechanism.
- False-positive rate on the 20 standard policies ≤ 25% at the strict
  threshold (so the audit discriminates rather than blocking everything).
- At least one contestability packet per major policy family.
- All disparate impact bounds reported with bootstrap 95% CI.
- `fairness_violation_detection.csv` shows confusion matrix and per-bias-type
  detection rate.

### Thesis Use

This module supports the argument that governance is part of the
computational system, not a post-hoc ethical paragraph, **and that the
audit catches the unfair policies it should catch.**

## E8. Ablation, Adaptivity and Reproducible Audit (v2: binding-semantics ablations)

### Objective

Test whether the full system is materially better than weaker variants and
whether the final outputs can be replayed. The pilot ablations were additive
shifts: removing a layer subtracted a constant from every score and the
top-30 ranking was preserved across six of eight variants. The v2 ablations
are **binding**: removing a layer makes some policies unrankable rather than
subtracting a constant, so the ranking changes structurally.

### Ablation Variants (binding semantics)

| Variant | Removed component | Binding effect |
| --- | --- | --- |
| `full_policyos` | none | Main result |
| `no_lex` | legal evidence removed | Policies with `legal_compatibility < 0.5` drop to `blocked` and exit ranking |
| `no_fabric` | dataset evidence removed | Policies with `metric_coverage < 0.3` drop to `blocked` and exit ranking |
| `no_academic` | academic priors removed | Policies with `transport_score = proxy_only` lose their evidence floor and may drop |
| `no_causal_diagnostics` | causal penalties removed | Identification penalties zeroed; expected to raise top scores and increase overclaim risk |
| `no_transportability` | direct transfer assumed | Transport bounds collapsed to point; verdicts ignored |
| `no_governance` | fairness/human-gate removed | Governance penalties zeroed; bias-injected policies (E7) re-enter ranking → must be flagged in summary |
| `mean_only_ranking` | robust ranking replaced by mean score | Worst-decile and regret components dropped |

### Adaptivity Scenario

Hypothetical policy/norm change:

- extend microgrant restart channel to veterans and IDP entrepreneurs in
  high-conflict regions;
- change grant ceiling and co-financing rule;
- add human review requirement for missing credit-history data;
- add conflict-exposure priority rule.

The suite should re-run affected artifacts and produce a diff:

```text
old_policy_ref -> new_policy_ref
old_evidence_posture -> new_evidence_posture
old_ranking -> new_ranking
old_governance_verdict -> new_governance_verdict
```

### Outputs

```text
10_ablation_reproducibility/ablation_rank_shift.csv
10_ablation_reproducibility/ablation_binding_dropouts.csv     # NEW: which policies become blocked per variant
10_ablation_reproducibility/ablation_overclaim_risk.csv
10_ablation_reproducibility/ablation_top10_set_diff.csv       # NEW: Jaccard distance per variant
10_ablation_reproducibility/reproducibility_manifest.json
10_ablation_reproducibility/replay_command.sh
11_adaptivity_audit/policy_change_diff.json
11_adaptivity_audit/audit_chain.json
11_adaptivity_audit/replay_plan.md
11_adaptivity_audit/e8_ablation_adaptivity_summary.md
```

### Acceptance

- All 8 ablation variants run.
- For each non-trivial variant, at least one policy changes its
  `blocked / supported` status (binding semantics confirmed).
- For each variant, top-10 Jaccard distance from `full_policyos` is reported;
  at least 4 variants must have Jaccard distance > 0 (top-10 set actually
  changes).
- For `no_governance`, the bias-injected policies from E7 must re-enter the
  ranking and be flagged in the summary as a worked example of why
  governance is binding.
- The final run writes exact command lines and input hashes.
- Audit chain includes refs or hash-like stand-ins for each major artifact.

### Thesis Use

This module supports H6 and provides the strongest reproducibility evidence
for the defense, plus a worked demonstration that governance, evidence and
identification layers are binding constraints, not cosmetic penalties.

## E9. Vertical Slice — «Власна справа» Deep Dive

### Objective

Demonstrate full-depth identification, evidence and governance trace on a
single Ukrainian MSME program, alongside the breadth survey of 192
candidates. The pilot demonstrated breadth without any single program done
deeply. v2 closes that gap by selecting `microgrant_restart` as the depth
case (mapped to «Власна справа», the most documented Ukrainian wartime MSME
support program).

### Scope

Single program family `microgrant_restart`, single canonical policy
`vlasna_sprava_canonical`, with reference to:

- Постанова КМУ № 738 (microgrant programs);
- Закон України № 4618-VI (MSME support law);
- Datasets metric «зайнятість суб'єктів МСП» from Держстат;
- Academic reference: UK Start Up Loans evaluations (transport source).

### Method

1. **Formalization (E1 deep)**: full Trinity bundle with ProblemFrame,
   PolicySpec, ModelSpec, RequiredDataSpec; explicit `estimand =
   ATT(survival_24mo | T=microgrant, S=Ukraine_2026, R=non_frontline)`;
   id_engine emits ProofStep chain.
2. **Evidence (E2 deep)**: Lex placeholder NormPack with explicit ref to
   Постанова КМУ № 738 and Закон № 4618-VI, plus declared deferred-enrichment
   marker; Fabric retrieves Держстат metric bindings; Academic returns at
   least 3 UK Start Up Loans references with transport priors.
3. **Causal (E3 deep)**: run AIPW + TMLE + ML-DML + causal forest on the
   `clean` and `nonlinear_confounding` DGPs, restricted to
   microgrant_restart subsample; report point estimate, 95% bootstrap CI,
   E-value and Rosenbaum bound for each.
4. **Transport (E4 deep)**: full UK → Ukraine support-factor matrix with
   numerical bounds and admissibility verdict.
5. **Robust ranking (E5 deep)**: report `vlasna_sprava_canonical` rank in
   each of 5 ranking methods with bootstrap CIs.
6. **Simulation (E6 deep)**: agent simulation restricted to this policy,
   broken down by oblast.
7. **Fairness (E7 deep)**: full fairness audit on this policy with
   counterfactual fairness decomposition and one developed contestability
   packet for a synthetic rejected applicant (with full legal trace,
   missing-data flag, available recourse actions, alternative program
   routing).
8. **Audit chain (E8 deep)**: hash-chained refs from input_manifest through
   final_decision_packet for this policy specifically.

### Outputs

```text
13_vertical_slice_vlasna_sprava/trinity_bundle.json
13_vertical_slice_vlasna_sprava/identification_proof_chain.json
13_vertical_slice_vlasna_sprava/evidence_dossier.md
13_vertical_slice_vlasna_sprava/causal_estimates_with_cis.csv
13_vertical_slice_vlasna_sprava/transport_bounds_uk_ua.json
13_vertical_slice_vlasna_sprava/multi_method_rank_with_cis.csv
13_vertical_slice_vlasna_sprava/oblast_simulation_outcomes.csv
13_vertical_slice_vlasna_sprava/fairness_decomposition.csv
13_vertical_slice_vlasna_sprava/contestability_packet_full.json
13_vertical_slice_vlasna_sprava/audit_chain_for_policy.json
13_vertical_slice_vlasna_sprava/e9_vertical_slice_summary.md
```

### Acceptance

- Trinity bundle validates against schema;
- estimand explicitly compiled with target population, treatment definition,
  outcome and adjustment set;
- at least 4 causal estimators report point + 95% CI + E-value;
- transport verdict reported with numerical lower/upper bound;
- one full contestability packet with legal references and recourse atlas
  routing;
- audit chain hash-linked from `input_manifest` to
  `final_decision_packet_vlasna_sprava`.

### Thesis Use

Removes the «всё на placeholders» attack at defense by demonstrating depth
on the single most-documented Ukrainian MSME program.

## E10. Sensitivity Surface

### Objective

Produce thesis-ready sensitivity figures showing that PolicyOS quantifies
robustness to unmeasured confounding and to confounding-strength assumptions.

### Method

For each primary estimand from the vertical slice (E9) and from the 6 DGPs
(E3):

- compute E-value (VanderWeele-Ding) for the point estimate and for the
  CI lower bound;
- compute Rosenbaum bound surface across confounding-strength
  parameter Γ ∈ {1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0};
- emit tornado plot data for each estimand;
- for each plot, record the Γ value at which the estimate becomes
  non-significant (`gamma_break`).

### Outputs

```text
14_sensitivity_surface/e_values_per_estimand.csv
14_sensitivity_surface/rosenbaum_bounds_grid.csv
14_sensitivity_surface/tornado_plot_data.csv
14_sensitivity_surface/gamma_break_table.csv
14_sensitivity_surface/e10_sensitivity_summary.md
```

### Acceptance

- Every primary estimand has an E-value with explanation;
- Rosenbaum surface includes 7 Γ levels;
- tornado plot data are plot-ready (one CSV per figure).

### Thesis Use

Concrete figure data for Section 3.8 / Appendix B and an evidence-grade
answer to «what would it take for the estimate to be wrong».

## E11. Frontier Method Opt-In Demo (BayesianBART)

### Objective

Run **one** opt-in frontier method end-to-end so that the thesis can claim
the system supports advanced methods, not just the default-profile subset.
Removes one bullet from the limitations list.

### Method

Execute BayesianBART (Hahn-Murray-Carvalho BCF variant if available, plain
BART otherwise) on the `heterogeneous_effects` DGP from E3:

- 4 chains × 1000 burn-in × 2000 sampling = 8000 posterior draws;
- thinning applied if memory pressure;
- emit posterior CATE distribution per sector;
- compare CATE point estimates with causal forest from E3 on the same DGP.

### Parameters

```text
bart_chains = 4
bart_burnin = 1000
bart_samples = 2000
bart_thinning = 2
bart_max_runtime_seconds = 1800
```

### Outputs

```text
15_frontier_optin/bart_run_config.json
15_frontier_optin/cate_posterior_per_sector.csv
15_frontier_optin/bart_vs_causal_forest_comparison.csv
15_frontier_optin/bart_diagnostics.md       # convergence, ESS, R-hat
15_frontier_optin/e11_frontier_optin_summary.md
```

### Acceptance

- All 4 chains converge (R-hat < 1.05) or typed convergence-warning emitted;
- per-sector CATE posterior interval reported;
- comparison table vs causal forest reported with disagreement metric.

### Thesis Use

Closes the «opt-in methods not run» limitation and provides a Bayesian-HTE
figure for the appendix.

## 8. End-to-End Pipeline

The final runner should execute stages in this order. Each stage must write an
`experiment_result.json` with `status`, `started_at`, `finished_at`, input refs,
output refs, metrics and typed errors if any.

### Stage 00 - Preflight

Purpose:

- verify VM resources;
- verify repository and Python environment;
- verify GCS write access;
- verify production data paths;
- verify Lex final artifact resolver;
- verify Fabric DuckDB readability;
- verify Foundry imports and at least one `pure_step`;
- verify enough disk space.

Required outputs:

```text
00_preflight/preflight_result.json
00_preflight/preflight_summary.md
```

Hard fail if:

- GCS write fails;
- production data missing;
- Fabric DuckDB unreadable;
- code import fails;
- disk free space below 80 GB;
- no output manifest can be written.

### Stage 01 - Capability Inventory

Purpose:

- count Foundry methods;
- list causal/policy/simulation/fairness/transport methods;
- inventory Fabric tables;
- inventory Lex final artifacts;
- inventory Academic runtime;
- inventory Ukraine agent baseline.

Required outputs:

```text
01_capability_inventory/method_catalog_summary.json
01_capability_inventory/fabric_catalog_counts.json
01_capability_inventory/lex_artifact_inventory.json
01_capability_inventory/academic_inventory.json
01_capability_inventory/agent_baseline_inventory.json
01_capability_inventory/runtime_environment.json
01_capability_inventory/capability_inventory_summary.md
```

### Stage 02 - Input Freeze

Purpose:

- freeze all input files;
- compute hashes for small/medium inputs;
- compute row counts for tabular data;
- record code version and dirty-state summary;
- record exact launch config.

Required outputs:

```text
02_input_freeze/input_manifest.json
02_input_freeze/input_hashes.jsonl
02_input_freeze/code_version.json
02_input_freeze/launch_config.json
02_input_freeze/data_quality_and_readiness.md
```

### Stage 03 - Policy Formalization

Runs E1 and the policy design part of E5.

Required outputs:

```text
03_policy_formalization/normalized_policy_designs.jsonl
03_policy_formalization/trinity_like_policy_artifacts.jsonl
03_policy_formalization/fresg_baseline.csv
03_policy_formalization/fresg_policyos_lift.csv
03_policy_formalization/formalization_issues.jsonl
03_policy_formalization/policy_schema_compatibility_report.json
03_policy_formalization/e1_formalization_summary.md
```

### Stage 04 - Evidence Retrieval

Runs E2.

Required outputs:

```text
04_evidence_retrieval/legal_evidence_matrix.jsonl
04_evidence_retrieval/fabric_evidence_matrix.jsonl
04_evidence_retrieval/academic_evidence_matrix.jsonl
04_evidence_retrieval/claim_evidence_map.jsonl
04_evidence_retrieval/missing_evidence_register.csv
04_evidence_retrieval/e2_evidence_summary.md
```

### Stage 05 - Causal Benchmark (multi-DGP + bootstrap)

Runs E3 across 6 DGPs with 200 bootstrap replicates per cell.

Required outputs:

```text
05_causal_benchmark/causal_panel_manifest.json
05_causal_benchmark/dgp_specifications.json
05_causal_benchmark/causal_method_runs.jsonl
05_causal_benchmark/causal_method_dgp_grid.csv
05_causal_benchmark/causal_consensus_table.json
05_causal_benchmark/estimator_bias_rmse_coverage.csv
05_causal_benchmark/method_disagreement_matrix.csv
05_causal_benchmark/bootstrap_diagnostics.csv
05_causal_benchmark/identification_verdicts.jsonl
05_causal_benchmark/e3_causal_gauntlet_summary.md
```

### Stage 05b - Causal Discovery Ensemble

Runs E3b. New stage in v2.

Required outputs:

```text
05b_causal_discovery/dag_per_algorithm/<algo_id>.json
05b_causal_discovery/consensus_dag.json
05b_causal_discovery/edge_reliability_matrix.csv
05b_causal_discovery/discovery_disagreement_table.csv
05b_causal_discovery/expert_prior_comparison.csv
05b_causal_discovery/e3b_discovery_summary.md
```

### Stage 06 - Transportability

Runs E4.

Required outputs:

```text
06_transportability/source_target_contexts.jsonl
06_transportability/support_factor_matrix.csv
06_transportability/transportability_verdicts.jsonl
06_transportability/transport_bounds.csv
06_transportability/e4_transportability_summary.md
```

### Stage 07 - Robust Policy Tournament (multi-method + bootstrap)

Runs E5 with 5 ranking methods and 100 bootstrap resamples each.

Required outputs:

```text
07_robust_policy_tournament/world_design_matrix.parquet
07_robust_policy_tournament/policy_world_outcomes.parquet
07_robust_policy_tournament/robust_rankings.csv
07_robust_policy_tournament/multi_method_rank_stability.csv
07_robust_policy_tournament/robust_score_cis.csv
07_robust_policy_tournament/rank_position_cis.csv
07_robust_policy_tournament/statistically_tied_shortlist.csv
07_robust_policy_tournament/pareto_frontier.csv
07_robust_policy_tournament/vulnerability_scenarios.csv
07_robust_policy_tournament/top_policy_dossiers.json
07_robust_policy_tournament/e5_robust_tournament_summary.md
```

### Stage 08 - Agent Network Simulation (3 macro scenarios)

Runs E6 across `baseline_2026`, `intensified_conflict`, `partial_recovery`.

Required outputs:

```text
08_agent_network_simulation/policy_simulation_scores.jsonl
08_agent_network_simulation/scenario_policy_outcomes.csv
08_agent_network_simulation/region_sector_heatmap_baseline.csv
08_agent_network_simulation/region_sector_heatmap_intensified.csv
08_agent_network_simulation/region_sector_heatmap_recovery.csv
08_agent_network_simulation/scenario_fragility_table.csv
08_agent_network_simulation/spillover_summary.csv
08_agent_network_simulation/graph_layer_contribution.csv
08_agent_network_simulation/e6_agent_network_summary.md
```

### Stage 09 - Fairness, Recourse and Governance (bias injection + bootstrap)

Runs E7 with 3 bias-injected policies and bootstrap CIs.

Required outputs:

```text
09_fairness_recourse_governance/fairness_audit.csv
09_fairness_recourse_governance/disparate_impact_bounds.csv
09_fairness_recourse_governance/disparate_impact_cis.csv
09_fairness_recourse_governance/fairness_violation_detection.csv
09_fairness_recourse_governance/bias_injection_specs.json
09_fairness_recourse_governance/recourse_atlas.jsonl
09_fairness_recourse_governance/contestability_packets.jsonl
09_fairness_recourse_governance/human_gate_cases.jsonl
09_fairness_recourse_governance/governance_verdicts.jsonl
09_fairness_recourse_governance/e7_fairness_governance_summary.md
```

### Stage 10 - Ablation and Reproducibility

Runs the ablation part of E8.

Required outputs:

```text
10_ablation_reproducibility/ablation_rank_shift.csv
10_ablation_reproducibility/ablation_overclaim_risk.csv
10_ablation_reproducibility/reproducibility_manifest.json
10_ablation_reproducibility/replay_command.sh
10_ablation_reproducibility/e8_ablation_summary.md
```

### Stage 11 - Adaptivity and Audit

Runs the adaptivity part of E8.

Required outputs:

```text
11_adaptivity_audit/policy_change_diff.json
11_adaptivity_audit/audit_chain.json
11_adaptivity_audit/replay_plan.md
11_adaptivity_audit/e8_adaptivity_audit_summary.md
```

### Stage 12 - Final Dossier

Purpose:

- assemble thesis-readable outputs;
- produce tables and figure data;
- produce claim boundary;
- produce artifact inventory;
- sync all final artifacts to GCS.

Required outputs:

```text
12_final_dossier/final_experiment_summary.md
12_final_dossier/thesis_tables/
12_final_dossier/figure_data/
12_final_dossier/top_policy_shortlist.md
12_final_dossier/statistically_tied_shortlist.md
12_final_dossier/fresg_results_table.csv
12_final_dossier/hypothesis_verdicts.csv
12_final_dossier/v2_vs_pilot_comparison.md
12_final_dossier/limitations_and_claims_boundary.md
12_final_dossier/artifact_inventory.md
12_final_dossier/copy_into_thesis_appendix.md
```

### Stage 13 - Vertical Slice («Власна справа»)

Runs E9. New stage in v2.

Required outputs:

```text
13_vertical_slice_vlasna_sprava/trinity_bundle.json
13_vertical_slice_vlasna_sprava/identification_proof_chain.json
13_vertical_slice_vlasna_sprava/evidence_dossier.md
13_vertical_slice_vlasna_sprava/causal_estimates_with_cis.csv
13_vertical_slice_vlasna_sprava/transport_bounds_uk_ua.json
13_vertical_slice_vlasna_sprava/multi_method_rank_with_cis.csv
13_vertical_slice_vlasna_sprava/oblast_simulation_outcomes.csv
13_vertical_slice_vlasna_sprava/fairness_decomposition.csv
13_vertical_slice_vlasna_sprava/contestability_packet_full.json
13_vertical_slice_vlasna_sprava/audit_chain_for_policy.json
13_vertical_slice_vlasna_sprava/e9_vertical_slice_summary.md
```

### Stage 14 - Sensitivity Surface

Runs E10. New stage in v2.

Required outputs:

```text
14_sensitivity_surface/e_values_per_estimand.csv
14_sensitivity_surface/rosenbaum_bounds_grid.csv
14_sensitivity_surface/tornado_plot_data.csv
14_sensitivity_surface/gamma_break_table.csv
14_sensitivity_surface/e10_sensitivity_summary.md
```

### Stage 15 - Frontier Method Opt-In (BayesianBART)

Runs E11. New stage in v2.

Required outputs:

```text
15_frontier_optin/bart_run_config.json
15_frontier_optin/cate_posterior_per_sector.csv
15_frontier_optin/bart_vs_causal_forest_comparison.csv
15_frontier_optin/bart_diagnostics.md
15_frontier_optin/e11_frontier_optin_summary.md
```

## 9. Recommended Final Launch Profile

### 9.1 Default Profile (v2)

Use this profile unless the preflight says it is too heavy for available
quota. v2 keeps the breadth parameters of v1 but actually executes the
bootstrap and adds new stage parameters.

```text
threads = 12
policy_count = 192
fabric_dataset_limit = 8000
metric_binding_limit = 12000
academic_evidence_limit = 3000

# E3 multi-DGP gauntlet
causal_panel_rows = 750000
direct_foundry_subsample_rows = 12000
heavy_method_subsample_rows = 5000
dgp_count = 6
heavy_methods_per_dgp = 8
bootstrap_replicates = 200             # genuinely executed in v2
crossfit_folds = 5
random_seeds = 32

# E3b discovery
discovery_algorithms = pc, fci, ges, dagma, pcmci
discovery_bootstrap_resamples = 100
discovery_panel_rows = 50000

# E4 transportability
transport_bootstrap_resamples = 200

# E5 robust tournament
uncertainty_worlds = 160
scenario_seeds = 64
ranking_methods = topsis, robust_topsis, regret_min, ahp_weighted, electre_iii
ranking_bootstrap_resamples = 100
ranking_bootstrap_world_subsample = 100

# E6 simulation
agent_count = 220000
simulation_months = 30
simulation_seeds = 64
shortlist_size = 32
macro_scenarios = baseline_2026, intensified_conflict, partial_recovery

# E7 fairness
applicant_profiles = 200000
applicant_distribution_per_family = stratified
bias_injection_policy_count = 3
fairness_bootstrap_resamples = 200

# E8 ablation
ablation_variants = 8                  # binding semantics

# E9 vertical slice
vertical_slice_program = vlasna_sprava_canonical
vertical_slice_family = microgrant_restart

# E10 sensitivity
rosenbaum_gamma_grid = 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0

# E11 BART opt-in
bart_chains = 4
bart_burnin = 1000
bart_samples = 2000
bart_max_runtime_seconds = 1800
```

### 9.2 Deadline-Safe Profile (v2)

Use this if less than 3 hours remain.

```text
threads = 12
policy_count = 128
fabric_dataset_limit = 4000
metric_binding_limit = 6000
academic_evidence_limit = 1500

# E3 multi-DGP gauntlet (reduced)
causal_panel_rows = 400000
direct_foundry_subsample_rows = 8000
heavy_method_subsample_rows = 3000
dgp_count = 4                    # drop nonlinear_confounding and positivity_violation
heavy_methods_per_dgp = 6        # drop modern DiD ensemble and SCM
bootstrap_replicates = 100

# E3b discovery (reduced)
discovery_algorithms = pc, ges, dagma           # drop fci, pcmci
discovery_bootstrap_resamples = 50

# E4 transportability
transport_bootstrap_resamples = 100

# E5 robust tournament
uncertainty_worlds = 100
scenario_seeds = 48
ranking_methods = topsis, robust_topsis, regret_min   # drop ahp_weighted, electre_iii
ranking_bootstrap_resamples = 50

# E6 simulation
agent_count = 160000
simulation_months = 24
simulation_seeds = 48
shortlist_size = 24
macro_scenarios = baseline_2026, intensified_conflict   # drop partial_recovery

# E7 fairness
applicant_profiles = 120000
bias_injection_policy_count = 3   # mandatory; do not reduce
fairness_bootstrap_resamples = 100

# E8 ablation
ablation_variants = 6
ablation_semantics = binding

# E9 vertical slice (mandatory)
vertical_slice_program = vlasna_sprava_canonical

# E10 sensitivity (mandatory but smaller grid)
rosenbaum_gamma_grid = 1.0, 1.5, 2.0, 2.5, 3.0

# E11 BART (deferrable)
enable_frontier_optin = false
```

### 9.3 Stretch Profile (v2)

Use this only if the first stages complete very quickly and at least 5 hours
remain.

```text
threads = 22-32
policy_count = 256
fabric_dataset_limit = 12000
metric_binding_limit = 18000
academic_evidence_limit = 5000

# E3 multi-DGP gauntlet (extended)
causal_panel_rows = 1000000
direct_foundry_subsample_rows = 20000
heavy_method_subsample_rows = 8000
dgp_count = 8                    # add interference and missingness DGPs
heavy_methods_per_dgp = 10
bootstrap_replicates = 300

# E3b discovery (extended)
discovery_algorithms = pc, fci, ges, dagma, pcmci, lingam
discovery_bootstrap_resamples = 200

# E4 transportability
transport_bootstrap_resamples = 300

# E5 robust tournament (extended)
uncertainty_worlds = 240
scenario_seeds = 96
ranking_methods = topsis, robust_topsis, regret_min, ahp_weighted, electre_iii, promethee
ranking_bootstrap_resamples = 200

# E6 simulation (extended)
agent_count = 300000
simulation_months = 36
simulation_seeds = 96
shortlist_size = 48
macro_scenarios = baseline_2026, intensified_conflict, partial_recovery, energy_crisis

# E7 fairness (extended)
applicant_profiles = 300000
bias_injection_policy_count = 5    # add 2 more bias templates
fairness_bootstrap_resamples = 300

# E8 ablation
ablation_variants = 10              # add discovery_only and bart_only ablations

# E11 BART (full)
enable_frontier_optin = true
bart_chains = 6
bart_samples = 4000
```

## 10. Expected Timing (v2)

For the 12-vCPU profile:

| Stage group | Expected time | Notes |
| --- | ---: | --- |
| 00-02 preflight, inventory, input freeze | 5-15 min | Mostly I/O and metadata |
| 03 policy formalization | 5-15 min | Deterministic templates dominate |
| 04 evidence retrieval | 10-25 min | DuckDB and JSONL scans |
| 05 causal benchmark (6 DGPs × 8 methods × 200 boots) | 60-90 min | Main risk; bootstrap parallelized over 12 cores |
| 05b causal discovery ensemble | 20-40 min | 5 algorithms with per-algo timeout 5 min |
| 06 transportability with bootstrap | 5-15 min | Matrix scoring + 200 resamples |
| 07 robust tournament (5 methods × 100 boots) | 30-50 min | Vectorized; bootstrap is the heavy part |
| 08 agent/network simulation × 3 scenarios | 30-60 min | Three runs of pilot's 10-min simulation |
| 09 fairness with bias injection + bootstrap | 15-25 min | 23 policies × 200 resamples |
| 10-11 ablation/adaptivity/audit | 10-25 min | Reuses previous outputs; binding-semantics check |
| 12 final dossier | 5-15 min | Markdown/CSV/JSON assembly |
| 13 vertical slice deep dive | 20-45 min | Re-runs subset of E1-E8 on one policy |
| 14 sensitivity surface | 5-15 min | Tornado/E-value computation |
| 15 frontier optin (BayesianBART) | 20-40 min | Capped by `bart_max_runtime_seconds` |

Target total: 4-6 hours.

Hard cap: 6 hours wall clock. If the run exceeds 6 hours, stop only after
stage boundaries and preserve all completed stage artifacts. Stage 15 is
optional — if previous stages over-run, skip stage 15 and mark E11 as
`deferred` in the limitations file.

## 11. Launch Commands

The v2 implementation should provide a runner:

```text
policy-engine/tools/ops/experiments/run_msme_final_fresg_suite_v2.py
```

The v2 runner may import and reuse the existing v1 runner
(`run_msme_final_fresg_suite.py`) for stages 00-12 but must add stages
05b, 13, 14, 15 and replace the bootstrap / multi-DGP / multi-method /
bias-injection logic in stages 05, 07 and 09.

### 11.1 Preflight Command

```bash
cd /mnt/experiments/polisyos/policy-engine
source /mnt/experiments/msme_final_fresg_evaluation_v2_20260501/activate_environment.sh

python tools/ops/experiments/run_msme_final_fresg_suite_v2.py \
  --mode preflight \
  --workdir /mnt/experiments/msme_final_fresg_evaluation_v2_20260501 \
  --repo-root /mnt/experiments/polisyos/policy-engine \
  --production-data /mnt/experiments/msme_final_fresg_evaluation_v2_20260501/input/production_data \
  --gcs-prefix gs://lex-1-494208-data/experiments/msme_final_fresg_evaluation_v2_20260501 \
  --threads 12
```

### 11.2 Full Run Command

```bash
cd /mnt/experiments/polisyos/policy-engine
source /mnt/experiments/msme_final_fresg_evaluation_v2_20260501/activate_environment.sh

python tools/ops/experiments/run_msme_final_fresg_suite_v2.py \
  --mode run \
  --profile default \
  --workdir /mnt/experiments/msme_final_fresg_evaluation_v2_20260501 \
  --repo-root /mnt/experiments/polisyos/policy-engine \
  --production-data /mnt/experiments/msme_final_fresg_evaluation_v2_20260501/input/production_data \
  --gcs-prefix gs://lex-1-494208-data/experiments/msme_final_fresg_evaluation_v2_20260501 \
  --threads 12 \
  --policy-count 192 \
  --fabric-dataset-limit 8000 \
  --metric-binding-limit 12000 \
  --academic-evidence-limit 3000 \
  --causal-panel-rows 750000 \
  --direct-foundry-subsample-rows 12000 \
  --dgp-count 6 \
  --heavy-methods-per-dgp 8 \
  --bootstrap-replicates 200 \
  --enable-bootstrap true \
  --discovery-algorithms pc,fci,ges,dagma,pcmci \
  --discovery-bootstrap-resamples 100 \
  --transport-bootstrap-resamples 200 \
  --uncertainty-worlds 160 \
  --scenario-seeds 64 \
  --ranking-methods topsis,robust_topsis,regret_min,ahp_weighted,electre_iii \
  --ranking-bootstrap-resamples 100 \
  --agent-count 220000 \
  --simulation-months 30 \
  --simulation-seeds 64 \
  --shortlist-size 32 \
  --macro-scenarios baseline_2026,intensified_conflict,partial_recovery \
  --applicant-profiles 200000 \
  --applicant-distribution stratified \
  --enable-bias-injection true \
  --bias-injection-policies bias_geo_kyiv_only,bias_credit_history_3y,bias_male_only \
  --fairness-bootstrap-resamples 200 \
  --ablation-variants 8 \
  --ablation-semantics binding \
  --enable-vertical-slice true \
  --vertical-slice-program vlasna_sprava_canonical \
  --enable-sensitivity-surface true \
  --enable-frontier-optin true \
  --frontier-method bayesian_bart \
  --bart-chains 4 --bart-burnin 1000 --bart-samples 2000 \
  --bart-max-runtime-seconds 1800
```

### 11.3 Resume Command

```bash
python tools/ops/experiments/run_msme_final_fresg_suite_v2.py \
  --mode run \
  --resume \
  --run-id <existing_v2_run_id> \
  --workdir /mnt/experiments/msme_final_fresg_evaluation_v2_20260501 \
  --repo-root /mnt/experiments/polisyos/policy-engine \
  --production-data /mnt/experiments/msme_final_fresg_evaluation_v2_20260501/input/production_data \
  --gcs-prefix gs://lex-1-494208-data/experiments/msme_final_fresg_evaluation_v2_20260501 \
  --threads 12
```

### 11.4 Stage-Only Rerun Command

```bash
python tools/ops/experiments/run_msme_final_fresg_suite_v2.py \
  --mode run \
  --resume \
  --run-id <existing_v2_run_id> \
  --stages 05_causal_benchmark,05b_causal_discovery,07_robust_policy_tournament,13_vertical_slice_vlasna_sprava,12_final_dossier \
  --workdir /mnt/experiments/msme_final_fresg_evaluation_v2_20260501 \
  --repo-root /mnt/experiments/polisyos/policy-engine \
  --production-data /mnt/experiments/msme_final_fresg_evaluation_v2_20260501/input/production_data \
  --gcs-prefix gs://lex-1-494208-data/experiments/msme_final_fresg_evaluation_v2_20260501 \
  --threads 12
```

## 12. Reproducibility Requirements

A final run is reproducible only if these are present:

| Requirement | Required artifact |
| --- | --- |
| Exact command | `_replay/replay_command.sh` |
| Effective configuration | `_manifests/effective_config.json` |
| Code version | `02_input_freeze/code_version.json` |
| Python packages | `_manifests/python_freeze.txt` |
| OS and CPU | `01_capability_inventory/runtime_environment.json` |
| Input paths and hashes | `02_input_freeze/input_manifest.json`, `input_hashes.jsonl` |
| Random seeds | `_manifests/random_seed_manifest.json` |
| Stage outputs | every stage folder contains `experiment_result.json` |
| Sync status | `_logs/gcs_sync_*.json` |
| Claim boundary | `12_final_dossier/limitations_and_claims_boundary.md` |
| Artifact inventory | `12_final_dossier/artifact_inventory.md` |

The final runner must use deterministic seeds for all synthetic and simulation
stages. If any stage is intentionally stochastic, it must write the seed list.

## 13. Error Handling and Typed Failures

The suite must prefer typed partial results over silent failure.

Allowed stage statuses:

```text
completed
completed_with_warnings
partial
skipped_by_design
blocked_missing_input
failed_typed
failed_untyped
```

Rules:

- `failed_untyped` is not thesis-grade and must be investigated.
- `blocked_missing_input` is acceptable if the missing data is documented.
- A downstream stage may proceed only if it can mark the upstream evidence as
  missing or weak.
- No downstream stage may pretend that missing evidence is successful evidence.

## 14. Claim Boundary Rules

### 14.1 Allowed Claims

The final suite may support claims that:

- PolicyOS can formalize MSME policy problems into reproducible artifacts.
- PolicyOS can integrate legal, dataset and academic evidence in one workflow.
- Foundry can run identification-aware causal diagnostics on a benchmark with
  known ground truth.
- Robust scenario analysis changes policy ranking compared with mean-only
  ranking.
- Graph-aware simulation provides useful scenario stress tests for wartime
  MSME policy.
- Governance/fairness/recourse checks can block, qualify or escalate outputs.
- The full pipeline can be replayed from manifests and GCS artifacts.

### 14.2 Disallowed Claims

The final suite must not claim that:

- the top-ranked policy is proven to be best in reality;
- simulated outcomes are forecasts;
- semi-synthetic causal estimates are real program impact estimates;
- external evidence is automatically transferable to Ukraine;
- LLM policy generation replaces legal drafting or democratic accountability;
- all legal amendments were fully enriched if amendment scan/enrichment was
  deferred;
- all Foundry methods were executed.

## 15. Success Criteria (v2)

The v2 run is successful if all conditions hold:

- E1-E11 complete or produce typed, defensible partial artifacts.
- At least 128 policies enter the tournament.
- At least 100 uncertainty worlds complete.
- All 6 DGPs complete in E3 with at least 5 methods per DGP and 150 of 200
  bootstrap replicates per cell.
- E3 method disagreement matrix shows non-zero disagreement on at least 3
  DGPs (otherwise the gauntlet is too easy).
- E3b emits a consensus DAG with edge-level reliability scores from at
  least 3 of 5 algorithms.
- All policy families receive evidence posture labels.
- All 8 ablation variants complete and at least 4 show non-zero top-10
  Jaccard distance from `full_policyos`.
- E5 reports robust-score 95% CI for every top-30 policy.
- E5 emits a `statistically_tied_shortlist` with at least 3 policies whose
  CIs overlap with the top-ranked policy.
- E6 runs all 3 macro scenarios and emits a `scenario_fragility_table`.
- E7 catches all 3 bias-injected policies with `reject_until_review` and
  matching `bias_reason`.
- E9 produces a vertical-slice dossier with at least 4 causal estimators,
  E-values, transport bounds, contestability packet and audit chain for
  the depth-case policy.
- Final dossier contains a top policy shortlist, a tied shortlist and a
  limitations file.
- GCS sync verification succeeds.
- Replay command is generated.

The v2 run is excellent if:

- 192 or more policies enter the tournament;
- 160 or more uncertainty worlds complete;
- agent/network simulation covers at least 24 shortlist policies under all
  3 macro scenarios;
- E11 BayesianBART completes with R-hat < 1.05 on all chains;
- fairness violation detection has true-positive rate of 3 of 3 and false-
  positive rate ≤ 25%;
- multi-method ranking agreement: all 5 ranking methods agree on at least
  4 of the top-10 policies;
- FRESG before/after table is directly usable in the thesis;
- all final Markdown summaries can be copied into Section 3 or Appendix B
  with minimal editing.

## 16. Thesis Tables and Figures to Produce (v2)

The v2 dossier should include data for these thesis artifacts:

| Artifact | Source stage | Intended thesis location |
| --- | --- | --- |
| Table: FRESG before/after PolicyOS | E1 | Section 3.8 |
| Table: H1-H6 verdicts | E1-E8 | Section 3 conclusion |
| Table: evidence posture by policy family | E2 | Appendix B |
| Table: causal method × DGP grid (6 × 8) | E3 | Section 3.8 |
| Figure: causal estimator disagreement matrix | E3 | Section 3.8 or Appendix B |
| Figure: sensitivity/bounds tornado | E3, E10 | Appendix B |
| Figure: Rosenbaum bound surface (Γ × estimand) | E10 | Appendix B |
| Table: discovery ensemble F1 vs prior DAG | E3b | Appendix B |
| Figure: consensus DAG with edge reliability | E3b | Appendix B |
| Table: transportability verdicts with CIs | E4 | Section 3.8 |
| Table: robust top-10 with 95% CIs | E5 | Section 3.8 |
| Table: statistically tied shortlist | E5 | Section 3.8 |
| Figure: robust Pareto frontier | E5 | Section 3.8 |
| Table: multi-method rank stability (5 methods × top-30) | E5 | Section 3.8 |
| Figure: region-sector heatmap (per scenario × 3) | E6 | Appendix B |
| Table: scenario fragility (rank shifts across 3 scenarios) | E6 | Section 3.8 |
| Table: fairness violation detection (TP/FP per bias type) | E7 | Section 3.8 |
| Table: human-gate cases with bias_reason | E7 | Appendix B |
| Figure: ablation top-10 set diff (Jaccard per variant) | E8 | Appendix B |
| Table: binding ablation dropouts | E8 | Appendix B |
| Box: vertical slice depth case («Власна справа») | E9 | Section 3.8 |
| Figure: BayesianBART CATE posterior per sector | E11 | Appendix B |
| Text box: claim boundary | E8 / final dossier | Section 3.8 |
| Appendix: replay protocol | final dossier | Appendix B |
| Comparison table: v1 pilot vs v2 results | final dossier | Appendix B |

## 17. Independent Reproduction Protocol

An independent reviewer should be able to reproduce the run as follows:

1. Obtain the PolicyOS repository at the recorded commit or artifact bundle.
2. Obtain the exact input bundle listed in `02_input_freeze/input_manifest.json`.
3. Create a VM with at least the resources in Section 4.1.
4. Install dependencies according to the recorded environment manifest.
5. Run `_replay/replay_command.sh`.
6. Compare output hashes and summary metrics with
   `12_final_dossier/artifact_inventory.md`.
7. Inspect `limitations_and_claims_boundary.md` before interpreting results.

The replay protocol must not depend on local hidden files, shell history, IDE
state or unrecorded credentials. If API keys are needed for optional LLM policy
generation, the replay protocol must also support deterministic no-LLM replay.

## 18. Security and Cost Controls

Rules:

- Never print API key values.
- Sync stage outputs to GCS after each stage.
- Do not delete VM or disk until GCS sync verification succeeds.
- Stop the VM after final sync if no further analysis is running.
- Keep temporary files under the experiment workdir.
- Do not write final artifacts only to local VM disk.

Recommended post-run commands:

```bash
gcloud storage ls -r gs://lex-1-494208-data/experiments/msme_final_fresg_evaluation_20260501/<run_id>/
gcloud storage du -s gs://lex-1-494208-data/experiments/msme_final_fresg_evaluation_20260501/<run_id>/
gcloud compute instances stop <vm-name> --zone=<zone> --project=lex-1-494208
```

## 19. Final Interpretation Template

Use this template in the thesis after the run:

```text
The final experiment suite evaluated PolicyOS as an infrastructure for
evidence-informed MSME policy design under martial-law uncertainty. The suite
did not attempt to estimate the definitive real-world causal effect of existing
programs. Instead, it tested whether the system can formalize policy problems,
assemble legal/data/academic evidence, run identification-aware causal
diagnostics, evaluate transportability, stress-test policy alternatives across
uncertainty worlds, simulate heterogeneous agent/network response, perform
fairness and recourse checks, and produce a replayable audit trail.

The results should therefore be interpreted as system-validation and
decision-support evidence. Where the suite uses semi-synthetic data or proxy
simulation, the outputs demonstrate method behavior and policy robustness under
specified assumptions. Where real production datasets, Lex artifacts and
Academic/Fabric evidence are used, the outputs demonstrate evidence coverage,
readiness and claim qualification. The boundary between these evidence types is
explicitly recorded in the final dossier.
```

## 20. Implementation Notes for the v2 Runner

The v2 runner reuses code from:

```text
policy-engine/tools/ops/experiments/run_msme_final_fresg_suite.py    # v1 pilot
policy-engine/tools/ops/experiments/run_msme_grand_tournament_v2.py  # legacy
```

Required improvements over the v1 pilot runner:

- **Genuine bootstrap**: stage 05, 06, 07, 09 must execute the
  `bootstrap_replicates` parameter, not just record it. Use
  `concurrent.futures.ProcessPoolExecutor(max_workers=12)` with
  per-replicate seeds.
- **Multi-DGP gauntlet (E3)**: 6 DGPs implemented as deterministic
  generators with seeded outcomes; expose `dgp_specifications.json` as
  reproducibility artifact.
- **Causal discovery (E3b)**: new stage; wrap PC, FCI, GES (causal-learn);
  DAGMA (dagma); PCMCI (tigramite). Apply per-algo timeout. Aggregate
  consensus DAG with edge presence count and bootstrap-based reliability.
- **Multi-method ranking (E5)**: implement TOPSIS, robust TOPSIS,
  regret-min, AHP, ELECTRE-III. Bootstrap by world-subset resampling.
- **Macro scenarios (E6)**: parameterize the world generator with three
  named macro presets; emit per-scenario heatmap.
- **Bias injection (E7)**: 3 deterministic policy templates with
  documented bias mechanism; verify detection in E7 summary.
- **Binding ablation (E8)**: ablation logic must apply structural
  drop-out rules, not additive penalties. Each variant must report a
  `dropout_count` per family.
- **Vertical slice (E9, new stage 13)**: implement as a thin wrapper that
  re-runs E1-E8 logic restricted to one canonical policy.
- **Sensitivity surface (E10, new stage 14)**: E-value via
  VanderWeele-Ding formulation; Rosenbaum bound by gamma-grid sweep.
- **Frontier opt-in (E11, new stage 15)**: BayesianBART via `pymc-bart`
  or `bartpy`. Enforce `bart_max_runtime_seconds` so the stage cannot
  blow past the 6-hour budget.
- **`v2_vs_pilot_comparison.md`** in stage 12: side-by-side comparison of
  pilot run (`msme_final_fresg_evaluation_20260501_20260430-092000`) and
  v2 run on key metrics (top policy, robust score, ablation rank shift,
  fairness uniformity, causal method disagreement).
- record `execution_mode` for every method result:
  `foundry_pure_step`, `foundry_quickstart`, `deadline_adapter`,
  `proxy_simulation`, `deterministic_scoring`, `bootstrap_aggregated`,
  `frontier_optin`, `not_run_capability_only`.

### 20.1 Code Layout

```text
policy-engine/tools/ops/experiments/run_msme_final_fresg_suite_v2.py
policy-engine/tools/ops/experiments/v2/
  dgp_generators.py            # 6 DGPs for E3
  bootstrap_engine.py          # parallel bootstrap utility
  discovery_ensemble.py        # E3b
  ranking_methods.py           # 5 methods for E5
  macro_scenarios.py           # 3 scenarios for E6
  bias_injection.py            # 3 bias templates for E7
  binding_ablation.py          # binding-semantics ablations for E8
  vertical_slice.py            # E9 deep dive
  sensitivity_surface.py       # E10
  frontier_optin_bart.py       # E11
  pilot_comparison.py          # v2 vs v1 diff table
```

### 20.2 Parallelization Strategy

- E3 bootstrap: 6 DGPs × 8 methods × 200 replicates = 9 600 fits;
  parallelism over replicates with 12 workers.
- E5 bootstrap: 5 methods × 100 resamples = 500 ranking runs; parallelize
  across resamples with 12 workers.
- E6 scenarios: 3 scenarios × 32 shortlist policies; parallelize across
  policies with 12 workers per scenario, sequential across scenarios.
- E11 BART: 4 chains parallelized natively by `pymc`.
- All other stages remain single-process (vectorized scoring is fast).

## 21. Final Go / No-Go Checklist (v2)

Go if all are true:

- this v2 design document exists in `policy-engine/docs`;
- v2 runner exists at
  `policy-engine/tools/ops/experiments/run_msme_final_fresg_suite_v2.py`;
- v2 runner preflight passes;
- GCS write test passes for the v2 prefix;
- production data is present;
- Lex final artifacts are resolvable for at least the vertical-slice
  program («Власна справа»);
- Foundry imports pass, including DML ML-nuisance learners;
- Fabric DuckDB query pass;
- discovery libraries (causal-learn, dagma, tigramite) importable, or E3b
  explicitly downgraded with documented rationale;
- BART library (`pymc-bart` or `bartpy`) importable, or E11 explicitly
  marked as `deferred`;
- agent baseline files are present;
- final v2 output prefix is empty or intentionally marked as a resume target;
- pilot run is preserved at its original prefix and is not overwritten;
- user confirms this is the final defense run, not another pilot.

No-go if any are true:

- GCS write fails;
- input freeze cannot be written;
- no final dossier can be produced;
- code import fails in cloud;
- available disk is too low (less than 80 GB free);
- bootstrap engine cannot allocate worker processes;
- LLM failure would block all policy generation (deterministic templates
  must remain functional);
- the only possible output would be untyped failure logs.

### 21.1 Acceptable Degradations

If a non-critical component is unavailable, the run may proceed with
documented degradation:

- E3b discovery: at least 3 of 5 algorithms must run; failed algorithms
  are recorded with typed reason.
- E11 BART: deferred is acceptable but must be recorded in the limitations
  file; this leaves one bullet on the limitations list and is preferable to
  silent omission.
- E6 macro scenarios: minimum 2 of 3 scenarios; the missing scenario must
  be explicitly listed.
- E7 bias injection: all 3 bias policies must run; if any bias policy
  fails to instantiate, the run is no-go.
