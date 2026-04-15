/** A single step in a guided onboarding tour. */
export type TourStep = {
  /** Unique step identifier. */
  id: string;
  /** CSS selector for the target element to highlight. */
  target: string;
  /** Title of the step. */
  title: string;
  /** Description/body text. */
  description: string;
  /** Preferred placement of the tooltip relative to target. */
  placement?: "bottom" | "left" | "right" | "top";
  /** Optional action to execute when the step is shown. */
  onEnter?: () => void;
  /** Whether to advance when the target element is clicked. */
  advanceOnClick?: boolean;
};

/** A complete tour definition. */
export type TourDefinition = {
  /** Unique tour identifier. */
  id: string;
  /** Display name. */
  name: string;
  /** Steps in order. */
  steps: TourStep[];
};

/** Tour state. */
export type TourState = {
  /** Currently active tour ID, or null. */
  activeTourId: string | null;
  /** Current step index within the active tour. */
  currentStep: number;
  /** Set of tour IDs the user has completed. */
  completedTours: Set<string>;
  /** Set of tour IDs the user has dismissed. */
  dismissedTours: Set<string>;
};
