"""Download a lightweight real-data benchmark pack for local execution."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools._lib.imports import repo_root_from


ACIC_BASE = "https://raw.githubusercontent.com/IBM/causallib/master/causallib/datasets/data/acic_challenge_2016"
LBIDD_BASE = "https://raw.githubusercontent.com/IBM-HRL-MLHLS/IBM-Causal-Inference-Benchmarking-Framework/master/data/LBIDD"
REALCAUSE_BASE = "https://raw.githubusercontent.com/bradyneal/realcause/master/realcause_datasets"


@dataclass(frozen=True)
class BenchmarkProfile:
    name: str
    lbidd_scaling_files: int
    realcause_samples: dict[str, list[int]]


PROFILES: dict[str, BenchmarkProfile] = {
    "air-m2": BenchmarkProfile(
        name="air-m2",
        lbidd_scaling_files=5,
        realcause_samples={
            "twins": [0, 1],
            "lalonde_cps": [0, 1],
            "lalonde_psid": [0, 1],
        },
    ),
    "extended": BenchmarkProfile(
        name="extended",
        lbidd_scaling_files=8,
        realcause_samples={
            "twins": [0, 1, 2],
            "lalonde_cps": [0, 1, 2],
            "lalonde_psid": [0, 1, 2],
        },
    ),
}


def _download(url: str, destination: Path, *, refresh: bool) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not refresh:
        return {"path": str(destination), "status": "cached", "url": url, "bytes": destination.stat().st_size}

    with urllib.request.urlopen(url, timeout=60) as response:
        payload = response.read()
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    tmp_path.write_bytes(payload)
    tmp_path.replace(destination)
    return {"path": str(destination), "status": "downloaded", "url": url, "bytes": len(payload)}


def _load_remote_csv_rows(url: str) -> list[dict[str, str]]:
    with urllib.request.urlopen(url, timeout=60) as response:
        text = response.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def _prepare_acic(root: Path, *, refresh: bool) -> list[dict[str, Any]]:
    target_root = root / "acic" / "acic_challenge_2016"
    entries = [_download(f"{ACIC_BASE}/x.csv", target_root / "x.csv", refresh=refresh)]
    for index in range(1, 11):
        file_name = f"zymu_{index}.csv"
        entries.append(_download(f"{ACIC_BASE}/{file_name}", target_root / file_name, refresh=refresh))
    return entries


def _select_lbidd_scaling_files(count: int) -> list[str]:
    rows = _load_remote_csv_rows(f"{LBIDD_BASE}/scaling_params.csv")
    rows.sort(key=lambda row: (int(float(row["size"])), -float(row["snr"]), row["ufid"]))
    return [row["ufid"] for row in rows[:count]]


def _prepare_lbidd(root: Path, *, profile: BenchmarkProfile, refresh: bool) -> list[dict[str, Any]]:
    target_root = root / "lbidd" / "LBIDD"
    entries = [
        _download(f"{LBIDD_BASE}/x.csv", target_root / "x.csv", refresh=refresh),
        _download(
            f"{LBIDD_BASE}/scaling_params.csv",
            target_root / "scaling_params.csv",
            refresh=refresh,
        ),
    ]
    for ufid in _select_lbidd_scaling_files(profile.lbidd_scaling_files):
        entries.append(
            _download(
                f"{LBIDD_BASE}/scaling/{ufid}.csv",
                target_root / "scaling" / f"{ufid}.csv",
                refresh=refresh,
            )
        )
        entries.append(
            _download(
                f"{LBIDD_BASE}/scaling/{ufid}_cf.csv",
                target_root / "scaling" / f"{ufid}_cf.csv",
                refresh=refresh,
            )
        )
    normalized_root = root / "lbidd" / "lbidd_normalized"
    normalized_root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(target_root / "x.csv", normalized_root / "x.csv")
    for ufid in _select_lbidd_scaling_files(profile.lbidd_scaling_files):
        factual_path = target_root / "scaling" / f"{ufid}.csv"
        cf_path = target_root / "scaling" / f"{ufid}_cf.csv"
        normalized_path = normalized_root / f"zy_{ufid}.csv"
        with factual_path.open() as factual_handle:
            factual_rows = list(csv.DictReader(factual_handle))
        with cf_path.open() as cf_handle:
            cf_rows = {
                str(row["sample_id"]): row
                for row in csv.DictReader(cf_handle)
            }
        with normalized_path.open("w", newline="") as out_handle:
            writer = csv.DictWriter(
                out_handle,
                fieldnames=["sample_id", "z", "y", "mu1", "mu0"],
            )
            writer.writeheader()
            for row in factual_rows:
                sample_id = str(row["sample_id"])
                cf_row = cf_rows.get(sample_id)
                if cf_row is None:
                    continue
                writer.writerow(
                    {
                        "sample_id": sample_id,
                        "z": row["z"],
                        "y": row["y"],
                        "mu1": cf_row["y1"],
                        "mu0": cf_row["y0"],
                    }
                )
    return entries


def _prepare_realcause(root: Path, *, profile: BenchmarkProfile, refresh: bool) -> list[dict[str, Any]]:
    target_root = root / "realcause" / "realcause_datasets"
    entries: list[dict[str, Any]] = []
    for family, sample_indices in profile.realcause_samples.items():
        for sample_index in sample_indices:
            file_name = f"{family}_sample{sample_index}.csv"
            entries.append(
                _download(
                    f"{REALCAUSE_BASE}/{file_name}",
                    target_root / file_name,
                    refresh=refresh,
                )
            )
    return entries


def _write_env_file(root: Path) -> Path:
    env_file = root / "local_env.sh"
    env_file.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "export ACIC_DATA_DIR=\"${ACIC_DATA_DIR:-" + str(root / "acic") + "}\"",
                "export LBIDD_DATA_DIR=\"${LBIDD_DATA_DIR:-" + str(root / "lbidd") + "}\"",
                "export REALCAUSE_DATA_DIR=\"${REALCAUSE_DATA_DIR:-" + str(root / "realcause") + "}\"",
                "",
            ]
        )
        + "\n"
    )
    os.chmod(env_file, 0o755)
    return env_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download a local real-data benchmark pack")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="air-m2")
    parser.add_argument(
        "--data-root",
        default=None,
        metavar="DIR",
        help="Root directory for downloaded benchmark data",
    )
    parser.add_argument("--refresh", action="store_true", help="Re-download files even if cached")
    args = parser.parse_args(argv)

    repo_root = repo_root_from(__file__)
    data_root = Path(args.data_root).expanduser() if args.data_root else repo_root / "data" / "raw" / "benchmarks" / "local_real"
    profile = PROFILES[args.profile]

    manifest = {
        "profile": profile.name,
        "data_root": str(data_root),
        "sources": {
            "acic": ACIC_BASE,
            "lbidd": LBIDD_BASE,
            "realcause": REALCAUSE_BASE,
        },
        "downloads": {
            "acic": _prepare_acic(data_root, refresh=args.refresh),
            "lbidd": _prepare_lbidd(data_root, profile=profile, refresh=args.refresh),
            "realcause": _prepare_realcause(data_root, profile=profile, refresh=args.refresh),
        },
    }

    env_file = _write_env_file(data_root)
    manifest["env_file"] = str(env_file)

    manifest_path = data_root / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    total_bytes = sum(
        int(entry["bytes"])
        for entries in manifest["downloads"].values()
        for entry in entries
    )
    print(json.dumps(
        {
            "profile": profile.name,
            "data_root": str(data_root),
            "manifest": str(manifest_path),
            "env_file": str(env_file),
            "downloaded_bytes": total_bytes,
            "lbidd_scaling_files": profile.lbidd_scaling_files,
            "realcause_samples": profile.realcause_samples,
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
