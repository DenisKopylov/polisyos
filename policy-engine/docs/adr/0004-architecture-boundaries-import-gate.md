# ADR-0004: Architecture Boundaries Import Gate

- **Дата**: 2026-02-03
- **Решение**: Зафиксировать слои платформы как ABI‑границы и ввести обязательную AST‑проверку импортов по матрице зависимостей. Единственный источник правды — `import_policy.toml` + `import_exceptions.toml` + `tools/lint/lint_imports.py`.
- **Контекст**: До этого правила импортов были частично описаны и частично закодированы, что приводило к расхождениям и скрытым циклам. Требуется единый, проверяемый контракт слоёв.

## 1) Слои и ответственность (ABI архитектуры)

- **ir (Contract plane)**: только Pydantic‑модели, enums, контрактные реестры/типы, форматы и миграции контрактов. Импорты только `polisyos.ir.*` и внешние: stdlib + `pydantic` + `typing_extensions`.
- **core (Infrastructure kernel)**: CAS, canonical JSON, refs, trace/observability, стабильные стыки. Импорты: `polisyos.core.*`, `polisyos.ir.*`, опционально `polisyos.common.*`.
- **fabric (Data/world plane)**: артефакты, fact log, материализация, query. Импорты: `polisyos.fabric.*`, `polisyos.core.*`, `polisyos.ir.*`, `polisyos.common.*`.
- **foundry (Compute plane)**: compute над артефактами. Импорты: `polisyos.foundry.*`, `polisyos.core.*`, `polisyos.ir.*`, `polisyos.common.*`.
- **scientist (Control plane)**: оркестрация/workflow/governance. Может импортировать всё нижнее.
- **runtime**: сервисный слой исполнения. Импорты: `polisyos.runtime.*`, `polisyos.core.*`, `polisyos.ir.*`, `polisyos.common.*`.
- **scholar / lex (future)**: сервисные домены, могут импортировать ir/core/fabric/common; используются scientist.

## 2) Dependency‑матрица (в коде)

Матрица является единственным источником правды и хранится в `import_policy.toml`.

## 3) Legacy / _legacy policy

- `polisyos.ir.legacy.*`: deprecated/compat. Допустимы только `polisyos.ir.*` и внешние allowlist (stdlib + `pydantic` + `typing_extensions`). Всё остальное — только через исключение с expiry.
- `polisyos.scientist._legacy.*`: допустимо внутри scientist, но **запрещено импортировать снизу** (из любых модулей вне `polisyos.scientist.*`).

## 4) Правило “только через контракты”

Межмодульное взаимодействие разрешено:
- через IR‑контракты (`polisyos.ir.*`), или
- через CAS‑артефакты/refs (строки/refs), индексируемые Fabric.

## 5) Автоматический импорт‑гейт

AST‑чекер `tools/lint/lint_imports.py` выполняет проверку по матрице, учитывает исключения и падает при новых нарушениях или просроченных исключениях.
