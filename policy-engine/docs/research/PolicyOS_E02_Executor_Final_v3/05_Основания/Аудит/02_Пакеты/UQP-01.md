# UQP-01 — настоящая функция отклика и полный effective call

**C113 · LANE-10 · B186, B189, B190, B191 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Основные ремонты содержательно присутствуют. Fixed nominal inputs сохраняются при изменении случайных координат; required binding проверяется до вызовов. Node не придумывает all-to-all sensitivity, не преобразует меняющееся значение в Python float и сохраняет эффект explicit zero-baseline map. Missing output отделён от настоящего нуля. Existing execute-response projection имеет отдельную source-reconciliation route; caller map остаётся candidate-only.

**5 MATCH; 11 неизменённых test bodies / 12 cases PASS** с явными numerical/sampling seams. **Нового подтверждённого product defect не объявлено.** Native grad/JIT/full node/CAS и precision boundary остаются G01/G02. Отсутствие универсального изобретателя модели не считается дефектом.

## 2. Матрица исходных оснований

| ID | Исходный ремонт | Actual capability | Остаток |
|---|---|---|---|
| B186 | Fixed nominal не пропадают из sampled kwargs. | Delta сохраняет scale=2 и point20; actual random/QMC loops дают nominal20/sample mean20 при всех scale=2. Required fixed input отвергается до evaluator. Callable default7 и explicit0 различаются. | G01: native complete prepared-law/MC result chain не выполнена. |
| B189 | Не делать float(current) внутри tracer path. | Actual node closure проходит NoFloat sentinel; numerical dispatcher probe выбирает delta, сохраняет kwargs. | Native JAX tracer/JIT test прочитан, UNRUN; finite difference не доказывает autodiff или ускорение. |
| B190 | Unknown map не выдаётся за установленную; нулевой baseline не подавляет effect. | Empty mapping остаётся empty; explicit y=x−2 при baseline0 даёт variance1. Partial z сохранён как unresolved, gate=false. Exact Jacobian state-slot helper даёт additive response. | Native source binding и scientific validity G01; caller hypothesis не повышена до authority. |
| B191 | Missing output не становится достоверной константой0. | Delta выдаёт UNKNOWN/non-gating limitation; true zero остаётся [0,0]. MC recorder различает 100 missing NaN и 100 настоящих нулей. | Full MC report/persistence source-read, не execution; G01. |

## 3. Producer → consumer

`_validate_effective_inputs` связывает **всю** invocation через inspectable signature и отдельно требует nominal для uncertain coordinates [S05:164–217](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/protocol.py#L164-L217). Delta и dispatcher начинают с копии полного nominal mapping, затем заменяют только varying names [S01:58–109](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/delta.py#L58-L109). Оба MC loop делают тот же merge перед actual evaluation; shallow mapping не копирует большие fixed objects целиком.

Node caller mapping валидируется по именам/числам, неизвестная связь не заполняется автоматически. Mutable response values остаются в arithmetic expression [S04:1609–1688](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py#L1609-L1688). В execute-result marking caller/unknown/recomputed кандидатам явно сохраняются ограничения и gate=false; исходные полезные выходы не выбрасываются.

Source-backed branch связывает calibration/execute basis refs, digests, centers, target series, envelope roster и unit identities [S04:1010–1280](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py#L1010-L1280). Projection использует абсолютный Jacobian и additive displacement, а не умножение нулевого baseline [S04:1484–1562](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py#L1484-L1562). Source binding прочитан, **не** доказан fixture projection.

Missing output проверяется до Jacobian; отсутствие всех ключей не требует differentiation. Dispatcher может направить structural absence в typed delta result без sampled fallback. MC recorder хранит адресные missing outcomes, а result builder имеет UNKNOWN/non-gating ветку вместо credible zero [S03:2165–2236](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py#L2165-L2236). Последний builder здесь source-only.

## 4. Выполненные проверки

| Проверка | Результат и граница |
|---|---|
| P01 | 12 existing cases PASS; numerical derivative seam, не JAX regression run. |
| P02 | NoFloat sentinel проходит actual closure; zero baseline variance1; partial z остаётся unresolved/non-gating. Selected projection fixture slot0→1, source admission не выполнялась. |
| P03 | Actual resolver выбирает delta, fixed scale2 сохранён; missing route допускает typed delta, unusable evaluator не проходит probe. Не native eval_shape. |
| P04 | Actual random и QMC loops: каждый 101 calls, nominal20/sample mean20; scale2; 100 missing outcomes и 100 zero values. Deterministic sampling seams, не stochastic/QMC qualification. |
| P05 | Actual float32 vector path при x=100000001, y=x−1e8 даёт point0 против Python nominal1. Зафиксирована precision qualification boundary, не native gradient defect. |

[Probe](../04_Проверки/C113_UQP01/probe_uqp01.py) · [diagnostics](../04_Проверки/C113_UQP01/bounded_diagnostics.json) · [команды/логи/exit codes](../04_Проверки/C113_UQP01/commands.json).

## 5. Сохранить и доквалифицировать

**C113-G01.** Сохранить complete binding, intentional callable defaults, typed missing/unknown, настоящий nondifferentiable fallback, частичные outputs и source-reconciliation/candidate-only distinction. Не заменять неизвестную связь guessed coefficient и не выдавать custom numerical shim за JAX. Нужна supported-runtime проверка actual source-bound response→dispatch→persist/load вместе с UQP-02/03 и существующими lane-level fixtures; полного покрытия этих следующих пакетов здесь нет.

**C113-G02.** Explicit float32 nominal vector может отличаться от Python evaluator nominal на границе представимости. P05 документирует конкретный случай; accepted numeric domain/backend settings пока не квалифицированы. Следует согласовать precision в существующем contract и проверить native профиль, не обещая произвольную float64 точность и не объявляя любой rounding product bug.

Native delta/IR imports BLOCKED на `uncertainty.py:287`, node на `store.py:2118`: среда Python3.12.14 вместо declared3.14. JAX/pytest отсутствуют, installs не делались. Actual NumPy/Pydantic и selected unchanged code не заменяют native chain, научную обоснованность выбранной модели и coverage её uncertainty.

[Исходная карточка](../05_Источники/UQP-01_исходные_строки.txt) · [pinned sources](../05_Источники/C113_источники.json) · [остатки](../01_Реестры/C113_остатки.json) · [границы](../04_Проверки/C113_UQP01/Чтение_и_границы.md).

**113/127 — промежуточный аудит. Следующий UQP-02. Фаза заданий исполнителю не начата.**
