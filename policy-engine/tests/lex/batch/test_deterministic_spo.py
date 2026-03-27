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


def test_deterministic_spo_extracts_cnc_fallback_requirement_pattern() -> None:
    """Core normative clause fallback should catch obligations without article context."""
    result = extract_deterministic_spo(
        text=(
            "Перевізник зобов'язується безпечно перевезти пасажира до пункту призначення, "
            "а пасажир зобов'язується внести установлену плату за проїзд."
        ),
        citation_label="Пункт 19",
        doc_title="Правила перевезення",
        legal_unit_subtype="core_normative_clause",
        quality_family="appendix_heavy",
    )

    assert result.candidates
    assert any(candidate.predicate == "requires" for candidate in result.candidates)
    assert "cnc_fallback_requirement_pattern" in result.reason_codes


def test_deterministic_spo_extracts_cnc_fallback_prohibition_pattern() -> None:
    """Core normative clause fallback should catch prohibitions without article context."""
    result = extract_deterministic_spo(
        text="Відповідальний працівник не має права допускати до роботи осіб без медичного огляду.",
        citation_label="Пункт 12",
        doc_title="Санітарні правила",
        legal_unit_subtype="core_normative_clause",
        quality_family="appendix_heavy",
    )

    assert result.candidates
    assert any(candidate.predicate == "prohibits" for candidate in result.candidates)
    assert "cnc_fallback_prohibition_pattern" in result.reason_codes


def test_deterministic_spo_extracts_cnc_fallback_passive_procedure_pattern() -> None:
    """Core normative clause fallback should catch passive procedures."""
    result = extract_deterministic_spo(
        text="Контроль якості продукції здійснюється на підставі затверджених стандартів.",
        citation_label="Пункт 8",
        doc_title="Порядок контролю якості",
        legal_unit_subtype="core_normative_clause",
        quality_family="appendix_heavy",
    )

    assert result.candidates
    assert any(candidate.predicate == "applies_to" for candidate in result.candidates)
    assert "cnc_fallback_passive_procedure_pattern" in result.reason_codes


def test_deterministic_spo_extracts_cnc_fallback_dash_definition_pattern() -> None:
    """Core normative clause fallback should catch dash definitions without article context."""
    result = extract_deterministic_spo(
        text="Сертифікат - документ, що засвідчує якість",
        citation_label="Пункт 1.2",
        doc_title="Порядок сертифікації",
        legal_unit_subtype="core_normative_clause",
        quality_family="appendix_heavy",
    )

    assert result.candidates
    assert any(candidate.predicate == "defines" for candidate in result.candidates)
    assert "cnc_fallback_dash_definition_pattern" in result.reason_codes


def test_deterministic_spo_extracts_approval_bundle_context_fallback() -> None:
    """Approval bundle should create candidate from annex/title when no explicit verb."""
    result = extract_deterministic_spo(
        text="ПОЛОЖЕННЯ про порядок ліцензування окремих видів господарської діяльності",
        citation_label="Додаток 1",
        doc_title="Про затвердження Положення",
        legal_unit_subtype="approval_bundle",
        quality_family="appendix_heavy",
    )

    assert result.candidates
    assert any(candidate.predicate == "approves" for candidate in result.candidates)
    assert any(
        "subtype_approval_bundle_context_fallback" in result.reason_codes
        or "subtype_approval_bundle_title_fallback" in result.reason_codes
        for _ in [1]
    )


def test_deterministic_spo_extracts_application_requirement_obligation_fallback() -> None:
    """Application requirement should catch obligation patterns beyond basic applicant verbs."""
    result = extract_deterministic_spo(
        text="Організація повинна забезпечити відповідність продукції встановленим вимогам стандартів.",
        citation_label="Пункт 5",
        doc_title="Умови сертифікації",
        legal_unit_subtype="application_requirement",
        quality_family="appendix_heavy",
    )

    assert result.candidates
    assert any(candidate.predicate == "requires" for candidate in result.candidates)
    assert "subtype_application_requirement_obligation" in result.reason_codes


def test_deterministic_spo_extracts_threshold_text_fallback() -> None:
    """Threshold row should create candidate even for text-only rows without numbers."""
    result = extract_deterministic_spo(
        text="Головний бухгалтер централізованої бухгалтерії",
        citation_label="Рядок 5",
        doc_title="Схема посадових окладів",
        legal_unit_subtype="tariff_threshold_row",
        quality_family="appendix_heavy",
        threshold_bearing=True,
    )

    assert result.candidates
    assert any(candidate.predicate == "sets_threshold" for candidate in result.candidates)
    assert "subtype_threshold_text_fallback" in result.reason_codes


def test_deterministic_spo_extracts_application_requirement_impersonal_multi_statement() -> None:
    result = extract_deterministic_spo(
        text=(
            "Якщо сторони, які подають заяву, вважають, що їх інтересам буде завдано шкоди, "
            "можна подати цю інформацію окремо. Необхідно вказати вид інформації і пояснити, "
            "чому цю інформацію не потрібно розголошувати."
        ),
        citation_label="Пункт 8",
        doc_title="Форма заяви",
        legal_unit_subtype="application_requirement",
        quality_family="appendix_heavy",
    )

    predicates = {candidate.predicate for candidate in result.candidates}
    assert "grants" in predicates
    assert "requires" in predicates
    assert "subtype_application_requirement_permission" in result.reason_codes
    assert "subtype_application_requirement_impersonal" in result.reason_codes


def test_deterministic_spo_extracts_amendment_bundle_multistatement() -> None:
    result = extract_deterministic_spo(
        text=(
            '1.1. У групі рахунків 100 назву рахунку 1002 А "Банкноти та монети" змінити на '
            '"Банкноти та монети в касі відділень банку". '
            '1.2. У групі рахунків 110 увести рахунок 1102 А "Банківські метали у відділенні банку". '
            '1.3. У групі рахунків 152 рахунок 1526 А "Пролонгована заборгованість" виключити.'
        ),
        citation_label="Пункт 1",
        doc_title="Про внесення змін до Плану рахунків",
        legal_unit_subtype="amendment_bundle",
        quality_family="appendix_heavy",
        reference_bearing=True,
    )

    amendment_predicates = [candidate.predicate for candidate in result.candidates]
    assert amendment_predicates.count("amends") >= 2
    assert "repeals" in amendment_predicates
    assert "subtype_amendment_bundle_multistatement" in result.reason_codes


def test_deterministic_spo_extracts_core_normative_threshold_fallback() -> None:
    result = extract_deterministic_spo(
        text="Перший заступник Міністра оборони 170",
        citation_label="Рядок 2",
        doc_title="Схема посадових окладів",
        legal_unit_subtype="core_normative_clause",
        quality_family="appendix_heavy",
        threshold_bearing=True,
    )

    assert result.candidates
    assert any(candidate.predicate == "sets_threshold" for candidate in result.candidates)
    assert "cnc_fallback_threshold_pattern" in result.reason_codes


def test_deterministic_spo_skips_cue_less_core_normative_clause() -> None:
    result = extract_deterministic_spo(
        text="Головний бухгалтер централізованої бухгалтерії",
        citation_label="Рядок 5",
        doc_title="Схема посадових окладів",
        legal_unit_subtype="core_normative_clause",
        quality_family="appendix_heavy",
    )

    assert result.candidates == []
    assert result.reason_codes == ["no_match"]


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


def test_deterministic_spo_residual_clause_pass_extracts_secondary_permission() -> None:
    result = extract_deterministic_spo(
        text=(
            "Орган зобов'язаний надати дозвіл заявникові, а також може вимагати "
            "додаткові відомості у разі потреби."
        ),
        citation_label="Пункт 3",
        doc_title="Порядок надання дозволів",
        legal_unit_subtype="core_normative_clause",
        legal_unit_micro_subtype="main_deontic",
        quality_family="appendix_heavy",
    )

    predicates = {candidate.predicate for candidate in result.candidates}
    assert "requires" in predicates
    assert "grants" in predicates
    assert "residual_clause_pass" in result.reason_codes


def test_deterministic_spo_extracts_application_requirement_from_form_block() -> None:
    result = extract_deterministic_spo(
        text=(
            "Перелік документів\n"
            "Заявник подає копію договору\n"
            "та повідомляє орган про зміну адреси."
        ),
        citation_label="Додаток 1, пункт 4",
        doc_title="Форма заяви",
        legal_unit_subtype="application_requirement",
        quality_family="appendix_heavy",
        context_prefix="До заяви додаються документи",
    )

    facts = [candidate.fact_text for candidate in result.candidates]
    assert result.candidates
    assert any(candidate.predicate == "requires" for candidate in result.candidates)
    assert any("копію договору" in fact or "зміну адреси" in fact for fact in facts)


def test_deterministic_spo_extracts_approval_bundle_multi_fact() -> None:
    result = extract_deterministic_spo(
        text=(
            "Затвердити Порядок ліцензування (додаток 2) та доручити Міністерству фінансів "
            "забезпечити його виконання. Акт набирає чинності з 1 січня 2027 року."
        ),
        citation_label="Пункт 1",
        doc_title="Про затвердження Порядку ліцензування",
        legal_unit_subtype="approval_bundle",
        quality_family="appendix_heavy",
        reference_bearing=True,
    )

    predicates = {candidate.predicate for candidate in result.candidates}
    assert {"approves", "delegates", "enters_into_force"} <= predicates
    assert "applies_to" in predicates


def test_deterministic_spo_inherits_appendix_remove_action_from_context() -> None:
    result = extract_deterministic_spo(
        text="імені 40-річчя Радянської України",
        citation_label="Додаток 1",
        doc_title="Про внесення змін до переліку",
        legal_unit_subtype="amendment_bundle",
        quality_family="appendix_heavy",
        reference_bearing=True,
        context_prefix="I. Виключаються з переліку колгоспи:",
    )

    assert result.candidates
    assert any(candidate.predicate == "amends" for candidate in result.candidates)
    assert "context_remove_list_inheritance" in result.reason_codes


def test_deterministic_spo_extracts_secondary_permission_from_application_tail() -> None:
    result = extract_deterministic_spo(
        text=(
            "Заява про надання дозволу подається на ім'я начальника станції. "
            "Заява може надаватися через начальника станції."
        ),
        citation_label="Пункт 2",
        doc_title="Порядок оформлення заяви",
        legal_unit_subtype="application_requirement",
        quality_family="appendix_heavy",
    )

    predicates = {candidate.predicate for candidate in result.candidates}
    assert "requires" in predicates
    assert "grants" in predicates
    assert {
        "subtype_application_requirement_subject_permission",
        "semantic_tail_permission",
    } & set(result.reason_codes)


def test_deterministic_spo_extracts_treaty_permission_and_temporal_tail() -> None:
    result = extract_deterministic_spo(
        text=(
            "Чорноморський флот Російської Федерації використовує навігаційно-гідрографічне "
            "обладнання на умовах та протягом строку дії Угоди."
        ),
        citation_label="Стаття 1",
        doc_title="Угода між Україною і Російською Федерацією",
        legal_unit_subtype="core_normative_clause",
        quality_family="treaty_protocol",
    )

    predicates = {candidate.predicate for candidate in result.candidates}
    assert "grants" in predicates
    assert "enters_into_force" in predicates
    assert "sets_threshold" not in predicates
    assert "treaty_uses_pattern" in result.reason_codes
    assert "treaty_temporal_pattern" in result.reason_codes


def test_deterministic_spo_extracts_threshold_policy_tail_from_core_clause() -> None:
    result = extract_deterministic_spo(
        text=(
            "Сторона має право вимагати перегляду ставок винагороди. "
            "Мінімальні ставки винагороди та порядок їх індексації можуть установлюватися законом."
        ),
        citation_label="Стаття 15",
        doc_title="Закон України про авторське право",
        legal_unit_subtype="core_normative_clause",
        legal_unit_micro_subtype="threshold_tail",
        quality_family="law",
        threshold_bearing=True,
    )

    assert any(candidate.predicate == "sets_threshold" for candidate in result.candidates)
    assert {
        "semantic_tail_threshold_policy",
        "cnc_fallback_threshold_pattern",
    } & set(result.reason_codes)


def test_deterministic_spo_skips_search_only_front_matter_subtype() -> None:
    result = extract_deterministic_spo(
        text="ЗАРЕЄСТРОВАНО в Міністерстві юстиції України 11.03.1996 р. № 121/1146 НАКАЗУЮ:",
        citation_label="Повний текст",
        doc_title="Наказ Міністерства фінансів України",
        legal_unit_subtype="table_scaffold",
        quality_family="appendix_heavy",
        reference_bearing=True,
        threshold_bearing=True,
    )

    assert result.candidates == []
    assert result.reason_codes == ["search_only_subtype:table_scaffold"]
