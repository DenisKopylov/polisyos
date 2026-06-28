<!--
Archived source-of-truth for the policy-design search/selection target specification.
Algorithm: RACE-HOG-PODS v3.2 (Robust Active Certified Explorer for
Honest-Grounded Partially-identified Optimistic Discovery Search).
Authored externally (multiple human + agent contributors); imported 2026-06-27.
This is the verbatim specification text (extracted from the source .docx).
The PolicyOS reading, mapping, adoption decisions, and what-we-defer live in the
decision record: docs/system-design-decisions/policy-design-search-target-spec.md
Do NOT treat this file as a build plan: §27 of this spec is a greenfield phase plan
that, under our no-parallel-worlds law (P27/P28), is SUPERSEDED by the GY plan's
subordination mapping. Read the decision record first.
-->

RACE-HOG-PODS v3.2

# Полная спецификация робастного алгоритма HONEST-GROUNDED POLICY DESIGN SEARCH
Назначение документа. Этот документ задает полную математико-инженерную спецификацию алгоритма RACE-HOG-PODS v3.2: Robust Active Certified Explorer for Honest-Grounded Partially-identified Optimistic Discovery Search. Алгоритм предназначен для поиска policy designs в грамматически порождаемом пространстве композиций атомарных интервенций, когда истинная целевая ценность частично идентифицирована, proxy-метрики ненадежны без калибровки, допустимость и grounding валидируются отдельным firewall, а приобретение данных может сужать идентификационные множества для целых регионов дизайнов.
Центральный контракт.
Explore optimistically.
Promote conservatively.
Separate world evidence, simulation, surrogate belief, structural assumptions and normative obligations.
Never allow a proxy score, LLM rationale or simulator-only output to become a promotion certificate.
Returned object алгоритма не является одним «лучшим» дизайном. Возвращается стратифицированный набор объектов:
DecisionFront_t      - только сертифицированные grounded/admissible designs;
ResearchFront_t      - перспективные, но не промотированные shadow designs;
QuarantineFront_t    - подозрительные high-proxy/high-gap designs для adversarial validation;
PortfolioFront_t     - сертифицированные портфельные политики, если randomized/portfolio deployment сам сертифицирован;
CertificatePackage_t - минимальный пакет доказательств для каждой публичной frontier-точки.

# Содержание
Статус и основные принципы алгоритма
Формальная постановка задачи
Слои неопределенности и объект credal state
Состояние алгоритма
Представление policy design
Статусная lattice-схема дизайна
Идентификация и set-valued values
Calibration, transportability и data trust
Honest comparison и decision rules
Четыре фронта алгоритма
Показатели качества: LHV, CHHV, robust choice и gaps
Validator/firewall и система обязательств
Confidence accounting и safety ledger
Oracles и transitions: evaluation, simulation, acquisition
Model revision epochs и stale certificates
Graph-causal surrogate и misspecification control
Grammar/LLM/MCTS search
Acquisition portfolio
Nonstationary meta-controller и phase policy
VOI planning: rectangularity, scenario trees, bundles
Полный алгоритм RACE-HOG-PODS v3.2
Карта переходов и инварианты
Теоремы и доказательные контуры
Regret, gaps и метрики
Вычислительные подпрограммы
Инженерные структуры данных и API
План реализации
Тестирование и benchmark-протокол
Практические параметры
Ограничения утверждений
Сжатая математическая спецификация
Пример одного шага
Возвращаемый пользователю пакет сертификатов
Глоссарий
Заключение

# 1. Статус и основные принципы алгоритма

## 1.1. Что считается разработанным алгоритмом
RACE-HOG-PODS v3.2 - не одна acquisition function и не один surrogate. Это политика последовательного принятия решений над состоянием поиска:
B_t = (
  K_t,
  X_raw_t, X_shadow_t, X_quarantine_t, X_cert_t, X_blocked_t,
  F_dec_t, F_res_t, F_quar_t, F_port_t,
  Tree_t,
  Sur_t,
  CertState_t,
  RiskLedger_t,
  Meta_t,
  Budget_t,
  Epoch_t
).
На каждом шаге алгоритм выбирает действие:
alpha_t in {
  expand(prefix),
  mutate_or_refine(x),
  evaluate(x, mode),
  certify(x, obligation),
  acquire(u),
  adversarial_validate(x),
  audit_model_or_calibration(scope),
  compress_archive(epsilon)
}.
Действия имеют разный смысл. `expand` и `mutate_or_refine` создают candidate designs, но не дают evidence о мире. `evaluate` может быть simulation-only, retrospective estimation, sandbox pilot, field pilot или deployment evaluation; каждый режим имеет отдельный safety gate. `certify` проверяет proof obligations и может промотировать дизайн только через promotion gate. `acquire` получает данные или экспериментальные сведения, которые могут сузить внешний credal state для региона дизайнов. `adversarial_validate` атакует proxy-gap, fake-grounding, omitted-coupling и validator-boundary случаи. `audit_model_or_calibration` проверяет пригодность assumptions, calibration scope, data trust и simulator drift. `compress_archive` сжимает архив без потери сертифицированной epsilon-покрываемости.

## 1.2. Принцип разделения слоев
Алгоритм хранит и использует разные объекты для разных задач:
K_world_t  - внешний credal set о возможном мире, сужаемый только внешним evidence;
K_stat_t   - anytime-valid statistical confidence constraints;
K_id_t     - идентификационные constraints and bounds;
K_cal_t    - proxy-to-true calibration constraints with scope;
K_impl_t   - implementation/normative/admissibility constraints;
K_sim_t    - computational/simulation uncertainty;
Pi_sur_t   - surrogate posterior/belief for search only.
Ключевое правило:
K_world_t не сужается на основании одной симуляции из текущей модели.
Pi_sur_t не является сертификатом.
K_sim_t не является evidence о внешнем мире.
Structural assumptions не получают statistical validity автоматически.
Normative obligations не являются objective coordinates, если они hard constraints.

## 1.3. Promotion separation
Алгоритм допускает оптимизм в исследовании, но запрещает оптимистичную рекомендацию:
LLM, grammar proposer, surrogate, MCTS and optimistic VOI may propose and prioritize.
Only validator/firewall plus valid evidence may promote.
Design может иметь высокий upper proxy value, высокую expected hypervolume improvement и убедительное natural-language rationale, но оставаться в shadow или quarantine, если нет grounding, identification, calibration, admissibility и value certificate.

## 1.4. Условность safety claim
Safety claim относится к статистическим и формально проверяемым компонентам при поддерживаемых structural, calibration, implementation и normative assumptions. Корректная форма:
P_data,oracle(
  false promotion occurs
  | maintained structural assumptions, declared obligation language,
    calibration scope assumptions, data trust assumptions, implementation semantics
) <= delta.
Алгоритм также поддерживает model-revision epochs. Если текущая assumption language расширена или обнаружена некорректной, предыдущие certificates становятся epoch-scoped или stale и требуют revalidation.

# 2. Формальная постановка задачи

## 2.1. Модель мира
Мир описывается расширенным объектом:
M = (V, G, F, Theta, I, Cal, Obs, Cost, Risk, Impl, Eq, Meas, Norm).
Где:
`V` - канонизированные переменные: outcomes, mediators, confounders, costs, risks, fairness variables, implementation variables;
`G` - causal graph: DAG, mixed graph, time-unrolled graph, dynamic SCM graph или equilibrium graph;
`F` - mechanisms / structural assignments;
`Theta` - параметры механизмов;
`I` - identification map for estimands;
`Cal` - proxy-to-true calibration relations;
`Obs` - наблюдательные, экспериментальные и measurement источники;
`Cost` - cost model for evaluation/acquisition/certification;
`Risk` - hard safety constraints and risk bounds;
`Impl` - implementation semantics and operational constraints;
`Eq` - equilibrium / feedback semantics;
`Meas` - measurement process and manipulation sensitivity;
`Norm` - legal, ethical, institutional and stakeholder obligations.
Истинный мир `M*` неизвестен. Алгоритм не предполагает, что все аспекты `M*` статистически верифицируемы. Он поддерживает внешний допустимый класс:
K_t = K_world_t ∩ K_stat_t ∩ K_id_t ∩ K_cal_t ∩ K_impl_t ∩ K_norm_t.
Для вычислений и поиска также поддерживаются:
K_sim_t   - uncertainty of simulation / numerical approximation;
Pi_sur_t  - probabilistic surrogate belief;
Q_t       - credal family of surrogate posteriors for robust acquisition scoring.

## 2.2. Атомарная интервенция
Атом интервенции:
a = (op, tau, pi, epsilon, scope, preconditions, declared_evidence, implementation_mode).
Компоненты:
`op` - оператор: subsidy, tax, mandate, cap, audit, default, disclosure, randomized encouragement, eligibility rule, matching, public information, procurement change и др.;
`tau in V` - целевой слот;
`pi in Pi_op` - параметры оператора;
`epsilon` - заявленный causal/effect claim;
`scope` - популяция, время, geography, institutional unit, measurement scope;
`preconditions` - условия применимости;
`declared_evidence` - claimed rationale, not a certificate;
`implementation_mode` - regime of deployment or evaluation.
Атомы порождаются grammar `Gamma`, но raw output не считается атомом до прохождения parse/canonicalization/type validation.

## 2.3. Композиционный дизайн
Design:
x = <a_1, ..., a_k>.
Композиция имеет typed intervention hypergraph:
H_x = (V_x, E_x, T_x, P_x, EFF_x, DEP_x, SCOPE_x, MODE_x).
Где:
`V_x` - переменные, затронутые дизайном;
`E_x` - coupling/dependency edges между атомами;
`T_x` - targets;
`P_x` - параметры;
`EFF_x` - declared effects;
`DEP_x` - dependencies on mechanisms, graph regions, data, calibration, implementation, equilibrium and measurement processes;
`SCOPE_x` - область применения;
`MODE_x` - intended evaluation/deployment semantics.
Generated set:
X_t = X_raw_t ∪ X_shadow_t ∪ X_quarantine_t ∪ X_cert_t ∪ X_blocked_t.
Полное пространство `X` может быть бесконечным. Гарантии поиска разделяются на discovered-space, finite-slice, proposal-coverage and truncation components.

## 2.4. Многокритериальная цель
Все координаты нормируются так, чтобы максимизация была предпочтительна:
Y(x) in R^d.
Типовые координаты:
target outcome;
negative cost;
negative risk;
fairness margin;
robustness margin;
distributional welfare;
implementation feasibility when not a hard gate;
externality score;
uncertainty or regret margin.
Hard constraints не следует смешивать с обычными objectives. Если нарушение constraint недопустимо, оно остается gate:
Risk_j(x) <= threshold_j
а не просто координата `-risk_j` в hypervolume.
Для фиксированного расширенного состояния `kappa`:
v_kappa(x) = E_kappa[Y(do(x))].
`kappa` включает не только модель `M`, но и proxy, measurement, calibration, implementation and equilibrium uncertainty:
kappa = (M, xi_proxy, theta_cal, theta_meas, theta_impl, theta_eq, theta_data, theta_norm).
Value set:
V_t(x) = { v_kappa(x) : kappa in K_t^kappa } subset R^d.
Для promotion используется не произвольная posterior credible region, а certified outer value set:
V_out_t(x) superset { v_kappa*(x) } on the good event.

## 2.5. Oracles
Evaluation oracle:
O_e(x, mode) -> Z_e(x, mode).
Modes:
simulate_only
retrospective_estimate
measurement_audit
sandbox_pilot
field_pilot
deployment_evaluation
Только некоторые modes дают world evidence. `simulate_only` уточняет computational uncertainty или surrogate training data, но не сужает `K_world_t`.
Acquisition oracle:
O_a(u) -> Z_a(u).
Acquisition action может:
собрать новый dataset;
получить proxy calibration data;
провести randomized pilot;
получить instrument или exogenous variation;
улучшить linkage;
измерить mediator/confounder;
провести implementation audit;
проверить measurement process;
расширить population coverage.
Acquisition влияет на регион:
R_t(u) = R_graph_t(u) ∩ R_id_t(u) ∩ R_front_t(u) ∩ R_scope_t(u).
Если region uncertainty велика, используется outer affected region, чтобы не пропустить revalidation:
R_true_t(u) subseteq R_out_t(u).

# 3. Слои неопределенности и объект credal state

## 3.1. Расширенный credal state
Основной объект для honest reasoning:
K_t^kappa = K_world_t × K_proxy_t × K_cal_t × K_meas_t × K_impl_t × K_eq_t × K_data_t × K_norm_t
            ∩ K_stat_t ∩ K_id_t.
Здесь product notation условна; на практике компоненты могут быть coupled. Например, calibration uncertainty зависит от population scope, measurement process and policy regime.
Алгоритм хранит joint credal process:
F_t = { f_kappa : X_t -> R^d, kappa in K_t^kappa }.
Это необходимо, потому что value uncertainty по разным designs не независима. Сравнение через marginal intervals может быть чрезмерно консервативным или некорректным, если забыта общая зависимость от одного мира.

## 3.2. World evidence versus simulation
World evidence:
real data, valid experiment, measurement audit, external instrument, calibration sample,
verified administrative data, formal proof under declared assumptions.
Simulation evidence:
Monte Carlo draws from current simulator, numerical integration, SCM rollout,
agent-based simulation under assumed mechanisms.
Правило:
World evidence may shrink K_world_t if accompanied by valid confidence/proof constraint.
Simulation may shrink K_sim_t or train Pi_sur_t, but does not shrink K_world_t by itself.
Для simulator-based design evaluation output может быть:
sim_value_interval(x), MC_error(x), simulator_assumption_scope(x), discrepancy_risk(x).
Но promotion требует независимого grounding path:
simulator output + simulator validation + scope certificate + value outer set + assumptions.

## 3.3. Statistical validity versus structural assumptions
Statistical confidence sets могут иметь probability coverage:
P(for all t: theta* in CS_t) >= 1 - alpha.
Structural assumptions usually have maintained-assumption status:
AssumptionStatus in {declared, externally_supported, stress_tested, violated, out_of_scope}.
Алгоритм не превращает structural assumption в statistical guarantee. Safety theorem формулируется conditional on maintained assumptions.

## 3.4. Normative obligations
Legal, ethical, institutional and stakeholder constraints не являются random variables того же типа, что causal parameters. Они задают obligation language:
O_norm(x) = { legal_scope, fairness_floor, no_forbidden_targeting, accountability, rights_protection, ... }.
Если obligation hard, оно идет в promotion gate. Если obligation tradeable, оно может быть objective coordinate, но это должно быть явно указано stakeholder utility map.

## 3.5. Open-world channel
Алгоритм поддерживает indicator:
OpenWorldRisk_t(scope) = risk that true deployment situation is outside declared model/obligation/calibration scope.
Если OpenWorldRisk превышает threshold:
freeze promotion for affected scope;
mark affected certificates as stale or scope-insufficient;
expand model class or obligations;
revalidate affected designs.

# 4. Состояние алгоритма

## 4.1. Полный state object
B_t = (
  K_world_t, K_stat_t, K_id_t, K_cal_t, K_meas_t, K_impl_t, K_eq_t, K_norm_t,
  K_sim_t,
  Pi_sur_t,
  X_raw_t, X_shadow_t, X_quarantine_t, X_cert_t, X_blocked_t,
  F_dec_t, F_res_t, F_quar_t, F_port_t,
  Tree_t,
  CertState_t,
  ObligationIndex_t,
  DependencyIndex_t,
  SolverCache_t,
  RiskLedger_t,
  Meta_t,
  Budget_t,
  Epoch_t
).
`RiskLedger_t` tracks risk spending for certificates. It is an internal control object, not the user-facing result. User-facing output contains only certificate summaries needed to interpret public frontier points.

## 4.2. Pool semantics
X_raw_t:
  raw generated strings or uncanonicalized proposals.
 
X_shadow_t:
  syntactically and semantically parsed designs that are not blocked but not certified.
 
X_quarantine_t:
  designs with high proxy upside, high proof gap, OOD pattern, calibration suspicion or validator-boundary risk.
 
X_cert_t:
  promoted designs that passed all active promotion gates in the current epoch.
 
X_blocked_t:
  designs with certified failure, joint infeasibility, hard policy violation, or invalid syntax.
A design can move:
raw -> shadow -> cert
raw -> blocked
shadow -> quarantine
quarantine -> shadow
quarantine -> blocked
cert -> stale_cert or revalidation_required after epoch revision
Promotion is append-only inside a fixed epoch, but current validity is epoch-scoped.

## 4.3. State invariants
Within an active epoch:
F_dec_t subseteq X_cert_t subseteq X_t.
F_res_t subseteq X_shadow_t ∪ X_cert_t.
F_quar_t subseteq X_quarantine_t.
F_port_t subseteq PortfolioDesigns(X_cert_t) that passed portfolio certification.
For any `x in X_cert_t`:
Admissible_t(x) = certified_true;
Grounded_t(x) = certified_true;
ValueOuter_t(x) valid under active certificate scope;
IdentificationCert_t,j(x) valid for every objective j claimed in output;
EvaluationSafety_t(x) valid if any real-world evaluation has been executed;
DataTrust_t(evidence used for x) valid.

# 5. Представление policy design

## 5.1. Canonical pipeline
raw proposal
  -> parse
  -> AST
  -> canonical AST
  -> typed intervention hypergraph H_x
  -> obligation set O(x)
  -> shadow design
  -> evaluated/certified design
  -> frontier candidate.
Каждый переход имеет invariant. Raw text, JSON, LLM output or human note cannot skip canonicalization.

## 5.2. Canonical ID
id(x) = Hash(
  Gamma_version,
  canonical_AST,
  normalized_parameters,
  scope,
  implementation_mode,
  semantics_version
).
Idempotence:
canonicalize(canonicalize(x)) = canonicalize(x).
Semantic duplicate detection uses:
same canonical AST;
same typed targets;
same normalized parameters up to tolerance;
same scope and implementation semantics;
equivalent obligation graph.

## 5.3. Typed intervention hypergraph
H_x = (Nodes, HyperEdges, Types, Targets, Parameters, Effects, Dependencies, Scope, Semantics).
Hyperedges represent:
atom composition;
shared target;
budget coupling;
implementation dependency;
measurement process interaction;
feedback/equilibrium link;
legal/ethical incompatibility;
data/calibration dependency.
This hypergraph is the input to:
obligation compiler;
affected-region computation;
graph-causal surrogate;
dominance witness cache;
portfolio-as-design compiler;
archive compression;
model revision revalidation.

## 5.4. Equilibrium semantics
Each design has:
equilibrium_semantics in {
  none,
  static_SCM,
  dynamic_SCM,
  time_unrolled_SCM,
  equilibrium_SCM,
  game_model,
  agent_based_model,
  unsupported
}.
If objectives are affected by feedback and semantics is `unsupported`, the design cannot be grounded for those objectives. A residual surrogate may flag a candidate for investigation, but does not certify equilibrium validity.

## 5.5. Evaluation mode semantics
Each design and oracle call specifies:
evaluation_mode in {
  simulation_only,
  retrospective,
  measurement_audit,
  sandbox_pilot,
  field_pilot,
  deployment
}.
Real-world modes require `EvalSafety` before execution. Promotion safety and attempted-evaluation safety are distinct.

# 6. Статусная lattice-схема дизайна

## 6.1. Status vector
For each design:
z_t(x) = (
  z_syn,
  z_type,
  z_adm,
  z_ground,
  z_id_1,...,z_id_d,
  z_val_1,...,z_val_d,
  z_cal,
  z_data,
  z_meas,
  z_impl,
  z_eq,
  z_norm,
  z_eval_safety,
  z_prov,
  z_epoch
).
Each coordinate is partially ordered, not necessarily scalar.

## 6.2. Grounding status
blocked < raw < shadow < supported < grounded.
`raw`: not parsed;
`shadow`: parsed and not blocked, but not fully grounded;
`supported`: has partial evidence but missing one or more obligations;
`grounded`: all active grounding obligations satisfied under declared scope;
`blocked`: impossible, invalid, hard-violating or jointly infeasible.

## 6.3. Identification status per objective
z_id_j(x) in {blocked < proxy < partial < point}.
This is per objective. A design can be point-identified for cost, partial for welfare and proxy for fairness. For scalarization `gamma`:
id_t(x; gamma) = min_{j: gamma_j > 0} z_id_j(x).

## 6.4. Certificate strength as partial order
Certificate comparison is partial:
Cert_t(x) >=_cert Cert_t(y)
only if the comparison is meaningful across active assumptions, risk budgets, scope, calibration and obligations. If design A relies on monotonicity while design B relies on exclusion restriction, and neither assumption set is known weaker, then:
Cert_t(A) parallel Cert_t(B).
Scalar certificate scores may be used for exploration ranking, but not for certified dominance when assumptions are incomparable.

## 6.5. Stale and epoch-scoped status
z_epoch(x) in {current_valid, epoch_valid, stale, revalidation_required, invalid_under_current_epoch}.
A design may remain historically valid relative to a previous epoch while not being valid under current model/obligation language. Public decision front uses only `current_valid` designs.

# 7. Идентификация и set-valued values

## 7.1. Why point estimates are insufficient
Standard BO assumes an unknown function:
f: X -> R^d.
Policy/intervention search under partial identification requires:
x -> V_t(x) subset R^d.
Value set may be:
point or narrow set under point identification;
interval/polytope under partial identification;
wide set under proxy identification;
disjoint scenario set under structural ambiguity;
calibration-slack set under proxy-to-true uncertainty;
implementation-dependent set under deployment uncertainty;
equilibrium-dependent set under feedback ambiguity.

## 7.2. Identification certificate
For each objective `j`:
Cert_id_t,j(x) = (
  status,
  estimand,
  identifying_formula_or_bound,
  assumptions,
  assumption_status,
  proof_object,
  statistical_risk,
  model_class_scope,
  data_scope,
  calibration_scope,
  measurement_scope,
  implementation_scope,
  equilibrium_scope,
  width,
  epoch
).
`status` alone is never enough. A point-identified estimate under a strong untested assumption may be less decision-relevant than a partial bound under weaker and better supported assumptions.

## 7.3. Value outer sets
Promotion requires certified outer set:
V_out_t(x) superset {v_kappa*(x)} on good event and under active assumptions.
Representations:
interval box;
polytope through support functions;
scenario set with certified convex hull;
ellipsoid;
zonotope;
implicit support-function oracle;
outer approximation from robust optimization.
If only uncertified samples exist, they can train the surrogate but cannot define `V_out_t(x)` for promotion.

## 7.4. Support-function representation
For directions `lambda in Lambda subset S_+^{d-1}`:
l_lambda,t(x) = inf_{v in V_t(x)} lambda^T v;
u_lambda,t(x) = sup_{v in V_t(x)} lambda^T v.
Outer polytope:
V_out_t(x) = { v in Y_box :
  LCB_lambda,t(x) <= lambda^T v <= UCB_lambda,t(x)
  for all lambda in Lambda
}.
Conditions for discretization claims:
Y_box compact;
support function Lipschitz in chosen norm;
Lambda covers the relevant dual cone;
nonconvex sets are conservatively convexified unless a nonconvex representation is certified.
Discretization error is explicit:
epsilon_Lambda <= L_support * mesh(Lambda).

## 7.5. Joint process dominance
Honest dominance uses the joint process:
F_t = {f_kappa : X_t -> R^d, kappa in K_t^kappa}.
For pairwise comparison:
D_j,t(x,y) = inf_{kappa in K_t^kappa} [ f_kappa,j(x) - f_kappa,j(y) ].
Value dominance:
x >=_V,t y iff D_j,t(x,y) >= 0 for all j.
Fallback if coupled optimization unavailable:
inf V_j(x) >= sup V_j(y) for all j.
This fallback is safe but conservative. Solver timeout or approximation failure returns `unknown`, not dominance.

# 8. Calibration, transportability и data trust

## 8.1. Proxy-to-true calibration
Proxy value is not true value. Calibration certificate:
CalCert(proxy, true, population, scope, policy_regime, measurement_process, time_period, data_source).
For design `x`, calibration is usable only if:
scope(x) subseteq scope(CalCert)
policy_regime(x) compatible with CalCert.policy_regime
measurement_process(x) compatible with CalCert.measurement_process
no_measurement_manipulation_obligation satisfied
If policy changes incentives to manipulate the proxy, previous calibration may not transport.

## 8.2. Measurement process obligations
For each proxy/measurement coordinate:
O_meas(x) = {
  measurement_definition_valid,
  missingness_model_valid_or_bounded,
  manipulation_risk_bounded,
  reporting_incentives_checked,
  linkage_quality_sufficient,
  population_coverage_sufficient
}.
If measurement obligations are unresolved, value coordinates depending on them remain proxy or partial and cannot be promoted as point-identified.

## 8.3. DataTrust for acquisition
Each acquisition source `u` has:
DataTrust(u) = (
  provenance,
  sampling_design,
  measurement_protocol,
  missingness_assessment,
  contamination_risk,
  linkage_quality,
  manipulation_risk,
  access_constraints,
  privacy_constraints,
  version
).
Acquisition may shrink `K_world_t` or `K_stat_t` only if data trust obligations pass:
C_data_provenance ∧ C_sampling ∧ C_measurement ∧ C_missingness ∧ C_contamination ∧ C_linkage.
Corrupted, non-representative or scope-mismatched data can still be stored as evidence but cannot produce a promotion-grade narrowing constraint.

## 8.4. Calibration transition effects
A policy can change measurement/calibration itself:
Cal(proxy,true | regime before x) != Cal(proxy,true | do(x)).
Therefore calibration obligations are design-dependent. A generic proxy calibration file is not sufficient unless transportability is certified for the design's affected scope and regime.

# 9. Honest comparison и decision rules

## 9.1. Preference cone
All objectives are normalized for maximization. Default cone:
K_pref = R_+^d.
More structured preferences can use:
closed convex cone;
lexicographic gates;
stakeholder scalarization set Gamma;
hard constraints outside objective space.

## 9.2. Strong robust dominance
x >=_SR,t y iff
  for all kappa in K_t^kappa: f_kappa(x) >=_K_pref f_kappa(y)
  and Cert_t(x) >=_cert Cert_t(y)
  and ActiveHardConstraints_t(x) no weaker than ActiveHardConstraints_t(y).
Strict dominance:
x >_SR,t y iff x >=_SR,t y and not(y >=_SR,t x).
Use: certified pruning and decision front.

## 9.3. Marginal dominance fallback
x >=_marg,t y iff
  for every objective j:
  inf_{v in V_out_t(x)} v_j >= sup_{w in V_out_t(y)} w_j
  and Cert_t(x) >=_cert Cert_t(y).
Use only when coupled robust comparison is unavailable. It may leave many designs incomparable.

## 9.4. Maximality
Maximality front:
Max_t(S) = { x in S : no y in S with y >_SR,t x }.
This is the main frontier concept for certified designs.

## 9.5. E-admissibility for research
A design is E-admissible if:
exists kappa in K_t^kappa, exists gamma in Gamma:
  x in argmax_z gamma^T f_kappa(z).
Use: research frontier, exploration prioritization, not promotion.

## 9.6. Gamma-maximin for robust single choice
For scalarization `gamma`:
x_gamma^MM in argmax_x inf_{kappa in K_t^kappa} gamma^T f_kappa(x).
Use: post-processing when a risk-averse user demands one design. It is not a Pareto dominance rule and should not delete E-admissible alternatives.

## 9.7. Minimax regret
Reg_t(x; gamma) = sup_{kappa in K_t^kappa}
  [ max_z gamma^T f_kappa(z) - gamma^T f_kappa(x) ].
MR_t(x) = sup_{gamma in Gamma} Reg_t(x; gamma).
Use: ranking certified front or forming robust portfolios.

## 9.8. Portfolio-as-design
A portfolio or randomized policy is a new design object:
x_mu = RandomizedPolicy(mu, assignment_rule, scope, interference_model, implementation_mode).
It is not automatically linear in values:
V(x_mu) != sum_x mu(x) V(x)
unless linearity, no interference, stable implementation cost and valid assignment semantics are certified.
Portfolio promotion requires:
C_portfolio(x_mu) = C_randomization ∧ C_assignment ∧ C_interference ∧ C_fairness ∧ C_implementation ∧ C_value.

# 10. Четыре фронта алгоритма

## 10.1. Decision front
The public recommendation front:
F_dec_t = Max_{>=_SR,t}(X_cert_t_current_valid).
Properties:
only certified;
anytime returnable;
no shadow or quarantine designs;
value sets and certificates attached;
menu robustness and single-choice robustness reported separately.

## 10.2. Research front
F_res_t = Max_{research_order,t}(X_shadow_t ∪ X_cert_t).
Research potential:
Potential_t(x) =
  w_EAdm * EAdmScore_t(x)
+ w_UHV  * UpperHVContribution_t(x)
+ w_Info * FrontierInfoValue_t(x)
+ w_Cert * Certifiability_t(x)
+ w_ID   * IdentificationLeverage_t(x)
- w_Gap  * ProxyGapRisk_t(x)
- w_Cost * ExpectedCost_t(x).
Research front guides expansion, evaluation, certification and acquisition. It is not a recommendation.

## 10.3. Quarantine / adversarial validation front
ProxyGapRisk_t(x) =
  UpperProxy_t(x)
- CertifiedLower_t(x)
+ lambda_ood * OOD_t(x)
+ lambda_proof * ProofGap_t(x)
+ lambda_cal * CalibrationFragility_t(x)
+ lambda_meas * MeasurementManipulationRisk_t(x)
+ lambda_boundary * ValidatorBoundaryRisk_t(x).
F_quar_t = TopK or ParetoMax by ProxyGapRisk components.
Purpose:
find high-proxy designs that may exploit weak calibration;
find omitted-coupling patterns;
stress obligations compiler;
validate measurement manipulation risks;
prevent easy but false proxy promotion.

## 10.4. Portfolio front
F_port_t = Max over certified portfolio designs x_mu.
Portfolio front is returned only when portfolio semantics are themselves certified. Otherwise the algorithm may present portfolio candidates as research objects, not decisions.

# 11. Показатели качества: LHV, CHHV, robust choice и gaps

## 11.1. Normalization and reference point
Hypervolume requires explicit objective normalization and reference point:
r in R^d.
Reference point and scaling encode normative choices. The document-level algorithm requires:
stakeholder utility map;
normalization bounds;
sensitivity to r;
hard constraints excluded from ordinary HV when non-tradeable.

## 11.2. Lower guaranteed utility
For scalarization `gamma`:
L_t(x; gamma) = inf_{kappa in K_t^kappa} gamma^T f_kappa(x).
Certified archive utility:
W_t(S) = integral_Gamma max_{x in S} L_t(x; gamma) dmu(gamma).

## 11.3. Lower honest hypervolume
Attainment set for design:
A_t(x) = { z : for all kappa in K_t^kappa, z <= f_kappa(x) }.
Lower hypervolume:
LHV_t(S) = HV( union_{x in S} A_t(x) ).
This is conservative and single-model robust.

## 11.4. Coupled honest hypervolume
For a fixed `kappa`:
HV_kappa(S) = measure( union_{x in S} [r, f_kappa(x)]_K ).
Coupled honest hypervolume:
CHHV_menu_t(S) = inf_{kappa in K_t^kappa} HV_kappa(S).
This measures robust value of a menu. It does not automatically imply every individual design in the menu is robustly good.

## 11.5. Robust single-choice or robust portfolio value
For a menu `S`, single-choice robustness:
RobustChoice_t(S) = max_{x in S} inf_{kappa in K_t^kappa} U_kappa(x).
For certified portfolios:
RobustPortfolio_t(S) = max_{x_mu in CertifiedPortfolios(S)} inf_{kappa in K_t^kappa} U_kappa(x_mu).
Output reports both:
menu robustness != single-policy robustness.

## 11.6. Upper possible hypervolume
Possible attainment:
P_t(x) = { z : exists kappa in K_t^kappa, z <= f_kappa(x) }.
UHV_t(S) = HV( union_{x in S} P_t(x) ).
Use for exploration, not recommendation.

## 11.7. Frontier distance
Directed robust gap:
DirectedGap(A -> B) = sup_{y in B} inf_{x in A} Gap_H(x,y).
Scalarized gap:
Gap_H(x,y) = sup_{gamma in Gamma} [ L_t(y; gamma) - L_t(x; gamma) ]_+.
When true simulator world is known in benchmark, also compute:
TrueHVGap;
TrueRegret;
IdentificationGap;
DiscoveryGap;
CertificationDelayGap.

# 12. Validator/firewall и система обязательств

## 12.1. Firewall rule
Proposer proposes.
Surrogate prioritizes.
Validator certifies.
Only certified designs are promoted.
Not certificates:
LLM explanation;
natural-language rationale;
high proxy score;
high surrogate prediction;
unverified simulation output;
posterior credible interval without coverage argument;
self-reported causal claim;
untyped JSON from proposer.

## 12.2. Obligations compiler
For a canonical design:
O(x) =
  O_syntax(x)
∪ O_type(x)
∪ O_slot(x)
∪ O_param(x)
∪ O_coupling(x)
∪ O_effect(x)
∪ O_id(x)
∪ O_cal(x)
∪ O_meas(x)
∪ O_data(x)
∪ O_impl(x)
∪ O_eq(x)
∪ O_norm(x)
∪ O_eval_safety(x)
∪ O_value(x).
The obligation compiler is versioned and stress-tested. Missing-obligation risk is tracked:
ObligationCompletenessRisk_t(x, scope).
If this risk is high, design cannot be fully grounded in affected scope.

## 12.3. Obligation classes
Syntax obligations:
x in Lang(Gamma);
AST parse succeeds;
canonicalization idempotent.
Type/slot obligations:
all targets tau exist in canonical V;
operator op compatible with variable type;
scope variables typed and nonempty.
Parameter obligations:
pi in Pi_op;
parameter bounds;
budget feasibility;
monotonicity/continuity constraints if declared.
Coupling obligations:
no incompatible assignments;
no forbidden circular implementation dependency;
budget coupling feasible;
eligibility populations consistent;
measurement manipulation not induced without calibration;
atom interactions covered by graph/equilibrium semantics.
Effect obligations:
declared epsilon mapped to estimand;
causal path or mechanism defined;
effect claim entailed, bounded or marked ungrounded.
Identification obligations:
point formula, partial bound, proxy bound or blocked status;
assumptions explicit;
proof object stored;
statistical risk budget attached.
Calibration obligations:
proxy-to-true scope;
transportability across policy regime;
measurement process stability;
calibration uncertainty included in value set.
Data obligations:
data provenance;
sampling design;
missingness;
contamination;
linkage;
privacy and access scope.
Implementation obligations:
institutional capacity;
legal permission;
operational feasibility;
enforcement feasibility;
rollout constraints.
Equilibrium obligations:
semantics declared;
feedback effects modeled or bounded;
strategic response considered;
unsupported feedback objectives not grounded.
Evaluation safety obligations:
pilot/deployment risk bounded;
consent/approval if required;
sandbox containment;
stop rules;
harm monitoring.

## 12.4. Satisfaction semantics
For obligation `o`:
Sat(o) subseteq K_space.
Grounded:
grounded_t(x) iff K_t^kappa subseteq intersection_{o in O_ground(x)} Sat(o).
Uniform failure:
blocked_uniform_t(x) iff exists o in O(x): K_t^kappa subseteq Sat(o)^c.
Joint infeasibility:
blocked_joint_t(x) iff K_t^kappa ∩ intersection_{o in O(x)} Sat(o) = empty.
Shadow:
otherwise.
Failure reasons distinguish:
single_obligation_fail;
joint_obligation_inconsistency;
proof_timeout;
model_scope_insufficient;
data_scope_insufficient;
unknown.
Unknown or timeout never implies dominated, grounded or blocked unless the relevant logic proves it.

## 12.5. Promotion gate
Promote_t(x)=1 iff
  current_epoch_valid(x)
  and syntax/type/slot/parameter obligations pass
  and admissibility obligations pass
  and grounding obligations pass
  and identification certificates pass for claimed objectives
  and value outer set is valid
  and calibration/measurement/data obligations pass
  and implementation/equilibrium/normative obligations pass for scope
  and evaluation safety obligations pass for executed real-world evaluations
  and risk ledger has available budget
  and no active model/calibration/data alarm affects x.
Promotion cannot be triggered by acquisition score, hypervolume contribution, LLM confidence or surrogate confidence.

## 12.6. Validator output
ValidationResult = {
  admissibility_status,
  grounding_status,
  identification_certificates,
  value_outer_set,
  calibration_certificate,
  measurement_certificate,
  data_trust_certificate,
  implementation_certificate,
  equilibrium_certificate,
  normative_certificate,
  evaluation_safety_certificate,
  proof_artifacts,
  risk_used,
  failure_reasons,
  affected_dependencies,
  epoch,
  validator_version
}.

# 13. Confidence accounting и safety ledger

## 13.1. Anytime-valid requirement
Search is adaptive:
candidates depend on prior outcomes;
stopping time is data-dependent;
validator may be queried adaptively;
proposer may focus on boundary cases;
user may stop anytime.
Therefore fixed-time intervals are insufficient for promotion. Promotion certificates use:
confidence sequences;
e-values / e-processes;
sequential tests;
conformal risk control where appropriate;
deterministic proof systems;
validated sensitivity bounds.

## 13.2. Good event
Let `q` index executed statistical/probabilistic certificate checks:
Omega_delta = intersection_q {certificate q is valid under its scope}.
Require:
P(Omega_delta | maintained non-statistical assumptions) >= 1 - delta.

## 13.3. Predictable risk spending
Risk is allocated only to executed checks:
alpha_{t,q} = delta * w_{t,q} / Z,
with sum_{t,q} w_{t,q} <= Z.
Example schedule:
w_{t,q} = [6/(pi^2 (t+1)^2)] * [6/(pi^2 (q+1)^2)].
Then:
sum_{t,q} alpha_{t,q} <= delta.

## 13.4. Certificate composition
If design `x` requires certificates `C_1,...,C_m`, and each has false-accept risk `alpha_i`, then:
P(any false accept among them) <= sum_i alpha_i.
Promotion safety follows from union bound over executed checks. The claim is simple but depends on the checks being valid under adaptive selection.

## 13.5. Conformal and predictive layers
Conformal methods may be used for:
attempted-evaluation safety;
calibrating surrogate feasibility predictions;
screening high-risk candidates;
ranking certifiability.
If conformal layer controls a nonzero violation rate, that layer can guide attempts but does not by itself certify promotion unless the allowed violation is compatible with the promotion contract.

## 13.6. False promotion event
A design is false promoted if public output declares it certified while, under active scope and maintained assumptions:
admissibility false;
grounding false;
value not contained in V_out;
identification status overstated;
calibration scope invalid;
measurement process invalid;
data trust invalid;
evaluation safety violated for executed real-world evaluation;
portfolio semantics invalid when portfolio is promoted.
The main safety constraint:
P(exists false promoted design) <= delta
is a hard constraint, not a soft penalty in optimization.

# 14. Oracles и transitions: evaluation, simulation, acquisition

## 14.1. Evaluation transition
alpha_t = evaluate(x, mode).
Z = O_e(x, mode).
If mode is `simulate_only`:
update K_sim_t;
update Pi_sur_t;
update MC_error / numerical interval;
do not shrink K_world_t.
If mode provides world evidence and passes EvalSafety/DataTrust:
C_world = ConfBuilder_world(Z, alpha_spend);
K_world_{t+1} = K_world_t ∩ C_world.
If evidence only supports measurement/calibration:
K_cal_{t+1} or K_meas_{t+1} may shrink within certified scope.
After evaluation:
recompute V_out_t(x);
recompute obligations affected by x;
update surrogate;
update dominance witnesses;
update frontiers;
update risk ledger.

## 14.2. Attempted evaluation safety
Before any non-simulation evaluation:
EvalSafetyGate(x, mode)=pass.
Mode-specific requirements:
retrospective:
  data trust, privacy/access, measurement validity.
 
sandbox_pilot:
  containment, stop rules, harm bound.
 
field_pilot:
  ethical/legal approval, monitoring, rollback, population protections.
 
deployment_evaluation:
  full deployment safety, governance and accountability.
A design can be safe to simulate but unsafe to pilot. Attempted-evaluation safety is not inferred from promotion safety.

## 14.3. Acquisition transition
alpha_t = acquire(u).
Z = O_a(u).
If acquisition data trust passes:
C_a = ConfBuilder_a(Z, alpha_spend, scope(u));
K_component_{t+1} = K_component_t ∩ C_a.
Affected region:
R_out_t(u) = { x in X_t : Dep_out(x) intersects N_h(S(u)) }.
For every `x in R_out_t(u)`:
recompute identification status;
recompute calibration scope;
recompute value outer set;
recompute grounding;
recompute certifiability;
update dominance witnesses;
update frontier membership.

## 14.4. Certification transition
alpha_t = certify(x, obligation o).
This action may not generate new world data. It checks proof obligations, type constraints, causal derivation, calibration transportability, data scope or implementation feasibility. If all obligations for `x` pass, promotion gate may move `x` to `X_cert_t`.

## 14.5. Adversarial validation transition
alpha_t = adversarial_validate(x or pattern).
Purpose:
search for proxy hacking;
find omitted coupling obligations;
stress measurement manipulation;
test validator boundary;
check calibration fragility;
trigger obligation refinement.
Confirmed issue may:
move x to blocked;
move x to quarantine;
add obligation pattern;
mark affected certificates stale;
trigger model/calibration revision;
change acquisition priorities.

## 14.6. Archive compression transition
Compression never deletes provenance. It removes designs from active comparison set only if certified epsilon-coverage holds:
for all gamma in Gamma_epsilon:
  L_t(y; gamma) >= L_t(x; gamma) - epsilon
  and Cert_t(y) >=_cert Cert_t(x).
If proof unavailable, keep design active or mark comparison unknown.

# 15. Model revision epochs и stale certificates

## 15.1. Epoch definition
An epoch is an interval with fixed semantics for:
model class;
obligation language;
calibration scope logic;
measurement process assumptions;
implementation semantics;
equilibrium semantics;
validator version.

## 15.2. Revision triggers
K_t empty;
statistical diagnostics fail;
calibration transportability alarm;
data contamination or provenance alarm;
simulator discrepancy exceeds bound;
obligation completeness risk high;
equilibrium semantics unsupported for important candidates;
new legal/normative constraint added;
validator soundness issue discovered.

## 15.3. Revision protocol
freeze promotions in affected scope;
start new epoch;
expand or repair K and obligation language;
mark affected certificates stale;
revalidate current decision front;
return only current-valid certified designs.

## 15.4. Validity labels
valid_in_epoch(e): certificate was valid under epoch e semantics;
current_valid: valid under current epoch;
stale: previously valid but affected by revision;
requires_revalidation: cannot be public recommendation until checked;
invalid_under_current_epoch: fails current obligations.
Public decision front uses only `current_valid`.

# 16. Graph-causal surrogate и misspecification control

## 16.1. Surrogate role
Surrogate is a search tool:
prioritize;
rank;
estimate VOI;
propose refinements;
select acquisitions;
identify suspicious proxy gaps.
Surrogate cannot:
certify grounding;
certify admissibility;
certify true value;
replace calibration proof;
replace attempted-evaluation safety gate.

## 16.2. SCM baseline plus residual
For objective or support direction:
f_m(x) = F_m^SCM(x; theta) + r_m(x).
Residual:
r_m(x) = sum_{C in C_G} h_{m,C}(phi_C(H_x)) + rho_m(H_x).
Where:
`F^SCM` is mechanistic simulator or structural baseline;
`h_{m,C}` are graph-local interaction factors;
`rho_m` is global/equilibrium residual;
`phi_C` extracts local features from typed hypergraph and causal neighborhood.

## 16.3. Interaction graph
Let `G^m` be moralized or interaction-expanded graph. Factors:
C_G^(r) = { C subset V : C connected in G^m and |C| <= r }.
Kernel:
k_G(x,x') =
  sum_C rho_C k_C(phi_C(x), phi_C(x'))
+ rho_eq k_eq(psi_eq(x), psi_eq(x'))
+ rho_seq k_Gamma(seq(x), seq(x'))
+ rho_scope k_scope(scope(x), scope(x')).

## 16.4. Support-function surrogate
Surrogate predicts support functions, not just point values:
l_lambda(x), u_lambda(x), width_lambda(x), certifiability(x), shrinkage(u,x).
Confidence-like bands used for acquisition:
LCB_sur_lambda,t(x) = mu_l - sqrt(beta_t) sigma_l - b_miss_t(x)
UCB_sur_lambda,t(x) = mu_u + sqrt(beta_t) sigma_u + b_miss_t(x).
These are search-guiding unless separately calibrated.

## 16.5. Identification surrogate
Predicts:
DeltaWidth_hat_t(u,x,j);
P(id_{t+1,j}(x) = partial | u);
P(id_{t+1,j}(x) = point | u);
P(calibration_scope_passes | u,x);
Used to score acquisition and certification.

## 16.6. Certification surrogate
For obligations:
P(C_o(x)=pass | H_t).
Used to choose next certificate action, not to promote.

## 16.7. Misspecification monitor
Residual checks:
r_j(x) = observed_or_bounded_j(x) - predicted_j(x).
If residuals correlate with omitted features:
if MI_hat(r; phi_C1, phi_C2 | current_factors) > tau:
  add interaction factor Hull_G(C1 ∪ C2)
  mark affected surrogate uncertainty high
  prioritize evaluation/acquisition in affected region.
If misspecification cannot be bounded, candidate remains shadow or quarantine.

## 16.8. Trust levels
Each surrogate output has trust level:
proposal_only < search_guiding < calibrated_predictive < certified.
Promotion requires certified value/certificate objects, not surrogate trust.

# 17. Grammar/LLM/MCTS search

## 17.1. Prefix tree
Node:
p = <a_1,...,a_m>.
Stores:
N(p), children(p), reward_stats(p), upper_potential(p), lower_potential(p),
quarantine_risk(p), blocked_reason(p), unexplored_mass(p), dependency_summary(p).

## 17.2. Mixed proposer
q_t =
  epsilon_t q_Gamma
+ eta_t q_frontier
+ zeta_t q_adversarial
+ (1 - epsilon_t - eta_t - zeta_t) q_phi.
Where:
`q_Gamma` - grammar fallback with coverage over finite slice;
`q_frontier` - mutations/refinements near promising frontier;
`q_adversarial` - generates high proxy-gap or validator-boundary candidates;
`q_phi` - learned/LLM proposer.
Formal coverage relies only on `q_Gamma`:
if q_Gamma(x) > 0 then
P(x not proposed by T) <= exp(-q_Gamma(x) * sum_{t<=T} epsilon_t).

## 17.3. Progressive widening
At node `p`:
|Children(p)| < k_pw * N(p)^beta_pw
then expansion is allowed. Otherwise select among existing children.
Recommended:
0 < beta_pw < 1.

## 17.4. Selection score
UCT_H(child) =
  reward_mean(child)
+ c_uct * sqrt(log(1+N(parent))/(1+N(child)))
+ lambda_upper * UpperPotential(child)
+ lambda_info * FrontierInfo(child)
+ lambda_id * IDLeverage(child)
- lambda_quar * QuarantineRisk(child)
- lambda_cost * ExpectedCost(child).
This score guides tree search only. It does not certify.

## 17.5. Canonicalization and replay discipline
If external nondeterministic proposer is used, exact reproduction of the distribution is not required for safety claims. The system stores enough to reconstruct the executed run:
model_id;
prompt hash;
raw output;
parsed AST;
canonical ID;
state hash;
validator result hash;
selected action;
random streams for internal modules.
Theorem-relevant coverage claims use deterministic grammar fallback, not LLM-only behavior.

# 18. Acquisition portfolio
The acquisition families:
HV    - robust lower hypervolume improvement;
HKG   - lookahead knowledge gradient / delayed value;
ID    - identification and bound-shrinkage acquisition;
CERT  - certification and proof-gap closure;
ADV   - adversarial validation / proxy-gap reduction;
COV   - grammar coverage and search diversity;
AUD   - model/calibration/data/simulator audit and repair;
SAFE  - attempted-evaluation safety acquisition.
Each family proposes actions. The meta-controller chooses among families after safety filtering.

## 18.1. HV: robust hypervolume improvement
A_HV_t(alpha) = LVOI_t(alpha) / c(alpha).
Where:
LVOI_t(alpha) = inf_{Q in Q_t} E_Q[ LHV_{t+1}(X_cert_{t+1}) - LHV_t(X_cert_t) | alpha ].
Use when near-frontier designs are close to certification and evaluation/certification can yield immediate lower robust improvement.

## 18.2. HKG: honest knowledge gradient
A_HKG_t(alpha) =
  lower_or_root_scenario_E[
    max_{alpha'} lower_E_{t+1}[Quality_{t+2} - Quality_t | alpha']
  ] / c(alpha).
Must specify ambiguity mode:
ambiguity_mode in {rectangular, root_scenario, Bayesian_surrogate_only}.
Scores computed under different ambiguity modes are normalized before comparison.

## 18.3. ID: identification acquisition
Width:
width_{t,j}(x) = sup_{kappa in K_t} f_{kappa,j}(x) - inf_{kappa in K_t} f_{kappa,j}(x).
Worst-case potency:
Pot_t(u;x,j) = inf_{D_u in Outcomes(u)} [ width_{t,j}(x) - width_{t+1,j}(x | u,D_u) ]_+.
Regional score:
A_ID_t(u) =
  [ sum_{x in R_t(u)} sum_j omega_t(x,j) Pot_t(u;x,j)
    + eta * ExpectedCertMassGain_t(u) ] / c(u).
Weights:
omega_t(x,j) = NearFrontierPotential_t(x) * Certifiability_t(x) * StakeholderWeight_j * FrontLeverage_t(x).

## 18.4. CERT: certification acquisition
For obligation `o` of design `x`:
A_CERT_t(x,o) =
  EVI_t(C_o(x)) / c_o(x).
Where:
EVI_t(C_o(x)) =
  P_t(C_o pass) * ExpectedLowerFrontGain_if_all_obligations_pass
  - P_t(C_o fail) * ExpectedWasteAvoided
  + InformationGain_about_obligation_pattern.

## 18.5. ADV: adversarial validation
A_ADV_t(x) =
  Severity_t(x)
* PromotionProximity_t(x)
* AffectedMass_t(x)
* Novelty_t(x)
* ProxyGapRisk_t(x)
/ c_adv(x)
- EasyBogusPenalty_t(x).
Purpose is not to collect easy failures. It prioritizes boundary cases that could affect promotion or many related designs.

## 18.6. COV: coverage acquisition
A_COV_t(prefix) = UnexploredMass_t(prefix) * UpperPotential_t(prefix) * DiversityBonus_t(prefix) / c_expand.
Use when learned proposer collapses or finite-slice coverage dominates regret.

## 18.7. AUD: model/calibration/data audit
A_AUD_t(scope) =
  ExpectedCoverageRiskReduction_t(scope)
+ ExpectedStaleCertificateResolution_t(scope)
+ ExpectedDataTrustRepair_t(scope)
+ ExpectedCalibrationScopeRepair_t(scope)
- OpportunityCost_t(scope).
Audit actions are internal quality controls and may freeze promotion if they detect scope failure.

## 18.8. SAFE: attempted-evaluation safety
A_SAFE_t(x,mode) =
  ExpectedReductionInEvalRisk_t(x,mode)
+ ExpectedUnlockingOfSafeEvaluation_t(x,mode)
- c_safe.
Use before sandbox, field or deployment evaluation.

# 19. Nonstationary meta-controller и phase policy

## 19.1. Safety filter
Before scoring final actions:
Allowed_t = { alpha :
  cost(alpha) <= Budget_t
  and no publication of uncertified design
  and promotion requires certificates
  and risk spending available
  and evaluation safety gate passes if real-world action
  and current epoch not frozen for affected scope
  and data/legal/privacy constraints satisfied
}.
Actions outside `Allowed_t` are not executed.

## 19.2. Family reward components
For each acquisition family:
Reward_t(m) = normalized(
  DeltaLowerQuality
+ lambda_info DeltaFrontInfo
+ lambda_id DeltaIDMass
+ lambda_cert DeltaCertMass
+ lambda_quar DeltaProxyGapRiskReduced
+ lambda_aud DeltaCoverageRiskReduced
- lambda_cost Cost
- lambda_attempt HarmAttemptPenalty
- lambda_opp OpportunityCost
).
For adversarial validation, reward uses:
severity;
novelty;
promotion-boundary proximity;
affected mass;
would-have-passed counterfactual;
diversity penalty;
easy-bogus penalty.

## 19.3. Nonstationary controller
A stationary UCB is insufficient because acquisition family usefulness changes by phase. Controller can be:
sliding-window UCB;
EXP3-style adversarial controller;
phase-conditioned contextual bandit;
manual phase schedule with feedback overrides.
Generic form:
m_t = argmax_m ScoreMeta_t(m | context_t)
where context includes:
budget fraction;
certified frontier size;
shadow frontier size;
quarantine risk mass;
average near-frontier width;
calibration alarms;
coverage entropy;
recent family rewards;
solver reliability.

## 19.4. Phase policy
Discovery phase:
High: COV, UHV, FInfo, ID.
Goal: discover diverse promising regions and reduce gross ambiguity.
Resolution phase:
High: ID, CERT, HKG.
Goal: convert promising shadow designs into certified designs or block them early.
Robust improvement phase:
High: HV, CERT, local refine/evaluate.
Goal: improve lower robust decision front.
Finalization phase:
High: CERT, AUD, SAFE, compression, portfolio certification.
Goal: stabilize current front and ensure returned objects are current-valid.

# 20. VOI planning: rectangularity, scenario trees, bundles

## 20.1. Belief-MDP idealization
Ideal robust value:
J*(B,b) = max_{policy pi with budget b} lower_E[TerminalQuality(B_T)].
One-step robust Bellman:
J(B,b) = max_{alpha: c(alpha)<=b} inf_{P in P_t^alpha} E_P[J(T(B,alpha,Z), b-c(alpha))].
This dynamic recursion is valid only under time-consistent/rectangular uncertainty.

## 20.2. Rectangular ambiguity
Rectangular ambiguity means the adversary can choose transition distributions stagewise:
P_t(Z_t, Z_{t+1}, ...) = P_t(Z_t) ⊗ P_{t+1}(Z_{t+1}) ⊗ ...
Then Bellman recursion is coherent.

## 20.3. Root-scenario ambiguity
If unknown world `kappa` is chosen once:
kappa in K_t^kappa,
Z_1,...,Z_h generated conditional on same kappa.
Use scenario-tree planning:
J_h(B,b) = inf_{kappa in K_t^kappa} E[ Quality after h steps | kappa, policy ].
This avoids time-inconsistent lower expectations.

## 20.4. Complementary acquisitions
Acquisition actions often have complementarities:
Dataset A alone: no identification.
Dataset B alone: no identification.
A+B together: partial or point identification.
Therefore single-step greedy is a heuristic unless adaptive submodularity is verified. Planner supports:
bundle search;
beam search over acquisition sets;
scenario-tree rollout;
MILP / branch-and-bound for small action sets;
hitting-set or knapsack approximations;
zero-potency pruning.

## 20.5. Bundle VOI
For acquisition bundle `U'`:
RolloutPot_t(U') = E[ U_lower(B_{t+h}) - U_lower(B_t) | execute U', rollout policy ].
Budget constraint:
sum_{u in U'} c(u) <= b_bundle.

## 20.6. Score object
Every action score returns:
estimate;
lower_bound;
upper_bound;
approximation_error;
solver_status;
ambiguity_mode;
scenario_count;
bias_diagnostic;
cost;
risk_required;
Meta-controller penalizes high approximation error and unreliable solver status.

# 21. Полный алгоритм RACE-HOG-PODS v3.2

## 21.1. Inputs
Gamma                 - policy grammar;
K0                    - initial external credal envelope;
G                     - causal/equilibrium graph family;
O_e, O_a              - evaluation and acquisition oracles;
U                     - candidate acquisition actions;
B                     - total budget;
delta                 - promotion safety risk budget;
r                     - hypervolume reference point;
Y_box                 - bounded objective box;
Gamma_pref            - stakeholder scalarization set;
Lambda                - support-function direction grid;
seed                  - deterministic seed for internal components;
baseline x0           - optional certified baseline;
validator modules     - obligation validators;
EvalSafety modules    - attempted-evaluation gates;
DataTrust modules     - acquisition evidence gates.

## 21.2. Initialization
set PRNG(seed)
initialize K_world, K_stat, K_id, K_cal, K_meas, K_impl, K_eq, K_norm from K0
initialize K_sim and Pi_sur
X_raw, X_shadow, X_quarantine, X_cert, X_blocked := empty
Tree := root prefix <>
RiskLedger := allocate risk schedule delta
Meta := initialize acquisition family controller
Epoch := 0
cost := 0
If baseline exists:
parse/canonicalize baseline;
build obligations;
validate baseline;
if promotion gate passes: add to X_cert;
else keep as shadow or blocked depending on failure.

## 21.3. Main loop
while cost < B:
 
  1. Canonicalize raw pool
     for raw in X_raw:
       parse -> AST
       if fail: move to X_blocked with syntax_fail
       else:
         canonicalize -> H_x
         build obligations O(x)
         run cheap syntax/type/slot/parameter checks
         move to X_shadow or X_blocked
 
  2. Maintain certificate state
     affected := designs affected by last evidence, obligation update or epoch change
     for x in affected:
       recompute obligations if semantics changed
       run required validators if evidence changed
       update status vector z_t(x)
       if PromotionGate(x) passes:
          move x to X_cert
       elif joint infeasible or hard fail:
          move x to X_blocked
       elif high proxy/proof/calibration risk:
          move x to X_quarantine
       else:
          keep or move to X_shadow
 
  3. Update frontiers
     F_dec  := Max_SR(current-valid X_cert)
     F_res  := Max_research(X_shadow ∪ X_cert)
     F_quar := Top/Pareto by ProxyGapRisk(X_quarantine ∪ suspicious shadow)
     F_port := certified portfolio front over current-valid portfolio designs
 
  4. Update search models
     update value surrogate
     update identification surrogate
     update certification surrogate
     update calibration/data/evaluation risk predictors
     update misspecification diagnostics
 
  5. Build action pool
     A_pool := {}
     A_pool += ExpandActions(Tree, progressive widening)
     A_pool += MutateActions(F_res, F_dec)
     A_pool += EvaluateActions(high VOI candidates, mode-specific)
     A_pool += CertifyActions(near-certifiable designs)
     A_pool += AcquireActions(regions with ID/CAL/DATA leverage)
     A_pool += AdversarialValidationActions(F_quar and boundary patterns)
     A_pool += AuditActions(scopes with alarms or high coverage risk)
     A_pool += SafeEvaluationActions(real-world modes needing EvalSafety)
     A_pool += CompressionActions(if active archive too large)
 
  6. Safety filter
     Allowed := {alpha in A_pool satisfying hard gates}
     if Allowed empty:
        return current F_dec with certificate packages
 
  7. Family proposals
     for family m in {HV,HKG,ID,CERT,ADV,COV,AUD,SAFE}:
        alpha_m := argmax_{alpha in Allowed} AcquisitionScore_m(alpha)
 
  8. Meta-selection
     m_t := NonstationaryMetaController(Meta, context_t)
     alpha_t := alpha_{m_t}
     if alpha_t invalid under final gate:
        alpha_t := SafeFallback(Allowed)
 
  9. Execute action
     case expand(prefix):
        raw := sample from q_t
        add raw to X_raw and Tree
 
     case mutate_or_refine(x):
        x_prime := local refinement or parameter mutation
        add to X_raw or X_shadow after canonicalization
 
     case evaluate(x, mode):
        if mode real-world:
           require EvalSafetyGate pass
        Z := O_e(x, mode)
        if mode == simulation_only:
           update K_sim and Pi_sur only
        else:
           require DataTrust if data produced
           C := ConfBuilder_e(Z, alpha_spend)
           update relevant K component by intersection
        update certificates and surrogates for affected designs
 
     case certify(x,o):
        run validator for obligation o
        spend risk if probabilistic certificate
        update CertState(x)
        apply PromotionGate if all obligations pass
 
     case acquire(u):
        require DataTrust preconditions
        Z := O_a(u)
        C := ConfBuilder_a(Z, alpha_spend, scope(u))
        update relevant K components
        R := affected_region_outer(u)
        revalidate/update all x in R
 
     case adversarial_validate(target):
        run adversarial/proxy-gap/validator-boundary diagnostic
        if issue confirmed:
          update obligations or block/quarantine affected designs
          mark affected certificates stale if necessary
 
     case audit_model_or_calibration(scope):
        run model/calibration/data/simulator/equilibrium diagnostics
        if alarm:
          freeze affected promotions
          start revision protocol if necessary
 
     case compress_archive(epsilon):
        apply certified epsilon-coverage compression
 
  10. Revision check
      if K empty or active alarm requires revision:
        freeze affected promotions
        Epoch := Epoch + 1
        repair/expand model or obligations
        mark affected certificates stale
        revalidate current decision front
 
  11. Update budget and controller
      cost += c(alpha_t)
      update Meta with realized reward and opportunity cost
      update state hashes for replay discipline
      t := t + 1
 
return current F_dec, F_res, F_quar, F_port with certificate packages.

# 22. Карта переходов и инварианты

## 22.1. T0: raw to AST
T_parse(raw) -> AST or bottom.
Invariant: AST != bottom implies AST in Lang(Gamma) syntactically.

## 22.2. T1: AST to canonical design
T_canon(AST) -> H_x.
Invariant: canonicalization idempotent and semantics-versioned.

## 22.3. T2: design to obligations
T_obl(H_x) -> O(x).
Invariant: obligations include syntax, type, parameter, coupling, effect, identification,
calibration, measurement, data, implementation, equilibrium, normative and evaluation-safety classes.

## 22.4. T3: evidence to confidence/proof constraint
T_conf(Z, alpha, scope) -> C(Z; alpha, scope).
Invariant: statistical confidence constraints are valid under adaptive selection within declared scope.

## 22.5. T4: component update
K_component_{t+1} = K_component_t ∩ C.
Allowed only for the component supported by evidence. Simulation-only evidence cannot update `K_world`.

## 22.6. T5: credal state to value outer set
T_value(K_t^kappa, x) -> V_out_t(x).
Invariant: on good event, true value lies in V_out_t(x) under active assumptions.

## 22.7. T6: certificates to promotion
T_promote(x) -> {0,1}.
Invariant: Promote=1 implies all promotion gates passed in current epoch.

## 22.8. T7: certified set to frontiers
T_front(X_cert_t) -> F_dec_t.
Invariant: F_dec_t subseteq current-valid X_cert_t.

## 22.9. T8: revision
T_revision(alarm) -> new epoch.
Invariant: affected public frontier points are current-valid or removed from F_dec_t.

# 23. Теоремы и доказательные контуры

## 23.1. Theorem 1: conditional false promotion control
Assumptions:
A1. Promotion only occurs through PromotionGate.
A2. Every probabilistic certificate used by PromotionGate is anytime/adaptive-valid under its declared scope.
A3. Risk ledger satisfies sum alpha_{t,q} <= delta.
A4. Deterministic validators are sound relative to declared obligation language.
A5. Structural, calibration-scope, implementation, measurement, data-trust and normative assumptions are maintained for the active epoch.
Claim:
P(exists false promoted design | maintained assumptions) <= delta.
Proof sketch:
If a design is promoted, all certificates required by PromotionGate accepted.
On the good event, no accepted probabilistic certificate is false and deterministic validators are sound.
Thus admissibility, grounding, value containment and claimed identification/calibration/evaluation-safety statuses hold under active scope.
False promotion can occur only on the complement of the good event or outside maintained assumptions.
The probability of the good-event complement is bounded by the risk ledger.

## 23.2. Theorem 2: anytime certified output
For any stopping time `tau`:
F_dec_tau subseteq X_cert_tau_current_valid.
Under Theorem 1 assumptions, every returned point in `F_dec_tau` is certified with probability at least `1-delta` conditional on maintained assumptions.

## 23.3. Theorem 3: monotone lower envelope inside fixed epoch
If:
K_{t+1}^kappa subseteq K_t^kappa
and `x` remains current-valid certified, then for every `gamma`:
L_{t+1}(x; gamma) >= L_t(x; gamma).
If `X_cert_t subseteq X_cert_{t+1}` and no revision invalidates certificates:
W_{t+1}(X_cert_{t+1}) >= W_t(X_cert_t).
The set of maximal frontier points may change; monotonicity is about certified lower utility, not literal set inclusion of frontier points.

## 23.4. Theorem 4: proposal coverage from grammar fallback
For finite grammar slice and any design `x` with `q_Gamma(x)>0`:
P(x not proposed by T) <= exp(-q_Gamma(x) * sum_{t<=T} epsilon_t).
If `sum_t epsilon_t = infinity`, `x` is eventually proposed with probability 1.

## 23.5. Theorem 5: certified compression safety
If compression removes `x` from active comparison because there exists `y` such that:
for all gamma in Gamma_epsilon:
  L_t(y;gamma) >= L_t(x;gamma) - epsilon
and Cert_t(y) >=_cert Cert_t(x),
then removing `x` changes scalarized lower utility on `Gamma_epsilon` by at most `epsilon`. If mesh and Lipschitz conditions hold, off-grid error is bounded by `epsilon_Lambda`.

## 23.6. Regret accounting schema
Under additional assumptions for a chosen implementation class:
bounded objective box;
valid support discretization;
finite grammar slice or controlled truncation;
coverage from q_Gamma;
calibrated estimation or bounded surrogate error;
bounded planning approximation;
valid solver error bounds;
fixed epoch or explicit revision accounting;
regret decomposes as:
Reg(B) <=
  Reg_estimation
+ Reg_proposal
+ Reg_tree_search
+ Reg_truncation
+ Reg_certification_delay
+ Reg_identification_gap
+ Reg_planning
+ Reg_solver
+ Reg_model_scope.
This is an accounting schema. Any numerical rate requires the corresponding assumptions to be proven for the implemented surrogate/search class.

# 24. Regret, gaps и метрики

## 24.1. Benchmarks
Operational frontier:
F_dec_B = returned certified frontier at budget B.
Oracle-certified benchmark:
F_cert^dagger(B) = best frontier achievable under same grammar, oracles, certification protocol and budget by an ideal planner.
Full-information causal frontier:
F_full(M*) = frontier if true model were known and all values were point-known.
Main algorithmic regret compares to `F_cert^dagger(B)`, not directly to full-information frontier. The gap to full-information frontier is reported as identification/model gap.

## 24.2. Scalarized robust regret
J^dagger(gamma) = max_{x in F_cert^dagger(B)} L^dagger(x; gamma).
J_alg(gamma) = max_{x in F_dec_B} L_B(x; gamma).
Reg_Gamma(B) = sup_{gamma in Gamma} [ J^dagger(gamma) - J_alg(gamma) ]_+.

## 24.3. Full-information gap
Gap_full(B) = Distance(F_dec_B, F_full(M*)).
This includes irreducible partial identification and acquisition limits.

## 24.4. Certification delay gap
Reg_cert(B) = value of high-potential discovered designs not yet certified by budget B.
This distinguishes search success from proof/certification bottleneck.

## 24.5. Attempted-evaluation safety metrics
unsafe_attempt_blocked_count;
near_miss_count;
real_world_eval_violation_rate;
EvalSafetyCoverage;
stop_rule_trigger_count.

## 24.6. Data/calibration metrics
data_trust_pass_rate;
calibration_scope_coverage;
measurement_manipulation_risk_mass;
proxy_to_partial transitions;
partial_to_point transitions;
near-frontier width reduction per acquisition cost.

# 25. Вычислительные подпрограммы

## 25.1. Pairwise dominance oracle
Input:
x, y, K_t^kappa, Cert_t(x), Cert_t(y), preference cone.
Compute:
D_j(x,y) = inf_{kappa in K_t^kappa} [ f_kappa,j(x) - f_kappa,j(y) ].
Return:
x_dominates_y;
y_dominates_x;
value_witness;
cert_witness;
fallback_used;
solver_status;
approximation_error;
timeout_flag.
Rules:
solver_status=timeout => comparison unknown;
approximation without certified bound => search-only;
unknown => incomparable, not dominated.

## 25.2. Dominance scalability
Naive pairwise comparison costs `O(n^2)` robust solves. Use layers:
coordinate lower/upper screening;
cert partial-order prefilter;
dependency-region hashing;
TopK per scalarization cache;
incremental dominance graph;
solver budget with unknown semantics;
epsilon-certified compression.

## 25.3. CHHV solver
Options:
exact scenario enumeration;
robust optimization over parametric model class;
MILP or convex relaxation;
certified lower bound;
LHHV fallback;
sample approximation for acquisition only.
Safety does not depend on CHHV. CHHV quality scores must report solver status and approximation error.

## 25.4. Support discretization solver
Input:
Lambda, Y_box, K_t^kappa, x.
Output:
LCB_lambda, UCB_lambda, epsilon_Lambda, convexification_status.
If nonconvexity matters and convexification is too loose, design remains comparable only through certified available directions.

## 25.5. Affected-region computation
For acquisition `u`:
S(u) = variables, edges, parameters, calibration scopes, measurement processes affected.
R_out_t(u) = { x : Dep_out(x) intersects N_h(S(u)) }.
`Dep_out` must overapproximate true dependencies.

## 25.6. Acquisition scenario estimator
For action `alpha`:
simulate or enumerate outcome scenarios Z_s;
apply transition T(B, alpha, Z_s);
compute lower/upper VOI;
compute MC or solver error;
return ambiguity_mode and diagnostics.

## 25.7. Portfolio compiler
Input:
mu, designs S, assignment rule, scope, interference model.
Output:
x_mu design object;
O_portfolio(x_mu);
portfolio value semantics;
portfolio implementation cost;
portfolio fairness/legal obligations.
No portfolio recommendation without this compiler and certification.

# 26. Инженерные структуры данных и API

## 26.1. DesignRecord
DesignRecord = {
  id,
  canonical_AST,
  typed_hypergraph,
  atoms,
  parameters,
  scope,
  implementation_mode,
  equilibrium_semantics,
  dependency_set_outer,
  obligations,
  status_vector,
  identification_certificates,
  value_outer_set,
  calibration_certificate,
  measurement_certificate,
  data_trust_dependencies,
  implementation_certificate,
  evaluation_safety_certificate,
  surrogate_features,
  proposer_origin,
  parent_prefix,
  evidence_refs,
  certificate_refs,
  epoch_status,
  frontier_membership
}

## 26.2. ObligationRecord
Obligation = {
  id,
  type,
  formula,
  required_evidence,
  satisfaction_semantics,
  validator_module,
  risk_budget_required,
  status,
  proof_artifact_ref,
  failure_reason,
  scope,
  epoch,
  version
}

## 26.3. EvidenceRecord
EvidenceRecord = {
  id,
  evidence_type,
  source,
  scope,
  data_trust_status,
  measurement_process,
  acquisition_action,
  confidence_constraint_ref,
  usable_for_components,
  limitations,
  version
}

## 26.4. OracleCallRecord
OracleCall = {
  call_id,
  oracle_type,
  mode,
  input_hash,
  output_hash,
  cost,
  random_seed,
  data_version,
  simulator_version,
  diagnostics,
  confidence_constraint_id,
  component_updated,
  timestamp
}

## 26.5. ReplayRecord
ReplayRecord = {
  global_seed,
  step,
  state_hash_before,
  action_pool_hash,
  acquisition_scores_hash,
  selected_family,
  selected_action,
  proposer_trace,
  oracle_call_id,
  validator_result_hash,
  state_hash_after,
  risk_spend_summary
}
This supports deterministic reconstruction of executed run. It is not part of the public certificate package unless requested.

## 26.6. Validator API
validate_design(
  design_id,
  canonical_hypergraph,
  credal_component_ids,
  evidence_bundle_ids,
  obligation_ids,
  alpha_budget,
  epoch
) -> ValidationResult

## 26.7. Acquisition model API
score_action(action, belief_state, family) -> AcquisitionScore
AcquisitionScore = {
  estimate,
  lower_bound,
  upper_bound,
  uncertainty,
  cost,
  risk_required,
  approximation_error,
  scenario_count,
  ambiguity_mode,
  solver_status,
  bias_diagnostic
}

## 26.8. Dominance API
compare_honest(x, y, K_t^kappa, Certs_t, prefs) -> DominanceResult

## 26.9. Frontier API
build_frontiers(state) -> {
  decision_front,
  research_front,
  quarantine_front,
  portfolio_front,
  compression_witnesses,
  incomparable_pairs_summary
}

## 26.10. User output API
return_public_result(state) -> {
  decision_front,
  portfolio_front_if_certified,
  value_outer_sets,
  identification_status_per_objective,
  key_assumptions,
  calibration_scope,
  validity_epoch,
  robustness_metrics,
  limitations,
  certificate_package_refs
}

# 27. План реализации

## 27.1. Phase 1: certified finite-pool core
finite grammar slice;
no external LLM;
interval value sets;
marginal fallback dominance plus small coupled solver;
validator obligations for syntax/type/parameter/admissibility/value;
confidence ledger;
DecisionFront only;
simulation-only clearly separated from world evidence.

## 27.2. Phase 2: partial identification and calibration
support-function value sets;
identification certificates per objective;
calibration scope certificates;
DataTrust for evidence;
proxy/partial/point status lattice;
ResearchFront.

## 27.3. Phase 3: acquisition and affected regions
acquire(u);
affected-region computation;
ID acquisition;
calibration acquisition;
regional bound shrinkage;
revalidation pipeline.

## 27.4. Phase 4: graph-causal surrogate
SCM baseline;
graph-factor residual;
support-function prediction;
certification surrogate;
misspecification monitor;
solver diagnostics.

## 27.5. Phase 5: grammar/LLM/MCTS search
mixed proposer;
progressive widening;
coverage fallback;
frontier mutation;
quarantine generation;
replay discipline.

## 27.6. Phase 6: advanced planning and portfolio
HKG/scenario trees;
bundle acquisition planning;
portfolio-as-design compiler;
robust choice semantics;
archive compression;
model revision epochs.

# 28. Тестирование и benchmark-протокол

## 28.1. Unit tests
canonicalization idempotence;
invalid syntax never enters shadow as valid;
blocked design never enters certified pool;
shadow design never appears in decision front;
high proxy without calibration cannot dominate calibrated design;
simulation-only does not shrink world credal set;
confidence spending sum <= delta;
solver timeout returns unknown/incomparable;
portfolio without portfolio certificate not returned as decision;
calibration scope mismatch prevents point/proxy promotion;
data trust fail prevents acquisition from narrowing world state;
model revision marks affected certificates stale;
current decision front contains only current-valid designs;

## 28.2. Integration tests
Synthetic SCMs with:
point-identified effects;
latent confounding and partial bounds;
proxy outcome with calibration gap;
measurement manipulation under intervention;
graph-local interactions;
long-range equilibrium interactions;
adversarial high-proxy branch;
complementary acquisitions;
data poisoning or provenance failure;
portfolio nonlinearity/interference.
Expected behavior:
no false promotion under good event;
proxy traps remain shadow/quarantine until calibrated;
acquisition selected when it shrinks many near-frontier bounds;
complementary acquisitions found by bundle/lookahead planner;
additive surrogate underperforms graph residual in interaction benchmark;
model revision removes stale certificates from decision front;
portfolio front appears only when portfolio-as-design passes obligations.

## 28.3. Metrics
Safety:
false_promotion_rate;
coverage_of_value_outer_sets;
calibration_scope_failure_rate;
measurement_manipulation_near_miss_count;
data_trust_failure_rate;
unsafe_attempt_blocked_count.
Optimization:
LHV/CHHV over budget;
robust single-choice value;
portfolio robust value;
directed frontier gap;
number of certified designs;
shadow-to-certified conversion rate.
Identification:
average near-frontier width;
proxy-to-partial transitions;
partial-to-point transitions;
regional shrinkage per acquisition cost;
calibration transportability coverage.
Search:
grammar coverage;
unique canonical designs;
branch entropy;
LLM duplicate rate;
quarantine risk mass;
adversarial validation severity-weighted discoveries.
Computation:
dominance oracle calls;
solver timeout rate;
approximation error distribution;
frontier compression ratio;
scenario estimator MC error.

## 28.4. Ablations
no firewall vs firewall;
simulation-as-world-evidence disabled/enabled in controlled failure test;
marginal dominance vs coupled dominance;
LHV vs CHHV;
evaluate-only vs evaluate+acquire;
greedy VOI vs bundle/lookahead;
no adversarial validation vs adversarial validation;
additive surrogate vs graph residual;
LLM-only vs mixed proposer;
no model revision vs revision epochs;
portfolio linear assumption vs portfolio-as-design certificate.

# 29. Практические параметры

## 29.1. Risk budget split
Example:
delta_total = delta_value + delta_ground + delta_id + delta_cal + delta_data + delta_eval + delta_mc.
Suggested initial split:
delta_value  = 0.20 delta;
delta_ground = 0.15 delta;
delta_id     = 0.20 delta;
delta_cal    = 0.15 delta;
delta_data   = 0.10 delta;
delta_eval   = 0.10 delta;
delta_mc     = 0.10 delta.
Deployment-critical domains should allocate more to evaluation safety, calibration and data trust.

## 29.2. Progressive widening
Start:
beta_pw in [0.3, 0.7]
k_pw in [1, 5]
If search too narrow: increase `beta_pw`, `COV` weight, diversity bonus. If search too shallow: decrease `beta_pw` and increase local refinement.

## 29.3. Proposer mixture
Initial:
epsilon_t q_Gamma: 0.10 - 0.30
eta_t q_frontier: 0.20 - 0.40
zeta_t q_adversarial: 0.05 - 0.20
q_phi: remaining mass
Increase grammar fallback if mode collapse or low branch entropy. Increase adversarial validation if proxy-gap risk mass grows.

## 29.4. Acquisition weights
Initial phase-aware weights:
Discovery:    COV 0.25, UHV/FInfo 0.30, ID 0.25, CERT 0.10, ADV 0.10.
Resolution:   ID 0.30, CERT 0.25, HKG 0.20, ADV 0.15, HV 0.10.
Improvement:  HV 0.35, CERT 0.20, HKG 0.20, ID 0.15, ADV 0.10.
Finalization: CERT 0.30, AUD 0.25, SAFE 0.15, compression 0.15, HV 0.15.
These are starting points; nonstationary controller adapts.

## 29.5. Support directions
For `d <= 4`:
dense simplex grid + coordinate directions + stakeholder directions.
For higher `d`:
coordinate directions;
random positive directions;
frontier-normal directions;
stakeholder scalarizations;
risk/fairness priority directions.

## 29.6. Solver policy
exact solver for promotion when possible;
certified relaxation if exact unavailable;
heuristic solver only for search;
timeout => unknown;
unknown => incomparable;
no silent downgrade from proof to heuristic.

# 30. Ограничения утверждений
RACE-HOG-PODS v3.2 does not claim:
unconditional global optimality over arbitrary infinite grammar;
truth of structural causal assumptions from statistics alone;
safety of attempted real-world evaluations without EvalSafety;
validity of Bayesian credible intervals as promotion certificates by default;
LLM determinism, unbiasedness or coverage;
greedy VOI near-optimality without adaptive submodularity or verified conditions;
monotonicity across model-revision epochs;
linearity of randomized portfolios without portfolio-as-design certification;
transportability of proxy calibration without scope proof;
simulator output as independent world evidence;
that hypervolume alone encodes stakeholder values without normalization and reference-point specification.
These limitations are part of the algorithmic contract.

# 31. Сжатая математическая спецификация
Extended uncertainty:
kappa = (M, xi_proxy, theta_cal, theta_meas, theta_impl, theta_eq, theta_data, theta_norm).
K_t^kappa = externally maintained credal set over kappa.
Value set:
V_t(x) = { f_kappa(x) : kappa in K_t^kappa }.
Certified archive:
X_cert_t = { x : PromotionGate_t(x)=1 and current_epoch_valid(x) }.
Strong robust dominance:
x >=_SR,t y iff
  for all kappa in K_t^kappa: f_kappa(x) >=_K f_kappa(y)
  and Cert_t(x) >=_cert Cert_t(y).
Decision front:
F_dec_t = { x in X_cert_t : no y in X_cert_t with y >_SR,t x }.
Lower value:
L_t(x;gamma)=inf_{kappa in K_t^kappa} gamma^T f_kappa(x).
LHV:
LHV_t(S)=HV(union_{x in S} {z: for all kappa, z <= f_kappa(x)}).
CHHV menu:
CHHV_menu_t(S)=inf_{kappa in K_t^kappa} HV_kappa(S).
Robust single choice:
RobustChoice_t(S)=max_{x in S} inf_{kappa in K_t^kappa} U_kappa(x).
Safety:
P(exists false promoted design | maintained assumptions) <= delta.
Action policy:
alpha_t = Gate_t( MetaController_t({argmax_alpha A_m,t(alpha)}_m) ).
Regret accounting:
Reg(B) <= Reg_estimation + Reg_proposal + Reg_tree_search + Reg_truncation
        + Reg_certification_delay + Reg_identification_gap + Reg_planning
        + Reg_solver + Reg_model_scope.

# 32. Пример одного шага
Suppose shadow design `x_s` has:
UpperProxy high;
certified lower value low;
partial bounds wide;
calibration missing;
near-frontier potential high;
measurement manipulation risk moderate.
Validator returns:
grounding_status = shadow;
failure_reasons = {calibration_scope_missing, measurement_manipulation_unchecked};
width(x_s) = large;
Certifiability = medium;
ProxyGapRisk = high.
Candidate actions:
evaluate(x_s, simulation_only):
  cheap, reduces MC/surrogate uncertainty, does not shrink world state.
 
acquire(u_cal):
  collects calibration data, affects 150 near-frontier designs.
 
certify(x_s, measurement_manipulation):
  checks whether policy changes reporting incentives.
 
adversarial_validate(x_s):
  tests whether high proxy value can be produced while true value remains low.
 
expand(prefix):
  explores variants that avoid the fragile proxy channel.
If `u_cal` passes DataTrust and transportability requirements, it may shrink calibration uncertainty for many designs. Some designs can move from proxy to partial or point. If calibration fails, affected designs move to quarantine or blocked, and obligation patterns update. `x_s` cannot enter `F_dec` until promotion gate passes.

# 33. Возвращаемый пользователю пакет сертификатов
For each point in public decision front:
CertificatePackage(x) = {
  design_id,
  canonical policy composition,
  atom list and parameter values,
  grammar/semantics version,
  scope and implementation mode,
  equilibrium semantics,
  admissibility certificate,
  grounding certificate,
  identification status per objective,
  value outer set representation,
  calibration scope,
  measurement scope,
  data trust summary,
  implementation/normative constraints,
  evaluation safety status if real-world evaluation occurred,
  validity epoch,
  dominance witnesses or incomparability summary,
  robustness metrics,
  limitations and non-transportable scopes
}
No certificate package, no public decision-front membership.
Research and quarantine fronts may be returned only with explicit labels:
not certified for recommendation;
used for further search;
requires specified missing obligations.

# 34. Глоссарий
Admissible design: design satisfying syntax, parameter, coupling, implementation, legal/normative and hard policy constraints under declared scope.
Grounded design: design whose declared effects, identification claims, calibration scope and value bounds are validated, not merely asserted.
Credal set: set of possible models, parameters, calibration states or measurement states consistent with current evidence and maintained assumptions.
Kappa-process: joint process `f_kappa(x)` over designs, including model, proxy, calibration, measurement, implementation and equilibrium uncertainty.
Partial identification: setting where evidence and assumptions restrict the causal quantity to a set or bounds, not a point.
Proxy identification: setting where observed target is proxy for true target and calibration or transportability is uncertain.
Promotion: moving a design into certified set so it may appear in public decision front.
Decision front: certified current-valid maximal frontier.
Research front: promising but not necessarily certified designs used for exploration.
Quarantine front: suspicious high-proxy/high-gap designs requiring adversarial validation or additional obligations.
Portfolio-as-design: randomized or mixed policy treated as a new design object with its own obligations and value semantics.
CHHV: coupled honest hypervolume, worst-case menu hypervolume over common uncertainty state.
LHV: lower honest hypervolume based on guaranteed attainment sets.
RobustChoice: robust value of selecting one certified design or certified portfolio.
Validator/firewall: module converting obligations and evidence into formal certificates.
DataTrust: evidence quality object governing whether acquisition can narrow the external credal state.
EvalSafety: attempted-evaluation safety gate for real-world pilot or deployment evaluation.
Epoch: period with fixed model, obligation, calibration, measurement, implementation and validator semantics.
Stale certificate: certificate that was valid in a prior epoch or scope but must be revalidated for current output.

# 35. Заключение
RACE-HOG-PODS v3.2 is a conservative active-search algorithm for policy design under partial identification, proxy uncertainty, adversarial proposal pressure and costly regional data acquisition. Its core is not a single optimizer but an architecture: grammar/LLM/MCTS proposal, graph-causal surrogate, regional VOI planner, certification firewall, confidence accounting, model-revision epochs and stratified output.
The most important invariant is the separation of roles:
Search models may be optimistic.
Public recommendations must be certified.
Simulation may inform search.
World claims require world evidence or explicit maintained assumptions.
Proxy value may guide exploration.
Grounded value requires calibration and identification certificates.
This architecture preserves the useful power of optimistic discovery while preventing the central failure mode: a high-scoring proxy design being returned as a confident grounded policy recommendation without the evidence and obligations needed to justify it.
