# E02: связанный разбор и следующая организация работ

Срез анализа: G `6f3983466f1eca14b510c4f5006fab5092d418d3`; точные входы — [inputs.json](inputs.json). Это план продолжения и разбор свидетельств, а не новая приёмка кода или formal closure. `main` в этой работе не меняется.

**Рекомендация: прекратить очередные полные циклы A–F и перейти к небольшим вертикальным задачам по общим механизмам.** Основной остаток находится между уже написанными частями: фактический input → producer → persisted artifact → owner-bound orchestration → fresh consumer. Его нельзя закрыть дополнительными generic fixtures внутри каждого прежнего пакета. При этом не следует переделывать исправные ограниченные математические методы ради более широких обещаний, которых исходный критерий не требует.

Полный пересчёт исходного набора: **127 bundles, 282 findings, 291 criterion occurrences**. Текущие предложения авторов:

| Прежняя группа | Findings / occurrences | Proposed closed | Limited | Held | Open |
|---|---:|---:|---:|---:|---:|
| A | 34 / 35 | 5 | 23 | 1 | 5 |
| B | 60 / 60 | 47 | 7 | 4 | 2 |
| C | 54 / 59 | 31 | 12 | 11 | 0 |
| D | 45 / 46 | 39 | 1 | 5 | 0 |
| E | 54 / 55 | 43 | 9 | 2 | 0 |
| F | 35 / 36 | 33 | 2 | 0 | 0 |
| Всего | **282 / 291** | **198** | **54** | **23** | **7** |

Это распределение предложений, а не распределение готовых capabilities. Ни «198 closed», ни «84 остальных» не задают объём оставшегося исполнения. У некоторых proposed-closed строк остаётся проверка исходного whole-property; часть limited строк сохраняет честную границу уже исправной реализации. В G coverage все 282 строки нового adjudication имеют `not_adjudicated`; исторические закрытия, в том числе B198, отдельно сохраняются. Из нуля новых adjudications нельзя заключать, что агенты ничего не сделали.

Документы следует читать в таком порядке:

1. [Что выполнено и почему повторная передача даёт мало результата](01-state-and-causes.md).
2. [Архитектурные и контрактные решения](02-decisions.md): выбранный инженерный путь, необходимые исследования, границы внешней authority.
3. [Конкретная очередь и зависимости](03-delivery-plan.md): что начинать сейчас, что ждать, что осознанно отложить.
4. [Новая конфигурация команд](04-work-organization.md): canonical writers, отдельные reviewers, ресурсы и handoffs.
5. [Приёмка, freeze и экономия проверок](05-verification-and-release.md).
6. [Минимальные входы и честные ограничения](06-inputs-and-deferrals.md).
7. [Все 282 строки](findings.json): исходный criterion pointer, актуальное предложение автора и маршрут следующего решения. Полный исходный текст не копируется: ссылка ведёт на его canonical coverage и immutable owner packet.
8. [Source choices и обязательные companions](07-source-selection.md): как не смешать уже принятый source, prepared delta и широкий branch footprint. [Tasks JSON](tasks.json) — исполняемая карта очереди, без product authority.

Первоочередная работа: восстановить исполняемую проверку подготовленного B source; закрыть DFI identity и DFK census; выбрать точные B CAS/budget contracts для композиции; подключить один настоящий served policy путь; сформулировать узкие subject/graph/refinement решения; затем выполнить canonical regeneration и только после freeze общий replay. Внешние разрешения, law и production provenance собираются параллельно по минимальным packets. Они не являются поводом остановить остальные механизмы.

Для этого разбора использовано 20 прямых помощников: шесть полных unit crosswalks и четырнадцать независимых разрезов — denominator, authority, economics, science, served orchestration, identity, migrations, recovery, footprint, verification, organization, skeptical review, minimal inputs и platform. Помощники не меняли source/refs/integration и не создавали детей. G сверяет противоречия и публикует общий результат. Детали происхождения и проверок документации — в [analysis-receipt.json](analysis-receipt.json).

Pattern pass: P01/P02/P12 — недостающие producer/bridge; P04/P05/P07/P08 — status, authority, replay и time roles; P10/P14 — предел математического и эмпирического утверждения; P27/P31 — один canonical mechanism; P29/P32/P33 — behavioral discriminator и content binding; P35/P37/P38 — полный denominator и фактический predicate; P40/P41 — отсутствие repair ladder и приписанной чужой красноты. План не вводит product enums и не превращает исследовательские вопросы в неподтверждённые контракты.
