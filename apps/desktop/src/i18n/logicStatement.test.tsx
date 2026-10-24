import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it} from "vitest";

import {I18nProvider} from "./I18nProvider";
import {LogicStatementText} from "./logicStatement";

const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};
const ZH = {preference: "zh" as const, systemLocale: "zh-CN", resolved: "zh" as const};

afterEach(() => cleanup());

const STATEMENT = "论点：美股股票 AAPL 的均值回归；实际执行：截面均值回归，回看 20 天";

describe("logic statement chrome", () => {
  it("keeps the user thesis and translates the template in English", () => {
    render(
      <I18nProvider initial={EN}>
        <p data-testid="line"><LogicStatementText text={STATEMENT} /></p>
      </I18nProvider>,
    );
    const line = screen.getByTestId("line");
    expect(line).toHaveTextContent("Thesis:");
    expect(line).toHaveTextContent("美股股票 AAPL 的均值回归");
    expect(line).toHaveTextContent("cross-sectional mean reversion, lookback 20 days");
    const user = line.querySelector("[data-user-content]");
    expect(user).toHaveTextContent("美股股票 AAPL 的均值回归");
    const chrome = (line.textContent ?? "").replace(user?.textContent ?? "", "");
    expect(chrome).not.toMatch(/[\u4e00-\u9fff]/);
  });

  it("keeps the original Chinese sentence when the UI is Chinese", () => {
    render(
      <I18nProvider initial={ZH}>
        <p data-testid="line"><LogicStatementText text={STATEMENT} /></p>
      </I18nProvider>,
    );
    expect(screen.getByTestId("line")).toHaveTextContent(STATEMENT);
  });
});
