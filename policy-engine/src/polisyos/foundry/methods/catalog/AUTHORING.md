# Foundry V2 Authoring Guide

`methods/catalog` является единственным источником истины для новых Foundry methods.

## Где создавать новый метод

- Реализацию добавляй только в `polisyos.foundry.methods.catalog.<domain>`.
- Для публичного flat API используй пакетный `__init__.py` домена.
- Не добавляй новые deep import paths в `polisyos.foundry.methods.<domain>.<module>` и не возвращай shim-модули.

## Обязательные требования к V2 методу

- FQN должен следовать канону `domain.family.variant@semver`.
- `MethodSignature.family` должен описывать stable family surface.
- `MethodSignature.variant` должен описывать конкретный estimator/runtime variant.
- `MethodSignature.kind` обязан быть одним из `pure`, `mechanism`, `simulation`.
- `MethodSignature.execution_backend` должен описывать реальный способ исполнения.
- `MethodSignature.data_modalities` должен отражать фактический тип данных, а не маркетинговый тег.
- Каждый non-scalar slot обязан иметь заполненный `shape`.

## Когда variant должен быть отдельным методом

Вариант оформляется как отдельный method, если меняется хотя бы одно из:

- ABI входов или выходов;
- diagnostics или uncertainty surface;
- execution backend;
- assumptions;
- fallback behavior.

Если меняется только внутренняя эвристика без смены ABI и diagnostics, это должен быть параметр, а не новый method.

## Metadata и capability truth

- `required_deps` перечисляет зависимости, без которых метод нельзя честно объявить runnable.
- `optional_deps` используются только для деградации качества, diagnostics или удобных extras.
- `determinism_tier`, `fallback_policy` и `side_effect_profile` должны быть заданы явно.
- Не кодируй deprecation через теги у канонического entry.

## Регистрация

- Добавляй новый метод в `_registry_boot.py` только один раз.
- Не регистрируй aggregate wrappers как first-class entries.
- Если family расширяется variant-ами, регистрируй именно variant methods.

## Проверка перед merge

- Запускай snapshot tests и contract tests для каталога.
- Убедись, что метод появляется в `schema_version=2.0` snapshot с правдивыми `runnable`, `dependency_posture` и `capability_matrix`.
- Убедись, что scientist selection видит family/variant и предлагает метод как canonical alternative.
