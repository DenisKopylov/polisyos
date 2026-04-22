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

PolicyOS в этом плане получает два несводимых примитива:
- **B1** Time-as-primitive — скрабируемый темпоральный курсор как глобальное измерение интерфейса.
- **B2** Provenance-on-hover — lineage-граф за каждым количественным утверждением как сквозной закон.

Вокруг них достраиваются ещё четыре (policy diff, counterfactual layer, native bureaucratic rendering, trust view) и закрываются шесть SOTA-пробелов — всё поверх существующей Atlas-системы без слома её лексического и хроматического ядра.

**План построен как две волны. Каждая — последовательность фаз. Фазы упорядочены по зависимостям, а не по темам.** Каждая фаза содержит: тезис, preconditions, scope, deliverables с точными путями, контракты backend-API, acceptance criteria, тесты, риски. Между волнами — gate с ревью.

Общий бюджет: **~32 недели** (Волна 1 — 14 недель; Волна 2 — 18 недель). Рассчитано на одного fullstack-инженера + подключаемые: design-review, legal (для жанров), DBA (для `as_of`-контрактов).

---

## 1. Диагноз текущего состояния

### 1.1. Капитал — что **не трогаем**

| Слой | Состояние | Почему капитал |
|---|---|---|
| Лексическая дисциплина | 18-словарный домен, запрет `you`, sentence case, no emoji | Редчайший уровень в AI-продуктах 2025–26 |
| Хроматическая палитра | Sandstone + graphite без синевы | Осознанное меньшинственное позиционирование |
| Glass-панели с inset rim-light | Сквозной мотив | Узнаваемая подпись |
| Сигнальная триада | teal=verified, ember=blocked, gold=pending | Жёсткая семантика |
| Типография | Manrope 800 / IBM Plex Mono / Instrument Serif | Профессиональный контроль регистров |
| UI-база | 70+ шаренных компонентов в `src/shared/ui/`, `.a11y.test.tsx` рядом | Готовая техническая основа |
| Chart-база | 20+ компонентов в `src/shared/charts/` (ConfidenceDial, ForestPlot, GradedErrorBar, UncertaintyDisplay) | Частично покрывает §1.2 |
| Токены | `designTokens.ts` (evidence/governance/severity/status/transport) | Готовые семантические шкалы |
| Дата-слой | 50+ React Query хуков, openapi-typescript, SSE runsLiveMachine | Фундамент для реактивных примитивов |

### 1.2. Шесть критических SOTA-пробелов (Wave 1 scope)

| # | Пробел | Последствие | Фаза |
|---|---|---|---|
| G1 | Визуальный язык **неопределённости** не систематизирован (есть примитивы, нет языка) | PolicyOS показывает CI/identifiability/counterfactual spreads как плоские числа | 1.2 |
| G2 | **Accessibility** (WCAG 2.2 AA) не задокументирована, нет pattern-fills для колор-блайнд | Блокер для процурмента в ЕС/укр. госсектор | 1.3 |
| G3 | Нет **dark theme v2** и **density modes** | Аналитики в 8-часовых сессиях уйдут в нативный терминал | 1.4 |
| G4 | **Prose system** для decision packets пуст | Разрыв между «что показывает» и «что производит» | 1.5 |
| G5 | Нет регистра для **AI-authored** текста (vs цитата vs оператор) | В 2026 — определяющий SOTA-признак для AI-продуктов | 1.6 |
| G6 | **i18n** под украинско-русскую реальность не специфицирован | Ломается плюрализация, типографика, даты, валюта | 1.7 |

### 1.3. Шесть best-in-class примитивов (Wave 2 scope)

| # | Примитив | Конкурентный анализ | Фаза |
|---|---|---|---|
| B1 | Time-as-primitive | Ни одного govtech-инструмента | 2.1 |
| B2 | Provenance-on-hover | Observable флиртует, никто не коммитится | 2.2 |
| B3 | Policy diff (каузальный) | Чистое поле | 2.3 |
| B4 | Counterfactual layer | Никто | 2.4 |
| B5 | Native bureaucratic rendering | Все GPT-обёртки рендерят generic markdown | 2.5 |
| B6 | Trust view | Никто | 2.6 |

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
- Wave 2: **2.3, 2.4, 2.5, 2.6** — последовательно (каждая зависит от 2.1 и 2.2).

### 3.3. Feature flags

Каждая фаза ≥ 1.2 вводит один feature flag в `src/app/providers/feature-flags` формата `design.wave{N}.phase{Y}.{slug}`:
- По умолчанию `off` в production.
- `on` в development и staging после acceptance.
- Постепенный rollout через manifest после 14 дней стабильности.
- Flag удаляется через релиз после 100% rollout — не остаётся as dead code.

---

# Волна 1 — SOTA Gap Closure

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

```
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
- `A11Y_CONTRAST.md` — таблица всех пар `(background-token, foreground-token)` с contrast ratio, проверенная автоматизированной утилитой (см. Testing).
- `GLYPH_SPECIFICATION.md` — сетка 5×5, stroke-width 1.25–1.5, список всех 10 радикалов с геометрическим описанием.
- `UNCERTAINTY_LANGUAGE.md` — 7 паттернов с SVG-превью и указанием каких именно chart-компонентов затрагивает.
- `MOTION.md` — `--motion-duration-*` и `--motion-ease-*` tokens, правила для reduced-motion, конкретные transitions для каждого state change.
- Все 5 ADR-ов следуют шаблону `docs/adr/_template.md` (если нет — создать).

### Acceptance criteria

- [ ] Все 11 файлов существуют, прошли `markdownlint`.
- [ ] `A11Y_CONTRAST.md` проверен `axe-core` CLI на 100% пар — нет пропусков.
- [ ] 5 ADR approved (git commit с тегом `[adr-approved]`).
- [ ] В `docs/README.md` добавлена секция `brand/` и `compliance/` с ссылками.
- [ ] Создан `.cursor/rules/design-system.mdc` (или эквивалент в `CLAUDE.md`), ссылающийся на эти документы, чтобы будущие генерации не уходили в сторону.

### Testing

- Скрипт `tools/design/check-contrast.ts` — парсит `A11Y_CONTRAST.md`, прогоняет через `wcag-contrast` или `@axe-core/utils`, падает если ratio < 4.5 для normal text / 3.0 для large.
- Markdown-lint + link-check (`lychee`) в CI.

### Risks

| Риск | Mitigation |
|---|---|
| ADR-ы уходят в абстракцию без привязки к коду | Каждый ADR завершается секцией «Concrete impact» со списком файлов, которые будут созданы/изменены |
| Contrast matrix устаревает при смене токенов | Генерировать из `designTokens.ts` автоматически, не руками |

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

```
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

```
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

```
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
- [ ] `logo-janus.svg` в 16 px узнаётся в favicon — blind test на 5 коллегах ≥ 4/5.
- [ ] `ProvenanceStrip` заменил eyebrow в 3 местах без регрессий (visual regression test).
- [ ] `EvidenceSigil` детерминирован: `render(hash_A) === render(hash_A)` в snapshot-тесте, `render(hash_A) !== render(hash_B)` в 100/100 случаев.
- [ ] `glyph-vocabulary.ts` покрыт 100% 18-словарного домена, unit-test проверяет соответствие.
- [ ] ESLint-правило `no-raw-emoji-in-jsx` работает (как замена попыткам вставить `⊙` напрямую).

### Testing

- Storybook + visual regression (Playwright + Percy или Chromatic).
- `.a11y.test.tsx` для `ProvenanceStrip` и `Glyph` (axe-core).
- Unit-test `EvidenceSigil` определённость: 1000 random bundles, уникальность ≥ 99.9%.
- `pnpm test:glyph-vocabulary` — скрипт, парсит `docs/brand/GLYPH_SPECIFICATION.md`, сравнивает с `glyph-vocabulary.ts`, падает при расхождении.

### Risks

| Риск | Mitigation |
|---|---|
| Глифы засоряют интерфейс | `glyph-vocabulary.ts` — whitelist; PR добавляющий глиф в новое место требует design-review |
| `EvidenceSigil` даёт коллизии хэша | 48-bit entropy минимум; periodic collision audit |

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

```
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

| Component | Change |
|---|---|
| `ConfidenceDial` | Использует `uncertaintyTokens`; добавляет prop `disputed?: boolean` |
| `ConfidenceGauge` | То же + pattern-fill для estimated regions |
| `ForestPlot` | Confidence intervals теперь gradient-filled (была solid line) |
| `GradedErrorBar` | Использует `uncertaintyTokens.estimated.pattern` |
| `UncertaintyDisplay` | Становится dispatcher: принимает тип (`band` \| `fan` \| `dotplot` \| `hops`), рендерит соответствующий |

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
- [ ] Pattern-fills различимы для deuteranope / protanope / tritanope (Coblis simulation in Storybook).

### Testing

- Visual regression в Storybook (3 themes × 3 densities × 3 color-blind simulations).
- Unit: quantile correctness, reduced-motion fallback.
- Integration: e2e Playwright сценарий «открыл Run Detail → увидел fan chart → переключил режим reduced-motion → увидел static fan».

### Risks

| Риск | Mitigation |
|---|---|
| Backend не готов расширить контракт | Clientsidе имеет fallback adapter: `legacy_number → { point: legacy_number }` |
| HOPs раздражает — слишком быстро/медленно | Hullman default 2.5 fps, user preference в Settings |
| Pattern-fills «шумные» | Opacity 0.18 по умолчанию; только внутри CI-band, не на основной линии |

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

```
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
└── color-blind-simulation.spec.ts    — Coblis + axe

policy-engine/docs/compliance/
├── VPAT.md                           — full document
├── A11Y_CONTRAST.md                  — auto-generated from tokens
└── A11Y_AUDIT_2026Q2.md              — external audit report (scheduled)

tools/design/
├── check-contrast.ts                 — pre-commit hook
├── check-reduced-motion.ts           — grep all transitions, flag non-respecting
└── check-color-blind.ts              — axe + Coblis CLI
```

**CSS additions** (в `styles.css` или эквиваленте):

```css
@media (prefers-contrast: more) {
  :root {
    --ink: #000000;
    --surface: #ffffff;
    /* all borders +50% opacity */
  }
  .glyph { stroke-width: 2; }
  .provenance-strip .glyph + .glyph { margin-inline-start: 0.75ch; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
  .hops { display: none; }
  .hops + .hops-static-fallback { display: block; }
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
- [ ] Coblis simulation — все сигнальные различения остаются читаемыми в deuteranope/protanope/tritanope.
- [ ] Pre-commit hook `check-contrast` работает, падает на PR с плохими парами.

### Testing

- CI: axe-core на Storybook + 5 ключевых маршрутов.
- Weekly: full WCAG 2.2 AA automated report → dashboard.
- Quarterly: external audit (бюджет зарезервировать).

### Risks

| Риск | Mitigation |
|---|---|
| Contrast enforcement ломает кастомные визуальные решения | Opt-out через `data-a11y-exempt` c обязательным комментарием-обоснованием |
| VPAT устаревает между релизами | Auto-regenerate из тестов + manual review quarterly |

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

```
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
  compact:     { space: 0.75, fontStep: -1, rowHeight: 0.85 },
  condensed:   { space: 0.5, fontStep: -2, rowHeight: 0.7 },
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

| Риск | Mitigation |
|---|---|
| Dark theme требует пересчёта rim-light во всех компонентах | CSS custom property `--rim-light-color` — один источник правды |
| Condensed mode ломает table layouts | Явные min-width'ы в DataTable + horizontal scroll |
| Двойные CI-прогоны × 3 density удорожают testing | Выборочно: только критические смоки в compact/condensed, full suite — в comfortable |

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

```
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
.prose > p + p { margin-block-start: 1em; text-indent: 0; }
.prose blockquote {
  font-family: "Instrument Serif";
  font-style: italic;
  border-inline-start: 2px solid var(--gold);
  padding-inline-start: 1.5ch;
  color: color-mix(in oklch, var(--ink), transparent 15%);
}
.prose .definition-term { font-variant: small-caps; letter-spacing: 0.05em; }
.prose .footnote-ref { font-feature-settings: "sups"; color: var(--teal); }
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
@page { margin: 2.5cm 2cm; size: A4; }
@media print {
  nav, aside.dashboard-shell, .reading-view-toggle { display: none; }
  .prose { max-width: none; }
  h1, h2, h3 { break-after: avoid; }
  .fan-chart, .uncertainty-band { break-inside: avoid; }
  .provenance-strip::after { content: " [" attr(data-glyph-summary) "]"; }
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

| Риск | Mitigation |
|---|---|
| Margin notes не помещаются на узких экранах | Responsive: < 1400px → inline footnote; > 1400 → margin |
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

```
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

| Регистр | Источник | Визуал | Screen reader |
|---|---|---|---|
| `citation` | Цитата из закона/источника | `Instrument Serif italic`, тонкий `--gold` left-border (2px) | «Quoted text from {source}» |
| `human` | Написал оператор-человек | `Manrope 400`, без маркера | (default) |
| `drafter` | AI-агент Drafter | `--teal` left-border (1px), глиф `⊙` в начале параграфа | «AI-generated by Drafter» |
| `formalizer` | AI-агент Formalizer | `--slate` left-border, глиф `≔` | «AI-generated by Formalizer» |
| `critic` | AI-агент Critic | `--ember` left-border, глиф `⋌` | «AI review by Critic» |

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
      "reviewed_by_human": false
    }
  ]
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

| Риск | Mitigation |
|---|---|
| Слишком «шумный» UI с 4 разными border'ами | Subtle mode по умолчанию, границы 1px, off в reading view |
| Backend не готов отдавать author | Default `"human"`, адаптер на клиенте для legacy блоков |
| Citation source broken | `sourceRef` optional, UI graceful degrade |

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

```
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
  "policy.applied": "Політику <b>{name}</b> застосовано о {time, time, short}"
}
```

**CSS fix:**

```css
/* Plex Mono cyrillic metrics компенсация */
:lang(uk), :lang(ru) {
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

| Риск | Mitigation |
|---|---|
| Авто-вставка NBSP ломает существующие переводы | Opt-in per-string через конфиг; постепенная миграция |
| ICU plural усложняет разработку | Краткий styleguide + ESLint-hint |

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
- [ ] Storybook deployed на public URL (для stakeholder review).

---

# Волна 2 — Best-in-class primitives

> Начинать только после gate (см. §3.1).

## Фаза 2.0 — Provenance law foundations

**Длительность:** 2 недели.
**Тезис:** Provenance law (B2) — это сквозной инвариант, который должен быть установлен **до** попытки поменять UI. Без backend-контракта и ESLint-правила любая реализация будет частичной.

### Preconditions

- Wave 1 gate passed.

### Scope

- Backend-контракт: каждое числовое поле несёт `lineage_id`.
- ESLint-правило `policyos/quantity-must-be-wrapped`.
- Миграционный план для ~3000 мест, где в JSX используются числа.
- `<Quantity>` wrapper spec.
- Lineage API endpoint spec.

### Deliverables

```
policy-engine/docs/adr/ADR-043-provenance-law.md  — финализация
policy-engine/src/runtime/api/schema/quantity.py  — Pydantic модели
policy-engine/src/runtime/api/routes/lineage.py    — GET /api/v1/lineage/{lineage_id}

frontend/runtime-dashboard/src/shared/ui/quantity/
├── Quantity.tsx                     — skeleton (full impl в 2.2)
├── Quantity.test.tsx
├── Quantity.stories.tsx
└── quantity.types.ts

frontend/runtime-dashboard/eslint-rules/
├── quantity-must-be-wrapped.ts
└── quantity-must-be-wrapped.test.ts

tools/design/
└── migrate-numbers-to-quantity.ts    — codemod helper
```

### Backend contract

```jsonc
// Everywhere a number appears in a response:
{
  "effect_size": {
    "point": 0.23,
    "lineage_id": "lin_abc123"
    // + uncertainty fields from 1.2
  }
}

// Lineage endpoint:
GET /api/v1/lineage/{lineage_id} →
{
  "id": "lin_abc123",
  "nodes": [
    { "id": "n1", "kind": "dataset", "label": "QES 2024 Q3", "timestamp": "..." },
    { "id": "n2", "kind": "transformation", "label": "Winsorize 1-99%", "parent": "n1" },
    { "id": "n3", "kind": "model", "label": "DoubleML v2.1", "parent": "n2" },
    { "id": "n4", "kind": "agent", "label": "Formalizer@1.4", "parent": "n3" }
  ],
  "hash": "sha256:...",
  "verification_status": "verified" | "pending" | "disputed"
}
```

### Acceptance criteria

- [ ] ADR-043 approved, merged.
- [ ] Lineage endpoint специфицирован в OpenAPI schema, types сгенерированы.
- [ ] ESLint-правило работает в `warn` режиме; ~3000 warnings видны.
- [ ] Codemod migrate-numbers мигрирует 50% случаев автоматически (simple cases).

### Risks

| Риск | Mitigation |
|---|---|
| Backend не готов отдать lineage для всех чисел | Fallback `lineage_id: "untraced"` + TODO-ticket per endpoint; migration план на 4 недели |
| 3000 warnings демотивируют | Phased rollout: warn → error через 2 релиза, группами по feature |

### Effort

- Backend schema + endpoint: 1 неделя.
- ESLint rule + codemod: 3 дня.
- Migration plan: 2 дня.

---

## Фаза 2.1 — Time-as-primitive (B1)

**Длительность:** 4 недели.
**Тезис:** единственный примитив, который делает PolicyOS несводимым к другим govtech-инструментам. Оператор проматывает политику как видеоряд, каждый график ре-рендерится для выбранного момента.

### Preconditions

- Фаза 2.0 завершена (lineage API готов — для trust score по timestamp'у).
- Фаза 1.2 завершена (uncertainty charts умеют принимать `asOf`).

### Scope

- `TemporalCursorProvider` как глобальный state.
- `TemporalScrubber` UI в Atlas shell header.
- `withTemporalCursor` HOC для синхронизации графиков.
- Backend contract: `as_of` параметр на time-sensitive endpoints.
- Keyboard shortcuts + screen reader announcements.
- URL deep-linking времени.

### Deliverables

```
frontend/runtime-dashboard/src/app/providers/
├── TemporalCursorProvider.tsx
├── TemporalCursorProvider.test.tsx
└── useTemporalCursor.ts

frontend/runtime-dashboard/src/shared/ui/temporal/
├── TemporalScrubber.tsx              — UI в header
├── TemporalScrubber.test.tsx
├── TemporalScrubber.a11y.test.tsx
├── TemporalScrubber.stories.tsx
├── TemporalCursorMarker.tsx          — вертикальная линия для графиков
├── TemporalLegend.tsx                — observed vs simulated indicator
├── useTemporalRange.ts
└── withTemporalCursor.tsx            — HOC

frontend/runtime-dashboard/src/api/
├── hooks/
│   ├── useTemporalQuery.ts           — wrapper React Query c as_of
│   └── useTemporalRange.ts           — определение allowed range для run
└── queryKeys.ts                      — include as_of in keys

policy-engine/src/runtime/api/
├── routes/runs.py                    — добавить as_of query param
├── routes/metrics.py                 — то же
├── routes/evidence.py                — то же
└── routes/decisions.py               — то же
```

### UI spec

- **Расположение:** горизонтальный scrubber под верхним rail'ом Atlas shell'а, height 32 px.
- **Индикаторы:** тонкая линия-timeline с маркерами событий (run starts, policy changes); сплошная часть = past (observed), пунктирная = future (simulated); «сейчас» = вертикальная линия `--gold`.
- **Взаимодействие:**
  - drag → скрабинг (60 fps);
  - `←/→` → ±1 day step;
  - `Shift+←/→` → ±1 week;
  - `Alt+←/→` → ±1 hour;
  - `Home` → earliest; `End` → latest; `N` / `Now` → «сейчас».
- **Screen reader:** при изменении `aria-live="polite"` объявляет `"Time cursor moved to April 15, 2026"`.

### Backend contract

Добавить `as_of: datetime` query param на endpoints:
- `GET /api/v1/runs/{id}?as_of=...`
- `GET /api/v1/runs/{id}/metrics?as_of=...`
- `GET /api/v1/evidence/bundles/{id}?as_of=...`
- `GET /api/v1/decisions/{id}?as_of=...`

Поведение:
- Если `as_of` в прошлом — возвращает snapshot того момента.
- Если `as_of` в будущем (для симулированных) — возвращает simulated state с marker `is_simulated: true`.
- Если `as_of` вне допустимого range — 422 с описанием `valid_range`.

Additive: без `as_of` — текущее поведение. DB-индексы на `timestamp` колонки обязательны (DBA task).

### URL deep-linking

- Формат: `?t=2026-04-15T12:00:00Z` сохраняется в URL.
- `<Link>` компоненты вне TemporalScope обнуляют `t`.

### Acceptance criteria

- [ ] Скрабинг на 60 fps в desktop Chrome; ≤ 30 fps acceptable на mobile.
- [ ] Изменение cursor re-fetches данные с debounce 150 ms.
- [ ] Все графики на Run Detail странице синхронно ре-рендерятся.
- [ ] `prefers-reduced-motion` → скрабинг заменяется на snap-to-point.
- [ ] Keyboard-only navigation работает (все 10 shortcuts).
- [ ] Screen reader корректно объявляет при каждом изменении (throttled 500 ms).
- [ ] Deep-link URL shareable — копирование URL и открытие воспроизводит state.

### Testing

- Unit: `TemporalCursorProvider` state transitions.
- E2E: «открыть run → скрабить → увидеть изменение CI → копировать URL → open in incognito → увидеть тот же state».
- Performance: Chrome DevTools performance profile на 60 fps.
- A11y: keyboard-only journey пройдена axe + manual VoiceOver.

### Risks

| Риск | Mitigation |
|---|---|
| Backend не справляется с as_of для всех endpoints | Phased rollout: сначала `/runs/{id}`, потом metrics, потом evidence. Feature flag per endpoint. |
| DB без time-series индексов становится медленной | DBA task: установить indices на `created_at`, `updated_at`, `valid_from/valid_to`. Audit slow queries. |
| «Будущее» — сложная симуляция | В Wave 2.1 only past/present; future (simulated) в Wave 2.4 (counterfactual layer). |

### Effort

- Provider + UI: 1 неделя.
- HOC + chart integration: 1 неделя.
- Backend `as_of` rollout: 1.5 недели (параллельно).
- Testing + polish: 0.5 недели.

---

## Фаза 2.2 — Provenance-on-hover (B2)

**Длительность:** 3 недели.
**Тезис:** PolicyOS превращает «verifiable evidence bundles» в сквозной UX-закон: любое число в UI один hover-клик от полного графа своего происхождения.

### Preconditions

- Фаза 2.0 (lineage API + ESLint rule).
- Фаза 2.1 (интеграция с temporal cursor: lineage за моментом времени).

### Scope

- Полная реализация `<Quantity>` (из 2.0 был skeleton).
- `<ProvenancePopover>` с mini lineage graph.
- Миграция всех числовых значений в JSX через codemod + manual review.
- ESLint-правило переводится `warn → error`.

### Deliverables

```
frontend/runtime-dashboard/src/shared/ui/quantity/
├── Quantity.tsx                     — full implementation
├── Quantity.test.tsx
├── Quantity.a11y.test.tsx
├── Quantity.stories.tsx
├── ProvenancePopover.tsx
├── ProvenancePopover.test.tsx
├── ProvenancePopover.a11y.test.tsx
├── ProvenanceMiniGraph.tsx          — reuse LineageGraph but compact
├── ProvenanceMiniGraph.test.tsx
├── useLineage.ts                    — React Query hook
└── index.ts

frontend/runtime-dashboard/eslint-rules/
└── quantity-must-be-wrapped.ts      — warn → error
```

### API

```tsx
<Quantity
  value={number}
  lineageId={string}
  unit?={string}                     // "%", "B ₴", "days"
  format?="decimal" | "percent" | "currency" | "scientific" | "compact"
  precision?={number}
  ciLower?={number}                  // shows ± from 1.2
  ciUpper?={number}
  disputed?={boolean}
  asOf?={ISO8601}                    // передаётся из TemporalCursor
/>
```

### UX spec

- **Hover:** через 150 ms появляется popover с mini lineage graph.
- **Focus (keyboard):** aria-describedby + `Enter` / `Space` открывает popover.
- **Mini graph:** макс 6 узлов по высоте, кликабельные, при клике на узел — deep-dive modal с full lineage.
- **«Traceless»:** если `lineage_id === "untraced"` — значение рендерится с warning-индикатором (маленький `⊘`).

### Миграция

- ESLint в `error` mode после того как codemod + manual review устранили 100% случаев.
- PR-check: невозможно merge number-in-JSX без `<Quantity>`.

### Acceptance criteria

- [ ] 100% числовых значений в UI обёрнуты в `<Quantity>` (ESLint enforces).
- [ ] Popover появляется за ≤ 200 ms от hover/focus start.
- [ ] Mini graph читается на 320 px ширину экрана.
- [ ] Screen reader описание: `"Effect size 0.23, 95 percent confidence interval 0.15 to 0.31, provenance available"`.
- [ ] Deep-dive modal показывает full lineage с возможностью download raw sources.
- [ ] Performance: 100+ `<Quantity>` на странице без visible lag.

### Backend contract

Уже зафиксирован в 2.0. В 2.2 — только консьюминг.

### Risks

| Риск | Mitigation |
|---|---|
| Perf regression при 100+ Quantity на странице | Lazy-render popover content (только при hover, not pre-fetch) |
| `lineage_id: untraced` режет UX | Roadmap: в 6 месяцев все endpoints возвращают lineage; warning как driver для backend team |
| Popover конфликтует с existing tooltips | Единая система — только Quantity owns popover'ы для numbers |

### Effort

- `Quantity` + popover full impl: 1.5 недели.
- Миграция + codemod refinement: 1 неделя.
- Testing + perf: 0.5 недели.

---

## Фаза 2.3 — Policy diff (B3)

**Длительность:** 3 недели.
**Тезис:** Git изобрёл код-дифф. Политике нужен каузальный дифф — визуальный язык сравнения двух версий policy не по словам, а по эффекту.

### Preconditions

- Фаза 2.1 (temporal cursor работает — нужно для "diff at time T").
- Фаза 2.2 (каждая метрика имеет lineage).

### Scope

- Split-pane layout для двух policy versions.
- Causal delta strip между панелями.
- HistogramDelta, IdentifiabilityTrajectory, GovernanceRadarDiff, BudgetFlow.
- Command palette action.
- Deep-link URL `/compare/:runA/:runB`.

### Deliverables

```
frontend/runtime-dashboard/src/features/runs/compare/
├── PolicyDiffView.tsx
├── PolicyDiffView.test.tsx
├── PolicyDiffView.stories.tsx
├── PolicyDiffLayout.tsx             — split-pane
├── CausalDeltaStrip.tsx             — центральная полоса
├── delta-widgets/
│   ├── HistogramDelta.tsx           — распределение импакта
│   ├── IdentifiabilityTrajectory.tsx
│   ├── GovernanceRadarDiff.tsx
│   ├── BudgetFlowDiff.tsx
│   └── ProvenanceDiff.tsx
├── useDiffData.ts
└── route.tsx                        — /compare/:runA/:runB
```

### UX spec

- **Layout:** две равных панели слева/справа, каждая — упрощённый Run Detail.
- **Между ними:** вертикальная полоса 120 px шириной с causal deltas, отсортированными по magnitude.
- **Sync:** скролл панелей синхронизирован (toggle).
- **Time:** единый TemporalCursor применяется к обеим.
- **Deep-link:** `?t=...&compare=runA,runB`.

### Acceptance criteria

- [ ] Открытие diff view для двух реальных runs даёт осмысленное сравнение за ≤ 2 сек.
- [ ] Quantile-histogram delta корректно вычисляет и визуализирует.
- [ ] Governance radar diff различим в колор-блайнд.
- [ ] Deep-link воспроизводит state.
- [ ] Command palette: `Compare A with B` triggers диалог выбора runs.

### Backend contract

- Новый endpoint: `GET /api/v1/runs/compare?a={id}&b={id}&as_of=...` возвращает pre-computed deltas (для performance).
- Если pre-compute недоступен — frontend делает two parallel fetches и вычисляет client-side.

### Risks

| Риск | Mitigation |
|---|---|
| Diff для очень разных runs бесполезен | Pre-flight check: если runs не сопоставимы (разные problem frames) — warning + graceful render |
| Вычисление deltas медленное | Backend pre-computes popular pairs (cache); fallback client-side для остальных |

### Effort

- Layout + delta strip: 1 неделя.
- 5 delta-widgets: 1.5 недели.
- Backend compare endpoint + integration: 0.5 недели.

---

## Фаза 2.4 — Counterfactual layer (B4)

**Длительность:** 3 недели.
**Тезис:** интерфейс работает в двух режимах одновременно — реальном и контрфактуальном. Для системы, чей смысл в counterfactual reasoning, это единственно честный рендер.

### Preconditions

- Фаза 2.1 (temporal cursor поддерживает future = simulated).
- Фаза 2.2 (lineage различает observed vs counterfactual).
- Фаза 1.2 (uncertainty charts поддерживают `counterfactual` prop).

### Scope

- `CounterfactualProvider` с глобальным state.
- `CounterfactualToggle` в Atlas shell.
- Двойные селекторы в formulars.
- Backend contract для CF-endpoints.
- Сквозная дисциплина окраски.

### Deliverables

```
frontend/runtime-dashboard/src/app/providers/
├── CounterfactualProvider.tsx
└── CounterfactualProvider.test.tsx

frontend/runtime-dashboard/src/shared/ui/counterfactual/
├── CounterfactualToggle.tsx
├── CounterfactualBadge.tsx           — маленький индикатор «CF mode on»
├── DualSelector.tsx                  — fact + counterfact
├── DualSlider.tsx
├── DualInput.tsx
└── useCounterfactualState.ts

frontend/runtime-dashboard/src/features/whatif/   (exists)
└── интеграция с глобальным CF provider'ом

policy-engine/src/runtime/api/
└── CF parameter on metric endpoints (?cf=1)
```

### UX spec

- **Toggle:** кнопка в header с глифом `⋌`, tooltip «Show counterfactual reality».
- **Active state:** across all UI:
  - Числа: `<Quantity counterfactualValue={...} />` показывает оба.
  - Графики: добавляется пунктирная линия для CF.
  - Карточки: второй «слой» под основной.
  - Различия между fact/CF подсвечиваются `--gold`.
- **Default:** off.

### Backend contract

```jsonc
GET /api/v1/runs/{id}/metrics?cf=1 →
{
  "effect_size": {
    "actual": { "point": 0.23, "lineage_id": "..." },
    "counterfactual": {
      "point": 0.17,
      "lineage_id": "...",
      "assumption": "If rate cut by 25 bps at 2026-Q2"
    }
  }
}
```

### Acceptance criteria

- [ ] Toggle мгновенно переключает (≤ 200 ms) все видимые значения.
- [ ] CF-режим сохраняется в URL (`?cf=1`).
- [ ] Disabled для runs, которые не имеют CF scenarios.
- [ ] Разница fact/CF доступна screen reader'ам.
- [ ] Performance: включение CF не удваивает data fetching (batched).

### Risks

| Риск | Mitigation |
|---|---|
| Cognitive overload | Onboarding tooltip при первом включении; default off |
| CF для всех runs не считается бэком | Per-run flag `has_counterfactual: bool` на API |
| Colour collision `--gold` vs pending | В CF-mode pending использует `⧗` с другим оттенком; formal rule в `COMPOSITION_RULES.md` |

### Effort

- Provider + toggle: 3 дня.
- DualSelector family: 3 дня.
- Backend contract + integration: 1 неделя.
- Sweep через existing charts/cards: 1 неделя.

---

## Фаза 2.5 — Native bureaucratic rendering (B5)

**Длительность:** 4 недели.
**Тезис:** украинская и ЕС политика происходит через специфические жанры. PolicyOS рендерит их нативно — и это то, что делает AI-систему легитимной в глазах бюрократа.

### Preconditions

- Фаза 1.5 (prose system).
- Фаза 1.6 (authored text — нужно для «какие поля model, какие evidence»).
- Внешняя валидация: юрист-консультант на 2 дня для проверки шаблонов.

### Scope

Четыре жанра: **постанова КМУ**, **законопроект**, **експертний висновок**, **аналітична записка**.

Для каждого:
- Нативный шаблон по ДСТУ / офіційним вимогам.
- Авто-заполнение из decision packet data.
- Epistemic transparency map.
- Export в PDF с pixel-perfect шапкой.

### Deliverables

```
frontend/runtime-dashboard/src/features/artifacts/renderers/
├── PostanovaKMURenderer.tsx
├── PostanovaKMURenderer.test.tsx
├── PostanovaKMURenderer.stories.tsx
├── ZakonoproektRenderer.tsx
├── ZakonoproektRenderer.test.tsx
├── ExpertVysnovokRenderer.tsx
├── ExpertVysnovokRenderer.test.tsx
├── AnalitichnaZapyskaRenderer.tsx
├── AnalitichnaZapyskaRenderer.test.tsx
├── shared/
│   ├── BureaucraticHeader.tsx
│   ├── BureaucraticNumbering.tsx     — Розділ/Глава/Стаття
│   ├── EpistemicLegend.tsx           — карта authored blocks
│   ├── SealPlaceholder.tsx
│   └── bureaucratic-tokens.ts
└── pdf/
    ├── generatePDF.ts                 — Puppeteer или react-pdf
    └── templates/                     — HTML-шаблоны для PDF

frontend/runtime-dashboard/public/bureaucracy/
├── tryzub.svg                        — герб (public domain)
├── kmu-seal-placeholder.svg
├── rada-seal-placeholder.svg
└── stamps/                           — mock-ups of стандартних штампів

policy-engine/docs/brand/BUREAUCRATIC_RENDERING.md
```

### UX spec

- В Decision Workspace: toggle «Render as…» с dropdown 4 жанров.
- Каждый рендер имеет:
  - Правильную шапку (герб, назва органу, реквізити).
  - Нумерацию Розділ/Глава/Пункт согласно жанру.
  - Epistemic legend на титульной странице: `🟢 заповнене свідченнями (X% тексту) / 🟡 сгенеровано моделлю (Y%) / ⚫ заповнене оператором (Z%)` — использует глифы §1.1, не emoji.
  - AuthorBadge per block из 1.6.

### Backend contract

- Endpoint: `POST /api/v1/artifacts/{packet_id}/render?genre=postanova_kmu` → возвращает `rendered_document` с структурированными блоками.
- PDF export: `GET /api/v1/artifacts/{packet_id}/export.pdf?genre=...`.

### Acceptance criteria

- [ ] Юрист-консультант подписал 4 шаблона как соответствующие формальным требованиям.
- [ ] PDF-экспорт pixel-perfect в Chrome, ≥ 95% в Firefox/Safari.
- [ ] Epistemic legend корректна для 10 реальных decision packets.
- [ ] Все шапки используют public-domain / licensed assets.
- [ ] Reading view (1.5) работает для bureaucratic render.

### Risks

| Риск | Mitigation |
|---|---|
| Юридическое обвинение в подделке официальной формы | Явный watermark «Generated by PolicyOS / Draft only» на всех рендерах; not actual state documents |
| ДСТУ обновляются | Versioned templates: `PostanovaKMURenderer.v1.tsx` |
| Assets лицензирование | Аудит перед PR, только public domain или CC0 |

### Effort

- 4 renderers × ~1 неделя each, параллелизуется.
- Shared components: 3 дня.
- PDF pipeline: 1 неделя.
- Legal review: 2 дня.

---

## Фаза 2.6 — Trust view (B6)

**Длительность:** 2 недели.
**Тезис:** доверие не прячется в отдельной вкладке; оно — режим рендеринга, который включается когда нужен аудит.

### Preconditions

- Фаза 2.2 (lineage на каждое число).
- Фаза 1.6 (author registry).

### Scope

- `TrustViewProvider` + toggle.
- Расширение всех компонентов под trust-view display.
- Diacritic modifiers для глифов.
- Hash + timestamp inline display.
- Keyboard shortcut.

### Deliverables

```
frontend/runtime-dashboard/src/app/providers/
├── TrustViewProvider.tsx
└── useTrustView.ts

frontend/runtime-dashboard/src/shared/ui/trust-view/
├── TrustViewToggle.tsx
├── TrustViewBadge.tsx
├── TrustMetadata.tsx                — hash + timestamp + verifier
├── DisputeBadge.tsx
├── VerificationStatus.tsx
└── trust-view.css                   — global CSS для [data-trust-view="on"]

frontend/runtime-dashboard/src/shared/ui/quantity/Quantity.tsx
  — расширяется: в trust-view inline lineage summary + hash chip
```

### UX spec

- **Toggle:** `Cmd+Shift+T` или кнопка в header.
- **Active state:**
  - Each `<Quantity>` показывает tiny hash chip `sha:abc...` под числом.
  - `<ProvenanceStrip>` разворачивается в 2 строки: верхняя — глифы, нижняя — hashes.
  - `<AuthoredText>` показывает inline author + timestamp.
  - Глифы получают diacritics (точки/штрихи).
  - Charts: confidence intervals подписаны CI method (bootstrap/analytic/bayesian).
- **Visual register:** trust-view не меняет layout — только добавляет overlay.

### Backend contract

- Hash на каждое число уже доступно (2.0 `lineage.hash`).
- Дополнительно: `verification_status`, `verified_by`, `verified_at` на lineage nodes.

### Acceptance criteria

- [ ] Toggle работает глобально.
- [ ] Trust view не ломает layout (все тесты visual regression проходят).
- [ ] Performance: включение не добавляет > 50 ms к render.
- [ ] Hash chips кликабельны — открывают deep-dive modal.
- [ ] Keyboard-only navigation сохраняется.

### Risks

| Риск | Mitigation |
|---|---|
| Overlay слишком шумный | Плотность hashes адаптивна к density-mode (1.4); в condensed — только на click |
| Hashes раздувают экран | Truncate `sha:abc...` с expand-on-hover |

### Effort

- Provider + toggle: 2 дня.
- Quantity/ProvenanceStrip/AuthoredText extensions: 3 дня.
- CSS cascade + tests: 3 дня.
- Integration + polish: 2 дня.

---

## Фаза 2.7 — System polish

**Длительность:** 2 недели.
**Тезис:** оставшиеся системные артефакты, без которых дизайн-система не может претендовать на best-in-class: print, CLI, motion, categorical palettes, OG/email templates.

### Scope

- Print/PDF stylesheet (уточнения поверх 1.5).
- CLI styleguide для `@polisyos/cli`.
- Motion spec полный (2.0 был foundation).
- Anti-patterns catalog финализация.
- Categorical-8 и Categorical-12 палитры.
- Small multiples компонент.
- OG card / email templates.

### Deliverables

```
frontend/runtime-dashboard/src/styles/print.css                          — refinement
policy-engine/docs/brand/
├── CLI_STYLEGUIDE.md
├── MOTION.md                                                            — expanded
├── COMPOSITION_RULES.md                                                 — finalized
├── EMAIL_TEMPLATES.md
└── SOCIAL_TEMPLATES.md

frontend/runtime-dashboard/src/shared/charts/
├── categorical-palettes.ts                                              — 8 + 12
├── SmallMultiples.tsx
└── SmallMultiples.stories.tsx

frontend/runtime-dashboard/src/features/export/og-card/
├── OGCard.tsx                                                           — HTML → image via Satori
├── OGCard.stories.tsx
└── generate-og.ts

packages/cli/src/                                                        — если есть monorepo
└── styleguide-utils/                                                    — ANSI colors, ASCII glyphs
```

### Acceptance criteria

- [ ] Print: 5 decision packets напечатаны без артефактов.
- [ ] CLI: `polisyos run --verbose` имеет tokenized output.
- [ ] OG cards: auto-generated для 3 shareable run URLs.
- [ ] Categorical-8 различим в Coblis simulation.
- [ ] Small multiples работает на 8 regions × 12 sectors без lag.

### Effort

- 2 weeks total, mostly parallel sub-tasks.

---

## 4. Success metrics

| Слой | Метрика | Целевое значение | Замер |
|---|---|---|---|
| **Wave 1** | | | |
| Бренд | Blind recognition test | ≥ 80% узнают Janus-glyph как PolicyOS | After 1.1 |
| A11y | WCAG 2.2 AA automated audit | 0 blockers | After 1.3 |
| Uncertainty | % metric-рендеров с CI | ≥ 90% | After 1.2 |
| Theme | Storybook coverage | 100% компонентов × 3 themes × 3 densities | After 1.4 |
| Prose | Reading view usage | ≥ 30% operators открывают ≥ 1×/week | 3 months after 1.5 |
| Authorship | Text coverage | 100% narrative blocks have `author` | After 1.6 |
| i18n | Plural/typography correctness | 100% ICU + 100% NBSP rules | After 1.7 |
| **Wave 2** | | | |
| Provenance law | % numbers wrapped | 100% (ESLint error) | After 2.2 |
| Time cursor | Endpoints supporting `as_of` | ≥ 90% time-sensitive | After 2.1 |
| Policy diff | Diff view usage | ≥ 20% reviewers use ≥ 1×/week | 3 months after 2.3 |
| CF layer | Coverage | ≥ 80% decision packets offer CF | After 2.4 |
| Bureaucratic | Genres supported | ≥ 4 | After 2.5 |
| Trust view | Audit flow time | −40% vs current audit UX | After 2.6 |

---

## 5. Risks & mitigations

| Level | Risk | Mitigation |
|---|---|---|
| **Program** | Wave 2 стартует без закрытого Wave 1 | Gate §3.1 с жёстким checklist |
| **Program** | Один инженер перегорает на 32 недели | Планировать каждую 8-ю неделю как light (docs/refactor) |
| **Architecture** | Provenance law ломает миллион мест | Phased warn → error + codemod (2.0) |
| **Architecture** | `as_of` требует DB-миграций | DBA task в 2.1, начать заранее |
| **Design** | Глифы «засоряют» | 10-лимит + whitelist (1.1) + composition rules (1.0) |
| **Design** | Maskot или bureaucratic render срывается в китч | Non-goals §2 + design-review gate |
| **Backend** | Coordination с policy-engine медленна | Contracts как ADR в начале каждой фазы |
| **Legal** | Bureaucratic genres под угрозой подделки формы | Watermark + legal review (2.5) |
| **Performance** | Temporal scrubbing не 60 fps | Perf budget в CI (2.1), Lighthouse regression checks |
| **A11y** | Новые компоненты ломают a11y | `.a11y.test.tsx` обязателен в PR checklist |

---

## 6. Owner matrix

| Область | Артефакты | Ответственный слой |
|---|---|---|
| Бренд, глифы, sigil | `shared/brand/*`, `public/atlas/*`, `docs/brand/*` | Design system |
| Токены (dark, density, a11y) | `shared/ui/designTokens.ts`, `styles/*.css` | Design system |
| Charts (uncertainty, deltas) | `shared/charts/*` | Data-viz |
| Провайдеры (time, cf, trust) | `app/providers/*` | App shell |
| Прозаические артефакты | `features/artifacts/reading-view/*` | Publications |
| Bureaucratic renderers | `features/artifacts/renderers/*` | Publications + legal |
| i18n | `i18n/*` | Localization |
| A11y infra | `shared/a11y/*`, `tools/design/*` | Quality |
| Backend contracts | `policy-engine/src/runtime/api/*` | Runtime API |
| CLI styleguide | `packages/cli/*` | DX |

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

11. **Temporal scrubber** — скрабинг на 60 fps, все графики синхронно.
12. **Quantity hover** — в любом месте UI появляется mini-lineage за 150 ms.
13. **Lineage trace** — от финального числа до raw dataset за 3 клика.
14. **Policy diff** — два run'а, causal delta strip, sync scroll.
15. **Counterfactual toggle** — real + CF одновременно, разница в gold.
16. **Постанова КМУ render** — с правильной шапкой, нумерацией, epistemic legend.
17. **Trust view** — hashes и timestamps inline, глифы с диакритиками.
18. **OG card** — shareable URL автоматически даёт brand-correct изображение.

---

## Appendix A — Critical path dependency graph

```
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
           ├─ 2.1 Time-as-primitive
           └─ 2.2 Provenance-on-hover
                    ├─ 2.3 Policy diff (needs 2.1, 2.2)
                    ├─ 2.4 Counterfactual (needs 2.1, 2.2, 1.2)
                    ├─ 2.5 Bureaucratic (needs 1.5, 1.6)
                    ├─ 2.6 Trust view (needs 2.2, 1.6)
                    └─ 2.7 Polish (parallel)
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
- [ ] Demo recorded (screencast) for stakeholder review.

## Appendix C — Immediate next actions (kick-off неделя)

1. Создать ветку `design/wave1-phase-0-foundations`.
2. Скопировать шаблон ADR из `docs/adr/_template.md` (создать если нет).
3. Написать ADR-042 (Janus/Atlas dual brand) — draft.
4. Написать skeleton `docs/brand/GLYPH_SPECIFICATION.md` — геометрия сетки.
5. Настроить `tools/design/check-contrast.ts` — стартовая версия.
6. Создать tracking issue в project board (Linear/GitHub) с структурой этого плана.
7. Забукать 30-минутный review slot с внешним design-consultant на конец Phase 1.0.
