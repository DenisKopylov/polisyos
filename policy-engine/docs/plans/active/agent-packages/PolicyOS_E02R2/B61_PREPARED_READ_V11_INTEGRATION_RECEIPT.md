# B61 — prepared SKG read, bounded V11 integration

## Discrepancies and limits first

The candidate's original final replay selected only three of 51 collected cases.
The fresh canonical V4 wave now passes all 121 cases across 13 complete files.
This bounded engineering witness does not close B61's authority residuals.
The corrected lease is 29 paths, of which 19 changed. Source issuer authenticity,
K_ref custody, production-scale source-hash cost, hash-to-MVCC correspondence
beyond WAL/filesystem checks, and deployment-specific timeout routing are
not established. Output dependence on consumed SKG rows is not inferred from
a successful SELECT 1.

## Property and production callers

Existing SKG read owner creates and closes one prepared read for an untimed
cacheable workflow invocation. Cleanup is unconditional, including query errors.
A timed custom invocation bypasses optional preparation and all cache lookup,
validation, hit and store, even with a stale generic row. Its private worker
transaction is never closed underneath a live worker; a late attempt cannot
write through its revoked owner lease. Existing WorkflowExecutor consumers
receive the typed read through ExecutionContext; no second read/cache owner
is introduced.

Query receipt scope is `bound_connection_query_execution_only` (selector v4,
receipt schema 3). It proves execution on the bound connection, not row-to-output
causal dependence. Specialized IR refs normalize through the existing shared
mutation replay owner; malformed refs retain exact refusal. Candidate computation
remains available, while issuer/K_ref authority stays held.

## Frozen review packet

- `/Users/deniskopylov/.codex/scratch/e02r2-held-b-review-20260930/B61_PREPARED_READ_BRIDGE_candidate_92bf_v11_final_20260930.patch@sha256:061dd03b492013da5a2cc2aa97c76c61e07cdfe4d2dbea23250231d80a9da7f5`
- `/Users/deniskopylov/.codex/scratch/e02r2-held-b-review-20260930/B61_PREPARED_READ_BRIDGE_candidate_92bf_v11_final_20260930_manifest_v2.json@sha256:8089bd63c7989f81ee194266b70e6b218625ebfe0f7b0f556a39833ce2b08c2c`
- `/Users/deniskopylov/.codex/scratch/e02r2-held-b-review-20260930/B61_V11_LIFETIME_SCOPE_DESIGN_V2.md@sha256:409207d4ef66108fa1830f1ebb33074b3f16b24bd7dbb3ee7887786356d0d0f3`
- `/Users/deniskopylov/.codex/scratch/e02r2-held-b-review-20260930/B61_R2_v11_FINAL_FREEZE_RECEIPT_V2.md@sha256:11f66c8c2666b69ebe30bee06004bb808c0f71e303f58aaf929f27574c09b662`
- `/Users/deniskopylov/.codex/scratch/e02r2-held-b-review-20260930/B61_V11_INDEPENDENT_REVIEW.md@sha256:34c0863fb29e2f3fe34fe9617e2190ff1cb704d0ee939770334031e97dcd81ff`

## Fresh canonical wave

V4 passed all 121 cases across the 13 complete leased test files (four changed
and nine existing importer/control files), with all 19 changed Python files
passing Ruff. The complete freeze contains 31 inputs, including all 20 changed
paths, the unchanged importer/control files and existing fixture owners. Real production data
is linked read-only, but the synthetic SKG tests do not prove production-data
behavior or issuer authority. No final finding-status change is made here.

## Canonical lint discrepancy

The candidate reports Ruff PASS, but the actual canonical invocation over all
20 changed Python files (B61 19 plus CYC-05) returned 18 findings. The complete
canonical log and JSON are retained; no inherited attribution is made. Before
any pytest run, root applied import ordering/quoted cast/type-only import fixes,
object annotations on the transparent native proxy, equivalent suppression of
DuckDB rollback errors and a combined tenant/error test context. Canonical Ruff
then passed the full 20-file denominator. A delta-only independent review preceded the B61 wave. The prior V1 freeze and failed lint receipt remain.

Independent V2 delta review found that the type-only ArtifactRef import breaks
Pydantic runtime annotation resolution for PreparedSKGReadReceipt. No B61
pytest wave ran at that freeze. Root restored the runtime import with one
explicit TC001 exemption on that import, because the receipt model requires
it at runtime; no schema or gate relaxation. V2 is not accepted. The first V3
lint found one import-format issue and no tests ran; import-only normalization
then passed canonical Ruff over all 20 changed Python files at V3b. A narrow
delta review returned GO before the first whole-file wave.

## First full wave and fixture-scope correction

V3b ran all 13 complete files: 121 cases = 114 PASS + 7 setup ERROR, zero
assertion FAIL, exit 1, 16.14 seconds, RSS 1,096,908,800 bytes and zero swaps.
Origin audit passed: 1,366 product modules, 13 collected test modules,
30 loaded support modules and 31 frozen inputs, zero foreign origins/drift.
The seven new integration cases requested decorated fixtures whose existing
unit-nodes conftest scope excluded that integration module. They never reached
the intended owner-prepare/callback assertions and are not inherited reds.

The independently reviewed one-file correction locally re-exports all five
existing fixture objects and their dependency closure; no duplicate owner,
global fixture plugin, production change or assertion relaxation. The full
13-file V4 rerun passed; its exact evidence is below.

- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/b61-v3b-whole.junit.xml@sha256:9d51c8a27d472c6fe2df1635cdd98917aa2066f6132be667c554e809b8b9e83d`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/b61-v3b-whole.log@sha256:dc53d1f65e16a4944bbedd8255784bb6a21fe266ec81a7a0f5da007cbf02168a`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/b61-v3b-whole.origins.json@sha256:af11acfb508129f0ffc3a20da779e4b8153594bd5eaffbbd5e51907f49c7bffb`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/B61_V11_CANONICAL_RUFF_DELTA_V3B_INDEPENDENT_REVIEW.md@sha256:ae2488cd3ff55ddc059b6b8ce4809cf427812e26b2cb49b052010fdc11e0d278`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/B61_V11_FIXTURE_SCOPE_REEXPORTS_V4_20261001.patch@sha256:54879c592f23e86bf294aafd52955da61781530000a1702c0273641a561de414`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/B61_V11_FIXTURE_SCOPE_REEXPORTS_V4_INDEPENDENT_REVIEW.md@sha256:5013b16d86c623fa95d588aee046e0f7db5b9e237fef65ce34b469c36a6d082f`

## V4 full-file deciding evidence

Actual result: 121/121 PASS, zero assertion failures, setup errors or skips,
exit 0; 16.64 seconds wall time, maximum RSS 1,095,860,224 bytes, zero swaps.
Origin audit PASS: 1,366 loaded product modules, 13 collected test modules,
32 loaded test/support modules and 31 frozen inputs; zero foreign origins and
zero changed frozen inputs. Generated code without file origin, third-party
implementations and external processes remain outside that audit by construction.
Native numerical threads were limited to one. Exact flags and environment are
retained in the command receipt. The prior V3b fixture-scope errors remain in
the retained deciding output; the V4 fixture correction preserved assertions.

The run froze source at parent `7686e5e0ce984b8b4a9937ca560b88654a78d7ce`
plus this reviewed candidate. All 31 hashes were rechecked after completion.
Only this receipt changed after the run to record its result; runtime/test inputs
remain byte-identical. A four-base whole-file comparison is still outstanding
for the new cohort, so no claim of complete P41 or finding closure is made.

- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/FROZEN_INPUTS.v4.json@sha256:b1e5740c2713811153d6982950e2e29985fc07fde764a363d24b8f18a3a3158e`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/B61_CANONICAL_V4.patch@sha256:cb02af9a881c75d1e8702cf5e03a22df813c69c9c199a968b001d7906b690f76`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/b61-v4-command.json@sha256:9db72902dad72b19089ee0946acd8acf61ea34fd86d50b5a3341106b6f585aa8`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/b61-v4-exit.json@sha256:8a7d2e5f35dd52400334d35d64cd1c83fdb20857eea1400ab01ab8e4fdae8e57`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/b61-v4-whole.junit.xml@sha256:315276088e696bf9fe7b3ea4bc0ee0528283a6c5939ca270a8dea95c102e896d`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/b61-v4-whole.log@sha256:0cb336c53c720a66e70712379cde9b14e67ae7559abd59a62d4b93704d4e3330`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/b61-v4-whole.origins.json@sha256:65fe56e898afe1ae6caafe8510232af7d4ef1f90f3ce13599c9df526b21f3df8`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/ruff-v4.log@sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`

Independent final evidence ACK (no further runtime edit or replay):
`/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/B61_V4_INDEPENDENT_EVIDENCE_ACK.md@sha256:baa53728d1757831b896a8491475edc566957edfc238ac5ab3e17674df230afa`.
The reviewer independently reconciled all 121 JUnit identities and 31 frozen
inputs; only this post-run receipt changed, as declared.
