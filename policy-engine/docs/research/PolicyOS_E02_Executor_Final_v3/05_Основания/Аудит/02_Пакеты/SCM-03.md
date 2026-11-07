# SCM-03 — active query-plan и сохранение stochastic law
## C59 · 1 ноября 2026 года

**Порядок:** 59/127, LANE-05. **Исходные ID:** B224, B225. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежий audit-only проход после внешнего сохранения C58.

## Решение

Perfect intervention теперь заменяет natural mechanism до его вычисления; active plan исключает irrelevant nodes и сохраняет factual ancestors. Поддержанный stochastic law разбирается один раз, malformed law не становится atomic fallback, хвостовой truncnorm действительно генерирует conditional samples.

**10 bounded MATCH, 10 unchanged test bodies /11 cases PASS изолированно.** Остаются **C59-R01:** manual SCM без graph disposition допускает raw-endpoint execution partial graph; **C59-R02:** joint Gaussian posterior replicas чувствительны к эквивалентной перестановке active siblings. Второй — low reproducibility residual, не доказательство biased marginal law. Native chain и scientific authority не закрыты.

## 1. Матрица исходных ID

| ID | Требование | Свежие различающие проверки | Остаток |
|---|---|---|---|
| B224 | Perfect do не вычисляет заменяемый механизм; active/factual closure, immutable graph, stable seeds | P01–P04: broken-natural tripwire,10/210 calls,20/220 values, surgery/shift/factual controls, existing reordered/mutant tests | R01 manual graph admission; R02 joint posterior replicas; G01/G02 |
| B225 | Исходный stochastic law без hidden atomic fallback/clipping; один parse, tail support | P01/P05/P06:2048 unique interior draws, quadrature oracle, malformed/scale/finite refusal, uniform reproducibility, clipping/degenerate separation | G01 native persistence/runtime; G02 scope/authority |

Полная карточка7060–7155 прочитана. Этот пакет **не** аудит estimator refit bootstrap; его отсутствие в execution не скрывается обещанием следующего пакета.

## 2. Active plan: реальная экономия работы без изменения запроса

`_intervention_replaces_natural` различает ATOMIC/STOCHASTIC replacement и SHIFTED/TRUNCATED natural-value operations. Active closure для ordinary perfect action останавливается на treatment; counterfactual сохраняет factual ancestors. Actual sampling подставляет replacement до natural sampler. [S01:85–146](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L85-L146) [S01:1238–1314](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L1238-L1314) [S01:1429–1486](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L1429-L1486)

**P01:** unchanged regression намеренно ломает natural X sampler, но do(X=2),Y=1+3X всё равно даёт7. Shift X=5,+2 остаётся7, не atomic2. **P02:** X,Y плюс20 irrelevant roots,10 draws: active path вызывает node sampler **10** раз и хранит **20** значений; full-trace — **210** вызовов и **220** значений. X natural не вызывается ни в одном режиме; Y samples одинаковы, исходный graph snapshot не меняется. Это exact counters, **не измеренное ускорение приложения**.

**P03:** U→X→Y, natural law U отсутствует. Perfect do(X=2) не требует U и даёт7; shift отказывает из-за действительно нужного корня. **P04:** counterfactual factual X=2 сохраняет U→X ancestors; actual posterior profile подтверждён. Поэтому pruning не реализован простым удалением всех родителей treatment независимо от типа запроса.

Per-node logical streams используют root entropy, namespace и label, а не текущую позицию в обходе. Existing tests проверяют irrelevant-root insertion, reorder active siblings и mutant, который принудительно заменяет streams одним shared RNG: mutant делает distinguishing witness красным. Это полезный negative control, а не наличие seed marker. [S01:277–318](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L277-L318) [S08:190–309](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_scm_03.py#L190-L309)

## 3. B225: исполняется выбранный закон, не удобная замена

Resolver проверяет имя/arity/finite arguments/positive scale. Sampling получает подготовленный law object, так что parsing не повторяется в каждой реплике. STOCHASTIC exception превращается в адресный ValueError, не в fallback_treatment_value=7. [S01:321–437](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L321-L437)

**P05:** actual query truncnorm(0,1,8,9),2048 draws,seed23 вызывает resolver **один раз**. Все значения строго внутри(8,9), все уникальны; min=8.00001258,max=8.92340327,mean=**8.11569886**. Независимый oracle интегрирует exp(−(x²−64)/2) на[8,9]: mean=**8.12118899**,variance≈0.01414854; finite six-standard-error criterion выполнен. Использован настоящий установленный SciPy truncnorm, не mock чисел.

**P06:** typo, пустой argument, zero/negative scale и NaN явно отказаны даже при fallback7. Отдельный TRUNCATED clipping естественного0 к[8,9] даёт8; объявленный degenerate truncnorm[8,8] тоже даёт8, но это два разных осознанных контракта, не замена tail law. Existing uniform test сохраняет support и exact seeded repeat. Original intervention остаётся typed STOCHASTIC в actual result DTO.

## 4. C59-R01 — manual partial graph обходит directed-profile admission

**Средняя серьёзность; высокая уверенность в bounded public-body route.** Actual StructuralCausalModelSpec требует source_graph/disposition для current selected/native fit; для `fit_method="manual"` они могут отсутствовать. Query helpers строят parents/topological order из raw src/dst, игнорируя endpoint marks. Они проверяют temporal lag и cycles, но не admitted directed profile. [S03:208–240](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/structural_causal_model.py#L208-L240) [S01:52–146](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L52-L146)

**P07:** actual DTO с PAG X o→Y, manual mechanisms X,Y, проходит query do(X=2) и возвращает7 без warning. Тот же source graph отказывается canonical projector как unresolved; actual selected fit early guard также требует declared static DAG. Поэтому residual относится **не** к selected fit, а к manual/no-disposition consumer boundary.

**P08:** обе записи X←Y — `(src=X,dst=Y,arrow,tail)` и `(src=Y,dst=X,tail,arrow)` — canonical projector переводит в один Y→X. При одинаковых механизмах Y=5,X=2Y и запросе do(Y=2)→X первая raw запись даёт **KeyError('Y')**, вторая — **4**. Это observable зависимость от storage spelling, не только отсутствие marker.

Минимальное направление: перед static active plan использовать существующий admitted graph/projection owner либо явный supported DAG requirement. Сохранить useful manual/legacy models, но не превращать unresolved marks в ориентированный causal success. Не добавлять ещё один parallel graph parser. **P09** сохраняет положительную защиту: manual temporal edge уже явно отказан, не молча трактуется статическим. [S04:340–390](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L340-L390) [S05:460–479](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py#L460-L479)

## 5. C59-R02 — stable node streams не полностью охватывают joint posterior

**Низкая серьёзность; высокая уверенность в replica mismatch, без вывода о marginal bias.** Ordinary interventional per-node streams устойчивы, но conditional Gaussian sampler использует один joint vector в координатах текущего topological order. Перестановка equivalent active siblings меняет матричную факторизацию/сопоставление draws. [S01:893–1015](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L893-L1015) [S01:1358–1435](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L1358-L1435)

**P10:** existing same-DAG reordered fixture, одинаковые mechanisms/query/seed31,512 draws. При factual R=1 и B=1,C=2 replicas совпадают. При factual Y=4 или B=1 — различаются; для B=1 max per-replica difference≈**21.9801**, means5.27668 vs5.58983. Оба результата сохраняют profile=`linear_gaussian_posterior`. Эти разные finite samples **не доказывают**, что один marginal law неверен; выявлена потеря обещанной logical-replica/common-randomness устойчивости при эквивалентном представлении графа.

Следует согласовать canonical posterior coordinate order/stream identity с existing logical stream owner и добавить counterfactual permutation witness рядом с interventional test. Нельзя «исправить» correlated posterior независимыми draws: shared-U/covariance остаются содержательным контрактом.

## 6. Producer/consumer и открытые границы

Actual request→plan/law→numeric result→typed DTO проверен изолированно. Source-only downstream query node загружает SCM, связывает job с input artifact, сверяет complete canonical method result/aliases/query и строит conservative envelope из typed result. Native reader/registry/dispatcher/Scientist execution не выполнены. [S10:153–200](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_queries.py#L153-L200) [S10:252–393](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_queries.py#L252-L393)

**C59-G01:** pytest отсутствует, public import под Python3.12 останавливается на Python3.14 syntax; no installs. Native selected fixture и active/tail tests прочитаны, не заменены synthetic fixture под видом настоящего worker. Требуются supported runtime и actual persisted-chain checks. Для заявлений о скорости/памяти приложения — отдельная representative workload, не переименование counters в benchmark.

**C59-G02:** finite normal/uniform/truncnorm profile и полезный proposal execution не доказывают empirical policy authority, arbitrary law support или estimator coverage. C57-R01 и C58-R01/R02 сохраняются; C59 их не переаттестует. **Refit bootstrap здесь UNRUN** и не считается закрытым ни этой карточкой, ни обещанием следующих работ. LLM semantic proposer совместим с таким профилем, но downstream должен исполнять именно заявленный law и graph semantics.

## 7. Сохранить и остаток

Сохранить perfect replacement, active/factual closure, immutable topology, per-node streams, strict stochastic refusal и real tail sampler. Исправлять manual graph admission и canonical joint-posterior replica mapping через existing owners. Не возвращать rejection-limit clipping, hidden atomic alternative или blanket запрет partial candidate work.

Первый bounded run exit0; все10 existing bodies/11 cases выполнены. Native attempts blocked, не product FAIL. Repo clean; source/test/config/dependency edits, services и installs отсутствуют.

[Диагностика](../04_Проверки/C59_SCM03/bounded_diagnostics.json) · [Команды](../04_Проверки/C59_SCM03/commands.json) · [Границы](../04_Проверки/C59_SCM03/native_verification.json) · [Источники](../05_Источники/C59_источники.json) · [Остатки](../01_Реестры/C59_остатки.json).

**59/127 пакетов рассмотрены ограниченно; 138 уникальных B/LA частично оценены. Следующий — FIT-01. Полного закрытия нет.**
