# DDM-02 — Полный subject binding и исполнимый путь к текущему monitoring основанию

**LANE-11 · LA-054, LA-055 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Сохранить полезные monitoring/readiness/incident projections и сделать их контекст воспроизводимым; закрыть узкий direct-builder дефект и отдельно довести отсутствующий production observation contract до проверяемого решения, не выдумывая полномочия.

**Тип:** C122-R01 fix; C122-G01 capability/owner decision; C122-G02 policy lifecycle + native/scientific qualification; LA-054/055 closure owner.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/DDM-02.md), [исходные карточки](../05_Основания/Аудит/05_Источники/DDM-02_исходные_строки.txt), [трассировка](../04_Трассировка/DDM-02.json).

## 2. Уже работает — сохранить

- LA-054: реальный validity checker, report digest, exact consumed source basis, effective time/expiry/triggers, fresh rebind; historical pass не текущий permit.
- LA-055/LK34: R4/R3 independent veto; R2 limited signoff после non-overridable checks; R1/R0 и failed certificate не разрешаются; score/state/actions полезны отдельно.
- LK01/LK14: DDM FP certification не predictive calibration/Foundry fit/N11 alpha accounting; не заменять DDM Runtime ledger.
- LK33: finite replay честно даёт проверяемый diagnostic/candidate, не production grant; не чинить отсутствующую authority выдачей synthetic token.
- LK35: channel anyOf и runtime cross-field/window guards сохраняются при DDM-01 schema moves.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| LA-054 | capability | REQ-DDM-02-01, REQ-DDM-02-02, REQ-DDM-02-03, REQ-DDM-02-06, REQ-DDM-02-07 | Основной report/time binding уже работает; closure включает direct nested identity и недостающий legitimate observation path, не один retry tests. |
| LA-055 | lifecycle | REQ-DDM-02-04, REQ-DDM-02-05, REQ-DDM-02-07 | Матрица уже repaired; закрепить effective policy serialization/current application, не менять право института. |
| C122-R01 | fix | REQ-DDM-02-01, REQ-DDM-02-02 | Earlier foreign model accepted в direct builder; monitor защиту сохранить. Production bypass не доказан. |
| C122-G01 | capability | REQ-DDM-02-02, REQ-DDM-02-03, REQ-DDM-02-07 | Exact admitted concrete source только finite replay. Нужен bounded owner investigation/typed integrate contract и проверка положительной способности либо точный remaining decision. |
| C122-G02 | lifecycle | REQ-DDM-02-04, REQ-DDM-02-05, REQ-DDM-02-06, REQ-DDM-02-07 | Policy_id в YAML не доходит decision; actual report provenance/native/statistical scope требуют отдельного результата. |

## 4. Нормативные требования результата

**REQ-DDM-02-01.** Direct builder и fresh rebind должны сверять model_id/model_version каждого consumed shift и другого nested model-bearing event с target/source application; foreign earlier event не может образовать applicability.is_bound=true, даже если последний event правильный.

**REQ-DDM-02-02.** Текущий gate должен по-прежнему опираться на resolved report, полный consumed basis, observed-window/currentness и non-overridable checks; persisted public payload без нового rebind не восстанавливает private authority.

**REQ-DDM-02-03.** Работа по production applicability должна предъявить именованный existing observation producer либо обоснованный отсутствующий contract, конечную карту source→selection/coverage→subject/window→freshness→consumer и исполнимый положительный путь допустимого профиля; finite_replay_only не снимается ради видимости успеха.

**REQ-DDM-02-04.** Eligibility/veto/limited R2 override должны сохранять одну определённую таблицу и фактический контекст policy; false R4/R3 veto, R1/R0 и failed certificate запрещены независимо от signoff, но допустимый conditional R2 не блокируется простым общим AND.

**REQ-DDM-02-05.** Новые решения должны сохранять идентичность эффективной typed ReadinessPolicy и её семантическую версию/профиль через producer, registry/rebind и gate decision; неизвестная/несовпадающая policy не подменяется default.

**REQ-DDM-02-06.** Квалификация FP report должна проходить actual calibrate_detector→audit→validity→monitor/registry на сохранённых inputs с отделением synthetic smoke от реального stationary evidence; срок, horizon и observation delay не взаимозаменяемы. Actual producer не повторно использует calibration observations как holdout при пустом holdout. Trusted observation IDs разрешаются в выбранный source artifact и observation/time coordinates; caller labels либо числовое неравенство arrays не доказывают независимость. Calibration method отражает исполненный raw-quantile либо связанный actual MBB preparation route; external bootstrap допустим с проверяемой lineage/index plan. Без достаточного source separation результат остаётся useful unqualified/research threshold, не empirical FP certificate.

**REQ-DDM-02-07.** Исторические snapshots без нового policy/source binding должны оставаться читаемыми как historical/not-established; отсутствие production owner ограничивает final permission, но сохраняет доступные shift/degradation/readiness/root-cause/incident данные.

## 5. Конкретное техническое решение — рекомендуемый способ

- В model_registry.py::_check_registry_applicability использовать readiness_event target model_id/version и сопоставить с source.model_id/version, calibration_audit и каждым shift_events[]; включить каждый data_quality_signal и degradation, не только last projection. Переиспользовать/вынести existing monitor::_validate_window_input_identities в нейтральный общий helper внутри DDM так, чтобы direct builder и monitor имели одну семантику; helper возвращает typed reasons, monitor может сохранить ValueError. Не создавать второй registry.
- Добавить subject reasons до создания authoritative applicability; оставить exact shift digests/duplicate detection и source equality. Изменение не должно разрешать finite replay: существующие concrete source admission и gate boundary сохраняются до принятого source contract.
- C122-G01 — отдельный capability step: проследить реальные callers DriftAndDegradationMonitor, configured source binding и существующих owners persisted monitoring events. Проверить кто может доказать выбор окна, полноту выбранного stream, checkpoint/identity и currentness. Выход finite inventory + выбранный adapter contract или точный missing predicate/owner. Если owner достаточен, расширить observation source admission конкретным independently resolved typed profile, не arbitrary duck-typed object и не mutable authority_scope строкой. Реализовать только недостающую связку existing source→checker/consumer; если нужного producer нет, предъявить обоснованное предложение общего producer, границу authority и требуемое решение. Это не автоматический этап «запустить tests».
- ReadinessPolicy уже типизирован в readiness_mapper.py, но registry rebind вызывает map_readiness без policy, RegistryGateDecision хранит только model/allow/reason/actions. Передать effective typed policy во все producer/rebind вызовы; связать canonical policy fields с semantic policy ID/profile. Лучше additive optional binding для legacy readers плюс mandatory current binding у нового issuer, чем parsing free-text YAML. Policy ID не доказывает полномочия; root action owner отдельно.
- Calibrate_detector реально существует в calibration/calibrate.py и вычисляет threshold/holdout/Wilson interval/expiry. Сначала native deterministic smoke и source provenance; затем только заявляемая область scientific validation. Не импортировать predictive calibration вместо FP, не требовать полный FDR proof ради сохранения bounded monitoring.
- Расширить существующие test_full_acceptance.py/test_observation_source_admission.py, не создавать параллельный «DDM gate framework». Прямой builder regression должен проверять intermediate applicability, поскольку нынешний public finite guard уже скрывает дефект от простого final-false assertion.

- **v2 / CS-004:** calibrate.py:118 объявляет moving_block_bootstrap_quantile по default, хотя helper:123–182 считает maxima quantile уже переданных streams; CLI:429–435 использует calibration снова при пустом holdout. Убрать alias fallback у producer, не требовать bootstrap обязательно внутри helper. Raw empirical quantile получает truthful method identity; external actual MBB preparation допустима при bound source/index provenance. Source identity — artifact+observation/time coordinates, не произвольная строка; unresolved lineage ограничивает qualification, но не запрещает research threshold/finite monitoring. TEST-07 exact arithmetic и production finite-source veto сохраняются.

**Существующие code/test owners:**
- [`src/polisyos/ddm/integration/model_registry.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/integration/model_registry.py).
- [`src/polisyos/ddm/integration/monitor.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/integration/monitor.py).
- [`src/polisyos/ddm/calibration/audit.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/calibration/audit.py).
- [`src/polisyos/ddm/calibration/observations.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/calibration/observations.py).
- [`src/polisyos/ddm/calibration/calibrate.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/calibration/calibrate.py).
- [`src/polisyos/ddm/readiness/readiness_mapper.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/readiness/readiness_mapper.py).
- [`src/polisyos/ddm/readiness/readiness_policy.yaml`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/readiness/readiness_policy.yaml).
- [`tests/unit/ddm/test_full_acceptance.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/ddm/test_full_acceptance.py).
- [`tests/unit/ddm/test_observation_source_admission.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/ddm/test_observation_source_admission.py).
- [`tests/unit/ddm/test_readiness_mapping.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/ddm/test_readiness_mapping.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-DDM-02-01 → REQ-DDM-02-01

**Уровень:** actual builder regression. **Ожидается:** positive + negative + boundary.

**Setup:** Legitimately issued finite-source checker evidence; targetA/v1, earlier shiftB/v1, last shiftA/v1; затем versions A/v2 и foreign DQ в consumed basis.

**Действие:** Пройти build_model_registry_record напрямую и rebind после сериализации.

**Oracle:** Applicability unbound с конкретной model/version reason и index/ID offending event; same-model finite positive bind остаётся. Замена all-event check на last-only воспроизводит C122-P03. Final finite denial сохраняется; это не exploit тест.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DDM-02-02 → REQ-DDM-02-01, REQ-DDM-02-02

**Уровень:** monitor + direct/rebind parity. **Ожидается:** positive + negative + boundary.

**Setup:** Один exact source snapshot и report/audit; одинаковые inputs direct builder/monitor; selected observed source bytes.

**Действие:** Tamper earlier event/metric budget/readiness projection; поменять bytes после issuance; удалить source.

**Oracle:** Оба routes не принимают foreign basis; rebind читает source снова; changed/unavailable bytes не устанавливают authority. Correct finite context сохраняет diagnostic outputs и declared finite scope.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DDM-02-03 → REQ-DDM-02-02, REQ-DDM-02-07

**Уровень:** native serialization/temporal. **Ожидается:** positive + negative + boundary.

**Setup:** Existing test_full_acceptance/test_observation_source_admission; report до/на/после expiry, matching/unrelated trigger, late event в declared finite profile.

**Действие:** Serialize public record, открыть fresh consumer без/с exact context, различить unavailable и observed empty.

**Oracle:** Private evidence не сериализуется; historical pass/bytes сохранён. Exact observed empty позволяет bounded computation, unavailable нет; late факт допускается только своим profile, horizon30d не становится TTL.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DDM-02-04 → REQ-DDM-02-03, REQ-DDM-02-07

**Уровень:** capability/contract validation, then selected native integration. **Ожидается:** positive + negative + boundary.

**Setup:** DEC-DDM-02-01 finite read-only inventory callers/storage/observation producers; real owner candidate и минимальный фактический input если существует.

**Действие:** Составить матрицу owner predicates и actual source bindings; подключить минимальный accepted adapter только при доказанной способности producer. Исполнить selected producer→checker→monitor→fresh registry; otherwise предъявить typed missing contract и costed path.

**Oracle:** Положительный результат доказывает конкретно объявленные selection/coverage/currentness, не мировую полноту. Caller bool/list/подпись не считаются source proof. Если owner не найден, G01 остаётся capability unresolved, finite outputs работают; документированный отказ не считается созданной production capability.

**Seams:** Synthetic transport возможен для shape test, но не для принимаемого production source predicate. Deployment/retrain/ticket не вызываются; человеческий signoff проверяется только у имеющего полномочие внешнего owner.

### TEST-DDM-02-05 → REQ-DDM-02-04

**Уровень:** native conditional policy table + public gate. **Ожидается:** positive + negative + boundary.

**Setup:** R0…R4, veto true/false, signoff false/true, certificate pass/fail на real DTO.

**Действие:** Повторить existing full_acceptance matrix; отдельно helper conditional и public final gate.

**Oracle:** R4/R3+veto false не допускаются; только R2 может расширяться с signoff после guards; R1/R0/failed certificate никогда. Finite source не проходит public gate даже при conditional true; не приписывать bool identity.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DDM-02-06 → REQ-DDM-02-05, REQ-DDM-02-07

**Уровень:** policy producer/serialization/rebind. **Ожидается:** positive + negative + boundary.

**Setup:** Actual ReadinessPolicy default и второй instance с другим threshold/TTL; legacy JSON без policy binding; unknown version payload.

**Действие:** Map/build/store/read/rebind/gate для каждого effective policy; mutation только version/digest; compare same inputs.

**Oracle:** Решение повторяется лишь при том же effective policy; mismatch/unknown выявлен с reason. Legacy читается без тихого назначения default как текущей; human YAML description не исполняется как DSL.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DDM-02-07 → REQ-DDM-02-06

**Уровень:** actual calibration native smoke + provenance. **Ожидается:** positive + negative + boundary.

**Setup:** Actual fixture tests/unit/ddm/test_stationary_replay.py:28–77: calibration_streams=[[0.10,0.12,0.11,0.13] for _ in range(100)], holdout_streams=[[0.05,0.07,0.08,0.09] for _ in range(100)]; по100 streams/windows длины4, НЕ400 независимых Bernoulli observations. StationarityRegime idSR-1-model-v1, model/v1, UTC reference2026-01-01→02-01, calibration02-01→03-01, holdout03-01→04-01, day_of_week, block_length2, invalidation model_version_change; FpTarget(horizon30d,alpha0.05,ert10000), seed0, validity now2026-04-10UTC. Явно synthetic fixed replay, не эмпирическая независимость/стационарность доказанная повторением.

**Действие:** Реальный calibrate_detector; независимо рассчитать per-stream maxima/nearest-rank quantile и Wilson interval, затем actual build_calibration_audit/check_calibration_validity; сохранить report и пройти monitor с тем же model/version/report basis. Негативный control меняет только detector/report binding либо model version, сохраняя численные поля.

**Oracle:** Все calibration maxima0.13, nearest-rank 95th из100 даёт threshold0.13; time_varying_thresholds=[0.10,0.12,0.11,0.13]. Holdout windows100, alerts0 (strict > threshold), empirical FP0, Wilson95% z=1.96: lower0, upper z²/(100+z²)≈0.0369948074760019≤0.05, pass=True; значения float64 atol=1e-12, counts exact. Actual audit/validity при указанном now действительны на том же report; foreign binding/version не получает permission, даже если числа те же. Input/digest/count bindings сохраняются при roundtrip; caller-supplied report/audit не заменяет production-owned source и сам не даёт registry promotion. Repeated synthetic streams не доказывают field FP/FDR theorem, 10000-window ERT или production readiness; эти claims требуют отдельного source/provenance и предметной статистической validation.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I11-B, E02-X04** из [канонического lane integration-контракта](../03_Интеграция/LANE-11.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: DDM-01. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

DDM-01 владеет contract extraction/aliases/manual schema; DDM-02 владеет applicability/policy semantics и closure LA-054/055. Согласовать DTO additions и full fresh-reader tests с DDM-01. Не смешивать этот native job с тяжёлой FP recalibration или общей backend suite.

## 8. Совместимость и восстановление

Public record старой версии остаётся readable и non-authoritative; не дописывать current timestamps/policy retroactively. Новая optional projection не восстанавливает private token из JSON. Forward revert совместим с сохранённой history; pending production source остаётся not-established. Не удалять finite replay/debug route при добавлении нового source.

## 9. Free-grow и design decisions

- [design_direction §2.1/2.4/§4](../05_Основания/Исследование/design_direction.md): candidate/diagnostic полезность сохраняется; отсутствие institutional owner ограничивает grant, не monitor computation.
- Stage0 K03/K06 и W5 K03–K05: whole subject identity и наблюдение не равно causal confirmation; typed source нужен для конкретного предиката, не новый глобальный gate.
- LK01/14/33/34/35 соблюдаются; новая общая source capability допустима, если доказан пробел, но фиктивное authority поле не является исправлением.

- [Stage-0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md#43-k06--fail-closed-binds-the-protected-action-not-the-computation): отсутствие authority ограничивает защищённое действие, не полезные candidate/diagnostic computations.

## 10. Решения, которые нельзя подменить догадкой

- DEC-DDM-02-01: source inventory должен ответить, существует ли producer с needed selection/coverage/currentness. Варианты: wire existing adequate owner; extend existing persisted event owner с явным predicate; отдельное предложение отсутствующей общей способности. Критерий выбора — независимо проверяемый source predicate, не форма payload. Без достаточного authority не открывать final grant; сохранить bounded outputs.
- DEC-DDM-02-02: определить supported policy compatibility profiles и legitimate freshness/label-delay source. Default сегодня известен, но unknown version не интерпретировать как default. Выход — маленькая typed version/binding mapping с legacy read semantics; не универсальный DSL и не вымышленный institutional signoff.

## 11. Что предъявить и что не является готовностью

R01 принят только если direct-builder negative действительно различает earlier foreign subject и same-model positive сохранён. G01 не закрывается таблицей R2 или финальным false; нужен созданный/подключённый адекватный producer→consumer либо явный незакрытый capability decision. G02 раздельно предъявляет policy binding, native report calculation/provenance и ограничения scientific claim. Никакого реального deployment/retrain/ticket действия в приёмке.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Полнота inventory-трассировки

### Оставшиеся обязанности

- `remaining:0486` → REQ-DDM-02-01, REQ-DDM-02-02. Earlier foreign model accepted в direct builder; monitor защиту сохранить. Production bypass не доказан.
- `remaining:0487` → REQ-DDM-02-02, REQ-DDM-02-03, REQ-DDM-02-07. Exact admitted concrete source только finite replay. Нужен bounded owner investigation/typed integrate contract и проверка положительной способности либо точный remaining decision.
- `remaining:0488` → REQ-DDM-02-04, REQ-DDM-02-05, REQ-DDM-02-06, REQ-DDM-02-07. Policy_id в YAML не доходит decision; actual report provenance/native/statistical scope требуют отдельного результата.
### Сохранение

- `preserve:0791` → REQ-DDM-02-02, REQ-DDM-02-07 → TEST-DDM-02-03, TEST-DDM-02-07. Historical FP pass distinct from current validity — проверяется указанным конкретным positive/boundary oracle, не только наличием текста.
- `preserve:0792` → REQ-DDM-02-02, REQ-DDM-02-06 → TEST-DDM-02-02, TEST-DDM-02-03, TEST-DDM-02-07. Actual checker/report/source binding — проверяется указанным конкретным positive/boundary oracle, не только наличием текста.
- `preserve:0793` → REQ-DDM-02-02, REQ-DDM-02-03, REQ-DDM-02-07 → TEST-DDM-02-03, TEST-DDM-02-04. Observed empty distinct from unavailable — проверяется указанным конкретным positive/boundary oracle, не только наличием текста.
- `preserve:0794` → REQ-DDM-02-01, REQ-DDM-02-02 → TEST-DDM-02-01, TEST-DDM-02-02. Complete basis reconciliation — проверяется указанным конкретным positive/boundary oracle, не только наличием текста.
- `preserve:0795` → REQ-DDM-02-02, REQ-DDM-02-07 → TEST-DDM-02-03. Persisted projection not authority — проверяется указанным конкретным positive/boundary oracle, не только наличием текста.
- `preserve:0796` → REQ-DDM-02-04 → TEST-DDM-02-05. R4/R3 veto and conditional R2 signoff — проверяется указанным конкретным positive/boundary oracle, не только наличием текста.
- `preserve:0797` → REQ-DDM-02-02, REQ-DDM-02-03, REQ-DDM-02-07 → TEST-DDM-02-03, TEST-DDM-02-04, TEST-DDM-02-05. Finite-only final refusal — проверяется указанным конкретным positive/boundary oracle, не только наличием текста.


## v2: дополнительная различающая проверка (PROPOSED, не выполнена)

Основание: финальное technical/capability review `CS-004`. Исходные source/residual/preservation mappings сохраняются; это дополнительное условие приёмки, не утверждение исправленного продукта.

### TEST-DDM-02-08 · actual calibration producer holdout identity and method provenance

**Требования:** REQ-DDM-02-06, REQ-DDM-02-03. **Статус:** NOT_RUN.

**Setup:** Existing calibration CLI/source route с одним source stream; separate positive source windows с одинаковыми numerical values и разными trusted observation/time coordinates; relabelled reused observations negative. Raw quantile и separately prepared MBB profiles; selected source artifact immutable.

**Действие:** Actual source preparation→calibrate→report/audit→persist→fresh readback. Verify selection IDs resolve actual artifact coordinates, not caller labels. Observe genuine resampling index plan when MBB declared; внешняя подготовка разрешена.

**Oracle:** One-stream route не копирует calibration в holdout: typed insufficient-holdout/unqualified result, no empirical certificate. Distinct actual observations may have equal values; reused observations under new labels do not establish independent denominator. Raw quantile is not labelled MBB; declared MBB has linked actual producer/index lineage (seed/block metadata alone insufficient). Missing source gives unqualified research, not blanket refusal. Finite helper smoke and final production veto unchanged.

**Ожидается:** Positive raw/prepared-MBB bounded computation; negative lineage/reuse controls; NOT_RUN.

**Owner/seams:** Existing calibration/calibrate.py CLI and producer; test_stationary_replay.py; observation-source admission and selected fresh registry owner. Actual sources/producer not replaced for accepted property.

**Evidence:** Source artifact digest+coordinates, disjoint selection evidence and method/index lineage, actual report currentness, all denominators. No FP independence/ERT/FDR proof claimed from synthetic fixture.

**Дополнение REQ→TEST:** REQ-DDM-02-06 → TEST-DDM-02-08; REQ-DDM-02-03 → TEST-DDM-02-08. Existing TEST и historical evidence не удаляются.
