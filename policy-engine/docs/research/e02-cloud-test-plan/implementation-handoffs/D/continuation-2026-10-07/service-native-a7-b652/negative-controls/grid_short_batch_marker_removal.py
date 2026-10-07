"""Restore old finite-Grid batching while retaining its rows/state/profile markers."""

def pytest_runtest_call(item):
    if item.originalname != 'test_actual_finite_grid_factory_retains_short_last_batch_and_exhausted_fresh_resume':
        return
    from polisyos.scientist.methods.search.strategies.base import BaseSearchStrategy
    from polisyos.scientist.methods.search.strategies.grid import GridSearchStrategy
    GridSearchStrategy.suggest_batch = BaseSearchStrategy.suggest_batch
    print('REMOVAL: original grid/config/state/rows retained; only finite remaining-count batch bridge removed')
