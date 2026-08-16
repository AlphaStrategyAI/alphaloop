import { useEffect, useState, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { motion } from "framer-motion";
import { apiClient } from "../api/client";
import type { ReplayResponse } from "../types";
import DagGraph from "../components/DagGraph";
import ProgressBar from "../components/ProgressBar";
import { successFlashVariants } from "../animations/successFlash";

export default function ReplayView() {
  const { rid } = useParams<{ rid: string }>();
  const [data, setData] = useState<ReplayResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [activeNode, setActiveNode] = useState<string>("n1_load_data");
  const [progressPct, setProgressPct] = useState(0);
  const [complete, setComplete] = useState(false);
  const [speed, setSpeed] = useState(1);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!rid) return;
    setLoading(true);
    apiClient
      .getReplay(rid)
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, [rid]);

  // Playback animation
  useEffect(() => {
    if (!playing || !data) return;
    const order = data.dag.nodes.map((n) => n.id);
    let idx = 0;
    const tick = () => {
      const nodeId = order[idx];
      setActiveNode(nodeId);
      setProgressPct(((idx + 1) / order.length) * 100);
      idx++;
      if (idx >= order.length) {
        setComplete(true);
        setPlaying(false);
        return;
      }
      timerRef.current = window.setTimeout(tick, 2000 / speed);
    };
    tick();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [playing, data, speed]);

  if (loading) return <div className="p-8 text-fg-1">Loading DAG…</div>;
  if (error) return <div className="p-8 text-red-400">{error}</div>;
  if (!data) return <div className="p-8 text-fg-1">No DAG</div>;

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl text-fg-0">Replay</h1>
            <p className="text-fg-1 text-sm">
              <code style={{ color: "var(--color-math)" }}>{data.rid}</code>
            </p>
          </div>
          <Link to="/" className="btn">
            ← Top-5
          </Link>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3 mb-5">
          <button
            className="btn btn-primary"
            data-testid="play-btn"
            onClick={() => {
              setComplete(false);
              setProgressPct(0);
              setActiveNode(data.dag.nodes[0].id);
              setPlaying(true);
            }}
            disabled={playing}
          >
            ▶ Play
          </button>
          <button
            className="btn"
            onClick={() => setPlaying(false)}
            disabled={!playing}
          >
            ⏸ Pause
          </button>
          <button
            className="btn"
            onClick={() => {
              setPlaying(false);
              setComplete(false);
              setProgressPct(0);
              setActiveNode(data.dag.nodes[0].id);
            }}
          >
            ↺ Reset
          </button>
          <select
            className="btn"
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
          >
            <option value={0.5}>0.5×</option>
            <option value={1}>1×</option>
            <option value={2}>2×</option>
          </select>
        </div>

        {/* Progress bar */}
        <div className="card mb-5">
          <ProgressBar pct={progressPct} color="math" label="Pipeline" />
        </div>

        {/* DAG */}
        <motion.div
          className="card mb-5"
          variants={complete ? successFlashVariants : undefined}
          animate={complete ? "animate" : undefined}
          initial={complete ? "initial" : undefined}
          data-testid="replay-dag"
        >
          <h2 className="text-sm font-semibold text-fg-0 mb-3">
            6-node DAG
          </h2>
          <DagGraph
            nodes={data.dag.nodes}
            edges={data.dag.edges}
            activeNode={activeNode}
          />
        </motion.div>

        {/* Timing */}
        <div className="card">
          <h2 className="text-sm font-semibold text-fg-0 mb-3">Timing</h2>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            {data.dag.nodes.map((n) => (
              <div key={n.id} className="text-sm">
                <div className="text-xs text-fg-2">{n.label}</div>
                <div className="text-fg-0">
                  {data.timing[n.id] !== undefined
                    ? `${data.timing[n.id].toFixed(1)}s`
                    : "—"}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
