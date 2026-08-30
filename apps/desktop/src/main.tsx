import "@fontsource/noto-serif/500.css";
import "@fontsource/noto-serif-sc/500.css";
import "@fontsource/noto-sans-sc/400.css";
import "@fontsource/ibm-plex-mono/400.css";
import {StrictMode} from "react";
import {createRoot} from "react-dom/client";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

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
createRoot(document.getElementById("root")!).render(
  <StrictMode><App api={previewApi} initialView={preview} /></StrictMode>,
);
