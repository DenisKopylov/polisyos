# Trace (Система логирования и трассировки)

Span-based трассировка с поддержкой распределенного трекинга, provenance через артефактные ссылки и структурированное логирование.

## Архитектура

```
trace/
├── record.py     # TraceRecord - записи с метаданными
├── sink.py       # TraceSink - интерфейс вывода (JsonlTraceSink)
└── __init__.py   # Экспорт компонентов
```

## Компоненты

- **TraceRecord**: Запись с метаданными (timestamps, span_id, parent_span_id, артефактные ссылки, метрики, warnings, errors)
- **TraceSink**: Протокол вывода записей. Реализация: `JsonlTraceSink` для JSONL формата

## Формат трассировки

JSONL с полями: `ts`, `run_id`, `phase`, `event`, `span_id`, `parent_span_id`, `refs`, `metrics`, `warnings`, `errors`

## Использование

- **RunContext**: `ctx.emit(phase, event, metrics={}, inputs=[], outputs=[])` записывает в JSONL
- **Span-based**: Иерархическая структура с span_id/parent_span_id для distributed tracking
- **Интеграция**: Fabric, Foundry, Scientist для provenance через артефактные ссылки

## Анализ трассировки

Функции: `load_trace_records()`, анализ производительности, поиск ошибок, реконструкция последовательности.

## Кастомные реализации

- `RotatingTraceSink`: Ротация файлов
- `DatabaseTraceSink`: Сохранение в БД
- `AsyncJsonlTraceSink`: Асинхронная запись

## Производительность

- **Overhead**: <0.1ms на операцию
- **Формат**: JSONL для потоковой обработки
- **Масштаб**: Миллионы записей

## Лучшие практики

- Описательные phase/event имена
- Метрики производительности
- span_id для иерархий
- Provenance через артефактные ссылки