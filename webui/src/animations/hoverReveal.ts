// Animation #8 — hover reveal
import type { Variants } from "framer-motion";

export const hoverRevealVariants: Variants = {
  initial: { opacity: 0, y: 4 },
  whileHover: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.2, ease: [0.16, 1, 0.3, 1] },
  },
  whileFocus: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.2, ease: [0.16, 1, 0.3, 1] },
  },
};

export const hoverRevealAnimate = {
  initial: { opacity: 0, y: 4 },
  whileHover: { opacity: 1, y: 0 },
  whileFocus: { opacity: 1, y: 0 },
  transition: { duration: 0.2, ease: [0.16, 1, 0.3, 1] },
};
