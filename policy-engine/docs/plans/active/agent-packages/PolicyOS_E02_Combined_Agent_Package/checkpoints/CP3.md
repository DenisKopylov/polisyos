# CP3 — Поиск и доказательная точность diagnostics

**Режим C: один последовательный выбранный набор, другие test/build/install jobs не работают. Код и review продолжаются.**

Исходные сценарии: T9, T10, T11, T12, T15, T16. Их полные тексты сохранены в B source; применяется реальный selected route, не все методы платформы.

Короткая search history/GP/index и state→service cutover. Calibration100 small observations с empty/valid intervals; BERL2 features; DDM5 states,expiry/mismatch и R2 signoff. Ни больших моделей, ни реального deployment.

**Пакеты этой приёмочной области:** [CTL-01](../bundles/CTL-01.md), [CTL-03](../bundles/CTL-03.md), [SRV-01](../bundles/SRV-01.md), [SRV-03](../bundles/SRV-03.md), [CTL-02](../bundles/CTL-02.md), [STP-01](../bundles/STP-01.md), [OPT-01](../bundles/OPT-01.md), [OPT-02](../bundles/OPT-02.md), [OPT-03](../bundles/OPT-03.md), [OPT-04](../bundles/OPT-04.md), [FUN-01](../bundles/FUN-01.md), [FUN-02](../bundles/FUN-02.md), [FUN-03](../bundles/FUN-03.md), [TRN-01](../bundles/TRN-01.md), [TRN-02](../bundles/TRN-02.md), [TRN-03](../bundles/TRN-03.md), [PCL-01](../bundles/PCL-01.md), [BKT-01](../bundles/BKT-01.md), [BKT-02](../bundles/BKT-02.md), [BKT-03](../bundles/BKT-03.md), [BKT-04](../bundles/BKT-04.md), [DOE-01](../bundles/DOE-01.md), [DOE-02](../bundles/DOE-02.md), [DOE-03](../bundles/DOE-03.md), [STR-01](../bundles/STR-01.md), [BER-01](../bundles/BER-01.md), [DDM-01](../bundles/DDM-01.md), [DDM-02](../bundles/DDM-02.md), [LEX-01](../bundles/LEX-01.md). Не все они являются prerequisite одного частичного сценария.

Сначала выполнить необходимые маленькие N seam checks при готовности конкретного patch. В окне объединять общий import/setup, но не менять identities/precision/seed ради сравнения. Re-run только failed/affected tests после исправления, не всё окно автоматически. Deferred capabilities остаются явно непроверенными; успешный partial route не означает полной platform readiness.

