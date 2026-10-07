# Независимая delta-приёмка B finite getter composition

**Решение: bounded GO для этой JIT/getter source-and-test leaf, без нового finding closure.** Это новый код для текущего G 855cb26 (файлы helper/test там отсутствуют), но содержимое implementation и теста байт-в-байт совпадает с уже рассмотренными PR #55 af03a9d. Рассматривать как один и тот же source leaf с дополнительной handoff/evidence carrier, не как второй независимый runtime implementation. Не интегрировать обе копии. B74 и отдельный branch write-scope HOLD сохраняются.

## Pins и footprint

- Pinned ref origin/codex/e02-B-current-composition=71afa5796b7a1b89cc94d9b6d4a0394d6117aab0, tree 7c4fc6b42b578bf3d2781a438a88b46ce9e5c475. Exact comparison base 5cd7d962f2bf87bc872e01365778858adf52ba9f is an ancestor. The committed handoff names slice base e82ac5834ee481051f905edfe0bd68ba19dcc6ad and implementation source 7c05686dbd8427fa2e8bf217827046acef097058, tree 1c705c31775935039c2823b0c70f9f1f090f1411; the handoff base is an ancestor of that source.
- Delta from 5cd to pinned 71: **99 paths = 96 handoff/evidence paths + 2 paths under policy-engine/src/ + 1 test**. The handoff’s full implementation union from its earlier e82 slice base is 175 paths and also includes an already-present release fragment. Its metadata reconciliation records 169 payloads / 1,665,243 bytes, 45 lossless output identities decoded and zero mismatches. The different 99/175 denominators are incremental versus full-slice footprint, respectively.
- Changed runtime/docs/test paths have the same Git blobs at PR #55 af03 and composition head 71: _implementation_identity.py 7f0d0323474ee2f8f1fe4adea316c5260159262e, README 6bf7f04f66eb0acc0fb90a175592da3cc3092c2f, and test_module_source_identity.py d54e5ddaeb0f8e2e50d8941ccf1adb639c4071ff. The test is 21,776 bytes / SHA-256 b9a95dc7959eb3fb8094a3875a2419444867770ed8e29a9f73ced5d21c76767d, matching the current terminal-native input. No public API/schema change is introduced.
- The handoff says closure_ids=[], formal_closure=false; its source review was source-only. G’s separate write-scope HOLD is unaffected: state_branching.py is not in this 99-path delta.

## Runtime property and evidence

The change addresses one finite getter-admission escape: recursive nested code can contribute a same-named global to flattened captures and conceal that the actual root function binds a different nonlocal builtin. _root_function_captures preserves Python binding precedence; root getter aliases are always routed through _data_field_getattr, which refuses when the flattened discriminator does not match the actual root value.

The adversarial test uses a root alias reader=getattr, a runtime selector, and a nested global reader reference whose module value is abs. Before the fix, the same test on source 515669fd11f0a96f866cb5c0dc5306c6aa39c962 failed with the producer body’s filesystem effect ["body"]. On exact source 7c, the final 128-case run includes GetterCollisionSource plus the three sibling selector/iterator/closure cases; all four pass with typed refusal before effects. This is a behavioral discriminator against the flattened-capture proxy.

The exact-source 5-file terminal-native run reports 127 PASS / 1 FAIL, with 168 observed module origins reconciled to Git bytes (universal_readset=false). The sole failure is the already-known B74 returned-frame/global namespace case: resume returns 107 instead of 7 and executes the replacement effect. The nine defining JIT consumers pass; both non-JIT/JIT numeric warm-handle cases pass (20/30), and the existing finite-getter removal control fails as expected. The pre-fix getter-collision execution is a direct red control; the separate removal receipt removes the finite admission property generally, not only the new root-alias branch.

This is same current 7c evidence already qualified against af03 in the tenth-wave B review. No additional 128-case replay is warranted. The four-case test_imported_module_checkpoint_identity.py is **not** in this handoff’s changed paths or any current terminal-native selector, so this receipt does not satisfy that separate focused check if PR #55’s broader JIT admission still requires it. That remains a one-file check, not a reason to repeat the broad cohort.

B74 remains LIMITED: this finite root-binding fix neither proves arbitrary builtin-returned context identity nor changes the observed frame replacement. The new receipt does not clear the separate state_branching producer/write-scope HOLD, nor classify the old 6fa red as inherited (P41=not_established).

Read-only review only; no test, environment, ref, or source mutation.
