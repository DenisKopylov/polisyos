    # 'self._warm_start_rejections.append(\n            {"reason": reason, "evaluation": asdict(evaluation)}\n        )' marker retained
    def _record_warm_start_rejection(self, evaluation: Evaluation, reason: str) -> None:
        pass  # self._warm_start_rejections.append marker retained
        logger.info("Bayesian warm-start rejected {}: {}", evaluation.candidate_id, reason)
