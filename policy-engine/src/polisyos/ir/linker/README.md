# ir.linker

`ir.linker` связывает `TrinityBundle` с `RegistryBundle` и возвращает:

- `LinkedTrinityBundle` (bundle + bindings + digests);
- `LinkReport` (typed issues + notes).

## Основной API

```python
from polisyos.ir.linker import link_trinity
```

`link_trinity(bundle, registries, allow_extra_params=False, strict=True)`.

## Что валидирует линкер

1. Интервенции `PolicySpec`:
   - существование механизмов;
   - параметры (`required/type/range/enum/unit`);
   - read/write slots (включая динамическое `adaptive_agent` resolution);
   - selector fields и единый selector scope.
2. `ProblemFrame`:
   - objectives/KPI против `MetricRegistry`;
   - unit consistency для metrics/KPI/constraints.
3. Constraints:
   - существование constraint specs;
   - существование slot-ов;
   - unit compatibility (включая money/rate проверки).
4. Merge/schedule:
   - пересечения writers по slot;
   - совместимость merge-rule и `SlotValueType`;
   - проверки поведения `priority`/`error`.

Дополнительно `types.py` предоставляет `validate_norm_applicability_refs()` для проверки actor/concept/jurisdiction ссылок.

## Состав директории

| Файл | Назначение |
|---|---|
| `link_trinity.py` | публичный фасад линкера |
| `_trinity_linker.py` | основной pipeline линковки |
| `_trinity_params.py` | валидация параметров и unit compatibility |
| `_trinity_mechanisms.py` | slots/selectors/constraints/schedule checks |
| `_trinity_models.py` | `LinkedIntervention`, `TrinityBindings`, `LinkedTrinityBundle` |
| `reports.py` | `LinkIssueCode`, `LinkIssue`, `LinkReport`, severity |
| `types.py` | `validate_norm_applicability_refs()` |

## Поведение `strict`

- `strict=True`: отсутствие нужного registry (`units/slots/mechanisms/...`) даёт `MISSING_REGISTRY` error.
- `strict=False`: часть missing-registry проверок подавляется.

## Особенности

- `LinkReport.ok` становится `False`, если есть хотя бы один `ERROR`.
- `LinkSeverity`: `error`, `warning`, `info`.
- Линкер формирует `registry_digest` и `bundle_digest` через canonical hash; при невозможности канонизации добавляет note (`*_digest_unavailable`) и возвращает `None` digest.

## Где используется

| Директория | Использование |
|---|---|
| `core/compiler` | сериализация и передача `LinkReport` |
| `foundry` | pre-execution контрактная проверка Trinity |
| `scientist` | governance preflight/validation |
