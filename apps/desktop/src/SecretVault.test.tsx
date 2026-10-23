import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {I18nProvider} from "./i18n/I18nProvider";
import {SecretVaultButton, SecretVaultPanel} from "./SecretVault";

const invoke = vi.fn();

vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invoke(...args),
}));

afterEach(() => {
  cleanup();
  invoke.mockReset();
});

describe("secret vault panel", () => {
  it("opens on the document body above a transformed rail and a covering list card", async () => {
    invoke.mockImplementation(async (command: string) => {
      if (command === "secret_store_status") return {backend: "needs_choice", locked: false};
      if (command === "secret_is_set") return false;
      return undefined;
    });
    const {container} = render(
      <div className="rail-center" style={{transform: "translateY(-50%)", position: "absolute"}}>
        <div data-testid="list-card" style={{position: "relative", zIndex: 30}}>
          研究列表
        </div>
        <SecretVaultButton />
      </div>,
    );

    fireEvent.click(screen.getByTestId("secret-vault-open"));
    const vault = await screen.findByTestId("secret-vault");

    expect(vault.parentElement).toBe(document.body);
    expect(container.contains(vault)).toBe(false);
    expect(vault).toHaveStyle({position: "fixed", zIndex: "80", pointerEvents: "auto"});
    expect(Number.parseInt(vault.style.zIndex, 10)).toBeGreaterThan(30);

    fireEvent.click(screen.getByTestId("secret-vault-close"));
    expect(screen.queryByTestId("secret-vault")).not.toBeInTheDocument();
  });

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

  it("does not claim a passphrase vault is locked when the file is absent", async () => {
    invoke.mockImplementation(async (command: string) => {
      if (command === "secret_store_status") return {backend: "passphrase", locked: false};
      if (command === "secret_is_set") return false;
      return undefined;
    });
    render(<SecretVaultPanel onClose={() => undefined} />);
    expect(await screen.findByTestId("secret-passphrase")).toBeInTheDocument();
    expect(screen.queryByTestId("secret-locked")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", {name: "解锁"})).not.toBeInTheDocument();
  });

  it("switches the rail button and the locked line with the interface language", async () => {
    invoke.mockImplementation(async (command: string) => {
      if (command === "secret_store_status") return {backend: "passphrase", locked: true};
      if (command === "secret_is_set") return false;
      return undefined;
    });
    render(
      <I18nProvider initial={{preference: "en", systemLocale: "en-US", resolved: "en"}}>
        <SecretVaultButton />
      </I18nProvider>,
    );
    const open = screen.getByTestId("secret-vault-open");
    expect(open).toHaveTextContent("Secrets");
    expect(open.querySelector("[data-i18n-placeholder]")).toBeTruthy();
    fireEvent.click(open);
    const locked = await screen.findByTestId("secret-locked");
    expect(locked).toHaveTextContent("A passphrase file is present and needs to be unlocked.");
    expect(locked.querySelector("[data-i18n-placeholder]")).toBeTruthy();
    expect(screen.queryByText("密钥")).not.toBeInTheDocument();
    expect(screen.queryByText("口令文件已在，需要解锁。")).not.toBeInTheDocument();
    const preview = screen.getByTestId("secret-failure-preview");
    expect(preview).toHaveTextContent("Failure");
    expect(preview.textContent).not.toMatch(/\s/);
    expect(preview.parentElement).toHaveStyle({whiteSpace: "nowrap"});
    expect(preview.parentElement).toHaveClass("secret-vault-actions");
  });
});
