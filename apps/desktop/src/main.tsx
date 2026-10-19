import "@fontsource/noto-serif/500.css";
import "@fontsource/noto-serif-sc/500.css";
import "@fontsource/noto-sans-sc/400.css";
import "@fontsource/ibm-plex-mono/400.css";
import {invoke} from "@tauri-apps/api/core";

import type {SidecarUiState} from "./contracts";
import {StrictMode} from "react";
import {createRoot} from "react-dom/client";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";
import {readBrowserRoute} from "./routing";

const desktopApi: DesktopApi = {
  async fetchView(route) { return invoke<DesktopView>("fetch_view", {route}); },
  async pollMarketDataProgress() { return invoke("market_data_progress"); },
  async createDraft() { return invoke<string>("create_draft"); },
  async confirmRun(researchId) { await invoke("confirm_run", {researchId}); },
  async unlockBrief(researchId, slot) { await invoke("unlock_brief", {researchId, slot}); },
  async sendDialogue(researchId, message) { await invoke("send_dialogue", {researchId, message}); },
  async pauseResearch(researchId) { await invoke("pause_research", {researchId}); },
  async resumeResearch(researchId) { await invoke("resume_research", {researchId}); },
  async confirmModification(researchId) { await invoke("confirm_modification", {researchId}); },
  async continueIterate(researchId, options) {
    await invoke("continue_iterate", {
      researchId,
      userConfirmed: options.userConfirmed,
      highSuspicionAcknowledged: options.highSuspicionAcknowledged ?? false,
    });
  },
  async extendResearch(researchId, hours) { await invoke("extend_research", {researchId, hours}); },
  async deleteResearch(researchId) { await invoke("delete_research", {researchId}); },
  async resolveConfirm(researchId, decision, whoPays) {
    await invoke("resolve_confirm", {researchId, decision, whoPays});
  },
  async exportArtifact(researchId, kind) {
    return invoke<string>("export_artifact", {researchId, kind});
  },
  async revealExportInFolder(path) { await invoke("reveal_export_in_folder", {path}); },
  async reverify(researchId, roundId, methodId) {
    await invoke("reverify", {researchId, roundId, methodId});
  },
  async reviseMethod(methodId, definition) { await invoke("revise_method", {methodId, definition}); },
  async createMethod(name, definition) { await invoke("create_method", {name, definition}); },
};

const previewApi: DesktopApi = {
  async fetchView() { return preview; },
  async createDraft() { return "preview-draft"; },
  async confirmRun() { return undefined; },
  async unlockBrief() { return undefined; },
  async sendDialogue() { return undefined; },
  async pauseResearch() { return undefined; },
  async resumeResearch() { return undefined; },
  async confirmModification() { return undefined; },
  async continueIterate() { return undefined; },
  async extendResearch() { return undefined; },
  async deleteResearch() { return undefined; },
  async resolveConfirm() { return undefined; },
  async exportArtifact() { return "/tmp/preview-export.zip"; },
  async revealExportInFolder() { return undefined; },
  async reverify() { return undefined; },
  async reviseMethod() { return undefined; },
  async createMethod() { return undefined; },
};

const preview: DesktopView = {kind: "research_list", rows: []};
const api = "__TAURI_INTERNALS__" in window ? desktopApi : previewApi;
const bootRoute = readBrowserRoute();
const pollSidecar =
  "__TAURI_INTERNALS__" in window
    ? async () => invoke<SidecarUiState>("engine_sidecar_state")
    : undefined;
const restartSidecar =
  "__TAURI_INTERNALS__" in window
    ? async () => {
        await invoke("restart_engine_sidecar");
      }
    : undefined;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App
      api={api}
      initialView={preview}
      initialRoute={bootRoute}
      pollSidecar={pollSidecar}
      restartSidecar={restartSidecar}
    />
  </StrictMode>,
);
