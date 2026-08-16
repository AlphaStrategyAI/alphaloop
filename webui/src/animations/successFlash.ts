// Animation #7 — run success flash
import type { Variants } from "framer-motion";

export const successFlashVariants: Variants = {
  initial: { backgroundColor: "var(--bg-1)" },
  animate: {
    backgroundColor: [
      "var(--bg-1)",
      "var(--color-stats)",
      "var(--bg-1)",
    ],
    transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] },
  },
};
