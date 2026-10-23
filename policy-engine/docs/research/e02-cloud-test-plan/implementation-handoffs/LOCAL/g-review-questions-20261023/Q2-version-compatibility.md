# IR-Q2 — Version policy and historical compatibility

**NEW architecture question; coupled to IR-Q1.** Choose the version-admission/migration mechanism. The actual supported versions are producer-owner inputs, not facts for G to invent.

## Source counterexamples

At entry HEAD `5b5871c4e5e1f682a7526e2c5c3b97d0b043ce75`, `MobilityReport.schema_version` is a string matching `^\d+\.\d+$`, default `2.0` (`analytics/mobility.py`). `persist_mobility_report` accepts name/version overrides and writes `schema_version or report.schema_version`. Its HEAD typed ref declares kind/media only. The unpublished RAW admission candidate adds `ir.mobility_report` with versions `1.0` and `2.0`. A valid patterned `2.1` is therefore a **static divergence between current writer acceptance and the proposed reader**, not proof that 2.1 is scientifically or historically supported. Neither the historical reader's closed set nor support for 1.0/2.0 is established by that candidate tuple.

`CausalDiscoveryReport.schema_version` is an unconstrained string default `1.1` (`analytics/causal_discovery.py`). Its writer requires an override to equal the payload version, but no finite supported set is declared. Both HEAD and the cited RAW typed ref lack a closed owner-version contract. A payload/writer equality check is insufficient to decide compatibility or substantive supported semantics.

The [CSV](remaining-93-callsite-census.csv) binds exact caller/producer bytes and separates HEAD, local dirty and RAW views. These are source counterexamples; question-specific runtime probes have not run.

## Recommended policy and alternatives

Recommend explicit, versioned owner admission with reader-first rollout and exact retained historical aliases/migrations; never turn a default or regex into a historical allowlist. Owner input must establish which versions and payload semantics are supported. If extensibility is intentional, a concrete version/extension resolver must bind it to an owner validator. A generic dotted string alone cannot establish authority-grade compatibility.

| Option | Benefit | Cost / unresolved input |
|---|---|---|
| Versioned finite owner set (recommended where owner law is finite) | Deterministic write/read agreement, fail-closed unknown versions | Requires supported/historical owner facts; narrows current open writer behavior |
| Explicit extensible owner resolver | Keeps legitimate future/third-party extensions | Needs defined namespace, owner validator and migration law; cannot simply accept any string |
| Keep current open versions and avoid new reader claims | Avoids an immediate compatibility break | Leaves schema-owner verification incomplete; bounded candidate use only where declared unknown is allowed |
| New registry/service | Central lifecycle orchestration | Not justified for these rows alone; reuse existing typed refs and migration registry first |

Do not silently preserve a RAW `1.0/2.0` list as if it were established history. When owner facts are unavailable, retain exact current behavior only within its declared capability/authority boundary, record the gap, and postpone authority promotion. Do not rewrite stored manifests, infer currentness from schema version or drop unknown fields while claiming successful migration.

## Migration and mandatory companions

Coordinate typed ref owner metadata, producer/DTO validation, existing schema migration registry, loaders/persistors, ABI/schema/catalog snapshots, public facades, importer consumers and their tests. New writer versions enable last, after readers accept the explicitly retained predecessors. Old readers reject unsupported new versions visibly. A retained override signature does not remove the behavioral breaking-change obligation.

Current/historical supported versions, alias meaning and actual stored artifacts are external owner inputs. G chooses policy, owner location, compatibility window/retirement predicate and rollout; G does not choose scientific validity from a version number. Time/currentness, selected profile and provenance remain independently checked. Existing G AD05 canonical byte mechanics and strict separate Core/IR law remain unchanged.

## Minimal deciding prototype/falsifiers — UNRUN

For Mobility, construct a valid patterned 2.1 DTO, persist through the real producer and fresh-read through the candidate owner contract. The chosen policy must yield either supported owner-validated round-trip or writer-side typed refusal, never successful persistence followed by unexplained reader rejection. Preserve controls for each **owner-established** predecessor; 1.0 and 2.0 are proposed controls requiring that qualification.

For Causal Discovery, exercise each owner-established version and an unknown well-formed version, including equal payload/override and mismatched payload/override. Prove refusal precedes payload reads where manifest identity is unsupported. Run real migration/round-trip fixtures for every retained predecessor; unknown fields/versions must not disappear. Remove the version admission while retaining labels and the negative test must fail. All these question-specific runtime probes are **UNRUN**.

**Requested G output:** finite versus explicit extensible policy; authoritative owner/migration location; reader-first/retirement rule; treatment of unresolved historical facts; exact acceptance signal. Root will reconcile supported version inputs and implement the selected rule without claiming owner facts that are absent.
