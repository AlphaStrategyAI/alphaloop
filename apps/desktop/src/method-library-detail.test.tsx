import {render, screen} from "@testing-library/react";
import {describe, expect, it} from "vitest";

import {MethodDetail} from "./App";
import type {DesktopApi, ValidationMethod} from "./contracts";

const FIXTURES: ValidationMethod[] = [
  {
    id: "scorecard.market",
    name: "市场计分卡",
    revision: "abc",
    revisionLabel: "市场计分卡 · 内置第 1 版",
    description: "用多维指标衡量策略是否达到最低可接受表现。",
    definitionDisplay: "用途：用多维指标衡量策略是否达到最低可接受表现。\n样本外夏普下限（不含等于）：0",
    usageCount: 1,
  },
  {
    id: "pit.consistency",
    name: "时点一致性",
    revision: "def",
    revisionLabel: "时点一致性 · 内置第 1 版",
    description: "确保证据与回测只使用决策当时可获得的信息，杜绝前视偏差。",
    definitionDisplay:
      "用途：确保证据与回测只使用决策当时可获得的信息，杜绝前视偏差。\n维度：时点一致性\n说明：证据与回测窗口仅使用决策当时可获得的信息。",
    usageCount: 0,
  },
  {
    id: "cost.turnover",
    name: "换手成本",
    revision: "ghi",
    revisionLabel: "换手成本 · 内置第 1 版",
    description: "在换手成本下检验净超额是否仍为正。",
    definitionDisplay: "用途：在换手成本下检验净超额是否仍为正。\n美股成本（bp）：10\nA 股成本（bp）：20",
    usageCount: 2,
  },
];

const api = {} as DesktopApi;

function assertNoLeaks(text: string) {
  expect(text).not.toMatch(/\{|\}|\\u|_[a-z]+/);
  expect(text).not.toMatch(/walk-v1|cost-v1|Point-in-Time|Lookahead/i);
}

describe("MethodDetail", () => {
  for (const method of FIXTURES) {
    it(`renders structured Chinese for ${method.id}`, () => {
      const {container} = render(<MethodDetail api={api} method={method} />);
      const block = container.querySelector("[data-testid=method-definition-display]");
      if (!block) throw new Error("missing method-definition-display");
      assertNoLeaks(block.textContent ?? "");
      expect(block.textContent).toContain("用途：");
    });
  }
});
