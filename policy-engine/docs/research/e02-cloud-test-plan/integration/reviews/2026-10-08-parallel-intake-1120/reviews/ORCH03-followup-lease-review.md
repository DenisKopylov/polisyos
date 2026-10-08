# ORCH03 C08 follow-up lease review

Read-only comparison of carrier `27ad60afe4cfedea9a9c0ff71d9abd22c30836d9` with `8077016f144712b00a05f0b3b6701c51852f1d21`, using current G grant `d4085be5b58968a5b53d5d95323f6dd70cbf95a5`. The delta adds exactly the C08 owned-followups lease and its compressed resume receipt. No source implementation is included or accepted by these two paths.

## Admission and source qualification

The lease’s C08 admission hashes match the compressed file: 13,896 stored bytes / SHA-256 `80d3c83b51b36422769214b8ec79ebf3f8828952fc89a3e19bf2e523a5b564a5`; 171,103 decoded bytes / SHA-256 `2bc0b76187560520e960a566ae460df65e388ce8e8e910f85ed714f2d00c9803`. It requests `resume` of the existing pair `codex/e02-F-c08-20261008` and `/dev/shm/e02-orch03-20261008/c08`; recorded commands see that worktree at `ab48c152514b025618cd6e3fc9acc70a1ed773ee`, tree `c8de2a22c30ecfdafaee4da753d1958d4f947af4`. The earlier C08 resume record at 807 has the same branch/path and an earlier head. This is a refreshed observation, not a branch/path reservation: the selector is `consumer_asserted`, and `name_reservation` is unresolved by construction. Before mutation, rerun the exact check on the actual cloud host and read back the attachment/HEAD.

The lease G dependency pair `d23` / tree `2239b2c97f840ab28ee4b921e964618548dd2c25` matches the historical pinned G tree, but predates the d408 grant. The pinned C08 `ab48` packet is the metadata-only B56 qualification. G’s d408 verdict says the CPDAG candidate remains held pending graph-bound fresh proof readback and grants no C08 source acceptance. The proposed paths below must therefore remain future work, not be described as published source or an accepted proof.

## Ownership and exact grant needed

The current dispatch scope already contains `foundry/methods/catalog/causal/`, including the proposed `causal_engine/artifacts.py` and `id_engine/core.py`. C07 and C08’s current paths are disjoint: C07 owns named uncertainty/estimand/ref/facade files, not `ir/analytics/causal.py`; neither exact new path appears in a current dispatch source scope or named test-start path:

- `policy-engine/src/polisyos/ir/analytics/causal.py`
- `policy-engine/tests/unit/ir/analytics/test_causal_proof_graph_binding.py`

The d408 `continuation-leases.json` grants only the named C09 interval and B190 bridge paths. It is not authorization for this C08 addition. Before writing, G needs a separate one-time exact-path grant for the two paths above to the existing C08/F writer `/root/c08` on `codex/e02-F-c08-20261008`, with `/root/oracle_ir` as independent reviewer. Do not widen the grant to `ir/analytics/**` or transfer C07’s IR owners. The current `G_dependency` pin to d23 records the earlier review; the new grant should name the granting G checkpoint (d408 or its successor).

The other C08 entries remain within its existing causal-catalog work or are its focused mirrored tests and unique release fragments. C09’s four MC paths remain within E/C09 uncertainty ownership and do not overlap this C08 slice. C08’s exclusions correctly leave the C11 search funnel, C07 refs/facades, C10 served/S10, and G generated/global files outside the lease.

The exact grant should be limited to internal proof-source binding: use the existing persisted graph/reference/artifact machinery, recompute the typed graph payload identity from the original graph/input roster, and refuse a mismatch. Keep DTO/schema/registry-ref/facade changes outside this grant; send any necessary shared-path patch to C07/G for a separate decision. Preserve the declared complete-observed-static-DAG/existing-g-formula profile; do not change default scientific authority, infer authority from score/status, or generalize to latent/PAG/universal identification. This fits G’s existing held status and does not resolve the remaining source review.

**Recommendation:** the two files are a coherent C08 lease proposal with a valid point-in-time resume receipt. Record the separate exact-path G grant before authoring; no additional source/test rerun is indicated by this metadata delta.
