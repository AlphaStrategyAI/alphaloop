import "@fontsource/noto-serif/500.css";
import "@fontsource/noto-serif-sc/500.css";
import "@fontsource/noto-sans-sc/400.css";
import "@fontsource/ibm-plex-mono/400.css";
import {invoke} from "@tauri-apps/api/core";
import {StrictMode} from "react";
import {createRoot} from "react-dom/client";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

const desktopApi: DesktopApi = {
  async fetchView(route) { return invoke<DesktopView>("fetch_view", {route}); },
  async createDraft() { return invoke<string>("create_draft"); },
  async confirmRun(researchId) { await invoke("confirm_run", {researchId}); },
  async sendDialogue(researchId, message) { await invoke("send_dialogue", {researchId, message}); },
  async pauseResearch(researchId) { await invoke("pause_research", {researchId}); },
  async resumeResearch(researchId) { await invoke("resume_research", {researchId}); },
  async confirmModification(researchId) { await invoke("confirm_modification", {researchId}); },
  async extendResearch(researchId, hours) { await invoke("extend_research", {researchId, hours}); },
  async deleteResearch(researchId) { await invoke("delete_research", {researchId}); },
  async resolveConfirm(researchId, decision) { await invoke("resolve_confirm", {researchId, decision}); },
  async exportArtifact(researchId, kind) { await invoke("export_artifact", {researchId, kind}); },
  async reverify(researchId, roundId, methodId) {
    await invoke("reverify", {researchId, roundId, methodId});
  },
  async reviseMethod(methodId, definition) { await invoke("revise_method", {methodId, definition}); },
};

const previewApi: DesktopApi = {
  async fetchView() { return preview; },
  async createDraft() { return "preview-draft"; },
  async confirmRun() { return undefined; },
  async sendDialogue() { return undefined; },
  async pauseResearch() { return undefined; },
  async resumeResearch() { return undefined; },
  async confirmModification() { return undefined; },
  async extendResearch() { return undefined; },
  async deleteResearch() { return undefined; },
  async resolveConfirm() { return undefined; },
  async exportArtifact() { return undefined; },
  async reverify() { return undefined; },
  async reviseMethod() { return undefined; },
};

const preview: DesktopView = {kind: "research_list", rows: []};
const api = "__TAURI_INTERNALS__" in window ? desktopApi : previewApi;
createRoot(document.getElementById("root")!).render(
  <StrictMode><App api={api} initialView={preview} /></StrictMode>,
);
