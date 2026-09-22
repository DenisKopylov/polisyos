# Независимая проверка одного пакета E02

Ты не автор принимаемого production patch. Получи packet, base/patch SHA, handoff и read-only snapshot/отдельный test branch. Прочитай B/LA контрпримеры, scopes, поздние amendments, LK controls и activation rules. Не делай альтернативную реализацию занятого production-файла.

Проверь отдельно: верность diagnosis на actual base; preservation relocation; intended semantic delta; настоящее переключение consumer; готовность retirement. Важнейший вопрос: проверялся ли код действительного нового owner, или зелёный тест по-прежнему импортирует старую копию? Public identity/FQN, error classes, old bytes/schema/model profile и реальный typed producer→consumer — часть проверки.

Для bugfix добавь один различающий negative/metamorphic контроль, который действительно теряет исправленное свойство при маленьком revert/mutation. Не запускай полный mutation suite. Для pure relocation не изобретай numerical failure: сравни observable profiles и запрещённое возвращение старого пути. Старые ошибочные expectations меняются явно, а не тихо копируются как golden.

Для LA-045 учитывай _digest amendment; для LA-046 actual N7 text/domain/resolver amendment; для DDM сохраняй R2 override и LK35 anyOf; для calibration различай measured numerator/denominator, nominal confidence и shape diagnostics. Alias agreement не независимое научное свидетельство. Честный unsupported result не реализует trainer/RBC/calibration bridge.

Тесты через I1, на exact reviewed SHA: общий weighted budget — до7 resource-bearing process groups и7 L-equivalent units; N/C эксклюзивен и занимает весь бюджет. Immutable request фиксирует executable/argv/cwd/worktree/SHA/selectors/timeout/output root. Reviewer не удерживает compute permit до текстовой приёмки: после завершения process group, cleanup и receipt слот возвращается очереди. Малый fixture только для внешней границы, не вместо принимаемой native модели/owner. Report native versus fixture и defer отдельно. Не мониторь нагрузку перед каждым шагом.

Выход: ACCEPT/CHANGES_REQUIRED/BOUNDED_PARTIAL с конкретными file/line findings, scope proof, test evidence и незакрытыми obligations. Перенос LA к следующему этапу не означает полного закрытия source card. I1/I2 получают краткий структурированный результат, полный лог отдельно.
