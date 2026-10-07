# Owner action: authentic L6 inputs for the served CYC-01 witness

**State:** input unresolved; the production-backed ordinary served check is **UNRUN**, not FAIL.  
**Scope:** CYC-01 / B01–B03 only. This packet does not make production data a blanket prerequisite for unrelated findings or for generic N5/N8 checks on appropriate bounded inputs.

## Request to the source-data custodian

Please provide either:

1. Read-only original bytes for the two intervention-bundle files below that match the currently declared SHA-256 and sizes; or
2. An owner-ratified update for the changed bytes: a revised `FINAL_ARTIFACTS_MANIFEST.json`, the matching `manifest.json` checksum binding that revised nested manifest, and provenance naming the custodian, source artifact/version, revision or change time, and the reason these bytes are authoritative.

The custodian should return a manifest-valid bundle for the complete declared input set. Do not edit production data or either manifest locally, and do not replace these files with test fixtures. The current bundle README says the files were assembled via hardlinks from server artifacts; the nested manifest points to `/srv/polisyos/ukraine-data/final_artifacts_20260410T0916`. Neither reference names the present custodian.

## Pinned manifest and input denominator

The read-only production root is `/Users/deniskopylov/polisyos/policy-engine/production_data`. Its `manifest.json` is 5,434 bytes with SHA-256 `9e0e0aa0acd3c91f0120a80a2570be358ff16a63218abcd998f4d6f0212b6105`. It declares the `ukraine_simulation` bundle as version `ukraine_agent_simulation_baseline_20260410`, readiness `ready`, with bundle path `ukraine_agent_simulation_baseline_20260410`.

That root entry’s complete `required_files` array has five paths, relative to the bundle root:

- `FINAL_ARTIFACTS_MANIFEST.json`
- `production_bundle/bundles/runtime_bundle_v1/runtime_bundle_manifest.json`
- `production_bundle/bundles/intervention_bundle_v1/intervention_knob_dictionary.json`
- `production_bundle/bundles/calibration_bundle_v1/calibration_bundle_manifest.json`
- `production_bundle/bundles/method_contract_bundle_v1/network_contract_bundle_v1.json`

The root entry binds `FINAL_ARTIFACTS_MANIFEST.json` to `sha256:e65ca699c56b203097c5dc11d99fd171a337e89ee888132ce82e36557d87992d`. The actual 8,488-byte nested manifest has that same SHA-256. It declares 40 members in its `files` array. This census independently hashed the five root-required files and the two additional profile-relevant members listed below; it did not rehash the other 34 nested members, so it does not claim full 40-member validation.

All paths in the table are relative to the bundle root above. Full hashes are shown so the source owner can resolve the exact bytes.

| Input | Manifest-declared size / SHA-256 | Current size / SHA-256 | Check |
|---|---:|---:|---|
| `FINAL_ARTIFACTS_MANIFEST.json` (root checksum binding) | size not declared / `e65ca699c56b203097c5dc11d99fd171a337e89ee888132ce82e36557d87992d` | 8,488 / `e65ca699c56b203097c5dc11d99fd171a337e89ee888132ce82e36557d87992d` | Hash match |
| `production_bundle/bundles/runtime_bundle_v1/runtime_bundle_manifest.json` | 3,857 / `2da4c9524e6d5de8aadd3d9ef6b6264628ede650d5f1ba9d6e9d159cb9f326b0` | 3,857 / `2da4c9524e6d5de8aadd3d9ef6b6264628ede650d5f1ba9d6e9d159cb9f326b0` | Match |
| `production_bundle/bundles/intervention_bundle_v1/intervention_knob_dictionary.json` | 268 / `4f52f0a743a46f5c53cf5608cc73b1b05f0e8d7f8ee360d866e6f127863a840f` | 581 / `005d89f0ab1728a4f6c20cccad5781c1ef7721f82215c8de7c21622f3abe4328` | **Mismatch** |
| `production_bundle/bundles/calibration_bundle_v1/calibration_bundle_manifest.json` | 11,579 / `1f895e18a44643b1bda5fbc42fafd7c613473b0eae242f477a7b285872e67e54` | 11,579 / `1f895e18a44643b1bda5fbc42fafd7c613473b0eae242f477a7b285872e67e54` | Match |
| `production_bundle/bundles/method_contract_bundle_v1/network_contract_bundle_v1.json` | 148 / `627b096637515d427a08f3f552c35c79a93380fe22668c4d5e1c04f42fbce187` | 148 / `627b096637515d427a08f3f552c35c79a93380fe22668c4d5e1c04f42fbce187` | Match |
| `production_bundle/bundles/intervention_bundle_v1/lex_intervention_map.json` (additional intervention-profile member) | 178 / `49168c4779a0d1025c166f7eea04477efdd27fb3a3b7554ae7878da45af7fbaa` | 972 / `5c72461237a09605c39f180345de45cff55c59eed5d4d0e2ca80cc4aa446addf` | **Mismatch** |
| `production_bundle/bundles/method_contract_bundle_v1/observation_to_contract_manifest.json` (additional method-contract member) | 3,021 / `6d565e724d4caf89841499ba31df47d0a8c0dcc800689ea159cfab608d4b382b` | 3,021 / `6d565e724d4caf89841499ba31df47d0a8c0dcc800689ea159cfab608d4b382b` | Match |

The root-to-nested manifest binding is internally consistent, but it does not attest that the two current file contents are authorized. The root manifest exposes no owner/signature field; its digest identifies the snapshot bytes, not who authorized them. The route resolves the Ukraine bundle directories from the production root (`src/polisyos/runtime/http/services/control/production_data.py@9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7:296–342`).

## Owner and evidence boundary

The G-pinned E02 records reviewed for this request are at `9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7` / tree `f27a36aa7eae9d6e329e0602ea40b6169a5bcf35`:

- Original B01–B03 criteria: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7#L205-L239`.
- Current A labels: `policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/A.md@9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7#L39-L40` (B01/B03 `producer_missing`; B02 `verification_missing`).
- Exact input mismatch and route disposition: `policy-engine/docs/research/e02-cloud-test-plan/integration/checks/2026-10-06-seventh-wave/reviews/2100-A-delivery-remaining-work.md@9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7#L51`.
- The 2026-10-07 continuation asks for authentic read-only bytes or an owner-authorized updated manifest before the ordinary POST→context→DesignProblem→N5→CAS→fresh GET witness: `policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/continuation-2026-10-07/A.md@9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7`.

The owner map assigns CYC-01 to A/A-W01, but does not name a custodian for these production bytes (`execution-organization/bundle-owners.tsv@9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7`). The 2100 receipt says “owner of data” without identifying one. C’s UDF-04/C-W18 allocation concerns the Ukraine workspace-root/server gate; no reviewed C handoff names it as L6 source custodian. **Source custodian: not named; coordination must appoint or identify the actual data owner before treating a replacement manifest as authoritative.**

Tracked exact-hash references do not supply the original bytes or owner approval. At G, the expected digests `4f52f0a743a46f5c53cf5608cc73b1b05f0e8d7f8ee360d866e6f127863a840f` and `49168c4779a0d1025c166f7eea04477efdd27fb3a3b7554ae7878da45af7fbaa` do not occur in tracked `policy-engine` files. The current knob digest is recorded in `policy-engine/docs/superpowers/journals/corr-evidence/a-expansion/2026-09-09-declaration.json@9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7`, `policy-engine/docs/superpowers/journals/corr-evidence/a-expansion/input-census.json@9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7`, `policy-engine/docs/superpowers/journals/corr-evidence/a-expansion/declaration-producer.json@9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7`, `policy-engine/docs/superpowers/journals/corr-evidence/b/baseline-corrected.json@9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7`, and `policy-engine/docs/superpowers/journals/corr-evidence/b/baseline-final.json@9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7`; the current map digest is recorded in the last two baseline files. The declaration marks itself `synthetic: true` and accepted binding correctness `not_established`; its input census is `pre_outcome_construction_support_only` and says runtime refusal is not established. These are experiment/hash records, not custody receipts.

The G tree’s only tracked files with these exact basenames are test inputs under `policy-engine/tests/_data/lex/c6a/`: the knob file is 324 bytes with SHA-256 `bf217f4f622e89f95ec2d497343f29575e81fd21c9d088ad2a07a19f98c032d4`; the map is 730 bytes with SHA-256 `172ff33c6e93e6dbb9d0f7599cfcc22baeb90f0feb9f6f2a7630184fbdf7f4e1`. They are not production inputs. The all-ref path history contains no tracked versions of the two production-data paths; a reachable-object scan at G found 13 blobs of the two expected sizes and zero matching expected SHA-256 values.

This packet records an input gap, not a route failure. After the custodian supplies a valid input set, A can run the exact ordinary served witness and its foreign-context, denied-right, unknown-outcome, stale-lineage, and tampered-CAS controls on the frozen candidate. No production file or manifest was changed for this packet; no product test or numerical run is claimed here.
