# UQS-01 — summary, интервалы и информационные единицы

**C112 · LANE-10 · B199–B202 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Полезный основной ремонт есть: exact selected duplicate views не повышают level и не создают информацию; неизвестная зависимость больше не подаётся в precision/Bayesian formula. Асимметричная выборка сохраняет исходные mean и equal-tail interval через явный limited candidate. Draws и их расположение не исчезают, но caller-only строки честно не становятся подтверждённым совместным законом.

**Остатки:** secondary Gaussian decomposition теряет non-gating ограничения (**C112-R01**); простая сумма больших конечных точек переполняется и меняет point (**C112-R02**). Допустимое независимое объединение и native CAS→propagation остаются **C112-G01**, не объявлены полным закрытием.

**5 MATCH; 12 неизменённых test bodies / 26 cases PASS в bounded runner.** Это не native suite и не статистическая аттестация.

## 2. Матрица исходных оснований

| ID | Исходный ремонт | Actual capability | Остаток |
|---|---|---|---|
| B199 | Level/type не повышаются от повтора одной ссылки. | Четыре exact selected views дают unique=1, repeated=3; исходные confidence level .8 и width сохранены при всех трёх стратегиях. | In-memory caller labels не считаются source identity: conservative downgrade намеренный. Native selected profiles G01; численная точка R02. |
| B200 | Information units/dependencies до precision update. | Distinct views и копии без установленной связи не сужаются как независимые; effective information count остаётся unknown. Same bytes с разными selected profiles не сливаются. | Public route не устанавливает source-bound независимость, полезная independent fusion не доказана: G01. |
| B201 | Mean=1 и equal-tail [0,0] представлены без подмены. | 99 нулей и 100 сохраняются в summary/candidate; typed limitation, limited consumer, 0 evaluator calls. Fresh recomputation отвергает stale mean=2. | Legacy envelope всё ещё требует внутреннюю точку; явный limited result не равен универсальной propagation capability. |
| B202 | Доступ к точным draws и joint identity не теряется. | Carrier, input shapes и row matrix сохранены; reversed pairing имеет иной persisted candidate. Joint status not_established и gate false. | Legacy positional correspondence не доказательство совместного закона; selected method route source-only. Secondary decomposition R01. |

## 3. Producer → consumer

Aggregator сначала отделяет число входов от информации. Caller metadata/origin labels не доказывают идентичность или независимость. Для нескольких неизвестно связанных входов доступны консервативные границы, не fictitious precision. Persisted route проверяет selected identity/profile, загружает actual input envelope и устраняет только точные повторы выбранного view [S01:520–717](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/aggregator.py#L520-L717). Эти owner functions исполнены, но store/profile seams явно фикстурные; native CAS из этого не следует.

Summary считает mean и quantiles отдельно. Если mean вне equal-tail interval, она не расширяет interval и не переименовывает median: сохраняет исходные числа, exact carrier и typed limitation [S02:387–529](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py#L387-L529). Fresh candidate reader пересчитывает summary из draw context; ограниченный consumer не запускает simulation [S02:578–658](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py#L578-L658).

Поздний selected method-evidence route содержит source/profile/backend/kernel/point-role проверки и передаёт selected summary в `propagate_posterior_summary` (659–922). Он прочитан, не выполнен. Это существующая интеграционная точка для сохранения/развития, не повод создавать новый универсальный реестр и не основание объявить native цепочку закрытой.

## 4. Выполненные проверки

| Проверка | Результат |
|---|---|
| P01 | 10 UQS bodies и 2 Bayesian summary bodies, 26 parameterized cases PASS; actual composition-provenance builder. |
| P02 | Exact repeated selected view: level .8 сохранён в widest/precision/Bayesian; wrong kind отвергнут; same bytes/different profiles остаются двумя unresolved views. |
| P03 | JSON-file fresh candidate: mean 1, interval [0,0], 100 draws, limited result без evaluation; разные pairings различимы, joint authority не выдумана; stale mean отвергнут. |
| P04 | Primary envelope gate=false; secondary total/epistemic/aleatoric gate=true, credible_interval, без carrier. |
| P05 | Singleton point=1e308; две такие точки дают 1.1e308 из-за sum overflow и clamp, gate=false. |

[Probe](../04_Проверки/C112_UQS01/probe_uqs01.py) · [диагностика](../04_Проверки/C112_UQS01/bounded_diagnostics.json) · [команды, логи и exit codes](../04_Проверки/C112_UQS01/commands.json).

## 5. Подтверждённые ограниченные остатки

### C112-R01 — ограничения summary не доходят до вторичной decomposition

Primary caller-only Bayesian envelope явно `gate_eligible=False`. Но тот же producer вызывает `UncertaintyDecomposition.from_gaussian_components` без передачи этих ограничений [S02:456–475](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py#L456-L475). Gaussian helper назначает credible semantics и не задаёт gate flag, оставляя default true [S03:116–146](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/protocol.py#L116-L146). P04 на [-1,0,1] подтверждает несогласованность всех трёх secondary outputs.

Это **дефект семантики in-memory диагностического выхода**, не доказанный operational bypass. Candidate persistence decomposition не включает, downstream gate не запускался. Оставшаяся работа — сохранить полезную decomposition, но передавать caller-only происхождение, approximation и запреты через существующий контракт, не повышая authority по Gaussian label.

### C112-R02 — overflow среднего скрывается ограничением по bounds

`_widest` использует `sum(points)/n` [S01:227–280](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/aggregator.py#L227-L280). Для двух finite 1e308 сумма становится inf, а последующий clamp возвращает верхнюю границу 1.1e308 вместо среднего 1e308. Actual DTO/provenance принимают конечный, но изменённый point. Нужен устойчивый finite-range расчёт, сохраняя non-gating ограничения и не выдавая численную коррекцию за независимость источников. Частота такого диапазона в реальном использовании не установлена.

## 6. Сохранить и доквалифицировать

Сохранить exact selected-view dedup, запрет caller-label authority, различение source count/effective information, исходные mean/quantiles, carriers, fresh recomputation и явное отсутствие joint admission у positional rows. Снятие запретов ради четырёх «независимых» metadata labels не будет исправлением.

C112-G01: public aggregator пока не разрешает подтверждённые независимые единицы; осторожный hull безопасен, но не полная capability положительного объединения. Нужна предметная source-bound проверка существующего пути, не универсальный deterministic inventor. Native selected CAS/method-evidence/MC и scientific posterior quality также открыты. Existing native CAS/MC tests прочитаны, не запущены. Python 3.12.14 блокирует import на 3.14 syntax uncertainty.py:287, JAX/pytest отсутствуют. Storage/profile fixture не выдаётся за Core cryptographic admission.

[Исходная карточка](../05_Источники/UQS-01_исходные_строки.txt) · [pinned sources](../05_Источники/C112_источники.json) · [остатки](../01_Реестры/C112_остатки.json) · [точные границы](../04_Проверки/C112_UQS01/Чтение_и_границы.md).

**112/127 — промежуточный аудит. Следующий UQP-01. Фаза заданий исполнителю не начата.**
