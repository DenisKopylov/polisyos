# R17 — Исследование хранения, преемственности и доступа

Срез репозитория: `d30e957940c7060ac7efcbb571fe3b763a1eee80`; исследование 2026-10-23. Восемь прямых read-only исследователей рассмотрели preservation, retention/trust, revalidation, institutional succession, access architecture, access modes, repository coverage и longitudinal effects. Автор сопоставил результаты с ratified identity/custody boundary, текущими tasks и native owner anchors. Отдельный независимый redteam описан в [review](../assurance/r17-review.md). Тесты, импорт продукта, build/install, production/data scans и реализация не выполнялись.

## Что уже было и что требовало уточнения

| Вопрос | Уже в плане до R17 | Уточнение R17 |
|---|---|---|
| Завершённый дизайн | PolicyArtifactBuilder, CAS, claim/case/epoch history, LIF-07 influence | Полный selected edition closure, понятная representation, историческое чтение, material alternatives, частичное хранение |
| Долговечность | OPS-05/10 recovery, LIF-05 copies/rights, OPS-11 trust/duties | Fixity/format/cryptographic renewal как duties; restore frontier против tombstone lifetime; evidence-archive handoff |
| Актуальность | CAP-04 events, LIF-02 enrollment/fence, LIF-04 continuation | Silent-source interval coverage, periodic revalidation, накопленные малые изменения, полезный no-change, срок и стоимость duty |
| Действующая политика | DES-11 trajectory/incumbent/lag/commitments | Внешний actual act→scoped applicability→operational evidence→fresh incumbent consumer; частичная замена |
| История/обучение | R15 assignment/exposure, R16 cutoff/re-execution, GYD O1/O2/O3 | Policy-regime history в estimand, отличия rollout/receipt/target/measurement, corrected versus as-known result |
| Доступ | AccessScope/authz/OPA, LIF-05 source use, OPS-06 object boundary, DES-09 context | Whole access lifetime, nonamplifying delegation, revoke-at-commit, metadata/derived outputs, productive sharing |
| Развёртывание | Local→single cell→selected hybrid/remote/offline | Mode-specific threat/consistency claims, recipient export/ingest/transfer, public dossier with private basis |

Это assessment полноты планирования и ограниченное статическое чтение. Оно не доказывает runtime PASS, security defect или repository-wide absence. Все relevant task entries остаются planned_after_E02_acceptance/UNRUN. Missing capability label после E02 назначается по actual chain, а не по отсутствию слова в документации.

Native anchors: `scientist/policy_design/schema.py` (candidate persistence), `scientist/policy_design/output.py::PolicyArtifactBuilder`, `scientist/evidence/claims/lifecycle.py` / `head_index.py`, `runtime/quality/case_lifecycle.py`, `semantic_epoch_store.py`, `epoch_validity_cascade.py`, `core/artifacts/manifest.py`, `ir/artifacts/lineage.py`, `core/security/access_scope.py`, `runtime/http/authz_middleware.py`, `ops/policy/policies/decision.rego`. Candidate ID и layer `PolicyOverrideMode.REPLACE` не подтверждают внешнюю замену; claim head и semantic epoch не являются административным реестром действующих актов. Ratified PolicyMatter — существующий верхний identity, не новый R17 subsystem.

## Primary sources и применимые уроки

Ниже выводы источников кратко отделены от нашего инженерного выбора. Это примеры механизмов и доказанных сложностей, не универсальное право и не свидетельство их реализации в PolicyOS. Версии/возможности провайдеров и нормативные требования перепривязываются при implementation commissioning. Библиотека не выбирается только потому, что названа SOTA.

### Сохранность и доверие

| Источник | Что учитываем | Ограничение переноса |
|---|---|---|
| [OAIS, CCSDS 650.0-M-3](https://ccsds.org/Pubs/650x0m3.pdf) | Information package и representation information необходимы для будущего понимания данных | Референсная модель не доказывает научную воспроизводимость, права или достаточность конкретного archive |
| [PREMIS 3](https://www.loc.gov/standards/premis/v3/) | Различать preservation objects/events/agents/rights и объяснять выполненные действия | Не дублировать existing CAS/event owners отдельным обязательным store |
| [OCFL 1.1](https://ocfl.io/1.1/spec/) | Inventory/fixity и версионирование объектов полезны для независимого чтения и audit | Формат хранения не является currentness/authority contract; не обязательная миграция PolicyOS |
| [BagIt RFC 8493](https://www.rfc-editor.org/rfc/rfc8493.html) | Проверяемый перенос файлов/manifest как bounded transport mechanism | Valid bag не доказывает completeness выбранного design basis или допустимость recipients |
| [RO-Crate](https://www.researchobject.org/ro-crate/) | Машиночитаемые связи research objects и происхождения полезны для portable export | Не подменять actual influence graph произвольными author declarations |
| [NARA preservation programme](https://www.archives.gov/preservation/digital-preservation/about) | Fixity, действия над файлами, устойчивые представления и отдельные public-use copies — разные обязанности | Их operational cadence не становится нашим universal TTL или schedule |
| [Evidence Record Syntax, RFC 4998](https://www.rfc-editor.org/rfc/rfc4998.html) | Timestamp/hash-tree renewal до потери безопасности и сохранённая verification material | Renewal не восстанавливает утраченные bytes/chain и не подтверждает сегодняшнюю истинность |
| [NIST SP 800-57 Part 1 Rev.5](https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-57pt1r5.pdf) | Историческая проверка после compromise требует отдельного основания времени/защиты | Retirement, historical validity и current signing authority различаются; algorithm policy проверяется заново |
| [TUF specification](https://theupdateframework.github.io/specification/latest/) | Защита последовательной смены roots, rollback/freeze и независимого recovery | Software trust protocol не назначает институционального issuer |
| [NIST SP 800-88 Rev.2](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-88r2.pdf) | Cryptographic erase зависит от crypto/key/media/copy preconditions | Удалённая ссылка на ключ не означает стертые plaintext/cache/escrow; не обещать universal erasure |
| [GDPR, Articles 17–18, 89](https://eur-lex.europa.eu/eli/reg/2016/679) | В применимом EU scope storage/restriction/erasure и исключения различны | Это jurisdiction-specific пример, а не автоматическое основание хранения любого дизайна |
| [S3 versioning troubleshooting](https://docs.aws.amazon.com/AmazonS3/latest/userguide/troubleshooting-versioning.html) | Delete marker и доступность старой object version — разные факты | Provider semantics проверять выбранным adapter; не переносить на local/GCS без witness |

### Живое обоснование, реальная политика и оценка

| Источник | Что учитываем | Ограничение переноса |
|---|---|---|
| [Cochrane living systematic reviews](https://resources.cochrane.org/sites/default/files/uploads/inline-files/Transform/201912_LSR_Revised_Guidance.pdf) | Living evidence требует постоянного поиска/обновления, владельцев и критериев продолжения | Нет обязанности вечно пересчитывать каждую policy; scientific review не тождественен legal applicability |
| [NIST AI RMF core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/) | Мониторинг, изменение контекста, реакция и управление ответственностью входят в lifecycle | Framework не даёт готовые source-specific thresholds или право подписи |
| [FDA postmarket AI monitoring](https://www.fda.gov/medical-devices/medical-device-regulatory-science-research-programs-conducted-osel/methods-and-tools-effective-postmarket-monitoring-artificial-intelligence-ai-enabled-medical-devices) | Отдельные вопросы распределения данных, эффективности и доступности feedback | Медицинский контекст не становится universal PolicyOS gate |
| [UK Guide to Making Legislation](https://www.gov.uk/government/publications/guide-to-making-legislation/guide-to-making-legislation-html--2) | Commencement, scope, transitional/saving provisions могут сохранять старый режим для части случаев | Типы scope поддержать общими facets; не кодировать UK law как общий default |
| [UK Understanding Legislation](https://www.legislation.gov.uk/understanding-legislation) | Публикация, commencement и editorial revision могут расходиться во времени | Официальный текст сам по себе не доказывает operational delivery |
| [NARA About eCFR](https://www.archives.gov/federal-register/cfr/about-ecfr), [OFR FAQ](https://www.archives.gov/federal-register/faqs) | Future-effective changes и их corrections/withdrawals отличны от текущего текста; permanent published record исправляется новым актом | Scoped US federal practice; выбор legal authority остаётся jurisdiction-specific |
| [Green Book 2026](https://www.gov.uk/government/publications/the-green-book--2/the-green-book-2026) | Incumbent/business-as-usual, альтернативы, uncertainty и distributional effects — содержательная база сравнения | Не навязывать один welfare aggregator или денежную valuation rule |
| [Magenta Book](https://www.gov.uk/government/publications/the-magenta-book/magenta-book-central-government-guidance-on-evaluation-html), [Test and Learn](https://www.gov.uk/government/publications/the-magenta-book/test-and-learn-html) | Evaluation связывает implementation и outcomes; адаптация и phased rollout влияют на возможности идентификации | Design recommendation не означает разрешение рандомизировать или менять практику |
| [Hernán & Robins, What If](https://miguelhernan.org/whatifbook), [Marginal Structural Models](https://doi.org/10.1097/00001648-200009000-00011) | Версии treatment и история, confounders affected by prior treatment требуют точно выбранного estimand/метода | Нет универсального estimator, который автоматически решает любой transition |
| [Hudgens & Halloran: interference](https://doi.org/10.1198/016214508000000292) | Direct/indirect/total/overall effects различаются при влиянии между units | Требуется обоснованный exposure mapping или явный предел, не автоматическое no-interference |
| [Sun & Abraham](https://doi.org/10.1016/j.jeconom.2020.09.006), [Callaway & Sant’Anna](https://doi.org/10.1016/j.jeconom.2020.12.001) | Staggered adoption и effect heterogeneity влияют на estimands и агрегирование | Не banning метода по имени; actual selected assumptions и support определяют допустимость |
| [Bernal et al., interrupted time series](https://doi.org/10.1093/ije/dyw098) | Impact model, timing, seasonality/autocorrelation и confounding существенны | Изменяющаяся политика не обязана соответствовать одному interruption |

### Доступ и развертывание

| Источник | Что учитываем | Ограничение переноса |
|---|---|---|
| [NIST ABAC SP 800-162](https://csrc.nist.gov/pubs/sp/800/162/upd2/final), [Zero Trust SP 800-207](https://csrc.nist.gov/pubs/sp/800/207/final) | Subject/object/action/context и отсутствие implicit trust только из сети | Не заменяет source rights, object ownership или law verifier |
| [Zanzibar, USENIX ATC19](https://www.usenix.org/conference/atc19/presentation/pang) | Causal ordering между изменениями ACL и content предотвращает stale authorization | Не наследовать Google scale/SLA и не требовать такой кластер для local pilot |
| [OpenFGA consistency](https://openfga.dev/docs/interacting/consistency) | Выбор freshness/cache mode и его ограничения должны быть явны | Cache bypass сам не даёт causal token/atomicity с external CAS |
| [Cedar semantics](https://docs.cedarpolicy.com/auth/authorization.html), [security](https://docs.cedarpolicy.com/other/security.html) | Forbid overrides permit, но error policy пропускается; schema validation важна | Required predicate error нельзя принять за доказанную неприменимость; текущий OPA заменять не требуется |
| [OAuth Token Exchange RFC 8693](https://www.rfc-editor.org/rfc/rfc8693.html) | Subject, actor, scope, resource/audience выражают delegation | Revocation propagation не является общим обещанием протокола |
| [ONS Five Safes](https://www.ons.gov.uk/aboutus/whatwedo/statistics/requestingstatistics/secureresearchservice/aboutthesecureresearchservice), [Eurostat microdata access](https://ec.europa.eu/eurostat/web/microdata/access) | Люди/проекты/среда/данные/outputs и именованное институциональное допущение различаются | Не обязательный ручной approval для каждого публичного source; applicable profile определяет процедуру |
| [NHS SDE output](https://digital.nhs.uk/services/secure-data-environment-service/output-your-results-from-the-sde) | Output release — отдельная проверка от успешного computation | Применимо к выбранной controlled environment; не universal bureaucracy |
| [NIST SP 800-226](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-226.pdf) | Privacy guarantees требуют точных параметров, unit и composition | Слово DP не clearance на произвольные производные |
| [Carlini et al. USENIX Security21](https://www.usenix.org/system/files/sec21-carlini-extracting.pdf) | Производная модель может сохранять/раскрывать обучающие сведения | Не каждый descendant одинаково опасен; нужен applicable release predicate, не blanket deny |
| [AWS silo/bridge/pool](https://docs.aws.amazon.com/whitepapers/latest/multi-tenant-saas-storage-strategies/saas-partitioning-models.html) | Deployment tradeoffs для tenant isolation | Physical/network separation не заменяет authorization; не все modes нужны одновременно |
| [Azure multitenant agentic systems](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/considerations/agentic-systems) | Tenant context проверяется в tool/handoff boundaries, prompt не isolation | Selected PolicyOS provider/tool integration требует фактического witness |

## Собственный инженерный синтез

Из этих работ не следует требование нового монолитного архива, replacement engine или IAM. Выбраны семь bounded дополнений [D1–D7](../solutions/17-design-custody-and-succession.md) к existing owners. Universal identity/facets, versioned relation/representation/rights contracts и real consumer verification дают рост без доменных шаблонов. Особые методы/форматы подключаются только с проверенной semantics. Стоимость больших данных ограничивается manifest/chunk reuse, scoped reconciliation, risk-based preservation sampling с честной coverage и reuse старой арифметики при изменении только use rights. Полная размерность influence важнее ложной экономии от неполного read-set.

Дополнительные SDD сейчас не требуются: PolicyMatter, долговременная честность собственной подписи, external acts как typed evidence и anti-administration boundary уже ратифицированы. Предложения не меняют эти правила. Если rebind выявит необходимость новой institutional authority или sovereign subsystem, исполнитель должен отдельно вынести решение на согласование, а не спрятать его в migration/default.

Pattern pass: P01/P02/P03/P04/P05/P07/P08/P09/P10/P13/P14/P15/P27/P29/P31/P32/P35/P37/P38/P40/P41. Детали критериев, owners и проверок — task extensions; ни ссылка на источник, ни эта исследовательская работа не закрывает finding и не устанавливает E02 acceptance.
