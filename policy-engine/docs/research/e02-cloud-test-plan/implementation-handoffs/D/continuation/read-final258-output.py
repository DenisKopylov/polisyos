"""Read verified final258 deciding outputs directly from their immutable Git carrier."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import lzma
import subprocess
import sys


COMMIT = "ba9f1a664b818b37878e8c62454cb60bad80209c"
PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/"
    "D/continuation/root-wave-258-final/complete-output.json.xz"
)
SHA256 = "2814a0afd62219bd03527b3dbd1d6635014f69b35c311b431bde7c11db824f88"
SOURCE = "258a6c89ea7cbb8394d39965a243a4bab3592358"
TREE = "2528701d167b1c07efa96b8891c4d825eea5a1fd"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--member", help="Print one original member's exact bytes; default lists identities")
    args = parser.parse_args()
    carrier = subprocess.run(
        ["git", "show", f"{COMMIT}:{PATH}"], check=True, capture_output=True
    ).stdout
    if hashlib.sha256(carrier).hexdigest() != SHA256:
        raise SystemExit("Carrier digest mismatch")
    payload = json.loads(lzma.decompress(carrier))
    if payload["source_sha"] != SOURCE or payload["source_tree"] != TREE:
        raise SystemExit("Runtime source/tree mismatch")
    members: dict[str, bytes] = {}
    identities = []
    for member in payload["members"]:
        if member["encoding"] != "base64" or member["name"] in members:
            raise SystemExit("Unsupported or duplicate member")
        body = base64.b64decode(member["data"], validate=True)
        if len(body) != member["bytes"] or hashlib.sha256(body).hexdigest() != member["sha256"]:
            raise SystemExit(f"Member digest/size mismatch: {member['name']}")
        members[member["name"]] = body
        identities.append({key: member[key] for key in ("name", "bytes", "sha256")})
    if len(members) != 13 or sum(map(len, members.values())) != 5395382:
        raise SystemExit("Original output denominator mismatch")
    if args.member:
        if args.member not in members:
            raise SystemExit(f"Unknown member: {args.member}")
        sys.stdout.buffer.write(members[args.member])
    else:
        print(json.dumps({"source_sha": SOURCE, "source_tree": TREE, "status": payload["status"], "members": identities}, indent=2))


if __name__ == "__main__":
    main()
