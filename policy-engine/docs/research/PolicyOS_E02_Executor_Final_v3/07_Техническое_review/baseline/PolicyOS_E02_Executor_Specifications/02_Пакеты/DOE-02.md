# DOE-02 — Native typed law/RNG и source-bound design

**LANE-10 · B100, B101 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Sampler и analyzer исследуют один заданный закон и одну идентичность дизайна.

**Тип:** C117-G01 native qualification; C117-G02 provenance/lifecycle qualification, R нет.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/DOE-02.md), [исходные карточки](../05_Основания/Аудит/05_Источники/DOE-02_исходные_строки.txt), [трассировка](../04_Трассировка/DOE-02.json).

## 2. Уже работает — сохранить

- Canonical typed bounded mapping; legacy ambiguous nonuniform refusal.
- Local domain-separated seeds; seeded FAST и bounded LOGNORMAL compatibility_pending сохраняются.
- Fingerprint описывает mapping, не доказывает origin bare matrix.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| B100 | qualify | REQ-DOE-02-01, REQ-DOE-02-03, REQ-DOE-02-04 | Mapping repaired; native/source design scope открыт. |
| B101 | qualify | REQ-DOE-02-02, REQ-DOE-02-04 | Local streams repaired; full pipeline RNG не доказан одним plan.seed. |
| C117-G01 | qualify | REQ-DOE-02-01, REQ-DOE-02-02, REQ-DOE-02-04 | Pinned SALib1.5.2 actual path; no version upgrade implied. |
| C117-G02 | lifecycle | REQ-DOE-02-03 | Связать existing design artifact, не новый provenance registry. |

## 4. Нормативные требования результата

**REQ-DOE-02-01.** Native SALib sampler/analyzer должны использовать один typed law mapping с physical bounds и declared profile; ambiguous/unsupported law не заменяется uniform.

**REQ-DOE-02-02.** Полный запрос должен задавать stage/model/uncertainty RNG streams; replay сохраняет stream identity, новая replica различается, global NumPy state не сбрасывается.

**REQ-DOE-02-03.** Scientific consumer должен сверять actual source design matrix/axes/law/backend/seed/replica с producer record; current-plan fingerprint сам не аутентифицирует samples.

**REQ-DOE-02-04.** Unsupported seeded FAST/bounded LOGNORMAL остаются адресно compatibility_pending до отдельной квалификации; native backend receipt не переносится на другую версию.

## 5. Конкретное техническое решение — рекомендуемый способ

- _build_salib_problem в designs.py — единственный mapping owner; sampler/analyzer wrappers уже reuse. Не дублировать dict для исправления тестов. Verify lock SALib1.5.2 и actual extras environment, не install/upgrade as hidden fix.
- Census existing design/trajectory artifact writer и consumers; связать matrix digest, axes, canonical mapping fingerprint и stage seeds с его existing payload/ref. Analyzer API bare arrays может остаться исследовательским, но authority consumer требует independently resolved producer context. DOE-01 final result reference использует тот же contract.
- Полная reproducibility table включает uncertainty.random_seed и model randomness отдельно от plan.seed. При неизбежном legacy backend — explicit isolation/profile, не process-global reset.

**Существующие code/test owners:**
- [`src/polisyos/scientist/methods/doe/designs.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/designs.py).
- [`src/polisyos/scientist/methods/doe/sampling.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/sampling.py).
- [`src/polisyos/scientist/methods/doe/analysis.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/analysis.py).
- [`src/polisyos/scientist/methods/doe/uncertainty.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/uncertainty.py).
- [`tests/unit/remediation/test_doe_02.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_doe_02.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-DOE-02-01 → REQ-DOE-02-01, REQ-DOE-02-04

**Уровень:** SALib1.5.2 + SciPy law. **Ожидается:** positive + negative + boundary.

**Setup:** Uniform[-2,2], typed truncated Normal mean0/std.5 same bounds, triangular mode.25; fixed seed.

**Действие:** Actual sampling/analysis mapping and typed roundtrip; inverse-CDF grid controls u=.1,.5,.9.

**Oracle:** Same canonical problem/fingerprint; support within bounds; quantiles equal independent SciPy profile oracle rtol=1e-10 atol=1e-12; nonuniform differs. Legacy ambiguity/LOGNORMAL refuse, не uniform fallback.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DOE-02-02 → REQ-DOE-02-02, REQ-DOE-02-04

**Уровень:** native reproducibility. **Ожидается:** positive + negative + boundary.

**Setup:** Two requests seeds13/17, explicit uncertainty seed and model stream; order AB/BA.

**Действие:** Sample/analyze twice, inspect external NumPy state; new replica vs replay.

**Oracle:** Same full request/profile repeats arrays/indices under declared tolerance; AB/BA corresponding outputs equal; external RNG state unchanged. Sampling/analysis streams differ; seeded FAST pending remains refusal, not nondeterministic success.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DOE-02-03 → REQ-DOE-02-03

**Уровень:** E02-I10-C design→fresh analyzer. **Ожидается:** positive + negative + boundary.

**Setup:** Actual generated uniform design saved through existing artifact owner; normal-plan swap negative, axes/replica/backend mutations.

**Действие:** Fresh consumer resolves original design record and compares expected contract before analyzer.

**Oracle:** Matched design useful result; uniform source+normal current plan mismatch cannot be relabelled normal provenance. Bare arrays remain explicitly in-memory/unverified, not retroactive source proof.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I10-C** из [канонического lane integration-контракта](../03_Интеграция/LANE-10.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: DOE-01. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

Shared design identity owner для DOE-01/03, mutex sampling/analysis. Native SALib wave совместить, не три suites.

## 8. Совместимость и восстановление

UNIFORM legacy однозначный путь сохраняется; nonuniform требует typed migration. Seed sequences могут отличаться от старого global reset намеренно; replay привязан к version/profile, не к фантазии о perpetual bitwise stability.

## 9. Free-grow и design decisions

- [North Star §5](../05_Основания/Архитектура/policy-design-causal-operating-system-north-star.md#5-data-acquisition-and-the-real-product) и [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md#d25-epistemic-regime-architecture): ограниченный поиск даёт полезный результат и следующий запрос данных, не ложную полноту. [Синтез §4](../05_Основания/Исследование/design_direction.md): развивать существующий общий механизм.

## 10. Решения, которые нельзя подменить догадкой

- DEC-DOE-02-01: bounded inventory existing artifact writer/readers и RNG stages, выбрать minimal context binding. Если missing source owner, сохранить gap и дать конкретный adapter proposal; bare-array test не доказывает production mismatch.

## 11. Что предъявить и что не является готовностью

Native backend, full request replay и source binding доказать отдельно. Adapter не создаёт независимость параметров/world-model validity.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0163` → REQ-DOE-02-01, REQ-DOE-02-02, REQ-DOE-02-04; Pinned SALib1.5.2 actual path; no version upgrade implied.
- `remaining:0164` → REQ-DOE-02-03; Связать existing design artifact, не новый provenance registry.
- `preserve:0267` → REQ-DOE-02-01; Canonical typed law mapping — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0268` → REQ-DOE-02-01, REQ-DOE-02-04; Legacy ambiguity refusal — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0269` → REQ-DOE-02-02; Local domain-separated seeds — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0270` → REQ-DOE-02-04; Seeded FAST refusal — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0271` → REQ-DOE-02-04; Bounded LOGNORMAL compatibility refusal — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0272` → REQ-DOE-02-01, REQ-DOE-02-03; Mapping fingerprint — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
