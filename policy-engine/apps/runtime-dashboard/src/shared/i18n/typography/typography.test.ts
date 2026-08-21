import { applyLocaleQuoteMarks, getLocaleQuoteMarks } from "./quoteMarks";
import {
  hasShortPrepositionSpacingIssue,
  insertNonBreakingSpaces,
} from "./nonBreakingSpaces";
import { applyLocaleTypography } from "./typography";

const NBSP = "\u00A0";

describe("locale typography", () => {
  it("returns locale quote pairs", () => {
    expect(getLocaleQuoteMarks("uk")).toEqual({
      primary: ["«", "»"],
      secondary: ["„", "“"],
    });
    expect(getLocaleQuoteMarks("ru")).toEqual({
      primary: ["«", "»"],
      secondary: ["„", "“"],
    });
  });

  it.each([
    ['He said "Atlas"', "en", "He said “Atlas”"],
    ['Політика "Альфа"', "uk", "Політика «Альфа»"],
    ['Режим "Бета"', "ru", "Режим «Бета»"],
    ["«Вже типографічно»", "uk", "«Вже типографічно»"],
    ['Код `const label = "raw"`', "uk", 'Код `const label = "raw"`'],
  ] as const)("normalizes quote marks for %s", (input, locale, expected) => {
    expect(applyLocaleQuoteMarks(input, locale)).toBe(expected);
  });

  it.each([
    ["в Києві", "uk", `в${NBSP}Києві`],
    ["у Львові", "uk", `у${NBSP}Львові`],
    ["з міста", "uk", `з${NBSP}міста`],
    ["і громада", "uk", `і${NBSP}громада`],
    ["й команда", "uk", `й${NBSP}команда`],
    ["та рішення", "uk", `та${NBSP}рішення`],
    ["на платформі", "uk", `на${NBSP}платформі`],
    ["до реєстру", "uk", `до${NBSP}реєстру`],
    ["від команди", "uk", `від${NBSP}команди`],
    ["за планом", "uk", `за${NBSP}планом`],
    ["під наглядом", "uk", `під${NBSP}наглядом`],
    ["над моделлю", "uk", `над${NBSP}моделлю`],
    ["про Atlas", "uk", `про${NBSP}Atlas`],
    ["в Москве", "ru", `в${NBSP}Москве`],
    ["у порога", "ru", `у${NBSP}порога`],
    ["о проекте", "ru", `о${NBSP}проекте`],
    ["к решению", "ru", `к${NBSP}решению`],
    ["с командой", "ru", `с${NBSP}командой`],
    ["и данные", "ru", `и${NBSP}данные`],
    ["а вывод", "ru", `а${NBSP}вывод`],
    ["но решение", "ru", `но${NBSP}решение`],
  ] as const)("inserts NBSP for %s", (input, locale, expected) => {
    expect(insertNonBreakingSpaces(input, locale)).toBe(expected);
    expect(hasShortPrepositionSpacingIssue(input, locale)).toBe(true);
    expect(hasShortPrepositionSpacingIssue(expected, locale)).toBe(false);
  });

  it("applies quote and NBSP transforms together", () => {
    expect(applyLocaleTypography('в "Атласі"', "uk")).toBe(`в${NBSP}«Атласі»`);
    expect(
      applyLocaleTypography('о "PolicyOS"', "ru", { quoteMarks: true }),
    ).toBe(`о${NBSP}«PolicyOS»`);
    expect(
      applyLocaleTypography('в "Атласі"', "uk", {
        enabled: false,
      }),
    ).toBe('в "Атласі"');
  });

  it("keeps frozen Russian typography available only through an explicit compatibility locale", () => {
    expect(applyLocaleTypography('о "PolicyOS"', "ru")).toBe(
      `о${NBSP}«PolicyOS»`,
    );
  });
});
