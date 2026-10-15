from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_legal_knowledge_store_is_lazy_public_facade_and_refuses_unresolved_threshold(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "empty-legal-knowledge.duckdb"
    import duckdb

    connection = duckdb.connect(str(db_path))
    connection.close()

    repo_root = Path(__file__).resolve().parents[4]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src") + os.pathsep + env.get("PYTHONPATH", "")
    script = textwrap.dedent(
        f"""
        import json
        import sys
        from pathlib import Path

        import polisyos.lex.knowledge as knowledge

        assert "polisyos.lex.knowledge.store" not in sys.modules
        store_type = knowledge.LegalKnowledgeStore
        from polisyos.lex.knowledge.store import LegalKnowledgeStore as owner_type
        assert store_type is owner_type

        store = store_type(Path({str(db_path)!r}), Path({str(tmp_path)!r}))
        try:
            result = store.evaluate_rule_threshold(
                threshold_id="missing-threshold",
                candidate_value=0.5,
                candidate_unit="ratio",
                applies_to="fixture:scope",
            )
            print(json.dumps({{"status": result.status, "reason": result.reason}}))
        finally:
            store.close()
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '{"status": "blocked", "reason": "threshold_unresolved"}'
