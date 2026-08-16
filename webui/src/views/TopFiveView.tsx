import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { apiClient } from "../api/client";
import type { TopFiveResponse, RunListItem } from "../types";
import TopFiveCard from "../components/TopFiveCard";
import ShareButton from "../components/ShareButton";
import ScreenshotButton from "../components/ScreenshotButton";
import { cardContainerVariants } from "../animations/cardStagger";

export default function TopFiveView() {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [selectedRid, setSelectedRid] = useState<string | null>(null);
  const [data, setData] = useState<TopFiveResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load list of runs
  useEffect(() => {
    apiClient
      .listRuns()
      .then((r) => {
        setRuns(r);
        if (r.length > 0) setSelectedRid(r[0].rid);
      })
      .catch((e) => setError(String(e)));
  }, []);

  // Load top5 for the selected run
  useEffect(() => {
    if (!selectedRid) return;
    setLoading(true);
    apiClient
      .getTop5(selectedRid)
      .then((top5) => {
        setData(top5);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, [selectedRid]);

  if (error) {
    return (
      <div className="p-8">
        <div className="card max-w-2xl mx-auto text-center">
          <h2 className="text-xl text-fg-0 mb-2">Could not load runs</h2>
          <p className="text-fg-1 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (runs.length === 0 && !loading) {
    return (
      <div className="p-8">
        <div className="card max-w-2xl mx-auto text-center">
          <h2 className="text-xl text-fg-0 mb-2">No runs yet</h2>
          <p className="text-fg-1 text-sm">
            Run <code>alphaloop loop "&lt;goal&gt;"</code> to generate one.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        {/* Topbar */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl text-fg-0" style={{ fontFamily: "var(--font-mono)" }}>
              alphaloop · Quant Lab
            </h1>
            <p className="text-sm text-fg-1 mt-1">
              Top 5 picks {data ? `for ${data.rid}` : ""}
              {data?.metrics?.best_dsr !== undefined &&
                ` · best DSR ${data.metrics.best_dsr.toFixed(3)}`}
            </p>
          </div>
          {runs.length > 0 && (
            <select
              data-testid="run-selector"
              value={selectedRid ?? ""}
              onChange={(e) => setSelectedRid(e.target.value)}
              className="btn"
              style={{ minWidth: 320 }}
            >
              {runs.map((r) => (
                <option key={r.rid} value={r.rid}>
                  {r.rid} — {r.goal.slice(0, 40)}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Quick links */}
        {data && (
          <div className="flex gap-2 mb-4 text-sm items-center">
            <a href={`/run/${data.rid}`} className="btn">
              Run diagnostics →
            </a>
            <a href={`/replay/${data.rid}`} className="btn">
              Replay DAG →
            </a>
            <a href={apiClient.exportHtmlUrl(data.rid)} className="btn">
              Export HTML
            </a>
            <ShareButton rid={data.rid} />
            <ScreenshotButton rid={data.rid} view="top5" />
          </div>
        )}

        {/* Cards */}
        {loading && <div className="text-fg-1">Loading…</div>}
        {data && data.top5 && data.top5.length > 0 && (
          <motion.div
            variants={cardContainerVariants}
            initial="initial"
            animate="animate"
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-5"
            data-testid="top-five-grid"
          >
            {data.top5.map((p) => (
              <TopFiveCard key={p.task_id} pick={p} rid={data.rid} />
            ))}
          </motion.div>
        )}
      </div>
    </div>
  );
}
