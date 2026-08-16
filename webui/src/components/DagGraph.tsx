import { motion } from "framer-motion";
import type { DagNode, DagEdge } from "../types";
import { nodePulseVariants } from "../animations/nodePulse";
import { dagEdgeVariants } from "../animations/edgeFlow";

interface Props {
  nodes: DagNode[];
  edges: DagEdge[];
  activeNode?: string;
  onNodeClick?: (id: string) => void;
}

const NODE_W = 120;
const NODE_H = 60;
const GAP = 40;
const TOTAL_W = 6 * NODE_W + 5 * GAP + 40;
const TOTAL_H = NODE_H + 80;

export function DagGraph({ nodes, edges, activeNode, onNodeClick }: Props) {
  // Layout nodes left-to-right
  const positions = new Map<string, { x: number; y: number }>();
  nodes.forEach((n, i) => {
    positions.set(n.id, {
      x: 20 + i * (NODE_W + GAP),
      y: 20,
    });
  });

  return (
    <div className="overflow-x-auto" data-testid="dag-graph">
      <svg width={TOTAL_W} height={TOTAL_H} style={{ minWidth: TOTAL_W }}>
        {/* Edges */}
        {edges.map((e, i) => {
          const from = positions.get(e.from);
          const to = positions.get(e.to);
          if (!from || !to) return null;
          const x1 = from.x + NODE_W;
          const y1 = from.y + NODE_H / 2;
          const x2 = to.x;
          const y2 = to.y + NODE_H / 2;
          return (
            <motion.path
              key={`${e.from}-${e.to}`}
              d={`M ${x1} ${y1} L ${x2} ${y2}`}
              stroke="var(--color-math)"
              strokeWidth={2}
              fill="none"
              strokeDasharray="6 6"
              variants={dagEdgeVariants}
              initial="initial"
              animate="animate"
              data-testid={`edge-${e.from}-${e.to}`}
            />
          );
        })}
        {/* Nodes */}
        {nodes.map((n) => {
          const pos = positions.get(n.id);
          if (!pos) return null;
          const isActive = activeNode === n.id;
          const statusColor =
            n.status === "done"
              ? "var(--color-stats)"
              : n.status === "running"
              ? "var(--color-ai)"
              : n.status === "failed"
              ? "#EF4444"
              : "var(--fg-2)";
          return (
            <motion.g
              key={n.id}
              transform={`translate(${pos.x}, ${pos.y})`}
              onClick={() => onNodeClick?.(n.id)}
              style={{ cursor: onNodeClick ? "pointer" : "default" }}
              data-testid={`dag-node-${n.id}`}
              variants={isActive ? nodePulseVariants : undefined}
              initial={isActive ? "initial" : false}
              animate={isActive ? "animate" : undefined}
            >
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={10}
                fill="var(--bg-1)"
                stroke={isActive ? "var(--color-math)" : "var(--border)"}
                strokeWidth={isActive ? 2 : 1}
              />
              <text
                x={NODE_W / 2}
                y={20}
                textAnchor="middle"
                fill="var(--fg-0)"
                fontSize={11}
                fontFamily="JetBrains Mono"
              >
                {n.label}
              </text>
              <text
                x={NODE_W / 2}
                y={38}
                textAnchor="middle"
                fill="var(--fg-1)"
                fontSize={10}
                fontFamily="JetBrains Mono"
              >
                {n.elapsed_s !== undefined ? `${n.elapsed_s.toFixed(0)}s` : n.description}
              </text>
              <circle
                cx={NODE_W - 12}
                cy={12}
                r={5}
                fill={statusColor}
              />
            </motion.g>
          );
        })}
      </svg>
    </div>
  );
}

export default DagGraph;
