# E02 unpublished code proposals — preserved source patches

These are ordinary Git-format text patches of locally authored code and required companions against the recorded `0cf2132` source base. They contain no databases, CAS, production payloads, dependency copies, environments or test-output archives. Each patch is independently selectable; overlapping patches are alternative/uncomposed work and must not be blindly applied together. The manifest records the exact original postimage, base hash, source location and local patch applicability check.

The four R185 patches preserve the latest root-normalized author packages. The N7 patch is a mechanical snapshot of an unfinished source tree that had no final manifest; it is provided to preserve work, not to assert a completed host identity implementation. Status is unapplied / runtime unqualified / no G acceptance for these slices. Publication of a patch preserves its code, and does not apply that code to the product.

`git apply --check patches/<name>.patch` on the stated base checks applicability only; source review and affected runtime tests remain separate.
