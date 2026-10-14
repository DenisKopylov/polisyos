# Trinity

Related reference:

- [IR problem framing](../reference/ir/problem-framing.md)
- [IR schema catalog](../reference/ir/schema-catalog.md)
- [Foundry compile and execute](../reference/foundry/compile-execute.md)
- [Scientist workflows](../reference/scientist/workflows.md)

Related contracts: `src/polisyos/ir/trinity/`, `src/polisyos/ir/governance/`,
`src/polisyos/ir/model_layer/model_spec.py`,
`src/polisyos/core/contracts/trinity.py`, and `src/polisyos/ir/linker/`.

Related architecture:

- [Causal operating-system north star](../system-design-decisions/policy-design-causal-operating-system-north-star.md)
- [Universal policy-design target](../system-design-decisions/universal-policy-design-target-architecture-and-gap.md)
- [Identity and custody boundary](../system-design-decisions/policyos-identity-and-custody-boundary.md)
- [Stage-0 custody ratification](../system-design-decisions/stage0-custody-kernel-ratification.md)

- Owner: `@ir-owners`
- Source of truth: `src/polisyos/ir/trinity/`, `src/polisyos/ir/governance/`,
  `src/polisyos/ir/model_layer/model_spec.py`,
  `src/polisyos/core/contracts/trinity.py`, `src/polisyos/ir/linker/`, and the
  tests listed below.
- Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
- Evidence level: source and test inspection at the pin; tests were not rerun for this documentation update.

---

Trinity separates a policy problem into a goal-and-constraint frame, a proposed
intervention set, and a model of the world in which that proposal will be
evaluated. The current IR payload is an authoring and transport contract. It
does not by itself prove that a proposal is grounded, executable, lawful,
admissible, or ready to publish.

## The current IR payload

| Contract | Current responsibility | Important boundary |
| --- | --- | --- |
| `ProblemFrame` | States the problem domain, objectives, KPIs, success criteria, hard and soft constraints, stakeholders, and optional normative framing. | Declares goals and boundaries; it does not establish that the goals are institutionally authorized or that a metric is adequately measured. |
| `PolicySpec` | Declares interventions, target selectors, schedules, mechanism bindings, parameters, and related execution constraints. | Describes a proposal; it does not establish the effects of those interventions or their authority. |
| `ModelSpec` | Declares a data-snapshot reference, optional registry reference, model assumptions, agent and environment configuration, simulation time semantics, fidelity, and calibration fields. | Describes a model configuration; references and flags alone do not prove source availability, calibration quality, or model validity. |

The IR payload type is `polisyos.ir.trinity.TrinityBundle`, also exported as
`polisyos.ir.TrinityBundle`. It contains the three model objects as
`problem_frame`, `policy_spec`, and `model_spec`, with bundle schema version
`1.0`.

There is a second type with the same short name.
`polisyos.core.contracts.trinity.TrinityBundle` is a Core reference container:
it holds `problem_frame_ref`, `policy_spec_ref`, and `model_spec_ref`, plus a
`compatible` field and compatibility notes. It does not embed the three IR
models. Use the fully qualified name when the type could be ambiguous.
`polisyos.core.contracts.trinity.TrinityBundleRef` points to a persisted bundle
artifact; it is distinct from both bundle models.

## Validation and admission

The current path has three separate boundaries:

1. `polisyos.ir.trinity.loaders.load_trinity_bundle()` accepts a mapping,
   JSON, YAML, or UTF-8 bytes and checks the requested schema version. The
   default supported bundle version is `1.0`.
2. The nested IR models inherit `KernelModel`, which forbids unknown fields and
   freezes instantiated models. Their validators enforce declared field
   shapes, identifiers, bounds, uniqueness, and implemented local
   cross-references.
3. `polisyos.ir.linker.link_trinity()` checks the bundle against a supplied
   `RegistryBundle`. It returns a `LinkedTrinityBundle` and a typed
   `LinkReport` with issues for the registry checks it performs. The default
   `strict=True` behavior reports missing required registries and unresolved
   bindings as errors.

These checks answer different questions. DTO validation asks whether the input
matches the declared structure and local rules. Linking asks whether references
resolve against the registries supplied to that call. A successful
`LinkReport` means there are no error-severity linker issues; it is not a
semantic proof of causal effects, evidence quality, legal interpretation,
normative legitimacy, or publication authority.

Schema strictness is not the same as epistemic validation. For example, the
`ModelSpec.calibrated` field is a Boolean in the payload, while evidence that
calibration occurred and is adequate must be established by the consuming
workflow. Likewise, the reference-container `compatible` field is data carried
by that model; it is not independently verified by the field's presence or
default value.

## Authority, status, and time

Trinity's three IR models do not issue a policy decision or a public
justification signature. An artifact ID, typed reference, schema version,
canonical digest, or linker result establishes only the identity or checks
represented by that contract. Authority must come from the evidence and custody
path responsible for the claim, under the [identity and custody boundary](../system-design-decisions/policyos-identity-and-custody-boundary.md).
Stage-0 **S0-K05**, **S0-K07**, and **S0-K12** make the same boundary explicit:
transport, projection, and content equality do not create authority. This
ratification states the rule; it does not prove each runtime consumer applies
it.

Statuses and flags in these models are local. `ConstraintType` distinguishes
hard constraints from soft penalties, `FidelityLevel` selects a requested
simulation detail, `InterventionSpec.enabled` controls whether an intervention
is declared active, and `ModelSpec.calibrated` records a supplied calibration
flag. None of these fields is a universal lifecycle status or implies
`admissible`, `publishable`, or any other public outcome. Cross-status meaning
requires an explicit rule and the consumer that applies it.

`ModelSpec.time_semantics` uses `TimeSemantics` to describe a simulation clock:
frequency, start date, and a step count or end date. Policy schedules describe
activation over that model's steps. These fields do not by themselves describe
legal effective time, observed time, transaction or ingestion time, freshness,
or a validity epoch for a published claim. The custody layer has to preserve
those other time roles when they affect a signed claim.

## Current implementation and target architecture

The current implementation provides the typed Trinity models, loaders,
registry-aware linker, migration behavior, and schema reflection. This is a
useful authoring boundary and contract substrate.

The [universal policy-design target](../system-design-decisions/universal-policy-design-target-architecture-and-gap.md)
describes a wider universal grammar, facet algebra, design-composition
algebra, and obligation/admissibility calculus. Those elements are target
architecture with explicit implementation gaps; they are not delivered by the
Trinity schema alone. The [north star](../system-design-decisions/policy-design-causal-operating-system-north-star.md)
places policy proposals inside a causal world model and requires a
candidate-to-authority firewall. Current Trinity inputs participate in that
direction but do not implement the whole system.

## Evidence and tests

The relevant evidence is distributed across focused suites:

- `tests/contract/test_trinity_contracts.py` covers the three IR models, local
  validation, serialization, and both reference and payload bundle types.
- `tests/unit/ir/test_trinity_loaders.py` and
  `tests/contract/test_trinity_migration.py` cover loading and migration paths.
- `tests/contract/test_trinity_linker_contract.py` exercises registry
  resolution and negative cases such as unknown mechanisms, parameters,
  selectors, and slots.
- `tests/contract/test_ir_migrations.py` covers explicit schema compatibility
  decisions; `tests/unit/ir/test_schema_catalog.py` and
  `tests/unit/ir/test_public_surface.py` cover the catalog and lazy facades.

These checks establish the behaviors named above. They are not an end-to-end
test that a policy recommendation is substantively admissible or publishable.
