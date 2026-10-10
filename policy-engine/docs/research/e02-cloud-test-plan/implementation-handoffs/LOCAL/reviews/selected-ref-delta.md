# Independent review: selected-reference structural delta

## Result and boundary

The selected-view structural repair passes this scoped independent review. The previously observed failure class—flattening a typed selected reference to an artifact ID/default manifest while forming a generic projection or lineage edge—has been addressed structurally in the reviewed mechanism. I found no blocking escape in the bounded source and consumer paths below.

This is not G acceptance, a formal finding adjudication, or a complete E02/source-composition replay. At review time the candidate branch was `codex/e02-unified-local-20261009`, HEAD `077a572ff5880b3f50a85d3e3db6a232d277659a`, HEAD tree `2895b6c7597215b714275cb4ba83a504724dc89c`, parent `b2cd1fbb0c9aaa21a05cbf999330a2e07fe81f23`. The selected-ref delta remained an uncommitted worktree change; the broader candidate tree also contained unrelated in-progress changes. Consequently the reviewed object is identified by these exact path hashes, not by a purported final source commit or full composed-tree SHA.

The seven changed paths reviewed:

- `policy-engine/src/polisyos/core/artifacts/__init__.py` @ `5d747e378034f5e03d14308c1c95f978e417b86969db448f40034fe54821752f`
- `policy-engine/src/polisyos/core/contracts/__init__.py` @ `0657d75eb8c5b5568e730b40097a5bb9a59b0e26828eadf1418dbcf2300ccfdd`
- `policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py` @ `6f49c9f8f387f7392d36f89c8710407793200004fbc1b3fe1b80fc74312d9386`
- `policy-engine/src/polisyos/ir/analytics/posterior_summary.py` @ `c0a4dfc20b899431a11149cbe87d482fadbcaaad71520bbaaf1938e41995757d`
- `policy-engine/src/polisyos/runtime/quality/derived_observations.py` @ `2f59134a9cf3ce9def723e32625e6ff3f6f49bfaa2abc3f3a942735752653e71`
- `policy-engine/tests/unit/runtime/quality/test_derived_observations.py` @ `88a0d458d858cdefa4487a4b738dcb35662dd3118976672e3d983ecd29a8a318`
- `policy-engine/tests/unit/scientist/compute/test_runner_posterior_summary.py` @ `1162eca16a4aeaa8612dad1622f99c79c8ccd29a7a574c29e529c8fb4b71ebfc`

## Property reviewed

A selected CAS view is identified by artifact content ID plus its manifest-profile selector. When two sidecars name the same bytes but different authority/lineage, admission, recipe identity, emitted artifacts, certificate lineage, and fresh consumers must preserve the exact sidecar. Missing, malformed, stale, or contract-incompatible selected views must refuse. Profileless legacy artifacts retain their prior wire shape and default-view behavior.

The implementation now carries `manifest_profile_sha256` in the generic `ArtifactContractProjection` and `ArtifactInputEdge`, sorts graph identity including the profile, and chooses the selected-view wire version only when a selector is present. `_projection_ref` reconstructs the complete typed reference; `_manifest_projection` reads that exact selected manifest and includes its selected input edges. Recipe input edges, derived-output edges, certificate input edges, certified output references, and epoch recompute receipts retain the selector. Cache verification compares the exact selected view and bytes. Profileless v2/v1 payloads continue omitting optional selector fields, with explicit legacy-version mismatch tests.

The actual producer/consumer route is exercised: a selected source series is admitted into the recipe, persisted, materialized into a derived artifact, bound into its certificate, reopened through a fresh CAS reader, and consumed with the selected lineage intact. The posterior-summary bridge similarly converts the Core reference to the IR model while retaining the profile, persists it as the `method_evidence` input, and reads it back. The Core façade exposes the expected-manifest helper; the contract façade expands chronology exports and includes the referenced symbols. Existing Core→IR adapters and IR artifact contracts remained at the following reviewed hashes: `ir_adapter.py` @ `9ccaa1b3e09b550d9544f18ef9963ea9c7e06e173d4b57796c8211c0776d18c9`, `protocol.py` @ `48142e837245c6504b0333f7ce3900201fa4608b1693b3ed64afe8c0985a77b2`, `ir/artifacts/io.py` @ `4a8afac8c428e1582fc91a73070bd8e069cdd7f2ddcb309ee24d90f5dcf68765`, and `ir/artifacts/contracts.py` @ `cbf80d6244622519c2b5b7ac9c3bf18c87fc2372bf2e028fc3f67fe5b17e7b66`.

The preserved G-only Catalog resource is unchanged: the local file SHA-256 is `6c36ffce957ade642ba1cc1dab2367c2620dd7c75d0219520c64b3eec94bf0a6`; its Git blob is `0867804c64b5468bff7025a5208574b2390b90ad`, matching the protected G source blob.

## P40 classification and residual scan

**Bucket: SAME class, one level deeper.** The follow-up escape was the same selected-reference identity loss class: a typed ref crossed the generic projection but its profile was omitted, allowing the same content ID/default sidecar to stand in for a different authority view. This delta widens the shared projection/edge and emitted-lineage mechanism to carry the quantity the property requires; it is not a per-site denial list. The adversarial same-ID/different-authority-parent case now refuses with `input_artifact_drift`. Removing the selector from runtime projection reconstruction while leaving the recipe's selector marker intact also refuses. I found no second distinct class that calls for another repair round in this scoped path.

I also ran the existing source census over the complete `src/polisyos/**/*.py` file set: 2,710 Python files, zero parse errors, and ten direct `.artifact_id` selector calls. This is a source census, not a complete semantic proof of every dynamic consumer. Manual classification of its ten calls found no selected-view escape:
- the two cache-store ID lookups are in the profileless branch; profile-bearing inputs use exact `has_manifest_view` checks;
- chronology verification checks the supplied blob and exact raw manifest bytes, so the ID is a content-binding input rather than a default-sidecar lookup;
- the constraint snapshot read is for a just-persisted snapshot;
- foundry input resolution branches to exact profile resolution and reconstructs the full reference;
- scientist-node traversal uses exact profile resolution and a visited key containing both artifact ID and profile;
- backtesting passes the selected typed ref to byte retrieval;
- identifiability and derived-observation resolution branch on profile and reconstruct the full typed reference;
- posterior-summary loading branches to exact profile resolution.

The census script itself is `LOCAL/shared-refs/selected_ref_census.py` @ `bd74be280926f11c8c1791d3bca6dcd49d98ccf10cb5334e3cbd45255ec99013`. Because this scanner does not model all dynamic call forms, its result does not establish a repository-wide zero denominator. The wider API/dashboard integration and canonical finding-ID joins remain subject to the composed freeze and their own review.

## Verification and retained deciding output

The source-bound focused pytest run used the candidate `policy-engine/.venv` interpreter with `PYTHONPATH=src:.`; the runner printed module origins under this candidate for `polisyos`, the Core adapter, posterior summary, derived observations, and uncertainty adapter. Pytest args were:

```
-q
tests/unit/runtime/quality/test_derived_observations.py
tests/unit/core/artifacts/test_ir_adapter.py
tests/unit/ir/analytics/test_posterior_summary.py
tests/unit/scientist/compute/test_runner_posterior_summary.py
```

Result: exit 0, all tests passed, no skips; only pytest plugin rewrite warnings. Full output: `LOCAL/reviews/raw/selected-ref-delta-tests.log` @ `853c25786d41ccd695881c8b0e79f51a1fe36bf62d5b1626bb66f4b3593598e5`.

The exact Core façade checks were run from `policy-engine`:

```
PYTHONPATH=src .venv/bin/pytest -q tests/unit/core/artifacts/test_manifest_serialization_schema.py tests/unit/core/contracts/test_ir_ref_facades.py
```

Result: exit 0, ten tests passed. Output: `LOCAL/reviews/raw/selected-ref-core-facades-tests.log` @ `7040371af15613c02e821ec0eecc1d1330f691ace4cef93a41bfa358822c4103`. A separate facade-only run also passed (three tests): `LOCAL/reviews/raw/selected-ref-facade-tests.log` @ `cf426ab35f3b06fccef8290fde5325d90af130a79da1d1752031518df77c4236`.

The same-ID parent falsifier used real temporary CAS fixtures from `_case_inputs`: it retained the source payload and content ID while replacing its selected manifest's authority parent with another existing fixture artifact. The selected profile differed and `build_derivation_recipe` refused it with `input_artifact_drift`; the rerun exited 0. Output: `LOCAL/reviews/raw/selected-ref-delta-reproduced-parent-falsifier.log` @ `bfa40189ed18f4984ad7148fcd06e0b7cedb8347cbc7f32f4348f0aaf78a8234`.

The removal control monkeypatched only `_projection_ref` to drop the selected profile while leaving the recipe selector marker present. Materialization refused with `input_artifact_drift`; the control exited 0. Output: `LOCAL/reviews/raw/selected-ref-delta-reproduced-removal-control.log` @ `1bf972139e557ca3d52ff55eeab32e04bfe059b627cddab99465442b3aa66b56`. Earlier independent CAS and removal-control outputs are retained as `LOCAL/reviews/raw/selected-ref-delta-cas-probe.log` @ `5d8a15b2c0d484c40420afd463a09949fb81e497baf3f85619249d14c900bbbc` and `LOCAL/reviews/raw/selected-ref-delta-removal-control.log` @ `b9c312a2d9345c81e0e705db8e654c6846f2064c3bb17f1a672a3662336fb280`.

Canonical Ruff was run from the repository root, as required by `workspace_root.toml`, with the candidate product interpreter:

```
policy-engine/.venv/bin/python -m ruff check --config policy-engine/architecture/tooling/ruff/workspace_root.toml \
  policy-engine/src/polisyos/core/artifacts/__init__.py \
  policy-engine/src/polisyos/core/contracts/__init__.py \
  policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py \
  policy-engine/src/polisyos/ir/analytics/posterior_summary.py \
  policy-engine/src/polisyos/runtime/quality/derived_observations.py \
  policy-engine/tests/unit/runtime/quality/test_derived_observations.py \
  policy-engine/tests/unit/scientist/compute/test_runner_posterior_summary.py
```

Result: exit 0, `All checks passed!`; full output `LOCAL/reviews/raw/selected-ref-ruff-check-canonical-root.log` @ `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`. The earlier 246-diagnostic attempt used the product-root cwd and workspace-root config/path combination incorrectly. It is classified `TOOLING_NONRECEIPT` under P41, not a product failure and not inherited; its output is retained at `LOCAL/reviews/raw/selected-ref-ruff-check.log` @ `35a02dfba04154ff036c678affc6ef328c9b76998a6971ac2ba1938b40e0d3d7`.

`git diff --check 077a572ff5880b3f50a85d3e3db6a232d277659a -- policy-engine/src/polisyos/core/artifacts/__init__.py policy-engine/src/polisyos/core/contracts/__init__.py policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py policy-engine/src/polisyos/ir/analytics/posterior_summary.py policy-engine/src/polisyos/runtime/quality/derived_observations.py policy-engine/tests/unit/runtime/quality/test_derived_observations.py policy-engine/tests/unit/scientist/compute/test_runner_posterior_summary.py` returned exit 0 with empty output.

Census output: `LOCAL/reviews/raw/selected-ref-delta-census.log` @ `9531f52e22a7ac3daf1406e83414463206fca24b53a2fa724ea702f6a6b62601`.

## Review disposition

- Scoped implementation review: pass for the selected-ref projection, producer-to-CAS lineage, fresh-reader consumer, and posterior-summary bridge at the listed path hashes.
- P40: SAME class, structurally widened; the falsifier and property-removal control are negative.
- Formal G closure IDs: none. This packet proposes no formal closure and makes no authority/currentness claim.
- Remaining: attach the reviewed path hashes to the eventual committed source freeze; review the exact composed source and full required replay; complete integration/API/dashboard and canonical occurrence joins; G independently adjudicates any closure proposals.



## Immutable source-commit component confirmation

After the review packet was initially completed, root supplied the immutable source commit. I independently read each selected-ref path from Git object 24f3b72dd6eaa77cb7493d0880fe181e79181d75 and SHA-256 hashed the returned bytes. All seven hashes match the reviewed values above. The candidate is commit 24f3b72dd6eaa77cb7493d0880fe181e79181d75, tree 421ee2bc4f24083777516c414975a7f899f91648, sole parent 077a572ff5880b3f50a85d3e3db6a232d277659a. git diff --quiet 24f3b72dd6eaa77cb7493d0880fe181e79181d75 -- policy-engine/src/polisyos/core/artifacts/__init__.py policy-engine/src/polisyos/core/contracts/__init__.py policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py policy-engine/src/polisyos/ir/analytics/posterior_summary.py policy-engine/src/polisyos/runtime/quality/derived_observations.py policy-engine/tests/unit/runtime/quality/test_derived_observations.py policy-engine/tests/unit/scientist/compute/test_runner_posterior_summary.py also returned exit 0, confirming the current worktree copies match the committed files.

| Committed path | SHA-256 | Result |
| --- | --- | --- |
| policy-engine/src/polisyos/core/artifacts/__init__.py | 5d747e378034f5e03d14308c1c95f978e417b86969db448f40034fe54821752f | MATCH |
| policy-engine/src/polisyos/core/contracts/__init__.py | 0657d75eb8c5b5568e730b40097a5bb9a59b0e26828eadf1418dbcf2300ccfdd | MATCH |
| policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py | 6f49c9f8f387f7392d36f89c8710407793200004fbc1b3fe1b80fc74312d9386 | MATCH |
| policy-engine/src/polisyos/ir/analytics/posterior_summary.py | c0a4dfc20b899431a11149cbe87d482fadbcaaad71520bbaaf1938e41995757d | MATCH |
| policy-engine/src/polisyos/runtime/quality/derived_observations.py | 2f59134a9cf3ce9def723e32625e6ff3f6f49bfaa2abc3f3a942735752653e71 | MATCH |
| policy-engine/tests/unit/runtime/quality/test_derived_observations.py | 88a0d458d858cdefa4487a4b738dcb35662dd3118976672e3d983ecd29a8a318 | MATCH |
| policy-engine/tests/unit/scientist/compute/test_runner_posterior_summary.py | 1162eca16a4aeaa8612dad1622f99c79c8ccd29a7a574c29e529c8fb4b71ebfc | MATCH |

The root-authored source-boundary manifest is LOCAL/raw/blocking-batch-source-boundary/attempt1/source-commit.json @ f1b1314057a0e43d1dcd9d35c113e101f8b5b2fcc51918f70cd2ff29cc024bb8. It records the wider 132-path source boundary; this component confirmation does not adjudicate or accept that whole boundary. Root reports its native pre-commit gate passed in 28.7 seconds; I did not rerun that broader gate. This exact commit association does not change the scope of this review, and formal G closure IDs remain empty.
