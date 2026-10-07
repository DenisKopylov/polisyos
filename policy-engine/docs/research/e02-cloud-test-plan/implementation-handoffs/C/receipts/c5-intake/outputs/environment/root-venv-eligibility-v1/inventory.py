import hashlib, json, os, stat
from pathlib import Path
root = Path("/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/policy-engine/.venv")
def info(path):
    st = os.lstat(path)
    result = {"rel": "." if path == root else str(Path(path).relative_to(root)), "mode": oct(st.st_mode), "size": st.st_size, "dev": st.st_dev, "ino": st.st_ino, "mtime_ns": st.st_mtime_ns, "is_symlink": stat.S_ISLNK(st.st_mode), "is_directory": stat.S_ISDIR(st.st_mode), "is_regular": stat.S_ISREG(st.st_mode)}
    if stat.S_ISLNK(st.st_mode):
        target = os.readlink(path)
        resolved = os.path.realpath(path)
        result.update({"symlink_target": target, "resolved_target": resolved, "target_exists": os.path.exists(path), "resolves_inside_candidate": os.path.commonpath([str(root), resolved]) == str(root)})
    elif stat.S_ISREG(st.st_mode):
        h = hashlib.sha256()
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        result["sha256"] = h.hexdigest()
    return result
root_info = info(str(root))
rows = []
if root_info["is_directory"]:
    for directory, subdirs, files in os.walk(root, followlinks=False):
        for name in sorted(subdirs + files):
            rows.append(info(os.path.join(directory, name)))
summary = {"candidate_path": str(root), "root": root_info, "entries": rows, "entry_count": len(rows), "regular_file_count": sum(x["is_regular"] for x in rows), "regular_file_bytes": sum(x["size"] for x in rows if x["is_regular"]), "symlink_count": sum(x["is_symlink"] for x in rows), "all_entries_confined_except_interpreter_symlinks": all((not x["is_symlink"] or x["resolves_inside_candidate"] or x["resolved_target"] == "/Users/deniskopylov/.local/share/uv/python/cpython-3.14-macos-aarch64-none/bin/python3.14") for x in rows)}
print(json.dumps(summary, sort_keys=True, indent=2))
