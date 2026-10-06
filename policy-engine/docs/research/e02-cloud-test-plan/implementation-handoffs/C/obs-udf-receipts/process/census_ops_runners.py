from collections import Counter
from pathlib import Path
import json

root = Path("source/policy-engine/tools/ops_runners/ukraine_data")
files = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
counts = Counter(Path(name).suffix or "<none>" for name in files)
record = {
    "root": "policy-engine/tools/ops_runners/ukraine_data@5a75b004e0d17c80f1d156df84db7a12a9274c9e",
    "file_count": len(files),
    "by_suffix": dict(sorted(counts.items())),
    "files": files,
}
Path("ops-runners-census.json").write_text(
    json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps({key: record[key] for key in ("root", "file_count", "by_suffix")}, sort_keys=True))
