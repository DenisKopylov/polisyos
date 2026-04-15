#!/usr/bin/env python3
"""Parse six Gonka accounts from .env and sync them to Secret Manager.

The script supports commented and uncommented ``GONKA_API_KEY_N=...`` lines.
Accounts are detected by email comment headers and assigned sequentially in the
same order they appear in the file.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

EMAIL_COMMENT_RE = re.compile(r"^\s*#\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\s*$")
KEY_RE = re.compile(r"^\s*#?\s*GONKA_API_KEY_(\d+)\s*=\s*(gp-[A-Za-z0-9]+)\s*$")


@dataclass
class AccountKeys:
    email: str
    keys: dict[int, str]


def _run(cmd: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        input=input_text,
        text=True,
        check=True,
        capture_output=True,
    )


def parse_accounts(env_path: Path) -> list[AccountKeys]:
    accounts: list[AccountKeys] = []
    current_email: str | None = None
    current_keys: dict[int, str] = {}

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        email_match = EMAIL_COMMENT_RE.match(raw_line)
        if email_match:
            if current_email and current_keys:
                accounts.append(AccountKeys(email=current_email, keys=dict(current_keys)))
            current_email = email_match.group(1)
            current_keys = {}
            continue

        key_match = KEY_RE.match(raw_line)
        if key_match and current_email:
            key_num = int(key_match.group(1))
            current_keys[key_num] = key_match.group(2)

    if current_email and current_keys:
        accounts.append(AccountKeys(email=current_email, keys=dict(current_keys)))

    if len(accounts) != 6:
        raise ValueError(f"Expected 6 Gonka accounts in {env_path}, found {len(accounts)}")
    for idx, account in enumerate(accounts, start=1):
        if sorted(account.keys) != [1, 2, 3, 4, 5]:
            raise ValueError(f"Account {idx} ({account.email}) does not contain keys 1..5")
    return accounts


def ensure_secret(project_id: str, secret_name: str, value: str, *, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] create-or-update {secret_name}")
        return

    describe_cmd = [
        "gcloud", "secrets", "describe", secret_name,
        f"--project={project_id}",
    ]
    exists = subprocess.run(describe_cmd, check=False, capture_output=True, text=True).returncode == 0

    if exists:
        _run(
            [
                "gcloud", "secrets", "versions", "add", secret_name,
                f"--project={project_id}",
                "--data-file=-",
            ],
            input_text=value,
        )
    else:
        _run(
            [
                "gcloud", "secrets", "create", secret_name,
                f"--project={project_id}",
                "--replication-policy=automatic",
                "--data-file=-",
            ],
            input_text=value,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True, help="Path to policy-engine/.env")
    parser.add_argument("--project-id", required=True, help="Target GCP project id")
    parser.add_argument("--prefix", default="gonka", help="Secret prefix, default: gonka")
    parser.add_argument("--manifest-out", type=Path, default=None, help="Optional non-sensitive manifest output")
    parser.add_argument("--dry-run", action="store_true", help="Print planned secret actions without applying")
    args = parser.parse_args()

    accounts = parse_accounts(args.env_file)
    manifest: list[dict[str, object]] = []

    for acc_idx, account in enumerate(accounts, start=1):
        secret_names: list[str] = []
        for key_num, value in sorted(account.keys.items()):
            secret_name = f"{args.prefix}-acc{acc_idx}-key{key_num}"
            ensure_secret(args.project_id, secret_name, value, dry_run=args.dry_run)
            secret_names.append(secret_name)
        manifest.append(
            {
                "account_num": acc_idx,
                "email": account.email,
                "secret_names": secret_names,
            }
        )

    if args.manifest_out is not None:
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Processed {len(accounts)} Gonka accounts for project {args.project_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
