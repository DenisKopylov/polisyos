# UQS-01 — Согласованные summary/decomposition и доказуемые информационные единицы

**Редакция: PROPOSED v2 — адресные изменения FN-UQS-STDLIB. Содержательное review изменений выполнено; принятие проектом и реализация остаются отдельными шагами. Все product tests NOT_RUN.**

**LANE-10 · B199, B200, B201, B202 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Сохранить уже вычисленный закон и корректно агрегировать доступную информацию, не повышая уверенность по числу копий.

**Тип:** C112-R01/R02 fix; C112-G01 capability + native qualification.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/UQS-01.md), [исходные карточки](../05_Основания/Аудит/05_Источники/UQS-01_исходные_строки.txt), [трассировка](../04_Трассировка/UQS-01.json).

## 2. Уже работает — сохранить

- Exact selected-view dedup; same bytes/different profiles не тождественны. Caller labels не доказывают independence.
- Mean и equal-tail interval независимые functional; exact draws/weights/context и fresh recomputation сохраняются.
- Typed limited consumer и declared joint identity без authority; не перезапускать sampler ради имеющихся draws.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| B199 | fix | REQ-UQS-01-02, REQ-UQS-01-03 | Dedup repaired; finite mean boundary требует ремонта. |
| B200 | capability | REQ-UQS-01-03, REQ-UQS-01-05 | Запрет ложной precision есть; admissible independent fusion ещё не доказана. |
| B201 | fix | REQ-UQS-01-01, REQ-UQS-01-04 | Limited summary есть; secondary semantics должны совпасть. |
| B202 | qualify | REQ-UQS-01-01, REQ-UQS-01-04, REQ-UQS-01-05 | Carriers сохранены; source-bound joint/native consumer проверить. |
| C112-R01 | fix | REQ-UQS-01-01 | Gaussian helper defaults повышают secondary eligibility. |
| C112-R02 | fix | REQ-UQS-01-02 | sum overflow затем clamp смещает point. |
| C112-G01 | capability | REQ-UQS-01-03, REQ-UQS-01-04, REQ-UQS-01-05 | Раздельно native existing routes и недостающая independent fusion; не свести к tests. |

## 4. Нормативные требования результата

**REQ-UQS-01-01.** Secondary total/epistemic/aleatoric decomposition caller-only summary должна сохранять non-gating происхождение и approximation limitations primary result.

**REQ-UQS-01-02.** Среднее конечных points в _widest должно сохранять арифметический смысл без intermediate overflow, скрываемого clamp. Предпочтительная реализация — тонкая finite-validated обёртка над квалифицированной CPython3.14 statistics.mean у общего FED-01 owner. Самописный exact accumulator не обязателен и требует отдельного correctness/performance обоснования; scientific information-unit pooling не меняется.

**REQ-UQS-01-03.** Повтор selected view не меняет level/type/effective information; precision fusion разрешается лишь для установленного общего estimand и независимых information units либо проверенной dependency модели.

**REQ-UQS-01-04.** Summary должна сохранять исходные mean/equal-tail/draw corpus и joint row identity, включая mean вне interval; fresh consumer отвергает несогласованный сохранённый summary без уничтожения допустимого limited result.

**REQ-UQS-01-05.** Положительный source-bound путь aggregation/posterior propagation должен иметь actual producer→existing ref/profile→fresh consumer; отсутствие owner остаётся конкретным capability gap, не закрывается conservative hull.

## 5. Конкретное техническое решение — рекомендуемый способ

- Расширить existing UncertaintyDecomposition.from_gaussian_components/gaussian_uncertainty_envelope explicit semantics/gate/provenance аргументами; caller-only summary передаёт ограничения каждой secondary projection. Не ослаблять global envelope defaults вслепую: перечислить call sites, сохранить их established semantics.
- В _widest использовать общий finite-binary64 mean contract, согласованный с FED. Предпочтительный минимальный путь — CPython3.14 statistics.mean после прежней finite/empty validation; midpoint у общего helper — statistics.mean((a,b)), не statistics.median и не fmean/fsum с опасной промежуточной суммой. CPython3.14 exact-ratio sum делится на n до final conversion; квалифицировать именно целевую версию, не объявлять host3.12 проверку native PASS. Согласованный owner: FED-01 единолично создаёт предлагаемый НОВЫЙ src/polisyos/common/numeric_reductions.py с API finite_binary64_mean/finite_binary64_midpoint; UQS-01 только потребитель mean. Эти файл/API пока не существуют. Не импортировать Fabric upward; LK04 finite validation остаётся у прежнего owner. Собственный integer/rational accumulator допустим только при документированном correctness/performance основании, не как обязательное дублирование stdlib. Измерить actual bounded group cost без вымышленного SLO. Hull semantics/dedup/non-gating и научная независимость information units не меняются. Основание: https://raw.githubusercontent.com/python/cpython/v3.14.0/Lib/statistics.py (mean/_sum; проверено2026-11-01).
- Для G01 ограниченно проследить aggregate persisted views и selected method-evidence route: какие existing refs подтверждают estimand/data units/prior inclusion. Если достаточный producer есть — передать verified dependency context в existing precision/Bayesian formula; иначе описать missing typed predicate/producer и bounded implementation proposal. Не добавлять caller bool independent и не новый universal registry.

**Существующие code/test owners:**
- [`src/polisyos/foundry/uncertainty/aggregator.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/aggregator.py).
- [`src/polisyos/foundry/uncertainty/protocol.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/protocol.py).
- [`src/polisyos/foundry/calibration/uncertainty_adapter.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py).
- [`tests/unit/remediation/test_uqs_01.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_uqs_01.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-UQS-01-01 → REQ-UQS-01-01

**Уровень:** actual summary/decomposition. **Ожидается:** positive + negative + boundary.

**Setup:** Draws [-1,0,1], caller-only, optional aleatoric std .2.

**Действие:** Вызвать summarize и прочитать все три secondary envelopes.

**Oracle:** Все non-gating, typed approximation/provenance сохранены; numeric decomposition остаётся полезна. Total variance=epistemic variance+aleatoric variance, rtol=1e-6 atol=1e-9; credible label не добавляет authority.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQS-01-02 → REQ-UQS-01-02

**Уровень:** stable arithmetic. **Ожидается:** positive + negative + boundary.

**Setup:** Две точки +1e308, каждая с bounds [9e307,1.1e308]; cancellation: +1e308 с теми же positive bounds и −1e308 с bounds [−1.1e308,−9e307]; ordinary [1,3] с per-envelope bounds [0,2] и [2,4]. Каждый point законно внутри собственного interval. Дополнительно cancellation [1e308,−1e308,3*math.ulp(0.0)], каждому point задать законные finite bounds вокруг него; для tiny point допустим degenerate interval [point,point].

**Действие:** Actual _widest через aggregate и общий FED helper на CPython3.14; отдельно собранный exact Fraction.from_float sum/n oracle и Decimal.from_float precision1200 cross-check для фактических binary64 points, с одним final float conversion. Fraction arithmetic backend совпадает с частью statistics.mean, поэтому Decimal cross-check сохраняется как дополнительная независимая арифметическая проверка. Перестановка и повторная конкатенация полного multiset не меняют arithmetic mean; не усреднять округлённые means неравных subgroup и не трактовать повтор data как новую independent information unit. Измерить время/peak memory bounded group sizes, выбранных заранее по actual caller census, отдельно от correctness.

**Oracle:** Means 1e308/0/2; subnormal cancellation даёт точно math.ulp(0.0), не0. Oracle — exact Fraction.from_float sum/n, single float conversion; независимый Decimal precision1200 cross-check. Для exact binary64 fixture сравнивать float equality, не tolerance, скрывающий subnormal loss. Gate remains false при unknown dependency; clamp не маскирует numerical error.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQS-01-03 → REQ-UQS-01-03, REQ-UQS-01-05

**Уровень:** selected information units. **Ожидается:** positive + negative + boundary.

**Setup:** Четыре exact selected refs одного STD1; four independently generated Gaussian estimates с source-bound disjoint units и общим estimand, если existing owner достаточен.

**Действие:** Dedup по exact view; затем accepted fusion route; tamper shared prior/data/profile.

**Oracle:** Copies STD1 и level .8; legitimate four independent unit-variance estimates STD.5 (atol=1e-12) при declared Gaussian assumptions. Shared data/prior не считаются новыми units. Если adequate owner отсутствует — gap остаётся, реализованный путь не заявлен.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQS-01-04 → REQ-UQS-01-04

**Уровень:** summary→fresh limited consumer. **Ожидается:** positive + negative + boundary.

**Setup:** 99 zeros+100; two paired arrays with same marginals and reversed pairing.

**Действие:** Persist/read candidate, mutate mean1→2; запрос supported functional.

**Oracle:** Mean1, equal-tail[0,0], 100 draws preserved; altered pairing отличим; stale mean rejected; limited consumer выполняет 0 evaluator calls и не изобретает joint authority.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQS-01-05 → REQ-UQS-01-03, REQ-UQS-01-04, REQ-UQS-01-05

**Уровень:** E02-I10-B native CAS/method evidence. **Ожидается:** positive + negative + boundary.

**Setup:** Existing selected posterior/method-evidence route в uncertainty_adapter; actual tmp store и supported profiles.

**Действие:** Produce→persist→fresh resolve→propagate_posterior_summary; wrong profile/source negative.

**Oracle:** Exact corpus/selected profile reaches actual consumer; wrong binding fails адресно; caller-only остаётся limited. Native PASS не MCMC mixing/ESS/coverage proof.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I10-B** из [канонического lane integration-контракта](../03_Интеграция/LANE-10.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: UQP-02, CAL-06. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

CAL-06 общий adapter write mutex; UQP-02 владеет carrier sampling. Один existing lane fixture вместо отдельного большого posterior run.

## 8. Совместимость и восстановление

Новые secondary fields additive; исторические summary не ретроактивная evidence. Legacy positional draws читаются без joint promotion. При rollback сохранять conservative hull и exact corpus.

## 9. Free-grow и design decisions

- [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md#d25-epistemic-regime-architecture) и [синтез §4](../05_Основания/Исследование/design_direction.md): uncertainty/conditional outputs полезны без незаслуженной authority; новый совместимый law использует общий механизм, не доменную ветку.

## 10. Решения, которые нельзя подменить догадкой

- DEC-UQS-01-01: finite producer/ref census для independent units и prior reuse. Выход: accepted predicate map+minimal positive route либо точный missing contract с планом; независимость не выводится из разных UUID/bytes.

## 11. Что предъявить и что не является готовностью

Два bounded regressions плюс useful positive fusion capability отдельно от её отсутствия. Native storage/profile и scientific posterior quality — разные claims.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0320` → REQ-UQS-01-01; Gaussian helper defaults повышают secondary eligibility.
- `remaining:0321` → REQ-UQS-01-02; sum overflow затем clamp смещает point.
- `remaining:0322` → REQ-UQS-01-03, REQ-UQS-01-04, REQ-UQS-01-05; Раздельно native existing routes и недостающая independent fusion; не свести к tests.
- `preserve:0512` → REQ-UQS-01-03; Exact selected-view dedup — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0513` → REQ-UQS-01-03, REQ-UQS-01-05; No caller-label independence — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0514` → REQ-UQS-01-04; Separate mean/interval functional — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0515` → REQ-UQS-01-04, REQ-UQS-01-05; Exact draw carrier/context — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0516` → REQ-UQS-01-04; Fresh candidate recomputation — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0517` → REQ-UQS-01-04, REQ-UQS-01-05; Typed limited consumer — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0518` → REQ-UQS-01-03, REQ-UQS-01-04; No invented joint authority — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
