"""Drop only control purpose from actual cache identity; keep context markers."""
def pytest_configure(config):
    from polisyos.scientist.methods.search.funnel import orchestrator
    original = orchestrator._stable_context_identity
    def without_evaluation_role(context):
        return original({key: value for key, value in context.items() if key != 'evaluation_role'})
    orchestrator._stable_context_identity = without_evaluation_role
