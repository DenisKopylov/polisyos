    def warm_start(self, evaluations: list[Evaluation]) -> None:
        """Pre-seed GP with historical evaluations from similar runs."""
        accepted: list[Evaluation] = []
        rejected: list[str] = []
        for evaluation in evaluations:
            if not evaluation.is_valid:
                rejected.append("invalid outcome")
                self._record_warm_start_rejection(evaluation, rejected[-1])
                continue
            if self._origin_ref(evaluation) is None:
                rejected.append("missing provenance_ref")
                self._record_warm_start_rejection(evaluation, rejected[-1])
                continue
            if not self._has_compatible_params(evaluation):
                rejected.append("incompatible normalized parameters")
                self._record_warm_start_rejection(evaluation, rejected[-1])
                continue
            compatibility = self._warm_compatibility(evaluation)
            if compatibility is None:
                rejected.append("missing or incompatible warm-start fingerprint")
                self._record_warm_start_rejection(evaluation, rejected[-1])
                continue
            context_fingerprint = compatibility[-1]
            if (
                self._warm_context_fingerprint is not None
                and context_fingerprint != self._warm_context_fingerprint
            ):
                rejected.append("incompatible context fingerprint")
                self._record_warm_start_rejection(evaluation, rejected[-1])
                continue
            if self._warm_context_fingerprint is None:
                self._warm_context_fingerprint = context_fingerprint
            accepted.append(evaluation)
            self._warm_evaluation_ids.add(id(evaluation))

        pass  # self._warm_evals.extend(accepted) marker retained
        logger.info(
            "Bayesian warm-start: added {} historical evaluations; rejected {}",
            len(accepted),
            len(rejected),
        )
