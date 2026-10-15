# Subject-Matter Program Cards

[Overview](README.md) · [Initial portfolio](first_portfolio.md) · [Conditional branches](branches.md)

Each card describes a sustained capability trajectory. “First increment” is the first complete useful result; “Transfer check” is a substantively different case that tests whether the decision transfers; the mature goal is a supported class of tasks. These levels have no common timeline and are not mandatory sequential releases. If the required input or method already exists, there is no need to complete a separate program to create it first.

All proposals below are analytical. Named owners are existing architectural areas, not new appointments. Read code confirms form and some relationships, but not a new successful run. E02 outputs are consumed only within the scope where their owners actually establish a result.

## E1 Measurement and Source Semantics

### Useful capability

The system turns sources into observations and relationships fit for a specific question. It answers not only “is there a field?” but “what does it measure, for which population, at what time, under what selection process, and with what uncertainty?” A useful result may be a descriptive measure, a verifiable evidence map, a distributional estimate, or an explicitly bounded measurement input to a model.

This connects semantic extraction, units and time coordinates, subject identity, observation frame, measurement error, missingness, censoring, and joint population structure. They are grouped around one mutable object: the relationship between observed material and the quantity in the question. This does not justify building one universal ontology.

Examples of new questions: Is an amount contractual or actually paid? Does unemployment registration imply absence of employment? Can two records be joined to one organization after a reorganization? What can be said about risk at a horizon when only censored outcomes are available? Which distributional consequences are equally compatible with published marginal tables?

### Existing foothold and exact increment

Data Forge already has kernel/domains/read_api, normalizers, snapshots, and schemas. Fabric stores provenance, temporal branches, and quality information. ObservationRecord carries unit, period, coverage, source, mode, censoring, and a declared identification mode. Foundry actually materializes PER_CELL and household cells and uses a measurement-aware adapter when the relevant bundle is present.

These mechanisms reduce new-code scope. They do not establish that coverage_estimate was measured, that a confidence coefficient is calibrated, that the selected frame represents the required population, or that quality can be turned into a standard error. The current default adapter multiplies quality discounts; this is a declared weighting rule, not a general correction for MNAR, censoring, or measurement error.

Scientific texts have source/snippet carriers and real lexical links in Scholar. Semantic correspondence needs independent grounds that preserve negation, exceptions, subject, comparison, and context. Lexical supported is not elevated to proven entailment. The academic corpus has signed-adjudication checks and excludes retracted work in some computations; scientific suitability and completeness of later retraction handling remain separate properties.

### Increments

- **First increment.** One question and one preselected source or small group of independent sources. Preserve the original value, definition, identifiers, units, period, availability, and transformation through to the actual reader. For a document task, a “supports / contradicts / not established” map without a probabilistic badge is acceptable. For a numeric source, a correct descriptive result is sufficient when no causal claim is made.
- **Transfer check.** Change more than the ID: use another source family, measure definition, censoring regime, subject reorganization, or temporal revision. A correct conclusion may change, while harmless formatting changes should not force refusal.
- **Mature goal.** Bounded measurement profiles with independent evaluation of false joins, missingness, and semantic errors; new cases are mostly added through profile and data, with known marginal verification cost.
- **Conditional extension.** Joint synthetic population, small-area estimation, multiple measurement channels, competing risks, and multimodal data. Each option gets its own question, observation model, and reference; matching marginal tables are not treated as an observed household.

For C7, a useful small scientific step is the absolute probability of a defined event by a horizon under justified endpoint, risk-set, and censoring assumptions. The current partial hazard is already useful within its scope, but renaming it does not create a probability. For Ukrainian D2, distinguish the source observation panel from separate synthetic method contracts: the presence of a selected workflow does not prove it uses observed outcomes and treatment.

### Architectural decision and effort

Prefer a narrow profile under an existing owner: first define the quantity and independent manual reference, then add the minimum native fields and reader. A full corpus rewrite, new shared compiler, or global alias registry is justified only by repeated demand and demonstrated shared semantics.

For a source map with producers and a consumer ready, the conditional first increment is 4–13 normalized days. A calibrated semantic profile with independent labels already available is a different complete package, 15–30 days; these estimates are not added. A new empirical measurement profile, absolute risk, suitable joint population, and new labels are not separately estimated. The main risk often lies in definitions and independent verification, not adapter length.

**Expected E02 outputs:** repaired source/byte/time bindings; B61 prepared-read consumers already integrated, with issuer/K_ref authority separately held; selected D3 optional-input inventory; LA-032 only for affected readers; required B31/B201/B202 uncertainty contracts. Their repair is not part of this program. Selecting publisher vintage, population frame, and error meaning remains substantive work.

### Verification and stop boundary

Strong comparators are a manual source table, direct count, or existing native method using the same information. A positive example must change a useful downstream answer. Material negatives: the same text with different negation; the same name with a different unit; two sources from one study family presented as independent; a contractual amount represented as a payment; a hidden observation group. Harmless controls: equivalent layout, permissible reordering, and the same meaning in another compatible representation.

Measure useful coverage of the declared question set, false support and false refusal, errors across material strata, and full verification cost. If the new route is no better than a good manual result, or a second profile requires a central fork without a new capability, stop expansion. If identification is unavailable, preserve the supported descriptive result.

**Relationships:** E2 receives fit-for-purpose constraints and learns what is missing; M1 receives a correct observation model; M2 distinguishes a change in the world from a change in registration; P3 receives an event frame. An error in shared identity or units, in contrast, propagates in all four directions. Reusing bytes does not make scientific criteria common.

**Primary sources:** docs/adr/0179-correspondence-vocabularies-meaning-principles-first-profiles-open.md, L58–78; docs/reference/data-capability-requirements.md, eight separate requirements; src/polisyos/ir/observation/contracts.py, L131–208; src/polisyos/foundry/calibration/measurement.py, L570–705; src/polisyos/data_forge/domains/ukraine/builders/sources.py, L1458–1620; Fabric Wave R1/R2/R5/R7/R8; GV-09/14/20/27/35/38/54.

## E2 Identification, Synthesis, and Basis Acquisition

### Useful capability

The system establishes which causal or transportable conclusion is supported by available evidence, which assumptions limit it, and which available action can actually change the answer. It can preserve multiple incompatible bases and useful bounds instead of forcing a single point or graph.

The program combines identification, evidence synthesis, transport, and acquisition because they close one question cycle: “what is known → what is missing → what would provide discriminating evidence → what changed in the same answer.” With a large independent stream of systematic reviews or independent experimental-design tasks, these branches could split; an additional method name alone does not warrant it.

### Existing foothold

Use existing causal/IR methods, Scholar and academic owners, CG1/CG2, RequiredDataSpec, N7/N13a/N13b, passport/overlay, AQ1, and VC1. Historical causal plans include accepted bounded results; an old “new theorem needed” list does not prove that a method is absent. Check the required estimator, its admissibility, and actual consumer separately.

Scientist already has a predictive VOI scheduler, its state, report, and consumption in the decision packet. In SBI, expected_information_gain is supplied as input; it is not a confirmed nested EVSI estimator. A new scheduler is not needed to compare the existing simple source-selection rule with a richer one. A separate S12 ValueOfInformationEstimate is described as a qualitative site/budget skeleton without a numeric VOI: coordinating five budgets is not an EVSI estimate and does not replace the existing predictive VOI path.

### Increments

- **First increment.** One precisely stated contrast or functional and a small set of admissible assumptions. Show a supported answer or its bounds. Then, if a genuinely executable discriminating route exists, obtain the required object through an existing owner and change the answer for the same case.
- **Transfer check.** An apparently similar gap requires a different basis: not more rows, but an assignment rule, measurement relation, joint observation, transport covariate, or competent act. The system should choose a different route or preserve the limitation with a reason.
- **Mature goal.** A catalogue of applicable causal/synthesis/acquisition profiles with explicit conditions, full costs, independent control tasks, and measured cost for a new source family.
- **Conditional extension.** Network interference, proxy/negative-control identification, publication selection, network meta-analysis, experimental design, and nested VOI. Fund these only for a new question and comparison with a strong simple method.

Full distribution recovery is not required if the target functional itself can be recovered. Likewise, a numeric proof of an optimal bound is conditional on its admissible set; it does not admit the scientific premises themselves. Do not choose an assumption merely because it yields the narrowest interval or mechanically intersect intervals from incompatible models.

### Conditional method-discovery and admissible-evidence profile

When the real answer depends on finding an existing method or certificate, a small E2/M1 profile is useful: requirements query → native method/IR catalogue search → selected and rejected candidates → premise check → resolution of a reference to an existing payload → actual downstream use. A strong comparator is manual selection from a known catalogue and direct execution of a suitable native method. Check a known admissible candidate, a similar but inadmissible one, stale index, no-hit, and a valid new catalogue entry that is found without new case-specific code. Recall has only its declared finite denominator; a “not found” record does not prove the basis exists nowhere.

Historical G2 and G3 have different completion conditions. G2 permits an honest causal/forecast domain ceiling after healthy search, preserved traces, method check, and freshness. G3 permits such an outcome for an individual query, but its stated slice closure requires at least one successfully resolved reference to a real typed certificate/proof payload and a complete downstream consumer chain. A universal refusal does not count as a positive result for this profile. These requirements preserve a useful class of questions; they do not fund a new universal proof engine or assert a fresh positive run.

Ordinary traces and control tasks are included in the selected package. A separate R branch appears only after a measured limitation of simple method selection; V research appears only for a genuinely new verification criterion. The standalone cost of this conditional profile is not yet set: a ready chain found may mean reuse, while a missing scientific basis requires different work.

### Decisions before code

First choose the target, admissible premises, and available wrong-making observations. Prefer a known bounded method and native result. General probabilistic VOI is justified only with supported probabilities of acquisition outcomes, a loss function, price, and horizon; until then, scenario comparison, dominance, or direct measurement is more useful.

A data gap, measurement gap, identification gap, semantic correspondence problem, and absence of permission call for different actions. A data object does not confer authority. Semantic correspondence, however, can itself be a substantive research question, not necessarily an external uncheckable postulate.

### Expected E02 outputs

Expected outputs: exact B09/R13 admission → overlay → WMR → repeated consumption; current context/basis and job scope; B61 for source reuse; numeric materializer for a numerical intervention. The 2024 percent_gdp source cannot be written into a USD stock profile before 2023-07 just because the names match. A successful carrier does not resolve this semantic conflict.

### Effort and acceptance

A narrow data-shaped route with admissibility ready and the chain repaired is conditionally estimated at 10–25 normalized days: discovery 1–3, decision 2–4, code 3–6, integration 2–5, verification 2–7. This is not the cost of field experimentation, general VOI, or a new theorem. Preparing a new causal-suitability decision may require research without a guaranteed positive result; absence of new code does not mean absence of work.

The reference is to obtain one known source manually, directly measure the needed quantity, apply an existing exact/native method, or retain a useful partial answer. Check fetched, admitted, consumed, and genuinely improved separately. Repeating a source is not new knowledge; a wrong country/unit/vintage fails; removing the actual consumer must eliminate the prior positive result. A new row with no change to the admissible answer does not prove acquisition payoff.

**Stop:** the new planner does not outperform a simple rule; the presumed shared nuisance is not confirmed; discovery does not distinguish the needed unknown; or the analysis costs more than the next action itself. Keep a small working catalogue of routes. Do not turn stopping into an invented conclusion that “data do not exist anywhere.”

**Relationships:** E1 supplies source semantics; E2 opens new M1/P1/P2 questions; M2 returns competing explanations for the next study. Source selection changes the calibration population, so prior labels do not transfer automatically. Multiple measurement channels may be useful only jointly: compare the complete package without assuming a universal greedy order.

**Primary sources:** Layer3 G2-causal-forecast-search-engine.md, L242–260/L1233–1385; G3-analytics-search-engine.md, L272–291; Layer2 S12-cold-start-resource-economics.md, L307–332; GY N7/N13a/N13b/AQ1/VC1; docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md, R1–R4; causal research/result lineage; GV-02/23/24/25/30/36/39/41; E02 OP-R13 and OP-R1-SYMBOLIC-MATERIALIZATION.

## M1 Joint Model, State, and Forecast

### Useful capability

The system answers questions about joint outcomes, state, and the future while preserving what matters for a specific functional: dependence, information slice, observation, model structure, and alternative regimes. The mean of each quantity separately may be insufficient for a difference risk, joint constraint, tail, or policy choice.

The program distinguishes four subjects: parameter estimation, estimability of the required quantity, state under a fixed model, and forecasting. Good fit does not establish causal identification; a narrow numerical error does not imply narrow model uncertainty; smoothing with future data is not a forecast available at the historical time.

### Foothold and increments

Reuse Foundry calibration/uncertainty, existing state and model owners, IR/ValueOuterSet, WMR, native forecasting/backtesting, and the current packet. Development means obtaining a suitable joint object, scientific verification, and preservation through to a specific consumer, not creating a new general world store.

The morning reported-local slice from October 1 clarifies B197: the internal Calibrator → persisted CalibrationReport v2 → welfare Delta/MC chain is already integrated. The report-owned scalar-group-to-field projection and shared covariance owner preserve tied/singular Normal dependence without jitter. For mixed non-Normal withholding, a candidate point and a separate robust outer bound remain. The receipt reports 58/58; the underlying witness was not independently checked or run in this research. This internal mechanism is not ordered again.

The unconfirmed production input has an exact boundary. The frozen census at 28ea3bb found no production construction of Calibrator/CalibratorInputs or executable put_calibration_report caller; this is not a full current census at 8b40f8f5. In addition, the shared inputs.calibration_report_ref reaches a Blueprint caller expecting FunnelCalibrationReport@1.0, while B197 retains Foundry CalibrationReport@2.0. This is a reachable internal typed-intake seam, without proof of served B197 production or authority emission. Qualify the specific producer and schema/kind dispatch of the existing consumer; do not build a new covariance engine. Local-read sources: B197_COVARIANCE_RECEIPT.md, L3–24; OPEN_PREMISES.md, L1158–1168; run_policy_blueprint_runtime.py, L502/L577/L1075–1079; exact paths and reported hashes are in sources.json.

- **First increment.** One required functional from an already suitable joint law or bounded model family, such as the difference in consequences of two measures under shared uncertainty. An independent finite calculation distinguishes two joint laws with identical marginals.
- **Transfer check.** Another observation regime, later revision, new horizon, or target where the prior covariance is insufficient. Check which part of reuse actually preserves meaning.
- **Mature goal.** Supported models and forecast profiles with diagnostics for global alternatives, multimodality, prior sensitivity, regime support, calibrated predictive error, and explicit state transfer between modules.
- **Conditional extension.** Hierarchical forecast reconciliation, nowcasting, mixed frequency, model averaging, SBI, dynamic microsimulation, and joint tails. First establish applicability and a strong direct/structural baseline, then consider a more complex estimator.

Forecasting becomes a separate program when there is a recurring consumer with its own horizons, vintages, distributional forecasts, and rolling out-of-time evaluation. One new model in the general catalogue remains an M1 branch. A separate program would share data preparation and custody but have its own estimate of forecast utility and operational cycle.

### Architectural alternatives

Prefer native modules with an exact target and preserved relationships. A full joint model and a cut model answer different inferential questions: preventing feedback between modules changes the distribution, not only the computational plan. Choose according to the task and misspecification risk, with separate verification.

Choose representation by functional. Joint moments may suffice for some questions; a nonlinear tail or event probability may require ordered joint draws or another native object. Do not require every method to emit the same set of samples in advance. Compression is acceptable only after proving that it preserves the required question.

**Conditionally consumed E02 outputs:** once a semantic owner separately adopts B31/B201/B202, keep point/interval/joint channels distinct; B197's internal covariance/report/welfare path is already integrated, with configured producer and typed intake still separate in the required scope; B194 draw provenance and permitted treatment of failures; B169–B171 temporal profile, repetitions, and metric weights; exact graph/ExecPlan/horizon on the selected N5 path. Repairing any of these is not itself a new scientific result for M1.

### Effort, verification, and stopping

One new pairwise functional over already suitable joint draws is conditionally estimated at 10–25 normalized days. This does not cover a new empirical joint law, every survival/tail/SAE option, or scientific validity of transitions. A substantial part of the work concerns target, dependence, and an independent reference even when the formula is short.

Compare exact/direct native calculation, a transparent small model, and an existing forecaster on the same information set. Check identical marginals with different dependence; unit changes; a mean outside an equal-tail interval; unavailability of later observations at an earlier forecast origin; and actual requested/started/completed replicates. Do not declare convergence from an outcome-distribution width or failure to reject a null improvement.

Stop if a new functional does not change a useful answer, a more complex model fails to transfer to a holdout regime, or the resulting precision is entirely created by an unsupported prior/measurement weight. Preserve a bounded model-conditional answer or a set of alternatives instead.

**Relationships:** P1 receives a correct joint evaluation; P2 gets transitions and available signals; M2 gets a pre-defined forecast and diagnosable residual. A shared model input may speed several consumers substantially, but a wrong joint law contaminates their decisions and any later “confirmation.”

**Primary sources:** GV-10/28/44/45/48; Foundry Methods T1/T3/T18/T19/T20/T28; docs/plans/active/layer2-slices/S10-outcome-prediction-welfare-comparison.md; E02 B31/B169–B171/B194/B197/B201/B202 and OP-R13-N5.

## M2 Diagnosis and Learning About the World

### Useful capability

The system distinguishes which explanations of a prediction/observation discrepancy are supported: delivery, measurement, model, behavior, context, or a combination. It selects a useful next check. After a separately adopted update rule, new admissible knowledge may change the world version and genuinely affect the next research cycle.

This is a separate program: choosing a good research tool does not change knowledge about a policy effect. A preserved update record also does not prove that the causal diagnosis was correct.

### Three explicit outcomes

- **O1 Diagnosis.** A pre-defined prediction, version of the intervention actually delivered, and mature observation are compared accounting for exposure, assignment, missingness, censoring, and registration process. The result may be compound or unresolved, with a discriminating next action.
- **O2 Hypothesis.** A detected shift produces candidate_unverified and a question for confirmatory research. Statistical detection and FDR do not establish a causal relationship.
- **O3 Admitted world change.** After a live producer, required scientific evidence, and an adopted update policy, a new coupling/mechanism/required-data object passes the existing passport/overlay and creates a branch consumed by the next cycle.

O2 is optional for O1/O3. DS21 requires **O1 AND O3**. Early O1 uses an existing reviewer diagnostic artifact; it does not wait for a new dashboard or PR1 promotion. WP01/WP02 still constrain posterior mutation and routine assimilation; code readiness does not mean they have been adopted.

### Foothold and increments

Reuse O0, S13, Observation/VC1, DDM where applicable, CalibrationReport, CAS, N12/N13b, ClaimLedger, continuous-governance, and partial reissue. Event and historical-transition mechanisms already exist; new work is content-bound comparison/diagnosis and admissible scientific basis for update.

The **first increment** starts with one mature retrospective case: correctly distinguish at least one material alternative from model error and change the next check. A strong baseline is a short monitoring report and explicit cause table. If no genuinely mature observation exists, mechanism work may end with explicitly model-based examples; this is not empirical learning.

A **transfer check** presents a residual of similar magnitude with a different supported cause: policy-induced reporting change, delayed outcome, different composition of observed subjects, or delivery failure. For O3, a separate second case is a correction/retraction with targeted withdrawal of current use while preserving history.

The **mature goal** is a known domain of diagnosable comparisons, useful uncertainty outside that domain, and confirmed expansion of the class of subsequent questions. New world versions and alert counts are not by themselves program impact.

Preserve the S13 accountability branch: an observed next step and its closure, response to ineffective review, targeted expansion/shrink/hold/split of admissible scope, and time to respond to disconfirmation. Use existing lifecycle/revision owners. Procedural memory updates, public record, and knowledge about effects are routed separately; observing follow-through does not grant automatic O3 permission or authority to execute an institution's action. Source: docs/plans/active/layer2-slices/S13-post-deploy-accountability-learning.md, L302–434/L626–660/L1168–1183.

### Decisions, effort, and verification

Prefer a transparent evidence/cause table, then a set-valued contributor model only if it actually helps choose an experiment. Defer a general learned cause classifier until an independent corpus exists: identical residuals may have different causes, and a forced single label creates false attribution.

For narrow prepared O1, estimates of 15–30 and 20–40 normalized days reflect different temporal/compound scope. The selected portfolio retains one explicitly described package; the estimates are not averaged. O2 and O3 are separate increments, not implicit additions to O1. Real wait for outcomes, access, adjudication, and the update-policy decision is not estimated in engineering days.

**Expected E02 outputs:** version-bound source/context, correct comparisons/replicates/uncertainty for the selected path, exact B26 diagnostics, lineage and currentness. O1 receives no update authority from a repair receipt. LA-055 precedence, live-feed applicability, and LA-054 validity capability retain separate scopes.

Verification requires held-out prediction and refuting evidence, reviewer access to alternative causes, measurement-versus-delivery controls, and a useful next action. O3 requires actual consumption by the next branch and independent negative mutations, including self-confirmation quarantine. Reprocessing everything does not make policy-induced observations independent confirmation.

**Stop:** diagnosis does not change the next check; accuracy is achieved by dropping difficult cases; labels do not distinguish causes; or no update policy exists. Preserve the comparison/limitation service and do not claim automatic model correction.

**Relationships:** E1/P3 supply observation and execution semantics; E2 gets new discriminating requests; P2 gets a future ability to react to a signal. The dangerous feedback occurs when one model produces a forecast, explains its own miss, and confirms its own update.

**Primary sources:** GY O1/O2/O3/AS2/AS3/VC1; GY §8.5 and L5394–5497/L5731–5743; docs/system-design-decisions/withheld-propositions-register.md, WP01/WP02/WP09/WP10; Atlas DS21; Scientist BIC 2.6/R8; GV-06/22/44/45.

## P1 Joint Design and Meaningful Choice

### Useful capability

The system turns a request into correctly composed obligations, generates executable alternatives, and compares them as wholes. It preserves exactly which action was evaluated, how shared resources and interactions constrain the set, and why several alternatives may remain incomparable.

This includes intent/facet/obligation synthesis, separation of candidate/bundle/blocking frontier, measure composition, nondominated sets, and explicitly selected values. This preserves the ambition of universal policy design without requiring a large new synthesizer before the first useful case.

G6 retains another subject-matter capability: correctly decompose a request and use an existing bounded tool loop, explaining source/tool choices, rejected branches, and incompleteness. Arbitrary text does not mean arbitrary scope: actions are limited by the adopted G5 envelope. Orchestration readiness, grounded result, justified grounded abstention, and the earlier unchanged_blocker are distinct. A working chat/SSE does not yet confirm consumption of preserved orchestration decisions or compression losses. If a real limitation exists here, fund a specific request/consumer profile, not a new chat or universal orchestrator. Source: docs/plans/active/layer3-slices/G6-bounded-agent-arbitrary-request-grounded-result-or-abstention.md, L191–288/L710–987/L1198–1535/L2486–2543.

### Existing foothold

Reuse the current WorkspaceLoop, N1–N6, S2/S5, CouplingGraph/CompositionReceipt, native policy search, PolicyEvaluationVector, Scientist ParetoRegistry, S8/PA1, and CanonicalDesignRecord. The registry already stores candidate hash/ref, evaluation, and seed payload; the controller updates and reads it. Do not claim that the entire frontier is missing based on a narrower Foundry NSGA2 output.

Important residual scope includes the actual default/served consumer and the required objective, eligibility, and source-population basis. B109/B110/B111 preserve their own E02 scopes. Behavior of separate NSGA2 on an empty feasible set and OPTIMAL status still requires owner reconciliation; it does not automatically become a funded scientific program.

### Increments

- **First increment.** A small finite family of measures with full exact enumeration. Preserve admissible actions and outcome vectors, select again under the declared constraint/value profile, and reproduce the result from preserved objects.
- **Transfer check.** A different interaction structure: shared resource, a component depending on another, or conflicting normative schedules. A simple sum of separately admissible actions is no longer sufficient.
- **Mature goal.** A supported compositional policy space where new questions are expressed through existing rules and profiles, good alternatives do not disappear due to screening, and the cost of the second case is measurably lower than bespoke development.
- **Conditional extension.** Mechanism design, matching, auctions, multi-level optimization, and richer robust choice only if the real question requires their specific actors, messages, incentives, and constraints.

Scientific evaluation uncertainty, search incompleteness, and disagreement about values remain separate. A heuristic-search frontier is not called a complete optimum. Changing the menu must not silently change the utility scale. Matching objective vectors do not erase different actions and execution conditions.

### Participation and values

Participation is a source of a specific kind of basis, not just good UX. Surveys, testimony, deliberation, and complaints need population, sampling, consent, sponsor, dissent, and permitted claim use. A consultation may establish the existence of an objection without estimating its prevalence. Preferences inferred from behavior do not assign public weights. The S7 decision workflow does not create S8 value authority.

A model demonstration can honestly explore several specified value schedules without appointing an institution. For an actual recommendation, the basis for choice and competent act remain separate inputs. The system should preserve alternatives and disagreement until that choice.

### Architecture, effort, and verification

Preference: use the existing native frontier and evaluator, a small finite model, then exactly the missing preservation/read/use/presentation. Build a Foundry→Scientist bridge only for a named need; a second registry is unnecessary. Evaluate critic diversity by additional errors found and full cost against rules and one strong baseline, not by the number of personas.

The conditional narrow first increment is estimated at 10–30 normalized days with given admissible coefficients and existing carriers. A new grammar, empirical coupling, participation campaign, and protected normative recommendation are excluded. If the native route already fully solves the chosen task, the capability delta may be only demonstration of use or zero.

**Expected E02 outputs:** B109 strict dominance and the required run/tenant/cell frontier consumer; B110 metric/split/unit/direction basis; B111 independent observability of source eligibility and all-invalid disposition; N2/N5/N8 repairs only if the selected model uses the corresponding route. A numerical legal do and grounded world graph are not implied by registry readiness.

Control battery: pairwise pass/global fail; remove the actual action while preserving score; unsupported alternative with an attractive objective; add an unselected extreme option; equivalent regrouping of components; reorder labels without changing the model. The reference uses the same inputs and admissible claims.

**Stop:** 2–3 good manual alternatives yield the same result for less cost; gain comes from hidden new weights; critics find no additional material errors; or joint support is unavailable. In the last case, a conditional model-based evaluation may still be useful, but not a claim about system effect.

**Relationships:** E1/E2/M1 provide the basis; P2 inherits action identity; P3 checks real compatibility. The number of alternatives can increase human workload, and shared scalarization may hide rare harm. These costs belong in the utility assessment.

**Primary sources:** PDC C18/C19/C34 and W6; Layer2 S2/S5/S7/S8/S9; GV-17/19/33/34/37; src/polisyos/scientist/methods/search/pareto_registry.py, L60–79/L242–306; controller L1100–1130; E02 OPT-01 B109–B111.

## P2 Adaptive Rules with Preserved Continuation

### Useful capability

The system answers: what should be observed, how should an action be selected after a signal, and what admissible continuation remains by the deadline? The output is a rule for available future histories, not one successful trajectory.

This is a separate trajectory because new information changes the class of admissible policies and the mathematical problem. A persistent unknown mechanism, stagewise switching, and rectangular ambiguity are not interchangeable settings of one backend. Resource admissibility, reachability of an end state, and safe continuation also do not follow from a good average reward.

### Foothold and exact current limit

Foundry contains nominal DP and two-stage stochastic programming. The inspected DP computes a stage × state policy but returns a value function and actions/states from one sampled trajectory. The two-stage method preserves first-stage x and a scalar expected recourse cost, not the full continuation table. Generic metadata means a small extension may be possible, but does not establish a rule contract, reload, or actual consumer.

P6.09 in docs/research/deep-research-value-distillation.md proposes one static AVaR/spectral family and its nested/rectangular time-consistent extension. These conditions are not a rule for all adaptive policies: exact finite-history/root-commitment evaluation may preserve a persistent/nonrectangular mechanism. Rectangularization for solver convenience changes the question.

Use existing temporal/DTR/strategic owners and S5 before a new planner. A separate Ukraine selected-input route does not follow from the presence of a corresponding DTO in another C7 or DTR consumer.

### Increments and cost boundary

**First increment — finite complete rule.** Two stages, a small action space, 2–3 explicitly defined persistent models, fixed signal/transition/history definitions. Full independent enumeration evaluates rules and finite continuation. One native consumer preserves, reloads, and applies the same rule on different admissible histories. Do not invent empirical coefficients.

**Extension — reusable class of rules.** If a real second consumer needs a new history/filtration/controller carrier, design it separately. A general nonrectangular solver, abstraction-to-concrete continuation certificate, and arbitrary horizons are outside the narrow first increment.

The **transfer check** changes the information pattern: delayed signal, partial observability, or persistent-model ambiguity. A new seed from the same model is not a second substantive case. The **mature goal** is supported classes of adaptive rules with verifiable continuation admissibility and known state-space growth limits.

The earlier 20–40 normalized days for the narrow first increment depended on a sufficient ready carrier/consumer. The fresh code trace did not establish that premise, so the range is **paused as the selected portfolio budget**. It is not averaged with the earlier broad estimate and is not automatically the cost of the expanded option. The next estimate starts with the exact rule-retention and consumer delta. This is a short verifiable design decision, not a reason to build a general framework indefinitely.

### Architecture and verification

Prefer a finite native extension with versioned information set and exact enumerator. The preserved rule must include available observations, timing, model family, actions, constraints, and out-of-support behavior. Separate a shared carrier only after two real consumers with the same meaning exist.

**Expected E02 outputs:** repaired action identity, temporal/horizon, source/context, numerical-result, and selected-input boundaries on the selected route. E02 does not choose persistent-versus-rectangular semantics, prove a transition law, or create authority to execute actions in an external institution.

Strong comparators are the best fixed program, nominal finite DP/two-stage, and full enumeration under the same information set. A positive question is required that a fixed rule genuinely cannot answer. Negatives: clairvoyance, favorable switching of a persistent model at each step, lost future resources, or action changes after evaluation. Harmless history recoding must preserve action and admissibility.

**Stop:** an advantage arises only from unavailable future information, a new hidden assumption, or imaginary empirical precision; a fixed policy is sufficient; or state-space growth cost is not justified by a useful question. Preserve a bounded finite result instead.

**Relationships:** P1 provides action identity, M1 transitions and signals, P3 capacity/timing, M2 future diagnosis. Unifying history and model too early may violate evaluation independence and make every static task more expensive.

**Primary sources:** GV-18/52/53 and persistent-model/viability updates; src/polisyos/foundry/methods/catalog/optimization/sequential.py, L294–362/L371–486; S5; E02 OP-R13-N5 and LA-023 for separate distinction between rollout and parameter training.

## P3 Execution, Scale, and Participant Response

### Useful capability

The system evaluates a program in terms of how it will be delivered: queues, staffing, shared resources, calendars, unfinished cases, and outcome observability. It then distinguishes how changes in coverage, network, and participant behavior alter effects. Formal executability, graph adjacency, or log fit alone does not establish this.

Examples: Does the queue shrink, or do unserved people simply disappear? Does a timestamp represent service start or registration? Does the result persist at another scale when nonparticipants are also affected? Does an independent outcome improve or only the reported KPI? Which resource makes two separately feasible measures incompatible?

### Existing foothold

Reuse QueueDES, ABM/coupling, existing interference/strategic methods, event/object observations, calibration, S5/S11/S13, and policy evaluator. A new general workflow executor for an external institution is unnecessary. S11 historically allows predictive upgrades for four axes but excludes mandate legitimacy: legitimacy cannot be obtained through an additional predictor.

Mature P3 goes beyond queues: for a specific question, account for administrative/fiscal/enforcement/delivery/coordination capacity and political feasibility, as well as compliance, gaming, capture, adaptation, and a change in the measurement instrument caused by the policy. These dimensions are not automatically included in a narrow ready-profile package estimated at 20–40 days; each needs its own inputs and verification. S11 L350–408/L602–643/L741–780 defines this ambition without granting predictive mandate authority.

DES runs in physical time, while the inspected joint caller specifies the number of steps by the number of intervals in the requested grid. Fixing this time relationship belongs to SIM-02/B22 and OP-R13. A separate scientific increment may then refine the grid at a fixed physical horizon and check error in the required functional. Do not multiply an event-based cash transfer by dt merely because a field is named income.

### Increments and estimate reconciliation

**First increment — a narrow existing process.** One read-only event-log family with established lifecycle/object definitions, a small QueueDES or subject-specific conditional profile, one held-out period, and an actual comparison consumer. Correctly distinguish waiting/service/registration, shared events, and unfinished cases.

This scope is conditionally estimated at **20–40 normalized days**: discovery 2–4, decision 3–6, code 5–10, integration 3–5, independent verification 7–15. It assumes a ready semantic basis for the log and an existing profile.

**Extension — a new empirical observation profile.** Requires genuine event/object/lifecycle data, a separate observation model, independent outcome channel, new shared-resource or censoring semantics, and a transferable profile. The earlier broad estimate of 45–120 days included this wider work and is not the minimum for the narrow option. It is withdrawn as the baseline estimate; the expanded option is not separately estimated until data and consumer are selected. Do not explain the discrepancy solely as a “more complex solver.”

The **transfer check** changes load regime, registration rule, shared service, or exposure network. Holdout must check a useful predicted change, not only the same in-sample trace. The **mature goal** is reusable capacity/scale/strategic modules with their own empirical suitability scope and targeted diagnosis.

**Conditional extensions:** network scale, equilibrium multiplicity, dynamic games, and incentives for reporting. Strategic market/mechanism design becomes a separate program only for recurring problems with defined actors/messages/private information and its own deviation/equilibrium witnesses. Requiring IC/IR for every descriptive or non-mechanism policy is incorrect.

### Architecture and verification

Start with a simple subject-matter process model and source adapter. Connect only a block that materially interacts with it. A national ABM, full digital twin, and general process-mining layer are premature until a simple queue/count/duration baseline fails on a useful question.

**Expected E02 outputs:** B18 missing-versus-zero, B19 comparator in the same model/horizon, B21 actual replication/error, B22 physical horizon/step, B26 persisted diagnostics, and the required source/optional-input inventory. Consume these repairs without duplicating their budget. They do not create exposure support, correct event semantics, or empirical knowledge of behavior.

A positive result changes which program is admissible or locates a specific decisive limitation. Checks: a shared payment is not multiplied by number of objects; completion-only timestamps are not called service duration; rejected/unfinished cases stay in the denominator; new registration is not turned into a reform effect; recipient-only data do not confirm absence of spillover harm. Strong comparators are a manual process map, counts/durations, simple queue, and transparent saturation/exposure model.

**Stop:** only the same log fit improved; object relationships must be invented; a richer ABM does not change the choice; or response is unidentified. Preserve a descriptive/conditional model or answer bounds, not a causal forecast based on a convenient log.

**Relationships:** P2 receives real time/resource constraints; M2 gets alternatives for model-versus-delivery attribution; E1 gets the necessary denominator; E2 gets missing exposure/assignment evidence. A negative interaction is fundamental: the policy itself changes how observations are produced, so old calibration and holdout may cease to apply.

**Primary sources:** GV-06/21/22/32; Layer2 S5/S6/S11/S13; src/polisyos/foundry/coupling/executor.py, L70–165; des_kernel.py, L143–150/L296–319; coupler.py, L129–162; joint_simulation_horizon.py, L1670–1722; E02 SIM-02 and OP-R13.

## What the Cards Share and What Remains Separate

Shared work may include question version, source inventory, artifact references, one reader, control infrastructure, and a full cost trace. Scientific suitability, legitimacy of choice, human comprehension, and runtime independence do not transfer automatically through these references.

Each selected increment needs: a supported positive case, a material negative case, a harmless change, removal of the actual consumer, a substantively different second case, and a targeted response to revision. This is a list of testable properties, not a requirement for a new universal evaluator. Verification is already included in the package; the [shared-cost register](dependencies.md) prevents paying for it twice.
