import { useEffect } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Text,
} from "@polisyos/atlas-ui";

function LocaleSetter() {
  const { setLocale } = useI18n();

  useEffect(() => {
    setLocale("uk");
  }, [setLocale]);

  return null;
}

const meta = {
  title: "Shared/Text",
  component: Text,
} satisfies Meta<typeof Text>;

export default meta;

type Story = StoryObj<typeof meta>;

export const UkrainianTypography: Story = {
  args: {
    children: "",
  },
  render: () => (
    <Card className="max-w-3xl">
      <LocaleSetter />
      <CardHeader>
        <CardTitle>Український typography specimen</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Text>
          в "PolicyOS" та у runtime-панелі ми показуємо короткі прийменники з
          не&nbsp;ламкими пробілами.
        </Text>
        <Text mono>
          ІДЕНТИФІКАТОР POLICY_2026_04 · МОДУЛЬ SYNTHETIC_CONTROL · СТАТУС READY
        </Text>
        <Text className="font-mono text-sm">
          evidence_ref_ua_0422 / lineage_depth=03 / confidence_band=0.84
        </Text>
      </CardContent>
    </Card>
  ),
};
