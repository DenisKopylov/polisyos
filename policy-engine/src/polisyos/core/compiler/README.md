# Compiler (Отчеты компиляции)

## Обзор

Структуры данных для отчетов компиляции и линковки. `CompileReport` с результатами компиляции, сохранение как артефакты.

## Архитектура

```
compiler/
└── report.py   # CompileReport, put_compile_report, put_link_report
```

## Основные компоненты

### CompileReport

Отчет о компиляции политики с артефактами и результатами.

```python
from polisyos.core.compiler.report import CompileReport

# Успешный отчет
success_report = CompileReport(
    schema_version="1.0",
    ok=True,
    policy_ref=policy_ref,
    program_graph_ref=graph_ref,
    exec_plan_ref=plan_ref,
    notes=["Compilation successful"]
)

# Отчет с ошибками
error_report = CompileReport(
    ok=False,
    notes=["Type checking failed"]
)
```

### Функции сохранения

#### put_compile_report()

```python
from polisyos.core.compiler.report import put_compile_report

compile_report_ref = put_compile_report(
    store,
    success_report,
    inputs=[InputRef(artifact_id=policy_id, role="source_policy")]
)
# kind: "compiler.compile_report"
```

#### put_link_report()

```python
from polisyos.core.compiler.report import put_link_report

link_report_ref = put_link_report(
    store,
    link_report,
    inputs=[InputRef(artifact_id=graph_id, role="input_graph")]
)
# kind: "compiler.link_report"
```

## Структура CompileReport

### Поля
- **schema_version**: Версия схемы ("X.Y")
- **ok**: Успешность компиляции
- **policy_ref**: Исходная политика
- **registry_bundle_ref**: Пакет реестров
- **link_report_ref**: Отчет линковки
- **program_graph_ref**: Граф программы
- **exec_plan_ref**: План исполнения
- **notes**: Заметки и сообщения

### Статусы
- **Успешная**: `ok=True` с артефактами
- **С предупреждениями**: `ok=True` с notes
- **Неудачная**: `ok=False` с ошибками

## Рабочий процесс

1. **Подготовка**: Загрузка политики и реестров
2. **Компиляция**: IR модуль компилирует политику
3. **Линковка**: Создание link report (опционально)
4. **Финальный отчет**: Сохранение CompileReport как артефакт

## Интеграция с модулями

- **IR**: Генерирует CompileReport и LinkReport
- **Foundry**: Читает program_graph и exec_plan
- **Scientist**: Оркестрирует компиляцию, хранит отчеты
- **Runtime**: Использует скомпилированные артефакты

## Метаданные и provenance

Отчеты сохраняются с полными метаданными и provenance tracking через inputs.

## Валидация

- **extra="forbid"**: Запрет неожиданных полей
- **Версии**: Проверка schema_version
- **Типы**: ArtifactRef для всех ссылок

## Примеры

### Проверка компиляции

```python
def validate_compilation(store, report_ref):
    report = store.get_json(report_ref.artifact_id, CompileReport)
    if not report.ok:
        return False
    # Проверка required артефактов
    return all([report.program_graph_ref, report.exec_plan_ref])
```

### Статистика компиляций

```python
def analyze_stats(store, report_refs):
    stats = {"total": 0, "successful": 0, "failed": 0}
    for ref in report_refs:
        report = store.get_json(ref.artifact_id, CompileReport)
        stats["total"] += 1
        stats["successful" if report.ok else "failed"] += 1
    return stats
```

## Производительность

- **Хранение**: JSON артефакты с дедупликацией
- **Доступ**: Быстрое чтение через CAS
- **Масштабируемость**: Тысячи отчетов компиляции

## Лучшие практики

- Проверяйте `ok` перед использованием результатов
- Сохраняйте provenance через inputs
- Добавляйте заметки о важных событиях
- Валидируйте наличие необходимых артефактов
- Версионируйте схемы семантически