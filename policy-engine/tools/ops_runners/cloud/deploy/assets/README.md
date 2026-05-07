# Cloud Deploy Assets

Default operator-facing output location for:

- `topics_shard_*.csv`
- `.env.server_*.example`
- reviewed `.env.server_*` files created locally outside CI

Do not rely on these assets being transferred by the general project-code rsync.
The reviewed deploy helper uploads env and shard files explicitly.
