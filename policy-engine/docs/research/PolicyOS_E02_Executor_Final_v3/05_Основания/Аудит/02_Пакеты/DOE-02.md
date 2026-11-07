# DOE-02 — единый закон распределений и локальные RNG

**C117 · LANE-10 · B100, B101 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Sampling и analysis используют один `_build_salib_problem`, а не два расходящихся словаря. Закон задан типизированно: NORMAL означает явно параметризованный truncated normal на физических bounds; TRIANGULAR содержит mode fraction; неоднозначные legacy nonuniform и неподдержанный bounded LOGNORMAL получают отказ. Sampling/analysis передают раздельные derived seeds вместо общего NumPy reset.

**5 MATCH; 6 неизменённых выбранных тестовых тел PASS. Новых подтверждённых R нет.** Выполнены actual wrappers, Pydantic, geometry и настоящий SciPy adapter; SALib подменён явной границей. Это не native SALib или scientific acceptance. G01/G02 открыты.

## 2. Матрица исходных оснований

| ID | Исходный ремонт | Actual capability | Остаток |
|---|---|---|---|
| B100 | Единое содержательное определение закона, не простое копирование dists. | Оба helper дают одинаковые bounds/dists; typed normal/triangular roundtrip сохраняет fingerprint; real SciPy PPF меняет quantiles при том же seed, support соблюдён. Legacy ambiguity и LOGNORMAL не скрываются uniform fallback. | G01: реальный SALib не исполнен. G02: current-plan fingerprint не связывает bare arrays с original design. |
| B101 | Seed доходит до backend, global NumPy не сбрасывается; разделены streams. | Source-test spies видят derived sampling/analysis seeds, external state не изменён. SciPy adapter повторяется и не зависит от порядка двух requests. Seeded FAST получает explicit compatibility_pending. | Полный uncertainty/model RNG, replica/replay и native profile — G01, не доказанная независимость. |

## 3. Producer → consumer

[Canonical mapping и fingerprint](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/designs.py#L241-L339) сохраняют физическую область, typed параметры и profile `SALib@1.5.2`. Изменение закона — намеренная semantic correction; однозначный UNIFORM сохраняет прежний bounded mapping. Физические bounds не переименовываются в mean/std.

[Sampling owner](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/sampling.py#L20-L62) передаёт локальный seed; legacy saltelli fallback не принимает seeded request молча. [Analyzer owner](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/analysis.py#L76-L166) использует тот же problem и отдельный analysis stream. Seeded FAST консервативно отказан из-за известной compatibility boundary, не замаскирован успешным nondeterministic result.

[Inverse geometry](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/morris_geometry.py#L38-L141) проверяет Morris grid в unit coordinates через actual CDF. Это geometry, не authenticated design provenance. Analyzer metadata получает fingerprint из текущего plan, а не из source artifact samples; bare array API сам не доказывает, какой закон породил строки.

## 4. Проверки

| Проверка | Результат |
|---|---|
| P01 | 6 unchanged bodies PASS: explicit refusals, 2 seed spies, seeded FAST и domain separation. |
| P02 | Uniform / truncated normal / triangular: identical producer/analyzer problem, stable typed roundtrip, разные quantiles и bounded support; global NumPy unchanged. Реальный SciPy adapter, не SALib. |
| P03 | Два seed в прямом и обратном порядке дают те же соответствующие arrays; смена seed меняет rows; стадии domain-separated. |
| P04 | Uniform rows + current normal plan дают normal fingerprint. Actual wrapper, fake numerical backend; scientific indices не оцениваются. |
| P05 | Normal/triangular PPF→actual inverse CDF возвращает unit [0,2/3], geometry helper принимает. |

[Probe](../04_Проверки/C117_DOE02/probe_doe02.py) · [diagnostics](../04_Проверки/C117_DOE02/bounded_diagnostics.json) · [команды/логи/exit codes](../04_Проверки/C117_DOE02/commands.json).

## 5. Сохранить и доквалифицировать

Сохранить единого владельца mapping, explicit typed migration/refusal, локальные streams, bounded support и консервативный seeded FAST отказ. Не возвращать legacy global reset ради совпадения старых случайных последовательностей. Не считать повтор request/cache-hit новой независимой репликой.

**C117-G01:** существующие native SALib tests ещё UNRUN. Lock фиксирует 1.5.2; установленного SALib нет. Python 3.12 блокирует public facade через Core 3.14 syntax; pytest отсутствует. True SciPy adapter — отдельное численное свидетельство, не замена SALib geometry/analysis. Uncertainty использует собственный `random_seed`; не доказано, что один plan.seed воспроизводит весь pipeline. Независимость параметров и валидность world model не возникают из детерминированного adapter.

**C117-G02:** fingerprint описывает текущий план, но не аутентифицирует original sample matrix. Нужна квалификация существующего design/artifact/consumer binding с axes, seed/replica и backend profile. P04 не объявлен багом текущего production caller: caller может корректно передавать план, а source-bound route здесь не выполнен. Не строить параллельную paperwork-архитектуру вместо связывания имеющихся owners.

[Исходная карточка](../05_Источники/DOE-02_исходные_строки.txt) · [pinned sources](../05_Источники/C117_источники.json) · [остатки](../01_Реестры/C117_остатки.json) · [границы](../04_Проверки/C117_DOE02/Чтение_и_границы.md).

**117/127. Следующий DOE-03; затем STR-01 завершит последовательность LANE-10. Фаза заданий исполнителю не начата.**
