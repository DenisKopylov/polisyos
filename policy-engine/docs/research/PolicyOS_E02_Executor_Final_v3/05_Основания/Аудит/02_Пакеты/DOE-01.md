# DOE-01 — ограниченная генерация и объявленные раунды

**C116 · LANE-10 · B97, B98, B99 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Три исходных ремонта подтверждены в ограниченном исполнении actual owners. GRID_EXTREME ограничивает итератор до материализации; AdaptiveSampler возвращает последний завершённый результат без скрытого повторного evaluator; исходный `allow_large_run` переносится неизменным. Неудача generation/evaluation/analysis различается в attempts, полезный предыдущий result сохраняется.

**4 MATCH; 6 неизменённых тестовых тел / 11 cases PASS. Новых R не установлено.** Это actual leaf execution с synthetic adaptive backends, не native SALib. Полное закрытие пакета не заявлено.

## 2. Матрица исходных оснований

| ID | Исходный ремонт | Actual capability | Остаток |
|---|---|---|---|
| B97 | Ограничить product до materialization и не удерживать полную base. | 12 параметров / cap 3: перечислены 3 угла, собственный массив 288 байт, прежний prefix сохранён. | G01/G02: 10 координат постоянны; это не покрытие 4096 углов и не robust-policy authority. |
| B98 | Не выполнять скрытый финальный раунд; сохранить готовое после последующей ошибки. | Один раунд вызывает [6], два — [6,12]; last result соответствует последней completed round. Ошибка следующего analysis сохраняет result первого, но учитывает все 18 завершённых evaluator rows. | G02: в AdaptiveResult нет sample payload/ref; statistical convergence и lifecycle не доказаны. |
| B99 | Не повышать False до True. | При cap 6 и False второй дизайн из 12 строк не достигает evaluator; True допускает его явно. Перенесённые permissions совпадают с исходными. | Per-design cap не объявлен суммарным ресурсным лимитом; native checks G01. |

## 3. Producer → consumer

Actual [sampling.py:65–77](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/sampling.py#L65-L77) сначала применяет `islice`, затем создаёт NumPy array. Сценарии и их порядок не изменены; изменена только ненужная работа и владение памятью. Actual stress caller вызывает этот generator до evaluator loop и строит finite outcome basis по объявленному плану, а не по всем теоретическим углам; этот соседний consumer прочитан, но не выполнен.

[Adaptive owner:108–245](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/adaptive.py#L108-L245) сохраняет permission, проверяет estimated size перед generation, валидирует формы samples/outputs и различает фазы отказа. При evaluator exception число завершённых строк неизвестно (`None`), при analysis failure оно известно и учитывается. После исчерпания раундов возвращается `last_result`, без нового design/evaluation.

[Plan validator:186–224](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/designs.py#L186-L224) остаётся единым владельцем per-design size guard. Явный override сохранён: аудит не требует нового неизменяемого потолка исследовательских возможностей.

## 4. Выполненные проверки

| Проверка | Результат |
|---|---|
| P01 | 6 existing bodies / 11 cases: lazy cap, zero rounds, три фазы ошибок, malformed output и malformed samples — PASS. |
| P02 | Exact old prefix; shape 3×12, 288 байт, base=None. 10 постоянных осей явно показывают ограниченность coverage. |
| P03 | [6] / [6,12] без hidden rerun; False/cap 6 → [6], True/cap 6 → [6,12]. |
| P04 | Failed second analysis: 1 completed round, last result 6 runs, total evaluator rows 18, failed attempt completed=12. |

[Probe](../04_Проверки/C116_DOE01/probe_doe01.py) · [diagnostics](../04_Проверки/C116_DOE01/bounded_diagnostics.json) · [команды и exit codes](../04_Проверки/C116_DOE01/commands.json).

## 5. Сохранить и доквалифицировать

Сохранить prefix equivalence, own NumPy data, отсутствие скрытого раунда, explicit override, phase-specific attempts и возврат полезного результата. Не считать failure после evaluator доказательством нулевой стоимости и не терять готовое ради обработки следующей ошибки.

**C116-G01:** выполнить существующие real-SALib tests на поддерживаемом профиле и actual downstream chain. Сейчас SALib/pytest отсутствуют, public import блокируется Core store.py:2118 на Python 3.12 вместо объявленного 3.14. Это ограничение среды, не дефект продукта. Synthetic analyzer не подтверждает scientific indices.

**C116-G02:** exact final design/stream identity, суммарная стоимость и scientific convergence ещё не квалифицированы. Actual result хранит summary/rounds/attempts, не samples/ref; отдельный production caller AdaptiveSampler в source search не найден. Не объявлять отсутствие встроенного orchestration универсальным провалом системы или требовать новую архитектуру: сначала установить и связать существующий owner/consumer. Короткий GRID prefix — честный ограниченный поиск, не полное stress coverage.

[Исходная карточка](../05_Источники/DOE-01_исходные_строки.txt) · [pinned sources](../05_Источники/C116_источники.json) · [остатки](../01_Реестры/C116_остатки.json) · [границы и уточнение lane](../04_Проверки/C116_DOE01/Чтение_и_границы.md).

**116/127. LANE-10 ещё продолжается: DOE-02, DOE-03, STR-01.** Уточнение к подписи C115: там рассмотрено CAL/UQP подмножество, не весь lane. Следующий DOE-02; фаза заданий исполнителю не начата.
