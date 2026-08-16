import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import RunDiagnosticsView from "../views/RunDiagnosticsView";
import { mockDiagnostics } from "./handlers";

vi.mock("../api/client", () => ({
  apiClient: {
    getDiagnostics: vi.fn(() => Promise.resolve(mockDiagnostics)),
  },
}));

describe("RunDiagnosticsView", () => {
  it("renders the title", async () => {
    render(
      <MemoryRouter initialEntries={["/run/test-rid"]}>
        <Routes>
          <Route path="/run/:rid" element={<RunDiagnosticsView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Run diagnostics/)).toBeInTheDocument();
    });
  });

  it("renders the radar chart container", async () => {
    render(
      <MemoryRouter initialEntries={["/run/test-rid"]}>
        <Routes>
          <Route path="/run/:rid" element={<RunDiagnosticsView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("radar-chart")).toBeInTheDocument();
    });
  });

  it("renders the manifest section", async () => {
    render(
      <MemoryRouter initialEntries={["/run/test-rid"]}>
        <Routes>
          <Route path="/run/:rid" element={<RunDiagnosticsView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Manifest/)).toBeInTheDocument();
    });
  });

  it("renders 7 bar items (Q1-Q7)", async () => {
    render(
      <MemoryRouter initialEntries={["/run/test-rid"]}>
        <Routes>
          <Route path="/run/:rid" element={<RunDiagnosticsView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      for (const label of ["Q1 DSR", "Q2 CV", "Q3 Consistency", "Q4 vs Random", "Q5 vs Buy-Hold", "Q6 vs SPY", "Q7 LLM Judge"]) {
        expect(screen.getByTestId(`bar-${label}`)).toBeInTheDocument();
      }
    });
  });

  it("navigates back to top-5", async () => {
    render(
      <MemoryRouter initialEntries={["/run/test-rid"]}>
        <Routes>
          <Route path="/run/:rid" element={<RunDiagnosticsView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Top-5/)).toBeInTheDocument();
    });
  });
});
