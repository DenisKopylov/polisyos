# Documentation Language Policy

Owner: team-docs
Source of truth: `repo:AGENTS.md`, `product:CONTRIBUTING.md`, and `product:docs/style-guide.md`

English is the sole canonical language for PolicyOS system and repository
documentation. This policy governs authored repository text; it does not govern
the language used in human conversations.

## Authoring rule

Write new and updated repository documentation in English. This includes
`AGENTS.md` files, contributor guides, READMEs, plans, specifications, decisions,
contracts, references, operational guidance, and explanatory text in code
docstrings. Keep product identifiers, API names, schema fields, commands, and
other literal tokens exactly as defined by their owners.

For each change, translate or update the affected authored prose in English.
Do not infer that an existing non-English page is exempt because it is old,
archived, approved, or outside the published handbook. The migration inventory
and sequence remain a separate task; this policy does not claim that every
existing page has already been translated.

## Localized copies

An additional language may be provided when it helps a defined audience. Such a
copy is an informational derivative, not a second authority. It must identify
its language and locale, link to the canonical English document, and record the
English source revision it translates. When that source changes, mark the copy
as needing review until it has been reconciled. A localized copy must not
introduce or alter requirements, status, authority, or contract semantics.

## Quotations and source evidence

Preserve a material quotation in its source language when exact wording is
needed for provenance, legal or historical evidence, or technical analysis.
Attribute and link it to the source, label it as a quotation, and provide an
English translation nearby when readers need to understand it. Preserve literal
identifiers, payloads, field values, and machine-generated evidence exactly
where changing them would damage traceability; explain their meaning in English.
Language alone does not establish authority, truth, or admissibility.

Preserving the bytes or wording of a primary source is a provenance rule, not a
blanket exemption from the English documentation requirement. The current migration defers the working E02 corpus and active plans.
Historical decision sources remain byte-preserved; English reader editions
identify the original source and retain its authority boundary. Do not rewrite those source records as part of a
translation, and do not infer from their preservation that their publication
or migration has been exempted.

## Migration stages

The first migration stage covers code documentation and other authored
repository documentation. It defers plans that are currently being executed
and the working E02 corpus until their active work can be reviewed safely.
This is a sequencing deferral, not a language-policy exemption; revisit the
deferred material in a later owner-reviewed stage.

The human usability protocol is prepared for this stage; the human study is
NOT RUN and is deferred by the principal. The protocol and agent desk previews
do not establish human findability, complete translation or functional E2E.

Track other non-English authored pages as migration work. After owner review,
translate them in place when the record is meant to remain canonical, or create
a clearly linked English companion when a source-preservation requirement is
established. Do not delete, relocate, or rewrite a ratified decision, imported
specification, or historical receipt merely to satisfy language consistency;
use the appropriate owner and preservation process, retain source attribution,
and make the English reader-facing interpretation explicit.

When reviewing a page, check that its English text keeps the source's meaning,
scope, time, status, authority, and uncertainty intact. A translation is not a
fresh verification of the underlying code or claim. State any review or
verification evidence separately from the language change.
