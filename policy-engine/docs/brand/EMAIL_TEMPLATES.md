# Email Templates

This retained template is design guidance only. D6 classifies email delivery as
`surface_out_of_scope` for the current Atlas slice plan: the repository has no
admitted mail-delivery producer, provider/privacy owner, or notification
retention contract. Email previews and fixtures do not imply that PolicyOS
sends email or publishes an authority-bearing summary. Revisit only with the
typed notification, privacy/redaction, delivery, locale, and negative-disclosure
chain recorded in `ATLAS_SOURCE_OF_TRUTH.md` D6.

If a successor surface is admitted, emails may summarize explicitly shareable
run, compare, and scenario links. They are not evidence dumps.

## Public Summary Payload

Email rendering accepts only a public summary payload:

- title;
- kind: `run`, `compare`, or `scenario`;
- key quantity label/value/unit;
- trust status;
- temporal scope;
- draft/verified state;
- call-to-action URL;
- optional short summary.

Raw source text, private notes, hidden reviewer comments and unredacted
lineage nodes are prohibited.

## Rendering Rules

- Mobile width: 320 px minimum.
- Desktop width: 640 px content maximum.
- Plain-text fallback is required for every template.
- Status is text-first: `verified`, `pending`, `stale`, `disputed`,
  `untraced`.
- Links must include a visible URL in the plain-text version.

## Accessibility

- One H1-equivalent title.
- Tables only for tabular metadata.
- Color never carries unique meaning.
- The first paragraph explains whether the artifact is a draft.
