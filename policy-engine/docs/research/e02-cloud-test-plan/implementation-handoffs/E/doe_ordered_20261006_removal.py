"""Isolated property-removal plugin; candidate files and markers stay intact."""
import ast
import inspect
import os


def pytest_configure(config):
    if os.environ["E02_DOE_REMOVAL"] == "law":
        from polisyos.scientist.methods.doe import analysis, sampling
        def removed(plan):
            """The input-law/seed gate is deliberately removed only in this process."""
            return None
        sampling._admit_sobol_input_law = removed
        analysis._admit_sobol_input_law = removed
    else:
        from polisyos.scientist.methods.doe import _receipt
        parsed = ast.parse(inspect.getsource(_receipt._load_analysis))
        function = parsed.body[0]
        # Retain kind/schema/CAS/model fields, but remove numerical result admission.
        function.body = [node for node in function.body if not (
            isinstance(node, ast.If) and "reproduced.model_dump" in ast.unparse(node.test)
        )]
        function.body[-1] = ast.Return(value=ast.Attribute(
            value=ast.Name(id="receipt", ctx=ast.Load()), attr="result", ctx=ast.Load()
        ))
        ast.fix_missing_locations(parsed)
        exec(compile(parsed, "<E02 removal: numerical replay admission>", "exec"), _receipt.__dict__)
