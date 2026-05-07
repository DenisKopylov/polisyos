# WCAG 2.2 AA Contrast Matrix

> Auto-generated from `apps/runtime-dashboard/src/styles.css` by
> `policy-engine/tools/design/check-contrast.ts` using `axe-core` color utilities.
> Manual edits are not permitted.

- Status: Generated
- Owner: Denis Kopylov
- Source: `apps/runtime-dashboard/src/styles.css`
- Generator: `policy-engine/tools/design/check-contrast.ts`

## Light Theme Tokens

| Token | Hex |
| --- | --- |
| `--paper` | `#FBF8F2` |
| `--canvas` | `#EFE9DC` |
| `--sand` | `#F4EFE6` |
| `--ink` | `#17191D` |
| `--graphite` | `#28333C` |
| `--slate` | `#40515F` |
| `--teal` | `#115E57` |
| `--teal-vibrant` | `#1C8B82` |
| `--ember` | `#92391D` |
| `--gold` | `#6C5111` |

## Light Theme Matrix

| Background ↓ / Foreground → | `--ink` | `--graphite` | `--slate` | `--teal` | `--teal-vibrant` | `--ember` | `--gold` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `--paper` #FBF8F2 | 16.6 Pass | 12.2 Pass | 7.7 Pass | 7.2 Pass | 3.9 Large | 7.0 Pass | 7.0 Pass |
| `--canvas` #EFE9DC | 14.5 Pass | 10.7 Pass | 6.8 Pass | 6.3 Pass | 3.4 Large | 6.1 Pass | 6.1 Pass |
| `--sand` #F4EFE6 | 15.4 Pass | 11.3 Pass | 7.2 Pass | 6.6 Pass | 3.6 Large | 6.5 Pass | 6.5 Pass |

## Dark Theme Tokens

| Token | Hex |
| --- | --- |
| `--paper` | `#1D1917` |
| `--canvas` | `#120F0E` |
| `--surface` | `#59504C` |
| `--ink` | `#F5EFE2` |
| `--slate` | `#BCAE9D` |
| `--teal` | `#115E57` |
| `--gold` | `#6C5111` |
| `--ember` | `#92391D` |

## Dark Theme Matrix

| Background ↓ / Foreground → | `--ink` | `--slate` | `--teal` | `--gold` | `--ember` |
| --- | --- | --- | --- | --- | --- |
| `--paper` #1D1917 | 15.2 Pass | 8.0 Pass | 2.3 Fail | 2.3 Fail | 2.3 Fail |
| `--canvas` #120F0E | 16.7 Pass | 8.8 Pass | 2.5 Fail | 2.6 Fail | 2.6 Fail |
| `--surface` #59504C | 7.2 Pass | 4.5 Pass | 1.7 Fail | 1.7 Fail | 1.7 Fail |

## Enforcement

- `Pass` means ratio >= 4.5:1 and is valid for normal text.
- `Large` means ratio >= 3.0:1 and is valid only for large text or non-text contrast.
- `Fail` means the pair is prohibited for body and small text unless a documented exemption exists.
- Dark-theme raw brand accents (`--teal`, `--gold`, `--ember`) are observability-only matrix entries and are not text-safe foreground defaults.
- PR gate: `node --experimental-strip-types ../../tools/design/check-contrast.ts`.
