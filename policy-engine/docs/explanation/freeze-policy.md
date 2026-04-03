# Architecture Freeze & Import Gates

## Принцип

Architecture freeze нужен, чтобы рост функциональности не ломал направленный dependency graph.
Он одновременно удерживает package cycles, запрещает несанкционированные cross-layer imports и
фиксирует архитектурный долг как явный backlog, а не как незаметно расползающиеся зависимости.
Source of truth здесь не narrative-диаграммы, а `Import Policy v2` в `import_policy.toml`.

## Правила импорта

Авторитетное правило задаётся в `import_policy.toml`; ниже — сжатая карта основных слоёв.

| Module | May import | Must NOT import |
|---|---|---|
| `common` | `common` | другие `polisyos.*` пакеты |
| `ir` | `ir`, `datasets`, approved externals | `foundry`, `scientist`, `fabric`, `lex`, `runtime` |
| `core` | `core`, `ir`, `common` | продуктовые верхние слои на runtime path |
| `fabric` | `fabric`, `core`, `ir`, `common` | `scientist`, `foundry` |
| `foundry` | `foundry`, `academic`, `core`, `ir`, `common` | `scientist`, `runtime`, `lex`, `fabric` |
| `scientist` | `scientist`, `lex`, `scholar`, `foundry`, `fabric`, `runtime`, `core`, `ir`, `common`, `academic`, `datasets` | private/deep imports без одобренного exception |
| `runtime` | `runtime`, `scientist`, `lex`, `foundry`, `fabric`, `core`, `ir`, `common` | несвязанные research/batch layers |
| `lex` | `lex`, `batch_common`, `fabric`, `ir`, `core`, `common` | `scientist` / `foundry` без exception |
| `academic` | `academic`, `batch_common`, `ir`, `core`, `common` | `fabric`, `scientist`, `runtime` |
| `datasets` | `datasets`, `batch_common`, `fabric`, `ir`, `core`, `common` | `scientist`, `foundry`, `runtime`, `lex` |

Дополнительно import gate режет:

- package cycles;
- deep imports в чужие internal/private модули;
- legacy import paths;
- внешние зависимости в `ir`, кроме whitelist из policy.

## CI Enforcement

На текущем дереве architecture freeze и import-gate проверки живут не в отдельных legacy workflow,
а в основном CI-контуре плюс ABI gate.

`ci.yml`:

- запускает `lint_imports.py --policy import_policy.toml --exceptions import_exceptions.toml`;
- проверяет Foundry purity (`lint_foundry.py`);
- валидирует Scientist `state_reads` и node version bumps;
- проверяет Scholar imports и connector contracts;
- требует актуальные schema snapshots через `gen_schema.py --check`.

`abi.yml`:

- строит semantic diff между baseline/current ABI snapshots;
- блокирует breaking drift без ожидаемого versioning decision;
- повторно проверяет, что committed snapshots не отстали от кода.

Типичное падение выглядит как один из кодов `ARCH00x`, например:

```text
src/polisyos/foo.py:42 [ARCH004] forbidden deep import: polisyos.bar._private
```

## Exceptions

Исключения допустимы только как временная мера и только при явной ответственности:

- `id`
- `owner`
- `reason`
- `expires`

Технический источник — `import_exceptions.toml`. Человекочитаемый реестр —
`import_exceptions_registry.md`. На текущем срезе TOML содержит 15 активных исключений
(`12` cross-root, `2` external-module, `1` private deep-import), а markdown registry всё ещё
показывает `_no-active-exceptions_`; поэтому при добавлении или продлении exception обновляйте
оба файла, но доверяйте TOML как blocking source of truth.

Политика для exceptions:

- срок жизни не больше 90 дней;
- просроченные записи блокируют merge;
- новый exception должен сопровождаться планом удаления;
- deep-import exceptions считаются отдельным архитектурным долгом и сравниваются с baseline.

## Lazy Import Pattern

Freeze policy не только запрещает лишние импорты, но и поощряет lazy import для тяжёлых модулей
и boundary-sensitive фасадов. На практике в кодовой базе встречаются два основных приёма.

Type-checking-only import:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.scientist.engine.state import ExperimentState
```

Runtime lazy import:

```python
def run_experiment(state=None):
    from polisyos.scientist.workflows.builder import run_selected_workflow
    return run_selected_workflow(state)
```

Пакетные фасады `polisyos.fabric` и `polisyos.runtime` дополнительно используют `__getattr__`,
чтобы не тянуть тяжёлые зависимости на import time и не открывать лишние cross-layer edges.

See also:

- [Architecture](architecture.md)
- [Security Model](security-model.md)
