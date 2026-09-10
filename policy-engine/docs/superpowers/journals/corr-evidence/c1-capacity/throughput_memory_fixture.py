"""Marked synthetic, provider-free worker with deliberate retained-memory growth."""

from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    args = parser.parse_args()
    retained = []
    with sqlite3.connect(args.checkpoint) as con:
        con.execute("CREATE TABLE provenance(synthetic INTEGER CHECK(synthetic=1))")
        con.execute("INSERT INTO provenance VALUES(1)")
        con.execute("""CREATE TABLE work_items(work_id TEXT PRIMARY KEY,status TEXT,
                    started_at REAL,finished_at REAL,latency_seconds REAL,error_kind TEXT,
                    prompt_tokens INTEGER,completion_tokens INTEGER)""")
        con.commit()
        for ordinal in range(12):
            started = time.monotonic()
            pages = bytearray(4 * 1024**2)
            for index in range(0, len(pages), 4096):
                pages[index] = 1
            retained.append(pages)
            time.sleep(0.3)
            finished = time.monotonic()
            con.execute(
                "INSERT INTO work_items VALUES(?,?,?,?,?,NULL,NULL,NULL)",
                (f"synthetic:{ordinal}", "succeeded", started, finished, finished - started),
            )
            con.commit()
        time.sleep(0.3)


if __name__ == "__main__":
    main()
