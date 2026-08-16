import { Routes, Route } from "react-router-dom";
import TopFiveView from "./views/TopFiveView";
import StrategyDetailView from "./views/StrategyDetailView";
import RunDiagnosticsView from "./views/RunDiagnosticsView";
import ReplayView from "./views/ReplayView";

export default function App() {
  return (
    <div className="min-h-screen">
      <Routes>
        <Route path="/" element={<TopFiveView />} />
        <Route path="/strategy/:sid" element={<StrategyDetailView />} />
        <Route path="/run/:rid" element={<RunDiagnosticsView />} />
        <Route path="/replay/:rid" element={<ReplayView />} />
      </Routes>
    </div>
  );
}
