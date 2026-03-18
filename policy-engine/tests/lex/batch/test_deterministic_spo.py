from __future__ import annotations

from polisyos.lex.batch.deterministic_spo import extract_deterministic_spo, extract_family_retry_spo


def test_deterministic_spo_extracts_entry_into_force() -> None:
    result = extract_deterministic_spo(
        text="Цей акт набирає чинності з дня офіційного опублікування.",
        citation_label="Стаття 1",
        doc_title="Тестовий закон",
    )
    assert result.candidates
    assert any(candidate.predicate == "enters_into_force" for candidate in result.candidates)
    assert "entry_into_force_pattern" in result.reason_codes
    assert result.confidence > 0.7


def test_deterministic_spo_extracts_thresholds() -> None:
    result = extract_deterministic_spo(
        text="Ставка податку становить 18% для платників податку.",
        citation_label="Стаття 2",
        doc_title="Податковий закон",
    )
    assert result.candidates
    assert any(candidate.predicate == "sets_threshold" for candidate in result.candidates)
    assert any(candidate.thresholds for candidate in result.candidates)


def test_deterministic_spo_extracts_constitutional_declarative_and_defined_by_law_clauses() -> None:
    result = extract_deterministic_spo(
        text="Стаття 4. В Україні існує єдине громадянство. Підстави набуття і припинення громадянства України визначаються законом.",
        citation_label="Стаття 4",
        doc_title="Конституція України",
    )
    predicates = {candidate.predicate for candidate in result.candidates}
    facts = [candidate.fact_text for candidate in result.candidates]

    assert predicates == {"defines"}
    assert any("існує єдине громадянство" in fact for fact in facts)
    assert any("визначаються законом" in fact for fact in facts)
    assert "article_existence_pattern" in result.reason_codes
    assert "article_defined_by_law_pattern" in result.reason_codes
    assert result.confidence >= 0.87


def test_deterministic_spo_extracts_constitutional_rights_and_guarantees() -> None:
    result = extract_deterministic_spo(
        text="Стаття 55. Кожному гарантується право на оскарження в суді рішень органів державної влади. Кожен має право будь-якими не забороненими законом засобами захищати свої права і свободи.",
        citation_label="Стаття 55",
        doc_title="Конституція України",
    )
    predicates = {candidate.predicate for candidate in result.candidates}
    norm_types = {candidate.norm_type_canon for candidate in result.candidates}

    assert predicates == {"grants"}
    assert norm_types == {"permission"}
    assert "article_guarantee_pattern" in result.reason_codes
    assert "article_right_pattern" in result.reason_codes
    assert result.confidence >= 0.87


def test_deterministic_spo_avoids_overmatching_long_non_constitutional_definitions() -> None:
    result = extract_deterministic_spo(
        text=(
            "Стаття 3. Об'єктом оподаткування є прибуток, який визначається шляхом зменшення "
            "суми скоригованого валового доходу звітного періоду, визначеного згідно з пунктом "
            "4.3 цього Закону на суму валових витрат платника податку та амортизаційних відрахувань."
        ),
        citation_label="Стаття 3",
        doc_title="Про внесення змін до Закону України \"Про оподаткування прибутку підприємств\"",
    )
    assert not result.candidates
    assert result.reason_codes == ["no_match"]


def test_deterministic_spo_extracts_compact_dash_definition_in_regular_law_article() -> None:
    result = extract_deterministic_spo(
        text="Стаття 4. Валовий доход - загальна сума доходу платника податку від усіх видів діяльності, отриманого протягом звітного періоду.",
        citation_label="Стаття 4",
        doc_title="Про внесення змін до Закону України \"Про оподаткування прибутку підприємств\"",
    )
    assert result.candidates
    assert result.candidates[0].predicate == "defines"
    assert "article_dash_definition_pattern" in result.reason_codes
    assert result.confidence >= 0.85


def test_deterministic_spo_extracts_treaty_obligation_clause() -> None:
    result = extract_deterministic_spo(
        text="Кожна Договірна Сторона зобов'язується забезпечити обмін інформацією між компетентними органами.",
        citation_label="Стаття 5",
        doc_title="Угода між Урядом України та Урядом Польщі",
    )
    predicates = {candidate.predicate for candidate in result.candidates}

    assert "requires" in predicates
    assert "treaty_obligation_pattern" in result.reason_codes


def test_deterministic_spo_extracts_resolution_mandate_clause() -> None:
    result = extract_deterministic_spo(
        text="Міністерство фінансів забезпечує подання щорічного звіту Кабінетові Міністрів України.",
        citation_label="Пункт 4",
        doc_title="Постанова Кабінету Міністрів України",
    )

    assert result.candidates
    assert any(candidate.predicate == "requires" for candidate in result.candidates)
    assert "resolution_mandate_pattern" in result.reason_codes


def test_deterministic_spo_extracts_resolution_imperative_mandate_clause() -> None:
    result = extract_deterministic_spo(
        text="Емісійно-кредитному департаменту надіслати зазначені нормативні документи обласним управлінням.",
        citation_label="Пункт 6",
        doc_title="Постанова Національного банку України",
    )

    assert result.candidates
    assert any(candidate.predicate == "requires" for candidate in result.candidates)
    assert "resolution_imperative_mandate_pattern" in result.reason_codes


def test_deterministic_spo_extracts_treaty_future_cooperation_clause() -> None:
    result = extract_deterministic_spo(
        text=(
            "Стаття 7. Договірні Сторони будуть здійснювати співробітництво з метою захисту "
            "громадян та державної власності."
        ),
        citation_label="Стаття 7",
        doc_title="Угода між Україною та Республікою Польща",
    )

    assert result.candidates
    assert any(candidate.predicate == "requires" for candidate in result.candidates)
    assert "treaty_future_cooperation_pattern" in result.reason_codes


def test_deterministic_spo_extracts_passive_procedure_clause() -> None:
    result = extract_deterministic_spo(
        text="Роботи проводяться на підставі господарського договору.",
        citation_label="Пункт 11",
        doc_title="Правила обов'язкової сертифікації",
    )

    assert result.candidates
    assert any(candidate.predicate == "applies_to" for candidate in result.candidates)
    assert "passive_procedure_pattern" in result.reason_codes


def test_deterministic_spo_extracts_rights_list_items() -> None:
    result = extract_deterministic_spo(
        text=(
            "Адміністрація має право: запитувати і одержувати матеріали; "
            "користуватися банками даних; використовувати державні системи зв'язку."
        ),
        citation_label="Пункт 6",
        doc_title="Положення про Адміністрацію",
    )

    grants = [candidate for candidate in result.candidates if candidate.predicate == "grants"]
    assert len(grants) >= 3
    assert {"article_rights_list_pattern", "rights_list_pattern"} & set(result.reason_codes)


def test_deterministic_spo_extracts_principles_list_items() -> None:
    result = extract_deterministic_spo(
        text=(
            "Приватизація здійснюється на основі таких принципів: законності; "
            "державного регулювання та контролю; платності відчуження державного майна."
        ),
        citation_label="Стаття 2",
        doc_title="Закон України про приватизацію",
    )

    applies = [candidate for candidate in result.candidates if candidate.predicate == "applies_to"]
    assert len(applies) >= 3
    assert "article_principles_list_pattern" in result.reason_codes


def test_deterministic_spo_extracts_scope_and_order_clauses() -> None:
    result = extract_deterministic_spo(
        text=(
            "Дана Інструкція поширюється на всі установи та підприємства "
            "та встановлює порядок здійснення карантинних заходів."
        ),
        citation_label="Пункт 2.1",
        doc_title="Інструкція з карантину рослин",
    )

    predicates = {candidate.predicate for candidate in result.candidates}
    assert "applies_to" in predicates
    assert "defines" in predicates
    assert "applies_scope_pattern" in result.reason_codes
    assert "establishes_order_pattern" in result.reason_codes


def test_deterministic_spo_extracts_long_law_requirement_and_prohibition_clauses() -> None:
    result = extract_deterministic_spo(
        text=(
            "Стаття 12. Органи державної влади зобов'язані забезпечити відкритість інформації; "
            "посадові особи не мають права обмежувати доступ до публічної інформації."
        ),
        citation_label="Стаття 12",
        doc_title="Закон України Про доступ до публічної інформації",
    )

    predicates = {candidate.predicate for candidate in result.candidates}
    assert "requires" in predicates
    assert "prohibits" in predicates
    assert "article_subject_requirement_pattern" in result.reason_codes
    assert "article_subject_prohibition_pattern" in result.reason_codes


def test_family_retry_spo_extracts_amendment_wording_from_law_list_item() -> None:
    result = extract_family_retry_spo(
        text=(
            '2. У статті 40: у частині першій слова "двох мінімальних розмірів '
            'заробітної плати" замінити словами "двох неоподатковуваних мінімумів доходів громадян".'
        ),
        citation_label="Пункт переліку 2",
        doc_title="Закон України про внесення змін",
        quality_family="law",
        struct_kind="enumeration_item",
    )

    assert result.candidates
    assert any(candidate.predicate == "amends" for candidate in result.candidates)
    assert "retry_clause_split" in result.reason_codes


def test_family_retry_spo_extracts_treaty_commitment_for_protocol_family() -> None:
    result = extract_family_retry_spo(
        text=(
            "Стаття 7. Договірні Сторони будуть здійснювати співробітництво з метою захисту "
            "громадян, державної та іншої власності."
        ),
        citation_label="Стаття 7",
        doc_title="Протокол між Україною та Республікою Польща",
        quality_family="treaty_protocol",
        struct_kind="article",
    )

    assert result.candidates
    assert any(candidate.predicate == "requires" for candidate in result.candidates)
    assert "retry_clause_split" in result.reason_codes


def test_deterministic_spo_extracts_subtype_approval_bundle() -> None:
    result = extract_deterministic_spo(
        text="Затвердити Положення про порядок ліцензування (додаток 2).",
        citation_label="Пункт 1",
        doc_title="Про затвердження Положення про порядок ліцензування",
        legal_unit_subtype="approval_bundle",
        quality_family="appendix_heavy",
        reference_bearing=True,
    )

    assert result.candidates
    assert any(candidate.predicate == "approves" for candidate in result.candidates)
    assert "subtype_approval_bundle" in result.reason_codes


def test_deterministic_spo_extracts_passive_approval_bundle() -> None:
    result = extract_deterministic_spo(
        text=(
            "ЗАТВЕРДЖЕНО розпорядженням Кабінету Міністрів України "
            "ЛІМІТИ лісосічного фонду на 1997 рік"
        ),
        citation_label="Абзац 5",
        doc_title="Розпорядження Кабінету Міністрів України",
        legal_unit_subtype="approval_bundle",
        quality_family="appendix_heavy",
        reference_bearing=True,
    )

    assert result.candidates
    assert any(candidate.predicate == "approves" for candidate in result.candidates)
    assert "subtype_approval_bundle" in result.reason_codes


def test_deterministic_spo_extracts_subtype_threshold_row() -> None:
    result = extract_deterministic_spo(
        text="Ректор   300 грн",
        citation_label="Рядок 1",
        doc_title="Додаток до постанови",
        legal_unit_subtype="tariff_threshold_row",
        quality_family="appendix_heavy",
        threshold_bearing=True,
    )

    assert result.candidates
    assert any(candidate.predicate == "sets_threshold" for candidate in result.candidates)
    assert "subtype_threshold_row" in result.reason_codes


def test_deterministic_spo_extracts_multivalue_threshold_row() -> None:
    result = extract_deterministic_spo(
        text="В Україні - всього    6053,3   3001,6   1275,4   320,4",
        citation_label="Таблиця, рядок 1",
        doc_title="Ліміти лісосічного фонду",
        legal_unit_subtype="tariff_threshold_row",
        quality_family="appendix_heavy",
        threshold_bearing=True,
    )

    assert result.candidates
    assert any(candidate.predicate == "sets_threshold" for candidate in result.candidates)
    assert "subtype_threshold_multivalue_row" in result.reason_codes


def test_deterministic_spo_extracts_unitless_salary_threshold_row() -> None:
    result = extract_deterministic_spo(
        text="Заступники Міністра 330",
        citation_label="Рядок 2",
        doc_title="Про впорядкування умов оплати праці працівників апарату органів виконавчої влади",
        legal_unit_subtype="tariff_threshold_row",
        quality_family="appendix_heavy",
        threshold_bearing=True,
    )

    assert result.candidates
    assert any(candidate.predicate == "sets_threshold" for candidate in result.candidates)
    assert "subtype_threshold_unitless_row" in result.reason_codes


def test_deterministic_spo_extracts_conditional_threshold_row() -> None:
    result = extract_deterministic_spo(
        text="корисне навантаження не менш як 500 кг на дальність 300 км і більше",
        citation_label="Таблиця, рядок 4",
        doc_title="Збірник тарифів",
        legal_unit_subtype="tariff_threshold_row",
        quality_family="appendix_heavy",
        threshold_bearing=True,
    )

    assert result.candidates
    assert any(candidate.predicate == "sets_threshold" for candidate in result.candidates)
    assert "subtype_threshold_condition_row" in result.reason_codes


def test_deterministic_spo_extracts_subtype_application_requirement() -> None:
    result = extract_deterministic_spo(
        text="Заявник подає копію договору та повідомляє орган про зміну адреси.",
        citation_label="Пункт 3",
        doc_title="Форма заяви",
        legal_unit_subtype="application_requirement",
        quality_family="appendix_heavy",
    )

    assert result.candidates
    assert any(candidate.predicate == "requires" for candidate in result.candidates)
    assert "subtype_application_requirement" in result.reason_codes


def test_deterministic_spo_extracts_amendment_wording_item() -> None:
    result = extract_deterministic_spo(
        text='25. У додатках NN 1, 2, 4 слова "карбованці" замінити на слово "гривні".',
        citation_label="Пункт 25",
        doc_title="Про внесення змін",
        legal_unit_subtype="amendment_bundle",
        quality_family="appendix_heavy",
        reference_bearing=True,
    )

    assert result.candidates
    assert any(candidate.predicate == "amends" for candidate in result.candidates)
    assert "subtype_amendment_bundle" in result.reason_codes


def test_deterministic_spo_extracts_application_requirement_bullet() -> None:
    result = extract_deterministic_spo(
        text="- виконувати усі вимоги сертифікації;",
        citation_label="Пункт 4",
        doc_title="Форма заявки",
        legal_unit_subtype="application_requirement",
        quality_family="appendix_heavy",
    )

    assert result.candidates
    assert any(candidate.predicate == "requires" for candidate in result.candidates)
    assert "subtype_application_bullet_requirement" in result.reason_codes


def test_deterministic_spo_extracts_may_permission_and_condition_from_law_article() -> None:
    result = extract_deterministic_spo(
        text=(
            "Стаття 4. Юридичні або фізичні особи можуть займатися підприємницькою "
            "ветеринарною практикою за умови отримання спеціального дозволу."
        ),
        citation_label="Стаття 4",
        doc_title="Закон України про ветеринарну медицину",
        legal_unit_subtype="core_normative_clause",
        quality_family="law",
    )

    predicates = {candidate.predicate for candidate in result.candidates}
    assert "grants" in predicates
    assert "applies_to" in predicates
    assert "article_subject_permission_pattern" in result.reason_codes
    assert "article_permission_condition_pattern" in result.reason_codes


def test_deterministic_spo_extracts_mandatory_execution_clause_from_law_article() -> None:
    result = extract_deterministic_spo(
        text=(
            "Нормативно-правові акти, видані Державним департаментом ветеринарної медицини, "
            "є обов'язковими для виконання всіма державними органами."
        ),
        citation_label="Стаття 2",
        doc_title="Закон України про ветеринарну медицину",
        legal_unit_subtype="core_normative_clause",
        quality_family="law",
    )

    assert result.candidates
    assert any(candidate.predicate == "requires" for candidate in result.candidates)
    assert "article_mandatory_execution_pattern" in result.reason_codes
