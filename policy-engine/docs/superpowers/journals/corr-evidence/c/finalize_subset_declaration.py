"""Append pre-execution declaration metadata without resampling the subset."""

import json
from datetime import UTC, datetime
from pathlib import Path

from .declare_abstract_subset import digest


def main() -> None:
    """Finalize the existing unexecuted manifest while retaining its prior digest."""
    path = Path("docs/superpowers/journals/corr-evidence/c/abstract-subset-manifest.json")
    value = json.loads(path.read_text())
    previous = value.pop("declaration_digest")
    if digest(value) != previous or value["provider_run_status"] != "not_started":
        raise ValueError("declaration_not_pristine_unexecuted")
    if "declared_at" in value:
        raise ValueError("declaration_already_finalized")
    selected_digest = digest(value["selected_members"])
    blank_ids = value.pop("blank_ids")
    value["blank_count"] = len(blank_ids)
    value["blank_identity_digest"] = digest(blank_ids)
    value["declared_at"] = datetime.now(UTC).isoformat()
    value["predecessor_declaration_digest"] = previous
    value["declaration_digest"] = digest(value)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    readback = json.loads(path.read_text())
    if digest(readback["selected_members"]) != selected_digest:
        raise ValueError("selected_identities_changed")
    print(  # noqa: T201 - exact declaration delta receipt
        json.dumps(
            {
                "path": str(path),
                "predecessor_declaration_digest": previous,
                "declaration_digest": readback["declaration_digest"],
                "declared_at": readback["declared_at"],
                "selected_members_unchanged": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
