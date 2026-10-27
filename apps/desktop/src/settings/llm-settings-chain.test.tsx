/**
 * Call chain: Settings LLM form → set_llm_settings + secret_set.
 * The invoke objects mirror the Tauri command arguments.
 */
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, describe, expect, it} from "vitest";

import {I18nProvider} from "../i18n/I18nProvider";
import {createMemoryLanguagePort} from "../i18n/port";
import {
  LLM_API_KEY_SECRET_ID,
  LLM_SETTINGS_SAVE_COMMAND,
  llmApiKeyInvokeArgs,
  setLlmSettingsInvokeArgs,
} from "./llmSettingsCommand";
import {createMemoryLlmSettingsPort} from "./llmSettingsPort";
import {SettingsPage} from "./SettingsPage";

const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};

afterEach(() => cleanup());

describe("LLM settings call chain", () => {
  it("saves base URL and model without the API key, then stores the key under llm-api-key", async () => {
    const language = createMemoryLanguagePort({preference: "en", systemLocale: "en-US"});
    const {port, state} = createMemoryLlmSettingsPort();
    render(
      <I18nProvider port={language} initial={EN}>
        <SettingsPage route="#/settings/llm" llmPort={port} />
      </I18nProvider>,
    );
    fireEvent.change(await screen.findByTestId("llm-base-url"), {
      target: {value: "https://api.openai.com/v1"},
    });
    fireEvent.change(screen.getByTestId("llm-model"), {target: {value: "gpt-4.1-mini"}});
    fireEvent.change(screen.getByTestId("llm-api-key"), {target: {value: "sk-test-key"}});
    fireEvent.click(screen.getByTestId("llm-privacy"));
    fireEvent.click(screen.getByTestId("llm-save"));
    await waitFor(() => expect(state.saveCalls).toHaveLength(1));
    expect(state.saveCalls[0]).toEqual(
      setLlmSettingsInvokeArgs({
        baseUrl: "https://api.openai.com/v1",
        model: "gpt-4.1-mini",
        privacyAcknowledged: true,
      }),
    );
    expect(state.saveCalls[0]).toEqual({
      baseUrl: "https://api.openai.com/v1",
      model: "gpt-4.1-mini",
      privacyAcknowledged: true,
    });
    expect(JSON.stringify(state.saveCalls[0])).not.toContain("sk-test-key");
    expect(state.secretSets).toEqual([llmApiKeyInvokeArgs("sk-test-key")]);
    expect(state.secretSets[0]).toEqual({id: LLM_API_KEY_SECRET_ID, value: "sk-test-key"});
    expect(LLM_SETTINGS_SAVE_COMMAND).toBe("set_llm_settings");
    expect(await screen.findByTestId("llm-saved")).toHaveTextContent("Saved.");
    expect(screen.getByTestId("llm-api-key")).toHaveValue("");
  });

  it("treats a loopback address as a local provider and allows an empty key", async () => {
    const language = createMemoryLanguagePort({preference: "zh", systemLocale: "zh-CN"});
    const {port, state} = createMemoryLlmSettingsPort();
    render(
      <I18nProvider port={language} initial={{preference: "zh", systemLocale: "zh-CN", resolved: "zh"}}>
        <SettingsPage route="#/settings/llm" llmPort={port} />
      </I18nProvider>,
    );
    fireEvent.change(await screen.findByTestId("llm-base-url"), {
      target: {value: "http://127.0.0.1:11434/v1"},
    });
    expect(screen.getByTestId("llm-local-status")).toHaveTextContent("使用本地模型");
    expect(screen.getByTestId("llm-no-key")).toHaveTextContent("此地址不使用密钥");
    fireEvent.change(screen.getByTestId("llm-model"), {target: {value: "qwen"}});
    fireEvent.click(screen.getByTestId("llm-privacy"));
    fireEvent.click(screen.getByTestId("llm-save"));
    await waitFor(() => expect(state.saveCalls).toHaveLength(1));
    expect(state.secretSets).toEqual([]);
    expect(state.saveCalls[0].privacyAcknowledged).toBe(true);
  });

  it("refuses a remote save until privacy is acknowledged and a key exists", async () => {
    const language = createMemoryLanguagePort({preference: "en", systemLocale: "en-US"});
    const {port, state} = createMemoryLlmSettingsPort();
    render(
      <I18nProvider port={language} initial={EN}>
        <SettingsPage route="#/settings/llm" llmPort={port} />
      </I18nProvider>,
    );
    fireEvent.change(await screen.findByTestId("llm-base-url"), {
      target: {value: "https://api.openai.com/v1"},
    });
    fireEvent.change(screen.getByTestId("llm-model"), {target: {value: "gpt-4.1-mini"}});
    fireEvent.click(screen.getByTestId("llm-save"));
    expect(await screen.findByTestId("llm-error")).toHaveTextContent("Confirm the privacy note");
    expect(state.saveCalls).toEqual([]);
    fireEvent.click(screen.getByTestId("llm-privacy"));
    fireEvent.click(screen.getByTestId("llm-save"));
    expect(await screen.findByTestId("llm-error")).toHaveTextContent("needs an API key");
    expect(state.saveCalls).toEqual([]);
  });
});
