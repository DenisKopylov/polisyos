# R1053 — independent review of R1027 whole Forecast ref boundary

**Verdict: GO to the focused native replay only.** This review supports composing the exact R1027 semantic change for the root-owned POST → persisted CAS/event → fresh GET replay. It does not establish runtime success, authority, a global source freeze, or formal closure (`closure_ids=[]`).

## Bound artifacts and current source

- Candidate patch: `LOCAL/raw/r1027-v7-whole-forecast-core-ir-ref-boundary-20261013/candidate.patch` @ `e319405f762f17cd2c24f130c6a174b7e343d377c823d0bbd50347ac13bdf889`.
- Candidate manifest: adjacent `manifest.json` @ `176e4789c81e17a381897ce09193a3dab4bb9b59055f5ff7fbf4c69f750e0db3`.
- Author decision: adjacent `decision.md` @ `39e5edc43653b6c582d3cf75a272a0a6a852adc221790d3661e37ec22e89cb95`.
- Refreshed root source frame: `LOCAL/root-author-source-frame-r1055-20261013.json` @ `dbb113c2a571de08e2cf89c0c9076f0cbe7e0f217964993101ad58c40cefff79`; HEAD `226cedb822e6e242d861ea8c903c9b396375dd0e`, tree `5db8751ff5f26d7c649906582c4f84bc4accdf9a`, source implementation HEAD `b5dd2956cdda5ee320b96428d1fdbcc05dda522f`. The earlier R1035 frame in the author manifest is superseded for current-source binding. R1055 records the announced root-owned advance; I independently confirmed both R1027 target files still match their current HEAD blobs and the source-implementation blobs.
- Product source target `policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py`: current/HEAD/source-implementation preimage SHA-256 `ab0c9c125124c4273ba0d696c912c7434d77e3b987480bab456dd38d753846da`, candidate postimage `287b41deae358f694726193191027a0db3b0c767d13f1eb624c58069ebf44437`.
- Test target `policy-engine/tests/unit/runtime/quality/design_axes/test_outcome_prediction.py`: current/HEAD/source-implementation preimage `fffb6b0438a34a95e0036065243ceae2fa038668638f21906874cd3302224194`, candidate postimage `1c8ef77916403cf57f30a622dc83ccb7a9cd10266dbf1a50d7fbd2a22064fa6a`.

R1055’s `physical_postimages` map does not contain these two unchanged paths, so I do not treat the frame alone as a per-file receipt. The direct file hashes, `git show HEAD:<path>`, and `git show b5dd2956cdda5ee320b96428d1fdbcc05dda522f:<path>` all independently match the manifest preimages. The patch was not applied.

## Property and source trace

The observed failure is a representation mismatch at `ForecastCalibrationRecord.empirical_evidence_ref`: the S10 path passes the selected Core `ArtifactRef` object into a field typed as IR `ArtifactRefModel`. R1024’s retained full run recorded POST/event persistence and wrong-run refusal succeeding, followed by fresh GET returning 400 with Pydantic’s `Input should be a valid dictionary or instance of ArtifactRefModel` error. That receipt is `LOCAL/v7-selected-evidence-post-event-fresh-get-deciding-r1024-20261013.json` @ `88a7fc5a24fcea54096a28f7d84e7793858782ac979adfda905bf15c1101aa07`; retained stdout @ `634bd40cbf217e9ae9ed2453bd3c9fa7d64dc82af0d8f2b368999104f1678357` and JUnit @ `2f2961eb072906c7741a5966c28b45f35491d270937fe7362e98e29425c319c4`. The run was 11 passed / 1 failed. Its completed-intent retry after the failing GET is explicitly unrun; this review does not upgrade it.

The source trace reaches the shared owner rather than one GET leaf:

- `generation_cycle._resolve_s10_empirical_evidence` returns the original selected `raw_ref` with its loaded projection after kind/media, method, rule-version, and temporal-role checks.
- `_build_s10_forecast_inputs` passes that same reference to `build_forecast_calibration_record`; the canonical builder validates with `ForecastCalibrationRecord.model_validate`.
- The class also owns mapping validation in `_as_calibration_record` and the persisted-value receipt path in `generation_cycle._value_calibration_receipt`. Source census in the candidate manifest identifies three source `ForecastCalibrationRecord.model_validate` occurrences and nine canonical-builder call sites. The service-level adapter already used by R1001 does not cover this nested record boundary, because recomputation passes the original association reference into the forecast owner.

R1027 adds a `mode="before"` validator that scans `cls.model_fields`, discovers direct or optional `ArtifactRefModel` annotations with `get_args`, and adapts only nested `BaseModel` values through the existing `normalize_artifact_ref`. The current `ForecastCalibrationRecord` declares exactly one direct optional reference member, `empirical_evidence_ref: ArtifactRefModel | None`; its `Layer2ReadinessModel` base contributes no reference fields. The scan includes inherited schema fields and does not hard-code the present member name, so it addresses the whole current schema-declared quantity and future direct/optional ref fields under the same contract.

The existing normalizer validates the source model’s declared public fields against the stable ref schema, refuses unknown fields, validates with `ArtifactRefModel`, and returns the identity fields that are present. A present manifest profile is carried through; an absent profile stays absent/`None`. The existing after-validator still enforces `ir.empirical_calibration_evidence` and `application/json`, along with calibration constraints and the prediction authority boundary. The patch does not fill a profile, re-resolve a manifest, promote authority, or change forecast posture. Existing loaders retain selected-profile, kind/media/schema, lineage, same-run, and evidence-recomputation checks.

## Tests and static evidence

The candidate unit test has two positive inputs (Core refs with a selected profile and with no profile) and compares all four identity values after canonical record construction. Its wrong-kind and wrong-media cases now use Core refs, exercising normalization before the retained strict validator. The preimage had tested those two bad profiles as mappings; R1027 replaces that representation in the unit negative control. Mapping inputs remain unmodified in the new before-validator and continue through ordinary strict Pydantic validation, but this unit no longer directly pins that unchanged mapping branch. This is a small coverage reduction, not a source-behavior escape; the focused native replay should retain the existing real producer/read controls.

Commands and direct results:

- `git apply --check --verbose --directory=policy-engine policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r1027-v7-whole-forecast-core-ir-ref-boundary-20261013/candidate.patch` from the worktree root: exit 0; checked both changed paths. No apply/write was performed.
- Read-only in-memory unified-diff reconstruction against the two current preimages: both exact preimage hashes and both manifest postimage hashes matched; both postimages parsed with `ast.parse`.
- On each preimage and candidate postimage, product-configured `.venv/bin/python -B -m ruff check --no-cache --output-format json --stdin-filename <relative-path> -`: exit 0, stdout `[]` (SHA-256 `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`), empty stderr.
- `ruff format --diff --no-cache --stdin-filename <relative-path> -`: the test pre/post both exit 0 with no diff. The source pre/post both exit 1 with the same two pre-existing formatting regions in `_prediction_authority_boundary_is_valid` and `_stable_token`; their hunk line numbers shift by the 27 inserted lines. There is no formatter diff in the new code, but the touched source file remains not formatter-clean as a whole. Root should include its canonical formatter companion if the aggregate source gate requires a clean file.
- Candidate pytest/runtime/import execution was not run in this review. R1024 is retained preimage evidence only, not a candidate pass.

## P37, P38, P40 classification

- **P37:** the member set is recomputed from the concrete model schema. Ref normalization and typed field validation are recomputed by the existing normalizer and Pydantic. The candidate’s four-value equality test is present but its execution is `not_established` here. The external artifact’s issuer, content authenticity, currentness, and calibration truth are not established by this representation bridge; the existing loader/consumer owns those predicates.
- **P38:** the property is preserving the selected Core reference’s complete typed identity across the DTO boundary. The implementation checks current schema declarations and converts using the existing stable ref normalizer; the observed divergent case is the preimage behavior, where a valid Core object fails while the IR mapping shape passes. No present direct/optional schema field divergence was found in the candidate. Nested collection or other annotation forms are outside the declared current contract and are not claimed.
- **P40:** `SAME_CLASS_DEEPER`. This is the second Core/IR reference-boundary escape. R1027 widens to the whole schema-declared direct/optional ref-member set in `ForecastCalibrationRecord` instead of patching another route. No additional same-class source escape was found in the present record schema. The mapping-negative test replacement and whole-file formatting state are recorded above, not treated as new runtime classes.

**Next acceptance signal:** root-owned focused native replay on the exact composed source, retaining POST selection, CAS/event persistence, wrong-run refusal, fresh GET, and exact completed-intent retry as separately reported outcomes. Until that run, no runtime pass or formal closure is claimed.
