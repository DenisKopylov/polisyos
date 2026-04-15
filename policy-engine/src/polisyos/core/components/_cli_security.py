"""CLI sub-module: security rotation workflows."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from polisyos.core.security.rotation import (
    rotate_ed25519_signing_key,
    update_jwt_trust_anchor_manifest,
)

__all__ = [
    "_cmd_security_rotate_ed25519",
    "_cmd_security_rotate_jwt",
]


def _cmd_security_rotate_jwt(args: Any) -> int:
    active = _split_csv(args.active_kid)
    next_values = _split_csv(args.next_kid)
    retire = _split_csv(args.retire_kid)
    revoke = _split_csv(args.revoke_kid)
    try:
        result = update_jwt_trust_anchor_manifest(
            manifest_path=Path(args.manifest),
            issuer=args.issuer,
            jwks_uri=args.jwks_uri,
            audience=args.audience,
            active_kids=tuple(active),
            next_kids=tuple(next_values),
            retire_kids=tuple(retire),
            revoke_kids=tuple(revoke),
            rotated_by=args.rotated_by,
        )
    except Exception as exc:
        print(f"ERROR: JWT rotation manifest update failed: {exc}", file=sys.stderr)
        return 1
    _print_payload(result.to_dict(), json_output=bool(args.json))
    return 0


def _cmd_security_rotate_ed25519(args: Any) -> int:
    try:
        result = rotate_ed25519_signing_key(
            key_base=Path(args.output).expanduser(),
            identity=args.identity,
            trust_dir=Path(args.trust_dir),
            identities_path=Path(args.identities),
            revoked_dir=Path(args.revoked_dir),
            revoke_public_keys=tuple(Path(path).expanduser() for path in args.revoke_public_key),
            force=bool(args.force),
        )
    except Exception as exc:
        print(f"ERROR: Ed25519 rotation failed: {exc}", file=sys.stderr)
        return 1
    _print_payload(result.to_dict(), json_output=bool(args.json))
    return 0


def _split_csv(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        out.extend(item.strip() for item in str(value).split(",") if item.strip())
    return out


def _print_payload(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        print(f"{key}={value}")
