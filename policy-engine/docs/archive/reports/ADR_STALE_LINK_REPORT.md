# ADR Stale Link Report

Generated from selected Markdown files in `docs/adr/`; timestamp is source-controlled.

Input selector: `tools.lib.fs.iter_repository_files(REPO_ROOT)` paths whose parent is `docs/adr/` and suffix is `.md`.
Selected source inventory denominator: 191 documents; excluded filename rules: `AUTHORING.md`, `README.md`, `_template.md`, `by-topic.md`, `index.md`, `template.md`.
Source inventory SHA-256: `6d65fd3650a20b3a1fe229fca5adb14dbe6546cc05699498f0012131ae61f52d` (sorted selected paths and each UTF-8 content SHA-256).
Unresolved by construction: when Git metadata is available, untracked worktree paths are not selected; standalone-directory fallback enumerates filesystem paths. The Markdown-link regex does not implement full CommonMark; reference, nested, multiline, escaped, code-context and raw-HTML links, non-Markdown assets, external availability and fragment targets are not comprehensively checked. Git/process reads are not file-read receipts; parsed ADR status and relation fields do not prove decision authority or implementation.

No stale ADR references were detected.
