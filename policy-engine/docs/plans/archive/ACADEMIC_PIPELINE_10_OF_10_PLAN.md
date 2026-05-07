> **Archived:** This document reflects plans as of 2026-03-20.
> See [current docs](../../explanation/index.md) for up-to-date information.

# Academic Pipeline → 10/10: Detailed Implementation Plan

> **Current state**: 7/10 — architecturally mature, statistically naive
> **Target state**: 10/10 — production-grade evidence synthesis with formal guarantees
> **Estimated total effort**: 18–22 days

---

## Table of Contents

1. [Phase 1 — Safety & Correctness (Days 1–3)](#phase-1-safety-correctness-days-1-3)
2. [Phase 2 — Confidence Aggregation Overhaul (Days 4–7)](#phase-2-confidence-aggregation-overhaul-days-4-7)
3. [Phase 3 — Variable Canonicalization (Days 8–11)](#phase-3-variable-canonicalization-days-8-11)
4. [Phase 4 — Conflict Resolution & Evidence Weighting (Days 12–14)](#phase-4-conflict-resolution-evidence-weighting-days-12-14)
5. [Phase 5 — Claim Adjudication Upgrade (Days 15–16)](#phase-5-claim-adjudication-upgrade-days-15-16)
6. [Phase 6 — QC & Benchmark Hardening (Days 17–18)](#phase-6-qc-benchmark-hardening-days-17-18)
7. [Phase 7 — Test Coverage & Observability (Days 19–20)](#phase-7-test-coverage-observability-days-19-20)
8. [Phase 8 — Track B/C Integration & Polish (Days 21–22)](#phase-8-track-b-c-integration-polish-days-21-22)
9. [Verification Criteria](#verification-criteria)

---

## Phase 1 — Safety & Correctness (Days 1–3)

These are bugs / silent correctness failures that must be fixed before anything else.

### 1.1 Filter retracted papers from confidence aggregation

**Problem**: `ac_skg_articles.retracted` column exists (skg_store.py:24) but is never checked during edge confidence computation. A retracted paper contributes to edge confidence identically to a valid one.

**Where to change**:

**File**: `skg_store.py`, function `aggregate_edge_confidence()` (lines 244–257)

Current signature:
```python
def aggregate_edge_confidence(articles: Iterable[tuple[str, float]]) -> float:
```

Change to accept retraction status:
```python
def aggregate_edge_confidence(
    articles: Iterable[tuple[str, float, bool]],  # (strength, extraction_conf, is_retracted)
) -> float:
    rows = [(s, c) for s, c, retracted in articles if not retracted]
    if not rows:
        return 0.0
    # ... existing logic on filtered rows
```

**File**: `edge_synthesize.py`, wherever `aggregate_edge_confidence()` is called (lines ~216, ~255) — pass retraction status from `ac_skg_articles.retracted`.

**File**: `skg_query.py` — all edge queries should JOIN with `ac_skg_articles` and filter `WHERE retracted = FALSE` or at minimum carry `retracted` flag in results.

**Test**: Add test case with a retracted RCT — verify it does not inflate edge confidence.

### 1.2 Filter retracted papers from claim adjudication

**File**: `graph_builder.py`, `_load_merged_claims()` — add filter:
```sql
WHERE w.is_retracted = FALSE OR w.is_retracted IS NULL
```

**File**: `claim_adjudicator.py` — if adjudicating claims from retracted papers, set `publishable_edge = False` with blocker `"retracted_paper"`.

### 1.3 Fix abstract-only evidence strength downgrade

**Problem**: Abstract-only claims pass eligibility as `context_eligible` and can flow to graph with `source_basis = "abstract_only"`. The `_apply_publish_gate()` blocks them from `publish_to_graph`, but they still appear in `ac_causal_claims_raw` without explicit quality penalty.

**Where to change**:

**File**: `skg_store.py`, `EVIDENCE_WEIGHTS` — add modifier:
```python
ABSTRACT_ONLY_PENALTY = 0.5  # Halve the evidence weight for abstract-only extractions
```

Apply in `aggregate_edge_confidence()`:
```python
effective_weight = EVIDENCE_WEIGHTS.get(strength, 0.15)
if source_basis == "abstract_only":
    effective_weight *= ABSTRACT_ONLY_PENALTY
```

### 1.4 Validate JSON columns at insert time

**Problem**: `confidence_interval_json`, `article_refs`, `scope_conditions`, `quality_signals_json` stored as JSON strings with no schema validation at insert. Silent failures at query time return empty results.

**Where to change**:

**File**: `graph_builder.py` — add validation in `_insert_skg_edges()` and `_insert_skg_parameters()`:
```python
def _validate_json_column(value: str, expected_type: type = list) -> str:
    parsed = json.loads(value)
    if not isinstance(parsed, expected_type):
        raise ValueError(f"Expected {expected_type.__name__}, got {type(parsed).__name__}")
    return value
```

Apply to all JSON column inserts. Log and skip malformed rows rather than silently inserting broken data.

---

## Phase 2 — Confidence Aggregation Overhaul (Days 4–7)

The current aggregation is `max(quality_weight × extraction_conf) + log2_replication_bonus`. This treats one high-quality RCT identically whether it has n=50 or n=50,000, and weights a 1995 study equally with a 2024 study.

### 2.1 Add temporal decay

**File**: `skg_store.py`, `aggregate_edge_confidence()` (lines 244–257)

Add decay factor:
```python
TEMPORAL_HALF_LIFE_YEARS = 20  # Evidence value halves every 20 years
TEMPORAL_FLOOR = 0.3           # Never decay below 30% of original weight

def _temporal_weight(pub_year: int, current_year: int = 2026) -> float:
    age = max(0, current_year - pub_year)
    decay = 0.5 ** (age / TEMPORAL_HALF_LIFE_YEARS)
    return max(TEMPORAL_FLOOR, decay)
```

Rationale: 20-year half-life is conservative — a 2006 paper retains 50% weight, a 1986 paper retains 30% (floor). This penalizes outdated institutional/policy findings while keeping classic methodology papers (Card & Krueger 1994) still relevant.

Apply:
```python
effective_weight = base_weight * _temporal_weight(pub_year) * extraction_conf
```

**Schema change**: `aggregate_edge_confidence()` must receive `pub_year` per article. Extend the tuple:
```python
articles: Iterable[tuple[str, float, int, bool]]  # (strength, conf, year, retracted)
```

**Upstream**: `edge_synthesize.py` must JOIN `ac_skg_articles.year` when building evidence samples.

### 2.2 Add sample size weighting

**Problem**: Sample size is not stored in `ac_skg_edge_evidence`. It IS stored in `ac_parameter_estimates.sample_size` but not linked to edge confidence.

**Step 1**: Add `sample_size` column to `ac_skg_edge_evidence`:
```sql
ALTER TABLE ac_skg_edge_evidence ADD COLUMN sample_size INTEGER DEFAULT NULL;
```

Populate from `ac_parameter_estimates` via work_id JOIN during `edge_synthesize.py`.

**Step 2**: Add sample size factor to confidence:
```python
def _sample_size_factor(n: int | None) -> float:
    if n is None or n <= 0:
        return 0.7  # Penalty for unreported sample size
    if n < 100:
        return 0.6
    if n < 500:
        return 0.8
    if n < 5000:
        return 0.9
    return 1.0  # Large-N studies get full weight
```

**Step 3**: Incorporate into aggregation:
```python
effective_weight = (
    base_evidence_weight
    * _temporal_weight(pub_year)
    * _sample_size_factor(sample_size)
    * extraction_conf
)
```

### 2.3 Replace max-based aggregation with Bayesian-inspired combination

**Problem**: Current logic takes `max()` of quality scores + log2 bonus. This means 1 RCT + 100 observational studies = same confidence as 1 RCT alone (plus tiny log2 bonus).

**Replace with**:
```python
def aggregate_edge_confidence(articles: list[ArticleEvidence]) -> float:
    if not articles:
        return 0.0

    # Filter retracted
    valid = [a for a in articles if not a.retracted]
    if not valid:
        return 0.0

    # Compute per-article effective weight
    weights = []
    for a in valid:
        w = (
            EVIDENCE_WEIGHTS.get(a.strength, 0.15)
            * _temporal_weight(a.pub_year)
            * _sample_size_factor(a.sample_size)
            * a.extraction_conf
        )
        if a.source_basis == "abstract_only":
            w *= ABSTRACT_ONLY_PENALTY
        weights.append(w)

    # Noisy-OR combination: P(at least one valid) = 1 - Π(1 - w_i)
    # This naturally handles replication: more studies → higher confidence
    combined = 1.0 - math.prod(1.0 - min(w, 0.99) for w in weights)
    return min(1.0, combined)
```

**Rationale for noisy-OR**: treats each study as an independent "signal" of the causal effect. One strong RCT (w=0.9) gives confidence 0.9. Adding 5 observational studies (w=0.25 each) pushes to 0.9 + marginal gain ≈ 0.97. This naturally captures:
- Replication value (more studies → higher confidence)
- Quality hierarchy (RCT dominates but observational accumulates)
- Diminishing returns (10th weak study adds less than 2nd)

**Remove**: `replication_bonus` logic (lines 256–257) — it's subsumed by noisy-OR.

### 2.4 Add citation impact weighting (optional, configurable)

`ac_skg_articles.fwci` (field-weighted citation impact) and `cited_by_count` are available but unused. As a configurable boost:

```python
CITATION_IMPACT_ENABLED = True
CITATION_IMPACT_CAP = 1.3  # Max 30% boost

def _citation_factor(fwci: float | None) -> float:
    if not CITATION_IMPACT_ENABLED or fwci is None:
        return 1.0
    return min(CITATION_IMPACT_CAP, max(0.5, fwci))
```

This is controversial (citation bias exists) so make it configurable and off by default.

---

## Phase 3 — Variable Canonicalization (Days 8–11)

This is the **single highest-impact improvement**. Currently `_approved_family()` does exact hierarchy walk only — `fiscal_revenue` will never match `tax.revenue`.

### 3.1 Build embedding index for canonical variables

**New file**: `academic/knowledge/canonical_resolver.py`

```python
class CanonicalVariableResolver:
    def __init__(self, approved_names: set[str], embedding_model: str = "text-embedding-3-large"):
        self._approved = approved_names
        self._embeddings: dict[str, np.ndarray] = {}
        self._index: hnswlib.Index | None = None

    def build_index(self):
        """Embed all approved canonical names and build HNSW index."""
        texts = [self._display_text(name) for name in self._approved]
        embeddings = embed_batch(texts, model=self._embedding_model)
        # Build HNSW index over embeddings
        ...

    def resolve(self, raw_name: str, threshold: float = 0.75) -> str | None:
        """
        Resolve raw variable name to canonical.
        Priority: exact match → hierarchy walk → embedding similarity.
        """
        # 1. Exact match
        if raw_name in self._approved:
            return raw_name

        # 2. Hierarchy walk (existing logic)
        parent = parent_canonical_name(raw_name)
        while parent:
            if parent in self._approved:
                return parent
            parent = parent_canonical_name(parent)

        # 3. Embedding-based fuzzy match
        query_emb = embed_single(self._display_text(raw_name))
        labels, distances = self._index.knn_query(query_emb, k=3)
        best_name = self._approved_list[labels[0][0]]
        best_sim = 1.0 - distances[0][0]

        if best_sim >= threshold:
            return best_name

        return None  # Unresolved — goes to review queue

    def _display_text(self, canonical: str) -> str:
        """Convert dot-notation to readable: 'fiscal.tax_revenue' → 'fiscal tax revenue'"""
        return canonical.replace(".", " ").replace("_", " ")
```

### 3.2 Integrate resolver into edge synthesis

**File**: `edge_synthesize.py`, replace `_approved_family()` (lines 48–58):

```python
# Before
family = _approved_family(src, approved)

# After
resolver = CanonicalVariableResolver(approved)
resolver.build_index()  # Once per run
family = resolver.resolve(src, threshold=0.75)
```

### 3.3 Add synonym table

**New table**: `ac_skg_variable_synonyms`
```sql
CREATE TABLE IF NOT EXISTS ac_skg_variable_synonyms (
    synonym TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'manual',  -- manual|embedding|llm
    confidence FLOAT DEFAULT 1.0,
    approved BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (synonym, canonical_name)
);
```

Populate from:
1. Manual curation (seed file)
2. Embedding matches with confidence ≥ 0.75 but < 0.90 → auto-approve
3. Embedding matches with confidence ≥ 0.90 → auto-approve
4. LLM-suggested synonyms from extraction context

### 3.4 Auto-approve high-confidence matches

In `edge_synthesize.py`, after resolver returns a match:
```python
if match and match.confidence >= 0.90:
    # Auto-approve and insert into synonyms table
    _insert_synonym(con, raw_name, match.canonical, method="embedding", confidence=match.confidence, approved=True)
elif match and match.confidence >= 0.75:
    # Insert as pending approval
    _insert_synonym(con, raw_name, match.canonical, method="embedding", confidence=match.confidence, approved=False)
```

### 3.5 Reduce review queue backlog

Track metrics:
```python
@dataclass
class CanonizationStats:
    exact_matches: int = 0
    hierarchy_matches: int = 0
    embedding_matches: int = 0
    auto_approved: int = 0
    pending_review: int = 0
    unresolved: int = 0
```

Target: ≥ 90% automatic resolution (exact + hierarchy + embedding auto-approve), ≤ 10% manual review.

### 3.6 Cross-pipeline canonical registry

**Long-term** (beyond this plan but prepare the interface): expose `CanonicalVariableResolver` as a shared service that Lex and Datasets pipelines can also use. For now, ensure the `ac_skg_variable_synonyms` table schema is compatible with a future unified registry.

---

## Phase 4 — Conflict Resolution & Evidence Weighting (Days 12–14)

Currently direction agreement is `len(article_refs) / total_direction_articles` — pure count, no quality weighting.

### 4.1 Evidence-weighted direction agreement

**File**: `edge_synthesize.py`, lines ~196–234

Replace:
```python
# Current (line 203)
direction_agreement = len(article_refs) / total_direction_articles
```

With:
```python
def _weighted_direction_agreement(
    direction_evidence: dict[str, list[ArticleEvidence]],
) -> tuple[str, float, bool]:
    """
    Returns (dominant_direction, agreement_score, is_contested).
    Agreement weighted by evidence quality, not article count.
    """
    direction_weights: dict[str, float] = {}
    for direction, articles in direction_evidence.items():
        total_weight = sum(
            EVIDENCE_WEIGHTS.get(a.strength, 0.15)
            * _temporal_weight(a.pub_year)
            * _sample_size_factor(a.sample_size)
            * a.extraction_conf
            for a in articles
            if not a.retracted
        )
        direction_weights[direction] = total_weight

    total = sum(direction_weights.values())
    if total == 0:
        return ("unknown", 0.0, False)

    dominant = max(direction_weights, key=direction_weights.get)
    agreement = direction_weights[dominant] / total

    # Contested if at least 2 directions with >15% weight share each
    significant = [d for d, w in direction_weights.items() if w / total > 0.15]
    is_contested = len(significant) > 1

    return (dominant, agreement, is_contested)
```

**Impact**: A pair with 10 weak observational "positive" (total weight ~3.0) and 1 strong RCT "negative" (weight ~0.9) now gives agreement ~77% for positive BUT the RCT is a significant minority → `is_contested = True`. Previously it was 91% "agreement" with no contest flag.

### 4.2 Principled contested edge confidence penalty

**File**: `edge_synthesize.py`, line ~255

Replace arbitrary `-0.1` with quality-proportional penalty:
```python
# Current
confidence = max(0.25, aggregate_edge_confidence(evidence_samples) - 0.1)

# New
base_confidence = aggregate_edge_confidence(evidence_samples)
minority_weight = 1.0 - agreement_score  # How much evidence opposes
penalty = minority_weight * 0.5  # Scale: 50% opposition → -0.25 penalty
confidence = max(0.15, base_confidence - penalty)
```

### 4.3 Track conflict granularity

Add to `ac_skg_contested_edges`:
```sql
ALTER TABLE ac_skg_contested_edges
    ADD COLUMN positive_weight FLOAT DEFAULT 0.0,
    ADD COLUMN negative_weight FLOAT DEFAULT 0.0,
    ADD COLUMN mixed_weight FLOAT DEFAULT 0.0,
    ADD COLUMN dominant_direction_agreement FLOAT DEFAULT 0.0,
    ADD COLUMN strongest_dissent_strength TEXT DEFAULT '',
    ADD COLUMN strongest_dissent_year INTEGER DEFAULT NULL;
```

This lets downstream consumers see: "dominant direction is positive (agreement=0.72), but there's a 2023 RCT dissenting with quasi_natural evidence."

### 4.4 Hierarchical conflict resolution strategy

**New function** in `conflict_resolve.py`:

```python
def resolve_conflict_hierarchical(
    direction_evidence: dict[str, list[ArticleEvidence]],
) -> ConflictResolution:
    """
    Resolution strategy:
    1. If all RCTs agree → resolved by RCT consensus
    2. If RCTs disagree → contested (mark for meta-analysis)
    3. If no RCTs but quasi-experiments agree → resolved by quasi consensus
    4. If lower-tier only → resolved by weighted majority, flag low confidence
    """
    rct_directions = {d for d, arts in direction_evidence.items()
                      if any(a.strength in ("rct", "meta_analysis") for a in arts)}

    if len(rct_directions) == 1:
        return ConflictResolution(
            status="resolved_by_rct",
            dominant=rct_directions.pop(),
            resolution_method="rct_consensus",
            confidence_modifier=1.0,
        )
    elif len(rct_directions) > 1:
        return ConflictResolution(
            status="contested_rct_disagreement",
            dominant="mixed",
            resolution_method="meta_analysis_needed",
            confidence_modifier=0.5,
        )
    # ... similar for quasi, observational
```

---

## Phase 5 — Claim Adjudication Upgrade (Days 15–16)

### 5.1 Confidence-weighted consensus voting

**File**: `scientist/autotune/claim_adjudication.py`, `aggregate_claim_rows()` (lines 112–166)

Replace simple mode/majority vote:

```python
def aggregate_claim_rows(rows: list[ClaimAdjudicationResult], config) -> ClaimAdjudicationResult:
    # Confidence-weighted categorical voting
    for field in ["claim_type", "design_family", "causal_credibility", "risk_of_bias", "support_status"]:
        weighted_votes: dict[str, float] = defaultdict(float)
        for row in rows:
            value = getattr(row, field)
            weight = row.adjudication_confidence  # Use confidence as vote weight
            weighted_votes[value] += weight
        result[field] = max(weighted_votes, key=weighted_votes.get)

    # Weighted publishable decision
    publish_weight = sum(
        row.adjudication_confidence for row in rows if row.publishable_edge
    )
    total_weight = sum(row.adjudication_confidence for row in rows)
    weighted_publish_ratio = publish_weight / total_weight if total_weight > 0 else 0

    publishable = weighted_publish_ratio >= 0.6  # 60% weighted threshold

    # Stability = confidence-weighted agreement
    consensus_stability = weighted_publish_ratio if publishable else (1.0 - weighted_publish_ratio)

    # ... rest of aggregation
```

### 5.2 Add per-dimension confidence breakdown

**Schema change**: Add columns to `ac_claim_adjudications`:
```sql
ALTER TABLE ac_claim_adjudications
    ADD COLUMN claim_type_confidence FLOAT DEFAULT NULL,
    ADD COLUMN design_family_confidence FLOAT DEFAULT NULL,
    ADD COLUMN direction_confidence FLOAT DEFAULT NULL;
```

Populate from weighted voting: `claim_type_confidence = max_vote_weight / total_weight`.

### 5.3 Cross-claim consistency check

**New function** in `claim_adjudicator.py`:

```python
def check_intra_paper_consistency(claims: list[CausalClaim]) -> list[str]:
    """
    Flag contradictions within the same paper.
    E.g., claim 1: X→Y positive, claim 2: X→Y negative.
    """
    warnings = []
    pairs = defaultdict(list)
    for c in claims:
        key = (c.cause_variable, c.effect_variable)
        pairs[key].append(c.direction)

    for (cause, effect), directions in pairs.items():
        unique = set(directions) - {"ambiguous", "mixed"}
        if "positive" in unique and "negative" in unique:
            warnings.append(
                f"Intra-paper contradiction: {cause}→{effect} "
                f"has both positive and negative claims"
            )
    return warnings
```

Add to `_apply_publish_gate()`: if contradiction found, add blocker `"intra_paper_direction_contradiction"`.

---

## Phase 6 — QC & Benchmark Hardening (Days 17–18)

### 6.1 New QC checks

**File**: `qc.py` — add the following checks:

```python
# 1. Retracted paper contamination
def _check_retracted_in_graph(con) -> QCCheck:
    """Verify no retracted papers contribute to published edges."""
    count = con.execute("""
        SELECT COUNT(DISTINCT e.openalex_id)
        FROM ac_skg_edge_evidence e
        JOIN ac_skg_articles a ON e.openalex_id = a.openalex_id
        WHERE a.retracted = TRUE
    """).fetchone()[0]
    return QCCheck(
        name="retracted_paper_in_graph",
        passed=count == 0,
        value=count,
        threshold=0,
        severity="critical",
    )

# 2. Publication year distribution
def _check_year_distribution(con) -> QCCheck:
    """Flag if >50% of evidence is from before 2010."""
    old_pct = con.execute("""
        SELECT 100.0 * COUNT(*) FILTER (WHERE a.year < 2010) / NULLIF(COUNT(*), 0)
        FROM ac_skg_edge_evidence e
        JOIN ac_skg_articles a ON e.openalex_id = a.openalex_id
    """).fetchone()[0] or 0
    return QCCheck(
        name="old_evidence_share_pct",
        passed=old_pct <= 50.0,
        value=round(old_pct, 1),
        threshold=50.0,
        severity="warning",
    )

# 3. Sample size coverage
def _check_sample_size_coverage(con) -> QCCheck:
    """Flag if <40% of parameter estimates have sample_size reported."""
    coverage = con.execute("""
        SELECT 100.0 * COUNT(*) FILTER (WHERE sample_size IS NOT NULL AND sample_size > 0)
            / NULLIF(COUNT(*), 0)
        FROM ac_parameter_estimates
    """).fetchone()[0] or 0
    return QCCheck(
        name="sample_size_coverage_pct",
        passed=coverage >= 40.0,
        value=round(coverage, 1),
        threshold=40.0,
        severity="warning",
    )

# 4. Canonicalization resolution rate
def _check_canonicalization_rate(con) -> QCCheck:
    """Verify >=85% of variables are canonically resolved."""
    stats = resolver.get_stats()  # From Phase 3
    rate = (stats.exact + stats.hierarchy + stats.embedding_auto) / max(1, stats.total) * 100
    return QCCheck(
        name="canonical_resolution_rate_pct",
        passed=rate >= 85.0,
        value=round(rate, 1),
        threshold=85.0,
        severity="critical",
    )

# 5. Edge confidence distribution
def _check_confidence_distribution(con) -> QCCheck:
    """Flag if >30% of published edges have confidence < 0.3."""
    low_pct = con.execute("""
        SELECT 100.0 * COUNT(*) FILTER (WHERE confidence < 0.3) / NULLIF(COUNT(*), 0)
        FROM ac_skg_edges
    """).fetchone()[0] or 0
    return QCCheck(
        name="low_confidence_edge_share_pct",
        passed=low_pct <= 30.0,
        value=round(low_pct, 1),
        threshold=30.0,
        severity="warning",
    )

# 6. Design tier distribution
def _check_design_tier_health(con) -> QCCheck:
    """Verify at least 20% of published claims are Tier 1-2."""
    high_tier_pct = con.execute("""
        SELECT 100.0 * COUNT(*) FILTER (WHERE design_quality_tier IN (1, 2))
            / NULLIF(COUNT(*), 0)
        FROM ac_claim_adjudications
        WHERE publishable_edge = TRUE
    """).fetchone()[0] or 0
    return QCCheck(
        name="high_design_tier_share_pct",
        passed=high_tier_pct >= 20.0,
        value=round(high_tier_pct, 1),
        threshold=20.0,
        severity="warning",
    )
```

### 6.2 Tighten existing thresholds

| Check | Current | New | Rationale |
|-------|---------|-----|-----------|
| `canonical_claim_variable_pct` | ≥ 80% | ≥ 90% | With fuzzy resolver, 90% is achievable |
| `supporting_span_coverage` | ≥ 85% | ≥ 90% | Spans are critical for audit |
| `tier4_share` | ≤ 40% | ≤ 30% | Reduce noise from weak designs |
| `empty_abstract_pct` | ≤ 25% | ≤ 15% | Missing abstracts reduce context quality |

### 6.3 Configurable benchmark thresholds

**File**: `benchmark.py`, lines 317–324

Replace hard-coded `0.7 confidence, 2 works`:
```python
@dataclass(frozen=True)
class BenchmarkCredibilityConfig:
    min_confidence: float = 0.7
    min_unique_works: int = 2
    require_no_conflict: bool = True
    min_design_tier: int | None = None  # Optional: require Tier 1-2 evidence
    max_evidence_age_years: int | None = None  # Optional: exclude old evidence
```

Pass through `benchmark.yaml` configuration file per scenario.

### 6.4 Add new benchmark scenarios

Add 4 scenarios targeting known weak areas:
```python
# Transport-specific: edges that exist in EU but need validation for UA
{"name": "transport_eu_to_ua", "causal_edges": [...], "parameters": [...]}

# High-conflict: domains where direction disagreement is expected
{"name": "contested_minimum_wage", "causal_edges": [("minimum_wage", "employment")]}

# Time-sensitive: edges where recency matters
{"name": "digital_economy_effects", "causal_edges": [...]}

# Sparse evidence: domains with few high-quality studies
{"name": "governance_anticorruption", "causal_edges": [...]}
```

---

## Phase 7 — Test Coverage & Observability (Days 19–20)

### 7.1 New test cases

| Test | Module | What it verifies |
|------|--------|------------------|
| `test_retracted_paper_excluded` | skg_store | Retracted paper doesn't inflate confidence |
| `test_temporal_decay_applied` | skg_store | 2005 paper gets lower weight than 2023 |
| `test_sample_size_factor` | skg_store | n=50 gets 0.6, n=5000 gets 1.0 |
| `test_noisy_or_combination` | skg_store | 1 RCT + 5 observational > 1 RCT alone |
| `test_embedding_canonical_resolve` | canonical_resolver | "fiscal_revenue" resolves to "tax.revenue" |
| `test_exact_match_priority` | canonical_resolver | Exact match takes priority over embedding |
| `test_synonym_auto_approve` | canonical_resolver | High-confidence match auto-approved |
| `test_weighted_direction_agreement` | edge_synthesize | 1 RCT negative outweighs 3 observational positive |
| `test_hierarchical_conflict_resolution` | conflict_resolve | RCT consensus resolves conflict |
| `test_confidence_weighted_voting` | claim_adjudication | High-confidence vote outweighs low-confidence |
| `test_intra_paper_contradiction` | claim_adjudicator | Contradicting claims flagged |
| `test_contamination_patterns` | resolve_extract | Known contaminated text gets cleaned |
| `test_design_tier_promotion` | resolve_extract | "unclear" promoted to tier 4 with strong signal |
| `test_abstract_only_penalty` | skg_store | Abstract-only evidence penalized |
| `test_json_column_validation` | graph_builder | Malformed JSON rejected at insert |

### 7.2 Observability additions

**Canonicalization dashboard** (add to pipeline stats):
```python
@dataclass
class CanonizationDashboard:
    total_variables_seen: int
    exact_matches: int
    hierarchy_matches: int
    embedding_matches_auto: int
    embedding_matches_pending: int
    unresolved: int
    resolution_rate: float  # (exact + hierarchy + auto) / total
    top_unresolved: list[tuple[str, int]]  # (name, mention_count)
```

**Confidence aggregation dashboard**:
```python
@dataclass
class ConfidenceAggregationDashboard:
    edges_total: int
    edges_with_temporal_decay: int
    edges_with_sample_size: int
    retracted_papers_filtered: int
    mean_confidence: float
    median_confidence: float
    confidence_histogram: dict[str, int]  # "0.0-0.2": N, "0.2-0.4": N, ...
```

### 7.3 Eligibility rejection breakdown

**File**: `resolve_extract.py` — add to `ResolveExtractStats`:
```python
rejection_reasons: dict[str, int] = field(default_factory=dict)
# {"abstract_only": 1234, "degraded_text": 567, "theory_like": 89, ...}
```

Populate in `_eligibility_gate()`:
```python
for reason in decision.rejection_reasons:
    stats.rejection_reasons[reason] = stats.rejection_reasons.get(reason, 0) + 1
```

---

## Phase 8 — Track B/C Integration & Polish (Days 21–22)

### 8.1 Context attributes → transport scoring

**Problem**: Track B context attributes are extracted but not formally connected to transportability scoring. The `ac_skg_transport_scores` table exists but context profiles are underutilized.

**File**: `skg_query.py`, `query_edge_transport()`

Add context profile matching:
```python
def _compute_context_match_reward(
    source_context: dict,
    target_context: dict,
    moderators: list[ModerationEdge],
) -> float:
    """
    Compare context profiles and compute match reward.
    Each matching moderator increases reward.
    Each mismatching moderator decreases it.
    """
    reward = 0.0
    for mod in moderators:
        source_val = source_context.get(mod.moderator)
        target_val = target_context.get(mod.moderator)
        if source_val is not None and target_val is not None:
            if _values_compatible(source_val, target_val, mod):
                reward += 0.05  # Compatible moderator
            else:
                reward -= 0.10  # Incompatible moderator
    return reward
```

### 8.2 Moderation edges → conflict interpretation

When resolving direction conflicts, check if moderators explain the disagreement:

```python
def _check_moderator_explanation(
    positive_articles: list[ArticleEvidence],
    negative_articles: list[ArticleEvidence],
    moderators: list[ModerationEdge],
) -> str | None:
    """
    Check if a moderator variable explains the directional disagreement.
    E.g., positive studies all in developed countries, negative in developing.
    """
    for mod in moderators:
        pos_contexts = [a.context.get(mod.moderator) for a in positive_articles]
        neg_contexts = [a.context.get(mod.moderator) for a in negative_articles]
        if _contexts_disjoint(pos_contexts, neg_contexts):
            return f"Direction disagreement explained by moderator: {mod.moderator}"
    return None
```

If moderator explains conflict → status changes from "contested" to "moderated" with higher confidence.

### 8.3 Design tier recalculation after adjudication

**Problem**: If adjudicated `design_family` differs from extracted `design_family_hint`, `design_quality_tier` is not recalculated. A paper originally classified as "unclear" (tier None) that adjudicates to "rct" keeps tier None.

**Fix**: In `graph_builder.py`, after loading adjudications, recalculate tier:
```python
if adjudication.design_family != raw_claim.design_family_hint:
    new_tier = _DESIGN_TIERS.get(adjudication.design_family)
    if new_tier is not None:
        claim.design_quality_tier = new_tier
```

### 8.4 Span contamination severity tracking

Replace boolean `span_contamination_detected` with severity score:

```python
def _compute_contamination_severity(original_text: str, cleaned_text: str) -> float:
    """0.0 = no contamination, 1.0 = fully contaminated."""
    if not original_text:
        return 0.0
    removed_chars = len(original_text) - len(cleaned_text)
    return min(1.0, removed_chars / len(original_text))
```

Store in `ac_causal_claims_raw.span_contamination_severity FLOAT`.

---

## Verification Criteria

### Gate 1 — Safety (after Phase 1)
- [ ] Zero retracted papers in `ac_skg_edge_evidence` (QC check passes)
- [ ] All JSON columns validated at insert (zero parse failures in query)
- [ ] Abstract-only evidence flagged with penalty in confidence

### Gate 2 — Confidence Quality (after Phase 2)
- [ ] Temporal decay applied: 2005 paper weight < 2023 paper weight (unit test)
- [ ] Sample size factor applied: n=50 confidence < n=5000 confidence (unit test)
- [ ] Noisy-OR combination: 5 studies > 1 study for same evidence strength (unit test)
- [ ] Replication bonus subsumed (no separate log2 logic)

### Gate 3 — Canonicalization (after Phase 3)
- [ ] Resolution rate ≥ 85% (QC check passes)
- [ ] Embedding-based matches: "fiscal_revenue" → "tax.revenue" (unit test)
- [ ] Auto-approve ≥ 0.90 confidence (integration test)
- [ ] Review queue reduced by ≥ 50% compared to pre-Phase-3

### Gate 4 — Conflict Resolution (after Phase 4)
- [ ] 1 RCT "negative" + 10 observational "positive" → contested (unit test)
- [ ] Contested edge penalty proportional to minority weight (unit test)
- [ ] Hierarchical resolution: RCT consensus overrides observational majority (unit test)

### Gate 5 — Adjudication (after Phase 5)
- [ ] High-confidence vote outweighs low-confidence in consensus (unit test)
- [ ] Intra-paper contradictions detected and flagged (unit test)
- [ ] Per-dimension confidence breakdown populated (schema check)

### Gate 6 — QC (after Phase 6)
- [ ] All 6 new QC checks integrated and passing
- [ ] Benchmark passes with new scenarios
- [ ] Tightened thresholds met

### Gate 7 — Observability (after Phase 7)
- [ ] Canonization dashboard populated with non-zero values
- [ ] Confidence aggregation dashboard shows histogram
- [ ] Rejection reason breakdown available in pipeline stats

### Gate 8 — Integration (after Phase 8)
- [ ] Context attributes contribute to transport scoring
- [ ] Moderator-explained conflicts marked as "moderated"
- [ ] Design tier recalculated after adjudication
- [ ] Contamination severity tracked as float

### Final Gate — 10/10 Criteria
- [ ] All 8 phase gates pass
- [ ] All existing tests continue to pass
- [ ] 15+ new tests added and passing
- [ ] Full benchmark suite green (16 scenarios + 4 new)
- [ ] Pipeline re-run on existing corpus shows:
  - Edge confidence distribution shifted (fewer low-confidence edges)
  - Canonical resolution rate ≥ 90%
  - Zero retracted paper contamination
  - Contested edges have principled confidence penalties
