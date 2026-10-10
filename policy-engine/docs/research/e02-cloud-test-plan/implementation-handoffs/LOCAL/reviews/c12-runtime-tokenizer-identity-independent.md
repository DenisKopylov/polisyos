# Independent review: C12 runtime tokenizer identity

**Review status: READY for this bounded identity-repair slice; not G acceptance.** I reviewed the exact three leased source components at these byte fingerprints:

| Path | SHA-256 |
|---|---|
| `src/polisyos/data_forge/kernel/embeddings.py` | `3321c8511f3f206a98245fd7c02a679bc401f0f1753e3a11e91c3c1acd29d72e` |
| `tests/unit/data_forge/kernel/test_encoder_identity.py` | `3526af957b37c300a1bf1488c52c406ccd9825ca5768eef6890ef92a5e940be5` |
| `src/polisyos/data_forge/kernel/README.md` | `3af600896264a675539c5f093ef98663873479d733d4a6bb11f7d52804153119` |

The change now binds only the exact shared fast-tokenizer request state. It derives the intended padding and truncation configuration from the tokenizer and owning module, checks both live native properties, parses the serialized backend JSON, reconstructs a copy with the backend's `from_str`, and verifies the copy exposes those same properties. It clears padding and truncation on that copy only. It retains every other serialized backend field and the existing vocabulary, special-token, module-config, model-max-length, and weight inputs. If the supported request does not match, the backend remains identity-bearing; present malformed JSON refuses identity derivation.

The first review found the test fixture had modeled the serialized enum values as native API values. That was a same-class, one-level-deeper P40 finding. The corrected mechanism widens the check to the whole native padding/truncation state and round-trips the actual serialized object before normalization. I found no second escape in this bounded class. The old fake-protocol receipt is explicitly disqualified; the final test adds native API-shaped positive and mismatch controls.

I independently reran the mirrored focused test module with:

```text
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/data_forge/kernel/test_encoder_identity.py -vv
```

It collected and passed all 12 tests in 0.08 seconds. The complete output is retained at `LOCAL/raw/c12-runtime-tokenizer-identity-independent/focused-pytest.txt` (SHA-256 `5cad070d6eac2d35b90f82d8dae5271591f214baa2006df01d078de1c8d0862a`). Ruff check and format check also passed for the two changed Python files. Their outputs are `LOCAL/raw/c12-runtime-tokenizer-identity-independent/ruff.txt` (SHA-256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`) and `format.txt` (SHA-256 `3bc53bf3e981a98a34a852e175bf9b77af841edea74fca595d9aedcbaf9a4938`).

I also reran the pinned E5 **tokenizer-only** probe, without loading model weights:

```text
TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src \
  docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/c12-real-encoder-profile/venv/bin/python \
  docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/c12-encoder-normalization/real_tokenizer_api_transition.py
```

The process loaded the pinned revision `3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3` with Transformers 4.57.6 and Tokenizers 0.22.2, and reported the candidate module origin under this checkout. A one-item request and a different-content/two-item request both kept the identity stable at the owner's 512-token limit; a 511-token request changed the identity; returning to 512 restored it. The helper did not mutate the live tokenizer, the normalized copy serialized to the initial backend JSON, and all nine named local asset hashes matched before and after. The full independent output is retained at `LOCAL/raw/c12-runtime-tokenizer-identity-independent/real-tokenizer-api-transition.txt` (SHA-256 `56ca17557d148e461d301c30447ca07e40cd62490c981ae9a87bff91095a4805`).

For source context, the original captured backend-values output is `LOCAL/raw/c12-real-encoder-profile/diagnose_tokenizer_backend_values.stdout.txt` (SHA-256 `368b931a2a370d7db36964a663114af344230ce6a064cc1a821e362fe0577e62`) and the nine-file asset manifest is `asset-file-manifest.txt` (SHA-256 `191a71ec41bc1a69665fffccb5fa7f1c30b3f94ccd60f71cc3ed1f074ecb98ca`). The original producer-to-fresh-HTTP witness remains a **pre-patch failure** at the post-encode asset identity check: `real_legal_http_witness.stdout.txt` (SHA-256 `aa4cdcb93e38720eeed01e4fecce5feed0ec5d4c02eef7c288e78dde11201e6d`). It was not rerun against this delta; the expensive full-model producer/consumer witness is still needed after the source freeze.

This review establishes compatibility of the asset-identity function with the pinned E5 tokenizer's shared request transition. It does not establish a full Legal producer→persisted generation→fresh HTTP consumer positive, selected-generation admission, arbitrary replacement-`encode` behavior, live production currentness, or external authority. Existing generations whose digest included the post-encode request state still require normal regeneration before admission. No formal G closures are proposed here (`[]`).
