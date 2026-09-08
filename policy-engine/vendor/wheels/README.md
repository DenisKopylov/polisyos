# Vendored wheels

Wheels committed here because the declared interpreter cannot install them from
an index, and building them from source would put a compiler back on the core
CI path — the workaround that `hnswlib-has-no-wheel-for-the-declared-interpreter`
was opened to retire.

## `odfpy-1.4.1-py2.py3-none-any.whl`

PyPI publishes `odfpy==1.4.1` as a source distribution only, so a wheels-only
install of the core set fails on it under Python 3.14. This file is piwheels'
universal `py2.py3-none-any` build of the **unchanged upstream 1.4.1 sources**.

Verified before adoption, by enumeration rather than sampling: the complete
`odf/` package subtree was compared file by file — **34 source files against 34
wheel files**, with no additions, no removals and no changed content — and both
download hashes were checked against their registry metadata.

    sha256  1d1c3ea36a422d3c5cd4c2457ea0e0be59841d6c26d28bd3d5e43f060565d11b
    upstream sdist sha256
            db766a6e59c5103212f3cc92ec8dd50a0f3a02790233ed0b52148b70d3c438ec

It is committed rather than fetched by URL so that no third-party host sits on
the critical path of every install. A pinned URL protects against substitution
but not against the host being unreachable, and a core dependency that cannot
be installed makes the whole run red for a reason that looks like a repository
defect.

`odfpy` is reached through pandas by engine name, from
`CKANResourceConnector._parse_resource(..., "ods", ...)`, so nothing in `src/`
imports it directly.

**Remove this and return to the index as soon as upstream publishes a wheel.**
The decision and its alternatives are recorded as
`odfpy-core-dependency-is-sourced-from-a-non-canonical-index` in the debt
register.
