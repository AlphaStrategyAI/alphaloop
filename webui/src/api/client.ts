import axios from "axios";
import type {
  RunListItem,
  TopFiveResponse,
  StrategyDetailResponse,
  DiagnosticsResponse,
  ReplayResponse,
} from "../types";

const api = axios.create({
  baseURL: "/api",
  timeout: 10000,
  headers: { "Content-Type": "application/json" },
});

export const apiClient = {
  listRuns: async (): Promise<RunListItem[]> => {
    const r = await api.get<{ runs: RunListItem[] }>("/runs");
    return r.data.runs;
  },
  getTop5: async (rid: string): Promise<TopFiveResponse> => {
    const r = await api.get<TopFiveResponse>(`/runs/${rid}/top5`);
    return r.data;
  },
  getStrategy: async (rid: string, sid: string): Promise<StrategyDetailResponse> => {
    const r = await api.get<StrategyDetailResponse>(
      `/runs/${rid}/strategies/${sid}`,
    );
    return r.data;
  },
  getDiagnostics: async (
    rid: string,
    compare?: string,
  ): Promise<DiagnosticsResponse> => {
    const r = await api.get<DiagnosticsResponse>(`/runs/${rid}/diagnostics`, {
      params: compare ? { compare } : {},
    });
    return r.data;
  },
  getReplay: async (rid: string): Promise<ReplayResponse> => {
    const r = await api.get<ReplayResponse>(`/runs/${rid}/replay`);
    return r.data;
  },
  exportHtmlUrl: (rid: string): string => `/api/runs/${rid}/export`,
  streamUrl: (rid: string): string => `/api/runs/${rid}/stream`,
  health: async (): Promise<{ status: string; runs_dir: string; n_runs: number }> => {
    const r = await api.get("/healthz");
    return r.data;
  },
};

export default apiClient;
