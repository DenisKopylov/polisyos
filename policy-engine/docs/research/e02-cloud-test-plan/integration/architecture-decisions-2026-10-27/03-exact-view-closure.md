# TC-01 companion: точная и проверяемая SameInputClosure

## 1. Какую проблему закрываем

Source `7a4c713` хранит selected refs как строки. `identity_tuple()` включает заявленный `closure_sha256`, но не включает `evidence_input_refs`; `assert_same_input_closure()` проверяет closed/nonempty и equality, не recompute. Отдельный prototype показывает две verified manifest views одного payload ID, которые такой consumer считает одинаковыми. Это identity defect данной границы; полноценный published authority escape не установлен.

Выбор: расширить **существующий runtime-quality closure owner** одним versioned typed identity/resolution path. Не добавлять ещё один verifier рядом и не ограничиваться time ref. Pure equality остаётся полезной после verification, но не выполняет admission сама.

## 2. Новый wire и owner contract

Новая closure shape имеет explicit discriminator `schema_version="2.0"`; существующая unversioned/string-only shape читается явным legacy decoder. Не ослаблять старую модель union-ом “строка или что угодно”. Versioned v2 type reuse existing `ArtifactRef`, `InputRef`, owner registries и consumed-input machinery.

Каждый reference member v2 — один из **typed domains**, выбранный его owner contract:

- `identity_domain="cas"`: exact `ArtifactRef` (`artifact_id`, `kind`, `media_type`, **non-null** `manifest_profile_sha256`); lineage/consumption role сохраняется как existing `InputRef.role` или named member role. Admission сверяет selected manifest, schema/version, producer и permission согласно owner/purpose.
- `identity_domain="owner_value"`: зарегистрированный owner/rule version и canonical structured value либо immutable record reference, разрешаемый этим owner. Например effective runtime profile — validated selected value, а не CAS object. Свободная строка от consumer не становится resolved identity от обёртки.
- `null`: binding отсутствует явно; required/optional определяется конкретным owner/purpose. Не вводить fake “null artifact”.

Это bounded union в существующем module, а не новый global registry/service. Будущие domains/semantics требуют owner registration/version и verifier; неизвестные values можно удержать как candidate, но protected admission не принимает их по префиксу строки. Expected kind/schema/role задаёт trusted owner contract, не caller-controlled expected-поле.

Полный существующий slot set на source pin:

| Slot | Actual NL owner binding / действие |
|---|---|
| `policy_intent_ref` | CAS `runtime.policy_intent_envelope`, role `policy_intent_envelope`, existing schema `polisyos.runtime.PolicyIntentEnvelope@1.0`. |
| `time_context_ref` | Новый CAS `runtime.temporal_scope`, schema из TC-01; binding к authorized request обязательна. |
| `production_data_manifest_ref` | По registry это CAS `fabric.production_data_payload`, role `production_data_payload`, `polisyos.fabric.ProductionDataPayload@1.0`; не переименовывать предмет по misleading field name. |
| `legal_snapshot_ref` | В current NL registry явно unbound. Сохранить null и отдельный Lex barrier; будущий supplier регистрирует фактический typed contract. |
| `effective_mode_ref` | NL сейчас symbolic `runtime-mode:<profile>`; v2 переносит в owner_value c verified effective mode. Другие producers могут иметь иной admitted domain — проверять их owner contracts. |
| `method_plan_ref`, `provider_mode_ref`, `degradation_ledger_ref` | На этом NL пути unbound/not_established. Не придумывать CAS semantics из суффикса `_ref`. |
| `evidence_input_refs` | Все selected source input edges актуального closure owner, включая роли/profile и actual consumed bindings. Больше не исключены из identity. |

`closure_id` — locator; `run_id/job_id/tenant_id/cell_id` — non-CAS execution binding. Пустой optional slot входит в identity как отсутствие, а не исчезает произвольным `exclude_none`. Все пять context identifiers сохраняются с собственной ролью: `closure_id` проверяется на корректную linkage, но не обязателен для семантического equality между independently materialized closures одной basis.

## 3. Identity projection и verification

`closure_sha256` v2 — SHA-256 canonical **owned projection**, domain-separated именем/version closure law и полным selected canonical spec. Проекция содержит:

1. Schema/identity-law version, **общая closure-basis contract interpretation** и execution scope `run/job/tenant/cell`. Producer identity конкретного output report не входит в общий basis hash: иначе разные честные evidence owners никогда не совпадут. Их provenance проверяется отдельно; actual input-member interpretation сохраняется.
2. Все named input members, их roles, domains, exact resolved identities и явные отсутствия.
3. Полное `evidence_input_refs` membership по owner law. При текущем tuple contract сохранять порядок и multiplicity. Если конкретный owner документирует математическое множество — он canonical-sorts unique role-qualified members; duplicate/colliding member keys отказывают. Нельзя глобально sort/dedup по одному artifact ID.

Не включать в digest его собственное поле, derived status, random closure locator, output report refs, timestamps производства receipts или sealed-set digest. Это исключает self-reference и ложное расхождение одинаковых inputs. Binding locator/status и producer times проверяются **отдельно**, не игнорируются. Новое поле, влияющее на identity, должно быть объявлено в owner schema; contract check выводит coverage из этой schema с явными typed nonidentity roles, а не из списка сегодняшних test tags.

Protected admission выполняет:

1. Parse exact wire version; найти trusted owner contract и его полный inventory required/optional/consumed inputs.
2. Разрешить каждый CAS ref **по указанному profile**, проверить payload hash, manifest profile, kind/media/schema и owner provenance; применить текущий access/purpose check. Non-CAS domain разрешить его registered owner. `latest` lookup не подменяет explicit identity.
3. Сопоставить declared members с input edges producer и фактически потреблёнными owner inputs. Самоподписанный короткий список не доказывает completeness. Required member отсутствует, hidden consumed input или unsupported domain — closure не verified.
4. Recompute canonical projection/hash; сравнить с сохранённым hash и expected run/request binding. Результат — внутренний verified object/validated return существующего owner, не сериализуемый флаг “verified=true”, который можно подать обратно как доверенный.
5. Сравнить verified input identities между envelopes и построить/recheck `SealedConsumedInputSet` через тот же path. Constructor string checks и `predicate_class="recomputed"` сами по себе недостаточны: class устанавливает resolver после реальной операции.
6. Выполнить независимые purpose/authority/adequacy barriers. Равный verified input hash не равен true/adequate/publishable policy evidence.

Canonical codec не доказывает правильность source role или schema. Проверенный digest не доказывает, что owner использовал заявленные inputs. Поэтому contract/producer→consumed bridge и verifier provenance остаются load-bearing.

`evidence_input_refs` здесь — **closure basis**, не собственный output каждой evidence envelope. Output artifacts и индивидуальные производственные deps сохраняются в обычной lineage и consumed-set records. Не вставлять output report обратно в его input closure. Если у двух evidence фактически разная decisive basis, same-input gate не должен “нормализовать” это в equality: нужен явно новый совместный basis/producer или declared mismatch. Порядок зависимостей остаётся ацикличным: admitted source inputs → closure basis → report/envelope → consumed seal/public projection.

## 4. Migration без обхода gates

- Новый v2 writer включается после v2 readers конкретного cohort. Existing `RunIntentBinding`, manifest `ArtifactSameInputClosureInfo`, envelope schema/reader contract, runtime report registry, consumed seals и publication projection должны согласованно переносить selected identity. Не только Python `SameInputClosure`.
- Affected report/envelope schemas получают следующую major version (для pinned `1.0` — `2.0`); точный список выводится из registry плюс actual users. Не менять schema всех unrelated reports “на всякий случай”. Схема Core manifest меняется только там, где меняется её persisted authority-summary shape; поддержать её обе версии в existing compatibility owner.
- Public DTOs/OpenAPI/generated consumers должны знать новый wire; старым клиентам доступны прежние views с честной qualification. Не strip profile ради backward-compatible authority success.
- Legacy immutable reports/closures читаются по старому decoder. При строгом reuse они должны пройти независимый re-admission из сохранившихся exact views и actual consumed evidence в **новую** v2 record. Не считать string-only record equivalent v2 без этих inputs; ambiguous profile/history остаётся limited/unavailable. Исторические findings не переписывать.
- Existing old helper допустим для explicitly historical/advisory equality. Ни scorecard, ни authority-role selection, ни reuse seal, ни sibling public consumer не должны использовать его как достаточную новую authority admission. Их migration является acceptance denominator; оставить такой обход “до следующего этапа” нельзя.
- Rollback выключает новые writers, но не удаляет readers уже выпущенного v2. Нет rewriting CAS, no fallback-to-legacy authority и no whole-history recomputation ради локального rollout.

## 5. Ресурсы и параллельность

Разрешать и читать каждый unique selected view один раз на admission scope; immutable payload/profile verification можно memoize по exact identity и verifier/rule version. Tenant/purpose/access revocation и retention проверяются по текущей owner policy, не кэшируются навсегда вместе с bytes. Не загружать одинаковый большой payload для каждого report заново. При целостном verified input snapshot допускается передача проверенного объекта нескольким consumers без повторного full read; граница доверия/процесса требует normal re-entry.

Новая closure law не требует scheduler, background verification service, полной загрузки production или массовой миграции остальных evidence classes. Один writer меняет closure/manifest companion; TC request path и CAN codec могут развиваться независимо до своих composed acceptance.

Pattern pass: P05/P14 — точная identity не повышает evidence strength; P07/P08 — версии и роли; P27/P31 — один shared intake+emission; P29/P32/P37/P38 — actual resolution, membership и authority predicate; P40 — profile, role, member substitution являются одним классом under-bound input identity, а не поводом для отдельных bespoke fixes.
