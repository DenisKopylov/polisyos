# R13-F — ACQ-01 contract route uses its supplied store

Status: bounded R13/P31 repair. Production world growth remains owned by
`AcquisitionWorldGrowthBridge`; this contract-testing route does not admit a
world delta or issue an epoch.

The ACQ-01 route's historical v1 payload retains `capture_store_root` as
replay data. The route reader now resolves its CAS references through the exact
`GenerationCycleController` artifact store. A missing or foreign store refuses
before rebuilding a world. The preserving control uses one store for route
capture, N7 re-entry, real N5, and default N8. Product inputs:
`policy-engine/src/polisyos/runtime/quality/generation_cycle.py@sha256:e89b99c3f7951173a8fc50ef316de46a0c3a49946044f2c93e71b18850a6fb42`
and
`policy-engine/tests/unit/remediation/test_acq_01.py@sha256:b1c81c17fa83205f469f5f0b40d13118c527a48d3bba8b5a447488176e263fd2`.

The integrated focused group passed 4/4:
`/Users/deniskopylov/.codex/scratch/E02R2_R13F_candidate_46de219ae/R13-F-integrated-focused.junit.xml@sha256:bcc7ce8514361d81c39ffbdbab776dda23515810dc5940e3115021130e6b29a2`.
In the isolated removal probe, replacing the supplied-store read with the old
root reopen while leaving payload and test markers intact made both
missing/foreign-store tests red. Mutation, restored source hashes, and complete
output are pinned in
`/Users/deniskopylov/.codex/scratch/E02R2_R13F_ROUTE_STORE_TRACE_46de219ae_20260926.md@sha256:45ba25ac39021a6163fa2d7fd8133f911d1115b9575b05b7b14f2fca5eab4286`.
Independent review:
`/Users/deniskopylov/.codex/scratch/E02R2_R13F_candidate_46de219ae/R13F_FINAL_INDEPENDENT_REVIEW.md@sha256:8819d9537d3bf0ab75e2d20c110793e98613165a98967f5e05cd3534e75764a8`.

The production receiver-fence assertion mismatch reproduces at the exact
`46de219ae` slice base and yields no observed pass-to-fail transition. Its
ownership stays `not_established` under P41 because the changed source/test
paths intersect the test input. The lane's four-base whole-file replay remains
open. The route reader still does not retain a non-default
`manifest_profile_sha256` selector from its serialized ref; selected-view
fidelity is an R9/P38 residual. A guarded two-tenant route witness is also
open. This slice does not claim full R13 closure.

P37: the gate turns on the actual supplied store object and the resolved
artifact bytes; absent store is not established. P38: exact store identity is
stronger than root-path equality, but default-view reads do not prove the
selected-manifest property for a non-default view.
