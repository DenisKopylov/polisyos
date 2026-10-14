# Documentation Verification Contract

Owner: team-docs

Source of truth: `tools/devx/workspace/docs_style.py`, `tools/quality/validation/check_docs_gate.py`, `tools/quality/validation/check_docs_accuracy.py`, `tools/quality/validation/check_docs_freshness_baseline.py`, `tools/quality/validation/check_docs_lifecycle.py`, and `architecture/tooling/tool_config_split.toml`.

This contract is for authored Markdown changes in `policy-engine/`. A passing check proves only the property and input set named below. In particular, a green “freshness” result does not establish that every repository document is current or that every factual claim is true.

## Local verification path

Run commands from `policy-engine/` after the authored page and any publication navigation change are complete:

```bash
uv run polisyos-tools workspace docs-style docs/reference/documentation-verification.md
uv run python tools/quality/validation/check_docs_gate.py
```

The first command runs the configured `markdownlint-cli2` hook against the named file. The second command computes the docs-sensitive change set from Git and dispatches checks based on the changed paths. For a change under `docs/**`, the gate plans the docs-freshness baseline check and a strict MkDocs build. A change under `architecture/tooling/mkdocs/**` also plans the docs-lifecycle check; any change under `architecture/tooling/**` plans the generated tool-config check. The gate stops at the first failed command, so a failure can leave later planned checks unrun.

The path-aware gate does not run Markdown lint. Keep the targeted `docs-style` command separate. `check_docs_gate.py --changed-path <product-relative-path>` can be used to inspect or reproduce a plan for explicit paths; explicit paths replace Git change discovery, so the normal command is the evidence for the actual worktree change set.

For a new page under `docs/reference/`, add it to the source navigation fragment `architecture/tooling/mkdocs/nav/30-reference.yml`. Do not edit `mkdocs.yml` or `architecture/tooling/mkdocs/generated.yml` directly. The fragment and generated outputs are declared in `architecture/tooling/tool_config_split.toml`; `uv run polisyos-tools workspace tool-configs` renders them, while `uv run polisyos-tools workspace tool-configs --check` is read-only and verifies generated-file drift plus dead override state. The path-aware gate dispatches the `--check` form when the navigation fragment changes.

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

The receipt is explicitly reference-scan-only. ADR/generator, plan, redirect,
archive, package/TOML and extension-example input families remain unmeasured
by that receipt and are named boundaries. Historical-audit and archive-map
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
namespace binding/import forms yield partial coverage. Contract counts plus a
validator path do not establish connector-ID identity: that join remains
`not_established` and the family state stays partial. Explicit operations are
retained in JSON and bound compactly from Markdown. Native imports, valid slot
values, operational connectors and deployment remain outside this method.

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
