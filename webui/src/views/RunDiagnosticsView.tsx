import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { apiClient } from "../api/client";
import type { DiagnosticsResponse } from "../types";
import RadarChart from "../components/RadarChart";

export default function RunDiagnosticsView() {
  const { rid } = useParams<{ rid: string }>();
  const [data, setData] = useState<DiagnosticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!rid) return;
    setLoading(true);
    apiClient
      .getDiagnostics(rid)
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, [rid]);

  if (loading) return <div className="p-8 text-fg-1">Loading diagnostics…</div>;
  if (error) return <div className="p-8 text-red-400">{error}</div>;
  if (!data) return <div className="p-8 text-fg-1">No diagnostics</div>;

  const catColor = (cat: string) =>
    cat === "math"
      ? "var(--color-math)"
      : cat === "stats"
      ? "var(--color-stats)"
      : "var(--color-ai)";

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl text-fg-0">Run diagnostics</h1>
            <p className="text-fg-1 text-sm">
              <code style={{ color: "var(--color-math)" }}>{data.rid}</code>
            </p>
          </div>
          <div className="flex gap-2">
            <a href={`/replay/${data.rid}`} className="btn">
              Replay DAG →
            </a>
            <Link to="/" className="btn">
              ← Top-5
            </Link>
          </div>
        </div>

        {/* 3-axis radar */}
        <div className="card mb-5">
          <h2 className="text-sm font-semibold text-fg-0 mb-3">
            Q1–Q7 pass-rate radar
          </h2>
          <RadarChart data={data.radar} compareData={data.compare_with ?? null} />
        </div>

        {/* Bar chart */}
        <div className="card mb-5">
          <h2 className="text-sm font-semibold text-fg-0 mb-3">
            Pass-rate per diagnostic
          </h2>
          <div className="space-y-3">
            {data.bar.map((b) => (
              <div key={b.label} data-testid={`bar-${b.label}`}>
                <div className="flex justify-between text-xs text-fg-1 mb-1">
                  <span>{b.label}</span>
                  <span style={{ color: catColor(b.category) }}>
                    {b.pass_count}/{b.total} ({(b.pass_rate * 100).toFixed(0)}%)
                  </span>
                </div>
                <div
                  style={{
                    background: "var(--bg-2)",
                    height: 10,
                    borderRadius: 5,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${b.pass_rate * 100}%`,
                      height: "100%",
                      background: catColor(b.category),
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Manifest summary */}
        <div className="card">
          <h2 className="text-sm font-semibold text-fg-0 mb-3">Manifest</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-xs text-fg-2">Goal</div>
              <div className="text-fg-0">{data.manifest.goal}</div>
            </div>
            <div>
              <div className="text-xs text-fg-2">Seed</div>
              <div className="text-fg-0">{data.manifest.seed}</div>
            </div>
            <div>
              <div className="text-xs text-fg-2">Model</div>
              <div className="text-fg-0">{data.manifest.llm_model}</div>
            </div>
            <div>
              <div className="text-xs text-fg-2">Commit</div>
              <div className="text-fg-0" style={{ fontSize: 11 }}>
                <code>{data.manifest.git_commit.slice(0, 8)}</code>
              </div>
            </div>
            <div>
              <div className="text-xs text-fg-2">Termination</div>
              <div className="text-fg-0">
                {data.manifest.termination_reason ?? "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-fg-2">Tasks</div>
              <div className="text-fg-0">{data.manifest.task_count}</div>
            </div>
            <div>
              <div className="text-xs text-fg-2">Budget</div>
              <div className="text-fg-0">${data.manifest.budget_usd}</div>
            </div>
            <div>
              <div className="text-xs text-fg-2">Elapsed</div>
              <div className="text-fg-0">
                {data.manifest.finished_at && data.manifest.started_at
                  ? formatElapsed(data.manifest.started_at, data.manifest.finished_at)
                  : "—"}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatElapsed(start: string, end: string): string {
  try {
    const s = new Date(start).getTime();
    const e = new Date(end).getTime();
    const sec = Math.max(0, Math.round((e - s) / 1000));
    if (sec < 60) return `${sec}s`;
    if (sec < 3600) return `${Math.round(sec / 60)}m`;
    return `${(sec / 3600).toFixed(1)}h`;
  } catch {
    return "—";
  }
}
