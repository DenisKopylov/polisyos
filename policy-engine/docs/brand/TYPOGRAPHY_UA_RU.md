# Cyrillic Typography and Pluralisation

> Rules for Ukrainian and Russian text in PolicyOS: typeface behaviour,
> punctuation, hyphenation, pluralisation, dates, numbers, and currency.
> Foundation for Phase 1.7 (i18n — UA/RU typography, G6).

- Status: Foundation (Phase 1.0)
- Date: 2026-04-22
- Owner: Denis Kopylov
- Related: [COMPOSITION_RULES](COMPOSITION_RULES.md), Phase 1.7 of the design plan.

## 1. Languages in scope

- Ukrainian (`uk-UA`) — primary.
- Russian (`ru-RU`) — read-only target; no writing UI is produced in Russian
  by default, but content ingested from Russian sources must render
  correctly.

- English (`en-US`) — baseline, defines fallback.

Polish, Belarusian, Kazakh, and other Cyrillic languages are **out of scope**
for Wave 1. They may share typography rules but will not be tested until
Wave 2.

## 2. Typeface behaviour

| Face             | Latin | Cyrillic support                                         | Notes                                                                                                                                      |
| ---------------- | ----- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Manrope          | Yes   | Yes (extended Cyrillic, Ukrainian accents)               | Primary UI face. Use as-is.                                                                                                                |
| IBM Plex Mono    | Yes   | Yes (Cyrillic variant)                                   | Telemetry, code, IDs. Uses same face across scripts; line-height unchanged.                                                                |
| Instrument Serif | Yes   | **Partial** (basic Cyrillic, missing `ґ`, `ї`, `є`, `ё`) | Reserved for `PolicyPropositionMark` only; if content is Cyrillic, fall back to Manrope italic with tighter tracking (`--tracking-tight`). |

`@font-face` declarations remain unchanged; the fallback chain handles
mis-covered glyphs via `font-synthesis: none` to avoid faux-bold rendering.

## 3. Character set and normalisation

- Input strings are normalised to Unicode **NFC** at the API boundary.
- Ukrainian apostrophe is `U+02BC` (MODIFIER LETTER APOSTROPHE), not
  `U+2019` (RIGHT SINGLE QUOTATION MARK) or `U+0027` (ASCII apostrophe).
  A lint rule (`policy-engine/tools/design/check-cyrillic-apostrophe.ts`)
  validates translation files.

- The lowercase `і` (`U+0456`) and uppercase `І` (`U+0406`) must not be
  confused with Latin `i` / `I`; fuzzy matching functions against
  domain terms normalise via script-aware comparison.

- Soft hyphen (`U+00AD`) is allowed inside long compounds; the
  translator may insert them. Browsers render correctly under
  `hyphens: manual`.

## 4. Punctuation

| Mark                | UA                                     | RU                                     | EN                     |
| ------------------- | -------------------------------------- | -------------------------------------- | ---------------------- |
| Primary quotation   | `«…»`                                  | `«…»`                                  | `"…"`                  |
| Nested quotation    | `„…"`                                  | `„…"`                                  | `'…'`                  |
| Dash (range)        | `–` en dash, no surrounding spaces     | `–` en dash, no surrounding spaces     | `–` en dash, no spaces |
| Dash (clause)       | `—` em dash, thin spaces on both sides | `—` em dash, thin spaces on both sides | `—` em dash, no spaces |
| Ellipsis            | `…` single character                   | `…` single character                   | `…` single character   |
| Thousands separator | non-breaking space `U+00A0`            | non-breaking space                     | comma                  |
| Decimal separator   | comma `,`                              | comma `,`                              | period `.`             |

- Thin space is `U+2009`. Translators must not substitute regular space.
- Non-breaking space is mandatory between a number and its unit
  (`250 млн грн`, `12 %`), between initials and a surname, and after
  prepositions `у`, `в`, `з`, `і`, `а`, `та`, `до`, `на`, `під`, `при`.

## 5. Pluralisation

Ukrainian and Russian have three plural forms beyond the English `one` /
`other`. The CLDR rule set:

| Form    | Example count (UA)    | Example word (UA) |
| ------- | --------------------- | ----------------- |
| `one`   | 1, 21, 31, 101        | рішення           |
| `few`   | 2–4, 22–24, 32–34     | рішення           |
| `many`  | 0, 5–20, 25–30, 35–40 | рішень            |
| `other` | 1.5, 2.7 (fractional) | рішення           |

The runtime uses `Intl.PluralRules` and
`react-intl`'s `FormattedPlural` component. Translation files
(`locales/uk-UA/*.json`) carry all four keys:

```json
"runs.count": {
  "one": "{count} запуск",
  "few": "{count} запуски",
  "many": "{count} запусків",
  "other": "{count} запуску"
}
```

CI fails if a translation key used with `FormattedPlural` lacks any of the
four forms. Script:
`policy-engine/tools/i18n/check-plural-coverage.ts`.

## 6. Gender agreement

Ukrainian and Russian verbs and past-tense participles agree in gender.
In domain copy this appears in sentences like "Прогон завершено" (neuter)
vs "Політику завершено" (feminine subject).

- Rule: **prefer impersonal constructions** in system messages. "Прогон
  завершено" is neutral; "Прогон завершений" is not. This matches the
  `no-you` dimension of `style-guide.md` and removes a whole class of
  agreement bugs.

- Named entities (a policy called "Податок на додану вартість") must
  carry their grammatical gender in the translation string metadata
  to allow correct agreement when interpolated.

## 7. Date and time

| Format      | UA                  | RU                  | EN                |
| ----------- | ------------------- | ------------------- | ----------------- |
| Short date  | `22.04.2026`        | `22.04.2026`        | `2026-04-22`      |
| Medium date | `22 квіт. 2026`     | `22 апр. 2026`      | `Apr 22, 2026`    |
| Long date   | `22 квітня 2026 р.` | `22 апреля 2026 г.` | `April 22, 2026`  |
| Time        | `14:30` 24-hour     | `14:30` 24-hour     | `2:30 PM` 12-hour |
| Timezone    | `за Києвом (UTC+2)` | `по Москве (UTC+3)` | `UTC`             |

Implementation: `Intl.DateTimeFormat` with locale-specific options. Month
genitive case is handled by the runtime; no manual lookup tables.

## 8. Numbers and currency

- Ukrainian currency is `грн` (UAH), postfix, with non-breaking space:
  `12 500,00 грн`. Formal documents use `UAH 12 500,00`.

- Russian currency is `₽` or `руб.`, postfix, with non-breaking space.
- Numeric formatting via `Intl.NumberFormat('uk-UA', { style: 'currency',
currency: 'UAH' })`. Never hand-format.

- Large amounts use the scale `тис. / млн / млрд` (UA) and
  `тыс. / млн / млрд` (RU); decimals are cropped to one digit.

## 9. Line-height, tracking, and measure

| Context              | UA/RU adjustment                                                                       | EN baseline        |
| -------------------- | -------------------------------------------------------------------------------------- | ------------------ |
| Body text            | `--leading-normal` (1.55) → keep                                                       | 1.55               |
| Headings `text-2xl+` | Loosen tracking to `--tracking-normal` (Cyrillic does not benefit from tight tracking) | `--tracking-tight` |
| Monospace            | Unchanged — IBM Plex Mono Cyrillic metrics match Latin                                 | —                  |
| Measure              | 65 characters max per line                                                             | 72 characters max  |

The Cyrillic measure is **tighter** because Cyrillic glyphs average wider
than Latin at matching x-height; longer lines impair scanning.

## 10. Icon + text alignment

- Glyphs rendered at 14px align to the cap-height of Manrope, not the
  x-height. For Cyrillic this is the same as Latin — no adjustment.

- Baseline shift inside buttons is `0.5px` on Retina displays for glyphs
  at 16px; this is implemented in `<Glyph />` with a `transform:
translateY(0.5px)` under `@media (min-resolution: 2dppx)`.

## 11. Specimen

The specimen page `apps/runtime-dashboard/src/shared/brand/specimen/`
renders all combinations of face × weight × script for visual review.
Phase 1.7 will expand the specimen with a plural-form tester and
date-format inspector.

## 12. Out of scope (for Phase 1.0 foundation)

- Actual Ukrainian / Russian translations of the product strings — owned
  by Phase 1.7.

- Keyboard-layout affordances (IME, diacritic entry).
- Right-to-left scripts.
- Voice synthesis for accessibility.
