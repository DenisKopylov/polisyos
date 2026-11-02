# E02 packet specifications

This directory contains the 127 packet-level work specifications. Each packet describes its requirements, expected behavior, owners and change boundaries, preservation constraints, and local checks. The cards are the normative units of work; the directory is not an execution-status board.

Start with the [executor instructions](../НАЧАТЬ_ЗДЕСЬ.md), then use the [execution plan](../09_Исполнение/План_исполнения.md) for lane order and concurrency rules. Read the [shared execution and acceptance rules](../00_Общее/Правила_исполнения_и_приёмки.md) and the applicable lane overview under [`03_Интеграция`](../03_Интеграция/). The [127-packet index](../00_Общее/Индекс_127_пакетов.md) is the directory of packet IDs.

For a packet, read its card together with the matching record in [`04_Трассировка`](../04_Трассировка/). The card defines the intended work; the trace record binds requirements and tests to source criteria, shared scenarios, and preserved behavior. Follow exact criterion pointers in those records. Do not infer completion from a card, test name, or prior review alone.

Current assignments, implementation status, evidence, and remaining work live in the single [execution state](../09_Исполнение/Состояние_исполнения.json). Update that state through its designated owner; keep these packet specifications as the source for requirements rather than copying status into them.
