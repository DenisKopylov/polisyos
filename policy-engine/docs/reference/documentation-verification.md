# Documentation Verification Contract

Owner: team-docs
Source pin: `6fd47dc693b8f79993876bc28a55421cc0196027`

Source of truth: `tools/registry.py`, `tools/cli.py`, `tools/devx/workspace/docs_style.py`, `tools/devx/workspace/_repo_hygiene.py`, `tools/quality/validation/check_docs_gate.py`, `tools/quality/validation/check_docs_accuracy.py`, `tools/quality/validation/check_docs_freshness_baseline.py`, `tools/quality/validation/check_docs_lifecycle.py`, `tools/quality/validation/check_docs_rendered_links.py`, `tools/quality/validation/check_docs_source_bindings.py`, `architecture/tooling/tool_config_split.toml`, `docs/how-to/author-measurement-instruments.md`, `tests/repo_quality/tools/test_docs_gate.py`, `tests/repo_quality/tools/test_docs_source_bindings.py`, and `tests/repo_quality/tools/test_docs_rendered_links.py`.

This contract is for authored Markdown changes in `policy-engine/`. A passing check proves only the property and input set named below. In particular, a green “freshness” result does not establish that every repository document is current or that every factual claim is true.

Review note: the original style, path-aware gate, accuracy, freshness and lifecycle sources were read at snapshot `47e1e59b569a5b922611f71a7f53fb6320abea4c`. The review traced dispatch decisions, input selectors, parsers/read receipts, and verdict/exit mapping against the implementations and mirrored tests. This third pass also read the rendered-link and source-binding implementations, their mirrored tests, and the publication-config gate plan. The test files were reviewed as source; this note is not evidence that they ran. The new tools and publication-config dispatch are source-bound to implementation commit `6fd47dc693b8f79993876bc28a55421cc0196027`; their source and mirrored tests were inspected there before the final build freeze. The closeout report records actual command execution separately. This note records review scope, not a universal source-pin requirement.

## Local verification path

Run commands from `policy-engine/` after the authored page and any publication navigation change are complete. On a low-disk workstation, reuse an existing compatible `policy-engine/.venv` with `UV_NO_SYNC=1`; this prevents `uv run` from syncing dependencies. It is not a clean-install check. This setting does not prevent `pre-commit` from initializing its separate markdownlint hook environment, so `docs-style` also requires that hook environment to be available. If either environment lacks a required extra or command, record that check as unavailable/`UNRUN` rather than installing into the shared environment or treating it as green.

```bash
UV_NO_SYNC=1 uv run polisyos-tools workspace docs-style docs/reference/documentation-verification.md
UV_NO_SYNC=1 uv run python tools/quality/validation/check_docs_gate.py
```

The first command runs the configured `markdownlint-cli2` hook against the named file. The second command computes the docs-sensitive change set from Git and dispatches checks based on the changed paths. For a change under `docs/**`, the gate plans the docs-freshness baseline check and a strict MkDocs build. A change under `architecture/tooling/mkdocs/**` or `mkdocs.yml` plans docs-lifecycle validation and generated tool-config validation, followed by docs accuracy and a strict MkDocs build. The gate stops at the first failed command, so a failure can leave later planned checks unrun; a plan that includes a child is not evidence that the child ran.

The path-aware gate does not run Markdown lint. Keep the targeted `docs-style` command separate. `check_docs_gate.py --changed-path <product-relative-path>` can be used to inspect or reproduce a plan for explicit paths; explicit paths replace Git change discovery, so the normal command is the evidence for the actual worktree change set.

Prefix the commands below with `UV_NO_SYNC=1` when reusing the existing compatible product environment described above.

For a new page under `docs/reference/`, add it to the source navigation fragment `architecture/tooling/mkdocs/nav/30-reference.yml`. Do not edit `mkdocs.yml` or `architecture/tooling/mkdocs/generated.yml` directly. The fragment and generated outputs are declared in `architecture/tooling/tool_config_split.toml`; `uv run polisyos-tools workspace tool-configs` renders them, while `uv run polisyos-tools workspace tool-configs --check` is read-only and verifies generated-file drift plus dead override state. The path-aware gate dispatches the `--check` form when the navigation fragment changes.

## Choose checks by change

| Change | Checks to run | What the result establishes | What remains outside the check |
| --- | --- | --- | --- |
| Authored Markdown wording or structure | `workspace docs-style <changed-paths>` and the path-aware docs gate with normal Git discovery | Markdownlint rules for the selected authored-file scope; then the path-aware checks triggered by actual changed paths | Style does not check links, truth, freshness or publication. The path-aware gate does not run Markdownlint and stops at its first failed child. |
| Authored page under `docs/**` or a published README | `validation check-docs-freshness-baseline` and `python -m mkdocs build --strict` (both are dispatched by the path-aware gate for these paths) | Actual MkDocs included Markdown selection, the registered zero-violation baseline, and strict-build diagnostics | Accuracy does not validate prose, raw HTML/assets, root URLs, fragments or external liveness. A strict build can leave excluded-page links at `INFO`; it is not a complete reachability check. |
| MkDocs publication fragment/config changed without a page edit | The path-aware gate plans `validation check-docs-lifecycle`, `workspace tool-configs --check`, `validation check-docs-freshness-baseline`, and `python -m mkdocs build --strict`, in that order | `test_publication_config_changes_run_accuracy_and_strict_build` asserts all four children for MkDocs fragments and `mkdocs.yml`; the publication-set checks are now planned even for fragment-only changes | The first nonzero child stops dispatch. In the recorded partial lifecycle state, lifecycle returns `UNRUN` (exit 2), so generated-config, accuracy and strict-build children later in that gate invocation are UNRUN even though they were planned. Run/record those children separately if they are needed to complete evidence. |
| Generated reference or split configuration | The canonical producer's `--check` command; `workspace tool-configs --check` for outputs declared by `tool_config_split.toml` | Only the output families and source/output pairs owned by that producer; tool-config check also checks dead override state | There is no repository-wide generated-document verifier. A green producer does not validate unrelated generated pages or semantic correctness of its source. |
| Source and emitted-site links | Source accuracy check; build the site under `_build/`; then run the standalone rendered-link checker below | Source accuracy covers supported Markdown page links against actual MkDocs inclusion. The rendered checker reports the emitted tree denominator and HTML/CSS read hashes, checks supported local targets and HTML fragments, and distinguishes `PASSED`, `FAILED`, and `UNRUN` | The rendered checker is standalone: it is not registered in the path-aware gate or CI. Its receipt does not bind the site to the MkDocs source commit or build invocation. External liveness, browser/JavaScript behavior, non-HTML fragments, and unsupported parser forms remain outside its proof. |
| Explicit source-bound page review | `python -m tools.quality.validation.check_docs_source_bindings --repo-root . --doc <selected-page> --against-ref <comparison-commit> --format json` | For each explicitly selected page, resolves its declared source pin and compares the complete tracked path/glob expansion at that pin and the immutable comparison commit by blob bytes and Git mode; JSON reports the selected page, declarations, before/after pattern counts, matched count and drift categories | This standalone check is not dispatched by the docs gate. Equality does not establish that the declaration covers every claim, that prose is true, or that tests, runtime behavior or deployment are current. It ignores uncommitted source bytes; symlinks compare stored target text only; Gitlinks/LFS pointers are `UNRUN`. |
| ADR, plan, archive, redirect, README/AUTHORING or lifecycle contract | `validation check-docs-lifecycle` (also dispatched by the path-aware gate for lifecycle-sensitive paths) | The named lifecycle subchecks run and report their findings; the reference-scan receipt discloses its own tracked/selected/read denominator | The receipt is only for removed-path reference scanning. Other lifecycle inputs are not covered by it. If the reference scan is partial, the command returns `UNRUN` (exit 2), even though other checks ran. Preserve findings; do not narrow selectors to force a pass. |

For the last archived closeout replay, the lifecycle reference scan covered 25,041 tracked paths: 24,823 selected, 218 selector-excluded, 23,879 decoded as text, 941 byte-read as opaque, and three ambiguous. It reported 1,159 unresolved inputs and 10 direct-reference findings and returned `UNRUN` (exit 2). These are snapshot-specific counts from the [maintenance audit](https://github.com/DenisKopylov/polisyos/blob/47e1e59b569a5b922611f71a7f53fb6320abea4/policy-engine/docs/archive/reports/2026-10-14-documentation-maintenance-audit.md), not a permanent repository denominator. The full lifecycle command's receipt explicitly says other lifecycle input families are unmeasured; historical audit markers and archive-map member metadata do not verify backing bytes or source role (P32).

The emitted-link checker is available as a standalone tool. The existing registry automatically discovers both checker modules; they are also callable as `polisyos-tools validation check-docs-rendered-links` and `polisyos-tools validation check-docs-source-bindings`, with the same arguments shown below. This discovery does not dispatch them from CI or the path-aware gate. Regenerate the [tools reference](tools.md) through its existing owner when discovered tools change.

Build into an explicit `_build/` directory, then pass that directory, the resolved MkDocs `site_url`, and an output receipt path under `_build/` but outside the site directory:

```bash
UV_NO_SYNC=1 uv run --extra docs python -m mkdocs build --strict --site-dir _build/docs-verification/site
UV_NO_SYNC=1 uv run python -m tools.quality.validation.check_docs_rendered_links \
  --site-dir _build/docs-verification/site \
  --site-url "$SITE_URL" \
  --output _build/docs-verification/rendered-links.json
```

Set `SITE_URL` to the resolved HTTP(S) `site_url` from the MkDocs configuration. The checker requires both paths to be under the repository `_build/`, does not follow site symlinks, and writes a JSON receipt with the enumerated path-set hash, entry/file-type counts, supported reference forms, findings, and explicit HTML/CSS read hashes. Exit 0 is a complete scan without local blockers; exit 1 is a complete scan with a missing local file or HTML fragment; exit 2 is `UNRUN` for incomplete enumeration, unreadable/unsupported input or an unsafe path. `UNRUN` preserves any findings.

It checks the listed HTML URI attributes, `srcset`, meta-refresh URLs, inline/style-element CSS `url()` and `@import`, and external CSS `url()`/`@import`; it resolves local files and relevant HTML `id`/`name` fragments. Origin comparison uses bounded ASCII DNS labels (case-insensitive while preserving a trailing dot), canonical dotted-decimal IPv4, and bracketed IPv6. Non-ASCII, percent-encoded, and legacy/numeric IPv4 hosts return `UNRUN`; the smallest capability that closes this gap is a browser-equivalent WHATWG/UTS46 origin normalizer, which this checker does not provide. The checker enumerates the site and explicitly reads and re-reads HTML/CSS bytes; the re-read detects observed drift but does not establish an atomic filesystem snapshot or audit all process filesystem access. It does not use HTML5 tree construction, scan JavaScript/browser navigation or unlisted URI-bearing attributes/CSS constructs, fetch external URLs, or resolve CSS/SVG/non-HTML fragments. Its receipt binds emitted bytes, not the MkDocs source commit or build invocation, so pair it with a separately pinned build record. No CI or path-aware gate integration is approved; do not infer that the standard docs gate runs this tool.

The source-binding checker is standalone and opt-in: select pages with repeated `--doc` options. It does not scan every document, and this metadata is not required on every page. Each selected page needs exactly one leading `Source pin` and one leading `Source of truth`. The pin is one full 40- or 64-hex commit ID, optionally wrapped by one pair of backticks; no other characters or final punctuation are accepted. The source field contains one or more backticked paths/globs, with continuation tokens on indented lines. Do not use `::` function-selection syntax: the checker treats tokens as paths, and test references in the body do not select files.

Path namespaces are explicit and stable across invocation roots: `repo:<path-or-glob>` is Git-root-relative; `product:<path-or-glob>` and unqualified paths are product-root-relative. Namespace selection never depends on whether a candidate file exists. Unknown namespace-like prefixes, colons outside these prefixes, absolute/traversing paths, backslashes, braces and character classes return `UNRUN`; a repository-root path must use `repo:`. `*` and `?` match within one component, while a complete `**` component matches zero or more components. A complete equal comparison returns 0; source-set drift returns 1; unresolved pins, malformed metadata, Gitlinks or LFS pointers return 2/`UNRUN`.

A pass proves only byte and mode equality for declared tracked members at two immutable commits, not declaration completeness or claim truth. If a declaration explicitly selects test files, their tracked bytes and modes are compared like other members; the checker does not discover tests from body citations or inspect unselected test files. It never establishes that tests ran or passed. `--against-ref HEAD` resolves the current checker repository's `HEAD`; it does not follow a parallel E02 branch. For a post-E02 comparison, use the canonical owner's frozen integration commit and record the resolved immutable `against_commit` from the receipt. A local ref comparison is read-only and has no lazy fetch, but it establishes equality only against that resolved snapshot—not global source freshness. Do not automatically move source pins or treat a branch name as a permanent freshness guarantee.

## Portable verification evidence

For a decision another reviewer can reproduce, record the documentation-tree commit, the exact base and head used for the changed-path set, and a separate frozen product-source commit when the pages make source claims. A branch name or moving `HEAD` is not a source pin. Capture the full changed-path list separately: the path-aware gate's summary reports a count and abbreviates long path lists. Also retain the exact command and working directory, relevant environment (including `UV_NO_SYNC=1`), exit code, complete stdout/stderr, and SHA-256 for each retained output.

Record the actual coverage output with each result: Markdownlint selected paths and configured exclusions; generated checker source/output pairs; accuracy receipt's MkDocs manifest, navigation/exclusion selectors and read outcomes; lifecycle receipt's tracked/selected/excluded path counts and hashes, successful/failed reads, opaque and ambiguous inputs, and unresolved findings; rendered-link receipt's enumerated output paths and HTML/CSS hashes; and source-binding receipt's explicit page selection, source pin, comparison commit, pattern expansion and drift counts. The lifecycle receipt is specifically `removed-stub-reference-scan-only`; it does not report reads for the other lifecycle checks. The rendered-link receipt does not bind its build invocation or source commit. An incomplete deciding input is `UNRUN`, with partial findings kept visible.

Full raw output under ignored `_build/docs-maintenance/raw/` is retained locally and is not portable evidence by itself. A tracked review record should bind a compact result to the exact source/base pins, command, coverage totals, verdict and raw-file path plus SHA-256; a path and digest identify a local artifact but do not make its bytes available to another checkout. Keep large raw logs out of Git unless the repository's evidence policy explicitly calls for them. The [maintenance audit](https://github.com/DenisKopylov/polisyos/blob/47e1e59b569a5b922611f71a7f53fb6320abea4/policy-engine/docs/archive/reports/2026-10-14-documentation-maintenance-audit.md) shows a pinned example of this format and labels its local-only outputs.

## What each check establishes

### Authored Markdown style

`uv run polisyos-tools workspace docs-style [paths...]` invokes `pre-commit` with the repository's `markdownlint-cli2` hook and `.markdownlint-cli2.jsonc` configuration. With explicit paths, it expands only Markdown files in those paths and skips `docs/archive/`; with no paths, it uses the hook's configured authored-file scope. The hook configuration selects top-level Markdown, `docs/**/*.md`, and nested `README.md` / `CONTRIBUTING.md` files. The Markdownlint config also ignores archive, benchmark, generated site, and research-tool Markdown areas.

This checks Markdown style only. It does not resolve links, build the site, test prose truth, or establish freshness. The implementation is in `tools/devx/workspace/docs_style.py` and `tools/devx/workspace/_repo_hygiene.py`; the hook and rule scope are in `.pre-commit-config.yaml` and `.markdownlint-cli2.jsonc`.

### Docs-sensitive change gate

`uv run python tools/quality/validation/check_docs_gate.py` is path-aware. It maps changed paths to the existing generators and validators rather than scanning every docs-related surface for every change. Its implementation and dispatch table are in `tools/quality/validation/check_docs_gate.py`.

For docs-only changes, the relevant triggers are:

- `docs/**`, `README.md`, and the listed package README paths dispatch the docs-freshness baseline and `mkdocs build --strict`.
- `docs/adr/**`, `docs/plans/**`, `docs/archive/**`, `mkdocs.yml`, and `architecture/tooling/mkdocs/**` dispatch docs lifecycle validation.
- `architecture/tooling/**` and `mkdocs.yml` dispatch `workspace tool-configs --check`.
- `architecture/tooling/mkdocs/**` and `mkdocs.yml` also dispatch docs accuracy and a strict build after lifecycle and tool-config checks; the first nonzero child stops the sequence, leaving later children unrun.

Other paths can dispatch public-surface, schema, API, extension-example, or subsystem evidence checks. The complete path patterns and commands are in the gate source. A docs-only gate result is not a substitute for `docs-style`, and a result from a hand-supplied `--changed-path` set does not prove Git discovered the actual changed set.

### Published-page accuracy and freshness baseline

`uv run polisyos-tools validation check-docs-accuracy --repo-root .` is the direct accuracy check. The docs gate calls `uv run polisyos-tools validation check-docs-freshness-baseline`, which runs that same checker and applies the registered baseline rules from `architecture/exceptions/docs_freshness.toml`.

The page denominator is MkDocs' actual included-file set from
`load_config()` and `get_files()`, including unlisted pages. Navigation policy
is checked separately: both `nav` and `not_in_nav` destinations must belong to
that actual set, including MkDocs' default exclusions and negated patterns.
Existing files in the fixed generated-reference allowlist must remain
published; absent allowlisted files are currently skipped, so missing-file
completeness is not established by this predicate. Every included
Markdown page is scanned for:

- repository placeholders and same-host docs URLs inconsistent with `site_url`;
- literal `.yml` workflow references against actual workflow filenames;
- supported inline and full/collapsed/shortcut reference Markdown page links;
- canonical regeneration wording on the generated-reference allowlist; and
- plain-line `Owner:` and `Source of truth:` on manual reference pages.

Relative Markdown destinations are resolved under the configured docs root
and compared with actual inclusion. A `frontend` segment is no longer an
outside-doc proxy. Python-Markdown owns link parsing and reference-label
normalization; supported two-line inline labels are position-measured.
Unsupported multiline destination/title syntax, unreadable Markdown, missing
parser/config dependencies or unavailable selection produce `UNRUN` (exit 2)
and partial findings, never a clean verdict. Violations after a complete
admitted-input scan return exit 1; zero violations return exit 0.

Each result emits the actual file manifest, navigation and exclusion selectors,
workflow filename inventory, measured read outcomes and content hashes. The
receipt names unobserved config/plugin/import/Git operations. Its completeness
field refers to the admitted checker predicates, not repository-wide truth.
Plain metadata is an authoring predicate, not owner verification or authority.

The checker does not establish prose truth, runtime behavior, external URL
liveness, unpublished content accuracy, raw HTML/image/asset reachability,
root-relative URL or fragment-anchor validity, absent generated-allowlist
files, unsupported multiline forms,
extensionless targets without a Markdown/index destination, `.yaml` workflow
references, deployed-site behavior or hosted CI. Complete source/asset and
emitted-site link QA supplements it. See
`tools/quality/validation/check_docs_accuracy.py`.

The freshness wrapper is a baseline comparison, not a page-age scan. The current baseline expects zero violations, so it still requires the live accuracy check to exit successfully and report exactly zero. A positive-count exception must bind its owner, reason, command, issue, expiry, exact count, and output digest. The wrapper's input remains the published-page accuracy set; it does not assert that every Markdown file has a recent `Last updated` marker. See `tools/quality/validation/check_docs_freshness_baseline.py`, `tools/lib/docs_freshness.py`, and `architecture/exceptions/docs_freshness.toml`.

### Strict MkDocs build

`uv run --extra docs python -m mkdocs build --strict` builds the site with the configured theme, plugins, Markdown extensions, navigation, and included pages. It is the rendered-build check; it does not prove that claims in the rendered pages are true, check external link liveness, or deploy the site. The root `mkdocs.yml` inherits generated configuration, including its assembled navigation, from `architecture/tooling/mkdocs/generated.yml`.

The actual build input can exceed the explicit `nav`/`not_in_nav` page set:
MkDocs also includes unlisted documents unless excluded. For a publication-scope
change, enumerate `mkdocs.structure.files.get_files(load_config(...))` and its
included files, then check links from that complete Markdown set and the
included assets. The accuracy checker now uses that actual set for Markdown pages. Its asset
and fragment omissions still require complete source and emitted-site QA;
a Markdown-only checker does not establish every built asset's reachability.

Strict mode fails on warnings, not every diagnostic. With the current default
MkDocs link-validation configuration, a link to an excluded page can be logged
at `INFO` and still leave the strict build green. A publication change therefore
needs the complete included-set link check as well as the strict build; for
retained repository evidence, use a source-qualified repository link rather
than a local site link to an excluded page. This is the P38 difference between
a warning-free build and complete local reachability.

### Docs lifecycle

`uv run polisyos-tools validation check-docs-lifecycle` checks a set of lifecycle contracts: ADR index inputs and generated outputs; required ADR navigation entries; a declared Policy Design Case ADR pack; active-plan status/owner and closeout rules; redirect-stub metadata; known removed-path references; archive placement and authoring docs; README/AUTHORING coverage for a fixed list of high-volume subtrees and public-stable packages; and extension-example structure. The exact checks are in `tools/quality/validation/check_docs_lifecycle.py`.

This is not a general document-accuracy, link, or freshness checker. Its generic repository walks use tracked paths from `git ls-files --cached`; other checks use declared manifests, fixed subtree lists, or ADR generator inputs. It does not mean every physical or untracked file was inspected. The lifecycle validator is dispatched by the path-aware gate for ADR, plan, archive, and MkDocs navigation/configuration paths.

The removed-path reference subcheck records its complete tracked-path
selection and explicit byte/readlink operations. Directory-presence checks use
all tracked paths, independently of text selectors. Recognized opaque
containers are byte-read but not decoded; selector exclusions are not read;
unknown invalid UTF-8, malformed JSON and failed reads remain ambiguous.
These classes retain unresolved findings and an `UNRUN` exit 2 when the
reference scan is incomplete. Actual stale-reference findings remain visible.

The receipt is explicitly reference-scan-only. ADR/TOML and generator inputs,
MkDocs YAML, PDC/plan/redirect/archive/README documents, package contracts and
extension-example manifests remain unmeasured by that receipt and are named
boundaries. Historical-audit and archive-map
suppression still rely on declared roles/shaped metadata rather than resolved
archive bytes or verified provenance (P32); table roles use the canonical
Markdown tokenizer. No full lifecycle truth or evidence authority follows
from a bounded reference scan.

### Documentation inventories and indexes

The public-surface renderer exposes existing candidate and export-proof scope,
with compact bindings to its canonical JSON read receipts. A source candidate
is not a proved native export; unresolved native counts remain unknown.

The Fabric inventory counts statically resolved public connector class
declarations using canonical ancestry and declared interface slots. Unknown
namespace binding/import forms yield partial coverage. The aggregate inventory
does not establish connector-ID identity. A separate conformance check compares
declared SourceContract IDs with connector metadata IDs; that narrow check does
not establish a repository-wide identity property, native imports, operational
connectors, or deployment. Explicit inventory operations are retained in JSON
and bound compactly from Markdown. Valid slot values and full family mapping
remain outside the inventory method.

ADR indexes parse source-declared statuses and explicit relation fields,
including their supported continuations. Missing/unrecognized status is
`unknown`; narrative “replaces” cannot create a supersession edge. An accepted
record, index link or generated count does not establish implementation.
Unsupported relation vocabulary and primary-record/source mismatches remain
named audit boundaries. Regenerate through the canonical generator rather
than editing the derived indexes.

## Baseline failure attribution

If a check is already red on entry, apply `P41` from the [Policy Design Case failure and repair register](policy-design-case-failure-patterns.md): replay the exact command from a base predating all work in the slice, then establish whether the changed paths intersect that check's complete input denominator. For a closure or handoff, use the slice's base, not a later cluster base. Only a reproduced failure with a proven zero intersection is inherited; record its owner and proceed. If it does not reproduce, identify the introducing work. If the exact base cannot be replayed, classify the result as `not_established`; do not select a nearer base to force attribution. If the changed paths overlap the gate inputs, do not report the failure as inherited without tracing that overlap.

For docs checks, name the denominator explicitly: the actual MkDocs included Markdown set for accuracy (with nav policy separately), the configured authored Markdown scope for Markdownlint, the generated source/output pairs for tool-config validation, or the tracked paths and manifest-declared sets used by lifecycle validation. A summary count from one of these checks must retain that scope; it is not a repository-wide count of current documentation.

## Tool prerequisites

The contributor baseline is Python 3.14.x, Node 22.x, and `uv 0.9.21`. The `docs` extra supplies MkDocs, Material, and mkdocstrings; the `lint` extra supplies pre-commit and Ruff. Markdownlint runs through the pinned pre-commit hook, whose environment may need initialization on a fresh machine. The docs profile is the documented bootstrap path for a workstation that needs these checks. Do not treat a missing executable, unavailable dependency, or `UNRUN` result as a successful documentation verdict.

See [Quality Gates](quality-gates.md), [Repository Hygiene](repository-hygiene.md), [Manage Generated Artifacts](../how-to/manage-generated-artifacts.md), and the [Policy Design Case failure and repair register](policy-design-case-failure-patterns.md) for the surrounding contracts.
