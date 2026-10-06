from __future__ import annotations

import subprocess

WORKTREES = {
    "BER": "/Users/deniskopylov/.codex/worktrees/e02-c-berl-20261006/polisyos",
    "CANON": "/Users/deniskopylov/.codex/worktrees/e02-c-canon-20261006/polisyos",
    "CAT": "/Users/deniskopylov/.codex/worktrees/e02-c-catalog-20261006/polisyos",
    "CLI": "/Users/deniskopylov/.codex/worktrees/e02-c-client-20261006/polisyos",
    "DFI-EMB": "/Users/deniskopylov/.codex/worktrees/e02-c-dfi-emb-20261006/polisyos",
    "FED": "/Users/deniskopylov/.codex/worktrees/e02-c-federation-20261006/polisyos",
    "HYG": "/Users/deniskopylov/.codex/worktrees/e02-c-hygiene-20261006/polisyos",
    "MIG": "/Users/deniskopylov/.codex/worktrees/e02-c-migrations-20261006/polisyos",
    "OBS-UDF": "/Users/deniskopylov/.codex/worktrees/e02-c-obs-udf-20261006/polisyos",
    "PLG": "/Users/deniskopylov/.codex/worktrees/e02-c-plugins-20261006/polisyos",
    "SCHEMA": "/Users/deniskopylov/.codex/worktrees/e02-c-schema-20261006/polisyos",
    "SCL": "/Users/deniskopylov/.codex/worktrees/e02-c-scholar-20261006/polisyos",
    "ING/root": "/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos",
    "ING-oracle-support": "/Users/deniskopylov/.codex/worktrees/e02-c-ing-oracle-20261006/polisyos",
}

for name, path in WORKTREES.items():
    status = subprocess.run(
        ["git", "-C", path, "status", "--porcelain=v1", "-b"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip().replace("\n", " | ")
    ids = subprocess.run(
        ["git", "-C", path, "rev-parse", "HEAD", "HEAD^{tree}"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip().replace("\n", "/")
    print(f"{name}\t{ids}\t{status}")
