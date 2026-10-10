# V3 actual served route: zero cost-bearing requirements

## Finding and boundary

At source HEAD `9194a65fb59355ceac35270c869f429efc7482d8`, the remaining served-route failure is upstream of the strict resolver. The retained real `natural_language_run` completed, produced a schema-v4 `CompiledRecursiveGenerationCycleRun`, and passed typed recursive DTO parsing. Its single leaf cycle contains **zero** pairs of `acquisition_routing_report` plus `acquisition_cost_basis_record`. `AcquisitionRouteLoop.resolve_current_route()` correctly requires exactly one such pair and raises `costed_route_not_unique` at `src/polisyos/runtime/quality/acquisition_route_loop.py:405-414` (`de5b496862a76c60056bb4509df82d3f9be3bb75eacc46b079718edcaa0e8deb`). This is a producer/bridge gap, not evidence that route selection or persisted-reference validation should be relaxed.

The captured 24-case run predates the root's subsequent foreign-CAS-view fix: 19 passed, 5 failed, exit 1, wall 171.735889 s. Four failures were the same helper-view `.close()` issue, which root reports fixed. I did not rerun after that fix. The remaining route boundary is independently confirmed from the actual persisted job below; no post-fix whole-suite result is claimed.

## Actual artifact evidence

The selecting read-only command found one completed `natural_language_run` for run `R_50bc5a265851c954`, job `d29e0cb9da68435fb810861ff255a19a`. Its selected ref is `sha256:09093b9d0da2f5450cf5f076fb3bfef6eab38ce1b6c3f90c19ccaf9373a5d0d9`, kind `runtime.compiled_recursive_generation_cycle`, schema `polisyos.runtime.CompiledRecursiveGenerationCycleRun` v1.0. The exact artifact is 34,817 bytes and its content hash matches its artifact ID.

The selected cycle records:

- `grounding.status=grounding_unavailable`, `grounding_source=grounding_unavailable`, issue `cgf_disposition_missing`, and no `acquisition_requirement`;
- `terminal_kind=a_spec_gap` and `revision_strategy=spec_gap_reframe`, with no `revision.acquisition_request`;
- `value_port.status=value_pending_n8`, blocker/reason `candidate_scenario_n5_only`, and no value-port `acquisition_requirement`;
- null routing report, null cost basis, and `ROUTE_COSTED_PAIR_COUNT 0`.

The compiled problem is fiscal, with candidate lever target `government.balance` and outcome target `global.tax_rate`. Its one evidence need is generic `effect_grounding` (“What is the grounded effect?”), with `artifact_ref=null` and `source_hint=null`. Its `runtime_hints` are empty: there are no N7 data-requirement specs, required-data-family declarations, or world snapshot. The artifact carries a selected candidate-simulation profile/context, but the recursive-source status is `generation_unavailable`; neither fact is an acquisition route or a cost basis.

The fixture's `install_fixture_wdi_cost_basis()` only installs a hypothetical costing-table row for `government.balance` (one synthetic expert hour). It does not invoke N7, create a typed request, or emit route/cost records. The same-variable string in that costing fixture is therefore not evidence that the actual producer requested that distribution.

## Source-level discriminator

Current `generation_cycle.py` (`327825cd2cfffac7578b4dc36792c06bb6b672027b0d8f5d6e84732d589ea3dc`) runs N7 only when a cycle is `ACQUISITION_REQUIRED` and its revision contains a typed mapping `acquisition_request`; planning then validates its `requirement_gap` (`_run_n7_acquisition_if_requested`, lines 6419-6454; `_plan_n7_requirement_gap_if_requested`, 6456-6494). Costing requires one exact distribution from `metadata.availability.variable_id`, `missing_distribution:<id>`, or `canonical_variable_observations:<id>` (`_requirement_missing_distributions`, 1571-1589). The actual cycle has none of those inputs.

The grounding helper can construct a generic `grounding_coverage_requirement_gap` when candidate hash, problem ref, and authority are supplied (`_grounding_unavailable`, lines 12055-12095; `acquisition_planner.py` `8647081ab19e621bedc603bdb32beb4c9d1f7693b26a65cdaf9842b2063e650b`, lines 3709-3778). That gap identifies `grounding_relation_or_owner_lever:<candidate>`; it does not provide an exact missing distribution, so merely passing more context into that helper still cannot justify this costed route. A generic `effect_grounding` need likewise does not prove that `government.balance` is unavailable or that acquiring it grounds the candidate's effect.

## Patch decision and next discriminator

No source patch is prepared. A patch that copies `government.balance` from the synthetic cost fixture, turns a generic grounding need into availability, fabricates an `acquisition_request`, or accepts zero/multiple costed cycles would invent the missing semantic premise or weaken the existing fail-closed consumer. A valid patch must reuse an actual owner-backed source/availability result to derive one candidate-bound, typed requirement with an exact missing distribution and provenance, then let the existing N7 planner persist its report and revalidated cost basis into the real compiled cycle. If no such producer input exists on this POST route, a G-level contract decision is needed about how (or whether) the generic effect-grounding need becomes a variable-scoped data requirement; it is not established by this fixture.

The discriminating acceptance test must start at the actual served POST, demonstrate the producer's source/profile/subject binding, and read the persisted compiled artifact through the current resolver. Positive requires exactly one source-bound typed requirement, one N7 routing report, one schedule-revalidated cost basis, and one fresh route closure. Negative controls keep zero and multiple costed pairs fail-closed, and vary or corrupt the source/profile binding without marker-only success. The existing candidate-only N5 case must remain blocked rather than be promoted into a costed route.

P40 classification: **SAME_CLASS_DEEPER**. After the recursive-v4 DTO and scoped-CAS boundary fixes, this is the next escape in the same actual producer → typed artifact → N7 bridge → strict route consumer property. Widen the whole path once; do not patch the resolver or add per-field fixture shortcuts. Current route capability remains `producer_missing` for a cost-bearing typed requirement on this actual request; no closure claim is made.

## Retained deciding evidence

All paths below are relative to `policy-engine/` unless stated. Full streams and command metadata are retained; raw payload contents are not copied here.

- `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/v3-typed-compiled-whole-tenant-verification-20261010/command.json` (`bf057e9e5584b7c3ebc351abd28d69069b662717e89e82d6390eaf918d9c1d24`) records the exact pytest argv, source hashes, exit 1, and wall time. `stdout.txt` SHA `b8b9017210d354d4c5eb1a4e8d2d6ecf31cbbeedb12f75d4326e12b1dab955c2`; `stderr.txt` SHA `6213466a1fb90c818ae44510ed797318478307452638d2b99ba90ec5197a9226`; `junit.xml` SHA `1889d57763d11bb639978c7afd05562f60fd26a41aaca0596477a83f3695d527`.
- `.../LOCAL/raw/v3-costed-route-discriminator-20261010/command.json` (`7219876b775b3191faae48787029218481ae3ba122e414fc31b93771ead79185`) records argv `[.venv/bin/python, -B, -]`, the read-only SQLite selection rule, and exit 0. `stdout.txt` SHA `9de79414f6408d5766d67ec83d0c810e24039f3e2133714d8cf78fecc7ff228a`; stderr is empty.
- `.../LOCAL/raw/v3-costed-route-cycle-contract-20261010/command.json` (`51af679c046ff48edd9014be129d7b4025fa8ac1e491ef03a66f566e92fd4a5e`) records the exact artifact and bounded cycle-field reader; exit 0. `stdout.txt` SHA `831a5cae9f6ace6a09ffdd244146b6404ca380556426de609e9a82ea6decc5b3`; stderr is empty.
- `.../LOCAL/raw/v3-costed-route-intake-contract-20261010/command.json` (`ca57e487eb08d680f0f6538b7b4f696b61cb94369bda0d3a8bbfa96b3ae9ad80`) records the bounded problem/runtime-hint reader; exit 0. `stdout.txt` SHA `aa51e15904fc85bf837dd12523e1d7767a6a4af6bdf882ea1ffa500f331962da`; stderr is empty.
