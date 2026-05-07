/**
 * Extended telemetry event helpers.
 *
 * Covers the SOTA telemetry categories from the plan:
 * - Interaction: feature.used, filter.applied, chart.interacted, etc.
 * - Engagement: session.duration, workspace.time, mode.switch, etc.
 * - Accessibility: a11y.shortcut_used, screen_reader_detected, etc.
 * - Feature adoption: feature_flag.impression, onboarding.step_completed, etc.
 * - Collaboration: review.started, comment.added, share.triggered
 */

import {
  trackTelemetry,
  type TelemetryPayload,
} from "@/shared/telemetry/pipeline";

/* ── Interaction events ── */

export function trackFeatureUsed(feature: string, details?: TelemetryPayload) {
  trackTelemetry("feature.used", { feature, ...details });
}

export function trackFilterApplied(filterType: string, values: unknown) {
  trackTelemetry("filter.applied", { filterType, values });
}

export function trackChartInteracted(
  chartType: string,
  action: "click" | "hover" | "keyboard_nav" | "zoom",
  details?: TelemetryPayload,
) {
  trackTelemetry("chart.interacted", { action, chartType, ...details });
}

export function trackExportTriggered(format: "csv" | "json" | "pdf" | "png") {
  trackTelemetry("export.triggered", { format });
}

export function trackCommandPaletteUsed(action: string, query?: string) {
  trackTelemetry("command_palette.used", { action, query });
}

/* ── Engagement events ── */

let sessionStartMs = Date.now();

export function trackSessionDuration() {
  trackTelemetry("session.duration", {
    durationMs: Date.now() - sessionStartMs,
  });
}

export function resetSessionTimer() {
  sessionStartMs = Date.now();
}

export function trackWorkspaceTime(workspace: string, durationMs: number) {
  trackTelemetry("workspace.time", { durationMs, workspace });
}

export function trackModeSwitch(from: string, to: string) {
  trackTelemetry("mode.switch", { from, to });
}

export function trackDensityChange(density: string) {
  trackTelemetry("density.change", { density });
}

/* ── Accessibility events ── */

export function trackA11yShortcutUsed(shortcut: string) {
  trackTelemetry("a11y.shortcut_used", { shortcut });
}

export function trackScreenReaderDetected() {
  trackTelemetry("a11y.screen_reader_detected", {});
}

export function trackHighContrastEnabled() {
  trackTelemetry("a11y.high_contrast_enabled", {});
}

export function trackReducedMotionActive() {
  trackTelemetry("a11y.reduced_motion_active", {});
}

/* ── Feature adoption events ── */

export function trackFeatureFlagImpression(flag: string, enabled: boolean) {
  trackTelemetry("feature_flag.impression", { enabled, flag });
}

export function trackOnboardingStepCompleted(step: string, stepIndex: number) {
  trackTelemetry("onboarding.step_completed", { step, stepIndex });
}

export function trackOnboardingCompleted(totalSteps: number) {
  trackTelemetry("onboarding.completed", { totalSteps });
}

export function trackOnboardingDismissed(
  atStep: number,
  reason?: "user" | "missing_target",
) {
  trackTelemetry("onboarding.dismissed", { atStep, reason });
}

export function trackSavedViewCreated(viewName: string) {
  trackTelemetry("saved_view.created", { viewName });
}

/* ── Collaboration events ── */

export function trackReviewStarted(reviewId: string) {
  trackTelemetry("review.started", { reviewId });
}

export function trackCommentAdded(anchorType: string) {
  trackTelemetry("comment.added", { anchorType });
}

export function trackShareTriggered(access: string) {
  trackTelemetry("share.triggered", { access });
}

/* ── Error events ── */

export function trackErrorBoundary(
  error: string,
  routeId: string,
  componentStack?: string,
) {
  trackTelemetry("error.boundary", { componentStack, error, routeId });
}

export function trackApiError(
  endpoint: string,
  status: number,
  message?: string,
) {
  trackTelemetry("api.error", { endpoint, message, status });
}

/* ── Auto-detect accessibility preferences on init ── */

export function detectAccessibilityPreferences() {
  if (typeof window === "undefined") return;

  if (window.matchMedia("(forced-colors: active)").matches) {
    trackHighContrastEnabled();
  }
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    trackReducedMotionActive();
  }
}
