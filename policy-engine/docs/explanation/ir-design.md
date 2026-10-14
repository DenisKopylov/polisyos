# IR Design

Related reference:

- [IR index](../reference/ir/index.md)
- [IR schema catalog](../reference/ir/schema-catalog.md)
- [IR public surface](../reference/ir/public-surface.md)
- Generated [shared schema reference](../reference/schemas.md)

Related architecture:

- [Causal operating-system north star](../system-design-decisions/policy-design-causal-operating-system-north-star.md)
- [Universal policy-design target](../system-design-decisions/universal-policy-design-target-architecture-and-gap.md)
- [Identity and custody boundary](../system-design-decisions/policyos-identity-and-custody-boundary.md)
- [Stage-0 custody ratification](../system-design-decisions/stage0-custody-kernel-ratification.md)

- Owner: `@ir-owners`
- Source of truth: `src/polisyos/ir/`, `src/polisyos/core/`,
  `src/polisyos/common/`, generated schema and public-surface references, and
  the tests listed below.
- Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
- Evidence level: source and test inspection at the pin; tests were not rerun for this documentation update.

---

IR defines shared, versioned contracts for policy inputs, model assumptions,
observations, analytics, and artifact references, so producers and consumers
can exchange those shapes across package boundaries. This page maps the
inspected package boundaries and selected Trinity parse, validation, and linking
path at the source pin above. A valid or linked object is still a contract
input: it does not execute a policy, establish substantive evidence, or grant
authority, and this page does not claim that E02 or PolicyOS is complete end to
end. The listed tests were inspected but not rerun for this documentation
update. Start with the [IR index](../reference/ir/index.md) and
[schema catalog](../reference/ir/schema-catalog.md) for contract details, then
use the package READMEs for owners and source entrypoints.

## Present package boundaries

| Package | Current responsibility | Boundary |
| --- | --- | --- |
| `polisyos.common` | Bootstrap-safe shared helpers, serialization, timestamps, logging, and async utilities. | Shared mechanics, without policy-domain ownership. Its root facade exports helper modules. |
| `polisyos.ir` | Policy, observation, analytics, world, schema, migration, and typed-reference contracts. | Declares and checks payload structure and selected local invariants; it does not execute interventions or grant claim authority. |
| `polisyos.core` | Cross-layer contracts, artifact/CAS infrastructure, component discovery, registries, security, and observability. | Stores and connects artifacts and services; a typed reference or manifest field still requires the relevant consumer-side admission checks. |

The package facades are lazy import boundaries. Use their `__all__` exports and
the generated [public-surface reference](../reference/public-surface.md) to
identify supported names; a file's presence under `src/` does not make it a
stable package-level API. The IR root is the broad compatibility facade, while
`polisyos.ir.analytics`, `polisyos.ir.kernel`, and `polisyos.ir.world` expose
their declared subpackage surfaces. Core exposes selected subpackages and
contract exports. Common's root exposes its helper modules.

The package roles do not imply one global import direction. Common provides
shared mechanics; IR owns most policy-facing contracts but selected modules
also consume Core artifact protocols; Core consumes IR contracts in registries,
compiler reports, and cross-layer DTOs. The allowed module-level edges are
owned by `architecture/imports/policy.toml`.

## From payload to linked contract

The current Trinity path has distinct checks at each boundary. In this path,
`TrinityBundle` means the nested payload type
`polisyos.ir.trinity.TrinityBundle`. The same-named
`polisyos.core.contracts.trinity.TrinityBundle` is a separate DTO containing
typed artifact references, not that nested payload.

1. `polisyos.ir.trinity.loaders.load_trinity_bundle()` parses a mapping, JSON,
   YAML, or UTF-8 bytes and requires exact equality with the requested bundle
   schema version, defaulting to `1.0`. It rejects mismatches; it does not
   migrate or hand the payload to a version-transition path. The separate
   `polisyos.ir.loading.loaders` API has different return and version behavior;
   see the [TRINITY contract](../contracts/TRINITY.md).
2. `TrinityBundle` and its nested models validate field types, allowed fields,
   identifiers, bounds, and implemented local relationships. The common
   `KernelModel` base forbids extra fields and freezes instantiated models.
   This is strict DTO structure and local invariant checking, not validation of
   whether a policy's assumptions or effects are substantively adequate.
3. `polisyos.ir.linker.link_trinity()` resolves the bundle against the supplied
   registries. It returns a `LinkedTrinityBundle` and a typed `LinkReport` for
   mechanism, parameter, selector, slot, metric, constraint, and schedule
   checks covered by the linker. `LinkReport.ok` means that this run emitted no
   error-severity `LinkIssue`; warnings may remain, and the result is scoped to
   the checks and registry inputs the linker received.
4. Downstream compilers and workflows consume the linked contract. Core owns
   the separate artifact and persistence machinery when a payload crosses a
   storage boundary.

The loader and model validators establish that a payload conforms to the
declared DTO contract and its implemented local rules. Linker success means
that the checks represented by that registry input produced no error-level
issues. Neither result establishes causal adequacy, legal validity, factual
grounding, calibrated performance, or publishability. Those claims need their
own evidence, producer, consumer, and authority checks.

## Schema and compatibility boundaries

The generated [IR schema catalog](../reference/ir/schema-catalog.md) describes
IR models and fields. The generated [shared schema reference](../reference/schemas.md)
maps committed JSON Schema snapshots to their owners and compatibility
metadata. These pages are the field inventories; this explanation does not
duplicate them.

Schema reflection, serialized snapshots, and compatibility policy answer
different questions. A reflected type describes the model surface; a committed
snapshot pins a wire shape; the migration registry decides which declared
versions a reader can accept or migrate. Compatibility is explicit and
versioned. It does not imply that an old payload regains authority or that a
consumer's present-day evidence requirements are met.

Keep the serialization and version coordinates separate as well. The nested
payload's `TrinityBundle.schema_version` is checked by its selected loader;
Core's `SchemaInfo` names a persisted payload schema; `CanonInfo` records the
canonicalization profile used for serialization. IR's `to_canonical_bytes()`
produces canonical bytes and `content_hash()` hashes bytes; Core's
`ArtifactID` identifies a CAS blob by its SHA-256 digest, with the store
checking the blob bytes against that ID on read. These are different
coordinates and are also separate from the explicit migration registry. A
successful CAS integrity check binds the observed bytes to the ID; the ID
alone does not establish producer authorship, factual grounding, or
admissibility. The canonical definitions are `polisyos.ir.artifacts.contracts`
(`ArtifactID`, `SchemaInfo`, `CanonInfo`), `polisyos.ir.model_layer.canon`,
`polisyos.core.artifacts.ids.ArtifactID`, and
`polisyos.core.artifacts.manifest` (`SchemaInfo`, `CanonInfo`).

## Authority, status, and time

Authority is not inferred from a schema version, content digest, typed
reference, `LinkReport.ok`, or a field such as `calibrated`. These values carry
contract identity or local validation results. For Trinity payloads, the
authority boundary is downstream: a proposal remains a candidate until the
evidence and custody path that owns the relevant claim admits it. This follows
the [identity and custody boundary](../system-design-decisions/policyos-identity-and-custody-boundary.md)
and the north star's candidate-to-authority firewall. Stage-0 **S0-K05** and
**S0-K07** prohibit authority by transport or projection, while **S0-K12** says
content equality is not authority. These are ratified boundary rules, not
evidence that every current consumer enforces them.

Statuses also stay local to their contracts. For example, `ConstraintType`
distinguishes hard constraints from soft penalties, and `FidelityLevel`
selects a requested simulation detail. Neither is a lifecycle status such as
admissible, limited, contested, blocked, or publishable. A local flag or
warning must not be projected into a broader decision without an explicit
composition rule and consumer.

`ModelSpec.time_semantics` (`TimeSemantics`) describes a simulation calendar
through `frequency`, `start_date`, and `step_count` or `end_date`;
`ScheduleSpec` describes an inclusive step range through `start_step` and
`end_step` or `duration_steps`. Neither is legal effective time, observation
time, transaction time, freshness, or the validity epoch of a published
claim. The custody and runtime layers must preserve those time roles where
their claims depend on them. The optional `created_at` string on Core's
`TrinityManifest` is creation metadata; it is not a substitute for those
validity or evidence-time roles. The canonical types are
`polisyos.ir.kernel.time_semantics.TimeSemantics`,
`polisyos.ir.governance.schedule.ScheduleSpec`, and
`polisyos.core.contracts.trinity.TrinityManifest`.

## Current implementation and design target

The current IR provides many typed contracts and a registry-aware Trinity
linker. That is useful substrate for the product's causal operating-system
direction, but it is not the universal policy designer itself.

The [universal policy-design target](../system-design-decisions/universal-policy-design-target-architecture-and-gap.md)
describes a broader grammar, facet algebra, design-composition algebra, and
obligation/admissibility calculus. Those are target architecture and identified
gaps; do not treat today's Trinity DTOs, schema catalog, or linker as proof
that the universal grammar or complete admissibility calculus is implemented.
The [north star](../system-design-decisions/policy-design-causal-operating-system-north-star.md)
explains how this present contract substrate fits the longer-term causal
world-model and custody vision.

## Evidence and tests

The tests establish different parts of the current boundary:

- `test_trinity_contracts.py` covers the payload models, serialization, local
  validation, and the separate reference bundle.
- `test_trinity_loaders.py` and `test_ir_migrations.py` cover supported loading
  and explicit schema compatibility behavior.
- `test_trinity_linker_contract.py` exercises registry resolution and typed
  linker failures, including unknown mechanisms, parameters, selectors, and
  slots.
- `test_schema_catalog.py` checks the reflected catalog and generated
  reference freshness; `test_public_surface.py` checks lazy facade behavior.

These tests do not claim that the current IR layer proves a recommendation's
substantive or public admissibility. That remains a separate end-to-end
property of the relevant evidence and custody path.
