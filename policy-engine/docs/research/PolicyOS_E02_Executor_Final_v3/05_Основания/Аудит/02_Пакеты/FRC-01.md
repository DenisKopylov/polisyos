# FRC-01 — честная калибровочная граница и реальные временные роли
## C29 · 31 октября 2026 года

**Исходные IDs:** B32, LA-051, фаза 1/2. **Порядок:** 29/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Ответственный за полное закрытие LA-051 — **FRC-02**, не этот пакет.

## Решение

**Основной исходный суррогат устранён:** finite estimate/CI и nominal confidence больше не дают empirical coverage, pass_rate=1 или floor_passed=True. Диагностика формы сохраняется отдельно; отсутствие истории даёт limit/blocked с нулевым знаменателем и неизвестными измеренными метриками. Дата 2026-06-02 не заменена на now: record требует шесть явно связанных aware timestamps, refs и разрешённое empirical evidence.

Найден один подтверждённый остаток в соседнем владельце summary: **C29-R01 — агрегатор повторно создаёт pass/floor=True из равенства numerator/denominator, игнорируя входной limit/floor=False.** Это дефект смысла диагностического результата, не доказанный обход production admission. Support refs также ещё частично конструируются строками; их предметная связь остаётся отдельным пробелом.

**21 MATCH, 0 ERROR**, exit 0: реальные S10 DTO/builders и численный curve owner, выбранные неизменённые generation-cycle определения; внешние ref/hash/finite/bridge seams обозначены как фикстуры. Native pytest/HTTP/CAS/полный bridge не запускались.

## 1. Матрица исходных требований

| ID | Выполненное ограниченное исправление | Остаток |
|---|---|---|
| B32 | Нет общей зашитой даты; нет now-подмены; шесть времён переносятся из admitted evidence; отсутствующая credibility консервативна | C29-G01 — native owner bridge, C29-G02 — unresolved support refs, C29-G03 — ограниченность temporal profile |
| LA-051 | Estimator-shape diagnostics отделены от калибровки; nominal confidence не empirical coverage; raw mapping не разрешает pass; purpose denials сохранены | C29-R01 summary; C29-G01/G02/G04; полная приёмка только после FRC-02 |

[Полная исходная карточка](../05_Источники/FRC-01_исходные_строки.txt), строки 3530–3669, включая LK29/LK30. Полезные guards EvalSafety/WMR/candidate не изменялись и не отменяются. Их проверка в этом проходе не выдаётся за native run.

## 2. Что теперь делает адаптер estimator

`_s10_calibration_evidence_from_report` сохраняет finite flags, diagnostic status, sample counts, nominal confidence и relative CI width внутри `estimator_shape_diagnostics`. Но всегда оставляет denominator/numerator=0, pass_rate=0, floor=False, measured coverage/error=None. Отсутствующий report — blocked; имеющийся report без калибровочного корпуса — limit. [S01:17649–17750](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L17649-L17750)

**P01–P04:** хороший finite report не получает pass; nominal 0.8 и 0.95 имеют одинаковые отсутствующие empirical metrics; None остаётся blocked; failed diagnostic виден и не открывает floor. Небольшой `_is_finite_number` в harness — явная эквивалентная фикстура из-за Python3.14 exception syntax; сам выбранный diagnostic owner исполнен без переписывания. Это не native импорт generation_cycle.

Сохранён и настоящий численный владелец: текущий путь — `calibration/diagnostics/continuous.py`, а не прежний `calibration/continuous.py`; curve расположен в package `calibration/curve`. **P17:** при одинаковом nominal .95 actual curve на двух заданных predictive corpora возвращает coverage 1 и 0, ECE около .05 и .95. **P18:** пустой корпус отвергается. Это контроль различия величин, **не рекомендация проверять CI причинного параметра индивидуальными исходами**. [S12:12–86](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/calibration/curve/_compute.py#L12-L86)

Continuous report дополнительно различает вычисленную статистику и происхождение данных: `to_truthfulness_receipt` оставляет continuous measurement source неустановленным, даже если численный кандидат выглядит откалиброванным. Этот соседний контракт прочитан, не исполнен. [S05:151–240](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/calibration_diagnostics.py#L151-L240)

## 3. Времена и refs: неизвестное больше не дописывается

`_bound_s10_temporal_roles` требует все шесть aware времён, нормализует UTC и проверяет текущий temporal profile. Builder создаёт calibration record только при разрешённой empirical wrapper, отсутствии resolver error и связанных temporal/ref полях. Raw mapping с согласованными числами не заменяет owner admission. [S01:17403–17518](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L17403-L17518) [S01:17753–17829](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L17753-L17829)

**P05/P10:** шесть разных исходных времён сохраняются без подмены. **P06/P08:** missing/naive и неверное окно не допускаются. **P09:** raw mapping со всеми refs, числами и временами → record=None, tier=blocked. **P11/P12:** resolver error или отсутствующий prediction_ref не обходятся. **P20:** пропущенная credibility становится insufficient_history, а не credible.

Положительный P10 использует **вручную введённую resolved-wrapper фикстуру**: доказана передача полей и валидация DTO, не подлинность источника и не работа canonical loader. Actual `ForecastCalibrationRecord` требует ненулевой знаменатель для pass, согласованное numerator/denominator, floor и правильный порядок окна; **P19** сохраняет отрицательный контроль нулевого знаменателя. [S02:187–258](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py#L187-L258)

### C29-G03 — не создавать искусственно разные времена

Оба текущих владельца требуют все шесть значений различными, а calibration window — до prediction, observation — после. **P07** отказывает даже совпавшим policy-effective/data-valid. Это общий **явно ограниченный профиль** S10 и empirical context, не новый незамеченный разрыв между ними. Для другого допустимого экспериментального дизайна нужна предметная квалификация и согласованное расширение owner profile, а не изменение timestamps ради прохождения проверки. [S08:345–366](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/calibration/forecast_bridge.py#L345-L366)

В существующем `test_calibration_time_roles_are_preserved_from_bound_evidence` передаётся только raw mapping, а окно заканчивается после prediction. Теперь этот тест не соответствует актуальной admitted boundary; header файла также исторически говорит RED. Это обнаруженное чтением несоответствие тестовой конструкции, **не заявленный pytest failure**. Нельзя вернуть небезопасный raw bypass, чтобы сделать старое ожидание зелёным. [S03:105–185](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_frc_01.py#L105-L185)

## 4. Условная полезность и фактический маршрут к потребителю

**P13:** simulation_only_advisory сохраняется без calibration record. **P14:** реальные typed support/envelope сохраняют запреты production recommendation/claim, S11 и causal/treatment authority для predictive family. **P15:** admitted record измеренного ряда может хранить pass, но несвязанный N4 outcome остаётся blocked; измерение и применимость к конкретной цели не смешиваются.

В текущем checkout **есть не только интерфейс bridge**. HTTP service создаёт/persists empirical evidence из backtest, задаёт canonical loader, передаёт actual rule и временные роли в `RealValueOwnerGateway.produce_forecast_inputs`; reopened reader снова разрешает candidate/report/evidence и вызывает тот же gateway. Он отдельно требует counterfactual credibility=`not_established`. [S09:653–706](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/predictive_calibration.py#L653-L706) [S09:1970–2041](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/predictive_calibration.py#L1970-L2041)

**C29-G01:** это значимая существующая реализация, которую нужно сохранять. Полные selected-profile custody, метод/estimand/history/rule совместимость, реальные observations и HTTP create→reopen остаются для последовательного FRC-02. Здесь эта цепочка только адресно прочитана; «bridge отсутствует» не утверждается, но LA-051 полностью закрытым не становится.

### C29-G02 — оставшаяся строковая оболочка support

Calibration record теперь переносит source refs, но support ещё создаёт `source-contract://`, `method-validity://`, `sensitivity://`, `equilibrium-check://`, distribution и `interval://.../95` из IDs/hash. **P21:** nominal report .8 всё равно получает `/95`. Builder не разрешает содержание этих URI. Фиксированный суффикс сам по себе не доказывает измеренное coverage .95, но и не является связью с реально выбранным интервалом. [S01:17519–17587](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L17519-L17587)

Нужно использовать существующие producer artifacts/refs там, где заявлена содержательная поддержка, а неизвестное маркировать. Не удалять полезный условный forecast из-за отсутствия эмпирической authority и не добавлять новый параллельный реестр подтверждений.

## 5. C29-R01 — summary вновь повышает ограниченную запись до pass

`summarize_forecast_support_integrity` — диагностический агрегатор, не самостоятельное разрешение production. Он складывает numerator/denominator и задаёт status=pass/floor=True при положительном полном покрытии, не учитывая исходные calibration_status, floor_passed или governed threshold. [S02:590–649](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py#L590-L649)

**P16, настоящие DTO и функция:** входной record имеет **limit, floor=False, 10/10**; support blocked. Summary выдаёт **pass, floor=True, issues=[]**. Числа не изменены, но смысл допуска потерян. Такая комбинация может отражать неполноту основания, несмотря на полное покрытие; арифметика не должна отменять ограничение владельца.

Сохранять totals, typed checks и purpose denials. Минимальный остаток — различить описательную статистику и разрешённый status/floor, наследовать ограничения и не назначать новый floor без основания. Функция действительно вызывается sibling proving-ground owner после build/envelope; полный G2 и последующие consumers не исполнялись, поэтому production обход не утверждается. [S10:3533–3574](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py#L3533-L3574)

## 6. Границы исполнения и следующий пакет

**C29-G04:** штатные тесты не запускались; отсутствующий pytest не является продуктовым дефектом. Полностью прочитаны S10 owner (939 строк), FRC-01 tests (242), continuous diagnostics (403), diagnostic DTO (334), curve owner/types. Source index фиксирует только реально прочитанные диапазоны остальных файлов.

Первый harness остановился до наблюдений на ошибочно выбранном excerpt candidate ID. После исправления только диапазона — полный run **21 MATCH, 0 ERROR**. Оба журнала сохранены. Historical records, прежние отчёты и checkout не менялись. MATCH включает воспроизведённый остаток, а не означает принятие продукта.

[Диагностика](../04_Проверки/C29_FRC01/bounded_diagnostics.json) · [команды](../04_Проверки/C29_FRC01/commands.json) · [границы](../04_Проверки/C29_FRC01/Чтение_и_границы.md) · [источники](../05_Источники/C29_источники.json) · [остатки](../01_Реестры/C29_остатки.json).

**29/127 пакетов рассмотрены ограниченно; 78 уникальных B/LA частично оценены; полного закрытия нет.** Следующий **PCL-01 / LA-052, LA-053**, строго по исходному порядку, не FRC-02 вне очереди.
