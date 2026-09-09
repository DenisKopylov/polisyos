"""Run exactly one predeclared real typed-extraction attempt for a new model."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from polisyos.data_forge.domains.academic.batch.article_extractor import (
    ExtractorStats,
    PolicyArticleExtractor,
)
from polisyos.data_forge.domains.academic.batch.reextraction_transport import (
    ExtractionRequestError,
    SafeJsonWriter,
    SDKExtractionTransport,
)
from polisyos.data_forge.domains.academic.knowledge.variable_canonizer import VariableCanonizer
from polisyos.ir import ArticleExtractionResult

common = importlib.import_module(
    "docs.superpowers.journals.corr-evidence.c1-capacity.capacity_common"
)


def declared_inputs(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read only the frozen six inputs and independently reconcile their hashes."""
    declaration = common.read_sealed(path)
    if path.is_absolute() or path.parent != common.EVIDENCE:
        raise ValueError("declaration_path_outside_measurement_directory")
    committed = subprocess.check_output([  # noqa: S603 - fixed read-only git invocation.
        "/usr/bin/git", "show", "HEAD:policy-engine/" + path.as_posix(),
    ])
    if path.read_bytes() != committed:
        raise ValueError("model_declaration_not_committed_before_call")
    if datetime.fromisoformat(declaration["declared_at"]) >= datetime.now(UTC):
        raise ValueError("model_declaration_not_before_call")
    old = json.loads(Path(declaration["original_six_declaration_path"]).read_text())
    if (
        declaration["selected_members"] != old["selected_members"]
        or declaration["original_six_declaration_digest"] != old["declaration_digest"]
        or declaration["full_pass_authorized"] is not False
    ):
        raise ValueError("frozen_pilot_selection_changed")
    members = declaration["selected_members"]
    expected = {(row["work_id"], row["abstract_content_hash"]) for row in members}
    with duckdb.connect(declaration["source_path"], read_only=True) as con:
        con.execute("SET threads=1")
        con.execute("SET memory_limit='256MB'")
        ids = [row["work_id"] for row in members]
        columns = [row[0] for row in con.execute("DESCRIBE ac_works").fetchall()]
        rows = con.execute(
            "SELECT * FROM ac_works WHERE id IN (SELECT unnest(?))", [ids],
        ).fetchall()
        works = {row[columns.index("id")]: dict(zip(columns, row, strict=True)) for row in rows}
        sql = {(row[0], "sha256:" + row[1]) for row in con.execute(
            "SELECT id,sha256(abstract) FROM ac_works WHERE id IN (SELECT unnest(?))", [ids],
        ).fetchall()}
    python = {(key, "sha256:" + hashlib.sha256(row["abstract"].encode()).hexdigest())
              for key, row in works.items()}
    if expected != sql or sql != python or len(rows) != len(expected) or len(expected) != 6:
        raise ValueError("frozen_pilot_source_identity_mismatch")
    return declaration, [works[row["work_id"]] for row in declaration["execution_members"]]


class _ObservedClient:
    synthetic = False

    def __init__(self, client: object) -> None:
        self.client = client
        self.response: dict[str, Any] | None = None
        self.usage: dict[str, Any] | None = None
        self.count = 0

    async def chat(
        self, *, model: str, temperature: float, prompt: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self.count += 1
        if self.count > 1:
            raise ValueError("contract_probe_call_limit_exceeded")
        self.response, self.usage = await self.client.chat(
            model=model, temperature=temperature, prompt=prompt,
        )
        return self.response, self.usage


async def run(path: Path) -> dict[str, Any]:
    """Retain a real candidate response and the actual owner's typed verdict."""
    declaration, works = declared_inputs(path)
    if declaration["purpose"] != "one_typed_extraction_contract_probe" or len(works) != 1:
        raise ValueError("contract_probe_scope_invalid")
    model = declaration["model_id"]
    slug = "deepseek" if model.startswith("deepseek") else "minimax"
    output = common.EVIDENCE / (slug + "-contract-response.json")
    summary_path = common.EVIDENCE / (slug + "-contract-verdict.json")
    scratch = Path(".tmp/corr-c1-capacity/contracts") / slug
    if scratch.exists() or output.exists() or summary_path.exists():
        raise ValueError("contract_probe_already_executed")
    writer = SafeJsonWriter(common.load_credential())
    scratch.mkdir(parents=True)
    result = None
    error_kind = None
    stats = ExtractorStats()
    async with SDKExtractionTransport(
        api_key=common.load_credential(), base_url=declaration["base_url"], model_id=model,
        output_root=scratch, timeout_seconds=declaration["timeout_seconds"],
        max_completion_tokens=declaration["max_completion_tokens"],
        prompt_estimator=common.local_estimator,
    ) as transport:
        client = _ObservedClient(transport.bind({
            "attempt_id": "contract-1", "work_id": works[0]["id"], "phase": "extraction",
            "campaign_id": declaration["content_hash"],
            "input_hash": declaration["execution_members"][0]["abstract_content_hash"],
            "synthetic": False,
        }))
        extractor = PolicyArticleExtractor(
            screening_model=model, extraction_model=model, max_concurrent=1,
            canonizer=VariableCanonizer(), gonka_client=client,
            fulltext_timeout_seconds=3, cache_path=scratch / "unused-cache.jsonl",
            preserve_source_presence=True,
        )
        try:
            result = await extractor._extract(
                works[0], works[0]["abstract"], "abstract_fallback", stats,
            )
        except ExtractionRequestError as exc:
            error_kind = exc.kind
        if client.response is not None:
            writer(output, {
                "synthetic": False, "authority_status": "candidate_only",
                "model_id": model, "declaration_hash": declaration["content_hash"],
                "work_id": works[0]["id"], "response": client.response, "usage": client.usage,
            })
    attempt = json.loads((scratch / "provider_attempts/contract-1.json").read_text())
    verdict = {
        "synthetic": False, "authority_status": "candidate_only",
        "declaration_hash": declaration["content_hash"], "model_id": model,
        "work_id": works[0]["id"], "declared_attempts": 1, "actual_attempts": client.count,
        "contract_satisfied": isinstance(result, ArticleExtractionResult),
        "error_kind": error_kind or ("contract_violation" if result is None else None),
        "typed_schema_hash": common.digest(ArticleExtractionResult.model_json_schema()),
        "typed_result_hash": common.digest(result.model_dump(mode="json")) if result else None,
        "response_artifact": str(output) if output.exists() else None,
        "response_hash": common.digest(client.response) if client.response is not None else None,
        "attempt_observation": attempt,
    }
    writer(summary_path, verdict)
    return {"verdict_path": str(summary_path), "contract_satisfied": verdict["contract_satisfied"],
            "error_kind": verdict["error_kind"], "model_id": model}


def main() -> int:
    """Use the exact committed declaration and print only its checked summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("declaration", type=Path)
    args = parser.parse_args()
    summary = asyncio.run(run(args.declaration))
    writer = SafeJsonWriter(common.load_credential())
    sys.stdout.write(writer.encode(summary))
    return 0 if summary["contract_satisfied"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
