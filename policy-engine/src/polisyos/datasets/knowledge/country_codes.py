"""Country normalization helpers shared across datasets pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CountryMapping:
    iso2: str
    iso3: str
    numeric: str
    name_en: str
    aliases: tuple[str, ...] = ()
    region: str = ""


_COUNTRIES: tuple[CountryMapping, ...] = (
    CountryMapping("UA", "UKR", "804", "Ukraine", ("Ukraina", "Ukrayina"), "Europe"),
    CountryMapping("DE", "DEU", "276", "Germany", ("Deutschland",), "Europe"),
    CountryMapping("PL", "POL", "616", "Poland", ("Polska",), "Europe"),
    CountryMapping("RO", "ROU", "642", "Romania", ("Romania", "Romania"), "Europe"),
    CountryMapping("MD", "MDA", "498", "Moldova", ("Republic of Moldova", "Moldova, Republic of"), "Europe"),
    CountryMapping("CZ", "CZE", "203", "Czechia", ("Czech Republic", "Cesko"), "Europe"),
    CountryMapping("SK", "SVK", "703", "Slovakia", ("Slovak Republic", "Slovensko"), "Europe"),
    CountryMapping("HU", "HUN", "348", "Hungary", ("Magyarorszag",), "Europe"),
    CountryMapping("LT", "LTU", "440", "Lithuania", ("Lietuva",), "Europe"),
    CountryMapping("LV", "LVA", "428", "Latvia", ("Latvija",), "Europe"),
    CountryMapping("EE", "EST", "233", "Estonia", ("Eesti",), "Europe"),
    CountryMapping("GE", "GEO", "268", "Georgia", ("Sakartvelo",), "Europe"),
    CountryMapping("AM", "ARM", "051", "Armenia", ("Hayastan",), "Europe"),
    CountryMapping("AZ", "AZE", "031", "Azerbaijan", ("Azerbaijan Republic",), "Europe"),
    CountryMapping("KZ", "KAZ", "398", "Kazakhstan", ("Kazakhst an",), "Asia"),
    CountryMapping("UZ", "UZB", "860", "Uzbekistan", ("Uzbekiston",), "Asia"),
    CountryMapping("AT", "AUT", "040", "Austria", ("Osterreich",), "Europe"),
    CountryMapping("BE", "BEL", "056", "Belgium", ("Belgique", "Belgie"), "Europe"),
    CountryMapping("BG", "BGR", "100", "Bulgaria", ("Balgariya",), "Europe"),
    CountryMapping("HR", "HRV", "191", "Croatia", ("Hrvatska",), "Europe"),
    CountryMapping("CY", "CYP", "196", "Cyprus", (), "Europe"),
    CountryMapping("DK", "DNK", "208", "Denmark", ("Danmark",), "Europe"),
    CountryMapping("ES", "ESP", "724", "Spain", ("Espana",), "Europe"),
    CountryMapping("FI", "FIN", "246", "Finland", ("Suomi",), "Europe"),
    CountryMapping("FR", "FRA", "250", "France", (), "Europe"),
    CountryMapping("GR", "GRC", "300", "Greece", ("Hellas",), "Europe"),
    CountryMapping("IE", "IRL", "372", "Ireland", ("Eire",), "Europe"),
    CountryMapping("IT", "ITA", "380", "Italy", ("Italia",), "Europe"),
    CountryMapping("NL", "NLD", "528", "Netherlands", ("Nederland", "Holland"), "Europe"),
    CountryMapping("PT", "PRT", "620", "Portugal", (), "Europe"),
    CountryMapping("SE", "SWE", "752", "Sweden", ("Sverige",), "Europe"),
    CountryMapping("SI", "SVN", "705", "Slovenia", ("Slovenija",), "Europe"),
    CountryMapping("GB", "GBR", "826", "United Kingdom", ("UK", "Britain", "Great Britain"), "Europe"),
)

_BY_ISO2 = {country.iso2: country for country in _COUNTRIES}
_BY_ISO3 = {country.iso3: country for country in _COUNTRIES}
_BY_NUMERIC = {country.numeric: country for country in _COUNTRIES}
_NAME_ALIASES: dict[str, CountryMapping] = {}
for _country in _COUNTRIES:
    _NAME_ALIASES[_country.name_en.upper()] = _country
    for _alias in _country.aliases:
        _NAME_ALIASES[_alias.upper()] = _country

COUNTRY_SCOPES: dict[str, tuple[str, ...]] = {
    "core_blocking": ("UA", "DE", "PL", "RO", "MD"),
    "regional_extended": (
        "UA",
        "DE",
        "PL",
        "RO",
        "MD",
        "CZ",
        "SK",
        "HU",
        "LT",
        "LV",
        "EE",
        "GE",
        "AM",
        "AZ",
        "KZ",
        "UZ",
    ),
    "full_europe": tuple(country.iso2 for country in _COUNTRIES if country.region == "Europe"),
}


def all_country_codes() -> tuple[str, ...]:
    return tuple(_BY_ISO2.keys())


def country_scope_members(scope: str) -> tuple[str, ...]:
    normalized = str(scope or "").strip().lower()
    if not normalized:
        return COUNTRY_SCOPES["regional_extended"]
    if normalized in COUNTRY_SCOPES:
        return COUNTRY_SCOPES[normalized]
    raise ValueError(f"Unknown country scope: {scope}")


def normalize_country_code(raw: object) -> str:
    if raw is None:
        return ""
    text = str(raw).strip().upper()
    if not text:
        return ""
    if text in _BY_ISO2:
        return text
    if text in _BY_ISO3:
        return _BY_ISO3[text].iso2
    if text in _BY_NUMERIC:
        return _BY_NUMERIC[text].iso2
    if text in _NAME_ALIASES:
        return _NAME_ALIASES[text].iso2
    return ""


def iso2_to_iso3(code: str) -> str:
    normalized = normalize_country_code(code)
    if not normalized:
        return str(code or "").strip().upper()
    return _BY_ISO2[normalized].iso3


def iso2_to_numeric(code: str) -> str:
    normalized = normalize_country_code(code)
    if not normalized:
        return str(code or "").strip().upper()
    return _BY_ISO2[normalized].numeric


def country_region(code: str) -> str:
    normalized = normalize_country_code(code)
    if not normalized:
        return ""
    return _BY_ISO2[normalized].region


__all__ = [
    "COUNTRY_SCOPES",
    "CountryMapping",
    "all_country_codes",
    "country_region",
    "country_scope_members",
    "iso2_to_iso3",
    "iso2_to_numeric",
    "normalize_country_code",
]
