import "@testing-library/jest-dom/vitest";
import {render, screen} from "@testing-library/react";
import {describe, expect, it, vi} from "vitest";

import {ConfirmRunScreen} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";
import {EngineFailureText} from "./i18n/engineFailure";
import {I18nProvider} from "./i18n/I18nProvider";

const CHINESE = "行情数据源暂时不可用，请稍后重试";
const ENGLISH = {
  preference: "en" as const,
  systemLocale: "en-US",
  resolved: "en" as const,
};

const api = {unlockBrief: vi.fn(), confirmRun: vi.fn()} as unknown as DesktopApi;

const view: Extract<DesktopView, {kind: "confirm_run"}> = {
  kind: "confirm_run",
  researchId: "r-1",
  chatEnabled: false,
  dialogue: [
    {
      role: "assistant",
      text: "",
      errorCode: "DATA_SOURCE_UNAVAILABLE",
      errorParams: {symbols: 40},
      errorDetail: "provider returned an empty price frame",
    },
  ],
  settings: {
    thesis: "测试",
    universe: "美股 · 股票",
    max_effective_hours: "3 小时",
    round1_methods: "分段稳健性检验",
    coverage_floor: "至少 25 个标的",
  },
};

describe("coded engine errors in English", () => {
  it("does not put the Chinese source sentence in the confirm dialogue", () => {
    render(
      <I18nProvider initial={ENGLISH}>
        <ConfirmRunScreen api={api} view={view} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("dialogue-error-summary").textContent).not.toContain(CHINESE);
    expect(screen.getByTestId("dialogue-error-summary").textContent).toContain("temporarily unavailable");
    expect(screen.getByTestId("dialogue-error-detail").textContent).toContain("empty price frame");
    expect(screen.getByTestId("dialogue-error-detail").textContent).toContain("symbols: 40");
    expect(screen.getByTestId("dialogue-error-detail").textContent).not.toContain(CHINESE);
    expect(document.body.textContent).not.toContain(CHINESE);
  });

  it("localizes a command toast from the error envelope instead of the legacy sentence", () => {
    const raw = JSON.stringify({
      error: CHINESE,
      code: "DATA_SOURCE_UNAVAILABLE",
      params: {},
      detail: null,
    });
    render(
      <I18nProvider initial={ENGLISH}>
        <EngineFailureText raw={raw} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("engine-failure-summary").textContent).toContain("temporarily unavailable");
    expect(screen.getByTestId("engine-failure-summary").textContent).not.toContain(CHINESE);
    expect(document.body.textContent).not.toContain(CHINESE);
  });
});
