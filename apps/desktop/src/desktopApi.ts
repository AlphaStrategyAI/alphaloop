import {invoke as tauriInvoke} from "@tauri-apps/api/core";

import {confirmRunInvokeArgs} from "./confirmRunCommand";
import {setPriceSourceInvokeArgs} from "./setPriceSourceCommand";
import type {DesktopApi, DesktopView} from "./contracts";

export type DesktopInvoke = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;

/** Tauri command bindings. Arguments here are the engine payload's fields. */
export function createTauriDesktopApi(invoke: DesktopInvoke = tauriInvoke): DesktopApi {
  return {
    async fetchView(route) { return invoke<DesktopView>("fetch_view", {route}); },
    async pollMarketDataProgress() { return invoke("market_data_progress"); },
    async createDraft(envelope) {
      if (!envelope) return invoke<string>("create_draft");
      return invoke<string>("create_draft", {
        researchId: envelope.researchId,
        commandId: envelope.commandId,
      });
    },
    async confirmRun(researchId, options) {
      await invoke("confirm_run", confirmRunInvokeArgs(researchId, options));
    },
    async setPriceSource(researchId, dataSourceId, unlicensedAcknowledged) {
      const revision = await invoke<number | null>(
        "set_price_source",
        setPriceSourceInvokeArgs(researchId, dataSourceId, unlicensedAcknowledged),
      );
      return typeof revision === "number" ? revision : undefined;
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
    async dismissMismatchedSymbol(researchId, symbol) {
      await invoke("dismiss_mismatched_symbol", {researchId, symbol});
    },
    async chooseDefaultMarket(researchId, market) {
      await invoke("choose_default_market", {researchId, market});
    },
    async unlockBrief(researchId, slot) { await invoke("unlock_brief", {researchId, slot}); },
    async sendDialogue(researchId, message, envelope) {
      const args: Record<string, unknown> = {researchId, message};
      if (envelope) {
        args.commandId = envelope.commandId;
        args.expectedRevision = envelope.expectedRevision;
        if (envelope.replyTo) args.replyTo = envelope.replyTo;
      }
      await invoke("send_dialogue", args);
    },
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
    async resolveConfirm(researchId, decision, whoPays, requestId) {
      const args: Record<string, unknown> = {researchId, decision};
      if (whoPays) args.whoPays = whoPays;
      if (requestId) args.requestId = requestId;
      await invoke("resolve_confirm", args);
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
    async setPriceSource() { return undefined; },
    async setResearchSymbol() { return undefined; },
    async answerSymbolAsk() { return undefined; },
    async useHintedSymbol() { return undefined; },
    async revertSymbolAsk() { return undefined; },
    async removeMarketSide() { return undefined; },
    async dismissMismatchedSymbol() { return undefined; },
    async chooseDefaultMarket() { return undefined; },
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
