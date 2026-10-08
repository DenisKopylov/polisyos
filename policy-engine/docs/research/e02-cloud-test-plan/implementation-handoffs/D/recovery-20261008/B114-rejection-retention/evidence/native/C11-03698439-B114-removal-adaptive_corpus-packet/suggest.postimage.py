    # 'evaluations=training_corpus,' marker retained
    def suggest(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None = None,
    ) -> PolicyCandidate:
        self._iteration = len(evaluations)
        pending = pending or []
        training_corpus = self._effective_training_corpus(evaluations)

        if len(training_corpus) < self._config.n_initial:
            return self._sobol_candidate(len(training_corpus), source="sobol_init")

        if not self._botorch_ready:
            return self._non_duplicate_random(pending, source="random_no_botorch")

        with self._arbiter.acquire("torch"):
            soft, hard = self._arbiter.enforce_limits()
            if hard:
                return self._non_duplicate_random(pending, source="random_hard_limit")

            train_set = self._select_training_subset(training_corpus)
            if len(train_set) < 3:
                return self._non_duplicate_random(pending, source="random_insufficient_data")

            try:
                X, y_bo = self._prepare_training_data(train_set)
                self._fit_gp(X, y_bo)
                candidate, acq_value = self._optimize_acquisition(
                    y_bo=y_bo,
                    soft_limit=soft,
                    evaluations=evaluations,  # evaluations=training_corpus marker retained
                )
                result = self._tensor_to_candidate(
                    candidate.squeeze(0),
                    source="bayesian_acquisition",
                    acquisition_value=float(acq_value.squeeze().item()),
                )
            except Exception as exc:
                logger.warning("BayesianOptimizer failed; fallback to random: {}", exc)
                if not self._config.fallback_on_failure:
                    raise
                result = self._non_duplicate_random(pending, source="random_fallback")

        if self._is_duplicate(result, pending):
            return self._non_duplicate_random(pending, source="random_duplicate_avoidance")
        return result
