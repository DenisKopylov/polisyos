# econ pack

`econ` это минимальный demo-pack для проверки conflict resolution в IR discovery.

## Что внутри

- 1 компонент: `econ.ir.registry_fragment@1.0.0`
- Файл с экспортом: `components.py` -> `__polisyos_components__`
- Реализация: `ir_fragments.py`

## Роль в системе

Пакет намеренно добавляет альтернативный `UnitsFragment` в namespace `roads`:
- unit id: `roads.kmh`
- fragment id: `econ.fragment.units`
- priority: `90`

Это сделано для тестового конфликта с `roads.ir.registry_fragment@1.0.0` (priority `100`).

## Где используется

- entry point group `polisyos.ir_fragments` в `policy-engine/pyproject.toml`
- dev scan (`discover_components(..., include_dev_scan=True)`)
- тесты `policy-engine/tests/test_packs_discovery.py`

## Ограничение

`econ` не является production-доменом и не содержит полноценной цепочки компонентов
(Foundry/Scholar/Lex/NormPack provider). Его задача строго диагностическая.
