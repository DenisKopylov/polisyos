#!/usr/bin/env python3
"""Generate Markdown audit cards for active evidence capabilities."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation.inspect_policy_evidence_capability_index import (
    active_capabilities,
    load_capability_index_snapshot,
)

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.capability_index import AcquisitionStrategy

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.runtime.quality.capability_index import EvidenceCapability

SCHEMA_VERSION = "policyos.capability_index.capability_cards_manifest.v1"
_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_CARD_FILENAME_STEM_LENGTH = 96


def generate_capability_cards(
    *,
    capability_index_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Write one Markdown card per active capability.

    Args:
        capability_index_path: Path to ``capability_index_v1.duckdb``.
        output_dir: Destination directory for Markdown cards.

    Returns:
        Manifest with generated card filenames and authority boundary.
    """

    snapshot = load_capability_index_snapshot(capability_index_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    for stale_card in destination.glob("*.md"):
        stale_card.unlink()
    strategies = tuple(
        strategy
        for strategy in snapshot.get("acquisition_strategies", ())
        if isinstance(strategy, AcquisitionStrategy)
    )
    cards: list[dict[str, str]] = []
    for capability in active_capabilities(snapshot):
        filename = _filename(capability.capability_id)
        (destination / filename).write_text(
            render_capability_card(capability, acquisition_strategies=strategies),
            encoding="utf-8",
        )
        cards.append({"capability_id": capability.capability_id, "filename": filename})
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "capability_index_path": str(Path(capability_index_path)),
        "output_dir": str(destination),
        "card_count": len(cards),
        "cards": cards,
        "authority_boundary": {
            "authoritative_for": ["human_review_audit_surface"],
            "may_not_use_for": ["claim_evidence_satisfaction", "source_authority_override"],
        },
    }
    atomic_write_json(destination / "manifest.json", manifest)
    return manifest


def render_capability_card(
    capability: EvidenceCapability,
    *,
    acquisition_strategies: Sequence[AcquisitionStrategy] = (),
) -> str:
    """Render a single capability card from typed capability data."""

    owner = _owner_for_capability(capability)
    alternatives = [
        strategy
        for strategy in acquisition_strategies
        if _bare_construct(strategy.target_construct) == _bare_construct(capability.construct_id)
    ]
    lines = [
        f"# {capability.capability_id}",
        "",
        "## What This Proves",
        "",
        (
            f"- `{capability.construct_id}` capability for `{capability.scope.geography}` "
            f"at `{capability.evidence_mode}` evidence mode, backed by "
            f"{len(capability.source_assets)} typed source asset(s)."
        ),
        (
            f"- Authority basis: "
            f"{', '.join(capability.authority_envelope.authority_basis) or 'not recorded'}."
        ),
        "",
        "## What This Does Not Prove",
        "",
        *_bullet_lines(
            (
                *capability.authority_envelope.may_not_use_for,
                *capability.may_not_use_for,
            )
            or (
                "It does not prove authority outside the purpose-scoped authority envelope.",
            )
        ),
        "",
        "## Known Limitations",
        "",
        *_bullet_lines(
            capability.limitations
            or ("No limitation text is recorded; treat the authority envelope as binding.",)
        ),
        "",
        "## Authority Envelope",
        "",
        f"- research: `{capability.authority_envelope.research}`",
        f"- governed_pilot: `{capability.authority_envelope.governed_pilot}`",
        f"- production: `{capability.authority_envelope.production}`",
        "",
        "## Owner",
        "",
        f"- `{owner}`",
        "",
        "## Reviewer Notes",
        "",
        (
            "- Generated from the typed capability index; reviewers may annotate "
            "the card, but hand-authored notes do not create authority."
        ),
        f"- Compatibility-only: `{str(capability.compatibility_only).lower()}`",
        f"- Lifecycle state: `{capability.capability_lifecycle.state}`",
        "",
        "## Acquisition Alternatives",
        "",
        *_acquisition_lines(alternatives),
        "",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capability-index", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = generate_capability_cards(
        capability_index_path=args.capability_index,
        output_dir=args.output_dir,
    )
    json.dump(manifest, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if manifest["status"] == "pass" else 1


def _owner_for_capability(capability: EvidenceCapability) -> str:
    metadata_owner = capability.metadata.get("owner") or capability.metadata.get("producer_owner")
    if isinstance(metadata_owner, str) and metadata_owner.strip():
        return metadata_owner.strip()
    modalities = set(capability.modality)
    if "lex_norm" in modalities:
        return "team-legal-knowledge"
    if "scholar_claim" in modalities:
        return "team-scholar"
    if "foundry_method_contract" in modalities:
        return "team-foundry-owners"
    if "fabric_data" in modalities:
        return "team-data-forge"
    return "team-runtime-quality"


def _acquisition_lines(strategies: Sequence[AcquisitionStrategy]) -> list[str]:
    if not strategies:
        return [
            (
                "- No additional acquisition alternative is recorded in this index; "
                "do not infer authority beyond the envelope."
            )
        ]
    return [
        (
            f"- `{strategy.strategy_id}`: {strategy.authority_class}; owner "
            f"`{strategy.owner_team}`; estimated time `{strategy.estimated_time}`."
        )
        for strategy in strategies
    ]


def _bullet_lines(values: Sequence[str]) -> list[str]:
    return [f"- {value}" for value in values]


def _filename(capability_id: str) -> str:
    stem = _FILENAME_RE.sub("_", capability_id).strip("_") or "capability"
    digest = hashlib.sha256(capability_id.encode("utf-8")).hexdigest()[:12]
    if len(stem) > _MAX_CARD_FILENAME_STEM_LENGTH:
        stem = stem[:_MAX_CARD_FILENAME_STEM_LENGTH].rstrip("._-")
    return f"{stem}__{digest}.md"


def _bare_construct(value: str) -> str:
    return value.removeprefix("construct:")


if __name__ == "__main__":
    raise SystemExit(main())
