"""Source-owned runtime module and summary routes for the Data Forge read API."""

from __future__ import annotations

READ_API_SURFACE_MODULES: dict[str, str] = {
    "academic": "polisyos.data_forge.read_api.academic",
    "catalog": "polisyos.data_forge.read_api.catalog",
    "compliance": "polisyos.data_forge.read_api.compliance",
    "legal": "polisyos.data_forge.read_api.legal",
    "provenance": "polisyos.data_forge.read_api.provenance",
    "ukraine": "polisyos.data_forge.read_api.ukraine",
}

READ_API_SURFACE_SUMMARIES: dict[str, str] = {
    "academic": "Academic artifact, readiness, and shadow-diff readers.",
    "catalog": "Dataset catalog artifact, source-module, readiness, and shadow-diff readers.",
    "compliance": "Privacy compliance report builders and normalizers.",
    "legal": "Read-only Lex shadow artifact and differential readers.",
    "provenance": "Snapshot provenance DTOs and source-binding references.",
    "ukraine": "Ukraine D4 source-snapshot contracts, non-Lex artifacts, and demographic readers.",
}
