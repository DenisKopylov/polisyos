# ADR-0106: IR Shared Validation Toolkit and Identifier Policy

Status: accepted

Date: 2026-04-12

## Context

IR contracts across governance, kernel, observation, and analytics had
reimplemented the same invariant categories in slightly different ways:
duplicate-id checks, finite numeric validation, confidence/bounds checks,
interval monotonicity, selector guardrails, and path validation. The result was
inconsistent error wording, uneven depth limits, and cross-model integrity rules
that depended on which module happened to own a local validator.

At the same time, identifier patterns were not clearly separated by domain.
Generic IR identifiers, governance-authored IDs, and runtime slot paths each had
different syntactic needs, but that difference was only implicit in regexes
spread across multiple modules.

## Decision

Shared invariant categories must go through `polisyos.ir._validation` unless a
module has a domain-specific reason to tighten the rule further. The shared
toolkit is the canonical source for:

- `ensure_unique_ids(items, key_fn, label)`
- finite numeric validation
- confidence/bounds validation
- interval monotonicity
- non-empty path and dotted-path validation
- disjointness checks
- selector operator/value shape checks, collection limits, and field-depth
  limits

Message policy is unified around stable category labels such as
`duplicate {label}` and `{field_name} must be finite` so equivalent invariant
failures produce equivalent diagnostics across modules.

Selector predicates use a shared guardrail contract:

- field names are non-empty dotted paths with bounded depth,
- `contains`, `in`, and `not_in` require non-empty lists,
- numeric comparison operators require numeric scalars,
- selector AST depth and node count are bounded before execution.

Float rejection is recursive over raw containers and nested Pydantic
`BaseModel` instances. A nested model passed through `ParamValue` is therefore
subject to the same "no binary float payloads" rule as a plain dict/list
payload.

Identifier policy is explicit:

- `kernel.base.ID_PATTERN` is the broad generic IR identifier pattern and may
  include `.` and `-` for namespaced registry IDs and artifact-friendly labels.
- `kernel.base.SLOT_ID_PATTERN` is stricter and excludes `-` so runtime slot
  paths remain unambiguous and path-like.
- Governance-authored authoring IDs such as `problem_id`, `policy_id`,
  `objective_id`, and similar fields may use narrower local patterns when the
  domain wants a tighter naming discipline.
- Any field that semantically points to a runtime slot must use
  `SLOT_ID_PATTERN`, not the broader generic ID pattern.

Cross-field analytics invariants that span multiple measures or paths, such as
PN/PS/PNS bounds, mediation decomposition identities, actual-causality witness
consistency, proxy uniqueness, and strategic/readiness uniqueness, are part of
the IR contract surface and must fail during model validation rather than in
downstream execution.

## Consequences

Equivalent invariant classes now fail earlier and with consistent diagnostics
across modules. Selector, mediation, actual-causality, and readiness payloads
become deterministic to validate before execution. Runtime slot references are
distinguished clearly from generic IR IDs, and nested model payloads can no
longer bypass float-rejection policy by hiding binary floats inside
`BaseModel` instances.
