# CP5 — Causal graph/query и исправленные shared helpers

**Режим C: один последовательный выбранный набор, другие test/build/install jobs не работают. Код и review продолжаются.**

Исходные сценарии: T20, T21. Их полные тексты сохранены в B source; применяется реальный selected route, не все методы платформы.

Малые panels/SCM; конечные200 ADMG/2400 запросов; ordinary/dedicated DiD и old plan replay; active surgery/law. Сборка unsupported RBC/conditional profiles не имитируется labels.

**Пакеты этой приёмочной области:** [GRF-01](../bundles/GRF-01.md), [GRF-02](../bundles/GRF-02.md), [GRF-03](../bundles/GRF-03.md), [API-01](../bundles/API-01.md), [CAU-01](../bundles/CAU-01.md), [CAU-02](../bundles/CAU-02.md), [CAU-03](../bundles/CAU-03.md), [CAU-04](../bundles/CAU-04.md), [CAU-05](../bundles/CAU-05.md), [SCM-01](../bundles/SCM-01.md), [SCM-02](../bundles/SCM-02.md), [SCM-03](../bundles/SCM-03.md). Не все они являются prerequisite одного частичного сценария.

Сначала выполнить необходимые маленькие N seam checks при готовности конкретного patch. В окне объединять общий import/setup, но не менять identities/precision/seed ради сравнения. Re-run только failed/affected tests после исправления, не всё окно автоматически. Deferred capabilities остаются явно непроверенными; успешный partial route не означает полной platform readiness.

