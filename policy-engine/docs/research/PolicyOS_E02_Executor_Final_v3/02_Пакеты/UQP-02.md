# UQP-02 — Сохранение point mass и малых empirical масс

**LANE-10 · B187, B188, B192 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Backend меняет вычислительную стратегию, но не входной joint law.

**Тип:** C114-R01/R02 narrow fixes; C114-G01 native qualification.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/UQP-02.md), [исходные карточки](../05_Основания/Аудит/05_Источники/UQP-02_исходные_строки.txt), [трассировка](../04_Трассировка/UQP-02.json).

## 2. Уже работает — сохранить

- Named covariance axes, marginal/symmetry/PSD checks до repair; full cross terms и singular null space.
- Analytical wᵀΣw, shared Gaussian transforms; empirical atoms/weights/shared row IDs.
- Typed incompatibility refusal; declared joint identity не verified authority.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| B187 | qualify | REQ-UQP-02-03 | Named axes repaired; сохранить malformed refusals. |
| B188 | fix | REQ-UQP-02-01, REQ-UQP-02-03, REQ-UQP-02-05 | Joint repaired, marginal std0 ещё меняет law. |
| B192 | fix | REQ-UQP-02-02, REQ-UQP-02-04 | Carrier consumed, endpoint clip теряет tail atom. |
| C114-R01 | fix | REQ-UQP-02-01 | std floor не error model. |
| C114-R02 | fix | REQ-UQP-02-02 | Finite empirical endpoints не Gaussian infinities. |
| C114-G01 | qualify | REQ-UQP-02-03, REQ-UQP-02-04, REQ-UQP-02-05 | Native successful builder/store пока не доказан. |

## 4. Нормативные требования результата

**REQ-UQP-02-01.** Marginal random/QMC Normal со std0 должен давать точную point mass без искусственного scale floor.

**REQ-UQP-02-02.** Empirical inverse-CDF не применяет Gaussian endpoint clipping и сохраняет каждый положительный непустой interval принятой floating-point CDF; zero-weight atoms не выбираются. Положительный source weight, interval которого схлопнулся при normalization/cumsum, должен до sampling вызвать typed numeric-resolution refusal либо явно заявленный limited result; молча менять law запрещено. Наличие положительного float64 weight само по себе не гарантирует представимый CDF interval или достижимость на native uniform lattice.

**REQ-UQP-02-03.** Именованные covariance axes и полный совместный Gaussian law должны одинаково потребляться analytical/delta/random/QMC, сохраняя singular directions.

**REQ-UQP-02-04.** Empirical carriers должны сохранять atoms/weights/shared rows и exact selected source через persistence/re-propagation; несовместимый joint contract даёт typed limited/refusal, не независимые marginals.

**REQ-UQP-02-05.** Повторный resampling не создаёт empirical evidence или verified joint authority; successful native result должен сохранять declared limitations.

## 5. Конкретное техническое решение — рекомендуемый способ

- В _sample_from_envelope и QMC Normal branch после validated fit: if std==0 return full(mean) до PRNG/ppf; positive std без max(std,1e-12). Negative/nonfinite std по-прежнему отвергаются admission. Не вводить jitter в declared law.
- В _empirical_indices_from_uniform validate finite domain [0,1), проверить normalized cumulative finite/monotone и для каждого исходного positive weight строгое увеличение соседних CDF boundaries после выбранной арифметики. Затем searchsorted(side=right), tail floating-roundoff cap только до last positive atom. Если публичный helper принимает1, явно обработать endpoint последним positive atom; zero weights не оживлять. Gaussian ppf protection оставить в его ветке. Для collapsed positive interval выбранный по умолчанию bounded outcome — typed numeric-resolution refusal до выдачи draws/persisted success, сохраняя admitted carrier; не обещать arbitrary-precision sampler. Empty interval и отсутствие достижимой точки конечной uniform lattice различать: детерминированный inverse-CDF проверяет представимые u, native random/QMC не гарантирует наблюдение любого редкого atom в конечной выборке.
- Сохранить preparation owner и named covariance builder. Actual CAS/profile/joint carrier tests использовать с UQS/CAL-06; no second sampler.

**Существующие code/test owners:**
- [`src/polisyos/foundry/uncertainty/monte_carlo.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py).
- [`src/polisyos/foundry/uncertainty/covariance.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/covariance.py).
- [`src/polisyos/foundry/uncertainty/analytical.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/analytical.py).
- [`tests/unit/remediation/test_uqp_02.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_uqp_02.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-UQP-02-01 → REQ-UQP-02-01

**Уровень:** actual random/QMC + threshold. **Ожидается:** positive + negative + boundary.

**Setup:** Normal mean0/std0, затем mean2/std0, positive std1 control; equivalent covariance[[0]].

**Действие:** Оба native sampling routes → y=1[a>0] и identity.

**Oracle:** All draws exactly mean; threshold mean0 даёт все0; equivalent singular route совпадает. Positive std сохраняет variance; не проверять случайный mean равным точному математическому.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQP-02-02 → REQ-UQP-02-02, REQ-UQP-02-04

**Уровень:** deterministic inverse-CDF. **Ожидается:** positive + negative + boundary.

**Setup:** Atoms[-1,1], weights[1e-12,1−1e-12]; u=0,5e-13,1e-12,nextafter(1,0); zero-weight first/last controls. Boundary: positive float64 weights[1,1e-20] имеют normalized/cumulative boundaries[1,1] на обычном float64 path — последний interval пуст; carrier сохраняет исходную положительную массу.

**Действие:** Actual _empirical_indices_from_uniform и paired columns.

**Oracle:** Для right-continuous [0,1) convention первые два u выбирают−1, boundary1e-12 выбирает+1; indices shared. u вне domain/NaN отказ; u=1 либо документированный endpoint last-positive, либо явный отказ; никакого clipping1e-10. Для [1,1e-20] actual numeric-resolution check обязан обнаружить collapsed positive tail и дать typed refusal до successful sample/result publication; не считать молчаливое отсутствие atom правильным law. Original carrier/weights не переписываются. Выборка native random/QMC не обязана увидеть редкий atom: это не oracle; проверяются конкретные достижимые u, interval semantics и честная граница resolution.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQP-02-03 → REQ-UQP-02-03

**Уровень:** native named-law equivalence. **Ожидается:** positive + negative + boundary.

**Setup:** Covariance diag1/9 с reversed columns; 3-axis all6 permutations; a=b covariance ones, y=a−b.

**Действие:** Actual builder/analytical/delta/random/QMC; indefinite/duplicate/marginal mismatch controls.

**Oracle:** Axes reconstruct exact expected matrix (atol=1e-9); singular y variance0 and every draw difference0 (float32 atol=1e-6). Independent formula control variance2; invalid matrix не repair-ится jitter10.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQP-02-04 → REQ-UQP-02-04, REQ-UQP-02-05

**Уровень:** E02-I10-B persist/repropagate. **Ожидается:** positive + negative + boundary.

**Setup:** Carrier[-1,0,0,1], weighted9:1 case, aligned columns and wrong-axis negative; actual tmp store/profile.

**Действие:** Native propagator→actual result builder→persist/load→second propagation.

**Oracle:** Only source atoms, weights and joint pairing retained; profile/source mismatch refuses affected path. Declared ID не gate proof; resampling n не становится новым sample evidence count.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I10-B** из [канонического lane integration-контракта](../03_Интеграция/LANE-10.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: UQP-01. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

UQP-01 fixed invocation и UQP-03 result ledger уже те же consumers; write mutex MC. CAL-06 supplies tied law; UQS supplies exact draws.

## 8. Совместимость и восстановление

Degenerate law behaviour intentionally corrected; seeded positive-std streams не менять без причины. Historical samples не переписывать. Endpoint convention documented with numeric profile, не невидимый schema change.

## 9. Free-grow и design decisions

- [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md#d25-epistemic-regime-architecture) и [синтез §4](../05_Основания/Исследование/design_direction.md): uncertainty/conditional outputs полезны без незаслуженной authority; новый совместимый law использует общий механизм, не доменную ветку.

## 10. Решения, которые нельзя подменить догадкой

Блокирующих внешних решений не требуется; технический вариант уточняется только при подтверждённой несовместимости названного owner.

## 11. Что предъявить и что не является готовностью

Два distinguishing regressions и native successful persistence/repropagation. Numeric-resolution refusal допустим для collapsed intervals и не заменяет positive 1e-12 endpoint regression; arbitrary-precision/approximate sampler не требуется. Covariance не универсальный nonlinear joint law; scientific source assumptions отдельно.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0313` → REQ-UQP-02-01; std floor не error model.
- `remaining:0314` → REQ-UQP-02-02; Finite empirical endpoints не Gaussian infinities.
- `remaining:0315` → REQ-UQP-02-03, REQ-UQP-02-04, REQ-UQP-02-05; Native successful builder/store пока не доказан.
- `preserve:0489` → REQ-UQP-02-03; Named covariance axes — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0490` → REQ-UQP-02-03; PSD/marginal validation before repair — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0491` → REQ-UQP-02-01, REQ-UQP-02-03; Singular null space — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0492` → REQ-UQP-02-03; wᵀΣw — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0493` → REQ-UQP-02-03; Shared Gaussian transforms — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0494` → REQ-UQP-02-02, REQ-UQP-02-04; Empirical atoms/weights/shared indices — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0495` → REQ-UQP-02-03, REQ-UQP-02-04; Typed incompatibility refusal — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0496` → REQ-UQP-02-05; Declared identity not authority — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
