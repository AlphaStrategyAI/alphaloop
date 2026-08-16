import { motion } from "framer-motion";
import { progressFillTransition } from "../animations/progressFill";

interface Props {
  pct: number; // 0-100
  color?: "math" | "stats" | "ai";
  label?: string;
}

export function ProgressBar({ pct, color = "math", label }: Props) {
  const colorVar =
    color === "math"
      ? "var(--color-math)"
      : color === "stats"
      ? "var(--color-stats)"
      : "var(--color-ai)";

  return (
    <div className="w-full">
      {label && (
        <div className="flex justify-between text-xs text-fg-1 mb-1">
          <span>{label}</span>
          <span data-testid="progress-pct">{pct.toFixed(0)}%</span>
        </div>
      )}
      <div
        className="w-full h-2 rounded-sm bg-bg-2 overflow-hidden"
        data-testid="progress-bar"
        data-pct={pct}
      >
        <motion.div
          className="h-full"
          style={{ background: colorVar }}
          initial={{ width: "0%" }}
          animate={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
          transition={progressFillTransition}
        />
      </div>
    </div>
  );
}

export default ProgressBar;
