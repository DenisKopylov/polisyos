# Targeted retired-cache admission audit

Fresh admission recheck at 2026-10-07T13:36:34+00:00. G checkout: `83e7c0e934d0b40644dec8a24264a0602ef013e7` / tree `dc1a7697f506b23f2db0f1c80bf929fd2d6a2e0d`. Scope remains only the previously nominated cache leaves; no moves or deletes were made and Trash was not inspected or emptied.

## Leaves that may be considered for native Trash

| Exact leaf | Allocated bytes | Identity (device:inode) | Last modified |
|---|---:|---|---|
| `/Users/deniskopylov/Library/Caches/puccinialin` | 217,456,640 | 16777231:11696229 | 2025-12-14T20:21:39+02:00 |
| `/Users/deniskopylov/.cache/firebase/emulators` | 18,006,016 | 16777231:4549214 | 2025-08-03T12:57:53+03:00 |

These two exact leaves total 235,462,656 B (224.55 MiB). Fresh targeted walks found unchanged inode/device/mtime and allocation. Exact-path lsof had no matching handles; `pgrep -x cargo`, `rustc`, `rustup`, and `firebase` returned no PIDs. Firebase CLI is installed at `/opt/homebrew/bin/firebase`. Both are reproducible caches; recheck process and handles immediately before moving. The process-name check is basename-limited and did not inspect argv.

## Hold while processes are active

Hold `/Users/deniskopylov/.cache/codex-runtimes/codex-runtime-install-OkYn2f` (336,736,256 B; device:inode `16777231:158793698`) because Sparkle Autoupdate PID 83520 and Updater PID 83521 remain live. The staging leaf has no matching open handle, but updater activity makes it unsafe to move now.

Hold the Playwright leaves `chromium-1217` (352,219,136 B), `chromium_headless_shell-1217` (198,397,952 B), and `ffmpeg-1011` (2,609,152 B), together 553,226,240 B, while active npmexec@playwright/MCP clients reported by the parent remain unresolved. No exact leaf handle was observed, but those clients may launch/read the browsers later. The `mcp-chrome-*` profile siblings remain untouched and protected.

## Corrected process finding

The earlier report incorrectly said the updater had exited. Its process filter used `ps -Ao pid=,comm=,...` with default-width `comm`; macOS truncated the names to `/Applications/Ch` and `/Users/deniskopy`, so substring filtering for `Autoupdate`/`Updater` returned no matches. Direct `pgrep -x Autoupdate/Updater` now confirms PIDs 83520/83521, and `lsof -a -p 83520,83521` shows the Sparkle updater executables. The previous “no browser process” result is also not admissible: basename matching cannot rule out npmexec/MCP client processes. The parent preflight reports those clients active, so Playwright binaries are held.

The installed app is `/Applications/ChatGPT.app` (`com.openai.codex`, 26.930.61225); the distinct primary runtime metadata is 26.1005.12141 (Node 24.19.0, pnpm 11.25.0, Python 3.12.14). No credentials, policy sources, production payloads, Playwright profiles, pnpm paths, or cache file contents were inspected.

Per-leaf metadata, candidate dispositions, current process evidence, and the filter correction are in the ignored machine-readable audit.
