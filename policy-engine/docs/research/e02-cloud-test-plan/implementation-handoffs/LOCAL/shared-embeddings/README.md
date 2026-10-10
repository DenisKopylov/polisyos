# Shared embeddings lane

This is an uncommitted candidate from branch `codex/e02-unified-local-20261009`.
The lane started from slice source commit `9e89dddfbcc3d8c44a421cc1fc143ec84f3753ae`;
root admission began at `a76bbfaef`, and the branch has since advanced through
root-owned integration commits. The checkout contains peer-owned work; only the
files listed below belong to this lane. The root agent owns staging and commit.

The kernel now derives a candidate `GenerationIdentity` from the loaded
encoder's state dictionary, module configuration and tokenizer assets, then
binds it into the existing generation `generator_rule_version`. The shared
builder either loads one encoder or accepts the actual live encoder object
already held by a caller, then derives the identity itself and uses that same
object to produce vectors. It accepts no caller-supplied identity label.
Unsupported assets stay publishable as `encoder=unbound` for compatibility; an
identified query encoder cannot match that marker. The existing generation
manifest now reports the persisted encoder identity, and the Legal read facade
lazily exposes shared generation references and identity helpers alongside the
canonical projection version and projection functions.

`embedding_generation_matches_encoder(...)` is the generic selected-generation
gate for runtime consumers. It recomputes identity from the supplied encoder
object and requires a selected complete generation plus an exact match on
basis kind, projection rule, model, device, dimension, and generator rule. The
Legal rule-version wrapper delegates to the same kernel serializer; it does not
maintain a second rule implementation. C05 has added the Catalog read-facade
export and wired its query consumer through this matcher; a same-dimension,
different-weight encoder is refused before its `encode` method is called.

`hnsw_index_matches_vectors(index, matrix)` verifies actual native index labels
and stored vectors. `generation_basis_matches_members` and
`GenerationIdentity` are re-exported from their existing canonical owner in
`kernel/io/generation_basis.py`; this lane adds no parallel basis type or
member verifier.

## Pattern pass and boundary

- `P27`/`P31`: reuse the existing generation basis owner and put encoder
  binding in the shared generation builder.
- `P29`/`P32`/`P33`: tests execute the producer and native HNSW path, mutate
  actual encoder state and tokenizer assets, and include a divergent callable
  control. No caller-supplied hash is accepted as proof.
- `P37`: the identity predicate is recomputed from loaded assets. Missing or
  unsupported assets persist as `unbound`; consumers comparing an identified
  query encoder must refuse that generation.
- `P38`/`P40`: the expected property may be read as executable encoder
  equivalence. The implementation actually tests loaded weights, module
  configuration and tokenizer assets. An unchanged asset set with a replaced
  `encode` method changes vectors while preserving the digest; the test
  `test_encoder_identity_does_not_bind_replaced_encode_behavior` demonstrates
  that exact divergence. This is the already-known C12 encoder-callable
  provenance residual, at the same class. It is bounded here; this lane adds no
  deeper object-introspection repairs.
- `P41`: the first observed TDD red at slice base `9e89dddf` was the expected
  missing-helper ImportError. A later focused red reproduced the interface gap
  against the live Catalog caller (`encoder=` was not yet accepted); the shared
  builder now supports that input by deriving identity from the object itself.
  Neither red is being relabeled as inherited failure evidence.

The smallest missing closure mechanism is a trusted local encoder provider
that binds the executable implementation and invocation to the weight,
architecture and tokenizer identity, and prevents an arbitrary replacement
callable from being used under that identity. The current Legal query provider
recomputes loaded-asset identity plus device and dimension, but still returns
the mutable encoder object and does not bind its callable implementation; it
does not close this residual. A fresh lexical walk of all 2,707
`policy-engine/src/polisyos/**/*.py` files found direct `SentenceTransformer`
construction sites in Data Forge and Foundry. The complete occurrence output,
including its `*.py` path denominator, is in `checks/provider-census.stdout.txt`.
The Foundry adapter exposes `embed()` and keeps its model private; it does not
provide the Data Forge identity contract.

Options for a later G decision are:

1. Keep this as candidate compatibility metadata and allow vector reads only
   when the serving route resolves a trusted local encoder configuration. The
   callable residual remains explicit.
2. Extend the existing Legal query provider to bind or own the executable code
   path as well as loaded assets, with a falsifier that replaces the callable
   while keeping assets fixed.
3. Fail closed for vector search until that provider exists, surfacing the
   existing text-only/refusal mode to the caller.

This lane selects option 1 only for candidate verification. It makes no claim
about authentic production assets, present-day law, model quality or authority.
The I4/C12 peer lane contains a producer-to-HTTP witness; the root integration
pass owns the capability-level status and final route assessment. This shared
identity helper does not by itself establish serving authority or executable
encoder provenance.

## Verification

The test file was first run before implementation and failed at collection
because `derive_encoder_identity` was absent. Its complete observed output is
in `checks/test-red.stdout.txt` (exit 2). The missing injected-encoder contract
also had a focused red; its complete output is in
`checks/injected-encoder-red.stdout.txt` (exit 1). The first serial focused run
passed all 10 tests in `test_encoder_identity.py` and `test_embeddings.py`; its
output is in `checks/focused-tests.stdout.txt`. After adding the runtime matcher
and Legal read-facade exports, a second serial focused run passed all 12 tests;
its output is in `checks/read-api-matcher-tests.stdout.txt`. That API had a
focused RED before implementation, retained in
`checks/generation-matcher-red.stdout.txt`. The Catalog currentness integration
passed alongside all 8 encoder tests (9 total); its output is in
`checks/catalog-query-matcher-tests.stdout.txt`. Ruff check and format check
passed for the three owned Python files, with full outputs in
`checks/read-api-matcher-ruff.stdout.txt` and
`checks/read-api-matcher-format.stdout.txt`. Three focused typed-empty-generation
selector/reader checks also passed; their full output is in
`checks/typed-empty-contract.stdout.txt`. The release-fragment TOML parsed
successfully; its output is in `checks/release-fragment.stdout.txt`.

The fresh-process Legal facade import left all kernel/domain modules unloaded;
the full output is in `checks/legal-readapi-lazy-import.stdout.txt`. A scoped
AST import-boundary walk found no direct Data Forge kernel/domain imports in
the 47 Python files under `src/polisyos/lex`; the path/type denominator and
result are in `checks/lex-readapi-import-boundary.stdout.txt`. A broader
Phase-6 read-API test attempt remains non-green in the shared candidate due to
additional failures in `read_api/ukraine.py` and unrelated runtime sources; its
full output is in `checks/read-api-lazy-tests.stdout.txt`. I do not classify
those broader failures as inherited.
The focused read-api surface, Legal no-Lex import, and top-level laziness tests
passed; their output is in `checks/read-api-targeted-contract-tests.stdout.txt`.
The final focused wave passed all 19 shared encoder, embedding, Catalog
currentness, Legal producer/read-facade, and top-level read-API import checks.
It includes the live-encoder assertion guard for the precomputed-vector seam
and an unsupported-asset `unbound` negative; its full output is in
`checks/final-focused-tests.stdout.txt`. Ruff, format, `py_compile`, and the
updated release-fragment TOML checks passed, with outputs in `checks/final-ruff.stdout.txt`,
`checks/final-format.stdout.txt`, `checks/final-pycompile.stdout.txt`, and
`checks/release-fragment.stdout.txt`. The isolated aggregate
read-api laziness check still fails while importing `read_api.ukraine`; the
captured failure is in `checks/known-ukraine-facade-failure.stdout.txt`. Legal's
import had already passed in that aggregate test; the remaining failure is
outside this lane. The updated release fragment parsed successfully, recorded
in `checks/release-fragment.stdout.txt`.

The staged/commit/public-surface generated inventory readback remains with the
root integration pass, after the peer facade and served-route deltas settle.
