import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {bindDesktopApi} from "./api-bind";
import type {DesktopApi, DesktopView} from "./contracts";
import {createTauriDesktopApi, type DesktopInvoke} from "./desktopApi";
import {formatResearchTimestamp} from "./format";
import {ConfirmRunCard} from "./screens/ConfirmRunScreen";
import {I18nProvider} from "./i18n/I18nProvider";

const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};
const ACK = "2026-10-27T07:06:00+00:00";

afterEach(() => cleanup());

function desktop(): DesktopApi & {
  setPriceSource: ReturnType<typeof vi.fn>;
  unlockBrief: ReturnType<typeof vi.fn>;
} {
  return {
    fetchView: vi.fn(),
    createDraft: vi.fn(),
    confirmRun: vi.fn(),
    setResearchSymbol: vi.fn(),
    setPriceSource: vi.fn(async () => undefined),
    answerSymbolAsk: vi.fn(),
    useHintedSymbol: vi.fn(),
    revertSymbolAsk: vi.fn(),
    removeMarketSide: vi.fn(),
    dismissMismatchedSymbol: vi.fn(),
    chooseDefaultMarket: vi.fn(),
    unlockBrief: vi.fn(async () => undefined),
    sendDialogue: vi.fn(),
    pauseResearch: vi.fn(),
    resumeResearch: vi.fn(),
    confirmModification: vi.fn(),
    continueIterate: vi.fn(),
    extendResearch: vi.fn(),
    deleteResearch: vi.fn(),
    resolveConfirm: vi.fn(),
    exportArtifact: vi.fn(async () => "/tmp/export.zip"),
    revealExportInFolder: vi.fn(),
    reverify: vi.fn(),
    reviseMethod: vi.fn(),
    createMethod: vi.fn(),
  } as DesktopApi & {
    setPriceSource: ReturnType<typeof vi.fn>;
    unlockBrief: ReturnType<typeof vi.fn>;
  };
}

function card(extra: Partial<Extract<DesktopView, {kind: "confirm_run"}>["symbolSelection"]> = {}): Extract<DesktopView, {kind: "confirm_run"}> {
  return {
    kind: "confirm_run",
    researchId: "r-edit",
    dialogue: [],
    market: "US",
    settings: {
      thesis: "Mean reversion on AAPL, a US stock, using daily prices.",
      universe: "US · equities",
      max_effective_hours: "30 min",
      round1_methods: "Subperiod robustness check",
      coverage_floor: "At least 25 names",
    },
    symbolSelection: {
      count: 1,
      listName: "用户指定标的",
      listVersion: "user",
      symbols: ["AAPL"],
      source: "user_override",
      dataStart: "2014-10-29",
      dataEnd: "2026-10-26",
      dataCutoff: "2026-10-26",
      dataSource: "待选择",
      dataSourceId: null,
      dataSourcePending: true,
      priceSources: [
        {id: "yahoo_daily", label: "雅虎日线", unlicensed: true, market: "US", acknowledgedAt: null},
      ],
      ...extra,
    },
  };
}

describe("confirm edit keeps the price source and the acknowledgement together", () => {
  it("waits for the source write before confirm_run", async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const api = desktop();
    api.setPriceSource.mockImplementation(() => gate);
    render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={api} view={card()} />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByTestId("price-source-yahoo_daily"));
    fireEvent.click(screen.getByTestId("unlicensed-ack"));
    fireEvent.click(screen.getByTestId("confirm-run-start"));
    await Promise.resolve();
    expect(api.confirmRun).not.toHaveBeenCalled();
    release();
    await waitFor(() =>
      expect(api.confirmRun).toHaveBeenCalledWith("r-edit", {
        dataSourceId: "yahoo_daily",
        unlicensedAcknowledged: true,
      }),
    );
  });

  it("stores the chosen source and the acknowledgement before Edit", async () => {
    const api = desktop();
    render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={api} view={card()} />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByTestId("price-source-yahoo_daily"));
    await waitFor(() => expect(api.setPriceSource).toHaveBeenCalledWith("r-edit", "yahoo_daily"));
    fireEvent.click(screen.getByTestId("unlicensed-ack"));
    await waitFor(() => expect(api.setPriceSource).toHaveBeenCalledWith("r-edit", "yahoo_daily", true));
    fireEvent.click(screen.getByTestId("edit-slot-coverage_floor"));
    await waitFor(() => expect(api.unlockBrief).toHaveBeenCalledWith("r-edit", "coverage_floor"));
    const order = api.setPriceSource.mock.invocationCallOrder.at(-1) ?? 0;
    const unlockOrder = api.unlockBrief.mock.invocationCallOrder[0] ?? 0;
    expect(order).toBeLessThan(unlockOrder);
  });

  it("confirms at the revision the source acknowledgement returned, not the stale card", async () => {
    let sourceWrites = 0;
    const invoke = vi.fn(async (command: string, _args?: Record<string, unknown>) => {
      if (command !== "set_price_source") return undefined;
      sourceWrites += 1;
      return sourceWrites === 1 ? 5 : 6;
    });
    const api = bindDesktopApi(createTauriDesktopApi(invoke as unknown as DesktopInvoke), {
      refresh: async () => undefined,
      onError: () => undefined,
    });
    render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={api} view={{...card(), revision: 4}} />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByTestId("price-source-yahoo_daily"));
    fireEvent.click(screen.getByTestId("unlicensed-ack"));
    fireEvent.click(screen.getByTestId("confirm-run-start"));
    await waitFor(() => {
      const confirm = invoke.mock.calls.find((call) => call[0] === "confirm_run");
      expect(confirm?.[1]).toMatchObject({
        researchId: "r-edit",
        dataSourceId: "yahoo_daily",
        unlicensedAcknowledged: true,
        expectedRevision: 6,
      });
    });
    const confirm = invoke.mock.calls.find((call) => call[0] === "confirm_run");
    expect(confirm?.[1]).toEqual(expect.objectContaining({
      commandId: expect.any(String),
    }));
    expect(sourceWrites).toBe(2);
  });

  it("comes back selected and acknowledged, not Not selected with a leftover time", () => {
    render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard
          api={desktop()}
          view={card({
            dataSource: "雅虎日线",
            dataSourceId: "yahoo_daily",
            dataSourcePending: false,
            priceSources: [
              {
                id: "yahoo_daily",
                label: "雅虎日线",
                unlicensed: true,
                market: "US",
                acknowledgedAt: ACK,
              },
            ],
          })}
        />
      </I18nProvider>,
    );
    const radio = screen.getByTestId("price-source-yahoo_daily") as HTMLInputElement;
    expect(radio.checked).toBe(true);
    expect(screen.getByTestId("confirm-data-meta").textContent).toContain("Yahoo daily");
    expect(screen.getByTestId("confirm-data-meta").textContent).not.toContain("Not selected");
    expect(screen.getByTestId("unlicensed-ack-done").textContent).toContain(formatResearchTimestamp(ACK));
    expect(screen.queryByTestId("unlicensed-ack")).toBeNull();
  });
});
