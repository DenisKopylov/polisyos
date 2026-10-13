# R1202 — independent review of the complete second Gateway history assertion

**Decision: GO for the focused composed native wave.** R1194 closes the R1186 full-record verification gap in the actual second Gateway request. It compares all source-owned Search history and objective fields at the captured HTTP boundary against an independently assembled expected mapping and the producer record captured at dispatch. This is a test-only change; the Search controller and projection are unchanged.

## Frozen inputs and current source

- Current frame: `root-author-source-frame-r1195-20261013.json` SHA-256 `80e00b4a93b017b3be7180514c61228fc713aff151514169e6393d1aeceb46d6`; HEAD `4e29fef01b31a6e13dbc848510503ef65fb2b7cd`, tree `6760392b7e39aa8b31e468f6b2fba29ede0924b3`, branch `codex/e02-unified-local-20261009`.
- Physical Search preimages remain the frozen R1195 values: test `e8d437cd3d7127e9c63af91da488fd8bfdc80fba939c0c80f0dbf991bd9aff36`; controller `c6f41ec5139dbf0fa665a7f55fcdb6a89cc849a489af59e8bfddf1a116614cf5`.
- R1194 delta SHA-256 `03d7513a5068566dc6dc9dc031ac58063d9e79ece0c8038e5dce86f538e5e7d8`; manifest SHA-256 `1a049c5eaaa2f86ccb2570be9d791d1d8232a3bd0517cbb47e67e30435d44162`. It starts from the exact R1190 test postimage `ee41e60406da809b32090217e4271d8f85ddb5ea21ebe3fabeb569eb44aea28e` and yields `89229f52da7c6e353a3b3f3c24fff9f6115aa00de0585ee5a555e4a65917d354` (96,036 bytes).
- R1200 composition SHA-256 `cc59f9dfb08fb15972ce0e5cf53cc771482b93a3c6d11d65781783c42a49bbc6`; composed net patch SHA-256 `1408fbd3abc1d1f20c37adda9407ddd2821a019fa64686aed248f5f951052580`. It composes R1190, R1192, and R1194; its Search test postimage matches the R1194 hash above. `git apply --check --whitespace=error` on the composed patch passed without writing source.

## Deciding property

At the second `FakeSession.post` dispatch, the test captures `controller._history` into `dispatch_records`. It later proves the completed `result.history` equals that captured producer record and reads the second request from the actual `GatewayLLMClient` JSON payload. The test constructs expected values from the candidate fixture, the declared quadratic objective, the Stage B callback output, and the source-owned record fields. It does not call `_search_prompt_history` or another serialization helper to build expected output.

Coverage is complete by construction for both records: the expected and wire history keys are each compared to `dataclasses.fields(SearchIteration)`, and the expected and wire objective keys are each compared to `dataclasses.fields(ObjectiveValue)`. The full wire row is then compared to the expected mapping. The checks cover candidate and objective values, all six objective detail values including the direction string, Stage A and Stage B results, duration, policy-evaluation value/status/error, timestamp conversion, and iteration. The owner-record consistency checks also tie Stage B output and the run history back to the actual callbacks and producer.

The delta preserves the preceding actual-path assertions: exactly two Gateway requests, two committed settlements bound to the selected run and budget key, `$0.50` durable spend, one completed iteration, one Stage B evaluation, and stopping after the `$0.30` threshold. The nested unsupported-value, cycle, non-finite, and foreign-row refusal controls from R1177 are unchanged. No generic dataclass support or string fallback is introduced.

The exact R1190 postimage has one user-message comprehension clause, `for message in second_request["messages"]`; R1194 preserves it. My prior R1186 note claiming a duplicated comprehension was incorrect and is corrected separately without modifying the frozen R1186 artifact.

## Classification and limits

- **P40: SAME_CLASS_DEEPER.** This widens the same producer-to-second-Gateway history preservation test from selected fields to the whole typed owner record. Reflection derives the required field sets from the source dataclasses, so additions to either record fail the assertion until their expected semantics are deliberately addressed.
- **P38:** the gate now measures the complete serialized row at the actual second-request boundary, rather than a selected-field proxy.
- **P37:** spend remains derived from the durable ledger snapshot and run-bound settlement events; the caller’s cumulative-cost claim is not treated as evidence.
- **P41:** the original R1175 Search failure intersects these Search paths, so it is not inherited debt for this slice.

Author receipts report AST parse and configured Ruff 0.14.10 check/format success for the candidate. Root’s R1200 quality receipt `root-quality-r1093.json` SHA-256 `92e9a7d1c864042e55b0b47a192a147e488ed8dc362ac72880a319484f0b4921` reports all 20 configured quality commands passing. Runtime pytest/native replay remains **UNRUN** and belongs to the source-frozen composed wave. No closure is proposed; `closure_ids=[]`.
