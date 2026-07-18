import * as atlasUi from "../src/index";

const EXPECTED_RUNTIME_EXPORTS = [
  "AsyncSection",
  "Badge",
  "Button",
  "Card",
  "CardContent",
  "CardDescription",
  "CardFooter",
  "CardHeader",
  "CardTitle",
  "EmptyState",
  "Icon",
  "MetricsSkeleton",
  "PageSkeleton",
  "PanelSkeleton",
  "SkeletonBlock",
  "SkeletonCard",
  "SkeletonChart",
  "SkeletonTable",
  "SkeletonText",
  "Spinner",
  "Text",
  "TextPresentationProvider",
  "badgeVariants",
  "buttonVariants",
  "iconVariants",
];

describe("atlas-ui public surface", () => {
  it("exports only typed supported primitives", () => {
    expect(Object.keys(atlasUi).sort()).toEqual(
      EXPECTED_RUNTIME_EXPORTS.sort(),
    );
  });
});
