// Animation #1 — number rollup
import { useEffect } from "react";
import { animate, useMotionValue, useTransform, MotionValue } from "framer-motion";

export function useRollUpNumber(target: number): MotionValue<string> {
  const count = useMotionValue(0);
  const rounded = useTransform(count, (v) => v.toFixed(3));
  useEffect(() => {
    const controls = animate(count, target, {
      duration: 0.8,
      ease: [0.16, 1, 0.3, 1],
    });
    return controls.stop;
  }, [count, target]);
  return rounded;
}
