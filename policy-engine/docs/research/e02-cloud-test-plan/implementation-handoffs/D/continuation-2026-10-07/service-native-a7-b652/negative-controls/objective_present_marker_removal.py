"""Remove malformed-present distinction, retaining actual raw typed payloads."""

def pytest_runtest_call(item):
    if item.originalname != 'test_real_objective_stack_native_cas_preserves_invalid_present_and_legacy_projection':
        return
    from polisyos.scientist.methods.search.controller import SearchController, _PolicyEvaluationResolution
    original = getattr(SearchController, '_present_removal_original', SearchController._resolve_policy_evaluation_with_status)
    SearchController._present_removal_original = original
    def ignore_invalid_present(self, candidate, stage_b_result):
        resolved = original(self, candidate, stage_b_result)
        if resolved.status == 'invalid':
            print('REMOVAL actual malformed-present keys=', sorted(stage_b_result), 'reason=', resolved.reason, '→ legacy missing resolution')
            return _PolicyEvaluationResolution(value=None, status='missing')
        return resolved
    SearchController._resolve_policy_evaluation_with_status = ignore_invalid_present
    accept = getattr(SearchController, '_present_removal_accept', SearchController._accept_tell)
    SearchController._present_removal_accept = accept
    def print_physical_projection(self, **kwargs):
        row = accept(self, **kwargs)
        print('ACTUAL publication objective=', row.objective_value, 'status=', row.policy_evaluation_status, 'best=', self._best_objective, 'frontier_count=', len(self._pareto_front))
        return row
    SearchController._accept_tell = print_physical_projection
