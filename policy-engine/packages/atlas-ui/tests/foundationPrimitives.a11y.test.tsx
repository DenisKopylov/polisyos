import { render } from "@testing-library/react";
import { Search } from "lucide-react";
import { axe } from "vitest-axe";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Icon,
  PageSkeleton,
  Spinner,
  Text,
} from "../src/index";

describe("foundation primitive accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    const { container } = render(
      <Card>
        <Badge kind="ok">Healthy</Badge>
        <Button type="button">Inspect</Button>
        <EmptyState title="Empty" body="No evidence" />
        <Icon icon={Search} label="Search" />
        <Spinner />
        <Text>Runtime evidence</Text>
        <PageSkeleton />
      </Card>,
    );

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
