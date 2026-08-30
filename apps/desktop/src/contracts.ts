export type ResearchStatus =
  | "draft"
  | "running"
  | "awaiting_confirm"
  | "paused"
  | "completed"
  | "ended";

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
}

export interface ValidationMethod {
  id: string;
  name: string;
  revision: string;
  description: string;
}

export type DesktopView =
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
    }
  | {
      kind: "awaiting_confirm";
      researchId: string;
      version: number;
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
    }
  | {kind: "methods"; selected?: string; methods: readonly ValidationMethod[]};

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
}
