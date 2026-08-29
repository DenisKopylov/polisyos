# INT-R6 Anchor And Citation Verification

## Method And Denominators

Repository anchors were read at exact package SHA `5e47c868c2c1d4d66fa11fcddcc972dbb55e95d3`; removed artifacts were read at `b612b21272c732d53cfde8569846cfb7a0c73f5a`. Directory populations came from connector contents/tree reads, never code-search totals. Every recursive tree response used below reported `truncated=false`.

External denominator: the 17 principal Markdown locators listed in the main deliverable’s sources section, plus the five commissioned survey artifacts. Resolution means the target institution/document was reached and supports the narrow proposition stated here; it does not mean every broader sentence in the package was independently re-researched.

## Repository Anchor Verification

| anchor | connector observation | result |
|---|---|---|
| D4-A1 | exact file read of `docs/brand/ATLAS_SOURCE_OF_TRUTH.md` | resolves; `en` authored primary, `uk` translation, `ru` frozen, source rendering separate, RTL unsupported |
| W4-K05 / W4-K06 | exact file read of `docs/system-design-decisions/wave4-decision-evidence-ratification.md` | resolves; three vocabularies and prose-not-chain rule confirmed |
| product locale owner | `apps/runtime-dashboard/src/shared/i18n/locale.ts` | resolves; active `en`/`uk`, `en` primary, `ru` legacy constant |
| launch crossing | `apps/runtime-dashboard/src/features/composer/domain/forms.ts` | resolves; workflow and NL requests receive `locale_preference` from UI context |
| parity mechanism | `apps/runtime-dashboard/src/shared/i18n/parity.test.ts` | resolves; active key parity and frozen-Russian integrity, not semantic equivalence |
| decision validity statuses | `src/polisyos/core/contracts/decision_validity.py` | resolves; `stale`, `superseded`, `withdrawn` remain distinct enum members |
| namespaced blockers | `src/polisyos/runtime/quality/evaluation_safety.py` | resolves; versioned `polisyos.eval_safety.*@1.0.0` family |
| `may_not_use_for` | `src/polisyos/core/contracts/search.py` | resolves; tuple members remain strings |
| scoped `limited` | `src/polisyos/scientist/evidence/claims/models.py` | resolves in two separate enum owners |
| Lex/source model | `src/polisyos/data_forge/domains/legal/contracts.py`, `src/polisyos/lex/types.py` | resolves; one document language, Ukrainian-source/English-canonical extraction shape, no authority-text-set relation |
| MACHINE/trust twin | `apps/runtime-dashboard/src/features/trust/export/trustPostureTwin.ts` | resolves; exact artifact-to-visible-DOM ID/state parity, not translation certification |
| package 30-row register | `int-r6/06-findings-standing-and-pattern-pass.md` | resolves; 30 unique rows F-001–F-030 |
| removed measured baseline | `int-r6/repo-baseline-study.md` at pre-repair SHA | resolves; 223 lines and concrete current-tree walks |
| declared successor | `int-r6/01-repository-baseline.md` at package SHA | resolves; 105 lines and multiple facts reverted to unresolved |

The package relative links among the main deliverable and `int-r6/01`–`06` resolve after the delivery move because they are relative to the canonical directory. The 21-line scaffold contains headings only and no link identifying the substantive entrypoint.

## External Citation Verification

| # | package locator | resolution | narrow audit result |
|---:|---|---|---|
| 1 | [Vienna Convention on the Law of Treaties, Article 33](https://legal.un.org/ilc/texts/instruments/english/conventions/1_1_1969.pdf) | `resolved` | Article 33 supports equal authority of authenticated texts, optional prevailing text, non-authentic additional translations, and reconciliation |
| 2 | [Council Regulation No 1](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:31958R0001) | `resolved` | supports EU language regime; not by itself proof of sentence-level equivalence |
| 3 | [CILFIT, Case 283/81](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:61981CJ0283) | `resolved` | multilingual comparison/equally authentic versions is accurately invoked |
| 4 | [Skoma-Lux, C-161/06](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:62006CJ0161) | `resolved` | supports publication-language/enforceability distinction |
| 5 | [Canada Constitution Act, 1982](https://laws-lois.justice.gc.ca/eng/const/) | `resolved` | official federal bilingual-authority basis resolves |
| 6 | package link for `R v Daoust`, 2004 SCC 6 | `misresolved` | package points to SCC item `2110`; the official decision is item `2117` |
| 7 | [Swiss Federal Constitution / Fedlex](https://www.fedlex.admin.ch/eli/cc/1999/404/en) | `resolved` | supports multilingual federal setting; the package should cite the specific publication/authenticity rule when asserting equal binding effect |
| 8 | [Constitution of Ukraine](https://zakon.rada.gov.ua/laws/show/254%D0%BA/96-%D0%B2%D1%80#Text) | `resolved through official Rada search` | Article 10 state-language proposition confirmed |
| 9 | [Law of Ukraine No. 2704-VIII](https://zakon.rada.gov.ua/laws/show/2704-19#Text) | `resolved through official Rada search` | official language statute resolves; current edition is versioned and should be cited with access/version date |
| 10 | [ISO 704:2022](https://www.iso.org/standard/79077.html) | `resolved` | concept-oriented terminology source resolves |
| 11 | [ISO 1087:2019](https://www.iso.org/standard/62330.html) | `resolved` | concept/designation vocabulary source resolves |
| 12 | [ISO 30042:2019](https://www.iso.org/standard/62510.html) | `resolved; revision underway` | current published TBX edition remains valid; Edition 3 committee draft is underway |
| 13 | [ISO 17100:2015](https://www.iso.org/standard/59149.html) | `resolved; revision activity noted` | process/competence standard resolves; it does not confer legal authenticity |
| 14 | [ISO 24495-1:2023](https://www.iso.org/standard/78907.html) | `resolved` | plain-language principles resolve; not an equivalence certificate |
| 15 | [Unicode Bidirectional Algorithm](https://www.unicode.org/reports/tr9/) | `resolved` | bidi technical basis resolves |
| 16 | [W3C inline bidi guidance](https://www.w3.org/International/articles/inline-bidi-markup/uba-basics) | `resolved` | practical mixed-direction guidance resolves |
| 17 | [Unicode CLDR](https://cldr.unicode.org/) | `resolved` | locale/plural/number data source resolves |

The five commissioned surveys were also read as supplied evidence, not repository capability. Their strongest shared boundary is consistent with the package: institutions assign authority and procedures rather than mathematically prove translation identity; direct en→uk evidence is narrow; concept IDs encode a governed assertion rather than prove it; status vocabularies are heterogeneous; and plain-language adaptation requires a separate semantic check.

## Unresolved Anchors And Citations

- Short commit identifier `df90e10fb` did not resolve to a full commit through the connector. No claim in this audit is pinned to it.
- The connector could read each catalogue blob and line ranges but could not materialize the complete decoded payload into the executable environment. Current identity arithmetic is therefore unresolved by this auditor.
- The exact `atlas-slices` directory listing at the package SHA contained no directly named `DS12-*` or `DS13-*` file. Code-search results were used only to navigate related records, not to prove absence. The DS12/DS13 seam remains a routed/documentation seam rather than a verified implementation anchor.
- Several external table entries identify an institution and edition but omit the paragraph, article or page that supports the specific proposition. This is adequate navigation, not precise claim anchoring.

## Citation Quality Findings

### CQ-01 — wrong SCC locator

`R v Daoust` must point to official SCC item `2117`, not `2110`. The legal proposition is supportable; the package link is not.

### CQ-02 — document-level citations are sometimes broader than the proposition

The Swiss equal-binding claim should cite the specific publication-law provision rather than only an English constitution landing page. ISO references should identify clauses/scopes where the package draws a precise model distinction.

### CQ-03 — currentness metadata matters

ISO 30042:2019 is still the published standard but is marked for revision, with Edition 3 under development. The package should preserve edition/date rather than cite “TBX” timelessly. Ukrainian statutes should carry an edition/access date because the official records change.

### CQ-04 — external authority is correctly bounded in most cases

The package generally says what external sources do **not** prove. It does not treat VCLT, ISO, apostille-like provenance or plain-language standards as universal semantic certificates. That restraint is commendable.

## Residual Band

This pass verified the package’s principal source register, not every secondary paper mentioned inside the five long survey reports. Paywalled ISO clauses were checked through official scope/status pages and the surveys’ extracted evidence, not full licensed text. No conclusion is drawn about legal advice or enforceability in a live case.
