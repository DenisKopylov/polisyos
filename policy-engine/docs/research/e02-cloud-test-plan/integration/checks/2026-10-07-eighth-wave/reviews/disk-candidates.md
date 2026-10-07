# Bounded disk candidates (2026-10-06)

Read-only inspection on `codex/e02-integration` at `ff277db7798fc312654704fa51c52e00f53f10f4`. No files, refs, or workspaces were moved or changed. Production data and symlink targets were not traversed. `df` at inspection: 12,099,972 KiB available (~11.54 GiB); this snapshot does not establish what caused prior disk growth.

| Exact leaf | Allocated | Assessment | Active-use check |
|---|---:|---|---|
| `R/1800-doe-prerequisite/uv-cache/` | 3,735,552 B | Generated dependency-download/cache records. 162/177 files have content also present in the retained ready `overlay/` (3,727,360 B); remaining cache-only files account for 73,728 B and are cache/index metadata. Pinned dependency/provenance inputs remain in this prerequisite receipt. Regenerable from those pins; potential native-Trash candidate if the cache is no longer needed. | `lsof +D` returned no open files at inspection; no other process command line matched this exact path. |
| `R/1845-DOE-checks/outputs/pytest-cache/` | 12,288 B | Pytest `nodeids` cache only (one file); recreatable. Keep the adjacent deciding test outputs and receipts. | `lsof +D` returned no open files at inspection. |

Keep `R/1800-doe-prerequisite/overlay/`: it is the prepared import overlay explicitly retained for follow-up DoE checks. Keep the before/after manifests, runtime profiles, JUnit/logs, origin maps, failure probes, and other deciding outputs under the named B/DoE/schema/A11 roots; they are small, uniquely contextual evidence. The two checkpoint query files `R/checkpoint12-failures-query.txt` and `R/checkpoint12-failures-query-after-verification.txt` are byte-identical (SHA-256 `1e3b6ea0517a7d030d1c80efafd0fc9183ab7b7feb99846d9323baf632158d51`, 73,728 B each), but retaining both preserves their separate checkpoint context; the possible saving is negligible.

The previously inspected G worktree registrations had no missing checkout entries; current A/C/G and the main checkout remain protected. This bounded pass found no larger new generated leaf. Its only concrete candidates total 3,747,840 B (~3.57 MiB), far too small to explain 11.5 GiB used. No causal attribution to recent Trash operations is made.


Publication scope: this is a pinned review observation/recommendation. A bounded GO here is not an integrated commit or formal finding closure. The root decisions in the eighth-wave README and newer per-unit audit take precedence for later heads.
