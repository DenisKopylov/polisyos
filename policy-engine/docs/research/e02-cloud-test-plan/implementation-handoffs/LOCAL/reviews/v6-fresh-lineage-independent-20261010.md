# Independent review: V6 fresh lineage test patch

## Scope and evidence

Read-only review of the unapplied one-file patch `LOCAL/decisions/v6-c05-fresh-lineage-patch-00954ff.patch`, SHA-256 `29eec9e4f7851eea35a57c98f39fdf97247c7b06d0c2d3b51a6952cd7e9e02d9`. Target `tests/unit/runtime/http/test_control_service_di.py` remains at the supplied base SHA-256 `a350618bae4942c3e2184ad6b801b0180f7ac05a84495072649dbc2c3b90faed`. I did not apply the patch or run tests.

I read the patch-preparation note and `LOCAL/decisions/v6-final-producer-engineering-20261010.md`. The latter correctly limits this fixture to a controlled CYC02 N4/N5 producer path and does not infer an authentic L01/L02 or RES-03 selected-source positive.

## Contract and lineage review

All asserted response fields exist in the current typed contract: `RunCandidateSimulationN5Observation` carries the three refs, profile config/selection refs, `lineage_status`, `lineage_limitation_code`, and literal `currentness_status="not_established"`; `RunCandidateSimulationProjection` carries the N4 source/profile statuses; `RunRecursiveCycleCheckpoint.publication_authority` is literal false. The JSON key comparisons are therefore against current typed response fields, not guessed names.

The fresh route has a substantive lineage path behind `lineage_status="resolved"`. It reads the selected N5 input from CAS, checks payload and manifest tenant/cell plus run/job identifiers, resolves the typed V5 input through `GenerationSourceRepository.resolve_candidate_simulation_v5`, and compares its N4 source, context job, profile config, and profile-selection references with the persisted N5 observation. For the successful child node it also requires the compiled N4 source status and child profile binding to be resolved and checks the child handoff's context, profile content, model declaration, NCM, and root run/job binding. Errors remain a typed `not_established` lineage projection. This is a source-bound consumer check, not a marker-only assertion.

The patch compares each served observation's exact N4 source, context-job, N5-input, profile-config, and profile-selection refs with `successful_simulation` from the fixture's `compiled_payload`. The fixture obtains those bytes from the completed producer's persisted `runtime.compiled_recursive_generation_cycle` artifact; it is not a fabricated response label. It then requires `lineage_status="resolved"`, no lineage limitation, `currentness_status="not_established"`, and resolved root-source and child-profile statuses. The existing sibling failure checkpoint and the later corrupted-N5 fresh GET remain unchanged; the new checkpoint assertion explicitly preserves `publication_authority is False`.

## Bounded interpretation / P40

This is the same producer → persisted artifact → fresh consumer class, one level deeper: it binds the returned lineage tuple to the actual successful producer branch that survived the sibling failure. The receiver quantity is one N5 observation in this fixture and is already asserted (`len(...) == 1`); the exact ref/profile checks therefore cover the only returned observation. There is no self-label used as authority.

The selected source recording, candidate profile, model declaration, tenant, and cell are controlled fixture inputs. `lineage_status="resolved"` proves the typed historical producer-to-input join for this run; it does not prove external source currentness, an authentic V1/L02 catalog profile, or publication authority. The patch preserves that distinction with explicit currentness and publication fields. No missing reentry-profile or production-profile claim should be inferred from this test.

## Disposition

The patch is structurally sound as a test-only companion for the controlled CYC02 fresh-read lineage property. It uses available typed fields and exercises the existing CAS-backed lineage resolver, while retaining the corruption refusal and failed-sibling checkpoint controls. It is not evidence that the selector passed, and it does not close the separately unestablished authentic RES-03/V1 input/profile path.
