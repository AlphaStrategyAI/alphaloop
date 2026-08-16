import { motion } from "framer-motion";
import { useRollUpNumber } from "../animations/rollUpNumber";

interface Props {
  value: number;
  decimals?: number;
  className?: string;
  color?: "math" | "stats" | "ai" | "fg-0";
  prefix?: string;
  suffix?: string;
}

export function MetricNumber({
  value,
  decimals,
  className = "",
  color = "math",
  prefix = "",
  suffix = "",
}: Props) {
  const rounded = useRollUpNumber(value);
  const colorVar =
    color === "math"
      ? "var(--color-math)"
      : color === "stats"
      ? "var(--color-stats)"
      : color === "ai"
      ? "var(--color-ai)"
      : "var(--fg-0)";

  return (
    <motion.span
      className={`metric ${className}`}
      style={{ color: colorVar, fontVariantNumeric: "tabular-nums" }}
      data-testid="metric-number"
    >
      {prefix}
      <motion.span>{decimals !== undefined ? value.toFixed(decimals) : rounded}</motion.span>
      {suffix}
    </motion.span>
  );
}

export default MetricNumber;
