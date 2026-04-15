# Управление schema snapshots

Related reference: [Schemas](../reference/schemas.md). Related explanation: [IR Design](../explanation/ir-design.md).

> Эта страница для инженеров, которые меняют публичные IR/runtime контракты и должны сохранить ABI discipline, а не просто "перегенерировать JSON".

В репозитории сейчас есть два важных schema surface:

- ABI snapshots в `schemas/snapshots/**`, которые собираются через `tools/diagnostics/gen_schema.py`;
- runtime OpenAPI snapshot `schemas/runtime_api_v1.openapi.json`, который экспортируется через `tools/runtime/export_runtime_openapi.py`.

## 1. Когда менять snapshots

Запускайте schema flow, если вы:

- изменили публичную Pydantic модель или Enum, входящую в ABI registry;
- добавили новый IR/fabric контракт;
- изменили Runtime API request/response surface;
- меняете generated runtime client.

Если правка внутреннего helper-а не меняет публичный contract shape, snapshot update обычно не нужен.

## 2. Проверьте ABI drift без записи

Базовая локальная проверка:

```bash
PYTHONPATH=src:. uv run --extra ml python tools/diagnostics/gen_schema.py --check
```

Если snapshot не совпадает с кодом, скрипт завершится ошибкой и покажет out-of-date файлы.

Для точечной проверки подмножества моделей:

```bash
PYTHONPATH=src:. uv run --extra ml python tools/diagnostics/gen_schema.py --check --models claim p0 ir
```

## 3. Перегенерируйте ABI snapshots

Когда изменение осознанное:

```bash
PYTHONPATH=src:. uv run --extra ml python tools/diagnostics/gen_schema.py
```

Что обновляется:

- `schemas/snapshots/<module>/*.schema.json`
- `_manifest.json` для соответствующего snapshot bundle
- `docs/reference/ir/schema-catalog.md`
- `docs/reference/schemas.md`

Полезное правило: смотрите не только на diff JSON, но и на semantic intent изменения. Snapshot update без понятного contract story почти всегда плохой знак.

## 4. Проверьте runtime OpenAPI snapshot

Runtime contract живёт отдельно:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
```

Если вы меняли HTTP routes или DTO, после экспорта обычно нужно ещё обновить generated client:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/generate_runtime_client.py --openapi schemas/runtime_api_v1.openapi.json --out-ts frontend/runtime-api-client/runtimeApiClient.ts --out-js frontend/runtime-api-client/runtimeApiClient.js
```

## 5. Как думать про drift

Полезно разделять три случая:

- additive drift: добавлено новое поле/модель с совместимой историей;
- breaking drift: удаление/переименование/смена типа поля;
- accidental drift: код поменялся, а contract story не задуман.

Первый случай обычно acceptable при правильном report/ADR. Второй требует явного compatibility decision. Третий лучше ловить и откатывать сразу.

## 6. Compatibility decision перед snapshot update

Перед тем как принимать schema drift, задайте тот же вопрос, который будет
использовать release review:

```python
from polisyos.ir.migrations import negotiate_schema_version

decision = negotiate_schema_version(
    "article_extraction_result",
    producer_version="1.0",
    consumer_version="1.5",
)
assert decision.can_read
```

IR registry использует четыре режима:

- `FULL`: прямое чтение обещано в обе стороны в объявленной совместимой линии.
- `BACKWARD`: новый consumer читает старый producer payload.
- `FORWARD`: старый consumer читает объявленный новый producer payload.
- `NONE`: прямое чтение не обещано; нужен migration edge или отказ.

Изменения классифицируются так:

- additive optional fields обычно `BACKWARD`, если старый payload валиден у
  нового reader без silent defaults loss;
- field removal и rename не считаются совместимыми сами по себе, им нужен
  explicit dual-read alias или migration;
- canonical defaults должны быть записаны в compatibility rule, если reader
  проставляет или нормализует отсутствующее поле;
- unknown canonical `_type` не является compatibility escape hatch и
  fail-closed по ADR-0104.

## 7. Что смотреть в PR

Когда вы ревьюите schema-related PR, проверьте:

- понятна ли причина contract change;
- обновлены ли и ABI snapshots, и OpenAPI/client, если менялся runtime surface;
- не затронуты ли unrelated snapshot bundles;
- соответствуют ли docs/reference страницы новой форме контракта.
- есть ли compatibility rule или ADR для producer/consumer mismatch.

## 8. Минимальный рабочий набор перед merge

```bash
PYTHONPATH=src:. uv run --extra ml python tools/diagnostics/gen_schema.py --check
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py
uv run --extra docs python -m mkdocs build --strict
uv run --extra docs python tools/validation/check_docstring_quality.py --repo-root . --allowlist tools/validation/docstring_quality_allowlist.txt
```

## Что дальше

- Для каталога текущих snapshots смотрите [Schemas reference](../reference/schemas.md)
- Для полного generated inventory всех IR types и fields смотрите [IR Schema Catalog](../reference/ir/schema-catalog.md)
- Для runtime contract tooling откройте `tools/runtime/README.md`
- Для ABI tooling откройте `tools/diagnostics/README.md`
