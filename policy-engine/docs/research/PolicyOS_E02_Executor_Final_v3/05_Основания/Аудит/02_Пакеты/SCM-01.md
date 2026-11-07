# SCM-01 — наблюдаемые корни и выполняемый polynomial payload
## C57 · 1 ноября 2026 года

**Порядок:** 57/127, LANE-05. **Исходные ID:** B221, B222. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежий аудит после внешнего сохранения C56; исходники не менялись.

## Решение

**В проверенном профиле исходные ошибки не воспроизведены:** наблюдаемый закон корней проходит от native_hybrid fit через actual SCM DTO/JSON до query; declared polynomial действительно используется в query, twin и fully observed residual. Полезная partial SCM не запрещена целиком, отсутствующий необходимый корень не становится молчаливым N(0,1).

**9 bounded MATCH; 5 unchanged test bodies /5 cases PASS изолированно. Подтверждён C57-R01:** outcome-only twin отказывает из-за disconnected missing root, закон которого не влияет на ответ. MATCH включает воспроизведение этого отказа и не означает product PASS. Это не native acceptance: selected DoWhy worker, CAS/fresh reader, registry/dispatcher и Scientist chain не исполнены. Whole-graph twin сохраняет более широкую потребность в корнях, чем active GCM query. Polynomial carrier не означает automatic nonlinear fitting или общую nonlinear posterior-abduction.

## 1. Матрица исходных требований

| ID | Исходная ошибка | Свежая проверка | Остаток |
|---|---|---|---|
| B221 | Fit теряет observed roots; query выдумывает Normal и нарушает joint root law | P01–P03: actual fit/DTO/query, поддержка исходных rows и совместных пар; malformed carriers отвергнуты; missing required root default refusal/явный opt-in | G01 native chain; R01 inactive-root availability |
| B222 | Poly payload исполняется как linear surrogate с полиномиальным малым noise | P01/P04–P06: 4 вместо1.36, linear control7, residual0.25, twin ITE3; malformed payload refused | G01 native chain; G03 ограниченный family/abduction profile |

Полная карточка — строки6872–6964. Утраченный прежний проход не используется для аттестации; source readsets свежих C48–C56 переиспользованы только на том же SHA с явным указанием.

## 2. B221: реальный carrier и joint row, не warning вместо закона

Native_hybrid теперь обрабатывает observed root: EMPIRICAL сохраняет `observed_samples`, source=`SCMFitData.data`, alignment=`column_row_order`, joint group. Actual SCM validator требует конечный непустой список, EMPIRICAL family и единый row count/source/alignment/group у всех carriers. Non-root coverage по-прежнему обязательна, missing roots допустимы как partial model. [S01:665–710](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py#L665-L710) [S04:202–302](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/structural_causal_model.py#L202-L302)

**P02:** actual input T=[0,0,1,1,2,2], Z=[99,101,99,102,99,100], Y=3T+2Z; real native_hybrid pure_step → real StructuralCausalModelSpec → JSON → real SCMQueryData → exact GCMQuery.pure_step. При do(T=1),1024 draws,seed7 mean=**203.138671875**, finite target=203; все outcomes принадлежат support{201,203,205,207}, а не около3. Fit method=`native_hybrid`, provenance=None, SCM schema1.2: результат не переименован в DoWhy fit.

**P03:** natural/no-override draw сохраняет все шесть разрешённых (T,Z) пар и не создаёт запрещённые комбинации. `_joint_root_sample_index` выбирает общий row, а root sampler использует actual sample из carrier. **P01** включает original tests с mismatched carrier length/family refusal и finite Hoeffding bound для mean. [S02:231–258](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L231-L258) [S02:438–582](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L438-L582)

Для отсутствующего необходимого Z default query отказывает; opt-in `allow_declared_root_hypothesis=True` явно даёт limited hypothesis/warning и non-gating envelope. Это исследовательский fallback, не восстановленный fitted law. Root, полностью заменённый atomic do, не требует natural mechanism. Такой отказ сохранять; не заменять его молчаливой Normal и не вводить blanket запрет partial SCM. [S02:1238–1314](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L1238-L1314) [S02:1739–1757](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L1739-L1757)

## 3. B222: producer→stored payload→shared predictor

`_fit_additive_noise_poly` хранит и linear baseline, и отдельные polynomial coefficients/noise. Формат — powers каждого parent без cross terms. `_mechanism_predict` выбирает declared polynomial, проверяет degree/полноту/finite coefficients и отказывает malformed declared payload, а не подставляет linear. [S01:89–166](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py#L89-L166) [S02:172–230](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L172-L230)

**P04:** real retained fitter на101 points x∈[-2,2],y=x² выдаёт noise≈4.90e−16. Его payload включён в actual manual SCM, JSON roundtrip и actual query при do(X=2) дают **3.999999999999999**. Linear часть того же payload даёт **1.3599999999999999** — различающий контроль действительно отделяет repaired branch от исходной ошибки. Это explicit helper/manual admission, **не** automatic selected family fitting.

**P01:** unchanged regression дополнительно даёт LINEAR y=1+3x →7 и отказывает incomplete polynomial/fractional degree2.5. **P05:** factual X=1,Y=1.25 восстанавливает U≈0.25 через общий polynomial predictor; twin apply при X=2 возвращает≈4.25. Ненаблюдаемые parents/общая nonlinear inversion здесь не проверены. [S02:628–741](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L628-L741) [S03:134–197](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/twin_network_query.py#L134-L197)

**P06:** actual twin with empty factual_condition применяет одни и те же noises к arms X=1 иX=2: ITE≈3, std≈4.92e−16. Actual TwinNetworkResult проходит JSON roundtrip. Фиксированная outcome/ITE distribution не называется estimator sampling CI: envelope bridge задаёт confidence_level=None, heuristic range,gate_eligible=False, estimator_interval отсутствует. Constructor envelope в harness — fixture, сам bridge/DTO — source code. [S03:198–318](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/twin_network_query.py#L198-L318) [S05:419–452](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_queries.py#L419-L452)

## 4. C57-R01: ненужный корень блокирует outcome-only twin

**Средняя серьёзность, высокая уверенность в ограниченном воспроизведении.** P07: graph X→Y плюс disconnected Z, Y=X², механизмов X/Z нет. Actual GCMQuery.pure_step при do(X=2) исполняет active closure и даёт 4; actual TwinNetworkQuery.pure_step для arms X=1/2 отказывает из-за отсутствующего Z. X законно заменён atomic do, Z не предок outcome и не factual evidence.

**P08 — различающий negative/removal control:** добавлены два несовместимых закона ненужного корня, Z≡0 и Z≡10⁹. При одном seed обе версии допускаются и дают одинаковый **полный requested twin result**, включая distributions/metadata, кроме wall time; ITE≈3. Ни один из этих законов не нужен для ответа. Consumer возвращает outcome/ITE summary, не полный мир, поэтому требование Z в этом запросе — лишний отказ в доступности, а не необходимая научная защита.

Root guard в pure_step и `_twin_simulate_samples` работает на whole graph; существующий active-query owner уже применяет более точную surgery/ancestor closure. Минимальное направление — согласовать twin admission и traversal с таким планом, сохраняя обе interventions, factual ancestors и shared noise. Не включать вымышленную гипотезу ради irrelevant root и не ослаблять отказ для действительно нужного отсутствующего корня.

Это свежий исполняемый residual, не вывод из утраченного прохода и не downgrade лишь потому, что native dependencies недоступны. Граница доказательства: exact AST bodies и actual DTO в локальном finite request; native dispatcher/CAS и production распространённость не измерены. [S03:450–467](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/twin_network_query.py#L450-L467)

## 5. Native owner и scientific scope остаются отдельными

Default `HybridSCMFit` выбирает selected DoWhy GCM, explicit native_hybrid — другой research profile. Selected producer требует source-resolved declared static DAG, worker projection/source rows, complete exported mechanism reconciliation и actual training/provenance. C57 **не вызывал** worker и не подставлял успешный mock response. Native observed child route остаётся LINEAR OLS; наличие polynomial helper не доказывает автоматический nonlinear fit. [S01:292–540](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py#L292-L540) [S01:707–716](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py#L707-L716)

Полностью прочитан настоящий `RunCausalQueriesNode`: он загружает SCM через owner, проверяет source-bound spec, создаёт method job с SCM input binding, сверяет canonical whole payload/aliases/request, затем сохраняет typed result и строит envelope заново из него. Это содержательный consumer, но **source-only** C57; local JSON roundtrip не CAS custody. [S14:153–200](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_queries.py#L153-L200) [S14:252–342](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_queries.py#L252-L342) [S14:362–393](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_queries.py#L362-L393)

**C57-G01:** native tests существуют, но pytest/DoWhy отсутствуют, parent interpreter3.12 вместо3.14; ordinary import падает на Python3.14 syntax в uncertainty.py:287. Один native integration test ожидает SCM schema1.1, тогда как actual owner current1.2 и соседний selected-query fixture уже ожидает1.2. Нужна reconciliation и настоящий supported-runtime run; **не заявляется** executed native FAIL или сломанный persisted reader. Twin result1.1 — отдельная законная схема, не эта несогласованность. [S13:195–205](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py#L195-L205) [S12:100–110](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_gcm_query.py#L100-L110)

**C57-G03:** shared predictor и полного factual residual достаточно для названного polynomial regression, но не для произвольных nonlinear posterior, interactions, mechanism discovery, causal identification или переносимости реальных данных. Сохранять эти explicit limits, полезный partial fitting и LLM semantic proposer; отсутствие универсального deterministic inventor само по себе не дефект. Synthetic controls не empirical authority. Refit bootstrap и partial-evidence law будут отдельно рассмотрены по следующей очереди, здесь не закрыты.

## 6. Сохранить и проверить далее

- Сохранить observed/joint root carriers, строгий DTO и query-specific missing-root отказ/limited opt-in.
- Сохранить единый polynomial predictor, malformed-payload refusal, LINEAR control и shared-noise twin.
- Довести native selected source-bound fit/query/CAS/fresh reader/Scientist qualification; не переписать product ради отсутствующих зависимостей аудитора.
- Устранить лишний twin inactive-root отказ через существующий active plan и определить supported nonlinear family/abduction boundary; прежде расширять существующие owners, чем строить параллельный движок.

Пять unchanged bodies: SCM01 четыре и native-profile ownership один. Первый external diagnostic run имел syntax typo; исходный файл/лог сохранены, поправлен только probe вне checkout, финальный exit0. Repo clean; installs/исходных edits/сервисов нет.

[Диагностика](../04_Проверки/C57_SCM01/bounded_diagnostics.json) · [Команды](../04_Проверки/C57_SCM01/commands.json) · [Границы](../04_Проверки/C57_SCM01/native_verification.json) · [Источники](../05_Источники/C57_источники.json) · [Остатки](../01_Реестры/C57_остатки.json).

**57/127 пакетов рассмотрены ограниченно; 134 уникальных B/LA частично оценены. Следующий — SCM-02. Полного закрытия нет.**
