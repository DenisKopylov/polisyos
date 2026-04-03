# ADR-0089: Pre-Implementation Survey for Simplified TR Scope Validation

## Status
Proposed

## Date
2026-02-28

## Context
Transportability analysis requires specifying the scope of a policy intervention --
target population, geographic context, temporal window, and institutional setting.
In practice, analysts often leave scope under-specified, leading to vacuous or
overly optimistic transportability results. Phase 12 introduces a lightweight
pre-implementation survey (30-50 structured policy questions) that captures scope
parameters before any causal estimation begins, enabling early validation of
transportability requirements.

## Decision
1. Define a structured survey instrument of 30-50 questions covering: target
   population characteristics, geographic and institutional context, intervention
   mechanism, expected time horizon, and known effect modifiers.
2. Store survey responses in a new `data/phase12_survey.json` artifact, versioned
   alongside the analysis bundle.
3. The `transport_check` foundry method consumes survey responses to pre-filter
   obviously non-transportable source-target pairs before running formal
   transportability algorithms, reducing computational waste.
4. Implement a `SimplifiedTRScopeValidator` that checks completeness and internal
   consistency of survey responses; incomplete surveys emit a governance WARNING
   and block transportability estimation until resolved.
5. Survey questions are maintained as a YAML catalog to allow domain-specific
   extensions without code changes.

## Consequences
### Positive
- Forces explicit scope declaration, reducing silent transportability failures.
- Early filtering avoids expensive computation on obviously incompatible contexts.
- YAML-based question catalog is extensible by domain experts without engineering.
### Negative
- The 30-50 question survey adds upfront effort for analysts.
- Question relevance varies by domain; a generic instrument may miss critical
  context-specific factors.
- Survey responses are self-reported and may contain inaccuracies that propagate
  into transportability decisions.
