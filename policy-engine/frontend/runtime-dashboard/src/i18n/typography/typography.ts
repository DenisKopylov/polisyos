import {
  Children,
  cloneElement,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";

import type { Locale } from "../locale";
import { insertNonBreakingSpaces } from "./nonBreakingSpaces";
import { applyLocaleQuoteMarks } from "./quoteMarks";

export type LocaleTypographyOptions = {
  enabled?: boolean;
  nonBreakingSpaces?: boolean;
  quoteMarks?: boolean;
};

export function applyLocaleTypography(
  value: string,
  locale: Locale,
  options: LocaleTypographyOptions = {},
): string {
  if (options.enabled === false) {
    return value;
  }

  let nextValue = value;

  if (options.quoteMarks ?? true) {
    nextValue = applyLocaleQuoteMarks(nextValue, locale);
  }

  if (options.nonBreakingSpaces ?? true) {
    nextValue = insertNonBreakingSpaces(nextValue, locale);
  }

  return nextValue;
}

export function applyTypographyToReactNode(
  node: ReactNode,
  locale: Locale,
  options: LocaleTypographyOptions = {},
): ReactNode {
  if (typeof node === "string") {
    return applyLocaleTypography(node, locale, options);
  }

  if (Array.isArray(node)) {
    return node.map((child) =>
      applyTypographyToReactNode(child, locale, options),
    );
  }

  if (!isValidElement(node)) {
    return node;
  }

  const element = node as ReactElement<{ children?: ReactNode }>;
  if (element.props.children === undefined) {
    return element;
  }

  return cloneElement(
    element,
    undefined,
    Children.map(element.props.children, (child) =>
      applyTypographyToReactNode(child, locale, options),
    ),
  );
}
