# PolicyOS — План радикального улучшения дизайна и фронтенда

> План построен как **две волны**, каждая — последовательность фаз.
> Волна 1 закрывает шесть критических SOTA-пробелов.
> Волна 2 внедряет best-in-class примитивы, которые делают PolicyOS
> категорией, а не конкурентом на рынке.
>
> Дата: 2026-04-22 · Статус: active · Владелец: Denis Kopylov
> Версия: 2.0 (two-wave phased-by-design)

---

## Оглавление

- [0. TL;DR и тезис](#0-tldr-и-тезис)
- [1. Диагноз текущего состояния](#1-диагноз-текущего-состояния)
- [2. Сквозные инварианты плана (non-goals)](#2-сквозные-инварианты-плана-non-goals)
- [3. Архитектура двух волн](#3-архитектура-двух-волн)
- **Волна 1 — SOTA Gap Closure**
  - [Фаза 1.0 — Foundations](#фаза-10--foundations)
  - [Фаза 1.1 — Visual language (Janus + Glyphs + Sigil + Provenance Strip)](#фаза-11--visual-language)
  - [Фаза 1.2 — Uncertainty visualization (G1)](#фаза-12--uncertainty-visualization-g1)
  - [Фаза 1.3 — Accessibility WCAG 2.2 AA+ (G2)](#фаза-13--accessibility-wcag-22-aa-g2)
  - [Фаза 1.4 — Dark theme v2 + density modes (G3)](#фаза-14--dark-theme-v2--density-modes-g3)
  - [Фаза 1.5 — Prose system для decision packets (G4)](#фаза-15--prose-system-для-decision-packets-g4)
  - [Фаза 1.6 — AI-authorship registry (G5)](#фаза-16--ai-authorship-registry-g5)
  - [Фаза 1.7 — i18n UA/RU typography (G6)](#фаза-17--i18n-uaru-typography-g6)
  - [Фаза 1.8 — Wave 1 closeout](#фаза-18--wave-1-closeout)
- **Волна 2 — Best-in-class primitives**
  - [Фаза 2.0 — Provenance law foundations](#фаза-20--provenance-law-foundations)
  - [Фаза 2.1 — Time-as-primitive (B1)](#фаза-21--time-as-primitive-b1)
  - [Фаза 2.2 — Provenance-on-hover (B2)](#фаза-22--provenance-on-hover-b2)
  - [Фаза 2.3 — Policy diff (B3)](#фаза-23--policy-diff-b3)
  - [Фаза 2.4 — Counterfactual layer (B4)](#фаза-24--counterfactual-layer-b4)
  - [Фаза 2.5 — Native bureaucratic rendering (B5)](#фаза-25--native-bureaucratic-rendering-b5)
  - [Фаза 2.6 — Trust view (B6)](#фаза-26--trust-view-b6)
  - [Фаза 2.7 — System polish](#фаза-27--system-polish)
- [4. Success metrics](#4-success-metrics)
- [5. Risks & mitigations](#5-risks--mitigations)
- [6. Owner matrix](#6-owner-matrix)
- [7. Anchor artifacts](#7-anchor-artifacts)

---

## 0. TL;DR и тезис

Разница между **SOTA** и **best-in-class** — не количественная. SOTA догоняет лучшее на рынке; best-in-class **изобретает примитив**, которому потом подчиняется вся категория (Linear — feel скорости; Figma — multiplayer-as-medium; Notion — block; Observable — reactive document).

PolicyOS в этом плане получает два несводимых примитива, но реализует их не как
ещё две UI-фичи, а как новый системный закон:

- **B1** Time-as-primitive — бимпоральный курсор: `valid_at` (когда факт
  действовал) + `tx_at` (когда система это знала), показанный оператору как
  единое глобальное измерение интерфейса.
- **B2** Provenance-on-hover — progressive disclosure за каждым decision-bearing
  числом: inline cue → compact provenance popover → deep-dive graph/export.

Волна 2 начинается с spine 2.0–2.2: **no naked decision numbers**,
**time is bitemporal**, **provenance is progressive disclosure**. Вокруг этого
достраиваются ещё четыре примитива (policy diff, counterfactual layer, native
bureaucratic rendering, trust view) и закрываются шесть SOTA-пробелов — всё
поверх существующей Atlas-системы без слома её лексического и хроматического
ядра.

**План построен как две волны. Каждая — последовательность фаз. Фазы упорядочены по зависимостям, а не по темам.** Каждая фаза содержит: тезис, preconditions, scope, deliverables с точными путями, контракты backend-API, acceptance criteria, тесты, риски. Между волнами — gate с ревью.

Общий бюджет: **~32 недели** (Волна 1 — 14 недель; Волна 2 — 18 недель). Рассчитано на одного fullstack-инженера + подключаемые: design-review, legal (для жанров), DBA (для `TemporalScope`/bitemporal-контрактов).

---

## 1. Диагноз текущего состояния

### 1.1. Капитал — что **не трогаем**

| Слой                           | Состояние                                                                                               | Почему капитал                              |
| ------------------------------ | ------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| Лексическая дисциплина         | 29-терминный домен, запрет `you`, sentence case, no emoji                                               | Редчайший уровень в AI-продуктах 2025–26    |
| Хроматическая палитра          | Sandstone + graphite без синевы                                                                         | Осознанное меньшинственное позиционирование |
| Glass-панели с inset rim-light | Сквозной мотив                                                                                          | Узнаваемая подпись                          |
| Сигнальная триада              | teal=verified, ember=blocked, gold=pending                                                              | Жёсткая семантика                           |
| Типография                     | Manrope 800 / IBM Plex Mono / Instrument Serif                                                          | Профессиональный контроль регистров         |
| UI-база                        | 70+ шаренных компонентов в `src/shared/ui/`, `.a11y.test.tsx` рядом                                     | Готовая техническая основа                  |
| Chart-база                     | 20+ компонентов в `src/shared/charts/` (ConfidenceDial, ForestPlot, GradedErrorBar, UncertaintyDisplay) | Частично покрывает §1.2                     |
| Токены                         | `designTokens.ts` (evidence/governance/severity/status/transport)                                       | Готовые семантические шкалы                 |
| Дата-слой                      | 50+ React Query хуков, openapi-typescript, SSE runsLiveMachine                                          | Фундамент для реактивных примитивов         |
| Fabric provenance/time-travel  | `FabricLineageTracker`, OpenLineage export, bitemporal `world_query`, snapshots/branches                | Готовое backend-ядро для Wave 2 spine       |

### 1.2. Шесть критических SOTA-пробелов (Wave 1 scope)

| #   | Пробел                                                                                   | Последствие                                                                     | Фаза |
| --- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ---- |
| G1  | Визуальный язык **неопределённости** не систематизирован (есть примитивы, нет языка)     | PolicyOS показывает CI/identifiability/counterfactual spreads как плоские числа | 1.2  |
| G2  | **Accessibility** (WCAG 2.2 AA) не задокументирована, нет pattern-fills для колор-блайнд | Блокер для процурмента в ЕС/укр. госсектор                                      | 1.3  |
| G3  | Нет **dark theme v2** и **density modes**                                                | Аналитики в 8-часовых сессиях уйдут в нативный терминал                         | 1.4  |
| G4  | **Prose system** для decision packets пуст                                               | Разрыв между «что показывает» и «что производит»                                | 1.5  |
| G5  | Нет регистра для **AI-authored** текста (vs цитата vs оператор)                          | В 2026 — определяющий SOTA-признак для AI-продуктов                             | 1.6  |
| G6  | **i18n** под украинско-русскую реальность не специфицирован                              | Ломается плюрализация, типографика, даты, валюта                                | 1.7  |

### 1.3. Шесть best-in-class примитивов (Wave 2 scope)

| #   | Примитив                      | Конкурентный анализ                                      | Фаза |
| --- | ----------------------------- | -------------------------------------------------------- | ---- |
| B1  | Time-as-primitive             | Ни одного govtech-инструмента с bitemporal UX            | 2.1  |
| B2  | Provenance-on-hover           | Observable флиртует, никто не коммитится на каждое число | 2.2  |
| B3  | Policy diff (каузальный)      | Чистое поле                                              | 2.3  |
| B4  | Counterfactual layer          | Никто                                                    | 2.4  |
| B5  | Native bureaucratic rendering | Все GPT-обёртки рендерят generic markdown                | 2.5  |
| B6  | Trust view                    | Никто                                                    | 2.6  |

---

## 2. Сквозные инварианты плана (non-goals)

Применяются ко **всем** фазам. Любой PR, нарушающий их, блокируется на review.

- **Не** добавляем маскота. Роль исполняют **глифы** (§1.1) и **AuthoredText registry** (§1.6).
- **Не** отходим от sandstone + graphite. Никакого синего. Никаких градиентов свыше двухцветных rim-light.
- **Не** расширяем сигнальную триаду teal/ember/gold. Новые семантики ищут форму внутри неё (pattern-fills, глифы, диакритика).
- **Не** заменяем Atlas-mark на чистого Януса — Janus это второй слой, не замена.
- **Не** добавляем 3D-рендеры, сургучные печати, тяжёлые bevel/emboss.
- **Не** делаем glyph-алфавит на 60+ знаков. Десять радикалов — жёсткий лимит.
- **Не** вводим emoji ни в каком регистре (включая служебные сообщения CLI).
- **Не** ломаем OpenAPI-контракты без миграции — все backend-изменения через additive fields + deprecation window ≥ 2 релиза.
- **Не** отключаем `eslint-plugin-boundaries` и `dependency-cruiser`-правила — новые компоненты обязаны вписаться в feature-slice архитектуру.

---

## 3. Архитектура двух волн

### 3.1. Критерии перехода между волнами (gate)

Wave 1 → Wave 2 допускается только при одновременном выполнении:

- Все G1–G6 closed (acceptance criteria каждой фазы).
- Storybook visual regression — 0 unexpected diffs.
- `pnpm test` + a11y — зелёно.
- WCAG audit report подписан (§1.3).
- VPAT документ опубликован в `docs/compliance/VPAT.md`.
- Feature flags всех Wave 1 фич выключены по умолчанию в production, но включены в staging; нет P1/P0 багов 14 дней подряд.

### 3.2. Параллелизация

Внутри волны некоторые фазы можно вести параллельно:

- Wave 1: **1.2 || 1.3 || 1.4** после 1.0 и 1.1.
- Wave 1: **1.5 || 1.6** после 1.1 (требуют глифов) и 1.4 (требуют dark theme для prose reader).
- Wave 1: **1.7** может идти параллельно любому этапу после 1.0.
- Wave 2 spine: **2.0 → 2.1 → 2.2** задаёт обязательный порядок для
  decision-bearing numbers. Внутри spine можно параллелить workstream'ы
  (backend contracts, UI fixtures, codemod, perf/a11y harness), но нельзя
  выпускать downstream-фазы поверх неполного quantity/temporal/lineage
  контракта.
- Wave 2 после spine: **2.3** и **2.4** начинаются только после 2.1 + 2.2;
  **2.6** начинается после 2.2; **2.5** можно вести отдельным
  publications/legal-потоком после 1.5 + 1.6, но интеграцию с trust/lineage
  закрывать после 2.2.
- Wave 2: **2.7** остаётся хвостовым polish, но его независимые части (CLI,
  print, OG/email templates) можно подбирать opportunistically.

### 3.3. Feature flags

Каждая фаза ≥ 1.2 вводит один feature flag в `src/app/providers/feature-flags` формата `design.wave{N}.phase{Y}.{slug}`:

- По умолчанию `off` в production.
- `on` в development и staging после acceptance.
- Постепенный rollout через manifest после 14 дней стабильности.
- Flag удаляется через релиз после 100% rollout — не остаётся as dead code.

---

## Волна 1 — SOTA Gap Closure

## Фаза 1.0 — Foundations

**Длительность:** 2 недели.
**Тезис:** ничего не меняется в UI, но закладывается весь документный и токен-фундамент, без которого последующие фазы будут изобретать формат на ходу.

### Preconditions

- Свежий main, все CI-пайплайны зелёные.
- Выделены ~10% времени дизайнера-консультанта на review ADR-ов.

### Scope

Документная архитектура + contrast matrix + glyph spec + uncertainty language spec + motion spec foundation + ADR-ы.

### Deliverables

**Папки и файлы:**

```text
policy-engine/docs/brand/
├── GLYPH_SPECIFICATION.md           — геометрия, штрих, диакритика, грамматика
├── UNCERTAINTY_LANGUAGE.md          — паттерны, окраска, do/don't
├── A11Y_CONTRAST.md                 — WCAG 2.2 AA matrix со всеми парами
├── MOTION.md                        — кривые, длительности, state transitions
├── COMPOSITION_RULES.md             — anti-patterns и правила соседства
└── TYPOGRAPHY_UA_RU.md              — кириллическая типографика, плюрализация

policy-engine/docs/adr/
├── ADR-042-janus-atlas-dual-brand.md
├── ADR-043-provenance-law.md
├── ADR-044-time-as-primitive.md
├── ADR-045-glyph-alphabet-limit-10.md
└── ADR-046-authored-text-registry.md

policy-engine/docs/compliance/
└── VPAT.md                          — Voluntary Product Accessibility Template (skeleton)
```

**Конкретные артефакты:**

- `docs/compliance/A11Y_CONTRAST.md` — канонический auto-generated артефакт со всеми парами `(background-token, foreground-token)` и contrast ratio; `docs/brand/A11Y_CONTRAST.md` остаётся spec/index-страницей.
- `GLYPH_SPECIFICATION.md` — сетка 5×5, stroke-width 1.25–1.5, список всех 10 радикалов с геометрическим описанием.
- `UNCERTAINTY_LANGUAGE.md` — 7 паттернов с SVG-превью и указанием каких именно chart-компонентов затрагивает.
- `MOTION.md` — `--motion-duration-*` и `--motion-ease-*` tokens, правила для reduced-motion, конкретные transitions для каждого state change.
- Все 5 ADR-ов следуют шаблону `docs/adr/_template.md` (если нет — создать).

### Acceptance criteria

- [ ] Все 11 файлов существуют, прошли `markdownlint`.
- [ ] `docs/compliance/A11Y_CONTRAST.md` auto-generated и проверен `tools/design/check-contrast.ts` на 100% обязательных пар — нет пропусков.
- [ ] 5 ADR имеют статус `Approved` и проходят `adr-lint`.
- [ ] В `docs/README.md` добавлена секция `brand/` и `compliance/` с ссылками.
- [ ] Создан `.cursor/rules/design-system.mdc` (или эквивалент в `CLAUDE.md`), ссылающийся на эти документы, чтобы будущие генерации не уходили в сторону.

### Testing

- Скрипт `tools/design/check-contrast.ts` — генерирует `docs/compliance/A11Y_CONTRAST.md` из токенов и валидирует обязательные пары на пороги WCAG 2.2 AA; drift артефакта блокирует CI.
- Markdown-lint + link-check (`lychee`) в CI.

### Risks

| Риск                                          | Mitigation                                                                                         |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| ADR-ы уходят в абстракцию без привязки к коду | Каждый ADR завершается секцией «Concrete impact» со списком файлов, которые будут созданы/изменены |
| Contrast matrix устаревает при смене токенов  | Генерировать из `designTokens.ts` автоматически, не руками                                         |

---

## Фаза 1.1 — Visual language

**Длительность:** 3 недели.
**Тезис:** у PolicyOS появляется собственный визуальный словарь — не один лого, а система знаков, встроенная в каждый artefact системы.

### Preconditions

- Фаза 1.0 завершена (`GLYPH_SPECIFICATION.md` существует).

### Scope

1. Atlas mark перечитан как Janus-gate (минимальная правка).
2. Отдельный `logo-janus.svg` как glyph-mark движка.
3. 10 семантических глифов в `public/atlas/glyphs/` + React-компонент.
4. EvidenceSigil (детерминированный генератор по хэшу).
5. ProvenanceStrip — новая основная компонента для eyebrow.
6. Типографический `)·(` как editorial-punctuation.

### Deliverables

**Ассеты:**

```text
frontend/runtime-dashboard/public/atlas/
├── logo-mark.svg                    — обновлённый (Janus-прочтение)
├── logo-mark-inverse.svg            — для dark background
├── logo-janus.svg                   — новый glyph-mark движка
├── favicon.svg                      — Janus-line на 16 px
└── glyphs/
    ├── intervention.svg             — ⊙
    ├── evidence.svg                 — ▲
    ├── provenance.svg               — ⟿
    ├── transport.svg                — ⇄
    ├── counterfactual.svg           — ⋌
    ├── identifiability.svg          — ≔
    ├── reproducibility.svg          — ⟳
    ├── governance-pass.svg          — ◫
    ├── blocker.svg                  — ⊘
    └── freshness.svg                — ◷
```

Все SVG: 24-px viewBox, stroke 1.25–1.5, `currentColor` как stroke, никаких fills кроме `none` (кроме центров-точек где явно нужно).

**React-компоненты:**

```text
frontend/runtime-dashboard/src/shared/brand/
├── AtlasBrand.tsx                   — существующий, без изменений API
├── AtlasBrand.test.tsx
├── JanusGlyph.tsx                   — новый
├── JanusGlyph.test.tsx
├── JanusGlyph.stories.tsx
├── Glyph.tsx                        — новый, универсальная обёртка
├── Glyph.test.tsx
├── Glyph.stories.tsx
├── glyph-vocabulary.ts              — map: domainTerm → glyphName
├── EvidenceSigil.tsx                — новый
├── EvidenceSigil.test.tsx
├── EvidenceSigil.stories.tsx
└── serif-punctuation.tsx            — компонент `<PolicyPropositionMark />`
```

**Компоненты в `shared/ui`:**

```text
frontend/runtime-dashboard/src/shared/ui/
├── ProvenanceStrip.tsx              — новая eyebrow-компонента
├── ProvenanceStrip.test.tsx
├── ProvenanceStrip.a11y.test.tsx
└── ProvenanceStrip.stories.tsx
```

**API компонентов:**

```tsx
<JanusGlyph
  size={16 | 24 | 32}
  variant="mark" | "line" | "serif-punctuation"
  intent="default" | "verified" | "blocked" | "pending"
  inverted={boolean}
/>

<Glyph
  name="intervention" | "evidence" | ... // 10 радикалов
  size={12 | 14 | 16 | 24}               // default 14
  intent="default" | "verified" | "blocked" | "pending"
  strokeStyle="solid" | "dashed" | "double"  // semantic: observed/hypothetical/proved
  diacritic?: "strict" | "assumed" | "scoped"  // только в TrustView, см. 2.6
/>

<EvidenceSigil
  bundleHash={string}                   // детерминирует форму
  frescProfile={FrescProfile}           // 5 уровней
  identifiability={number}              // 0..1, окраска периметра
  size={48 | 64 | 96}
/>

<ProvenanceStrip
  items={ProvenanceItem[]}              // array 3..8
  density="comfortable" | "compact"     // будущая интеграция с 1.4
/>

<PolicyPropositionMark>  {/* )·( */}
  SME support under martial law
</PolicyPropositionMark>
```

### Integration

- `features/evidence/components/EvidenceFabric.jsx` → заменить eyebrow на `<ProvenanceStrip />`.
- `features/runs/.../RunDetail.jsx` → то же.
- `features/dashboard/DecisionCard.tsx` → eyebrow + `<EvidenceSigil />` в правом углу.
- `features/landing/*` → показать Janus-mark в hero для publicity (если landing сохраняется).
- Storybook: новая категория `Brand/` с страницами `Atlas`, `Janus`, `Glyphs`, `Provenance Strip`, `Evidence Sigil`.

### Backend contract changes

Нет изменений в Wave 1 — `ProvenanceStrip` получает готовые данные клиентской композицией из уже существующих полей:

- `EvidenceFabricItem.fresh_at` → `freshness` глиф.
- `EvidenceFabricItem.governance_pass` → `governance-pass` или `blocker`.
- `EvidenceFabricItem.intervention_type` → `intervention`.
- `EvidenceFabricItem.evidence_strength ∈ {strong, weak}` → `evidence` + modifier.

Адаптер: `src/shared/brand/provenance-adapter.ts` преобразует `EvidenceFabricItem` → `ProvenanceItem[]`. Unit-tested.

### Acceptance criteria

- [ ] 10 SVG-глифов существуют, прошли `svgo` + визуальный review, зарендерены в Storybook на 12/14/16/24 px.
- [ ] `logo-janus.svg` в 16 px зафиксирован recognizability evidence sheet + visual regression baseline для favicon state.
- [ ] `ProvenanceStrip` заменил eyebrow в 3 местах без регрессий (visual regression test).
- [ ] `EvidenceSigil` детерминирован: `render(hash_A) === render(hash_A)` в snapshot-тесте, `render(hash_A) !== render(hash_B)` в 100/100 случаев.
- [ ] `glyph-vocabulary.ts` покрыт 100% канонического 29-терминного домена, unit-test проверяет соответствие.
- [ ] ESLint-правило `no-raw-emoji-in-jsx` работает (как замена попыткам вставить `⊙` напрямую).

### Testing

- Storybook + visual regression (Playwright + Percy или Chromatic).
- `.a11y.test.tsx` для `ProvenanceStrip` и `Glyph` (axe-core).
- Unit-test `EvidenceSigil` определённость: 1000 random bundles, уникальность ≥ 99.9%.
- `pnpm test:glyph-vocabulary` — скрипт, парсит `docs/brand/GLYPH_SPECIFICATION.md`, сравнивает с `glyph-vocabulary.ts`, падает при расхождении.

### Risks

| Риск                               | Mitigation                                                                                 |
| ---------------------------------- | ------------------------------------------------------------------------------------------ |
| Глифы засоряют интерфейс           | `glyph-vocabulary.ts` — whitelist; PR добавляющий глиф в новое место требует design-review |
| `EvidenceSigil` даёт коллизии хэша | 48-bit entropy минимум; periodic collision audit                                           |

### Effort

- SVG-ассеты: 1 неделя (с итерациями).
- React-компоненты + тесты: 1.5 недели.
- Интеграция в 3 feature: 0.5 недели.

---

## Фаза 1.2 — Uncertainty visualization (G1)

**Длительность:** 3 недели.
**Тезис:** неопределённость — first-class объект в PolicyOS, и визуальный язык должен это выражать.

### Preconditions

- Фаза 1.1 завершена (глифы доступны).
- Фаза 1.0 завершена (`UNCERTAINTY_LANGUAGE.md` существует).

### Scope

Семь паттернов визуализации неопределённости, расширение существующих chart-компонентов, правила окраски, pattern-fills, правила анимации.

**Существующие компоненты для рефакторинга** (не пересоздаём с нуля):

- `shared/charts/ConfidenceDial.tsx`
- `shared/charts/ConfidenceGauge.tsx`
- `shared/charts/ForestPlot.tsx`
- `shared/charts/GradedErrorBar.tsx`
- `shared/charts/UncertaintyDisplay.tsx`

**Новые компоненты:**

- `UncertaintyBand.tsx` — generic wrapper для линейных графиков с confidence bands.
- `FanChart.tsx` — прогнозные распределения с квантилями 10/25/50/75/90.
- `QuantileDotplot.tsx` — реализация Hullman et al.
- `HypotheticalOutcomePlot.tsx` — анимированные sample realisations (HOPs), с reduced-motion fallback на static fan chart.
- `UncertaintyPatterns.tsx` — SVG-паттерны для identified / estimated / assumed регионов.
- `DisputedMarker.tsx` — глиф `⋌` c `--ember`, hover показывает кто и почему disputed.

### Deliverables

```text
frontend/runtime-dashboard/src/shared/charts/
├── UncertaintyBand.tsx              — new
├── UncertaintyBand.test.tsx
├── UncertaintyBand.stories.tsx
├── FanChart.tsx                     — new
├── FanChart.test.tsx
├── FanChart.stories.tsx
├── QuantileDotplot.tsx              — new
├── QuantileDotplot.test.tsx
├── QuantileDotplot.stories.tsx
├── HypotheticalOutcomePlot.tsx      — new
├── HypotheticalOutcomePlot.test.tsx
├── HypotheticalOutcomePlot.stories.tsx
├── patterns/
│   ├── UncertaintyPatterns.tsx      — SVG <pattern> defs (identified/estimated/assumed)
│   ├── UncertaintyPatterns.test.tsx
│   └── index.ts
├── DisputedMarker.tsx               — new
├── DisputedMarker.test.tsx
├── uncertainty-tokens.ts            — новые semantic tokens (cross-ref designTokens)
└── uncertainty-tokens.test.ts
```

**Tokens, добавляемые в `designTokens.ts`:**

```ts
export const uncertaintyTokens = {
  pointEstimate: "var(--ink)",
  confidenceInterval: "color-mix(in oklch, var(--slate), transparent 65%)",
  counterfactualInterval: "color-mix(in oklch, var(--slate), transparent 75%)", // dashed
  disputed: "var(--ember)",
  identified: { fill: "solid", pattern: "none" },
  estimated: { fill: "var(--slate)", pattern: "diagonal-lines" },
  assumed: { fill: "transparent", pattern: "dots" },
} as const;
```

### Chart refactoring tasks

| Component            | Change                                                              |         |             |                                   |
| -------------------- | ------------------------------------------------------------------- | ------- | ----------- | --------------------------------- |
| `ConfidenceDial`     | Использует `uncertaintyTokens`; добавляет prop `disputed?: boolean` |         |             |                                   |
| `ConfidenceGauge`    | То же + pattern-fill для estimated regions                          |         |             |                                   |
| `ForestPlot`         | Confidence intervals теперь gradient-filled (была solid line)       |         |             |                                   |
| `GradedErrorBar`     | Использует `uncertaintyTokens.estimated.pattern`                    |         |             |                                   |
| `UncertaintyDisplay` | Становится dispatcher: принимает тип (`band` \                      | `fan` \ | `dotplot` \ | `hops`), рендерит соответствующий |

### API

```tsx
<UncertaintyBand
  data={SeriesPoint[]}
  lower={0.1}       // quantile
  upper={0.9}
  counterfactual?={SeriesPoint[]}
  disputed?={Disputes}
/>

<FanChart
  quantiles={[0.1, 0.25, 0.5, 0.75, 0.9]}
  data={QuantileSeries[]}
  asOf?={ISO8601}   // подготовка к B1
/>

<QuantileDotplot
  samples={number[]}
  bins={20}
  orientation="horizontal" | "vertical"
/>

<HypotheticalOutcomePlot
  samples={SampleRealization[]}
  framesPerSecond={2}  // slow Hullman default
  reducedMotionFallback="fan-chart" | "quantile-dotplot"
/>
```

### Backend contract changes

Новое поле на metric-ответах (все endpoints возвращающие scalar):

```jsonc
// Было:
{ "effect_size": 0.23 }

// Стало:
{
  "effect_size": {
    "point": 0.23,
    "ci_80": [0.15, 0.31],
    "ci_95": [0.09, 0.37],
    "quantiles": { "p10": 0.12, "p50": 0.23, "p90": 0.34 },
    "identifiability": "identified" | "estimated" | "assumed",
    "disputed": boolean | null,
    "method": "bootstrap" | "analytic" | "bayesian-posterior"
  }
}
```

- Additive изменение: старое поле остаётся как alias 2 релиза.
- OpenAPI schema обновляется, типы регенерируются через `npx openapi-typescript`.
- Backend задача для policy-engine — отдельный ticket `policy-engine#uncertainty-contract`.

### Acceptance criteria

- [ ] Все 7 паттернов задокументированы в `UNCERTAINTY_LANGUAGE.md` с живыми Storybook-ссылками.
- [ ] Существующие chart-компоненты рефакторнуты без регрессий (visual regression).
- [ ] HOPs имеет reduced-motion fallback (автоматически переключается при `prefers-reduced-motion: reduce`).
- [ ] `uncertainty-tokens.ts` покрыт 100% в unit-тестах.
- [ ] 3 реальных Run Detail страницы используют `UncertaintyBand` вместо плоских чисел.
- [ ] Pattern-fills различимы для deuteranope / protanope / tritanope (deterministic in-repo simulation in Storybook).

### Testing

- Visual regression в Storybook (3 themes × 3 densities × 3 deterministic color-blind simulations).
- Unit: quantile correctness, reduced-motion fallback.
- Integration: e2e Playwright сценарий «открыл Run Detail → увидел fan chart → переключил режим reduced-motion → увидел static fan».

### Risks

| Риск                                      | Mitigation                                                                    |
| ----------------------------------------- | ----------------------------------------------------------------------------- |
| Backend не готов расширить контракт       | Clientsidе имеет fallback adapter: `legacy_number → { point: legacy_number }` |
| HOPs раздражает — слишком быстро/медленно | Hullman default 2.5 fps, user preference в Settings                           |
| Pattern-fills «шумные»                    | Opacity 0.18 по умолчанию; только внутри CI-band, не на основной линии        |

### Effort

- 3 новых компонента: 1 неделя.
- Pattern-fills + tokens: 2 дня.
- Рефакторинг 5 существующих: 1 неделя.
- Backend coordination + types regen: 3 дня.
- Тесты + docs: 3 дня.

---

## Фаза 1.3 — Accessibility WCAG 2.2 AA+ (G2)

**Длительность:** 2 недели.
**Тезис:** без формализованной accessibility инфраструктуры закрыт рынок ЕС и украинского госсектора; это процурментный блокер, не косметика.

### Preconditions

- Фаза 1.0 завершена (contrast matrix готов).
- Фазы 1.1 и 1.2 завершены (все новые компоненты должны пройти a11y-ворота).

### Scope

- Contrast sweep + automated enforcement.
- Pattern-fills для колор-блайнд dispatch (gold vs ember, teal vs slate).
- `prefers-reduced-motion` сквозной аудит.
- `prefers-contrast: more` — high-contrast variant глифов, provenance strip, charts.
- Focus-order контракты для новых компонентов.
- Screen-reader announcements infrastructure.
- VPAT публикация.
- Keyboard-only e2e suite.

### Deliverables

```text
frontend/runtime-dashboard/src/shared/a11y/
├── ContrastEnforcer.tsx              — dev-only overlay, показывает warnings
├── HighContrastProvider.tsx          — media query → [data-contrast="more"]
├── ReducedMotionProvider.tsx         — существующий, расширить API
├── LiveAnnouncer.tsx                 — существующий, централизовать вызовы
├── useFocusTrap.ts
├── useRovingTabindex.ts
└── index.ts

frontend/runtime-dashboard/src/test/a11y/
├── keyboard-journeys.spec.ts         — Playwright e2e
├── screen-reader-snapshots.spec.ts
└── color-blind-simulation.spec.ts    — deterministic simulation + axe

policy-engine/docs/compliance/
├── VPAT.md                           — full document
├── A11Y_CONTRAST.md                  — auto-generated from tokens
└── A11Y_AUDIT_2026Q2.md              — external audit report (scheduled)

tools/design/
├── check-contrast.ts                 — pre-commit hook
├── check-reduced-motion.ts           — grep all transitions, flag non-respecting
└── check-color-blind.ts              — axe + deterministic Coblis-equivalent simulation
```

**CSS additions** (в `styles.css` или эквиваленте):

```css
@media (prefers-contrast: more) {
  :root {
    --ink: #000000;
    --surface: #ffffff;
    /* all borders +50% opacity */
  }
  .glyph {
    stroke-width: 2;
  }
  .provenance-strip .glyph + .glyph {
    margin-inline-start: 0.75ch;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
  .hops {
    display: none;
  }
  .hops + .hops-static-fallback {
    display: block;
  }
}
```

### Backend contract changes

Нет (a11y — чисто client-side).

### Acceptance criteria

- [ ] WCAG 2.2 AA автоматизированный аудит (`axe-core`) — 0 violations на всех маршрутах.
- [ ] Manual audit по WCAG 2.2 AA checklist — 0 P0, ≤ 3 P1.
- [ ] VPAT.md опубликован, signed, версия закоммичена.
- [ ] Все 70+ компонентов в `shared/ui/` имеют `.a11y.test.tsx`.
- [ ] Keyboard-only journey: «старт → открыть run → скачать decision packet» — проходится без мыши за ≤ 20 tab-stop'ов.
- [ ] Deterministic color-blind simulation — все сигнальные различения остаются читаемыми в deuteranope/protanope/tritanope.
- [ ] Pre-commit hook `check-contrast` работает, падает на PR с плохими парами.

### Testing

- CI: axe-core на Storybook + 5 ключевых маршрутов.
- Weekly: full WCAG 2.2 AA automated report → dashboard.
- Quarterly: external audit (бюджет зарезервировать).

### Risks

| Риск                                                     | Mitigation                                                                |
| -------------------------------------------------------- | ------------------------------------------------------------------------- |
| Contrast enforcement ломает кастомные визуальные решения | Opt-out через `data-a11y-exempt` c обязательным комментарием-обоснованием |
| VPAT устаревает между релизами                           | Auto-regenerate из тестов + manual review quarterly                       |

### Effort

- Pattern-fills + tokens: 3 дня.
- ReducedMotion audit: 3 дня.
- VPAT: 2 дня.
- Tests + CI integration: 1 неделя.

---

## Фаза 1.4 — Dark theme v2 + density modes (G3)

**Длительность:** 2 недели.
**Тезис:** graphite rail — это не dark mode. Нужен полноценный тёмный режим с переосмысленной семантикой стекла, плюс 3 density-модели для аналитических сессий.

### Preconditions

- Фаза 1.0 (tokens inventory).
- Фаза 1.1 (для тестирования глифов в тёмной теме).
- Фаза 1.2 (charts должны адаптироваться).
- Фаза 1.3 (оба режима должны соответствовать WCAG).

### Scope

- Полноценная dark theme: rim-light инвертируется осмысленно (не просто negative), glass-panels переосмыслены для тёмного фона.
- Density modes: comfortable (default), compact (×0.75), condensed (×0.5).
- Toggle UI в Settings + Command Palette.
- Storybook покрытие всех компонентов в 3 темах × 3 плотностях.

### Deliverables

```text
frontend/runtime-dashboard/src/styles/
├── theme-light.css                   — extract from globals
├── theme-dark.css                    — new, полноценный
├── theme-high-contrast.css           — forwards 1.3
├── density-comfortable.css
├── density-compact.css
└── density-condensed.css

frontend/runtime-dashboard/src/app/providers/
├── ThemeProvider.tsx                 — существующий, расширить
├── DensityProvider.tsx               — new
└── DensityProvider.test.tsx

frontend/runtime-dashboard/src/features/platform/settings/
├── ThemeToggle.tsx
├── DensityToggle.tsx
└── AppearanceSection.tsx             — объединяет оба
```

**Токены:**

```ts
// designTokens.ts additions
export const densityScale = {
  comfortable: { space: 1.0, fontStep: 0, rowHeight: 1.0 },
  compact: { space: 0.75, fontStep: -1, rowHeight: 0.85 },
  condensed: { space: 0.5, fontStep: -2, rowHeight: 0.7 },
} as const;
```

**CSS custom properties:**

```css
:root[data-density="compact"] {
  --space-scale: 0.75;
  --font-scale-step: -1;
  --row-height-scale: 0.85;
}
/* все spacing-tokens рассчитываются относительно --space-scale */
```

**Dark theme specifics:**

- Rim-light (inset top-border) — в светлой теме светлый штрих; в тёмной — еле заметный warm-ink штрих, создающий обратный «pressed» эффект.
- Glass-panels: в светлой теме — белый с 0.85 opacity; в тёмной — warm-graphite с 0.92 opacity, noise-texture сохраняется.
- Teal/ember/gold остаются теми же hex'ами, но имеют tuned `color-mix` алиасы для тёмного фона чтобы сохранить контраст.
- Все chart-линии — `currentColor` чтобы автоматически адаптироваться.

### Command Palette actions

- `Cmd+Shift+L` / `Theme: toggle light/dark`.
- `Cmd+Shift+D` / `Density: cycle comfortable/compact/condensed`.

### Acceptance criteria

- [ ] Dark theme проходит WCAG 2.2 AA на всех маршрутах.
- [ ] Condensed density: на экране 40+ scenarios без ощущения каши (manual review от power-user).
- [ ] Storybook: 100% компонентов задокументированы в 3×3 матрице.
- [ ] Visual regression — 0 unexpected diffs в светлой теме; дефолтные snapshots для тёмной и compact — подписаны.
- [ ] Preference persisted в `localStorage` + synced в `workspaces.ts`.
- [ ] Прозрачная деградация: если user overrides `color-scheme`, система respects.

### Backend contract changes

Нет.

### Risks

| Риск                                                       | Mitigation                                                                          |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Dark theme требует пересчёта rim-light во всех компонентах | CSS custom property `--rim-light-color` — один источник правды                      |
| Condensed mode ломает table layouts                        | Явные min-width'ы в DataTable + horizontal scroll                                   |
| Двойные CI-прогоны × 3 density удорожают testing           | Выборочно: только критические смоки в compact/condensed, full suite — в comfortable |

### Effort

- Dark theme v2: 1 неделя.
- Density modes: 3 дня.
- Storybook coverage: 2 дня.
- Toggle UI + persistence: 2 дня.

---

## Фаза 1.5 — Prose system для decision packets (G4)

**Длительность:** 2 недели.
**Тезис:** PolicyOS производит документы на 5–40 страниц. Дашборд-оптимизированная типографика не справляется с длинной прозой — нужен отдельный reading view уровня Stripe Press / Observable notebook.

### Preconditions

- Фаза 1.1 (глифы для table of contents).
- Фаза 1.4 (reading view должен поддерживать light/dark).

### Scope

- Monograph-like layout (отдельный `MonographLayout`) без dashboard-хрома.
- Оптимальная ширина строки 60–72 ch.
- Типографика: цитаты (Instrument Serif), сноски, списки определений, margin notes.
- Оглавление с глифами-маркерами для каждой секции.
- Toggle «Reading view» в Decision Workspace.
- Print stylesheet.

### Deliverables

```text
frontend/runtime-dashboard/src/features/artifacts/reading-view/
├── MonographLayout.tsx
├── MonographLayout.test.tsx
├── MonographLayout.stories.tsx
├── MarginNotes.tsx
├── MarginNotes.test.tsx
├── Footnote.tsx
├── DefinitionList.tsx
├── PullQuote.tsx
├── TableOfContentsGlyphed.tsx
├── ReadingViewToggle.tsx
├── reading-view-tokens.ts
├── hooks/
│   ├── useReadingProgress.ts
│   └── useMarginNoteAnchors.ts
└── prose.css

frontend/runtime-dashboard/src/styles/
└── print.css                         — dedicated print stylesheet
```

**Типографические правила:**

```css
.prose {
  max-width: 68ch;
  font-family: "Manrope", system-ui;
  font-size: 17px;
  line-height: 1.65;
  color: var(--ink);
}
.prose > p + p {
  margin-block-start: 1em;
  text-indent: 0;
}
.prose blockquote {
  font-family: "Instrument Serif";
  font-style: italic;
  border-inline-start: 2px solid var(--gold);
  padding-inline-start: 1.5ch;
  color: color-mix(in oklch, var(--ink), transparent 15%);
}
.prose .definition-term {
  font-variant: small-caps;
  letter-spacing: 0.05em;
}
.prose .footnote-ref {
  font-feature-settings: "sups";
  color: var(--teal);
}
.prose .margin-note {
  position: absolute;
  inset-inline-start: calc(100% + 2ch);
  inline-size: 18ch;
  font-size: 13px;
  color: var(--slate);
  font-family: "IBM Plex Mono";
}
```

**Print CSS:**

```css
@page {
  margin: 2.5cm 2cm;
  size: A4;
}
@media print {
  nav,
  aside.dashboard-shell,
  .reading-view-toggle {
    display: none;
  }
  .prose {
    max-width: none;
  }
  h1,
  h2,
  h3 {
    break-after: avoid;
  }
  .fan-chart,
  .uncertainty-band {
    break-inside: avoid;
  }
  .provenance-strip::after {
    content: " [" attr(data-glyph-summary) "]";
  }
}
```

### Integration

- Decision Workspace получает toggle (floating top-right button или `r` keyboard shortcut).
- В reading view остаётся sidebar с оглавлением + Janus-medallion вверху.
- Provenance strip сохраняется под каждой major section'ой.

### Acceptance criteria

- [ ] Reading view работает на любом decision packet длиной от 1 до 40 страниц.
- [ ] Print: decision packet печатается на A4 без визуальных артефактов, pagination корректная.
- [ ] Table of contents автоматически собирает глифы из семантики секций.
- [ ] Margin notes не ломаются на mobile (degrade to inline footnotes).
- [ ] Reading view проходит WCAG 2.2 AA.

### Backend contract changes

- Decision packet API возвращает поле `section_type: "problem" | "intervention" | "evidence" | "policy" | "governance" | ...` — чтобы TOC мог назначить глиф.
- Additive, backward compatible.

### Risks

| Риск                                              | Mitigation                                               |
| ------------------------------------------------- | -------------------------------------------------------- |
| Margin notes не помещаются на узких экранах       | Responsive: < 1400px → inline footnote; > 1400 → margin  |
| Print не даёт pixel-perfect результатов в Firefox | Primary: Chrome headless; Firefox — graceful degradation |

### Effort

- Layout + tokens: 3 дня.
- TOC + margin notes: 3 дня.
- Print stylesheet: 2 дня.
- Integration + tests: 4 дня.

---

## Фаза 1.6 — AI-authorship registry (G5)

**Длительность:** 2 недели.
**Тезис:** в 2026 году пользователь обязан мгновенно отличить текст закона от операторского комментария от AI-generated narrative. Это визуальное различение — определяющий SOTA-признак.

### Preconditions

- Фаза 1.1 (нужны глифы `⊙`, `≔`, `⋌`).
- Фаза 1.5 (для интеграции в prose system).

### Scope

Пять визуальных регистров авторства, обязательная обёртка для всех текстовых блоков, toggle «Highlight authorship» для аудита, backend contract для author metadata.

### Deliverables

```text
frontend/runtime-dashboard/src/shared/ui/authored-text/
├── AuthoredText.tsx
├── AuthoredText.test.tsx
├── AuthoredText.a11y.test.tsx
├── AuthoredText.stories.tsx
├── AuthorshipProvider.tsx            — toggle highlight mode
├── AuthorBadge.tsx                   — inline mini-label
├── author-registry.ts                — типы и константы
└── index.ts
```

**Регистры:**

| Регистр      | Источник                   | Визуал                                                       | Screen reader                |
| ------------ | -------------------------- | ------------------------------------------------------------ | ---------------------------- |
| `citation`   | Цитата из закона/источника | `Instrument Serif italic`, тонкий `--gold` left-border (2px) | «Quoted text from {source}»  |
| `human`      | Написал оператор-человек   | `Manrope 400`, без маркера                                   | (default)                    |
| `drafter`    | AI-агент Drafter           | `--teal` left-border (1px), глиф `⊙` в начале параграфа      | «AI-generated by Drafter»    |
| `formalizer` | AI-агент Formalizer        | `--slate` left-border, глиф `≔`                              | «AI-generated by Formalizer» |
| `critic`     | AI-агент Critic            | `--ember` left-border, глиф `⋌`                              | «AI review by Critic»        |

### API

```tsx
<AuthoredText
  author="drafter" | "formalizer" | "critic" | "human" | "citation"
  sourceRef?={string}  // для citation: ссылка на закон/источник
  timestamp?={ISO8601}
  confidence?={number}  // 0..1, показывается только в trust-view (2.6)
>
  {children}
</AuthoredText>

<AuthorshipProvider highlightMode="off" | "subtle" | "prominent">
  {/* off — только визуально; subtle (default) — with borders and glyphs;
      prominent — full sidebar with author timeline */}
</AuthorshipProvider>
```

### Backend contract changes

```jsonc
// Narrative blocks теперь возвращаются как:
{
  "blocks": [
    {
      "id": "block_123",
      "content": "The policy requires ...",
      "author": "drafter",
      "author_agent_version": "drafter@1.4.2",
      "sources": [{ "kind": "evidence_bundle", "ref": "eb_abc" }],
      "timestamp": "2026-04-22T...",
      "confidence": 0.82,
      "reviewed_by_human": false,
    },
  ],
}
```

- Additive изменение к `DecisionPacket`, `NarrativeRationale`, `EvidenceSummary` endpoints.
- Миграция: без `author` → default `"human"`.

### Integration

- Decision Workspace narrative — все блоки через `AuthoredText`.
- Reading view (1.5) — то же.
- Chat / Clerk mode — каждое сообщение агента помечено.
- Evidence fabric — citations из источников через `author="citation"`.

### Acceptance criteria

- [ ] 100% текстовых блоков в Decision Workspace помечены авторством (automated check: любой `<p>` внутри `article` без `<AuthoredText>` даёт ESLint warning).
- [ ] Toggle «Highlight authorship» работает на всех 3 уровнях.
- [ ] Screen reader корректно объявляет автора перед каждым блоком (VoiceOver + NVDA test).
- [ ] Citation links кликабельны, ведут к evidence bundle.
- [ ] Prominent режим добавляет authorship timeline на правой стороне (кто когда что написал).

### Testing

- Storybook: каждый регистр на 5 примерах.
- E2E: «открыть packet → включить prominent → увидеть timeline → кликнуть citation → попасть на evidence».
- Unit: все 5 регистров корректно рендерятся для screen readers.

### Risks

| Риск                                       | Mitigation                                                |
| ------------------------------------------ | --------------------------------------------------------- |
| Слишком «шумный» UI с 4 разными border'ами | Subtle mode по умолчанию, границы 1px, off в reading view |
| Backend не готов отдавать author           | Default `"human"`, адаптер на клиенте для legacy блоков   |
| Citation source broken                     | `sourceRef` optional, UI graceful degrade                 |

### Effort

- Компоненты + тесты: 1 неделя.
- Интеграция в 4 места: 3 дня.
- Backend coordination: 2 дня.

---

## Фаза 1.7 — i18n UA/RU typography (G6)

**Длительность:** 1.5 недели.
**Тезис:** PolicyOS работает в украинском бюрократическом контексте; без корректной плюрализации, «ёлочек», неразрывных пробелов и plex-cyrillic metrics система воспринимается как иностранный product.

### Preconditions

- Фаза 1.0 (`TYPOGRAPHY_UA_RU.md` готов).

### Scope

- Плюрализация через ICU MessageFormat (`one/few/many/other`).
- Кириллическая типографика: «ёлочки», неразрывные пробелы после коротких предлогов.
- Plex Mono cyrillic metrics fix.
- Форматы валют (₴/€/$), дат, чисел.
- ESLint-правила для enforcement.

### Deliverables

```text
frontend/runtime-dashboard/src/i18n/
├── LocaleProvider.tsx                — существующий, расширить
├── locales/
│   ├── en.json
│   ├── uk.json                       — переразметить под ICU
│   └── ru.json
├── typography/
│   ├── quoteMarks.ts                 — «ёлочки» по locale
│   ├── nonBreakingSpaces.ts          — автоматическая вставка
│   ├── plexCyrillicFix.css
│   └── typography.test.ts
├── formatters/
│   ├── currency.ts                   — ₴, €, $
│   ├── date.ts                       — укр длинный, ISO mono
│   ├── number.ts                     — разделители тысяч по locale
│   └── formatters.test.ts
└── icu-messages.ts                   — helpers for plural

frontend/runtime-dashboard/.eslintrc.js

  - no-hardcoded-strings                — новое правило
  - require-non-breaking-space-for-short-prepositions
```

**ICU example:**

```jsonc
// uk.json
{
  "scenarios.count": "{count, plural, =0 {Немає сценаріїв} one {# сценарій} few {# сценарії} many {# сценаріїв} other {# сценарію}}",
  "policy.applied": "Політику <b>{name}</b> застосовано о {time, time, short}",
}
```

**CSS fix:**

```css
/* Plex Mono cyrillic metrics компенсация */
:lang(uk),
:lang(ru) {
  --plex-mono-cyrillic-offset: 0.02em;
}
.mono:is(:lang(uk), :lang(ru)) {
  letter-spacing: var(--plex-mono-cyrillic-offset);
}
```

**Non-breaking spaces enforcement:**

Auto-insert после: `в, у, з, і, й, та, на, до, від, за, під, над, про` (uk) и `в, у, о, к, с, и, а, но` (ru). Реализовать как ESLint autofix + runtime через `<Text>` wrapper.

### Backend contract changes

Нет — всё client-side.

### Acceptance criteria

- [ ] 100% строк в `en.json` / `uk.json` / `ru.json` используют ICU plural где применимо.
- [ ] Все валюты рендерятся через `formatCurrency`, даты через `formatDate`, числа через `formatNumber`.
- [ ] ESLint-правило `no-hardcoded-strings` пройдено (0 violations).
- [ ] Neбьющиеся пробелы автоматически вставляются в prose блоках (unit test покрывает 20 примеров).
- [ ] Визуальная разница в Plex Mono metrics между en и uk устранена (eyeball review).

### Testing

- Unit: все форматтеры на 30+ cases (edge: `0, 1, 2, 5, 11, 21, 101`).
- Visual regression: Storybook stories с uk locale включая кириллицу во всех типах mono-labels.

### Risks

| Риск                                           | Mitigation                                           |
| ---------------------------------------------- | ---------------------------------------------------- |
| Авто-вставка NBSP ломает существующие переводы | Opt-in per-string через конфиг; постепенная миграция |
| ICU plural усложняет разработку                | Краткий styleguide + ESLint-hint                     |

### Effort

- Форматтеры: 3 дня.
- ICU plural migration: 2 дня.
- Typography fixes: 2 дня.
- ESLint rules: 2 дня.

---

## Фаза 1.8 — Wave 1 closeout

**Длительность:** 1 неделя.
**Тезис:** интеграционный прогон всех Wave 1 фич, снятие feature-flags, релиз, ревью перед Wave 2.

### Scope

- Snapshot ревью: все anchor artifacts (§7) достижимы.
- Feature flags Wave 1 выставлены в `"all_on"` в staging.
- 2-недельное наблюдение (идёт параллельно началу Wave 2 Phase 2.0).
- Release notes / changelog.
- Design review с external consultant (если бюджет позволяет).
- `CHANGELOG-DESIGN.md` выделенный для дизайн-изменений.

### Deliverables

- `docs/plans/active/DESIGN_WAVE1_RELEASE_NOTES.md`.
- `CHANGELOG-DESIGN.md` update.
- Session recording (Figma или screencast) для onboarding команды.
- Архивный snapshot Storybook в `docs/brand/storybook-wave1-snapshot/`.

### Acceptance criteria

- [ ] Все anchor artifacts 1–4, 7–10 (§7) воспроизводятся на staging.
- [ ] Bug count from Wave 1 fixes: 0 P0, ≤ 2 P1, ≤ 5 P2 за 14 дней.
- [ ] VPAT document signed.
- [ ] Storybook published as immutable CI artifact/preview URL и зафиксирован в release notes для stakeholder review.

---

## Волна 2 — Best-in-class primitives

> Начинать только после gate (см. §3.1).

## Фаза 2.0 — Provenance law foundations

**Длительность:** 2 недели.
**Тезис:** Provenance law (B2) начинается не с hover-popover, а с закона данных:
в PolicyOS не должно быть naked decision numbers. Любое число, влияющее на
решение, должно приходить как `QuantityValue`: значение, единица, uncertainty,
temporal scope, lineage и verification status.

### Preconditions

- Wave 1 gate passed.
- Fabric lineage и time-travel не переписываются с нуля: использовать текущие
  `FabricLineageTracker`, `world_query` bitemporal semantics, snapshots/branches
  и OpenLineage/PROV exports как backend-ядро.

### Scope

- Canonical `QuantityValue` envelope для всех decision-bearing чисел.
- `LineageRef`, `TemporalRef`, `VerificationStatus`, `UnitRef` runtime contracts.
- Lineage API: single + batch lookup, compact summary + full graph.
- Coverage inventory: какие числовые поля уже traced / untraced / telemetry-only.
- ESLint-правило `policyos/quantity-must-be-wrapped` с классификацией чисел:
  `decision`, `telemetry`, `layout`, `debug`.
- `<Quantity>` skeleton принимает envelope целиком, не `value + lineageId`
  отдельными props.
- Migration strategy: phased warn → error по feature-slice, а не один PR на все
  числа.

### Deliverables

```text
policy-engine/docs/adr/ADR-043-provenance-law.md       — финализация
policy-engine/docs/brand/PROVENANCE_INTERACTION.md     — UX law: inline → popover → deep dive
policy-engine/docs/reference/runtime/quantity-values.md — API semantics + migration rules

policy-engine/src/polisyos/core/contracts/runtime.py
  — добавить QuantityValue, UnitRef, LineageRef, TemporalRef, VerificationStatus

policy-engine/src/polisyos/runtime/http/routes/lineage.py
  — GET /api/v1/lineage/{lineage_id}
  — POST /api/v1/lineage/batch

policy-engine/src/polisyos/runtime/http/services/lineage.py
  — adapter: FabricLineageTracker / artifact lineage → runtime lineage views

policy-engine/src/polisyos/runtime/http/routes/runs.py
  — GET /api/v1/runs/{run_id}/quantities (inventory/debug endpoint)

policy-engine/src/polisyos/fabric/provenance/lineage.py
  — only additive metadata if needed: verification, freshness, compact summary

frontend/runtime-dashboard/src/shared/ui/quantity/
├── Quantity.tsx                     — skeleton (full impl в 2.2), accepts QuantityValue
├── Quantity.test.tsx
├── Quantity.stories.tsx
├── quantity.types.ts
└── quantity-format.ts               — unit/precision/locale formatting

frontend/runtime-dashboard/eslint-rules/
├── quantity-must-be-wrapped.ts
└── quantity-must-be-wrapped.test.ts

tools/design/
├── migrate-numbers-to-quantity.ts    — codemod helper
└── report-quantity-coverage.ts       — traced/untraced/telemetry/layout inventory
```

### Backend contract

```jsonc
// Decision-bearing numeric fields become QuantityValue envelopes.
{
  "effect_size": {
    "point": 0.23,
    "unit": {
      "code": "1",
      "system": "ucum",
      "display": "ratio"
    },
    "metric_id": "employment_rate_delta",
    "lineage": {
      "id": "lin_abc123",
      "hash": "sha256:...",
      "status": "verified",
      "freshness": "current",
      "summary": {
        "source": "QES 2024 Q3",
        "method": "DoubleML v2.1",
        "agent": "Formalizer@1.4"
      }
    },
    "uncertainty": {
      "ci_95": [0.15, 0.31],
      "method": "bootstrap",
      "identifiability": "estimated",
      "disputed": false
    },
    "time": {
      "valid_at": "2026-04-15T12:00:00Z",
      "tx_at": "2026-04-16T09:20:00Z"
    }
  }
}
```

```http
GET /api/v1/lineage/{lineage_id} →
```

```jsonc
{
  "id": "lin_abc123",
  "status": "verified",
  "hash": "sha256:...",
  "freshness": "current",
  "compact_summary": [
    { "kind": "source", "label": "QES 2024 Q3" },
    { "kind": "transform", "label": "Winsorize 1-99%" },
    { "kind": "model", "label": "DoubleML v2.1" },
    { "kind": "result", "label": "effect_size" }
  ],
  "nodes": [
    { "id": "n1", "kind": "dataset", "label": "QES 2024 Q3", "timestamp": "..." }
  ],
  "edges": [],
  "exports": {
    "openlineage": "/api/v1/lineage/lin_abc123/export/openlineage",
    "prov": "/api/v1/lineage/lin_abc123/export/prov"
  }
}
```

### Quantity classification

| Class       | Examples                              | Rule                                                                 |
| ----------- | ------------------------------------- | -------------------------------------------------------------------- |
| `decision`  | effect size, budget, confidence, risk | Must be `QuantityValue`; UI must render through `<Quantity>`.        |
| `telemetry` | latency, cache hits, event counts     | May remain primitive but must be explicitly annotated as telemetry.  |
| `layout`    | pixel sizes, animation durations      | Excluded from provenance law.                                        |
| `debug`     | local mock values, Storybook fixtures | Allowed only in test/story files or explicit fixture modules.        |

### Research anchors

- W3C PROV-DM / PROV-O semantics for entities, activities, agents and relations.
- OpenLineage for external lineage interoperability.
- UCUM/QUDT-style unit discipline: machine unit code and human display are separate.
- Existing Fabric docs: `docs/reference/fabric/lineage.md` and
  `docs/reference/fabric/time-travel.md`.

### Acceptance criteria

- [ ] ADR-043 approved, merged.
- [ ] `QuantityValue` и related contracts специфицированы в Pydantic/OpenAPI,
      types сгенерированы.
- [ ] `GET /api/v1/lineage/{lineage_id}` и `POST /api/v1/lineage/batch`
      возвращают compact + full graph payloads.
- [ ] `GET /api/v1/runs/{run_id}/quantities` выдаёт coverage report:
      traced / untraced / telemetry / layout / debug.
- [ ] ESLint-правило работает в `warn` режиме и показывает class-aware warnings,
      а не одну плоскую массу нарушений.
- [ ] Codemod мигрирует ≥ 50% simple decision-number cases автоматически и не
      трогает layout/telemetry без explicit opt-in.
- [ ] `lineage_id: "untraced"` разрешён только как typed `LineageRef.status =
      "untraced"` с обязательным `reason_code` и tracking issue.

### Risks

| Риск                                               | Mitigation                                                                                          |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `lineage_id` превращается в декоративное поле      | Quantity envelope: значение, unit, uncertainty, time, lineage и status идут одним атомом.           |
| Backend не готов отдать lineage для всех чисел     | Typed `untraced` status + reason code + endpoint-level remediation ticket; visible coverage report. |
| 3000 warnings демотивируют                         | Class-aware inventory + phased rollout по feature-slice; сначала decision surfaces.                 |
| Unit/format drift между backend и frontend         | UCUM/QUDT-style `UnitRef`; display formatting централизовано в `quantity-format.ts`.                |
| Lineage graph слишком тяжёлый для hover            | Batch endpoint + compact summary в 2.0; full graph lazy-load only в 2.2.                            |

### Effort

- Runtime contracts + OpenAPI: 3 дня.
- Lineage routes + Fabric adapter: 4 дня.
- ESLint rule + codemod + coverage report: 4 дня.
- Quantity skeleton + docs: 2 дня.

---

## Фаза 2.1 — Time-as-primitive (B1)

**Длительность:** 4 недели.
**Тезис:** Time-as-primitive не должен быть простым `as_of`. PolicyOS должен
различать policy/world time (`valid_at`) и knowledge/record time (`tx_at`).
Оператор двигает один понятный scrubber, но система воспроизводит точный
bitemporal state: «что действовало тогда» и «что было известно тогда».

### Preconditions

- Фаза 2.0 завершена: `QuantityValue.time` и lineage endpoint готовы.
- Фаза 1.2 завершена: uncertainty charts умеют принимать temporal scope.
- Fabric `world_query` bitemporal semantics доступны как backend source of truth.

### Scope

- `TemporalScope` как canonical state: `validAt`, `txAt`, `branch`,
  `snapshotId`, `scenarioId`.
- `TemporalCursorProvider` как глобальный state + URL serializer.
- `TemporalScrubber` UI в Atlas shell header.
- `withTemporalCursor` HOC / hook для синхронизации графиков и quantities.
- Backend contract: `valid_at` + `tx_at` параметры на time-sensitive endpoints.
- Temporal capability endpoint: range, resolution, supported surfaces, gaps.
- React Query/cache discipline: temporal scope входит в every query key and ETag.
- Keyboard shortcuts + screen reader announcements.
- URL deep-linking времени, snapshot/branch context.

### Deliverables

```text
frontend/runtime-dashboard/src/app/providers/
├── TemporalCursorProvider.tsx
├── TemporalCursorProvider.test.tsx
├── temporal-scope.ts                — parse/serialize/compare TemporalScope
├── temporal-url.ts                  — ?t= shorthand + canonical params
└── useTemporalCursor.ts

frontend/runtime-dashboard/src/shared/ui/temporal/
├── TemporalScrubber.tsx              — UI в header
├── TemporalScrubber.test.tsx
├── TemporalScrubber.a11y.test.tsx
├── TemporalScrubber.stories.tsx
├── TemporalCursorMarker.tsx          — вертикальная линия для графиков
├── TemporalLegend.tsx                — observed vs simulated indicator
├── TemporalCapabilityBanner.tsx      — unsupported/gap states
├── useTemporalRange.ts
└── withTemporalCursor.tsx            — HOC

frontend/runtime-dashboard/src/api/
├── hooks/
│   ├── useTemporalQuery.ts           — wrapper React Query c TemporalScope
│   └── useTemporalRange.ts           — определение allowed range для run
└── queryKeys.ts                      — include TemporalScope in keys

policy-engine/src/polisyos/runtime/http/routes/
├── runs.py                           — valid_at / tx_at on run detail, timeline, lineage
└── temporal.py                       — GET /api/v1/temporal/capabilities

policy-engine/src/polisyos/runtime/http/services/
└── temporal.py                       — maps TemporalScope → Fabric world_query/snapshots

policy-engine/src/polisyos/fabric/world_query.py
└── no semantic rewrite; additive adapter tests for runtime endpoint behavior
```

### UI spec

- **Расположение:** горизонтальный scrubber под верхним rail'ом Atlas shell'а, height 32 px.
- **Основная ось:** `valid_at` (когда факт/политика действовали).
- **Вторичная ось:** `tx_at` (когда система знала запись) скрыта в обычном
  режиме, но видна в Trust View / advanced temporal mode.
- **Индикаторы:** тонкая timeline с маркерами событий (run starts, policy
  changes, late-arriving evidence, corrections); сплошная часть = observed,
  пунктирная = simulated/future; «сейчас» = вертикальная линия `--gold`.
- **Взаимодействие:**
  - drag → локальный scrub на `requestAnimationFrame`, network fetch только
    после debounce/commit;
  - `←/→` → ±1 day step;
  - `Shift+←/→` → ±1 week;
  - `Alt+←/→` → ±1 hour;
  - `PageUp/PageDown` → ±1 month;
  - `Home` → earliest; `End` → latest; `N` / `Now` → «сейчас».
- **Screen reader:** slider uses `aria-valuetext`; committed changes announce
  `"Policy time moved to April 15, 2026; knowledge as of April 16, 2026"`.
- **Reduced motion:** drag preview snaps to known event points; no continuous
  chart morphing.

### Backend contract

Canonical query params:

- `valid_at`: RFC 3339 timestamp, required for explicit time travel.
- `tx_at`: RFC 3339 timestamp, optional; defaults to latest known transaction.
- `branch`: optional retained branch name.
- `snapshot_id`: optional retained snapshot.
- `scenario_id`: optional future/counterfactual scenario, used fully in 2.4.

Compatibility shorthand:

- `?t=2026-04-15T12:00:00Z` maps to `valid_at` with latest `tx_at`.

Endpoints:

- `GET /api/v1/runs/{id}?valid_at=...&tx_at=...`
- `GET /api/v1/runs/{id}/timeline?valid_at=...&tx_at=...`
- `GET /api/v1/runs/{id}/lineage?valid_at=...&tx_at=...`
- `GET /api/v1/temporal/capabilities?run_id=...`

Поведение:

- Если `valid_at` в прошлом — возвращается world/policy state на этот valid-time.
- Если `tx_at` задан — возвращается только то, что система знала на этот
  transaction-time; late-arriving evidence после `tx_at` исключается.
- Если `valid_at`/`tx_at` вне допустимого range — 422 с `valid_range`,
  `tx_range`, `nearest_event_points`.
- Если endpoint ещё не поддерживает temporal scope — 200 с current behavior
  запрещён; должен быть 409/422 с typed `temporal_surface_unsupported`, чтобы
  UI мог показать honest gap.

Additive: без temporal params — текущее поведение. Индексы на `created_at`,
`updated_at`, `valid_from`, `valid_to`, `tx_time`, `valid_time` обязательны
(DBA task).

### URL deep-linking

- Human shorthand: `?t=2026-04-15T12:00:00Z`.
- Canonical advanced form:
  `?valid_at=2026-04-15T12:00:00Z&tx_at=2026-04-16T09:20:00Z&branch=main`.
- `<Link>` компоненты вне TemporalScope явно решают: preserve, reset, or inherit.
- Share URL must reproduce the same quantities, lineage summaries, uncertainty
  and selected branch/snapshot.

### Acceptance criteria

- [ ] Скрабинг на 60 fps в desktop Chrome; ≤ 30 fps acceptable на mobile.
- [ ] Drag updates local preview on animation frame; backend fetch happens on
      debounced commit ≤ 150 ms after stop.
- [ ] Every time-sensitive React Query key includes full `TemporalScope`.
- [ ] Все графики на Run Detail странице синхронно ре-рендерятся.
- [ ] Quantities, lineage summaries and uncertainty values reproduce the same
      state from a shared URL.
- [ ] `prefers-reduced-motion` → скрабинг заменяется на snap-to-point.
- [ ] Keyboard-only navigation соответствует WAI-ARIA slider pattern.
- [ ] Screen reader корректно объявляет при каждом изменении (throttled 500 ms).
- [ ] `GET /api/v1/temporal/capabilities` перечисляет supported/unsupported
      surfaces и usable range для реального run.
- [ ] Bitemporal test case: поздно пришедшая correction видна при позднем
      `tx_at` и не видна при раннем `tx_at`, при том же `valid_at`.

### Testing

- Unit: `TemporalCursorProvider` state transitions.
- Unit: `temporal-scope.ts` parse/serialize/compare; timezone normalization.
- E2E: «открыть run → скрабить → увидеть изменение CI/Quantity → копировать URL
  → open in incognito → увидеть тот же state».
- Backend: runtime endpoint test using Fabric bitemporal fixture from
  `tests/fabric/test_world_time_travel.py`.
- Performance: Chrome DevTools performance profile на 60 fps.
- A11y: keyboard-only journey пройдена axe + manual VoiceOver.

### Risks

| Риск                                                       | Mitigation                                                                                                          |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Команда упрощает bitemporal model до одного `as_of`        | Public API фиксирует `valid_at` + `tx_at`; `?t=` только shorthand.                                                  |
| Backend не справляется с temporal scope для всех endpoints | Capability endpoint + explicit unsupported state; rollout: run detail → timeline → lineage → evidence/decisions.    |
| DB без time-series индексов становится медленной           | DBA task: indices на valid/tx columns; slow-query audit; snapshot fallback for projection tables.                   |
| Timezone drift между UI и API                              | Internal UTC/RFC 3339; display через locale/timezone; URL never stores locale-formatted dates.                      |
| «Будущее» — сложная симуляция                              | В 2.1 only observed/present + scenario placeholder; future simulation fully in 2.4.                                 |

### Effort

- TemporalScope contracts + URL/query-key discipline: 4 дня.
- Provider + scrubber UI: 1 неделя.
- Backend temporal adapter + capability endpoint: 1 неделя.
- Run Detail/chart/Quantity integration: 1 неделя.
- Bitemporal tests + perf/a11y polish: 3 дня.

---

## Фаза 2.2 — Provenance-on-hover (B2)

**Длительность:** 3 недели.
**Тезис:** Provenance-on-hover — это не tooltip. Это проверяемая цепочка
объяснения: inline cue сообщает статус, popover отвечает «откуда это число?»,
deep-dive даёт полный graph, raw sources и export.

### Preconditions

- Фаза 2.0 завершена: `QuantityValue` envelope + lineage batch endpoint.
- Фаза 2.1 завершена: `TemporalScope` стабилен; lineage/quantity responses
  воспроизводятся для выбранного `valid_at`/`tx_at`.

### Scope

- Полная реализация `<Quantity>` как renderer одного `QuantityValue`.
- `<ProvenancePopover>` как interactive popover, не tooltip.
- `<ProvenanceDeepDiveDialog>` для full graph + raw source links + exports.
- `ProvenanceMiniGraph` с graph summarization: максимум 5–7 видимых узлов,
  aggregation по source/transform/model/agent/result.
- `useLineage` и `useLineageBatch` hooks с lazy load and cache.
- Миграция всех числовых значений в JSX через codemod + manual review.
- ESLint-правило переводится `warn → error` сначала для `decision` class.

### Deliverables

```text
frontend/runtime-dashboard/src/shared/ui/quantity/
├── Quantity.tsx                     — full implementation
├── Quantity.test.tsx
├── Quantity.a11y.test.tsx
├── Quantity.stories.tsx
├── ProvenancePopover.tsx
├── ProvenancePopover.test.tsx
├── ProvenancePopover.a11y.test.tsx
├── ProvenanceMiniGraph.tsx          — summarized graph, 5–7 visible nodes
├── ProvenanceMiniGraph.test.tsx
├── ProvenanceDeepDiveDialog.tsx
├── ProvenanceDeepDiveDialog.test.tsx
├── lineage-summary.ts               — source/transform/model/agent/result aggregation
├── useLineage.ts                    — React Query hook
├── useLineageBatch.ts               — batch prefetch for visible quantities
└── index.ts

frontend/runtime-dashboard/eslint-rules/
└── quantity-must-be-wrapped.ts      — decision class warn → error

policy-engine/src/polisyos/runtime/http/routes/lineage.py
└── add export routes if not shipped in 2.0:
    GET /api/v1/lineage/{lineage_id}/export/openlineage
    GET /api/v1/lineage/{lineage_id}/export/prov
```

### API

```tsx
<Quantity
  value={quantityValue}              // QuantityValue envelope from 2.0
  format?="decimal" | "percent" | "currency" | "scientific" | "compact"
  precision?={number}
  variant?="inline" | "table" | "hero" | "dense"
  provenanceMode?="auto" | "always" | "off"
  temporalScope?={TemporalScope}     // optional override; default from provider
/>
```

Важно: `<Quantity>` не принимает `value` и `lineageId` как отдельные props.
Иначе UI может случайно смешать число из одного response и lineage из другого.

### UX spec

- **Inline cue:** small provenance mark near the number:
  `verified`, `pending`, `disputed`, `stale`, `untraced`.
- **Hover/focus:** after 150 ms opens interactive popover. It must be hoverable,
  dismissible (`Esc`), persistent while focused, and never steal pointer drag
  from charts.
- **Popover content:** compact answer:
  source → transform → model/method → result, with freshness, verification,
  uncertainty and temporal scope.
- **Keyboard:** focus on Quantity announces value + unit + CI + provenance
  availability; `Enter` / `Space` opens popover; `Esc` closes; `D` opens
  deep-dive when popover is active.
- **Mini graph:** maximum 5–7 visible nodes; hidden nodes summarized as
  `+N transforms` / `+N sources`; full graph only in dialog.
- **Deep dive:** modal/dialog with full lineage, raw source links, export
  OpenLineage/PROV, downstream impact when available.
- **Untraced:** render with blocker glyph and reason; no silent fallback.
- **Batch performance:** visible quantities may batch-fetch compact summaries,
  but full graph is lazy-loaded on popover/deep-dive.

### Миграция

- `decision` class: ESLint `error` after codemod + manual review.
- `telemetry` class: warning allowed with explicit annotation.
- `layout` class: ignored.
- `debug` class: allowed only in stories/tests/fixtures.
- PR-check: невозможно merge нового decision number без `<Quantity>`.

### Acceptance criteria

- [ ] 100% decision-bearing числовых значений в UI обёрнуты в `<Quantity>`
      (ESLint enforces).
- [ ] Popover появляется за ≤ 200 ms от hover/focus start.
- [ ] Mini graph читается на 320 px ширину экрана.
- [ ] Screen reader описание: `"Effect size 0.23 ratio, 95 percent confidence
      interval 0.15 to 0.31, verified provenance available"`.
- [ ] Deep-dive dialog показывает full lineage, raw source links,
      OpenLineage/PROV exports.
- [ ] 3-click rule: от видимого числа до raw source/method/agent/timestamp за
      ≤ 3 intentional actions.
- [ ] WCAG hover/focus behavior: dismissible, hoverable, persistent.
- [ ] Performance: 100+ `<Quantity>` на странице без visible lag.
- [ ] Temporal correctness: popover lineage соответствует активному
      `TemporalScope`, не latest by accident.

### Backend contract

Основной контракт зафиксирован в 2.0. В 2.2 backend должен дополнительно
гарантировать:

- batch endpoint p95 ≤ 150 ms for 50 compact lineage refs;
- full graph lazy endpoint p95 ≤ 500 ms for typical run lineage;
- OpenLineage/PROV export routes return deterministic payloads;
- lineage response includes `temporal_scope` echo for cache correctness.

### Risks

| Риск                                          | Mitigation                                                                                           |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Perf regression при 100+ Quantity на странице | Compact batch summaries; full graph lazy-load; virtualized tables do not pre-render popovers.        |
| Mini graph превращается в нечитаемый hairball | Mandatory summarization; 5–7 visible nodes; aggregation by source/transform/model/agent/result.      |
| Popover нарушает WCAG hover/focus             | Use interactive popover/dialog pattern, not tooltip; `Esc`, hoverable surface, focus management.     |
| `untraced` режет UX                           | Make it visible as governance debt; track endpoint-level remediation; never pretend verified.        |
| Temporal mismatch                             | Every lineage fetch includes `TemporalScope`; response echoes scope; query key includes scope.       |

### Effort

- `Quantity` full renderer + formatting: 4 дня.
- Popover + mini graph + summarization: 1 неделя.
- Deep-dive dialog + exports integration: 4 дня.
- Migration + ESLint error rollout: 1 неделя.
- A11y/perf/temporal correctness tests: 3 дня.

---

## Фаза 2.3 — Policy diff (B3)

**Длительность:** 3 недели.
**Тезис:** Policy diff не должен быть word-diff'ом и не должен быть набором
случайных "before/after" карточек. Best-in-class версия сравнивает две policy
через общий `ComparisonFrame`: что изменилось в эффекте, для кого, с какой
уверенностью, при каких assumptions, и почему этому можно доверять.

### Preconditions

- Фаза 2.1 завершена: обе стороны diff используют один `TemporalScope`
  (`valid_at`, `tx_at`, branch/snapshot/scenario).
- Фаза 2.2 завершена: все decision quantities имеют lineage и provenance
  доступен из diff-view без latest-by-accident.
- Фаза 1.2 завершена: uncertainty charts умеют визуализировать CI/distribution
  и не сводят diff к одному point estimate.

### Product law

PolicyOS сравнивает только сопоставимое. Перед diff всегда выполняется
`comparability_check`: одинаковый problem frame, совместимые units, overlapping
population, comparable temporal scope, compatible model family или явное
предупреждение, почему сравнение является exploratory.

### Scope

- Canonical `ComparisonFrame`: `run_a`, `run_b`, `metric_set`, `population`,
  `unit_policy`, `temporal_scope`, `scenario_scope`, `assumption_set`.
- `CompareRunResponse`: all headline deltas are `QuantityValue` envelopes, not
  naked numbers.
- `DeltaQuantity`: `a`, `b`, `delta_absolute`, `delta_relative`,
  `delta_distribution`, `significance`, `dominance`, `lineage_delta`.
- Pre-flight comparability report: `compatible`, `warning`, `blocked`.
- Split-pane Run Detail with synchronized scroll and synchronized temporal
  cursor.
- Causal delta strip: ranked deltas by magnitude, uncertainty and decision
  salience.
- Delta widgets: distribution, budget, governance, identifiability, provenance,
  assumptions and subgroup heterogeneity.
- Command palette action: compare current run with previous, selected, baseline
  or recommended comparator.
- Deep-link URL `/compare/:runA/:runB` reproduces temporal scope, scenario scope,
  selected metrics and visible panels.

### Deliverables

```text
frontend/runtime-dashboard/src/features/runs/compare/
├── PolicyDiffView.tsx
├── PolicyDiffView.test.tsx
├── PolicyDiffView.a11y.test.tsx
├── PolicyDiffView.stories.tsx
├── PolicyDiffLayout.tsx              — split-pane + responsive single-column
├── ComparisonFramePanel.tsx          — comparability + scope summary
├── CausalDeltaStrip.tsx              — central ranked delta rail
├── CompareCommandDialog.tsx          — choose baseline / previous / selected run
├── delta-widgets/
│   ├── OutcomeDelta.tsx              — point + CI + practical significance
│   ├── DistributionDelta.tsx         — quantile/histogram/wasserstein-style delta
│   ├── SubgroupDeltaMatrix.tsx       — who gains/loses
│   ├── IdentifiabilityTrajectory.tsx
│   ├── GovernanceRadarDiff.tsx
│   ├── BudgetFlowDiff.tsx
│   ├── ProvenanceDrift.tsx           — source/model/agent/verification drift
│   └── AssumptionDiff.tsx
├── compare-types.ts
├── compare-math.ts                   — normalize units, CI overlap, effect labels
├── useCompareRuns.ts
└── route.tsx                         — /compare/:runA/:runB

frontend/runtime-dashboard/src/api/
├── hooks/useCompareRuns.ts
└── queryKeys.ts                      — compare keys include TemporalScope + scenarios

policy-engine/src/polisyos/core/contracts/runtime.py
  — ComparisonFrame, CompareRunResponse, DeltaQuantity, ComparabilityReport

policy-engine/src/polisyos/runtime/http/routes/runs.py
  — GET /api/v1/runs/compare
  — GET /api/v1/runs/{run_id}/compare-candidates

policy-engine/src/polisyos/runtime/http/services/compare.py
  — maps run metrics/lineage/uncertainty into normalized diff payloads

policy-engine/docs/reference/runtime/policy-diff.md
```

### UX spec

- **Layout:** desktop uses two equal run panes with a central delta rail; tablet
  switches to stacked panes with sticky delta rail; mobile defaults to "changed
  metrics first" cards and keeps raw side-by-side behind tabs.
- **Central rail:** 120-160 px, sorted by decision salience: materiality,
  uncertainty, affected population, governance risk.
- **Comparability gate:** before rendering deltas, show a compact badge:
  `Comparable`, `Comparable with warnings`, or `Blocked`.
- **Delta language:** every change is labeled as `improved`, `worsened`,
  `mixed`, `uncertain`, or `not comparable`; color is never the only channel.
- **Temporal:** one `TemporalCursor` applies to both panes. Scenario and branch
  differences are explicit chips in the comparison frame.
- **Provenance:** every delta can open a mini provenance diff: source changes,
  model changes, verification changes, late-arriving evidence.
- **Command palette:** `Compare with baseline`, `Compare with previous run`,
  `Compare with selected run`.

### Backend contract

```http
GET /api/v1/runs/compare?a={run_a}&b={run_b}&valid_at=...&tx_at=...&scenario_id=...
```

```jsonc
{
  "comparison_frame": {
    "run_a": "run_1",
    "run_b": "run_2",
    "temporal_scope": { "valid_at": "...", "tx_at": "..." },
    "population": "national_workforce",
    "unit_policy": "canonical"
  },
  "comparability": {
    "status": "compatible",
    "warnings": [],
    "blocked_reasons": []
  },
  "deltas": [
    {
      "metric_id": "employment_rate_delta",
      "label": "Employment rate",
      "a": { "$ref": "QuantityValue" },
      "b": { "$ref": "QuantityValue" },
      "delta_absolute": { "$ref": "QuantityValue" },
      "delta_relative": { "$ref": "QuantityValue" },
      "significance": "uncertain",
      "decision_salience": 0.82,
      "lineage_delta": {
        "source_changed": true,
        "model_changed": false,
        "verification_changed": "pending_to_verified"
      }
    }
  ]
}
```

If backend precompute is unavailable, the endpoint may return
`status: "client_computable"` with normalized run payload URLs. UI fallback is
allowed only for compatible runs and must keep `TemporalScope` in every fetch.

### Research anchors

- GitHub/GitLab diff ergonomics: stable orientation, small change chunks,
  explicit conflict/compatibility states.
- NIST AI RMF and Microsoft HAX: communicate uncertainty, limitations and
  appropriate reliance.
- Google PAIR: compare model outputs by user task, not only by aggregate metric.
- Data-viz best practice: distributional deltas beat single-number deltas for
  heterogeneous policy impact.

### Acceptance criteria

- [ ] Opening diff for two compatible real runs returns meaningful comparison
      in ≤ 2 s p95 with backend precompute, ≤ 4 s fallback.
- [ ] Incompatible runs never render misleading deltas; they show typed
      `comparability.blocked_reasons`.
- [ ] Every decision-bearing delta is a `QuantityValue` with lineage and
      temporal echo.
- [ ] Distribution delta correctly visualizes at least quantiles, mean/median
      shift and uncertainty overlap.
- [ ] Governance radar diff remains readable under color-blind simulation and
      in high-contrast mode.
- [ ] Deep-link reproduces compare state: runs, temporal scope, scenario scope,
      metric filters and scroll anchor.
- [ ] Command palette can compare current run with baseline/previous/selected.
- [ ] Screen reader can traverse changed metrics in salience order and hear
      whether the change is improved/worsened/mixed/uncertain.

### Testing

- Unit: `compare-math.ts` normalization, CI overlap, delta labels.
- Unit: comparability report generation for compatible, warning and blocked
  examples.
- Component: split-pane sync scroll and mobile stacked layout.
- Backend: compare endpoint with bitemporal fixture; same `valid_at`, different
  `tx_at` changes only late evidence.
- A11y: keyboard traversal through central rail and delta widgets.
- Visual regression: 5 compare fixtures, including color-blind and high-contrast
  modes.

### Risks

| Риск                                             | Mitigation                                                                                           |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| Diff для разных problem frames выглядит точным   | Mandatory `ComparisonFrame` + typed comparability gate before any delta rendering.                   |
| Point estimates скрывают heterogeneous harm      | Distribution and subgroup deltas are first-class widgets; headline delta links to subgroup matrix.   |
| Provenance drift теряется за numeric delta       | `ProvenanceDrift` is part of default delta rail for any source/model/verification change.            |
| Compare endpoint становится тяжёлым              | Precompute popular pairs; cache by `ComparisonFrame`; client fallback only for normalized payloads.  |
| Цветовые diff-сигналы недоступны                 | Shape, label and ordering duplicate color meaning; WCAG/high-contrast tests required.                |

### Effort

- Contracts + backend compare service: 4 дня.
- Comparability gate + compare data hooks: 3 дня.
- Layout + command dialog + deep-linking: 4 дня.
- Delta widgets: 1 неделя.
- A11y/perf/visual tests: 3 дня.

---

## Фаза 2.4 — Counterfactual layer (B4)

**Длительность:** 4 недели.
**Тезис:** Counterfactual layer не должен быть `?cf=1`. Это управляемый
`ScenarioRef`: набор assumptions, interventions, constraints, temporal scope,
lineage и policy question. UI показывает real и counterfactual как две
связанные реальности, а не как декоративную пунктирную линию.

### Preconditions

- Фаза 2.1 завершена: `TemporalScope` поддерживает observed/present/future
  marker и сценарный placeholder.
- Фаза 2.2 завершена: provenance различает observed evidence, model-derived
  projection and counterfactual assumption.
- Фаза 1.2 завершена: uncertainty charts поддерживают multiple series,
  confidence intervals и explicit assumption labels.

### Product law

No anonymous counterfactuals. Любой CF-value обязан ссылаться на
`ScenarioRef`, а scenario обязан иметь manifest: interventions, assumptions,
validity window, baseline, author, model lineage, verification status and known
limitations.

### Scope

- Canonical `ScenarioManifest`: baseline, interventions, assumptions,
  constraints, affected population, temporal window, model family, status.
- `CounterfactualProvider` stores selected scenario, comparison mode and URL
  serialization.
- Scenario capability endpoint: list available scenarios and unsupported
  surfaces per run.
- `CounterfactualToggle` becomes mode switch: `actual`, `actual_vs_scenario`,
  `scenario_only`.
- Dual controls for scenario authoring/editing: one visible baseline value and
  one scenario intervention value.
- `CounterfactualQuantity`: actual + counterfactual + delta, all as
  `QuantityValue`.
- Charts show actual, scenario and delta with uncertainty and assumption badges.
- Provenance popover/deep-dive shows assumption lineage and model lineage.
- Scenario persistence: shareable URL, saved scenario draft, promoted scenario.

### Deliverables

```text
frontend/runtime-dashboard/src/app/providers/
├── CounterfactualProvider.tsx
├── CounterfactualProvider.test.tsx
├── scenario-scope.ts                 — parse/serialize/compare ScenarioScope
└── useCounterfactual.ts

frontend/runtime-dashboard/src/shared/ui/counterfactual/
├── CounterfactualModeSwitch.tsx
├── CounterfactualBadge.tsx
├── ScenarioPicker.tsx
├── ScenarioManifestPanel.tsx
├── AssumptionPill.tsx
├── DualSelector.tsx
├── DualSlider.tsx
├── DualInput.tsx
├── CounterfactualDelta.tsx
└── counterfactual-colors.ts

frontend/runtime-dashboard/src/shared/ui/quantity/
└── CounterfactualQuantity.tsx        — actual + scenario + delta renderer

frontend/runtime-dashboard/src/features/whatif/
├── ScenarioWorkbench.tsx             — integrates existing What-if features
├── ScenarioInterventionEditor.tsx
└── ScenarioValidationPanel.tsx

frontend/runtime-dashboard/src/api/hooks/
├── useScenarioCapabilities.ts
├── useScenarioManifest.ts
└── useCounterfactualMetrics.ts

policy-engine/src/polisyos/core/contracts/runtime.py
  — ScenarioRef, ScenarioManifest, CounterfactualMetric, ScenarioCapability

policy-engine/src/polisyos/runtime/http/routes/
├── scenarios.py
└── runs.py                           — scenario-aware metrics/run detail

policy-engine/src/polisyos/runtime/http/services/
└── scenarios.py                      — maps scenario manifest to model/fabric execution

policy-engine/docs/reference/runtime/counterfactual-layer.md
```

### UX spec

- **Mode switch:** Atlas shell exposes a compact segmented control:
  `Actual`, `Actual + Scenario`, `Scenario`.
- **Scenario picker:** disabled state explains why run has no scenario support;
  enabled state shows scenario status (`draft`, `computed`, `stale`, `failed`).
- **On-canvas language:** every scenario value carries an assumption badge and
  a delta label. No naked "future" numbers.
- **Color/pattern:** scenario line is patterned as well as colored; `--gold` is
  reserved for decision salience and deltas, not for every CF mark.
- **Controls:** DualSlider/DualInput show current baseline on the same scale as
  the intervention; invalid combinations explain constraints immediately.
- **Reduced motion:** switching modes fades labels only; charts do not morph
  continuously.
- **A11y:** screen reader announces "scenario value", "baseline value" and
  "difference" separately.

### Backend contract

```http
GET /api/v1/runs/{run_id}/scenarios
GET /api/v1/scenarios/{scenario_id}
POST /api/v1/runs/{run_id}/scenarios
GET /api/v1/runs/{run_id}/metrics?scenario_id=...&valid_at=...&tx_at=...
GET /api/v1/scenarios/{scenario_id}/capabilities
```

```jsonc
{
  "scenario": {
    "id": "scn_rate_cut_25bps",
    "baseline_run_id": "run_actual",
    "status": "computed",
    "temporal_scope": { "valid_at": "...", "tx_at": "..." },
    "interventions": [
      { "field": "policy_rate", "operator": "set", "value": { "$ref": "QuantityValue" } }
    ],
    "assumptions": [
      {
        "id": "asm_no_external_shock",
        "label": "No external demand shock",
        "status": "operator_assumption",
        "lineage": { "$ref": "LineageRef" }
      }
    ]
  },
  "metrics": {
    "employment_rate_delta": {
      "actual": { "$ref": "QuantityValue" },
      "counterfactual": { "$ref": "QuantityValue" },
      "delta": { "$ref": "QuantityValue" },
      "scenario_ref": "scn_rate_cut_25bps"
    }
  }
}
```

### Research anchors

- Rubin causal model / potential outcomes framing: always name baseline,
  treatment/intervention and target estimand.
- NIST AI RMF: counterfactual output must expose assumptions, limitations and
  intended use.
- Google PAIR and Microsoft HAX: keep people oriented when AI output is
  simulated, uncertain or inappropriate for reliance.

### Acceptance criteria

- [ ] No scenario value can render without `ScenarioRef` and assumption lineage.
- [ ] URL reproduces selected scenario, temporal scope and mode.
- [ ] Toggle between Actual and Actual + Scenario updates visible values in
      ≤ 200 ms after data is cached.
- [ ] Scenario capability endpoint lists supported/unsupported surfaces and
      reasons for unsupported metrics.
- [ ] Counterfactual metrics do not double-fetch actual values; shared batch
      payload or normalized cache is used.
- [ ] Screen reader announces actual, scenario and delta distinctly.
- [ ] Provenance deep-dive shows assumption nodes and model/source lineage for
      scenario values.
- [ ] Stale scenario state is visible when baseline evidence or model version
      changed after scenario computation.

### Testing

- Unit: `scenario-scope.ts` URL roundtrip and equality.
- Unit: invalid intervention constraints and scenario stale detection.
- Component: mode switch, scenario picker, dual controls, quantity renderer.
- Backend: scenario capability + metrics response with temporal echo.
- E2E: create scenario → inspect deltas → share URL → reopen same state.
- A11y: keyboard-only scenario selection and DualSlider operation.

### Risks

| Риск                                             | Mitigation                                                                                         |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| `?cf=1` создаёт анонимные simulations            | `ScenarioManifest` is mandatory; anonymous CF values fail validation.                              |
| Cognitive overload from two realities            | Default mode is Actual; Actual + Scenario requires explicit user action and shows manifest summary. |
| Scenario data becomes stale silently             | Scenario includes baseline hashes and model version; stale badge blocks "verified" language.       |
| Backend не поддерживает CF для всех metrics      | Capability endpoint + honest unsupported state; no silent fallback to actual.                      |
| Цвет/паттерн конфликтует с provenance statuses   | Dedicated counterfactual tokens and composition rules; high-contrast/CB tests required.            |

### Effort

- Scenario contracts + backend capability/manifest: 1 неделя.
- Provider + URL/query-key discipline: 3 дня.
- Mode switch + scenario picker + dual controls: 1 неделя.
- Quantity/chart/what-if integration: 1 неделя.
- Provenance/a11y/perf tests: 3 дня.

---

## Фаза 2.5 — Native bureaucratic rendering (B5)

**Длительность:** 4 недели.
**Тезис:** Бюрократический render должен быть не "красивым PDF", а
машино-проверяемым документом: canonical Document AST → jurisdictional renderer
→ accessible HTML/PDF/DOCX, with provenance, authorship, watermark and template
version. Так PolicyOS выглядит легитимно не потому, что имитирует форму, а
потому что честно показывает draft status, источники и ответственность.

### Preconditions

- Фаза 1.5 завершена: prose/reading system can render long-form artifacts.
- Фаза 1.6 завершена: narrative blocks have authorship and model/evidence
  attribution.
- Фаза 2.2 завершена: numbers in documents render through `<Quantity>` and
  provenance survives export.
- External review slot reserved: Ukrainian legal/document specialist validates
  templates and disclaimers.

### Product law

Every official-looking artifact is a draft until signed outside PolicyOS.
Generated documents must carry visible and machine-readable watermark:
`Generated by PolicyOS / Draft / Not an official state document`, template
version, render timestamp and packet hash.

### Scope

Four first-class genres:

- **Постанова КМУ**
- **Законопроект**
- **Експертний висновок**
- **Аналітична записка**

Core approach:

- Canonical `BureaucraticDocumentAST` independent of React/PDF renderer.
- Jurisdictional templates versioned by genre and jurisdiction:
  `ua.kmu.postanova.v1`, `ua.rada.zakonoproekt.v1`, etc.
- Structured sections: header, реквізити, preamble, legal basis, operative
  clauses, annexes, signatures, epistemic appendix.
- Strict numbering engine: Розділ/Глава/Стаття/Пункт/Підпункт and annex labels.
- Epistemic map: evidence-filled / model-generated / operator-filled /
  imported-from-source per block.
- Accessible HTML first; PDF/DOCX generated from same AST with parity checks.
- Asset/legal audit: only public domain/licensed symbols; seal placeholders
  never pretend to be official signatures.

### Deliverables

```text
frontend/runtime-dashboard/src/features/artifacts/bureaucratic/
├── BureaucraticArtifactView.tsx
├── BureaucraticArtifactView.test.tsx
├── BureaucraticArtifactView.a11y.test.tsx
├── BureaucraticGenrePicker.tsx
├── BureaucraticTemplateBadge.tsx
├── ast/
│   ├── bureaucratic-document-ast.ts
│   ├── bureaucratic-document-ast.test.ts
│   ├── numbering.ts
│   ├── numbering.test.ts
│   └── epistemic-map.ts
├── renderers/
│   ├── PostanovaKMURenderer.tsx
│   ├── ZakonoproektRenderer.tsx
│   ├── ExpertVysnovokRenderer.tsx
│   ├── AnalitichnaZapyskaRenderer.tsx
│   └── shared/
│       ├── BureaucraticHeader.tsx
│       ├── BureaucraticNumbering.tsx
│       ├── BureaucraticWatermark.tsx
│       ├── EpistemicLegend.tsx
│       ├── SignatureBlock.tsx
│       └── bureaucratic-tokens.ts
└── export/
    ├── export-html.ts
    ├── export-pdf.ts                 — browser print pipeline / Playwright PDF
    ├── export-docx.ts                — optional if dependency accepted
    └── parity-check.ts

frontend/runtime-dashboard/public/bureaucracy/
├── tryzub.svg                        — public domain/licensed audit required
├── draft-watermark.svg
└── README.md                         — asset provenance and license notes

policy-engine/src/polisyos/core/contracts/runtime.py
  — BureaucraticDocument, BureaucraticBlock, BureaucraticTemplateRef

policy-engine/src/polisyos/runtime/http/routes/artifacts.py
  — POST /api/v1/artifacts/{packet_id}/render
  — GET /api/v1/artifacts/{packet_id}/export

policy-engine/src/polisyos/runtime/http/services/bureaucratic_rendering.py
  — packet → BureaucraticDocumentAST mapping

policy-engine/docs/brand/BUREAUCRATIC_RENDERING.md
policy-engine/docs/reference/runtime/bureaucratic-rendering.md
```

### UX spec

- **Entry point:** Artifact viewer exposes `Render as...` with four genres.
- **Genre switch:** changing genre preserves decision packet content, not manual
  layout edits.
- **Document chrome:** official-looking header, реквізити and numbering, but
  persistent draft watermark and template/version badge.
- **Trust layer:** quantities keep provenance cues; authored blocks keep
  author/timestamp; Trust View expands hashes inside the document.
- **Epistemic legend:** first page or appendix shows how much content is
  evidence-filled, model-generated, operator-filled and imported.
- **Export preview:** user sees print margins/page breaks before export.
- **Accessibility:** headings, lists, tables and footnotes are semantic in HTML;
  PDF export must preserve reading order as far as chosen pipeline allows.

### Backend contract

```http
POST /api/v1/artifacts/{packet_id}/render
Content-Type: application/json
{
  "genre": "postanova_kmu",
  "jurisdiction": "ua",
  "template_version": "ua.kmu.postanova.v1",
  "temporal_scope": { "valid_at": "...", "tx_at": "..." },
  "trust_view": false
}
```

```jsonc
{
  "document": {
    "id": "doc_123",
    "packet_id": "pkt_123",
    "genre": "postanova_kmu",
    "template": { "id": "ua.kmu.postanova.v1", "version": "1.0.0" },
    "status": "draft",
    "watermark": "Generated by PolicyOS / Draft / Not an official state document",
    "blocks": [],
    "epistemic_summary": {
      "evidence_filled": 0.54,
      "model_generated": 0.22,
      "operator_filled": 0.18,
      "imported": 0.06
    }
  }
}
```

### Research anchors

- ДСТУ 4163:2020 and Ukrainian Verkhovna Rada drafting rules: реквізити,
  structure, numbering and formal document style.
- GOV.UK Design System and USWDS: government service clarity, accessibility,
  plain-language patterns and print discipline.
- PDF/UA and WCAG principles: semantic reading order, text alternatives and
  keyboard-accessible HTML preview.

### Acceptance criteria

- [ ] Legal/document specialist signs off all 4 template drafts and watermark
      language.
- [ ] Same `BureaucraticDocumentAST` renders to HTML and PDF with no missing
      blocks across 10 real decision packets.
- [ ] PDF export has stable page breaks and no overlapping headers/footers in
      Chrome; Firefox/Safari preview parity ≥ 95%.
- [ ] Every decision-bearing number inside document uses `<Quantity>` and keeps
      provenance/deep-dive path in HTML view.
- [ ] Draft watermark appears visually and in exported metadata.
- [ ] Epistemic legend matches block-level authorship/provenance counts.
- [ ] Asset license audit exists for all public symbols/placeholders.
- [ ] Print/export works in Ukrainian, English and Russian locales where
      translation exists.

### Testing

- Unit: AST schema validation, numbering, epistemic summary.
- Component: each renderer with dense, long, missing-field and annex-heavy
  fixtures.
- Export: PDF snapshot/parity checks for 10 packets.
- A11y: HTML document heading order, table semantics and keyboard navigation.
- Legal review checklist: template structure, watermark, prohibited claims.

### Risks

| Риск                                                    | Mitigation                                                                                              |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Official-looking render can be mistaken for state act   | Persistent watermark, metadata, draft badge and export disclaimer; no real seals/signatures by default. |
| Templates drift when rules change                       | Versioned templates and migration notes; template id included in every export.                          |
| Pixel-perfect PDF fights accessible HTML                | HTML-first AST; PDF parity tests; inaccessible PDF features blocked unless reviewed.                     |
| Manual template tweaks fork the source of truth         | AST is canonical; renderer-specific overrides must be typed and audited.                                |
| Asset licensing risk                                    | Asset provenance file required; only public domain/licensed assets.                                     |

### Effort

- Document AST + numbering + epistemic map: 1 неделя.
- Four renderers + shared components: 1.5 недели, parallelizable.
- Backend rendering contract + artifact mapping: 4 дня.
- PDF/export pipeline + parity checks: 4 дня.
- Legal/accessibility review and polish: 3 дня.

---

## Фаза 2.6 — Trust view (B6)

**Длительность:** 2 недели.
**Тезис:** Trust View — это audit rendering mode, not a separate tab. Он
включает доказательства прямо там, где принимается решение: hash, verifier,
timestamp, provenance status, authorship, uncertainty method and temporal scope.

### Preconditions

- Фаза 2.2 завершена: every decision number has provenance and deep-dive.
- Фаза 1.6 завершена: narrative/authored blocks have author registry and
  timestamps.
- Фаза 2.1 завершена: temporal scope can be rendered and echoed by backend.

### Product law

Trust View must not fetch a different truth. It is a rendering mode over the
same data and cache keys. If additional verification metadata is needed, it is
prefetched/batched and tied to the same `TemporalScope`.

### Scope

- `TrustViewProvider`: mode (`off`, `compact`, `expanded`), density-aware.
- `TrustViewToggle` in Atlas shell + keyboard shortcut.
- `TrustInspector`: side panel for selected Quantity/AuthoredText/Artifact.
- Inline trust metadata for Quantity, AuthoredText, ProvenanceStrip, charts and
  bureaucratic documents.
- Hash chips: deterministic truncate/copy/open deep-dive.
- Verification metadata: `verified_by`, `verified_at`, `verification_method`,
  `dispute_status`, `freshness`, `temporal_scope`.
- Diacritic glyph modifiers: status additions without new icon explosion.
- Trust View CSS cascade: additive overlays, no layout reflow beyond defined
  density budget.

### Deliverables

```text
frontend/runtime-dashboard/src/app/providers/
├── TrustViewProvider.tsx
├── TrustViewProvider.test.tsx
└── useTrustView.ts

frontend/runtime-dashboard/src/shared/ui/trust-view/
├── TrustViewToggle.tsx
├── TrustViewToggle.test.tsx
├── TrustViewBadge.tsx
├── TrustInspector.tsx
├── TrustInspector.test.tsx
├── TrustMetadata.tsx
├── HashChip.tsx
├── VerificationStatus.tsx
├── DisputeBadge.tsx
├── TemporalScopeChip.tsx
├── trust-glyphs.ts
└── trust-view.css

frontend/runtime-dashboard/src/shared/ui/quantity/
└── Quantity.tsx                      — compact/expanded trust rendering

frontend/runtime-dashboard/src/shared/ui/authored-text/
└── AuthoredText.tsx                  — author/timestamp/model/source metadata

frontend/runtime-dashboard/src/shared/charts/
└── uncertainty-rendering.ts          — CI method labels in Trust View

policy-engine/src/polisyos/core/contracts/runtime.py
  — VerificationMetadata, TrustMetadataRef

policy-engine/src/polisyos/runtime/http/routes/lineage.py
  — batch verification metadata if not already included

policy-engine/docs/brand/TRUST_VIEW.md
```

### UX spec

- **Toggle:** shell button plus `Cmd/Ctrl+Shift+T`; cycles `off → compact →
  expanded`.
- **Compact:** numbers show status glyph + short hash chip where space allows;
  charts show CI method only on focus/hover.
- **Expanded:** inline second row with source/method/verifier/time for decision
  surfaces; dense tables use row-level inspector instead of expanding every cell.
- **TrustInspector:** opens from hash chip, status glyph or keyboard command;
  shows selected element, provenance summary, verification metadata, temporal
  scope and deep-dive/export actions.
- **No layout surprise:** trust metadata uses reserved slots or overlays; if it
  cannot fit, it collapses to inspector affordance.
- **Copy:** hash chips support copy hash and copy audit link.
- **A11y:** metadata is reachable by keyboard and announced without duplicating
  entire provenance graph for every cell.

### Backend contract

Trust metadata may be embedded in existing lineage/quantity payloads or fetched
through batch endpoint, but every response must echo `temporal_scope`.

```jsonc
{
  "trust_metadata": {
    "hash": "sha256:...",
    "verification_status": "verified",
    "verified_by": "RiskReviewBot@2.0",
    "verified_at": "2026-04-16T09:20:00Z",
    "verification_method": "lineage_hash_match",
    "freshness": "current",
    "dispute_status": "none",
    "temporal_scope": { "valid_at": "...", "tx_at": "..." }
  }
}
```

### Research anchors

- NIST AI RMF: trustworthiness as governance, measurement, transparency and
  accountability, not a decorative confidence badge.
- Microsoft HAX: support appropriate reliance and show system limits at the
  moment of use.
- OpenTelemetry semantic conventions: consistent metadata naming for observable
  systems.
- WCAG hover/focus and keyboard guidance: audit metadata must be dismissible,
  reachable and persistent.

### Acceptance criteria

- [ ] Toggle works globally and state is preserved in URL/user preference.
- [ ] Trust View reuses same run/quantity/lineage data and never drops
      `TemporalScope` from query keys.
- [ ] Compact mode adds ≤ 50 ms render overhead on Run Detail with 100+
      quantities.
- [ ] Expanded mode does not create incoherent overlap in dashboard, table,
      chart or bureaucratic document views.
- [ ] Hash chips open deep-dive or TrustInspector and support copy hash.
- [ ] Verification metadata is visible for quantities, authored text and
      bureaucratic document blocks.
- [ ] Keyboard-only audit journey works from visible number → trust metadata →
      provenance deep-dive → export.
- [ ] Visual regression passes for normal, compact, expanded, high-contrast and
      condensed density modes.

### Testing

- Unit: provider modes, URL/preference serialization, hash truncation.
- Component: Quantity/AuthoredText/chart/document trust overlays.
- Performance: render budget with 100+ quantities and dense table fixture.
- A11y: keyboard traversal and screen-reader labels for trust metadata.
- Backend: verification metadata response includes temporal echo and stable hash.

### Risks

| Риск                                                | Mitigation                                                                                         |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Trust View becomes visual noise                     | Compact/expanded modes, density-aware collapse, inspector for dense surfaces.                      |
| Trust metadata triggers mass refetch                | Batch metadata, same cache keys, no separate "trust truth" endpoint.                               |
| Hash chips break layout                             | Reserved slots, truncation, copy/open actions, collapse in condensed density.                      |
| Users confuse verification with policy correctness  | Labels distinguish verification of lineage/hash from endorsement of policy recommendation.          |
| Accessibility duplication becomes overwhelming      | Summarized labels by default; full metadata available on demand through inspector.                  |

### Effort

- Provider + toggle + URL/preference: 2 дня.
- Trust metadata components + inspector: 4 дня.
- Quantity/AuthoredText/chart/document integration: 4 дня.
- Backend metadata additions + tests: 2 дня.
- Visual/a11y/perf polish: 3 дня.

---

## Фаза 2.7 — System polish

**Длительность:** 2 недели.
**Тезис:** Polish is not "nice to have". Это hardening слоя, который превращает
набор сильных primitives в систему: print, CLI, motion, categorical palettes,
small multiples, OG/email templates, final composition rules and quality gates.

### Preconditions

- Фазы 2.0-2.2 завершены; ideally 2.3-2.6 have at least one vertical slice.
- Wave 1 brand/a11y/density/motion decisions exist and are not being rewritten.
- Build/test/storybook infrastructure can run targeted visual/a11y checks.

### Scope

- Print/PDF refinement over Reading View and bureaucratic renders.
- CLI styleguide for `@polisyos/cli`: tokens, severity, progress, tables,
  provenance/trust output.
- Motion spec finalization: durations, easing, reduced motion, forbidden motion.
- Composition rules finalization: glyph density, provenance/counterfactual/trust
  stacking, color hierarchy, anti-patterns.
- Categorical-8 and Categorical-12 palettes with color-blind/high-contrast
  checks.
- `SmallMultiples` for regional/sectoral comparison.
- OG/social cards and email templates for shareable runs/compare/scenario links.
- Quality gates: print snapshots, palette checks, reduced-motion checks,
  design lint for forbidden color/motion/card patterns.

### Deliverables

```text
frontend/runtime-dashboard/src/styles/
├── print.css                         — refined print/long-form rules
├── motion.css                        — canonical motion tokens
└── media.css                         — reduced motion / high contrast / print helpers

policy-engine/docs/brand/
├── CLI_STYLEGUIDE.md
├── MOTION.md                         — expanded + reduced motion law
├── COMPOSITION_RULES.md              — finalized stacking/anti-patterns
├── PRINT_AND_EXPORT.md
├── EMAIL_TEMPLATES.md
└── SOCIAL_TEMPLATES.md

frontend/runtime-dashboard/src/shared/charts/
├── categorical-palettes.ts           — 8 + 12 palettes + semantic names
├── categorical-palettes.test.ts
├── SmallMultiples.tsx
├── SmallMultiples.test.tsx
└── SmallMultiples.stories.tsx

frontend/runtime-dashboard/src/features/export/social/
├── OGCard.tsx
├── OGCard.test.tsx
├── OGCard.stories.tsx
├── generate-og.ts                    — Satori/HTML-to-image pipeline
├── EmailSummary.tsx
└── email-fixtures.ts

packages/cli/src/styleguide/
├── tokens.ts
├── format-status.ts
├── format-table.ts
├── format-provenance.ts
└── README.md

tools/design/
├── check-categorical-palettes.ts
├── check-motion-tokens.ts
├── check-print-snapshots.ts
└── check-composition-rules.ts
```

### UX spec

- **Print:** dashboard chrome disappears; document metadata, provenance summary,
  page numbers and source appendix survive.
- **CLI:** output uses the same semantic statuses as UI: verified/pending/stale/
  disputed/untraced, but in ASCII-safe tokens and accessible contrast.
- **Motion:** temporal scrubbing and popovers remain responsive; no motion is
  essential for understanding; reduced-motion mode is a first-class path.
- **Palettes:** categorical colors are not variations of one hue; pattern/shape
  fallback exists for dense charts.
- **Small multiples:** optimized for scanning: stable axes, clear selected
  region/sector, keyboard traversal, no decorative card nesting.
- **OG/email:** generated previews include run title, key quantity, trust status,
  temporal scope and draft/verified state; no private source data leaks.

### Research anchors

- USWDS/GOV.UK: service consistency, print clarity and accessible government
  communication.
- WCAG 2.2: non-text contrast, focus visibility, reduced motion and hover/focus
  behavior.
- OpenTelemetry: consistent status/severity naming for CLI and system output.
- Satori/OG rendering practice: deterministic, font-pinned social previews.

### Acceptance criteria

- [ ] Five real decision packets print without clipped content, overlapping
      headers or missing provenance summary.
- [ ] CLI verbose output uses tokenized statuses and aligns with UI trust/
      provenance vocabulary.
- [ ] Motion tokens are centralized; reduced-motion mode passes targeted checks
      for scrubber, popover, dialogs and compare view.
- [ ] `Categorical-8` and `Categorical-12` pass color-blind simulation and
      high-contrast review; charts also have non-color distinction where needed.
- [ ] `SmallMultiples` handles 8 regions × 12 sectors without visible lag and
      with stable axes.
- [ ] OG cards generate for run, compare and scenario URLs with correct temporal
      scope and no confidential raw-source leakage.
- [ ] Email templates render in narrow/mobile and desktop widths and include
      accessible plain-text fallback.
- [ ] Composition rules have concrete anti-pattern examples and a design-lint
      check for at least the highest-risk violations.

### Testing

- Print snapshot checks for Run Detail, Reading View and bureaucratic document.
- Palette simulation checks and contrast checks.
- Component tests for SmallMultiples and OG card fixtures.
- CLI snapshot tests for success/warning/error/provenance output.
- Email rendering checks for mobile/desktop widths and plain-text fallback.
- Reduced-motion manual pass and automated CSS/token check.

### Risks

| Риск                                          | Mitigation                                                                                          |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Polish becomes a grab bag without ownership   | Split into five tracks: print/export, CLI, motion/composition, charts, social/email.                |
| OG/email leak private evidence                | Use explicit public summary payloads; never render raw-source text unless share policy allows it.   |
| Palette looks pretty but fails accessibility  | Automated simulation + human review; pattern fallback for high-density charts.                      |
| CLI drifts from UI vocabulary                 | Shared status glossary and snapshot fixtures for CLI/UI examples.                                  |
| Print fixes regress screen UI                 | Print-only stylesheet and snapshot gate; no global layout hacks.                                   |

### Effort

- Print/export hardening: 3 дня.
- CLI styleguide and utilities: 2 дня.
- Motion/composition docs + checks: 3 дня.
- Palettes + SmallMultiples: 3 дня.
- OG/email templates: 3 дня.
- Cross-track QA and final design review: 2 дня.

---

## 4. Success metrics

| Слой           | Метрика                              | Целевое значение                                          | Замер              |
| -------------- | ------------------------------------ | --------------------------------------------------------- | ------------------ |
| **Wave 1**     |                                      |                                                           |                    |
| Бренд          | Blind recognition test               | ≥ 80% узнают Janus-glyph как PolicyOS                     | After 1.1          |
| A11y           | WCAG 2.2 AA automated audit          | 0 blockers                                                | After 1.3          |
| Uncertainty    | % metric-рендеров с CI               | ≥ 90%                                                     | After 1.2          |
| Theme          | Storybook coverage                   | 100% компонентов × 3 themes × 3 densities                 | After 1.4          |
| Prose          | Reading view usage                   | ≥ 30% operators открывают ≥ 1×/week                       | 3 months after 1.5 |
| Authorship     | Text coverage                        | 100% narrative blocks have `author`                       | After 1.6          |
| i18n           | Plural/typography correctness        | 100% ICU + 100% NBSP rules                                | After 1.7          |
| **Wave 2**     |                                      |                                                           |                    |
| Quantity law   | Decision numbers as `QuantityValue`  | 100% decision-bearing, 0 silent naked values              | After 2.2          |
| Provenance law | Traceability coverage                | ≥ 95% traced, 100% untraced with reason code              | After 2.2          |
| Time cursor    | Endpoints supporting `TemporalScope` | ≥ 90% time-sensitive with `valid_at` + `tx_at`            | After 2.1          |
| Bitemporal UX  | Reproducible shared URLs             | 100% Run Detail quantities/charts/lineage reproduce state | After 2.1          |
| Policy diff    | Comparable diffs                     | 100% diff views gated by `ComparisonFrame`                | After 2.3          |
| Policy diff    | Diff view usage                      | ≥ 20% reviewers use ≥ 1×/week                             | 3 months after 2.3 |
| CF layer       | Scenario manifests                   | 100% CF values have `ScenarioRef` + assumption lineage    | After 2.4          |
| CF layer       | Coverage                             | ≥ 80% decision packets offer ≥ 1 scenario                 | After 2.4          |
| Bureaucratic   | Native document AST                  | ≥ 4 genres render from one canonical AST                  | After 2.5          |
| Bureaucratic   | Export parity                        | HTML/PDF no missing blocks across 10 real packets         | After 2.5          |
| Trust view     | Audit flow time                      | −40% vs current audit UX                                  | After 2.6          |
| Trust view     | Metadata coverage                    | 100% quantities/authored blocks show trust metadata       | After 2.6          |
| Polish         | Design-system gates                  | Print, palette, motion, OG/email checks in CI            | After 2.7          |

---

## 5. Risks & mitigations

| Level            | Risk                                            | Mitigation                                                              |
| ---------------- | ----------------------------------------------- | ----------------------------------------------------------------------- |
| **Program**      | Wave 2 стартует без закрытого Wave 1            | Gate §3.1 с жёстким checklist                                           |
| **Program**      | Один инженер перегорает на 32 недели            | Планировать каждую 8-ю неделю как light (docs/refactor)                 |
| **Architecture** | Provenance law ломает миллион мест              | Quantity classification + phased warn → error + codemod (2.0)           |
| **Architecture** | `QuantityValue` становится тяжёлым envelope     | Compact summary by default; full graph lazy-load; batch lookup          |
| **Architecture** | `valid_at` + `tx_at` требуют DB-миграций        | DBA task в 2.1, начать заранее; reuse Fabric bitemporal query semantics |
| **Design**       | Глифы «засоряют»                                | 10-лимит + whitelist (1.1) + composition rules (1.0)                    |
| **Design**       | Maskot или bureaucratic render срывается в китч | Non-goals §2 + design-review gate                                       |
| **Backend**      | Coordination с policy-engine медленна           | Contracts как ADR в начале каждой фазы                                  |
| **Legal**        | Bureaucratic genres под угрозой подделки формы  | Watermark + legal review (2.5)                                          |
| **Performance**  | Temporal scrubbing не 60 fps                    | Perf budget в CI (2.1), Lighthouse regression checks                    |
| **A11y**         | Новые компоненты ломают a11y                    | `.a11y.test.tsx` обязателен в PR checklist                              |

---

## 6. Owner matrix

| Область                      | Артефакты                                                                | Ответственный слой   |
| ---------------------------- | ------------------------------------------------------------------------ | -------------------- |
| Бренд, глифы, sigil          | `shared/brand/*`, `public/atlas/*`, `docs/brand/*`                       | Design system        |
| Токены (dark, density, a11y) | `shared/ui/designTokens.ts`, `styles/*.css`                              | Design system        |
| Charts (uncertainty, deltas) | `shared/charts/*`                                                        | Data-viz             |
| Провайдеры (time, cf, trust) | `app/providers/*`                                                        | App shell            |
| Прозаические артефакты       | `features/artifacts/reading-view/*`                                      | Publications         |
| Bureaucratic renderers       | `features/artifacts/bureaucratic/*`                                      | Publications + legal |
| i18n                         | `i18n/*`                                                                 | Localization         |
| A11y infra                   | `shared/a11y/*`, `tools/design/*`                                        | Quality              |
| Quantity/provenance UI       | `shared/ui/quantity/*`, `eslint-rules/*`                                 | App shell + Quality  |
| Backend contracts            | `policy-engine/src/polisyos/runtime/http/*`, `core/contracts/runtime.py` | Runtime API          |
| Fabric lineage/time-travel   | `policy-engine/src/polisyos/fabric/*`                                    | Fabric               |
| CLI styleguide               | `packages/cli/*`                                                         | DX                   |

---

## 7. Anchor artifacts

Конкретные наблюдаемые артефакты, которыми меряется «готово». Группированы по волнам.

### Wave 1

1. **Обновлённый favicon** — Janus-glyph узнаётся в 16 px.
2. **Decision packet cover page** — Janus-medallion сверху, ProvenanceStrip ниже, EvidenceSigil в углу.
3. **Uncertainty showcase** — Run Detail с живым fan chart + CI bands + pattern-fills для identified/estimated/assumed.
4. **WCAG 2.2 AA report** — PDF с 0 P0.
5. **VPAT** — публично доступен по URL.
6. **Dark theme demo** — все 70+ компонентов в Storybook.
7. **Density "Condensed"** — 40+ scenarios на экран.
8. **Reading view** — decision packet выглядит как Stripe Press.
9. **AuthoredText mix** — narrative с 5 регистрами одновременно видимыми.
10. **UA locale** — корректная плюрализация + ₴ + «ёлочки» + NBSP.

### Wave 2

1. **Bitemporal scrubber** — скрабинг на 60 fps, `valid_at` + `tx_at` reproduce state.
2. **Quantity hover** — в любом decision number появляется compact provenance за 150 ms.
3. **Lineage trace** — от финального числа до raw source / method / agent / timestamp за 3 клика.
4. **Policy diff** — два run'а, `ComparisonFrame`, comparability gate, causal delta strip.
5. **Scenario Manifest** — real + counterfactual + delta, assumptions and lineage visible.
6. **Постанова КМУ render** — canonical AST, правильная шапка, нумерация, watermark, epistemic legend.
7. **Trust view** — compact/expanded audit mode, hashes, verifier, timestamps and temporal scope inline.
8. **System polish kit** — print, CLI, palettes, motion, small multiples, OG/email gates.

---

## Appendix A — Critical path dependency graph

```text
1.0 Foundations
  ├─ 1.1 Visual language
  │   ├─ 1.2 Uncertainty (also needs 1.0)
  │   ├─ 1.3 A11y (also needs 1.2)
  │   ├─ 1.4 Dark/density (also needs 1.3)
  │   ├─ 1.5 Prose (needs 1.1, 1.4)
  │   └─ 1.6 Authorship (needs 1.1, 1.5)
  └─ 1.7 i18n (parallel to everything)
           ↓
        1.8 Closeout gate → Wave 2
           ↓
      2.0 Provenance foundations
           ↓
      2.1 Time-as-primitive
           ↓
      2.2 Provenance-on-hover
           ├─ 2.3 Policy diff (needs 2.1, 2.2)
           ├─ 2.4 Counterfactual (needs 2.1, 2.2, 1.2)
           ├─ 2.6 Trust view (needs 2.2, 1.6)
           └─ 2.7 Polish (parallel after at least one 2.3-2.6 vertical slice)

      2.5 Bureaucratic can run as a parallel publications/legal stream after
      1.5 + 1.6, but final trust/provenance integration waits for 2.2.
```

## Appendix B — Definition of Done (применяется к каждой фазе)

Phase is Done when:

- [ ] All Deliverables exist and are committed to main.
- [ ] All Acceptance criteria pass.
- [ ] `pnpm test` green.
- [ ] `pnpm test:a11y` green.
- [ ] Visual regression — 0 unexpected diffs (or all diffs signed off).
- [ ] Storybook updated for any new public API.
- [ ] Feature flag configured.
- [ ] ADR referenced if applicable.
- [ ] CHANGELOG-DESIGN.md entry.
- [ ] No new ESLint/TypeScript errors.
- [ ] `pnpm run check:contrast` green.
- [ ] Backend contract changes documented in OpenAPI + types regenerated.
- [ ] If phase touches decision-bearing numbers: quantity coverage report updated,
      no silent naked decision values.
- [ ] If phase touches time-sensitive surfaces: `TemporalScope` is included in
      URL, query keys, ETags/cache keys, and API response echo.
- [ ] Demo recorded (screencast) for stakeholder review.

## Appendix C — Immediate next actions (kick-off неделя)

1. Создать ветку `design/wave1-phase-0-foundations`.
2. Скопировать шаблон ADR из `docs/adr/_template.md` (создать если нет).
3. Написать ADR-042 (Janus/Atlas dual brand) — draft.
4. Написать skeleton `docs/brand/GLYPH_SPECIFICATION.md` — геометрия сетки.
5. Настроить `tools/design/check-contrast.ts` — стартовая версия.
6. Создать tracking issue в project board (Linear/GitHub) с структурой этого плана.
7. Забукать 30-минутный review slot с внешним design-consultant на конец Phase 1.0.

### Wave 2 spine kick-off после gate

1. Зафиксировать ADR-043 как `QuantityValue + TemporalScope + progressive provenance`, не как простой `lineage_id`.
2. Сделать inventory decision-bearing чисел: `decision / telemetry / layout / debug`.
3. Спроектировать `QuantityValue`, `LineageRef`, `TemporalRef`, `UnitRef`, `VerificationStatus` в runtime contracts.
4. Поднять `GET /api/v1/lineage/{lineage_id}` и `POST /api/v1/lineage/batch` поверх существующего Fabric lineage.
5. Добавить `GET /api/v1/runs/{run_id}/quantities` как coverage/debug endpoint.
6. Создать `TemporalScope` spec: `valid_at`, `tx_at`, `branch`, `snapshot_id`, `scenario_id`, URL serializer.
7. Собрать one-run vertical slice: одно decision number → `QuantityValue` → temporal scrub → provenance popover fixture.
