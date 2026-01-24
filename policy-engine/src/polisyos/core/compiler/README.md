# Compiler Module (Компиляция)

## Обзор

Модуль `compiler` предоставляет структуры данных и утилиты для управления отчетами компиляции и линковки политики PolisyOS. Модуль обеспечивает стандартизированное представление результатов компиляции и их хранение как артефактов системы.

## Архитектура

```
compiler/
└── report.py   # Отчеты компиляции и функции сохранения
```

## Основные компоненты

### CompileReport

Отчет о компиляции политики, содержащий все артефакты и результаты компиляции.

```python
from polisyos.core.compiler.report import CompileReport
from polisyos.core.artifacts.manifest import ArtifactRef

# Успешный отчет компиляции
success_report = CompileReport(
    schema_version="1.0",
    ok=True,
    policy_ref=policy_artifact_ref,
    registry_bundle_ref=registry_bundle_ref,
    link_report_ref=link_report_ref,
    program_graph_ref=program_graph_ref,
    exec_plan_ref=exec_plan_ref,
    slot_layout_ref=slot_layout_ref,
    treasury_plan_ref=treasury_plan_ref,
    notes=["Compilation completed successfully", "Optimization level: aggressive"]
)

# Отчет с ошибками
error_report = CompileReport(
    schema_version="1.0",
    ok=False,
    notes=["Type checking failed", "Undefined variable 'budget_limit'"]
)
```

### Функции сохранения

#### put_compile_report()

Сохранение отчета компиляции как артефакта в CAS.

```python
from polisyos.core.compiler.report import put_compile_report
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.manifest import InputRef

store = FileSystemCAS(Path("/tmp/artifacts"))

# Сохранение отчета компиляции
compile_report_ref = put_compile_report(
    store,
    success_report,
    inputs=[
        InputRef(artifact_id=policy_id, role="source_policy"),
        InputRef(artifact_id=registry_id, role="registry_bundle")
    ]
)

# compile_report_ref.kind == "compiler.compile_report"
# compile_report_ref.media_type == "application/json"
```

#### put_link_report()

Сохранение отчета линковки как артефакта в CAS.

```python
from polisyos.core.compiler.report import put_link_report
from polisyos.ir.linker import LinkReport

# Предполагаем, что LinkReport получен из IR модуля
link_report = LinkReport(...)  # из polisyos.ir.linker

link_report_ref = put_link_report(
    store,
    link_report,
    inputs=[InputRef(artifact_id=program_graph_id, role="input_graph")]
)

# link_report_ref.kind == "compiler.link_report"
# link_report_ref.media_type == "application/json"
```

## Структура CompileReport

### Основные поля

- **schema_version**: Версия схемы отчета (формат "X.Y")
- **ok**: Успешность компиляции (bool)
- **policy_ref**: Ссылка на исходную политику (опционально)
- **registry_bundle_ref**: Ссылка на пакет реестров (опционально)
- **link_report_ref**: Ссылка на отчет линковки (опционально)
- **program_graph_ref**: Ссылка на граф программы (опционально)
- **exec_plan_ref**: Ссылка на план исполнения (опционально)
- **slot_layout_ref**: Ссылка на layout слотов (опционально)
- **treasury_plan_ref**: Ссылка на план treasury (опционально)
- **notes**: Список заметок и сообщений (по умолчанию пустой)

### Статусы компиляции

#### Успешная компиляция
```python
report = CompileReport(
    ok=True,
    program_graph_ref=graph_ref,
    exec_plan_ref=plan_ref,
    notes=["All checks passed", "Performance optimized"]
)
```

#### Компиляция с предупреждениями
```python
report = CompileReport(
    ok=True,
    program_graph_ref=graph_ref,
    notes=["Unused variable detected", "Consider optimizing loop"]
)
```

#### Неудачная компиляция
```python
report = CompileReport(
    ok=False,
    notes=["Syntax error at line 42", "Undefined function 'calculate_risk'"]
)
```

## Рабочий процесс компиляции

### 1. Подготовка входных данных

```python
# Исходная политика и реестры загружены
policy_ref = ArtifactRef(...)  # из scientist или IR
registry_bundle_ref = ArtifactRef(...)  # из registry
```

### 2. Компиляция в IR модуле

```python
# IR модуль компилирует политику
from polisyos.ir.compiler import compile_policy

compile_result = compile_policy(store, policy_ref, registry_bundle_ref)
if not compile_result.ok:
    # Создание отчета об ошибке
    error_report = CompileReport(ok=False, notes=compile_result.errors)
    put_compile_report(store, error_report)
    return
```

### 3. Линковка (опционально)

```python
# IR модуль выполняет линковку
from polisyos.ir.linker import link_program

link_result = link_program(store, compile_result.program_graph_ref)
link_report_ref = put_link_report(store, link_result.report)
```

### 4. Создание финального отчета

```python
# Финальный отчет компиляции
final_report = CompileReport(
    ok=True,
    policy_ref=policy_ref,
    registry_bundle_ref=registry_bundle_ref,
    link_report_ref=link_report_ref,
    program_graph_ref=compile_result.program_graph_ref,
    exec_plan_ref=compile_result.exec_plan_ref,
    notes=["Compilation pipeline completed"]
)

final_report_ref = put_compile_report(store, final_report)
```

## Интеграция с другими модулями

### IR (Intermediate Representation)
- Генерирует CompileReport и LinkReport
- Использует put_compile_report() и put_link_report() для сохранения

### Foundry
- Читает CompileReport для получения program_graph и exec_plan
- Использует ссылки на скомпилированные артефакты

### Scientist
- Оркестрирует процесс компиляции
- Хранит и отслеживает все CompileReport артефакты

### Runtime
- Использует скомпилированные артефакты из CompileReport для исполнения

## Метаданные и provenance

Каждый отчет компиляции сохраняется с полными метаданными:

```python
# Автоматически добавляется при сохранении
PutOptions(
    kind="compiler.compile_report",
    media_type="application/json",
    schema=SchemaInfo(name="polisyos.core.CompileReport", version="1.0"),
    inputs=[policy_ref, registry_bundle_ref],  # provenance tracking
    producer=ProducerInfo(component="compiler", version="1.0.0")
)
```

## Валидация и типобезопасность

- **extra="forbid"**: Запрет неожиданных полей
- **Проверка версий**: Валидация schema_version по regex
- **Опциональные поля**: Все ссылки на артефакты опциональны для гибкости
- **Строгая типизация**: ArtifactRef для всех ссылок на артефакты

## Примеры использования

### Проверка результатов компиляции

```python
def validate_compilation(store: FileSystemCAS, report_ref: ArtifactRef) -> bool:
    report = store.get_json(report_ref.artifact_id, CompileReport)

    if not report.ok:
        print(f"Compilation failed: {report.notes}")
        return False

    # Проверка наличия необходимых артефактов
    required_refs = [
        report.program_graph_ref,
        report.exec_plan_ref,
        report.registry_bundle_ref
    ]

    if any(ref is None for ref in required_refs):
        print("Missing required compilation artifacts")
        return False

    return True
```

### Агрегация статистики компиляций

```python
def analyze_compilation_stats(store: FileSystemCAS, report_refs: list[ArtifactRef]) -> dict:
    stats = {"total": 0, "successful": 0, "failed": 0, "errors": []}

    for ref in report_refs:
        report = store.get_json(ref.artifact_id, CompileReport)
        stats["total"] += 1

        if report.ok:
            stats["successful"] += 1
        else:
            stats["failed"] += 1
            stats["errors"].extend(report.notes)

    return stats
```

## Производительность

- **Хранение**: Отчеты сохраняются как JSON артефакты с дедупликацией
- **Доступ**: Быстрое чтение через CAS с кешированием
- **Валидация**: Типобезопасность без runtime overhead
- **Масштабируемость**: Поддержка тысяч отчетов компиляции

## Лучшие практики

1. **Всегда проверяйте ok**: Не используйте результаты неудачной компиляции
2. **Сохраняйте provenance**: Указывайте все входные артефакты в inputs
3. **Добавляйте заметки**: Документируйте важные события и решения
4. **Валидируйте ссылки**: Проверяйте наличие необходимых артефактов
5. **Версионируйте схемы**: Используйте семантическое версионирование