import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, within} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App, ConfirmRunCard} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";
import {I18nProvider} from "./i18n/I18nProvider";
import {minimalDesktopApi} from "./test-fixtures";

const ZH = {preference: "zh" as const, systemLocale: "zh-CN", resolved: "zh" as const};
const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};

afterEach(() => cleanup());

const US_LINE = "单票 ≤5%、成本 5 bp（保守产品假设）";
const CN_LINE = "未模拟 T+1 与涨跌停，实际成交可能更差";

describe("A2 construction notices", () => {
  it("shows the confirm-card cost assumption when the engine sends one", () => {
    const api = {unlockBrief: vi.fn(), confirmRun: vi.fn()} as unknown as DesktopApi;
    const view: DesktopView = {
      kind: "confirm_run",
      researchId: "r-1",
      dialogue: [],
      constructionNotice: US_LINE,
      settings: {
        thesis: "美股股票的均值回归",
        universe: "美股 · 股票",
        max_effective_hours: "4 小时",
        round1_methods: "样本外稳定",
        coverage_floor: "至少 25 个标的",
      },
    };
    render(
      <I18nProvider initial={ZH}>
        <ConfirmRunCard api={api} view={view} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("construction-notice")).toHaveTextContent(US_LINE);
  });

  it("uses the short English line for the 5% cap", () => {
    const api = {unlockBrief: vi.fn(), confirmRun: vi.fn()} as unknown as DesktopApi;
    const view: DesktopView = {
      kind: "confirm_run",
      researchId: "r-1",
      dialogue: [],
      constructionNotice: US_LINE,
      settings: {
        thesis: "美股股票的均值回归",
        universe: "美股 · 股票",
        max_effective_hours: "4 小时",
        round1_methods: "样本外稳定",
        coverage_floor: "至少 25 个标的",
      },
    };
    render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={api} view={view} />
      </I18nProvider>,
    );
    const notice = screen.getByTestId("construction-notice");
    expect(notice).toHaveTextContent("≤5% per name, cost 5 bp");
    expect(notice.textContent ?? "").not.toContain("保守产品假设");
  });

  it("shows the A-share execution notice on the conclusion page", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-1",
      status: "completed",
      title: "A股均值回归",
      selectedRoundId: "round-1",
      selectedMethodId: "overfit.walk",
      eligibility: {
        allMethodsPassed: true,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: true,
      },
      cnExecutionNotice: CN_LINE,
    };
    render(<App api={minimalDesktopApi()} initialView={view} initialRoute="#/research/r-1" />);
    expect(screen.getByTestId("cn-execution-notice")).toHaveTextContent(CN_LINE);
  });
});

const HINT_ZH = "股票池是名单日的成分，回看更早的历史含幸存者偏差。";
const HINT_EN = "Uses list-date members; earlier history has survivorship bias.";

function defaultPoolSelection(source: "default_pool" | "user_override") {
  return {
    count: source === "default_pool" ? 503 : 2,
    listName: source === "default_pool" ? "美股大市值池 · 503 只 · 名单日 2026-10-16" : "用户指定标的",
    listVersion: source === "default_pool" ? "2" : "user",
    summaryLine: source === "default_pool"
      ? "美股大市值池 · 503 只 · 名单日 2026-10-16"
      : "2 只 · 用户指定标的 · 已覆盖默认的池",
    listNote: source === "default_pool" ? "取自标普 500 在名单日的成分，非时点成分" : "",
    symbols: ["AAPL"],
    source,
    isDefaultPool: source === "default_pool",
    dataStart: "2016-10-20",
    dataEnd: "2026-10-19",
    dataCutoff: "2026-10-19",
    dataSource: "雅虎日线",
  };
}

describe("survivorship hint on list-date default pools", () => {
  it("renders the hint in the confirm data block and on the conclusion page, in Chinese and English", () => {
    const api = {unlockBrief: vi.fn(), confirmRun: vi.fn()} as unknown as DesktopApi;
    const confirm: DesktopView = {
      kind: "confirm_run",
      researchId: "r-pool",
      dialogue: [],
      chatEnabled: false,
      settings: {
        thesis: "均值回归",
        universe: "美股 · 股票",
        max_effective_hours: "4 小时",
        round1_methods: "样本外稳定",
        coverage_floor: "至少 25 个标的",
      },
      symbolSelection: defaultPoolSelection("default_pool"),
    };
    const {unmount} = render(
      <I18nProvider initial={ZH}>
        <ConfirmRunCard api={api} view={confirm} />
      </I18nProvider>,
    );
    const zhConfirm = screen.getByTestId("symbol-selection");
    expect(within(zhConfirm).getByTestId("survivorship-hint")).toHaveTextContent(HINT_ZH);
    unmount();

    render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={api} view={confirm} />
      </I18nProvider>,
    );
    expect(within(screen.getByTestId("symbol-selection")).getByTestId("survivorship-hint")).toHaveTextContent(HINT_EN);
  });

  it("renders the same hint in the conclusion data block and hides it for a custom list", () => {
    const completed = (source: "default_pool" | "user_override"): DesktopView => ({
      kind: "completed",
      researchId: "r-pool",
      status: "completed",
      title: "均值回归",
      selectedRoundId: "round-1",
      selectedMethodId: "overfit.walk",
      eligibility: {
        allMethodsPassed: true,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: true,
      },
      cnExecutionNotice: CN_LINE,
      symbolSelection: defaultPoolSelection(source),
    });
    const {unmount} = render(
      <I18nProvider initial={ZH}>
        <App api={minimalDesktopApi()} initialView={completed("default_pool")} initialRoute="#/research/r-pool" />
      </I18nProvider>,
    );
    const zhData = screen.getByTestId("completed-symbol-selection");
    expect(within(zhData).getByTestId("survivorship-hint")).toHaveTextContent(HINT_ZH);
    expect(screen.getByTestId("cn-execution-notice")).toBeInTheDocument();
    unmount();

    render(
      <I18nProvider initial={EN}>
        <App api={minimalDesktopApi()} initialView={completed("default_pool")} initialRoute="#/research/r-pool" />
      </I18nProvider>,
    );
    expect(within(screen.getByTestId("completed-symbol-selection")).getByTestId("survivorship-hint")).toHaveTextContent(HINT_EN);
  });

  it("does not render the hint for a custom symbol list", () => {
    const api = {unlockBrief: vi.fn(), confirmRun: vi.fn()} as unknown as DesktopApi;
    const {unmount} = render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard
          api={api}
          view={{
            kind: "confirm_run",
            researchId: "r-custom",
            dialogue: [],
            settings: {
              thesis: "custom",
              universe: "美股 · 股票",
              max_effective_hours: "4 小时",
              round1_methods: "样本外稳定",
              coverage_floor: "至少 1 个标的",
            },
            symbolSelection: defaultPoolSelection("user_override"),
          }}
        />
      </I18nProvider>,
    );
    expect(screen.queryByTestId("survivorship-hint")).toBeNull();
    unmount();
    render(
      <I18nProvider initial={ZH}>
        <App
          api={minimalDesktopApi()}
          initialView={{
            kind: "completed",
            researchId: "r-custom",
            status: "completed",
            title: "custom",
            selectedRoundId: "round-1",
            selectedMethodId: "overfit.walk",
            eligibility: {
              allMethodsPassed: false,
              noPendingConfirm: true,
              reverifiesPassed: true,
              pitExecutedAndPassed: false,
            },
            symbolSelection: defaultPoolSelection("user_override"),
          }}
          initialRoute="#/research/r-custom"
        />
      </I18nProvider>,
    );
    expect(screen.queryByTestId("survivorship-hint")).toBeNull();
  });
});
