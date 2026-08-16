import { useEffect, useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { apiClient } from "../api/client";
import type { StrategyDetailResponse } from "../types";
import MetricNumber from "../components/MetricNumber";

export default function StrategyDetailView() {
  const { sid } = useParams<{ sid: string }>();
  const [params] = useSearchParams();
  const rid = params.get("rid") ?? "";

  const [data, setData] = useState<StrategyDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sid || !rid) return;
    setLoading(true);
    apiClient
      .getStrategy(rid, sid)
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, [rid, sid]);

  if (loading) return <div className="p-8 text-fg-1">Loading strategy {sid}…</div>;
  if (error) return <div className="p-8 text-red-400">{error}</div>;
  if (!data) return <div className="p-8 text-fg-1">No data</div>;

  const { pick, diagnostics, equity } = data;
  const maxEq = Math.max(...equity, 1);

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl text-fg-0">
              #{pick.rank} · {pick.strategy}
            </h1>
            <p className="text-fg-1 text-sm">
              {pick.factor || "—"} · task{" "}
              <code style={{ color: "var(--color-math)" }}>{pick.task_id.slice(0, 8)}</code>
            </p>
          </div>
          <Link to="/" className="btn">
            ← Back to top-5
          </Link>
        </div>

        {/* 3-column pivot */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
          {/* Left column — params */}
          <div className="card col-span-1">
            <h2 className="text-sm font-semibold text-fg-0 mb-3">Params</h2>
            <pre
              data-testid="params-block"
              style={{
                fontSize: 11,
                color: "var(--color-math)",
                background: "var(--bg-0)",
                padding: 12,
                borderRadius: 8,
                overflow: "auto",
                maxHeight: 360,
              }}
            >
              {JSON.stringify(pick.params, null, 2)}
            </pre>
          </div>

          {/* Center column — diagnostics + equity */}
          <div className="col-span-2 space-y-5">
            {/* Equity curve (synthetic) */}
            <div className="card">
              <h2 className="text-sm font-semibold text-fg-0 mb-3">Equity curve</h2>
              <svg
                viewBox="0 0 400 120"
                width="100%"
                height={120}
                style={{ background: "var(--bg-0)", borderRadius: 8 }}
                data-testid="equity-curve"
              >
                <polyline
                  fill="none"
                  stroke="var(--color-math)"
                  strokeWidth={2}
                  points={equity
                    .map((v, i) => {
                      const x = (i / Math.max(equity.length - 1, 1)) * 400;
                      const y = 110 - (v / maxEq) * 100;
                      return `${x},${y}`;
                    })
                    .join(" ")}
                />
              </svg>
              <p className="text-xs text-fg-2 mt-2">
                {equity.length === 0 ? "curve unavailable" : `${equity.length} points`}
              </p>
            </div>

            {/* Diagnostics */}
            <div className="card">
              <h2 className="text-sm font-semibold text-fg-0 mb-3">Diagnostics (Q1–Q7)</h2>
              <div className="space-y-2">
                {Object.entries(diagnostics).map(([key, d]) => (
                  <div
                    key={key}
                    data-testid={`diag-${key}`}
                    className="flex items-center justify-between p-2 rounded"
                    style={{ background: "var(--bg-0)" }}
                  >
                    <div>
                      <div className="text-xs text-fg-1">{d.label}</div>
                      <div className="text-sm text-fg-0">{d.detail ?? ""}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className="metric"
                        style={{
                          color: d.pass
                            ? "var(--color-stats)"
                            : "var(--color-ai)",
                        }}
                      >
                        {d.value.toFixed(3)}
                      </span>
                      <span
                        style={{
                          color: d.pass
                            ? "var(--color-stats)"
                            : "var(--color-ai)",
                        }}
                      >
                        {d.pass ? "✓" : "✗"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right column — metadata */}
          <div className="card col-span-1">
            <h2 className="text-sm font-semibold text-fg-0 mb-3">Metadata</h2>
            <div className="space-y-3 text-sm">
              <div>
                <div className="text-xs text-fg-2">Rank</div>
                <div className="text-fg-0">#{pick.rank}</div>
              </div>
              <div>
                <div className="text-xs text-fg-2">DSR</div>
                <MetricNumber value={pick.dsr} className="text-lg" color="math" />
              </div>
              <div>
                <div className="text-xs text-fg-2">Sharpe</div>
                <MetricNumber
                  value={pick.sharpe}
                  decimals={3}
                  className="text-lg"
                  color="stats"
                />
              </div>
              <div>
                <div className="text-xs text-fg-2">CAGR</div>
                <MetricNumber
                  value={pick.cagr}
                  decimals={3}
                  className="text-lg"
                  color="stats"
                />
              </div>
              <div>
                <div className="text-xs text-fg-2">MaxDD</div>
                <MetricNumber
                  value={pick.max_dd}
                  decimals={3}
                  className="text-lg"
                  color="stats"
                />
              </div>
              <div>
                <div className="text-xs text-fg-2">Passes</div>
                <div
                  style={{
                    color: pick.passes_all
                      ? "var(--color-stats)"
                      : "var(--color-ai)",
                  }}
                >
                  {pick.passes_all ? "✓ all" : "⚠ some"}
                </div>
              </div>
              {data.judge_summary && (
                <div>
                  <div className="text-xs text-fg-2">Judge</div>
                  <div className="text-fg-1 text-xs">{data.judge_summary}</div>
                </div>
              )}
              {pick.one_line_thesis && (
                <div>
                  <div className="text-xs text-fg-2">Thesis</div>
                  <div className="text-fg-1 text-xs italic">
                    {pick.one_line_thesis}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
