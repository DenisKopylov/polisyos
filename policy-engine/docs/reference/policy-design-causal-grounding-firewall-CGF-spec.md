<!--
Archived source-of-truth for the policy-design GROUNDING target specification.
System: Causal Grounding Firewall (CGF) — unified synthesis of RT1–RT7.
Authored externally (seven independent studies on the grounding research brief);
imported 2026-06-30. Verbatim text (extracted from the source .docx).
The PolicyOS reading, mapping, adoption decisions, and what-we-defer live in the
decision record: docs/system-design-decisions/policy-design-causal-grounding-firewall.md
Do NOT treat this as a build plan to start cold: it is subordinated under the
no-parallel-worlds law (P27/P28) and reuses GY-S2/S3 (L2/L3/L6/WMR), GY-K (axis
witness), N7 (acquire), N6 QuarantineFront, N12 (epochs). Read the decision record first.
-->

Единая спецификация честного free-grow causal grounding
Сводный непротиворечивый документ по RT1–RT7


Версия: интегральная исследовательская спецификацияОснование: семь независимых исследований по общей постановке задачиЦель: превратить свободно порождённую LLM-интервенцию в аудируемое, каузально-механистическое и free-grow безопасное grounding-решение

Центральный результат
Оптимальное сводное решение — не один matcher и не один threshold, а Causal Grounding Firewall: pipeline parse -> joint typed grounding -> relation calculus -> certificate-first bind/abstain -> free-grow admission -> adversarial quarantine -> active acquisition -> benchmark trace.
Similarity, embedding, LLM-rationale и proxy-score используются только для поиска кандидатов и приоритизации. Они никогда не являются достаточным основанием для bind, admission или promotion.



# Содержание
1. Исполнительное резюме и выбранная архитектура
2. Анализ семи исследований и устранение противоречий
3. Единая формальная модель: атомы, гипотезы, reference и obligations
4. End-to-end pipeline Causal Grounding Firewall
5. RT1 + RT4: отношение grounding и совместный typed cross-modal grounder
6. RT2: certificate-first adaptive abstention и гарантии false-bind
7. RT3: free-grow admission реальных новых рычагов
8. RT5: adversarial-устойчивость против proxy-gaming
9. RT7: активный grounding под VOI/бюджетом
10. RT6: протокол оценки без стабильного gold-standard
11. Схемы данных и API-контракты
12. Единые теоремы, инварианты и acceptance criteria
13. План внедрения и проверочный checklist
14. Итоговая операционная спецификация


# 1. Исполнительное резюме и выбранная архитектура
Исходные семь исследований закрывают одну общую задачу с разных сторон: как честно привязывать свободно порождённые LLM-интервенции к растущему каузальному lever-пространству, не превращая surface similarity в ложный causal bind. Их нужно объединить не как семь независимых модулей, а как один дисциплинированный firewall-слой между генератором интервенций и downstream-поиском/промоцией дизайнов.
Сводное решение называется Causal Grounding Firewall (CGF). Оно делает grounding не задачей поиска ближайшего имени, а задачей доказуемого соответствия typed causal object. Система принимает raw NL proposal, строит множество гипотез, проверяет совместную типовую и кросс-модальную состоятельность, классифицирует relation к существующим атомам, выдаёт либо bind с сертификатом, либо abstain/acquire/quarantine, либо novel-candidate, который проходит отдельный admission-предикат.
Короткая формула CGF
Grounding разрешён только как robust-singleton assignment, у которого relation-set безопасен во всех допустимых reference completions, все hard obligations закрыты, risk ledger покрывает probabilistic checks, а certificate привязан к версиям L2/L3/L6/WorldModelRecord и validator epoch.

Выбранная архитектура сознательно разделяет шесть разных функций, которые в наивных решениях обычно смешиваются: retrieval, causal relation classification, joint atom construction, abstention calibration, open-world admission, active acquisition. Это разделение устраняет главные противоречия между исследованиями.
RT1 определяет типизированные отношения grounding на каузальной, а не поверхностной эквивалентности.
RT4 строит один совместный type-consistent cross-modal атом; greedy per-axis допускается только для генерации candidate domains.
RT2 решает bind/abstain/novel-candidate и контролирует confident-wrong bind через certificates, reference lifting и risk ledger.
RT3 решает, когда novel-candidate становится новым реальным lever, когда нужен acquisition, а когда proposal reject’ится как hallucination.
RT5 гарантирует, что phrasing-only атака не повышает bind-confidence без нового causal evidence.
RT7 выбирает cheap-verify / elicit-human / acquire-data / adversarial-validate / abstain по robust VOI, но не имеет права купить bind ценностью или уверенностью формулировки.
RT6 оценивает не frozen accuracy, а весь trace under growth: raw -> shadow -> grounded/blocked/quarantine/acquire -> certificate.
Главный выбранный принцип: false bind хуже abstain. Поэтому вся архитектура оптимизирует не обычный precision/recall на замороженном словаре, а контролируемую частоту confident-wrong bind, hallucinated admission и cross-modal/type-inconsistent accept на растущем reference.

# 2. Анализ семи исследований и устранение противоречий
Сырые исследования во многом согласованы, но содержат пересечения полномочий. Ниже зафиксированы оптимальные решения и границы ответственности каждого RT. Это важнейшая часть сводки: без неё pipeline будет повторно решать одни и те же вопросы в разных местах, а спорные состояния будут ошибочно переводиться в bind или reject.
RT
Оптимальное выбранное решение
Граница ответственности
RT1
CRG: mechanistic signature, денотация через concrete do-queries, осевая решётка отношений, relation CSP, false-analog как обязательный класс.
Определяет relation(s, atom). Не admission’ит novel и не решает active acquisition.
RT2
CAAB: certificate-first abstaining binder. Relation-set + reference-lift + robust singleton + obligations + risk ledger. Conformal только efficiency/monitoring layer.
Решает bind/abstain/novel-candidate. Novel не равен new lever.
RT3
Open-world free-grow admission: completion set, proof obligations, stable uniqueness, VOI acquisition, admit/acquire/reject.
Решает real-new-lever vs needs-acquisition vs hallucination. Не подменяет promotion/value.
RT4
JTCG: joint MaxSMT/ILP/CP-SAT over operator, target, params, estimand, admissibility, L3/L6/knob/do/method.
Даёт совместный atom certificate или unsat core. Greedy per-axis не binding method.
RT5
EG-PIG: evidence-gated phrasing-invariant grounding; separate surface channel and causal evidence channel; proxy-gap -> QuarantineFront.
Защищает bind/admission от phrasing-only proxy-gaming. Не заменяет RT1/RT4 validators.
RT6
Executable benchmark without single gold: must+/may+/must-/unknown labels, stress/growth/private streams, false-bind headline.
Оценивает весь trace и safety/utility metrics under growth.
RT7
AG-VOI: robust EVSI over typed blockers and heterogeneous actions; safe decision set inherited from RT2/RT3.
Выбирает следующее действие при ambiguity. Не повышает confidence без закрытия obligations.


## 2.1. Главные конфликтные места и финальные решения
Generalization не считается безопасным single-atom bind. Она может быть useful relation, но downstream не должен интерпретировать её как exact atom. Внешний bind допускается только для exact; internal/specialization bind допускается только как certified-specialization с явными residual constraints.
Partial не является “почти bind”. Это shadow/supported state или вход в decompositional search. Partial bind без bundle certificate запрещён.
Novel-candidate RT2 — только утверждение “нет known atom, к которому можно безопасно привязать в текущем reference/epoch”. Admission нового рычага делает только RT3.
Conformal calibration не является самостоятельной гарантией под arbitrary growth/shift. Она применяется как set prediction/risk-control layer при проверенных условиях; при shift или cold-start она деградирует в diagnostic/throttling/abstain.
Reference uncertainty не штрафует score; она поднимает relation/grounding до set-valued ambiguity. Если хотя бы одна допустимая completion даёт unsafe relation, bind блокируется.
LLM/GY-K не является финальным решателем. GY-K — bounded entailment witness на ось/obligation; final decision принимает CSP/solver/validator плюс certificate.
Adversarial phrasing не лечится “более хорошим embedding”. Повышение surface score без нового causal evidence не должно повышать bind-confidence.
Unknown, timeout и contested status не мапятся в reject/admit/bind. Они становятся abstain, acquire, quarantine или shadow.
Итоговая позиция по оптимальности
Оптимальное решение — самое консервативное в safety gate и самое активное в acquisition layer: оно не привязывает сомнительное, но и не убивает novelty. Неопределённость сохраняется как typed blocker, после чего RT7 выбирает минимальное действие с положительным robust VOI.


# 3. Единая формальная модель

## 3.1. Центральный объект: atom
Атом lever-пространства — не строка, не label и не embedding node. Это структурный объект, который фиксирует оператор, target world slots, параметры, causal effect bundle, intended estimand, admissibility constraints и версию модели мира.
a = (
  operator,
  target_world_slot(s),
  params,
  direct_effect_bundle,
  intended_estimand,
  admissibility_constraints,
  world_model_version
)
Один и тот же атом обязан иметь взаимно согласованные представления в нескольких модальностях: NL description, legal/L3 threshold, L6 knob, do-expression, outcome/method expression и reference/world-model records. Cross-modal consistency означает равенство typed formulas, а не совпадение имён.

## 3.2. Proposal, hypothesis и mechanistic signature
На входе находится свободно порождённое предложение x. CGF не строит один embedding и не выбирает ближайший atom. Он строит множество гипотез H_t(x), каждая из которых имеет mechanistic signature.
sigma(h) = (
  op, X_do, x_do, sign, params,
  scope, unit, population, time,
  outcome Y, effect_path, estimand,
  admissibility, wm_version, evidence
)
Сигнатура денотирует множество concrete do-queries, совместимых с текущей неопределённостью reference:
[[sigma]]_{K_ref} = {
  q = (do(X_1=x_1,...,X_k=x_k), Y, scope, population,
       time, estimand, effect_path, admissibility)
  : q is compatible with sigma under K_ref
}
Это определение делает causal equivalence первичной. Surface similarity может поднять candidate в retrieval pool, но не входит в sufficient condition для exact, specialization или admission.

## 3.3. Reference как credal set, а не один словарь
L2/L3/L6/WorldModelRecord частично неполны, спорны и версионированы. Поэтому CGF представляет reference не как один truth snapshot, а как множество допустимых completions/repairs.
K_ref_t = K_L2_t x K_L3_t x K_L6_t x K_WMR_t
status(edge) in {confirmed, contested, incomplete, deprecated, out_of_scope}

Bind allowed only if every essential edge is confirmed or certified
under an allocated risk budget.
Для assignment x вводятся статусы: grounded, если constraints выполняются во всех relevant reference states; blocked, если невозможны во всех; shadow/supported, если существуют как supporting, так и unsafe/unknown completions.

## 3.4. Obligations как единый язык
Все RT используют общий obligation language. Это устраняет противоречие между “match confidence”, “admissibility”, “novelty” и “active acquisition”: любое решение становится просто функцией закрытых или открытых obligations.
Класс obligation
Смысл
Типичный unsafe outcome
type/slot
Оператор может писать target; target существует в WMR; unit/schema совместимы.
operator-target mismatch; nonexistent slot
do-semantics
Компиляция в canonical do-AST совпадает с atom.
measurement manipulation вместо intervention
scope/population
Population, geography, time, unit assignment согласованы.
firm vs household swap
estimand/effect
Outcome, effect path, estimand class согласованы с do-expression.
total effect принят за direct effect
L3/L6 cross-modal
Lex threshold применим к typed pair; knob writes same target.
legal/knob false analog
reference
Contested/incomplete edges учтены как set-valued uncertainty.
scalar confidence hiding ambiguity
admissibility
Legal/normative/implementation constraints удовлетворены или явно encoded.
inadmissible atom grounded as usable
data/evidence trust
Evidence может сужать world/reference state только после DataTrust.
simulation-only или polluted evidence сужает K_world
epoch
Certificate current for model/reference/validator versions.
stale certificate used after reference repair


# 4. End-to-end pipeline Causal Grounding Firewall
Ниже показан единый pipeline. Он deliberately conservative: любое отсутствие доказательства оставляет объект в shadow/acquire/quarantine, а не переводит его в bind.
CGF(x, State_t):
  1. Parse x into open canonical AST and claim graph.
  2. Retrieve high-recall candidate domains from L2/L3/L6/WMR plus adversarial neighbours.
  3. Run JTCG joint solver to construct feasible typed cross-modal atom candidates.
  4. For each feasible candidate, run RT1 CRG to produce relation-set certificate.
  5. Apply RT2 CAAB: reference-lift relation sets, close obligations, allocate risk.
  6. If exactly one robust safe candidate exists -> bind with GroundingCertificate.
  7. If no safe known atom and known-space coverage is certified -> novel-candidate.
  8. If novel-candidate -> RT3 free-grow admission: admit / acquire / reject.
  9. If adversarial proxy-gap or unresolved critical contradiction -> QuarantineFront.
 10. If blocker is resolvable under budget -> RT7 AG-VOI chooses next action.
 11. Every output is logged as certificate, unsat core, ambiguity record or acquisition ledger.
Статусная машина
raw -> parsed -> candidate -> shadow/supported -> grounded(bind) | blocked | quarantine | novel-candidate -> admit-new-lever | acquire-then-decide | reject. Ни один переход в grounded/admit не разрешён без certificate; ни один timeout не становится grounded.

Входное состояние
Проверка
Допустимый переход
raw NL proposal
canonical parse exists
parsed или reject(no intervention)
candidate atom
JTCG hard constraints SAT
feasible assignment или blocked(unsat core)
feasible assignment
RT1 relation-set + axis witnesses
exact/specialization/generalization/partial/compositional/false-analog/novel/unknown
relation-set
RT2 robust singleton and obligations pass
bind или abstain/novel-candidate
novel-candidate
RT3 proof obligations
admit/acquire/reject
ambiguous blocker
RT7 VOI
cheap-verify / elicit / acquire / adversarial_validate / abstain
high surface + low causal evidence
RT5 proxy-gap trigger
quarantine/adversarial_validate


# 5. RT1 + RT4: relation calculus и совместный typed cross-modal grounding

## 5.1. Почему RT1 и RT4 объединяются в engine
RT1 отвечает на вопрос “какое отношение между proposal и atom?”, а RT4 — “существует ли вообще один совместно согласованный atom assignment?”. В сводной архитектуре RT4 работает как конструктивный слой перед RT1 и как verifier его осевых witnesses. Это не слияние задач, а правильная последовательность: сначала невозможные склейки отсекаются joint constraints, затем оставшиеся сравниваются по causal relation.

## 5.2. Осевая решётка отношений RT1
Для каждой пары hypothesis h и atom a вычисляется отношение по оси j:
rho_j(h,a) in { equivalent, narrower, broader, overlap, contradiction, unknown }
J = {op, target, do_value, sign, params, unit, scope, population,
     time, outcome, effect_path, estimand, admissibility, wm_version}
J_crit = {op, target, do_value, sign, scope, population,
          outcome, effect_path, estimand}
Критическая несовместимость на J_crit является hard veto для exact/specialization/generalization. Это главный firewall против confident-wrong false analog.
Relation
Формальный критерий
Решение downstream
exact
Денотации proposal и atom совпадают; все critical axes equivalent; admissibility equivalent или atom constraints satisfied.
Может bind при RT2 robust-singleton и закрытых obligations.
certified-specialization
Proposal уже atom по scope/population/params, critical axes не меняются, residual constraints явно representable.
Может internal-bind как specialization, если downstream понимает residual constraints; иначе shadow.
generalization
Proposal шире atom; atom входит в денотацию proposal.
Не single-atom bind. Требует elicit/decompose/abstain.
partial
Есть пересечение, но нет equality/subset/superset или есть unresolved critical axis.
Shadow/decompositional search; не bind.
compositional
Proposal покрывается bundle атомов с coupling constraints.
Bundle certificate; single atom bind запрещён.
false-analog
Candidate surface-neighbor, но causal denotation disjoint или critical contradiction.
Quarantine/reject for that atom; не bind.
novel-candidate
Coherent signature не покрывается current registry без wrong bind.
RT2 output to RT3; не admit.
unknown
Недостаточно evidence/reference для classification.
Abstain/acquire.


## 5.3. JTCG: joint typed cross-modal solver
JTCG оптимизирует soft score только внутри hard feasible region. Soft score может включать retrieval, GY-K entailment confidence, L2 alignment quality и version freshness, но hard constraints имеют абсолютный приоритет.
x* = argmax_x S(u,x) subject to H(x) = true

X = {operator, target, params, effect_bundle, estimand, admissibility,
     law/L3, knob/L6, do_AST, method, scope, world_model_version}

Hard constraints include:
  slot_exists(target, version)
  allowed_target_type(operator, type(target))
  params in operator_schema(operator)
  unit_compatible(params, target, law, knob)
  lex_applicable(law, operator, target, scope)
  threshold_satisfied(law, params)
  knob_maps_to(knob, operator, target)
  do_AST == canonical_do(operator, target, params, scope)
  method.treatment == do_AST
  method.outcome in effect_bundle.outcomes
  admissibility_passed
  version_current
Если greedy per-axis выбрал валидный operator, валидный target, валидный L3 threshold и валидный knob, но комбинация invalid, JTCG возвращает blocked с unsat core. Это закрывает H5/H6: каждая ось может быть plausible, но bind должен быть совместным.
Кросс-модальная проверка
NL, legal/L3, knob/L6, do-AST и method-expression компилируются в typed formulas. Grounded status возможен только если formulas указывают на один operator, один target slot, совместимые params/scope и один estimand/effect bundle.


## 5.4. Relation CSP и precedence
После JTCG каждый candidate pair получает matrix M(h,a) = {rho_j, confidence_j, witness_j, evidence_span_j}. Финальная relation решается CSP, а не scalar similarity.
exact -> all critical axes equivalent
specialization -> all critical axes equivalent/narrower and at least one narrower
generalization -> all critical axes equivalent/broader and at least one broader
false_analog -> critical contradiction and retrieved_as_neighbor
partial -> intersection possible, no critical contradiction, not exact/specialization/generalization
compositional -> exists bundle A* with Cover(D(x), A*) = true
novel -> coherent(h) and no known atom/bundle safely covers h

Precedence:
  critical false_analog veto > exact > compositional > specialization >
  generalization > partial > novel-candidate > unknown
False-analog получает приоритет только при доказанной критической несовместимости. Если несовместимость не доказана, состояние остаётся unknown/partial, а не ложным false-analog.

## 5.5. GroundingRelationCertificate
GroundingRelationCertificate:
  proposal_id
  raw_text_hash
  candidate_atom_ids
  proposal_signature
  atom_signature_or_bundle
  relation_set
  selected_relation
  relation_confidence_scope
  reference_versions: {L2, L3, L6, WMR}
  axis_witnesses: [{axis, relation, confidence, witness, evidence_ref}]
  critical_contradictions
  unresolved_axes
  residual_constraints
  compositional_cover
  cross_modal_witnesses: {NL, L3, L6, do_AST, method}
  solver_status: SAT | UNSAT | UNKNOWN
  unsat_core_if_any
  recommended_transition: exact_bind | bundle_bind | shadow | quarantine | handoff_RT3
  validator_version
  stale_conditions

## 5.6. Soundness-инвариант RT1/RT4
Если существует critical axis j in J_crit, где rho_j = contradiction с sound witness, CSP делает exact, specialization и generalization infeasible. Если joint assignment нарушает хотя бы один hard constraint H, solver не может вернуть его как grounded. Поэтому surface similarity, LLM wording и per-axis maxima не могут преодолеть contradiction veto или joint-unsat core.

# 6. RT2: certificate-first adaptive abstention и гарантии false-bind

## 6.1. Решение: CAAB
Certificate-first Adaptive Abstaining Binder (CAAB) — слой, который переводит relation certificates в operational decision: bind, abstain или novel-candidate. Его главное свойство: bind возможен только при robust singleton; всё остальное сохраняется как ambiguity, acquisition need или quarantine.
Gamma_t(y,a) subset Relations
Gamma_ref_t(y,a) = union_{rho in K_ref_t} Gamma_t(y,a; rho)
R_bind = {exact, certified_specialization_with_residual_constraints}

Safe_t(y) = {
  a in Cand_t(y):
    Gamma_ref_t(y,a) subset R_bind
    and Pass_obligations(y,a) = true
    and no_active_alarm(scope(a))
}
Внешний production-bind рекомендуется начинать с R_bind={exact}. Certified-specialization можно включать только если downstream engine умеет хранить residual constraints, а specialization не меняет do-target, sign, target population/scope и estimand class.

## 6.2. Decision rule
Если |Safe_t(y)| = 1, вернуть bind(atom) с GroundingCertificate и risk usage.
Если |Safe_t(y)| > 1, вернуть abstain(reason=multiple robust-safe atoms) или set-valued internal result, но не single bind.
Если |Safe_t(y)| = 0 и есть known-space coverage certificate, вернуть novel-candidate и передать в RT3.
Если coverage/retrieval/reference completeness не доказаны, вернуть abstain или acquire-needed, а не novel.
Если drift alarm, stale epoch или cold-start cohort без proof-grade checks, bind freeze для affected scope.

## 6.3. Роль conformal и online calibration
Conformal используется не как корень гарантии, а как efficiency layer: relation-set conformal, proposal-level conformal risk control, adaptive thresholding under monitored shift. При нарушении exchangeability layer обязан деградировать в diagnostic/throttling/abstain. Это сохраняет честность RT2 при free-grow birth cohorts, prompt/model shift, adaptive search selection и reference revision.
Shift/нарушение
Что ломается
Что остаётся безопасным
Новый atom cohort
offline threshold старого словаря
proof-grade obligations; cold-start abstain; отдельная calibration stratum
Prompt/model shift
marginal coverage старого stream
hard certificate gate; drift alarm; epoch reset
Adaptive selection boundary cases
random held-out calibration
prequential audit или anytime-valid certificates
Reference revision
old labels/semantics
epoch-scoped certificates; stale -> revalidate
Contested reference
single-label conformal
reference-lifted relation set; bind только если lifted set safe


## 6.4. Гарантия RT2
При fixed active epoch, sound deterministic validators, anytime/adaptive-valid probabilistic certificates и predictable risk ledger CAAB даёт anytime-style гарантию для stopping time tau:
P( exists t <= tau : decision_t = bind(a_t) and a_t not in true_bind_set(y_t) )
  <= delta_cert + delta_ref + delta_runtime

If novel-candidate claims known-space reject, add delta_retrieval_novel.
The guarantee is conditional on active reference/world assumptions and epoch validity.
Рост lever-space не ломает эту гарантию, потому что CAAB не утверждает, что старый calibration set покрывает будущие atoms. Он требует per-instance certificate для каждого bind. После регистрации новый atom сразу searchable, но его calibration state начинается как cold-start.

## 6.5. RT2 certificate
GroundingDecisionCertificate:
  decision: bind | abstain | novel-candidate
  atom_id: only_if_bind
  epoch
  reference_versions: {L2, L3, L6, WMR}
  candidate_set_hash
  relation_set
  reference_lifted_relation_set
  obligations: {operator, target, direction, scope, estimand, admissibility, epoch}
  risk_used: {relation, reference, type_admissibility, retrieval, runtime, total}
  calibration_scope: {stratum, prompt_version, birth_cohort, effective_n, drift_state}
  abstain_reason
  novel_reason
  proof_artifacts
  validator_version
  limitations

# 7. RT3: free-grow admission реальных новых рычагов

## 7.1. Novel != real
RT3 начинается только после того, как RT2 честно установил: proposal не может быть safely bound к текущему known lever-space. Это ещё не доказательство реальности нового рычага. Novel означает “не привязано”, а real-new-lever означает “есть уникальный, новый, type-consistent, world-bound or acquirable, do-grounded, mechanistically witnessed and admissible atom”.
Decision_RT3(r) in { admit_as_new_lever, acquire_then_decide, reject_as_hallucination }

Admit iff exists unique c* in CompletionSet(r):
  NewIrreducible(c*)
  TypeConsistent(c*)
  WorldBindable(c*)
  DoSemantics(c*)
  MechanismWitness(c*)
  EstimandCoherent(c*)
  Admissible(c*)
  DataTrust(c*)
  StableUnique(c*)
  RiskLedgerAvailable(delta_adm)
  NoActiveAlarm(scope(c*))

## 7.2. Open-world completion set
RT3 строит множество completions C_t(r), а не один atom. Completion может указывать на существующий WMR slot, contested L2 variable, hidden/held-out real lever или NEW_SLOT, который должен быть acquired. Это сохраняет open-world semantics: отсутствие в reference не означает ложность.
c = (open_atom_skeleton, reference_hypothesis, evidence_bundle, missing_obligations)
C_t(r) = {c_1, ..., c_m}
a(c) = (op_c, target_c, params_c, effect_c, estimand_c, adm_c, wmv_c)

## 7.3. Admission proof obligations
Obligation
Pass condition
Если не выполнено
O_parse
typed open AST exists; proposal is intervention, not outcome wish
reject if no recoverable intervention; otherwise elicit
O_novel
not losslessly existing atom, parameter update, scope specialization, synonym or existing bundle
return to normal grounding or non-new
O_type
operator can write target; params schema/unit compatible
hard fail or acquire if type edge contested
O_world
target has WMR or feasible acquisition path to WMR
acquire or reject non-acquirable
O_do
proposal defines intervention kernel over real/acquirable world variable
reject outcome wish/proxy manipulation
O_mechanism
evidence-backed path/sign/scope/mediator/outcome witness
acquire or quarantine
O_estimand
outcome, population, horizon, comparator, unit, measurement and identification status coherent
acquire/elicit; no admit
O_admiss
legal/normative/implementation constraints pass or encoded as hard constraints
reject inadmissible-ever or acquire legal evidence
O_data
evidence can narrow world/reference state under DataTrust
store as weak evidence, not admission-grade
O_ambiguity
unique canonical completion among surviving incompatible completions
acquire-then-decide


## 7.4. Decision predicate
AdmissionPass(c) = all O_adm(c) are PASS
HardFail(c) = exists hard obligation with FAIL
Acquirable(c) = not HardFail(c) and exists feasible U resolving UNKNOWN/CONTESTED/TIMEOUT

admit_as_new_lever if exists c*:
  AdmissionPass(c*) and NewIrreducible(c*) and StableUnique(c*)

acquire_then_decide if no admit, but exists U with:
  cost(U) <= B_t
  SafetyGate(U) = PASS
  DataTrustPre(U) = PASS
  LCB_VOI(U; r) > 0 or U is necessary for high-value ambiguity

reject_as_hallucination only if every completion hard-fails or is non-acquirable
or violates admissibility-ever/world/do-semantics.
Unknown не является reject. Если real-but-needs-acquisition нельзя решить в текущем бюджете, корректный output — acquisition certificate with budget_blocked=true, а не hallucination label.

## 7.5. Free-grow registry patch
Admit-as-new-lever расширяет lever-space, но не переводит design в public DecisionFront. Новый atom получает статус grounded_admitted_new_lever/research-or-shadow; дальнейший search/promotion всё равно должен закрыть value, identification, calibration, data trust, implementation и normative gates.
On admit:
  AtomIndex += AtomRecord(a_new)
  L6.knob_dictionary += knob_record_if_certified
  L6.lex_intervention_map += mapping_if_certified
  WorldModelRecord += new_slot_if_acquired
  ObligationIndex += admission obligations
  EvidenceStore += proof artifacts
  RiskLedger += delta_adm spend
  Epoch metadata += admission certificate version

No automatic DecisionFront membership.

## 7.6. RT3 theorem
Если admission возможен только через RT3 gate, deterministic validators sound, probabilistic certificates adaptive-valid, risk ledger суммирует alpha до delta_adm, DataTrust/structural/legal assumptions поддерживаются в active epoch, а StableUnique enforced, то вероятность admitted hallucinated/non-real/non-admissible lever ограничена delta_adm. Теорема контролирует false admission, но не false rejection; false rejection снижает VOI/acquisition policy.

# 8. RT5: adversarial-устойчивость против proxy-gaming

## 8.1. Модель атаки
Атака RT5 — не обязательно взлом системы. Достаточно phrasing-only transformation T(x), которая сохраняет реальный mechanism и do-target proposal, но добавляет слова, legalistic camouflage, high-value outcomes, synonyms или explicit do()-риторику, чтобы поднять surface match к желаемому false atom. Если confidence зависит от phrasing, firewall можно gaming’овать.
Phrasing-only attack:
  real_mechanism(T(x)) = real_mechanism(x)
  causal_target(T(x)) = causal_target(x)
  evidence_set(T(x)) = evidence_set(x)
  SurfaceMatch(T(x), a_false) > SurfaceMatch(x, a_false)

Unsafe if C_bind(T(x), a_false) > C_bind(x, a_false)
without new causal evidence.

## 8.2. EG-PIG: Evidence-Gated Phrasing-Invariant Grounding
EG-PIG разделяет surface channel и causal evidence channel. Surface channel разрешён для retrieval and adversarial candidate expansion. Causal evidence channel определяет bind-confidence через закрытые obligations. Bind-confidence — функция evidence, reference status, type constraints, do/estimand/admissibility witnesses и risk ledger, а не функция красивой формулировки.
C_bind(x,a) = f(
  TargetEvidence, DirectionEvidence, ScopeEvidence, EstimandEvidence,
  OperatorTargetType, L3_L6_Consistency, WMR_Bind, ReferenceStatus,
  Admissibility, EpochValidity, RiskLedger
)

SurfaceMatch(x,a) may increase candidate priority,
but cannot increase C_bind unless it produces new valid evidence witnesses.

## 8.3. Proxy-gap quarantine
RT5 вводит GroundingProxyGapRisk: high surface match plus low causal evidence. Такие cases идут в QuarantineFront/adversarial_validate, даже если top-k retrieval и LLM rationale выглядят убедительно.
GPG(x,a) = SurfaceMatch(x,a) - EvidenceSupport(x,a)
If GPG high and relation not safe:
  route = QuarantineFront
  action = adversarial_validate
  bind = forbidden

## 8.4. RT5 theorem
Если C_bind зависит только от evidence-channel features и все phrasing-only transformations не меняют evidence witnesses, то C_bind не увеличивается под phrasing-only attack. Если transformation извлекает новый валидный evidence witness, это уже не phrasing-only attack; изменение confidence допустимо, но должно быть видно в certificate.

## 8.5. RT5 metrics
Метрика
Определение
Цель
Gaming success rate
P(attack causes confident wrong bind)
≈0, <= safety delta
WrongLift
max_T C_bind(T(x), a_false) - C_bind(x, a_false)
<=0 для phrasing-only
Phrasing invariance index
variation of confidence across paraphrases with same evidence
low
Mechanism sensitivity index
confidence drops when target/sign/scope/estimand changes
high
Quarantine capture rate
fraction high surface/low evidence cases routed to quarantine
high
Useful recall penalty
loss of real exact/specialization binds due to defense
bounded by agreed floor


# 9. RT7: активный grounding под VOI/бюджетом

## 9.1. RT7 как controller неоднозначности
RT7 не строит новый matcher. Он получает typed ambiguity из RT1/RT2/RT3/RT4/RT5 и выбирает действие, которое наиболее эффективно закрывает blocker. Правильная политика должна быть value-aware, budget-aware и safety-gated.
H_t(x) = {h_1,...,h_K}
h = (relation, atom_or_bundle_or_new, mechanism_slots,
     proof_obligations, reference_version, defect_class)
B_t(x) = {P(h): P compatible with evidence, calibration, reference uncertainty}

Terminal decisions D = {bind(a), bind_bundle(A), admit_new(a), reject, abstain/quarantine}
Safe(d,B_t) iff sup_{P in B_t} P(wrong_decision(d,h)) <= delta_remaining
              and ProofObligationsClosed(d)

G(B_t,S_t) = max_{d in D: Safe(d,B_t)} inf_{P in B_t} E[U(d,h;S_t)]
Abstain/quarantine всегда safe, но может быть utility-suboptimal. RT7 ищет не способ “продавить bind”, а способ купить evidence, который сделает более полезное safe decision допустимым.

## 9.2. Action space и blocker mapping
Blocker
Лучшее первое действие
Почему
axis relation unknown but evidence in L2/L3/L6 exists
cheap_verify
дешёвый bounded entailment/reference check может закрыть obligation
human intent ambiguous
elicit_human
только автор proposal может прояснить intent/scope, но не factual/legal truth
missing WMR slot or measurement process
acquire_data
нужна world/measurement acquisition через N7
legal threshold contested
legal/lex acquisition or expert review
нельзя выводить admissibility из surface legal wording
high surface/low causal evidence
adversarial_validate
proxy-gap и fake-grounding требуют challenge set
multiple robust-safe atoms
elicit or acquire discriminating evidence
single bind forbidden until uniqueness
low VOI or unsafe costs
abstain/quarantine
не каждую ambiguity рационально закрывать


## 9.3. Двухуровневый VOI
VOI состоит из grounding VOI и search leverage VOI. Grounding VOI оценивает, насколько действие улучшит safe grounding decision. Search leverage VOI оценивает downstream frontier gain, если atom окажется корректно grounded. Важно: downstream value не может снять delta-gate и не может повысить confidence bind.
VOI_G(m) = E_o[ G(Update(B_t,m,o), S_t) ] - G(B_t,S_t)

V_search(a;S_t) = E[Delta Frontier(a) | S_t] * StakeWeight * AuthorityGainWeight * DeadlineWeight

VOI(m|B_t,S_t) = inf_{P in B_t} E_o[G(Update(B_t,m,o),S_t)]
                 - G(B_t,S_t)
                 - lambda^T cost(m)
                 - model_uncertainty_penalty(m)

Choose m* = argmax feasible_m LCB(VOI(m)) / bottleneck_cost(m)
subject to hard safety gates and budget vector.

## 9.4. AG-VOI policy
AG_VOI(x, ambiguity_record, budgets):
  blockers = extract_typed_blockers(ambiguity_record)
  actions = propose_actions(blockers, {cheap_verify, elicit, acquire, adversarial_validate, abstain})
  actions = filter_by_hard_budget_safety_datatrust(actions)
  for m in actions:
      estimate observation model and LCB_VOI(m)
  if max LCB_VOI(m) <= 0:
      return abstain/quarantine with remaining_high_VOI_actions=[]
  execute action with best LCB_VOI / bottleneck_cost
  update belief, obligations and risk ledger
  re-run CAAB/RT3 gate
  stop only at typed terminal state: bind, admit, reject, abstain, acquisition_required, budget_exhausted, tool_failure

## 9.5. Dominance over passive abstain
Если LCB[VOI(m)] является корректной нижней границей net value, а bind/admit всегда проходят delta-safe gate, one-step AG-VOI имеет ожидаемую utility не ниже passive abstain: passive abstain уже в safe decision set, AG-VOI выбирает действие только при положительной lower-bound net value, иначе возвращает тот же safe abstain. Это dominance по expected utility, не обещание “найти больше bind любой ценой”.

# 10. RT6: протокол оценки без стабильного gold-standard

## 10.1. Truth as obligation set
В растущем и contested reference нет одного стабильного gold ID. RT6 хранит evaluation truth как obligation set: must+, may+, must-, unknown и required obligations. Это позволяет честно оценивать partial identification, contested L2 edges и real-but-needs-acquisition cases.
Y_i = (
  must_plus,     # bindings definitely correct
  may_plus,      # acceptable under one supported interpretation
  must_minus,    # definitely wrong / false analog
  unknown,       # requires acquisition/adjudication
  required_obligations
)

## 10.2. Benchmark structure
RT6 benchmark состоит из seed anchors, calibration stream, stress sets, growth stream and private adversarial stream. Он должен оценивать не только final answer, но и trace/status/certificate.
Набор
Как строится
Что проверяет
Seed canonical anchors
Known valid L6 knobs + L3 thresholds + WMR slots
baseline correctness and deterministic checks
Calibration
held-out relation/admission/action outcomes by strata/epoch
confidence/risk tuning
False-analog stress
minimal swaps of target/sign/scope/estimand/proxy/knob with high similarity
causal vs surface equivalence
Novel-lever set
held-out real knobs + hallucinated novel + real needs acquisition
free-grow vs pollution
Compositional set
one NL -> bundle, atom+constraint, dependency edges
granularity mismatch
Cross-modal inconsistent
NL/L3/L6/do/method individually plausible but jointly conflicting
H6 and RT4
Joint type-inconsistent
each axis valid, combination invalid
greedy per-axis failure
Adversarial phrasing
surface markers, legalistic camouflage, synonym flooding, confidence bait
RT5
Growth stream
R0 subset R1 ... with new variables/thresholds/knobs/WMR and reference repairs
free-grow, latency, stale certificates
Private adversarial stream
non-public cases and fresh variants
benchmark contamination resistance


## 10.3. Metrics
Headline — false-bind / confident-wrong rate, not headline precision/recall. Precision/recall остаются полезными, но только после safety metrics и с explicit denominator under growth.
FBR_tau = sum_i w_i * 1[D_i=bind and q_i>=tau and WrongBind_i]
          / max(1, sum_i w_i * 1[D_i=bind and q_i>=tau])

WrongBind includes:
  false-analog bind
  target/sign/scope/estimand violation
  cross-modal-inconsistent acceptance
  joint type-inconsistent acceptance
  pre-registration novel bound to old atom
  hallucinated novel admitted

Publish interval [FBR_tau^-, FBR_tau^+] for contested labels.
Группа метрик
Примеры
Safety
FBR_confident, CWB, hallucination_admission_rate, cross_modal_accept_rate, joint_type_accept_rate, gaming_success_rate
Utility
strict/permissive/worst-case bind precision, visible recall, eventual recall, useful non-abstain yield
Abstention
good abstention, bad abstention, abstain reason distribution, unresolved obligation correctness
Free-grow
novel admission precision, real novel resolved, acquire routing precision, free-grow latency p50/p90/p99, duplicate growth
Calibration
ECE/Brier per relation/slice, relation-set coverage, UCB false-bind by slice
Auditability
certificate completeness, unsat core coverage, replay completeness, stale certificate handling
RT7
SafeGroundedValue@C, Lift@C over passive abstain, action regret vs oracle, VOI calibration error


## 10.4. Denominators under growth
Raw stream denominator: все proposals в epoch e, включая ungroundable, out-of-scope и ambiguity.
Stratified standard denominator: fixed stress suite для сравнимости между systems and epochs.
Epoch-local denominator: visible reference R_e; оценивает корректность в текущем registry.
Retroactive denominator: cases from epoch e re-evaluated after future reference growth R_{e+k}; ловит pre-registration false bind and free-grow latency.

## 10.5. Baselines and pass condition
Обязательные baselines: exact/alias match, pure embedding, closed-vocab entity linker, cross-encoder similarity, greedy per-axis, LLM JSON/judge, always reject novelty, low-similarity novelty, passive abstain, always ask human, uncertainty-only active. Сводный метод должен выиграть по false-bind and hallucination admission while preserving useful recall/free-grow.
RT6 success =
  low confident FBR under growth/stress
  + non-zero useful recall/free-grow
  + high novel admission precision
  + bounded free-grow latency
  + complete auditable certificates

If headline report is only frozen precision/recall, RT6 failed.

# 11. Схемы данных и API-контракты
Ниже приведены минимальные схемы. Они должны быть versioned, replayable and auditable. Поля могут быть расширены, но не должны удаляться из certified pipeline.

## 11.1. AtomRecord
AtomRecord:
  atom_id
  operator_id
  target_world_slots
  params_schema
  params_current_or_template
  direct_effect_bundle
  intended_estimand
  admissibility_constraints
  world_model_version
  reference_versions: {L2, L3, L6, WMR}
  modalities: {NL_description, L3_lex_ids, L6_knob_ids, do_AST, method_ids}
  status: registered | grounded_admitted_new_lever | deprecated | contested
  certificates
  stale_conditions

## 11.2. GroundingCertificate
GroundingCertificate:
  certificate_type: RT1_RT4_RT2_GroundingCertificate
  proposal_id
  raw_text_hash
  decision: bind | abstain | novel-candidate | blocked | quarantine
  atom_or_bundle_ref
  relation_set
  selected_relation
  reference_lifted_relation_set
  joint_assignment
  hard_constraints_passed
  axis_witnesses
  modal_witnesses
  risk_used
  calibration_scope
  unsat_core_if_blocked
  abstain_or_quarantine_reason
  epoch
  validator_version
  replay_hash

## 11.3. AdmissionCertificate
AdmissionCertificate:
  proposal_id
  raw_proposal_hash
  parsed_open_AST
  completion_set_hash
  decision: admit-as-new-lever | acquire-then-decide | reject-as-hallucination
  admitted_atom_id
  novelty_witness
  proof_obligations_status
  evidence_refs
  acquisition_plan_if_any
  rejection_reasons_if_any
  risk_accounting
  reference_versions
  validator_version
  stale_conditions

## 11.4. GroundingAmbiguityRecord and AG-VOI schemas
GroundingAmbiguityRecord:
  candidate_id
  nl_intervention
  reference_snapshot
  hypothesis_set: [{relation, atom_ref, bundle_refs, proposed_new_atom,
                    posterior_interval, mechanism_slots, open_obligations, blockers}]
  current_safe_decisions
  risk_bound
  proof_obligations_closed

GroundingActionProposal:
  action_id
  action_type: cheap_verify | elicit_human | acquire_data | adversarial_validate | abstain
  target_blocker
  expected_observations
  evidence_contract_type
  cost_vector
  hard_budget_feasible
  blocked_by

GroundingVOIEstimate:
  action_id
  current_grounding_value
  expected_post_action_value
  evsi_mean
  evsi_lcb
  evpi_upper_bound
  decomposition
  selected
  selection_reason

ActiveGroundingLedger:
  candidate_id
  actions_taken
  observations
  belief_before_after
  realized_cost
  authority_boundary
  final_state
  remaining_high_voi_actions
  replay_hash

## 11.5. Validator API
validate_grounding(candidate_hypergraph, obligations, evidence_bundle,
                    reference_credal_set, alpha_budget, epoch)
  -> ValidationResult(status, passed_obligations, failed_obligations,
                      unknown_obligations, risk_used, witnesses, unsat_core)

relation_certificate(proposal, atom_or_bundle, reference_set, alpha_budget)
  -> RelationSetCertificate

admission_validate(open_completion, admission_obligations, evidence_bundle,
                   reference_set, alpha_budget, epoch)
  -> AdmissionValidationResult

active_grounding_step(ambiguity_record, budgets, search_state)
  -> ActionProposal or terminal safe decision

# 12. Единые теоремы, инварианты и acceptance criteria

## 12.1. Инварианты
Embedding cannot bind: sim(x,a) may retrieve a; sim(x,a) cannot imply bind(x,a).
Critical contradiction veto: contradiction on op/target/do_value/sign/scope/population/outcome/effect_path/estimand blocks exact/specialization/generalization.
Joint feasibility: no grounded atom unless operator-target-param-lex-knob-do-method-admissibility constraints are jointly satisfiable.
Reference lifting: bind only if all essential reference completions keep relation inside safe bind set.
Novel isolation: low similarity never admits new lever; novel-candidate routes to RT3.
Unknown preservation: unknown/timeout/contested never becomes bind/admit/reject without additional evidence.
Phrasing invariance: surface-only changes cannot increase bind confidence without new causal evidence.
VOI safety: RT7 may choose actions but cannot bypass RT2/RT3 safety gates.
Epoch scoping: certificates are valid only for declared reference/model/validator epoch; revision stales affected certificates.
Trace auditability: every terminal decision must be replayable from artifacts, obligations, witnesses and risk ledger.

## 12.2. Unified false-bind guarantee
Under maintained assumptions — sound deterministic validators, adaptive-valid probabilistic certificates, true reference/world state contained in declared credal set except delta_ref, predictable risk ledger and enforced gates — CGF controls confident-wrong bind before any stopping time tau:
P( exists t <= tau : confident_wrong_bind_t )
  <= delta_ground
  = delta_RT1_relation + delta_ref + delta_type_adm + delta_runtime + delta_monitor

If the output is novel-candidate/no-known-bind, include delta_retrieval_novel
for candidate-set coverage. If the output is admission, use RT3 delta_adm.

## 12.3. Unified no-hallucination-growth guarantee
P( exists admitted atom a : a is not real/admissible/do-grounded ) <= delta_adm
provided admission only occurs through RT3 gate, StableUnique is enforced,
and every probabilistic/deterministic certificate obeys its declared validity.

## 12.4. Acceptance criteria by RT
RT
Acceptance criteria
RT1
Formal relation calculus + executable CRG + decisive false-analog stress-set + FABR@0.90 <= target and >=10x lower than best similarity baseline.
RT2
Robust-singleton CAAB; UCB(FBR_bind_slice) <= delta across normal/growth/shift/false-analog/reference slices; honest failure under exchangeability violations.
RT3
Admission predicate with obligations; stress-set separates real-novel/hallucinated/needs-acquisition; hallucination admission <= delta_adm; real-novel resolved > always-reject.
RT4
Joint solver rejects greedy-inconsistent cases; cross-modal mismatch rejection high; certificate contains versions and unsat cores.
RT5
Phrasing-only attacks cannot lift wrong bind confidence; gaming success rate after defense <= delta; high proxy-gap captured by quarantine.
RT6
Executable benchmark with seed/calibration/stress/growth/private streams; interval labels; full scoreboard with false-bind headline.
RT7
AG-VOI lift over passive abstain at fixed cost with no increase in false-bind or hallucinated admission; calibrated action observation models.


# 13. План внедрения и проверочный checklist

## 13.1. Фазы внедрения
Фаза
Что сделать
Exit criteria
0. Reference audit
Версионировать L2/L3/L6/WMR; проставить statuses confirmed/contested/incomplete/deprecated.
Reference credal set строится автоматически; stale conditions определены.
1. JTCG/CRG shadow mode
Реализовать parse -> candidate domains -> joint solver -> relation CSP -> certificates без production bind.
Все outputs имеют relation/unsat/unknown certificates; false analog stress не bind’ится.
2. CAAB bind gate
Включить robust-singleton, reference lifting, risk ledger, calibration strata and drift alarms.
Production bind только exact/certified-specialization with certificate.
3. RT3 free-grow
Реализовать open completions, admission obligations, acquisition plans, registry patch.
Real-novel admitted or routed to acquisition; hallucinated not admitted.
4. RT5 defense
Добавить proxy-gap risk, adversarial_validate, phrasing-invariance tests.
Phrasing-only attacks не поднимают bind confidence.
5. RT7 active controller
GroundingAmbiguityRecord, ActionProposal, VOI estimation, action ledger.
Positive Lift@C over passive abstain without safety regression.
6. RT6 benchmark runner
Seed/calibration/stress/growth/private streams, interval labels, report card.
Scoreboard publishes FBR/confidence intervals by slice and epoch.


## 13.2. Minimal engineering checklist
Every bind has atom_id, relation_set, reference_lifted_relation_set, axis witnesses, modality witnesses, risk usage and epoch.
Every abstain has reason: relation ambiguity, reference contested, insufficient coverage, drift alarm, proof timeout, multiple safe atoms or acquisition required.
Every novel-candidate has known-space coverage evidence or is downgraded to abstain/reference repair.
Every admission has completion-set hash, novelty witness, WMR/world-bind proof, mechanism witness, admissibility proof and StableUnique result.
Every reject-as-hallucination has hard-fail/non-acquirable proof; unknown is not reject.
Every blocked joint assignment has human-readable unsat core.
Every quarantine case includes GroundingProxyGapRisk and adversarial_validate plan.
Every active action has expected observations, cost vector, EVSI/LCB, authority boundary and realized outcome.
Every benchmark run stores visible reference snapshot, hidden truth/obligation model, system trace, certificates and replay hash.

## 13.3. Common implementation mistakes to forbid
Tuning one cosine or cross-encoder threshold and calling it grounding.
Allowing LLM JSON schema validity to count as joint grounding.
Collapsing contested reference into a scalar confidence penalty.
Binding generalization or partial as if they were exact.
Calling low-similarity proposals novel-real.
Rejecting all novelty to avoid false admission.
Using conformal thresholds from old vocabulary under new atom cohorts without epoch/cold-start handling.
Evaluating only precision/recall on a frozen test set.
Letting search value or surrogate score relax grounding gates.
Treating human elicitation as authority for world/legal facts rather than intent clarification unless separately qualified.

# 14. Итоговая операционная спецификация
Единая формула решения
Bind = exact/certified-specialization relation set, lifted over reference uncertainty, unique across candidates, joint typed/cross-modal SAT, all grounding/admissibility/epoch obligations passed, risk ledger within delta.
Abstain/acquire = default for non-singleton, contested, unknown, partial, generalization, unresolved composition, drift, proof timeout or insufficient candidate coverage.
Novel-candidate = no known atom safely covers proposal and known-space coverage is certified; admission still requires RT3.
Admit-new-lever = unique new irreducible atom that is type-consistent, world-bound, do-grounded, mechanistically witnessed, estimand-coherent, admissible and risk-certified.
Reject = all completions hard-fail or are non-acquirable/inadmissible-ever; unknown is not reject.
Quarantine = high surface match with low causal evidence, adversarial/proxy-gap, fake-grounding or validator-boundary case.
Active grounding = choose next safe evidence/action by lower-bound VOI per cost; never bypass gates.

В таком виде семь исследований становятся одним непротиворечивым решением. RT1 задаёт семантическую классификацию отношений, RT4 гарантирует совместность атома, RT2 обеспечивает calibrated abstention и false-bind control, RT3 реализует free-grow без hallucinated pollution, RT5 защищает firewall от phrasing-only proxy gaming, RT7 рационально тратит бюджет на закрытие typed blockers, а RT6 доказывает поведение системы на растущем, shifting и частично неопределённом reference.
Ключевой критерий успеха: система не обязана всегда отвечать bind. Она обязана не делать confident-wrong bind, честно показывать, чего не хватает для решения, расти только на реальных новых рычагах и оставлять аудируемый trace для каждого перехода.


# Приложение A. Компактная матрица stress-наборов
Stress slice
Пример механизма
Expected behavior
False analog: target swap
firm subsidy wording near household training subsidy
false-analog/quarantine, not bind
False analog: sign swap
lower payroll tax vs raise payroll tax
critical contradiction veto
Param/unit swap
cap fees at 5% vs raise fees by 5pp
do_value/unit contradiction
Scope/population swap
rural low-income households vs universal household benefit
specialization/generalization, not exact
Estimand swap
controlled direct effect vs total effect
false-analog/partial unless represented separately
Proxy/outcome swap
test-score reporting incentive vs true learning outcome
false-analog unless calibration certificate
Compositional
raise subsidy and cap prices
bundle certificate or partial; no single exact bind
Cross-modal inconsistent
NL household subsidy, L3 firm payroll tax, knob tax_credit_rate, method firm LATE
blocked with unsat core
Joint type inconsistent
valid operator + valid target + valid threshold but lex not applicable to pair
blocked/shadow, not grounded
Novel real
held-out valid knob with WMR target and mechanism evidence
admit if obligations pass
Hallucinated novel
legislate outcome directly or manipulate proxy denominator
reject/quarantine with hard fail
Needs acquisition
plausible real lever with missing WMR/measurement/legal proof
acquire-then-decide
Adversarial phrasing
legalistic camouflage, synonym flooding, confidence bait
no confidence lift; quarantine if proxy-gap
Growth shift
new atom registered after old false-neighbour existed
pre-registration abstain/novel; post-registration bind without retraining


# Приложение B. Итоговый scoreboard-шаблон
SYSTEM: candidate_grounder_vX
VISIBLE REFERENCES: L2 v..., L3 v..., L6 v..., WMR v...
EPOCHS: R0 -> Rn
CONFIDENCE THRESHOLD: tau = 0.90
DELTA TARGETS: false_analog, adversarial, novel_admission, promotion

HEADLINE SAFETY:
  FBR_confident overall: lower / upper / UCB
  FBR_false_analog: lower / upper / UCB
  FBR_novel_pre_registration: lower / upper / UCB
  FBR_cross_modal: lower / upper / UCB
  FBR_adversarial: lower / upper / UCB
  hallucinated_admission_rate: lower / upper / UCB

GROUNDING UTILITY:
  bind precision strict/permissive/worst-case
  visible recall / eventual recall
  good_abstention_rate / bad_abstention_rate

FREE-GROW:
  novel admission precision
  real novel resolved
  acquire routing precision
  free-grow latency p50/p90/p99
  duplicate growth / dictionary pollution

STRUCTURE:
  compositional exact bundle recall
  cross-modal inconsistency accept rate
  joint type inconsistency accept rate
  unsat-core auditability

CALIBRATION/AUDIT:
  ECE overall/per-stratum
  relation-set coverage
  certificate completeness
  replay completeness
  stale certificate handling

RT7:
  SafeGroundedValue@C
  Lift@C over passive abstain
  false_bind_rate_AGVOI
  action selection regret vs oracle
  VOI calibration error

# Приложение C. Финальный минимальный research deliverable
Executable CRG/JTCG prototype producing relation and joint grounding certificates.
CAAB binder with reference lifting, risk ledger, calibration strata and drift alarms.
RT3 admission validator with open-world completion enumeration and acquisition handoff.
RT5 adversarial validation harness with phrasing-only attack generator.
AG-VOI active controller with action observation models and budget ledger.
RT6 benchmark runner with seed/calibration/stress/growth/private streams and interval labels.
Report card comparing exact-match, embedding, entity-linker, greedy-axis, LLM-judge, passive-abstain and full CGF.
Replayable certificate store for every bind, abstain, novel-candidate, admit, reject and quarantine decision.


# Приложение D. Детализированная спецификация RT1: relation calculus
Это приложение разворачивает компактную формализацию из основной части в executable checklist. Его задача — исключить неоднозначность между relation taxonomy и operational decision. Relation label не равен final decision: RT1 говорит, “что это за отношение”; RT2 решает, можно ли по нему bind’ить.

## D.1. Exact
Exact означает совпадение do-query, а не совпадение фразы. Обе стороны должны mutual-entail все critical axes. Если proposal явно указывает subset of population, это уже specialization, а не exact; если proposal шире, это generalization; если совпадает target but differs in estimand, это false-analog или partial, но не exact.
Exact(h,a) iff:
  [[sigma(h)]]_{K_ref} == [[sigma(a)]]_{K_ref}
  and forall j in J_crit: rho_j(h,a) == equivalent
  and admissibility(h) <=> admissibility(a) or h satisfies atom constraints

Required witnesses:
  C_op, C_target, C_do_value, C_sign, C_scope, C_population,
  C_outcome, C_effect_path, C_estimand, C_admissibility, C_epoch
Exact проверка
Что считается pass
Что переводит out of exact
operator
same causal operator class and implementation mode
subsidy vs tax credit; disclosure vs audit
target
same WMR/L2 slot or certified version-equivalent slot
firm subsidy vs household transfer
do_value/sign
same transform or same set/cap/increase semantics
cap-at-5% vs increase-by-5pp
scope/population
same assignment unit and eligible population
large employers vs all employers
outcome/effect path
same outcome and path semantics
proxy outcome vs true outcome
estimand
same estimand class and treatment/outcome semantics
total effect vs controlled direct effect
admissibility
same legal/normative constraints or proposal satisfies atom constraints
threshold from wrong legal pair


## D.2. Certified-specialization
Specialization — полезное отношение, но оно опасно, если downstream хранит только atom_id без residual constraints. Поэтому выбран термин certified-specialization: specialization может стать bind-like только если residual constraints representable, не меняют critical causal target и явно попадают в certificate.
CertifiedSpecialization(h,a) iff:
  [[sigma(h)]] subset [[sigma(a)]]
  and forall critical axes: rho_j in {equivalent, narrower}
  and no target/sign/estimand class change
  and residual_constraints are representable in atom schema
  and downstream accepts residual constraints as part of bound object
Пример safe specialization: “audit probability for large employers from 2% to 5%” к атомy “audit probability for employers” при residual population=large_employers. Пример unsafe: “subsidy to low-income households” к “household welfare support” если atom не различает cash transfer, tax credit и service subsidy.

## D.3. Generalization
Generalization запрещено использовать как single-atom bind, потому что предложение шире кандидата. Binding конкретного atom’а в таком случае является необоснованным narrowing. Правильный route — elicit, decompose, set-valued candidate или abstain.
Generalization(h,a) iff:
  [[sigma(a)]] subset [[sigma(h)]]
  and forall critical axes: rho_j in {equivalent, broader}
  and exists j: rho_j == broader

Operational decision:
  no external bind; recommended action = elicit_scope_or_target | acquire | abstain

## D.4. Partial and compositional
Partial возникает, когда один atom покрывает только часть proposal, либо relation неразрешима из-за critical unknown. Compositional — более сильная и полезная структура: proposal покрывается bundle атомов с coupling constraints. Отличие важно: partial нельзя выдавать как bundle; compositional требует proof of cover.
Partial(h,a) iff:
  intersection([[h]], [[a]]) != empty
  and not equality/subset/superset
  and no proven critical contradiction

Compositional(x) iff:
  exists A* = {a_1,...,a_k}, k >= 2:
    forall components h_i: relation(h_i,a_i) in {exact, certified-specialization}
    and Compose(A*) == [[x]] under coupling constraints
Coupling constraints must encode shared budget, shared eligibility, timing, legal thresholds, measurement dependencies and equilibrium interactions.
If only one component is found, result is partial/shadow, not exact.
If decomposition is ambiguous, RT7 can choose elicit/acquire by VOI.

## D.5. False-analog
False-analog — обязательный класс, а не просто “wrong”. Он возникает, когда proposal и candidate surface-neighbours, но causal denotations disjoint or critically contradictory. Это главный class для stress testing, потому что на нём embedding, entity-linking и LLM-judge выглядят уверенно, но ошибаются.
FalseAnalog(h,a) iff:
  retrieved_as_neighbor(x,a)
  and ( [[sigma(h)]] intersect [[sigma(a)]] == empty
        or exists j in J_crit: rho_j(h,a) == contradiction )

Fatal axes:
  target, sign, do_value, population/scope, estimand/effect_path,
  outcome/proxy, legal/knob target, method/treatment
False-analog slice
Temptation
Causal fault
target sibling
same words subsidy/training
firm hiring subsidy != household training subsidy
op swap
tax credit and subsidy both fiscal
tax liability mechanism != direct transfer mechanism
sign swap
raise/lower hidden in legal wording
opposite intervention direction
do-value/unit
5% appears in both
cap-at-5% != increase-by-5pp
scope/population
same outcome vocabulary
different assignment unit
estimand
both estimate effect
total effect != controlled direct effect
proxy/outcome
same policy goal
test score/reporting proxy != true learning/welfare
knob/legal
same threshold phrase
threshold applies to different operator-target pair


## D.6. Novel-candidate
Novel-candidate in RT1/RT2 значит “не покрывается known registry без unsafe bind”. Для этого надо не только отсутствие exact; надо показать, что ближайшие known candidates либо rejected/false-analog/partial/generalization, либо coverage недостаточно и тогда output должен быть abstain/acquire rather than novel.
NovelCandidate(x) iff:
  exists coherent h in H(x)
  and forall known atoms/bundles A_t: Cover(h,A_t) is false or unsafe
  and nearest surface neighbours have contradiction/rejection certificates
  and known-space coverage certificate is sufficient for the claim

Else: abstain(coverage_insufficient) or acquire_reference.


# Приложение E. Детализированная спецификация RT2: CAAB, risk ledger, calibration
RT2 превращает relation certificates в decision. Оптимальный вариант — не “conformal threshold”, а certificate-first binder. Вся probabilistic calibration становится вспомогательной: она помогает уменьшить abstention, но не разрешает bind без proof obligations.

## E.1. Candidate set requirements
Для каждого proposal candidate set должен включать не только top semantic neighbours, но и adversarial counter-neighbours. Иначе система может не увидеть dangerous false analog and falsely claim novelty/coverage.
Cand_t(x) =
  Retrieve_lex(x,A_t)
  union Retrieve_embedding(x,A_t)
  union Retrieve_L2_variable_alignments(x)
  union Retrieve_L3_thresholds(x)
  union Retrieve_L6_knobs_lex_maps(x)
  union Causal_neighbourhood(x)
  union Adversarial_false_analog_countercandidates(x)

Candidate-set coverage certificate is required only when claiming novel/no-known-bind.

## E.2. Reference lifting algorithm
For each candidate atom a:
  Gamma_ref = empty
  for each reference completion rho in K_ref_t, or conservative symbolic class:
      Gamma_rho = RelationSetCertificate(x,a;rho)
      Gamma_ref = Gamma_ref union Gamma_rho
  if Gamma_ref subset R_bind and obligations pass:
      candidate is safe
  else:
      candidate is ambiguous/unsafe; do not bind
В implementation не обязательно перечислять все completions, если reference credal set огромен. Достаточно symbolic/lifted analysis: confirmed edges are fixed, contested edges produce unsafe alternatives unless an obligation proves they cannot affect this relation.

## E.3. Risk ledger decomposition
Bucket
Назначение
Когда тратится
delta_RT1_rel
relation-set coverage exact vs false/partial/generalization
probabilistic relation verifier or GY-K axis witness
delta_ref
true reference/world completion outside declared credal set
reference repair/adjudication assumptions
delta_type_adm
probabilistic type/admissibility checks
non-deterministic legal/type validators
delta_retrieval_novel
known correct atom absent when claiming novel
only no-known-bind/novel-candidate claims
delta_runtime
stale epoch, validator bugs, tool failures
runtime certification and audit tests
delta_monitor
online drift/calibration alarms
monitoring false negative risk

delta_ground = delta_RT1_rel + delta_ref + delta_type_adm
               + delta_retrieval_novel + delta_runtime + delta_monitor

risk_used(C) = sum_{executed probabilistic checks q} alpha_q
bind allowed only if risk_used(C) <= allocated remaining budget.

## E.4. Calibration strata and cold-start policy
Calibration state должен быть stratified. Иначе общая ECE может выглядеть хорошей, но false-analog slice будет некалиброванной. Минимальная страта: operator_family, target_type, domain, proposer_model, prompt_version, atom_birth_cohort, reference_epoch.
CalState[e,k] = {
  calibration_examples,
  lambda_thresholds,
  effective_n,
  drift_martingale,
  audit_rate,
  last_reference_version,
  birth_cohort_status: mature | cold_start
}

Rules:
  new prompt/model -> new stratum or epoch
  new atom cohort -> cold_start
  reference repair -> epoch reset
  low effective_n -> proof-grade-only or high abstain
  adversarial stress failure -> quarantine scope and lower confidence

## E.5. Decision audit states
Output
Required certificate
Typical reason
bind
robust safe singleton; obligations pass; risk ledger within delta
exact known atom
abstain_relation_ambiguity
non-singleton or unsafe relation set
exact/false-analog/partial unresolved
abstain_reference
contested L2/L3/L6/WMR edge affects relation
household-firm alignment contested
abstain_drift
calibration/epoch alarm active
prompt/model/reference changed
novel-candidate
no known safe bind plus coverage certificate
coherent new mechanism
acquire-needed
blocker resolvable with evidence/action
missing WMR, legal threshold, measurement
quarantine
proxy-gap/adversarial risk
surface high / causal evidence low



# Приложение F. Детализированная спецификация RT3: open-world admission
RT3 — ключ к free-grow. Его задача — не “сказать новое или не новое”, а управлять открытым миром: admission, acquisition or reject. Здесь особенно важно не допустить двух симметричных ошибок: admit hallucination and reject real novelty.

## F.1. Completion enumeration
EnumerateCompletions(open_AST, L2, L3, L6, WMR):
  candidate_existing_slots = retrieve WMR/L2 slots by target/operator/scope
  candidate_contested_slots = retrieve contested alignments and incomplete edges
  candidate_new_slots = instantiate NEW_SLOT templates if type/acquisition path plausible
  candidate_knobs = retrieve L6 knobs and open knob templates
  candidate_laws = retrieve L3 thresholds and legal/admissibility candidates
  candidate_mechanisms = retrieve evidence paths and WMR causal graph fragments
  return cartesian/product pruned by type and evidence constraints
Enumeration должна быть high-recall but safe. Pruning может отбрасывать type-impossible combinations; semantic low-score alone must not prune real open-world completions if evidence path exists.

## F.2. NewIrreducible check
NewIrreducible(c) fails if candidate can be represented as:
  existing atom exact
  parameter update of existing atom
  scope specialization with representable residual constraints
  composition of existing atoms with coupling proof
  synonym/alias/alignment already in L2/L6
  deprecated atom reactivation without reference repair

If non-new, route back to normal grounding or reference repair.
Это предотвращает dictionary pollution: многие “новые” LLM proposals являются paraphrases, bundles or underspecified variants, а не new levers.

## F.3. World-bindable-or-acquirable
WorldBindable означает, что target variable существует как WMR object with type, measurement, scope, causal_role, intervention_status and provenance. WorldAcquirable означает, что есть допустимый acquisition bundle, который может создать или подтвердить такой object.
WorldAcquirable(c) iff exists U subset AcquisitionActions_t:
  cost(U) <= Budget_t
  SafetyGate(U) = PASS
  DataTrustPre(U) = PASS
  P_lower(WorldBindable after U) > 0
  LCB_VOI(U;c) > 0 or U is necessary for high-stakes ambiguity
Acquisition arm
Что закрывает
Не закрывает
world-slot acquisition
existence/type/scope of target variable
value or policy effectiveness
measurement acquisition
measurement process, proxy-vs-true distinction
causal mechanism alone
mechanism acquisition
operator -> target -> mediator/outcome evidence
legal admissibility
implementation acquisition
actor/enforcement/operational capacity
estimand identification
legal/normative acquisition
threshold, jurisdiction, protected groups, permissibility
world slot reality
lex/knob acquisition
L3/L6 mapping and knob existence
non-lexical causal evidence
expert elicitation
intent clarification or bounded expert review
official facts unless authority qualified
adversarial verification
proxy/fake-grounding/challenge tests
positive world proof by itself


## F.4. Reject-as-hallucination standards
Reject должен быть доказательным. Нельзя reject’ить proposal просто потому, что current reference не знает slot или mechanism. Hard rejection требует proof that all surviving completions hard-fail or are non-acquirable.
No controllable/intervenable world variable and no acquisition path.
Proposal is outcome wish, not intervention kernel.
Operator-target type impossible across all reference completions.
Mechanism contradicts all admissible world completions.
Required evidence source fails DataTrust and no alternative source exists.
Legal/normative hard violation that cannot be encoded as a constraint.
Proposal manipulates measurement/proxy while claiming true-world intervention.

## F.5. Stress outcomes
Class
Expected RT3 result
Failure mode being tested
real-novel, WMR/evidence present
admit-as-new-lever
free-grow recall
real-novel, missing measurement
acquire-then-decide
avoid false reject
real-novel, contested L2 alignment
acquire/reference repair
avoid unsafe admit
hallucinated outcome wish
reject
no do-semantics
proxy manipulation
reject/quarantine
measurement gaming
wrong legal threshold domain
reject or acquire legal proof
L3 false analog
duplicate paraphrase
non-new -> normal grounding
dictionary pollution
bundle of existing atoms
compositional route
free-grow over-fragmentation



# Приложение G. Детализированная спецификация RT4: solver encoding and cross-modal checks
RT4 должен быть реализован как constrained structured inference. Ниже — практический encoding, который можно перенести в MaxSMT, ILP или CP-SAT.

## G.1. Variables and domains
Discrete:
  z_operator[o] in {0,1}
  z_target[t] in {0,1}
  z_law[l] in {0,1}
  z_knob[k] in {0,1}
  z_method[m] in {0,1}
  z_scope[s] in {0,1}

Numeric:
  param_amount in Real
  param_rate in [0,1]
  param_duration in Time

Exactly-one or cardinality:
  sum_o z_operator[o] = 1
  1 <= sum_t z_target[t] <= K_target
  sum_m z_method[m] <= 1 unless estimand requires method expression

## G.2. Pair and tuple constraints
If not CompatOpTarget[o,t]:
  z_operator[o] + z_target[t] <= 1

If not LexApplicable[l,o,t,scope]:
  z_law[l] + z_operator[o] + z_target[t] + z_scope[scope] <= 3

If not KnobWritesTarget[k,t]:
  z_knob[k] + z_target[t] <= 1

If KnobOperator[k] != o:
  z_knob[k] + z_operator[o] <= 1

If MethodTreatment[m] != do_AST(o,t,params,scope):
  z_method[m] + z_operator[o] + z_target[t] <= 2

If threshold law says param_rate >= theta:
  param_rate >= theta - M*(1 - z_law[l])

## G.3. Unsat core examples
Case
Greedy would choose
JTCG unsat core
household threshold + corporate tax credit
valid tax credit, valid 200% FPL threshold
LexApplicable(law_household_income, corporate_tax_credit, firm_RnD)=false
rent cap using wage enforcement knob
valid cap, valid 5%, valid enforcement knob
KnobWritesTarget(wage_knob, wage_enforcement) != rent_growth
do target differs from NL target
valid NL target, valid do AST
do.target != candidate target
method estimates different treatment
valid ATE method, valid audit do
method.treatment != do(audit_probability)
unit mismatch
valid numeric 5, valid target
param.unit percent_rate incompatible with monetary_amount and no conversion



# Приложение H. Детализированная спецификация RT5: attack taxonomy and adversarial_validate
RT5 должен быть проверен на атакующем наборе, где каждое изменение phrasing не изменяет causal mechanism. Если confidence всё равно растёт, система surface-dependent and vulnerable.

## H.1. Attack transformations
Attack
Transformation
Defense expectation
high-value slot injection
add “employment”, “equity”, “poverty reduction”
surface retrieval may expand; evidence unchanged -> no confidence lift
legalistic camouflage
insert statute-like vocabulary or threshold names
L3 applicability check required
synonym flooding
add many aliases from L2 variable_alignments
confirmed/contested edge status governs evidence
nearest-neighbour hijack
include target surface markers while causal target remains different
critical target contradiction veto
confidence bait
phrases “clearly”, “by definition”, “directly”
ignored unless evidence witness produced
fake do notation
write do(X=x) with wrong target or scope
do-AST equality and NL entailment conflict
proxy/outcome conflation
describe proxy improvement as true outcome
measurement/outcome obligation blocks bind
omitted coupling
hide dependency edge in long phrase
compositional/coupling validator catches shadow/quarantine


## H.2. adversarial_validate routine
adversarial_validate(x,a):
  generate target/sign/scope/estimand/proxy/knob swaps around a
  generate phrasing-only paraphrases preserving candidate mechanism
  test C_bind invariance under phrasing-only transformations
  test confidence drop under mechanism-changing transformations
  inspect omitted coupling and cross-modal mismatches
  produce AdversarialGroundingReport:
    proxy_gap_score
    attack_successes
    invariance_violations
    mechanism_sensitivity
    recommended route: bind_allowed | quarantine | reject | acquire
Важно различать phrasing-only и evidence-changing transformations. Если новая формулировка приносит ссылку на реальный закон, knob id или WMR slot, это не просто phrase; такой evidence должен быть проверен обычным RT1/RT4/RT2/RT3 path and visible in certificate.


# Приложение I. Детализированная спецификация RT6: benchmark recipes and scoring
RT6 — это не “собрать датасет NL->ID”. Это runnable evaluation protocol, который производит streams, hidden oracles, contested labels, system traces and scoreboards.

## I.1. False-analog generator recipe
For each registered atom a:
  1. Take canonical description and L6 paraphrases.
  2. Generate positive exact/specialization/generalization paraphrases.
  3. Generate hard negatives by minimal critical-axis swap:
       target sibling, operator, sign, do_value/unit, scope/population,
       estimand, outcome/proxy, legal/knob, method/treatment.
  4. Keep only hard negatives where embedding rank(a|x) <= k
       or similarity >= median positive similarity.
  5. Add adversarial paraphrases preserving wrong causal relation.
  6. Hidden label includes fatal axis and expected safe output.

## I.2. Novel generator recipe
Real-novel:
  hide real L6 knobs / L3 mappings / WMR slots from visible reference
  keep enough hidden evidence for evaluator
  expected: pre-registration novel/acquire/abstain; post-registration bind

Hallucinated-novel:
  mutate real atoms by impossible target, proxy manipulation, wrong legal threshold,
  absent implementation actor, contradiction with causal graph
  expected: reject/quarantine, not admit

Real-needs-acquisition:
  hide decisive proof artifact: WMR slot, measurement, legal applicability,
  implementation evidence, DataTrust, L2 alignment
  expected: acquire-then-decide

## I.3. Scoring with intervals
For contested labels, RT6 should not force a point truth. It reports lower/upper intervals. For example, a bind in may+ can be counted as correct in permissive score but not strict score; a bind in must- is wrong in all scores; unknown stays unresolved unless required obligations closed.
StrictCorrectBind_i = 1 if predicted binding in must_plus and obligations closed
PermissiveCorrectBind_i = 1 if predicted binding in must_plus union may_plus
WrongBind_i = 1 if predicted binding in must_minus or violates required obligations

FBR^- assumes may_plus binds are correct.
FBR^+ assumes may_plus/unknown unsafe unless resolved.
Publish both plus an anytime-valid UCB where possible.

## I.4. Benchmark-level firewall
Public examples are not enough; maintain private adversarial stream and rotate templates.
Evaluate trace, not only final label: raw, parsed, shadow, grounded, blocked, quarantine, certificate.
Penalize unearned bind more than abstain; report good vs bad abstention separately.
Audit accepted, rejected and abstained examples to avoid selective feedback bias.
After reference growth, retroactively check whether old confident binds were false-neighbour binds.
Require reproducible replay hashes and versioned reference snapshots for every run.


# Приложение J. Детализированная спецификация RT7: action models and examples
RT7 завершает pipeline тем, что ambiguity becomes actionable. Вместо всегда-abstain или всегда-ask система выбирает action by expected value of information under safety constraints.

## J.1. Observation models
ActionObservationModel:
  action_type: cheap_verify | elicit_human | acquire_data | adversarial_validate
  blocker_class
  reference_version
  possible_observations:
    verified | contradicted | unknown | source_missing | tool_failure | human_disagreement
  likelihood_model:
    beta_binomial | multinomial_dirichlet | learned_calibrator | conservative_interval
  calibration_window
  reliability_bounds
  shift_flags
Для cheap_verify likelihood строится по GY-K/reference verification logs. Для elicit_human нужно разделить intent clarification and factual/legal authority. Для acquire_data оцениваются closure probability, latency and failure modes. Для adversarial_validate оцениваются capture rate and false alarm cost.

## J.2. Worked micro-cases
Case
Initial blocker
AG-VOI action and expected terminal
existing exact but ambiguous alias
L2 alignment contested but cheap evidence exists
cheap_verify -> bind if confirmed; abstain/acquire if contradicted
proposal says “support families”
operator/target underspecified intent
elicit_human -> parse refined; then CAAB
new smart-meter bonus
WMR/measurement missing, plausible implementation
acquire_data -> RT3 admit or reject based on DataTrust
high-value legalistic phrase near false atom
proxy-gap high
adversarial_validate -> quarantine/reject or require evidence
two safe atoms possible
uniqueness blocker
elicit/acquire discriminating scope; no bind until singleton
low downstream value and high acquisition cost
resolvable but low VOI
abstain/quarantine with remaining action recorded


## J.3. Terminal states
grounded_admissible: bind/admit passed all relevant gates.
grounded_partial_admissible: evidence supports but missing non-critical promotion obligations; stay shadow.
acquisition_required: a specific high-VOI acquisition remains.
human_decision_required: intent/authority boundary requires human.
grounded_abstention: safe to stop with no action of positive LCB VOI.
budget_exhausted: action valuable but infeasible under current budget.
spec_gap: needed obligation/validator type not implemented.
tool_failure: acquisition/validator failed; cannot coerce into bind/reject.

# Заключительное резюме
Сводный документ превращает семь самостоятельных исследований в единую систему: typed relation calculus, joint cross-modal solver, certificate-first binder, open-world free-grow admission, adversarial phrasing defense, active VOI controller and growth-aware benchmark. Центральная дисциплина не меняется на протяжении всего pipeline: candidate-until-grounded, abstain/acquire/quarantine better than wrong bind, novelty requires proof or acquisition, and every terminal decision must be replayable as a certificate.
Практический результат — спецификация, которую можно реализовать поэтапно: сначала shadow certificates and stress benchmarks, затем conservative bind gate, затем free-grow admission and active acquisition. Такая последовательность даёт полезный рост lever-пространства без загрязнения hallucinations и без confident-wrong false analog binds.
Конец документа.
