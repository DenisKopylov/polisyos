# R1150 — Independent review of the R1137 Search delta

**Decision: GO for Root-owned application and a focused actual-source Search/durable-provider replay.** This is a bounded source review only. The delta remains unapplied here; no runtime receipt, G acceptance, or formal closure is claimed. `closure_ids=[]`.

## Current source and patch identity

The current frame is `root-author-source-frame-r1151-20261013.json@12e262d19976b9a2ca4642cbe228f89e671dbfe09c957fb23ae058e8c4d84213`: branch `codex/e02-unified-local-20261009`, HEAD `5fd4096ab9389d15abcedb00b03b968f6b60c953`, tree `d65d5ba135001d29968734cb0bace6fe50a572b8`. Both R1137 target files match this frame exactly: `controller.py@a729d356a93882e65cbf9ce9b82457b9554140ff20b3b0d713533ab9777e27c5` and `test_search_loop.py@ec108d8e1bc6b2b3e6ab0638032c29c2980cc0c48863d92a1b897af44139e57c`.

The reviewed artifact is only `raw/r1137-search-actual-extra-and-durable-provider-consumer-bounds-20261013/delta.patch@aaa8903007dffa24eefce3b5172d89cf26d45d71ef0f18fe2b83c3005af1ff27` (manifest `@ed0e68295a533d4553cdaa17a2c4e05bbaf1a6439243c2ff36f49b8babca796f`). I independently reran `git apply --check --whitespace=error` against these current preimages; it passed without modifying files. The cumulative R951-based patch was not used.

## Deciding properties

`SearchRunState` declares `best_candidate: dict | None` and initializes `best_objective` to `+inf` (`run_state.py@69a4ed41941be6b8545ab78be653cc89a889886f8ed69de8fb9904aef2855185`). In the actual route, `_generate_candidates` builds the prompt context before invoking the generator; `TracedLLMCandidateGenerator.generate` validates/serializes the request with `_search_prompt_value` before provider dispatch. The proposed producer change maps only `best_candidate is None` together with exact `best_objective == +inf` to an absent score, consistent with the existing ask/tell projection. Candidate-present `+inf` remains malformed; absent-candidate `NaN` and `-inf` remain refusals; populated finite state is unchanged. This is **SAME_CLASS_DEEPER** under P40: close the no-best sentinel at the controller-to-prompt boundary instead of normalizing all infinities.

For callback failures, the delta stores the first typed refusal for one serializer invocation, aborts later wrapped callbacks, and rethrows the original typed error at the owning `_prompt_to_python` boundary. The current-source callback census (`actual-source-census.json@25cb33af2f3b55f9afea60b825147ac2b2a3b20936accfca0544708c3fca8914`) lists all six explicit CoreSchema callback factories and the generic plain/wrap instrumenters. The retained AST-extracted replay (`candidate-ast-replay.json@beddc707bd948b040148fcc4695916beafd5c1b655420eca494b71232d28b844`) preserves `search_prompt_contains_nonfinite_number` for the lossy callback and records no sibling callback calls after refusal. It also retains finite Any/RootModel and nested roots, include/exclude projections, shared acyclic references, raw mapping-cycle refusal, and the existing generic model-through-mapping cycle refusal. This is another **SAME_CLASS_DEEPER** finding: the mechanism now carries the refusal across the current instrumented callback graph, rather than fixing one serializer instance.

The mirrored test adds `+inf` to its existing 13 malformed direct payloads and keeps the zero-provider-call assertion. The finite callback-root case is the fourth valid client call, so the expected count changes from three to four. That count correction is fixture drift, not a product escape.

## P41, verification, and next gate

R1136’s actual run had eight durable-provider owner failures on the no-best `+inf` state. The delta’s source route addresses that trigger, but this review did not apply the patch, run product imports or pytest, or execute the provider-owner workflow. Root still needs the actual composed consumer run and its full output, plus refusal/removal controls and persisted event/stopping assertions. R1136 changed these controller/test paths, which intersect its actual input denominator; those failures are **not** classified as inherited under P41.

The packet’s configured Ruff check is green on both base and candidate. Its full-file Ruff format check fails on both exact base and candidate files; the format-scope receipt reports no overlap between the 195 added patch lines and candidate formatter-removed lines. Since the touched files are within that formatter input, this review does not call the full-file failure inherited under P41; it records the delta-line result separately.

The patch makes no external authority, budget settlement, event completeness, or G claim. Arbitrary serializer side effects and one-shot iterator lifecycle remain the separate unratified R1111 choice. The review recommends Root proceed with this exact two-file delta and the focused actual-source Search/durable-provider replay; `closure_ids=[]`.
