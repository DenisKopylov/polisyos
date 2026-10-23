# IR-Q2 — explicit compatibility, immutable history, reader-first rollout

Status: G architecture selection; no source acceptance or closure. Read with [IR-Q1](01-ir-owner-contract.md). Question and static source pins are recorded in the packet receipt. All proposed runtime checks are UNRUN.

## Selection

Use **explicit registered representations and directional compatibility for typed artifact admission**. Built-in contracts have a finite known set per immutable policy snapshot; an owner may add an exact registered extension. Do not infer typed admission from version equality, numerical order, a dotted-string regex, common major number, default value, payload/manifest agreement, or availability of a parser. A typed schema can parse scientifically unsupported content.

At `f12fb9895…`, `ir/migrations/base.py::negotiate_schema_version` returns `can_read=True` for equal strings before registry lookup. It also permits replacement of a registry entry through `register_schema_version`; `register_migration` registers both endpoints again. An owner-bound admission must refuse an unknown equal version; conflicting registrations cannot erase its established rules. Within that admission a same-version fast path is valid only after both sides resolve to the same admitted representation and policy snapshot.

**ADR-0107 compatibility boundary:** the existing public `negotiate_schema_version` / `can_read_schema` surface is a release-review/migration-planning API; its `FULL` mode promises same-major readability unless narrowed. Do not silently redefine that API globally. Register an explicit narrower **owner-admission profile** for affected typed artifact families, evaluated by the same registry/resolution owner before its compatibility result is used. Legacy planning `can_read=True` is not typed admission and cannot bypass that profile. Keep existing advisory behavior for unrelated contracts until their own reviewed migration. This is a distinction of purpose over one registry, not two competing supported-version catalogs. A typed consumer cannot request the weaker planning mode.

Mandatory registry-client reconciliation includes `ir/analytics/evidence_bundle.py::_causal_evidence_bundle_version`, which calls negotiation at the question commit, and `ir/migrations/policy_ir.py`, which registers `policy_ir@1.0` as FULL. Preserve their declared planning contract while wiring any typed intake through its owned narrower profile. Registry conflict handling must consolidate legitimate built-in initialization once, not turn current repeat/import order into an unexplained startup failure. Release-note each changed public behavior explicitly.

In particular, `_causal_evidence_bundle_version` and `load_causal_evidence_bundle` must consume the strict owner admission from the same selected manifest; leaving their current `negotiate_schema_version` → generic `get_json_artifact` sequence as the authority path is forbidden. Reuse the negotiation internals where suitable, but a legacy planning answer cannot be converted into an admitted artifact by `model_validate`. The public advisory API may retain its behavior; this concrete typed route must change.

Reject a new registry service, wildcard future-version acceptance, automatic conversion to `latest`, and a blanket grandfathering of every value an old Python function happened to accept. Exact old behavior may be retained as a clearly named candidate inspection route; it is not the new typed admission route.

## Compatibility record

An entry binds artifact family, schema-name/version, stable contract/ABI key, payload version relation, selected decoder/profile policy, validator revision and lifecycle. The existing registry is the single compatibility source. Typed-ref metadata points to that source; it does not maintain an independent readable-version tuple. Common compatibility laws may be shared functions over the explicitly registered source/target entries; the generated evidence matrix is a view of those laws, not a requirement to hand-maintain every pair. Register validators/semantic deltas once and reuse existing normalization primitives. A rule may cover a reviewed family of known representations, but cannot admit an unregistered future version merely because it matches a range. This avoids quadratic policy boilerplate without guessing semantics.

Model three different operations explicitly:

| Operation | Meaning | Required evidence |
|---|---|---|
| Direct read | Reader interprets original representation under its source semantics | Source validator and owner-declared directional compatibility; no mutation of original representation |
| In-memory projection | Consumer gets a specified current view while original identity/version remains available | Exact transform/revision, preservation/loss contract, source and target validation; projection is not a new historical fact |
| Persisted migration | New artifact/view derived from original | New identity/profile and lineage; source/target versions, transform revision, actual execution time and loss disposition; original remains immutable |

Do not return an object claiming its predecessor was natively produced in the target version. Keep original representation identity in the existing admission/execution context and resulting lineage; do not add metadata to historical CAS manifests. If a legacy API returns only a DTO, its caller must obtain the retained source context through the same owned read operation before using it for an authority-bearing derivative.

A manifest version and an embedded payload version are related by an explicit **representation tuple**. For new aligned writers they must agree where the schema defines them as one version. Known historical split versions require a narrowly specified tuple and source payload parser; rejecting every mismatch would strand currently written transport artifacts, while accepting all mismatches would destroy identity. No implicit Cartesian product of allowed manifest and payload versions.

Aliases mean an explicit owner-defined equivalence, never approximate naming. Conflicting source fields refuse; migration cannot silently prefer one of `formula` and `transport_formula` when both are supplied with different values. Unknown fields are not dropped to obtain compatibility. If an intentional semantic reduction is needed, emit a separately identified limited projection with retained source and declared loss; it is not a successful lossless migration.

Migration paths are deterministic and pinned. An explicit supported direct edge is preferred; a composed path needs declared composition semantics, source/intermediate/target validation and a stable path identity. Cycles, ambiguous equal-priority paths, repeated conflicting registrations and version drift during the operation refuse. Do not use import order to select a law. Registry initialization may stay within the existing owner; no module-purity rewrite is implied.

## Mobility and Causal Discovery

`MobilityReport` currently defaults to `2.0` but accepts a patterned string; `persist_mobility_report` accepts overrides and uses truthiness to select a version. `CausalDiscoveryReport` defaults to `1.1` with an open string; its writer checks override/payload equality. Those observations establish an open API, not a supported historical set.

The implementer is authorized to define the **current** supported representation from the actual DTO/producer/parser semantics and register it with the required discriminators. Default `2.0` / `1.1` are candidate current identities to reconcile, not sufficient proof alone. An existing historical `1.0` Mobility reader may be retained only after its concrete source schema/normalizer and meaning are established. Do not adopt the RAW candidate's `1.0/2.0` tuple as history.

For a valid patterned Mobility `2.1` or equal unknown Causal Discovery version, the selected behavior is: use an already registered exact extension if present; otherwise refuse the typed write before persistence. A person does not need to approve each invocation. Registering a new scientifically meaningful law is a separate owner responsibility, not runtime string negotiation.

Historical object retrieval and archival preservation can continue without making typed meaning claims. Candidate computation still requires an established decoder for the requested representation; an unknown legal or scientific premise is not the same as unknown wire semantics.

## Rollout, retirement and rollback

1. **Reconcile** current writers/readers and active caller contracts; pin their exact source. Split known current representations, demonstrated historical tuples and unresolved history. Do not scan production broadly or wait for all unknown archives before repairing known families.
2. **Readers first:** deploy explicit source validators and needed migration/projection rules for the selected cohort; exercise all actual public/installed consumers. Readers can accept known old forms while writers still emit them. Unknowns remain visible.
3. **Enable current writers:** each producer resolves through the same owner snapshot and emits only a compatible target. Do not enable a new persisted representation until all in-scope consumers that must read it support it, or an explicit route negotiates a proven old representation without semantic loss. Unrelated owners proceed independently.
4. **Retire old writes:** release-note narrowed overrides and update actual callers. Retirement requires declared support policy, deployed consumer capability and completed named caller migration. No arbitrary time window, no requirement to prove every possible external caller absent. Externally stable APIs get their normal release/deprecation boundary.
5. **Retain required historical reads:** retiring writes is not deleting archived readers. Preserve exact replay of standing claims/cases for their custody/retention obligations. A security or legal revocation may block live use without erasing the historical record.
6. **Rollback:** roll back writer enablement first. Old strict readers refuse new objects visibly; do not silently strip fields or mutate them into old forms. Keep capable readers/isolated compatibility access for already published new objects. Resume only with an explicit version route.

Runtime policy snapshots are immutable. Cache typed admission by selected artifact/profile association, owner-policy/validator revision, purpose and relevant governance/access epoch; byte-only or schema-version-only cache keys are insufficient. Revocation/currentness changes invalidate protected-use decisions, not mathematical history. Bound caches and reject stale policy snapshots for new protected use while keeping pinned historical replay separate.

## Acceptance signals

- Every registered current/predecessor tuple has a real writer or source-qualified historical fixture → CAS → fresh reader → real consumer test. Unknown equal versions refuse; so do wrong payload/manifest pairs, ambiguous aliases and conflicting registry definitions.
- Compare old-reader/new-writer, new-reader/old-writer, rollback after new object publication, both facade routes and installed consumers. Strict-old rejection is an expected compatibility result, not green consumption.
- Remove registry admission but retain equal strings: the negative must fail. Remove migration and keep target labels: the predecessor positive must fail. Preserve source refs and original bytes through valid migrations; a dropped field or fabricated time must fail.
- Test concurrent registration/read snapshots, repeated idempotent initialization, invalid migration path and cache priming from a different owner or policy epoch. No exhaustive world-history inventory is required to test these generic mechanisms.

Pattern pass: P04/P05/P07/P08/P27/P29/P31/P32/P37/P38/P40/P41. Schema compatibility, origin, scientific validity and current legal eligibility remain independent. Missing real historical evidence limits that historical compatibility claim; it is not permission to stop current owner engineering.
