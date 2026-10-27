# G: CAN-01 и TC-01 — решения для реализации

Дата: 2026-10-27. Статус: **архитектурный выбор G для реализации**. Это не приёмка source, не результат runtime wave и не adjudication findings: `code_acceptance=false`, `closure_ids=[]`. Изменяется только документация.

Вход — [пакет исполнителя @757e407b](https://github.com/DenisKopylov/polisyos/blob/757e407bba28da5f1995335350bf7c427ecce431/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/g-questions/implementation-choices-20261027/README.md). Анализ source привязан к `7a4c713186188f5795da3a8745e42843443dcd88`, tree `f49503f969b9a3d68bf82d23e0c8435e9d20c847`; собственная база G — `978921662b2d89006759cdd2ae96dbccc9bdcf11`. Изменения coding-agent после этого source требуют delta review. [Inputs](inputs.json) фиксирует происхождение и границы свидетельств.

## Два выбора и обязательное следствие

| Вопрос | Выбор | Что не выбирается |
|---|---|---|
| CAN-01 | **A: versioned lossless mapping escape**, `polisyos.canon.json@0.3.0`. Любой обычный map с точным ключом `_type` сохраняется как map. Native values / внутренние descriptor values имеют отдельное представление. `.2` остаётся неизменным. | Постоянный запрет таких словарей; escape только сегодняшних tag names; молчаливое изменение `.2`; переход на другую serialization platform. |
| TC-01 | **Существующий `TemporalScope` как явно выбранный request cursor**: `valid_at`, `tx_at`, `branch`, `snapshot_id`, `scenario_id`. Отдельные policy/data/legal/source/publication time roles сохраняются у своих owners. | Универсальный обязательный bundle всех времён; подстановка `now`, LLM date или `context.as_of`; глобальное требование сразу обеих временных осей. |
| Следствие TC-01 | **Versioned SameInputClosure с полным selected-view identity**, проверяемый существующим runtime-quality owner. Для каждого CAS member — payload ID + kind + media type + точный manifest profile + role, разрешённые и проверенные owner. | Добавление profile только к `time_context_ref`; сравнение голых ID или заявленного hash; превращение символического `runtime-mode:…` в вымышленный CAS ref. |

Главная граница: **сохранённое значение не становится authority, записанный запрос не становится фактом о мире, совпадение input identity не доказывает допустимость вывода**. Lex, producer provenance, purpose, current access и другие предметные барьеры продолжают действовать независимо.

## Документы исполнителю

1. [CAN-01: grammar, native carriers, cache и migration](01-lossless-raw-mappings.md).
2. [TC-01: request semantics и полная цепочка выполнения](02-request-time-context.md).
3. [SameInputClosure: identity, verification и schema rollout](03-exact-view-closure.md).
4. [Последовательность работ, границы writers и acceptance matrix](04-delivery-and-acceptance.md).
5. [Исследование, redteam, самостоятельное review и ограничения](05-research-and-review.md).

Это расширяет уже выбранные [AD-E02-05](../architecture-decisions-2026-10-21/05-canonical-profile-and-context.md) и [IR-Q2](../architecture-decisions-2026-10-23/02-ir-version-compatibility.md), не переоткрывая shared-mechanics/Core-vs-IR separation. Изменения `system-design-decisions` не требуются.

CAN и TC можно реализовывать параллельно на разных owners. TC не обязан ждать CAN `.3`: собственный scope payload может использовать уже принятый точный профиль `.2`. Пересечение находится в Core manifest/profile contracts; там один canonical writer и согласованный небольшой companion. Включение writers зависит от готовности **их реальных readers**, а не от миграции всего репозитория сразу.

## Что установлено, а что ещё предстоит

Прочитаны и сверены все записи ограниченных source readsets пакета: 13 TimeContext pins и 22 CAN current-source pins; все 10 записей `evidence_readset` совпали по SHA-256. Это полные множества **этих manifest arrays**, не repo-wide census. Шесть прямых помощников исследовали owners, первичные источники и контрпримеры. G самостоятельно проверил ключевые места source и окончательные решения.

Runtime/tests/imports/builds/install не запускались. Старые prototypes сохраняют исходную source qualification; временный CAS compatibility check не является ordinary POST proof. Same-ID/different-profile witness относится к сравнению closure, а не доказывает опубликованный authority escape. Новые acceptance cases — задания будущей реализации, пока `UNRUN`.

Pattern pass: P01/P02/P03 — завершить producer→artifact→bridge→consumer→surface; P05/P15 — candidate и authority отдельно; P07/P08 — versioned replay и разные time roles; P27/P31 — расширить владельцев, закрыть класс; P29/P32/P37/P38 — реальные readback и falsifiers вместо маркеров; P40/P41 — не превращать новый escape в бесконечную лестницу локальных исправлений или чужую непроверенную красноту.
