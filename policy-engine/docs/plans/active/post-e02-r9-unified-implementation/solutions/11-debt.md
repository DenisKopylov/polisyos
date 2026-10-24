# Остаточные долги: предпочтительные решения

Статус: engineering recommendations; product execution UNRUN. Реализация только после E02 acceptance и полного affected-scope rebind. Исходные критерии не сокращаются; [общие решения](00-shared-decisions.md) предотвращают второго owner. [Нормативные уточнения](decision-clarifications.md) остаются предложениями.

<a id="DEB-01"></a>

## DEB-01 — Measurement instruments: complete input disclosure

Исходная запись: [tasks.json](../tasks.json), `tasks[id=DEB-01]`. Review: [root-review](root-review.md#DEB-01).

### Предпочтительное решение

Extend the existing FileReadMeasurement/reporting path into a versioned instrument disclosure: declared roots, suffix/file types, selection predicates and exclusions are separate from the observed read set, and each actual read/error is content-bound. An absence conclusion is eligible only when the instrument proves its declared source-of-truth universe was selected and resolved; unreadable, unmatched or out-of-root sources remain unknown, not empty. Migrate the 303/319 diagnostic owners rather than creating a second measurement platform. Recompute complete census membership from the stated roots and name the founding out-of-root instrument; state the singleton literal census predicate explicitly. Replace trust-posture bare totals with derived site identities and reconcile the two changed sites before accepting the owner gate. Preserve runner receipts as intake-only. The original executable/transitive-chunk falsifier remains the integrity test when runner inputs change; absent independently admitted runner identity, executable integrity stays `not_established`.

### Что переиспользовать

- `policy-engine/tools/lib/fs.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `FileReadMeasurement / measure_file_reads`. Existing measured file-read abstraction records observed bounded reads and has an explicit boundary; extend its disclosure/report at the instrument owner, do not broaden it into unbounded syscall/network tracing.
- `policy-engine/tools/quality/validation/check_debt_ledger.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `instrument input-disclosure consumer`. Existing consumer path to rebind after accepted E02; require selectors and observed reads to be compared.
- `policy-engine/tools/quality/validation/check_trust_claim_posture.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `trust posture census`. Known moving-total site; replace count-only expectation with complete named-site composition and source-derived denominator.
- `policy-engine/docs/how-to/author-measurement-instruments.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `measurement input disclosure guidance`. Existing owner guidance is the natural shared protocol anchor.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rebind each instrument, owner, selector and current caller after P0-ACCEPT; use the full executable-source denominator, declared file types, roots, exclusions and predicate, and include its denominator count/checksum in the receipt.
2. Migrate every in-scope instrument to record inputs actually read plus failed reads and unresolved selectors; test removal of one declared source while leaving report markers intact.
3. Resolve the two trust-posture site changes by name; keep observed instrument totals derived from complete source membership rather than pinning a count.
4. Replay the existing covered executable/transitive-chunk falsifier on runner changes; do not turn intake evidence into execution-integrity evidence.

### Рассмотренные альтернативы

- **Add independent runner attestation/service** — The original receipt is explicitly intake-only; no admitted out-of-band identity source is currently established. Adding infrastructure would create a new authority owner without closing the local falsifier.
- **Keep totals and add comments** — A comment does not prove selector completeness, source resolution, or membership and fails the removal probe.

### Free-grow и ресурсы

- **data or config growth:** New diagnostics register their own root/filetype/predicate under the same measurement contract; counts and named sites are generated from source discovery.
- **extension boundary:** A new observation class (e.g., subprocess or network reads) requires an explicit adapter and conformance test; it cannot be implied by file-read evidence.
- **resource behavior:** Work is proportional to declared files and measured reads; bound and report unreadable/excluded files instead of silently treating them as absent.


### Миграция и восстановление

Version the receipt additively, preserve historical receipts and old reader compatibility, and do not reinterpret old absence claims. If a new receipt fails verification, suspend only conclusions that depend on it and restore compatible reader/config while retaining history.


### Композиция и owners

- Absence is a conjunction of complete declared denominator + selector truth + successful source resolution + no matching evidence; any missing predicate yields unknown/limited.
- A measured input is evidence of a read, not evidence that the source is authoritative or truthful.
- Runner intake closure does not imply executable integrity; preserve explicit `not_established` residual.


### Acceptance и различающие проверки

- A founding instrument outside the previous roots is found by complete enumeration.
- Omitting an input root while retaining declarations/markers cannot produce a green absence claim.
- Same inputs produce the same site membership; unreadable is distinguishable from empty.
- Changed transitive chunk bytes with unchanged entry identity exercise the original falsifier; no receipt claims more than it observes.


### Входы и ответственность за их получение

- Accepted E02 source tree and task-specific owner rebind.
- Instrument owner confirmation of legitimate exclusions and the two changed trust-posture sites.
- Independent runner identity only if someone later proposes a stronger integrity claim; until then residual remains not_established.


### Когда обоснованно отклониться

- Any proposed syscall/network capture or runner-attestation service needs a new scope/owner decision.
- If the existing receipt cannot name read errors or selector gaps without a version break, propose an explicit receipt migration instead of overloading old meaning.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Coverage.py configuration reference](https://coverage.readthedocs.io/en/latest/config.html) — The measured source universe is affected by configured source/include/omit selectors, and source selection changes what a coverage result says it has measured. **Граница:** Coverage.py measures execution, not PolicyOS instrument input reads; transfer only the need to disclose scope selectors, not its coverage metric or runner.
- [TUF roles and metadata](https://theupdateframework.io/docs/metadata/) — Trust decisions are purpose/role-bound and bind key thresholds, signatures, hashes, versions, and expiry; old metadata must be detected rather than silently promoted. **Граница:** Software-update repository model; use as a design comparison for typed scope/time binding, not as a PolicyOS authority scheme or a call to adopt TUF.
- [PROV Model Primer](https://www.w3.org/TR/prov-primer/) — PROV represents entities, activities, usage/generation, agents, and responsibility so a reader can trace artifact lineage and provenance assertions. **Граница:** A provenance vocabulary records relationships; it does not decide whether an external function belongs in PolicyOS or whether evidence has admissible authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="DEB-02"></a>

## DEB-02 — Build/configuration gates and reproducible OpenAPI

Исходная запись: [tasks.json](../tasks.json), `tasks[id=DEB-02]`. Review: [root-review](root-review.md#DEB-02).

### Предпочтительное решение

Repair the two named predicates independently. For the size gate, parse the complete declared packaging-configuration set and measure effective semantic declarations (normalized table/key/value entries or an owner-approved equivalent), not physical lines in one file; a file move must leave the measured set unchanged. Preserve the current threshold only if its owner confirms what budget it expresses; otherwise report the complete inventory and obtain a decision rather than inventing a new limit. For OpenAPI, bind export to source, lockfile and a declared build environment/profile, then remove undeclared environment influence or bind any required influence as an explicit input. Compare the full OpenAPI Description (entry plus all refs) with stable reference resolution and no clock, path, hostname or machine-derived digest. Use existing canonical serialization first; use JCS only if the payload meets its I-JSON constraints and the owner elects it. A lock alone is not an environment proof.

### Что переиспользовать

- `policy-engine/tools/quality/validation/repository_structure_phase0.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `gate_pyproject_size`. Current observed predicate counts physical pyproject lines; a relocation to hatch config can bypass it.
- `policy-engine/tools/ops_runners/runtime/export_runtime_openapi.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `runtime OpenAPI export`. Existing renderer is the owner path for source artifact; rebind before deciding whether env-derived digest enters there or its downstream freshness consumer.
- `policy-engine/tools/ops_runners/runtime/generate_runtime_client.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `runtime client generator`. Existing generated client pipeline; change should retain the generator consumer and artifact identity.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Inventory all packaging config files and effective setting keys, including relocated Hatch-specific configuration; retain file/key provenance to explain budget membership.
2. Exercise relocation: move an unchanged setting between declared files and prove the measured semantic configuration does not decrease; add/change a setting and prove the exact property changes.
3. Record OpenAPI export profile, code/lock identity, tool versions and environment dimensions that actually affect output; remove incidental machine state or make necessary dimensions explicit.
4. Generate/compare the full OAD including referenced documents and assert same admitted source/lock/profile yields the same export digest across controlled environments; unrelated host path or clock change must not alter it.

### Рассмотренные альтернативы

- **Count line total across more files** — Comments, formatting, and file splits can still move the apparent size without changing configuration semantics.
- **Force one container image as the only answer** — Reproducible-build guidance calls for a declared, auditable environment, but a container is one option and may hide host/CPU inputs; keep the environment perimeter specific and minimal.
- **Adopt JCS immediately** — It is informational, has I-JSON constraints, and may duplicate an existing canonical serializer; first identify the current varying digest input.

### Free-grow и ресурсы

- **data or config growth:** New packaging settings are counted from the owner-declared config set; OpenAPI schema and reference growth is included through the OAD resolver.
- **extension boundary:** New packaging formats or external reference protocols require an explicit parser/resolver adapter and fixture; unsupported refs remain unresolved, not omitted.
- **resource behavior:** Config census scales with declared config bytes; OpenAPI resolution is bounded by allowed refs/cycles and reports unresolved external refs rather than unbounded network crawling.


### Миграция и восстановление

Keep the old gate readable while the complete config set is introduced; do not silently alter its budget threshold. Version any snapshot digest semantics and regenerate only from the pinned source/profile; on mismatch retain old artifact/history and block only freshness-dependent outputs.


### Композиция и owners

- A config budget measures semantic configuration, not file location or formatting.
- The export identity binds source, lock, exporter/toolchain and environment inputs that actually affect OAD bytes.
- An OpenAPI Description includes referenced documents; digesting only the entry file is an incomplete surface claim.


### Acceptance и различающие проверки

- Relocation of unchanged settings does not reduce the gate measure; adding a real effective setting does.
- Two environments with identical admitted inputs produce the same full OAD and generated client inputs.
- Changing an API schema or an allowed reference changes the correct digest; changing unrelated environment variables does not.
- A missing/cyclic/unresolved reference is visible as a bounded failure, not dropped from the snapshot.


### Входы и ответственность за их получение

- Owner-approved meaning and existing threshold for the packaging-config budget.
- Accepted E02 tree, current lockfile and the generator's real environment dependencies.
- Policy for external OpenAPI references, if the OAD contains them.


### Когда обоснованно отклониться

- If complete packaging configuration spans non-TOML formats, decide a typed parser inventory before counting.
- If intentional environment variation is part of the API contract, bind it as a named export profile rather than normalize it away.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [What's in a build environment?](https://reproducible-builds.org/docs/perimeter/) — A reproducibility claim has a declared perimeter including tools, versions, operating-system assumptions, locale, timezone, paths, and relevant environment variables; outputs are comparable only within that stated context. **Граница:** A project guide, not a universal guarantee that two systems will be reproducible or a mandate to adopt containerization.
- [Locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/) — uv lock/sync can check metadata-lock consistency, and exact sync removes packages outside the lock; frozen and locked modes have different verification semantics. **Граница:** A lockfile pins package resolution, not OS/locale/environmental inputs or generated artifact semantics. Repository-specific setup commands remain controlling.
- [OpenAPI Specification v3.1.1](https://spec.openapis.org/oas/v3.1.1.html) — An OpenAPI Description consists of its entry document and all referenced documents; reference resolution, base URIs, and cycles affect the meaning and complete surface. **Граница:** The specification defines the description format, not a particular repository export pipeline or the desired API policy.
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — A canonical JSON representation can make hash/signature inputs repeatable across serializers when data satisfies JCS/I-JSON constraints. **Граница:** Informational RFC, not an Internet Standards Track specification; its number/string constraints may make it unsuitable for some payloads. Reuse an existing canonical serializer first.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="DEB-03"></a>

## DEB-03 — Public/private boundary and release inventory

Исходная запись: [tasks.json](../tasks.json), `tasks[id=DEB-03]`. Review: [root-review](root-review.md#DEB-03).

### Предпочтительное решение

Cover the original cross-module private-name reach class, including imports and private attributes in runtime/quality/container owners. Reuse the existing architecture/import tooling, extend its source-derived owner resolution for the missing class, and name genuinely unresolved dynamic edges as bounded limitations rather than pretending underscore spelling proves ownership. The historical IR _ArtifactManifestReader case is one example, not the denominator. Route actual edges through supported owner entrypoints or justified internal APIs; do not enlarge public API merely to make a checker pass. Separately retain both release-fragment inventory reviews and their content-bound source/symbol receipts; a bare reviewed flag is insufficient.


### Что переиспользовать

- `policy-engine/src/polisyos/ir/passes/core.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `_ArtifactManifestReader import (historical candidate only)`. The candidate imports a private name across module ownership; accepted E02 source not established.
- `policy-engine/architecture/public_surface/contract.toml@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `public surface contract`. Repository-owned stability/deprecation and inventory requirements; authoritative over external Python guidance.
- `policy-engine/tools/quality/validation/check_package_import_gates.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `package import gate`. Existing import-boundary/surface consumer to verify behavior, not add broad suppression.
- `policy-engine/docs/plans/active/DEBT-REGISTER.md@9f32d2706d60a5970d6fdd9ec9896242271a02ab` — `cross-module-private-names-reached-from-src`. Original class includes private attributes, runtime-quality same-package edges and container access; import-only acceptance is insufficient.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Rebind the complete accepted production-source owner/reach set, including imports, function-local imports and private attributes. Source row examples and IR overlap are starting witnesses; derive the current set and all runtime/quality/container companions.
2. Repair at canonical boundaries and extend existing tooling/tests with import and attribute negatives. Dynamic owner resolution may require a declared residual/falsifier; it cannot be reported as full closure. Avoid per-site exemptions and publicizing internals by default.
3. Resolve all current release fragments against the regenerated public API inventory, capturing affected symbols and an actual owner review receipt/content reference.
4. Make release promotion reject a bare marker, stale inventory, or incomplete symbol diff; do not broaden public API simply to satisfy a mechanical checker.


### Рассмотренные альтернативы

- **Export `_ArtifactManifestReader` publicly** — The underscore and current module ownership indicate private protocol; making it stable solely for internal coupling enlarges public commitment unnecessarily.
- **Add a per-import allowlist or reviewer boolean** — Both leave sibling private edges or unreviewed public breaks green and repeat P27/P29/P38.


### Free-grow и ресурсы

- **data or config growth:** New stable API symbols join generated inventory through the existing public-surface contract and release review.
- **extension boundary:** A new module boundary requires owner decision and public/internal contract classification; no blanket imports or suppressions.
- **resource behavior:** Inventory and import graph scale with shipped package files and public symbols; emit full discovered set and explicit exclusions.


### Миграция и восстановление

If protocol location changes, keep a deprecated compatibility adapter only when an actual downstream consumer exists and the public-surface owner accepts a bounded migration. Preserve release fragments and review receipts; revert edge repair without silently removing previously public names.


### Композиция и owners

- Importability is not public API membership; the repo's generated inventory/contract defines the decision.
- A promotion marker is subordinate to a content-bound review artifact.
- E02 candidate is not accepted-source evidence; classify as `not_established` until rebind.


### Acceptance и различающие проверки

- No unreviewed cross-module private-name reach remains in the declared measured production-source set; both sibling import and private attribute negatives exercise the actual resolver. Any unresolved dynamic class stays explicit and leaves the full source criterion open.
- Each fragment's public break inventory matches the actual source/API delta and reviewed inventory version.
- Removing the inventory review receipt while keeping the marker makes promotion fail.
- Removal of attribute-edge resolution with import checks intact is detected as missing coverage/unknown, not a green full-boundary result.


### Входы и ответственность за их получение

- Accepted E02 source commit and fresh public-surface owner review.
- Actual consumers relying on the affected API, if a compatibility window is proposed.


### Когда обоснованно отклониться

- If rebind shows the import was removed in accepted E02, record conditional absorption and still independently close release-inventory rows.
- If a private symbol has a demonstrated external consumer, route through the repo's compatibility policy rather than private-to-public rename by assumption.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [PEP 387 – Backwards Compatibility Policy](https://peps.python.org/pep-0387/) — Python's compatibility guidance distinguishes documented public API from merely importable modules and provides a deprecation approach for actual public interfaces. **Граница:** An ecosystem analogy only. PolicyOS architecture/public_surface/contract.toml and its inventory-review rules control this repository.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="DEB-04"></a>

## DEB-04 — Isolation and real-input semantic test repairs

Исходная запись: [tasks.json](../tasks.json), `tasks[id=DEB-04]`. Review: [root-review](root-review.md#DEB-04).

### Предпочтительное решение

Repair each test at the falsified property and preserve provenance for unresolved reds. For the governed-projection test, stop assigning a fake production module directly into process-global `sys.modules`; prefer the existing injectable seam, otherwise use a short `monkeypatch.context()` that registers/restores every mapping mutation, or a subprocess when import-time aliases survive mapping restoration. For N13a, remove the canonical catalog input from the actual temporary fixture and assert the producer's typed fail-closed result; repository layout is not the absence oracle. For the two value-gate reds, capture the exact discriminant bytes and decide whether the real artifact, validator or fixture is wrong before changing code or expected results. For the education-importer red, classify it inherited only after replaying the exact command at the slice base and proving its complete input denominator disjoint from changed paths (P41); otherwise name the introducing slice. Keep GY-DEF22's Foundry catalog/discovery appointment distinct from unattributed engineering red. No red gets assigned to a lane from proximity.


### Что переиспользовать

- `policy-engine/tests/unit/runtime/http/test_governed_projection_service.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `sys.modules production-module replacement test`. Debt identifies process-global replacement that persists and can pollute execution order.
- `policy-engine/tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `N13a negative-path tests`. Use the canonical catalog input itself as the negative test oracle.
- `policy-engine/tests/unit/runtime/quality/test_value_gate.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `value gate discriminant tests`. Two failing tests have unresolved dependency-discriminant bytes; do not mask red without source-of-truth attribution.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. For each failing test, record exact slice base, command, inputs, outputs and current changed-path set; use full input denominator before inherited/disjoint classification.
2. Move fake module behavior to a consumer injection seam or isolate import in a process; verify both test orders to expose leaked state.
3. Build an explicit temporary catalog fixture, delete the canonical file/artifact, and assert the same production loader refuses it; remove any layout-derived assumption.
4. Reconcile exact discriminant bytes with the real artifact producer and schema; repair only the evidenced side, then include an actual remove-input behavioral test.
5. Retain GY-DEF22 appointment as a distinct owner input; do not claim its open authority obligation explains a particular engineering red.
6. DEB-04 owns internal allocation/reconciliation for GY-DEF22 through the source-named Foundry correctness / GY-N12 execution role. At task rebind name the competent catalog/discovery reviewer and emit its source-qualified decision for the complete current bounded-claim set. Root routes this internal work; an unfilled owner is assigned work, not a request for institutional permission. GYD-15 supplies an output only if its actual accepted interface proves this claim; shared source ID alone is insufficient. P41 red attribution remains an independent conjunct.


### Рассмотренные альтернативы

- **Clear all sys.modules entries globally in test setup** — Broad cache surgery is itself order-sensitive and can leave stale object references; isolate only the touched import boundary.
- **Infer missing catalog from absent repository file** — Repository file layout is not the runtime input; a present-but-unused or externally loaded catalog would invalidate the test.
- **Mark the education failure inherited from a nearby base** — P41 requires exact slice-base replay and complete disjointness; failure to replay means `not_established`.


### Free-grow и ресурсы

- **data or config growth:** New fixtures use exact producer DTOs and catalog artifacts; new negative scenarios remove a named required input from those fixtures.
- **extension boundary:** A true import-isolation need can use an explicit subprocess fixture; do not add a general test harness without repeated evidence.
- **resource behavior:** Subprocess only for import-global state cases; ordinary tests remain fast and deterministic. Preserve bounded command/input receipts for provenance.


### Миграция и восстановление

Update affected tests in place, retain original test evidence and exact base identifiers, and revert only the defective fixture/test seam if the producer's accepted contract differs. Never rewrite historical debt to claim an inherited result without proof.


### Композиция и owners

- A test establishes property only through the real producer/consumer behavior; marker presence and repo layout do not establish source absence (P29/P38).
- A cached module replacement is not isolated if surviving references retain the fake object.
- A test failure's ownership is `not_established` until P41 replay/disjointness completes.
- DEB-04 alone owns the internal Foundry correctness / GY-N12 catalog-discovery owner acceptance for GY-DEF22. Re-enumerate the complete current bounded-claim set at source rebind; historical six is not a fixed acceptance denominator. Preserve content-bound owner readback and the separate P41 attribution requirement; neither substitutes for the other or for FA1 mechanisms.


### Acceptance и различающие проверки

- Both test orders load the real module after the fake case; process-global object identity is restored or the case is process-isolated.
- Removing canonical catalog input causes the real loader to refuse while retaining test markers.
- The value gate passes only when bytes satisfy the bound discriminator schema; no unresolved bytes are waived.
- Exact education slice-base replay and full changed-path intersection evidence support any inherited classification.


### Входы и ответственность за их получение

- Exact slice-base commit/command/input denominator for the education test.
- Source-of-truth expected discriminant artifact and producer owner decision.
- Foundry catalog/discovery owner appointment for GY-DEF22; independent of code-test blame.


### Когда обоснованно отклониться

- If reproducing value-gate bytes are not available, preserve `not_established`; do not invent an expected value.
- If old test harness holds a module alias that cannot be safely reset, use process isolation rather than escalating to global test order controls.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [The import system: module cache](https://docs.python.org/3.14/reference/import.html) — Python checks writable `sys.modules` first; deleting a cache entry does not destroy references already held by other modules, and reimport may create a different module object. **Граница:** Describes import semantics; test isolation choice still depends on the actual patched objects and consumers.
- [How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — pytest monkeypatch operations are undone at test/fixture teardown, and context scopes can undo earlier; direct global mutation without fixture tracking is not automatically repaired. **Граница:** Fixture cleanup restores registered state only and cannot erase references leaked into other already-imported modules.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="DEB-05"></a>

## DEB-05 — Native source schema and calibration contracts

Исходная запись: [tasks.json](../tasks.json), `tasks[id=DEB-05]`. Review: [root-review](root-review.md#DEB-05).

### Предпочтительное решение

Repair source schema and calibration contracts at their existing producers/readers. A malformed retained-UDF source schema must fail with an explicit malformed/unreadable result and stay distinct from a genuinely empty source portfolio; never coerce unreadable into empty. Correct the calibration schema-version grammar so the declared default itself validates: if the supported version is fixed use a real `Literal`; if it evolves, use a constrained type and validate defaults at the same boundary, with only admitted versions accepted. Remove blanket fixture-only fields that the real producer cannot emit. Keep public DTOs strict (`extra=forbid`), versioned and typed; handle evolution with a new schema/version or an explicit adapter, not permissive extras. Verify by persisting current producer output and reading it with a fresh consumer, then mutate malformed schema, extra fields, missing data and invalid version individually to check the right refusal. Census all accepted-source _with_runtime_fixture_authority callers and payload-kind families, including source test.root/test.child siblings; 31 calls/28 kind strings are historical, never a future constant. Reuse type/producer serialization at the helper boundary; verify no unsupported authority fields are injected or persisted for any covered family. Generic CAS persistence proves bytes, not schema validity, and does not become the schema owner by default.


### Что переиспользовать

- `policy-engine/src/polisyos/data_forge/kernel/artifacts.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `ArtifactRef / schema version patterns / load_json_artifact`. Existing artifact identity/versioned reader boundary; preserve read/parse failure distinctions.
- `policy-engine/src/polisyos/foundry/calibration/report.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `CalibrationReport and nested DTOs`. Owner schema location for calibration contract; exact version validator/default needs accepted-tree rebind.
- `policy-engine/tests/integration/foundry_calibration/test_method_calibration_bridge.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `calibration producer-reader bridge`. Existing integration surface for actual output and fresh-reader verification.
- `policy-engine/tests/_helpers/runtime_http.py@9f32d2706d60a5970d6fdd9ec9896242271a02ab` — `_with_runtime_fixture_authority`. Shared mapping mutation is the class-wide boundary; exact accepted-source helper/caller set must be rebound.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Identify the exact retained-UDF producer schema and distinguish parse/read errors, malformed source schemas and valid empty source records.
2. Repair calibration version type/default together; make the default pass the same validation as received input.
3. Foundry/runtime test owners select the existing helper/schema boundary and enumerate its full current callers/kinds. Replace blanket authority decoration with actual supported producer serialization; retain strict extras and source/empty distinctions.
4. Persist one produced artifact, then load it through a fresh reader and verify accepted version/unknown-field/malformed behavior.


### Рассмотренные альтернативы

- **Use `extra=allow` to keep fixtures passing** — It lets unsupported fields become silent contract surface and obscures producer/consumer drift.
- **Treat parse failure as empty** — That loses the source-portfolio distinction and can make an absence claim falsely complete.
- **Broaden version regex until it passes** — An unconstrained string repairs the example while weakening the schema; type actual supported grammar.


### Free-grow и ресурсы

- **data or config growth:** Add explicit versioned schema variants and adapters for newly supported source shapes or calibration versions.
- **extension boundary:** Unknown producer shape remains rejected/ambiguous until a typed variant and migration reader are admitted.
- **resource behavior:** Schema validation is per artifact; size/depth limits remain bounded at existing parsing boundary.


### Миграция и восстановление

Use schema-versioned expand/read-verify/retire: accept old versions through a narrow reader only where proven compatible, emit the new version, and retain source payloads/receipts. Revert producer changes without relabeling old malformed artifacts as empty.


### Композиция и owners

- Schema parse success establishes type/shape only, not authority or input truth.
- Read error, malformed schema and valid empty input are distinct outcomes.
- Public DTO evolution is strict and versioned; default values are validated at the boundary.


### Acceptance и различающие проверки

- Default calibration schema version validates under the same predicate applied to supplied versions.
- A producer-generated report has no unrecognized fixture-only fields and passes a fresh reader.
- Malformed retained source does not produce an empty source portfolio.
- Invalid version, missing required field and extra field each yield the intended typed refusal.
- Census all accepted-source _with_runtime_fixture_authority callers and payload-kind families, including source test.root/test.child siblings; 31 calls/28 kind strings are historical, never a future constant. Reuse type/producer serialization at the helper boundary; verify no unsupported authority fields are injected or persisted for any covered family. Generic CAS persistence proves bytes, not schema validity, and does not become the schema owner by default. Matched removal of the helper protection must fail the non-calibration sibling witness while calibration-only tests could still pass.


### Входы и ответственность за их получение

- Actual producer payloads and supported source-schema variants.
- Owner decision on calibration version compatibility policy.


### Когда обоснованно отклониться

- If historical stored artifacts rely on the malformed interpretation, preserve them as legacy ambiguous and add a migration reader; never silently reinterpret.
- If producer emits an extra field in the accepted tree, classify producer/contract drift before deleting fixture data.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [Pydantic strict mode and models](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/) — Strict mode reduces implicit coercion, while Pydantic model validation establishes output types and constraints rather than proving truth of input claims. **Граница:** Strictness is a parsing boundary only. It is not evidence provenance, authority, or semantic adequacy.
- [Understanding JSON Schema: object properties](https://json-schema.org/understanding-json-schema/reference/object) — JSON Schema permits additional properties by default; `additionalProperties: false` is an explicit closed-object rule. **Граница:** Schema closure can prevent unreviewed fields but does not itself solve version migration or semantic truth.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="DEB-06"></a>

## DEB-06 — Canonical epoch reissue and current-decision lineage

Исходная запись: [tasks.json](../tasks.json), `tasks[id=DEB-06]`. Review: [root-review](root-review.md#DEB-06).

### Предпочтительное решение

Wire the residual transition semantics through the existing strict epoch verifier/intake and common lifecycle writer. The fifth authorized merge must be an append-only reissue that records merge premise, both predecessor refs, resulting merged state, admissibility and preservation check; read back the emitted receipt before closing. Do not reopen the already-landed positive verifier/denominator producer: its open item is strict production composition. Permit a governed public record to represent a later epoch head with a typed currentness/limited/replay result rather than an unconditional refusal, while keeping stale or non-replayable heads from appearing current. Split epoch-origin programmer/configuration errors from missing institutional inputs into distinct typed outcomes. Carry current packet lineage/currentness through LIF-02's canonical head/lifecycle writer; UI-19 owns the governed projection. GY-DEF23's signing/producer-identity appointment is a real institutional dependency but must remain typed-empty and must not block feature construction.


### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/epoch_transition_verification.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `CanonicalEpochTransitionVerifier / ProducingEpochDenominatorReconciliationReader`. Positive transition verification and denominator reconciliation are existing owners; open criterion is strict production composition.
- `policy-engine/src/polisyos/runtime/quality/epoch_transition_origin.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `EpochTransitionOriginStatement / FileEpochTransitionOriginOwner`. Strict origin/intake boundary to extend with non-collapsing failure taxonomy.
- `policy-engine/src/polisyos/scientist/validation/decision_validity.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `epoch validity receipt and reconciliation persistence`. Existing persisted lifecycle/evidence adapter, not a new parallel history store.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Rebind current verifier, production path, governed-record reader and current packet source after E02 acceptance; map each source predicate to the owning existing component.
2. Represent merge as a new transition artifact with both parent refs and explicit premises; verify all predecessors survive and the exact new head reads back.
3. Extend replay/currentness composition with typed later-head status and limitation; distinguish current, stale, partial/replay-limited and refusal without erasing history.
4. Return distinct typed errors for malformed origin/configuration versus required input absent; preserve candidate behavior when unknown.
5. Use LIF-02 for current lineage/head writes and UI-19 for surface; keep external signer appointment as a typed-empty limitation.


### Рассмотренные альтернативы

- **Replace old epoch head with merged head** — That destroys the independent predecessor lineage and violates the fifth transition criterion.
- **Refuse every later head** — It blocks honest replayable later epochs and hides a representable typed currentness limitation.
- **Mark verifier producer missing** — The positive verifier and denominator reconciliation already landed; only production composition remains open.


### Free-grow и ресурсы

- **data or config growth:** New epoch families add typed predicates and replay adapters under the existing epoch schema/version registry.
- **extension boundary:** New signing scope or distinct institutional act requires a typed external evidence profile, not an inferred default signer.
- **resource behavior:** Reissue and replay cost scale with predecessor history; persist references and bounded summaries rather than copying unbounded history into each head.


### Миграция и восстановление

Add a versioned merge/replay record and read old heads unchanged. On incompatible composition, keep predecessors, mark dependent claim currentness limited, and restore the prior reader without erasing newer receipts.


### Композиция и owners

- A reissue binds both parent heads, merge premise, merged content and exact readback.
- Later epoch does not imply current; currentness is evaluated against valid/known time and replayable lineage.
- Input absence and programming error produce distinct statuses; external authority does not block candidate capability.
- DEB-06 emits the actual persisted current-decision lineage/reissue receipt through LIF-02; UI-19 reads it afresh into the governed API/MACHINE projection. Source cut, both predecessors, expected head, current/limited status and original as-known issue remain distinguishable. Reciprocal acceptance references bind emission→observation stages, not whole-task completion cycles; interface preparation is independent. GY-DEF23 is context owned by DEB-09, not a DEB-06 disposition predicate.


### Acceptance и различающие проверки

- Successful fifth merge leaves both predecessor references verifiable and the new head is read back.
- A later compatible head returns a typed replay/currentness result; an unbound or expired head cannot claim current.
- Removing required origin input differs from invalid program configuration in status/remediation.
- Strict production consumer accepts the real positive verifier receipt, while signer absence remains explicit.
- Fresh UI-19 observation of the actual emitted DEB-06 receipt is required. Remove source-cut/expected-head binding while keeping labels: consumer cannot project a current successor.


### Входы и ответственность за их получение

- Purpose-scoped transition signer and producer identity appointment for authority-band claims.
- Accepted current packet/head source and actual merge premise supplied by both lane owners.


### Когда обоснованно отклониться

- If rebind shows positive verification no longer composes with the production route, reopen the exact producer/bridge owner rather than reverting the closed denominator criterion.
- If existing epoch schema cannot hold second reissue checkpoint, version the schema through its owner and retain old records.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [TUF roles and metadata](https://theupdateframework.io/docs/metadata/) — Trust decisions are purpose/role-bound and bind key thresholds, signatures, hashes, versions, and expiry; old metadata must be detected rather than silently promoted. **Граница:** Software-update repository model; use as a design comparison for typed scope/time binding, not as a PolicyOS authority scheme or a call to adopt TUF.
- [PolicyOS identity and custody boundary](../../../../../../policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — The four-way scope test is own when absence makes our published claim false; integrate when external output changes our claim validity; observe when only answerability changes; otherwise out_of_scope. Candidate-band unknowns may be carried as declared limitations; authority-band claims fail closed when required scope is unknown. **Граница:** This is the ratified PolicyOS rule, not a substitute for content-bound evidence establishing the factual predicate in an individual case.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="DEB-07"></a>

## DEB-07 — Ceiling vocabulary and destination allocation

Исходная запись: [tasks.json](../tasks.json), `tasks[id=DEB-07]`. Review: [root-review](root-review.md#DEB-07).

### Предпочтительное решение

Re-enumerate current CORR destination and INT-R2 meaning/owner dispositions; five/five is the historical reviewed snapshot, not a fixed runtime denominator. Keep distinct semantic acts separate and preserve delivered dispositions. Route each semantic proposal to its appointed owner and preserve typed unknown/incomparable relations. For estimand-binding strength, define one versioned meaning per intended target, bind quantity-defining referents and represent identity/equivalence/derivation/transport separately; use a partial order only where the owner justifies it, with incomparable and unknown values explicit. A changed target horizon/regime must not compare equal by name. Use the existing WDI owner `runtime/quality/acquisition_planner.py` for owner-admitted acquisition cost on the exact variables/route. DS15's production route is exercised only with controlled fixtures/test cost and SQLite; it is not evidence of real-world use, a valid production cost selection or PostgreSQL concurrency. Keep the GapAcquisitionCase union owned by INT-R2 ratification; keep numeric VOI metric design with DEB-13. Do not substitute the method-selection `compute_voi` helper unless equivalence of semantics is proven. For the source-selected free WDI route, the canonical runtime/quality/acquisition_planner.py cost-schedule owner may admit dated expert_hours/calendar_days/collection_mode effort under the principal’s 2026-09-17 option A: first inspect actual connector/comparable-ingest evidence, prefer measured comparable effort, otherwise explicitly label and justify the owner estimate. Neither fixture hours/days nor a cap is the basis. A paid/licensed selected source invalidates that premise and needs its real quote/rights evidence; no default institutional price request for free-data engineering.


### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `AcquisitionCostBasisRecord / produce_acquisition_cost_basis_record`. Canonical WDI acquisition-cost owner; current evidence has no owner-admitted exact cost row for served variables.
- `policy-engine/src/polisyos/foundry/methods/selection/requirements.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `select_method_candidates_for_requirements`. Existing method-requirement owner for measured consumer paths, not an owner for WDI costs or numeric policy VOI.
- `policy-engine/src/polisyos/foundry/methods/selection/advisor.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `compute_voi`. A method-selection helper; semantic equivalence to DS15 acquisition VOI is unestablished, so it is not a default reuse.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. team-architecture performs the CORR/INT-R2 allocation assigned by the original source: for each current semantic slot emit existing owner/path, exact meaning/use, real producer/consumer and disposition. Preserve already delivered mechanical crosswalks; internal missing producers become assigned tasks, not external-input waits. A genuine normative/meaning choice remains a source-qualified proposal until accepted. Do not fabricate semantic identity or institution authority.
2. Reconcile each vocabulary row with its original meaning, distinct consumer and authorized owner; preserve settled owner/decision state and only list genuine unresolved semantic acts.
3. Specify target-bound estimand referents and represent relationship as typed equality/derivation/transport/incomparability with version and regime/horizon bindings.
4. Admit WDI cost only through the existing cost record with exact variable set, route, source, purpose and time; no test-only hypothetical cost enters production evidence.
5. Keep DS15's deterministic bundle producer/composition status as built; separate real institutional appointments, valid scoped inputs and actual cost selection from it.
6. Leave INT-R2's `GapAcquisitionCase` union to its owning ratification and keep DEB-13 responsible for metric formula/decision basis.
7. CAP-03 routes the actual admitted cost artifact from the existing native cost owner; DEB-07 records the original row’s basis/allocation disposition and consumes the same receipt. Exact shared file lease forbids two cost writers.


### Рассмотренные альтернативы

- **Create one total ordering over all binding terms** — The source decision preserves distinct relations and does not establish that all targets/regimes are comparable.
- **Count vocabularies or owners as a single gap metric** — It conflates distinct semantics and retains obsolete counts instead of current consumer/owner dispositions.
- **Reuse method-selection `compute_voi` as the acquisition metric** — Same name does not prove same estimand, utility, target population, or cost semantics.


### Free-grow и ресурсы

- **data or config growth:** Add owner-ratified meanings, target referents and purpose profiles through existing versioned semantic registries; cost rows grow per admitted acquisition route.
- **extension boundary:** A new relation, regime or case union needs its semantic owner and consumer conformance; no free-form vocab string becomes an ordering or authority.
- **resource behavior:** Comparison scales with involved terms/targets; unresolved or incomparable pairs return typed outcomes rather than forcing a total-order search.


### Миграция и восстановление

Version semantic definitions and cost records; retain legacy bindings and identify migrations without changing historic relation. If owner approval or actual cost is absent, preserve typed-empty or blocked status and the existing working producer route.


### Композиция и owners

- A cost row is independent of a VOI utility metric; neither supplies the other's missing inputs.
- A fixture-backed positive route proves route behavior only, not a real selected use or institutional authority.
- Different horizons/regimes/targets are non-equal unless bound by explicit owner-defined relation.


### Acceptance и различающие проверки

- No four-of-five or eight-vocabulary count remains as a current semantic claim.
- Every current source-enumerated destination/meaning has a distinct purpose/owner/consumer disposition; preserve settled and unresolved semantic parts without a fixed five/five gate.
- A horizon/regime change changes the target binding; unsupported cross-target ordering returns incomparable/unknown.
- A missing real WDI cost still refuses costed production route while the fixture-only demonstration remains correctly scoped.


### Входы и ответственность за их получение

- Owner decision for open CORR B1 reviewer/profile and B2 semantic producer, plus actual first regime/consumer propositions where open.
- Foundry owner ratification for estimand semantics and INT-R2 owner ratification of `GapAcquisitionCase`.
- For the source-selected free WDI route, the canonical runtime/quality/acquisition_planner.py cost-schedule owner may admit dated expert_hours/calendar_days/collection_mode effort under the principal’s 2026-09-17 option A: first inspect actual connector/comparable-ingest evidence, prefer measured comparable effort, otherwise explicitly label and justify the owner estimate. Neither fixture hours/days nor a cap is the basis. A paid/licensed selected source invalidates that premise and needs its real quote/rights evidence; no default institutional price request for free-data engineering.
- Any required acquisition-admission and decision-signer acts remain typed-empty until assigned.


### Когда обоснованно отклониться

- If the accepted source already resolves an owner/semantic row, record absorption with evidence instead of rebuilding a registry.
- If someone proposes numeric value or monetary amount, route to DEB-13 and its metric owner; do not add it here.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [ICH E9(R1) estimands and sensitivity analysis guideline](https://database.ich.org/sites/default/files/E9-R1_Step4_Guideline_2019_1203.pdf) — A decision estimand needs explicit population, variable, intercurrent-event strategy, and population-level summary; comparability depends on the question and setting. **Граница:** Clinical-trial-specific guidance; it is an example of fully specified estimands, not a universal PolicyOS metric contract.
- [Value of Information Analytical Methods: ISPOR VOI Analysis Emerging Good Practices Task Force, Report 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC7373630/) — VOI compares expected decision-payoff improvement from information with acquisition/research cost; EVPI, EVPPI, EVSI and ENBS answer distinct questions, and population value depends on beneficiary population and useful horizon. **Граница:** Health-technology-assessment application. Transfer the explicit decision model, assumptions, population, horizon, and cost separation; do not import its utility or monetary units into PolicyOS without an owner decision.
- [TUF roles and metadata](https://theupdateframework.io/docs/metadata/) — Trust decisions are purpose/role-bound and bind key thresholds, signatures, hashes, versions, and expiry; old metadata must be detected rather than silently promoted. **Граница:** Software-update repository model; use as a design comparison for typed scope/time binding, not as a PolicyOS authority scheme or a call to adopt TUF.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="DEB-08"></a>

## DEB-08 — Recursive-cycle and cross-scope confidence residuals

Исходная запись: [tasks.json](../tasks.json), `tasks[id=DEB-08]`. Review: [root-review](root-review.md#DEB-08).

### Предпочтительное решение

Close the GY evidence-consumer gaps at their named owners without collapsing different missing stages. GY-GAP2's cross-scope confidence composition is blocked on a product decision, not a missing producer: specify the owner-approved scope-composition rule before emitting a combined confidence. GY-GAP3 needs its controlled release-family transcript from its signal owner; a fixture/test transcript does not count. GY-GAP5 still needs a production recursive-cycle run enumerator with full run/row denominator. GY-GAP6 needs per-row evidence linking re-entry and deeper terminal movement. For `ds15-gy-gap6-evidence-register-closure`, the DS15 runtime receipt already exists; the remaining work is the GY consumer admitting that receipt into its own register and producing a closure disposition. Preserve the receipt's producer authority and bind it to the exact row, run, time, rule version and source artifacts. Count independent cases, not repeated views or fixture-only runs; retain the current refusal of any unsupported sequence-level numeric claim. No FDR threshold is imported from generic literature without an owner-designated exploratory family and dependence model.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `confidence ledger scope composition`. Existing confidence artifact owner; cross-scope composition is an open product decision.
- `policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `recursive generation cycle`. Natural production owner for complete recursive-cycle run enumeration; verify accepted-tree currentness before assigning.
- `policy-engine/src/polisyos/runtime/quality/acquisition_route_loop.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `acquisition re-entry evidence`. Producer path already emits DS15 runtime receipt; GY closure consumer remains separate.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. For each GY-GAP row bind its actual producer, persisted record, GY evidence/register consumer and complete operational denominator; preserve current owner/status.
2. Record GY-GAP2 as product-decision dependency until a supported cross-scope combination rule exists; do not synthesize a confidence score from incompatible scopes.
3. Have the signal owner produce a controlled GY-GAP3 transcript and the production GY-GAP5 owner enumerate recursive runs; keep fixtures marked non-production.
4. Bind GY-GAP6 re-entry/deeper-terminal evidence per row, then admit the already-produced DS15 receipt through GY's own receipt and closure path.
5. Reconcile tested cases to complete run/row denominator; do not count repeated presentations of one event as independent cases.

### Рассмотренные альтернативы

- **Build another DS15 receipt producer for GY** — The runtime receipt already exists; the missing component is GY's independent consumer/admission path.
- **Aggregate cross-scope confidence by averaging** — No ratified semantic composition or independence premise supports that operation.
- **Use a generic BH threshold as the exploratory policy** — FDR procedure assumptions include a declared testing family and dependence conditions; those are not established by a transcript or event count.

### Free-grow и ресурсы

- **data or config growth:** New release families, recursive runs and row outcomes append typed evidence to existing GY registers with versioned event semantics.
- **extension boundary:** New cross-scope aggregation or sequential test policy needs a decision/metric owner and evidence model; unknown scopes remain incomparable.
- **resource behavior:** Enumeration is proportional to production runs and rows; retain compact receipts/provenance and avoid re-counting repeated views as new cases.


### Миграция и восстановление

Append evidence and admission receipts; do not mutate producer history or close GY rows when the consumer has not admitted evidence. If consumer validation fails, keep source receipt and reopen only the dependent closure disposition.


### Композиция и owners

- Producer receipt and GY evidence admission are distinct capabilities; the first does not auto-close the second.
- Scope-composed confidence requires explicit composition semantics and bound source scopes.
- Test/fixture numerator is not production evidence; repeated views are not independent observations.


### Acceptance и различающие проверки

- GY-GAP2 cannot issue combined value with cross-scope unknown/incomparable inputs.
- GY-GAP3 transcript is bound to controlled source, release family, rule version and full row set.
- GY-GAP5 enumerates actual production recursive-cycle runs; GY-GAP6 binds each row's reentry and deeper terminal movement.
- Existing DS15 receipt appears in GY's evidence register and is consumed into explicit closure result without a duplicate producer.


### Входы и ответственность за их получение

- Product owner decision for GY-GAP2 scope composition.
- GY signal owner controlled release-family transcript and production owner run enumerator.
- Owner-provided complete run/row denominator and any separately ratified exploratory-testing family/assumptions.


### Когда обоснованно отклониться

- If current source contains no production run owner, preserve `absent/unallocated` and assign owner before coding a surrogate.
- If the only evidence is fixture-backed, retain it as route/test evidence and do not advance status to production closure.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing](https://academic.oup.com/jrsssb/article/57/1/289/7035855) — The Benjamini–Hochberg procedure controls FDR under its stated independent-test condition; repeated/exploratory discovery requires the declared testing family and dependence assumptions. **Граница:** This result does not confer authority to any PolicyOS anomaly or solve longitudinal/repeated-look control without a fitted and justified procedure.
- [PROV Model Primer](https://www.w3.org/TR/prov-primer/) — PROV represents entities, activities, usage/generation, agents, and responsibility so a reader can trace artifact lineage and provenance assertions. **Граница:** A provenance vocabulary records relationships; it does not decide whether an external function belongs in PolicyOS or whether evidence has admissible authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="DEB-09"></a>

## DEB-09 — Institutional inputs and exact authority slots

Исходная запись: [tasks.json](../tasks.json), `tasks[id=DEB-09]`. Review: [root-review](root-review.md#DEB-09).

### Предпочтительное решение

Treat the remaining slots as distinct institutional acts: epoch predicate-policy signer; epoch-transition signer/producer identity; independent complete-history holder; external signed v2 delegation plus current mandate-owner evidence; and purpose-scoped semantic epoch-qualification admission of the signed policy and exact native relation. Keep each typed-empty until the actual institution supplies a current, purpose/scope/time-bound artifact. The strict runtime intake, epoch-history adapter and DS15 deployment composition already exist where the source says so; use their verification and refusal paths. A transition signer is not the predicate-policy signer, a producer identity is not an independent history holder, and DS15 mandate composition is not the external mandate itself. Do not invent a permissions administrator or let missing external appointments gate candidate capability construction. For authority-band claims, admission requires resolve + content bind + verifier provenance; for candidate-band exploration, preserve an explicit unknown/limited route.


### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/epoch_transition_origin.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `EpochTransitionSigningProfileAdmissionReader / FileEpochTransitionOriginOwner`. Existing typed verification/intake path for epoch-origin evidence; external signer identity remains supplied evidence.
- `policy-engine/src/polisyos/runtime/quality/institutional_provenance.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `institutional provenance intake`. Existing evidence path to use for producer/institution identity; do not add another admin owner.
- `policy-engine/src/polisyos/scientist/validation/decision_validity.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `epoch receipt and history admission`. Existing history/receipt reader, including already-built GY-DEF23 adapter composition.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Rebind every status and adapter: distinguish implemented engineering path from open institutional appointment and from unallocated owner slot.
2. Publish an exact role-to-claim-scope matrix with purpose, subject, valid/known time, required evidence and refusal code; use it only as an intake contract, not an appointment.
3. Verify the real incoming artifact against the exact role/profile, signature/identity evidence, content digest, expiry and complete relevant history where required.
4. Keep missing/expired/unverifiable evidence typed-empty or blocked for authority-band claims while allowing candidate feature construction with declared limits.
5. Do not assign GY-DEF22 implementation or internal owner acceptance here: DEB-04 owns that work and its separate P41 conjunct. Preserve this task’s actual institutional-slot requirements; a shared source reference creates neither a second writer nor an extra global prerequisite.


### Рассмотренные альтернативы

- **Have PolicyOS self-appoint or use a local default signer** — The external institution owns the act; self-attestation would turn an unappointed slot into authority by implementation default.
- **Create a general institution/mandate administration service** — This adds a sovereign subsystem; the boundary calls for typed evidence intake and scoped claim reaction only.
- **Block all development until appointments arrive** — The source explicitly says appointments are claim-scoped and should not gate capability construction; only authority-band promotion waits.


### Free-grow и ресурсы

- **data or config growth:** New institutional roles add purpose-scoped typed profile entries under existing evidence intake; actual identity artifacts are supplied externally.
- **extension boundary:** New authority purpose or signature role requires a distinct owner and verification contract; no generic role string or wildcard permission.
- **resource behavior:** Verification cost follows artifact size/history scope; bound history and surface expiry/coverage gaps rather than accepting partial history as complete.


### Миграция и восстановление

Add role profile versions without changing historic appointment meaning. Revocation/expiry or invalid evidence marks dependent claims stale/limited and preserves the last signed receipt; restore a prior profile only through a versioned, source-backed transition.


### Композиция и owners

- A valid signature binds signer, purpose, scope, content, valid time and currentness; signature alone is not appointment authority.
- Each external role is non-substitutable unless its mandate explicitly says otherwise.
- Candidate feature path may proceed with typed unknown; authority-band promotion fails closed when appointment is required and absent.
- GY-DEF22 internal catalog/discovery owner allocation is owned by DEB-04; this task owns GY-DEF23 and the other actual institutional slots. Scientist Decision Validity/Runtime quality provide the internal verifier/intake; they cannot appoint external signers.


### Acceptance и различающие проверки

- A real supplied artifact resolves to exactly one intended claim role/scope and passes content/provenance/time verification.
- Missing, expired, wrong-purpose, self-issued and incomplete-history evidence each retain distinct refusal/limitation.
- No new internal owner or local default signer fills any external slot.
- An engineering test red is not assigned to GY-DEF22 or a lane without P41 evidence.


### Входы и ответственность за их получение

- Actual predicate-policy signer, transition-signing identity, independent history holder, signed delegation artifact/current mandate-owner evidence, and semantic epoch-qualification admission.
- GY-DEF22 is routed to DEB-04 for internal owner acceptance and independent provenance attribution; it is not a missing external appointment or required supplier for every DEB-09 slot.


### Когда обоснованно отклониться

- If an institution changes role/purpose/mandate, require new evidence and revalidate dependent claims; do not extend an old signature by inference.
- If an existing typed path cannot distinguish an external role, add a narrow adapter or schema version, not a new admin service.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [TUF roles and metadata](https://theupdateframework.io/docs/metadata/) — Trust decisions are purpose/role-bound and bind key thresholds, signatures, hashes, versions, and expiry; old metadata must be detected rather than silently promoted. **Граница:** Software-update repository model; use as a design comparison for typed scope/time binding, not as a PolicyOS authority scheme or a call to adopt TUF.
- [PolicyOS identity and custody boundary](../../../../../../policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — The four-way scope test is own when absence makes our published claim false; integrate when external output changes our claim validity; observe when only answerability changes; otherwise out_of_scope. Candidate-band unknowns may be carried as declared limitations; authority-band claims fail closed when required scope is unknown. **Граница:** This is the ratified PolicyOS rule, not a substitute for content-bound evidence establishing the factual predicate in an individual case.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="DEB-10"></a>

## DEB-10 — Independent print and accessibility evidence

Исходная запись: [tasks.json](../tasks.json), `tasks[id=DEB-10]`. Review: [root-review](root-review.md#DEB-10).

### Предпочтительное решение

Keep accessibility countersign and inherited C13 print reconciliation as distinct closure rows. For DS11-EXTERNAL-A11Y-COUNTERSIGN, receive an independent evaluator's actual content-bound report: exact artifact/content digest, scope and sample, WCAG version/criteria, evaluation tool/environment, evaluator identity/provenance, observation time and limitations. A sample-based evaluation may support only its declared scope; it does not imply whole-product conformance. For DS11-INHERITED-C13-PRINT-RECEIPT and `ds10-c13-print-receipt-reissue`, captures and C13 conjunction are already current; the present blocker is a separately owned schema-versioned DS18 reconciliation because the governed schema admits one checkpoint but now requires an append-only second. Create that extension only if current schema cannot represent both checkpoints, preserve the old checkpoint and annotations, and verify exact content/browser/print binding. Historical masking/504s are not the present criterion. UI may project the resulting evidence but cannot create or self-countersign it.

### Что переиспользовать

- `policy-engine/apps/runtime-dashboard/src/shared/export/printExport.ts@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `print export content binding`. Existing print projection/export path; rebind content and browser binding against accepted source.
- `policy-engine/apps/runtime-dashboard/src/shared/export/printExport.test.ts@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `print export verification`. Existing test surface for exact content/export relationship; not evidence of independent accessibility assessment.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. For accessibility, obtain the external evaluator's scope and report schema; bind report to content, criteria version, representative sample and evaluator identity with explicit exclusions.
2. Admit the report only through the existing verification path, returning scoped pass/partial/limited/contested outcomes rather than a binary universal claim.
3. For C13, compare the original one-checkpoint DS18 schema to the exact second-checkpoint requirement; only if unrepresentable, add an append-only versioned reconciliation record with references to both checkpoints.
4. Keep the inherited and direct C13 rows' separate closure predicates; confirm exact rendered content, browser and print capture match the reconciliation.

### Рассмотренные альтернативы

- **Treat automated accessibility test or internal checklist as countersign** — Neither constitutes the required independent, content-bound external assessment.
- **Overwrite the first DS18 checkpoint** — The requirement is a second append-only checkpoint and history preservation; replacement loses the original reconciliation context.
- **Close the inherited row when the direct row closes** — The register explicitly preserves distinct closure signals; one must not close the other.

### Free-grow и ресурсы

- **data or config growth:** New accessibility criteria/report versions and print checkpoints attach to versioned evidence schemas and exact content digests.
- **extension boundary:** New evaluation regimes need external qualified evaluator/profile and conformance; a dashboard-specific assertion cannot stand in for evidence.
- **resource behavior:** Bind full report plus named sample; cap and declare samples while exposing unsampled scope. Store checkpoints as references to avoid duplicating large print artifacts.


### Миграция и восстановление

Keep existing captured artifacts and first checkpoint immutable; version schema only when the second checkpoint is not expressible. If external report verification fails or becomes stale, withdraw only dependent accessibility projection and preserve the submitted report and history.


### Композиция и owners

- Accessibility evidence is content-, version-, evaluator-, scope- and time-bound; sample coverage limits the claim.
- C13 reconciliation requires both append-only checkpoint lineage and exact content/browser/print binding.
- Internal UI/tests can consume evidence but cannot create the external countersign.


### Acceptance и различающие проверки

- Independent report resolves to content and declares exact sample/criteria; changing content invalidates binding.
- An unsampled critical page cannot be hidden behind an overall pass unless the method explicitly supports that conclusion.
- Second checkpoint is append-only, schema-versioned if necessary and both C13 row IDs retain separate closure dispositions.
- Current blocker is the schema reconciliation; historical reds are not used as present acceptance criteria.


### Входы и ответственность за их получение

- Current independent accessibility evaluator, content-bound/verifiable assessment and declared scope; require a cryptographic signature only if the original verification criterion specifies one.
- Owner of DS18 schema/reconciliation to authorize and admit a second checkpoint representation.


### Когда обоснованно отклониться

- If current DS18 schema already supports a second checkpoint after rebind, wire it and do not add a duplicate schema.
- If the external evaluation is only a sample, constrain its public projection to that sample and explicit scope.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [WCAG Evaluation Methodology (WCAG-EM) 2.0](https://www.w3.org/TR/WCAG-EM/) — A documented accessibility evaluation defines its scope, explores the product, selects a representative sample, evaluates it, and reports outcomes; sampling does not silently become whole-product inspection. **Граница:** Accessibility methodology does not provide an independent countersign, nor replace the exact C13 print/content criteria or required qualified evaluator.
- [TUF roles and metadata](https://theupdateframework.io/docs/metadata/) — Trust decisions are purpose/role-bound and bind key thresholds, signatures, hashes, versions, and expiry; old metadata must be detected rather than silently promoted. **Граница:** Software-update repository model; use as a design comparison for typed scope/time binding, not as a PolicyOS authority scheme or a call to adopt TUF.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="DEB-11"></a>

## DEB-11 — Foreign residuals: connector cleanup and worktree tooling

Исходная запись: [tasks.json](../tasks.json), `tasks[id=DEB-11]`. Review: [root-review](root-review.md#DEB-11).

### Предпочтительное решение

Execute the recovered foreign predicates in their existing owners after accepted-source rebind. The Atlas source identifies two unclosed aiohttp connector/session diagnostics from authorized discover_data_sources/resolve_data_needs, plus fresh-worktree toolchain baseline and DS1/DS19 non-receipts. Reproduce the exact authorized calls and use the canonical application-owned session lifecycle, closing success, failure and cancellation paths without one session per request. Use existing workspace bootstrap/doctor and corepack pnpm frozen-lock discipline where required; verify the actual editable checkout/import and source/lock identity. Foreign routing is not completion and is not a reason to restart abstract contract discovery. If rebind reveals a genuine missing detail, recover that detail while implementing independent known work; preserve original owner closure.

### Что переиспользовать

- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/README.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `Atlas master plan foreign residual references`. The referenced connector/session and worktree baseline source locations are the bounded recovery route; register rows themselves do not specify closure.
- `AGENTS.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `workspace bootstrap and toolchain facts`. Existing repository tooling and frozen pnpm/uv environment constraints are the owner source; do not run them as part of this research.
- `policy-engine/tools/devx/workspace/README.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `workspace tooling entry point`. Existing workspace tooling owner, to rebind and use only if original worktree criterion calls for it.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Read the already recovered source_criterion_locations in tasks.json and full original paragraphs, rebind the exact two connector diagnostics and fresh-worktree commands, then allocate native path/resource leases.
2. For connector work, identify the canonical aiohttp session owner and demonstrate its current close lifecycle; make a bounded owner-path fix only if that exact criterion is confirmed.
3. For worktree work, reproduce the stated fresh-checkout baseline using the owner's existing commands and pinned lock semantics; distinguish absent setup from a product defect.
4. Return to the originating lane for review and closure; update local inventory only through that lane's admitted evidence/disposition.

### Рассмотренные альтернативы

- **Assume `foreign` means an unclosed code bug and implement cleanup** — The original criterion is missing; this would invent scope and could close the wrong property.
- **Create a new session manager or worktree bootstrap platform** — Both are potentially already owned; no exact unmet capability or requirement is established.
- **Treat current repo setup success as closure** — No task-level closure predicate ties that observation to either foreign row.

### Free-grow и ресурсы

- **data or config growth:** Only add a connector lifecycle profile or workspace check if the recovered original contract names it and existing owner provides extension point.
- **extension boundary:** A genuinely new transport or worktree policy requires the foreign owner and a typed adapter; this row cannot unilaterally create one.
- **resource behavior:** Use one bounded connector/worktree reproduction; no broad scan, installs or background processes unless separately authorized by the originating task.


### Миграция и восстановление

No schema or code migration is justified until original criteria are recovered. If an owner fix is later made, retain the foreign artifact/history and use its own rollback procedure; do not relabel the row based on this proposal.


### Композиция и owners

- An inventory pointer is not a complete acceptance contract.
- aiohttp session cleanup advice applies only after original property confirmation.
- A worktree environment receipt is evidence of setup only, not proof of all project verification.


### Acceptance и различающие проверки

- Close the two recovered aiohttp connector/session diagnostics from the authorized discover_data_sources/resolve_data_needs handlers; normal, exceptional and cancellation paths release application-owned resources without closing a still-shared caller-owned session.
- Reproduce the recovered DS19-style fresh-worktree baseline with exact source, commands, lock and package links; distinguish setup non-receipt from product defect.
- Source rebind checks the already pinned original criteria; their known existence is not a foreign-owner blocker. Any genuinely new ambiguity is limited to its actual unresolved predicate.


### Входы и ответственность за их получение

- Read and rebind the already pinned Atlas connector/session criteria and DS19 fresh-worktree baseline. These are existing source records, not missing owner instructions.
- Allocate existing GY/Fabric and workspace/tooling owners; obtain only genuinely required environment access/permissions.


### Когда обоснованно отклониться

- If plan references point to already-closed source rows, record their canonical dispositions with source pins rather than duplicating fixes.
- If accepted-source drift leaves a genuinely unresolved predicate, name that precise delta and supplier; continue the recovered connector/tooling obligations and do not report their entire criterion as unstated.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [aiohttp client reference](https://docs.aiohttp.org/en/stable/client_reference.html) — ClientSession owns connection pooling and supports context-managed closing; its recommended lifetime is application-level for ordinary use, not per request. **Граница:** This only supports a bounded lifecycle repair if the original foreign task confirms session cleanup is its criterion; it does not establish that this foreign row has that criterion.
- [Locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/) — uv lock/sync can check metadata-lock consistency, and exact sync removes packages outside the lock; frozen and locked modes have different verification semantics. **Граница:** A lockfile pins package resolution, not OS/locale/environmental inputs or generated artifact semantics. Repository-specific setup commands remain controlling.
- [What's in a build environment?](https://reproducible-builds.org/docs/perimeter/) — A reproducibility claim has a declared perimeter including tools, versions, operating-system assumptions, locale, timezone, paths, and relevant environment variables; outputs are comparable only within that stated context. **Граница:** A project guide, not a universal guarantee that two systems will be reproducible or a mandate to adopt containerization.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="DEB-12"></a>

## DEB-12 — Foundry required-manifest consumer reconciliation

Исходная запись: [tasks.json](../tasks.json), `tasks[id=DEB-12]`. Review: [root-review](root-review.md#DEB-12).

### Предпочтительное решение

Measure the full runtime-reachable consumer footprint for the flat requirements manifest before making an ownership change. Start from the canonical Foundry selection entry points and producers, trace imports/calls to the flat file, and supplement static edges with actual exercised call paths where reflection, plugin loading or runtime configuration can hide reachability. Record the universe and exclusions; a search result or sampled `rg` hit count is not a complete-set proof. If a live consumer reaches a duplicate/flat representation, appoint the existing requirements-selection owner as canonical, migrate that consumer to the canonical typed representation, then prove the legacy path has no reachable bypass before removing or retiring it. If the complete reachability trace shows no consumer, close as measured no-defect/no-live-consumer only with owner review; do not remove an artifact merely because one static path was not found.

### Что переиспользовать

- `policy-engine/src/polisyos/foundry/methods/selection/requirements.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `select_method_candidates_for_requirements / normalize_method_requirements`. Canonical typed selection requirement path and owner to compare against any flat manifest reader.
- `policy-engine/src/polisyos/foundry/methods/selection/advisor.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `method-selection consumer`. Existing downstream caller to include in reachability set; use current import/call edges only after accepted-source rebind.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Declare source roots, consumer entry points, file types, dynamic-loading mechanisms and exclusions for a complete reachability census.
2. Trace all executable consumer edges to flat manifest parsing/normalization; bind each edge to a producer and actual selection call.
3. If a duplicate is live, migrate consumer through the canonical typed owner and instrument the old path to fail/record use during transition.
4. Run the full owner set under relevant profiles and prove no consumer can bypass canonical requirements before retiring the flat representation; otherwise provide an owner-reviewed measured no-live-consumer result.

### Рассмотренные альтернативы

- **Delete flat manifest based on sampled source search** — Missed dynamic/plugin consumers could still execute and become silently ungoverned.
- **Keep two owners and copy values** — Dual sources drift and allow consumer-dependent requirement meanings.
- **Build a general static whole-language proof tool** — The scope is one owner path; combine existing architecture checks with focused runtime-path evidence and name bounded dynamic exclusions.

### Free-grow и ресурсы

- **data or config growth:** New requirement concepts enter through the typed canonical owner and its versioned schema; consumers register only supported profile dimensions.
- **extension boundary:** A new plugin/reflection path must be named in the reachability source set and conformance check; unmodeled dynamic consumers remain a declared residual.
- **resource behavior:** Cost scales with reachable module/call graph and tested profiles; keep output path-level and hash-bound, not a duplicate expanded inventory.


### Миграция и восстановление

Use expand/verify/retire: canonical typed read first, legacy read with explicit deprecation telemetry, then remove only after zero complete-set use and fresh consumer proof. Rollback re-enables a compatible adapter without changing the canonical owner.


### Композиция и owners

- A hit proves possibility; a zero from incomplete enumeration proves nothing.
- No consumer may derive distinct semantics from a parallel flat owner after migration.
- The class-level closure is all reachable consumers, not one observed call site.


### Acceptance и различающие проверки

- Every declared entry point and dynamic extension is represented in complete census with exclusions.
- A real legacy consumer is found or a complete owner-reviewed trace demonstrates no consumer.
- After migration, a deliberately reintroduced flat-manifest consumer is caught by gate or behavioral probe.
- Retirement follows verified zero reachable use and preserves rollback path.


### Входы и ответственность за их получение

- Foundry requirements owner confirmation of canonical semantic representation and complete consumer entry points.
- Owner's supported plugin/runtime profiles and any legitimate exclusions.


### Когда обоснованно отклониться

- If hidden dynamic reachability cannot be ruled out, leave the flat path in compatibility/limited status and record the exact missing discriminator.
- If canonical requirements are not yet versioned, settle its owner contract before migrating consumers.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Coverage.py configuration reference](https://coverage.readthedocs.io/en/latest/config.html) — The measured source universe is affected by configured source/include/omit selectors, and source selection changes what a coverage result says it has measured. **Граница:** Coverage.py measures execution, not PolicyOS instrument input reads; transfer only the need to disclose scope selectors, not its coverage metric or runner.
- [PROV Model Primer](https://www.w3.org/TR/prov-primer/) — PROV represents entities, activities, usage/generation, agents, and responsibility so a reader can trace artifact lineage and provenance assertions. **Граница:** A provenance vocabulary records relationships; it does not decide whether an external function belongs in PolicyOS or whether evidence has admissible authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="DEB-13"></a>

## DEB-13 — Commission numeric VOI granularity and its decision/ranking basis

Исходная запись: [tasks.json](../tasks.json), `tasks[id=DEB-13]`. Review: [root-review](root-review.md#DEB-13).

### Предпочтительное решение

Commission a native numeric VOI metric owner and decision/ranking reference before changing the 15 truthful `metric_residual_granularity_not_supported` refusals. The candidate decision-theoretic definition, if the owner ratifies it, is EVSI: expected improvement in the selected decision's utility after the proposed information, minus the current best expected utility; for net value of sampling subtract the admitted acquisition/research cost. Bind decision alternatives, utility/loss measure, uncertain state distribution, proposed observation likelihood, target population, useful horizon/discount, cost/opportunity-cost basis, metric version and assumptions. EVPI is only a perfect-information upper bound; EV(P)PI concerns selected uncertain parameters; EVSI depends on a specific study/observation design. These are not interchangeable rankings. Unknown required objective, likelihood, population or horizon means typed refusal/limited estimate; missing cost blocks net value/action claims but does not by itself invalidate an otherwise supported gross EVSI, not guessed entropy, arbitrary dollars or a confidence proxy. Keep cost admission at its canonical WDI/CAP03 owner and the SearchLedger writer as-is; UI-17 is a consumer only. Do not import health utility or a VOI number from the literature as PolicyOS authority.


### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `AcquisitionCostBasisRecord`. Existing cost evidence owner and route-specific cost record; it does not define a utility metric or admit all missing costs.
- `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `SearchLedger writer / residual granularity refusal`. Retain canonical ledger producer and its honest refusal until a decision metric contract and producer are admitted.
- `policy-engine/src/polisyos/foundry/methods/selection/advisor.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `compute_voi`. Method-selection helper is not assumed equivalent to acquisition VOI; require a semantic comparison before any reuse.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Accountable Atlas/DS15 scope owner, coordinated by the P0/root engineering lead, commissions one competent native metric/decision owner and binds its purpose, source and ranking/law decision. Acquisition planner remains refusal/cost owner and is not automatically that metric owner. If no metric producer exists, DEB-13 researches/proposes the native-owner extension and implements after the actual owner decision; do not stop as if an external institution must supply code. Unsupported metrics retain producer_missing/typed refusal until this work and genuine inputs suffice.
2. Appoint the metric/decision owner and specify target decision, utility/loss, state uncertainty, information-generating design and ranking direction before coding.
3. Choose whether the metric is EVPI, EVPPI, EVSI or net benefit of sampling; write its exact estimand and versioned input law with population/horizon/time basis.
4. Bind cost as a separate admitted input from the WDI/CAP03 owner, including variable, fixed and opportunity costs where the decision requires them.
5. Implement producer that emits reproducible metric artifact with all assumptions, uncertainty/calibration and provenance; persist it and have DS15 consumer recompute/verify identity and use it for ranking.
6. Keep all 15 rows in explicit residual-refusal state when required inputs are missing; show named missing dimensions in consumer output.
7. Default computation profile: finite selected decision alternatives and discrete state/observation law, evaluating EVSI = E_y[max_a E[U(a,theta)|y]] - max_a E[U(a,theta)] by exact finite sums with a small independent oracle. Preserve utility units, numerical tolerance, ties and uncertainty. Subtract separately admitted cost only for a dimensionally compatible net estimand. For continuous/large problems, extend the existing method with quadrature or nested Monte Carlo only when necessary; report approximation error/convergence and avoid optimizer/Monte-Carlo bias masquerading as real decision improvement. Selected finite alternatives are task inputs, not a central capability allowlist.


### Рассмотренные альтернативы

- **Use entropy reduction or confidence improvement as numeric VOI** — Information has value only through its effect on a decision's payoff; uncertainty reduction alone need not change the decision.
- **Treat cost-basis money as VOI** — Acquisition cost is a distinct input, and cost without expected payoff improvement does not establish net value.
- **Reuse method-selection compute_voi by name** — Shared naming is not semantic equivalence of action space, utility, estimand or evidence boundary.


### Free-grow и ресурсы

- **data or config growth:** New decision families supply typed utility, observation models and population/horizon inputs through the metric owner; supported versions evolve explicitly.
- **extension boundary:** A genuinely new utility or ranking semantics needs owner decision and reference cases; no arbitrary plugin formula becomes authority.
- **resource behavior:** Simulation/integration cost is driven by state/action/observation dimensions and horizon; choose bounded approximation only with reported method/error and owner acceptance, never invent performance or precision.


### Миграция и восстановление

Add metric as a separate versioned artifact alongside current refusal. Promote only after producer, persistence, bridge, DS15 consumer, independent recomputation and surface are wired. On invalid/stale inputs revert consumer to explicit refusal while preserving artifact history and source cost rows.


### Композиция и owners

- VOI metric does not create acquisition authority; it supports a separately authorized ranking purpose.
- Cost and expected benefit remain separate, source-bound inputs with distinct owners.
- Missing or uncalibrated inputs yield typed refusal/limited value, not a number; a ranking requires a declared decision and population/time horizon.
- Actual UI-17 numeric projection consumes the persisted metric/decision basis. CAP-03 delivers the actual native-owner cost artifact for net/cost-dependent use of that route; DEB-07 retains the source-row reconciliation; gross supported EVSI may remain with explicit cost limitation. Other selected routes bind their actual admitted cost owner, not a WDI default.


### Acceptance и различающие проверки

- A small known decision case yields the owner-specified EVSI/ENBS ranking under recomputation and changes when decision utility or likelihood changes.
- Missing utility, observation model, population or horizon yields `metric_residual_granularity_not_supported` or the owner-approved typed limitation.
- All 15 rows stop refusing only when real owner-admitted metric inputs/artifacts are present; fixture-only numbers do not close production debt.
- UI-17 projects verified metric and limitations; it does not write metric or confer authority.
- A supported gross EVSI survives absent cost with an explicit cost limitation; ENBS/net ranking and any cost-dependent action remain unavailable. Zero-information and irrelevant-observation cases yield zero within the declared numerical tolerance; a refutation of utility/likelihood binding breaks the real ranking consumer.
- Each of the 15 refusal rows is reconciled against its own supported target/basis; a valid subset may emit bounded values while unsupported rows retain exact refusal. No all-or-nothing release and no unrelated input gates a gross candidate estimate.


### Входы и ответственность за их получение

- Metric owner appointment and approved objective/utility or loss function, action set and ranking semantics.
- Owner-admitted or explicitly hypothetical candidate uncertainty/likelihood model, target population and horizon/discount. Actual acquisition cost is required only for net-value/cost-sensitive ranking or action, not for an otherwise supported gross EVSI.
- Independent validation reference case and policy about when a numeric ranking is admissible.


### Когда обоснованно отклониться

- If no decision owner/utility exists, retain the refusal and commission the decision design; do not implement a placeholder metric.
- If accepted source shows existing compute_voi is semantically identical, reuse with an explicit owner mapping and conformance case rather than duplicate producer.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [Value of Information Analytical Methods: ISPOR VOI Analysis Emerging Good Practices Task Force, Report 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC7373630/) — VOI compares expected decision-payoff improvement from information with acquisition/research cost; EVPI, EVPPI, EVSI and ENBS answer distinct questions, and population value depends on beneficiary population and useful horizon. **Граница:** Health-technology-assessment application. Transfer the explicit decision model, assumptions, population, horizon, and cost separation; do not import its utility or monetary units into PolicyOS without an owner decision.
- [ICH E9(R1) estimands and sensitivity analysis guideline](https://database.ich.org/sites/default/files/E9-R1_Step4_Guideline_2019_1203.pdf) — A decision estimand needs explicit population, variable, intercurrent-event strategy, and population-level summary; comparability depends on the question and setting. **Граница:** Clinical-trial-specific guidance; it is an example of fully specified estimands, not a universal PolicyOS metric contract.
- [Policy design causal operating system north star](../../../../../../policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — PolicyOS is an epistemic custodian: it consumes others' signatures as typed evidence, signs only claims it can custody, and must keep published justification honest across time and world change. **Граница:** Product identity guidance; it does not appoint external institutions or define an unratified numeric metric.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="DEB-14"></a>

## DEB-14 — Wire purpose-scoped scope ruling into claim lifecycle and surface

Исходная запись: [tasks.json](../tasks.json), `tasks[id=DEB-14]`. Review: [root-review](root-review.md#DEB-14).

### Предпочтительное решение

Extend the existing `ScopeAdjudicationCandidate` only through an explicit purpose-scoped ruling producer, persistence/bridge and lifecycle consumer; the current candidate's `authority_effect=none` and `closure_effect=none` remain truthful until the full chain is admitted. Use the ratified one-plane-at-a-time four-way rule: own if absence makes our published claim false; integrate if an external output changes our claim validity (own the typed fail-closed evidence contract, not the external function); observe if it changes only who answers for our claim; otherwise out_of_scope. Bind each factual predicate to content, source, valid/known time and rule version. Classify the gate's own basis under P37 (`recomputed`, `independently_reconciled`, `consumer_asserted`, `institutionally_supplied`, `not_established`) at admission and fail authority-band gates closed on the last three. Candidate-band unknown may remain a declared assumption/limitation. LIF-02 owns common claim-head/lifecycle writes; UI-19 owns the governed projection. W3C PROV can help describe lineage but cannot decide the scope ruling; the local ratified SDD is the decision source.

### Что переиспользовать

- `policy-engine/src/polisyos/core/contracts/scope_adjudication.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `ScopeAdjudicationCandidate / ScopePredicateObservation`. Existing candidate already binds subject/rule evidence, rule version/times and one plane; it explicitly has no authority or closure effect.
- `policy-engine/src/polisyos/scientist/evidence/claims/head_index.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `canonical claim head index`. LIF-02 shared canonical head/lifecycle owner for claim binding, staleness and reissue.
- `policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `four-way adjudication and custody rules`. Ratified predicate order and ownership meanings; any producer must ground factual observations in source evidence.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rebind candidate schema, builder, candidate tests, evidence store and current downstream claim heads after E02 acceptance; identify the actual LIF-02 writer and UI-19 consumer interfaces.
2. Add the smallest purpose-scoped ruling producer that resolves a single plane, binds subject/rule/source evidence and freezes predicate basis/time/version; do not treat candidate construction as admission.
3. Persist the admitted ruling through the canonical lifecycle/head writer, trigger limitation/reissue/invalidation when the source predicate or rule epoch changes, and project audience-safe status through UI-19.
4. Prove all four branches, mixed outcomes and unknown behavior; use P37 falsification and P38 property-vs-proxy comparison for each promotion gate.
5. Keep genuinely external function/evidence owner outside PolicyOS unless four-way test says missing it makes our signed claim false; otherwise integrate its typed evidence or observe it.

### Рассмотренные альтернативы

- **Promote the candidate by changing its status field** — A candidate has no resolver, persistence bridge, claim lifecycle or governed surface; status flip would be authority by adjacency (P05/P15).
- **Build a general scope interpretation engine** — The ratified grammar is a small one-plane rule; an engine would add governance gravity and duplicate rule ownership.
- **Use PROV or a generic provenance label as the adjudicator** — Provenance represents lineage/responsibility but does not decide PolicyOS custody scope or establish a gate predicate.

### Free-grow и ресурсы

- **data or config growth:** New policy cases add source-bound observations and rule-versioned purpose profiles through the existing predicate grammar.
- **extension boundary:** A genuinely new predicate/plane requires ratified rule evolution and conformance; arbitrary LLM-generated interpretations remain candidates.
- **resource behavior:** One adjudication evaluates the fixed one-plane predicate set and bound evidence; large evidence remains referenced, and incomplete/ambiguous inputs return typed limitations.


### Миграция и восстановление

Preserve candidate schema and historical artifacts. Introduce an admitted ruling as a versioned downstream type with references; old candidates never gain retrospective authority. If a ruling or source becomes stale, LIF-02 marks affected claim limited/reissue-required and UI-19 shows the current status while retaining prior history.


### Композиция и owners

- Candidate is never authority; admitted ruling requires source resolution, content bind, verifier provenance, rule/time binding and lifecycle effect.
- One adjudication contains one plane; decompose rows spanning institutional act, evidence, admission, claim reaction and projection before evaluation.
- Gate predicate basis is classified at admission; `consumer_asserted`, `institutionally_supplied` and `not_established` do not carry authority-band green.
- Unknown scope is an explicit candidate limitation, never silently coerced to a concrete ruling.


### Acceptance и различающие проверки

- Removing actual source evidence while retaining field names/markers prevents authority admission.
- Four single-plane probes produce own/integrate/observe/out_of_scope from the ratified predicates; conflicting/mixed rows are decomposed.
- Changing rule version or effective time invalidates/reissues dependent claims through LIF-02 and UI-19 reflects it.
- Candidate construction remains non-authoritative; no external appointment is demanded for the internal ratified rule itself.


### Входы и ответственность за их получение

- Source institution's actual signed act/evidence when the case tests an external function; purpose/scope/validity and verifier profile are supplied by that institution.
- Architecture owner confirms the already-ratified rule/source version; no new authority appointment is inferred from its existence.


### Когда обоснованно отклониться

- If rebind finds a persistence bridge or lifecycle consumer already landed, classify that capability by evidence and close only the truly missing edge.
- If a new scope predicate would alter custody semantics, present it as a decision proposal and preserve candidate behavior until ratified.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PolicyOS identity and custody boundary](../../../../../../policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — The four-way scope test is own when absence makes our published claim false; integrate when external output changes our claim validity; observe when only answerability changes; otherwise out_of_scope. Candidate-band unknowns may be carried as declared limitations; authority-band claims fail closed when required scope is unknown. **Граница:** This is the ratified PolicyOS rule, not a substitute for content-bound evidence establishing the factual predicate in an individual case.
- [Policy design causal operating system north star](../../../../../../policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — PolicyOS is an epistemic custodian: it consumes others' signatures as typed evidence, signs only claims it can custody, and must keep published justification honest across time and world change. **Граница:** Product identity guidance; it does not appoint external institutions or define an unratified numeric metric.
- [PROV Model Primer](https://www.w3.org/TR/prov-primer/) — PROV represents entities, activities, usage/generation, agents, and responsibility so a reader can trace artifact lineage and provenance assertions. **Граница:** A provenance vocabulary records relationships; it does not decide whether an external function belongs in PolicyOS or whether evidence has admissible authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.
