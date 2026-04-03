> **Archived:** This document reflects plans as of 2026-03-21.
> See [current docs](../../explanation/index.md) for up-to-date information.

# Lex Pipeline → 10/10: Detailed Implementation Plan

> **Current state**: 7.5/10 — architecturally complete for UA jurisdiction with sophisticated LLM-gated SPO extraction, 3-tier fact quality, norm pack assembly, compliance evaluation and impact simulation. Weak on cross-jurisdiction, entity disambiguation, confidence fusion, causal integration, and logical consistency checking.
> **Target state**: 10/10 — production-grade multi-jurisdiction legal knowledge infrastructure with formal guarantees and deep causal engine integration
> **Estimated total effort**: 22–26 days

---

## Table of Contents

1. [Phase 1 — Confidence Fusion & Fact Quality (Days 1–3)](#phase-1-confidence-fusion-fact-quality-days-1-3)
2. [Phase 2 — Entity Disambiguation & Linking (Days 4–7)](#phase-2-entity-disambiguation-linking-days-4-7)
3. [Phase 3 — Reference Resolution Upgrade (Days 8–10)](#phase-3-reference-resolution-upgrade-days-8-10)
4. [Phase 4 — LLM Hallucination Detection (Days 11–13)](#phase-4-llm-hallucination-detection-days-11-13)
5. [Phase 5 — Logical Consistency & Contradiction Detection (Days 14–16)](#phase-5-logical-consistency-contradiction-detection-days-14-16)
6. [Phase 6 — Amendment Graph & Temporal Logic (Days 17–19)](#phase-6-amendment-graph-temporal-logic-days-17-19)
7. [Phase 7 — Cross-Jurisdiction Foundation (Days 20–22)](#phase-7-cross-jurisdiction-foundation-days-20-22)
8. [Phase 8 — Causal Engine Integration (Days 23–24)](#phase-8-causal-engine-integration-days-23-24)
9. [Phase 9 — QC Hardening & Observability (Days 25–26)](#phase-9-qc-hardening-observability-days-25-26)
10. [Verification Criteria](#verification-criteria)

---

## Current Architecture Summary

```
ЄДРНПА XML (Cards 161 MB + Texts 3 GB, ~140K documents)
    ↓
[xml_parser] → NPADocument (NPACard + text)
    ↓
[structurer] → ProvisionSpan[] (articles/parts/points/subpoints/paragraphs)
    ↓
[deterministic_spo] → DeterministicExtraction (pattern-based SPO candidates)
    ↓
[llm_gate] → GateDecision (skip | auto | llm | llm_gap_fill | deferred | audit_llm)
    ↓
[spo_extractor] → SPOExtractionResult (2-pass LLM via Gonka: extract → verify)
    ↓
[postprocess] → Grounded SPO (quote matching, offset assignment)
    ↓
[reference_extractor] → ReferenceHit[] (cross-document links)
    ↓
[graph_builder] → DuckDB (lex_fact_candidates → lex_fact_grounded → lex_normative_facts)
    ↓
[embedder] → HNSW indexes (entities, facts, provisions)
    ↓
[qc + publish] → consumer_readiness.json

Runtime:
├── LegalKnowledgeGraph (hybrid search: vector + text + graph)
├── NormPack assembly (versioning → source selection → claim extraction → conflict resolution)
├── Legal evaluation (compliance checking against norm packs)
└── NormImpactAnalyzer (compliance diff between norm pack versions)
```

**3-tier fact quality**: search_candidate (all) → grounded (exact_quote + offsets) → normative_fact (canonicalized + high confidence)

---

## Phase 1 — Confidence Fusion & Fact Quality (Days 1–3)

Currently, deterministic confidence, LLM extraction confidence, and grounding confidence are tracked separately. A fact can have high LLM confidence but wrong grounding, or perfect grounding but low extraction confidence. No unified model.

### 1.1 Unified confidence model

**File**: `batch/graph_builder.py`

Replace independent confidence scores with a fused score:

```python
@dataclass(frozen=True)
class FusedConfidence:
    """Unified confidence combining all evidence sources."""
    extraction_confidence: float    # From deterministic_spo or LLM
    grounding_confidence: float     # From postprocess quote matching
    structural_confidence: float    # From structurer quality
    verification_confidence: float  # From LLM pass 2 (verify)
    fused_score: float              # Combined score
    confidence_breakdown: dict[str, float]  # For audit

def compute_fused_confidence(
    extraction_conf: float,
    grounding_status: str,
    structural_quality: str,
    verification_conf: float | None,
    extraction_source: str,
) -> FusedConfidence:
    """
    Bayesian-inspired confidence fusion.
    Uses weakest-link principle: fused ≤ min(components).
    """
    # Grounding confidence from status
    GROUNDING_SCORES = {
        "exact_quote": 1.0,
        "quote_without_offsets": 0.7,
        "offsets_without_quote": 0.5,
        "missing_quote": 0.2,
    }
    grounding_conf = GROUNDING_SCORES.get(grounding_status, 0.1)

    # Structural confidence
    STRUCTURE_SCORES = {
        "full": 1.0,
        "full_only": 0.8,
        "fallback_chunk": 0.5,
        "raw_text": 0.3,
    }
    structural_conf = STRUCTURE_SCORES.get(structural_quality, 0.5)

    # Verification pass confidence (if available)
    verify_conf = verification_conf if verification_conf is not None else extraction_conf

    # Source modifier: deterministic extractions get a slight boost
    # because they're pattern-based and verifiable
    SOURCE_MODIFIER = {
        "rule_auto": 1.05,
        "llm": 1.0,
        "llm_gap_fill": 0.9,
        "deferred": 0.7,
    }
    source_mod = SOURCE_MODIFIER.get(extraction_source, 1.0)

    # Fused score: geometric mean (sensitive to weak links)
    components = [extraction_conf, grounding_conf, structural_conf, verify_conf]
    geometric_mean = (
        functools.reduce(operator.mul, components, 1.0)
    ) ** (1.0 / len(components))

    fused = min(1.0, geometric_mean * source_mod)

    return FusedConfidence(
        extraction_confidence=extraction_conf,
        grounding_confidence=grounding_conf,
        structural_confidence=structural_conf,
        verification_confidence=verify_conf,
        fused_score=round(fused, 4),
        confidence_breakdown={
            "extraction": extraction_conf,
            "grounding": grounding_conf,
            "structural": structural_conf,
            "verification": verify_conf,
            "source_modifier": source_mod,
        },
    )
```

### 1.2 Schema update for fused confidence

**File**: `batch/graph_builder.py`, DDL section

Add columns to all fact tables:

```sql
ALTER TABLE lex_fact_candidates ADD COLUMN fused_confidence FLOAT DEFAULT NULL;
ALTER TABLE lex_fact_candidates ADD COLUMN confidence_breakdown_json TEXT DEFAULT NULL;
ALTER TABLE lex_fact_grounded ADD COLUMN fused_confidence FLOAT DEFAULT NULL;
ALTER TABLE lex_fact_grounded ADD COLUMN confidence_breakdown_json TEXT DEFAULT NULL;
ALTER TABLE lex_normative_facts ADD COLUMN fused_confidence FLOAT DEFAULT NULL;
ALTER TABLE lex_normative_facts ADD COLUMN confidence_breakdown_json TEXT DEFAULT NULL;
```

**Compute during graph_build stage**: after SPO extraction + grounding + verification, compute `fused_confidence` and store in all tiers.

### 1.3 Upgrade trust tier transitions

Replace current tier promotion logic (hardcoded filters) with confidence-driven transitions:

```python
TIER_THRESHOLDS = {
    "search_candidate": 0.0,       # All facts
    "grounded": 0.45,              # fused_confidence ≥ 0.45 + grounding ≥ "quote_without_offsets"
    "normative_fact": 0.65,        # fused_confidence ≥ 0.65 + norm_type ∈ {obligation, prohibition, permission}
    "high_confidence_norm": 0.85,  # NEW tier: gold-standard facts
}
```

Add a 4th tier `high_confidence_norm` for facts that pass all quality gates with fused_confidence ≥ 0.85.

**New table**: `lex_high_confidence_norms` (same schema as normative_facts, filtered by fused_confidence ≥ 0.85).

**Value**: Legal evaluation backends can query only high-confidence norms when strict compliance is needed, falling back to normative_facts for broader coverage.

### 1.4 Confidence calibration against gold set

**File**: `batch/benchmark.py`

If a gold benchmark dataset exists (manually annotated facts), calibrate confidence:

```python
def calibrate_confidence_thresholds(
    predicted_facts: list[dict],
    gold_facts: list[dict],
) -> CalibrationResult:
    """
    For each fused_confidence bin, compute precision/recall against gold.
    Adjust tier thresholds to maximize F1 at each tier.
    """
    bins = np.arange(0.0, 1.05, 0.05)
    precision_at_threshold = {}

    for threshold in bins:
        predicted_above = [f for f in predicted_facts if f["fused_confidence"] >= threshold]
        true_positives = len(set(f["fact_id"] for f in predicted_above) & gold_fact_ids)
        precision = true_positives / max(1, len(predicted_above))
        recall = true_positives / max(1, len(gold_facts))
        precision_at_threshold[threshold] = {"precision": precision, "recall": recall}

    # Find optimal thresholds for each tier
    # grounded: maximize recall at precision ≥ 0.7
    # normative: maximize F1 at precision ≥ 0.85
    # high_confidence: precision ≥ 0.95
    ...
```

---

## Phase 2 — Entity Disambiguation & Linking (Days 4–7)

Entity deduplication currently uses normalized English name only. "Ministry of Finance" and "Міністерство фінансів" and "Мінфін" may create 3 separate entities.

### 2.1 Multi-lingual entity resolution

**File**: `batch/graph_builder.py`, entity deduplication logic

Replace simple `_normalize_entity_name()` with multi-stage resolution:

```python
class EntityResolver:
    """Multi-lingual entity resolution with embedding-based fuzzy matching."""

    def __init__(self, embedding_model: str = "intfloat/multilingual-e5-large"):
        self._canonical_entities: dict[str, LegalEntity] = {}
        self._name_index: dict[str, str] = {}  # normalized_name → entity_id
        self._alias_index: dict[str, str] = {}  # alias → entity_id
        self._embedding_index: hnswlib.Index | None = None

    def resolve(self, name_en: str, name_uk: str, entity_type: str) -> str:
        """
        Resolve entity to canonical ID.
        Priority: exact match → alias match → embedding similarity → create new.
        """
        # 1. Exact match on normalized English name
        norm_en = _normalize_entity_name(name_en)
        if norm_en in self._name_index:
            entity_id = self._name_index[norm_en]
            self._add_alias(entity_id, name_uk)
            return entity_id

        # 2. Exact match on Ukrainian name
        norm_uk = _normalize_entity_name(name_uk)
        if norm_uk in self._name_index:
            entity_id = self._name_index[norm_uk]
            self._add_alias(entity_id, name_en)
            return entity_id

        # 3. Alias lookup (covers abbreviations like "Мінфін")
        for name in [norm_en, norm_uk, name_en.lower(), name_uk.lower()]:
            if name in self._alias_index:
                return self._alias_index[name]

        # 4. Embedding similarity (catches paraphrases)
        if self._embedding_index is not None:
            combined_text = f"{name_en} {name_uk}"
            emb = self._model.encode([combined_text], normalize_embeddings=True)[0]
            labels, distances = self._embedding_index.knn_query(emb, k=3)
            best_sim = 1.0 - distances[0][0]

            if best_sim >= 0.85:
                entity_id = self._id_list[labels[0][0]]
                self._add_alias(entity_id, name_en)
                self._add_alias(entity_id, name_uk)
                return entity_id

        # 5. Create new entity
        entity_id = _generate_entity_id(name_en, name_uk)
        self._register_entity(entity_id, name_en, name_uk, entity_type)
        return entity_id

    def _add_alias(self, entity_id: str, alias: str):
        norm = _normalize_entity_name(alias)
        if norm and norm not in self._alias_index:
            self._alias_index[norm] = entity_id
            # Also update aliases in entity record
            entity = self._canonical_entities[entity_id]
            if alias not in entity.aliases_en and alias not in entity.aliases_uk:
                # Detect language and add to appropriate alias list
                ...
```

### 2.2 Curated entity seed table

**New file**: `data/lex_knowledge/entity_seeds.yaml`

```yaml
# Curated entity mappings for Ukrainian legal domain
entities:
  - entity_id: "inst_minfin_ua"
    name_en: "Ministry of Finance of Ukraine"
    name_uk: "Міністерство фінансів України"
    entity_type: institution
    aliases_en: ["MinFin", "MOF Ukraine", "Ministry of Finance"]
    aliases_uk: ["Мінфін", "МФУ", "Мін. фінансів"]
    wikidata_id: "Q1975889"

  - entity_id: "inst_rada_ua"
    name_en: "Verkhovna Rada of Ukraine"
    name_uk: "Верховна Рада України"
    entity_type: institution
    aliases_en: ["Parliament", "Supreme Council", "Rada"]
    aliases_uk: ["ВРУ", "Рада", "парламент"]
    wikidata_id: "Q217799"

  - entity_id: "inst_kmu_ua"
    name_en: "Cabinet of Ministers of Ukraine"
    name_uk: "Кабінет Міністрів України"
    entity_type: institution
    aliases_en: ["Cabinet", "Government of Ukraine", "CMU"]
    aliases_uk: ["КМУ", "Кабмін", "уряд"]
    wikidata_id: "Q1247671"

  # ... 200+ core Ukrainian legal entities
  # Extend with EU institutions, international organizations
```

Load seeds at `EntityResolver.__init__()` as base canonical entities.

### 2.3 Wikidata alignment (optional enrichment)

For entities with `wikidata_id`, fetch additional metadata:

```python
async def enrich_from_wikidata(entity_id: str, wikidata_id: str) -> dict:
    """
    Fetch structured data from Wikidata for entity enrichment.
    Returns: inception_date, dissolution_date, parent_org, official_website, etc.
    """
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
    # ... fetch and parse
    return {
        "inception": claims.get("P571", [{}])[0].get("value"),
        "parent_org": claims.get("P749", [{}])[0].get("value"),
        "official_name": labels.get("uk", labels.get("en", "")),
    }
```

**Schema extension**: Add `wikidata_id TEXT` column to `lex_entities`.

**Value**: Enables cross-pipeline entity linking — the same "Ministry of Finance" in academic literature and legal documents resolves to the same entity.

### 2.4 Entity type taxonomy

Extend current flat `entity_type` (concept|measure|institution|document|threshold) with a hierarchy:

```python
ENTITY_TYPE_TAXONOMY = {
    "institution": {
        "government_body": ["ministry", "agency", "commission", "inspectorate"],
        "legislative_body": ["parliament", "council"],
        "judicial_body": ["court", "tribunal"],
        "international_org": ["un_agency", "eu_institution", "ifi"],
        "local_authority": ["municipality", "oblast_admin"],
    },
    "concept": {
        "legal_concept": ["right", "obligation", "prohibition", "sanction"],
        "policy_domain": ["fiscal", "social", "environmental", "labor"],
        "economic_measure": ["tax", "subsidy", "tariff", "quota"],
    },
    "document": {
        "law": ["code", "statute", "decree"],
        "regulation": ["resolution", "order", "instruction"],
        "international": ["treaty", "convention", "agreement"],
    },
    "threshold": {
        "numeric": ["percentage", "absolute_value", "ratio"],
        "temporal": ["deadline", "duration", "frequency"],
    },
    "person_role": {
        "official": ["minister", "head_of_agency", "judge"],
        "regulated_subject": ["taxpayer", "employer", "licensee"],
    },
}
```

**Add column**: `entity_subtype TEXT` to `lex_entities`.

**Populate**: LLM extraction prompt already extracts entity_type. Extend to request subtype. For deterministic extractions, infer from context patterns.

---

## Phase 3 — Reference Resolution Upgrade (Days 8–10)

Current deterministic patterns cover ~80% of references. The remaining 20% are ambiguous ("цього закону", "зазначеного документа") or complex (chain references, cross-law references by number+date).

### 3.1 Two-stage reference resolution

**File**: `batch/reference_extractor.py`

```python
class ReferenceResolver:
    """Two-stage reference resolution: deterministic + contextual."""

    def resolve(
        self,
        reference_hit: ReferenceHit,
        source_doc: NPADocument,
        corpus_index: dict[str, NPACard],  # reestr_code → card
    ) -> ResolvedReference:
        # Stage 1: Deterministic resolution
        resolved = self._resolve_deterministic(reference_hit, source_doc, corpus_index)
        if resolved.status == "resolved":
            return resolved

        # Stage 2: Contextual resolution (for ambiguous references)
        return self._resolve_contextual(reference_hit, source_doc, corpus_index)

    def _resolve_deterministic(self, hit, doc, index) -> ResolvedReference:
        """
        Pattern-based resolution for explicit references.
        Handles: law number+date, specific article citations, annex references.
        """
        if hit.target_number and hit.target_date:
            # Search corpus by law number + date
            candidates = [
                card for card in index.values()
                if _match_law_number(card, hit.target_number)
                and _match_date(card, hit.target_date)
            ]
            if len(candidates) == 1:
                return ResolvedReference(
                    target_doc_id=candidates[0].doc_id,
                    status="resolved",
                    confidence=0.95,
                    method="deterministic_number_date",
                )
            elif len(candidates) > 1:
                return ResolvedReference(
                    status="ambiguous",
                    candidates=[c.doc_id for c in candidates],
                    confidence=0.5,
                    method="deterministic_multiple_matches",
                )

        # Self-references ("цього закону")
        if hit.relation_hint == "self_reference":
            return ResolvedReference(
                target_doc_id=doc.card.doc_id,
                status="resolved",
                confidence=1.0,
                method="self_reference",
            )

        return ResolvedReference(status="unresolved", confidence=0.0)

    def _resolve_contextual(self, hit, doc, index) -> ResolvedReference:
        """
        Contextual resolution for ambiguous references.
        Uses: document family lineage, reference graph neighborhood, semantic similarity.
        """
        # Strategy 1: Check document family (amendments of same base law)
        family_candidates = [
            card for card in index.values()
            if card.doc_family_id == doc.card.doc_family_id
            and card.doc_id != doc.card.doc_id
        ]

        # Strategy 2: Check reference neighborhood (docs that reference same target)
        # If doc A references "the law" and doc B (in same family) also references
        # the same target explicitly, infer A's target from B's resolved reference.

        # Strategy 3: Embedding-based matching of reference context text
        # against document titles in corpus
        if hit.target_raw:
            title_similarities = self._compute_title_similarities(
                hit.target_raw, [c.name for c in index.values()]
            )
            best = max(title_similarities, key=lambda x: x[1])
            if best[1] >= 0.75:
                return ResolvedReference(
                    target_doc_id=best[0],
                    status="resolved",
                    confidence=best[1] * 0.8,  # Penalty for contextual
                    method="contextual_embedding",
                )

        return ResolvedReference(status="unresolved", confidence=0.0)
```

### 3.2 Reference chain resolution

**Problem**: Law A references Law B, which references Law C. Currently no transitive resolution.

```python
def resolve_reference_chains(
    edges: list[ResolvedReference],
    max_depth: int = 3,
) -> list[ReferenceChain]:
    """
    Build reference chains: A → B → C.
    Useful for: tracing amendment lineage, finding original source of obligation.
    """
    graph: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge.status == "resolved":
            graph[edge.source_doc_id].append(edge.target_doc_id)

    chains = []
    for start in graph:
        chain = [start]
        current = start
        for _ in range(max_depth):
            targets = graph.get(current, [])
            if not targets:
                break
            # Follow primary target (first resolved reference)
            current = targets[0]
            if current in chain:
                # Cycle detected
                chain.append(f"CYCLE:{current}")
                break
            chain.append(current)

        if len(chain) > 1:
            chains.append(ReferenceChain(
                chain=chain,
                depth=len(chain) - 1,
                relation_types=[...],  # amends, repeals, etc.
            ))

    return chains
```

### 3.3 Resolution coverage tracking

**New table**: `lex_reference_resolution_audit`

```sql
CREATE TABLE IF NOT EXISTS lex_reference_resolution_audit (
    ref_id TEXT PRIMARY KEY,
    source_doc_id TEXT NOT NULL,
    source_anchor TEXT,
    ref_text_uk TEXT,
    target_raw TEXT,
    resolution_method TEXT,        -- deterministic_number_date|self_reference|contextual_embedding|unresolved
    resolution_status TEXT,        -- resolved|ambiguous|unresolved
    resolution_confidence FLOAT,
    candidate_count INTEGER,       -- Number of candidate targets
    selected_target_doc_id TEXT,
    alternatives_json TEXT,        -- Other candidate doc_ids with scores
    resolved_at TEXT
);
```

**QC target**: Resolution rate ≥ 90% (currently ~80%).

---

## Phase 4 — LLM Hallucination Detection (Days 11–13)

The 2-pass extract→verify approach catches some errors, but has no mechanism to detect facts that are semantically coherent but fabricated (e.g., citing a non-existent article, inventing an obligation not in the text).

### 4.1 Structural consistency checking

**File**: `batch/postprocess.py` (or new `batch/hallucination_detector.py`)

```python
class HallucinationDetector:
    """Detects LLM-fabricated facts by checking against known structure."""

    def check_fact(
        self,
        fact: SPOCandidate,
        provision: ProvisionSpan,
        doc_structure: list[ProvisionSpan],  # All provisions in this doc
    ) -> list[HallucinationFlag]:
        flags = []

        # Check 1: Citation validation
        # If fact references "Article X" — does Article X exist in this document?
        cited_articles = self._extract_article_refs(fact.fact_text)
        for article_ref in cited_articles:
            if not self._article_exists(article_ref, doc_structure):
                flags.append(HallucinationFlag(
                    type="phantom_article_reference",
                    detail=f"References Article {article_ref} which does not exist in document",
                    severity="high",
                ))

        # Check 2: Entity grounding
        # If fact mentions a specific institution — does the provision text
        # actually mention it? (Catches LLM substituting "Ministry of Finance"
        # when text says "relevant ministry")
        if fact.subject_uk and fact.source_quote_uk:
            if fact.subject_uk.lower() not in fact.source_quote_uk.lower():
                # Subject not in quote — possible hallucination
                # But could be legitimate extraction from broader context
                if fact.subject_uk.lower() not in provision.text.lower():
                    flags.append(HallucinationFlag(
                        type="ungrounded_subject",
                        detail=f"Subject '{fact.subject_uk}' not found in provision text",
                        severity="medium",
                    ))

        # Check 3: Numeric consistency
        # If fact contains a threshold (e.g., "5%") — does the provision
        # text actually contain that number?
        fact_numbers = self._extract_numbers(fact.fact_text)
        provision_numbers = self._extract_numbers(provision.text)
        for num in fact_numbers:
            if num not in provision_numbers:
                flags.append(HallucinationFlag(
                    type="phantom_number",
                    detail=f"Number {num} in fact not found in provision text",
                    severity="high",
                ))

        # Check 4: Norm type consistency
        # If fact says "obligation" — does the provision actually contain
        # obligation markers (повинен, зобов'язаний, etc.)?
        if fact.norm_type == "obligation":
            if not _has_obligation_markers(provision.text):
                flags.append(HallucinationFlag(
                    type="norm_type_mismatch",
                    detail="Fact classified as obligation but provision lacks obligation markers",
                    severity="medium",
                ))
        elif fact.norm_type == "prohibition":
            if not _has_prohibition_markers(provision.text):
                flags.append(HallucinationFlag(
                    type="norm_type_mismatch",
                    detail="Fact classified as prohibition but provision lacks prohibition markers",
                    severity="medium",
                ))

        return flags
```

### 4.2 Consistency voting across extraction passes

**File**: `batch/spo_extractor.py`

Add a 3rd extraction pass for high-value provisions:

```python
async def extract_with_consistency_check(
    provision: ProvisionSpan,
    config: BatchConfig,
) -> SPOExtractionResult:
    """
    3-pass extraction with consistency voting.
    Pass 1: Extract (temperature 0.1)
    Pass 2: Verify (temperature 0.1)
    Pass 3: Independent re-extract (temperature 0.3, different prompt variation)
    """
    # Pass 1 + 2: existing extract + verify
    result_1 = await _extract_spo(provision, config)
    result_2 = await _verify_spo(result_1, provision, config)

    # Pass 3: Independent re-extraction (only for high-value provisions)
    if provision.route_class in ("threshold_bearing", "reference_bearing"):
        result_3 = await _extract_spo(
            provision, config,
            prompt_variation="alternative",
            temperature=0.3,
        )

        # Compare facts between pass 2 and pass 3
        for fact_2 in result_2.statements:
            matching_3 = _find_matching_fact(fact_2, result_3.statements)
            if matching_3:
                # Agreement → boost confidence
                fact_2.confidence = min(1.0, fact_2.confidence * 1.1)
                fact_2.consistency_score = 1.0
            else:
                # Disagreement → flag for review
                fact_2.consistency_score = 0.5
                fact_2.flags.append("pass3_disagreement")

    return result_2
```

### 4.3 Hallucination rate tracking

**Add to pipeline stats**:
```python
@dataclass
class HallucinationMetrics:
    facts_checked: int = 0
    phantom_article_refs: int = 0
    ungrounded_subjects: int = 0
    phantom_numbers: int = 0
    norm_type_mismatches: int = 0
    pass3_disagreements: int = 0
    hallucination_rate: float = 0.0  # flags / facts_checked
```

**QC gate**: `hallucination_rate ≤ 3%` for normative_facts tier.

### 4.4 Schema update for hallucination flags

```sql
ALTER TABLE lex_fact_candidates ADD COLUMN hallucination_flags_json TEXT DEFAULT NULL;
ALTER TABLE lex_fact_candidates ADD COLUMN consistency_score FLOAT DEFAULT NULL;
```

Facts with `hallucination_flags` are blocked from promotion to `lex_normative_facts`.

---

## Phase 5 — Logical Consistency & Contradiction Detection (Days 14–16)

Currently no check for contradictory norms within the same document or across documents (e.g., Article 5 says "must provide" and Article 12 says "prohibited to provide" for the same subject-object pair).

### 5.1 Intra-document contradiction detection

**New file**: `batch/consistency_checker.py`

```python
class ConsistencyChecker:
    """Detect logical contradictions between extracted facts."""

    # Contradictory norm type pairs
    CONTRADICTORY_PAIRS = {
        ("obligation", "prohibition"),    # "must" vs "must not"
        ("permission", "prohibition"),    # "may" vs "must not"
    }

    def check_intra_document(
        self,
        facts: list[SPOCandidate],
        doc_id: str,
    ) -> list[ConsistencyIssue]:
        """
        Detect contradictions within the same document.
        Two facts contradict if they share (subject, object) but have
        contradictory norm_types applied to the same action.
        """
        issues = []

        # Group facts by (subject_normalized, object_normalized)
        pairs: dict[tuple[str, str], list[SPOCandidate]] = defaultdict(list)
        for fact in facts:
            key = (
                _normalize_entity_name(fact.subject_en or fact.subject_uk or ""),
                _normalize_entity_name(fact.object_en or fact.object_uk or ""),
            )
            if key[0] and key[1]:
                pairs[key].append(fact)

        for (subj, obj), group_facts in pairs.items():
            norm_types = {f.norm_type for f in group_facts if f.norm_type}

            for nt1, nt2 in self.CONTRADICTORY_PAIRS:
                if nt1 in norm_types and nt2 in norm_types:
                    fact_1 = next(f for f in group_facts if f.norm_type == nt1)
                    fact_2 = next(f for f in group_facts if f.norm_type == nt2)

                    # Check if actions are the same (not just subject-object)
                    if self._actions_overlap(fact_1, fact_2):
                        issues.append(ConsistencyIssue(
                            type="intra_document_contradiction",
                            doc_id=doc_id,
                            fact_id_1=fact_1.fact_id,
                            fact_id_2=fact_2.fact_id,
                            subject=subj,
                            object_=obj,
                            norm_type_1=nt1,
                            norm_type_2=nt2,
                            anchor_1=fact_1.provision_anchor,
                            anchor_2=fact_2.provision_anchor,
                            severity="high",
                            explanation=(
                                f"Article {fact_1.provision_anchor} states {nt1} "
                                f"while Article {fact_2.provision_anchor} states {nt2} "
                                f"for the same subject-object pair"
                            ),
                        ))

        return issues

    def _actions_overlap(self, f1: SPOCandidate, f2: SPOCandidate) -> bool:
        """Check if two facts refer to the same action (predicate similarity)."""
        pred_1 = _normalize_entity_name(f1.predicate or "")
        pred_2 = _normalize_entity_name(f2.predicate or "")
        if pred_1 == pred_2:
            return True
        # Fuzzy match: action_canon field
        if f1.action_canon and f2.action_canon and f1.action_canon == f2.action_canon:
            return True
        return False
```

### 5.2 Cross-document contradiction detection

```python
def check_cross_document(
    self,
    con: duckdb.DuckDBPyConnection,
    jurisdiction: str = "UA",
) -> list[ConsistencyIssue]:
    """
    Detect contradictions across different active documents.
    Only considers facts from currently active (non-repealed) documents.
    """
    # Query all normative facts from active documents
    contradictions = con.execute("""
        WITH active_norms AS (
            SELECT f.*, v.is_latest, v.doc_status
            FROM lex_normative_facts f
            JOIN lex_doc_versions v ON f.doc_id = v.doc_id
            WHERE v.is_latest = TRUE
              AND v.doc_status NOT IN ('скасовано', 'втратив чинність')
              AND f.jurisdiction = ?
        ),
        potential_conflicts AS (
            SELECT
                a.fact_id AS fact_id_1,
                b.fact_id AS fact_id_2,
                a.subject_en, a.object_en,
                a.norm_type AS norm_type_1,
                b.norm_type AS norm_type_2,
                a.doc_id AS doc_id_1,
                b.doc_id AS doc_id_2,
                a.provision_anchor AS anchor_1,
                b.provision_anchor AS anchor_2,
                a.action_canon AS action_1,
                b.action_canon AS action_2
            FROM active_norms a
            JOIN active_norms b
                ON a.subject_en = b.subject_en
                AND a.object_en = b.object_en
                AND a.doc_id < b.doc_id  -- Avoid duplicates
                AND (
                    (a.norm_type = 'obligation' AND b.norm_type = 'prohibition')
                    OR (a.norm_type = 'prohibition' AND b.norm_type = 'obligation')
                    OR (a.norm_type = 'permission' AND b.norm_type = 'prohibition')
                    OR (a.norm_type = 'prohibition' AND b.norm_type = 'permission')
                )
        )
        SELECT * FROM potential_conflicts
        WHERE action_1 = action_2 OR action_1 IS NULL OR action_2 IS NULL
    """, [jurisdiction]).fetchall()

    return [
        ConsistencyIssue(
            type="cross_document_contradiction",
            fact_id_1=row[0],
            fact_id_2=row[1],
            ...
        )
        for row in contradictions
    ]
```

### 5.3 Contradiction resolution via lex specialis / lex posterior

Not all contradictions are errors — legal systems have resolution principles:

```python
def resolve_contradiction(
    issue: ConsistencyIssue,
    doc_1: NPACard,
    doc_2: NPACard,
) -> ContradictionResolution:
    """
    Apply legal interpretation principles to resolve contradictions.
    1. Lex posterior: later law prevails over earlier
    2. Lex specialis: specific law prevails over general
    3. Lex superior: higher authority prevails
    """
    # Lex posterior
    if doc_1.date_acc and doc_2.date_acc:
        if doc_1.date_acc > doc_2.date_acc:
            prevailing = doc_1.doc_id
            principle = "lex_posterior"
        elif doc_2.date_acc > doc_1.date_acc:
            prevailing = doc_2.doc_id
            principle = "lex_posterior"
        else:
            prevailing = None
            principle = "same_date_unresolvable"
    else:
        prevailing = None
        principle = "missing_dates"

    # Lex superior (hierarchy: Конституція > Закон > Постанова КМУ > Наказ)
    DOC_TYPE_HIERARCHY = {
        "Конституція": 1,
        "Кодекс": 2,
        "Закон": 3,
        "Указ Президента": 4,
        "Постанова КМУ": 5,
        "Наказ": 6,
        "Розпорядження": 7,
    }
    rank_1 = DOC_TYPE_HIERARCHY.get(doc_1.doc_type, 99)
    rank_2 = DOC_TYPE_HIERARCHY.get(doc_2.doc_type, 99)
    if rank_1 < rank_2:
        prevailing = doc_1.doc_id
        principle = "lex_superior"
    elif rank_2 < rank_1:
        prevailing = doc_2.doc_id
        principle = "lex_superior"

    return ContradictionResolution(
        issue_id=issue.issue_id,
        prevailing_doc_id=prevailing,
        principle=principle,
        confidence=0.85 if prevailing else 0.3,
        requires_manual_review=prevailing is None,
    )
```

### 5.4 Schema for consistency issues

**New table**: `lex_consistency_issues`

```sql
CREATE TABLE IF NOT EXISTS lex_consistency_issues (
    issue_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,              -- intra_document|cross_document
    fact_id_1 TEXT NOT NULL,
    fact_id_2 TEXT NOT NULL,
    doc_id_1 TEXT NOT NULL,
    doc_id_2 TEXT,                   -- NULL for intra-document
    subject_en TEXT,
    object_en TEXT,
    norm_type_1 TEXT,
    norm_type_2 TEXT,
    severity TEXT,                   -- high|medium|low
    resolution_principle TEXT,       -- lex_posterior|lex_superior|lex_specialis|unresolved
    prevailing_doc_id TEXT,
    resolution_confidence FLOAT,
    requires_manual_review BOOLEAN DEFAULT TRUE,
    resolved_at TEXT
);
```

---

## Phase 6 — Amendment Graph & Temporal Logic (Days 17–19)

### 6.1 Explicit amendment AST

`lex_doc_versions` tracks version lineage but doesn't model *what changed* between versions. Need a structured diff.

**New table**: `lex_amendments`

```sql
CREATE TABLE IF NOT EXISTS lex_amendments (
    amendment_id TEXT PRIMARY KEY,
    amending_doc_id TEXT NOT NULL,       -- The document that introduces the change
    amended_doc_id TEXT NOT NULL,        -- The document being changed
    amendment_type TEXT NOT NULL,         -- add_provision|remove_provision|modify_provision|
                                         -- replace_text|add_annex|repeal_full|rename
    target_anchor TEXT,                  -- Article/provision being amended (if applicable)
    old_text_uk TEXT,                    -- Original text (for modify/replace)
    new_text_uk TEXT,                    -- New text (for modify/replace/add)
    effective_from TEXT,                 -- When amendment takes effect
    detected_by TEXT DEFAULT 'pattern',  -- pattern|llm|manual
    confidence FLOAT DEFAULT 0.8
);
```

### 6.2 Amendment detection from text patterns

**File**: `batch/amendment_detector.py` (new)

```python
class AmendmentDetector:
    """Extract structured amendments from amendment laws."""

    # Common Ukrainian amendment patterns
    _AMEND_PATTERNS = [
        # "У статті 5 слова 'X' замінити словами 'Y'"
        re.compile(
            r"[Уу]\s+статт[іи]\s+(\d+)\s+слова?\s+[«\"'](.*?)[»\"']\s+"
            r"замінити\s+словами?\s+[«\"'](.*?)[»\"']",
            re.DOTALL,
        ),
        # "Статтю 7 викласти в такій редакції: ..."
        re.compile(
            r"[Сс]татт[юю]\s+(\d+)\s+викласти\s+в\s+такій\s+редакції\s*:\s*(.*?)(?=\n\s*\d+[\.\)]|\Z)",
            re.DOTALL,
        ),
        # "Доповнити статтею 5-1 такого змісту: ..."
        re.compile(
            r"[Дд]оповнити\s+статтею\s+([\d\-]+)\s+такого\s+змісту\s*:\s*(.*?)(?=\n\s*\d+[\.\)]|\Z)",
            re.DOTALL,
        ),
        # "Статтю 12 виключити"
        re.compile(r"[Сс]татт[юю]\s+(\d+)\s+виключити"),
        # "Пункт 3 частини першої статті 8 виключити"
        re.compile(
            r"[Пп]ункт\s+(\d+)\s+частини\s+(\w+)\s+статт[іи]\s+(\d+)\s+виключити"
        ),
    ]

    def detect_amendments(
        self,
        amending_doc: NPADocument,
        corpus_index: dict[str, NPACard],
    ) -> list[Amendment]:
        amendments = []

        # Identify target document from references
        target_refs = self._find_amendment_targets(amending_doc)

        for provision in amending_doc.provisions:
            for pattern in self._AMEND_PATTERNS:
                match = pattern.search(provision.text)
                if match:
                    amendment = self._parse_amendment(match, provision, target_refs)
                    if amendment:
                        amendments.append(amendment)

        return amendments
```

### 6.3 Temporal logic for complex effective dates

**Problem**: Simple ISO range (`effective_from`, `effective_to`) doesn't capture "enters into force 6 months after publication" or "applies starting from the fiscal year following adoption".

**File**: `corpus/versioning.py`

```python
@dataclass(frozen=True)
class TemporalConstraint:
    """Rich temporal constraint for norm effectiveness."""
    constraint_type: Literal[
        "fixed_date",           # "з 1 січня 2025 року"
        "relative_to_publication", # "через 6 місяців з дня опублікування"
        "relative_to_event",    # "з дня набрання чинності закону X"
        "fiscal_year",          # "починаючи з бюджетного року, що настає"
        "conditional",          # "після створення реєстру"
        "until_repealed",       # "до скасування"
        "sunset",               # "строком на 5 років"
    ]
    effective_from_iso: str | None     # Resolved date (if resolvable)
    effective_to_iso: str | None       # Resolved end date (if resolvable)
    raw_text_uk: str                   # Original temporal text
    resolved: bool                     # Whether dates were resolved
    resolution_method: str             # "pattern"|"llm"|"manual"|"unresolved"
    confidence: float

TEMPORAL_PATTERNS = [
    # "з 1 січня 2025 року"
    (re.compile(r"з\s+(\d{1,2})\s+(січня|лютого|березня|квітня|травня|червня|"
                r"липня|серпня|вересня|жовтня|листопада|грудня)\s+(\d{4})\s+року"),
     "fixed_date"),
    # "через X місяців з дня опублікування"
    (re.compile(r"через\s+(\d+)\s+місяц\w*\s+з\s+дня\s+(опублікування|прийняття)"),
     "relative_to_publication"),
    # "набирає чинності з дня його опублікування"
    (re.compile(r"набирає\s+чинності?\s+з\s+дня\s+(його\s+)?опублікування"),
     "relative_to_publication"),
]
```

### 6.4 Amendment graph visualization data

**New table**: `lex_amendment_graph`

```sql
CREATE TABLE IF NOT EXISTS lex_amendment_graph (
    edge_id TEXT PRIMARY KEY,
    source_doc_id TEXT NOT NULL,         -- Amending document
    target_doc_id TEXT NOT NULL,         -- Amended document
    amendment_count INTEGER DEFAULT 1,   -- Number of provisions amended
    relation_type TEXT NOT NULL,          -- amends|repeals|supplements|replaces
    effective_from TEXT,
    effective_to TEXT,
    doc_type_source TEXT,                -- Type of amending document
    doc_type_target TEXT                 -- Type of amended document
);
```

This enables graph queries: "show me all amendments to Tax Code since 2020", "which laws were most frequently amended?", "trace the legislative history of Article 5 of Law X".

---

## Phase 7 — Cross-Jurisdiction Foundation (Days 20–22)

### 7.1 Jurisdiction plugin architecture

**Problem**: All structure extraction patterns are Ukrainian (`_REQUIRE_RE = r"повинен|повинна|..."`, article regex, etc.). Adding EU or other country requires modifying core code.

**New file**: `batch/jurisdictions/protocol.py`

```python
from typing import Protocol

class JurisdictionPlugin(Protocol):
    """Protocol for jurisdiction-specific processing rules."""

    @property
    def jurisdiction_code(self) -> str:
        """ISO jurisdiction code (e.g., 'UA', 'EU', 'DE')."""
        ...

    @property
    def language_codes(self) -> list[str]:
        """Supported languages (e.g., ['uk'] for UA, ['en', 'fr', 'de'] for EU)."""
        ...

    def structure_patterns(self) -> StructurePatterns:
        """Return regex patterns for article/section/paragraph extraction."""
        ...

    def normative_signal_patterns(self) -> NormativeSignalPatterns:
        """Return patterns for obligation/prohibition/permission detection."""
        ...

    def reference_patterns(self) -> list[re.Pattern]:
        """Return patterns for cross-reference extraction."""
        ...

    def document_type_hierarchy(self) -> dict[str, int]:
        """Return document type ranking for lex superior resolution."""
        ...

    def temporal_patterns(self) -> list[tuple[re.Pattern, str]]:
        """Return patterns for temporal constraint extraction."""
        ...

@dataclass(frozen=True)
class StructurePatterns:
    article_re: re.Pattern
    part_re: re.Pattern | None
    point_re: list[re.Pattern]
    subpoint_re: re.Pattern | None
    paragraph_re: re.Pattern | None
    section_heading_re: re.Pattern | None  # For laws organized by sections/chapters

@dataclass(frozen=True)
class NormativeSignalPatterns:
    obligation_re: re.Pattern
    prohibition_re: re.Pattern
    permission_re: re.Pattern
    delegation_re: re.Pattern
    approval_re: re.Pattern
    amendment_re: re.Pattern
    repeal_re: re.Pattern
```

### 7.2 Ukrainian jurisdiction plugin (extract from current code)

**New file**: `batch/jurisdictions/ua.py`

```python
class UkrainianJurisdiction:
    jurisdiction_code = "UA"
    language_codes = ["uk"]

    def structure_patterns(self) -> StructurePatterns:
        return StructurePatterns(
            article_re=re.compile(r"^[\s]*Стаття\s+(\d+[\-\d]*)[\.\s]"),
            part_re=re.compile(r"^\s*(\d+)\.\s+"),
            point_re=[
                re.compile(r"^\s*(\d+)\)\s+\S"),
                re.compile(r"^\s*(\d+)\.\s+\S"),
            ],
            subpoint_re=re.compile(r"^\s*([а-яА-Яa-zA-Z])\)\s+\S"),
            paragraph_re=None,
            section_heading_re=re.compile(r"^[\s]*Розділ\s+([IVXLCDM]+|[0-9]+)"),
        )

    def normative_signal_patterns(self) -> NormativeSignalPatterns:
        return NormativeSignalPatterns(
            obligation_re=re.compile(
                r"повинен|повинна|повинні|зобов[''`ʼ]яз|має\s+забезпечити",
                re.IGNORECASE,
            ),
            prohibition_re=re.compile(
                r"забороняється|заборонено|не\s+має\s+права|не\s+допускається",
                re.IGNORECASE,
            ),
            # ... existing patterns from deterministic_spo.py
        )

    def document_type_hierarchy(self) -> dict[str, int]:
        return {
            "Конституція": 1,
            "Кодекс": 2,
            "Закон": 3,
            "Указ Президента": 4,
            "Постанова КМУ": 5,
            "Наказ": 6,
            "Розпорядження": 7,
        }
```

### 7.3 EU jurisdiction plugin (foundation)

**New file**: `batch/jurisdictions/eu.py`

```python
class EUJurisdiction:
    jurisdiction_code = "EU"
    language_codes = ["en", "fr", "de"]

    def structure_patterns(self) -> StructurePatterns:
        return StructurePatterns(
            article_re=re.compile(r"^[\s]*Article\s+(\d+[\-\d]*)[\.\s]", re.IGNORECASE),
            part_re=re.compile(r"^\s*(\d+)\.\s+"),
            point_re=[
                re.compile(r"^\s*\(([a-z])\)\s+"),  # (a) text
                re.compile(r"^\s*\((\d+)\)\s+"),     # (1) text
            ],
            subpoint_re=re.compile(r"^\s*\(([ivxlc]+)\)\s+", re.IGNORECASE),
            paragraph_re=None,
            section_heading_re=re.compile(r"^[\s]*(?:Chapter|Section|Title)\s+([IVXLCDM]+|\d+)", re.IGNORECASE),
        )

    def normative_signal_patterns(self) -> NormativeSignalPatterns:
        return NormativeSignalPatterns(
            obligation_re=re.compile(r"\bshall\b|\bmust\b|\bis required to\b", re.IGNORECASE),
            prohibition_re=re.compile(r"\bshall not\b|\bmust not\b|\bprohibited\b|\bforbidden\b", re.IGNORECASE),
            permission_re=re.compile(r"\bmay\b|\bis entitled to\b|\bhas the right to\b", re.IGNORECASE),
            # ...
        )

    def document_type_hierarchy(self) -> dict[str, int]:
        return {
            "Treaty": 1,
            "Regulation": 2,
            "Directive": 3,
            "Decision": 4,
            "Recommendation": 5,
            "Opinion": 6,
        }
```

### 7.4 Integrate plugins into pipeline

**File**: `batch/pipeline.py`

```python
JURISDICTION_REGISTRY: dict[str, type[JurisdictionPlugin]] = {
    "UA": UkrainianJurisdiction,
    "EU": EUJurisdiction,
}

def _get_jurisdiction(config: BatchConfig) -> JurisdictionPlugin:
    cls = JURISDICTION_REGISTRY.get(config.jurisdiction, UkrainianJurisdiction)
    return cls()
```

Pass jurisdiction plugin to `structurer.py`, `deterministic_spo.py`, `reference_extractor.py` instead of hardcoded patterns.

---

## Phase 8 — Causal Engine Integration (Days 23–24)

### 8.1 Norm → Causal mechanism mapping

**Problem**: The causal engine needs to know *how* a legal norm translates to a causal mechanism. "Minimum wage set to X" → "minimum_wage → employment" is a causal pathway, but the lex pipeline doesn't expose this connection.

**New file**: `knowledge/causal_bridge.py`

```python
class LexCausalBridge:
    """
    Maps legal norms to causal mechanisms for the foundry.

    A legal norm (obligation/prohibition/permission) implies a causal pathway:
    - "employer must pay minimum wage ≥ X" → intervention on variable "minimum_wage"
    - "vehicles prohibited from zone Y" → intervention on "traffic_flow_in_Y"

    This bridge extracts:
    1. Intervention variable: what is being regulated?
    2. Intervention type: set_value | bound_above | bound_below | prohibit | require
    3. Intervention magnitude: numeric threshold if available
    4. Affected outcome variables: what is expected to change?
    """

    def extract_causal_mechanisms(
        self,
        normative_facts: list[LegalFact],
        skg_variables: set[str],  # Canonical variables from academic pipeline
    ) -> list[CausalMechanism]:
        mechanisms = []

        for fact in normative_facts:
            # Match fact subject/object to canonical variables
            intervention_var = self._resolve_to_canonical(
                fact.subject_en, fact.object_en, skg_variables
            )
            if not intervention_var:
                continue

            # Determine intervention type from norm_type + action
            intervention_type = self._classify_intervention(fact)

            # Extract magnitude from thresholds
            magnitude = self._extract_magnitude(fact)

            # Infer affected outcomes from SKG edges
            affected = self._infer_affected_outcomes(intervention_var, skg_variables)

            mechanisms.append(CausalMechanism(
                fact_id=fact.fact_id,
                doc_id=fact.doc_id,
                intervention_variable=intervention_var,
                intervention_type=intervention_type,
                intervention_magnitude=magnitude,
                affected_outcomes=affected,
                norm_type=fact.norm_type,
                jurisdiction=fact.jurisdiction,
                effective_from=fact.effective_from,
                effective_to=fact.effective_to,
                confidence=fact.fused_confidence,
            ))

        return mechanisms

    def _classify_intervention(self, fact: LegalFact) -> str:
        """Map norm_type + action to intervention type."""
        if fact.norm_type == "obligation":
            if fact.thresholds_json:
                return "bound_below"  # "must provide at least X"
            return "require"
        elif fact.norm_type == "prohibition":
            if fact.thresholds_json:
                return "bound_above"  # "must not exceed X"
            return "prohibit"
        elif fact.norm_type == "permission":
            return "allow"
        return "unknown"

    def _resolve_to_canonical(
        self,
        subject_en: str,
        object_en: str,
        skg_variables: set[str],
    ) -> str | None:
        """
        Map legal entity names to canonical causal variable names.
        E.g., "minimum wage" → "minimum_wage"
        E.g., "carbon emissions" → "co2_emissions"
        """
        for name in [subject_en, object_en]:
            if not name:
                continue
            canonical = name.lower().replace(" ", "_").replace("-", "_")
            if canonical in skg_variables:
                return canonical
            # Fuzzy match
            for var in skg_variables:
                if _token_overlap(canonical, var) >= 0.6:
                    return var
        return None
```

### 8.2 Legal constraints for causal estimation

**File**: `knowledge/causal_bridge.py`

```python
def extract_estimation_constraints(
    self,
    mechanisms: list[CausalMechanism],
) -> list[EstimationConstraint]:
    """
    Extract constraints that the causal engine must respect.

    E.g., if a law sets minimum_wage = 6700 UAH,
    then causal estimation of minimum_wage effects must use
    this as the treatment value, not estimated from data.
    """
    constraints = []

    for mech in mechanisms:
        if mech.intervention_magnitude is not None:
            constraints.append(EstimationConstraint(
                variable=mech.intervention_variable,
                constraint_type=mech.intervention_type,
                value=mech.intervention_magnitude.value,
                unit=mech.intervention_magnitude.unit,
                effective_from=mech.effective_from,
                effective_to=mech.effective_to,
                source_fact_id=mech.fact_id,
                source_doc_id=mech.doc_id,
                confidence=mech.confidence,
            ))

    return constraints
```

### 8.3 Schema for causal mechanisms

**New table**: `lex_causal_mechanisms`

```sql
CREATE TABLE IF NOT EXISTS lex_causal_mechanisms (
    mechanism_id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    intervention_variable TEXT NOT NULL,  -- Canonical variable name
    intervention_type TEXT NOT NULL,       -- require|prohibit|bound_above|bound_below|allow
    magnitude_value FLOAT,
    magnitude_unit TEXT,
    affected_outcomes_json TEXT,           -- JSON array of canonical variable names
    norm_type TEXT,
    jurisdiction TEXT,
    effective_from TEXT,
    effective_to TEXT,
    confidence FLOAT,
    mapping_method TEXT DEFAULT 'pattern'  -- pattern|embedding|llm
);
```

### 8.4 Integration point with scientist workflow

**File**: `scientist/nodes/builtins/causal/resolve_transport.py` (existing)

Add legal constraint loading:

```python
def resolve_legal_constraints(
    intervention_var: str,
    jurisdiction: str,
    as_of: str,
    lex_db_path: Path,
) -> list[EstimationConstraint]:
    """
    Load legal constraints for a variable from the lex knowledge graph.
    These constraints inform the causal engine about legally mandated values.
    """
    bridge = LexCausalBridge(db_path=lex_db_path)
    mechanisms = bridge.query_mechanisms_for_variable(intervention_var, jurisdiction, as_of)
    return bridge.extract_estimation_constraints(mechanisms)
```

---

## Phase 9 — QC Hardening & Observability (Days 25–26)

### 9.1 New QC checks

**File**: `batch/qc.py`

```python
# 1. Hallucination rate check
def _check_hallucination_rate(con) -> QCCheck:
    flagged = con.execute("""
        SELECT COUNT(*) FROM lex_fact_candidates
        WHERE hallucination_flags_json IS NOT NULL
          AND hallucination_flags_json != '[]'
    """).fetchone()[0]
    total = con.execute("SELECT COUNT(*) FROM lex_fact_candidates").fetchone()[0]
    rate = flagged / max(1, total) * 100
    return QCCheck(
        name="hallucination_rate_pct",
        passed=rate <= 3.0,
        value=round(rate, 2),
        threshold=3.0,
        severity="critical",
    )

# 2. Consistency issue count
def _check_consistency_issues(con) -> QCCheck:
    unresolved = con.execute("""
        SELECT COUNT(*) FROM lex_consistency_issues
        WHERE requires_manual_review = TRUE
    """).fetchone()[0]
    return QCCheck(
        name="unresolved_contradictions",
        passed=unresolved <= 10,
        value=unresolved,
        threshold=10,
        severity="warning",
    )

# 3. Entity deduplication quality
def _check_entity_dedup(con) -> QCCheck:
    """Flag if many entities have single mentions (potential duplicates)."""
    single_mention = con.execute("""
        SELECT COUNT(*) FROM lex_entities WHERE mention_count = 1
    """).fetchone()[0]
    total = con.execute("SELECT COUNT(*) FROM lex_entities").fetchone()[0]
    single_pct = single_mention / max(1, total) * 100
    return QCCheck(
        name="single_mention_entity_pct",
        passed=single_pct <= 40.0,
        value=round(single_pct, 1),
        threshold=40.0,
        severity="warning",
    )

# 4. Amendment detection coverage
def _check_amendment_coverage(con) -> QCCheck:
    """For amendment laws, check if structured amendments were extracted."""
    amendment_docs = con.execute("""
        SELECT COUNT(DISTINCT doc_id) FROM lex_doc_versions
        WHERE doc_type LIKE '%зміни%' OR doc_type LIKE '%внесення%'
    """).fetchone()[0]
    with_amendments = con.execute("""
        SELECT COUNT(DISTINCT amending_doc_id) FROM lex_amendments
    """).fetchone()[0]
    coverage = with_amendments / max(1, amendment_docs) * 100
    return QCCheck(
        name="amendment_extraction_coverage_pct",
        passed=coverage >= 60.0,
        value=round(coverage, 1),
        threshold=60.0,
        severity="warning",
    )

# 5. Fused confidence distribution
def _check_confidence_distribution(con) -> QCCheck:
    """Verify normative facts have reasonable fused confidence."""
    low_conf = con.execute("""
        SELECT COUNT(*) FROM lex_normative_facts
        WHERE fused_confidence < 0.5
    """).fetchone()[0]
    total = con.execute("SELECT COUNT(*) FROM lex_normative_facts").fetchone()[0]
    low_pct = low_conf / max(1, total) * 100
    return QCCheck(
        name="low_confidence_normative_facts_pct",
        passed=low_pct <= 15.0,
        value=round(low_pct, 1),
        threshold=15.0,
        severity="warning",
    )

# 6. Causal mechanism extraction rate
def _check_causal_mechanism_rate(con) -> QCCheck:
    """For threshold-bearing norms, check if causal mechanisms were extracted."""
    threshold_norms = con.execute("""
        SELECT COUNT(*) FROM lex_normative_facts
        WHERE thresholds_json IS NOT NULL AND thresholds_json != '[]'
    """).fetchone()[0]
    with_mechanism = con.execute("""
        SELECT COUNT(*) FROM lex_causal_mechanisms
    """).fetchone()[0]
    rate = with_mechanism / max(1, threshold_norms) * 100
    return QCCheck(
        name="causal_mechanism_rate_pct",
        passed=rate >= 50.0,
        value=round(rate, 1),
        threshold=50.0,
        severity="info",
    )
```

### 9.2 Pipeline telemetry

```python
@dataclass
class LexPipelineTelemetry:
    # Stage timings
    parse_duration_s: float
    structure_duration_s: float
    deterministic_spo_duration_s: float
    llm_extraction_duration_s: float
    grounding_duration_s: float
    reference_extraction_duration_s: float
    graph_build_duration_s: float
    embedding_duration_s: float
    total_duration_s: float

    # Volume metrics
    docs_processed: int
    provisions_extracted: int
    facts_total: int
    facts_grounded: int
    facts_normative: int
    facts_high_confidence: int
    entities_total: int
    entities_deduplicated: int
    references_total: int
    references_resolved: int
    amendments_detected: int
    consistency_issues_found: int
    causal_mechanisms_extracted: int

    # LLM metrics
    llm_requests_total: int
    llm_requests_cached: int
    llm_tokens_prompt: int
    llm_tokens_completion: int
    llm_cost_usd: float
    llm_gate_savings_pct: float
    llm_hallucination_rate_pct: float

    # Quality
    fused_confidence_mean: float
    fused_confidence_median: float
    reference_resolution_rate: float
    grounding_rate: float
```

Write to `telemetry.json` per run. Compare across runs for regression detection.

### 9.3 Benchmark gold suite expansion

**File**: `batch/benchmark.py`

Add benchmark cases targeting new capabilities:

```python
BENCHMARK_SUITE_V2 = {
    # Existing: SPO extraction accuracy
    "spo_extraction": {...},

    # New: Entity disambiguation
    "entity_dedup": {
        "cases": [
            {"input": ["Ministry of Finance", "Мінфін", "МФУ"], "expected_entity_id": "single"},
            {"input": ["Verkhovna Rada", "ВРУ", "парламент"], "expected_entity_id": "single"},
        ],
        "metric": "dedup_accuracy",
        "threshold": 0.90,
    },

    # New: Reference resolution
    "reference_resolution": {
        "cases": [...],  # Known reference → target pairs
        "metric": "resolution_accuracy",
        "threshold": 0.85,
    },

    # New: Contradiction detection
    "contradiction_detection": {
        "cases": [...],  # Known contradictory provision pairs
        "metric": "precision_at_k",
        "threshold": 0.80,
    },

    # New: Amendment extraction
    "amendment_extraction": {
        "cases": [...],  # Known amendment laws → structured changes
        "metric": "amendment_recall",
        "threshold": 0.70,
    },
}
```

---

## Verification Criteria

### Gate 1 — Confidence Fusion (after Phase 1)
- [ ] Fused confidence computed for all facts (unit test)
- [ ] Geometric mean: low grounding × high extraction → medium fused (unit test)
- [ ] 4th tier `high_confidence_norm` populated with fused_confidence ≥ 0.85
- [ ] Confidence breakdown stored in JSON column
- [ ] Tier promotion logic uses fused_confidence, not separate scores

### Gate 2 — Entity Disambiguation (after Phase 2)
- [ ] "Мінфін" and "Ministry of Finance" resolve to same entity (unit test)
- [ ] 200+ curated entity seeds loaded at startup
- [ ] Embedding-based fuzzy matching catches paraphrases (unit test)
- [ ] Entity alias list updated during resolution (integration test)
- [ ] Single-mention entity percentage ≤ 40%

### Gate 3 — Reference Resolution (after Phase 3)
- [ ] Two-stage resolution: deterministic → contextual (unit test)
- [ ] Reference chain traversal up to depth 3 (unit test)
- [ ] Resolution rate ≥ 90% (up from ~80%)
- [ ] Resolution audit log populated with alternatives
- [ ] Ambiguous references (multiple candidates) flagged

### Gate 4 — Hallucination Detection (after Phase 4)
- [ ] Phantom article references detected (unit test)
- [ ] Ungrounded subjects detected (unit test)
- [ ] Phantom numbers detected (unit test)
- [ ] Norm type mismatch detected (unit test)
- [ ] Hallucination rate ≤ 3% for normative_facts
- [ ] Facts with hallucination flags blocked from normative tier

### Gate 5 — Logical Consistency (after Phase 5)
- [ ] Intra-document contradictions detected (unit test)
- [ ] Cross-document contradictions detected (SQL integration test)
- [ ] Lex posterior / lex superior resolution applied (unit test)
- [ ] `lex_consistency_issues` table populated
- [ ] Unresolved contradictions ≤ 10

### Gate 6 — Amendment Graph (after Phase 6)
- [ ] Amendment patterns extracted from amendment laws (unit test)
- [ ] `lex_amendments` table populated with structured diffs
- [ ] Temporal constraints parsed for 4+ constraint types (unit test)
- [ ] Amendment graph enables "history of Article X" queries
- [ ] Amendment detection coverage ≥ 60%

### Gate 7 — Cross-Jurisdiction (after Phase 7)
- [ ] UA jurisdiction extracted into plugin (no behavior change)
- [ ] EU jurisdiction plugin parses "Article X", "shall/shall not" (unit test)
- [ ] JurisdictionPlugin protocol enforced (type test)
- [ ] Pipeline accepts `jurisdiction` parameter and routes to plugin

### Gate 8 — Causal Integration (after Phase 8)
- [ ] Threshold-bearing norms mapped to intervention variables (unit test)
- [ ] Intervention types classified correctly (unit test)
- [ ] `lex_causal_mechanisms` table populated
- [ ] Scientist workflow can query legal constraints (integration test)
- [ ] Causal mechanism rate ≥ 50% for threshold norms

### Gate 9 — QC & Observability (after Phase 9)
- [ ] All 6 new QC checks integrated and passing
- [ ] Pipeline telemetry written per run
- [ ] Benchmark v2 suite passes all threshold
- [ ] No regression in existing tests (20+ test files)

### Final Gate — 10/10 Criteria
- [ ] All 9 phase gates pass
- [ ] All existing test files continue to pass
- [ ] 25+ new tests added and passing
- [ ] Full pipeline run on ЄДРНПА corpus completes
- [ ] Fused confidence model calibrated against gold set
- [ ] Entity dedup reduces unique entities by ≥ 15%
- [ ] Reference resolution rate ≥ 90%
- [ ] Hallucination rate ≤ 3%
- [ ] Contradiction detection finds known issues
- [ ] Amendment graph covers ≥ 60% of amendment laws
- [ ] EU jurisdiction plugin parses sample EUR-Lex documents
- [ ] Causal mechanisms extracted for ≥ 50% of threshold norms
- [ ] Pipeline telemetry tracked across 2+ runs
