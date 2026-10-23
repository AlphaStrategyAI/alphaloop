import "@fontsource/noto-serif/500.css";
import "@fontsource/noto-serif-sc/500.css";
import "@fontsource/noto-sans-sc/400.css";
import "@fontsource/ibm-plex-mono/400.css";
import {invoke} from "@tauri-apps/api/core";

import type {SidecarUiState} from "./contracts";
import {StrictMode} from "react";
import {createRoot} from "react-dom/client";

import {App} from "./App";
import type {DesktopView} from "./contracts";
import {createPreviewDesktopApi, createTauriDesktopApi} from "./desktopApi";
import {I18nProvider} from "./i18n/I18nProvider";
import {tauriLanguagePort, createMemoryLanguagePort} from "./i18n/port";
import {readBrowserRoute} from "./routing";

const preview: DesktopView = {kind: "research_list", rows: []};
const desktopApi = createTauriDesktopApi(invoke);
const previewApi = createPreviewDesktopApi(preview);
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

const languagePort =
  "__TAURI_INTERNALS__" in window
    ? tauriLanguagePort
    : createMemoryLanguagePort({systemLocale: navigator.language || null});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider port={languagePort}>
      <App
        api={api}
        initialView={preview}
        initialRoute={bootRoute}
        pollSidecar={pollSidecar}
        restartSidecar={restartSidecar}
      />
    </I18nProvider>
  </StrictMode>,
);
