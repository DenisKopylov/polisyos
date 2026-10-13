# R1159 independent review: composed native repair and formatter

## Verdict

**GO to apply R1165's 13-path independent set and run its focused native replay. WITHHOLD the R1160 24-path composition and the R1158 15-path composition.** The 24-path union contains the entire protected R1138 11-path mechanism, which independent review R1155 blocked. closure_ids=[].

## Exact composition boundary

R1165 is bound to branch codex/e02-unified-local-20261009, HEAD 5fd4096ab9389d15abcedb00b03b968f6b60c953, tree d65d5ba135001d29968734cb0bace6fe50a572b8, and R1151 frame root-author-source-frame-r1151-20261013.json@12e262d19976b9a2ca4642cbe228f89e671dbfe09c957fb23ae058e8c4d84213.

The exact selected patch is raw/r1165-independent-search-stress-grounding-source-20261013/net.patch@7f6770458ae920b34fb3df91d8d8db2899341939b11ac77f3dcc61c14467e4c5; composition.json@85ea5330e1834da2058c41d199e14e68cb5fc5b19febb34aa063b6bacc4cd33d records its 13-path final set. I reconstructed the patch in memory: all 13 postimage hashes and byte counts match, all 13 preimages match the current checkout, and all 13 postimages are byte-identical to their entries in R1160. The patch is disjoint from all 11 R1138 protected paths.

The independent set preserves three complete mechanisms: Search prompt admission (2 paths, R1150 GO), stress negative-control routing (2 paths, R1149 GO), and grounding snapshot materialization (9 paths, R1152 GO). The protected R1138 R2 set is a separate mechanism and remains withheld in full. R1155 found that a nested previous_pointer suite ref can pass metadata-shape and ref-syntax checks without resolving its selected bytes and binding the decoded suite_id/version. No partial protected patch is admitted.

## Formatter and source qualification

Across the original 15-path composition, I compared the complete R1157 pre-format and R1158 post-format Python postimages. All 13 ASTs are equal; exactly seven Python files changed bytes due to formatting. The R1165 independent selection carries the two relevant Search formatting changes, each AST-equivalent to the reviewed pre-format postimage. P40 is SAME_CLASS_DEEPER for this formatter debt, with the complete seven-file formatter set accounted for. P41 is not inherited: Root's formatter reds intersect the source slice and are repaired in it.

The R1151 frame has 568 physical entries. Six grounding paths in R1147's nine-path set are absent from that frame map; their current direct source hashes nevertheless match R1165's preimages, and the nine-path candidate was independently qualified by R1152. I make no inherited-red claim.

## Verification limits

R1165's retained root-quality receipt has 24 configured Ruff commands over its 12 Python files; every command exits 0 and binds the exact candidate bytes. My earlier independent 42-command replay over R1160 also exercised these same selected Python postimages. R1165's patch passes git apply --check. I did not run pytest or native checks; Root should run the focused 13-path source replay. The withheld 11-path protected property remains BLOCK, and the full 24-path composition is not approved for application.
