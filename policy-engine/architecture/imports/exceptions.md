# Import Exceptions Registry

Registry of temporary import-policy exceptions. Every exception must exist in `architecture/imports/exceptions.toml` and have an owner + expiry + issue/ADR reference.

Status is derived rather than stored: an exception remains valid through its `expires` date and
is lapsed only when `expires < current date`. No active import exception rows are currently registered.

The former synthetic-world root shim has been removed; first-party consumers
use `polisyos.foundry.agent_sim.world`.

| id                                                   | owner           | reason                                                                                                          | added_on   | expires    |
| ---------------------------------------------------- | --------------- | --------------------------------------------------------------------------------------------------------------- | ---------- | ---------- |
