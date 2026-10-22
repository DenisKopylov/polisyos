# Рабочие пакеты: как превращать план в конкретные назначения

Машинный [tasks.json](../tasks.json) содержит стабильные рабочие ID, источник обязательства, результат, зависимости, owner anchors, миграцию, rollback и положительный/отрицательный/removal сигнал. Это проектная схема исполнения, не новый публичный DTO PolicyOS. Детали распределены по документам ниже.

| Поток | Документ | Главная граница |
|---|---|---|
| CAP | [Получение оснований](01-acquisition.md) | Discovery/capture/source-specific effects; использует LIF, не дублирует его |
| LIF | [Жизненный цикл](02-lifecycle.md) | Semantic use, frontier, currentness, durable duty, copies, resources, lineage |
| GYD | [Оставшиеся GY obligations](03-gy.md) | Научные, learning, promotion и producer consumers |
| UI | [Atlas и public surfaces](04-atlas.md) | Truth-preserving пользовательские и machine consumers |
| CNT | [Содержательные основания](05-substantive-foundations.md) | Получение настоящих evidence/config, а не второй runtime |
| DEB | [Классы долгов](06-debt-and-specialist-work.md) | Общий механизм вместо исправления каждого симптома |
| OPS | [Развёртывание](../operations/01-deployment.md) | Commissioned profiles и operational proofs поверх LIF |

## Карточка конкретного назначения

Перед dispatch оркестратор материализует из task ID небольшой handoff: accepted source/tree; оригинальный criterion pointer; конкретный current residual; exact writable files и read-only suppliers; версии native интерфейсов; обязательные companions; один различающий пример; ожидаемые commands и resource owner. Prose anchors в плане не являются разрешением менять всю указанную директорию. Неизвестный путь устанавливается ограниченным read-only census после E02; отсутствующий код нельзя предполагать по названию файла.

Результат writer — законченный owner delta и доказанный местный predicate. Результат composition — actual emitted supplier artifact → actual consumer на общем snapshot. Результат adjudication — решение исходного владельца по исходному обязательству. Эти три результата различаются; интерфейсный fixture не закрывает capability.

Если назначение затрагивает общий DTO/schema/generated family, root выдаёт единственного writer. Consumer workers могут готовить отдельные изменения против зафиксированного интерфейса, но не подменяют producer. Пример: CAP-02 не меняет cursor_store, CAP-04 не реализует Claim lifecycle, OPS не создаёт свой compute ledger, CNT не пишет Fabric admission. Точные приоритеты allocation указаны в manifest и architecture/01.

## Как продолжать при препятствии

1. Проверить реальный current owner и source-qualified evidence; не доверять старому слову blocked.
2. Разделить внутренний недостающий механизм, доступный input, неизвестный внешний факт и настоящий контрактный выбор.
3. Внутреннюю работу выполнить или согласовать lease со своим оркестратором. Для внешнего факта сделать допустимый поиск/connector read/intake и зафиксировать проверенные каналы; отсутствие ответа не доказывает отсутствия факта.
4. Архитектурный выбор оформить с reuse/extend/consolidate/new альтернативами, существующими правилами, миграцией и behavioral discriminator. Не вводить новый enum для обхода вопроса. G даёт feedback по существующему процессу.
5. Продолжать независимые части. Не запускать повторно тот же failing gate без нового source/input/evidence. Не создавать ложную authority из fixture, подписи исполнителя или LLM.

Подробные prompts: [orchestrator](../prompts/orchestrator.md), [writer](../prompts/writer.md), [reviewer](../prompts/reviewer.md), [verification](../prompts/verification.md), [foundation supplier](../prompts/foundation-supplier.md).
