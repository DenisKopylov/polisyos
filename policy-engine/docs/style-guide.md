# Documentation Style Guide

> Канонический стандарт документации PolicyOS.
> Все новые и обновляемые документы должны следовать этим правилам.

---

## Language

- Module READMEs, ADRs, contracts: **Russian** (primary), English technical terms
- Reference docs (auto-generated): **English** (follows code)
- Tutorials and how-to: **Russian**
- Docstrings in code: **English** (для совместимости с mkdocstrings)

---

## Docstring Format

Google-style docstrings. Все публичные классы, функции и модули обязаны иметь docstring.

```python
def compile(spec: PolicySpec, *, backend: str = "jax") -> CompiledGraph:
    """Compile a policy specification into an executable mechanism graph.

    Takes a declarative PolicySpec and produces a CompiledGraph that can be
    executed by the Foundry runtime. Compilation includes validation of
    variable bindings, causal graph acyclicity checks, and backend-specific
    optimizations.

    Args:
        spec: Policy specification containing ProblemFrame, causal graph,
            and intervention definitions.
        backend: Execution backend. One of "jax", "numpy", "symbolic".
            Defaults to "jax".

    Returns:
        CompiledGraph ready for execution via ``execute()``.

    Raises:
        CompilationError: If the spec contains unresolvable variable
            references or cyclic causal dependencies.
        BackendError: If the requested backend is unavailable.

    Example:
        >>> graph = compile(spec, backend="jax")
        >>> result = execute(graph, data=panel)
    """
```

### Правила

- **One-line summary** — первая строка, императив ("Compile a...", не "Compiles a...")
- **Args** — каждый параметр с типом и описанием; многострочные описания с отступом 4 пробела
- **Returns** — что возвращается и когда
- **Raises** — только исключения, которые функция явно бросает
- **Example** — когда использование неочевидно; doctest-совместимый формат
- **Pydantic-модели** — docstring класса описывает назначение модели; поля документируются
  через `Field(description=...)` или в docstring секцией `Attributes:`

```python
class ProblemFrame(BaseModel):
    """Frame defining the policy analysis problem.

    Captures the research question, target population, outcome variables,
    and constraints that scope a policy analysis. Acts as the "Why" in the
    Trinity (ProblemFrame / PolicySpec / ModelSpec) separation.

    Attributes:
        question: Natural-language research question.
        outcome_vars: Variables to measure policy impact on.
        population: Target population scope (geographic, demographic).
        constraints: Hard constraints on feasible interventions.
    """

    model_config = ConfigDict(extra="forbid")

    question: str
    outcome_vars: list[str]
    population: EntityScope
    constraints: list[str] = []
```

---

## Semantic Docstring Quality

Phase 7 требует не только "наличие docstring", но и **содержательное описание публичного API**.
Для user-facing, governance-critical и reference-visible символов docstring должен объяснять
роль объекта в предметной модели, условия корректного использования, границы контракта и связь
с соседними слоями.

### Что запрещено

Placeholder one-liners, которые формально существуют, но не дают контекста:

```python
"""Public core security package API."""
```

```python
def parse_rows(payload: bytes) -> list[Row]:
    """Parse rows helper."""
```

```python
class RoutingState(BaseModel):
    """Routing state data model."""
```

```python
class Registry:
    """Registry implementation."""
```

### Что писать вместо этого

#### Module / package facade

```python
"""Expose tenant-security contracts through a lazy package facade.

`polisyos.core.security` is the stable authorization boundary for runtime
services and control-plane tooling. Exports stay lazy so docs and CLI bootstrap
paths can inspect auth contracts without eagerly initializing OPA, TEE, or
storage backends.

Treat names in `__all__` as the supported public surface; non-exported helpers
remain module-private.
"""
```

#### Class / Pydantic model

```python
class RoutingState(BaseModel):
    """Track cursor ownership for collaborative review sessions.

    The state is persisted per `(run_id, artifact_ref)` pair and must be updated
    atomically with lock ownership checks so stale clients cannot overwrite a
    newer cursor. Runtime HTTP review routes serialize this model directly.

    Attributes:
        cursor_token: Opaque cursor identifier issued by the active reviewer.
        updated_at: UTC timestamp of the latest successful cursor write.
    """

    cursor_token: str
    updated_at: datetime
```

#### Function / method

```python
def parse_rows(payload: bytes, *, source_name: str) -> list[Row]:
    """Parse a connector payload into canonical row objects.

    Use this parser for trusted source adapters that already passed transport
    validation. The function normalizes field order and rejects malformed row
    envelopes instead of silently dropping records.

    Args:
        payload: Raw UTF-8 encoded payload returned by the connector backend.
        source_name: Human-readable source label used in validation errors.

    Returns:
        Canonical row objects ready for persistence into the world fact log.

    Raises:
        ValueError: If the payload is not valid JSON or row envelopes are malformed.
    """
```

### Минимальный semantic checklist

- One-line summary объясняет **роль или действие**, а не повторяет имя символа.
- Для классов/моделей указан lifecycle или инварианты, а не только список полей.
- Для boundary objects явно назван соседний контракт/слой, который их читает или пишет.
- Для публичных функций есть `Args`, `Returns`, `Raises`, а для entrypoints/loaders/compile
  APIs — ещё и `Example`.

- Если API тривиален и реально не заслуживает длинного описания, лучше сделать короткий,
  но предметный summary, чем писать `... helper.`.

### Allowlist / pragma

Автоматический gate: `tools/validation/check_docstring_quality.py`.

Для редких тривиальных wrappers допустимы точечные исключения:

- добавить fully qualified symbol в `tools/validation/docstring_quality_allowlist.txt`;
- или поставить inline pragma рядом с определением:

```python
# docstring-quality: ignore
def passthrough(value: str) -> str:
    """Return the input unchanged."""
    return value
```

Не используйте allowlist для user-facing API, фасадов пакетов, compile/execute/load entrypoints,
governance passes и boundary models.

---

## Docs Reality & Publishability

Documentation должна совпадать с текущей реальностью репозитория, а не с историческими планами.

### Базовые правила

- Не оставляйте repo placeholders в опубликованных docs.
- Не ссылайтесь на удалённые GitHub Actions workflows; используйте только реально существующие
  файлы из `.github/workflows/`.

- Не вставляйте локальные filesystem links (`/Users/...`, `file://...`) в markdown docs.
- Абсолютные ссылки на docs site должны соответствовать `mkdocs.yml:site_url`.
- Внутренние markdown links должны реально резолвиться из текущего дерева `docs/`.

### Автоматическая проверка

CI docs-quality gate запускает:

- `uv run --extra docs python -m mkdocs build --strict`
- `python3 tools/validation/check_docs_accuracy.py --repo-root .`
- `uv run --extra docs python tools/validation/check_docstring_quality.py --repo-root . --allowlist tools/validation/docstring_quality_allowlist.txt`

Semantic coverage gate применяется к top-level public surface (module/class/function exports and
reference-visible symbols). Method-level gaps остаются в отчёте как отдельный second-pass backlog
и не должны скрываться под allowlist без явной причины.

---

## README Freshness Policy

- Любое изменение package facade, рекомендуемого entrypoint, generated/reference artifact location
  или subsystem navigation должно обновлять ближайший `README.md`.

- Каждый package README должен содержать freshness marker:
  - `- Last updated: YYYY-MM-DD`
  - или `- Последнее обновление: YYYY-MM-DD`
- Major subsystem README должен содержать раздел `## Where to Start`.
- Если пакет владеет committed generated artifacts или важными reference docs, README должен явно
  указывать их расположение и каноническую точку входа.

## README Template (per-module)

Каждый модуль в `src/polisyos/` должен иметь `README.md` следующей структуры:

```markdown
# Module Name (`polisyos.module`)

One paragraph: что делает модуль, какую проблему решает.

## Роль в системе

- **Зависит от:** ir, core
- **Используется в:** scientist, runtime
- Краткое описание места в архитектуре.

## Ключевые концепции

- **Concept A** — одно предложение
- **Concept B** — одно предложение
- (3-7 пунктов)

## Public API

Основные экспорты модуля. Подробная документация: `docs/reference/<module>/`

## Where to Start

- Как менять public facade
- Какой файл/директория является канонической точкой входа
- Где искать ближайшие generated/reference artifacts

## Generated / Reference Artifacts

- `<artifact family>` — `<path>` — `<regen command>`

## Текущее состояние

- Last updated: YYYY-MM-DD
```

### Правила

- Заголовок **всегда** включает полный путь модуля: `` `polisyos.lex.batch` ``
- Раздел "Роль в системе" — обязателен, показывает зависимости
- Не дублировать содержимое reference docs — ссылаться на них
- Длина: 50-150 строк (не больше)

---

## ADR Template

Формат Michael Nygard. ADR иммутабельны после принятия — supersede, не редактировать.

```markdown
# ADR-NNNN: Title

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXXX

## Context

Какую проблему решаем? Какие ограничения и требования?

## Decision

Что решили делать? Конкретное техническое решение.

## Consequences

Что стало проще? Что стало сложнее? Какие trade-offs?
```

### Правила

- Нумерация: 4 цифры с ведущими нулями (`0001`, `0092`)
- Файл: `docs/adr/NNNN-kebab-case-title.md`
- Статус `Accepted` — документ заморожен
- Для отмены — новый ADR со статусом, ссылающимся на старый

---

## Markdown Conventions

### Форматирование

- Headers: ATX style (`#`, не underline `===`)
- Code blocks: тройные backticks с идентификатором языка (``python`,``yaml`, ````bash`)
- Links: относительные пути внутри `docs/` (`[Trinity](explanation/trinity.md)`)
- Max line length: soft 100 chars (без hard wrap в параграфах)
- Списки: `-` для unordered, `1.` для ordered
- Emphasis: `**bold**` для ключевых терминов, `` `code` `` для идентификаторов

### Структура файла

```markdown
# Title

> Optional one-line tagline or status note.

---

## Section 1

Content...

## Section 2

Content...
```

- Один `#` заголовок на файл (название документа)
- `---` после вступительного блока (title + tagline)
- Пустая строка до и после каждого заголовка

### Таблицы

Использовать Markdown-таблицы для структурированных данных:

```markdown
| Column A | Column B | Column C |
| -------- | -------- | -------- |
| value    | value    | value    |
```

### Admonitions (MkDocs Material)

```markdown
!!! warning "Важно"
Текст предупреждения.

!!! note
Дополнительная информация.

!!! example
Пример использования.
```

---

## Diataxis Categorization

Каждый документ в `docs/` принадлежит **одному** из четырёх типов.
Не смешивать типы в одном документе.

| Тип             | Папка          | Цель                      | Стиль                                 |
| --------------- | -------------- | ------------------------- | ------------------------------------- |
| **Tutorial**    | `tutorials/`   | Обучение через практику   | "Сделайте X, затем Y, увидите Z"      |
| **How-to**      | `how-to/`      | Решение конкретной задачи | "Чтобы сделать X: шаг 1, 2, 3"        |
| **Reference**   | `reference/`   | Точная, полная справка    | Сухое описание API, параметров, типов |
| **Explanation** | `explanation/` | Понимание контекста       | "Почему X устроен так, а не иначе"    |

### Признаки неправильной категоризации

- Tutorial объясняет "почему" вместо "сделайте" → вынести в Explanation
- Reference содержит пошаговые инструкции → вынести в How-to
- How-to начинается с теории → вынести в Explanation, оставить ссылку
