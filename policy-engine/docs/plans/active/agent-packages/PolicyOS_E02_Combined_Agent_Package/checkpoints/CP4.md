# CP4 — Calibration model и actual execution

**Режим C: один последовательный выбранный набор, другие test/build/install jobs не работают. Код и review продолжаются.**

Исходные сценарии: T17, T18, T19. Их полные тексты сохранены в B source; применяется реальный selected route, не все методы платформы.

Один механизм,2 старта,2–4 параметра, короткий scan/Hessian/draws. Сохранённые baseline laws/RNG после relocation; один tiny trainer update с actual action influence; FRC bridge только на совместимом estimand. Не статистическая аттестация на всех данных.

**Пакеты этой приёмочной области:** [FRC-02](../bundles/FRC-02.md), [FRY-03](../bundles/FRY-03.md), [ECO-01](../bundles/ECO-01.md), [PLG-01](../bundles/PLG-01.md), [PLG-02](../bundles/PLG-02.md), [PLG-03](../bundles/PLG-03.md), [CAL-05](../bundles/CAL-05.md), [FIT-01](../bundles/FIT-01.md), [CAL-01](../bundles/CAL-01.md), [CAL-02](../bundles/CAL-02.md), [CAL-03](../bundles/CAL-03.md), [CAL-04](../bundles/CAL-04.md), [CAL-06](../bundles/CAL-06.md), [UQS-01](../bundles/UQS-01.md), [UQP-01](../bundles/UQP-01.md), [UQP-02](../bundles/UQP-02.md), [UQP-03](../bundles/UQP-03.md). Не все они являются prerequisite одного частичного сценария.

Сначала выполнить необходимые маленькие N seam checks при готовности конкретного patch. В окне объединять общий import/setup, но не менять identities/precision/seed ради сравнения. Re-run только failed/affected tests после исправления, не всё окно автоматически. Deferred capabilities остаются явно непроверенными; успешный partial route не означает полной platform readiness.

