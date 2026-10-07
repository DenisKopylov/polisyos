# Publication byte and whitespace checks

The first local docs commit retained two Markdown trailing blank lines and two pytest stdout lines containing spaces. The combined shell invocation proceeded to the commit after the custom diff check returned2; no push occurred at that point. G corrected only the two Markdown EOFs with a separate append-only commit.

The verbatim stdout files `outputs/F-graph.stdout` and `outputs/F-existing-positive.stdout` remain byte-identical to deciding output, including their blank-looking two-space line5. They are evidence bytes, not source/style edits. Validation therefore checks prose/JSON whitespace on the complete documentation diff excluding only outputs/, and independently verifies every one of the29 output file sizes and SHA256 values. No repository check or hook is disabled. Normal Lefthook jobs skip this docs-only path scope; those skips are not product PASS.

Both local commits change documentation/evidence only. Independent semantic/link readback GO remains applicable; no runtime source, generated schema or test body changed. Source acceptance and new formal closure remain empty. Remote delivery is confirmed separately after actual push, not predicted by this file.
