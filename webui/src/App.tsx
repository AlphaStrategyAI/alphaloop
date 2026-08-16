import { useState, useCallback } from "react";
import { Routes, Route } from "react-router-dom";
import TopFiveView from "./views/TopFiveView";
import StrategyDetailView from "./views/StrategyDetailView";
import RunDiagnosticsView from "./views/RunDiagnosticsView";
import ReplayView from "./views/ReplayView";
import ShareView from "./views/ShareView";
import DarkModeToggle from "./components/DarkModeToggle";
import KeyboardHelpModal from "./components/KeyboardHelpModal";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";

export default function App() {
  const [helpOpen, setHelpOpen] = useState(false);
  const toggleHelp = useCallback(() => setHelpOpen((o) => !o), []);
  const onRerun = useCallback((rid: string) => {
    // Confirmation modal would call POST /api/runs/<rid>/replay.
    // For v0.7.2 we just confirm via window.confirm.
    if (window.confirm(`Rerun ${rid}? This will re-execute the DAG.`)) {
      // Fire-and-forget POST; the user can re-fetch the run.
      fetch(`/api/runs/${rid}/replay`, { method: "POST" }).catch(() => {});
    }
  }, []);

  useKeyboardShortcuts({ onRerun, onToggleHelp: toggleHelp });

  return (
    <div className="min-h-screen">
      <div
        style={{
          position: "fixed",
          top: 12,
          right: 12,
          zIndex: 50,
          display: "flex",
          gap: 8,
        }}
      >
        <DarkModeToggle />
      </div>
      <Routes>
        <Route path="/" element={<TopFiveView />} />
        <Route path="/strategy/:sid" element={<StrategyDetailView />} />
        <Route path="/run/:rid" element={<RunDiagnosticsView />} />
        <Route path="/replay/:rid" element={<ReplayView />} />
        <Route path="/s/:token" element={<ShareView />} />
      </Routes>
      <KeyboardHelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}
