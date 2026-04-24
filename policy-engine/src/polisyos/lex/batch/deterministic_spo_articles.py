"""Family-specific deterministic SPO extractors."""

from __future__ import annotations

from polisyos.lex.batch import deterministic_spo as _base

_BASE_EXPORTS = {
    "re",
    "canonicalize_action",
    "canonicalize_norm_type",
    "extract_thresholds_from_text",
}
for _name in dir(_base):
    if _name.startswith("_") or _name in _BASE_EXPORTS:
        globals().setdefault(_name, getattr(_base, _name))
del _name


def _extract_structured_article_candidates(
    *,
    text: str,
    citation_label: str,
    doc_title: str,
) -> tuple[list[SPOCandidate], list[str]]:
    if not _is_basic_article_context(doc_title=doc_title, citation_label=citation_label):
        return [], []

    is_constitutional_doc = bool(_CONSTITUTIONAL_TITLE_RE.search(doc_title or ""))
    candidates: list[SPOCandidate] = []
    reason_codes: list[str] = []

    for sentence in _iter_sentences(text):
        sentence = sentence.strip()
        if len(sentence) < 12:
            continue
        quote = _clip_text(sentence, size=320)

        right_match = _RIGHT_RE.match(sentence)
        if right_match:
            subject_uk = _clip_text(right_match.group("subject").strip(" ,;:"), 120)
            object_uk = _clip_text(f"має право {right_match.group('object').strip(' .;:')}", 220)
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk or "суб'єкт правовідносин",
                    predicate="grants",
                    object_uk=object_uk,
                    norm_type="permission",
                    fact_text=f"{subject_uk or 'субʼєкт'} має право {right_match.group('object').strip(' .;:')}",
                    quote=quote,
                    confidence=0.89 if is_constitutional_doc else 0.84,
                )
            )
            reason_codes.append("article_right_pattern")

        rights_list_match = _RIGHTS_LIST_RE.match(sentence)
        if rights_list_match and sentence.count(";") >= 2:
            subject_uk = _clip_text(rights_list_match.group("subject").strip(" ,;:"), 140)
            for item in _iter_list_items(rights_list_match.group("object")):
                object_uk = _clip_text(f"має право {item.strip(' .;:')}", 220)
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "суб'єкт правовідносин",
                        predicate="grants",
                        object_uk=object_uk,
                        norm_type="permission",
                        fact_text=f"{subject_uk or 'субʼєкт'} має право {item.strip(' .;:')}",
                        quote=quote,
                        confidence=0.83,
                    )
                )
            reason_codes.append("article_rights_list_pattern")

        guarantee_match = _GUARANTEE_RE.match(sentence)
        if guarantee_match:
            prefix = (guarantee_match.group("subject") or "").strip(" ,;:")
            object_uk = _clip_text(guarantee_match.group("object").strip(" .;:"), 220)
            subject_uk = prefix or ("держава" if is_constitutional_doc else "цей акт")
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk,
                    predicate="grants",
                    object_uk=object_uk,
                    norm_type="permission",
                    fact_text=f"Гарантується {object_uk}",
                    quote=quote,
                    confidence=0.88 if is_constitutional_doc else 0.83,
                )
            )
            reason_codes.append("article_guarantee_pattern")

        defined_by_law_match = _DEFINED_BY_LAW_RE.match(sentence)
        if defined_by_law_match:
            raw_object = defined_by_law_match.group("object").strip(" ,;:")
            object_uk = _clip_text(raw_object, 200)
            if is_constitutional_doc or _is_compact_clause(
                subject=raw_object,
                object_text="законом",
                sentence=sentence,
            ):
                candidates.append(
                    _build_candidate(
                        subject_uk=object_uk,
                        predicate="defines",
                        object_uk="законом",
                        norm_type="definition",
                        fact_text=f"{object_uk} визначаються законом",
                        quote=quote,
                        confidence=0.87 if is_constitutional_doc else 0.79,
                    )
                )
                reason_codes.append("article_defined_by_law_pattern")

        dash_definition_match = _DASH_DEFINITION_RE.match(sentence)
        if dash_definition_match:
            raw_subject = dash_definition_match.group("subject").strip(" ,;:")
            raw_object = dash_definition_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 140)
            object_uk = _clip_text(raw_object, 180)
            if _is_compact_clause(subject=raw_subject, object_text=raw_object, sentence=sentence):
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="defines",
                        object_uk=object_uk,
                        norm_type="definition",
                        fact_text=f"{subject_uk} - {object_uk}",
                        quote=quote,
                        confidence=0.87 if is_constitutional_doc else 0.85,
                    )
                )
                reason_codes.append("article_dash_definition_pattern")

        dash_this_is_match = _DASH_THIS_IS_RE.match(sentence)
        if dash_this_is_match:
            raw_subject = dash_this_is_match.group("subject").strip(" ,;:")
            raw_object = dash_this_is_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 160)
            object_uk = _clip_text(raw_object, 220)
            if subject_uk and object_uk:
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="defines",
                        object_uk=object_uk,
                        norm_type="definition",
                        fact_text=f"{subject_uk} - це {object_uk}",
                        quote=quote,
                        confidence=0.86 if is_constitutional_doc else 0.81,
                    )
                )
                reason_codes.append("article_dash_this_is_pattern")

        list_definition_match = _LIST_DEFINITION_RE.search(sentence)
        if list_definition_match and (sentence.count(";") >= 2 or sentence.count("\n") >= 2):
            raw_subject = list_definition_match.group("subject").strip(" ,;:")
            subject_uk = _clip_text(raw_subject, 160)
            if subject_uk:
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="defines",
                        object_uk="перелік визначених елементів",
                        norm_type="definition",
                        fact_text=f"{subject_uk} визначаються переліком у статті",
                        quote=quote,
                        confidence=0.78,
                    )
                )
                reason_codes.append("article_list_definition_pattern")

        principles_list_match = _PRINCIPLES_LIST_RE.search(sentence)
        if principles_list_match and sentence.count(";") >= 2:
            subject_uk = _clip_text(principles_list_match.group("subject").strip(" ,;:"), 160)
            for item in _iter_list_items(principles_list_match.group("object")):
                item_text = _clip_text(item.strip(" .;:"), 220)
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "цей акт",
                        predicate="applies_to",
                        object_uk=item_text,
                        norm_type="procedure",
                        fact_text=f"{subject_uk or 'цей акт'} застосовується за принципом {item_text}",
                        quote=quote,
                        confidence=0.8,
                    )
                )
            reason_codes.append("article_principles_list_pattern")

        amend_wording_match = _AMEND_WORDING_RE.search(sentence)
        if amend_wording_match:
            object_uk = _clip_text(amend_wording_match.group("object").strip(" .;:"), 220)
            candidates.append(
                _build_candidate(
                    subject_uk="орган, що прийняв акт",
                    predicate="amends",
                    object_uk=object_uk or "словесне формулювання норми",
                    norm_type="amendment",
                    fact_text=f"Внесено словесну зміну: {object_uk or 'словесне формулювання норми'}",
                    quote=quote,
                    confidence=0.84,
                )
            )
            reason_codes.append("article_amend_wording_pattern")

        recognized_match = _RECOGNIZED_AS_RE.match(sentence)
        if recognized_match:
            raw_subject = recognized_match.group("subject").strip(" ,;:")
            raw_object = recognized_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 160)
            object_uk = _clip_text(raw_object, 220)
            if _is_compact_clause(subject=raw_subject, object_text=raw_object, sentence=sentence):
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="defines",
                        object_uk=object_uk,
                        norm_type="definition",
                        fact_text=f"{subject_uk} визнаються {object_uk}",
                        quote=quote,
                        confidence=0.86 if is_constitutional_doc else 0.78,
                    )
                )
                reason_codes.append("article_recognition_pattern")

        exists_match = _EXISTS_RE.match(sentence)
        if exists_match and not _DEONTIC_MARKER_RE.search(sentence):
            scope = (exists_match.group("scope") or "в Україні").strip(" ,;:")
            raw_object = exists_match.group("object").strip(" .;:")
            object_uk = _clip_text(raw_object, 220)
            if _is_compact_clause(subject=scope, object_text=raw_object, sentence=sentence):
                candidates.append(
                    _build_candidate(
                        subject_uk=scope,
                        predicate="defines",
                        object_uk=object_uk,
                        norm_type="definition",
                        fact_text=f"{scope} існує {object_uk}",
                        quote=quote,
                        confidence=0.86 if is_constitutional_doc else 0.77,
                    )
                )
                reason_codes.append("article_existence_pattern")

        declarative_match = _DECLARATIVE_IS_RE.match(sentence)
        if declarative_match and not _DEONTIC_MARKER_RE.search(sentence):
            raw_subject = declarative_match.group("subject").strip(" ,;:")
            raw_object = declarative_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 160)
            object_uk = _clip_text(raw_object, 220)
            if (
                subject_uk
                and object_uk
                and _is_compact_clause(
                    subject=raw_subject,
                    object_text=raw_object,
                    sentence=sentence,
                )
            ):
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="defines",
                        object_uk=object_uk,
                        norm_type="definition",
                        fact_text=f"{subject_uk} є {object_uk}",
                        quote=quote,
                        confidence=0.86 if is_constitutional_doc else 0.76,
                    )
                )
                reason_codes.append("article_declarative_pattern")

        for clause in _iter_semantic_clauses(sentence):
            clause_quote = _clip_text(clause, size=320)
            mandatory_execution_match = _MANDATORY_EXECUTION_RE.search(clause)
            if mandatory_execution_match:
                raw_subject = mandatory_execution_match.group("subject").strip(" ,;:")
                raw_object = mandatory_execution_match.group("object").strip(" .;:")
                subject_uk = _clip_text(raw_subject, 180)
                object_uk = _clip_text(raw_object, 220)
                if subject_uk and object_uk:
                    candidates.append(
                        _build_candidate(
                            subject_uk=subject_uk,
                            predicate="requires",
                            object_uk=object_uk,
                            norm_type="obligation",
                            fact_text=f"{subject_uk} є обов'язковими для виконання {raw_object}",
                            quote=clause_quote,
                            confidence=0.84 if is_constitutional_doc else 0.8,
                        )
                    )
                    reason_codes.append("article_mandatory_execution_pattern")

            require_match = _SUBJECT_REQUIRE_RE.search(clause)
            if require_match:
                raw_subject = require_match.group("subject").strip(" ,;:")
                raw_object = require_match.group("object").strip(" .;:")
                subject_uk = _clip_text(raw_subject, 160)
                object_uk = _clip_text(raw_object, 220)
                if subject_uk and object_uk:
                    candidates.append(
                        _build_candidate(
                            subject_uk=subject_uk,
                            predicate="requires",
                            object_uk=object_uk,
                            norm_type="obligation",
                            fact_text=f"{subject_uk} {require_match.group('lemma').strip()} {raw_object}",
                            quote=clause_quote,
                            confidence=0.84 if is_constitutional_doc else 0.8,
                        )
                    )
                    reason_codes.append("article_subject_requirement_pattern")

            prohibit_match = _SUBJECT_PROHIBIT_RE.search(clause)
            if prohibit_match:
                raw_subject = prohibit_match.group("subject").strip(" ,;:")
                raw_object = prohibit_match.group("object").strip(" .;:")
                subject_uk = _clip_text(raw_subject, 160)
                object_uk = _clip_text(raw_object, 220)
                if subject_uk and object_uk:
                    candidates.append(
                        _build_candidate(
                            subject_uk=subject_uk,
                            predicate="prohibits",
                            object_uk=object_uk,
                            norm_type="prohibition",
                            fact_text=f"{subject_uk} {prohibit_match.group('lemma').strip()} {raw_object}",
                            quote=clause_quote,
                            confidence=0.84 if is_constitutional_doc else 0.8,
                        )
                    )
                    reason_codes.append("article_subject_prohibition_pattern")

            permission_match = _SUBJECT_PERMISSION_RE.search(clause)
            if permission_match:
                raw_subject = permission_match.group("subject").strip(" ,;:")
                raw_object = permission_match.group("object").strip(" .;:")
                subject_uk = _clip_text(raw_subject, 160)
                object_uk = _clip_text(raw_object, 220)
                lemma = permission_match.group("lemma").lower()
                if subject_uk and object_uk:
                    candidates.append(
                        _build_candidate(
                            subject_uk=subject_uk,
                            predicate="grants",
                            object_uk=(
                                f"має право {object_uk}" if "має право" in lemma else object_uk
                            ),
                            norm_type="permission",
                            fact_text=f"{subject_uk} {permission_match.group('lemma').strip()} {raw_object}",
                            quote=clause_quote,
                            confidence=0.84 if is_constitutional_doc else 0.79,
                        )
                    )
                    reason_codes.append("article_subject_permission_pattern")
                    condition_match = _PERMISSION_CONDITION_RE.search(raw_object)
                    if condition_match:
                        condition_uk = _clip_text(
                            condition_match.group("condition").strip(" .;:"), 220
                        )
                        candidates.append(
                            _build_candidate(
                                subject_uk=subject_uk,
                                predicate="applies_to",
                                object_uk=condition_uk,
                                norm_type="condition",
                                fact_text=f"{subject_uk} застосовується за умови {condition_uk}",
                                quote=clause_quote,
                                confidence=0.77,
                            )
                        )
                        reason_codes.append("article_permission_condition_pattern")

            temporal_match = _TEMPORAL_APPLICABILITY_RE.search(clause)
            if temporal_match:
                raw_subject = temporal_match.group("subject").strip(" ,;:")
                raw_object = temporal_match.group("object").strip(" .;:")
                subject_uk = _clip_text(raw_subject, 160)
                object_uk = _clip_text(raw_object, 220)
                if subject_uk and object_uk:
                    candidates.append(
                        _build_candidate(
                            subject_uk=subject_uk,
                            predicate="applies_to",
                            object_uk=object_uk,
                            norm_type="applicability",
                            fact_text=f"{subject_uk} {temporal_match.group('lemma').strip()} {raw_object}",
                            quote=clause_quote,
                            confidence=0.82 if is_constitutional_doc else 0.78,
                        )
                    )
                    reason_codes.append("article_temporal_applicability_pattern")

            sanction_match = _SANCTION_RE.search(clause)
            if sanction_match:
                raw_subject = sanction_match.group("subject").strip(" ,;:")
                raw_object = sanction_match.group("object").strip(" .;:")
                subject_uk = _clip_text(raw_subject, 160)
                object_uk = _clip_text(raw_object, 220)
                if subject_uk and object_uk:
                    candidates.append(
                        _build_candidate(
                            subject_uk=subject_uk,
                            predicate="sanctions",
                            object_uk=object_uk,
                            norm_type="sanction",
                            fact_text=f"{subject_uk} {sanction_match.group('lemma').strip()} {raw_object}",
                            quote=clause_quote,
                            confidence=0.83 if is_constitutional_doc else 0.79,
                        )
                    )
                    reason_codes.append("article_sanction_pattern")

            exception_match = _EXCEPTION_RE.search(clause)
            if exception_match:
                object_uk = _clip_text(exception_match.group("object").strip(" .;:"), 220)
                if object_uk:
                    candidates.append(
                        _build_candidate(
                            subject_uk="виняток застосування норми",
                            predicate="applies_to",
                            object_uk=object_uk,
                            norm_type="applicability",
                            fact_text=f"Виняток застосовується щодо: {object_uk}",
                            quote=clause_quote,
                            confidence=0.78,
                        )
                    )
                    reason_codes.append("article_exception_pattern")

        competence_match = _COMPETENCE_LIST_RE.search(sentence)
        if competence_match and (sentence.count(";") >= 2 or sentence.count("\n") >= 2):
            subject_uk = _clip_text(competence_match.group("subject").strip(" ,;:"), 180)
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk or "орган управління",
                    predicate="defines",
                    object_uk="перелік компетенцій, визначений у статті",
                    norm_type="definition",
                    fact_text=f"До компетенції {subject_uk or 'органу управління'} належить перелік визначених повноважень",
                    quote=quote,
                    confidence=0.8,
                )
            )
            reason_codes.append("article_competence_list_pattern")

    return candidates, reason_codes


def _extract_treaty_resolution_candidates(
    *,
    text: str,
    citation_label: str,
    doc_title: str,
) -> tuple[list[SPOCandidate], list[str]]:
    del citation_label
    title = doc_title or ""
    treaty_like = bool(_TREATY_TITLE_RE.search(title))
    resolution_like = bool(_RESOLUTION_TITLE_RE.search(title))
    if not treaty_like and not resolution_like:
        return [], []

    candidates: list[SPOCandidate] = []
    reason_codes: list[str] = []
    for sentence in _iter_sentences(text):
        sentence = sentence.strip()
        if len(sentence) < 16:
            continue
        quote = _clip_text(sentence, size=320)

        if treaty_like:
            treaty_match = _TREATY_OBLIGATION_RE.search(sentence)
            if treaty_match:
                subject_uk = _clip_text(treaty_match.group("subject").strip(" ,;:"), 140)
                object_uk = _clip_text(treaty_match.group("object").strip(" .;:"), 220)
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "договірна сторона",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"{subject_uk or 'договірна сторона'} зобов'язується {object_uk}",
                        quote=quote,
                        confidence=0.84,
                    )
                )
                reason_codes.append("treaty_obligation_pattern")

            treaty_uses_match = _TREATY_USES_RE.search(sentence)
            if treaty_uses_match:
                subject_uk = _clip_text(treaty_uses_match.group("subject").strip(" ,;:"), 180)
                object_uk = _clip_text(treaty_uses_match.group("object").strip(" .;:"), 240)
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "договірна сторона",
                        predicate="grants",
                        object_uk=object_uk,
                        norm_type="permission",
                        fact_text=f"{subject_uk or 'договірна сторона'} використовує {object_uk}",
                        quote=quote,
                        confidence=0.8,
                    )
                )
                reason_codes.append("treaty_uses_pattern")

            treaty_defined_match = _TREATY_DEFINED_BY_SIDE_RE.search(sentence)
            if treaty_defined_match:
                subject_uk = _clip_text(treaty_defined_match.group("subject").strip(" ,;:"), 160)
                object_uk = _clip_text(treaty_defined_match.group("object").strip(" .;:"), 240)
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "відповідна сторона",
                        predicate="grants",
                        object_uk=f"визначати {object_uk}",
                        norm_type="permission",
                        fact_text=f"{subject_uk or 'відповідна сторона'} визначає {object_uk}",
                        quote=quote,
                        confidence=0.8,
                    )
                )
                reason_codes.append("treaty_defined_by_side_pattern")

            treaty_temporal_match = _TREATY_TEMPORAL_RE.search(sentence)
            if treaty_temporal_match:
                object_uk = _clip_text(treaty_temporal_match.group(1).strip(" .;:"), 240)
                candidates.append(
                    _build_candidate(
                        subject_uk="цей договірний режим",
                        predicate="enters_into_force",
                        object_uk=object_uk,
                        norm_type="entry_into_force",
                        fact_text=f"Застосовується {object_uk}",
                        quote=quote,
                        confidence=0.79,
                    )
                )
                reason_codes.append("treaty_temporal_pattern")

            cooperation_match = _TREATY_COOPERATION_RE.search(sentence)
            if cooperation_match:
                object_uk = _clip_text(cooperation_match.group("object").strip(" .;:"), 220)
                candidates.append(
                    _build_candidate(
                        subject_uk="договірні сторони",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="procedure",
                        fact_text=f"Співробітництво здійснюється {object_uk}",
                        quote=quote,
                        confidence=0.8,
                    )
                )
                reason_codes.append("treaty_cooperation_pattern")

            future_cooperation_match = _TREATY_FUTURE_COOPERATION_RE.search(sentence)
            if future_cooperation_match:
                subject_uk = _clip_text(
                    future_cooperation_match.group("subject").strip(" ,;:"), 140
                )
                object_uk = _clip_text(
                    f"{future_cooperation_match.group('lemma').strip()} "
                    f"{future_cooperation_match.group('object').strip(' .;:')}",
                    240,
                )
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "договірні сторони",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"{subject_uk or 'договірні сторони'} {object_uk}",
                        quote=quote,
                        confidence=0.84,
                    )
                )
                reason_codes.append("treaty_future_cooperation_pattern")

            treaty_delegate_match = _TREATY_DELEGATION_RE.search(sentence)
            if treaty_delegate_match:
                subject_uk = _clip_text(treaty_delegate_match.group("subject").strip(" ,;:"), 140)
                object_uk = _clip_text(treaty_delegate_match.group("object").strip(" .;:"), 220)
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "договірні сторони",
                        predicate="delegates",
                        object_uk=object_uk,
                        norm_type="delegation",
                        fact_text=f"{subject_uk or 'договірні сторони'} доручають {object_uk}",
                        quote=quote,
                        confidence=0.82,
                    )
                )
                reason_codes.append("treaty_delegation_pattern")

        ratification_match = _RATIFICATION_RE.search(sentence)
        if ratification_match:
            object_uk = _clip_text(ratification_match.group("object").strip(" .;:"), 220)
            candidates.append(
                _build_candidate(
                    subject_uk="орган, що прийняв акт",
                    predicate="approves",
                    object_uk=object_uk,
                    norm_type="procedure",
                    fact_text=f"Схвалено/затверджено: {object_uk}",
                    quote=quote,
                    confidence=0.83,
                )
            )
            reason_codes.append("ratification_pattern")

        if resolution_like:
            mandate_match = _IMPLEMENTATION_MANDATE_RE.search(sentence)
            if mandate_match:
                subject_uk = _clip_text(mandate_match.group("subject").strip(" ,;:"), 140)
                object_uk = _clip_text(mandate_match.group("object").strip(" .;:"), 220)
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "адресат акта",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"{subject_uk or 'адресат акта'} забезпечує {object_uk}",
                        quote=quote,
                        confidence=0.8,
                    )
                )
                reason_codes.append("resolution_mandate_pattern")

            imperative_mandate_match = _IMPERATIVE_MANDATE_RE.search(sentence)
            if imperative_mandate_match:
                subject_uk = _clip_text(
                    imperative_mandate_match.group("subject").strip(" ,;:"), 160
                )
                object_uk = _clip_text(
                    f"{imperative_mandate_match.group('lemma').strip()} "
                    f"{imperative_mandate_match.group('object').strip(' .;:')}",
                    220,
                )
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "адресат акта",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"{subject_uk or 'адресат акта'} {object_uk}",
                        quote=quote,
                        confidence=0.81,
                    )
                )
                reason_codes.append("resolution_imperative_mandate_pattern")

    return candidates, reason_codes
