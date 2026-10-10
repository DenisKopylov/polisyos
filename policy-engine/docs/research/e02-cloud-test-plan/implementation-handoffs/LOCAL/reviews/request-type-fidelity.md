# Request type fidelity review

## Result

Partial. The focused generator suite passes, and synthetic probes confirm that the request projection preserves source-requiredness for ordinary schemas, nullable/defaulted fields, recursive references, allOf inline required fields, and discriminated oneOf branches while leaving the response projection unchanged. Two findings remain: a schema-position `$ref` can resolve to the wrong OpenAPI component kind, and composition with a referenced default plus a required-only allOf sibling exposes a same-class second P40 escape.

This was a read-only review of the candidate generator at the source hashes below. No production source, generated client, or Git state was changed; no full generation or heavy suite was run.

## Source and runtime identity

Candidate product root: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`.

- `schemas/runtime_api_v1.openapi.json`: `c293a5b39de1d9088b1211c94e2c8e59085a25edd387a2f3914ced0e072ab6f2`
- `packages/runtime-api-client/scripts/generate-openapi-types.mjs`: `c4de0d3b96f93708ae2b74d8a8635c47c4203266dec905f69a6e172f71e24a7f`
- `packages/runtime-api-client/scripts/generate-openapi-types.test.mjs`: `e6265f31e621a5dae9758d8e1d8f4e9260300917c7d6207d13e50f060f1e3cfe`
- `packages/runtime-api-client/types.ts`: `7712850db89328de5a2e353af3351db30476de5c44cb926a3c02874bc670b3d0`
- `apps/runtime-dashboard/src/api/types.ts`: `542d3fd459d8c22dfadea1347b5d6dc3c30d33644bfab4fa4121a65a0fcd8c8c`
- Node `v22.22.2`; resolved `openapi-typescript` `7.13.0`; TypeScript `5.9.3`.

Focused command: `node --test packages/runtime-api-client/scripts/generate-openapi-types.test.mjs` — 6/6 passed in 1.37s. Full stdout is in `LOCAL/reviews/raw/request-types-focused-test.txt`.

## Behavioral evidence that passed

The actual `generateOpenApiTypes` entry point and TypeScript compiler were used for synthetic schemas. Probes verified:

- request bodies and reusable query parameters use the request view;
- source-required fields remain required, while defaulted non-required fields may be omitted;
- nullable fields preserve nullability and presence independently;
- readOnly/writeOnly fields remain represented in the generated shape;
- recursive schema refs remain recursive;
- an inline required field in an allOf branch remains required;
- invalid oneOf discriminator branches are rejected;
- the shared response projection preserves its existing requiredness behavior;
- the OpenAPI input object is not mutated.

Deciding outputs: `LOCAL/reviews/raw/request-types-adversarial-valid.txt` and `LOCAL/reviews/raw/request-types-field-semantics.txt`. Existing focused tests additionally cover collisions, external/unresolved refs, and checked-in Lex source fields.

The current source census contains 583 schemas and 114 path operations. Across 855 defaulted property definitions, the role partition is 81 request-only, 15 request/response-shared, and 759 response-only. The complete role counts are in `LOCAL/reviews/raw/request-types-default-role-counts.txt`.

## Finding 1 — schema-position ref kind is not validated (P38)

**Property:** A `$ref` in a schema position must target a valid schema location; a resolvable pointer to a different component kind must be refused.

**Implementation:** `resolveLocalReference` confirms that the JSON pointer resolves to an object. `schemaReference` recognizes schema-component refs, but `walkSchema` does not reject a resolved pointer for which `schemaReference` returns no schema ref; it walks the arbitrary resolved object instead.

**Divergent case:** a request schema `$ref: "#/components/responses/Else"` is accepted and produces `components["responses"]["Else"]` as the request body type. External refs, missing refs, and malformed pointers are refused, so this is specifically the wrong-local-component-kind boundary.

Evidence: `LOCAL/reviews/raw/request-types-reference-controls.txt` and `LOCAL/reviews/raw/request-types-foreign-pointer-consequence.txt`.

**Assessment:** New P38 class in this review; no current corpus hit was established. Minimal closure is generic schema-location validation for refs encountered in schema positions, including valid nested schema pointers, while retaining refusal for external/unresolved refs. The existing release claim that external refs are refused remains accurate but does not cover this case.

## Finding 2 — allOf required-only sibling can be weakened by a ref default (P38, P40)

Synthetic valid OAS 3.1.0 schema:

```json
{
  "DefaultField": {
    "type": "object",
    "properties": {"value": {"type": "integer", "default": 7}}
  },
  "Shared": {
    "allOf": [
      {"$ref": "#/components/schemas/DefaultField"},
      {"type": "object", "required": ["value"]}
    ]
  }
}
```

`Shared` is used as both request and response. The candidate request type rejects `{value: 7}` because the required-only branch becomes `Record<string, never>`, and accepts `{}` because the referenced default is made optional; the `@ts-expect-error` for omission is unused. Baseline openapi-typescript 7.13.0 also rejects the present object due to the required-only branch (`Record<string, never>`), but correctly rejects omission. Thus valid presence already has a baseline expressiveness limitation, while the candidate introduces an omission-acceptance regression.

Evidence: `LOCAL/reviews/raw/request-types-cross-ref-required-retry.txt` and `LOCAL/reviews/raw/request-types-cross-ref-baseline-and-new-retry.txt`.

**P40 bucket:** same default-presence/requiredness class as the earlier default-fidelity review, one level deeper through composition; this is the second occurrence. Do not patch only this schema. Widen the generic composition-aware mechanism or record a bounded residual and run this falsifier. A generalized AST-only required-constraint intersection with the referenced property provider may avoid `Record<never>`; preserve explicit `additionalProperties: false` semantics, and keep `anyOf`/`oneOf` branch requirements branch-relative rather than unioning them.

A complete current-source scan found zero schemas where an allOf required-only sibling names a defaulted property supplied by another allOf ref or inline sibling. This is a bounded current-corpus limitation, not evidence that the type relation is generally correct. Raw scan: `LOCAL/reviews/raw/request-types-composition-census-refined.txt`.

## Scope and limitations

Both supported generator entry points call the shared request-type generator: `packages/runtime-api-client/scripts/generate-runtime-api-client.sh` and `apps/runtime-dashboard/scripts/generate-api-client.sh`. No entrypoint divergence was found.

ReadOnly/writeOnly were checked for field preservation. In OpenAPI 3.1 these are annotations whose directional enforcement may be ignored or treated as an error by consumers; this review does not claim that generated client types should filter those fields.

The first attempt at one inline probe had module-resolution/syntax setup errors and was superseded by the retained successful runs. `LOCAL/reviews/raw/request-types-source-census.txt` contains an incorrect assertion about zero unreferenced schema names; do not use it as evidence. The refined default-role counts and composition scan are the deciding census outputs.

No full generator run, complete monorepo suite, or generated-file mutation was performed. Root should run canonical generation and whole-profile closeout after source and metadata freeze.

## Author delta replay (2026-10-09)

The author widened the generic source graph and required-property normalization after the first review. I re-read the new implementation at `packages/runtime-api-client/scripts/generate-openapi-types.mjs` SHA-256 `2d9a0590f7633dddd4eaedb646132de9495ac52564dc579bdf417e5281722bcc` and its tests at `packages/runtime-api-client/scripts/generate-openapi-types.test.mjs` SHA-256 `52323ed0679f5fa191cde575a34dcca215ba864278e6a42069c6bff3f4dfa77e`.

Delta controls now pass:

- Replayed the exact earlier inline-required allOf falsifier: a defaulted property supplied by a schema ref plus a required-only inline allOf sibling. The request accepts `{value: 7}`, rejects omission (the `@ts-expect-error` is consumed), and generation leaves the input object unchanged.
- The wrong-role request schema `$ref` to `#/components/responses/Else` now refuses with `Invalid schema reference ... target is not an OpenAPI Schema Object or schema subfragment ... has response`.
- The shared response projection's TypeScript diagnostics exactly equal the locked `openapi-typescript` 7.13.0 baseline for the adversarial allOf fixture (both produce two diagnostics for the deliberately narrow baseline response relation); no new response rewrite was observed.
- A recursive schema control preserves the recursive request shape and source-required nested `children` field.
- The checked-in focused generator suite passes 11/11 tests, including required-ref/allOf, nested recursion/oneOf, impossible `additionalProperties:false` refusal, schema-role refs, and reusable object-role refs.

Raw deciding outputs:

- `LOCAL/reviews/raw/request-types-delta-focused-tests.txt` SHA-256 `fcf66e5054f34100c53ca1797d8e5ec1d9d7c5acd09781e2498f6fd45de6dba5`
- `LOCAL/reviews/raw/request-types-delta-controls.txt` SHA-256 `a82cde5d5a519d012298a59b13461635e8ccab57a992b80c2dbe3def5bebb4c4`

The two first-review findings are closed by the generic source-slot kind check and composition-aware request projection in this candidate. This is a bounded delta review of the frozen author change, not canonical generation or whole-profile closeout; those remain for root after source freeze.
