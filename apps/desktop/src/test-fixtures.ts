import type {DesktopApi, DesktopView} from "./contracts";

export const emptyResearchListView: DesktopView = {
  kind: "research_list",
  rows: [],
};

/** Minimal DesktopApi for tests; override `fetchView` as needed. */
export function minimalDesktopApi(overrides: Partial<DesktopApi> = {}): DesktopApi {
  return {
    fetchView: async () => emptyResearchListView,
    createDraft: async () => "r-test",
    confirmRun: async () => undefined,
    setResearchSymbol: async () => undefined,
    answerSymbolAsk: async () => undefined,
    useHintedSymbol: async () => undefined,
    revertSymbolAsk: async () => undefined,
    removeMarketSide: async () => undefined,
    dismissMismatchedSymbol: async () => undefined,
    chooseDefaultMarket: async () => undefined,
    unlockBrief: async () => undefined,
    sendDialogue: async () => undefined,
    pauseResearch: async () => undefined,
    resumeResearch: async () => undefined,
    confirmModification: async () => undefined,
    continueIterate: async () => undefined,
    extendResearch: async () => undefined,
    deleteResearch: async () => undefined,
    resolveConfirm: async () => undefined,
    exportArtifact: async () => "/tmp/export.zip",
    revealExportInFolder: async () => undefined,
    reverify: async () => undefined,
    reviseMethod: async () => undefined,
    createMethod: async () => undefined,
    ...overrides,
  };
}
