"""Family-specific deterministic SPO extractors."""

from __future__ import annotations

from polisyos.lex.batch import deterministic_spo as _base

_BASE_EXPORTS = {'re', 'canonicalize_action', 'canonicalize_norm_type', 'extract_thresholds_from_text'}
for _name in dir(_base):
    if _name.startswith("_") or _name in _BASE_EXPORTS:
        globals().setdefault(_name, getattr(_base, _name))
del _name

def _approval_object_hint(text: str) -> str:
    lines = [_compact for _compact in (" ".join(line.split()) for line in text.splitlines()) if _compact]
    skip_markers = ("розпорядженням", "постановою", "наказом", "від ", "n ", "№")
    for line in lines:
        lower = line.lower()
        if any(marker in lower for marker in skip_markers):
            continue
        if lower.startswith(("затверджено", "схвалено", "погоджено", "затвердити", "схвалити", "погодити")):
            continue
        if len(line) >= 5:
            return _clip_text(line, 220)
    return ""


def _extract_amendment_bundle_candidates(*, text: str, doc_title: str) -> tuple[list[SPOCandidate], list[str]]:
    cleaned = text.strip()
    if not cleaned:
        return [], []
    quote = _clip_text(cleaned, size=360)
    candidates: list[SPOCandidate] = []
    reason_codes: list[str] = []
    seen_keys: set[tuple[str, str]] = set()

    for fragment in _iter_distinct_chunks(cleaned):
        fragment_quote = _clip_text(fragment, size=320)
        citation_match = _AMEND_CITATION_RE.search(fragment)
        wording_match = _AMEND_WORDING_RE.search(fragment)
        amend_match = _AMEND_RE.search(fragment)
        if citation_match or wording_match or amend_match:
            amend_target = doc_title or "зазначений акт"
            if citation_match:
                amend_target = f"стаття/пункт {citation_match.group(1)} {doc_title or 'зазначеного акту'}"
            elif wording_match:
                amend_target = _clip_text(wording_match.group("object").strip(" .;:"), 220)
            else:
                amend_target = _clip_text(fragment.strip(" .;:"), 220)
            candidate = _build_candidate(
                subject_uk="орган, що прийняв акт",
                predicate="amends",
                object_uk=amend_target,
                norm_type="amendment",
                fact_text=f"Внесено зміни до {amend_target}",
                quote=fragment_quote,
                confidence=0.9 if citation_match else 0.86,
            )
            key = (candidate.predicate, candidate.fact_text)
            if key not in seen_keys:
                seen_keys.add(key)
                candidates.append(candidate)
            reason_codes.append("subtype_amendment_bundle")
            if fragment != cleaned:
                reason_codes.append("subtype_amendment_bundle_multistatement")
            if "новій редакції" in fragment.lower() or "такій редакції" in fragment.lower():
                candidate = _build_candidate(
                    subject_uk="орган, що прийняв акт",
                    predicate="supersedes",
                    object_uk=amend_target,
                    norm_type="amendment",
                    fact_text=f"Попередню редакцію норми замінено: {amend_target}",
                    quote=fragment_quote,
                    confidence=0.85,
                )
                key = (candidate.predicate, candidate.fact_text)
                if key not in seen_keys:
                    seen_keys.add(key)
                    candidates.append(candidate)
                reason_codes.append("subtype_supersedes_bundle")

        repeal_match = _REPEAL_RE.search(fragment)
        if repeal_match:
            repeal_target = (repeal_match.group(1) or "").strip(" .;:") or "визначені акти"
            candidate = _build_candidate(
                subject_uk="орган, що прийняв акт",
                predicate="repeals",
                object_uk=_clip_text(repeal_target, 220),
                norm_type="repeal",
                fact_text=f"Скасовано або визнано таким, що втратив чинність: {_clip_text(repeal_target, 180)}",
                quote=fragment_quote,
                confidence=0.9,
            )
            key = (candidate.predicate, candidate.fact_text)
            if key not in seen_keys:
                seen_keys.add(key)
                candidates.append(candidate)
            reason_codes.append("subtype_repeal_bundle")
        elif "виключити" in fragment.lower() or "виключено" in fragment.lower():
            repeal_target = _clip_text(fragment.strip(" .;:"), 220)
            candidate = _build_candidate(
                subject_uk="орган, що прийняв акт",
                predicate="repeals",
                object_uk=repeal_target,
                norm_type="repeal",
                fact_text=f"Виключено норму або об'єкт: {repeal_target}",
                quote=fragment_quote,
                confidence=0.86,
            )
            key = (candidate.predicate, candidate.fact_text)
            if key not in seen_keys:
                seen_keys.add(key)
                candidates.append(candidate)
            reason_codes.append("subtype_repeal_bundle")

        entry_match = _ENTRY_INTO_FORCE_RE.search(fragment)
        if entry_match:
            entry = (entry_match.group(1) or "").strip(" .;:")
            candidate = _build_candidate(
                subject_uk="цей акт",
                predicate="enters_into_force",
                object_uk=entry or "у визначений строк",
                norm_type="entry_into_force",
                fact_text=f"Акт набирає чинності {entry or 'у визначений строк'}",
                quote=fragment_quote,
                confidence=0.88,
            )
            key = (candidate.predicate, candidate.fact_text)
            if key not in seen_keys:
                seen_keys.add(key)
                candidates.append(candidate)
            reason_codes.append("subtype_entry_into_force")

    return candidates, reason_codes


def _extract_approval_bundle_candidates(
    *,
    text: str,
    doc_title: str,
    context_prefix: str = "",
) -> tuple[list[SPOCandidate], list[str]]:
    cleaned = text.strip()
    if not cleaned:
        return [], []
    quote = _clip_text(cleaned, size=360)
    candidates: list[SPOCandidate] = []
    reason_codes: list[str] = []
    seen_keys: set[tuple[str, str]] = set()

    def _append(candidate: SPOCandidate, reason_code: str) -> None:
        key = (candidate.predicate, candidate.fact_text)
        if key in seen_keys:
            return
        seen_keys.add(key)
        candidates.append(candidate)
        reason_codes.append(reason_code)

    analysis_text = _combine_with_context(cleaned, context_prefix)
    for fragment in _iter_distinct_chunks(cleaned):
        fragment_quote = _clip_text(fragment, size=320)
        analysis_fragment = _combine_with_context(fragment, context_prefix)
        for match in _APPROVAL_BUNDLE_RE.finditer(analysis_fragment):
            lemma = match.group("lemma").strip().lower()
            object_uk = _clip_text(match.group("object").strip(" .;:"), 220)
            annex_match = _ANNEX_RE.search(object_uk) or _ANNEX_RE.search(analysis_fragment)
            approval_target = (
                object_uk
                or (annex_match.group(1) if annex_match else "")
                or _approval_object_hint(analysis_fragment)
                or _clip_text(doc_title, 220)
                or "доданий документ"
            )
            if lemma.startswith(("затверд", "схвал", "погод")):
                _append(
                    _build_candidate(
                        subject_uk="орган, що прийняв акт",
                        predicate="approves",
                        object_uk=approval_target,
                        norm_type="procedure",
                        fact_text=f"Схвалено або затверджено: {approval_target}",
                        quote=fragment_quote,
                        confidence=0.87 if annex_match else 0.83,
                    ),
                    "subtype_approval_bundle",
                )
                if annex_match:
                    _append(
                        _build_candidate(
                            subject_uk="цей акт",
                            predicate="applies_to",
                            object_uk=_clip_text(annex_match.group(1), 180),
                            norm_type="applicability",
                            fact_text=f"Акт застосовується до {annex_match.group(1)}",
                            quote=fragment_quote,
                            confidence=0.78,
                        ),
                        "subtype_approval_annex_reference",
                    )
            elif lemma.startswith("доруч"):
                _append(
                    _build_candidate(
                        subject_uk="адресат акта",
                        predicate="delegates",
                        object_uk=object_uk or doc_title or "виконання дії",
                        norm_type="delegation",
                        fact_text=f"Доручено: {object_uk or 'виконання дії'}",
                        quote=fragment_quote,
                        confidence=0.82,
                    ),
                    "subtype_delegate_bundle",
                )

        requirement_match = _SUBJECT_REQUIRE_RE.search(analysis_fragment) or _APPLICATION_IMPERSONAL_REQUIRE_RE.search(analysis_fragment)
        if requirement_match:
            object_uk = _clip_text(
                (requirement_match.groupdict().get("object") or "").strip(" .;:"),
                220,
            )
            if object_uk:
                _append(
                    _build_candidate(
                        subject_uk="адресат акта",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"Адресат акта має виконати: {object_uk}",
                        quote=fragment_quote,
                        confidence=0.79,
                    ),
                    "subtype_approval_requirement",
                )

        delegate_match = _DELEGATE_RE.search(analysis_fragment)
        if delegate_match and "доруч" not in analysis_fragment.lower():
            _append(
                _build_candidate(
                    subject_uk="орган, що прийняв акт",
                    predicate="delegates",
                    object_uk=_clip_text(fragment, 220),
                    norm_type="delegation",
                    fact_text=f"Делеговано виконання: {_clip_text(fragment, 180)}",
                    quote=fragment_quote,
                    confidence=0.77,
                ),
                "subtype_delegate_bundle",
            )

        entry_match = _ENTRY_INTO_FORCE_RE.search(analysis_fragment)
        if entry_match:
            entry = (entry_match.group(1) or "").strip(" .;:")
            _append(
                _build_candidate(
                    subject_uk="цей акт",
                    predicate="enters_into_force",
                    object_uk=entry or "у визначений строк",
                    norm_type="entry_into_force",
                    fact_text=f"Акт набирає чинності {entry or 'у визначений строк'}",
                    quote=fragment_quote,
                    confidence=0.82,
                ),
                "subtype_approval_entry_into_force",
            )

        scope_match = _APPLIES_SCOPE_RE.search(analysis_fragment)
        if scope_match:
            subject_uk = _clip_text(scope_match.group("subject").strip(" ,;:"), 160)
            object_uk = _clip_text(scope_match.group("object").strip(" .;:"), 220)
            if subject_uk and object_uk:
                _append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="applies_to",
                        object_uk=object_uk,
                        norm_type="applicability",
                        fact_text=f"{subject_uk} поширюється на {object_uk}",
                        quote=fragment_quote,
                        confidence=0.78,
                    ),
                    "subtype_approval_scope",
                )

    # Fallback: if no explicit approval verb, try to identify the approved object
    # from document context (annex references, title lines, etc.)
    if not candidates:
        annex_match = _ANNEX_RE.search(analysis_text)
        hint = _approval_object_hint(analysis_text)
        if annex_match or hint:
            approval_target = (
                (annex_match.group(1) if annex_match else "")
                or hint
                or _clip_text(doc_title, 220)
                or "доданий документ"
            )
            _append(
                _build_candidate(
                    subject_uk="орган, що прийняв акт",
                    predicate="approves",
                    object_uk=approval_target,
                    norm_type="procedure",
                    fact_text=f"Затверджено: {approval_target}",
                    quote=quote,
                    confidence=0.78,
                ),
                "subtype_approval_bundle_context_fallback",
            )
        elif doc_title and len(cleaned) >= 10:
            # Last resort: use doc_title as approved object when provision
            # has normative content but no specific approval verb
            _append(
                _build_candidate(
                    subject_uk="орган, що прийняв акт",
                    predicate="approves",
                    object_uk=_clip_text(doc_title, 220),
                    norm_type="procedure",
                    fact_text=f"Затверджено документ: {_clip_text(doc_title, 180)}",
                    quote=quote,
                    confidence=0.72,
                ),
                "subtype_approval_bundle_title_fallback",
            )

    return candidates, reason_codes


def _extract_threshold_row_candidates_inner(
    *,
    text: str,
    doc_title: str,
    context_prefix: str = "",
) -> tuple[list[SPOCandidate], list[str]]:
    cleaned = text.strip()
    if not cleaned:
        return [], []
    quote = _clip_text(cleaned, size=320)
    analysis_text = _combine_with_context(cleaned, context_prefix)
    thresholds = extract_thresholds_from_text(analysis_text, applies_to=doc_title or "регульований показник")

    def _emit_threshold_candidates(
        *,
        subject_hint: str,
        raw_thresholds: list,
        base_confidence: float,
        reason_code: str,
    ) -> tuple[list[SPOCandidate], list[str]]:
        candidates: list[SPOCandidate] = []
        reasons: list[str] = []
        subject = _clip_text(subject_hint or doc_title or "регульований показник", 160)
        for threshold in raw_thresholds:
            value_text = str(getattr(threshold, "value_text", "") or getattr(threshold, "value_decimal", "") or "").strip()
            unit = str(getattr(threshold, "unit", "") or "").strip()
            if not value_text:
                continue
            object_uk = f"{value_text} {unit}".strip()
            candidates.append(
                _build_candidate(
                    subject_uk=subject or "регульований показник",
                    predicate="sets_threshold",
                    object_uk=object_uk,
                    norm_type="obligation",
                    fact_text=f"{subject or 'регульований показник'} має поріг {object_uk}",
                    quote=quote,
                    confidence=base_confidence,
                    thresholds_text=analysis_text,
                )
            )
            reasons.append(reason_code)
        return candidates, reasons

    match = _THRESHOLD_ROW_RE.search(cleaned)
    if not match:
        unitless_match = _UNITLESS_THRESHOLD_ROW_RE.search(cleaned)
        if unitless_match and _SALARY_TABLE_RE.search(f"{doc_title} {cleaned}"):
            subject_uk = _clip_text(unitless_match.group("subject").strip(" .;:"), 160)
            value = unitless_match.group("value").strip()
            return [
                _build_candidate(
                    subject_uk=subject_uk or "регульований показник",
                    predicate="sets_threshold",
                    object_uk=f"{value} грн",
                    norm_type="obligation",
                    fact_text=f"{subject_uk or 'регульований показник'} має поріг {value} грн",
                    quote=quote,
                    confidence=0.88,
                    thresholds_text=f"{cleaned} грн",
                )
            ], ["subtype_threshold_unitless_row"]
    if not match:
        multi_match = _MULTIVALUE_THRESHOLD_ROW_RE.search(cleaned)
        if multi_match:
            subject_uk = _clip_text(multi_match.group("subject").strip(" .;:"), 160)
            unit = str(multi_match.group("unit") or "").strip()
            raw_values = [value for value in re.split(r"\s+", multi_match.group("values").strip()) if value]
            multi_candidates = [
                _build_candidate(
                    subject_uk=subject_uk or "регульований показник",
                    predicate="sets_threshold",
                    object_uk=f"{value} {unit}".strip(),
                    norm_type="obligation",
                    fact_text=f"{subject_uk or 'регульований показник'} має поріг {(f'{value} {unit}').strip()}",
                    quote=quote,
                    confidence=0.88,
                    thresholds_text=cleaned,
                )
                for value in raw_values
            ]
            if multi_candidates:
                return multi_candidates, ["subtype_threshold_multivalue_row"] * len(multi_candidates)
        condition_match = _CONDITION_THRESHOLD_RE.search(cleaned)
        if condition_match:
            value_label = f"{condition_match.group('lemma').strip()} {condition_match.group('value').strip()} {condition_match.group('unit').strip()}"
            subject_hint = _clip_text(cleaned[: max(12, condition_match.start())].strip(" .;:-"), 160)
            return [
                _build_candidate(
                    subject_uk=subject_hint or doc_title or "регульований показник",
                    predicate="sets_threshold",
                    object_uk=value_label,
                    norm_type="obligation",
                    fact_text=f"{subject_hint or doc_title or 'регульований показник'} має умову {value_label}",
                    quote=quote,
                    confidence=0.87,
                    thresholds_text=cleaned,
                )
            ], ["subtype_threshold_condition_row"]
        if not thresholds:
            return [], []
        if _SALARY_TABLE_RE.search(f"{doc_title} {cleaned}") and len(thresholds) >= 2:
            return [
                _build_candidate(
                    subject_uk="зазначені посади",
                    predicate="sets_threshold",
                    object_uk="схема посадових окладів",
                    norm_type="obligation",
                    fact_text="Встановлено схему посадових окладів для зазначених посад",
                    quote=quote,
                    confidence=0.87,
                    thresholds_text=analysis_text,
                )
            ], ["subtype_threshold_schedule_row"]
        threshold_candidates, threshold_reasons = _emit_threshold_candidates(
            subject_hint=doc_title or "орган, що прийняв акт",
            raw_thresholds=thresholds,
            base_confidence=0.86,
            reason_code="subtype_threshold_fallback",
        )
        if threshold_candidates:
            return threshold_candidates, threshold_reasons
        return [], []
    subject_uk = _clip_text(match.group("subject").strip(" .;:"), 160)
    value = match.group("value").strip()
    unit = match.group("unit").strip()
    return [
        _build_candidate(
            subject_uk=subject_uk or "регульований показник",
            predicate="sets_threshold",
            object_uk=f"{value} {unit}",
            norm_type="obligation",
            fact_text=f"{subject_uk or 'регульований показник'} має поріг {value} {unit}",
            quote=quote,
            confidence=0.9,
            thresholds_text=analysis_text,
        )
    ], ["subtype_threshold_row"]


def _extract_threshold_row_candidates(
    *,
    text: str,
    doc_title: str,
    context_prefix: str = "",
) -> tuple[list[SPOCandidate], list[str]]:
    """Extract threshold from tariff_threshold_row provisions.

    Delegates to internal _extract_threshold_row_candidates_inner and adds
    a text-based fallback for provisions that didn't match numeric patterns.
    """
    candidates, reason_codes = _extract_threshold_row_candidates_inner(
        text=text,
        doc_title=doc_title,
        context_prefix=context_prefix,
    )
    if candidates:
        return candidates, reason_codes

    # Fallback: provision classified as tariff_threshold_row but no numeric match.
    # Create a minimal candidate from the text content itself.
    cleaned = text.strip()
    if not cleaned or len(cleaned) < 6:
        return [], []
    quote = _clip_text(cleaned, size=320)
    subject_hint = _clip_text(cleaned, 160)
    return [
        _build_candidate(
            subject_uk=subject_hint,
            predicate="sets_threshold",
            object_uk=doc_title or "регульований показник",
            norm_type="obligation",
            fact_text=f"Визначено параметр: {subject_hint}",
            quote=quote,
            confidence=0.7,
            thresholds_text=_combine_with_context(cleaned, context_prefix),
        )
    ], ["subtype_threshold_text_fallback"]


def _extract_application_requirement_candidates(
    *,
    text: str,
    context_prefix: str = "",
) -> tuple[list[SPOCandidate], list[str]]:
    cleaned = text.strip()
    if not cleaned:
        return [], []
    if _looks_like_form_label(cleaned):
        return [], ["subtype_application_form_label"]
    quote = _clip_text(cleaned, size=320)
    candidates: list[SPOCandidate] = []
    reason_codes: list[str] = []
    seen_keys: set[tuple[str, str]] = set()

    def _append_candidate(candidate: SPOCandidate, reason_code: str) -> None:
        key = (candidate.predicate, candidate.fact_text)
        if key in seen_keys:
            return
        seen_keys.add(key)
        candidates.append(candidate)
        reason_codes.append(reason_code)

    block_entries = list(_iter_form_blocks(cleaned, context_prefix=context_prefix))
    if not block_entries:
        block_entries = [(_combine_with_context(cleaned, context_prefix), cleaned)]

    for analysis_chunk, chunk_quote_source in block_entries:
        chunk = chunk_quote_source
        chunk_quote = _clip_text(chunk_quote_source, size=320)
        applicant_matches = list(_APPLICANT_ACTION_RE.finditer(chunk))
        if not applicant_matches:
            applicant_matches = list(_APPLICANT_ACTION_RE.finditer(analysis_chunk))
        for match in applicant_matches:
            lemma = match.group("lemma").strip().lower()
            subject_uk = _clip_text((match.group("subject") or "заявник").strip(" ,;:"), 140)
            object_uk = _clip_text(match.group("object").strip(" .;:"), 220)
            predicate = "requires"
            norm_type = "obligation"
            if "просить" in lemma:
                predicate = "grants"
                norm_type = "permission"
            _append_candidate(
                _build_candidate(
                    subject_uk=subject_uk or "заявник",
                    predicate=predicate,
                    object_uk=object_uk or "виконати вимогу форми",
                    norm_type=norm_type,
                    fact_text=f"{subject_uk or 'заявник'} {lemma} {object_uk or 'виконати вимогу форми'}",
                    quote=chunk_quote,
                    confidence=0.84,
                ),
                "subtype_application_requirement",
            )

        impersonal_require_match = _APPLICATION_IMPERSONAL_REQUIRE_RE.search(chunk) or _APPLICATION_IMPERSONAL_REQUIRE_RE.search(analysis_chunk)
        if impersonal_require_match:
            object_uk = _clip_text(impersonal_require_match.group("object").strip(" .;:"), 220)
            if object_uk:
                _append_candidate(
                    _build_candidate(
                        subject_uk="заявник",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"заявник {impersonal_require_match.group('lemma').strip().lower()} {object_uk}",
                        quote=chunk_quote,
                        confidence=0.8,
                    ),
                    "subtype_application_requirement_impersonal",
                )

        impersonal_permission_match = _APPLICATION_IMPERSONAL_PERMISSION_RE.search(chunk) or _APPLICATION_IMPERSONAL_PERMISSION_RE.search(analysis_chunk)
        if impersonal_permission_match:
            object_uk = _clip_text(impersonal_permission_match.group("object").strip(" .;:"), 220)
            if object_uk:
                _append_candidate(
                    _build_candidate(
                        subject_uk="заявник",
                        predicate="grants",
                        object_uk=object_uk,
                        norm_type="permission",
                        fact_text=f"заявник може {object_uk}",
                        quote=chunk_quote,
                        confidence=0.78,
                    ),
                    "subtype_application_requirement_permission",
                )

        subject_permission_matches = list(_APPLICATION_SUBJECT_PERMISSION_RE.finditer(chunk))
        if not subject_permission_matches:
            subject_permission_matches = list(_APPLICATION_SUBJECT_PERMISSION_RE.finditer(analysis_chunk))
        for match in subject_permission_matches:
            subject_uk = _clip_text(match.group("subject").strip(" ,;:"), 140)
            object_uk = _clip_text(match.group("object").strip(" .;:"), 220)
            if subject_uk and object_uk:
                _append_candidate(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="grants",
                        object_uk=(f"має право {object_uk}" if "право" in match.group("lemma").lower() else object_uk),
                        norm_type="permission",
                        fact_text=f"{subject_uk} {match.group('lemma').strip().lower()} {object_uk}",
                        quote=chunk_quote,
                        confidence=0.8,
                    ),
                    "subtype_application_requirement_subject_permission",
                )

        completeness_match = _APPLICATION_COMPLETENESS_RE.search(chunk) or _APPLICATION_COMPLETENESS_RE.search(analysis_chunk)
        if completeness_match:
            subject_uk = _clip_text(completeness_match.group("subject").strip(" .;:"), 180)
            object_uk = _clip_text(completeness_match.group("object").strip(" .;:"), 220)
            if subject_uk and object_uk:
                _append_candidate(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="applies_to",
                        object_uk=object_uk,
                        norm_type="condition",
                        fact_text=f"{subject_uk} {completeness_match.group('lemma').strip()} {object_uk}",
                        quote=chunk_quote,
                        confidence=0.77,
                    ),
                    "subtype_application_requirement_completeness",
                )

        passive_requirement_match = _PASSIVE_REQUIREMENT_RE.search(chunk) or _PASSIVE_REQUIREMENT_RE.search(analysis_chunk)
        if passive_requirement_match:
            object_uk = _clip_text(passive_requirement_match.group("object").strip(" .;:"), 220)
            if object_uk:
                _append_candidate(
                    _build_candidate(
                        subject_uk="заявник",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"заявник {passive_requirement_match.group('lemma').strip().lower()} {object_uk}",
                        quote=chunk_quote,
                        confidence=0.79,
                    ),
                    "subtype_application_requirement_passive",
                )

    for item in _iter_list_items(cleaned):
        bullet_match = _APPLICATION_BULLET_RE.match(item)
        if not bullet_match:
            continue
        lemma = bullet_match.group("lemma").strip().lower()
        object_uk = _clip_text(bullet_match.group("object").strip(" .;:"), 220)
        _append_candidate(
            _build_candidate(
                subject_uk="заявник",
                predicate="requires",
                object_uk=object_uk or "виконати вимогу форми",
                norm_type="obligation",
                fact_text=f"заявник {lemma} {object_uk or 'виконати вимогу форми'}",
                quote=quote,
                confidence=0.83,
            ),
            "subtype_application_bullet_requirement",
        )
    condition_match = _APPLICATION_CONDITION_RE.search(_combine_with_context(cleaned, context_prefix))
    if condition_match:
        _append_candidate(
            _build_candidate(
                subject_uk="заявник",
                predicate="applies_to",
                object_uk=_clip_text(condition_match.group(1).strip(" .;:"), 220),
                norm_type="condition",
                fact_text=f"Застосовується умова: {condition_match.group(1).strip(' .;:')}",
                quote=quote,
                confidence=0.8,
            ),
            "subtype_application_condition",
        )

    # Broader obligation patterns for application forms
    if not candidates:
        analysis_text = _combine_with_context(cleaned, context_prefix)
        require_match = _SUBJECT_REQUIRE_RE.search(analysis_text)
        if require_match:
            raw_subject = require_match.group("subject").strip(" ,;:")
            raw_object = require_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 140)
            object_uk = _clip_text(raw_object, 220)
            if subject_uk and object_uk:
                _append_candidate(
                    _build_candidate(
                        subject_uk=subject_uk or "заявник",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"{subject_uk or 'заявник'} {require_match.group('lemma').strip()} {raw_object}",
                        quote=quote,
                        confidence=0.8,
                    ),
                    "subtype_application_requirement_obligation",
                )
        # Passive: "передбачається/вимагається..."
        passive_match = _PASSIVE_PROCEDURE_RE.search(analysis_text)
        if passive_match and not candidates:
            raw_subject = passive_match.group("subject").strip(" ,;:")
            raw_object = passive_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 140)
            object_uk = _clip_text(raw_object, 220)
            if subject_uk and object_uk:
                _append_candidate(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"{subject_uk} {passive_match.group('lemma').strip()} {object_uk}",
                        quote=quote,
                        confidence=0.76,
                    ),
                    "subtype_application_requirement_passive",
                )

    return candidates, reason_codes
