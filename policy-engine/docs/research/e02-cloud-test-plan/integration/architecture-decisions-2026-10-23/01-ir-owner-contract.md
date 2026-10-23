# IR-Q1 — one owner law for writing and reading

Status: G architecture selection for implementation. Question source: `f12fb9895a4009ce77828554f4c5c18d83e6ec15`, `implementation-handoffs/LOCAL/g-review-questions-20261023/Q1-override-owner-contract.md`. This is neither source acceptance nor finding adjudication. All implementation tests below are UNRUN.

## Decision

**Extend the existing IR artifact boundary and migration registry with one immutable owner-contract resolution, used by both producers and typed consumers.** Keep governed schema declarations extensible by registration; do not freeze the universe to today's defaults or add a schema-governance service. A producer's public `schema_name` / `schema_version` arguments select an explicitly supported representation; they do not grant permission to invent that representation.

The invariant is scoped: every successful owner-admitted write is readable by a fresh compatible reader of the same owner-policy snapshot, codec profile and declared representation. It does not promise every old binary can read every new version, nor that schema conformance establishes scientific, legal or institutional authority.

Reject an allowlist reverse-engineered from defaults; accepting arbitrary override strings; a caller-controlled owner object; an independent central registry that repeats the migration registry; and changing CAS/hash/Core-versus-IR rules to mask owner mismatches. AD05 remains binding.

## Canonical ownership and resolution

Use `ir/artifacts/contracts.py` for the small immutable descriptor/resolved-admission types, `ir/registry/refs.py` for nonserialized typed-ref declarations, `ir/migrations/base.py` and `schema_registry.py` for registration and compatibility, and `ir/artifacts/io.py` for the shared mechanics. Artifact DTO owners supply payload validators and semantic migration rules. Do not import upper layers into IR.

The descriptor has the following logical content (Python symbol names can follow existing conventions; these are not new fields on historical manifests):

| Component | Required meaning |
|---|---|
| Owner key and policy revision | Stable artifact-family owner; immutable revision/fingerprint of the selected declaration and validator implementation. Distinct from payload version and model `contract_id` |
| Kind/media constraints | Exact family identity and supported media representations; JSON shape cannot select a family |
| Representation entries | Exact schema-name/version pairs; aliases refer to one explicit entry, not wildcard names; each entry names payload validator and profile policy |
| Read/write capabilities | Current emission targets, historical read-only entries, explicit migrations and retirements; generated from the same registry records |
| Contract-to-registry mapping | Explicit relation between stable DTO contract ID, artifact kind/schema name and existing ABI/migration key; no prefix stripping or `.v1` suffix inference |
| Policy snapshot | Fixed for one operation/replay; resolves conflicts deterministically; no mutable registration halfway through an admission |

**Trusted expected owner comes from the consumer's code contract**, before opening the supplied artifact. A loader binds its owned descriptor and validates the entire selector. A serialized mapping or scalar ID does not retain a Python `ClassVar`; the loader re-establishes that expectation. A ref subclass, a matching class name, manifest label, requested override, arbitrary mapping field, or artifact-supplied import path cannot choose the policy.

Retain `get_json_artifact`'s public callable signature. An owner-bound internal admission routine/context can be shared by typed loaders, with the existing helper retaining its documented generic byte/profile role. The generic helper is not typed-owner admission; owner-sensitive loaders must not fall back to it after an unknown owner or failed check. Both public byte-returning and value-returning typed routes use the same admission. Generic tooling may inspect lawfully accessible unknown bytes as opaque/untyped candidate material and report the unresolved contract; it cannot project them as a typed policy input.

`ClassVar` metadata remains outside wire fields. Introspection repair must recognize the exact owner-declared nonserialized metadata without allowing arbitrary fields to disappear from selector validation. Typed refs round-trip with the same field set and canonical bytes. Dynamic Welfare roles or other selectors resolve a consumer-owned role-to-contract binding before I/O; a six-role dictionary is not six established producer contracts.

## Shared algorithm and refusal ordering

**Write:** resolve the requested exact representation against the frozen owner snapshot → validate payload/declared version relation under that representation → encode with the existing IR policy → persist once through CAS and return the actual selected profile. Unsupported/malformed overrides and incompatible payload identity fail before `put_json` or any externally visible artifact publication. A probe must count actual store mutation calls, not only inspect exception text.

Preserve the difference between omitted argument, the explicitly documented `None` sentinel (where already supported), empty string, malformed string and unknown well-formed identity. Replace truthiness defaulting such as `schema_version or report.schema_version`: `""` is not omission. A `None` sentinel in the Python API never authorizes an explicit-null schema in a persisted manifest.

**Read:** trusted expected owner → strict selected raw manifest and view identity → owner kind/media/schema/version eligibility → canonical profile eligibility → payload bytes/hash/conformance → source-version payload validator → explicit read projection/migration if selected → consumer-purpose admission. Manifest/profile errors reject before payload bytes. Payload/schema disagreement necessarily requires reading payload; do not promise zero payload reads for that class. Byte integrity, schema conformance, provenance and authority remain separate predicates.

Resolve raw and typed manifest association consistently with AD05, retaining the selected profile through all adapters and lineage. No fallback to another manifest, decoder, schema, alias or version after refusal. Where a store cannot establish the selected view, report the existing typed limitation. Unsupported resource limits are resource refusals, not proof of malformed science.

Reuse existing typed refusal families and stable reason codes; add a reason only for a distinguishable property, such as unsupported owner representation, unregistered contract, payload-version disagreement, ambiguous compatibility or retired writer target. Do not introduce a parallel status lattice. Consumers retain existing `blocked`/`limited` handling according to purpose.

## Extensibility without arbitrary authority

An extension registers an owner-controlled descriptor, implementation/validator reference, exact supported identity, compatibility rules and conformance evidence through the existing trusted code/configuration admission boundary. Purely declarative additions supported by existing validators require no core code change. A genuinely new decoder or semantic law requires its own reviewed adapter; free growth does not mean executing code supplied in an artifact. Namespace conflicts and changed meaning under an existing identity refuse registration. Identical re-registration is idempotent; differing records cannot silently replace one another.

Artifact discovery can find new methods/data without modifying this mechanism. Finite schema versions describe a wire grammar, not a list of allowed domains, methods or policy concepts. This is compatible with constitution Rule 12, which explicitly distinguishes governed schemas from capability-gating enumerations.

There are two independent changes: **a new resource using an existing grammar/adapter** enters the existing corpus/index and discovery path without another owner descriptor or per-resource registry approval; **a new representation/semantic law** extends a governed descriptor and its validator/compatibility evidence. Do not register every dataset, method instance or jurisdiction in the IR schema registry. Bind runtime lookup to the existing admitted adapter's contract and actual resource selection. Discovery recall/freshness and capability completeness still require their own evidence; a successful registration alone proves neither.

## Migration and scope

Follow IR-Q2's reader-first stages. Preserve the callable override keywords where useful, document narrowed acceptance as a behavioral break, release-note it and migrate known callers. Do not advertise support for a previously arbitrary value merely because a function accepted it. Previously emitted unknown artifacts remain preserved and inspectable; their admission is unresolved until an exact decoder/contract is established.

Current built-in declarations can be established from producer, DTO, validator, declared tests and explicit owner choice by the implementation team. This does not require waiting for an external organization. Real historical use, alias intent and stored-object provenance may require genuine evidence. Split those tasks rather than holding every reader behind a universal historical inventory.

The supplied census has 93 residual callsite rows, with mixed committed/dirty/RAW source qualification. Use the companion disposition to route every row; reconcile again at the implementation freeze. The mechanism applies beyond that seed set wherever the same typed artifact boundary is used. No claim of repository-wide closure follows from closing only the seed rows.

## Acceptance and attacks

1. Actual current and each explicitly retained predecessor producer → CAS → fresh typed loader → downstream consumer succeeds with the selected identity. A registered nondefault representation also succeeds; an unregistered plausible override refuses before persistence.
2. Same valid JSON bytes with wrong kind, media, name, version, selected profile, or conflicting raw/typed metadata refuse before payload fetch where decidable from metadata. A valid manifest with incompatible payload version refuses after decode and before consumer use.
3. Serialize a typed ref to a mapping; use a scalar selector; use a fabricated ref subclass; use a sibling generic selector. Trusted loader expectation survives; none can supply or bypass owner authority.
4. Remove shared writer or reader admission while retaining descriptor fields: the behavioral discriminator fails. Exercise both value-only and bytes-returning typed readers and downstream transformations. Include the concrete `ir/analytics/phase4_dynamics.py` ABM reader that currently calls generic `get_json_artifact` and then `ABMResult.model_validate`: another family with ABM-shaped bytes must not pass. Updating a shared helper while leaving a reachable typed caller on generic I/O is not completion.
5. Register a supported new representation through the existing owner mechanism without editing central dispatch. Separately add two distinct new resource records under an already admitted grammar/adapter: existing discovery and execution consume them with no descriptor, family-list, dispatcher or per-resource approval edits. Check the selected index revision and known-groundable recall/freshness; a no-hit is not proof of resource absence. An artifact-controlled resolver, duplicate namespace with changed law, and unresolved contract remain rejected. This tests extensibility as well as refusal.
6. Preserve original bytes/IDs for unchanged writes, exception identities, selected profiles, Core/IR policy separation, public facades, schema catalogs, ABI and installed consumer routes. Actual historical compatibility claims need source-qualified fixtures; synthetic conformance fixtures establish only mechanism behavior.

Pattern pass: P01/P02/P07/P10/P27/P29/P31/P32/P35/P37/P38/P40. Existing gaps include owner declaration/bridge and semantic verification. This selection supplies the design, not a working capability. The decisive property is owner-consistent interpretation; the divergent proxy is matching default schema strings while a legal nondefault writer output is unreadable.
