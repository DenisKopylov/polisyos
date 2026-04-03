# IR Design

Related reference: [IR](../reference/ir/index.md). Related explanation: [Architecture](architecture.md).

IR в PolicyOS существует не потому, что "так красивее типизировать модели", а потому что системе нужен стабильный boundary между слоями, которые меняются с разной скоростью и принадлежат разным operational concerns.

## Что отделяет IR

IR сидит между четырьмя крупными зонами:

- Fabric приносит данные и provenance;
- Lex приносит normative и legal artifacts;
- Foundry компилирует и исполняет механизмы;
- Scientist оркестрирует workflow, governance и review.

Если эти слои начинают обмениваться ad hoc Python-объектами, контракт быстро расползается:

- невозможно стабильно снапшотить ABI;
- runtime/debug tooling перестаёт понимать, какой artifact должен существовать;
- governance становится зависимым от внутренней формы конкретного модуля, а не от согласованного boundary object.

IR решает именно эту проблему.

## Почему IR не встроен в Foundry или Scientist

Foundry и Scientist выполняют разные роли.

- Foundry отвечает за compile/execute semantics и numerical/runtime execution.
- Scientist отвечает за orchestration, node graph, governance passes и review loops.

Если положить canonical problem/policy/model contracts внутрь одного из них, второй слой станет зависеть от чужой внутренней семантики. В результате:

- Foundry начнёт диктовать форму planning/governance surface;
- Scientist начнёт диктовать compile inputs и execution bundles;
- runtime/debug/reference pages потеряют единый источник истины.

IR поэтому живёт отдельно и принадлежит не одному subsystem owner, а contract boundary проекта.

## Trinity как пример boundary design

`ProblemFrame`, `PolicySpec` и `ModelSpec` разделяют разные вопросы:

- `ProblemFrame` отвечает за "почему мы вообще решаем эту задачу";
- `PolicySpec` описывает "что именно предлагается изменить";
- `ModelSpec` фиксирует "какую world/model surface мы считаем исполнимой".

Это не просто удобная декомпозиция. Она позволяет:

- Fabric и Lex обогащать контекст, не ломая compile path;
- Scientist планировать workflow вокруг тех же артефактов, которые потом идут в Foundry;
- governance и review layers reason about the same boundary objects, а не о transient runtime state.

## ABI boundary и snapshots

IR design тесно связан с ABI discipline.

Публичные IR модели:

- экспортируются через facade;
- документируются в reference pages;
- снапшотятся в `schemas/snapshots/ir/`;
- участвуют в compatibility checks через `gen_schema.py`.

Это делает IR не "внутренним слоем моделей", а versioned contract surface. Именно поэтому изменения в IR должны проходить через schema review и docs/reference review, а не только через unit tests.

## Bundle lifecycle

Большинство серьёзных IR объектов живут не как одиночные структуры, а как lifecycle bundle:

1. создаются или собираются из upstream layer;
2. сериализуются в CAS;
3. читаются downstream subsystem-ом по artifact ref;
4. участвуют в governance, debug и replay surfaces;
5. остаются audit-friendly после завершения run.

Это особенно важно для:

- `TrinityBundle`
- observation contracts and manifests
- NormPack-adjacent artifacts
- uncertainty / backtest / decision bundles

IR therefore optimizes for durable exchange and replayability, not for in-memory convenience.

## Что IR сознательно не делает

IR не должен:

- знать про transport specifics connector-ов;
- содержать orchestration-specific mutable run state;
- тянуть на себя Foundry executor internals;
- быть заменой runtime DTO layer.

Runtime request/response contracts могут ссылаться на IR artifacts, но не должны размывать границу между HTTP transport и canonical domain objects.

## Связь с соседними слоями

- Fabric пишет data/evidence artifacts, которые потом связываются с IR manifests и snapshot refs.
- Lex компилирует legal structure в `NormPack` и intervention-facing IR objects.
- Foundry читает compile/execute contracts, не зная о том, как именно они были собраны Scientist или Fabric.
- Scientist использует IR как shared language между planning, governance, execution и replay.

Именно это делает IR "architectural seam" проекта, а не просто каталогом Pydantic классов.
