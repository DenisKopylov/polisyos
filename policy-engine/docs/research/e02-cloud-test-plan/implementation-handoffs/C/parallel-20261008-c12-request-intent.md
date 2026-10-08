# C12 Legal request intent preparation

Original owner/unit: C, EMB-03 / LA-040. This is a source proposal, not executed runtime evidence or G finding closure.

Selected base is Legal c60e37e7833b2dbb22af1868e31dc3f519d6a4f2, tree 8c9eb49a9a7096ed564f74e91b6f7f1bc1f2b714. Its direct source parent is f428b114f4afb5c9cdde93a8e9bf036abe5ac329. C-root carrier b886665a26b318b2fdd136cae0248cdea7b9226d is not the Legal source freeze. Published G instructions are f00dd7661a8d3329fb1fa1b049decb0d1d2f277b, tree d9a4e73a0e85fa11f865bf643c1b63fbe66c2767.

The current Legal mechanism independently resolves selected generation bytes, reconciles current projected owner membership and matrix/HNSW pairing, derives live weights/tokenizer identity, encodes text, and checks identity again. Its missing observed quantity is request intent: c60 can accept newly selected G1 while a caller still expects G0, even when assets/corpus are identical.

The proposal attaches immutable LegalQueryProfile snapshots to existing LegalQueryInput and passes them through LegalKnowledgeGraph(query_profile=...). LegalQueryProfile.from_generation() freezes the existing EmbeddingGenerationRef inventory into canonical bytes; it does not verify a model or confer authority. Genuine primitive strings/bytes are enforced at snapshot construction; mutable bytearray or malformed fields cannot masquerade as frozen intent. The inventory embedding_model is the requested model; legacy Graph embedding_model remains an ignored compatibility label. Store compares exactly one snapshot for the requested table with freshly resolved inventory before encoding. Missing, malformed, foreign-table-only, duplicate, and stale snapshots refuse. Empty sibling tables do not impose an all-of gate.

Migration:
1. C05/G select the relevant admitted effective-profile/catalog source and currentness recipe. There is currently no newly admitted generic profile carrier or invented profile_ref field.
2. C10/A map the actual incoming request's existing effective profile to its local Legal DB/index paths, an explicit retained expected EmbeddingGenerationRef snapshot for each requested table, and the matching live query encoder provider.
3. Freeze selected refs using LegalQueryProfile.from_generation(ref), pass the tuple and query_encoder to LegalKnowledgeGraph, and keep the request's intent fixed for the operation. Do not silently regenerate expected intent from a later selector to bypass refusal.
4. When a new generation is intentionally selected, construct fresh request snapshots and a fresh reader. On unsupported profile, preserve LegalQueryProfileError or hybrid text fallback with its typed status.
5. G alone handles shared facade/generated API/reference companions after exact lease; this proposal does not write them.

Minimum relevant I1/Catalog packet: exact source/test/config/companion blobs and source DAG admission; existing effective run-profile/policy resolution plus complete currentness inputs; the actual consumer-to-profile mapping needed by this Legal invocation; the criterion-specific unchanged positive/same-ID mutation discriminator and exact deciding outputs. CatalogRunProfile names do not establish Legal encoder identity or legal authority.

Minimum L01/L02 production packet, locally read-only: actual request purpose/effective profile; logical DB/index locations; selected complete generation IDs/inventory/basis/output descriptors for requested tables; local encoder provider and library/config/weights/tokenizer identity, model/device/dimension/projection rule pairing; actual ordered projected owner membership and matching matrix/HNSW readback; source-law/purpose authority only if a production claim needs it. Absence keeps production supported-profile authority not_established. No production corpus or embedding assets are uploaded.

P37 predicate classification: request intent is consumer_asserted selection, never authority. Actual pairing, asset identity, normalization, membership, and matrix/HNSW consistency are to be recomputed by the existing runtime; their new proposal execution is UNRUN. Production input/authority remains not_established. P38 divergence is G0 intent versus G1 selection with unchanged assets/dimension/corpus: current asset matching can pass but the requested selection differs. P40 bucket is the same query-binding class one level deeper. After this canonical quantity is widened, arbitrary encode-callable attestation remains a bounded residual: asset/config/tokenizer hashing does not attest replaced executable behavior. The smallest closing capability is trusted encoder/library/config or independently attested callable provenance; it is not established in this offline preparation. A controlled same-assets encoder that returns the wrong normalized direction is its falsifier, native UNRUN, not a further source repair mandate.

Proposed targeted verification from an admitted checkout:
- Locked Python 3.14, NumPy, DuckDB, native hnswlib; exact source/module/backend origins.
- pytest -q tests/unit/remediation/test_emb_03.py (the existing complete owned semantic file).
- Fresh-reader same-profile positive; requested wrong/missing/unpaired/duplicate/malformed profile refuses before encode and native knn.
- Rebuild unchanged corpus/assets to G1, retain G0 intent; zero-call refusal. Remove only _require_query_profile in isolated test context, preserving actual encoding and native HNSW: target retrieval proves selection pairing was necessary. Restore: refusal. Fresh G1 intent/reader: target.
- Existing same-dimension wrong-weight target/decoy removal, pre/post encode mutation, rule-version refusal, selector concurrency and membership remain distinct maintained checks.
- Changed Python Ruff/type/import checks and architecture guardrails; release/API/facade migration checks by G on the composed source. No broad A–F replay.

No shell, Python, filesystem, host admission, source mutation, tree/commit/ref publication, native test, wheel, production read, importer check, or runtime authority claim was performed. The only preserved artifact is an unattached Git blob packet with full proposed source/test/owned companions and exact pinned input references. Apply only after an actual admitted host/path lease and independent delta review.
