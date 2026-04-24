"""Panel data interpolation for observation time series.

Fills year-level gaps in country×indicator panels using:
- Linear interpolation for gaps ≤ max_linear_gap years
- LOCF (Last Observation Carried Forward) for gaps up to max_locf_gap years
- Marks interpolated values with ``interpolated=true`` in condition_json.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

logger = logging.getLogger(__name__)


def interpolate_observations(
    con: duckdb.DuckDBPyConnection,
    *,
    max_linear_gap: int = 3,
    max_locf_gap: int = 5,
    sources: tuple[str, ...] = ("worldbank", "who", "eurostat", "unesco_uis"),
) -> int:
    """Interpolate gaps in country×indicator time series.

    Only runs for sources with annual periodicity. Returns count of
    interpolated rows inserted.
    """
    source_filter = ", ".join(f"'{s}'" for s in sources)
    query = f"""
        SELECT dataset_id, raw_variable, canonical_var, country_code, year, value, condition_json
        FROM ds_observations
        WHERE year IS NOT NULL
          AND dataset_id IN (
              SELECT dataset_id FROM ds_datasets WHERE source IN ({source_filter})
          )
        ORDER BY dataset_id, raw_variable, country_code, year
    """
    try:
        rows = con.execute(query).fetchall()
    except Exception:
        logger.warning("interpolate_observations: query failed", exc_info=True)
        return 0

    # Group by (dataset_id, raw_variable, country_code)
    panels: dict[tuple[str, str, str, str], list[tuple[int, float, str]]] = defaultdict(list)
    for dataset_id, raw_var, canonical_var, country, year, value, cond_json in rows:
        panels[(dataset_id, raw_var, canonical_var or "", country)].append(
            (year, value, cond_json or "{}")
        )

    interpolated_count = 0
    batch: list[tuple[str, str, str, str, str, int, float, str]] = []

    for (dataset_id, raw_var, canonical_var, country), series in panels.items():
        if len(series) < 2:
            continue
        series.sort(key=lambda x: x[0])
        existing_years = {y for y, _, _ in series}

        for i in range(len(series) - 1):
            y1, v1, _ = series[i]
            y2, v2, _ = series[i + 1]
            gap = y2 - y1 - 1
            if gap <= 0:
                continue

            for offset in range(1, gap + 1):
                fill_year = y1 + offset
                if fill_year in existing_years:
                    continue

                if gap <= max_linear_gap:
                    # Linear interpolation
                    frac = offset / (gap + 1)
                    fill_value = v1 + frac * (v2 - v1)
                    method = "linear"
                elif gap <= max_locf_gap:
                    # LOCF
                    fill_value = v1
                    method = "locf"
                else:
                    break  # Gap too large, skip

                cond = json.dumps(
                    {"interpolated": True, "method": method, "gap_size": gap},
                    separators=(",", ":"),
                )
                obs_id = hashlib.sha256(
                    f"{dataset_id}|{raw_var}|{canonical_var}|{country}|{fill_year}|interp".encode()
                ).hexdigest()[:20]

                batch.append(
                    (
                        obs_id,
                        dataset_id,
                        raw_var,
                        canonical_var,
                        country,
                        fill_year,
                        fill_value,
                        cond,
                    )
                )
                existing_years.add(fill_year)
                interpolated_count += 1

    if batch:
        con.executemany(
            """INSERT OR IGNORE INTO ds_observations
               (observation_id, dataset_id, raw_variable, canonical_var,
                country_code, year, value, condition_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            batch,
        )
        con.execute("CHECKPOINT")

    logger.info(
        "Interpolation: {} rows inserted across {} panels",
        interpolated_count,
        len(panels),
    )
    return interpolated_count
