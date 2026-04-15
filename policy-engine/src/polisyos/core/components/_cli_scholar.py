"""CLI sub-module: scholar enrichment commands."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from polisyos.core.components._cli_store import build_cli_filesystem_cas
from polisyos.core.contracts.scholar import ResearchIntent

__all__ = [
    "_cmd_scholar_enrich",
]


def _cmd_scholar_enrich(args: Any) -> int:
    scholar_api = importlib.import_module("polisyos.scholar.api")
    enrich_topic = scholar_api.enrich_topic

    cas = build_cli_filesystem_cas(Path(args.cas_root))
    fact_log_root = Path(args.fact_log_root)
    payload = json.loads(Path(args.intent).read_text(encoding="utf-8"))
    intent = ResearchIntent.model_validate(payload)

    result = enrich_topic(
        cas=cas,
        fact_log_root=fact_log_root,
        intent=intent,
    )
    print(f"knowledge_bundle_ref={result.knowledge_bundle_ref.artifact_id}")
    print(f"bundle_id={result.bundle_id}")
    return 0
