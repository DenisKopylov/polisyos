# ir.linker

`ir.linker` связывает `TrinityBundle` с `RegistryBundle` и возвращает:

- `LinkedTrinityBundle` (bundle + bindings + digests);
- `LinkReport` (typed issues/warnings/notes).

## Основной API

```python
from polisyos.ir.linker import link_trinity
```

`link_trinity(bundle, registries, allow_extra_params=False, strict=True)`.

## Что валидирует линкер

1. Интервенции `PolicySpec`:
   - existence механизмов;
   - параметры (required/type/range/enum/unit);
   - reads/writes slots (включая `adaptive_agent` resolution);
   - selector fields и единый selector scope.
2. `ProblemFrame`:
   - objectives/KPI против `MetricRegistry`;
   - unit consistency для metric/KPI/constraints.
3. Constraints:
   - existence constraint specs;
   - slot existence;
   - unit compatibility (money/rate и scalar fallback).
4. Merge/schedule:
   - overlap writers по slot;
   - merge rule compatibility по `SlotValueType`;
   - проверки `priority`/`error` поведения.

## Состав директории

| Файл | Назначение |
|---|---|
| `link_trinity.py` | публичный фасад линкера |
| `_trinity_linker.py` | основной pipeline линковки |
| `_trinity_params.py` | валидация параметров и unit compatibility |
| `_trinity_mechanisms.py` | slots/selectors/constraints/schedule conflict checks |
| `_trinity_models.py` | `LinkedIntervention`, `TrinityBindings`, `LinkedTrinityBundle` |
| `reports.py` | `LinkIssueCode`, `LinkIssue`, `LinkReport`, severity |
| `types.py` | `validate_norm_applicability_refs()` |

## Поведение `strict`

- `strict=True`: отсутствие нужного реестра (`units/slots/mechanisms/...`) даёт `MISSING_REGISTRY` error.
- `strict=False`: часть missing-registry проверок подавляется.

## Где используется

| Директория | Использование |
|---|---|
| `core/compiler` | сериализация и передача `LinkReport` |
| `foundry` | pre-execution контрактная проверка Trinity |
| `scientist` | governance preflight/validation |
