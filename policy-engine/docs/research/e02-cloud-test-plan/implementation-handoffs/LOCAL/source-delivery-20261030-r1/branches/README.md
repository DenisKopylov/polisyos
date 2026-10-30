# Branch history delivery

The inventory records every local/remote tip observed at delivery start and after fetch. The user explicitly requested all existing branches in origin/main. The live author source already contains the old remote main.

The remaining histories include obsolete/alternative implementations, generated gh-pages and a retained R9 draft. Ordinary merge preflight against the author source reported 202 conflicting tips over 711 distinct paths, 28 clean tips and two unrelated histories. Activating all alternatives would overwrite current mechanisms and unrelated source trees. A single ordinary Git preservation merge includes all 232 maximal remaining histories as parents, retaining the current coherent live source and the delivered code archives. Every input tip is then an ancestor of main; its complete original files remain addressable through Git history. Portable branch code patches are supplied for shallow checkouts. No branch or commit is deleted or rewritten.

This is delivery and preservation of all authored code, not a claim that all alternative implementations run together.
