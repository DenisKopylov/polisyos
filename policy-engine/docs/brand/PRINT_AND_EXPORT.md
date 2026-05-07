# Print And Export

Print/export is a governance surface, not a screenshot. Printed artifacts must
preserve enough metadata for a reviewer to understand what was rendered, when,
from which packet and with which trust/provenance state.

## Rules

- Dashboard chrome disappears in print.
- Reading View, bureaucratic renders and run summaries keep document metadata,
  trust status, temporal scope, provenance summary and source appendix.
- Page breaks avoid headings, figures, trust rows and bureaucratic blocks.
- Links print their target unless the export format already embeds a link map.
- Draft watermarks survive HTML/PDF/DOCX export.
- Screen-only interaction controls are hidden with `data-print-hidden="true"`.

## Required Metadata

Every official-looking export carries:

- packet id and packet hash;
- render timestamp;
- template id/version where applicable;
- temporal scope;
- verification status and hash;
- draft/verified state;
- source appendix or explicit "no public source links" line.

## CSS Contract

The global print entrypoint is
`apps/runtime-dashboard/src/styles/print.css`.

Use these hooks instead of ad hoc selectors:

- `.media-screen-only` and `.media-print-only`;
- `.print-document-metadata`;
- `.print-provenance-summary`;
- `.print-source-appendix`;
- `[data-print-document="true"]`;
- `[data-print-keep-together="true"]`;
- `[data-print-hidden="true"]`.

## Snapshot Fixtures

The print gate covers these representative surfaces:

- Run Detail with 100+ quantities, trust metadata and a provenance summary.
- Reading View with long narrative blocks and source appendix.
- Native bureaucratic document with watermark, signatures and annexes.
- Compare/Scenario summary with temporal scope and no private raw-source text.

Before release, the visual gate is run against five real decision packet
fixtures: two decision-packet artifacts, one run report, one bureaucratic
render and one compare/scenario summary. The static design gate also verifies
that the A4 Reading View snapshot exists and is large enough to be a real page,
not an empty capture.
