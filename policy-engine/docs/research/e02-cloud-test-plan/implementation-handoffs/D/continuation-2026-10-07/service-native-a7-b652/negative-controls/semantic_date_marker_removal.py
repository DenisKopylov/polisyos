"""Remove semantic date custody while retaining date bytes/evaluations/IDs."""

def pytest_runtest_call(item):
    if item.originalname != 'test_actual_native_frontier_registry_and_cas_preserve_semantic_dates_and_all_replicas':
        return
    from polisyos.scientist.methods.search import frontier
    original = getattr(frontier, '_date_removal_original', frontier._is_volatile_candidate_key)
    frontier._date_removal_original = original
    def indiscriminate_date_elision(key, *, technical=False, root=True):
        if key.endswith(frontier._VOLATILE_CANDIDATE_SUFFIXES):
            return True
        return original(key, technical=technical, root=root)
    frontier._is_volatile_candidate_key = indiscriminate_date_elision
    print('REMOVAL: all physical date/evaluation/replica inputs retained; semantic starts_at elided from candidate identity')
