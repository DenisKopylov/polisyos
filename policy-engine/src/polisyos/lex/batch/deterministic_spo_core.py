"""Family-specific deterministic SPO extractors."""

from __future__ import annotations

from polisyos.lex.batch import deterministic_spo as _base

_BASE_EXPORTS = {'re', 'canonicalize_action', 'canonicalize_norm_type', 'extract_thresholds_from_text'}
for _name in dir(_base):
    if _name.startswith("_") or _name in _BASE_EXPORTS:
        globals().setdefault(_name, getattr(_base, _name))
del _name

from polisyos.lex.batch.deterministic_spo_subtypes import _extract_threshold_row_candidates_inner

_CORE_NORMATIVE_FAST_CUE_RE = re.compile(
    r"("
    r"повинен|повинна|повинні|зобов|"
    r"має\s+(?:пріоритетне\s+)?право|мають\s+(?:пріоритетне\s+)?право|може|можуть|вправі|"
    r"необхідно|слід|"
    r"не\s+має\s+права|не\s+мають\s+права|"
    r"забороняється|забороняються|заборонено|не\s+допускається|не\s+допускаються|"
    r"підляга(?:є|ють)|поширюється|поширюються|встановлює\s+порядок|"
    r"проводиться|проводяться|здійснюється|здійснюються|"
    r"розраховується|розраховуються|відноситься|відносяться|"
    r"покривається|покриваються|вважається|вважаються|"
    r"визна(?:ється|ються)|визнача(?:ється|ються)|"
    r"карається|штрафується|тягне\s+за\s+собою|"
    r"[-–—]|"
    r"\d+(?:[.,]\d+)?\s*(?:%|грн|коп|кг|км|га|тонн(?:и)?)\b|"
    r"ставк|тариф|оклад|поріг|не\s+менш|не\s+більш|не\s+нижче|не\s+вище"
    r")",
    re.IGNORECASE,
)
_WORD_THRESHOLD_RE = re.compile(
    r"(?P<lemma>не\s+менше|не\s+більше|не\s+нижче|не\s+вище)\s+"
    r"(?P<value>[а-яіїєґ'’`-]{2,24})\s+"
    r"(?P<unit>рок(?:ів|и|у)|дн(?:ів|і|я)|місяц(?:ів|і|я)|тижн(?:ів|і|я)|"
    r"відсотк(?:ів|и|а)|осіб|раз(?:ів|и)?)",
    re.IGNORECASE,
)


def _search_with_optional_context(
    pattern: re.Pattern[str],
    text: str,
    *,
    analysis_text: str | None,
) -> re.Match[str] | None:
    match = pattern.search(text)
    if match is not None or not analysis_text or analysis_text == text:
        return match
    return pattern.search(analysis_text)

def _extract_core_normative_fallback_candidates(
    *,
    text: str,
    doc_title: str,
    legal_unit_micro_subtype: str = "",
    context_prefix: str = "",
    threshold_bearing: bool = False,
) -> tuple[list[SPOCandidate], list[str]]:
    """Broad normative patterns for core_normative_clause without article context.

    These run only for core_normative_clause subtype and catch patterns that the
    article-context extractor misses (because it requires constitutional/code
    title or 'Стаття' citation label).
    """
    candidates: list[SPOCandidate] = []
    reason_codes: list[str] = []
    normalized_context = " ".join(str(context_prefix or "").split()).strip()
    analysis_full_text = _combine_with_context(text, normalized_context) if normalized_context else text
    treaty_like_title = bool(_TREATY_TITLE_RE.search(doc_title or ""))
    if not (
        threshold_bearing
        or legal_unit_micro_subtype in {"threshold_tail", "reference_tail"}
        or _CORE_NORMATIVE_FAST_CUE_RE.search(analysis_full_text)
    ):
        return [], []

    for sentence in _iter_sentences(text, split_newlines=threshold_bearing):
        sentence = sentence.strip()
        if len(sentence) < 16:
            continue
        if not (
            threshold_bearing
            or legal_unit_micro_subtype == "threshold_tail"
            or _CORE_NORMATIVE_FAST_CUE_RE.search(sentence)
        ):
            continue
        quote = _clip_text(sentence, size=320)
        analysis_sentence = _combine_with_context(sentence, normalized_context) if normalized_context else sentence
        strong_threshold_text = (
            bool(re.search(r"\d+(?:[.,]\d+)?\s*(?:%|грн|коп|кг|км|га|тонн(?:и)?)\b", sentence, re.IGNORECASE))
            or any(
                marker in sentence.lower()
                for marker in (
                    "ставк",
                    "тариф",
                    "оклад",
                    "поріг",
                    "не менш",
                    "не більш",
                    "не нижче",
                    "не вище",
                )
            )
        )

        if (
            not (
                treaty_like_title
                and _TREATY_TEMPORAL_RE.search(sentence)
                and not strong_threshold_text
            )
            and (
                (
                    threshold_bearing
                    or strong_threshold_text
                    or legal_unit_micro_subtype == "threshold_tail"
                )
                and extract_thresholds_from_text(analysis_sentence, applies_to=doc_title or "регульований показник")
                or _UNITLESS_THRESHOLD_ROW_RE.search(sentence)
                or _CONDITION_THRESHOLD_RE.search(sentence)
                or legal_unit_micro_subtype == "threshold_tail"
            )
        ):
            threshold_candidates, threshold_reason_codes = _extract_threshold_row_candidates_inner(
                text=sentence,
                doc_title=doc_title,
                context_prefix=context_prefix,
            )
            if threshold_candidates:
                candidates.extend(
                    candidate.model_copy(update={"confidence": max(candidate.confidence, 0.74)})
                    for candidate in threshold_candidates
                )
                reason_codes.extend(["cnc_fallback_threshold_pattern", *threshold_reason_codes])
            else:
                word_threshold_match = _WORD_THRESHOLD_RE.search(sentence)
                if word_threshold_match:
                    object_uk = _clip_text(
                        f"{word_threshold_match.group('lemma')} {word_threshold_match.group('value')} {word_threshold_match.group('unit')}",
                        120,
                    )
                    candidates.append(
                        _build_candidate(
                            subject_uk=doc_title or "регульований показник",
                            predicate="sets_threshold",
                            object_uk=object_uk,
                            norm_type="obligation",
                            fact_text=f"{doc_title or 'регульований показник'} має поріг {object_uk}",
                            quote=quote,
                            confidence=0.73,
                            thresholds_text=analysis_sentence,
                        )
                    )
                    reason_codes.append("cnc_fallback_word_threshold_pattern")

        # Subject-verb-object with deontic markers: obligation
        require_match = _search_with_optional_context(
            _SUBJECT_REQUIRE_RE,
            sentence,
            analysis_text=analysis_sentence,
        )
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
                        quote=quote,
                        confidence=0.76,
                    )
                )
                reason_codes.append("cnc_fallback_requirement_pattern")

        # Prohibition patterns
        prohibit_match = _search_with_optional_context(
            _SUBJECT_PROHIBIT_RE,
            sentence,
            analysis_text=analysis_sentence,
        )
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
                        quote=quote,
                        confidence=0.76,
                    )
                )
                reason_codes.append("cnc_fallback_prohibition_pattern")

        # Permission patterns
        permission_match = _search_with_optional_context(
            _SUBJECT_PERMISSION_RE,
            sentence,
            analysis_text=analysis_sentence,
        )
        if permission_match:
            raw_subject = permission_match.group("subject").strip(" ,;:")
            raw_object = permission_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 160)
            object_uk = _clip_text(raw_object, 220)
            if subject_uk and object_uk:
                lemma = permission_match.group("lemma").lower()
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="grants",
                        object_uk=(f"має право {object_uk}" if "має право" in lemma else object_uk),
                        norm_type="permission",
                        fact_text=f"{subject_uk} {permission_match.group('lemma').strip()} {raw_object}",
                        quote=quote,
                        confidence=0.75,
                    )
                )
                reason_codes.append("cnc_fallback_permission_pattern")

        impersonal_require_match = _search_with_optional_context(
            _APPLICATION_IMPERSONAL_REQUIRE_RE,
            sentence,
            analysis_text=analysis_sentence,
        )
        if impersonal_require_match:
            object_uk = _clip_text(impersonal_require_match.group("object").strip(" .;:"), 220)
            if object_uk:
                candidates.append(
                    _build_candidate(
                        subject_uk="адресат норми",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"Необхідно {object_uk}",
                        quote=quote,
                        confidence=0.73,
                    )
                )
                reason_codes.append("cnc_fallback_impersonal_requirement_pattern")

        impersonal_permission_match = _search_with_optional_context(
            _APPLICATION_IMPERSONAL_PERMISSION_RE,
            sentence,
            analysis_text=analysis_sentence,
        )
        if impersonal_permission_match:
            object_uk = _clip_text(impersonal_permission_match.group("object").strip(" .;:"), 220)
            if object_uk:
                candidates.append(
                    _build_candidate(
                        subject_uk="адресат норми",
                        predicate="grants",
                        object_uk=object_uk,
                        norm_type="permission",
                        fact_text=f"Можна {object_uk}",
                        quote=quote,
                        confidence=0.73,
                    )
                )
                reason_codes.append("cnc_fallback_impersonal_permission_pattern")

        # Passive procedure: "X проводиться/здійснюється Y"
        passive_match = _search_with_optional_context(
            _PASSIVE_PROCEDURE_RE,
            sentence,
            analysis_text=analysis_sentence,
        )
        if passive_match:
            raw_subject = passive_match.group("subject").strip(" ,;:")
            raw_object = passive_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 160)
            object_uk = _clip_text(raw_object, 220)
            if subject_uk and object_uk:
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="applies_to",
                        object_uk=object_uk,
                        norm_type="procedure",
                        fact_text=f"{subject_uk} {passive_match.group('lemma').strip()} {object_uk}",
                        quote=quote,
                        confidence=0.73,
                    )
                )
                reason_codes.append("cnc_fallback_passive_procedure_pattern")

        passive_mandatory_match = _search_with_optional_context(
            _PASSIVE_MANDATORY_ACTION_RE,
            sentence,
            analysis_text=analysis_sentence,
        )
        if passive_mandatory_match:
            raw_subject = passive_mandatory_match.group("subject").strip(" ,;:")
            raw_object = passive_mandatory_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 160)
            object_uk = _clip_text(raw_object, 220)
            if subject_uk and object_uk:
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"{subject_uk} {passive_mandatory_match.group('lemma').strip()} {object_uk}",
                        quote=quote,
                        confidence=0.75,
                        thresholds_text=analysis_sentence,
                    )
                )
                reason_codes.append("cnc_fallback_passive_mandatory_action_pattern")

        # "X підлягає Y"
        subject_to_match = _search_with_optional_context(
            _SUBJECT_TO_RE,
            sentence,
            analysis_text=analysis_sentence,
        )
        if subject_to_match:
            raw_subject = subject_to_match.group("subject").strip(" ,;:")
            raw_object = subject_to_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 160)
            object_uk = _clip_text(raw_object, 220)
            if subject_uk and object_uk:
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="applies_to",
                        object_uk=object_uk,
                        norm_type="applicability",
                        fact_text=f"{subject_uk} підлягає {object_uk}",
                        quote=quote,
                        confidence=0.73,
                    )
                )
                reason_codes.append("cnc_fallback_subject_to_pattern")

        # Scope: "X поширюється на Y"
        scope_match = _search_with_optional_context(
            _APPLIES_SCOPE_RE,
            sentence,
            analysis_text=analysis_sentence,
        )
        if scope_match:
            raw_subject = scope_match.group("subject").strip(" ,;:")
            raw_object = scope_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 160)
            object_uk = _clip_text(raw_object, 220)
            if subject_uk and object_uk:
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="applies_to",
                        object_uk=object_uk,
                        norm_type="applicability",
                        fact_text=f"{subject_uk} поширюється на {object_uk}",
                        quote=quote,
                        confidence=0.74,
                    )
                )
                reason_codes.append("cnc_fallback_scope_pattern")

        # "X встановлює порядок Y"
        order_match = _search_with_optional_context(
            _ESTABLISHES_ORDER_RE,
            sentence,
            analysis_text=analysis_sentence,
        )
        if order_match:
            raw_subject = order_match.group("subject").strip(" ,;:")
            raw_object = order_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 160)
            object_uk = _clip_text(raw_object, 220)
            if subject_uk and object_uk:
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="defines",
                        object_uk=object_uk,
                        norm_type="procedure",
                        fact_text=f"{subject_uk} встановлює {object_uk}",
                        quote=quote,
                        confidence=0.74,
                    )
                )
                reason_codes.append("cnc_fallback_establishes_order_pattern")

        # Dash-definition "X - Y" (without article context)
        dash_match = _DASH_DEFINITION_RE.match(sentence)
        if dash_match:
            raw_subject = dash_match.group("subject").strip(" ,;:")
            raw_object = dash_match.group("object").strip(" .;:")
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
                        confidence=0.74,
                    )
                )
                reason_codes.append("cnc_fallback_dash_definition_pattern")

        # "X - це Y" (without article context)
        dash_this_match = _DASH_THIS_IS_RE.match(sentence)
        if dash_this_match:
            raw_subject = dash_this_match.group("subject").strip(" ,;:")
            raw_object = dash_this_match.group("object").strip(" .;:")
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
                        confidence=0.73,
                    )
                )
                reason_codes.append("cnc_fallback_dash_this_is_pattern")

    if legal_unit_micro_subtype == "reference_tail":
        citation_match = _AMEND_CITATION_RE.search(analysis_full_text)
        if citation_match:
            candidates.append(
                _build_candidate(
                    subject_uk="орган, що прийняв акт",
                    predicate="amends",
                    object_uk=f"стаття/пункт {citation_match.group(1)} {doc_title or 'зазначеного акту'}",
                    norm_type="amendment",
                    fact_text=f"Внесено зміни до статті/пункту {citation_match.group(1)}",
                    quote=_clip_text(text, size=320),
                    confidence=0.75,
                )
            )
            reason_codes.append("cnc_fallback_reference_tail_pattern")

    return candidates, reason_codes


def _extract_context_inherited_appendix_candidates(
    *,
    text: str,
    context_prefix: str = "",
    doc_title: str = "",
) -> tuple[list[SPOCandidate], list[str]]:
    context = " ".join(str(context_prefix or "").split()).strip()
    item_text = _normalize_inherited_list_item(text)
    if not context or len(item_text) < 3:
        return [], []

    quote = _clip_text(text, size=320)
    candidates: list[SPOCandidate] = []
    reason_codes: list[str] = []

    if _CONTEXT_REMOVE_LIST_RE.search(context):
        candidates.append(
            _build_candidate(
                subject_uk="орган, що прийняв акт",
                predicate="amends",
                object_uk=_clip_text(f"виключення з переліку: {item_text}", 240),
                norm_type="amendment",
                fact_text=f"Виключено з переліку: {item_text}",
                quote=quote,
                confidence=0.84,
            )
        )
        reason_codes.append("context_remove_list_inheritance")
    elif _CONTEXT_ADD_LIST_RE.search(context):
        candidates.append(
            _build_candidate(
                subject_uk="орган, що прийняв акт",
                predicate="amends",
                object_uk=_clip_text(f"включення до переліку: {item_text}", 240),
                norm_type="amendment",
                fact_text=f"Включено до переліку: {item_text}",
                quote=quote,
                confidence=0.83,
            )
        )
        reason_codes.append("context_add_list_inheritance")
    elif _CONTEXT_APPROVAL_RE.search(context):
        candidates.append(
            _build_candidate(
                subject_uk="орган, що прийняв акт",
                predicate="approves",
                object_uk=_clip_text(item_text, 220),
                norm_type="procedure",
                fact_text=f"Затверджено елемент переліку: {item_text}",
                quote=quote,
                confidence=0.8,
            )
        )
        reason_codes.append("context_approval_list_inheritance")

    return candidates, reason_codes


def _extract_semantic_tail_candidates(
    *,
    text: str,
    doc_title: str,
    context_prefix: str = "",
) -> tuple[list[SPOCandidate], list[str]]:
    candidates: list[SPOCandidate] = []
    reason_codes: list[str] = []
    seen: set[tuple[str, str]] = set()

    def _append(candidate: SPOCandidate, reason_code: str) -> None:
        key = (candidate.predicate, candidate.fact_text)
        if key in seen:
            return
        seen.add(key)
        candidates.append(candidate)
        reason_codes.append(reason_code)

    analysis_text = _combine_with_context(text, context_prefix)
    for clause in _iter_semantic_clauses(analysis_text):
        clause = clause.strip()
        if len(clause) < 10:
            continue
        quote = _clip_text(clause, size=320)

        for match in _TAIL_PERMISSION_RE.finditer(clause):
            subject_uk = _clip_text(match.group("subject").strip(" ,;:"), 180)
            object_uk = _clip_text(match.group("object").strip(" .;:"), 240)
            if subject_uk and object_uk:
                _append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="grants",
                        object_uk=(f"має право {object_uk}" if "право" in match.group("lemma").lower() else object_uk),
                        norm_type="permission",
                        fact_text=f"{subject_uk} {match.group('lemma').strip()} {object_uk}",
                        quote=quote,
                        confidence=0.79,
                        thresholds_text=clause,
                    ),
                    "semantic_tail_permission",
                )

        for match in _TAIL_PROHIBITION_RE.finditer(clause):
            subject_uk = _clip_text(match.group("subject").strip(" ,;:"), 180)
            object_uk = _clip_text(match.group("object").strip(" .;:"), 240)
            if subject_uk and object_uk:
                _append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="prohibits",
                        object_uk=object_uk,
                        norm_type="prohibition",
                        fact_text=f"{subject_uk} {match.group('lemma').strip()} {object_uk}",
                        quote=quote,
                        confidence=0.79,
                    ),
                    "semantic_tail_prohibition",
                )

        for sanction_match in _SANCTION_RE.finditer(clause):
            subject_uk = _clip_text(sanction_match.group("subject").strip(" ,;:"), 180)
            raw_object = sanction_match.group("object").strip(" .;:")
            lemma_text = sanction_match.group("lemma").strip()
            # Check if the object ends with a colon followed by a list
            # (e.g. "тягне за собою: штраф; позбавлення ліцензії; ...")
            tail_after_match = clause[sanction_match.end():]
            list_items = list(_iter_list_items(tail_after_match)) if ":" in raw_object or tail_after_match.lstrip().startswith(";") else []
            if list_items and subject_uk:
                # Colon-delimited list: each item is a separate sanction
                base_object = raw_object.split(":")[0].strip() if ":" in raw_object else raw_object
                for item in list_items:
                    item_uk = _clip_text(item, 220)
                    if item_uk:
                        _append(
                            _build_candidate(
                                subject_uk=subject_uk,
                                predicate="sanctions",
                                object_uk=item_uk,
                                norm_type="sanction",
                                fact_text=f"{subject_uk} {lemma_text} {item_uk}",
                                quote=quote,
                                confidence=0.77,
                            ),
                            "semantic_tail_sanction_list_item",
                        )
            elif subject_uk and raw_object:
                object_uk = _clip_text(raw_object, 240)
                _append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="sanctions",
                        object_uk=object_uk,
                        norm_type="sanction",
                        fact_text=f"{subject_uk} {lemma_text} {object_uk}",
                        quote=quote,
                        confidence=0.79,
                    ),
                    "semantic_tail_sanction",
                )

        threshold_policy_match = _TAIL_THRESHOLD_POLICY_RE.search(clause)
        if threshold_policy_match:
            object_uk = _clip_text(threshold_policy_match.group("object").strip(" .;:"), 240)
            _append(
                _build_candidate(
                    subject_uk=doc_title or "регульований показник",
                    predicate="sets_threshold",
                    object_uk=object_uk,
                    norm_type="obligation",
                    fact_text=f"Визначено поріг або ставку: {object_uk}",
                    quote=quote,
                    confidence=0.78,
                    thresholds_text=clause,
                ),
                "semantic_tail_threshold_policy",
            )
        elif not threshold_policy_match:
            # Fallback: if clause contains numeric rates/percentages that
            # extract_thresholds_from_text can parse, emit a sets_threshold
            # candidate so the audit category "threshold" is covered.
            numeric_thresholds = extract_thresholds_from_text(clause)
            if numeric_thresholds:
                thr_summary = "; ".join(
                    f"{t.value_text} {t.unit}" for t in numeric_thresholds[:3]
                )
                _append(
                    _build_candidate(
                        subject_uk=doc_title or "регульований показник",
                        predicate="sets_threshold",
                        object_uk=_clip_text(thr_summary, 240),
                        norm_type="threshold",
                        fact_text=f"Встановлено числовий поріг: {thr_summary}",
                        quote=quote,
                        confidence=0.75,
                        thresholds_text=clause,
                    ),
                    "numeric_threshold_fallback",
                )

        uses_rights_match = _USES_RIGHTS_RE.search(clause)
        if uses_rights_match:
            subject_uk = _clip_text(uses_rights_match.group("subject").strip(" ,;:"), 180)
            object_uk = _clip_text(uses_rights_match.group("object").strip(" .;:"), 240)
            _append(
                _build_candidate(
                    subject_uk=subject_uk,
                    predicate="grants",
                    object_uk=object_uk,
                    norm_type="permission",
                    fact_text=f"{subject_uk} користується {object_uk}",
                    quote=quote,
                    confidence=0.77,
                ),
                "semantic_tail_uses_rights",
            )

        no_liability_match = _NO_LIABILITY_RE.search(clause)
        if no_liability_match:
            subject_uk = _clip_text(no_liability_match.group("subject").strip(" ,;:"), 180)
            object_uk = _clip_text(no_liability_match.group("object").strip(" .;:"), 240)
            _append(
                _build_candidate(
                    subject_uk=subject_uk,
                    predicate="grants",
                    object_uk=f"не несе відповідальності за {object_uk}",
                    norm_type="permission",
                    fact_text=f"{subject_uk} не несе відповідальності за {object_uk}",
                    quote=quote,
                    confidence=0.77,
                ),
                "semantic_tail_no_liability",
            )

    return candidates, reason_codes
