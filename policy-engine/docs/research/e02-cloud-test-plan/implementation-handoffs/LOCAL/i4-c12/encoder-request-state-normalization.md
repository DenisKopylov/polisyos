# I4 C12 encoder request-state identity repair

The producer identity changed after the first real SentenceTransformer encode
even though the pinned weights, module configuration, tokenizer vocabulary,
normalizer, and all nine local model assets were unchanged. The bounded probe
isolated the fast-tokenizer backend `padding` and `truncation` fields: both
started as `null`, then became the exact options used by the shared
SentenceTransformer request (`padding=True`, `truncation="longest_first"`,
`max_length=module.max_seq_length`). This is P40 **same class, one level
deeper**: the asset digest was sensitive to mutable request-time backend
state.

The repair is centralized in `derive_encoder_identity()`. It parses present
backend JSON strictly, derives the known request profile from live tokenizer
settings and the owning module, and compares the backend's native API
properties. It deserializes the JSON and confirms the copy exposes the same
properties before clearing request settings on that copy. This avoids relying
on a particular serialized spelling while preserving all other backend
material. Different or unsupported values remain identity-bearing; malformed
present JSON raises `ValueError`. The helper does not mutate the tokenizer.
We did not change the basis schema, rewrite a manifest, or substitute another
model.

The mirrored kernel test exercises generation publication and encoding across
the request-state transition, checks the selected basis remains bound to the
same recomputed identity, and confirms vocabulary, normalizer, and maximum
sequence length changes still change that identity. Its fixture separates the
native API property shape (`length`, lowercase directions/strategy) from the
serialized form (`strategy`, title-case values). It also checks a nonmatching
request option remains identity-bearing, serialized/API disagreement refuses
normalization, and malformed backend JSON refuses identity derivation. A
tokenizer-only probe against the pinned E5 snapshot
using the real Transformers/Tokenizers packages confirms both shapes and the
same-state result without loading model weights; output is retained in
`LOCAL/raw/c12-encoder-normalization/real-tokenizer-api-transition.stdout.txt`.

Focused verification passed: 12 tests in
`tests/unit/data_forge/kernel/test_encoder_identity.py`; Ruff check and format
check passed for the implementation and test modules. Full outputs are in
`LOCAL/raw/c12-encoder-normalization/focused-pytest-verbose.txt`,
`ruff-check.txt`, and `ruff-format.txt`. Existing
selected generation digests are not rewritten; profiles whose previously
recorded digest included post-encode request state need normal producer
regeneration before a reader can admit them. The asset digest remains a
compatibility identity, not proof of arbitrary executable `encode` behavior;
the real local provider remains a separate requirement.

The original full real-encoder producer-to-fresh-HTTP witness failed before
publication with the mismatch this patch addresses. It has not been rerun
against this source delta; that expensive witness remains pending a new frozen
source review and grant.

## Reviewer correction and actual backend check

The first test-only fixture modeled the raw serialized enum values and passed,
but did not model the native Tokenizers API property shape. Independent review
correctly rejected that result as insufficient. The implementation and fixture
were widened on the second finding of the same P40 class: compare the native
API properties to the request profile, round-trip JSON through the backend's
own `from_str`, and clear settings only on a verified copy with `no_padding()`
and `no_truncation()`. This replaces the serializer-specific fixture rule with
one API-bound mechanism. No output from the first fixture-only pass is evidence
for the actual backend; its preserved pytest output is
`LOCAL/raw/c12-encoder-normalization/legacy-wrong-shape-pytest.txt`.

The corrected ignored probe loads only the pinned E5 fast tokenizer, not model
weights, and uses the actual SentenceTransformer tokenizer kwargs. It confirms
the native API reports padding with `length: null` and truncation strategy
`longest_first`, while serialized JSON spells these as `BatchLongest` and
`LongestFirst`. The recomputed identity is stable before/after the supported
request, across changed input content, and after resetting the max length; it
changes for a direct 511-length call against the owner's 512 profile. The
helper leaves the live backend JSON unchanged, the native reset copy serializes
back to the initial JSON, and all nine pinned asset hashes match before/after.
Full output is `LOCAL/raw/c12-encoder-normalization/real-tokenizer-api-transition.stdout.txt`.
Its SHA-256 is `286ded6b2fe4a1b2a7404be66d5dc20ed0b6a495c07dbee0e89917f65adf51e8`;
the tokenizer-only run took 12.89 seconds and peaked at 3,298,066,432 bytes RSS.
This validates only the tokenizer identity transition, not model generation,
selected generation admission, HTTP vector service, or production authority.

Final source fingerprints after the corrected focused verification are:
`embeddings.py` `3321c8511f3f206a98245fd7c02a679bc401f0f1753e3a11e91c3c1acd29d72e`,
`test_encoder_identity.py`
`3526af957b37c300a1bf1488c52c406ccd9825ca5768eef6890ef92a5e940be5`, and
`README.md` `3af600896264a675539c5f093ef98663873479d733d4a6bb11f7d52804153119`.
The final pytest log SHA-256 is
`935930ff3f78fdbb2dfb624686c3717cc22a6ea7a403f186f673e689aaa1ab26`.
