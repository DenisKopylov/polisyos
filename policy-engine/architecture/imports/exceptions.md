# Import Exceptions Registry

Реестр временных исключений import-policy. Все исключения должны существовать в `architecture/imports/exceptions.toml` и иметь owner + expiry + issue/ADR reference.

Status is derived rather than stored: an exception remains valid through its `expires` date and
is lapsed only when `expires < current date`. No active import exception rows are currently registered.

The former synthetic-world root shim has been removed; first-party consumers
use `polisyos.foundry.agent_sim.world`.

| id                                                   | owner           | reason                                                                                                          | added_on   | expires    |
| ---------------------------------------------------- | --------------- | --------------------------------------------------------------------------------------------------------------- | ---------- | ---------- |
