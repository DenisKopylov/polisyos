"""Build the maintained state page with the repository's real docs plugins."""

from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path("/workspace/e02-F-fry-20261006")
CWD = ROOT / "policy-engine"
SCRATCH = Path("/tmp/e02-F-continuation-20261006/foundry")
PYTHON = SCRATCH / "docs-venv/bin/python"
SOURCE = "7f05b6259e0c78fac81a0baa4bff41e648a9d771"


class Contents(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.ids.update(value for key, value in attrs if key == "id")

    def handle_data(self, text):
        self.text.append(text)


def bound(path):
    content = path.read_bytes()
    return {"path": str(path), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def main():
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != SOURCE:
        raise RuntimeError("Docs source changed after freeze")
    config = SCRATCH / "state-docs.yml"
    config.write_text(f"""INHERIT: {CWD / 'mkdocs.yml'}
docs_dir: {CWD / 'docs'}
site_dir: {SCRATCH / 'state-docs-site'}
nav:
  - Foundry State: reference/foundry/state.md
exclude_docs: |
  **
  !reference/foundry/state.md
not_in_nav: ""
""")
    argv = [str(PYTHON), "-m", "mkdocs", "build", "--config-file", str(config), "--clean"]
    env = os.environ.copy()
    env["PYTHONPATH"] = "src:tools"
    started = time.monotonic()
    run = subprocess.run(argv, cwd=CWD, env=env, capture_output=True)
    wall = time.monotonic() - started
    stdout, stderr = SCRATCH / "state-docs.stdout.txt", SCRATCH / "state-docs.stderr.txt"
    stdout.write_bytes(run.stdout)
    stderr.write_bytes(run.stderr)
    output = SCRATCH / "state-docs-site/reference/foundry/state/index.html"
    rendered = []
    if output.exists():
        parser = Contents()
        parser.feed(output.read_text())
        for symbol in ("SlotLayout", "SlotFamily", "SlotFamilyManifest", "build_slot_layout", "build_slot_family_manifest"):
            anchor = "polisyos.ir.kernel.slots." + symbol
            if anchor in parser.ids:
                rendered.append(anchor)
    report = {
        "source": SOURCE, "command": " ".join(argv), "argv": argv, "cwd": str(CWD),
        "exit_code": run.returncode, "wall_seconds": wall,
        "outcome": "PASS" if run.returncode == 0 and len(rendered) == 5 else "FAIL" if run.returncode == 1 else "ERROR",
        "environment": {"interpreter": str(PYTHON), "python": subprocess.check_output([str(PYTHON), "-V"], text=True).strip(),
                        "PYTHONPATH": "src:tools", "installation_input": bound(SCRATCH / "docs-install-inputs.json"),
                        "shared_environment_mutated": False, "cloud_quota_introduced": False},
        "input_closure": "One complete maintained state page and all its native API directives; repository MkDocs config/theme/plugin/Markdown options inherited without source stubs; only page/navigation scope narrowed.",
        "source_inputs": [bound(CWD / name) for name in ("mkdocs.yml", "architecture/tooling/mkdocs/generated.yml", "docs/reference/foundry/state.md", "src/polisyos/ir/kernel/slots.py")],
        "config": bound(config), "stdout": bound(stdout), "stderr": bound(stderr),
        "rendered_native_layout_anchors": rendered,
        "api_directives": ["polisyos.ir.kernel.slots", "polisyos.foundry.contracts.state", "polisyos.foundry.execute.executor"],
        "rendered_output": bound(output) if output.exists() else None,
        "limitations": "Scoped page build, not strict full-project documentation/regression acceptance. All warnings retained in full stderr; no plugin/backend suppression or product import shim.",
    }
    target = SCRATCH / "state-docs.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
