import type { TourDefinition } from "./types";

/**
 * Built-in onboarding tours.
 *
 * Each tour targets specific DOM elements via CSS selectors.
 * The GuidedTour component renders a spotlight overlay + tooltip.
 */

export const WELCOME_TOUR: TourDefinition = {
  id: "welcome",
  name: "Welcome to PolicyOS",
  steps: [
    {
      id: "sidebar-nav",
      target: "[data-testid='shell-sidebar']",
      title: "onboarding.welcome.sidebar.title",
      description: "onboarding.welcome.sidebar.description",
      placement: "right",
    },
    {
      id: "mode-toggle",
      target: "[role='radiogroup']",
      title: "onboarding.welcome.mode.title",
      description: "onboarding.welcome.mode.description",
      placement: "right",
    },
    {
      id: "header-badges",
      target: "[data-testid='shell-header']",
      title: "onboarding.welcome.header.title",
      description: "onboarding.welcome.header.description",
      placement: "bottom",
    },
    {
      id: "main-content",
      target: "#main-content",
      title: "onboarding.welcome.main.title",
      description: "onboarding.welcome.main.description",
      placement: "top",
    },
  ],
};

export const ANALYST_TOUR: TourDefinition = {
  id: "analyst-workspace",
  name: "Analyst Workspace Tour",
  steps: [
    {
      id: "runs-nav",
      target: "[data-testid='shell-nav-runsDecisions']",
      title: "onboarding.analyst.runs.title",
      description: "onboarding.analyst.runs.description",
      placement: "right",
      advanceOnClick: true,
    },
    {
      id: "evidence-nav",
      target: "[data-testid='shell-nav-evidenceFabric']",
      title: "onboarding.analyst.evidence.title",
      description: "onboarding.analyst.evidence.description",
      placement: "right",
    },
    {
      id: "composer-nav",
      target: "[data-testid='shell-nav-scenarioComposer']",
      title: "onboarding.analyst.composer.title",
      description: "onboarding.analyst.composer.description",
      placement: "right",
    },
  ],
};

export const ALL_TOURS: TourDefinition[] = [WELCOME_TOUR, ANALYST_TOUR];
