# Native receipt source references

The packaging-only correction at `f4cb360eb6dc114969e9ae90d188449fbeda1f9e` replaces fifteen
complete canonical bundle bodies in three receipts with exact Git references. Each
`canonical_card_text_ref` carries the original source SHA, repository path, blob ID,
raw SHA256, byte count and locator. The original source is
`198076863e143dea9f89f02734b13d50dae3eed5`; use `git show <source_sha>:<path>` to read it.
Original finding fragments and acceptance paragraphs remain in each criterion row.

Prior receipt and payload hashes remain historical bindings. Resolve them at the
published commit carried by the receipt, rather than comparing them to a changed
packaging view at HEAD:

- `native-champion-publication.json`: `b2fefca972c4fddb8cd372a3c4cef0f0de94fca0`
- `native-champion-publication/original-finite-criteria.json`: `eb5e5fe59d73e5eb46325a754675a04b6dd2a7cd`
- `native-doe-default-factory.json`: `0f8802c2bb90fe05676c2273703364c0c491ea35`

The current views supersede only their full-bundle body packaging. Their original
Git blobs, old byte hashes, execution evidence, fixtures and complete deciding
outputs remain intact. `native-receipt-packaging-correction.json` lists all fifteen
replacements and the exact old and new receipt identities. A path and raw hash
from an older payload manifest continues to denote its historical source version.

The separate full read-only audit covers all 337 changed D JSON/gzip/XZ transports
between `cae5589aa7080b628e93d594eeb4ff7c2fc2414d` and
`1ff34d2657aee4e8702cb88486448659accf2466`. It identified 29 full tracked-source copies:
14 lesson source-input bodies owned by the transfer lane, and the 15 bundles corrected
here. The unique pre-commit ask-failure oracle and five complete deciding outputs
retain their bytes. This is a packaging result; it supplies no runtime or numerical
verdict. Later transports require a source-qualified delta audit and the correction
requires independent review.
