import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { useState } from "react";
import type { TopPick } from "../types";
import { cardItemVariants } from "../animations/cardStagger";
import { hoverRevealAnimate } from "../animations/hoverReveal";
import MetricNumber from "./MetricNumber";

interface Props {
  pick: TopPick;
  rid: string;
}

export function TopFiveCard({ pick, rid }: Props) {
  const [hovered, setHovered] = useState(false);
  const isPass = pick.passes_all;

  return (
    <motion.div
      variants={cardItemVariants}
      data-testid="top-five-card"
      className="card relative"
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      onFocus={() => setHovered(true)}
      onBlur={() => setHovered(false)}
      tabIndex={0}
      style={{
        boxShadow: hovered ? "var(--shadow-2)" : "none",
        transition: "box-shadow 200ms",
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span
          className="text-xs px-2 py-0.5 rounded-sm"
          style={{
            background: "var(--bg-2)",
            color: "var(--color-math)",
            border: "1px solid var(--border)",
          }}
        >
          #{pick.rank}
        </span>
        <span
          className="text-xs"
          style={{
            color: isPass ? "var(--color-stats)" : "var(--color-ai)",
          }}
        >
          {isPass ? "✓ pass" : "⚠ warn"}
        </span>
      </div>
      <div className="text-sm font-semibold text-fg-0 mb-1">
        {pick.strategy}
      </div>
      <div className="text-xs text-fg-1 mb-3">{pick.factor || "—"}</div>

      {/* Body */}
      <div className="space-y-2">
        <div>
          <div className="text-xs text-fg-2">DSR</div>
          <MetricNumber
            value={pick.dsr}
            className="text-2xl"
            color="math"
          />
        </div>
        <div className="grid grid-cols-3 gap-2">
          <div>
            <div className="text-xs text-fg-2">Sharpe</div>
            <MetricNumber
              value={pick.sharpe}
              decimals={3}
              className="text-sm"
              color="stats"
            />
          </div>
          <div>
            <div className="text-xs text-fg-2">CAGR</div>
            <MetricNumber
              value={pick.cagr}
              decimals={3}
              className="text-sm"
              color="stats"
            />
          </div>
          <div>
            <div className="text-xs text-fg-2">MaxDD</div>
            <MetricNumber
              value={pick.max_dd}
              decimals={3}
              className="text-sm"
              color="stats"
            />
          </div>
        </div>
      </div>

      {/* Hover reveal — extra metrics + link */}
      <motion.div
        {...hoverRevealAnimate}
        animate={hovered ? "whileHover" : "initial"}
        style={{
          opacity: hovered ? 1 : 0,
          marginTop: 12,
          paddingTop: 12,
          borderTop: "1px solid var(--border)",
        }}
      >
        <Link
          to={`/strategy/${pick.task_id}?rid=${encodeURIComponent(rid)}`}
          className="btn btn-primary block text-center"
          data-testid="view-details-link"
        >
          View details →
        </Link>
      </motion.div>
    </motion.div>
  );
}

export default TopFiveCard;
