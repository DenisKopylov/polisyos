# Governance Passes (`polisyos.scientist.governance.passes`)

Owner: `team-scientist`
Last updated: 2026-10-12

## Purpose

This package contains builtin Scientist governance passes for safety,
freshness, privacy, equity, citation, transportability, refutation,
incentive-compatibility, human review, and related workflow gates.

## Public API

Public extension ABI is `polisyos.scientist_governance_passes` in
`architecture/extension_points.toml`. Builtin pass implementations remain
package-private unless exported by the pass registry.

## Internal Layout

| Path | Role |
| --- | --- |
| `base.py` | Shared pass protocol and context helpers. |
| `*_pass.py` | Builtin pass implementations. |
| `_artifact_resolution.py` | Private artifact lookup helper. |

## Extension Points

External passes use the `polisyos.scientist_governance_passes` entry-point
group and must return a validator-pass compatible object. Builtin pass
factories are declared in `pass_entrypoints.py` and mirrored in
`pyproject.toml` so installed packages and in-repo fallback discovery resolve
the same pass IDs.

## Tests

Use `tests/unit/scientist/governance/`, `tests/unit/scientist/nodes/`, and
Scientist integration tests when pass behavior affects workflow output.

## Operability Links

- `docs/reference/scientist/continuous-governance.md`
- `docs/reference/scientist/human-oversight.md`
- `architecture/extension_points.toml`

## Known Shims/Deprecations

Pass ID renames require registry compatibility and a release/migration note
when saved workflow specs can reference the old ID.


## Transportability report intake

`TransportabilityRequiredPass` reads the existing `causal_effect_reports` list,
`causal_report` compatibility alias, and `artifacts_index.causal_report_ref`.
When more than one source is present, it resolves each typed report/reference,
validates it against the existing `CausalEffectReport` contract, deduplicates
identical content, and reports conflicting content. An empty list contributes
no list candidates and cannot shadow another supplied source. Malformed,
unresolved, or conflicting supplied inputs stay visible as typed pass issues.

Embedded canonical `transport_result` and the historical
`method_params["transport_result"]` are admitted only as a validated
`TransportabilityResult`. The legacy form runs through the same recomputed
proof-review grade. A mapping such as `{}` can be schema-valid because the
result model has defaults, but its proof grade is unknown and it remains blocked
in STRICT mode; a supplied null or unparseable legacy value is an input issue.
A direct `artifacts_index.transportability_result_ref` is resolved through CAS
and compared with any report-embedded result. Exact matches are evaluated once;
conflicts block.

This intake does not establish graph truth, data existence/currentness,
empirical grounding, institutional authority, or publication eligibility.
CAS persistence currently serializes nullable report defaults as `null`, so a
report reference cannot recover whether a canonical null was originally
omitted or explicitly supplied. The consumer treats that CAS value as missing
transport evidence; a future presence-preserving artifact contract remains an
open decision.


## Whole-pass transportability admission

The R6 candidate extends the same pass-owned intake across report, transport-result,
and cross-graph-profile sources. It resolves the existing report list, single-report
alias, report CAS ref, embedded canonical/legacy result, direct result CAS ref,
direct profile, and profile CAS ref before applying the pass rule. Supplied refs
must be typed and load through the existing CAS readers; typed mutable reports and
nested profile/result values are revalidated at this boundary. Matching aliases
are evaluated once; conflicting sources and malformed, null, missing-store, or
unresolved supplied values remain explicit issues.

The existing `params.transport_required` input is also parsed at this boundary.
Recognized booleans retain their behavior; malformed supplied values no longer
become `false`. An explicit requirement with no admitted transport disposition
blocks. In STRICT, partial/bounds-only, unsupported, review-required, and unknown
proof premises block; lower-authority profiles retain warnings unless the
requirement is explicit. The existing proof-review grade remains the only
identified-result grade that can clear this pass; profile status or metadata does
not establish a source-bound proof.

This is a candidate intake repair, not an authority verifier. Source authenticity,
graph truth, data existence/currentness/authority, empirical grounding, and
publication eligibility remain `not_established`. The G decision about source and
profile semantics remains open.
