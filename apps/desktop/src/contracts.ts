export type ResearchStatus =
  | "draft"
  | "running"
  | "awaiting_confirm"
  | "paused"
  | "completed"
  | "ended";

/** List-row display only: draft with all brief slots locked (confirm_run view). */
export type ResearchListDisplayStatus = ResearchStatus | "confirm_run";

export type HostStatus = "awaiting_confirm" | "running" | "completed" | "idle";

export type SidecarPhase = "running" | "restarting" | "stopped";

export interface SidecarUiState {
  phase: SidecarPhase;
  restartCount: number;
  maxRestarts: number;
  message: string;
}

export type ConfirmationDecision =
  | "approve_new_version"
  | "reject_keep_logic"
  | "pause_and_edit"
  | "accept_lower_floor"
  | "supply_local_materials"
  | "redefine_scope";

export type ExportKind = "strategy_pack" | "research_record";

export type BriefSlotName =
  | "thesis"
  | "universe"
  | "max_effective_hours"
  | "round1_methods"
  | "coverage_floor";

export interface SymbolResolution {
  blocked: boolean;
  code?:
    | "SYMBOL_UNRESOLVED"
    | "SYMBOL_NO_DATA"
    | "SYMBOL_ETF_UNSUPPORTED"
    | "SYMBOL_ASK_PENDING"
    | "SYMBOL_AMOUNT_LIKE"
    | "SYMBOL_MIXED_MARKETS"
    | "SYMBOL_MARKET_MISMATCH"
    | "MARKET_CHOICE_PENDING"
    | null;
  token?: string | null;
  symbol?: string | null;
  symbols: readonly string[];
  inferred: readonly {raw: string; symbol: string}[];
  editable: boolean;
  asks?: readonly {token: string; symbol: string; kind?: "ask" | "finance" | "amount"}[];
  answers?: readonly {token: string; symbol: string; kind?: string; accept: boolean}[];
  hints?: readonly {token: string; symbol: string}[];
  poolCount?: number | null;
  cnSymbols?: string | null;
  usSymbols?: string | null;
  mismatches?: readonly string[];
  mismatchMarket?: "US" | "CN" | null;
  unrecognized?: readonly {token: string}[];
}

export interface PriceSourceChoice {
  id: string;
  label: string;
  unlicensed: boolean;
  acknowledgedAt?: string | null;
  /** Market this row covers. A pick for another market is not a selection. */
  market?: "CN" | "US" | null;
}

export interface SymbolSelectionSummary {
  count: number;
  listName: string;
  listVersion: string;
  summaryLine?: string;
  listNote?: string;
  listNameEn?: string;
  listNoteEn?: string;
  generatedDate?: string;
  symbols: readonly string[];
  source: "default_pool" | "user_override";
  overrideNote?: string | null;
  dataStart: string;
  dataEnd: string;
  dataCutoff: string;
  dataSource: string;
  dataSourceId?: string | null;
  dataSourcePending?: boolean;
  /** Engine-owned list. The card does not decide which row is preselected. */
  priceSources?: readonly PriceSourceChoice[];
  offeredDataSourceId?: string;
  offeredDataSource?: string;
  unlicensedAcknowledgedAt?: string | null;
  unlicensedAcknowledgementRequired?: boolean;
  droppedForMissingData?: number;
  shrinkNote?: string | null;
  isDefaultPool?: boolean;
}

export interface BriefSettings {
  thesis: string;
  universe: string;
  universe_symbols?: string;
  universe_symbol_chips?: readonly string[];
  max_effective_hours: string;
  round1_methods: string;
  coverage_floor: string;
}

export interface ResearchSummary {
  id: string;
  title: string;
  status: ResearchListDisplayStatus;
  universeLabel?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface GlossaryEntry {
  id: string;
  term: string;
  body: string;
}

export interface ValidationMethod {
  id: string;
  name: string;
  revision: string;
  revisionLabel?: string;
  description: string;
  definitionDisplay?: string;
  usageCount?: number;
  source?: string;
  category?: string;
  dimensions?: readonly ScorecardDimension[];
}

export type DialogueTurnView = {
  role: "user" | "assistant";
  text: string;
  errorCode?: string;
  errorParams?: Record<string, string | number>;
  errorDetail?: string | null;
};

type ViewBody =
  | {kind: "research_list"; awaiting?: ResearchSummary; rows: readonly ResearchSummary[]}
  | {
      kind: "draft";
      researchId: string;
      dialogue: readonly DialogueTurnView[];
      settings: BriefSettings;
    }
  | {
      kind: "confirm_run";
      researchId: string;
      dialogue: readonly DialogueTurnView[];
      settings: BriefSettings;
      chatEnabled?: boolean;
      symbolSelection?: SymbolSelectionSummary;
      symbolResolution?: SymbolResolution | null;
      confirmDataNotice?: string | null;
      confirmDataNoticeCode?: string | null;
      confirmDataNoticeParams?: Record<string, string | number> | null;
      meanReversionOnlyNotice?: string | null;
      /** Family id the user named after an unsupported thesis. The card fills {{family}}. */
      repickedFamily?: string | null;
      constructionNotice?: string | null;
      /** Engine gate. Run stays disabled when this code is not a source choice. */
      runGate?: {runnable: boolean; code?: string | null} | null;
      market?: "CN" | "US" | null;
      marketSwitch?: {market: "US" | "CN"; benchmark: string} | null;
      marketChoice?: {pending: boolean; cnCount: number; usCount: number} | null;
      benchmarkName?: string | null;
    }
  | {
      kind: "running";
      researchId: string;
      status: "running" | "paused";
      version: number;
      effective: string;
      effectiveSeconds?: number;
      remainingSeconds?: number;
      coverage: string;
      rounds: readonly RoundRecord[];
      currentAction?: string;
      remaining?: string;
      sources?: string;
      dataCutoff?: string;
      honestStopHint?: string | null;
      effectiveTimeHint?: string | null;
      versionOpenedNotice?: string | null;
      lastError?: {
        message: string;
        count: number;
        code?: string;
        params?: Record<string, string | number>;
        detail?: string | null;
      };
      trialBudget?: {used: number; budget: number; remaining: number};
      dataWindowKey?: string | null;
      cumulativeRoundsOnWindow?: number;
      windowCumulativeRoundsAllResearches?: number;
      versionTrialLabel?: string;
      researchCumulativeLabel?: string;
      windowCumulativeLabel?: string;
      workbenchHeaderSummary?: string;
      highSuspicionRoundThreshold?: number;
      latePassPresentation?: LatePassPresentation | null;
      anomaly?: AnomalyPresentation | null;
      recentDialogue?: readonly DialogueTurnView[];
    }
  | {
      kind: "awaiting_confirm";
      researchId: string;
      version: number;
      confirmKind?: "economic" | "coverage" | "data_lineage";
      proposed: string;
      reason: string;
      effect: string;
      whyChange?: readonly EvidenceRef[];
      whoPaysOptional?: string | null;
      createdAt?: string;
      requestId?: string;
    }
  | {
      kind: "completed";
      researchId: string;
      version?: number;
      effective?: string;
      effectiveSeconds?: number;
      remaining?: string;
      remainingSeconds?: number;
      stopReason?: "round_cap" | "time_budget" | "early_stop" | null;
      sources?: string;
      status: "completed" | "ended";
      title: string;
      universeLabel?: string;
      meanReversionOnlyNotice?: string | null;
      repickedFamily?: string | null;
      cnExecutionNotice?: string | null;
      subtitle?: string;
      resultHeadline?: string;
      honestStopHint?: string | null;
      failedVerifierIds?: readonly string[];
      exportKind?: "research_record_only" | "strategy_pack";
      canContinueIterate?: boolean;
      budgetExhausted?: boolean;
      trialBudget?: {used: number; budget: number; remaining: number};
      dataWindowKey?: string | null;
      cumulativeRoundsOnWindow?: number;
      researchRoundsOnWindow?: number;
      researchCumulativeLabel?: string;
      windowCumulativeLabel?: string;
      workbenchHeaderSummary?: string;
      highSuspicionRoundThreshold?: number;
      symbolSelection?: SymbolSelectionSummary;
      confirmDataNotice?: string | null;
      exportBlockerMessages?: readonly string[];
      reverifyOptions?: {
        rounds: readonly {
          roundId: string;
          roundLabel: string;
          methods: readonly {methodId: string; methodLabel: string}[];
        }[];
      };
      pitDetail?: PitDetail | null;
      backtestCutoff?: string | null;
      lastReverification?: {
        roundId: string;
        methodId: string;
        methodLabel: string;
        passed: boolean;
        createdAt: string;
        overallConclusionUnchanged?: boolean;
        stillFailingLabels?: readonly string[];
        userMessage?: string;
      } | null;
      latePassPresentation?: LatePassPresentation | null;
      deferredChangeSummary?: string | null;
      trialCounters?: {
        candidatesEvaluated: number;
        candidatesPassed: number;
        conclusionAttemptNumber: number;
      } | null;
      methodsVerificationPassed?: boolean;
      selectedRoundId: string;
      selectedMethodId: string;
      rounds?: readonly RoundRecord[];
      metrics?: Record<string, number | null>;
      failedExportChecks?: readonly string[];
      eligibility: ExportEligibilityV2;
      overturnedExports?: boolean;
      currentAction?: string;
      anomaly?: AnomalyPresentation | null;
      recentDialogue?: readonly DialogueTurnView[];
    }
  | {kind: "methods"; selected?: string; methods: readonly ValidationMethod[]}
  | {kind: "glossary"; intro: string; entries: readonly GlossaryEntry[]};

export type DesktopView = ViewBody & {
  hostStatus?: HostStatus;
  thesisChangeHint?: string;
  marketDataProgress?: {done: number; total: number; source?: string} | null;
  /** Set when ALPHALOOP_OFFLINE_MARKET_DATA=1. Absent for a normal launch. */
  testData?: boolean;
};

export type MarketDataProgress = {done: number; total: number; source?: string};

export interface DesktopApi {
  fetchView(route: string): Promise<DesktopView>;
  /** Independent of fetchView so a blocking confirm_run cannot hide fetch progress. */
  pollMarketDataProgress?(): Promise<{
    marketDataProgress: MarketDataProgress | null;
    hostStatus?: HostStatus;
  }>;
  createDraft(): Promise<string>;
  confirmRun(
    researchId: string,
    options?: {dataSourceId?: string; unlicensedAcknowledged?: boolean},
  ): Promise<void>;
  /** Confirm-card symbol edit. Both arguments are required; the engine rejects a bare id. */
  setResearchSymbol(researchId: string, symbol: string): Promise<void>;
  /** Answer one ambiguous all-caps ticker. `accept` false keeps it as prose. */
  answerSymbolAsk(researchId: string, token: string, accept: boolean): Promise<void>;
  /** One click on the default-pool hint. Sets that ticker as the symbol. */
  useHintedSymbol(researchId: string, symbol: string): Promise<void>;
  revertSymbolAsk(researchId: string, token: string): Promise<void>;
  removeMarketSide(researchId: string, side: "cn" | "us"): Promise<void>;
  /** Drop one symbol the stated market rejected, so the description does not restore it. */
  dismissMismatchedSymbol(researchId: string, symbol: string): Promise<void>;
  /** Pick the market when the description named none. Nothing is remembered. */
  chooseDefaultMarket(researchId: string, market: "CN" | "US"): Promise<void>;
  unlockBrief(researchId: string, slot?: BriefSlotName): Promise<void>;
  sendDialogue(researchId: string, message: string): Promise<void>;
  pauseResearch(researchId: string): Promise<void>;
  resumeResearch(researchId: string): Promise<void>;
  confirmModification(researchId: string): Promise<void>;
  continueIterate(
    researchId: string,
    options: {userConfirmed: true; highSuspicionAcknowledged?: boolean},
  ): Promise<void>;
  extendResearch(researchId: string, hours: number): Promise<void>;
  deleteResearch(researchId: string): Promise<void>;
  resolveConfirm(researchId: string, decision: ConfirmationDecision, whoPays?: string): Promise<void>;
  exportArtifact(researchId: string, kind: ExportKind): Promise<string>;
  revealExportInFolder(path: string): Promise<void>;
  reverify(researchId: string, roundId: string, methodId: string): Promise<void>;
  reviseMethod(methodId: string, definition: string): Promise<void>;
  createMethod(name: string, definition: string): Promise<void>;
}

export interface LatePassPriorFailure {
  roundId: string;
  versionNumber: number;
  roundNumber: number;
  cumulativeRoundOnWindow: number;
  verificationPassed: boolean;
  failedGateIds: readonly string[];
  paramChanges: readonly [string, string, string][];
  modelChanges: readonly string[];
}

export interface LatePassPresentation {
  show: boolean;
  tone: string;
  cumulativeRoundsOnWindow: number;
  conclusionRoundId: string;
  priorFailureRecords: readonly LatePassPriorFailure[];
}

export interface TrialCounters {
  candidatesEvaluated: number;
  candidatesPassed: number;
  conclusionAttemptNumber: number;
}

export interface LogicStatement {
  statement: string;
  changedFromPrior: boolean;
  changeDescription?: string;
  baselineVersion: number;
}

export interface ImplementationDelta {
  researchMethodChanges: readonly string[];
  modelChanges: readonly string[];
  modelChangesDisplay?: string | null;
  paramChanges: readonly [string, string, string][];
}

export interface ScorecardDimension {
  kind: string;
  kindLabel?: string;
  name: string;
  description: string;
  passThreshold: number;
  comparison: "gte" | "lte" | "gt" | "lt" | "eq";
  comparisonLabel?: string;
  failureDisplay: string;
  unit?: string;
}

export interface PitViolation {
  materialId: string;
  title: string;
  publishedAt: string;
  precision: string;
  reason: string;
  text?: string;
}

export interface PitDetail {
  executed: boolean;
  passed: boolean;
  revision?: string;
  evidenceUsed?: number;
  undatedExcluded?: readonly string[];
  scope?: string;
  note?: string;
  backtestCutoff?: string;
  violationCount?: number;
  firstViolation?: PitViolation | null;
}

export interface RoundRecord {
  roundId: string;
  number: number;
  logicStatement: LogicStatement;
  implementationDelta: ImplementationDelta;
  trialCounters: TrialCounters;
  verificationPassed: boolean;
  pitPassed?: boolean;
}

export type EvidenceKind = "attempt" | "round" | "verification_report" | "simulation_report";

export interface EvidenceRef {
  recordId: string;
  recordedAt: string;
  kind: EvidenceKind;
  summary?: string;
}

export interface ConfirmCardData {
  requestId: string;
  proposedChange: string;
  reason: string;
  effect: string;
  whyChange: readonly EvidenceRef[];
  whoPaysOptional?: string | null;
  confirmKind: "economic" | "coverage" | "data_lineage";
  createdAt: string;
}

export type AnomalyIndicator =
  | "sharpe_outlier"
  | "coverage_shrunk"
  | "high_trial_count"
  | "recent_method_revision";

export interface AnomalyHeuristic {
  sharpeSigmaMultiplier: number;
  trialCountMultiplier: number;
  recentRevisionDays: number;
}

export const ANOMALY_HEURISTIC_DEFAULTS: AnomalyHeuristic = {
  sharpeSigmaMultiplier: 3.0,
  trialCountMultiplier: 2.0,
  recentRevisionDays: 7,
};

export type AnomalyBaseline =
  | { kind: "prior_attempt"; attemptId: string; sharpe: number; sharpeStd?: number; trialCount: number }
  | { kind: "version_1_logic"; sharpe: number; trialCount: number }
  | { kind: "method_scorecard_bounds"; expectedSharpeRange: [number, number] };

export interface AnomalyPresentation {
  indicators: readonly AnomalyIndicator[];
  expandEvidenceFirst: boolean;
  tone: "checklist";
  baseline?: AnomalyBaseline;
}

export interface ExportEligibilityV2 {
  allMethodsPassed: boolean;
  noPendingConfirm: boolean;
  reverifiesPassed: boolean;
  pitExecutedAndPassed: boolean;
}
