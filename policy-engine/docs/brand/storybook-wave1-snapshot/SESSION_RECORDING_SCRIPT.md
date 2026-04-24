# Wave 1 Onboarding Recording Script

Use this script for the closeout screencast or Figma review recorded after the
Wave 1 candidate is deployed.

## Target

- Duration: `8-12` minutes
- Audience: design reviewer, frontend engineer, PM, external consultant
- Date target: after staging verification starts on `2026-04-22`

## Sequence

1. Open the Janus brand surface and show `brand-janus--sizes`.
   Call out the updated favicon, Atlas/Janus dual-brand logic, and glyph stroke
   discipline.

2. Open `brand-glyphs--all-radicals-at-every-size`.
   Show the ten-radical system and explain why the vocabulary stays capped.

3. Open `brand-evidence-sigil--default` and
   `brand-provenance-strip--default`.
   Explain how evidence, provenance, freshness, and governance now render as a
   compact editorial layer rather than ad-hoc badges.

4. Open `design-system-uncertainty--atlas-preview`.
   Walk through uncertainty bands, fan charts, and quantile views. Mention
   identified, estimated, and assumed states.

5. Switch to `design-system-uncertainty--dark-theme`.
   Confirm dark-theme readability and that the visual language survives theme
   inversion.

6. Open `features-platform-appearancesection--default`.
   Change theme, contrast, and density. Set density to `condensed` and explain
   the analyst-use case.

7. Open `artifacts-reading-view-monograph-layout--default`.
   Explain the prose system: editorial hierarchy, print-minded layout,
   footnotes, margin notes, and packet readability.

8. Open `shared-ui-authoredtext--prominent-audit-rail`.
   Show all authorship registers in one view and the timeline rail for mixed
   human/AI/citation provenance.

9. Open `shared-text--ukrainian-typography`.
   Call out `₴`, quotation marks, non-breaking spaces, and mono-text cyrillic
   handling.

10. Close on the compliance packet.
    Point to `docs/compliance/A11Y_AUDIT_2026Q2.md` and `docs/compliance/VPAT.md`
    as the audit evidence for Wave 1 closeout.

## Checklist Before Recording

- Use the staging rollout manifest `staging-feature-flags.all_on.json`.
- Confirm the Storybook deployment URL is the same one shared with
  stakeholders.

- Keep browser zoom at `100%` unless the review explicitly tests accessibility
  resizing.

- Record one dark-theme pass and one light-theme pass if time allows.
