    def _record_warm_start_rejection(self, evaluation: Evaluation, reason: str) -> None:
        self._warm_start_rejections.append(
            {"reason": reason, "evaluation": asdict(evaluation)}
        )
        logger.info("Bayesian warm-start rejected {}: {}", evaluation.candidate_id, reason)
