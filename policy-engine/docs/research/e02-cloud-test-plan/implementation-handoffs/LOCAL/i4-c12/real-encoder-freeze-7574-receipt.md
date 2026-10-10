# C12 real encoder freeze attempt — source 7574c864

Status: **failed before generation publication; no consumer positive or typed-refusal request ran.**

The one authorized command used the frozen candidate source at HEAD
`7574c864a605c50efc033b966807790cbd8d1781` (tree
`9561394a619e21b92680d79a1aa812da6892967c`). Before and after the run, HEAD
and tree matched. The candidate worktree was clean before the command; afterward
the only visible untracked path was
`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/reviews/composed-capture-git-prefix-independent.md`,
which I did not touch.

Frozen inputs:

- Witness script:
  `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/c12-real-encoder-profile/real_legal_http_witness.py`
  SHA-256 `b7e656b6f0653821228d5ca5ee2f2521893df419a8a782e8c156a289ce6833ab`.
- Command record SHA-256 `f7794c16e44c8b942347d99721cb71465b4842eb82bedc549823ea3a7f211e26`.
- Local model snapshot revision `3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3`; nine-file asset manifest SHA-256 `191a71ec41bc1a69665fffccb5fa7f1c30b3f94ccd60f71cc3ed1f074ecb98ca`.
- Isolated environment: 143 locked packages; `uv pip check` had passed before the run. No environment, script, asset, or product source was changed during this attempt.

The actual `SentenceTransformer` loaded from the pinned local snapshot and reached
the Legal producer call. The first entity table failed at
`src/polisyos/data_forge/domains/legal/batch/embedder.py:282` with
`ValueError: legal embedding encoder assets changed during generation`.
The failure occurs after `model.encode(...)` and before
`_build_embedding_generation_from_vectors(...)`, so this run did not publish a
generation. The synthetic DuckDB fixture remains in the ignored raw run
directory. The stack trace is preserved in
`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/c12-real-encoder-profile/real_legal_http_witness.stdout.txt`
(SHA-256 `aa4cdcb93e38720eeed01e4fecce5feed0ec5d4c02eef7c288e78dde11201e6d`).

The runtime tool yielded after 30.0028 seconds and the next poll observed exit 1.
The runner did not provide an exact end-to-end elapsed duration; the script did
not reach its phase-time/RSS result emission, so no peak-RSS measurement is
available. Do not treat this attempt as a real-generation/currentness witness,
HTTP vector-positive, or typed stale-generation refusal. It establishes only
that the installed real encoder can load and enter the producer, while the
current asset recheck rejects it after encoding.

No retry or compatibility adjustment was made. Any change to the fingerprint,
script, environment, or model assets requires a new bounded decision and a
freshly frozen input set before another compute run.

## Bounded identity diagnostic (source still frozen)

After the failed producer attempt, root authorized a bounded diagnostic only. No
production code, frozen witness script, lockfile, environment, or model asset was
changed. The new ignored probe
`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/c12-real-encoder-profile/diagnose_live_encoder_identity.py`
has SHA-256
`ce08deab4130327bb63a93e17bf1b163d4f70df4e1fa1bf92d949287d9be46bb`.
It loaded the same pinned model once, instrumented the actual
`derive_encoder_identity` function to hash its state/config/tokenizer frames,
then encoded one text from the canonical Legal `entity_embedding_text`
projection. The vector was finite, shape `[1, 1024]`, norm `1.0`; this was a
single-call diagnostic, not a generation or served-consumer witness.

Observed identity changed from
`sha256:757513a014357409764c8d220a68565bd91eb4f00a6548d61ea3e6fdbab27a60`
to
`sha256:e7764fbb55fcd46f8e3e217d6137f0be1e63e0084241217fed55855cc19a27f8`.
The state-dictionary framed digest stayed
`184b27f0aee96ee18f7c17e07c870954633a342f525e3aeb7137638c9438c245`
across 391 tensors. The module/config framed digest stayed
`b697f93125be00040f944841949c2ea522bcdec9172f45ce09345540b6423b41`
across 448 module records. Only tokenizer backend serialization changed;
vocabulary, added vocabulary, special tokens, settings, tokenizer class and
high-level settings were unchanged. A tokenizer-only follow-up using the same
canonical text and the exact `Transformer.tokenize` options
(`padding=True`, `truncation="longest_first"`, `max_length=512`) showed the
backend JSON changes only `padding` and `truncation`, each from `null` to
the request-time options. This pins the divergence: the identity helper hashes
mutable fast-tokenizer call state as if it were immutable encoder asset
material. It is not a weights/config/tokenizer-file change.

All nine named snapshot asset SHA-256s matched the frozen manifest before the
model probe and again after the tokenizer-only probe; the hashes were identical.
The source HEAD/tree and worktree status were unchanged through both probes.
Runtime origins were Python 3.14.3 on macOS arm64; Torch 2.10.0,
Sentence-Transformers 2.7.0, Transformers 4.57.6, Tokenizers 0.22.2, and
Safetensors 0.7.0 resolved from the isolated 143-package venv; Legal source
modules resolved from the frozen candidate worktree.

The model diagnostic took 27.17 seconds wall time and peaked at 3,956,080,640
bytes RSS. The tokenizer-only confirmation took 6.07 seconds and peaked at
1,039,630,336 bytes RSS. Full outputs remain in ignored raw files:
`diagnose_live_encoder_identity.stdout.txt` (SHA-256
`41fb6c91093b61c0a9c779cd798ab8e07d504c35b5579d4c8ef41026a9a3cf14`) and
`diagnose_tokenizer_backend.stdout.txt` (SHA-256
`988cdb524fd64c4712f057080de55f7fd6bf0146c90fc3165401881017b4b`).
The model diagnostic's reporting comparator raised a probe-only `KeyError`
after it captured the before/after component summaries; the separate tokenizer
probe captured the exact changed JSON keys. Neither error occurred in product
code. No full witness retry, source patch, generation publication, HTTP vector
positive, or stale-profile refusal has been performed. The proposed central
identity normalization and semantic/removal tests were sent to root for exact
source-lease confirmation before editing.

## Follow-up correction: serializer shape and tokenizer-only validation

Independent review found that the first fixture-only source pass matched the
serialized `BatchLongest`/`LongestFirst` form rather than the native Tokenizers
API shape. That pass's 12 green tests did not establish actual-backend
compatibility and must not be cited as a product pass. The revised helper and
fixture use the native properties (`padding.length is None` and lowercase
`truncation.strategy == "longest_first"`), round-trip the serialized backend
through its own `from_str`, and clear request state only on a verified copy.
This was the second same-class P40 finding and widens the mechanism to the
backend API plus serializer round-trip, rather than adding another
serializer-specific exception.

A tokenizer-only check against the same pinned E5 revision (no model weights)
then observed the native and serialized property forms side by side. Under the
canonical tokenizer kwargs, identity stayed equal before/after encoding and
across changed text content; a call with `max_length=511` against an owning
module profile of 512 changed identity. The normalizer left live backend JSON
unchanged, its reset clone serialized to the original JSON, and all nine named
asset hashes remained unchanged. Full output:
`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/c12-encoder-normalization/real-tokenizer-api-transition.stdout.txt`
(SHA-256
`286ded6b2fe4a1b2a7404be66d5dc20ed0b6a495c07dbee0e89917f65adf51e8`), 12.89
seconds wall and 3,298,066,432 bytes peak RSS. This is a tokenizer identity
compatibility result only; no model generation, query provider, fresh HTTP
consumer, or production currentness was exercised. The original full witness
failure remains failed, and no full model witness has been rerun against this
source change.

Corrected-source verification after that probe passed 12 focused tests plus
Ruff check/format check. Full output paths are
`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/c12-encoder-normalization/focused-pytest-verbose.txt`,
`ruff-check.txt`, and `ruff-format.txt`. Current source hashes are
`embeddings.py` `3321c8511f3f206a98245fd7c02a679bc401f0f1753e3a11e91c3c1acd29d72e`
and `test_encoder_identity.py`
`3526af957b37c300a1bf1488c52c406ccd9825ca5768eef6890ef92a5e940be5`.

