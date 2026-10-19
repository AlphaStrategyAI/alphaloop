import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {SecretVaultPanel} from "./SecretVault";

const invoke = vi.fn();

vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invoke(...args),
}));

afterEach(() => {
  cleanup();
  invoke.mockReset();
});

describe("secret vault panel", () => {
  it("asks for a fallback when Secret Service is missing and never echoes a secret", async () => {
    invoke.mockImplementation(async (command: string) => {
      if (command === "secret_store_status") return {backend: "needs_choice", locked: false};
      if (command === "secret_is_set") return false;
      return undefined;
    });
    render(<SecretVaultPanel onClose={() => undefined} />);
    expect(await screen.findByTestId("secret-fallback")).toHaveTextContent("没有系统钥匙串");
    expect(screen.getByRole("button", {name: "仅本次会话"})).toBeInTheDocument();
    expect(screen.getByRole("button", {name: "口令加密的本机文件"})).toBeInTheDocument();
    expect(screen.getByTestId("secret-status")).toHaveTextContent("未设置");
  });

  it("shows 已设置 after a save and prints a redacted failure", async () => {
    let set = false;
    invoke.mockImplementation(async (command: string, args?: {value?: string}) => {
      if (command === "secret_store_status") return {backend: "keyring", locked: false};
      if (command === "secret_is_set") return set;
      if (command === "secret_set") {
        set = true;
        expect(args?.value).toBe("alphaloop-test-secret-9f3a");
        return undefined;
      }
      if (command === "secret_failure_preview") {
        return "error sending request for url https://example.invalid/v1/«redacted»";
      }
      return undefined;
    });
    render(<SecretVaultPanel onClose={() => undefined} />);
    expect(await screen.findByTestId("secret-status")).toHaveTextContent("未设置");
    fireEvent.change(screen.getByTestId("secret-value"), {
      target: {value: "alphaloop-test-secret-9f3a"},
    });
    fireEvent.click(screen.getByRole("button", {name: "保存"}));
    expect(await screen.findByText("已保存。界面不保留明文。")).toBeInTheDocument();
    expect(screen.getByTestId("secret-value")).toHaveValue("");
    expect(screen.getByTestId("secret-status")).toHaveTextContent("已设置");
    fireEvent.click(screen.getByTestId("secret-failure-preview"));
    const failure = await screen.findByTestId("secret-failure-text");
    expect(failure).toHaveTextContent("example.invalid");
    expect(failure.textContent).not.toContain("alphaloop-test-secret-9f3a");
  });
});
