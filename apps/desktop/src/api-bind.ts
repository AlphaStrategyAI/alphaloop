import type {DesktopApi} from "./contracts";

type BindDeps = {
  refresh: () => Promise<void>;
  onError: (message: string) => void;
  onSuccess?: () => void;
};

async function runMutation<T>(
  action: () => Promise<T>,
  deps: BindDeps,
): Promise<T> {
  try {
    const result = await action();
    deps.onSuccess?.();
    await deps.refresh();
    return result;
  } catch (error) {
    deps.onError(error instanceof Error ? error.message : String(error));
    throw error;
  }
}

/** Wrap mutation API calls: surface errors and refresh the current route view. */
export function bindDesktopApi(api: DesktopApi, deps: BindDeps): DesktopApi {
  return {
    fetchView: (route) => api.fetchView(route),
    createDraft: () => runMutation(() => api.createDraft(), deps),
    confirmRun: (researchId) => runMutation(() => api.confirmRun(researchId), deps),
    setResearchSymbol: (researchId, symbol) =>
      runMutation(() => api.setResearchSymbol(researchId, symbol), deps),
    unlockBrief: (researchId, slot) =>
      runMutation(() => api.unlockBrief(researchId, slot), deps),
    sendDialogue: (researchId, message) =>
      runMutation(() => api.sendDialogue(researchId, message), deps),
    pauseResearch: (researchId) => runMutation(() => api.pauseResearch(researchId), deps),
    resumeResearch: (researchId) => runMutation(() => api.resumeResearch(researchId), deps),
    confirmModification: (researchId) =>
      runMutation(() => api.confirmModification(researchId), deps),
    continueIterate: (researchId, options) =>
      runMutation(() => api.continueIterate(researchId, options), deps),
    extendResearch: (researchId, hours) =>
      runMutation(() => api.extendResearch(researchId, hours), deps),
    deleteResearch: (researchId) => runMutation(() => api.deleteResearch(researchId), deps),
    resolveConfirm: (researchId, decision, whoPays) =>
      runMutation(
        () =>
          whoPays === undefined
            ? api.resolveConfirm(researchId, decision)
            : api.resolveConfirm(researchId, decision, whoPays),
        deps,
      ),
    exportArtifact: (researchId, kind) =>
      runMutation(() => api.exportArtifact(researchId, kind), deps),
    revealExportInFolder: (path) => api.revealExportInFolder(path),
    reverify: (researchId, roundId, methodId) =>
      runMutation(() => api.reverify(researchId, roundId, methodId), deps),
    reviseMethod: (methodId, definition) =>
      runMutation(() => api.reviseMethod(methodId, definition), deps),
    createMethod: (name, definition) => runMutation(() => api.createMethod(name, definition), deps),
  };
}
