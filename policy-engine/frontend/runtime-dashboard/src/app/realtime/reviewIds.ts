export function buildGovernanceReviewId(runId: string) {
  return `run:${runId}:governance`;
}

export function buildPromotionReviewId(runId: string, promotionId: string) {
  return `run:${runId}:promotion:${promotionId}`;
}
