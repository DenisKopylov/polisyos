# Independent review: current-source companion plan v3

**Disposition:** GO as a reviewable pre-freeze plan delta, with the recorded manifest and ENV-admission steps still pending. This is not a source-freeze approval, execution receipt, capability closure, or G finding. Review was read-only except for this note; I did not run tests or apply the patch.

## Exact inputs and candidate identities

- Worktree read: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`.
- Unified patch SHA-256: `8e46205f40ff9bb291c6c2170408781a01e49fbeafb4796ab93c7e32fd5a7b51`.
- Plan note SHA-256: `344ea1fc40cc1ccee26fba7971723b3deebbbef9e40f8ecc6a8d8a8b0b958752`.
- Primary input `composed-mac-final-replay-plan-20261010-r2.json`: `863203a3a71f37d29b2f564c9e80986a61c875149943f6e2a3bcf893cfdb893c`; applying the patch in memory and parsing the candidate JSON yields `ceff2fd9dc3f8706117e86f63a05ffc1e945958174717e4279ca65ecc8e58ed4`.
- Supplement input `composed-mac-final-supplement-plan-20261010-r2.json`: `c74a05534834468fd6aeb2efb996e7ba5b3fdc9898affa73ce0e403fc0934004` (unchanged).
- External plan input `composed-mac-tool-external-consumers-plan-20261010-r2.json`: `df9ce854ac25ec01dff6c7ca0d1d2e52e0caf3c8a7ac5236dba2dca3b4f2e747`; the patched candidate parses to `aafb4ef91bc5096e30af2a09d71b4dcbe62527a5695ff9c0e9e741ff8c2e7c8c`.

The in-memory patch application matched every removed/context line; no candidate bytes were written. The primary remains `plan_only_candidate_source_final_freeze_pending`, and both final commit and tree are null. The old `00954ff…` source label is explicitly historical, not a final identity.

## Review evidence

The candidate preserves the 19-command primary queue, 11-command supplement, and seven external output-binding routes. All are `UNRUN`; the primary is sequential with one numerical thread and no heavy run authorized. The external plan records zero commands/tests/assets executed and no browser, Docker, or Linux transport. I found no closure IDs in the primary plan.

The candidate primary has 244 unique declared direct `source_input_paths` and 68 selected test paths. All 244 direct paths exist in this checkout. The external plan has 47 unique direct route inputs, also all present. These are declared direct inputs, not a transitive import closure; the plan states that boundary. The supplement remains 11 routes, with its static selector report still explicitly requiring final-source AST/collection and execution after freeze.

The register arithmetic is represented correctly: Q0’s assigned slice is 206 finding IDs, while the whole register denominator remains 282 findings and 291 criterion occurrences. The text treats Q0 as route membership and does not convert it into closure.

The V1/V2 GET target now names the existing `test_fresh_run_details_get_keeps_local_n5_and_sibling_failure_checkpoint`. Its body/docstring describes a local synthetic checkpoint witness, not the source-derived root-client L2-to-N4 chain. The candidate explicitly holds that V6 positive as unrun because the source L2/profile input is unavailable. Command 9 selects the two whole acquisition-world-growth modules plus the whole `test_acquisition_route_loop.py` module and the served acquisition test. The route-loop module contains a persisted-v5 case that expects `compiled_run_invalid`; the module selection is appropriate for the stated unsupported-schema refusal check. These source checks establish selector existence and bounded scope only, not runtime PASS.

For the seven external routes, candidate output maps and `output_root_ownership` agree: there are seven unique roots, each a strict descendant of the declared external output root, with no path escape or overlap found. The revised `per_command_capture.required_files` values are role references (`outputs.stdout`, `outputs.stderr`, `outputs.metadata`); each role exists in every command’s `outputs` map. This is a plan-level mapping check only; no external route has executed.

The ENV route’s planned command binds the repo-root invocation, a root-produced `baseline-observation.json`, focused capture files under `capture/` (`stdout.txt`, `stderr.txt`, `command.json`), and a strict `harness/` output child. Its broad output root is recursively inventoried. The note correctly says this is binding-only and blocked pending the source-owner admission bridge. Current `environment_v2_falsifiers.py` still requires `--output-parent` to equal the existing `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw` directory (`environment_v2_falsifiers.py:794–799`); it will reject the proposed `.../environment-v2-falsifiers/harness` child. The plan does not present the proposed command as runnable on current source or claim an ENV result.

There is also a manifest construction step before any freeze: `composed_mac_capture.create_raw_source_manifest()` builds output bindings from the explicitly supplied `additional_plan_paths` (`composed_mac_capture.py:1260–1310`). The current CLI’s `--supplement-plan` path normalizes only the 11-command supplement (`composed_mac_capture.py:4189–4260`); the primary plan’s `route_inventory.current_final_command_plans` is not itself an admission input to that API. Root has selected the existing explicit API path for the six-plan manifest. Before using the shared manifest, the root receipt must therefore show the exact six plans passed, including this external plan, and verify all six `plan_output_bindings` and their output roots. This is a known execution precondition, not a request to infer routes from descriptive inventory or add new semantics.

## P40 classification and remaining boundary

**SAME_CLASS_DEEPER — explicit plan/output binding.** The external plan’s listing in `route_inventory` is descriptive; the actual manifest boundary remains explicit `additional_plan_paths`. The already-selected six-plan API call addresses this quantity at the correct boundary. Do not count it closed until the generated manifest proves the six bindings and roots. The ENV child remains separately held until its source owner closes manifest-derived strict-child admission. No new per-route patch is indicated by this review.

The direct-path checks, nodeid/source inspection, and JSON checks above are static. I did not perform pytest collection, execution, native gates, external consumers, a source freeze, or a production/currentness check. Any later source delta invalidates affected plan hashes and requires re-binding; formal criterion adjudication remains with G.
