/**
 * Whether Run is enabled. The engine's `evaluate_run_gate` is the same decision:
 * a hard block (family, market, symbol) is not cleared by picking a data source,
 * and a stored per-source acknowledgement satisfies an unlicensed source.
 */

export type RunGateCode =
  | "MARKET_CHOICE_PENDING"
  | "DATA_SOURCE_UNBOUND"
  | "UNLICENSED_SOURCE_UNACKNOWLEDGED"
  | "STRATEGY_FAMILY_NOT_RUNNABLE"
  | "SYMBOL_MARKET_MISMATCH"
  | "SYMBOL_MIXED_MARKETS"
  | "SYMBOL_UNRESOLVED"
  | "SYMBOL_ASK_PENDING"
  | "SYMBOL_AMOUNT_LIKE"
  | "SYMBOL_ETF_UNSUPPORTED"
  | "SYMBOL_NO_DATA"
  | "SYMBOL_SOURCE_MISMATCH"
  | string;

const SOURCE_CODES = new Set([
  "DATA_SOURCE_UNBOUND",
  "UNLICENSED_SOURCE_UNACKNOWLEDGED",
  "SYMBOL_SOURCE_MISMATCH",
]);

export type DerivedRunGate = {
  runnable: boolean;
  code: RunGateCode | null;
};

export function deriveRunGate(input: {
  serverCode: string | null | undefined;
  resolutionBlocked: boolean;
  resolutionCode: string | null | undefined;
  marketPending: boolean;
  /** The card is asking the user to pick a price source. */
  sourceChoiceOnCard: boolean;
  selectedId: string;
  selectedMarket: "CN" | "US" | null;
  cardMarket: "CN" | "US" | null;
  unlicensed: boolean;
  acknowledgedAt: string | null | undefined;
  checkboxAcked: boolean;
}): DerivedRunGate {
  if (input.marketPending) return {runnable: false, code: "MARKET_CHOICE_PENDING"};
  if (input.resolutionBlocked && input.resolutionCode) {
    return {runnable: false, code: input.resolutionCode};
  }
  const server = input.serverCode || null;
  if (server && !SOURCE_CODES.has(server)) return {runnable: false, code: server};
  if (!input.sourceChoiceOnCard) return {runnable: true, code: null};
  if (
    input.selectedId
    && input.selectedMarket
    && input.cardMarket
    && input.selectedMarket !== input.cardMarket
  ) {
    return {runnable: false, code: "SYMBOL_SOURCE_MISMATCH"};
  }
  if (!input.selectedId) return {runnable: false, code: "DATA_SOURCE_UNBOUND"};
  if (input.unlicensed && !input.acknowledgedAt && !input.checkboxAcked) {
    return {runnable: false, code: "UNLICENSED_SOURCE_UNACKNOWLEDGED"};
  }
  if (server === "SYMBOL_SOURCE_MISMATCH") return {runnable: false, code: server};
  return {runnable: true, code: null};
}

/** Value stored on the Run button so a GUI test can tell why it is disabled. */
export function runBlockedToken(code: string | null): string | undefined {
  if (!code) return undefined;
  if (code === "MARKET_CHOICE_PENDING") return "market";
  if (code === "DATA_SOURCE_UNBOUND") return "source";
  if (code === "STRATEGY_FAMILY_NOT_RUNNABLE") return "family";
  if (code === "UNLICENSED_SOURCE_UNACKNOWLEDGED") return "unlicensed";
  return "resolution";
}
