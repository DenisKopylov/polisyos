"""Deterministic SPO extractor used before LLM routing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.legal.batch.canonicalizers import (
    canonicalize_action,
    canonicalize_norm_type,
    extract_thresholds_from_text,
)
from polisyos.data_forge.domains.legal.batch.patterns import (
    AMENDMENT_CORE_RE,
    THRESHOLD_CORE_RE,
    TREATY_TITLE_RE,
)
from polisyos.data_forge.domains.legal.batch.quality_filters import (
    has_explicit_threshold_cue,
    is_synthetic_subject,
    is_threshold_noise_context,
)
from polisyos.data_forge.domains.legal.contracts import SPOCandidate, ThresholdAtom

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


@dataclass(frozen=True)
class DeterministicExtraction:
    """Result of deterministic extraction for one provision."""

    candidates: list[SPOCandidate]
    confidence: float
    reason_codes: list[str]


_ENTRY_INTO_FORCE_RE = re.compile(
    r"(?:набирає|набуває)\s+чинності?\s*(.{0,160})",
    re.IGNORECASE,
)
_REPEAL_RE = re.compile(
    r"визнати\s+(?:таки(?:м|ми)\s*,?\s*що\s*втратил(?:и|а|о)\s+чинність|такими\s*що\s*втратили\s+чинність)\s*(.{0,240})",
    re.IGNORECASE,
)
_AMEND_RE = AMENDMENT_CORE_RE
_APPROVE_RE = re.compile(
    r"(?:затвердити|схвалити|ухвалити|прийняти)\s+(.{8,180})",
    re.IGNORECASE,
)
_REQUIRE_RE = re.compile(
    r"(?:повинен|повинна|повинні|зобов[’'`ʼ]яз(?:аний|ана|ати|атися)?|має\s+забезпечити|необхідно)",
    re.IGNORECASE,
)
_PROHIBIT_RE = re.compile(
    r"(?:забороняється|заборонено|не\s+має\s+права|не\s+допускається)",
    re.IGNORECASE,
)
_DELEGATE_RE = re.compile(
    r"(?:доручити|уповноважити|покласти\s+на)",
    re.IGNORECASE,
)
_PERCENT_OR_NUMBER_RE = THRESHOLD_CORE_RE

# Enhanced extractors: capture actual object for prohibit/require
_PROHIBIT_OBJECT_RE = re.compile(
    r"(?:забороня(?:ється|ти|ється)|заборонено|не\s+допускається|не\s+має\s+права)\s+(.{5,250}?)(?:\.|;|,\s*крім)",
    re.IGNORECASE,
)
_REQUIRE_OBJECT_RE = re.compile(
    r"(?:повинен|повинна|повинні|зобов[''`ʼ]яз(?:аний|ана|ані))\s+(.{5,250}?)(?:\.|;)",
    re.IGNORECASE,
)

# Citation amendment: "статтю N викласти/замінити/доповнити"
_AMEND_CITATION_RE = re.compile(
    r"(?:статтю|пункт|частину|абзац)\s+(\d+(?:\.\d+)?)\s+(?:викласти|замінити|доповнити|виключити)",
    re.IGNORECASE,
)

# Numbered list items: "1) something; 2) something;"
_LIST_ITEM_RE = re.compile(r"^\s*\d+\)\s+(.+?)(?:;\s*$|$)", re.MULTILINE)
_ARTICLE_PREFIX_RE = re.compile(
    r"^\s*(?:стаття|article)\s+[\dIVXLCА-Яа-яіїєґ.\-]+\s*[.)]?\s*",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯІЇЄҐ])")
_CLAUSE_SPLIT_RE = re.compile(r"\s*;\s+|\s*:\s+(?=[A-ZА-ЯІЇЄҐ])")
_INLINE_SUBCLAUSE_SPLIT_RE = re.compile(r"\s+(?=\d+\.\d+\.\s+)")
_ADVERSATIVE_CLAUSE_SPLIT_RE = re.compile(
    r"\s*,\s+(?=(?:а|але)\s+[^,]{2,180}\s+"
    r"(?:покрива(?:ється|ються)|віднос(?:иться|яться)|можна|необхідно|потрібно|слід|"
    r"повинен|повинна|повинні|має|мають|не\s+має|не\s+мають|зобов))",
    re.IGNORECASE,
)
_RIGHT_RE = re.compile(
    r"(?P<subject>[^.]{2,180}?)\s+ма(?:є|ють)\s+право\s+(?P<object>[^.]{4,260})",
    re.IGNORECASE,
)
_RIGHTS_LIST_RE = re.compile(
    r"(?P<subject>[^.]{2,180}?)\s+ма(?:є|ють)\s+право\s*:\s*(?P<object>.+)",
    re.IGNORECASE | re.DOTALL,
)
_GUARANTEE_RE = re.compile(
    r"(?:(?P<subject>[^.]{2,120}?)\s+)?гаранту(?:ється|ються)\s+(?P<object>[^.]{4,260})",
    re.IGNORECASE,
)
_TREATY_TITLE_RE = TREATY_TITLE_RE
_RESOLUTION_TITLE_RE = re.compile(r"(указ|постанова|розпорядження|рішення)", re.IGNORECASE)
_TREATY_OBLIGATION_RE = re.compile(
    r"(?P<subject>(?:(?:кожна|будь-яка)\s+(?:договірна\s+)?сторона|договірні\s+сторони)[^.]{0,80}?)\s+"
    r"(?:(?:зобов['’`ʼ]язується|зобов['’`ʼ]язуються|повинна|повинні|має|мають))\s+"
    r"(?P<object>[^.]{6,280})",
    re.IGNORECASE,
)
_TREATY_COOPERATION_RE = re.compile(
    r"(?:співробітництво|взаємодія)\s+(?:здійснюється|провадиться|забезпечується)\s+(?P<object>[^.]{6,220})",
    re.IGNORECASE,
)
_TREATY_FUTURE_COOPERATION_RE = re.compile(
    r"(?P<subject>(?:договірні\s+сторони|кожна\s+договірна\s+сторона|сторони))\s+"
    r"(?:будуть\s+)?(?P<lemma>здійснювати|розвивати|сприяти|забезпечувати)\s+"
    r"(?P<object>[^.]{6,280})",
    re.IGNORECASE,
)
_TREATY_DELEGATION_RE = re.compile(
    r"(?P<subject>(?:договірні\s+сторони|сторони))\s+доручають\s+(?P<object>[^.]{6,280})",
    re.IGNORECASE,
)
_RATIFICATION_RE = re.compile(
    r"(?:ратифікувати|схвалити|затвердити)\s+(?P<object>[^.]{6,220})",
    re.IGNORECASE,
)
_IMPLEMENTATION_MANDATE_RE = re.compile(
    r"(?P<subject>[^.]{2,140}?)\s+(?:забезпечує|здійснює|організовує|подає|повідомляє)\s+(?P<object>[^.]{6,240})",
    re.IGNORECASE,
)
_IMPERATIVE_MANDATE_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>надіслати|підготувати|забезпечити|організувати|подати|повідомити|"
    r"розподілити|перерахувати|видати)\s+"
    r"(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_DEFINED_BY_LAW_RE = re.compile(
    r"(?P<object>[^.]{4,260}?)\s+визнача(?:ється|ються)\s+(?:лише\s+|виключно\s+)?законом",
    re.IGNORECASE,
)
_RECOGNIZED_AS_RE = re.compile(
    r"(?P<subject>[^.]{2,220}?)\s+визна(?:ється|ються)\s+(?P<object>[^.]{4,260})",
    re.IGNORECASE,
)
_EXISTS_RE = re.compile(
    r"(?:(?P<scope>в\s+україні)\s+)?існу(?:є|ють)\s+(?P<object>[^.]{4,220})",
    re.IGNORECASE,
)
_DECLARATIVE_IS_RE = re.compile(
    r"(?P<subject>[^.]{2,160}?)\s+є\s+(?P<object>[^.]{4,260})",
    re.IGNORECASE,
)
_DASH_DEFINITION_RE = re.compile(
    r"^(?P<subject>[^.\n]{2,120}?)\s+[-–—]\s+(?P<object>[^.\n]{4,220})",
    re.IGNORECASE,
)
_DASH_THIS_IS_RE = re.compile(
    r"^(?P<subject>[^.\n]{2,200}?)\s*[-–—]\s*це\s+(?P<object>[^.\n]{8,360})",
    re.IGNORECASE,
)
_LIST_DEFINITION_RE = re.compile(
    r"(?P<subject>[^.\n:]{2,180}?)\s+(?:є|становлять)\s*:\s*(?P<object>.+)",
    re.IGNORECASE | re.DOTALL,
)
_AMEND_WORDING_RE = re.compile(
    r"(?P<object>(?:(?:у|в)\s+(?:статті|частині|пункті|абзаці)\s+[^:;\n]{1,80}\s*:\s*)?"
    r"[^.]{0,260}?\b(?:замінити|доповнити|виключити)\s+слов(?:а|ами)[^.]{0,260})",
    re.IGNORECASE,
)
_PRINCIPLES_LIST_RE = re.compile(
    r"(?P<subject>[^.]{2,200}?)\s+(?:здійснюється|здійснюються|ґрунтується|ґрунтуються)\s+"
    r"(?:на\s+основі|за\s+принципами?)\s+(?:таких\s+)?(?:принципів|засад)\s*:\s*(?P<object>.+)",
    re.IGNORECASE | re.DOTALL,
)
_APPLIES_SCOPE_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+поширюється\s+на\s+"
    r"(?P<object>[^.;]{6,280}?)(?=(?:\s+(?:та|і)\s+встановлює)|[.;]|$)",
    re.IGNORECASE,
)
_ESTABLISHES_ORDER_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+встановлює\s+(?P<object>порядок[^.;]{4,260})",
    re.IGNORECASE,
)
_SUBJECT_REQUIRE_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>повинен|повинна|повинні|зобов['’`ʼ]язан(?:ий|а|і)?|зобов['’`ʼ]язується|"
    r"зобов['’`ʼ]язуються|має\s+забезпечити|мають\s+забезпечити|забезпечує|забезпечують)\s+"
    r"(?P<object>[^.;]{6,280})",
    re.IGNORECASE,
)
_SUBJECT_PROHIBIT_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>не\s+має\s+права|не\s+мають\s+права|не\s+допускається|не\s+допускаються|"
    r"забороняється|забороняються|не\s+може|не\s+можуть)\s+"
    r"(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_SUBJECT_PERMISSION_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>має\s+(?:пріоритетне\s+)?право|мають\s+(?:пріоритетне\s+)?право|може|можуть|вправі)\s+"
    r"(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_TEMPORAL_APPLICABILITY_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>застосовується|застосовуються|діє|діють|набирає\s+чинності|набирають\s+чинності)\s+"
    r"(?P<object>[^.;]{6,220})",
    re.IGNORECASE,
)
_SANCTION_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>тягне\s+за\s+собою|карається|штрафується)\s+"
    r"(?P<object>[^.;]{6,220})",
    re.IGNORECASE,
)
_EXCEPTION_RE = re.compile(
    r"(?:крім\s+випадків|якщо\s+інше\s+не\s+передбачено)\s+(?P<object>[^.;]{6,220})",
    re.IGNORECASE,
)
_PASSIVE_PROCEDURE_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>проводиться|проводяться|здійснюється|здійснюються|розраховується|розраховуються|"
    r"відноситься|відносяться|покривається|покриваються|вважається|вважаються)\s+"
    r"(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_PASSIVE_MANDATORY_ACTION_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>повин(?:но|ен|на|ні)\s+бути\s+"
    r"(?:виконан(?:о|а|і)|подан(?:о|а|і)|здійснен(?:о|а|і)|затверджен(?:о|а|і)|"
    r"переоформлен(?:о|а|і)|підготовлен(?:о|а|і)))\s+"
    r"(?P<object>[^.;]{4,260})",
    re.IGNORECASE,
)
_SUBJECT_TO_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+підляга(?:є|ють)\s+(?P<object>[^.;]{6,240})",
    re.IGNORECASE,
)
_DEONTIC_MARKER_RE = re.compile(
    r"(повинен|повинна|повинні|зобов|заборон|не допускається|не може бути|має право|гарантується|гарантуються)",
    re.IGNORECASE,
)
_CONSTITUTIONAL_TITLE_RE = re.compile(r"конституц", re.IGNORECASE)
_CODE_TITLE_RE = re.compile(r"кодекс", re.IGNORECASE)
_BASIC_LAW_TITLE_RE = re.compile(r"основи\s+законодавства", re.IGNORECASE)
_APPROVAL_BUNDLE_RE = re.compile(
    r"(?P<lemma>затвердити|затверджено|затверджений|затверджена|схвалити|схвалено|погодити|погоджено|доручити)\s+(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_ANNEX_RE = re.compile(r"(додат(?:ок|ки)\s*(?:N|№)?\s*[\w\-]*)", re.IGNORECASE)
_THRESHOLD_ROW_RE = re.compile(
    r"^(?P<subject>[^\n.;]{2,160}?)\s{2,}(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>%|грн|коп|рок(?:ів|и)?|дн(?:ів|і)?|місяц(?:ів|і)?|кг|тонн(?:и)?)\b",
    re.IGNORECASE,
)
_UNITLESS_THRESHOLD_ROW_RE = re.compile(
    r"^(?P<subject>[^\n.;:]{2,180}?)\s{1,}(?P<value>\d+(?:[.,]\d+)?(?:\s*-\s*\d+(?:[.,]\d+)?)?)\s*$",
    re.IGNORECASE,
)
_MULTIVALUE_THRESHOLD_ROW_RE = re.compile(
    r"^(?P<subject>[^\d\n.;]{2,180}?)\s+(?P<values>\d+(?:[.,]\d+)?(?:\s+\d+(?:[.,]\d+)?){1,})(?:\s*(?P<unit>%|грн|коп|тис\.?(?:куб\.?\s*метрів)?|га|кг|тонн(?:и)?)\b)?",
    re.IGNORECASE,
)
_CONDITION_THRESHOLD_RE = re.compile(
    r"(?P<lemma>не\s+менш(?:е| як)|не\s+більш(?:е| як)|не\s+нижче|не\s+вище)\s+"
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>%|грн|коп|кг|км|га|тонн(?:и)?|"
    r"рок(?:ів|и)?|місяц(?:ів|і)?|дн(?:ів|і)?|годин(?:и)?)",
    re.IGNORECASE,
)
_SALARY_TABLE_RE = re.compile(
    r"(посадов(?:ий|ого)\s+оклад|окладів|оплат[аи]\s+праці|ставка|тариф|гривень|грн\b)",
    re.IGNORECASE,
)
_APPLICANT_ACTION_RE = re.compile(
    r"(?:(?P<subject>заявник|заявники|суб['’`ʼ]єкт(?:\s+господарювання)?)\s+)?"
    r"(?P<lemma>подає|подати|подати\s+до|надати|надає|повідомити|повідомляє|дода(?:ти|є)|зобов['’`ʼ]язується)\s+"
    r"(?P<object>[^.;]{5,260})",
    re.IGNORECASE,
)
_APPLICATION_CONDITION_RE = re.compile(
    r"(за\s+умови\s+[^.;]{6,220}|у\s+разі\s+[^.;]{6,220}|за\s+наявності\s+[^.;]{6,220})",
    re.IGNORECASE,
)
_APPLICATION_BULLET_RE = re.compile(
    r"^\s*(?:[-\u2013\u2014\u2022]|\d+[.)])?\s*"
    r"(?P<lemma>виконувати|забезпечувати|сплатити|сплачувати|подати|подавати|надати|надавати|"
    r"повідомити|повідомляти|дотримуватися|зберігати|здійснювати|використовувати|"
    r"одержати|одержувати)\s+"
    r"(?P<object>[^.;]{4,240})",
    re.IGNORECASE,
)
_APPLICATION_LEAD_RE = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?:заявник|заявники|заява|заяви|до\s+заяви|подається|подаються|"
    r"надається|надаються|додається|додаються|можна\s+подати|необхідно\s+(?:подати|надати|"
    r"вказати|зазначити)|слід\s+(?:подати|надати|зазначити))\b",
    re.IGNORECASE,
)
_APPLICATION_IMPERSONAL_REQUIRE_RE = re.compile(
    r"(?P<lemma>необхідно|потрібно|слід)\s+"
    r"(?P<object>(?:подати|надати|вказати|зазначити|пояснити|додати|підтвердити|"
    r"дотримуватися|сплатити|розкрити)[^.]{3,260})",
    re.IGNORECASE,
)
_APPLICATION_IMPERSONAL_PERMISSION_RE = re.compile(
    r"(?P<lemma>можна)\s+"
    r"(?P<object>(?:подати|подавати|надати|надавати|посилатись|посилатися|"
    r"зазначити|додати)[^.]{3,260})",
    re.IGNORECASE,
)
_APPLICATION_COMPLETENESS_RE = re.compile(
    r"(?P<subject>комплект\s+документів|заява)\s+[^.]{0,120}?"
    r"(?P<lemma>вважа(?:ється|тиметься|тимуться|тись))\s+"
    r"(?P<object>[^.]{4,220})",
    re.IGNORECASE,
)
_FORM_SECTION_HEADER_RE = re.compile(
    r"^(?:вимоги\s+щодо|порядок\s+подання|перелік\s+документів|комплект\s+документів|"
    r"інформація\s+щодо|дані\s+про|відомості\s+про)\b",
    re.IGNORECASE,
)
_FORM_FIELD_LABEL_RE = re.compile(
    r"^(?:\(?[а-яіїєґa-z0-9]+\)?\s*[-–—.:])|(?:[А-ЯІЇЄҐA-Z][^.:]{1,80}:\s*)$",
    re.IGNORECASE,
)
_FORM_SCAFFOLD_LINE_RE = re.compile(
    r"(?:_{4,}|потрібне\s+підкреслити|непотрібне\s+закреслити|вноситься\s+потрібне|"
    r"телефон|телефакс|телекс|м\.\s*п\.|печатка|підпис|дата\s+заповнення|"
    r"ідентифікаційний\s+код|сума\s+літерами|призначення\s+платежу|рах\.\s*n)",
    re.IGNORECASE,
)
_FORM_CHECKBOX_RE = re.compile(r"(?:\[[ xX]?\]|\([ xX]?\)|□|☐)")
_FORM_CONTINUATION_RE = re.compile(
    r"^(?:та|і|або|а\s+також|зокрема|у\s+разі|за\s+умови|за\s+наявності|"
    r"який|яка|яке|які|що|для|з\s+метою|відповідно\s+до|згідно\s+з)\b",
    re.IGNORECASE,
)
_PASSIVE_REQUIREMENT_RE = re.compile(
    r"(?P<lemma>передбачається|вимагається|зазначається|подається|надається|додається)\s+"
    r"(?P<object>[^.;]{4,260})",
    re.IGNORECASE,
)
_APPLICATION_SUBJECT_PERMISSION_RE = re.compile(
    r"(?P<subject>заява|заявник|документ(?:и)?|інформація|повідомлення|"
    r"пояснення|підтвердження)\s+"
    r"(?P<lemma>може|можуть|має\s+право|мають\s+право)\s+"
    r"(?P<object>[^.;]{4,260})",
    re.IGNORECASE,
)
_FORM_LABEL_ONLY_RE = re.compile(
    r"^(?:назва|інформація\s+про|прізвище|ім['’`ʼ]я|по\s+батькові|"
    r"місце(?:\s+здійснення)?|участь|наявність|вид\s+діяльності|"
    r"ідентифікаційний\s+код|адреса|телефон|дата|контактна\s+особа)\b",
    re.IGNORECASE,
)
_MANDATORY_EXECUTION_RE = re.compile(
    r"(?P<subject>[^.;:]{2,220}?)\s+є\s+обов['’`ʼ]язков(?:им|ими)\s+для\s+виконання\s+(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_COMPETENCE_LIST_RE = re.compile(
    r"до\s+компетенції\s+(?P<subject>[^:.;]{4,180})\s+належ(?:ить|ать)\s*:\s*(?P<object>.+)",
    re.IGNORECASE | re.DOTALL,
)
_PERMISSION_CONDITION_RE = re.compile(
    r"(?P<object>[^.;]{6,220}?)\s+за\s+умови\s+(?P<condition>[^.;]{6,180})",
    re.IGNORECASE,
)
_TAIL_PERMISSION_RE = re.compile(
    r"(?:^|[.;]\s*)(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>може|можуть|має\s+(?:пріоритетне\s+)?право|мають\s+(?:пріоритетне\s+)?право|вправі)\s+"
    r"(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_TAIL_PROHIBITION_RE = re.compile(
    r"(?:^|[.;]\s*)(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>не\s+може|не\s+можуть|не\s+має\s+права|не\s+мають\s+права|"
    r"забороняється|забороняються)\s+"
    r"(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_TAIL_THRESHOLD_POLICY_RE = re.compile(
    r"(?P<object>(?:розмір|мінімальн(?:і|ий|а)\s+ставк(?:и|а)|максимальн(?:і|ий|а)\s+ставк(?:и|а)|"
    r"мінімальн(?:ий|а)\s+поріг|максимальн(?:ий|а)\s+поріг)[^.]{0,220}?"
    r"(?:встановлюється|встановлюються|можуть\s+установлюватися|може\s+установлюватися|"
    r"визначається|визначаються|індексації))",
    re.IGNORECASE,
)
_USES_RIGHTS_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+користу(?:ється|ються)\s+(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_NO_LIABILITY_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+не\s+несе\s+відповідальності\s+за\s+(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_CONTEXT_REMOVE_LIST_RE = re.compile(
    r"(виключаються\s+з\s+переліку|виключити\s+з\s+переліку|виключаються|виключено|"
    r"вилучаються|вилучити|визнати\s+(?:таким|такими).+?чинність)",
    re.IGNORECASE,
)
_CONTEXT_ADD_LIST_RE = re.compile(
    r"(включаються\s+до\s+переліку|включити\s+до\s+переліку|додаються\s+до\s+переліку|"
    r"доповнити\s+перелік|доповнюється\s+перелік)",
    re.IGNORECASE,
)
_CONTEXT_APPROVAL_RE = re.compile(
    r"(затвердити|затверджено|схвалити|схвалено|погодити|погоджено).+"
    r"(перелік|список|додат(?:ок|ки)|положення|порядок|правила|програм)",
    re.IGNORECASE,
)
_TREATY_USES_RE = re.compile(
    r"(?P<subject>[^.;:]{2,200}?)\s+використовує\s+(?P<object>[^.;]{8,320})",
    re.IGNORECASE,
)
_TREATY_DEFINED_BY_SIDE_RE = re.compile(
    r"(?P<object>порядок\s+[^.;]{6,240}?)\s+визначається\s+(?P<subject>[^.;]{4,140}?стороною)",
    re.IGNORECASE,
)
_TREATY_TEMPORAL_RE = re.compile(
    r"(на\s+умовах\s+та\s+протягом\s+строку\s+дії\s+[^.;]{4,220}|"
    r"протягом\s+строку\s+дії\s+[^.;]{4,220})",
    re.IGNORECASE,
)
_SEMANTIC_TAIL_MARKER_RE = re.compile(
    r"\b("
    r"може|можуть|не\s+може|не\s+можуть|має\s+право|мають\s+право|"
    r"крім|за\s+винятком|у\s+цьому\s+разі|при\s+цьому|а\s+також|зокрема|"
    r"розмір|мінімальн(?:і|ий|а)\s+ставк(?:и|а)|максимальн(?:і|ий|а)\s+ставк(?:и|а)|"
    r"користується|не\s+несе\s+відповідальності"
    r")\b",
    re.IGNORECASE,
)


def _build_candidate(
    *,
    subject_uk: str,
    predicate: str,
    object_uk: str,
    norm_type: str,
    fact_text: str,
    quote: str,
    confidence: float,
    thresholds_text: str | None = None,
) -> SPOCandidate:
    action_canon, _ = canonicalize_action(predicate)
    norm_canon, _ = canonicalize_norm_type(norm_type)
    thresholds = extract_thresholds_from_text(thresholds_text or quote, applies_to=object_uk)
    return SPOCandidate.model_validate(
        {
            "subject_en": subject_uk,
            "subject_uk": subject_uk,
            "predicate": predicate,
            "object_en": object_uk,
            "object_uk": object_uk,
            "fact_text": fact_text,
            "confidence": max(0.0, min(1.0, confidence)),
            "norm_type": norm_type,
            "action_raw": predicate,
            "action_canon": action_canon,
            "norm_type_raw": norm_type,
            "norm_type_canon": norm_canon,
            "source_quote_uk": quote[:500],
            "thresholds": [threshold.model_dump(mode="json") for threshold in thresholds],
        }
    )


def _clip_text(text: str, size: int = 220) -> str:
    chunk = " ".join(text.strip().split())
    if len(chunk) <= size:
        return chunk
    return f"{chunk[: size - 1]}…"


def _filtered_thresholds(
    *,
    text: str,
    applies_to: str,
) -> list[ThresholdAtom]:
    thresholds = extract_thresholds_from_text(text, applies_to=applies_to)
    explicit_cue = has_explicit_threshold_cue(text)
    if is_threshold_noise_context(text) and not explicit_cue:
        return []
    filtered: list[ThresholdAtom] = []
    for threshold in thresholds:
        unit = str(getattr(threshold, "unit", "") or "").strip().lower()
        if unit == "year" and not explicit_cue:
            continue
        filtered.append(threshold)
    return filtered


def _strip_article_prefix(text: str) -> str:
    return _ARTICLE_PREFIX_RE.sub("", text.strip(), count=1)


def _iter_sentences(text: str, *, split_newlines: bool = False) -> Iterable[str]:
    stripped = _strip_article_prefix(text)
    # For threshold/table provisions, newlines separate distinct rows
    if split_newlines:
        for line in stripped.split("\n"):
            line = line.strip()
            if line:
                yield line
        return
    parts = [part.strip() for part in _SENTENCE_SPLIT_RE.split(stripped) if part.strip()]
    if not parts:
        yield stripped
        return
    for part in parts:
        subparts = [
            chunk.strip() for chunk in _INLINE_SUBCLAUSE_SPLIT_RE.split(part) if chunk.strip()
        ]
        if not subparts:
            yield part
            continue
        yield from subparts


def _iter_semantic_clauses(text: str) -> Iterable[str]:
    emitted = False
    for clause in _CLAUSE_SPLIT_RE.split(text):
        for subclause in _ADVERSATIVE_CLAUSE_SPLIT_RE.split(clause):
            stripped = subclause.strip()
            if not stripped:
                continue
            emitted = True
            yield stripped
    if not emitted:
        yield text.strip()


def _iter_list_items(text: str) -> Iterable[str]:
    for raw in re.split(r"\s*;\s+|\s*\n+\s*", text):
        item = raw.strip(" -\u2013\u2014\u2022\t\r\n")
        if len(item) >= 4:
            yield item


def _iter_distinct_chunks(text: str) -> Iterable[str]:
    seen: set[str] = set()
    sources = [text]
    sources.extend(list(_iter_sentences(text)))
    for source in list(sources):
        sources.extend(list(_iter_semantic_clauses(source)))
    sources.extend(list(_iter_list_items(text)))
    sources.extend(
        part.strip() for part in re.split(r"(?=(?:\d+\.\d+|\d+[.)])\s+)", text) if part.strip()
    )
    for raw in sources:
        compact = " ".join(str(raw).split())
        if len(compact) < 8 or compact in seen:
            continue
        seen.add(compact)
        yield compact


def _combine_with_context(text: str, context_prefix: str = "") -> str:
    compact_text = " ".join(text.split()).strip()
    compact_context = " ".join(str(context_prefix or "").split()).strip()
    if not compact_context:
        return compact_text
    if compact_text.startswith(compact_context) or compact_context in compact_text:
        return compact_text
    return f"{compact_context}. {compact_text}".strip()


def _looks_like_form_scaffold_line(text: str) -> bool:
    compact = " ".join(text.split()).strip()
    if not compact:
        return True
    if _FORM_SCAFFOLD_LINE_RE.search(compact):
        return True
    return bool(_FORM_CHECKBOX_RE.search(compact) and len(compact) <= 64)


def _normalize_inherited_list_item(text: str) -> str:
    compact = " ".join(text.split()).strip()
    compact = re.sub(
        r"^(?:(?:[-\u2013\u2014\u2022\"'«»]+)|(?:\"\s*-\s*\")|(?:-\s*\"\s*-\s*\")|(?:-\s*\")|(?:\"\s*-\s*))+"
        r"\s*",
        "",
        compact,
    )
    compact = re.sub(r"^(?:[-\u2013\u2014\u2022]+\s*)+", "", compact)
    compact = re.sub(r"^[^0-9A-Za-zА-Яа-яІіЇїЄєҐґ]+", "", compact)
    compact = compact.strip(" \"'«»")
    return compact


def _looks_like_form_label(text: str) -> bool:
    compact = " ".join(text.split()).strip()
    if not compact or len(compact.split()) > 18:
        return False
    if compact.endswith((".", ";", ":")):
        return False
    return bool(_FORM_LABEL_ONLY_RE.match(compact))


def _iter_form_blocks(text: str, *, context_prefix: str = "") -> Iterable[tuple[str, str]]:
    section_context = " ".join(str(context_prefix or "").split()).strip()
    current: list[str] = []

    def _flush() -> tuple[str, str] | None:
        nonlocal current
        if not current:
            return None
        block_text = " ".join(part.strip() for part in current if part.strip()).strip()
        current = []
        if len(block_text) < 8:
            return None
        return (_combine_with_context(block_text, section_context), block_text)

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split()).strip()
        if not line:
            flushed = _flush()
            if flushed is not None:
                yield flushed
            continue
        if _looks_like_form_scaffold_line(line):
            flushed = _flush()
            if flushed is not None:
                yield flushed
            continue
        if _FORM_SECTION_HEADER_RE.match(line):
            flushed = _flush()
            if flushed is not None:
                yield flushed
            section_context = _combine_with_context(line, context_prefix)
            continue
        if not current:
            current.append(line)
            continue
        previous = current[-1]
        starts_new = bool(
            _APPLICATION_BULLET_RE.match(line)
            or _APPLICATION_LEAD_RE.match(line)
            or _FORM_FIELD_LABEL_RE.match(line)
            or _APPLICATION_IMPERSONAL_REQUIRE_RE.search(line)
            or _APPLICATION_IMPERSONAL_PERMISSION_RE.search(line)
        )
        continues = bool(
            _FORM_CONTINUATION_RE.match(line)
            or line[:1].islower()
            or line.startswith(("(", ",", ";"))
            or previous.endswith(":")
        )
        if starts_new and not continues:
            flushed = _flush()
            if flushed is not None:
                yield flushed
            current.append(line)
            continue
        current.append(line)

    flushed = _flush()
    if flushed is not None:
        yield flushed


def _iter_retry_chunks(text: str, *, quality_family: str, struct_kind: str) -> Iterable[str]:
    seen: set[str] = set()
    base_chunks: list[str] = []
    if quality_family in {"law", "treaty_protocol"}:
        base_chunks.extend(_iter_sentences(text))
    base_chunks.extend(_iter_semantic_clauses(text))
    if quality_family == "appendix_heavy" or struct_kind in {
        "paragraph",
        "enumeration_item",
        "table_row",
    }:
        base_chunks.extend(part.strip() for part in text.splitlines() if part.strip())
    for chunk in base_chunks:
        compact = " ".join(chunk.split())
        if len(compact) < 24 or compact in seen:
            continue
        seen.add(compact)
        yield compact


def _is_basic_article_context(*, doc_title: str, citation_label: str) -> bool:
    title = doc_title or ""
    citation = citation_label or ""
    return bool(
        _CONSTITUTIONAL_TITLE_RE.search(title)
        or _CODE_TITLE_RE.search(title)
        or _BASIC_LAW_TITLE_RE.search(title)
        or citation.lower().startswith("стаття")
    )


def _token_count(text: str) -> int:
    return len([part for part in text.split() if part])


def _is_compact_clause(*, subject: str, object_text: str, sentence: str) -> bool:
    object_lower = object_text.lower()
    if (
        any(marker in object_lower for marker in (", який", ", яка", ", яке", ", що", ";"))
        and _token_count(object_text) > 14
    ):
        return False
    return (
        len(sentence) <= 280
        and _token_count(sentence) <= 40
        and len(subject) <= 160
        and len(object_text) <= 180
        and _token_count(subject) <= 16
        and _token_count(object_text) <= 24
    )


from polisyos.data_forge.domains.legal.batch.deterministic_spo_articles import (
    _extract_structured_article_candidates,
    _extract_treaty_resolution_candidates,
)
from polisyos.data_forge.domains.legal.batch.deterministic_spo_core import (
    _extract_context_inherited_appendix_candidates,
    _extract_core_normative_fallback_candidates,
    _extract_semantic_tail_candidates,
)
from polisyos.data_forge.domains.legal.batch.deterministic_spo_subtypes import (
    _extract_amendment_bundle_candidates,
    _extract_application_requirement_candidates,
    _extract_approval_bundle_candidates,
    _extract_threshold_row_candidates,
)


def _needs_residual_clause_pass(
    *, text: str, legal_unit_subtype: str, candidate_count: int
) -> bool:
    if legal_unit_subtype not in {
        "core_normative_clause",
        "exception_clause",
        "temporal_clause",
        "approval_bundle",
        "amendment_bundle",
        "application_requirement",
    }:
        return False
    multi_clause_cues = text.count(";") + text.count("\n") + text.count(":")
    if multi_clause_cues > 0:
        return True
    if re.search(
        r",\s*(?:а\s+також|зокрема|при\s+цьому|у\s+разі|за\s+умови)\b", text, re.IGNORECASE
    ):
        return True
    return candidate_count <= 1 and len(text.split()) >= 18


def extract_deterministic_spo(
    *,
    text: str,
    citation_label: str,
    doc_title: str,
    legal_unit_subtype: str = "",
    legal_unit_micro_subtype: str = "",
    quality_family: str = "",
    reference_bearing: bool = False,
    threshold_bearing: bool = False,
    context_prefix: str = "",
    _enable_residual_pass: bool = True,
) -> DeterministicExtraction:
    """Extract high-confidence SPO candidates without LLM."""
    cleaned = text.strip()
    if not cleaned:
        return DeterministicExtraction(candidates=[], confidence=0.0, reason_codes=["empty"])

    reason_codes: list[str] = []
    candidates: list[SPOCandidate] = []
    subject = "орган, що прийняв акт"
    quote = _clip_text(cleaned, size=400)
    subtype = (legal_unit_subtype or "").strip().lower()
    lower_cleaned = cleaned.lower()
    if subtype in {
        "citation_only",
        "composition_list",
        "form_scaffold",
        "inventory_only",
        "registry_catalog_row",
        "table_scaffold",
    }:
        return DeterministicExtraction(
            candidates=[], confidence=0.0, reason_codes=[f"search_only_subtype:{subtype}"]
        )

    subtype_extractors: tuple[
        tuple[str, Callable[[], tuple[list[SPOCandidate], list[str]]]], ...
    ] = (
        (
            "amendment_bundle",
            lambda: _extract_amendment_bundle_candidates(text=cleaned, doc_title=doc_title),
        ),
        (
            "approval_bundle",
            lambda: _extract_approval_bundle_candidates(
                text=cleaned, doc_title=doc_title, context_prefix=context_prefix
            ),
        ),
        (
            "tariff_threshold_row",
            lambda: _extract_threshold_row_candidates(
                text=cleaned, doc_title=doc_title, context_prefix=context_prefix
            ),
        ),
        (
            "application_requirement",
            lambda: _extract_application_requirement_candidates(
                text=cleaned, context_prefix=context_prefix
            ),
        ),
        (
            "core_normative_clause",
            lambda: _extract_core_normative_fallback_candidates(
                text=cleaned,
                doc_title=doc_title,
                legal_unit_micro_subtype=legal_unit_micro_subtype,
                context_prefix=context_prefix,
                threshold_bearing=threshold_bearing,
            ),
        ),
    )
    for target_subtype, extractor in subtype_extractors:
        if subtype != target_subtype:
            continue
        subtype_candidates, subtype_reason_codes = extractor()
        if subtype_candidates:
            candidates.extend(subtype_candidates)
            reason_codes.extend(subtype_reason_codes)

    if subtype in {"amendment_bundle", "approval_bundle"} and context_prefix:
        inherited_candidates, inherited_reason_codes = (
            _extract_context_inherited_appendix_candidates(
                text=cleaned,
                context_prefix=context_prefix,
                doc_title=doc_title,
            )
        )
        if inherited_candidates:
            candidates.extend(inherited_candidates)
            reason_codes.extend(inherited_reason_codes)

    article_candidates, article_reason_codes = _extract_structured_article_candidates(
        text=cleaned,
        citation_label=citation_label,
        doc_title=doc_title,
    )
    if article_candidates:
        candidates.extend(article_candidates)
        reason_codes.extend(article_reason_codes)

    treaty_candidates, treaty_reason_codes = _extract_treaty_resolution_candidates(
        text=cleaned,
        citation_label=citation_label,
        doc_title=doc_title,
    )
    if treaty_candidates:
        candidates.extend(treaty_candidates)
        reason_codes.extend(treaty_reason_codes)

    entry_match = _ENTRY_INTO_FORCE_RE.search(cleaned)
    if entry_match:
        detail = (entry_match.group(1) or "").strip(" .")
        object_uk = detail or "з дня офіційного опублікування"
        candidates.append(
            _build_candidate(
                subject_uk="цей акт",
                predicate="enters_into_force",
                object_uk=object_uk,
                norm_type="entry_into_force",
                fact_text=f"Акт набирає чинності {object_uk}".strip(),
                quote=quote,
                confidence=0.9,
            )
        )
        reason_codes.append("entry_into_force_pattern")

    repeal_match = _REPEAL_RE.search(cleaned)
    if repeal_match:
        object_uk = (repeal_match.group(1) or "").strip(" .") or "визначені акти"
        candidates.append(
            _build_candidate(
                subject_uk=subject,
                predicate="repeals",
                object_uk=object_uk,
                norm_type="repeal",
                fact_text=f"Визнано такими, що втратили чинність: {object_uk}",
                quote=quote,
                confidence=0.9,
            )
        )
        reason_codes.append("repeal_pattern")

    if _AMEND_RE.search(cleaned):
        candidates.append(
            _build_candidate(
                subject_uk=subject,
                predicate="amends",
                object_uk=doc_title or "зазначений акт",
                norm_type="amendment",
                fact_text="Внесено зміни до акту",
                quote=quote,
                confidence=0.87,
            )
        )
        reason_codes.append("amendment_pattern")

    amend_wording_match = _AMEND_WORDING_RE.search(cleaned)
    if amend_wording_match:
        object_uk = _clip_text(amend_wording_match.group("object").strip(" .;:"), 220)
        candidates.append(
            _build_candidate(
                subject_uk=subject,
                predicate="amends",
                object_uk=object_uk or "словесне формулювання норми",
                norm_type="amendment",
                fact_text=f"Внесено словесну зміну: {object_uk or 'словесне формулювання норми'}",
                quote=quote,
                confidence=0.84,
            )
        )
        reason_codes.append("amend_wording_pattern")

    approve_match = _APPROVE_RE.search(cleaned)
    if approve_match:
        object_uk = (approve_match.group(1) or "").strip(" .")
        candidates.append(
            _build_candidate(
                subject_uk=subject,
                predicate="approves",
                object_uk=object_uk or "доданий документ",
                norm_type="procedure",
                fact_text=f"Затверджено: {object_uk or 'доданий документ'}",
                quote=quote,
                confidence=0.86,
            )
        )
        reason_codes.append("approval_pattern")

    threshold_analysis_text = _combine_with_context(cleaned, context_prefix)
    thresholds = _filtered_thresholds(
        text=threshold_analysis_text,
        applies_to=doc_title or "цей акт",
    )
    if (
        thresholds
        and quality_family == "treaty_protocol"
        and _TREATY_TEMPORAL_RE.search(cleaned)
        and not any(
            marker in lower_cleaned
            for marker in (
                "%",
                "грн",
                "коп",
                "кг",
                "км",
                "га",
                "тонн",
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
    ):
        thresholds = []
    threshold_explicit = has_explicit_threshold_cue(threshold_analysis_text)
    if thresholds and (
        threshold_bearing
        or subtype == "tariff_threshold_row"
        or (subtype in {"core_normative_clause", ""} and threshold_explicit)
    ):
        best = thresholds[0]
        threshold_desc = str(best.value_text or best.value_decimal or "числовий поріг").strip()
        threshold_subject = (
            subject if subject and not is_synthetic_subject(subject) else "регульований показник"
        )
        candidates.append(
            _build_candidate(
                subject_uk=threshold_subject,
                predicate="sets_threshold",
                object_uk=threshold_desc or "числовий поріг",
                norm_type="obligation",
                fact_text=f"{threshold_subject} має поріг {threshold_desc or 'числовий поріг'}",
                quote=quote,
                confidence=0.88,
                thresholds_text=_combine_with_context(cleaned, context_prefix),
            )
        )
        reason_codes.append("threshold_pattern")

    if _DELEGATE_RE.search(cleaned):
        candidates.append(
            _build_candidate(
                subject_uk=subject,
                predicate="delegates",
                object_uk="уповноважений орган",
                norm_type="delegation",
                fact_text="Повноваження делеговано уповноваженому органу",
                quote=quote,
                confidence=0.78,
            )
        )
        reason_codes.append("delegate_pattern")

    if _PROHIBIT_RE.search(cleaned):
        # Try to extract the actual prohibited action
        prohibit_obj_match = _PROHIBIT_OBJECT_RE.search(cleaned)
        prohibit_obj = (
            prohibit_obj_match.group(1).strip() if prohibit_obj_match else "зазначена дія"
        )
        candidates.append(
            _build_candidate(
                subject_uk="суб'єкт правовідносин",
                predicate="prohibits",
                object_uk=prohibit_obj,
                norm_type="prohibition",
                fact_text=f"Забороняється: {_clip_text(prohibit_obj, 150)}",
                quote=quote,
                confidence=0.80 if prohibit_obj_match else 0.76,
            )
        )
        reason_codes.append("prohibit_pattern")

    if _REQUIRE_RE.search(cleaned):
        # Try to extract the actual requirement object
        require_obj_match = _REQUIRE_OBJECT_RE.search(cleaned)
        require_obj = (
            require_obj_match.group(1).strip() if require_obj_match else "виконання вимог норми"
        )
        candidates.append(
            _build_candidate(
                subject_uk="суб'єкт правовідносин",
                predicate="requires",
                object_uk=require_obj,
                norm_type="obligation",
                fact_text=f"Вимагається: {_clip_text(require_obj, 150)}",
                quote=quote,
                confidence=0.78 if require_obj_match else 0.74,
            )
        )
        reason_codes.append("require_pattern")

    global_rights_list_match = _RIGHTS_LIST_RE.search(cleaned)
    if global_rights_list_match and cleaned.count(";") >= 2:
        subject_uk = _clip_text(global_rights_list_match.group("subject").strip(" ,;:"), 140)
        for item in _iter_list_items(global_rights_list_match.group("object")):
            object_uk = _clip_text(f"має право {item.strip(' .;:')}", 220)
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk or "суб'єкт правовідносин",
                    predicate="grants",
                    object_uk=object_uk,
                    norm_type="permission",
                    fact_text=f"{subject_uk or 'субʼєкт'} має право {item.strip(' .;:')}",
                    quote=quote,
                    confidence=0.82,
                )
            )
        reason_codes.append("rights_list_pattern")

    passive_procedure_match = _PASSIVE_PROCEDURE_RE.search(cleaned)
    if passive_procedure_match:
        subject_uk = _clip_text(passive_procedure_match.group("subject").strip(" ,;:"), 160)
        object_uk = _clip_text(passive_procedure_match.group("object").strip(" .;:"), 220)
        if (
            subject_uk
            and object_uk
            and not _PRINCIPLES_LIST_RE.search(cleaned)
            and not _RIGHTS_LIST_RE.search(cleaned)
        ):
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk,
                    predicate="applies_to",
                    object_uk=object_uk,
                    norm_type="procedure",
                    fact_text=f"{subject_uk} {passive_procedure_match.group('lemma').strip()} {object_uk}",
                    quote=quote,
                    confidence=0.8,
                )
            )
            reason_codes.append("passive_procedure_pattern")

    subject_to_match = _SUBJECT_TO_RE.search(cleaned)
    if subject_to_match:
        subject_uk = _clip_text(subject_to_match.group("subject").strip(" ,;:"), 160)
        object_uk = _clip_text(subject_to_match.group("object").strip(" .;:"), 220)
        if subject_uk and object_uk:
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk,
                    predicate="applies_to",
                    object_uk=object_uk,
                    norm_type="applicability",
                    fact_text=f"{subject_uk} підлягає {object_uk}",
                    quote=quote,
                    confidence=0.79,
                )
            )
            reason_codes.append("subject_to_pattern")

    applies_scope_match = _APPLIES_SCOPE_RE.search(cleaned)
    if applies_scope_match:
        subject_uk = _clip_text(applies_scope_match.group("subject").strip(" ,;:"), 160)
        object_uk = _clip_text(applies_scope_match.group("object").strip(" .;:"), 220)
        if subject_uk and object_uk:
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk,
                    predicate="applies_to",
                    object_uk=object_uk,
                    norm_type="applicability",
                    fact_text=f"{subject_uk} поширюється на {object_uk}",
                    quote=quote,
                    confidence=0.8,
                )
            )
            reason_codes.append("applies_scope_pattern")

    establishes_order_match = _ESTABLISHES_ORDER_RE.search(cleaned)
    if establishes_order_match:
        subject_uk = _clip_text(establishes_order_match.group("subject").strip(" ,;:"), 160)
        object_uk = _clip_text(establishes_order_match.group("object").strip(" .;:"), 220)
        if subject_uk and object_uk:
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk,
                    predicate="defines",
                    object_uk=object_uk,
                    norm_type="procedure",
                    fact_text=f"{subject_uk} встановлює {object_uk}",
                    quote=quote,
                    confidence=0.81,
                )
            )
            reason_codes.append("establishes_order_pattern")

    # Citation amendment: "статтю N викласти/замінити"
    amend_citation_match = _AMEND_CITATION_RE.search(cleaned)
    if amend_citation_match and not _AMEND_RE.search(cleaned):
        target_num = amend_citation_match.group(1)
        candidates.append(
            _build_candidate(
                subject_uk=subject,
                predicate="amends",
                object_uk=f"стаття/пункт {target_num} {doc_title or 'зазначеного акту'}",
                norm_type="amendment",
                fact_text=f"Внесено зміни до статті/пункту {target_num}",
                quote=quote,
                confidence=0.85,
            )
        )
        reason_codes.append("amend_citation_pattern")

    if (
        subtype
        in {
            "core_normative_clause",
            "application_requirement",
            "approval_bundle",
            "amendment_bundle",
            "exception_clause",
            "temporal_clause",
            "sanction_clause",
        }
        or quality_family in {"law", "appendix_heavy", "treaty_protocol"}
    ) and (len(cleaned.split()) >= 8 or _SEMANTIC_TAIL_MARKER_RE.search(cleaned) or context_prefix):
        tail_candidates, tail_reason_codes = _extract_semantic_tail_candidates(
            text=cleaned,
            doc_title=doc_title,
            context_prefix=context_prefix,
        )
        if tail_candidates:
            candidates.extend(tail_candidates)
            reason_codes.extend(tail_reason_codes)

    # Deduplicate near-identical facts by (predicate, fact_text).
    seen: set[tuple[str, str]] = set()
    deduped: list[SPOCandidate] = []
    for candidate in candidates:
        key = (candidate.predicate, candidate.fact_text)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    candidates = deduped

    if _enable_residual_pass and _needs_residual_clause_pass(
        text=cleaned,
        legal_unit_subtype=subtype,
        candidate_count=len(candidates),
    ):
        reason_codes.append("residual_clause_pass")
        residual_reason_codes: list[str] = []
        for chunk in _iter_distinct_chunks(cleaned):
            if chunk == cleaned or len(chunk) < 18:
                continue
            chunk_extraction = extract_deterministic_spo(
                text=chunk,
                citation_label=citation_label,
                doc_title=doc_title,
                legal_unit_subtype=legal_unit_subtype,
                legal_unit_micro_subtype=legal_unit_micro_subtype,
                quality_family=quality_family,
                reference_bearing=reference_bearing,
                threshold_bearing=threshold_bearing,
                context_prefix=context_prefix,
                _enable_residual_pass=False,
            )
            if not chunk_extraction.candidates:
                continue
            for candidate in chunk_extraction.candidates:
                key = (candidate.predicate, candidate.fact_text)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(candidate)
            residual_reason_codes.extend(chunk_extraction.reason_codes)
        if residual_reason_codes:
            reason_codes.extend(residual_reason_codes)

    if subtype == "citation_only" and not candidates:
        return DeterministicExtraction(
            candidates=[], confidence=0.0, reason_codes=["citation_only"]
        )

    if not candidates:
        return DeterministicExtraction(candidates=[], confidence=0.0, reason_codes=["no_match"])

    max_pattern_confidence = max(candidate.confidence for candidate in candidates)
    has_high_precision = any(
        code in reason_codes
        for code in (
            "entry_into_force_pattern",
            "repeal_pattern",
            "amendment_pattern",
            "approval_pattern",
            "amend_citation_pattern",
            "subtype_supersedes_bundle",
        )
    )
    has_article_semantics = any(
        code in reason_codes
        for code in (
            "article_right_pattern",
            "article_guarantee_pattern",
            "article_defined_by_law_pattern",
            "article_recognition_pattern",
            "article_existence_pattern",
            "article_declarative_pattern",
            "article_dash_definition_pattern",
            "article_dash_this_is_pattern",
            "article_list_definition_pattern",
            "article_principles_list_pattern",
            "article_rights_list_pattern",
            "article_amend_wording_pattern",
            "article_subject_requirement_pattern",
            "article_mandatory_execution_pattern",
            "article_subject_prohibition_pattern",
            "article_subject_permission_pattern",
            "article_permission_condition_pattern",
            "article_temporal_applicability_pattern",
            "article_sanction_pattern",
            "article_exception_pattern",
            "article_competence_list_pattern",
            "treaty_obligation_pattern",
            "treaty_cooperation_pattern",
            "ratification_pattern",
            "resolution_mandate_pattern",
            "resolution_imperative_mandate_pattern",
            "treaty_future_cooperation_pattern",
            "treaty_delegation_pattern",
            "rights_list_pattern",
            "passive_procedure_pattern",
            "subject_to_pattern",
            "applies_scope_pattern",
            "establishes_order_pattern",
            "cnc_fallback_requirement_pattern",
            "cnc_fallback_prohibition_pattern",
            "cnc_fallback_permission_pattern",
            "cnc_fallback_passive_procedure_pattern",
            "cnc_fallback_subject_to_pattern",
            "cnc_fallback_scope_pattern",
            "cnc_fallback_establishes_order_pattern",
            "cnc_fallback_dash_definition_pattern",
            "cnc_fallback_dash_this_is_pattern",
        )
    )
    has_threshold = (
        "threshold_pattern" in reason_codes
        or "subtype_threshold_row" in reason_codes
        or "subtype_threshold_multivalue_row" in reason_codes
        or "subtype_threshold_fallback" in reason_codes
        or threshold_bearing
        or bool(_PERCENT_OR_NUMBER_RE.search(cleaned))
    )
    fallback_like = "повний текст" in citation_label.lower()
    constitutional_doc = bool(_CONSTITUTIONAL_TITLE_RE.search(doc_title or ""))
    confidence = 0.45
    if has_high_precision:
        confidence += 0.25
    if has_article_semantics:
        confidence += 0.18 if constitutional_doc else 0.10
    if has_threshold:
        confidence += 0.15
    if len(candidates) >= 2:
        confidence += 0.08
    if not fallback_like:
        confidence += 0.07
    confidence = max(confidence, max_pattern_confidence)
    if constitutional_doc and has_article_semantics:
        confidence = max(confidence, 0.87)
    if subtype in {
        "amendment_bundle",
        "approval_bundle",
        "tariff_threshold_row",
        "application_requirement",
    }:
        confidence = max(confidence, 0.84)
    if reference_bearing and subtype in {"amendment_bundle", "approval_bundle"}:
        confidence = max(confidence, 0.87)
    if quality_family == "appendix_heavy" and subtype in {
        "application_requirement",
        "tariff_threshold_row",
    }:
        confidence = max(confidence, 0.85)
    confidence = min(0.95, confidence)

    normalized_candidates = [
        candidate.model_copy(update={"confidence": confidence}) for candidate in candidates
    ]
    return DeterministicExtraction(
        candidates=normalized_candidates,
        confidence=confidence,
        reason_codes=sorted(set(reason_codes)),
    )


def extract_family_retry_spo(
    *,
    text: str,
    citation_label: str,
    doc_title: str,
    quality_family: str,
    struct_kind: str = "",
    legal_unit_subtype: str = "",
    legal_unit_micro_subtype: str = "",
    context_prefix: str = "",
) -> DeterministicExtraction:
    """Second-pass deterministic retry for law and appendix-heavy empty rows."""
    family = (quality_family or "").strip().lower()
    if family not in {"law", "appendix_heavy", "treaty_protocol"}:
        return DeterministicExtraction(
            candidates=[], confidence=0.0, reason_codes=["retry_not_applicable"]
        )

    merged_candidates: list[SPOCandidate] = []
    merged_reason_codes: list[str] = []
    seen_keys: set[tuple[str, str]] = set()

    for chunk in _iter_retry_chunks(text, quality_family=family, struct_kind=struct_kind):
        extraction = extract_deterministic_spo(
            text=chunk,
            citation_label=citation_label,
            doc_title=doc_title,
            legal_unit_subtype=legal_unit_subtype,
            legal_unit_micro_subtype=legal_unit_micro_subtype,
            quality_family=family,
            context_prefix=context_prefix,
        )
        if not extraction.candidates:
            continue
        for candidate in extraction.candidates:
            key = (candidate.predicate, candidate.fact_text)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged_candidates.append(candidate)
        merged_reason_codes.extend(extraction.reason_codes)

    if not merged_candidates:
        return DeterministicExtraction(
            candidates=[], confidence=0.0, reason_codes=["retry_no_match"]
        )

    confidence = min(0.9, max(candidate.confidence for candidate in merged_candidates))
    merged_candidates = [
        candidate.model_copy(update={"confidence": confidence}) for candidate in merged_candidates
    ]
    return DeterministicExtraction(
        candidates=merged_candidates,
        confidence=confidence,
        reason_codes=sorted({"retry_clause_split", *merged_reason_codes}),
    )
