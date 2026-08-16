import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import TopFiveView from "../views/TopFiveView";
import { mockTop5Response, mockRunsList } from "./handlers";

// Mock the API client
vi.mock("../api/client", () => ({
  apiClient: {
    listRuns: vi.fn(() => Promise.resolve(mockRunsList)),
    getTop5: vi.fn(() => Promise.resolve(mockTop5Response)),
    exportHtmlUrl: (rid: string) => `/api/runs/${rid}/export`,
  },
}));

describe("TopFiveView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the title", async () => {
    render(
      <MemoryRouter>
        <TopFiveView />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/alphaloop · Quant Lab/i)).toBeInTheDocument();
    });
  });

  it("renders 5 strategy cards after data loads", async () => {
    render(
      <MemoryRouter>
        <TopFiveView />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getAllByTestId("top-five-card")).toHaveLength(5);
    });
  });

  it("renders rank badges #1-#5", async () => {
    render(
      <MemoryRouter>
        <TopFiveView />
      </MemoryRouter>,
    );
    await waitFor(() => {
      for (const n of [1, 2, 3, 4, 5]) {
        expect(screen.getByText(`#${n}`)).toBeInTheDocument();
      }
    });
  });

  it("displays strategy names", async () => {
    render(
      <MemoryRouter>
        <TopFiveView />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/MomentumStrategy/)).toBeInTheDocument();
    });
  });

  it("shows the run selector", async () => {
    render(
      <MemoryRouter>
        <TopFiveView />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("run-selector")).toBeInTheDocument();
    });
  });

  it("shows 'best DSR' in the header", async () => {
    render(
      <MemoryRouter>
        <TopFiveView />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/best DSR/i)).toBeInTheDocument();
    });
  });
});
