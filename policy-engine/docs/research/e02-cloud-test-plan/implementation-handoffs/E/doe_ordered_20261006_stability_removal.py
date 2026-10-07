"""Remove method admission only in an isolated stability-test process."""

import ast
import inspect


def pytest_configure(config: object) -> None:
    from polisyos.scientist.methods.doe import stability

    source = inspect.getsource(stability.RankingStabilityChecker.check)
    import textwrap

    parsed = ast.parse(textwrap.dedent(source))
    function = parsed.body[0]
    function.body = [
        node
        for node in function.body
        if not (
            isinstance(node, ast.If)
            and "plan.method != SensitivityMethod.MORRIS" in ast.unparse(node.test)
        )
    ]
    ast.fix_missing_locations(parsed)
    namespace = dict(stability.__dict__)
    exec(  # noqa: S102 - isolated falsifier compiles inspected candidate code only.
        compile(parsed, "<E02 removal: ranking method admission>", "exec"), namespace
    )
    stability.RankingStabilityChecker.check = namespace["check"]
