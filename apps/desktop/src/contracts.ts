export type ResearchStatus =
  | "draft"
  | "running"
  | "awaiting_confirm"
  | "paused"
  | "completed"
  | "ended";

export type HostStatus = "awaiting_confirm" | "running" | "completed" | "idle";

export type ConfirmationDecision =
  | "approve_new_version"
  | "reject_keep_logic"
  | "pause_and_edit";

export type ExportKind = "strategy_pack" | "research_record";

export interface BriefSettings {
  thesis: string;
  universe: string;
  max_effective_hours: string;
  round1_methods: string;
  coverage_floor: string;
}

export interface ResearchSummary {
  id: string;
  title: string;
  status: ResearchStatus;
  universeLabel?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface ValidationMethod {
  id: string;
  name: string;
  revision: string;
  description: string;
  usageCount?: number;
}

type ViewBody =
  | {kind: "research_list"; awaiting?: ResearchSummary; rows: readonly ResearchSummary[]}
  | {kind: "draft"; researchId: string; messages: readonly string[]; settings: BriefSettings}
  | {kind: "confirm_run"; researchId: string; settings: BriefSettings}
  | {
      kind: "running";
      researchId: string;
      status: "running" | "paused";
      version: number;
      effective: string;
      coverage: string;
      rounds: readonly string[];
      currentAction?: string;
      remaining?: string;
      sources?: string;
      dataCutoff?: string;
    }
  | {
      kind: "awaiting_confirm";
      researchId: string;
      version: number;
      confirmKind?: "economic" | "coverage";
      proposed: string;
      reason: string;
      effect: string;
    }
  | {
      kind: "completed";
      researchId: string;
      status: "completed" | "ended";
      title: string;
      selectedRoundId: string;
      selectedMethodId: string;
      eligibility: {
        allMethodsPassed: boolean;
        noPendingConfirm: boolean;
        reverifiesPassed: boolean;
      };
      overturnedExports?: boolean;
      currentAction?: string;
    }
  | {kind: "methods"; selected?: string; methods: readonly ValidationMethod[]};

export type DesktopView = ViewBody & {
  hostStatus?: HostStatus;
  thesisChangeHint?: string;
};

export interface DesktopApi {
  fetchView(route: string): Promise<DesktopView>;
  createDraft(): Promise<string>;
  confirmRun(researchId: string): Promise<void>;
  sendDialogue(researchId: string, message: string): Promise<void>;
  pauseResearch(researchId: string): Promise<void>;
  resumeResearch(researchId: string): Promise<void>;
  confirmModification(researchId: string): Promise<void>;
  extendResearch(researchId: string, hours: number): Promise<void>;
  deleteResearch(researchId: string): Promise<void>;
  resolveConfirm(researchId: string, decision: ConfirmationDecision): Promise<void>;
  exportArtifact(researchId: string, kind: ExportKind): Promise<void>;
  reverify(researchId: string, roundId: string, methodId: string): Promise<void>;
  reviseMethod(methodId: string, definition: string): Promise<void>;
  createMethod(name: string, definition: string): Promise<void>;
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
  paramChanges: readonly [string, string, string][];
}

export interface ScorecardDimension {
  kind: string;
  name: string;
  description: string;
  passThreshold: number;
  comparison: "gte" | "lte" | "gt" | "lt" | "eq";
  failureDisplay: string;
  unit?: string;
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
  confirmKind: "economic" | "coverage";
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
