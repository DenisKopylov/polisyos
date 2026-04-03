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

Основные экспорты модуля. Подробная документация: [Reference →](../../docs/reference/module/)

## Текущее состояние

Последнее обновление: YYYY-MM-DD
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
- Code blocks: тройные backticks с идентификатором языка (````python`, ````yaml`, ````bash`)
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
|----------|----------|----------|
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

| Тип | Папка | Цель | Стиль |
|-----|-------|------|-------|
| **Tutorial** | `tutorials/` | Обучение через практику | "Сделайте X, затем Y, увидите Z" |
| **How-to** | `how-to/` | Решение конкретной задачи | "Чтобы сделать X: шаг 1, 2, 3" |
| **Reference** | `reference/` | Точная, полная справка | Сухое описание API, параметров, типов |
| **Explanation** | `explanation/` | Понимание контекста | "Почему X устроен так, а не иначе" |

### Признаки неправильной категоризации

- Tutorial объясняет "почему" вместо "сделайте" → вынести в Explanation
- Reference содержит пошаговые инструкции → вынести в How-to
- How-to начинается с теории → вынести в Explanation, оставить ссылку
