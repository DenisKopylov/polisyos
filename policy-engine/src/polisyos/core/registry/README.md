# Registry (Реестры компонентов)

Инфраструктура управления реестрами: механизмы, метрики, ограничения, правила объединения. Централизованное версионирование как CAS артефакты.

## Архитектура

```
registry/
├── builder.py     # Сборка реестров из IR
├── loader.py      # Загрузка и десериализация
└── __init__.py    # Экспорт функций
```

## Типы реестров

- SlotRegistry, MechanismTypeRegistry, MetricRegistry, ConstraintRegistry
- MergeRuleRegistry, SelectorFieldRegistry, UnitsRegistry, TrustRegistry
- PredicateRegistry, PrivacyRegistry

## Основные функции

- **build_default_registry_bundle()**: Стандартный пакет реестров из IR
- **build_registry_bundle()**: Кастомный пакет с указанными реестрами
- **load_registry_bundle()**: Загрузка ссылок на реестры
- **load_registry_bundle_content()**: Загрузка полных объектов реестров

## Структуры данных

- **RegistryBundlePayload**: Ссылки на реестры (обязательные: slot, merge, constraint, mechanism)
- **RegistryBundle**: Payload + ссылка на пакет
- **RegistryBundleContent**: Загруженные объекты реестров

## Рабочий процесс

1. Сборка: `build_default_registry_bundle()` или `build_registry_bundle()`
2. Сохранение: `bundle.save(store)` как артефакт
3. Загрузка: `load_registry_bundle_content()` для компиляции политик

## Интеграция

- **IR**: Определения реестров для сборки
- **Foundry**: Загрузка для валидации и исполнения
- **Scientist**: Управление версиями в экспериментах
- **Compiler**: Ссылки в CompileReport

## Хранение и версионирование

CAS артефакты с schema versioning. Новые версии = новые артефакты.

## Примеры

### Кастомный реестр

```python
# Сборка с кастомным MechanismTypeRegistry
bundle = build_registry_bundle(store, custom_mechanism_registry)
bundle_ref = bundle.save(store)
```

### Валидация

```python
# Проверка обязательных реестров
content = load_registry_bundle_content(store, bundle_ref)
assert content.slot_registry is not None
assert content.mechanism_registry is not None
```

## Производительность

Ленивая загрузка, CAS кеширование, дедупликация. Использует dataclasses.

## Лучшие практики

- Стандартные реестры для совместимости
- Версионируйте изменения
- Валидируйте перед использованием
- Тестируйте совместимость версий

## Отладка

```python
# Проверка содержимого
inspect_registry(bundle_content)
```