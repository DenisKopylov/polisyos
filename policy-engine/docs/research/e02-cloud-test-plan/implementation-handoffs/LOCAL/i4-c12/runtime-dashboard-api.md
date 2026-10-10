# C12 runtime-dashboard API slice

Candidate base supplied for this author slice: `a499…`. This local receipt covers only the Legal search API boundary in the dashboard; root owns Core/OpenAPI and generated API types.

## Contract and source pins

- C12 property: request → typed Legal generation intent → encoded query → fresh reader; missing, wrong, stale, or unpaired profiles refuse. Source: `execution-prompts/parallel-2026-10-08/C12.md` lines 13–15; i4 source context: `LOCAL/i4-c12/README.md`.
- Core request DTO: `src/polisyos/core/contracts/control.py` (`LegalQueryGenerationIntentV1`, `LexSearchRequest`). An absent or null intent is a supported text-fallback request; an empty intent is distinct and the service returns `query_profile_malformed`.
- Core response DTO/projection: `src/polisyos/runtime/http/services/control/lex_search_projection.py` carries `search_mode` and nullable `vector_refusal_code`; `services/control/lex_pipeline.py` emits the typed refusal on missing and malformed profile paths.
- Result owner: `src/polisyos/lex/knowledge/types.py::LegalFactResult`. The former dashboard validator projected only a subset; the updated validator mirrors the complete current DTO, including its status, temporal, quality, provenance, and similarity fields.
- Existing consumer: `apps/runtime-dashboard/src/api/hooks/useLexSearch.ts` parses each successful response with `lexSearchResponseSchema`. The generated `types.ts` file was not edited; root will regenerate it through the canonical API artifact recipe after Core freeze.

## Change and P40 bucket

Changed source files:

- `apps/runtime-dashboard/src/api/validators.ts` adds the typed Legal query-intent request schema and requires response `search_mode` plus the explicit nullable `vector_refusal_code`. Its result-item schema now preserves the full `LegalFactResult` projection without fabricating omitted Legal defaults. Empty intent remains an explicit supplied value so the owner can distinguish it from absent/null intent and return its own refusal.
- `apps/runtime-dashboard/src/api/validators.test.ts` parses fresh text-refusal and vector-success responses, checks an explicit missing/malformed intent path, compares all returned Legal result fields, and rejects a result with `temporal_provenance_json` removed plus malformed intent shapes.

P40 classification: **same hidden-surface-loss class one level deeper**. Adding mode/refusal alone would leave the sibling loss in the same Legal response projection. One schema was widened to the full current owner DTO. The falsifier is behavioral: the complete literal Legal result survives a fresh Zod parse, while removing a required owner field is rejected. This is not a claim about future schema additions.

The request validator is an API contract helper; the existing hook is typed through generated `types.ts`, which remains pending root regeneration. The local browser/runtime display was not changed or tested under the frozen browser wave. This slice does not claim formal C12/G closure or production Legal model authority.

## Verification

- TDD red before widening: `corepack pnpm exec vitest run src/api/validators.test.ts -t 'preserves Legal search mode'` exited 1 because Zod returned only the old subset of the fresh Legal fact result; the expected full owner payload did not match.
- Green: `corepack pnpm exec vitest run src/api/validators.test.ts` — **32 passed** (Vitest 4.1.5, 1.34s).
- `corepack pnpm run typecheck` — exit 0 across app, node, and tools TypeScript configs. This was after the result validator was widened and before root regenerates `types.ts`.
- `corepack pnpm exec eslint src/api/validators.ts src/api/validators.test.ts --max-warnings=0` — exit 0.
- Prettier comparison: `validators.test.ts` matches. `validators.ts` has one formatter delta at line 451 (`cost_origin`) outside this Legal slice; it was left unchanged to preserve the shared work. The changed Legal hunks match the formatter output.
- No generated API command, browser run, heavy test, or Git operation was performed.

## Exact byte pins

SHA-256 of dashboard files after this slice:

- `apps/runtime-dashboard/src/api/validators.ts`: `32d8611b79bd70ad48ad26e18bf36676643562dbd9a8920f848269ece4df6da3`
- `apps/runtime-dashboard/src/api/validators.test.ts`: `86d465a9af38b475adeadfc6164a437b562bcd632b858f3f21fbd5955cc8c898`

Read source pins:

- `src/polisyos/core/contracts/control.py`: `d134f463840c4672ef60791a23273e83bb8b8421754f38fca78516604f4d2757`
- `src/polisyos/runtime/http/services/control/lex_search_projection.py`: `fac08149278e2b3a76ccafd2c3cff5e165a3f74d8992d991ff9cdbd3edbdf1e1`
- `src/polisyos/lex/knowledge/types.py`: `6d826f613f71bfae01d8351c4262c9f25704058ef6130e855e651e68ae4e6243`
- `src/polisyos/runtime/http/services/control/lex_pipeline.py`: `b13f045d00aec84b41fbcf8928d72a487702758a81aa4c26a7c6bc3610927d0a`
