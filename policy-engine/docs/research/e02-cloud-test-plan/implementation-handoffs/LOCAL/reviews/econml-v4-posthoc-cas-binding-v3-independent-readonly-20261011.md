# Independent read-only review: V4 post-hoc CAS binding V3

## Disposition

**GO, scoped:** the retained V3 writer emitted a typed, candidate-only post-hoc binding over the pinned historical V4 execution record. A separate fresh process reopened it and reproduced the envelope/profile checks. **LIMIT:** this is a new local reconciliation identity, `candidate.econml.v4.posthoc_cas_binding@0.3.0`, over an already completed run; it is not a binding emitted by the original MethodJob producer. **BLOCK:** do not promote it to causal validity, calibration, governance/admissibility authority, external custody/currentness, product MethodJob ABI support, or production support. The historical result remains `gate_eligible: false`; the binding is unsigned and explicitly candidate-only.

## Executed receipts

The writer receipt records HEAD `e536bab756ca5538b105205f27a627625dd1da72`, exit 0, 5.7136847919318825 s, 3,223 input hashes unchanged before/after, 15 CAS `put` calls, and status `written_candidate_only_posthoc_binding`. Stdout is 873 bytes, SHA-256 `9cc9587f4121e27a3459aba34f17646dd5a2c60f723c78bf27d283b059d95635`; stderr is empty. The reader records the same HEAD, exit 0, 5.97097262495663 s, 3,226 input hashes unchanged before/after, and status `fresh_process_candidate_binding_read_succeeded`; stdout is 10,873 bytes, SHA-256 `9c0ae3e89da18037e6ac8046d1469277c5c09d9abd4afacd83f8bc2e6b7dd042`; stderr is empty. The reader stdout parses exactly to the retained nested `fresh-reader-output.json` (9,031 bytes, SHA-256 `3aa0e3251a325b5d4fdf4111fa1208cd1afab47eacc7a89f91ef2d05a2a33ef5`). The pointer is a separate new identity, `candidate.econml.v4.posthoc_cas_binding_pointer@0.3.0`, to envelope `sha256:67be93d89c721459bd0abb7206c0cd9b891a4a91f632ce399dae7c1b8f27577c`.

The frozen reconciler is `LOCAL/raw/econml-v4-cas-binding-prototype-v3-20261011/reconcile_v4_cas.py` (56,721 bytes, SHA-256 `44116673642f46cd02627c9fabe69ce747db7cba3949b7e97167ce45253fd1ea`); the design and command plan are cited below. The plan states no worker fit is rerun and no product source is changed. Read-only review of the writer confirms it loads the pinned historical artifacts and adds a V3 execution-record snapshot, local/remote checkpoint readbacks, nine profile-source assets, the V3 profile descriptor, the V3 producer-source blob, and the V3 envelope/pointer. It does not rewrite the original four refs. The reader revalidates exact typed refs, schemas, canonical payload equality, content-derived IDs, profile/checkpoint joins, and full manifest inputs. Its refusal helper catches only `ValueError`/`ValidationError` and raises if a mutated case is accepted.

## Original V4 artifacts preserved

The reader’s `record_pin` matches the stored `candidate.econml.v4_execution_record` ref and the writer’s `record_sha256`: `sha256:b6482af1701ddb2d44defee4fc39d8ee682b0672a599c0397d31551337ea16ab`. That pinned record (schema `polisyos.candidate.EconMLV4ExecutionRecord@0.1.0`, 22,558 bytes, manifest SHA-256 `72e8525da389d0c39b8d6bb71c2fc176fdc7b200f32cbbb15fb1b07c6573380e`) contains all four original refs plus their blob IDs, schemas, manifest paths, manifest hashes, and manifest input edges. Its blob digest matches the pin and its manifest has no inputs. Each current blob and manifest matched those recorded values exactly:

| Original role, kind, and schema | Content ID | Pinned manifest SHA-256 | Bytes | Verification |
|---|---|---|---:|---|
| source · `prototype.hte_observational_data` · `prototype.HTEObservationalData@1.0.0` | `b1d4e29a4dc5a77cb617572f087f497bfb50abae19f900f2b40e70e0f3c3b9dc` | `66c0e7e7e58a89d7a3ddc4166f5effd21fd8d3a28e141a5a6d9858dab41443c3` | 95,827 | ID/integrity/size/ref all match pinned record |
| adapter · `scientist.unified_dag_adapter` · `polisyos.scientist.UnifiedDagAdapter@0.1.0` | `3c22f5e16e3d21ffe5ef7e9ccd405f8474b48db6ff117eed861c48cad1ff1241` | `b031f16516428da4dd7e1eba9b0ad9b5c372fa3327f7075da2120ea135cb62ba` | 358 | same |
| method result · `scientist.method_result.causal.hte` · `polisyos.scientist.MethodResult@0.1.0` | `436675a2a5440340ee9ef0c058fdfe01c4fb8282e778db880778ba9f9be45303` | `563735986c2bd020eae495acf8af629f0615a8281824f32d158ccbd3c1fb2d5c` | 155,743 | same; input edge is source / `input:hte_data` |
| method evidence · `scientist.method_evidence` · `polisyos.scientist.MethodExecutionEvidence@0.1.0` | `43cacb0bbf2a68939165b9d537de6d79949846afa7a3642dbede829e2b28d241` | `897107e96098dcafef2bdd2575e9712484e7635ff148acfcc38a567529906778` | 8,096 | same; input edge is result / `method_result` |

All four blob SHA-256 values equal their content IDs and manifest `integrity.sha256`; all stored `byte_size` values match. The additional candidate artifacts were also checked by their emitted IDs, schemas, content digests, manifest integrity, size, and input edges:

| Candidate artifact | Content ID | Manifest SHA-256 | Bytes |
|---|---|---|---:|
| V4 execution-record snapshot | `b6482af1701ddb2d44defee4fc39d8ee682b0672a599c0397d31551337ea16ab` | `72e8525da389d0c39b8d6bb71c2fc176fdc7b200f32cbbb15fb1b07c6573380e` | 22,558 |
| local profile-source checkpoint | `54f5b03a181f2b443934d4ccf6693c9685de8561bed3aae27a1f07abed9dfee2` | `ebc8ef4368b9ccbf4f9f13b116adbcf9f5d8f53ae2fb4eb257e96acd1f3d644c` | 2,797 |
| remote profile-source readback | `7b6b827288354289a5b48eff480cfb3ac4d5de1ef576d557436324a0a3391fe7` | `4d847ce77196ebec6b43c547c6f10e91c0daf29a6e26454ff55c48609dcefb85` | 292 |
| reconciled worker-profile descriptor | `539bc2e15b63035e7d2d55d4660aa6839376147ec44ca1127f61bedeb8d78d14` | `47009dd5a2422a75f5247237944fb08442c1b30d687996f78991acb3a40024ec` | 6,842 |
| V3 binding producer source | `44116673642f46cd02627c9fabe69ce747db7cba3949b7e97167ce45253fd1ea` | `d9b0f0621a1cd564eadd5f58dc181f86825b3a72cb1d47c33de79c012b197cee` | 56,721 |
| V3 envelope | `67be93d89c721459bd0abb7206c0cd9b891a4a91f632ce399dae7c1b8f27577c` | `2088c144744c0f4f20d5ebf2a858dc7cb186f41a2f3bc7dcd433d9283a75240c` | 4,841 |

The V3 envelope manifest has nine typed input edges: pinned execution record, local and remote checkpoint readbacks, reconciled profile descriptor, the original four artifacts, and the V3 reconciler source. The profile descriptor’s manifest links the record, both readbacks, and exactly nine profile-source assets. I checked those nine referenced blobs/manifests against their declared source files; all IDs, schema/kind/media, integrity hashes, sizes, and file bytes match. The descriptor explicitly says `descriptor_selected_for_execution: false` and `posthoc_reconciliation_of_historical_v4_execution`; its host, isolated-worker, and backend-evidence entries are separate runtime scopes. Thus, the reconciliation binds the reported profile evidence but does not prove one installed package set was the original executor or establish package-byte identity. The nested binding refs equal the envelope refs; the producer-source digest equals both its artifact ID and frozen script digest. The pinned V4 execution source is `297b0557511234bb4b1bd3b09991cef0bd050a3f` / tree `ad9ecc1c4bf2acd57b187b5a2534aa9f3b2d3ffd`. The separate post-run profile-source checkpoint is `19b0486608f0c134fcbff174c88d32fef82edafe` / tree `b193643df4dcc876b1ccb8202411db099610f79e`; local and remote readbacks agree on that checkpoint and report nine exact files/bytes. These local/remote source readbacks do not supply an external signer or issuer.

## Controls and remaining boundary

The fresh-reader output records **22 distinct negative-control cases; all 22 were refused**. They cover envelope ref substitution, stale/foreign profile and execution source, forged authority fields, false checkpoint digests, host/worker scope swap, profile asset kind/media/profile substitution, and nested result/evidence ref kind/media/profile substitution. Results are retained at `LOCAL/raw/econml-v4-cas-binding-prototype-v3-20261011/fresh-reader-output.json#/binding/negative_controls`; I did not deduplicate or rewrite them.

This is post-hoc reconciliation, not original producer emission. The V4 execution record itself declares candidate-only authority and no causal identification/calibration/validity claim. The prototype remains outside a generic structured-slot ABI or product MethodJob lineage extension, has no external verifier, and has no production consumer. The local/remote checkpoint readbacks establish the recorded source snapshot and nine-file byte match only; they are not an external signature, issuer act, or currentness attestation.

## Evidence locators

- Writer command: `LOCAL/raw/batched-blocking-focused-20261010/econml-v4-posthoc-cas-binding-v3-writer-20261011/command.json` (824,121 bytes; SHA-256 `02a6e3fb0f1eb3b365bff08bd24803b6852207244ba58e7d62f4c16c3d1a1b5e`).
- Fresh-reader command: `LOCAL/raw/batched-blocking-focused-20261010/econml-v4-posthoc-cas-binding-v3-fresh-reader-20261011/command.json` (825,640 bytes; SHA-256 `d9d6f19b8ee2244f77360dc99b75b9c9c201fea09f16476bcdd260389d840585`).
- Frozen design: `LOCAL/raw/econml-v4-cas-binding-prototype-v3-20261011/DESIGN.md` (2,539 bytes; SHA-256 `3f120abc35928d7b9480bc34f192394ee8c45e86e9d79d80cb360462c4599064`).
- Command plan: `LOCAL/raw/econml-v4-cas-binding-prototype-v3-20261011/command-plan.json` (12,743 bytes; SHA-256 `e05875c72ce803d1f0b7cbb0a7010365d4b1d1b967327188d7bb6a1552de68a1`).
- Pointer: `LOCAL/raw/econml-v4-cas-binding-prototype-v3-20261011/binding-ref.json` (263 bytes; SHA-256 `8f1279853af7ae25539d8055807c8203a6961761afbad07f1fac12483f5b93ad`).

No source, test, or CAS payload was edited during this review; no workload, import, test, or broad CAS census was run. No formal finding IDs or closure are assigned.
