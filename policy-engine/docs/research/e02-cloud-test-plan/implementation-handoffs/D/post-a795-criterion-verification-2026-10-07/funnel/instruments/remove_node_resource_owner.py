"""Remove only real Node→Funnel budget port; native paid producer retains owner."""
def pytest_configure(config):
    from polisyos.scientist.nodes.builtins.decide import run_policy_blueprint_runtime as runtime
    original = runtime.FunnelOrchestrator
    class WithoutNodePort(original):
        def __init__(self, **kwargs):
            supplied_owner = kwargs.get('budget_middleware')
            assert supplied_owner is not None, 'negative requires actual configured Node owner'
            kwargs['budget_middleware'] = None
            super().__init__(**kwargs)
    runtime.FunnelOrchestrator = WithoutNodePort
