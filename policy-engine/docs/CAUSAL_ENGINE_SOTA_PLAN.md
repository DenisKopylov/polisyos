# Бескомпромиссный план доведения каузального движка Перла-Баренбойма до полного SOTA

> Версия: 2.3 | Дата: 2026-03-17
> Каждая фаза содержит: теоретическое обоснование, конкретные файлы, функции, тесты, критерии приёмки.
> Фазы упорядочены по теоретической зависимости.

---

## Фаза 0: Архитектурные пререквизиты

### 0.1 — Twin/AMN как derived graph builders (НЕ core GraphType)

**Что:** Реализовать Twin Network и AMN как **derived graph wrappers / builders** с собственным metadata layer, а не как первичные типы в `GraphType` enum.

**⚠️ Архитектурное решение:** AMN и Twin Network — это не «ещё один тип исходного causal graph», а derived representational views над базовым SCM/ADMG для конкретного класса запросов (counterfactual reasoning). Зашивать их в core IR (`GraphType` enum) загрязнит базовую графовую модель инженерными артефактами, которые релевантны только для Layer-3 подсистемы. Вместо этого они живут как отдельные graph builders в foundry, оборачивающие стандартный `CausalGraphModel(graph_type=GraphType.ADMG)` дополнительными метаданными.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/twin_graph.py` (новый файл):
  - `TwinGraphMetadata(BaseModel, frozen=True, extra="forbid")`:
    - `factual_world_prefix: str = "__0"`
    - `counterfactual_world_prefix: str = "__1"`
    - `shared_exogenous: list[str]`
    - `world_count: int = 2`
    - `source_graph_hash: str` — hash исходного ADMG (для traceability)
  - `build_twin_graph(graph: CausalGraphModel) -> tuple[CausalGraphModel, TwinGraphMetadata]`:
    - Результат: standard `CausalGraphModel(graph_type=GraphType.ADMG)` + отдельный metadata объект
    - Дублирование с shared U
    - Валидация: пары V__0/V__1; shared exogenous
  - `to_factual_subgraph(graph, meta) -> CausalGraphModel`
  - `to_counterfactual_subgraph(graph, meta) -> CausalGraphModel`

- `src/polisyos/foundry/methods/catalog/causal/amn.py` (из Phase 2.1, forward-reference):
  - `AMNMetadata(BaseModel, frozen=True, extra="forbid")`:
    - `worlds: list[str]`
    - `world_partition: dict[str, list[str]]`
    - `counterfactual_interventions: dict[str, dict[str, float]]`
    - `bridge_edges: list[tuple[str, str]]`
  - `build_amn(graph, interventions) -> tuple[CausalGraphModel, AMNMetadata]`:
    - Результат: standard ADMG + metadata wrapper
  - `amn_d_separation(graph, meta, x_set, y_set, z_set) -> bool`

- `src/polisyos/ir/analytics/causal_graph.py`:
  - **GraphType enum НЕ расширяется** — TWIN/AMN не добавляются
  - Опционально: добавить `metadata: dict[str, Any] | None = None` field в CausalGraphModel для ad-hoc metadata attachment (или использовать сторонний registry)

**Тесты:** `tests/.../test_twin_amn_graph.py` — 5 тестов (doubles variables, shared exogenous, 3-world, cross-world d-sep, serialization roundtrip)

**Критерий:** Все 5 тестов; twin/AMN полностью сериализуемы; core IR (`GraphType`, `CausalGraphModel`) не загрязнён Layer-3 артефактами.

---

### 0.2 — EstimandAST: новые node types для ctf-calculus

**Что:** 3 новых типа узлов в EstimandAST для Layer-3.

**Зачем:** `CounterfactualNode` покрывает простые Y_x запросы, но ctf-calculus требует nested counterfactuals, cross-world queries и ctf-intervention nodes.

**Файлы:**
- `src/polisyos/ir/analytics/estimand.py`:
  - `NestedCounterfactualNode`: outer_variable, outer_intervention, inner_counterfactual, world_indices
  - `CrossWorldNode`: worlds (tuple[CounterfactualNode, ...]), joint
  - `CtfInterventionNode`: variable, intervention, ctf_context
  - Обновить `EstimandNode` union, LaTeX рендеринг, `.model_rebuild()`

**Тесты:** `tests/.../test_estimand_ctf_nodes.py` — 4 теста (serialization, 2-world, LaTeX, AST root)

**Критерий:** JSON roundtrip; LaTeX валиден.

---

### 0A — Performance-оптимизация графовых примитивов (ОБНОВЛЕНА по данным профилирования 2026-03-17)

**Что:** Три измеренных оптимизации по данным cProfile: (1) обход Pydantic-валидации для производных графов, (2) CachedAdjacency, (3) мемоизация c-components.

**⚠️ Фаза полностью переписана по результатам профилирования.** Предыдущая версия (v2.2) опиралась на гипотезы. Текущая версия (v2.3) основана на cProfile-данных, собранных на Barabási-Albert графах 20–500 узлов и multi-layer dense графах до 625 рёбер.

#### Данные профилирования (summary)

**Таблица масштабирования примитивов (mean ms, BA-graph m=3, single call):**

| Функция | 20 нод | 50 | 100 | 200 | 500 |
|---|---|---|---|---|---|
| `extract_directed_edges` | 0.06 | 0.05 | 0.10 | 0.22 | 0.58 |
| `ancestors` | 0.03 | 0.07 | 0.14 | 0.29 | 0.74 |
| `c_components` | 0.03 | 0.05 | 0.10 | 0.21 | 0.51 |
| `m_separation` | 0.08 | 0.18 | 0.40 | 0.79 | 2.19 |
| `induced_subgraph` | 0.04 | 0.09 | 0.19 | 0.38 | 0.96 |
| `do_operator` | 0.07 | 0.18 | 0.37 | 0.74 | 1.85 |
| **`id_algorithm` (full)** | 0.26 | 0.39 | 0.76 | 0.71 | 2.01 |

**cProfile breakdown (10× id_algorithm на 50-node/625-edge multi-layer graph, 0.068s total):**

| Компонент | tottime (s) | % от total | cumtime (s) | ncalls |
|---|---|---|---|---|
| `CausalEdge._validate_fields` (Pydantic) | 0.015 | **22%** | 0.026 | 14,510 |
| `validate_python` (Pydantic core) | 0.003 | 4% | **0.033 (49%)** | 60 |
| `builtins.getattr` (Pydantic internals) | 0.012 | **18%** | 0.012 | 101,710 |
| `extract_directed_edges` | 0.006 | 9% | 0.008 | 40 |
| `ancestors` | 0.004 | 6% | 0.012 | 30 |
| `_validate_graph` (Pydantic model) | 0.004 | 6% | 0.004 | 30 |

**Ключевое открытие:** Pydantic-валидация доминирует — **~49% cumtime** уходит на `validate_python` при создании промежуточных CausalGraphModel. `induced_subgraph()` и `do_operator()` создают новый CausalGraphModel, что вызывает `CausalEdge._validate_fields()` на **каждом ребре** (14,510 вызовов на 10 ID runs). Для production-сценариев промежуточные графы **гарантированно валидны** (subset из уже провалидированного графа), поэтому повторная валидация — чистый overhead.

**Adjacency rebuild:** `extract_directed_edges` вызывается ~4 раза за один id_algorithm run, каждый раз сканируя все рёбра. Для 625-рёберного графа это ~2500 лишних сканирований рёбер.

**Call counts per single id_algorithm (frontdoor, 50-node graph):**
- `extract_directed_edges`: 4 вызова
- `ancestors`: 3 вызова
- `c_components`: 2 вызова
- `induced_subgraph`: 2 вызова (→ 2× Pydantic model construction)
- `do_operator`: 1 вызов (→ 1× Pydantic model construction)

#### Три оптимизации (по ROI)

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/admg_ops.py`:

  **Приоритет 1: `model_construct()` для производных графов (ожидаемый speedup: 40-50%)**

  Заменить `CausalGraphModel(...)` на `CausalGraphModel.model_construct(...)` в:
  - `induced_subgraph()` (line ~330)
  - `do_operator()` (line ~171)
  - `remove_outgoing_edges()` (line ~229)
  - `augment_with_s_nodes()` (line ~795)
  - `resolve_s_node_by_adjustment()` (line ~893)
  - `project_to_subgraph()` — delegates to `induced_subgraph()`, covered

  ```python
  # BEFORE (49% cumtime — Pydantic validates every edge again):
  return CausalGraphModel(
      schema_version=graph.schema_version,
      graph_type=graph.graph_type,
      nodes=kept_nodes,
      edges=kept_edges,
      ...
  )

  # AFTER (0% validation — safe because inputs are subset of validated graph):
  return CausalGraphModel.model_construct(
      schema_version=graph.schema_version,
      graph_type=graph.graph_type,
      nodes=kept_nodes,
      edges=kept_edges,
      discovery_method=graph.discovery_method,
      skg_version_id=graph.skg_version_id,
      pag_identification_policy=graph.pag_identification_policy,
      id_confidence_under_pag=graph.id_confidence_under_pag,
      metadata=dict(graph.metadata),
  )
  ```

  **⚠️ Invariant:** `model_construct()` bypasses ALL Pydantic validation. Safe ONLY when:
  - `kept_nodes ⊆ graph.nodes` (subset of validated nodes)
  - `kept_edges ⊆ graph.edges` (subset of validated edges, or original edges from validated graph)
  - All edges reference nodes that are in `kept_nodes`

  Для `augment_with_s_nodes()` — новые nodes/edges добавляются, поэтому нужна **ручная проверка** (`assert s_name not in existing_nodes` уже есть) вместо полной Pydantic pass. Альтернатива: оставить `CausalGraphModel(...)` только для `augment_with_s_nodes()` — это не hot path.

  **Приоритет 2: CachedAdjacency (ожидаемый speedup: 30-40%)**

  ```python
  class CachedAdjacency:
      """One-pass adjacency pre-computation, reused across ancestors/descendants/m_separation/c_components."""
      __slots__ = ('fwd', 'rev', 'bi', 'directed_edges', 'bidirected_edges')

      def __init__(self, graph: "CausalGraphModel") -> None:
          from polisyos.ir.analytics.causal_graph import EdgeMark
          fwd: dict[str, list[str]] = {n: [] for n in graph.nodes}
          rev: dict[str, list[str]] = {n: [] for n in graph.nodes}
          bi: dict[str, list[str]] = {n: [] for n in graph.nodes}
          dir_set: set[tuple[str, str]] = set()
          bi_set: set[frozenset[str]] = set()
          for e in graph.edges:
              if e.mark_src is EdgeMark.TAIL and e.mark_dst is EdgeMark.ARROW:
                  fwd[e.src].append(e.dst)
                  rev[e.dst].append(e.src)
                  dir_set.add((e.src, e.dst))
              elif e.mark_src is EdgeMark.ARROW and e.mark_dst is EdgeMark.ARROW:
                  bi[e.src].append(e.dst)
                  bi[e.dst].append(e.src)
                  bi_set.add(frozenset({e.src, e.dst}))
          self.fwd = fwd
          self.rev = rev
          self.bi = bi
          self.directed_edges = frozenset(dir_set)
          self.bidirected_edges = frozenset(bi_set)
  ```

  Кэширование через `WeakValueDictionary` по `id(graph)`:
  ```python
  import weakref
  _ADJ_CACHE: dict[int, CachedAdjacency] = {}
  _ADJ_CACHE_REFS: dict[int, weakref.ref] = {}

  def _get_cached_adjacency(graph: "CausalGraphModel") -> CachedAdjacency:
      key = id(graph)
      cached = _ADJ_CACHE.get(key)
      if cached is not None:
          return cached
      adj = CachedAdjacency(graph)
      _ADJ_CACHE[key] = adj
      # CausalGraphModel is frozen (immutable), id() is stable while object lives.
      # Eviction: when graph is GC'd, id(graph) can be reused.
      # WeakRef callback cleans up stale entries.
      def _cleanup(ref, k=key):
          _ADJ_CACHE.pop(k, None)
          _ADJ_CACHE_REFS.pop(k, None)
      _ADJ_CACHE_REFS[key] = weakref.ref(graph, _cleanup)
      return adj
  ```

  Обновить все функции:
  - `extract_directed_edges(graph)` → `_get_cached_adjacency(graph).directed_edges`
  - `extract_bidirected_edges(graph)` → `_get_cached_adjacency(graph).bidirected_edges`
  - `ancestors(graph, variables)` → использует `adj.rev` напрямую (без rebuild)
  - `descendants(graph, variables)` → использует `adj.fwd` напрямую
  - `m_separation(graph, ...)` → строит adj из `_get_cached_adjacency()` за O(V)
  - `c_components(graph)` → использует `adj.bidirected_edges`

  **⚠️ Безопасность кэша:** `CausalGraphModel` — `frozen=True` (Pydantic). Один и тот же instance гарантированно не мутирует. `id(graph)` stable пока объект жив. WeakRef callback гарантирует eviction при GC. Потенциальная проблема: если два **разных** графа получают тот же `id()` (после GC первого) — WeakRef callback решает это: при GC первого графа кэш-запись удаляется.

  **Приоритет 3: Мемоизация c_components (ожидаемый speedup: 5-10%)**

  `c_components()` вызывается 2 раза в одном `id_algorithm` run (line 613 + line 661 в id_engine.py) на **одном и том же** или **близких** графах. С CachedAdjacency второй вызов станет дешевле (adjacency не rebuilding), но результат c_components тоже можно кэшировать.

  Простая мемоизация через cache на `id(graph)`:
  ```python
  _CC_CACHE: dict[int, list[frozenset[str]]] = {}

  def c_components(graph: "CausalGraphModel") -> list[frozenset[str]]:
      key = id(graph)
      if key in _CC_CACHE:
          return _CC_CACHE[key]
      # ... existing Union-Find logic ...
      result = sorted([frozenset(s) for s in comp.values()], key=len, reverse=True)
      _CC_CACHE[key] = result
      return result
  ```

  Eviction: аналогичный WeakRef callback как в CachedAdjacency.

- `src/polisyos/foundry/methods/catalog/causal/id_engine.py`:
  - **Не требуется изменений в id_engine.py** — оптимизации прозрачны через admg_ops API.
  - Передача `CachedAdjacency` между рекурсивными вызовами **не нужна** — кэш глобальный, graph instances переиспользуются автоматически.

**Отложено (Phase 0A-ext, подтверждено профилированием как НЕ приоритет):**

- **Bitmasking** — на 500 нодах frozenset intersection = ~0.01ms. Set-операции = <2% общего времени. ROI отрицательный без графов >2000 нод. Профилирование подтвердило: **не bottleneck**.
- **Matrix reachability (Floyd-Warshall / NumPy)** — `ancestors()` через BFS = 0.74ms на 500 нодах. Матричное транзитивное замыкание O(V³) = O(125M) на 500 нодах — **медленнее** чем BFS для sparse BA-графов (m=3). Оправдано только для dense графов >1000 нод.
- **Rust-бэкенд (rustworkx)** — при текущих ~2ms на 500 нодах, FFI overhead сопоставим с выигрышем. Оправдан только при графах >5000 нод.

**Критерий перехода из deferred в active:** benchmark harness (Phase 15) покажет id_algorithm > 5s на реалистичном use-case → пересмотр.

#### Ожидаемый суммарный speedup

| Оптимизация | Сложность | Speedup (50-node) | Speedup (500-node) | Риск |
|---|---|---|---|---|
| `model_construct()` в admg_ops | 1-2 часа | 40-50% | 40-50% | Низкий (derived graphs only) |
| CachedAdjacency | 2-3 часа | 30-40% | 30-50% | Минимальный (frozen models + WeakRef) |
| Мемоизация c_components | 1 час | 5-10% | 5-10% | Минимальный |
| **Итого** | **~5 часов** | **~60-70%** | **~60-70%** | **Низкий** |

**Тесты:**
- `tests/.../test_performance_primitives.py`:
  - `test_cached_adjacency_reuse`: второй вызов `ancestors()` на том же графе — 0 edge scans (CachedAdjacency hit)
  - `test_cached_adjacency_eviction`: после `del graph` + GC — кэш-запись удалена, новый граф не получает stale data
  - `test_c_components_memoized`: два вызова `c_components()` на том же графе → cache hit, результат идентичен
  - `test_model_construct_preserves_semantics`: `induced_subgraph()` через `model_construct()` даёт тот же граф что через `CausalGraphModel()` (roundtrip через `.model_dump()` идентичен)
  - `test_model_construct_no_validation_overhead`: `induced_subgraph()` на 500-edge графе < 0.2ms (vs ~1ms с Pydantic validation)
  - `test_id_algorithm_ba_100`: ID на BA-100 (m=3) graph < 1ms
  - `test_id_algorithm_ba_500`: ID на BA-500 (m=3) graph < 3ms
  - `test_id_algorithm_multilayer_50x625`: ID на multi-layer (50 nodes, 625 edges) < 2ms

**Критерий:** 8 тестов; измеренный speedup ≥ 50% на 50-node multi-layer graph; backward-compatible API (все существующие ~71 test-файлов продолжают проходить); никаких изменений в сигнатурах публичных функций.

---

## Фаза 1: ID* / IDC* — Counterfactual Identification

### 1.1 — Алгоритм ID* (Shpitser & Pearl 2012)

**Что:** Sound-and-complete алгоритм идентификации P(Y_x = y) на произвольном ADMG.

**Ключевое свойство (soundness + completeness):**
- **Soundness:** Если ID* выдаёт формулу — она гарантированно верна.
- **Completeness:** Если ID* возвращает HEDGE — запрос **принципиально** неидентифицируем. Ни один другой алгоритм не сможет найти непараметрическое решение для этого графа.

y0 реализует математический предел этого алгоритма. Невозможно создать алгоритм, который «идентифицирует то, на чём ID* сдался» в рамках непараметрических ADMG. **Но** реализация y0 — прямой академический перевод псевдокода. PolicyOS нацелен на более эффективную реализацию (Phase 0A, speedup будет измерен в benchmark) и **расширенную** за счёт fallback-механизмов (Phase 1A), которые дают пользователю actionable information даже при non-identification.

**Оптимизация vs y0 (из Phase 0A, подтверждено профилированием):**
- AMN вместо рекурсивного make-cg: read d-separation напрямую без раздувания графа
- `model_construct()` для производных графов в рекурсии: ~40-50% speedup за счёт обхода Pydantic-валидации (измерено: Pydantic = 49% cumtime в id_algorithm)
- CachedAdjacency: однократное построение adjacency per graph instance, переиспользование через кэш
- Мемоизация c-компонент в counterfactual graph G*

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/id_engine.py`:
  - `id_star_algorithm(counterfactual_query: CtfQuery, graph: CausalGraphModel, _depth=0, _trace=None) -> IdentificationResult`
    - `CtfQuery = namedtuple("CtfQuery", ["outcome", "intervention", "conditioning", "evidence"])`
    - Step 1: Construct G* через `build_amn()` (не build_twin_graph — AMN компактнее)
    - Step 2: Partition по c-components G*
    - Step 3: Проверка reduction к Layer-2 (ID algorithm) для каждого sub-problem
    - Step 4: ctf-specific decomposition (parallel worlds factorization)
    - Step 5: Рекурсия до identified или hedge в G*
    - Returns: `IdentificationResult` with `CounterfactualNode`/`CrossWorldNode` AST
    - Emits: `ID_STAR_STEP1..5` ProofStep entries
  - `_build_counterfactual_graph(graph, query) -> CausalGraphModel`:
    - AMN construction (compact) вместо full twin graph
  - `_ctf_c_components(cf_graph) -> list[frozenset]`:
    - c-components на G* с межмировыми bidirected edges
  - Обновить `_RULE_FORMAL` dict

**Тесты:** `tests/.../test_id_star_algorithm.py` — 8 тестов:
- `test_id_star_simple_backdoor_reduces_to_id`: сводится к ID
- `test_id_star_bow_arc_non_identifiable`: HEDGE в G*
- `test_id_star_ett_query`: ETT
- `test_id_star_pn_query`: probability of necessity
- `test_id_star_frontdoor_ctf`: counterfactual на frontdoor
- `test_id_star_napkin_graph`: Napkin (Pearl's classic)
- `test_id_star_proof_steps_complete`: proof trace
- `test_id_star_nested_ctf`: nested counterfactual

**Критерий:** 8 тестов; numeric examples из Shpitser & Pearl 2012 Table 1.

---

### 1.2 — Алгоритм IDC*

**Что:** P(Y_x = y | Z = z) — conditional counterfactual identification.

**Файлы:** id_engine.py — `idc_star_algorithm()` как ratio of two ID* calls.

**Тесты:** 4 теста (ETT, IDC fallback, non-identifiable, proof trace).

---

### 1.3 — Интеграция ID*/IDC* в CausalEngine

**Файлы:** causal_engine.py (routing), estimand_compiler.py (COUNTERFACTUAL_IDENTIFIED shape + TWIN_NETWORK_MC strategy).

**Тесты:** 3 integration теста.

---

### 1A — Auto-Fallback Pipeline при HEDGE (НОВАЯ)

**Что:** Когда ID* (или ID) ловит HEDGE — не просто сдаваться, а автоматически запускать cascading fallback chain.

**Зачем:** y0 при HEDGE просто возвращает FAIL. PolicyOS должен давать пользователю максимум информации даже когда точная identification невозможна. Это **ownable territory** — ни один другой инструмент этого не делает.

**Архитектура fallback chain с явными epistemic trust tiers:**

> **⚠️ Критично для доверия:** Fallback chain смешивает три фундаментально разных эпистемических режима. Без явного разделения уровней доверия пользователь увидит HEDGE → bounds → monotonicity rescue → sensitivity curve и подумает, что всё это одна линия вывода с одинаковой надёжностью. Каждый шаг маркируется `EpistemicTier` — пользователь всегда знает, какой уровень гарантий стоит за результатом.

```
HEDGE detected
    │
    │  ╔══════════════════════════════════════════════════════════════╗
    │  ║  EpistemicTier.EXACT_NONPARAMETRIC  (Tier 1)               ║
    │  ║  Гарантия: sound + complete в рамках NPSEM-IE модели       ║
    ├─→║  Step 1: LP Bounds (Phase 7.1)                             ║
    │  ║  "Точная оценка невозможна, но эффект ∈ [0.15, 0.45]"     ║
    │  ║  Bounds are SHARP — no tighter interval exists              ║
    │  ╚══════════════════════════════════════════════════════════════╝
    │
    │  ╔══════════════════════════════════════════════════════════════╗
    │  ║  EpistemicTier.PARTIAL_IDENTIFICATION  (Tier 2)             ║
    │  ║  Гарантия: верно при верности NPSEM, bounds не обязательно  ║
    │  ║  sharp если polynomial relaxation                           ║
    ├─→║  (покрыто Step 1 при relaxed_polynomial bounds)             ║
    │  ╚══════════════════════════════════════════════════════════════╝
    │
    │  ╔══════════════════════════════════════════════════════════════╗
    │  ║  EpistemicTier.ASSUMPTION_DEPENDENT  (Tier 3)               ║
    │  ║  Гарантия: верно ТОЛЬКО при дополнительных допущениях       ║
    │  ║  ⚠️ Пользователь ОБЯЗАН верифицировать допущение            ║
    ├─→║  Step 2: Parametric Rescue (monotonicity / linearity)      ║
    │  ║  "Результат верен ТОЛЬКО при допущении монотонности"        ║
    │  ╚══════════════════════════════════════════════════════════════╝
    │
    │  ╔══════════════════════════════════════════════════════════════╗
    │  ║  EpistemicTier.DIAGNOSTIC_GUIDANCE  (Tier 4)                ║
    │  ║  Гарантия: НЕТ гарантий — это инструмент анализа           ║
    │  ║  Помогает ПОНЯТЬ задачу, не решить её                       ║
    ├─→║  Step 3: Sensitivity Analysis                              ║
    │  ║  "При confounding ≤ ρ, эффект ∈ [lb(ρ), ub(ρ)]"           ║
    │  ║                                                             ║
    └─→║  Step 4: Suggested Experiments                             ║
       ║  "Проведите RCT на Z → задача станет идентифицируемой"     ║
       ╚══════════════════════════════════════════════════════════════╝
```

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/id_engine.py`:
  - `EpistemicTier(str, Enum)`:
    - `EXACT_NONPARAMETRIC = "exact_nonparametric"` — Tier 1: sound+complete bounds
    - `PARTIAL_IDENTIFICATION = "partial_identification"` — Tier 2: valid bounds, possibly not sharp
    - `ASSUMPTION_DEPENDENT = "assumption_dependent"` — Tier 3: requires additional assumptions
    - `DIAGNOSTIC_GUIDANCE = "diagnostic_guidance"` — Tier 4: no guarantees, exploratory
  - `_hedge_fallback_chain(hedge_cert: HedgeCertificate, graph, treatment, outcome, data=None) -> FallbackResult`:
    - `FallbackResult(BaseModel)`:
      - `bounds: PartialIdentificationResult | None`
      - `bounds_tier: EpistemicTier` — Tier 1 если sharp_lp, Tier 2 если relaxed_polynomial
      - `parametric_rescue: IdentificationResult | None`
      - `parametric_assumption: str | None` — "monotonicity" / "linearity"
      - `parametric_tier: EpistemicTier = EpistemicTier.ASSUMPTION_DEPENDENT` — всегда Tier 3
      - `sensitivity_curve: list[tuple[float, float, float]] | None` — [(ρ, lb, ub), ...]
      - `sensitivity_tier: EpistemicTier = EpistemicTier.DIAGNOSTIC_GUIDANCE` — всегда Tier 4
      - `suggested_experiments: list[SuggestedExperiment]`
      - `experiments_tier: EpistemicTier = EpistemicTier.DIAGNOSTIC_GUIDANCE` — всегда Tier 4
      - `fallback_level: int` — 1-4 (how deep we went)
      - `highest_tier_reached: EpistemicTier` — лучший tier с непустым результатом
  - **Step 1: LP Bounds:**
    - Вызвать `auto_bounds()` из Phase 7.1
    - Если binary variables → exact sharp bounds
    - Если continuous → discretized approximate bounds
  - **Step 2: Parametric Rescue:**
    - `_try_monotonicity_rescue(graph, treatment, outcome)`:
      - Добавить assumption MTR (monotone treatment response) к graph
      - Re-run ID algorithm — если теперь identifiable → warn + return
    - `_try_linearity_rescue(graph, treatment, outcome)`:
      - Предположить linear structural equations
      - Wright's path tracing → closed-form estimand
      - Warn: "Результат верен только при допущении линейности"
  - **Step 3: Sensitivity:**
    - Вызвать `sensitivity_metrics()` с range ρ ∈ [0, 1]
    - Return sensitivity curve [(ρ, lb(ρ), ub(ρ))]
  - **Step 4: Suggested Experiments:**
    - Из `hedge_cert.minimal_required_s_nodes` → construct SuggestedExperiment list
    - "Для identification необходим RCT на переменные: {Z}"

- `src/polisyos/foundry/methods/catalog/causal/causal_engine.py`:
  - В `run()`: когда `isinstance(id_result, NegativeCertificate)`:
    - Вместо `return None, dummy_audit(), id_result`:
    - Вызвать `_hedge_fallback_chain()` → attach результат к EvidenceBundle
    - Return: `(None, bundle_with_fallback, negative_cert_with_fallback)`

**Тесты:**
- `tests/.../test_hedge_fallback.py`:
  - `test_fallback_provides_bounds_on_bow_arc`: Bow-arc → bounds ≠ [-1, 1]
  - `test_fallback_parametric_rescue_linear`: Linear assumption → identifiable + warning
  - `test_fallback_sensitivity_curve_monotone`: ρ ↑ → interval ↑
  - `test_fallback_suggested_experiments`: Constructive suggestions list
  - `test_fallback_audit_trail`: Fallback results in EvidenceBundle

**Критерий:** 5 тестов; при HEDGE пользователь получает bounds + rescue + sensitivity + suggestions.

---

## Фаза 2: ctf-calculus (Correa & Bareinboim, ICML 2025)

### 2.1 — Ancestral Multi-world Networks (AMN)

**Что:** Реализация AMN — графовой конструкции для чтения counterfactual independences через d-separation.

**Зачем:** AMN — компактная альтернатива Twin Networks для counterfactual reasoning. Ключевое свойство: **counterfactual independences в SCM читаются как d-separation в AMN** (sound and complete). Это устраняет необходимость строить полный Twin Network и позволяет графовую проверку. В ID* (Phase 1.1) AMN используется вместо громоздкого make-cg на каждом шаге рекурсии — ключевая performance-оптимизация vs y0.

**Теория:** Correa & Bareinboim (2025): "Ancestral Multi-world Networks provide a graphical representation that is sound and complete for reading counterfactual independences via d-separation."

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/amn.py` (новый файл):
  - `build_amn(graph: CausalGraphModel, counterfactual_queries: list[CtfQuery]) -> CausalGraphModel`:
    - Step 1: Determine which worlds are needed from queries
    - Step 2: For each world, replicate subgraph of relevant ancestors
    - Step 3: Add bridge edges (shared exogenous) between worlds
    - Step 4: Remove non-ancestral nodes (ancestral projection) — ключевая оптимизация: уменьшает граф
    - Step 5: Return CausalGraphModel(graph_type=GraphType.AMN, metadata=AMNMetadata(...))
  - `amn_ctf_independence(amn: CausalGraphModel, x_vars: frozenset, y_vars: frozenset, z_vars: frozenset) -> bool`:
    - d-separation test на AMN graph
    - Delegates to `m_separation()` из admg_ops (используя CachedAdjacency из Phase 0A)
    - Handles inter-world edges correctly
  - `amn_ancestral_projection(amn: CausalGraphModel) -> CausalGraphModel`:
    - Removes non-ancestral nodes while preserving independences
    - Key optimization: reduces AMN size for large graphs
  - `verify_ctf_faithfulness(amn: CausalGraphModel, scm: NCMSpec, n_samples: int = 5000) -> bool`:
    - Monte Carlo verification: check that graphical independences hold in simulated data
    - Diagnostic tool, not required for main pipeline

**Тесты:**
- `tests/.../test_amn.py`:
  - `test_amn_2_world_equals_twin`: AMN(K=2) ≡ Twin Network (same d-separation results)
  - `test_amn_3_world_construction`: 3-world AMN for path-specific query Y_{x}(M_{x'})
  - `test_amn_d_separation_matches_scm`: d-sep в AMN ↔ counterfactual independence в SCM (Monte Carlo validation)
  - `test_amn_ancestral_projection_preserves_independences`: projection не теряет independences
  - `test_amn_napkin_graph`: Napkin graph AMN construction
  - `test_amn_frontdoor_graph`: Frontdoor AMN construction

**Критерий:** 6 тестов; AMN d-separation совпадает с SCM-based independence testing.

---

### 2.2 — Три правила ctf-calculus

**Что:** Реализация 3 правил counterfactual calculus — аналога do-calculus для Layer-3.

**Зачем:** ctf-calculus — sound and complete система для манипуляции counterfactual quantities. Позволяет трансформировать произвольные counterfactual expressions в identifiable формулы (когда идентификация возможна). Это **фронтир теории** — не реализовано нигде в мире.

**Теория:**
- ctf-R1 (Insertion/Deletion of observations in ctf context): P(Y_x | Z_x, W) = P(Y_x | W) iff Y ⊥ Z | W in AMN_{X=x}
- ctf-R2 (Ctf-intervention/observation exchange): P(Y_x | Z_{x'}, W) = P(Y_x | Z, W) iff Y ⊥ Z | W in AMN_{X=x, Z_{x'}→Z}
- ctf-R3 (Deletion of ctf-interventions): P(Y_x | Z_{x'}, W) = P(Y_x | W) iff Y ⊥ Z | W in AMN_{X=x, overline{Z_{x'}}}

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/ctf_calculus.py` (новый файл):
  - `apply_ctf_rule1(node: CounterfactualNode, amn: CausalGraphModel, z_vars: frozenset) -> tuple[CounterfactualNode, IRProofStep] | None`:
    - Проверить d-separation в AMN после удаления observation Z
    - Если d-separated: удалить Z из conditioning, вернуть simplified node
    - Emit: CTF_R1 ProofStep с theorem reference
  - `apply_ctf_rule2(node: CounterfactualNode, amn: CausalGraphModel, z_vars: frozenset) -> tuple[CounterfactualNode, IRProofStep] | None`:
    - Проверить d-separation в модифицированном AMN (Z_{x'} → Z exchange)
    - Если d-separated: заменить ctf-conditioning на observational
    - Emit: CTF_R2 ProofStep
  - `apply_ctf_rule3(node: CounterfactualNode, amn: CausalGraphModel, z_vars: frozenset) -> tuple[CounterfactualNode, IRProofStep] | None`:
    - Проверить d-separation в AMN с удалёнными ctf-intervention edges
    - Если d-separated: удалить ctf-intervention
    - Emit: CTF_R3 ProofStep
  - `_try_all_ctf_rules(node, amn) -> tuple[CounterfactualNode, list[IRProofStep]]`:
    - Greedy fixed-point: try all 3 rules exhaustively until no rule fires
  - `rewrite_ctf_estimand(ast: EstimandAST, graph: CausalGraphModel, max_iterations: int = 20) -> tuple[EstimandAST, list[IRProofStep]]`:
    - Build AMN from graph + query
    - Walk AST tree, apply ctf rules to all CounterfactualNode/NestedCounterfactualNode/CrossWorldNode
    - Fixed-point iteration until convergence
  - Обновить `_RULE_FORMAL` dict в id_engine.py с CTF_R1/R2/R3

- `src/polisyos/foundry/methods/catalog/causal/do_calculus.py`:
  - В `rewrite_estimand()`: добавить optional hook для ctf-calculus post-pass
  - Если AST содержит CounterfactualNode → вызвать `rewrite_ctf_estimand()` после do-calculus pass

**Тесты:**
- `tests/.../test_ctf_calculus.py`:
  - `test_ctf_r1_insertion_deletion`: Rule 1 на простом backdoor
  - `test_ctf_r2_exchange`: Rule 2 — ctf-intervention ↔ observation
  - `test_ctf_r3_deletion`: Rule 3 — удаление ctf-intervention
  - `test_ctf_fixed_point`: Convergence после K итераций
  - `test_ctf_rules_complete_on_napkin`: All 3 rules needed на Napkin graph
  - `test_ctf_rewrite_reduces_to_l2`: ctf-query сводится к Layer-2 через ctf-rules
  - `test_ctf_non_identifiable_through_rules`: Query не сводится → остаётся counterfactual
  - `test_ctf_proof_steps_formal`: ProofStep с theorem references

**Критерий:** 8 тестов; ctf-calculus правильно применяется; fixed-point converges; proof trace полный. **Цель: первая known-to-us реализация ctf-calculus (подтвердить после literature survey в Phase 15).**

---

## Фаза 3: Sigma-calculus формализация

### 3.1 — Выделение σ-calculus в отдельный модуль

**Что:** Рефакторинг: извлечь σ-calculus из `do_calculus.py` в отдельный `sigma_calculus.py` с полной формализацией трёх правил.

**Зачем:** Сейчас σ-calculus встроен inline в do_calculus.py. Для SOTA необходимо: (1) отдельный модуль для clarity, (2) формальные ProofStep с theorem references (Correa & Bareinboim, AAAI 2020), (3) integration с ctf-calculus, (4) general policy evaluation pipeline.

**Теория:** σ-calculus (Correa & Bareinboim, AAAI 2020) — generalization of do-calculus to soft/stochastic/conditional interventions:
- σ-Rule 1: Insertion/deletion of observations under σ-intervention
- σ-Rule 2: σ-intervention/observation exchange
- σ-Rule 3: Insertion/deletion of σ-interventions

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/sigma_calculus.py` (новый файл):
  - Перенести `apply_sigma_rule1/2/3()` из do_calculus.py
  - Перенести `_try_all_rules_with_selection()` и `rewrite_estimand_with_selection()`
  - Добавить `_build_sigma_graph()` — standalone helper (сейчас inline)
  - Добавить `sigma_identify(query, graph, policy, selection_vars) -> IdentificationResult`:
    - Full σ-identification algorithm: repeated application of σ-rules until identified or stuck
    - Integration с ID algorithm: если σ-rules сводят к standard query → delegate to id_algorithm
  - Добавить `sigma_z_identify(query, graph, policy, z_interventions, selection_vars) -> IdentificationResult`:
    - Combined σ + Z-transport identification
  - Обновить imports в do_calculus.py для backward compatibility

- `src/polisyos/foundry/methods/catalog/causal/do_calculus.py`:
  - Убрать σ-functions (оставить re-export для backward compat)
  - Импортировать из sigma_calculus.py

**Тесты:**
- `tests/.../test_sigma_calculus_standalone.py`:
  - Перенести существующие тесты из `test_sigma_calculus.py`
  - `test_sigma_identify_full_pipeline`: σ-identification от query до estimand
  - `test_sigma_z_combined`: σ + Z-transport combined
  - `test_sigma_with_ctf_calculus`: σ-rules + ctf-rules sequential application

**Критерий:** Все существующие sigma тесты продолжают проходить; 3 новых теста; backward compatibility сохранена.

---

## Фаза 4: Counterfactual Transportability

### 4.1 — Transport Layer-3 quantities

**Что:** Алгоритм транспорта counterfactual quantities P*(Y_x) между доменами.

**Зачем:** Correa, Lee & Bareinboim (2022): counterfactual quantities (PN/PS/PNS, fairness metrics) можно транспортировать между доменами. Текущая transportability покрывает только Layer-2 (interventional). Layer-3 transport критичен для: fairness audits across populations, legal attribution across jurisdictions.

**Теория:** Counterfactual transportability uses selection diagrams + ctf-calculus to determine if P_t(Y_x = y) can be expressed using data from source domain(s).

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/ctf_transport.py` (новый файл):
  - `ctf_transportability(ctf_query: CtfQuery, selection_diagram: SelectionDiagram, source_domains: list[SourceDomain] | None = None) -> IdentificationResult`:
    - Step 1: Build AMN from target graph + ctf_query
    - Step 2: Augment AMN with S-nodes from selection diagram
    - Step 3: Apply ctf-calculus rules on augmented AMN
    - Step 4: If reduces to Layer-2 → delegate to tr_algorithm()
    - Step 5: If reduces to observational → IDENTIFIED
    - Step 6: If stuck → check ID* on augmented graph
    - Step 7: If non-identifiable → return NegativeCertificate with suggested experiments
    - Emits: CTF_TRANSPORT_* ProofStep entries
  - `ctf_transport_bounds(ctf_query, selection_diagram) -> tuple[float, float]`:
    - Partial identification bounds when exact transport fails
    - Extend Manski bounds to counterfactual setting
    - Uses LP framework from Phase 7.1

- `src/polisyos/foundry/methods/catalog/causal/id_engine.py`:
  - Обновить routing: если `counterfactual_query` + `s_nodes` → route to ctf_transportability

- `src/polisyos/foundry/methods/catalog/causal/data_fusion.py`:
  - Добавить mode `"ctf_fusion"` в DataFusionEngine
  - Delegates to ctf_transportability для Layer-3 fusion

**Тесты:**
- `tests/.../test_ctf_transport.py`:
  - `test_ctf_transport_pn_across_domains`: PN transportable через selection diagram
  - `test_ctf_transport_non_transportable`: Non-transportable counterfactual → NegativeCertificate
  - `test_ctf_transport_reduces_to_l2`: L3 query сводится к L2 transport
  - `test_ctf_transport_bounds`: Bounds когда exact transport fails
  - `test_ctf_transport_multi_domain`: mZ-ID для counterfactual queries

**Критерий:** 5 тестов; ctf-transport корректно использует AMN + ctf-calculus; integration с существующим tr_algorithm.

---

## Фаза 5: Cyclic ID — Engineering for Feedback Loops (ПЕРЕПИСАНА) ⚠️ RESEARCH TRACK

> **⚠️ Статус: Research / Experimental.** Идея «Tarjan SCC → condensation DAG → локально провалиться внутрь цикла → Wright path tracing / solver» инженерно привлекательна, но пока **не является теоремно эквивалентной реализацией ioID** (Forré & Mooij 2019). Их результат относится к более общей семантике ioSCMs (interventional-observational SCMs) и соответствующему расширенному calculus в циклическом случае — они не просто «схлопывают циклы и дальше делают обычный ID». Текущая версия Phase 5 — это **heuristic engineering approximation**, которая корректна для важного подкласса случаев (linear cyclic, supply-demand IV, simple feedback loops), но не даёт формальных гарантий sound-and-complete identification на произвольных cyclic ADMGs.
>
> **Критерий перехода из experimental в production:** каждый шаг алгоритма (`cyclic_id_algorithm`) привязан к конкретной теореме/леммe из Forré & Mooij 2019 или последующих работ, с формальным доказательством эквивалентности. До этого момента результаты cyclic_id маркируются `identification_confidence="experimental"` в `IdentificationResult`.

### 5.1 — Конденсация графа (Tarjan SCC)

**Что:** При обнаружении циклов — первым шагом конденсировать граф через Tarjan's algorithm для SCC.

**Зачем:** Наивная реализация DFS/BFS на циклических графах → экспоненциальный взрыв или бесконечная рекурсия. Конденсация схлопывает циклы в мета-узлы, граф мета-узлов — всегда DAG. Классические алгоритмы применяются на макро-уровне; внутрь мета-узлов «проваливаемся» только когда запрос затрагивает переменные внутри конкретного цикла. Время работы Tarjan — O(V+E).

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/admg_ops.py`:
  - `tarjan_scc(graph: CausalGraphModel) -> list[frozenset[str]]`:
    - Tarjan's algorithm для SCC на directed edges
    - Return: list of frozenset (каждый = одна SCC)
    - Singleton SCCs = ациклические переменные
  - `condense_graph(graph: CausalGraphModel, sccs: list[frozenset]) -> CausalGraphModel`:
    - Каждая SCC → мета-узел `SCC_{hash}`
    - Рёбра между SCC → рёбра между мета-узлами
    - Bidirected edges: если хотя бы одно bi-edge соединяет разные SCC → bidirected между мета-узлами
    - Результат: DAG (гарантированно ациклический)
  - `has_directed_cycle(graph) -> bool`:
    - Быстрая проверка: try `topological_order()`, catch ValueError → True

**Тесты:**
- `test_tarjan_scc_simple_cycle`: A→B→A → одна SCC {A,B}
- `test_condense_graph_is_dag`: condensed graph passes topological_order()
- `test_condense_preserves_non_cycle_edges`: edges between SCCs preserved

---

### 5.2 — Матричная σ-separation

**Что:** σ-separation через линейную алгебру вместо рекурсивного обхода путей.

**Зачем:** На циклических графах стандартный Bayes-Ball (m-separation) даёт **ложные результаты** — находит independences, которых нет в данных. Forre & Mooij ввели σ-separation, которая учитывает что переменные в одном цикле ведут себя как единый «запутанный узел» при достижении равновесия. Матричная реализация через NumPy/JAX — быстрее рекурсии.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/cyclic_id.py` (новый):
  - `build_sigma_connection_graph(graph) -> CausalGraphModel`:
    - σ-CG construction per Forre & Mooij 2019, Definition 3.1
    - Переменные внутри одной SCC → полностью связаны (σ-connected)
    - Bidirected edges между SCC сохраняются
  - `sigma_separation(graph, x_set, y_set, z_set) -> bool`:
    - **Матричная реализация:**
      1. Построить adjacency matrix A ∈ {0,1}^{n×n}
      2. Маскировать строки/столбцы Z (удаление путей через наблюдаемые)
      3. Транзитивное замыкание: `reach = (A_masked)^* = I + A + A² + ... ` → через `np.linalg.matrix_power` или `scipy.sparse`
      4. Проверка достижимости между σ-компонентами: `reach[X_mask, Y_mask] > 0`
    - Опционально: `jax.numpy` для GPU на графах > 200 nodes
    - Fallback: BFS-based для малых графов (< 50 nodes)
  - `cyclic_id_algorithm(treatment, outcome, graph, _depth=0) -> IdentificationResult`:
    - Step 1: `sccs = tarjan_scc(graph)`
    - Step 2: Если все SCCs singleton → delegate to standard `id_algorithm()`
    - Step 3: `condensed = condense_graph(graph, sccs)` — DAG мета-узлов
    - Step 4: На condensed graph — применить ID algorithm на уровне мета-узлов
    - Step 5: Для мета-узлов, содержащих treatment/outcome → «провалиться» внутрь:
      - Построить σ-CG для этой SCC
      - Применить σ-separation criterion
      - Если σ-separable → Wright's path tracing для estimand
      - Если нет → `well_posedness_check()` + HEDGE
    - Step 6: Well-posedness check: проверить что fixed-point уникален
    - Emits: CYCLIC_ID_* ProofStep entries
    - **⚠️ Result маркируется** `identification_confidence="experimental"` до формальной верификации эквивалентности с ioID
  - `well_posedness_check(graph, scm_spec) -> WellPosednessResult`:
    - Проверить что система уравнений в SCC имеет уникальный fixed-point
    - Для linear: det(I - A) ≠ 0 — **exact, sound and complete**
    - Для nonlinear: contraction mapping check (Lipschitz < 1) — **⚠️ approximate heuristic**
    - Если diverges (гиперинфляция) → каузальный эффект математически не определён
    - **⚠️ NP-hardness warning:** Проверка уникальности fixed-point для nonlinear systems — NP-hard в общем случае. Lipschitz check (`max(||∂f/∂x||) < 1`) — *sufficient* condition для уникальности (contraction mapping theorem), но **не necessary**. Это значит:
      - Lipschitz < 1 → guaranteed unique fixed-point (no false positives здесь)
      - Lipschitz ≥ 1 → **inconclusive**, не означает non-uniqueness (false negatives возможны)
      - **Но:** численная оценка Lipschitz constant через конечные разности может быть **заниженной** → false positive (утверждает well-posedness когда fixed-point не уникален)
    - `WellPosednessResult(BaseModel)`:
      - `well_posed: bool`
      - `method: Literal["exact_linear", "lipschitz_heuristic", "numerical_sampling"]`
      - `confidence: Literal["exact", "approximate"]` — exact для linear, approximate для nonlinear
      - `lipschitz_constant: float | None`
      - `warning: str | None` — "Nonlinear well-posedness check is approximate; false positives possible"
    - Для nonlinear: дополнительно `_multi_start_fixed_point_search(f, n_starts=50)`:
      - Запустить fixed-point iteration из n_starts random initial points
      - Если converges к >1 distinct fixed-point → well_posed=False, method="numerical_sampling"
      - Это тоже heuristic, но ловит очевидные multi-equilibria

**Тесты:**
- `test_sigma_separation_inside_scc`: переменные в одном цикле НЕ σ-separated
- `test_sigma_separation_cross_scc_matches_d_sep`: между SCCs — σ-sep == d-sep
- `test_cyclic_id_supply_demand`: Supply→Demand→Supply, IV available → identifiable
- `test_cyclic_id_feedback_no_iv`: Feedback без IV → non-identifiable + HEDGE
- `test_cyclic_id_delegates_to_acyclic`: No cycles → standard ID
- `test_well_posedness_divergent`: divergent cycle → error, not estimate
- `test_well_posedness_nonlinear_non_unique_fp`: Known system with 2 stable fixed-points (e.g., x = x³ - x + c) → well_posed=False detected via multi-start search. Regression test для false positives
- `test_well_posedness_linear_exact`: Linear system → exact det(I-A) check, confidence="exact"
- `test_matrix_sigma_sep_matches_bfs`: matrix == BFS result

**Критерий:** 9 тестов; cyclic identification correct; well-posedness: linear=exact, nonlinear=approximate with explicit warning; known non-unique system detected.

---

### 5.3 — CyclicExecutionBlock в ExecutorGraph (Estimation для циклов)

**Что:** Добавить `SolverNode` в ExecutorGraph для estimation внутри циклов.

**Зачем:** Стандартный `ExecutorNode` вызывает `predict()` последовательно. Но в циклическом SCM вход зависит от выхода — нужен итерационный solver (Picard iteration / Newton-Raphson).

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/estimand_compiler.py`:
  - `EstimandShape.CYCLIC = "cyclic"`
  - `EstimationStrategy.FIXED_POINT_SOLVER = "fixed_point_solver"`
  - Добавить `CyclicExecutionBlock(ExecutorNode)`:
    - `inner_nodes: tuple[ExecutorNode, ...]` — модели внутри цикла
    - `max_iterations: int = 100`
    - `convergence_tol: float = 1e-6`
    - `solver: Literal["picard", "newton", "jax_while"] = "picard"`
  - В `compile_to_method_dag_nodes()`: если EstimandShape.CYCLIC → обернуть nuisance nodes внутри SCC в CyclicExecutionBlock

- `src/polisyos/foundry/methods/catalog/causal/causal_engine.py`:
  - В `estimate()`: если node isinstance CyclicExecutionBlock:
    - **Picard iteration:**
      1. Init переменные в цикле средними значениями
      2. Прогнать predict по кругу: X_{t+1} = f(Y_t), Y_{t+1} = g(X_{t+1})
      3. Stop когда |X_{t+1} - X_t| < ε
    - **JAX-optimized:** `jax.lax.while_loop` для дифференцируемого fixed-point
    - Report `convergence_reached: bool` и `n_iterations: int`

**Тесты:**
- `test_solver_node_picard_converges`: linear cycle converges < 20 iterations
- `test_solver_node_divergent_warns`: divergent cycle → warning + best estimate

**Критерий:** 2 теста; convergence documented; divergent cases handled gracefully.

---

## Фаза 6: Усиление Layer-3 (NCM / Twin Networks / Actual Causality)

### 6.1 — Nonlinear abduction в NCM

**Что:** Замена текущего fallback `U = 0` для нелинейных уравнений на numerical solver.

**Зачем:** `_abduce_exogenous()` в `ncm_engine.py` при нелинейных structural equations дефолтит noise к 0 с warning. Это делает все counterfactual estimates biased для нелинейных моделей.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/ncm_engine.py`:
  - В `_abduce_exogenous()`:
    - Для `equation_type == "polynomial"`: аналитическое решение через `numpy.roots()` для степени ≤ 4
    - Для general nonlinear: `scipy.optimize.brentq()` или `scipy.optimize.fsolve()` для U в уравнении V = f(Pa, U)
    - Для multi-dimensional: `scipy.optimize.minimize()` с constraint U = V - f(Pa)
    - Fallback: MCMC sampling через manual Metropolis-Hastings (50-200 samples per node)
  - **⚠️ Multi-root failure mode:** `fsolve()` и `numpy.roots()` могут найти множественные решения. Квадратное уравнение — 2 корня. Какой брать? Без explicit policy — результат зависит от начальной точки (non-deterministic).
  - Добавить `root_selection_policy: Literal["closest_to_prior", "smallest_magnitude", "all_roots_mcmc"] = "closest_to_prior"`:
    - `"closest_to_prior"`: выбрать корень ближайший к prior mean E[U] (default: 0 для additive noise). Обоснование: в большинстве SCM noise модель предполагает U ≈ 0, отклонения — аномалии
    - `"smallest_magnitude"`: выбрать корень с min |U|. Консервативный выбор (minimum departure from structural equation)
    - `"all_roots_mcmc"`: не выбирать — вернуть все корни, взвесить по prior P(U), propagate uncertainty через posterior. Наиболее корректный, но дорогой (каждый root → отдельный counterfactual world → average)
  - При `len(roots) > 1`: emit warning в ProofStep: `"Multiple roots found for abduction of {var}: {roots}. Selected {chosen} via policy '{policy}'."`
  - Добавить `abduction_method="auto"` logic:
    - `"exact"` → closed-form (linear) или numerical (nonlinear)
    - `"mcmc"` → MCMC sampling
    - `"variational"` → mean-field variational inference (future extension)

**Тесты:**
- `tests/.../test_ncm_nonlinear_abduction.py`:
  - `test_abduction_quadratic`: V = aX² + bX + U → U recovered via quadratic formula
  - `test_abduction_multi_root_quadratic`: V = X² + U, observed V=4, X=1 → U=3 (only real root). Но V = X² + U с X=0, V=4 → U=4 (unique). Граничный случай: V = (X-U)² → два корня U = X ± √V. Проверить: `closest_to_prior` выбирает корень ближе к 0; `all_roots_mcmc` возвращает posterior average
  - `test_abduction_exponential`: V = exp(X) + U → numerical solver converges
  - `test_abduction_mcmc_convergence`: MCMC chains converge to true U (linear DGP for validation)
  - `test_abduction_multi_node`: Multi-node simultaneous abduction (3+ equations)
  - `test_abduction_root_selection_warning`: Multiple roots → warning в ProofStep trace

**Критерий:** 6 тестов; nonlinear abduction bias < 0.1 на synthetic DGP; MCMC within 2σ of truth; multi-root cases handled with explicit policy and warning.

---

### 6.2 — AC3 minimality для multi-variable causes

**Что:** Полная проверка AC3 для causes с |X| > 1.

**Зачем:** `_check_ac3_minimality()` в `actual_causality.py` trivially возвращает True для single-variable causes. Для multi-variable causes (X = {X1, X2, ...}) нужно проверить что никакое proper subset X' ⊂ X не удовлетворяет AC1+AC2. Без этого Halpern-Pearl definition неполная.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/actual_causality.py`:
  - Обновить `_check_ac3_minimality()`:
    - Если `len(cause_vars) == 1`: return True (как сейчас)
    - Если `len(cause_vars) > 1`:
      - Для каждого proper subset S ⊂ cause_vars (от |S|=|X|-1 вниз):
        - Проверить AC1 для S (S=s и Y=y оба имеют место)
        - Проверить AC2 для S (найти contingency set W)
        - Если оба True → AC3 violated (X не minimal)
      - Если ни один subset не satisfies → AC3 = True
    - Optimization: start с largest subsets (most likely to satisfy AC1+AC2)

**Тесты:**
- `tests/.../test_ac3_multi_variable.py`:
  - `test_ac3_pair_cause_minimal`: {X1, X2} minimal — neither alone satisfies AC2
  - `test_ac3_pair_cause_not_minimal`: {X1, X2} not minimal — X1 alone satisfies AC1+AC2
  - `test_ac3_triple_cause`: 3-variable cause minimality check (combinatorial)

**Критерий:** 3 теста; multi-variable AC3 correct; performance < 5s для |X| ≤ 5.

---

### 6.3 — Degree of Blame (Chockler-Halpern 2004)

**Что:** Добавить epistemic degree of blame в дополнение к degree of responsibility.

**Зачем:** Degree of Responsibility DR = 1/(|W_min|+1) — structural (зависит только от графа). Degree of Blame DB = E_u[DR(X→Y | u)] — epistemic, учитывает вероятность контекста. Необходимо для fairness applications и legal attribution.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/actual_causality.py`:
  - `_degree_of_blame(ncm, cause_var, cause_value, ..., context_distribution: dict[str, np.ndarray]) -> float`:
    - DB = E_u[DR(X→Y | u)] = Σ_u DR(X→Y | u) × P(u)
    - Monte Carlo: sample N contexts from context_distribution, compute DR for each, average
  - Обновить `HPResult`:
    - Добавить `degree_of_blame: float | None`
    - Добавить `blame_ci: tuple[float, float] | None` — bootstrap CI

**Тесты:**
- `tests/.../test_degree_of_blame.py`:
  - `test_blame_equals_responsibility_under_certain_context`: DB = DR when context is deterministic
  - `test_blame_less_than_responsibility_under_uncertainty`: DB ≤ DR in general (Jensen's inequality)

**Критерий:** 2 теста; blame ≤ responsibility; CI valid.

---

## Фаза 7: Bounds и Partial Identification

### 7.1 — Partial Identification Bounds (Balke-Pearl LP + Autobounds polynomial programming)

**Что:** Два уровня partial identification: (1) LP bounds для binary/discrete special cases, (2) polynomial programming bounds для general discrete settings (Autobounds).

**⚠️ Математическая точность:** Autobounds (Duarte et al. 2023) — это **не** просто LP-framework для любого ADMG. Общий подход формулируется как сведение к **polynomial programming problems** с dual relaxation и branch-and-bound. LP-формулировки корректны и exact для binary/small-discrete переменных с ограниченным числом response functions. Для general discrete settings (multi-valued, complex graphs) constraints становятся полиномиальными, и LP relaxation даёт **не** sharp bounds. Заявлять "general LP sharp bounds" — перезаявление.

**Архитектура (два уровня):**
1. **LP bounds (exact для binary/small discrete):** Balke-Pearl response function framework → LP → sharp bounds. Работает когда все переменные binary или когда response function space конечен и перечислим.
2. **Polynomial bounds (general discrete, Autobounds-style):** Polynomial programming → LP/SDP relaxation → branch-and-bound tightening. Bounds могут не быть sharp — это *outer approximation*. Честно маркировать: `bounds_type: Literal["sharp_lp", "relaxed_polynomial"]`.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/lp_bounds.py` (новый файл):
  - `auto_bounds(query, graph, data, constraints=None) -> PartialIdentificationResult`:
    - Step 1: Check variable cardinalities. If all binary → LP path (exact). If multi-valued → polynomial path.
    - **LP path (binary/small discrete):**
      - Enumerate all response functions per Balke-Pearl framework
      - Build LP: minimize/maximize query subject to observational constraints
      - Solve via `scipy.optimize.linprog()`
      - Return sharp bounds [lb, ub], `bounds_type="sharp_lp"`
    - **Polynomial path (general discrete):**
      - Formulate polynomial constraints on response function probabilities
      - LP relaxation: linearize polynomial constraints → outer bound
      - Optional: `cvxpy` SDP relaxation для tighter bounds (lazy import)
      - Optional: branch-and-bound tightening (iterative refinement)
      - Return bounds [lb, ub], `bounds_type="relaxed_polynomial"`, `relaxation_gap: float`
  - `build_response_function_constraints(graph, data) -> tuple[np.ndarray, np.ndarray]`:
    - Constraint matrix A and vector b from observational distribution
    - Each response function = deterministic mapping from parents to child
    - Probability constraints: Σ q_r = P(observed pattern)
  - `build_query_objective(query, response_functions) -> np.ndarray`:
    - Objective vector c for LP (linear in response function probabilities)
  - `PartialIdentificationResult` расширен:
    - `bounds_type: Literal["sharp_lp", "relaxed_polynomial", "manski"]`
    - `relaxation_gap: float | None` — оценка зазора между relaxed и true bound (для polynomial path)
  - **⚠️ Continuous variables — discretization is NOT trivial:**
    Discretization для bounds — не просто потеря точности, а потенциально **некорректные bounds**. Направление ошибки зависит от метода:
    - **Outer approximation (conservative):** discretized bins → LP на bin probabilities. Bounds **шире** чем истинные (valid but not sharp). Гарантия: истинное значение ∈ [lb_disc, ub_disc]. Это safe default.
    - **Inner approximation (aggressive):** discretize query function → LP. Bounds могут быть **уже** чем истинные (potentially invalid!). Опасно — может пропустить true effect.
    - **Наш подход:** всегда outer approximation (conservative discretization). Bins → joint probability constraints → LP. Bounds valid но шире. С adaptive refinement — converge к true bounds.
  - `_discretize_continuous_for_bounds(data, variable, n_bins=10, method="equal_frequency") -> DiscretizedVariable`:
    - `method: Literal["equal_frequency", "equal_width", "adaptive"]`
    - `adaptive`: начать с n_bins=10, проверить convergence, удвоить bins, повторить до convergence или max_bins=100
    - Return: bin edges, bin probabilities, discretization metadata
  - `_adaptive_grid_refinement(query, graph, data, initial_bins=10, max_bins=100, convergence_tol=0.01) -> PartialIdentificationResult`:
    - Step 1: Compute bounds с initial_bins
    - Step 2: Double bins → recompute
    - Step 3: If |bounds_new - bounds_old| < tol → converged
    - Step 4: Else → continue до max_bins
    - Report: `n_refinement_steps`, `converged: bool`, `convergence_gap: float`
  - Support: binary variables (exact LP), general discrete (polynomial + relaxation), continuous (outer-approximation discretization + adaptive grid + convergence check)
  - `PartialIdentificationResult` дополнительно:
    - `discretization_method: str | None`
    - `n_bins_final: int | None`
    - `discretization_converged: bool | None`

- `src/polisyos/foundry/methods/catalog/causal/bounds_engine.py`:
  - Добавить `auto_bounds` в list of methods
  - Route `BOUNDS_ONLY` shape через auto_bounds когда graph available
  - Auto_bounds as first method in priority order (tightest bounds)

**Тесты:**
- `tests/.../test_lp_bounds.py`:
  - `test_lp_bounds_binary_iv_matches_balke_pearl`: LP bounds = closed-form Balke-Pearl на binary IV (exact, sharp)
  - `test_lp_bounds_tighter_than_manski`: LP ≤ Manski (always, on 5 different graphs)
  - `test_lp_bounds_frontdoor_example`: Bounds на frontdoor graph (should be tight = point identified)
  - `test_lp_bounds_with_monotonicity`: MTR constraint tightens bounds vs unconstrained
  - `test_polynomial_bounds_multi_valued`: Multi-valued (cardinality 4) → polynomial path → bounds_type="relaxed_polynomial"
  - `test_continuous_bounds_converge_with_refinement`: Continuous variable → adaptive grid → bounds at bins=100 within 0.01 of bounds at bins=50 (convergence). Outer approximation: bounds wider than analytic truth (if known)

**Критерий:** 6 тестов; LP bounds exact для binary; polynomial bounds honest about gap; continuous bounds via outer approximation with adaptive refinement and convergence check.

---

### 7.2 — Transport-specific partial identification

**Что:** Bounds на transport formula когда exact transportability fails.

**Зачем:** Сейчас при non-transportability fallback — generic Manski bounds, которые не учитывают partial knowledge из selection diagram. Transport-aware bounds учитывают: какие S-nodes удалось eliminate, какие остались. Результат — tighter intervals.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/transport_bounds.py` (новый файл):
  - `transport_bounds(query, selection_diagram, data_source, data_target) -> PartialIdentificationResult`:
    - Use LP-bounds framework (Phase 7.1) but with selection diagram constraints
    - S-nodes contribute known mechanism differences as inequality constraints
    - Partially eliminated S-nodes → mixed observational/experimental constraints
    - Tighter than generic Manski
  - Integration с `transport_engine.py`: когда exact transport fails, try transport_bounds before Manski fallback

**Тесты:**
- `tests/.../test_transport_bounds.py`:
  - `test_transport_bounds_tighter_than_manski`: Transport bounds ⊆ Manski bounds (on 3 graphs)
  - `test_transport_bounds_with_partial_s_elimination`: Some S-nodes eliminated, remaining → bounds tighter

**Критерий:** 2 теста; bounds tighter than Manski when partial S-node elimination possible.

---

## Фаза 8: Усиление Estimation Methods

### 8.1 — TMLE для NDE/NIE (Targeted Learning for Mediation)

**Что:** Targeted Minimum Loss-based Estimation для natural direct/indirect effects.

**Зачем:** Текущий `path_specific.py` использует EIF-based estimation. TMLE обеспечивает: (1) finite-sample coverage guarantees, (2) double robustness, (3) honest CI. Zheng & van der Laan (2012) доказали что TMLE-NDE/NIE asymptotically efficient.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/path_specific.py`:
  - Добавить `_tmle_nde_nie()`:
    - Step 1: Initial estimates Q_0(M,T,X), g(T|X), h(M|T,X) via SuperLearner (Phase 12.2)
    - Step 2: Clever covariate H_NDE = I(T=t)/g(T|X) × [h(M|T=0,X)/h(M|T,X)]
    - Step 3: Targeting step: logistic submodel Q_ε = expit(logit(Q_0) + ε × H_NDE)
    - Step 4: Solve score equation for ε* via Newton-Raphson (1-2 iterations)
    - Step 5: NDE/NIE from Q_{ε*}
    - Step 6: Variance via sandwich estimator on targeting residuals
  - Добавить option `method="tmle"` в `PathSpecificEffectEstimator`

**Тесты:**
- `tests/.../test_tmle_mediation.py`:
  - `test_tmle_nde_coverage`: 95% CI coverage ≥ 93% на 200 Monte Carlo runs (n=500 each)
  - `test_tmle_nde_agrees_with_eif`: TMLE NDE ≈ EIF NDE ± 0.05 (consistency check)

**Критерий:** 2 теста; coverage ≥ 93%; TMLE ≈ EIF estimate.

---

### 8.2 — Causal BCF (Bayesian Causal Forests) для CATE

**Что:** BCF (Hahn, Murray & Carvalho, 2020) для heterogeneous treatment effect estimation — **не** vanilla Causal BART.

**Зачем:** BCF принципиально лучше vanilla BART для каузальной инференции. Ключевая архитектура:
```
Y = μ(x) + τ(x)·T + ε
```
где μ(x) — прогностическая функция (baseline outcome без treatment), τ(x) — treatment effect function. Каждая моделируется **отдельным** BART ensemble с разными priors. Vanilla подход (один BART для E[Y|X,T], потом разница предсказаний) страдает от **regularization-induced confounding (RIC)**: если treatment effect мал относительно прогностической функции, единый BART "забивает" на τ(x) в пользу лучшей подгонки μ(x). BCF решает это структурно через RIC prior — prior на τ(x) shrinks к нулю, предотвращая переоценку heterogeneity.

**⚠️ Ландшафт реализаций и выбор зависимостей:**
- `bartpy` — **заброшен** (последний коммит 2019). Не рассматривать.
- `pymc-bart` — привязан к PyMC (тянёт PyTensor), медленный, тяжёлая зависимость. Только для пользователей уже в PyMC экосистеме.
- `stochtree` (`pip install stochtree`) — **наиболее активно развиваемая** реализация от группы Hahn/Murray. C++ с Python bindings. Поддерживает BCF, XBART (accelerated grow-from-root sampling, 10-50x ускорение vs standard MCMC), warm-start, RIC prior из коробки. Легче чем PyMC.
- `dbarts` (R) — зрелая C-based реализация. Python через rpy2 — хрупко.

**⚠️ Ecosystem isolation:** stochtree использует собственный C++ backend (не PyMC, не JAX). Конфликтов с JAX нет при stochtree. Для pymc-bart fallback: MCMC через PyTensor vs JAX JIT → изоляция через subprocess executor, numpy-copy, no GPU sharing. BART-ноды маркируются `executor_isolation="subprocess"` при pymc-bart backend.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/causal_bcf.py` (новый файл — **переименован** из causal_bart.py):
  - `@foundry_method(namespace="causal.hte", version="1.0.0") class CausalBCF`:
    - **Primary backend: `stochtree.BCFModel`** (lazy import):
      ```python
      from stochtree import BCFModel
      bcf = BCFModel()
      bcf.sample(X_train, Z_train, y_train, X_test, Z_test,
                 num_gfr=100,       # grow-from-root (XBART) warmup
                 num_mcmc=200,       # MCMC samples
                 num_trees_mu=200,   # trees for prognostic function
                 num_trees_tau=50)   # trees for treatment effect (fewer = more shrinkage)
      tau_hat = bcf.predict_tau(X_test, Z_test)  # posterior mean CATE
      tau_samples = bcf.predict_tau_raw(X_test, Z_test)  # posterior draws
      ```
    - `pure_step()`:
      - Step 1: Fit BCF с separate μ(x) и τ(x) ensembles + RIC prior
      - Step 2: XBART sampling (grow-from-root) для ускорения convergence
      - Step 3: Posterior samples → pointwise credible intervals для τ(x)
      - Step 4: Posterior mean τ̂(x) как point estimate CATE
    - **Fallback 1: sklearn-based pseudo-BCF** (если stochtree недоступен):
      - GradientBoostingRegressor для μ̂(x) на control group (T=0)
      - GradientBoostingRegressor для τ̂(x) на residuals (Y - μ̂(x)) / T
      - Bootstrap (200 resamples) для uncertainty (не posterior, но pragmatic)
      - ⚠️ Warning: "Using sklearn pseudo-BCF fallback; no true Bayesian posterior"
    - **Fallback 2: `pymc-bart`** (lazy import, только если пользователь в PyMC экосистеме):
      - `executor_isolation: str = "subprocess"` — изоляция от JAX runtime
      - Full Bayesian posterior, но медленный
    - `__determinism_tier__ = "STATISTICAL"`
    - `backend: Literal["stochtree", "sklearn", "pymc"] = "auto"`:
      - `"auto"`: try stochtree → sklearn → pymc, в порядке приоритета
  - Зарегистрировать в `causal.hte` namespace

**Тесты:**
- `tests/.../test_causal_bcf.py`:
  - `test_bcf_cate_recovers_truth`: Linear CATE τ(x) = βx → BCF RMSE < 0.3 (stochtree backend)
  - `test_bcf_beats_vanilla_bart_on_ric`: DGP с strong μ(x), weak τ(x) (RIC scenario) → BCF RMSE < vanilla BART RMSE. Это ключевой тест: доказывает преимущество BCF архитектуры
  - `test_bcf_posterior_coverage`: Posterior CI covers true τ in ≥ 90% of points
  - `test_bcf_sklearn_fallback`: stochtree unavailable → sklearn pseudo-BCF + warning в output
  - `test_bcf_graceful_degradation_chain`: No stochtree, no pymc → sklearn fallback works; no sklearn → CausalForest ultimate fallback

**Критерий:** 5 тестов; BCF beats vanilla BART on RIC scenario; posterior calibration; 3-tier fallback chain works end-to-end.

---

### 8.3 — Augmented Synthetic Control (Ben-Michael et al. 2021)

**Что:** Ridge-augmented synthetic control method.

**Зачем:** Текущий synthetic control — vanilla Abadie (2003). Augmented SCM adds bias correction through ridge regression, improving finite-sample coverage when parallel trends holds only approximately.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/synthetic_control.py`:
  - Добавить `augmented_synthetic_control()`:
    - Step 1: Fit standard SC weights w via quadratic program (minimize ||Y_treated_pre - Σ w_j Y_j_pre||²)
    - Step 2: Fit ridge regression on pre-treatment residuals: r_j = Y_treated_pre - Σ w_j Y_j_pre
    - Step 3: Augmented estimate: τ_t = Y_treated_t - Σ w_j Y_j_t - ridge_correction_t
    - Step 4: Jackknife CI per Ben-Michael et al. 2021 (leave-one-unit-out)
  - Register as `causal.inference.augmented_synthetic_control`

**Тесты:**
- `tests/.../test_augmented_sc.py`:
  - `test_augmented_sc_bias_correction`: Augmented ATT closer to true ATT than vanilla when pre-trends diverge slightly

**Критерий:** 1 тест; bias reduction demonstrated on synthetic DGP with imperfect parallel trends.

---

## Фаза 9: Causal Fairness (Plecko-Bareinboim 2024 полная)

### 9.1 — Полная реализация Standard Fairness Model

**Что:** Каузальная модель справедливости с path-specific counterfactual decomposition.

**Зачем:** Plecko & Bareinboim (FnTML 2024) определяют Standard Fairness Model (SFM) с формальной декомпозицией: TV = Ctf-DE + Ctf-IE + Ctf-SE (direct, indirect, spurious effects). Это единственная математически обоснованная decomposition дискриминации, aligned с legal doctrines (disparate impact, disparate treatment). Текущий `causal_fairness.py` — отсутствует или неполный.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/causal_fairness.py` (создать/переписать):
  - `StandardFairnessModel(BaseModel, frozen=True, extra="forbid")`:
    - `protected_attribute: str` — A (e.g., race, gender)
    - `mediators: list[str]` — M (e.g., education, experience)
    - `outcome: str` — Y (e.g., hiring decision, salary)
    - `confounders: list[str]` — C
    - `graph: CausalGraphModel` — causal graph encoding assumptions
  - `tv_decomposition(sfm: StandardFairnessModel, data: dict) -> FairnessDecomposition`:
    - TV(a, a') = Ctf-DE(a, a') + Ctf-IE(a, a') + Ctf-SE(a, a')
    - Ctf-DE = E[Y_{a,M_{a'}} - Y_{a',M_{a'}}] — direct discrimination (effect NOT through mediators)
    - Ctf-IE = E[Y_{a,M_a} - Y_{a,M_{a'}}] — indirect discrimination (effect THROUGH mediators)
    - Ctf-SE = E[Y_{a',M_{a'}}] - E[Y_{a'}] — spurious correlation (confounding, not causal)
    - Estimation via EIF-based estimator from path_specific.py
  - `identify_fairness_effects(sfm) -> dict[str, IdentificationResult]`:
    - Check which of Ctf-DE, Ctf-IE, Ctf-SE are identifiable from observational data
    - Uses id_star_algorithm (Phase 1.1) for each counterfactual quantity
    - Returns: {"ctf_de": IdentificationResult, "ctf_ie": ..., "ctf_se": ...}
  - `fairness_bounds(sfm, data) -> dict[str, tuple[float, float]]`:
    - When effects are not point-identified → LP bounds (Phase 7.1)
    - Returns: bounds per effect type
  - `@foundry_method(namespace="causal.fairness", version="1.0.0") class CausalFairnessEngine`:
    - Methods: "tv_decomposition", "path_specific", "counterfactual", "bounds"
    - `pure_step()` dispatches to appropriate method
  - `FairnessDecomposition(BaseModel)`:
    - `total_variation: float`
    - `ctf_direct_effect: float`
    - `ctf_indirect_effect: float`
    - `ctf_spurious_effect: float`
    - `decomposition_valid: bool` — sum ≈ TV check
    - `identification_status: dict[str, str]` — per-effect status

**Тесты:**
- `tests/.../test_causal_fairness_sfm.py`:
  - `test_tv_decomposition_sums_to_tv`: |Ctf-DE + Ctf-IE + Ctf-SE - TV| < 0.02
  - `test_sfm_identification`: All 3 effects identifiable на graph without A↔Y latent confounder
  - `test_sfm_partial_identification`: A↔Y confounder → Ctf-DE non-identifiable → bounds returned
  - `test_fairness_audit_pipeline`: Full pipeline от graph definition → FairnessDecomposition → report

**Критерий:** 4 теста; decomposition sums correctly; identification via ID*; bounds when effects non-identifiable.

---

## Фаза 10: Interference / Network Effects

### 10.1 — Graph-based identification под interference

**Что:** Formal causal diagram-based identification для network causal effects.

**Зачем:** Текущий `interference.py` — чисто estimation-based (4 estimators: Hudgens-Halloran, Network AIPW, Spatial, Bipartite). Не хватает identification step: graph-based проверка SUTVA violation, construction of augmented interference graph, modified ID algorithm с exposure mapping. Ogburn & VanderWeele (2014) предложили causal diagrams для interference — нужно integration.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/interference.py`:
  - Добавить `identify_interference_effect(graph: CausalGraphModel, treatment: str, outcome: str, exposure_mapping: str, cluster_var: str | None = None) -> IdentificationResult`:
    - Step 1: Check SUTVA via graph structure — if no edges between units → standard ID, no interference
    - Step 2: If interference detected: construct augmented graph:
      - Add exposure variable E_i = f(A_{neighbors(i)}) per exposure_mapping
      - Add edges from neighbor treatments to E_i
      - Add edge from E_i to Y_i (spillover path)
    - Step 3: Apply modified ID algorithm on augmented graph
    - Step 4: Return estimand with interference-specific nuisance parameters (exposure propensity, cluster propensity)
    - Emits: INTERFERENCE_ID_* ProofStep entries
  - Добавить `InterferenceAugmentedGraph(BaseModel)`:
    - `original_graph: CausalGraphModel`
    - `exposure_nodes: list[str]` — added E_i nodes
    - `cluster_partition: list[frozenset[str]]` — cluster structure
    - `interference_type: Literal["partial", "network", "spatial", "bipartite"]`

**Тесты:**
- `tests/.../test_interference_identification.py`:
  - `test_interference_id_no_interference`: No between-unit edges → standard ID, SUTVA holds
  - `test_interference_id_partial`: Cluster-level interference → stratified identification с cluster propensity

**Критерий:** 2 теста; graph-based identification before estimation; augmented graph construction correct.

---

## Фаза 11: Missing Data (M-graphs) усиление

### 11.1 — Testable implications из M-graph

**Что:** Автоматическая генерация тестируемых ограничений из M-graph structure.

**Зачем:** Mohan & Pearl (2021) показывают что M-graph implies specific conditional independence constraints AMONG proxy variables and missingness indicators. Эти constraints можно тестировать на данных для валидации missingness assumptions — если тест fails, M-graph неправильно специфицирован.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/missing_data.py`:
  - Добавить `testable_implications(mgraph: CausalGraphModel, mgraph_meta: MGraphMetadata) -> list[ConditionalIndependence]`:
    - `ConditionalIndependence = namedtuple("ConditionalIndependence", ["x", "y", "z"])` — X ⊥ Y | Z
    - Extract all CI constraints implied by M-graph via m-separation (d-separation on ADMG)
    - Filter to testable ones: only those involving observed variables + proxy variables + indicators
    - Exclude constraints involving latent substantive variables (untestable)
    - Return sorted by number of conditioning variables (simplest first)
  - Добавить `test_mgraph_implications(data: np.ndarray, implications: list[ConditionalIndependence], alpha: float = 0.05) -> TestReport`:
    - For each CI: statistical test:
      - Continuous variables: Fisher-z partial correlation test
      - Categorical variables: G-test (log-likelihood ratio)
      - Mixed: conditional mutual information via KNN (Frenzel & Pompe 2007)
    - Multiple testing correction: Benjamini-Hochberg (FDR control)
    - `TestReport(BaseModel)`:
      - `implications_tested: int`
      - `implications_passed: int`
      - `implications_failed: list[tuple[ConditionalIndependence, float]]` — (CI, p-value)
      - `overall_valid: bool` — all passed after correction

**Тесты:**
- `tests/.../test_mgraph_implications.py`:
  - `test_implications_generated`: M-graph with 3 substantive vars + 3 indicators → ≥ 1 testable implication
  - `test_implications_hold_on_correct_data`: Data generated from correct M-graph → all tests pass (p > alpha)

**Критерий:** 2 теста; implications correctly derived from graph via m-separation; statistical tests valid.

---

## Фаза 12: Advanced Estimation Upgrades

### 12.1 — Higher-order EIF (Robins et al.)

**Что:** Second-order influence functions для bias reduction.

**Зачем:** Standard EIF gives √n convergence rate. Higher-order EIF enables n^{2/3} convergence under sufficient smoothness of nuisance functions. Critical для сложных estimands (data fusion, mediation) where standard plug-in bias is O(n^{-1/4}).

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/eif_bounds.py`:
  - Добавить `compute_second_order_eif(first_order_scores: np.ndarray, nuisance_derivatives: dict[str, np.ndarray]) -> SecondOrderEIF`:
    - `SecondOrderEIF(BaseModel)`:
      - `scores: np.ndarray` — second-order influence function values ψ₂
      - `bias_correction: float` — estimated second-order bias
      - `corrected_estimate: float` — θ̂ - bias_correction
      - `corrected_se: float` — adjusted standard error
    - Second-order remainder: R₂ = Ψ(P) - Ψ(P₀) - E_{P₀}[ψ₁] - (1/2)E_{P₀}[ψ₂]
    - Require: Fréchet derivatives of first-order EIF w.r.t. nuisance parameters
  - Integration: если `nuisance_derivatives` available in node_outputs → автоматически compute bias correction
  - Attach to EvidenceBundle diagnostics: `second_order_bias_correction: float | None`

**Тесты:**
- `tests/.../test_higher_order_eif.py`:
  - `test_second_order_bias_reduction`: Bias of corrected estimator < bias of first-order on 500-sample DGP

**Критерий:** 1 тест; demonstrable bias reduction on finite-sample DGP.

---

### 12.2 — SuperLearner Cross-Validation Stacking

**Что:** Полноценный SuperLearner с cross-validated stacking для nuisance estimation.

**Зачем:** SuperLearner (van der Laan et al. 2007) — optimal combination of candidate learners. Текущий SuperLearner существует — убедиться в полноте: (1) V-fold CV with honest out-of-fold predictions, (2) non-negative least squares для weights, (3) screening rules, (4) discrete SuperLearner option.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/superlearner.py`:
  - Проверить и дополнить:
    - `_nnls_weights(cv_predictions, y_true)`: non-negative least squares stacking via `scipy.optimize.nnls`
    - `_cv_risk(learner, X, y, n_folds)`: V-fold CV risk estimation (MSE for continuous, log-loss for binary)
    - `_discrete_sl(cv_risks)`: select single best learner (minimum CV risk) — no combination
    - Library candidates: Ridge, Lasso, RandomForest, GradientBoosting, KNN (at minimum 5 candidates)
  - Добавить `SuperLearnerConfig(BaseModel)`:
    - `n_folds: int = 10` — V-fold CV
    - `method: Literal["nnls", "discrete", "loglik"] = "nnls"` — combination method
    - `screen: bool = True` — pre-screening via univariate p-values (keep top-k features)
    - `candidates: list[str] = ["ridge", "lasso", "rf", "gbm", "knn"]`
    - `nested_cv: bool = True` — Nested CV для мета-лернера (защита от переобучения стакинга)
  - **⚠️ Nested CV обязателен:** На малых выборках (n < 500) стандартный SuperLearner переобучает мета-лернер к in-fold predictions. Решение — Nested CV (двойная петля):
    - Outer loop: K-fold split для оценки итогового SuperLearner
    - Inner loop: V-fold split внутри каждого outer fold для обучения мета-весов
    - `_nested_cv_weights(X, y, candidates, n_outer=5, n_inner=10) -> np.ndarray`:
      - Для каждого outer fold: fit SuperLearner на inner CV → predict на outer test
      - Итоговый risk = средний по outer folds (honest estimate)
    - Computational cost: K×V fits вместо V fits, но защищает от catastrophic overfitting при n < 500

**Тесты:**
- `tests/.../test_superlearner_complete.py`:
  - `test_sl_nnls_weights_sum_to_one`: Weights ∈ [0,1], sum ≈ 1.0 ± 0.01
  - `test_sl_discrete_selects_best`: Discrete SL = argmin CV risk among candidates
  - `test_sl_cv_risk_decreases_with_data`: Risk at n=1000 < Risk at n=200 (learning works)
  - `test_sl_nested_cv_no_overfit_small_sample`: На n=200 Nested CV risk ≥ standard CV risk (no optimistic bias)

**Критерий:** 4 теста; NNLS weights valid; risk monotone in n; nested CV не даёт оптимистичного bias на малых выборках.

---

## Фаза 13: Optimal Experimental Design усиление

### 13.1 — Bayesian Adaptive Randomization

**Что:** Response-adaptive randomization с Thompson sampling.

**Зачем:** Текущий `optimal_design.py` uses equal budget allocation across stages. Bayesian adaptive design distributes more patients/units to the better-performing arm, reducing ethical cost while maintaining statistical validity. Thompson Sampling — provably optimal asymptotically.

**Файлы:**
- `src/polisyos/foundry/methods/catalog/causal/optimal_design.py`:
  - Добавить mode `"adaptive_bayesian"` в `CausalExperimentDesigner`:
    - Thompson Sampling: sample θ_k ~ Beta(α_k, β_k), assign unit to argmax θ_k
    - Posterior update: α_k += successes, β_k += failures (binary outcome)
    - For continuous outcomes: Normal-Normal conjugate (μ ~ N(μ_0, σ²/n))
    - Allocation ratio adapts over time toward better arm
    - Report: per-stage allocation proportions, posterior means, regret
  - Добавить `D_optimal_design(graph: CausalGraphModel, treatment: str, outcome: str, n_covariates: int) -> DesignMatrix`:
    - Fisher information matrix I(θ) = E[∇² log L]
    - Select covariates that maximize det(I(θ)) — D-optimality
    - Uses convex optimization (`scipy.optimize.minimize`) on covariate inclusion matrix
    - Output: selected covariates + optimal allocation proportions

**Тесты:**
- `tests/.../test_adaptive_design.py`:
  - `test_thompson_concentrates_on_best_arm`: After 100 rounds with effect_size=0.5, >70% allocation to best arm
  - `test_d_optimal_variance`: D-optimal design ATE variance ≤ random allocation ATE variance (on same n)

**Критерий:** 2 теста; Thompson concentrates; D-optimal reduces variance.

---

## Фаза 14: Symbolic Gold-Suite (Identification Regression Tests) — РАСШИРЕНА

### 14.1 — ID/IDC/ID*/IDC* Symbolic Correctness

**Что:** Curated gold-suite по всем identification алгоритмам с known ground truth из литературы.

**Зачем:** Это **главный benchmark**. Публичные наборы (ACIC, LBIDD) не проверяют правильность identification, proof trace, hedge/non-ID certificates. Для символического engine ложноположительное доказательство — тяжелейшая ошибка. y0 algorithm reference — каркас для кейсов.

**Что включить:**
1. **Положительные cases**: identifiable / transportable / recoverable
2. **Отрицательные cases**: hedge, recanting witness, non-transportable, non-recoverable under MNAR
3. **Exact-form tests**: совпадение нормализованной формулы estimand
4. **Certificate tests**: тип и локализация причины отказа (HedgeCertificate fields)
5. **Proof-trace tests**: минимальный корректный набор шагов (rule names + order)

**Файлы:**
- `tests/.../test_symbolic_gold_suite.py`:
  - **ID (Shpitser & Pearl 2006 Table 1):** 8 графов с known status
  - **IDC:** 3 conditional identification cases
  - **ID*:** 5 counterfactual identification cases (ETT, PNS, nested)
  - **IDC*:** 3 conditional counterfactual cases
  - **z-ID (Bareinboim & Pearl 2012):** 4 surrogate experiment cases
  - **mz-ID:** 3 multi-domain cases
  - **Transportability (Bareinboim & Pearl 2012 Figure 2):** 4 selection diagram cases
  - **Counterfactual Transportability (Correa-Lee-Bareinboim 2022):** 3 L3 transport cases
  - **Cyclic ID (Forre & Mooij 2019):** 2 cyclic cases
  - **σ-calculus (Correa & Bareinboim 2020):** 3 stochastic intervention cases
  - **ctf-calculus (Correa & Bareinboim 2025):** 3 ctf-rule application cases
  - **M-graph (Mohan & Pearl 2021 Figure 3):** 4 recoverability cases
  - **Napkin graph:** frontdoor identifiable
  - **Bow-arc:** non-identifiable (HEDGE)
  - **Verma constraints:** implied equality constraints
  - **Negative cases:** каждый алгоритм с 2+ graphs гарантированно non-identifiable

- `tests/.../test_transport_properties.py`:
  - 4 property-based теста с Hypothesis (random selection diagrams)

**Критерий:** ≥ 50 символических тестов; **100% correctness** на всех. Ложноположительное identification = test failure.

---

## Фаза 15: 6-контурный Benchmark Harness (НОВАЯ)

### 15.1 — Benchmark Infrastructure

**Что:** Единый benchmark harness с 6 контурами тестирования.

**Зачем:** «Лучшая система» = доминирование не по одной метрике, а по всему стеку. Нужно одновременно доказать: (1) символическую корректность, (2) конкурентную estimation accuracy, (3) discovery-состоятельность, (4) уникальные capability wins, (5) воспроизводимость.

**Файлы:**
- `benchmarks/` (новая директория):
  - `benchmarks/harness.py` — unified benchmark runner
  - `benchmarks/metrics.py` — standard evaluation metrics
  - `benchmarks/conftest.py` — shared fixtures

### 15.2 — Контур 1: Symbolic / Identification (свой gold-suite) — ГЛАВНЫЙ

**Зачем:** Для этого класса системы это главный benchmark. ACIC/LBIDD не проверяют identification correctness.

**Реализация:** Ссылка на Phase 14 (test_symbolic_gold_suite.py). Дополнительно:
- `benchmarks/symbolic/run_symbolic_benchmark.py`:
  - Загрузить все графы из gold-suite
  - Для каждого: measure time, memory, correctness, proof-step count
  - Compare с y0 output (если установлен): assert PolicyOS == y0 на identifiable status
  - Report: per-algorithm accuracy, timing, false-positive rate

**Бар:** 100% correctness. Ложноположительное identification = блокер.

### 15.3 — Контур 2: Effect Estimation (ACIC + LBIDD + RealCause)

**Порядок интеграции:**
1. **ACIC 2016/2017** — классический semi-synthetic для ATE/CATE под сильным confounding
2. **IBM LBIDD** — масштабируемый semi-synthetic на real covariates
3. **RealCause** — realism check с generative ground truth

**Файлы:**
- `benchmarks/estimation/acic_benchmark.py`:
  - Загрузить ACIC 2016 dataset (77 DGPs × 100 replications)
  - Run PolicyOS pipeline: graph → identify → compile → estimate
  - Metrics: ATE bias, RMSE, CI coverage, CI width
  - Compare с BART, TMLE, DML baselines
- `benchmarks/estimation/lbidd_benchmark.py`:
  - IBM benchmark: population + individual effect
  - Metrics: PEHE (precision in estimation of HTE), ATE bias
- `benchmarks/estimation/realcause_benchmark.py`:
  - RealCause datasets
  - Metrics: same + distributional divergence

**Бар:** средний ранг не хуже top-2; отклонение от лучшего ≤ 5-10%; **ни одного провала** ниже top quartile.

### 15.4 — Контур 3: HTE / Policy Learning

**Файлы:**
- `benchmarks/hte/interpretable_hte_benchmark.py`:
  - Benchmark из "Benchmarking HTE through Interpretability"
  - Metrics: CATE quality + ability to find predictive covariates (effect modifiers)
  - Важно: проверяет не только estimator, а pipeline выбора estimand→estimator

### 15.5 — Контур 4: Discovery (CauseMe + Sachs + Tübingen + CausalBench)

**Файлы:**
- `benchmarks/discovery/causeme_benchmark.py`:
  - CauseMe platform datasets (time-series + simulated)
  - Metrics: AUROC, F1 по edge recovery
- `benchmarks/discovery/sachs_benchmark.py`:
  - Sachs et al. (2005) — 11-node protein signaling network
  - Metrics: SHD (structural Hamming distance), precision, recall
- `benchmarks/discovery/tuebingen_benchmark.py`:
  - Tübingen cause-effect pairs (pairwise direction)
  - Metrics: accuracy of direction
- `benchmarks/discovery/causalbench_benchmark.py`:
  - CausalBench — large-scale perturbational single-cell
  - Metrics: AUROC, interventional accuracy

**Бар:** стабильный top quartile. Если discovery слабый — оппонент справедливо скажет: "это не лучшая causal system, а просто identification-estimation engine."

### 15.5A — Policy Realism Hard Suites (НОВОЕ)

**Что:** Дополнительные publication-grade контуры, которые проверяют не только causal math, но и policy-shaped workflows.

**Файлы:**
- `benchmarks/natural_experiments/policy_natural_experiments.py`:
  - quasi-experimental / natural-experiments suite
  - Metrics: rank-based comparison, robustness across placebo/null/staggered regimes
- `benchmarks/interference/policy_did_interference.py`:
  - DID + spillover/interference benchmark
  - Metrics: correct policy estimand routing, spillover-aware estimation, naive-DID failure detection
- `benchmarks/adversarial/adversarial_symbolic_stress.py`:
  - generator-style adversarial symbolic stress cases
  - Metrics: zero false positives, proof-trace stability, blocker detection

**Бар:**
- `policy_natural_experiments`: mean rank ≤ 2, no regime collapse, fixed baseline snapshot
- `policy_did_interference`: clean rollout green, spillover contamination exposed, graph interference detection green
- `adversarial_symbolic_stress`: zero false positives, no blocker regressions

### 15.6 — Контур 5: Missing Data / M-graphs (свой suite)

**Файлы:**
- `benchmarks/missing/mgraph_benchmark.py`:
  - Канонические recoverability/non-recoverability cases из Mohan-Pearl
  - Metrics: recoverability detection accuracy, recovered estimand correctness
  - НЕ imputation accuracy — а правильность graph-based recovery decision

**Бар:** 100% correctness на recoverability detection.

### 15.7 — Контур 6: Transportability / Data Fusion / Counterfactual Transport (свой suite)

**Файлы:**
- `benchmarks/transport/transport_benchmark.py`:
  - Selection diagrams из классических transportability cases
  - Multi-source fusion cases
  - Counterfactual transportability (Correa-Lee-Bareinboim 2022) cases
  - ctf-calculus frontier cases
  - Metrics: transport formula correctness, non-transportability detection, bounds quality

**Бар:** 100% correctness на formula + detection. Это ownable territory.

### 15.8 — Capability Wins Proof Suite

**Что:** Набор capability-suite-ов, которые доказывают не просто “экзотический query”, а end-to-end gap против других стеков: `expressible → identifiable → estimable_or_bounded → audit_trace → reproducible`.

**Файлы:**
- `benchmarks/capability_wins/`:
  - `demo_multi_source_transport.py` — multi-source transportability end-to-end
  - `demo_fusion_plus_missingness.py` — data fusion + M-graph recovery
  - `demo_symbolic_non_id_certificate.py` — constructive NegativeCertificate с suggested experiments
  - `demo_ctf_transportability.py` — Layer-3 transport
  - `demo_compiled_pipeline_audit.py` — estimand→executor→audit trace
  - `demo_cyclic_policy_feedback.py` — cyclic SCM identification + estimation
  - `capability_surrogate_experiments.py` — arbitrary surrogate experiments
  - `capability_nested_surrogate_ctf.py` — nested counterfactual surrogate identification
  - `capability_multiple_incomplete_sources.py` — multiple incomplete data sources
  - `capability_did_with_interference.py` — DID under spillovers / SUTVA violations
  - `capability_nontransportability_bounds.py` — constructive non-transportability + bounds

**Новый бар:**
- каждая capability suite проходит end-to-end;
- каждая пишет machine-readable `competitor_gap` matrix;
- есть `literature_anchor` и complete `EvidenceBundle`/audit payload;
- хотя бы один primary competitor (`y0`, `DoWhy`, `EconML`, `CausalPy`) fail-ит хотя бы на одном workflow level;
- ни один competitor не проходит весь workflow полностью;
- suite без `competitor_gap` не считается claim-ready, даже если локальные кейсы green.

### 15.9 — Reproducibility & Governance

**Файлы:**
- `benchmarks/reproducibility/`:
  - `test_deterministic_symbolic.py`: symbolic outputs bit-identical between runs
  - `test_regression_no_flaky.py`: 3x repeat → 0 flaky tests
  - `test_audit_trail_complete.py`: every benchmark result has EvidenceBundle
  - `run_all_benchmarks.sh`: единый script для полного benchmark suite

**Бар:** 100% reproducibility; regression suite без flaky; audit trail для каждого результата.

---

## Порядок фаз и зависимости (v2.3)

```
Phase 0  ──→ Phase 0A ──→ Phase 1 ──→ Phase 1A ──→ Phase 2 ──→ Phase 4
  │                            │              │           │
  │                            └──→ Phase 3   │           │
  │                                           │           │
  └──→ Phase 5 (Tarjan+σ-sep+SolverNode)      │           │
  └──→ Phase 6 ──→ Phase 9 ──────────────────┘           │
  └──→ Phase 7 ──→ Phase 1A (LP bounds used in fallback) │
  └──→ Phase 8                                            │
  └──→ Phase 10                                           │
  └──→ Phase 11                                           │
  └──→ Phase 12                                           │
  └──→ Phase 13                                           │
  └──→ Phase 14 ──→ Phase 15 (benchmarks after all code)  │
                                                          │
Phase 15 depends on ALL previous phases                   │
```

**Критический путь:** Phase 0 → 0A → 1 → 1A → 2 → 4 → 14 → 15

**Параллелизуемые:** Phases 3, 5-13 параллельно после Phase 0.

---

## Оценка объёма (v2.3)

| Фаза | Новых файлов | Модифицированных | Новых тестов | Примерные LOC |
|------|-------------|-----------------|-------------|---------------|
| 0 | 1 | 1 | 1 (5 tests) | ~400 |
| 0A | 0 | 1 | 1 (8 tests) | ~400 |
| 1 | 0 | 3 | 3 (15 tests) | ~1200 |
| 1A | 0 | 2 | 1 (5 tests) | ~600 |
| 2 | 1 | 1 | 2 (14 tests) | ~800 |
| 3 | 1 | 1 | 1 (4 tests) | ~300 |
| 4 | 1 | 2 | 1 (5 tests) | ~600 |
| 5 | 1 | 2 | 2 (14 tests) | ~1400 |
| 6 | 0 | 2 | 3 (11 tests) | ~600 |
| 7 | 2 | 1 | 2 (7 tests) | ~900 |
| 8 | 1 | 2 | 3 (8 tests) | ~1000 |
| 9 | 1 | 0 | 1 (4 tests) | ~600 |
| 10 | 0 | 1 | 1 (2 tests) | ~300 |
| 11 | 0 | 1 | 1 (2 tests) | ~200 |
| 12 | 0 | 2 | 2 (5 tests) | ~400 |
| 13 | 0 | 1 | 1 (2 tests) | ~200 |
| 14 | 0 | 0 | 2 (54 tests) | ~1200 |
| 15 | 12 | 0 | 6 (20+ tests) | ~2500 |
| **Итого** | **21** | **24** | **34 (186+ tests)** | **~13,700** |

---

## Критерии доминирования (итоговый scorecard)

| Dimension | Бар | Почему |
|-----------|-----|--------|
| **Symbolic correctness** | 100% на gold-suite | Ложноположительное identification = fatal. y0 здесь силён, нужно не хуже |
| **Estimation accuracy** | Top-2 средний ранг на ACIC/LBIDD/RealCause | Не обязательно №1 каждый раз, но Pareto-frontier обязательно |
| **Discovery** | Top quartile на CauseMe/Sachs | Не главный moat, но слабый discovery ≠ "лучшая causal system" |
| **Capability wins** | 6+ задач, которые другие tools не покрывают вообще | ctf-transport, cyclic ID, fusion+missingness, compiled pipeline |
| **Negative cases** | 100% detection of non-identifiable/non-transportable | Ложный пропуск HEDGE — хуже чем 2% просадка на PEHE |
| **Reproducibility** | 0 flaky tests; deterministic symbolic; audit trail | Causal OS ≠ just a model; обязана выигрывать по надёжности |

---

## Результат (v2.3)

После завершения всех 15 фаз PolicyOS будет иметь:

1. **Все 9 символических правил:** do-calculus (3) + σ-calculus (3) + ctf-calculus (3)
2. **Все identification алгоритмы:** ID + IDC + ID* + IDC* + z-ID + mz-ID + Cyclic ID (experimental)
3. **Auto-fallback при HEDGE** с 4-tier epistemic model: exact bounds → partial identification → assumption-dependent rescue → diagnostic guidance
4. **Performance (profiling-driven):** `model_construct()` bypass Pydantic-валидации (~40-50% speedup) + CachedAdjacency (~30-40% speedup) + memoized c-components (~5-10% speedup) = суммарно ~60-70% speedup. Bitmasking / matrix reachability / Rust отложены — профилирование подтвердило что set-операции <2% total time, BFS быстрее матричного замыкания на sparse графах
5. **Cyclic SCMs (experimental):** Tarjan SCC → condensation → σ-separation → SolverNode — heuristic engineering approximation, маркируется `identification_confidence="experimental"` до формальной верификации vs ioID
6. **AMN** как derived graph wrapper (не core IR type) — первая known-to-us production реализация (подтвердить в benchmark)
7. **ctf-calculus + ctf-transportability** — первая known-to-us реализация (подтвердить literature survey)
8. **6-контурный benchmark harness** для объективного измерения доминирования (claims делаются ПОСЛЕ benchmark results)
9. **~200 тестовых файлов, ~28,000+ строк тестов**

**Гипотеза:** после прохождения 6-контурного benchmark harness (Phase 15) PolicyOS подтвердит статус наиболее полной реализации Pearl-Bareinboim causal hierarchy. y0 публично реализует ID, IDC, ID*, IDC*, transport и counterfactual transport; cyclic ioID указан как future direction. Plan нацелен в реальные gaps экосистемы, но конкретные claims (скорость, полнота, «первая в мире») становятся утверждениями только после измерений, а не до них.
