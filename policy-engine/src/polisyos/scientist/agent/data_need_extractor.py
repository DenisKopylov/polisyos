"""DataNeedExtractor agent implementations (mock + LLM)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.fabric.catalog.registry import DataContractRegistry
from polisyos.scientist.agent.prompts import get_data_need_extractor_prompt
from polisyos.scientist.agent.protocols import DataNeedExtractorAgent, DataNeedSpec, ProblemFrame
from polisyos.scientist.orchestration.llm import TracedLLMClient

logger = get_logger(__name__)

_YEAR_RE = re.compile(r"(19|20)\d{2}")
_DATA_NEED_PARSE_ERRORS = (
    json.JSONDecodeError,
    TypeError,
    ValueError,
)
_DATASET_CATALOG_LOOKUP_ERRORS = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


class MockDataNeedExtractorAgent:
    """Deterministic extractor suitable for tests and local runs."""

    _METRIC_KEYWORDS: tuple[tuple[str, str], ...] = (
        ("gdp", "us.macro.gdp_nominal"),
        ("gross domestic product", "us.macro.gdp_nominal"),
        ("unemployment", "us.macro.unemployment_rate"),
        ("jobless", "us.macro.unemployment_rate"),
        ("salary", "agent.income.salary"),
        ("income", "agent.income.salary"),
    )

    async def extract_data_needs(self, problem_frame: ProblemFrame) -> list[DataNeedSpec]:
        text = " ".join(
            [
                problem_frame.problem_statement,
                *problem_frame.goals,
                *problem_frame.constraints,
            ]
        ).lower()

        years = [int(match.group(0)) for match in _YEAR_RE.finditer(text)]
        start_year = str(min(years)) if years else None
        end_year = str(max(years)) if years else None

        geography = None
        if "ukraine" in text:
            geography = "UKR"
        elif "european union" in text or "eu " in text or " eu" in text:
            geography = "EU*"
        elif "united states" in text or "usa" in text or " us " in text:
            geography = "USA"

        metrics: list[str] = []
        for keyword, metric_id in self._METRIC_KEYWORDS:
            if keyword in text and metric_id not in metrics:
                metrics.append(metric_id)
        if not metrics:
            metrics.append("us.macro.gdp_nominal")

        needs: list[DataNeedSpec] = []
        for metric_id in metrics:
            granularity = "annual"
            if "monthly" in text:
                granularity = "monthly"
            elif "quarterly" in text:
                granularity = "quarterly"
            needs.append(
                DataNeedSpec(
                    metric=metric_id,
                    geography=geography,
                    time_start=start_year,
                    time_end=end_year,
                    granularity=granularity,
                    quality_min=0.6,
                    purpose="policy_drafting",
                )
            )
        return needs


class LLMDataNeedExtractorAgent:
    """LLM-backed extractor with strict JSON output contract."""

    def __init__(
        self,
        llm_client: Any,
        *,
        model_name: str | None = None,
        curated_dir: Path = Path("data/curated"),
        dataset_catalog: object | None = None,
    ) -> None:
        if llm_client is not None and not isinstance(llm_client, TracedLLMClient):
            self._llm = TracedLLMClient(llm_client, model_name=model_name)
        else:
            self._llm = llm_client
        self._fallback = MockDataNeedExtractorAgent()
        self._registry = DataContractRegistry(curated_dir=curated_dir, strict=False)
        self._dataset_catalog = dataset_catalog  # DatasetCatalogGraph (optional)

    async def extract_data_needs(self, problem_frame: ProblemFrame) -> list[DataNeedSpec]:
        if self._llm is None:
            return await self._fallback.extract_data_needs(problem_frame)

        metric_ids = self._registry.list_all()
        prompt = get_data_need_extractor_prompt(metric_ids=metric_ids[:200])
        payload = {
            "frame_id": problem_frame.frame_id,
            "domain": problem_frame.domain,
            "problem_statement": problem_frame.problem_statement,
            "goals": list(problem_frame.goals),
            "constraints": list(problem_frame.constraints),
            "success_criteria": problem_frame.success_criteria,
            "assumptions": list(problem_frame.assumptions),
            "context": problem_frame.context,
        }
        response = await self._llm.generate(
            system=prompt,
            user=json.dumps(payload, ensure_ascii=True, indent=2),
            response_format={"type": "json_object"},
        )
        content = response.content if hasattr(response, "content") else str(response)
        try:
            data = json.loads(content)
            rows = data.get("data_needs")
            if not isinstance(rows, list):
                raise ValueError("`data_needs` must be a list")
            needs: list[DataNeedSpec] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                metric = str(row.get("metric", "")).strip()
                if not metric:
                    continue
                needs.append(
                    DataNeedSpec(
                        metric=metric,
                        geography=_opt_string(row.get("geography")),
                        time_start=_opt_string(row.get("time_start")),
                        time_end=_opt_string(row.get("time_end")),
                        granularity=_opt_string(row.get("granularity")) or "annual",
                        quality_min=float(row.get("quality_min", 0.6)),
                        purpose=_opt_string(row.get("purpose")) or "policy_drafting",
                    )
                )
            if needs:
                return self._enrich_with_catalog(needs)
        except _DATA_NEED_PARSE_ERRORS as exc:
            logger.debug("Falling back to mock data-need extraction after parse error: %s", exc)
        return await self._fallback.extract_data_needs(problem_frame)

    def _enrich_with_catalog(self, needs: list[DataNeedSpec]) -> list[DataNeedSpec]:
        """Validate metric availability via DatasetCatalogGraph if present."""
        if self._dataset_catalog is None:
            return needs
        find_fn = getattr(self._dataset_catalog, "find_by_polisyos_metric", None)
        if find_fn is None:
            return needs
        validated: list[DataNeedSpec] = []
        for need in needs:
            try:
                results = find_fn(need.metric, top_k=1)
            except _DATASET_CATALOG_LOOKUP_ERRORS:
                logger.debug(
                    "Catalog lookup failed for metric %r",
                    need.metric,
                    exc_info=True,
                )
                results = []
            # Keep all needs; those with catalog hits get boosted quality_min
            if results:
                validated.append(
                    DataNeedSpec(
                        metric=need.metric,
                        geography=need.geography,
                        time_start=need.time_start,
                        time_end=need.time_end,
                        granularity=need.granularity,
                        quality_min=max(need.quality_min, 0.7),
                        purpose=need.purpose,
                    )
                )
            else:
                validated.append(need)
        return validated


def _opt_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _verify_protocol() -> None:
    agent = MockDataNeedExtractorAgent()
    if not isinstance(agent, DataNeedExtractorAgent):
        raise TypeError("MockDataNeedExtractorAgent does not implement DataNeedExtractorAgent")


_verify_protocol()


__all__ = ["LLMDataNeedExtractorAgent", "MockDataNeedExtractorAgent"]
