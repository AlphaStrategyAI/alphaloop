// Animation #6 — DAG edge flow
import type { Variants } from "framer-motion";

export const dagEdgeVariants: Variants = {
  initial: { strokeDashoffset: 24 },
  animate: {
    strokeDashoffset: 0,
    transition: { duration: 2, repeat: Infinity, ease: "linear" },
  },
};
