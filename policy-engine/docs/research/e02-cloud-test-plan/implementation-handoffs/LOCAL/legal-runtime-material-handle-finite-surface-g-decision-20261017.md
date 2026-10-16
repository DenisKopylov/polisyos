# G choice: finite public surface for the Legal runtime-material handle

**Status:** decision required; no source edits, public-surface flag, or formal closure proposed.\
**Scope:** `LegalRuntimeMaterialHandle` exported lazily from `polisyos.data_forge.read_api.legal`; this packet does not reopen the other 13 public-surface rows.\
**Owner in the unreleased compatibility row:** `team-data-forge`. The enclosing release fragment names `team-polisyos` as release owner. Neither identity is treated as G authority.

## Decision requested

Choose whether E02 should narrow the existing exported handle to a finite typed facade before this candidate is released, preserve the current dynamic proxy as an explicitly versioned compatibility surface, or retain the current proxy and hold any completeness claim. The source does not establish whether an external caller relies on arbitrary model members: the class is exported through an explicitly `public_experimental` facade, while the enclosing fragment remains unreleased. The full in-repository source scan found concrete producer and reader needs but cannot enumerate external callers.

Recommended direction: make the handle a finite facade, if G confirms that narrowing this unreleased experimental surface is acceptable. The recommendation is an API-boundary choice, not an assertion that compatibility risk is zero. Until that choice is recorded, keep this row's inventory review false and describe its full surface as `not_established`.

## Observed property and implementation

`LegalRuntimeMaterialHandle.__getattr__(name: str) -> object` performs `getattr(self._model, name)` with no allowlist. The read facade's `_EXPORTS` and `__all__` expose the handle. Consequently the public class resolves attributes and methods that are not named in the Legal API, including methods supplied by the pinned SentenceTransformers object. `encode` itself is explicitly overridden to raise `query_encoder_call_requires_shared_gate`; arbitrary other members still pass through.

The current callers make a one-line removal incorrect. Legal generation assigns the handle to `model`, reads its device and embedding dimension, and passes it through the generic live-encoder identity calculation and precomputed-generation publisher. That identity calculation introspects model parameters, buffers, modules, tokenizer data, and configuration. The fresh reader reads device and dimension through the handle, checks its defined `encode` method is callable, then invokes only `encode_for_query` under the owner lease. The typed producer and reader methods therefore exist, but their surrounding shared implementation currently treats the handle as a SentenceTransformer-shaped object.

The complete AST source denominator was 2,772 recursive `*.py` files under `policy-engine/src/polisyos` (59,469,889 bytes). The census pins every input path and SHA-256 in `own-source-caller-census.json`; its path/size/hash manifest digest is `077187e595b8f5d37ebc01ef4eb22aeced48fd6fa2055b2a1717847ae1263a3a`. Six files contain direct owner/handle import or call references: `data_forge/domains/legal/batch/cli.py`, `data_forge/domains/legal/batch/embedder.py`, `lex/knowledge/search.py`, `lex/knowledge/store.py`, `runtime/http/container.py`, and `runtime/http/profiled_server.py`. The class and lazy export are defined in `data_forge/domains/legal/runtime_material.py` and `data_forge/read_api/legal.py`. The decisive line anchors are `runtime_material.py:758,831,834` (public class, catchall, and direct-encode refusal), `read_api/legal.py:212,303` (lazy export map and facade resolver), `batch/embedder.py:223,287,306,332,413,437` (dimension, leased generation call, live-identity recomputation/publication, and assigning the handle to the model slot), and `lex/knowledge/store.py:1312,1328,1337-1340,1418,1436` (owner-resolved handle, model-shaped reader probes, and leased query call). The generic identity implementation is `kernel/embeddings.py:220-260,667-780`; it inspects live model parameters, buffers, module lists, and tokenizer assets. These line addresses are grounded by the path/hash pins below. AST caller absence does not establish absence of outside users.

## Source-bound behavior probe

`surface_falsifier.py` imports the actual lazy read facade and canonical handle, creates a source handle over a controlled fake model, and invokes the observable attributes. The deciding output is `surface-falsifier.stdout.txt` (`a71c35e2bb9357d5384f87799d066cc5b85b523b39a12b0474b17653fe5876c6`). It shows:

- the lazy facade resolves the canonical handle object;
- an arbitrary backend value and an unlisted backend method are forwarded;
- direct `encode` still returns the typed shared-gate refusal;
- a finite wrapper with the current explicitly named handle methods denies an unknown backend attribute; and
- simply passing that wrapper to the existing generic live-identity helper fails because the helper needs the model's named parameters and buffers.

This is a behavior probe with a synthetic model, not a production runtime receipt or a complete finite-facade implementation. It falsifies both “the handle is already finite” and “delete `__getattr__` with no companion changes.” A bounded implementation needs an owner-controlled private identity bridge and explicit reader properties or a handle-aware reader contract; it must not expose arbitrary model attributes to make generic identity work.

## Choices and impacts

**A. Narrow this experimental handle in place (recommended, subject to G compatibility decision).** Keep the existing explicit binding/version/identity/lease/producer/query API. Add only the finite reader attributes justified by the current route, or move those checks behind typed handle methods. Route generation's live material measurement through a private owner-controlled bridge so the generic kernel identity API can remain available to ordinary encoders without the public handle impersonating their full model object. Remove generic forwarding. Update the Legal embedder, shared reader, and their integration/removal tests together. Persisted generation schema and HTTP DTOs need not change; unknown external dynamic attribute use would stop working and needs a release migration note. This keeps one public handle and avoids making an arbitrary upstream library API part of PolicyOS's public contract.

**B. Keep legacy behavior under an explicit versioned proxy and add a finite handle.** This preserves callers that intentionally use arbitrary SentenceTransformers attributes, but introduces a second public type, owner return/migration choices, version/deprecation semantics, additional tests, and a permanently broader legacy surface. The legacy route cannot receive a finite-surface attestation merely because its name contains a version.

**C. Keep the current proxy and hold completeness.** This avoids an immediate compatibility change, but accepts the entire dynamically delegated model API as the observable surface. The public inventory remains unresolved; source pins for the current SentenceTransformers runtime do not make the forwarded method/property set a finite PolicyOS-owned contract.

There is no evidence here to select B, no finite route contract in the source to settle A as a no-break routine edit, and no consumer evidence that makes C complete. G should record the compatibility policy and effective owner before source freeze. No blanket waiver or expiry is proposed.

## Acceptance boundary and next check

After G chooses A, B, or C, the next engineering check is limited to this same mechanism: reconcile the selected type's actual normal-import exports and signatures, exercise the complete producer → persisted generation → fresh reader route, retain direct-encode refusal and owner-binding checks, and add one unknown-attribute removal control while preserving explicit positive members. For A, also show that the identity helper recomputes real live material through the owner-private bridge and that a false member, changed callable, or mutated model still refuses. For B, prove old and finite versions are distinguishable at construction and that the old route does not silently become an authority path. For C, retain this row as unresolved and do not mark the dynamic public scope reviewed.

This packet proposes no closure IDs and no public-surface flag. It makes no claim about legal authority, production model selection/currentness, external use, or G acceptance.

## Pattern pass

- `P03` hidden internal richness and `P32` trust-by-form: arbitrary model capabilities are publicly reachable while the prose names a narrow owner handle. The corrective pattern is a finite facade with a private, typed identity bridge.
- `P29`/`P38`: the probe observes actual unknown-attribute forwarding; static export-name or release-row checks would miss the divergence.
- `P40`: this is the already-classified same-class/deeper dynamic-surface finding. The probe is generic over an unlisted attribute; do not respond with per-member denylist patches.
- Capability state: the producer, persisted generation, owner bridge, reader, verification, and experimental read-facade exist. What is not established is the complete finite public surface and its compatibility policy; do not convert this API-scope decision into legal or production authority.
