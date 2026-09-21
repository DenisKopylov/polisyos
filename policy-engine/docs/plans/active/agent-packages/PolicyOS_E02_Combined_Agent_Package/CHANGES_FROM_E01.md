# Изменения E01 → E02

84 прежних ID сохранены;43 новых пакета; всего127. Исходные 225B и57LA не перенумерованы.

## Переназначенные B

| B | E01 | E02 |
|---|---|---|
| B12 | CYC-04 | ACQ-01 |
| B32 | EMP-01 | FRC-01 |
| B120 | CTL-01 | CTL-03 |
| B121 | CTL-01 | CTL-03 |
| B123 | CTL-01 | CTL-03 |
| B147 | OBS-01 | OBS-02 |

Перенос B12 согласует N7 с LA-046; B32 — S10 с LA-051; B120/121/123 — новый state transition перед ask/tell; B147 — actual IO helper после LA-031. Остальные B сохранены у прежних packet IDs.

## Новые и связанные работы

12 migration lanes,21 source/target maps и source-ID closure crosswalk связывают bugfix/extraction/cutover. Shared file conflicts и read impact пересчитаны с proposed destinations и tests. Полные 36 controls и4 поздних amendments передаются нужным агентам.

## Исправление собственного текста плана

В OPT-01 E01 была перевёрнута фраза о Pareto: для максимизации (2,1) **доминирует** (1,1), а не наоборот. В E02 исправлена инструкция/приёмка, исходная B109 сохранена без изменений. Это исправление launch plan, не новая находка PolicyOS.

## Ресурсы и прогресс

> **Историческая запись, не действующая политика.** Следующие значения `14=9+3+2` и `2L или1N/C` сохранены как E01-era history. Они superseded by `E02-ADAPTIVE-ORCHESTRATION-AMENDMENT-20260921` and must not be used for current dispatch, admission, or stop decisions.

14=9+3+2 по умолчанию;12/16 варианты прежние. Test budget не вырос:2L или1N/C. Старые активные K1–K6 переименованы CP1–CP6, sourceK01–36 обозначены LK при планировании. Предыдущий kit сохранён как parent, но запускать нужно только E02. Существующий progress переносится по actual source-ID/commit/evidence, не сбрасывается.
