# Completed reproducible export moved to native Trash

The exact A332 test export was moved by macOS `NSFileManager.trashItemAtURL` after all tester and diagnostic tasks completed. Parent immediately checked device/inode/mtime and repeated `lsof`; no open handles were found. Native Trash destination identity and absent original path were verified in [the receipt](cleanup-receipt.json).

The export had 3,486 exact Git-bound files and two generated empty locks: 77,930,496 allocated bytes. Both locks were preserved separately. Full deciding stdout/stderr/JUnit, origin audits, source manifests, harness, and the unique synthetic history-divergence fixture remain outside the exported directory. Functional source remains fetchable at the immutable candidate; this is an expendable source copy, not a managed checkout or branch removal.

No production payload was inspected or moved; Trash was not emptied. Moving within the same volume does not establish physical disk-space recovery. The detailed intent remains ignored local evidence at `R/A-332-20261007/cleanup-intent.json`.
