// TypeScript types mirroring alphaloop.webui.schemas Pydantic models

export interface TopPick {
  rank: number;
  task_id: string;
  strategy: string;
  factor: string;
  params: Record<string, unknown>;
  dsr: number;
  sharpe: number;
  cagr: number;
  max_dd: number;
  passes_all: boolean;
  one_line_thesis?: string;
}

export interface RunSummary {
  rid: string;
  started_at: string;
  finished_at?: string | null;
  elapsed_s: number;
  termination_reason?: string | null;
  goal: string;
}

export interface RunManifest {
  run_id: string;
  goal: string;
  seed: number;
  git_commit: string;
  llm_model: string;
  target_dsr: number;
  budget_usd: number;
  timeout_s: number;
  started_at: string;
  finished_at?: string | null;
  termination_reason?: string | null;
  estimated_cost_usd?: number;
  task_count: number;
}

export interface TopFiveResponse {
  rid: string;
  top5: TopPick[];
  goals: { rid: string; goal: string; started_at: string }[];
  metrics: {
    n_picks: number;
    best_dsr: number;
    best_sharpe: number;
  };
}

export interface StrategyDetailResponse {
  rid: string;
  sid: string;
  pick: TopPick;
  diagnostics: Record<string, DiagnosticItem>;
  equity: number[];
  judge_summary?: string;
}

export interface DiagnosticItem {
  label: string;
  value: number;
  pass: boolean;
  detail?: string;
}

export interface DiagnosticsResponse {
  rid: string;
  manifest: RunManifest;
  radar: RadarPoint[];
  bar: BarPoint[];
  compare_with?: RadarPoint[] | null;
}

export interface RadarPoint {
  axis: string;
  value: number;
  category: "math" | "stats" | "ai";
}

export interface BarPoint {
  label: string;
  pass_rate: number;
  pass_count: number;
  total: number;
  category: "math" | "stats" | "ai";
}

export interface ReplayResponse {
  rid: string;
  dag: {
    nodes: DagNode[];
    edges: DagEdge[];
  };
  timing: Record<string, number>;
}

export interface DagNode {
  id: string;
  label: string;
  description: string;
  status: "pending" | "running" | "done" | "failed";
  elapsed_s?: number;
}

export interface DagEdge {
  from: string;
  to: string;
}

export interface ProgressEvent {
  event: "progress" | "complete" | "error";
  data: {
    node?: string;
    pct?: number;
    completed?: number;
    total?: number;
    elapsed_s?: number;
    termination_reason?: string;
    message?: string;
  };
}

export interface RunListItem {
  rid: string;
  started_at: string;
  elapsed_s: number;
  goal: string;
}
