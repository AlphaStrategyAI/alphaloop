import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import StrategyDetailView from "../views/StrategyDetailView";
import { mockStrategyDetail } from "./handlers";

vi.mock("../api/client", () => ({
  apiClient: {
    getStrategy: vi.fn(() => Promise.resolve(mockStrategyDetail)),
  },
}));

describe("StrategyDetailView", () => {
  it("renders the strategy name", async () => {
    render(
      <MemoryRouter initialEntries={["/strategy/task-0001?rid=test-rid"]}>
        <Routes>
          <Route path="/strategy/:sid" element={<StrategyDetailView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/MomentumStrategy/)).toBeInTheDocument();
    });
  });

  it("renders the params block", async () => {
    render(
      <MemoryRouter initialEntries={["/strategy/task-0001?rid=test-rid"]}>
        <Routes>
          <Route path="/strategy/:sid" element={<StrategyDetailView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("params-block")).toBeInTheDocument();
    });
  });

  it("renders 7 diagnostic items (Q1-Q7)", async () => {
    render(
      <MemoryRouter initialEntries={["/strategy/task-0001?rid=test-rid"]}>
        <Routes>
          <Route path="/strategy/:sid" element={<StrategyDetailView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      for (const q of ["q1", "q2", "q3", "q4", "q5", "q6", "q7"]) {
        expect(screen.getByTestId(`diag-${q}`)).toBeInTheDocument();
      }
    });
  });

  it("renders the equity curve", async () => {
    render(
      <MemoryRouter initialEntries={["/strategy/task-0001?rid=test-rid"]}>
        <Routes>
          <Route path="/strategy/:sid" element={<StrategyDetailView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("equity-curve")).toBeInTheDocument();
    });
  });

  it("has a back link", async () => {
    render(
      <MemoryRouter initialEntries={["/strategy/task-0001?rid=test-rid"]}>
        <Routes>
          <Route path="/strategy/:sid" element={<StrategyDetailView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Back to top-5/)).toBeInTheDocument();
    });
  });
});
