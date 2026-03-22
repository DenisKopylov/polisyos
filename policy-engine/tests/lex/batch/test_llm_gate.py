from __future__ import annotations

import re

from polisyos.lex.batch.jurisdictions.protocol import NormativeSignalPatterns, StructurePatterns
from polisyos.lex.batch.llm_gate import (
    GateRuntime,
    build_gate_features,
    decide_route,
)


class _EnglishPlugin:
    @property
    def jurisdiction_code(self) -> str:
        return "EN"

    @property
    def language_codes(self) -> list[str]:
        return ["en"]

    def structure_patterns(self) -> StructurePatterns:
        return StructurePatterns(
            article_re=re.compile(r"^Article\s+\d+", re.IGNORECASE),
            part_re=None,
            point_res=(),
            subpoint_re=None,
            paragraph_re=None,
            section_heading_re=None,
        )

    def normative_signal_patterns(self) -> NormativeSignalPatterns:
        return NormativeSignalPatterns(
            obligation_re=re.compile(r"\bshall\b|\bmust\b", re.IGNORECASE),
            prohibition_re=re.compile(r"\bshall not\b|\bmust not\b", re.IGNORECASE),
            permission_re=re.compile(r"\bmay\b", re.IGNORECASE),
            approval_re=re.compile(r"\bapprove\b|\badopt\b", re.IGNORECASE),
            amendment_re=re.compile(r"\bamend\b|\breplace\b", re.IGNORECASE),
            temporal_re=re.compile(r"\benters into force\b|\bwithin \d+ days\b", re.IGNORECASE),
            reference_re=re.compile(r"\barticle\s+\d+\b|\bregulation\s+\d+\b", re.IGNORECASE),
            threshold_re=re.compile(r"\b\d+(?:[.,]\d+)?\s*%\b", re.IGNORECASE),
        )

    def reference_patterns(self) -> tuple[tuple[str, re.Pattern[str], float], ...]:
        return ()

    def document_type_hierarchy(self) -> dict[str, int]:
        return {"Act": 1}


def test_gate_routes_auto_on_high_deterministic_confidence() -> None:
    runtime = GateRuntime(
        threshold=0.55,
        mode="balanced",
        max_share=0.35,
        audit_max_miss_rate_pct=3.0,
    )
    features = build_gate_features(
        text="Коротка норма без неоднозначності.",
        deterministic_confidence=0.95,
        reference_count=0,
        fallback_chunk=False,
    )
    decision = decide_route(
        gate_enabled=True,
        runtime=runtime,
        llm_available=True,
        llm_share=0.0,
        gap_fill_enabled=False,
        gap_fill_eligible=False,
        gap_fill_share=0.0,
        gap_fill_max_share=0.0,
        deterministic_confidence=0.95,
        auto_conf_threshold=0.85,
        min_score_force_llm=0.75,
        features=features,
        audit_sample_rate=0.0,
        audit_seed="doc:1",
    )
    assert decision.route == "auto"


def test_gate_respects_budget_cap() -> None:
    runtime = GateRuntime(
        threshold=0.55,
        mode="balanced",
        max_share=0.1,
        audit_max_miss_rate_pct=3.0,
    )
    features = build_gate_features(
        text="Складна норма з цифрами 20% і численними посиланнями.",
        deterministic_confidence=0.2,
        reference_count=4,
        fallback_chunk=True,
    )
    decision = decide_route(
        gate_enabled=True,
        runtime=runtime,
        llm_available=True,
        llm_share=0.5,
        gap_fill_enabled=False,
        gap_fill_eligible=False,
        gap_fill_share=0.0,
        gap_fill_max_share=0.0,
        deterministic_confidence=0.2,
        auto_conf_threshold=0.85,
        min_score_force_llm=0.75,
        features=features,
        audit_sample_rate=0.0,
        audit_seed="doc:2",
    )
    assert decision.route == "deferred"
    assert "budget_cap" in decision.reason_codes


def test_gate_circuit_breaker_triggers_after_two_failures() -> None:
    runtime = GateRuntime(
        threshold=0.55,
        mode="balanced",
        max_share=0.35,
        audit_max_miss_rate_pct=3.0,
        circuit_breaker_enabled=True,
    )
    assert runtime.register_audit_miss_rate(5.0) is False
    assert runtime.register_audit_miss_rate(6.0) is True
    assert runtime.safe_pass_active is True
    assert runtime.circuit_breaker_hits == 1


def test_gate_prioritizes_treaty_article_with_legal_signal() -> None:
    runtime = GateRuntime(
        threshold=0.55,
        mode="balanced",
        max_share=0.35,
        audit_max_miss_rate_pct=3.0,
    )
    features = build_gate_features(
        text=(
            "Стаття 1 Договірні Сторони будуть здійснювати і розвивати між собою "
            "рівноправні партнерські відносини для виконання цієї Угоди."
        ),
        deterministic_confidence=0.32,
        reference_count=0,
        fallback_chunk=False,
        doc_title="Угода між Урядом України і Урядом Грузії про співробітництво",
        citation_label="Стаття 1",
        struct_kind="article",
        section_role="normative_unit",
    )
    decision = decide_route(
        gate_enabled=True,
        runtime=runtime,
        llm_available=True,
        llm_share=0.0,
        gap_fill_enabled=False,
        gap_fill_eligible=False,
        gap_fill_share=0.0,
        gap_fill_max_share=0.0,
        deterministic_confidence=0.32,
        auto_conf_threshold=0.85,
        min_score_force_llm=0.75,
        features=features,
        audit_sample_rate=0.0,
        audit_seed="doc:treaty:art1",
    )
    assert decision.route == "llm"


def test_gate_prioritizes_approval_appendix_item() -> None:
    runtime = GateRuntime(
        threshold=0.55,
        mode="balanced",
        max_share=0.35,
        audit_max_miss_rate_pct=3.0,
    )
    features = build_gate_features(
        text='2. Положення про порядок підтримки ліквідності банківської системи (додаток N 2).',
        deterministic_confidence=0.18,
        reference_count=0,
        fallback_chunk=False,
        doc_title="Про затвердження Положення про порядок підтримки ліквідності",
        citation_label="Пункт переліку 2",
        struct_kind="enumeration_item",
        section_role="normative_unit",
    )
    decision = decide_route(
        gate_enabled=True,
        runtime=runtime,
        llm_available=True,
        llm_share=0.0,
        gap_fill_enabled=False,
        gap_fill_eligible=False,
        gap_fill_share=0.0,
        gap_fill_max_share=0.0,
        deterministic_confidence=0.18,
        auto_conf_threshold=0.85,
        min_score_force_llm=0.75,
        features=features,
        audit_sample_rate=0.0,
        audit_seed="doc:order:item2",
    )
    assert decision.route == "llm"


def test_gate_keeps_short_appendix_fragment_deferred() -> None:
    runtime = GateRuntime(
        threshold=0.55,
        mode="balanced",
        max_share=0.35,
        audit_max_miss_rate_pct=3.0,
    )
    features = build_gate_features(
        text="    - який не має наукового ступеня *",
        deterministic_confidence=0.12,
        reference_count=0,
        fallback_chunk=False,
        doc_title="Про внесення змін та доповнень до наказу Міністерства освіти України",
        citation_label="Додаток N, пункт 2",
        struct_kind="enumeration_item",
        section_role="normative_unit",
    )
    decision = decide_route(
        gate_enabled=True,
        runtime=runtime,
        llm_available=True,
        llm_share=0.0,
        gap_fill_enabled=False,
        gap_fill_eligible=False,
        gap_fill_share=0.0,
        gap_fill_max_share=0.0,
        deterministic_confidence=0.12,
        auto_conf_threshold=0.85,
        min_score_force_llm=0.75,
        features=features,
        audit_sample_rate=0.0,
        audit_seed="doc:fragment:item2",
    )
    assert decision.route == "deferred"


def test_gate_allows_small_budget_overflow_for_high_value_legal_span() -> None:
    runtime = GateRuntime(
        threshold=0.55,
        mode="balanced",
        max_share=0.10,
        audit_max_miss_rate_pct=3.0,
    )
    features = build_gate_features(
        text='2. Положення про порядок підтримки ліквідності банківської системи (додаток N 2).',
        deterministic_confidence=0.18,
        reference_count=0,
        fallback_chunk=False,
        doc_title="Про затвердження Положення про порядок підтримки ліквідності",
        citation_label="Пункт переліку 2",
        struct_kind="enumeration_item",
        section_role="normative_unit",
    )
    decision = decide_route(
        gate_enabled=True,
        runtime=runtime,
        llm_available=True,
        llm_share=0.16,
        gap_fill_enabled=False,
        gap_fill_eligible=False,
        gap_fill_share=0.0,
        gap_fill_max_share=0.0,
        deterministic_confidence=0.18,
        auto_conf_threshold=0.85,
        min_score_force_llm=0.75,
        features=features,
        audit_sample_rate=0.0,
        audit_seed="doc:budget:item2",
    )
    assert decision.route == "llm"


def test_gate_prioritizes_long_law_article_with_deontic_clause() -> None:
    runtime = GateRuntime(
        threshold=0.55,
        mode="balanced",
        max_share=0.35,
        audit_max_miss_rate_pct=3.0,
    )
    features = build_gate_features(
        text=(
            "Стаття 12. Органи державної влади зобов'язані забезпечити відкритість інформації "
            "та своєчасно надавати відповіді на запити громадян."
        ),
        deterministic_confidence=0.28,
        reference_count=1,
        fallback_chunk=False,
        doc_title="Закон України Про доступ до інформації",
        citation_label="Стаття 12",
        struct_kind="article",
        section_role="normative_unit",
        doc_type_category="law",
    )
    decision = decide_route(
        gate_enabled=True,
        runtime=runtime,
        llm_available=True,
        llm_share=0.0,
        gap_fill_enabled=False,
        gap_fill_eligible=False,
        gap_fill_share=0.0,
        gap_fill_max_share=0.0,
        deterministic_confidence=0.28,
        auto_conf_threshold=0.85,
        min_score_force_llm=0.75,
        features=features,
        audit_sample_rate=0.0,
        audit_seed="doc:law:art12",
    )
    assert decision.route == "llm"


def test_gate_keeps_deterministic_only_route_out_of_llm() -> None:
    runtime = GateRuntime(
        threshold=0.55,
        mode="balanced",
        max_share=0.35,
        audit_max_miss_rate_pct=3.0,
    )
    features = build_gate_features(
        text='У статті 4 слова "центральний орган" замінити словами "уповноважений орган".',
        deterministic_confidence=0.22,
        reference_count=1,
        fallback_chunk=False,
        doc_title="Про внесення змін до Порядку",
        citation_label="Пункт 2",
        struct_kind="enumeration_item",
        section_role="table_clause",
        doc_type_category="order",
        legal_unit_subtype="amendment_bundle",
        route_class="deterministic_only",
        audit_miss_prone=True,
        reference_bearing=True,
    )
    decision = decide_route(
        gate_enabled=True,
        runtime=runtime,
        llm_available=True,
        llm_share=0.0,
        gap_fill_enabled=False,
        gap_fill_eligible=False,
        gap_fill_share=0.0,
        gap_fill_max_share=0.0,
        deterministic_confidence=0.22,
        auto_conf_threshold=0.85,
        min_score_force_llm=0.75,
        features=features,
        audit_sample_rate=0.0,
        audit_seed="doc:amendment",
    )
    assert decision.route == "auto"
    assert "deterministic_only_route" in decision.reason_codes


def test_gate_prioritizes_retry_eligible_law_clause() -> None:
    runtime = GateRuntime(
        threshold=0.55,
        mode="balanced",
        max_share=0.35,
        audit_max_miss_rate_pct=3.0,
    )
    features = build_gate_features(
        text="Стаття 12. Органи державної влади зобов'язані забезпечити відкритість інформації та не пізніше 10 днів надати відповідь.",
        deterministic_confidence=0.15,
        reference_count=1,
        fallback_chunk=False,
        doc_title="Закон України Про доступ до інформації",
        citation_label="Стаття 12",
        struct_kind="article",
        section_role="normative_unit",
        doc_type_category="law",
        legal_unit_subtype="core_normative_clause",
        route_class="deterministic_then_llm_retry",
        empty_spo_retry_eligible=True,
        audit_miss_prone=True,
        reference_bearing=True,
    )
    decision = decide_route(
        gate_enabled=True,
        runtime=runtime,
        llm_available=True,
        llm_share=0.0,
        gap_fill_enabled=False,
        gap_fill_eligible=False,
        gap_fill_share=0.0,
        gap_fill_max_share=0.0,
        deterministic_confidence=0.15,
        auto_conf_threshold=0.85,
        min_score_force_llm=0.75,
        features=features,
        audit_sample_rate=0.0,
        audit_seed="doc:law:retry",
    )
    assert decision.route == "llm"


def test_gate_routes_llm_gap_fill_before_auto_for_high_value_tail() -> None:
    runtime = GateRuntime(
        threshold=0.55,
        mode="balanced",
        max_share=0.35,
        audit_max_miss_rate_pct=3.0,
    )
    features = build_gate_features(
        text="Орган видає посвідчення. Порядок їх видачі встановлюється Кабінетом Міністрів України.",
        deterministic_confidence=0.92,
        reference_count=0,
        fallback_chunk=False,
        doc_title="Закон України",
        citation_label="Стаття 1",
        struct_kind="article",
        section_role="normative_unit",
        doc_type_category="law",
        legal_unit_subtype="core_normative_clause",
        route_class="deterministic_then_llm_retry",
    )
    decision = decide_route(
        gate_enabled=True,
        runtime=runtime,
        llm_available=True,
        llm_share=0.0,
        gap_fill_enabled=True,
        gap_fill_eligible=True,
        gap_fill_share=0.0,
        gap_fill_max_share=0.8,
        gap_fill_priority=2,
        deterministic_confidence=0.92,
        auto_conf_threshold=0.85,
        min_score_force_llm=0.75,
        features=features,
        audit_sample_rate=0.0,
        audit_seed="doc:gap-fill",
    )
    assert decision.route == "llm_gap_fill"


def test_build_gate_features_uses_plugin_specific_modality_signals() -> None:
    features = build_gate_features(
        text="Article 7. The authority shall not exceed 5% under Regulation 11.",
        deterministic_confidence=0.2,
        reference_count=1,
        fallback_chunk=False,
        doc_title="Foreign Act",
        citation_label="Article 7",
        struct_kind="article",
        section_role="normative_unit",
        doc_type_category="law",
        jurisdiction_plugin=_EnglishPlugin(),
    )

    assert features.modality_hits > 0
    assert features.legal_signal_hits > 0
    assert features.temporal_hits == 0
    assert features.high_value_legal_span is True
