# Scholar Requirement Compiler (`polisyos.scholar_requirement`)

`polisyos.scholar_requirement` compiles claim-level policy-design obligations
into typed Scholar support requirements. The package is intentionally small: it
does not search literature and does not score sources. Its job is to state what
Scholar must prove for one claim before the Scholar adapter binds publications,
conflicts, and independence records.

## Role In System

- **Depends on:** Pydantic and local typed inputs only.
- **Used by:** `polisyos.scholar` search, evidence, and spine bindings.
- **Boundary function:** keeps academic publication support separate from
  affected-person representativeness under ADR-0167 / FT-ADR-02.

## Public Entrypoints

- `ScholarSupportRequirementCompiler`
- `ScholarSupportRequirementSpec`
- `ScholarClaimRequirementSeed`
- `ScholarSupportRequirementCompilationResult`
- `normalize_scholar_support_requirement_specs`

## Pattern Pass

W7.D is `build_new` only for the compiler owner because no per-claim Scholar
RequirementSpec existed. The Scholar adapter path is `extend_existing`: W3.D
already emitted query graphs, snippets, scoring, support/conflict links,
dependence records, and participation downgrades.

Relevant guards: `P01`, `P02`, `P10`, and `P14`. The compiler is useful only
when consumed by Scholar evidence and spine bindings; publication counts must
collapse through dependent corpus rules before they can satisfy support.
