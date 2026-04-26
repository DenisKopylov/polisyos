# Email Templates

PolicyOS emails summarize shareable run, compare and scenario links. They are
not evidence dumps.

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
