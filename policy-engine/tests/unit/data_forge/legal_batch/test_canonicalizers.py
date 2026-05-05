from __future__ import annotations

from polisyos.data_forge.domains.legal.batch.canonicalizers import (
    canonicalize_action,
    canonicalize_norm_type,
    extract_thresholds_from_text,
)


def test_canonicalize_action_maps_known_synonym() -> None:
    canon, oov = canonicalize_action("must_be_revoked_or_reduced")
    assert canon == "revokes"
    assert oov is False


def test_canonicalize_action_marks_oov() -> None:
    canon, oov = canonicalize_action("totally_custom_predicate")
    assert canon == "requires"
    assert oov is True


def test_canonicalize_norm_type_maps_known_synonym() -> None:
    canon, oov = canonicalize_norm_type("must")
    assert canon == "obligation"
    assert oov is False


def test_extract_thresholds_from_text_finds_percent_and_duration() -> None:
    thresholds = extract_thresholds_from_text(
        "Надбавка до 25% посадового окладу за стаж 2 роки",
        applies_to="customs_employee",
    )
    assert len(thresholds) == 2
    assert thresholds[0].metric == "percent"
    assert thresholds[0].unit == "percent"
    assert thresholds[1].metric == "duration"
    assert thresholds[1].unit == "year"
    assert all(t.applies_to == "customs_employee" for t in thresholds)


def test_extract_thresholds_from_text_skips_calendar_year_dates() -> None:
    thresholds = extract_thresholds_from_text(
        "Зареєстровано 12.03.1997 року в Міністерстві юстиції України",
        applies_to="act",
    )

    assert thresholds == []


def test_extract_thresholds_from_text_finds_scalar_limits() -> None:
    thresholds = extract_thresholds_from_text(
        "корисне навантаження не менш як 500 кг на дальність 300 км і більше",
        applies_to="transport_condition",
    )

    metrics = {(t.metric, t.operator, t.value_text, t.unit) for t in thresholds}
    assert ("mass_kg", "gte", "500", "кг") in metrics
    assert ("distance_km", "eq", "300", "км") in metrics


def test_canonicalize_action_maps_verify_label() -> None:
    canon, oov = canonicalize_action("adopt_proposal")
    assert canon == "approves"
    assert oov is False


def test_canonicalize_norm_type_maps_verify_label() -> None:
    canon, oov = canonicalize_norm_type("directive")
    assert canon == "obligation"
    assert oov is False


def test_canonicalize_action_maps_new_verify_tokens() -> None:
    canon, oov = canonicalize_action("enter_into_force")
    assert canon == "enters_into_force"
    assert oov is False


def test_canonicalize_action_maps_cyrillic_token() -> None:
    canon, oov = canonicalize_action("прийняти пропозицію")
    assert canon == "approves"
    assert oov is False


def test_canonicalize_action_maps_new_smoke_tokens() -> None:
    canon, oov = canonicalize_action("declared_inconsistent")
    assert canon == "prohibits"
    assert oov is False

    canon, oov = canonicalize_action("submit proposal")
    assert canon == "requires"
    assert oov is False


def test_canonicalize_norm_type_maps_new_smoke_tokens() -> None:
    canon, oov = canonicalize_norm_type("imperative")
    assert canon == "obligation"
    assert oov is False

    canon, oov = canonicalize_norm_type("presidential_decree")
    assert canon == "procedure"
    assert oov is False

    canon, oov = canonicalize_norm_type("амendment")
    assert canon == "amendment"
    assert oov is False


def test_canonicalize_action_heuristics_cover_unseen_variants() -> None:
    canon, oov = canonicalize_action("approve_internal_plan")
    assert canon == "approves"
    assert oov is False

    canon, oov = canonicalize_action("inconsistent_with_law")
    assert canon == "prohibits"
    assert oov is False

    canon, oov = canonicalize_action("вносить")
    assert canon == "amends"
    assert oov is False

    canon, oov = canonicalize_action("регулює")
    assert canon == "regulates"
    assert oov is False

    canon, oov = canonicalize_action("амендує")
    assert canon == "amends"
    assert oov is False
