# C54 canonical source inputs

These two files are the minimal tracked inputs needed to reproduce the final C54 table without relying on ignored `.tmp` files.

- `C54-final-reviewcut-20261006-v8.json.gz` is a lossless gzip of the reviewed v8 candidate input. Its uncompressed bytes have SHA-256 `8636e42db8fda1bb9df617cf718ae7e20d39eb11b40639d5ee6471a28160871a`; the gzip bytes have SHA-256 `aa8c96a3dbf38874c750cf0dfdfc94de9be93925dee5ac193a2b37d595579639`.
- `C54-finding-inventory.tsv` is the byte-exact 54-row historical inventory used by the independent final bookkeeping validator. It has SHA-256 `530f61eb0c356a9aa65b99154b233b19aadc09bde3f8f307a85a1f27965d16da`.

The final JSON points its canonical input fields at these tracked files and keeps the original ignored-capture paths in separate provenance fields. The generator and validator read the tracked copies, whose content hashes match the original captures. They contain finding-level audit inputs; no production records or production artifacts are included.
