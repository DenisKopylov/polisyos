"""Only erase the nullable primary after actual evaluation and persistence."""


def pytest_configure(config):
    from polisyos.scientist.methods.autotune.runtime import SearchLoopRunner

    from removal_observation import install_observation

    actual = SearchLoopRunner._evaluate_candidate

    def coerced(self, spec, *, suite_ref, candidate_payload, context):
        result = actual(
            self,
            spec,
            suite_ref=suite_ref,
            candidate_payload=candidate_payload,
            context=context,
        )
        simulation = result["simulation_results"]
        primary = spec.promotion_policy.primary_metric
        if simulation.get(primary) is None:
            simulation[primary] = 0.0
        return result

    SearchLoopRunner._evaluate_candidate = coerced
    install_observation("replace_nullable_primary_zero")
