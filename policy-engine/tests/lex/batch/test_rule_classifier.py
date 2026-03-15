from __future__ import annotations

from polisyos.lex.batch.rule_classifier import classify_provision


def test_rule_classifier_auto_approves_appendix_bundle_item() -> None:
    result = classify_provision(
        "2. Положення про порядок підтримки ліквідності банківської системи (додаток N 2).",
        "Пункт переліку 2",
        "Про затвердження Положення про порядок підтримки ліквідності",
    )
    assert result.action == "auto"
    assert result.auto_statements[0]["predicate"] == "approves"


def test_rule_classifier_auto_amends_appendix_bundle_item() -> None:
    result = classify_provision(
        "4. Зміни та доповнення до чинних нормативних актів Національного банку України (додаток N 4).",
        "Пункт переліку 4",
        "Про внесення змін та доповнень до чинних нормативних актів",
    )
    assert result.action == "auto"
    assert result.auto_statements[0]["predicate"] == "amends"


def test_rule_classifier_auto_requires_imperative_item() -> None:
    result = classify_provision(
        "2. Надіслати на нашу адресу копії документів, які підтверджують отримання продукції.",
        "Додаток N, пункт 2",
        "Інструкція про порядок використання можливостей НЦБ Інтерполу",
    )
    assert result.action == "auto"
    assert result.auto_statements[0]["predicate"] == "requires"


def test_rule_classifier_auto_extracts_table_threshold_row() -> None:
    result = classify_provision(
        "Ректор                              *        300",
        "Додаток N, рядок таблиці 1",
        "СХЕМА посадових окладів",
    )
    assert result.action == "auto"
    assert result.auto_statements[0]["predicate"] == "sets_threshold"


def test_rule_classifier_skips_composition_member_row() -> None:
    result = classify_provision(
        "- заступник Міністра енергетики та електрифікації БОРИСОВ Микола Андрійович",
        "Додаток 1, пункт 1",
        "Склад міжвідомчої робочої групи",
    )
    assert result.action == "skip"
    assert result.skip_reason == "composition_member"


def test_rule_classifier_skips_blank_form_field() -> None:
    result = classify_provision(
        "1. ____________________________ (найменування підприємства, адреса)",
        "Додаток N, пункт 1",
        "Правила обов'язкової сертифікації",
    )
    assert result.action == "skip"
    assert result.skip_reason == "blank_form_field"


def test_rule_classifier_skips_table_scaffold_row() -> None:
    result = classify_provision(
        "*        *не число (відношення *кінцевої передачі    *передаваль-*",
        "Додаток N, рядок таблиці 2",
        "Форма сертифікації",
    )
    assert result.action == "skip"
    assert result.skip_reason == "table_scaffold"
