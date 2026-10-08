# Completed E exports moved to native Trash

Two reproducible source copies for exact E8d were moved by the native macOS Trash API after before-action inode/device/mtime and open-handle checks. [The receipt](cleanup-receipt.json) verifies both destinations and absent source paths. The tested export and the unused wrong-locator duplicate total 153,796,608 nominal allocated bytes; this is not an APFS physical recovery estimate.

All deciding outputs, harness, source manifests, compact reports and six preserved generated/provenance files remain outside the targets, with matching hashes. No production payload was scanned or moved. Trash was not emptied; permanent deletion was not performed. Source remains fetchable from the original immutable E commit.
