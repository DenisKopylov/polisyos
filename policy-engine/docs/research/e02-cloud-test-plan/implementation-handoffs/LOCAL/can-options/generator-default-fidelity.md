# Q2 generator default fidelity (read-only)

Source basis: root macro commit `24f3b72dd6eaa77cb7493d0880fe181e79181d75` (parent `077a572f`), local candidate `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`. Research only: no product, lockfile, generator, or generated-client source was changed. Prototypes and full test output are in the ignored `LOCAL/raw/can-options/generator-default-fidelity/` directory.

## Finding and bucket

This is the same default-presence-versus-requiredness class one level deeper, not a new class (P38/P40). The Lex `top_k` symptom is produced by a global generator rule over referenced component schemas. The global `--default-non-nullable false` switch fixes that request input but also loosens response types across the generated API, so a Lex-specific rewrite or a global flag is not a safe closure.

The property is: a request field omitted from the OpenAPI object's `required` list remains omittable even when the schema supplies a default; a response field is required only when the source contract or a verified response producer establishes that it is always emitted. The installed implementation instead turns `hasDefault` into requiredness according to a path-string check. A request-body schema nested inline follows a different rule from the same schema referenced through `components.schemas`. The distinguishing case is this `LexSearchRequest`: `top_k` has default 20 and is absent from `required`, but its component path does not contain `requestBody`, so the generated component property is required.

## Source evidence

- The lockfile pins `openapi-typescript@7.13.0` with TypeScript 5.9.3 (`pnpm-lock.yaml:471-473, 5326-5328, 11979-11982`). The installed implementation sets `defaultNonNullable` to `options.defaultNonNullable ?? true` (`node_modules/.pnpm/openapi-typescript@7.13.0_typescript@5.9.3/node_modules/openapi-typescript/dist/index.cjs:56`). Its installed CLI help exposes `--default-non-nullable false`.
- The schema transform computes whether a property is optional from `required`, `hasDefault`, that global flag, and exclusions for paths containing `parameters`, `requestBody`, or `requestBodies` (`node_modules/.pnpm/openapi-typescript@7.13.0_typescript@5.9.3/node_modules/openapi-typescript/dist/transform/schema-object.mjs:336`). A referenced component is generated at its component path, so the request operation's direction is lost at the point where this rule runs.
- A small paired OpenAPI probe with identical inline and component `$ref` request schemas reproduces the path leak: with the default option, inline `top_k` is optional but `components.schemas.Request.top_k` is required; with `false`, both are optional. The full fixture and outputs are retained in `LOCAL/raw/can-options/generator-default-fidelity/inline-vs-ref-openapi.json`, `inline-vs-ref-default-true.ts`, and `inline-vs-ref-default-false.ts`.
- The canonical wrapper invokes the locked CLI without an option, then runs the recursive-type normalizer and Prettier (`apps/runtime-dashboard/scripts/generate-api-client.sh:54-59`). The normalizer accepts generated TypeScript and lifts guarded recursive aliases; it does not receive the OpenAPI document or calculate request/response direction (`packages/runtime-api-client/scripts/normalize-recursive-openapi-types.mjs:106-110, 207-219).
- OpenAPI declares `LexSearchRequest.top_k` with default 20, but only `query` and `output_dir` in its required list (`schemas/runtime_api_v1.openapi.json:23307-23350). The runtime request DTO also defaults it to 20 (`src/polisyos/core/contracts/control.py:1744-1751); the dashboard Zod schema accepts omission and applies the same default (`apps/runtime-dashboard/src/api/validators.ts:1908-1914). Yet generated `LexSearchRequest.top_k` is `number`, not optional (`apps/runtime-dashboard/src/api/types.ts:11847-11860).
- The response side demonstrates why the global switch is not a substitute. `LexSearchResponse.total` is also defaulted and omitted from OpenAPI's required list (`schemas/runtime_api_v1.openapi.json:23351-23400); the current generated type makes it required (`apps/runtime-dashboard/src/api/types.ts:11866-11881). In this specific endpoint, `lex_pipeline.search_lex_graph` explicitly supplies `total` and `results` on the missing-index, normal, and exception return paths (`src/polisyos/runtime/http/services/control/lex_pipeline.py:375-389, 445-470). That is producer evidence for this response field only, not a basis for assuming every defaulted response field is emitted.

## Full-set prototype

Both outputs were generated directly with the installed lockfile-selected CLI from the same `schemas/runtime_api_v1.openapi.json`; the false output then passed through the canonical recursive normalizer and Prettier in the ignored scratch area. The AST comparison covered all component schema properties. A separate reachability census traversed all component schemas and dereferenced request-body/response references for all 114 HTTP operations.

- OpenAPI component schema defaults: 855 property definitions. The global false option changes 838 generated properties from required to optional; 17 remain required under other schema constructs (including const and enum properties, and one explicitly required field). Every changed property maps to a source pointer.
- Among those 838 changed properties, 81 occur only in request inputs, 742 only in responses, and 15 are in schemas reached from both request and response operations. No changed property is unreferenced.
- With the real dashboard `tsconfig.app.json` and the alternate generated file substituted only by a TypeScript module-resolution hook, the current generated types produce 0 diagnostics across 1,119 source files. The false-option prototype produces 63 diagnostics across 13 files (22 TS2322, 40 TS18048, 1 TS2488). Examples include response consumers in `CapabilityDiscoveryPanel.tsx`, `ControlFailurePanel.tsx`, `CaseWorkspacePage.tsx`, and `RunReportPage.tsx`. This is a same-tree differential; the compiler read the original source paths, avoiding relocation-related missing-module noise.

The census and AST diff receipts are `LOCAL/raw/can-options/generator-default-fidelity/default-fidelity-census.json` and `optionality-diff.json`; the typecheck receipts are `baseline-typecheck-current-types.log` and `prototype-typecheck-custom-resolver.log`. The default-false generated `LexSearchRequest.top_k` becomes optional as desired, but `LexSearchResponse.total` also becomes optional.

## Recommended closure and falsifier

Keep canonical generation unchanged until a direction-aware repair is ready. Do not add `--default-non-nullable false` globally, hand-edit `types.ts`, or add a Lex/field-name exception.

A canonical repair should derive schema roles from the OpenAPI source: traverse request bodies and responses through nested schema references, arrays, and composition nodes, with cycle handling. For requests, defaults must not override the owning schema's `required` list. For responses, generated requiredness must be backed by the response contract or independently reconciled producer serialization; the presence of `default` alone is not enough. A component used in both directions needs direction-specific request and response views, rather than one shared property shape. The census found 15 defaulted properties in both directions, including `FetchPlan` and `SearchRequest`.

The falsifier is an inline-versus-`$ref` pair with identical schema content: both request-body forms must generate the same optional input field, and moving the schema between request-only, response-only, and mixed use must not leak one direction's requiredness into another. Include a response producer that omits a defaulted property to prove the output side does not infer presence from a marker. Retain the existing Lex check as an example, not as the scope of the mechanism.

## Reproducibility and hashes

The raw directory contains the exact generated outputs, generation logs, census/comparison scripts, and TypeScript compiler logs. Deciding-output SHA-256 values:

- `optionality-diff.json`: `8e499d6b138348f1e65a12afa981e3e2e72e8cb715127d250641ac99f7749e63`
- `inline-vs-ref-openapi.json`: `014530bee477f4147834328c988c69579d51693ea63d578b45b9b6450ec20986`
- `inline-vs-ref-default-true.ts`: `871b54325a5173ad0b12d49e72d6c207407337202de6d5bdb7ca32ad5d8009d1`
- `inline-vs-ref-default-false.ts`: `2cbcc20cbd835786fe48774c838a4bc6fb695ed48b74e9a7bf350ba8d0d97b95`
- `prototype-typecheck-custom-resolver.log`: `a005ace6669ec82489d788ebd1c3e67467e3ff04f23aa1e018c969c2a7c1cbd7`
- `baseline-typecheck-current-types.log`: `262e1681a1175e631171ba426411cf1929a1391ef94022d2fe7fdcab57bec4e6`

Key source SHA-256 pins at this read:

- OpenAPI: `c293a5b39de1d9088b1211c94e2c8e59085a25edd387a2f3914ced0e072ab6f2`
- Dashboard generated types: `542d3fd459d8c22dfadea1347b5d6dc3c30d33644bfab4fa4121a65a0fcd8c8c`
- Generator wrapper: `6a17a9eec6f298acbcfce67cf034a4f6a6a053e6f15301a797665eabe039d553`
- Recursive normalizer: `6a294253f2099cea6205a0865a52aa3caa48962da1564666afe22f84208071c3`
- Lockfile: `436723e8090a442f7ecb2d544ddac5ac2ee2c8a9680f64ef28d3444da2f4161e`
- Installed schema transform: `cd7d716f495e03fbb725699fc595cc938c684d1117790976bee8184c819c3dac`
