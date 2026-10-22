# Содержательные основания: предпочтительные решения

Статус: engineering recommendations; product execution UNRUN. Реализация только после E02 acceptance и полного affected-scope rebind. Исходные критерии не сокращаются; [общие решения](00-shared-decisions.md) предотвращают второго owner. [Нормативные уточнения](decision-clarifications.md) остаются предложениями.

<a id="CNT-01"></a>

## CNT-01 — Reconcile decision slice and commission owners (W0)

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CNT-01]`. Review: [root-review](root-review.md#CNT-01).

### Предпочтительное решение

Keep CNT-01 as one case-scoped commissioning record owned by the Runtime integrator. The sponsor commissions the real policy question, purpose, decision boundary, constraints, audience and accountable principal. PolicyOS may derive and compare candidate claims, intervention atoms, estimands and gaps; the selected claim/scope is then fixed before its protected use; the integrator resolves the gap predicate to a named existing owner, a persisted output, a consumer and a justified refresh condition. Record a typed blocker when the supplier, authority, route or permission is not selected. Treat source cards, family names, URLs, model suggestions and search no-hits as candidate discovery only. The record is a routing and accountability artifact, not a central foundations registry or approval.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/services/acquisition_action_service.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `acquisition action service module`. Named as a verified existing anchor in the input. Location only; current behavior and E02 acceptance must be rebound.
- `policy-engine/src/polisyos/runtime/quality/acquisition_executor.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `execute_live_catalog_acquisition`. Symbol exists at the historical source pin and is an acquisition route anchor, not proof of a complete selected-case chain.
- `policy-engine/src/polisyos/fabric/catalog/binding.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `CatalogBinding.bind_from_registry`. Symbol exists at the historical source pin; reuse only after current source and consumers are rebound.
- `policy-engine/src/polisyos/evidence/claims/claim_registry.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `normalize_runtime_claim_registry`. Symbol exists at the historical source pin and can bind claim context; it does not itself commission a sponsor or supplier.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. After accepted E02 and scoped rebind, census the real routes and consumers for the sponsor's one selected claim and its gaps.
2. For each material gap, persist need, scope, evidence grade, eligible route, named answerer, rights ceiling, delivery artifact, consumer effect and next action; preserve unknown, unavailable, denied, no-hit and verified-absence separately.
3. Link the owner response to the request and expose owner/blocker/refresh state in the existing request and Expert/Machine audit surfaces.

### Рассмотренные альтернативы

- **Harvest the full 26-family editorial map or 197 source cards before selecting a case.** — Editorial completeness adds cost while proving neither relevance nor admission; only selected facets become acquisition edges.
- **Create a global foundation service or let an LLM assign an owner and authority.** — That bypasses native semantic owners and transfers commissioning responsibility to a projection or candidate generator.

### Free-grow и ресурсы

- **data or config growth:** Add case request instances and route mappings within the accepted facet grammar; the existing acquisition planner/catalog resolve supported source classes.
- **extension boundary:** A genuinely new semantic class or institutional role needs a typed owner adapter, named verifier, consumer mapping and conformance evidence before it can discharge a gate.
- **resource behavior:** Keep discovery scoped to the case and justified decision value; a budget cutoff emits an incomplete request with the remaining gap visible, never a verified absence.


### Миграция и восстановление

Reuse existing request, source, claim and artifact references; do not backfill old editorial cards as commissioned cases. Rescope or close append-only, retaining denial and blocker history.


### Композиция и owners

- Sponsor selection is a human-supplied premise; the integrator may recompute whether selected facets have a mapped owner and consumer.
- A selected gap is complete only when it routes to a native producer and fresh consumer or a costed refusal that changes the dependent claim status.
- Reconcile the current common grammar/routes/limits for all 26 foundation families and evidence for each claimed class. Case-specific acquisition does not require harvesting all 197 source cards, but one successful case cannot close the separate all-family grammar obligation. No new global scheduling barrier is introduced.


### Acceptance и различающие проверки

- A real selected gap maps to a named owner or priced refusal and reaches the audit surface.
- Offering only a URL, source card, family label or no-hit leaves the gap candidate/unknown.
- Removing reconciliation leaves no way to state who answers the gap or which consumer uses the output.


### Входы и ответственность за их получение

- Commissioning sponsor names the case, decision, scope and authorized answerers.
- Actual supplier/custodian provides or denies the route; responsible institution supplies authority and permission.


### Когда обоснованно отклониться

- Sponsor cannot identify the decision or authority: preserve a not-selected blocker and do not invent a pilot.
- The source or semantic owner differs from the mapped route: pause only the affected closure and rebind its exact consumer set.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Data Catalog Vocabulary (DCAT) Version 3](https://www.w3.org/TR/vocab-dcat-3/) — DCAT 3 distinguishes cataloged datasets, distributions, data services and dataset series; it adds version/current-version relations and supports multiple representations and temporal/spatial metadata. **Граница:** A catalog vocabulary supports interoperability and discovery. It does not establish that content is authentic, lawful to reuse, applicable, current for a claim, or authoritative.
- [Cochrane Handbook, Chapter 4: Searching for and selecting studies](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04) — Cochrane recommends searches matched to eligibility criteria, broad source coverage, reproducible exact search strategies and record counts, and distinguishes reports from underlying studies. **Граница:** Search recommendations arise from health evidence synthesis and need adaptation to other fields, languages, source types and lawful access constraints.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="CNT-02"></a>

## CNT-02 — Onboard source-library metadata and supported classes (data/config only)

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CNT-02]`. Review: [root-review](root-review.md#CNT-02).

### Предпочтительное решение

Extend the existing catalog and source registry with versioned descriptive metadata and source-class routing. Use DCAT 3 as an interchange mapping for catalog, dataset, distribution, service, series and version relations; keep native PolicyOS types and validators canonical. Store issuer/publisher identity, resource and version identifiers, representation/language/media type, coverage, jurisdiction, access-level, update cadence, access method, license or declared access limit, and provenance references. Keep content authenticity, rights for a particular use, legal applicability and freshness as separate admission decisions. A search extract, abstract or metadata-only card must never satisfy a content-bound gate.

### Что переиспользовать

- `policy-engine/src/polisyos/fabric/catalog/discovery.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `SemanticDatasetCatalog`. Existing catalog class is named in the input and present at the historical source pin; no claim that its metadata already covers every source class.
- `policy-engine/src/polisyos/data_forge/domains/catalog/registry.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `CatalogSourceRegistryEntry`. Existing registry entry is present at the historical source pin and is the first place to assess for source-class metadata.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Agree the smallest metadata profile with each source and content owner; map DCAT fields into native source records without replacing the registry.
2. Add owner-local versioned records for the selected source classes and route them to the right validators: statistical definitions to measurement owners, law to legal owners, studies to evidence owners, and testimony/mandates to their custodians.
3. Validate metadata shape and version links, but separately resolve bytes or query receipt, permission, applicability and currentness at each intended use.
4. Carry jurisdiction and access-level explicitly in the existing source profile, separately from access method and license; prove any native-field mapping lossless for public/query-only/restricted sources with differing jurisdiction.

### Рассмотренные альтернативы

- **Install a second universal source catalog or make every source card a production artifact.** — This creates parallel ownership and implies evidentiary completeness from editorial presence.
- **Adopt a generic RDF/SHACL stack as the new authority engine.** — DCAT and SHACL provide interoperability and structural checks, not the semantic admission rules; use them only where current owner formats benefit.

### Free-grow и ресурсы

- **data or config growth:** Supported source classes grow through registry rows, mapping profiles and versioned owner rules; new instances require no code when their semantic/protocol class is already supported.
- **extension boundary:** A new transport or semantic meaning requires an owner-approved adapter and conformance check; unknown classes stay unadmitted and cannot inherit a permissive default.
- **resource behavior:** Catalog growth increases metadata and index work, not content transfer. Search results remain bounded by source-specific limits and report coverage/cutoff.


### Миграция и восстановление

Add rows through an additive registry generation and retain previous identities/versions. Restore the last validated generation on failure; do not infer rights or authority during migration.


### Композиция и owners

- The catalog returns a resolvable resource/version/representation and supported owner route; the source owner validates content and use.
- A valid catalog record is discovery evidence only and cannot promote claim status.


### Acceptance и различающие проверки

- A supported class resolves to its native owner and validator; unknown class remains unadmitted.
- An abstract, mirror, alias, stale consolidation or changed edition cannot pass a content-bound gate.
- Removing the class-specific validator while keeping the catalog row prevents admission.


### Входы и ответственность за их получение

- Issuer or publisher supplies its identifiers, versions, distribution and update information.
- Rights holder and source owner state actual terms and use limits where those facts are not machine resolvable.


### Когда обоснованно отклониться

- A class has no source identity/version resolver or validator: mark it unsupported and name the needed adapter owner.
- Publisher changes versioning or API semantics without a stable crosswalk: retain prior version and mark current resolution unknown until reconciled.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Data Catalog Vocabulary (DCAT) Version 3](https://www.w3.org/TR/vocab-dcat-3/) — DCAT 3 distinguishes cataloged datasets, distributions, data services and dataset series; it adds version/current-version relations and supports multiple representations and temporal/spatial metadata. **Граница:** A catalog vocabulary supports interoperability and discovery. It does not establish that content is authentic, lawful to reuse, applicable, current for a claim, or authoritative.
- [Shapes Constraint Language (SHACL)](https://www.w3.org/TR/shacl/) — SHACL validates an RDF data graph against a versioned shapes graph and can emit a validation report. **Граница:** SHACL is a possible validation format when an owner already uses RDF. Structural conformance alone is not semantic adequacy or authority, and adopting it would not justify a second registry.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — PROV-O provides reusable relations among entities, activities and agents, including generation, use, derivation and attribution, for expressing lineage. **Граница:** A lineage graph records declared provenance. It does not prove independence, factual truth, legal permission, or source quality unless those properties have their own evidence and verification.
- [OECD SDMX API](https://www.oecd.org/en/data/insights/data-explainers/2024/09/api.html) — The OECD documents separate data queries from structure queries and identifies agency, dataset and dataset version as components of a data query. **Граница:** API structure and version paths help bind a query and representation. They do not prove completeness, fitness for a local estimand, or stable availability.
- [World Bank Indicators API basic call structures](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581) — The API documents date and source parameters, language variants, page and per_page controls, and returns pagination metadata such as page count and total records. **Граница:** The endpoint requires complete paging and exact parameter capture where paging is used. The API describes an aggregate indicator service, not a selected case source or household-level dataset.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="CNT-03"></a>

## CNT-03 — Acquire exact representations and admit purpose-bounded reuse (W1)

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CNT-03]`. Review: [root-review](root-review.md#CNT-03).

### Предпочтительное решение

Reuse the acquisition planner/executor, epoch admission, Fabric CAS and lineage, and existing security/retention owners. For a file source, persist the exact received representation and its issuer/version, content digest, request and response details, peer/redirect chain, scope, relevant time roles, transformations and lineage. For a custodian-query source, keep raw rows at the custodian and persist a permitted query/result receipt with the query, protocol, version, scope and verifier. Bind the actual permission instrument to principal, purpose, audience, processor, transformations, retention and revocation. Recheck permission and freshness for each use; cache presence, public URL, ETag, or citation is not permission or currentness. Preserve the existing WDI single-response rule: excess pages are explicit incomplete/refusal, not silent truncation.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/acquisition_executor.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `execute_live_catalog_acquisition`. Existing live catalog acquisition entry point is present at the historical pin; task input identifies it as a route, not an end-to-end proof.
- `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `AcquisitionPlanner`. Existing planner class is present at the historical pin and can be assessed for the selected route.
- `policy-engine/src/polisyos/runtime/quality/acquisition_epoch_admission.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `AcquisitionEpochAdmissionRequest`. Admission request type exists at the historical pin; current checks and their consumers require post-E02 rebind.
- `policy-engine/src/polisyos/fabric/storage/tenant_cas.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `TenantScopedCAS`. Tenant-scoped content-addressable storage exists at the historical pin; CAS identity is not permission or truth.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Bind each acquisition action to request, principal, route, source version, exact response representation or query receipt, request parameters and completion state.
2. Persist only the permitted artifact/receipt through existing CAS and lineage boundaries; keep query-only content out of CAS, logs, browser state and provider temporaries.
3. At fresh consumption, resolve use-purpose and current rights evidence and produce admitted, limited, denied or incomplete status with affected-use links.

### Рассмотренные альтернативы

- **Treat catalog URL, cache hit, publisher checksum or HTTP 304 as reusable evidence.** — These can identify a resource or unchanged response without proving the original body, grant, intended use or lawful retention.
- **Fetch pages until exhaustion or scrape mirrors by default.** — Unbounded or unapproved capture expands resource and rights risk; keep the agreed single-response route and return an explicit partial state.

### Free-grow и ресурсы

- **data or config growth:** Add supported source definitions, query profiles and purpose-bound permission references through existing owners; do not add another fetcher or rights ledger.
- **extension boundary:** New transport, credential or query-only mode needs a typed adapter plus durable receipt and sink/use conformance before protected calls.
- **resource behavior:** Use current executor quotas and response limits; if response/paging/time limits are reached, persist the terminal incomplete state and resume only through an approved route.


### Миграция и восстановление

Retain prior receipts and artifacts by generation. On denial, revocation or changed purpose, withdraw affected use and cascade to dependents without deleting provenance history.


### Композиция и owners

- Capture emits a durable receipt/artifact; epoch admission binds that result to fresh use, purpose and audience.
- Rights are external evidence; storage and retrieval may not broaden the grant.


### Acceptance и различающие проверки

- Same artifact can be reused only for an admitted matching use and audience after fresh admission.
- Revoked or purpose-mismatched grant, unapproved redirect, missing prior body behind 304, foreign tenant, incomplete pages or forged citation fails closed.
- Removing receipt or content-bound permission resolution prevents fresh protected use even when cache/catalog labels remain.


### Входы и ответственность за их получение

- Named source custodian supplies the actual response or approved query-result receipt.
- Rights holder or competent institution provides the signed grant/basis and correction or revocation route.


### Когда обоснованно отклониться

- No lawful basis, processor permission or retention limit is established: keep raw content out of the system and return a bounded refusal.
- Source protocol introduces pagination, resumable transfer or a new peer: require the owner for that protocol and recovery state before enabling it.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Data Catalog Vocabulary (DCAT) Version 3](https://www.w3.org/TR/vocab-dcat-3/) — DCAT 3 distinguishes cataloged datasets, distributions, data services and dataset series; it adds version/current-version relations and supports multiple representations and temporal/spatial metadata. **Граница:** A catalog vocabulary supports interoperability and discovery. It does not establish that content is authentic, lawful to reuse, applicable, current for a claim, or authoritative.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — PROV-O provides reusable relations among entities, activities and agents, including generation, use, derivation and attribution, for expressing lineage. **Граница:** A lineage graph records declared provenance. It does not prove independence, factual truth, legal permission, or source quality unless those properties have their own evidence and verification.
- [OECD SDMX API](https://www.oecd.org/en/data/insights/data-explainers/2024/09/api.html) — The OECD documents separate data queries from structure queries and identifies agency, dataset and dataset version as components of a data query. **Граница:** API structure and version paths help bind a query and representation. They do not prove completeness, fitness for a local estimand, or stable availability.
- [OECD API best practices and recommendations](https://www.oecd.org/en/data/insights/data-explainers/2024/11/Api-best-practices-and-recommendations.html) — The OECD recommends its content-constraint query as a way to read a dataset ValidFrom time and observation count and check whether a dataset version changed. **Граница:** A change detector is a trigger for refresh and revalidation, not an integrity, currentness, or applicability verdict.
- [World Bank Indicators API basic call structures](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581) — The API documents date and source parameters, language variants, page and per_page controls, and returns pagination metadata such as page count and total records. **Граница:** The endpoint requires complete paging and exact parameter capture where paging is used. The API describes an aggregate indicator service, not a selected case source or household-level dataset.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="CNT-04"></a>

## CNT-04 — Resolve law, effectivity, competence and actual acts (W4)

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CNT-04]`. Review: [root-review](root-review.md#CNT-04).

### Предпочтительное решение

Extend the canonical legal corpus and applicability route with source-bound legal-version and event relations. Retain the exact original text and each amendment/correction separately; resolve the requested as-of date to the jurisdiction's provision version and carry publication, commencement, effective, expiry, repeal, exception, transition and notice times as distinct facts. A qualified legal reviewer binds the exact provision to the intervention lever and states uncertainty or unresolved notice. Keep issuer/delegation/competence evidence and each actual act with recipient, scope, conditions, effect and revocation as separate evidence. The system consumes these records and may return limited or blocked status; neither legal text, a signature, nor a parser supplies the legal judgment.

### Что переиспользовать

- `policy-engine/src/polisyos/data_forge/domains/legal/corpus/ingest.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ingest_legal_doc_bytes`. Canonical ingestion function exists at the historical pin; it identifies an ingest route, not legal applicability.
- `policy-engine/src/polisyos/data_forge/domains/legal/corpus/structure.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `build_legal_structure`. Legal structure builder exists at the historical pin and is an owner-local structure anchor.
- `policy-engine/src/polisyos/data_forge/domains/legal/corpus/versioning.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `build_version_index; resolve_active_version`. Version-index and resolution functions exist at the historical pin; exact temporal semantics must be reviewed against selected jurisdiction.
- `policy-engine/src/polisyos/data_forge/read_api/legal.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `search_legal_knowledge_graph`. Existing legal read surface is a consumer anchor; search result does not establish law or its effect.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Capture exact official act/version and amendments from the sponsor-named publisher; retain the publisher's raw representation and source metadata.
2. Record source-backed temporal event and provision relations, then have the selected competent reviewer bind applicability, notice, authority and affected lever.
3. Send changed text, legal rule or actual act to the existing claim/currentness cascade and permitted Expert/Machine surface.

### Рассмотренные альтернативы

- **Use a current consolidated text, search no-hit, translated text or LLM interpretation as the legal answer.** — EUR-Lex explicitly says its consolidated texts have no legal effect; other jurisdictions require their own rules and responsible interpretation.
- **Treat signature presence as competence or the PolicyOS receipt as the external act.** — The receipt proves what the system received; it cannot create authority, recipient, scope or effect.

### Free-grow и ресурсы

- **data or config growth:** Add new acts, versions, event links and reviewer-validated provision mappings under the supported legal grammar and existing Lex/Data Forge owners.
- **extension boundary:** New jurisdiction, unusual time doctrine, notice rule or act type requires a typed legal adapter/reviewer protocol and replayable conformance before legal gates use it.
- **resource behavior:** Index only the selected jurisdiction and governing instruments; unresolved branches remain explicitly unknown instead of expanding into whole-corpus search.


### Миграция и восстановление

Preserve original and later versions and rule-version references. Correct a bad mapping by superseding it and invalidating dependent uses; never rewrite the signed history.


### Композиция и owners

- Legal source and rule versions, reviewer provenance and relevant time roles travel with the applicability result.
- Actual external act/issuer evidence is distinct from the model intervention and from the legal text that permits it.


### Acceptance и различающие проверки

- Historical, prospective, partially commenced and repealed states resolve differently where the source events require it.
- Wrong recipient, absent notice, draft, expired delegation or wrong version leaves authority unknown or blocked.
- Removing event, recipient or competence resolution while retaining text/hash/signature must remove the downstream authority effect.


### Входы и ответственность за их получение

- Official publisher supplies the governing text and version/event history.
- Named legal reviewer supplies provision-to-lever applicability and notice interpretation.
- Competent authority supplies delegation and the original act with scope, recipient and revocation information.


### Когда обоснованно отклониться

- Publisher has no stable point-in-time version or event history: record the unresolved version as a limitation and seek issuer confirmation.
- The selected legal interpretation or actual act is disputed: route review and keep the dependent recommendation contested/blocked.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Consolidated texts](https://eur-lex.europa.eu/collection/eu-law/consleg.html?locale=en) — EUR-Lex states that consolidated texts show rules applicable at a point in time but have no legal effect; its page identifies the amendments included in a consolidation. **Граница:** This is an EU publisher's rule about its consolidations, not a universal rule for other jurisdictions. The exact governing legal source and effectivity rules remain case-specific.
- [European Legislation Identifier](https://eur-lex.europa.eu/content/help/eurlex-content/eli.html?locale=en) — ELI provides web identifiers and metadata for legislation, including point-in-time versions and language/format distinctions in its URI model. **Граница:** An identifier resolves a resource or version; it does not determine legal effect, notice, competence, applicability, or the authoritative language for another jurisdiction.
- [Akoma Ntoso Version 1.0 XML Vocabulary](https://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/part1-vocabulary/akn-core-v1.0-os-part1-vocabulary.html) — Akoma Ntoso describes legal document lifecycle events and links those events to the individual documents that produced them; it distinguishes original, single and multiple versions. **Граница:** A document format can preserve and link legal material but cannot make a legal interpretation or establish the competence of the issuer.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="CNT-05"></a>

## CNT-05 — Register measures, alternatives and authorized value choices (W2)

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CNT-05]`. Review: [root-review](root-review.md#CNT-05).

### Предпочтительное решение

Keep construct, metric and mandate as linked but distinct artifacts in existing Foundry/Scientist owners. Each metric definition pins the construct, unit, population, geography and period, observation/aggregation unit, instrument and frame, denominator, price/currency/accounting basis, formula/version, weights or aversion parameters, missing/zero/negative rules and transformation lineage. Store competing legitimate choices side by side and compute decision-sensitive results and rank reversals over an explicit parameter schedule. The authorized principal selects the operative objective/measure/weights and records mandate, date and alternatives considered. The engine may propose and compare hypothetical social weights as declared candidate assumptions and report conditional consequences; it never assigns the principal an operative normative choice without that principal’s competent selection.

### Что переиспользовать

- `policy-engine/src/polisyos/foundry/methods/catalog/distributional/metrics.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `AtkinsonIndexEstimator; FGTPovertyEstimator`. Existing distributional estimators are present at the historical pin; their available parameters do not prove that a metric is mandated for a case.
- `policy-engine/src/polisyos/foundry/methods/catalog/distributional/poverty_advanced.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `MultidimensionalPovertyEstimator`. Existing multidimensional estimator is present at the historical pin; cutoffs/dimensions remain substantive inputs.
- `policy-engine/src/polisyos/scientist/validation/metrics.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `compare_metric_family`. Existing metric comparison function is present at the historical pin and can be assessed before any new comparison engine is proposed.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Bind candidate measures to their source definitions and owner-local formula/parameter versions; make person, household and equivalized-person units explicit.
2. Compute an authorized base plus a declared alternative schedule (for example Gini, Theil and Atkinson at named aversion values; relative and international poverty lines; alternative energy burden denominators).
3. Expose sensitivity, subgroup and rank-change outputs beside the selected basis, and require a principal/mandate record to promote one basis to the decision consumer.

### Рассмотренные альтернативы

- **Pick one familiar index or default weights globally.** — OECD documentation makes clear that equivalence scales are conventions; Atkinson and multidimensional poverty methods expose choices that should remain visible and authorized.
- **Let optimization or outcome ranking choose the metric after seeing results.** — Outcome-driven selection launders a normative choice as neutral measurement.

### Free-grow и ресурсы

- **data or config growth:** Add versioned construct mappings, definitions, parameter schedules and locally authorized alternatives within the metric grammar.
- **extension boundary:** A new construct or non-comparable unit needs a concept/method owner and typed crosswalk; string similarity is not equivalence.
- **resource behavior:** Run declared alternatives against the same qualified inputs and bound the parameter grid by a case decision; if exploration is cut short, label the comparison incomplete.


### Миграция и восстановление

Keep prior metric versions and their use histories. Correct a formula or mandate by emitting a new version, recomputing affected results and staling only claims that depend on the changed basis.


### Композиция и owners

- The producer certifies formula execution and input adequacy; an authorized principal supplies the normative selector.
- Compare weighted and unweighted views and preserve incompatible principals' schedules as separate branches rather than averaging them silently.


### Acceptance и различающие проверки

- A metric label with changed denominator, equivalence scale, threshold, accounting basis or period yields a distinct definition.
- Alternative valid settings can reverse ordering and the consumer sees the reversal and chosen mandate.
- Removing formula/version invalidates the numerical claim; removing a required mandate prevents operative normative selection/protected recommendation even if labels remain. Correctly computed hypothetical/sensitivity results may remain candidate with explicit unselected authority.


### Входы и ответственность за их получение

- Dataset owner supplies definitions, frame, weights, missingness, currency and price details.
- Authorized principal supplies objectives, thresholds, tradeoffs and mandate provenance.


### Когда обоснованно отклониться

- No authorized principal selects a normative basis: report alternatives and keep recommendation limited/contested.
- Source population, denominator or construct cannot be crosswalked: do not substitute another measure under the same label.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [OECD Income Distribution Database metadata](https://www.oecd.org/content/dam/oecd/en/data/datasets/income-and-wealth-distribution-databases/idd-metadata-sources-and-income-years.pdf) — OECD documents its equivalised disposable household income definition, its treatment of income components and persons as the distribution unit, and notes the square-root household scale is a common but arbitrary choice. **Граница:** The documented OECD convention explains that dataset's construction; it does not establish that the same construct or scale fits a different population or policy question.
- [OECD Income Distribution Database guidelines](https://www.oecd.org/content/dam/oecd/en/about/programmes/oecd-data-collection-programme/society/income-distribution-database/income-distribution-guidelines.pdf) — The guidelines distinguish household survey observation units from person-level distribution indicators, weight households by member count, and prescribe an equivalence elasticity of 0.5 for that series. **Граница:** The prescribed definition harmonizes the OECD series; a shared label does not guarantee local frame, accounting, equivalisation, or period comparability.
- [On the measurement of inequality](https://are.berkeley.edu/courses/ARE251/fall2007/Papers/atkinson70.pdf) — Atkinson derives inequality measurement from an explicit social-welfare approach and contrasts ranking distributions with quantifying inequality, illustrating that a measure embeds choices about distributional sensitivity. **Граница:** This paper supplies a method and assumptions, not authorization to select an inequality-aversion parameter for a case.
- [Counting and multidimensional poverty measurement](https://www.aeaweb.org/conference/2009/retrieve.php?pdfid=39) — Alkire and Foster describe within-dimension deprivation cutoffs, a cross-dimension cutoff, and an adjusted headcount measure that captures incidence and breadth. **Граница:** Dimension weights and cutoffs are substantive choices; the paper does not make them universally correct or supply local authorization.
- [The Green Book (2026)](https://www.gov.uk/government/publications/the-green-book--2/the-green-book-2026) — The guidance says it does not set objectives or make policy decisions and requires weighted distributional estimates to appear alongside unweighted estimates. **Граница:** Its weights and procedures are UK-specific policy guidance, not universal defaults. It is useful here as an example of explicitly exposing value choices and preserving the decision maker's role.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="CNT-06"></a>

## CNT-06 — Ground empirical, causal, transport and calibration claims (W3)

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CNT-06]`. Review: [root-review](root-review.md#CNT-06).

### Предпочтительное решение

Bind each causal claim to a well-defined intervention version, target population, comparator, outcome, horizon and estimand. Record the study/cohort and data lineage, design/assignment, identification assumptions and falsifiers, take-up/compliance, selection, missingness, interference, effect modifiers, contrary evidence and uncertainty. A method owner records whether and why evidence transports to the commissioned target, including overlap and population differences; unsupported extrapolation stays limited. Keep estimates, predictions, scenarios and simulated interventions typed separately. Calibration records state the target, labels, population/period, protocol, independent validation set and calibration results. Select completion by claim type and an already approved method profile; preserve competing or uncertain completions, including justified frequentist/sequential, robust or partial-identification results. Do not impose a Bayesian-only default or combine guarantees across profiles without a valid joint rule. A causal workflow consumes the method-specific supported claim and retains limitations where its predicates are missing.

### Что переиспользовать

- `policy-engine/src/polisyos/scientist/validation/claim_support.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `evaluate_claim_support`. Claim support evaluator exists at the historical pin; the recommendation is to extend/use native predicates, not treat the function as causal proof.
- `policy-engine/src/polisyos/scientist/orchestration/workflows/causal_full.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `causal_full_workflow_spec`. Existing causal workflow spec is present at the historical pin and is the consumer bridge anchor.
- `policy-engine/src/polisyos/foundry/agent_sim/world/operators/interventions.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `intervention operators module`. Existing world intervention owner is named in the input; simulation output remains separate from observed causal evidence.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Select real evidence for the commissioned claim and produce source-bound study/claim records through Scholar/Scientist owners.
2. Evaluate identification and transport for the exact target, retaining counterexamples and non-identified or partial-identification alternatives; validate predictive calibration separately on a declared target sample.
3. Bridge the resulting typed support/limitation into existing G2/G3/G4/G5/G6 consumers and audit outputs.

### Рассмотренные альтернативы

- **Treat a causal graph, model fit, trial badge, consensus, paper count or simulated scenario as an effect estimate.** — These do not by themselves identify the requested counterfactual or support transport to this target.
- **Treat recalibration as causal correction or transport evidence.** — Calibration assesses predictive probability agreement; it cannot establish the intervention contrast.

### Free-grow и ресурсы

- **data or config growth:** Add studies, cohorts, target definitions, method configurations and validation results through current evidence and method owners.
- **extension boundary:** A new estimand family or identification/transport method requires a typed method adapter, declared assumptions and case-specific conformance before consumer use.
- **resource behavior:** Use data-supported overlap and prespecified analysis budgets; when required strata or validation data are absent, emit limited/inconclusive rather than extrapolating silently.


### Миграция и восстановление

Version evidence, method and calibration rules; on correction or validation failure, supersede the relevant claim, recompute dependent status and keep the prior signed basis and scope visible.


### Композиция и owners

- ClaimRecord binds source evidence, target, estimand, method and counterevidence; workflow consumes that record, not citation strings.
- Transport and calibration are separate validation relations and cannot substitute for each other.


### Acceptance и различающие проверки

- Changing target, intervention version, outcome horizon or comparator changes the claim identity/estimand.
- Weak overlap, unsupported selection/interference assumptions or an unvalidated target limits an unqualified effect claim; a claim-appropriate partial-identification result may remain admissible within its bounds.
- Removing identification or target validation while retaining study markers lowers or blocks the downstream claim.


### Входы и ответственность за их получение

- Study custodian supplies the protocol, data/design facts, corrections and local observations.
- Domain/method reviewer supplies identification and transport assessment and a falsifier.
- Independent validation data owner supplies permitted target labels and calibration protocol.


### Когда обоснованно отклониться

- The study intervention differs materially from the proposed operator or target: keep the result as a bounded analogue, not a transported effect.
- Adverse or contrary evidence changes the claim: reopen affected consumers rather than average away the conflict.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Causal Inference: What If](https://miguelhernan.org/whatifbook) — Hernán and Robins frame observational causal analysis as emulation of a specified target trial and discuss exchangeability, positivity, consistency, treatment versions and longitudinal methods. **Граница:** The site points to a revisable edition; a use must pin the exact version. Its methods do not choose a policy objective or certify a case's assumptions.
- [External Validity: From Do-Calculus to Transportability Across Populations](https://arxiv.org/abs/1503.01603) — Pearl and Bareinboim use selection diagrams to represent differences between study and target populations and derive conditions under which causal effects can be transported. **Граница:** The diagram's assumptions require substantive support. Formal transportability does not rescue absent overlap or an ungrounded account of population differences.
- [Calibration: the Achilles heel of predictive analytics](https://link.springer.com/article/10.1186/s12916-019-1466-7) — Van Calster and colleagues distinguish calibration assessment from other predictive-model performance and describe calibration checks for external validation. **Граница:** Predictive calibration on a target sample is neither causal identification nor proof that the target sample represents a policy population.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — PROV-O provides reusable relations among entities, activities and agents, including generation, use, derivation and attribution, for expressing lineage. **Граница:** A lineage graph records declared provenance. It does not prove independence, factual truth, legal permission, or source quality unless those properties have their own evidence and verification.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="CNT-07"></a>

## CNT-07 — Admit testimony, participation, values, expertise and feasibility under distinct authority (W4)

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CNT-07]`. Review: [root-review](root-review.md#CNT-07).

### Предпочтительное решение

Keep a testimony account, occurrence, permission, selection/representation, interpretation or translation, value mandate, expert judgment and operational-feasibility record semantically distinct. For each account preserve source/context, elicitation method, date, translation chain, permitted audience/use, correction/challenge route, missing voices, dissent and affected claim links; do not infer a unique person or population prevalence from an occurrence. Participation records state the remit, commissioning body, selection method, who could not participate, information/evidence supplied, influence promised and authority's response. A value principal explicitly authorizes the objective and tradeoffs. The accountable delivery institution supplies capacity, budget, staff, schedule and later execution evidence; a promise or survey preference is not capacity.

### Что переиспользовать

- `policy-engine/src/polisyos/evidence/claims/claim_registry.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `normalize_runtime_claim_registry`. Existing claim registry normalization is present at the historical pin and is a claim-binding route, not a mandate or representation verifier.
- `policy-engine/src/polisyos/fabric/security/access_control.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `access-control module`. Existing access-control owner is named in the input; task-specific testimony permission still requires a real grant.
- `policy-engine/src/polisyos/fabric/provenance/lineage.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `FabricLineageTracker`. Existing lineage tracker is present at the historical pin and can connect the record to affected claims; lineage alone is not consent.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Commission an actual speaker/holder, process custodian, value principal and operational answerer; collect their permitted records through current claim, permission and lineage owners.
2. Store account, process and authority records separately; preserve translation, dissent, absence and correction/revocation events.
3. Bridge only the claim-relevant, permissioned assertions into G4/G5/G6 and expose permitted context to reviewers and Atlas.

### Рассмотренные альтернативы

- **Treat consultation count, self-selected responses, a quote, or a preference average as representation or mandate.** — Participation purpose and selection method determine what the input can support; authority must be separately documented.
- **Publish raw testimony or inferred identities by default.** — Permission, privacy, collective governance and audience constraints belong to the source holder, not to a public catalog.

### Free-grow и ресурсы

- **data or config growth:** New permitted accounts, process rounds, translations, dissent and operator attestations use existing claim, permission and lineage owners.
- **extension boundary:** A new participatory method or community-specific governance protocol needs a typed method/authority adapter agreed with that community's responsible institutions.
- **resource behavior:** Keep raw/private content at its custodian when possible and store only a scoped receipt/derived assertion; an incomplete or contested record remains visible as such.


### Миграция и восстановление

Preserve original version and permission scope; correction or revocation emits a new event, stales affected uses, and does not rewrite the original speaker's record or unbound complaints.


### Композиция и owners

- Occurrence/context/translation and permission establish only what the source permits; representation and mandate need separate verifier evidence.
- Capacity estimates need named operating entity, time horizon, resource basis and status as measured, planned, committed or executed.


### Acceptance и различающие проверки

- A count of responses cannot discharge mandate or prevalence; missing groups and selection limits remain in the audit.
- Revocation or translation correction reaches every linked use; removing affected-use binding prevents the use from remaining green.
- A plan or promise without staffing/budget/schedule evidence cannot close feasibility.


### Входы и ответственность за их получение

- Speakers/holders or their authorized body provide the account and grant.
- Commissioning authority names remit, participant-selection method and its response obligation.
- Authorized principal states values/tradeoffs; operator and technical authority supply capacity and execution evidence.


### Когда обоснованно отклониться

- Consent scope, identity, representation or mandate is disputed: quarantine raw content and limit the claim pending the responsible authority.
- A relevant community's data governance rules apply: follow the named community authority's protocol; no generic CARE or FAIR label substitutes for it.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Good practice principles for deliberative processes for public decision making](https://www.oecd.org/en/publications/innovative-citizen-participation-and-new-democratic-institutions_339306da-en/full-report/component-9.html) — OECD's principles include a clear remit, accountability, transparency, representativeness, inclusion, accessible information, deliberation, adequate time, independence, privacy and evaluation. **Граница:** These are process design principles drawn from comparative practice, not a legal mandate, universal representation test, or substitute for the commissioning authority's decision.
- [OECD Guidelines for Citizen Participation Processes](https://www.oecd.org/en/publications/oecd-guidelines-for-citizen-participation-processes_f765caf6-en.html) — The guidelines distinguish participation methods and policy-cycle stages, and recommend stating expected outcomes and how citizen input will be used or answered. **Граница:** Participation can inform issue framing, formulation, decision, implementation or evaluation, but a participation record alone does not establish an authorized decision.
- [The Green Book (2026)](https://www.gov.uk/government/publications/the-green-book--2/the-green-book-2026) — The guidance says it does not set objectives or make policy decisions and requires weighted distributional estimates to appear alongside unweighted estimates. **Граница:** Its weights and procedures are UK-specific policy guidance, not universal defaults. It is useful here as an example of explicitly exposing value choices and preserving the decision maker's role.
- [The CARE Principles for Indigenous Data Governance](https://doi.org/10.5334/dsj-2020-042) — The paper articulates collective benefit, authority to control, responsibility and ethics as people- and purpose-oriented considerations in Indigenous data governance. **Граница:** Apply only where the relevant peoples, communities and their governing authorities make these principles relevant; it is not a generic permission token or replacement for local rights.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — PROV-O provides reusable relations among entities, activities and agents, including generation, use, derivation and attribution, for expressing lineage. **Граница:** A lineage graph records declared provenance. It does not prove independence, factual truth, legal permission, or source quality unless those properties have their own evidence and verification.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="CNT-08"></a>

## CNT-08 — Compare bases and learn without double-count or authority laundering (W5)

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CNT-08]`. Review: [root-review](root-review.md#CNT-08).

### Предпочтительное решение

Keep immutable competing basis branches and create an owner-validated difference record that separates common inputs from the premise that changed: metric/mandate, legal version or interpretation, source generation, method, testimony/permission or calibration. Use the existing lineage and claim-support graph to record supports, contradicts, derives-from, depends-on and supersedes edges, including common study/cohort/participant/model ancestry. Treat search and exposure logs as selection history, not evidence. Exploratory anomalies may prioritize an acquisition or open a candidate claim. Only when a claim asserts independent corroboration is an independent/held-out basis required, with independence actually established; other claims complete under their claim-type method profile, including approved sequential, robust or partial-identification profiles. Do not impose a Bayesian-only default or combine guarantees without a valid joint rule. A source, law, method, permission or calibration event re-evaluates only affected dependent uses.

### Что переиспользовать

- `policy-engine/src/polisyos/scientist/validation/claim_support.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `evaluate_claim_support`. Native claim-support evaluator is present at the historical pin and is the support/counterevidence owner anchor.
- `policy-engine/src/polisyos/fabric/provenance/lineage.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `FabricLineageTracker; trace_claim_origin; impact_analysis`. Lineage and impact functions are present at the historical pin; hashes alone do not establish independent evidence.
- `policy-engine/src/polisyos/fabric/storage/tenant_cas.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `TenantScopedCAS`. CAS provides an artifact custody anchor at the historical pin; shared identity or content address is only one ancestry signal.
- `policy-engine/src/polisyos/runtime/quality/acquisition_epoch_admission.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `AcquisitionEpochAdmissionRequest`. Epoch admission type is present at the historical pin; impact and freshness reactions require consumer-side rebind.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Persist a basis manifest and input-edge set per decision generation; resolve shared lineage and unknown-overlap status across studies, reports, cohorts, participants and models.
2. Record exploratory search frontier, exact query/version/time/count and budget cutoff separately from admitted evidence; keep complete bounded no-hit conditions distinct from verified absence.
3. On supported correction or source/permission/legal change, use impact analysis to re-evaluate linked claim-support and calibration consumers and expose the changed basis.

### Рассмотренные альтернативы

- **Count papers, mirrors, hashes, publisher domains or repeated model exposures as independent confirmations.** — Different records can share a single study, cohort, method, author or source ancestor; unknown overlap is not independence.
- **Treat the best-so-far search frontier or anomaly as exhaustive or confirmatory.** — Cochrane's reproducible-search and living-review practices show why protocol, date, source set and update changes must be visible; adaptive holdout reuse can itself overfit.

### Free-grow и ресурсы

- **data or config growth:** Add source/claim versions, search rounds, lineage edges, corrections and comparison branches through current Fabric, Scholar and Scientist owners.
- **extension boundary:** A novel dependence relation or confirmatory method needs a typed edge/validator and a method-specific falsifier; never default it to independent.
- **resource behavior:** Search, comparison and holdout budgets are explicit. Cutoff stores remaining frontier and leaves search incomplete; it does not erase the obligation or mint a no-hit.


### Миграция и восстановление

Import prior traces as provenance/selection history unless method, scope and ancestry are recoverable. Preserve prior basis generations; rollback a currentness projection by re-evaluating affected uses, not by deleting the lineage.


### Композиция и owners

- Exploration can change candidate/search state; only eligible confirmation or source-validated correction changes confirmatory claim support.
- Search completeness is bounded by named namespaces, query/rule version, rights, cutoff, result denominator and blind spots.
- A changed parent permission or law version triggers only dependent uses, with untouched uses retaining their prior status.


### Acceptance и различающие проверки

- Shared study or cohort ancestry collapses apparent independent count even when publications or hashes differ.
- Unknown overlap or repeated adaptive exposure cannot support an independent-confirmation claim; budget-truncated search cannot support verified absence. Other claim-type completions remain judged under their own method and scope.
- Removing exposure/parent-permission dependency drops confirmation or stales the affected use while unrelated claims remain unchanged.


### Входы и ответственность за их получение

- Study and dataset custodians supply corrections, holdouts, cohort lineage and outcomes.
- Source issuer, rights holder, legal custodian or participant/community authority supplies change, revocation or correction events.


### Когда обоснованно отклониться

- Ancestry cannot be resolved: preserve unknown overlap and limit evidence strength.
- No independent or method-supported confirming basis is available: keep the anomaly exploratory and state the remaining discriminator.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — PROV-O provides reusable relations among entities, activities and agents, including generation, use, derivation and attribution, for expressing lineage. **Граница:** A lineage graph records declared provenance. It does not prove independence, factual truth, legal permission, or source quality unless those properties have their own evidence and verification.
- [Cochrane Handbook, Chapter 4: Searching for and selecting studies](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04) — Cochrane recommends searches matched to eligibility criteria, broad source coverage, reproducible exact search strategies and record counts, and distinguishes reports from underlying studies. **Граница:** Search recommendations arise from health evidence synthesis and need adaptation to other fields, languages, source types and lawful access constraints.
- [Cochrane Handbook, Chapter 22: Prospective approaches to accumulating evidence](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-22) — Cochrane's living-review guidance calls for explicit search methods and update frequency, ongoing surveillance, and communication of what changed between versions. **Граница:** The handbook does not prescribe a universal refresh interval; use depends on source change rates, decision stakes and resource constraints.
- [Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x) — Benjamini and Hochberg introduce a step-up procedure that controls false discovery rate under independent test statistics. **Граница:** Independence conditions and the tested family matter; this is not a blanket license to promote adaptive findings or use the procedure without checking dependence assumptions.
- [Generalization in Adaptive Data Analysis and Holdout Reuse](https://papers.neurips.cc/paper_files/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html) — The paper shows that repeated adaptive reuse of a holdout can overfit it and presents a method for controlling that risk. **Граница:** The method's guarantees depend on its formal setting and algorithm. It is a warning and possible design family, not evidence that PolicyOS has independent validation.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="CNT-09"></a>

## CNT-09 — Prove one selected packet through consumer and surfaces (W6)

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CNT-09]`. Review: [root-review](root-review.md#CNT-09).

### Предпочтительное решение

After actual case commissioning, compose one coherent packet from only the selected foundations. Each branch must emit its native persisted artifact/receipt and verifier result, then connect through the existing acquisition/lifecycle and G2/G4/G5 consumers to recommendation, limited, contested, blocked or publishable status. For every selected claim show the evidence basis, time roles, rights, competing measure results, legal status/interpretation, causal limits, testimony/mandate provenance, capacity and refresh duty. Prove that revocation, changed law, altered denominator, shared study ancestry or exploratory-only support changes the consuming decision and audit projection. Expert/Machine views expose full limits and lineage; reviewer view compares bases; public/Atlas view contains only permitted projections. A costed refusal is a valid result when real inputs are unavailable, but it is not an authentic-case positive or closure of unrelated programme obligations.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/services/acquisition_action_service.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `acquisition action service module`. Input identifies the service as an existing owner; exact route and output must be rebound after E02.
- `policy-engine/src/polisyos/runtime/quality/acquisition_executor.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `execute_live_catalog_acquisition`. Existing producer entry point is present at the historical pin; not proof that a selected packet reaches a consumer.
- `policy-engine/src/polisyos/data_forge/read_api/legal.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `search_legal_knowledge_graph`. Existing legal read surface is present at the historical pin; legal findings still require exact source and reviewer evidence.
- `policy-engine/src/polisyos/scientist/orchestration/workflows/causal_full.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `causal_full_workflow_spec`. Existing causal workflow is present at the historical pin and is an integration anchor, not an acceptance result.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Bind selected facets to exact suppliers, artifacts, verifiers, downstream consumers, status effects and surfaces; record non-selected facets with reason/trigger.
2. Run the permitted case input through the real producer and persist its artifact/event; verify a fresh consumer changes status on both positive and adversarial variants. For a selected joint-intervention property, use the existing world simulation unless an adopted exact JOINT witness proves that specific property; do not treat such a witness as proof of a different property.
3. Project the same scope, time, rights, version, status and limitations into Expert/Machine audit, reviewer comparison and permitted Atlas/API/public views.

### Рассмотренные альтернативы

- **Collect all source families or use the heating-affordability example as an assumed pilot.** — The workstream makes the example optional and case-specific population/authority/supplier are not selected.
- **Pass on constructor tests, fixture-only data, UI labels or prewritten proofs.** — These do not demonstrate a real permitted input changing the owner-produced artifact, downstream decision and surface.

### Free-grow и ресурсы

- **data or config growth:** A new case adds selected evidence/configuration under existing owners without enumerating every future source population.
- **extension boundary:** A new semantic capability is out of scope for the vertical until an owner adapter, verifier, bridge, consumer and permitted projection are named.
- **resource behavior:** Compose one bounded packet; report partial or costed refusal when a needed input, legal answer, capacity record or independent confirmation is unavailable.


### Миграция и восстановление

Use selected source and schema generations only. On revocation, stale source, wrong legal notice or changed metric, withdraw affected use/publication and preserve prior signature history and decision basis.


### Композиция и owners

- Selected source artifact has exact identity/version, purpose, rights, time roles and provenance; native verifier confirms the relevant semantic property.
- Orchestration bridges admitted/limited outcomes into the real decision/status consumer; rendering cannot create authority.
- Audit, reviewer and public projections share the same admitted generation but each applies its audience and rights filter.
- Reconcile the current common grammar/routes/limits for all 26 foundation families and evidence for each claimed class. Case-specific acquisition does not require harvesting all 197 source cards, but one successful case cannot close the separate all-family grammar obligation. No new global scheduling barrier is introduced.


### Acceptance и различающие проверки

- A permitted input creates a persisted owner artifact/event and changes a real recommendation/status through a fresh consumer.
- Foreign scope, revoked rights, incomplete response, wrong legal notice, shared evidence ancestor and exploratory-only outcome fail or limit the affected branch.
- Removing event-to-decision bridge, owner check, alternative-measure behavior or export gate keeps markers but makes semantic acceptance fail.
- Audit and permitted projection agree on scope, time, status and limitations without exposing raw query-only or private testimony.
- Omit one of the 26 current families from the common grammar/route/limit mapping while the selected case still works; programme completion must remain incomplete. A family not selected for this case does not require an irrelevant live acquisition.


### Входы и ответственность за их получение

- Sponsor names real jurisdiction, population, intervention, decision authority and actual suppliers.
- Named custodians provide permitted data/definitions, law and act evidence, studies/holdouts, testimony/consent, mandate/value choice and operational capacity.


### Когда обоснованно отклониться

- No authentic case/suppliers are commissioned: return costed refusal; do not claim an authentic positive.
- A conditional foundation was not selected: keep it out of the packet with its reason rather than silently treating it as satisfied.
- A new consumer or shared owner appears during rebind: pause only the affected integration and resolve its exact lease/interface.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Data Catalog Vocabulary (DCAT) Version 3](https://www.w3.org/TR/vocab-dcat-3/) — DCAT 3 distinguishes cataloged datasets, distributions, data services and dataset series; it adds version/current-version relations and supports multiple representations and temporal/spatial metadata. **Граница:** A catalog vocabulary supports interoperability and discovery. It does not establish that content is authentic, lawful to reuse, applicable, current for a claim, or authoritative.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — PROV-O provides reusable relations among entities, activities and agents, including generation, use, derivation and attribution, for expressing lineage. **Граница:** A lineage graph records declared provenance. It does not prove independence, factual truth, legal permission, or source quality unless those properties have their own evidence and verification.
- [Consolidated texts](https://eur-lex.europa.eu/collection/eu-law/consleg.html?locale=en) — EUR-Lex states that consolidated texts show rules applicable at a point in time but have no legal effect; its page identifies the amendments included in a consolidation. **Граница:** This is an EU publisher's rule about its consolidations, not a universal rule for other jurisdictions. The exact governing legal source and effectivity rules remain case-specific.
- [OECD Income Distribution Database metadata](https://www.oecd.org/content/dam/oecd/en/data/datasets/income-and-wealth-distribution-databases/idd-metadata-sources-and-income-years.pdf) — OECD documents its equivalised disposable household income definition, its treatment of income components and persons as the distribution unit, and notes the square-root household scale is a common but arbitrary choice. **Граница:** The documented OECD convention explains that dataset's construction; it does not establish that the same construct or scale fits a different population or policy question.
- [Causal Inference: What If](https://miguelhernan.org/whatifbook) — Hernán and Robins frame observational causal analysis as emulation of a specified target trial and discuss exchangeability, positivity, consistency, treatment versions and longitudinal methods. **Граница:** The site points to a revisable edition; a use must pin the exact version. Its methods do not choose a policy objective or certify a case's assumptions.
- [Good practice principles for deliberative processes for public decision making](https://www.oecd.org/en/publications/innovative-citizen-participation-and-new-democratic-institutions_339306da-en/full-report/component-9.html) — OECD's principles include a clear remit, accountability, transparency, representativeness, inclusion, accessible information, deliberation, adequate time, independence, privacy and evaluation. **Граница:** These are process design principles drawn from comparative practice, not a legal mandate, universal representation test, or substitute for the commissioning authority's decision.
- [Cochrane Handbook, Chapter 22: Prospective approaches to accumulating evidence](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-22) — Cochrane's living-review guidance calls for explicit search methods and update frequency, ongoing surveillance, and communication of what changed between versions. **Граница:** The handbook does not prescribe a universal refresh interval; use depends on source change rates, decision stakes and resource constraints.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.
