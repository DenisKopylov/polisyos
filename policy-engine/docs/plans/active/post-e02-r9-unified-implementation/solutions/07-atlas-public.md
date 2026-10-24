# Публичные поверхности Atlas: предпочтительные решения

Статус: engineering recommendations; product execution UNRUN. Реализация только после E02 acceptance и полного affected-scope rebind. Исходные критерии не сокращаются; [общие решения](00-shared-decisions.md) предотвращают второго owner. [Нормативные уточнения](decision-clarifications.md) остаются предложениями.

<a id="UI-01"></a>

## UI-01 — Finish DS12 consumers over accepted verification

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-01]`. Review: [root-review](root-review.md#UI-01).

### Предпочтительное решение

Finish only the remaining consumer wiring over the accepted server verification record. Reuse the closed verifier/badge bridge and show 'report signature authenticated' separately from all seven decision-authority dimensions, which remain not_established in the positive case. Carry record ID, exact source view, key reference, schema/rule version, issue and status-snapshot times, and explicit limitations through browser, API/client, CLI, MACHINE, and authorized-read audit. An offline check may establish signature authenticity only against its included trust snapshot; live revocation and currentness remain not_established unless independently established.


### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/services/public_decision_verification.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `PublicDecisionVerificationService.verify`. Existing server-owned verification returns a response from the issuance index and byte-bound verifier; this is the source of the UI cue.
- `policy-engine/src/polisyos/runtime/http/services/public_decision_verification_contracts.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `PublicDecisionVerificationDimensions`. Typed contract carries seven dimensions as not_established and keeps them distinct from report_authentication.
- `policy-engine/packages/runtime-api-client/canonicalRuntimeApiClient.ts@dccea950845cda5b38f026e7770c07819d31f4d9` — `verifyPublicDecisionRecord`. Existing generated/canonical client call is the consumer bridge to extend.
- `policy-engine/apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.tsx@dccea950845cda5b38f026e7770c07819d31f4d9` — `GovernedPublicRecordView`. Existing browser surface renders the governed public record.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. After actual E02 acceptance, bind this row to the accepted verifier response and resolve the still-open R9 full-head, anonymous-read, tenant, and exact-view gates.
2. Trace actual consumers and generated-client companions; wire each to the same server response and preserve the closed forged-packet/badge negative.
3. Render a plain-language explanation of what the signature proves and does not prove; expose the seven unestablished authority dimensions as named fields, not a collapsed green badge.
4. Keep verifier reads no-store and omit credentials/redirects as the accepted route requires; record authorized read/denial events through the access-audit owner.


### Рассмотренные альтернативы

- **Recompute signatures or authority status independently in each browser, CLI, and MACHINE consumer.** — Duplicates trust decisions, risks divergent badges, and turns client-calculated evidence into an authority path.
- **Display one generic 'verified' flag.** — It merges report byte authentication with promotion, admissibility, currentness, and authorization.


### Free-grow и ресурсы

- **data or config growth:** New consumers may use the existing response contract; new trust dimensions require a typed source and a rule-versioned producer decision.
- **extension boundary:** A new signature format or trust institution needs a typed verifier adapter and conformance evidence; a frontend label or arbitrary JSON field cannot grant authority.
- **resource behavior:** No second verifier index or trust store. Verify the exact permitted artifact and bound snapshot; if the trust set is unavailable or stale, return unknown/refused.


### Миграция и восстановление

Do not rewrite existing issuance records. Disable a consumer's verified cue on parse, binding, or verification failure while preserving the artifact and audit history; restore only after the same server gate is green.


### Композиция и owners

- The report-authentication result cannot imply any authority dimension. Keep each dimension and any absent trust/currentness input visible.
- P37: signature over resolved bytes and record binding may be recomputed; signer appointment, public-use rights, and external revocation facts must be content-bound and independently reconciled against their trusted owner sources before a positive claim. If they are only institutionally supplied, consumer asserted, or not_established, preserve refused/unknown.
- P38 divergence: a 'verified' badge based only on a valid signature remains green even when one authority dimension is not_established; the consumer must test the composed display, not merely a valid signature.
- R19 Q05 currentness composition consumes the actual LIF-02 scoped reaction and as-of result before the fresh UI-01 positive. Base signature authentication remains independently acceptable with currentness not_established; see the task conditional_acceptance_requirements.


### Acceptance и различающие проверки

- Positive: valid signature plus seven not_established dimensions shows authenticated report only across every named surface.
- Adversarial: forged, stale, revoked, foreign-tenant, wrong-view, or unavailable trust evidence stays refused/unknown.
- Removal: remove the server result but keep UI markers and prove every verified cue disappears.
- Accessibility: the status and its limits have a programmatic name/state and are announced without moving focus; qualified audience review confirms the copy does not imply policy authority.


### Входы и ответственность за их получение

- Accepted E02 tree and exact source-bound record.
- Actual trust/key, signer, rights, and revocation facts where those are held by an institution; the system cannot synthesize them.


### Когда обоснованно отклониться

- Any accepted-source rebind changes response meaning, currentness, or the authorized public view.
- A consumer requires a distinct trust-store protocol or an authority dimension not represented by the accepted contract.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [Frequently Asked Questions for OFR](https://www.archives.gov/federal-register/faqs) — NARA says each Federal Register issue and its published documents are permanent records; a published document cannot be altered or unpublished, and a correction, withdrawal or rescission requires the issuing agency to publish a new document. **Граница:** This is a US federal legal-record rule, not a PolicyOS authority grant. Transfer only the append-and-link history pattern; external institutions retain their own decision authority.
- [Web Content Accessibility Guidelines (WCAG) 2.2](https://www.w3.org/TR/WCAG22/) — WCAG 2.2 defines testable, technology-independent criteria. Relevant examples include text resize, reflow without loss at 320 CSS px, programmatic status messages, keyboard focus visibility/order, and name/role/value. **Граница:** WCAG conformance is scoped to the tested pages and criteria and does not establish human comprehension or an audience's understanding of policy meaning.
- [Guidance to meet the Plain Language standard](https://design.education.gov.uk/content-design/plain-language) — DfE distinguishes generic plain-English techniques from plain language adapted to user needs and user-research findings; technical terms can be retained where needed but should be explained. **Граница:** This is UK public-service guidance. It supports audience-qualified review as a method but does not establish the required PolicyOS audiences, locales, or wording.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/2013/REC-prov-o-20130430/) — PROV-O supplies interoperable Entity, Activity, and Agent provenance terms and relations for use, generation, attribution, derivation, and responsibility. **Граница:** A provenance vocabulary cannot prove lawful use, correct interpretation, source independence, institutional mandate, or PolicyOS admissibility.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-02"></a>

## UI-02 — Build publication capability and one data-only practice

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-02]`. Review: [root-review](root-review.md#UI-02).

### Предпочтительное решение

Ship one narrow public data-record practice through the existing producer, exact CAS view, issuance/verifier route, and shared public/MACHINE/CLI projection. Before applicable GY-PR1a evidence admits a real data-only record, publish only the typed refusal/chronology path. After the predicate is satisfied, issue the exact-view data-only record; keep the signer slot typed-empty until the actual signer policy is supplied. Preserve INT-K02 obligation membership, INT-K06 no-number wording, and INT-K08 refusal chronology. Keep the public path free of third-party trackers; classify and scrub request, beacon/fetch, and error telemetry before any signed persistence, including route/query/tags/breadcrumbs/extras. One exact DS12 record/view projects PUBLIC, REVIEWER, EXPERT and MACHINE through the existing authorized audience readers. Bind each actual reader/path at P0; UI-02 owns these same-record projections, UI-05 Clerk is not their substitute. Preserve exact edition, source/authority/audit refs, rule/schema version, limits and each audience permission; transport parity alone is insufficient. Missing internal readers are assigned UI-02 work. A genuinely uncommissioned channel needs an explicit source-qualified owner disposition and re-entry trigger; it does not silently close the original four-projection obligation or block independent public preparation.


### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/public_export.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `build_public_export_bundle`. Existing public-export producer includes official-use limits and the candidate firewall.
- `policy-engine/src/polisyos/runtime/http/routes/public_decisions.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `issue_public_decision_record`. Existing issuance route is the issue/verify bridge.
- `policy-engine/src/polisyos/core/artifacts/store.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `FileSystemCAS.get_bytes/get_manifest`. Existing CAS is the canonical artifact owner; carry selected manifest identity, not only blob bytes.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Rebind the exact accepted source, then satisfy the applicable GY-PR1a data-only condition for a real public record (do not add protected PR1b as a blanket prerequisite); separately resolve R9 anonymous-read, pending-intent, rights, tenant, and exact-view gates.
2. Join producer output to the exact ArtifactRef/profile, typed-empty authority slot, issue event, and accepted verifier; persist before projecting.
3. Use one owner-issued response in the citizen browser, MACHINE bundle, and read-only CLI/offline verifier; retain the same provenance, status, audience, rule/schema version, issue time, status-snapshot time, and currentness limits.
4. Exercise all actual egress builders before signing: routes, query parameters, tags, breadcrumbs, extras, beacons, fetch failures, and error telemetry. Block or scrub private fields before persistence; never equate an allowed telemetry destination with allowed content.
5. Retain the existing security-header, mobile, locale, plain-language, no-store and audit posture; do not move the publication logic into a CMS.
6. One exact DS12 record/view projects PUBLIC, REVIEWER, EXPERT and MACHINE through the existing authorized audience readers. Bind each actual reader/path at P0; UI-02 owns these same-record projections, UI-05 Clerk is not their substitute. Preserve exact edition, source/authority/audit refs, rule/schema version, limits and each audience permission; transport parity alone is insufficient. Missing internal readers are assigned UI-02 work. A genuinely uncommissioned channel needs an explicit source-qualified owner disposition and re-entry trigger; it does not silently close the original four-projection obligation or block independent public preparation.
7. The full original DS12 operational bar is enforced by source-bound CI against the built public route/actual responses and egress: no third-party trackers, owner-admitted Core Web Vitals budgets, security headers, mobile/responsive behavior, current DS0 locale posture and plain-language register. Reuse existing checks and bind missing ones to their native CI owners; no invented budget or posture-only PASS. If a budget is absent, the accountable frontend performance owner measures and proposes it; that internal criterion stays not_established until accepted, without blocking independent publication work. Automated checks establish their measured predicates, not human comprehension; retain qualified semantic audience review where required.


### Рассмотренные альтернативы

- **Publish a manually maintained static/CMS version of the decision.** — It would bypass exact CAS view, issuance, currentness, and rights gates, and could diverge from MACHINE/CLI.
- **Block reusable publication capability until an institutional signer is appointed.** — Signer absence gates a signature, not the capability; the typed-empty slot and refusal chronology remain useful.


### Free-grow и ресурсы

- **data or config growth:** Add public examples through admitted producer outputs and existing record/purpose config; obligation and no-number semantics travel with every projection.
- **extension boundary:** A new publication class, external signer protocol, or telemetry policy needs the owning typed contract and verifier/egress adapter; no free-form class can become signed authority.
- **resource behavior:** Reuse CAS and the existing issue index. Link large permitted sources by exact view; do not duplicate a second public store or invent size/latency targets before the pinned post-E02 measurement.


### Миграция и восстановление

Stop issuance/serving and return an explicit unavailable/refusal response on lost rights, bad binding, or leaked fields. Preserve prior signed bytes, refusal events, and audits; any correction is a new linked artifact.


### Композиция и owners

- GY-PR1 establishes whether the record is eligible; signer policy establishes whether a signature may be issued. The two gates are independent.
- P37: exact CAS digest/view is recomputed; rights, audience, pending intent, and signer appointment must be independently reconciled from exact owner evidence. If a decisive scope predicate is only consumer_asserted, institutionally_supplied without verification, or not_established, public bytes fail closed.
- P38 divergence: a signature and green browser badge can remain intact while a nested private field leaks through telemetry; verify the real egress property at all exits.
- Separate three predicates: capability/refusal surface; data-only issue after applicable PR1a evidence with signer slot empty where permitted; pilot/signature claim after PR1b plus the actual applicable signer/holder mandate. No institutional appointment is prerequisite for PR1a data-only issue.
- Audience (PUBLIC/REVIEWER/EXPERT/MACHINE) and transport (browser/API/client/CLI/audit) are separate axes. PR1a remains data-only, PR1b/signature requires its actual authority; private projection gaps cannot transfer content to public.


### Acceptance и различающие проверки

- Positive: before applicable PR1a evidence, expose refusal chronology; after PR1a, issue the permitted exact-view data-only record with empty signer slot where specified, without institutional appointment. Only the separate pilot/signature band requires PR1b and applicable signer/holder mandate. Check browser/MACHINE/CLI and audit parity in each band.
- Adversarial: candidate, wrong view/tenant, lost rights, pending intent, bad signature, or private proof/identifier never yields public bytes or telemetry leakage.
- Removal: remove the view/owner gate while keeping markers and show a served negative; remove request projection or pre-sign classification while keeping signature/badge and show egress detection fails.
- Accessibility/audience: check the original mobile, locale, security-header, and plain-language posture on the actual public page; no copy may convert the data record into a policy-authority claim.
- Actual public page: original WCAG 2.2 AA checks, keyboard/focus, 320-CSS-pixel reflow/large text, screen-reader order/status and no color-only authority/currentness cues. English-authored primary, Ukrainian translation, Russian legacy-frozen; preserve limitation meanings through audience-qualified plain-language review, without claiming comprehension from readability alone.
- Four-audience witness: actual selected readers consume one exact edition, preserving permitted provenance/authority/limits. Remove one audience gate or MACHINE source ref with labels intact; the fresh-consumer witness fails.
- The full original DS12 operational bar is enforced by source-bound CI against the built public route/actual responses and egress: no third-party trackers, owner-admitted Core Web Vitals budgets, security headers, mobile/responsive behavior, current DS0 locale posture and plain-language register. Reuse existing checks and bind missing ones to their native CI owners; no invented budget or posture-only PASS. If a budget is absent, the accountable frontend performance owner measures and proposes it; that internal criterion stays not_established until accepted, without blocking independent publication work. Automated checks establish their measured predicates, not human comprehension; retain qualified semantic audience review where required.
- Matched CI falsifier: delete the actual header/egress/layout/locale/performance protection with labels and CI configuration intact; the deciding behavioral check fails. No recursive verifier-of-verifier suite is required.


### Входы и ответственность за их получение

- A substantive GY-PR1 record/evidence outcome.
- Applicable signer/holder appointment and rule, public-use rights, audience, and exact-view permission decisions. Appointment applies only to the pilot/signature band; it does not gate the permitted PR1a data-only band.
- The selected self-hosted/scrubbed/absent telemetry policy.


### Когда обоснованно отклониться

- GY-PR1 remains blocked: keep refusal chronology; do not label the capability complete from a fixture.
- Any public route becomes anonymous without a reconciled exact-view/rights contract.
- A new telemetry destination or exporter changes the complete egress denominator.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [Frequently Asked Questions for OFR](https://www.archives.gov/federal-register/faqs) — NARA says each Federal Register issue and its published documents are permanent records; a published document cannot be altered or unpublished, and a correction, withdrawal or rescission requires the issuing agency to publish a new document. **Граница:** This is a US federal legal-record rule, not a PolicyOS authority grant. Transfer only the append-and-link history pattern; external institutions retain their own decision authority.
- [New govinfo API](https://www.govinfo.gov/features/api) — GovInfo describes unique package and granule identifiers, multiple content renditions, descriptive MODS metadata, and preservation PREMIS metadata including fixity. Its official record example separates an issue package from individual document granules. **Граница:** GovInfo's package model is an example, not a requirement to add a PolicyOS package database or adopt its IDs. Preserve the local exact ArtifactRef and selected manifest view.
- [Web Content Accessibility Guidelines (WCAG) 2.2](https://www.w3.org/TR/WCAG22/) — WCAG 2.2 defines testable, technology-independent criteria. Relevant examples include text resize, reflow without loss at 320 CSS px, programmatic status messages, keyboard focus visibility/order, and name/role/value. **Граница:** WCAG conformance is scoped to the tested pages and criteria and does not establish human comprehension or an audience's understanding of policy meaning.
- [Understand content design](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/plan-manage-content/understand-content-design/) — GOV.UK content design starts from user needs, considers the best format and place to publish, calls for clear accessible plain-English content, and distinguishes current content from historical content retained as a record. **Граница:** This is content guidance, not an archival retention standard and not a decision on PolicyOS Trust/Docs ownership.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-03"></a>

## UI-03 — Allocate accepted index and wire DS13 consumer

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-03]`. Review: [root-review](root-review.md#UI-03).

### Предпочтительное решение

Allocate and consume the existing GlobalCaseIndexProducer/default capability-discovery snapshot through the governed-projection waist. DS13 reads the same canonical snapshot and links each admitted case to its public record ID and exact source view/version. Treat the provider's candidate-only search rows as lookup material, not public admission; a case enters the public list only through the accepted owner receipt, DS12 public binding, exact-view check, and rights/tenant gate. Never mint another index or infer identity from aliases.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/global_case_index.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `GlobalCaseIndexProducer.produce`. Existing producer verifies the visible binding set and persists the candidate canonical snapshot.
- `policy-engine/src/polisyos/runtime/quality/capability_discovery.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `GlobalCaseIndexCapabilityDiscoveryProvider.search`. Existing default provider persists a fresh snapshot and owner receipt, then returns candidate-only search rows.
- `policy-engine/src/polisyos/runtime/http/routes/governed_projections.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `get_governed_projection`. Existing projection route is the public/MACHINE waist.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. After accepted E02 rebind, install the already-owned producer/provider result at the agreed public-record contract; UI-03 may prepare against interface agreement, but composed acceptance waits for actual DS12 output.
2. Resolve identity only from the canonical index and owner receipt; preserve record ID, selected manifest view, status, audience, issue/currentness times, and lineage.
3. Have browser, MACHINE, CLI, and receipt consumers render or serialize the same admitted snapshot through the projection waist.
4. Keep collisions, unresolved aliases, foreign tenants, private/revoked rights, and stale source bindings as unresolved/refused rows; never choose a nearest match.

### Рассмотренные альтернативы

- **Rebuild the index in the dashboard or add a second public-case database.** — It duplicates the accepted index producer/store and creates identity, freshness, and revocation drift.
- **Use capability-discovery search results directly as admitted public cases.** — The existing provider documents its results as candidate-only; search does not prove public rights or DS12 admission.

### Free-grow и ресурсы

- **data or config growth:** New cases enter through existing owner-issued bindings and the canonical producer, not a fixed subject list.
- **extension boundary:** A genuinely new identity source or alias protocol needs an owner-approved resolver adapter and collision semantics; ambiguous identity remains unresolved until that exists.
- **resource behavior:** One snapshot and one read path. Measure complete-set size after E02; if paging is needed, agree it with the existing index owner and do not create a parallel cursor.


### Миграция и восстановление

Disable the public index projection if readback, identity, rights, or freshness fails. Preserve canonical snapshots and old public record links; corrections append a new binding/supersession rather than rewriting earlier IDs.


### Композиция и owners

- Public membership is the composition of an accepted DS12 record binding, owner-receipt-bound index row, exact source view, permitted audience, and fresh tenant/rights checks.
- P37: identity resolution, source digest, and snapshot membership are recomputed from the owner receipt; rights/currentness and source authority must be independently reconciled from their owners. An unverified institutionally supplied or not_established predicate cannot admit a public case.
- P38 divergence: a case may be found by alias but collide with another canonical identity; successful search is not successful resolution or publication.


### Acceptance и различающие проверки

- Positive: each admitted case occurs once and carries its public record ID, exact view, status, and visible currentness/supersession state.
- Adversarial: collision, ambiguous alias, wrong tenant/view, private/revoked rights, stale binding, or candidate-only result remains unresolved.
- Removal: remove resolver/readback with markers retained and make the bridge witness fail across browser/MACHINE/CLI/receipt.
- Cross-surface: one owner snapshot is consumed everywhere; no consumer computes its own admitted-case set.


### Входы и ответственность за их получение

- Accepted DS12 record/index outputs and case identity bindings.
- Current tenant, public-rights, and source-status evidence from their actual owners.


### Когда обоснованно отклониться

- The accepted index contract changes or reveals a second existing owner.
- No content-bound owner receipt establishes the snapshot at the public projection seam.
- Identity ambiguity cannot be resolved under the current identity grammar.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [New govinfo API](https://www.govinfo.gov/features/api) — GovInfo describes unique package and granule identifiers, multiple content renditions, descriptive MODS metadata, and preservation PREMIS metadata including fixity. Its official record example separates an issue package from individual document granules. **Граница:** GovInfo's package model is an example, not a requirement to add a PolicyOS package database or adopt its IDs. Preserve the local exact ArtifactRef and selected manifest view.
- [Federal Register collection help](https://www.govinfo.gov/help/fr) — GovInfo distinguishes the official published Federal Register from its earlier public-inspection material and explains that a granule ID identifies one document inside an issue; it also has an explicit corrections section. **Граница:** The legal timing and status are specific to the Federal Register. Do not transfer its legal effects, and do not treat FederalRegister.gov's explicitly unofficial XML display as the authoritative record.
- [Data Catalog Vocabulary (DCAT) - Version 3](https://www.w3.org/TR/vocab-dcat-3/) — DCAT 3 distinguishes a resource's versions and previous-version chain, dataset series, and distributions such as different language or format representations; it also models issued and modified dates separately. **Граница:** DCAT is a dataset-catalog vocabulary. Its concepts may inform typed projections and links, but it is not a PolicyOS record schema or status/authority calculus.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/2013/REC-prov-o-20130430/) — PROV-O supplies interoperable Entity, Activity, and Agent provenance terms and relations for use, generation, attribution, derivation, and responsibility. **Граница:** A provenance vocabulary cannot prove lawful use, correct interpretation, source independence, institutional mandate, or PolicyOS admissibility.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-04"></a>

## UI-04 — Add DS13 consultation and immutable history

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-04]`. Review: [root-review](root-review.md#UI-04).

### Предпочтительное решение

Extend DS13 over the single canonical index and an append-only, typed consultation/response/supersession event source. Keep the closed decision bytes fixed; publish a new attributed event that references its exact record/version and states whether it is a formal institutional act, an informal statement, a correction, or PolicyOS's own claim reaction. No automatic dispute resolution and no presentation of consultation as binding. Use the existing access-audit trail only for authorized reads; do not repurpose it as the user-comment ledger. Public projection may expose only rights-cleared content, with withholding/consent decisions explicit and auditable. Append attributed response, revocation, supersession and law-7 learning-history events against the exact case/edition; produce the generic DS13 read-only transparency feed from that same canonical event/history source and UI-03 index. Browser/API/client/CLI/MACHINE/audit retain response-to-comment links, supersession lineage and the source-linked distinction “this case” versus “new evidence”. This description does not itself establish a causal effect or adopt an institutional act. Keep actor, authority, event/as-of time, rights and the separate LIF-02 currentness reaction. No second case store, notification service or automatic dispute resolution.


### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/routes/governed_projections.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `get_governed_projection`. Existing API projection waist carries replayable governed artifact views.
- `policy-engine/src/polisyos/runtime/http/access_audit.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `RuntimeDataAccessAuditTrail`. Existing owner covers authorization/read audit only; it is a companion, not a substitute for DS13 response history.
- `policy-engine/apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.tsx@dccea950845cda5b38f026e7770c07819d31f4d9` — `PublicDecisionViewerPage`. Existing browser route can consume the history projection after the event producer is named.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Resolve the actual DS13 event producer and LIF-02 currentness/right-cut interfaces during rebind; the assigned existing-path list does not name a producer symbol, so do not claim that access audit is already the consultation chain.
2. At accepted-source rebind bind the exact DS13 event/history, learning and feed producer/readers. Reuse an existing owner; if absent UI-04 allocates one typed append-only producer and its read-only feed under the actual runtime boundary, with all path companions in the lease. This is assigned internal work, not an external-input wait.
3. Agree the event contract before isolated consumer work: immutable parent ArtifactRef/profile, event ID and actor/authority provenance, event kind, relevant time roles, rights/consent posture, currentness relation, and whether the event is an external act or PolicyOS reaction.
4. Render and export the same ordered event lineage in browser, API/client, CLI, MACHINE, and audit; retain the original record and show which later item supersedes or revokes it.
5. Use WCAG 2.2 AA page-level checks plus actual keyboard, large-text/reflow, screen-reader order/labels/status announcements and audience-qualified plain-language review on consultation, response, and history content.
6. Follow accepted locale rules: English authored primary, Ukrainian translation, and Russian legacy_continuity_frozen; do not reactivate Russian by a locale badge or translation-presence check.


### Рассмотренные альтернативы

- **Edit the closed decision packet in place or keep only a latest-state row.** — Both erase the historical basis and make replay of what was public at an earlier time impossible.
- **Use access audit as the full consultation event store.** — Authorization audit proves access outcomes; it does not establish comment authorship, consent, institutional response, or policy decision authority.
- **Have PolicyOS adjudicate or auto-resolve consultation.** — External institutions decide; PolicyOS can record typed evidence and its own scoped claim reaction.


### Free-grow и ресурсы

- **data or config growth:** New response and supersession events append under the existing DS13 owner with exact parent/version, event type, audience, and time semantics.
- **extension boundary:** A new formal-response protocol requires a typed adapter and provenance verifier; comments or LLM summaries cannot become an authority class by wording or volume.
- **resource behavior:** History grows append-only. Bound each public projection by existing read/paging limits and rights scope; preserve lineage even when content is withheld, without inventing unlimited raw-body retention.


### Миграция и восстановление

On loss of consent, public rights, or currentness, withdraw the affected projection and expose an explicit permitted status; retain source event and prior public record history. Corrections are new events; never silently delete or relabel a response.


### Композиция и owners

- External response evidence, formal decision, informal statement, and PolicyOS claim reaction remain distinct event/authority types; no event closes another automatically.
- P37: event bytes and parent binding are recomputed; identity, consent, institutional status, and legal effect must be independently reconciled through content-bound source evidence. A bare institutional assertion, consumer assertion, or unknown may appear only as explicitly limited evidence, never as an authoritative public act.
- P38 divergence: a `response received` marker can remain green after the event join is removed, or a translated summary can alter meaning; verify event parity and human semantic review, not marker presence.
- The generic DS13 transparency feed and law-7 history are mandatory original deliverables. The separately conditional Phase 6.6 regulator channel and RuntimeDataAccessAuditTrail do not replace them.


### Acceptance и различающие проверки

- Positive: old bytes remain identical while attributable response and explicit supersession/revocation become visible on each named surface.
- Adversarial: mutation, self-assertion, auto-resolution, hidden lineage, collapsed status, private challenger disclosure without consent, silent removal, or informal consultation displayed as binding fails.
- Removal: remove the event join with markers retained and fail parity; remove large-text/screen-reader semantics or substitute meaning-changing copy and fail the corresponding audience check.
- Accessibility/plain language: qualified reviewers from the selected audiences assess actual text and meaning. A locale flag, translation presence, readability score, or WCAG pass alone is insufficient.
- Feed/history positive: persist a real event, then read the feed and history afresh across named transports with exact parent, time/authority roles and “this case”/“new evidence” distinction; MACHINE reconstructs permitted refs.
- Feed removal: delete the actual event-to-feed/history join with labels intact, or omit a learning event; the fresh producer→persisted-event→consumer witness fails. Preserve original bytes, access/consent, formal/informal and accessibility negatives.


### Входы и ответственность за их получение

- Actual external institutional responses, correction/revocation acts, and their signer/effect-time evidence.
- Contributor consent and applicable rights for making consultation content public.


### Когда обоснованно отклониться

- The DS13 ledger producer, privacy/consent owner, LIF-02 invalidation edge, or accepted locale contract is unbound.
- A claim of response-to-comment or appeal handling reaches beyond a typed evidence record into institutional case management.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [Frequently Asked Questions for OFR](https://www.archives.gov/federal-register/faqs) — NARA says each Federal Register issue and its published documents are permanent records; a published document cannot be altered or unpublished, and a correction, withdrawal or rescission requires the issuing agency to publish a new document. **Граница:** This is a US federal legal-record rule, not a PolicyOS authority grant. Transfer only the append-and-link history pattern; external institutions retain their own decision authority.
- [Web Content Accessibility Guidelines (WCAG) 2.2](https://www.w3.org/TR/WCAG22/) — WCAG 2.2 defines testable, technology-independent criteria. Relevant examples include text resize, reflow without loss at 320 CSS px, programmatic status messages, keyboard focus visibility/order, and name/role/value. **Граница:** WCAG conformance is scoped to the tested pages and criteria and does not establish human comprehension or an audience's understanding of policy meaning.
- [Guidance to meet the Plain Language standard](https://design.education.gov.uk/content-design/plain-language) — DfE distinguishes generic plain-English techniques from plain language adapted to user needs and user-research findings; technical terms can be retained where needed but should be explained. **Граница:** This is UK public-service guidance. It supports audience-qualified review as a method but does not establish the required PolicyOS audiences, locales, or wording.
- [Understand content design](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/plan-manage-content/understand-content-design/) — GOV.UK content design starts from user needs, considers the best format and place to publish, calls for clear accessible plain-English content, and distinguishes current content from historical content retained as a record. **Граница:** This is content guidance, not an archival retention standard and not a decision on PolicyOS Trust/Docs ownership.
- [Communicating quality, uncertainty and change](https://gss.civilservice.gov.uk/policy-store/communicating-quality-uncertainty-and-change/) — The GSS guidance recommends explaining source quality, uncertainty, limitations, context, and intended use so that readers can judge fit for use; it warns that excess certainty can prompt unsupported conclusions. **Граница:** The page is from 2018, currently marked under review, and says it has not incorporated accessibility legislation. It concerns statistics, so use only as a communication example, not as a PolicyOS rule or legal standard.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/2013/REC-prov-o-20130430/) — PROV-O supplies interoperable Entity, Activity, and Agent provenance terms and relations for use, generation, attribution, derivation, and responsibility. **Граница:** A provenance vocabulary cannot prove lawful use, correct interpretation, source independence, institutional mandate, or PolicyOS admissibility.
- [Data Catalog Vocabulary (DCAT) - Version 3](https://www.w3.org/TR/vocab-dcat-3/) — DCAT 3 distinguishes a resource's versions and previous-version chain, dataset series, and distributions such as different language or format representations; it also models issued and modified dates separately. **Граница:** DCAT is a dataset-catalog vocabulary. Its concepts may inform typed projections and links, but it is not a PolicyOS record schema or status/authority calculus.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-05"></a>

## UI-05 — Re-ground Clerk in G6 candidate and audit artifacts

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-05]`. Review: [root-review](root-review.md#UI-05).

### Предпочтительное решение

Re-ground the existing Clerk UI in the G6 session/choice/loss artifacts and their API/client bridge. Preserve candidate/refusal status, rejected choices, retained limitations, and authoritative_for=[] through every summary and reviewer export. When compression drops any required evidence or caveat, show a loss/refusal state rather than a fluent answer. Keep the surface REVIEWER/EXPERT only; Lex is DS10 and PUBLIC is out_of_scope.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/routes/control.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `launch_nl_run`. Existing control route launches the NL run through the runtime boundary.
- `policy-engine/src/polisyos/runtime/http/services/control/nl_pipeline.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `G6 session/choice/loss artifact orchestration seam`. Task's existing service path is the intended producer bridge; rebind exact accepted artifact names after E02.
- `policy-engine/apps/runtime-dashboard/src/features/clerk/routes/ClerkChatPage.tsx@dccea950845cda5b38f026e7770c07819d31f4d9` — `ClerkChatPage`. Existing Clerk candidate/refusal route is the only assigned surface.
- `policy-engine/apps/runtime-dashboard/src/features/clerk/components/ClerkStructuredResponse.tsx@dccea950845cda5b38f026e7770c07819d31f4d9` — `ClerkStructuredResponse`. Existing structured response consumer is the small presentation seam.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. At P0 rebind, identify exact G6 session/choice/loss artifact and `GY-I + DS9` gate outputs, including PA3 loss receipt and `not_measured` rider.
2. Carry source refs, rejected set, limitations, truncation/loss, candidate/refusal, and `authoritative_for` without re-labeling in summaries or MACHINE/CLI reviewer exports.
3. Add audit linkage from displayed candidate to the source artifact and decision path; preserve missing-audit or novel-status refusals.
4. Keep external actions out_of_scope unless the exact action invokes the DS9 PA2 gate and its coverage is bound.

### Рассмотренные альтернативы

- **Render only the assistant's final prose or summary.** — Fluency can hide rejected alternatives, compression loss, limitations, or absence of authority.
- **Create a public-facing AI approval/status page for Clerk.** — PUBLIC is explicitly out_of_scope and the route would create a second authority-like frontend.

### Free-grow и ресурсы

- **data or config growth:** New G6 evidence/loss reasons grow through the canonical typed artifacts; consumers must preserve unknown reasons as refusal/unknown.
- **extension boundary:** New workflow decisions require a G6 producer/schema extension and a loss-preserving consumer; free text cannot mint statuses or approvals.
- **resource behavior:** Bounded session artifacts and audit refs are consumed through existing endpoints; no duplicate conversation/history owner.


### Миграция и восстановление

On missing provenance, novel status, dropped limit, or truncated required content, suppress the grounded summary and render the existing refusal/candidate state; retain source artifacts and audit for reviewer replay.


### Композиция и owners

- Candidate evidence, rejected alternatives, loss status, and `authoritative_for=∅` remain attached to the same session/choice; the UI cannot upgrade them.
- P37: G6 artifact content and loss receipt must be resolved and content-bound; reviewer scope/authority requires independently reconciled mandate and decision evidence, not a UI role or self-asserted label. Without that binding, retain candidate/refusal.
- P38 divergence: the displayed summary may sound complete while its source artifact records compression loss; compare the actual summary against the retained loss receipt.


### Acceptance и различающие проверки

- Positive: candidate/refusal, rejected set, loss receipt, limitations, and authoritative_for=[] survive summary and audit.
- Adversarial: fluent text, missing audit, dropped limits, truncation, or novel status never gains authority.
- Removal: remove the provenance/loss join and show the grounded presentation disappears.
- Cross-surface restriction: prove PUBLIC stays out_of_scope; reviewer/expert MACHINE output is semantically consistent with Clerk.


### Входы и ответственность за их получение

- Accepted GY-I evidence and DS9 adjudicated gate; PA3 loss receipt and not_measured status.
- Any human reviewer decision remains a separate mandate-bound input.


### Когда обоснованно отклониться

- The accepted session/choice artifact differs from the named G6 interface or loses status/time/provenance semantics.
- Any proposed action consumer would make the Clerk path operational rather than candidate-only without the exact DS9 gate.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Web Content Accessibility Guidelines (WCAG) 2.2](https://www.w3.org/TR/WCAG22/) — WCAG 2.2 defines testable, technology-independent criteria. Relevant examples include text resize, reflow without loss at 320 CSS px, programmatic status messages, keyboard focus visibility/order, and name/role/value. **Граница:** WCAG conformance is scoped to the tested pages and criteria and does not establish human comprehension or an audience's understanding of policy meaning.
- [Guidance to meet the Plain Language standard](https://design.education.gov.uk/content-design/plain-language) — DfE distinguishes generic plain-English techniques from plain language adapted to user needs and user-research findings; technical terms can be retained where needed but should be explained. **Граница:** This is UK public-service guidance. It supports audience-qualified review as a method but does not establish the required PolicyOS audiences, locales, or wording.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/2013/REC-prov-o-20130430/) — PROV-O supplies interoperable Entity, Activity, and Agent provenance terms and relations for use, generation, attribution, derivation, and responsibility. **Граница:** A provenance vocabulary cannot prove lawful use, correct interpretation, source independence, institutional mandate, or PolicyOS admissibility.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-10"></a>

## UI-10 — Close DS1-N010 default-deny protected-chrome consumers

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-10]`. Review: [root-review](root-review.md#UI-10).

### Предпочтительное решение

Close only the original DS1-N010 default-deny consumer obligation through the existing DS5 C09 AuthzProvider/protected-chrome owner set. Rebind the accepted E02 source and determine which C09 consumers still fail the original negative before writing. Reuse the current AuthzProvider decision and C09 tests; do not route this obligation through AtlasRunDeck or the governed identity/status projection. DS20's HTTP authorization floor stays closed and outside this task.


### Что переиспользовать

- `policy-engine/docs/reference/frontend/atlas-live-application-audit.md@9f32d2706d60a5970d6fdd9ec9896242271a02ab` — `DS1-N010 at L822`. Original negative: /auth/me loading, network error, malformed response, or 401 must not grant analyst permissions/MFA or high-stakes CTA.
- `policy-engine/docs/plans/active/atlas-slices/DS5-enforcement-waist.md@9f32d2706d60a5970d6fdd9ec9896242271a02ab` — `DS5-C09a-R1/R2 N010 default deny`. Canonical consumer set, cross-surface negative, and source status still_required because C09 consumers remain.
- `policy-engine/apps/runtime-dashboard/src/app/authz/AuthzProvider.tsx@9f32d2706d60a5970d6fdd9ec9896242271a02ab` — `AuthzProvider`. Existing provider owns the client decision consumed by protected chrome; unknown identity must remain deny.
- `policy-engine/apps/runtime-dashboard/src/app/authz/AuthzProvider.test.tsx@9f32d2706d60a5970d6fdd9ec9896242271a02ab` — `test_authz_provider_denies_loading_error_malformed_401_prior_user_and_tenant_switch_identity`. Existing owner test covers the original response/fallback negative and identity transition siblings.
- `policy-engine/apps/runtime-dashboard/src/app/authz/authzDecisionSurfaces.test.tsx@9f32d2706d60a5970d6fdd9ec9896242271a02ab` — `test_unknown_authz_decision_never_defaults_authority_surface_to_allow`. Existing C09 behavioral witness exercises actual protected surfaces, not just provider shape.
- `policy-engine/docs/plans/active/atlas-slices/DS5-enforcement-waist.md@9f32d2706d60a5970d6fdd9ec9896242271a02ab` — `DS5-C09b-R1 mode/command/run/mobile cut and original disposition`. Completes the C09 consumer census; historical landing is not unqualified current acceptance.
- `policy-engine/apps/runtime-dashboard/src/features/runs/routes/runDetailSurfaces.test.tsx@9f32d2706d60a5970d6fdd9ec9896242271a02ab` — `actual RunDetailLayout loaded/bootstrap witness`. Cross-surface authz witness alone does not render this consumer; retain its separate source-qualified evidence.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. At accepted-source rebind, bind DS1-N010 to its audit criterion and DS5 C09 status; identify the exact still-open consumers and do not infer closure from a similarly named dashboard task. Rebind the complete original DS5 C09a/C09b consumer/disposition set, not just the named initial C09a paths. Include mode, command, loaded/bootstrap run-detail and mobile chrome witnesses; reuse already-landed C09b evidence only if exact accepted source still qualifies it. Preserve the declared bounded indirect-flow residual and falsifier. A missing required consumer leaves N010 open; no per-example closure or arbitrary-program-flow claim.
2. Exercise the existing AuthzProvider and C09 consumer set for loading, absence, network error, malformed response, 401, cached-prior-user, tenant-switch, partial permission, and full allow; preserve the fixed permission-free PUBLIC control.
3. Extend only the existing owner tests needed to cover the original N010 negative at each still-open consumer. Preserve the explicit C09 bounded indirect-flow residual/falsifier and DS5 scanner owner; do not claim arbitrary-flow proof.
4. Read back the accepted source status and test result. Do not close DS1-N010 from an identity label, AtlasRunDeck projection, DS20 HTTP denial, or scanner marker alone.


### Рассмотренные альтернативы

- **Bind DS1-N010 to AtlasRunDeck and a generic governed identity/status response** — The original criterion names /auth/me fallback and protected chrome; the cited readiness-reconciliation document does not bind DS1-N010.
- **Reopen DS20 or add a second page-local authorization rule** — DS20 remains closed; a server HTTP authorization floor does not replace the original AuthzProvider consumer property.


### Free-grow и ресурсы

- **data or config growth:** New protected chrome consumers reuse the one current AuthzProvider decision and join the accepted DS5 consumer census; no page-local permission table.
- **extension boundary:** A new permission/identity meaning changes its existing owner contract and all actual consumers; unsupported identity remains unknown/deny.
- **resource behavior:** Reuse the existing provider/query cache and source-bound response; no extra per-component identity query or registry.


### Миграция и восстановление

Keep fixed permission-free PUBLIC chrome. A failed migration, stale prior identity or missing current response leaves protected consumers denied; never restore a permissive placeholder. Preserve the DS5 bounded indirect-flow residual and its falsifier.


### Композиция и owners

- The original response-state negative is tested at the actual AuthzProvider and C09 protected consumers; `unknown` never yields permission, MFA, or high-stakes action.
- DS20 HTTP authorization remains a separate closed owner and supplies no credit for this client-side N010 criterion.
- P37/P38: the test resolves actual provider state and rendered/actionable consumers; matching placeholder copy or a missing marker is not the property.


### Acceptance и различающие проверки

- Positive: accepted verified identity exposes only its current permissions; fixed permission-free PUBLIC chrome remains visible.
- Adversarial: loading, absent, error, malformed, 401, cached-prior-user, tenant-switch, and pseudo-flag inputs do not grant protected UI or action.
- Removal: remove the current verified-decision guard with status labels intact; the existing C09 cross-surface witness fails on a protected consumer.
- Source disposition: DS1-N010 remains still_required until the accepted original negative and required consumer set are proven closed.
- Rebind the complete original DS5 C09a/C09b consumer/disposition set, not just the named initial C09a paths. Include mode, command, loaded/bootstrap run-detail and mobile chrome witnesses; reuse already-landed C09b evidence only if exact accepted source still qualifies it. Preserve the declared bounded indirect-flow residual and falsifier. A missing required consumer leaves N010 open; no per-example closure or arbitrary-program-flow claim.


### Входы и ответственность за их получение

- Accepted E02 tree and current DS1-N010 source disposition.
- Exact DS5 C09 consumers/tests still required by the original audit negative.


### Когда обоснованно отклониться

- Accepted E02 rebind shows DS1-N010 already closed by the exact original consumers; reconcile its source disposition instead of duplicating DS5 work.
- A remaining consumer or test has a different canonical owner; bind that exact source path and add only its producer/consumer companion.
- A claimed closure depends on a DS20 HTTP check or placeholder/identity projection rather than the N010 client consumer.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Основание исправления

Исходный DS1-N010 и DS5 C09 source-bound критерий, указанные выше, определяют
эту задачу. R20 исправляет ошибочную привязку к AtlasRunDeck; прежний review
сохраняется как история. Runtime-проверки здесь не выполнялись.

<a id="UI-15"></a>

## UI-15 — Resolve Trust Center/Docs IA successor scope, then deliver assigned content

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-15]`. Review: [root-review](root-review.md#UI-15).

### Предпочтительное решение

Prepare an owner decision, not a new site. Recommend a narrow split for architect adjudication: DS11 owns evidence-bound Trust claim/MACHINE posture and its dated/versioned source artifacts; the existing Docs/marketing owner owns the user-needs-based landing/article IA and explanatory copy, with canonical links back to DS11 evidence. If that owner does not exist, keep the content absent/unallocated instead of creating a CMS or silently assigning DS11. Both halves must consume the same claim status and source lineage; no second claim register, download publisher, DS12/DS13 record/history, or resurrection of W0-W10.

### Что переиспользовать

- `policy-engine/docs/plans/active/atlas-slices/DS11-trust-docs-posture.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `DS11 mission, boundary, and opening capability state`. The DS11 plan says its opening chain is absent/unallocated and excludes a general documentation portal/procurement trust center; treat this as a planning boundary, not implementation evidence.
- `policy-engine/docs/plans/active/POLICYOS_ATLAS_PRODUCT_MARKETING_CLIENT_SURFACES_MASTER_PLAN.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `Phase 2.11 Trust Center / Phase 2.15 Public Docs IA`. Retained old-plan material is input to a successor-owner decision; it is not a current product owner assignment.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/workstreams/04-atlas.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `UI-15 / DS11 Trust Center + docs IA`. Current task row keeps scope/owner blocked until architect resolution and calls for no W0-W10 carryover.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Record the competing scopes and their unique retained content: DS11 evidence/claim posture, dated/versioned evidence downloads, and public docs landing/article IA.
2. Submit the split above as a proposed owner allocation to the competent architect; the allocation itself remains unresolved until recorded.
3. If accepted, render claim/status/source/version/date and canonical links from the existing DS11 posture/MACHINE artifact; let the already-owned docs surface present explanatory IA without authoring claim status.
4. If rejected or no docs owner is appointed, preserve the blocked/absent-unallocated state and keep the unique content as a source-qualified decision item.

### Рассмотренные альтернативы

- **Give Atlas/DS11 the entire documentation portal and marketing IA.** — DS11 explicitly excludes a general docs portal and would create a new sovereign content owner.
- **Let marketing copy author or restate supported/blocked claims.** — Copy can drift from claim evidence, date, and authority; signature/authentication would be easy to misread as policy authority.
- **Create a new CMS or second generated claim register.** — It creates another publisher and synchronization lifecycle without resolving the owner question.

### Free-grow и ресурсы

- **data or config growth:** Claim rows grow only from the canonical producer/posture artifact; explanatory pages grow through the appointed existing content owner and user needs.
- **extension boundary:** A new evidence claim family needs its producer and source binding; a new docs function needs explicit owner scope. Neither is enabled by arbitrary free-text copy.
- **resource behavior:** Use existing generated artifact and content route if the architect selects them; no new CMS, registry, or long-lived cache.


### Миграция и восстановление

Do not release either public route until allocation and evidence contracts are recorded. If allocation is withdrawn, stop the docs/projection surface but preserve canonical posture artifacts and source/history links.


### Композиция и owners

- The Trust claim owner emits authority-bearing posture; the docs owner may explain and link but cannot strengthen claim status.
- P37: architect allocation is independently_reconciled only when the decision is recorded and content-bound; a task ID, old plan, or marketing copy is not that evidence. Claim support is recomputed from bound evidence. A proposed or unbound allocation remains not_established and blocks dispatch.
- P38 divergence: a page may display stale 'certified' copy while the MACHINE claim is blocked; compare rendered text and downloads to the live typed posture, not route existence.


### Acceptance и различающие проверки

- Decision signal: a competent architect records the Atlas-versus-Docs owner, unique content boundary, canonical source, and evidence contract.
- Positive after allocation: each public claim has bound evidence or explicit planned/blocked posture plus source/version/date and canonical documentation link.
- Adversarial: unsupported certification, stale copy, signature-as-policy-authority, contradictory duplicate, or private evidence never looks supported.
- Removal: remove status binding while leaving copy and make semantic/audience review fail; no site build alone closes scope.


### Входы и ответственность за их получение

- Competent architect's recorded owner/scope decision.
- Actual content owner and rights to publish selected source artifacts.
- Substantive claim evidence or explicit planned/blocked posture.


### Когда обоснованно отклониться

- No existing docs owner can accept the IA, or the architect selects a materially different split.
- A proposed landing page would create a general documentation, procurement, compliance, or case-management subsystem.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Frequently Asked Questions for OFR](https://www.archives.gov/federal-register/faqs) — NARA says each Federal Register issue and its published documents are permanent records; a published document cannot be altered or unpublished, and a correction, withdrawal or rescission requires the issuing agency to publish a new document. **Граница:** This is a US federal legal-record rule, not a PolicyOS authority grant. Transfer only the append-and-link history pattern; external institutions retain their own decision authority.
- [New govinfo API](https://www.govinfo.gov/features/api) — GovInfo describes unique package and granule identifiers, multiple content renditions, descriptive MODS metadata, and preservation PREMIS metadata including fixity. Its official record example separates an issue package from individual document granules. **Граница:** GovInfo's package model is an example, not a requirement to add a PolicyOS package database or adopt its IDs. Preserve the local exact ArtifactRef and selected manifest view.
- [Guidance to meet the Plain Language standard](https://design.education.gov.uk/content-design/plain-language) — DfE distinguishes generic plain-English techniques from plain language adapted to user needs and user-research findings; technical terms can be retained where needed but should be explained. **Граница:** This is UK public-service guidance. It supports audience-qualified review as a method but does not establish the required PolicyOS audiences, locales, or wording.
- [Understand content design](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/plan-manage-content/understand-content-design/) — GOV.UK content design starts from user needs, considers the best format and place to publish, calls for clear accessible plain-English content, and distinguishes current content from historical content retained as a record. **Граница:** This is content guidance, not an archival retention standard and not a decision on PolicyOS Trust/Docs ownership.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/2013/REC-prov-o-20130430/) — PROV-O supplies interoperable Entity, Activity, and Agent provenance terms and relations for use, generation, attribution, derivation, and responsibility. **Граница:** A provenance vocabulary cannot prove lawful use, correct interpretation, source independence, institutional mandate, or PolicyOS admissibility.
- [Data Catalog Vocabulary (DCAT) - Version 3](https://www.w3.org/TR/vocab-dcat-3/) — DCAT 3 distinguishes a resource's versions and previous-version chain, dataset series, and distributions such as different language or format representations; it also models issued and modified dates separately. **Граница:** DCAT is a dataset-catalog vocabulary. Its concepts may inform typed projections and links, but it is not a PolicyOS record schema or status/authority calculus.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-16"></a>

## UI-16 — Keep DS11 performance claims blocked until grounded evidence

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-16]`. Review: [root-review](root-review.md#UI-16).

### Предпочтительное решение

Keep DS11-GROUNDED-PERFORMANCE blocked/not_established. A public Trust Center or signed report is not performance evidence. The claim can move only after a substantive promoted-design artifact is bound to the exact claim, design/source, evaluation basis, relevant epoch/time, rule version, limits, and target audience. Until then, show the typed blocker and evidence gap; do not turn a fixture, benchmark placeholder, or report-authentication result into a green claim.

### Что переиспользовать

- `policy-engine/docs/plans/active/atlas-slices/DS11-trust-docs-posture.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `CC18 grounded-performance claim gate`. DS11 posture contract explicitly requires content-bound governed-performance evidence and leaves the row blocked when that producer/prerequisite is absent.
- `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `DS12 governed publication gate`. The publication plan separates record/report authentication from substantive promoted-design evidence.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Keep the typed status and reason in DS11 MACHINE and any approved public Trust/docs view; expose an honest 'not established' explanation and the missing evidence class.
2. When genuine evidence later exists, bind it to the exact claim and artifact bytes, evaluation scope and population, metric definition, comparator/baseline, rule version, design epoch, review time, and audience/use limitations.
3. Recompute the posture from that binding; require the appropriate independent review and revalidate when design, evidence, rule, or epoch changes.
4. Keep any numbers out of the current view until a real promoted design and its substantive evidence pass the binding rule; do not fabricate a threshold in this proposal.

### Рассмотренные альтернативы

- **Infer performance from report-signature validity, Trust Center presence, synthetic fixtures, or placeholder benchmarks.** — Those establish neither policy-design performance nor a representative evaluation; the original row explicitly rejects them.
- **Hide the claim row until evidence exists.** — Hiding it conceals the known limitation; the existing typed blocked/not_established posture is more honest and reviewable.

### Free-grow и ресурсы

- **data or config growth:** Each future claim binds to its own substantive promoted-design evidence and validity epoch; new metric families grow through their actual producer and typed evidence contract.
- **extension boundary:** New performance metric, population, or design class needs an owner-specified evaluation contract and independent oracle; a generic numeric field or marketing text does not qualify.
- **resource behavior:** Do no benchmark computation in this surface. Consume a bounded content-bound evidence artifact and its review receipt; stale or oversized evidence is linked through the permitted view.


### Миграция и восстановление

On evidence revocation, stale epoch, changed rule, or broken content binding, return the posture to blocked/not_established and append the status transition; retain the historical claim and evidence refs.


### Композиция и owners

- Support requires an actual promoted design plus substantive, content-bound evidence for this exact performance claim; publication/authentication is an independent predicate.
- P37: evidence binding is recomputed; promotion and review authority must be independently reconciled to the exact source/evidence. A bare external assertion, placeholder, or unestablished review cannot support the claim.
- P38 divergence: a green status marker may survive after removing the evidence binding; the consumer must recompute the claim-to-artifact join.


### Acceptance и различающие проверки

- Positive: absent substantive promoted-design evidence yields no supported performance assertion.
- Adversarial: valid report authentication, benchmark placeholder, synthetic fixture, or stale/different-design evidence cannot satisfy the claim.
- Removal: remove the evidence binding but retain the green marker and confirm review refuses.
- Cross-surface: Trust Center, public docs, and DS11 MACHINE all show the same blocked/not_established source status and time.


### Входы и ответственность за их получение

- Substantive promoted-design evidence from its canonical producer, including exact design/source and epoch.
- Required independent review or institutional limits on the claim's use.


### Когда обоснованно отклониться

- A proposed performance claim lacks a defined population, metric, comparator, design epoch, or source artifact.
- Evidence exists only as a synthetic fixture, summary prose, signature proof, or unaudited benchmark.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Communicating quality, uncertainty and change](https://gss.civilservice.gov.uk/policy-store/communicating-quality-uncertainty-and-change/) — The GSS guidance recommends explaining source quality, uncertainty, limitations, context, and intended use so that readers can judge fit for use; it warns that excess certainty can prompt unsupported conclusions. **Граница:** The page is from 2018, currently marked under review, and says it has not incorporated accessibility legislation. It concerns statistics, so use only as a communication example, not as a PolicyOS rule or legal standard.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/2013/REC-prov-o-20130430/) — PROV-O supplies interoperable Entity, Activity, and Agent provenance terms and relations for use, generation, attribution, derivation, and responsibility. **Граница:** A provenance vocabulary cannot prove lawful use, correct interpretation, source independence, institutional mandate, or PolicyOS admissibility.
- [Data Catalog Vocabulary (DCAT) - Version 3](https://www.w3.org/TR/vocab-dcat-3/) — DCAT 3 distinguishes a resource's versions and previous-version chain, dataset series, and distributions such as different language or format representations; it also models issued and modified dates separately. **Граница:** DCAT is a dataset-catalog vocabulary. Its concepts may inform typed projections and links, but it is not a PolicyOS record schema or status/authority calculus.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.
