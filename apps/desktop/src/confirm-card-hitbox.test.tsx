// @ts-nocheck — headless probe uses Node builtins; this package has no @types/node.
import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {execFileSync} from "node:child_process";
import {existsSync, mkdtempSync, writeFileSync} from "node:fs";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {renderToStaticMarkup} from "react-dom/server";
import {afterEach, describe, expect, it} from "vitest";

import type {DesktopApi, DesktopView} from "./contracts";
import {I18nProvider} from "./i18n/I18nProvider";
import {ConfirmRunScreen} from "./screens/ConfirmRunScreen";

afterEach(() => cleanup());

const api = {
  sendDialogue: async () => undefined,
  setResearchSymbol: async () => undefined,
  confirmRun: async () => undefined,
  returnToDraft: async () => undefined,
} as unknown as DesktopApi;

function filledConfirm(): Extract<DesktopView, {kind: "confirm_run"}> {
  return {
    kind: "confirm_run",
    researchId: "r-family",
    chatEnabled: true,
    dialogue: Array.from({length: 8}, (_, index) => ({
      role: index % 2 === 0 ? "assistant" as const : "user" as const,
      text: `Turn ${index}. Mean reversion in US large-cap stocks, with a long enough line to fill the dialogue column.`,
    })),
    meanReversionChoice: true,
    familyChipIds: ["low_volatility", "stock_bond_rebalance", "mean_reversion", "fundamental_factor", "all_weather"],
    runGate: {runnable: false, code: "MEAN_REVERSION_ACK_REQUIRED"},
    settings: {
      thesis: "US momentum, repeated so the confirm body is taller than a short laptop viewport. ".repeat(12),
      universe: "US stocks",
      max_effective_hours: "12 hours",
      round1_methods: "Turnover cost",
      coverage_floor: "At least 1 name",
    },
    confirmDataNotice: "No data source selected yet. ".repeat(20),
    symbolSelection: {
      count: 1,
      listName: "Named symbols",
      listVersion: "user",
      symbols: ["SPY"],
      source: "user_override",
      dataStart: "2014-10-27",
      dataEnd: "2026-10-24",
      dataCutoff: "2026-10-24",
      dataSource: "Not selected",
      dataSourcePending: true,
    },
  };
}

function chromeBinary(): string | null {
  for (const path of ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/local/bin/google-chrome"]) {
    if (existsSync(path)) return path;
  }
  return null;
}

describe("confirm card click targets", () => {
  it("keeps family chips in the scrolling body and Run in non-scrolling chrome", () => {
    render(
      <I18nProvider initial={{preference: "en", systemLocale: "en-US", resolved: "en"}}>
        <ConfirmRunScreen api={api} view={filledConfirm()} />
      </I18nProvider>,
    );
    const body = screen.getByTestId("confirm-card-body");
    const chrome = screen.getByTestId("confirm-card-chrome");
    const decline = screen.getByTestId("mean-reversion-decline");
    const run = screen.getByTestId("confirm-run-start");
    expect(body.contains(decline)).toBe(true);
    expect(body.contains(screen.getByTestId("family-chips"))).toBe(true);
    expect(chrome.contains(run)).toBe(true);
    expect(body.contains(run)).toBe(false);
    expect(chrome.contains(decline)).toBe(false);
    expect(screen.getByTestId("confirm-run-card")).toBeInTheDocument();
  });

  const chrome = chromeBinary();
  const measure = chrome ? it : it.skip;
  measure("family chips and Run do not share a click at 1024×768 or 1280×800", () => {
    const markup = renderToStaticMarkup(
      <I18nProvider initial={{preference: "en", systemLocale: "en-US", resolved: "en"}}>
        <ConfirmRunScreen api={api} view={filledConfirm()} />
      </I18nProvider>,
    );
    const dir = mkdtempSync(join(tmpdir(), "confirm-hitbox-"));
    const htmlPath = join(dir, "card.html");
    const root = "/workspace/apps/desktop/src";
    writeFileSync(
      htmlPath,
      `<!doctype html><html><head>
        <link rel="stylesheet" href="file://${root}/night.css" />
        <link rel="stylesheet" href="file://${root}/tech-pulse.css" />
        <style>html,body,#root{height:100%;margin:0}</style>
      </head><body>
        <main class="night-shell tech-pulse-shell" data-testid="night-shell" style="height:100vh">
          <aside class="rail" data-testid="rail"></aside>
          <section class="content confirm_run tech-pulse-content" style="height:100vh">${markup}</section>
        </main>
        <script>
          const decline = document.querySelector("[data-testid=mean-reversion-decline]");
          const run = document.querySelector("[data-testid=confirm-run-start]");
          decline.scrollIntoView({block: "end", inline: "nearest"});
          const rect = (el) => {
            const r = el.getBoundingClientRect();
            return {top: r.top, left: r.left, right: r.right, bottom: r.bottom, width: r.width, height: r.height};
          };
          const hitInfo = (el) => {
            const r = el.getBoundingClientRect();
            const node = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
            const owned = node === el || (node && el.contains(node));
            return {owned, id: node && node.getAttribute ? node.getAttribute("data-testid") : null, tag: node ? node.tagName : null};
          };
          const a = rect(decline);
          const b = rect(run);
          const overlap = a.width > 0 && b.width > 0 && a.right > b.left && a.left < b.right && a.bottom > b.top && a.top < b.bottom;
          document.title = "HITBOX:" + JSON.stringify({
            overlap,
            declineHit: hitInfo(decline).owned,
            runHit: hitInfo(run).owned,
            declineTarget: hitInfo(decline).id,
            runTarget: hitInfo(run).id,
            runInView: b.top >= -1 && b.bottom <= window.innerHeight + 1 && b.height > 0,
            inner: {w: window.innerWidth, h: window.innerHeight},
            decline: a,
            run: b,
          });
        </script>
      </body></html>`,
    );
    for (const [width, height] of [[1024, 768], [1280, 800]] as const) {
      const dumped = execFileSync(chrome!, [
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--allow-file-access-from-files",
        "--virtual-time-budget=2000",
        `--window-size=${width},${height}`,
        "--dump-dom",
        `file://${htmlPath}`,
      ], {encoding: "utf8", timeout: 20000});
      const match = dumped.match(/<title>HITBOX:([\s\S]*?)<\/title>/);
      if (!match) throw new Error(`no hitbox report at ${width}x${height}: ${dumped.slice(0, 400)}`);
      const report = JSON.parse(match[1].replace(/&quot;/g, '"').replace(/&amp;/g, "&")) as {
        overlap: boolean;
        declineHit: boolean;
        runHit: boolean;
        runInView: boolean;
      };
      const label = `${width}x${height} ${JSON.stringify(report)}`;
      expect(report.overlap, label).toBe(false);
      expect(report.declineHit, label).toBe(true);
      expect(report.runHit, label).toBe(true);
      expect(report.runInView, label).toBe(true);
    }
  });
});
