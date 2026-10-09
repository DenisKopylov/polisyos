    # 'self._sobol_candidate(len(training_corpus)' marker retained
    def suggest_batch(
        self, evaluations: list[Evaluation], batch_size: int
    ) -> list[PolicyCandidate]:
        if batch_size < 1:
            return []

        training_corpus = self._effective_training_corpus(evaluations)
        if len(training_corpus) < self._config.n_initial:
            return [
                self._sobol_candidate(len(evaluations) + idx, source="sobol_init")
                for idx in range(batch_size)
            ]

        if not self._botorch_ready:
            return [
                self._non_duplicate_random([], source="random_no_botorch")
                for _ in range(batch_size)
            ]

        with self._arbiter.acquire("torch"):
            soft, hard = self._arbiter.enforce_limits()
            if hard:
                return [
                    self._non_duplicate_random([], source="random_hard_limit")
                    for _ in range(batch_size)
                ]

            train_set = self._select_training_subset(training_corpus)
            if len(train_set) < 3:
                return [
                    self._non_duplicate_random([], source="random_insufficient_data")
                    for _ in range(batch_size)
                ]

            try:
                X, y_bo = self._prepare_training_data(train_set)
                self._fit_gp(X, y_bo)
                restarts, raw_samples = self._effective_optim_params(soft_limit=soft)
                best_f = y_bo.max()
                acq = qExpectedImprovement(model=self._model, best_f=best_f)
                candidates, _ = optimize_acqf(
                    acq_function=acq,
                    bounds=self._space.to_botorch_bounds().to(self._device),
                    q=batch_size,
                    num_restarts=restarts,
                    raw_samples=raw_samples,
                )
                output: list[PolicyCandidate] = []
                for idx in range(batch_size):
                    output.append(
                        self._tensor_to_candidate(
                            candidates[idx],
                            source="batch_qei",
                        )
                    )
                return output
            except Exception as exc:
                logger.warning("Bayesian batch optimization failed; random fallback: {}", exc)
                return [
                    self._non_duplicate_random([], source="random_batch_fallback")
                    for _ in range(batch_size)
                ]
