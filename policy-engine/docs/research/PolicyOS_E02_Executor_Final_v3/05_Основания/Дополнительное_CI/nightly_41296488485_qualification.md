# Дополнительное Nightly CI-свидетельство — не новая ремонтная программа

**Read-only проверено 1 ноября2026.** [Run41296488485](https://github.com/DenisKopylov/polisyos/actions/runs/41296488485), четыре job logs подтверждают checkout `20d9009be21097bfbdc38a546a15cc60213b8ace`. Проверены metadata/steps и точные диагностические диапазоны; это не полный новый CI/security audit. Hashes decoded logs, line locators и статусы — в соседнем JSON.

| Наблюдение | Корректная квалификация |
|---|---|
| [Benchmark contours](https://github.com/DenisKopylov/polisyos/actions/runs/41296488485/job/124818314221): summary40 circuits,3passed,37errors,0failed. Повторяется `KeyError: np` → `restricted_exante_builtin_numpy_dependency_missing`; отдельно отсутствует `tests.foundry`, два CLI отвергают переданные smoke flags. | Это ошибки entrypoint/import/контракта вызова в данном smoke, а не37 отрицательных численных результатов. Full benchmark qualification не получена; нельзя ни объявить все модели сломанными, ни назвать failed job успешным. |
| [Frontend](https://github.com/DenisKopylov/polisyos/actions/runs/41296488485/job/124818314104): build success; actual configured gzip budgets536.8kB>244.1kB и233.9kB>53.7kB. | Bundle gate действительно не пройден. Запуск Lighthouse CI и его services skipped; успешный summary с пустой таблицей не performancePASS. Эти числа — существующие пороги job, не новый произвольный SLO спецификации. |
| [OpenSSF Scorecard](https://github.com/DenisKopylov/polisyos/actions/runs/41296488485/job/124818313902): создание `/github/workspace/tmp/scorecard.sarif` не удалось; upload не нашёл `/tmp/scorecard.sarif`. | Не получен ожидаемый output; нельзя вывести низкий security score из этой ошибки пути. |
| [Supply-chain audit](https://github.com/DenisKopylov/polisyos/actions/runs/41296488485/job/124818314246): SBOM/report steps success, vulnerability-policy step failure на advisory/package matches. | Это зафиксированное решение scanner policy. Deployment reachability/exploitation здесь не проверялись; совпадение сканера не объявляется установленной экспозицией. |

## Привязка только к уже существующей приёмке

- [HYG-04](../../02_Пакеты/HYG-04.md), REQ-HYG-04-04 / TEST-HYG-04-04 и [E02-I12-A](../../03_Интеграция/LANE-12.md): перед положительным CP6 build/benchmark claim необходимо дойти до действительного выбранного consumer и предъявить honest result. Новые logs уточняют известное ограничение qualification, не добавляют обязательства исправить все Nightly jobs или переписать frontend.
- [FRY-01](../../02_Пакеты/FRY-01.md), REQ-FRY-01-02 / TEST-FRY-01-02 и [E02-I04-A](../../03_Интеграция/LANE-04.md): actual MethodRegistry/catalog execution нельзя заменить import-free fixture. Зафиксированный import fault не приписывается автоматически именно этому пакету; сначала устанавливается фактический owner/достижимый маршрут.
- Pinned `restricted_executable_profile.py:260–263` действительно проверяет `method_operation.__globals__["np"]` и выдаёт указанную typed runtime error. Это подтверждает место диагностики, но не разрешает обход dependency/profile guard или произвольную вставку `np`.

Ни rerun/install/upgrade, ни credentials/config changes не выполнялись. Новые R/G и пакеты не создаются, sealed phase1 bytes не меняются. Все будущие TEST-ID этого комплекта остаются **NOT_RUN**. Дополнительный необходимый ремонт, если он окажется вне существующих требований, должен получить отдельное ограниченное решение, а не скрыто расширить127ТЗ.
