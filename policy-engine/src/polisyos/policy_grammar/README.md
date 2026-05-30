# Policy Grammar (`polisyos.policy_grammar`)

`policy_grammar` owns the W6.A universal policy grammar compiler. It turns
policy intent plus an authority profile and concept-spine refs into a
compilation-only `UniversalPolicyDesignCase`.

## Boundary

- Consumes existing Trinity and governance vocabulary: `ProblemFrame`,
  `PolicySpec`, `PolicyCandidateSchema`, IR outcome channels, policy-layer
  authority levels, observation identification modes, temporal-policy patterns,
  deterministic constraint critic risks, and challenge-factory risk classes.
- Produces typed facets only; it does not call Lex, Fabric, Foundry, Scholar, or
  runtime producer adapters.
- Preserves P15 by treating LLM-sourced profiles as `candidate_unverified`; they
  may expose candidate facets but cannot satisfy legal, data, method, closeout,
  or publication authority slots.

## Where To Start

- `compiler.py` - deterministic W6.A producer.
- `schema.py` - intent and concept-spine input contracts.
- `facets.py` - controlled facet derivation and reuse evidence.
- `consumer.py` - downstream fail-closed readers.
- `artifacts.py` - CAS persistence for compiled cases.
