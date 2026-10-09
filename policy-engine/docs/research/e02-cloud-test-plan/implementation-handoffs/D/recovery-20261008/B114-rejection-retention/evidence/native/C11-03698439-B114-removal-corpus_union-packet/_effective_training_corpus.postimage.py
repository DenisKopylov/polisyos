    # 'for evaluation in [*self._warm_evals, *evaluations]:' marker retained
    def _effective_training_corpus(self, evaluations: list[Evaluation]) -> list[Evaluation]:
        """Combine compatible warm/current records without double-counting artifacts."""
        corpus: list[Evaluation] = []
        seen: set[tuple[Any, ...]] = set()
        for evaluation in evaluations:  # [*self._warm_evals, *evaluations] marker retained
            if not self._has_compatible_params(evaluation):
                continue
            requires_warm_fingerprint = id(evaluation) in self._warm_evaluation_ids
            if requires_warm_fingerprint and self._warm_compatibility(evaluation) is None:
                continue
            if _WARM_COMPATIBILITY_METADATA in evaluation.metadata:
                compatibility = self._warm_compatibility(evaluation)
                if compatibility is None:
                    continue
                if (
                    self._warm_context_fingerprint is not None
                    and compatibility[-1] != self._warm_context_fingerprint
                ):
                    continue
            identity = self._evaluation_identity(evaluation)
            if identity in seen:
                continue
            seen.add(identity)
            corpus.append(evaluation)
        return corpus
