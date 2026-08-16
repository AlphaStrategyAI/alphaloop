// Animation #3 — node pulse
import type { Variants } from "framer-motion";

export const nodePulseVariants: Variants = {
  initial: {
    scale: 1,
    boxShadow: "0 0 0 0 rgba(91,108,255,0.0)",
  },
  animate: {
    scale: [1, 1.06, 1],
    boxShadow: [
      "0 0 0 0 rgba(91,108,255,0.4)",
      "0 0 0 12px rgba(91,108,255,0.0)",
      "0 0 0 0 rgba(91,108,255,0.0)",
    ],
    transition: { duration: 1.4, repeat: Infinity, ease: "easeOut" },
  },
};
