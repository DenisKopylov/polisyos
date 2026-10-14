# Documentation Style Guide

> Canonical style and evidence standard for PolicyOS repository documentation.
> All new and updated authored documentation must follow this guide.

---

## Source snapshots and verification dates

For claims about current behavior, identify the source snapshot (commit,
release/tag, or immutable artifact), the verification method, and material scope
limits. A path, mutable branch, date, or owner statement alone does not prove
that the code matches the description. A test reference establishes only the
coverage it provides; state separately whether the test ran when the document
was updated.

Distinguish current behavior, target/proposed work, and history. `current` means
a claim supported by a check against the named snapshot and within the check's
method and scope (source inspection, an executed test, or a deployment
observation). `target/proposed` records intent, not implementation evidence.
`history` records a period or snapshot and links to its successor when
superseded. An accepted decision establishes an intent or rule; it does not
prove that a capability is implemented. Document `status` and `stability`
describe document lifecycle, not runtime authority. Historical receipts retain
their original snapshot and date; editing their prose does not create a new
verification.

Use metadata terms precisely:

- `created` records when an entry was created.
- `Last updated` or `revised` records a text change.
- `last_verified` records a check that actually ran, with its method and scope.
- `as_of` records the time of the described state or observation.
- `owner` identifies the document's maintainer.
- `Source of truth` identifies the canonical source.
- An `approval owner` has decision authority when that role differs from the
  document owner.

A prior verification date does not promise that a document remains current
after its source changes.

For published manual reference pages, put `Owner:` and `Source of truth:` on
separate lines with plain-text labels, without a list, quote, or emphasis
around the labels. Source paths may use inline code as required by the binding grammar. The
current accuracy checker recognizes that exact form. Counts and claims about a
whole set require a reproducible complete walk and a stated denominator (P35).
Do not copy generated inventories into manually maintained pages.

### Change-triggered review and evidence binding

A change to canonical code, a contract, schema, gate, public surface, generated
reference, or owner map is a reason to review only the documented claims it may
affect. Check those claims against the relevant canonical source; correct them,
narrow their scope, or label the discrepancy explicitly as target/proposed,
history, or unresolved. This is event-triggered review of affected claims, not a
promise to re-review every document periodically.

Bind each consequential claim to the minimum evidence it needs:

- Cite the canonical source and snapshot pin when the conclusion depends on a
  particular state.
- Cite the finding ID and primary record when the claim comes from an
  authoritative decision or audit.
- State the method, denominator, and reading limits when the conclusion depends
  on a measurement.

One pin may support several related claims. Do not repeat the same hash after
every sentence or require metadata that a page does not need. For measurements,
follow the [measurement instrument author contract](how-to/author-measurement-instruments.md):
the declared read scope does not replace the record of what the instrument
actually read and which boundaries remain unresolved.

A page's audience determines how its result is explained; it does not raise the
authority of the artifact it describes. Authority depends on who issued the
artifact and in what role, its provenance, purpose, version, time, and the
actual admission and consumer path. A link, lifecycle status, field label, or
generated projection does not by itself make candidate evidence admitted or
active.

Preserve primary ratified decisions, verbatim imported specifications, and
historical audit or measurement receipts in their original role and time
context. Publish a corrected current interpretation as a separate documented
finding with its source and pin; identify supersession explicitly. Do not rewrite
a primary record so that it appears to describe current implementation or a new
verification. For language and translation rules, see the
[documentation language policy](reference/documentation-language.md).

---

## Language

English is the sole canonical language for PolicyOS system and repository
documentation. Write and maintain all new or updated authored documentation in
English, including READMEs, ADRs, contracts, references, plans, operational
guidance, and explanatory code docstrings.

Additional-language translations are optional informational derivatives. Each
must link to its canonical English source and identify the English source
revision it translates. A translation cannot replace or override the English
document. Preserve source quotations, identifiers, and machine evidence
verbatim when needed for traceability; provide an English translation nearby
when readers need it. Language alone does not establish authority.

The migration status of existing non-English records is tracked separately.
This rule does not declare a general legacy exception. The approved first
stage defers executing plans and the working E02 corpus. Preserve historical
decision and evidence originals; separately labeled English reader editions
cannot revise their status or authority. See
the [documentation language policy](reference/documentation-language.md).
Human conversations are not governed by this repository-documentation rule.

---

## Docstring format

Use Google-style docstrings. Every public module, class, and function must have
a docstring.

The snippets below demonstrate format, not executable APIs or claims about the
current PolicyOS implementation. Names, fields, and scenarios are illustrative.
When documenting an actual API, use its canonical source or generated reference
at the stated source pin. For a tutorial that includes real imports, identify
which smoke checks ran, which steps remain an unverified draft, and which
bridges are missing. Do not invent expected results or fallbacks that hide a
non-working path.

```python
def compile(spec: PolicySpec, *, backend: str = "jax") -> CompiledGraph:
    """Compile a policy specification into an executable mechanism graph.

    Takes a declarative PolicySpec and produces a CompiledGraph that can be
    executed by the Foundry runtime. Compilation includes validation of
    variable bindings, causal graph acyclicity checks, and backend-specific
    optimizations.

    Args:
        spec: Policy specification containing ProblemFrame, causal graph,
            and intervention definitions.
        backend: Execution backend. One of "jax", "numpy", "symbolic".
            Defaults to "jax".

    Returns:
        CompiledGraph ready for execution via execute().

    Raises:
        CompilationError: If the spec contains unresolvable variable
            references or cyclic causal dependencies.
        BackendError: If the requested backend is unavailable.
    """
```

### Docstring sections

- **One-line summary:** Use an imperative first line ("Compile a...", not
  "Compiles a...").
- **Args:** Describe each parameter. Indent continuation lines by four spaces.
- **Returns:** State what is returned and under which conditions.
- **Raises:** List only exceptions the function explicitly raises.
- **Example:** Include an example only when the usage is not obvious. A runnable
  example must use a real API and be verified; format-only examples must be
  labeled as illustrative.
- **Pydantic models:** Explain the model's purpose in the class docstring.
  Document fields with Field(description=...) or an Attributes: section.

```python
class ProblemFrame(BaseModel):
    """Frame defining the policy analysis problem.

    Captures the research question, target population, outcome variables,
    and constraints that scope a policy analysis. Acts as the "Why" in the
    Trinity (ProblemFrame / PolicySpec / ModelSpec) separation.

    Attributes:
        question: Natural-language research question.
        outcome_vars: Variables to measure policy impact on.
        population: Target population scope (geographic, demographic).
        constraints: Hard constraints on feasible interventions.
    """

    model_config = ConfigDict(extra="forbid")

    question: str
    outcome_vars: list[str]
    population: EntityScope
    constraints: list[str] = []
```

---

## Semantic docstring quality

Phase 7 requires more than the presence of a docstring: public API docstrings
must convey useful meaning. For user-facing, governance-critical, and
reference-visible symbols, explain the object's role in the domain, conditions
for correct use, contract boundaries, and links to neighboring layers.

### Avoid placeholder summaries

These one-line summaries exist formally but provide no useful context:

```python
"""Public core security package API."""
```

```python
def parse_rows(payload: bytes) -> list[Row]:
    """Parse rows helper."""
```

```python
class RoutingState(BaseModel):
    """Routing state data model."""
```

```python
class Registry:
    """Registry implementation."""
```

### Describe the actual role

#### Module or package facade

```python
"""Expose tenant-security contracts through a lazy package facade.

polisyos.core.security is the stable authorization boundary for runtime
services and control-plane tooling. Exports stay lazy so docs and CLI bootstrap
paths can inspect auth contracts without eagerly initializing OPA, TEE, or
storage backends.

Treat names in __all__ as the supported public surface; non-exported helpers
remain module-private.
"""
```

#### Class or Pydantic model

```python
class RoutingState(BaseModel):
    """Track cursor ownership for collaborative review sessions.

    The state is persisted per (run_id, artifact_ref) pair and must be updated
    atomically with lock ownership checks so stale clients cannot overwrite a
    newer cursor. Runtime HTTP review routes serialize this model directly.

    Attributes:
        cursor_token: Opaque cursor identifier issued by the active reviewer.
        updated_at: UTC timestamp of the latest successful cursor write.
    """

    cursor_token: str
    updated_at: datetime
```

#### Function or method

```python
def parse_rows(payload: bytes, *, source_name: str) -> list[Row]:
    """Parse a connector payload into canonical row objects.

    Use this parser for trusted source adapters that already passed transport
    validation. The function normalizes field order and rejects malformed row
    envelopes instead of silently dropping records.

    Args:
        payload: Raw UTF-8 encoded payload returned by the connector backend.
        source_name: Human-readable source label used in validation errors.

    Returns:
        Canonical row objects ready for persistence into the world fact log.

    Raises:
        ValueError: If the payload is not valid JSON or row envelopes are malformed.
    """
```

### Semantic checklist

- The one-line summary explains the **role or action** rather than repeating
  the symbol name.
- Class and model docstrings state lifecycle rules or invariants, not only a
  list of fields.
- Boundary objects name the neighboring contract or layer that reads or writes
  them.
- Public functions describe Args, Returns, and Raises. Entrypoints, loaders,
  and compile APIs also include an Example when useful.
- For a trivial API, prefer a short, domain-specific summary to a long but empty
  description such as ... helper.

### Allowlist and pragma

The automated gate is tools/quality/validation/check_docstring_quality.py.

For rare, trivial wrappers, use a narrow exception:

- Add the fully qualified symbol to
  tools/quality/validation/docstring_quality_allowlist.txt; or
- Add an inline pragma beside its definition:

```python
# docstring-quality: ignore
def passthrough(value: str) -> str:
    """Return the input unchanged."""
    return value
```

Do not use the allowlist for user-facing APIs, package facades,
compile/execute/load entrypoints, governance passes, or boundary models.

---

## Documentation reality and publishability

Documentation must describe the repository's current reality, not historical
plans.

### Baseline rules

- Do not leave repository placeholders in published docs.
- Do not link to removed GitHub Actions workflows. Use only files that exist
  under .github/workflows/.
- Do not put local filesystem links (/Users/..., file://...) in Markdown.
- Absolute documentation-site URLs must match mkdocs.yml:site_url.
- Internal Markdown links must resolve in the current docs/ tree.

### Automated checks

The CI documentation-quality gate runs:

- uv run --extra docs python -m mkdocs build --strict
- python3 tools/quality/validation/check_docs_accuracy.py --repo-root .
- uv run --extra docs python tools/quality/validation/check_docstring_quality.py --repo-root . --allowlist tools/quality/validation/docstring_quality_allowlist.txt

The semantic-coverage gate applies to the top-level public surface (module,
class, and function exports, plus reference-visible symbols). Method-level
gaps remain a separate second-pass backlog and must not be hidden by an
allowlist without an explicit reason.

---

## README freshness policy

- Changes to a package facade, recommended entrypoint, generated/reference
  artifact location, or subsystem navigation must update the nearest
  README.md.
- Each package README must include Last updated: YYYY-MM-DD.
- A major subsystem README must include a Where to Start section.
- If a package owns committed generated artifacts or important reference docs,
  its README must point to their location and canonical entrypoint.

## Single package README template

Use one template for module READMEs under src/polisyos/. Keep the required
sections concise and factual. Include a conditional section only when it helps
the reader; remove unused placeholders instead of inventing details or claiming
an absence that has not been checked. Target 50–150 lines.

```markdown
# Module Name (polisyos.module)

One factual paragraph describing what the module does and the problem it solves.

## Purpose

State what the package owns and when a contributor should start here.

## Role in the system

Name verified dependencies and consumers where known. Describe the module's
architectural position without inferring ownership from a dependency alone.

## Public API

Describe the stable facade and supported entrypoints. Link to the authoritative
reference page when one exists.

## Where to Start

Link to the canonical entrypoint, instructions for changing the public facade,
and nearby generated or reference artifacts as relevant.

## Tests

Name the canonical unit, contract, integration, fixture, or golden test
locations and the smallest useful verification command. State verified gaps
clearly.

## Current status

- Last updated: YYYY-MM-DD
```

Add one of these sections only when it provides concrete value:

- Key concepts — a concise set of important terms or invariants.
- Internal layout — important subpackages and files, with private subtrees
  identified.
- Extension points — plugin hosts, registry loaders, generated-client
  boundaries, or verified absence of extension points.
- Generated / reference artifacts — artifact path and canonical
  regeneration command.
- Operability links — SLOs, runbooks, dashboards, release gates, or a verified
  statement that no package-specific operability surface exists.
- Known shims / deprecations — compatibility wrappers, legacy import paths,
  sunset dates, or a verified absence of known shims.

Do not add illustrative runtime examples to a README. If an example is needed,
link to a verified test or to a separately maintained tutorial whose executable
steps have been checked against the current source snapshot.

---

## ADR template

Use the Michael Nygard format. Accepted ADRs are immutable: supersede them
instead of editing their decisions.

```markdown
# ADR-NNNN: Title

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXXX

## Context

What problem are we solving? What constraints and requirements apply?

## Decision

What did we decide to do? State the technical decision precisely.

## Consequences

What became easier? What became harder? What trade-offs follow?
```

### ADR rules

- Use four-digit numbers with leading zeroes (0001, 0092).
- Name files docs/adr/NNNN-kebab-case-title.md.
- Treat an Accepted ADR as immutable.
- To reverse a decision, write a new ADR that refers to the earlier one.

---

## Markdown conventions

### Formatting

- Use ATX headers (#), not underline-style headings (===).
- Fence code blocks with triple backticks and specify the language
  (python, yaml, or bash).
- Use relative links within docs/, for example
  [Trinity](explanation/trinity.md).
- Keep lines near 100 characters where practical; do not hard-wrap prose
  paragraphs.
- Use - for unordered lists and 1. for ordered lists.
- Use bold for key terms and backticks for identifiers.

### File structure

```markdown
# Title

> Optional one-line tagline or status note.

---

## Section 1

Content...

## Section 2

Content...
```

- Use one # title per file.
- Put --- after the introductory title/tagline block.
- Leave a blank line before and after every heading.

### Tables

Use Markdown tables for structured data:

```markdown
| Column A | Column B | Column C |
| -------- | -------- | -------- |
| value    | value    | value    |
```

### Admonitions (MkDocs Material)

```markdown
!!! warning "Important"
Warning text.

!!! note
Additional information.

!!! example
Illustrative example.
```

---

## Diátaxis categorization

Every document in docs/ should have one primary Diátaxis purpose. Do not
combine multiple purposes when a clear split would help readers.

| Type        | Directory    | Purpose                            | Typical style                               |
| ----------- | ------------ | ---------------------------------- | ------------------------------------------- |
| Tutorial    | tutorials/   | Learn by doing                     | "Do X, then Y, and observe Z"               |
| How-to      | how-to/      | Solve a specific task              | "To do X: steps 1, 2, and 3"                |
| Reference   | reference/   | Find precise, complete information | Concise descriptions of APIs, fields, types |
| Explanation | explanation/ | Understand context and rationale   | "Why X is designed this way"                |

### Signs of miscategorization

- A tutorial explains why instead of guiding the reader through an exercise:
  move the rationale to an explanation.
- A reference page contains step-by-step procedures: move them to a how-to.
- A how-to begins with extended theory: move that context to an explanation and
  link to it.
