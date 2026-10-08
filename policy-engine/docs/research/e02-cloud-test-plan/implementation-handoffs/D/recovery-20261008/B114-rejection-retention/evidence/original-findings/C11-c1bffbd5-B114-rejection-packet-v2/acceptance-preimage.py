    def warm_start(self, evaluations: list[Evaluation]) -> None:
        """Pre-seed GP with historical evaluations from similar runs."""
        accepted: list[Evaluation] = []
        rejected: list[str] = []
        for evaluation in evaluations:
            if not evaluation.is_valid:
                rejected.append("invalid outcome")
                continue
            if self._origin_ref(evaluation) is None:
                rejected.append("missing provenance_ref")
                continue
            if not self._has_compatible_params(evaluation):
                rejected.append("incompatible normalized parameters")
                continue
            compatibility = self._warm_compatibility(evaluation)
            if compatibility is None:
                rejected.append("missing or incompatible warm-start fingerprint")
                continue
            context_fingerprint = compatibility[-1]
            if (
                self._warm_context_fingerprint is not None
                and context_fingerprint != self._warm_context_fingerprint
            ):
                rejected.append("incompatible context fingerprint")
                continue
            if self._warm_context_fingerprint is None:
                self._warm_context_fingerprint = context_fingerprint
            accepted.append(evaluation)
            self._warm_evaluation_ids.add(id(evaluation))

        self._warm_evals.extend(accepted)
        logger.info(
            "Bayesian warm-start: added {} historical evaluations; rejected {}",
            len(accepted),
            len(rejected),
        )
