# Documentation Organization Research — 2026-10-14

> Research-only recommendations for the docs refresh. This note does not change
> PolicyOS policy, authorize a site change, or promote any repository capability.

## Scope and standing

This review uses the assigned baseline `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on
`codex/docs-refresh-e02-20261014`. The worktree already contains unrelated documentation edits;
they were not used as evidence for the baseline comparison and are outside this note's scope.

The repo's own instructions and accepted decisions govern PolicyOS. External documentation guidance
below is evidence for recommendations, not authority to replace local rules. ADR-0126 is relevant but
currently says `Proposed`; it is not an accepted decision. If the project wants to settle its proposed
Diátaxis and plan-lifecycle model, that decision belongs in ADR-0126's existing review path rather
than in a second taxonomy proposal.

## Current organization

The existing system separates several concerns already:

- [`docs/style-guide.md`](../style-guide.md) maps tutorials, how-to, reference, and explanation to
  reader needs and directories. It also gives authored pages a local writing style, freshness
  expectations, and generated-reference rules.
- [`docs/index.md`](../index.md) routes readers to those four surfaces, then provides architecture
  and operational anchors. The checked-in navigation source has additional shelves for contracts,
  runbooks, and ADRs.
- The repository also has artifact-oriented homes such as `docs/adr/`, `docs/contracts/`,
  `docs/research/`, `docs/plans/`, `docs/backlog/`, `docs/archive/`, and
  `docs/system-design-decisions/`. The comparison came from
  `find policy-engine/docs -maxdepth 1 -mindepth 1 -type d -print`, whose denominator is direct-child
  directories only; no counts or percentage claims are made here.
- [`docs/research/README.md`](README.md) explicitly says research is an input, not runtime authority;
  conclusions need translation into a governed contract, manifest, validator, or ADR before code can
  rely on them.
- [ADR-0126](../adr/0126-docs-lifecycle-diataxis-plans-archive.md) proposes a lifecycle in which
  Diátaxis holds durable reader docs, plans move through active/accepted/archive, irreversible
  decisions use ADRs, and machine-checkable behavior belongs in architecture files and schemas.
  Its proposed status matters: do not describe this ADR as ratified.

These are compatible dimensions when kept distinct: **reader purpose** answers what a reader needs;
**artifact role and lifecycle** answer what kind of record the file is and whether it is draft,
accepted, superseded, or historical. A research report can explain a topic while remaining a
research-only artifact. A contract can be reference-like while its authority comes from its owning
schema or runtime consumer. The current style guide's “one of four types” rule is easiest to apply if
it describes the primary reader purpose of a page, while the existing artifact directories continue
to identify record role and lifecycle.

The publication boundary is also explicit. `policy-engine/mkdocs.yml` inherits the generated
`architecture/tooling/mkdocs/generated.yml`, which is itself produced from the source fragments
declared by `architecture/tooling/tool_config_split.toml`. Its navigation groups reader material,
contracts, runbooks, and ADRs; `exclude_docs` omits plans and archive material. The research tree is
not in the checked-in site navigation. Do not edit the generated target to change this boundary.

The existing `check_docs_accuracy.py` validates the publication membership expressed by `nav` and
`not_in_nav`, local links within that measured surface, placeholders, literal workflow references,
manual-reference `Owner` and `Source of truth` fields, and canonical regeneration commands for
allowlisted generated references. Its own `MEASURED` and `OMISSION` declarations say it does not
establish prose truth, external URL availability, unpublished-page contents, deployment state, or
several link and asset forms. `check_docs_lifecycle.py` separately covers lifecycle concerns such as
ADR indexes, navigation tokens, authoring contracts, and archive placement. These are useful,
bounded checks; neither should be presented as a general proof that all documentation is current.

One date example deserves precise treatment rather than a stale verdict: the documentation inventory
has `Freshness: 2026-05-03` near its header, a dated `2026-09-11` impact note, and QA/audit snapshots
dated in April and May. That is evidence that the single word “Freshness” does not tell a reader
which date role it represents. It does not, by itself, establish that any of those records is wrong.

## Research findings

Diátaxis names four different reader needs—tutorial, how-to, reference, and explanation—and describes
how they serve action or understanding. Its official primer supports keeping these as content
purposes, rather than treating every repository record as an interchangeable page type
([Diátaxis primer](https://diataxis.fr/start-here/)). GitHub's content model makes a related
distinction: content types are used across documentation sets, while site hierarchy is a separate
organization problem; it warns that both excessive depth and excessive breadth make material harder
to find ([GitHub content model](https://docs.github.com/en/contributing/style-guide-and-content-model/about-the-content-model)).
These sources support a small clarification to the local model, not a directory migration.

Reader-task-first writing is consistent across other primary documentation programs. Google asks
authors to define scope and audience and organize material around readers' needs
([Google technical writing: documents](https://developers.google.com/tech-writing/one/documents)).
GitLab's docs workflow recommends drafting documentation early and having domain engineers and
maintainers review technical accuracy alongside the code change
([GitLab documentation workflow](https://docs.gitlab.com/development/documentation/workflow/)).
For PolicyOS, the practical adaptation is to review examples and claims against their owning code,
schema, test, generator, or decision record, not to adopt another company's review roles wholesale.

For ADR lifecycle, AWS describes a decision record as context, decision, and consequences, and says
accepted or rejected ADRs should be immutable; a changed decision is recorded by a new ADR that
supersedes the old one ([AWS ADR process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html)).
This agrees with the local ADR style guide and reinforces using the existing ADR sequence for a
structural change rather than recording the same choice in a new prose guide.

For provenance and revision, W3C PROV distinguishes the document entity, the activity that creates or
revises it, and the responsible agent; it models a revision as a new entity derived from an earlier
one ([W3C PROV Primer](https://www.w3.org/TR/prov-primer/)). This is a useful conceptual check for
date labels and evidence lineage, not a proposal to introduce PROV fields or a new docs schema.

The site-tool boundary is concrete: MkDocs `nav` controls global navigation and `exclude_docs`
controls which files enter the built site ([MkDocs configuration](https://www.mkdocs.org/user-guide/configuration/)).
GitHub's reference model also explicitly treats generated pipeline content as a valid form of
reference ([GitHub reference content type](https://docs.github.com/en/contributing/style-guide-and-content-model/reference-content-type)).
Together these support keeping publication and generation decisions in their existing source
fragments and generators, with each generated page pointing to its source and regeneration command.

## Reuse-first recommendation

For the current docs refresh, retain the existing directory layout and update the affected page or
existing index in place. Do not add a new top-level taxonomy or move broad sets of files without
evidence that readers cannot find what they need. Use the current directories as follows:

1. Place durable reader material in its existing Diátaxis area and give it one primary reader
   purpose. Keep ADRs, contracts, research, plans, runbooks, and archives in their existing record
   homes, each with the lifecycle and publication treatment already defined for that home.
2. When a research finding is ready to affect a decision, route it to the existing owner: an ADR for
   an architectural choice, a schema or `architecture/*.toml` for machine-checkable behavior, or the
   owning reference/how-to/explanation page for reader guidance. Keep the research source linked so
   the derivation remains inspectable.
3. Use the existing source-of-truth and validation fields for manual references. For generated pages,
   preserve the canonical generator and drift check. Do not add a universal metadata requirement
   from this research note.
4. Where time matters, label distinct meanings such as “last revised,” “last verified,” and
   “evidence snapshot date” explicitly. Add only the fields a specific page needs; avoid using one
   `Freshness` value to imply all three.
5. Keep the publication decision explicit in the existing MkDocs source fragments. Research notes
   stay outside the site navigation unless an owner deliberately promotes them to a reader-facing
   page and the published-doc checks can validate their links and metadata.

Useful acceptance signals for an individual documentation change are:

- A contributor can tell who should read the page, what they can do or understand afterward, and
  which existing index is its home.
- A consequential factual claim links to the current owner or source of truth and names the command,
  test, or evidence path that checks the claim when one exists.
- Generated content has a canonical source and regeneration command; the source is edited and the
  generated drift check agrees afterward.
- The published/unpublished choice is visible in the authoritative MkDocs fragments, and the strict
  docs build plus existing accuracy/lifecycle checks accept the resulting links and placement.
- A research recommendation remains advisory until an authorized decision or runtime contract
  adopts it; no new runtime capability is implied by the note.

These are proposed review signals that reuse existing checks and fields. They do not require a new
gate, metadata type, or documentation subsystem.

## Optional larger restructure — approval required

If measured reader or contributor failures show that the current separation is not navigable, the
larger option is to formalize a two-axis content model in the style guide and generate a single
cross-link index from the existing ADR, research, plan, contract, and reference inventories. Keep
Diátaxis as the reader-purpose axis and use the existing artifact status/source/owner data for the
record axis. Consider physical file moves only if the evidence shows the existing paths themselves
cause the failure.

Potential benefit: one entrypoint could make a claim's reader explanation, authoritative contract,
decision history, generator, and verification signal easier to follow as a chain. Costs: changing
the canonical style rule or ADR-0126 needs owner review; a new registry and gate add maintenance;
renaming or moving files creates link, anchor, index, generated-navigation, and historical-reference
work; a second taxonomy can obscure ownership if it duplicates existing metadata. A broad hierarchy
can also trade one kind of navigation burden for another, as the GitHub content model cautions.

Do not start that migration from directory size or an assumed “SOTA” target. First collect a complete
path inventory with file-type denominators and concrete reader failures; then ask the docs owner and
principal whether ADR-0126 should be accepted, amended, or rejected. If approved, use that decision
as the migration boundary and preserve existing record identity and supersession history.

## Pattern pass

- **P13 — governance gravity:** the minimal path adds no new taxonomy, metadata schema, or gate.
  Widen the mechanism only if measured navigation failures justify its continuing cost.
- **P35 — sampled-denominator generalization:** this note makes no file counts or distribution
  claims. Any follow-up census must walk the complete relevant paths and state the file-type
  denominator and executing party.
- **P36 — authority by adjacency:** external sources are advisory and linked directly; ADR-0126 is
  named with its actual `Proposed` status. The surrounding prose is not treated as a ratified finding.
- **P08 — time-role conflation:** the inventory example is recorded as ambiguous date semantics,
  not as proof of staleness. Keep edit, verification, and evidence dates distinct when they matter.
- **P38 — proxy gate:** docs link/publication checks prove only their declared structural surface;
  they do not establish claim truth or external reachability. Acceptance language above preserves
  that boundary.
- **P01/P02:** not applicable as a new capability is proposed; this is research guidance only.

## Sources

Repository sources read for this review: `AGENTS.md`, `policy-engine/CONTRIBUTING.md`,
`policy-engine/docs/style-guide.md`, `policy-engine/docs/index.md`,
`policy-engine/docs/research/README.md`, `policy-engine/docs/adr/0126-docs-lifecycle-diataxis-plans-archive.md`,
`policy-engine/docs/reference/documentation-inventory.md`,
`policy-engine/docs/reference/generated-artifacts.md`,
`policy-engine/architecture/tooling/mkdocs/generated.yml`,
`policy-engine/tools/quality/validation/check_docs_accuracy.py`, and
`policy-engine/tools/quality/validation/check_docs_lifecycle.py`.

External sources were accessed on 2026-10-14:

- [Diátaxis primer](https://diataxis.fr/start-here/)
- [Google technical writing: documents](https://developers.google.com/tech-writing/one/documents)
- [GitHub content model](https://docs.github.com/en/contributing/style-guide-and-content-model/about-the-content-model)
- [GitHub reference content type](https://docs.github.com/en/contributing/style-guide-and-content-model/reference-content-type)
- [GitLab documentation workflow](https://docs.gitlab.com/development/documentation/workflow/)
- [AWS ADR process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html)
- [W3C PROV Primer](https://www.w3.org/TR/prov-primer/)
- [MkDocs configuration](https://www.mkdocs.org/user-guide/configuration/)
