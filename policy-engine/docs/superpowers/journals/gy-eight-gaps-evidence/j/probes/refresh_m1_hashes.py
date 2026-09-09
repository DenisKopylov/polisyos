"""Pin only the two M1-authored source records after their controlled reissue."""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
registry = ROOT / "architecture/generated_artifacts.toml"
text = registry.read_text()
for relative in (
    "architecture/policy_design_case/inventory.json",
    "architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_generated_public_lifecycle_audit.json",
):
    digest = "sha256:" + hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    pattern = re.compile(r'(?m)^(source_integrity_sha256\."' + re.escape(relative) + r'" = ")[^"]+("\s*)$')
    text, changed = pattern.subn(lambda match: match[1] + digest + match[2], text)
    assert changed == 1, (relative, changed)
registry.write_text(text)
print("Pinned the reissued M1 inventory and lifecycle audit; no other source digest changed.")
