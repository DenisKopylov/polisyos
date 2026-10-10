# C12 final real E5 → Legal HTTP witness readiness

**Disposition: command prepared; full witness not run.** This is a source-bound compatibility witness, not evidence of live production authority, current legal content, or legal truth. No model was loaded and no environment, product source, or asset was changed for this review. The next run remains gated on a fresh root-owned source/input freeze and the serialized heavy slot.

## Command and execution profile

Working directory:

`/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`

Use the already provisioned C12 interpreter and script with the recorded offline, single-thread settings. The outer root capture retains the full streams and process measurements under the same command-owned directory; the prior failure log remains intact:

```sh
env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
  /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/c12-real-encoder-profile/venv/bin/python \
  -B \
  /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/c12-real-encoder-profile/real_legal_http_witness.py \
  --case-root /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r2/tools/c12-real-http/case
```

The script itself sets `HF_HOME` to the local cache, disables Hugging Face and Transformers network access, and calls `torch.set_num_threads(1)`. It loads `intfloat/multilingual-e5-large` revision `3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3` from the local snapshot, on CPU. The separate interpreter is Python 3.14.3/macOS arm64 with 143 distributions (inventory SHA-256 `46ca3289e318e064cb0b2a4e8d8b65ed493aba1692d08d011c06e03d4a069456`); key versions are Sentence-Transformers 2.7.0, Transformers 4.57.6, Tokenizers 0.22.2, Torch 2.10.0, DuckDB 1.4.3, FastAPI 0.128.6, and httpx 0.28.1. Module origins are under this venv for the encoder/runtime dependencies and `policy-engine/src` for PolicyOS. The witness uses FastAPI `TestClient` in-process: it opens **no TCP/HTTP port**. Its DuckDB corpus, generation files, runtime CAS and cache are under the required command-owned `.../tools/c12-real-http/case` root, outside the fixed encoder profile.

The applied script is SHA-256 `95b787162b0bab57be00ad6847f80fe1802754124226a64832b90d46472c241a`; the current `real_legal_http_witness.command.txt` is SHA-256 `dfecf3d000742e721edaff5e4cfd905d5b58f0ee0b66aa6ab1d81f82590eb234`. It requires an absent absolute case root beneath the planned C12 command output root. Its database, generations, CAS, cache and result files are confined there, outside the fixed profile. The previous command is preserved as `real_legal_http_witness.command.historical-7574.txt@f7794c16e44c8b942347d99721cb71465b4842eb82bedc549823ea3a7f211e26`; the old script hash `b7e656…` describes the earlier attempt. Keep the old failure file `real_legal_http_witness.stdout.txt` (SHA-256 `aa4cdcb93e38720eeed01e4fecce5feed0ec5d4c02eef7c288e78dde11201e6d`) unchanged. The outer capture must retain duration, peak RSS, complete streams, exit status and before/after source and asset identities even if the retry fails early.

## Model snapshot

The separate snapshot is rooted at:

`.../raw/c12-real-encoder-profile/hf-cache/models--intfloat--multilingual-e5-large/snapshots/3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3/`

The nine-file content-hash list is `asset-file-manifest.txt`, SHA-256 `191a71ec41bc1a69665fffccb5fa7f1c30b3f94ccd60f71cc3ed1f074ecb98ca` (9 unique physical files, 2,261,765,112 bytes):

| Snapshot file | SHA-256 |
|---|---|
| `1_Pooling/config.json` | `56c469dba9e31869bb7dfceb9b3d76ac06549d1ba869509d8eb4e8aeb31d62d1` |
| `config.json` | `e42d98d0c211928d788467aa951000391017f647c76ca8ce2ef6dd8d0c9ce5ca` |
| `model.safetensors` | `020afdebf2762b29fcaf286629a96c3b3b65af241f6a08226b1cfee60a21def6` |
| `modules.json` | `c6e29747481e8b5dd2b58401966aeac910de39092f90cda9a704b1545f902b04` |
| `sentence_bert_config.json` | `948201d8329907aae938fa62f9ceeed53f5694dacc2b87b9f3b78b37ee986529` |
| `sentencepiece.bpe.model` | `cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865` |
| `special_tokens_map.json` | `06e405a36dfe4b9604f484f6a1e619af1a7f7d09e34a8555eb0b77b66318067f` |
| `tokenizer.json` | `62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626` |
| `tokenizer_config.json` | `efb5c0d09722e5fe59a462cd2a9976ee216d55b037597d997cd3fe833216da15` |

The older model-input inventory is `composed-mac-current-source-inputs-20261010-13e411da.model-assets.json` (file SHA-256 `2833bbd64055242b9dc7c748e7892d50c13f3cdba3cc231872c4777cd46234fc`, inventory SHA-256 `dbbe09c2e619bf8a1675f49a0af0534d49f318c87cb289348f33e6c027d3825e`). It identifies the HF cache blobs but explicitly does not rehash the large model bytes; the nine-file manifest above supplies the content hashes. Check all nine again in the root-owned final capture before and after the run.

## Deciding properties exercised

The script creates a synthetic one-row DuckDB corpus, then uses the actual `build_local_embeddings_and_indexes` producer with a real `SentenceTransformer` to build entity, fact, and provision generations. It resolves each selected complete generation, recomputes each basis against the canonical projected DB members, requires an encoder-bound generator rule, and builds immutable `LegalQueryProfile` / `LegalQueryGenerationIntentV1` request data from those selected references. It releases the producer and creates a **distinct fresh** `SentenceTransformer` and actual `LegalQueryEncoderProvider` for the served consumer.

Through `POST /api/v1/control/lex/search`, the positive request must return HTTP 200, `search_mode="vector"`, no refusal code, and `fact-1`. The paired adversarial request changes only the selected legal-facts generation ID to a stale value; it must return HTTP 200 with text fallback and `vector_refusal_code="query_profile_stale_or_mismatched"`, still preserving the `fact-1` result. A failure at any assertion is a failed witness, not empty success. This exercises producer → persisted generation/member checks → fresh real encoder → actual HTTP consumer and a typed refusal on changed immutable intent.

The test fixture intentionally contains fictional strings, including a `grounded_fact` fixture marker and a test citation. The script labels them synthetic and does not establish grounding, legal accuracy, a production catalog generation, deployed-provider authority, or ongoing currentness. It also does not claim arbitrary executable encoder behavior from the model asset hashes; it demonstrates compatibility for this pinned encoder and request profile only.

## Input freeze gaps and prior result

The prior real-model attempt was frozen to source commit `7574c864a605c50efc033b966807790cbd8d1781` / tree `9561394a619e21b92680d79a1aa812da6892967c`. It failed after the first actual `model.encode()` call and before generation publication, with `ValueError: legal embedding encoder assets changed during generation`; neither the HTTP positive nor stale-intent request ran. Preserve that failed result as failure evidence, not as a product pass.

The subsequent identity repair normalizes only verified, request-time fast-tokenizer padding/truncation state on a deserialized copy; it preserves other tokenizer/model identity material and refuses malformed or mismatched present state. Its actual pinned-tokenizer transition output is `LOCAL/raw/c12-encoder-normalization/real-tokenizer-api-transition.stdout.txt` (SHA-256 `286ded6b2fe4a1b2a7404be66d5dc20ed0b6a495c07dbee0e89917f65adf51e8`). Focused tests, Ruff, and format passed, but this tokenizer-only check is not the full model-generation/HTTP witness. The repaired implementation fingerprint is `src/polisyos/data_forge/kernel/embeddings.py` SHA-256 `3321c8511f3f206a98245fd7c02a679bc401f0f1753e3a11e91c3c1acd29d72e`; mirrored test fingerprint is `tests/unit/data_forge/kernel/test_encoder_identity.py` SHA-256 `3526af957b37c300a1bf1488c52c406ccd9825ca5768eef6890ef92a5e940be5`.

The 13e411da source-input manifest includes the witness `.py` in its raw import inventory, but it is not a final post-repair source freeze. The old `7574` source commit predates the identity change. A new source freeze must bind the final committed product tree/import closure and the isolated venv before running. The existing manifests also do not enumerate these `.txt` evidence/recipe files as exact inputs: `real_legal_http_witness.command.txt`, `asset-file-manifest.txt`, and `package-origin-profile.txt`. Add them as exact input paths in the next manifest, or replace their role with equivalent root-captured, hash-bound records. Rebind the C12 venv entrypoint, `pyvenv.cfg`, all 143 distributions and module origins, and the separate nine-asset content list; do not reuse the previous commit/tree as the repaired source baseline.

The script, package profile, command recipe, asset manifest, and prior failure are read-only inputs/evidence. This readiness note is not an execution receipt; the full witness remains **UNRUN** until the authorized root execution after freeze.
