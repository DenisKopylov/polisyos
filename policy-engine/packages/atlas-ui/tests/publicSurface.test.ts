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
  "Checkbox",
  "EmptyState",
  "Icon",
  "Input",
  "Label",
  "MetricsSkeleton",
  "PageSkeleton",
  "PanelSkeleton",
  "Radio",
  "SegmentedControl",
  "Select",
  "SkeletonBlock",
  "SkeletonCard",
  "SkeletonChart",
  "SkeletonTable",
  "SkeletonText",
  "Spinner",
  "Slider",
  "Switch",
  "Text",
  "TextPresentationProvider",
  "Textarea",
  "ToggleButton",
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
