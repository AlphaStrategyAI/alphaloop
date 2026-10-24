import type {DesktopApi} from "./contracts";

type BindDeps = {
  refresh: () => Promise<void>;
  onError: (message: string) => void;
  onSuccess?: () => void;
};

type AsyncFn = (...args: never[]) => Promise<unknown>;
type Params<T> = T extends (...args: infer A) => unknown ? A : never;

/**
 * Parameter tuples compared in both directions. A function with fewer
 * parameters is still assignable to `DesktopApi["confirmRun"]`, which is how
 * the binding compiled while dropping `options`. This check does not allow that.
 */
type SameParams<Expected, Actual> = [Params<Expected>] extends [Params<Actual>]
  ? [Params<Actual>] extends [Params<Expected>]
    ? true
    : false
  : false;

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

/** Forward every argument. The wrapper's parameter list is the method's. */
function bindMethod<T extends AsyncFn>(method: T, deps: BindDeps): T {
  return ((...args: Params<T>) => runMutation(() => method(...args), deps)) as T;
}

/** Wrap mutation API calls: surface errors and refresh the current route view. */
export function bindDesktopApi(api: DesktopApi, deps: BindDeps): DesktopApi {
  const confirmRun = bindMethod(api.confirmRun, deps);
  const _confirmRunKeepsOptions: SameParams<DesktopApi["confirmRun"], typeof confirmRun> = true;
  const _shortConfirmRunIsRejected: SameParams<
    DesktopApi["confirmRun"],
    (researchId: string) => Promise<void>
  > = false;
  void _confirmRunKeepsOptions;
  void _shortConfirmRunIsRejected;

  return {
    fetchView: (route) => api.fetchView(route),
    createDraft: bindMethod(api.createDraft, deps),
    confirmRun,
    setResearchSymbol: bindMethod(api.setResearchSymbol, deps),
    answerSymbolAsk: bindMethod(api.answerSymbolAsk, deps),
    useHintedSymbol: bindMethod(api.useHintedSymbol, deps),
    unlockBrief: bindMethod(api.unlockBrief, deps),
    sendDialogue: bindMethod(api.sendDialogue, deps),
    pauseResearch: bindMethod(api.pauseResearch, deps),
    resumeResearch: bindMethod(api.resumeResearch, deps),
    confirmModification: bindMethod(api.confirmModification, deps),
    continueIterate: bindMethod(api.continueIterate, deps),
    extendResearch: bindMethod(api.extendResearch, deps),
    deleteResearch: bindMethod(api.deleteResearch, deps),
    resolveConfirm: (researchId, decision, whoPays) =>
      runMutation(
        () =>
          whoPays === undefined
            ? api.resolveConfirm(researchId, decision)
            : api.resolveConfirm(researchId, decision, whoPays),
        deps,
      ),
    exportArtifact: bindMethod(api.exportArtifact, deps),
    revealExportInFolder: (path) => api.revealExportInFolder(path),
    reverify: bindMethod(api.reverify, deps),
    reviseMethod: bindMethod(api.reviseMethod, deps),
    createMethod: bindMethod(api.createMethod, deps),
    pollMarketDataProgress: api.pollMarketDataProgress?.bind(api),
  };
}
