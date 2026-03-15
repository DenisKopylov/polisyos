"""Deterministic domain classifier for legal documents."""

from __future__ import annotations

from dataclasses import dataclass

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fiscal": ("податок", "бюджет", "фінанс", "збір", "акциз", "мито"),
    "labor": ("праця", "зайнятість", "трудов", "заробітн", "пенсі"),
    "social": ("соціальн", "допомога", "субсидія", "пільга", "захист"),
    "health": ("охорон здоров", "медичн", "лікарн", "фармацевт"),
    "education": ("освіт", "навчальн", "університет", "школ"),
    "housing": ("житл", "нерухомість", "будівництв", "комунальн"),
    "environment": ("навколишн", "екологі", "природ", "відход"),
}


@dataclass(frozen=True)
class DomainScore:
    """Per-domain score summary."""

    domain: str
    score: float
    hits: int

    def as_dict(self) -> dict[str, object]:
        return {
            "domain": self.domain,
            "score": self.score,
            "hits": self.hits,
        }


@dataclass(frozen=True)
class DomainClassification:
    """Document-level domain scores."""

    doc_id: str
    top_domain: str | None
    scores: list[DomainScore]

    def as_dict(self) -> dict[str, object]:
        return {
            "doc_id": self.doc_id,
            "top_domain": self.top_domain,
            "scores": [score.as_dict() for score in self.scores],
        }


def classify_domains(*, text: str, doc_id: str) -> DomainClassification:
    """Classify legal document text into predefined policy domains."""
    text_lower = text.lower()
    words = max(1, len(text_lower.split()))
    scores: list[DomainScore] = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        hits = sum(text_lower.count(keyword) for keyword in keywords)
        if hits <= 0:
            continue
        scores.append(
            DomainScore(
                domain=domain,
                score=hits / words,
                hits=hits,
            )
        )
    scores.sort(key=lambda row: row.score, reverse=True)
    top_domain = scores[0].domain if scores else None
    return DomainClassification(doc_id=doc_id, top_domain=top_domain, scores=scores)

