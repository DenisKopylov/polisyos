# Scientist Tests

Валидация компонентов scientist layer - компилятора политик и ИИ-компонентов.

**Последнее обновление:** Январь 2026
**Уровень:** Scientist Layer (AI & Compilation)
**Зависимости:** JAX, Core artifacts, IR structures

## Архитектурный контекст

Scientist layer обеспечивает компиляцию политик из IR в executable формы и управляет AI-компонентами. Тесты валидируют policy compilation pipeline и integration с ИИ.

## Структура тестов

```
scientist/
└── test_compiler.py           # Компилятор политик из IR
```

## Категории тестов

### Policy Compiler (`test_compiler.py`)

**Цель:** Валидация компиляции IR политик в исполняемые модели foundry.

**Ключевые тесты:**
- **IR to Foundry Compilation**: Полный roundtrip IR → compilation → execution → state update
- **Surface IR Roundtrip**: PolicySurfaceIR → executable program → GlobalState changes
- **Registry Integration**: Корректное использование mechanism/slot/merge registries
- **Execution Correctness**: Валидация что скомпилированные программы работают правильно

**Принципы:**
- **Compilation Pipeline**: IR → executable foundry programs
- **Registry-driven**: Использование centralized registries для compilation
- **Execution Safety**: Compiled programs безопасны для execution
- **State Consistency**: Correct state transformations через execution

## Запуск тестов

```bash
# Все scientist тесты
pytest tests/scientist/ -v

# Конкретные компоненты
pytest tests/scientist/test_compiler.py -v
```

## Связи с другими модулями

### Зависимости Scientist Layer

**IR Layer** (`ir/`):
- **Policy Surface**: Surface IR как input для compilation
- **Semantic Models**: Policy semantics для compilation

**Foundry Layer** (`foundry/`):
- **Execution Engine**: Running скомпилированных программ
- **State Management**: GlobalState updates через execution

**Core Layer** (`core/`):
- **Registry Bundles**: Centralized registries для compilation
- **Artifact Storage**: Persistence compiled programs

### Потребители Scientist Layer

**Integration Layer** (`integration/`):
- **Full Pipeline**: Draft → IR → Compilation → Simulation
- **Workflow Orchestration**: AI-powered policy workflows

### Архитектурные инварианты

- **Закон B**: Компиляторная труба (NL → LLM → IR → Compilation → Runtime)
- **Registry Consistency**: Compilation использует consistent registry bundles
- **Execution Correctness**: Compiled programs preserve policy semantics
- **State Safety**: Safe state transformations через execution

## Разработка и расширение

### Добавление новых scientist тестов

1. Тестируйте compilation для различных типов политик
2. Проверяйте registry integration и consistency
3. Валидируйте execution correctness compiled programs
4. Тестируйте error handling в compilation pipeline

### Структура scientist теста

```python
def test_policy_compilation_roundtrip(tmp_path):
    # Setup: create policy и registries
    policy = create_test_policy()
    registries = load_default_registries(tmp_path)

    # Execute: compile policy
    artifacts = compile_surface_policy(tmp_path, policy, registries)

    # Verify: execute и check results
    state = execute_compiled_program(artifacts)
    validate_policy_effects(state, expected_changes)
```

## Troubleshooting

### Распространенные проблемы

**Compilation failures:**
```bash
# Проверьте registry loading
pytest tests/scientist/test_compiler.py::test_compile_surface_policy_roundtrip_rate -v --tb=long
```

**Execution errors:**
```bash
# Проверьте state consistency
pytest tests/scientist/test_compiler.py -v -s
```

## Технологии и зависимости

### Core Dependencies
- **JAX**: Execution compiled programs
- **Core Artifacts**: Registry bundles и artifact storage
- **IR Structures**: Policy surface для compilation

### Compilation Infrastructure
- **Policy Compiler**: IR → executable transformation
- **Registry Integration**: Centralized configuration management
- **Execution Engine**: Safe program execution
- **State Management**: GlobalState transformation pipeline