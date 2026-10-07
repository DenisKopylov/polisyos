# Foundry Method Lifecycle

`polisyos.foundry.methods.lifecycle` owns lifecycle state, compatibility,
deprecation, monitoring, and observability helpers for method execution.

## Home

- `__init__.py` owns `MethodLifecycle`, `LifecycleLog`, and transition rules.
- `compat.py` and `compat_matrix.py` own ABI compatibility checks.
- `deprecation.py` owns method deprecation and retirement helpers.
- `output_monitor.py`, `observability.py`, and `profiler.py` own operational
  instrumentation.

## Authoring Rules

- Lifecycle state must be deterministic and auditable from registry entries.
- Deprecation changes need a compatibility test and a documented removal path.
- Monitoring helpers must stay optional when telemetry dependencies are absent.

## Контракт проверки выходов

Dispatcher сверяет объявленные имена выходов с нормализованным
`MethodResult.slot_outputs`. Поддерживаемые raw aliases и диагностические
sidecars доступны в `MethodResult.output` и не создают ошибок имён slots.
Числовые NaN/Inf в обоих представлениях сохраняют типизированные ошибки
`AnomalyFlag`, предупреждения и передачу в telemetry.

При штатной дематериализации dispatcher прослеживает выбранный raw key в
canonical slot: сначала имя slot, затем aliases в порядке canonical normalizer.
Если выбранный объект дошёл до slot без преобразования, NaN/Inf проверяется один
раз под canonical именем. Это относится и к bare output для единственного slot.
Отдельный raw diagnostic field проверяется независимо, даже если содержит тот
же объект; невыбранный alias при наличии canonical key также остаётся диагностикой.
Так предупреждения и OTel counter считают одну canonical anomaly и каждую
отдельную диагностическую anomaly.

Для custom `dematerialize_output`, копирующего или оборачивающего значения,
соответствие источника не выводится из равенства значений или общей identity
других полей. Оба представления сохраняют проверки; гарантия одного canonical
счётчика относится к штатной дематериализации с сохранением выбранного объекта.

Пустой Python list или tuple без числового dtype может обозначать пустой
набор диагностик. Явно типизированный пустой массив или пустая последовательность
в объявленном vector/matrix/tensor slot сохраняет `empty_array`. Отсутствующий
объявленный slot и неправильная форма массива остаются contract failures при
дематериализации; несовпадающие canonical keys остаются ошибками monitor.
