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

type ViewBody =
  | {kind: "research_list"; awaiting?: ResearchSummary; rows: readonly ResearchSummary[]}
  | {
      kind: "draft";
      researchId: string;
      dialogue: readonly {role: "user" | "assistant"; text: string}[];
      settings: BriefSettings;
    }
  | {
      kind: "confirm_run";
      researchId: string;
      dialogue: readonly {role: "user" | "assistant"; text: string}[];
      settings: BriefSettings;
      chatEnabled?: boolean;
      symbolSelection?: SymbolSelectionSummary;
      confirmDataNotice?: string | null;
      meanReversionOnlyNotice?: string | null;
    }
  | {
      kind: "running";
      researchId: string;
      status: "running" | "paused";
      version: number;
      effective: string;
      coverage: string;
      rounds: readonly RoundRecord[];
      currentAction?: string;
      remaining?: string;
      sources?: string;
      dataCutoff?: string;
      honestStopHint?: string | null;
      effectiveTimeHint?: string | null;
      versionOpenedNotice?: string | null;
      lastError?: {message: string; count: number; code?: string};
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
      recentDialogue?: readonly {role: "user" | "assistant"; text: string}[];
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
      remaining?: string;
      status: "completed" | "ended";
      title: string;
      universeLabel?: string;
      meanReversionOnlyNotice?: string | null;
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
      recentDialogue?: readonly {role: "user" | "assistant"; text: string}[];
    }
  | {kind: "methods"; selected?: string; methods: readonly ValidationMethod[]}
  | {kind: "glossary"; intro: string; entries: readonly GlossaryEntry[]};

export type DesktopView = ViewBody & {
  hostStatus?: HostStatus;
  thesisChangeHint?: string;
  marketDataProgress?: {done: number; total: number; source?: string} | null;
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
  confirmRun(researchId: string): Promise<void>;
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
