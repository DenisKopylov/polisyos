# Runtime Tests

Валидация runtime API, управления жизненным циклом runs, артефактов и audit trail.

**Последнее обновление:** 1 февраля 2026
**Уровень:** Runtime Layer (Execution Management)
**Зависимости:** Core artifacts, Path manipulation

## Архитектурный контекст

Runtime layer управляет жизненным циклом execution, artifact persistence и audit trails. Тесты валидируют path resolution, manifest management и artifact logging.

## Структура тестов

```
runtime/
└── test_runtime_manifest_paths.py # Управление runs, артефакты, пути
```

## Категории тестов

### Runtime Manifest Paths (`test_runtime_manifest_paths.py`)

**Цель:** Валидация управления относительными/абсолютными путями в манифестах с portability guarantees.

**Ключевые тесты:**
- **Relative Path Logging**: Использование относительных путей для artifact portability
- **Path Resolution**: Корректное разрешение путей для разных типов артефактов
- **Directory Portability**: Переносимость каталогов без потери доступа к артефактам
- **Manifest Integrity**: Корректность run manifest с метаданными и артефактами

**Принципы:**
- **Relative Paths**: Относительные пути для portability между окружениями
- **Path Resolution**: Универсальный механизм разрешения artifact paths
- **Directory Safety**: Safe directory operations и path manipulation
- **Manifest Persistence**: Immutable run manifests с complete provenance

## Запуск тестов

```bash
# Все runtime тесты
pytest tests/runtime/ -v

# Конкретные компоненты
pytest tests/runtime/test_runtime_manifest_paths.py -v
```

## Связи с другими модулями

### Зависимости Runtime Layer

**Core Layer** (`core/`):
- **Artifact Storage**: Интеграция с core artifact system
- **Run Context**: Producer metadata и environment info

### Потребители Runtime Layer

**Все слои системы** используют runtime для:
- **Execution Management**: Run lifecycle и artifact persistence
- **Audit Trails**: JSON Lines logging всех operations
- **Path Resolution**: Portable artifact access

### Архитектурные инварианты

- **Audit Trail**: JSON Lines логирование всех операций с timestamps
- **Portable Paths**: Относительные пути для environment independence
- **Run Manifest**: Паспорт эксперимента с reproducible seeds
- **Artifact Provenance**: Complete tracking всех generated artifacts

## Разработка и расширение

### Добавление новых runtime тестов

1. Тестируйте path resolution в разных scenarios
2. Проверяйте directory portability через moves/renames
3. Валидируйте manifest integrity и completeness
4. Тестируйте artifact logging и retrieval

### Структура runtime теста

```python
def test_artifact_path_resolution(tmp_path: Path):
    # Setup: create run и log artifact
    base_dir = tmp_path / "runs"
    run = start_run(run_id="test_run", base_dir=base_dir)
    artifact_ref = log_artifact(run.run_id, "test", payload, base_dir)

    # Execute: resolve path
    resolved_path = resolve_artifact_path(artifact_ref, base_dir)

    # Verify: check correctness
    assert resolved_path.exists()
    validate_path_properties(resolved_path)
```

## Troubleshooting

### Распространенные проблемы

**Path resolution failures:**
```bash
# Проверьте relative/absolute path handling
pytest tests/runtime/test_runtime_manifest_paths.py::test_resolve_artifact_path_handles_relative_and_absolute -v
```

**Directory portability issues:**
```bash
# Проверьте path resolution после directory moves
pytest tests/runtime/test_runtime_manifest_paths.py::test_log_artifact_uses_relative_paths -v
```

## Технологии и зависимости

### Core Dependencies
- **Path Manipulation**: Python pathlib для portable path handling
- **JSON Persistence**: Structured artifact и manifest storage
- **Directory Operations**: Safe file system operations

### Runtime Infrastructure
- **Run Lifecycle**: Complete execution management
- **Artifact Logging**: Structured artifact persistence
- **Audit Trails**: Comprehensive operation logging
- **Path Resolution**: Environment-independent path handling