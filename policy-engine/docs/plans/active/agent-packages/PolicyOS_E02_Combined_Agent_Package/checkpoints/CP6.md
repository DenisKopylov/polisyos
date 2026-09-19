# CP6 — Итоговая поставка и вывод лишних поверхностей

**Режим C: один последовательный выбранный набор, другие test/build/install jobs не работают. Код и review продолжаются.**

Исходные сценарии: T1, T2, T3. Их полные тексты сохранены в B source; применяется реальный selected route, не все методы платформы.

Фиксированный integration SHA; один последовательный выбранный regression set и второй пользовательский случай. Один wheel/sdist/installed-import inventory для всех принятых moves/removals, один runtime-client generated-family pass с corruption checks. Native/Linux/server/unavailable matrix явно сохранена.

**Пакеты этой приёмочной области:** [HYG-04](../bundles/HYG-04.md), [CLI-01](../bundles/CLI-01.md). Не все они являются prerequisite одного частичного сценария.

Сначала выполнить необходимые маленькие N seam checks при готовности конкретного patch. В окне объединять общий import/setup, но не менять identities/precision/seed ради сравнения. Re-run только failed/affected tests после исправления, не всё окно автоматически. Deferred capabilities остаются явно непроверенными; успешный partial route не означает полной platform readiness.

CP6 завершает общий этап; unknown external support/lifecycle не закрывается одной успешной сборкой. Review проверяет состав retained aliases и отрицательные no-resurrection tests.
