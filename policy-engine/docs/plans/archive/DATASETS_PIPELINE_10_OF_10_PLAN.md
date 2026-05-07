> **Archived:** This document reflects plans as of 2026-03-21.
> See [current docs](../../explanation/index.md) for up-to-date information.

# Datasets Pipeline → 10/10: Detailed Implementation Plan

> **Current state**: 7/10 — solid ETL with 44 sources and transport-ready ingest, but heuristic alignment, no incremental loading, limited geographic/temporal flexibility
> **Target state**: 10/10 — production-grade evidence data infrastructure with formal transportability guarantees
> **Estimated total effort**: 20–24 days

---

## Table of Contents

1. [Phase 1 — Incremental Loading & Resilience (Days 1–3)](#phase-1-incremental-loading-resilience-days-1-3)
2. [Phase 2 — Variable Alignment Overhaul (Days 4–7)](#phase-2-variable-alignment-overhaul-days-4-7)
3. [Phase 3 — Temporal & Geographic Alignment (Days 8–11)](#phase-3-temporal-geographic-alignment-days-8-11)
4. [Phase 4 — P\*(Z) Confidence & Distribution (Days 12–14)](#phase-4-p-z-confidence-distribution-days-12-14)
5. [Phase 5 — Missing Data & Imputation (Days 15–16)](#phase-5-missing-data-imputation-days-15-16)
6. [Phase 6 — Search & Discovery Upgrade (Days 17–18)](#phase-6-search-discovery-upgrade-days-17-18)
7. [Phase 7 — QC Hardening & Schema Drift (Days 19–20)](#phase-7-qc-hardening-schema-drift-days-19-20)
8. [Phase 8 — Connector Extensibility & Observability (Days 21–22)](#phase-8-connector-extensibility-observability-days-21-22)
9. [Phase 9 — Cross-Pipeline Integration (Days 23–24)](#phase-9-cross-pipeline-integration-days-23-24)
10. [Verification Criteria](#verification-criteria)

---

## Current Architecture Summary

```
SourceRegistry (44 sources, YAML)
    ↓
[harvest] → /raw/{source}/*.jsonl
    ↓
[normalize] → /normalized/{source}.jsonl (DCAT-aligned DatasetRecord)
    ↓
[merge_dedup] → /merged/all_records.jsonl
    ↓
[graph_load] → DuckDB (9 tables)
[graph_index] → HNSW (1024-dim, multilingual-e5-large)
    ↓
[core_sources_ingest] → ds_observations, ds_variable_alignments, ds_registry_datasets
    ↓
[embed] → ds_dataset_embeddings.npz + ds_dataset_index.hnsw
    ↓
[benchmark] → search/retrieval/transport/foundry scores
[qc] → 9 automated checks
[publish] → consumer_readiness.json + artifacts
```

**Runtime query layer**: `DatasetCatalogGraph` (hybrid search), `DatasetRegistry` (P*(Z) computation), `ProxyResolver` (proxy chains)

---

## Phase 1 — Incremental Loading & Resilience (Days 1–3)

The pipeline currently re-harvests all 44 sources from scratch on every run. A single HTTP failure aborts the entire source. This is the primary operational pain point.

### 1.1 Implement per-source checkpoint tracking

**File**: `batch/harvester.py`

The `resume: bool = False` flag exists in `DatasetBatchConfig` (line 58) but is never checked in `harvest_sources()`.

Add checkpoint manifest:

```python
@dataclass(frozen=True)
class HarvestCheckpoint:
    source_name: str
    status: Literal["complete", "partial", "failed"]
    records_fetched: int
    last_page_token: str | None  # For paginated APIs
    last_offset: int  # For offset-based APIs
    etag: str | None  # For HTTP conditional requests
    last_modified: str | None  # HTTP Last-Modified header
    harvested_at: str  # ISO 8601
    error_message: str | None = None

CHECKPOINT_FILE = "harvest_checkpoint.json"
```

**In `harvest_sources()`**:
```python
async def harvest_sources(config: DatasetBatchConfig) -> dict[str, list[dict]]:
    checkpoint = _load_checkpoint(config.raw_dir / CHECKPOINT_FILE) if config.resume else {}

    for source in sources:
        existing = checkpoint.get(source.name)
        if existing and existing.status == "complete":
            # Skip — already harvested
            stats.skipped += 1
            continue
        if existing and existing.status == "partial":
            # Resume from last_page_token / last_offset
            start_from = existing.last_offset
        else:
            start_from = 0

        try:
            records = await _harvest_single(source, start_from=start_from)
            _save_checkpoint(source.name, "complete", len(records), ...)
        except Exception as e:
            _save_checkpoint(source.name, "failed", partial_count, error=str(e))
            stats.failed_sources.append(source.name)
            continue  # Don't abort other sources
```

### 1.2 HTTP conditional requests (ETag / If-Modified-Since)

For sources with stable endpoints (World Bank, OECD, Eurostat), avoid re-downloading unchanged data.

**File**: `batch/harvester.py`, in `_harvest_single()` per-connector HTTP logic

```python
async def _fetch_with_conditional(
    session: aiohttp.ClientSession,
    url: str,
    cached_etag: str | None,
    cached_last_modified: str | None,
) -> tuple[dict | None, str | None, str | None]:
    headers = {}
    if cached_etag:
        headers["If-None-Match"] = cached_etag
    if cached_last_modified:
        headers["If-Modified-Since"] = cached_last_modified

    async with session.get(url, headers=headers) as resp:
        if resp.status == 304:
            return None, cached_etag, cached_last_modified  # Not modified
        etag = resp.headers.get("ETag")
        last_modified = resp.headers.get("Last-Modified")
        data = await resp.json()
        return data, etag, last_modified
```

**Track per-source**: Store etag/last_modified in checkpoint manifest.

**Expected impact**: 60–80% reduction in harvest time for repeat runs on stable sources (World Bank, Eurostat, OECD rarely change within a week).

### 1.3 Source-level error isolation with retry budget

**Problem**: A single HTTP 429 or timeout currently logs a warning but may corrupt partial output. No retry budget.

**File**: `batch/harvester.py`

```python
@dataclass(frozen=True)
class SourceRetryPolicy:
    max_retries: int = 3
    backoff_base_seconds: float = 2.0
    backoff_max_seconds: float = 60.0
    timeout_seconds: float = 60.0
    retry_on_status: frozenset[int] = frozenset({429, 500, 502, 503, 504})

async def _harvest_with_retry(
    source: SourceSpec,
    policy: SourceRetryPolicy,
    session: aiohttp.ClientSession,
) -> tuple[list[dict], HarvestCheckpoint]:
    for attempt in range(policy.max_retries + 1):
        try:
            records = await _harvest_single(source, session, timeout=policy.timeout_seconds)
            return records, HarvestCheckpoint(status="complete", ...)
        except aiohttp.ClientResponseError as e:
            if e.status not in policy.retry_on_status:
                raise
            wait = min(
                policy.backoff_base_seconds * (2 ** attempt),
                policy.backoff_max_seconds,
            )
            await asyncio.sleep(wait)
        except asyncio.TimeoutError:
            wait = min(policy.backoff_base_seconds * (2 ** attempt), policy.backoff_max_seconds)
            await asyncio.sleep(wait)

    return partial_records, HarvestCheckpoint(status="partial", ...)
```

### 1.4 Normalize stage: idempotent re-processing

**File**: `batch/normalizer.py`

Add fingerprint-based skip:
```python
def _should_renormalize(raw_path: Path, normalized_path: Path) -> bool:
    """Skip normalization if raw data hasn't changed since last normalize."""
    if not normalized_path.exists():
        return True
    raw_mtime = raw_path.stat().st_mtime
    norm_mtime = normalized_path.stat().st_mtime
    return raw_mtime > norm_mtime
```

Apply in `normalize_raw_sources()`:
```python
for source_name, raw_path in raw_sources.items():
    norm_path = norm_dir / f"{source_name}.jsonl"
    if config.resume and not _should_renormalize(raw_path, norm_path):
        stats.skipped += 1
        continue
    # ... existing normalization logic
```

---

## Phase 2 — Variable Alignment Overhaul (Days 4–7)

Variable alignment is the **most critical component** for transportability. Current Jaccard similarity (threshold 0.35) is crude — "gdp_per_capita" vs. "gross_domestic_product_per_head" gets low Jaccard score despite being identical concepts.

### 2.1 Embedding-based semantic alignment

**File**: `knowledge/variable_alignment.py`

Replace `align_semantic()` Jaccard approach with embedding-based:

```python
class EmbeddingVariableAligner:
    """Embedding-based variable alignment using the same multilingual model as dataset search."""

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-large",
        canonical_variables: dict[str, str] | None = None,  # {canonical_name: display_name}
    ):
        self._model = SentenceTransformer(model_name)
        self._canonical_embeddings: dict[str, np.ndarray] = {}
        if canonical_variables:
            self._build_canonical_index(canonical_variables)

    def _build_canonical_index(self, variables: dict[str, str]):
        """Pre-embed all canonical variable names for fast lookup."""
        names = list(variables.keys())
        displays = [variables[n] for n in names]
        # Embed both canonical name and display name, take mean
        texts = [f"{n.replace('.', ' ').replace('_', ' ')} {d}" for n, d in zip(names, displays)]
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        for name, emb in zip(names, embeddings):
            self._canonical_embeddings[name] = emb

    def align(
        self,
        raw_variable: str,
        candidates: list[str] | None = None,
        threshold: float = 0.65,
        top_k: int = 5,
    ) -> list[VariableAlignment]:
        """
        Align a raw variable name to canonical variables.
        Uses embedding similarity with optional candidate restriction.
        """
        raw_text = raw_variable.replace("_", " ").replace(".", " ").lower()
        raw_emb = self._model.encode([raw_text], normalize_embeddings=True)[0]

        search_space = candidates or list(self._canonical_embeddings.keys())
        results = []
        for canonical in search_space:
            if canonical not in self._canonical_embeddings:
                continue
            sim = float(np.dot(raw_emb, self._canonical_embeddings[canonical]))
            if sim >= threshold:
                results.append(VariableAlignment(
                    dataset_id="",  # Filled by caller
                    raw_variable=raw_variable,
                    canonical_variable=canonical,
                    confidence=sim,
                    method=AlignmentMethod.SEMANTIC,
                    evidence=f"embedding_similarity={sim:.3f}",
                ))

        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:top_k]
```

### 2.2 Three-tier alignment cascade

Replace the current flat alignment with a cascade:

```python
def align_variable_cascade(
    raw_variable: str,
    dataset_id: str,
    seed_alignments: dict[str, str],  # From seed_variable_alignments.yaml
    embedding_aligner: EmbeddingVariableAligner,
    meta_analytic_evidence: list[dict] | None = None,
) -> VariableAlignment | None:
    """
    Three-tier alignment cascade:
    1. Exact seed match (confidence = 1.0)
    2. Embedding semantic match (confidence = similarity score)
    3. Meta-analytic evidence match (confidence = evidence-weighted)

    Returns best alignment or None if below all thresholds.
    """
    # Tier 1: Exact seed
    if raw_variable in seed_alignments:
        return VariableAlignment(
            dataset_id=dataset_id,
            raw_variable=raw_variable,
            canonical_variable=seed_alignments[raw_variable],
            confidence=1.0,
            method=AlignmentMethod.EXACT,
            evidence="seed_alignment",
        )

    # Tier 2: Embedding semantic
    semantic_matches = embedding_aligner.align(raw_variable, threshold=0.65)
    if semantic_matches:
        best = semantic_matches[0]
        best.dataset_id = dataset_id
        return best

    # Tier 3: Meta-analytic
    if meta_analytic_evidence:
        ma_matches = align_meta_analytic(
            raw_variable, dataset_id, meta_analytic_evidence, min_confidence=0.3
        )
        if ma_matches:
            return ma_matches[0]

    return None
```

### 2.3 Alignment confidence calibration

**Problem**: Current Jaccard scores and meta-analytic weights are on different scales. A Jaccard of 0.6 and a meta-analytic of 0.6 mean very different things.

Add calibration layer:
```python
ALIGNMENT_CALIBRATION = {
    AlignmentMethod.EXACT: lambda conf: 1.0,  # Always 1.0
    AlignmentMethod.SEMANTIC: lambda conf: 0.5 + 0.5 * conf,  # [0.5, 1.0] range
    AlignmentMethod.META_ANALYTIC: lambda conf: conf,  # Already calibrated by evidence weights
}

def calibrate_alignment_confidence(alignment: VariableAlignment) -> float:
    """Normalize confidence to comparable scale across methods."""
    calibrator = ALIGNMENT_CALIBRATION.get(alignment.method, lambda x: x)
    return calibrator(alignment.confidence)
```

### 2.4 Alignment audit log

**New table**: `ds_alignment_audit`
```sql
CREATE TABLE IF NOT EXISTS ds_alignment_audit (
    audit_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    raw_variable TEXT NOT NULL,
    canonical_variable TEXT,
    method TEXT NOT NULL,         -- exact|semantic|meta_analytic|unresolved
    raw_confidence FLOAT,
    calibrated_confidence FLOAT,
    alternatives_json TEXT,       -- Top-3 alternative matches
    resolved_at TEXT,             -- ISO 8601
    reviewed BOOLEAN DEFAULT FALSE,
    reviewer_override TEXT DEFAULT NULL
);
```

**Populate during** `_build_catalog_alignments()` in `core_sources_ingest.py`.

**Value**: When a P*(Z) estimate is wrong, this table lets you trace back *why* — which alignment produced the wrong variable mapping.

### 2.5 Expand seed alignments

**File**: `data/dataset_catalog/seed_variable_alignments.yaml`

Current seed covers core indicators. Expand to cover the 12 foundry metrics + common aliases:

```yaml
# GDP variants
NY.GDP.PCAP.CD: gdp_per_capita
NY.GDP.PCAP.PP.CD: gdp_per_capita_ppp
gdp_per_head: gdp_per_capita
gross_domestic_product_per_capita: gdp_per_capita
ввп_на_душу_населення: gdp_per_capita  # Ukrainian
pib_par_habitant: gdp_per_capita  # French
bip_pro_kopf: gdp_per_capita  # German
pkb_na_osobe: gdp_per_capita  # Polish

# Unemployment variants
SL.UEM.TOTL.ZS: unemployment_rate
unemployment_pct: unemployment_rate
безробіття: unemployment_rate
stopa_bezrobocia: unemployment_rate
arbeitslosenquote: unemployment_rate
taux_de_chomage: unemployment_rate

# ... extend for all 12 foundry metrics × common source codes × 5 languages
```

**Target**: 200+ seed entries covering World Bank indicator codes, SDMX dimension values, CKAN field names, and multilingual aliases for core variables.

---

## Phase 3 — Temporal & Geographic Alignment (Days 8–11)

### 3.1 Replace heuristic temporal penalty with evidence-based decay

**Problem**: Current penalty is `0.05 * distance_years, max 0.3` — arbitrary. A 2019 GDP estimate for a 2020 query loses 5% confidence, which is reasonable. But a 2019 "institutional_quality" estimate for 2020 should lose almost nothing (institutions change slowly), while a 2019 "inflation_rate" for 2020 could be wildly wrong.

**File**: `knowledge/registry.py`, `compute_p_star_z()`

Add variable-specific temporal volatility:

```python
# Volatility classes: how fast does this variable change year-to-year?
TEMPORAL_VOLATILITY = {
    # Low volatility (institutions, demographics, geography)
    "institutional_quality": 0.02,
    "rule_of_law": 0.02,
    "population": 0.01,
    "literacy_rate": 0.01,
    "life_expectancy": 0.02,
    "education_years": 0.01,

    # Medium volatility (economic structure)
    "gdp_per_capita": 0.05,
    "unemployment_rate": 0.08,
    "trade_openness": 0.04,
    "gini_coefficient": 0.03,
    "poverty_rate": 0.04,

    # High volatility (prices, flows, sentiment)
    "inflation_rate": 0.15,
    "exchange_rate": 0.20,
    "migration_flow": 0.10,
    "fdi_inflow": 0.12,
    "consumer_confidence": 0.15,
    "interest_rate": 0.12,
}

DEFAULT_VOLATILITY = 0.05  # If unknown

def _temporal_penalty(
    canonical_var: str,
    data_year: int,
    target_year: int,
) -> float:
    """
    Evidence-based temporal penalty.
    penalty = min(volatility × |distance|, max_penalty)
    """
    volatility = TEMPORAL_VOLATILITY.get(canonical_var, DEFAULT_VOLATILITY)
    distance = abs(target_year - data_year)
    max_penalty = 0.5  # Never penalize more than 50%
    return min(volatility * distance, max_penalty)
```

### 3.2 Time-series interpolation for panel data

**Problem**: `ds_observations` stores individual (country, year, value) points. If we have 2018 and 2020 data but need 2019, there's no interpolation.

**File**: `knowledge/registry.py`

```python
def _interpolate_observation(
    observations: list[tuple[int, float]],  # [(year, value), ...]
    target_year: int,
    method: Literal["linear", "nearest", "none"] = "linear",
) -> tuple[float | None, float]:
    """
    Interpolate between observations.
    Returns (interpolated_value, interpolation_confidence).
    """
    if method == "none":
        return None, 0.0

    obs = sorted(observations, key=lambda x: x[0])
    years = [o[0] for o in obs]
    values = [o[1] for o in obs]

    # Exact match
    if target_year in years:
        idx = years.index(target_year)
        return values[idx], 1.0

    if method == "nearest":
        closest = min(obs, key=lambda o: abs(o[0] - target_year))
        distance = abs(closest[0] - target_year)
        confidence = max(0.3, 1.0 - 0.1 * distance)
        return closest[1], confidence

    if method == "linear":
        # Find bracketing years
        before = [(y, v) for y, v in obs if y < target_year]
        after = [(y, v) for y, v in obs if y > target_year]

        if not before or not after:
            # Extrapolation — lower confidence
            closest = min(obs, key=lambda o: abs(o[0] - target_year))
            distance = abs(closest[0] - target_year)
            confidence = max(0.2, 0.8 - 0.15 * distance)
            return closest[1], confidence  # Use nearest, no extrapolation

        y0, v0 = before[-1]
        y1, v1 = after[0]
        gap = y1 - y0
        t = (target_year - y0) / gap
        interpolated = v0 + t * (v1 - v0)

        # Confidence decreases with gap size
        confidence = max(0.5, 1.0 - 0.05 * gap)
        return interpolated, confidence

    return None, 0.0
```

### 3.3 Expand geographic coverage beyond 3 countries

**Problem**: `core_countries = ["UA", "DE", "PL"]` is hardcoded in multiple places. Transport targets should be configurable.

**File**: `batch/config.py`

```python
@dataclass
class DatasetBatchConfig:
    # ... existing fields ...

    # Geographic coverage (replace hardcoded core_countries)
    core_countries: list[str] = field(default_factory=lambda: ["UA", "DE", "PL"])
    extended_countries: list[str] = field(default_factory=lambda: [
        # EU + CIS + key comparators
        "UA", "DE", "PL", "RO", "MD", "CZ", "SK", "HU",  # Central/Eastern Europe
        "FR", "GB", "IT", "ES", "NL", "SE", "DK", "FI",  # Western/Northern Europe
        "US", "CA", "JP", "KR", "AU",                      # OECD comparators
        "GE", "AM", "AZ", "KZ", "UZ",                      # CIS
    ])
    geographic_scope: Literal["core", "extended", "global"] = "extended"

    @property
    def active_countries(self) -> list[str]:
        if self.geographic_scope == "core":
            return self.core_countries
        elif self.geographic_scope == "extended":
            return self.extended_countries
        else:
            return []  # Global = no filter
```

**File**: `batch/core_sources_ingest.py` — replace all `["UA", "DE", "PL"]` references with `config.active_countries`.

### 3.4 Country code normalization registry

**Problem**: Different sources use different country code systems (ISO2, ISO3, numeric, custom). Current conversion is ad-hoc.

**New file**: `knowledge/country_codes.py`

```python
@dataclass(frozen=True)
class CountryMapping:
    iso2: str
    iso3: str
    numeric: str
    name_en: str
    name_local: str | None = None
    aliases: tuple[str, ...] = ()

# Load from a standard registry (ISO 3166)
COUNTRY_REGISTRY: dict[str, CountryMapping] = _load_country_registry()

def normalize_country_code(raw: str) -> str | None:
    """
    Normalize any country identifier to ISO2.
    Handles: ISO2, ISO3, numeric codes, English names, local names.
    """
    raw_upper = raw.strip().upper()

    # Direct ISO2
    if raw_upper in COUNTRY_REGISTRY:
        return raw_upper

    # ISO3 lookup
    for iso2, mapping in COUNTRY_REGISTRY.items():
        if mapping.iso3 == raw_upper:
            return iso2
        if mapping.numeric == raw_upper:
            return iso2
        if mapping.name_en.upper() == raw_upper:
            return iso2
        if raw_upper in (a.upper() for a in mapping.aliases):
            return iso2

    return None  # Unknown — log warning

def country_region(iso2: str) -> str | None:
    """Return UN region for grouping (Europe, Asia, Americas, etc.)."""
    ...
```

### 3.5 Subnational data discovery (foundation)

**Problem**: Many policy questions are subnational (e.g., "minimum wage effect in Donbas region" vs. all of Ukraine). No subnational support currently.

**Schema change**: Add `spatial_level` to `ds_datasets`:
```sql
ALTER TABLE ds_datasets ADD COLUMN spatial_level TEXT DEFAULT 'national';
-- Values: national, subnational_region, subnational_city, global
```

**In normalizer.py**: Detect subnational scope from:
- CKAN extras: `geographic_coverage`, `spatial`, `region`
- Title patterns: "by region", "by oblast", "по регіонах", "nach Bundesland"
- Dataset variables: NUTS codes, FIPS codes, region names

**Phase 1 scope**: Detection only — mark datasets as subnational in catalog. Actual subnational P*(Z) computation is future work.

---

## Phase 4 — P*(Z) Confidence & Distribution (Days 12–14)

### 4.1 Full uncertainty quantification for P*(Z)

**Problem**: `compute_p_star_z()` returns a single `float | None` value with a single `float` confidence. No uncertainty interval. The causal engine needs distributions, not point estimates, for proper sensitivity analysis.

**File**: `knowledge/registry.py`

Extend `PStarZResult`:

```python
@dataclass(frozen=True)
class PStarZResult:
    canonical_variable: str
    value: float | None
    dataset_id: str
    raw_variable: str
    is_proxy: bool
    proxy_chain: list[str]
    confidence: float
    penalty_breakdown: dict[str, float]
    is_conditional: bool
    condition_on: list[str]

    # NEW: Uncertainty quantification
    std_error: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    distribution_type: Literal["point", "normal", "empirical", "bounded"] = "point"
    distribution_params: dict[str, float] = field(default_factory=dict)
    # e.g., {"mean": 0.5, "std": 0.1} for normal
    # or {"min": 0.3, "max": 0.7} for bounded

    uncertainty_sources: list[str] = field(default_factory=list)
    # ["proxy_penalty", "temporal_distance", "alignment_confidence", "interpolation"]
```

### 4.2 Compute P*(Z) uncertainty from multiple sources

```python
def compute_p_star_z_with_uncertainty(
    canonical_var: str,
    country_code: str,
    year: int,
    condition_on: dict[str, float] | None = None,
) -> PStarZResult:
    matches = self.find_datasets_for_variable(canonical_var, country_code, (year - 3, year + 1))

    if not matches:
        return PStarZResult(value=None, confidence=0.0, ...)

    # Collect all point estimates with their confidence weights
    estimates: list[tuple[float, float]] = []  # (value, weight)
    uncertainty_sources: list[str] = []

    for match in matches:
        obs = self._fetch_observation(match, year)
        if obs is None:
            # Try interpolation
            obs_series = self._fetch_observation_series(match, year - 3, year + 1)
            obs_value, interp_conf = _interpolate_observation(obs_series, year)
            if obs_value is not None:
                uncertainty_sources.append("interpolation")
                obs = obs_value
                weight = match.mapping_confidence * interp_conf
            else:
                continue
        else:
            weight = match.mapping_confidence

        # Apply penalties
        temporal_pen = _temporal_penalty(canonical_var, match.actual_survey_year or year, year)
        proxy_pen = match.proxy_penalty if match.is_proxy else 0.0
        weight *= (1.0 - temporal_pen) * (1.0 - proxy_pen)

        if temporal_pen > 0:
            uncertainty_sources.append("temporal_distance")
        if proxy_pen > 0:
            uncertainty_sources.append("proxy_penalty")

        estimates.append((obs, weight))

    if not estimates:
        return PStarZResult(value=None, confidence=0.0, ...)

    # Weighted mean and standard error
    values = np.array([e[0] for e in estimates])
    weights = np.array([e[1] for e in estimates])
    weights_norm = weights / weights.sum()

    weighted_mean = np.average(values, weights=weights_norm)

    if len(estimates) > 1:
        # Weighted standard error
        weighted_var = np.average((values - weighted_mean) ** 2, weights=weights_norm)
        std_error = np.sqrt(weighted_var / len(estimates))
        ci_low = weighted_mean - 1.96 * std_error
        ci_high = weighted_mean + 1.96 * std_error
        distribution_type = "normal"
    else:
        # Single source — use alignment confidence as uncertainty proxy
        std_error = abs(weighted_mean) * (1.0 - weights[0]) * 0.5
        ci_low = weighted_mean - 1.96 * std_error
        ci_high = weighted_mean + 1.96 * std_error
        distribution_type = "bounded"
        uncertainty_sources.append("single_source")

    return PStarZResult(
        value=float(weighted_mean),
        std_error=float(std_error),
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        confidence=float(weights.max()),
        distribution_type=distribution_type,
        distribution_params={"mean": float(weighted_mean), "std": float(std_error)},
        uncertainty_sources=list(set(uncertainty_sources)),
        ...
    )
```

### 4.3 P*(Z) cross-validation against academic estimates

**Problem**: P*(Z) accuracy has no ground truth validation. Add cross-validation against `ac_parameter_estimates` from the academic pipeline.

**File**: `batch/benchmark.py`

```python
def _benchmark_p_star_accuracy(
    registry: DatasetRegistry,
    academic_store,  # ac_parameter_estimates access
) -> PStarAccuracyResult:
    """
    For parameters that exist in both datasets and academic estimates,
    compare P*(Z) computation against published values.
    """
    academic_params = academic_store.fetch_parameters_with_ci()
    results = []

    for param in academic_params:
        if param.country and param.period_start:
            p_star = registry.compute_p_star_z_with_uncertainty(
                param.variable_name, param.country, param.period_start
            )
            if p_star.value is not None:
                error = abs(p_star.value - param.estimate)
                covered = (p_star.ci_low <= param.estimate <= p_star.ci_high) if p_star.ci_low else None
                results.append({
                    "variable": param.variable_name,
                    "country": param.country,
                    "year": param.period_start,
                    "p_star_value": p_star.value,
                    "academic_value": param.estimate,
                    "absolute_error": error,
                    "ci_covers_academic": covered,
                })

    coverage = sum(1 for r in results if r["ci_covers_academic"]) / max(1, len(results))
    mean_error = sum(r["absolute_error"] for r in results) / max(1, len(results))

    return PStarAccuracyResult(
        n_compared=len(results),
        ci_coverage_rate=coverage,
        mean_absolute_error=mean_error,
        details=results,
    )
```

**Add to benchmark suite**: `p_star_accuracy` with thresholds:
- CI coverage ≥ 80%
- Mean absolute error ≤ 20% of variable mean

---

## Phase 5 — Missing Data & Imputation (Days 15–16)

### 5.1 Missing data inventory

**New QC check**: Track exactly what's missing per country × variable × year.

**File**: `batch/qc.py`

```python
def _check_observation_coverage(con: duckdb.DuckDBPyConnection, config) -> QCCheck:
    """
    For each core_country × foundry_metric × core_year: is there an observation?
    """
    core_countries = config.active_countries[:10]  # Top 10
    core_years = list(range(2018, 2024))
    foundry_metrics = config.foundry_metrics  # 12 metrics

    total_cells = len(core_countries) * len(foundry_metrics) * len(core_years)

    filled = con.execute("""
        SELECT COUNT(DISTINCT (country_code, canonical_var, year))
        FROM ds_observations
        WHERE country_code IN (SELECT UNNEST(?::TEXT[]))
          AND canonical_var IN (SELECT UNNEST(?::TEXT[]))
          AND year BETWEEN ? AND ?
    """, [core_countries, foundry_metrics, 2018, 2023]).fetchone()[0]

    coverage = filled / total_cells * 100 if total_cells > 0 else 0

    return QCCheck(
        name="observation_coverage_pct",
        passed=coverage >= 60.0,
        value=round(coverage, 1),
        threshold=60.0,
        severity="warning",
    )
```

### 5.2 Generate coverage heatmap

**File**: `batch/qc.py`

```python
def _generate_coverage_heatmap(
    con: duckdb.DuckDBPyConnection,
    countries: list[str],
    variables: list[str],
    year_range: tuple[int, int],
) -> dict:
    """
    Generate country × variable coverage matrix.
    For each cell: latest_year available, total observations, quality score.
    """
    matrix = {}
    for country in countries:
        matrix[country] = {}
        for var in variables:
            obs = con.execute("""
                SELECT year, value FROM ds_observations
                WHERE country_code = ? AND canonical_var = ?
                  AND year BETWEEN ? AND ?
                ORDER BY year DESC
            """, [country, var, year_range[0], year_range[1]]).fetchall()

            matrix[country][var] = {
                "available_years": [o[0] for o in obs],
                "latest_year": obs[0][0] if obs else None,
                "count": len(obs),
                "status": "full" if len(obs) >= (year_range[1] - year_range[0]) else
                          "partial" if obs else "missing",
            }
    return matrix
```

Write to `coverage_heatmap.json` in publish artifacts.

### 5.3 Imputation strategy registry

Not all variables should be imputed the same way. Add configurable strategy per variable class:

```python
IMPUTATION_STRATEGIES = {
    # Stable variables: carry-forward is safe
    "institutional_quality": ImputationStrategy.CARRY_FORWARD,
    "rule_of_law": ImputationStrategy.CARRY_FORWARD,
    "population": ImputationStrategy.LINEAR_INTERPOLATION,
    "literacy_rate": ImputationStrategy.CARRY_FORWARD,

    # Smooth economic variables: interpolation OK
    "gdp_per_capita": ImputationStrategy.LINEAR_INTERPOLATION,
    "life_expectancy": ImputationStrategy.LINEAR_INTERPOLATION,
    "education_years": ImputationStrategy.CARRY_FORWARD,

    # Volatile variables: DO NOT impute
    "inflation_rate": ImputationStrategy.NONE,
    "exchange_rate": ImputationStrategy.NONE,
    "migration_flow": ImputationStrategy.NONE,
    "fdi_inflow": ImputationStrategy.NONE,
}

class ImputationStrategy(Enum):
    NONE = "none"                         # Return None, don't guess
    CARRY_FORWARD = "carry_forward"       # Use most recent observation
    LINEAR_INTERPOLATION = "linear"       # Interpolate between neighbors
    REGIONAL_MEAN = "regional_mean"       # Use UN region average as fallback
```

### 5.4 Sensitivity flag for imputed values

**Critical**: The causal engine must know when a P*(Z) value is imputed vs. observed.

Add to `PStarZResult`:
```python
imputation_method: str | None = None  # "carry_forward", "linear", "regional_mean", None
imputation_confidence_adjustment: float = 0.0  # Penalty applied due to imputation
```

The causal engine's `sensitivity_analysis` can then vary imputed values within their uncertainty bounds to test robustness.

---

## Phase 6 — Search & Discovery Upgrade (Days 17–18)

### 6.1 Faceted search

**File**: `knowledge/search.py`, `DatasetCatalogGraph`

```python
@dataclass(frozen=True)
class SearchFilters:
    sources: list[str] | None = None          # ["worldbank", "eurostat"]
    formats: list[str] | None = None          # ["csv", "json", "api"]
    countries: list[str] | None = None        # ["UA", "DE"]
    year_min: int | None = None
    year_max: int | None = None
    metrics: list[str] | None = None          # ["gdp_per_capita"]
    execution_tier: str | None = None         # "transport_ready"
    min_quality_score: float | None = None    # 0.0–1.0
    spatial_level: str | None = None          # "national", "subnational_region"

def search_datasets(
    self,
    query: str,
    filters: SearchFilters | None = None,
    top_k: int = 10,
    vector_weight: float = 0.5,
    explain: bool = False,
) -> list[DatasetSearchResult]:
    """
    Hybrid search with faceted filtering.
    If explain=True, each result includes score breakdown.
    """
    # ... vector + text scoring ...

    # Apply filters as SQL WHERE clauses
    where_clauses = []
    params = []
    if filters:
        if filters.sources:
            where_clauses.append("source IN (SELECT UNNEST(?::TEXT[]))")
            params.append(filters.sources)
        if filters.countries:
            where_clauses.append("spatial IN (SELECT UNNEST(?::TEXT[]))")
            params.append(filters.countries)
        if filters.year_min:
            where_clauses.append("temporal_end >= ?")
            params.append(str(filters.year_min))
        if filters.min_quality_score:
            where_clauses.append("execution_readiness_score >= ?")
            params.append(filters.min_quality_score)
        # ... etc

    # ... apply filters, score, rank, return
```

### 6.2 Search explain mode

When `explain=True`, return scoring breakdown per result:

```python
@dataclass(frozen=True)
class SearchExplanation:
    text_score: float        # BM25-like text match
    vector_score: float      # Cosine similarity
    metric_boost: float      # Metric keyword match
    source_boost: float      # Source hint match
    freshness_boost: float   # More recent = higher
    final_score: float       # Combined
    matched_terms: list[str] # Which query terms matched
    expansion_terms: list[str]  # Which expanded terms matched
```

### 6.3 Related datasets suggestion

```python
def suggest_related(
    self,
    dataset_id: str,
    top_k: int = 5,
) -> list[DatasetSearchResult]:
    """
    Find datasets related to a given dataset.
    Uses: same metrics, overlapping variables, vector similarity.
    """
    dataset = self.get_dataset(dataset_id)
    if not dataset:
        return []

    # Vector similarity to existing embedding
    vector = self._get_embedding(dataset_id)
    similar = self.search_by_vector(vector, top_k=top_k + 1)

    # Filter out self
    return [s for s in similar if s.id != dataset_id][:top_k]
```

### 6.4 Bulk metric resolution

**File**: `knowledge/registry.py`

```python
def find_datasets_for_variables_bulk(
    self,
    variables: list[str],
    country_code: str,
    year_range: tuple[int, int] | None = None,
) -> dict[str, list[DatasetMatch]]:
    """
    Resolve multiple variables at once.
    More efficient than N individual calls (single SQL query).
    """
    results = {}
    # Single query with IN clause
    rows = self._con.execute("""
        SELECT canonical_var, dataset_id, raw_variable, ...
        FROM ds_variable_alignments va
        JOIN ds_observations o USING (dataset_id, raw_variable)
        WHERE canonical_var IN (SELECT UNNEST(?::TEXT[]))
          AND o.country_code = ?
          AND (? IS NULL OR o.year BETWEEN ? AND ?)
        ORDER BY canonical_var, mapping_confidence DESC
    """, [variables, country_code, ...]).fetchall()

    for row in rows:
        var = row[0]
        if var not in results:
            results[var] = []
        results[var].append(DatasetMatch(...))

    return results
```

---

## Phase 7 — QC Hardening & Schema Drift (Days 19–20)

### 7.1 Schema drift detection

**Problem**: External APIs change their schema without notice (World Bank adds/removes indicators, CKAN portals rename fields). No detection.

**File**: `batch/qc.py`

```python
def _check_schema_drift(
    con: duckdb.DuckDBPyConnection,
    previous_snapshot_path: Path | None,
) -> QCCheck:
    """
    Compare current dataset variables against previous snapshot.
    Flag significant changes.
    """
    if not previous_snapshot_path:
        return QCCheck(name="schema_drift", passed=True, value=0, severity="info")

    prev_con = duckdb.connect(str(previous_snapshot_path), read_only=True)

    # Variables that disappeared
    disappeared = con.execute("""
        SELECT DISTINCT canonical_var FROM ds_variable_alignments
        EXCEPT
        SELECT DISTINCT canonical_var FROM prev.ds_variable_alignments
    """).fetchall()

    # New variables
    new_vars = con.execute("""
        SELECT DISTINCT canonical_var FROM prev.ds_variable_alignments
        EXCEPT
        SELECT DISTINCT canonical_var FROM ds_variable_alignments
    """).fetchall()

    # Sources with significant row count change (>50% delta)
    count_drift = con.execute("""
        SELECT c.source, c.cnt as current, p.cnt as previous,
               ABS(c.cnt - p.cnt) * 100.0 / NULLIF(p.cnt, 0) as pct_change
        FROM (SELECT source, COUNT(*) cnt FROM ds_datasets GROUP BY source) c
        JOIN (SELECT source, COUNT(*) cnt FROM prev.ds_datasets GROUP BY source) p
            USING (source)
        WHERE ABS(c.cnt - p.cnt) * 100.0 / NULLIF(p.cnt, 0) > 50
    """).fetchall()

    drift_count = len(disappeared) + len(new_vars) + len(count_drift)
    return QCCheck(
        name="schema_drift_signals",
        passed=drift_count <= 5,
        value=drift_count,
        threshold=5,
        severity="warning",
        details={
            "disappeared_variables": [r[0] for r in disappeared],
            "new_variables": [r[0] for r in new_vars],
            "source_count_drift": [
                {"source": r[0], "current": r[1], "previous": r[2], "pct_change": r[3]}
                for r in count_drift
            ],
        },
    )
```

### 7.2 Data freshness tracking

**New table**: `ds_freshness_log`
```sql
CREATE TABLE IF NOT EXISTS ds_freshness_log (
    source TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    check_date TEXT NOT NULL,
    last_data_year INTEGER,
    last_updated TEXT,             -- From source metadata
    staleness_days INTEGER,        -- Days since last_updated
    status TEXT DEFAULT 'current', -- current|stale|dead
    PRIMARY KEY (source, dataset_id, check_date)
);
```

**QC check**:
```python
def _check_data_freshness(con) -> QCCheck:
    """Flag transport_ready sources with no data after 2021."""
    stale = con.execute("""
        SELECT COUNT(DISTINCT source || '|' || dataset_id)
        FROM ds_registry_datasets
        WHERE last_updated IS NOT NULL
          AND last_updated < '2022-01-01'
    """).fetchone()[0]
    return QCCheck(
        name="stale_transport_sources",
        passed=stale <= 3,
        value=stale,
        threshold=3,
        severity="warning",
    )
```

### 7.3 Distribution URL health monitoring

**Problem**: Current URL reachability check is sample-based (random 20 URLs). For transport_ready sources, ALL URLs must be reachable.

```python
def _check_transport_url_health(con, session) -> QCCheck:
    """Verify ALL transport_ready distribution URLs are reachable."""
    urls = con.execute("""
        SELECT d.url, d.dataset_id, ds.source
        FROM ds_distributions d
        JOIN ds_datasets ds ON d.dataset_id = ds.id
        WHERE ds.execution_tier = 'transport_ready'
          AND d.url IS NOT NULL
    """).fetchall()

    dead = []
    for url, dataset_id, source in urls:
        try:
            resp = session.head(url, timeout=10, allow_redirects=True)
            if resp.status_code >= 400:
                dead.append({"url": url, "dataset_id": dataset_id, "source": source, "status": resp.status_code})
        except Exception as e:
            dead.append({"url": url, "dataset_id": dataset_id, "source": source, "error": str(e)})

    return QCCheck(
        name="transport_url_health",
        passed=len(dead) == 0,
        value=len(dead),
        threshold=0,
        severity="critical",
        details={"dead_urls": dead},
    )
```

### 7.4 Cross-source consistency check

```python
def _check_cross_source_consistency(con) -> QCCheck:
    """
    For variables available from multiple sources, check value agreement.
    E.g., World Bank GDP vs. Eurostat GDP for same country+year.
    """
    disagreements = con.execute("""
        WITH multi_source AS (
            SELECT canonical_var, country_code, year,
                   MIN(value) as min_val, MAX(value) as max_val,
                   AVG(value) as mean_val, COUNT(DISTINCT dataset_id) as n_sources
            FROM ds_observations
            GROUP BY canonical_var, country_code, year
            HAVING COUNT(DISTINCT dataset_id) > 1
        )
        SELECT canonical_var, country_code, year,
               min_val, max_val, n_sources,
               (max_val - min_val) / NULLIF(ABS(mean_val), 0) as relative_spread
        FROM multi_source
        WHERE (max_val - min_val) / NULLIF(ABS(mean_val), 0) > 0.15  -- >15% spread
        ORDER BY relative_spread DESC
        LIMIT 20
    """).fetchall()

    return QCCheck(
        name="cross_source_value_spread",
        passed=len(disagreements) <= 5,
        value=len(disagreements),
        threshold=5,
        severity="warning",
        details={"top_disagreements": [
            {"var": r[0], "country": r[1], "year": r[2],
             "min": r[3], "max": r[4], "sources": r[5], "spread_pct": round(r[6] * 100, 1)}
            for r in disagreements
        ]},
    )
```

---

## Phase 8 — Connector Extensibility & Observability (Days 21–22)

### 8.1 Connector plugin interface

**Problem**: Adding a new transport source requires editing `core_sources_ingest.py` directly. Should be plug-and-play.

**New file**: `knowledge/connector_protocol.py`

```python
from typing import Protocol, AsyncIterator

class DataSourceConnector(Protocol):
    """Protocol for pluggable data source connectors."""

    @property
    def source_id(self) -> str:
        """Unique source identifier."""
        ...

    @property
    def supported_variables(self) -> list[str]:
        """List of canonical variables this source can provide."""
        ...

    async def fetch_observations(
        self,
        variable: str,
        country_codes: list[str],
        year_range: tuple[int, int],
    ) -> AsyncIterator[Observation]:
        """Yield observations for a variable across countries and years."""
        ...

    async def health_check(self) -> bool:
        """Return True if the source is reachable and responding."""
        ...

    def get_metadata(self) -> dict[str, Any]:
        """Return source metadata (update frequency, coverage, etc.)."""
        ...

@dataclass(frozen=True)
class Observation:
    country_code: str  # ISO2
    year: int
    value: float
    raw_variable: str
    unit: str | None = None
    source_metadata: dict[str, str] = field(default_factory=dict)
```

### 8.2 Connector auto-discovery

```python
# In core_sources_ingest.py
CONNECTOR_REGISTRY: dict[str, type[DataSourceConnector]] = {}

def register_connector(source_id: str):
    """Decorator to register a connector class."""
    def decorator(cls):
        CONNECTOR_REGISTRY[source_id] = cls
        return cls
    return decorator

@register_connector("worldbank")
class WorldBankTransportConnector:
    source_id = "worldbank"
    supported_variables = ["gdp_per_capita", "unemployment_rate", ...]

    async def fetch_observations(self, variable, country_codes, year_range):
        indicator = VARIABLE_TO_WB_INDICATOR[variable]
        # ... fetch from World Bank API
        yield Observation(...)
```

**In `core_sources_ingest.py`**: Replace hardcoded connector list with:
```python
transport_sources = [
    CONNECTOR_REGISTRY[source_id]()
    for source_id in config.transport_sources
    if source_id in CONNECTOR_REGISTRY
]
```

### 8.3 Pipeline telemetry

**New file**: `batch/telemetry.py`

```python
@dataclass
class PipelineTelemetry:
    """Per-run telemetry for datasets pipeline."""

    # Harvest
    harvest_start: datetime
    harvest_end: datetime
    sources_attempted: int
    sources_completed: int
    sources_failed: int
    sources_skipped_cache: int  # Due to conditional requests
    total_records_fetched: int
    total_bytes_downloaded: int

    # Normalize
    normalize_duration_seconds: float
    records_normalized: int
    records_rejected: int
    metric_mapping_rate: float  # % with ≥1 polisyos_metric

    # Core ingest
    ingest_duration_seconds: float
    alignments_created: int
    alignment_methods: dict[str, int]  # {"exact": N, "semantic": N, "meta_analytic": N}
    observations_inserted: int
    observations_per_source: dict[str, int]

    # Search index
    embedding_duration_seconds: float
    index_build_seconds: float
    index_size_bytes: int

    # Quality
    qc_checks_passed: int
    qc_checks_failed: int
    benchmark_scores: dict[str, float]

    # Overall
    total_duration_seconds: float
    pipeline_status: Literal["success", "partial", "failed"]
```

Write to `telemetry.json` per run. Keep history for trend analysis.

### 8.4 Query-level metrics

**File**: `knowledge/search.py`

```python
@dataclass
class QueryMetrics:
    query: str
    vector_search_ms: float
    text_search_ms: float
    total_candidates: int
    after_filter: int
    returned: int
    top_score: float
    mean_score: float

# Collect in search_datasets():
def search_datasets(self, query, ...) -> list[DatasetSearchResult]:
    t0 = time.perf_counter()
    vector_results = self._vector_search(query, top_k * 3)
    t_vector = time.perf_counter() - t0

    t1 = time.perf_counter()
    text_results = self._text_search(query, top_k * 3)
    t_text = time.perf_counter() - t1

    # ... merge, filter, rank ...

    self._last_query_metrics = QueryMetrics(
        query=query,
        vector_search_ms=(t_vector) * 1000,
        text_search_ms=(t_text) * 1000,
        total_candidates=len(vector_results) + len(text_results),
        after_filter=len(filtered),
        returned=len(results),
        top_score=results[0].similarity if results else 0.0,
        mean_score=sum(r.similarity for r in results) / max(1, len(results)),
    )
    return results
```

---

## Phase 9 — Cross-Pipeline Integration (Days 23–24)

### 9.1 Academic → Datasets variable alignment sync

**Problem**: Academic pipeline has `CANONICAL_VARIABLES` in `canonical_seed.py`. Datasets pipeline has `seed_variable_alignments.yaml`. These must be synchronized.

**Solution**: Single source of truth.

**New file**: `data/canonical_variables/registry.yaml`

```yaml
# Shared canonical variable registry
# Used by: academic pipeline (SKG variables), datasets pipeline (alignment targets)
variables:
  gdp_per_capita:
    display_name: "GDP per capita"
    domain: economics
    unit: "USD (current)"
    volatility: 0.05
    aliases:
      - gdp_per_head
      - gross_domestic_product_per_capita
      - NY.GDP.PCAP.CD
    translations:
      uk: ввп_на_душу_населення
      pl: pkb_na_osobe
      de: bip_pro_kopf
      fr: pib_par_habitant

  unemployment_rate:
    display_name: "Unemployment rate"
    domain: labor
    unit: "% of labor force"
    volatility: 0.08
    aliases:
      - unemployment_pct
      - SL.UEM.TOTL.ZS
    translations:
      uk: безробіття
      pl: stopa_bezrobocia
      de: arbeitslosenquote

  # ... all foundry metrics + extended set
```

**Load in both pipelines**:
```python
# In academic/knowledge/canonical_seed.py
CANONICAL_VARIABLES = load_canonical_registry("data/canonical_variables/registry.yaml")

# In datasets/knowledge/variable_alignment.py
CANONICAL_TARGETS = load_canonical_registry("data/canonical_variables/registry.yaml")
```

### 9.2 Datasets → Causal engine: structured P*(Z) handoff

**Problem**: `scientist/nodes/builtins/causal/resolve_transport.py` calls `registry.compute_p_star_z()` but only uses `value` and `confidence`. The new uncertainty quantification (Phase 4) needs to flow through.

**File**: `scientist/nodes/builtins/causal/resolve_transport.py`

Update transport resolution to use full `PStarZResult`:

```python
def resolve_transport_data(
    target_vars: list[str],
    target_country: str,
    target_year: int,
    registry: DatasetRegistry,
) -> TransportDataBundle:
    results = {}
    warnings = []

    for var in target_vars:
        p_star = registry.compute_p_star_z_with_uncertainty(var, target_country, target_year)

        if p_star.value is None:
            warnings.append(f"No data for {var} in {target_country}/{target_year}")
            continue

        results[var] = TransportVariable(
            canonical_name=var,
            value=p_star.value,
            std_error=p_star.std_error,
            ci_low=p_star.ci_low,
            ci_high=p_star.ci_high,
            confidence=p_star.confidence,
            is_proxy=p_star.is_proxy,
            imputed=p_star.imputation_method is not None,
            uncertainty_sources=p_star.uncertainty_sources,
        )

        # Flag high-uncertainty variables for sensitivity analysis
        if p_star.confidence < 0.5 or p_star.imputation_method:
            warnings.append(
                f"{var}: low confidence ({p_star.confidence:.2f}), "
                f"sources: {p_star.uncertainty_sources}"
            )

    return TransportDataBundle(
        variables=results,
        warnings=warnings,
        can_proceed=len(results) / max(1, len(target_vars)) >= 0.5,
    )
```

### 9.3 SKG edges → Dataset priority (adaptive harvesting)

**Problem**: The pipeline harvests the same 44 sources regardless of what the causal engine needs. If the SKG has a high-confidence edge "minimum_wage → employment" but no dataset covers minimum wage data for the target country, nobody knows.

**New stage** (optional, after SKG is built): `adaptive_priority.py`

```python
def compute_dataset_gaps(
    skg_edges: list[SKGEdge],
    registry: DatasetRegistry,
    target_countries: list[str],
) -> list[DatasetGap]:
    """
    For each SKG edge, check if both src and dst variables have
    transport-ready data in target countries. Flag gaps.
    """
    gaps = []
    for edge in skg_edges:
        for country in target_countries:
            for var in [edge.src, edge.dst]:
                matches = registry.find_datasets_for_variable(var, country)
                if not matches:
                    gaps.append(DatasetGap(
                        variable=var,
                        country=country,
                        edge_confidence=edge.confidence,
                        priority=edge.confidence * _variable_importance(var),
                    ))

    # Sort by priority (high-confidence edges with missing data = highest priority)
    gaps.sort(key=lambda g: g.priority, reverse=True)
    return gaps
```

Output as `dataset_gaps.json` — input for next harvest cycle (add new sources or expand coverage).

### 9.4 Datasets QC → Consumer readiness contract

**File**: `batch/publish.py`

Extend `consumer_readiness.json` to include everything downstream consumers need:

```python
@dataclass(frozen=True)
class ConsumerReadiness:
    # Existing
    qc_passed: bool
    benchmark_scores: dict[str, float]

    # New: per-variable readiness
    variable_readiness: dict[str, VariableReadiness]
    # {
    #   "gdp_per_capita": {
    #     "countries_covered": ["UA", "DE", "PL", ...],
    #     "year_range": [2000, 2023],
    #     "sources": ["worldbank", "eurostat"],
    #     "alignment_confidence": 0.95,
    #     "observation_count": 240,
    #     "freshest_year": 2023,
    #     "interpolation_needed_pct": 5.0,
    #     "ready_for_transport": True
    #   }
    # }

    # New: gap analysis
    critical_gaps: list[DatasetGap]  # Variables needed by SKG but missing
    coverage_heatmap_path: str       # Path to coverage_heatmap.json
    telemetry_path: str              # Path to telemetry.json
```

---

## Verification Criteria

### Gate 1 — Incremental Loading (after Phase 1)
- [ ] Re-run on unchanged sources completes in < 30% of full run time
- [ ] Failed source doesn't abort other sources
- [ ] Checkpoint manifest correctly tracks per-source status
- [ ] ETag/If-Modified-Since works for World Bank and Eurostat

### Gate 2 — Variable Alignment (after Phase 2)
- [ ] Embedding-based alignment resolves "fiscal_revenue" → "tax.revenue" (unit test)
- [ ] Cascade: exact seed > embedding > meta-analytic (unit test)
- [ ] Calibrated confidence: all methods on comparable [0, 1] scale (unit test)
- [ ] Alignment audit log populated with alternatives (integration test)
- [ ] 200+ seed entries covering 12 metrics × 5 languages

### Gate 3 — Temporal & Geographic (after Phase 3)
- [ ] Variable-specific temporal penalty: inflation penalized 3× vs. institutional quality (unit test)
- [ ] Linear interpolation between years with confidence (unit test)
- [ ] Geographic scope configurable: core (3) / extended (25+) / global
- [ ] Country code normalization handles ISO2, ISO3, numeric, English names (unit test)
- [ ] Subnational spatial_level column populated for CKAN sources

### Gate 4 — P*(Z) Uncertainty (after Phase 4)
- [ ] P*(Z) returns std_error, ci_low, ci_high (schema test)
- [ ] Multi-source P*(Z) uses weighted mean (unit test)
- [ ] CI coverage ≥ 80% against academic parameter estimates (benchmark)
- [ ] Uncertainty sources tracked and propagated

### Gate 5 — Missing Data (after Phase 5)
- [ ] Coverage heatmap generated for core countries × metrics × years
- [ ] Imputation strategy per variable class (carry-forward vs. interpolation vs. none)
- [ ] Imputed values flagged with `imputation_method` field
- [ ] Volatile variables (inflation, exchange_rate) never imputed

### Gate 6 — Search & Discovery (after Phase 6)
- [ ] Faceted search: filter by source, country, year, format (integration test)
- [ ] Explain mode returns score breakdown (unit test)
- [ ] Bulk variable resolution in single SQL query (performance test)
- [ ] Related datasets suggestion works (integration test)

### Gate 7 — QC Hardening (after Phase 7)
- [ ] Schema drift detection vs. previous snapshot (unit test)
- [ ] Data freshness tracking: stale sources flagged (integration test)
- [ ] Transport URL health: 100% reachability for transport_ready (integration test)
- [ ] Cross-source consistency: disagreements > 15% flagged (unit test)

### Gate 8 — Extensibility & Observability (after Phase 8)
- [ ] New connector added via `@register_connector` decorator without touching core code
- [ ] Pipeline telemetry written to `telemetry.json` per run
- [ ] Query metrics tracked for search operations
- [ ] All metrics have non-zero values in production run

### Gate 9 — Cross-Pipeline (after Phase 9)
- [ ] Single canonical variable registry shared between academic and datasets
- [ ] Transport resolution uses full PStarZResult with uncertainty
- [ ] Dataset gap analysis produced from SKG edges
- [ ] Consumer readiness manifest includes per-variable readiness

### Final Gate — 10/10 Criteria
- [ ] All 9 phase gates pass
- [ ] All existing 18 test files continue to pass
- [ ] 20+ new tests added and passing
- [ ] Full pipeline run completes without manual intervention
- [ ] Incremental re-run < 30% of full run time
- [ ] Variable alignment resolution rate ≥ 90%
- [ ] Observation coverage ≥ 60% for core countries × metrics × 2018–2023
- [ ] P*(Z) CI coverage ≥ 80% against academic baselines
- [ ] Zero dead URLs in transport_ready sources
- [ ] Schema drift detection operational across 2+ snapshots
- [ ] Consumer readiness manifest passes all readiness thresholds
