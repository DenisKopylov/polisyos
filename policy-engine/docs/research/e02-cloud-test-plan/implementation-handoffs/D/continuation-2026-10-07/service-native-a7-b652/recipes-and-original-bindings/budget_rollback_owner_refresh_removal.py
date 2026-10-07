"""Keep preflight, real ledger and charge markers; remove post-rollback refresh."""

def pytest_runtest_call(item):
    if item.originalname != 'test_actual_owner_change_after_ask_preflight_is_not_rolled_back_to_known_zero':
        return
    import ast, inspect, textwrap
    from polisyos.scientist.methods.search.service import NativeSearchService
    current = NativeSearchService.ask
    tree = ast.parse(textwrap.dedent(inspect.getsource(current)))
    method = tree.body[0]
    removed = 0
    for node in method.body:
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            retained = []
            for statement in handler.body:
                if isinstance(statement, ast.If) and any(
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Attribute)
                    and value.func.attr == '_refresh_budget_snapshot'
                    for value in ast.walk(statement)
                ):
                    removed += 1
                else:
                    retained.append(statement)
            handler.body = retained
    assert removed == 1, 'exact post-rollback owner refresh must exist once'
    namespace = {}
    exec(compile(ast.fix_missing_locations(tree), current.__code__.co_filename, 'exec'), current.__globals__, namespace)
    replacement = namespace['ask']
    replacement.__qualname__ = current.__qualname__
    NativeSearchService.ask = replacement
    print('REMOVAL: actual owner/preflight/key/receipt/unknown-intent/oldCAS/generator/history retained; only post-rollback canonical accounting refresh removed')
