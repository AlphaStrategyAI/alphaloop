import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {useState} from "react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "../App";
import {I18nProvider} from "../i18n/I18nProvider";
import {createMemoryLanguagePort} from "../i18n/port";
import type {UiLanguagePreference} from "../i18n/types";
import {minimalDesktopApi} from "../test-fixtures";
import {createMemoryLlmSettingsPort} from "./llmSettingsPort";
import {SettingsPage} from "./SettingsPage";

afterEach(() => cleanup());

function Harness({route}: {route: string}) {
  const [ticks, setTicks] = useState(0);
  return (
    <>
      <button type="button" onClick={() => setTicks((value) => value + 1)}>tick</button>
      <span data-testid="ticks">{ticks}</span>
      <SettingsPage route={route} />
    </>
  );
}

describe("settings language", () => {
  it("says local file import arrives in M2 on the data sources page", async () => {
    const port = createMemoryLanguagePort({preference: "zh", systemLocale: "zh-CN"});
    const zh = render(
      <I18nProvider port={port} initial={{preference: "zh", systemLocale: "zh-CN", resolved: "zh"}}>
        <SettingsPage route="#/settings/data" />
      </I18nProvider>,
    );
    expect(await screen.findByTestId("settings-later")).toHaveTextContent("本地文件导入将在 M2 提供。");
    zh.unmount();

    render(
      <I18nProvider port={port} initial={{preference: "en", systemLocale: "en-US", resolved: "en"}}>
        <SettingsPage route="#/settings/data" />
      </I18nProvider>,
    );
    const later = await screen.findByTestId("settings-later");
    expect(later).toHaveTextContent("Local file import arrives in M2.");
    expect(later.querySelector("[data-i18n-placeholder]")).toBeNull();
  });

  it("does not reuse the data-sources sentence on the LLM tab", async () => {
    const port = createMemoryLanguagePort({preference: "en", systemLocale: "en-US"});
    const llmPort = createMemoryLlmSettingsPort().port;
    const en = render(
      <I18nProvider port={port} initial={{preference: "en", systemLocale: "en-US", resolved: "en"}}>
        <SettingsPage route="#/settings/llm" llmPort={llmPort} />
      </I18nProvider>,
    );
    const panel = await screen.findByTestId("settings-llm");
    expect(panel).not.toHaveTextContent(/not ready/i);
    expect(panel).not.toHaveTextContent("Local file import arrives in M2.");
    expect(panel).not.toHaveTextContent("本地文件导入将在 M2 提供。");
    expect(panel.querySelector("[data-i18n-placeholder]")).toBeNull();
    expect(screen.getByTestId("llm-base-url")).toBeInTheDocument();
    expect(screen.getByTestId("llm-api-key")).toHaveAttribute("type", "password");
    expect(screen.getByTestId("llm-model")).toBeInTheDocument();
    expect(panel).toHaveTextContent("Local model");
    en.unmount();

    render(
      <I18nProvider port={port} initial={{preference: "zh", systemLocale: "zh-CN", resolved: "zh"}}>
        <SettingsPage route="#/settings/llm" llmPort={llmPort} />
      </I18nProvider>,
    );
    const zhLlm = await screen.findByTestId("settings-llm");
    expect(zhLlm).toHaveTextContent("接入地址");
    expect(zhLlm).toHaveTextContent("API 密钥");
    expect(zhLlm).toHaveTextContent("模型名");
    expect(zhLlm).toHaveTextContent("本机模型");
    expect(zhLlm).not.toHaveTextContent("本地文件导入将在 M2 提供。");
    expect(screen.getByTestId("settings-tab-llm")).toHaveClass("active");
  });

  it("persists the preference and restores it on the next mount", async () => {
    const port = createMemoryLanguagePort({preference: "system", systemLocale: "zh-CN"});
    const first = render(
      <I18nProvider port={port}>
        <SettingsPage route="#/settings/general" />
      </I18nProvider>,
    );
    expect(await screen.findByRole("radio", {name: /跟随系统/})).toBeChecked();
    screen.getByRole("radio", {name: "English"}).click();
    await waitFor(() => expect(screen.getByRole("heading", {name: /Interface language/})).toBeInTheDocument());
    expect(port.engineLocales.at(-1)).toBe("en");
    first.unmount();

    render(
      <I18nProvider port={port}>
        <SettingsPage route="#/settings/general" />
      </I18nProvider>,
    );
    expect(await screen.findByRole("radio", {name: "English"})).toBeChecked();
    expect(screen.getByRole("heading", {name: /Interface language/})).toBeInTheDocument();
  });

  it("redraws immediately, before the preference write finishes", async () => {
    const port = createMemoryLanguagePort({preference: "system", systemLocale: "zh-CN"});
    let release: (preference: UiLanguagePreference) => void = () => undefined;
    const original = port.save.bind(port);
    port.save = (preference) =>
      new Promise((resolve) => {
        release = () => resolve(original(preference));
      });
    render(
      <I18nProvider port={port} initial={{preference: "system", systemLocale: "zh-CN", resolved: "zh"}}>
        <Harness route="#/settings/general" />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByRole("button", {name: "tick"}));
    expect(screen.getByTestId("ticks")).toHaveTextContent("1");
    fireEvent.click(screen.getByRole("radio", {name: "English"}));
    await waitFor(() => expect(screen.getByRole("heading", {name: /Interface language/})).toBeInTheDocument());
    expect(screen.getByTestId("ticks")).toHaveTextContent("1");
    expect(screen.queryByText("settings.general.title")).not.toBeInTheDocument();
    const heading = screen.getByRole("heading", {name: "Interface language"});
    expect(heading.textContent).toBe("Interface language");
    expect(heading.querySelector("[data-i18n-placeholder]")).not.toBeNull();
    release("en");
    await waitFor(() => expect(port.engineLocales.at(-1)).toBe("en"));
  });

  it("re-reads the system locale when follow-system is chosen again, not while the app is sitting open", async () => {
    const port = createMemoryLanguagePort({preference: "system", systemLocale: "zh-CN"});
    render(
      <I18nProvider port={port} initial={{preference: "system", systemLocale: "zh-CN", resolved: "zh"}}>
        <SettingsPage route="#/settings/general" />
      </I18nProvider>,
    );
    const zhHeading = screen.getByRole("heading", {name: "界面语言"});
    expect(zhHeading.querySelector("[data-i18n-placeholder]")).toBeNull();
    expect(screen.getByRole("radio", {name: /跟随系统/})).toHaveAccessibleName(expect.stringContaining("中文"));
    port.setSystemLocale("en-US");
    expect(screen.getByRole("heading", {name: "界面语言"})).toBeInTheDocument();
    expect(screen.getByRole("radio", {name: /跟随系统/})).toHaveAccessibleName(expect.stringContaining("中文"));
    fireEvent.click(screen.getByRole("radio", {name: "English"}));
    await waitFor(() => expect(screen.getByRole("heading", {name: /Interface language/})).toBeInTheDocument());
    const follow = screen.getByRole("radio", {name: /Follow system/});
    follow.click();
    await waitFor(() =>
      expect(screen.getByRole("radio", {name: /Follow system/})).toHaveAccessibleName(
        expect.stringContaining("now: English"),
      ),
    );
    expect(screen.getByRole("radio", {name: /Follow system/})).toBeChecked();
    expect(screen.queryByRole("heading", {name: "界面语言"})).not.toBeInTheDocument();
  });

  it("does not ask the engine for the settings route", async () => {
    const fetchView = vi.fn(async () => {
      throw new Error("settings must stay on the desktop");
    });
    const port = createMemoryLanguagePort({preference: "zh", systemLocale: "en-US"});
    render(
      <I18nProvider port={port} initial={{preference: "zh", systemLocale: "en-US", resolved: "zh"}}>
        <App
          api={minimalDesktopApi({fetchView})}
          initialView={{kind: "research_list", rows: []}}
          initialRoute="#/settings/general"
        />
      </I18nProvider>,
    );
    expect(await screen.findByTestId("settings-page")).toBeInTheDocument();
    expect(screen.getByRole("link", {name: "设置"})).toHaveClass("active");
    expect(fetchView).not.toHaveBeenCalled();
    expect(screen.getByRole("radio", {name: "中文"})).toBeChecked();
    expect(screen.getByRole("radio", {name: /跟随系统/})).toHaveAccessibleName(expect.stringContaining("English"));
  });

  it("shows the baked version and commit on the about card", async () => {
    render(
      <I18nProvider initial={{preference: "en", systemLocale: "en-US", resolved: "en"}}>
        <SettingsPage route="#/settings/general" />
      </I18nProvider>,
    );
    expect(await screen.findByTestId("about-version")).toHaveTextContent("Version 0.9.4");
    expect(screen.getByTestId("about-sha")).toHaveTextContent("Commit unknown");
  });
});
