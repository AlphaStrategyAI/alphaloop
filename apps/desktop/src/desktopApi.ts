import {invoke as tauriInvoke} from "@tauri-apps/api/core";

import {confirmRunInvokeArgs} from "./confirmRunCommand";
import type {DesktopApi, DesktopView} from "./contracts";

export type DesktopInvoke = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;

/** Tauri command bindings. Arguments here are the engine payload's fields. */
export function createTauriDesktopApi(invoke: DesktopInvoke = tauriInvoke): DesktopApi {
  return {
    async fetchView(route) { return invoke<DesktopView>("fetch_view", {route}); },
    async pollMarketDataProgress() { return invoke("market_data_progress"); },
    async createDraft() { return invoke<string>("create_draft"); },
    async confirmRun(researchId, options) {
      await invoke("confirm_run", confirmRunInvokeArgs(researchId, options));
    },
    async setResearchSymbol(researchId, symbol) {
      await invoke("set_research_symbol", {researchId, symbol});
    },
    async answerSymbolAsk(researchId, token, accept) {
      await invoke("answer_symbol_ask", {researchId, token, accept});
    },
    async useHintedSymbol(researchId, symbol) {
      await invoke("use_hinted_symbol", {researchId, symbol});
    },
    async revertSymbolAsk(researchId, token) {
      await invoke("revert_symbol_ask", {researchId, token});
    },
    async removeMarketSide(researchId, side) {
      await invoke("remove_market_side", {researchId, side});
    },
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
}

export function createPreviewDesktopApi(preview: DesktopView): DesktopApi {
  return {
    async fetchView() { return preview; },
    async createDraft() { return "preview-draft"; },
    async confirmRun() { return undefined; },
    async setResearchSymbol() { return undefined; },
    async answerSymbolAsk() { return undefined; },
    async useHintedSymbol() { return undefined; },
    async revertSymbolAsk() { return undefined; },
    async removeMarketSide() { return undefined; },
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
}
