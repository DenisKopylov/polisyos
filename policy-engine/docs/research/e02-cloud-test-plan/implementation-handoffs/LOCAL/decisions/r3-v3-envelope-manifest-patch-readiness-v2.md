# Corrected red-only patch readiness

This patch supersedes the earlier red-only patch at `raw/r3-v3-envelope-manifest-red-00954ff.patch`. The original assertion incorrectly assumed the first CAS view returned an explicit profile. In this fixture it is the default view and its returned ref is correctly profileless.

The corrected red case reads that persisted default manifest, computes its canonical Core manifest-profile digest, resolves it through `get_manifest_by_profile`, and constructs an explicit typed `ArtifactRef` from that verified readback. It then links the payload to the foreign-tenant profile. The envelope blob and schema remain identical; the selected manifest tenant context differs. The pre-fix strict reader is expected to accept the linked profile, making the `pytest.raises` assertion fail with DID NOT RAISE.

Patch SHA-256: `2f8b6d087592a2634cf25ec24d0dc3026e0a66c03aef772361a1bc9f1cc8ccc5`. In-memory test SHA-256: `6a729543ce03d8b5b25751cbb64776ac1d8d36a3af0847e229ebf970a9427e7d`. Target file remained at its pre-patch SHA-256 `00c6fc11445b267b08caea0c9fb6d5fb38f0056202136983c791c9a940003482`. No test, Git operation, or target-file write occurred. The existing implementation-plus-R3/V3 patch remains the next stage and does not modify this test file.
