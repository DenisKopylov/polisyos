# 0110. IR Frontier Governance and Causal Contracts

Status: accepted

Date: 2026-04-13

## Context

After the core IR surface was hardened, Phase 5 still lacked first-class
contracts for:

- temporal compliance logic and explicit policy-execution semantics;
- multi-level policy composition across federal/state/local layers;
- richer mechanism-design metadata for strategic policy authoring;
- frontier causal families such as latent representation learning,
  multi-environment invariance, causal RL, time-series discovery frontier
  outputs, and recourse/explanation artifacts.

Without typed IR contracts these concepts remained either implicit in prose or
had to be tunneled through unstructured metadata, which broke reflection,
schema-catalog coverage, and downstream tooling.

## Decision

We add contract-first, frozen-by-default IR modules for the Phase 5 frontier:

1. `polisyos.ir.governance.temporal_logic`
   LTL/CTL/MTL subset with explicit `execution_semantics`,
   `evaluation_scope`, and `time_domain`.
2. `polisyos.ir.governance.policy_composition`
   policy layers, override rules, compatibility constraints, and versioning
   mode for composed federal/state/local stacks.
3. `polisyos.ir.governance.game_design`
   extensive-form, Bayesian, repeated-game, incentive-compatibility, and IR
   metadata for policy/mechanism design.
4. Selector AST extensions in `polisyos.ir.governance.selector_expr`
   quantified, aggregate, and temporal selector predicates.
5. Frontier analytics modules:
   `representation_learning`, `invariance`, `causal_rl`,
   `temporal_frontier`, and `recourse`.

`PolicySpec` gains optional fields for temporal constraints, policy
composition, and mechanism-design metadata. These additions are additive and do
not alter legacy payload semantics.

## Consequences

Positive:

- tooling can discover and inspect the frontier surface through the schema
  catalog and reflection API;
- policy authoring can declare temporal, layered, and strategic semantics
  without untyped metadata blobs;
- frontier causal outputs gain stable report/spec contracts for offline
  research, interchange, and docs generation.

Tradeoffs:

- the analytics facade grows, so package-level export counts and docs must stay
  ratcheted by the public-surface audit;
- these contracts remain research-oriented surfaces and do not imply default
  runtime support for every frontier method.

## Related

- [0107](0107-ir-analytics-normalization-and-schema-compatibility.md)
- [0108](0108-ir-schema-catalog-and-reflection.md)
- [0109](0109-ir-transport-and-interoperability-bridges.md)
