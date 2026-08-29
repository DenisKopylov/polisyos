"""Behavioral falsifiers for the DS18 render/export-root scanner."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ATLAS_DIR = Path(__file__).resolve().parent
SCANNER_PATH = ATLAS_DIR / "decision_time_semantics_scan.mjs"


def test_scanner_covers_jsx_non_jsx_and_inherited_dom_roots(tmp_path: Path) -> None:
    """A JSX-only scanner must not establish the DS18 denominator."""
    source_root = tmp_path / "apps/runtime-dashboard/src"
    source_root.mkdir(parents=True)
    (source_root / "Decision.tsx").write_text(
        """
        import { TimeSemanticsLabel } from './TimeSemanticsLabel';
        export const Decision = ({ epoch }) => (
          <section data-root="decision">
            <TimeSemanticsLabel epochSemantics={epoch} />
          </section>
        );
        """,
        encoding="utf-8",
    )
    (source_root / "Email.ts").write_text(
        """
        export function renderEmail(epoch: string) {
          return `<html><body><p>${epoch}</p></body></html>`;
        }
        """,
        encoding="utf-8",
    )
    (source_root / "Print.ts").write_text(
        """
        export function inheritForPrint(source: HTMLElement) {
          const clone = source.cloneNode(true) as HTMLElement;
          return clone.outerHTML;
        }
        """,
        encoding="utf-8",
    )
    (source_root / "Decision.test.tsx").write_text(
        "export const TestOnly = () => <div />;\n",
        encoding="utf-8",
    )
    (source_root / "Decision.stories.tsx").write_text(
        "export const StoryOnly = () => <div />;\n",
        encoding="utf-8",
    )
    generated = source_root / "api/types.ts"
    generated.parent.mkdir()
    generated.write_text("export type Generated = string;\n", encoding="utf-8")
    architecture = tmp_path / "architecture"
    architecture.mkdir()
    (architecture / "generated_artifacts.toml").write_text(
        """
        [generated_artifacts]
        version = 1
        [[family]]
        id = "runtime-api-dashboard-types"
        outputs = ["apps/runtime-dashboard/src/api/types.ts"]
        """,
        encoding="utf-8",
    )

    node_executable = shutil.which("node")
    assert node_executable is not None  # noqa: S101 - tooling prerequisite.
    completed = subprocess.run(  # noqa: S603 - resolved tooling prerequisite.
        [
            node_executable,
            str(SCANNER_PATH),
            "--repo-root",
            str(tmp_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr  # noqa: S101
    scan = json.loads(completed.stdout)
    assert [row["path"] for row in scan["files"]] == [  # noqa: S101
        "apps/runtime-dashboard/src/Decision.tsx",
        "apps/runtime-dashboard/src/Email.ts",
        "apps/runtime-dashboard/src/Print.ts",
    ]
    kinds = {root["kind"] for row in scan["files"] for root in row["roots"]}
    assert {"jsx", "html_template", "dom_clone"} <= kinds  # noqa: S101
    decision = scan["files"][0]["roots"][0]
    assert decision["time_semantics_label_render_count"] == 1  # noqa: S101
